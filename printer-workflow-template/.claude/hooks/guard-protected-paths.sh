#!/usr/bin/env bash
# PreToolUse(Edit|Write) guard: refuse edits to protected paths.
#
# Why: most printer configs contain files that are NOT safely hand-editable — vendor- or
# framework-managed files that get overwritten by their own updater, firmware autosave blocks,
# and generated files. Editing them looks like it works and is silently reverted later, or is
# never tracked by this repo's git history at all.
#
# Patterns live in .claude/protected-paths.txt (one glob per line, "#" comments allowed) so this
# script never needs editing. A file with no patterns makes this a no-op.
#
# Requires: jq
# stdin: hook JSON. stdout: PreToolUse deny JSON, or nothing to allow.
set -uo pipefail

PATTERNS_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/protected-paths.txt"
[ -f "$PATTERNS_FILE" ] || exit 0

command -v jq >/dev/null 2>&1 || exit 0        # no jq => fail open, never block work

f=$(jq -r '.tool_input.file_path // ""' 2>/dev/null) || exit 0
[ -n "$f" ] || exit 0

matched=""
reason=""
while IFS= read -r line || [ -n "$line" ]; do
    # Strip comments and surrounding whitespace; skip blanks.
    pattern="${line%%#*}"
    pattern="$(printf '%s' "$pattern" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [ -n "$pattern" ] || continue

    # A pattern may carry its own explanation after "|".
    case "$pattern" in
        *"|"*)
            reason="${pattern#*|}"
            pattern="${pattern%%|*}"
            pattern="$(printf '%s' "$pattern" | sed -e 's/[[:space:]]*$//')"
            reason="$(printf '%s' "$reason" | sed -e 's/^[[:space:]]*//')"
            ;;
        *) reason="" ;;
    esac

    # shellcheck disable=SC2254  # glob matching is the point
    case "$f" in
        $pattern) matched="$pattern"; break ;;
    esac
done < "$PATTERNS_FILE"

[ -n "$matched" ] || exit 0

[ -n "$reason" ] || reason="It matches a protected path pattern in .claude/protected-paths.txt."

jq -n --arg f "$f" --arg r "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: ("Blocked: " + $f + " must not be edited directly. " + $r +
      " See CLAUDE.md for where hand-edits belong instead.")
  }
}'
