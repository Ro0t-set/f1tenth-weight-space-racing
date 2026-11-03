# Costruire una rete dalla geometria del veicolo

Su 21 piste con cinque nuovi seed ciascuna, da 60101 a 60505, la rete analitica `arc_dynamic` completa 98 giri. La PPO della fase precedente ne completa 95. A Sochi il confronto passa da zero a cinque completamenti. La rete analitica richiede in media l’8,23% di tempo in più sulle 92 coppie completate. Tutti i suoi sette timeout hanno meno dell’1% di progresso.

| Esito | PPO modificata precedente | Rete da zero |
|---|---:|---:|
| Completamenti | 95/105 | **98/105** |
| Collisioni segnalate dal simulatore | 10 | **0** |
| Timeout | 0 | **7** |
| Giri completati senza contatti raster nelle pose controllate | 89 | **98** |
| Sochi | 0/5 | **5/5** |
| Tempo sulle 92 coppie completate | riferimento | **+8,23%** |

## Dal LiDAR agli archi

I minimi su gruppi di sei raggi riducono la scansione a 180 settori. Per 17 curvature e nove orizzonti fra 0,5 e 11 m, il compilatore calcola l’ingombro del corpo, con riserva di 5 cm, incorporando la deriva a regime dalle equazioni del veicolo. La rete seleziona la direzione con spazio sufficiente e interpola soltanto con le direzioni adiacenti. Così due passaggi distanti non si fondono in una direzione intermedia bloccata.

Le teste ReLU a tratti usano riferimenti di frenata e accelerazione laterale di 6 e 7 m/s², con comando massimo di 10 m/s. Le equazioni generano i coefficienti prima dell’inferenza. In esecuzione bastano i tensori e la singola scansione LiDAR. Il modulo TorchScript, l’adattatore e il calcolo singolo o in batch coincidono su 479 ingressi.

## Costo della rete e prove scartate

| Misura | Attore PPO precedente | Rete da zero |
|---|---:|---:|
| Coefficienti dell'attore | 73.474 | **28.427** |
| Memoria dei coefficienti float32 | 293.896 byte | **113.708 byte** |
| Inferenza completa `predict`, mediana locale | 55,4 µs | **49,8 µs** |
| Solo calcolo della rete, mediana locale | **31,3 µs** | 46,5 µs |

I coefficienti memorizzati, compresi i tensori geometrici, calano del 61,3%. Il benchmark usa un thread, batch singolo, 128 chiamate di riscaldamento e cinque serie di 1.000 chiamate. L’adattatore migliora la mediana complessiva mentre il solo calcolo della rete impiega più tempo.

| Programma | Prove di sviluppo | Esito |
|---|---|---|
| `arc_soft`, geometria senza deriva, selezione globale | 3 | 0 completamenti, 3 collisioni |
| `arc_mode`, geometria senza deriva, selezione locale | 3 | 0 completamenti, 3 collisioni |
| `arc_dynamic`, deriva analitica | 21 | **18 completamenti, 0 collisioni, 3 timeout** |
| `arc_dynamic_pace`, riferimento laterale 8 m/s² e massimo 11 m/s | 21 | 15 completamenti, 3 collisioni, 3 timeout: scartato |

## Margini osservati

Su 210 episodi e 1.083.184 pose, tutti i 98 completamenti della rete analitica mantengono margine raster positivo, con minimo 2,56 cm. Tre timeout partono già sovrapposti al muro e accumulano 60.000 pose sovrapposte. Sulle coppie completate, le pose sotto 10 cm dal muro salgono dallo 0,203% al 4,814%. A Sochi, seed 60101, la PPO collide a 24,52 s e la nuova rete completa il giro in 58,23 s.

Sulle 14 piste escluse dallo sviluppo di questa rete, i completamenti sono 67/70 contro 68/70 della PPO e il tempo cresce dell’8,55%. Le mappe erano note al progetto. La deriva a regime approssima i transitori. Il primo indice scelto a parità di punteggio può rompere la simmetria dello sterzo. Tra i campioni registrati e dopo l’ultimo passo il margine resta sconosciuto.

Ogni episodio dura al massimo 200 secondi simulati. Per completare il giro occorre visitare almeno il 99% dei waypoint in ordine e attraversare la linea di partenza senza una collisione segnalata. Partenze e rumore LiDAR sono appaiati. I tempi si confrontano sulle stesse partenze completate dai modelli indicati. Un valore negativo indica un giro più rapido.

## Controlli indipendenti della rete e dei giri

Dei 28.427 coefficienti, 28.130 sono diversi da zero. L’artefatto TorchScript occupa 122.271 byte. Sei scenari simmetrici di controllo rispettano la simmetria dello sterzo, mentre due scenari con punteggi a pari merito lasciano residui normalizzati di 0,5661 e 0,8025. Nelle 92 coppie completate i giri con contatto scendono da cinque a zero, ma i campioni a meno di 20 cm dal muro crescono dallo 0,6901% al 26,1239%. A Sochi 60101 i minimi di separazione registrati sono 2,10 e 35,67 mm. Il giro interrotto della PPO e quello completo di Arc coprono distanze diverse.

## Giri completati per pista

| Pista | `early_smooth` | `arc_dynamic` |
|:---|:---|:---|
| Austin | 4/5 | 4/5 |
| BrandsHatch | 5/5 | 5/5 |
| Budapest | 5/5 | 5/5 |
| Catalunya | 5/5 | 5/5 |
| Hockenheim | 5/5 | 5/5 |
| IMS | 4/5 | 3/5 |
| Melbourne | 5/5 | 5/5 |
| MexicoCity | 5/5 | 5/5 |
| Monza | 4/5 | 4/5 |
| MoscowRaceway | 5/5 | 5/5 |
| Nuerburgring | 5/5 | 5/5 |
| Oschersleben | 3/5 | 3/5 |
| Sakhir | 5/5 | 5/5 |
| SaoPaulo | 5/5 | 5/5 |
| Sepang | 5/5 | 5/5 |
| Silverstone | 5/5 | 5/5 |
| Sochi | 0/5 | 5/5 |
| Spa | 5/5 | 5/5 |
| Spielberg | 5/5 | 5/5 |
| YasMarina | 5/5 | 4/5 |
| Zandvoort | 5/5 | 5/5 |

## Dati e riproduzione

- [Compilatore della rete](experiments/from_scratch.py)
- [Rete TorchScript](artifacts/from_scratch/arc_dynamic.pt)
- [Audit dei pesi, simmetria e tempi di calcolo](results/from_scratch_audit/arc_dynamic_audit.json)
- [Contatti suddivisi per esito](results/from_scratch/final_footprints_by_outcome.json)
