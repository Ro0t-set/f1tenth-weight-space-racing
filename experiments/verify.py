"""Checks evaluator equivalence, deterministic resets, and edit scope."""
import json
import argparse
import zipfile
import numpy as np
import torch
from evaluate import ROOT, BASE, load_policy, load_state
from stable_baselines3 import PPO

ap=argparse.ArgumentParser()
ap.add_argument('--cautious',action='store_true')
args=ap.parse_args()
edited = ROOT/'artifacts'/('clearance_cautious.zip' if args.cautious else 'clearance_gate.zip')
obs = np.load(ROOT/'results/development_baseline_BrandsHatch_101_trace.npz')['obs'][:128]
checks = {}
for path in [BASE, edited]:
    policy = load_policy(path)
    ppo = PPO.load(path, device='cpu', custom_objects={
        'learning_rate':0., 'lr_schedule':lambda _:0., 'clip_range':lambda _:.2})
    np.testing.assert_array_equal(policy.predict(obs,deterministic=True)[0],
                                  ppo.predict(obs,deterministic=True)[0])
checks['sb3_prediction_equivalence'] = 'Exact, 128 observations for each checkpoint'
before, after = load_state(BASE), load_state(edited)
manifest = json.loads(edited.with_suffix('.json').read_text())
assert sum(int((before[k]!=after[k]).sum()) for k in before) == manifest['changed_total']
assert all(torch.equal(v, after[k]) for k,v in before.items() if 'value' in k or k=='log_std')
with zipfile.ZipFile(BASE) as a, zipfile.ZipFile(edited) as b:
    assert a.namelist() == b.namelist()
    assert all(a.read(k)==b.read(k) for k in a.namelist() if k!='policy.pth')
checks['edit_scope'] = 'Only policy.pth changed; critic and log_std unchanged; 1276 scalar edits'
smoke = json.loads((ROOT/'results/smoke_baseline.json').read_text())['rows']
dev = json.loads((ROOT/'results/development_baseline.json').read_text())['rows']
for x in smoke:
    y = next(r for r in dev if (r['map'],r['seed'])==(x['map'],x['seed']))
    assert {k:v for k,v in x.items() if k!='wall_seconds'} == {k:v for k,v in y.items() if k!='wall_seconds'}
checks['repeatability'] = 'Two independently repeated episodes exactly match, except wall time'
(ROOT/'results'/('verification_cautious.json' if args.cautious else 'verification.json')).write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
