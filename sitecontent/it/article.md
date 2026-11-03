# Programmare i pesi per correre in F1TENTH

Tommaso Patriti · Nota sperimentale · 3 novembre 2026

**Una rete geometrica con 28.427 coefficienti ha completato 95 giri su 105 senza collisioni segnalate, con 10 timeout.** Sulle 86 partenze completate anche dai due riferimenti, il tempo sul giro è sceso del 9,91% rispetto alla rete geometrica precedente e dell’1,73% rispetto alla PPO già modificata.

Con Codex e GPT-6 Astra abbiamo programmato direttamente i tensori di una rete che riceve 1.080 raggi LiDAR. I pesi descrivono lo spazio occupato dall’auto lungo 17 curvature e la velocità compatibile con la pista visibile. Abbiamo rivisto le formule dopo le simulazioni e congelato i pesi prima del confronto finale. L’esperimento riprende il progetto dell’Università di Bologna e il metodo di *weight-space programming* di Takehi e colleghi. [Progetto F1TENTH originale](https://github.com/zucchero-sintattico/svs-f1tenth_gym) · [Takehi et al., 2026](https://rikiyat.github.io/blog/weight-space-programming/)

| Test finale su 21 piste × 5 nuove partenze | Giri completati | Collisioni | Timeout |
|---|---:|---:|---:|
| PPO modificata | 88 | 17 | 0 |
| Rete geometrica precedente | 93 | 0 | 12 |
| Rete geometrica finale | 95 | 0 | 10 |

Nei 95 giri del modello finale, l’ingombro completo dell’auto è rimasto separato dai muri della mappa in ogni posa controllata a intervalli di 0,01 s. La nuova manovra ha recuperato due dei sette timeout storici. Il test misura la guida simulata su un giro, con partenze e rumore nuovi su piste note. [Risultati finali e tentativi scartati](phase6/) · [Prompt e protocollo](methods/) · [Codice, pesi e dati](https://github.com/Ro0t-set/f1tenth-weight-space-racing)
