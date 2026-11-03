"""Run the one declared correction on development failures and known starts."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path('experiments').resolve()))
from arc_pose_guard import build
from evaluate import ROOT,evaluate,load_policy
from trajectory_audit import Geometry
folder=ROOT/'results/arc_recovery/guard3';path=build();policy=load_policy(path)
old=json.loads((ROOT/'results/from_scratch/final_candidate.json').read_text())['rows'];recent=json.loads((ROOT/'results/arc_recovery/final_candidate.json').read_text())['rows']
cases=[('Austin',71808),('Austin',71303)]+[(r['map'],r['seed']) for r in old if r['timeout']]+[(r['map'],r['seed']) for r in recent if r['timeout']]
rows=[]; geometry=[]
for n,s in cases:
 result,tr=evaluate(policy,[n],[s],state_trace=True);row=result[0];rows.append(row);states=np.stack([f['state'] for f in tr[0][2]])
 np.savez_compressed(folder/f'guard_{n}_{s}.npz',states=states,steps=np.arange(len(states)))
 geo=Geometry(n);positions,inv=np.unique(states[:,[0,1,4]],axis=0,return_inverse=True);distance=np.array([geo.clearance(p[:2],p[2],with_center=False) for p in positions])[inv];g=dict(map=n,seed=s,initial_clearance_m=float(distance[0]),minimum_clearance_m=float(distance.min()),overlap_frames=int((distance<=1e-10).sum()),frames=len(states),max_distance_from_start_m=float(np.linalg.norm(states[:,:2]-states[0,:2],axis=1).max()),success=row['success'],collision=row['collision'],timeout=row['timeout']);geometry.append(g)
 (folder/'outcomes.json').write_text(json.dumps(dict(checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=rows,geometry=geometry),indent=2)+'\n');print('CHECK',g,flush=True)
