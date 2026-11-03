# Recuperare il passo e ripartire vicino al muro

Il candidato finale `nose_guard` completa 95 giri su 105, con zero collisioni segnalate e dieci timeout. Sulle 86 partenze completate sia dal candidato sia da `arc_dynamic` e dalla PPO `early_smooth`, il suo tempo è inferiore del 9,91% rispetto ad Arc e dell’1,73% rispetto alla PPO. Sulle stesse partenze Arc impiega il 10,41% in più della PPO. L’8,23% della fase precedente riguardava altri seed.

| Su 105 nuove partenze per modello | PPO `early_smooth` | Arc `arc_dynamic` | Solo passo `clear_straight` | Passo e partenza `nose_guard` |
|---|---:|---:|---:|---:|
| Giri completati | 88 | 93 | 93 | **95** |
| Collisioni segnalate | 17 | 0 | 0 | **0** |
| Timeout | 0 | 12 | 12 | **10** |
| Giri completati senza contatti raster | 83 | 93 | 93 | **95** |

Sulle 81 triplette senza contatti campionati, i vantaggi di tempo sono del 9,94% e dell’1,58%. La variante con la sola modifica del passo riduce i tempi di Arc del 9,21% e impiega lo 0,15% in più della PPO sulle proprie 86 triplette completate.

## Velocità e margini per partire

Sui 15 giri di sviluppo completati da entrambi, la rete Arc percorreva solo lo 0,61% di distanza in più della PPO, ma nel 46% dei campioni la velocità era limitata dalla frenata a fine arco. La nuova testa di velocità tiene conto della velocità di uscita quando la visibilità supera un metro. Consente più accelerazione laterale nei raggi intermedi e supera 10 m/s solo sul rettilineo.

I due archi di partenza più corti adottano la sagoma effettiva e ripristinano gradualmente la riserva di 5 cm. Una protezione dei raggi frontali considera il rumore LiDAR e la distanza percorsa durante il ritardo dello sterzo. Nel grafo originale di Arc cambiano 12.044 dei 28.427 coefficienti, di cui 11.906 nell’ingombro, 74 nella testa di velocità e 64 in quella di sterzo.

## Due collisioni motivano la revisione

Il primo tentativo recupera quattro dei sette timeout storici, poi collide ad Austin dopo 0,09 s sul seed 71303, con margine iniziale di 4,45 mm. Il secondo salva tre casi storici, poi collide ad Austin dopo 0,13 s sul seed 71808, con margine di 0,196 mm. Le prove precedenti diventano sviluppo per la revisione successiva. I coefficienti finali sono fissati prima dei cinque nuovi seed da 73101 a 73505 su ciascuna pista.

| Timeout storico | Margine iniziale del corpo | Esito finale |
|---|---:|---|
| IMS 60404 | 28,9 mm | Giro pulito in 29,08 s |
| Monza 60404 | 18,1 mm | Giro pulito in 46,33 s |
| Austin 60404 | 6,3 mm | Timeout |
| Yas Marina 60404 | 9,8 mm | Timeout |
| IMS 60505 | Sovrapposto | Timeout |
| Oschersleben 60404 e 60505 | Entrambi sovrapposti | Due timeout |

I cinque timeout storici ancora aperti comprendono due partenze con margine inferiore a un centimetro e tre con sovrapposizione iniziale. Nelle simulazioni cinematiche di retromarcia più del 99% del nuovo spazio spazzato dalle uscite praticabili ricade nel settore cieco del LiDAR.

## Controllo delle traiettorie

Il confronto finale copre 420 episodi e 2.463.075 pose. In tutti i 95 giri completati dal candidato la carrozzeria resta separata dai pixel occupati nelle pose registrate. Il minimo misurato è 0,85 cm, rispetto a 1,69 cm di Arc. Il campionamento ogni 0,01 s esclude il moto fra due pose e il passo successivo all’ultimo campione. Sui 315 casi già osservati il candidato completa 294 giri con zero collisioni segnalate. Solo i nuovi 105 casi costituiscono la verifica indipendente di questa versione.

Ogni episodio dura al massimo 200 secondi simulati. Per completare il giro occorre visitare almeno il 99% dei waypoint in ordine e attraversare la linea di partenza senza una collisione segnalata. Partenze e rumore LiDAR sono appaiati. I tempi si confrontano sulle stesse partenze completate dai modelli indicati. Un valore negativo indica un giro più rapido.

## Giri completati per pista

| Pista | `early_smooth` | `arc_dynamic` | `clear_straight` | `nose_guard` |
|:---|:---|:---|:---|:---|
| Austin | 5/5 | 4/5 | 4/5 | 5/5 |
| BrandsHatch | 5/5 | 5/5 | 5/5 | 5/5 |
| Budapest | 5/5 | 5/5 | 5/5 | 5/5 |
| Catalunya | 5/5 | 5/5 | 5/5 | 5/5 |
| Hockenheim | 5/5 | 5/5 | 5/5 | 5/5 |
| IMS | 1/5 | 1/5 | 1/5 | 1/5 |
| Melbourne | 5/5 | 5/5 | 5/5 | 5/5 |
| MexicoCity | 5/5 | 5/5 | 5/5 | 5/5 |
| Monza | 3/5 | 4/5 | 4/5 | 4/5 |
| MoscowRaceway | 5/5 | 5/5 | 5/5 | 5/5 |
| Nuerburgring | 5/5 | 5/5 | 5/5 | 5/5 |
| Oschersleben | 3/5 | 2/5 | 2/5 | 3/5 |
| Sakhir | 4/5 | 5/5 | 5/5 | 5/5 |
| SaoPaulo | 5/5 | 5/5 | 5/5 | 5/5 |
| Sepang | 5/5 | 5/5 | 5/5 | 5/5 |
| Silverstone | 5/5 | 5/5 | 5/5 | 5/5 |
| Sochi | 0/5 | 5/5 | 5/5 | 5/5 |
| Spa | 5/5 | 5/5 | 5/5 | 5/5 |
| Spielberg | 5/5 | 5/5 | 5/5 | 5/5 |
| YasMarina | 2/5 | 2/5 | 2/5 | 2/5 |
| Zandvoort | 5/5 | 5/5 | 5/5 | 5/5 |

## Dati e riproduzione

- [Modello finale TorchScript](artifacts/arc_recovery/nose_guard.pt)
- [Compilatore della protezione anteriore](experiments/arc_nose_guard.py)
- [Modelli e seed congelati](results/arc_recovery/locked/holdout_manifest.json)
- [Confronto finale fra quattro modelli](results/arc_recovery/locked/verified_four_way.json)
- [Verifica dei sette timeout storici](results/arc_recovery/locked/verified_historical_timeouts.json)
