# Runbook — standardise per-filament PA calibration with BDPressure

**Objective:** turn the one-off ABS characterisation into a **repeatable per-filament procedure**
with a cheap decision gate: measure the minimum needed to decide whether adaptive PA is worth it
for this filament, deliver a constant PA if it isn't, and expand to a full adaptive matrix if it
is. Deliver the SOP, the refit tooling it needs, and prove it on a real second filament.
**Status:** not started · **Created:** 2026-08-14
**Prerequisites:** BDPressure working (`docs/runbooks/done/bdpressure-pa-sensor.md`); a second
filament to characterise; ABS results as the regression baseline.

## Read first — this objective is built on prior work
- **`docs/pa_physics.md`** — the melt model, §4 *what the sensor cannot measure*, §5 *from traces to
  a PA number*, §6 the generic protocol, Appendix A (sensor bugs), Appendix B (dataset).
- **`docs/decisions.md`**, entries 2026-08-12 → 2026-08-14 — three `bdpressure.py` bugs, the soak
  requirement, the zero-crossing solve, and the adaptive-PA validation finding.
- **`physics/pa_law.json`** — the fitted law, its matrix, and `orca_paste_block`.

**The law:** `PA = C · Qpeak^(n−1)`, with `n = 0.653` taken from an *independent* trace fit
(`melt_model.py`, never saw a sweep result) and `C = 0.1032` fitted to 13 valid ABS sweeps.
χ²/dof 1.81; the 4 rows at accel 6000 were a **blind prediction** (blind χ²/dof 0.27).

## Scope
Schema + tooling so a filament can be added without hand-editing JSON → a two-corner gate that
decides constant-vs-adaptive on evidence → the expansion path when adaptive wins → results filed in
both homes → validated on one real new filament.

## ⚠️ Out of scope — do not touch
- **`n_shear = 0.653` for ABS, and the ABS fit generally.** It came from an independent dataset and
  survived a blind prediction. Do not refit ABS, and do not "improve" `melt_model.py` /
  `fit_model.py` while doing this.
- **`[update_manager bd_pressure]` in `moonraker.conf` stays commented out.** ⚠️ The three
  `bdpressure.py` patches live **outside this repo**. Re-enabling the updater silently reverts them
  and **the symptom is bad data, not an error** (`docs/decisions.md`, 2026-08-12).
- **`KARMAN_PA_CALIBRATE` soak defaults** (`soak_cold: 240`, `soak_hot: 30`) — measured, not
  guessed. Shortening them reintroduces a thermal artefact.
- **The module's own "Calc the best Pressure Advance" verdict** — the rows are the data, the verdict
  is not. The patched `cmd_stop` solves the `Hr−Hl` zero crossing and *refuses* rather than
  guessing; keep it that way and keep `apply_result` **off** (default).
- **`debug: 1`** — only for raw trace capture, ~50k log lines per sweep. Not for routine sweeps.
- **Beacon, MMU, Blobifier, purge and START_PRINT config** — all unrelated and all validated.

## Pre-resolved decisions
- **Tiered with a gate:** minimum sweeps first to decide if adaptive earns its keep; expand only if
  it does, tuning the model to the filament and then using it to fill the range.
- **Two homes:** per-filament constant PA **and** adaptive matrix go in the **Orca filament
  profile** (Orca is per-brand). Klipper's `material_parameters` keeps a **type-level default**
  (`ABS`, `PLA`) as the fallback for non-slicer paths (`SWAP`, standalone purge, START_PRINT).
- **Deliverable includes tooling and a validation run** — a process run once is not a process.

## ⚠️ Known measurement floor — design the gate above it
From `docs/decisions.md` 2026-08-12: the sensor emits a result only when `has_plus()` fires, which
aliases against the module's per-step polling.

| Flow | Behaviour |
|---|---|
| **25 mm³/s** | ~1 fresh read per step — **clean** (dup ratio 1.0) |
| 14.4 mm³/s | ~1 per **5** steps — ~10 usable points, ±4-step PA slop |
| 12 mm³/s | dup ratio 2.8 — degraded |
| 7.2 mm³/s | 50 distinct but **incoherent** — genuine signal failure |

