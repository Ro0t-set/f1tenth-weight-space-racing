"""Fixed-cohort geometry audit: seed 50101 on every track, including failures.

Run only after final_previous.json and final_candidate.json are complete.
No candidate selection, rollout, checkpoint changes or outcome-dependent plots.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
from trajectory_audit import Geometry, HALF, SIGNS, ROOT, audit

SEED = 50101
EXAMPLES = ('Budapest', 'Monza', 'Spa')


def aggregate(records):
    totals = {}
    for model in ('previous', 'candidate'):
        rows = [r[model] for r in records]
        frames = sum(r['saved_frames'] for r in rows)
        totals[model] = dict(episodes=len(rows), completed=sum(r['success'] for r in rows),
                            collisions=sum(r['collision'] for r in rows), saved_frames=frames,
                            global_body_clearance_min_m=min(r['body_clearance_min_m'] for r in rows),
                            mean_episode_body_clearance_p05_m=float(np.mean([r['body_clearance_p05_m'] for r in rows])),
                            occupied_or_outside_body_frames=sum(r['occupied_or_outside_body_frames'] for r in rows),
                            frame_fraction_below_10cm=sum(r['body_frames_below_10cm'] for r in rows)/frames,
                            frame_fraction_below_20cm=sum(r['body_frames_below_20cm'] for r in rows)/frames)
    paired = [r for r in records if r['previous']['success'] and r['candidate']['success']]
    def change(r, key):
        return 100*(r['candidate'][key]/r['previous'][key]-1)
    totals['paired_completed'] = dict(count=len(paired), maps=[r['map'] for r in paired],
        mean_path_length_change_pct=float(np.mean([change(r,'sampled_path_length_m') for r in paired])) if paired else None,
        mean_episode_time_change_pct=float(np.mean([change(r,'episode_seconds') for r in paired])) if paired else None,
        mean_body_clearance_p05_change_m=float(np.mean([r['candidate']['body_clearance_p05_m']-r['previous']['body_clearance_p05_m'] for r in paired])) if paired else None,
        mean_raceline_cross_track_p95_change_m=float(np.mean([r['candidate']['raceline_cross_track_abs_p95_m']-r['previous']['raceline_cross_track_abs_p95_m'] for r in paired])) if paired else None)
    return totals


def figure(examples, out):
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    fig, axes = plt.subplots(2,3,figsize=(14,9))
    colors = {'previous':'#2777b7','candidate':'#dc601a'}
    labels = {'previous':'Veloce precedente','candidate':'Nuovo candidato'}
    for col, name in enumerate(EXAMPLES):
        if name not in examples:
            for ax in axes[:,col]: ax.text(.5,.5,f'{name}: dati assenti',ha='center'); ax.set_axis_off()
            continue
        g, rows, arrays = examples[name]
        # Location depends only on the map's supplied curvature, never outcomes.
        racefile=ROOT/f'upstream/map/f1tenth_racetracks/{name}/{name}_raceline.csv'
        curvature=np.loadtxt(racefile,delimiter=';',skiprows=3)[:,4]
        focus=g.race[int(np.argmax(np.abs(curvature)))]; radius=4.
        for ax in axes[:,col]:
            ax.imshow(g.free,cmap='gray',vmin=0,vmax=1,origin='lower',extent=[g.origin[0],g.upper[0],g.origin[1],g.upper[1]])
            closed=np.vstack([g.race,g.race[0]])
            ax.plot(*closed.T,'--',color='#888888',lw=.8,label='Raceline di riferimento')
            ax.set_aspect('equal'); ax.set_xlabel('x [m]'); ax.set_ylabel('y [m]')
        caption=[]
        for model in ('previous','candidate'):
            states=arrays[model]['states']; xy=states[:,:2]; color=colors[model]
            for ax in axes[:,col]: ax.plot(*xy.T,color=color,lw=1.1,label=labels[model],alpha=.9)
            # Sparse footprints in the fixed zoom only; coordinates are recorded states.
            near=np.flatnonzero(np.max(np.abs(xy-focus),axis=1)<radius)
            for j in near[::max(1,len(near)//5)][:6]:
                p=states[j]; c,s=np.cos(p[4]),np.sin(p[4]); rot=np.array([[c,-s],[s,c]])
                axes[1,col].add_patch(Polygon(SIGNS*HALF@rot.T+p[:2],fill=False,edgecolor=color,lw=.8,alpha=.8))
            status='completato' if rows[model]['success'] else 'collisione' if rows[model]['collision'] else 'non completato'
            caption.append(f'{labels[model]}: {status}')
        axes[0,col].set_title(name+' · seed 50101\n'+'\n'.join(caption),fontsize=10)
        axes[1,col].set_xlim(focus[0]-radius,focus[0]+radius); axes[1,col].set_ylim(focus[1]-radius,focus[1]+radius)
        axes[1,col].set_title('Curva con massimo |κ| nella raceline',fontsize=10)
    axes[0,0].legend(fontsize=8,loc='best')
    fig.suptitle('Traiettorie e margine del corpo · esempi fissati prima dei risultati\nRaceline di riferimento; nessuna ottimalità assoluta dimostrata',fontsize=13)
    fig.tight_layout(); fig.savefig(out/'final_fixed_trajectory_examples.png',dpi=180); fig.savefig(out/'final_fixed_trajectory_examples.svg'); plt.close(fig)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dir',type=Path,default=ROOT/'results/trajectory_v4')
    args=ap.parse_args(); folder=args.dir
    payload={m:json.loads((folder/f'final_{m}.json').read_text()) for m in ('previous','candidate')}
    lookup={m:{(r['map'],r['seed']):r for r in p['rows']} for m,p in payload.items()}
    if any(len(lookup[m])!=len(payload[m]['rows']) for m in payload): raise ValueError('Duplicate map/seed rows')
    if lookup['previous'].keys()!=lookup['candidate'].keys(): raise ValueError('Unpaired evaluation keys')
    maps=sorted({name for name,seed in lookup['previous']})
    if any((name,SEED) not in lookup['previous'] for name in maps): raise ValueError('Fixed seed missing; no replacements allowed')
    out=folder/'geometry_seed50101'; out.mkdir(parents=True,exist_ok=True)
    records=[]; examples={}
    for name in maps:
        geometry=Geometry(name); record={'map':name,'seed':SEED}; arrays={}
        for model in ('previous','candidate'):
            row=lookup[model][(name,SEED)]
            trace=folder/f'final_{model}_{name}_{SEED}_trace.npz'
            summary,arrays[model]=audit(trace,geometry,.01)
            if summary['frame_interval_max_s'] not in (None,.01): raise ValueError(f'{trace}: requires every-step state trace')
            if summary['saved_frames']!=row['steps']: raise ValueError(f'{trace}: frame count differs from episode steps')
            summary.update(success=row['success'],collision=row['collision'],progress=row['progress'],episode_seconds=row['seconds'])
            record[model]=summary
            (out/f'{model}_{name}_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
            np.savez_compressed(out/f'{model}_{name}_geometry.npz',**arrays[model])
        if not np.allclose(arrays['previous']['states'][0],arrays['candidate']['states'][0],rtol=0,atol=1e-12): raise ValueError(f'{name}: unpaired starting states')
        records.append(record)
        if name in EXAMPLES: examples[name]=(geometry,record,arrays)
    result=dict(cohort='All tracks, seed50101, both frozen policies, all failures retained; no replacement seeds',
                examples=list(EXAMPLES),summary=aggregate(records),rows=records,
                caveats=['Path/time changes use jointly completed episodes only; denominator and tracks are reported.',
                         'All-cohort clearance fractions mix episode durations; crashes are not treated as short successful paths.',
                         'All states are pre-action; final post-step pose is absent even with 0.01s recording.',
                         'Geometry uses occupied map pixel squares, not LiDAR/TTC labels or continuous real walls.',
                         'Nearer raceline, shorter path, or smaller wall margin is not by itself proof of faster/safe/optimal driving.'])
    (folder/'final_geometry_seed50101.json').write_text(json.dumps(result,indent=2)+'\n')
    figure(examples,folder)
    print(json.dumps(result['summary'],indent=2))


if __name__=='__main__': main()
