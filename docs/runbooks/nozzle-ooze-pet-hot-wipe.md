# Runbook — PET ooze survives the START_PRINT nozzle wipe

**Objective:** after a PET-family print, the next print's nozzle is **clean before the first
Beacon contact touch**. Two halves:
(1) **END_PRINT** wipes the still-hot nozzle and runs the part fan while it cools on the rest, so
less ooze forms;
(2) **START_PRINT** after a PET print heats to **230 °C on the nozzle rest**, wipes, then cools for
contact. At 150 °C the attached PET ooze is too stiff to brush off.
**Status:** 🟡 not started
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
  - On exit it **restores the target saved at entry**. So the target must already be back at 150
    before the first contact, or the guard re-heats the nozzle to 230 for QGL and the mesh.

## Scope

1. `overrides.cfg`:
   - three new START_PRINT actions;
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
2. **End of print: hot wipe + part-fan cooldown, no retract.**
   - The new action `karman_end_wipe` sits after `nozzle_expansion` and before
     `turn_off_heaters`, so the nozzle is still at print temperature.
   - It records the nozzle material, then, if the nozzle is ≥ 200 °C, runs `BLOBIFIER_CLEAN`
     followed by `PARK E=0` (back onto the rest).
   - This runs after **every** print, not just PET. It is cheap (~10 s) and helps any material.
   - The new action `karman_end_cooldown_fan` sits after `turn_off_fans`. It turns the part fan
     to 100 % and starts a 5 s `[delayed_gcode]` loop that turns the fan off once the nozzle is
     **< 120 °C**.
   - The loop stops **without touching the fan** if a new print has started
     (`print_stats.state == "printing"`).
3. **Start of print: hot wipe only after a PET-family print.**
   - The trigger is the saved variable `karman_last_nozzle_material`, upper-cased, **containing
     `PET`**. That covers PET, PETG, PET-GF and PETG-CF.
   - If the variable is missing, for example after a cancelled print that never ran END_PRINT,
     there is no hot wipe; the action just logs a message.
4. **Wipe temperature: fixed 230 °C.** That is soft enough for PET/PETG/PET-GF skins and well
   below PET-GF's 290 print temperature, so less fresh ooze at the brush.
5. **Where the heat-up happens: on the nozzle rest.**
   - `karman_hot_wipe_heat` calls `PARK E=0` before `M109 S230`, so the ooze lands in the RTV
     cup and not on the PEI. Heating at the bed-soak's Z50 mid-bed position would drip on the
     plate before contact.
   - The first `clean` then wipes at 230.
6. **Cooling for contact.**
   - `karman_hot_wipe_cool`, right after the first `clean`, sets the target back to 150 with no
     wait.
   - The contact guard then fan-cools to ≤ 180 for `contact_auto_calibrate`. That touch only
     calibrates Beacon's proximity model, so 180 is acceptable there.
   - `karman_contact_z_temp`, placed immediately before `contact_z_home`, settles the nozzle to
     **150 ± 2 °C**, because that touch defines Z.
7. **Order relative to the cold-start runbook:** this runbook goes first. Step 9 updates the
   cold-start runbook so it keeps these actions and does not redefine `karman_contact_z_temp`.

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
variable_startprint_actions: "bed_soak", "extruder_preheating", "chamber_soak", "karman_hot_wipe_heat", "clean", "karman_hot_wipe_cool", "contact_auto_calibrate", "tilt_calib", "bedmesh", "karman_contact_z_temp", "contact_z_home", "extruder_heating", "nozzle_expansion", "clean", "primeline"
```

Add these macros near the other START_PRINT customisations:

```
# --- PET ooze hot wipe (docs/runbooks/nozzle-ooze-pet-hot-wipe.md) ---------------------------------
# After a PET-family print the cooled ooze is too stiff to brush off at 150 C. Heat to 230 ON THE
# REST (ooze drops into the RTV cup, not onto the PEI), then the first `clean` wipes it hot.
[gcode_macro _START_PRINT_ACTION_KARMAN_HOT_WIPE_HEAT]
gcode:
    {% set wipe_temp = 230 %}    # soft enough for PET/PETG/PET-GF skins, well below PET-GF's 290
    {% set last = printer.save_variables.variables.karman_last_nozzle_material|default("")|string|upper %}
    {% if "PET" in last %}
        RESPOND MSG="KARMAN: last nozzle material {last} - hot wipe at {wipe_temp} C"
        PARK E=0
        M109 S{wipe_temp}
    {% else %}
        RESPOND MSG="KARMAN: last nozzle material '{last}' - no hot wipe"
    {% endif %}

