# Workflow quick reference

**Audience: you (the maintainer).** A cheat sheet for the system this repo runs on.
Claude's own entry point is `CLAUDE.md`; the runbook convention lives in
`docs/runbooks/README.md`. This file is the human-readable index of both.

---

## The one-minute version

```
/start          → pick session type, get oriented
   ...work...
/done           → verify, report, update docs, say if safe to close
```
Long chats lose detail when compacted. Keep sessions short and let the **files** carry knowledge.

---

## Starting a session

`/start` asks which kind of session this is. You can skip the question:
`/start objective blobifier-bringup` · `/start debug` · `/start architecture`

| Kind | Use when | Claude will |
|---|---|---|
| **Objective** | Executing planned work | Read the runbook + related decisions, confirm scope, execute. Stays in scope; notes drift for TODO instead of fixing it |
| **Architecture** | Planning, deciding, writing runbooks | Read TODO + decisions, summarise state, question assumptions. **Makes no config changes** |
| **Debug** | Something broke | Check `decisions.md` for a known cause *first*, gather logs/git evidence, diagnose before changing |

## Planning work → `/brief <objective>`

From an **architecture** session. Produces `docs/runbooks/<slug>.md` — a self-contained brief a
fresh (or cheaper) session can execute with no prior context.

It will interview you only where a decision genuinely needs you, then write: scope ·
**⚠️ out-of-scope** · pre-resolved decisions · exact steps · verification · commit guidance.

**It always registers the objective in `TODO.md`** — in the matching section, or `## Miscellaneous`
for a one-off, or a new section if it's likely the first of several.

Then run it in a **fresh session**: `/start objective <slug>`.

## Ending a session → `/done`

Reports what was done using honest labels — **verified on hardware** / **validated offline** /
**written only** — plus uncommitted work, config edited but not yet `FIRMWARE_RESTART`ed, loose
ends, and whether it's safe to close. Updates the runbook status log, `TODO.md`, and prompts for a
`docs/decisions.md` entry.

---

## Where things live

| File | Holds | You edit it? |
|---|---|---|
| `CLAUDE.md` | Durable facts for Claude: hardware, keep-outs, framework gotchas, workflow rules | Rarely — it's the model's context |
| `TODO.md` | **Index of record.** Backlog, roadmap, links to runbooks. Actionable above the `# 📖 History` divider | Yes |
| `docs/decisions.md` | **Why** — rejected alternatives, counter-intuitive values, expensive bugs | Append-only |
| `docs/runbooks/*.md` | One objective each. Archived to `done/` when finished | Via `/brief` |
| `docs/*.md` | Subsystem reference (purge math, slicer setup, bed fans…) | As needed |
| `NOTES.md` | Your scratchpad — raw measurements, half-thoughts | Freely |

**Rule of thumb:** if a future session would waste time rediscovering it → `decisions.md` or
`CLAUDE.md`. If it's *what to do next* → `TODO.md`. If it's *how to do one objective* → a runbook.

---

## Safety nets (automatic)

Three hooks run without being asked (`tools/hooks/`, wired in `.claude/settings.json`). All are
no-ops in a workstation clone:

| Hook | Fires on | Does |
|---|---|---|
| **guard-git** | any `git` in Bash | **Blocks** it on the SSHFS mount — the mount mangles symlinks. Tells Claude to use SSH |
| **guard-framework** | Edit/Write | **Blocks** edits to `config/`, `macros/`, `moonraker/`, `scripts/` — Klippain overwrites them |
| **check-toolchange** | Edit/Write on motion files | Re-runs `visualize_toolchange.py` and reports **keep-out violations** |

`/hooks` to review or disable. **Hooks and skills added mid-session need `/hooks` opened once (or
a restart) before they take effect.**

## Validation tools

```
uv run tools/visualize_toolchange.py    # simulate toolchange paths + check keep-outs → HTML
uv run tools/render_macro.py --selftest # bed-fan state machine
```
The visualizer now runs automatically after motion-file edits, but run it by hand any time you
want the picture. There is **no** offline Klipper config linter — `FIRMWARE_RESTART` is the
authoritative check.

---

## Habits that make this work

- **Let Claude wait for real output.** It should never label something tested unless you said so.
- **Trust measurements over intuition** on unusual hardware — the UHF hotend broke several
  standard-hotend assumptions (see `decisions.md`).
- **Long chat drifting?** `/done`, close it, `/start` fresh. That's the intended cost of doing
  business, not a failure.
- **Made a non-obvious call?** Get it into `decisions.md` while the reasoning is fresh — the value
  that looks like a mistake but isn't is exactly what future-you will "fix".
