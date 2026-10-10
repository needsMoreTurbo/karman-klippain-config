# Runbook — Happy Hare v4 migration, part 1: prep (pin v3, back up, build the carry-over ledger)

**Objective:** make the v3 → v4 upgrade safe and mechanical:
- close the "Update button pulls v4" hazard;
- take a restorable backup;
- write `docs/hh_v4_carryover.md`, a ledger of **every** Karman-specific Happy Hare value and
  behaviour, each mapped to where it goes in v4, plus the menuconfig answers and the compatibility
  risks checked against v4 source.

No v4 code is installed in this runbook.
**Status:** 🟡 not started
**Created:** 2026-10-10
**Series:** 1 of 3 — next `docs/runbooks/hh-v4-2-install-core.md`, then
`docs/runbooks/hh-v4-3-blobifier-print.md`.
**Prerequisites:** printer idle for any restart; Pi reachable.

## Background

- **Why v4, and why now.** Decided 2026-10-10 (`docs/decisions.md`). The 2026-09-13 evaluation
  (`docs/mmu_software_hh_vs_afc.md`) rejected AFC for Karman: no upstream Blobifier, Klippain's
  START_PRINT MMU path is HH-only, and the tooling is written against HH. It recommended v4.
  The maintainer runs AFC on another printer and finds it easier. v4's `menuconfig` installer
  targets exactly the v3 configuration burden.
  **Timing:** the maintainer chose to migrate **before** the CAN / Micro-Fit wiring, against
  the evaluation's suggestion. Accepted consequence: a later hardware fault must be
  distinguished from a v4 regression by testing, not by elimination.
- **The upgrade is a fresh setup.** No v3 settings migrate. `./install.sh -b main` →
  "Upgrade to v4" renames `~/printer_data/config/mmu` to `mmu.V3` and runs `menuconfig` from
  scratch. Rollback is documented upstream (see part 2). Upgrade guide:
  <https://moggieuk.github.io/Happy-Hare-Doc/Upgrade-v3-v4/>.
- **The open hazard.** `moonraker.conf` → `[update_manager happy-hare]` has
  `primary_branch: main`, and upstream `main` **is v4**. The Pi checkout is `main` @ `5cc88729`
  (v3.4.2-31). Clicking **Update** in Mainsail does a `git pull` without the installer, and
  Klipper then refuses to start.
- **v4 upstream state (2026-10-10).** Tag `v4.0.0` (2026-08-30); `main` is 1537 commits ahead
  @ `c66216b` (2026-10-04). Fast-moving. Part 2 installs `main` and records the commit.

## Scope

1. Pin HH to the `v3` branch and smoke-test it.
2. Back up the v3 config, state and HH checkout.
3. Write `docs/hh_v4_carryover.md`: values, hooks, macros, pins, includes, menuconfig answers,
   and compatibility checks.
4. Register findings; hand off to part 2.

## ⚠️ Out of scope — do not touch

- **Do not install or test v4** — that's part 2.
- **Do not change any value** in `mmu/`, `overrides.cfg`, `mcu.cfg`, `printer.cfg` or
  `variables.cfg` here. The ledger *records* them. If a value looks wrong, note it in the
  ledger's "questions" section for the maintainer. Do not fix it.
- **Never edit Happy Hare's Python** (`~/Happy-Hare/extras/`).
- **Validated values and why they are what they are.** The ledger must carry each with its
  reason (from `docs/decisions.md`), so part 2 doesn't "normalise" any of them to v4 defaults:
  - `toolhead_residual_filament: 33` (2026-08-08, not 25);
  - `variable_retract_length: 60` (cut-fragment margin);
  - `blade_pos 69`, `pushback_length 30`;
  - `min_toolchange_z: 15` (back-left keep-out);
  - `park_toolchange: -999,-999` (Blobifier positions itself);
  - `force_purge_standalone: 1`, `purge_macro: BLOBIFIER`, `restore_xy_pos: "next"`;
  - `flowguard_max_relief: 8` (40 missed a real clog);
  - `gear_unload_speed: 70` (PETG rewinder stall, 2026-09-14);
  - gear `run_current 0.8 A`;
  - `variable_bowden_lengths: 0` (both gates track gate 0 on v3);
  - PSF calibration `0.5037 / 0.0109 / 0.9965`, buffer range 14.5;
  - Blobifier: purge floor 140, `z_raise 8`, `eject_hop 3`, `pressure_release_time 2000`,
    shaker x4/z4, tray top 0.3, brush 53/35, `brush_top: None`;
  - `mmu_unload_on_end_print: False` (Klippain).
