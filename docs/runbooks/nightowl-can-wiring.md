# Runbook — NightOwl on CAN: one Micro-Fit cable (24 V + CAN) from the Leviathan

**Objective:** the ERB V2 in the NightOwl gets its power **and** its Klipper link over one 4-wire
Micro-Fit cable from the Leviathan V1.3's `CAN_BUS` port (J33). The Leviathan runs as a USB-to-CAN
bridge. The dedicated 24 V brick and the ERB's USB-C cable are retired. **Done means:**
- Klipper runs with `[mcu]` and `[mcu mmu]` on `canbus_uuid:`;
- the bus is clean;
- a **cold power-cycle of the printer comes up ready with no `FIRMWARE_RESTART`** (the
  stale-shutdown trap is gone);
- after the Nightwatch is reinstalled, real `T0`↔`T1` swaps work over CAN.

**Status:** 🟡 Steps 1–8 and 11 done 2026-10-16 (cold power-cycle passes); **Step 9 (swaps over CAN) pending** the Nightwatch reinstall
**Created:** 2026-10-15
**Prerequisites:**
- The printer is idle and **no print is needed for several hours**: the printer is unusable from
  Step 4 to Step 8.
- The NightOwl is open for maintenance (dual Nightwatch removed; this runbook works with it out).
- A meter. A USB-C cable (Pi → ERB) on hand for Step 5. Crimp tool and Micro-Fit 3.0 crimps.

## Read first

- **`docs/mmu_can_bus.md` is the procedure** (hardware facts, wiring checks §2, conversion
  §3.0–3.5, routine updates §4, recovery §5). This runbook adds the order, the decisions made
  since, the cable build and the acceptance tests. **Do not re-derive its contents; follow its
  commands exactly.**
- **`docs/decisions.md` 2026-09-13** explains why CAN through the Leviathan bridge, the rejected
  alternatives, and the cost: every Klipper update must reflash the ERB first and the Leviathan
  last.
- **`docs/decisions.md` 2026-09-12** describes the trap this removes: the MMU board stays powered
  on its brick when the printer is off, keeps Klipper's shutdown state, and needs a
  `FIRMWARE_RESTART` on every cold start after a dropout.

## Scope

1. Build the cable and fit the **Micro-Fit keystone adapter** (panel pass-through).
2. Wiring checks with the power off (`mmu_can_bus.md` §2).
3. Flash: Leviathan → bridge, ERB Katapult → CAN, ERB Klipper → CAN (§3.0–3.4).
4. `mcu.cfg` → `canbus_uuid:` (§3.5), first start, bus health.
5. Cold power-cycle test.
6. After the Nightwatch is reinstalled: sensors and swaps over CAN.
7. Retire the brick and USB-C; update docs, CLAUDE.md and TODO.md.

## ⚠️ Out of scope — do not touch

- **The Nitehawk toolboard stays on USB.** Leave its `[mcu toolhead] serial:` and firmware alone.
  So do BDPressure (USB) and Beacon (USB).
- **The MMU pin aliases in `mcu.cfg`** (`[board_pins mmu_mcu]`), especially
  `MMU_GEAR_UART=gpio11` and `MMU_SYNC_ANALOG=gpio26`. Both are measured and validated; CAN changes
  only the link. The "Rabbit Burrow" wording in that comment block is a known naming quirk:
  **the board is an ERB V2.0** (maintainer, 2026-10-15). Don't touch the aliases because of it.
- **`mmu/base/mmu.cfg`'s `[mcu mmu] serial:`** is dead config: Klippain's
  `[include mmu/base/mmu_*.cfg]` doesn't match that filename. Don't "fix" it. `mcu.cfg` holds the
  only live `[mcu mmu]`.
- **Any Happy Hare setting.** No MMU parameter changes because of CAN. This includes
  `gear_unload_speed`, currents, FlowGuard and bowden lengths.
- **The Pi host CAN config** (`/etc/systemd/network/25-can.network`,
  `/etc/udev/rules.d/10-can.rules`). It's already correct (found 2026-09-13). Don't re-create it.
- **Happy Hare v4.** The maintainer moved CAN *ahead of* the v4 series (2026-10-11 order change).
  Do this on v3; the v4 runbooks then start from CAN.
- **No toolhead motion is involved** until Step 9's swaps, which use existing validated macros.
  Keep-out zones (CLAUDE.md) are unchanged.

## Pre-resolved decisions (maintainer)

