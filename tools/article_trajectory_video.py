"""Render the recorded before/after PPO drives. Requires numpy, Pillow, matplotlib and ffmpeg."""
import argparse
import gzip
import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / '.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/article'
DATA = OUT / 'trajectory-animation.json.gz'
COLORS = {'original': '#bd473c', 'edited': '#167b72', 'scratch': '#315ec4'}


def extract(workspace):
    import yaml
    folder = workspace / 'upstream/map/f1tenth_racetracks/Budapest'
    meta = yaml.safe_load((folder/'Budapest_map.yaml').read_text())
    data = dict(map='Budapest', seed=1101, cohort='development', dimensions_m=[.58,.31],
                source='https://github.com/f1tenth/f1tenth_racetracks/tree/3f581789c749261ae36fc4fef19a81372acc3ecf/Budapest',
                raster_sha256=hashlib.sha256((folder/'Budapest_map.png').read_bytes()).hexdigest(),
                map_origin=meta['origin'][:2], resolution=meta['resolution'], runs={})
    image = Image.open(folder/'Budapest_map.png').convert('L')
    image.save(OUT/'trajectory-map.png')
    for name, source in [('original','racing_v2/development_baseline'),('edited','ultra/development_wall_panic')]:
        trace = workspace/f'results/{source}_Budapest_1101_trace.npz'
        ledger = json.loads((workspace/f'results/{source}.json').read_text())
        row = next(r for r in ledger['rows'] if (r['map'],r['seed'])==('Budapest',1101))
        with np.load(trace) as z:
            times = z['steps']*.01
            states = z['states']
        data['runs'][name] = dict(times=times.tolist(),states=np.round(states,8).tolist(),
                                 seconds=row['seconds'],success=row['success'],collision=row['collision'],
                                 checkpoint_sha256=ledger['sha256'], trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest())
    assert np.allclose(data['runs']['original']['states'][0],data['runs']['edited']['states'][0],atol=1e-7)
    DATA.write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))


def pose(run, time):
    states = np.asarray(run['states'])
    values = np.array([np.interp(time,run['times'],states[:,i]) for i in range(7)])
    values[4] = np.interp(time,run['times'],np.unwrap(states[:,4]))
    return values


