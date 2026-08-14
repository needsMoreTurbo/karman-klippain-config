# Physics models

Small, self-contained models used to **predict before measuring**. The point is not accuracy —
it is having a stated expectation, so that when hardware disagrees we learn something instead of
rationalising whatever came out.

Pure stdlib, no dependencies.

```
python3 extract_traces.py     # captures/*.json -> measured.json     (rebuild the dataset)
python3 fit_model.py          # measured.json   -> fit_result.json   (refit, prints everything)
python3 melt_model.py         # -> melt_model_out.json               (predict a sweep)
```

| File | What it is |
|---|---|
| `captures/` | Raw ADC streams from four real sweeps, with the firmware's own reads kept as labelling anchors |
| `extract_traces.py` | Finds every PA step in a stream and builds the fitting dataset |
| `melt_model.py` | The model |
| `fit_model.py` | Fits it, and argues with itself about whether the fit means anything |
| `pa_sweeps.json` | **Hand-recorded**, not regenerable — every `KARMAN_PA_CALIBRATE` sweep result (flow, accel, PA, σ, read quality), pulled from klippy.log with source line numbers. This is the input to the matrix below, not to `melt_model.py`. |
| `pa_law.json` | **Hand-recorded** — the fitted `PA = C·Q_peak^(n−1)` law and the Orca `adaptive_pressure_advance_model` matrix generated from it. `n` comes from `melt_model.py`'s waveform fit, not from `pa_sweeps.json`. |
| `measured.json`, `fit_result.json`, `melt_model_out.json` | Generated; safe to delete |

Full narrative — why the sweeps needed geometry scaling, what a repeatable measurement looks like,
the `smooth_time` hypothesis that fit and was falsified, the calibration protocol — is in
[`docs/pa_physics.md`](../docs/pa_physics.md). `pa_sweeps.json` and `pa_law.json` are that
document's evidence, kept as data rather than prose so a new condition can be appended and refit
without re-deriving anything.

---

## `melt_model.py` — melt-zone pressure during a `PA_E` step

### The model

The melt zone is a **compliance feeding a resistance** — a squishy reservoir draining through the
nozzle — plus a constant friction term:

```
Q_in(t)  = A_fil * v_cmd(t)              extruder pushes filament in
Q_out(P) = (P / K) ** (1/n)              polymer squeezes out of the nozzle
dP/dt    = (Q_in - Q_out) / C            pressure is what the reservoir holds
F(t)     = P + F0 * sign(v_cmd)          what the gauge feels
```

`Q_out` is a **power law, not linear**, because molten polymer is shear-thinning. Pressure advance
enters as Klipper models it, `v_cmd = v_nominal + PA * a_nominal`. The gauge reads force, so the
reported ADC is `baseline − F`: pressure appears as a **dip**.

### Fitted parameters

`n = 0.653`, `K = 3.939`, `C = 0.0204`, `F0 = 2.31`, no extra ADC smoothing.

Fitted against all 49 PA steps of the 14.4 mm³/s sweep. Every one of the five features lands
within 1σ of measurement (χ² = 1.1).

`F0` was **not** in the original model; the data forced it. The apparent exponent of pressure
against flow *rises* with flow — 0.32, 0.58, 0.72 across the four measured flows — which no power
law can do. `P = F0 + K·Q^n` fits all four points to 0.09 counts where the power law alone manages
0.77. Physically it is filament friction through the heatbreak plus the melt's entrance pressure:
a force present whenever filament moves, regardless of how fast.

It was worth checking that offset is force and not an artifact of zeroing each trace on its own
pre-extrusion samples. During the 300 mm/s travel move the gauge reads **−0.5 ± 0.4 counts**, the
same as standing still — so toolhead motion contributes nothing and the extruding levels are not
sitting on a shifted zero.

### What it reproduces

- Spike and plateau depths, and how both scale with flow
- **Peak response to PA: +85%, matching measurement** — the whole point of the exercise
- The **convexity** of peak against PA (+1887 counts/PA² against a measured +3193), which was
  never fitted and comes out of the transient by itself
- Rise and fall times, and run lengths against the firmware's `low_count > 60` cap

### ⚠️ What it does NOT reproduce — the plateau asymmetry, and this is the important one

The settled levels of the slow segments either side of the spike differ, and that difference moves
with PA. (Note this is NOT the firmware's `Hr − Hl`, which is a local-maximum search near the dip
edges and therefore samples transients — the two correlate only r = 0.69. See docs/pa_physics.md.)
The hardware shows the settled asymmetry clearly:

