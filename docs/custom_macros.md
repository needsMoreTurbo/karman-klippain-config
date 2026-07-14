# Custom macros — what Karman adds beyond stock Klippain / Happy-Hare

This is the index of every g-code macro on Karman that is **not** part of a stock
[Klippain](https://github.com/Frix-x/klippain) or [Happy-Hare](https://github.com/moggieuk/Happy-Hare)
install. Each entry lists the macros, the file they live in, what they do, and — where the work is
based on or leverages someone else's code — the source and the specific features borrowed.

All custom macros are defined in the **repo-root, user-editable** files (`bed_fans.cfg`,
`thermal_expansion.cfg`, `overrides.cfg`). The framework directories (`config/`, `macros/`,
`moonraker/`, `scripts/`) and the `mmu/base/mmu_*.cfg` symlinks are unmodified upstream code — see
[CLAUDE.md](../CLAUDE.md) for the layout.

| Subsystem | File | Public macros | Source / basis |
|---|---|---|---|
| Bed-fan control state machine | [bed_fans.cfg](../bed_fans.cfg) | `BED_FANS_MANUAL/AUTO/OFF/STATUS` | Original rewrite (replaces a 3DPrintDemon port) |
| Nozzle thermal-expansion compensation | [thermal_expansion.cfg](../thermal_expansion.cfg) | `BEACON_CALIBRATE_NOZZLE_TEMP_OFFSET`, `BEACON_APPLY_MULTIPLIER`, `BEACON_VARS` | YanceyA/BeaconPrinterTools (RatOS lineage) |
| Config git sync | [overrides.cfg](../overrides.cfg) | `GIT_PUSH`, `GIT_PULL` | Original; needs the G-Code Shell Command extension |
| START/END-print sequence wiring | [overrides.cfg](../overrides.cfg) | `_START_PRINT_ACTION_NOZZLE_EXPANSION`, `_END_PRINT_ACTION_NOZZLE_EXPANSION` | Klippain modular-sequence extension point |

---

## 1. Bed-fan control state machine

**File:** [bed_fans.cfg](../bed_fans.cfg) · **Design of record:** [docs/bed_fans_control.md](bed_fans_control.md)

A self-contained, always-on control loop for the under-bed LDO 5015 fans
(`[fan_generic Bed_Fans]`, pin `PF9`). One `delayed_gcode` (`_BED_FAN_TICK`) runs both the
standby preheat and the in-print behaviour and needs **no** START_PRINT hooks. Fan speed is gated
on the **bed** temperature (chamber is only a safety cap), with an explicit state machine:
`OFF → HEATING → SETTLE → RAMP → HOLD`, plus `MANUAL`, `DROP-GUARD`, `CHAMBER-CAP`, and `COOL`.

| Macro | Purpose |
|---|---|
| `_BED_FAN_VARS` | Tunables (activation temp, heating/high speed, ramp step, chamber cap/resume, cool-down) + internal state. |
| `_BED_FAN_TICK` (`delayed_gcode`) | The control loop — re-arms itself every `tick_interval` seconds. |
| `BED_FANS_MANUAL SPEED=<0-100>` | Latch a fixed speed for the rest of the print. |
| `BED_FANS_AUTO` | Clear the latch, resume automatic control. |
| `BED_FANS_OFF` | Force off and hold off (latched). |
| `BED_FANS_STATUS` | Report state / speed / latch / thresholds. |

Moving the Mainsail fan slider auto-latches to that speed (slider-change detection in the tick).

**Source / basis.** This is an **original rewrite**. It *replaces* the previous `bed_fans.cfg`,
which was a port of the community **3DPrintDemon "Bed Fans Monitor" v2.0.1** (`_BED_FAN_MONITOR` /
`_FLOATING_FAN` / `_BED_PREHEAT_WATCH`). The rewrite exists to fix three concrete failures in that
port — the preheat fans stalling the Keenovo bed (`max_power: 0.8`) and tripping Klipper's
`verify_heater`, no persistent manual override, and no true low→high ramp. The full problem
statement and state-machine spec are in [docs/bed_fans_control.md](bed_fans_control.md). The
`[fan_generic Bed_Fans]` hardware block follows the standard Voron under-bed-fan wiring; only the
control logic is bespoke.

---

## 2. Nozzle thermal-expansion compensation (Beacon contact)

**File:** [thermal_expansion.cfg](../thermal_expansion.cfg) · **Doc:** [docs/thermal_expansion.md](thermal_expansion.md)

As the hotend heats, the nozzle grows longer, so the real nozzle-to-bed gap at print temperature is
smaller than at the low temperature used for Beacon **contact** Z establishment. These macros apply
a matching `SET_GCODE_OFFSET Z_ADJUST` at print start and remove it at print end, so first-layer
height is correct regardless of print temperature.

```
Z_ADJUST = multiplier * (extruder.target - calibration_temp) * (coefficient / 100)
```

| Macro | Purpose |
|---|---|
| `BEACON_VARS` | Enable flag, `calibration_temp` (150 °C), `multiplier`. |
| `_BEACON_INIT` (`delayed_gcode`) | Re-zeros the saved applied offset on every `FIRMWARE_RESTART`. |
| `_BEACON_SET_/_REMOVE_NOZZLE_TEMP_OFFSET` | Runtime apply/remove pair; self-correcting (backs out the prior offset first). |
| `BEACON_CALIBRATE_NOZZLE_TEMP_OFFSET` | On-machine calibration: probes at 150 °C and 250 °C to derive the coefficient. |
| `_BEACON_PROBE_/_STORE_/_NOZZLE_TEMP_OFFSET` | Calibration helpers. |
| `BEACON_APPLY_MULTIPLIER` | Derives a correction multiplier from a measured `homing_origin.z` at temperature. |

**Source / basis.** Adapted from
[**YanceyA/BeaconPrinterTools** — Thermal Expansion Compensation](https://github.com/YanceyA/BeaconPrinterTools/blob/main/Tools/Thermal_Expansion_Compensation/Thermal_expansion_compensation.md).
Features leveraged from that project: the two-temperature contact-probe calibration routine, the
`coefficient`/`multiplier` model, and the runtime apply/remove offset scheme. The macros retain
their **RatOS** heritage in places (the `svv = printer.save_variables.variables` "ratos variables
file" idiom). Persistence uses the stock Klipper `[save_variables]` → `save_variables.cfg`.

**Karman-specific:** `nozzle_expansion_coefficient = 0.055` (≈0.055 mm growth over 150→250 °C).
Because `save_variables.cfg` is gitignored/runtime-written, this must be re-seeded after a reflash —
see [docs/thermal_expansion.md](thermal_expansion.md).

---

## 3. Config git sync — `GIT_PUSH` / `GIT_PULL`

**File:** [overrides.cfg](../overrides.cfg) (macros) + [git_sync.sh](../git_sync.sh) (logic)

Console/Mainsail macros that keep the printer's live `~/printer_data/config` in sync with the
GitHub repo — the deploy path described in [CLAUDE.md](../CLAUDE.md).

| Macro / section | Purpose |
|---|---|
| `[gcode_shell_command git_push]` / `git_pull` | Bind `git_sync.sh push` / `pull` to Klipper. |
| `GIT_PUSH` | Commit `-A` and push (auto-commit message with timestamp). |
| `GIT_PULL` | `--ff-only` pull; **blocked mid-print**, and only issues a `FIRMWARE_RESTART` if the pull actually changed something. |

**Source / basis.** The macros and `git_sync.sh` are **original** to this repo. They depend on the
community **G-Code Shell Command extension** (`klipper/klippy/extras/gcode_shell_command.py`, which
provides `[gcode_shell_command]` / `RUN_SHELL_COMMAND` — commonly installed via
[KIAUH](https://github.com/dw-0/kiauh)'s Klipper extensions). The script is deliberately
fail-safe for automation: `ssh -o BatchMode=yes`, `--ff-only` (never auto-merges into conflict
markers), and it refuses to restart firmware unless `HEAD` moved.

---

## 4. START_PRINT / END_PRINT sequence customization

**File:** [overrides.cfg](../overrides.cfg) — `_USER_VARIABLES` + the `_*_ACTION_*` macros

Klippain's START/END print sequences are **modular**: the ordered lists in
`variable_startprint_actions` / `variable_endprint_actions` name actions, and each maps to a
`_START_PRINT_ACTION_<NAME>` / `_END_PRINT_ACTION_<NAME>` macro. Karman uses this documented
extension point to inject a custom `nozzle_expansion` action:

```
variable_startprint_actions: ... "extruder_heating", "nozzle_expansion", "purge", "clean", "primeline"
variable_endprint_actions:   "retract_filament", "nozzle_expansion", "turn_off_heaters", ...
```

`_START_PRINT_ACTION_NOZZLE_EXPANSION` / `_END_PRINT_ACTION_NOZZLE_EXPANSION` (defined in
[thermal_expansion.cfg](../thermal_expansion.cfg)) call the thermal-expansion apply/remove pair. On
START it is ordered **after** `extruder_heating` (so `extruder.target` holds the real print temp)
and after the contact-Z steps (so `Z_ADJUST` stacks on the probe/material offset).

**Source / basis.** This uses Klippain's own modular-sequence mechanism (see the guidance block at
the top of `overrides.cfg`); the only custom part is the `nozzle_expansion` action itself. Nothing
in the framework is modified.

---

## Not custom (documented here so it isn't mistaken for custom)

- **MMU / Happy-Hare.** The `mmu/base/mmu_*.cfg` files that hold macros
  (`mmu_purge.cfg`, `mmu_sequence.cfg`, `mmu_software.cfg`, cut/form-tip, …) are **symlinks into the
  stock Happy-Hare install** — unmodified. Only the *user template* files are edited, and only their
  **values**: `mmu_parameters.cfg`, `mmu_hardware.cfg`, `mmu_macro_vars.cfg` (`_MMU_*_VARS`), and the
  boilerplate `T0`/`T1` tool macros HH's own template tells you to define. There are **no custom MMU
  macros**. The filament-change purge behaviour is stock HH `_MMU_PURGE`, analysed (not modified) in
  [docs/mmu_purge_volume.md](mmu_purge_volume.md).
- **`test_speed.cfg`** (`[include macros/calibration/test_speed.cfg]`) is a **Klippain-bundled**
  macro (Andrew Ellis' `TEST_SPEED`); `overrides.cfg` only enables it.
- **`[autotune_tmc]`, `[input_shaper]`, `[shaketune]`, PID blocks** in `overrides.cfg` are
  third-party plugin config / calibration *values*, not macros.

## See also
- [docs/bed_fans_control.md](bed_fans_control.md) — full bed-fan design of record.
- [docs/thermal_expansion.md](thermal_expansion.md) — thermal-expansion math, tuning, re-seeding.
- [docs/mmu_purge_volume.md](mmu_purge_volume.md) — how stock HH computes toolchange purge.
- [CLAUDE.md](../CLAUDE.md) — repo layout, modes, and deploy workflow.
