# Protocol, model and prompts

The experiment took place on 3 November 2026, local time in Italy. Tommaso Patriti specified the goals and constraints. Codex inspected the code, wrote the weight compilers, ran the simulations and prepared the comparisons. Session metadata identifies the coordinating model as **GPT-6 Astra** (`gpt-6-astra`), using `high` reasoning effort in the first stages and `ultra` in later stages.

On 3 November 2026 the author estimated that the Astra session used approximately 20% of the weekly allowance on his Pro account. Token use and compute time were not measured.

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

<h2 id="media">Supplementary material</h2>

<figure class="study-figure"><a href="results/article/lidar-en.svg"><img src="results/article/lidar-en.svg" alt="One Budapest scan at 6.10 seconds. The top panel shows all 1,080 beams. The detail in centimetres shows the 40 readings the new neuron uses to measure clearance on the left."></a><figcaption><strong>Figure S1. LiDAR input in Budapest.</strong> The scan recorded at 6.10 s contains 1,080 beams. The lower panel shows the ranges for beams 880 to 919 used by the steering repair.</figcaption></figure>

<figure class="study-figure"><video src="results/article/trajectory-lap-en.mp4" poster="results/article/trajectory-lap-en-poster.jpg" controls muted playsinline preload="metadata" aria-label="Full Budapest lap with both recorded trajectories"></video><figcaption><strong>Video S1. Full Budapest lap.</strong> The trajectories of the original PPO and the steering-only variant are synchronized by simulation time. Playback at four times the recorded speed.</figcaption></figure>

<figure class="study-figure"><a href="results/article/track-en.svg"><img src="results/article/track-en.svg" alt="Trajectories and vehicle footprints in the Sochi corner"></a><figcaption><strong>Figure S2. Vehicle footprint in the Sochi corner.</strong> Comparing the body outline with occupied map cells distinguishes the two trajectories in the vicinity of the collision.</figcaption></figure>

<figure class="study-figure"><a href="results/article/pace-en.svg"><img src="results/article/pace-en.svg" alt="Relative lap times for the 86 starts completed by all three controllers. The final network beats its geometric predecessor on 86 laps and the edited PPO on 62."></a><figcaption><strong>Figure S3. Paired lap times for the geometric controller.</strong> Each point represents one of 86 starts completed by the three controllers. The vertical scales differ between panels.</figcaption></figure>
