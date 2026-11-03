"""Build and replay a fixed departure hypothesis on all known stalled starts."""
import hashlib,json,sys
from pathlib import Path
import numpy as np,torch
sys.path.insert(0,str(Path('experiments').resolve()))
from arc_launch_weights import build_launch_envelope
from evaluate import ROOT,evaluate,load_policy
from trajectory_audit import Geometry
folder=ROOT/'results/arc_recovery/startup';source=ROOT/'artifacts/from_scratch/arc_dynamic.pt';dest=ROOT/'artifacts/arc_recovery/startup_core.pt'
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
assert torch.equal(weights[:,2:],original[:,2:]),(weights[:,2:]-original[:,2:]).abs().max()
published=load_policy(dest).model
assert torch.equal(weights, published.envelope)
for k,v in policy.model.state_dict().items():
    if k!='envelope':assert torch.equal(v,published.state_dict()[k])
outcomes=json.loads((folder/'core/startup_outcomes.json').read_text())
assert outcomes['checkpoint_sha256']==hashlib.sha256(dest.read_bytes()).hexdigest()
assert all(r['success'] and not r['overlap_frames'] for r in outcomes['geometry'] if not r['initial_overlap'])
assert all(r['timeout'] and not r['collision'] for r in outcomes['geometry'] if r['initial_overlap'])
print('Verified published compiler, checkpoint and seven full-length replays', outcomes['checkpoint_sha256'])
