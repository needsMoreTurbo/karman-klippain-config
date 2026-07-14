# TODAY — get Karman printing 2-color again

Goal: a first multi-material print with **tip forming** (cutter deferred — blocked on the depressor and not required). Detailed slicer steps live on the HH wiki (linked); this file is the sequence + the printer-specific bits.

> Mode: SSHFS mount — edits are live after `FIRMWARE_RESTART`. Git via SSH on the Pi only.

## ✅ Already done (don't redo)
- Toolhead calibrated (manual: `extruder_to_nozzle 94.5`, `sensor_to_nozzle 85`, `entry_to_extruder 13`, `residual 5`).
- FlowGuard active **encoderless** via TurtleNeck (`flowguard_enabled: 1`). Nothing to enable.
- Tool changes `T0`/`T1` working; `MMU_TEST_PURGE` works.

---

## Step 1 — Slicer configuration
The detailed, up-to-date instructions are on the HH wiki — **follow these, don't hand-roll**:
- Slicer setup: <https://github.com/moggieuk/Happy-Hare/wiki/Slicer-Setup>
- Toolchange g-code / movement: <https://github.com/moggieuk/Happy-Hare/wiki/Toolchange-Movement>
- Purge-volume matrix (g-code preprocessing): <https://github.com/moggieuk/Happy-Hare/wiki/Gcode-Preprocessing>

Printer-specific decisions to make while following those:
- **Tip forming:** leave `force_form_tip_standalone: 1` (already set). Turn **off** the slicer's own tip shaping / ramming.
- **Who purges** — pick one:
  - **Option A — fastest first print:** slicer **wipe tower ON**, `force_purge_standalone: 0`. HH does tip-form + load; the slicer purges on its tower. Just keep the tower clear of the front-left keep-out (x=10,y=17) and the back-edge depressor zone.
  - **Option B — roadmap target:** wipe tower **OFF**, `force_purge_standalone: 1`, HH purges into the back-left bin (needs Step 2 first).
  - _Recommendation: do **Option A** to get a print out, then switch to B once the bin/park is set._
- Set the **Tx toolchange g-code** and a **filament profile per gate** (gate 0 → T0, gate 1 → T1).

## Step 2 — Purge + park position (only needed for Option B)
- Set a real toolchange **park XY** in `_MMU_SEQUENCE_VARS` (park positions are still `-999` = "don't move"). See the Toolchange-Movement wiki above.
- Purge amount math (and why `MMU_TEST_PURGE` pushed exactly the residual): `docs/mmu_purge_volume.md`.
  Without a slicer matrix, purge = residual only (~5 mm). For real color-change volumes, load a matrix via
  slicer preprocessing or `MMU_CALC_PURGE_VOLUMES MULTIPLIER=..`.

## Step 3 — 🎯 First 2-color test print
- Small 2-color model, slow speeds.
- Watch: clean tip on unload, load reaches the nozzle, purge clears the old color, no false FlowGuard trips, no stall on gate 1.
- If a toolchange errors mid-print: `MMU_RECOVER` → inspect → resume.

---

## Deferred / watch items
- **Filamatrix cutter** — blocked on the beefy-depressor install. Then set `pin_loc_xy` / `pin_loc_compressed_xy` / `pin_park_dist` / `cutting_axis` (back-edge, high-Y) and switch `form_tip_macro: _MMU_FORM_TIP → _MMU_CUT_TIP`. Geometry `blade_pos 69` / `retract_length 64` already staged. Not needed for Step 3.
- **Extruder `run_current` = 0.45 A** (Klippain default) — weak; broke auto toolhead-cal via slip. If you see clicking / under-extrusion during purge or print, bump `[tmc2209 extruder] run_current` in `overrides.cfg` to ~70–80% of the motor's rating (need the toolhead motor spec).
