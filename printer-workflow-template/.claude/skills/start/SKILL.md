---
name: start
description: Open a working session on the printer config repo - asks whether this is architecture, objective, or debug work, loads the right context, and sets the working posture for that mode. Use when the user says /start, "new session", or "let's work on X" at the beginning of a chat.
---

# Start a session

Orient fast, then work. `CLAUDE.md` is already loaded; this picks the **mode**, the **extra
context**, and the **posture**. Session model: `docs/runbooks/README.md`.

Usage: `/start` · `/start objective <runbook-slug>` · `/start debug` · `/start architecture`

**Keep this short.** One question, a few lines of orientation, then get to work. If the mode
(and runbook) came as arguments, skip straight to the mode section.

> If `CLAUDE.md` still contains `{{PLACEHOLDER}}` markers, this machine has not been
> characterised. Stop and run **`/setup`** instead — working without it means guessing at
> hardware and geometry.

## First, confirm the access model

`CLAUDE.md` describes how this working copy relates to the live printer. Confirm which situation
you are in before touching anything, since it determines whether an edit is live, needs
deploying, or cannot be made at all. If `CLAUDE.md` gives a detection command, run it.

## Pick the mode

If not given as an argument, use **AskUserQuestion** with these three:

| Mode | When |
|---|---|
| **Objective** | Executing planned work — usually an existing runbook |
| **Architecture** | Planning, deciding direction, writing runbooks — not changing config |
| **Debug** | Something broke or surprised you; unplanned |

---

## Objective mode

1. List `docs/runbooks/*.md` (excluding `README.md`, `TEMPLATE.md`, `done/`) with each one's
   status line. If the user named one, use it. If none exist for what they want, suggest `/brief`
   first rather than improvising the plan here.
2. **Read the whole runbook**, plus anything it links.
3. Read `docs/decisions.md` entries touching this area — that is what stops you "fixing"
   deliberate config.
4. Confirm back in ≤5 lines: the objective, the **out-of-scope list**, and the first step. Then
   begin.

**Posture:** execute the runbook. Stay inside scope — if something outside it looks wrong, note it
for `TODO.md`, don't fix it now. The user runs the printer: give exact commands and wait for real
output. Append to the runbook's status log as you go, so the session is resumable if it ends
early.

## Architecture mode

1. Read `TODO.md` (roadmap + next-up) and `docs/decisions.md` in full.
2. Skim the active runbook list to see what's already planned.
3. Summarise in ≤10 lines: where the project stands, what's in flight, and the open questions you
   can see. Ask what they want to think about.

**Posture:** think broadly and question assumptions — this is the session where challenging the
plan is cheap and welcome. **Do not make config changes.** The output of this mode is runbooks
(`/brief`) and `docs/decisions.md` entries. If a change is genuinely trivial and urgent, say so
and ask rather than assuming.

## Debug mode

1. Ask what happened — exact symptom, what they were doing, any console output or error text.
2. **Check `docs/decisions.md` first** for a matching known cause. Re-diagnosing a documented
   cause from scratch wastes a whole session, and symptoms with non-obvious documented causes are
   exactly what that file exists for.
3. **Gather evidence before theorising.** Using the access model in `CLAUDE.md`: the printer's
   logs, recent commits, and current uncommitted state. Recent changes are the first suspect —
   check what moved before assuming the hardware did.
4. For something still unfolding, watch the log live rather than trading pastes back and forth.
5. Prefer **reading the installed source** of any framework or plugin involved over guessing at
   its behaviour. Guessing at third-party behaviour is a reliable way to lose an afternoon.

**Posture:** diagnose before changing. State the evidence for a cause before proposing a fix, and
say plainly when you're uncertain. When the cause turns out to be non-obvious, add a
`docs/decisions.md` entry as part of the fix.

---

Close any session with **`/done`**.
