# Pressure advance from a strain-gauge sensor

**What this is.** A strain-gauge (load-cell) sensor at the hotend can measure melt pressure directly,
which in principle turns pressure-advance calibration from a print-and-squint exercise into a
measurement. This document records what that actually takes: a physical model of the melt zone, the
ways a fit of that model can be confidently wrong, the things the sensor physically cannot see, and
a protocol that produces a number you can defend.

**Who it is for.** Anyone with a load-cell PA sensor on a Klipper machine. The worked example
throughout is **Karman**, a Voron 2.4 with a Rapido V2 UHF hotend and a PandaPi3D BDPressure E
sensor, printing ABS at 275 °C. Every number below is from that machine and traceable to a raw
capture in `physics/captures/`. Hardware-specific details about that particular sensor's firmware
are quarantined in Appendix A so the main text stays portable.

**What it is not.** Not a characterised rheology, and not a guide to wiring or installing a sensor.
The model is for trends: direction, relative size, and how things move with flow and acceleration.

Companion material: `physics/README.md` (how to run the code), `physics/melt_model.py`,
`physics/fit_model.py`, `physics/extract_traces.py`, and the raw sweeps in `physics/captures/`.

---

## 1. What the sensor sees

A load cell at the hotend groove mount reads the reaction force of pushing polymer through the
nozzle. Force is proportional to melt pressure, and the ADC counts fall as pressure rises, so
pressure appears as a **dip**. On Karman: an ADS1220 24-bit ADC sampling at a measured **87.7 Hz**,
with a quiescent baseline near 6600 counts and useful signals of 5–50 counts.

A calibration sweep extrudes a repeating pattern — a slow segment, a fast segment, a slow segment —
at a series of PA values, and asks which PA makes the pressure transient cleanest. Two facts about
that pattern govern everything downstream:

- **The signal lives in the acceleration ramp.** Pressure advance adds `PA × acceleration` to
  commanded filament velocity, so it acts only while the toolhead is accelerating. On Karman that
  window is **13–78 ms** depending on flow and acceleration.
- **Steady-state flow carries no information about PA.** The plateaus are pure `Q_out(P)`; PA does
  not appear in them. Roughly 88% of a captured trace is baseline or plateau, and it is all
  irrelevant to the question being asked. This single fact is responsible for the worst mistake in
  Section 3.

---

## 2. The melt-zone model

### 2.1 Structure

The melt zone is modelled as a **compliance feeding a resistance** — a squishy reservoir draining
through the nozzle — plus a constant friction term:

```
Q_in(t)  = A_fil · v_cmd(t)              extruder pushes filament in
Q_out(P) = (P / K)^(1/n)                 polymer squeezes out of the nozzle
dP/dt    = (Q_in − Q_out) / C            pressure is what the reservoir holds
F(t)     = P + F0 · sign(v_cmd)          what the gauge feels
v_cmd    = v_nominal + PA · a_nominal    Klipper's pressure advance
```

`Q_out` is a **power law, not linear**, because a polymer melt is shear-thinning: push harder and
apparent viscosity falls. That single non-linearity generates the interesting behaviour — a response
time that shortens as flow rises, which is the whole reason one PA value cannot be right everywhere.

The lumped time constant is `τ = C·K·n·Q^(n−1)`. Note what happens at `n = 1`: the flow term becomes
`Q⁰ = 1` and τ stops depending on flow at all. A fit that lands on `n = 1` has switched off the
mechanism the model exists to represent. Treat it as a signal that something else is wrong, not as
a measurement (Section 3.2).

### 2.2 Fitted parameters, and how well it does

Fitted against all 49 PA steps of the 14.4 mm³/s sweep:

```
n = 0.653    K = 3.939    C = 0.0204    F0 = 2.31    no extra ADC smoothing
```

