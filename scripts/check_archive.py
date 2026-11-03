"""Check archived files and recompute the paired comparisons without dependencies."""
import hashlib
import json
import math
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results'


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def episodes(path):
    payload = read(path)
    rows = {(r['map'], r['seed']): r for r in payload['rows']}
    check(len(rows) == len(payload['rows']), f'Duplicate record in {path}')
    for row in rows.values():
        check(sum(row[k] for k in ('success', 'timeout', 'collision')) == 1, 'Ambiguous episode outcome')
    return rows


def main():
    index = read(ROOT / 'artifacts/checkpoints.json')
    rewritten = read(ROOT / 'artifacts/public_file_hashes.json')
    for name, item in rewritten.items():
        check(digest(ROOT / name) == item['public_sha256'], f'Public file changed: {name}')
    for name, item in index.items():
        path = ROOT / name
        if 'public_sha256' in item or path.is_file():
            check(digest(path) == item.get('public_sha256', item['historical_sha256']), f'Checkpoint changed: {name}')
    for manifest in RESULTS.rglob('holdout_manifest.json'):
        frozen = read(manifest)
        for name, sha in frozen.get('source_sha256', {}).items():
            check(digest(ROOT / name) == sha, f'Frozen source changed: {name}')
        for item in frozen['checkpoints'].values():
            check(index[item['path']]['historical_sha256'] == item['sha256'], f'Freeze mismatch: {manifest}')

    pairs = [
        ('', 'holdout_baseline', 'holdout_edited', 'holdout_comparison'),
        ('', 'final_baseline', 'final_cautious', 'final_comparison'),
        ('racing_v2', 'final_baseline', 'final_curvature', 'comparison_curvature'),
        ('ultra', 'final_original', 'final_fast', 'comparison_fast'),
        ('trajectory_v4', 'final_previous', 'final_candidate', 'final_comparison'),
        ('from_scratch', 'final_previous', 'final_candidate', 'final_comparison'),
    ]
    for folder, baseline, candidate, summary in pairs:
        source = RESULTS / folder
        first, second = [episodes(source / f'{name}.json') for name in (baseline, candidate)]
        expected = read(source / f'{summary}.json')
        check(first.keys() == second.keys(), 'Unpaired data')
        shared = [k for k in first if first[k]['success'] and second[k]['success']]
        changes = [(second[k]['seconds'] / first[k]['seconds'] - 1) * 100 for k in shared]
        check(all(first[k]['start'] == second[k]['start'] for k in first), 'Mismatched initial poses')
        check(len(shared) == expected['paired_success'] and math.isclose(fmean(changes), expected['mean_paired_lap_change_pct'], abs_tol=1e-10), 'Paired times differ')
        for label, rows in [('baseline', first), ('edited', second)]:
            for metric, field in [('success', 'success'), ('collisions', 'collision'), ('timeouts', 'timeout')]:
                check(sum(r[field] for r in rows.values()) == expected[f'{label}_{metric}'], 'Outcome counts differ')
        print(f'{folder or "clearance"}/{candidate}: {expected["edited_success"]}/{len(first)} completed, {len(shared)} pairs, time {fmean(changes):+.4f}%')

    for subdir in ('', 'confirmation', 'locked'):
        folder = RESULTS / 'arc_recovery' / subdir
        models = ('candidate', 'previous', 'ppo')
        report = read(folder / ('verified_four_way.json' if subdir == 'locked' else 'verified_three_way.json'))
        frozen = read(folder / 'holdout_manifest.json')
        check(report['freeze_sha256'] == digest(folder / 'holdout_manifest.json'), 'Recovery freeze changed')
        ledgers = {}
        for model, sha in report['evaluation_json_sha256'].items():
            path = folder / f'final_{model}.json'
            stored = rewritten.get(str(path.relative_to(ROOT)), {})
            check(stored.get('historical_sha256', digest(path)) == sha, 'Recovery ledger digest differs')
            check(read(path)['sha256'] == frozen['checkpoints'][model]['sha256'], 'Wrong historical controller')
            ledgers[model] = episodes(path)
            check(set(ledgers[model]) == {(m,s) for m in frozen['maps'] for s in frozen['seeds']}, 'Recovery grid differs')
        for model in ledgers:
            rows = [r for r in report['rows'] if r['model'] == model]
            check(len(rows) == len(ledgers[model]), 'Geometry coverage differs')
            for r in rows:
                e = ledgers[model][r['map'],r['seed']]
                check(r['saved_frames'] == e['steps'] and r['success'] == e['success'], 'Geometry is unpaired')
            check(sum(r['success'] and not r['contact_or_overlap_episode'] for r in rows) == report['models'][model]['clean_laps'], 'Clean lap count differs')
        shared = [k for k in ledgers['ppo'] if all(ledgers[m][k]['success'] for m in models)]
        times = report['candidate_three_completed' if subdir == 'locked' else 'common_completed']
        check(times['count'] == len(shared), 'Recovery triplet count differs')
        for reference in ('previous', 'ppo'):
            delta = fmean((ledgers['candidate'][k]['seconds'] / ledgers[reference][k]['seconds'] - 1) * 100 for k in shared)
            check(math.isclose(delta, times['mean_change_pct'][f'candidate_vs_{reference}'], abs_tol=1e-10), 'Recovery lap times differ')
        print(f'recovery/{subdir or "first"}: {report["models"]["candidate"]["clean_laps"]} clean, {len(shared)} common completed triplets')


if __name__ == '__main__':
    main()
