---
name: setup
description: One-time bootstrap for a new printer config repo - interviews the maintainer about the machine, its modifications, how Claude reaches it, and its physical keep-out zones, then writes CLAUDE.md and seeds TODO.md. Use when the user says /setup, when CLAUDE.md still contains {{PLACEHOLDER}} markers, or when starting the workflow on a printer for the first time.
---

# Characterise a new printer

Run **once** per machine. You are turning an unfilled template into a real `CLAUDE.md` that every
future session depends on. Everything you get wrong or leave vague here gets rediscovered — or
guessed at — for the lifetime of the repo.

**Do not change any printer config during this skill.** The only files you write are `CLAUDE.md`,
`TODO.md`, `docs/decisions.md`, and `NOTES.md`.

## Ground rules

- **Inspect before asking.** Anything you can read from the repo or the machine, read. Every
  question you avoid asking is goodwill you spend on the questions that matter.
- **Ask about physical reality; derive everything else.** Geometry, what's actually installed,
  what the maintainer has modified — you cannot know these. File layout, board types and pin
  assignments are usually readable.
- **Batch questions.** Use `AskUserQuestion` for discrete choices; ask open questions in grouped
  rounds of related items. Do not trickle out one question at a time.
- **"I don't know yet" is a valid answer** and must be recorded as such. An honest
  *"not yet surveyed"* is far safer than a confident blank, especially for keep-out zones.

---

## 1. Look around first

Before asking anything:

```
ls -la
cat *.cfg 2>/dev/null | head -100        # or the equivalent for this firmware
git log --oneline -15 2>/dev/null
git status -s 2>/dev/null
```

Work out what you can, and note what you cannot:
- Is this a git repo? Is it the live config, or a copy?
- What config format and firmware family is this (Klipper, RepRapFirmware, Marlin, a vendor fork)?
- Which files look hand-maintained versus generated, vendor-supplied, or autosaved?
- Are there existing `CLAUDE.md` / `TODO.md` / docs worth merging rather than overwriting?

If a previous `CLAUDE.md` or `TODO.md` exists, **read it fully and preserve what's still true.**
Merging beats clobbering.

---

## 2. Round 1 — identity and access *(the part that blocks everything else)*

Ask together:

1. **What is this machine?** Make, model, name you call it, bed size, enclosed or open.
2. **What firmware / stack?** Stock vendor firmware, a vendor fork, mainline Klipper or similar,
   any config framework layered on top, and any plugins or add-on modules that carry **their own
   updaters** — those overwrite files and are a recurring source of surprise.
3. **What interface do you use?** Vendor app/screen, Mainsail, Fluidd, OctoPrint, something else.
4. **How does an edit in this repo reach the printer?** This is the single most important answer
   in the whole interview. Pin down concretely:
   - Is this working copy the **live config**, a **network mount** of it, or a **clone** that must
     be deployed?
   - If a clone: exactly what deploys it? (git pull on the machine, a sync script, upload through
     a web UI, SD card…)
   - Can you reach the machine **read-only** for inspection — SSH, an HTTP API? Give the exact
     command that works.
   - Is anything **forbidden**? (writing over SSH, restarting mid-print, editing vendor files.)
5. **Is the machine locked down?** Many consumer CoreXY printers ship a modified Klipper with no
   SSH and a read-only or vendor-managed config. If so, establish early what can actually be
   changed and how — it constrains every runbook you'll ever write here.

Then **verify the access model** rather than trusting the description: try the read-only command
they gave you and report whether it worked. An access model that doesn't actually work is a trap
for every future session.

---

## 3. Round 2 — hardware

Ask what you could not read from the config:

- **Toolhead:** hotend, extruder, nozzle size/material, any toolhead board.
- **Probe / bed levelling:** type, and whether it's nozzle-contact, inductive, optical, eddy,
  strain-gauge, or manual.
- **Bed:** heater type, build surface, max temperature in practice.
- **Cooling / chamber:** part fan, hotend fan, chamber heater or fans, chamber sensor and whether
  it reads true.
