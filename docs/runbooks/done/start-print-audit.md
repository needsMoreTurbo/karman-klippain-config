# Runbook — audit START_PRINT for steps that are no-ops or wrong for current hardware

**Objective:** go through the 13-action `START_PRINT` sequence and remove steps that either do
nothing, or were correct for older hardware and are not any more. Correctness only — **not** a
speed or filament-waste optimisation.
**Status:** ✅ **complete — verified on hardware 2026-08-02** · **Created:** 2026-07-25
**Prerequisites:** none. Reading `docs/start_print_walkthrough.md` first is strongly advised —
it already traces every step of this exact sequence with timings.

## Scope
The action list in `overrides.cfg`:
```
variable_startprint_actions: "bed_soak", "extruder_preheating", "chamber_soak", "clean",
  "contact_auto_calibrate", "tilt_calib", "bedmesh", "contact_z_home", "extruder_heating",
  "nozzle_expansion", "purge", "clean", "primeline"
```
…plus the Klippain variables that change what those actions do. For each: **does it still do
anything, and is what it does still right for the machine as it is now?** Audit → propose with
evidence → apply what the user approves → verify with a real print.

## ⚠️ Out of scope — do not touch
- **`contact_auto_calibrate` stays, every print.** Explicitly decided by the user. Do not remove,
  reorder for speed, or propose making it conditional.
- **Soak times, bed/nozzle temperatures, bed-mesh strategy** — tuning, not correctness. Even if
  they look slow, they are not this objective.
- **Purge *ownership*** — `purge_macro: BLOBIFIER` + `force_purge_standalone: 1` is settled (see
  `docs/decisions.md`). The only open question is whether Klippain's *additional* `purge` action
  is now redundant on top of it, not whether Blobifier should own purging.
- **`min_toolchange_z: 15`, `park_toolchange: -999,-999`, cut geometry, Blobifier geometry** —
  all validated; unrelated to this objective. See `docs/decisions.md` before touching anything
  that looks odd.
- **Klippain framework files** (`macros/`, `config/`) — never edit; a hook blocks it. All changes
  go in `overrides.cfg` / `variables.cfg`.

## Pre-resolved decisions
- Correctness only; ignore time and waste except as supporting evidence.
- `contact_auto_calibrate` is retained unconditionally.
- The session applies changes **after** presenting findings and getting approval, then verifies.

## Candidate list (starting hypotheses — confirm or refute each, don't assume)

| # | Candidate | Hypothesis to test |
|---|---|---|
| 1 | `chamber_soak` | Permanent no-op. `CHAMBER` comes from `[chamber_temperature]`, which `docs/decisions.md` says must be **0** on every MMU filament profile, and `print_default_chamber_temp: 0`. If it can never be nonzero, it is dead weight. |
| 2 | `force_homing_before_brush: True` | **Wrong for current hardware.** It adds a `G28 Z` before every `clean` "to be sure to not miss the brush" — but the brush is now **gantry-mounted**, so its Z tracks the toolhead and only an X slide engages it (`docs/decisions.md`). Z-homing for brush clearance is meaningless now, and this fires **twice** (two `clean` actions). |
| 3 | `purge` action vs Blobifier | Possible triple purge. With `force_purge_standalone: 1`, the initial tool load inside `extruder_heating` triggers a **Blobifier purge**; then the `purge` action purges ~30 mm; then `primeline` purges another ~30 mm. Determine how many actually run and whether `purge` is now redundant. |
| 4 | `purge_bucket_xyz: 9, 359` | Possibly unsafe. This was repointed at the **Blobifier tray area**. Klippain's `PURGE` moves there and extrudes with the **tray state unknown** — if the tray is extended, filament lands on the tray rather than in the bucket and gets carried around. Verify what the tray is doing at that moment. |
| 5 | Ordering: `contact_auto_calibrate` → `tilt_calib` | Beacon model calibration currently runs **before** QGL. Check whether calibrating on an unlevelled gantry is valid, or whether it should follow `tilt_calib`. (Reorder only — the step itself stays.) |
| 6 | Two `clean` actions | Expected to be legitimate: #1 gives contact probing a clean tip, #2 removes purge remnants. Confirm both still earn their place; do not remove without a reason. |

