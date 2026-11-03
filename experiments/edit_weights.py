"""Compile a LiDAR clearance gate into two existing tanh neurons. No optimizer."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
import argparse
import numpy as np
import torch
from evaluate import ROOT, BASE, load_state, load_policy

def edit(source=BASE, destination=ROOT/'artifacts/clearance_gate.zip', cautious=False):
    state = load_state(source)
    before = {key: value.clone() for key, value in state.items()}
    w1, b1 = state['mlp_extractor.policy_net.0.weight'], state['mlp_extractor.policy_net.0.bias']
    w2, b2 = state['mlp_extractor.policy_net.2.weight'], state['mlp_extractor.policy_net.2.bias']
    wo, bo = state['action_net.weight'], state['action_net.bias']
    # Development traces: h1[15] >= .9999992; h2[1] in [-.99901,-.99601].
    # Absorb their old near-constant contributions into the next layer's biases.
    b2.add_(w2[:,15])
    w2[:,15] = 0.
    bo.sub_(wo[:,1])
    wo[:,1] = 0.
    # Input x=(distance/15)-1. Mean of 40 forward rays (+/- ~5 degrees).
    # h1[15] = tanh((mean_forward_distance - 15m) / 3m).
    w1[15,:] = 0.
    w1[15,520:560] = 15. / (3. * 40.)
    b1[15] = 0.
    w2[1,:] = 0.
    w2[1,15] = 2.
    b2[1] = 0.
    # h2[1] = tanh(2*h1[15]); bounded, analytically specified speed correction.
    # Physical v = 12.5 * action[1] + 7.5. Steering gets no new circuit.
    low, high = (-.6, .3) if cautious else (0., .6)
    amplitude, offset = (high-low)/2., (high+low)/2.
    wo[1,1] = amplitude / (12.5 * np.tanh(2.))
    bo[1] += offset / 12.5
    changed = {k:int((v != before[k]).sum()) for k,v in state.items()}
    changed = {k:v for k,v in changed.items() if v}
    assert all(torch.equal(v,before[k]) for k,v in state.items()
               if 'value' in k or k == 'log_std')
    assert all(torch.isfinite(v).all() for v in state.values())
    buffer = io.BytesIO()
    torch.save(state, buffer)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as out:
        for item in original.infolist():
            out.writestr(item, buffer.getvalue() if item.filename == 'policy.pth' else original.read(item.filename))
    # Validate the analytic circuit against actual forward passes on development data.
    old_policy, new_policy = load_policy(source), load_policy(destination)
    observations = np.concatenate([np.load(f)['obs'] for f in
                                    sorted((ROOT/'results').glob('development_baseline_*_trace.npz'))])
    x = torch.from_numpy(observations)
    a_old = old_policy.action_net(old_policy.mlp_extractor.forward_actor(x)).numpy()
    a_new = new_policy.action_net(new_policy.mlp_extractor.forward_actor(x)).numpy()
    distance = (observations[:,520:560].mean(1)+1.)*15.
    expected_boost = offset + amplitude*np.tanh(2.*np.tanh((distance-15.)/3.))/np.tanh(2.)
    speed_error = float(np.max(np.abs((a_new[:,1]-a_old[:,1])*12.5-expected_boost)))
    steering_error = float(np.max(np.abs(a_new[:,0]-a_old[:,0])))
    assert steering_error < .0001, steering_error
    assert speed_error < .002, speed_error
    manifest = dict(source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    output_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                    changed=changed, changed_total=sum(changed.values()),
                    total_parameters=sum(v.numel() for v in state.values()),
                    speed_correction_mps=[low,high],
                    validation_samples=len(x), max_unclipped_steering_delta=steering_error,
                    max_speed_formula_error_mps=speed_error,
                    method='analytic clearance gate, no gradients, fitting, or automated search',
                    caveat='Near-constant neuron assumption checked on development only. Optimizer state is original: inference artifact, reset optimizer before training.')
    destination.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--cautious',action='store_true')
    args=ap.parse_args()
    edit(destination=ROOT/'artifacts'/('clearance_cautious.zip' if args.cautious else 'clearance_gate.zip'),
         cautious=args.cautious)