- **Filament handling:** single, multi-material, AMS/MMU/toolchanger, runout sensors, cutter.
- **Accelerometer / input shaping** — present, and where.
- **Common materials** and their typical temperatures — this drives thermal behaviour throughout.

For each: **what's stock and what's modified.** The modifications are what a fresh session gets
wrong.

---

## 4. Round 3 — ⚠️ physical keep-out zones *(highest value; do not rush)*

Frame it plainly for the maintainer: *the firmware has no obstacle model — nothing stops a crash,
so these have to live in writing.*

Walk through the candidates rather than asking an open question, because people forget the
obvious ones:

- **Purge / poop chute / waste bin** — where, and at what heights is it in the way?
- **Nozzle wipe / brush** — where, and must it be approached from a particular direction?
- **Park / home positions** — and anything mounted near them.
- **Toolhead protrusions** — cutters, probes, fans or cable exits that stick out and collide with
  frame members at certain coordinates, *at any Z*. These are the dangerous ones because they
  apply to every move forever.
- **Bed clips, camera, lighting, door, filament path** — anything intruding into the motion volume.
- **Gantry-mounted features** — if a feature is mounted to the gantry, its Z tracks the toolhead,
  so only XY engages it. Note this explicitly where it applies; it inverts the usual intuition.
- **Any minimum-Z floor** already enforced anywhere in the config, and why.

For each zone, capture the **region (x/y/z bounds), what is physically there, and whether it is
height-dependent or permanent**.

If the maintainer hasn't surveyed these, record **"not yet surveyed"** explicitly and add a TODO
to do it. Never leave the section silently empty — an empty list reads as "no hazards".

---

## 5. Round 4 — working agreements and what's next

- **Commit conventions** — style, and whether the maintainer runs their own commits/pushes or
  wants you to.
- **Validation** — do any offline checks exist (macro renderer, motion simulator, linter, tests)?
  If not, say so plainly in `CLAUDE.md`; it's a real gap and worth a TODO.
- **Near-term work** — what do they want to do with this machine in the next few weeks? Capture
  enough per item to become a `TODO.md` task: what, why, and what "done" looks like.
- **Known annoyances** — anything currently broken, flaky, or irritating. These become debug
  sessions later and are much cheaper to note now.

---

## 6. Write the files

**`CLAUDE.md`** — fill every `{{PLACEHOLDER}}`, delete the "unfilled template" warning block at
the top, and delete the `<!-- -->` guidance comments once each section is written. Then verify:

```
grep -n '{{\|UNFILLED TEMPLATE' CLAUDE.md     # must return nothing
```

Rules while writing it:
- **Facts and their consequences**, not prose. "Chamber sensor reads warm — treat as a cap, not a
  setpoint" beats "there is a chamber sensor".
- **Say what is unknown**, explicitly, rather than omitting it.
- Keep it dense. This file is loaded into every session; every line should earn its place.

**`TODO.md`** — seed from Round 4. Group into `##` sections by subsystem or theme, put the
immediate items under **▶ Next up**, keep everything actionable above the `# 📖 History` divider.

**`docs/decisions.md`** — add entries for any non-obvious choice the maintainer explained during
the interview ("X is set to Y because the obvious Z doesn't work here"). These are pure gold and
they surface naturally in conversation — capture them now or lose them.

**`NOTES.md`** — drop in any raw measurements mentioned in passing.

---

## 7. Hand off

Report back in ≤10 lines: what the machine is, how edits reach it, how many keep-out zones were
captured (and whether any remain unsurveyed), and what's queued in `TODO.md`.

Then tell the maintainer:
- Review `CLAUDE.md` — it is the context every future session starts from, so errors there
  propagate.
- Commit it.
- If hooks are in use, open `/hooks` once so they activate.
- Start real work with **`/start`**, and plan bigger objectives with **`/brief`**.

Do **not** roll straight into executing work. Setup is its own session.
