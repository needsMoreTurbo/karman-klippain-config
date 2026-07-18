# Bed Fan Control System — Design

**Machine:** Karman (Voron 2.4, Klippain) · **Fans:** under-bed 5015 blowers (`fan_generic Bed_Fans`, pin `PF9`) · **Bed:** Keenovo, `max_power: 0.8` · **Chamber sensor:** toolhead-integrated (`temperature_sensor Chamber`).

The bed fans circulate hot air from beneath the heated bed up into the enclosure. On high-temperature materials (ABS/ASA) this raises chamber temperature and evens out heat, but the same airflow that warms the chamber also pulls heat off the bed — so *when* and *how hard* the fans run has to be coordinated with the bed heater. This document defines a replacement control system and the reasoning behind it. It is the design of record; the config rewrite (`bed_fans.cfg`) follows the state machine specified here.

---

## 1. Problems with the current system

The current `bed_fans.cfg` is a port of the *3DPrintDemon Bed Fans Monitor v2.0.1*. It uses a `readback_value` 1–9 state loop (`_BED_FAN_MONITOR`), a proportional "floating" mode (`_FLOATING_FAN`), a slider-reinterpretation helper (`_BED_FAN_HELPER`), and a **second, separate** standby loop (`_BED_PREHEAT_WATCH`). Three concrete failures result:

### 1.1 Preheat stalls the heater and crashes Klipper
`_BED_PREHEAT_WATCH` (`bed_fans.cfg:385`) runs during standby and, once `heater_bed.target > 85`, calls `_BED_FAN_SET`. Inside `_BED_FAN_SET`, once the bed climbs to within 40 °C of target (`bed_fans.cfg:241` → `:249`), the fans are switched to **HIGH** (`bed_fans.cfg:251`) *while the bed is still heating*. On a Keenovo limited to `max_power: 0.8`, high airflow removes heat faster than the heater can add it, the rise rate collapses, and Klipper's `verify_heater` trips:

> `Heater heater_bed not heating at expected rate`

This is the headline bug: the fans fight the bed heater during preheat/soak.

### 1.2 No usable manual override
The monitor loop rewrites the fan speed every ~10 s. The only manual paths are:
- `_BED_FAN_HELPER` (`bed_fans.cfg:157`) — reinterprets a Mainsail slider move as "`<50 %` → new *low* setting, `≥50 %` → new *high* setting," and **disallows `0`**. Confusing and lossy.
- `DISABLE_BED_FANS` (`output_pin` PG9) — an all-or-nothing pause toggle.

Any speed you set directly is clobbered on the next tick. There is no "hold this speed" that survives the loop.

### 1.3 No true gradual ramp
The "floating" mode (`_FLOATING_FAN`, `bed_fans.cfg:187`) nudges speed ±1 % but keys off a *chamber* midpoint, not off "the bed reached target, now bring the fans up." There is no smooth low→high transition tied to the bed reaching temperature, so the system either sits low or jumps to high — and a hard jump to high once at target can pull bed temp down sharply, re-triggering the same `verify_heater` fault.

---

## 2. Research: how others solve this

