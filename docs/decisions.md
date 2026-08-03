# Decision log

Why things are the way they are. Config comments say *what*; this says *why*, and what was
tried and rejected — so a later session (human or agent) doesn't "fix" something that is
deliberate, or re-litigate a settled tradeoff.

**Add an entry when:** a value is counter-intuitive, an obvious-looking alternative was
rejected, a default was overridden, or a bug cost real debugging time. Newest first.
Keep entries short. Link the file, don't duplicate it.

---

## 2026-08-02 — Nozzle-expansion offset silently applied **zero** on every print but the first
**Decision:** `_START_PRINT_ACTION_NOZZLE_EXPANSION` now calls
`_BEACON_SET_NOZZLE_TEMP_OFFSET RESET=True` *before* the real call, and
`_BEACON_REMOVE_NOZZLE_TEMP_OFFSET` zeroes the saved variable.
**Why:** `_BEACON_SET_NOZZLE_TEMP_OFFSET` applies `(-applied_offset) + expansion_offset`, where
the first term is meant to remove a **still-in-effect** previous offset. It never is:
Klippain's START_PRINT prologue runs an absolute `SET_GCODE_OFFSET Z=0`
(`macros/base/start_print.cfg:126`) long before this action. Meanwhile
`nozzle_expansion_applied_offset` is only cleared by `_BEACON_INIT` (firmware restart) or an
explicit RESET — the END_PRINT remover subtracted from the gcode offset without clearing it. So
the two terms cancelled **exactly** and `SET_GCODE_OFFSET Z_ADJUST=0.0` was issued. Net effect:
**the first print after a FIRMWARE_RESTART got the offset; every print after it got nothing**,
which is why this presented as intermittent and was mistaken for a calibration problem.
Nothing was miscalibrated — `nozzle_expansion_coefficient = 0.055` is correct and
`1.0 × (275−150) × 0.055/100 = 0.06875` is the right answer; it was just never applied.
**Reproduced offline** with `tools/render_macro.py`: stale saved value → `Z_ADJUST=0.0`;
after RESET → `Z_ADJUST=0.06875`.
**Why RESET rather than only fixing the remover:** it also covers cancelled prints and power
loss, where END_PRINT never runs at all. ~0.069 mm is ~1/3 of a 0.2 mm layer.

## 2026-08-02 — `M141` / `M191` are undefined; the errors are cosmetic
**Decision:** noted, not yet fixed. Klipper answers `Unknown command:"M191"` non-fatally and the
print continues.
**Why it appears:** OrcaSlicer emits `M191 S45` / `M141 S0` when chamber temperature control is
active in the profile. There is no chamber heater and no `M141`/`M191` definition anywhere in
Klipper, Klippain, or this repo. KlipperScreen raises the response as a popup; Mainsail files it
in the console, hence "it only showed on one screen". Chamber waiting is owned by START_PRINT's
`chamber_soak` via the `CHAMBER=` parameter, which is passed independently of these commands.
**If it becomes annoying:** define no-op `M141`/`M191` macros in overrides.cfg. Do *not* fix it
by turning the slicer toggle off — that suppresses the commands but does not zero
`chamber_temperature`, so `CHAMBER=` still arrives (see 2026-07-14).

## 2026-08-02 — `force_homing_before_brush: False` (was True)
**Decision:** no `G28 Z` before either `clean` in START_PRINT.
**Why:** two independent reasons. (1) *Stale* — it existed to "not miss the brush", but the
brush is gantry-mounted (2026-07-19), so its Z tracks the toolhead and only an X slide engages
it. (2) *Harmful* — `home_method_when_homed: proximity`, so the `G28 Z` in the **second** clean
re-homed Z by proximity immediately after `contact_z_home` had set it by nozzle contact,
discarding the authoritative Z origin right before the prime line. Either the contact home is
the reference or it isn't; it can't be both.
**Also worth knowing:** this flag never protected against a racked gantry — re-homing Z
re-zeroes at bed centre, it does not level. Its `home_z_hop: 5` was in fact the *cause* of the
bucket traverse crossing the plate at z5. That job now belongs to `bucket_travel_safe_z`.
Klippain's own template default is `False`; our `True` dated to the initial config commit and
predated the gantry-brush rework.