# Target back to safe temp, NO wait. Klippain's contact guard then fan-cools to <=180 for the
# calibrate touch, and restores THIS target (150) afterwards instead of the 230 wipe temp.
[gcode_macro _START_PRINT_ACTION_KARMAN_HOT_WIPE_COOL]
gcode:
    {% set safe = printer["gcode_macro _USER_VARIABLES"].safe_extruder_temp|float %}
    {% if printer.extruder.target > safe %}
        M104 S{safe}
        RESPOND MSG="KARMAN: hot wipe done, nozzle target -> {safe} C"
    {% endif %}

# contact_z_home defines Z, and thermal_expansion.cfg computes the hot-nozzle offset from 150 C.
# Settle to safe +/- 2 C so that assumption holds (part fan only while cooling).
[gcode_macro _START_PRINT_ACTION_KARMAN_CONTACT_Z_TEMP]
gcode:
    {% set safe = printer["gcode_macro _USER_VARIABLES"].safe_extruder_temp|float %}
    M104 S{safe}
    {% if printer.extruder.temperature > safe + 2 %}
        M106 S255
        TEMPERATURE_WAIT SENSOR=extruder MAXIMUM={safe + 2}
        M106 S0
    {% elif printer.extruder.temperature < safe - 2 %}
        M109 S{safe}
    {% endif %}
    RESPOND MSG="KARMAN: contact Z temperature settled (was {printer.extruder.temperature|round(1)} C)"
```

Note: Jinja renders the whole macro before any line runs, so `RESPOND` messages report the
temperature **at macro entry**. The wording ("was") says so. Don't "fix" it.

### 3. END_PRINT actions (model) — add to `overrides.cfg`

Replace the `variable_endprint_actions:` line (currently ~549) with:

```
variable_endprint_actions: "retract_filament", "nozzle_expansion", "karman_end_wipe", "turn_off_heaters", "turn_off_fans", "karman_end_cooldown_fan", "turn_off_motors", "reset_limits"
```

Add:

```
# Runs while the nozzle is still at print temp, AFTER END_PRINT's own PARK (toolhead on the rest).
# Records what is in the nozzle for the next START_PRINT, then wipes at the CURRENT Z with
# BLOBIFIER_CLEAN (gantry brush - never CLEAN_NOZZLE here: it drops to Z1/Z5 with parts on the bed)
# and returns to the rest. No retract on purpose - see the runbook's out-of-scope list.
[gcode_macro _END_PRINT_ACTION_KARMAN_END_WIPE]
gcode:
    {% set mmu = printer.mmu %}
    {% if mmu.filament == "Loaded" and mmu.gate|int >= 0 %}
        {% set material = mmu.gate_material[mmu.gate|int]|string %}
    {% else %}
        {% set material = printer["gcode_macro START_PRINT"].material|string %}
    {% endif %}
    SAVE_VARIABLE VARIABLE=karman_last_nozzle_material VALUE='"{material}"'
    {% if printer.extruder.temperature >= 200 %}
        BLOBIFIER_CLEAN
        PARK E=0
        RESPOND MSG="KARMAN: end-of-print hot wipe done ({material})"
    {% else %}
        RESPOND MSG="KARMAN: nozzle already below 200 C - end wipe skipped ({material})"
    {% endif %}

# Part fan on while the nozzle cools on the rest: a shorter hot window means less ooze.
[gcode_macro _END_PRINT_ACTION_KARMAN_END_COOLDOWN_FAN]
gcode:
    M106 S255
    UPDATE_DELAYED_GCODE ID=_KARMAN_END_COOLDOWN_FAN_LOOP DURATION=5

