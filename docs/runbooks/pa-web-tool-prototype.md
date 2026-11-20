# Runbook — PA web tool prototype: DOE, fit and spot checks around KARMAN_PA_CALIBRATE

**Objective:** a working first version of a browser tool at `http://192.168.1.240/karman-pa/`.
The user enters a filament label, temperature, flow range and acceleration range. The tool plans a
baseline DOE of `KARMAN_PA_CALIBRATE` sweeps, runs it, fits the PA law, and then proposes spot
checks one at a time, each needing the user's approval, until the model is well tuned. It exports an
Orca adaptive-PA block. **"Done" for this runbook:** the offline tests pass (including
reproducing the existing ABS law), the page is served and connected, and **one real sweep launched
from the page** is run, parsed and stored, with the page's value matching the console's.
Running a full campaign is the next runbook (`docs/runbooks/pa-web-tool-first-campaign.md`).
**Issue:** td-6321c3 · **Epic:** td-ee87cd · **Created:** 2026-11-19
**Prerequisites:**
- The BDPressure working with `[include bdpressure.cfg]` and `KARMAN_PA_CALIBRATE` (true since
  2026-08-12; re-proven 2026-11-19: 0.0345 ± 0.0074 at 25 mm³/s / 5000 / 265 °C).
- Node ≥ 20 on the workstation for the tests (`node --version`; v24 on 2026-11-19).
- The maintainer for Step 6 (one `sudo` nginx edit) and Step 8 (one real sweep, about 10 minutes
  at the printer, with ABS loaded).
- Printer idle for Step 8.

Reference, link don't re-read everything:
- `docs/pa_physics.md` §5.1 (zero-crossing method and its refusals), §5.2 (trust repeat scatter;
  the fit's own error is about 2× conservative), §5.3 (the law), §4.1 (ramp-sample check).
- `bdpressure.cfg`: `PA_CALIBRATE` and `KARMAN_PA_CALIBRATE`, which give the pattern speeds and parameters.
- `physics/pa_sweeps.json` (13 valid ABS rows on the **steel** nozzle) and `physics/pa_law.json`.
- Moonraker API: https://moonraker.readthedocs.io/en/latest/web_api/ (websocket JSON-RPC,
  `printer.gcode.script`, `notify_gcode_response`, `server.gcode_store`, `server.database.*`,
  `printer.objects.query`).
- How KAPAT's web page is served (a pattern to copy): `location /kapat/` in
  `/etc/nginx/sites-enabled/mainsail` on the Pi.

Progress is logged to the issue (`td log`), not here. This file is the plan.

## Scope

Model + DOE + parser as tested JS modules → single-page UI over Moonraker → deployed and served at
`/karman-pa/` → one real sweep from the page → verified.

## ⚠️ Out of scope — do not touch

- **`bdpressure.cfg` as a whole**: `[bdpressure bd_pa]`, the patched `PA_CALIBRATE`/`PA_E` macros
  (flow-scaled geometry, decisions 2026-08-13), and `KARMAN_PA_CALIBRATE` with its soak defaults
  (`soak_cold: 240`, `soak_hot: 30`, `prime_mm: 40`, measured in decisions 2026-08-12). The tool
  **calls** `KARMAN_PA_CALIBRATE`; it never changes it. Its `action_respond_info` "done" line
  prints at the *start* (template render time). Do not "fix" that here; the tool ignores it.
- **`~/bd_pressure` and `[update_manager bd_pressure]` (commented out).** The three local patches
  produce the result lines this tool parses. A `git pull` silently reverts them.
- **`apply_result` off and never auto-apply.** The tool records PA values and never sends
  `SET_PRESSURE_ADVANCE` (decisions 2026-08-13).
- **`physics/pa_law.json`, `physics/pa_sweeps.json`, `physics/*.py`.** Read them as test fixtures
  (copy the rows into the test folder); never edit them. The ABS law (`n` 0.653, `C` 0.1032) is the
  steel-nozzle reference.
- **KAPAT, `kapat.cfg`, `bdp_load_cell`, `~/KAPAT`, `/kapat/`, `settings.json`.** KAPAT stays for
  auto-PA experiments. This tool shares the BDPressure port with it, and the tool's guard (Step 3)
  refuses to run while KAPAT is active. That is the only interaction.
- **`~/mainsail` and Mainsail's nginx `location /`.** Add a new `location`; touch nothing else.
- **`[extruder] pressure_advance: 0.032`, `pressure_advance_smooth_time: 0.040`, Orca presets.**
  The tool exports a block. Applying it belongs to td-746307.
