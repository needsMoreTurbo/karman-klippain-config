# Runbook — verify the back-left rework and bring Blobifier live

**Objective:** prove the reworked back-left geometry is safe, get Blobifier purging in a real
toolchange, and finish with a 2-colour print using cutter + blobifier.
**Status:** ✅ complete (2026-07-24) · **Created:** 2026-07-17 (migrated from TODAY.md 2026-07-25)
**Prerequisites:** hardware rework installed (depressor back-left, gantry brush/rest, blobifier
tray/arm); config already written — **`FIRMWARE_RESTART` before Step 1** (the servo auto-cycles
~5 s after boot, expect motion).

## Scope
Jog-verify the new paths → re-validate the cut at the relocated depressor → exercise Blobifier
piece by piece → hand purging to Blobifier → 2-colour print.

## ⚠️ Out of scope — do not touch
- **`park_toolchange` stays `-999,-999`.** Looks like an oversight; is deliberate (Blobifier
  positions itself). See `docs/decisions.md`.
- **Cut geometry** (`pin_loc_xy 15,341` → `pin_loc_compressed_xy 0,341`) — measured, validated.
- **`min_toolchange_z: 15`** — this is what keeps toolchange travel above the shaker arm.
- **PSF sync-feedback calibration** — freshly calibrated; `flowguard_max_relief` tuning is a
  separate objective.
- Do not use **`MMU_TEST_FORM_TIP`** on this machine (see CLAUDE.md).

## Keep-outs while hand-jogging
Front-left (x<10, y<17, **any Z** — cutter arm vs idler) · back-left (x<20, y>335, z<15 —
blobifier + depressor) · the y_max feature row is entered only via lanes **15<x<40** or **x>95**,
then slid in X.

## Step 0 — Preview the paths offline
```
uv run tools/visualize_toolchange.py     # writes tools/toolchange_viz.html
```
Simulates the real macros against live config values and auto-checks the keep-out zones. Expect
**clean** on all scenarios. (Now also runs automatically via the PostToolUse hook.)

## Step 1 — Jog verification *(user runs; hand on E-stop, no filament)*
Home, then:
1. **Cut path at z15:** `G1 Z15` → `G1 X30 Y300` → `G1 X20 Y341` (pin park) → `G1 X15` (contact)
   → slowly toward `G1 X5`, watching lever compression **and shaker-arm clearance** → `G1 X20`.
2. **y_max lane + rest/brush slide:** at z15: `G1 X30 Y300` → `G1 Y359` (lane entry) → `G1 X45`
   (rest) → `G1 X53` → `G1 X88` (brush sweep) → `G1 X30` → `G1 Y300` (lane exit).
3. **Tray approach:** `G1 X33 Y359` → `G1 Z0.5` → `G1 X9` — verify tray/base/arm clearance at low
   Z → `G1 Z15` → out via the lane.
4. **Bed-mesh rear-left check:** `G1 Z3` → `G1 X20 Y330` → `G1 X10 Y330` — eyeball clearance to
   the depressor mount and blobifier base. If tight, shrink the mesh Y range.

## Step 2 — Re-validate the cut *(user runs, hot)*
```
T0
MMU_EJECT
```
Expect: approach at **z≥15**, cut 15→0 at y341, **flat sheared face** at the gate. A pointy face
or any low-Z approach → stop and report.

## Step 3 — Blobifier live tests *(user runs; one piece at a time)*
1. `BLOBIFIER_SERVO POS=out` / `POS=in` — full travel, no buzz.
2. `QUERY_BUTTON BUTTON=bucket` + actuate by hand — "bucket installed" / "removed".
3. **First blob** (hot, loaded): `BLOBIFIER PURGE_LENGTH=30` — tray out → pulsed purge with Z
   raise → tray-cycle deposit → count message → wipe. Watch shaker clearance during the x9 work.
4. `BLOBIFIER_CLEAN` — lane entry, X-only scrub (brush_top None), lane exit.
5. `BLOBIFIER_SHAKE_BUCKET SHAKES=4` — engage at x≈4/z4, 4 mm Y strokes, clean disengage.
6. Pause → should lane-approach and slide onto the rest (45,359); resume slides out via the lane.

## Step 4 — Hand purging to Blobifier
1. `mmu_parameters.cfg`: `purge_macro: BLOBIFIER`, `force_purge_standalone: 1`.
2. `mmu_macro_vars.cfg`: `user_post_form_tip_extension: "BLOBIFIER_PARK"`, `restore_xy_pos: "next"`.
3. OrcaSlicer: wipe tower **OFF**; add before `START_PRINT`:
   `MMU_START_SETUP INITIAL_TOOL={initial_tool} REFERENCED_TOOLS=!referenced_tools! TOOL_COLORS=!colors! TOOL_TEMPS=!temperatures! TOOL_MATERIALS=!materials! FILAMENT_NAMES=!filament_names! PURGE_VOLUMES=!purge_volumes!`
4. `FIRMWARE_RESTART`, then `T0`↔`T1`: cut (z15) → unload → load → **Blobifier purge** → wipe.

## Step 5 — 🎯 2-colour print with cutter + blobifier
Small model. Watch: full toolchange sequence, blob quality (BLOB TUNING table in
`blobifier.cfg`), colour transitions (`purge_length_modifier` 0.6 / slicer matrix), no FlowGuard
trips, START_PRINT purge/clean behaving at the new bucket/brush coords.

## Verification
- [ ] All four jog paths clear, no contact
- [ ] Cut produces a flat face, approach never below z15
- [ ] Blobifier: blob adheres, wipe clean, shake engages/disengages, pause parks on rest
- [ ] A real `T0`↔`T1` swap purges via Blobifier
- [ ] 2-colour print completes with clean transitions
- [ ] `uv run tools/visualize_toolchange.py` still reports clean

## Commit guidance
Likely one commit once Steps 1–4 verify:
`feat(mmu): hand in-print purging to blobifier` — mmu_parameters.cfg, mmu_macro_vars.cfg.
Docs updates separately.

## Status log
- **2026-07-25** — migrated from TODAY.md. Steps 0–4 were substantially exercised during the
  long build session: servo/switch/blob/wipe/shake all tested, purge ownership handed to
  Blobifier, `park_toolchange` sentinel bug found and fixed, nozzle LEDs set white during purge.
  **Remaining:** the Step 5 2-colour print, and confirming Step 1.4 (bed-mesh rear-left jog).

## Parked / later (separate objectives)
- Walk `retract_length` 55 → 62.
- `flowguard_max_relief` 40 → ~15 now the PSF is calibrated.
- 2nd ground to Leviathan (base mod + reprint) · gate-1 latch @ 99.5% · Orca bed-polygon exclusions.

- **2026-07-24 — OBJECTIVE COMPLETE.** 2-colour print with cutter + Blobifier ran successfully:
  full chain (cut at z15 → unload → load → Blobifier purge → gantry-brush wipe → resume) validated
  on a real print. Runbook archived.
  **Loose ends handed back to TODO.md** (not blockers): confirm the OrcaSlicer wipe tower is off
  (Process → Multimaterial → Prime tower → Enable), the bed-mesh rear-left jog check (Step 1.4,
  never confirmed by hand), and `flowguard_max_relief` 40 → ~15.
