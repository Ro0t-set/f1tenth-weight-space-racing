"""Report the frozen fourth-phase test; never choose or change weights."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np
from compare import compare

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/trajectory_v4'


def main():
    manifest = json.loads((OUT / 'holdout_manifest.json').read_text())
    payload = {n: json.loads((OUT / f'final_{n}.json').read_text()) for n in ('previous', 'candidate')}
    for n, p in payload.items():
        frozen = manifest['checkpoints'][n]
        assert p['sha256'] == frozen['sha256'] == hashlib.sha256((ROOT / frozen['path']).read_bytes()).hexdigest()
        expected = {(m, s) for m in manifest['maps'] for s in manifest['seeds']}
        assert {(r['map'], r['seed']) for r in p['rows']} == expected
        assert len(p['rows']) == len(expected) == 210
    c = compare(OUT / 'final_previous.json', OUT / 'final_candidate.json')
    (OUT / 'final_comparison.json').write_text(json.dumps(c, indent=2) + '\n')
    names = ['early_panic', 'exit_support', 'exit_only', 'exit_approach', 'early_smooth', 'turn_preview']
    dev = {n: compare(ROOT / 'results/ultra/development_wall_panic_fast.json', OUT / f'development_{n}.json') for n in names}
    (OUT / 'development_comparisons.json').write_text(json.dumps(dev, indent=2) + '\n')
    geometry = json.loads((OUT / 'final_geometry_seed50101.json').read_text())
    footprints = json.loads((OUT / 'final_all_footprints.json').read_text())
    index = {n: {(r['map'], r['seed']): r for r in p['rows']} for n, p in payload.items()}
    clean_keys = {n: {(r['map'], r['seed']) for r in footprints['rows']
                     if r['model'] == n and r['success'] and not r['contact_or_overlap_episode']} for n in payload}
    both_clean = clean_keys['previous'] & clean_keys['candidate']
    clean = dict(definition='Secondary diagnostic: official success AND no contact with occupied pixel squares in recorded pre-action states; not a replacement for the frozen outcome',
                 previous_clean=len(clean_keys['previous']), candidate_clean=len(clean_keys['candidate']), paired_clean=len(both_clean),
                 mean_paired_time_change_pct=float(np.mean([(index['candidate'][k]['seconds']/index['previous'][k]['seconds']-1)*100 for k in sorted(both_clean)])),
                 gained=sorted(clean_keys['candidate']-clean_keys['previous']), lost=sorted(clean_keys['previous']-clean_keys['candidate']))
    (OUT / 'secondary_contact_free.json').write_text(json.dumps(clean, indent=2) + '\n')
    fp = footprints['summary']
    g = geometry['summary']['paired_completed']
    early = {n: sum(r['collision'] and r['seconds'] <= .1 for r in p['rows']) for n, p in payload.items()}
    devrows = '\n'.join(f"| `{n}` | {d['edited_success']}/21 | " + (f"{d['mean_paired_lap_change_pct']:+.3f}%" if d['paired_success'] else '—') + ' |' for n, d in dev.items())
    maprows = '\n'.join(f"| {r['map']} | {r['baseline_success']}/10 | {r['edited_success']}/10 | " + (f"{r['paired_lap_change_pct']:+.3f}%" if r['paired_success'] else '—') + ' |' for r in c['per_map'])
    crash_change = 100 * (c['edited_collisions'] / c['baseline_collisions'] - 1)
    report = f'''# Pesi e traiettorie — quarta fase

3 novembre 2026. Il confronto riguarda il candidato congelato `early_smooth` e il veloce precedente `wall_panic_fast`. Tutti i risultati qui sotto provengono dalle nuove partenze 50101–51010, salvo le sezioni esplicitamente di sviluppo. Non sono nuove piste.

## Risultato finale

| Modello | Giri completati | Collisioni | Tempo appaiato |
|---|---:|---:|---:|
| Veloce precedente | {c['baseline_success']}/210 | {c['baseline_collisions']} | riferimento |
| Nuovi pesi | {c['edited_success']}/210 | {c['edited_collisions']} | {c['mean_paired_lap_change_pct']:+.4f}% |

Collisioni: {crash_change:+.2f}%. Il candidato recupera {len(c['gained'])} episodi e ne perde {len(c['lost'])} rispetto al precedente. Il tempo è confrontato sulle **{c['paired_success']} coppie completate**, mai usando un crash come giro breve. Intervallo descrittivo bootstrap delle medie per pista: {c['map_mean_change_bootstrap95'][0]:+.4f}% … {c['map_mean_change_bootstrap95'][1]:+.4f}%; non è una garanzia su piste o partenze future.

**Il controllo del corpo completo ridimensiona il risultato di sicurezza:** tra i giri dichiarati completati, {fp['previous']['completed']['contact_or_overlap_episodes']} precedenti e {fp['candidate']['completed']['contact_or_overlap_episodes']} nuovi hanno contatti/sovrapposizioni con pixel occupati. I giri completati **senza contatto nei campioni registrati** sono quindi **{clean['previous_clean']} → {clean['candidate_clean']}**, con tempo {clean['mean_paired_time_change_pct']:+.4f}% sulle {clean['paired_clean']} coppie così filtrate. È una diagnostica secondaria, non una ridefinizione a posteriori del successo congelato, e non certifica l'intero moto continuo.

Collisioni entro 0,10 s: precedente {early['previous']}, candidato {early['candidate']}; sono mantenute nel denominatore. I risultati per pista, inclusi Sochi e le partenze difficili, non vengono esclusi.

![Confronto](results/trajectory_v4/final_comparison.png)

## Modifiche effettive

Si mantiene l'architettura 1080→64→64→2, con il solo LiDAR originale. Due interventi espliciti:

1. La soglia del predicato di parete sinistra passa da 0,4 a 0,6 m. Nei fallimenti osservati la sterzata estrema iniziava prima dell'intervento precedente. La correzione resta condizionata alla combinazione interna di sterzo, non forza l'auto al centro pista.
2. Le sole righe 1, 14, 41, 61 del primo strato appreso ricevono un filtro angolare gaussiano di 2 raggi (circa 0,5°), incorporato nei coefficienti. La riga del nuovo predicato del muro resta intatta. Non c'è un filtro esterno o memoria temporale.

Cambiano **4.321 scalari rispetto al veloce precedente**, 5.596 rispetto all'originale storico (3,81% dei 146.885 scalari totali). Critico, `log_std`, architettura, fisica, sensori e normalizzazione restano invariati.

La testa di velocità non è riscritta; il filtro degli strati condivisi cambia anche le sue attivazioni. Sulle 9.319 osservazioni di sviluppo, variazione assoluta media della velocità comandata 0,01046 m/s, percentile 99 0,08263 m/s. Per questo la conservazione del passo si misura con i giri appaiati, non si deduce dalla sola testa invariata.

## Traiettorie e muri

Le pose sono registrate a ogni passo fisico (0,01 s), senza darle in ingresso alla rete. L'audit geometrico misura il rettangolo completo **0,58 × 0,31 m** rispetto ai pixel occupati della mappa, includendo rotazione e spigoli. La distanza del centro da sola sovrastima il margine disponibile.

Coorte primaria fissata prima dei risultati: seed 50101 su tutte le 21 piste, entrambi i modelli, con tutti i fallimenti. Nelle {g['count']} coppie completate:

- Lunghezza percorsa media appaiata: {g['mean_path_length_change_pct']:+.4f}%.
- Cambiamento medio del quinto percentile del margine del corpo: {100*g['mean_body_clearance_p05_change_m']:+.3f} cm.
- Cambiamento medio del 95° percentile dello scarto dalla raceline: {100*g['mean_raceline_cross_track_p95_change_m']:+.3f} cm.

![Traiettorie](results/trajectory_v4/final_fixed_trajectory_examples.png)

Budapest, Monza e Spa e lo zoom sulla curva di massima curvatura sono stati scelti prima degli esiti. I rettangoli mostrano l'ingombro dell'auto. La raceline del progetto è un riferimento: **non si dimostra una traiettoria globalmente ottima**, né stare più vicino al muro ovunque significa andare più veloce. Il margine in centimetri dipende anche dalla risoluzione della mappa. Il campione dopo l'ultimo passo terminale non è salvato.

Le statistiche complete sono in `final_geometry_seed50101.json`. L'audit aggiuntivo `final_all_footprints.json/.csv` esamina **420 episodi e {fp['previous']['all']['saved_frames'] + fp['candidate']['all']['saved_frames']:,} pose**, senza esclusioni. Fra le 178 coppie completate, entrambi i modelli presentano contatti raster in 6 episodi (i casi non sono tutti identici), con 23 contro 25 pose di contatto. Un contatto raster non misura la profondità della penetrazione.

Il codice originale `base_classes.py` calcola la semilunghezza TTC come `(lf+lr)/2`: il rilevatore di parete tratta una lunghezza di **0,3302 m**, mentre il corpo dichiarato è lungo **0,58 m**. Inoltre proietta la velocità ignorando l'angolo di deriva. Per questo collisioni del simulatore e contatto geometrico del corpo sono misure distinte; la risoluzione raster introduce un'ulteriore differenza. Nessuna modifica alla fisica o al rilevatore e nessuna dichiarazione di drift controllato. Dettagli e verifiche in `geometry_findings.md`.

## Sviluppo e tentativi scartati

Metodo del [Weight-Space Programming](https://rikiyat.github.io/blog/weight-space-programming/) con strumenti e feedback: lettura di pesi e attivazioni, ipotesi meccanistica, modifica esplicita dei tensori, verifica. Nessun training, fitting, gradiente, ottimizzatore o ricerca automatica dei valori.

| Ipotesi | Completamenti, precedente 12/21 | Tempo appaiato |
|---|---:|---:|
{devrows}

Le correzioni generiche vicino al muro intervengono anche nella guida normale e falliscono. Aggiungere una condizione di avvicinamento alla parete ne migliora la specificità ma non il compromesso finale; anticipare le curve destre accorcia alcuni giri ma introduce regressioni. Nessuno di questi modelli viene scelto.

`early_panic` ed `early_smooth` sono poi confrontati sulle 210 partenze già note della fase precedente: entrambi 184/210 contro 180, quattro recuperi senza perdite. Tempo rispettivamente +0,01255% e +0,000846%. Questi dati sono sviluppo, non il risultato finale. `early_smooth` è scelto e gli hash congelati prima delle nuove prove. Nessun peso viene modificato dopo il congelamento.

## Per pista nel nuovo test

| Pista | Precedente | Candidato | Tempo appaiato |
|---|---:|---:|---:|
{maprows}

## Riproduzione e verifiche

Il generatore è `experiments/trajectory_weights.py`. Audit indipendente: `results/trajectory_v4_analysis/early_smooth_verification.json`, con convoluzione NumPy indipendente esattamente uguale ai tensori, caricamento PPO/evaluator identico su 9.319 input, critico e metadati ZIP invariati. La nuova registrazione delle pose riproduce esattamente i risultati precedenti su tre episodi di controllo.

```bash
.venv/bin/python experiments/trajectory_weights.py early_smooth
.venv/bin/python experiments/evaluate.py --checkpoint artifacts/trajectory_v4/early_smooth.zip --maps all --seeds 50101 50202 50303 50404 50505 50606 50707 50808 50909 51010 --state-trace --out results/trajectory_v4/final_candidate.json
.venv/bin/python experiments/summarize_trajectories_v4.py
.venv/bin/python experiments/audit_all_footprints_v4.py
.venv/bin/python experiments/summarize_weights_v4.py
```

Ripetere l'evaluatore anche con `artifacts/ultra/wall_panic_fast.zip`, output `final_previous.json`, prima dei due riepiloghi. Il checkpoint resta per inferenza; conserva lo stato storico dell'ottimizzatore, da reinizializzare se in futuro si decide di fare training. Nessun file sorgente upstream modificato.
'''
    (ROOT / 'TRAJECTORY_RESULTS.md').write_text(report)
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    labels = ['Veloce precedente', 'Nuovi pesi']
    values = [c['baseline_collisions'], c['edited_collisions']]
    axes[0].bar(labels, values, color=['#2777b7', '#dc601a'])
    for i, value in enumerate(values): axes[0].text(i, value+.3, str(value), ha='center')
    axes[0].set_ylim(0, max(values)*1.2); axes[0].set_title('Collisioni su 210 nuove prove')
    axes[1].axis('off')
    axes[1].text(.5, .66, f"{c['mean_paired_lap_change_pct']:+.4f}%", ha='center', fontsize=28)
    axes[1].text(.5, .39, f"Tempo sul giro appaiato\n{c['paired_success']} coppie completate\nNegativo = più veloce", ha='center', fontsize=12)
    fig.suptitle('21 piste · pesi congelati prima delle prove', fontweight='bold')
    fig.tight_layout(); fig.savefig(OUT / 'final_comparison.png', dpi=180); plt.close(fig)
    print(json.dumps({k: v for k, v in c.items() if k != 'per_map'}, indent=2))


if __name__ == '__main__':
    main()
