# Printer session-workflow template

A drop-in workflow for running a 3D-printer config repo with Claude Code, generic to any
**CoreXY printer**. It is a generalization of a system built and proven on a Voron 2.4 running a
Klippain + Happy Hare stack, with every machine-specific assumption stripped out and replaced by
a setup interview.

## What problem it solves

Long chat sessions get compacted, and compaction silently drops detail. In practice that means
re-deriving settled facts, and — worse — mislabelling untested work as tested. This workflow
pushes durable knowledge into **files** and keeps **sessions short and disposable**.

```
/setup          → once, on a new machine: interview + generate CLAUDE.md and TODO.md
/start          → open a session: pick its kind, load the right context, set the posture
   ...work...
/brief <obj>    → write a runbook a fresh (or cheaper) session can execute cold
/done           → verify claims against evidence, report honestly, update the docs
```

## What's in here

```
CLAUDE.md                     stub — auto-loaded, tells Claude to run /setup first,
                              then becomes the machine's permanent context file
TODO.md                       seed backlog; the index of record
NOTES.md                      your scratchpad
docs/
  decisions.md                WHY things are set the way they are (append-only)
  workflow.md                 maintainer cheat sheet for this whole system
  runbooks/
    README.md                 the session model + runbook anatomy
    TEMPLATE.md               blank runbook skeleton
    done/                     archived runbooks
.claude/
  settings.json               hook wiring (opt-in; safe to delete)
  protected-paths.txt         paths the guard hook refuses to edit
  hooks/
    README.md                 hook patterns, and how to add machine-specific ones
    guard-protected-paths.sh  generic vendor-file guard
  skills/
    setup/SKILL.md            the one-time interview
    start/SKILL.md            open a session
    brief/SKILL.md            write a runbook
    done/SKILL.md             close a session
```

## Installing it on a new machine

1. **Copy the contents of this directory into the root of the printer's config repo.**
   If that repo already has a `CLAUDE.md` or `TODO.md`, copy those two aside first — `/setup`
   will merge what's worth keeping rather than clobbering it.

2. **Make sure it's a git repo.** `git init` if not. The workflow assumes version control; several
   steps in `/done` report on uncommitted state.

3. **Check the dependency.** The optional guard hook needs `jq`. Skip it if you don't want hooks —
   delete `.claude/settings.json` and `.claude/hooks/` and everything else still works.

4. **Start a Claude Code session in that directory and run `/setup`.**
   It interviews you about the machine, what you've modified, how Claude reaches the config, the
   physical keep-out zones, and what's next — then writes a real `CLAUDE.md` and seeds `TODO.md`.
   Budget 15–20 minutes; it is the highest-leverage time you'll spend, because every later session
   starts from what it produces.

5. **Open `/hooks` once** (or restart the session) if you kept the hooks. Skills and hooks added
   mid-session aren't picked up until the settings watcher re-reads them.

6. Commit.

## Design rules worth preserving if you edit this

These are the parts that make it work, learned the expensive way:

- **`TODO.md` is the single index of record.** Every runbook is reachable from the task it serves.
  Two indexes drift; one doesn't.
- **The out-of-scope section of a runbook is its most valuable part.** It names the validated
  config a fresh session would otherwise "improve". Without it, working config gets broken by a
  well-meaning session with no history.
- **Honest labels in `/done`:** *verified on hardware* / *validated offline* / *written only*.
  Claude must never upgrade a label on the strength of its own reasoning.
- **The user runs the printer.** Claude proposes exact commands and waits for real output. It
  never assumes an outcome it wasn't told.
- **`docs/decisions.md` is append-only and matters most when a value looks wrong but isn't.**
  That's exactly what future-you will try to "fix".

## Adapting it further

The template is deliberately conservative about machine specifics — it asks rather than assumes.
Two places reward customization once you know the machine:

- **`.claude/hooks/`** — the shipped guard is generic. The real wins are machine-specific: a hook
  that re-runs a motion simulator after editing a macro, or one that blocks a known-dangerous
  command. See `.claude/hooks/README.md`.
- **Validation tooling** — there is no offline linter for most printer configs, so a project-local
  simulator or macro renderer pays for itself fast. `/done` will use one if `CLAUDE.md` says it
  exists.
