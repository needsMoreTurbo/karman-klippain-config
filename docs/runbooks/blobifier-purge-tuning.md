# Runbook — tune Blobifier purge lengths for the UHF melt zone

**Objective:** colour changes complete cleanly on the part. Fix the measured under-purge on
light→dark swaps without making dark→light wasteful. **Klipper-side only.**
**Status:** 🔴 **BLOCKED — jams in the PTFE/heatbreak region opened 2026-08-08** (see the regression
section below; resolve before anything else). Steps 1-4 complete, floor settled at 140; Step 5
attempted and abandoned. **Created:** 2026-08-03
**Prerequisites:** Blobifier live and owning purge; both gates loaded with contrasting filament.

## The problem, already diagnosed
> ⚠️ **The arithmetic in this section is superseded.** It was written against
> `toolhead_residual_filament: 25` and a 25 mm melt zone. Both were **wrong** — the pool measures
> **33 mm** (~79 mm³) and displacement is **35 mm**, not 26. The *diagnosis* below (only the flush
> term changes colour; displacement replaces nothing) is correct and is why this runbook exists;
> only the numbers are stale. Corrected figures are in the status log. Kept as written because the
> reasoning is what matters and the correction is itself part of the story.
Blobifier computes (`mmu/addons/blobifier.cfg:378-391`):
```
purge_len = (pv[from][to] × purge_length_modifier) / 2.405
          + extruder_filament_remaining + retracted_length + purge_length_addition
```
**Only the first term flushes colour.** `extruder_filament_remaining` (residual + any cut
fragment) and `retracted_length` are **displacement** — they push old material to the tip; they
replace nothing. On this machine that displacement is ≈ **26 mm** of the total.

Measured 2026-08-02, `SWAP TOOL=0` (teal → black) which visibly failed to change colour:

| Swap | slicer mm³ | → flush (mm) | + displacement | total reported |
|---|---|---|---|---|
| **T1→T0 (→dark)** | 41 | **10.2** | 26 | **36 mm** ← the failure |
| T0→T1 (→light) | 218 | 54.4 | 26 | ~80 mm (fine) |

**The melt zone alone is 25 mm ≈ 60 mm³.** So the failing swap delivered under half a melt-zone
volume of fresh material. The slicer's 41 mm³ is the standard "going darker needs less" heuristic,
sized for a ~10 mm melt zone — the same class of error as the original
`toolhead_residual_filament` mistake (`docs/decisions.md`, 2026-07-17).

Corollary: **`purge_length_minimum: 30` is effectively zero flush** (~4 mm once displacement is
subtracted).

## Scope
Tune Blobifier's own purge variables so no swap can under-flush, verify on a real 2-colour print,
and confirm the already-generous →light direction didn't become wasteful.

## ⚠️ Out of scope — do not touch
- **`toolhead_residual_filament: 25`** — ⚠️ the trap. It looks like "the melt zone", and raising it
  looks like it would purge more. It does **not**: it is a *displacement* term, and it also
  **shortens the load** (`load = D − residual − ooze_reduction − retract`). Raising it to fix
  purging would under-load the nozzle — the exact failure of 2026-07-17, which produced cut-air
  tips and tower blobs. It is hand-measured and correct. Leave it.
- **Slicer / Orca flushing volumes** — the user chose a Klipper-side fix. Do not edit the matrix,
  and do not "helpfully" re-run `MMU_CALC_PURGE_VOLUMES`.
- **`toolhead_ooze_reduction: 2`** — load-side ooze control, unrelated to colour flush.
- **Blob-shape variables** (`z_raise`, `z_raise_exp`, `purge_spd`, `purge_start`,
  `pressure_release_time`) — those tune whether the blob *forms* well, not whether the colour
  changes. Only touch if blobs stop depositing cleanly at the new larger volumes.
