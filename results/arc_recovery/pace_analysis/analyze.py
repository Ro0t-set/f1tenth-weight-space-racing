"""Compare old paired development successes using spatially nearest PPO samples."""
from pathlib import Path
import json
from collections import Counter
import numpy as np
import torch
from scipy.spatial import cKDTree

out = Path(__file__).resolve().parent
root = out.parents[2]
arc = root / 'results/from_scratch/development_arc_dynamic'
ppo = root / 'results/trajectory_v4/development_early_smooth'
original = root / 'artifacts/from_scratch/arc_dynamic'
def rows(path):
    return {(r['map'], r['seed']): r for r in json.loads(path.with_suffix('.json').read_text())['rows']}
def trace(path,key):
    return np.load(path.parent / f'{path.name}_{key[0]}_{key[1]}_trace.npz')
b = {k:v.numpy() for k,v in torch.jit.load(str(original.with_suffix('.pt'))).state_dict().items()}
curv = np.array(json.loads(original.with_suffix('.json').read_text())['curvature'])
data = []
paths = []
arc_rows, ppo_rows = rows(arc), rows(ppo)
for key, row in arc_rows.items():
    if not row['success'] or not ppo_rows[key]['success']:
        continue
    a,p = trace(arc,key), trace(ppo,key)
    ast, pst = a['states'],p['states']
    ds = lambda s: np.linalg.norm(np.diff(s[:,:2],axis=0),axis=1).sum()
    paths.append((ds(ast),ds(pst),row['seconds'],ppo_rows[key]['seconds']))
    da, ix = cKDTree(pst[:,:2]).query(ast[:,:2])
    for i in range(0, len(ast), 64):
        sl = slice(i,min(i+64,len(ast)))
        sector = (a['obs'][sl].reshape(-1,180,6).min(-1)+1)*15.
        violation = (b['envelope'][None,:,:,:]-sector[:,None,None,:]).max(-1).clip(0)
        feasible = (1.-violation/.04).clip(0)*b['valid']
        free = (feasible*b['delta_h']).sum(-1)
        w = (free-b['prior']).argmax(-1)
        h = free[np.arange(len(w)),w]
        k = np.abs(curv[w])
        caps = np.stack([np.full_like(h,10.),np.sqrt(12.*(h-.25).clip(0)),np.sqrt(7./k.clip(.001))],axis=1)
        command = a['actions'][sl,1]*12.5+7.5
        pc = p['actions'][ix[sl],1]*12.5+7.5
        v = ast[sl,3]
        pv = pst[ix[sl],3]
        data.extend(zip(caps.argmin(-1),h,k,command,pc,v,pv,da[sl]))
x = np.array(data); paths = np.array(paths)
def mean(a): return float(np.mean(a))
summary = {'pairs':len(paths),'poses':len(x),'maps_used':sorted(set(key[0] for key,r in arc_rows.items() if r['success'] and ppo_rows[key]['success'])), 'mean_path_delta_pct':mean(100*(paths[:,0]/paths[:,1]-1)), 'mean_time_delta_pct':mean(100*(paths[:,2]/paths[:,3]-1)), 'nearest_pose_separation_m_p50_p95':np.quantile(x[:,7],[.5,.95]).tolist()}
for label, column, values in [('cap',0,range(3)),('horizon',1,[0.,.5,1.,1.5,2.,3.,4.5,6.,8.,11.]),('curvature',2,np.unique(np.abs(curv)))]:
    bins={}
    for val in values:
        y=x[np.isclose(x[:,column],val)]
        if len(y):
            bins[str(val)]=[round(100*len(y)/len(x),2),round(mean(y[:,3]),2),round(mean(y[:,4]),2),round(mean(y[:,5]),2),round(mean(y[:,6]),2)]
    summary[label]=bins
summary['cap_labels']=['top','stop','lateral']
summary['binned_columns']=['pct_of_arc_poses','arc_command','nearest_ppo_command','arc_speed','nearest_ppo_speed']
print(json.dumps(summary,indent=2))
(out/'development.json').write_text(json.dumps(summary,indent=2)+'\n')
