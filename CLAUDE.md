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
- Toolhead-mounted chamber sensor named `Chamber` — reads warm/noisy, so treat it as a *cap*, not a setpoint. (In the slicer, chamber temp must be **0** on MMU filament profiles or Klippain's chamber soak blocks START_PRINT for up to 15 min.)
- LDO 5015 under-bed fans (`[fan_generic Bed_Fans]`, pin `PF9`), controlled by the state machine in `bed_fans.cfg` (design of record: `docs/bed_fans_control.md`).
- Rapido V2 **UHF** hotend + melt-zone extender — long melt zone, so `toolhead_residual_filament` is large (~25 mm) and purge volumes run high. Several MMU symptoms trace back to this.
- Frequent materials: **ABS/ASA** (bed ~105 °C) — chamber/bed thermal behavior matters.

### MMU (the largest subsystem — most work happens here)
- **NightOwl 2-gate MMU** driven by **Happy Hare v3.4.2** (Type-B / VirtualSelector), on its own `[mcu mmu]` (Fysetc Rabbit Burrow). Encoderless: the BTT SFS was removed, so FlowGuard runs off the **PSF sync-feedback** sensor, not an encoder.
- **Filamatrix toolhead cutter** — back-left depressor, cut line y341 (x15 → x0) at **z15**. `form_tip_macro: _MMU_CUT_TIP`.
- **Blobifier** purge tray/bucket at the back left — `purge_macro: BLOBIFIER`, `force_purge_standalone: 1` (slicer wipe tower is OFF). Servo `PC3`, bucket switch `PC1`.
- **Gantry-mounted nozzle rest (x45) and brush (x53–88)** at y_max. Gantry-mounted ⇒ their Z tracks the toolhead, so only an **X slide** seats/unseats the nozzle; Z is irrelevant to engagement.

## ⚠️ Physical keep-out zones (Klipper has NO obstacle model — you enforce these)
Nothing in Klipper prevents a crash. Any change to a park position, brush/purge coordinate, macro
travel, or slicer bed shape must respect these. Verify with `tools/visualize_toolchange.py`.
- **Front-left, x<10 / y<17, at ANY Z** — the Filamatrix cutter arm on the toolhead strikes the
  front-left XY idler. Permanent toolhead geometry; applies to every move, forever.
- **Back-left, x<~20 / y>~335, below z15** — blobifier tray, shaker arm and the depressor. This is why
  `min_toolchange_z: 15` floors all toolchange travel.
- **The y_max feature row** (tray ~x2–17, shaker x4, rest x45, brush x53–88) — must be entered in +Y
  through a **clear lane (15<x<40, or x>95)**, then slid in X. Never approach a feature head-on.
  `_KARMAN_PARK_MOVE` (overrides.cfg) enforces this and is wired in via `user_park_move_macro`.

## Repo layout (Klippain)
- User-editable files live in the **repo root**: `printer.cfg`, `overrides.cfg`, `variables.cfg`, `mcu.cfg`, `bed_fans.cfg`, `git_sync.sh`, plus `tools/` and `docs/`.
- The Klippain framework core (`config/`, `macros/`, `moonraker/`, `scripts/`) are **symlinks into the Klippain install** — they resolve only on the Pi and are absent/dangling in a fresh clone. Don't try to edit them here.
- `save_variables.cfg` is runtime-written and gitignored; don't re-track it.
- Hand-edits go in `overrides.cfg`; Klipper's `SAVE_CONFIG` autosave block lands at the end of `printer.cfg`.

## Reaching the wider Pi filesystem (mount mode only)
When in **MOUNT/on-Pi** mode, this working copy is an **SSHFS mount of the Pi's `/home/ernst/`** (`ernst@192.168.1.240`); the repo root maps to `~/printer_data/config`. (In workstation-clone mode these parents don't exist and the symlinks are dangling — skip this section.) Everything above the repo root is browsable through parent directories — `../../` from here is the Pi's home. Useful parents (all **read-only** — framework installs managed by their own updaters; the symlinks in this repo point into them):
- `../../klippain_config/` — the Klippain framework install that `config/`, `macros/`, `moonraker/`, `scripts/` symlink into.
- `../../Happy-Hare/` — the MMU install that the symlinked `mmu/*.cfg` files point into. **Enabled** in `printer.cfg`. Reading `extras/mmu/mmu.py` there is often the only way to settle a behavior question; do it rather than guessing.
- `../../klipper/`, `../../moonraker/`, `../../mainsail/`, `../../KlipperScreen/`, and the other tool checkouts and `*-env/` venvs.
- `../logs/`, `../gcodes/`, `../database/` — Klipper runtime data.