- **Keep-out zones** (CLAUDE.md) still apply to every value that is a coordinate.

## Pre-resolved decisions (maintainer, 2026-10-10)

1. **Pin to v3 first, now.** It closes the hazard for the days until part 2. The `v3` branch
   carries upstream fixes through 2026-08-16 that the current checkout lacks. The smoke test in
   Step 2 proves they don't disturb the validated setup.
2. **Backup = tarball plus git.** The config repo itself is the primary record.
3. **`[mcu mmu]` and the MMU pin aliases stay owned by Klippain's `mcu.cfg`** (including the
   Rabbit Burrow `MMU_GEAR_UART=gpio11` fix and `MMU_SYNC_ANALOG=gpio26`). On v3, Klippain's
   include glob `mmu/base/mmu_*.cfg` deliberately **skips** HH's own `mmu/base/mmu.cfg`, which
   also defines `[mcu mmu]` / `[board_pins mmu]`. Part 2 preserves that.
4. **The gate-temperature wrapper** (`docs/runbooks/hh-gate-temp-by-material.md`) is Karman-side
   and carries over. If it's already applied, list it in the ledger; if not, note it as pending.

## Steps

### 1. Record the starting state (model, read-only)

```
ssh ernst@192.168.1.240 'cd ~/Happy-Hare && git rev-parse --abbrev-ref HEAD && git describe --tags && git status -s | head; grep -n "update_manager happy-hare" -A6 ~/printer_data/config/moonraker.conf'
```

Expected: `main`, `v3.4.2-31-g5cc88729`, clean tree, `primary_branch: main`.
Paste this into the ledger's header.

### 2. Pin to v3 (USER, printer idle)

The installer is interactive, so the maintainer runs it **in their own terminal**:

```
ssh -t ernst@192.168.1.240 'cd ~/Happy-Hare && ./install.sh -b v3'
```

Then (model) verify:

```
ssh ernst@192.168.1.240 'cd ~/Happy-Hare && git rev-parse --abbrev-ref HEAD && git describe --tags; grep -n "update_manager happy-hare" -A6 ~/printer_data/config/moonraker.conf; cd ~/printer_data/config && git status -s'
```

Expected: branch `v3`; `primary_branch: v3`. Config-repo changes are limited to
`moonraker.conf` (and possibly HH-managed symlinked files). **If the installer changed any
tracked `mmu/` file, show the maintainer the diff before continuing.**

**Smoke test (USER):** `FIRMWARE_RESTART` (it must be clean), then `MMU_STATUS`, then one
standalone swap and back: `SWAP TOOL=1`, then `SWAP TOOL=0`. Watch:

```
ssh ernst@192.168.1.240 'tail -Fn0 ~/printer_data/logs/mmu.log'
```

Expected: a cut, unload, load and Blobifier purge on each swap, as before.
`docs/mmu_standalone_swap_plan.md` describes `SWAP`. **If anything regresses, stop.** Report
it, and roll back with `ssh -t ernst@192.168.1.240 'cd ~/Happy-Hare && ./install.sh -b main'`
followed by `git checkout 5cc88729` in `~/Happy-Hare`, or ask the maintainer.

### 3. Back up (model, via SSH)

```
ssh ernst@192.168.1.240 'cd ~/printer_data && tar czf ~/hh_v3_backup_$(date +%F).tgz config/mmu config/save_variables.cfg config/printer.cfg config/mcu.cfg config/overrides.cfg config/variables.cfg config/moonraker.conf && (cd ~/Happy-Hare && git rev-parse HEAD) > ~/hh_v3_backup_HEAD.txt && ls -l ~/hh_v3_backup_*'
```

Record the file names in the ledger.

### 4. Build the ledger — values (model, read-only)

Create `docs/hh_v4_carryover.md`. Its sections are: **Header** (state, versions, backups) ·
**Values** · **Hooks & macros** · **Pins & includes** · **menuconfig answers** ·
**Compatibility checks** · **Questions for the maintainer**.

**Values: find every Karman change by diffing against HH's own v3 templates.** Ignore comments
and blank lines:

```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && for f in mmu_parameters mmu_hardware mmu_macro_vars; do echo "=== $f"; diff <(grep -vE "^\s*(#|$)" ~/Happy-Hare/config/base/$f.cfg | sed "s/[[:space:]]*#.*//") <(grep -vE "^\s*(#|$)" mmu/base/$f.cfg | sed "s/[[:space:]]*[#;].*//"); done; echo "=== blobifier"; diff <(grep -vE "^\s*(#|$)" ~/Happy-Hare/config/addons/blobifier.cfg | sed "s/[[:space:]]*#.*//") <(grep -vE "^\s*(#|$)" mmu/addons/blobifier.cfg | sed "s/[[:space:]]*#.*//"); echo "=== blobifier_hw"; cat mmu/addons/blobifier_hw.cfg'
```

