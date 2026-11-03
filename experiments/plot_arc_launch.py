"""Show the original footprint and first metre of two historical IMS departures."""
import argparse
import json
import os
import numpy as np
from trajectory_audit import Geometry, HALF, ROOT, SIGNS

os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Polygon


def body(pose, start):
    c, s = np.cos(pose[4]), np.sin(pose[4])
    return (SIGNS * HALF) @ np.array([[c, s], [-s, c]]) + pose[:2] - start


def main(confirmation):
    phase = ROOT / 'results/arc_recovery'
    folder = phase / 'confirmation' if confirmation else phase
    trace_prefix = phase / 'iteration2/historical' if confirmation else phase / 'known/arc_recovered'
    cases = json.loads((folder / 'verified_historical_timeouts.json').read_text())['rows']
    geometry = Geometry('IMS')
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.7), constrained_layout=True)
    for ax, seed in zip(axes, (60404, 60505)):
        case = next(r for r in cases if (r['map'], r['seed']) == ('IMS', seed))
        path = trace_prefix.with_name(f'{trace_prefix.name}_IMS_{seed}_trace.npz')
        with np.load(path) as trace:
            states = trace['states']
        start = states[0, :2]
        lower, upper = geometry.origin - start, geometry.upper - start
        ax.imshow(geometry.free, origin='lower', interpolation='nearest', extent=[lower[0],upper[0],lower[1],upper[1]],
                  cmap=ListedColormap(['#5d6268', '#f7f7f3']), vmin=0, vmax=1)
        ax.add_patch(Polygon(body(states[0], start), facecolor='#337ca455', edgecolor='#135b81', lw=2))
        cumulative = np.r_[0., np.cumsum(np.linalg.norm(np.diff(states[:, :2], axis=0), axis=1))]
        if case['clean_completion']:
            last = int(np.searchsorted(cumulative, 1.))
            ax.plot(*(states[:last+1, :2]-start).T, color='#d66119', lw=1.4)
            for distance in (.35, .7, 1.):
                step = int(np.searchsorted(cumulative, distance))
                ax.add_patch(Polygon(body(states[step], start), fill=False, edgecolor='#d66119', lw=1.2))
            description = 'Giro completato · margine iniziale 2,89 cm'
        else:
            description = 'Timeout · corpo già sovrapposto al muro'
        ax.set(title=f'IMS, seed {seed}\n{description}', xlim=(-1.25,.85), ylim=(-.85,1.45),
               xlabel='x dalla partenza (m)', ylabel='y dalla partenza (m)', aspect='equal')
    fig.suptitle('Partenze storiche · blu alla partenza, arancione nel primo metro', fontsize=12)
    fig.savefig(folder / 'launch_examples.png', dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirmation', action='store_true')
    main(parser.parse_args().confirmation)
