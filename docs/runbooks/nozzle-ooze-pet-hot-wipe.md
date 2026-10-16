# Runbook — PET ooze survives the START_PRINT nozzle wipe

**Objective:** after a PET, PC, PA, ABS or ASA print (per-material wipe temp, amended 2026-10-15), the next print's nozzle is **clean before the first
Beacon contact touch**. Two halves:
(1) **END_PRINT** wipes the still-hot nozzle and runs the part fan while it cools on the rest, so
less ooze forms;
(2) **START_PRINT** after a PET/PC/PA/ABS/ASA print heats to **230/200/180 °C (by material) on the nozzle rest**, wipes, then cools for
contact. At 150 °C the attached PET ooze is too stiff to brush off.
**Status:** 🟠 applied and running on hardware — waiting on the maintainer's ooze verdict (nozzle clean before the first touch?), a PET start, and a PA/PC/MMU-enabled run
**Created:** 2026-10-10
**Prerequisites:** printer idle for every `FIRMWARE_RESTART`; PET or PET-GF loaded (both gates are
`PET` / 290 °C in Happy Hare's gate map as of 2026-10-09); one small PET model and one ABS model to
slice.
**Run order:** execute this runbook **before** `docs/runbooks/start-print-cold-start-speedup.md`
(maintainer's choice, 2026-10-10). That runbook rewrites the same `startprint_actions` list. Step 9
here updates it to keep this runbook's actions.

## Background (traced 2026-10-10)

- **The symptom.** PET oozes as the nozzle cools after a print. At the next START_PRINT, the first
  `clean` (Klippain `CLEAN_NOZZLE`) runs right after `extruder_preheating` has brought the nozzle
  to `safe_extruder_temp` = **150 °C**. That is too cold to soften the PET skin, so the brush
  doesn't remove it, and Beacon's contact touch then happens with ooze on the nozzle.
  `docs/start_print_walkthrough.md` has the full START_PRINT trace.
- **END_PRINT today** (`macros/base/end_print.cfg`, framework):
  - It calls `PARK` **first**, before any end action. Our `PARK` override parks on the nozzle
    rest, x45 / y_max.
  - It then runs `variable_endprint_actions` (`overrides.cfg`):
    `"retract_filament", "nozzle_expansion", "turn_off_heaters", "turn_off_fans", "turn_off_motors", "reset_limits"`.
  - `retract_filament` is a **complete no-op** on this machine (`docs/decisions.md` 2026-08-02).
  - Filament stays loaded (`mmu_unload_on_end_print: False`), so the full melt zone (~33 mm) sits
    hot while the nozzle cools. That is the ooze.
- **Custom actions.** Both macros dispatch any list entry to `_START_PRINT_ACTION_<NAME>` /
  `_END_PRINT_ACTION_<NAME>` if such a macro exists (`start_print.cfg:211-212`,
  `end_print.cfg:51-52`). So everything here goes in `overrides.cfg`, and no framework file is
  touched.
- **Happy Hare reports the material in the nozzle.** `printer.mmu.filament == "Loaded"` plus
  `printer.mmu.gate_material[printer.mmu.gate]` gives it (currently `"PET"`). END_PRINT records it,
  and START_PRINT reads it. This has to happen at END_PRINT, because on a multi-tool start
  `_KLIPPAIN_MMU_INIT` has already unloaded before any start action runs.
- **Klippain's contact guard** (`_PROBE_ENTER_CONTACT_GUARD`,
  `macros/base/probing/virtual_z_probe.cfg:74-82`) runs before every contact touch:
  - if the target is above 180 °C, it does `M106 S255` then `M109 S180`;
  - otherwise, if the nozzle is above 183 °C, it does `M106 S255`, then
    `TEMPERATURE_WAIT … MAXIMUM=180`, then `M106 S0`.
  - On exit it **restores the target saved at entry** with a *blocking* `M109` (and fan off), so after
    a hot wipe with the nozzle still above 150 would stall START_PRINT on a slow passive cool
    before `tilt_calib`. So `karman_hot_wipe_cool` fan-cools to 150 *before* the first contact
    (2026-10-15 decision): the saved target is 150 (not the wipe temp, or the guard would re-heat
    for QGL and the mesh), and the nozzle is already there, so the guard exit returns at once.

## Scope

1. `overrides.cfg`:
   - two new START_PRINT actions;
   - two new END_PRINT actions plus one `[delayed_gcode]`;
   - rewritten `variable_startprint_actions` and `variable_endprint_actions` lines.
2. Offline validation, plus extending `tools/visualize_toolchange.py` to cover the new motion.
3. Hardware test: a PET print, then a PET start, then an ABS start.
4. Docs:
   - the walkthrough;
   - a `docs/decisions.md` entry;
   - TODO.md, which also closes the "END_PRINT `retract_filament` is a no-op" task;
   - the amendment to the cold-start runbook (Step 9).

## ⚠️ Out of scope — do not touch

- **No END_PRINT retract, of any size.** It was considered and **rejected** (maintainer,
  2026-10-10):
  - Happy Hare can't see a retract it didn't make. The next unload's cut would land that many mm
    higher.
  - `variable_retract_length: 60` (`mmu/base/mmu_macro_vars.cfg:302`) was chosen to give the cut
    fragment ("Piece B") a 6–12 mm band, and every hidden mm comes straight off it.
  - Short fragments caused the 2026-08/09 jam regression.
  - Leave `retract_filament` in the list as it is (a harmless no-op).
- **`mmu_unload_on_end_print: False`** (`docs/decisions.md` 2026-08-02). Don't "fix" the ooze by
  unloading at the end.
- **The cut geometry** — `retract_length`, `blade_pos`, `toolhead_residual_filament: 33`,
  `pushback_length`. All coupled; see the comments in `mmu_macro_vars.cfg` / `mmu_parameters.cfg`.
- **`safe_extruder_temp: 150` and `probe_contact_max_temp: 180`.**
  - 150 is also the reference temperature of the nozzle-expansion compensation in
    `thermal_expansion.cfg`: offset = `(print_target − 150) × 0.055 / 100` mm.
  - That formula assumes the **Z-defining** touch (`contact_z_home`) happens at 150 °C. Every
    10 °C off is ~0.0055 mm of first-layer error.
  - This is why Step 3 adds a settle-to-150 action before `contact_z_home`.
- **`thermal_expansion.cfg`**, and the `nozzle_expansion` start/end actions — they stay in both
  lists, in place.
- **Both `clean` actions and both contact actions.** Each does a different job; see "Things easy
  to misread" in the walkthrough.
- **`CLEAN_NOZZLE` / `_CONDITIONAL_MOVE_TO_PURGE_BUCKET`** (and its `bucket_travel_safe_z: 20`).
  - Do **not** use `CLEAN_NOZZLE` at END_PRINT: it drops to the bucket at Z5 and the brush at Z1,
    and at END_PRINT there are parts on the bed.
  - The end wipe uses `BLOBIFIER_CLEAN`, which wipes at the **current** Z. The brush is
    gantry-mounted, so Z is irrelevant to engaging it.
- **Blobifier's own config and macros** — `mmu/addons/blobifier.cfg`. It is called, never edited.
  See the memory/maintainer rule: no edits to stock addon macros.
- **Any Klippain framework file** (`macros/`, `config/`, …). The `guard-framework` hook blocks
  edits there.
- **Keep-out zones** (Klipper has no obstacle model; `CLAUDE.md`). The new motion must respect:
  - **front-left x<10 / y<17, at any Z**;
  - **back-left x<~20 / y>~335, below z15**;
  - the **y_max feature row** (tray x2–17, shaker x4, rest x45, brush x53–88). Enter it only in
    +Y through the clear lanes **15<x<40 or x>95**, then slide in X.
  - All new parking goes through `PARK`, which uses `_KARMAN_PARK_MOVE`. Never write a raw XY move
    to the rest.

## Pre-resolved decisions (maintainer, 2026-10-10)

1. **Both halves.** End-of-print prevention *and* a start-of-print hot wipe.
2. **End of print: cool to the material's wipe temp, wipe there, keep cooling; no retract.**
   (Amended 2026-10-15 after the first PET-GF test: a wipe at print temp, ~285 °C, left the nozzle
   too hot and it oozed again afterwards. Maintainer: wipe once it reaches the wipe temperature,
   then continue cooling.)
   - One action, `karman_end_cooldown_wipe`, sits after `turn_off_heaters` and `turn_off_fans`.
     It records the nozzle material, turns the part fan to 100 %, and waits (blocking, inside
     END_PRINT) until the nozzle is at that material's **wipe temperature** (the same table as
     decision 3: 230 / 200 / 180 °C).
   - It then runs `BLOBIFIER_CLEAN` followed by `PARK E=0`, and starts the 5 s
     `_KARMAN_END_COOLDOWN_FAN_LOOP`, which turns the fan off once the nozzle is **< 120 °C**.
   - Materials with no wipe temp (PLA, TPU, …) are recorded and fan-cooled but **not** wiped. If
     the nozzle is already more than 30 °C below the wipe temp at that point, the wipe is skipped.
   - The loop stops (and turns the fan off) as soon as `extruder.target > 0`, i.e. a new print
     has heated the nozzle. It does not key on `print_stats.state`: that still reads `printing`
     while END_PRINT runs from inside the gcode file.
   - The old `karman_end_wipe` (wipe at print temp, before `turn_off_heaters`) and
     `karman_end_cooldown_fan` actions are gone.