| feature | measured | model | z |
|---|---|---|---|
| peak intercept (PA→0) | 22.3 ± 0.7 | 21.9 | −0.6 |
| peak slope d(peak)/d(PA) | 197.0 ± 12.4 | 198.7 | +0.1 |
| settled plateau | 6.7 ± 0.5 | 7.0 | +0.6 |
| rise, 10–90% | 40.3 ± 14.9 ms | 36.1 ms | −0.3 |
| fall, 90–10% | 190 ± 80 ms | 193 ms | +0.0 |

χ² = 0.8 over five features. But five features against four free parameters is one degree of
freedom, so a low χ² *here* is close to arithmetic. Two things carry more weight:

**Curvature, which was never fitted.** Measured peak-versus-PA is convex — it steepens as PA rises —
at +3193 counts per PA² at 14.4 mm³/s. The model produces +1887 without being asked, because its
spike is a transient that never reaches equilibrium. Getting the *shape* of a curve right when only
its slope and intercept were scored is evidence the mechanism is right.

**A hold-out that only partly passes.** Predicting the 25 mm³/s sweep with nothing refitted gives
χ² = 21.4, driven almost entirely by PA sensitivity: predicted slope 158 against a measured
86 ± 20 (z = +3.5). The model is ~1.8× too sensitive to PA at the higher flow. That sweep also ran
at a different nozzle temperature, so it is not a clean test — but the gap is real and unexplained.

### 2.3 The term the data forced in

`F0` was not in the original model. The data demanded it, and the argument is worth repeating
because it generalises: **plot the apparent exponent between adjacent measured flows.** For a pure
power law it must be constant. On Karman it is not:

```
 1.35 →  2.35 mm³/s :  n = 0.319
 2.35 → 14.26 mm³/s :  n = 0.584
14.26 → 24.75 mm³/s :  n = 0.724
```

An apparent exponent that *rises* with flow is the signature of an additive offset. Fitting
`P = F0 + K·Q^n` to all four flow points lands within **0.09 counts**; the pure power law manages
0.77. Physically it is filament friction through the heatbreak plus the melt's entrance pressure —
a force present whenever filament moves, regardless of how fast.

**Check that an offset is force and not a zeroing artifact.** Each trace is zeroed on its own
pre-extrusion samples, so any systematic error there would masquerade as exactly this term. During
the 300 mm/s travel move with no extrusion the gauge reads **−0.5 ± 0.4 counts**, the same as
standing still. Toolhead motion contributes nothing, so the extruding levels are not sitting on a
shifted zero.

**Then falsify it.** The two candidate laws diverge most at low flow, where the offset dominates:
at 5 mm³/s they predicted a slow-segment plateau of **≈5.0 counts with the offset and ≈2.0
without**. Fifty steps measured **4.00 ± 0.66** (SE 0.09). The pure power law is excluded outright;
`F0` is real, and mildly overestimated.

### 2.4 What the model does not reproduce

**No slow relaxation, so no plateau asymmetry.** One lumped compliance gives the model a memory of
~20 ms. The slow segments either side of the spike last 1.6 s — eighty time constants — so pressure
fully re-settles and both plateaus come out *identical by construction*: the model's settled
asymmetry is `0.00 + 0.0·PA` at every PA and every flow.

The hardware disagrees at **7.3σ**: `−0.42 − 12.5·PA` counts at 14.4 mm³/s. Tracking the recovery
after the spike in fifths of a segment gives a decay of roughly **τ ≈ 2.8 s** — the real melt
remembers the spike's retraction for seconds. That is a slow relaxation mode, which a real polymer
melt has and a single lumped element does not. Adding a second, slower compliance in parallel is the
obvious next step and has not been done.

**Not modelled at all:** filament-column compliance and gear slip (the commanded burst is assumed
delivered), melt cooling at high flow, junction-deviation cornering, and sensor mechanics (the gauge
and its mount are assumed infinitely stiff).

---

## 3. Four ways to fit the model and be confidently wrong

This section is the most transferable part of the document. Every failure below produced a *better
score* than the thing it replaced.

### 3.1 An objective dominated by the part that carries no information

The first fit minimised RMS over whole traces. It improved RMS from 4.49 to 3.39 counts and passed
a hold-out with a ratio of 0.88 — better on data it had never seen than on data it was fitted to.
Every check the procedure applied to itself, it passed.

