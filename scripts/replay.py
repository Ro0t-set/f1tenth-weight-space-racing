"""Replay the recorded controller, circuit, seed and horizon of an episode ledger."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger', type=Path)
    parser.add_argument('--maps', nargs='+', help='Optional subset of recorded circuits')
    parser.add_argument('--seeds', nargs='+', type=int, help='Optional subset of recorded seeds')
    parser.add_argument('--footprints', action='store_true', help='Record every pre-action pose and audit the full body')
    args = parser.parse_args()
    ledger = args.ledger.resolve()
    relative = ledger.relative_to(ROOT / 'results')
    reference = read(ledger)
    index = read(ROOT / 'artifacts/checkpoints.json')
    name = reference['checkpoint']
    checkpoint = ROOT / name
    if not checkpoint.is_file():
        parser.error(f'Missing {name}. Run setup.sh and scripts/build_ppo.sh all for the PPO derivatives.')
    digest = sha256(checkpoint.read_bytes()).hexdigest()
    entry = index[name]
    if reference['sha256'] != entry['historical_sha256'] or digest != entry.get('public_sha256', entry['historical_sha256']):
        parser.error('Recorded or local checkpoint differs from the release catalog.')

    groups = defaultdict(dict)
    for row in reference['rows']:
        circuit, seed = row['map'], row['seed']
        if (not args.maps or circuit in args.maps) and (not args.seeds or seed in args.seeds):
            if seed in groups[circuit]:
                parser.error(f'Duplicate recorded start {circuit} {seed}')
            groups[circuit][seed] = row
    if not groups or set(args.maps or []) - groups.keys() or set(args.seeds or []) - {s for g in groups.values() for s in g}:
        parser.error('Requested map or seed absent from the selected records.')

    from datetime import datetime, timezone
    output = ROOT / 'reruns' / relative.with_suffix('') / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    output.mkdir(parents=True)
    geometry, episodes, differences = [], [], []
    if args.footprints:
        sys.path.insert(0, str(ROOT / 'experiments'))
        from audit_all_footprints_v4 import process_map
    for circuit, expected in groups.items():
        folder = output / circuit
        target = folder / 'final_replay.json'
        command = [sys.executable, str(ROOT / 'experiments/evaluate.py'), '--checkpoint', str(checkpoint),
                   '--maps', circuit, '--seeds', *map(str, expected), '--max-steps', str(reference['max_steps']),
                   '--out', str(target)]
        if args.footprints:
            command.append('--state-trace')
        subprocess.run(command, cwd=ROOT, check=True)
        rows = read(target)['rows']
        if {r['seed'] for r in rows} != expected.keys() or len(rows) != len(expected):
            raise ValueError(f'Missing replayed starts on {circuit}')
        for row in rows:
            original = expected[row['seed']]
            fields = [k for k in ('start', 'success', 'collision', 'timeout', 'steps', 'seconds') if row[k] != original[k]]
            if fields:
                differences.append(dict(circuit=circuit, seed=row['seed'], fields=fields))
        episodes.extend(rows)
        if args.footprints:
            geometry.extend(process_map((folder, circuit, [('replay', row) for row in rows])))
    summary = dict(ledger=relative.as_posix(), checkpoint=name, checkpoint_sha256=digest,
                   episodes=len(episodes), completions=sum(r['success'] for r in episodes),
                   collisions=sum(r['collision'] for r in episodes), timeouts=sum(r['timeout'] for r in episodes),
                   differences=differences)
    if args.footprints:
        summary['completed_without_sampled_body_contact'] = sum(r['success'] and not r['contact_or_overlap_episode'] for r in geometry)
        (output / 'geometry.json').write_text(json.dumps(geometry, indent=2) + '\n')
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), '\nOutput', output.relative_to(ROOT))
    if differences:
        raise SystemExit('Some outcomes or lap times differ from the archived run.')


if __name__ == '__main__':
    main()
