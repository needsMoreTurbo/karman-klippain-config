# TODAY — verify the back-left rework, bring Blobifier live

Hardware rework is configured (cut @ back-left z15, gantry brush/rest, blobifier geometry, side-approach
parking). Nothing is trusted until jogged/tested. **`FIRMWARE_RESTART` first** to load it all
(servo will auto-cycle ~5 s after boot).

> Keep-outs while hand-jogging: front-left (x<10, y<17, any Z — idler); back-left (x<20, y>335, z<15 —
> blobifier + depressor); enter the y_max feature row only via lanes **15<x<40** or **x>95**, then slide in X.

## Step 0 — Preview the paths offline (new tool)
```
uv run tools/visualize_toolchange.py        # writes tools/toolchange_viz.html
```
Simulates 4 scenarios (mid-print swap, swap+shake, pause-park, complete-park) from the LIVE macro/config
values and draws the toolpath over the bed map with zones + automatic violation checks (idler keep-out,
depressor pin volume, y_max lane rule). Re-run after ANY geometry/config change — it reads the current files.

## Step 1 — Jog verification (no filament ops, hand on E-stop)
Home, then:
1. **Cut path at z15**: `G1 Z15` → `G1 X30 Y300` → `G1 X20 Y341` (pin park) → `G1 X15` (contact) →
   slowly `G1 X5` … watch lever compress and **shaker-arm clearance** the whole way → `G1 X20`.
2. **y_max lane + rest/brush slide**: at z15: `G1 X30 Y300` → `G1 Y359` (lane entry) → `G1 X45` (rest) →
   `G1 X53` → `G1 X88` (brush sweep) → back to `G1 X30` → `G1 Y300` (lane exit).
3. **Tray approach (Blobifier's own path)**: `G1 X33 Y359` → `G1 Z0.5` → `G1 X9` — verify tray/base/arm
   clearances at low Z → `G1 Z15` → out via the lane.
4. **Bed-mesh rear-left check**: `G1 Z3` → `G1 X20 Y330` → `G1 X10 Y330` — eyeball clearance to the
   depressor mount + blobifier base (mesh rows can put the nozzle here). If tight, we shrink the mesh Y range.

## Step 2 — Re-validate the cut at the new depressor
```
T0            (hot)
MMU_EJECT
```
Watch: approach at **z≥15** (the new `min_toolchange_z` floor), cut at 15→0 @ y341, flat sheared face at
the gate. Pointy face or any low-Z approach → stop, report.

## Step 3 — Blobifier live tests (one piece at a time)
1. `BLOBIFIER_SERVO POS=out` / `POS=in` with tray installed — full travel, no buzz.
2. Bucket switch: `QUERY_BUTTON BUTTON=bucket` + hand actuation ("bucket installed"/"removed").
3. **First blob** (hot, loaded): `BLOBIFIER PURGE_LENGTH=30` — tray out → pulsed purge with Z raise →
   tray-cycle deposit → count message → wipe on gantry brush. Watch shaker-arm clearance during the x9 work.
4. **Wipe only**: `BLOBIFIER_CLEAN` — lane entry, X-only scrub at any Z (brush_top None), lane exit.
5. **Shake**: `BLOBIFIER_SHAKE_BUCKET SHAKES=4` — engagement at x≈4.1 z4, 4mm Y strokes, clean disengage.
6. **Park to rest**: trigger a pause (`MMU_PAUSE` or PAUSE) — toolhead should lane-approach and slide to
   the rest (45,359) via `_KARMAN_PARK_MOVE`; resume should slide out through the lane.

## Step 4 — HH integration (purge ownership → Blobifier)
1. `mmu_parameters.cfg`: `purge_macro: BLOBIFIER`, `force_purge_standalone: 1`.
2. `mmu_macro_vars.cfg`: `variable_user_post_form_tip_extension: "BLOBIFIER_PARK"`,
   `variable_restore_xy_pos: "next"`.
3. OrcaSlicer: wipe tower **OFF**; add before `START_PRINT`:
   `MMU_START_SETUP INITIAL_TOOL={initial_tool} REFERENCED_TOOLS=!referenced_tools! TOOL_COLORS=!colors! TOOL_TEMPS=!temperatures! TOOL_MATERIALS=!materials! FILAMENT_NAMES=!filament_names! PURGE_VOLUMES=!purge_volumes!`
4. `FIRMWARE_RESTART`, then a full `T0`↔`T1` swap: cut (z15) → unload → load → **BLOBIFIER purge** → wipe.

## Step 5 — 🎯 2-color print with cutter + blobifier
Small test model. Watch: toolchange sequence end-to-end, blob quality (see BLOB TUNING table in
blobifier.cfg), transitions (tune `purge_length_modifier` 0.6 / slicer matrix), no FlowGuard trips,
START_PRINT purge/clean at the new bucket/brush coords behave.

## Parked / later
- Walk `retract_length` up 55→62; retune if the new cut geometry changes behavior.
- 2nd ground to Leviathan (base mod + reprint) · gate-1 latch @99.5% · bed-polygon exclusions in Orca.
- Commit the batch once Steps 1–4 verify (blobifier cfg + macro_vars + overrides + variables + docs).