## Step 1 — Read the ground truth first
```
docs/start_print_walkthrough.md      # traces all 13 actions, with a timeline
docs/decisions.md                    # why several of these are as they are
```
Then read the live values:
```
grep -n "startprint_actions" overrides.cfg
grep -nE "chamber|purge|brush|prime_line|soak" variables.cfg
```

## Step 2 — Establish what actually runs *(user runs a print; model reads logs)*
The purge chain (candidates 3 and 4) cannot be settled by reading config — the Blobifier purge
only happens on the initial tool load at runtime. Ask the user to start a normal 2-colour print
and let it reach the first layer, then:
```
ssh ernst@192.168.1.240 'grep -aE "Purging|purge|PRIMELINE|Prime|CLEAN_NOZZLE" ~/printer_data/logs/mmu.log | tail -40'
ssh ernst@192.168.1.240 'tail -200 ~/printer_data/logs/klippy.log | grep -aiE "purge|prime|clean|G28"'
```
Count: how many separate purges occur between START_PRINT and layer 1, and how much filament each
consumes. Ask the user what the tray was doing during the Klippain `purge` step if the logs
don't settle it — that is a physical observation only they can make.

## Step 3 — Classify every action
Produce a table: **active and correct** / **no-op** / **wrong for current hardware** / **suspect,
needs a test**. Every entry needs evidence — a config value, a log line, or a user observation.
"Looks unnecessary" is not evidence.

## Step 4 — Present findings and get approval
Show the table plus a proposed change list, smallest-blast-radius first. State explicitly for each
proposal what would break if the hypothesis is wrong. **Wait for approval before editing.**

## Step 5 — Apply approved changes
All edits in `overrides.cfg` / `variables.cfg`. After editing, the PostToolUse hook re-runs the
toolchange visualizer automatically — confirm it still reports clean. Then:
```
FIRMWARE_RESTART      # user runs; never mid-print
```

## Step 6 — Verify with a real print *(user runs)*
A normal 2-colour print, cold start, watched to the end of layer 1.
- [ ] START_PRINT completes with no errors and no skipped-step warnings
- [ ] First layer quality unchanged (adhesion, squish, no gaps at the start of the print)
- [ ] Nozzle is clean when printing begins
- [ ] For each removed step: confirm nothing regressed that it was supposedly protecting
- [ ] `uv run tools/visualize_toolchange.py` still reports clean

## Commit guidance
Likely one commit:
`fix(start_print): remove no-op and hardware-stale steps from the action sequence`
— `overrides.cfg`, `variables.cfg`. Add a `docs/decisions.md` entry for anything removed whose
absence would look like an oversight later (especially if `chamber_soak` goes — a future session
will wonder why there is no chamber handling in START_PRINT; the answer is `bed_fans.cfg`).
Update `docs/start_print_walkthrough.md` so it still matches reality.

## Status log
- **2026-07-25** — runbook created; not yet started.
- **2026-08-02** — Steps 1–4. Audit done from framework source + existing logs; Step 2 did **not**
  need a fresh print (`mmu.log.2026-07-27` 09:39–09:41 is a cold-start START_PRINT, and
  `mmu.log.2026-07-26` 17:35–17:40 a warm-start one, which together settle candidates 3 and 4).
  Results: **c1 confirmed** (no-op + 15-min latent trap) · **c2 confirmed, and worse than stated** —
  the `G28 Z` in `clean` #2 re-homes Z by *proximity* after `contact_z_home` set it by *contact*,
  overwriting the authoritative Z origin · **c3 confirmed** (triple purge on cold start) **but the
  `purge` action is not removable** — its −20 mm retract is the anti-ooze retract that PRIMELINE's
  unconditional +23 mm unretract is paired against · **c4 partly refuted** — the coordinate is
  correct by design, but the *approach* to it bypasses `_KARMAN_PARK_MOVE` · **c5 refuted** —
  calibrate-before-QGL is Klippain's own `beacon_contact` default and is required (QGL/mesh probe by
  proximity, so the model must exist first) · **c6 confirmed** (keep both cleans).
  Awaiting approval before any edit.
