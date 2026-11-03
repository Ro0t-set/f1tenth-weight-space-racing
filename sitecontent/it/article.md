# Come Astra ha scritto i pesi di una rete che guida

Tommaso Patriti · Studio sperimentale · 3 novembre 2026

Ho chiesto a GPT-6 Astra di correggere lo sterzo di un’auto simulata intervenendo sui pesi della sua rete neurale. Poi le ho chiesto di scrivere una rete da zero. Con pochi prompt e circa **il 20% della mia quota settimanale Pro**, secondo la mia stima del 3 novembre 2026, ho ottenuto due controllori che si possono scaricare e rimettere in pista.

<figure id="trajectory-comparison" class="study-figure"><video src="results/article/trajectory-corner-it.mp4" poster="results/article/trajectory-corner-it-poster.jpg" controls autoplay loop muted playsinline preload="metadata" aria-label="Confronto animato delle traiettorie prima e dopo la modifica dei pesi"></video><figcaption><strong>Budapest, al rallentatore.</strong> Rosso e verde partono dalla stessa posa. A 6,50 secondi la PPO originale urta il muro. Con i pesi corretti l’auto supera la curva. Replay di sviluppo a metà velocità.</figcaption></figure>

## Dentro la sterzata sbagliata

A Budapest l’auto ha il muro alla sua sinistra e chiede ancora tutto sterzo a sinistra. Astra ha letto i pesi della rete addestrata con PPO, osservato quali neuroni si attivavano in curva e provato le modifiche nel simulatore. Il mio vincolo, in uno dei sei prompt documentati, era «solo modifiche ai pesi». [I prompt e il protocollo](methods/)

La correzione sta in due neuroni riutilizzati. Il primo legge **40 raggi laser rivolti a sinistra**. Il secondo attenua una sterzata forte quando il muro è vicino. Ecco tre righe del programma che scrive il primo neurone. [Codice della modifica](experiments/ultra_weights.py)

```python
w1[15, :] = 0.0
w1[15, 880:920] = -7.5
b1[15] = -292.0
```

<figure class="study-figure"><a href="results/article/lidar-it.svg"><img src="results/article/lidar-it.svg" alt="Una scansione di Budapest a 6,10 secondi. In alto si vedono tutti i 1.080 raggi. Il dettaglio in centimetri mostra i 40 valori usati dal nuovo neurone per misurare lo spazio a sinistra."></a><figcaption>Una scansione di Budapest a 6,10 secondi. In alto si vedono tutti i 1.080 raggi. Il dettaglio in centimetri mostra i 40 valori usati dal nuovo neurone per misurare lo spazio a sinistra.</figcaption></figure>

<figure class="study-figure"><a href="results/article/repair-it.svg"><img src="results/article/repair-it.svg" alt="Budapest, seed 1101. Traiettorie della PPO originale e corretta e confronto fra i comandi di sterzo sulla stessa sequenza di scansioni."></a><figcaption>A 6,10 secondi, dando alle due reti la stessa scansione laser, il comando di sterzo passa da +1,000 a +0,445. Le linee sulla mappa mostrano come proseguono le due corse.</figcaption></figure>

## Quanto cambia su 210 partenze?

A pesi congelati, la sola correzione dello sterzo porta i giri completati da **167 a 179**, quasi allo stesso passo. Aumentando anche il comando di velocità di 0,2 m/s, Astra arriva a **180 su 210**. La seconda versione cambia 1.276 valori ed è più veloce in tutti i 164 giri completati da entrambe le reti, del 2,01% in media.

<figure class="study-figure"><a href="results/article/raw-it.svg"><img src="results/article/raw-it.svg" alt="Su 210 partenze appaiate la PPO modificata recupera 16 giri e ne perde tre. I completamenti passano da 167 a 180."></a><figcaption>I colori raccontano dove funziona la modifica. Dei 16 giri recuperati, otto sono a Budapest e cinque a Oschersleben, entrambe usate in sviluppo. Sulle altre 19 piste il saldo è pari. Tre partenze prima riuscite finiscono con una collisione.</figcaption></figure>

