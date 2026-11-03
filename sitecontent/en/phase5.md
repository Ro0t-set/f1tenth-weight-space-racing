# Building a network from vehicle geometry

Across 21 tracks and five fresh seeds per track, from 60101 to 60505, the analytical network `arc_dynamic` completes 98 laps. The edited PPO from the previous phase finishes 95. At Sochi the result rises from zero finishes to five. The analytical network takes 8.23% longer on average over 92 paired finishes. All seven of its timeouts make less than 1% progress.

| Outcome | Previous edited PPO | New geometric network |
| --- | ---: | ---: |
| Completed laps | 95/105 | **98/105** |
| Simulator collisions | 10 | **0** |
| Timeout | 0 | **7** |
| Completed laps without raster contact at sampled poses | 89 | **98** |
| Sochi | 0/5 | **5/5** |
| Time on 92 paired completions | baseline | **+8.23%** |

## From LiDAR rays to arcs

Taking the minimum over each group of six rays reduces the scan to 180 sectors. For 17 curvatures and nine horizons from 0.5 to 11 m, the compiler computes the body envelope with a 5 cm reserve, incorporating steady-state sideslip from the vehicle equations. The network selects a direction with clearance and interpolates only with adjacent directions. This avoids averaging two distant openings into a blocked direction between them.

Piecewise ReLU heads use braking and lateral-acceleration references of 6 and 7 m/s² and a top command of 10 m/s. The equations generate coefficients ahead of inference. Runtime takes the stored tensors and one LiDAR scan. The TorchScript module, adapter, single-observation and batched calculations agree on 479 inputs.

## Network cost and rejected variants

| Measure | Previous PPO actor | New geometric network |
| --- | ---: | ---: |
| Actor coefficients | 73,474 | **28,427** |
| Float32 coefficient storage | 293,896 bytes | **113,708 bytes** |
| Full `predict`, local median | 55.4 µs | **49.8 µs** |
| Network alone, local median | **31.3 µs** | 46.5 µs |

Stored coefficients, including geometry tensors, fall by 61.3%. The benchmark uses one thread, batch size one, 128 warm-up calls and five runs of 1,000 calls. The simpler adapter improves end-to-end median latency while the network computation alone takes longer.

| Program | Development starts | Outcome |
| --- | --- | --- |
| `arc_soft`, no sideslip, global selection | 3 | 0 finishes, 3 collisions |
| `arc_mode`, no sideslip, local selection | 3 | 0 finishes, 3 collisions |
| `arc_dynamic`, analytical sideslip | 21 | **18 finishes, 0 collisions, 3 timeouts** |
| `arc_dynamic_pace`, lateral reference 8 m/s², top command 11 m/s | 21 | 15 finishes, 3 collisions, 3 timeouts (rejected) |

## Measured clearances

Across 210 episodes and 1,083,184 poses, all 98 finishes for the analytical network have positive raster clearance, with a minimum of 2.56 cm. Three timeouts already overlap the wall at launch and account for 60,000 overlapping poses. On paired finishes the fraction of poses within 10 cm of the wall rises from 0.203% to 4.814%. At Sochi, seed 60101, the PPO crashes at 24.52 s and the new network finishes in 58.23 s.

On the 14 tracks excluded from this network’s development, it finishes 67/70 against the PPO’s 68/70 and takes 8.55% longer. These maps were known to the project. Steady-state sideslip approximates transients. Choosing the first index to break a tie can introduce steering asymmetry. Clearance between recorded poses and after the last step remains unknown.

Each episode lasts up to 200 simulated seconds. Finishing requires visiting at least 99% of the waypoints in order and crossing the start line without a simulator collision. Models share starting poses and LiDAR noise. Times compare laps completed from the same starts by the specified models. A negative value means a faster lap.

## Independent network and lap checks

Of the 28,427 coefficients, 28,130 are nonzero. The TorchScript artifact occupies 122,271 bytes. Six symmetric control scenes preserve steering symmetry, while two with tied scores yield normalized residuals of 0.5661 and 0.8025. In the 92 paired finishes, laps with contact fall from five to zero, but samples within 20 cm of a wall rise from 0.6901% to 26.1239%. At Sochi 60101, recorded minimum clearances are 2.10 and 35.67 mm. The PPO’s interrupted lap and Arc’s complete lap cover different distances.

## Completed laps by track

| Track | `early_smooth` | `arc_dynamic` |
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

## Data and reproduction

- [Network compiler](experiments/from_scratch.py)
- [TorchScript network](artifacts/from_scratch/arc_dynamic.pt)
- [Weight, symmetry and timing audit](results/from_scratch_audit/arc_dynamic_audit.json)
- [Contacts by outcome](results/from_scratch/final_footprints_by_outcome.json)
