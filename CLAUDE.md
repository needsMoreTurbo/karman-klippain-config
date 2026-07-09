# Karman — Voron 2.4 / Klippain config

This repo is the Klipper configuration for **Karman**, a Voron 2.4 running a **Klippain**-based config. It is a working copy of the printer's `~/printer_data/config`. This file is auto-loaded by Claude Code and travels with the repo, so it holds the repo/printer facts any contributor (or agent) should know.

## Which mode am I in? (check this first)
This repo is used two ways, and the safe workflow differs. **Detect the mode before editing or searching:**
```
readlink -e config >/dev/null 2>&1 && echo "MOUNT/on-Pi" || echo "WORKSTATION CLONE"
```
`config/` is a framework symlink into `~/klippain_config/config` that resolves **only when the Klippain install is present** — i.e. on the Pi or through the SSHFS mount. A second confirmation: `../../Happy-Hare` / `../../klipper` exist in **mount** mode but not in a clone.

- **Workstation clone** — a plain git clone on your machine. Framework symlinks (`config/`, `macros/`, `moonraker/`, `scripts/`, the symlinked `mmu/*.cfg`) are **dangling**; parent dirs are just your projects folder, not the Pi. Edits reach the printer only via the **Deploy / sync workflow** below (commit → push → `GIT_PULL`). The Pi may or may not be reachable.
- **SSHFS mount / on the Pi** — you are editing the printer's **live** `~/printer_data/config`. Symlinks resolve, parent directories are the Pi's home, and an edit here is applied immediately (still needs a `FIRMWARE_RESTART` to take effect — see below). Use the mount/SSH rules under **Reaching the wider Pi filesystem**. In this mode you generally do *not* need `GIT_PULL` to deploy, but still commit/push so the repo history stays in sync.

## Printer
- Voron 2.4 (350 mm) named "Karman"; Klippain framework (V2.4 layout).
- Beacon probe; Keenovo bed (`[heater_bed] max_power: 0.8`).
- Toolhead-mounted chamber sensor named `Chamber` — reads warm/noisy, so treat it as a *cap*, not a setpoint.
- LDO 5015 under-bed fans (`[fan_generic Bed_Fans]`, pin `PF9`), controlled by the state machine in `bed_fans.cfg` (design of record: `docs/bed_fans_control.md`).
- Frequent materials: **ABS/ASA** (bed ~105 °C) — chamber/bed thermal behavior matters.

## Repo layout (Klippain)
- User-editable files live in the **repo root**: `printer.cfg`, `overrides.cfg`, `variables.cfg`, `mcu.cfg`, `bed_fans.cfg`, `git_sync.sh`, plus `tools/` and `docs/`.
- The Klippain framework core (`config/`, `macros/`, `moonraker/`, `scripts/`) are **symlinks into the Klippain install** — they resolve only on the Pi and are absent/dangling in a fresh clone. Don't try to edit them here.
- `save_variables.cfg` is runtime-written and gitignored; don't re-track it.
- Hand-edits go in `overrides.cfg`; Klipper's `SAVE_CONFIG` autosave block lands at the end of `printer.cfg`.

## Reaching the wider Pi filesystem (mount mode only)
When in **MOUNT/on-Pi** mode, this working copy is an **SSHFS mount of the Pi's `/home/ernst/`** (`ernst@192.168.1.240`); the repo root maps to `~/printer_data/config`. (In workstation-clone mode these parents don't exist and the symlinks are dangling — skip this section.) Everything above the repo root is browsable through parent directories — `../../` from here is the Pi's home. Useful parents (all **read-only** — framework installs managed by their own updaters; the symlinks in this repo point into them):
- `../../klippain_config/` — the Klippain framework install that `config/`, `macros/`, `moonraker/`, `scripts/` symlink into.
- `../../Happy-Hare/` — the MMU install that the symlinked `mmu/*.cfg` files point into. (In `printer.cfg` the `[include mmu/base/mmu_*.cfg]` lines are currently commented out.)
- `../../klipper/`, `../../moonraker/`, `../../mainsail/`, `../../KlipperScreen/`, and the other tool checkouts and `*-env/` venvs.
- `../logs/`, `../gcodes/`, `../database/` — Klipper runtime data.

**Mount vs SSH — this matters.** Every file stat over SSHFS is a network round-trip, so recursive walks across the mount are slow and can hang.
- Use the **mount** (Read/Edit) only to open a **specific known file**.
- Use **SSH** (`ssh ernst@192.168.1.240 '...'`) for anything that **traverses or searches** — `find`, `grep -r`, `ls -R`, `git log`, tailing logs — so the filesystem walk stays local to the Pi. Do not run recursive Glob/Grep across the mount; push them through SSH instead.

## Deploy / sync workflow (primary path in clone mode)
The repo syncs **bidirectionally** with the printer: the workstation makes hand-edits; the Pi writes calibration via `SAVE_CONFIG` and auto-commits through the `GIT_PUSH` / `GIT_PULL` console macros (backed by `git_sync.sh`). This is how edits reach the printer in **workstation-clone** mode. In **mount** mode your edits are already live on the Pi, so `GIT_PULL` isn't needed to deploy — but still commit/push to keep history in sync, and run `FIRMWARE_RESTART` to apply.

- **Deploy = edit in the repo → commit & push → run `GIT_PULL` on the printer.** Do NOT edit files directly over SSH.
- The Pi is reachable at `ernst@192.168.1.240` for **read-only** inspection. _(If this repo is public, consider whether to keep this LAN address here.)_
- `GIT_PULL` is print-safe (blocked mid-print) and only restarts firmware when the pull actually changed something; `git_sync.sh` uses `--ff-only` and non-interactive SSH.

## Git conventions
- **Conventional Commits**: `type: lowercase subject`, single line. Types in use: `feat`, `docs`, `tools`, `chore`, `fix`.
- The maintainer runs their own commits/pushes — propose commands + a typed message, don't commit/push unless asked.
- Pull strategy differs on purpose: workstation `pull.rebase true` (interactive), Pi `pull.ff only` (fail-safe for automation).

## Validating Klipper macros before pushing
Klipper macro logic isn't cheaply unit-testable on hardware, so validate offline first:
```
uv run tools/render_macro.py --selftest
```
`tools/render_macro.py` renders `[gcode_macro]`/`[delayed_gcode]` bodies through Klipper's real Jinja2 environment — single-brace `{ }` expressions (not `{{ }}`), `{% %}` statements, `jinja2.ext.do` — and self-tests the bed-fan state machine. It needs Python ≥3.11 with `jinja2`; the script carries a PEP 723 header, so `uv run` self-provisions it. There is **no** offline Klipper config linter — the authoritative check is `FIRMWARE_RESTART` on the Pi after deploy.
