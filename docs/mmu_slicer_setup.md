# MMU slicer setup — OrcaSlicer checklist (Klippain + Happy Hare v3)

One checklist for the whole slicer-side setup. Sources: HH wiki
([Slicer-Setup](https://github.com/moggieuk/Happy-Hare/wiki/Slicer-Setup),
[Toolchange-Movement](https://github.com/moggieuk/Happy-Hare/wiki/Toolchange-Movement),
[Gcode-Preprocessing](https://github.com/moggieuk/Happy-Hare/wiki/Gcode-Preprocessing)),
mapped from the wiki's PrusaSlicer screenshots to OrcaSlicer names. ✅ = verified on Karman 2026-07-14.

**Key deviation from the HH wiki:** we do NOT paste the raw `MMU_START_SETUP` / `MMU_START_CHECK` /
`MMU_START_LOAD_INITIAL_TOOL` block. Klippain's `START_PRINT` already wraps those
(`_KLIPPAIN_MMU_INIT` + `_KLIPPAIN_MMU_LOAD_INITIAL_TOOL`); pasting them too would double-init.
Klippain doc: <https://github.com/Frix-x/klippain/blob/main/docs/mmu.md>

## Printer Settings → Machine G-code
- [x] **Machine start G-code** — existing `START_PRINT ...` call plus `INITIAL_TOOL=[initial_tool] TOOLS_USED=!referenced_tools!`
  (`!referenced_tools!` is resolved by the Moonraker preprocessor, not the slicer)
- [x] **Machine end G-code** — `END_PRINT` only. **Delete `MMU_END`** — Klippain's `END_PRINT` already runs
  `_MMU_PRINT_END` + `MMU_UNLOAD` (`mmu_unload_on_end_print: True`); keeping it = double unload
- [x] **Layer change G-code** — `_MMU_UPDATE_HEIGHT` + `SET_PRINT_STATS_INFO CURRENT_LAYER={layer_num}`
- [x] **Change filament G-code** — `T[next_extruder]` (nothing else)
- [x] **Pause G-code** — `PAUSE`

## Printer Settings → Multimaterial tab
- [x] **Single Extruder Multi Material: ON**; Extruders = 1; Manual Filament Change: off
- [x] **Wipe tower Type 2, "Purge in prime tower" ON** — slicer owns purging (matches `force_purge_standalone: 0`)
- [x] **Enable filament ramming: OFF** — HH forms the tip; the slicer must not ram
- [x] **Cooling tube position 0 / length 0.01, Filament parking position 0, Extra loading distance 0**
  (wiki: zero everything; the 0.01 dodges an old PrusaSlicer-lineage bug where 0 was rejected)
- [x] **High extruder current on filament swap: off** (HH manages currents)
- [x] *Tool change on wipe tower* — greyed out; multi-toolhead only, N/A for SEMM

## Printer Settings → Extruder tab  ← the ones we hadn't covered
- [x] **"Retraction when switching material" → Length (`retract_length_toolchange`) = 0** —
  this is the slicer's own toolchange retract; nonzero leaves the filament out of position for HH's tip forming
- [x] **"Retraction when switching material" → Extra length on restart (`retract_restart_extra_toolchange`) = 0** —
  the matching re-extrude after the swap; nonzero causes blobs (wiki: "turns off an initial retraction and
  subsequent extrude that will leave blobs")
- [x] Normal travel *Z-hop* can stay as-is. Orca has no separate "z-hop on toolchange" (that's PrusaSlicer);
  HH does its own toolchange z-hop via `z_hop_height_toolchange` / sequence-macro vars

## Filament settings → Multimaterial tab (each MMU filament profile)
- [x] **All "Tool change parameters with single extruder MM printers" = 0** — loading/unloading speeds,
  delay, cooling moves + speeds, stamping. HH owns tip forming end-to-end. (Timing-only fields may stay)
- [x] **Ramming parameters** — irrelevant while ramming is OFF at printer level; don't bother editing
- [x] **Minimal purge on wipe tower** — default 15 mm³ is fine as a floor
- [ ] **Chamber temperature = 0** on every MMU filament profile ⚠️ — Orca's *"Activate temperature control"*
  toggle only suppresses `M141`/`M191`; it does **not** zero the value, and our start g-code passes
  `CHAMBER=[chamber_temperature]`. Any nonzero value makes Klippain's `chamber_soak` action block START_PRINT
  for up to **15 min** (`print_default_chamber_max_heating_time`) with **0.0 tolerance** — and Karman's
  toolhead-mounted chamber sensor reads warm/noisy, so it may never satisfy the target and always burns the
  full timeout. Chamber thermal behavior is owned by `bed_fans.cfg`, not a START_PRINT setpoint.
- [ ] **One filament slot per gate** — Prepare tab → Filament panel → “+” to add slot 2; assign a profile +
  color swatch per slot (slot 1 = T0/gate 0, slot 2 = T1/gate 1). Drives `[filament_type]`, `!temperatures!`, `!colors!`.
  ⚠️ After first slice, check the exported `START_PRINT` line: with 2 filaments, `MATERIAL=[filament_type]` may expand
  to a joined list (`ABS;ABS`) and break Klippain's material lookup — if so use `MATERIAL={filament_type[initial_tool]}`

## Process settings → Multimaterial tab
- [x] **Prime tower: Enable ON** (+ Skip points ON) — width 60, brim 3, rib wall/fillet, max speed 90 mm/s
  all fine for the first print
- [x] **Ooze prevention: OFF** — it lowers standby temps for idle tools; wrong for a single-extruder MMU
  (HH manages temps)
- [x] **Flush options** — "into objects' support" ON (purge waste lands in discarded supports, saves filament);
  "into objects' infill" OFF (safer: flushed infill can show through thin walls)
- [x] "Filament for Features" all Default; beam interlocking / interface shells off

## Prepare tab (per project)
> ⚠️ **PERMANENT front-left keep-out (~x<10, y<17, all Z):** the Filamatrix **cutter arm on the toolhead
> strikes the front-left XY idler**. Toolhead geometry ⇒ applies to every move (print, travel, park, purge,
> brush, homing), independent of the depressor. Klipper will not stop it — you enforce it.
- [x] **Prime tower placement clear of keep-outs** — drag the tower away from the front-left keep-out above
  (and from the depressor zone once it's reinstalled)
- [x] **Flushing volumes matrix** (Filament panel → Flushing volumes) — adjust via the **Multiplier** + Re-calculate,
  not per-cell edits (auto-recalc can overwrite manual cells). Orca's base assumes a normal melt zone; the Rapido
  V2 UHF + extender needs more: **start multiplier ~0.6–0.8** (e.g. black→teal ~109→~220–290 mm³). Iterate off the
  tower: muddy color after swap → raise; clean + tall tower → lower by 0.1 steps

## Moonraker / Klipper side (prerequisites)
- [x] `[mmu_server] enable_file_preprocessor: True` in moonraker.conf (resolves `!...!` placeholders)
- [x] `variable_mmu_check_gates_on_start_print: True` in variables.cfg (pairs with `TOOLS_USED`)
- [x] `[file_manager] default_metadata_parser_timeout: 120` — added to root `moonraker.conf` (merges with the
  framework's `[file_manager]`; needs a **Moonraker restart**, not FIRMWARE_RESTART)
- [ ] Optional (later): `variable_restore_xy_pos: "next"` in mmu_macro_vars.cfg — toolhead travels directly to
  the next print position after a swap instead of returning to where the toolchange was issued.
  (`enable_toolchange_next_pos: True` is **already set** in moonraker.conf, so this is just the one macro-var flip)
- [ ] Optional (later): feed HH the purge matrix even in slicer-purge mode — add a supplemental
  `MMU_START_SETUP ... PURGE_VOLUMES=!purge_volumes! TOOL_COLORS=!colors! ...` line before `START_PRINT`
  (needed only if we later switch to HH-owned purging; see `docs/mmu_purge_volume.md`)

## Switching to Option B later (HH-owned purge into the back-left bin)
Currently **Option A**: slicer wipe tower owns purging. To switch:
1. `mmu_macro_vars.cfg` → swap which `variable_park_toolchange` line is commented (both are staged in-file):
   `0, 358, 1, 5, 2` = **back-left purge bin**. `_MMU_PURGE` purges in place, so the park position *is* the
   purge location. Must stay `-999,-999` under Option A (else the head detours to the bin and back to the
   tower every swap). Depressor is currently removed, so 0,358 is clear — re-verify when it's reinstalled.
2. `mmu_parameters.cfg` → `force_purge_standalone: 1`
3. OrcaSlicer → wipe tower **OFF**
4. Feed the purge matrix via the supplemental `MMU_START_SETUP ... PURGE_VOLUMES=!purge_volumes!` line above —
   otherwise `V_slicer = 0` and purge collapses to residual-only (~5 mm). See `docs/mmu_purge_volume.md`.
5. Finer-grained staging (for the optimized cut→blobifier→shake→wipe sequence) uses
   `variable_post_form_tip_position` / `variable_pre_load_position` rather than one park position.

## Known caveat
- **Klippain's MMU macros target HH v2.x; we run v3.4.2.** Core flow works, but
  `_KLIPPAIN_MMU_SET_CLOGDETECTION` reads `printer.mmu.clog_detection`, which v3 removed (FlowGuard now).
  Not hit in START_PRINT; may surface on in-print pause/toolchange paths — verify before unattended prints.

## References
- Purge math: `docs/mmu_purge_volume.md` · Klippain MMU: <https://github.com/Frix-x/klippain/blob/main/docs/mmu.md>
- HH wiki: [Slicer-Setup](https://github.com/moggieuk/Happy-Hare/wiki/Slicer-Setup) ·
  [Toolchange-Movement](https://github.com/moggieuk/Happy-Hare/wiki/Toolchange-Movement) ·
  [Gcode-Preprocessing](https://github.com/moggieuk/Happy-Hare/wiki/Gcode-Preprocessing)