[delayed_gcode _KARMAN_END_COOLDOWN_FAN_LOOP]
gcode:
    {% if printer.print_stats.state == "printing" %}
        # A new print owns the part fan now - stop the loop without touching it.
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
| same | `"ABS"` | RESPOND "no hot wipe" only |
| same | variable absent | RESPOND "no hot wipe" only |
| `…KARMAN_HOT_WIPE_COOL` | extruder target 230 | `M104 S150.0`, RESPOND |
| same | target 150 | nothing |
| `…KARMAN_CONTACT_Z_TEMP` | temp 175 / 150 / 140 | fan + `TEMPERATURE_WAIT … MAXIMUM=152.0` / `M104` only / `M109 S150.0` |
| `_END_PRINT_ACTION_KARMAN_END_WIPE` | mmu `filament: "Loaded"`, `gate: 0`, `gate_material: ["PET","PET"]`, extruder temp 285 | `SAVE_VARIABLE … VALUE='"PET"'`, `BLOBIFIER_CLEAN`, `PARK E=0` |
| same | extruder temp 150 | SAVE_VARIABLE + "skipped" RESPOND |
| same | mmu `filament: "Unloaded"`, START_PRINT `material: "ABS"` | `VALUE='"ABS"'` |
| `_KARMAN_END_COOLDOWN_FAN_LOOP` (`[delayed_gcode]`) | print state `complete`, temp 200 / 100; state `printing` | reschedule / `M107` / nothing |

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
- park on the rest → a short wipe on the brush (X53↔X88) at the **same Z** → back on the rest;
- `KARMAN: end-of-print hot wipe done (PET)`;
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
2. a park on the rest and a heat to 230;
3. `clean`;
4. `KARMAN: hot wipe done, nozzle target -> 150.0 C`;
5. a fan-assisted cool to ≤ 180, then the calibrate touch;
6. QGL and the mesh;
7. `KARMAN: contact Z temperature settled (was ~150 C)`;
8. `contact_z_home`.

**Ask the maintainer** to look at the nozzle after the first `clean` and before the touch. That is
the objective: **no ooze attached.** Also ask them to check that there's no PET smear at the
bed-centre contact point and that the first layer is good.

### 8. Next start after ABS (USER)

Print the ABS model, then start another print. Expected:
`KARMAN: last nozzle material 'ABS' - no hot wipe`. The start is otherwise as before, apart from
the contact-Z settle line.

### 9. Amend the cold-start runbook (model)

In `docs/runbooks/start-print-cold-start-speedup.md`:
- **Step 3a:** replace the action list with
  ```
  variable_startprint_actions: "karman_nozzle_to_safe", "bed_soak", "karman_nozzle_warm", "chamber_soak", "karman_hot_wipe_heat", "clean", "karman_hot_wipe_cool", "contact_auto_calibrate", "tilt_calib", "bedmesh", "karman_contact_z_temp", "contact_z_home", "extruder_heating", "nozzle_expansion", "clean", "primeline"
  ```
- **Step 3b:** `_START_PRINT_ACTION_KARMAN_CONTACT_Z_TEMP` **already exists** (added by this
  runbook). Do not add it a second time; add only `…NOZZLE_TO_SAFE` and `…NOZZLE_WARM`.
- Add a status-log line saying it was amended for the ooze runbook.

### 10. Document (model)

- **`docs/start_print_walkthrough.md`:** add the new start actions in Phase 2 (hot-wipe heat/cool
  around the first `clean`, contact-Z settle before step 24). Also describe END_PRINT's new wipe +
  cooldown fan, either in Phase 3 or as a short END_PRINT note.
- **`docs/decisions.md`:** a new entry at the **top**:
  `## 2026-MM-DD — PET ooze: hot wipe at START_PRINT (230 °C on the rest), end wipe + cooldown fan, no END_PRINT retract`.
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
- [ ] The contact Z settle line was logged at ~150 °C; the first layer is as good as before.
- [ ] After an ABS print, the next start skips the hot wipe (Step 8).
- [ ] The cold-start runbook is amended (Step 9); the walkthrough, decisions.md and TODO.md are
      updated (Step 10).

## Commit guidance

The maintainer runs commits. Git runs **only over SSH**, never on the mount. Propose:

1. `feat: hot-wipe the nozzle after pet prints and wipe + fan-cool it at print end`
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