1. **Board = FYSETC ERB V2.0** (2026-10-15). `mmu_can_bus.md`'s pinout, jumpers (JP1/JP2/JP3/JP4)
   and Katapult/Klipper CAN settings (RX gpio0, TX gpio1, 1 Mbit/s) apply as written.
2. **Do it now, on Happy Hare v3, during the current NightOwl maintenance** (2026-10-11). This
   reverses the 2026-10-10 "v4 before CAN" order. It was the 2026-09-13 evaluation's
   recommendation anyway: hardware first, on known-good software.
3. **No extra fuse.** The rule: fuse only if J33 is unfused, and it is fused. Leviathan V1.3
   KiCad (`MotorDynamicsLab/Leviathan`, `KiCad/V1.3/Leviathan_V1.3.kicad_sch`, read 2026-10-15):
   J33 pin 1 sits on the global `+24V` net, which is the output of the board's **10 A main fuse
   F3**, after the reverse-polarity FET Q2 and the 28 V TVS D21 on `PWR_IN`.
   **Consequence:** the cable's 24 V and GND conductors must be rated for 10 A, so use **18 AWG**.
   The ERB has no fuse or TVS on X1 (`mmu_can_bus.md` §1); that's accepted as designed.
4. **The cable is built from scratch** (the maintainer hasn't started it):
   - 4 conductors: 24 V and GND in 18 AWG; CAN_H and CAN_L in 22–24 AWG, **twisted together as a
     pair** (about one twist per 25 mm).
   - Length: measured along the actual route, plus about 10 % slack.
   - Leviathan end: Micro-Fit 3.0, 2×2 (J33: 1 = +24 V, 2 = GND, **3 = CAN_H, 4 = CAN_L**).
   - ERB end: green 4-pin pluggable terminal (X1: 1 = +24 V, 2 = GND, **3 = CAN_L, 4 = CAN_H**).
   - **H/L must cross between the ends.** The meter check in Step 3 proves it.
5. **Micro-Fit keystone adapter: in scope.** Print it and fit it as the panel pass-through for this
   cable. **The hex-insert adapters and the barrel-jack connector are dropped** (TODO cleanup in
   Step 11).
6. **Termination:** JP1 `term` fitted on **both** boards. They are the two ends of the bus.
7. **Save every kconfig in `~/klipper-kconfigs/`**, as `mmu_can_bus.md` does: `erb-usb.config`,
   `leviathan-canbridge.config`, `erb-katapult-can.config`, `erb-can.config`.

## Steps

### 1. Preflight (model, read-only)

```
ssh ernst@192.168.1.240 'git -C ~/klipper describe --tags; git -C ~/klipper status -s | head; head -40 ~/klipper/.config | grep -E "CONFIG_MACH|BOARD_DIRECTORY|FLASH_APPLICATION|USB|CANBUS"; ls ~/klipper-kconfigs; ls ~/katapult-env/bin/python3; grep -n "^serial\|^canbus_uuid" ~/printer_data/config/mcu.cfg'
```

Expected:
- Klipper `v0.13.0-662-gbd99b19b0`. The host shows `-dirty`; record what `status -s` lists.
  Firmware built from it will carry the `-dirty` suffix, which is harmless.
- `~/klipper/.config` is the **ERB USB build** (RP2040, 16 KiB offset, USB). If it isn't, stop:
  `mmu_can_bus.md` §3.0 depends on it.
- `~/katapult-env` exists.

Record the results in this runbook's status log.

### 2. Build the cable and fit the keystone (USER)

Follow the cable spec in Pre-resolved 4. Fit the printed Micro-Fit keystone adapter at the
panel. Route the cable away from heater and stepper wiring where possible. **Leave both ends
unplugged** until Step 3.

### 3. Wiring checks — power OFF, cable plugged in at both ends (USER, with the model)

On the ERB, before anything is powered:
- **JP3 + JP4 → CAN** position;
- **JP2 (USB 5 V) → off**;
- **JP1 term → fitted**.

Confirm JP1 is fitted on the Leviathan too.

Then run `mmu_can_bus.md` **§2** with a meter, all three checks:
1. CAN_H–CAN_L ≈ **60 Ω**.
2. Leviathan U12 pin 7 ↔ ERB U11 pin 7 ≈ **0 Ω**, and pin 6 ↔ pin 6 ≈ 0 Ω. A reading of 60 Ω
   means H/L are swapped; open means the jumpers are wrong or a wire is open.
3. Power: X1 pin 2 ↔ ERB GND ≈ 0 Ω, and **no** continuity from +24 V to GND or to either CAN
   line.

**All three must pass before anything is powered.** If any fails, stop and fix the cable or
jumpers.

### 4. Leviathan → USB-to-CAN bridge (USER runs; model watches)

Klipper is stopped from here until Step 7.

```
ssh ernst@192.168.1.240 'sudo service klipper stop'
```

Then `mmu_can_bus.md` **§3.0** (save `erb-usb.config`) and **§3.1** exactly. The `make menuconfig`
step is interactive, so the maintainer runs it in their own terminal (`ssh -t ernst@192.168.1.240`).

Expected end state:
- `ip -details link show can0` shows the interface;
- `canbus_query.py can0` returns the **Leviathan UUID** (record it in the status log);
- the Leviathan's `/dev/serial/by-id` entry is gone.

### 5. ERB Katapult → CAN (USER)

With the cable connected and **printer 24 V on**, the ERB is now powered over the cable. Run
`mmu_can_bus.md` **§3.3** exactly: menuconfig values, BOOT/RST ROM-boot entry, `make flash
FLASH_DEVICE=2e8a:0003`, save `erb-katapult-can.config`, unplug USB-C, double-click RST, then
`flashtool.py -i can0 -q`.

Expected: `Detected UUID: …, Application: Katapult`. That's the **ERB UUID**; record it.

This proves the cable, termination and bridge before Klipper is involved. If the buttons are
unreachable, use the §3.3 deployer route, **while the ERB is still on USB-C**.

### 6. ERB Klipper → CAN (USER)

`mmu_can_bus.md` **§3.4** exactly. Expected:
`flashtool.py -i can0 -q` now reports **`Application: Klipper`** for the ERB UUID, and the
Leviathan's UUID is also listed.

### 7. `mcu.cfg` and first start (model edits; USER starts)

Edit `mcu.cfg` on the mount: comment out the `serial:` lines and add the UUIDs, exactly as in
`mmu_can_bus.md` §3.5:

```ini
[mcu]
#serial: /dev/serial/by-id/usb-Klipper_stm32h743xx_4F0038000B51323237363839-if00
canbus_uuid: <LEVIATHAN_UUID>

[mcu mmu]
#serial: /dev/serial/by-id/usb-Klipper_rp2040_E6612C771F48752B-if00
canbus_uuid: <ERB_UUID>
```

Add a one-line dated comment above each (`# 2026-MM-DD: on CAN via the Leviathan bridge — docs/mmu_can_bus.md`).
Then the USER runs:

```
ssh ernst@192.168.1.240 'sudo service klipper start'
```

Model checks:

```
ssh ernst@192.168.1.240 'sleep 20; tail -n 40 ~/printer_data/logs/klippy.log | grep -iE "error|mcu|ready|shutdown"; ip -details -statistics link show can0'
```

Expected:
- Klipper reaches **ready**;
- `can0` shows `ERROR-ACTIVE` with the error counters at 0.

The MMU is still in maintenance, so run `MMU ENABLE=0` after starting if single-spool printing
continues (`is_enabled` isn't persisted).

### 8. Cold power-cycle test — the reason for this work (USER)

1. Retire the dedicated 24 V brick: unplug it from the ERB. From now on the ERB is powered only
   by the cable.
2. Switch the **whole printer off at the mains**, wait 30 s, and switch it on. Don't run
   `FIRMWARE_RESTART`.
3. The model checks that Klipper reached **ready** on its own, with no
   `Can not update MCU 'mmu' config as it is shutdown`:
   ```
   ssh ernst@192.168.1.240 'grep -nE "Start printer|ready|shutdown|Can not update MCU" ~/printer_data/logs/klippy.log | tail -8'
   ```
4. Bus health after warm-up:
   - `ip -details -statistics link show can0` stays `ERROR-ACTIVE` and the counters don't climb;
   - in `klippy.log`'s `Stats` lines, `mmu:` `bytes_retransmit` stays near 0 over 10+ minutes
     idle.

### 9. After the Nightwatch is reinstalled: MMU over CAN (USER)

This happens when the maintainer finishes the NightOwl maintenance. The Nightwatch is
reconnected **with the NightOwl unpowered**, i.e. the printer off.

1. Power on (no `FIRMWARE_RESTART` needed). HH comes back enabled.
2. `MMU_SENSORS DETAIL=1`, then trigger each switch by hand. Every one must toggle and be the
   right one.
3. `MMU_STATUS` should show UNLOADED. Check physically that both gates are clear of the shared
   bowden before any load (maintainer rule).
4. Load and swap over CAN: `T0`, then `SWAP TOOL=1`, then `SWAP TOOL=0`. Watch:
   ```
   ssh ernst@192.168.1.240 'tail -Fn0 ~/printer_data/logs/klippy.log | grep -iE "timeout|retransmit|shutdown|error"'
   ```
   Homing the ERB's gear stepper to the Filamatrix switch on the **Nitehawk (still USB)** crosses
   MCUs. Look specifically for **`Communication timeout during homing`**. If it appears, stop and
   report it; don't tweak HH settings to hide it.

### 10. Recovery and rollback reference

If something goes wrong, use `mmu_can_bus.md` **§5**: the recovery table, and **Rolling back to
USB**. The ERB's RP2040 ROM boot can't be overwritten, so it is always recoverable over USB-C.

### 11. Documentation (model)

- **`docs/mmu_can_bus.md`:** change the status line to "done <date>". Fill in both UUIDs in §4
  (routine updates).
- **`CLAUDE.md`:** in the MMU bullet (`[mcu mmu]` line), say it's on CAN via the Leviathan bridge.
  Add one line under the validation/firmware notes: **after any Klipper update, reflash the ERB
  first and the Leviathan last** (`docs/mmu_can_bus.md` §4); updating the host alone leaves the
  MCUs mismatched.
- **`docs/decisions.md`:** add an entry at the top:
  `## 2026-MM-DD — MMU on CAN: done; brick retired; order moved ahead of HH v4`. Record:
  - the J33 fuse finding (10 A F3 → 18 AWG power conductors);
  - the 2026-10-11 order change;
  - the measured bus health;
  - anything §2/§3 got wrong in practice.
- **`TODO.md`**, *NightOwl exterior wiring*:
  - tick "wire microfit wire internally to the printer";
  - tick the Micro-Fit keystone adapter;
  - **delete** the hex-insert adapter and barrel-jack lines (dropped, maintainer 2026-10-15);
  - mark the dedicated-brick line as retired;
  - update Next up and roadmap #8 (NightOwl position).
- **The v4 runbooks** (`docs/runbooks/hh-v4-1-prep.md`, `hh-v4-2-install-core.md`): replace "before
  the CAN wiring" with "after the CAN conversion (done <date>)". In part 2's Step 3, note that
  `[mcu mmu]` now uses `canbus_uuid:`. If v4's menuconfig asks for the MMU's connection, the answer
  is the ERB UUID, but `mcu.cfg` keeps ownership as already planned.

## Verification

- [ ] §2 meter checks passed before power was applied (Step 3).
- [ ] `can0` is up; both UUIDs recorded; the ERB reports `Application: Klipper` (Steps 4–6).
- [ ] Klipper is ready with `[mcu]` and `[mcu mmu]` on `canbus_uuid:`; `can0` is `ERROR-ACTIVE`
      with counters flat (Steps 7–8).
- [ ] **A mains power-cycle comes up ready with no `FIRMWARE_RESTART`**, with the brick
      disconnected (Step 8). This is the objective.
- [ ] After the Nightwatch is reinstalled: all switches correct, and two swaps each way with no
      homing timeout or retransmit growth (Step 9).
- [ ] Docs, CLAUDE.md, decisions.md, TODO.md and the v4 runbooks are updated (Step 11).

## Commit guidance

Git runs **only over SSH**. The maintainer runs commits. Propose:
1. `feat: move the leviathan and mmu mcus to can` — `mcu.cfg`.
2. `docs: record the mmu can conversion` — `docs/mmu_can_bus.md`, `CLAUDE.md`,
   `docs/decisions.md`, `TODO.md`, the v4 runbooks, and this runbook (moved to
   `docs/runbooks/done/`).

The kconfigs live in `~/klipper-kconfigs/` on the Pi, outside the repo. Nothing to commit there.

## Status log

- **2026-10-15** — Runbook written (architecture session). J33 fuse checked against the Leviathan
  V1.3 KiCad (fused, 10 A F3). Board confirmed as ERB V2.0. Nothing wired or flashed.
- **2026-10-16** — Step 1 preflight (read-only) done. Klipper `v0.13.0-662-gbd99b19b0`; `status -s`
  lists only untracked user extras (`auto_speed`, `autotune_tmc`, `beacon`, `gcode_shell_command`,
  `mmu/`, `mmu_*`…), no modified tracked files. `~/klipper/.config` is the ERB USB build (RP2040,
  `0x10004000`, USB). `~/katapult-env` present. `~/klipper-kconfigs/` holds `leviathan.config`,
  `nitehawk-v1.config`, `nitehawk-v2.config` (no `erb-usb.config` yet — §3.0 saves it).
  `mcu.cfg` still on `serial:` (lines 66 / 200). Cable not yet built.
- **2026-10-16** — Steps 2–3 done (maintainer-reported). Cable built with H/L crossed (keystone
  fitting not confirmed). §2 meter checks (60 Ω, U12/U11 pin 7↔7 and 6↔6 ≈ 0 Ω, power/GND) all passed with power
  off. The 24 V brick was disconnected entirely and physically can't reach the ERB any more, so
  Step 8's "unplug the brick" is already done; the ERB is cable-powered from first power-on.
  Next: Step 4 (Leviathan → bridge).
- **2026-10-16** — Step 4 done. First menuconfig save was CAN-only (no USB); caught before flashing
  and redone as USB-to-CAN bridge. Klipper stopped via Moonraker (`/machine/services/stop`) since
  `sudo` needs a TTY. `erb-usb.config` saved. Leviathan flashed by the maintainer; verified:
  `can0` UP / ERROR-ACTIVE, 1 Mbit/s, counters 0; Leviathan serial entry gone; **Leviathan UUID
  `30fdcd6e3150`** (Application: Klipper). ERB not visible yet (still USB firmware), as expected.
  Next: Step 5 (ERB Katapult → CAN).
- **2026-10-16** — Step 5 done. First ROM-boot attempt crashed the Pi's `xhci-hcd.1` (bus 3 = C920 +
  Leviathan; ERB's USB-C had enumerated on the C920's jack `3-1`) — `HC died`, `can0` lost; Pi reboot
  recovered it, Leviathan bridge intact. Retried with the ERB's USB-C on a K-Hub port (bus 1, other
  controller): `2e8a:0003` appeared, no crash. **Lesson: put the ERB's USB-C on bus 1, never bus 3.**
  Katapult CAN flashed; `erb-katapult-can.config` saved. `flashtool.py -i can0 -q`: **ERB UUID
  `f2d9c8c4f555`** (Application: Katapult); Leviathan `30fdcd6e3150` (Klipper). Cable, termination
  and bridge proven. Next: Step 6 (ERB Klipper → CAN).
