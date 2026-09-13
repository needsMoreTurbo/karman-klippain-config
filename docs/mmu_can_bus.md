# MMU on CAN — Leviathan bridge + ERB V2

**Status (2026-09-13): planned — not yet wired or flashed.** Leviathan-side cable connector made;
wiring later that week. Update this line when the conversion is done.
**Why CAN, and what was rejected:** `docs/decisions.md` 2026-09-13.

The ERB V2 (MMU MCU, RP2040) talks to Klipper over CAN on one 4-wire Micro-Fit cable that also
carries its 24 V, from the Leviathan V1.3's `CAN_BUS` port. The Leviathan runs Klipper in
**USB-to-CAN bridge** mode, so it is both the main MCU and the Pi's CAN adapter:

```
Pi ──USB── Leviathan V1.3 (STM32H743, bridge) ──J33── 4-wire Micro-Fit ──X1── ERB V2 (RP2040)
```

## 1. Hardware facts

| | Leviathan V1.3 | ERB V2 |
|---|---|---|
| Connector | J33 `CAN_BUS`, Micro-Fit 3.0 2×2 | X1, green 4-pin pluggable terminal |
| +24 V | pin 1 | pin 1 |
| GND | pin 2 | pin 2 |
| **CAN_H** | **pin 3** | **pin 4** |
| **CAN_L** | **pin 4** | **pin 3** |
| Transceiver (SOIC-8: pin 7 = CANH, pin 6 = CANL) | U12 TJA1057GT | U11 MCP2542 / SIT1051T/3 |
| 120 Ω termination | JP1 `term` — **fit** | JP1 — **fit** |
| Other jumpers | — | JP3 + JP4 → **CAN** · JP2 (USB 5 V) → **off** whenever 24 V is connected |
| Bootloader | Katapult (USB build — correct for a bridge), app at 128 KiB | Katapult, app at 16 KiB — **currently a USB build; rebuild for CAN (§3.3)** |
| Klipper CAN settings | USB on PA11/PA12, CAN bus on PB5/PB6 | CAN RX gpio0, CAN TX gpio1 |

Bus speed everywhere: **1000000**.

