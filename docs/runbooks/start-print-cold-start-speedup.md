# Runbook — cut cold-start time in START_PRINT

**Objective:** START_PRINT finishes measurably faster on both a **cold multi-tool start** and a
**warm repeat start**, with **first-layer quality and contact Z unchanged**. Three changes, all
in repo-root files: shorter bed soak, hotend dropped to the contact-safe temperature right after
the start-of-print MMU unload, and a cooldown that no longer blocks on a fan-less wait to 150 °C.
**Status:** 🟡 not started
**Created:** 2026-10-09
**⚠️ Run order:** execute **after** `docs/runbooks/nozzle-ooze-pet-hot-wipe.md` (maintainer, 2026-10-10).
That runbook adds `karman_hot_wipe_heat` / `karman_hot_wipe_cool` around the first `clean`; its
Step 9 amends Steps 3a/3b here. (`karman_contact_z_temp` was dropped on 2026-10-15; this runbook
no longer adds it either.)
If that amendment has not happened yet, stop and do it first.
**Prerequisites:** printer idle (not mid-print) for every `FIRMWARE_RESTART`; both MMU gates
loaded; one 2-colour ABS model and one single-colour model ready to slice (any small parts with
a decent first-layer area — the maintainer picks).

## Background — what the time goes on today (traced 2026-10-09)

Read `docs/start_print_walkthrough.md` for the full step-by-step trace (its "Approximate
timeline" table is the cold-start baseline: **~25–30 min**). The problem in short, for a
multi-tool print (`TOOLS_USED=0,1`):

1. **Before any start action**, Klippain's `_KLIPPAIN_MMU_INIT`
   (`macros/hardware_functions/mmu.cfg:42`) runs `MMU_UNLOAD`, then `MMU_CHECK_GATE`. This
   happens on **every** multi-tool print (the guard `printer.mmu.tool|string != TOOLS_USED`
   compares e.g. `"0"` to `"0,1"` and is always true). The unload heats the hotend to the gate
   temperature (~260 °C) and cuts — and the hotend **stays at that temperature** afterwards.
2. `bed_soak` parks at **Z50** mid-front (`macros/base/start_print.cfg:302`) and runs
   `HEATSOAK_BED` — bed to target, then `print_default_soak: 8` one-minute dwells. Meanwhile the
   hot nozzle oozes. (The soak is skipped entirely when the bed is already within 8 °C of target.)
3. `extruder_preheating` — because `probe_needs_contact_temp_guard` is True — runs
   **`M109 S150`**, a blocking wait that, after the hot unload, means waiting for the nozzle to
   *cool* from ~260 to 150 with no fan.

Measured on warm single-tool repeat starts 2026-10-09 (Moonraker console history): whole
START_PRINT **~2.5–3 min**, of which the fan-less cool-to-150 was **27–47 s**.

**Already in place that this runbook relies on:** Klippain's contact guard
(`_PROBE_ENTER_CONTACT_GUARD`, `macros/base/probing/virtual_z_probe.cfg:74-82`) already does a
**fan-assisted** cooldown before every contact touch, but only down to `probe_contact_max_temp`
(180 °C): if `target > 180` it does `M106 S255` + `M109 S180`; else if `actual > 183` it does
`M106 S255` + `TEMPERATURE_WAIT SENSOR=extruder MAXIMUM=180` + `M106 S0`.

## Scope

1. `variables.cfg`: `variable_print_default_soak` **8 → 3**.
2. `overrides.cfg`: three new START_PRINT custom actions and a rewritten
   `variable_startprint_actions` list (details under *Pre-resolved decisions*).
3. Measure before/after timings and confirm first layer + contact Z are unchanged.
4. Update `docs/start_print_walkthrough.md` (steps 17–18 + timeline) and add a
   `docs/decisions.md` entry.

## ⚠️ Out of scope — do not touch

Every item here is validated config with a recorded reason. Changing any of them is a different
objective.

- **The start-of-print `MMU_UNLOAD` / gate check.** Do not try to skip it. It lives in the
  Klippain framework (`macros/hardware_functions/mmu.cfg`, read-only — the `guard-framework` hook
  blocks edits), and even if Klippain skipped it, Happy Hare's `MMU_CHECK_GATE` force-ejects
  before checking any gate other than the loaded one (`~/Happy-Hare/extras/mmu/mmu.py` ~8960-8975).
  This runbook shortens what happens *after* it, not the unload itself.
- **Any Klippain framework file** (`macros/`, `config/`, `scripts/`, `moonraker/`). Custom
  actions go in `overrides.cfg` only — `START_PRINT` dispatches any `startprint_actions` entry to
  a `_START_PRINT_ACTION_<NAME>` macro if one exists (`start_print.cfg:211-212`).
- **`variable_safe_extruder_temp: 150` and `variable_probe_contact_max_temp: 180`**
  (`variables.cfg`). 150 is also the hard-coded reference temperature of the nozzle-expansion
  compensation (see next item).
- **`thermal_expansion.cfg`** and `nozzle_expansion_coefficient` (0.055). The expansion offset
  is computed as `(print_target − 150) × 0.055 / 100` mm — it **assumes the Z-defining contact
  (`contact_z_home`) happens at 150 °C**. Every 10 °C of error there is ~0.0055 mm of first-layer
  error. The contact guard exit's blocking `M109 S150` is what holds that (no extra settle
  action; maintainer decision 2026-10-15).
