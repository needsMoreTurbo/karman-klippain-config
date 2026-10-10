# Runbook — Happy Hare v4 migration, part 3: Blobifier, print integration, acceptance print

**Objective:** on Happy Hare v4, the full toolchange chain works in a real print, exactly as it
did on v3:
- cut at z15;
- unload → load;
- **Blobifier purge** (floor 140), bucket shake and gantry-brush wipe;
- resume.

Klippain's START_PRINT / END_PRINT, standalone `SWAP` and the Karman macros all work. A
**2-colour ABS print** passes, and the docs and CLAUDE.md describe v4 instead of v3.
**Status:** 🟡 not started — blocked on part 2
**Created:** 2026-10-10
**Series:** 3 of 3 — after `docs/runbooks/hh-v4-2-install-core.md`.
**Prerequisites:**
- Part 2 complete (core MMU on v4, swaps with cut, tooling reads v4);
- `docs/hh_v4_carryover.md` up to date;
- ABS on both gates (contrasting colours);
- a small 2-colour ABS model sliced with the existing OrcaSlicer setup (`docs/mmu_slicer_setup.md`;
  prime tower **off**).

## Background

- **v4 bundles Blobifier** (`config/macros/blobifier.cfg` in the HH repo, installed under
  `mmu/macros/`). It has every feature Karman's tuned v3 copy has: `shaker_pos_x`,
  `brush_top: None` gantry brush, `brush_y_offset`, lane-safe moves.
  Its variables live on **`gcode_macro _BLOBIFIER_VARS`**; in v3 they were on
  `gcode_macro BLOBIFIER`. Karman's v3 values are in the ledger, taken from
  `mmu.V3/addons/blobifier.cfg`.
- **What the purge settings mean** (each is in the ledger with its decision):
  - `purge_macro: BLOBIFIER` + `force_purge_standalone: 1` — HH owns purge; the slicer tower is off.
  - `user_post_form_tip_extension: BLOBIFIER_PARK` + `restore_xy_pos: "next"`.
  - `park_toolchange: -999,-999` — Blobifier positions itself.
  - Purge floor `purge_length_minimum: 140`, which makes the slicer matrix vestigial (2026-08-08).
  - PETG blob fixes `z_raise 8`, `eject_hop 3`, `pressure_release_time 2000` (2026-09-14).
- **Karman macros that wrap the toolchange** (`overrides.cfg`; `docs/custom_macros.md`):
  - `SWAP` — standalone swap that ends on the rest (HH restores position last);
  - `BLOBIFIER_TEST` — bench purge, then park on the rest;
  - `_KARMAN_PARK_MOVE` — y_max side approach;
  - `_KARMAN_STANDALONE_FINISH` — hotend off after bench ops;
  - `_KARMAN_MMU_ACTION_CHANGED` — white LEDs during purge;
  - the `PARK` / `RESUME` overrides and the idle-timeout park.

## Scope

1. Configure Blobifier on v4 from the ledger, and restore purge ownership.
2. Bench-test purge, deposit, shake and wipe. Then standalone swaps with purge.
3. Run START_PRINT end to end, then a single-colour print, then the 2-colour acceptance print.
4. Re-verify the Karman-side features: gate-temperature wrapper, PET hot wipe and cold-start
   actions if applied, END_PRINT.
5. Update CLAUDE.md, the docs and `docs/decisions.md`. Retire the v3-specific notes.

## ⚠️ Out of scope — do not touch

- **Blobifier geometry and tuning values from the ledger.** Carry them exactly; don't take v4
  defaults:
  - shaker x4/z4, tray top 0.3, purge_x 9;
  - brush 53/35, `brush_top: None`;
  - floor 140, `z_raise 8`, `eject_hop 3`, `pressure_release_time 2000`;
  - `bucket_shake_frequency 0.95`, `max_blobs 400`.
- **Never add logic to the stock Blobifier macro** (maintainer rule). Use its variables.
  Karman-specific behaviour lives in `overrides.cfg`.
- **Cut geometry, `min_toolchange_z 15`, `park_toolchange -999,-999`** — validated (ledger).
- **Klippain framework files.** START_PRINT changes go through `overrides.cfg` actions only.
- **CAN wiring** — separate objective.
- **Keep-out zones** (CLAUDE.md):
  - front-left x<10/y<17, any Z;
  - back-left x<~20/y>~335, below z15 — the tray, shaker and depressor;
  - y_max row (tray x2–17, shaker x4, rest x45, brush x53–88): only via the lanes 15<x<40 or
    x>95, then an X slide.

  `tools/visualize_toolchange.py` must be clean before every motion test that changes a path.

## Pre-resolved decisions (maintainer, 2026-10-10)

1. **The acceptance test is a real 2-colour ABS print**, with clean transitions on the part, no
   FlowGuard trip, and no state desync. That matches the v3 acceptance
   (`docs/runbooks/done/blobifier-bringup.md`).
2. **v3-specific notes are corrected, not deleted.** In CLAUDE.md, each Happy Hare gotcha is
   re-labelled with what v4 does (from the ledger's compatibility checks). History stays in
   `docs/decisions.md`.
3. **The ledger stays** as `docs/hh_v4_carryover.md`, as the record of what was carried and why.

## Steps

### 1. Configure Blobifier and purge (model)

- Set every Blobifier value from the ledger in v4's `_BLOBIFIER_VARS` location (and
  `blobifier_hw` pins, if v4 keeps a separate file). Keep date/reason comments.
