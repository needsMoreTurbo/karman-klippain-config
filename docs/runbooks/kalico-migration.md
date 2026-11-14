# Runbook — Karman runs Kalico (current hardware), proven by a normal print

**Objective:** Replace mainline Klipper with **Kalico** on Karman. The hardware stays as it is:
Klippain, Happy Hare v3, the NightOwl, Beacon (contact Z), BDPressure and the UHF hotend are all
still installed. All four MCUs run Kalico-built firmware. Klipper reaches `ready`, and the
maintainer reports a clean **single-colour ABS print** plus **one `T0`→`T1` swap**. A tested
rollback path to mainline is kept until then.
**Status:** 🟡 not started · **Created:** 2026-11-13
**Prerequisites:**
- Printer idle, not printing. A few hours of maintainer time at the machine are available.
- `git status` on the Pi is clean, and everything is pushed. Check this over SSH (Step 1).
- `klipper-backup` has a commit from today on `needsMoreTurbo/karman-klippain-backup` (it fails
  silently, see Hazards).
- Moonraker has been restarted since 2026-11-13, so the Happy Hare `v3` pin is live. Step 1 checks
  this.

This is **phase 1 of the INDX migration** (`TODO.md` → *Bondtech INDX migration*). The reasons
are in `docs/decisions.md` 2026-11-13. In short, Kalico goes in first, on known-good hardware, so
that a fault is attributable to one change.

References:
- Kalico migration: <https://docs.kalico.gg/Migrating_from_Klipper.html>
- Kalico config changes: <https://raw.githubusercontent.com/KalicoCrew/kalico/main/docs/Config_Changes.md>
- MCU flashing on this machine: `docs/mmu_can_bus.md` §4 (routine update) and §5 (recovery)
- INDX on Kalico (phase 2+, **not** this runbook): <https://docs.kalico.gg/INDX.html>

## Scope

Snapshot → swap the `~/klipper` tree for Kalico `v2026.11.00` (or newer) → re-link add-ons →
convert two fan options → restart the host and fix errors to `ready` → reflash ERB, Leviathan,
Nitehawk → functional checks → test print + swap → keep the rollback until the maintainer signs
off.

## ⚠️ Out of scope — do not touch

- **No INDX config, and no Klippain removal.** Those are phase 2. Klippain stays exactly as it is.
  This runbook proves only that Kalico runs the *current* config.
- **No Kalico-only features.** No `mpc`, Python macros, `[constants]`, `[danger_options]`,
  `is_non_critical`, `home_current` or `RELOAD_GCODE_MACROS`. The one exception is
  `[danger_options] multi_mcu_trsync_timeout`, and only if Step 9 hits *"Communication timeout
  during homing"*. Each feature is a separate change with its own risk.
- **Happy Hare stays at `5cc88729` on branch `v3`.** Do not update it unless Step 6 fails with a
  `trapq_finalize_moves` `TypeError` (see the Step 6 gate). Never touch `main` or `v4`; `main` is v4
  and has no migration path. HH will print *"Warning: You are running on Kalico… Support is not
  guaranteed!"* at startup. That is expected. Leave `suppress_kalico_warning` unset.
- **`~/bd_pressure` is never pulled or reinstalled.** It carries three local patches, and a pull
  reverts them silently (`docs/pa_physics.md` Appendix A). Only its symlink is re-created.
- **Do not run any add-on `install.sh`**: not Happy Hare's, Klippain's, Beacon's, ShakeTune's,
  `klipper_tmc_autotune`'s or `klipper_auto_speed`'s. HH's installer upgrades and rewrites the
  `mmu/` config. Every add-on is a symlink into `klippy/extras/`, and Step 4 copies those links
  as they are.
- **Do not copy Klippain's `gcode_shell_command.py` link.** Kalico ships its own
  `gcode_shell_command`, and the `[gcode_shell_command git_push/git_pull]` sections in
  `overrides.cfg` work with it unchanged.
