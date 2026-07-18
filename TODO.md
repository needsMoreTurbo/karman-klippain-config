# NightOwl Build — TODO

Captured from the Todoist project **NightOwl Build** on 2026-07-08.
Updated 2026-07-14 (late) after the 🎉 **first 2-color print** and Filamatrix cutter bring-up.

## ▶ Next up (in order)
_Goal: validate the cutter end-to-end, then a 2-color print WITH cutting. Details in TODAY.md._
1. **Confirmation cut at `residual 25`** — `T0` → `MMU_EJECT`, inspect at the gate; expect `Retracting filament 30.0mm` and a **flat** face. Pointy → set residual 30.
2. **Real `T0`↔`T1` swaps with the cutter** — verify fragment accounting comes out small-positive (net-based in real flow) and state stays in sync.
3. **Walk `retract_length` up** (55 → 58 → 62) while cuts stay flat — less sliver per cut.
4. 🎯 **2-color print with cutting** — watch swap blobs (should shrink with residual fixed), tower transitions (may need more flushing for the fragment), FlowGuard.
5. **Commit the batch** via SSH (cutter config, residual/ooze, slicer docs, moonraker, TODO/TODAY — many files pending).

**Watch item:** toolhead extruder `run_current` = **0.45 A** (Klippain default). The cut-accounting anomaly was cleared (test-mode arithmetic, NOT slip), but the auto toolhead-cal push-to-stall failures still implicate it. Bump to ~70–80% of motor rating if slip symptoms appear in prints (need the motor's rated current).

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

### 2026-07-14 (evening) — 🎉 first 2-color print + cutter bring-up
- **First 2-color print succeeded** (Option A: slicer wipe tower owns purge, tip forming). 7 toolchanges, purge deferral to slicer verified in mmu.log.
- **Slicer fully configured** — complete OrcaSlicer checklist in `docs/mmu_slicer_setup.md` (start/end g-code, SEMM zeroing, extruder-tab toolchange retraction, flushing multiplier guidance). Found the **chamber-soak trap**: Orca's "activate temperature control" toggle doesn't zero `[chamber_temperature]`; nonzero blocks START_PRINT up to 15 min (0.0 tolerance + noisy sensor) — set chamber temp 0 in every MMU filament profile.
- **Depressor reinstalled front-left + measured**: contact 17,36 → compressed 0.5,36 (X-axis cut). **Cutter enabled** (`form_tip_macro: _MMU_CUT_TIP`); flat cut verified.
- **Root-caused "formed tip" cut failures + per-swap tower blob to the same bug**: `toolhead_residual_filament` far too low (5). The cut macro parks the tip at `retract_length` *only if residual is true*; at 5 vs a real ~35 the tip sat ~30 mm above the blade (cut air) and loads over-advanced ~30 mm (blob out the nozzle). Set 35 (cut verified flat) → refined to **25** by hand calc (confirmation cut pending). Also `toolhead_ooze_reduction 0→2`, `retract_length 64→55` (margin during testing).
- **Root-caused the `MMU_EJECT` failure after test cuts**: `MMU_TEST_FORM_TIP` final-ejects into the PTFE and hard-stamps state UNLOADED (mmu.py:4195) → a following `MMU_EJECT` takes the short gate-release branch and errors. Its "−68mm remaining" is test-mode cumulative-travel arithmetic — **not motor slip**. New test workflow: from loaded, `MMU_EJECT` alone (cut + full unload + gate release); `MMU_RECOVER` for any desync.
- Staged **Option B park/purge position** `0, 358` (back-left bin) as a one-line comment swap in `mmu_macro_vars.cfg`; added `[file_manager] default_metadata_parser_timeout: 120`; noted `enable_toolchange_next_pos: True` already on.
- Captured the **permanent front-left keep-out** (cutter arm vs. XY idler, ~x<22,y<40 incl. depressor) in configs + docs.

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
### Depressor reinstalled FRONT-LEFT 2026-07-14. Lever first contact measured: **x = 17, y = 36** (set as `pin_loc_xy`).
- [x] wire sensors to nitehawk (pre/post-extruder switches → PB0 / PB1)
- [x] install toolhead
- [x] install filamatrix
- [x] install beefy depressor — front-left (keeps the back-left corner free for the purge bin @ 0,358)
- [x] measure depressor contact point → 17, 36 (staged in `mmu_macro_vars.cfg`)
- [x] measure fully-compressed point → 0.5, 36 (dry-run verified)
- [x] enable cutter — `form_tip_macro: _MMU_CUT_TIP` set 2026-07-14
- [x] first flat cut verified (at `residual 35`); residual refined to 25 by hand calc
- [ ] **Confirmation cut at `residual 25`** — `T0` → `MMU_EJECT` (cut + full unload + gate release), inspect the flat face **at the NightOwl**, reinsert. Expect `Retracting filament 30.0mm prior to cut`. Pointy face → residual 30.
  ⚠️ Never use `MMU_TEST_FORM_TIP` here: final-ejects into the PTFE + hard-stamps state UNLOADED (mmu.py:4195) → next `MMU_EJECT` errors. Desync fix: `MMU_RECOVER`.
- [ ] **Walk `retract_length` up** 55 → 58 → 62 while cuts stay flat (smaller sliver = less purge)
- [ ] Real `T0`↔`T1` swap — watch the *real* fragment accounting (net-position based, should be a small positive number)
- [ ] Watch tower flushing volumes with the cutter (cut fragment adds to what must purge)

## NightOwl exterior wiring
- [x] short term, setup dedicated 24v power brick (variable voltage unit)
- [ ] print adapters for microfit and keystone adapters (hex inserts)
- [x] order usb port / cable for hex insert
- [ ] cut and wire barrel jack connector
- [ ] wire microfit wire internally to the printer

## Blobifier
### Note: The bucket was reassembled and the optimum engagement point for the shaker arm is X = 3.0 mm and Z = 3.0 mm (SB is cradled within the shaker arm just right!)
- [ ] Assemble blobifier servo assembly - post-rebuild from new printed parts, hot glue the connect in place 
- [x] Assemble bucket - post-rebuild from new printed parts
- [ ] Wire up servo + bucket switch to Leviathan and buck converter — **ports identified:** servo → EXT header `PF5` (+5V/GND from EXT), bucket switch → free endstop port `PC3` (Z is Beacon)
- [x] Determine shim height required and print it
- [x] Adjust SB shaker mount for shimmed servo height (shim height 5.5mm)
- [x] Reprint shaker arm 4 mm taller
- [ ] Print wider bed plate version of the mount (5 mm wider)
- [ ] Print shim 1 mm shorter
- [ ] Reprint the base due to damage to the existing one (cracked attachment last time, consider making the design more robust)
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
- [ ] replace mirrored latch with althernative versions that I printed (existing version is coming unlatched and is not reliable)
- [ ] properly adjust the extruder idler tension (didn't actually follow the instructions, just tightened it down some arbritray amount)
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
- [ ] **Switch purging to Option B (HH-owned, back-left bin)** — currently **Option A** (slicer wipe tower owns purge). Full procedure in `docs/mmu_slicer_setup.md` → *Switching to Option B*. All four are required together:
  - [ ] **Update park position** — in `mmu_macro_vars.cfg`, swap which `variable_park_toolchange` line is commented: `-999,-999,1,5,2` (A) → **`0, 358, 1, 5, 2`** (B, back-left bin). Both lines already staged in-file.
  - [ ] `force_purge_standalone: 1` in `mmu_parameters.cfg`
  - [ ] OrcaSlicer wipe tower **OFF**
  - [ ] Feed the purge matrix (`MMU_START_SETUP ... PURGE_VOLUMES=!purge_volumes!` before `START_PRINT`) — else purge collapses to residual-only (~5mm). See `docs/mmu_purge_volume.md`.
  - [x] 0,358 clearance verified — depressor reinstalled **front-left** (17,36), so the back-left bin corner is clear
- [x] **Filament cutting (Filamatrix)** — CONFIGURED + ENABLED 2026-07-14: pin 17,36 → compressed 0.5,36 (X-axis cut), `blade_pos 69`, `retract_length 55` (testing margin; walk toward 62), `residual 25`, `form_tip_macro: _MMU_CUT_TIP`. Flat cut verified at residual 35; 25-confirmation + swap test pending (see Filamatrix section).
- [ ] **Nozzle wipe** — configure the post-toolchange wipe on the **existing** brush (the new brush comes later)
- [ ] Blobifier configuration — servo control, bucket switch, bucket shake
- [ ] Filament change tuning (retraction amounts, blob tuning, etc.)
- [ ] **Collision avoidance** — *no Klipper obstacle model exists; enforced by you:*
  - ⚠️ **FRONT-LEFT KEEP-OUT IS PERMANENT (~x<10, y<17, all Z):** the **Filamatrix cutter arm on the toolhead strikes the front-left XY idler**. This is toolhead geometry — it applies to **every** move (print, travel, homing, park, purge, brush) and is **independent of the depressor** (still applies with the depressor removed).
  - [ ] **Slicer bed exclusion** — notch a custom bed polygon so no toolpath/travel enters the front-left keep-out; the depressor (front-left, lever contact at 17,36) extends that zone to roughly x<22, y<40
  - [ ] **Vet all macro-driven positions** (homing, purge, nozzle brush, prime, park, START_PRINT, QGL/tilt, Beacon contact) clear the front-left keep-out
- [x] 🎯 **First multi-material print** — DONE 2026-07-14 (tip forming, Option A slicer purge; 7 toolchanges clean)
- [ ] 🎯 **First multi-material print WITH cutter** — same test, cutting live; validates cut → unload → load → purge chain + fragment purging

## Slicer configuration (Happy Hare)
_Done 2026-07-14 — full OrcaSlicer checklist lives in `docs/mmu_slicer_setup.md` (the authoritative record)._
- [x] Slicer tip-forming / ramming disabled; SEMM + extruder-tab toolchange retraction zeroed
- [x] MMU toolchange g-code (`T[next_extruder]`), start/end/layer g-code (Klippain-wrapped, no `MMU_END`)
- [x] Wipe/prime tower ON (Option A — slicer owns purge); flushing-volume multiplier guidance recorded
- [x] Per-gate filament slots + colors/temps; chamber temp **0** in MMU filament profiles (chamber-soak trap)
- [x] Slice + run a 2-color test model end-to-end 🎉
- [ ] Bed-shape exclusions (see Collision avoidance) — front-left keep-out not yet notched into the bed polygon

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
