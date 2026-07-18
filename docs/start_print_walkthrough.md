# START_PRINT walkthrough — Karman

A step-by-step trace of what `START_PRINT` actually does on this machine, including
all Klippain framework logic, our overrides, and the Happy Hare (MMU) integration.

Reference command (the one this document traces):

```
START_PRINT EXTRUDER_TEMP=275 BED_TEMP=105 MATERIAL=ABS SIZE=154.586_158.81_232.191_278.9
            INITIAL_TOOL=0 TOOLS_USED=0,1 CHAMBER=0 TOTAL_LAYER=5
```

Assumed start state: printer cold, MMU homed, extruder empty, gates 0 and 1 loaded
with filament parked at the gates.

## Who owns what

| Piece | File | Notes |
|---|---|---|
| `START_PRINT` + `_MODULE_*` actions | `macros/base/start_print.cfg` (Klippain framework) | The orchestrator. Modular: runs a list of named actions in order. |
| Action list (custom) | `overrides.cfg` → `_USER_VARIABLES.startprint_actions` | Ours. Identical to the Beacon-contact default **plus `nozzle_expansion`** inserted after `extruder_heating`. |
| Tunables (temps, soak, brush/purge positions, materials) | `variables.cfg` | Ours. |
| MMU glue (`_KLIPPAIN_MMU_INIT`, `_KLIPPAIN_MMU_LOAD_INITIAL_TOOL`) | `macros/hardware_functions/mmu.cfg` (Klippain framework) | Bridges START_PRINT and Happy Hare. |
| Actual filament handling (`MMU_CHECK_GATE`, `MMU_CHANGE_TOOL`, …) | Happy Hare (`mmu/base/*.cfg` + `~/Happy-Hare`) | NightOwl, 2 gates, type-B (per-gate gear steppers, VirtualSelector), encoderless, TurtleNeck sync-feedback buffer, Filamatrix cutter. |
| Beacon contact probing framework | `macros/base/probing/virtual_z_probe.cfg` + `hooks/beacon_contact.cfg` | Temperature guard + the two `G28 Z METHOD=CONTACT` variants. |
| Nozzle thermal expansion compensation | `thermal_expansion.cfg` (ours) | Registered as the `nozzle_expansion` action. |

## Feature flags that shape this run

Resolved from `printer.cfg` includes and `variables.cfg`:

- **Probe**: `beacon_contact` — Z is a Beacon virtual endstop; contact ops are temperature-guarded (`probe_needs_contact_temp_guard: True`, max contact temp 180 °C, safe preheat temp 150 °C).
- **QGL** enabled (Voron 2.4). **Chamber sensor** enabled (toolhead `Chamber` sensor) but `CHAMBER=0` in the command, so the chamber soak is a no-op this run.
- **Status LEDs** and **caselight** enabled. **Hotend-fan tachometer** monitoring enabled.
- **Not present / disabled**: exhaust filter, Klippain filament sensor (SFS removed), firmware retraction, part-fan tachometer, Z-calibration plugin.
- **MMU**: enabled, `print_start_detection: 1` — Happy Hare detects print start/end itself from the virtual-SD job, so **every** `_MMU_PRINT_START` / `_MMU_PRINT_END` call inside the Klippain glue is skipped. HH has already put itself into "printing" state by the time START_PRINT runs.
- **Gate check**: `variable_mmu_check_gates_on_start_print: True` + slicer passes `TOOLS_USED=!referenced_tools!` (resolved by the Moonraker preprocessor to `0,1`).
- ABS material entry: pressure advance 0.048, additional Z offset 0. (Its `filter_speed: 80` and `filament_sensor: 1` fields are unused — no filter, no Klippain-managed sensor.)

---

## Phase 0 — Prologue (parameter capture and machine reset)

All in `START_PRINT` itself, before any action module:

