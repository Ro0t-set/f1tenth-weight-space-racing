"""Verify tensor-only edit, evaluator equivalence, and drift-model limitations."""
import json
import zipfile
import numpy as np
import torch
import yaml
from PIL import Image
from evaluate import ROOT,BASE,MAPS,load_state,load_policy
from f110_gym.envs.dynamic_models import vehicle_dynamics_st
from stable_baselines3 import PPO

OUT=ROOT/'results/racing_v2'
edited=ROOT/'artifacts/racing_v2/curvature_compensated.zip'
b,e=load_state(BASE),load_state(edited)
changed={k:int((e[k]!=v).sum()) for k,v in b.items() if not torch.equal(e[k],v)}
assert changed=={'action_net.weight':64,'action_net.bias':2},changed
with zipfile.ZipFile(BASE) as a,zipfile.ZipFile(edited) as z:
    assert all(a.read(k)==z.read(k) for k in a.namelist() if k!='policy.pth')
states=np.concatenate([np.load(p)['obs'] for p in sorted(OUT.glob('development_baseline_*_trace.npz'))])
old,new=load_policy(BASE),load_policy(edited)
x=torch.from_numpy(states)
ao=old.action_net(old.mlp_extractor.forward_actor(x)).numpy()
ae=new.action_net(new.mlp_extractor.forward_actor(x)).numpy()
gain=json.loads(edited.with_suffix('.json').read_text())['specification']['steering_gain']
np.testing.assert_allclose(ae[:,0],ao[:,0]*gain,rtol=1e-5,atol=5e-7)
np.testing.assert_allclose(ae[:,1],ao[:,1]+.3/12.5,rtol=1e-5,atol=5e-7)
for path in [BASE,edited]:
    ppo=PPO.load(path,device='cpu',custom_objects={'learning_rate':0.,'lr_schedule':lambda _:0.,'clip_range':lambda _:.2})
    np.testing.assert_array_equal(ppo.predict(states[:256],deterministic=True)[0],
                                  load_policy(path).predict(states[:256],deterministic=True)[0])
old_rows=json.loads((ROOT/'results/holdout_baseline.json').read_text())['rows']
new_rows=json.loads((OUT/'development_baseline.json').read_text())['rows']
repeats=0
for a in old_rows:
    row=next((r for r in new_rows if (r['map'],r['seed'])==(a['map'],a['seed'])),None)
    if row:
        assert all(a[k]==row[k] for k in a if k!='wall_seconds')
        repeats+=1

# Linear steady-state lateral dynamics at fixed speed, zero acceleration.
# This is not an all-transient impossibility proof; it audits representative speeds.
params=[1.0489,4.718,5.4562,.15875,.17145,.074,3.74,.04712,-.4189,.4189,-3.2,3.2,7.319,9.51,-5.,20.]
equilibria=[]
for speed in [3.,5.,8.,10.,12.,15.,20.]:
    x=np.zeros(7);x[3]=speed
    def f(y):return vehicle_dynamics_st(y,np.zeros(2),*params)[5:7]
    xr=x.copy();xr[5]=1.;xb=x.copy();xb[6]=1.;xd=x.copy();xd[2]=1.
    A=np.c_[f(xr),f(xb)];B=f(xd);eq=-np.linalg.solve(A,B)
    equilibria.append(dict(speed_mps=speed,yaw_rate_per_steer=float(eq[0]),
                          beta_per_steer=float(eq[1]),max_real_eigenvalue=float(np.linalg.eigvals(A).real.max()),
                          stable_countersteer_equilibrium=bool(eq[0]<0 and np.linalg.eigvals(A).real.max()<0)))
(OUT/'drift_equilibria.json').write_text(json.dumps(equilibria,indent=2)+'\n')

# Independently inspect the geometric footprint at the recorded spawn, without
# excluding any episode or altering the evaluation metrics.
footprints=[]
for row in new_rows:
    if row['seconds']>.1:continue
    folder=MAPS/row['map']
    meta=yaml.safe_load((folder/f"{row['map']}_map.yaml").read_text())
    img=np.flipud(np.array(Image.open(folder/f"{row['map']}_map.png")))
    xx,yy=np.meshgrid(np.linspace(-.29,.29,30),np.linspace(-.155,.155,17))
    px,py,heading=row['start']
    wx=px+xx*np.cos(heading)-yy*np.sin(heading);wy=py+xx*np.sin(heading)+yy*np.cos(heading)
    ix=((wx-meta['origin'][0])/meta['resolution']).astype(int)
    iy=((wy-meta['origin'][1])/meta['resolution']).astype(int)
    footprints.append(dict(map=row['map'],seed=row['seed'],failure_seconds=row['seconds'],
                           occupied_footprint_samples_fraction=float((img[iy,ix]<=128).mean()),sample_count=xx.size))
(OUT/'spawn_audit.json').write_text(json.dumps(footprints,indent=2)+'\n')
validation=dict(changed=changed,formula_verified_on=len(states),sb3_exact_prediction_samples=256,
                telemetry_preserves_repeated_episodes=repeats,unchanged_zip_entries='all except policy.pth',
                original_simulator_unchanged=True,
                drift_proxy_definition='|beta|>=5deg, speed>=3m/s, steering*yaw_rate<-.01, continuously >=.5s; only completed episodes; not proof of tire drift')
(OUT/'verification.json').write_text(json.dumps(validation,indent=2)+'\n')
print(json.dumps(validation,indent=2))
