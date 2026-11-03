"""Mechanistic, manually specified weight edits; no optimization or training."""
import argparse, hashlib, io, json, zipfile
import numpy as np
import torch
from scipy.ndimage import gaussian_filter1d
from evaluate import ROOT, BASE, load_state

OUT=ROOT/'artifacts/ultra'
def save(s,name,hypothesis):
    before=load_state(BASE)
    assert all(torch.equal(before[k],v) for k,v in s.items() if 'value' in k or k=='log_std')
    assert all(torch.isfinite(v).all() for v in s.values())
    OUT.mkdir(exist_ok=True,parents=True); path=OUT/f'{name}.zip'
    buffer=io.BytesIO();torch.save(s,buffer)
    with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info,buffer.getvalue() if info.filename=='policy.pth' else src.read(info.filename))
    counts={k:int((v!=before[k]).sum()) for k,v in s.items() if not torch.equal(v,before[k])}
    path.with_suffix('.json').write_text(json.dumps(dict(name=name,hypothesis=hypothesis,
        source_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        changed=counts,changed_total=sum(counts.values()),method='direct analytic edits, no fitting/training/search',
        inference_only=True),indent=2)+'\n')
    print(path,counts)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('variant',choices=['angular_smooth','soft_gates','panic_gate','wall_panic','wall_panic_fast'])
    a=p.parse_args();s=load_state(BASE)
    if a.variant=='wall_panic_fast':
        s=load_state(OUT/'wall_panic.zip')
        s['action_net.bias'][1]+=.2/12.5
        hypothesis='Retain the specific near-left-wall panic correction; test a smaller .2m/s longitudinal bias increase without the global steering gain that previously regressed. No other tensors changed relative to wall_panic.'
    elif a.variant=='angular_smooth':
        w=s['mlp_extractor.policy_net.0.weight'].numpy()
        s['mlp_extractor.policy_net.0.weight']=torch.tensor(gaussian_filter1d(w,2.,axis=1,mode='reflect'))
        hypothesis='Bake a 0.5-degree angular Gaussian low-pass into first-layer weights. Preserve DC sums and reject unstructured high-frequency beam sensitivity; no external sensor preprocessing.'
    elif a.variant=='soft_gates':
        for i in [1,14,41,61]:
            s['mlp_extractor.policy_net.0.weight'][i]*=.5
            s['mlp_extractor.policy_net.0.bias'][i]*=.5
        hypothesis='Four active first-layer tanh gates flip in panic steering transients. Halve their preactivation slope while retaining decision hyperplanes, all downstream weights and all other units.'
    else:
        w1,b1=s['mlp_extractor.policy_net.0.weight'],s['mlp_extractor.policy_net.0.bias']
        w2,b2=s['mlp_extractor.policy_net.2.weight'],s['mlp_extractor.policy_net.2.bias']
        wo,bo=s['action_net.weight'],s['action_net.bias']
        bo-=wo[:,1];wo[:,1]=0.
        if a.variant=='wall_panic':
            b2+=w2[:,15];w2[:,15]=0.
            w1[15,:]=0.;w1[15,880:920]=-15./(.05*40.);b1[15]=(.4-15.)/.05
        w2[1,:]=0.;w2[1,41]=4.;w2[1,61]=-4.
        w2[1,14 if a.variant=='panic_gate' else 15]=4.;b2[1]=-8.
        wo[0,1]=-.35;bo[0]-=.35
        hypothesis=('Logical AND of h41+,h14+,h61- predicts rare saturated positive steering. Attenuate excessive branch by at most .7 normalized, using an existing near-constant second-layer unit. Threshold2 is the midpoint of boolean true3 vs false<=1.' if a.variant=='panic_gate' else
          'Constrain saturation attenuation to near-left-wall states: h41+,h61- AND mean left90deg clearance below .4m (half-width .155m plus .245m clearance). Preserve hard steering elsewhere. No fitting.')
    save(s,a.variant,hypothesis)
