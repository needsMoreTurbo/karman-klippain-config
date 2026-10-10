# Runbook — Happy Hare v4 migration, part 2: install v4 and bring up the core MMU

**Objective:** Karman runs Happy Hare v4 with the core MMU working:
- Klipper starts clean and Klippain sees the MMU;
- all sensors and the PSF read correctly;
- both gates are calibrated (bowden **per gate**);
- `MMU_LOAD` / `MMU_EJECT` work on both gates;
- standalone `T0`↔`T1` swaps **with the Filamatrix cut** work.

**Purge (Blobifier) is not part of this runbook.** It stays off until part 3.
**Status:** 🟡 not started — blocked on part 1
**Created:** 2026-10-10
**Series:** 2 of 3 — after `docs/runbooks/hh-v4-1-prep.md`, before
`docs/runbooks/hh-v4-3-blobifier-print.md`.
**Prerequisites:**
- Part 1 complete: HH on `v3`; backup exists; `docs/hh_v4_carryover.md` complete, with every
  question answered.
- The printer is **idle, with no print planned for the session** — this takes hours.
- Both spools present.

## Background

- **Read `docs/hh_v4_carryover.md` first.** It is the input to every step here: values, hooks,
  menuconfig answers, include/pin notes, and the compatibility findings.
- **The upgrade is a fresh setup.** `./install.sh -b main` → "Upgrade to v4". The installer:
  - renames `~/printer_data/config/mmu` → `mmu.V3` (untouched);
  - runs `menuconfig`;
  - generates a new `mmu/` tree;
  - **adds** `[include mmu/macros/*.cfg]` and `[include mmu/base/*.cfg]` at the top of
    `printer.cfg`. It **does not** remove Klippain's existing MMU include lines.
- **v4 is new Python.** `FIRMWARE_RESTART` does **not** reload `extras/*.py` (CLAUDE.md). After
  the install, and after any HH update, use a **host restart**:
  `ssh ernst@192.168.1.240 'sudo systemctl restart klipper'`.
- **Upstream rollback** (from the upgrade guide), plus Karman's own files:
  ```
  ssh -t ernst@192.168.1.240 'cd ~/Happy-Hare && ./install.sh -d'      # uninstall v4 (backs up the v4 config)
  ssh ernst@192.168.1.240 'cp -a ~/printer_data/config/mmu.V3 ~/printer_data/config/mmu'   # only if no mmu/ dir remains
  ssh -t ernst@192.168.1.240 'cd ~/Happy-Hare && ./install.sh -b v3'
  ssh ernst@192.168.1.240 'cd ~/printer_data/config && git checkout -- printer.cfg mcu.cfg overrides.cfg moonraker.conf && sudo systemctl restart klipper'
  ```
  Never copy over an existing `mmu` directory. If several `mmu.V3-*` exist, pick the right one
  with the maintainer.

## Scope

1. Put the MMU in a known physical state, then install v4 with the ledger's menuconfig answers.
2. Reconcile `printer.cfg` includes and `mcu.cfg` pins with Klippain.
3. Apply the ledger's file-level values. Adapt `overrides.cfg` to v4 names.
4. Bring up and verify: Klippain status, sensors, PSF, calibration, load/eject, swaps with cut.
5. Update `tools/visualize_toolchange.py` / `tools/hh_extract.py` for the v4 paths. They must
   pass before the first motion test.

## ⚠️ Out of scope — do not touch

- **Blobifier purge ownership and tuning** — part 3. Keep it configured if menuconfig requires
  it, but set `purge_macro` empty (no purge) for this runbook. Bench swaps will mix colour in the
  nozzle; that's expected.
- **START_PRINT / slicer / real prints** — part 3.
- **Every validated value in the ledger.** Carry it exactly as recorded; do not adopt a v4
  default instead. In particular:
  - `toolhead_residual_filament 33`, `retract_length 60`, `blade_pos 69`, `pushback 30`;
  - `min_toolchange_z 15`, `park_toolchange -999,-999`;
  - `flowguard_max_relief 8`, `gear_unload_speed 70`, the gear current;
  - the PSF calibration.

  The reasons are in the ledger and `docs/decisions.md`.
