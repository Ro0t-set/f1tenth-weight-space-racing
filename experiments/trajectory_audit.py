"""Offline geometry of saved traces; does not change policy, physics or evaluation.

Clearance is exact Euclidean separation of the 0.58 x 0.31 m footprint from
closed occupied pixel squares (<=128), at the SAVED poses only. It is not the
simulator's LiDAR/TTC collision label or clearance to a continuous real wall.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
import yaml

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / 'upstream/map/f1tenth_racetracks'
HALF = np.array([.58, .31]) / 2
SIGNS = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]])


def rectangle_pixel_distance(centers, position, yaw, resolution):
    """Minimum distance between one rotated rectangle and axis-aligned squares.

    For disjoint convex polygons the minimum is a vertex-to-edge distance;
    the separating-axis test additionally detects edge crossings/containment.
    """
    c, s = np.cos(yaw), np.sin(yaw)
    rotation = np.array([[c, -s], [s, c]])
    relative = centers - position
    local = relative @ rotation
    pixel_half = resolution / 2
    body_vertices = SIGNS * HALF @ rotation.T + position
    pixels = centers[:, None, :] + SIGNS[None, :, :] * pixel_half
    local_vertices = (pixels - position) @ rotation
    point_body = np.linalg.norm(np.maximum(np.abs(local_vertices) - HALF, 0), axis=2).min(axis=1)
    point_pixel = np.linalg.norm(np.maximum(np.abs(body_vertices[None, :, :] - centers[:, None, :]) - pixel_half, 0), axis=2).min(axis=1)
    body_world_extent = np.abs(rotation) @ HALF
    pixel_local_extent = pixel_half * np.abs(rotation).sum(axis=0)
    overlap = np.all(np.abs(relative) <= body_world_extent + pixel_half, axis=1) & np.all(np.abs(local) <= HALF + pixel_local_extent, axis=1)
    return np.where(overlap, 0., np.minimum(point_body, point_pixel))


class Geometry:
    def __init__(self, name):
        folder = MAPS / name
        meta = yaml.safe_load((folder / f'{name}_map.yaml').read_text())
        self.res = float(meta['resolution'])
        self.origin = np.asarray(meta['origin'][:2])
        # Existing project maps all use yaw=0; reject rather than silently misplot.
        if abs(float(meta['origin'][2])) > 1e-12:
            raise ValueError('Rotated map origins are not supported by this audit.')
        self.free = np.flipud(np.asarray(Image.open(folder / f'{name}_map.png').convert('L'))) > 128
        rows, cols = np.nonzero(~self.free)
        self.occupied_centers = np.c_[cols + .5, rows + .5] * self.res + self.origin
        self.tree = cKDTree(self.occupied_centers)
        self.upper = self.origin + np.array(self.free.shape[::-1]) * self.res
        self.race = np.loadtxt(folder / f'{name}_raceline.csv', delimiter=';', skiprows=3)[:, 1:3]
        self.seg = np.roll(self.race, -1, axis=0) - self.race
        self.lengths = np.linalg.norm(self.seg, axis=1)
        self.arc = np.r_[0., np.cumsum(self.lengths)]

    def clearance(self, position, yaw, with_center=True):
        c, s = np.cos(yaw), np.sin(yaw)
        rotation = np.array([[c, -s], [s, c]])
        nearest = self.tree.query(position)[0]
        # Any better square center must be within this radius, by triangle inequality.
        radius = nearest + np.linalg.norm(HALF) + self.res / np.sqrt(2)
        centers = self.occupied_centers[self.tree.query_ball_point(position, radius)]
        center_to_body = np.linalg.norm(np.maximum(np.abs((centers - position) @ rotation) - HALF, 0), axis=1)
        centers = centers[center_to_body <= center_to_body.min() + self.res / np.sqrt(2) + 1e-12]
        distance = float(rectangle_pixel_distance(centers, position, yaw, self.res).min())
        corners = SIGNS * HALF @ rotation.T + position
        boundary = float(np.minimum(corners - self.origin, self.upper - corners).min())
        distance = min(distance, max(0., boundary))
        if not with_center:
            return distance
        # Center-to-occupied-square distance is useful for exposing center-only bias.
        center_candidates = self.occupied_centers[self.tree.query_ball_point(position, nearest + self.res / np.sqrt(2))]
        center_distance = np.linalg.norm(np.maximum(np.abs(center_candidates - position) - self.res / 2, 0), axis=1).min()
        center_distance = min(float(center_distance), max(0., float(np.minimum(position - self.origin, self.upper - position).min())))
        return distance, center_distance

    def project(self, positions):
        cte, arc = [], []
        for position in positions:
            t = np.clip(np.sum((position - self.race) * self.seg, axis=1) / np.maximum(self.lengths**2, 1e-20), 0, 1)
            residual = position - (self.race + t[:, None] * self.seg)
            j = int(np.argmin(np.sum(residual**2, axis=1)))
            sign = 1. if self.seg[j, 0] * residual[j, 1] - self.seg[j, 1] * residual[j, 0] >= 0 else -1.
            cte.append(float(np.linalg.norm(residual[j]) * sign))
            arc.append(float(self.arc[j] + t[j] * self.lengths[j]))
        return np.asarray(cte), np.asarray(arc)


def audit(path, geometry, dt):
    with np.load(path) as data:
        if 'states' not in data or 'steps' not in data:
            raise ValueError(f'{path}: trace requires states and steps; no synthetic poses are inferred.')
        states, steps = data['states'], data['steps']
    if len(states) == 0 or states.shape[1] != 7 or not np.isfinite(states).all():
        raise ValueError(f'{path}: invalid state trace')
    body, center = np.asarray([geometry.clearance(p[:2], p[4]) for p in states]).T
    cte, arc = geometry.project(states[:, :2])
    path_segments = np.linalg.norm(np.diff(states[:, :2], axis=0), axis=1)
    heading_change = np.abs(np.diff(np.unwrap(states[:, 4])))
    summary = dict(trace=str(path.resolve()), saved_frames=len(states), frame_interval_max_s=float(np.diff(steps).max() * dt) if len(steps)>1 else None,
                   sampled_duration_s=float((steps[-1]-steps[0])*dt), sampled_path_length_m=float(path_segments.sum()), raceline_loop_length_m=float(geometry.arc[-1]),
                   sampled_absolute_body_yaw_change_rad=float(heading_change.sum()), body_clearance_min_m=float(body.min()),
                   body_clearance_p05_m=float(np.quantile(body,.05)), body_clearance_median_m=float(np.median(body)),
                   center_clearance_min_m=float(center.min()), occupied_or_outside_body_frames=int((body<=1e-10).sum()),
                   body_frames_below_10cm=int((body<.1).sum()), body_frames_below_20cm=int((body<.2).sum()),
                   raceline_cross_track_abs_median_m=float(np.median(np.abs(cte))), raceline_cross_track_abs_p95_m=float(np.quantile(np.abs(cte),.95)),
                   minimum_clearance_time_s=float(steps[int(np.argmin(body))]*dt), map_resolution_m=geometry.res,
                   limitations=['Saved poses only: excursions between frames and final collision pose may be absent.',
                                'Closed occupied pixel squares; real wall position is uncertain at map resolution.',
                                'Zero separation means footprint contact/overlap, not signed penetration depth.',
                                'Raceline is a geometric reference, not a demonstrated absolute optimum.',
                                'Polyline length omits sub-frame motion and is not comparable across unequal progress.',
                                'Upstream TTC ignores slip beta; this geometry audit does not redefine collision outcomes.'])
    arrays=dict(states=states, time=steps*dt, body_clearance=body, center_clearance=center, signed_cross_track=cte, raceline_arc=arc)
    return summary, arrays


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('traces', nargs='+', type=Path)
    ap.add_argument('--map', required=True)
    ap.add_argument('--dt', type=float, default=.01, help='Simulator step duration, not saved-frame duration')
    ap.add_argument('--out-dir', type=Path, default=ROOT/'results/trajectory_v4')
    args=ap.parse_args(); args.out_dir.mkdir(parents=True, exist_ok=True)
    geometry=Geometry(args.map)
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    fig=plt.figure(figsize=(13,8)); grid=fig.add_gridspec(2,2,width_ratios=[1.3,1]); ax=fig.add_subplot(grid[:,0]); ac=fig.add_subplot(grid[0,1]); at=fig.add_subplot(grid[1,1])
    ax.imshow(geometry.free,cmap='gray',vmin=0,vmax=1,origin='lower',extent=[geometry.origin[0],geometry.upper[0],geometry.origin[1],geometry.upper[1]])
    closed=np.vstack([geometry.race,geometry.race[0]])
    ax.plot(*closed.T,'--',color='#999999',lw=.9,label='Raceline: riferimento')
    reports=[]
    for i,path in enumerate(args.traces):
        summary,arrays=audit(path,geometry,args.dt); reports.append(summary)
        (args.out_dir/f'{path.stem}_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
        np.savez_compressed(args.out_dir/f'{path.stem}_geometry.npz',**arrays)
        states=arrays['states']; label=path.stem.replace('development_','').replace('_trace',''); color=f'C{i%10}'
        ax.plot(states[:,0],states[:,1],color=color,lw=1.1,label=label)
        j=int(np.argmin(arrays['body_clearance'])); p=states[j]; c,s=np.cos(p[4]),np.sin(p[4]); rot=np.array([[c,-s],[s,c]])
        ax.add_patch(Polygon(SIGNS*HALF@rot.T+p[:2],fill=False,edgecolor=color,lw=1.5)); ax.plot(*states[0,:2],'o',color=color,ms=3)
        marker='o' if len(states)==1 else None
        ac.plot(arrays['time'],arrays['body_clearance'],color=color,lw=1,marker=marker,label=label)
        at.plot(arrays['time'],arrays['signed_cross_track'],color=color,lw=1,marker=marker)
    ax.set_aspect('equal'); ax.set_xlabel('x [m]'); ax.set_ylabel('y [m]'); ax.legend(fontsize=7,loc='best')
    for axis in (ac,at): axis.set_xlabel('Tempo del campione [s]'); axis.grid(alpha=.25)
    ac.axhline(.1,color='gray',ls=':',lw=.7); ac.set_ylabel('Margine del corpo [m]'); at.set_ylabel('Scarto laterale dalla raceline [m]'); at.axhline(0,color='gray',lw=.6)
    fig.suptitle(f'{args.map} · geometria ai soli campioni salvati\nCorpo 0,58 × 0,31 m; muri a pixel; raceline di riferimento',fontsize=12)
    fig.tight_layout(); fig.savefig(args.out_dir/f'{args.map}_trajectories.png',dpi=180); fig.savefig(args.out_dir/f'{args.map}_trajectories.svg'); plt.close(fig)
    (args.out_dir/f'{args.map}_comparison.json').write_text(json.dumps(reports,indent=2)+'\n')
    print(json.dumps([{k:r[k] for k in ('trace','saved_frames','sampled_path_length_m','body_clearance_min_m','occupied_or_outside_body_frames','raceline_cross_track_abs_p95_m')} for r in reports],indent=2))


if __name__=='__main__':
    main()
