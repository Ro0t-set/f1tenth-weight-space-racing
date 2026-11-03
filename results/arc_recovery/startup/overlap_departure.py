"""Static upper-bound manoeuvre audit from already overlapping starts."""
import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path('experiments').resolve()));from trajectory_audit import Geometry,ROOT
folder=ROOT/'results/arc_recovery/startup';cases=json.loads((folder/'initial_geometry.json').read_text());ks=json.loads((ROOT/'artifacts/from_scratch/arc_dynamic.json').read_text())['curvature'];out=[]
for row in cases:
 if row['body_clearance']>0:continue
 n,seed=row['map'],row['seed'];g=Geometry(n);p0=np.load(folder/f'initial_{n}_{seed}.npz')['state'];ss=np.arange(0,1.0001,.002);cand=[];points=g.occupied_centers[g.tree.query_ball_point(p0[:2],1.5)]
 for k in ks:
  depth=[]
  for s in ss:
   yaw=p0[4]+k*s;pos=p0[:2]+(np.array([np.sin(yaw)-np.sin(p0[4]),np.cos(p0[4])-np.cos(yaw)])/k if k else s*np.array([np.cos(yaw),np.sin(yaw)]));c,z=np.cos(yaw),np.sin(yaw);R=np.array([[c,-z],[z,c]]);rel=points-pos;local=rel@R;half=np.array([.29,.155]);p_half=g.res/2
   separation=np.c_[np.abs(rel)-(np.abs(R)@half+p_half),np.abs(local)-(half+p_half*(abs(c)+abs(z)))].max(axis=1);depth.append(float(max(0,-separation.min())))
  d=np.array(depth);clear=np.flatnonzero(d<=1e-12);idx=int(clear[0]) if len(clear) else None
  cand.append(dict(k=k,initial_depth_m=d[0],initial_depth_change_at_2mm_m=d[1]-d[0],maximum_depth_m=float(d.max()),first_disjoint_s_m=float(ss[idx]) if idx is not None else None,decreases_monotonically_until_clear=bool(idx is not None and np.all(np.diff(d[:idx+1])<=1e-10)),remains_disjoint_to_1m=bool(idx is not None and np.all(d[idx:]<=1e-12))))
 acceptable=[r for r in cand if r['decreases_monotonically_until_clear'] and r['remains_disjoint_to_1m']];out.append(dict(map=n,seed=seed,uniform_forward_arcs=cand,monotonic_escape_candidates=acceptable));print(n,seed,'initial_depth',cand[0]['initial_depth_m'],'escape',[(r['k'],r['first_disjoint_s_m']) for r in acceptable])
(folder/'overlap_departure.json').write_text(json.dumps(dict(method='Sampled kinematic front-motion arcs at 2mm arclength. Penetration proxy is maximum per-pixel SAT minimum translation distance. Ideal constant curvature available from first millimetre, without actuator delay; diagnostic only.',rows=out),indent=2)+'\n')