1. **Startup guard** — aborts if Klippain's startup sequence didn't complete (`klippain_startup_succeeded`).
2. **Parameter capture** — every slicer parameter is copied into `gcode_macro START_PRINT` variables (`bed_temp=105`, `extruder_temp=275`, `soak=8` *(default from `variables.cfg`, not passed)*, `chamber_temp=0`, `initial_tool=0`, `tools_used="0,1"`, `check_gates=1`, `material="ABS"`, `fl_size="154.586_…"`, …). The action modules read these variables instead of taking arguments — this is why the modules have no parameters.
3. **Layer stats** — `TOTAL_LAYER=5` is pushed into `SET_PRINT_STATS_INFO` (drives the layer display in Mainsail/KlipperScreen).
4. **Material lookup** — `ABS` found in `material_parameters`; console prints `Material 'ABS' is used`. Unknown materials abort the print here.
5. **LEDs BUSY, caselight to 100 %** (`light_intensity_start_print`).
6. **State reset** — `CLEAR_PAUSE`, `BED_MESH_CLEAR`, `SET_GCODE_OFFSET Z=0`, `M221 S100`, `M220 S100`, `G90`, `M83`. Any leftover Z offset / flow / speed factor from a previous print is wiped.
7. **Hotend fan watchdog** — starts the `_BACKGROUND_HOTEND_TACHO_CHECK` delayed-gcode loop (runs for the entire print; pauses the print if the hotend fan stalls).
8. **Pressure advance** — `SET_PRESSURE_ADVANCE ADVANCE=0.048` (ABS). Firmware retraction block skipped (not enabled).
9. **Homing** — `force_homing_in_start_print: False` → `_CG28` (home only if needed). Cold boot means a **full G28**: X and Y to their switches, then Z by **Beacon contact** (`home_method: contact`, and because the axis is unhomed, `home_autocalibrate: unhomed` also builds the Beacon proximity model on this first touch). The nozzle is cold, so touching the bed is clean — no ooze smear.

## Phase 1 — MMU initialization (`_KLIPPAIN_MMU_INIT`)

Runs immediately after homing, **before any heating**, so gate problems abort the
print while everything is still cold.

10. `_MMU_PRINT_START` branch skipped (`print_start_detection=1`, see above).
11. **`PARK E=0`** — toolhead lifts 50 mm and parks back-right (343, 352). `E=0` means "retract nothing" (and the cold extruder couldn't anyway). This just gets the head somewhere safe while the MMU works.
12. **`MMU_HOME` skipped** — MMU is already homed and `mmu_force_homing_in_start_print: False`. (With the NightOwl's VirtualSelector there's no physical selector to home anyway.)
13. **Gate check** — `TOOLS_USED="0,1"` is valid and is a multi-tool list, so the multi-filament branch runs:
    - Console: *"You are planning a multi-filament print. The tool(s): 0,1 will be checked…"*
    - `MMU_UNLOAD` — safety unload in case a tool was left loaded; with the extruder empty it's a no-op.
    - **`MMU_CHECK_GATE TOOLS=0,1`** — for each gate, HH briefly drives that gate's gear stepper until the post-gear (`mmu_gear`) sensor proves filament is present, then parks it back (`gate_parking_distance: 0`). Updates the gate map (Available/Empty). This is the step that catches "you forgot to load gate 1" *before* 10+ minutes of heating.
    - `MMU_SELECT TOOL=0` — re-selects the initial tool (instant on a type-B MMU).
14. **Early error check skipped** (`mmu_check_errors_on_start_print: False`).
15. **Sync-to-extruder block is inert** — the Klippain glue reads `printer.configfile.config.mmu.sync_to_extruder`, an option that no longer exists in this Happy Hare version. Both branches evaluate false, so nothing happens. Print-time gear/extruder sync is governed entirely by HH itself (TurtleNeck sync-feedback buffer, `sync_gear_current: 70`, flowguard enabled) — the `SYNC_MMU_EXTRUDER` slicer parameter does nothing on this machine.
16. **Preload skipped** — the selected tool already equals `INITIAL_TOOL`, and the gate check just verified/parked its filament. Nothing to do.

## Phase 2 — The action loop

`startprint_actions` (from `overrides.cfg`) runs in this order. It is the standard
Beacon-contact sequence with **`nozzle_expansion`** added after `extruder_heating`:

> bed_soak → extruder_preheating → chamber_soak → clean → contact_auto_calibrate →
> tilt_calib → bedmesh → contact_z_home → extruder_heating → **nozzle_expansion** →
> purge → clean → primeline

### 17. `bed_soak` — bed to 105 °C + 8 min soak
Bed is cold (< 105−8 °C), so the full branch runs: toolhead moves to center-front
(≈ X175 Y120, Z50) so the hotend fan helps stir chamber air, then
`HEATSOAK_BED TEMP=105 SOAKTIME=8` → `M190 S105` (blocks until the Keenovo reaches
105 °C at `max_power: 0.8`), then eight 1-minute dwells with a countdown in the
console. If the bed had already been within 8 °C of target, the soak would be
skipped entirely (`SOAKTIME=0`).

### 18. `extruder_preheating` — nozzle to 150 °C (blocking)
Because `probe_needs_contact_temp_guard: True`, this is `M109 S150`, a **blocking**
wait — not the fire-and-forget `M104` other probe types get. 150 °C
(`safe_extruder_temp`) is the temperature all Beacon contact probing happens at:
warm enough for repeatable contact, cool enough (< 180 max) not to ooze or brand
the PEI.

### 19. `chamber_soak` — no-op this run
`CHAMBER=0` → the module's `CHAMBER_TEMP > 0` test fails immediately. (With a
setpoint it would park center-front and poll the toolhead `Chamber` sensor
minute-by-minute up to `CHAMBER_MAXTIME`, default 15 min.)

