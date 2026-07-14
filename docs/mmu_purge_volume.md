# MMU filament-change purge (standard `_MMU_PURGE`)

How much filament Happy Hare pushes out of the nozzle on a tool change, and how it's computed.
Scope: the reference `_MMU_PURGE` macro only (Blobifier ignored). Source: HH 3.4.2
`extras/mmu/mmu.py` + `mmu/base/mmu_purge.cfg`.

## Symbols
| Symbol | Meaning | Where set |
|---|---|---|
| `d` | filament diameter (1.75 mm) | `[extruder] filament_diameter` |
| `A` | filament cross-section = `π·(d/2)²` ≈ **2.405 mm²** | derived |
| `V_slicer` | slicer purge-matrix volume for transition `from→to` (mm³) | slicer tool map (see below) |
| `L_res` | `toolhead_residual_filament` — melt left in nozzle after unload | `mmu_parameters.cfg` |
| `L_frag` | `filament_remaining` — **cut fragment** left in extruder; **0 for tip forming** | computed per unload |
| `V` | `toolchange_purge_volume` (mm³) | computed |
| `L_purge` | purge length actually extruded (mm) | computed |

## 1. Purge volume  (`_calc_purge_volume`, mmu.py:1153)

```
V = V_slicer + A · (L_frag + L_res)
```

- `V_slicer` comes from the slicer's per-transition purge matrix. **If no matrix is loaded, `V_slicer = 0`.**
  If the source tool is unknown, HH uses the worst case `V_slicer = max over rows of matrix[*][to]`.
- The second term is *always* added — it accounts for material already in the melt zone / a cut fragment,
  which must be flushed to get clean color.

## 2. Volume → length  (`_MMU_PURGE`, mmu_purge.cfg)

```
A         = (d/2)² · π
L_purge   = V / A
          = (L_frag + L_res) + V_slicer / A
```

So with **no slicer matrix** (`V_slicer = 0`): `L_purge = L_frag + L_res`.
For **tip forming** (`L_frag = 0`): `L_purge = L_res` exactly.

> Worked example (our MMU_TEST_PURGE with tip forming, no slicer map, `L_res = 38`):
> `L_purge = 0 + 38 = 38 mm`, `V = 2.405 · 38 = 91.4 mm³` — matches the console output exactly.
> (With `L_res = 5` now: `L_purge ≈ 5 mm`.)

## 3. Tip forming vs. tip cutting → `L_frag`  (mmu.py:5479–5508)

`L_frag` is the only difference between the two tip methods:

- **Tip forming** — macro reports no park position → `L_frag = 0`. Purge covers only `L_res` (+ slicer).
- **Tip cutting** (Filametrix) — macro reports `output_park_pos` → a rigid fragment is left past the gears:
  ```
  L_frag = park_pos − stepper_movement − L_res − toolchange_retract
  ```
  That fragment adds to the purge so the leftover cut piece is flushed before the new color prints.

## 4. What the load side does with the same numbers  (mmu.py:4870)

The *next* load is shortened by everything already sitting in the path, so you don't over-stuff the nozzle:
```
D        = toolhead_sensor_to_nozzle   (with toolhead sensor; else toolhead_extruder_to_nozzle)
L_load   = max(D − L_frag − L_res − toolhead_ooze_reduction − toolchange_retract, 0)
```
This is why an over-stated `L_res` under-loads the nozzle (the failure we hit at `L_res = 38`).

## 5. `_MMU_PURGE` macro sequence
1. Un-retract HH's toolchange retract (`retracted_length`).
2. Purge `L_purge` in **2 mm segments** (so a clog/pause can interrupt between segments) at
   `_MMU_PURGE_VARS.extruder_purge_speed`.
3. Re-retract `retracted_length`.
4. `MMU_SYNC_FEEDBACK ADJUST_TENSION=1` — neutralise tension so FlowGuard doesn't false-trip on resume.

Purge extruder current is boosted during the move via `extruder_purge_current` (%).

## 6. Standalone vs. slicer — when `_MMU_PURGE` actually runs  (mmu.py:6842)

```
do_purge = STANDALONE                       # default → call purge_macro (_MMU_PURGE)
if skip_purge:                do_purge = NONE
elif printing and not (standalone or force_purge_standalone):
                              do_purge = SLICER   # HH defers to slicer wipe/purge tower
```

| Situation | `force_purge_standalone` | Who purges |
|---|---|---|
| Not printing (console `Tx`, `MMU_TEST_PURGE`) | any | **HH `_MMU_PURGE`** |
| In a print | `0` (default) | **Slicer** wipe/purge tower |
| In a print | `1` | **HH `_MMU_PURGE`** — *you must turn the slicer wipe tower OFF or you double-purge* |

## 7. Feeding HH the slicer's purge matrix (`V_slicer`)
Two ways to populate `slicer_tool_map.purge_volumes`:
- **From the slicer**, via g-code preprocessing that emits `MMU_SLICER_TOOL_MAP ... PURGE_VOLUMES=...`
  (the slicer's own wipe-volume matrix). See the g-code preprocessing wiki below.
- **From filament colors**: `MMU_CALC_PURGE_VOLUMES MULTIPLIER=..` builds a matrix from color differences
  when the slicer didn't provide one.

Until either is set, `V_slicer = 0` and purge = residual/fragment only (section 2).

## References (Happy Hare wiki)
- Purge / tip forming / residual-filament calibration: <https://github.com/moggieuk/Happy-Hare/wiki/Blobbing-and-Stringing>
- Slicer purge matrix / g-code preprocessing: <https://github.com/moggieuk/Happy-Hare/wiki/Gcode-Preprocessing>
- Slicer setup & toolchange movement: <https://github.com/moggieuk/Happy-Hare/wiki/Slicer-Setup>
