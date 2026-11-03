# Protocol, model and prompts

The experiment took place on 3 November 2026, local time in Italy. Tommaso Patriti specified the goals and constraints. Codex inspected the code, wrote the weight compilers, ran the simulations and prepared the comparisons. Session metadata identifies the coordinating model as **GPT-6 Astra** (`gpt-6-astra`), using `high` reasoning effort in the first stages and `ultra` in later stages.

## User prompts

English translations of excerpts from the original Italian prompts, in chronological order. The Italian edition preserves the user’s wording. [Original excerpts](../../it/methods/)

1. “I want to see if you can improve the model by changing its raw weights, as in the linked work.”
2. “I want it to go faster, avoid crashing and be able to drift.”
3. “Keep the current project and only change the weights.”
4. “Continue improving the weights. Try to reduce crashes further without losing speed.”
5. “Can you generate a network from scratch, more general and smaller, by writing the weights directly?”
6. “Continue with the new network. Try to recover the 8.2% in speed and resolve the seven timeouts without increasing crashes, still writing the weights directly, without training.”

## Experimental design

The first series starts with the PPO checkpoint from the project by Manuel Andruccioli, Tommaso Patriti and Giacomo Totaro. The second builds a geometric actor from scratch. Its coefficients come from formulas using LiDAR rays, the car footprint and the vehicle dynamics. Simulation feedback guides the selection and revision of formulas. The resulting policy receives only LiDAR at inference. [Original project report](https://github.com/zucchero-sintattico/svs-f1tenth_gym/blob/9381a13eec6b182ff38e4fba55a105cf94219da6/report/index.tex) · [Methodological reference](https://rikiyat.github.io/blog/weight-space-programming/)

Controllers share the track, starting pose and noise seed for each comparison. Success requires at least 99% of ordered waypoints and a start-line crossing without a collision. The time limit is 200 simulated seconds. The final verification freezes checkpoint hashes and uses five fresh seeds on each of 21 tracks. Two earlier verification rounds rejected candidates after collisions at Austin. A fourth controller in the last comparison isolates the speed edit. [Full comparisons](../phase6/)

Reported lap time change is the mean of `100 × (candidate time / reference time − 1)` over the same completed starts. Collisions and timeouts stay in the completion denominator. A separate audit checks the full 58 × 31 cm rectangle against occupied pixels at each recorded pre-action pose. Map resolution, 0.01 s sampling and the tyre model limit conclusions about real-world contact and controlled drift. [Trajectory audit](../phase4/)