- **Blobifier geometry** (`purge_x`, `tray_top`, shaker, brush) and **START_PRINT's purge chain**
  (settled 2026-08-02) — both validated, both unrelated.

## Pre-resolved decisions
- **Klipper-side only** (`blobifier.cfg`); slicer matrix untouched.
- **Acceptance = the part is clean.** The blob showing a colour transition is expected and fine —
  that is what it is for.
- **Fix →dark first**, then confirm →light hasn't become wasteful.

## Why `purge_length_minimum` is the right knob here
It is a **floor on the total**, applied last (`purge_len = max(purge_len, purge_length_minimum)`).
That makes it surgical for this problem:

| Knob | Effect on →dark (36 mm) | Effect on →light (80 mm) |
|---|---|---|
| **`purge_length_minimum`** | raises it to the floor ✅ | **untouched** if the floor is below 80 ✅ |
| `purge_length_addition` | +N | **+N as well** — adds waste to the good direction ✗ |
| `purge_length_modifier` | ×N on the flush term | ×N as well, and it is already generous ✗ |

Sizing, given ~26 mm displacement:

| Flush wanted | Melt zones | `purge_length_minimum` |
|---|---|---|
| 25 mm | 1.0 | ~51 |
| 37 mm | 1.5 | ~63 |
| 50 mm | 2.0 | ~76 |

**Start at 65** (~1.5 melt zones) and iterate.

## Step 1 — Confirm the current numbers *(model)*
```
grep -nE "purge_length_minimum|purge_length_maximum|^variable_purge_length:|purge_length_modifier|purge_length_addition" mmu/addons/blobifier.cfg
grep -nE "^toolhead_residual_filament|^toolhead_ooze_reduction" mmu/base/mmu_parameters.cfg
```
Expected today: `minimum 30`, `maximum 150`, `modifier 0.6`, `addition 0`, `residual 25`.
Background maths: `docs/mmu_purge_volume.md`.

## Step 2 — Baseline *(user runs)*
Load both gates with the contrasting pair, then:
```
SWAP TOOL=1
SWAP TOOL=0
```
Read the console line `BLOBIFIER: Purging NNmm of filament` for each direction and record both.
Confirm the →dark figure is ~36 mm before changing anything — if it differs, the slicer matrix has
changed and the arithmetic above must be redone before proceeding.

## Step 3 — Raise the floor *(model edits; user restarts)*
In `mmu/addons/blobifier.cfg`:
```
variable_purge_length_minimum: 65      # was 30
```
Comment it with the reasoning (≈26 mm displacement + ~37 mm flush ≈ 1.5 melt zones), then:
```
FIRMWARE_RESTART      # user runs; never mid-print
```

## Step 4 — Fast iteration loop *(user runs)*
Not the acceptance test — just a quick proxy so you are not printing for every trial:
```
SWAP TOOL=1
SWAP TOOL=0
```
Confirm the reported purge is now ≥65 mm, and look at the **tail of the deposited blob**: it should
end in clean new colour. Still contaminated → raise `purge_length_minimum` by ~12 (half a melt
zone) and repeat. Note each value tried and what it looked like.

## Step 5 — Acceptance: a real 2-colour print *(user runs)*
The blob tail is a proxy; **the part is the acceptance test.** Print a small 2-colour model with
several alternating swaps in both directions.
- [ ] First few mm of each new colour on the **part** show no contamination from the previous one
- [ ] →dark transitions specifically are clean (the original failure)
- [ ] No FlowGuard trips, no state desyncs across the swaps

## Step 6 — Check the good direction didn't regress *(model + user)*
> ⚠️ **Rewritten 2026-08-08 — the original check no longer applies.** It asked to confirm →light
> "still reports ~80 mm", i.e. that it stayed **above** the floor and was untouched. That premise
> died: →light was never actually clean at its natural value, so the floor had to rise above it.
> →light being floor-driven is now the intended design, not a regression to catch.