- **Gear rotation distances** are carried, not re-measured (see Pre-resolved).
- **`[mcu mmu]` / pin aliases** stay in Klippain's `mcu.cfg` (see Pre-resolved).
- **Never edit Happy Hare's Python.** Never edit Klippain framework files (`macros/`, `config/`).
- **Never `MMU_TEST_FORM_TIP`** (CLAUDE.md) unless the ledger's compatibility check proved v4
  changed that behaviour. Test cuts with `MMU_EJECT` / swaps; fix desync with `MMU_RECOVER`.
- **CAN wiring** — separate objective (TODO roadmap #7).
- **Keep-out zones** (CLAUDE.md): front-left x<10/y<17 any Z; back-left x<~20/y>~335 below z15;
  y_max feature row only via the lanes 15<x<40 or x>95. `tools/visualize_toolchange.py` must be
  clean before any swap.

## Pre-resolved decisions (maintainer, 2026-10-10)

1. **Install `main`** — the installer's `-b main`. Record the commit in the ledger header.
2. **Start from a physically clear MMU.** Eject to the gates under v3 before upgrading, and
   confirm every gate is clear of the shared bowden. RECOVER moves nothing; see the maintainer
   memory rule about physical state before any load.
3. **Klippain keeps `[mcu mmu]` and the pin aliases** (`mcu.cfg`). That includes the Rabbit Burrow
   `MMU_GEAR_UART=gpio11` override and `MMU_SYNC_ANALOG=gpio26`. Include HH's base files with
   Klippain's glob `mmu/base/mmu_*.cfg`, which skips HH's `mmu.cfg` (its `[mcu mmu]`), **not** the
   installer's `mmu/base/*.cfg`. If v4's hardware file references an alias that `mcu.cfg` lacks,
   **add it to `mcu.cfg`**.
4. **Carry the gear rotation distances** (`[22.3243, 22.4819]`) and the PSF calibration from the
   ledger. Re-calibrate **only** the bowden, per gate, because v4 autotunes each gate and v3 only
   ever tuned gate 0 (`docs/decisions.md` 2026-08-08). If a load/eject length check (Step 9) is off
   by more than 2 %, stop and ask the maintainer before re-calibrating the gears.
5. **Git:** add `mmu.V3*/` to `.gitignore` (the backup tarball plus git history already hold v3).
   Commit the new `mmu/` tree only after Step 11 passes.

## Steps

### 1. Preflight (model + USER)

- Read the ledger end to end. **If any question is unanswered, stop.**
- USER: from loaded, `MMU_EJECT`. Then physically confirm **both** filament tips are back at
  their gates and the shared bowden is empty. Model checks:
  `ssh ernst@192.168.1.240 'grep -n "^mmu_state_filament_pos\|^mmu_state_tool\|^mmu_state_gate_selected" ~/printer_data/config/save_variables.cfg'`.

### 2. Install v4 (USER, interactive)

In the maintainer's own terminal:

```
ssh -t ernst@192.168.1.240 'cd ~/Happy-Hare && ./install.sh -b main'
```

- Choose **"Upgrade to v4"**.
- In `menuconfig`, answer **every prompt from the ledger's "menuconfig answers" table**. If a
  prompt isn't in the table, stop and ask the model, which will check the v4 source, rather than
  guessing.
- Save and exit. Let the installer finish. Klipper may fail to start at this point; that is
  expected until Step 3.

Model records the result:

```
ssh ernst@192.168.1.240 'cd ~/Happy-Hare && git rev-parse HEAD && git describe --tags; ls ~/printer_data/config | grep -i mmu; ls -la ~/printer_data/config/mmu ~/printer_data/config/mmu/*; cd ~/printer_data/config && git status -s'
```

### 3. Reconcile includes and pins (model)

1. In `printer.cfg`, remove the installer-added `[include mmu/base/*.cfg]` and
   `[include mmu/macros/*.cfg]` at the top, and their installer comment. Rewrite Klippain's MMU
   block (~line 241) as follows, keeping the existing Klippain comments:
   ```
   [include mmu/base/mmu_*.cfg]
   [include mmu/macros/*.cfg]
   [include config/hardware/mmu.cfg]
   ```
   Delete the old `[include mmu/addons/blobifier.cfg]` line (and its comment). In v4, Blobifier
   ships in `mmu/macros/` if menuconfig enabled it.
   **Order check:** `overrides.cfg` must still be included **after** these lines, because it
   redefines HH/Klippain macros (`PARK`, `MMU_GATE_MAP` wrapper, …).
2. If the v4 tree has `mmu/base/mmu.cfg` with `[mcu mmu]` / `[board_pins mmu]`, leave it in
   place; the glob excludes it. Then list every `mmu:` alias the v4 files reference, and check
   each exists in `mcu.cfg`'s `[board_pins mmu_mcu]`:
   ```
   ssh ernst@192.168.1.240 'cd ~/printer_data/config && grep -rhoE "mmu:[A-Z_0-9]+" mmu/ | sort -u'
   ```
   Add any missing alias to `mcu.cfg`, mapped to the same physical pin as v3 used. If v3 didn't
   use it, ask.
3. If any v4 file *other than* `mmu/base/mmu.cfg` defines `[mcu mmu]`, stop and report it.

### 4. Apply ledger values and adapt `overrides.cfg` (model)

- For every ledger row whose v4 destination is a **file : key**, set the value in the generated
  v4 file. Keep a one-line comment with the date and reason, copied from the v3 comment.
- `overrides.cfg`:
  - Replace every `printer['gcode_macro BLOBIFIER']` variable read flagged in the ledger with
    `printer['gcode_macro _BLOBIFIER_VARS']`, or whatever the ledger's check 5 found.
  - `_KARMAN_PARK_MOVE` must tolerate v4's `RESTORE=1` parameter (ledger check 1). Keep the
    `-999` handling.
  - Re-check every in-print guard still uses `printer.print_stats.state` (ledger check 3).
- `mmu_macro_vars` hooks: set `user_park_move_macro`, `user_post_form_tip_extension:
  BLOBIFIER_PARK`, and `user_post_unload_extension` / `user_post_load_extension:
  _KARMAN_STANDALONE_FINISH` exactly as in the ledger.
- Set `purge_macro` empty for this runbook (part 3 restores `BLOBIFIER`).
- If the gate-temperature wrapper (`docs/runbooks/hh-gate-temp-by-material.md`) is in
  `overrides.cfg`, leave it. v4's `MMU_GATE_MAP` has the same bug (ledger check 8).

### 5. Tooling (model)

Update `tools/visualize_toolchange.py` and `tools/hh_extract.py` to read the v4 locations
(`mmu/macros/`, `_BLOBIFIER_VARS`, `[mmu_buffer]`, and any renamed keys). Then:

```
uv run tools/visualize_toolchange.py
ssh ernst@192.168.1.240 'cd ~/printer_data/config && python3 tools/hh_extract.py --no-files'
```

The visualizer must report **every scenario clean**, and the extract must report the same cut
geometry as the ledger. Don't continue to any motion step until both match.

### 6. Start Klipper (USER)

```
ssh ernst@192.168.1.240 'sudo systemctl restart klipper'
```

Then the model reads errors:

```
ssh ernst@192.168.1.240 'tail -n 80 ~/printer_data/logs/klippy.log'
```

Fix config errors one at a time and host-restart after each. **Do not** silence an error by
deleting a validated value. If a ledger key is rejected as unknown, the ledger mapping is wrong:
re-check the v4 source.

### 7. Klippain and status (USER + model)

- USER: `MMU_STATUS`. The model compares it with the ledger: 2 gates, gate map, tool map.
- Model:
  ```
  curl -s "http://192.168.1.240:7125/printer/objects/query?mmu"
  ```
  Confirm every Klippain field from ledger check 6 is present with a sensible value.

### 8. Sensors and PSF (USER + model)

- USER runs `MMU_SENSORS DETAIL=1`, then triggers each switch by hand while the model watches
  the output: pre-gate 0/1, post-gear 0/1, gate sensor, extruder-entry, toolhead. Every switch
  must change state **and** be the right one. Polarity was inverted (`^!`) on v3; see the ledger.
- PSF: with a gate loaded to the buffer, the raw reading must move from high (compression) to
  low (tension) as the buffer is squeezed and pulled. It reads **HIGH under compression**.
- Only if the ledger says the PSF must be re-calibrated: `MMU_CALIBRATE_PSENSOR` **from
  mid-travel** (the 2026-07-25 gotcha). Starting at a rail returns garbage. Expected values are
  close to `0.5037 / 0.0109 / 0.9965`.

### 9. Calibration and load/eject (USER + model)

Watch the MMU log live:

```
ssh ernst@192.168.1.240 'tail -Fn0 ~/printer_data/logs/mmu.log'
```

1. Bowden, per gate. Use v4's command and syntax as found in the v4 source or docs (record which
   in the ledger). Expect roughly 1445 mm for gate 0 and ~43 mm more for gate 1
   (`docs/decisions.md` 2026-08-08).