**Do not place the low corner below ~14.4 mm³/s**, and treat anything under 20 as needing more
repeats. This is a property of the sensor, not of the filament.

---

## Step 1 — Add a material field to the dataset *(model)*
`physics/pa_sweeps.json` has **no material field** — all 15 rows are implicitly ABS. Add
`"material": "ABS"` to every existing row (and a filament/brand string if you want brand
granularity), and document the field in the file's `_read_me`.

## Step 2 — Build the refit helper *(model)*
Appendix B: *"A refit helper is not written. Adding a condition today means running the sweep,
appending a row to `physics/pa_sweeps.json` by hand, and re-running the fit ad hoc."* Write
`physics/pa_refit.py`:

- **Input:** `--material <name>`; reads `pa_sweeps.json`, uses only `valid: true` rows for that material.
- **Fit:** `C` with `n` fixed (default `0.653`, `--n` to override); refit both only with `--fit-n`
  and enough cells to be identifiable (see `pa_physics.md` §3.3 on identifiability).
- **Report:** fitted `C` ± error, χ²/dof, the two-point `n` estimate from the corner cells,
  the constant PA at the outer-wall condition (Step 3), the full matrix, and the Orca paste block.
- **Output:** `physics/pa_law_<material>.json`, same shape as `pa_law.json`.

**Regression gate — the helper is not trusted until it passes this:**
```
uv run physics/pa_refit.py --material ABS
```
must reproduce **C = 0.1032**, χ²/dof ≈ **1.81**, and an `orca_paste_block` matching
`physics/pa_law.json`. If it doesn't, the helper is wrong — not the old result.