## 2026-08-02 — `bucket_travel_safe_z: 20` and an override of `_CONDITIONAL_MOVE_TO_PURGE_BUCKET`
**Decision:** lift to 20 mm before the diagonal to the purge bucket. ⚠️ Looks arbitrary; isn't.
**Why:** Klippain drives a bare `G1 X Y` from wherever the toolhead is to (9, 359) and does
**not** route through `_KARMAN_PARK_MOVE`, so nothing enforced a Z floor on a traverse that
crosses the whole bed — and the first `clean` runs *before* `tilt_calib`, i.e. on a gantry that
may still be racked. Sizing (from `gantry_corners` geometry, checked by the `start_print`
scenario in `tools/visualize_toolchange.py`): one Z-motor corner low by 30 mm puts the nozzle up
to **14.6 mm** below commanded Z on this traverse and **17.0 mm** below anywhere over the plate.
20 covers it with margin. For scale, QGL's `max_adjust` is 10 mm, so a rack big enough to defeat
this aborts `tilt_calib` anyway.
**Rejected:** relying on `bed_soak`'s Z50 park — it is skipped entirely when the bed is already
within 8 °C of target, which is exactly the repeat-print case.
**Refined same day** after the maintainer spotted the toolhead bobbing in the back-left corner:
the lift is now gated on `travels` (does the XY move actually go anywhere) as well as on Z. The
second `clean` follows the initial-load purge with the toolhead **already at the bucket**, so it
was lifting 5→20→5 in place, protecting a diagonal that never happened.

## 2026-08-02 — Klippain's `purge` action removed from `startprint_actions`
**Decision:** drop `purge`; resize `unretract_length` 23 → 5 in the same change.
**Why:** it was waste. Blobifier owns purging when a load happens, and `primeline` re-primes the
nozzle when one doesn't. On a cold 2-colour start it made three purges back to back (Blobifier
~94 mm³ → `purge` 30 mm → prime line 23 + 30 mm).
**The coupling that makes this non-obvious:** `PRIMELINE` unretracts **unconditionally**
(`prime_line.cfg`, no guard), and that unretract existed solely to refill the −20 mm retract at
the *end* of `PURGE`. Removing `purge` alone would have left +23 mm extruded standing still at
the prime-line start. `retract_length` is consequently now unused by START_PRINT *and* END_PRINT
— it survives only as a parameter of the manually callable `PURGE` command, so don't delete it.
**Watch:** `unretract_length` is the tuning knob — blobby prime-line start → lower, starved → raise.

## 2026-08-02 — Chamber soak stays; the tolerance was the bug
**Decision:** keep `chamber_soak` in the action list; `print_default_chamber_temp_tolerance`
0.0 → 2.0. ⚠️ An earlier proposal to *remove* the action was wrong and was withdrawn.
**Why:** `chamber_soak` heats nothing (there is no chamber heater) — it is a wait-with-timeout
that polls the toolhead sensor and prints anyway after ~14 min. Removing it would have deleted
the only mechanism that can wait on chamber temperature at all; `bed_fans.cfg` cannot do this —
it has no chamber *target*, only fan thresholds, and emits nothing but `SET_FAN_SPEED` /
`SET_GCODE_VARIABLE` / `RESPOND`, so it can never delay or block a print. The real defect was
`tolerance: 0.0`, demanding an exact hit on a warm, noisy, toolhead-mounted sensor rounded to
0.1 °C — which guaranteed the full timeout for any nonzero setpoint.
**Constraint that isn't discoverable from either file alone:** keep slicer `CHAMBER` setpoints
**≤ ~55 °C**. `bed_fans.cfg` throttles the under-bed fans above `chamber_max` (60 °C), and those
fans are what warms the chamber — a higher setpoint makes the two systems fight and burns the
timeout. This may also mean the 2026-07-14 "MMU profiles must send CHAMBER=0" rule can be
relaxed; it was a workaround for the zero-tolerance behaviour.

