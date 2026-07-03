#!/bin/bash
# Config git sync helper, driven by the GIT_PUSH / GIT_PULL gcode macros.
# See docs/bed_fans_control.md's sibling notes and overrides.cfg for the macros.
set -uo pipefail
cd ~/printer_data/config || { echo "config dir missing"; exit 1; }

# Fail fast instead of hanging on a passphrase prompt or unknown host key.
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"

case "${1:-}" in
  pull)
    before=$(git rev-parse HEAD)
    git fetch origin main || { echo "fetch failed"; exit 1; }
    # ff-only: never auto-merge into conflict markers that would brick the config.
    if ! git pull --ff-only origin main; then
      echo "pull is not fast-forward (Pi has diverged) - resolve manually; NOT restarting"
      exit 2
    fi
    after=$(git rev-parse HEAD)
    if [ "$before" != "$after" ]; then
      echo "config updated ${before:0:7} -> ${after:0:7}, restarting firmware"
      curl -sf -X POST http://localhost:7125/printer/firmware_restart >/dev/null \
        || echo "WARNING: firmware restart request failed - restart manually"
    else
      echo "already up to date; no restart needed"
    fi
    ;;
  push)
    git add -A
    if git diff --cached --quiet; then
      echo "nothing new to commit"
    else
      git commit -m "Auto-commit from printer: $(date +'%Y-%m-%d %H:%M:%S')" \
        || { echo "commit failed"; exit 1; }
    fi
    if ! git push origin main; then
      echo "push rejected (remote ahead?) - run GIT_PULL first, then GIT_PUSH"; exit 3
    fi
    ;;
  *)
    echo "usage: git_sync.sh {pull|push}"; exit 64 ;;
esac