<figure class="study-figure"><video src="results/article/trajectory-lap-it.mp4" poster="results/article/trajectory-lap-it-poster.jpg" controls autoplay loop muted playsinline preload="metadata" aria-label="Intero giro di Budapest con le due traiettorie sovrapposte"></video><figcaption>Il giro intero di Budapest a velocità 4×. La rete con la sola modifica allo sterzo taglia il traguardo a 47,13 secondi.</figcaption></figure>

## Una rete scritta da zero

Poi ho chiesto ad Astra di generare una rete da zero. Questa volta Astra ha scritto un programma che traduce la sagoma dell’auto e le equazioni del veicolo in **28.427 coefficienti**. Durante la guida la rete riceve una scansione laser e valuta 17 possibili curvature. Le prime tre prove finiscono contro il muro. Quando Astra include nei pesi la deriva prevista in curva, la rete supera tutte e tre. Seguono altre revisioni in simulazione, senza addestramento. [Dalle formule ai pesi](phase5/)

<figure class="study-figure" id="sochi"><video src="results/article/trajectory-overlay-lap-it.mp4" poster="results/article/trajectory-overlay-lap-it-poster.jpg" controls autoplay loop muted playsinline preload="metadata" aria-label="Ripresa ravvicinata delle tre auto sovrapposte a Sochi"></video><figcaption><strong>Sochi, la stessa partenza per tre auto.</strong> La PPO originale è rossa, la PPO modificata è verde e la rete scritta da zero è blu. Dopo l’urto, le auto restano ferme nell’ultima posa registrata.</figcaption></figure>

<figure class="study-figure"><a href="results/article/track-it.svg"><img src="results/article/track-it.svg" alt="Traiettorie e carrozzerie nella curva di Sochi"></a><figcaption>Il dettaglio della curva di Sochi. La sagoma della carrozzeria permette di vedere dove la PPO tocca una cella occupata e dove passa la rete finale.</figcaption></figure>

Su **105 nuove partenze**, la rete finale completa **95 giri**, con dieci timeout e zero collisioni segnalate. La PPO già migliorata ne completa 88, con 17 collisioni. Nei 95 arrivi della nuova rete, l’ingombro dell’auto resta separato dalle celle del muro in ogni posa registrata. Il margine più piccolo è 0,85 cm sulla mappa.

<figure class="study-figure"><a href="results/article/outcomes-it.svg"><img src="results/article/outcomes-it.svg" alt="Test conclusivo con quattro controller. La rete geometrica finale completa 95 giri puliti su 105, con zero collisioni segnalate e dieci timeout."></a><figcaption>Esiti sulle stesse 105 partenze per ciascuno dei quattro controllori. Ogni timeout conta come giro fallito.</figcaption></figure>

<figure class="study-figure"><a href="results/article/pace-it.svg"><img src="results/article/pace-it.svg" alt="Tempi relativi sulle 86 partenze completate dai tre controller. Il modello finale è più rapido della rete geometrica precedente in 86 casi e della PPO modificata in 62."></a><figcaption>Sulle 86 partenze completate dai tre controllori confrontati, la rete finale riduce il tempo medio appaiato dell’1,73% rispetto alla PPO migliorata e del 9,91% rispetto alla prima rete geometrica. Le scale dei pannelli sono diverse.</figcaption></figure>

## Fin dove arriva questa prova?

In una sessione Astra ha saputo inserire una regola leggibile in una rete addestrata e costruire un secondo controllore a partire dalla geometria. I pochi prompt misurano quanto ho dovuto specificare io. Tra una richiesta e l’altra, Astra ha scritto codice, osservato incidenti e scartato soluzioni. Resta aperta la domanda più interessante: con un’altra rete di partenza, quanto spesso riuscirebbe a trovare da sola una correzione altrettanto efficace?

Le prove coprono un giro alla volta su 21 piste note. Restano dieci partenze senza arrivo e resta da provare l’auto reale. Nel protocollo si trovano anche i tentativi falliti e la verifica successiva dei timeout. [Risultati completi](phase6/) · [Relazione F1TENTH originale, con Manuel Andruccioli e Giacomo Totaro (PDF)](output/pdf/original-f1tenth-report.pdf) · [Codice, pesi e dati](https://github.com/Ro0t-set/f1tenth-weight-space-racing)
