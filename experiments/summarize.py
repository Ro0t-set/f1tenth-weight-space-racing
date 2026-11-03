"""Export final comparison, chart and concise experiment report."""
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1]/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from compare import compare

ROOT=Path(__file__).resolve().parents[1]
results=ROOT/'results'
final=compare(results/'final_baseline.json',results/'final_cautious.json')
(results/'final_comparison.json').write_text(json.dumps(final,indent=2)+'\n')
first=json.loads((results/'holdout_comparison.json').read_text())
dev=json.loads((results/'development_comparison.json').read_text())
cdev=json.loads((results/'development_cautious_comparison.json').read_text())

rows=final['per_map']; labels=[r['map'] for r in rows]; y=np.arange(len(rows))
fig,axes=plt.subplots(1,2,figsize=(13,9),gridspec_kw={'width_ratios':[1,1.05]})
fig.patch.set_facecolor('#fafaf7')
for ax in axes:
    ax.set_facecolor('#fafaf7')
    ax.spines[['top','right']].set_visible(False)
axes[0].barh(y+.18,[r['baseline_success'] for r in rows],height=.34,label='Originale',color='#738394')
axes[0].barh(y-.18,[r['edited_success'] for r in rows],height=.34,label='Pesi modificati: prudente',color='#207f78')
axes[0].set_yticks(y,labels);axes[0].invert_yaxis();axes[0].set_xlim(0,11)
axes[0].set_xlabel('Giri completati / 10 partenze');axes[0].legend(loc='lower right',fontsize=9)
axes[0].set_title('Affidabilità osservata',loc='left',fontweight='bold')
for i,r in enumerate(rows):
    d=r['paired_lap_change_pct']
    if d is not None:
        axes[1].barh(i,d,color='#c78945' if d>0 else '#207f78',height=.6)
        axes[1].text(d+.07,i,f"{d:+.1f}% (n={r['paired_success']})",va='center',fontsize=8)
    else:
        axes[1].text(.1,i,'nessuna coppia completata',va='center',fontsize=8,color='#65717b')
axes[1].set_yticks(y,labels);axes[1].invert_yaxis();axes[1].axvline(0,color='#738394',lw=.8)
axes[1].set_xlim(-.4,max((r['paired_lap_change_pct'] or 0) for r in rows)+2.5)
axes[1].set_xlabel('Variazione tempo sul giro (%) · positivo = più lento')
axes[1].set_title('Tempi sulle coppie completate da entrambi',loc='left',fontweight='bold')
for ax in axes:
    ax.set_ylim(len(rows)+1.5,-1)
fig.suptitle('F1TENTH · modifica diretta di 1.276 pesi, senza training',fontsize=16,fontweight='bold')
fig.text(.5,.025,f"21 piste × 10 nuovi seed · originale {final['baseline_success']}/210 · modificato {final['edited_success']}/210\n"
         'Piste già osservate; verifica su nuove partenze e nuovo rumore LiDAR. Simulazione di un giro.',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.065,1,.95))
fig.savefig(results/'comparison.png',dpi=160)
fig.savefig(results/'comparison.svg')

table='\n'.join(f"| {r['map']} | {r['baseline_success']}/10 | {r['edited_success']}/10 | "
                 +(f"{r['paired_lap_change_pct']:+.2f}%" if r['paired_lap_change_pct'] is not None else '—')+' |' for r in rows)
