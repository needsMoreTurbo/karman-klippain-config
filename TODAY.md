# TODAY — validate the cutter, print with it, commit

Previous session's wins: 🎉 **first 2-color print** (Option A, tip forming), slicer fully configured
(`docs/mmu_slicer_setup.md`), cutter installed + enabled, flat cut verified at `residual 35`,
residual refined to **25** (unconfirmed), the `MMU_EJECT`-after-test failure root-caused.

> Mode: SSHFS mount — edits live after `FIRMWARE_RESTART`; git via SSH on the Pi only.
> ⚠️ **Never use `MMU_TEST_FORM_TIP`** on this machine — it strands the tip in the PTFE and lies to the
> state tracker (marks UNLOADED), which makes the next `MMU_EJECT` error. Test cuts with the loop below.
> State ever wrong? `MMU_RECOVER`, never hand-crank with `MMU_TEST_MOVE`.

## Step 1 — Confirmation cut at `residual 25`
The cut test loop (state-safe, tip inspectable):
```
T0            (hot; load if needed)
MMU_EJECT     (cut → full unload → release at gate)
```
- Console must show **`Retracting filament 30.0mm prior to cut`** (55 − 25 — proves the value's live).
- Pull the filament out at the NightOwl: **flat sheared face** = 25 confirmed. Pointy/formed = melt pool
  deeper than 25 → set `toolhead_residual_filament: 30`, restart, repeat.
- Reinsert the filament at the gate when done.

## Step 2 — Real swaps with the cutter
```
T0  →  T1  →  T0      (hot)
```
- Each swap should cut, unload, load the other gate, land at the nozzle. No errors, no `MMU_RECOVER` needed.
- Check the log line after each cut: *real* fragment accounting is net-based — expect a **small positive**
  "filament remaining" (~5–15 mm), not the −68 test artifact.

## Step 3 — Walk `retract_length` up (waste optimization, optional)
55 → 58 → 60 → 62, one confirmation cut each (Step 1 loop). Stop at the last reliably-flat value; each mm
gained is a mm less sliver left to purge per toolchange. Don't change residual at the same time.

## Step 4 — 🎯 2-color print WITH cutting
Same test model as the tip-forming print. Watch:
- **Swap blobs on the tower** — should be much smaller now (residual fix removed the ~30 mm over-advance;
  `ooze_reduction 2` also in play). Gaps after swaps instead → reduce `ooze_reduction` toward 0.
- **Color transitions** — the cut fragment adds purge load; muddy transitions → bump the Orca flushing
  multiplier a notch.
- **No false FlowGuard trips**; no state desyncs across many swaps.

## Step 5 — Commit the batch (SSH on the Pi)
Everything pending: cutter geometry + enable (`mmu_macro_vars.cfg`, `mmu_parameters.cfg` — residual/ooze/
retract saga), Option B park staging, `moonraker.conf` timeout, `variables.cfg` gate-check,
`docs/mmu_slicer_setup.md`, `docs/mmu_purge_volume.md` update if any, TODO/TODAY.
```
ssh ernst@192.168.1.240 'cd ~/printer_data/config && git status -s'
```
Ask Claude to propose the commit split + messages, or slice it yourself (config vs docs).

## Parked / watch
- **Extruder 0.45 A** — cut accounting cleared it of blame (test-mode arithmetic), but auto toolhead-cal slip
  still points at it. Bump `[tmc2209 extruder] run_current` in `overrides.cfg` to ~70–80% of the motor's
  rating if print/purge slip appears (motor rating still unknown).
- **Bed-shape exclusion** for the permanent front-left keep-out (~x<22, y<40 with depressor) — not yet
  notched into the Orca bed polygon.
- **Option B purge switch** (HH-owned, bin @ 0,358) — fully staged, 4-step procedure in
  `docs/mmu_slicer_setup.md`; do after the cutter print is solid.
- Later: nozzle wipe on existing brush, blobifier, NightOwl relocation + bowden re-cal, Spoolman.
