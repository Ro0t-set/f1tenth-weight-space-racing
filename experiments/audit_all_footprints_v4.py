"""Secondary predeclared audit of ALL final dense traces, with no exclusions.

Uses exact rectangle-to-occupied-pixel-square geometry, independent of policy
inference and LiDAR/TTC. A zero separation means contact/overlap, not depth.
"""
import argparse
import csv
import hashlib
import json
from multiprocessing import get_context
from pathlib import Path
from time import perf_counter

import numpy as np
from trajectory_audit import Geometry, ROOT

MODELS = ('previous', 'candidate')
SEEDS = [50101, 50202, 50303, 50404, 50505, 50606, 50707, 50808, 50909, 51010]


def process_map(task):
    folder, name, inputs = task
    geometry = Geometry(name)
    results = []
    starts = {}
    for model, row in inputs:
        path = Path(folder)/f'final_{model}_{name}_{row["seed"]}_trace.npz'
        with np.load(path) as data:
            states, steps = data['states'], data['steps']
        if states.ndim!=2 or states.shape!=(row['steps'],7) or not np.isfinite(states).all():
            raise ValueError(f'{path}: invalid dense state shape/content')
        if not np.array_equal(steps,np.arange(len(states))):
            raise ValueError(f'{path}: trace does not contain every pre-action physics step')
        seed=row['seed']
        if seed in starts and not np.array_equal(starts[seed], states[0]):
            raise ValueError(f'{path}: policies do not have identical starting states')
        starts[seed]=states[0]
        clearance=np.fromiter((geometry.clearance(p[:2],p[4],with_center=False) for p in states),dtype=float,count=len(states))
        overlap=clearance<=1e-10
        worst=int(np.argmin(clearance))
        results.append(dict(model=model,map=name,seed=seed,success=row['success'],collision=row['collision'],
            episode_seconds=row['seconds'],progress=row['progress'],saved_frames=len(states),
            minimum_body_clearance_m=float(clearance[worst]),minimum_time_s=float(steps[worst]*.01),
            initial_body_clearance_m=float(clearance[0]),final_saved_body_clearance_m=float(clearance[-1]),
            contact_or_overlap_frames=int(overlap.sum()),contact_or_overlap_episode=bool(overlap.any()),
            frames_below_10cm=int((clearance<.1).sum()),frames_below_20cm=int((clearance<.2).sum()),
            clearance_p05_m=float(np.quantile(clearance,.05)),map_resolution_m=geometry.res,
            trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return results


def metrics(rows):
    frames=sum(r['saved_frames'] for r in rows)
    return dict(episodes=len(rows),completed=sum(r['success'] for r in rows),collisions=sum(r['collision'] for r in rows),
        saved_frames=frames,minimum_body_clearance_m=min((r['minimum_body_clearance_m'] for r in rows),default=None),
        contact_or_overlap_episodes=sum(r['contact_or_overlap_episode'] for r in rows),
        contact_or_overlap_frames=sum(r['contact_or_overlap_frames'] for r in rows),
        frame_fraction_below_10cm=sum(r['frames_below_10cm'] for r in rows)/frames if frames else None,
        frame_fraction_below_20cm=sum(r['frames_below_20cm'] for r in rows)/frames if frames else None,
        mean_episode_clearance_p05_m=float(np.mean([r['clearance_p05_m'] for r in rows])) if rows else None,
        contact_or_overlap_cases=[dict(map=r['map'],seed=r['seed'],success=r['success'],frames=r['contact_or_overlap_frames'],initial_clearance_m=r['initial_body_clearance_m']) for r in rows if r['contact_or_overlap_episode']])


def summarize(rows):
    success={m:{(r['map'],r['seed']) for r in rows if r['model']==m and r['success']} for m in MODELS}
    paired=success['previous']&success['candidate']
    result={'jointly_completed_pair_count':len(paired)}
    for model in MODELS:
        selected=[r for r in rows if r['model']==model]
        result[model]=dict(all=metrics(selected),completed=metrics([r for r in selected if r['success']]),
                          failed=metrics([r for r in selected if not r['success']]),
                          jointly_completed=metrics([r for r in selected if (r['map'],r['seed']) in paired]))
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dir',type=Path,default=ROOT/'results/trajectory_v4')
    ap.add_argument('--workers',type=int,default=2)
    ap.add_argument('--seeds',nargs='+',type=int,default=SEEDS,help='Frozen cohort seed list; defaults to the original ten seeds')
    args=ap.parse_args(); folder=args.dir
    if len(set(args.seeds))!=len(args.seeds): ap.error('--seeds must not contain duplicates')
    payload={m:json.loads((folder/f'final_{m}.json').read_text()) for m in MODELS}
    lookup={m:{(r['map'],r['seed']):r for r in payload[m]['rows']} for m in MODELS}
    for m in MODELS:
        if len(lookup[m])!=len(payload[m]['rows']): raise ValueError(f'{m}: duplicate episodes')
    if lookup['previous'].keys()!=lookup['candidate'].keys(): raise ValueError('Evaluation keys differ')
    maps=sorted({name for name,seed in lookup['previous']})
    expected={(name,seed) for name in maps for seed in args.seeds}
    if len(maps)!=21 or set(lookup['previous'])!=expected: raise ValueError(f'Expected frozen 21 tracks x {len(args.seeds)} seeds, no exclusions')
    tasks=[(str(folder),name,[(m,lookup[m][(name,s)]) for m in MODELS for s in args.seeds]) for name in maps]
    # Assert every trace exists before beginning; no partial aggregate is published.
    for _,name,inputs in tasks:
        for m,row in inputs:
            if not (folder/f'final_{m}_{name}_{row["seed"]}_trace.npz').is_file(): raise FileNotFoundError(f'Missing {m} {name} {row["seed"]}')
    start=perf_counter(); rows=[]
    with get_context('spawn').Pool(args.workers) as pool:
        for completed in pool.imap_unordered(process_map,tasks):
            rows.extend(completed)
            print(json.dumps({'map_complete':completed[0]['map'],'episodes':len(rows),'elapsed_s':round(perf_counter()-start,2)}),flush=True)
    rows.sort(key=lambda r:(r['model'],r['map'],r['seed']))
    output=dict(protocol=f'Secondary audit predeclared before final outcomes: all 21 tracks x all {len(args.seeds)} frozen seeds x both models; no exclusions',
        checkpoint_sha256={m:payload[m]['sha256'] for m in MODELS},
        evaluation_json_sha256={m:hashlib.sha256((folder/f'final_{m}.json').read_bytes()).hexdigest() for m in MODELS},
        elapsed_s=perf_counter()-start,summary=summarize(rows),rows=rows,
        caveats=['Exact separation from occupied pixel squares at recorded poses only; zero means contact/overlap, not penetration depth.',
                 'All 0.01s pre-action states included; the final post-step pose and between-step motion are not recorded.',
                 'Contact geometry is independent of upstream LiDAR/TTC collision labels, which ignore slip beta in velocity projection.',
                 'Raster map resolution limits interpretation as physical wall clearance.',
                 'Frame fractions weight longer episodes more; all, completed, failed and jointly completed subsets are reported separately.'])
    (folder/'final_all_footprints.json').write_text(json.dumps(output,indent=2)+'\n')
    with (folder/'final_all_footprints.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(output['summary'],indent=2),flush=True)


if __name__=='__main__': main()
