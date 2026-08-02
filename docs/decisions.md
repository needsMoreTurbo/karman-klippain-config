# Decision log

Why things are the way they are. Config comments say *what*; this says *why*, and what was
tried and rejected — so a later session (human or agent) doesn't "fix" something that is
deliberate, or re-litigate a settled tradeoff.

**Add an entry when:** a value is counter-intuitive, an obvious-looking alternative was
rejected, a default was overridden, or a bug cost real debugging time. Newest first.
Keep entries short. Link the file, don't duplicate it.

---

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