The templates contain `{placeholder}` tokens, so some diff lines are template noise. Keep every
line where Karman's file has a concrete value that differs. For **each** value, write a row:

| v3 file : key | v3 value | why (decision date / comment) | v4 destination (menuconfig question, or file : key) |

Also capture these:
- **Calibration/state in `save_variables.cfg`.** Every `mmu_*` key, e.g.:
  ```
  ssh ernst@192.168.1.240 'grep -n "^mmu_" ~/printer_data/config/save_variables.cfg'
  ```
  Includes gear rotation distances `[22.3243, 22.4819]`, bowden lengths, gate map, and so on.
- **The cut-geometry report:**
  ```
  ssh ernst@192.168.1.240 'cd ~/printer_data/config && python3 tools/hh_extract.py --no-files'
  ```
- **HH-related Karman values outside `mmu/`:** `variables.cfg` (`klippain_mmu_enabled`,
  `mmu_check_gates_on_start_print`, `mmu_unload_on_end_print`, …) and `overrides.cfg` (see Step 5).

**v4 destinations: read the v4 source, do not guess.** Download it into the session scratchpad
(not the repo, and **not with `git`** — the repo's guard hook blocks any `git` in a
mount-started session):

```
curl -sL https://codeload.github.com/moggieuk/Happy-Hare/tar.gz/refs/heads/main | tar xz -C <scratchpad>
```

Record the commit:

```
curl -s https://api.github.com/repos/moggieuk/Happy-Hare/commits/main | python3 -c "import json,sys;print(json.load(sys.stdin)['sha'])"
```

Map each key using:
- `config/base/mmu_parameters.cfg`, `mmu_hardware.cfg`, `mmu_macro_vars.cfg` — v4 templates use
  `[[PARAM_…]]` tokens filled by menuconfig;
- `installer/Kconfig*` — the menuconfig questions;
- `installer/build.py` — the token → section mapping, e.g. `var_blobifier_` →
  `gcode_macro _BLOBIFIER_VARS`.

Known moves:
- PSF keys → `[mmu_buffer <unit>] analog_pin / analog_max_compression / analog_max_tension /
  analog_neutral_point`;
- Blobifier variables → `_BLOBIFIER_VARS` (they were on `gcode_macro BLOBIFIER` in v3).

### 5. Build the ledger — hooks, macros, pins, includes (model, read-only)

- **Hooks set in `mmu_macro_vars.cfg`:**
  - `user_park_move_macro: _KARMAN_PARK_MOVE`
  - `user_post_form_tip_extension: BLOBIFIER_PARK`
  - `user_post_unload_extension` / `user_post_load_extension: _KARMAN_STANDALONE_FINISH`
  - plus any other non-empty `variable_user_*`
- **Karman macros in `overrides.cfg` that touch HH:** list every macro and the HH names it uses:
  ```
  ssh ernst@192.168.1.240 'cd ~/printer_data/config && grep -nE "^\[gcode_macro|BLOBIFIER|_?MMU_[A-Z_]+|printer\.mmu|gcode_macro BLOBIFIER" overrides.cfg'
  ```
  For each HH name, confirm it exists in v4 (`grep -rn "^\[gcode_macro NAME\]" <v4>/config` or a
  `register_command` in `<v4>/extras`). Confirmed present on 2026-10-10: `_MMU_PARK`,
  `_MMU_ACTION_CHANGED`, `_MMU_CUT_TIP`, `_MMU_CUT_TIP_VARS`, `_MMU_SEQUENCE_VARS`,
  `BLOBIFIER`, `BLOBIFIER_CLEAN`, `BLOBIFIER_PARK`. **Flag every `printer['gcode_macro BLOBIFIER']`
  variable read**: in v4 those variables live on `_BLOBIFIER_VARS`.
