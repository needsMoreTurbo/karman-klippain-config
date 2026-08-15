# Runbook — install BDPressure E for automatic pressure-advance calibration

**Objective:** fit the PandaPi3D **BDPressure E** strain-gauge sensor, connect it **by USB** to the
Pi, install the Klipper module, and get `PA_CALIBRATE` returning a usable pressure-advance value on
demand as a standalone command.
**Status:** ✅ **COMPLETE — 2026-08-14**, with one pending deploy step (⚠️ below: needs
`FIRMWARE_RESTART`). All verification passed. The sensor returns repeatable PA values (±0.004 run
to run), and the measured ABS figure of **0.032** has replaced the inherited 0.0480 in
`variables.cfg` — on disk; **not yet live on the printer**, see the warning below. Went beyond the
original scope: two vendor bugs found and patched, a melt-zone physics model built and fitted, and
a flow/acceleration PA matrix generated for OrcaSlicer's adaptive model. See `docs/pa_physics.md`
for the physics and method, `physics/pa_sweeps.json` for every sweep result, `physics/pa_law.json`
for the matrix. Remaining follow-ups are listed at the end of the status log. · **Created:**
2026-08-03
**Prerequisites:** sensor in hand; a hotend-removal session (it mounts at the groove mount);
filament loadable via the MMU.

**Vendor docs (read both before starting):**
- <https://pandapi3d.cn/en/bdpressure/home> — wiring, Klipper config, `PA_CALIBRATE` usage
- <https://github.com/markniu/bd_pressure> — module source and install script

## What this sensor actually does
A strain gauge at the hotend groove mount measures extrusion force directly. `PA_CALIBRATE` runs
the extruder through a controlled accel/decel sequence **in free air — it prints nothing**, fits a
pressure-vs-acceleration curve, and applies the result with `SET_PRESSURE_ADVANCE`. Filament
**must** be loaded in the nozzle first.

## Scope
Mount → connect (USB to the Pi; originally planned as I2C to the Nitehawk, superseded 2026-08-12) →
install module → configure PA section only → verify comms → get a plausible PA value out of
`PA_CALIBRATE` → confirm nothing else regressed.

## ⚠️ Out of scope — do not touch
- **The Beacon stays the only probe.** The sensor also works as a strain-gauge nozzle probe and the
  vendor's example config includes a `[probe]` section with `activate_gcode: PA_RESET`. **Do not
  copy that section in.** Karman probes with Beacon: `stepper_z` uses `probe:z_virtual_endstop`,
  `contact_auto_calibrate` runs every print by explicit decision, and `nozzle_expansion` depends on
  Beacon contact behaviour (see `docs/decisions.md`, 2026-08-02). A second `[probe]` collides.
- **`material_parameters` PA values** (`ABS 0.0480`, `PLA 0.0525`) — leave them *during* the
  objective. The user reads the calibrated number and decides manually; **nothing writes back
  automatically**, and that stays true — the module's `apply_result` defaults off.
  **Closed 2026-08-14:** ABS was changed 0.0480 → **0.032** by explicit decision once the
  measurement existed. PLA is untouched and uncalibrated.
- **Slicer start g-code** — no per-print `PA_CALIBRATE`. This is a standalone command only.
- **Klippain framework files** (`macros/`, `config/`) — a hook blocks edits. Config goes in
  `overrides.cfg` / `mcu.cfg` / a dedicated included file.
- **`contact_auto_calibrate`, `contact_z_home`, `nozzle_expansion`** — unrelated, all validated.

## Pre-resolved decisions
- **PA calibration only**; probe mode not used.
- ~~**Software-I2C to the Nitehawk toolhead MCU** (not USB — avoids a second cable up the
  umbilical).~~ **SUPERSEDED 2026-08-12 → USB.** The original choice optimised for cabling, before
  two facts were known: (a) I2C **structurally cannot deliver the raw signal** — the firmware
  writes only the processed `R:` result into the I2C register file (`pa.c:204`) while the raw ADC
  stream goes exclusively to the UART; and (b) an I2C NAK is an unconditional `shutdown()`, so a
  dead or unplugged sensor took down the toolhead MCU on **every `G28`**. USB also runs the sensor
  at its designed 5V from VBUS and restores the vendor's diagnostic tooling. See the Step 5 config
  block and `bdpressure.cfg`'s header for the current wiring.
- **Runtime only**: `PA_CALIBRATE` applies via `SET_PRESSURE_ADVANCE` for the session.

---

## ⚠️ Step 1 — Measure nozzle Z BEFORE removing anything *(user; do this first)* — ✅ DONE
**Reference measurement, 2026-08-03: nozzle tip to the bottom of the nozzle wiper = `10.4 mm`.**
Chosen because it is easy to replicate after the hotend goes back together. **Re-take this exact
measurement at Step 3 and compare.**

Expected to be unchanged: the maintainer has designed a custom Filamatrix cowling specifically for
the Rapido V2 UHF *with* the BDPressure E fitted, intended to preserve nozzle Z. That is the
expectation, not yet the evidence — the Step 3 re-measurement is still what confirms it, and the
escalation path below still applies if it moved.


**This gates the whole objective.** The sensor sits at the **groove mount**, in the load path
between hotend and toolhead. If it changes where the nozzle sits relative to the toolhead, a large
amount of validated calibration becomes wrong at once:

| Value | Where | Why it moves |
|---|---|---|
| `toolhead_extruder_to_nozzle: 94.5` | `mmu_parameters.cfg` | extruder gears → nozzle distance |
| `toolhead_sensor_to_nozzle: 85` | `mmu_parameters.cfg` | toolhead sensor → nozzle |
| `variable_blade_pos: 69` | `mmu_macro_vars.cfg` | Filamatrix cut position, measured from the nozzle |
| Beacon `z_offset` / contact cal | `overrides.cfg` | nozzle-to-probe relationship |
| `tray_top: 0.3`, keep-out clearances | `blobifier.cfg`, CLAUDE.md | nozzle height vs fixed structures |

Record, with the hotend at a known reference, the nozzle tip position relative to a fixed toolhead
feature. **Repeat the same measurement after fitting (Step 3).**

- **If nozzle Z is unchanged** → continue; nothing above needs revisiting.
- **If it moved** → STOP and report the delta. Re-deriving the MMU toolhead dimensions, cut
  geometry and Beacon offsets is a **separate objective needing its own runbook** — do not attempt
  it inside this one. `MMU_CALIBRATE_TOOLHEAD` auto-cal is unreliable on this machine (extruder
  slip); these were measured by hand with a filament probe.

## Step 2 — Plan the wiring *(model audits, user confirms)* — ✅ RESOLVED 2026-08-03
**No umbilical conductors are needed.** The premise that they were was wrong: the Nitehawk-SB v2.0
has a **dedicated general-purpose I2C port on the toolboard itself** (PCB label `I2C`, JST-PH 4P,
`PB3`/`PB4` = SCL/SDA), added in v2 specifically for secondary I2C devices. The sensor mounts at
the groove mount, centimetres from that connector — it is a single short pigtail, entirely at the
toolhead.

