"""Independent forward-only audit; never modifies checkpoints."""
import sys,io,zipfile,json,hashlib
from pathlib import Path
import torch,numpy as np
sys.path.insert(0,str(Path('experiments').resolve()))
from evaluate import BASE,ROOT,load_state,load_policy
from stable_baselines3 import PPO
paths=sorted((ROOT/'results/racing_v2').glob('development_baseline_*_trace.npz'))
x=np.concatenate([np.load(p)['obs'] for p in paths]);tx=torch.tensor(x)
old=load_policy(BASE);state=load_state(BASE)
h1=old.mlp_extractor.policy_net[:2](tx);h2=old.mlp_extractor.forward_actor(tx);a=old.action_net(h2)
wo=state['action_net.weight'];b2old=state['mlp_extractor.policy_net.2.bias'];w2old=state['mlp_extractor.policy_net.2.weight']
results={}
for name in ['panic_gate','wall_panic']:
 path=ROOT/'artifacts/ultra'/f'{name}.zip';p=load_policy(path);s=load_state(path)
 hn1=p.mlp_extractor.policy_net[:2](tx);hn2=p.mlp_extractor.forward_actor(tx);an=p.action_net(hn2)
 if name=='panic_gate':signal=h1[:,41]+h1[:,14]-h1[:,61]
 else:
  d=(tx[:,880:920].mean(1)+1)*15
  near=torch.tanh((.4-d)/.05)
  torch.testing.assert_close(hn1[:,15],near,atol=8e-5,rtol=1e-4)
  signal=h1[:,41]+near-h1[:,61]
 g=torch.tanh(4*(signal-2))
 desired=-.35*(1+g)
 compensation=-wo[:,1].unsqueeze(0)*(1+h2[:,1]).unsqueeze(1)
 rem=hn2-h2;rem[:,1]=0
 compensation+=rem@wo.T
 predicted=a+compensation;predicted[:,0]+=desired
 error=(an-predicted).abs().max(0).values
 assert max(error)<5e-6,error
 changed={k:int((s[k]!=v).sum()) for k,v in state.items() if not torch.equal(s[k],v)}
 assert all(torch.equal(s[k],v) for k,v in state.items() if 'value' in k or k=='log_std')
 with zipfile.ZipFile(BASE) as az,zipfile.ZipFile(path) as bz:
  assert az.namelist()==bz.namelist()
  assert all(az.read(k)==bz.read(k) for k in az.namelist() if k!='policy.pth')
 ppo=PPO.load(path,device='cpu',custom_objects={'learning_rate':0.,'lr_schedule':lambda _:0.,'clip_range':lambda _:.2})
 np.testing.assert_array_equal(ppo.predict(x,deterministic=True)[0],p.predict(x,deterministic=True)[0])
 np.testing.assert_allclose(p.predict(x,deterministic=True)[0],an.clamp(-1,1).numpy(),atol=1e-6)
 results[name]=dict(checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),samples=len(x),changed=changed,
  exact_formula_max_error_normalized=error.tolist(),max_deviation_from_ideal_steering_correction=float(((an-a)[:,0]-desired).abs().max()),
  max_speed_change_mps=float((an-a)[:,1].abs().max()*12.5),
  reclaimed_h2_original_range=[float(h2[:,1].min()),float(h2[:,1].max())],
  reclaimed_h1_original_range=[float(h1[:,15].min()),float(h1[:,15].max())] if name=='wall_panic' else None,
  activation_count_gt_point1=int(((1+g)/2>.1).sum()),
  ideal_correction_range=[float(desired.min()),float(desired.max())],
  sb3_predict_exact_match=True,critic_and_log_std_identical=True,non_policy_zip_entries_identical=True)
# Diagnostic only: mirror observations, no policy edits or model selection.
mirrored=old.predict(x[:,::-1].copy(),deterministic=True)[0];original=old.predict(x,deterministic=True)[0]
results['reflection_diagnostic']=dict(samples=len(x),original_positive_gt_point8=int((original[:,0]>.8).sum()),
 original_negative_lt_minus_point8=int((original[:,0]<-.8).sum()),mirrored_positive_gt_point8=int((mirrored[:,0]>.8).sum()),
 mirrored_negative_lt_minus_point8=int((mirrored[:,0]<-.8).sum()),median_abs_odd_symmetry_error=float(np.median(abs(original[:,0]+mirrored[:,0]))),
 caution='Asymmetry is not proof of a bug; mirrored scans are off the original state distribution. Use only a bounded local correction with independent paired rollouts, not a wholesale symmetry rewrite.')
(ROOT/'results/ultra_analysis/gate_verification.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