- **Both `clean` actions and both contact actions** (`contact_auto_calibrate`, `contact_z_home`)
  — each does a different job; see "Things easy to misread" in `docs/start_print_walkthrough.md`.
- **`chamber_soak` and `print_default_chamber_temp_tolerance: 2.0`** — `docs/decisions.md`
  2026-08-02 "Chamber soak stays; the tolerance was the bug".
- **`bucket_travel_safe_z: 20` and the `_CONDITIONAL_MOVE_TO_PURGE_BUCKET` override**,
  **`force_homing_before_brush: False`**, the **removed `purge` action** — all
  `docs/decisions.md` 2026-08-02.
- **`mmu_unload_on_end_print: False`** — `docs/decisions.md` 2026-08-02.
- **HH `default_extruder_temp` / gate-map temperatures** — the unload temperature is not this
  objective.
- **`bed_fans.cfg`** — independent, self-triggering state machine; START_PRINT does not drive it.
- **No new toolhead motion.** The new actions only set temperatures and the part fan. Do not add
  parks or moves. Keep-out zones (from `CLAUDE.md`, enforced by you — Klipper has no obstacle
  model): front-left **x<10 / y<17 at any Z** (cutter arm vs XY idler); back-left **x<~20 /
  y>~335 below z15** (Blobifier/depressor); the **y_max feature row** entered only via the clear
  lanes **15<x<40 or x>95**.

## Pre-resolved decisions (maintainer, 2026-10-09)

Each is a default the maintainer already chose — execute as written.

1. **Bed soak: 8 → 3 min** (`variable_print_default_soak: 3`). Not 0: a short soak still lets
   the frame and gantry settle on ABS. A slicer `SOAK=n` parameter still overrides per print.
   The `bed_soak` Z50 park stays (it only runs when a soak runs).
2. **Hotend right after the MMU unload: set target to `safe_extruder_temp` (150) with no wait.**
   New action `karman_nozzle_to_safe`, **first** in the list (start actions run *after*
   `_KLIPPAIN_MMU_INIT`). On a cold start this also pre-heats the nozzle to 150 in parallel with
   the bed instead of afterwards.
3. **Cooldown: fan-assisted, and the early touch only waits down to 180** ("both", maintainer's
   choice):
   - `extruder_preheating` is **removed** from the list and replaced by `karman_nozzle_warm`,
     which only ever waits for **heating** (nozzle more than 10 °C below 150 → `M109 S150`);
     it never waits for cooling.
   - The first touch (`contact_auto_calibrate`, which only calibrates Beacon's proximity model
     for QGL/mesh) is left to the existing contact guard: fan-assisted, down to ≤ 180 °C.
   - The guard exit's `M109 S150` after the calibrate touch brings the nozzle to 150 before QGL
     and the mesh (a passive cool from ≤180 with the fan off, so it may take a minute), and the
     Z-defining touch is therefore at 150 — the expansion compensation assumes that (see Out of
     scope). No separate settle action (dropped 2026-10-15, maintainer).
4. **Done =** before/after timings for a cold multi-tool start and a warm repeat start, plus a
   first layer and contact Z judged as good as before. No fixed target time.

## Steps

### 1. Capture baselines (model, read-only)

The warm-repeat baseline already exists (see Background). For any start, phase timestamps come
from Moonraker's console history — use this exact command (it prints the most recent starts):

```
curl -s "http://192.168.1.240:7125/server/gcode_store?count=3000" | python3 -c "
import json,sys,datetime
for g in json.load(sys.stdin)['result']['gcode_store']:
    m=g['message']
    if any(k in m for k in ['Material profile','Heating up bed','heatsoak','Soak','soak','Pre-heating','safe temperature','KARMAN','multi-filament','Probing','Start printing']):
        print(datetime.datetime.fromtimestamp(g['time']).strftime('%m-%d %H:%M:%S'), m[:110].replace(chr(10),' '))" | tail -60
```

