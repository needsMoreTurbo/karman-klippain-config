# Revert the touchscreen to KlipperScreen (Happy Hare edition), retire HelixScreen

**Objective:** Karman's 4.3" touchscreen runs **KlipperScreen – Happy Hare edition** again, updated
to the latest `origin/master`, surviving a cold boot with correct rotation, touch and a working MMU
panel. HelixScreen is fully uninstalled from the Pi and removed from this repo.
**Status:** Done 2026-11-08 — all Verification items confirmed.
**Date opened:** 2026-11-08
**Supersedes:** `docs/runbooks/helixscreen-migration.md` (closed by Step 8 of this runbook).
**Prerequisites:**
- Mount mode (`readlink -e config` resolves) — all git commands run **over SSH** (`CLAUDE.md`).
- Pi reachable at `ernst@192.168.1.240`.
- **Nothing printing** for the whole runbook — Step 3 may restart Moonraker and Step 7 reboots the Pi.
- The maintainer has their **own terminal** for Steps 3–4: they need `sudo`, which needs a TTY. The
  agent cannot run them, and Claude Code's `!` prefix cannot answer a sudo password prompt either.

## Why (context the executing session needs)

The maintainer tried HelixScreen from 2026-08-20 and is going back. Their reasons, verbatim in
substance: HelixScreen suits larger screens and Karman's 4.3" (800×480) panel is too small for it;
the interface is too dense; everyday tasks such as setting temperatures take more interaction; it
is more customizable, but they don't want to spend time customizing a UI and want a good default.
These reasons go into the `docs/decisions.md` entry (Step 8) so nobody re-migrates without
addressing them.

## Facts already established (2026-11-08, read from the Pi — don't re-derive)

- `~/KlipperScreen` is a checkout of `https://github.com/moggieuk/KlipperScreen-Happy-Hare-Edition.git`,
  branch `master`, HEAD `e448ebac`, **18 commits behind** `origin/master` (`1ad01a13`). Pending
  commits include `94be28f1 Fix MMU panel breaking permanently after a cold boot`. Its venv is
  `~/.KlipperScreen-env`. `~/KlipperScreen.orig` is an old **stock** KlipperScreen checkout — not
  used by anything; leave it.
- `KlipperScreen.service` exists but is **disabled + inactive**; it runs X on tty7
  (`BACKEND=X`). Last ran 2026-08-22 with the MMU panels working (`~/printer_data/logs/KlipperScreen.log`).
- **Rotation for KlipperScreen is already in place** and needs nothing:
  `/etc/X11/xorg.conf.d/40-dsi-rotate.conf` (written by `~/pi5-display-rotate.sh`) rotates the DSI
  image 180° and applies a 180° touch `TransformationMatrix`. HelixScreen's own rotation lived in
  its `settings.json` and leaves with it.
- `moonraker.conf` already registers `[update_manager KlipperScreen]` (HH edition origin, a
  `LEGACY` comment block above it) and `[update_manager helixscreen]` (installer-written).