## 2026-08-02 — `mmu_unload_on_end_print: False`, and what it does *not* buy
**Decision:** leave filament loaded at print end.
**Why:** avoids a pointless unload/reload cycle on repeat single-tool prints, where the next
START_PRINT then reports "Tool T0 is already loaded" and skips both the load and the Blobifier
purge.
**⚠️ The catch:** on **multi-tool** prints this saves nothing. `_KLIPPAIN_MMU_INIT`'s gate-check
branch is guarded on `printer.mmu.tool|string != TOOLS_USED` — with `TOOLS_USED="0,1"` that is
always true, so it runs `MMU_UNLOAD` at print *start* regardless of what END_PRINT did. The flag
only moves the unload from END_PRINT to START_PRINT, where it costs ~1 min of startup, and the
filament now sits in the UHF melt zone through the whole cooldown in between.
**Side effect:** END_PRINT's `retract_filament` action is now a **complete** no-op — the MMU
branch is gated off by this flag and the plain-retract `elif` is unreachable while
`klippain_mmu_enabled` is True.

## 2026-07-25 — Standalone swaps end at the rest via a `SWAP` wrapper, not an HH hook
**Decision:** `SWAP TOOL=n` (overrides.cfg) parks on the nozzle rest *before* calling `Tn`.
**Why:** Happy Hare saves the toolhead position at command start (`mmu.py:6892`, after
`_auto_home`) and restores it as the final step (`mmu.py:3281`). The save precedes *every*
extension hook, so `user_post_load_extension` and friends **cannot** change where a swap ends.
Parking first exploits the restore instead of fighting it — and the ~2 min heat-up then happens
with the nozzle in the RTV cup, which is what fixed the ooze that left the first blob dry.
**Rejected:** parking from the post-load hook (silently undone by the restore).

## 2026-07-25 — In-print guards use `print_stats.state`, never `mmu.print_state` alone
**Decision:** `_KARMAN_STANDALONE_FINISH` leads its guard with `printer.print_stats.state`.
**Why:** a guard on HH state alone shut the hotend off **during START_PRINT on every print**.
Klippain's `_KLIPPAIN_MMU_LOAD_INITIAL_TOOL` runs `MMU_CHANGE_TOOL STANDALONE=1` while HH's
`print_state` is still `initialized` — not in any "printing" list — whereas Klipper's
`print_stats.state` reads `printing` for the whole gcode file. Caught before it shipped only
because the slicer start-gcode was reviewed.

## 2026-07-25 — `_KARMAN_PARK_MOVE` must handle the `-999` sentinel itself
**Decision:** the macro no-ops when X and Y are both `-999`, and handles X-only / Y-only.
**Why:** HH's `_MMU_PARK` calls a `user_park_move_macro` **unconditionally**; its own `-999`
filtering only guards the *default* `G1` path. Emitting `-999` as a coordinate threw
"Move out of range" and aborted the park on every toolchange. It only surfaced after the
back-left rework because `park_toolchange` is `-999,-999` while pause/complete carry real
coordinates, so pause parking had masked it.

## 2026-07-25 — `park_toolchange` stays `-999,-999`
**Decision:** do **not** give the toolchange park a real XY. ⚠️ Looks like an oversight; isn't.
**Why:** BLOBIFIER positions itself at the tray. A real park here would detour the toolhead to
the park point and back on *every* swap. The earlier "Option B / purge bin at 0,358" plan that
would have used it is superseded by Blobifier — see `docs/mmu_slicer_setup.md`.

## 2026-07-19 — `min_toolchange_z: 15` (was 1.0)
**Decision:** floor all toolchange travel at z15.
**Why:** the depressor cut line (back-left, y341) sits above the blobifier shaker arm; anything
lower collides. This is the enforcement mechanism for the back-left keep-out, so the extra lift
on every swap is intentional, not a tuning artifact.

## 2026-07-19 — Gantry-mounted rest/brush: engagement is XY-only
**Decision:** `brush_top: None`; Z lifts in park macros are bed clearance only.
**Why:** the rest and brush ride the gantry, so their Z tracks the toolhead. Only an X slide
seats/unseats the nozzle. Consequences: wiping needs no Z move; `M84` at idle can't jam the
nozzle into the cup (gantry sag moves both together); HH's z15 lift won't lift the nozzle out
mid-swap. Corollary: everything in the y_max row must be entered via a **clear lane**
(15<x<40 or x>95) and then slid in X — head-on approaches crash.