**Pin pair: `toolhead:MCU_I2C_SCL` (PB3) and `toolhead:MCU_I2C_SDA` (PB4).** Both are unused —
verified against every `toolhead:` reference in `mcu.cfg` / `overrides.cfg` / `printer.cfg` and
against the aliases in `config/mcu_definitions/toolhead/LDO_Nitehawk-SB_v2.0.cfg`. Committed
toolhead pins for the record: `PB0` pre-extruder switch, `PB1` post-extruder switch, `PC15`
relocated X endstop, `PB2` chamber thermistor, `PB10/PA5/PA2/PA6` ADXL345 (accelerometer include
is active), `PD0/PD1` hotend fan + tacho, `PA15` part fan, `PB12` hotend thermistor, `PA7` heater,
`PB8/PB9/PC14/PB7/PB6` extruder motor, `PD3` neopixel, `PC6` activity LED. Only `PB3`/`PB4` and
`PD2` (part-fan tacho, commented out) are free — so the I2C pair is the *only* workable choice,
which is convenient.

Sensor pigtail (from `hardware/bdpressureE/connect.jpg`) breaks out `I2Cscl`, `I2Csda`, `Boot`,
`Probe`, `USB+`, `GND`, `USB-`, `5V`. **I2C-only PA mode uses four of them: SCL, SDA, GND, 5V.**
The other four stay unconnected — `Probe` in particular must NOT be landed anywhere.

### Rail voltage — resolved 2026-08-03
The Nitehawk `I2C` port is **`SCL / SDA / 3V3 / GND`** (JST-PH2.0 4P) — 3.3V, not 5V. The sensor's
pigtail asks for 5V. Reviewing the BDPressure E schematic
(`hardware/bdpressureE/Schematic_Pressure_sensor_E3D_2026-04-13.pdf`) resolves the mismatch:

- On the sensor board the **5V net feeds exactly one thing: the input of U2, an LP5907MFX-3.3
  LDO** (plus its input caps, and the CH340E/USB-C section we are not using). Everything that
  matters — U3 `STM32C011F6U6` `VDD/VDDA`, U1 `ADS1220` `AVDD`/`DVDD` — runs off that LDO's 3.3V
  output.
- Critically, **the strain-gauge bridge is already excited at 3.3V, not 5V**: test-dot `T4` ties
  the bridge high side to the 3.3V net and `T1` to GND, while the ADC's external reference
  `REFP0` sits on that same 3.3V net. The measurement is therefore **ratiometric** — excitation
  and reference are the same node, so the absolute rail value cancels out of the result.
- LP5907 input range is **2.2–5.5V** and dropout is 120 mV at its full 250 mA. This board draws
  a small fraction of that, so at 3.3V in the part simply sits in permanent dropout and passes
  through ≈3.28V. `STM32C0` needs ≥2.0V, `ADS1220` needs ≥2.7V (DVDD) / ≥2.3V (AVDD). No part is
  out of spec and nothing is at risk of damage.

**So 3.3V works.** The one genuine cost: an LDO in dropout has no PSRR left — it stops filtering
and becomes a wire, passing the Nitehawk's 3.3V rail noise (stepper, fan PWM, neopixel, bit-banged
I2C) straight onto the bridge excitation and the ADC reference. The ratiometric topology cancels
most of that, so this is a **noise risk, not a function risk**.

### ✅ Wiring decision — single connector, all four wires on the `I2C` port
**Try 3.3V first.** Everything goes to the one JST-PH2.0 4P `I2C` header:

| Sensor wire | `I2C` port pin |
|---|---|
| `I2Cscl` | `SCL` (PB3) |
| `I2Csda` | `SDA` (PB4) |
| `5V` | `3V3` |
| `GND` | `GND` |

Leave `Boot`, `Probe`, `USB+`, `USB−` unconnected — `Probe` especially must not be landed anywhere.

**Why not 5V, having established it is electrically preferable:** the two candidate 5V sources both
cost more than the benefit is worth.
- The `USB Expansion Port` is **already occupied by the Beacon**, and teeing 5V off a JST-ZH1.5 is
  fiddly, fragile work on a moving toolhead.
- The `XY Endstop` port's `5V` pin is genuinely free (Karman uses only `GND`/`PB0`/`PB1` there for
  the MMU pre- and post-extruder switches), but reaching it means re-crimping or piggybacking an
  in-use 4-pin connector.

Against that: 3.3V leaves every part in spec, and the ratiometric bridge cancels the rail out of
the result. The only exposure is noise, which is **cheap to detect and cheap to reverse** — so
buying certainty up front with fiddly connector work is the wrong trade. Wire the single connector,
measure, escalate only on evidence.

### Escalation to 5V — the trigger, decided in advance
Move the `5V` wire to the **`XY Endstop` port's `5V` pin** (the practical 5V source) if the first
calibrations show any of:
- Two `PA_CALIBRATE` runs on the same filament disagreeing by more than ~20%.
- The sweep never converging — `pa_data_process` early-stops once ≥20 samples land with `Hk≥2` and
  `Ha≥5`, so a run that grinds through all 50 steps every time is the signature of a noisy fit.
- Visibly scattered raw values in the per-step `bd_pa: R:...` console lines.

If none of those show up, the 3.3V feed is fine and stays.

### ⚠️ Hazard — do not plug in the sensor's USB-C
VBUS on the sensor's Type-C sits on the **same net** as the pigtail's `5V` wire. With this wiring
that net is tied to the Nitehawk's **3.3V rail**, so plugging in USB-C would backfeed 5V straight
into the STM32G0B1 and the ADXL345. This matters more on the 3.3V feed than it would have on 5V.

**Note that the USB fallback is unavailable regardless**, so it costs us nothing here: U5 (CH340E)
is strapped for 5V operation (`V3` decoupled to GND rather than tied to VCC) and will not
enumerate at 3.3V — and in any case the toolboard's only downstream USB port is taken by the
Beacon. `port: usb` was never a live option on this machine.

### I2C pull-ups — non-issue
The sensor schematic shows no I2C pull-ups (`R3` 4.7 kΩ is on `boot0`). Not a problem: Klipper's
software I2C calls `gpio_in_setup(pin, 1)` — pull-up enabled — when releasing each line
(`klipper/src/i2c_software.c`). The STM32's internal ~40 kΩ pull-up gives a ~2 µs rise against
typical bus capacitance, and `bdpressure.py` clocks the bus at `BDP_I2C_SPEED = 10000` (10 kHz,
100 µs bit period). Ample margin.

## Step 3 — Mount and wire *(user)*
Follow the vendor mounting guide. Notes specific to this machine:
- Hotend is a **Rapido V2 UHF + melt-zone extender** — the vendor lists Rapido as compatible, but
  the extender makes the stack taller than stock; confirm the M2.5 screws are **not too long**
  (vendor warns they can crush the PCB/strain gauge).
- The toolhead already carries the **Filamatrix cutter arm**. After fitting, re-check the
  permanent **front-left keep-out** (x<10, y<17, any Z — cutter arm vs XY idler) and the y_max
  feature row clearances still hold. See CLAUDE.md.
- **Re-take the Step 1 nozzle-Z measurement now** and compare.

## Step 4 — Install the Klipper module *(model; user runs restarts)*
```
ssh ernst@192.168.1.240 'cd ~ && git clone https://github.com/markniu/bd_pressure.git'
ssh ernst@192.168.1.240 'cat ~/bd_pressure/klipper/install.sh'    # READ IT BEFORE RUNNING
```
**Read the script first** and report what it does — specifically whether it only links a module
into `~/klipper/klippy/extras/` or whether it **patches Klipper itself**. A patch is a much bigger
commitment here: this machine already layers Klippain + Happy Hare + Beacon, all with their own
updaters.

