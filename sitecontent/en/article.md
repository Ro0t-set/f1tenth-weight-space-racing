# Programming weights to race in F1TENTH

Tommaso Patriti · Experimental note · 3 November 2026

**A geometric network with 28,427 coefficients finished 95 of 105 laps, with zero simulator-reported collisions and 10 timeouts.** On the 86 starts also completed by both reference controllers, it cut mean paired lap time by 9.91% relative to the previous geometric network and by 1.73% relative to the previously edited PPO policy.

Using Codex with GPT-6 Astra, we programmed the tensors of a network that takes 1,080 LiDAR rays as input. Its weights encode the car’s swept footprint over 17 curvatures and the speed it can carry through the visible track. We revised the formulas after simulation runs and froze the weights before the final comparison. The experiment builds on the University of Bologna racing project and the weight-space programming method of Takehi and colleagues. [Original F1TENTH project](https://github.com/zucchero-sintattico/svs-f1tenth_gym) · [Takehi et al., 2026](https://rikiyat.github.io/blog/weight-space-programming/)

| Final test on 21 tracks × 5 new starts | Completed laps | Collisions | Timeouts |
|---|---:|---:|---:|
| Edited PPO | 88 | 17 | 0 |
| Previous geometric network | 93 | 0 | 12 |
| Final geometric network | 95 | 0 | 10 |

On all 95 completed laps, the entire car footprint remained clear of occupied map pixels at every recorded pose, sampled every 0.01 s. The launch edit recovered two of seven historical timeouts. The test measures single-lap simulation performance under new starts and sensor noise on familiar tracks. [Final results and rejected edits](phase6/) · [Prompts and protocol](methods/) · [Code, weights and data](https://github.com/Ro0t-set/f1tenth-weight-space-racing)
