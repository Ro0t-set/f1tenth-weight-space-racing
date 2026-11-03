"""Deterministic paired evaluation; no training, fitting, or gradient computation."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
sys.path[:0] = [str(ROOT / 'upstream/gym'), str(ROOT / 'upstream/src')]
import numpy as np
import torch
import pyglet
pyglet.options['shadow_window'] = False
from f110_gym.envs.f110_env import F110Env
from f110_gym.envs.base_classes import Integrator
import wrapper.wrapper as wrapper_module
from wrapper.wrapper import F110_Wrapped
from gymnasium.spaces import Box
from stable_baselines3.common.policies import ActorCriticPolicy

torch.set_num_threads(1)
torch.set_grad_enabled(False)
# Suppress only the historical CSV side effect, not reward or physics.
wrapper_module.logger = lambda *args, **kwargs: None
MAPS = ROOT / 'upstream/map/f1tenth_racetracks'
BASE = ROOT / 'upstream/train_test/best_global_model.zip'
DEV = ['BrandsHatch', 'Catalunya', 'Melbourne', 'YasMarina']

def load_state(path):
    with zipfile.ZipFile(path) as archive:
        return torch.load(io.BytesIO(archive.read('policy.pth')), map_location='cpu', weights_only=True)

def load_policy(path):
    if Path(path).suffix == '.pt':
        from from_scratch import ScriptPolicy
        return ScriptPolicy(path)
    policy = ActorCriticPolicy(Box(-1., 1., (1080,), dtype=np.float64),
                              Box(-1., 1., (2,), dtype=np.float64), lambda _: 0.)
    policy.load_state_dict(load_state(path), strict=True)
    policy.set_training_mode(False)
    return policy

def evaluate(policy, maps, seeds, max_steps=20000, trace=False, state_trace=False):
    if trace and state_trace:
        raise ValueError('Choose observation traces or dense state traces, not both.')
    rows, traces = [], []
    for name in maps:
        folder = MAPS / name
        # Direct construction avoids Gym's changed API wrappers. Physics is upstream.
        raw = F110Env(map=str(folder / f'{name}_map'), map_ext='.png',
                      num_agents=1, timestep=.01, integrator=Integrator.RK4)
        env = F110_Wrapped(raw, random_map=False)
        env.set_map_path(str(folder))
        env.set_optimize_speed(False)
        for seed in seeds:
            # Upstream reset rotates the raceline and leaves some reward counters behind.
            # Restore canonical state before EVERY episode, equally for both policies.
            env.set_raceliens()
            env.count = 0
            env.one_lap_done = False
            env.number_of_base_reward_give = 10
            np.random.seed(seed)
            for car in raw.sim.agents:
                car.seed = seed
            with contextlib.redirect_stdout(io.StringIO()):
                obs = env.reset()
            start = [float(raw.poses_x[0]), float(raw.poses_y[0]), float(raw.poses_theta[0])]
            total_reward = 0.
            max_progress = 0.
            speeds, commands, steer, front = [], [], [], []
            states, slip_run, longest_slip, counter_run, longest_counter = [], 0, 0, 0, 0
            success = False
            episode_trace = []
            started = time.monotonic()
            for step in range(max_steps):
                action, _ = policy.predict(obs, deterministic=True)
                if trace and step % 10 == 0:
                    episode_trace.append({'step': step, 'obs': obs.astype(np.float32),
                                          'action': action.copy(), 'state': raw.sim.agents[0].state.copy()})
                elif state_trace:
                    # Offline footprint/path audit at every physics step. These
                    # states never enter the policy's unchanged LiDAR input.
                    episode_trace.append({'step': step, 'state': raw.sim.agents[0].state.copy()})
                vehicle_state = raw.sim.agents[0].state.copy()
                states.append(vehicle_state)
                slipping = abs(vehicle_state[6]) >= np.deg2rad(5.) and vehicle_state[3] >= 3.
                countersteering = slipping and vehicle_state[2]*vehicle_state[5] < -.01
                slip_run = slip_run+1 if slipping else 0
                counter_run = counter_run+1 if countersteering else 0
                longest_slip, longest_counter = max(longest_slip,slip_run), max(longest_counter,counter_run)
                front.append(float(np.min((obs[500:580] + 1.) * 15.)))
                commands.append(float(env.un_normalise_actions(action)[1]))
                steer.append(float(action[0]))
                with contextlib.redirect_stdout(io.StringIO()):
                    obs, reward, done, _ = env.step(action)
                total_reward += reward
                speeds.append(float(raw.sim.agents[0].state[3]))
                max_progress = max(max_progress, env.count / len(env.race_line_x))
                collision = bool(raw.collisions[0])
                # Waypoint completion plus actual start-line crossing: neither alone
                # is enough (the legacy crossing detector can fire on shortcuts).
                if env.one_lap_done:
                    max_progress = 1.
                success = max_progress >= .99 and raw.lap_counts[0] >= 1 and not collision
                if success or done:
                    break
            states = np.asarray(states)
            slip = np.abs(np.rad2deg(states[:,6]))
            row = dict(map=name, seed=seed, start=start, success=bool(success),
                       collision=collision, timeout=not(success or done),
                       steps=step+1, seconds=round((step+1)*.01, 2),
                       progress=max_progress, reward=total_reward,
                       mean_speed=float(np.mean(speeds)),
                       mean_speed_command=float(np.mean(commands)),
                       speed_command_p95=float(np.quantile(commands,.95)),
                       steer_abs_p95=float(np.quantile(np.abs(steer),.95)),
                       front_min=float(min(front)), wall_seconds=time.monotonic()-started,
                       max_abs_beta_deg=float(slip.max()), p95_abs_beta_deg=float(np.quantile(slip,.95)),
                       longest_slip_gt5_s=longest_slip*.01,
                       longest_countersteer_slip_s=longest_counter*.01,
                       slip_gt5_s=float(((slip>=5.) & (states[:,3]>=3.)).sum()*.01))
            rows.append(row)
            if trace or state_trace:
                traces.append((name,seed,episode_trace))
            print(json.dumps(row), flush=True)
    return rows, traces

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--checkpoint', type=Path, default=BASE)
    ap.add_argument('--maps', nargs='+', default=DEV)
    ap.add_argument('--seeds', nargs='+', type=int, default=[101,202,303])
    ap.add_argument('--max-steps', type=int, default=20000)
    ap.add_argument('--out', type=Path, required=True)
    trace_args = ap.add_mutually_exclusive_group()
    trace_args.add_argument('--trace', action='store_true')
    trace_args.add_argument('--state-trace', action='store_true', help='Record states every .01s for offline geometry only')
    args = ap.parse_args()
    if args.maps in [['holdout'], ['all']]:
        excluded = DEV if args.maps == ['holdout'] else []
        args.maps = sorted(p.name for p in MAPS.iterdir()
                           if (p / f'{p.name}_raceline.csv').exists() and p.name not in excluded)
    policy = load_policy(args.checkpoint)
    rows, traces = evaluate(policy, args.maps, args.seeds, args.max_steps, args.trace, args.state_trace)
    payload = dict(checkpoint=str(args.checkpoint.resolve()),
                   sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                   protocol='one lap: >=99% ordered waypoints AND >=1 start crossing; no collision',
                   max_steps=args.max_steps, rows=rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2)+'\n')
    if args.trace or args.state_trace:
        for name,seed,trace in traces:
            extra = dict(obs=np.stack([t['obs'] for t in trace]),
                         actions=np.stack([t['action'] for t in trace])) if args.trace else {}
            np.savez_compressed(args.out.with_name(f'{args.out.stem}_{name}_{seed}_trace.npz'),
                                states=np.stack([t['state'] for t in trace]),
                                steps=np.array([t['step'] for t in trace]), **extra)
    print('SUMMARY', len(rows), 'success',sum(r['success'] for r in rows),
          'collisions',sum(r['collision'] for r in rows), flush=True)

if __name__ == '__main__':
    main()
