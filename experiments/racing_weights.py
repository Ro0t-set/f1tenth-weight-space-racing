"""Reasoned weight-space programs. No fitting, gradients, optimizer or search loop."""
import argparse
import hashlib
import io
import json
import zipfile
import numpy as np
import torch
from evaluate import ROOT, BASE, load_state, load_policy

DEST=ROOT/'artifacts/racing_v2'

def save(state, name, specification):
    before=load_state(BASE)
    assert all(torch.equal(v,before[k]) for k,v in state.items() if 'value' in k or k=='log_std')
    assert all(torch.isfinite(v).all() for v in state.values())
    path=DEST/f'{name}.zip'
    data=io.BytesIO();torch.save(state,data)
    with zipfile.ZipFile(BASE) as src, zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item,data.getvalue() if item.filename=='policy.pth' else src.read(item.filename))
    changed={k:int((v!=before[k]).sum()) for k,v in state.items() if not torch.equal(v,before[k])}
    metadata=dict(source=str(BASE),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  specification=specification,changed=changed,changed_total=sum(changed.values()),
                  method='reasoned analytic edits; no training, fitting, gradient or automated search',
                  observation='original single 1080-ray lidar; no velocity, slip, yaw rate or memory',
                  inference_only=True)
    path.with_suffix('.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return path

def program_clearance():
    s=load_state(BASE)
    w1,b1=s['mlp_extractor.policy_net.0.weight'],s['mlp_extractor.policy_net.0.bias']
    w2,b2=s['mlp_extractor.policy_net.2.weight'],s['mlp_extractor.policy_net.2.bias']
    wo,bo=s['action_net.weight'],s['action_net.bias']
    # Reclaim two near-constant units, preserving their old steering contribution.
    b2 += w2[:,15]; w2[:,15]=0.
    bo -= wo[:,1]; wo[:,1]=0.
    # h1=tanh((mean_front_metres-8)/5); h2=tanh(h1).
    w1[15,:]=0.;w1[15,520:560]=15./(5.*40.);b1[15]=(15.-8.)/5.
    w2[1,:]=0.;w2[1,15]=1.;b2[1]=0.
    # Replace only longitudinal control: 4m/s tight turn .. 12.5m/s open straight.
    wo[1,:]=0.;wo[1,1]=4.25/(12.5*np.tanh(1.));bo[1]=(8.25-7.5)/12.5
    path=save(s,'clearance_speed',dict(
        formula='v_command=8.25+4.25*tanh(tanh((mean(d[520:560])-8)/5))/tanh(1)',
        rationale='Earlier substantial braking in tight corners, larger speed increase on open straights; original steering retained.',
        bounds_mps=[4.,12.5]))
    old,new=load_policy(BASE),load_policy(path)
    files=sorted((ROOT/'results/racing_v2').glob('development_baseline_*_trace.npz'))
    x=np.concatenate([np.load(f)['obs'] for f in files]);tx=torch.from_numpy(x)
    a=old.action_net(old.mlp_extractor.forward_actor(tx)).numpy()
    b=new.action_net(new.mlp_extractor.forward_actor(tx)).numpy()
    d=(x[:,520:560].mean(1)+1)*15
    expected=8.25+4.25*np.tanh(np.tanh((d-8)/5))/np.tanh(1.)
    error=float(np.max(np.abs(b[:,1]*12.5+7.5-expected)))
    steering_error=float(np.max(np.abs(b[:,0]-a[:,0])))
    assert error<1e-4,error
    assert steering_error<1e-4,steering_error
    print(json.dumps(dict(path=str(path),speed_formula_error=error,steering_error=steering_error)))

def program_two_gate():
    s=load_state(BASE)
    w1,b1=s['mlp_extractor.policy_net.0.weight'],s['mlp_extractor.policy_net.0.bias']
    w2,b2=s['mlp_extractor.policy_net.2.weight'],s['mlp_extractor.policy_net.2.bias']
    wo,bo=s['action_net.weight'],s['action_net.bias']
    # Constant contributions are moved before repurposing either circuit.
    for i in [15,0]:
        b2 += w2[:,i];w2[:,i]=0.
    for j in [1,14]:
        bo -= wo[:,j];wo[:,j]=0.
    for i,j,centre,width,amplitude in [(15,1,16.,4.,.4),(0,14,5.,2.,.8)]:
        w1[i,:]=0.;w1[i,520:560]=15./(width*40.);b1[i]=(15.-centre)/width
        w2[j,:]=0.;w2[j,i]=2.;b2[j]=0.
        wo[1,j]=amplitude/(12.5*np.tanh(2.))
    bo[1]+=(.4-.8)/12.5
    path=save(s,'two_gate',dict(
        formula='v_original + 0.4*(1+g(d;16,4)) - 0.8*(1-g(d;5,2)); g=tanh(2*tanh((d-centre)/width))/tanh(2)',
        rationale='Retain trained throttle/steering relationship. Boost up to .8m/s on open straight, brake up to 1.6m/s only at tight corners. No intervention in ordinary bends.',
        correction_bounds_mps=[-1.6,.8]))
    old,new=load_policy(BASE),load_policy(path)
    x=np.concatenate([np.load(f)['obs'] for f in sorted((ROOT/'results/racing_v2').glob('development_baseline_*_trace.npz'))])
    tx=torch.from_numpy(x)
    a=old.action_net(old.mlp_extractor.forward_actor(tx)).numpy()
    b=new.action_net(new.mlp_extractor.forward_actor(tx)).numpy()
    d=(x[:,520:560].mean(1)+1)*15
    g=lambda c,w:np.tanh(2*np.tanh((d-c)/w))/np.tanh(2)
    expected=.4*(1+g(16,4))-.8*(1-g(5,2))
    speed_error=float(np.max(np.abs((b[:,1]-a[:,1])*12.5-expected)))
    steering_error=float(np.max(np.abs(b[:,0]-a[:,0])))
    assert speed_error<.01,speed_error
    assert steering_error<.00025,steering_error
    print(json.dumps(dict(path=str(path),speed_formula_error=speed_error,steering_error=steering_error)))

def program_guard():
    s=load_state(DEST/'two_gate.zip')
    w1,b1=s['mlp_extractor.policy_net.0.weight'],s['mlp_extractor.policy_net.0.bias']
    w2,b2=s['mlp_extractor.policy_net.2.weight'],s['mlp_extractor.policy_net.2.bias']
    wo,bo=s['action_net.weight'],s['action_net.bias']
    for i in [62,32]:
        b2 -= w2[:,i];w2[:,i]=0.
    for j in [39,15]:
        bo += wo[:,j];wo[:,j]=0.
    # Read walls ahead, rather than at +/-90 degrees, to include heading error.
    # A 30-degree ray with distance 2m looks ~1.7m forward and 1m sideways.
    for i,j,lo,hi,sign in [(62,39,650,670,1.),(32,15,410,430,-1.)]:
        w1[i,:]=0.;w1[i,lo:hi]=15./(.6*(hi-lo));b1[i]=(15.-2.)/.6
        w2[j,:]=0.;w2[j,i]=2.;b2[j]=0.
        wo[0,j]=sign*.12/np.tanh(2.)
        wo[1,j]=.3/(12.5*np.tanh(2.))
    bo[1]-=.6/12.5
    path=save(s,'two_gate_guard',dict(
        parent='two_gate',
        formula='additional steer=.12*(g(left30deg;2,.6)-g(right30deg;2,.6)); additional v=-.3*(2-gL-gR)',
        rationale='Traces show heading toward wall at curve exit despite front clearance. Anticipatory diagonal wall repulsion acts before the original late saturated steering response.',
        steering_correction_bound_normalized=.24,extra_braking_bound_mps=1.2))
    print(path)

def program_exit_guard():
    s=load_state(DEST/'two_gate.zip')
    w1,b1=s['mlp_extractor.policy_net.0.weight'],s['mlp_extractor.policy_net.0.bias']
    w2,b2=s['mlp_extractor.policy_net.2.weight'],s['mlp_extractor.policy_net.2.bias']
    wo,bo=s['action_net.weight'],s['action_net.bias']
    for i,constant in [(62,-1.),(32,-1.),(49,1.)]:
        b2 += constant*w2[:,i];w2[:,i]=0.
    for j in [39,15]:
        bo += wo[:,j];wo[:,j]=0.
    for i,lo,hi,centre,width in [(62,880,920,.9,.25),(32,160,200,.9,.25),(49,520,560,8.,2.)]:
        w1[i,:]=0.;w1[i,lo:hi]=15./(width*(hi-lo));b1[i]=(15.-centre)/width
    for i,j,sign in [(62,39,-1.),(32,15,1.)]:
        # AND(open front, close side): neither feature alone triggers correction.
        w2[j,:]=0.;w2[j,49]=3.;w2[j,i]=-3.;b2[j]=-3.
        wo[0,j]=sign*.06
        wo[1,j]=-.25/12.5
    bo[1]-=.5/12.5
    path=save(s,'exit_guard',dict(parent='two_gate',
        formula='g_side=tanh(3*(front_open-side_far-1)); steer+=.06*(g_right-g_left); v-=.25*(2+g_right+g_left)',
        rationale='Unconditional diagonal guard opposed intended corner entry. Restrict small correction to open-front, near-side-wall exits; leave ordinary corners to learned steering.',
        steering_correction_bound_normalized=.12))
    print(path)

def program_geometric():
    s=load_state(BASE)
    for key in s:
        if 'policy_net' in key or 'action_net' in key:s[key].zero_()
    w1,b1=s['mlp_extractor.policy_net.0.weight'],s['mlp_extractor.policy_net.0.bias']
    w2,b2=s['mlp_extractor.policy_net.2.weight'],s['mlp_extractor.policy_net.2.bias']
    wo,bo=s['action_net.weight'],s['action_net.bias']
    # Approximate a centered lookahead point from +/-30deg wall distances.
    # The angle supplies heading feedback as well as lateral offset feedback.
    w1[0,650:670]=15./(6.*20.);w1[0,410:430]=-15./(6.*20.)
    w2[0,0]=1.;wo[0,0]=.6
    w1[1,520:560]=15./(4.*40.);b1[1]=(15.-6.)/4.
    w2[1,1]=1.;wo[1,1]=3./(12.5*np.tanh(1.))
    path=save(s,'geometric',dict(
        formula='steer=.6*tanh(tanh((d_left30-d_right30)/6)); v=7.5+3*tanh(tanh((d_front-6)/4))/tanh(1)',
        rationale='Diagnostic from-scratch neural program: equalize wall distances at a forward lookahead; no PPO throttle/steering coadaptation remains.',
        bounds_mps=[4.5,10.5],full_actor_rewrite=True))
    print(path)

def program_curvature():
    from f110_gym.envs.dynamic_models import vehicle_dynamics_st
    params=[1.0489,4.718,5.4562,.15875,.17145,.074,3.74,.04712,-.4189,.4189,-3.2,3.2,7.319,9.51,-5.,20.]
    def yaw_gain(v):
        x=np.zeros(7);x[3]=v
        def f(y):return vehicle_dynamics_st(y,np.zeros(2),*params)[5:7]
        xr=x.copy();xr[5]=1;xb=x.copy();xb[6]=1;xd=x.copy();xd[2]=1
        return -np.linalg.solve(np.c_[f(xr),f(xb)],f(xd))[0]
    nominal,boost=8.5,.3
    gain=(nominal+boost)/nominal*yaw_gain(nominal)/yaw_gain(nominal+boost)
    s=load_state(BASE)
    s['action_net.weight'][0]*=gain;s['action_net.bias'][0]*=gain
    s['action_net.bias'][1]+=boost/12.5
    path=save(s,'curvature_compensated',dict(
        formula='steer_new=gain*steer_original; v_new=v_original+0.3m/s (before action clipping)',
        steering_gain=float(gain),nominal_speed_mps=nominal,
        rationale='Large throttle edits destabilized load-transfer transients. Preserve learned throttle modulation and compensate the single-track steady-state curvature loss from a small speed increase. Gain derived from vehicle equations, not fitted.'))
    print(path,gain)

def program_straight_boost():
    # Keep the previous cautious circuit, including its steering, unchanged.
    # Only expand the positive end of its clearance-dependent speed correction.
    s=load_state(ROOT/'artifacts/clearance_cautious.zip')
    wo,bo=s['action_net.weight'],s['action_net.bias']
    # Original cautious delta=-.15+.45*g. New delta=.6+1.2*g.
    # Both approach -.6m/s in tight corners; positive endpoint becomes +1.8m/s.
    wo[1,1]=1.2/(12.5*np.tanh(2.))
    bo[1]+=.75/12.5
    path=save(s,'straight_boost',dict(
        parent='clearance_cautious',
        formula='v_original + .6 + 1.2*g; g=tanh(2*tanh((front_distance-15)/3))/tanh(2)',
        rationale='Uniform speed increase plus steering compensation failed safety. Preserve cautious corner endpoint and unchanged steering, allocate the entire speed increase to open straights.',
        correction_bounds_mps=[-.6,1.8]))
    print(path)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('variant',choices=['clearance_speed','two_gate','two_gate_guard','exit_guard','geometric','curvature_compensated','straight_boost'])
    args=ap.parse_args()
    if args.variant=='clearance_speed': program_clearance()
    elif args.variant=='two_gate': program_two_gate()
    elif args.variant=='two_gate_guard': program_guard()
    elif args.variant=='exit_guard': program_exit_guard()
    elif args.variant=='geometric': program_geometric()
    elif args.variant=='curvature_compensated': program_curvature()
    else: program_straight_boost()
