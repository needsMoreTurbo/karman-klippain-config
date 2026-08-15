# NightOwl Build — TODO

Captured from the Todoist project **NightOwl Build** on 2026-07-08.
Updated 2026-07-25 — 🎉 **MMU is functionally complete**: cutter + Blobifier + wipe all validated by
a 2-colour print (2026-07-24). Remaining work is tuning, safety loose ends, and relocation.

## ▶ Next up (in order)
1. **Confirm the OrcaSlicer wipe tower is OFF** — Process settings → Multimaterial → *Prime tower →
   Enable* (uncheck). With `force_purge_standalone: 1` live, leaving it on double-purges every swap.
2. **Bed-mesh rear-left jog check** — the one path-safety item never confirmed by hand
   (jog to 20,330,z3 then 10,330,z3; shrink the mesh Y range if tight).
3. **Tune `flowguard_max_relief`** — still at the switch-era 40; walk toward ~15 now the PSF is
   calibrated. Do *after* a clean print so false-trip debugging isn't confounded.
4. **Commit + push** the pending batch (workflow tooling, decisions.md, runbooks, hooks).
5. **Open `/hooks` once** (or restart the session) to activate the new hooks and skills — they
   were added after this session started, so the settings watcher hasn't picked them up.
6. Then the next big objective: **relocate the NightOwl** (roadmap #6) — worth a `/brief`.

_Resolved watch item: the 0.45 A extruder current is fine in practice — no skipping observed in real prints/purges. The NightOwl "skipping" was the gate-0 mirrored nightwatch latch not holding (fixed by a 99% reprint; see NightOwl internals for gate 1)._

## 🗺 High-level roadmap (priority order)
_The big-picture sequence — reference this when re-prioritizing. Detailed tasks live in the sections below._

1. [x] **Finish Happy Hare setup + calibration for NightOwl** — cutter (**back-left**), purge (**Blobifier**), wipe (**new gantry brush**). Printing again ✓
2. [x] **Slicer configuration for Happy Hare** — toolchange g-code, purge ownership, filament slots. _(Bed exclusions still open — see Collision avoidance.)_
3. [x] **Reprint** blobifier + brush parts as needed.
4. [x] **New brush** — installed + configured, with park on the nozzle rest.
5. [x] **Blobifier** — reassembled, wired, working and owning purge.
6. **Finalize NightOwl position** — relocate closer to the filament-load side; wire to printer 24 V via microfit; **re-run bowden cal** for the shorter run.  ← *next big one*
7. **Optimize the toolchange sequence:**
   - retract → move to cutter → cut → fast retract while fast-moving to blobifier → load + execute blobifier → shake bin → wipe nozzle → return to print.
   - tune purge amount (accounting for the pre-cut retraction).
8. **Spoolman integration.**

## Filamatrix
### CURRENT geometry (relocated BACK-LEFT 2026-07-17): contact **15, 341** → compressed **0, 341**, cut plane **z=15** (clears the shaker arm; enforced by `min_toolchange_z: 15`). Validated by real swaps post-rework.
- [x] wire sensors to nitehawk (pre/post-extruder switches → PB0 / PB1)
- [x] install toolhead · install filamatrix
- [x] ~~install depressor front-left; contact 17,36 → compressed 0.5,36~~ **superseded** — relocated back-left 2026-07-17, geometry above
- [x] enable cutter — `form_tip_macro: _MMU_CUT_TIP` set 2026-07-14
- [x] first flat cut verified (at `residual 35`); residual refined to 25 by hand calc
- [x] confirmation cut at `residual 25` ✓ (2026-07-15)
- [x] real `T0`↔`T1` swaps with the cutter ✓; 1-color print with start/end cuts ✓ *(pre-rework)*
- [x] cut re-validated at the back-left location ✓ (exercised by the post-rework blobifier swaps)
  ⚠️ Cut-test workflow reminder: from loaded, `MMU_EJECT` alone (cut + unload + gate release). Never `MMU_TEST_FORM_TIP` (strands tip in PTFE + hard-stamps UNLOADED → next `MMU_EJECT` errors). Desync fix: `MMU_RECOVER`.
- [ ] **Walk `retract_length` up** 55 → 58 → 62 while cuts stay flat (smaller sliver = less purge)
- [ ] Watch purge/flushing amounts with the cutter (cut fragment adds to what must purge)

## NightOwl exterior wiring
- [x] short term, setup dedicated 24v power brick (variable voltage unit)
- [ ] print adapters for microfit and keystone adapters (hex inserts)
- [x] order usb port / cable for hex insert
- [ ] cut and wire barrel jack connector
- [ ] wire microfit wire internally to the printer

## Blobifier
### Note: The bucket was reassembled and the optimum engagement point for the shaker arm is X = 3.0 mm and Z = 3.0 mm (SB is cradled within the shaker arm just right!)
- [x] Assemble blobifier servo assembly - post-rebuild from new printed parts, hot glue the connect in place 
- [x] Assemble bucket - post-rebuild from new printed parts
- [x] Wire up servo + bucket switch to Leviathan and buck converter
- [x] Determine shim height required and print it
- [x] Adjust SB shaker mount for shimmed servo height (shim height 5.5mm)
- [x] Reprint shaker arm 4 mm taller
- [x] Print wider bed plate version of the mount (5 mm wider)
- [x] Print shim 1 mm shorter
- [x] Reprint the base due to damage to the existing one (cracked attachment last time, consider making the design more robust)
- [x] Install and wire up buck converter for servo power (5V)
- [x] Install base and bucket assembly in printer
- [x] Test servo operation and bucket switch operation
- [x] Install servo arm and sliding tray
- [x] Test servo with tray attached
- [x] Update blobifier config in klipper / happy-hare
- [x] Test blobifier operation with tray attached
- [ ] **Wire dedicated 2nd ground to the Leviathan** — bucket-switch ground currently returns through the buck converter (works but noise-susceptible). Blocked on hardware: the base only fits a 4-pin JST, so a 5th conductor needs a base mod + reprint. Do together with a base revision (also: make the cracked attachment more robust).


## Nozzle brush
### As configured (authoritative — these are the live values): brush **x53–88** at **y_max**, centre 70.5 (`variable_brush_xyz: 70.5, 359, 1`); nozzle rest **x=45, y=359** (`park_pause` / `park_complete` / `SWAP`).
### Gantry-mounted ⇒ Z tracks the toolhead, so only the X slide seats/unseats the nozzle; approach y_max via the clear lanes (15<x<40 or x>95), never head-on.
- [x] Fill with RTV and let cure
- [x] Assemble unit
- [x] Install in printer
- [x] Configure brush position in klipper / happy-hare (position in notes above)
- [x] Configure nozzle rest position in klipper / happy-hare (position in notes above)
- [x] Test brush operation
- [x] Test nozzle rest operation
- [x] Reprint vertical mount (no change, broke the first one)

## NightOwl internals
- [x] connect endstops and test them in klipper (all 7 switches)
- [x] connect extruders and test them in klipper
- [x] plumb the ptfe lines (gate → extruder) — needed before bowden calibration / full loads
- [x] replace mirrored latch with althernative versions that I printed (existing version is coming unlatched and is not reliable) — gate 0 fixed with a **99%-scale** reprint
- [ ] *(optional)* print + replace the **gate-1** latch too — no failures yet, but measurements say ~**99.5% scale**; do preemptively if it starts slipping
- [x] properly adjust the extruder idler tension (didn't actually follow the instructions, just tightened it down some arbritray amount)
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
- [x] **FlowGuard** — active via the **PSF** proportional sync-feedback sensor (`flowguard_enabled: 1`); encoder path (`flowguard_encoder_mode`) stays 0 (encoderless). `flowguard_max_relief` still 40 → walk toward ~15 (Next up #3).
- [x] **Switch purging to HH-owned via BLOBIFIER** — *supersedes the old "Option B / `_MMU_PURGE` @ 0,358" plan*: Blobifier positions itself, so `park_toolchange` stays `-999,-999` (see `docs/decisions.md`).
  - [x] `purge_macro: BLOBIFIER` + `force_purge_standalone: 1` in `mmu_parameters.cfg`
  - [x] `variable_user_post_form_tip_extension: "BLOBIFIER_PARK"` + `restore_xy_pos: "next"`; staged `0,358` park comment retired
  - [ ] OrcaSlicer wipe tower **OFF** ← *confirm; required now that `force_purge_standalone: 1`, or you double-purge*
  - [x] Purge matrix fed via `MMU_START_SETUP ... PURGE_VOLUMES=!purge_volumes!` (verified in the machine start g-code)
- [x] **Filament cutting (Filamatrix)** — ENABLED; geometry now **back-left**: pin `15,341` → compressed `0,341` (X-axis cut) at **z15**, `blade_pos 69`, `retract_length 55` (walk toward 62), `residual 25`, `form_tip_macro: _MMU_CUT_TIP`. Flat cut + real swaps verified.
- [x] **Nozzle wipe** — post-toolchange wipe runs on the **new gantry brush** (x53–88, `brush_top: None`) via `BLOBIFIER_CLEAN`; tested.
- [x] **Blobifier configuration** — servo, bucket switch, tray, shake all configured and tested.
- [ ] Filament change tuning (retraction amounts, blob tuning, purge volumes under real prints)
- [ ] **Collision avoidance** — *no Klipper obstacle model exists; enforced by you:*
  - ⚠️ **FRONT-LEFT KEEP-OUT, PERMANENT (~x<10, y<17, all Z):** the Filamatrix **cutter arm strikes the front-left XY idler** — toolhead geometry, applies to every move.
  - ⚠️ **BACK-LEFT ZONE (x<~20, y>~335, below z15):** blobifier structures + relocated depressor. Enter only via the managed macros; manual jogs at low Z stay out.
  - ⚠️ **y_max FEATURE ROW** (tray x~2–17, shaker x4, rest x45, brush x53–88, all gantry/frame at y_max): approach in **+Y only through the clear lanes 15<x<40 or x>95**, then slide in X. `_KARMAN_PARK_MOVE` + retargeted CLEAN_NOZZLE handle this for parks/wipes.
  - [x] QGL (max y 275) + Y-homing (x≈345) verified clear from config
  - [ ] **Bed-mesh rear-left jog check** — jog nozzle to (20, 330, z3) then (10, 330, z3) and eyeball clearance to the depressor mount + blobifier base (mesh probing rows can reach nozzle y≈332 at low Z)
  - [ ] **Slicer bed exclusion** — notch the bed polygon: front-left idler corner + back-left blobifier/depressor zone
  - [ ] **Vet remaining macro positions** (prime line, Beacon contact, purge/clean during START_PRINT) against the new zones
- [x] 🎯 **First multi-material print** — DONE 2026-07-14 (tip forming, Option A slicer purge; 7 toolchanges clean)
- [x] 🎯 **Multi-material print WITH cutter + Blobifier** — DONE 2026-07-24. Validates the full chain: cut at z15 → unload → load → Blobifier purge → gantry-brush wipe → resume. Runbook: `docs/runbooks/done/blobifier-bringup.md`

## Slicer configuration (Happy Hare)
_Done 2026-07-14 — full OrcaSlicer checklist lives in `docs/mmu_slicer_setup.md` (the authoritative record)._
- [x] Slicer tip-forming / ramming disabled; SEMM + extruder-tab toolchange retraction zeroed
- [x] MMU toolchange g-code (`T[next_extruder]`), start/end/layer g-code (Klippain-wrapped, no `MMU_END`)
- [x] Wipe/prime tower ON (Option A — slicer owns purge); flushing-volume multiplier guidance recorded
- [x] Per-gate filament slots + colors/temps; chamber temp **0** in MMU filament profiles (chamber-soak trap)
- [x] Slice + run a 2-color test model end-to-end 🎉
- [ ] Bed-shape exclusions (see Collision avoidance) — front-left keep-out not yet notched into the bed polygon

## Pressure advance

- [x] ✅ **Install BDPressure E sensor for automatic PA calibration — DONE 2026-08-14.**
  PandaPi3D strain-gauge sensor at the groove mount, **connected by USB** (the original I2C plan
  was superseded — I2C structurally cannot carry the raw ADC stream, and an unanswered NAK shut
  the toolhead MCU down on every `G28`). **PA mode only — Beacon stays the probe.**
  The first unit was faulty (strain-gauge P+ lead open); the replacement works. Measured ABS PA is
  **0.032**, which replaced the inherited 0.0480 in `variables.cfg`. Two vendor bugs found and
  patched along the way (an event-length limit that discarded 78% of steps at 14.4 mm³/s, and an
  answer-selection routine that returned 0.076 for a sweep whose data crossed at 0.031).
  Physics model, measurement limits and calibration protocol: `docs/pa_physics.md`. Every sweep
  result: `physics/pa_sweeps.json`. Orca adaptive matrix: `physics/pa_law.json`.
  Open follow-ups are listed at the end of the runbook — none blocking.
  — runbook: `docs/runbooks/done/bdpressure-pa-sensor.md`
- [ ] **Standardise per-filament PA calibration (constant + adaptive)** — turn the one-off ABS
  characterisation into a repeatable procedure: a two-corner gate that decides whether adaptive PA
  earns its keep for a given filament, a constant PA at the outer-wall operating point if it
  doesn't, and the law-driven expansion to a full matrix if it does. Includes the refit helper
  Appendix B flags as missing, and validation on a real second filament.
  — runbook: `docs/runbooks/pa-calibration-sop.md`

## Miscellaneous
- [x] **Audit START_PRINT for no-op / hardware-stale steps** — ✅ done and **verified on hardware
  2026-08-02** (single-colour + 2-colour). First layer measurably better; no manual Z offset
  needed. — runbook: `docs/runbooks/done/start-print-audit.md`
- [x] **Fix: nozzle-expansion offset applied zero on every print but the first after a restart**
  — a stale `nozzle_expansion_applied_offset` cancelled the new offset exactly, and the console
  message reported the *target* rather than the delta actually issued, which hid it. Both fixed
  in `thermal_expansion.cfg`; see `docs/decisions.md` 2026-08-02.
- [ ] **END_PRINT `retract_filament` is now a complete no-op** — with `mmu_unload_on_end_print:
  False` the MMU branch is gated off and the plain-retract `elif` is unreachable
  (`klippain_mmu_enabled` is True). Decide whether END_PRINT should retract at all now that
  filament stays loaded in the UHF melt zone through cooldown. Same kind of audit as START_PRINT.
- [ ] **Reconsider "MMU profiles must send CHAMBER=0"** (`docs/decisions.md` 2026-07-14) — that rule
  was a workaround for `chamber_temp_tolerance: 0.0`, which is now 2.0. Keep setpoints ≤ ~55 °C.
- [ ] **Purge lengths are sized for a standard hotend, not the UHF** — runbook:
  `docs/runbooks/blobifier-purge-tuning.md` (Klipper-side fix via `purge_length_minimum`; acceptance
  is a clean colour change *on the part*). Do this AFTER the START_PRINT
  verification prints (changing it mid-verification would confound the result). Measured 2026-08-02
  on a `SWAP TOOL=0` (teal → black) that visibly failed to complete the colour change:

  ```
  BLOBIFIER: Swapped T1 > T0
  BLOBIFIER: Purging 36mm of filament
  ```

  Blobifier's formula (`mmu/addons/blobifier.cfg:378-391`):
  `purge_len = (pv[from][to] × purge_length_modifier) / 2.405 + extruder_filament_remaining + retracted_length + purge_length_addition`

  | Term | Value | Note |
  |---|---|---|
  | slicer `pv[1][0]` (T1→T0) | 41 mm³ | `PURGE_VOLUMES=0,218,41,0`; T0→T1 is 218 |
  | × `purge_length_modifier` 0.6 | 24.6 mm³ | |
  | ÷ 2.405 mm² | **10.2 mm** | ← the only part that actually flushes colour |
  | + residual (~24) + retract (2) | ≈ 36 mm | displacement only — pushes old colour to the tip |

  **The melt zone alone holds 25 mm ≈ 60 mm³**, so the swap delivered under half a melt-zone volume
  of fresh material. The slicer's 41 mm³ is the standard "going to a dark colour needs less"
  heuristic, sized for a ~10 mm melt zone — same class of error as `toolhead_residual_filament`
  (see `docs/decisions.md` 2026-07-17).

  Corollary: **`purge_length_minimum: 30` is effectively zero flush** (~4 mm after displacement).
  Knobs, in rough order of preference: raise the slicer flushing volume for →dark swaps; raise
  `purge_length_minimum` toward ~60–70; `purge_length_addition` (blobifier.cfg's own guidance:
  *"INCREASE when dark→light swaps are good but light→dark aren't"* — this is that case);
  `purge_length_modifier` 0.6 → higher. Supersedes the older "Tune purge volume" line under
  Toolchange optimization.

  For manual swaps meanwhile, bypass the matrix entirely: `BLOBIFIER_TEST PURGE_LENGTH=100`,
  repeated until the blob runs clean, **before** starting a print.

## Toolchange optimization (later)
- [ ] Implement the fast sequence: retract → cutter → cut → fast-retract while moving to blobifier → blobifier purge → shake bin → wipe → resume
- [ ] ~~Tune purge volume~~ — superseded by the purge-length task under **Miscellaneous**, which has
  the measured numbers from the 2026-08-02 teal→black swap failure
- [ ] Tune **PSF** sync-feedback behaviour under real prints (incl. `flowguard_max_relief`)

## Spoolman integration (later)
- [ ] Install / enable Spoolman + Moonraker integration
- [ ] Map HH gates → Spoolman spools
- [ ] Verify filament usage tracking across toolchanges

## Pin reference (new peripherals)
| Device | MCU | Pin |
|---|---|---|
| ~~SFS v2 runout~~ (removed) | Leviathan | PC0 (`RUNOUT_SENSOR`) — **free** |
| Blobifier bucket switch | Leviathan | PC1 (`MCU_STOP_X` → `BLOBIFIER_BUCKET`, NC→GND, was SFS motion) |
| Y endstop | Leviathan | PC2 (unchanged) |
| X endstop (relocated) | Nitehawk | PC15 (`PROBE_INPUT` / HV) |
| Pre-extruder switch | Nitehawk | PB0 (`MCU_ENDSTOP_X`) |
| Post-extruder switch | Nitehawk | PB1 (`MCU_ENDSTOP_Y`) |
| Blobifier servo | Leviathan | PC3 (`MCU_STOP_Z` → `BLOBIFIER_SERVO`, Z-STOP header; 5V from 24V buck) |
| ~~Blobifier servo (old plan)~~ | Leviathan | PF5 (EXT_7) — **free** |

---

# 📖 History — completed work

_Reference only; nothing below is actionable. Newest first. The durable **why** behind these
decisions lives in `docs/decisions.md`; per-objective execution records are in
`docs/runbooks/done/`._

## ✅ Recently completed

### 2026-08-02 — visualizer covers START_PRINT, and a silent under-reporting bug fixed
- **`start_print` scenario added** to `tools/visualize_toolchange.py`. START_PRINT motion was
  previously unchecked by any scenario, despite making **three** entries into the y_max feature row
  (`_CONDITIONAL_MOVE_TO_PURGE_BUCKET` in `clean` ×2 and `extruder_heating`). It simulates the real
  Klippain modules through the framework symlink, and skips itself with a clear message in a
  workstation clone where those symlinks dangle.
- **Result: clean, but with almost no margin.** All three bucket approaches cross y=350 at
  **x=17.1** — inside the 15<x<40 clear lane by 2.1 mm. Klippain's bucket move is a bare diagonal
  `G1 X Y` that does **not** route through `_KARMAN_PARK_MOVE`, so the lane rule is not enforced
  there, only observed. Worth remembering before anything moves `purge_bucket_xyz` or `home_xy_position`.
- **Fixed a bug that made the visualizer under-report** (`92ef3df`): the move regex accepted `-` but
  not `+`, so every `G1 X+35` was dropped. Nozzle wipes were simulated as a one-sided walk out to
  x=−139 and still passed, because segments that never happen cannot violate a zone. The four
  toolchange scenarios were unaffected (segment counts unchanged), but any wipe loop was blind.
- Found incidentally while auditing START_PRINT (`docs/runbooks/start-print-audit.md`); not part of
  that runbook's scope, and no printer config was changed.

### 2026-07-25 — Blobifier live, standalone-swap workflow, and session tooling
- **Blobifier fully live**: base/bucket installed, servo + switch tested, arm/tray fitted, geometry
  configured, and **purge ownership handed over** (`purge_macro: BLOBIFIER`,
  `force_purge_standalone: 1`, `BLOBIFIER_PARK` hook, `restore_xy_pos: "next"`). Real swaps verified.
- **Fixed the `-999` park-sentinel crash**: HH passes its "no move" sentinel to a
  `user_park_move_macro` **unfiltered** — `_KARMAN_PARK_MOVE` now handles it (was aborting every
  toolchange park with "Move out of range").
- **Standalone-swap workflow** (`docs/mmu_standalone_swap_plan.md`): `SWAP TOOL=n` parks on the rest
  *before* swapping so heat-up ooze lands in the RTV cup and HH's restore returns there; hotend now
  turns off after bench ops; idle timeout parks on the rest. Caught and fixed a guard bug that would
  have shut the hotend off mid-START_PRINT on **every** print.
- **Nozzle LEDs go white during purge** so colour change is visible (were red — purge runs in
  Klippain's `heating` LED state).
- **Session tooling**: `tools/visualize_toolchange.py` (offline path simulator + keep-out checker),
  three hooks in `.claude/` (git-on-mount guard, framework-edit guard, auto-run the visualizer),
  `docs/decisions.md` (the *why* log), and the `/start` · `/brief` · `/done` session model with
  `docs/runbooks/` (TODAY.md retired into it).

### 2026-07-25 — TurtleNeck → PSF proportional sync-feedback sensor
- **Swapped the dual-switch TurtleNeck for a PSF (Proportional Sync-Feedback) analog sensor.** Wiring validated: signal → **gpio26 (ADC0)** on the ERB EXTRA PINS header, power → **3.3 V**, common → GND.
- **Why gpio26 and not a sensor port**: the PSF is analog, and on the RP2040 only gpio26–29 are ADC-capable. Every populated ERB sensor/endstop port (gpio2/3/4/5/12/18/22/24/25) is digital-only, so no existing port could take it. 3.3 V rather than 5 V because the PSF output is ratiometric to its supply — on 5 V it would swing past the 3.3 V ADC limit.
- **Config**: `MMU_SYNC_ANALOG=gpio26` alias in `mcu.cfg`; `sync_feedback_analog_*` block live in `mmu/base/mmu_hardware.cfg` (tension/compression pin lines commented, not deleted — TurtleNeck is a two-line revert); flowguard comment updated.
- Corrected a **stale note** claiming the installed Happy Hare rejects the analog options — HH `5cc88729` (2026-07-07) implements `MmuProportionalSensor` and registers `MMU_CALIBRATE_PSENSOR`.
- Verified nothing else depended on the discrete compression switch: `extruder_homing_endstop: extruder` (Filamatrix switch) and `gate_homing_endstop: mmu_gear` are unaffected, and the tension test / post-load tension adjust both branch on `has_proportional`.
- **Calibrated** (`MMU_CALIBRATE_PSENSOR`, gate 0 loaded): `max_compression: 0.9965`, `max_tension: 0.0109`, `neutral_point: 0.5037`. Sensor reads **HIGH under compression**, LOW under tension, spanning nearly the full ADC range — so the initial placeholder values were inverted. Buffer travel measured **14.5 mm**, `sync_feedback_buffer_range`/`_maxrange` set to match.
- **Calibration gotcha (cost several bad runs)**: `MMU_CALIBRATE_PSENSOR` only works if the buffer starts near **mid-travel**. Started from a rail (raw ≈ 0.996) it exits after ~2 of its 2 mm steps on ADC noise and reports garbage — max_tension came back as 0.996 / 0.985 / 0.690 / 0.760 / 0.770 on five consecutive runs. `_seek_limit` in `mmu.py` ends the sweep the instant one sample moves against the ramp, and `SD_THRESHOLD = 0.02` (mmu.py:2833) is **declared but never referenced** — the intended jitter deadband was never wired up. Fix: `MMU_TEST_MOVE MOVE=-2 MOTOR=gear` until `MMU_SENSORS DETAIL=1` shows raw ≈ 0.27, then calibrate. Step budget is *not* the constraint (28 mm available at maxrange 14.5), so raising `MOVE=` doesn't help despite what HH's failure message suggests.
- **Still pending**: `flowguard_max_relief` at the switch-era 40, to be walked toward ~15.

### 2026-07-17 — back-left rework: depressor moved, gantry brush/rest, blobifier geometry final
- **Hardware rework**: depressor moved front-left → **back-left** (cut line y=341, x 15→0, **cut plane z=15** to clear the shaker arm); blobifier tray raised (top **z=0.3**, purge x=9); shaker arm engagement now **x=4, z=4**; NEW **gantry-mounted brush (x53–88)** and **nozzle rest (x=45, RTV cup, handles hot nozzle)** — both work at any Z; old brush + old purge bucket removed.
- **Config updated to match**: cut geometry (15,341 → 0,341); `min_toolchange_z: 15` (Z floor for all toolchange travel — enforces the cut-zone clearance); parks `pause`/`complete` → nozzle rest (45,359); new `_KARMAN_PARK_MOVE` side-approach macro (y_max features approached only via lanes **15<x<40** or **x>95**); Klippain `brush_xyz → 70.5,359`, `purge_bucket_xyz → 9,359`; blobifier vars (shaker 4/4, tray 0.3, purge_x 9, brush 53/35, `brush_top: None`).
- **Path-safety verified from config**: QGL points (max y=275) and Y-homing (runs at x≈345, in the x>95 lane) are both clear of the new structures. Bed-mesh rear-left row still needs a manual jog check.

### 2026-07-15/16 — cutter validated, latch root-cause, blobifier rebuilt + wired
- **Confirmation cut at `residual 25` ✓** and **real `T0`↔`T1` swaps with the cutter ✓** — cut → unload → load chain solid.
- **1-color print with cuts at start + end** — no issues. (Full 2-color cutter print parked until Blobifier is up.)
- **Root-caused the suspected NightOwl "skipping": gate-0 mirrored nightwatch latch wasn't holding.** Reprinted at **99% scale** — holds. Gate 1 measured; likely needs **99.5%** (task under NightOwl internals). Extruder-current worry retired.
- **Blobifier rebuilt + wired**: new base (old one cracked), wider bed plate (+5mm), taller shaker arm (+4mm), shims sorted; shaker-arm engagement measured **X=3.0, Z=3.0**. Servo → **PC3** (Z-STOP header, 5V from 24V buck), bucket switch → **PC1** (X-STOP, NC→GND). `blobifier_hw.cfg` configured, `[include mmu/addons/blobifier.cfg]` live, aliases in `mcu.cfg`. Servo/switch untested; arm/tray not yet attached. Known debt: switch ground returns via the buck (base only fits a 4-pin JST) — dedicated 2nd ground needs a base mod + reprint.
- Committed the prior batch (cutter enable/tuning, gate-check, slicer docs, moonraker timeout, bed_fans fix, `docs/custom_macros.md`).

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
- TurtleNeck dual-switch sync feedback configured (stand-in until the proportional PSF arrives). **Superseded 2026-07-25 — PSF fitted, see below.**
- Filamatrix + beefy depressor installed; pre/post-extruder filament switches wired to the Nitehawk.
- BTT SFS v2 wired to the Leviathan (runout + motion).