- `KlipperScreen.conf` contains `[include mmu_klipperscreen.conf]` under a `LEGACY` comment;
  `mmu_klipperscreen.conf` (Happy Hare's KlipperScreen menus) is tracked in the repo.
- HelixScreen's footprint: `/etc/systemd/system/helixscreen.service`,
  `helixscreen-update.path`, `helixscreen-update.service`; `~/helixscreen/`; a `helixscreen` line
  in `~/printer_data/moonraker.asvc`; the `[update_manager helixscreen]` block. It installed **no**
  Klipper includes, no Moonraker component, and wrote **no** disabled-services ledger
  (`~/helixscreen/config/.disabled_services` absent).
- HelixScreen ships an uninstaller, `~/helixscreen/scripts/uninstall.sh` (`--force` skips the
  prompt). Per its header and code it: stops HelixScreen, removes its systemd units, removes
  `~/helixscreen` and caches, removes the `[update_manager helixscreen]` block **plus the comment
  block above it** from `moonraker.conf` (backup at `moonraker.conf.bak.helixscreen-uninstall`,
  already gitignored by `*.bak.*`), removes the `moonraker.asvc` line, and may restart Moonraker.
  It **preserves** `~/printer_data/config/helixscreen/` — Step 5 removes that.
- Repo files tracked under `helixscreen/`: `helixscreen.env`, `printer_database.d/README.md`,
  `settings.json`, `themes/nord.json`, `tool_spools.json`. Untracked on disk:
  `user_filaments.json`, `crash_history.json` (gitignored). Pi `git status -s` at brief time showed
  only ` M helixscreen/settings.json`, ` M helixscreen/tool_spools.json`,
  `?? helixscreen/user_filaments.json`.

## Scope

1. Update KlipperScreen-HH to latest `origin/master`.
2. Run HelixScreen's uninstaller; enable KlipperScreen.
3. Remove `helixscreen/` from the repo and disk; drop the HelixScreen `.gitignore` line.
4. Rewrite the `LEGACY` comments in `moonraker.conf` and `KlipperScreen.conf` — KlipperScreen is
   the UI of record again.
5. Cold-boot verification.
6. Bookkeeping: `docs/decisions.md` entry, close + archive `helixscreen-migration.md`, `TODO.md`.

## ⚠️ Out of scope / do not touch

- **`[output_pin caselight]` `scale: 1` and the `LIGHT_ON`/`LIGHT_OFF` overrides in `overrides.cfg`
  stay exactly as they are.** KlipperScreen's Pins panel *also* sends `SET_PIN VALUE` as a 0.0–1.0
  fraction, so reverting to Klippain's `scale: 100` would make "100%" land at 1% again
  (`docs/decisions.md` 2026-09-16, "do not 'fix' this to 100"). The comment above it mentions
  HelixScreen — leave the comment; it is still accurate history and both UIs are named.
- **`mmu_klipperscreen.conf` and the `[include mmu_klipperscreen.conf]` line stay.** They are the
  MMU menus KlipperScreen-HH needs. The 2026-09-16 decision said to delete them "once HelixScreen
  has run a few prints" — that trigger is **void** now; do not act on it. Don't hand-edit
  `mmu_klipperscreen.conf` (Happy Hare's installer owns it; the HH v4 migration may replace it).
- **`/etc/X11/xorg.conf.d/40-dsi-rotate.conf`, `/boot/firmware/config.txt`, `~/pi5-*.sh`** — the
  rotation/KMS setup is validated. Don't touch it, and don't add rotation to `KlipperScreen.conf`
  (it would double-rotate).
- **Don't customize KlipperScreen** (themes, menus, screen-blanking, sort order). The maintainer
  explicitly wants defaults. The auto-generated block at the bottom of `KlipperScreen.conf` is
  KlipperScreen's to write.
- **Don't switch the KlipperScreen origin** to stock KlipperScreen, and don't touch
  `~/KlipperScreen.orig`.
- **Don't uninstall HelixScreen by hand** (`rm -rf`, `systemctl disable` alone). Use its
  uninstaller — it also cleans the asvc entry and caches.
- Unrelated dirty files, if any appear in `git status -s` beyond the `helixscreen/` ones listed
  above, belong to other work: don't stage or revert them.
- Keep-out zones (`CLAUDE.md`) are unaffected — no toolhead motion is involved.

## Pre-resolved decisions

1. **Full uninstall** of HelixScreen (maintainer, 2026-11-08). Not "disable and keep".
2. **`git rm` the repo's `helixscreen/` directory** and delete the untracked files there. Git
   history keeps `settings.json` / `tool_spools.json` / `nord.json` if HelixScreen ever returns
   (last commit containing them: whatever `git log -1 --format=%h -- helixscreen/` prints in
   Step 5 — record it in the decisions entry). `user_filaments.json` was never tracked and is
   lost; acceptable (HelixScreen-only spool data, Spoolman isn't set up). Veto: copy it to
   `~/helixscreen-user_filaments.json.bak` on the Pi before Step 5.
3. **Update KlipperScreen before enabling it**, via Moonraker's update manager (no sudo needed).
4. **The old runbook is closed, not edited further** — append a status line, move it to
   `docs/runbooks/done/`.
5. The open HelixScreen TODO items (dirty `settings.json`, dial in settings, decide long-term,
   laptop instance) are **dropped**, not completed — say so in TODO.md's history.

## Steps

### 0. Preflight (agent)
```
readlink -e config >/dev/null 2>&1 && echo "MOUNT/on-Pi" || echo "WORKSTATION CLONE"
curl -s 'http://192.168.1.240:7125/printer/objects/query?print_stats=state' | python3 -c 'import json,sys;print(json.load(sys.stdin)["result"]["status"]["print_stats"]["state"])'
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git status -s && git log --oneline -1'
ssh ernst@192.168.1.240 'systemctl is-enabled helixscreen KlipperScreen; systemctl is-active helixscreen KlipperScreen'
```
Expect: `MOUNT/on-Pi`; state `standby`, `complete`, `cancelled` or `error` (**stop if `printing` or
`paused`**); git status matching the "Facts" section; `enabled disabled` / `active inactive`. If
the mode is "WORKSTATION CLONE", stop — this runbook is written for mount mode.

### 1. Update KlipperScreen-HH (maintainer clicks, or agent runs with the maintainer's OK)
Maintainer: Mainsail → Machine → Update Manager → **KlipperScreen** → Update.
Or the agent (Moonraker API; try the first, fall back to the second on HTTP 404):
```
curl -s -X POST 'http://192.168.1.240:7125/machine/update/upgrade?name=KlipperScreen'
curl -s -X POST 'http://192.168.1.240:7125/machine/update/client?name=KlipperScreen'
```
Verify:
```
ssh ernst@192.168.1.240 'cd ~/KlipperScreen && git fetch -q origin && git log --oneline -1 && git rev-list --count HEAD..origin/master && git status -s | head'
```
Expect `0` commits behind and a clean tree. The service is still disabled, so nothing appears on
the screen yet — that's correct.

### 2. Snapshot the files the uninstaller will edit (agent)
```
ssh ernst@192.168.1.240 'cat ~/printer_data/moonraker.asvc; grep -n -B6 -A6 "update_manager helixscreen" ~/printer_data/config/moonraker.conf'
```
Keep this output for the Step 3 check.

### 3. Uninstall HelixScreen — **maintainer runs this in their own terminal** (needs sudo)
```
ssh -t ernst@192.168.1.240 'sh ~/helixscreen/scripts/uninstall.sh'
```
Answer the confirmation prompt; enter the sudo password when asked. The screen goes dark/black
when HelixScreen stops — expected. Wait for the maintainer to paste the output or say it finished;
do not assume success.

Then the agent verifies:
```
ssh ernst@192.168.1.240 'ls -d ~/helixscreen 2>&1; ls /etc/systemd/system | grep -i helix; cat ~/printer_data/moonraker.asvc; grep -n -i helix ~/printer_data/config/moonraker.conf; ls ~/printer_data/config/moonraker.conf.bak.* 2>&1'
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git diff moonraker.conf'
```
Expect: `~/helixscreen` gone; no helix units; no `helixscreen` line in the asvc; **no `helix` match
in `moonraker.conf`**; the diff removes only the `[update_manager helixscreen]` block and its
4-line `# HelixScreen Update Manager …` comment. If the diff removed anything else, restore that
part by hand-editing `moonraker.conf` on the mount. If the uninstaller left the block or its
comment behind, delete them by hand on the mount (the block is the last section of the file).
Then remove the backup: `ssh ernst@192.168.1.240 'rm -f ~/printer_data/config/moonraker.conf.bak.helixscreen-uninstall'`.

If `ls /etc/systemd/system | grep -i helix` still lists units, the maintainer runs (own terminal):
```
ssh -t ernst@192.168.1.240 'sudo systemctl disable --now helixscreen helixscreen-update.path; sudo rm -f /etc/systemd/system/helixscreen*.service /etc/systemd/system/helixscreen*.path; sudo systemctl daemon-reload'
```

### 4. Enable KlipperScreen — **maintainer runs this in their own terminal** (needs sudo)
```
ssh -t ernst@192.168.1.240 'sudo systemctl enable KlipperScreen && systemctl is-enabled KlipperScreen'
```
Expect `enabled`. Do **not** `--now` it: HelixScreen unbinds the virtual console at start, and the
reboot in Step 7 gives KlipperScreen a clean tty7. (If the uninstaller already re-enabled it,
this is a harmless no-op.)

### 5. Remove HelixScreen from the repo (agent; edits on the mount, git over SSH)
Record the last commit that held the settings (for the decisions entry), then remove:
```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git log -1 --format="%h %s" -- helixscreen/'
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git rm -r -q --cached helixscreen && rm -rf helixscreen && git status -s'
```
(`--cached` first then `rm -rf`, because `git rm` refuses on the locally-modified `settings.json`
and would leave the untracked files behind.)

Edit `.gitignore` on the mount — delete these two lines (and the blank line above them):
```
# HelixScreen runtime state. The rest of helixscreen/ IS tracked — it is the app config.
helixscreen/crash_history.json
```
Keep the `*.bak.*` rule and its comment — it still catches other installers' backups.

### 6. Rewrite the LEGACY comments (agent, mount)
In `moonraker.conf`, replace the 6-line comment block directly above `[update_manager KlipperScreen]`
(starts `# LEGACY — KlipperScreen is retained only as a fallback`, ends
`# Tracking: docs/runbooks/helixscreen-migration.md`) with:
```
# KlipperScreen, Happy Hare edition — the touchscreen UI in use (HelixScreen was tried
# 2026-08 → 2026-11 and removed; see docs/decisions.md). The HH fork carries the MMU panels;
# its menus come from mmu_klipperscreen.conf, included by KlipperScreen.conf.
```
In `KlipperScreen.conf`, replace the 3 lines starting `# LEGACY — KlipperScreen is a fallback only`
(through `# Tracking: docs/runbooks/helixscreen-migration.md`) with:
```
# Happy Hare's MMU menus for KlipperScreen-HH. Required — do not remove.
```
Leave everything from `#~# --- Do not edit below this line` down untouched.

Check nothing else still references HelixScreen as live:
```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git grep -n -i helix -- ":!docs/runbooks" ":!docs/decisions.md" ":!TODO.md"'
```
Expected remaining hits: the caselight comment in `overrides.cfg` (leave — see Out of scope) and
`docs/mmu_software_hh_vs_afc.md` (a comparison table, leave). Anything else that describes
HelixScreen as the current UI: fix the wording to KlipperScreen.

### 7. Cold-boot verification — **maintainer runs and reports** (nothing printing)
```
ssh -t ernst@192.168.1.240 'sudo systemctl reboot'
```
After ~90 s the agent checks:
```
ssh ernst@192.168.1.240 'systemctl is-active KlipperScreen; systemctl is-enabled KlipperScreen; systemctl list-units --all | grep -i helix; tail -n 20 ~/printer_data/logs/KlipperScreen.log | grep -i -E "error|traceback" || echo no-errors'
curl -s http://192.168.1.240:7125/server/info | python3 -c 'import json,sys;r=json.load(sys.stdin)["result"];print("warnings:",r["warnings"]);print("failed:",r["failed_components"])'
curl -s http://192.168.1.240:7125/machine/update/status | python3 -c 'import json,sys;print(sorted(json.load(sys.stdin)["result"]["version_info"]))'
```
Expect: `active` / `enabled`; no helix units; no errors; Moonraker warnings don't mention
helixscreen; update list contains `KlipperScreen` and **not** `helixscreen`.

Then ask the maintainer to confirm on the physical screen (do not assume — wait for their answer):
- [ ] Image is right side up.
- [ ] Touch lands where the finger is (tap a corner button).
- [ ] **MMU** button on the main menu opens the MMU panel with both gates shown (this is the
      cold-boot bug `94be28f1` fixed).
- [ ] Setting a nozzle or bed temperature works (then set it back to 0).
- [ ] Caselight at 100% from the screen is full brightness, not dim.

### 8. Bookkeeping (agent)
**a. `docs/decisions.md`** — insert at the top (above the newest entry), date = execution date:
```markdown
## <YYYY-MM-DD> — Back to KlipperScreen (Happy Hare edition); HelixScreen uninstalled
**Decision:** KlipperScreen-HH (`moggieuk/KlipperScreen-Happy-Hare-Edition`, `master`) is the
touchscreen UI. HelixScreen was removed with its own uninstaller and `helixscreen/` deleted from
the repo (last version of its settings: `<hash from Step 5>`). Supersedes the 2026-09-16 "both
touchscreen UIs stay registered" entry — its removal trigger for `mmu_klipperscreen.conf` is void.
**Why:** HelixScreen targets larger screens; on Karman's 4.3" 800×480 panel it is too dense, and
everyday actions (e.g. setting temperatures) take more taps. It is more customizable, but the
maintainer wants good defaults, not a UI to tune.
**If you're tempted to migrate again:** a new UI has to be usable at 4.3" out of the box and carry
Happy Hare MMU panels. Rotation is in `/etc/X11/xorg.conf.d/40-dsi-rotate.conf` (X backends only);
the caselight `scale: 1` fix applies to any UI that sends `SET_PIN` fractions.
```
**b. Close the old runbook** — append to the status log of `docs/runbooks/helixscreen-migration.md`:
```
- **<YYYY-MM-DD>** — Closed, superseded by `docs/runbooks/klipperscreen-revert.md`: maintainer chose to return to KlipperScreen-HH; HelixScreen uninstalled. Steps 5–6 abandoned.
```
change its `**Status:**` line to `Closed (superseded) — see docs/runbooks/klipperscreen-revert.md.`,
then `ssh ernst@192.168.1.240 'cd ~/printer_data/config && git mv docs/runbooks/helixscreen-migration.md docs/runbooks/done/'`.
Fix the link in `TODO.md` and anywhere else: `git grep -n "runbooks/helixscreen-migration"`.
**c. `TODO.md`** — tick this runbook's task in `## Touchscreen UI`; collapse the section's
completed items into a one-line note in the `# 📖 History` area (closed + dropped HelixScreen
tasks); update roadmap item 6 to `[x]` with "reverted to KlipperScreen-HH (<date>)".
**d. This runbook** — tick Verification, append the status log, move it to `docs/runbooks/done/`.

## Verification (proves the objective)

- [x] KlipperScreen-HH is `0` commits behind `origin/master` (Step 1 command).
- [x] After a **cold boot**: `KlipperScreen` active + enabled; no `helixscreen*` units; `~/helixscreen` absent.
- [x] Moonraker: no `helixscreen` update entry, no helixscreen warning; `KlipperScreen` entry present.
- [x] Maintainer confirmed on the screen: right side up, touch aligned, MMU panel works, temperature set works, caselight full brightness.
- [x] `git ls-files helixscreen/` (over SSH) prints nothing; `git status -s` clean after the commit.
- [x] `docs/decisions.md` entry written; old runbook archived; TODO.md updated.

## Commit guidance

One commit is fine — it is one change of UI. Stage explicitly (never `git add -A`):
```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git add -A helixscreen .gitignore moonraker.conf KlipperScreen.conf docs/decisions.md docs/runbooks TODO.md && git status -s'
```
(`git add -A <paths>` limited to these paths records the deletions and the runbook move.) Check the
status shows nothing outside those paths, then propose to the maintainer:
`feat: revert the touchscreen to klipperscreen happy hare edition and remove helixscreen`
The maintainer commits/pushes unless they ask the agent to (`CLAUDE.md`, Git conventions).

## Status log

- **2026-11-08** — Brief written (architecture session). Nothing executed.
- **2026-11-08** — Executed Steps 0–6. KlipperScreen-HH updated via Moonraker API to `1ad01a13`
  (0 behind). Uninstaller gotchas: it refuses to run from inside `~/helixscreen`, and only runs
  `main` when its filename is literally `uninstall.sh` — copy it to a temp dir *keeping the name*
  (`d=$(mktemp -d) && cp …/uninstall.sh "$d/uninstall.sh" && sh "$d/uninstall.sh"`). It removed
  `~/helixscreen`, `helixscreen.service` and the moonraker.conf block (+5-line comment, nothing
  else), and re-enabled **and started** KlipperScreen itself (Step 4 became a no-op). It left the
  `helixscreen` line in `moonraker.asvc` (removed by agent) and `helixscreen-update.{path,service}`
  (removed by maintainer with sudo; confirmed `no-helix-units`). Last commit holding HelixScreen settings: `9a24dc1`.
- **2026-11-08** — Step 7 deviation: after the cold boot KlipperScreen was **upside down** — the
  panel had been physically remounted during the HelixScreen period, so the "rotation already in
  place" fact above was stale. With the maintainer's OK, `/etc/X11/xorg.conf.d/40-dsi-rotate.conf`
  moved to `/etc/X11/40-dsi-rotate.conf.disabled` (no X rotation now), rebooted again. Screen was
  also dim: systemd-backlight had restored a saved **12/255**; set to 255 via
  `/sys/class/backlight/11-0045/brightness`. Post-boot checks all clean (KS active/enabled, no helix
  units, no Moonraker warnings, KlipperScreen in update list, helixscreen not). Maintainer confirmed
  on screen: right side up, touch aligned, MMU panel both gates, temp set, caselight full,
  brightness normal. Step 8 bookkeeping done; awaiting maintainer commit.
