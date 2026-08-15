---
name: done
description: End-of-session wrap-up for the printer config repo. Verifies claims against evidence, reports uncommitted/unapplied work, updates the active runbook, TODO.md and decisions.md, and says whether the session is safe to close. Use when the user says /done, "wrap up", "end of session", or asks what's left.
---

# Session wrap-up

Produce an honest end-of-session report. **Verify before asserting** — the failure mode this
exists to prevent is confidently reporting work as finished, tested, or safe when it isn't.

## 1. Gather evidence (don't skip; don't infer)

**Git state.** Follow the access rules in `CLAUDE.md` — on some setups git must be run in a
specific place, not wherever is convenient:
```
git status -s
git status -sb | head -1
git log --oneline -8
```

**Config-applied state.** Editing a file is not the same as the printer running it. Establish
whether what's on disk has actually been applied — deployed if this is a clone, and restarted if
the firmware needs it. `CLAUDE.md`'s "Applying changes" section defines what that takes here.

**Offline validation**, if the repo has any and this session touched what it covers. See
`CLAUDE.md`'s "Validating before applying". Run it and report the real result.

## 2. Verify the session's claims

For every "fixed" / "working" / "tested" claim made this session, classify it honestly:

| Label | Means |
|---|---|
| **verified on hardware** | the user ran it on the printer and reported the result |
| **validated offline** | a simulator/selftest/linter passed, but the printer has not run it |
| **written only** | edited, not applied, and not exercised |

Do not upgrade a label on the strength of your own reasoning. If you cannot tell whether the user
actually ran something, **ask** rather than guess — guessing has burned projects in both
directions: claiming untested work was tested, and claiming tested work was untested.

## 3. Report

- **Done this session** — one short paragraph, using the labels above.
- **Uncommitted work** — file list, and a proposed commit split with messages in the repo's
  convention. Do **not** commit or push unless asked.
- **Live on the printer?** — flag anything edited but not yet applied.
- **Loose ends** — anything started and abandoned, TODOs raised mid-session, questions left
  unanswered, a runbook step left half-finished.
- **Safe to close?** — say plainly yes or no, and if no, what must happen first.

  Physical state counts here, not just files. Leaving the machine mid-operation is **not** safe to
  close: filament loaded and hot, a heater left on, a paused or errored job, a part removed, a
  changed park position never jogged by hand, or a sensor unplugged while the config still
  expects it. Say so explicitly and say what to do about it.

## 4. Update the working docs

- **The active runbook** (`docs/runbooks/<slug>.md`) — append to its status log: what was
  verified, what's left, anything a resuming session needs. If the objective is complete, set its
  status to ✅ and move it to `docs/runbooks/done/`. If it's blocked, say so in the status line
  along with what it's blocked on.
- **`TODO.md`** — **the index of record; keep it in sync with the runbooks.** Tick completed
  items, add anything discovered. When a runbook is archived, tick its task and repoint the
  `runbook:` link at `docs/runbooks/done/<slug>.md`. Hand any loose ends the runbook didn't finish
  back to `TODO.md` as their own tasks rather than leaving them buried in an archived file. Keep
  actionable content above the `# 📖 History` divider.
- **`docs/decisions.md`** — **add an entry for any counter-intuitive choice, rejected
  alternative, or bug that cost real debugging time.** This is the step most often skipped and
  most often regretted; a value that looks like a mistake but isn't must be recorded here, or a
  later session will helpfully "fix" it.
- **`CLAUDE.md`** — only for durable facts a *fresh* session would otherwise have to rediscover:
  hardware geometry, newly found keep-out zones, stack gotchas. Not session narrative.

If work remains that doesn't fit the current runbook, suggest `/brief` for it rather than letting
it live only in this chat — when the chat closes, it's gone.
