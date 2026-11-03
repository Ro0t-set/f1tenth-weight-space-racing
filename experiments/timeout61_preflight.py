"""Validate exact seeded initial poses before running a paired benchmark.

Exit code 2 rejects the whole batch if any body intersects occupied pixels.
No episode is replaced or silently removed. This does not change policy inputs.
"""
import argparse,contextlib,io,json
from pathlib import Path
import numpy as np
from evaluate import F110Env,F110_Wrapped,Integrator,MAPS
from trajectory_audit import Geometry

def check(maps,seeds):
    rows=[]
    for name in maps:
        folder=MAPS/name
        raw=F110Env(map=str(folder/f'{name}_map'),map_ext='.png',num_agents=1,timestep=.01,integrator=Integrator.RK4)
        env=F110_Wrapped(raw,random_map=False)
        env.set_map_path(str(folder));env.set_optimize_speed(False)
        geometry=Geometry(name)
        for seed in seeds:
            env.set_raceliens();env.count=0;env.one_lap_done=False;env.number_of_base_reward_give=10
            np.random.seed(seed)
            for car in raw.sim.agents:car.seed=seed
            with contextlib.redirect_stdout(io.StringIO()):env.reset()
            pose=raw.sim.agents[0].state.copy()
            margin=geometry.clearance(pose[:2],pose[4],with_center=False)
            rows.append(dict(map=name,seed=seed,pose=[float(pose[i]) for i in (0,1,4)],
                             body_clearance_m=float(margin),invalid_start=bool(margin<=1e-10)))
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--maps',nargs='+',default=['all'])
    p.add_argument('--seeds',nargs='+',type=int,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    maps=sorted(f.name for f in MAPS.iterdir() if (f/f'{f.name}_raceline.csv').exists()) if a.maps==['all'] else a.maps
    rows=check(maps,a.seeds);invalid=sum(r['invalid_start'] for r in rows)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(dict(rows=rows,invalid_starts=invalid,replaced_starts=0,
        accepted_for_evaluation=invalid==0),indent=2)+'\n')
    print(f'{len(rows)} starts checked, {invalid} invalid, 0 replaced')
    raise SystemExit(2 if invalid else 0)
