# Runbook — KAPAT on the BDPressure: a working PA-tuning interface

**Objective:** start a PA tuning sweep on Karman from a browser and get a K back. The sweep is
KAPAT's in-air square wave (`GRID` or `BISECT_SECANT`), measured by the existing **BDPressure E**
through a small host-side shim that makes it look like a Klipper load cell. "Working" means: with
ABS at 275 °C, three `GRID` sweeps started from the interface each return a K in 0.020–0.050 with
σ ≤ 0.004, and the KAPAT web page at `http://192.168.1.240/kapat/` shows those runs.
**Issue:** td-8dd427 · **Created:** 2026-11-19
**Prerequisites:**
- The BDPressure plugged in, with `[include bdpressure.cfg]` active and `KARMAN_PA_CALIBRATE`
  working. That is the state since 2026-08-12 (`docs/runbooks/done/bdpressure-pa-sensor.md`).
- ABS loaded at the toolhead (`filament_switch_sensor toolhead_sensor` reads detected). Any spool
  of the LDO ABS used for the August data is fine.
- Printer idle. Steps 6 and 11–14 restart Klipper or run sweeps, so nothing may be printing.
- The maintainer at the printer for Steps 4 and 9–14. They need about 90 minutes there.
- No other issue has to close first. This blocks **td-746307** (the per-filament SOP), which will
  use this interface to do its sweeps.

Reference, link don't re-read everything:
- KAPAT upstream: https://github.com/vzagranichnyy/KAPAT. **Pin it to commit `a33957d`**
  (2026-08-07); that is the version this runbook was written against.
- The research behind this runbook is in the separate workstation repo
  `/home/kyle/projects/auto-pa-tuning`. The sensor facts come from
  `docs/research/04-bdpressure-signal-chain.md` and `08-phase1-measurements.md`, and the interview
  decisions from `06-decisions.md`. The sensor command sequence comes from
  `tools/bdp_noise_capture.py`.
- `docs/pa_physics.md` (this repo): the ABS law and what the sensor cannot measure.

Progress is logged to the issue (`td log`), not here. This file is the plan.

> **As-run corrections (2026-11-19 execution, details in `docs/decisions.md` 2026-11-19):**
> - The test temperature is **265 °C**, not 275. The installed nozzle is now the 0.4 CHT BiMetal,
>   where 265 °C matches 275 °C on hardened steel. `KARMAN_KAPAT` defaults to 265.
> - Step 1: stamp samples with `reactor.monotonic()` (CLOCK_MONOTONIC_RAW), **not** `time.monotonic()`.
> - Step 8: the page never shows the text `bdp_load_cell`. Check `has_load_cell` via Moonraker instead.
> - Step 10 result: `invert: True`.
> - The open KAPAT tab sends `M104 S0` after every sweep, so back-to-back runs cold-soak.
> - BISECT_SECANT completes but reads about 2× high on this sensor (integral-area bias). GRID +
>   composite is the usable mode.

## Scope

Shim written and tested offline → KAPAT installed (pinned) with its web UI → shim deployed → safe
calibration position written → `kapat.cfg` included and Klipper restarted → sensor self-test
(rate, sign) → wrapper-macro sweeps on ABS → cross-check against the vendor method → one sweep
started from the KAPAT web page → verified.

**What "fast" cost.** This is a concept, not the finished tool that `auto-pa-tuning` decision 9
plans, which would replace the vendor module completely. The shim and the vendor module **share
the serial port**, and the shim opens it only while a KAPAT sweep is collecting. KAPAT's in-air
**wobble** stands in for the XY de-energise trick (see Pre-resolved decisions). The live force
chart in KAPAT's UI will stay empty, because the shim does not implement `load_cell/dump_force`.

## ⚠️ Out of scope — do not touch

- **`~/bd_pressure` and its three local patches; `[update_manager bd_pressure]` stays commented
  out.** Any `git pull` there silently reverts the patches, and the vendor method returns wrong
  answers. The symptom is bad data, not an error (`docs/decisions.md` 2026-08-12, `pa_physics.md`
  Appendix A).
- **`bdpressure.cfg` as a whole**: `[bdpressure bd_pa]`, `probe_mode_on_homing: 0`, `debug: 0`,
  `port: usb`, and `KARMAN_PA_CALIBRATE` with its soak defaults (`soak_cold: 240`,
  `soak_hot: 30`, `prime_mm: 40`). The soak values are measured, not guessed: a sweep during the
  groove-mount drift reads high (decisions 2026-08-12). The vendor method stays as the cross-check
  in Step 13, so it must keep working unchanged. The new wrapper **reads** these soak variables
  and does not copy them.
- **The vendor module's "Calc the best Pressure Advance" verdict and `apply_result` off.** Never
  auto-apply a PA result (decisions 2026-08-13). The same rule applies to KAPAT: `apply: False`.
