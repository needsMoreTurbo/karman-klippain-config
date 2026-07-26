# Standalone swap fixes — implementation runbook

Executable plan for the standalone (out-of-print) filament-swap problems. Written to be executed
step-by-step by any agent/session with no prior context. Background analysis is at the bottom;
the steps are self-contained.

## Ground rules for the executing session
- This working copy is an SSHFS **mount** of the Pi (`ernst@192.168.1.240`, repo = `~/printer_data/config`).
  Edit files here directly; **run ALL git commands via SSH on the Pi**, never from the mount (see CLAUDE.md).
- Config edits take effect only after `FIRMWARE_RESTART` (user runs it, or ask them). Never restart mid-print.
- The user operates the printer. For every LIVE TEST step: give the exact commands, ask the user to run
  them, and wait for their result. Do not assume outcomes.
- Do not use `MMU_TEST_FORM_TIP` (breaks state tracking on this machine). Test cuts/swaps with `T0`/`T1`/`MMU_EJECT`.
- After any macro/geometry change, re-run `uv run tools/visualize_toolchange.py` and check "clean" per scenario.

## Defaults chosen (user may veto at Step 0)
- D1: Heater turns off **immediately** after a standalone load/toolchange (reheat is ~2 min; simplest policy).
- D2: After standalone **load/toolchange**: park on the nozzle rest (45,359). After **unload/eject**: heater
  off but NO park — the user is usually working at the NightOwl and the toolhead position is theirs.
- D3: P3 (color-based standalone purge volumes) is included; skip only if the user says the ~177 mm
  standalone purge doesn't bother them.

## Step 0 — Confirm defaults with the user
Ask exactly: "Executing the standalone-swap plan. OK with: heater off immediately after standalone ops;
park-at-rest only after loads (not unloads); include the purge-volume matrix step? (D1/D2/D3 in the doc)"
Adjust the steps below per answer.

## Step 1 — P4 hygiene edits (safe, do first, no behavior risk)
1a. `mmu/base/mmu_parameters.cfg` (~line 657):
    `default_extruder_temp: 200` → `default_extruder_temp: 245` — comment: safe ABS fallback; gate map normally overrides.
1b. `mmu/base/mmu_parameters.cfg` (~line 655):
    `timeout_pause: 72000` → `timeout_pause: 7200`
1c. `variables.cfg` (~line 80):
    `variable_turn_off_extruder_on_pause: False` → `True`
    (Klippain RESUME reheats automatically — the RESUME override in overrides.cfg retains
    `extruder_target_temp` support. Verify that block still exists before flipping.)
1d. Do NOT touch `flowguard_max_relief` yet (Step 6).

## Step 2 — P1: standalone ops end at the rest, heater off
2a. Add to `overrides.cfg` (near `_KARMAN_PARK_MOVE`):
```
# Finish a STANDALONE (not printing) MMU operation: optionally park on the nozzle rest and
# turn the hotend off. Hooked via HH's user_post_load/user_post_unload extensions.
# In-print guard: HH print_state values during a print are printing/started/pause_locked/paused.
[gcode_macro _KARMAN_STANDALONE_FINISH]
description: Park at rest + heater off after standalone MMU ops
gcode:
    {% set park = params.PARK|default(1)|int %}
    {% if printer.mmu.print_state not in ["started", "printing", "pause_locked", "paused"] %}
        {% if park and "xyz" in printer.toolhead.homed_axes %}
            _KARMAN_PARK_MOVE X=45 Y=359 F=12000
        {% endif %}
        M104 S0
    {% endif %}
```
2b. `mmu/base/mmu_macro_vars.cfg`:
    - `variable_user_post_load_extension : 'BLOBIFIER_PARK'`?? — CHECK FIRST: current value of
      `user_post_load_extension` is `''` and `user_post_form_tip_extension` is `'BLOBIFIER_PARK'`.
      Set: `variable_user_post_load_extension : '_KARMAN_STANDALONE_FINISH'`
    - Per D2: `variable_user_post_unload_extension : '_KARMAN_STANDALONE_FINISH PARK=0'`
      (HH passes the string through as gcode — verify a parameterized extension renders; if HH
      rejects parameters here, create a `_KARMAN_STANDALONE_FINISH_NOPARK` wrapper macro instead.)
2c. `FIRMWARE_RESTART` (user).

## Step 3 — RESOLVED STATICALLY (no test swap needed) → Outcome B
Determined from HH source, 2026-07-25: `_save_toolhead_position_and_park()` runs at the START of
the command (mmu.py:6892, after `_auto_home`), and `_restore_toolhead_position()` is the final step
(mmu.py:3281, "Restore print position as final step"). **No extension hook can change where a swap
ends** — the save precedes every hook. Implemented instead:
- `SWAP TOOL=n` (overrides.cfg) — parks on the rest BEFORE `Tn`, so heat-up ooze lands in the cup
  AND HH's restore returns to the rest. This is the bench swap command.
- `_KARMAN_STANDALONE_FINISH` — hotend-off only, hooked on post_load + post_unload.
- `[idle_timeout]` override — parks on the rest before `M84`, making "on the rest" the idle state.
- ⚠️ GUARD BUG FOUND + FIXED: guarding on HH `print_state` alone shuts the hotend off during
  START_PRINT (Klippain's `_KLIPPAIN_MMU_LOAD_INITIAL_TOOL` runs `MMU_CHANGE_TOOL STANDALONE=1`
  while HH state is still `initialized`). Guard now leads with `printer.print_stats.state`, which
  reads `printing` for the whole file. Verified across 7 state combinations.
- Note: the rest/brush are GANTRY mounted — Z tracks the toolhead, so only the X slide seats or
  unseats the nozzle. Z lifts in these macros are bed-clearance for travel only.