| Flow | measured `Hr − Hl` | significance | model |
|---|---|---|---|
| 14.4 mm³/s | −0.42 − 12.5·PA counts | slope 7.3σ from zero | `0.00 + 0.0·PA` |
| 25 mm³/s | +1.21 − 18.3·PA counts | slope 3.6σ from zero | `0.00 + 0.0·PA` |

**The model produces exactly zero.** With one lumped compliance its memory is ~20 ms and the slow
segments last 1.6 s, so after eighty time constants both plateaus are identical by construction.
The real system remembers the spike's retraction for over a second.

That is a **slow relaxation mode** — what a real polymer melt has and a single lumped element does
not. Adding a second, slower compliance in parallel is the next step, and it is the only route to
a model that predicts what a sweep will *conclude* rather than just what the trace looks like.

### Also open

- **At 25 mm³/s the model is 1.8× too sensitive to PA** (slope 158 predicted, 86 measured, z = +3.5).
  No power-law exponent produces that flow dependence, so a mechanism is missing — candidates are a
  melting-rate limit at high flow or filament-column compliance. That sweep also ran at a different
  nozzle temperature, so it is not a clean hold-out; a matched-temperature sweep would settle it.
- **`pressure_advance_smooth_time` is NOT the missing mechanism.** It was the leading candidate and
  it was falsified on hardware: it predicted PA 0.0592 at 14.4 mm³/s / accel 6000, and the sweep
  measured 0.0306 ± 0.0030 — 9.5σ away. See docs/pa_physics.md.
- **`F0` was tested and survived.** At `MAX_VOLUMETRIC=5` the two candidate laws predicted a
  slow-segment plateau of ≈5.0 counts with the offset and ≈2.0 without; 50 steps measured
  **4.00 ± 0.66** (SE 0.09). The pure power law is excluded; `F0` is real and mildly overestimated.

---

## `fit_model.py` — how the parameters were found, and two ways it went wrong first

Chi-square over five features, each measured by **identical code** on model and hardware traces,
each normalised by that feature's scatter across the sweep:

```
peak_intercept   spike height extrapolated to PA=0
peak_slope       d(peak)/d(PA)  <- the PA-sensitive one
plateau          settled slow-segment depth
rise_ms          10-90% of the spike
fall_ms          90-10% after it
```

Stages: **identifiability** (which parameter moves which feature, and are any two redundant) →
**global coordinate sweeps** → **hold-out** on the 25 mm³/s sweep → **waveform RMS reported
alongside**, so any trade against the old objective stays visible.

### The first version scored better and predicted worse

It minimised RMS over whole traces. Result: PA response fell to **+5%** against a measured +85%,
while RMS improved and a hold-out passed. Two independent causes:

1. **The objective measured the wrong thing.** ~88% of a trace is baseline or plateau — steady-state
   flow, which pressure advance does not affect. The spike is ~12% of the samples and is the entire
   signal, so RMS paid the optimiser to fit the plateau and abandon the spike.
2. **The search could not reach the answer.** Coordinate descent stepped each parameter by at most
   ±50% of its current value, confining `C` to [0.036, 0.110]. The value that fits is 0.020. No
   objective would have found it through that window.

Both are fixed: features instead of RMS, and full-range log grids instead of local steps. The
current fit improves RMS *as well* (3.70 → 2.84 counts), so there was never a trade — the old fit
was simply in the wrong region.

### Two numerical traps found on the way

- **ADC sampling phase.** The spike is a few sample periods wide, so where the sample grid lands
  changes the recorded peak by 2–3 counts out of a ~12-count PA signal. The hardware re-randomises
  it every step, so the model must predict the *expectation* over phase; `model_features()`
  integrates once and samples at six phases. Before this the model's 25 mm³/s slope swung 119–142
  depending on integration step, which looks like physics and is not.
- **Integer quantisation over a short PA span.** The 25 sweep covers PA 0→0.046, over which the peak
  moves ~4 counts — comparable to the ADC's own 1-count resolution. Its slope needs a dense PA grid,
  as the measurement itself uses 24 steps.

### Reading the fitted χ²

Five features against four free parameters is one degree of freedom, so χ² = 1.1 on the fitted
sweep is close to arithmetic. The hold-out, with nothing free, is the number that means anything —
and it is a partial pass (χ² 19.7, driven by the PA slope above).

Comparison plots: <https://claude.ai/code/artifact/fe1bd7ae-1bcc-42b4-b578-2b41c25bd190>