Both natural values (→dark 45, →light 89) sit below the 140 floor, so **every swap purges 140
regardless of direction** and the slicer's 41/218 mm³ matrix no longer affects anything. What to
confirm instead:
- [ ] Both directions report exactly the floor (140) — if either reports *more*, its natural value
      has risen above the floor and the matrix is back in play, which changes the reasoning.
- [ ] The cost is accepted: →dark is over-purged by ~15 mm on every swap because it shares →light's
      floor. The fix, if it matters, is `purge_length_modifier` ≈ 1.16 (see status log) — not a
      lower floor, which would break →light again.

Also watch: `purge_length_minimum` is what a **same-tool prime** purges
(`blobifier.cfg`, `from_tool == to_tool`). At 140, print-start priming — when the initial tool is
already loaded — purges **140 mm instead of 30**. Confirm that is acceptable; if not, it is the
argument for `purge_length_addition` instead of a floor.

## Verification
- [x] →dark swap reports the floor and produces a clean colour change *(blob proxy, 2026-08-08)*
- [x] →light swap clean *(blob proxy at floor 140, 2026-08-08)*
- [x] `purge_length_maximum: 150` not exceeded — 140 is still a single blob (little headroom left)
- [x] Cuts verified square at `residual 33` / `retract_length 66` over multiple tests
- [x] Gate 1 loads reliably — homing 57.1 mm → 16.9/19.9 mm, no failures since
- [ ] Blobs still deposit cleanly at the larger volume (no stringing, no failure to release)
- [ ] **A full 2-colour print completes with clean transitions throughout** ← the real acceptance
- [ ] Post-purge ooze resolved (3-5 mm dribbles onto the part after the blob; trialling
      `pressure_release_time` 1000 → 2500)
- [ ] `toolhead_ooze_reduction: 2` reviewed — load now advances 8 mm less; drop toward 0 if the
      load-side blob is gone
- [ ] Same-tool print-start prime at 140 mm (was 30) consciously accepted

## Commit guidance
`fix(blobifier): size purge floor to the UHF melt zone` — `mmu/addons/blobifier.cfg`.
Add a `docs/decisions.md` entry recording **why the floor is what it is** (displacement vs flush,
and that `purge_length_minimum` was chosen over `_addition`/`_modifier` because it is a floor and
so leaves the already-generous direction alone). Tick the task in `TODO.md`.

## 🔴 REGRESSION — frequent jams in the PTFE/heatbreak region (opened 2026-08-08)
**Symptom:** a chunk of filament lodges in the PTFE/heatbreak region; frequent. **Started only after
this session's changes.** Note it produces **no MMU error** — the 2026-08-08 print shows no FlowGuard
trip and `0.00 spent paused over 0 pauses (This job)`; the pause and cancel were manual. So this is a
physical obstruction degrading extrusion, not a fault HH can see. Logs will not find it — geometry will.

### Prime suspect — the cut fragment is no longer pushed past the PTFE/metal boundary
`mmu/base/mmu_cut_tip.cfg:98` exists for precisely this failure: *"Pushback of the tip residual into
the hotend to avoid future catching (ideally past the PTFE/metal boundary)"*, and
`pushback_length: 15.0` in `mmu_macro_vars.cfg` still carries its shipped **`TUNE ME: PTFE tube
length + 3mm`** comment — it was never tuned to this toolhead.

```
effective_pushback = min(pushback_length, retract_length − extruder_filament_remaining − retracted_length)
  before: min(15, 55 − 25 − 2) = min(15, 28) = 15
  after:  min(15, 66 − 33 − 2) = min(15, 31) = 15   <-- pushback DISTANCE unchanged
```
The pushback distance did not change — but the **starting position did**. The fragment now parks at
64 mm from the nozzle instead of 61, so after a fixed 15 mm push it ends at **49 mm instead of 46 mm**.
If the PTFE/metal boundary lies between those, the fragment used to clear it and now stops short
inside the PTFE, and every swap deposits another one. This is a **direct consequence of
`retract_length: 55 → 66`**, made possible by a pushback that was never sized for this machine.