| Approach | Mechanism | Ramp? | Notes |
|---|---|---|---|
| **[Ellis Bed Fans](https://github.com/VoronDesign/VoronUsers/blob/main/printer_mods/Ellis/Bed_Fans/Klipper_Macros/bedfans.cfg)** (canonical Voron) | Keys purely off `heater_bed.target` and proximity: `slow` (or `0`) while heating, `fast` only within ~1 °C of target. Overrides `M140`/`M190`/`SET_HEATER_TEMPERATURE`. | No — discrete | Directly prevents the heater stall by keeping fans low during heat-up. Docs explicitly note the `not heating at expected rate` fault comes from fan speeds set too high, and that `slow` may be `0`. |
| **[DarkDoldier "Better Bed Fans"](https://github.com/DarkDoldier/Klipper-better-BED-FANS-Macro)** | Adds chamber awareness: `slow`/`fast` during/after target, then `slow_c`/`fast_c` to hold a chamber target. | No — discrete | Three phases: heating → target reached → chamber hold. |
| **[N3MI-DG bed_fans](https://github.com/N3MI-DG/bed_fans)** | Fan speed from the bed↔chamber temperature delta. | Continuous but delta-driven | Needs a trustworthy chamber reading. |

**Takeaways adopted here:**
1. **Gate on the bed, not the chamber, during heat-up** (Ellis). Fans stay gentle until the bed is actually at target — this is the clean fix for the heater-stall crash.
2. **Keep the chamber as a safety *cap*, not a setpoint.** Our `Chamber` sensor is toolhead-mounted (reads warm and noisy), so closed-loop chamber targeting (DarkDoldier/N3MI style) would hunt. We use it only to trim fans down if the chamber gets too hot.
3. **Add what none of the references have: a gradual ramp with a drop-guard.** After the bed settles at target, ramp low→high in small steps, and if bed temp dips during the ramp/hold, step back down and freeze — so the fans can never outrun the heater.

---

## 3. Design

### 3.1 Principles
- **One loop, one source of truth.** A single always-on `delayed_gcode` (`_BED_FAN_TICK`) governs both standby preheat and printing. No second divergent standby loop.
- **Bed-gated.** Fan behavior is driven by `heater_bed.target`/`temperature`; the chamber is only a cap.
- **Fail toward the bed.** Every ambiguous condition resolves to *less* airflow, protecting the heater.
- **Manual override is explicit and persistent.** A latch holds your speed until you clear it, a new print starts, or (for an override set during a print) the print ends — the loop never silently overrides you. It works in every state, including post-print cooldown.
- **Only engages when it matters.** Below `activation_temp` (i.e. PLA/PET), the system stays fully off.

### 3.2 State machine

`_BED_FAN_TICK` reads `print_stats.state`, `heater_bed.target`, `heater_bed.temperature`, and `Chamber`, then selects one state per tick:

| State | Entry condition | Fan action | Next tick |
|---|---|---|---|
| **OFF** | `enable` false, **or** `heater_bed.target < activation_temp` | `0` | slow (~10 s) |
| **MANUAL** | manual latch set (macro or auto-detected slider move) | leave fan **untouched** | normal |
| **HEATING** | demand active **and** `bed_temp < target − target_tolerance` | `heating_speed`; reset settle + ramp progress | `tick_interval` |
| **RAMP** | at target (within `target_tolerance`), held ≥ `settle_time` | `+ramp_step` toward `high_speed` | `tick_interval` |
| **HOLD** | ramp reached `high_speed` | hold `high_speed` (subject to caps) | `tick_interval` |
| **COOL** | post-print window open (see below) and `heater_bed.target == 0`, no manual latch | `cool_speed` until `chamber < cool_temp`, then OFF; clears a mid-print latch on the print-end transition | `tick_interval` / slow |

"Demand active" = `heater_bed.target ≥ activation_temp`. Because the same loop runs in standby, **manual preheat gets the identical HEATING→RAMP→HOLD treatment** — gentle while climbing, ramp after target.

**Post-print window (one-shot, `post_print` flag).** COOL is governed by an explicit window, *entered* on the print-end **transition** (`print_stats.state` newly ∈ {complete, cancelled, error}, detected via `prev_state`) and tracked in the `post_print` variable — never level-triggered on `print_stats.state` itself. That distinction matters because Klipper leaves `print_stats.state` at `"complete"` indefinitely: it only returns to `"standby"` via `SDCARD_RESET_FILE`, or when the next print loads (`SDCARD_PRINT_FILE`/`M23`) — there is no timeout, and Klippain issues `SDCARD_RESET_FILE` only on *cancel*, not on *complete*. An earlier revision level-triggered on the stale state, so a manual bed preheat after a completed print stayed trapped in the post-print branch and the fans never engaged (found 2026-07-18).

The window **closes permanently** when any of these occurs:
1. **Cooldown completes** — `chamber < cool_temp` (the normal COOL→OFF exit).
2. **Any bed heat demand appears** — `heater_bed.target > 0`. Deliberately *any* demand, not `≥ activation_temp`: an ABS-temp reheat during cooldown must get the full HEATING→RAMP→HOLD cycle, and a PLA-temp reheat must drop the fans to OFF rather than leaving COOL stirring warm air at a bed being heated.
3. **A new print starts** (`just_started`).

A manual latch held during cooldown *suspends* the window without closing it — clearing the latch with `BED_FANS_AUTO` resumes COOL if the chamber is still warm. One accepted trade-off: the window is one-shot, so if a reheat is set and then cancelled while the chamber is still ≥ `cool_temp`, COOL does **not** resume — fans stay off and the chamber cools passively ("fail toward less airflow"). After the window closes, `print_stats.state == "complete"` is inert; the automatic rules alone decide fan behavior.

```
                    ┌─────────────────────────── manual latch set ──────────────────────────┐
                    │                                                                        ▼
  target<act ──▶ [OFF] ──target≥act & bed<target−tol──▶ [HEATING] ──at target, settle_time──▶ [RAMP] ──reached high──▶ [HOLD]
                    ▲                                        ▲   │                              │  │                      │
                    │                                        │   └──────bed drops below─────────┘  │                      │
                    │                                        │        (target−drop_guard):         │                      │
                    │                                        └───────── step down + freeze ────────┴──────────────────────┘
                    │                                                                                                      
                    └── window closes (chamber cool, ◀── [COOL] ◀── print-end transition (opens one-shot window; ─────────
                        bed demand, or new print)                   any bed target > 0 exits to the auto states)
```

### 3.3 Crash protection (the core fix)
Applied every tick:
1. **Never high while heating.** HEATING uses `heating_speed` only. Since the same loop governs standby, this eliminates the preheat crash (§1.1) *and* the in-print soak version of it.
2. **Ramp only after settle.** Begin ramping only once the bed has stayed within `target_tolerance` of target continuously for `settle_time`. This avoids ramping during the initial overshoot/settle wobble.
3. **Drop-guard.** Once the bed has settled, a `reached` latch keeps the controller in RAMP/HOLD across a **reheat band** (`target − reheat_band` … `target`) rather than flipping back to `HEATING` on the first small dip. Within that band, if `bed_temp < target − ramp_drop_guard`, step the fan **down** by `ramp_step` (floored at `heating_speed`) and **freeze** the ramp until the bed recovers. This lets the fan settle at an equilibrium the heater can sustain — guaranteeing the fans never outrun the heater and re-trip `verify_heater` (§1.3). Only a *large* drop (`bed_temp < target − reheat_band`) is treated as a genuine re-heat: the latch clears and the machine returns to `HEATING` (fan → `heating_speed`, ramp restarts). Note `reheat_band` must exceed `ramp_drop_guard`, otherwise the drop-guard band is empty and unreachable.
4. **Chamber cap.** If `chamber ≥ chamber_max`, step the fan down. Allow stepping back up only once `chamber < chamber_resume` (hysteresis) **and** the bed is healthy. The chamber never forces the fan *up* — only down.

### 3.4 Manual override (§1.2 fix)
A single latch (`manual_latch` + `manual_speed`) makes manual control persistent and predictable:

- **`BED_FANS_MANUAL SPEED=<0-100>`** — latch to a fixed speed for the rest of the print.
- **`BED_FANS_AUTO`** — clear the latch, resume automatic control.
- **`BED_FANS_OFF`** — latch at `0` (hard off).
- **Mainsail slider also works.** The loop records `last_commanded_speed`. If the actual `fan_generic Bed_Fans.speed` differs from it by more than ε (~0.02) between ticks, *you* moved the slider → the loop auto-latches to that speed and stops touching it. This is the robust version of the old `_BED_FAN_HELPER` intent, without the `<50 %`/`≥50 %`/`0-disallowed` quirks.
- **Latch lifetime.** A latch set *during* a print is released once, on the **print-end transition** (`just_ended`), so cooldown and the next print run in auto. A latch set *after* a print (during cooldown) **wins over the COOL state and holds** — so `BED_FANS_MANUAL`/`BED_FANS_OFF` work post-print, which they previously didn't. Any lingering latch is also dropped at the **next print start** (`just_started`), so a stale manual speed can never leak into a new print's heat-up and re-cause the heater stall. This requires the loop to remember the previous `print_stats.state` in `prev_state` and to check the manual/slider branches **before** the ongoing-COOL branch.

Klipper reports `fan_generic.speed` as the last commanded value (not a measurement), so slider detection is exact aside from the ε guard for kick-start/`off_below` rounding.

- **`BED_FANS_STATUS`** — prints current state, commanded speed, latch status, and the active thresholds. Replaces the old `_BED_FAN_READ` / `BED_FANS_*_INFO` / `_MONITOR_MESSAGE_READ` cluster.

### 3.5 Parameters (`_BED_FAN_VARS`)

| Var | Default | Meaning |
|---|---|---|
| `enable` | `True` | master enable |
| `activation_temp` | `90` | engage only when `heater_bed.target ≥` this (skips PLA/PET) |
| `heating_speed` | `0.10` | gentle speed while the bed climbs (preheat + in-print). Kept low so it doesn't slow the bed's rise and risk a `verify_heater` fault. Set `0` to keep fans fully off during heat-up. |
| `high_speed` | `0.55` | ramp ceiling |
| `target_tolerance` | `2.0` | °C band counted as "at target" |
| `settle_time` | `30` | seconds at target before the ramp starts |
| `ramp_step` | `0.03` | speed increment/decrement per tick |
| `ramp_drop_guard` | `3.0` | °C below target that forces a step-down + ramp freeze |
| `reheat_band` | `8.0` | °C below target before the ramp is abandoned and the bed fully re-heats (must be `> ramp_drop_guard`) |
| `chamber_max` | `55` | chamber cap — fans step down above this |
| `chamber_resume` | `50` | fans may step back up below this (hysteresis) |
| `cool` | `True` | run fans post-print to assist bed cool-down |
| `cool_speed` | `0.40` | fan speed during the post-print cool assist (independent of `heating_speed` — the heater-stall constraint doesn't apply with the heater off) |
| `cool_temp` | `40` | stop the post-print cool assist below this chamber temp |
| `tick_interval` | `4` | seconds between ticks while active |

**Ramp time** = `(high_speed − heating_speed) / ramp_step × tick_interval`. With defaults: `(0.55 − 0.10)/0.03 × 4 = 60 s`. Tune the ramp by changing `ramp_step` (size) or `tick_interval` (cadence).

### 3.6 Tuning guide

| Material | Bed | Suggested `heating_speed` / `high_speed` | Notes |
|---|---|---|---|
| PLA / PET | 60 / 70 | — | Below `activation_temp` → system stays OFF. Print with the enclosure open. |
| ABS / ASA | 105–110 | `0.10` / `0.55` | Start here. If you still see a slow rise or a `verify_heater` warning during heat-up, lower `heating_speed` to `0`. |
| Chamber too hot | — | lower `high_speed` and/or `chamber_max` | The cap trims automatically, but a lower ceiling reduces hunting. |
| Chamber too cold | — | raise `high_speed`, raise `chamber_max` | More airflow once at target. |
| Heater faults during ramp | — | lower `ramp_step`, raise `settle_time`, raise `ramp_drop_guard` sensitivity (lower the value) | Gentler, later, more protective ramp. |

Always change one variable at a time and re-test a preheat.

---

## 4. Integration

- **Include** stays: `[include bed_fans.cfg]` in `overrides.cfg` (`:173`).
- **START_PRINT hooks removed.** The old `bed_fans_init` / `bed_fans_monitor` actions in `variable_startprint_actions` (`overrides.cfg:179`) are dropped — the always-on tick loop makes them redundant and removes coupling to the Klippain START_PRINT dispatcher. The `_START_PRINT_ACTION_BED_FANS_*` macros go away with the rewrite.
- **`DISABLE_BED_FANS` (`output_pin` PG9)** is replaced by `BED_FANS_OFF`/`BED_FANS_AUTO`. Confirm PG9 isn't wired to real hardware before removing the section (read-only check on the Pi if unsure).
- **Preserved dependencies:** the sensor object must remain named `temperature_sensor Chamber`; `_USER_VARIABLES.verbose` still gates optional console chatter.

---

## 5. Rollout & testing

This repo is a local clone of the Pi's `~/printer_data/config`. Workflow: edit here → commit/push → pull on the printer → `RESTART`. `ernst@192.168.1.240` is for read-only inspection only.

**Offline pre-check (run before every push):** `tools/render_macro.py` renders the `_BED_FAN_TICK` template through Klipper's exact Jinja2 environment and asserts the state/speed/duration across the whole state machine:
```bash
uv run tools/render_macro.py --selftest
```
This catches template syntax errors and logic regressions (it already caught an unreachable drop-guard). It is **not** a substitute for on-machine testing — it can't model real thermodynamics — so still validate on the printer:

1. **Config loads** — `RESTART`; no errors; `BED_FANS_STATUS` responds.
2. **Preheat (fixes §1.1)** — from cold, set bed 105 °C in standby. Fans hold `heating_speed` for the entire climb, never jumping high; bed rises smoothly with **no** `not heating at expected rate` fault.
3. **Ramp (fixes §1.3)** — at 105 °C, fans wait `settle_time`, then ramp in `ramp_step` increments to `high_speed`; bed stays within `ramp_drop_guard`. Force a dip (brief manual blast) and confirm the loop steps down + freezes the ramp.
4. **Manual override (fixes §1.2)** — mid-print, drag the Mainsail slider → auto-latch, loop stops clobbering; `BED_FANS_MANUAL SPEED=40` holds; `BED_FANS_AUTO` resumes. Also verify `BED_FANS_MANUAL` **during cooldown** holds (doesn't get reclaimed by COOL), a mid-print latch clears when the print ends, and a latch left on during cooldown is dropped when the next print starts.
5. **Chamber cap** — fans step down when `Chamber ≥ chamber_max`, recover below `chamber_resume`.
6. **Post-print** — end/cancel → COOL runs `cool_speed` to `cool_temp`, then OFF; latch cleared.
7. **PLA regression** — bed 60 °C (< `activation_temp`) → fans stay OFF throughout.
8. **Stale-complete preheat (post-print window)** — run a print to completion, then **without restarting Klipper** (a `FIRMWARE_RESTART` resets `print_stats` to `standby` and hides the bug this tests for), set bed 105 °C from the GUI. Fans must run the normal HEATING→SETTLE→RAMP→HOLD cycle (`BED_FANS_STATUS` shows `window=False`). Then: during a cooldown (COOL active), set bed 60 °C → fans go OFF immediately; set bed 105 °C instead → HEATING engages.
