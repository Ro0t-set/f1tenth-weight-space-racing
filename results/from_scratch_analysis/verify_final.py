"""Independent frozen final audit; no inference, tuning or checkpoint mutation."""
import hashlib,json,time,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];folder=ROOT/'results/from_scratch'
for _ in range(1200):
 if all((folder/f'final_{n}.json').exists() for n in ['previous','candidate']):break
 time.sleep(1)
else:raise SystemExit('Both final payloads were not ready within1200s')
manifest=json.loads((folder/'holdout_manifest.json').read_text())
payload={n:json.loads((folder/f'final_{n}.json').read_text()) for n in ['previous','candidate']}
expected={(m,s) for m in manifest['maps'] for s in manifest['seeds']};assert len(expected)==105
for path,sha in manifest['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
indices={}
for n,p in payload.items():
 frozen=manifest['checkpoints'][n]
 assert p['sha256']==frozen['sha256']==hashlib.sha256((ROOT/frozen['path']).read_bytes()).hexdigest()
 assert Path(p['checkpoint']).resolve()==(ROOT/frozen['path']).resolve()
 assert len(p['rows'])==105
 indices[n]={(r['map'],r['seed']):r for r in p['rows']};assert set(indices[n])==expected
 assert all(r['success']+r['collision']+r['timeout']==1 for r in p['rows'])
 assert all(not r['success'] or r['progress']>=.99 for r in p['rows'])
 assert all(abs(r['seconds']-.01*r['steps'])<1e-10 for r in p['rows'])
assert payload['previous']['protocol']==payload['candidate']['protocol']
assert payload['previous']['max_steps']==payload['candidate']['max_steps']
pairs=[(indices['previous'][k],indices['candidate'][k]) for k in sorted(expected)]
assert all(a['start']==b['start'] for a,b in pairs)
unseen=set(manifest['maps_not_used_for_new_network_development_rollouts']);dev=set(manifest['development_maps'])
assert len(unseen)==14 and len(dev)==7 and not unseen.intersection(dev) and unseen.union(dev)==set(manifest['maps'])
actual_dev_maps=set(); actual_dev_seeds=set()
for path in list(folder.glob('smoke_*.json'))+list(folder.glob('development_arc*.json')):
 d=json.loads(path.read_text())
 actual_dev_maps.update(r['map'] for r in d['rows']);actual_dev_seeds.update(r['seed'] for r in d['rows'])
assert actual_dev_maps==dev
assert not actual_dev_seeds.intersection(manifest['seeds'])
def summarize(ps):
 both=[(a,b) for a,b in ps if a['success'] and b['success']]
 ds=np.array([100*(b['seconds']/a['seconds']-1) for a,b in both])
 counts={}
 for key,idx in [('previous',0),('candidate',1)]:
  rr=[p[idx] for p in ps]
  counts[key]={'successes':sum(r['success'] for r in rr),'collisions':sum(r['collision'] for r in rr),'timeouts':sum(r['timeout'] for r in rr),'collisions_first_0p1s':sum(r['collision'] and r['seconds']<=.1 for r in rr),'timeout_episodes':[[r['map'],r['seed'],r['progress']] for r in rr if r['timeout']]}
 return {'episodes_per_model':len(ps),'counts':counts,'gained':[[a['map'],a['seed']] for a,b in ps if not a['success'] and b['success']],'lost':[[a['map'],a['seed']] for a,b in ps if a['success'] and not b['success']],'paired_completed_count':len(both),'mean_paired_lap_change_pct':float(ds.mean()) if len(ds) else None,'median_paired_lap_change_pct':float(np.median(ds)) if len(ds) else None,'mean_paired_lap_change_seconds':float(np.mean([b['seconds']-a['seconds'] for a,b in both])) if both else None,'paired_lap_change_min_max_pct':[float(ds.min()),float(ds.max())] if len(ds) else None}
overall=summarize(pairs);per_map={m:summarize([(a,b) for a,b in pairs if a['map']==m]) for m in manifest['maps']}
sys.path.insert(0,str(ROOT/'experiments'));from compare import compare
cmp=compare(folder/'final_previous.json',folder/'final_candidate.json')
assert cmp['paired_success']==overall['paired_completed_count']
assert cmp['gained']==overall['gained'] and cmp['lost']==overall['lost']
assert abs(cmp['mean_paired_lap_change_pct']-overall['mean_paired_lap_change_pct'])<1e-12
result={'all_manifest_pairs_present_once':True,'all_initial_poses_exactly_paired':True,'frozen_checkpoint_and_source_hashes_match':True,'protocol_max_steps_match':True,'shared_comparator_agrees':True,'new_seeds_disjoint_from_new_network_development':True,'development_map_partition_verified_against_all_saved_smoke_development_rollouts':True,'overall':overall,'14_maps_not_used_for_new_network_development':summarize([(a,b) for a,b in pairs if a['map'] in unseen]),'7_maps_used_for_new_network_development':summarize([(a,b) for a,b in pairs if a['map'] in dev]),'per_map':per_map,'timeouts_and_initial_collisions_included_in_denominator':True,'generality_scope':'The14 maps were not used for development rollouts of the NEW network. They are known from earlier project phases and are not globally unseen tracks. The105 map/seed pairs use new seeds; physical start-pose uniqueness against the entire project history is not asserted.'}
(ROOT/'results/from_scratch_analysis/final_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='per_map'},indent=2))