- **Input shaper values** (`ei`, X 71.0 / Y 49.2, 2026-09-16) stay. Kalico's 2026-10-21 shaper
  change only affects runs that use `ACCEL_PER_HZ` overrides or `SWEEPING_PERIOD`. Do not re-run
  ShakeTune here.
- **`[output_pin caselight] scale: 1`** looks wrong but is correct (`docs/decisions.md`
  2026-09-16).
- **Pressure advance 0.032, residual 33 / retract_length 60, Blobifier `z_raise 8`, `gear_unload_speed 70`,
  `flowguard_max_relief 8`**: all measured. Nothing in this runbook justifies changing them.
- **The bed-fan state machine logic** (`bed_fans.cfg`). Only the `off_below` line changes (Step 5).
- **`printer.cfg`'s `SAVE_CONFIG` block.** Never hand-edit it.

## ⚠️ Hazards in play

Copied from CLAUDE.md's hazard register:

- **Flashing order after a Klipper update** — reflash the ERB first and the Leviathan last.
  Flashing the bridge drops `can0` and takes the ERB with it (`docs/mmu_can_bus.md` §4).
  **Conditional**: after any Klipper update or reflash. *(This runbook is exactly that case.)*
- **Restarting Klipper mid-print** (`FIRMWARE_RESTART`, a service restart) kills the print. Check
  `print_stats.state` first. **Conditional**: while printing.
- **`~/bd_pressure` carries three local patches** (framed USB reads, warm-up discard, zero-crossing
  solve). Its `update_manager` entry is commented out on purpose, and any `git pull` there silently
  reverts them and the PA sweeps return wrong answers (`docs/pa_physics.md` Appendix A).
  **Always-on**.
- **Happy Hare must stay on its `v3` branch** (`moonraker.conf [update_manager happy-hare]`
  `primary_branch: v3`; local checkout on branch `v3`, pinned 2026-11-13). Upstream `main` carries
  v4, which has no migration path from v3. Never switch the checkout or the Moonraker entry back to
  `main`. **Conditional**: until the NightOwl is removed in the INDX conversion.
- **`klipper-backup` fails silently.** … `save_variables.cfg` (gitignored) is backed up **only**
  there. **Always-on** until failures alert. *(Step 1 also copies it by hand.)*
- **`MMU_TEST_FORM_TIP` / hand-cranking with `MMU_TEST_MOVE`** — strands filament in the ~1.45 m
  bowden and desyncs HH state. **Always-on**. *(Test the swap with `T0`/`T1`; fix desync with
  `MMU_RECOVER`.)*
- **MMU load/swap commands outside a print can run as cold as ~200 °C** … too cold for ABS in this
  UHF melt zone (grinds or jams). Preheat to the gate's material temperature first.
  **Conditional**: bench MMU operations. *(Step 9 preheats before the swap.)*
- **Front-left, x<10 / y<17, at ANY Z** — the Filamatrix cutter arm on the toolhead strikes the
  front-left XY idler. **Always-on**. *(Do not jog there while checking homing.)*
- **Back-left, x<~20 / y>~335, below z15** — blobifier tray, shaker arm and the depressor.
  **Conditional**: only below z15.
- **The y_max feature row** — must be entered in +Y through a clear lane (15<x<40, or x>95), then
  slid in X. **Always-on** near y_max.
- **A forgotten preheat keeps heating** — never leave heaters on assuming the idle timeout will
  catch it. **Always-on**. *(Turn heaters off at the end of every bench step.)*
- **Bed SSR runs without a heatsink** — `max_power: 0.8`, never toward 1.0. **Always-on**.

## Pre-resolved decisions

Each of these is a default the maintainer can veto in one line before starting.

