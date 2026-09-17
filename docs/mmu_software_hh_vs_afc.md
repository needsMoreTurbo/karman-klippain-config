# MMU software — Happy Hare vs AFC for Karman's NightOwl

**Status (2026-09-13): evaluated, no software change made.** Desk research only: source read at
the commits listed under **Evidence**, plus read-only inspection of the Pi. Nothing was installed,
switched or tested on hardware.

**Conclusion:** stay on **Happy Hare**. Move to **Happy Hare v4** later, as its own objective,
*after* the CAN move and NightOwl relocation. AFC is a sound choice for a stock NightOwl, but on
this machine it loses on exactly the subsystems that took July–August to get working:
Blobifier, Klippain's START_PRINT integration, and the keep-out tooling.

## 0. ⚠️ Open hazard: the update button now pulls v4

`moonraker.conf` → `[update_manager happy-hare]` has `primary_branch: main`. Upstream `main` **is
now v4** (tag `v4.0.0`), and v4 cannot load a v3 config. The Pi checkout is `main` @ `5cc88729`
(v3.4.2-31, 2026-07-07), 1501 commits behind `origin/main`. **Clicking Update in Mainsail pulls
v4 and Klipper refuses to start.** Moonraker's update only does a `git pull` + restart; it never
runs `install.sh`.

**Fix (not yet applied):** when not printing, run `ssh ernst@192.168.1.240 'cd ~/Happy-Hare && ./install.sh -b v3'`.
It switches the checkout to the `v3` branch and repoints the update manager (`primary_branch: v3`).
Per the upstream upgrade guide it leaves the config unchanged. The `v3` branch also carries fixes
through 2026-08-16 that the current checkout lacks.

## 1. The real choice is v4 vs AFC, not v3 vs AFC

- **v3 is maintenance-only.** Upstream says it "will not be actively developed", with updates
  likely limited to breaking Klipper changes or severe bugs. Staying on v3.4.2 is fine for months,
  not indefinitely.
- **v3 → v4 is a fresh setup.** There is no config migration. `install.sh` backs up the old
  config to `~/printer_data/config/mmu.V3` and walks `menuconfig` from scratch.
- Moving to AFC is also a fresh setup. So both forward paths cost a reconfigure. What differs is
  how much of Karman's existing work carries across.

## 2. Fit to Karman, subsystem by subsystem

| Karman has | Happy Hare (v3 today → v4) | AFC |
|---|---|---|
| NightOwl, 2 gates, ERB V2 | ✅ v4 `installer/mmu_types/Kconfig.night_owl`, `installer/boards/Kconfig.erb_2` | ✅ `templates/AFC_NightOwl_1.cfg`, `config/mcu/ERB_2.0.cfg`. `AFC_NightOwl` subclasses `AFC_BoxTurtle` |
| Sensors: pre-gate ×2, post-gear ×2, shared gate, pre- and post-extruder | ✅ as configured | ✅ maps to `prep`, `load`, `[AFC_hub] switch_pin`, `pin_tool_start`, `pin_tool_end` |
| **PSF** proportional sensor, clog detection | ✅ FlowGuard, tuned (`flowguard_max_relief: 8`), with `sync_<gate>.jsonl` telemetry. v4 moves the keys to `[mmu_buffer <unit>] analog_pin / analog_max_compression / …` | ⚠️ `type: FPS_PSF`, **added 2026-07-12** (two months old). Accepts HH-style `neutral_point / max_tension / max_compression`, so the calibrated 0.5037 / 0.0109 / 0.9965 carry over. Fault detection = `filament_error_sensitivity` 0–10 |
| Filamatrix cutter (`_MMU_CUT_TIP_VARS`) | ✅ working | ✅ `AFC_CUT` uses the same variable set (`pin_loc_xy`, `pin_park_dist`, `rip_length`, `pushback_length`, `safe_margin_xy`, …). Values port almost 1:1 |
| **Blobifier** (servo tray, bucket shaker, gantry brush) | ✅ v3 addon. **v4 bundles it** (`config/macros/blobifier.cfg` + menuconfig) with every feature Karman uses (§3) | ❌ not upstream. The community port is stale and unsafe here as-is (§3) |
| **Klippain START_PRINT** | ✅ Klippain's MMU path is HH-only (`_KLIPPAIN_MMU_INIT`, `_KLIPPAIN_MMU_LOAD_INITIAL_TOOL`; see `printer.cfg:241`) | ❌ would need `klippain_mmu_enabled` off and a rewritten print-start sequence |
| Per-gate bowden (gate 1 ≈ 43 mm longer) | ⚠️ v3 autotune only tunes gate 0 (`decisions.md` 2026-08-08). ✅ **v4 autotunes per gate** (`extras/mmu/unit/mmu_calibrator.py` `_autotune_bowden_length(gate, …)`, no gate-0 guard) | ✅ per-lane `dist_hub` via `CALIBRATE_AFC`, plus shared hub `afc_bowden_length` |
| Keep-out enforcement (`_KARMAN_PARK_MOVE` via `user_park_move_macro`) | ✅ hook still present in v4 source | ⚠️ `park_cmd`, `post_load_macro`, `park_pre_load_cmd` exist. Must be rebuilt and re-verified |
| Tooling: `tools/visualize_toolchange.py`, `mmu/hh_extract.py`, HH gotchas in `CLAUDE.md` | ✅ written against HH | ❌ mostly rewrite; gotchas relearned from zero |
| UI: HelixScreen, Mainsail/Fluidd, KlipperScreen, Spoolman | ✅ | ✅ (HelixScreen binary contains AFC support; separate AFC KlipperScreen add-on) |

