# Nozzle thermal expansion compensation

Compensates for the nozzle growing longer as the hotend heats: the true
nozzle-to-bed gap at print temperature is smaller than at the low temperature used
for Beacon **contact** Z establishment. A matching `SET_GCODE_OFFSET Z_ADJUST` is
applied at print start and removed at print end.

Adapted from [YanceyA/BeaconPrinterTools — Thermal Expansion Compensation](https://github.com/YanceyA/BeaconPrinterTools/blob/main/Tools/Thermal_Expansion_Compensation/Thermal_expansion_compensation.md).

## How it's wired in

- **`thermal_expansion.cfg`** (repo root, `[include]`d from `overrides.cfg`) holds the
  macros: `BEACON_VARS` (config), `_BEACON_INIT` (resets applied offset on restart),
  the runtime apply/remove pair, and the calibration macros.
- **Klippain hooks:** the `"nozzle_expansion"` action is registered in both
  `variable_startprint_actions` (after `extruder_heating`, so `extruder.target` is the
  real print temp and `Z_ADJUST` stacks on the probe/material offset) and
  `variable_endprint_actions`, in the `overrides.cfg` `_USER_VARIABLES` block. Those map
  to `_START_PRINT_ACTION_NOZZLE_EXPANSION` / `_END_PRINT_ACTION_NOZZLE_EXPANSION`.

## The math

```
Z_ADJUST = multiplier * (extruder.target - calibration_temp) * (coefficient / 100)
```
with `calibration_temp = 150` and `multiplier = 1.0` (`BEACON_VARS`). The runtime apply
is self-correcting — it backs out the previously-applied offset before applying the new
one — and `_BEACON_INIT` re-zeros the saved applied offset on every `FIRMWARE_RESTART`.

## Tuned value for Karman

```
nozzle_expansion_coefficient = 0.055000   # ~0.055 mm growth over 150->250 °C
nozzle_expansion_applied_offset = 0        # runtime-managed; reset on restart
```

`0.055` = 0.00055 mm/°C. Example: a 250 °C print → `(250-150) * 0.055/100 = 0.055 mm`.

### Re-seeding after a reflash

`save_variables.cfg` is gitignored and runtime-written, so this value does **not**
travel via git. If the printer's `save_variables.cfg` is wiped, re-seed it on the
console (idle printer):

```
SAVE_VARIABLE VARIABLE=nozzle_expansion_coefficient VALUE=0.055
```

## Re-running calibration on-machine (optional)

`BEACON_CALIBRATE_NOZZLE_TEMP_OFFSET` probes at 250 °C and settles the mechanics with
`beacon_poke`. Before running it:

- Uncomment / set `contact_max_hotend_temperature` in the `overrides.cfg` `[beacon]`
  block (must exceed 250 to allow contact probing that hot).
- Confirm `beacon_poke` and `beacon.home_z_hop` exist in the installed Beacon plugin
  version. The runtime apply/remove path uses neither.