It was badly wrong. Peak response to PA:

| PA | measured | before fitting | after fitting |
|---|---|---|---|
| 0.000 | 26 | 36 | 21 |
| 0.050 | 29 | 38 | 21 |
| 0.098 | 45 | 41 | 22 |

Measured response across the sweep is **+85%**; the fit delivered **+5%**. A calibration sweep works
by finding where that response turns over, so a model that flattens it cannot be used to reason
about calibration at all.

The cause is arithmetic. RMS was taken over ~260 samples per trace, of which ~88% are plateau. The
spike is ~12% of the points and is the entire signal, so the optimiser bought plateau accuracy with
spike accuracy — trading away the only part that responds to PA.

**The fix is the objective, not the physics.** Score a small number of named features, each
normalised by its own scatter across the sweep, and measure them with *identical code* on model and
hardware traces:

```
peak_intercept   spike height extrapolated to PA = 0
peak_slope       d(peak)/d(PA)   ← the quantity that matters
plateau          settled slow-segment depth
rise_ms          10–90% of the spike
fall_ms          90–10% after it
```

The feature fit improved whole-trace RMS *as well* (3.70 → 2.84 counts), so there was never a
trade-off. The first fit was simply in the wrong region of parameter space.

### 3.2 A search that cannot reach the answer

The same fit used coordinate descent with multiplicative steps of at most ±50% of each parameter's
current value. Starting from `C = 0.073`, that confines the compliance to `[0.036, 0.110]` for the
entire run. **The value that fits the data is 0.020.** No objective, however well designed, would
have found it through that window.

This is why the first fit drove `n` to its boundary at 1.0: with `C` pinned too slow, the only way
to make the spike large enough was to raise the exponent, and the optimiser rode it to the edge —
switching off the flow dependence in the process.

**Sweep each parameter over its full physical range on a log grid** before believing any local
refinement. Report the boundary if a parameter lands on one.

### 3.3 Skipping identifiability

Perturb each parameter and ask which features move, in units of the measured scatter. On Karman,
before fitting:

```
d(trace)/d(n)  = 1.12 counts per +10%
d(trace)/d(K)  = 0.93
d(trace)/d(C)  = 0.41      ← and C never moved during four rounds of descent
```

The parameter governing the transient was the one the objective could barely feel. That was visible
*before* the fit ran and would have predicted the failure. Also correlate the sensitivity vectors:
two parameters whose vectors are near-parallel cannot be separated by that data no matter how good
the optimiser is.

### 3.4 Nuisance parameters that look like physics

Two numerical effects on Karman were large enough to be mistaken for real behaviour:

**ADC sampling phase.** The spike is only a few sample periods wide, so where the sampling grid
happens to land relative to the peak changes the recorded peak by **2–3 counts out of a ~12-count PA
signal**. The hardware re-randomises this every step, and it is already inside the measured scatter.
The model must therefore predict the *expectation over phase*, not one arbitrary alignment.
Before this was handled, the model's predicted slope at 25 mm³/s swung between **119 and 142**
depending on the integration timestep — which looks like a physical result and is not. Integrate
once, then sample the same integration at several phases; the integration is the expensive part.

**Integer quantisation over a short span.** The 25 mm³/s sweep covers PA 0 → 0.046, over which the
peak moves ~4 counts — comparable to the ADC's own 1-count resolution. Estimating a slope from a
handful of quantised points across that span is noise-dominated; use a dense grid, as the
measurement itself does with 24 steps.

---

## 4. What the sensor cannot measure

These are hard limits. No amount of modelling or averaging recovers them.

### 4.1 Sample rate against ramp duration

The PA signal exists only during the acceleration ramp, of duration `Δv / a`. At 87.7 Hz, counting
ADC samples across that ramp on Karman:

