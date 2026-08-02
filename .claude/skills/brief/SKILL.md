---
name: brief
description: Write a self-contained runbook for one objective into docs/runbooks/, so a fresh (or cheaper) session can execute it end to end. Use when the user says /brief, "write a runbook", "plan this objective", or wants to hand work off to another session.
---

# Write an objective runbook

Turn one objective into a runbook a **cold session** can execute without this conversation.
Convention and template: `docs/runbooks/README.md` (read it first if unsure of the shape).

Usage: `/brief <objective>` — e.g. `/brief spoolman integration`.

## The bar

The reader has seen **only `CLAUDE.md`**. They have none of this conversation. Everything they
need is in the runbook or explicitly linked. Assume they may be a cheaper model: no inference,
no judgement calls left open, no "you'll figure it out".

## 1. Establish scope (don't skip; don't invent)

Read what already exists before asking anything: `TODO.md`, `docs/decisions.md`, any related
`docs/*.md`, and the relevant config. Then use **AskUserQuestion** for genuine choices only —
things the executing session cannot safely decide alone:

- Where the objective starts and stops (what counts as done?)
- Any approach fork with real trade-offs
- Anything requiring hardware knowledge you can't read from the repo

Do **not** ask what you can determine yourself. Every question you resolve now is a stall the
cold session avoids.

## 2. Determine the out-of-scope list — the highest-value section

Name the validated config near this objective that a fresh session might "improve" without
knowing why it is the way it is. Mine `docs/decisions.md` for exactly this. Concrete examples:
`park_toolchange` staying `-999,-999`; a measured cut geometry; the `min_toolchange_z` floor.

A runbook without this section is how working config gets broken by a well-meaning session.

## 3. Write it

`docs/runbooks/<kebab-slug>.md`, following the anatomy in `docs/runbooks/README.md`:
header · scope · ⚠️ out of scope · pre-resolved decisions · steps · verification · commit
guidance · status log.

Rules while writing:
- **Exact commands**, not descriptions of commands.
- Mark clearly **which steps the user must run on the printer** — the model never runs the machine.
- Flag steps needing `FIRMWARE_RESTART` first, and anything unsafe to do mid-print.
- Verification proves *the objective*, not that commands executed.
- One objective per runbook. Two verification endpoints ⇒ two runbooks.
- Carry over relevant keep-out zones — geometry work is safety-critical here.

## 4. Register it in TODO.md — required, not optional

**`TODO.md` is the index of record.** Every runbook must be reachable from a task there; a
runbook nobody can find from the backlog is lost work. Decide where the objective belongs:

| Situation | Where it goes |
|---|---|
| Fits an existing section (Filamatrix, Blobifier, NightOwl internals, Happy Hare…) | Add the task **to that section** |
| Standalone one-off, unlikely to spawn follow-ups | Add to a **`## Miscellaneous`** section (create it if absent — place it after the topic sections, before the `(later)` sections) |
| Likely the first of **several** related objectives | Create a **new `##` section** named for the theme, and put the task there |

Then, on the task line:
- Mark it `- [ ]` and link the runbook: `` — runbook: `docs/runbooks/<slug>.md` ``
- If it's the immediate next thing, also add it to **▶ Next up**.
- If it's a large objective, check it belongs in the **🗺 roadmap** too.

**If the objective is already a task in TODO.md**, don't duplicate it — attach the runbook link
to the existing line and update its wording if the brief sharpened the scope.

Keep TODO.md's ordering principle intact: actionable content stays above the `# 📖 History`
divider; nothing actionable goes below it.

## 5. Hand off

Tell the user how to run it: start a **fresh session** and `/start objective <slug>`.

Do not begin executing the runbook in this session unless the user asks — writing the brief and
doing the work are deliberately different sessions.