START_PRINT duration = `Material profile handling is disabled…` → `Start printing !`.
The console history holds ~1000 lines, so run this **right after** each test start.

**Ask the maintainer** whether a recent *cold multi-tool* start is still in the history. If not,
the cold baseline is the walkthrough's timeline table (~25–30 min, bed heat-up 8–12 min). Bed
heat-up time is unaffected by this change, so the comparison that matters is everything else.

### 2. Edit `variables.cfg` (model)

Change the line `variable_print_default_soak: 8` to:

```
## 8 -> 3 (2026-10-09): shorter cold start; a short soak still settles the frame on ABS.
## Slicer SOAK=n overrides per print. docs/runbooks/start-print-cold-start-speedup.md
variable_print_default_soak: 3
```

### 3. Edit `overrides.cfg` (model)

3a. Replace the existing `variable_startprint_actions:` line (currently line ~548, inside the
`_USER_VARIABLES` override) with:

```
variable_startprint_actions: "karman_nozzle_to_safe", "bed_soak", "karman_nozzle_warm", "chamber_soak", "clean", "contact_auto_calibrate", "tilt_calib", "bedmesh", "contact_z_home", "extruder_heating", "nozzle_expansion", "clean", "primeline"
```

Diff against the old list: `karman_nozzle_to_safe` added first; `extruder_preheating` replaced
by `karman_nozzle_warm`. Everything
else is identical and in the same order. Update the comment block above the line if it lists the
actions.

3b. Add these three macros to `overrides.cfg`, near the other START_PRINT customisations (next
to the `_USER_VARIABLES` override is fine). Use them verbatim:

```
# --- START_PRINT cold-start speed-up (docs/runbooks/start-print-cold-start-speedup.md) ------------
# Runs FIRST, i.e. right after _KLIPPAIN_MMU_INIT. On multi-tool prints that just did MMU_UNLOAD at
# ~260 C; dropping the target now lets the nozzle cool (and stop oozing) during bed heat-up instead
# of blocking later. On a cold start it pre-heats to 150 in parallel with the bed. Never waits.
[gcode_macro _START_PRINT_ACTION_KARMAN_NOZZLE_TO_SAFE]
gcode:
    {% set safe = printer["gcode_macro _USER_VARIABLES"].safe_extruder_temp|float %}
    M104 S{safe}
    RESPOND MSG="KARMAN: nozzle target -> {safe} C (was {printer.extruder.temperature|round(1)} C), no wait"

# Replaces Klippain's extruder_preheating, whose M109 S150 also blocks while COOLING. This only
# waits when the nozzle is too cold to brush/probe. Cooling for the first contact is left to
# Klippain's contact guard (fan-assisted, down to probe_contact_max_temp).
[gcode_macro _START_PRINT_ACTION_KARMAN_NOZZLE_WARM]
gcode:
    {% set safe = printer["gcode_macro _USER_VARIABLES"].safe_extruder_temp|float %}
    {% if printer.extruder.target < safe %}
        M104 S{safe}
    {% endif %}
    {% if printer.extruder.temperature < safe - 10 %}
        M109 S{safe}
    {% endif %}
    RESPOND MSG="KARMAN: nozzle warm check done (entered at {printer.extruder.temperature|round(1)} C)"
```

Note: Jinja renders the whole macro before any line executes, so each `RESPOND` reports the
temperature **at macro entry** — the message wording says so ("was" / "entered at"). Do not "fix" this by
expecting the post-wait temperature.

### 4. Validate offline (model)

```
uv run tools/render_macro.py overrides.cfg _START_PRINT_ACTION_KARMAN_NOZZLE_WARM --json <state>.json
```

Write small JSON state files in the session scratchpad (not the repo) and render each new macro
for these cases, checking the emitted G-code:

| Macro | `extruder.temperature` / `target` | Expected output |
|---|---|---|
| `…NOZZLE_TO_SAFE` | 258 / 260 | `M104 S150.0`, RESPOND |
| `…NOZZLE_WARM` | 25 / 150 | `M109 S150.0` |
| `…NOZZLE_WARM` | 200 / 150 | no M104, no M109 (just RESPOND) |
| `…NOZZLE_WARM` | 25 / 0 | `M104 S150.0` **and** `M109 S150.0` |

