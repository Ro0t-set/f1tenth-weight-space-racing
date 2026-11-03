"""Read-only forward audit. No parameter search, training, or new rollout."""
import sys, json, zipfile, hashlib
from pathlib import Path
import numpy as np, torch
sys.path.insert(0,str(Path('experiments').resolve()))
from evaluate import ROOT,BASE,load_state,load_policy
from stable_baselines3 import PPO
parent=ROOT/'artifacts/ultra/wall_panic_fast.zip'
p=load_state(parent); bp=load_policy(parent)
paths=sorted((ROOT/'results/racing_v2').glob('development_baseline_*_trace.npz'))+sorted((ROOT/'results/trajectory_v4_analysis').glob('fast_*_trace.npz'))
xs=[np.load(path)['obs'] for path in paths]; x=np.concatenate(xs); tx=torch.tensor(x)
h1=bp.mlp_extractor.policy_net[:2](tx); h2=bp.mlp_extractor.forward_actor(tx); ap=bp.action_net(h2)
w1,b1,w2,b2,wo,bo=[p[k] for k in ['mlp_extractor.policy_net.0.weight','mlp_extractor.policy_net.0.bias','mlp_extractor.policy_net.2.weight','mlp_extractor.policy_net.2.bias','action_net.weight','action_net.bias']]
d=(tx+1)*15; angles=torch.tensor(np.linspace(-2.35,2.35,1080)[760:800],dtype=torch.float32)
y=(d[:,760:800]*angles.sin()).mean(1); near=torch.tanh((1-y)/.2)
g_broad=torch.tanh(4*(near-h1[:,41]+h1[:,61]-2))
angles_back=torch.tensor(np.linspace(-2.35,2.35,1080)[1000:1040],dtype=torch.float32)
y_back=(d[:,1000:1040]*angles_back.sin()).mean(1)
approach=torch.tanh((y_back-y-.15)/.075)
g=torch.tanh(4*(near-h1[:,41]+h1[:,61]+approach+h1[:,1]-4))
report={'samples':len(x),'original_h1_0_range':[float(h1[:,0].min()),float(h1[:,0].max())],'original_h2_14_range':[float(h2[:,14].min()),float(h2[:,14].max())], 'variants':{},'interference':{}}
for name in ['exit_approach']:
 path=ROOT/f'artifacts/trajectory_v4/{name}.zip'; s=load_state(path); pol=load_policy(path)
 a=pol.action_net(pol.mlp_extractor.forward_actor(tx))
 hh=h1.clone()
 if name!='exit_only': hh[:,15]=torch.tanh((.6-d[:,880:920].mean(1))/.05)
 hh2=torch.tanh(hh@w2.T+b2)
 prior=hh2@wo.T+bo
 if name!='early_panic':
  # Exact compensation residual from reclaiming h1[0] and h2[14].
  compensated=torch.tanh(hh@w2.T+b2+(1-hh[:,0,None])*w2[:,0][None,:])
  compensated=torch.tanh(hh@w2.T+b2+(1-hh[:,0,None])*w2[:,0][None,:]-(1+hh[:,62,None])*w2[:,62][None,:])
  compensated[:,14]=-1.
  expected=compensated@wo.T+bo
  comp=expected-prior
  expected[:,0]-=.08*(1+g)
 else:
  expected=prior;comp=torch.zeros_like(a)
 err=(a-expected).abs().max(0).values
 assert float(err.max())<1e-4, (name,err)
 assert all(torch.equal(v,s[k]) for k,v in p.items() if 'value' in k or k=='log_std')
 with zipfile.ZipFile(parent) as aa,zipfile.ZipFile(path) as zz:
  assert aa.namelist()==zz.namelist()
  assert all(aa.read(k)==zz.read(k) for k in aa.namelist() if k!='policy.pth')
 model=PPO.load(path,device='cpu',custom_objects={'learning_rate':0.,'lr_schedule':lambda _:0.,'clip_range':lambda _:.2})
 np.testing.assert_array_equal(model.predict(x,deterministic=True)[0],pol.predict(x,deterministic=True)[0])
 report['variants'][name]={'formula_max_error':err.tolist(),'compensation_steering_error_range':[float(comp[:,0].min()),float(comp[:,0].max())],'compensation_speed_error_mps_range':[float(comp[:,1].min()*12.5),float(comp[:,1].max()*12.5)],'speed_change_total_range_mps':[float(((a-ap)[:,1]*12.5).min()),float(((a-ap)[:,1]*12.5).max())],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'critic_logstd_zip_metadata_unchanged':True,'PPO_load_exact_predictions':True,'changed_tensors':{k:int((v!=p[k]).sum()) for k,v in s.items() if not torch.equal(v,p[k])}}
offset=0
for path,xx in zip(paths,xs):
 ix=slice(offset,offset+len(xx));offset+=len(xx)
 correction=(.08*(1+g[ix])).numpy(); pp=ap[ix,0].numpy(); hh1=h1[ix,1].numpy(); yy=y[ix].numpy()
 report['interference'][path.stem]={'samples':len(xx),'correction_gt_02':int((correction>.02).sum()),'correction_gt_08':int((correction>.08).sum()),'correction_gt_08_while_h1_1_negative':int(((correction>.08)&(hh1<0)).sum()),'correction_gt_08_while_parent_right_gt_02':int(((correction>.08)&(pp<-.2)).sum()),'max_correction':float(correction.max()),'projection_min':float(yy.min()),'broad_correction_gt_08':int((.08*(1+g_broad[ix])>.08).sum()),'last_8_samples':[{ 'time':float(np.load(path)['steps'][j]*.01),'steer':float(pp[j]),'projected_left60':float(yy[j]),'approach_delta_m':float((y_back-y)[ix][j]),'h1_1':float(hh1[j]),'correction':float(correction[j])} for j in range(max(0,len(xx)-8),len(xx))],'time_integrated_correction_normalized':float(correction.sum()*.1)}
out=ROOT/'results/trajectory_v4_analysis/exit_approach_verification.json';out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='interference'},indent=2))
print('COUNTS',json.dumps({k:{kk:vv for kk,vv in v.items() if kk!='last_8_samples'} for k,v in report['interference'].items()},indent=2))
print('SOCHI_TAILS',json.dumps({k:v['last_8_samples'] for k,v in report['interference'].items() if k.startswith('fast_sochi_monza_Sochi')},indent=2))
