# NightOwl Build — TODO

Captured from the Todoist project **NightOwl Build** on 2026-07-08.
Updated 2026-07-14 after toolhead calibration, SFS removal, and first working tool changes.

## ▶ Next up (in order)
_Goal: get Karman printing 2-color again with **tip forming** (cutter deferred — it's blocked on the depressor install and isn't required to print)._
1. **Slicer configuration for Happy Hare** — toolchange g-code, wipe tower OFF, `force_purge_standalone: 1`, per-gate filament profiles. See the *Slicer configuration* section + HH wiki.
2. **Purge + park position** — give the toolchange a real XY (park positions are still `-999`); purge into the back-left bin, wipe on the existing brush. See *Happy Hare — calibration & tuning*.
3. 🎯 **First 2-color test print** — tip forming only, slow is fine. Validates load → tip form → purge → wipe → resume.
4. **Filamatrix cutter** (after depressor installed) — cut geometry + enable `_MMU_CUT_TIP`. Blocked; not needed for #3.

**Watch item:** toolhead extruder `run_current` is only **0.45 A** (Klippain default) — too weak to reliably stall against the nozzle (broke auto toolhead cal) and a likely purge-slip risk. Bump toward ~70–80% of the motor's rating if slip recurs. (Need the toolhead motor's rated current.)

## 🗺 High-level roadmap (priority order)
_The big-picture sequence — reference this when re-prioritizing. Detailed tasks live in the sections below._

1. **Finish Happy Hare setup + calibration for NightOwl** — cutter (front-left), purge (back-left bin), wipe (existing brush). Goal: **printing again**, even if slow.
2. **Slicer configuration for Happy Hare** — toolchange g-code, wipe tower off, bed exclusions, etc.
3. **Reprint** blobifier + brush parts as needed.
4. **New brush** — install + configure, with park on the nozzle pad.
5. **Blobifier** — reassemble, wire, get it working (correctness over speed for now).
6. **Finalize NightOwl position** — relocate closer to the filament-load side; wire to printer 24 V via microfit; **re-run bowden cal** for the shorter run.
7. **Optimize the toolchange sequence:**
   - retract → move to cutter → cut → fast retract while fast-moving to blobifier → load + execute blobifier → shake bin → wipe nozzle → return to print.
   - tune purge amount (accounting for the pre-cut retraction).
8. **Spoolman integration.**

## ✅ Recently completed

### 2026-07-14 — toolhead calibration, SFS removal, working tool changes
- **Removed the BTT SFS v2** (encoder). It sat downstream of the sync-feedback sensor and its wheel drag was corrupting the tension signal + toolhead-path measurements. Running **encoderless** now (PC0/PC1 free).
- **FlowGuard still active, encoderless** — the tension-based path runs off the **TurtleNeck** sync-feedback switches (`flowguard_enabled: 1`); only the encoder path is off. (Corrected an earlier wrong note that said FlowGuard needed an encoder.)
- **Toolhead calibrated** (clean + dirty). Auto-cal (`MMU_CALIBRATE_TOOLHEAD`) proved unreliable due to **0.45 A extruder slip**, so values were **measured manually with a filament probe**: `extruder_to_nozzle 94.5`, `sensor_to_nozzle 85`, `entry_to_extruder 13`, `residual 5`. Also raised `toolhead_homing_max 40→60`.
- **Cut geometry measured** (`blade_pos 69`, `retract_length 64`) — staged but inactive (`form_tip_macro` still `_MMU_FORM_TIP`).
- **Cooling-tube tuned for Rapido V2 UHF + melt-zone extender** (`cooling_tube_position 42`, `length 10`). Large residual (~38 initially) traced to the UHF's long melt zone, then dialed to 5.
- **Tool changes `T0`/`T1` working.** Diagnosed a "purge does nothing" as the over-large residual under-loading the nozzle.
- Wrote `docs/mmu_purge_volume.md` (how purge volume/length is computed).

### 2026-07-13 — encoder calibration + gear current
- Diagnosed the gate-1 stall during encoder cal as **mechanical**, not electrical: both gears confirmed identical (`0.7 A`, spreadcycle) via `DUMP_TMC`.
- Bumped both gear `run_current` 0.7 → **0.8 A** (80% of the 1.0 A TriangleLab NEMA14s), set explicitly on both drivers — margin for the long preliminary bowden.
- Encoder (BTT SFS v2 as `[mmu_encoder]`) calibrated on both gates: resolution **~1.626**, gates agree to **0.07%** — confirms reliable reads regardless of driving gate.
- Both gates **`MMU_LOAD` / `MMU_EJECT` verified** end-to-end.