3. **Start of print: hot wipe by material family** (amended 2026-10-15, maintainer).
   - The trigger is the saved variable `karman_last_nozzle_material`, upper-cased. Substrings are
     checked in this order, first match wins:
     the FIRST word of the material only (so "PLA SPARKLE" is PLA, not PA): `PET*` or `PCTG` → **230 °C**; `PC*` or `PA*` → **200 °C** (so PC-ABS → 200); `ABS` or `ASA` →
     **180 °C**; anything else → no hot wipe.
   - PEKK/PEI/PEEK/PSU are deliberately not handled (maintainer does not print them).
   - `karman_hot_wipe_heat` also **saves the new print's `MATERIAL`** (skipped if empty/`XXX`) after
     the wipe decision, so a cancelled print still leaves a correct value for the next start.
     END_PRINT's `karman_end_cooldown_wipe` overwrites it with the gate actually loaded last (more accurate
     on multi-material prints). Added 2026-10-15 (maintainer).
   - If the variable is missing (fresh install only), there is no hot wipe; the action just logs a
     message. A **cancelled** print never runs END_PRINT (Klippain's CANCEL_PRINT only does PARK +
     TURN_OFF_HEATERS), so the variable keeps the *previous* print's material and the next start may
     hot-wipe for the wrong material. Mostly harmless (it drips into the cup).
