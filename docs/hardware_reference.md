# Hardware reference — as configured

The as-configured geometry and pin assignments for the current NightOwl / Happy Hare / Filamatrix /
Blobifier build, moved here verbatim from `TODO.md` on 2026-11-14 when task tracking moved to td.
The headings below carry the values. **The keep-out zones are also in the `CLAUDE.md` hazard
register, which is the authority** — if the two ever disagree, fix this file. Most of this hardware
is removed at INDX phase 3; rewrite or retire this file then.

## Filamatrix
### CURRENT geometry (relocated BACK-LEFT 2026-07-17): contact **15, 341** → compressed **0, 341**, cut plane **z=15** (clears the shaker arm; enforced by `min_toolchange_z: 15`). Validated by real swaps post-rework.

**Collision avoidance** — *no Klipper obstacle model exists; enforced by you:*
  - ⚠️ **FRONT-LEFT KEEP-OUT, PERMANENT (~x<10, y<17, all Z):** the Filamatrix **cutter arm strikes the front-left XY idler** — toolhead geometry, applies to every move.
  - ⚠️ **BACK-LEFT ZONE (x<~20, y>~335, below z15):** blobifier structures + relocated depressor. Enter only via the managed macros; manual jogs at low Z stay out.
  - ⚠️ **y_max FEATURE ROW** (tray x~2–17, shaker x4, rest x45, brush x53–88, all gantry/frame at y_max): approach in **+Y only through the clear lanes 15<x<40 or x>95**, then slide in X. `_KARMAN_PARK_MOVE` + retargeted CLEAN_NOZZLE handle this for parks/wipes.

## Blobifier
### Note: The bucket was reassembled and the optimum engagement point for the shaker arm is X = 3.0 mm and Z = 3.0 mm (SB is cradled within the shaker arm just right!)

## Nozzle brush
### As configured (authoritative — these are the live values): brush **x53–88** at **y_max**, centre 70.5 (`variable_brush_xyz: 70.5, 359, 1`); nozzle rest **x=45, y=359** (`park_pause` / `park_complete` / `SWAP`).
### Gantry-mounted ⇒ Z tracks the toolhead, so only the X slide seats/unseats the nozzle; approach y_max via the clear lanes (15<x<40 or x>95), never head-on.

## Filament sensor (BTT SFS v2) — REMOVED
- **Removed 2026-07-14** — drag corrupted the sync-feedback signal. Config commented out (not deleted); PC0/PC1 free. Re-add later **upstream** of the sync-feedback sensor after MMU relocation.

## Pin reference (new peripherals)
| Device | MCU | Pin |
|---|---|---|
| ~~SFS v2 runout~~ (removed) | Leviathan | PC0 (`RUNOUT_SENSOR`) — **free** |
| Blobifier bucket switch | Leviathan | PC1 (`MCU_STOP_X` → `BLOBIFIER_BUCKET`, NC→GND, was SFS motion) |
| Y endstop | Leviathan | PC2 (unchanged) |
| X endstop (relocated) | Nitehawk | PC15 (`PROBE_INPUT` / HV) |
| Pre-extruder switch | Nitehawk | PB0 (`MCU_ENDSTOP_X`) |
| Post-extruder switch | Nitehawk | PB1 (`MCU_ENDSTOP_Y`) |
| Blobifier servo | Leviathan | PC3 (`MCU_STOP_Z` → `BLOBIFIER_SERVO`, Z-STOP header; 5V from 24V buck) |
| ~~Blobifier servo (old plan)~~ | Leviathan | PF5 (EXT_7) — **free** |

---

# 📖 History — completed work

_Reference only; nothing below is actionable. Newest first. The durable **why** behind these
decisions lives in `docs/decisions.md`; per-objective execution records are in
`docs/runbooks/done/`._
