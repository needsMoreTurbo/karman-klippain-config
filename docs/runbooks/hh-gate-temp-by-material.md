# Runbook — gate temperature follows the material, and stops reverting to 245 °C

**Objective:** when a gate's filament is edited in the **Mainsail / Fluidd Happy Hare panel**,
(a) choosing a material fills the swap temperature from a material table (ABS → 260), and
(b) editing any other field (colour, name, …) **keeps** the gate's current temperature instead
of resetting it to 245. This is a Karman-side wrapper in `overrides.cfg`. It works on Happy Hare
v3 today and carries over unchanged to v4.
**Status:** 🟡 not started
**Created:** 2026-10-10
**Prerequisites:** printer idle for `FIRMWARE_RESTART`. No print needed.

## Background — root cause (found 2026-10-10)

- **Mainsail sends one field per command.** From `~/printer_data/logs/mmu.log` (HH logs every
  `MMU_GATE_MAP` command line):
  ```
  09:17:45 > MMU_GATE_MAP GATE=0 NAME="Polymaker ABS" QUIET=1
  09:17:48 > MMU_GATE_MAP GATE=0 MATERIAL=ABS QUIET=1
  09:17:57 > MMU_GATE_MAP GATE=0 TEMP=260 QUIET=1
  09:18:03 > MMU_GATE_MAP GATE=0 COLOR=000000FF QUIET=1
  ```
- **The per-gate branch defaults a missing `TEMP` to `default_extruder_temp`, not to the gate's
  current value.** In v3 that is `~/Happy-Hare/extras/mmu/mmu.py` ~8636–8643:
  `temperature = gcmd.get_int('TEMP', int(self.default_extruder_temp))`, then
  `temperature or self.gate_temperature[gate]`. 245 is truthy, so the `or` never falls back. So
  the `COLOR=` command at 09:18:03 silently overwrote 260 with 245 (`default_extruder_temp: 245`
  in `mmu/base/mmu_parameters.cfg`). **v4 has the identical code**
  (`extras/mmu/commands/mmu_gate_map.py:288` and `:307` on upstream `main` @ `c66216b`,
  2026-10-04), so upgrading does not fix it.
- **Neither v3 nor v4 maps material to temperature.** AFC does, through
  `default_material_temps`, matching on a **case-insensitive substring, first match wins, in list
  order** (`AFC.py` `_get_default_material_temps`). The maintainer's ECC printer runs AFC with
  `default_material_temps: default: 240, PLA:210, PETG:240, ABS:260, ASA:260, TPU:230`
  (read from its `printer.cfg` on 2026-10-10). This runbook copies that table and behaviour.

## Scope

1. Add a `[gcode_macro MMU_GATE_MAP]` wrapper (`rename_existing`) to `overrides.cfg`.
2. Extend `tools/render_macro.py` so it can pass `rawparams` (the wrapper forwards it).
3. Validate offline, apply, and test from the Mainsail panel.
4. Record a `docs/decisions.md` entry.

## ⚠️ Out of scope — do not touch

- **Happy Hare's Python** (`~/Happy-Hare/extras/…`). Never patch it: it is managed by its own
  installer and replaced wholesale on the v4 upgrade. The wrapper is the fix.
- **`default_extruder_temp: 245`** in `mmu_parameters.cfg`. It stays as HH's fallback for code
  paths the wrapper does not cover.
- **The `MAP=` (JSON / Spoolman) and `GATES=` list forms** of `MMU_GATE_MAP`. They are passed
  through untouched. Spoolman isn't used on Karman yet (TODO "Spoolman integration (later)").
- **The bypass gate (`GATE=-2`)** and out-of-range gates are passed through untouched.
- **Slicer-driven temperatures.** During a print, swap temperatures come from the slicer tool map
  (`MMU_START_SETUP` / `MMU_SLICER_TOOL_MAP`), not this table. Not affected.
- **Blobifier, cutter, purge config**: unrelated.

## Pre-resolved decisions (maintainer, 2026-10-10)

1. **Fix it now on v3, as its own objective.** It carries to v4. The v4 runbooks re-verify it.
2. **Table = the ECC's AFC table plus `PET:290`.** 290 is Karman's live gate-map value for
   PET-GF on the UHF hotend. **`PETG` must come before `PET` in the list**: matching is by
   substring, so `PET` would also match `PETG`. Unknown materials get `default` = 240, as in AFC.
