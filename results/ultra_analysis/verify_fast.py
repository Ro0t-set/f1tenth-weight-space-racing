"""Independent read-only checkpoint audit. No rollout or parameter tuning."""
import sys,zipfile,json,hashlib
from pathlib import Path
import numpy as np,torch
sys.path.insert(0,str(Path('experiments').resolve()))
from evaluate import ROOT,BASE,load_policy,load_state
from stable_baselines3 import PPO
wall=ROOT/'artifacts/ultra/wall_panic.zip';fast=ROOT/'artifacts/ultra/wall_panic_fast.zip'
b,w,f=load_state(BASE),load_state(wall),load_state(fast)
changes_base={k:int((f[k]!=v).sum()) for k,v in b.items() if not torch.equal(f[k],v)}
changes_wall={k:int((f[k]!=v).sum()) for k,v in w.items() if not torch.equal(f[k],v)}
assert changes_wall=={'action_net.bias':1}
assert f['action_net.bias'][0]==w['action_net.bias'][0]
assert abs(float(f['action_net.bias'][1]-w['action_net.bias'][1])-.016)<1e-8
assert sum(changes_base.values())==1276
assert all(torch.equal(f[k],v) for k,v in b.items() if 'value' in k or k=='log_std')
for path in [BASE,wall]:
 with zipfile.ZipFile(path) as a,zipfile.ZipFile(fast) as z:
  assert a.namelist()==z.namelist()
  assert all(a.read(k)==z.read(k) for k in a.namelist() if k!='policy.pth')
x=np.concatenate([np.load(p)['obs'] for p in sorted((ROOT/'results/racing_v2').glob('development_baseline_*_trace.npz'))]);tx=torch.tensor(x)
po,pw,pf=load_policy(BASE),load_policy(wall),load_policy(fast)
h1=po.mlp_extractor.policy_net[:2](tx);h2=po.mlp_extractor.forward_actor(tx);ao=po.action_net(h2)
hw=pw.mlp_extractor.forward_actor(tx);aw=pw.action_net(hw);af=pf.action_net(pf.mlp_extractor.forward_actor(tx))
np.testing.assert_array_equal(aw[:,0].numpy(),af[:,0].numpy())
expected_from_wall=aw.clone();expected_from_wall[:,1]+=.016
wall_error=(af-expected_from_wall).abs().max(0).values
assert max(wall_error)<1e-7
# Reconstruct the complete raw-output formula independently from original weights.
d=(tx[:,880:920].mean(1)+1)*15
near=torch.tanh((.4-d)/.05)
g=torch.tanh(4*(h1[:,41]-h1[:,61]+near-2))
comp=-b['action_net.weight'][:,1].unsqueeze(0)*(1+h2[:,1]).unsqueeze(1)
residual=hw-h2;residual[:,1]=0
comp+=residual@b['action_net.weight'].T
expected=ao+comp;expected[:,0]-=.35*(1+g);expected[:,1]+=.016
formula_error=(af-expected).abs().max(0).values
assert max(formula_error)<5e-6
ppo=PPO.load(fast,device='cpu',custom_objects={'learning_rate':0.,'lr_schedule':lambda _:0.,'clip_range':lambda _:.2})
np.testing.assert_array_equal(ppo.predict(x,deterministic=True)[0],pf.predict(x,deterministic=True)[0])
np.testing.assert_allclose(pf.predict(x,deterministic=True)[0],af.clamp(-1,1).numpy(),rtol=1e-6,atol=1e-6)
metadata=json.loads(fast.with_suffix('.json').read_text())
sha=hashlib.sha256(fast.read_bytes()).hexdigest();assert metadata['sha256']==sha
assert metadata['source_sha256']==hashlib.sha256(BASE.read_bytes()).hexdigest()
result=dict(checkpoint_sha256=sha,samples=len(x),changes_vs_original=changes_base,
 changes_vs_wall_panic=changes_wall,added_normalized_speed_bias=float(f['action_net.bias'][1]-w['action_net.bias'][1]),
 exact_formula_max_error_normalized=formula_error.tolist(),exact_wall_plus_bias_error_normalized=wall_error.tolist(),
 raw_speed_increase_vs_wall_mps_range=[float(((af-aw)[:,1]*12.5).min()),float(((af-aw)[:,1]*12.5).max())],
 raw_speed_increase_vs_original_mps_range=[float(((af-ao)[:,1]*12.5).min()),float(((af-ao)[:,1]*12.5).max())],
 steering_identical_to_wall_panic_on_all_samples=True,critic_and_log_std_identical=True,
 non_policy_zip_entries_identical=True,sb3_prediction_exact_match_on_all_samples=True,
 original_architecture_and_observation_shapes_preserved=True,
 caveat='Speed increment is exact before original action clipping. Tiny difference from +.2 relative to ORIGINAL is the already-audited near-constant-neuron compensation, not an external controller.')
(ROOT/'results/ultra_analysis/fast_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
