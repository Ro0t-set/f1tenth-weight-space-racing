"""Reverse sampled SAT audit of historical overlapping starts, no rollout."""
import json,sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root/'experiments'))
from trajectory_audit import Geometry,HALF
out=Path(__file__).resolve().parent
ks=json.loads((root/'artifacts/from_scratch/arc_dynamic.json').read_text())['curvature']
def pose(st,k,s):
    y=st[2]+k*s
    d=np.array([np.sin(y)-np.sin(st[2]),np.cos(st[2])-np.cos(y)])/k if k else s*np.array([np.cos(y),np.sin(y)])
    return np.r_[st[:2]+d,y]
def mat(y):
    return np.array([[np.cos(y),-np.sin(y)],[np.sin(y),np.cos(y)]])
def sep(st):
    R=mat(st[2]); rel=points-st[:2]; h=g.res/2
    return np.max(np.c_[np.abs(rel)-(np.abs(R)@HALF+h),np.abs(rel@R)-(HALF+h*np.abs(R).sum(axis=0))],axis=1).min()
def fov(k,L):
    # Area in the radial envelope (including any pockets behind it). The
    # ray samples also resolve sub-millimetre slivers at the front corners.
    angles=np.linspace(-np.pi,np.pi,7200,endpoint=False)
    rays=np.c_[np.cos(angles),np.sin(angles)]
    swept=np.zeros(len(angles))
    for s in np.linspace(0,L,max(2,round(L/.002)+1)):
        p=pose(np.zeros(3),k,-s); R=mat(p[2])
        o=-p[:2]@R; v=rays@R
        v[np.abs(v)<1e-12]=1e-12
        t0=(-HALF-o)/v; t1=(HALF-o)/v
        hi=np.maximum(t0,t1).min(axis=1)
        lo=np.minimum(t0,t1).max(axis=1)
        swept=np.maximum(swept,np.where(hi>=np.maximum(lo,0),hi,0.))
        if s==0: initial=swept.copy()
    area=swept**2-initial**2
    return float(area[np.abs(angles)>2.35].sum()/area.sum())
rows=[]
for row in json.loads((out.parent/'initial_geometry.json').read_text()):
    if row['body_clearance']>0:continue
    n,seed=row['map'],row['seed'];g=Geometry(n)
    v=np.load(out.parent/f'initial_{n}_{seed}.npz')['state'];st=v[[0,1,4]];points=g.occupied_centers[g.tree.query_ball_point(st[:2],2.35)]
    ss=np.arange(0,1.0001,.002);opts=[]
    for k in ks:
        states=np.array([pose(st,k,-s) for s in ss]); d=np.array([sep(p) for p in states]);clear=np.flatnonzero(d>1e-10)
        if not len(clear):continue
        i=clear[0];j=i+75
        if j>=len(d) or np.any(d[i:j+1]<=1e-10) or np.any(np.diff(np.minimum(d[:i+1],0))< -1e-10):continue
        p=states[j]; co=g.project(np.stack([st[:2],p[:2]]))[0]; forward=[]
        for q in ks:
            ps=np.array([pose(p,q,s) for s in np.arange(0,.7501,.01)])
            if all(sep(u)>1e-10 for u in ps):
                off=g.project(ps[[-1],:2])[0][0]; forward.append([q,round(float(abs(off)-abs(co[0])),4)])
        opts.append(dict(k=k,first_clear_m=round(float(ss[i]),3),reverse_stop_m=round(float(ss[j]),3),blind_new_area_fraction=fov(k,ss[j]),released_clearance_m=g.clearance(p[:2],p[2],False),closest_centerline_change_m=float(abs(co[1])-abs(co[0])),forward_075m_options_raceline_abs_offset_change=forward))
    rows.append(dict(map=n,seed=seed,initial_depth_m=-sep(st),choices=opts))
    print(n,seed,[(r['k'],r['first_clear_m'],round(r['blind_new_area_fraction'],2),len(r['forward_075m_options_raceline_abs_offset_change'])) for r in opts],flush=True)
(out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
