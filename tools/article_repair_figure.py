"""Draw the bilingual Budapest example from repair-data.json (Python 3 only).

Use --verify-weights PATH in the study environment to check both steering curves
from the included twelve normalized scans. PATH must contain the original and
rebuilt wall_panic checkpoints. To also repeat extraction, use --workspace PATH
with the two recorded development traces and pinned track checkout.
No environment is stepped and no parameters are fitted.
"""
import argparse
import gzip
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

from article_track_figure import ARC, INK, MAP_REPO, MAP_REV, MUTED, OUT, PPO, ROOT, WALL, path_data

RUNS = {'original': 'racing_v2/development_baseline', 'edited': 'ultra/development_wall_panic'}
CHECKPOINTS = {'original': 'upstream/train_test/best_global_model.zip',
               'edited': 'artifacts/ultra/wall_panic.zip'}
SCANS = OUT / 'repair-original-scans.npy.gz'


def predict(checkpoint, expected_digest, scans):
    import torch
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != expected_digest:
        raise ValueError(f'Checkpoint differs from the episode ledger: {checkpoint}')
    with zipfile.ZipFile(checkpoint) as archive:
        weights = torch.load(io.BytesIO(archive.read('policy.pth')), map_location='cpu', weights_only=True)
    # Two tanh layers and clipped mean action match deterministic SB3 prediction.
    torch.set_num_threads(1)
    with torch.inference_mode():
        y = torch.from_numpy(scans)
        for prefix in ['mlp_extractor.policy_net.0', 'mlp_extractor.policy_net.2', 'action_net']:
            y = torch.nn.functional.linear(y, weights[prefix+'.weight'], weights[prefix+'.bias'])
            if prefix != 'action_net':
                y = y.tanh()
        return y.clamp(-1, 1).numpy()