4. **Wipe temperatures: 230 / 200 / 180 °C by family** (see 3). Basis: typical HDT + average
   print-temp ranking (2026-10-15 session). 180 is exactly the contact guard's limit, so no
   guard cooldown is needed for ABS/ASA anyway. 230 is below PET-GF's 290 print temp and below
   a true PET's ~255 melt; if ooze survives on PET, raise this first.
5. **Where the heat-up happens: on the nozzle rest.**
   - `karman_hot_wipe_heat` calls `PARK E=0` before the wipe `M109`, so the ooze lands in the RTV
     cup and not on the PEI. Heating at the bed-soak's Z50 mid-bed position would drip on the
     plate before contact.
   - The first `clean` then wipes at the wipe temp.
6. **Cooling for contact.**
   - `karman_hot_wipe_cool`, right after the first `clean`, sets the target to 150 and **fan-cools
     to ≤ 152 °C, blocking**, while the head is still at the y_max brush/bucket (not over the
     bed). Chosen over passive cooling in the guard exit (maintainer, 2026-10-15), which would
     stall START_PRINT before QGL with the fan off.
   - The contact guard then has nothing to cool for `contact_auto_calibrate`, and its exit
     `M109 S150` returns at once.
   - No separate settle step before `contact_z_home`: the nozzle is at 150 °C already (hot-wipe
     cool + the guard exit's `M109 S150`), and that touch's own guard covers the rest.
7. **Order relative to the cold-start runbook:** this runbook goes first. Step 9 updates the
   cold-start runbook so it keeps these actions.

## Steps

### 1. Read before editing (model)

Read these, in full or at the stated lines:
- `overrides.cfg`: the `PARK` override (~line 327), `_KARMAN_PARK_MOVE` (~273) and the
  `_USER_VARIABLES` override that holds both action lists (~548).
- `mmu/addons/blobifier.cfg`: `BLOBIFIER_CLEAN` (~line 670).

Confirm:
- `BLOBIFIER_CLEAN` only lifts Z when it is below `clearance_z` (2 mm);
- it slides to X53, wipes X53↔X88, and exits to X33 (the 15<x<40 lane) at y_max.

### 2. START_PRINT actions (model) — add to `overrides.cfg`

Replace the `variable_startprint_actions:` line (currently ~548) with the line below. **If the
cold-start runbook has already been executed**, merge instead: keep its `karman_*` entries and
insert this runbook's two new ones in the same relative positions.

```
variable_startprint_actions: "bed_soak", "extruder_preheating", "chamber_soak", "karman_hot_wipe_heat", "clean", "karman_hot_wipe_cool", "contact_auto_calibrate", "tilt_calib", "bedmesh", "contact_z_home", "extruder_heating", "nozzle_expansion", "clean", "primeline"
```

Add these macros near the other START_PRINT customisations:

```
# --- PET ooze hot wipe (docs/runbooks/nozzle-ooze-pet-hot-wipe.md) ---------------------------------
# After a PET/PC/PA/ABS/ASA print the cooled ooze is too stiff to brush off at 150 C. Heat (per material) ON THE
# REST (ooze drops into the RTV cup, not onto the PEI), then the first `clean` wipes it hot.
[gcode_macro _START_PRINT_ACTION_KARMAN_HOT_WIPE_HEAT]
gcode:
    {% set last = printer.save_variables.variables.karman_last_nozzle_material|default("")|string|upper %}
    # Wipe temp by material family of the PREVIOUS print (checked in this order, so PC-ABS -> PC):
    #   PET / PETG / PET-GF / PCTG -> 230    PC / PA* -> 200    ABS / ASA -> 180    else none
    {% set wipe_temp = 0 %}
    {% if "PET" in last or "PCTG" in last %}
        {% set wipe_temp = 230 %}
    {% elif "PC" in last or "PA" in last %}
        {% set wipe_temp = 200 %}
    {% elif "ABS" in last or "ASA" in last %}
        {% set wipe_temp = 180 %}
    {% endif %}
    {% if wipe_temp > 0 %}
        RESPOND MSG="KARMAN: last nozzle material {last} - hot wipe at {wipe_temp} C"
        PARK E=0
        M109 S{wipe_temp}
    {% else %}
        RESPOND MSG="KARMAN: last nozzle material '{last}' - no hot wipe"
    {% endif %}
    # Record THIS print's material for the next start (Jinja rendered `last` above before this runs, so
    # the hot wipe used the previous value). Covers a print that is cancelled and never reaches
    # END_PRINT; END_PRINT's karman_end_cooldown_wipe overwrites it with what was actually loaded last.
    {% set new_mat = printer["gcode_macro START_PRINT"].material|default("")|string %}
    {% if new_mat|trim != "" and new_mat|upper != "XXX" %}
        SAVE_VARIABLE VARIABLE=karman_last_nozzle_material VALUE='"{new_mat}"'
    {% endif %}

# Back to safe temp, fan-cooled while still at the y_max brush/bucket station after `clean` (not
# over the bed). The wait is deliberate: Klippain's contact guard exit does a blocking
# `M109 S<target saved at entry>` with the fan off, so a target of 150 with a ~180 C nozzle would
# stall START_PRINT on a slow passive cool before QGL. Cooling here leaves the guard nothing to do.
# Only runs after a hot wipe (target > safe); otherwise a no-op.
[gcode_macro _START_PRINT_ACTION_KARMAN_HOT_WIPE_COOL]
gcode:
    {% set safe = printer["gcode_macro _USER_VARIABLES"].safe_extruder_temp|float %}
    {% if printer.extruder.target > safe %}
        M104 S{safe}
        M106 S255
        TEMPERATURE_WAIT SENSOR=extruder MAXIMUM={safe + 2}
        M106 S0
        RESPOND MSG="KARMAN: hot wipe done, nozzle cooled to {safe} C"
    {% endif %}

# Runs AFTER turn_off_heaters / turn_off_fans, so the nozzle is cooling with the part fan on. It
# records what is in the nozzle for the next START_PRINT, lets the nozzle fall to that material's
# wipe temperature (same table as _START_PRINT_ACTION_KARMAN_HOT_WIPE_HEAT - keep in sync), wipes
# there with BLOBIFIER_CLEAN at the CURRENT Z (gantry brush - never CLEAN_NOZZLE here: it drops to
# Z1/Z5 with parts on the bed), returns to the rest, and keeps cooling. Wiping at the soft-but-not-
# draining temperature, not at print temp, leaves less time for new ooze to form after the wipe.
# No retract on purpose - see the runbook's out-of-scope list. Materials with no wipe temp are
# recorded and fan-cooled but not wiped.
[gcode_macro _END_PRINT_ACTION_KARMAN_END_COOLDOWN_WIPE]
gcode:
    {% set mmu = printer.mmu %}
    {% if mmu.filament == "Loaded" and mmu.gate|int >= 0 %}
        {% set material = mmu.gate_material[mmu.gate|int]|string %}
    {% else %}
        {% set material = printer["gcode_macro START_PRINT"].material|string %}
    {% endif %}
    {% set tok = ((material|upper).replace("-", " ").split() or [""])[0] %}
    {% set wipe_temp = 0 %}
    {% if tok.startswith("PET") or tok == "PCTG" %}
        {% set wipe_temp = 230 %}
    {% elif tok.startswith("PC") or tok.startswith("PA") %}
        {% set wipe_temp = 200 %}
    {% elif tok == "ABS" or tok == "ASA" %}
        {% set wipe_temp = 180 %}
    {% endif %}
    {% set temp = printer.extruder.temperature|float %}
    SAVE_VARIABLE VARIABLE=karman_last_nozzle_material VALUE='"{material}"'
    M106 S255
    {% if wipe_temp > 0 and temp >= wipe_temp - 30 %}
        {% if temp > wipe_temp %}
            RESPOND MSG="KARMAN: cooling to {wipe_temp} C for the end-of-print wipe ({material})"
            TEMPERATURE_WAIT SENSOR=extruder MAXIMUM={wipe_temp}
        {% endif %}
        BLOBIFIER_CLEAN
        PARK E=0
        RESPOND MSG="KARMAN: end-of-print wipe done at {wipe_temp} C ({material})"
    {% else %}
        RESPOND MSG="KARMAN: no end-of-print wipe for '{material}' (nozzle {temp|round(0)} C)"
    {% endif %}
    UPDATE_DELAYED_GCODE ID=_KARMAN_END_COOLDOWN_FAN_LOOP DURATION=5

[delayed_gcode _KARMAN_END_COOLDOWN_FAN_LOOP]
gcode:
    {% if printer.extruder.target > 0 %}
        # Heater is back on (a new print is starting, or heaters were left at safe temp): stop the
        # loop and turn the fan off. Do NOT key on print_stats.state: it still reads "printing"
        # while END_PRINT runs from inside the gcode file, and nothing in START_PRINT clears the
        # part fan, so leaving it at 100% would blow through the next print's bed soak.
        M107
    {% elif printer.extruder.temperature < 120 %}
        M107
    {% else %}
        UPDATE_DELAYED_GCODE ID=_KARMAN_END_COOLDOWN_FAN_LOOP DURATION=5
    {% endif %}
```

`printer.save_variables` needs Klipper's `[save_variables]` section. It already exists here: Happy
Hare and `thermal_expansion.cfg` use it. If `FIRMWARE_RESTART` complains, stop and report it; don't
add a second `[save_variables]`.

### 4. Validate offline (model)

Render each new macro with `tools/render_macro.py`. Put the JSON state files in the session
scratchpad, not the repo:

```
uv run tools/render_macro.py overrides.cfg <MACRO> --json <state>.json
```

| Macro | State | Expected |
|---|---|---|
| `_START_PRINT_ACTION_KARMAN_HOT_WIPE_HEAT` | `save_variables.variables.karman_last_nozzle_material: "PET"` | RESPOND, `PARK E=0`, `M109 S230` |
| same | `"PETG-CF"` | same as above |
| same | `"ABS"` / `"ASA"` | RESPOND, `PARK E=0`, `M109 S180` |
| same | `"PC-ABS"` / `"PA12-CF"` | `M109 S200` |
| same | `"PCTG"` / `"PET-GF"` | `M109 S230` |
| same | `"PLA"` / `"TPU"` | RESPOND "no hot wipe" only |
| same | saved `"PET"`, START_PRINT `material: "ABS"` | hot wipe at 230 **and** `SAVE_VARIABLE … VALUE='"ABS"'` |
| same | START_PRINT `material: "XXX"` or `""` | no SAVE_VARIABLE |
| same | variable absent | RESPOND "no hot wipe" only |
| `…KARMAN_HOT_WIPE_COOL` | extruder target 230 | `M104 S150.0`, `M106 S255`, `TEMPERATURE_WAIT … MAXIMUM=152.0`, `M106 S0`, RESPOND |
| same | target 150 | nothing |
| `_END_PRINT_ACTION_KARMAN_END_COOLDOWN_WIPE` | mmu `Unloaded`, START_PRINT `material: "PET-GF"`, extruder temp 285 | SAVE_VARIABLE `"PET-GF"`, `M106 S255`, `TEMPERATURE_WAIT … MAXIMUM=230`, `BLOBIFIER_CLEAN`, `PARK E=0`, loop armed |
| same | temp 229 (PET) | no wait, wipe |
| same | temp 100 (PET) | SAVE_VARIABLE, fan, "no end-of-print wipe", loop armed |
| same | PLA at 210 | no wipe (no wipe temp) |
| same | mmu `Loaded`, `gate: 1`, `gate_material: ["PET","ABS"]`, temp 245 | `VALUE='"ABS"'`, wait to 180, wipe |
| same | PA12-CF at 215 | wait to 200, wipe |
| `_KARMAN_END_COOLDOWN_FAN_LOOP` (`[delayed_gcode]`) | target 0, temp 200 / 100; target 150 | reschedule / `M107` / `M107` |

The state JSONs need:
- `gcode_macro _USER_VARIABLES.safe_extruder_temp: 150`;
- `extruder.temperature` / `extruder.target`;
- `print_stats.state`;
- the `mmu` fields above;
- `"gcode_macro START_PRINT": {"material": …}`;
- `save_variables.variables`.

(`wipe_temp` is a local `{% set %}` on purpose: `render_macro.py` does not inject a macro's own
`variable_*` values, so a `variable_wipe_temp` would fail to render offline.)

Then the motion check:

```
uv run tools/visualize_toolchange.py
```

It must cover the new motion, so **extend the tool**:
- the `start_print` scenario must simulate `karman_hot_wipe_heat`'s `PARK E=0` (via
  `_KARMAN_PARK_MOVE`) and treat the other `karman_*` actions as no-motion;
