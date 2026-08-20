# Runbook — tune Blobifier purge lengths for the UHF melt zone

**Objective:** colour changes complete cleanly on the part. Fix the measured under-purge on
light→dark swaps without making dark→light wasteful. **Klipper-side only.**
**Status:** 🔴 **BLOCKED — jams in the PTFE/heatbreak region opened 2026-08-08** (see the regression
section below; resolve before anything else). Steps 1-4 complete, floor settled at 140; Step 5
attempted and abandoned. Pushback-distance fix (15→30) did **not** resolve the jam — mechanism is now
understood as wisp buckling, not insufficient push distance; see
[Tip-Cut Anatomy](https://claude.ai/code/artifact/cbab05b3-1215-4832-bc5a-977eba6ba92c). PTFE tubing
replaced by the user as a mitigation, result pending. **Created:** 2026-08-03
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

> **Update, 2026-08-18 — partially right, importantly incomplete.** `pushback_length: 15 → 30` was
> applied and the jam recurred (user report, same week the fix shipped) — so "not pushed far enough"
> was not the actual mechanism. The extracted fragment: a **6mm solid chunk with a ~9mm tapered wisp**
> attached, 15mm total (not the ~3mm the macro's own arithmetic predicts). The wisp sits on **Piece
> B's nozzle-facing end** — stretched-out material from the tip that was molten at the nozzle a moment
> before the retract pulled it away, not something torn by the blade. Being slender, it's prone to
> **buckle** under the pushback's axial force instead of travelling straight, folding into a
> cross-section wider than the bore — at which point more pushback distance just folds it harder.
> Full geometry, both retract-phase wisp sources (the original Step-1 retract *and* the pre-cut
> tip-forming wiggle, which dips to within ~1mm of the melt-zone boundary), and the buckling mechanism
> are worked through in
> [Tip-Cut Anatomy](https://claude.ai/code/artifact/cbab05b3-1215-4832-bc5a-977eba6ba92c).
>
> The user has since replaced the PTFE tubing with a slightly longer piece — a plausible mitigation
> (removes a step/gap at the metal transition, likely where a buckling wisp first catches) — but
> **untested in isolation**, since it changed at the same time as everything else this runbook has
> touched.

> **Update, 2026-08-18 — the PTFE→metal boundary is now measured, and it closes the distance
> question for good.** User measurement: 3mm from the cutter to the top of the PTFE, 18.6mm of PTFE
> tube, so the transition to metal sits **21.6mm below the cutter** = `blade_pos − 21.6` =
> `69 − 21.6` = **47.4mm from the nozzle**. Piece A's pushback stop is **well past** that line — see
> the corrected figures immediately below — so the 15→30mm pushback fix was never marginal on
> distance. It should have cleared the transition with room to spare, and the jam happened anyway.
> A *measured* confirmation of the buckling conclusion, not just a plausible theory.

> **⚠️ Correction, 2026-08-19 — `effective_retract_length` is 31mm, not 64mm.** An earlier pass
> through this analysis used `extruder_filament_remaining = 0`; it is actually the residual (33).
> **Verified against the log:** `Retracting filament 31.0mm prior to cut`, on every swap. Corrected
> geometry, and what changes:
> | quantity | was stated | actually |
> |---|---|---|
> | effective retract | 64mm | **31mm** (66 − 33 − 2) |
> | tip travel in Step 1 | 2 → 66mm | **33 → 64mm** (starts at the melt-pool top) |
> | Piece B nominal size | 3mm | **5mm** (69 − 64) |
> | wiggle depth | tip to 34mm | **tip to 48.5mm** (E±15.5, not E±32) |
> | Piece B after pushback | ≈40mm | **34–39mm**, wisp end ~25mm |
>
> Three consequences, and the third is the important one:
> - **The cut model is not broken.** Nominal Piece B is 5mm and the user measured a **6mm** solid
>   chunk — within measurement error. The earlier "fragment is 5× the model" framing was an artifact
>   of the bad number. The *entire* discrepancy is the ~9mm wisp; the chunk was never the problem.
> - **Pushback clears the boundary by even more than thought.** Piece B lands at 34–39mm — 13.4mm
>   past the 47.4mm transition — and the wisp's free end reaches ~25mm, *inside the melt pool*, where
>   it should simply remelt and purge away. The destination is correct; the failure is in transit.
> - **The wiggle's tip never reaches the melt zone** (48.5mm, 15.5mm clear of it) — so F1's original
>   "dips into the reservoir" rationale was wrong. But the **wisp**, hanging ~9mm below the tip, dives
>   to ~39.5mm: about **8mm inside the hot metal heatbreak**. F1 survives the correction with a better
>   mechanism than it had.

### Other candidates, ranked
2. **Heat creep from longer swaps.** A 140 mm purge at `purge_spd: 400` adds ~21 s of extrusion per
   swap. More time at temperature with filament stationary in the heatbreak → softening and swelling.
   *(Revisit, 2026-08-18: the fragment isn't clean — it has a molten-stretched wisp — so heat creep
   may be a contributing cause of the wisp's length rather than a mutually-exclusive candidate.)*
3. **Under-load from `residual: 25 → 33`.** The load advances 8 mm less, parking the fresh tip 8 mm
   further back. Plausible contributor, weak as a sole cause.
4. **Melt-zone chilling at 140 mm purge.** ~16 mm³/s sustained; within a UHF's capability, so
   unlikely, and it would jam at the *nozzle*, not the heatbreak.
5. **Gate-1 bowden / `toolhead_homing_max`.** Upstream of the toolhead entirely. Effectively excluded
   — but note `homing_max: 100` means a genuine load failure now drives 100 mm rather than 60.

### Plan — discriminate before changing anything
**Step J1 — inspect the chunk (do this first; it alone eliminates most candidates).**
✅ **Done, 2026-08-15/18.** Result was neither pure option below — it was both at once: a 6mm
solid/crisp chunk (the cut face) **plus** a ~9mm tapered wisp (the nozzle-facing end), 15mm total.
See the reality-check figure in [Tip-Cut Anatomy](https://claude.ai/code/artifact/cbab05b3-1215-4832-bc5a-977eba6ba92c).
- ~~Clean ~5 mm cylinder, two flat cut faces → candidate 1, the cut fragment~~ — partially: the cut
  face itself *is* crisp.
- ~~Swollen / mushroomed / tapered / longer than 5 mm → candidate 2, heat creep~~ — partially: there
  is a tapered wisp, but it's on the wrong end for pure heat creep to explain alone (nozzle-facing,
  not the cut face) — see candidate 1's update above.

**Step J2 — measure the PTFE/metal boundary.** ✅ **Done, 2026-08-18** (direct measurement, not filament
probe): 3mm cutter→PTFE-top + 18.6mm of PTFE tube = **47.4mm from the nozzle**. See the update above —
this rules out pushback distance definitively (nominal stop is already 7.4mm past it) and narrows the
buckling-trigger search: a step in bore diameter right at 47.4mm is now the concrete place to look, not
just a hypothesis.

**Step J3 — does it correlate with swap count?** Not yet answered.

**Step J4 — pushback distance.** ✅ **Attempted at 30 (persisted, committed `00be615`) — did not stop
the jam.** Distance was not the lever; see the 2026-08-18 update above. Do not re-try higher pushback
values as a first move — it treats the wrong variable.

**Step J5 — if the PTFE swap doesn't hold, shorten the original retract:**
`retract_length: 66 → 63` restores the pre-session tip position of 61 mm while *keeping* the correct
residual 33 (tip = retract_length − retracted_length). Costs ~3 mm of extra sliver, but also shortens
the distance the once-molten tip travels away from the nozzle in Step 1 — which may shorten the wisp
itself, not just relocate where it ends up. Worth trying before or alongside F1 below.

**Step J6 — only if the wisp/buckling mechanism is excluded:** drop the purge floor to ~100 for a few
swaps to test whether less time at temperature (less heat creep) changes anything. Expect colour
quality to regress; this is a diagnostic, not a fix.

### ⚠️ Do not "fix" this by reverting `toolhead_residual_filament` to 25
33 is measured and verified by square cuts. Reverting it would restore the old cut park as a *side
effect* while re-breaking the purge arithmetic and the load length. If the park position is the
problem, change `retract_length` (J5), which moves it directly and in isolation.

### 🕓 Captured for later — not started (2026-08-18)
Two items identified while working through the wisp mechanism above. **Do not start these yet** —
parked here so they aren't lost, not queued as the next action.

- **F1 — reduce the wisp length at the source, instead of surviving it.** ⭐ **Now the recommended
  next action** (see the 2026-08-19 correction in the status log — F1's original rationale used a
  wrong retract figure; the corrected geometry makes the case *stronger*, not weaker).
  **Action:** `SET_GCODE_VARIABLE MACRO=_MMU_CUT_TIP_VARS VARIABLE=simple_tip_forming VALUE=False`
  (live, no restart, instantly reversible, zero coupling to cut geometry or purge math).
  **Mechanism:** the wisp forms during Step 1's *mandatory* 31mm retract, which drags molten material
  out of the pool — unavoidable, the filament has to reach the blade. But `simple_tip_forming` then
  adds an *optional* `E+15.5 / E−15.5` round trip (hardcoded as half the effective retract — there is
  **no** variable to shorten it, so on/off is the only lever). The **tip** stays in the PTFE
  throughout (64 → 48.5 → 64mm, never reaching the melt zone) — but the **wisp hanging ~9mm below it**
  dives from ~55mm to ~39.5mm, roughly **8mm inside the hot metal heatbreak**, where a sub-millimetre
  thread softens almost instantly, and is then drawn back out. That is a second soften-and-stretch
  cycle applied to the exact feature that jams, and it is the only optional one.
  **What "better" looks like:** shorter/absent wisp on the extracted fragment; the 6mm solid chunk
  should be unchanged (it already matches the 5mm model).
  **Risk:** HH says the wiggle "adds some additional cooling time … may help avoid potential
  clogging." Losing it means less dwell before the blade. Watch for a less-square cut face — the
  servo-down (500ms) and travel moves still provide some cooling. Revert instantly if cuts degrade.
  **If that is not enough, second lever:** raise `extruder_move_speed` (currently 25 mm/s) to ~40.
  A faster pull tends to rupture a molten thread rather than draw it long. Also live-settable on
  `_MMU_CUT_TIP_VARS`. Watch for extruder slip — run_current is only 0.45 A.
  ⚠️ **This one is confounded:** `extruder_move_speed` drives *both* the retract and the pushback
  (`mmu_cut_tip.cfg:83, 103, 105`), with opposing effects — faster retract should *shorten* the wisp
  (rupture beats draw), faster pushback should *worsen* buckling (more axial force on a slender
  column). There is no variable to separate them, so a null result may be the two cancelling rather
  than "speed doesn't matter." Run F1's boolean first and alone.
  See the "wiggle between ①→②" figure in
  [Tip-Cut Anatomy](https://claude.ai/code/artifact/cbab05b3-1215-4832-bc5a-977eba6ba92c).

  **Test protocol (what each experiment can and cannot show).**
  `MMU_EJECT` performs a real unload — cut included — then pushes the filament 100mm past the gate
  (`gate_final_eject_distance: 100`) so it can be pulled out and inspected. Per CLAUDE.md, **never**
  use `MMU_TEST_FORM_TIP` here.
  ```
  M109 S260                    # pre-heat EVERY trial: if the extruder is not hot enough to retract,
                               # retracted_length is 0 not 2, shifting the effective retract 31 -> 33mm
  MMU_EJECT                    # baseline -> pull out, photograph, label
  T0                           # reload
  SET_GCODE_VARIABLE MACRO=_MMU_CUT_TIP_VARS VARIABLE=simple_tip_forming VALUE=False
  MMU_EJECT                    # variant -> photograph, label
  ```
  - ✅ **Shows:** the blade-cut face on **Piece A** — i.e. whether disabling tip forming degrades cut
    squareness, which is the actual *risk* of the change.
  - ❌ **Does NOT show the wisp.** The wisp lives on **Piece B**, the fragment that stays in the
    hotend and is purged out on the next swap; Piece A never has one. Inspecting the wisp requires
    either waiting for a jam and extracting it (how the 6mm+9mm measurement was obtained), or a cold
    pull at ~100 °C, which fuses everything together and shows *that* a fragment existed rather than
    its shape.
  - 📊 **The real measure is jam frequency over N swaps.** The tip photos only tell you the change
    didn't break the cut.

- **F2 — confirm T0 and T1 filament behave the same under these settings.** Jams are *suspected, not
  confirmed* to happen preferentially with T1 (LDO ABS, dark teal) loaded rather than T0 (Polymaker
  PolyLite ABS, black). Every setting tuned this session — residual/retract geometry, pushback, purge
  floor — was tuned once for both gates, validated mostly by watching whichever tool happened to be
  active rather than deliberately checked against both. Before calling any of it settled, run the
  same jam/cut/purge checks with **both** T0 and T1 loaded and compare.
  **Standing principle, not just this bug:** this machine has no per-filament config — one
  `retract_length`, one `purge_length_minimum`, one `pushback_length` serves every tool. Any future
  toolchange tuning here has to be validated against *every filament actually in rotation*, not just
  whichever one happened to be loaded while tuning. A setting that's clean for T0 and marginal for T1
  is not a finished setting.

## ▶️ Next steps on resume (as of 2026-08-18)
Session paused mid-diagnosis to work on something else on the Pi. **Nothing below has a result
yet** — do these in order, each gates the next:

1. **Jam fix verified — result is NO.** `pushback_length: 15 → 30` did not stop the jam (user
   report). The extracted fragment (6mm chunk + ~9mm wisp — see the artifact) shows the failure is
   buckling, not insufficient push distance; pushing further was never going to help. The user has
   since replaced the PTFE tubing with a longer piece as a separate mitigation — **not yet confirmed**
   whether that alone fixes it. Next: run several T0↔T1 swaps / a short print on the new PTFE and
   watch for recurrence.
   - **Fixed** → jam regression closed (log in `docs/decisions.md` that pushback distance was a red
     herring, confirmed by measurement — nominal pushback already clears the PTFE/metal boundary by
     7.4mm — and the PTFE transition/geometry was the real lever), go to step 2.
   - **Still jamming** → J2 is done (boundary measured at 47.4mm). **Go to F1 first, not J5** —
     `simple_tip_forming: False` is a single live boolean with no coupling, and the corrected geometry
     (2026-08-19) shows it is the only *optional* step that drags the wisp through hot metal. J5
     (`retract_length: 66 → 63`) is the fallback after that; note it also shrinks the wiggle, since
     the wiggle is hardcoded to half the effective retract, so run F1 first or the two confound.
2. **Only after the jam is confirmed fixed — resume Step 5,** the real 2-colour print acceptance
   test. This is the actual blocking item for the runbook itself; everything up to floor 140 is
   still only proxy-verified (blob tail, not the part).
3. **Post-purge ooze (3-5mm dribble after the blob, found 2026-08-08) — untested.**
   `SET_GCODE_VARIABLE MACRO=BLOBIFIER VARIABLE=pressure_release_time VALUE=2500` was proposed but
   there is no report on whether it was tried or whether it worked. Config still reads `1000`
   (`blobifier.cfg:214`) — a runtime override would NOT have survived any `FIRMWARE_RESTART` since,
   so assume it needs re-testing from scratch. If it works, persist it to the file with reasoning,
   the same way the other tuned values were.
4. **`toolhead_ooze_reduction: 2` review — still no observation.** Watch the load side (start of a
   new colour, not the post-purge blob) on the next successful print. If clean, try walking it
   toward 0 live via `MMU_TEST_CONFIG TOOLHEAD_OOZE_REDUCTION=0`.
5. **Same-tool print-start prime cost (140mm vs the old 30mm) — never explicitly accepted.** Small
   but real per-print cost; flag it once Step 5 passes so it's a conscious tradeoff, not a silent one.
6. **`TODO.md` still doesn't link this runbook.** Not touched this session — the file currently has
   unrelated uncommitted PA-calibration edits in progress; add the blobifier line without disturbing
   those, or coordinate with whichever session owns that work first.
7. **Optional, not blocking:** `purge_length_modifier` ≈ 1.16 would let →light reach 140 on its own
   and drop the floor to →dark's real requirement (~125, still unmeasured as a true minimum) — saves
   ~15mm per dark-ward swap. Do this only after everything above is closed.

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
- **2026-08-18** — 🔬 **Jam mechanism reframed: buckling, not push distance.** The `pushback_length:
  15→30` fix (2026-08-08) did not stop the jam — user confirmed it recurred. Extracted fragment: 6mm
  solid chunk + ~9mm tapered wisp (15mm total, not the ~3mm the cut macro's own arithmetic predicts).
  The wisp is on Piece B's **nozzle-facing end**, not the cut face — stretched-out material from a tip
  that was molten at the nozzle a moment before Step 1's retract pulled it 64mm away, not something
  torn by the blade. Being slender, it buckles under the pushback's axial force instead of travelling
  straight, wedging wider than the bore — more push distance just folds it harder. Worked through in
  full, including a second candidate wisp-source (the pre-cut `simple_tip_forming` wiggle dips to
  within ~1mm of the measured melt-zone top before the blade fires), in
  [Tip-Cut Anatomy](https://claude.ai/code/artifact/cbab05b3-1215-4832-bc5a-977eba6ba92c).
  Regression section, Step J1/J4 status, and "Next steps on resume" updated to match. User has
  separately replaced the PTFE tubing with a longer piece (untested in isolation).
- **2026-08-18** — Captured two future investigation items per user request, explicitly **not
  started**: **F1** reduce the wisp length at the source (candidate lever: the tip-forming wiggle
  above) instead of continuing to just survive it; **F2** confirm T0 (Polymaker PolyLite ABS) and T1
  (LDO ABS) behave the same under these settings before calling any of this session's tuning settled
  — plus the standing principle that this machine's shared (non-per-filament) settings need
  validating against every filament in rotation, not just whichever one was loaded while tuning.
- **2026-08-18** — 📏 **PTFE→metal boundary measured directly (user, not filament probe): 47.4mm from
  the nozzle** (3mm cutter→PTFE-top + 18.6mm PTFE length = 21.6mm below the fixed `blade_pos: 69`).
  Closes Step J2. The number **confirms** the buckling conclusion rather than just supporting it:
  J4's nominal pushback stop (≈40mm) is already 7.4mm past this line, so the jam is not, and was
  never going to be, fixable by pushing further. Also feeds F1: the pre-cut wiggle's advance leg
  (66→34mm) now measurably transits 13.4mm past this same boundary before retracting again — a
  second full crossing, strengthening it as the wisp's likely origin. Artifact and runbook plan
  updated to match; noted the retract_length(66)≈PTFE-top(66) coincidence but flagged it as
  unexplained, not causal.
- **2026-08-19** — ⚠️ **Correction: `effective_retract_length` is 31mm, not 64mm.** The 2026-08-18
  analysis used `extruder_filament_remaining = 0`; it is the residual (33). Verified against the log
  (`Retracting filament 31.0mm prior to cut`, every swap). Full corrected table in the regression
  section above. Net effect: **the cut model is vindicated** — nominal Piece B is 5mm vs the 6mm
  chunk measured, so the "fragment is 5× the model" framing was wrong and the entire discrepancy is
  the ~9mm wisp. Pushback lands Piece B at 34–39mm with the wisp reaching into the melt pool, so the
  destination was always right and the failure is purely in transit. F1's rationale was wrong in
  detail (the wiggle's *tip* stops 15.5mm short of the melt zone) but **right in conclusion**: the
  wisp hanging below the tip still dives ~8mm into the hot metal heatbreak and is drawn back out.
  Artifact and runbook both corrected.
- **2026-08-19** — 🎯 **Recommended remediation for the wisp: `simple_tip_forming: False`** (F1
  above). Rationale: the Step-1 retract that creates the wisp is mandatory; the wiggle that softens
  and re-stretches it is not. Single live boolean, no coupling, instantly reversible. There is no
  variable to shorten the wiggle — it is hardcoded to `effective_retract_length / 2` in the
  framework-owned `mmu_cut_tip.cfg`, so on/off is the only available lever. Second lever if
  insufficient: `extruder_move_speed` 25 → ~40 mm/s (faster pull ruptures a molten thread rather than
  drawing it long; watch for extruder slip at 0.45 A). **Not yet run — no result.**