text=f'''# Risultati — 3 novembre 2026

## Esito

Modifica diretta dei pesi eseguita e verificata. La rete non è troppo grande: attore da 73.474 parametri, checkpoint da 146.885. Due candidati analitici, 1.276 scalari modificati ciascuno; nessun riaddestramento.

| Confronto | Originale | Modificato | Tempo sulle coppie completate |
|---|---:|---:|---:|
| Primo candidato, sviluppo | {dev['baseline_success']}/20 | {dev['edited_success']}/20 | {dev['mean_paired_lap_change_pct']:+.2f}% |
| Primo candidato, 17 altre piste | {first['baseline_success']}/85 | {first['edited_success']}/85 | {first['mean_paired_lap_change_pct']:+.2f}% |
| Candidato prudente, sviluppo | {cdev['baseline_success']}/20 | {cdev['edited_success']}/20 | {cdev['mean_paired_lap_change_pct']:+.2f}% |
| **Candidato prudente, verifica finale** | **{final['baseline_success']}/210** | **{final['edited_success']}/210** | **{final['mean_paired_lap_change_pct']:+.2f}%** |

Nella verifica finale: collisioni {final['baseline_collisions']} → {final['edited_collisions']}; timeout {final['baseline_timeouts']} → {final['edited_timeouts']}. Episodi recuperati: {len(final['gained'])}; episodi precedentemente riusciti ma persi: {len(final['lost'])}. Tempi confrontati su {final['paired_success']} coppie completate da entrambi.

Il primo candidato accelera ma peggiora il saldo dei completamenti, quindi non è un miglioramento complessivo. Il secondo va giudicato come compromesso fra completamento e tempo: i dati non dimostrano una policy universalmente superiore. Il checkpoint originale resta il riferimento; nessuna sostituzione automatica.

## Come sono stati modificati i pesi

Due neuroni quasi costanti nelle tracce di sviluppo vengono riutilizzati per un circuito che legge la distanza LiDAR frontale. Il loro precedente contributo viene trasferito nei bias successivi. Nel secondo candidato il circuito riduce fino a 0,6 m/s il comando quando lo spazio davanti è piccolo, e aggiunge fino a 0,3 m/s con spazio ampio. È tutto nei tensori della rete, senza logica di controllo aggiuntiva esterna.

La modifica riguarda lo 0,869% del checkpoint (1,737% dell'attore). Critico e deviazione standard delle azioni sono identici. I dettagli matematici, gli script e i comandi sono in [README.md](README.md); gli hash e il dettaglio dei tensori in [artifacts/clearance_cautious.json](artifacts/clearance_cautious.json).

## Verifica finale per pista

| Pista | Originale | Prudente | Variazione tempo appaiata |
|---|---:|---:|---:|
{table}

![Confronto per pista](results/comparison.png)

## Limiti e controlli

- Le 210 partenze finali non sono state usate per scegliere i pesi. Le piste erano già osservate nella prima verifica e già disponibili nel training storico: non sono un test su piste sconosciute.
- Le partenze e il rumore LiDAR sono appaiati; nessuna esclusione di incidenti immediati. Successo: almeno 99% dei waypoint in ordine più passaggio sulla linea di partenza, senza collisione. Limite 200 secondi, un giro.
- È un nuovo benchmark locale: la relazione storica usa 19 piste, qui ci sono 21 raceline. Python, NumPy e Gym differiscono dall'ambiente storico; le comparazioni sono valide all'interno di questo setup, non una replica numerica del paper.
- Verificata equivalenza esatta delle azioni con `PPO.load` su 128 osservazioni per checkpoint. Due episodi originali ripetuti producono risultati identici. Solo `policy.pth` cambia negli archivi; gli originali sono intatti.
- Nessun test su veicolo reale, ROS, più giri o avversari. Gli ZIP sono per inferenza; prima di nuovo training va reinizializzato lo stato dell'optimizer conservato nell'archivio.
- Il numero di episodi per pista è limitato e le partenze sulla stessa pista sono correlate. Non si pretende una garanzia statistica di superiorità generale.

## File utili

- [Checkpoint prudente](artifacts/clearance_cautious.zip)
- [Checkpoint veloce, candidato non promosso](artifacts/clearance_gate.zip)
- [Confronto finale JSON](results/final_comparison.json)
- [Episodi originali](results/final_baseline.json) / [episodi modificati](results/final_cautious.json)
- [Verifiche](results/verification_cautious.json)
- [Relazione originale LaTeX](upstream/report/index.tex)
- [Riferimento metodologico](https://rikiyat.github.io/blog/weight-space-programming/)
'''
(ROOT/'RESULTS.md').write_text(text)
print(json.dumps({k:v for k,v in final.items() if k!='per_map'},indent=2))

