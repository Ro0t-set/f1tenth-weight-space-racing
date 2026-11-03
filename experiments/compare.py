"""Paired outcomes and lap times; failures never become fake fast laps."""
import argparse
import json
from pathlib import Path
import numpy as np

def compare(base_path, edit_path):
    b = json.loads(Path(base_path).read_text())
    e = json.loads(Path(edit_path).read_text())
    assert b['protocol'] == e['protocol'] and b['max_steps'] == e['max_steps']
    index = lambda rows: {(r['map'],r['seed']): r for r in rows}
    bi,ei = index(b['rows']),index(e['rows'])
    assert bi.keys() == ei.keys()
    pairs = [(bi[k],ei[k]) for k in sorted(bi)]
    assert all(x['start'] == y['start'] for x,y in pairs)
    both = [(x,y) for x,y in pairs if x['success'] and y['success']]
    deltas = np.array([(y['seconds']/x['seconds']-1)*100 for x,y in both])
    maps = sorted({x['map'] for x,y in pairs})
    per_map = []
    for m in maps:
        ps = [(x,y) for x,y in pairs if x['map']==m]
        ds = [(y['seconds']/x['seconds']-1)*100 for x,y in ps if x['success'] and y['success']]
        per_map.append(dict(map=m, episodes=len(ps), baseline_success=sum(x['success'] for x,y in ps),
                            edited_success=sum(y['success'] for x,y in ps), paired_success=len(ds),
                            paired_lap_change_pct=float(np.mean(ds)) if ds else None))
    # Cluster resample at map level, acknowledging starts within a map are correlated.
    map_deltas = [r['paired_lap_change_pct'] for r in per_map if r['paired_success']]
    rng = np.random.default_rng(20261103)
    ci = np.quantile(np.mean(rng.choice(map_deltas,size=(10000,len(map_deltas)),replace=True),axis=1),[.025,.975]).tolist() if map_deltas else None
    return dict(episodes=len(pairs), maps=len(maps),
                baseline_success=sum(x['success'] for x,y in pairs),
                edited_success=sum(y['success'] for x,y in pairs),
                baseline_collisions=sum(x['collision'] for x,y in pairs),
                edited_collisions=sum(y['collision'] for x,y in pairs),
                baseline_timeouts=sum(x['timeout'] for x,y in pairs),
                edited_timeouts=sum(y['timeout'] for x,y in pairs),
                gained=[[x['map'],x['seed']] for x,y in pairs if not x['success'] and y['success']],
                lost=[[x['map'],x['seed']] for x,y in pairs if x['success'] and not y['success']],
                paired_success=len(both), mean_paired_lap_change_pct=float(deltas.mean()) if len(deltas) else None,
                map_mean_change_bootstrap95=ci, per_map=per_map)

if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('baseline');ap.add_argument('edited');ap.add_argument('--out')
    a=ap.parse_args();result=compare(a.baseline,a.edited)
    text=json.dumps(result,indent=2)
    if a.out: Path(a.out).write_text(text+'\n')
    print(text)