**Why AFC is popular on NightOwls:** it is the home software of the BoxTurtle/NightOwl ecosystem.
Its lane/hub model maps directly onto type-B hardware, and its config surface is smaller than HH
v3's. It also ships extras: a blade-cut counter, per-lane load stats, button controls, TD-1 and
quiet mode. Most migrations were escapes from v3's configuration burden, and v4's `menuconfig`
installer targets exactly that burden.

**When AFC would become the right answer:** if Blobifier were replaced by a fixed purge spot plus
a kick (AFC's native `AFC_POOP` / `AFC_KICK`), or if Klippain were dropped. Either change removes
one of AFC's two largest costs on this machine.

## 3. Blobifier on AFC — the community port

[ImSundee/Turtleblobifier](https://github.com/ImSundee/Turtleblobifier) is a fork of Dendrowen's
Blobifier adapted for AFC on a BoxTurtle. It has 8 commits, the last on **2025-01-22**, and 3 forks
with no later changes. One issue (Nov 2025) is still unanswered. Its README warns the values are
preset for the author's printer.

**The hookup is correct.** AFC runs cut → `park_cmd` → unload/load → `poop_cmd PURGE_LENGTH=…`
(`extras/AFC.py:1398`, `:1996`), which puts `BLOBIFIER_PARK` / `BLOBIFIER` at the same points HH
uses them. Its leftover `{% if printer.mmu %}` guard (`blobifier.cfg:870`) safely evaluates false,
because Klipper's Jinja env uses default `Undefined` (`klippy/extras/gcode_macro.py:83`).

**It predates features Karman's hardware depends on.** Line numbers refer to the port's `blobifier.cfg`:

1. **Shaker position:** no `shaker_pos_x`. The shake slides to X = `skew_correction` ≈ 0.1
   (`:772`, `:797`). Karman's arm engages at **x=4** (measured 2026-07-17).
2. **Shake path breaks the y_max lane rule:** the shake starts with a diagonal
   `G1 X{brush_start} Y{position_max}` (`:791`), i.e. head-on into y_max at x=53, the brush's left
   edge. It then slides left along y_max past the nozzle rest at x=45. See the keep-out zones in
   `CLAUDE.md`.
3. **No gantry-brush support:** `brush_top` must be numeric and Z always moves to it before
   wiping (`:553-561`). Karman uses `brush_top: None`.
4. **Other missing settings:** `brush_y_offset`, `y_offset`, `retract_between_blobs`,
   `part_cooling_fan_blob_deposit`.
5. **Purge length is computed twice:** the second block (`:363-371`) overwrites the first, so
   purge = max(`PURGE_LENGTH` or `purge_length`, `purge_length_minimum`), and HH's
   residual/fragment term is dropped. **Harmless on Karman**: the 140 mm floor always wins
   (`decisions.md` 2026-08-08).

**If AFC is ever chosen:** start from Karman's own `mmu/addons/blobifier.cfg`, not this fork. The
port's AFC-specific edits (park vars, `PURGE_LENGTH` handling) are small to reapply. The hardware
features above are the hard part, and Karman's file already has them.

## 4. Recommended sequence

1. **Now:** pin Happy Hare to the `v3` branch (§0).
2. **Next:** do the CAN move, NightOwl relocation and bowden re-cal on v3, known-good software, so
   hardware faults aren't confounded with software changes (`docs/mmu_can_bus.md`, roadmap #7).
3. **Then:** migrate to v4 as its own objective (worth a `/brief`). Keep the `mmu.V3` backup open
   for calibration values and custom macros.

**Unverified — check against v4 source before relying on any of it:**
- Klippain's MMU macros against v4's `printer.mmu.*` status fields. Klippain already targets HH
  v2.x, and v3 broke `printer.mmu.clog_detection`.
- Each HH gotcha in `CLAUDE.md`:
  - `-999` sentinel passed unfiltered to `user_park_move_macro`
  - toolhead position saved at command start and restored as the final step (`SWAP` wrapper)
  - `mmu.print_state` lagging `print_stats.state` during START_PRINT
  - `MMU_TEST_FORM_TIP` stranding the tip
- Which `MMU_TEST_CONFIG` params are silently startup-only (`decisions.md` 2026-08-20). v4
  restructured the sync-feedback code.
- Hook names confirmed present in v4 source (presence only, not behavior): `user_park_move_macro`,
  `user_post_load_extension`, `user_post_unload_extension`, `user_post_form_tip_extension`,
  `user_action_changed_extension`, `_MMU_CUT_TIP_VARS`, `_MMU_SEQUENCE_VARS`, `restore_xy_pos`,
  `force_purge_standalone`, `purge_macro`, `min_toolchange_z`, `flowguard_max_relief`,
  `variable_bowden_lengths`, `toolhead_residual_filament`.

## Evidence

| Source | Version read |
|---|---|
| Pi `~/Happy-Hare` | `main` @ `5cc88729`, `v3.4.2-31-g5cc88729` (2026-07-07); `origin/v3` @ `d5cce9f9` (2026-08-16) |
| moggieuk/Happy-Hare `main` (v4) | `baa5097` (2026-09-13) |
| ArmoredTurtle/AFC-Klipper-Add-On | `5ea84ea` (2026-08-23) |
| ImSundee/Turtleblobifier | `8b8cbeb` (2025-01-22) |
| Pi `~/klipper` | `v0.13.0-662-gbd99b19b0` |
| Docs | [HH v3→v4 upgrade guide](https://moggieuk.github.io/Happy-Hare-Doc/Upgrade-v3-v4/), [AFC features](https://github.com/ArmoredTurtle/AT-Documentation/blob/main/docs/afc-klipper-add-on/features.md), AFC `CHANGELOG.md` |