- `complete_park` (or a new `end_print_wipe` scenario) must append `BLOBIFIER_CLEAN` + `PARK E=0`
  after the end-of-print park.

Expect **every scenario clean**. If a zone is violated, stop and report; don't loosen the zone
checks.

### 5. Apply (USER, printer idle — never mid-print)

Ask the maintainer to run this and paste any error:

```
FIRMWARE_RESTART
```

These are `.cfg` changes only, so no `systemctl restart klipper` is needed.

### 6. PET print, end side (USER + model)

Maintainer prints the small PET model and **watches the end**. The model can tail the log live:

```
ssh ernst@192.168.1.240 'tail -Fn0 ~/printer_data/logs/klippy.log'
```

Expected:
- park on the rest, the part fan on, `KARMAN: cooling to 230 C for the end-of-print wipe (PET)` while
  the nozzle falls to 230 °C;
- then a short wipe on the brush (X53↔X88) at the **same Z** → back on the rest;
- `KARMAN: end-of-print wipe done at 230 C (PET)`;
- the part fan runs, then stops on its own once the nozzle is below 120 °C.

Confirm the saved material:

```
curl -s "http://192.168.1.240:7125/printer/objects/query?save_variables" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['status']['save_variables']['variables'].get('karman_last_nozzle_material'))"
```