- **`[extruder] pressure_advance: 0.032` in `overrides.cfg`, and every Orca filament preset.** The
  concept measures only. Applying a result is td-746307's job.
- **`variable_material_profiles_enabled: False`** (decisions 2026-09-23). Leave Klippain's
  per-material table dormant.
- **`physics/` (`pa_law.json`, `pa_sweeps.json`, `melt_model.py`, `fit_model.py`) and the ABS fit
  `n = 0.653`, `C = 0.1032`.** It is an independent fit that survived a blind prediction. KAPAT
  results do not go into `pa_sweeps.json` in this runbook.
- **KAPAT's own source files.** The shim adapts to KAPAT; KAPAT is not patched. If something
  looks like it needs a KAPAT patch, stop and escalate (see Step 11).
- **`~/mainsail`.** Install KAPAT with `--web=kapat` only. `--web=mainsail` or `--web=both`
  **replaces** the Mainsail install.
- **Beacon, MMU / Happy Hare, Blobifier, purge and `START_PRINT` config.** These are unrelated and
  validated.
- **The old SOP steps** (refit helper, two-corner gate, PETG). They belong to td-746307 and
  `docs/runbooks/pa-calibration-sop.md`, which runs after this.

## ⚠️ Hazards in play

Copied from the `CLAUDE.md` hazard register, plus one new one this work creates.

