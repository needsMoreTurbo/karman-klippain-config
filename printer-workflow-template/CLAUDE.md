# {{PRINTER_NAME}} — {{MAKE_AND_MODEL}} printer config

> ## ⚠️ THIS FILE IS AN UNFILLED TEMPLATE — RUN `/setup` FIRST
>
> If you are a Claude session reading this and it still contains `{{PLACEHOLDER}}` markers, the
> machine has **not** been characterised yet. Do not guess at hardware, geometry, or file layout,
> and do not change any config. Say so, and run the **`/setup`** skill — it interviews the
> maintainer and rewrites this file with real facts.
>
> Delete this whole block once `/setup` has filled the file in.
>
> _(Check with `grep -n '{{' CLAUDE.md` — no hits means it's been filled in.)_

This repo is the printer configuration for **{{PRINTER_NAME}}**, a {{MAKE_AND_MODEL}}
({{KINEMATICS}}, {{BED_SIZE}}{{ENCLOSED}}). This file is auto-loaded by Claude Code and travels
with the repo, so it holds the facts any contributor — human or agent — should not have to
rediscover.

## How Claude reaches this machine

{{ACCESS_MODEL}}

<!-- Filled by /setup. Must answer, concretely:
     - Is this working copy the live config, a network mount of it, or a clone that must be
       deployed?
     - If a clone: exactly how do edits reach the printer? (git pull on the printer, a sync
       script, manual upload through a web UI, SD card…)
     - Can Claude read the machine directly (SSH, HTTP API)? With what command?
     - Anything Claude must NOT do against the machine (write over SSH, restart mid-print…).
     - If there are two modes (e.g. on-machine vs remote clone), give the one-line check that
       tells them apart, and what differs.
-->

## The printer

- **Kinematics / size:** {{KINEMATICS}}, {{BED_SIZE}}.
- **Controller / MCUs:** {{MCUS}}
- **Firmware stack:** {{FIRMWARE_STACK}}
- **Interface:** {{UI}}
- **Hotend / extruder:** {{HOTEND_EXTRUDER}}
- **Probe / bed levelling:** {{PROBE}}
- **Bed / build surface:** {{BED}}
- **Chamber / cooling:** {{CHAMBER_AND_FANS}}
- **Filament handling:** {{FILAMENT_SYSTEM}}
- **Common materials:** {{MATERIALS}}

### Modifications from stock
{{MODIFICATIONS}}

<!-- Anything not as it left the factory: replaced parts, added sensors, custom macros, printed
     mods, rewiring. This is where a fresh session's assumptions most often go wrong. -->

## ⚠️ Physical keep-out zones — nothing in firmware enforces these

The controller has **no obstacle model**. Nothing prevents a crash. Any change to a park position,
purge or wipe coordinate, macro travel, or slicer bed shape must respect the list below.

{{KEEPOUT_ZONES}}

<!-- One bullet per zone: the region (x/y/z bounds), what is physically there, and why it matters.
     Mark which are permanent toolhead geometry (apply to every move, forever) versus
     height-dependent. If none are known yet, say so explicitly — "not yet surveyed" is a useful
     and honest statement; a silent empty list reads as "no hazards". -->

## Repo layout

{{REPO_LAYOUT}}

<!-- Which files are hand-editable, which are vendor/framework-managed and will be overwritten,
     where the firmware's own autosave block lands, what is generated or runtime-written and
     should stay untracked. -->

## Applying changes

{{APPLY_PROCEDURE}}

<!-- The exact sequence to make an edit take effect, e.g. deploy → FIRMWARE_RESTART. Note what is
     unsafe mid-print, and what the authoritative check is that a config is valid (for Klipper
     machines this is usually a restart on the machine — there is no offline linter). -->

## Validating before applying

{{VALIDATION}}

<!-- Any offline checks that exist: macro renderers, motion simulators, linters, unit tests, with
     the exact command. If none exist yet, say "none — the only check is applying it on the
     machine", and consider that a gap worth a TODO. -->

## Hard-won gotchas

{{GOTCHAS}}

<!-- Grows over time. The test for belonging here: a fresh session would waste real time
     rediscovering it, and it is a *fact about this machine or stack* rather than a decision.
     Decisions and their rationale go in docs/decisions.md instead. -->

## Working with the maintainer

- **The maintainer runs the printer; you never see a result you weren't told.** After proposing
  commands, wait for the actual output. Never label work "tested" unless they said so.
- **Ask before guessing on physical facts** — hardware geometry, what is actually installed, what
  was actually run. A wrong assumption about the machine is expensive; a question is cheap.
- **Trust measurements over priors**, especially on modified or unusual hardware.
- **Watch logs live rather than round-tripping pastes** where the access model allows it.

## How sessions work here (read before starting work)

This project runs on **many short, focused sessions**, not one long chat — long sessions get
compacted and silently lose detail. Durable knowledge lives in files; the chat is disposable.

- **`/start`** opens a session: pick **architecture** (plan, decide, write runbooks — no config
  changes), **objective** (execute one runbook), or **debug** (something broke).
- **`/brief <objective>`** (architecture sessions) writes a self-contained runbook to
  `docs/runbooks/` that a fresh — or cheaper — session can execute with no prior context.
- **`/done`** closes a session: verifies claims against evidence, reports uncommitted work, and
  prompts for a `docs/decisions.md` entry.
- Runbook anatomy and what-goes-where: **`docs/runbooks/README.md`**.
  Maintainer cheat sheet: **`docs/workflow.md`** (point the maintainer there if they ask how any
  of this works).
- **`TODO.md` is the index of record** — every runbook is linked from the task it serves.
  Actionable content lives above its `# 📖 History` divider; nothing actionable below.

## Reference docs

- `docs/decisions.md` — **why** things are set the way they are. Read before "fixing" an
  odd-looking value; add an entry when you make a non-obvious call.
- `docs/workflow.md` — maintainer cheat sheet for the session/runbook system.
- `TODO.md` — backlog and roadmap.
- `docs/runbooks/` — one file per objective.
- `NOTES.md` — the maintainer's scratchpad of raw measurements and half-thoughts.
{{EXTRA_DOCS}}

## Conventions

- **Commits:** {{COMMIT_CONVENTION}}
- **Who commits:** {{WHO_COMMITS}}
- {{OTHER_CONVENTIONS}}
