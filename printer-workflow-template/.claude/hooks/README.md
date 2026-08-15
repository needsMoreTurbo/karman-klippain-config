# Hooks

Hooks run automatically, without the model choosing to. That makes them the right place for rules
that must hold **even when the model forgets** — which, over enough sessions, it will.

Wired in `.claude/settings.json`. Review or disable with `/hooks`.

> **Gotcha:** hooks and skills added mid-session are not picked up until the settings watcher
> re-reads them. Open `/hooks` once, or restart the session.

## What ships here

| Hook | Fires on | Does |
|---|---|---|
| `guard-protected-paths.sh` | `Edit`/`Write` | Denies edits to any path matching `.claude/protected-paths.txt`, with an explanation of where the edit belongs instead |

It is data-driven: add glob patterns to `.claude/protected-paths.txt`, never to the script. With
no patterns it's a no-op, so it's harmless until you've decided what to protect.

**Dependency:** `jq`. The hook fails open if `jq` is missing — it will never block work because a
tool is absent.

## Hooks worth adding once you know the machine

The generic guard is the floor, not the ceiling. The highest-value hooks are specific to how a
given machine can hurt you:

- **Motion / geometry check.** If the repo grows a simulator that checks toolhead paths against
  the keep-out zones, run it on `PostToolUse` after edits to motion-affecting files and surface
  any violation immediately. Catching a crash at edit time rather than at print time is the single
  biggest win available here.
- **Block a dangerous command.** If a command is destructive on this machine or must be run
  somewhere specific (git that has to run on the printer rather than a mount, a flash command that
  must never run mid-print), a `PreToolUse` `Bash` guard is more reliable than a note in
  `CLAUDE.md`.
- **Config validation.** If an offline linter exists for this firmware, run it after config edits.
- **Print-state guard.** If the machine exposes its state over an API, a hook can refuse edits or
  restarts while a print is running.

## Writing one

The contract, briefly:

- **stdin** is JSON describing the tool call. `.tool_input.file_path` for `Edit`/`Write`,
  `.tool_input.command` for `Bash`.
- **To allow:** exit 0 with no output.
- **To deny (PreToolUse):** print
  ```json
  {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",
   "permissionDecisionReason":"why, and what to do instead"}}
  ```
- **To surface information (PostToolUse):** print the message; it reaches the model as feedback.

Two rules learned the hard way:

1. **Fail open.** A hook that errors should let work proceed, not block it. Guard every external
   dependency.
2. **Make the reason actionable.** "Blocked" wastes a turn; "Blocked — put hand-edits in
   `overrides.cfg` instead" does not. The model reads this string and acts on it.
