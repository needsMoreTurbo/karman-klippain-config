# Workflow quick reference

**Audience: you (the maintainer).** A cheat sheet for the system this repo runs on. Claude's own
entry point is `CLAUDE.md`; the runbook convention lives in `docs/runbooks/README.md`. This file
is the human-readable index of both.

---

## The one-minute version

```
/setup          → once per machine: interview + write CLAUDE.md and seed TODO.md
/start          → pick session type, get oriented
   ...work...
/done           → verify, report, update docs, say if safe to close
```

Long chats lose detail when compacted. Keep sessions short and let the **files** carry knowledge.

---

## First run on a new machine → `/setup`

Interviews you about the printer, what you've modified, how Claude reaches the config, the
physical keep-out zones, and what's next — then writes `CLAUDE.md` and seeds `TODO.md`.

Budget 15–20 minutes and take the keep-out questions seriously. Every later session starts from
what this produces, so errors there propagate quietly.

## Starting a session → `/start`

Asks which kind of session this is. You can skip the question:
`/start objective <slug>` · `/start debug` · `/start architecture`

| Kind | Use when | Claude will |
|---|---|---|
| **Objective** | Executing planned work | Read the runbook + related decisions, confirm scope, execute. Stays in scope; notes drift for TODO instead of fixing it |
| **Architecture** | Planning, deciding, writing runbooks | Read TODO + decisions, summarise state, question assumptions. **Makes no config changes** |
| **Debug** | Something broke | Check `decisions.md` for a known cause *first*, gather logs and git evidence, diagnose before changing |

## Planning work → `/brief <objective>`

From an **architecture** session. Produces `docs/runbooks/<slug>.md` — a self-contained brief a
fresh (or cheaper) session can execute with no prior context.

It interviews you only where a decision genuinely needs you, then writes: scope ·
**⚠️ out-of-scope** · pre-resolved decisions · exact steps · verification · commit guidance.

**It always registers the objective in `TODO.md`** — in the matching section, or `## Miscellaneous`
for a one-off, or a new section if it's likely the first of several.

Then run it in a **fresh session**: `/start objective <slug>`.

## Ending a session → `/done`

Reports what was done using honest labels — **verified on hardware** / **validated offline** /
**written only** — plus uncommitted work, config edited but not yet applied, loose ends, and
whether it's safe to close. Updates the runbook status log and `TODO.md`, and prompts for a
`docs/decisions.md` entry.

"Safe to close" includes the *physical* state of the machine, not just the files.

---

## Where things live

| File | Holds | You edit it? |
|---|---|---|
| `CLAUDE.md` | Durable facts for Claude: hardware, keep-outs, stack gotchas, workflow rules | Rarely — it's the model's context |
| `TODO.md` | **Index of record.** Backlog, roadmap, links to runbooks. Actionable above the `# 📖 History` divider | Yes |
| `docs/decisions.md` | **Why** — rejected alternatives, counter-intuitive values, expensive bugs | Append-only |
| `docs/runbooks/*.md` | One objective each. Archived to `done/` when finished | Via `/brief` |
| `docs/*.md` | Subsystem reference | As needed |
| `NOTES.md` | Your scratchpad — raw measurements, half-thoughts | Freely |

**Rule of thumb:** if a future session would waste time rediscovering it → `decisions.md` or
`CLAUDE.md`. If it's *what to do next* → `TODO.md`. If it's *how to do one objective* → a runbook.

---

## Safety nets (optional)

Hooks in `.claude/hooks/`, wired in `.claude/settings.json`, run without being asked. The template
ships one generic guard that refuses edits to paths listed in `.claude/protected-paths.txt` —
useful for vendor-managed or auto-generated files that would be silently overwritten.

`/hooks` to review or disable. **Hooks and skills added mid-session need `/hooks` opened once (or
a session restart) before they take effect.**

The highest-value hooks are machine-specific — see `.claude/hooks/README.md` for the patterns
worth adding once you know the machine.

---

## Habits that make this work

- **Let Claude wait for real output.** It should never label something tested unless you said so.
- **Trust measurements over intuition** on modified or unusual hardware.
- **Long chat drifting?** `/done`, close it, `/start` fresh. That's the intended cost of doing
  business, not a failure.
- **Made a non-obvious call?** Get it into `decisions.md` while the reasoning is fresh — the value
  that looks like a mistake but isn't is exactly what future-you will "fix".
- **Found a new way to crash the toolhead?** It goes in `CLAUDE.md`'s keep-out list immediately,
  not "later".
