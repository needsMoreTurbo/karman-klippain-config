# NightOwl Build — TODO

Captured from the Todoist project **NightOwl Build** on 2026-07-08.
Updated 2026-07-11 after the MMU bring-up + toolhead/endstop rewire session.

## ✅ Recently completed (this session)
- Enabled Happy Hare MMU for Klippain (finalized the install: includes, save_variables merge).
- Fixed the gear-0 UART pin (Rabbit Burrow routes it to `gpio11`, not the ERB def's `gpio20`).
- Both gear steppers moving, directions correct, gates 0/1 mapped (gate 1 on the selector driver).
- Gear rotation distance calibrated per gate (`[22.3243, 22.4819]`).
- All 7 MMU switches wired + tested (pre-gate 0/1, post-gear 0/1, gate, sync tension/compression); D2F NC-terminal rework sorted; polarity inverted (`^!`).
- TurtleNeck dual-switch sync feedback configured (stand-in until the proportional PSF arrives).
- Filamatrix + beefy depressor installed; pre/post-extruder filament switches wired to the Nitehawk.
- BTT SFS v2 wired to the Leviathan (runout + motion).

## Filamatrix
- [x] wire sensors to nitehawk (pre/post-extruder switches → PB0 / PB1)
- [x] install toolhead
- [x] install filamatrix + beefy depressor
- [ ] install bumper

## NightOwl exterior wiring
- [ ] short term, setup dedicated 24v power brick (variable voltage unit)
- [ ] print adapters for microfit and usb ports (hex inserts)
- [ ] order usb port / cable for hex insert
- [ ] cut and wire barrel jack connector
- [ ] wire microfit wire internally to the printer

## Blobifier
- [ ] Assemble blobifier
- [ ] Wire up servo + bucket switch to Leviathan — **ports identified:** servo → EXT header `PF5` (+5V/GND from EXT), bucket switch → free endstop port `PC3` (Z is Beacon)
- [ ] Determine shim height required and print it

## Nozzle brush
- [ ] Fill with RTV and let cure
- [ ] Assemble unit
- [ ] Install in printer

## NightOwl internals
- [x] connect endstops and test them in klipper (all 7 switches)
- [x] connect extruders and test them in klipper
- [ ] plumb the ptfe lines (gate → extruder) — needed before bowden calibration / full loads

## Filament sensor (BTT SFS v2)
- [x] create extension cable / wire to Leviathan (PC0 runout, PC1 motion)
- [ ] configure in klipper (see config section below)

## Klipper / config changes pending (from the rewire)
- [ ] **X endstop relocation:** override `[stepper_x] endstop_pin: ^toolhead:PROBE_INPUT` (PC15 on Nitehawk); free PC1 for SFS motion — must be one atomic change with the SFS motion sensor
- [ ] **Recalibrate `position_endstop`** for X (new toolhead mount) and Y (new location, still PC2) — home carefully, watch homing direction (crash risk on X)
- [ ] **SFS v2 config:** `[filament_switch_sensor]` on PC0 + `[filament_motion_sensor]` on PC1; decide role and gate it OFF during MMU moves to avoid false runouts (Happy Hare interaction)
- [ ] **Verify PC15 (Nitehawk HV probe port)** works as a mechanical endstop via `QUERY_ENDSTOPS`
- [ ] **Pre/post-extruder sensors in HH:** `extruder_switch_pin: ^toolhead:MCU_ENDSTOP_X` (PB0), `toolhead_switch_pin: ^toolhead:MCU_ENDSTOP_Y` (PB1); check polarity via `MMU_SENSORS`
- [ ] **Enable `extruder_homing_endstop: extruder`** now that the extruder-entry sensor exists (unblocks auto bowden + toolhead calibration)

## Happy Hare — calibration & tuning
- [ ] Bowden length calibration (`MMU_CALIBRATE_BOWDEN`) — now doable automatically via the extruder sensor once PTFE is plumbed
- [ ] Toolhead calibration (`MMU_CALIBRATE_TOOLHEAD`) — needs the post-extruder/toolhead sensor
- [ ] Filament cutting (Filamatrix) configuration — retract most of the way, cut the tip, retract
- [ ] Blobifier configuration — servo control, bucket switch, bucket shake
- [ ] Filament change tuning (retraction amounts, blob tuning, etc.)

## Pin reference (new peripherals)
| Device | MCU | Pin |
|---|---|---|
| SFS v2 runout | Leviathan | PC0 (`RUNOUT_SENSOR`) |
| SFS v2 motion | Leviathan | PC1 (was X endstop) |
| Y endstop | Leviathan | PC2 (unchanged) |
| X endstop (relocated) | Nitehawk | PC15 (`PROBE_INPUT` / HV) |
| Pre-extruder switch | Nitehawk | PB0 (`MCU_ENDSTOP_X`) |
| Post-extruder switch | Nitehawk | PB1 (`MCU_ENDSTOP_Y`) |
| Blobifier servo (planned) | Leviathan | PF5 (EXT_7) |
| Blobifier bucket switch (planned) | Leviathan | PC3 (Z endstop, free) |
