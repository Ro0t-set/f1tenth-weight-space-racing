# Reproduction and data inventory · Riproduzione e inventario

## Runtime

Run from the repository root. The experiment used Python 3.11.14 on an Apple Silicon CPU, PyTorch 2.2.2, SB3 2.2.1, NumPy 1.23.5 and Gym 0.23.1. Floating-point and simulator outcomes on other architectures can differ. The package pins are in [requirements-lock.txt](requirements-lock.txt).

~~~sh
bash setup.sh
bash scripts/build_ppo.sh comparison
~~~

Setup checks out the original simulator and pretrained policy at commit `9381a13eec6b182ff38e4fba55a105cf94219da6` and verifies the track submodule at `3f581789c749261ae36fc4fef19a81372acc3ecf`. The evaluator imports the simulator from that checkout. On headless Linux the legacy Pyglet/OpenGL import may need the OS GL/GLU libraries. On macOS the published run used the native ARM64 Python interpreter. No ROS master or rendering is required.

The fast build produces the three PPO ZIPs in the final controller’s comparison lineage, including `early_smooth.zip`. For all nineteen historical PPO edits across phases 1–4, use the following command. It generates the development observation traces required by the original editor checks, verifies every ZIP against its historic SHA-256, then places the verified files under `artifacts/`. The temporary build outputs stay in `reruns/`.

~~~sh
bash scripts/build_ppo.sh all
~~~

## Rerun an episode ledger

The release includes the episode records from the separate development and evaluation cohorts. Timeouts and collisions are in the denominators. Any JSON containing `checkpoint`, `max_steps`, `sha256` and `rows` is a replayable ledger. These commands run all recorded pairs in each file. To shorten a run, add e.g. `--maps Austin --seeds 73101` for a ledger containing that start. Fresh outputs go in a separate timestamped directory under `reruns/`. The runner checks the published input hashes and compares the new starting poses, outcomes, step counts and lap times to the archived rows. Use `--footprints` for dense pre-action traces, per-episode clearances and sampled contact counts.

~~~sh
# Phase 1, including the original 17-track holdout and final cautious policy
.venv/bin/python scripts/replay.py results/holdout_edited.json
.venv/bin/python scripts/replay.py results/final_cautious.json
# Phase 2, rejected faster PPO
.venv/bin/python scripts/replay.py results/racing_v2/final_curvature.json
# Phase 3, wall-steering gate plus speed bias
.venv/bin/python scripts/replay.py results/ultra/final_fast.json
# Phase 4, smoothed PPO and geometric audit
.venv/bin/python scripts/replay.py results/trajectory_v4/final_candidate.json --footprints
# Phase 5, new network slower on common finishes
.venv/bin/python scripts/replay.py results/from_scratch/final_candidate.json --footprints
# Phase 6, both earlier failed confirmation attempts
.venv/bin/python scripts/replay.py results/arc_recovery/final_candidate.json --maps Austin --seeds 71303 --footprints
.venv/bin/python scripts/replay.py results/arc_recovery/confirmation/final_candidate.json --maps Austin --seeds 71808 --footprints
# Four frozen controllers on the independent final starts
for model in previous ppo candidate speed; do
  .venv/bin/python scripts/replay.py "results/arc_recovery/locked/final_${model}.json" --footprints
done
~~~

Preceding `final_previous`, `final_baseline`, `final_original` and other comparator ledgers live alongside the candidate. Raw geometry can take substantial time and disk space for full cohorts. For the seven historical timeout replays see the per-case table with map, seed and initial overlap in [verified_historical_timeouts.json](results/arc_recovery/locked/verified_historical_timeouts.json) and the corresponding [recorded episode ledger](results/arc_recovery/retained/nose_historical.json).

## Inventory and integrity

* **Original data.** All 216 JSON result files, including episode ledgers, cohort freezes, per-map and paired summaries, rejected trials, startup diagnostics and identically seeded controls. Five CSV files record full-body audit outcomes per episode. The original Python generators, simulator harness, geometry routines and supplementary analysis scripts are under `experiments/` and `results/`. [Final freeze](results/arc_recovery/locked/holdout_manifest.json)
* **Executable models.** The release contains twenty from-scratch and recovery TorchScript checkpoints, twelve available raw tensor exports and the metadata for the PPO edits. All non-debug members of each public TorchScript archive are byte-identical to the recorded run. Two debug tables use project-relative source paths. On the release machine, the original and public archives for each of the twenty models produced identical outputs on 240 deterministic test scans, with the same forward code and every stored tensor equal. Historical and public SHA-256 are recorded separately. The twelve raw tensor exports retain their original SHA-256. [Checkpoint catalog](artifacts/checkpoints.json)
* **Archived records.** Absolute project paths in the distributed JSON are relative to the project root. Two diagnostic TTC values with no finite time-to-contact use the string `"Infinity"`. Numerical run data and frozen checkpoint hashes are preserved. The SHA-256 mapping covers all JSON records whose bytes changed for publishing. The historic `verify_arc_*.py` programs expect literal original container/JSON hashes and dense traces. Use `scripts/check_archive.py` for the release, or `scripts/replay.py --footprints` for a fresh full-body measurement. [Public and historic file hashes](artifacts/public_file_hashes.json)
* **Regenerated inputs.** Setup obtains the simulator, original PPO weights and track assets from their pinned repositories. The simulator checkout carries an MIT license. The track checkout carries GPLv3. The pretrained model has no separate model-specific license in the pinned training directory. The baseline, trained-model ZIP derivatives, map rasters, racelines, upstream report and the reference blog are obtained from their original sources. The public release contains the PPO editor programs. [Simulator and baseline](https://github.com/zucchero-sintattico/svs-f1tenth_gym/tree/9381a13eec6b182ff38e4fba55a105cf94219da6) · [Track sources](https://github.com/f1tenth/f1tenth_racetracks/tree/3f581789c749261ae36fc4fef19a81372acc3ecf) · [Weight-Space Programming](https://rikiyat.github.io/blog/weight-space-programming/)
* **Large files.** Observation and pose traces, caches, runtime logs, environments and generated map-overlay graphics are excluded from the numerical archive. Generate dense traces with the replay command and observation traces with `experiments/evaluate.py --trace`. The published numerical results can be inspected without downloading those files.

Il pacchetto conserva tutti i risultati JSON e i cinque CSV, compresi gli episodi falliti e i manifest congelati. I checkpoint PPO si ricostruiscono dal progetto originale. I modelli TorchScript pubblici hanno gli stessi tensori e lo stesso codice dei modelli congelati. Gli hash pubblici cambiano soltanto per il confezionamento con percorsi di debug relativi. Per verificare i numeri si usa `scripts/check_archive.py`; per misurare nuovamente il comportamento si usa `scripts/replay.py`. Le nuove misure vengono salvate in `reruns/`.

The historical PPO study was written by Manuel Andruccioli, Tommaso Patriti and Giacomo Totaro at the University of Bologna. The six phases in this repository are subsequent simulation experiments. [Original project report](https://github.com/zucchero-sintattico/svs-f1tenth_gym/blob/9381a13eec6b182ff38e4fba55a105cf94219da6/report/index.tex)