- **2026-10-16** — Steps 6–7 done. `erb-can.config` built and flashed over CAN (`-u f2d9c8c4f555`);
  both MCUs report `Application: Klipper`. `mcu.cfg` now `canbus_uuid:` for `[mcu]` (30fdcd6e3150) and
  `[mcu mmu]` (f2d9c8c4f555), dated comments added, `serial:` lines commented, Nitehawk untouched.
  Klipper started via Moonraker → **ready**. Bus: `can0` ERROR-ACTIVE, 0 errors/drops; Stats
  `mmu rx_error=0 tx_error=0 bytes_retransmit=0`; `mcu` rx_error=692 / tx_error=15203379 are frozen
  (not climbing over 16 s) — likely accrued while the Leviathan was alone on the bus. Re-check after
  the cold power-cycle. Next: Step 8 (cold power-cycle).
- **2026-10-16** — Step 8 cold power-cycle: mains off/on, no `FIRMWARE_RESTART`, no brick. Pi up
  21:48:40, Klipper started 21:48:41 → **ready**, no `Can not update MCU 'mmu'` / timeout lines.
  `can0` ERROR-ACTIVE, 0 errors/drops; `mcu` and `mmu` bus_state=active, rx/tx_error=0 (the earlier
  `mcu` tx_error=15203379 reset to 0 — it was a leftover from the Leviathan sitting alone on the bus).
  Idle bytes_retransmit check (10+ min) pending.
- **2026-10-16** — Step 11 docs done: `mmu_can_bus.md` (status, UUIDs in §4, traps section), CLAUDE.md
  (MMU bullet + reflash-order note), `decisions.md` entry, TODO.md (Next up, roadmap #7, wiring section;
  keystone ticked after the maintainer confirmed it's fitted), v4 runbooks. Runbook stays in `docs/runbooks/` (not
  `done/`) until Step 9 passes.