### Other candidates, ranked
2. **Heat creep from longer swaps.** A 140 mm purge at `purge_spd: 400` adds ~21 s of extrusion per
   swap. More time at temperature with filament stationary in the heatbreak → softening and swelling.
   Fits "chunk in the heatbreak" but does **not** explain a clean fragment.
3. **Under-load from `residual: 25 → 33`.** The load advances 8 mm less, parking the fresh tip 8 mm
   further back. Plausible contributor, weak as a sole cause.
4. **Melt-zone chilling at 140 mm purge.** ~16 mm³/s sustained; within a UHF's capability, so
   unlikely, and it would jam at the *nozzle*, not the heatbreak.
5. **Gate-1 bowden / `toolhead_homing_max`.** Upstream of the toolhead entirely. Effectively excluded
   — but note `homing_max: 100` means a genuine load failure now drives 100 mm rather than 60.

### Plan — discriminate before changing anything
**Step J1 — inspect the chunk (do this first; it alone eliminates most candidates).**
- Clean ~5 mm cylinder, two flat cut faces → **candidate 1**, the cut fragment
- Swollen / mushroomed / tapered / longer than 5 mm → **candidate 2**, heat creep
- Several fragments fused together → candidate 1, accumulating over swaps

**Step J2 — measure the PTFE/metal boundary.** Distance from nozzle tip to where the PTFE ends, by
filament probe (same method that produced `toolhead_extruder_to_nozzle: 94.5`). This converts the
whole question into arithmetic: the fragment must be pushed **below** that number, and it currently
lands at 49 mm. Record it — nothing in this repo documents it today.

**Step J3 — does it correlate with swap count?** Jams after a predictable number of swaps ⇒
accumulation (candidate 1). Jams at random ⇒ thermal (candidate 2).

**Step J4 — cheapest targeted fix, live, no restart:**
```
SET_GCODE_VARIABLE MACRO=_MMU_CUT_TIP_VARS VARIABLE=pushback_length VALUE=25
```
Ceiling is `retract_length − residual − retracted` = **31**, so 25 is safe and clears ~6 mm deeper
than the old-and-working 46 mm. If jams stop, candidate 1 is confirmed and the fix is forward, not a
revert. **Do J2 first if possible** — a measured boundary beats a guessed 25.

**Step J5 — if J4 does not fix it, revert the cut park to its old position:**
`retract_length: 66 → 63` restores the pre-session tip position of 61 mm while *keeping* the correct
residual 33 (tip = retract_length − retracted_length). Costs ~3 mm of extra sliver. If jams stop here
but not at J4, the mechanism is the park position rather than the pushback.

**Step J6 — only if 1 is excluded:** drop the purge floor to ~100 for a few swaps to test the thermal
hypothesis. Expect colour quality to regress; this is a diagnostic, not a fix.

### ⚠️ Do not "fix" this by reverting `toolhead_residual_filament` to 25
33 is measured and verified by square cuts. Reverting it would restore the old cut park as a *side
effect* while re-breaking the purge arithmetic and the load length. If the park position is the
problem, change `retract_length` (J5), which moves it directly and in isolation.

## Status log
- **2026-08-03** — runbook created from the 2026-08-02 measurements; not yet started.
- **2026-08-08** — Step 1 confirmed: `minimum 30`, `maximum 150`, `purge_length 150`, `modifier 0.6`,
  `addition 0`, `residual 25`, `ooze_reduction 2`. All as expected; arithmetic stands.
- **2026-08-08** — Step 2 partially confirmed **from klippy.log**, not a fresh run: `Swapped T1 > T0`
  → `Purging 36mm` (and `38mm` on a later swap), matching the runbook's →dark baseline. No logged
  `Swapped T0 > T1` line, so →light (~82mm predicted) is **still unconfirmed** — carry that into Step 6.
