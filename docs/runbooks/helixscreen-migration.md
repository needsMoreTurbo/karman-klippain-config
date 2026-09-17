# HelixScreen UI migration

**Objective:** Finish migrating Karman's touchscreen UI to HelixScreen — dial in its settings,
get the app's config properly committed to this repo, verify the fixes made so far survive a
real reboot, and decide what happens to KlipperScreen.
**Status:** In progress. Two bugs found and fixed; repo commits and settings tuning still open.
**Date opened:** 2026-08-22
**Prerequisites:** Pi reachable at `ernst@192.168.1.240`; HelixScreen already installed and
running as the `helixscreen` systemd service (installed 2026-08-20, `~/helixscreen/`); Karman is
a Raspberry Pi 5 driving an 800×480 DSI panel via `/dev/dri/card1` (DRM backend).

## Scope

HelixScreen application configuration and its footprint in this repo. Rotation/caselight bugs
already root-caused in Klipper's own `output_pin` handling are **in scope** to commit; anything
about MMU hardware, toolhead motion, or KlipperScreen's Happy-Hare menu wiring is **not**.

## ⚠️ Out of scope / do not touch

The repo currently has several **unrelated** uncommitted changes sitting alongside the
HelixScreen work (confirmed via `git status -s` **over SSH**, per `CLAUDE.md` — the mount shows
spurious types on these paths). A cold session must not sweep these into a HelixScreen commit,
and must not revert them either — they belong to other in-progress work:

- `mmu_hardware.cfg`, `mmu_parameters.cfg` — FlowGuard / sync-feedback tuning from a different
  session (see the `fix(mmu):` commits at the top of `git log`). Unrelated to HelixScreen.
- `NOTES.md` — the maintainer's personal hardware-measurement scratchpad (residual_filament
  numbers for LDO vs. Polymaker ABS). Unrelated.
- `mmu_klipperscreen.conf` (untracked, new) and the `[include mmu_klipperscreen.conf]` line added
  to `KlipperScreen.conf` — this is Happy Hare's **KlipperScreen** MMU menu wiring, a parallel
  task, not part of migrating *to* HelixScreen. Leave both alone.
- `mmu/hh_extract.py`, `mmu/hh_extract.json`, `mmu/hh_extract_report.txt` (untracked) — unrelated
  tooling.
- The caselight fix already in `overrides.cfg` (`[output_pin caselight]` `scale: 1` +
  `[gcode_macro LIGHT_ON]`/`LIGHT_OFF` overrides) is **correct and validated** — see "Progress so
  far" below. Do not "simplify" it back toward Klippain's stock `scale: 100`; that is precisely
  the bug it fixes. If you're re-deriving why it looks different from Klippain's upstream
  `fcob_white.cfg`, read the comment block directly above it in `overrides.cfg` first.
- Physical keep-out zones (front-left cutter arm, back-left blobifier, y_max feature row, all in
  `CLAUDE.md`) are unaffected by anything in this runbook — no toolhead motion is touched — but
  still apply to any future physical work near the display mount.

## Pre-resolved decisions

1. **Commit `printer_data/config/helixscreen/` as real repo config.** The HelixScreen installer
   placed the user-editable parts of its config here on purpose and symlinked them from
   `~/helixscreen/config/`: `helixscreen.env` → real file, `themes/` → real dir (contains a
   custom `nord.json`), `printer_database.d/` → real dir (currently just the installer's
   `README.md`), `custom_images/` → real but currently empty. `settings.json` itself is **not**
   here — it lives only in `~/helixscreen/config/settings.json` and is not part of this
   directory. Track everything except `crash_history.json` (empty `[]`, runtime state — same
   pattern as `save_variables.cfg`). Veto: if you'd rather keep the whole `helixscreen/`
   directory untracked, just add `helixscreen/` to `.gitignore` instead of Step 3 below.