- **Moonraker config (`moonraker.conf`, `[authorization]`).** The KAPAT page already proved the
  browser can reach `:7125` from the LAN. If this page cannot connect, stop and escalate rather than
  editing `cors_domains`/`trusted_clients`.
- **Beacon, MMU / Happy Hare, Blobifier, purge and `START_PRINT` config.** Unrelated and validated.

## ⚠️ Hazards in play

Copied from the `CLAUDE.md` hazard register:

- **Front-left, x<10 / y<17, at ANY Z** — the Filamatrix cutter arm on the toolhead strikes the
  front-left XY idler. Permanent toolhead geometry. **Always-on**: applies to every move. *Here:
  the tool sends only `KARMAN_PA_CALIBRATE` (and `M104 S0`), which moves to its validated purge
  position 175/40/80. The tool never sends its own moves.*
- **The y_max feature row** (tray ~x2–17, shaker x4, rest x45, brush x53–88) — must be entered in +Y
  through a **clear lane (15<x<40, or x>95)**, then slid in X. Never approach a feature head-on.
  **Always-on** near y_max. *Here: `KARMAN_PA_CALIBRATE` moves Z first, then straight XY to
  175/40. The tool refuses to start a run while the toolhead is homed at Y>300 (Step 3 guard).*
- **Umbilical + PTFE above the gantry** — they limit how high Z can safely go, and the umbilical
  is the only toolhead protrusion besides the cutter arm. The clearance has **not been measured**,
  so treat moves near Z max as unsafe until it is. **Conditional**: high Z. *Here: Z80, as since August.*
- **A forgotten preheat keeps heating** (maintainer-observed). `[idle_timeout]` in `overrides.cfg`
  should `TURN_OFF_HEATERS` after 1800 s, so something is stopping it; the cause hasn't been
  diagnosed. **Always-on** until fixed — never leave heaters on assuming the timeout will catch it.
  *Here: the tool sends `M104 S0` (nozzle only; the bed may be in use for something else) when a
  queue finishes or is stopped.*
- **Unattended ABS/ASA relies on the external exhaust duct** (slight negative pressure, vented
  outside). Klipper doesn't control it. **Conditional**: ABS/ASA prints. *Here: each sweep purges
  about 480 mm³ in air. The tool requires a human click between runs (Pre-resolved decisions).*
- **Restarting Klipper mid-print** (`FIRMWARE_RESTART`, a service restart) kills the print. Check
  `print_stats.state` first. **Conditional**: while printing. *Here: nothing in this runbook
  restarts Klipper. The tool refuses to run while printing.*
- **MMU load/swap commands outside a print can run as cold as ~200 °C** — too cold for ABS in this
  UHF melt zone. **Conditional**: bench MMU operations. *Here: Step 8, `M109 S265` before `SWAP`.*
- **`~/bd_pressure` carries three local patches.** Any `git pull` there silently reverts them and
  the PA sweeps return wrong answers. **Always-on**.
- **Beacon contact homing refuses above 180 °C** (warning in `KARMAN_PA_CALIBRATE`). Home cold.
- **The BDPressure port is shared with KAPAT's `bdp_load_cell`.** Never run `KARMAN_PA_CALIBRATE`
  and a KAPAT sweep at the same time (`overrides.cfg` comment, decisions 2026-11-19).
- **td hangs the SSHFS mount** (CLAUDE.md, td section). Run td from the repo root as
  `GIT_DIR=/nonexistent GIT_CEILING_DIRECTORIES=/home timeout 20 td ...`, never in the background.

## Pre-resolved decisions

Each is a default the maintainer can veto in one line.

- **Architecture: a static single-page app with no build step, plain ES modules, and no
  printer-side code.** It talks to Moonraker over the websocket (JSON-RPC) and keeps campaign state
  in **Moonraker's database** (namespace `karman_pa`, one key per campaign), so a reload or a second
  browser resumes where it left off. Nothing runs in Klippy, so no host restart and no
  shutdown risk (decisions 2026-09-03). Charts are inline SVG, with no libraries.
- **Code lives in `/home/kyle/projects/auto-pa-tuning/web/karman-pa/`** (that repo's decision 8:
  code there, deployed by `rsync`). It is deployed to `~/karman-pa-web/` on the Pi and served by
  nginx at `/karman-pa/`, the same pattern as KAPAT.