## Step 3 (original) — P1 ordering test (superseded by the above)
HH may run its standalone position-restore AFTER the post_load extension, which would move the
toolhead away from the rest again. Test:
- User runs (hot not required to observe motion; but a real swap needs temp — ask user to run a
  full swap): `T0` then `T1` from the console, not printing.
- Then: `ssh ernst@192.168.1.240 'grep -a "Restoring toolhead position\|_KARMAN" ~/printer_data/logs/mmu.log | tail -8'`
- **Outcome A (extension last / toolhead ends at 45,359, heater off):** done; go to Step 4.
- **Outcome B (HH restore moves it away after parking):** implement the fallback wrapper instead —
  remove the two extension hooks from 2b, keep `_KARMAN_STANDALONE_FINISH`, and add:
```
# Bench convenience: standalone swap that always ends parked at the rest, heater off.
[gcode_macro SWAP]
description: Standalone tool swap: Tn + park on rest + heater off
gcode:
    {% if params.TOOL is not defined %}
        RESPOND TYPE=error MSG="Usage: SWAP TOOL=n"
    {% else %}
        T{params.TOOL|int}
        _KARMAN_STANDALONE_FINISH
    {% endif %}
```
  and tell the user to use `SWAP TOOL=n` for bench swaps.
- Either way, verify the in-print guard: during the next print, swaps must NOT park at the rest or
  kill the heater (watch the first print closely — Step 7).

## Step 4 — P2: first-blob compensation (only if needed)
Ask the user after Step 3's test swap: did the first blob adhere and extrude immediately?
- If yes: skip.
- If no: `mmu/addons/blobifier.cfg`: `variable_purge_length_addition: 0` → `10` — comment:
  compensates melt-zone drain from heat-soak ooze; tune down as P1 reduces ooze.

## Step 5 — P3: standalone purge-volume matrix (per D3)
- User runs: `MMU_CALC_PURGE_VOLUMES` (uses gate-map colors; optional `MULTIPLIER=` if transitions
  look under/over-purged — start default).
- Verify: `ssh ernst@192.168.1.240 'grep -a "purge_volumes\|MMU_CALC" ~/printer_data/logs/mmu.log | tail -5'`
  and that a standalone swap's purge is no longer the flat ~150 mm (console shows the computed value).
- Check persistence: after the next `FIRMWARE_RESTART`, `MMU_SLICER_TOOL_MAP` (console) should still
  show the matrix. If it does NOT persist, note in TODO.md: "re-run MMU_CALC_PURGE_VOLUMES after
  restarts / color changes" (do not build automation now).
- Note: in-print, the slicer's `MMU_START_SETUP ... PURGE_VOLUMES=!purge_volumes!` overwrites this — intended.

## Step 6 — FlowGuard sensitivity walk-down (separate from everything above)
Only after Steps 1–5 are verified and at least one clean print has completed:
- `mmu/base/mmu_parameters.cfg`: `flowguard_max_relief: 40` → `25`. Print. If no false clog/tangle
  trips → `15`. If false trips appear at any value, go back up one step and stop.
- Known risk: PSF ADC noise with no jitter deadband upstream (SD_THRESHOLD is dead code in the
  installed HH). False trips show as "FlowGuard detected a clog/tangle" with no physical cause.

## Step 7 — Verification checklist (end state)
- [ ] Standalone `T0`→`T1` from cold: heats AT the rest (ooze into cup), first blob adheres,
      ends parked at rest (or via `SWAP`), heater off within seconds.
- [ ] `MMU_EJECT`: heater off after; toolhead stays put (per D2).
- [ ] One 2-color print: swaps behave exactly as before (no rest detours, heater stays on,
      Blobifier purge normal). The in-print guard is the critical assertion.
- [ ] Pause mid-print: parks at rest, heater off (new 1c), RESUME reheats + side-exits + resumes.
- [ ] `uv run tools/visualize_toolchange.py` still reports all scenarios clean.
- [ ] Update TODO.md (mark plan items done) and this doc (mark steps done, record Outcome A/B).

## Step 8 — Commit (via SSH on the Pi, only after user confirms tests pass)
Suggested split (Conventional Commits, single-line, propose to user first):
- `feat(mmu): park standalone swaps on nozzle rest with heater off`  (overrides.cfg, mmu_macro_vars.cfg)
- `fix(mmu): safer standalone defaults - abs fallback temp, pause heater-off, shorter pause timeout`  (mmu_parameters.cfg, variables.cfg)
- `feat(mmu): color-based standalone purge volumes` / blobifier tweak if Step 4/5 changed files
- `docs: standalone swap runbook progress`

---

## Background (why these steps — condensed analysis, 2026-07-25)
- Swap temps are CORRECT (gate map 260°C is used; `default_extruder_temp: 200` is an inactive trap).
- The failed first blob is a POSITION problem: standalone ops end wherever HH's restore puts them
  (e.g. 300,25), so the next swap's ~2 min heat-soak oozes there and drains the melt zone → first
  purge extrudes air → blob doesn't stick, then sputters.
- Nothing turns the heater off after standalone ops (HH's `disable_heater` is MMU-pause-only);
  only the 30-min `[idle_timeout]` eventually does.
- Standalone purge volume falls back to the flat `purge_length: 150` (+~27 residual) because no
  slicer matrix exists outside a print.
- Print-path config (cut geometry, purge ownership, parking/side-approach, PSF sync feedback) was
  reviewed and is deliberate — explicitly out of scope; do not modify `park_toolchange`,
  `BLOBIFIER_PARK` hook, or the cut variables in the course of this work.