3. **When `MATERIAL=` is given without `TEMP=`, the table wins.** When neither is given, the
   gate's current temperature is kept. An explicit `TEMP=` always passes through unchanged.

## Steps

### 1. Confirm HH doesn't call `MMU_GATE_MAP` from its own macros (model, read-only)

```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && grep -rn "MMU_GATE_MAP" mmu/ macros/ overrides.cfg | grep -v "^\s*#"'
```

The wrapper applies to every caller. For each hit, check that it either passes `TEMP=` or is a
`GATES=` / `MAP=` / `RESET` form (which pass through). Report any other hit before continuing.

### 2. Add `rawparams` to the offline renderer (model)

In `tools/render_macro.py`:
- add `--rawparams` (string) to `main()`;
- pass it through `render()` into `tmpl.render(…, rawparams=…)`;
- keep `--params` as it is (`params` is still needed for `'X' in params` tests).

Keep the change minimal and in the file's existing style.

### 3. Add the wrapper to `overrides.cfg` (model)

Add it near the other Happy Hare overrides (e.g. after `_KARMAN_MMU_ACTION_CHANGED`), verbatim:

```
# ------- MMU_GATE_MAP wrapper: gate temp follows the material, and survives partial edits -------
# Mainsail's HH panel sends ONE field per command (GATE=0 COLOR=..., GATE=0 TEMP=..., ...). HH's
# per-gate branch defaults a missing TEMP to default_extruder_temp (245), so a colour edit after
# setting 260 silently reset it to 245 (v3 mmu.py ~8636; v4 commands/mmu_gate_map.py:288 - same).
# Single-gate edits without TEMP get one added: from the material table when MATERIAL is given,
# else the gate's current temperature. Explicit TEMP, GATES=, MAP= and the bypass gate pass through.
# Table + matching mirror AFC's default_material_temps (case-insensitive substring, first match
# wins - so PETG must stay before PET). Values copied from the ECC's AFC config, plus PET:290.
# docs/runbooks/hh-gate-temp-by-material.md
[gcode_macro MMU_GATE_MAP]
rename_existing: _KARMAN_MMU_GATE_MAP_STOCK
description: Gate map editor (Karman wrapper: keep a gate's temp on partial edits, fill it from the material)
variable_material_temps: "PLA:210, PETG:240, PET:290, ABS:260, ASA:260, TPU:230, default:240"
gcode:
    {% set ngates = printer.mmu.gate_temperature|length %}
    {% set gate = params.GATE|default(-99)|int %}
    {% set single = ('GATE' in params) and ('GATES' not in params) and ('MAP' not in params)
                    and ('RESET' not in params) and (0 <= gate < ngates) %}
    {% if single and 'TEMP' not in params %}
        {% if params.MATERIAL|default("")|trim != "" %}
            {% set mat = params.MATERIAL|trim|lower %}
            {% set ns = namespace(temp=-1, fallback=-1) %}
            {% for entry in material_temps.split(',') %}
                {% set kv = entry.split(':') %}
                {% set key = kv[0]|trim|lower %}
                {% if key == 'default' %}
                    {% set ns.fallback = kv[1]|trim|int %}
                {% elif ns.temp < 0 and key in mat %}
                    {% set ns.temp = kv[1]|trim|int %}
                {% endif %}
            {% endfor %}
            {% set temp = ns.temp if ns.temp > 0 else ns.fallback %}
        {% else %}
            {% set temp = printer.mmu.gate_temperature[gate]|int %}
        {% endif %}
        {% if temp > 0 %}
            _KARMAN_MMU_GATE_MAP_STOCK {rawparams} TEMP={temp}
        {% else %}
            _KARMAN_MMU_GATE_MAP_STOCK {rawparams}
        {% endif %}
    {% else %}
        _KARMAN_MMU_GATE_MAP_STOCK {rawparams}
    {% endif %}
```

### 4. Validate offline (model)

Write a state JSON in the session scratchpad:
`{"mmu": {"gate_temperature": [260, 290]}}`.

