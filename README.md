# F1TENTH weight-space racing

**English.** GPT-6 Astra edited 1,276 scalar weights and biases in a pretrained PPO racing controller. Across 210 paired starts it raised completions from 167 to 180 and reduced simulator-reported crashes from 43 to 30. On all 164 starts where both policies finished, the edited one was faster, cutting lap time by 2.01% on average. A second experiment built a geometric controller from scratch. [Illustrated article](https://tommasopatriti.me/research/f1tenth-weight-space/en/)

**Italiano.** GPT-6 Astra ha riscritto 1.276 valori nei tensori di una PPO già addestrata. Su 210 partenze appaiate i completamenti salgono da 167 a 180 e le collisioni segnalate scendono da 43 a 30. La rete modificata è più veloce in tutti i 164 giri completati da entrambe, con una riduzione media del tempo del 2,01%. Un secondo esperimento costruisce un controllore geometrico da zero. [Articolo illustrato](https://tommasopatriti.me/research/f1tenth-weight-space/it/)

## Quick start · Come iniziare

Verify the published counts and paired lap times with Python alone. Per controllare conteggi e tempi appaiati basta Python.

~~~sh
python3 scripts/check_archive.py
~~~

Run one of the frozen starts with the public model and its geometric audit. Per ripetere una delle partenze congelate con il modello pubblico e il controllo della carrozzeria usare Python 3.11, Git e una shell Bash.

~~~sh
bash setup.sh
.venv/bin/python scripts/replay.py results/arc_recovery/locked/final_candidate.json --maps Sochi --seeds 73101 --footprints
~~~

[Reproduction commands and artifact inventory / Comandi e inventario](REPRODUCING.md) · [Final controller / Controllore finale](artifacts/arc_recovery/nose_guard.pt) · [Checkpoint digests / Hash](artifacts/checkpoints.json)

| Phase / Fase | Experiment / Esperimento | Evidence / Risultati |
|---|---|---|
| 1 | LiDAR clearance and pace / Spazio frontale e velocità | [17-track holdout](results/holdout_comparison.json) · [Final](RESULTS.md) |
| 2 | Faster PPO, more collisions / PPO più rapida, più collisioni | [Rejected candidate](RACING_RESULTS.md) |
| 3 | Targeted steering repair / Correzione mirata dello sterzo | [Frozen comparison](ULTRA_RESULTS.md) |
| 4 | Trajectories and full-body contacts / Traiettorie e contatti della carrozzeria | [420 episodes](TRAJECTORY_RESULTS.md) |
| 5 | From-scratch geometric network / Rete geometrica da zero | [105 starts per model](FROM_SCRATCH_RESULTS.md) |
| 6 | Pace and launch recovery / Velocità e partenze bloccate | [Final and failed attempts](ARC_RECOVERY_RESULTS.md) · [Historical timeouts](results/arc_recovery/locked/verified_historical_timeouts.json) |

These are single-car, single-lap simulations on known tracks. The geometric audit samples the 58 × 31 cm body at saved pre-action poses. Between-sample motion, the terminal post-action pose, physical racing and controlled tire drift are outside the measured evidence.

Le prove usano una sola auto, un giro per episodio e piste già disponibili. L’audit misura la carrozzeria di 58 × 31 cm alle pose registrate prima dell’azione. Il moto fra campioni, la posa successiva all’ultimo passo, la guida in pista reale e il drift controllato restano fuori dalle misure.