**Mount vs SSH — this matters.** Every file stat over SSHFS is a network round-trip, so recursive walks across the mount are slow and can hang.
- Use the **mount** (Read/Edit) only to open a **specific known file**.
- Use **SSH** (`ssh ernst@192.168.1.240 '...'`) for anything that **traverses or searches** — `find`, `grep -r`, `ls -R`, `git log`, tailing logs — so the filesystem walk stays local to the Pi. Do not run recursive Glob/Grep across the mount; push them through SSH instead.

**Git MUST run via SSH on the Pi — never from the mount.** The mount is exported with `follow_symlinks` + `transform_symlinks`, so the framework symlinks (`config/`, `macros/`, `moonraker/`, `scripts/`, `mmu/base/mmu_*.cfg`, …) appear to git as type-changes/deletions from this side. Running `git status`/`add`/`commit`/`diff` on the mount reports bogus changes and would stage a mangled tree. Run **every** git command over SSH, e.g. `ssh ernst@192.168.1.240 'cd ~/printer_data/config && git ...'`, where the symlinks are native and git sees the true state. Editing files on the mount is fine — only git must go through SSH. (Confirm: `git status -s` on the Pi shows plain ` M` on real files, whereas the mount shows spurious `T`/`D`.)

## Deploy / sync workflow (primary path in clone mode)
The repo syncs **bidirectionally** with the printer: the workstation makes hand-edits; the Pi writes calibration via `SAVE_CONFIG` and auto-commits through the `GIT_PUSH` / `GIT_PULL` console macros (backed by `git_sync.sh`). This is how edits reach the printer in **workstation-clone** mode. In **mount** mode your edits are already live on the Pi, so `GIT_PULL` isn't needed to deploy — but still commit/push to keep history in sync, and run `FIRMWARE_RESTART` to apply.

- **Deploy = edit in the repo → commit & push → run `GIT_PULL` on the printer.** Do NOT edit files directly over SSH.
- The Pi is reachable at `ernst@192.168.1.240` for **read-only** inspection. _(If this repo is public, consider whether to keep this LAN address here.)_
- `GIT_PULL` is print-safe (blocked mid-print) and only restarts firmware when the pull actually changed something; `git_sync.sh` uses `--ff-only` and non-interactive SSH.

## Klippain + Happy Hare layering (hard-won gotchas)
Two frameworks both think they own the toolhead. Facts that are expensive to rediscover:
- **Klippain already wraps the MMU print-start** (`_KLIPPAIN_MMU_INIT`, `_KLIPPAIN_MMU_LOAD_INITIAL_TOOL`
  inside `START_PRINT`). Do **not** paste HH's raw start block — it double-inits. `MMU_START_SETUP` *is*
  added before `START_PRINT`, but only to feed the slicer tool map / purge volumes.
