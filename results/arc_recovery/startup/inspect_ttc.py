"""Record arguments to the original TTC exactly when its existing test fires."""
import json,sys,contextlib,io
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path('experiments').resolve()));from evaluate import ROOT,evaluate,load_policy
import f110_gym.envs.base_classes as base
original=base.check_ttc_jit
folder=ROOT/'results/arc_recovery/startup';model=load_policy(ROOT/'artifacts/arc_recovery/startup_body.pt');report=[]
for n,s in [('IMS',60505),('YasMarina',60404)]:
 hit=[]
 def record(scan,vel,angles,cosines,sides,threshold):
  verdict=original(scan,vel,angles,cosines,sides,threshold)
  if verdict and vel:
   t=(scan-sides)/(vel*cosines);indices=np.flatnonzero((t>=0)&(t<threshold));hit.append([dict(beam=int(i),angle_deg=float(np.rad2deg(angles[i])),distance_m=float(scan[i]),ttc_body_radius_m=float(sides[i]),ttc_s=float(t[i]),vx_mps=float(vel)) for i in indices])
  return verdict
 base.check_ttc_jit=record
 with contextlib.redirect_stdout(io.StringIO()):rows,_=evaluate(model,[n],[s],max_steps=100)
 assert rows[0]['collision'] and hit
 report.append(dict(map=n,seed=s,physics_steps=rows[0]['steps'],hits=hit));print(report[-1])
 base.check_ttc_jit=original
(folder/'ttc_failure_beams.json').write_text(json.dumps(report,indent=2)+'\n')