**✅ Answered 2026-08-03 — it does NOT patch Klipper.** `install.sh` does exactly three things:
symlink `bd_pressure/klipper/bdpressure.py` → `~/klipper/klippy/extras/bdpressure.py`, remove any
prior symlink first, and append that path to `~/klipper/.git/info/exclude` so the Klipper repo
stays clean. Nothing else is touched. This is the low-commitment install we hoped for, and it is
trivially reversible (`rm` the symlink).

⚠️ **But the module is not inert.** `bdpressure.py` registers a `homing:homing_move_begin` event
handler that calls `set_probe_mode()` on **every homing move** — including every Beacon contact
probe, QGL point and `G28`. In I2C mode that is two queued `i2c_write`s (`pa_probe_mode`,
`probe_thr`), no blocking read, so it cannot stall or error out a homing move — but it is an
unconditional side-effect on the machine's most safety-critical path, and it happens **even
though we omit `[probe]`**. Judged acceptable; recorded here so nobody is surprised later.

Then run it, and add a Moonraker `update_manager` entry so the module survives updates and is
visible in Mainsail's update list.

## Step 5 — Configure — PA section only
> ⚠️ **The I2C config block below is SUPERSEDED — the transport changed to USB on 2026-08-12.**
> The live section is now:
> ```
> [bdpressure bd_pa]
> port: usb          # must be exactly "usb" — runtime methods match with ==, not "in"
> serial: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
> baud: 38400
> thrhold: 4
> ```
> Everything else in this step — omitting `[probe]`, copying the vendor macros, the three
> patches — is transport-agnostic and still applies. The `_measure_data` off-by-one no longer
> matters, since that bug is in the I2C read path only.

Create `bdpressure.cfg` in the repo root and `[include bdpressure.cfg]` from `printer.cfg`.
Do **not** `[include]` the vendor's own `bd_pressure.cfg` — it carries the `[probe]` block. Write
our own, containing the hardware section plus copies of the vendor's `PA_E` / `PA_CALIBRATE` /
`PA_STATE` macros (`PA_CALIBRATE` calls `PA_E`, so both are required):
```
[bdpressure bd_pa]
port: i2c
i2c_mcu: toolhead
i2c_software_scl_pin: toolhead:MCU_I2C_SCL     # PB3
i2c_software_sda_pin: toolhead:MCU_I2C_SDA     # PB4
thrhold: 4          # probe trigger threshold; unused in PA-only mode
```
⚠️ **Omit the vendor's `[probe]` block entirely** (see out-of-scope). Confirmed safe: nothing in
`PA_CALIBRATE` touches `[probe]` — it drives the sensor purely through `SET_BDPRESSURE` and reads
`printer["bdpressure bd_pa"].state`. The vendor's `PA_RESET` macro exists only to be called from
`[probe] activate_gcode`; `PA_CALIBRATE` issues `COMMAND=RESET_PROBE` directly. Copy `PA_RESET` in
anyway (harmless) or drop it.

Fixes to apply while copying the macros — see the Step 7 findings for why:
- Fix `ACC_WALL` — the vendor reads `params.ACCEL_TO_DECEL` inside the `if params.ACC_WALL` branch,
  so a passed `ACC_WALL` is silently discarded and 4000 is used.
- Drop the `SET_VELOCITY_LIMIT ... ACCEL_TO_DECEL=` line. Harmless (Klipper ignores unknown gcode
  params, verified in `klippy/toolhead.py`) but it is dead on this Klipper build; the following
  `MINIMUM_CRUISE_RATIO` line is the one that does the work.
- Replace the trailing `SET_KINEMATIC_POSITION X=0 Y=0` / `G28 X` / `G28 Y` recovery with something
  that does not lie to Klipper about being in the front-left keep-out corner.

Then:
```
FIRMWARE_RESTART    # user runs; never mid-print
```

## Step 6 — Verify communication *(user runs)*
```
ssh ernst@192.168.1.240 'grep -ai "pandapi3d\|bdpressure\|bd_pa" ~/printer_data/logs/klippy.log | tail -20'
```
Klipper must start cleanly with no config errors and no Beacon conflict.

### ⚠️ `PA_STATE` is NOT a comms test
`get_status` returns `START`/`STOP` straight from `self.last_state`, a Python flag set by
`cmd_start`/`stop_pa`. It never touches the bus. A fresh `PA_STATE` reporting `STOP` only proves
the module loaded and the config section parsed — the sensor could be entirely unwired.

### ⚠️ An unanswered I2C address SHUTS KLIPPER DOWN — verify before homing
`src/i2ccmds.c` maps every NAK to `shutdown()`: `I2C NACK`, `I2C START NACK`,
`I2C START READ NACK`. There is no soft-error path. Combined with the module's
`homing:homing_move_begin` hook — which calls `set_probe_mode()` and therefore two
`i2c_write`s on **every homing move** — a sensor that is not answering means
**every `G28` shuts down the toolhead MCU.**

So the order matters. **Do not home until I2C is confirmed.** The real comms test is a blocking
read, run cold and idle:
```
SET_BDPRESSURE NAME=bd_pa COMMAND=READ VALUE=0
```
- **No shutdown** → the device ACKed its address. Since an absent device leaves SDA pulled high and
  `i2c_software_read_ack` turns that into `shutdown()`, *surviving the command at all is the
  positive result.* The payload itself is expected to be empty here: `_measure_data` (reg 15) has
  nothing in it until a measurement is running.
- **`MCU 'toolhead' shutdown: I2C NACK`** (or `START NACK`) → nothing is answering at the address.
  Recover with `FIRMWARE_RESTART`, then check the connector seating and pinout before anything
  else. A controlled failure at idle is much cheaper than the same failure during a homing move,
  or mid-sweep at 260 °C with the gantry de-energized.

