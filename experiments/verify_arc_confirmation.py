"""Apply the frozen three-way verifier to the separate confirmation cohort."""
import argparse
from pathlib import Path

import numpy as np

import verify_arc_recovery as verifier
from trajectory_audit import Geometry, ROOT


CONFIRMATION_SEEDS = [71606, 71707, 71808, 71909, 72010]
FIRST_RUN = ROOT / 'results/arc_recovery'


def check_austin(folder, manifest, path):
    payload = verifier.read_json(path)
    if payload['sha256'] != manifest['checkpoints']['candidate']['sha256'] or payload['max_steps'] != 20000:
        raise ValueError('Austin replay does not match frozen candidate and step limit')
    cases = [r for r in payload['rows'] if r['map'] == 'Austin' and r['seed'] == 71303]
    if len(cases) != 1:
        raise ValueError('Expected one Austin 71303 replay')
    row = cases[0]
    verified = verifier.read_json(FIRST_RUN / 'verified_three_way.json')
    if verified['freeze_sha256'] != verifier.digest(FIRST_RUN / 'holdout_manifest.json'):
        raise ValueError('First freeze differs from recorded verification')
    previous = {}
    for model in verifier.MODELS:
        baseline_path = FIRST_RUN / f'final_{model}.json'
        if verifier.digest(baseline_path) != verified['evaluation_json_sha256'][model]:
            raise ValueError(f'{model}: first evaluation changed')
        reference = next(r for r in verifier.read_json(baseline_path)['rows'] if r['map'] == 'Austin' and r['seed'] == 71303)
        if reference['start'] != row['start']:
            raise ValueError('Austin replay start differs')
        previous[model] = {key: reference[key] for key in ('success', 'collision', 'timeout', 'seconds', 'progress')}
    trace_path = path.with_name(f'{path.stem}_Austin_71303_trace.npz')
    with np.load(trace_path) as trace:
        states, steps = trace['states'], trace['steps']
    if states.shape != (row['steps'], 7) or not np.isfinite(states).all() or not np.array_equal(steps, np.arange(len(states))):
        raise ValueError('Austin replay requires complete dense trace')
    geometry = Geometry('Austin')
    clearance = np.array([geometry.clearance(p[:2], p[4], with_center=False) for p in states])
    result = {'first_comparison': previous,
              'confirmation_candidate': {key: row[key] for key in ('success', 'collision', 'timeout', 'seconds', 'progress')},
              'initial_clearance_m': float(clearance[0]), 'minimum_clearance_m': float(clearance.min()),
              'contact_frames': int((clearance <= 1e-10).sum()),
              'maximum_displacement_m': float(np.linalg.norm(states[:, :2] - states[0, :2], axis=1).max()),
              'trace_sha256': verifier.digest(trace_path)}
    verifier.write_json(folder / 'verified_austin_71303.json', result)
    print('Verified Austin 71303 replay.')


def summarize_criteria(folder, result):
    rows = result['models']
    candidate = rows['candidate']
    clean_time = result['common_clean']['mean_change_pct']
    standard_time = result['common_completed']['mean_change_pct']
    checks = {
        'zero_simulator_collisions': candidate['collision']['episodes'] == 0,
        'zero_raster_contact_in_completed_laps': candidate['success']['contact_or_overlap_episodes'] == 0,
        'at_least_as_many_completions_as_previous': candidate['success']['episodes'] >= rows['previous']['success']['episodes'],
        'at_least_as_many_clean_completions_as_previous': candidate['clean_laps'] >= rows['previous']['clean_laps'],
        'no_more_timeouts_than_previous': candidate['timeout']['episodes'] <= rows['previous']['timeout']['episodes'],
    }
    for label, ratios in [('standard', standard_time), ('clean', clean_time)]:
        for model in ('previous', 'ppo'):
            value = ratios[f'candidate_vs_{model}']
            checks[f'faster_than_{model}_on_common_{label}_triplets'] = value < 0 if value is not None else None
    verifier.write_json(folder / 'verified_criteria.json', checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', type=Path, default=FIRST_RUN / 'confirmation')
    parser.add_argument('--workers', type=int, default=2)
    replay = parser.add_mutually_exclusive_group()
    replay.add_argument('--historical', type=Path, nargs='+')
    replay.add_argument('--austin', type=Path)
    args = parser.parse_args()
    # Change only this driver's process-local cohort. The frozen verifier's
    # source, prior manifests, checkpoint files and reports remain intact.
    verifier.SEEDS = CONFIRMATION_SEEDS
    manifest, maps = verifier.freeze(args.dir)
    if args.historical:
        result = verifier.historical(args.dir, manifest, args.historical)
        print(f'Verified {len(result["rows"])} historical starts.')
    elif args.austin:
        check_austin(args.dir, manifest, args.austin)
    else:
        result = verifier.holdout(args.dir, manifest, maps, args.workers)
        summarize_criteria(args.dir, result)
        print(f'Verified {len(result["rows"])} confirmation traces.')


if __name__ == '__main__':
    main()