- **2026-08-02** — *Side quest, not part of this runbook's scope.* Chasing c4 showed START_PRINT
  motion was covered by no visualizer scenario at all, so a `start_print` scenario was added
  (`tools/visualize_toolchange.py`) and it surfaced a bug that had been making the tool
  under-report (`92ef3df` — `G1 X+n` moves were silently dropped, so wipes passed by not being
  simulated). Both are committed separately and changed **no** printer config; recorded under
  2026-08-02 in `TODO.md`. Useful result for this runbook: all three bucket approaches clear the
  y_max lane rule by only 2.1 mm (cross at x=17.1), and applying P1 removes the `clean` #2 crossing
  entirely while lifting `clean` #1's to z50.
- **2026-08-02** — Steps 5 applied after maintainer review of each proposal in turn. Two proposals
  changed materially under questioning and the record should show why:
  - **P2 was withdrawn and replaced.** Proposed removing `chamber_soak`; that was wrong. It heats
    nothing and imposes no minimum — it is a wait-with-timeout, and it is the *only* thing that can
    wait on chamber temperature (`bed_fans.cfg` has no chamber target and cannot block a print).
    Removing it would have deleted a capability the maintainer actively uses via the slicer. The
    real defect was `tolerance: 0.0`. Applied 2.0 instead.
  - **P3 "the purge is required" was overstated.** The purge is waste; the only real constraint is
    that `PRIMELINE` unretracts unconditionally, so `purge` and `unretract_length` must move
    together. Option A taken (drop the action, `unretract_length` 23 → 5).
  - Also corrected mid-session: END_PRINT's 20 mm retract never ran (unreachable `elif`), and
    `_KLIPPAIN_MMU_INIT` unloads at print start on multi-tool prints regardless of
    `mmu_unload_on_end_print` — so that flag buys nothing for 2-colour prints.

  Applied: `force_homing_before_brush: False` · new `bucket_travel_safe_z: 20` +
  `_CONDITIONAL_MOVE_TO_PURGE_BUCKET` override · `chamber_temp_tolerance: 2.0` · `purge` dropped ·
  `unretract_length: 5` · `mmu_unload_on_end_print: False`.
  Both validators pass; all 5 visualizer scenarios clean.
- **2026-08-02 — Step 6 VERIFIED. Runbook complete.** Two prints run by the maintainer: a
  single-colour (no Blobifier purge — prime line is the only purge) and a 2-colour with 5
  toolchanges. Results against the Step 6 checklist:
  - ✅ START_PRINT completed clean on both. Only console noise was `Unknown command:"M141"/"M191"`
    (cosmetic, see decisions.md). No shutdowns, no "Move out of range", no keep-out trips.
  - ✅ **First layer "much more consistent and just the right level"** — better than before, which
    is the outcome P1 predicted (the contact-set Z origin now survives to the prime line).
  - ✅ **No manual Z offset needed** — also the hardware confirmation of the nozzle-expansion fix.
  - ✅ Nozzle clean at print start on both.
  - ✅ Visualizer clean on all 5 scenarios.
  - ⚠️ **Prime line straddles the two paths, as designed and as predicted.** Slight starvation on
    the no-purge path, a *minor* blob on the Blobifier path. `unretract_length: 5` is deliberately
    the compromise; **left as-is** — a blob lands on the discarded prime line, starvation lands on
    the part. Revisit only if either end gets worse.
  - 🔧 **One defect found by the maintainer and fixed:** the safe-Z lift bobbed 5→20→5 in place
    when the toolhead was already at the bucket. Now gated on `travels` too. See decisions.md.
  - ℹ️ Teal→black bleed persists at toolchanges — expected, that is the purge-matrix task in
    TODO.md, not this runbook.

  Committed as `79a595f` (audit), `78a49cd` (thermal_expansion fix), `a00b923` (docs), on top of
  `92ef3df` / `7bbb1df` (visualizer). Archived here. **Two edits made after the last
  `FIRMWARE_RESTART` are committed but not yet live** — the `travels` guard on the safe-Z lift and
  the corrected nozzle-offset console message. Both are cosmetic/efficiency only; current running
  behaviour is correct. They apply on the next restart, no action needed.

  Handed back to `TODO.md` rather than left buried here: purge-length tuning (with the measured
  numbers), the END_PRINT `retract_filament` no-op, and revisiting the "MMU profiles must send
  CHAMBER=0" rule now that the tolerance is fixed.