### The positive confirmation — read the version string
`cmd_start`'s I2C branch reads `_version` (reg 0x0, 15 bytes) and echoes it:
```
SET_BDPRESSURE NAME=bd_pa COMMAND=START     # expect ".cmd_start i2c: <version string>"
SET_BDPRESSURE NAME=bd_pa COMMAND=STOP      # always follow with this — see below
```
A version string is static content the sensor must actively produce, so this proves the full
chain (bus, addressing, and the sensor's STM32C011 running) rather than just an address ACK.

⚠️ **`COMMAND=START` de-energizes X and Y** — that is what it does in a real sweep too. The gantry
goes slack until `COMMAND=STOP`. Harmless while idle and unhomed, but do not leave it in the START
state, and do not run this while anything is resting against the gantry.

(Correction to the Step 4 note above: the homing hook *cannot block or stall* a homing move, but
it **can** shut the MCU down via NAK. "Not inert" was an understatement.)

## Step 7 — First calibration *(user runs)*

### ⚠️ What `PA_CALIBRATE` actually does — read before running it
Read from the vendor macro source; this is materially different from the description in "What this
sensor actually does" above, which was written from the marketing page.

- **It de-energizes X and Y.** `SET_BDPRESSURE COMMAND=START` makes `bdpressure.py` drive the
  `stepper_x` and `stepper_y` enable pins low directly, behind Klipper's back. On this CoreXY that
  frees the whole gantry. (It correctly guards `stepper_x1`/`stepper_y1`, which Karman does not
  have — single X and single Y motor.)
- **So every `G1 X.. Y..` in the macro is virtual.** Klipper thinks it is tracing lines from
  x78→x158 and y38.75→y210.25; the toolhead physically does not move. "It prints nothing" is
  therefore true, but not for the reason assumed — and it means **the entire purge lands in one
  spot, wherever the toolhead was parked when you started it.**
- **That purge is ~199 mm of filament** (`G1 E4`, then `E9.92204`, then 50 × 3.706 mm) ≈ **480 mm³**.
  On the UHF melt zone this is a substantial blob dropping from whatever Z you are at. Decide
  deliberately where it goes — *not* over the bed if you want to avoid chiselling ABS off the
  plate, and *not* into the Blobifier tray, which is sized for per-toolchange blobs, not for half
  a cm³ in one go.
- **It ends by lying about position:** `SET_KINEMATIC_POSITION X=0 Y=0` then `G28 X` / `G28 Y`, then
  `SET_KINEMATIC_POSITION Z={z_current}`. It sets the position to **(0,0) — inside the permanent
  front-left cutter keep-out** — while the toolhead is physically elsewhere. Any Klippain homing
  prologue that moves relative to the believed position now runs in a frame offset by ~78 mm.
  This is the single most dangerous line in the macro and the reason for the wrapper below.
- The `[probe]` omission is confirmed safe (see Step 5); the module's homing hook is not (Step 4).

### Plan: wrap it, don't call it bare
Write a `KARMAN_PA_CALIBRATE` wrapper in `bdpressure.cfg` that positions the toolhead over a chosen
purge target first, calls the patched `PA_CALIBRATE`, and does a sane re-home afterwards. Run
`uv run tools/visualize_toolchange.py` against it — noting the visualizer cannot model
`SET_KINEMATIC_POSITION`, so the recovery path still needs one careful manual dry-run at high Z
with no filament loaded.

### Running it
Filament **must** be loaded. Use the standalone swap macro, not a bare `Tn`:
```
SWAP TOOL=0
G28
G1 Z40
KARMAN_PA_CALIBRATE NOZZLE_TEMP=260 MAX_VOLUMETRIC=25 ACC_WALL=5000 TRAVEL_SPEED=300
```
Notes:
- `NOZZLE_TEMP=260` matches the gate-map ABS temperature; adjust per filament. The macro issues
  `M109` itself and waits.
- `MINIMUM_CRUISE_RATIO=0.5` is the parameter to use; `ACC_TO_DECEL_FACTOR` is legacy. Verified:
  this Klipper (`bd99b19`, 2026-05-23) has no `ACCEL_TO_DECEL` in `SET_VELOCITY_LIMIT`.
- The macro overrides PA to 0.04, then sweeps 0 → 0.098 in 0.002 steps across 50 iterations, and
  can stop early once the fit converges (needs ≥20 samples). The result is reported to the console
  by `pa_data_process`; **it does not write back to `material_parameters`** — you read it and
  decide, as intended.
- Hotend fan vibration perturbs the strain gauge — if results are noisy, note it and retry.

Record the returned PA value and compare against the current `material_parameters` figure
(ABS `0.0480`). A wildly different number is a signal to re-run, not to trust blindly.

## Verification — ✅ ALL PASSED (2026-08-14)
- [x] Nozzle Z either unchanged, or the delta reported and escalated (Step 1) — 10.4 mm, unchanged
- [x] Klipper starts clean; no `[probe]` conflict; Beacon still homes and `contact_auto_calibrate` works
- [x] Sensor visible in `klippy.log`
- [x] `PA_CALIBRATE` completes and reports a plausible PA value — 13 valid sweeps, 0.028–0.044
      across 10–25 mm³/s and accel 1500–6000
- [x] Repeatable: two runs on the same filament agree reasonably — 14.4/6000 measured 0.0306 twice
      to four decimals; three runs at 14.4/1500 gave a sample SD of ±0.0040 (χ²/dof 0.26 about the
      mean), so the fit's own ±0.008 is roughly 2× conservative
- [x] A normal 2-colour print still starts and prints correctly (nothing regressed) — ran; the
      toolchange/Blobifier path is unaffected by the PA changes. The print later stopped on a
      **clogged nozzle, which is a pre-existing recurring fault predating this sensor** and is
      tracked separately — not a BDPressure regression.
- [x] `uv run tools/visualize_toolchange.py` still reports clean — re-run 2026-08-14 after the
      `GEOM_SCALE` and PA-restore changes; all five scenarios clean

## Commit guidance
- `feat(hardware): add BDPressure E sensor for automatic PA calibration` — `bdpressure.cfg`,
  `printer.cfg`, `mcu.cfg`, `moonraker.conf`
- Add a `docs/decisions.md` entry recording **why the vendor's `[probe]` section is deliberately
  omitted** — otherwise a later session will "helpfully" add it and collide with Beacon.
- Add a second `docs/decisions.md` entry for **the 3.3V feed into a sensor whose pigtail is
  labelled 5V** — it looks like a wiring mistake and is not. Capture: the 5V net only feeds an
  LP5907-3.3 LDO, the bridge is already 3.3V-excited and the measurement is ratiometric, the
  accepted cost is PSRR, and the escalation path is the `XY Endstop` port's 5V pin.
- If nozzle Z moved, that recalibration is its own runbook and its own commits.

## Status log
- **2026-08-03** — runbook created; not yet started.
- **2026-08-03** — **Step 2 resolved on paper; Steps 4/5/7 pre-audited from source.** No hardware
  touched. Cloned the module to `/tmp/bdp_probe` on the Pi (scratch, not `~`) and read
  `install.sh`, `bdpressure.py`, `bd_pressure.cfg` and the E-variant wiring photo; cross-read the
  LDO Nitehawk-SB v2.0 port table and this repo's committed toolhead pins.
  Findings, in order of how much they change the plan:
  1. **No umbilical work needed** — the v2 toolboard has a dedicated 4-pin `I2C` port at `PB3/PB4`.
     Four wires, all at the toolhead. Only open question is that port's rail voltage.
  2. **`PA_CALIBRATE` de-energizes X/Y and purges ~480 mm³ in one spot**, then re-homes from a
     faked `X=0 Y=0` — which is inside the front-left cutter keep-out. Needs a wrapper.
  3. **`install.sh` does not patch Klipper** — one symlink plus a `.git/info/exclude` line.
  4. **The module hooks `homing:homing_move_begin`** and pokes the sensor on every homing move,
     `[probe]` or not. Two queued I2C writes, no blocking read — acceptable, but not inert.
  5. Two vendor macro bugs to fix on copy (`ACC_WALL` reads the wrong param; a dead
     `ACCEL_TO_DECEL` argument).
  **Blocked on the user for:** the Step 1 nozzle-Z reference measurement (gates everything), and
  confirmation of the I2C port's rail voltage from the board silkscreen.
- **2026-08-03** — **Step 1 done and the rail voltage resolved; Step 2 now fully specified.**
  Maintainer supplied the nozzle-Z reference (`10.4 mm` to the wiper bottom), the LDO port/pin
  graphic, and the BDPressure E schematic.
  - Nitehawk `I2C` port is `SCL/SDA/3V3/GND` — **3.3V**, so the sensor's 5V wire has no match on
    that connector.
  - Schematic review: the sensor's 5V net only feeds an **LP5907-3.3 LDO**; the bridge is already
    excited at 3.3V and the ADC reference shares that node, so the measurement is **ratiometric**
    and 3.3V-in works (LDO sits in dropout, ≈3.28V out, every part in spec). Cost is lost PSRR,
    i.e. a noise risk only.
  - **Better option adopted: 5V + GND from the unused `USB Expansion Port` (JST-ZH1.5 5P), SCL/SDA
    from the `I2C` port.** Keeps the LDO in regulation, still no umbilical work, and preserves the
    option of falling back to `port: usb` later.
  - Two hazards recorded: sensor USB-C VBUS shares the 5V net (backfeed risk onto the Nitehawk
    3.3V rail), and the CH340E is strapped for 5V so a 3.3V feed would kill the USB fallback.
  - I2C pull-ups confirmed a non-issue (Klipper software I2C enables internal pull-ups; bus runs
    at 10 kHz).
  **Next:** Step 3 — mount and wire, then re-measure nozzle Z against the 10.4 mm reference.
- **2026-08-03** — **Wiring decided: 3.3V, single connector.** All four wires go to the `I2C` port,
  with the sensor's `5V` on the port's `3V3` pin. Maintainer's call, and the right one: the
  `USB Expansion Port` is already taken by the Beacon and the `XY Endstop` 5V pin needs an in-use
  connector re-crimped, whereas the 3.3V downside is noise only — cheap to detect, cheap to
  reverse. Escalation trigger to 5V written into Step 2 so it is decided before the data arrives
  rather than argued about after. Also settled: `port: usb` was never actually available on this
  machine (CH340E strapped for 5V, and the only downstream USB port is the Beacon's), so nothing
  is lost by the 3.3V feed.
  **Still blocked on hardware:** Step 3 mount + wire.
- **2026-08-03** — **Step 3 confirmed by the maintainer: nozzle Z unchanged** (re-measured 10.4 mm
  to the wiper bottom). The custom Filamatrix cowling did its job — none of the MMU toolhead
  dimensions, cut geometry or Beacon offsets need revisiting, and the escalation branch is closed.
- **2026-08-03** — **Steps 4 and 5 done; awaiting `FIRMWARE_RESTART`.** Printer was `ready` /
  `standby` before any change.
  - **Step 4:** cloned `~/bd_pressure` (`5e94c64`, 2026-07-30), re-verified `install.sh` and the
    audited behaviours in `bdpressure.py` byte-for-byte against what was reviewed earlier (the
    `/tmp` copy was wiped by the reboot), then ran it. Symlink created; `bdpressure.py` correctly
    excluded from the Klipper repo's git status. Added an `[update_manager bd_pressure]` entry to
    `moonraker.conf` alongside the other module entries.
  - **Step 5:** wrote `bdpressure.cfg` and included it from `overrides.cfg` (next to
    `bed_fans.cfg` / `thermal_expansion.cfg`, matching house style). Contains `[bdpressure bd_pa]`
    on `MCU_I2C_SCL`/`MCU_I2C_SDA`, the vendor's `PA_RESET`/`PA_STATE`/`PA_E`, a patched
    `PA_CALIBRATE`, and the `KARMAN_PA_CALIBRATE` wrapper. **No `[probe]` section.**
  - All three planned patches applied and verified by rendering: `ACC_WALL=5000` now actually
    reaches `SET_VELOCITY_LIMIT` (was silently 4000); the dead `ACCEL_TO_DECEL` argument is gone;
    the recovery is `SET_KINEMATIC_POSITION CLEAR=XY` + `G28 X Y` instead of asserting (0,0), and
    the velocity limits the vendor leaves mangled are restored to the configured 21000/5.0/0.5.
  - Confirmed `[force_move] enable_force_move: True` (Klippain `machine.cfg`), so `CLEAR=XY` is
    available; confirmed Klipper `v0.13.0-662` has no `ACCEL_TO_DECEL`; confirmed Klippain's X/Y
    homing hooks (`_HOME_PRE_AXIS`/`_HOME_POST_AXIS`/`_HOME_XY`) never invoke Beacon contact, so
    the post-sweep `G28 X Y` at 260 °C does **not** trip `contact_max_hotend_temperature: 180`.
    The wrapper warns the user anyway, because a subsequent `G28 Z`/QGL *would*.
  - **Tooling:** `tools/render_macro.py` could not render any macro using `action_respond_info`
    (StrictUndefined) and had no way to pass `params`. Added stubs for the `action_*` globals and
    a `--params KEY=VAL,...` flag. Bed-fan selftest still 29/29.
  - **Validation:** all five macros render; both guard paths abort correctly (mid-print, no
    filament) and the unhomed path emits `G28`; the legacy `ACC_TO_DECEL_FACTOR=40%` path yields
    `min_cruise=0.60`. `visualize_toolchange.py` clean on all five existing scenarios.
  - **Deliberately did not add a visualizer scenario for `KARMAN_PA_CALIBRATE`.** It would draw
    the 50 virtual `PA_E` sweeps as real toolhead travel across x78–158 / y38–210, which is
    exactly the motion that does *not* happen — false assurance, worse than no scenario. The
    wrapper's only real motion is `G1 Z40` then a single travel to bed centre (175,175); reaching
    the front-left keep-out from there would require already being inside it.
  **Next:** user runs `FIRMWARE_RESTART`, then Step 6 verification.
- **2026-08-03** — **`FIRMWARE_RESTART` done; Klipper `ready`.** No config error, no Beacon
  conflict, nothing bdpressure-related in the log (the one `BlockingIOError` traceback present is
  an old `gcode_button` respond failure from a much earlier session, unrelated). `PA_STATE`
  returned `bd_pa state: STOP`.
  **But `PA_STATE` is not evidence of communication** — `get_status` reads the internal
  `last_state` flag and never touches the bus. Config parsed and module loaded is all we know.
  **Hazard found while establishing that, and it reorders the remaining work:** Klipper maps every
  I2C NAK to `shutdown()` (`src/i2ccmds.c`), and the module's homing hook issues `i2c_write`s on
  every homing move. If the sensor is not answering, **every `G28` shuts down the toolhead MCU.**
  Step 6 rewritten: confirm comms with `SET_BDPRESSURE NAME=bd_pa COMMAND=READ VALUE=0` while cold
  and idle, **before homing**. This also supersedes the Step 4 claim that the homing hook "cannot
  stall or error out a homing move" — it cannot block, but it can shut the MCU down.
  Also noted for later: the toolhead MCU reports `BUS_PINS_i2c3_PB3_PB4`, so PB3/PB4 are a
  hardware I2C bus too. Software I2C stays for now; hardware I2C is an option if bit-banging
  proves noisy.
- **2026-08-03** — **🎉 I2C confirmed working at 3.3V.** `SET_BDPRESSURE COMMAND=READ VALUE=0`
  returned `bd_pa:` with an empty payload **and did not shut down the MCU**. That absence is the
  result: an unwired or unpowered sensor leaves SDA pulled high, which
  `i2c_software_read_ack` turns into `shutdown("I2C START READ NACK")`. Surviving the transaction
  means the device acknowledged its address. The empty payload is expected — `_measure_data` is
  only populated once a measurement is running.
  **This validates the whole wiring decision:** the LP5907 in dropout at 3.3V is powering the
  sensor's STM32C011 well enough for it to run and respond, exactly as the schematic analysis
  predicted. The 5V escalation path stays documented but is not needed so far.
  **Next:** `COMMAND=START` to read the `_version` string (positive confirmation rather than
  inferred-from-absence-of-shutdown), then `COMMAND=STOP` to re-energize X/Y.
- **2026-08-03** — **✅ STEP 6 PASSED.** `COMMAND=START` returned `.cmd_start i2c: pandapi3dv1` —
  the version string, actively produced. Positive end-to-end confirmation of bus, address and the
  sensor's STM32C011 running on the 3.3V feed. Homing is safe from here.
  Pre-Step-7 checks: `sync_drive: true` (gear motor synced to extruder, so the sweep's ~199 mm is
  fed by the MMU rather than dragged through the 2 m bowden); MMU reports `filament: Loaded`,
  `tool: 0`. Purge target chosen: **front-centre (175, 40) at Z40**, now the wrapper's default.
- **2026-08-03** — **First run: sweep executed correctly, sensor returned no data.** Filament
  purged as expected; all 50 steps ran (`pressure_advance` walked 0.000 → 0.098 in 0.002 steps,
  confirming the macro and patched parameters are correct), but **every one of the 50 `bd_pa:`
  lines was empty** and `STOP` reported `No PA calibration data or number is <=5`. Evidence from
  Moonraker's `gcode_store`, not inferred.

  **This is a sensor/signal problem, not a macro or I2C problem.** Traced through `firmware_src/`,
  which is authoritative:
  - `Receive_D` in `main.c` is the I2C register file: `version[16]` @0, `measue_data[32]` @16,
    `status_clk` @48, `out_data_mode` @49, `THRHOLD_Z` @50, `range` @51, `set_normal` @52,
    `invert_data` @53. Every `BDP_REGS` entry in `bdpressure.py` matches **except**
    `_measure_data`, which Python puts at **15** while the struct and the firmware's own
    `sprintf(ram_i2c + 16, "R:...")` put it at **16**.
    ⚠️ **This off-by-one is real but is NOT the cause** — `version[]` is zero-padded past
    "pandapi3dv1", so the stray leading byte is a NUL that `.strip('\0')` removes. Recorded so a
    later session doesn't chase it as the fix.
  - The result string is written only by `get_low_value()`, which `Pressure_advance()` calls only
    when `has_plus()` returns non-zero. `has_plus()` requires the signal to sit **below**
    `normal - threshold` for six consecutive samples. Empty data at every step therefore means
    **the firmware never saw a downward pressure excursion.**
  - Sampling is not the bottleneck: PA mode runs `ADS1220_Init(4, 0x34)` (continuous, ~175 SPS)
    and each step lasted ~2.8 s ≈ 490 samples against a 768-sample buffer.
  - `threshold` is **not** our `thrhold:` setting — it is auto-derived in `find_normal()` as
    `(normal - min_t)/2` clamped to [2,10]. `thrhold: 4` maps to `THRHOLD_Z` @50, the *endstop*
    threshold, irrelevant to PA exactly as the config comment says.

  **Hypotheses, in the order worth testing:**
  1. **Mechanical — the load path bypasses or over-compresses the gauge.** Highest prior: the
     cowling is a custom design, and Step 3's own warning was that over-long M2.5 screws can crush
     the PCB/strain gauge. If the hotend is clamped by the cowling rather than loaded through the
     groove-mount sensor, extrusion force never reaches the gauge. Free to check.
  2. **Signal polarity.** `main.c` does `if(PolarFlag == R_CMD.invert_data) tempA = -tempA;` and
     `has_plus()` only detects *downward* excursions. `bdpressure.py` never writes `invert_data`
     (@53), so if this mounting produces an upward excursion the symptom is exactly what we saw.
  3. Signal amplitude below the auto-threshold.

  **Blocker: no raw-signal visibility.** The vendor's diagnostic is
  `tool/BDPressureMonitor_C011_32KB.py` over USB, and the USB path is unavailable here (CH340E
  strapped for 5V won't enumerate at 3.3V; the only downstream USB port is the Beacon's). This is
  the first real cost of the I2C + 3.3V choice — correct on the electrical merits, but it
  forecloses the vendor's debug tooling. `bdpressure.py` exposes no arbitrary register read/write,
  so testing hypothesis 2 requires a small local patch to the module.
  **Next:** mechanical check first (free), then a debug patch if needed.
- **2026-08-03** — **Moved to bench diagnosis over USB-C; no module patch needed after all.**
  Maintainer unplugged the I2C connector (sensor now electrically isolated from the printer) and
  proposed driving it from a separate computer over USB-C. Better than patching `bdpressure.py`:
  USB-C VBUS supplies the sensor its designed **5V**, so the LP5907 runs in regulation, and the
  CH340E enumerates — the exact combination that was unavailable while it hung off the toolboard.
  With I2C unplugged there is no backfeed path, so USB-C is now safe to use.
  **The firmware's UART command set makes both hypotheses directly testable** (`process_cmd` in
  `main.c`, 38400 8N1): `d;` streams raw ADC continuously, `D;` stops it, `l;`/`e;` select PA vs
  endstop mode, **`i;`/`I;` flip polarity live**, `N;` re-zeros the baseline, `<n>;` sets
  `THRHOLD_Z`. So hypothesis 1 (mechanical) is "does the number move when you press the nozzle"
  and hypothesis 2 (polarity) is "which direction does it move, and does `I;` fix it" — no code
  changes to the Klipper module at all.
  Wrote `bdp_monitor.py` (scratchpad → `/tmp/bdp_monitor.py` on the Pi): terminal-based live
  monitor — auto-detects the CH340, fixes a baseline, and shows current/delta/span with a
  baseline-centred bar so the *direction* of excursion is obvious. The vendor's own tool needs
  Tkinter + matplotlib + a display, which a headless Pi does not have. Promote it to `tools/` if
  it earns its keep.
  ⚠️ **`[include bdpressure.cfg]` commented out in `overrides.cfg` while the sensor is unplugged.**
  Non-optional: the module's homing hook issues `i2c_write`s on every homing move, and with
  nothing on the bus those NAK → `shutdown()`. Left enabled, **every `G28` would shut down the
  toolhead MCU.** Needs a `FIRMWARE_RESTART` to take effect, and uncommenting when the sensor goes
  back on the toolboard.
- **2026-08-03** — **⛔ ROOT CAUSE FOUND: the strain gauge's P+ excitation lead is open.**
  Maintainer confirmed it visually with a macro photo: the leftmost lead has separated from its
  pad, while all four gauge grids are intact. **The sensor was never capable of producing a
  reading** — the bridge had no excitation, so every measurement was of an unpowered bridge, which
  is exactly why I2C, addressing, the version string and the whole software stack all checked out
  perfectly while `measue_data` stayed empty for all 50 sweep steps.
  This retrospectively explains everything and closes the three-hypothesis list: it was neither the
  cowling load path nor polarity. Note for anyone reading the earlier entries: a P+ open produces
  **zero** differential (both taps pulled to GND through the surviving lower arms), not a railed
  one — which is why the symptom looked so benign.
  **Runbook is ON HOLD pending replacement hardware.** Nothing else is outstanding: Steps 1–6 are
  complete and validated, and Step 7 is written and offline-tested.

  **Replacement research (done 2026-08-03) — do not re-derive this:**
  - **Mainline Klipper already has first-class load-cell support** on this install:
    `load_cell.py`, `load_cell_probe.py`, plus ADC drivers `ads1220.py`, `hx71x.py`,
    `ads131m0x.py`, and `docs/Load_Cell.md`. Notably `ads1220.py` is the *same ADC* the
    BDPressure E uses.
  - **But it is strictly for probing and force measurement — there is no pressure-advance
    linkage** (`grep -rli pressure_advance klippy/extras/load_cell*.py` → no match). PA-from-force
    is the BDPressure firmware's own algorithm and has no mainline equivalent.
  - **Therefore a load-cell hotend/toolhead is the wrong replacement.** It would deliver nozzle
    probing, which Karman already has working and validated via Beacon contact, and would *not*
    deliver the PA calibration that is this objective's entire point. Like-for-like replacement of
    the PandaPi3D unit is the only route to the original goal.
  - The BDPressure's ADS1220 sits behind the sensor's own STM32C011 on SPI, so the board cannot be
    repurposed as a native Klipper `[load_cell]` device either.
  - **Interim fallback, already installed:** Klippain ships
    `macros/calibration/calibrate_pa.cfg` — the conventional test-pattern PA calibration. Costs
    nothing and gives a usable number without any new hardware.
- **2026-08-08** — **Replacement ordered; machine reverted to its pre-BDPressure state.**
  Maintainer returned the toolhead hardware to its original configuration so other work can
  continue while waiting. Config reverted to match — deliberately *reversibly*, since this is
  temporary:
  - **Verified already inert before changing anything:** Klipper reports `ready`/`standby` with
    **no `bdpressure` object loaded**, so the commented-out include had already taken effect and
    the `G28`-shutdown hazard is gone. Homing and printing are safe.
  - `overrides.cfg` — include stays commented; the note was rewritten from "unplugged for bench
    diagnosis" to the actual current state (sensor off the machine, replacement on order,
    re-enable and resume at Step 7). The NACK→`shutdown()` warning is retained, because that is
    the load-bearing safety fact.
  - `moonraker.conf` — `[update_manager bd_pressure]` **commented out, not deleted.** Extra
    benefit beyond tidiness: it freezes `~/bd_pressure` at `5e94c64` (2026-07-30), the exact
    revision audited in this runbook, so the replacement gets fitted against known code rather
    than whatever upstream has become. Re-read `install.sh` before re-enabling if time has passed.
  - **Kept deliberately:** `bdpressure.cfg` (finished, offline-validated work — nothing includes
    it, so it is inert); the `klippy/extras/bdpressure.py` symlink (Klipper only imports extras
    named by a config section, so it is inert too); and the `tools/render_macro.py` improvements,
    which are **generic tooling** (`action_*` stubs + `--params`), not BDPressure-specific —
    confirmed by diff.
  - **Restart needed:** Moonraker only. The Klipper-side edit was comment-only and the config was
    already applied, so no `FIRMWARE_RESTART` is required.
  **To resume when the replacement arrives:** fit and wire per Step 3 (re-measure nozzle Z against
  the 10.4 mm reference), uncomment both blocks, restart Moonraker and Klipper, re-verify comms
  per Step 6, then Step 7.