## Step 3 — Define the operating envelope *(model + user)*
From the Orca process profile for this filament, extract the flow and acceleration the print
actually uses: outer-wall speed/width/height → volumetric flow, and `outer_wall_acceleration`.
Record the **outer-wall operating point** — the constant PA is evaluated *there*, not as a global
average of the matrix. (ABS's 0.032 corresponds to roughly flow 20 / accel 3000.)

## Step 4 — Phase A: the gate sweeps *(user runs)*
Two corners of the envelope, **three repeats each** — scatter is the uncertainty, per `pa_physics.md`
§5.2. Load the filament, then for each condition:
```
KARMAN_PA_CALIBRATE NOZZLE_TEMP=<filament temp> MAX_VOLUMETRIC=<flow> ACC_WALL=<accel>
```
- **High corner:** highest flow and acceleration the profile actually reaches (prefer flow ≥20).
- **Low corner:** lowest flow the profile uses, **but not below ~14.4 mm³/s** (see floor above).
- Soak is automatic: 240 s from cold, 30 s back-to-back. Don't shorten it.

Record every run into `pa_sweeps.json` (material, temp, flow, accel, geom_scale, pa, pa_sigma,
fresh/skipped counts). **Watch `fresh` vs `skipped`** — a thin sweep is visible at the time, not
three runs later.

## Step 5 — The gate decision *(model presents; user decides)*
Adaptive PA earns its place only if **both** are true:

**(a) Rheology — does PA actually move?**
Compare `|PA_high − PA_low|` against the run-to-run scatter. Separation under ~2σ means the
filament's PA is flat across your envelope → **constant PA**. For reference, ABS's scatter was
σ ≈ 0.0019 and its matrix spanned 0.028–0.039.

**(b) Profile — does the print traverse the envelope?**
⚠️ **`dont_slow_down_outer_wall` is enabled in the Orca profile** (`docs/decisions.md`,
2026-08-14). It holds outer-wall speed near-constant, so the adaptive matrix acts mostly on
internal features. Three ABS test prints showed a *dramatic* no-PA vs PA difference but only a
**subtle** flat-vs-adaptive one, despite a matrix spanning 0.028–0.039. If that setting stays on
and outer-wall appearance is what you care about, adaptive may not be worth the effort **even for a
filament that passes (a)**.

State the recommendation with the numbers, and let the user choose.

## Step 6a — If constant PA wins
- Evaluate PA at the **outer-wall operating point** (Step 3).
- **Orca filament profile:** set that PA; leave adaptive PA disabled.
- **Klipper `variables.cfg`:** update the type-level `material_parameters` default if this filament
  is representative of its material class.
- ⚠️ `material_parameters` edits need a `FIRMWARE_RESTART` to take effect — a past ABS change sat
  unapplied because the files were never reloaded. Re-query `gcode_macro _USER_VARIABLES` to confirm.

## Step 6b — If adaptive PA wins
The two corners give a **two-point estimate of `n`** — the derivative that matters, since spread
across the envelope is governed entirely by the exponent:
```
n − 1 = ln(PA_high / PA_low) / ln(Qpeak_high / Qpeak_low)
```
- **If that `n` agrees with 0.653 within error** → carry `n` over, fit only `C`, and generate the
  matrix from the law. Add ~2 interior cells to give the fit some dof and a residual to look at.
- **If it disagrees** → the filament's shear-thinning genuinely differs. Add cells across the flow
  range and refit `n` and `C` together (`--fit-n`), checking identifiability first. A trace-level
  refit (`debug: 1` captures → `extract_traces.py` → `melt_model.py`) is the fallback, and is a
  **separate objective** — do not start it inside this runbook.
- Generate the matrix and paste `orca_paste_block` into the Orca filament profile's adaptive PA table.
- Per `pa_physics.md` §6 step 9: make a **blind prediction** for one unmeasured cell, then measure
  it. That is what separates a model from a curve fit.

## Step 7 — Validate on a real print *(user runs)*
Print the same test model used for ABS
([Printables #437927](https://www.printables.com/model/437927-pressure-advance-torture-test))
or a comparable one, with the new filament and its new setting.
- Confirm from the log **what PA was actually in effect** (`pa_physics.md` §6 step 10 — this has
  bitten before).
- Compare against the same model printed with the old/default PA.

## Step 8 — Write it down
- **`docs/pa_calibration_sop.md`** (or a new section in `pa_physics.md`) — the per-filament
  procedure as a standalone checklist: envelope → 2 corners × 3 → gate → constant or expand → file
  results → validate. Someone should be able to do a new filament from that page alone.
- **`docs/decisions.md`** — an entry for the gate criterion and anything the new filament revealed.
- Update **Appendix B** — the dataset table, and strike the "refit helper is not written" note.

## Verification
- [ ] `pa_refit.py --material ABS` reproduces C = 0.1032, χ²/dof ≈ 1.81, and the existing Orca block
- [ ] `pa_sweeps.json` carries a material field on every row; ABS rows unchanged in value
- [ ] Six gate sweeps recorded for the new filament, with `fresh`/`skipped` counts showing healthy reads
- [ ] The constant-vs-adaptive decision is stated **with the numbers behind it**, not asserted
- [ ] Chosen values are live: Orca profile updated, and if `material_parameters` changed, verified
      after `FIRMWARE_RESTART` by re-querying `_USER_VARIABLES`
- [ ] A real print with the new filament looks right, and the log confirms the PA in effect
- [ ] The SOP page exists and is self-contained

## Commit guidance
- `feat(physics): add per-material PA refit helper and material field` — `physics/pa_refit.py`,
  `physics/pa_sweeps.json`
- `docs: add per-filament PA calibration SOP` — `docs/pa_calibration_sop.md`, `pa_physics.md`
  Appendix B, `docs/decisions.md`
- `feat(pa): <filament> PA characterisation` — `variables.cfg` if the type-level default moved;
  note the Orca-side change in the commit body since it lives outside the repo.

## Status log
- **2026-08-14** — runbook created. Absorbs the "refit helper is not written" follow-up from
  `docs/runbooks/done/bdpressure-pa-sensor.md`.