2. `MMU_LOAD GATE=0`, then `MMU_EJECT`; then the same for gate 1. Each must reach the nozzle and
   return to the gate with no error. Check the logged distances against the calibrated bowden ±2 %.

### 10. Standalone swaps with cut (USER)

`visualize_toolchange.py` must be clean (Step 5). Then:
1. `T0` (load).
2. `SWAP TOOL=1`, then `SWAP TOOL=0`.

Expected each time:
- cut at the back-left (y341, z15) → unload → load → **no purge** (`purge_macro` empty);
- the toolhead ends on the nozzle rest via the side approach.

Ask the maintainer to watch the path at the y_max row: the lane entry, the X slide, no head-on
approach.

Then `MMU_EJECT` and check the cut tip by eye: flat, with no wisp.

### 11. Commit and hand off (model)

- `.gitignore`: add `mmu.V3*/`.
- Update the ledger with what changed during bring-up. Update `TODO.md` and the status logs of
  this runbook and part 3.

## Verification

- [ ] HH reports v4 (`MMU_STATUS` / `git describe`), commit recorded in the ledger.
- [ ] Klipper starts with no config error after a host restart. Klippain's MMU fields are
      present (Step 7).
- [ ] Every sensor toggles and is the correct one. The PSF responds in the right direction
      (Step 8).
- [ ] The bowden is calibrated **per gate**, and both gates load and eject cleanly (Step 9).
- [ ] At least two standalone swaps in each direction **with cut**, the toolhead ends on the rest
      via a lane, and the cut tip is flat (Step 10).
- [ ] `visualize_toolchange.py` reads the v4 tree and is clean; `hh_extract.py` matches the ledger.

## Commit guidance

Git runs **only over SSH**. The maintainer runs commits. Propose:
1. `feat: migrate happy hare to v4 (core mmu)` — the new `mmu/`, `printer.cfg`, `mcu.cfg`,
   `overrides.cfg`, `moonraker.conf`, `.gitignore`.
2. `tools: read the happy hare v4 config layout` — `tools/visualize_toolchange.py`,
   `tools/hh_extract.py`.
3. `docs: record happy hare v4 core bring-up` — the ledger, `TODO.md`, the runbook status logs.

The mount shows symlink type-changes, so check the real state with
`ssh ernst@192.168.1.240 'cd ~/printer_data/config && git status -s'`.

## Status log

- **2026-10-10** — Runbook written (architecture session). Nothing executed.
