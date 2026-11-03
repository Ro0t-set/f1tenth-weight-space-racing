import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path('experiments').resolve()))
from evaluate import evaluate,load_policy,ROOT
from from_scratch import radial_envelope
from trajectory_audit import Geometry
folder=ROOT/'results/arc_recovery/startup'
policy=load_policy(ROOT/'artifacts/from_scratch/arc_dynamic.pt')
rows=json.loads((ROOT/'results/from_scratch/final_candidate.json').read_text())['rows']
a=np.linspace(-2.35,2.35,1080);body=radial_envelope(0,0,a,margin=0);margin=radial_envelope(0,0,a);R=policy.model.envelope.numpy();data=[]
for r in rows:
 if not r['timeout']:continue
 n,s=r['map'],r['seed'];_,tr=evaluate(policy,[n],[s],max_steps=1,trace=True);f=tr[0][2][0];obs=f['obs'];d=(obs+1)*15;sector=d.reshape(-1,6).min(-1);v=(R[:,0]-sector).max(-1);st=f['state'];g=Geometry(n).clearance(st[:2],st[4],with_center=False)
 j=(body-sector).argmax();closest=d.argmin(); i=v.argmin(); jj=(R[i,0]-sector).argmax()
 row=dict(map=n,seed=s,body_clearance=g,min_lidar=float(d.min()),min_lidar_angle=float(np.rad2deg(a[closest])),max_current_body_violation=float((body-sector).max()),angle_of_max_violation=float(np.rad2deg(a[6*j+3])),max_current_margin_violation=float((margin-sector).max()),shortest_arc_violation=float(v[i]),limiting_angle=float(np.rad2deg(a[6*jj+3])),limiting_range=float(sector[jj]))
 data.append(row);np.savez_compressed(folder/f'initial_{n}_{s}.npz',obs=obs,state=st);print('START',row,flush=True)
(folder/'initial_geometry.json').write_text(json.dumps(data,indent=2)+'\n')
