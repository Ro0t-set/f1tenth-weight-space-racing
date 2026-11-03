"""Frozen-holdout summary for the mechanistic circuit repair."""
import json,hashlib,os
from pathlib import Path
from compare import compare
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/ultra'
manifest=json.loads((OUT/'holdout_manifest.json').read_text())
raw={n:json.loads((OUT/f'final_{n}.json').read_text()) for n in ['original','cautious','wall','fast']}
for n,p in raw.items():
    frozen=manifest['checkpoints'][n]
    assert p['sha256']==frozen['sha256']==hashlib.sha256((ROOT/frozen['path']).read_bytes()).hexdigest()
    assert len(p['rows'])==210
    assert sorted(set(r['seed'] for r in p['rows']))==manifest['seeds']
comparisons={n:compare(OUT/'final_original.json',OUT/f'final_{n}.json') for n in ['cautious','wall','fast']}
for n,c in comparisons.items():(OUT/f'comparison_{n}.json').write_text(json.dumps(c,indent=2)+'\n')
dev={n:compare(ROOT/'results/racing_v2/development_baseline.json',OUT/f'development_{n}.json') for n in ['angular_smooth','panic_gate','wall_panic','wall_panic_fast']}
(OUT/'development_comparisons.json').write_text(json.dumps(dev,indent=2)+'\n')
drift={n:dict(completed_proxy_events=sum(r['success'] and r['longest_countersteer_slip_s']>=.5 for r in p['rows']),
             max_completed_countersteer_s=max(r['longest_countersteer_slip_s'] for r in p['rows'] if r['success']),
             early_collisions_leq_point1s=sum(r['collision'] and r['seconds']<=.1 for r in p['rows'])) for n,p in raw.items()}
(OUT/'drift_summary.json').write_text(json.dumps(drift,indent=2)+'\n')
f=comparisons['fast'];w=comparisons['wall'];c=comparisons['cautious']
improved=f['edited_collisions']<f['baseline_collisions'] and f['mean_paired_lap_change_pct']<0
outcome=('Nel test il candidato primario migliora sia i completamenti sia il tempo appaiato rispetto all’originale.' if improved else
         'Il test non conferma un miglioramento simultaneo di velocità e collisioni per il candidato primario.')
rows='\n'.join(f"| {r['map']} | {r['baseline_success']}/10 | {next(x for x in c['per_map'] if x['map']==r['map'])['edited_success']}/10 | {next(x for x in w['per_map'] if x['map']==r['map'])['edited_success']}/10 | {r['edited_success']}/10 | "+(f"{r['paired_lap_change_pct']:+.2f}%" if r['paired_success'] else '—')+' |' for r in f['per_map'])
devrows='\n'.join(f"| `{n}` | {d['edited_success']}/21 | {d['mean_paired_lap_change_pct']:+.3f}% |" for n,d in dev.items())

os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
names=['original','cautious','wall','fast'];labels=['Originale','Prudente precedente','Riparazione circuito','Riparazione + 0,2 m/s']
success=[sum(r['success'] for r in raw[n]['rows']) for n in names]
times=[0]+[comparisons[n]['mean_paired_lap_change_pct'] for n in names[1:]]
fig,axes=plt.subplots(1,2,figsize=(12,4.5));colors=['#7c8796','#738a51','#398f8a','#315fc2']
axes[0].barh(labels,success,color=colors);axes[0].invert_yaxis();axes[0].set_xlim(0,230)
for i,s in enumerate(success):axes[0].text(s+2,i,f'{s}/210',va='center')
axes[0].set_title('Giri completati');axes[0].set_xlabel('21 piste × 10 nuove partenze, senza esclusioni')
axes[1].barh(labels,times,color=colors);axes[1].invert_yaxis();axes[1].axvline(0,color='#555',lw=.8)
for i,t in enumerate(times):axes[1].text(t+(.1 if t>=0 else -.1),i,f'{t:+.2f}%',ha='left' if t>=0 else 'right',va='center')
axes[1].set_xlim(min(times)-1.3,max(times)+1.3);axes[1].set_title('Tempo appaiato rispetto all’originale');axes[1].set_xlabel('Solo coppie completate · negativo = più veloce')
fig.suptitle('Weight-space programming · test dopo il congelamento dei pesi',fontweight='bold')
fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=160);fig.savefig(OUT/'comparison.svg')