def extract(workspace):
    import numpy as np
    sys.path.insert(0, str(ROOT / 'experiments'))
    import trajectory_audit as audit
    maps = workspace / 'upstream/map/f1tenth_racetracks'
    audit.MAPS = maps
    g = audit.Geometry('Budapest')
    data = {'map': 'Budapest', 'seed': 1101, 'cohort': 'development',
            'map_source': f'{MAP_REPO}/tree/{MAP_REV}/Budapest', 'map_license': 'GPL-3.0',
            'map_sha256': hashlib.sha256((maps/'Budapest/Budapest_map.png').read_bytes()).hexdigest(),
            'cell_m': g.res, 'sample_seconds': .10, 'models': {}}
    results = workspace / 'results'
    for key, run in RUNS.items():
        trace = results / f'{run}_Budapest_1101_trace.npz'
        ledger = json.loads((results / f'{run}.json').read_text())
        episode = next(r for r in ledger['rows'] if r['map'] == 'Budapest' and r['seed'] == 1101)
        with np.load(trace) as z:
            if not np.all(np.diff(z['steps']) == 10):
                raise ValueError('Expected traces sampled every 10 simulator steps.')
            if key == 'original':
                scans = z['obs']
                steps = z['steps']
                recorded_actions = z['actions']
                last_pose = z['states'][-1, :2]
            mask = (z['steps'] >= 520) & (z['steps'] <= 720)
            samples = np.column_stack([z['steps'][mask], z['states'][mask, :2]])
        data['models'][key] = {
            'episode_seconds': episode['seconds'], 'success': episode['success'], 'collision': episode['collision'],
            'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(), 'checkpoint_sha256': ledger['sha256'],
            'step_x_y_m': samples.round(8).tolist(),
        }

    # One 12 m long strip of the real raster, centered near the last saved PPO pose.
    # Store occupied column runs on each original row. This also preserves thin walls.
    ncols, nrows = 54, 184
    lower = np.floor((last_pose - g.origin) / g.res).astype(int) - [ncols // 2, 82]
    c0, r0 = lower
    cells = g.free[r0:r0+nrows, c0:c0+ncols]
    rows = []
    for row in cells:
        occupied = np.r_[False, ~row, False]
        edges = np.flatnonzero(occupied[:-1] != occupied[1:]).reshape(-1, 2)
        rows.append(edges.tolist())
    data.update(lower_left_m=(g.origin + lower*g.res).tolist(), ncols=ncols,
                occupied_column_runs_bottom_up=rows, focus_step=610)

    visible = steps >= 530
    array_bytes = io.BytesIO()
    np.save(array_bytes, scans[visible], allow_pickle=False)
    SCANS.write_bytes(gzip.compress(array_bytes.getvalue(), mtime=0))
    data['scan_archive'] = SCANS.name
    data['scan_npy_sha256'] = hashlib.sha256(array_bytes.getvalue()).hexdigest()
    for key, checkpoint in CHECKPOINTS.items():
        model = data['models'][key]
        actions = predict(workspace / checkpoint, model['checkpoint_sha256'], scans)
        if key == 'original':
            error = float(np.max(np.abs(actions - recorded_actions)))
            if error > 2e-6:
                raise ValueError(f'Offline original differs from recorded actions by {error}')
            data['original_replay_max_abs_error'] = error
        model['same_input_step_steering'] = np.column_stack([steps[visible], actions[visible, 0]]).tolist()
    return data


def verify_weights(workspace, data):
    import numpy as np
    array_bytes = gzip.decompress(SCANS.read_bytes())
    if hashlib.sha256(array_bytes).hexdigest() != data['scan_npy_sha256']:
        raise ValueError('Published LiDAR sample hash differs.')
    scans = np.load(io.BytesIO(array_bytes), allow_pickle=False)
    for key, relative in CHECKPOINTS.items():
        model = data['models'][key]
        steering = predict(workspace / relative, model['checkpoint_sha256'], scans)[:, 0]
        expected = np.asarray(model['same_input_step_steering'])
        np.testing.assert_allclose(steering, expected[:, 1], rtol=0, atol=2e-6)
        focus = int(np.flatnonzero(expected[:, 0] == data['focus_step'])[0])
        print(f'{key}: verified {len(scans)} scans; steering at step {data["focus_step"]} = {steering[focus]:+.6f}')


def render(data, lang):
    it = lang == 'it'
    def t(en, italian):
        return italian if it else en
    def n(value, decimals):
        result = f'{value:.{decimals}f}'
        return result.replace('.', ',') if it else result
    def txt(x, y, value, size, color=INK, weight=400, family='sans-serif', anchor='start'):
        return (f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" font-weight="{weight}" '
                f'font-size="{size}" text-anchor="{anchor}">{value}</text>')
    heading = t('Editing the steering response', 'Modificare la risposta dello sterzo')
    desc = t('Recorded paths from two development runs, with a comparison of both steering outputs on identical LiDAR inputs.',
             'Traiettorie di due giri di sviluppo e confronto delle due uscite di sterzo sulle stesse scansioni LiDAR.')
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" xml:lang="{lang}" width="640" height="690" viewBox="0 0 640 690" role="img" aria-labelledby="title desc">',
         f'<title id="title">Budapest · {heading}</title><desc id="desc">{desc}</desc>',
         f'<metadata>Map cropped, rotated and recolored from {data["map_source"]}. GPLv3. Paths drawn from separately recorded episodes. Steering outputs evaluated on the original run’s saved LiDAR scans.</metadata>',
         '<rect width="640" height="690" fill="#fcfbf7"/>',
         txt(20,31,'BUDAPEST   /   SEED 1101   /   '+t('DEVELOPMENT','SVILUPPO'),16,MUTED,700,'monospace'),
         txt(18,78,heading,35,family='Georgia, serif')]
    models = data['models']
    for x,key,color,label in [(20,'original',PPO,t('Original PPO','PPO originale')),
                              (332,'edited',ARC,t('Edited PPO · wall_panic','PPO modificata · wall_panic'))]:
        line_style = 'stroke-dasharray="5 4"' if key == 'original' else ''
        s.append(f'<path d="M{x} 106h22" stroke="{color}" stroke-width="3" {line_style}/>')
        s.append(txt(x+29,112,label,18,color,700))
        outcome = t('Lap in','Giro in') if models[key]['success'] else t('Collision at','Urto a')
        s.append(txt(x,142,f'{outcome} {n(models[key]["episode_seconds"],2)} s',24,family='Georgia, serif'))
    x, top, width = 20, 162, 600
    cell = data['cell_m']
    rows = data['occupied_column_runs_bottom_up']
    k = width / len(rows)
    h = data['ncols'] * k
    left, bottom = data['lower_left_m']
    # Rotate the map 90 degrees so that the cars advance from left to right.
    def project(p):
        return (x + width - (p[1]-bottom)*k/cell, top + h - (p[0]-left)*k/cell)
    s.extend([f'<defs><clipPath id="map"><rect x="{x}" y="{top}" width="{width}" height="{h:.3f}"/></clipPath></defs>',
              f'<g clip-path="url(#map)"><rect x="{x}" y="{top}" width="{width}" height="{h:.3f}" fill="#eeeae0"/>'])
    bounds = []
    for j,runs in enumerate(rows):
        for lo,hi in runs:
            bounds.append(f'M{x+width-(j+1)*k:.3f},{top+h-hi*k:.3f}h{k:.3f}v{(hi-lo)*k:.3f}h-{k:.3f}Z')
    s.append(f'<path fill="{WALL}" shape-rendering="crispEdges" d="{" ".join(bounds)}"/>')
    for key, color in [('edited', ARC), ('original', PPO)]:
        pos = [sample[1:] for sample in models[key]['step_x_y_m']]
        style = 'stroke-dasharray="7 5"' if key == 'original' else ''
        s.append(f'<path d="{path_data(pos, project)}" fill="none" stroke="{color}" stroke-width="3.6" stroke-linecap="round" {style}/>')
    last = models['original']['step_x_y_m'][-1]
    ex,ey = project(last[1:])
    s.extend([f'<circle cx="{ex:.2f}" cy="{ey:.2f}" r="5" stroke="{PPO}" stroke-width="2.5" fill="white"/>',
              '</g>', f'<rect x="{x}" y="{top}" width="{width}" height="{h:.3f}" fill="none" stroke="#bcbbaf"/>',
              f'<circle cx="25" cy="363" r="4.5" stroke="{PPO}" stroke-width="2.5" fill="white"/>',
              txt(40,369,t('Last saved original pose','Ultima posa salvata della PPO originale') + f' · {n(last[0]*.01,2)} s',18),
              f'<path d="M515 356v7h{k/cell:.3f}v-7" fill="none" stroke="{INK}" stroke-width="2"/>',
              txt(574,369,'1 m',16,MUTED), '<path d="M20 389H620" stroke="#c9c9be"/>',
              txt(20,423,t('Steering on identical LiDAR scans','Sterzo a parità di scansione LiDAR'),26,family='Georgia, serif'),
              txt(20,449,t('Normalized command from both checkpoints','Comando normalizzato dei due checkpoint'),17,MUTED)])
    x0,x1,yt,yb=61,613,477,602
    lo = models['original']['same_input_step_steering'][0][0]
    hi = last[0]
    def axis(p):
        return (x0 + (p[0]-lo)/(hi-lo)*(x1-x0), yb - (p[1]+.6)/1.65*(yb-yt))
    for value in [-.5,0,.5,1.0]:
        _, py = axis((lo,value))
        s.extend([f'<path d="M{x0} {py:.2f}H{x1}" stroke="#cecec3"/>',
                  txt(x0-8,py+5,n(value,1),15,MUTED,anchor='end')])
    for tick in range(540,int(hi)+1,20):
        px,_ = axis((tick,0))
        s.append(txt(px,627,n(tick*.01,1),16,MUTED,anchor='middle'))
    focus = data['focus_step']
    fx,_ = axis((focus,0))
    s.extend([f'<path d="M{fx:.2f} {yt}V{yb}" stroke="#8a8980" stroke-dasharray="3 4"/>',
              txt(fx,627,n(focus*.01,1),16,INK,700,anchor='middle')])
    for key,color,dashes in [('original',PPO,'7 5'),('edited',ARC,None)]:
        points = models[key]['same_input_step_steering']
        style = f'stroke-dasharray="{dashes}"' if dashes else ''
        s.append(f'<path d="{path_data(points, axis)}" fill="none" stroke="{color}" stroke-width="3.4" stroke-linejoin="round" {style}/>')
        value = next(val for step,val in points if step == focus)
        fx,fy = axis((focus,value))
        s.extend([f'<circle cx="{fx:.2f}" cy="{fy:.2f}" r="5" fill="{color}" stroke="white" stroke-width="1.5"/>',
                  txt(fx+12,fy-4,'+'+n(value,3),17,color,700)])
    s.extend([txt(613,650,t('Simulation time (s)','Tempo simulato (s)'),16,MUTED,anchor='end'),
              txt(20,677,t('Map','Mappa')+' · f1tenth_racetracks / GPLv3',15,MUTED), '</svg>'])
    return '\n'.join(s)+'\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--workspace', type=Path)
    modes.add_argument('--verify-weights', type=Path)
    args = p.parse_args()
    dataset = OUT / 'repair-data.json'
    if args.workspace:
        data = extract(args.workspace)
        dataset.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n')
    else:
        data = json.loads(dataset.read_text())
    if args.verify_weights:
        verify_weights(args.verify_weights, data)
        return
    for lang in ['en','it']:
        (OUT / f'repair-{lang}.svg').write_text(render(data,lang))


if __name__ == '__main__':
    main()
