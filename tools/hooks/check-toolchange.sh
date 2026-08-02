#!/usr/bin/env bash
# PostToolUse(Write|Edit) check: re-run the toolchange path visualizer whenever a file that
# can move the toolhead is edited, and feed the result back into the conversation.
#
# Why: Klipper has no obstacle model. A wrong park position, cut coordinate or brush position
# crashes the toolhead into the XY idler, the depressor or the blobifier. tools/
# visualize_toolchange.py simulates the real macros against the live config values and checks
# the keep-out zones — but only if someone remembers to run it. This makes it automatic.
#
# stdin: hook JSON. stdout: PostToolUse JSON with additionalContext when something is wrong.
set -uo pipefail

f=$(jq -r '.tool_input.file_path // .tool_response.filePath // ""' 2>/dev/null) || exit 0
[ -n "$f" ] || exit 0

# Only files that participate in toolhead motion.
case "$f" in
  *mmu_macro_vars.cfg|*mmu_parameters.cfg|*blobifier.cfg|*blobifier_hw.cfg|\
  *mmu_cut_tip.cfg|*mmu_sequence.cfg|*overrides.cfg|*variables.cfg) ;;
  *) exit 0 ;;
esac

root="${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"
cd "$root" 2>/dev/null || exit 0
[ -f tools/visualize_toolchange.py ] || exit 0
command -v uv >/dev/null 2>&1 || exit 0

out=$(uv run tools/visualize_toolchange.py 2>&1) || true

# Surface anything that is not a clean run: zone violations or a simulation error.
problems=$(printf '%s\n' "$out" | grep -E 'VIOLATION|SIMULATION ERROR|⚠' || true)
[ -n "$problems" ] || exit 0

jq -n --arg p "$problems" '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: ("tools/visualize_toolchange.py flagged the toolchange paths after this edit. Klipper will NOT prevent these collisions — resolve before the user runs the printer:\n" + $p)
  }
}'
