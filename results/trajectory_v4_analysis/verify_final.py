"""Frozen holdout audit independent of reporting script; no checkpoint mutation."""
import json,hashlib,time,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];folder=ROOT/'results/trajectory_v4'
for _ in range(600):
 if all((folder/f'final_{n}.json').exists() for n in ['previous','candidate']):break
 time.sleep(1)
else:raise SystemExit('Final payloads not both complete after 600 seconds')
manifest=json.loads((folder/'holdout_manifest.json').read_text());payload={n:json.loads((folder/f'final_{n}.json').read_text()) for n in ['previous','candidate']}
expected={(m,s) for m in manifest['maps'] for s in manifest['seeds']}
assert len(expected)==210
indices={}
for n,p in payload.items():
 frozen=manifest['checkpoints'][n];assert p['sha256']==frozen['sha256']==hashlib.sha256((ROOT/frozen['path']).read_bytes()).hexdigest()
 assert Path(p['checkpoint']).resolve()==(ROOT/frozen['path']).resolve()
 assert len(p['rows'])==210
 indices[n]={(r['map'],r['seed']):r for r in p['rows']};assert set(indices[n])==expected
 assert all(r['success']+r['collision']+r['timeout']==1 for r in p['rows'])
 assert all(not r['success'] or r['progress']>=.99 for r in p['rows'])
 assert all(abs(r['seconds']-.01*r['steps'])<1e-10 for r in p['rows'])
assert payload['previous']['protocol']==payload['candidate']['protocol']
assert payload['previous']['max_steps']==payload['candidate']['max_steps']
pairs=[(indices['previous'][k],indices['candidate'][k]) for k in sorted(expected)]
assert all(a['start']==b['start'] for a,b in pairs)
both=[(a,b) for a,b in pairs if a['success'] and b['success']]
deltas=np.array([100*(b['seconds']/a['seconds']-1) for a,b in both])
gained=[[a['map'],a['seed']] for a,b in pairs if not a['success'] and b['success']]
lost=[[a['map'],a['seed']] for a,b in pairs if a['success'] and not b['success']]
per_map=[]
for m in manifest['maps']:
 ps=[(a,b) for a,b in pairs if a['map']==m];ds=[100*(b['seconds']/a['seconds']-1) for a,b in ps if a['success'] and b['success']]
 per_map.append({'map':m,'previous_successes':sum(a['success'] for a,b in ps),'candidate_successes':sum(b['success'] for a,b in ps),'paired_successes':len(ds),'paired_lap_change_pct':float(np.mean(ds)) if ds else None})
counts={n:{'successes':sum(r['success'] for r in p['rows']),'collisions':sum(r['collision'] for r in p['rows']),'timeouts':sum(r['timeout'] for r in p['rows']),'collisions_first_0p1_seconds':sum(r['collision'] and r['seconds']<=.1 for r in p['rows'])} for n,p in payload.items()}
# Also cross-check independently recomputed figures against the shared comparison helper.
sys.path.insert(0,str(ROOT/'experiments'));from compare import compare
comparison=compare(folder/'final_previous.json',folder/'final_candidate.json')
assert comparison['paired_success']==len(both)
assert comparison['gained']==gained and comparison['lost']==lost
assert abs(comparison['mean_paired_lap_change_pct']-float(deltas.mean()))<1e-12
for mine,theirs in zip(sorted(per_map,key=lambda r:r['map']),comparison['per_map']):
 assert mine['map']==theirs['map'] and mine['previous_successes']==theirs['baseline_success'] and mine['candidate_successes']==theirs['edited_success']
 assert mine['paired_lap_change_pct']==theirs['paired_lap_change_pct']
# Development and holdout starts are disjoint by seed, while maps intentionally overlap.
devseeds=set()
for path in [ROOT/'results/ultra/final_fast.json',folder/'expanded_early_smooth.json',folder/'development_early_smooth.json']:
 devseeds.update(r['seed'] for r in json.loads(path.read_text())['rows'])
assert not devseeds.intersection(manifest['seeds'])
result={'episodes_per_model':210,'all_manifest_pairs_present_once':True,'all_paired_start_poses_exact':True,'frozen_checkpoint_hashes_match':True,'protocol_max_steps_match':True,'shared_comparator_agrees':True,'new_seeds_disjoint_from_documented_development':True,'counts':counts,'gained':gained,'lost':lost,'paired_completed_count':len(both),'mean_paired_lap_change_pct':float(deltas.mean()),'median_paired_lap_change_pct':float(np.median(deltas)),'paired_lap_change_min_max_pct':[float(deltas.min()),float(deltas.max())],'mean_paired_lap_change_seconds':float(np.mean([b['seconds']-a['seconds'] for a,b in both])),'map_mean_bootstrap_interval_reported':comparison['map_mean_change_bootstrap95'],'per_map':per_map,'early_collisions_included_in_denominator':True,'limitations':['Same21 maps; new starts, not unseen tracks.','Successful paired lap-time analysis excludes crashes from time, but crash totals retain all210.','Bootstrap interval describes unweighted map means; headline is episode-weighted paired mean.']}
(ROOT/'results/trajectory_v4_analysis/final_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