| flow (mm³/s) | Δv (mm/s) | accel 1500 | 3000 | 6000 | 10000 |
|---|---|---|---|---|---|
| 5.0 | 40.5 | 2.4 | 1.2 | 0.6 | 0.4 |
| 10.0 | 81.0 | 4.7 | 2.4 | 1.2 | 0.7 |
| 14.4 | 116.6 | 6.8 | 3.4 | 1.7 | 1.0 |
| 20.0 | 162.0 | 9.5 | 4.7 | 2.4 | 1.4 |
| 25.0 | 202.5 | 11.8 | 5.9 | 3.0 | 1.8 |

**Below about two samples there is nothing left to resolve.** This showed up exactly where predicted:
the 10 mm³/s / accel 6000 cell (1.2 samples) was the single worst measurement of thirteen — triple
the error bar of its neighbours and the only cell to miss the fitted law by more than 0.5σ. The
high-acceleration corner is permanently beyond this sensor; anything there rests on extrapolation.

### 4.2 Event duration against the analyser's window

A sensor that ships its own analyser will have an internal limit on how long an extrusion event may
be. With a fixed-length test pattern, event duration is inversely proportional to flow, so **low
flows silently fall off the end of it**. On Karman the yield at 14.4 mm³/s was **11 usable steps of
50 — 22%**.

The fix is to **scale every distance in the pattern by `flow / flow_reference`**, holding event
duration constant at all flows. Speeds already scale with flow, so extrusion-per-mm and the measured
flow rates are unchanged; only duration normalises. Yield at the same flow went to **41 of 42 —
98%**, and every cell in a flow sweep then sits the same distance from the limit, which is what makes
cells comparable at all.

There is a trap in the other direction. Scaling *shortens* the slow segments at low flow, and the
melt's slow relaxation mode (τ ≈ 2.8 s, Section 2.4) means a settled plateau needs a segment several
τ long. At 5 mm³/s the scaled segment is 0.94 s (32% settled) against 4.71 s (86%) unscaled. **Any
measurement that reads plateau *levels* wants the long pattern; any measurement that reads the
*transient* wants the scaled one.** They are different experiments.

### 4.3 Transient discriminators beat settled ones

There are two quantities that could be called "the asymmetry between the plateaus either side of the
spike", and they are not the same:

- the difference of **settled levels**, sampled where each slow segment has stopped moving
- a **local-maximum search near the dip edges**, which samples transients

On the same 41 steps they correlate only **r = 0.69**, and the transient version has roughly **4×
the dynamic range**. Decisively: across all four Karman captures, the settled-plateau metric
**never crosses zero at any flow**, while the transient metric crosses cleanly and gives a usable
answer. Steady-state levels wash out precisely the information the calibration needs.

This also raises the bar on the model. Reproducing the discriminator that a sweep actually uses
needs the transient *shape* near the dip edges to be right — a slow relaxation mode alone would not
be enough.

---

## 5. From traces to a PA number

### 5.1 Solve for a root, not a minimum

The discriminator is negative when PA under-compensates and positive when it over-compensates. The
answer is therefore **the PA where it crosses zero** — a root. Fit a least-squares line through
(PA, discriminator), take the crossing, and propagate the uncertainty.

Make the routine capable of *failing*. Require: a genuine sign change in the data, a slope
significant at 3σ, a crossing inside the swept range, and a minimum point count. A routine that
always returns something will always return something (Appendix A).

### 5.2 Trust run-to-run scatter over the fit's own error bar

Three repeats of one cell gave 0.0395, 0.0332, 0.0322 — a sample standard deviation of **±0.0040**
against a fit-reported **±0.0078**, with χ²/dof about the mean of **0.26**. The fit's uncertainty is
roughly 2× conservative. Two other repeated cells agreed to within 0.0000 and 0.0027.

Precision also varies enormously with condition. The best measurement of thirteen (±0.0030) beat
the worst (±0.0127) by 4×, decomposing as **1.8× from a wider swept PA span, 1.3× from more points,
1.65× from lower scatter**. Higher acceleration produces a larger PA-induced asymmetry, so it is
strictly better to calibrate at high acceleration — provided the ramp still spans two samples.

### 5.3 Fit a law across cells instead of interpolating them