- **2026-08-08** — ⚠️ **Gotcha found:** a `FIRMWARE_RESTART` clears the slicer tool map, after which a
  bare `SWAP` reports `Purging 177mm` — the `variable_purge_length: 150` fallback (150 + 25 residual
  + 2 retracted), *not* a per-direction value. Restore the map before any Step 4 iteration with
  `MMU_SLICER_TOOL_MAP PURGE_VOLUMES="0,218,41,0"` (reconstructs the slicer's 41/218 mm³; does not
  touch the slicer matrix and is not `MMU_CALC_PURGE_VOLUMES`).
- **2026-08-08** — Step 3 applied: `variable_purge_length_minimum: 30 → 65` with reasoning inline.
- **2026-08-08** — Step 4 iteration (blob-tail proxy, contrasting filament):

  | floor | reported | flush | melt zones | result |
  |---|---|---|---|---|
  | 65 | 65 (T1→T0) | 39 | 1.6 | ❌ only *started* to darken at the blob top |
  | 100 | 100 (T0→T1) | 74 | 3.0 | ⚠️ transitioning over last 30%, almost clean |
  | 125 | — | 99 | 4.0 | under test |

- **2026-08-08** — ⚠️ **The runbook's central premise is disproved.** `purge_length_minimum` was
  chosen *because* it is a floor that would leave the generous →light direction untouched. But
  →light was **not** actually clean at its natural ~82 mm (the "fine" label was never verified with
  contrasting filament), so the floor had to rise above it. The floor now drives **both** directions
  and the slicer's 41/218 mm³ matrix is vestigial — every swap purges the floor regardless of
  direction. Steps 6's "did →light regress?" check is therefore moot: →light is now floor-driven by
  design, not by accident.
- **2026-08-08** — 🔬 **`toolhead_residual_filament: 25` is measurably WRONG — likely ~33.** Found by
  bisecting `retract_length` live (no restarts needed, see below): **58 flat · 61 flat · 64 cut air**.
  From `mmu_cut_tip.cfg:80`, `effective_retract = retract_length − residual − retracted_length`, so
  final tip position is `ρ + R − 25 − retracted` and the cut fails when that exceeds `blade_pos: 69`.
  Solving at the 61/64 boundary gives **ρ = 94 + retracted − R_fail → 32 ≤ ρ < 35** (30–33 if the
  extruder was cold and `retracted` was 0). This independently reproduces the *original* 2026-07-13
  measurement of **35**, which `docs/decisions.md` (2026-07-17) records as having been talked down to
  25 by a hand-calc — the second instance of the exact failure mode that entry warns about.
  - ⚠️ **`residual` and `retract_length` are coupled and must move together.** Once residual is
    correct, `tip = R − retracted`, so raising residual *alone* to 33 while leaving R=55 drops the tip
    to 53 and **doubles** the sliver (8mm → 16mm). Proposed settle: `residual 33` + `retract_length 66`
    (tip ~64, sliver ~5mm). R=68 was rejected: at the top of the ρ bracket it leaves 1mm of blade
    margin.
  - Corroboration: at residual 33 the load shortens 67.5 → 59.5mm, i.e. today's config over-advances
    by 8mm — which is exactly the load ooze that `toolhead_ooze_reduction: 2` was added to mask
    (`mmu_parameters.cfg:265`). If the blob goes away, ooze_reduction should return toward 0.
  - **Impact on this runbook:** displacement is 35mm, not 27. Floor 125 delivers 90mm flush = 2.7
    corrected melt zones (33mm ≈ 79mm³), not 4.0. Natural values shift →dark 36→45, →light 82→**89**.
    The floor likely needs ~8mm more than the blob test suggests. **The melt-zone arithmetic in
    "The problem, already diagnosed" above is built on residual 25 and needs redoing if ρ is confirmed.**
