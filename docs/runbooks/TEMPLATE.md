# Runbook — <one-line objective>

**Objective:** <What this session achieves, in one or two sentences. Concrete and testable.>
**Status:** not started · **Created:** <YYYY-MM-DD>
**Prerequisites:** <Materials in hand, prior runbooks completed, state the project must be in.>

<Links to vendor docs, datasheets, specs, or subsystem notes the executor will need. Link, don't
summarise.>

## Scope

<The sequence this runbook covers, in one line: A → B → C → verified outcome.>

## ⚠️ Out of scope — do not touch

<THE MOST IMPORTANT SECTION. Name the validated, working config or state near this objective that
a fresh session might "improve" without knowing why it is the way it is. Mine docs/decisions.md for
these. For each: what it is, and one line on why it is that way.>

- **<Thing>** — <why it must not change>
- **<Thing>** — <why it must not change>

## ⚠️ Hazards in play

<Copy the relevant entries from CLAUDE.md's hazard register verbatim. The executing session has
read only CLAUDE.md and this file — do not make it go looking.>

- **<Hazard>** — <consequence>. <Always-on / conditional on what>.

## Pre-resolved decisions

<Choices already made by the planner, so the executor never stalls on a judgement call. State each
as a default the human can veto in one step.>

- <Decision, and the one-line reason.>

---

## Step 1 — <name> *(who does it: human / model)*

<Exact commands. Expected result.>

```
<command>
```

<If this step is a GATE — a result that could invalidate everything downstream — say so here, and
state explicitly what means "stop and escalate" versus "continue".>

## Step 2 — <name> *(who does it: human / model)*

...

---

## Verification

<A checklist that proves the OBJECTIVE, not that the commands ran.>

- [ ] <Observable outcome>
- [ ] <Nothing else regressed — name what to check>
- [ ] <Repeatable / stable across N attempts, where that matters>

## Commit guidance

- `<type>: <lowercase subject>` — <files>
- <Any docs/decisions.md entry this work should produce, and what it must record.>

## Status log

- **<YYYY-MM-DD>** — runbook created; not yet started.