- **Result source: the console.** The patched module prints the result only as text. The tool
  sends the run with JSON-RPC `printer.gcode.script` (the reply arrives when the macro finishes)
  and collects the `notify_gcode_response` lines in between. If the socket drops, it recovers the
  lines from `server.gcode_store` by timestamp. The lines it parses (exact text from
  `~/klipper/klippy/extras/bdpressure.py`):
  - `Calc the best Pressure Advance: <pa> +/- <sigma>  [zero crossing of Hr-Hl; slope <b> +/- <sb> counts/PA, scatter <sd>, <used> of <total> points, swept <lo> to <hi>]`
  - `Calc the best Pressure Advance: NO RESULT — <why>` (any text after the dash)
  - `No PA calibration data or number is <=5`
  - `bd_pa reads: <fresh> fresh, <skipped> skipped (no new measurement) of <total> steps`
  - any line starting `!!` (a Klipper error) fails the run.
- **The model is the existing law, made explicit:**
  `K = C · Qpeak^(n−1)`, with `Qpeak = A_fil · E_per_mm · (v_high + K · accel)`,
  `A_fil = 2.405`, `E_per_mm = 0.046`, `v_high = 537 · MAX_VOLUMETRIC / 60` mm/s. K appears on
  both sides, so a prediction iterates `K ← C·Qpeak(K)^(n−1)` from 0.03 until it changes by less
  than 1e-9. This was never written down; it was reverse-engineered on 2026-11-19, and it
  reproduces all 12 cells of `pa_law.json`'s `orca_paste_block` from C = 0.1032, n = 0.653.
  - **Fit:** weighted least squares in log space, `ln K = ln C + (n−1)·ln Qpeak(measured K)`, with
    weights `(K/σ)²`.
  - **A Gaussian prior on n: mean 0.653, σ 0.10**, entered as one extra pseudo-observation. The
    vendor sweeps barely constrain n: a free fit of the 13 steel rows gives 0.745 ± 0.229. Without a
    prior, extrapolation is meaningless. The UI shows the posterior σ of n next to the prior's 0.10,
    so it is visible whether the data or the prior is deciding.
  - **σ per run = max(reported σ / 2, 0.0020)**, because the fit's own error is about 2×
    conservative (§5.2). Parameter covariance is scaled by max(1, χ²/dof).
  - **A second, empirical model as a cross-check:** `ln K = b0 + b1·ln(flow) + b2·ln(accel)`,
    weighted, needing ≥ 4 runs. It is not exported. It only scores where the law might be wrong.
- **Feasibility, applied to every planned point:**
  - `ramp_samples = (537 − 51)·flow/60 / accel × 88` must be **≥ 1.0**. That is the lowest any
    valid existing sweep reached (10 mm³/s @ 6000 = 1.19). Between 1.0 and 2.0 is shown amber,
    per §4.1's "below ~2 is unmeasurable".
  - Flow 3–50 mm³/s (`max_velocity` 500 caps `v_high` near 55).
  - Accel 500–21000 mm/s² (`max_accel` 21000).
- **Baseline DOE: 6 runs.** Centre (geometric mean of the flow and accel ranges) → the 4 corners of
  the box, each corner clipped into the feasible region (lower the accel until ramp ≥ 1.0) → centre
  again. Corners are run low-flow first. The two centre runs check drift: if they differ by more
  than 0.008, the UI flags "drift", and the campaign stops for a decision.
- **Run acceptance:** a result line is present, `fresh/(fresh+skipped) ≥ 0.8`, and points used ≥ 10.
  Anything else is stored as rejected, with the reason, and the UI offers one re-run.
- **Spot checks:** candidates are a 7 × 7 log-spaced grid over the feasible box, excluding any
  within 0.15 (in log units, both axes) of a run already made. The score is
  `sqrt(σ_law_pred² + (K_law − K_emp)²)`, and the top-scoring point is proposed. Before the user
  approves it, its **law prediction ± σ is stored as a blind prediction**. After the run, the UI
  shows `|measured − predicted| / sqrt(σ_pred² + σ_run²)`.
  - **Tuned** = max score over the grid ≤ 0.0015 **and** the last two spot checks are within 2.
  - **Stop and flag:** a miss over 3, two consecutive misses over 2, or 6 spot checks without
    reaching "tuned".
- **Human in the loop:**
  - "Launch baseline DOE" is one click that approves the 6 planned runs. Between every two runs,
    the UI waits for **one click, "blob cleared — continue"**, which also confirms someone is
    present for the ABS purge. Auto-continue is a later iteration.
  - Each spot check needs its own "Approve and run" click.
  - "Stop after this run" finishes the current sweep and stops. A sweep cannot be cancelled
    mid-way, except by Mainsail's emergency stop.
  - When the queue finishes or stops, the tool sends `M104 S0`.
