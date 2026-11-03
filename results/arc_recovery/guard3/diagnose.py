import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path('experiments').resolve()));from evaluate import ROOT,evaluate,load_policy
import f110_gym.envs.base_classes as base
model=load_policy(ROOT/'artifacts/arc_recovery/launch_guard.pt');orig=base.check_ttc_jit;folder=ROOT/'results/arc_recovery/guard3';recent=[]
def observe(scan,vel,angles,cosines,sides,threshold):
 verdict=orig(scan,vel,angles,cosines,sides,threshold);ttc=np.divide(scan-sides,vel*cosines,out=np.full_like(scan,np.inf),where=vel*cosines!=0);k=np.argmin(np.where(ttc>=0,ttc,np.inf));recent.append(dict(min_ttc=float(ttc[k]),verdict=bool(verdict),beam=int(k),theta=float(np.rad2deg(angles[k])),vel=float(vel),distance=float(scan[k]),ttc_body=float(sides[k])));return verdict
base.check_ttc_jit=observe;rows,tr=evaluate(model,['Austin'],[71808],max_steps=20,trace=True);base.check_ttc_jit=orig
np.savez_compressed(folder/'initial_Austin_71808.npz',obs=tr[0][2][0]['obs'],state=tr[0][2][0]['state']);(folder/'ttc.json').write_text(json.dumps(recent,indent=2)+'\n');print(recent[-1]);d=np.load(ROOT/'results/arc_recovery/confirmation/final_candidate_Austin_71808_trace.npz')['states'];print(d[:,[2,3,4,5,6]].round(4));print([(r['map'],r['seed']) for r in json.loads((ROOT/'results/arc_recovery/confirmation/final_candidate.json').read_text())['rows'] if r['timeout']]);print('start',rows[0]['start'])
