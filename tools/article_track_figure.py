"""Rebuild both article SVGs with Python 3 and the published track-data.json.

To re-extract the drawing from the original recordings, pass --traces DIR
(the locked trace directory) and --maps DIR (the pinned f1tenth_racetracks
checkout). Extraction requires the study's Python environment.
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/article'
LOCKED = ROOT / 'results/arc_recovery/locked'
MAP_REV = '3f581789c749261ae36fc4fef19a81372acc3ecf'
MAP_REPO = 'https://github.com/f1tenth/f1tenth_racetracks'
INK, MUTED, WALL = '#22231f', '#55574e', '#444b45'
PPO, ARC = '#ad3e21', '#006b67'
COLS, ROWS = 34, 28


def extract(traces, maps):
    import numpy as np
    sys.path.insert(0, str(ROOT / 'experiments'))
    import trajectory_audit as audit
    audit.MAPS = maps
    g = audit.Geometry('Sochi')
    with (LOCKED / 'verified_footprints.csv').open() as stream:
        audit_rows = {r['model']: r for r in csv.DictReader(stream)
                      if r['map'] == 'Sochi' and r['seed'] == '73101'}
    records = {}
    for model in ('ppo', 'candidate'):
        path = traces / f'final_{model}_Sochi_73101_trace.npz'
        if hashlib.sha256(path.read_bytes()).hexdigest() != audit_rows[model]['trace_sha256']:
            raise ValueError(f'Trace hash differs from the locked audit: {path}')
        with np.load(path) as data:
            records[model] = data['states'], data['steps']

    # Both views use the same rectangle of whole source cells. Keep a single
    # consecutive visit per trajectory; disjoint visits must never be joined.
    endpoint = records['ppo'][0][-1, :2]
    lower = np.floor((endpoint - g.origin) / g.res).astype(int) - [COLS // 2, ROWS // 2]
    base = g.origin + lower * g.res
    def selected_points(points, anchor):
        # Retain the adjacent points outside the viewport for clipping in SVG.
        inside = np.all((points >= base) & (points <= base + np.array([COLS, ROWS]) * g.res), axis=1)
        assert inside[anchor]
        left = next((i for i in range(anchor - 1, -1, -1) if not inside[i]), 0)
        right = next((i for i in range(anchor + 1, len(points)) if not inside[i]), len(points) - 1)
        return points[left:right+1].round(8).tolist()

    col, row = lower
    free = g.free[row:row+ROWS, col:col+COLS]
    race_i = int(np.linalg.norm(g.race - endpoint, axis=1).argmin())
    result = {
        'map': 'Sochi', 'seed': 73101,
        'map_source': f'{MAP_REPO}/tree/{MAP_REV}/Sochi',
        'map_revision': MAP_REV, 'map_license': 'GPL-3.0',
        'description': 'Adapted Sochi map and raceline, f1tenth/f1tenth_racetracks. '
                       'World positions in meters. # marks occupied cells. Rows start at the bottom. '
                       'The small locator samples every twelfth raceline vertex.',
        'map_source_sha256': {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                              for f in (maps / 'Sochi').glob('Sochi_*') if f.suffix in ('.png', '.yaml') or f.name.endswith('_raceline.csv')},
        'cell_m': g.res, 'lower_left_m': base.tolist(),
        'walls_bottom_up': [''.join('.' if v else '#' for v in line) for line in free],
        'locator_raceline_m': g.race[::12].round(5).tolist(),
        'local_raceline_m': selected_points(g.race, race_i),
        'body_size_m': (audit.HALF * 2).tolist(),
        'models': {},
    }
    for model, (states, steps) in records.items():
        i = len(states)-1 if model == 'ppo' else int(np.linalg.norm(states[:, :2] - endpoint, axis=1).argmin())
        pose = states[i]
        r = audit_rows[model]
        result['models'][model] = {
            'trace_sha256': r['trace_sha256'], 'sample_step': int(steps[i]),
            'sample_seconds': float(steps[i]) * .01,
            'pose_xy_yaw': pose[[0, 1, 4]].tolist(), 'sample_margin_m': g.clearance(pose[:2], pose[4], False),
            'xy_m': selected_points(states[:, :2], i), 'episode_seconds': float(r['episode_seconds']),
            'minimum_margin_m': float(r['minimum_body_clearance_m']),
            'success': r['success'] == 'True', 'collision': r['collision'] == 'True',
        }
    return result


def path_data(points, project):
    return 'M' + ' '.join(f'{x:.2f},{y:.2f}' for x, y in map(project, points))


def render(data, lang):
    it = lang == 'it'
    def t(en, italian):
        return italian if it else en
    def number(value, places=2):
        result = f'{value:.{places}f}'
        return result.replace('.', ',') if it else result
    def txt(x, y, text, size, color=INK, bold=False, font='sans-serif'):
        return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
                f'font-weight="{700 if bold else 400}" fill="{color}">{escape(text)}</text>')
    title = t('Two passes through one corner', 'Due passaggi nella stessa curva')
    desc = t('The PPO touches a wall cell in its last saved pose. The final actor passes the same corner and completes the lap.',
             'La PPO tocca una cella del muro nell’ultima posa registrata. Il modello finale supera la curva e completa il giro.')
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" xml:lang="{lang}" width="640" height="595" viewBox="0 0 640 595" role="img" aria-labelledby="title desc">',
         f'<title id="title">Sochi · {title}</title><desc id="desc">{desc}</desc>',
         f'<metadata>Map and raceline adapted from {data["map_source"]}. GPLv3. Crop, threshold, recoloring and overlays for this figure.</metadata>',
         '<rect width="640" height="595" fill="#fcfbf7"/>',
         txt(20, 33, 'SOCHI   /   SEED 73101', 17, MUTED, True, 'monospace'),
         txt(19, 79, t('At the wall', 'Vicino al muro'), 44, font='Georgia, serif'),
         txt(20, 109, title, 21),
         '<path d="M20 137H620" stroke="#c9c9be"/>']
    # The locator and both details have equal x/y scale; north is up in all three.
    locator = data['locator_raceline_m']
    x0, x1 = min(p[0] for p in locator), max(p[0] for p in locator)
    y0, y1 = min(p[1] for p in locator), max(p[1] for p in locator)
    k = min(170 / (x1 - x0), 96 / (y1 - y0))
    project = lambda p: (538 + (p[0] - (x0+x1)/2)*k, 70 - (p[1] - (y0+y1)/2)*k)
    px, py = project(data['models']['ppo']['pose_xy_yaw'])
    s.extend([f'<path d="{path_data(locator, project)} Z" stroke="{MUTED}" stroke-width="2.4" fill="none" stroke-linejoin="round"/>',
              f'<circle cx="{px:.2f}" cy="{py:.2f}" r="8" fill="#fcfbf7" stroke="{PPO}" stroke-width="2"/>',
              f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3" fill="{PPO}"/>'])
    cell = data['cell_m']
    px_per_cell = 288 / COLS
    scale = px_per_cell / cell
    left, bottom = data['lower_left_m']
    top = 207
    h = ROWS * px_per_cell
    for model, x, color, name in [('ppo',20,PPO,'PPO · early_smooth'), ('candidate',332,ARC,'nose_guard')]:
        m = data['models'][model]
        result = t('Lap in', 'Giro in') if m['success'] else t('Collision at', 'Urto a')
        s.extend([txt(x, 166, name, 19, color, True, 'monospace'),
                  txt(x, 195, f'{result} {number(m["episode_seconds"])} s', 26, font='Georgia, serif')])
        project = lambda p: (x + (p[0] - left)*scale, top + h - (p[1] - bottom)*scale)
        s.append(f'<defs><clipPath id="{model}"><rect x="{x}" y="{top}" width="288" height="{h:.2f}"/></clipPath></defs>'
                 f'<g clip-path="url(#{model})"><rect x="{x}" y="{top}" width="288" height="{h:.2f}" fill="#eeeae0"/>')
        # The map boundary is rendered from original occupied pixel squares.
        walls = []
        for j, line in enumerate(data['walls_bottom_up']):
            for i, c in enumerate(line):
                if c == '#':
                    walls.append(f'M{x+i*px_per_cell:.3f},{top+h-(j+1)*px_per_cell:.3f}h{px_per_cell:.3f}v{px_per_cell:.3f}h-{px_per_cell:.3f}Z')
        s.append(f'<path fill="{WALL}" shape-rendering="crispEdges" d="{" ".join(walls)}"/>')
        for points, stroke, style in [(data['local_raceline_m'], '#686b64', 'stroke-width="2" stroke-dasharray="3 6"'),
                                       (m['xy_m'], color, 'stroke-width="3.5" stroke-linecap="round"')]:
            s.append(f'<path d="{path_data(points, project)}" stroke="{stroke}" {style} stroke-linejoin="round" fill="none"/>')
        cx, cy, yaw = m['pose_xy_yaw']
        bx, by = project((cx, cy))
        l, w = (n * scale for n in data['body_size_m'])
        # Exact car dimensions and pose. A small arrow within the body shows heading.
        s.append(f'<g transform="translate({bx:.3f} {by:.3f}) rotate({-math.degrees(yaw):.5f})">'
                 f'<rect x="{-l/2:.3f}" y="{-w/2:.3f}" width="{l:.3f}" height="{w:.3f}" fill="{color}"/>'
                 '<path d="M-10 0H9m-5 -4 5 4-5 4" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></g></g>')
        s.append(f'<rect x="{x}" y="{top}" width="288" height="{h:.2f}" fill="none" stroke="#bcbbaf"/>')
        margin = m['sample_margin_m'] * 100
        label = t('Gap', 'Margine') + '  ' + (number(margin, 1) if margin else '0') + ' cm'
        s.extend([txt(x, 477, label, 24, color, True), txt(x, 503, t('Pose at', 'Posa a') + f' {number(m["sample_seconds"])} s', 19)])
    scale_width = .5*scale
    s.extend(['<path d="M20 522H620" stroke="#c9c9be"/>',
              f'<rect x="20" y="538" width="15" height="15" fill="{WALL}"/>',
              txt(44, 551, t('Wall cell', 'Cella del muro'), 17),
              '<path d="M221 545h29" stroke="#686b64" stroke-width="2.5" stroke-dasharray="3 5"/>',
              txt(257, 551, 'Raceline', 17), f'<path d="M466 539v9h{scale_width:.3f}v-9" fill="none" stroke="{INK}" stroke-width="2"/>',
              txt(524, 551, t('0.5 m', '0,5 m'), 17),
              txt(20, 581, t('Car body', 'Carrozzeria') + ' 58 × 31 cm', 16, MUTED),
              txt(274, 581, t('Map', 'Mappa') + ' · f1tenth_racetracks / GPLv3', 16, MUTED), '</svg>'])
    return '\n'.join(s) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--traces', type=Path)
    p.add_argument('--maps', type=Path)
    args = p.parse_args()
    if bool(args.traces) != bool(args.maps):
        p.error('Provide both --traces and --maps, or neither to redraw the published inputs.')
    path = OUT / 'track-data.json'
    if args.traces:
        data = extract(args.traces, args.maps)
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    else:
        data = json.loads(path.read_text())
    for lang in ('en', 'it'):
        (OUT / f'track-{lang}.svg').write_text(render(data, lang))


if __name__ == '__main__':
    main()