def render(data, lang, mode):
    local = mode=='corner'
    it = lang=='it'
    labels = {'original':'Prima · PPO originale' if it else 'Before · original PPO',
              'edited':'PPO · pesi modificati' if it else 'PPO · edited weights',
              'scratch':'Rete scritta da zero' if it else 'Network written from scratch'}
    image = np.flipud(np.asarray(Image.open(OUT/data.get('map_file','trajectory-map.png'))))
    resolution = data['resolution']; origin = data['map_origin']
    extent = [origin[0],origin[0]+image.shape[1]*resolution,origin[1],origin[1]+image.shape[0]*resolution]
    runs = data['runs']
    all_xy = np.concatenate([np.asarray(r['states'])[:,:2] for r in runs.values()])
    if local:
        heading = pose(runs['edited'], 6.0)[4]
        view = np.array([[np.cos(heading),np.sin(heading)],[-np.sin(heading),np.cos(heading)]])
        window = np.concatenate([np.asarray(r['states'])[(np.asarray(r['times'])>=5.2)&(np.asarray(r['times'])<=7.0),:2] @ view.T for r in runs.values()])
        low,high=window.min(0)-.85,window.max(0)+.85
        # Identical square windows preserve both the geometry and vehicle scale.
        center=(low+high)/2; half_x=max((high-low)[0]/2, 2.12*(high-low)[1]/2, 5.); half_y=half_x/2.12
        bounds=[center[0]-half_x,center[0]+half_x,center[1]-half_y,center[1]+half_y]
        fig, one=plt.subplots(figsize=(9,7),dpi=100); axes=[one]*len(runs)
        fig.subplots_adjust(left=.025,right=.975,top=.80,bottom=.09)
        speed=.5; end=7.8; start=5.2
    else:
        low,high=all_xy.min(0)-3,all_xy.max(0)+3
        bounds=[low[0],high[0],low[1],high[1]]
        fig, one=plt.subplots(figsize=(9,8),dpi=100);axes=[one]*len(runs)
        fig.subplots_adjust(left=.03,right=.97,top=.87,bottom=.11)
        speed=4.;start=0.;end=max(r['seconds'] for r in runs.values())+.8
        view=np.eye(2);heading=0.
    fig.patch.set_facecolor('#f6f4ef')
    title = data.get('titles',{}).get(lang, 'La stessa rete, pesi diversi' if it else 'Same network, different weights')
    fig.suptitle(title,fontsize=22,fontweight='bold',y=.995,color='#211f1b')
    sub=(f"{data['map']} · seed {data['seed']} · " + ('traiettorie registrate' if it else 'recorded trajectories'))
    fig.text(.5,.925,sub+f' · {speed:g}×',ha='center',fontsize=14,color='#514e47')
    artists={}
    for (name,run),ax in zip(runs.items(),axes):
        if name=='original':
            ax.imshow(image,cmap='gray',origin='lower',extent=extent,interpolation='nearest',vmin=0,vmax=255)
            if local:
                from matplotlib.transforms import Affine2D
                ax.images[-1].set_transform(Affine2D().rotate(-heading)+ax.transData)
            ax.set(xlim=bounds[:2],ylim=bounds[2:],aspect='equal');ax.set_axis_off()
        color=COLORS[name]

        line,=ax.plot([],[],color=color,lw=2.8,label=labels[name])
        dot,=ax.plot([],[],'o',color=color,ms=4)
        body=Polygon(np.zeros((4,2)),facecolor=color,edgecolor='#182724',lw=1.0)
        ax.add_patch(body)
        text=ax.text(.015,.98 - .085*list(runs).index(name),'',
                     transform=ax.transAxes,va='top',fontsize=15,color=color,
                     bbox=dict(facecolor='#fffef9',alpha=.94,edgecolor='none',pad=5))
        artists[name]=(line,dot,body,text)
    footer=('Pose registrate ogni 0,1 s · interpolazione solo visiva' if it else 'Recorded poses every 0.1 s · interpolation for display only')
    fig.text(.5,.022,footer,ha='center',fontsize=12,color='#514e47')
    fps=20
    stem=data.get('stem','trajectory'); path=OUT/f'{stem}-{mode}-{lang}.mp4'
    width,height=fig.canvas.get_width_height()
    command=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}',
             '-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','22',
             '-pix_fmt','yuv420p','-movflags','+faststart',str(path)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for n,time in enumerate(np.arange(start,end+speed/fps,speed/fps)):
            for name,run in runs.items():
                state=pose(run,time);line,dot,body,text=artists[name]
                t=np.asarray(run['times']);states=np.asarray(run['states'])
                mask=t<=min(time,t[-1]); points=states[mask,:2]
                points=points@view.T;center=state[:2]@view.T
                line.set_data(points[:,0],points[:,1]);dot.set_data([center[0]],[center[1]])
                c,s=np.cos(state[4]),np.sin(state[4]);rot=np.array([[c,-s],[s,c]])
                body.set_xy((np.array([[-1,-1],[1,-1],[1,1],[-1,1]])*np.array([.29,.155]))@rot.T@view.T+center)
                if run['collision'] and time>=run['seconds']:
                    status=(f"Collisione a {run['seconds']:.2f} s" if it else f"Collision at {run['seconds']:.2f} s")
                elif run['success'] and time>=run['seconds']:
                    status=(f"Giro in {run['seconds']:.2f} s" if it else f"Lap in {run['seconds']:.2f} s")
                else:
                    actual=min(time,run['times'][-1])
                    status=f't = {actual:.2f} s'
                status=labels[name]+' · '+status
                text.set_text(status)
            fig.canvas.draw()
            poster_time = 32. if stem=='trajectory-overlay' else 8.
            if n==0 or (local and abs(time-6.1)<speed/fps/2) or (not local and abs(time-poster_time)<speed/fps/2):
                fig.savefig(OUT/f'{stem}-{mode}-{lang}-poster.jpg',dpi=100,facecolor=fig.get_facecolor())
            pixels=np.asarray(fig.canvas.buffer_rgba())[:,:,:3]
            process.stdin.write(pixels.tobytes())
        process.stdin.close()
        if process.wait()!=0:raise RuntimeError('ffmpeg failed')
    finally:
        if process.poll() is None:process.kill()
        plt.close(fig)
    print(path.name, path.stat().st_size)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path)
    parser.add_argument('--mode',choices=['corner','lap'])
    args=parser.parse_args()
    if args.workspace:extract(args.workspace)
    data=json.loads(gzip.decompress(DATA.read_bytes()))
    for lang in ['it','en']:
        for mode in ([args.mode] if args.mode else ['corner','lap']):render(data,lang,mode)


if __name__=='__main__':main()
