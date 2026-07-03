# Karman — Voron 2.4 / Klippain config

This repo is the Klipper configuration for **Karman**, a Voron 2.4 running a **Klippain**-based config. It is a working copy of the printer's `~/printer_data/config`. This file is auto-loaded by Claude Code and travels with the repo, so it holds the repo/printer facts any contributor (or agent) should know.

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

## Deploy / sync workflow
The repo syncs **bidirectionally** with the printer: the workstation makes hand-edits; the Pi writes calibration via `SAVE_CONFIG` and auto-commits through the `GIT_PUSH` / `GIT_PULL` console macros (backed by `git_sync.sh`).

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
