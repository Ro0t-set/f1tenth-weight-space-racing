"""Verify the frozen three-controller experiment and its separate historical replay."""
import argparse
import csv
import hashlib
import json
from multiprocessing import get_context
from pathlib import Path

import numpy as np

from audit_all_footprints_v4 import metrics, process_map
from trajectory_audit import Geometry, MAPS, ROOT


MODELS = ('previous', 'candidate', 'ppo')
SEEDS = [71101, 71202, 71303, 71404, 71505]
HISTORICAL = {('Austin', 60404), ('IMS', 60404), ('IMS', 60505), ('Monza', 60404),
              ('Oschersleben', 60404), ('Oschersleben', 60505), ('YasMarina', 60404)}
INITIAL_OVERLAPS = {('IMS', 60505), ('Oschersleben', 60404), ('Oschersleben', 60505)}


def read_json(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def freeze(folder):
    manifest = read_json(folder / 'holdout_manifest.json')
    maps = sorted(p.name for p in MAPS.iterdir() if (p / f'{p.name}_raceline.csv').is_file())
    if len(maps) != 21 or sorted(manifest['maps']) != maps or manifest['seeds'] != SEEDS:
        raise ValueError('Freeze does not match the predeclared 21 maps and five seeds')
    for model in MODELS:
        item = manifest['checkpoints'][model]
        if digest(ROOT / item['path']) != item['sha256']:
            raise ValueError(f'{model}: frozen checkpoint differs from file')
    for name, checksum in manifest['source_sha256'].items():
        if digest(ROOT / name) != checksum:
            raise ValueError(f'{name}: source differs from freeze')
    return manifest, maps


def frozen_results(folder, manifest, maps):
    expected = {(name, seed) for name in maps for seed in SEEDS}
    lookup = {}
    protocols = set()
    for model in MODELS:
        payload = read_json(folder / f'final_{model}.json')
        if payload['sha256'] != manifest['checkpoints'][model]['sha256'] or payload['max_steps'] != 20000:
            raise ValueError(f'{model}: checkpoint or step limit mismatch')
        protocols.add(payload['protocol'])
        rows = {(r['map'], r['seed']): r for r in payload['rows']}
        if len(rows) != len(payload['rows']) or set(rows) != expected:
            raise ValueError(f'{model}: missing, duplicate, or unexpected map/seed')
        for row in rows.values():
            if sum(row[k] for k in ('success', 'collision', 'timeout')) != 1:
                raise ValueError(f'{model}: ambiguous episode outcome')
        lookup[model] = rows
    if len(protocols) != 1:
        raise ValueError('Evaluation protocols differ')
    for key in expected:
        starts = {tuple(lookup[m][key]['start']) for m in MODELS}
        if len(starts) != 1:
            raise ValueError(f'{key}: starting pose differs')
    return lookup


def key_list(keys):
    return [{'map': name, 'seed': seed} for name, seed in sorted(keys)]


def times(lookup, keys):
    ordered = sorted(keys)
    report = {'count': len(keys), 'cases': key_list(keys), 'mean_seconds': {}, 'mean_change_pct': {}}
    for model in MODELS:
        values = [lookup[model][key]['seconds'] for key in ordered]
        report['mean_seconds'][model] = float(np.mean(values)) if values else None
    for model, reference in [('candidate', 'previous'), ('candidate', 'ppo'), ('previous', 'ppo')]:
        changes = [100 * (lookup[model][key]['seconds'] / lookup[reference][key]['seconds'] - 1) for key in ordered]
        report['mean_change_pct'][f'{model}_vs_{reference}'] = float(np.mean(changes)) if changes else None
    return report


def holdout(folder, manifest, maps, workers):
    lookup = frozen_results(folder, manifest, maps)
    tasks = [(str(folder), name, [(m, lookup[m][name, s]) for m in MODELS for s in SEEDS]) for name in maps]
    rows = []
    with get_context('spawn').Pool(workers) as pool:
        for map_rows in pool.imap_unordered(process_map, tasks):
            rows.extend(map_rows)
    rows.sort(key=lambda r: (r['model'], r['map'], r['seed']))
    success, clean, counts = {}, {}, {}
    for model in MODELS:
        selected = [r for r in rows if r['model'] == model]
        for r in selected:
            r['timeout'] = lookup[model][r['map'], r['seed']]['timeout']
            r['clean'] = r['success'] and not r['contact_or_overlap_episode']
        success[model] = {(r['map'], r['seed']) for r in selected if r['success']}
        clean[model] = {(r['map'], r['seed']) for r in selected if r['clean']}
        counts[model] = {'clean_laps': len(clean[model]), 'all': metrics(selected)}
        for field in ('success', 'collision', 'timeout'):
            counts[model][field] = metrics([r for r in selected if r[field]])
    changes = {}
    for reference in ('previous', 'ppo'):
        changes[reference] = {}
        for label, group in [('success', success), ('clean', clean)]:
            changes[reference][label] = {
                'gained': key_list(group['candidate'] - group[reference]),
                'lost': key_list(group[reference] - group['candidate'])}
    result = {
        'freeze_sha256': digest(folder / 'holdout_manifest.json'),
        'evaluation_json_sha256': {m: digest(folder / f'final_{m}.json') for m in MODELS},
        'models': counts, 'changes_candidate_vs_reference': changes,
        'common_completed': times(lookup, set.intersection(*success.values())),
        'common_clean': times(lookup, set.intersection(*clean.values())),
        'clean_definition': 'Official completion with positive rectangle-to-wall separation in every saved pre-action pose.',
        'time_definition': 'Mean of per-start percent changes on the identical three-model cohort. Negative means faster.',
        'rows': rows}
    write_json(folder / 'verified_three_way.json', result)
    with (folder / 'verified_footprints.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return result


def historical(folder, manifest, paths):
    prior = ROOT / 'results/from_scratch'
    arc_previous = read_json(prior / 'final_candidate.json')
    ppo = read_json(prior / 'final_previous.json')
    for model, payload in [('previous', arc_previous), ('ppo', ppo)]:
        if payload['sha256'] != manifest['checkpoints'][model]['sha256']:
            raise ValueError(f'{model}: historical reference hash differs')
    earlier = {(r['map'], r['seed']): r for r in arc_previous['rows'] if r['timeout']}
    if set(earlier) != HISTORICAL:
        raise ValueError('Historical timeout cohort differs')
    old_geometry = read_json(prior / 'final_all_footprints.json')
    if old_geometry['evaluation_json_sha256']['candidate'] != digest(prior / 'final_candidate.json'):
        raise ValueError('Historical geometry does not match the original evaluation')
    geometry_refs = {(r['model'], r['map'], r['seed']): r for r in old_geometry['rows']}
    ppo_lookup = {(r['map'], r['seed']): r for r in ppo['rows']}
    records, maps = {}, {}
    for path in paths:
        payload = read_json(path)
        if payload['sha256'] != manifest['checkpoints']['candidate']['sha256'] or payload['max_steps'] != 20000:
            raise ValueError(f'{path}: historical candidate or step limit mismatch')
        for row in payload['rows']:
            key = (row['map'], row['seed'])
            if key not in HISTORICAL:
                continue
            if key in records or row['start'] != earlier[key]['start'] or row['start'] != ppo_lookup[key]['start']:
                raise ValueError(f'{key}: duplicate or unpaired historical start')
            name, seed = key
            if name not in maps:
                maps[name] = Geometry(name)
            trace_path = path.with_name(f'{path.stem}_{name}_{seed}_trace.npz')
            with np.load(trace_path) as trace:
                states, steps = trace['states'], trace['steps']
            if states.shape != (row['steps'], 7) or not np.isfinite(states).all() or not np.array_equal(steps, np.arange(len(states))):
                raise ValueError(f'{trace_path}: dense state trace required')
            clearance = np.array([maps[name].clearance(p[:2], p[4], with_center=False) for p in states])
            contact = clearance <= 1e-10
            if bool(contact[0]) != (key in INITIAL_OVERLAPS):
                raise ValueError(f'{key}: initial occupancy differs from historical cohort')
            clear_indices = np.flatnonzero(~contact)
            first_clear = int(clear_indices[0]) if len(clear_indices) else None
            records[key] = {
                'map': name, 'seed': seed, 'initial_overlap': bool(contact[0]),
                'candidate': {k: row[k] for k in ('success', 'collision', 'timeout', 'seconds', 'progress')},
                'previous': {k: earlier[key][k] for k in ('success', 'collision', 'timeout', 'seconds', 'progress')},
                'ppo': {k: ppo_lookup[key][k] for k in ('success', 'collision', 'timeout', 'seconds', 'progress')},
                'previous_contact_frames': geometry_refs['candidate', name, seed]['contact_or_overlap_frames'],
                'ppo_contact_frames': geometry_refs['previous', name, seed]['contact_or_overlap_frames'],
                'candidate_contact_frames': int(contact.sum()), 'first_clear_step': first_clear,
                'contact_frames_after_first_clear': int(contact[first_clear:].sum()) if first_clear is not None else None,
                'clean_completion': bool(row['success'] and not contact.any()),
                'trace_sha256': digest(trace_path)}
    if set(records) != HISTORICAL:
        raise ValueError('Missing historical replay records')
    result = {'cohort': 'Seven previously observed timeouts, separate from the new-seed evaluation.',
              'rows': [records[key] for key in sorted(records)]}
    write_json(folder / 'verified_historical_timeouts.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', type=Path, default=ROOT / 'results/arc_recovery')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--historical', type=Path, nargs='+', help='Verify only historical candidate replay JSON(s) with matching dense NPZ files')
    args = parser.parse_args()
    manifest, maps = freeze(args.dir)
    if args.historical:
        report = historical(args.dir, manifest, args.historical)
        print(f'Verified {len(report["rows"])} historical starts.')
    else:
        report = holdout(args.dir, manifest, maps, args.workers)
        print(f'Verified {len(report["rows"])} final dense traces.')


if __name__ == '__main__':
    main()
