# Workflow quick reference

**Audience: you (the maintainer).** A cheat sheet for the system this repo runs on.
Claude's own entry point is `CLAUDE.md`; the runbook convention lives in
`docs/runbooks/README.md`. This file is the human-readable index of both.

The session commands come from the **`work-system` plugin** (`/ws-*`). This repo is set up at the
**Full** tier, and `.claude/work-system.json` records the tier, traits, SSH probe and what the
three verification labels mean here. The repo-local `/start` · `/brief` · `/done` skills were
retired on 2026-11-13; see `docs/decisions.md`.

---

## The one-minute version

```
/ws-start          → pick session type, check the Pi is reachable, get oriented
   ...work...
/ws-brief <obj>    → write a runbook a fresh (or cheaper) session can execute cold
/ws-decide         → record why something is the way it is, the moment you learn it
/ws-done           → verify, report, update docs, say if safe to stop
/ws-check          → read-only drift audit (dead TODO links, stalled runbooks, hazard gaps)
```
Long chats lose detail when compacted. Keep sessions short and let the **files** carry knowledge.

---

## Starting a session → `/ws-start`

It runs the SSH probe first, then asks which kind of session this is. You can skip the question:
`/ws-start objective <slug>` · `/ws-start debug` · `/ws-start architecture`

| Kind | Use when | Claude will |
|---|---|---|
| **Objective** | Executing planned work | Read the runbook + related decisions, confirm scope, execute. Stays in scope; notes drift for TODO instead of fixing it |
| **Architecture** | Planning, deciding, writing runbooks | Read TODO + decisions, summarise state, question assumptions. **Makes no config changes** |
| **Debug** | Something broke | Check `decisions.md` and the hazard register for a known cause *first*, gather logs/git evidence, diagnose before changing |

## Planning work → `/ws-brief <objective>`

From an **architecture** session. Produces `docs/runbooks/<slug>.md` (shape: `docs/runbooks/TEMPLATE.md`)
— a self-contained brief a fresh (or cheaper) session can execute with no prior context.

It interviews you only where a decision genuinely needs you, then writes: scope ·
**⚠️ out-of-scope** · **⚠️ hazards in play** (copied from CLAUDE.md) · pre-resolved decisions ·
exact steps tagged human/model · verification · commit guidance.

**It always registers the objective in `TODO.md`**: in the matching section, or in `## Miscellaneous`
for a one-off, or in a new section if it's likely the first of several.

Then run it in a **fresh session**: `/ws-start objective <slug>`.

## Recording a decision → `/ws-decide`

Use it mid-session, as soon as a call is made: a counter-intuitive value, a rejected alternative, or
a bug that cost real time. The entry is prepended to `docs/decisions.md`.

## Ending a session → `/ws-done`

Reports what was done using honest labels — **verified in reality** (ran on the printer, you
reported it) / **validated in a proxy** (visualizer or selftest passed) / **written only** — plus
uncommitted work (git over SSH), config edited but not yet `FIRMWARE_RESTART`ed, loose ends, and
whether it's safe to stop. Updates the runbook status log and `TODO.md`, and prompts for a
`docs/decisions.md` entry.

---

## Where things live

| File | Holds | You edit it? |
|---|---|---|
| `CLAUDE.md` | Durable facts for Claude: hardware, hazard register, framework gotchas, workflow rules | Rarely — it's the model's context |
| `TODO.md` | **Index of record.** Backlog, roadmap, links to runbooks. Actionable above the `# 📖 History` divider | Yes |
| `docs/decisions.md` | **Why** — rejected alternatives, counter-intuitive values, expensive bugs | Append-only |
| `docs/runbooks/*.md` | One objective each. Archived to `done/` when finished | Via `/ws-brief` |
| `docs/*.md` | Subsystem reference (purge math, slicer setup, bed fans…) | As needed |
| `NOTES.md` | Your scratchpad — raw measurements, half-thoughts | Freely |
| `.claude/work-system.json` | Tier, traits, probe, label meanings | Re-run `/ws-init` to change |

**Rule of thumb:** if a future session would waste time rediscovering it → `decisions.md` or
`CLAUDE.md`. If it's *what to do next* → `TODO.md`. If it's *how to do one objective* → a runbook.

---

## Safety nets (automatic)

| Guard | Source | Fires on | Does |
|---|---|---|---|
| **guard-git** | `tools/hooks/` (project) | any `git` in Bash | **Blocks** it on the SSHFS mount — the mount mangles symlinks. Tells Claude to use SSH |
| **check-toolchange** | `tools/hooks/` (project) | Edit/Write on motion files | Re-runs `visualize_toolchange.py` and reports **keep-out violations** |
| **protected paths** | work-system plugin + `.claude/protected-paths.txt` | Edit/Write | **Blocks** edits to `config/`, `macros/`, `moonraker/`, `scripts/`, `klippain_config/` — Klippain overwrites them |
| **danger commands** | work-system plugin + `.claude/danger-commands.txt` | Bash | **Blocks** `MMU_TEST_FORM_TIP` / `MMU_TEST_MOVE` sent through Moonraker |

The project hooks are no-ops in a workstation clone. `/hooks` to review or disable. **Hooks and
skills added mid-session need `/hooks` opened once (or a restart) before they take effect.**

## Validation tools

```
uv run tools/visualize_toolchange.py    # simulate toolchange paths + check keep-outs → HTML
uv run tools/render_macro.py --selftest # bed-fan state machine
```
The visualizer runs automatically after motion-file edits, but you can run it by hand any time you
want the picture. There is **no** offline Klipper config linter — `FIRMWARE_RESTART` is the
authoritative check.

---

## Habits that make this work

- **Let Claude wait for real output.** It should never label something tested unless you said so.
- **Trust measurements over intuition** on unusual hardware — the UHF hotend broke several
  standard-hotend assumptions (see `decisions.md`).
- **Long chat drifting?** `/ws-done`, close it, `/ws-start` fresh. That's the intended cost of doing
  business, not a failure.
- **Made a non-obvious call?** `/ws-decide` while the reasoning is fresh — the value that looks like
  a mistake but isn't is exactly what future-you will "fix".
- **Back after a long gap?** `/ws-check` first.