### 20. `clean` (first of two) — brush the cold-ish nozzle
`force_homing_before_brush: True` → `G28 Z` first (now that the axis is homed this
uses Beacon **proximity**, per `home_method_when_homed: proximity` — no bed touch).
Then: accel drops to 1500, toolhead moves via the purge bucket (50, 357) to the
brush (135, 356, Z1) and does 6 X-axis wipe pairs across the 35 mm brush at
100 mm/s. Purpose: scrape any debris off the nozzle **before** it touches the bed
for calibration. At 150 °C leftover filament is soft enough to wipe.

### 21. `contact_auto_calibrate` — Beacon model calibration
Wrapped in the contact guard (`_PROBE_ENTER_CONTACT_GUARD`): target is 150 ≤ 180 so
no cooldown is needed; the guard just records state. Hook executes
**`G28 Z METHOD=CONTACT CALIBRATE=1`** — the nozzle touches the bed at bed center
and Beacon rebuilds its proximity model against that true zero *at the current
thermal state of the frame*. Guard exit: 5 mm Z-hop, restore saved temp (still 150).

This is the step people confuse with the later `contact_z_home`: **this one exists
to calibrate the proximity model** so that QGL and the bed mesh (both proximity
sweeps) are accurate.

### 22. `tilt_calib` — QGL
`_TILT_CALIBRATE FORCE=false` → gantry not yet leveled this boot → `QUAD_GANTRY_LEVEL`
runs, using fast Beacon proximity probing (accurate thanks to step 21).

### 23. `bedmesh` — adaptive mesh over the first-layer footprint
No `MESH` profile passed → `ADAPTIVE_BED_MESH SIZE=154.586_158.81_232.191_278.9`.
The macro takes the first-layer bounding box (X 154.6→232.2, Y 158.8→278.9), pads it
with a margin, scales the probe count down proportionally, and runs
`BED_MESH_CALIBRATE` over just that window (Beacon proximity sweep — seconds, not
minutes). Meshing only what you print is why SIZE is in the slicer start gcode.

### 24. `contact_z_home` — the *real* Z zero
Guard again, then **`G28 Z METHOD=CONTACT CALIBRATE=0`** — one more nozzle touch,
no recalibration, purely to set the final Z origin **after** QGL moved the gantry
and after the mesh. This touch is the Z reference the first layer is printed
against. Ends with a 5 mm Z-hop.

### 25. `extruder_heating` — 275 °C + initial tool load
- Toolhead moves over the purge bucket (50, 357, Z5) so all heating ooze and the
  upcoming load happen over the bin.
- `M109 S275` — blocking heat to print temperature.
- `_KLIPPAIN_MMU_LOAD_INITIAL_TOOL` → **`MMU_CHANGE_TOOL TOOL=0 STANDALONE=1`**
  (`STANDALONE=1` = don't expect slicer tip-forming gcode; irrelevant here anyway
  since nothing is loaded, so no cut/tip step runs). Happy Hare then loads gate 0:
  1. Gear stepper fast-feeds through the bowden (auto-tuned length minus
     `extruder_homing_buffer: 25`).
  2. Slow advance until the **pre-extruder `extruder` switch** (Filamatrix sensor,
     PB0) triggers (`extruder_homing_max: 80`).
  3. Synced gear+extruder feed into the extruder until the **`toolhead` sensor**
     (PB1) triggers (`toolhead_homing_max: 60`).
  4. Final metered extrude to the nozzle tip:
     `toolhead_sensor_to_nozzle (85) − toolhead_residual_filament (25) −
     toolhead_ooze_reduction (2) = 58 mm`.
  5. `toolhead_post_load_tighten: 60` — the gear briefly reverses at reduced
     current to take slack out of the filament path.
- HH's own load-verification (sensors + flowguard) stands in for the old encoder.

### 26. `nozzle_expansion` — hot-nozzle growth compensation (our addition)
`_BEACON_SET_NOZZLE_TEMP_OFFSET`: the Z reference was established by contact at
150 °C, but at 275 °C the nozzle is physically longer. Offset applied:

```
(275 − 150) × (0.055 / 100) × 1.0 = +0.069 mm   (SET_GCODE_OFFSET Z_ADJUST, MOVE=1)
```

