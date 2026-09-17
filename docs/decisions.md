## 2026-09-16 — `[output_pin caselight]` back to `scale: 1` (do not "fix" this to 100)
**Problem:** tapping full brightness in either touchscreen UI lit the case light at ~1%. The console
`LIGHT_ON` worked fine, so it read as a UI bug in KlipperScreen/HelixScreen.
**Cause:** Klippain's `fcob_white.cfg` sets `scale: 100` so its `LIGHT_ON`/`LIGHT_OFF` can pass a
0–100 value straight through to `set_pin`. KlipperScreen's Pins panel and HelixScreen's LED control
both assume Klipper's **default `scale: 1`** and always send `VALUE` as a 0.0–1.0 fraction — so their
"100%" arrived as `1.0`, which under `scale: 100` means 1/100 = **1%**.
**Decision:** override to `scale: 1` (`value: 1`) in `overrides.cfg`, and override `LIGHT_ON` to
divide its `S` parameter by 100. Every existing call site still passes 0–100 from `variables.cfg`, so
they keep working unchanged, and both UIs are now correct.
**Why it looks wrong:** `scale: 1` next to a `LIGHT_ON` that takes `S=0-100` looks like a mismatch.
It is not — the division in the macro is what reconciles them. Setting `scale` back to 100 would
re-break both touchscreens.

## 2026-09-14 — Blobifier `z_raise: 8`, `eject_hop: 3`, `pressure_release_time: 2000` (PETG blobs)
**Problem:** on PETG, every blob slid off Blobifier's aluminium tray into the bucket partway through
the purge, and the rest extruded as strings. Worse at 245 °C than 260.
**Found by bench purges** (`BLOBIFIER_TEST PURGE_LENGTH=140`, no swap needed — reproduces the in-swap
symptom): the slide tracks **nozzle height ≈ 8 mm** above the tray (`z_raise` 12 → slid at 60–70%,
9 → 90%, both at ~8 mm). **Ruled out:** purge fan — 30% and 0% slid at the same point.
**Why not lower:** `z_raise: 7` held, but the shorter, wider blob — which stays on the tray when the
nozzle hops, it does not lift with it — jammed between the retracting tray and a nozzle only 1 mm
above it, then rode into the wipe. `eject_hop: 3` gives that clearance; `z_raise: 8` with it deposits
cleanly. `pressure_release_time` 2000 adds ~1 s of 100% deposit fan before the tray swings out.
**Rejected:** adding a pause between hop and tray retract — Blobifier has no such setting, and the
maintainer does not want the stock macro customised for it.
**Open:** unverified on ABS (these variables are shared by every material). The previous ABS/ASA
values (`z_raise 12`, `eject_hop 1.0`, `pressure_release_time 1000`) are kept commented out directly
above each active line in `blobifier.cfg`, for a one-line revert.

## 2026-09-14 — PTFE/heatbreak jam regression closed; the fix is not isolated
**Decision:** close the 2026-08-08 jam regression (`docs/runbooks/blobifier-purge-tuning.md`).
**Evidence:** ~a dozen ABS swaps since 2026-08-20 with no recurrence (user report — logs before
2026-09-07 have rotated away), then 6 consecutive clean PETG `SWAP`s on 2026-09-14 with full-size,
consistent blobs and no FlowGuard trip.
**What we know:** pushback *distance* was a red herring — `15 → 30` did not stop it, and the measured
PTFE→metal boundary (47.4 mm from the nozzle) is cleared by the nominal pushback anyway. The failure
was a slender wisp on the cut fragment buckling in transit.
**What we don't:** which change fixed it. `retract_length 66 → 60` (fatter fragment),
`extruder_move_speed 25 → 40` (shorter wisp, validated on the retract only) and a longer PTFE tube
all landed together. **If jams return, don't revert these one at a time on a hunch** — each has its
own reasoning in `mmu_macro_vars.cfg`; re-inspect the extracted fragment first.

