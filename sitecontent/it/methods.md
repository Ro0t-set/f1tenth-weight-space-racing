# Protocollo, modello e prompt

L’esperimento si è svolto il 3 novembre 2026, ora italiana. Tommaso Patriti ha assegnato gli obiettivi e i vincoli. Codex ha esaminato il codice, scritto i compilatori dei pesi, eseguito i rollout e preparato i confronti. I metadati della sessione identificano il modello che ha coordinato il lavoro come **GPT-6 Astra** (`gpt-6-astra`), con ragionamento `high` nelle prime fasi e `ultra` nelle successive.

Secondo la stima dell’autore del 3 novembre 2026, la sessione con Astra ha utilizzato circa il 20% della quota settimanale del suo account Pro. Il consumo in token e il tempo di calcolo non sono stati misurati.

## Richieste effettive

Estratti dei prompt originali, in ordine cronologico. Gli estratti mantengono la formulazione dell’utente.

1. «Voglio vedere se sei in grado di migliorare il modello, modificando i pesi row, come nel lavoro allegato.»
2. «voglio che vada più veloce, che non si schianti e che sappia driftare.»
3. «Mantieni il progetto attuale: solo modifiche ai pesi»
4. «Continua a migliorare i pesi: prova a ridurre ancora gli schianti senza perdere velocità»
5. «sei in grado di generare una rete da 0? più generale e snella, scrivendo direttamente i pesi»
6. «Continua sulla rete nuova: prova a recuperare l’8,2% di velocità e risolvere i 7 timeout senza aumentare gli schianti, sempre scrivendo direttamente i pesi, senza training»

## Disegno sperimentale

La prima serie parte dal checkpoint PPO del progetto di Manuel Andruccioli, Tommaso Patriti e Giacomo Totaro. La seconda costruisce un attore geometrico da zero. I coefficienti provengono da formule sui raggi LiDAR, sull’ingombro del veicolo e sul modello dinamico. I rollout orientano la scelta e la revisione manuale delle formule. Il controllore risultante usa soltanto il LiDAR durante la guida. [Relazione originale del progetto](https://github.com/zucchero-sintattico/svs-f1tenth_gym/blob/9381a13eec6b182ff38e4fba55a105cf94219da6/report/index.tex) · [Metodo di riferimento](https://rikiyat.github.io/blog/weight-space-programming/)

Per ogni confronto, i controller condividono pista, posa iniziale e seed del rumore. Un successo richiede almeno il 99% dei waypoint in ordine e un attraversamento della partenza senza collisione. Il limite è 200 secondi simulati. La verifica conclusiva congela gli hash e usa cinque nuovi seed su ciascuna delle 21 piste. Due verifiche precedenti hanno respinto candidati dopo collisioni ad Austin. Il quarto modello dell’ultimo confronto isola la sola modifica della velocità. [Tutti i confronti](../phase6/)

Il tempo riportato è la media di `100 × (tempo candidato / tempo riferimento − 1)` calcolata sugli stessi giri completati. Collisioni e timeout rimangono nel denominatore dei completamenti. Un audit separato confronta un rettangolo di 58 × 31 cm con i pixel occupati a ogni posa registrata prima dell’azione. La risoluzione della mappa, il passo di 0,01 s e la fisica degli pneumatici limitano le conclusioni su contatti reali e drift controllato. [Audit delle traiettorie](../phase4/)

<h2 id="media">Materiale supplementare</h2>

<figure class="study-figure"><a href="results/article/lidar-it.svg"><img src="results/article/lidar-it.svg" alt="Una scansione di Budapest a 6,10 secondi. In alto si vedono tutti i 1.080 raggi. Il dettaglio in centimetri mostra i 40 valori usati dal nuovo neurone per misurare lo spazio a sinistra."></a><figcaption><strong>Figura S1. Segnale LiDAR a Budapest.</strong> La scansione registrata a 6,10 s comprende 1.080 raggi. Il pannello inferiore mostra le distanze dei raggi da 880 a 919 utilizzati dal circuito di correzione.</figcaption></figure>

<figure class="study-figure"><video src="results/article/trajectory-lap-it.mp4" poster="results/article/trajectory-lap-it-poster.jpg" controls muted playsinline preload="metadata" aria-label="Intero giro di Budapest con le due traiettorie sovrapposte"></video><figcaption><strong>Video S1. Budapest, giro completo.</strong> Le traiettorie della PPO originale e della variante con correzione dello sterzo sono sincronizzate sul tempo simulato. Riproduzione a velocità quadrupla.</figcaption></figure>

<figure class="study-figure"><a href="results/article/track-it.svg"><img src="results/article/track-it.svg" alt="Traiettorie e carrozzerie nella curva di Sochi"></a><figcaption><strong>Figura S2. Ingombro del veicolo nella curva di Sochi.</strong> Il confronto tra la sagoma e le celle occupate della mappa distingue le due traiettorie nella zona della collisione.</figcaption></figure>

<figure class="study-figure"><a href="results/article/pace-it.svg"><img src="results/article/pace-it.svg" alt="Tempi relativi sulle 86 partenze completate dai tre controller. Il modello finale è più rapido della rete geometrica precedente in 86 casi e della PPO modificata in 62."></a><figcaption><strong>Figura S3. Tempi appaiati del controllore geometrico.</strong> Ciascun punto rappresenta una delle 86 partenze completate dai tre controllori. I pannelli adottano scale verticali diverse.</figcaption></figure>