- **NEW — KAPAT's default calibration position is `(0, 0, Z10)`.** That is inside the front-left
  keep-out. `KAPAT_SWEEP TARGET_TEMP=…` (which the web UI's start button sends) moves there with a
  straight `G1 … F3000` whenever `~/printer_data/kapat/settings.json` is missing or lacks
  `calibX`/`calibY`/`calibZ`. **Step 5 writes that file before Klipper ever loads KAPAT. It is a
  hard gate.** Never delete the file, and never set those fields from the UI to anything other than
  `175 / 40 / 80`. **Always-on** while KAPAT is installed.
- **Front-left, x<10 / y<17, at ANY Z** — the Filamatrix cutter arm on the toolhead strikes the
  front-left XY idler. Permanent toolhead geometry. **Always-on**: applies to every move.
- **The y_max feature row** (tray ~x2–17, shaker x4, rest x45, brush x53–88) — must be entered in +Y
  through a **clear lane (15<x<40, or x>95)**, then slid in X. Never approach a feature head-on.
  **Always-on** near y_max. Here: KAPAT's start button makes a straight diagonal move to the
  calibration position. Starting it with the nozzle seated in the rest drags it out sideways. The
  wrapper refuses to run with Y > 300. **Before using the web UI's start button, the toolhead must
  already be at the calibration position**, which is where the wrapper leaves it.
- **Umbilical + PTFE above the gantry** — they limit how high Z can safely go, and the umbilical
  is the only toolhead protrusion besides the cutter arm. The clearance has **not been measured**,
  so treat moves near Z max as unsafe until it is. **Conditional**: high Z. Here: Z80 is the
  existing `KARMAN_PA_CALIBRATE` height, used for dozens of sweeps. Do not raise it.
- **A forgotten preheat keeps heating** (maintainer-observed). `[idle_timeout]` should
  `TURN_OFF_HEATERS` after 1800 s, but something stops it, and the cause hasn't been diagnosed.
  **Always-on** until fixed. Here: KAPAT and the wrapper leave the nozzle at 275 °C after every
  sweep, on purpose, for back-to-back runs. **Step 15 turns the heaters off. It is not optional.**
- **Unattended ABS/ASA relies on the external exhaust duct** (slight negative pressure, vented
  outside). Klipper doesn't control it. **Conditional**: ABS/ASA. Here: each GRID sweep extrudes
  about 400 mm of ABS in air. Keep the exhaust running and the maintainer present.
- **MMU load/swap commands outside a print can run as cold as ~200 °C** — too cold for ABS in this
  UHF melt zone (grinds or jams). Preheat to the gate's material temperature first.
  **Conditional**: bench MMU operations. Here: if ABS has to be loaded for this test, run
  `M109 S265` before `SWAP TOOL=n`.
- **Restarting Klipper mid-print** (`FIRMWARE_RESTART`, a service restart) kills the print. Check
  `print_stats.state` first. **Conditional**: while printing. Step 6 restarts the host.
- **`~/bd_pressure` carries three local patches.** Any `git pull` there silently reverts them and
  the PA sweeps return wrong answers. **Always-on**.
- **Beacon contact homing refuses above 180 °C** (from `KARMAN_PA_CALIBRATE`'s own warning, not
  the register). A hot, unhomed printer cannot `G28`. The wrapper refuses to home when the nozzle
  is above 170 °C, and an error here is safe.
- Not in reach: the Beacon dent at (175,175) (nothing here probes), flashing order, Happy Hare
  branch, `klipper-backup` (nothing here touches `~/config_backup`).

## Pre-resolved decisions

Each is a default the maintainer can veto in one line.

- **KAPAT unmodified + a load-cell shim, not a rewrite.** KAPAT finds its sensor with
  `printer.lookup_object('load_cell')` (`klipper_extras/kapat/__init__.py` `_handle_ready`). The
  shim registers itself under that name and implements only what KAPAT calls:
  `get_collector()`, `start_collecting(min_time)`, `collect_until(print_time)` returning
  `(rows, errors)`, and `is_started`. It also provides `name` and `sensor.sensor_type`. Rows are
  `[time, grams, counts, tare_counts]`, and KAPAT computes `force = -(counts - tare_counts)`.
  This is option A3 from `auto-pa-tuning` `05-paths-forward.md`. Research graded it "high" before
  `08-phase1-measurements.md` showed host timestamps with a per-sweep linear fit are good to
  0.09 ms rms. That removed its main risk.
- **The interface lives on Karman**: KAPAT's standalone web UI at
  `http://192.168.1.240/kapat/` (History, Profiles, Analysis, start button), plus the
  `KARMAN_KAPAT` macro in Mainsail's macro panel, which gives a parameter form. Nothing is
  installed on the workstation.
- **Start cold sweeps with `KARMAN_KAPAT`, not the web UI's start button.** KAPAT's own prep only
  homes, moves and runs `M109`, with no soak, and an unsoaked sweep reads high. The wrapper copies
  `KARMAN_PA_CALIBRATE`'s prep (guards, position, heat, soak, prime), then calls `KAPAT_SWEEP`. Use
  the start button only for back-to-back runs once the first wrapper run has soaked the hotend.
- **Use the wobble, not XY de-energise.** `auto-pa-tuning` decision 10 chose de-energise because
  only it reproduces print-like accelerations. KAPAT has a 0.05 mm wobble at accel 1000 built in,
  so the concept uses that. The cost: acceleration is not a test variable yet. Revisit in
  td-746307.
- **`max_extrude_cross_section: 200` in `[extruder]`**, from KAPAT's example config. The warm-up
  leg puts about 3.2 mm of filament on a 0.05 mm wobble. That ratio needs at least about 154 mm²
  (KAPAT refuses to run otherwise and prints the exact need). This only loosens a gcode
  sanity check. Sliced prints are nowhere near it. Remove it if the concept is abandoned.
- **Shim code lives in `/home/kyle/projects/auto-pa-tuning`** (its decision 8), deployed to
  `~/auto-pa-tuning/` on the Pi with `rsync` and symlinked into `~/klipper/klippy/extras/`, like
  every other add-on on Karman. Karman's config repo gets only `kapat.cfg` and its include.
- **Test condition: ABS, 275 °C**, the temperature of every valid August sweep. 265 °C, the
  temperature the ABS preset prints at, is not part of this runbook.
- **KAPAT defaults otherwise** (`VFR 19.24`, `VFR_LOW 1.92`, `TSLOW 1.0`, `TFAST 0.25`,
  `CYCLES 8`, `K 0.000–0.080 step 0.005`). A GRID sweep then extrudes about 397 mm, just under
  KAPAT's 400 mm cap, and takes about 3.5 minutes.

---

## Step 1 — Write the shim and its offline tests *(model, workstation)*

Work in `/home/kyle/projects/auto-pa-tuning` (a plain local git repo; git is fine there because it
is not on the mount). Before writing, read KAPAT's `klipper_extras/kapat/__init__.py` at commit
`a33957d`, lines 150–170 (`_handle_ready`) and 285–620 (`cmd_KAPAT_SWEEP`, `_probe_k`), so the
shim matches how it is called. To get the source **without git on the mount**:
```
mkdir -p /home/kyle/projects/auto-pa-tuning/references/repos && cd /home/kyle/projects/auto-pa-tuning/references/repos && curl -sL https://codeload.github.com/vzagranichnyy/KAPAT/tar.gz/a33957dfb8e60cac07dc5ab057a6ebc45765a629 | tar xz
```

Create `klipper_extras/bdp_load_cell.py`, a Klipper extra loaded by a `[bdp_load_cell]` section.
Contract:

| Item | Requirement |
|---|---|
| Config | `serial` (default `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`), `baud` (default 38400), `invert` (bool, default False), `time_offset` (float s, default 0.0, added to every sample time), `idle_stop` (s, default 10) |
| Registration | `printer.add_object('load_cell', self)` in `__init__`. Attributes `name = 'bdp_load_cell'` and `sensor` with `sensor_type = 'bdpressure_uart'`. |
| Startup | **Does not open the port at startup.** A missing sensor must not stop Klipper from starting. |
| Stream on | On the first `start_collecting`, open `serial.Serial(port, baud, timeout=0.05)`, then use the exact sequence from `tools/bdp_noise_capture.py`: write `b"D;"`, wait 0.3 s, write `b"l;"` (PA mode, ~88 Hz), wait 1.5 s, write `b"d;"` (raw on). Use `reactor.pause`, never `time.sleep`, on the reactor thread. |
| Reader | A daemon thread reads bytes, splits on `\n`, and keeps lines that parse as an int after stripping whitespace and a trailing `;`. It skips `R:` lines and junk. It appends `(time.monotonic(), value)` under a lock, and also counts any line it could not parse. |
| Clock | Inside `collect_until` (reactor thread only), fit `stamp = a + b·index` by least squares over the samples of this stream session, use the fitted stamp for each sample, add `time_offset`, and convert with `printer.lookup_object('mcu').estimated_print_time(fitted_stamp)`. |
| Sign | `counts = -value`, or `+value` if `invert: True`. `tare_counts` is `counts` of the first sample in the window, and `grams = -(counts - tare_counts)`. With the right sign, KAPAT's force rises when extrusion pressure rises. |
| `collect_until(print_time)` | Wait with `reactor.pause(reactor.monotonic() + 0.1)` until the newest sample's print time is ≥ `print_time`. If no new sample arrives for 2 s, raise `printer.command_error("bdp_load_cell: sensor stream stalled")`. Return `(rows, 0)`, where `rows` are the samples with `min_time ≤ t ≤ print_time`. |
| Collector | `get_collector()` returns a fresh object with `is_started`, `start_collecting(min_time)` and `collect_until(print_time)`. KAPAT sets `is_started = False` itself; allow that. |
| Stream off | A reactor timer: once no collector has been active for `idle_stop` s, write `b"D;"`, wait 0.3 s, write `b"e;"` (endstop mode, as the vendor module expects), then close the port. Do the same on `klippy:disconnect` and `klippy:shutdown`. |
| Faults | Wrap every port access. On `serial.SerialException` or `OSError`, close the port, mark the stream down, and raise `command_error` only from inside a command. Never let an exception escape an event handler or the timer (the 2026-09-03 G28 shutdown came from exactly that). |
| `BDP_LC_SELFTEST [SECONDS=5] [EXTRUDE=0]` | Collects for SECONDS and reports sample count, rate (Hz), the clock-fit residual (rms and max, ms), unparsed lines, and the mean and std of `grams`. With `EXTRUDE=1` it first collects 2 s idle, then queues `G1 E15 F125` (about 5 mm³/s, extrude-only, `M83`), collects through it, and reports `delta = mean(extruding) − mean(idle)`. Refuse `EXTRUDE=1` unless `printer.extruder.can_extrude` is true. |

Tests in `tests/test_bdp_load_cell.py` (pytest, run with `uv run --with pytest --with numpy --with pyserial pytest tests`):
- Line parsing: `"6891;"`, `"6891"`, `"R:1,2,3"`, `""`, `"garb;"`, and a partial line completed by the next read.
- Clock fit: replay `data/captures/2026-10-19_idle_cold_pa-mode_60s.tsv` (host stamp, raw line) and
  assert the fit residual rms < 0.5 ms and the rate is 87–89 Hz.
- Windowing and sign: synthetic samples with a step. Rows exclude anything outside
  `[min_time, print_time]`, and `-(counts - tare)` rises with the step when `invert` is False.
- A fake reactor and a fake mcu (`estimated_print_time = lambda t: t + 100`) are enough. Do not
  import Klipper.

**Done when** the tests pass. Commit in `auto-pa-tuning`:
`git -C /home/kyle/projects/auto-pa-tuning add klipper_extras tests && git -C /home/kyle/projects/auto-pa-tuning commit -m "feat: bdpressure load-cell shim for kapat"`
(that repo has no remote, so there is no push).

## Step 2 — Write `kapat.cfg` *(model, mount)*

Create `kapat.cfg` in the repo root. **Do not include it yet** (Step 6 does that).

```ini
#####################################################################
#   KAPAT (in-air PA sweep) measured by the BDPressure via bdp_load_cell
#####################################################################
# Concept, 2026-11. Runbook: docs/runbooks/pa-kapat-bdpressure-concept.md
# - bdp_load_cell (~/auto-pa-tuning/klipper_extras) makes the BDPressure look like a Klipper
#   load cell. It opens the CH340 only while a KAPAT sweep collects, and shares the port with
#   [bdpressure bd_pa]. Never run KARMAN_PA_CALIBRATE and a KAPAT sweep at the same time.
# - KAPAT (~/KAPAT, pinned a33957d) is unmodified. Results are never applied: apply: False.
# - ⚠️ ~/printer_data/kapat/settings.json MUST hold calibX 175 / calibY 40 / calibZ 80. KAPAT's
#   built-in default is (0,0,10), inside the front-left cutter keep-out.

[bdp_load_cell]
serial: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
baud: 38400
invert: False          # Step 10 of the runbook decides this
time_offset: 0.0

[kapat]
apply: False           # never auto-apply (docs/decisions.md 2026-08-13)
wobble_axis: Y
wobble: 0.05
accel: 1000

# KAPAT's wobble legs carry up to ~3.2 mm of filament per 0.05 mm of Y. Needs >= ~154 mm2.
[extruder]
max_extrude_cross_section: 200

[gcode_macro KARMAN_KAPAT]
description: Position, soak, prime, then run a KAPAT sweep on the BDPressure. Never applies the result.
gcode:
    {% set cal = printer["gcode_macro KARMAN_PA_CALIBRATE"] %}
    {% set nozzle_temp = params.NOZZLE_TEMP|default(275)|float %}
    {% set mode = params.MODE|default("GRID")|upper %}
    {% set filament = params.FILAMENT|default("ABS") %}
    {% set travel_speed = printer["gcode_macro _USER_VARIABLES"].travel_speed|default(300)|float * 60 %}
    {% set t_start = printer.extruder.temperature|float %}
    {% set soak = params.SOAK|default(cal.soak_hot if t_start >= nozzle_temp - 5 else cal.soak_cold)|int %}
    {% set homed = printer.toolhead.homed_axes %}

    {% if printer.print_stats.state == "printing" %}
        { action_raise_error("KARMAN_KAPAT: refusing to run during a print.") }
    {% endif %}
    {% if not printer["filament_switch_sensor toolhead_sensor"].filament_detected %}
        { action_raise_error("KARMAN_KAPAT: no filament at the toolhead sensor. Load with SWAP TOOL=n first.") }
    {% endif %}
    {% if mode not in ["GRID", "BISECT", "BISECT_SECANT"] %}
        { action_raise_error("KARMAN_KAPAT: MODE must be GRID, BISECT or BISECT_SECANT.") }
    {% endif %}
    {% if 'x' in homed and 'y' in homed and printer.toolhead.position.y > 300 %}
        { action_raise_error("KARMAN_KAPAT: toolhead is at Y>300 (y_max feature row). Run G28 first; it ends at the bed centre.") }
    {% endif %}
    {% if 'x' not in homed or 'y' not in homed or 'z' not in homed %}
        {% if t_start > 170 %}
            { action_raise_error("KARMAN_KAPAT: not homed and nozzle above 170C. Beacon contact homing refuses when hot. Cool down or home first.") }
        {% endif %}
        G28
    {% endif %}

    { action_respond_info("KARMAN_KAPAT: start nozzle %.1fC -> %.0fC, soak %ds, prime %.0fmm, MODE=%s at X%.0f Y%.0f Z%.0f"
                          % (t_start, nozzle_temp, soak, cal.prime_mm, mode, cal.purge_x, cal.purge_y, cal.purge_z)) }
    M107
    G90
    G1 Z{cal.purge_z} F1500
    G1 X{cal.purge_x} Y{cal.purge_y} F{travel_speed}
    M400
    M109 S{nozzle_temp}
    {% if soak > 0 %}
        { action_respond_info("KARMAN_KAPAT: soaking %ds (console will look idle)" % soak) }
        G4 P{soak * 1000}
    {% endif %}
    M83
    G1 E{cal.prime_mm} F300
    M400
    G4 P2000

    {% set extra = [] %}
    {% for p in ["VFR", "VFR_LOW", "TSLOW", "TFAST", "CYCLES", "KSTART", "KEND", "KSTEP", "WARMUP"] %}
        {% if p in params %}{% set _ = extra.append("%s=%s" % (p, params[p])) %}{% endif %}
    {% endfor %}
    KAPAT_SWEEP MODE={mode} FILAMENT={filament}_{nozzle_temp|int} APPLY=0 {extra|join(" ")}

    { action_respond_info("KARMAN_KAPAT: done. K is in the kapat report above and in http://192.168.1.240/kapat/ History. Nothing was applied.") }
    { action_respond_info("Nozzle is still at %.0fC. TURN_OFF_HEATERS when finished — idle_timeout is not reliable on this machine." % nozzle_temp) }
```

Validate the macro renders:
```
cd /home/kyle/projects/karman-printer-mnt/printer_data/config && uv run tools/render_macro.py --selftest
```
It must still pass (nothing regressed). If `render_macro.py` can render a named macro with
params, render `KARMAN_KAPAT` with `MODE=GRID` and with `MODE=BISECT_SECANT VFR=10`, and check the
`KAPAT_SWEEP` line. The `check-toolchange` hook may run the visualizer. This file adds no
toolchange motion, so it should report clean.

## Step 3 — Put KAPAT on the Pi, pinned *(model, over SSH)*

```
ssh ernst@192.168.1.240 'cd ~ && git clone https://github.com/vzagranichnyy/KAPAT.git && cd KAPAT && git checkout --detach a33957dfb8e60cac07dc5ab057a6ebc45765a629 && git log -1 --oneline'
```
Expected: `a33957d …`. Do **not** add an `[update_manager]` entry for KAPAT. It stays pinned.

## Step 4 — Run KAPAT's installer for the web UI *(human: it needs sudo, which needs a TTY)*

The maintainer runs this from a terminal on the workstation:
```
ssh -t ernst@192.168.1.240 'cd ~/KAPAT && ./install.sh --web=kapat'
```
What it does (checked against the source): it symlinks `~/KAPAT/klipper_extras/kapat` to
`~/klipper/klippy/extras/kapat`, runs `pip install numpy scipy` in `~/klippy-env` (both are
already present: numpy 2.2.2 and scipy 1.17.1, so this is a no-op), copies the web UI to
`~/kapat-web`, and uses `sudo sed` to insert `/kapat` locations into
`/etc/nginx/sites-enabled/mainsail`, then tests and reloads nginx. **It does not restart Klipper.**
It says so at the end; ignore that until Step 6.

Model checks afterwards:
```
ssh ernst@192.168.1.240 'ls -l ~/klipper/klippy/extras/kapat; ls ~/kapat-web | head -3; grep -n "kapat" /etc/nginx/sites-enabled/mainsail; sudo -n true 2>/dev/null; curl -s -o /dev/null -w "%{http_code}\n" http://localhost/kapat/'
```
Expected: the symlink, an `index.html`, two `location` lines, and `200`. If nginx was not wired,
the installer printed the two `location` lines to add by hand. The human adds them inside
`server {`, then runs `sudo nginx -t && sudo systemctl reload nginx`.

## Step 5 — ⚠️ GATE: write the safe calibration position *(model, over SSH)*

**This must happen before Klipper loads KAPAT (Step 6).**
```
ssh ernst@192.168.1.240 'mkdir -p ~/printer_data/kapat && printf "%s\n" "{\"calibX\": 175, \"calibY\": 40, \"calibZ\": 80}" > ~/printer_data/kapat/settings.json && cat ~/printer_data/kapat/settings.json'
```
Expected: `{"calibX": 175, "calibY": 40, "calibZ": 80}`. These are `KARMAN_PA_CALIBRATE`'s
`purge_x/y/z`: front-centre, clear of every keep-out, watched and validated since August.
**If this file is not exactly that, stop. Do not continue to Step 6.**

## Step 6 — Deploy the shim, include `kapat.cfg`, restart the host *(model)*

1. Copy the shim and symlink it:
   ```
   rsync -a --mkpath /home/kyle/projects/auto-pa-tuning/klipper_extras/ ernst@192.168.1.240:auto-pa-tuning/klipper_extras/
   ssh ernst@192.168.1.240 'ln -sfn ~/auto-pa-tuning/klipper_extras/bdp_load_cell.py ~/klipper/klippy/extras/bdp_load_cell.py && ls -l ~/klipper/klippy/extras/bdp_load_cell.py'
   ```
2. Edit `overrides.cfg` on the mount. Directly under the existing `[include bdpressure.cfg]` line,
   add:
   ```
   # KAPAT PA sweeps measured by the BDPressure (concept). Needs bdpressure.cfg above.
   # Runbook: docs/runbooks/pa-kapat-bdpressure-concept.md
   [include kapat.cfg]
   ```
3. Confirm the printer is not printing, then restart the **host** (new `extras/*.py` need it;
   `FIRMWARE_RESTART` is not enough):
   ```
   curl -s 'http://192.168.1.240:7125/printer/objects/query?print_stats=state'
   curl -s -X POST 'http://192.168.1.240:7125/machine/services/restart?service=klipper'
   ```
   Only restart if the state is not `printing` or `paused`.
4. Wait about 20 s, then check:
   ```
   ssh ernst@192.168.1.240 'tail -5 ~/printer_data/logs/klippy.log'
   curl -s 'http://192.168.1.240:7125/printer/objects/query?kapat&webhooks'
   ```
   Expected: webhooks `state: ready`, and kapat `has_load_cell: true`,
   `load_cell_name: bdp_load_cell`.

**Gate.** If Klipper does not reach `ready`, comment out the new `[include kapat.cfg]` line,
restart again the same way, and log the error from `klippy.log` to the issue. **Stop and
escalate. The printer must be left working.**

## Step 7 — Idle self-test *(model, printer cold is fine)*

```
curl -s -X POST 'http://192.168.1.240:7125/printer/gcode/script?script=BDP_LC_SELFTEST%20SECONDS=10'
ssh ernst@192.168.1.240 'grep -a "bdp_load_cell" ~/printer_data/logs/klippy.log | tail -5'
```
**Gate:** rate between 80 and 95 Hz, clock-fit residual rms < 1 ms, and almost no unparsed lines.
A rate under 70 Hz, a residual over 2 ms rms, or a stall error means **stop and escalate**. Under
those conditions KAPAT's timing cannot be trusted.

Then prove the vendor path still works and the port is handed back. This also exercises sharing
the port:
```
curl -s -X POST 'http://192.168.1.240:7125/printer/gcode/script?script=SET_BDPRESSURE%20NAME=bd_pa%20COMMAND=RESET_PROBE'
```
Expected: no error.

## Step 8 — Open the web UI *(human, browser on the workstation)*

Open `http://192.168.1.240/kapat/`. Expected: it connects, shows a load cell
(`bdp_load_cell`), and Settings or the Filament Profile card shows the calibration position
175 / 40 / 80. **If it shows anything else, do not touch the start button. Stop and escalate.**

The page talks to Moonraker's raw bridge at `ws://192.168.1.240:7125/klippysocket`. If it cannot
connect, the browser console says why, usually a Moonraker `[authorization]`
`trusted_clients`/`cors_domains` rejection. The model then checks
`ssh ernst@192.168.1.240 'grep -rn -A10 "^\[authorization\]" ~/printer_data/config/moonraker.conf ~/printer_data/config/moonraker/'`
and proposes adding `http://192.168.1.240` to `cors_domains`. That is a `moonraker.conf` edit, so
ask first. **This is not a blocker for Steps 9–13**, which run from Mainsail. Do not block on it;
finish them and come back.

## Step 9 — Load and heat for the sign test *(human)*

From Mainsail. If ABS is already at the toolhead, skip the `SWAP`.
```
G28
M109 S265
SWAP TOOL=<gate holding ABS>
```
Then park at the purge position and soak:
```
KARMAN_PA_CALIBRATE NOZZLE_TEMP=275 MAX_VOLUMETRIC=25 ACC_WALL=5000
```
This also produces the **vendor baseline for Step 13**. Record the PA it reports (expected about
0.031). It leaves the nozzle at 275 °C, positioned and soaked.

## Step 10 — Sign test *(human runs; model reads)*

The toolhead must already be at 175/40/80, hot, after Step 9.
```
G90
G1 X175 Y40 Z80 F6000
BDP_LC_SELFTEST EXTRUDE=1
```
The model reads the `delta` line (`klippy.log` or the console paste).
- **delta > 0** by clearly more than the idle std → the sign is right. Continue.
- **delta < 0** → set `invert: True` in `kapat.cfg` and `FIRMWARE_RESTART` (a cfg change only).
  Re-run this step, and expect delta > 0.
- **|delta| ≈ idle std** → the sensor is not seeing extrusion pressure. **Stop and escalate.**

## Step 11 — First KAPAT sweep *(human starts; model watches)*

Model: start a live log watch before the human starts:
```
ssh ernst@192.168.1.240 'tail -Fn0 ~/printer_data/logs/klippy.log | grep -a --line-buffered -E "kapat|bdp_load_cell|KARMAN_KAPAT|Error|error"'
```
(run it with Monitor).

Human, from Mainsail's macro panel or console:
```
KARMAN_KAPAT MODE=GRID NOZZLE_TEMP=275 FILAMENT=ABS
```
About 4 minutes (30 s hot soak + prime + about 190 s sweep). The blob forms at Z80; clear it
before the next run.

**Gate:**
- **Carry on** if the report shows a per-K table with `integral_area` **changing sign** inside
  0–0.08, and a K_opt in 0.020–0.050.
- **No sign change, or K_opt pinned at 0.000 or 0.080** → most likely a time offset between the
  shim's clock and the moves (USB plus ADC filter lag). Try `time_offset: -0.012` (one sample) in
  `kapat.cfg`, run `FIRMWARE_RESTART`, and re-run once. Still pinned → **stop and escalate** with the
  capture name from `~/printer_data/kapat/captures/`. Do not patch KAPAT.
- **"kapat: … exceeds max_extrude_cross_section"** → the `[extruder]` override did not apply.
  Check that `kapat.cfg` is included after Klippain's extruder section, and fix that. Do not
  raise the value past what the error asks for.
- **Stall error** → the USB device dropped. Check `ls /dev/serial/by-id/` and escalate. This is
  the 2026-09-03 failure mode.

## Step 12 — Repeatability *(human starts; model records)*

Two more back-to-back GRID runs (the soak drops to 30 s automatically), then one fast run:
```
KARMAN_KAPAT MODE=GRID NOZZLE_TEMP=275 FILAMENT=ABS
KARMAN_KAPAT MODE=GRID NOZZLE_TEMP=275 FILAMENT=ABS
KARMAN_KAPAT MODE=BISECT_SECANT NOZZLE_TEMP=275 FILAMENT=ABS
```
Model: compute the mean and σ of the three GRID K_opts. Note how far the bisect K is from the
GRID mean and how many probes it used. **σ ≤ 0.004 passes.** σ > 0.004 → record it and escalate.
Do not tune KAPAT parameters to make the number behave; that is td-746307's work.

## Step 13 — Cross-check against the vendor method *(model)*

Compare the GRID mean with the Step 9 vendor PA. They measure **different things**: KAPAT's fast
leg is 19.24 mm³/s against a 1.92 slow leg, while the vendor runs a 25 mm³/s pattern with
`ACC_WALL 5000`. The ABS law `PA ∝ Q^(n−1)` with n = 0.653 predicts KAPAT's value to be about
**1.1×** the vendor's at most. Report the ratio. **This is a finding, not a gate.** Log it to the
issue in one line, for example `td log td-8dd427 "KAPAT GRID 0.0xx±0.00x (n=3) vs vendor 0.0xx; ratio x.xx"`.

## Step 14 — Start one sweep from the web UI *(human)*

The toolhead must be at 175/40/80 and hot, which is where Step 12 left it. On
`http://192.168.1.240/kapat/`, pick or create a filament profile "ABS" at 275 °C and press start.
Expected: it does **not** move anywhere visible (it is already at the calibration position), runs,
and the result appears in History together with the Step 11–12 runs.
If Step 8 failed to connect, mark this item open in the verification list and say so in the
handoff.

## Step 15 — Shut down *(human)*

```
TURN_OFF_HEATERS
M84
```
Remove the blob. **Mandatory**: idle_timeout is not reliable on Karman.

---

## Verification

- [ ] `uv run --with pytest --with numpy --with pyserial pytest tests` passes in
      `auto-pa-tuning`. *(validated in a proxy)*
- [ ] Klipper reaches `ready` with `kapat.cfg` included, and `kapat` reports
      `has_load_cell: true` and `load_cell_name: bdp_load_cell`. *(verified in reality)*
- [ ] `settings.json` holds 175 / 40 / 80, and the UI shows the same. *(verified in reality)*
- [ ] `BDP_LC_SELFTEST` gives 80–95 Hz and clock-fit residual rms < 1 ms; `EXTRUDE=1` gives a
      clearly positive delta. *(verified in reality)*
- [ ] Three `KARMAN_KAPAT MODE=GRID` runs on ABS at 275 °C: each K_opt is in 0.020–0.050, there
      is an `integral_area` sign change in range, and σ ≤ 0.004. *(verified in reality: the
      maintainer reports the console output)*
- [ ] One `BISECT_SECANT` run completes without falling back to the grid. *(verified in reality)*
- [ ] One sweep started from the KAPAT web page completes and appears in its History.
      *(verified in reality)*
- [ ] **Nothing regressed:** `KARMAN_PA_CALIBRATE` still returns a PA with healthy `fresh` reads
      (Step 9), `[extruder] pressure_advance` still reads 0.032
      (`curl -s 'http://192.168.1.240:7125/printer/objects/query?extruder=pressure_advance'` after
      the session's last restart, since KAPAT changes PA live during sweeps; a restart restores it), Mainsail at
      `http://192.168.1.240/` still loads, `uv run tools/render_macro.py --selftest` passes.
- [ ] Heaters off at the end of the session.

## When it is done

- **`docs/decisions.md`**: one entry, "KAPAT on the BDPressure via a load-cell shim (concept)".
  Record why the shim and not a rewrite, why the wobble and not de-energise for now, and why
  `max_extrude_cross_section: 200`. Include the measured rate and residual, the time_offset that
  worked, the sign, and the three GRID K values against the vendor value.
- **`CLAUDE.md`**: under *Printer*, add one line: KAPAT installed (pinned `a33957d`, web UI at
  `/kapat/`), sensor via `bdp_load_cell` from `~/auto-pa-tuning`, and the `settings.json`
  calibration-position rule. Add the "KAPAT default calibration position" hazard to the
  **Physical keep-out zones** list in the register (always-on).
- **Update `overrides.cfg`'s "ONE OWNER OF THE PORT" comment** above `[include bdpressure.cfg]`: it
  is no longer strictly true, because `bdp_load_cell` opens the port during KAPAT sweeps. Say that
  the two must not run at the same time.
- **td**: `td log` the K values; mark td-8dd427 done only when every item above is checked.
  td-746307 then uses `KARMAN_KAPAT` in place of its Step 4 sweeps.
- **Commits** (Karman, over SSH on the Pi, after asking):
  - `feat: kapat pa sweeps on the bdpressure via a load-cell shim`: `kapat.cfg`, `overrides.cfg`
  - `docs: record the kapat concept`: `docs/decisions.md`, `CLAUDE.md`,
    `docs/runbooks/pa-kapat-bdpressure-concept.md`
  - In `auto-pa-tuning` (local, no remote): the Step 1 commit, plus a short note in
    `docs/research/README.md` *Status* saying the concept took path A3.
