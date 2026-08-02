#!/usr/bin/env bash
# PreToolUse(Bash) guard: refuse git commands run directly on the SSHFS mount.
#
# Why: the mount is exported with follow_symlinks + transform_symlinks, so the Klippain
# framework symlinks (config/, macros/, moonraker/, scripts/, mmu/base/mmu_*.cfg) appear to
# git as type-changes/deletions. Running git here reports bogus changes and would stage a
# mangled tree. Git must run over SSH on the Pi, where the symlinks are native.
#
# Only fires in MOUNT mode (detected exactly as CLAUDE.md documents: the `config/` symlink
# resolves only when the Klippain install is present). In a workstation clone this is a no-op,
# so the same committed settings.json is correct in both modes.
#
# stdin: hook JSON. stdout: PreToolUse deny JSON, or nothing to allow.
set -uo pipefail

cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null) || exit 0
[ -n "$cmd" ] || exit 0

# Not on the mount => nothing to guard.
readlink -e config >/dev/null 2>&1 || exit 0

# A git invocation at the start of the command or after a shell separator.
# `git_sync.sh` and similar do not match: a space is required after `git`.
printf '%s' "$cmd" | grep -qE '(^|[;&|(]|&&|\|\|)[[:space:]]*git[[:space:]]' || exit 0

# Already delegated to the Pi.
printf '%s' "$cmd" | grep -q 'ssh[[:space:]]' && exit 0

cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Blocked: git must not run on the SSHFS mount (see CLAUDE.md). The mount's transform_symlinks makes the framework symlinks look like type-changes/deletions, so git reports bogus changes and would stage a mangled tree. Re-run it over SSH on the Pi instead, e.g.:\n  ssh ernst@192.168.1.240 'cd ~/printer_data/config && git status -s'"}}
JSON
