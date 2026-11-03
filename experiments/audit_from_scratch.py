"""Independent size/equivalence/symmetry/latency audit; no rollouts or fitting."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter_ns
import numpy as np
import torch
from from_scratch import ArcNetwork, ScriptPolicy, ROOT


def synthetic():
    angles=np.linspace(-2.35,2.35,1080)
    def corridor(left,right,front):
        distance=np.full(1080,30.)
        for wall,direction in ((left,np.sin(angles)),(right,-np.sin(angles)),(front,np.cos(angles))):
            distance=np.minimum(distance,np.divide(wall,direction,out=np.full(1080,np.inf),where=direction>1e-12))
        return (distance/15.-1.).astype(np.float32)
    cases={'free':np.ones(1080,np.float32),'symmetric_1m_front30m':corridor(1,1,30),
           'symmetric_1m_front5m':corridor(1,1,5),'offset_035_165_front30m':corridor(.35,1.65,30),
           'offset_07_13_front5m':corridor(.7,1.3,5)}
    obstacle=corridor(1,1,30);obstacle[600:660]=np.minimum(obstacle[600:660],2./15.-1.)
    cases['offcenter_obstacle']=obstacle
    # Additional structural counterexamples test the explicit symmetry claim,
    # not a search over controller coefficients or simulated racing outcomes.
    cases['tie_stress_symmetric_10m_front5m']=corridor(10,10,5)
    cases['tie_stress_symmetric_3m_front3m']=corridor(3,3,3)
    return cases


def latency(function,inputs):
    for i in range(128): function(inputs[i%len(inputs)])
    blocks=[]
    for _ in range(5):
        times=[]
        for i in range(1000):
            start=perf_counter_ns();function(inputs[i%len(inputs)]);times.append((perf_counter_ns()-start)/1000.)
        blocks.append(times)
    values=np.asarray(blocks)
    return dict(calls=5000,warmup=128,p50_us=float(np.median(values)),p95_us=float(np.quantile(values,.95)),
                block_median_us=np.median(values,axis=1).tolist())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--name',default='arc_mode',choices=['arc_soft','arc_mode','arc_dynamic','arc_dynamic_pace'],
                    help='Artifact basename without .pt; defaults to the original arc_mode audit')
    args=ap.parse_args()
    torch.set_num_threads(1);torch.set_grad_enabled(False)
    path=ROOT/f'artifacts/from_scratch/{args.name}.pt';source=ROOT/'experiments/from_scratch.py'
    original_hash=hashlib.sha256(path.read_bytes()).hexdigest();source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    meta=json.loads(path.with_suffix('.json').read_text())
    assert meta['sha256']==original_hash,'Manifest and artifact hashes differ'
    policy=ScriptPolicy(path);scripted=policy.model
    state=torch.load(path.with_name(f'{args.name}_weights.pth'),map_location='cpu',weights_only=True)
    eager=ArcNetwork(state['envelope'],state['valid'],np.asarray(meta['horizons']),np.asarray(meta['curvature']),
        state['knots'],state['speed_slopes'],state['steer_slopes'],state['speed_base'],state['steer_base'],bool(scripted.mode_local)).eval()
    eager.load_state_dict(state,strict=True)
    tensors=[];storages={}
    for name,value in scripted.state_dict().items():
        storage=value.untyped_storage(); key=(storage.data_ptr(),storage.nbytes())
        storages.setdefault(key,[]).append(name)
        tensors.append(dict(name=name,shape=list(value.shape),dtype=str(value.dtype),dense_elements=value.numel(),nonzero_elements=int(torch.count_nonzero(value)),bytes=value.numel()*value.element_size()))
        assert torch.equal(value,state[name])
    examples=synthetic();mirror=[]
    for name,scan in examples.items():
        y=policy.predict(scan)[0];reflected=policy.predict(scan[::-1].copy())[0]
        residual=np.abs(y-reflected*np.array([-1.,1.]))
        mirror.append(dict(case=name,action=y.tolist(),mirrored_action=reflected.tolist(),steering_residual=float(residual[0]),speed_residual=float(residual[1]),passes_tolerance_2e_6=bool(residual.max()<2e-6)))
    with np.load(ROOT/'results/ultra/development_wall_panic_fast_Budapest_1101_trace.npz') as data:
        observed=data['obs'].copy()
    inputs=np.concatenate([observed,np.stack(list(examples.values())),np.stack([a[::-1].copy() for a in examples.values()])])
    tensor=torch.from_numpy(inputs)
    direct=eager(tensor).numpy();export=scripted(tensor).numpy();adapter=policy.predict(inputs)[0]
    assert direct.shape==(len(inputs),2) and np.isfinite(direct).all() and np.abs(direct).max()<=1
    equivalence=dict(observations=len(inputs),max_eager_script_difference=float(np.abs(direct-export).max()),
                     max_script_adapter_difference=float(np.abs(export-adapter).max()),
                     max_batch_single_difference=float(max(np.abs(policy.predict(scan)[0]-adapter[i]).max() for i,scan in enumerate(inputs))))
    from evaluate import load_policy,load_state
    previous_path=ROOT/'artifacts/trajectory_v4/early_smooth.zip'
    previous=load_policy(previous_path);previous_state=load_state(previous_path)
    old_actor={k:v for k,v in previous_state.items() if k.startswith('mlp_extractor.policy_net.') or k.startswith('action_net.')}
    sample=[x.copy() for x in inputs[:128]];raw=[torch.from_numpy(x[None,:]) for x in sample]
    timings=dict(arc_predict=latency(lambda x:policy.predict(x),sample),ppo_predict=latency(lambda x:previous.predict(x,deterministic=True),sample),
                 arc_raw=latency(scripted,raw),ppo_raw_actor=latency(lambda x:previous._predict(x,deterministic=True),raw))
    result=dict(artifact=str(path),artifact_sha256=original_hash,source_sha256=source_hash,
        explicit_origin='All stored tensors are analytically generated in compiler; no learned PPO tensors, optimizer, training, fitting or random initialization are used.',
        size=dict(registered_parameter_elements=sum(x.numel() for x in scripted.parameters()),
            registered_buffer_elements=sum(x.numel() for x in scripted.buffers()),
            dense_stored_elements=sum(x['dense_elements'] for x in tensors),nonzero_stored_elements=sum(x['nonzero_elements'] for x in tensors),
            stored_tensor_bytes=sum(x['bytes'] for x in tensors),unique_storage_bytes=sum(k[1] for k in storages),
            storage_aliases=[names for names in storages.values() if len(names)>1],script_file_bytes=path.stat().st_size,
            ppo_actor_mean_elements=sum(v.numel() for v in old_actor.values()),ppo_log_std_elements=previous_state['log_std'].numel(),
            ppo_full_checkpoint_tensor_elements=sum(v.numel() for v in previous_state.values()),ppo_zip_file_bytes=previous_path.stat().st_size,
            interpretation='Zero trainable parameters does not mean zero weights: coefficients are persistent buffers. Stored elements, nonzeros and independent design constants are distinct. Formula construction ties geometric coefficients; stored tensor elements are not independent learned degrees of freedom. No fully expanded dense1080-to-geometry matrix is stored.',
            uncounted_architecture_literals=['LiDAR/action normalization constants','pool6/stride6','feasibility width0.04','softmax temperature0.15','mode-local boolean and argmax tie convention']),
        tensors=tensors,equivalence=equivalence,synthetic_mirror=mirror,latency=timings,
        findings=[('Mirror symmetry fails on one or more synthetic cases. For local mode selection, argmax resolves exact ties toward the lowest index; symmetric scenes can produce nonzero steering.' if any(not r['passes_tolerance_2e_6'] for r in mirror) else 'Mirror symmetry passes the finite synthetic cases tested; this is not a proof over every observation.'),
                  'A smaller coefficient count is not itself a guarantee of lower latency: 17x9x180 envelope comparisons/reductions are evaluated each call.',
                  'Current velocity/slip are absent from observation; compiled steady-state steering and braking schedules are approximations, not dynamic guarantees.',
                  'Runtime is a tensor geometric controller with analytically compiled coefficients, not a newly trained RL model.'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==original_hash,'Artifact changed during audit'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash,'Source changed during audit'
    out=ROOT/'results/from_scratch_audit';out.mkdir(parents=True,exist_ok=True)
    (out/f'{args.name}_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('artifact_sha256','size','equivalence','synthetic_mirror','latency')},indent=2))


if __name__=='__main__':main()