Each state JSON needs `gcode_macro _USER_VARIABLES` → `safe_extruder_temp: 150` and an
`extruder` object with `temperature` and `target`.

Then run the motion check (the `check-toolchange` hook also runs it automatically after an
`overrides.cfg` edit):

```
uv run tools/visualize_toolchange.py
```

Expect every scenario **clean**. The `start_print` scenario simulates the action list; if it
errors or warns on the three unknown `karman_*` actions, teach it to treat them as no-motion
actions (they contain no G0/G1) — do **not** remove them from the list to make it pass.

### 5. Apply (USER, printer idle)

Edits on the mount are live immediately but only load on restart. **Not mid-print.** Ask the
maintainer to run:

```
FIRMWARE_RESTART
```

and paste any error. Expected: clean restart. (These are `.cfg` changes only — no
`systemctl restart klipper` needed.)

### 6. Warm repeat start test (USER)

Maintainer prints the single-colour model right after another print (bed still hot, nozzle
loaded). Then the model runs the Step 1 timing command. Expected:
- `No heatsoak needed` (soak skipped, as before).
- `KARMAN: nozzle target -> 150.0 C …` first, then `KARMAN: nozzle warm check done …` with no
  blocking wait.
- Total START_PRINT shorter than the 2.5–3 min baseline (the 27–47 s cooldown wait should be
  gone or replaced by a shorter fan-assisted one inside the contact guard).
- `Nozzle expansion offset: … applied` appears as before.

**Ask the maintainer** to judge the first layer against previous prints of the same kind.

### 7. Cold multi-tool start test (USER)

Maintainer starts the 2-colour ABS model from a **cold** printer (bed < ~95 °C). Watch live
instead of round-tripping pastes:

```
ssh ernst@192.168.1.240 'tail -Fn0 ~/printer_data/logs/klippy.log'
```

Then run the Step 1 timing command. Expected:
- `MMU_UNLOAD` + gate check as before, then `KARMAN: nozzle target -> 150.0 C (was ~260 C)`.
- Bed heat-up, then **3** soak minutes (not 8).
- No long wait at the warm check; the hotend is **not** oozing at Z50 during the soak (ask the
  maintainer to look).
- Prime line and first layer good.
- Total START_PRINT ≈ baseline − ~5 min (soak) − the cooldown wait.

**Ask the maintainer** to judge first layer and both colours' start.

### 8. Document (model)

- `docs/start_print_walkthrough.md`: update the action list in Phase 2, step 17 (soak 3), step
  18 (replaced by `karman_nozzle_warm`, plus `karman_nozzle_to_safe` before 17), and the timeline table (use the measured numbers).
- `docs/decisions.md`: new entry at the **top** (newest first):
  `## 2026-MM-DD — START_PRINT cold-start speed-up: soak 3, nozzle to 150 after the unload`
  covering: why 3 not 0; why `extruder_preheating` was replaced (its M109 blocks on cooling);
  why the Z-defining contact must be at 150 (expansion reference) while the calibrate contact may
  be ≤ 180; the measured before/after times.
- `TODO.md`: tick the task under *Miscellaneous* and remove it from *▶ Next up*.

## Verification

- [ ] `FIRMWARE_RESTART` clean with the new config (Step 5).
- [ ] Offline renders match the table in Step 4; `visualize_toolchange.py` all clean.
- [ ] Warm repeat start: START_PRINT duration measured and **shorter** than 2.5–3 min; no
      blocking cool-to-150 wait (Step 6).
- [ ] Cold multi-tool start: soak runs 3 min; nozzle target drops to 150 right after the
      unload; START_PRINT duration measured and compared to the baseline (Step 7).
- [ ] Maintainer confirms first layer is **as good as before** on both tests.
- [ ] Walkthrough + decisions.md updated; TODO.md task ticked.

## Commit guidance

The maintainer runs commits. Git **only over SSH** (never on the mount). Propose:

1. `feat: shorten start_print cold start (soak 3, nozzle to safe temp after unload)`
   — `variables.cfg`, `overrides.cfg` (+ `tools/visualize_toolchange.py` if Step 4 needed it).
2. `docs: record the start_print cold-start speed-up` — `docs/start_print_walkthrough.md`,
   `docs/decisions.md`, `TODO.md`, this runbook (moved to `docs/runbooks/done/`).

```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git status -s'
```

## Status log

- **2026-10-09** — Runbook written (architecture session). Design pre-resolved with the
  maintainer; nothing executed yet.
- **2026-10-10** — Now runs after the PET-ooze runbook (see header); Steps 3a/3b get amended by its Step 9.