- **Pre-run guard** (queried before every run; any failure blocks the run and says why):
  - `print_stats.state` is not `printing` or `paused`.
  - `webhooks.state == "ready"`.
  - `filament_switch_sensor toolhead_sensor.filament_detected` is true.
  - If the objects exist: `kapat.activity.state == "idle"` and `bdp_load_cell.streaming == false`.
  - Not homed at Y > 300.
- **The run command:** `KARMAN_PA_CALIBRATE NOZZLE_TEMP=<T> MAX_VOLUMETRIC=<flow> ACC_WALL=<accel>`.
  Everything else stays at the macro's defaults (`GEOM_SCALE` = flow/25, `HOME_AFTER=1`).
- **Orca export:**
  - Flows: the campaign's flow min/max plus 3 log-spaced flows between them. Accels: its accel
    min/max plus 1 between.
  - Each line `"%.4f,%.2f,%d"` (K, flow, accel), K from the **law**, floored at 0.005 (Kalico
    flushes step generation when PA crosses 0).
  - Cells outside the convex hull of measured (flow, accel) points are listed below the block as
    "extrapolated".
  - A "Download JSON" button exports the campaign: runs with raw console lines, fits, and blind
    predictions.
- **UI layout: one page, four panels.**
  - *Setup:* label, temperature, flow min/max, accel min/max, and a feasibility map with the planned
    points and ETA (4.5 min/run hot, plus 4 min for the first cold soak).
  - *Run queue:* status, live console lines, the blob-cleared button.
  - *Model:* C, n with σ (prior σ shown), χ²/dof, residual list, and a K-vs-Qpeak SVG plot.
  - *Spot check & export.*

---

## Step 1 — Model, DOE and parser modules with tests *(model, workstation)*

In `/home/kyle/projects/auto-pa-tuning/web/karman-pa/`, create:
- `parse.js`: `parseRunLines(lines) → {status:'ok'|'no_result'|'error', pa, sigma, slope, slopeSigma, scatter, used, total, sweptLo, sweptHi, fresh, skipped, reads, reason}`.
- `model.js`: `qpeak`, `predict(flow, accel, C, n)`, `fitLaw(points, {nPrior:{mean,sigma}|null, nFixed:null|number})`
  → `{C, n, cov, chi2, dof, residuals}`, `predictSigma(flow, accel, fit)` (numeric derivative +
  covariance), `fitEmpirical(points)`, `orcaBlock(fit, flows, accels)`, `rampSamples(flow, accel)`.
- `doe.js`: `baselinePlan(box)` and `proposeSpot(box, runs, fitLaw, fitEmp)`, deterministic.

Tests in `test/` using `node:test` (no dependencies). Fixtures: copy the 13 `valid: true` rows of
Karman `physics/pa_sweeps.json` into `test/fixtures/steel_abs_valid.json` (read-only copy), and the
real console lines below into `test/fixtures/console_2026-11-19.txt`:
```
bd_pa reads: 25 fresh, 1 skipped (no new measurement) of 26 steps
Calc the best Pressure Advance: 0.0345 +/- 0.0074  [zero crossing of Hr-Hl; slope 2793 +/- 435 counts/PA, scatter 22.5, 20 of 20 points, swept 0.012 to 0.050]
bd_pa: not applied. To use it now:  SET_PRESSURE_ADVANCE ADVANCE=0.0345   To keep it, edit pressure_advance in your config.
```
Required tests and their exact expectations:
1. `predict(f, a, 0.1032, 0.653)` reproduces every line of `pa_law.json`'s `orca_paste_block` within
   0.00011 (12 cells, 10–25 mm³/s × 1500/3000/6000).
2. `fitLaw(steel rows, {nFixed: 0.653})` with σ = the row's `pa_sigma` (no halving, in this
   test only): C = 0.1046 ± 0.0005, χ² = 3.05 ± 0.05.
3. `fitLaw(steel rows, {nPrior: null})`: n = 0.745 ± 0.005 with a reported σ_n of 0.229 ± 0.01.
4. With the prior (mean 0.653, σ 0.10), n lies between 0.653 and 0.745, and its σ is < 0.10.
5. The parser on the fixture gives pa 0.0345, sigma 0.0074, used 20, total 20, fresh 25,
   skipped 1. A `NO RESULT — no sign change` line gives `no_result` with the reason. A `!!` line
   gives `error`.
