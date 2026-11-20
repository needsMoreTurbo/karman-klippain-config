# Runbook — first PA web tool campaign: ABS on the CHT, 7–21 mm³/s × 2500–15000 mm/s²

**Objective:** use the PA web tool (`http://192.168.1.240/karman-pa/`) to build an adaptive-PA model
for ABS on the 0.4 CHT BiMetal at 265 °C, over the ABS print envelope including its low-flow end.
**"Done":** the tool reports **"tuned"** (max spot-check score ≤ 0.0015 and the last two spot checks
within 2σ of their blind predictions). It exports an Orca block plus a campaign JSON, and the
result is recorded in `docs/decisions.md`. This also proves the prototype end to end; any bugs
found become td issues.
**Issue:** td-d0324c · **Epic:** td-ee87cd · **Created:** 2026-11-19
**Prerequisites:**
- **td-6321c3 closed** (`docs/runbooks/pa-web-tool-prototype.md`): tool deployed, served, and one
  real sweep verified.
- ABS on gate 0 (Polymaker ABS Galaxy Black). Use the same spool for every run.
- The 0.4 CHT BiMetal installed.
- Printer idle. **The maintainer at the printer for about 75 minutes** (6 baseline runs plus up to
  6 spot checks, about 4.5 minutes each, plus one cold soak), clearing the blob between runs.
- Exhaust running.

Reference: `docs/runbooks/pa-web-tool-prototype.md`, the *Pre-resolved decisions* section, is the
tool's behaviour of record (model, prior, DOE, acceptance, stopping rule). Print envelope:
`/home/kyle/projects/auto-pa-tuning/docs/research/08-phase1-measurements.md` §1.

Progress is logged to the issue (`td log`), not here. This file is the plan.

## Scope

Campaign set up in the tool → baseline DOE (6 runs) → fit → spot checks until "tuned" →
export → recorded.

## ⚠️ Out of scope — do not touch

- **The tool's model, prior and thresholds.** This is the first campaign. If a rule looks wrong,
  `td create` it and finish the campaign as specified. Changing rules mid-campaign makes the result
  uninterpretable.
- **Everything listed out of scope in `docs/runbooks/pa-web-tool-prototype.md`**: `bdpressure.cfg`
  and `KARMAN_PA_CALIBRATE`, `~/bd_pressure`, never auto-apply, `physics/`, KAPAT, Mainsail/nginx,
  Moonraker config, and `[extruder]` PA settings.
- **Orca presets.** The export is pasted into a *copied* preset under td-746307, not here.
- **Beacon, MMU / Happy Hare, Blobifier, purge and `START_PRINT` config.**

## ⚠️ Hazards in play

Copied from the `CLAUDE.md` hazard register (the same set as the prototype runbook):

- **Front-left, x<10 / y<17, at ANY Z** — the Filamatrix cutter arm on the toolhead strikes the
  front-left XY idler. Permanent toolhead geometry. **Always-on**: applies to every move.
- **The y_max feature row** (tray ~x2–17, shaker x4, rest x45, brush x53–88) — must be entered in +Y
  through a **clear lane (15<x<40, or x>95)**, then slid in X. Never approach a feature head-on.
  **Always-on** near y_max. *Here: `G28` before the first run. The tool refuses to run when homed
  at Y>300.*
- **Umbilical + PTFE above the gantry** — they limit how high Z can safely go, and the umbilical
  is the only toolhead protrusion besides the cutter arm. The clearance has **not been measured**,
  so treat moves near Z max as unsafe until it is. **Conditional**: high Z. *Here: Z80.*
- **A forgotten preheat keeps heating** (maintainer-observed). `[idle_timeout]` in `overrides.cfg`
  should `TURN_OFF_HEATERS` after 1800 s, so something is stopping it; the cause hasn't been
  diagnosed. **Always-on** until fixed — never leave heaters on assuming the timeout will catch it.
  *Here: the tool sends `M104 S0` when a queue ends. Step 5 turns everything off.*
- **Unattended ABS/ASA relies on the external exhaust duct** (slight negative pressure, vented
  outside). Klipper doesn't control it. **Conditional**: ABS/ASA prints. *Here: about 12 purges of
  ~480 mm³ in air.*
- **MMU load/swap commands outside a print can run as cold as ~200 °C** — too cold for ABS in this
  UHF melt zone (grinds or jams). Preheat to the gate's material temperature first.
  **Conditional**: bench MMU operations. *Here: `M109 S265` before `SWAP TOOL=0`.*
- **Restarting Klipper mid-print** kills the print. **Conditional**: while printing. Nothing here restarts.
- **`~/bd_pressure` carries three local patches.** **Always-on**.
- **Beacon contact homing refuses above 180 °C.** Home before heating.
- **The BDPressure port is shared with KAPAT.** No KAPAT sweeps during the campaign. Keep the KAPAT
  page closed: its tab also sends `M104 S0` after a sweep.
- **td hangs the SSHFS mount.** Run td as
  `GIT_DIR=/nonexistent GIT_CEILING_DIRECTORIES=/home timeout 20 td ...` from the repo root.

## Pre-resolved decisions

- **Envelope: flow 7–21 mm³/s, accel 2500–15000 mm/s²**, from the measured ABS print envelope
  (outer wall 7.3 @ 5000 up to sparse infill 20.9 @ 15000). 7 is the requested **low-flow
  condition**. The tool clips the 7-mm³/s corner to about 5000 mm/s² (ramp ≥ 1.0 sample).
