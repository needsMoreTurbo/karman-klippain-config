# Runbook — {{one-line objective}}

**Objective:** {{What this session achieves, in one or two sentences. Concrete and testable.}}
**Status:** not started · **Created:** {{YYYY-MM-DD}}
**Prerequisites:** {{Parts in hand, prior runbooks completed, machine state required.}}

{{Links to vendor docs, datasheets, or subsystem docs the executor will need. Link, don't
summarise.}}

## Scope
{{The sequence of things this runbook covers, in one line: A → B → C → verified outcome.}}

## ⚠️ Out of scope — do not touch
{{THE MOST IMPORTANT SECTION. Name the validated config near this objective that a fresh session
might "improve" without knowing why it is the way it is. Mine docs/decisions.md for these. For
each: what it is, and one line on why it is that way.}}

- **{{Setting / subsystem}}** — {{why it must not change}}
- **{{Setting / subsystem}}** — {{why it must not change}}

## Pre-resolved decisions
{{Choices already made by the planner, so the executor never stalls. State each as a default the
maintainer can veto in one step.}}

- {{Decision, and the one-line reason.}}

---

## Step 1 — {{name}} *(who does it: user / model)*
{{Exact commands. Expected result. Note if the config must be applied first, or if this is unsafe
mid-print.}}

```
{{command}}
```

{{If this step is a GATE — a result that could invalidate everything downstream — say so here,
and state explicitly what means "stop and escalate" versus "continue".}}

## Step 2 — {{name}} *(who does it)*
...

---

## Verification
{{A checklist that proves the OBJECTIVE, not that the commands ran.}}

- [ ] {{Observable outcome}}
- [ ] {{Nothing else regressed — name what to check}}
- [ ] {{Repeatable / stable across N attempts, where that matters}}

## Commit guidance
- `{{type}}: {{lowercase subject}}` — {{files}}
- {{Any docs/decisions.md entry this work should produce, and what it must record.}}

## Status log
- **{{YYYY-MM-DD}}** — runbook created; not yet started.
