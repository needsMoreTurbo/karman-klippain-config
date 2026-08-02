---
name: done
description: End-of-session wrap-up for the Karman config repo. Verifies claims against evidence, reports uncommitted/unpushed work and unapplied config, updates the active runbook, TODO.md and decisions.md, and says whether the session is safe to close. Use when the user says /done, "wrap up", "end of session", or asks what's left.
---

# Session wrap-up

Produce an honest end-of-session report. **Verify before asserting** — the failure mode this
exists to prevent is confidently reporting work as finished, tested, or safe when it isn't.

## 1. Gather evidence (don't skip; don't infer)

Git state — **over SSH, never on the mount** (see CLAUDE.md):
```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git status -s && echo --- && git status -sb | head -1 && echo --- && git log --oneline -8'
```

Config-applied state — edits on the mount are live on disk but **inert until `FIRMWARE_RESTART`**:
```
ssh ernst@192.168.1.240 'ls -l --time-style=+%s ~/printer_data/config/*.cfg ~/printer_data/config/mmu/base/*.cfg 2>/dev/null | awk "{print \$6, \$7}" | sort -rn | head -5'
ssh ernst@192.168.1.240 'grep -c . ~/printer_data/logs/klippy.log >/dev/null && tail -3 ~/printer_data/logs/klippy.log'
```

Offline validation, if anything touching motion or macros changed:
```
uv run tools/visualize_toolchange.py     # expect "clean" on all scenarios
uv run tools/render_macro.py --selftest  # only if bed_fans.cfg changed
```

## 2. Verify the session's claims

For every "fixed" / "working" / "tested" claim made this session, classify it honestly:

| Label | Means |
|---|---|
| **verified on hardware** | the user ran it on the printer and reported the result |
| **validated offline** | simulator/selftest passed, but the printer has not run it |
| **written only** | edited, not applied (no `FIRMWARE_RESTART`) and not exercised |

Do not upgrade a label on the strength of your own reasoning. If you cannot tell whether the
user ran something, **ask** rather than guess — guessing in either direction has burned this
project before (claiming untested work was tested, and claiming tested work was untested).

## 3. Report

- **Done this session** — one short paragraph, using the labels above.
- **Uncommitted / unpushed** — file list, and a proposed commit split with Conventional Commit
  messages (`type: lowercase subject`). Do **not** commit or push unless asked.
- **Live on the printer?** — flag any config edited but not yet applied via `FIRMWARE_RESTART`.
- **Loose ends** — anything started and abandoned, TODOs added mid-session, questions left
  unanswered, or a runbook step left half-finished.
- **Safe to close?** — say plainly yes/no, and if no, what must happen first. Leaving the
  printer mid-operation (filament loaded and hot, MMU in a paused/error state, a park position
  changed but never jogged) is *not* safe to close.

## 4. Update the working docs

- **The active runbook** (`docs/runbooks/<slug>.md`) — append to its status log: what was
  verified, what's left, anything a resuming session needs. If the objective is complete, set its
  status to ✅ and `git mv` it to `docs/runbooks/done/`.
- `TODO.md` — **the index of record; keep it in sync with the runbooks.** Tick completed items and
  add anything discovered. When a runbook is archived, tick its task and update the `runbook:` link
  to point at `docs/runbooks/done/<slug>.md`. Hand any loose ends the runbook didn't finish back to
  TODO.md as their own tasks rather than leaving them buried in an archived file. Keep actionable
  content above the `# 📖 History` divider.
- `docs/decisions.md` — **add an entry for any counter-intuitive choice, rejected alternative,
  or bug that cost real debugging time.** This is the step most often skipped and most often
  regretted; a value that looks like a mistake but isn't must be recorded here.
- `CLAUDE.md` — only for durable facts a *fresh* session would otherwise have to rediscover
  (hardware geometry, framework gotchas, keep-out zones). Not session narrative.

If work remains that doesn't fit the current runbook, suggest `/brief` for it rather than
letting it live only in this chat.
