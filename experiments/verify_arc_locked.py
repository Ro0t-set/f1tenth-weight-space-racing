"""Final comparison with a preselected launch candidate and a speed-only control."""
import argparse
from pathlib import Path
import numpy as np

import verify_arc_recovery as verifier
from trajectory_audit import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--historical', type=Path)
    args = parser.parse_args()
    folder = ROOT / 'results/arc_recovery/locked'
    verifier.MODELS = ('previous', 'candidate', 'ppo', 'speed')
    verifier.SEEDS = [73101, 73202, 73303, 73404, 73505]
    manifest, maps = verifier.freeze(folder)
    if args.historical:
        verifier.historical(folder, manifest, [args.historical])
        return
    result = verifier.holdout(folder, manifest, maps, workers=2)
    (folder / 'verified_three_way.json').replace(folder / 'verified_four_way.json')
    lookup = verifier.frozen_results(folder, manifest, maps)
    for model in ('candidate', 'speed'):
        clean = {(r['model'],r['map'],r['seed']) for r in result['rows'] if r['clean']}
        for clean_only in (False, True):
            models = ('previous', 'ppo', model)
            keys = sorted(k for k in lookup[model] if all(
                lookup[m][k]['success'] and (not clean_only or (m,*k) in clean) for m in models))
            ratios = {f'{a}_vs_{b}': float(np.mean([100*(lookup[a][k]['seconds']/lookup[b][k]['seconds']-1)
                                                       for k in keys])) for a,b in [(model,'previous'),(model,'ppo'),('previous','ppo')]}
            label = 'clean' if clean_only else 'completed'
            result[f'{model}_three_{label}'] = dict(count=len(keys), mean_change_pct=ratios, cases=verifier.key_list(keys))
    verifier.write_json(folder / 'verified_four_way.json', result)
    print('Verified', len(result['rows']), 'dense traces')


if __name__ == '__main__':
    main()