The renderer resolves the macro's own `variable_material_temps` only if it injects macro
variables. **If it doesn't** (current behaviour), also pass it in the context the way the tool
expects, or extend the tool to inject `variable_*` values of the macro being rendered. Prefer
the extension; it is a small, general fix.

Then render each row and compare:

| `--rawparams` | Expected forwarded command |
|---|---|
| `GATE=0 COLOR=000000FF QUIET=1` | `… GATE=0 COLOR=000000FF QUIET=1 TEMP=260` (kept) |
| `GATE=0 MATERIAL=ABS QUIET=1` | `… TEMP=260` |
| `GATE=1 MATERIAL=PETG QUIET=1` | `… TEMP=240` (PETG before PET) |
| `GATE=1 MATERIAL=PET-GF QUIET=1` | `… TEMP=290` |
| `GATE=0 MATERIAL=Nylon QUIET=1` | `… TEMP=240` (default) |
| `GATE=0 TEMP=250 QUIET=1` | unchanged, no extra TEMP |
| `GATE=0 NAME="Polymaker ABS" QUIET=1` | `… NAME="Polymaker ABS" QUIET=1 TEMP=260` (quotes preserved) |
| `GATES=0,1 AVAILABLE=1` | unchanged |
| `GATE=-2 MATERIAL=ABS` | unchanged (bypass) |
| `REFRESH=1` | unchanged |

(`--params` must carry the same keys as `--rawparams` for each row.) These expectations were
produced by a scratch render of this exact macro on 2026-10-10. Any difference means the copy
was altered.

### 5. Apply (USER, printer idle)

```
FIRMWARE_RESTART
```

Expected: a clean restart. A `rename_existing` error here means HH didn't register
`MMU_GATE_MAP` before the macro loaded. Stop and report it; don't work around it.

### 6. Test from the Mainsail HH panel (USER + model)

Watch HH's own log of every command:

```
ssh ernst@192.168.1.240 'tail -Fn0 ~/printer_data/logs/mmu.log | grep --line-buffered MMU_GATE_MAP'
```

Ask the maintainer to edit **gate 0** in the Mainsail Happy Hare panel, in this order, closing
the filament menu after each step:
1. Material → **ABS**. Expect the temperature to show **260**. The log shows
   `_KARMAN_MMU_GATE_MAP_STOCK … MATERIAL=ABS … TEMP=260`, or the wrapper's line.
2. Change the **colour**. The temperature must **stay 260**.
3. Type temperature **255**, close, then change the **name**. It must **stay 255**.
4. Material → **PLA**. Expect **210**. Then set it back to the real filament.

Cross-check from the console after each step:

```
curl -s "http://192.168.1.240:7125/printer/objects/query?mmu=gate_material,gate_temperature"
```

## Verification

- [ ] Step 1 found no HH-internal caller that the wrapper would change.
- [ ] Offline renders match the Step 4 table.
- [ ] `FIRMWARE_RESTART` is clean.
- [ ] **Choosing ABS in Mainsail sets 260**, and **changing the colour afterwards keeps it**
      (the original bug). Confirmed by the maintainer and by the query in Step 6.
- [ ] An explicit typed temperature survives a later edit.
- [ ] `docs/decisions.md` entry written.

## Commit guidance

Git runs **only over SSH**. The maintainer runs commits. Propose:
1. `tools: let render_macro pass rawparams (and macro variables)` — `tools/render_macro.py`.
2. `fix: keep gate temperature on partial gate-map edits and fill it from the material` —
   `overrides.cfg`, `docs/decisions.md`, `TODO.md`, this runbook (moved to `docs/runbooks/done/`).

Decisions entry title:
`## 2026-MM-DD — MMU_GATE_MAP wrapper: gate temperature from material, kept on partial edits`.
It should record the root cause (the `TEMP` default in HH v3 and v4), why it's a wrapper and not
a patch, the table's source and why PETG precedes PET. Optionally suggest the maintainer file an
upstream Happy Hare issue with the two code references above.

## Status log

- **2026-10-10** — Runbook written (architecture session). Root cause confirmed from `mmu.log`
  and source. Wrapper scratch-rendered against the table in Step 4. Nothing applied yet.