- **Method: fresh clone into `~/klipper`, old tree kept as `~/klipper_old`** (Kalico's Option 1).
  Rollback then means moving a directory back. All the add-on links and `.config` stay intact in
  `klipper_old`, with no branch juggling. *Rejected:* adding a git remote to the existing tree
  (Option 3), because the untracked add-on links make the checkout fragile. KIAUH is not needed.
- **Version: the newest `vYYYY.MM.NN` stable tag that contains `board_configs/bondtech_indx_usb.config`.**
  As of writing that is `v2026.11.00` (both `.10.00` and `.11.00` have it). Moonraker gets
  `[update_manager klipper] channel: stable`, so updates arrive as monthly tags rather than every
  commit.
- **Fans: `off_below: X` → `min_power: 0`**, on both `[fan]` (`overrides.cfg`, was 0.14) and
  `[fan_generic Bed_Fans]` (`bed_fans.cfg`, was 0.09). Kalico maps requests onto
  `min_power..max_power`. Keeping the old values as `min_power` would raise every PWM, so the
  slicer's 30 % would become ~40 %, and the bed-fan ramp would start at 0.18 instead of 0.10.
  `min_power: 0` keeps today's PWM for every request at or above the old cutoff. The bed-fan loop
  never commands between 0 and 0.10, so nothing changes there. A slicer request below 14 % might
  now buzz the part fan without spinning it, which is acceptable. Both fans have `max_power: 1.0`,
  so the macros that read `.speed` (bed_fans, Blobifier, HH form-tip) see the same numbers as
  before.
- **Kconfigs: copy `~/klipper-kconfigs/*.config` into `~/klipper-kconfigs/kalico/` and build from
  the copies.** Kalico's `olddefconfig` adds options and rewrites the file, so the mainline
  originals must stay untouched for rollback.
- **Nitehawk USB path: keep it the same.** In its Kalico menuconfig, **disable "USB product from
  MCU name"** (*USB ids* menu; Kalico 2026-09-14 change). Then `/dev/serial/by-id/usb-Klipper_stm32g0b1xx_450054000550303857383820-if00`
  still matches `mcu.cfg`. The two CAN boards are addressed by UUID, so their product string does
  not matter.
- **Python deps:** run `pip install -r ~/klipper/scripts/klippy-requirements.txt` into
  `~/klippy-env`. It is harmless if nothing changes.
- **Who runs what:** the model proposes every command and reads output over SSH and Moonraker. The
  **maintainer** runs anything that flashes, restarts services, heats or moves. If the maintainer
  explicitly says "go ahead" for a step, the model may run that step's commands over SSH.
  `sudo` needs a TTY, so stop/start Klipper through Moonraker.

---

## Step 1 — Preflight and snapshot *(model checks; maintainer confirms)*

```bash
# printer idle?
curl -s 'http://192.168.1.240:7125/printer/objects/query?print_stats=state'
# config repo clean and pushed
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git status -sb | head -3'
# HH pin live (expect "## v3...origin/v3") and Moonraker sees it
ssh ernst@192.168.1.240 'cd ~/Happy-Hare && git status -sb | head -1'
curl -s http://192.168.1.240:7125/machine/update/status | python3 -c 'import sys,json;r=json.load(sys.stdin)["result"]["version_info"]["happy-hare"];print(r.get("branch"),r.get("is_valid"),r.get("warnings"))'
# record versions for the status log
curl -s 'http://192.168.1.240:7125/printer/objects/query?mcu&mcu%20mmu&mcu%20toolhead&mcu%20beacon' | python3 -c 'import sys,json;[print(k,v.get("mcu_version")) for k,v in json.load(sys.stdin)["result"]["status"].items()]'
# hand snapshot of the irreplaceable runtime files + all kconfigs
ssh ernst@192.168.1.240 'mkdir -p ~/kalico-migration-backup && cp -a ~/printer_data/config/save_variables.cfg ~/printer_data/config/printer.cfg ~/klipper/.config ~/klipper-kconfigs ~/kalico-migration-backup/ && ls -la ~/kalico-migration-backup'
```
Expected: `standby`, a clean tree, `v3 True`, mainline `v0.13.0-662-gbd99b19b0` on mcu, mmu and
toolhead, Beacon `2.1.0`.
**Gate:** if Moonraker still shows HH on `main`, ask the maintainer to restart Moonraker
(`curl -X POST 'http://192.168.1.240:7125/machine/services/restart?service=moonraker'`) and
re-check. If the tree is dirty, stop until the maintainer commits.

## Step 2 — Swap the Klipper tree *(maintainer)*

```bash
curl -X POST 'http://192.168.1.240:7125/machine/services/stop?service=klipper'
ssh ernst@192.168.1.240 '
  mv ~/klipper ~/klipper_old &&
  git clone https://github.com/KalicoCrew/kalico.git ~/klipper &&
  cd ~/klipper && git tag --sort=-v:refname | grep -E "^v20[0-9]{2}\.[0-9]{2}\.[0-9]{2}$" | head -3'
```
Choose the newest tag that has `board_configs/bondtech_indx_usb.config`, then check it out:
```bash
ssh ernst@192.168.1.240 'cd ~/klipper && git checkout v2026.11.00 && ls board_configs/ klippy/extras/indx && git describe --tags'
```
Expected: `bondtech_indx_usb.config` is listed, and the `indx` directory exists.

## Step 3 — Python requirements *(maintainer or model)*

```bash
ssh ernst@192.168.1.240 '~/klippy-env/bin/pip install -r ~/klipper/scripts/klippy-requirements.txt 2>&1 | tail -3'
```

## Step 4 — Re-link add-ons into the new tree *(model, after go-ahead)*

Copy every add-on link from `klipper_old`, preserving the symlinks. Exclude
`gcode_shell_command.py`, which Kalico ships itself.
```bash
ssh ernst@192.168.1.240 '
  cd ~/klipper_old/klippy/extras &&
  for f in mmu mmu_machine.py mmu_leds.py mmu_espooler.py mmu_sensors.py mmu_encoder.py mmu_led_effect.py mmu_servo.py \
           beacon.py bdpressure.py autotune_tmc.py motor_constants.py motor_database.cfg \
           auto_speed.py autospeed shaketune; do
    cp -a "$f" ~/klipper/klippy/extras/ || echo "MISSING $f"; done
  cd ~/klipper/klippy/extras && ls -la | grep -E "^l|^d" | grep -vE " \.\.?$|__pycache__|display|indx"
  find ~/klipper/klippy/extras -xtype l   # dangling links: expect no output'
```
Then check that nothing in the old tree was missed: every untracked or ignored file must be in
the list above or be `gcode_shell_command.py`.
```bash
ssh ernst@192.168.1.240 'cd ~/klipper_old && git status --porcelain --ignored klippy/extras | grep -v __pycache__'
```
**Gate:** if an entry appears that is neither in the list nor `gcode_shell_command.py`, stop and
ask. It is an add-on this runbook doesn't know about.

## Step 5 — Config edits for Kalico *(model edits on the mount; maintainer reviews)*

1. `overrides.cfg` `[fan]`: replace `off_below: 0.14` with
   `min_power: 0   # Kalico: was off_below 0.14 (mainline). 0 keeps today's PWM; see docs/decisions.md`.
2. `bed_fans.cfg` `[fan_generic Bed_Fans]`: replace `off_below: 0.09` the same way. Add one line
   to `docs/bed_fans_control.md` noting the change.
3. `moonraker.conf`: add a section (Moonraker has no `[update_manager klipper]` entry today):
   ```
   # Kalico (docs/runbooks/kalico-migration.md): track monthly stable tags, not every commit.
   [update_manager klipper]
   channel: stable
   ```
4. Re-run the offline check from the mount. It returned 0 problems at planning time:
   `uv run ~/.claude/skills/klipper/scripts/klipper_macro.py check printer.cfg --flavor kalico`
   and `uv run tools/render_macro.py --selftest`.

No other config option is known to need changing. At planning time the live config had no
`max_accel_to_decel`, `max_stepper_error`, `SET_PIN CYCLE_TIME` or short `CHIPS=`, and every TMC
section already had `sense_resistor`. Klippain's `end_print.cfg` `ACCEL_TO_DECEL` use is guarded
by `is defined`, so it is inert.

## Step 6 — First host start, error loop to `ready` *(maintainer starts; model reads)*

The MCUs are still on mainline firmware here. Expect a version-mismatch warning or a protocol
error naming an MCU. That is fine at this step; it is fixed in Step 7.
```bash
curl -X POST 'http://192.168.1.240:7125/machine/services/start?service=klipper'
curl -X POST 'http://192.168.1.240:7125/machine/services/restart?service=moonraker'
curl -s http://192.168.1.240:7125/printer/info | python3 -c 'import sys,json;r=json.load(sys.stdin)["result"];print(r["state"]);print(r["state_message"]);print(r["software_version"])'
ssh ernst@192.168.1.240 'grep -nE "Error|error|Option .* is not valid|Unable|mcu .*version" ~/printer_data/logs/klippy.log | tail -20'
```
Fix one config error per restart, recording each in the status log. Only MCU protocol or version
errors may remain before Step 7.
**Gate (stop, consider rollback):**
- A **Python traceback from an add-on module** (`beacon.py`, `mmu*`, `bdpressure.py`,
  `shaketune`, `autotune_tmc`, `auto_speed`), as opposed to a config-option error.
- *Exception:* a `TypeError` mentioning `trapq_finalize_moves` in HH has a known fix. It is upstream
  `883a0119` on `v3`. Ask the maintainer before running
  `ssh ernst@192.168.1.240 'cd ~/Happy-Hare && git pull --ff-only'` (on branch `v3`, this pulls 10
  v3 fixes), then restart the host.
- Any other add-on traceback: record it, then run the Rollback section, or escalate.

## Step 7 — Reflash MCUs from the Kalico tree *(maintainer)*

The order is **ERB first, Leviathan last, then the Nitehawk**. This is `docs/mmu_can_bus.md` §4
with the Kalico copies of the kconfigs. Klipper must be stopped.
```bash
curl -X POST 'http://192.168.1.240:7125/machine/services/stop?service=klipper'
ssh ernst@192.168.1.240 'mkdir -p ~/klipper-kconfigs/kalico && cp -n ~/klipper-kconfigs/*.config ~/klipper-kconfigs/kalico/'
# review new options for each board (interactive — run in a real terminal on the Pi):
#   cd ~/klipper && make menuconfig KCONFIG_CONFIG=$HOME/klipper-kconfigs/kalico/erb-can.config
#   cd ~/klipper && make menuconfig KCONFIG_CONFIG=$HOME/klipper-kconfigs/kalico/leviathan-canbridge.config
#   cd ~/klipper && make menuconfig KCONFIG_CONFIG=$HOME/klipper-kconfigs/kalico/nitehawk-v2.config
#     → USB ids → DISABLE "USB product from MCU name"  (keeps the by-id path)
#   Do not change anything else: MCU, bootloader offset, CAN 1000000, USB-to-CAN bridge, all as saved.
cd ~/klipper
make clean && make KCONFIG_CONFIG=$HOME/klipper-kconfigs/kalico/erb-can.config
~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -i can0 -u f2d9c8c4f555 -f ~/klipper/out/klipper.bin
make clean && make KCONFIG_CONFIG=$HOME/klipper-kconfigs/kalico/leviathan-canbridge.config
~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -i can0 -u 30fdcd6e3150 -f ~/klipper/out/klipper.bin
ip -br link show can0                      # must be UP before continuing
~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -i can0 -q   # expect both UUIDs, Application: Klipper
make clean && make KCONFIG_CONFIG=$HOME/klipper-kconfigs/kalico/nitehawk-v2.config
~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -d /dev/serial/by-id/usb-Klipper_stm32g0b1xx_450054000550303857383820-if00 -f ~/klipper/out/klipper.bin
ls /dev/serial/by-id/                      # toolhead path unchanged?
```
If the Nitehawk's by-id path changed anyway, update `[mcu toolhead] serial:` in `mcu.cfg` to the
new path and note it in the status log.
Recovery for any failed CAN flash: `docs/mmu_can_bus.md` §5. That covers the Leviathan stuck in
Katapult (`usb-katapult_stm32h743xx_…`) and the ERB double-click RST.
Beacon is **not** reflashed here. Its firmware is managed by `beacon_klipper` and stays `2.1.0`.

## Step 8 — Start, `ready`, read the state *(maintainer starts; model reads)*

```bash
curl -X POST 'http://192.168.1.240:7125/machine/services/start?service=klipper'
curl -s http://192.168.1.240:7125/printer/info | python3 -c 'import sys,json;r=json.load(sys.stdin)["result"];print(r["state"], r["software_version"]);print(r["state_message"])'
curl -s 'http://192.168.1.240:7125/printer/objects/query?mcu&mcu%20mmu&mcu%20toolhead&mcu%20beacon' | python3 -c 'import sys,json;[print(k,v.get("mcu_version")) for k,v in json.load(sys.stdin)["result"]["status"].items()]'
ssh ernst@192.168.1.240 'ip -s -d link show can0 | grep -E "state|errors|bus-off"'
```
Expected: `ready`. mcu, mmu and toolhead all report a Kalico version string matching
`software_version`. `can0` is ERROR-ACTIVE with no errors. A power-cycle check is not needed here.

## Step 9 — Functional checks *(maintainer runs at the machine; model watches logs)*

Start a log watch first:
`ssh ernst@192.168.1.240 'tail -Fn0 ~/printer_data/logs/klippy.log ~/printer_data/logs/mmu.log'`.
Run these one at a time and report each result:
1. `QUERY_ENDSTOPS` → all open.
2. `G28`, the normal Klippain homing with Beacon contact Z. Kalico 2026-10-02 no longer backs off
   `homing_retract_dist` after a physical-endstop touch, so the toolhead may sit a few mm closer
   to X/Y max than before. That is expected; report anything else.
3. `QUAD_GANTRY_LEVEL`, which must converge as before.
4. `BED_MESH_CALIBRATE`. Watch it stay out of the front-left keep-out, as before (`mesh_overscan: 5`).
5. `M106 S77` then `M106 S0`, and `BED_FANS_STATUS` (or the console line from `bed_fans.cfg`)
   while the bed fans run. Fans spin at about the same speeds as before.
6. `MMU_STATUS` shows gates, and `MMU_SENSORS` shows the expected states.
7. Swap: preheat to the gate's material temperature (ABS 260), then `T1` from T0, then `T0`. The
   cut, Blobifier purge and wipe should complete as before. Turn the heaters off afterwards.
   **If** *"Communication timeout during homing"* appears, stop and consider
   `[danger_options] multi_mcu_trsync_timeout`. Record the value and the reason in decisions.md
   before setting it.
8. `MMU_STATUS` and `mmu.log` show no desync. If one appears, fix it with `MMU_RECOVER` only.

**Gate:** any failure in items 1–4 means stop. It is motion or probing behaviour, so roll back
rather than tune.

## Step 10 — Acceptance print *(maintainer)*

Slice and run a normal **single-colour ABS** part (≈30–60 min) from the usual Orca preset. Watch
the first layer: the too-close first layers are a known pre-existing issue (Beacon dent), not a
regression, unless they are clearly worse than usual. The maintainer reports START_PRINT, first
layer, print, END_PRINT (cool-then-wipe), and anything odd in the console.

## Step 11 — Close out *(model drafts; maintainer commits)*

- Update `CLAUDE.md`. Say the firmware is **Kalico `<tag>`** in *Printer*, and amend the hazard
  *"Flashing order after a Klipper update"* to say kconfigs are now in `~/klipper-kconfigs/kalico/`.
- `docs/decisions.md` entry (see Commit guidance).
- `docs/mmu_can_bus.md` §4: build from `~/klipper-kconfigs/kalico/`.
- Keep `~/klipper_old` and the mainline kconfigs **until the maintainer has run about 5 more
  prints**. Then deleting them is a maintainer decision, not part of this runbook.

---

## Rollback (any gate) *(maintainer)*

```bash
curl -X POST 'http://192.168.1.240:7125/machine/services/stop?service=klipper'
ssh ernst@192.168.1.240 'mv ~/klipper ~/klipper_kalico && mv ~/klipper_old ~/klipper'
# if MCUs were already flashed with Kalico: reflash mainline, same order, ORIGINAL kconfigs
cd ~/klipper
make clean && make KCONFIG_CONFIG=$HOME/klipper-kconfigs/erb-can.config && ~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -i can0 -u f2d9c8c4f555 -f out/klipper.bin
make clean && make KCONFIG_CONFIG=$HOME/klipper-kconfigs/leviathan-canbridge.config && ~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -i can0 -u 30fdcd6e3150 -f out/klipper.bin
make clean && make KCONFIG_CONFIG=$HOME/klipper-kconfigs/nitehawk-v2.config && ~/katapult-env/bin/python3 ~/katapult/scripts/flashtool.py -d /dev/serial/by-id/<toolhead path from ls> -f out/klipper.bin
```
Then revert the Step 5 config edits (`git checkout -- overrides.cfg bed_fans.cfg moonraker.conf`
**over SSH**), start Klipper, and restart Moonraker. `~/klippy-env` packages from Step 3 are
backwards-compatible. Record in the status log which gate triggered.

## Verification

- [ ] `printer/info` shows `ready` with a Kalico `software_version`. mcu, mmu and toolhead report
      matching Kalico firmware.
- [ ] Homing, QGL and mesh behave as before (Step 9.1–9.4, maintainer-reported).
- [ ] One `T0`→`T1`→`T0` swap completes: cut, purge, wipe, no FlowGuard trip, no desync.
- [ ] A single-colour ABS print completes normally (maintainer-reported).
- [ ] Nothing else regressed: bed fans and part fan run at the speeds they did before, Beacon is
      present, the BDPressure module loads, Moonraker shows `klipper` on `channel: stable` and
      `happy-hare` on `v3`, and `can0` has no errors.
- [ ] Rollback is still possible: `~/klipper_old` and the mainline kconfigs are intact.

## Commit guidance

- `chore: migrate karman from mainline klipper to kalico` — `overrides.cfg`, `bed_fans.cfg`,
  `moonraker.conf`, `CLAUDE.md`, `docs/mmu_can_bus.md`, `docs/bed_fans_control.md`, this runbook,
  `TODO.md`.
- `docs/decisions.md` entry *"Karman on Kalico `<tag>`"*. It must record:
  - why `min_power: 0` rather than the old `off_below` values (the rescale);
  - that add-ons were re-linked by copying symlinks, not by running installers, and why;
  - the Kalico-copied kconfigs;
  - any `danger_options` or HH update that a gate forced;
  - every config error hit in Step 6.

## Status log

- **2026-11-13** — runbook created; not yet started. Planning-time facts:
  - mainline `v0.13.0-662-gbd99b19b0` (165 behind `master`); Beacon fw `2.1.0`.
  - HH `5cc88729` pinned on `v3` (10 behind `origin/v3`).
  - `klipper_macro.py check --flavor kalico` gave 0 problems in 257 templates.
  - Kalico `v2026.11.00` contains INDX support.
