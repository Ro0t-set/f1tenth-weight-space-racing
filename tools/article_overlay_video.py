"""Three synchronized recorded controllers on the same Sochi start."""
import argparse,gzip,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
from article_trajectory_video import ROOT, OUT, render

def extract(workspace):
    import yaml
    folder=workspace/'upstream/map/f1tenth_racetracks/Sochi'
    meta=yaml.safe_load((folder/'Sochi_map.yaml').read_text())
    data=dict(map='Sochi',seed=73101,stem='trajectory-overlay',map_file='trajectory-overlay-map.png',
              map_origin=meta['origin'][:2],resolution=meta['resolution'],runs={},
              titles={'it':'Tre reti, la stessa partenza','en':'Three networks, the same start'},
              source='https://github.com/f1tenth/f1tenth_racetracks/tree/3f581789c749261ae36fc4fef19a81372acc3ecf/Sochi')
    Image.open(folder/'Sochi_map.png').convert('L').save(OUT/data['map_file'])
    for name,prefix in [('original','video/original_sochi'),('edited','arc_recovery/locked/final_ppo'),('scratch','arc_recovery/locked/final_candidate')]:
        ledger=workspace/f'results/{prefix}.json'
        payload=json.loads(ledger.read_text())
        row=next(r for r in payload['rows'] if r['map']=='Sochi' and r['seed']==73101)
        trace=ledger.with_name(ledger.stem+'_Sochi_73101_trace.npz')
        with np.load(trace) as z:
            states=z['states'][::10];times=z['steps'][::10]*.01
        data['runs'][name]=dict(times=times.tolist(),states=np.round(states,8).tolist(),seconds=row['seconds'],
            success=row['success'],collision=row['collision'],checkpoint_sha256=payload['sha256'],
            trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest())
    assert all(np.allclose(r['states'][0],data['runs']['original']['states'][0],atol=1e-7) for r in data['runs'].values())
    (OUT/'overlay-animation.json.gz').write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))
    print({k:(v['seconds'],v['success']) for k,v in data['runs'].items()})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path);args=parser.parse_args()
    if args.workspace:extract(args.workspace)
    data=json.loads(gzip.decompress((OUT/'overlay-animation.json.gz').read_bytes()))
    for lang in ('it','en'):render(data,lang,'lap')