## 2026-07-17 — `toolhead_residual_filament: 25` — and why the low values were wrong
**Decision:** 25 mm (measured; briefly 35, originally mis-set to 5).
**Why:** the Rapido V2 **UHF + melt-zone extender** holds a genuinely large melt pool. The
value is not a tuning knob — the cut macro parks the tip at `retract_length` *only if residual
is true*. At 5 mm the tip sat ~30 mm above the blade (cut air → "formed" tips) **and** loads
over-advanced ~30 mm, extruding out the nozzle as the per-swap tower blob. One wrong number,
two unrelated-looking symptoms.
**Process note:** the original ~35 mm measurement was talked down to 5 on the reasoning that it
was implausible — using standard-hotend intuition that does not apply to a UHF. Trust the
measurement over the prior when the hardware is unusual.

## 2026-07-14 — BTT SFS v2 removed; FlowGuard runs encoderless
**Decision:** run without an encoder; config commented out, not deleted (PC0/PC1 free).
**Why:** the SFS sat *downstream* of the sync-feedback sensor, so its spring-loaded wheel drag
corrupted the tension signal it was meant to complement, and added noise to toolhead
measurements. FlowGuard's **tension-based** path still works off the sync-feedback sensor —
only `flowguard_encoder_mode` is off. If reinstalled, mount it **upstream** of the feedback
sensor.

## 2026-07-14 — Never use `MMU_TEST_FORM_TIP` on this machine
**Decision:** test cuts with `T0`/`T1`/`MMU_EJECT` from a loaded state instead.
**Why:** it final-ejects the tip into the 2 m bowden (uninspectable) and hard-stamps state
`UNLOADED` (`mmu.py:4195`). A following `MMU_EJECT` then takes the short gate-release branch
and errors. Its "-68mm filament remaining" output is test-mode cumulative-travel arithmetic —
it is **not** evidence of motor slip. Fix any desync with `MMU_RECOVER`, never `MMU_TEST_MOVE`.

## 2026-07-14 — Klippain's `PARK`/`RESUME` are overridden, not left alone
**Decision:** override both in overrides.cfg; `park_position_xy` → the nozzle rest.
**Why:** Klippain and HH both park on pause. HH parked on the rest, then Klippain's `PARK`
yanked the toolhead to its own `343,352` — a double-park. Both now converge on the rest and
route through `_KARMAN_PARK_MOVE` for the side approach.

## 2026-07-14 — Chamber temperature must be 0 in MMU filament profiles
**Decision:** slicer-side, not a Klipper change.
**Why:** OrcaSlicer's "activate temperature control" toggle suppresses `M141`/`M191` but does
**not** zero `[chamber_temperature]`, which our start gcode passes through. Any nonzero value
makes Klippain's chamber soak block START_PRINT for up to 15 min — with 0.0 tolerance and a
warm/noisy toolhead-mounted sensor, it burns the full timeout every time. Chamber behavior is
owned by `bed_fans.cfg`, not a START_PRINT setpoint.

## 2026-07-13 — Gear `run_current` 0.8 A, set explicitly on **both** drivers
**Decision:** don't rely on HH inheriting the base driver's current to `stepper_mmu_gear_1`.
**Why:** while chasing a gate-1 stall, `DUMP_TMC` showed both gears already identical at 0.7 A —
proving the stall was mechanical, not electrical. Root cause turned out to be the **gate-0
mirrored nightwatch latch** not holding (fixed by a 99%-scale reprint); gate 1 may need ~99.5%.
The current bump stayed as margin for the long preliminary bowden. Extruder `run_current`
(0.45 A) was suspected repeatedly and **exonerated** — no skipping in real prints.

## 2026-07-11 — Git runs over SSH on the Pi, never on the mount
**Decision:** enforced mechanically by `tools/hooks/guard-git.sh` (PreToolUse), not just docs.
**Why:** the SSHFS mount uses `follow_symlinks` + `transform_symlinks`, so framework symlinks
appear to git as type-changes/deletions. Git on the mount reports bogus changes and would stage
a mangled tree. The hook is mode-aware — it no-ops in a workstation clone.

## 2026-07-11 — MMU gear UART is `gpio11`, not the ERB definition's `gpio20`
**Decision:** override the alias in mcu.cfg.
**Why:** the Fysetc **Rabbit Burrow** routes it differently from the ERB board whose definition
file HH ships. Symptom was a TMC init failure on gate 0 only.