- **Label `ABS_CHT`, temperature 265 °C** (265 on the CHT matches 275 on hardened steel).
- **Low-flow fallback:** if a 7-mm³/s run is rejected twice (no result, or fresh ratio < 0.8),
  change the campaign's flow minimum to 8.5, let the tool re-plan that corner, and log it. If 8.5
  also fails twice, use 10, which is proven by the steel data.
- **The n prior stays at 0.653 ± 0.10** even though it came from the steel nozzle. Whether the
  CHT data moves n off the prior is itself the finding. The tool shows the posterior σ.

---

## Step 1 — Prepare the printer *(human)*

From Mainsail:
```
G28
M109 S265
SWAP TOOL=0
```
Skip the `SWAP` if ABS is already at the toolhead. Close any KAPAT browser tab.

## Step 2 — Set up the campaign *(human, browser; model checks)*

On `http://192.168.1.240/karman-pa/`: create a campaign with label `ABS_CHT`, 265 °C, flow 7–21,
accel 2500–15000. Expected plan: 6 points, centre ≈ 12.1 mm³/s @ 6124 first and last, and the
(7, 15000) corner clipped to accel ≈ 4990. ETA about 31 minutes.

Model: start a console Monitor, as in the prototype runbook Step 8, to cross-check each result
against the console independently of the page. `td log` the plan.

## Step 3 — Baseline DOE *(human launches; model checks each run)*

Click **Launch baseline DOE**. Between runs: clear the blob, then click **blob cleared — continue**.

After each run, the model checks:
- The page's stored value equals the console's `Calc the best Pressure Advance` line.
- The run was accepted or rejected for the right reason.

Then `td log` one line per run: flow, accel, K, σ, fresh/skipped.

**Gates:**
- **Centre drift:** the two centre runs differ by > 0.008 → the tool stops. Record both values and
  **stop and escalate**. A thermal or mechanical drift invalidates the rest of the campaign.
- **Low-flow corner:** apply the fallback in Pre-resolved decisions.
- **Any `!!` error, or a USB `sensor offline`:** check `ssh ernst@192.168.1.240 'ls /dev/serial/by-id/'`
  (decisions 2026-09-03). **Stop and escalate.**

## Step 4 — Fit and spot checks *(model reads; human approves each)*

After the baseline, the Model panel shows C, n (posterior σ next to the prior's 0.10) and χ²/dof.
`td log` them.

**Gate: the fit.** χ²/dof > 4 → do not spot-check. Record the residuals and **stop and escalate**:
the law does not describe this nozzle. If the empirical model fits where the law does not, say
which axis.

Spot-check loop, one at a time:
1. The tool proposes a point and stores its blind prediction. The model `td log`s the point and
   the prediction **before** the human approves.
2. Human: **Approve and run**, then clear the blob afterwards.
3. The model checks the page against the console and logs the miss in σ units.

The tool reports **"tuned"** → carry on. It **stops and flags** (a miss > 3σ, two consecutive misses
> 2σ, or 6 spot checks without "tuned") → record the state and escalate. Do not loosen thresholds
to get to "tuned".

## Step 5 — Export and shut down *(human, then model)*

Human: on the page, **Copy Orca block** and **Download JSON**, then from Mainsail:
```
TURN_OFF_HEATERS
M84
```
Remove the blob.

Model: save the downloaded JSON to
`/home/kyle/projects/auto-pa-tuning/data/pa-web/2026-11-19_ABS_CHT.json` (use the actual date), and
the Orca block beside it as `.orca.txt`.

---

## Verification

- [ ] 6 baseline runs made, and every page value matches its console line. *(verified in reality)*
- [ ] The centre repeat agrees within 0.008. *(verified in reality)*
- [ ] Law fit χ²/dof ≤ 4. *(verified in reality)*
- [ ] The tool reached **"tuned"**: max score ≤ 0.0015 and the last two spot checks within 2σ of
      predictions stored before they ran. *(verified in reality)*
- [ ] The Orca block and campaign JSON are saved in `auto-pa-tuning/data/pa-web/`, with
      extrapolated cells listed. *(validated in a proxy)*
- [ ] **Nothing regressed:** `[extruder] pressure_advance` reads 0.032
      (`curl -s 'http://192.168.1.240:7125/printer/objects/query?extruder=pressure_advance'`).
      `physics/` is unchanged. The Mainsail and KAPAT pages load.
- [ ] Heaters off.

## When it is done

- **`docs/decisions.md`**: "ABS adaptive PA on the CHT (PA web tool, first campaign)". Record C
  and n with σ (and how far n moved from the 0.653 prior), χ²/dof, the run count, the blind
  spot-check misses, whether the low-flow fallback was needed, the Orca block, and the extrapolated
  cells.
- **td**:
  - `td log td-746307` with the Orca block path. Its Step 6b (paste into a copied Orca preset and
    validate with a print) now has an input.
  - `td create` each tool bug or rule change found, as a child of the epic (`--parent td-ee87cd`).
- **Commits**:
  - `auto-pa-tuning` (local): `data: abs cht pa web campaign` for `data/pa-web/`.
  - Karman, over SSH on the Pi, after asking: `docs: record the first pa web campaign` —
    `docs/decisions.md`, this runbook.
