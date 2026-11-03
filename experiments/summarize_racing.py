"""Summarize frozen final test without promoting a speed/safety tradeoff as success."""
import json
import os
from pathlib import Path
import numpy as np
from compare import compare
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/racing_v2'
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

baseline=OUT/'final_baseline.json'
comparisons={name:compare(baseline,OUT/f'final_{name}.json') for name in ['cautious','curvature']}
for name,c in comparisons.items():
    (OUT/f'comparison_{name}.json').write_text(json.dumps(c,indent=2)+'\n')
vs_cautious=compare(OUT/'final_cautious.json',OUT/'final_curvature.json')
(OUT/'comparison_vs_cautious.json').write_text(json.dumps(vs_cautious,indent=2)+'\n')
raw={name:json.loads((OUT/f'final_{name}.json').read_text())['rows'] for name in ['baseline','cautious','curvature']}
drift={name:dict(completed_sustained_countersteer_proxy=sum(r['success'] and r['longest_countersteer_slip_s']>=.5 for r in rows),
                 longest_countersteer_slip_s=max(r['longest_countersteer_slip_s'] for r in rows),
                 longest_completed_countersteer_slip_s=max(r['longest_countersteer_slip_s'] for r in rows if r['success']),
                 max_abs_beta_deg=max(r['max_abs_beta_deg'] for r in rows),
                 median_completed_p95_abs_beta_deg=float(np.median([r['p95_abs_beta_deg'] for r in rows if r['success']])))
       for name,rows in raw.items()}
(OUT/'drift_summary.json').write_text(json.dumps(drift,indent=2)+'\n')
variants=['clearance_speed','two_gate','two_gate_guard','exit_guard','geometric','curvature_compensated','straight_boost']
dev={v:compare(OUT/'development_baseline.json',OUT/f'development_{v}.json') for v in variants}
(OUT/'development_comparisons.json').write_text(json.dumps(dev,indent=2)+'\n')

labels=['Originale PPO','Precedente prudente','Tentativo veloce (scartato)']
names=['baseline','cautious','curvature'];colors=['#7b8794','#368b80','#3c64b1']
success=[sum(r['success'] for r in raw[n]) for n in names]
timing=[0,comparisons['cautious']['mean_paired_lap_change_pct'],comparisons['curvature']['mean_paired_lap_change_pct']]
fig,axes=plt.subplots(1,2,figsize=(12,4.2));fig.patch.set_facecolor('#fafaf7')
for ax in axes:
    ax.set_facecolor('#fafaf7');ax.spines[['top','right']].set_visible(False)
axes[0].barh(labels,success,color=colors);axes[0].invert_yaxis();axes[0].set_xlim(0,220)
for i,n in enumerate(success):axes[0].text(n+2,i,f'{n}/210',va='center')
axes[0].set_title('Giri completati senza collisione',loc='left',fontweight='bold')
axes[0].set_xlabel('21 piste × 10 nuovi seed · nessuna esclusione')
axes[1].barh(labels,timing,color=colors);axes[1].invert_yaxis();axes[1].axvline(0,color='#666',lw=1)
for i,t in enumerate(timing):axes[1].text(t+(.1 if t>=0 else -.1),i,f'{t:+.2f}%',ha='left' if t>=0 else 'right',va='center')
axes[1].set_xlim(min(timing)-1.5,max(timing)+1.5);axes[1].set_title('Tempo sul giro rispetto all’originale',loc='left',fontweight='bold')
axes[1].set_xlabel('Solo coppie completate · negativo = più veloce')
fig.suptitle('Modifica diretta dei pesi · fisica e osservazioni invariate',fontweight='bold')
fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=160);fig.savefig(OUT/'comparison.svg')

c=comparisons['curvature'];p=comparisons['cautious']
development_table='\n'.join(f"| `{v}` | {dev[v]['edited_success']}/21 | "+
    (f"{dev[v]['mean_paired_lap_change_pct']:+.2f}%" if dev[v]['paired_success'] else '—')+' |' for v in variants)
permap='\n'.join(f"| {row['map']} | {row['baseline_success']}/10 | {next(r for r in p['per_map'] if r['map']==row['map'])['edited_success']}/10 | {row['edited_success']}/10 | "+
                (f"{row['paired_lap_change_pct']:+.2f}%" if row['paired_success'] else '—')+' |' for row in c['per_map'])
