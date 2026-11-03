"""Development example, explicitly not a held-out success claim."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np,yaml
from PIL import Image

folder=ROOT/'upstream/map/f1tenth_racetracks/Budapest'
meta=yaml.safe_load((folder/'Budapest_map.yaml').read_text())
im=np.flipud(np.array(Image.open(folder/'Budapest_map.png')))
o=meta['origin'];r=meta['resolution']
base=np.load(ROOT/'results/racing_v2/development_baseline_Budapest_1101_trace.npz')
wall=np.load(ROOT/'results/ultra/development_wall_panic_Budapest_1101_trace.npz')
fig,axes=plt.subplots(1,2,figsize=(11,4.5))
axes[0].imshow(im,origin='lower',cmap='gray',extent=[o[0],o[0]+im.shape[1]*r,o[1],o[1]+im.shape[0]*r])
end=base['states'][-1]
for z,label,color in [(base,'Originale: collisione a 6,50 s','#c3473c'),(wall,'Circuito corretto, senza accelerazione','#187d71')]:
    mask=z['steps']<=850
    s=z['states'][mask];t=z['steps'][mask]*.01
    axes[0].plot(s[:,0],s[:,1],color=color,label=label,lw=2)
    axes[1].plot(t,z['actions'][mask,0],color=color,label=label,lw=1.7)
axes[0].scatter(end[0],end[1],marker='x',color='#c3473c',s=80)
axes[0].set_xlim(end[0]-5,end[0]+5);axes[0].set_ylim(end[1]-5,end[1]+5)
axes[0].set_aspect('equal');axes[0].set_xlabel('x (m)');axes[0].set_ylabel('y (m)')
axes[0].set_title('Traiettoria sul tratto problematico')
axes[1].set_xlim(4.5,8.5);axes[1].set_ylim(-1.1,1.1)
axes[1].set_xlabel('Tempo simulato (s)');axes[1].set_ylabel('Comando sterzo normalizzato')
axes[1].set_title('La sterzata estrema viene attenuata');axes[1].legend(fontsize=8)
fig.suptitle('Budapest, seed 1101 · esempio di sviluppo, non test finale',fontweight='bold')
fig.tight_layout();fig.savefig(ROOT/'results/ultra/repair_example.png',dpi=160)
