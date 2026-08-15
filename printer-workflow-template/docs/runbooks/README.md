# Runbooks — the session model

This project runs on **many short, focused sessions** rather than one long chat. Durable knowledge
lives in files; a chat is disposable. A runbook is the handoff artifact that makes that work: a
self-contained brief one fresh session can execute end to end.

## Three kinds of session

| Kind | Purpose | Produces | Typical length |
|---|---|---|---|
| **Architecture** | Hold the map. Decide direction, resolve cross-cutting questions, plan the next objectives. | Runbooks + `docs/decisions.md` entries. **Not** config changes. | Long-lived, occasional |
| **Objective** | Execute exactly one runbook. | A verified outcome on the machine + commits | Short, disposable |
| **Debug** | React to something broken or surprising. Unplanned. | A fix, plus a `decisions.md` entry if the cause was non-obvious | Short |

Start one with `/start` (it asks which kind and orients accordingly). Close one with `/done`.
Write a runbook with `/brief <objective>` from an architecture session.

**Why bother:** long sessions get compacted, and compaction silently drops detail. In practice
that means re-deriving settled facts and, at worst, mislabelling tested work as untested or the
reverse. A focused session starts with a small, correct context: `CLAUDE.md` (auto-loaded) plus
one runbook.

## Where things live

| File | Holds | Lifetime |
|---|---|---|
| `CLAUDE.md` | Durable facts a fresh session must not have to rediscover: hardware, keep-out zones, stack gotchas, workflow rules | Permanent |
| `docs/decisions.md` | **Why** — rejected alternatives, counter-intuitive values, expensive bugs | Permanent, append-only |
| `docs/*.md` | Subsystem reference | Permanent |
| `TODO.md` | Backlog + roadmap; links to active runbooks | Permanent |
| `docs/runbooks/*.md` | One objective each: steps, scope, status | Until done, then archived to `done/` |
| `NOTES.md` | Maintainer scratchpad: raw measurements, half-thoughts | Freely overwritten |

A runbook is **not** a diary. Durable outcomes graduate into `decisions.md` / `CLAUDE.md` /
`docs/`; the runbook keeps only the execution record.

## Anatomy of a good runbook

`/brief` writes this shape automatically; `TEMPLATE.md` is the blank form.

1. **Header** — objective in one line, status, date, prerequisites.
2. **Scope** — what this session will do.
3. **Out of scope / do not touch** — ⚠️ the most important section. Names the validated config a
   cold session might otherwise "improve". Without it, a fresh session with no history wanders
   into working config.
4. **Pre-resolved decisions** — choices already made, stated as defaults the user can veto in one
   step, so execution never stalls on a judgement call the planner already made.
5. **Steps** — numbered, each with exact commands and the expected result. Mark which steps the
   *user* must run on the printer. Note any step that needs the config applied first.
6. **Verification** — a checklist that proves the objective, not just that commands ran.
7. **Commit guidance** — proposed split and commit subjects.
8. **Status log** — appended during execution: what happened, what's left.

## Rules

- **One objective per runbook.** If it needs two verification endpoints, it's two runbooks.
- **Self-contained.** Assume the executing session has read only `CLAUDE.md`. Spell out commands;
  link rather than summarise for background.
- **Written for a cheaper model.** No inference required — if a decision is needed, pre-resolve it
  or make it an explicit question.
- **Gate the risky steps.** If an early result could invalidate everything after it, say plainly
  what "stop and escalate" looks like versus "carry on".
- **Update as you go.** The status log is the handoff if the objective spans sessions — and they
  often do.
- **Archive when done** — move to `done/`, and record any lasting *why* in `docs/decisions.md`.

## Finding runbooks

**`TODO.md` is the index of record** — every runbook is linked from the task it serves, in the
section that task belongs to. Don't keep a second list here; two indexes drift.

- **Active** — `ls docs/runbooks/*.md`, or follow the `runbook:` links in `TODO.md`.
- **Completed** — `docs/runbooks/done/`.

When `/brief` writes a runbook it **must** register the objective in `TODO.md`: into the matching
section if one exists, into `## Miscellaneous` if it's a standalone one-off, or into a new section
if it's likely the first of several related objectives.