Individual cells are noisy and a 2-D grid of them is mostly noise. But `PA ~ τ ~ Q_peak^(n−1)`,
where `Q_peak` is the peak volumetric flow during the burst — which rises with *both* nominal flow
and acceleration. That is one free parameter across the whole grid.

On Karman, with **n = 0.653 taken from the waveform fit and never refitted against sweeps**:

```
C = 0.1032     χ²/dof = 0.15 over 13 measurements
```

The law was then used to make **blind predictions** for four cells that did not yet exist, which
came back at **χ²/dof = 0.27**, three of the four within 0.1σ. An exponent derived from fitting
pressure *waveforms* correctly predicts how the *calibration answer* moves with flow and
acceleration — two quantities it was never shown.

The resulting matrix is generated from the law rather than interpolated from cells, so every run
constrains every entry:

| flow (mm³/s) | accel 1500 | 3000 | 6000 |
|---|---|---|---|
| 10.0 | 0.0391 | 0.0355 | 0.0314 |
| 14.4 | 0.0363 | 0.0336 | 0.0303 |
| 20.0 | 0.0336 | 0.0316 | 0.0289 |
| 25.0 | 0.0317 | 0.0301 | 0.0279 |

### 5.4 A hypothesis that fit the data and was still wrong

Klipper smooths the pressure-advance correction over `pressure_advance_smooth_time` (default 40 ms).
Where the acceleration ramp is shorter than that window, less of the correction is delivered, so the
sweep would have to ask for a larger PA to compensate. On Karman the ramp is 13–78 ms — squarely in
range — and anchoring on the longest-ramp cell reproduced the observed flow trend reasonably
(predicted 0.0425 / 0.0295 / 0.0287 / 0.0287 against measured 0.0381 / 0.0338 / 0.0304 / 0.0287).

It was wrong. The two explanations diverge violently at high acceleration, where the ramp is
shortest: smoothing predicted **0.0592** at 14.4 mm³/s / accel 6000, against **~0.034** if PA is a
genuine material time constant. Measured: **0.0306 ± 0.0030**, which is **9.5σ** from the smoothing
prediction. Dead.

Two lessons. First, the fact that a mechanism *could* explain a trend, and quantitatively does, is
weak evidence — design the measurement where the candidates disagree most. Second, the sign was the
giveaway available in advance: PA fell with rising flow *and* with rising acceleration, which move
ramp duration in **opposite** directions. What they share is raising peak flow through the nozzle,
which is what Section 5.3 turned into a law.

---

## 6. Protocol

For someone with a load-cell PA sensor who wants a defensible number.

1. **Capture raw, not just the sensor's verdict.** Log the raw ADC stream. Vendor analysers reject
   steps for their own reasons; the stream contains every step. On Karman this recovered 49 usable
   steps from a sweep the firmware scored 12 — the difference between a slope fit and a guess.
2. **Normalise event duration.** Scale the test pattern's distances with flow so every condition
   presents the same event length to the analyser. Verify by checking the yield, not by assuming.
3. **Match the pattern to the question.** Transient measurements want the scaled (short) pattern;
   plateau-level measurements want the long one, several slow-mode τ per segment.
4. **Check the ramp against the sample rate before believing a cell.** `Δv / a × f_sample` below ~2
   means the cell is unmeasurable, whatever number comes out.
5. **Use a transient discriminator, and solve for its zero crossing** with explicit refusal
   conditions.
6. **Calibrate at high acceleration** for signal, since PA itself is acceleration-independent to
   within the precision available — but stay above the two-sample floor from step 4.
7. **Repeat at least one cell three times.** Use the observed scatter as your uncertainty, not the
   fit's.
8. **Fit a physical law across all cells** rather than interpolating a sparse grid, and where
   possible take its exponent from an independent measurement so the law can be tested rather than
   merely fitted.
9. **Make a blind prediction and then measure it.** It is the only step that distinguishes a model
   from a curve fit.
