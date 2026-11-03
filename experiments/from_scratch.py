"""Compile a small geometric neural actor from zero. No learned tensors or fit.

Inference uses fixed tensors, pooling, ReLU, maxout and softmax only. The
rectangle/vehicle calculations run once in the compiler, never in predict().
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'artifacts/from_scratch'


class ArcNetwork(nn.Module):
    def __init__(self, envelope, valid, horizons, curvature, knots, speed_slopes,
                 steer_slopes, speed_base, steer_base, mode_local: bool):
        super().__init__()
        self.mode_local = mode_local
        for name, value in dict(envelope=envelope, valid=valid,
                                delta_h=np.diff(np.r_[0., horizons]),
                                prior=.3*(curvature/1.2)**2, knots=knots,
                                speed_slopes=speed_slopes, steer_slopes=steer_slopes,
                                speed_base=speed_base, steer_base=steer_base).items():
            self.register_buffer(name, torch.as_tensor(value, dtype=torch.float32))
        indices = np.arange(len(curvature))
        mask = np.where(np.abs(indices[:, None]-indices[None, :]) <= 1, 0., -10000.)
        self.register_buffer('mode_mask', torch.tensor(mask, dtype=torch.float32))

    def forward(self, observations):
        # Conservative angular pooling uses every original beam, including
        # narrow nearby obstacles that angular averaging could hide.
        distance = 15.*observations + 15.
        sectors = -F.max_pool1d(-distance.unsqueeze(1), 6, 6).squeeze(1)
        violation = F.relu(self.envelope.unsqueeze(0)-sectors[:, None, None, :]).amax(-1)
        feasible = F.relu(1.-violation/.04)*self.valid.unsqueeze(0)
        free_length = (feasible*self.delta_h).sum(-1)
        score = free_length-self.prior
        if self.mode_local:
            # Maxout selects one mode. Softmax interpolates only its immediate
            # neighbours, rather than averaging separated left/right passages.
            winner = score.argmax(-1)
            score = score+self.mode_mask.index_select(0, winner)
        attention = torch.softmax(score/.15, dim=-1)
        features = F.relu(free_length.unsqueeze(-1)-self.knots)
        speed = self.speed_base+(features*self.speed_slopes).sum(-1)
        steer = self.steer_base+(features*self.steer_slopes).sum(-1)
        action_steer = (attention*steer).sum(-1)/.4189
        action_speed = ((attention*speed).sum(-1)-7.5)/12.5
        return torch.stack((action_steer, action_speed), dim=-1).clamp(-1., 1.)


class ScriptPolicy:
    """Adapter only: unchanged LiDAR observation -> normalized action."""
    def __init__(self, path):
        self.model = torch.jit.load(str(path), map_location='cpu').eval()

    def predict(self, observation, deterministic=True):
        x = np.asarray(observation, dtype=np.float32)
        single = x.ndim == 1
        if single:
            x = x[None, :]
        if x.ndim != 2 or x.shape[-1] != 1080:
            raise ValueError('Expected the original 1080 LiDAR observations')
        with torch.no_grad():
            y = self.model(torch.from_numpy(x)).numpy()
        return (y[0] if single else y), None


def radial_envelope(kappa, horizon, angles, margin=.05, beta=0.):
    """Ray/rectangle intersections of the swept footprint, only at compile time."""
    distances = np.linspace(0., horizon, max(2, int(np.ceil(horizon/.03))+1))
    yaw = kappa*distances
    if abs(kappa) < 1e-12:
        xy = np.c_[distances, np.zeros_like(distances)]
    else:
        xy = np.c_[np.sin(yaw)/kappa, (1.-np.cos(yaw))/kappa]
    # In the dynamic variant, velocity/course is offset from body heading by
    # the analytically predicted steady slip. Body orientation stays yaw.
    rotation = np.array([[np.cos(beta), -np.sin(beta)], [np.sin(beta), np.cos(beta)]])
    xy = xy @ rotation.T
    c, s = np.cos(yaw), np.sin(yaw)
    # Ray origin and direction in each swept rectangle's local frame.
    origin = np.c_[-xy[:, 0]*c-xy[:, 1]*s, xy[:, 0]*s-xy[:, 1]*c]
    relative = angles[None, :]-yaw[:, None]
    direction = np.stack([np.cos(relative), np.sin(relative)], -1)
    half = np.array([.58, .31])/2. + margin
    safe_direction = np.where(np.abs(direction)<1e-12, 1e-12, direction)
    t1 = (-half-origin[:, None, :])/safe_direction
    t2 = (half-origin[:, None, :])/safe_direction
    entry = np.minimum(t1, t2).max(-1)
    leave = np.maximum(t1, t2).min(-1)
    ranges = np.where(leave >= np.maximum(entry, 0.), leave, 0.).max(0)
    # Use the largest required distance over each 6-beam sector, paired with
    # the smallest actual LiDAR distance in that sector at inference.
    return ranges.reshape(180, 6).max(-1)


def piecewise_slopes(values, knots):
    slopes = np.diff(values, axis=-1)/np.diff(knots)
    slopes = np.c_[slopes, np.zeros(len(values))]
    return np.c_[slopes[:, :1], np.diff(slopes, axis=-1)]


def build(name):
    dynamic = name in ('arc_dynamic', 'arc_dynamic_pace')
    lateral_limit = 8. if name == 'arc_dynamic_pace' else 7.
    speed_limit = 11. if name == 'arc_dynamic_pace' else 10.
    from evaluate import ROOT as _root
    from f110_gym.envs.dynamic_models import vehicle_dynamics_st
    params = [1.0489, 4.718, 5.4562, .15875, .17145, .074, 3.74, .04712,
              -.4189, .4189, -3.2, 3.2, 7.319, 9.51, -5., 20.]
    def steady_state(k, v):
        if v < .5:
            return np.arctan(.3302*k), 0.
        x = np.zeros(7); x[3] = v
        def f(y): return vehicle_dynamics_st(y, np.zeros(2), *params)[5:7]
        xr = x.copy(); xr[5] = 1.
        xb = x.copy(); xb[6] = 1.
        xd = x.copy(); xd[2] = 1.
        gain = -np.linalg.solve(np.c_[f(xr), f(xb)], f(xd))
        delta = np.clip(k*v/gain[0], -.4189, .4189)
        return delta, gain[1]*delta
    # Symmetric architecture and coefficients, with no map IDs or raceline input.
    positive = np.array([.05, .1, .18, .3, .45, .65, .9, 1.2])
    curvature = np.r_[-positive[::-1], 0., positive]
    horizons = np.array([.5, 1., 1.5, 2., 3., 4.5, 6., 8., 11.])
    angles = np.linspace(-2.35, 2.35, 1080)
    valid = np.abs(curvature[:, None]*horizons[None, :]) <= 1.8
    envelope = np.zeros((len(curvature), len(horizons), 180))
    for i, k in enumerate(curvature):
        for j, horizon in enumerate(horizons):
            if valid[i, j]:
                v = min(np.sqrt(12.*max(horizon-.25, 0.)), np.sqrt(lateral_limit/max(abs(k), .001)), speed_limit)
                beta = steady_state(k, v)[1] if dynamic else 0.
                envelope[i, j] = radial_envelope(k, horizon, angles, beta=beta)
    # Preserve nesting: later envelopes must include all shorter required sweeps,
    # including their different predicted speeds/slips in the dynamic program.
    if dynamic:
        envelope = np.maximum.accumulate(envelope, axis=1)
    knots = np.array([0., .25, .5, 1., 1.5, 2., 3., 4.5, 6., 8., 11.])
    # Physical limits: <=6m/s² planned deceleration, <=7m/s² lateral acceleration,
    # 10m/s top command. Piecewise-linear coefficients come from formulas only.
    speed = np.minimum(np.sqrt(12.*np.maximum(knots[None, :]-.25, 0.)),
                       np.sqrt(lateral_limit/np.maximum(np.abs(curvature[:, None]), .001)))
    speed = np.minimum(speed, speed_limit)
    # Exact steady-state linear single-track yaw gain from the existing equations.
    # No rollout data or fitted coefficients enter this calculation.
    steer = np.array([[steady_state(k, v)[0] for v in row] for k, row in zip(curvature, speed)])
    model = ArcNetwork(envelope, valid, horizons, curvature, knots,
                       piecewise_slopes(speed, knots), piecewise_slopes(steer, knots),
                       speed[:, 0], steer[:, 0], name != 'arc_soft').eval()
    DEST.mkdir(parents=True, exist_ok=True)
    path = DEST/f'{name}.pt'
    scripted = torch.jit.script(model)
    scripted.save(str(path))
    torch.save(model.state_dict(), DEST/f'{name}_weights.pth')
    manifest = dict(name=name, method='all tensors constructed analytically from scratch; no training/fitting/optimizer or imported learned weights',
                    input='original 1080 instantaneous normalized LiDAR rays',
                    architecture='minpool1080->180; 17 curvature x9 horizon envelope neurons; ReLU/maxpool; piecewise ReLU heads; '+('global softmax' if name=='arc_soft' else 'maxout and local softmax'),
                    envelope_dynamics='nested sweeps with steady-state slip computed from original vehicle equations' if dynamic else 'no slip in footprint path',
                    lateral_acceleration_limit_mps2=lateral_limit, speed_limit_mps=speed_limit,
                    curvature=curvature.tolist(), horizons=horizons.tolist(), margin_m=.05,
                    footprint_m=[.58, .31], sector_pool=6, horizon_heading_limit_rad=1.8,
                    tensor_scalars=sum(t.numel() for t in model.state_dict().values()),
                    nonzero_scalars=sum(int(torch.count_nonzero(t)) for t in model.state_dict().values()),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size,
                    limitations=['Static visibility of constant-curvature arcs, not a proof of dynamic safety.',
                                 'Only instantaneous LiDAR: current speed/slip are not observable.',
                                 'Soft interpolation can still invalidate clearance between discrete arcs.',
                                 'No claim of global racing-line optimality.'])
    path.with_suffix('.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('name', choices=['arc_soft', 'arc_mode', 'arc_dynamic', 'arc_dynamic_pace'])
    build(ap.parse_args().name)
