# Protocollo, modello e prompt

L’esperimento si è svolto il 3 novembre 2026, ora italiana. Tommaso Patriti ha assegnato gli obiettivi e i vincoli. Codex ha esaminato il codice, scritto i compilatori dei pesi, eseguito i rollout e preparato i confronti. I metadati della sessione identificano il modello che ha coordinato il lavoro come **GPT-6 Astra** (`gpt-6-astra`), con ragionamento `high` nelle prime fasi e `ultra` nelle successive.

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