- Restore `purge_macro: BLOBIFIER`, `force_purge_standalone: 1`, `restore_xy_pos: "next"`, and
  the `BLOBIFIER_PARK` hook (part 2 emptied `purge_macro`).
- Check `overrides.cfg`'s `BLOBIFIER_TEST` and any other Blobifier variable reads use the v4
  names.
- `uv run tools/visualize_toolchange.py` — **all clean**, including `midprint_swap_shake`.

### 2. Apply (USER)

`FIRMWARE_RESTART` is enough for `.cfg`-only changes. Use `sudo systemctl restart klipper` if HH
was updated. Then `BLOBIFIER_STATUS`, and the model compares the output to the ledger.

### 3. Bench purge, shake, wipe (USER)

With T0 loaded and the nozzle hot via HH:
1. `BLOBIFIER_TEST PURGE_LENGTH=140`. Expected: the tray comes out, a full-size blob, the tray
   retracts and the blob drops into the bucket, the nozzle is wiped, and the toolhead parks on
   the rest.
2. Run `BLOBIFIER_SHAKE_BUCKET` once. The shaker arm must engage at x4 with no collision.

Ask the maintainer to watch each and describe the result. Watch the log live:

```
ssh ernst@192.168.1.240 'tail -Fn0 ~/printer_data/logs/mmu.log'
```

### 4. Standalone swaps with purge (USER)

Run `SWAP TOOL=1`, then `SWAP TOOL=0`. Expected:
- cut → `BLOBIFIER_PARK` → unload → load → Blobifier purge (`Purging 140mm` or more in the log)
  → wipe;
- the toolhead ends on the rest;
- the hotend turns off afterwards (`_KARMAN_STANDALONE_FINISH`);
- the nozzle LEDs go white during the purge.

### 5. START_PRINT and a single-colour print (USER)

Print any small single-colour model. Watch klippy.log and mmu.log. Expected:
- `_KLIPPAIN_MMU_INIT` runs with no Klippain error, which proves the status fields;
- the initial tool loads inside `extruder_heating`;
- the purge goes to Blobifier;
- the print completes;
- END_PRINT parks on the rest.

If the PET-ooze / cold-start runbooks have been applied, their `KARMAN:` console lines appear as
those runbooks describe.

### 6. 2-colour ABS acceptance print (USER)

Print the 2-colour model. Ask the maintainer to judge:
- [ ] every colour transition is clean **on the part**;
- [ ] no FlowGuard trip and no MMU error or desync across all swaps (the model checks mmu.log
      afterwards);
- [ ] the bucket shakes when the counter calls for it (about every 20 blobs —
      `bucket_shake_frequency 0.95`, `max_blobs 400`). Only expected if the print has enough swaps.

### 7. Karman-side features (USER + model)

- **Gate-temperature wrapper,** if applied: in the Mainsail HH panel, set the material to ABS
  (expect 260), then change the colour; the temperature must stay 260.
  `docs/runbooks/hh-gate-temp-by-material.md` Step 6 has the full check.
- **Idle-timeout park and `PAUSE` / `RESUME`:** run `PAUSE` then `RESUME` once on the single-colour
  print, or on a test print. It must park on the rest and leave it sideways.

### 8. Docs (model)

- **`CLAUDE.md`:**
  - change "Happy Hare v3.4.2" to v4 (with the commit);
  - update the include/paths notes (`mmu/macros/`, `_BLOBIFIER_VARS`, `[mmu_buffer]`);
  - re-state each HH gotcha in "Klippain + Happy Hare layering" per the ledger's compatibility
    findings. Keep it if it's still true; correct it if it changed.
- **`docs/mmu_purge_volume.md`, `docs/custom_macros.md`, `docs/mmu_standalone_swap_plan.md`,
  `docs/start_print_walkthrough.md`:** fix v3 paths and names.
- **`docs/mmu_software_hh_vs_afc.md`:** add a line at the top saying "Superseded: migrated to v4
  on <date>".
- **`docs/decisions.md`:** add an entry at the top,
  `## 2026-MM-DD — Happy Hare v4 migration complete`. Cover what was carried vs re-calibrated
  (per-gate bowden), the include/pin ownership choice (Klippain keeps `[mcu mmu]`), and anything
  v4 changed that bit you.
- **`TODO.md`:** tick the series; update the roadmap.

## Verification

- [ ] Bench purge, deposit, shake and wipe all correct (Step 3).
- [ ] Standalone swaps purge through Blobifier and end on the rest (Step 4).
- [ ] A single-colour print completes through Klippain's START_PRINT/END_PRINT with no MMU
      error (Step 5).
- [ ] **The 2-colour ABS print passes all three criteria in Step 6** — the objective.
- [ ] The gate-temperature wrapper and PAUSE/RESUME were re-verified (Step 7).
- [ ] `visualize_toolchange.py` is clean on all scenarios against the final v4 config.
- [ ] CLAUDE.md, the docs and decisions.md are updated (Step 8).

## Commit guidance

Git runs **only over SSH**. The maintainer runs commits. Propose:
1. `feat: restore blobifier purge ownership on happy hare v4` — `mmu/`, `overrides.cfg`.
2. `docs: update claude.md and mmu docs for happy hare v4` — `CLAUDE.md`, `docs/*.md`,
   `docs/decisions.md`, `TODO.md`, and the three series runbooks (moved to `docs/runbooks/done/`).

## Status log

- **2026-10-10** — Runbook written (architecture session). Nothing executed.
