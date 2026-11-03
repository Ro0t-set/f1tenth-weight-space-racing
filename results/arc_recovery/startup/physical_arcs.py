"""Compare nominal departure sweeps with the occupancy raster and sampled LiDAR."""
import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path('experiments').resolve()));from evaluate import ROOT
from trajectory_audit import Geometry
from from_scratch import radial_envelope
folder=ROOT/'results/arc_recovery/startup';adata=json.loads((folder/'initial_geometry.json').read_text());ang=np.linspace(-2.35,2.35,1080)
ks=np.array(json.loads((ROOT/'artifacts/from_scratch/arc_dynamic.json').read_text())['curvature']);ss=np.linspace(0,.5,51);out=[]
for a in adata:
 n,seed=a['map'],a['seed'];q=np.load(folder/f'initial_{n}_{seed}.npz');d=(15*q['obs']+15).reshape(180,6).min(-1);state=q['state'];geo=Geometry(n);states=[]
 for k in ks:
  heading=ss*k; xx=np.sin(heading)/k if k else ss; yy=(1-np.cos(heading))/k if k else np.zeros_like(ss);yaw=state[4];xy=state[:2]+np.c_[xx*np.cos(yaw)-yy*np.sin(yaw),xx*np.sin(yaw)+yy*np.cos(yaw)];ds=np.array([geo.clearance(z,r+yaw,with_center=False) for z,r in zip(xy,heading)])
  required=radial_envelope(k,.5,ang,margin=0,beta=0.);states.append(dict(k=float(k),swept_true_min_m=float(ds.min()),true_clearance_at_0p5_m=float(ds[-1]),min_LiDAR_clearance_nominal_sweep=float((d-required).min())))
 best=max(states,key=lambda r:(r['swept_true_min_m']>1e-8,r['true_clearance_at_0p5_m']));out.append(dict(map=n,seed=seed,sweeps=states));print(n,seed,'init',a['body_clearance'],'rasterbest',best,'LIDARsafecurvatures',[r['k'] for r in states if r['min_LiDAR_clearance_nominal_sweep']>0])
(folder/'initial_physical_arcs.json').write_text(json.dumps(out,indent=2)+'\n')