2. **KlipperScreen stays installed, running, and untouched for now.** Don't remove, disable, or
   reconfigure it as part of this runbook. The replace-vs-coexist call happens later, after the
   maintainer has actually used HelixScreen through a few real prints (Step 6).
3. **Settings iteration happens by editing `~/helixscreen/config/settings.json` over the SSHFS
   mount** (`/home/kyle/projects/karman-printer-mnt/helixscreen/config/settings.json`) followed
   by `systemctl restart helixscreen` on the Pi — not by touching the physical panel per change.
   `~/helixscreen/config/settings.json.template` has an `_<key>_comment` field documenting every
   setting; consult it before changing a key you haven't touched before.

## Progress so far (this session, 2026-08-22)

- **Fixed: screen rendered upside down.** The display key is `display.rotate` in
  `settings.json` (confirmed against the binary's own strings and
  `[Config] Migrated display_rotate -> /display/rotate` in the journal). The maintainer corrected
  the value and restarted the service themselves; journal after the fix shows
  `[Watchdog] Display rotation: 180°` and the running process as `helix-screen --rotate=180`
  (`[DisplayManager] DRM lacks hardware rotation for 180°, falling back to fbdev` — software
  rotation, expected on this panel/DRM combo, not a fault).
- **Fixed: caselight commanded to 100% brightness actually landed at ~1%.** Root cause:
  Klippain's `fcob_white.cfg` sets `[output_pin caselight] scale: 100` so its own
  `LIGHT_ON`/`LIGHT_OFF` macros can pass a plain 0–100 value straight to `set_pin`. Neither
  KlipperScreen's generic Pins panel (`panels/pins.py`: `value = scale.get_value() / 100`) nor
  HelixScreen's LED controller (binary strings show `SET_PIN PIN={} VALUE={:.4f}`, a 0.0–1.0
  fraction) honor a non-default `scale` — both assume Klipper's default `scale: 1` and always
  send `VALUE` as a 0.0–1.0 fraction. Under `scale: 100`, a UI-commanded "100%" (`VALUE=1.0`)
  became actual duty cycle `1.0 / 100 = 1%`. Confirmed by reading Klipper's own
  `klippy/extras/output_pin.py` on the Pi (`value /= self.scale` in `cmd_SET_PIN`) and both UI
  source paths directly, not by guessing.
  **Fix, in `overrides.cfg`:** `[output_pin caselight]` now sets `scale: 1`, `value: 1` (was
  `value: 100`, invalid under the new scale — Klipper's own `value` bound is `[0, scale]`); added
  `[gcode_macro LIGHT_ON]`/`[gcode_macro LIGHT_OFF]` overrides so `LIGHT_ON`'s public `S=0–100`
  interface (used everywhere: `start_print.cfg`, `pause_resume.cfg`, `end_print.cfg`,
  `cancel_print.cfg`, `startup.cfg`, all passing 0–100 values from `variables.cfg`) keeps working
  unchanged — the macro itself now divides by 100 before calling `set_pin`.
  **Validated** by rendering the macro through Klipper's real Jinja2 environment
  (`uv run tools/render_macro.py overrides.cfg LIGHT_ON --params "S=80"` → `value=0.8`; default →
  `value=1.0`). **Not yet validated live on hardware** — see Step 4.
- **Investigated, no fix needed: transient "105 / -" bed-target display.** Queried Moonraker
  directly during the glitch — `heater_bed` reported `target: 105.0` correctly the whole time, so
  the backend was never wrong. Maintainer confirmed it was a one-off that cleared itself, i.e.
  ordinary UI lag (current temp echoes on tap; target only updates on the next status push).
  **Worth revisiting if it recurs and stays stuck**, not if it's occasional: HelixScreen's journal
  showed a `[Moonraker Client] WebSocket connection closed` and a later
  `Klipper disconnected from Moonraker` line with no reconnect message logged after either — a
  real subscription-drop bug would look like this. This session could not confirm from the SSH
  session whether the socket was actually still open (blocked reading `/proc/<pid>/fd` even as
  the owning user — `ss -tnp` also silently failed to attribute two of the four established
  connections to Moonraker's port 7125 to any process, consistent with the same permission gap
  rather than proof those connections are HelixScreen's). If it recurs, that's where to pick up.
- **Researched (official docs): a second HelixScreen instance can run on the maintainer's
  laptop** as a pure Moonraker client pointed at `192.168.1.240:7125` — gives an interactive,
  mouse-driven copy of the same UI for iterating on **printer-behavior** settings (macros, spool
  bindings, etc.). It is **not** a remote-control/mirror of the physical screen — there's no
  general VNC-style feature for a Pi/Voron install (the "view the screen through a webcam"
  capability some HelixScreen docs mention is Snapmaker U1/PAXX-firmware-specific and doesn't
  apply to Karman). **Display-hardware settings stay local to each install's own
  `settings.json`** — rotation, backlight, touch calibration, sleep/dim timers, DRM device — so a
  laptop instance is useful for Step 5 below but not for Step 4.

## Steps

### 1. Add a `docs/decisions.md` entry for the caselight scale fix
Insert above the current top entry (`## 2026-08-20 — Some MMU_TEST_CONFIG parameters...`).
Suggested text:

```markdown
## 2026-08-22 — Caselight `output_pin` reverted to `scale: 1`, not Klippain's `scale: 100`
**Decision:** `[output_pin caselight]` uses `scale: 1` (Klipper's default); `LIGHT_ON` divides
its `S=0-100` param by 100 before calling `set_pin`, in an override in `overrides.cfg`.
**Why:** Klippain's `fcob_white.cfg` sets `scale: 100` so `LIGHT_ON`/`LIGHT_OFF` can pass 0-100
straight through. But neither KlipperScreen's Pins panel nor HelixScreen's LED control read a
pin's configured `scale` — both always send `SET_PIN VALUE` as a 0.0-1.0 fraction, assuming
Klipper's default. Under `scale: 100` a UI-commanded 100% became 1% actual brightness. Reverting
to the Klipper default fixes both UIs without patching either (and they're framework/vendor
binaries — not ours to patch). Confirmed against Klipper's own `output_pin.py` on the Pi.
**If you're tempted to restore `scale: 100`:** don't, unless you're also prepared to patch
KlipperScreen's `panels/pins.py` and HelixScreen's LED controller, which we don't control.
```

### 2. Commit the caselight fix
```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git add overrides.cfg docs/decisions.md && \
  git commit -m "fix(helixscreen): caselight scale mismatch made 100% brightness land at 1%"'
```

### 3. Commit the HelixScreen app config directory (per pre-resolved decision 1)
```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && \
  echo "helixscreen/crash_history.json" >> .gitignore && \
  git add .gitignore helixscreen/helixscreen.env helixscreen/themes helixscreen/printer_database.d && \
  git status -s'
```
Check the `git status -s` output before committing — it should show only files under
`helixscreen/` plus `.gitignore`, nothing from the "Out of scope" list above. Then:
```
ssh ernst@192.168.1.240 "cd ~/printer_data/config && git commit -m 'chore(helixscreen): track app config (env, themes, printer database)'"
```

### 4. Verify the caselight and rotation fixes survive a real reboot — **user must run this on the printer**
Both fixes were only verified via service restart / Jinja rendering so far, not a cold boot.
**Confirm nothing is printing first** (`print_stats.state` should be `standby`/`complete`, not
`printing`/`paused`) — a reboot mid-print will fail the print.
```
ssh ernst@192.168.1.240 'systemctl reboot'
```
After the Pi comes back (give it ~60–90s):
- Screen renders right-side-up, not upside down.
- Caselight at 100% is visibly full brightness, not dim. (Cross-check:
  `ssh ernst@192.168.1.240 "curl -s http://127.0.0.1:7125/printer/objects/query?output_pin%20caselight"`
  should show `"value": 1.0` after commanding 100% from either UI.)
- `journalctl -u helixscreen --no-pager | grep -i "rotation\|caselight"` shows the expected
  180° rotation line and no PWM-range errors.

### 5. Dial in the rest of `settings.json`
Still open, no fixed list — walk `settings.json.template`'s `_comment` fields for: `theme`,
`sleep_sec`/`dim_sec`/`dim_brightness`, `screensaver_type`, `gcode_render_mode`,
`bed_mesh_render_mode`, `touch_device`/calibration, and the per-printer
`printers.default.default_macros` / `leds` / `fans` bindings (already partially populated — see
current `settings.json`). Edit → `systemctl restart helixscreen` → check on-screen → repeat.
*(Optional, faster iteration for non-display-hardware settings: install a second HelixScreen
instance on a laptop per "Progress so far" above —
`curl -sSL https://raw.githubusercontent.com/prestonbrown/helixscreen/main/scripts/install.sh | sh`,
point the wizard's Moonraker step at `192.168.1.240:7125`. Remember this only helps for
printer/macro-behavior settings, not display-hardware ones.)*

### 6. Decide KlipperScreen's fate — **after** Step 5, once HelixScreen has been used through a few real prints
Options: keep both running side by side (current default, pre-resolved decision 2), or retire
KlipperScreen. Not a config change by itself — comes back to a fresh `/brief` if retiring it
turns out to need coordinated changes (e.g. the pending `mmu_klipperscreen.conf` wiring in the
"out of scope" list above would need revisiting, not blindly deleted).

## Verification

- [ ] `docs/decisions.md` has the caselight-scale entry (Step 1).
- [ ] `git log` on the Pi shows the caselight-fix and app-config commits; `git status -s` (via
      SSH) shows nothing from the "Out of scope" list touched.
- [ ] Rotation and caselight both confirmed correct **after a cold reboot**, not just a service
      restart (Step 4).
- [ ] `printer_data/config/helixscreen/` is tracked: `ssh ernst@192.168.1.240 "cd ~/printer_data/config && git ls-files helixscreen/"` lists `helixscreen.env`, `themes/nord.json`,
      `printer_database.d/README.md`; `crash_history.json` does not appear.
- [ ] Maintainer sign-off that `settings.json` reflects their actual preferences (subjective —
      no command proves this, just ask).
- [ ] Explicit decision recorded (even if "defer") on KlipperScreen's fate.

## Commit guidance

Three separate commits, matching Steps 2–3 above (don't combine — the app-config commit and the
caselight fix are unrelated enough to bisect independently):
1. `fix(helixscreen): caselight scale mismatch made 100% brightness land at 1%` —
   `overrides.cfg`, `docs/decisions.md`.
2. `chore(helixscreen): track app config (env, themes, printer database)` — `.gitignore`,
   `helixscreen/helixscreen.env`, `helixscreen/themes/`, `helixscreen/printer_database.d/`.
3. (separately, whenever `moonraker.conf`'s `[update_manager helixscreen]` block is ready to
   commit — it's already in place from the installer, just uncommitted) `chore(helixscreen):
   register Moonraker update-manager entry` — `moonraker.conf`, `.moonraker.conf.bkp`. Check the
   diff first: `.moonraker.conf.bkp` currently also shows a `[update_manager KlipperScreen]`
   block as new-since-last-commit; that's pre-existing (unrelated to this session), fine to
   include since it's already the file's real content, just flag it in the commit body so it
   isn't mistaken for new HelixScreen work.

## Status log

- **2026-08-22** — Runbook opened. Rotation and caselight bugs fixed this session (see "Progress
  so far"); bed-target display glitch investigated and closed as non-reproducing. Nothing
  committed yet — Steps 1–3 are the immediate next actions. Reboot verification (Step 4) and
  settings tuning (Step 5) not started.