- **2026-08-12** — **Replacement sensor works, and the transport is changed to USB.**
  Maintainer bench-tested the new unit standalone over USB-C with `~/bdp_monitor.py` and it
  **responds as expected** — the first working baseline this objective has had. (The monitor was
  improved first: silence now shows a live `bytes=N` counter and an explicit diagnostic after 4 s,
  because "no output" previously looked identical to "port stolen", "not powered" and "sensor
  dead". Both paths verified against a pty.)
  **Transport decision reversed to USB** — rationale recorded in Pre-resolved decisions above.
  Config reconfigured accordingly:
  - `bdpressure.cfg` — section is now `port: usb` + explicit `serial:` by-id path + `baud: 38400`.
    Header rewritten: the 3.3V/ratiometric note is replaced by the USB rationale, plus a warning
    that `port:` must be **exactly** `usb` (startup matches with `in`, runtime methods with `==`,
    so `usb0` would initialise and then silently do nothing).
  - `overrides.cfg` — `[include bdpressure.cfg]` **re-enabled**. The old I2C NAK→`shutdown()`
    hazard is gone; two milder ones documented in its place: with no device present pyserial
    raises at startup so **Klipper will not start**, and the homing hook writes to the port with
    no error handling so a cable pulled mid-session makes the next `G28` throw.
  - **Port ownership documented** as a first-class constraint: Klipper now holds `/dev/ttyUSB0`,
    so `~/bdp_monitor.py` (and any future logging tool) cannot open it. Comment the include out
    and `FIRMWARE_RESTART` before bench diagnostics.
  - All five macros re-render clean; `render_macro.py --selftest` 29/29. Macros were unaffected —
    they only ever touched the sensor through `SET_BDPRESSURE`, which is transport-agnostic.
  - `moonraker.conf` — `[update_manager bd_pressure]` **left commented**, still freezing
    `~/bd_pressure` at the audited `5e94c64`. Re-enable once the new sensor is proven in-place.
  ⚠️ **Not yet applied — and blocked.** The printer is in `shutdown` with an unrelated fault:
  `MCU 'toolhead' shutdown: ADC out of range`, extruder thermistor reading ~10⁷ °C and fluctuating
  — an open thermistor circuit, almost certainly `TH0` (JST-PH 2P, `PB12`) disturbed during the
  toolhead rework. That must be fixed before any `FIRMWARE_RESTART` can succeed.
  **Next:** fix the thermistor, `FIRMWARE_RESTART`, confirm the module loads on USB, then Step 7.
- **2026-08-12** — **Thermistor fixed, module loads on USB, first `KARMAN_PA_CALIBRATE` failed —
  cause: the sensor's internal FPC came unplugged.**
  Startup verification all passed: printer `ready`, extruder back to a sane 25.5 °C,
  `bdpressure bd_pa` in the object list, and klippy (PID 742) holding `/dev/ttyUSB0` — which on
  USB is real evidence, since `serial.Serial()` runs in `__init__` and a bad path would stop
  Klipper booting. A manual `COMMAND=START` returned `.cmd_start usb: PA mode`.
  Then `KARMAN_PA_CALIBRATE NOZZLE_TEMP=260` failed. `klippy.log` was decisive — the module logs
  every retry:
  ```
  attempt 1/5, response=''
  attempt 2/5, response='PA mode\nPA mode'   <- the earlier manual run, cold, worked
  attempt 1..5/5, response=''                <- the macro run: zero bytes, all five
  ```
  `START` failing left `state` at `"STOP"`, and every `PA_E` step is wrapped in
  `{% if status=='START' %}`, so **all 50 steps silently evaluated to nothing** — only the
  unconditional pre-loop moves ran (~15 mm extruded, not 480 mm³). Recovery homing ran fine.

  ### ⚠️ Diagnostic signature worth remembering
  **"Serial port opens and stays healthy, but the sensor returns zero bytes" means the internal
  FPC between the daughterboard and the sensor board, NOT the USB link.** The CH340 lives on the
  daughterboard and is powered straight from VBUS, so it enumerates, holds the port and throws no
  `SerialException` regardless of whether the ribbon to the STM32C011 is seated. USB has no
  visibility of that break at all.
  The trigger was **toolhead motion** — it worked on the bench and went silent the first time the
  macro moved the toolhead (`G28` + travel to 175,40). A partially-seated FPC is exactly the kind
  of fault motion shakes loose, so **strain-relieve that ribbon** before trusting it.

  ### Hypothesis that was wrong, recorded so it isn't chased again
  I proposed thermal clock drift: the sensor's STM32C011 runs on **HSI (internal RC, no crystal —
  `RCC_OSCILLATORTYPE_HSI`)** and the UART is bit-banged off TIM1 at `IO_USART_SENDDELAY_TIME 26`
  µs ≈ 38461 baud, so at 260 °C at the groove mount HSI drift could plausibly break 8N1 framing.
  Plausible mechanism, **not the cause here.** Worth keeping in mind only if silence ever recurs
  *with the FPC verified seated and correlating with temperature rather than motion*. If that ever
  happens, note that I²C would be immune — it is synchronous and clocked by the master, so the
  sensor's own oscillator accuracy is irrelevant to framing.
  **Next:** after reboot, re-verify `COMMAND=START`, then **re-test after a `G28` and travel** —
  the failure only appears once the toolhead moves, so the regression test must include motion.
