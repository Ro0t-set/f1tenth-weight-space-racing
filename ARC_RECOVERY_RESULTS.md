# Recupero del passo e delle partenze bloccate

**Il modello consegnato è [nose_guard.pt](artifacts/arc_recovery/nose_guard.pt).** Nel confronto finale recupera il divario di velocità e completa 95 giri su 105, tutti con separazione positiva fra carrozzeria e muri nelle pose registrate. Dei sette timeout storici ne recupera due.

| Su 105 nuove partenze per modello | PPO `early_smooth` | Arc `arc_dynamic` | Solo passo `clear_straight` | Passo e partenza `nose_guard` |
|---|---:|---:|---:|---:|
| Giri completati | 88 | 93 | 93 | **95** |
| Collisioni segnalate | 17 | 0 | 0 | **0** |
| Timeout | 0 | 12 | 12 | **10** |
| Giri completati senza contatti raster | 83 | 93 | 93 | **95** |

Sulle **86 partenze completate** da PPO, Arc precedente e candidato finale, il tempo medio appaiato del candidato è **−9,91%** rispetto ad Arc e **−1,73%** rispetto alla PPO. Su queste partenze Arc precedente impiega +10,41% rispetto alla PPO. L’8,23% originario era misurato su altri seed. Sulle **81 triplette geometricamente pulite**, il candidato impiega rispettivamente −9,94% e −1,58%. Il controllo con i soli pesi di velocità impiega −9,21% rispetto ad Arc e +0,15% rispetto alla PPO sulle sue 86 triplette completate.

La verifica comprende 420 episodi e 2.463.075 pose. Il margine minimo del candidato nei 95 giri completati è **0,85 cm nel raster**. È inferiore a quello del precedente, 1,69 cm. Nelle 315 prove già osservate usate durante questa fase, lo stesso checkpoint finale completa 294 giri e registra zero collisioni del simulatore. Soltanto i 105 casi dei seed 73101–73505 costituiscono la verifica finale indipendente di questo checkpoint. [Risultati e geometria](results/arc_recovery/locked/verified_four_way.json) · [Freeze finale](results/arc_recovery/locked/holdout_manifest.json)

| Timeout storico | Margine iniziale del corpo | Esito finale |
|---|---:|---|
| IMS 60404 | 28,9 mm | Giro pulito in 29,08 s |
| Monza 60404 | 18,1 mm | Giro pulito in 46,33 s |
| Austin 60404 | 6,3 mm | Timeout |
| Yas Marina 60404 | 9,8 mm | Timeout |
| IMS 60505 | Sovrapposto | Timeout |
| Oschersleben 60404 e 60505 | Entrambi sovrapposti | Due timeout |

**Restano aperti cinque timeout storici.** Due partono liberi con meno di un centimetro di margine. I tre inizialmente sovrapposti rimangono inclusi nelle prove. [Replay appaiati con controllo del corpo](results/arc_recovery/locked/verified_historical_timeouts.json)

Il grafo di inferenza è identico a quello di `arc_dynamic`. Cambiano 12.044 dei 28.427 coefficienti memorizzati, di cui 11.906 nell’inviluppo, 74 nella testa di velocità e 64 nella testa di sterzo. I [tensori esportati](artifacts/arc_recovery/nose_guard_weights.pth) coincidono con quelli del checkpoint. [Verifica dei pesi](results/arc_recovery/locked/weight_check.json)

## Modifiche ai pesi

