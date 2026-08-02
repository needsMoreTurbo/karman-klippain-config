---
name: start
description: Open a working session on the Karman config repo - asks whether this is architecture, objective, or debug work, loads the right context, and sets the working posture for that mode. Use when the user says /start, "new session", or "let's work on X" at the beginning of a chat.
---

# Start a session

Orient fast, then work. `CLAUDE.md` is already loaded; this picks the **mode**, the **extra
context**, and the **posture**. Session model: `docs/runbooks/README.md`.

Usage: `/start` · `/start objective blobifier-bringup` · `/start debug` · `/start architecture`

**Keep this short.** One question, a few lines of orientation, then get to work. If the mode
(and runbook) came as arguments, skip straight to the mode section.

## Pick the mode

If not given as an argument, use **AskUserQuestion** with these three:

| Mode | When |
|---|---|
| **Objective** | Executing planned work — usually an existing runbook |
| **Architecture** | Planning, deciding direction, writing runbooks — not changing config |
| **Debug** | Something broke or surprised you; unplanned |

---

## Objective mode

1. List `docs/runbooks/*.md` (excluding `README.md`, `done/`) with each one's status line. If the
   user named one, use it. If none exist for what they want, suggest `/brief` first.
2. **Read the whole runbook**, plus anything it links.
3. Read `docs/decisions.md` entries touching this area — that is what stops you "fixing"
   deliberate config.
4. Confirm back in ≤5 lines: the objective, the **out-of-scope list**, and the first step. Then
   begin.

**Posture:** execute the runbook. Stay inside scope — if something outside it looks wrong, note
it for `TODO.md`, don't fix it now. The user runs the printer: give exact commands and wait for
real output. Append to the runbook's status log as you go.

## Architecture mode

1. Read `TODO.md` (roadmap + next-up) and `docs/decisions.md` in full.
2. Skim `docs/runbooks/README.md` active list to see what's already planned.
3. Summarise in ≤10 lines: where the project stands, what's in flight, and the open questions
   you can see. Ask what they want to think about.

**Posture:** think broadly and question assumptions — this is the session where challenging the
plan is cheap and welcome. **Do not make config changes**; the output of this mode is runbooks
(`/brief`) and `docs/decisions.md` entries. If a change is genuinely trivial and urgent, say so
and ask rather than assuming.

## Debug mode

1. Ask what happened — exact symptom, what they were doing, any console output.
2. **Check `docs/decisions.md` first** for a matching known cause. Several symptoms here have
   non-obvious documented causes (a `-999` park sentinel, HH state vs Klipper state, a mechanical
   latch masquerading as motor slip). Re-diagnosing one of those from scratch wastes a session.
3. Gather evidence before theorising:
   ```
   ssh ernst@192.168.1.240 'tail -60 ~/printer_data/logs/mmu.log'
   ssh ernst@192.168.1.240 'cd ~/printer_data/config && git log --oneline -8 && git status -s'
   ```
   For something still unfolding, start a **Monitor** on the log rather than trading pastes.
4. Prefer reading the installed Happy Hare source (`~/Happy-Hare/extras/mmu/mmu.py`) over
   guessing at its behaviour.

**Posture:** diagnose before changing. State the evidence for a cause before proposing a fix,
and say plainly when you're uncertain. Recent commits are the first suspect. When the cause was
non-obvious, add a `docs/decisions.md` entry as part of the fix.

---

Close any session with **`/done`**.
