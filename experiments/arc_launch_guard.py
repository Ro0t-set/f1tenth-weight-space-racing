"""Patch the two short visibility horizons of the frozen recovery checkpoint."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
RECOVERED = ROOT / 'artifacts/arc_recovery/arc_recovered.pt'
PARENT = ROOT / 'artifacts/from_scratch/arc_dynamic.pt'
OUT = ROOT / 'artifacts/arc_recovery/launch_guard.pt'


def build_launch_guard(envelope, parent_envelope, angles):
    """Protect the currently occupied footprint while the steering responds."""
    half_width = .31 / 2
    half_axle_length = (.15875 + .17145) / 2
    absolute_angle = np.abs(angles)
    forward_side = (absolute_angle >= np.arctan(half_width / half_axle_length)) & (absolute_angle < np.pi / 2)
    required = np.zeros_like(angles)
    # The project uses one centimetre of scan noise. Two noise widths cover
    # a shorter return on the next scan. At the simulator's 0.5 m/s low-speed
    # transition, add the 5 ms TTC distance along the measured ray.
    required[forward_side] = (half_width / np.sin(absolute_angle[forward_side])
                              + 2 * .01 + .005 * .5 * np.cos(absolute_angle[forward_side]))
    # Free length begins to command motion at 0.25 m. For two 0.5 m bins
    # constrained by the same ray, 0.03 m of the 0.04 m activation ramp
    # corresponds to precisely that threshold.
    required[forward_side] += .03
    floor = torch.as_tensor(required.reshape(-1, 6).max(axis=1), dtype=envelope.dtype)
    result = envelope.clone()
    result[:, :2] = torch.maximum(envelope[:, :2], torch.minimum(parent_envelope[:, :2], floor))
    return result


def build():
    model = torch.jit.load(str(RECOVERED)).eval()
    parent = torch.jit.load(str(PARENT)).eval()
    angles = np.linspace(-2.35, 2.35, 1080)
    guard = build_launch_guard(model.envelope, parent.envelope, angles)
    changed = int((guard != model.envelope).sum())
    assert changed > 0 and torch.equal(guard[:, 2:], model.envelope[:, 2:])
    model.envelope.copy_(guard)
    model.save(str(OUT))
    manifest = dict(parent=RECOVERED.name, parent_sha256=hashlib.sha256(RECOVERED.read_bytes()).hexdigest(),
                    sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(), changed_envelope_scalars=changed,
                    changed_horizons_m=[.5, 1.], scan_noise_reserve_m=.02, ttc_window_s=.005,
                    reference_velocity_mps=.5, width_m=.31, axle_length_m=.3302,
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    OUT.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return OUT


if __name__ == '__main__':
    print(build())
