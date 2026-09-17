# Runbook — fuzz the Beacon contact point (RatOS-style wear spreading)

**Objective:** every Beacon **contact** touch during `START_PRINT` lands on a *randomized* point
inside a 20×20 mm patch centred on 175, 175, instead of hammering the exact same spot on the PEI
sheet twice per print. Adopted from RatOS's
`variable_beacon_contact_start_print_true_zero_fuzzy_position`
([RatOS beacon docs](https://os.ratrig.com/docs/configuration/beacon/)).
**Status:** 🟡 not started
**Created:** 2026-09-04
**Prerequisites:** printer idle (not mid-print); a bed mesh loaded or creatable; nozzle clean.

## Why this isn't a copy-paste from RatOS

RatOS never uses Beacon's own `home_xy_position`. Its true-zero macro does a plain
`G0 X.. Y..` and then calls `BEACON_AUTO_CALIBRATE`, which probes **wherever the toolhead
currently is** — so "fuzzing" there is just randomizing that `G0`.

Karman is wired differently. `overrides.cfg` sets `[beacon] home_xy_position: 175, 175`, which
installs Beacon's `BeaconHomingHelper` as the `G28` handler. Klippain's contact hooks
(`macros/base/probing/hooks/beacon_contact.cfg`) call `G28 Z METHOD=CONTACT CALIBRATE=0|1`, and
inside `beacon.py` that does:

```python
pos = [self.home_pos[0], self.home_pos[1]]      # 175,175 — read from config at startup
toolhead.manual_move(pos, self.xy_move_speed)
self.beacon.cmd_BEACON_AUTO_CALIBRATE(...)      # SKIP_MODEL_CREATION=1 when CALIBRATE=0
```

`home_pos` is a Python attribute read once at config time — **no macro can change it at runtime.**
So the fix is to stop routing through `G28 Z METHOD=CONTACT` and instead do what RatOS does:
move to a fuzzed point ourselves, then call `BEACON_AUTO_CALIBRATE` directly. That is an exact
behavioural equivalent — verified by reading `beacon.py` (`~/beacon_klipper/beacon.py`,
`cmd_G28` contact branch and `cmd_BEACON_AUTO_CALIBRATE`).

Karman touches the bed with the nozzle **twice** per print, per
`variable_startprint_actions` in `overrides.cfg`:

```
"bed_soak", "extruder_preheating", "chamber_soak", "clean",
 → "contact_auto_calibrate", "tilt_calib", "bedmesh", "contact_z_home",
"extruder_heating", "nozzle_expansion", "clean", "primeline"
```

Both are fuzzed by this runbook.

## The one real consequence: mesh coupling (read before changing the radius)

`[bed_mesh] zero_reference_position` is **175, 175** — the *same* point as the contact. That is
not a coincidence, and it is why the current setup has zero Z error: the mesh is normalized so its
correction is 0 at exactly the point where Z=0 was established.

`contact_z_home` runs **after** `bedmesh`, so it sets the final Z origin. Move it to a fuzzed
point `P` and the first-layer gap becomes `gcode_z + m(P)`, where `m(P)` is the mesh value at `P`.
The error is exactly the bed's local deviation over the patch — nothing more.

*(`contact_auto_calibrate` runs **before** `bedmesh`, so fuzzing it has **no** Z consequence at
all: whatever zero it sets is superseded, and the mesh built afterwards is normalized at the
zero reference regardless.)*

Measured on the mesh loaded on 2026-09-04 (`tools/beacon_fuzz_mesh_check.py`, added in Step 1):

| patch radius | worst \|deviation\| |
|---|---|
| ±5 mm | 0.0117 mm |
| ±7.5 mm | 0.0152 mm |
| **±10 mm (chosen)** | **0.0183 mm** |

0.018 mm is ~9 % of a 0.2 mm layer, and it is *close to* the 0.020 mm accept threshold — Step 2
re-measures it against a current mesh and Step 2b tells you exactly what to do if it exceeds.

## Scope

Add a fuzzed-contact-point implementation to `overrides.cfg`, validate it offline, verify on the
printer that contact lands somewhere different each time and that first-layer quality is
unchanged.

## ⚠️ Out of scope — do not touch

- **`[beacon] home_xy_position: 175, 175`** (`overrides.cfg:154`) — **leave it exactly as is.**
  It is still the contact point for a plain `G28`, for `BEACON_CALIBRATE_NOZZLE_TEMP_OFFSET`, and
  for this runbook's own fallback path. Deleting it does not "free" anything — it *uninstalls*
  Beacon's `G28` handler and changes homing behaviour machine-wide.
- **`[bed_mesh] zero_reference_position: 175, 175`** — do **not** move it to chase the fuzz point,
  and do not remove it. The entire error analysis above assumes it stays at the nominal centre;
  every print's mesh normalization depends on it.
- **`variable_startprint_actions` ordering** — `contact_auto_calibrate` before `tilt_calib`/
  `bedmesh`, `contact_z_home` after `bedmesh`. That order was settled by the START_PRINT audit
  (`docs/decisions.md` 2026-08-02). Do **not** reorder it to "avoid" the mesh coupling.
- **`thermal_expansion.cfg`** — `BEACON_CALIBRATE_NOZZLE_TEMP_OFFSET` /
  `_BEACON_PROBE_NOZZLE_TEMP_OFFSET` must keep probing a **fixed** point: they compare Z at 150 °C
  against Z at 250 °C, so a moving point would inject bed deviation straight into the expansion
  coefficient. They use `G28`, `G28 Z` and `PROBE PROBE_METHOD=contact` — none of which route
  through the hooks this runbook overrides. Leave the file alone.
- **`nozzle_expansion_coefficient = 0.055`** (in `save_variables.cfg`) — correct and hand-verified.
  Not part of this objective; see `docs/decisions.md` 2026-08-02.
- **`variable_beacon_max_probing_temp: 180`** (`variables.cfg`) and
  **`contact_max_hotend_temperature: 180`** — the contact temperature guard. Do not raise either
  to skip the cool-down wait.
- **`macros/base/probing/hooks/beacon_contact.cfg`** and everything under `config/`, `macros/`,
  `moonraker/`, `scripts/` — symlinks into the Klippain install. Never edit them; override in
  `overrides.cfg` (the `guard-framework` hook will block you anyway). Precedent for this style of
  override: `_CONDITIONAL_MOVE_TO_PURGE_BUCKET` in `overrides.cfg`.
- **`~/beacon_klipper/beacon.py`** — do **not** patch the vendor module to make `home_pos`
  settable. It is managed by its own updater and would be silently reverted, and a `.py` change
  needs a full host restart to take effect (see `CLAUDE.md`).
- **Do not add `[safe_z_home]` or `[homing_override]`** — Beacon raises a config error if either
  exists alongside `home_xy_position`.
- **Keep-out zones** — the patch (165–185 × 165–185) is dead centre and clear of every zone. Do not
  widen the radius past ±25 mm without re-checking: adaptive meshes can be smaller than the patch,
  and `bed_mesh mesh_min` is 25,25.

## Pre-resolved decisions

Already decided — implement as written; the user can veto any line in one edit.

| Decision | Value | Why |
|---|---|---|
| Which operations get fuzzed | **both** `contact_auto_calibrate` and `contact_z_home` | fuzzing only one halves the wear mark instead of removing it |
| Pattern | **uniform random in a square**, 0.1 mm grid | what RatOS does; confirmed working under Klipper's Jinja env |
| Patch radius | **±10 mm** (20×20 mm) | user's choice; measured mesh residual 0.018 mm, inside the 0.020 threshold |
| Mesh compensation | **none** | residual is under 10 % of a layer; a sign error in `mesh_matrix` interpolation would silently ruin first layers |
| Toggle | `variable_enabled: True` on `_KARMAN_BEACON_FUZZ_VARS` | one `SET_GCODE_VARIABLE` reverts to stock behaviour without a restart |
| Fallback | stock `G28 Z METHOD=CONTACT` when disabled **or** X/Y/Z not all homed | `BEACON_AUTO_CALIBRATE` errors on unhomed XY, and a bare `G1 Z` errors on unhomed Z |
| Implementation site | override the two hook macros in `overrides.cfg` | keeps Klippain's temperature guard, `SAVE/RESTORE_GCODE_STATE` and `ACTIVATE_PROBE` wiring intact |

---

## Steps

### Step 0 — confirm which mode you are in

```bash
readlink -e config >/dev/null 2>&1 && echo "MOUNT/on-Pi" || echo "WORKSTATION CLONE"
```

- **MOUNT/on-Pi** — your edits are live on the printer immediately; you still need
  `FIRMWARE_RESTART` (Step 5). Run every `git` command over SSH.
- **WORKSTATION CLONE** — edits reach the printer only via commit → push → `GIT_PULL`. Steps that
  query the printer over HTTP still work if it is reachable.

### Step 1 — add the mesh-deviation check tool

Create `tools/beacon_fuzz_mesh_check.py` with exactly this content:

```python
#!/usr/bin/env python3
"""Report the bed-mesh deviation across the Beacon contact fuzz patch.

The fuzzed contact point shifts the final Z origin by the mesh value at that point
(bed_mesh.zero_reference_position is the nominal centre, where the mesh value is 0).
This reports the worst-case shift over the patch, so the radius can be chosen against
a real number instead of a guess.

Usage: python3 tools/beacon_fuzz_mesh_check.py [HOST] [CENTER_X] [CENTER_Y] [RADIUS]
Defaults: 192.168.1.240 175 175 10
"""
import json, sys, urllib.request

host = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.240"
cx = float(sys.argv[2]) if len(sys.argv) > 2 else 175.0
cy = float(sys.argv[3]) if len(sys.argv) > 3 else 175.0
r = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0

url = f"http://{host}:7125/printer/objects/query?bed_mesh"
bm = json.load(urllib.request.urlopen(url))["result"]["status"]["bed_mesh"]
m = bm.get("mesh_matrix")
if not m:
    sys.exit("No mesh loaded. Run BED_MESH_CALIBRATE (or load a profile) first.")
x0, y0 = bm["mesh_min"]; x1, y1 = bm["mesh_max"]
ny, nx = len(m), len(m[0])

def val(x, y):
    fx = (x - x0) / (x1 - x0) * (nx - 1)
    fy = (y - y0) / (y1 - y0) * (ny - 1)
    fx = min(max(fx, 0), nx - 1); fy = min(max(fy, 0), ny - 1)
    i, j = int(fx), int(fy)
    i2, j2 = min(i + 1, nx - 1), min(j + 1, ny - 1)
    tx, ty = fx - i, fy - j
    return ((m[j][i] * (1 - tx) + m[j][i2] * tx) * (1 - ty)
            + (m[j2][i] * (1 - tx) + m[j2][i2] * tx) * ty)

if not (x0 <= cx - r and cx + r <= x1 and y0 <= cy - r and cy + r <= y1):
    print(f"WARNING: patch extends outside the mesh ({x0}..{x1}, {y0}..{y1}); values are clamped.")

samples = [val(cx + r * i / 10.0, cy + r * j / 10.0)
           for i in range(-10, 11) for j in range(-10, 11)]
print(f"mesh profile     : {bm.get('profile_name')}  ({x0}..{x1} x {y0}..{y1})")
print(f"value at centre  : {val(cx, cy):+.4f} mm  (should be ~0 -- zero_reference_position)")
print(f"patch {cx}+/-{r}, {cy}+/-{r}")
print(f"  min / max      : {min(samples):+.4f} / {max(samples):+.4f} mm")
print(f"  worst |dev|    : {max(abs(v) for v in samples):.4f} mm")
print("PASS (<=0.020 mm)" if max(abs(v) for v in samples) <= 0.020 else "FAIL -> shrink radius")
```

### Step 2 — measure the mesh deviation across the patch

**USER, on the printer console** — if no mesh is currently loaded, or the loaded one is a small
adaptive mesh from the last print, get a full-bed one first (printer must be idle):

```
G28
BED_MESH_CALIBRATE PROFILE=default
```

Then, from the repo:

```bash
python3 tools/beacon_fuzz_mesh_check.py 192.168.1.240 175 175 10
```

Expected shape of the output (numbers will differ):

```
value at centre  : +0.0029 mm  (should be ~0 -- zero_reference_position)
  worst |dev|    : 0.0183 mm
PASS (<=0.020 mm)
```

**Record this number in the status log.** It is the baseline the verification compares against.

### Step 2b — if Step 2 printed `FAIL`

Do **not** proceed with ±10 mm. Re-run at 7.5 and 5:

```bash
python3 tools/beacon_fuzz_mesh_check.py 192.168.1.240 175 175 7.5
python3 tools/beacon_fuzz_mesh_check.py 192.168.1.240 175 175 5
```

Use the **largest** radius that reports `PASS`, and set `variable_radius` in Step 3 to it instead
of `10.0`. Note the substitution in the status log. If even ±5 mm fails, stop and report — that
means the bed is unusually uneven near the centre and is a separate problem.

### Step 3 — add the fuzz implementation to `overrides.cfg`

Append to the **end** of `overrides.cfg` (the file currently ends without a trailing newline, so
the `printf` matters):

```bash
printf '\n\n' >> overrides.cfg
cat >> overrides.cfg <<'EOF'
# ------- Beacon contact-point fuzzing -------
# Randomizes where the nozzle touches the bed for Beacon *contact* operations, so the two
# contact pokes per print stop wearing a single spot on the PEI. Adopted from RatOS's
# `beacon_contact_start_print_true_zero_fuzzy_position`; see
# docs/runbooks/beacon-contact-fuzzy-position.md for why it cannot be a straight port.
#
# `[beacon] home_xy_position` is read once at config time and cannot be changed at runtime, so
# `G28 Z METHOD=CONTACT` always lands on 175,175. These hooks bypass it and call
# BEACON_AUTO_CALIBRATE directly at a fuzzed point, which is what beacon.py's own G28 contact
# branch does after its move (SKIP_MODEL_CREATION=1 <=> CALIBRATE=0).
#
# ⚠️ RADIUS IS BOUNDED BY THE BED MESH, NOT BY CLEARANCE. `bed_mesh zero_reference_position` is
# 175,175, so a fuzzed `contact_z_home` shifts the Z origin by the mesh value at that point.
# Re-run `tools/beacon_fuzz_mesh_check.py` before increasing `radius`.
[gcode_macro _KARMAN_BEACON_FUZZ_VARS]
description: Beacon contact-point fuzzing settings (spreads nozzle-contact wear on the PEI)
variable_enabled: True
variable_center_x: 175.0
variable_center_y: 175.0
variable_radius: 10.0
variable_last_x: 0.0
variable_last_y: 0.0
gcode:


[gcode_macro _KARMAN_BEACON_CONTACT_FUZZED]
description: Beacon contact Z establishment at a randomized point around the nominal centre
gcode:
    {% set skip_model = params.SKIP_MODEL_CREATION|default(1)|int %}
    {% set v = printer["gcode_macro _KARMAN_BEACON_FUZZ_VARS"] %}
    {% set b = printer.configfile.settings.beacon %}
    {% set travel_speed = b.home_xy_move_speed|float * 60 %}
    {% set z_hop = b.home_z_hop|float %}
    {% set z_hop_speed = b.home_z_hop_speed|float * 60 %}
    {% set steps = (v.radius|float * 10)|round|int %}
    {% set fx = v.center_x|float + (range(-steps, steps + 1)|random) / 10.0 %}
    {% set fy = v.center_y|float + (range(-steps, steps + 1)|random) / 10.0 %}

    # Same lift-then-move ordering as beacon.py's _maybe_zhop, so travel hazard is unchanged.
    G90
    {% if printer.toolhead.position.z|float < z_hop %}
        G1 Z{z_hop} F{z_hop_speed}
    {% endif %}
    G1 X{fx} Y{fy} F{travel_speed}
    SET_GCODE_VARIABLE MACRO=_KARMAN_BEACON_FUZZ_VARS VARIABLE=last_x VALUE={fx}
    SET_GCODE_VARIABLE MACRO=_KARMAN_BEACON_FUZZ_VARS VARIABLE=last_y VALUE={fy}
    RESPOND MSG="Beacon contact at fuzzed point {fx}, {fy}"
    BEACON_AUTO_CALIBRATE SKIP_MODEL_CREATION={skip_model}
    {% if printer.toolhead.position.z|float < z_hop %}
        G1 Z{z_hop} F{z_hop_speed}
    {% endif %}


# Overrides macros/base/probing/hooks/beacon_contact.cfg (Klippain framework symlink).
[gcode_macro _PROBE_HOOK_CONTACT_Z_HOME]
description: Beacon Contact Z homing hook (Karman: fuzzed contact point)
gcode:
    {% set source = params.SOURCE|default("manual")|string|lower %}
    _PROBE_VALIDATE_SOURCE SOURCE={source}
    {% if printer["gcode_macro _KARMAN_BEACON_FUZZ_VARS"].enabled and 'xyz' in printer.toolhead.homed_axes %}
        _KARMAN_BEACON_CONTACT_FUZZED SKIP_MODEL_CREATION=1
    {% else %}
        G28 Z METHOD=CONTACT CALIBRATE=0
    {% endif %}


[gcode_macro _PROBE_HOOK_CONTACT_AUTO_CALIBRATE]
description: Beacon Contact automatic model calibration hook (Karman: fuzzed contact point)
gcode:
    {% set source = params.SOURCE|default("manual")|string|lower %}
    _PROBE_VALIDATE_SOURCE SOURCE={source}
    {% if printer["gcode_macro _KARMAN_BEACON_FUZZ_VARS"].enabled and 'xyz' in printer.toolhead.homed_axes %}
        _KARMAN_BEACON_CONTACT_FUZZED SKIP_MODEL_CREATION=0
    {% else %}
        G28 Z METHOD=CONTACT CALIBRATE=1
    {% endif %}
EOF
```

If Step 2b changed the radius, edit `variable_radius` now.

### Step 4 — offline validation (no printer needed)

```bash
uv run tools/render_macro.py --selftest
uv run tools/visualize_toolchange.py
```

Both must pass; the visualizer must report **clean** on all scenarios. (The `check-toolchange`
hook also runs the visualizer automatically after any edit to `overrides.cfg`.)

Then render the four code paths. These write three throwaway JSON files — put them in **your
session's scratchpad directory** (its path is in your system prompt); `export SP=<that path>`
first. If you don't have one, `export SP=/tmp`.

```bash
cat > "$SP/ctx.json" <<'EOF'
{
  "gcode_macro _KARMAN_BEACON_FUZZ_VARS": {"enabled": true, "center_x": 175.0, "center_y": 175.0, "radius": 10.0, "last_x": 0.0, "last_y": 0.0},
  "configfile": {"settings": {"beacon": {"home_xy_move_speed": 350.0, "home_z_hop": 5.0, "home_z_hop_speed": 30.0}}},
  "toolhead": {"position": {"x": 70.5, "y": 359.0, "z": 1.0}, "homed_axes": "xyz"}
}
EOF
python3 - "$SP" <<'EOF'
import copy, json, sys
sp = sys.argv[1]
base = json.load(open(f"{sp}/ctx.json"))
u = copy.deepcopy(base); u["toolhead"]["homed_axes"] = "xy"
json.dump(u, open(f"{sp}/ctx_unhomed.json", "w"))
d = copy.deepcopy(base); d["gcode_macro _KARMAN_BEACON_FUZZ_VARS"]["enabled"] = False
json.dump(d, open(f"{sp}/ctx_disabled.json", "w"))
EOF
```

Render:

```bash
for m in _PROBE_HOOK_CONTACT_Z_HOME _PROBE_HOOK_CONTACT_AUTO_CALIBRATE; do
  for c in ctx ctx_unhomed ctx_disabled; do
    echo "### $m / $c"
    uv run tools/render_macro.py overrides.cfg $m --json "$SP/$c.json" --params "SOURCE=start_print" | grep -v '^[[:space:]]*$'
  done
done
uv run tools/render_macro.py overrides.cfg _KARMAN_BEACON_CONTACT_FUZZED --json "$SP/ctx.json" --params "SKIP_MODEL_CREATION=1"
```

**Expected** (this exact output was produced while writing this runbook):

| macro | context | must emit |
|---|---|---|
| `_PROBE_HOOK_CONTACT_Z_HOME` | homed, enabled | `_KARMAN_BEACON_CONTACT_FUZZED SKIP_MODEL_CREATION=1` |
| `_PROBE_HOOK_CONTACT_Z_HOME` | unhomed **or** disabled | `G28 Z METHOD=CONTACT CALIBRATE=0` |
| `_PROBE_HOOK_CONTACT_AUTO_CALIBRATE` | homed, enabled | `_KARMAN_BEACON_CONTACT_FUZZED SKIP_MODEL_CREATION=0` |
| `_PROBE_HOOK_CONTACT_AUTO_CALIBRATE` | unhomed **or** disabled | `G28 Z METHOD=CONTACT CALIBRATE=1` |
| `_KARMAN_BEACON_CONTACT_FUZZED` | homed | `G1 Z5.0 F1800.0`, then `G1 X<165..185> Y<165..185> F21000.0`, then `BEACON_AUTO_CALIBRATE SKIP_MODEL_CREATION=1` |

Run the last one three times — **the X/Y must differ between runs** and must always fall inside
165–185. If they are identical every time, the `|random` filter is not doing what it should; stop
and report rather than continuing to hardware.

### Step 5 — apply on the printer

**Mount mode:** the file is already live.
**Clone mode:** commit + push first (Step 9), then run `GIT_PULL` on the printer.

**USER, on the printer console** (printer must be idle — this is unsafe mid-print):

```
FIRMWARE_RESTART
```

A config error here means a typo in the appended block. There is no offline Klipper config
linter — this restart is the authoritative check.

### Step 6 — verify the contact point actually moves

**USER, on the printer console.** The nozzle must be clean (contact readings are corrupted by
debris) and cool enough for the guard (< 180 °C):

```
G28
_PROBE_CONTACT_AUTO_CALIBRATE SOURCE=manual
_PROBE_CONTACT_AUTO_CALIBRATE SOURCE=manual
_PROBE_CONTACT_Z_HOME SOURCE=manual
```

Each should print `Beacon contact at fuzzed point <x>, <y>` with **different** coordinates, all
inside 165–185, followed by Beacon's own `Collected 3 samples, … sd` line. Report the console
output — do not assume it worked.

Check the recorded point and that Beacon is happy:

```bash
curl -s 'http://192.168.1.240:7125/printer/objects/query?beacon&gcode_macro%20_KARMAN_BEACON_FUZZ_VARS'
```

`beacon.last_probe_result` must be `ok`.

### Step 7 — verify the fallback path

**USER, on the printer console:**

```
SET_GCODE_VARIABLE MACRO=_KARMAN_BEACON_FUZZ_VARS VARIABLE=enabled VALUE=False
_PROBE_CONTACT_Z_HOME SOURCE=manual
SET_GCODE_VARIABLE MACRO=_KARMAN_BEACON_FUZZ_VARS VARIABLE=enabled VALUE=True
```

The middle command must **not** print a "fuzzed point" message, and the toolhead must go to
175, 175. That is the escape hatch working.

### Step 8 — measure the physical consequence (recommended)

This directly measures what Step 2 predicted. **USER, on the printer console**, homed, clean cold
nozzle, no mesh applied (`BED_MESH_CLEAR` first so raw contact is compared, not mesh-corrected):

```
BED_MESH_CLEAR
G28
G1 X175 Y175 Z5 F9000
PROBE PROBE_METHOD=contact SAMPLES=3 SAMPLES_RESULT=median
G1 X165 Y165 F9000
PROBE PROBE_METHOD=contact SAMPLES=3 SAMPLES_RESULT=median
G1 X185 Y185 F9000
PROBE PROBE_METHOD=contact SAMPLES=3 SAMPLES_RESULT=median
```

The spread across the three results is the real-world version of Step 2's `worst |dev|`. It
should be the same order of magnitude (≲ 0.02 mm here). A much larger spread means the mesh
prediction underestimates the local bed shape — shrink `variable_radius` and re-run Step 2.

Restore the mesh afterwards:

```
BED_MESH_PROFILE LOAD=default
```

### Step 9 — one real print

**USER.** Run a normal single-colour print and check the first layer against the last known-good
one. The START_PRINT console output should show two `Beacon contact at fuzzed point` lines with
different coordinates.

---

## Verification — the objective is met when all of these hold

- [ ] `FIRMWARE_RESTART` completes with no config error (Step 5).
- [ ] Three consecutive contact operations report **three different** fuzzed points, all inside
      165–185 in both axes (Step 6).
- [ ] `beacon.last_probe_result` is `ok` after each (Step 6).
- [ ] With `enabled: False`, contact goes to 175, 175 and prints no fuzz message (Step 7).
- [ ] Contact-Z spread across the patch is ≲ 0.02 mm and consistent with Step 2's prediction
      (Step 8).
- [ ] A real print's START_PRINT logs two fuzzed points, and **first-layer quality is
      indistinguishable from before** — no new elephant's foot, no gaps (Step 9).

Anything short of that last box means the objective is *not* met, regardless of how clean the
console looked.

## Commit guidance

Run every `git` command **over SSH on the Pi** in mount mode
(`ssh ernst@192.168.1.240 'cd ~/printer_data/config && git ...'`). Propose the commands; the
maintainer runs them.

```
feat(beacon): fuzz the contact point to spread nozzle wear on the PEI
tools: add beacon_fuzz_mesh_check to bound the fuzz radius by mesh deviation
docs: runbook + decision for beacon contact-point fuzzing
```

After hardware verification, add a `docs/decisions.md` entry covering:
- why `home_xy_position` could not simply be randomized (config-time attribute),
- that `BEACON_AUTO_CALIBRATE SKIP_MODEL_CREATION=1` is the exact equivalent of
  `G28 Z METHOD=CONTACT CALIBRATE=0` minus the fixed move,
- that the radius is bounded by `bed_mesh zero_reference_position` coupling, not by clearance,
  with the measured deviation numbers.

Then update `TODO.md`: tick the task under **Miscellaneous** and drop it from **▶ Next up** if it
was added there.

## Status log

_(append during execution)_

- **2026-09-04** — runbook written (architecture session). Nothing applied to the printer. The
  macro text in Step 3 was rendered offline through `tools/render_macro.py` across all four code
  paths and behaved as documented; the mesh-deviation numbers in the table came from the mesh
  loaded on the printer that day. No hardware step has been run.