- **Klippain's MMU macros target HH v2.x; we run v3.4.2.** Mostly compatible, but e.g.
  `printer.mmu.clog_detection` no longer exists (it's FlowGuard now).
- **HH saves the toolhead position at command start and restores it as the final step.** No extension
  hook (`user_post_load_extension`, etc.) can change where a swap *ends* — the save precedes every hook.
  To control the end position, wrap the command from outside (see `SWAP` in overrides.cfg).
- **`user_park_move_macro` receives HH's `-999` "no move" sentinel unfiltered** — HH's own `-999`
  filtering only guards its default path. A user park macro MUST handle it or every toolchange park
  throws "Move out of range".
- **In-print guards must use `printer.print_stats.state`, not `printer.mmu.print_state`.** During
  START_PRINT, HH's state is still `initialized` while Klipper already reads `printing`; guarding on HH
  state alone shuts the hotend off mid-START_PRINT.
- **Never use `MMU_TEST_FORM_TIP` on this machine** — it strands the tip in the 2 m bowden and stamps
  state UNLOADED, so the next `MMU_EJECT` errors. Test cuts with `T0`/`T1`/`MMU_EJECT`; fix desync with
  `MMU_RECOVER` (never hand-crank with `MMU_TEST_MOVE`).

## Working with the maintainer
- **The maintainer runs the printer; you never see a result you weren't told.** After proposing
  console commands, wait for the actual output — don't assume an outcome, and don't label work
  "tested" unless they said so. (Both directions of that mistake have happened here.)
- **Ask before guessing on physical facts.** Hardware geometry, what's installed, what was
  actually run. A wrong assumption about the machine is expensive; a question is cheap.
- **Trust measurements over priors when the hardware is unusual** — the UHF hotend broke several
  standard-hotend intuitions (see `docs/decisions.md`).
- **Watch the printer's logs live instead of round-tripping pastes.** For a test that will take
  a while, start a Monitor on the Pi's log and let its output wake you:
  `ssh ernst@192.168.1.240 'tail -Fn0 ~/printer_data/logs/mmu.log'`
  (also `klippy.log`). Much faster than "run it, paste the error, repeat".

## How sessions work here (read this before starting work)
This project runs on **many short, focused sessions**, not one long chat — long sessions get
compacted and silently lose detail. Durable knowledge lives in files; the chat is disposable.
- **`/start`** opens a session: pick **architecture** (plan, decide, write runbooks — no config
  changes), **objective** (execute one runbook), or **debug** (something broke).
- **`/brief <objective>`** (architecture sessions) writes a self-contained runbook to
  `docs/runbooks/` that a fresh — or cheaper — session can execute without any prior context.
- **`/done`** closes a session: verifies claims against evidence, reports uncommitted work, and
  prompts for a `docs/decisions.md` entry.
- Runbook anatomy + what-goes-where: **`docs/runbooks/README.md`**. Maintainer cheat sheet:
  **`docs/workflow.md`** (point the user there if they ask how any of this works).
- **`TODO.md` is the index of record** — every runbook is linked from the task it serves.
  Actionable content lives above its `# 📖 History` divider; nothing actionable below.

## Automation in this repo (`.claude/`)
- `.claude/settings.json` wires three hooks (scripts in `tools/hooks/`, all mode-aware no-ops in
  a workstation clone): **guard-git** blocks git run on the mount, **guard-framework** blocks
  edits to the Klippain install, **check-toolchange** re-runs the visualizer after any edit to a
  motion-affecting file and reports keep-out violations. Run `/hooks` to review or disable.
- Skills in `.claude/skills/`: **`/start`** (open a session), **`/brief`** (write a runbook),
  **`/done`** (wrap up — verifies claims against evidence before reporting).

## Reference docs (`docs/`)
`bed_fans_control.md` · `camera_streaming.md` · `custom_macros.md` · `thermal_expansion.md` ·
`decisions.md` (**why** things are set the way they are — read before "fixing" an odd-looking
value; add an entry when you make a non-obvious call) · `workflow.md` (maintainer cheat sheet for
the session/runbook system) · `start_print_walkthrough.md` ·
`pa_physics.md` (pressure advance from a strain-gauge sensor — the melt model, how a fit of it goes
wrong, what the sensor cannot measure, and the calibration protocol; code-level notes live in
`physics/README.md`) ·
**MMU:** `mmu_purge_volume.md` (how purge length is computed),
`mmu_slicer_setup.md` (OrcaSlicer checklist), `mmu_standalone_swap_plan.md` (standalone-swap runbook).
`TODO.md` holds the build backlog; `docs/runbooks/` the per-objective runbooks; `NOTES.md` is the
maintainer's scratchpad of hardware measurements.

## Git conventions
- **Conventional Commits**: `type: lowercase subject`, single line. Types in use: `feat`, `docs`, `tools`, `chore`, `fix`.
- The maintainer runs their own commits/pushes — propose commands + a typed message, don't commit/push unless asked.
- Pull strategy differs on purpose: workstation `pull.rebase true` (interactive), Pi `pull.ff only` (fail-safe for automation).

## Validating Klipper macros before pushing
Klipper macro logic isn't cheaply unit-testable on hardware, so validate offline first:
```
uv run tools/render_macro.py --selftest
```
`tools/render_macro.py` renders `[gcode_macro]`/`[delayed_gcode]` bodies through Klipper's real Jinja2 environment — single-brace `{ }` expressions (not `{{ }}`), `{% %}` statements, `jinja2.ext.do` — and self-tests the bed-fan state machine. It needs Python ≥3.11 with `jinja2`; the script carries a PEP 723 header, so `uv run` self-provisions it.

**Any change to toolhead motion (park positions, cut/purge/brush geometry, macros) must also pass:**
```
uv run tools/visualize_toolchange.py    # writes tools/toolchange_viz.html (gitignored)
```
It simulates the real macros with the live config values, draws the path over a bed map, and
auto-checks the keep-out zones above. Expect "clean" on all scenarios. Cheaper and safer than
re-jogging by hand — but it can't see HH's internal Python moves, which it marks "inferred".

There is **no** offline Klipper config linter — the authoritative check is `FIRMWARE_RESTART` on the Pi after deploy.