- **2026-08-13** — **Working sensor, two vendor bugs found, and the sweep made usable.**
  The FPC was reseated and the sensor produced data. Three things had to be fixed before any
  number could be trusted:
  1. **Yield.** At 14.4 mm³/s only **11 of 50** steps produced a usable read. Cause: the vendor's
     fixed 20/40/20 mm pattern makes the extrusion event's *duration* inversely proportional to
     flow, and the firmware analyser rejects events longer than ~0.68 s (`low_count > 2*SAMPLES`).
     Fix: scale every distance by `MAX_VOLUMETRIC/25`, holding event duration at ~2.06 s for any
     flow. Yield went to **41 of 42**. A `GEOM_SCALE` override was added, because scaling shortens
     the slow segments and any test that reads plateau *levels* needs them long (the melt has a
     slow relaxation mode, τ ≈ 2.8 s).
  2. **The vendor picks the wrong answer.** `cmd_stop` scanned backwards for the last row with
     `Hk < 5` then searched only from there to the end — which is always the tail of the sweep,
     the highest PA values, chosen before any physics. On a clean 41-point sweep whose `Hr−Hl`
     crossed zero at **0.031 ± 0.003** it returned **0.076**, then silently applied it with
     `SET_PRESSURE_ADVANCE`. Replaced with a least-squares solve for the zero crossing, with
     refusal conditions (needs a real sign change, a 3σ slope, a crossing inside the swept range),
     and applying the result is now opt-in.
  3. **PA was left mangled after every sweep.** `PA_E` sets PA on each step and nothing restored
     it, so the machine sat at the top of the swept range. `PA_CALIBRATE` now restores the
     configured value and says so.
  15 sweeps were then run across 10–25 mm³/s and accel 1500–6000, all at 275 °C. Two competing
  explanations for the flow dependence were separated by measurement rather than argument:
  `pressure_advance_smooth_time` attenuation predicted 0.0592 at 14.4/6000, and the sweep measured
  **0.0306 ± 0.0030** — falsified at 9.5σ. What survives is `PA ∝ Q_peak^(n−1)` with the exponent
  taken unchanged from an independent waveform fit; it predicted four unmeasured cells blind at
  χ²/dof 0.27. Full record: `docs/pa_physics.md`, `physics/pa_sweeps.json`, `physics/pa_law.json`.
