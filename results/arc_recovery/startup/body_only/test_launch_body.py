"""Build and replay a fixed departure hypothesis on all known stalled starts."""
import hashlib,json,sys
from pathlib import Path
import numpy as np,torch
sys.path.insert(0,str(Path('experiments').resolve()))
from arc_launch_body import build_launch_envelope
from evaluate import ROOT,evaluate,load_policy
from trajectory_audit import Geometry
folder=ROOT/'results/arc_recovery/startup';source=ROOT/'artifacts/from_scratch/arc_dynamic.pt';dest=ROOT/'artifacts/arc_recovery/startup_body.pt'
spec=json.loads(source.with_suffix('.json').read_text());ks=np.array(spec['curvature']);hs=np.array(spec['horizons']);angles=np.linspace(-2.35,2.35,1080)
policy=load_policy(source);model=policy.model;original=model.envelope.clone()
def speed_function(k,h):return min(np.sqrt(12.*max(h-.25,0.)),np.sqrt(7./max(abs(k),.001)),10.)
def steady_function(k,v):
 if v<.5:return np.arctan(.3302*k),0.
 mu_g=1.0489*9.81
 steer_gain=.3302+v*v*(1/4.718-1/5.4562)/mu_g
 delta=np.clip(k*steer_gain,-.4189,.4189)
 return delta,(delta/steer_gain)*(.17145-v*v/(mu_g*5.4562))
weights=torch.tensor(build_launch_envelope(ks,hs,angles,model.valid.numpy(),speed_function,steady_function),dtype=torch.float32)
assert torch.equal(weights[:,1:],original[:,1:]),(weights[:,1:]-original[:,1:]).abs().max()
assert torch.all(weights[:,0]<=original[:,0]);model.envelope.copy_(weights);model.save(str(dest));policy=load_policy(dest)
base=load_policy(source).model
for k,v in policy.model.state_dict().items():
 if k!='envelope':assert torch.equal(v,base.state_dict()[k])
inits=json.loads((folder/'initial_geometry.json').read_text());folder=folder/'body_only';rows=[];geometry=[]
for r in inits:
 n,s=r['map'],r['seed'];result,tr=evaluate(policy,[n],[s],state_trace=True);row=result[0];rows.append(row)
 st=np.stack([f['state'] for f in tr[0][2]]);steps=np.arange(len(st));np.savez_compressed(folder/f'startup_{n}_{s}_trace.npz',states=st,steps=steps)
 geo=Geometry(n);unique,inv=np.unique(st[:,[0,1,4]],axis=0,return_inverse=True)
 distance=np.array([geo.clearance(p[:2],p[2],with_center=False) for p in unique])[inv];overlap=distance<=1e-10
 geometry.append(dict(map=n,seed=s,initial_clearance_m=float(distance[0]),minimum_clearance_m=float(distance.min()),first_1s_minimum_clearance_m=float(distance[:100].min()),overlap_frames=int(overlap.sum()),frames=len(st),initial_overlap=bool(overlap[0]),max_distance_from_start_m=float(np.linalg.norm(st[:,:2]-st[0,:2],axis=1).max()),success=row['success'],collision=row['collision'],timeout=row['timeout']))
 (folder/'startup_outcomes.json').write_text(json.dumps(dict(checkpoint_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),rows=rows,geometry=geometry),indent=2)+'\n');print('CHECK',geometry[-1],flush=True)