- **Pins & includes:**
  - `printer.cfg` lines ~240–250. Klippain's MMU block is `[include mmu/base/mmu_*.cfg]`,
    `[include config/hardware/mmu.cfg]`, `[include mmu/addons/blobifier.cfg]`.
  - `mcu.cfg` `[mcu mmu]` + `[board_pins mmu_mcu]` (~line 198 on).
  - **Part 2 must handle this:** v4's installer **adds** `[include mmu/macros/*.cfg]` and
    `[include mmu/base/*.cfg]` at the top of `printer.cfg` (`installer/build.py` ~790–800). It
    does not remove Klippain's lines. `mmu/base/*.cfg` would also pull in HH's `mmu.cfg`
    (a duplicate `[mcu mmu]`), and the `mmu/addons/blobifier.cfg` include will point at a
    renamed directory.
  - List every pin alias v3's `mmu_hardware.cfg` references (`mmu:MMU_*`). Part 2 checks that
    v4's generated hardware file references the same names.

### 6. menuconfig answers (model)

Read `installer/Kconfig` and the files it sources in the v4 download. For **every** prompt the
NightOwl / ERB 2 path will show, write the answer in the ledger:
- MMU type `night_owl`; board `erb_2`; 2 gates; per-gate gear steppers;
- the sensors — pre-gate ×2, post-gear ×2, gate (hall) sensor, extruder-entry
  `^toolhead:MCU_ENDSTOP_X`, toolhead `^toolhead:MCU_ENDSTOP_Y`;
- PSF analog buffer on `gpio26`, encoderless, FlowGuard on;
- cutter = Filamatrix tip-cut;
- Blobifier = servo type, servo `PC3` (printer MCU, alias `BLOBIFIER_SERVO`), bucket switch `PC1`
  (`BLOBIFIER_BUCKET`);
- client macros, LEDs (the NightOwl has none unless found in `mmu_hardware.cfg`), and so on.

Take every answer from the live v3 config. Where the v3 config has no answer, put it under
**Questions for the maintainer**. Do not invent one.

### 7. Compatibility checks against v4 source (model)

For each item, record **"confirmed / changed / unknown"** with a file:line from the v4 download:

1. `user_park_move_macro` is called from `config/macros/mmu_sequence.cfg` ~195 and ~273–283.
   v4 also passes **`RESTORE=1`** on the restore moves. `_KARMAN_PARK_MOVE` must accept and
   ignore it. Note whether the `-999` sentinel can still arrive unfiltered.
2. HH still saves the toolhead position at command start and restores it last. This matters for
   the `SWAP` wrapper in `overrides.cfg`.
3. `printer.mmu.print_state` vs `printer.print_stats.state` during START_PRINT. The in-print
   guards in `overrides.cfg` must keep using `print_stats.state`.
4. The `MMU_TEST_FORM_TIP` stranding behaviour: is it still the case?
5. Which `MMU_TEST_CONFIG` parameters are startup-only. Re-derive them for the sync-feedback /
   FlowGuard keys (`docs/decisions.md` 2026-08-20).
6. **Klippain's `printer.mmu.*` reads** must exist in v4's status:
   `tool, print_start_detection, enabled, filament, clog_detection, is_locked, print_state,
   ttg_map, sync_drive, is_homed, filament_pos`. All 11 appear as strings in v4 `extras/`
   (2026-10-10). Confirm each is still emitted by `get_status` and has the same meaning.
   `clog_detection` was already gone in v3, so check what v4 emits.
7. v4's gate check still skips an already-loaded gate (`commands/mmu_check_gate.py:136`,
   confirmed 2026-10-10).
8. v4's `MMU_GATE_MAP` `TEMP` default bug is still present (`commands/mmu_gate_map.py:288`), so
   the Karman wrapper is still needed.

### 8. Hand off (model)

- Add to the ledger a short **"Part 2 must do"** list: everything flagged above.
- Update `TODO.md` (tick this task), and the status logs of this runbook and part 2.

## Verification

- [ ] HH is on branch `v3`; Moonraker `primary_branch: v3`; the smoke test passed (Step 2).
- [ ] Backup tarball and `hh_v3_backup_HEAD.txt` exist on the Pi (Step 3).
- [ ] `docs/hh_v4_carryover.md` exists and has:
  - a row for **every** diffed value, each with a v4 destination or a question;
  - the hooks/macros/pins/includes inventory;
  - a menuconfig answer for every prompt (or a question);
  - all 8 compatibility checks marked with evidence.
- [ ] The maintainer has answered (or deferred, in writing) every ledger question.

## Commit guidance

Git runs **only over SSH**. The maintainer runs commits.
1. `chore: pin happy hare to the v3 branch` — `moonraker.conf` (plus anything else the installer
   touched, after review).
2. `docs: add the happy hare v4 carry-over ledger` — `docs/hh_v4_carryover.md`, `TODO.md`, the
   runbook status logs.

## Status log

- **2026-10-10** — Runbook written (architecture session). Nothing executed.