Il riferimento è `arc_dynamic.pt`, la rete geometrica da 28.427 coefficienti. Il confronto di velocità usa anche la PPO `early_smooth.zip`, rispetto alla quale il tempo sul giro era più alto dell’8,23%. Tutte le prove usano il simulatore originale, un giro per episodio e il LiDAR istantaneo. La procedura di [weight-space programming](https://rikiyat.github.io/blog/weight-space-programming/) usa ipotesi sulla funzione dei tensori, modifiche analitiche e prove in simulazione. Le traiettorie servono a valutare le ipotesi, senza addestramento o fitting.

Sui 15 giri di sviluppo completati da entrambi, la rete geometrica percorreva solo lo 0,61% di strada in più. Il 46% dei campioni era limitato dalla frenata a fine arco. Ho cambiato i coefficienti delle funzioni a tratti che comandano la velocità. Con più di un metro visibile, il programma considera la velocità con cui l’auto può proseguire in una curva successiva. Consente più accelerazione laterale nelle curve di raggio intermedio quando c’è abbastanza visibilità. Solo l’arco rettilineo può superare i 10 m/s. Il compilatore ricalcola gli inviluppi della carrozzeria e lo sterzo per la deriva prevista a queste velocità.

Per la partenza, i due archi più corti usano la sagoma effettiva dell’auto e ristabiliscono progressivamente la riserva di 5 cm. Un disco inscritto conserva una riserva intorno al centro. Due verifiche successive hanno mostrato che il margine sui raggi vicini alle ruote anteriori era insufficiente. Il candidato finale `nose_guard.pt` protegge anche i raggi rivolti alla faccia anteriore, tenendo conto del rumore LiDAR e della distanza percorsa durante il ritardo dello sterzo. Applica questa correzione ai coefficienti dello spazio aperto per la partenza. `clear_straight.pt` è il confronto con la sola modifica del passo.

## Come si è arrivati alla verifica finale

1. Sui 105 casi già conosciuti, il primo candidato recupera **4/7** timeout con zero collisioni e 102 completamenti puliti. Sui nuovi seed 71101–71505 completa 100/105 giri e batte la PPO dell’1,74% sulle 91 triplette completate, ma collide ad Austin 71303 dopo 0,09 s. Il margine iniziale della carrozzeria è 4,45 mm. Questo candidato fallisce il criterio sulle collisioni. [Dati della prima verifica](results/arc_recovery/verified_three_way.json)
2. La seconda versione evita quella collisione fermandosi e conserva **3/7** recuperi storici. Su ulteriori 105 partenze, seed 71606–72010, completa 96 giri puliti ma collide ad Austin 71808 dopo 0,13 s. Il margine iniziale raster è 0,196 mm. Anche questa versione fallisce il criterio sulle collisioni. [Dati della seconda verifica](results/arc_recovery/confirmation/verified_three_way.json)
3. Il candidato finale e il confronto con la sola modifica del passo sono stati fissati prima di aprire i risultati dei seed 73101–73505. Le prove delle prime due verifiche sono quindi dati già osservati per quest’ultima scelta. [Manifest del confronto finale](results/arc_recovery/locked/holdout_manifest.json)

## Limiti delle partenze

Dei sette timeout originari, tre iniziano già con il rettangolo della carrozzeria sovrapposto a celle occupate. Sono IMS 60505 e Oschersleben 60404 e 60505. Per definizione questi tre non possono produrre un giro geometricamente pulito dal primo campione. La possibilità di liberare il veicolo dipende dalla manovra. Nei controlli cinematici di retromarcia, oltre il 99% del nuovo spazio spazzato dalle uscite praticabili ricade nel settore cieco del LiDAR. [Analisi delle manovre](results/arc_recovery/startup/reverse_audit/results.json)

Il numero di collisioni è quello del simulatore. Il controllo geometrico misura separatamente il corpo di 58 × 31 cm contro i pixel della mappa a ogni posa registrata, ogni 0,01 s. Tutti i timeout rimangono nel denominatore. Il tempo sul giro è confrontato soltanto sulle stesse partenze completate dai modelli indicati. Le misure non coprono il movimento tra due campioni o la posa successiva all’ultimo passo terminale.

## File per la riproduzione

- [Compilatore del passo](experiments/arc_recovery_weights.py), [inviluppi di partenza](experiments/arc_launch_weights.py), [riserva laterale](experiments/arc_launch_guard.py) e [riserva anteriore](experiments/arc_nose_guard.py).
- [Verificatore finale](experiments/verify_arc_locked.py) e [risultati di sviluppo delle manovre](results/arc_recovery/startup/summary.json).

Riproduzione del test con le copie pubbliche: [istruzioni](REPRODUCING.md).
