#!/usr/bin/env bash
# PreToolUse(Edit|Write) guard: refuse edits to the Klippain framework installs.
#
# Why: config/, macros/, moonraker/ and scripts/ are symlinks into ~/klippain_config, which is
# managed by Klippain's own updater. Edits there are silently reverted on the next update and
# are invisible to this repo's git history. Hand-edits belong in overrides.cfg / variables.cfg.
#
# stdin: hook JSON. stdout: PreToolUse deny JSON, or nothing to allow.
set -uo pipefail

f=$(jq -r '.tool_input.file_path // ""' 2>/dev/null) || exit 0
[ -n "$f" ] || exit 0

case "$f" in
  */printer_data/config/config/*|*/printer_data/config/macros/*|\
  */printer_data/config/moonraker/*|*/printer_data/config/scripts/*|\
  */klippain_config/*) ;;
  *) exit 0 ;;
esac

jq -n --arg f "$f" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: ("Blocked: " + $f + " is part of the Klippain framework install (see CLAUDE.md). It is symlinked into ~/klippain_config, managed by Klippain'"'"'s updater, so edits are reverted on update and never tracked by this repo. Put hand-edits in overrides.cfg (macros/overrides) or variables.cfg (settings) instead.")
  }
}'