6. `baselinePlan({flow:[7,21], accel:[2500,15000]})` gives 6 points, all with ramp ≥ 1.0. The first
   and last are the centre, and the 15000 corner at flow 7 is clipped to accel ≤ 5000.
7. `orcaBlock` lines match `^\d\.\d{4},\d+\.\d{2},\d+$`, and none is below 0.005.
8. `proposeSpot` returns the same point twice for the same input, and never one within 0.15 log
   units of an existing run.
```
cd /home/kyle/projects/auto-pa-tuning/web/karman-pa && node --test test/
```
**Gate:** if test 1 fails, the model is wrong, not `pa_law.json`. **Do not continue until it passes.**

## Step 2 — Moonraker client and store *(model, workstation)*

- `moonraker.js`: websocket to `ws://<location.hostname>:7125/websocket`, JSON-RPC with ids,
  auto-reconnect, `call(method, params)`, `onGcodeResponse(cb)`, `query(objects)`,
  `gcodeStore(count)`.
- `store.js`: `server.database.get_item` / `post_item` on namespace `karman_pa`; key
  `campaign_<label>_<T>C_<created ISO>`; plus `index`, a list of campaign keys.

A unit test with a fake socket: `call` resolves on the matching id, and a dropped socket rejects the
pending calls.

## Step 3 — The page *(model, workstation)*

`index.html` + `app.js` + `style.css`, implementing the four panels and every behaviour in
Pre-resolved decisions, the guard and the human clicks especially. Guard text shown to the user
names the failing condition, for example "KAPAT is sweeping; wait for it to finish".

Offline check: `python3 -m http.server -d web/karman-pa 8765`, then open `http://localhost:8765/`.
With no Moonraker reachable, the page must show "disconnected" and keep every run button disabled.
**Human:** open it and confirm that, then stop the server.

Commit in `auto-pa-tuning`:
```
git -C /home/kyle/projects/auto-pa-tuning add web/karman-pa && git -C /home/kyle/projects/auto-pa-tuning commit -m "feat: karman pa web tool prototype"
```

## Step 4 — Deploy the files *(model)*

```
rsync -a --delete /home/kyle/projects/auto-pa-tuning/web/karman-pa/ --exclude test/ ernst@192.168.1.240:karman-pa-web/
ssh ernst@192.168.1.240 'ls ~/karman-pa-web'
```
Expected: `index.html`, the `.js` modules and `style.css`; no `test/`.

## Step 5 — Look at the nginx file before anyone edits it *(model)*

```
ssh ernst@192.168.1.240 'grep -n -B1 -A10 "kapat" /etc/nginx/sites-enabled/mainsail'
```
Note where the `# >>> kapat >>>` block sits inside `server {`. The new block goes right after
`# <<< kapat <<<`. Then write the snippet (no sudo needed) and show it:
```
ssh ernst@192.168.1.240 'cat > ~/karman-pa-nginx.snippet <<'"'"'EOF'"'"'
    # >>> karman-pa >>>
    location = /karman-pa {
        return 301 /karman-pa/;
    }
    location /karman-pa/ {
        alias /home/ernst/karman-pa-web/;
        try_files $uri $uri/ /karman-pa/index.html;
    }
    # <<< karman-pa <<<
EOF
cat ~/karman-pa-nginx.snippet'
```
The printed snippet must show `$uri` literally (not empty).

## Step 6 — Add the nginx location *(human: needs sudo)*

From a workstation terminal. It backs up the file, inserts the snippet after the KAPAT block, tests,
and reloads only if the test passes:
```
ssh -t ernst@192.168.1.240 'sudo cp /etc/nginx/sites-enabled/mainsail /etc/nginx/mainsail.bak-karman-pa && sudo sed -i "/# <<< kapat <<</r /home/ernst/karman-pa-nginx.snippet" /etc/nginx/sites-enabled/mainsail && sudo nginx -t && sudo systemctl reload nginx'
```
Model checks afterwards:
```
ssh ernst@192.168.1.240 'grep -n -A8 "karman-pa >>>" /etc/nginx/sites-enabled/mainsail; curl -s -o /dev/null -w "karman-pa %{http_code}\n" http://localhost/karman-pa/; curl -s -o /dev/null -w "kapat %{http_code}\n" http://localhost/kapat/; curl -s -o /dev/null -w "mainsail %{http_code}\n" http://localhost/'
```
**Gate:** all three must return `200`. If `nginx -t` failed, the reload did not happen and nothing
changed. Restore with `sudo cp /etc/nginx/mainsail.bak-karman-pa /etc/nginx/sites-enabled/mainsail`
and escalate. If Mainsail or KAPAT stops returning 200, restore the backup the same way at once.