report=f'''# Velocità, collisioni e drift: secondo esperimento

3 novembre 2026. Vincolo confermato: progetto attuale, solo modifiche ai pesi. **Fisica, sensori, architettura e logica di controllo esterna restano invariati.** La telemetria aggiunta non entra nella policy.

## Risultato finale

| Modello | Giri completati | Collisioni | Tempo appaiato rispetto all’originale |
|---|---:|---:|---:|
| Originale PPO | {c['baseline_success']}/210 | {c['baseline_collisions']} | riferimento |
| Precedente prudente | {p['edited_success']}/210 | {p['edited_collisions']} | {p['mean_paired_lap_change_pct']:+.2f}% |
| Tentativo veloce, scartato | {c['edited_success']}/210 | {c['edited_collisions']} | {c['mean_paired_lap_change_pct']:+.2f}% |

Il confronto del nuovo modello con l’originale comprende {c['paired_success']} coppie completate. Recupera {len(c['gained'])} episodi falliti dall’originale e ne perde {len(c['lost'])} precedentemente riusciti. Rispetto al precedente prudente, la variazione di tempo sulle {vs_cautious['paired_success']} coppie completate è {vs_cautious['mean_paired_lap_change_pct']:+.2f}%.

**L’obiettivo completo «più veloce, zero incidenti, drift controllato» non è raggiunto.** Eventuali miglioramenti di tempo non sono una garanzia di sicurezza; il modello resta sperimentale e non sostituisce automaticamente nessun checkpoint precedente.

![Confronto](results/racing_v2/comparison.png)

## Modifica sottoposta al test finale, poi scartata

Sono modificati **66 parametri**, lo 0,045% dei 146.885 scalari del checkpoint. I due strati nascosti, il critico e `log_std` sono identici all’originale.

```
sterzo_nuovo = 1,02721087931901 × sterzo_originale
velocità_nuova = velocità_originale + 0,3 m/s
```

Le formule valgono prima del clipping originale. Il guadagno dello sterzo non deriva da una ricerca sui dati: si ricava dal modello dinamico single-track, affinché l’incremento di velocità mantenga approssimativamente la curvatura a regime. Se G(v) è il rapporto yaw-rate/sterzo di equilibrio, il guadagno è `(8,8/8,5) × G(8,5)/G(8,8)`. La modifica è scritta nella riga dei pesi dello sterzo e nei due bias della testa d’azione; non è applicata da un wrapper esterno.

La formula è stata verificata su 6.889 osservazioni di sviluppo. Il caricamento SB3 è verificato con 256 osservazioni per checkpoint. L’aggiunta della telemetria lascia esattamente invariati gli esiti di 15 episodi originali ripetuti.

## Esperimenti scartati e metodologia

Come nel [lavoro sul Weight-Space Programming](https://rikiyat.github.io/blog/weight-space-programming/), ogni intervento nasce da un’ipotesi sui tensori, sulle equazioni o sulle traiettorie. Nessun training, gradiente, fitting, ricerca automatica o modifica della reward.

| Programma nei pesi | Successi di sviluppo | Tempo su coppie completate |
|---|---:|---:|
{development_table}

L’originale completa 10/21 prove di sviluppo. La riscrittura forte della velocità destabilizza la guida; i circuiti di frenata e correzione laterale interferiscono con la policy appresa; la policy geometrica da zero non completa i circuiti. Tutti i risultati negativi e i checkpoint sono conservati. Solo il candidato a curvatura compensata è stato scelto, poi congelato, prima del confronto finale. Dopo il suo fallimento è stata tentata un’ultima modifica, `straight_boost`: mantiene il limite di frenata prudente nelle curve più strette, ma aumenta fino a +1,8 m/s il comando sui rettilinei. È stata scartata già in sviluppo (9/21 contro 10/21), senza riusare il test finale per dichiararla superiore.

Sviluppo: BrandsHatch, YasMarina, Monza, Spa, Sochi, Budapest, Oschersleben; seed 1101, 2202, 3303. Test finale: tutte le 21 piste, seed 20001, 21002, 22003, 23004, 24005, 25006, 26007, 27008, 28009, 29010. Sono nuove partenze e nuovo rumore LiDAR, non nuove piste. Il test finale contiene 630 episodi complessivi per i tre modelli; aggiungendo lo sviluppo, questa fase comprende 798 episodi. Il checkpoint a curvatura compensata non è stato modificato dopo il test finale. È una sequenza di interventi ragionati con feedback del simulatore, non una riproduzione dell’esperimento one-shot dell’articolo.

## Drift: cosa è stato realmente misurato

Si misura lo stato dinamico interno β, insieme a velocità, sterzo e yaw rate. Un indicatore diagnostico richiede `|β|≥5°`, velocità ≥3 m/s, sterzo di segno contrario allo yaw rate per almeno 0,5 s consecutivi, e completamento dell’episodio. Non è, da solo, una prova di drift pneumatico.

Con il nuovo modello, episodi completati che soddisfano questo indicatore: **{drift['curvature']['completed_sustained_countersteer_proxy']}**. Il massimo intervallo di controsterzo con deriva negli episodi completati è **{drift['curvature']['longest_completed_countersteer_slip_s']:.2f} s**. I picchi di β non vengono presentati come drift controllato.

Il modello fisico attuale usa forze laterali linearizzate e non contiene saturazione combinata dei pneumatici né velocità angolari delle ruote. L’analisi di equilibrio a sette velocità fra 3 e 20 m/s, con accelerazione nulla, trova equilibri stabili con yaw rate dello stesso segno dello sterzo: nessun equilibrio di controsterzo nei casi controllati. Questo non è un teorema che esclude qualsiasi transitorio; mostra perché la sola sbandata numerica non certifica il comportamento richiesto.

La rete riceve una singola scansione LiDAR: velocità, β e yaw rate non sono osservati. Stati con identica posa e scansione ma diversa deriva ricevono la stessa azione. Su richiesta dell’utente non sono stati aggiunti sensori, memoria o nuovi modelli fisici.

Riferimenti del simulatore: [dinamica e stato single-track](https://f1tenth-gym.readthedocs.io/en/v1.0.0/api/dynamic_models.html), [parametri fisici](https://f1tenth-gym.readthedocs.io/en/stable/customized_usage.html). La diagnosi usa il codice locale effettivamente eseguito, non versioni differenti del simulatore.

## Partenze e limiti

Tutte le partenze sono conservate nei denominatori. Un controllo indipendente della mappa trova già occupato dal muro circa il 20,8% dei 510 punti campionati nell’impronta iniziale del veicolo a YasMarina, seed 2202. Altre collisioni avvengono dopo aver guidato: non vengono attribuite automaticamente alle partenze.

Successo: almeno il 99% dei waypoint ordinati più passaggio sulla linea di partenza, senza collisione. Limite 200 secondi simulati, un giro, RK4 e passo 0,01 s. Nessuna prova su hardware o gare di più giri. Tempi confrontati solo sugli episodi completati da entrambi; nessuna esclusione di fallimenti per far apparire più veloce un modello.

## Dettaglio per pista

| Pista | Originale | Prudente | Nuovo | Tempo nuovo/originale |
|---|---:|---:|---:|---:|
{permap}

## Artefatti e riproduzione

- [Checkpoint sperimentale](artifacts/racing_v2/curvature_compensated.zip) e [manifest](artifacts/racing_v2/curvature_compensated.json).
- [Confronto finale](results/racing_v2/comparison_curvature.json), [drift](results/racing_v2/drift_summary.json), [verifiche](results/racing_v2/verification.json).
- [Programmi dei pesi](experiments/racing_weights.py), [audit riproducibile](experiments/audit_racing.py).
- Gli optimizer storici negli ZIP sono conservati: artefatti per inferenza; reinizializzarli prima di eventuale training futuro.

```bash
.venv/bin/python experiments/racing_weights.py curvature_compensated
.venv/bin/python experiments/audit_racing.py
.venv/bin/python experiments/evaluate.py --checkpoint artifacts/racing_v2/curvature_compensated.zip --maps all --seeds 20001 21002 22003 23004 24005 25006 26007 27008 28009 29010 --out results/racing_v2/final_curvature.json
.venv/bin/python experiments/summarize_racing.py
```
'''
(ROOT/'RACING_RESULTS.md').write_text(report)
print(json.dumps(dict(final={k:v for k,v in c.items() if k!='per_map'},versus_cautious={k:v for k,v in vs_cautious.items() if k!='per_map'},drift=drift),indent=2))