The expected output is `PET`.

**Ask the maintainer:** how much ooze is on the nozzle after cooldown, compared with before (less /
same)?

### 7. Next start after PET (USER)

Let the printer cool fully, so the ooze has hardened, then start the next PET print. Expected
console sequence:
1. `KARMAN: last nozzle material PET - hot wipe at 230 C`;
2. a park on the rest and a heat to the wipe temp (230 for PET);
3. `clean`;
4. a fan-assisted cool to ≤ 152 at the brush/bucket, then `KARMAN: hot wipe done, nozzle cooled to 150.0 C`;
5. the calibrate touch (no guard cooling, no exit wait);
6. QGL and the mesh;
7. `contact_z_home`.

**Ask the maintainer** to look at the nozzle after the first `clean` and before the touch. That is
the objective: **no ooze attached.** Also ask them to check that there's no PET smear at the
bed-centre contact point and that the first layer is good.

### 8. Next start after ABS (USER)

Print the ABS model, then start another print. Expected:
`KARMAN: last nozzle material ABS - hot wipe at 180 C`, a park on the rest and a short heat from
150 to 180. Ask the maintainer whether the nozzle is clean after the first `clean`. If a PLA/TPU
print is on hand, its next start should log "no hot wipe".

### 9. Amend the cold-start runbook (model)