- **2026-08-08** — 🛠 **Iterate without `FIRMWARE_RESTART`** (no re-home, no QGL, tool map survives):
  `SET_GCODE_VARIABLE MACRO=_MMU_CUT_TIP_VARS VARIABLE=retract_length VALUE=<n>`,
  `SET_GCODE_VARIABLE MACRO=BLOBIFIER VARIABLE=purge_length_minimum VALUE=<n>`, and
  `MMU_TEST_CONFIG TOOLHEAD_RESIDUAL_FILAMENT=<n>` for `[mmu]` options. All read live at call time;
  none persist across a restart. Keep the hotend at temp every trial — `retracted_length` is 2 when
  hot and 0 when not, a 2mm shift that confounds the cut arithmetic.
- **2026-08-08** — ✅ **Geometry settled and persisted:** `toolhead_residual_filament: 33`
  (mmu_parameters.cfg), `retract_length: 66` (mmu_macro_vars.cfg). Cuts verified square over multiple
  tests. Both files carry the measurement and the ⚠️ coupling warning inline.
- **2026-08-08** — ✅ **Floor settled at 140** (`variable_purge_length_minimum`), restated against the
  corrected 35mm displacement:

  | floor | flush | melt zones (33mm ≈ 79mm³) | result |
  |---|---|---|---|
  | 30 | ~0 | ~0 | original — effectively zero flush |
  | 65 | 30 | 0.9 | ❌ →dark only started to darken at blob top |
  | 100 | 65 | 2.0 | ❌ →light transitioning over last 30% |
  | 125 | 90 | 2.7 | →dark **clean**; →light almost |
  | **140** | **105** | **3.2** | ✅ **both directions clean** |

  Both natural values (→dark 45, →light 89) sit below 140, so every swap purges the floor regardless
  of direction — deliberate, and the reason `_modifier`/`_addition` were not used.
- **2026-08-08** — ⏳ **Still open:**
  - **Step 5 acceptance (a real 2-colour print) has NOT been run.** Everything above is the blob-tail
    proxy, which the runbook explicitly says is *not* the acceptance test. The part is.
  - `toolhead_ooze_reduction: 2` unreviewed. The load now advances 8mm less (67.5 → 59.5), and that
    setting exists only to mask ooze that understated residual was causing. If the per-swap load blob
    is gone, it should come down toward 0. No observation was taken either way.
  - Optional: `purge_length_modifier` ~1.16 would let →light reach 140 naturally and drop the floor
    back to ~125 for →dark (~15mm saved per dark-ward swap). Needs →dark's true minimum measured —
    125 is known to work, not known to be minimal.
- **2026-08-08** — Neither alternative knob helps: `_modifier` can't fix →dark (its flush term comes
  from a 41 mm³ slicer volume that is ~5× too small for a 25 mm melt zone — a 5.3× modifier would be
  needed), and `_addition` inflates both directions equally. **The real fix is upstream in the slicer
  purge volumes**, which this runbook put out of scope. → new TODO item.
- **2026-08-08** — **Unrelated blocker hit and fixed mid-session** (T0→T1 `Failed to reach toolhead
  sensor after moving 60.0mm`): gate 1 arrives ~25mm shorter than gate 0 at end of bowden. HH's
  bowden autotune is hard-gated on `gate_selected == 0` (`mmu_calibration_manager.py`), so gate 1
  never self-corrects. Fixed with `variable_bowden_lengths: 1` in `[mmu_machine]` +
  `toolhead_homing_max: 60 → 100`, then `MMU_CALIBRATE_BOWDEN` on gate 1.
  **RESOLVED & verified:** `mmu_calibration_bowden_lengths = [1462.7, 1505.4]`; T1 homing dropped
  57.1mm → 19.9/16.9mm (extra homing 10.3/7.4mm vs gate 0's 26.4mm). No failures since.