## 2026-09-14 — MMU gear stalls on PETG trace to the Filamentalist rewind load (open)
**Status: OPEN — tension adjustment reduced the stall, did not eliminate it.** Investigation:
`docs/petg-unload-stall-investigation.md`.
**Finding:** on PETG, both gates' gear steppers stalled partway through the fast bowden unload
(`Failed to unload gate because did not home to sensor 'mmu_gear' after moving 150mm`, tip found
200–300 mm above the toolhead). (The two T1 *load* failures on 09-12 were a procedure error — T1
was loaded into a bowden still holding gate 0's stalled strand — not this fault.) Cause (user): the
**Filamentalist rewinder** — PETG grips its o-ring nip harder than ABS/ASA, and the rewind load
overloads the 0.8 A NEMA14 gear motors at speed. Adjusting the tensioner moved the stall point
further into the move, but **80 mm/s still stalled on 2026-09-14 16:03** (gate 1, after 4 clean
swaps at 70).
**Why it looked like something else:** it began with the switch to PETG (09-10) with no config
change, hit gate 1 first (the known-marginal latch), and stalled only at speed — the fast unload
(80 mm/s ≈ 1,050 motor RPM) failed while 50 mm/s homing moved fine, which reads as a torque/speed or
current problem. Lowering `gear_unload_speed` to 50 via `MMU_TEST_CONFIG` did avoid it (09-13), but
only by staying under the extra drag.
**Rule:** an MMU stall that appears with a **new filament** — check upstream drag (respooler
tension, spool path) before touching gear current, unload speed, or latches. Re-check tension for
each new material.
**Decision (2026-09-14): `gear_unload_speed: 80 → 70`**, rewinder loosened a further 1.5 turns.
At that tension gate 1 (fuller spool) still stalled at 80 (~315 mm in, buzz, filament taut) while
70 ran 3/3 gate-1 and 2/2 gate-0 unloads clean. Chosen over a per-gate `gate_speed_override`
(slows loads and homing too, and is per gate not per material) and over more gear current. Costs
~2.5 s per unload. **If it stalls again, go to 60 first.** Mitigated, not root-caused: the
rewinder-disconnect test in `docs/petg-unload-stall-investigation.md` was not run.

## 2026-09-13 — MMU (ERB V2) moves to CAN through the Leviathan's USB-to-CAN bridge
**Decision:** the ERB V2 drops USB-C and its dedicated 24 V brick for one 4-wire Micro-Fit cable
(24 V / GND / CAN_H / CAN_L) from the Leviathan V1.3's `CAN_BUS` port (J33). The Leviathan runs
Klipper in USB-to-CAN bridge mode; `[mcu]` and `[mcu mmu]` in `mcu.cfg` move from `serial:` to
`canbus_uuid:`, and the ERB's Katapult (currently a USB build) is rebuilt for CAN. Procedure, pinouts
and traps: `docs/mmu_can_bus.md`. **Status:** Leviathan-side connector made; not yet wired or flashed.
**Why:**
- Removes the dedicated brick — and with it the powered-while-printer-off recovery trap and one more
  supply tied in through USB grounds (2026-09-12 entry below).
- Takes the MMU off USB. In bridge mode its traffic rides the Leviathan's root-port link, the one MCU
  link that has never dropped; the Sep 11 MMU drop was a retransmit storm behind the K-Hub.
- CAN survives the wiring faults USB doesn't: both transceivers are rated for 24 V on the bus pins
  (Leviathan TJA1057 ±42 V, ERB MCP2542 ±58 V), and a short never reaches the Pi. 24 V on USB D+/D−
  would travel back to the Pi's hub.
- The hardware was already in place: J33 is exactly 24 V/GND/CAN_H/CAN_L on Micro-Fit with a
  termination jumper, the Leviathan already has Katapult, and the Pi already has `can0` host config.
**Rejected:**
- *USB-C for data, only 24 V moved to the printer* — still two cables and a non-latching USB-C plug.
- *USB over the 4-wire cable via the spare Nitehawk V1 USB adapter* — viable (the adapter has D+/D−
  clamps, TVS, 5 A fuse) and needs no firmware change, but D+/D− would share one ground with motor
  current in an untwisted cable (LDO's adapter pairs a ground with each signal), and the MMU stays on USB.
- *Dedicated USB-CAN adapter (BTT U2C)* — leaves the Leviathan untouched and keeps updates to one
  board, but adds a board and another 24 V tap that J33 already provides.
**Cost accepted:** every Klipper update flashes the ERB first and the Leviathan last (reflashing the
bridge takes `can0` down), and a Leviathan USB drop now also takes the MMU (either already shuts
Klipper down).
**Looks wrong, isn't:** CAN_H/CAN_L sit on pins 3/4 of J33 but 4/3 of the ERB's X1 — the cable must
cross them. FYSETC's JP3/JP4 graphic and schematic number the jumper pins oppositely. And
`mmu/base/mmu.cfg`'s `[mcu mmu] serial:` is dead — `[include mmu/base/mmu_*.cfg]` doesn't match it.
**Evidence:** desk research only — FYSETC ERB V2.0 schematic, LDO Leviathan V1.3 KiCad, LDO Nitehawk
USB Adapter V1.5.1 schematic, transceiver datasheets, and read-only Pi inspection (Katapult/Klipper
`.config`, shell history, `/etc/systemd/network/25-can.network`). Nothing wired or tested yet.

## 2026-09-12 — MCU dropouts are USB-level; journald made persistent, uhubctl 2.6.0 built from source
**Root cause found (2026-09-13): a bad pin in the Microfit connector where the Nitehawk umbilical
meets its USB adapter board.** It surfaced when the toolboard stopped enumerating entirely after a
round of cable moves: 24V/3V3/ACT LEDs on (STM32 running Klipper — firmware sets `!PC6` at startup)
but **HUB LED off**, and `usb1-port1` read `not attached` with no kernel activity at all. Swapping the
Pi→adapter cable changed nothing (the original cable failed too); handling the connector made the hub
flap (up 1.4 s, up 0.2 s, then stable). Maintainer re-pinned the whole connector → HUB LED on, all
devices enumerate, `FIRMWARE_RESTART` → ready. This explains the toolhead-side drops (hub-level
`usb 1-1: USB disconnect`, instant recovery). **Not yet proven fixed** — past drops were days apart.
**Still unexplained:** (a) the hub still enumerates at 12 Mbit after the repin, so that pin was not
what blocked high-speed; (b) the Sep 11 MMU drop is on the K-Hub, not the umbilical (the 3 s `usb 3-1.4`
blip at 21:30:12 on Sep 12 coincided with the maintainer reseating USB cables — likely not a fault).
Watching the MMU to see whether Sep 11 was a one-off.
**Recovery trap — the MMU board stays powered when the printer is switched off** (it runs from a
dedicated 24 V brick; moving it onto the printer supply is planned, which removes this trap and one
of the separate supplies tied together through USB grounds). It keeps Klipper's
shutdown state across power cycles, so every start fails with `Can not update MCU 'mmu' config as it
is shutdown` until a `FIRMWARE_RESTART` resets it. And `FIRMWARE_RESTART` can only reset an MCU whose
USB link is up: after a drop it logs `Unable to issue reset command on MCU 'x'` and silently skips
it. If that line appears, power-cycle that board, then restart again.
**Finding:** the "firmware crashes `FIRMWARE_RESTART` won't fix" are USB devices leaving the bus,
not Klipper faults — same class as the 2026-09-03 CH340 dropout below. Signatures: `Got EOF when
reading from device` (Sep 9, toolhead) or a retransmit storm (Sep 11, mmu: `bytes_retransmit`
9→152 in 3 s, `rto` 3.2) → `Timeout with MCU` → shutdown; afterwards `Unable to open serial port …
No such file or directory`. `FIRMWARE_RESTART` reopens a device node — it cannot make USB
re-enumerate, so it only "works" once the device comes back by itself. **Reboots don't reliably
fix it either:** Sep 7 was *four* host boots in 78 min (toolhead absent after boots 1–2, mmu after
boot 3, clean on 4). Only hub-attached MCUs have dropped; the root-port `mcu` never has.
`bytes_invalid` stayed 0 and bed heating didn't correlate (Sep 9 bed at 100 °C, Sep 11 cold).
**First kernel capture (same day, 21:08:55):** `usb 1-1: USB disconnect` — the Nitehawk's *hub
itself* dropped off the Pi's root port, taking Beacon and the toolhead MCU with it. No
`error -71` / `clear tt` / over-current / reset beforehand. The hub re-enumerated in 0.5 s and both
devices were back in 1.8 s (again at 12 Mbit), so one `FIRMWARE_RESTART` suffices for this variant.
Context: manual MMU recovery — two `G1 E50` at 255 °C with gear sync active, then `CLEAN_NOZZLE`
~14 s before the drop (brushing had finished). Localizes the fault to the hub / umbilical / USB
adapter / toolboard-power path — not Beacon, the STM32, Klipper, or bandwidth. (Sep 9's toolhead
drop came after 100 min idle, so filament motion isn't the whole story.)
**Hardware (corrected same day):** toolhead + Beacon sit behind the Nitehawk-SB v2's *onboard*
hub (`1a86:8091`, QinHeng). It runs at 12 Mbit although it is high-speed capable: it is the only
one of five full-speed devices that answers the kernel's device-qualifier probe (`usb 1-1: not
running at top speed`; Beacon and all three MCUs correctly refuse). So the high-speed handshake
across the umbilical + USB adapter board is failing — a **signal-quality symptom, not a bandwidth
limit**. mmu + CH340 sit behind a BTT K-Hub (`1a40:0101`, fed from 24 V) running at its full
480 Mbit; its single TT (`bDeviceProtocol=01`) is by design. Downstream devices cannot lower a
hub's own link speed. Nothing is short of bandwidth: from 1-s Klipper stats (Sep 11) every device
peaks under 1 % of 12 Mbit (mcu 11 kB/s, beacon 7.2, mmu 5.4, toolhead 4.8). Both hubs are
self-powered, so the Pi 5's 600 mA USB cap (3 A PSU, no USB-PD,
`/proc/device-tree/chosen/power/max_current` = 3000) carries essentially only the C920 — the PSU
is under-spec for a Pi 5 but an unlikely dropout cause; do **not** set `usb_max_current_enable=1`
on the 3 A brick. **Open lead:** LDO's Nitehawk-SB v2 docs ("ESD Hardening") name communication
loss as an ESD symptom, from filament friction in the reverse bowden charging the extruder, and
specify grounding the extruder motor body to the toolboard and the USB adapter board to the frame
— directly relevant with a 2 m MMU bowden. **Maintainer confirmed both grounding cables and the
umbilical chain-end zip-ties are installed**, so this is not a missing-mitigation case.
**Decision 1 — journald `Storage=persistent`, `SystemMaxUse=500M`** (was `volatile`, an SD-wear
setting that is moot on NVMe). Every earlier incident's kernel log died with the next reboot.
**Trap:** editing the conf and restarting journald is not enough on systemd 252 — the boot-time
flush ran while storage was volatile, so nothing moves to `/var` until `journalctl --flush`.
Backup at `/etc/systemd/journald.conf.bak`. After the next dropout:
`journalctl -k -b -1 | grep -iE 'usb|clear tt|disconnect|over-current'` (`-b 0` if no reboot).
**Decision 2 — uhubctl 2.6.0 from source (`~/uhubctl` @ tag v2.6.0 → `/usr/local/sbin`), not
apt.** Bookworm's 2.5.0 predates Pi 5 support and builds the wrong root-hub sysfs path on kernel
≥ 6.0 (`1:1.0/1-port1/disable` doesn't exist here; `1-0:1.0/usb1-port1/disable` does). The Pi 5's
onboard hubs *advertise* per-port power switching (`ppps`) but all four ports share one VBUS,
which drops only when every port is off. Recovery, printer idle or already shut down — drops
every USB device including `mcu` and the webcam; SSH survives:
`sudo sh -c 'for h in 1 2 3 4; do uhubctl -l $h -a 0; done; sleep 5; for h in 1 2 3 4; do uhubctl -l $h -a 1; done'`,
then `FIRMWARE_RESTART`. **Not yet proven** to clear a real dropout.
**Log-reading traps (both cost time here):** (1) The Pi has no RTC — `wtmp`/`last reboot` times
are pre-NTP fake-hwclock values, wrong by ~1 h and duplicated. Date boots with `uptime -s`.
(2) Conversely, the second number on klippy's `Start printer at … (unix mono)` line **is** host
uptime (`CLOCK_MONOTONIC_RAW`) — a value near 10 means the host just booted. It's the reliable
reboot marker; don't "correct" it against `wtmp`.

## 2026-09-03 — A diagnostic accessory took the whole printer down; accessories get guarded, not trusted
**Decision:** `probe_mode_on_homing: 0` in `bdpressure.cfg`, plus a patch to `bdpressure.py`
(fork `karman-patches`) that guards every port access. **Generalisation: any Klipper module that
registers an event handler on a motion path must not be able to raise out of it.**
**What happened:** at 15:46:48 the BDPressure CH340 dropped off the USB bus by itself — a storm of
`clear tt 3 error -32` (hub transaction-translator errors; it shares hub `3-1` with the webcam),
then `USB disconnect`. It re-enumerated 6.5 min later as **ttyUSB1**, but Klippy still held the fd
for the vanished ttyUSB0. Nothing complained for 33 minutes. At 16:14 an ABS print started; at
16:19:45 `contact_auto_calibrate` ran `G28`, which fires `homing:homing_move_begin` →
`set_probe_mode()` → `usb.write('e;')` → `OSError(EIO)`. That escaped through `send_event()` inside
`homing_move()`, and Klipper turns *any* non-`CommandError` exception into
`Internal error on command:"G28"` → **full shutdown, all four MCUs emergency-stopped**, five
minutes into a 3 h 15 m print.
**Why the hook existed at all:** vendor code re-asserts probe mode on every homing move. Karman
never uses this sensor as a probe — the vendor `[probe]` section is deliberately omitted because
Beacon owns probing — so the hook was **pure risk for zero function**. Turning it off is the real
fix; the exception guards are the seatbelt for the paths that remain.
**The trap that made this expensive:** the hazard was already written down in `overrides.cfg`, but
phrased as *"a cable pulled mid-session makes the next G28 throw"* — framing it as an operator
action. **USB devices unplug themselves.** A hazard whose trigger is written as a human mistake
reads as avoidable and never gets fixed; write the trigger as the failure mode, not the finger.
**Second trap — the failure is silent and delayed.** 33 minutes and a whole `START_PRINT` passed
between the disconnect and the bang, so the log evidence is nowhere near the symptom. The module
now announces `sensor OFFLINE` once, when the fault is first touched.
**Physical root cause, still open:** the CH340 is a 12 Mbit full-speed device sharing a hub TT with
a 480 Mbit webcam that Crowsnest streams continuously. Move it to a root port or a camera-free hub.
**Deployment gotcha found while verifying this — `FIRMWARE_RESTART` does NOT reload a `.py`
module.** Klipper's restart builds a fresh `Printer` object *in the same Python process*, and
`load_object()` goes through `importlib.import_module`, so `sys.modules` still holds the copy
imported at boot. A patched `extras/*.py` needs a **host restart**
(`systemctl restart klipper`, or `POST /machine/services/restart?service=klipper`). The failure is
worse than a silent no-op: the old code doesn't read the new config option, so Klipper's
`check_unused_options` rejects it as *"Option 'probe_mode_on_homing' is not valid in section
'bdpressure bd_pa'"* — an error that points at the config file when the config file is correct.
Two restarts were burned chasing that. `.cfg` edits are fine with `FIRMWARE_RESTART`; `.py` edits
are not.
**Not the cause, though it looked like it:** the chamber soak timed out ~30 s earlier (47.2 of a
48.0 minimum). That is the documented designed behaviour — see 2026-08-02 below — and it merely
released START_PRINT into the homing move where the pre-armed fault was waiting.

## 2026-08-20 — Some `MMU_TEST_CONFIG` parameters are silent no-ops (sync-feedback / FlowGuard)
**Decision:** treat `sync_feedback_debug_log` and `flowguard_max_relief` as **startup-only**. Edit
`mmu_parameters.cfg` and `FIRMWARE_RESTART`; never trust `MMU_TEST_CONFIG` for them.
**Why:** both are consumed when `SyncControllerConfig(...)` is built inside `_init_controller()`
(`~/Happy-Hare/extras/mmu/mmu_sync_feedback_manager.py:609,615`), called **only** from `__init__`
(line 93). `set_test_config()` updates the attribute on the *manager* (lines 108, 113), but the code
that uses them reads `ctrl.cfg.log_sync` and `ctrl.cfg.flowguard_relief_mm` — the frozen startup
copy. Nothing propagates the change.
**Why this is nastier than a plain no-op:** `get_test_config()` echoes the *manager's* value back
(lines 132, 136), so `MMU_TEST_CONFIG` prints `sync_feedback_debug_log = 1` and looks like it
worked. Cost a whole test print: the log was "enabled", a clog was reproduced, and no
`sync_<gate>.jsonl` was ever written.
**Generalisation:** other `MMU_TEST_CONFIG` params *do* apply live (verified this session:
`TOOLHEAD_RESIDUAL_FILAMENT`; likewise all `_MMU_CUT_TIP_VARS` via `SET_GCODE_VARIABLE`). The
distinguishing question is whether the value is re-read per use or captured into a config object at
init. **Check the consumer, not the setter.**
**Telemetry location** (not stated in the config comment): `sync_<gate>.jsonl` lands in the same
directory as `klippy.log` → `~/printer_data/logs/sync_0.jsonl`, `sync_1.jsonl`. Plot with
`~/Happy-Hare/utils/plot_sync_feedback.sh`.

## 2026-08-20 — `flowguard_max_relief` is not measured in extruded filament
**Decision:** convert before choosing a value; do not read the raw number as millimetres of print.
**Why:** `_relief_effort()` (`mmu_sync_controller.py:971`) accumulates
`d_ext * ((rd_ref / rd_cur) - 1)` — extruder motion scaled by the **fractional rotation-distance
deviation**, i.e. how hard the controller is counter-steering, not how much filament moved. That
deviation is capped by `sync_feedback_speed_multiplier` (5%) and measures ~4.5% in our logs (RD
swings 22.32 → 23.38). Dividing by ~0.045: **40 ≈ 890 mm of filament, 15 ≈ 330 mm, 8 (HH default)
≈ 180 mm.** The config's original "walk it toward ~15" note reads as conservative and is not — it is
still ~330 mm of under-extruded printing before a trip.
**Bigger caveat:** FlowGuard fires only when compression is **pegged at the extreme** (a hard
stoppage where the synced gear piles filament into the buffer). A partial obstruction that merely
degrades flow may never peg, and then **no threshold helps**.
**Outcome:** a full test print at 40 failed to catch a real clog. Set to **8** (HH's default,
≈180 mm) on 2026-08-20. If 8 false-triggers, step up (12, 15) — do not go back toward 40.
**Process note:** two test prints were burned here — one on a `MMU_TEST_CONFIG` call that was a
silent no-op, one holding 40 "to gather telemetry" on a threshold already known to be ~890 mm of
filament. Read what a parameter actually does *before* asking the maintainer to run a print on it;
a print is expensive and they are the only one who can run it.

## 2026-08-14 — Adaptive PA's visible benefit is muted by `dont_slow_down_outer_wall`
**Decision:** none — a validation finding, recorded so it isn't mistaken for a bug later.
**Why:** three test prints (no PA / flat 0.032 / adaptive matrix; model:
[Printables #437927](https://www.printables.com/model/437927-pressure-advance-torture-test))
showed a dramatic difference between no-PA and either PA-enabled print, but only a subtle one
between flat 0.032 and the adaptive matrix — despite the matrix spanning a measured 0.028–0.039
(docs/pa_physics.md). Cause: `dont_slow_down_outer_wall` is enabled in the Orca profile, which
keeps outer-wall speed — and so the flow and accel-burst PA acts on — close to constant across the
part. The outer wall is most of what's visible, and at nearly-constant flow/accel the matrix and
the flat value land close to the same table entry. The matrix's larger effect is concentrated on
internal features with more speed variation, and on any profile without that setting enabled.

## 2026-08-13 — BDPressure: solve for the Hr−Hl zero crossing; never auto-apply the result
**Decision:** replaced the vendor's answer-selection in `cmd_stop` (`~/bd_pressure/klipper/
bdpressure.py`, outside this repo, frozen in moonraker.conf) with a least-squares fit for the PA
where `Hr − Hl` crosses zero, and made applying the result opt-in via `apply_result` (default off).
**Why:** the vendor scanned *backwards* for the last row with `Hk < 5`, then searched only from
there to the end for `min(res + |Hr−Hl|)`. `Hk` is 0 on most rows, so that window is always the
tail of the sweep — the highest PA values — chosen before any physics. On a clean 41-point sweep
whose `Hr − Hl` crossed zero at **0.031 ± 0.003** it returned **0.076**, and then silently ran
`SET_PRESSURE_ADVANCE`, leaving the machine on a value no config records and that reverts at the
next restart. `Hr − Hl` is pressure after the fast segment minus pressure before it: negative =
under-compensated, positive = over-compensated, so the answer is a **root, not a minimum**. The
new code also refuses — it requires a real sign change, a 3σ slope and a crossing inside the swept
range — where the old one could never fail. Verified against the real rows and three adversarial
inputs. **This is module code, so it needs `sudo systemctl restart klipper`, not FIRMWARE_RESTART.**

## 2026-08-13 — Flow-scaled `PA_E` geometry, with a `GEOM_SCALE` escape hatch
**Decision:** `PA_CALIBRATE` scales the pattern by `MAX_VOLUMETRIC/25`; `GEOM_SCALE` overrides it.
**Why:** the vendor's fixed 20/40/20 mm pattern makes the event longer as flow falls, and the
firmware analyser cannot handle a long event — 14.4 mm3/s yielded **11 usable steps of 50**.
Scaling to a constant ~2.06 s event took the same flow to **41 of 42**. The override exists
because scaling works *against* any test that reads plateau LEVELS: the melt has a slow relaxation
mode of τ ≈ 2.8 s (measured, `physics/`), so a settled plateau needs a long segment. At
MAX_VOLUMETRIC=5 the scaled segment is 0.94 s (32% settled) against 4.71 s (86%) at GEOM_SCALE=1.

# Decision log

Why things are the way they are. Config comments say *what*; this says *why*, and what was
tried and rejected — so a later session (human or agent) doesn't "fix" something that is
deliberate, or re-litigate a settled tradeoff.

**Add an entry when:** a value is counter-intuitive, an obvious-looking alternative was
rejected, a default was overridden, or a bug cost real debugging time. Newest first.
Keep entries short. Link the file, don't duplicate it.

---

## 2026-08-12 — `bdpressure.py` USB reads are patched locally; the stock code **fabricates data**
**Decision:** `~/bd_pressure/klipper/bdpressure.py` carries a local patch to `cmd_read`'s USB
branch (original kept as `bdpressure.py.orig`). ⚠️ **`[update_manager bd_pressure]` in
`moonraker.conf` must stay commented out** — re-enabling it will pull upstream and silently revert
this, and the symptom is bad *data*, not an error.
**Why:** the stock code did
```python
response = self.usb.read(self.usb.in_waiting or 1)...     # unframed grab
if response: ...
else:        self.pa_data_process(gcmd, self.old_res)     # re-process the PREVIOUS result
```
Two defects compounding. The read is unframed, so it can capture a **partial** `R:` line (that
step is silently dropped). And when nothing has arrived it **re-processes the last result** —
which `pa_data_process` then appends against the *current* PA value, relabelling a stale
measurement with a PA it was never measured at. `cmd_stop` picks its answer out of that array.
**Evidence** — distinct measurements per sweep:

| Run | rows | distinct | ratio |
|---|---|---|---|
| MV=25 @5000 (×4) | 22–23 | 20–22 | **1.0–1.1** ✅ |
| MV=14.4 @3000 → "PA 0.048" | 17 | **3** | **5.7** ❌ |
| MV=12 @3000 → "PA 0.050" | 31 | **11** | **2.8** ❌ |

The sensor only emits an `R:` line when `has_plus()` fires, which is *not* reliably once per sweep
step, while the module polls once per step. The two rates alias — which is why 14.4 was worse than
both 12 and 25 rather than degrading monotonically with flow.
**Consequence:** the apparent "PA rises from 0.031 to ~0.049 at low flow" was an **artifact** and
was nearly adopted as the basis of the adaptive-PA model. High-flow data (MV=25) is unaffected —
dup ratio 1.0 — so **PA ≈ 0.031 @ 25 mm³/s / 5000, σ ≈ 0.0019 still stands.**
**The patch:** accumulate bytes across calls, split on newlines, keep the **newest complete** `R:`
line, and **skip the step** when no fresh result arrived rather than duplicating. Adds a
`bd_pa reads: N fresh, M skipped of T steps` line to `cmd_stop`, so a thin sweep is visible at the
time instead of three runs later. Verified with six mock-serial cases against the extracted code
(complete line, nothing, partial-then-completed, two-lines-newest-wins, text noise, partial
surviving across calls).
**Second patch, same file — the warm-up discard in `cmd_stop`.** Original was
`pop(0);pop(1);pop(2);pop(3);pop(4)`; each pop shifts the list, so it removed original indices
**0,2,4,6,8** — decimating alternate entries rather than dropping the first five. Now
`drop = min(5, len//4)`, which reproduces the intended behaviour exactly at ≥20 points (verified:
a 22-point high-flow sweep still selects 0.032) while not halving a sparse one.
**⚠️ Fixing it is necessary but NOT sufficient at low flow.** `cmd_stop` then picks its search
start by scanning backwards for the last entry with `Hk−avt < 5`, which assumes overshoot grows
monotonically once past the optimum. Sparse data breaks that: a 10-point 14.4 mm³/s sweep had
`Hk−avt` = 0,0,7,7,0,0,20,17, so the scan landed at 0.074 and still missed the true minimum at
0.044. **Do not trust `Calc the best Pressure Advance` on sparse sweeps — derive PA from the
logged `bd_pa: R:` rows instead** (minimum of `res + |Hr−Hl|`, cross-checked against where
`Hr−Hl` crosses zero). The rows are the data; the module's verdict is not.
**Still open — the real limiter:** at 14.4 mm³/s the sensor emits a result only every **~23.6 s**,
i.e. one per **5** sweep steps (10–11 fresh of 50, perfectly periodic). At 25 mm³/s it emits about
once per step, which is why high-flow data is clean. Until that is understood, low-flow sweeps
yield ~10 points with ±4-step PA attribution slop — comparable to the effect being measured.
MV=7.2 fails differently again: 50 distinct but incoherent results (`k_l`≈10, `Hr−Hl` pinned near
−200), a genuine signal problem rather than a read or selection problem.

## 2026-08-12 — PA measurements need a thermal **soak**; `M109` alone is not enough
**Decision:** `KARMAN_PA_CALIBRATE` (`bdpressure.cfg`) now heats **in position**, then soaks —
`soak_cold: 240` s when the nozzle starts >5 °C below target, `soak_hot: 30` s for back-to-back
runs — then primes `prime_mm: 40` before the sweep. It also logs the **starting nozzle
temperature**, so a later analysis can tell whether a run was settled without reconstructing it
from `klippy.log`. Default `purge_z` raised 40 → 80 to stay clear of the accumulating blob.
**Why:** `M109` waits only for the **nozzle**. The BDPressure strain gauge sits at the groove
mount and keeps heating for minutes afterwards, and a sweep run during that drift biases the
firmware's edge detection high. Measured directly, six repeats at an identical requested 275 °C:

| Run | Nozzle at macro start | PA | `res` |
|---|---|---|---|
| 3 | **33 °C (cold start)** | **0.040** | **10** |
| 4–7 | 275 °C (settled) | 0.030 / 0.032 / 0.030 / 0.034 | 6–8 |

The log trace is unambiguous: run 3 reached target only at t+81 s and swept while the assembly was
still climbing. Settled repeatability is **σ ≈ 0.0019** (range 0.004, ~one quantization step);
including unsettled runs inflates that to σ ≈ 0.0037 with a 0.010 range.
**Also:** a long soak oozes, and the UHF melt zone holds ~33 mm (`toolhead_residual_filament`, see
the entry below), so without the prime the sweep would start on a partly empty nozzle.
**Corollary — `res` is a usable quality filter.** It is the fit error at the chosen point (first
trailing number of `Calc the best Pressure Advance: PA, res, index`). It flagged the bad run
independently of any temperature data. **Discard and re-run any sweep with `res >= 10`.**
**Consequence for old data:** the earlier 260 °C result (0.040) was *itself* a heat-up transient,
so there is **no valid 260 °C measurement** — the temperature question is untested, not answered.
**Best current ABS figure:** ~**0.031** at 275 °C, against `material_parameters` ABS `0.0480` —
a 50% gap worth resolving on its own.
**`soak_cold: 240` is a considered starting value, not a measured optimum** — the clean runs were
1–3 min apart. Worth calibrating if it ever matters.

## 2026-08-08 — `toolhead_residual_filament: 33` — the 2026-07-17 entry below was wrong
**Decision:** 33 (measured), paired with `retract_length: 66` in `mmu_macro_vars.cfg`.
**Supersedes the 2026-07-17 entry**, which settled on 25.
**Why:** bisecting `retract_length` live gave **58 flat · 61 flat · 64 cut-air**. Per
`mmu/base/mmu_cut_tip.cfg:80` the cut tip lands at
`true_pool + retract_length − residual − retracted_length`, and the cut fails once that exceeds
`blade_pos: 69`. Solving at the 61/64 boundary: `true_pool = 94 + retracted − R_fail` → **32..35**.
That reproduces the *original* 2026-07-13 measurement of 35, which the 2026-07-14 hand-calc had
talked down to 25. The 2026-07-17 entry's own process note — *trust the measurement over the prior
when the hardware is unusual* — was written about this exact mistake and then repeated it. Twice
now the UHF melt pool has been judged "implausibly large" and twice the measurement was right.
**⚠️ `residual` and `retract_length` are coupled — never move one alone.** Once residual is correct
the tip lands at `retract_length − retracted_length`. Raising residual 25→33 *without* moving
`retract_length` would have dropped the tip from 61 to 53 and **doubled** the sliver left in the
hotend (8mm → 16mm) — the opposite of the intent. 66 parks it at ~64 (≈5mm sliver); **68 was
rejected** because at the top of the measured bracket it leaves ~1mm of blade margin.
**Corroboration:** at residual 33 the load advances 8mm less (67.5 → 59.5mm), i.e. the old config
was over-advancing — which is precisely the per-swap load ooze that `toolhead_ooze_reduction: 2`
was added to mask on 2026-07-14. **Open:** ooze_reduction should probably return toward 0; not yet
observed either way.

## 2026-08-08 — Blobifier purge floor 140, and why it makes the slicer matrix vestigial
**Decision:** `variable_purge_length_minimum: 140` (was 30) in `mmu/addons/blobifier.cfg`.
**Why:** only part of any purge is flush — 35mm is displacement (residual 33 + retract 2) that
pushes old material out but replaces nothing. Measured, in corrected melt zones (33mm ≈ 79mm³):
0.9 MZ under-flushed badly, 2.0 left →light mid-transition, 2.7 fixed →dark but not →light,
**3.2 (floor 140) is clean both ways**.
**The runbook's premise was disproved mid-execution.** `purge_length_minimum` was chosen precisely
*because* it is a floor that would leave the "already generous" →light direction alone. →light was
never actually clean at its natural value — that label came from an unverified 2026-08-02
observation made with non-contrasting filament. So the floor had to rise above both natural values
(→dark 45, →light 89), and **every swap now purges 140 regardless of direction**; the slicer's
41/218 mm³ matrix no longer affects anything. That is deliberate.
**Rejected:** `_modifier` alone can't fix →dark (its flush term derives from a 41 mm³ slicer volume
sized for a ~10mm melt zone, off by ~5× here); `_addition` inflates both directions equally.
**The real fix is upstream in the slicer purge volumes** — explicitly out of scope for that runbook,
and still open.
**Watch:** `purge_length_maximum: 150`. At 140 a swap is still one blob; past 150 Blobifier splits
into multiple blobs. Little headroom left. Same-tool print-start priming now costs 140mm, not 30mm.

## 2026-08-08 — Per-gate bowden lengths; HH's autotune only ever tunes gate 0
**Decision:** `variable_bowden_lengths: 1` in `[mmu_machine]` (overriding the NightOwl vendor
default of 0), plus `toolhead_homing_max: 60 → 100` as headroom, then `MMU_CALIBRATE_BOWDEN` on
gate 1. Result: `mmu_calibration_bowden_lengths = [1462.7, 1505.4]`.
**Why:** consistent `Failed to reach toolhead sensor after moving 60.0mm` on T0→T1. Gate 1's path
is ~25mm longer than gate 0's, so it needed ~57mm of homing where gate 0 needed ~32 — against a
60mm ceiling. It failed *most* of the time and squeaked through at 58.8mm once, which is what made
it look intermittent rather than systematic.
**The trap:** `autotune_bowden_length: 1` is on and HH reports `Extra homing movement` for every
gate, so it looks self-correcting. It is not — the autotune is hard-gated on
`gate_selected == 0` (`~/Happy-Hare/extras/mmu/mmu_calibration_manager.py`, with a TODO saying it
could work for other gates "if variable_bowden_lengths is True"). With the vendor default the two
gates also shared one stored length and overwrote each other's value (1465.1 ↔ 1462.7) on every
swap. **Gates > 0 must be calibrated by hand; they will never converge on their own.**
**Verified:** T1 homing dropped 57.1mm → 19.9/16.9mm; no failures since.

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
> ⚠️ **SUPERSEDED 2026-08-08 — the value in this entry is wrong.** The pool measures **33**, not 25;
> the 35 dismissed below as "briefly" held was the correct measurement. See the 2026-08-08 entry.
> The reasoning about *why low values break things* remains valid and worth reading.

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
