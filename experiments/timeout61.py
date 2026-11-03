"""GPT-6.1/high experiment: a short kinematic departure, encoded only in weights."""
import hashlib,json
from pathlib import Path
import numpy as np
import torch
from from_scratch import radial_envelope,piecewise_slopes,ROOT
from arc_recovery_weights import steady_state

SOURCE=ROOT/'artifacts/arc_recovery/nose_guard.pt'
OUT=ROOT/'artifacts/timeout61'
def build():
    model=torch.jit.load(str(SOURCE)).eval()
    k=np.array([-1.2,-.9,-.65,-.45,-.3,-.18,-.1,-.05,0,.05,.1,.18,.3,.45,.65,.9,1.2])
    angles=np.linspace(-2.35,2.35,1080)
    before={n:v.clone() for n,v in model.state_dict().items()}
    for i,curvature in enumerate(k):
        # A 20cm footprint sweep at creep speed is evaluated in the existing
        # first predicate. The 2cm offset compensates the half-activation ramp.
        model.envelope[i,0].copy_(torch.tensor(radial_envelope(curvature,.2,angles,margin=0.,beta=0.)+.02))
    knots=model.knots.numpy()
    basis=np.maximum(knots[:,None]-knots[None,:],0)
    speed=(model.speed_base[:,None]+model.speed_slopes@torch.tensor(basis.T,dtype=torch.float32)).numpy()
    steer=(model.steer_base[:,None]+model.steer_slopes@torch.tensor(basis.T,dtype=torch.float32)).numpy()
    speed[:,2]=.35
    steer[:,2]=np.arctan(.3302*k)
    model.speed_slopes.copy_(torch.tensor(piecewise_slopes(speed,knots),dtype=torch.float32))
    model.steer_slopes.copy_(torch.tensor(piecewise_slopes(steer,knots),dtype=torch.float32))
    OUT.mkdir(exist_ok=True,parents=True)
    path=OUT/'short_departure.pt';model.save(str(path))
    changed={n:int((v!=before[n]).sum()) for n,v in model.state_dict().items() if not torch.equal(v,before[n])}
    data={'model':'gpt-6.1-sol','reasoning_effort':'high','date':'2026-11-03','hypothesis':'Short 0.2m kinematic sweep can escape a launch deadlock; isolated predicate commands at most 0.35m/s. Longer heads retain their knot values.',
          'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'changed':changed,'simulator_unchanged':True}
    (ROOT/'results/timeout61/experiment.json').write_text(json.dumps(data,indent=2)+'\n')
    print(path)
if __name__=='__main__':build()
