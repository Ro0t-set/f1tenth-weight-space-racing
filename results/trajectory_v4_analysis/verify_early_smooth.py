"""Independent read-only audit of frozen early_smooth; no rollout or tuning."""
import json,zipfile,hashlib,sys
from pathlib import Path
import numpy as np, torch
sys.path.insert(0,str(Path('experiments').resolve()))
from evaluate import ROOT,BASE,load_state,load_policy
from stable_baselines3 import PPO
parent=ROOT/'artifacts/ultra/wall_panic_fast.zip'
candidate=ROOT/'artifacts/trajectory_v4/early_smooth.zip'
p,c,b=load_state(parent),load_state(candidate),load_state(BASE)
W='mlp_extractor.policy_net.0.weight';B='mlp_extractor.policy_net.0.bias'
expected={k:v.clone() for k,v in p.items()}
# Independent NumPy convolution, half-sample symmetric edge extension, radius 4*sigma.
t=np.arange(-8,9,dtype=np.float64);kernel=np.exp(-t*t/8);kernel/=kernel.sum()
for i in [1,14,41,61]:
 expected[W][i]=torch.tensor(np.convolve(np.pad(p[W][i].numpy(),8,mode='symmetric'),kernel,mode='valid').astype(np.float32))
expected[B][15]=(.6-15)/.05
formula_errors={k:float((c[k]-v).abs().max()) for k,v in expected.items()}
assert max(formula_errors.values())<1e-8,formula_errors
changes=lambda ref:{k:int((v!=ref[k]).sum()) for k,v in c.items() if not torch.equal(v,ref[k])}
assert set(changes(p))=={W,B}
assert torch.equal(c[W][15],p[W][15])
assert torch.where(torch.any(c[W]!=p[W],dim=1))[0].tolist()==[1,14,41,61]
assert torch.where(c[B]!=p[B])[0].tolist()==[15]
assert all(torch.equal(c[k],v) for k,v in b.items() if 'value' in k or k=='log_std')
for ref in [parent,BASE]:
 with zipfile.ZipFile(ref) as aa,zipfile.ZipFile(candidate) as zz:
  assert aa.namelist()==zz.namelist()
  assert all(aa.read(k)==zz.read(k) for k in aa.namelist() if k!='policy.pth')
freeze=json.loads((ROOT/'results/trajectory_v4/holdout_manifest.json').read_text())
for key,path in [('previous',parent),('candidate',candidate)]:
 assert hashlib.sha256(path.read_bytes()).hexdigest()==freeze['checkpoints'][key]['sha256']
paths=sorted((ROOT/'results/racing_v2').glob('development_baseline_*_trace.npz'))+sorted((ROOT/'results/trajectory_v4_analysis').glob('fast_*_trace.npz'))
x=np.concatenate([np.load(q)['obs'] for q in paths]);tx=torch.tensor(x)
pp,pc=load_policy(parent),load_policy(candidate)
ap=pp.action_net(pp.mlp_extractor.forward_actor(tx));ac=pc.action_net(pc.mlp_extractor.forward_actor(tx))
model=PPO.load(candidate,device='cpu',custom_objects={'learning_rate':0.,'lr_schedule':lambda _:0.,'clip_range':lambda _:.2})
np.testing.assert_array_equal(model.predict(x,deterministic=True)[0],pc.predict(x,deterministic=True)[0])
np.testing.assert_allclose(pc.predict(x,deterministic=True)[0],ac.clamp(-1,1).numpy(),atol=1e-7,rtol=1e-6)
def stats(z):
 z=z.numpy();return {'min':float(z.min()),'max':float(z.max()),'mean':float(z.mean()),'mean_abs':float(np.abs(z).mean()),'absolute_quantiles_p50_p95_p99_max':np.quantile(np.abs(z),[.5,.95,.99,1.]).tolist()}
summary={}
for name in ['early_panic','exit_support','exit_only','exit_approach','early_smooth','turn_preview']:
 d=json.loads((ROOT/f'results/trajectory_v4/development_{name}.json').read_text()); rows=d['rows']
 summary[name]={'episodes':len(rows),'successes':sum(r['success'] for r in rows),'collisions':sum(r['collision'] for r in rows),'sha256_recorded':d['sha256']}
 allcomparisons=json.loads((ROOT/'results/trajectory_v4/development_comparisons.json').read_text())
 cmp=allcomparisons.get(name) or json.loads((ROOT/f'results/trajectory_v4/development_{name}_comparison.json').read_text())
 summary[name].update({k:cmp[k] for k in ['gained','lost','mean_paired_lap_change_pct']})
 assert summary[name]['episodes']==21
result={'checkpoint_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'samples':len(x),'frozen_hashes_match':True,'changed_from_parent':changes(p),'changed_from_original':changes(b),'total_changed_from_parent':sum(changes(p).values()),'total_changed_from_original':sum(changes(b).values()),'independent_gaussian_max_error':max(formula_errors.values()),'sigma_rays':2.,'radius_rays':8,'edge_mode':'half-sample symmetric reflect','gaussian_rows':[1,14,41,61],'other_changed_parameter':'first layer bias15 = -288, left wall threshold .6m','programmed_wall_weights_unchanged':True,'critic_logstd_unchanged':True,'nonpolicy_zip_entries_unchanged':True,'PPO_predictions_exactly_match_evaluator':True,'raw_same_observation_steering_delta_normalized':stats(ac[:,0]-ap[:,0]),'raw_same_observation_speed_command_delta_mps':stats((ac[:,1]-ap[:,1])*12.5),'clipped_same_observation_speed_command_delta_mps':stats((ac[:,1].clamp(-1,1)-ap[:,1].clamp(-1,1))*12.5),'row_DC_sum_errors':[float((c[W][i].double().sum()-p[W][i].double().sum()).abs()) for i in [1,14,41,61]],'development_candidates':summary,'caveat':'Speed-head tensors unchanged but smoothing shared hidden features changes both outputs. These development observations are not holdout performance evidence.'}
(ROOT/'results/trajectory_v4_analysis/early_smooth_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
