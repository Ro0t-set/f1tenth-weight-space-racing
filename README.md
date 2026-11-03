# F1TENTH weight-space racing

**English.** Can hand-written changes to a driving policy improve its lap times or bring it home in one piece? These six simulator experiments start with a pretrained PPO actor, edit its tensors, then build a LiDAR-only policy from geometric coefficients. On 105 fresh starts the final controller completed 95 laps with no simulator collisions or sampled body contacts on those laps. Ten starts timed out. It was 1.73% quicker than the edited PPO on the 86 starts completed by all three reference controllers. [Research article](https://tommasopatriti.me/research/f1tenth-weight-space/en/)

**Italiano.** Quanto si può cambiare il comportamento di un’auto intervenendo sui pesi della rete? Le sei fasi partono da un attore PPO già addestrato e arrivano a un controllore costruito con coefficienti geometrici. In 105 nuove partenze il modello finale completa 95 giri, senza collisioni del simulatore né contatti del corpo nelle pose registrate di quei giri. Dieci partenze scadono. Sulle 86 partenze completate da tutti e tre i controllori di riferimento, il modello finale riduce il tempo medio appaiato dell’1,73% rispetto alla PPO modificata. [Articolo di ricerca](https://tommasopatriti.me/research/f1tenth-weight-space/)

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