In `docs/runbooks/start-print-cold-start-speedup.md`:
- **Step 3a:** replace the action list with
  ```
  variable_startprint_actions: "karman_nozzle_to_safe", "bed_soak", "karman_nozzle_warm", "chamber_soak", "karman_hot_wipe_heat", "clean", "karman_hot_wipe_cool", "contact_auto_calibrate", "tilt_calib", "bedmesh", "contact_z_home", "extruder_heating", "nozzle_expansion", "clean", "primeline"
  ```
- **Step 3b:** add only `…NOZZLE_TO_SAFE` and `…NOZZLE_WARM`. There is no `karman_contact_z_temp`
  (dropped 2026-10-15; see the status log), so remove it from that runbook's macros too.
- Add a status-log line saying it was amended for the ooze runbook.

### 10. Document (model)

- **`docs/start_print_walkthrough.md`:** add the new start actions in Phase 2 (hot-wipe heat/cool
  around the first `clean`, no extra settle step before step 24). Also describe END_PRINT's new wipe +
  cooldown fan, either in Phase 3 or as a short END_PRINT note.
- **`docs/decisions.md`:** a new entry at the **top**:
  `## 2026-MM-DD — PET ooze: hot wipe at START_PRINT (230/200/180 °C on the rest, by material), end wipe + cooldown fan, no END_PRINT retract`.
  It should cover:
  - why 150 fails on PET;
  - why the heat-up happens on the rest;
  - why the trigger is saved at END_PRINT (the multi-tool unload hides it at start);
  - why `CLEAN_NOZZLE` isn't used at the end (Z drops with parts on the bed);
  - why there's no retract (cut margin, `retract_length` 60);
  - the 150 °C contact-Z constraint.