10. **Verify the value reaches the nozzle.** Firmware and start-up macros can override a slicer's
    pressure advance silently. Confirm from the log what was actually in effect during a print. (On
    Karman this bit: see `docs/decisions.md`.)

---

## Appendix A — BDPressure / PandaPi3D specifics

Everything here is particular to this sensor's firmware and Klipper module. It is recorded because
this is the only place the knowledge exists.

**The discriminator.** The firmware emits `R:res,k_l,k_r,Hk,Hr−Hl` per step. `Hr−Hl` is the PA
discriminator, and its `H_left`/`H_right` come from a **local-maximum search near the dip edges** —
transient points, not settled plateaus (Section 4.3). It is reported in units of 0.1 ADC count and
with the ADC sign convention, so it is inverted relative to a depth-based calculation.

**The analyser's event-length cap.** `if (low_count > 2 * SAMPLES) return 0;` — 60 samples, about
0.68 s at 87 SPS. This is what makes long, low-flow events unanalysable and motivates the geometry
scaling in Section 4.2. Measured: a 3.58 s event yielded 24% of steps, a 2.06 s event 92–98%.

**The answer-selection bug.** The vendor's `cmd_stop` scanned *backwards* for the last row with
`Hk < 5`, then searched only from that index to the end for the smallest `res + |Hr−Hl|`. Because
`Hk` is 0 on most rows, that backward scan halts within a few rows of the **end** of the sweep, so
the search window is the highest PA values — selected before any physics is considered. On a clean
41-point sweep whose `Hr−Hl` crossed zero at **0.031 ± 0.003**, it returned **0.076**. The routine
could not fail: it always returned some row.

It also then ran `SET_PRESSURE_ADVANCE` on that value, leaving the machine on a number no config
file records and which silently reverts at the next restart.

**Local patches** (module frozen in `moonraker.conf` so updates cannot overwrite them):

1. **Framed USB reads** — the original grabbed unframed bytes and re-processed a stale result when
   nothing new had arrived, so one measurement could be relabelled with a PA it was never measured
   at. Now: accumulate, split on newlines, keep the newest complete `R:` line, skip when nothing
   fresh arrived, and report fresh/stale counts.
2. **Warm-up discard** — the original `pop(0);pop(1);…pop(4)` removes indices 0,2,4,6,8 because each
   pop shifts the list. Harmless at 22 points, destructive at 10. Now a proportional drop.
3. **Zero-crossing solve** — replaces the tail-window search with the least-squares root of Section
   5.1, with refusal conditions, and makes applying the result opt-in (`apply_result`, default off).

**Module code needs `sudo systemctl restart klipper`, not `FIRMWARE_RESTART`** — Python caches
modules in `sys.modules`. Config *values* (including this module's options) do reload on
`FIRMWARE_RESTART`.

---

## Appendix B — the Karman dataset

Raw ADC captures in `physics/captures/`, each with the firmware's own reads kept as independent
labelling anchors:

| capture | flow | accel | temp | geometry | steps |
|---|---|---|---|---|---|
| `sweep_14p4.json` | 14.4 | 3000 | 275 °C | vendor (20/40/20 mm) | 49 |
| `sweep_25.json` | 25.0 | assumed 3000 | 260 °C | vendor | 24 |
| `sweep_5.json` | 5.0 | 3000 | 275 °C | vendor, forced | 49 |
| `sweep_14p4_scaled.json` | 14.4 | 3000 | 275 °C | scaled (11.5/23/11.5 mm) | 42 |

`sweep_25.json` ran at a different temperature and an acceleration the runbook leaves ambiguous, so
it is **not a clean hold-out**; treat its residuals with that in mind.

The thirteen PA determinations behind Section 5.3 are in `docs/decisions.md` and the console logs,
not in a capture file — the sweeps were run after `debug` was turned off. Re-enable `debug: 1` in
`bdpressure.cfg` to capture raw traces again, at roughly 50k log lines per sweep.

Rebuild everything with:

```
python3 physics/extract_traces.py     # captures/ -> measured.json
python3 physics/fit_model.py          # -> fit_result.json, prints every stage
```