### 2026-07-11 — MMU bring-up + toolhead/endstop rewire
- Enabled Happy Hare MMU for Klippain (finalized the install: includes, save_variables merge).
- Fixed the gear-0 UART pin (Rabbit Burrow routes it to `gpio11`, not the ERB def's `gpio20`).
- Both gear steppers moving, directions correct, gates 0/1 mapped (gate 1 on the selector driver).
- Gear rotation distance calibrated per gate (`[22.3243, 22.4819]`).
- All 7 MMU switches wired + tested (pre-gate 0/1, post-gear 0/1, gate, sync tension/compression); D2F NC-terminal rework sorted; polarity inverted (`^!`).
- TurtleNeck dual-switch sync feedback configured (stand-in until the proportional PSF arrives).
- Filamatrix + beefy depressor installed; pre/post-extruder filament switches wired to the Nitehawk.
- BTT SFS v2 wired to the Leviathan (runout + motion).

## Filamatrix
### Note: the cutter and depressor make contact at x = 17 mm, y = 352 mm
### Note: the depressor makes contact with the toolhead at x = 10, y = 303 - 345 mm (makes contact with cutter arm backside, front side at y = 359 mm)
- [x] wire sensors to nitehawk (pre/post-extruder switches → PB0 / PB1)
- [x] install toolhead
- [x] install filamatrix
- [ ] install beefy depressor [front left side of bed, conservative placement to avoid clash and enable the setup and config of blobifier]

## NightOwl exterior wiring
- [x] short term, setup dedicated 24v power brick (variable voltage unit)
- [ ] print adapters for microfit and keystone adapters (hex inserts)
- [x] order usb port / cable for hex insert
- [ ] cut and wire barrel jack connector
- [ ] wire microfit wire internally to the printer

## Blobifier
- [ ] Assemble blobifier
- [ ] Wire up servo + bucket switch to Leviathan and buck converter — **ports identified:** servo → EXT header `PF5` (+5V/GND from EXT), bucket switch → free endstop port `PC3` (Z is Beacon)
- [x] Determine shim height required and print it
- [ ] Adjust SB shaker mount for shimmed servo height (shim height 5.5mm)
- [ ] Reprint shaker arm 4 mm taller
- [ ] Print wider bed plate version of the mount
- [ ] Print shim 1 mm shorter
- [ ] Install and wire up buck converter for servo power (5V)


## Nozzle brush
### Note: The brush y position is -2 mm from max position, x position right hand side of brush is at 87 mm, left is 53 mm, 34 mm wide.
## Note: nozzle rest position is at x = 44 mm, same y as brush
- [x] Fill with RTV and let cure
- [x] Assemble unit
- [x] Install in printer
- [ ] Configure brush position in klipper / happy-hare (position in notes above)
- [ ] Configure nozzle rest position in klipper / happy-hare (position in notes above)
- [ ] Test brush operation
- [ ] Test nozzle rest operation
- [ ] Reprint vertical mount (no change, broke the first one)

## NightOwl internals
- [x] connect endstops and test them in klipper (all 7 switches)
- [x] connect extruders and test them in klipper
- [x] plumb the ptfe lines (gate → extruder) — needed before bowden calibration / full loads
- [ ] relocate NightOwl to its permanent home (closer to the filament-load side) — pairs with the re-plumb + bowden re-cal below and the microfit 24V wiring
- [ ] re-plumb the ptfe and recalibrate the bowden lengths (MMU_CALIBRATE_BOWDEN) [only for final installation once everything works and there is a good location for the nightowl]

## Filament sensor (BTT SFS v2) — REMOVED
- [x] ~~create extension cable / wire to Leviathan (PC0 runout, PC1 motion)~~
- [x] ~~configure in klipper as `[mmu_encoder]` + `[filament_switch_sensor]`~~
- **Removed 2026-07-14** — drag corrupted the sync-feedback signal. Config commented out (not deleted); PC0/PC1 free. Re-add later **upstream** of the sync-feedback sensor after MMU relocation.

## Klipper / config changes pending (from the rewire)
- [x] **X endstop relocation:** override `[stepper_x] endstop_pin: ^toolhead:PROBE_INPUT` (PC15 on Nitehawk); free PC1 for SFS motion — must be one atomic change with the SFS motion sensor
- [x] **Recalibrate `position_endstop`** for X (new toolhead mount) and Y (new location, still PC2) — home carefully, watch homing direction (crash risk on X)
- [x] **SFS v2 config:** `[filament_switch_sensor]` on PC0 + `[filament_motion_sensor]` on PC1; decide role and gate it OFF during MMU moves to avoid false runouts (Happy Hare interaction)
- [x] **Verify PC15 (Nitehawk HV probe port)** works as a mechanical endstop via `QUERY_ENDSTOPS`
- [x] **Pre/post-extruder sensors in HH:** `extruder_switch_pin: ^toolhead:MCU_ENDSTOP_X` (PB0), `toolhead_switch_pin: ^toolhead:MCU_ENDSTOP_Y` (PB1); check polarity via `MMU_SENSORS`
- [x] **Enable `extruder_homing_endstop: extruder`** now that the extruder-entry sensor exists (unblocks auto bowden + toolhead calibration)

## Happy Hare — calibration & tuning
- [x] Gear rotation distance calibration (both gates); loads/ejects verified
- [x] Bowden length calibration (`MMU_CALIBRATE_BOWDEN`) — **preliminary** long run; re-do when relocated (see NightOwl internals)
- [x] **Toolhead calibration** — done clean+dirty; auto-cal unreliable (0.45 A extruder slip) so measured manually. Values in `mmu_parameters.cfg` 238–240 + `residual 5`.
- [x] **Test tool changes** (`T0` / `T1`) — both gates swap correctly with tip forming.
- [x] **FlowGuard** — active encoderless via the TurtleNeck tension switches (`flowguard_enabled: 1`). Encoder path (`flowguard_encoder_mode`) stays 0. Tune `flowguard_max_relief` (currently 40) if false trips.
- [ ] **Purge + park position** — set a real toolchange park XY (`_MMU_SEQUENCE_VARS` park positions are still `-999`); purge into the back-left bin. `MMU_TEST_PURGE` works; volume math in `docs/mmu_purge_volume.md`.
- [ ] **Filament cutting (Filamatrix)** — geometry **measured** (`blade_pos 69`, `retract_length 64`); still need `pin_loc_xy` / `pin_loc_compressed_xy` / `pin_park_dist` / `cutting_axis` (back-edge, high-Y) — **blocked on depressor install**. Then enable by setting `form_tip_macro: _MMU_CUT_TIP`.
- [ ] **Nozzle wipe** — configure the post-toolchange wipe on the **existing** brush (the new brush comes later)
- [ ] Blobifier configuration — servo control, bucket switch, bucket shake
- [ ] Filament change tuning (retraction amounts, blob tuning, etc.)
- [ ] **Collision avoidance** — *no Klipper obstacle model exists; enforced by you:*
  - [ ] **Slicer bed exclusion** — shrink usable Y and/or notch a custom bed polygon so no toolpath reaches the back-edge depressor; also notch the front-left keep-out corner (x=10, y=17)
  - [ ] **Vet all macro-driven positions** (homing, purge, nozzle brush, prime, park, START_PRINT) to clear the depressor + XY-tensioner zones
- [ ] 🎯 **First multi-material print** — get Karman printing 2-color again (slow is fine); validates the full load → cut → purge → wipe → resume chain

## Slicer configuration (Happy Hare)
- [ ] Disable slicer tip-forming / ramming; let HH form + cut the tip (`force_form_tip_standalone`)
- [ ] Set up the MMU toolchange g-code (`Tx` mapping) per the HH slicer wiki
- [ ] Disable the wipe/prime tower (HH handles purge + wipe)
- [ ] Apply bed-shape exclusions (see Collision avoidance) so no toolpath enters the depressor / tensioner zones
- [ ] Define per-gate filament profiles + material/color map
- [ ] Slice + run a 2-color test model end-to-end

## Toolchange optimization (later)
- [ ] Implement the fast sequence: retract → cutter → cut → fast-retract while moving to blobifier → blobifier purge → shake bin → wipe → resume
- [ ] Tune purge volume — account for the pre-cut retraction so we don't over/under-purge
- [ ] Tune sync-feedback (TurtleNeck) behavior under real prints

## Spoolman integration (later)
- [ ] Install / enable Spoolman + Moonraker integration
- [ ] Map HH gates → Spoolman spools
- [ ] Verify filament usage tracking across toolchanges

## Pin reference (new peripherals)
| Device | MCU | Pin |
|---|---|---|
| ~~SFS v2 runout~~ (removed) | Leviathan | PC0 (`RUNOUT_SENSOR`) — **free** |
| ~~SFS v2 motion~~ (removed) | Leviathan | PC1 (was X endstop) — **free** |
| Y endstop | Leviathan | PC2 (unchanged) |
| X endstop (relocated) | Nitehawk | PC15 (`PROBE_INPUT` / HV) |
| Pre-extruder switch | Nitehawk | PB0 (`MCU_ENDSTOP_X`) |
| Post-extruder switch | Nitehawk | PB1 (`MCU_ENDSTOP_Y`) |
| Blobifier servo (planned) | Leviathan | PF5 (EXT_7) |
| Blobifier bucket switch (planned) | Leviathan | PC3 (Z endstop, free) |