⚠️ Pin numbers come from the schematics (FYSETC ERB V2.0 SCH, LDO Leviathan V1.3 KiCad), not the
boards — **confirm with a meter (§2)**:
- **CAN_H/CAN_L pin order is reversed between the two boards.** A pin-for-pin cable swaps them
  (no damage — the bus just won't come up).
- FYSETC's pinout graphic labels JP3/JP4 "1–2 = USB, 2–3 = CAN", but the schematic numbers
  pin 1 = CAN, pin 3 = USB. Trust the meter, not the numbers.
- The ERB has **no fuse or TVS** on X1, and whether J33's 24 V is fused is unverified.

**The Pi host side is already configured** (found 2026-09-13): `/etc/systemd/network/25-can.network`
(`BitRate=1M`), `/etc/udev/rules.d/10-can.rules` (`tx_queue_len` 128), and
`systemd-networkd-wait-online` disabled. `can0` appears once the Leviathan runs bridge firmware. (In
bridge mode the firmware sets the bitrate; Linux's setting is ignored.)

## 2. Wiring checks (power off, cable connected at both ends)

1. **Termination:** CAN_H–CAN_L ≈ **60 Ω**. 120 Ω means a JP1 is missing or a wire is open.
2. **Cable, H/L order and ERB jumper position in one check:** Leviathan U12 pin 7 ↔ ERB U11 pin 7
   reads **≈ 0 Ω** (and pin 6 ↔ pin 6). 60 Ω instead means H/L are swapped; open means JP3/JP4 are in
   the USB position or a wire is open.
3. **Power:** ERB X1 pin 2 ↔ an ERB GND pin (e.g. an endstop header) ≈ 0 Ω. No continuity between
   +24 V and GND, or between +24 V and either CAN line.

## 3. One-time conversion

Klipper stays stopped throughout (`sudo service klipper stop`); the printer is unusable until §3.5.
Use `~/katapult-env/bin/python3` for every `flashtool.py` call — flashing the bridge needs pyserial.
Keep a USB-C cable (Pi → ERB) handy for §3.3.

### 3.0 Save the current ERB USB build (rollback)
As of 2026-09-13, `~/klipper/.config` is the ERB's USB build (RP2040, 16 KiB bootloader, USB) — check
before copying:
```bash
cp ~/klipper/.config ~/klipper-kconfigs/erb-usb.config
```

### 3.1 Leviathan → USB-to-CAN bridge
```bash
cd ~/klipper
cp ~/klipper-kconfigs/leviathan.config ~/klipper-kconfigs/leviathan-canbridge.config
make KCONFIG_CONFIG=$HOME/klipper-kconfigs/leviathan-canbridge.config menuconfig
```
Change only **Communication interface → USB to CAN bus bridge (USB on PA11/PA12)**, **CAN bus
interface → CAN bus (on PB5/PB6)**, **CAN bus speed → 1000000**. Keep STM32H743, 128KiB bootloader and
the 25 MHz clock.
```bash
make clean
make KCONFIG_CONFIG=$HOME/klipper-kconfigs/leviathan-canbridge.config
~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py \
  -d /dev/serial/by-id/usb-Klipper_stm32h743xx_4F0038000B51323237363839-if00 \
  -f ~/klipper/out/klipper.bin
ip -details link show can0                                      # must exist now
~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0   # note the Leviathan's UUID
```
The Leviathan's `/dev/serial/by-id` entry disappears after this — expected.

### 3.2 Wire the ERB, run §2, power on

### 3.3 ERB Katapult → CAN
```bash
cd ~/katapult
make menuconfig
```
Matches FYSETC's `V2.0/images/ERBv2_katakulpt_menuconfig_CAN.png`. Compared with the current USB
build, only the interface and pins change:
- Raspberry Pi RP2040 · Flash chip W25Q080 with CLKDIV 2 · Build Katapult deployment application: Do not build
- **Communication interface: CAN bus** · **CAN RX gpio 0** · **CAN TX gpio 1** · CAN bus speed 1000000
- `[*]` bootloader entry on rapid double click of reset · `[ ]` entry on button · `[*]` Status LED, gpio20

```bash
make clean && make
```
Connect USB-C Pi → ERB (24 V on, JP2 off). Enter ROM boot: hold **BOOT**, press **RST** ~0.5 s,
release RST, wait ~3 s, release BOOT. `lsusb` must show `2e8a:0003 Raspberry Pi RP2 Boot`.
```bash
make flash FLASH_DEVICE=2e8a:0003
cp .config ~/klipper-kconfigs/erb-katapult-can.config
```
Unplug USB-C, **double-click RST** so the ERB stays in Katapult, then:
```bash
~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -i can0 -q
# expect: Detected UUID: xxxxxxxxxxxx, Application: Katapult   ← the ERB's UUID
```
This proves cable, termination and bridge before Klipper is involved. Katapult and Klipper report
the same UUID.

*Buttons unreachable inside the NightOwl?* Katapult's deployer (supported on RP2040) swaps the
bootloader through the **current USB** Katapult instead — do it while the ERB is still on USB-C: set
**Build Katapult deployment application → 16KiB bootloader**, `make`, then
`flashtool.py -d /dev/serial/by-id/usb-Klipper_rp2040_E6612C771F48752B-if00 -f ~/katapult/out/deployer.bin`.
Katapult warns to be certain the config is right first; ROM boot (above) is the recovery.

### 3.4 ERB Klipper → CAN
```bash
cd ~/klipper
cp ~/klipper-kconfigs/erb-usb.config ~/klipper-kconfigs/erb-can.config
make KCONFIG_CONFIG=$HOME/klipper-kconfigs/erb-can.config menuconfig
```
Matches FYSETC's `ERBv2_menuconfig_16kb_CAN.png`: RP2040 · Bootloader offset 16KiB ·
**Communication Interface: CAN bus** · **CAN RX gpio 0** · **CAN TX gpio 1** · 1000000.
```bash
make clean
make KCONFIG_CONFIG=$HOME/klipper-kconfigs/erb-can.config
~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -i can0 -u <ERB_UUID> -f ~/klipper/out/klipper.bin
~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -i can0 -q     # now "Application: Klipper"
```

### 3.5 Klipper config and first start
`mcu.cfg` holds the only live `[mcu mmu]`. `mmu/base/mmu.cfg` has one too, but
`[include mmu/base/mmu_*.cfg]` doesn't match that filename, so it isn't loaded.
```ini
[mcu]
#serial: /dev/serial/by-id/usb-Klipper_stm32h743xx_4F0038000B51323237363839-if00
canbus_uuid: <LEVIATHAN_UUID>

[mcu mmu]
#serial: /dev/serial/by-id/usb-Klipper_rp2040_E6612C771F48752B-if00
canbus_uuid: <ERB_UUID>
```
`sudo service klipper start`, then verify:
- `ip -details -statistics link show can0` → `ERROR-ACTIVE`, error counters not climbing.
- `klippy.log` stats: `mmu:` `bytes_retransmit` stays near 0.
- A real `T0`↔`T1` swap. It homes the ERB's gear stepper to the Filamatrix switch on the Nitehawk
  (still USB) — watch for `Communication timeout during homing`.

Then update the status line above and the MMU line in `CLAUDE.md`, and commit via SSH.

## 4. Routine firmware update (after a Klipper update)

**ERB first, Leviathan last** — flashing the bridge drops `can0`, and the ERB with it. No separate
`-r` step: flashtool asks the running Klipper to jump to Katapult, and for the bridge it follows the
board to its USB bootloader automatically.
```bash
sudo service klipper stop
cd ~/klipper

make clean && make KCONFIG_CONFIG=$HOME/klipper-kconfigs/erb-can.config
~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -i can0 -u <ERB_UUID> -f ~/klipper/out/klipper.bin

make clean && make KCONFIG_CONFIG=$HOME/klipper-kconfigs/leviathan-canbridge.config
~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -i can0 -u <LEVIATHAN_UUID> -f ~/klipper/out/klipper.bin

# Nitehawk is unchanged (USB, nitehawk-v2.config, flashtool -d /dev/serial/by-id/usb-Klipper_stm32g0b1xx_…)
sudo service klipper start
```
- The Makefile runs `olddefconfig` when `src/Kconfig` is newer than a saved config, so new options
  take defaults. Add `menuconfig` with the same `KCONFIG_CONFIG=` to review them.
- If the Leviathan flash times out waiting for its bootloader:
  `flashtool.py -i can0 -u <LEVIATHAN_UUID> -r`, find `usb-katapult_stm32h743xx_…` in
  `/dev/serial/by-id/`, then `flashtool.py -d <that path> -f ~/klipper/out/klipper.bin`.

## 5. Recovery

| Symptom | Fix |
|---|---|
| `mmu` won't connect; ERB missing from `flashtool.py -i can0 -q` | Double-click ERB **RST** → `-q` shows `Application: Katapult` → reflash §3.4 |
| ERB's Katapult broken or built with wrong CAN settings | USB-C + BOOT/RST → `2e8a:0003` → redo §3.3. The RP2040 ROM boot mode can't be overwritten |
| No `can0` | Leviathan isn't running bridge firmware (e.g. left in Katapult by a failed flash): look for `usb-katapult_stm32h743xx_…` and flash the bridge build with `flashtool.py -d …`. Last resort: Leviathan DFU (hold BOOT0, press + release RESET, count 5, release BOOT0) |
| `can0` up but errors / `BUS-OFF` | Redo §2 (60 Ω, H/L order); confirm all builds use 1000000; `sudo ip link set can0 down && sudo ip link set can0 up` |

**Rolling back to USB:** flash the Leviathan with `leviathan.config` (via
`flashtool.py -i can0 -u <LEVIATHAN_UUID> -f …`); on the ERB, rebuild Katapult for USB and flash it
through ROM boot, then flash `erb-usb.config` over USB-C. Leave JP3/JP4 on CAN while the 4-pin cable
stays connected for power, and restore the `serial:` lines.

## Sources
- FYSETC ERB V2.0 — README, pinout, schematic, menuconfig screenshots: <https://github.com/FYSETC/FYSETC-ERB/tree/main/V2.0>
- LDO Leviathan V1.3 KiCad (J33, U12, JP1): <https://github.com/MotorDynamicsLab/Leviathan> · bridge menuconfig: <https://ldomotion.com/guides/voron-leviathan-v1-3>
- Katapult README and `scripts/flashtool.py` (CAN jump, bridge follow-through): <https://github.com/Arksine/katapult>
- Klipper CAN docs: <https://www.klipper3d.org/CANBUS.html> · Esoterical updating guides: <https://canbus.esoterical.online/toolhead_klipper_updating.html>, <https://canbus.esoterical.online/mainboard_klipper_updating.html>