- **`TODO.md`:**
  - tick the task;
  - close the *"END_PRINT `retract_filament` is now a complete no-op"* task, with a pointer to the
    decisions entry ("decided: no END_PRINT retract — cut-margin coupling");
  - remove the task from *▶ Next up*.

## Verification

- [ ] `FIRMWARE_RESTART` is clean (Step 5).
- [ ] Every offline render matches the table in Step 4; `visualize_toolchange.py` covers the new
      moves and every scenario is clean.
- [ ] After a PET print: the end wipe ran at the same Z and ended on the rest; the cooldown fan
      stopped by itself; `karman_last_nozzle_material` = `PET` (Step 6).
- [ ] **Next PET start: the nozzle has no attached ooze before the first contact touch**
      (maintainer's eyes, Step 7). This is the objective.
- [ ] The first layer is as good as before (the Z touch runs at 150 °C via the guard).
- [ ] After an ABS print, the next start hot-wipes at 180 °C and the nozzle is clean (Step 8).
- [ ] The cold-start runbook is amended (Step 9); the walkthrough, decisions.md and TODO.md are
      updated (Step 10).

## Commit guidance

The maintainer runs commits. Git runs **only over SSH**, never on the mount. Propose:

1. `feat: hot-wipe the nozzle by material at start and wipe + fan-cool it at print end`
   — `overrides.cfg`, plus `tools/visualize_toolchange.py` (scenario coverage).
2. `docs: record the pet ooze hot-wipe decision` — `docs/start_print_walkthrough.md`,
   `docs/decisions.md`, `TODO.md`, `docs/runbooks/start-print-cold-start-speedup.md`, and this
   runbook (moved to `docs/runbooks/done/`).

```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git status -s'
```

## Status log

- **2026-10-10** — Runbook written (architecture session). Design pre-resolved with the
  maintainer; nothing executed yet.
- **2026-10-15** — Objective session. Step 1 confirmed: `BLOBIFIER_CLEAN` has `brush_top: None`, so
  it only lifts Z to `clearance_z` (2) if below it, slides to X53, wipes X53↔X88 and exits to X33
  (inside the 15<x<40 lane). Steps 2–3: added the five macros, the delayed_gcode and both action
  lists to `overrides.cfg` (cold-start runbook not yet executed, so no merge needed). Step 4: all 14
  offline renders matched the table; `visualize_toolchange.py` extended (`start_print` simulates
  `PARK E=0` for the hot-wipe heat, `complete_park` appends `BLOBIFIER_CLEAN` + `PARK E=0`) and all
  five scenarios are clean. **Not yet applied to the printer** — Steps 5–10 pending.
- **2026-10-15 (later)** — Maintainer amended the START trigger: per-material wipe temp
  (PET/PCTG 230, PC/PA 200, ABS/ASA 180, else none) instead of PET-only at 230. Implemented in
  `_START_PRINT_ACTION_KARMAN_HOT_WIPE_HEAT`; 11 offline renders pass (PET, PET-GF, PETG, PCTG,
  PC-ABS, PA12-CF, ABS, asa, PLA, TPU, absent). Still **not applied** to the printer.
  Docs (Step 10) must describe the per-material table, not "PET only". The objective's title and
  END_PRINT side are unchanged.
- **2026-10-15 (review)** — Opus review agent found: (1) cooldown-fan loop could leave the part fan
  at 100% into the next print because `print_stats.state` stays `printing` while END_PRINT runs;
  **fixed** — loop now stops on `extruder.target > 0` (new print or heater back on) or nozzle <120.
  (2) contact-guard exit is a blocking M109 — **documented**, no code change pending maintainer
  call. (3) cancelled-print wording — **fixed**. Also fixed: `"PA"` substring false positives
  (now first-word match), stale 230-only wording, X30→X33. Noted, not changed: END_PRINT's plain
  `PARK` already does a 2 mm retract (PARK default `E=2`), contradicting "no retract of any size" —
  add a line to decisions.md in Step 10. Selftest 29/29, visualizer 5/5 clean.
- **2026-10-15 (cooling)** — Maintainer chose to fan-cool in `karman_hot_wipe_cool` (blocking, to
  ≤152 °C at the y_max station after `clean`) instead of leaving the guard exit's blocking passive
  `M109 S150` to do it. Implemented; offline render matches; selftest 29/29. Not yet applied.
  Open check at Step 7: time the cool (how long START_PRINT waits there).
- **2026-10-15 (simplify)** — Maintainer removed `karman_contact_z_temp` (redundant: the guard exit's
  `M109 S150` already leaves the nozzle at 150 and `contact_z_home` has its own guard; fewer
  deviations from Klippain). Removed from `overrides.cfg`, the action list, this runbook and the
  cold-start runbook. Remaining START actions: `karman_hot_wipe_heat`, `karman_hot_wipe_cool`.
- **2026-10-15 (start-side save)** — `karman_hot_wipe_heat` now also saves the new print's material
  (after deciding the wipe), so cancelled prints keep a correct value. Rendered: saves ABS after a
  PET wipe; no save for `XXX`/empty. Known edge: a print cancelled before its filament loads records a
  material that never reached the nozzle.
- **2026-10-15 (first hardware test)** — START side ran clean on a PET-GF print (MMU disabled for
  the run): hot wipe heat 150→230 in ~22 s, wipe, fan-cool 230→150 in ~55 s, then the contact
  touch at 150 °C with no guard cooling. End side ran as designed, fan stopped itself at <120 °C
  (~2.3 min after print end). **Result: ooze still on the nozzle, maybe slightly less.** The
  maintainer's diagnosis: the end wipe at ~285 °C is too hot, and the nozzle oozes again after it.
  Redesigned the end side (decision 2): cool to the wipe temp first, wipe, keep cooling
  (`karman_end_cooldown_wipe`, replaces `karman_end_wipe` + `karman_end_cooldown_fan`). Rendered
  offline (7 states), selftest 29/29, visualizer 5/5 clean. **Not yet applied** — needs
  `FIRMWARE_RESTART`. Still to judge after the next run: is the nozzle clean before the start
  touch, and does a wipe at 230 °C reduce the post-wipe ooze.
- **2026-10-16 (second hardware test + wrap-up)** — Real ABS print, MMU disabled. START hot-wiped at
  230 for the previous PET-GF (about 70 s from the clean start to "cooled to 150.0 C"), contact,
  mesh and Z touch fine. END: cooled to 180, wiped, "end-of-print wipe done at 180 C (ABS)" 63 s
  after the print ended; saved material `ABS`; fan stopped itself (nozzle 53, target 0, fan 0).
  Docs written: walkthrough sections, decisions entry. **Open:** ooze verdict; ABS start hot wipe
  at 180 and a PET start not yet seen; the gate-map path, cancelled prints and PA/PC wipes are
  untried; whether to wipe PLA/TPU at the end is unanswered. Not archived for that reason. Nothing
  committed.