i.e. the head is raised ~0.07 mm to restore the true first-layer gap. The
coefficient (0.055 mm/100 °C) lives in `save_variables.cfg`; the mirror action in
END_PRINT removes exactly the applied amount. **Position in the list matters**: it
must come after `extruder_heating` (so `extruder.target` is the real print temp)
and after the contact steps (so it stacks on the final Z origin).

### 27. `purge` — 30 mm into the bucket
`PURGE TEMP=275`: over the bucket, extrude 30 mm at F150, then retract 20 mm
(`retract_length` from `variables.cfg` — a deep retract that pulls the melt out of
the heatbreak to stop oozing), then wait 10 s (`purge_ooze_time`) to let the
nozzle finish drooling. This clears the load ooze and pressurizes fresh ABS
through the nozzle.

### 28. `clean` (second) — brush off the purge remnants
Same as step 20, now at 275 °C. The preceding `G28 Z` is again a proximity home —
safe at print temperature (contact would be blocked by the 180 °C guard, but it is
never requested here).

### 29. `primeline` — adaptive prime line
`PRIMELINE SIZE=… ADAPTIVE_MODE=1`. With this SIZE the default start point (5, 2.5)
is pulled toward the print: clamped to `(xMin−5, yMin−5)` → the line starts at
**≈ (149.6, 153.8)**, running **+X** for 40 mm at Z 0.6. Sequence: unretract 23 mm
(`unretract_length` — refills the 20 mm purge retract plus pressure), extrude 30 mm
of filament along the line (~3 mm wide bead, ~5.5 mm/s for a 10 mm³/s flowrate),
micro-retract 0.2 mm, hop to Z3, sidestep 2/2 mm so the slicer's first Z move can't
drag the nozzle back through the line, `M400`.
(The clog-detection disable/re-enable calls inside PRIMELINE are inert for the same
`sync_to_extruder` reason as step 15.)

## Phase 3 — Epilogue

30. `SET_GCODE_OFFSET Z_ADJUST=0` (no `Z_ADJUST` passed) and `Z_ADJUST=0` again for
    ABS `additional_z_offset` — both no-ops this run, but this is where a slicer
    per-profile Z tweak or a material offset would stack onto the offsets from
    steps 24/26.
31. Filter start skipped (none), filament-sensor enable skipped (none).
32. LEDs → PRINTING, caselight → 80 % (`light_intensity_printing`).
33. Final `_MMU_PRINT_START` branch skipped once more (`print_start_detection=1`).
34. Console: `Start printing !`, then `G92 E0` — extruder position zeroed, control
    returns to the sliced gcode.

---

## Things easy to misread

- **Two `clean` actions is deliberate**: one *before* contact probing (clean nozzle
  → trustworthy touch), one *after* the purge (clean nozzle → tidy first layer).
- **`contact_auto_calibrate` vs `contact_z_home`**: both touch the bed with the
  nozzle. The first (CALIBRATE=1) exists to calibrate Beacon's *proximity model*
  before QGL/mesh; the second (CALIBRATE=0) sets the *final Z origin* after the
  gantry has been leveled. Removing either breaks a different thing.
- **All bed-touching happens at ≤150 °C** via the contact temperature guard; every
  later `G28 Z` uses proximity (`home_method_when_homed: proximity`) and never
  touches, so 275 °C is safe there.
- **Gate check ≠ load**: `MMU_CHECK_GATE` only proves filament exists at gates 0
  and 1 (cheap, cold, early). The actual load to the nozzle happens ~15 minutes
  later inside `extruder_heating`, once the hotend is at 275 °C.
- **`SYNC_MMU_EXTRUDER` and the PRIMELINE clog-detection toggles do nothing** on
  this HH version — the config key Klippain checks (`sync_to_extruder`) no longer
  exists. Print-time sync behavior is owned by HH (sync-feedback buffer +
  flowguard).
- **The 20 mm purge retract and 23 mm prime-line unretract are a matched pair**
  (`retract_length` / `unretract_length` in `variables.cfg`). Change one, revisit
  the other, or the prime line starts starved or over-pressurized.
- **Bed fans are absent from this sequence on purpose** — the `bed_fans.cfg` state
  machine is always-on and self-triggering (see `docs/bed_fans_control.md`).

## Approximate timeline (cold ABS start)

| Step | Duration |
|---|---|
| Homing + MMU park/gate check | ~1 min |
| Bed to 105 °C | ~8–12 min |
| Bed soak | 8 min |
| Nozzle to 150 °C | ~1 min (overlaps nothing — blocking) |
| Clean + calibrate + QGL + mesh + Z home | ~2–3 min |
| Nozzle 150 → 275 °C + tool load | ~2 min |
| Purge (incl. 10 s ooze) + clean + prime | ~1 min |
| **Total** | **~25–30 min** |
