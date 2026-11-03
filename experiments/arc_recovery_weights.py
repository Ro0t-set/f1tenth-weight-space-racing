"""Reasoned edits to buffers of the frozen ArcNetwork. No fitted coefficients."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from from_scratch import ArcNetwork, ROOT, piecewise_slopes, radial_envelope

PARENT = ROOT / 'artifacts/from_scratch/arc_dynamic.pt'
OUT = ROOT / 'artifacts/arc_recovery'


def steady_state(curvature, speed):
    """Steady-state solution of the upstream lateral and yaw equations at ax=0."""
    if speed < .5:
        return np.arctan(.3302 * curvature), 0.
    friction_gravity = 1.0489 * 9.81
    understeer = (1. / 4.718 - 1. / 5.4562) / friction_gravity
    effective_length = .3302 + understeer * speed**2
    delta = np.clip(effective_length * curvature, -.4189, .4189)
    beta = (.17145 - speed**2 / (friction_gravity * 5.4562)) * delta / effective_length
    return delta, beta


def speed_program(name, curvature, length):
    # Retain the original stop and low-speed manoeuvre on very short arcs.
    # A 0.65/m bend permits sqrt(7/.65) m/s on the curve ahead. Carry that
    # terminal speed into the braking-distance formula on visible corridors.
    carry_fraction = np.clip(length - 1., 0., 1.)
    brake_distance = max(length - .25, 0.)
    terminal_curvature = .3 if name == 'rolling_corner' else .65
    speed_squared = 12. * brake_distance + carry_fraction * (7. / terminal_curvature)
    if name == 'rolling_corner':
        # The medium-radius continuation reduces abrupt braking when an arc
        # loses a visibility bin. Cap speed by the simulator's full stopping
        # deceleration over the visible distance, even on this continuation.
        speed_squared = min(speed_squared, 2. * 9.51 * brake_distance)
    lateral_limit = 7.
    if name in ('bend_carry', 'clear_straight', 'rolling_corner') and .1 <= abs(curvature) <= .65:
        # Preserve the 10m/s high-speed cap; permit more lateral acceleration
        # in established, visible bends. Short, sharp manoeuvres keep 7m/s².
        lateral_limit += 2. * np.clip((length - 2.) / 2.5, 0., 1.)
    # Only the straight arc can exceed 10m/s when its stopping length allows.
    # The closest nonzero curvature still uses the original 10m/s cap.
    top = 12. if name == 'clear_straight' and curvature == 0. else 10.
    return min(np.sqrt(speed_squared), np.sqrt(lateral_limit / max(abs(curvature), .001)), top)


def build(name, with_launch=False, verify=None):
    meta = json.loads(PARENT.with_suffix('.json').read_text())
    curvature = np.array(meta['curvature'])
    horizons = np.array(meta['horizons'])
    parent = torch.jit.load(str(PARENT), map_location='cpu').eval()
    valid = parent.valid.numpy().astype(bool)
    knots = parent.knots.numpy().astype(float)
    angles = np.linspace(-2.35, 2.35, 1080)
    if with_launch:
        from arc_launch_weights import build_launch_envelope
        envelope = build_launch_envelope(curvature, horizons, angles, valid,
                                         lambda k, h: speed_program(name, k, h), steady_state)
    else:
        envelope = np.zeros_like(parent.envelope.numpy())
        for i, k in enumerate(curvature):
            for j, horizon in enumerate(horizons):
                if valid[i, j]:
                    _, beta = steady_state(k, speed_program(name, k, horizon))
                    envelope[i, j] = radial_envelope(k, horizon, angles, beta=beta)
        envelope = np.maximum.accumulate(envelope, axis=1)
    speed = np.array([[speed_program(name, k, h) for h in knots] for k in curvature])
    steer = np.array([[steady_state(k, v)[0] for v in values] for k, values in zip(curvature, speed)])
    model = ArcNetwork(envelope, valid, horizons, curvature, knots, piecewise_slopes(speed, knots),
                       piecewise_slopes(steer, knots), speed[:, 0], steer[:, 0], True).eval()
    meta['speed_program'] = name
    meta['head_specification'] = 'Carry a terminal bend speed after 1m; preserve the original short manoeuvre and 10m/s cap except the clear_straight zero-curvature arc.'
    if verify:
        frozen = torch.jit.load(str(verify)).eval()
        assert frozen.code == torch.jit.script(model).code
        for key, value in model.state_dict().items():
            if not torch.equal(value, frozen.state_dict()[key]):
                raise ValueError(f'Coefficient mismatch in {key}')
        print(f'All {sum(v.numel() for v in model.state_dict().values())} coefficients and forward graph match {verify}')
        return
    return save(name + ('_launch' if with_launch else ''), model, meta)


def combine(pace_path, launch_path, name):
    """Compose independent edits, rejecting ambiguous overwrites."""
    base = torch.jit.load(str(PARENT)).state_dict()
    pace = torch.jit.load(str(pace_path)).state_dict()
    launch = torch.jit.load(str(launch_path)).state_dict()
    meta = json.loads(pace_path.with_suffix('.json').read_text())
    changes = {}
    for key, original in base.items():
        altered = launch[key] != original
        if not altered.any():
            continue
        if key != 'envelope':
            raise ValueError(f'Launch changes {key}, review the composition explicitly')
        conflict = altered & (pace[key] != original) & (pace[key] != launch[key])
        if conflict.any():
            raise ValueError(f'{int(conflict.sum())} overlapping coefficient edits in {key}')
        pace[key][altered] = launch[key][altered]
        changes[key] = int(altered.sum())
    k = np.asarray(meta['curvature'])
    h = np.asarray(meta['horizons'])
    model = ArcNetwork(pace['envelope'], pace['valid'], h, k, pace['knots'], pace['speed_slopes'],
                       pace['steer_slopes'], pace['speed_base'], pace['steer_base'], True).eval()
    model.load_state_dict(pace, strict=True)
    meta.update(speed_program=pace_path.stem, launch_program=launch_path.stem, launch_changes=changes,
                component_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [pace_path, launch_path]})
    return save(name, model, meta)


def save(name, model, meta):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f'{name}.pt'
    torch.jit.script(model).save(str(path))
    torch.save(model.state_dict(), OUT / f'{name}_weights.pth')
    parent = torch.jit.load(str(PARENT)).state_dict()
    assert all(parent[k].shape == v.shape and torch.isfinite(v).all() for k,v in model.state_dict().items())
    diff = {k: int((v != parent[k]).sum()) for k,v in model.state_dict().items() if not torch.equal(v, parent[k])}
    manifest = dict(meta, name=name, changed_from_arc_dynamic=diff,
                    parent_sha256=hashlib.sha256(PARENT.read_bytes()).hexdigest(),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size,
                    nonzero_scalars=sum(int(torch.count_nonzero(t)) for t in model.state_dict().values()))
    path.with_suffix('.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(path)
    return path


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('--compose', nargs=2, type=Path, metavar=('PACE', 'LAUNCH'))
    ap.add_argument('--launch', action='store_true', help='Include the slow departure envelopes')
    ap.add_argument('--verify', type=Path, help='Rebuild in memory and compare against this artifact')
    args = ap.parse_args()
    if args.compose:
        if not args.name.isidentifier():
            ap.error('Use a simple artifact name')
        combine(*args.compose, name=args.name)
    elif args.name in ('carry', 'bend_carry', 'clear_straight', 'rolling_corner'):
        build(args.name, args.launch, args.verify)
    else:
        ap.error('Unknown speed program')