report=f'''# Riparazione di un circuito nei pesi — terza fase

3 novembre 2026. {outcome} **Zero incidenti e drift controllato non sono dimostrati.**

## Confronto finale

| Modello | Completamenti | Collisioni | Tempo appaiato rispetto all’originale |
|---|---:|---:|---:|
| Originale | {f['baseline_success']}/210 | {f['baseline_collisions']} | riferimento |
| Prudente precedente | {c['edited_success']}/210 | {c['edited_collisions']} | {c['mean_paired_lap_change_pct']:+.2f}% |
| Riparazione, velocità invariata | {w['edited_success']}/210 | {w['edited_collisions']} | {w['mean_paired_lap_change_pct']:+.2f}% |
| Riparazione +0,2 m/s, candidato primario | {f['edited_success']}/210 | {f['edited_collisions']} | {f['mean_paired_lap_change_pct']:+.2f}% |

Il candidato primario recupera {len(f['gained'])} episodi falliti dall’originale e ne perde {len(f['lost'])} precedentemente riusciti. Il tempo è confrontato sulle {f['paired_success']} coppie completate. Il circuito senza aumento di velocità recupera {len(w['gained'])} episodi e ne perde {len(w['lost'])}; serve come confronto per isolare l’effetto della riparazione.

![Risultati](results/ultra/comparison.png)

## Cosa è stato individuato nei pesi

L’analisi indipendente degli strati e delle traiettorie trova quattro neuroni del primo strato particolarmente variabili: 1, 14, 41, 61. La combinazione h41 positivo e h61 negativo partecipa alle sterzate positive estreme. Non tutte sono dannose: alcune appartengono a tornanti completati. Nei campioni terminali problematici esaminati, la parete sinistra è però a circa 0,26–0,32 m, mentre nei campioni di sterzata estrema completati la distanza minima è 0,441 m.

Il nuovo circuito interviene solo sulla combinazione richiesta di sterzo positivo + parete sinistra molto vicina. Non simmetrizza l’intera rete e non sostituisce il controller appreso.

```
dL = media LiDAR dei raggi 880:920 (circa perpendicolari a sinistra)
h15_nuovo = tanh((0,4 - dL) / 0,05)
g = tanh(4 * (h15_nuovo + h41 - h61 - 2))
sterzo_nuovo ≈ sterzo_originale - 0,35 * (1 + g)
velocità_nuova ≈ velocità_originale + 0,2 m/s
```

La soglia del predicato è il punto medio fra la combinazione vera (+3) e una condizione falsa (≤+1) per segnali tanh saturi. Il margine spaziale di 0,4 m comprende la semilarghezza di 0,155 m più margine. La scelta è motivata dalla geometria osservata nello sviluppo, non da fitting o scansioni automatiche di parametri; la generalizzazione va giudicata solo dal confronto finale.

Le formule sono implementate riutilizzando due neuroni quasi costanti e compensando il loro vecchio contributo nei bias successivi. L’architettura resta 1080→64→64→2. Cambiano **1.276 scalari (0,869% del checkpoint)**; critico e `log_std` restano identici. Gli input, il simulatore e la normalizzazione non cambiano. Le formule sono prima del clipping originale, con un piccolo residuo di compensazione verificato.

## Verifiche indipendenti

Su 6.889 osservazioni di sviluppo: equivalenza esatta delle predizioni con `PPO.load`; formula dei tensori entro 8,7e−7 normalizzato; il candidato veloce ha sterzo bit-identico al circuito non accelerato e differisce da esso per un solo bias (+0,016 normalizzato = +0,2 m/s). Tutte le voci ZIP tranne `policy.pth` sono identiche all’originale. Audit e script sono in `results/ultra_analysis/`.

Gli hash dei quattro checkpoint sono fissati in `results/ultra/holdout_manifest.json` prima delle prove finali e verificati contro gli output. Nessun peso è stato modificato dopo il test finale.

## Metodo e tentativi di sviluppo

Si segue la modalità con strumenti e feedback del [Weight-Space Programming](https://rikiyat.github.io/blog/weight-space-programming/): lettura dei tensori, ipotesi meccanistiche, modifica esplicita dei pesi e rollout. Nessun training, gradiente, fitting, ottimizzatore o ricerca automatica dei valori.

| Intervento | Successi (originale 10/21) | Tempo appaiato |
|---|---:|---:|
{devrows}

Due ipotesi sono scartate prima dei rollout: dimezzare la temperatura dei quattro neuroni introduce un bias sinistro e riduce la velocità; recuperare la testa di sterzo dal vecchio checkpoint YasMarina aumenta i picchi. Il filtro angolare da solo migliora leggermente i completamenti ma non la velocità. Il predicato solo interno colpisce anche alcune sterzate utili: aggiungere la distanza dal muro restringe l’intervento.

![Esempio causale di sviluppo](results/ultra/repair_example.png)

L’esempio mostra Budapest, seed 1101, nel gruppo di sviluppo: non è una prova indipendente di generalizzazione.

## Protocollo e limiti

- Sviluppo: le stesse sette piste difficili della seconda fase, seed 1101, 2202, 3303. Il candidato primario è scelto per miglioramento simultaneo di tempo e completamenti sullo sviluppo, prima del test finale.
- Test finale: 21 piste ×10 seed nuovi, 40101, 40202, 40303, 40404, 40505, 40606, 40707, 40808, 40909, 41010. Sono nuove partenze/rumore, non piste mai osservate. Quattro checkpoint, 840 episodi finali; 84 ulteriori episodi di sviluppo per i quattro candidati.
- Il successo richiede ≥99% waypoint ordinati e attraversamento della partenza, senza collisione; massimo 200 s simulati, un giro. Tutti i fallimenti sono inclusi. Il confronto della velocità è condizionato al completamento di entrambi, non include i crash come giri veloci.
- Partenze problematiche non eliminate: nel gruppo finale l’originale conta {drift['original']['early_collisions_leq_point1s']} collisioni entro 0,10 s, il primario {drift['fast']['early_collisions_leq_point1s']}.
- Nessuna garanzia di zero incidenti, superiorità universale, robustezza su più giri o comportamento su un veicolo reale.

## Drift

Nessun drift controllato viene dichiarato. Nel primario, episodi completati con |β|≥5°, v≥3m/s e controsterzo continuo per almeno 0,5 s: **{drift['fast']['completed_proxy_events']}**. Il massimo tratto così misurato negli episodi completati è {drift['fast']['max_completed_countersteer_s']:.2f} s; anche un eventuale risultato positivo sarebbe solo un indicatore diagnostico.

Il modello usa forze laterali linearizzate e manca della dinamica di ruote/slittamento necessaria a certificare il drift pneumatico. Inoltre il rilevatore originale `check_ttc_jit` proietta la velocità come `v*cos(ray_angle)`, ignorando β, mentre il moto segue heading+β. Quindi anche l’interpretazione delle collisioni in forte deriva è limitata. Questa fase mantiene tutti questi componenti invariati, come richiesto. Non si sfrutta il difetto per dichiarare un drift riuscito.

## Per pista

| Pista | Originale | Prudente | Circuito | Circuito veloce | Tempo veloce/originale |
|---|---:|---:|---:|---:|---:|
{rows}

## File e comandi

- [Checkpoint primario sperimentale](artifacts/ultra/wall_panic_fast.zip), [circuito senza accelerazione](artifacts/ultra/wall_panic.zip).
- [Confronto finale](results/ultra/comparison_fast.json), [confronto senza accelerazione](results/ultra/comparison_wall.json).
- [Generatore dei pesi](experiments/ultra_weights.py), [audit del candidato](results/ultra_analysis/fast_verification.json).
- Gli originali sono intatti. Gli ZIP sono per inferenza: conservano lo stato storico dell’optimizer, da reinizializzare prima di eventuale training.

```bash
.venv/bin/python experiments/ultra_weights.py wall_panic
.venv/bin/python experiments/ultra_weights.py wall_panic_fast
.venv/bin/python experiments/evaluate.py --checkpoint artifacts/ultra/wall_panic_fast.zip --maps all --seeds 40101 40202 40303 40404 40505 40606 40707 40808 40909 41010 --out results/ultra/final_fast.json
.venv/bin/python experiments/summarize_ultra.py
```
'''
(ROOT/'ULTRA_RESULTS.md').write_text(report)
print(json.dumps({n:{k:v for k,v in d.items() if k!='per_map'} for n,d in comparisons.items()},indent=2))
