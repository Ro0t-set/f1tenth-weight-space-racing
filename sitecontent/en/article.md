# How Astra wrote the weights of a racing network

Tommaso Patriti · Experimental study · 3 November 2026

I asked GPT-6 Astra to fix a simulated car’s steering by editing the weights of its neural network. Then I asked it to write a network from scratch. With a handful of prompts and around **20% of my weekly Pro allowance**, by my estimate on 3 November 2026, I got two controllers that anyone can download and run.

<figure id="trajectory-comparison" class="study-figure"><video src="results/article/trajectory-corner-en.mp4" poster="results/article/trajectory-corner-en-poster.jpg" controls autoplay loop muted playsinline preload="metadata" aria-label="Animated comparison of recorded trajectories before and after the weight edit"></video><figcaption><strong>Budapest in slow motion.</strong> Red and green start from the same pose. At 6.50 seconds the original PPO hits the wall. The edited network clears the corner. Development replay at half speed.</figcaption></figure>

## Inside a bad turn

In Budapest the wall is on the car’s left and the network is still asking for full left steering. Astra read the weights of the PPO-trained network, inspected neuron activations in corners and tested edits in simulation. In one of the six documented prompts I restricted it to weight edits. [Prompts and protocol](methods/)

Astra reused two neurons. The first reads **40 left-facing laser beams**. The second softens a sharp turn when the wall is close. These three lines program the first neuron. [Weight-editing code](experiments/ultra_weights.py)

```python
w1[15, :] = 0.0
w1[15, 880:920] = -7.5
b1[15] = -292.0
```

<figure class="study-figure"><a href="results/article/lidar-en.svg"><img src="results/article/lidar-en.svg" alt="One Budapest scan at 6.10 seconds. The top panel shows all 1,080 beams. The detail in centimetres shows the 40 readings the new neuron uses to measure clearance on the left."></a><figcaption>One Budapest scan at 6.10 seconds. The top panel shows all 1,080 beams. The detail in centimetres shows the 40 readings the new neuron uses to measure clearance on the left.</figcaption></figure>

<figure class="study-figure"><a href="results/article/repair-en.svg"><img src="results/article/repair-en.svg" alt="Budapest, seed 1101. Original and repaired PPO paths, with steering commands compared on the same sequence of laser scans."></a><figcaption>At 6.10 seconds, giving both networks the same laser scan changes the steering command from +1.000 to +0.445. The lines on the map show the two subsequent runs.</figcaption></figure>

## How much changes across 210 starts?

With the weights frozen, the steering repair alone raises completions from **167 to 179** at almost the same pace. Adding 0.2 m/s to the speed command brings that to **180 out of 210**. This version changes 1,276 values. It is faster on all 164 laps both networks finish, cutting lap time by 2.01% on average.

<figure class="study-figure"><a href="results/article/raw-en.svg"><img src="results/article/raw-en.svg" alt="Across 210 paired starts the edited PPO recovers 16 laps and loses three. Completions rise from 167 to 180."></a><figcaption>Of 16 recovered laps, eight are in Budapest and five in Oschersleben, both used in development. Across the other 19 tracks the net gain is zero. Three previously successful starts end in collisions.</figcaption></figure>

<figure class="study-figure"><video src="results/article/trajectory-lap-en.mp4" poster="results/article/trajectory-lap-en-poster.jpg" controls autoplay loop muted playsinline preload="metadata" aria-label="Full Budapest lap with both recorded trajectories"></video><figcaption>The full Budapest lap at 4× speed. With the steering repair alone, the car crosses the line at 47.13 seconds.</figcaption></figure>

## A network written from scratch

Could Astra generate an entire network? This time it wrote a program that translates the car’s footprint and equations of motion into **28,427 coefficients**. At runtime the network takes a laser scan and evaluates 17 possible curvatures. The first three trials end at the wall. Once Astra accounts for the car’s predicted sideslip, the network finishes all three. Further revisions use simulation feedback without training. [From equations to weights](phase5/)

<figure class="study-figure" id="sochi"><video src="results/article/trajectory-overlay-lap-en.mp4" poster="results/article/trajectory-overlay-lap-en-poster.jpg" controls autoplay loop muted playsinline preload="metadata" aria-label="Close-up tracking shot of three overlaid cars at Sochi"></video><figcaption><strong>Sochi, three cars from the same start.</strong> Red is the original PPO, green the edited PPO and blue the network written from scratch. Cars that crash remain at their last recorded pose.</figcaption></figure>

<figure class="study-figure"><a href="results/article/track-en.svg"><img src="results/article/track-en.svg" alt="Trajectories and vehicle footprints in the Sochi corner"></a><figcaption>A close look at the Sochi corner. The car’s footprint shows where the PPO touches an occupied cell and where the final network passes.</figcaption></figure>

Across **105 new starts**, the final network finishes **95 laps**, with ten timeouts and zero reported collisions. The previously improved PPO finishes 88, with 17 collisions. On the new network’s 95 completed laps, the car’s footprint clears the occupied map cells at every recorded pose. Its smallest measured clearance is 0.85 cm on the map.

<figure class="study-figure"><a href="results/article/outcomes-en.svg"><img src="results/article/outcomes-en.svg" alt="Final test of four controllers. The final geometric actor finishes 95 clean laps from 105 starts, with zero simulator-reported collisions and ten timeouts."></a><figcaption>Outcomes on the same 105 starts for each of four controllers. Every timeout counts as a failed lap.</figcaption></figure>

<figure class="study-figure"><a href="results/article/pace-en.svg"><img src="results/article/pace-en.svg" alt="Relative lap times for the 86 starts completed by all three controllers. The final network beats its geometric predecessor on 86 laps and the edited PPO on 62."></a><figcaption>On 86 starts finished by all three controllers compared here, mean paired lap time falls by 1.73% against the improved PPO and 9.91% against the earlier geometric network. The panels use different scales.</figcaption></figure>

## What does this tell us about Astra?

In one session Astra wrote an inspectable steering rule into a trained network and built a second controller from vehicle geometry. The small number of prompts tells us how much direction I supplied. Between requests, Astra wrote code, inspected crashes and discarded unsuccessful designs. How often could it find an equally effective repair if we gave it a different starting network?

The tests cover one lap at a time on 21 known tracks. Ten starts still end in timeouts. Performance on a physical car remains an open question. The protocol includes failed candidates and the follow-up timeout investigation. [Full results](phase6/) · [Original F1TENTH report with Manuel Andruccioli and Giacomo Totaro (PDF)](output/pdf/original-f1tenth-report.pdf) · [Code, weights and data](https://github.com/Ro0t-set/f1tenth-weight-space-racing)