## Step 7 — Connect *(human, browser)*

Open `http://192.168.1.240/karman-pa/`. Expected:
- "connected".
- A live printer state line (temperatures, `print_stats.state`, KAPAT idle).
- The guard listing anything currently blocking a run.

Make a test campaign: label `TEST`, 265 °C, flow 7–21, accel 2500–15000. The feasibility map should
show the 6-point plan and the clipped corner. Reload the page: the campaign must still be there,
read from Moonraker's database. **Do not launch it.**
**If it cannot connect:** the browser console says why. Stop and escalate (no Moonraker config
edits in this runbook).

## Step 8 — One real sweep from the page *(human runs; model checks)*

Model: start a Monitor on the console, as in `docs/runbooks/pa-kapat-bdpressure-concept.md` Step 11,
or poll `server/gcode_store`, so the run's real console lines are captured independently of the page.

Human, at the printer, ABS loaded (`M109 S265` then `SWAP TOOL=0` if needed, then `G28` while the
nozzle is below 170 °C). The page has a **"Single test run"** button in Setup that runs only the
centre point. Use it on the `TEST` campaign.

Model check: the page's stored result (read `server.database.get_item` namespace `karman_pa`) must
match the console's `Calc the best Pressure Advance` line exactly (pa, σ, points, fresh/skipped).
Then check that the page sent `M104 S0` at the end:
`curl -s 'http://192.168.1.240:7125/printer/objects/query?extruder=target'` should show `0.0`.

**Gate:** a mismatch between page and console → fix the parser, add the line to the fixtures, re-run
Step 1, redeploy, and repeat this step. A `NO RESULT` from the sweep is **not** a tool failure, as
long as the page shows it as rejected with the same reason; run it once more to get a real value.

## Step 9 — Shut down *(human)*

```
TURN_OFF_HEATERS
M84
```
Remove the blob.

---

## Verification

- [ ] `node --test test/` passes, including test 1 (reproduces the steel-ABS matrix) and the
      parser on real console text. *(validated in a proxy)*
- [ ] `/karman-pa/`, `/kapat/` and `/` all return 200 after the nginx change. *(verified in reality)*
- [ ] With Moonraker unreachable the page disables every run button; connected, it shows live state
      and the guard. *(verified in reality: the maintainer looked)*
- [ ] A campaign survives a page reload (stored in Moonraker's database). *(verified in reality)*
- [ ] One sweep started from the page: the stored result matches the console line exactly, and the
      nozzle target is 0 afterwards. *(verified in reality)*
- [ ] **Nothing regressed:** Mainsail and KAPAT pages load. `KARMAN_PA_CALIBRATE` from the Mainsail
      console still works (the Step 8 sweep proves it). `physics/` is unchanged (`ssh
      ernst@192.168.1.240 'cd ~/printer_data/config && git status -s physics/'` is empty).
      `[extruder] pressure_advance` still reads 0.032.
- [ ] Heaters off at the end.

## When it is done

- **`docs/decisions.md`**: one entry, "PA web tool around KARMAN_PA_CALIBRATE (prototype)". Record
  the architecture (static page + Moonraker DB, no Klippy code, and why), **the implicit Qpeak
  definition** (`v_high + K·accel`, reverse-engineered and verified against `pa_law.json`), the
  n prior and why (free n = 0.745 ± 0.229 on the steel data), σ = reported/2, the feasibility rule,
  the DOE and stopping rule.
- **`docs/pa_physics.md` §5.3**: one sentence and the formula for `Qpeak`, so it is written down
  where the law is.
- **`CLAUDE.md`**: under *Printer*, one line: the PA web tool at `/karman-pa/`
  (`~/karman-pa-web`, source `auto-pa-tuning/web/karman-pa`), which drives `KARMAN_PA_CALIBRATE`
  and stores campaigns in Moonraker's database namespace `karman_pa`.
- **td**: close this issue only when every item above is checked. The next issue (first campaign)
  then becomes ready.
- **Commits**:
  - `auto-pa-tuning` (local): the Step 3 commit, plus any parser fixes.
  - Karman, over SSH on the Pi, after asking: `docs: record the pa web tool prototype` —
    `docs/decisions.md`, `docs/pa_physics.md`, `CLAUDE.md`, this runbook.
