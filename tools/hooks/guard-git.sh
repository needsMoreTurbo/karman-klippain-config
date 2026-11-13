#!/usr/bin/env bash
# PreToolUse(Bash) guard: refuse git commands run directly on the SSHFS mount.
#
# Why: the mount is exported with follow_symlinks + transform_symlinks, so the Klippain
# framework symlinks (config/, macros/, moonraker/, scripts/, mmu/base/mmu_*.cfg) appear to
# git as type-changes/deletions. Running git here reports bogus changes and would stage a
# mangled tree. Git must run over SSH on the Pi, where the symlinks are native.
#
# Only fires in MOUNT mode (detected exactly as CLAUDE.md documents: the repo's `config/`
# symlink resolves only when the Klippain install is present). In a workstation clone this is a
# no-op, so the same committed settings.json is correct in both modes.
#
# It judges each git invocation by the directory it will actually run in — following `cd`
# along the command chain and `git -C <dir>` — not by the session's starting directory. Git
# aimed anywhere on the mount (the repo, or any other Pi directory under it, e.g.
# ../../Happy-Hare) is blocked; git in an unrelated local repo is allowed. Text inside quotes
# (e.g. `ssh host 'cd ... && git ...'`) is an argument, not a command, so it is never matched.
# A `cd` it cannot resolve (`cd $VAR`, `cd -`) fails closed if git follows it.
#
# stdin: hook JSON. stdout: PreToolUse deny JSON, or nothing to allow.
set -uo pipefail

input=$(cat)
proj="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Not on the mount => nothing to guard.
readlink -e "$proj/config" >/dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0     # no python => fail open, never block work

verdict=$(printf '%s' "$input" | PROJ="$proj" python3 -I -c '
import json, os, shlex, sys
d = json.load(sys.stdin)
cmd = (d.get("tool_input") or {}).get("command") or ""
if not cmd:
    sys.exit()
proj = os.path.realpath(os.environ["PROJ"])
mount_root = os.path.realpath(os.path.join(proj, "..", ".."))   # the Pi home the mount exposes
cwd = d.get("cwd") or os.getcwd()

def on_mount(p):
    p = os.path.realpath(p)
    return p == mount_root or p.startswith(mount_root + os.sep)

def resolve(base, arg):
    if base is None or any(c in arg for c in "$`") or arg == "-":
        return None
    return os.path.normpath(os.path.join(base, os.path.expanduser(arg)))

try:
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()")
    lex.whitespace_split = True
    toks = list(lex)
except ValueError:
    toks = cmd.split()

segs, cur = [], []
for t in toks:
    if t and set(t) <= set(";&|()"):
        segs.append(cur); cur = []
    else:
        cur.append(t)
segs.append(cur)

here = cwd
for s in segs:
    if not s:
        continue
    if s[0] == "cd":
        here = resolve(here, s[1] if len(s) > 1 else "~")
    elif s[0] == "pushd" and len(s) > 1:
        here = resolve(here, s[1])
    elif s[0] == "git":
        target = here
        for i, t in enumerate(s[1:-1], 1):
            if t == "-C":
                target = resolve(target, s[i + 1])
        if target is None or on_mount(target):
            print("deny"); sys.exit()
')

[ "$verdict" = "deny" ] || exit 0

cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Blocked: git must not run on the SSHFS mount (see CLAUDE.md). The mount's transform_symlinks makes the framework symlinks look like type-changes/deletions, so git reports bogus changes and would stage a mangled tree. Re-run it over SSH on the Pi instead, e.g.:\n  ssh ernst@192.168.1.240 'cd ~/printer_data/config && git status -s'"}}
JSON
