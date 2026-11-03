# Repairing a steering response near the wall

In final testing the fast repair recovers 16 episodes and loses three against the original PPO. Mean time falls by 2.01% on 164 paired finishes. The repair without acceleration isolates the steering change. The cautious policy from phase one retains the most finishes.

| Model | Completed laps | Collisions | Paired time vs. original |
| --- | ---: | ---: | ---: |
| Original | 167/210 | 43 | baseline |
| Previous cautious model | 184/210 | 26 | +3.78% |
| Repair, unchanged speed setting | 179/210 | 31 | -0.00% |
| Repair +0.2 m/s, primary candidate | 180/210 | 30 | -2.01% |

![Finishes and times with the steering repair](results/ultra/comparison.png)

## Distinguishing a steering error from a hairpin

First-layer neurons 41 and 61 contribute to extreme positive steering, including on successful hairpins. In problematic terminal samples, the left wall is 0.26–0.32 m away. In successful hard-steering samples, the closest observed wall is 0.441 m away. The new circuit combines the internal activations with a second signal, the mean distance reported by left-side rays 880–919.

With a 0.4 m threshold, the combination of a nearby wall, positive h41 and negative h61 reduces the steering command. Two nearly constant units carry the circuit. Overall, 1,276 scalars change. The faster version changes just one bias relative to the repair, equivalent to +0.2 m/s. Across 6,889 observations, predicted and implemented outputs differ by at most 8.7 × 10⁻⁷ in normalized units.

## Development and comparison

| Edit | Completions (original 10/21) | Paired lap time |
| --- | ---: | ---: |
| `angular_smooth` | 11/21 | -0.063% |
| `panic_gate` | 12/21 | +0.067% |
| `wall_panic` | 13/21 | -0.053% |
| `wall_panic_fast` | 12/21 | -2.030% |

Halving the temperature of four neurons introduces a left bias. Transplanting an earlier steering head increases peaks. These hypotheses are rejected before rollouts. The four variants in the table account for 84 episodes on seven development tracks. Hashes identify the four final checkpoints before 840 episodes are run, using ten fresh seeds from 40101 to 41010 on each track.

Each episode lasts up to 200 simulated seconds. Finishing requires visiting at least 99% of the waypoints in order and crossing the start line without a simulator collision. Models share starting poses and LiDAR noise. Times compare laps completed from the same starts by the specified models. A negative value means a faster lap.

Both the original and primary candidate collide 13 times within 0.10 s. On completed laps, countersteer with sideslip ≥5° at speed ≥3 m/s lasts at most 0.14 s, below the 0.5 s threshold. The collision detector projects velocity along the rays while ignoring sideslip angle β, although the motion includes β. This limits interpretation of high-slip events.

## Independent evaluation audit

The evaluator resets the racing line, counters and steering buffer for every episode. The seed controls both the start and LiDAR noise. Initial headings agree with the tangent of the racing line on all 21 tracks, with the 95th percentile of absolute error below 0.03 radians. Telemetry reproduces the outcomes of 15 control episodes. Each model runs in a separate process because the LiDAR simulator shares its map at class level.

In phase two’s original-policy test, 12 of 45 collisions occurred within 0.10 s and 16 within 1 s. An early crash can depend on the starting pose, but inevitability requires a case-by-case check. The manifest hashes designate the fast repair as primary and the steering-only variant as its comparator before testing.

## Finishes and times by track

| Track | Original | Cautious | Repair | Faster repair | Paired time, faster repair vs. original |
| --- | ---: | ---: | ---: | ---: | ---: |
| Austin | 9/10 | 9/10 | 9/10 | 9/10 | -2.00% |
| BrandsHatch | 10/10 | 10/10 | 10/10 | 10/10 | -2.01% |
| Budapest | 2/10 | 10/10 | 10/10 | 10/10 | -2.16% |
| Catalunya | 10/10 | 10/10 | 10/10 | 10/10 | -1.99% |
| Hockenheim | 10/10 | 10/10 | 10/10 | 10/10 | -2.10% |
| IMS | 4/10 | 4/10 | 4/10 | 4/10 | -2.05% |
| Melbourne | 10/10 | 10/10 | 10/10 | 10/10 | -2.00% |
| MexicoCity | 10/10 | 10/10 | 10/10 | 10/10 | -1.97% |
| Monza | 7/10 | 8/10 | 5/10 | 6/10 | -1.84% |
| MoscowRaceway | 10/10 | 10/10 | 10/10 | 9/10 | -2.12% |
| Nuerburgring | 10/10 | 10/10 | 10/10 | 10/10 | -2.03% |
| Oschersleben | 2/10 | 7/10 | 7/10 | 7/10 | -2.53% |
| Sakhir | 10/10 | 10/10 | 10/10 | 10/10 | -2.04% |
| SaoPaulo | 10/10 | 10/10 | 10/10 | 10/10 | -2.00% |
| Sepang | 10/10 | 10/10 | 10/10 | 10/10 | -2.00% |
| Silverstone | 10/10 | 10/10 | 10/10 | 10/10 | -1.99% |
| Sochi | 0/10 | 0/10 | 0/10 | 0/10 | — |
| Spa | 6/10 | 9/10 | 7/10 | 8/10 | -1.93% |
| Spielberg | 10/10 | 10/10 | 10/10 | 10/10 | -1.98% |
| YasMarina | 7/10 | 7/10 | 7/10 | 7/10 | -2.01% |
| Zandvoort | 10/10 | 10/10 | 10/10 | 10/10 | -1.93% |

## Data and reproduction

- [Circuit implementation](experiments/ultra_weights.py)
- [Test manifest](results/ultra/holdout_manifest.json)
- [Primary candidate results](results/ultra/comparison_fast.json)