- **2026-08-14** — **Verified in real prints, and the default PA changed.**
  Three test prints (adaptive PA, flat 0.032, PA disabled) confirmed from `klippy.log` that the
  slicer's intent actually reaches the nozzle — and exposed that it usually does not: Klippain's
  `START_PRINT` applies `material_parameters` over both `[extruder]` and anything the slicer set
  before it, so the first "no PA" print silently ran at **0.048**, the *highest* PA of the three.
  A `SET_PRESSURE_ADVANCE ADVANCE=0` after `START_PRINT` in the slicer's machine start g-code
  fixes it; verified live at 0.000.
  **ABS `pressure_advance` changed 0.0480 → 0.032** in `variables.cfg` (and `[extruder]` in
  `overrides.cfg` kept in step, since that is what `PA_CALIBRATE` restores to). 0.032 is the single
  compromise across the measured 0.028–0.039 range, never worse than ~20% off anywhere in it.
  All verification items passed; a 2-colour print ran correctly and its later nozzle clog is a
  pre-existing recurring fault, tracked separately, not a regression from this work.
  **Objective complete.**
- **2026-08-14** — **Three test prints visually compared.** Model:
  [PA torture test, Printables #437927](https://www.printables.com/model/437927-pressure-advance-torture-test).
  No-PA vs either PA-enabled print is dramatic, as expected. **Flat 0.032 vs the adaptive matrix is
  subtle** — visually close, matrix still preferred by eye. Cause identified, not a measurement
  problem: Orca's `dont_slow_down_outer_wall` is enabled, which keeps outer-wall speed — and so the
  flow and accel-burst PA acts on — close to constant across the part. Most of what the eye actually
  sees is the outer wall, and at nearly-constant flow/accel the matrix and the flat value sit close
  to the same point in the table (docs/pa_physics.md §5.3). The matrix's larger, measured effect
  (0.028–0.039 across the swept range) is concentrated on faster/slower internal features and any
  print without that setting enabled — see `docs/decisions.md` for the record, kept so a future
  session doesn't mistake this for the calibration not working.

## ⚠️ Pending — FIRMWARE_RESTART needed before the 0.032 value is live
Checked directly against the running Klipper session on 2026-08-14 (query
`gcode_macro _USER_VARIABLES` and `configfile.settings.extruder`): the last restart was
**07:29:46**, and the `variables.cfg` / `overrides.cfg` edits landed at **16:05:01** — after it.
The **live** ABS `material_parameters.pressure_advance` is still **0.048**, and live
`configfile.settings.extruder.pressure_advance` is still **0.035**. The files on disk are correct;
the running printer has not picked them up. **Run `FIRMWARE_RESTART`, then re-query
`gcode_macro _USER_VARIABLES` to confirm ABS reads 0.032**, before printing ABS and trusting the
default PA. (No physical risk in the meantime — the printer is idle, `standby`, both heaters at
target 0 — this is a config-drift gap, not a safety issue.)

## Remaining follow-ups (not blocking; this runbook is closed)
- **The three module patches live outside this repo.** Mirrored to a fork of `markniu/bd_pressure`
  (see `docs/pa_physics.md` Appendix A); `update_manager` stays commented out so an update cannot
  overwrite them. A Pi reimage still needs them restored by hand.
- **The model does not reproduce the firmware's discriminator.** It needs a slow relaxation mode
  and the right transient shape near the dip edges. Only matters if the model is ever used to
  predict what a sweep will *conclude* rather than what the trace looks like.
- **`sweep_25.json` is not a clean hold-out** — different nozzle temperature and an ambiguous
  acceleration. A matched-temperature sweep at 25 mm³/s would close the one real gap in the model's
  cross-flow validation.
- **A refit helper is not written.** Adding a condition today means running the sweep, appending a
  row to `physics/pa_sweeps.json` by hand, and re-running the fit ad hoc.
