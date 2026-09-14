# PETG Unload Stall — Nightowl MMU + Filamentalist Rewinder

**Status:** Open — root cause understood mechanistically, fix not yet selected
**Printer:** Karman (Voron 2.4 R2, 350mm)
**Subsystem:** Nightowl 2-gate MMU / Happy Hare / Filamentalist rewinder
**Bowden length:** ~1500 mm calibrated

---

## 1. Symptom

| Material | Unload speed | Result |
|---|---|---|
| ABS | 80 mm/s | OK |
| PETG | 80 mm/s | Stall |
| PETG | 70 mm/s | OK |

Stall occurs **partway through** the unload, not at the start. Adjusting Filamentalist
tensioner preload moved the stall point further into the move but did not eliminate it.

**Trial log** (stall distance ≈ tip distance above toolhead − 150 mm, assuming the 150 mm slow
homing that follows the fast move ran fully, as observed on 09-12):

| Date | Gate (spool) | Tension | Speed | Result | Tip above toolhead | ≈ Stall into fast move |
|---|---|---|---|---|---|---|
| 09-12 20:40 | 0 | original | 80 | stall | 200–300 mm | ~50–150 mm |
| 09-14 16:53 | 0 (less full) | loosened +1.5 turns | 80 | ✅ clean (19 s fast move) | — | — |
| 09-14 16:55 | 1 (fuller) | loosened +1.5 turns | 80 | stall — high-pitched buzz, filament **taut** | ~500 mm (measured: recovery homed to gear sensor after 984.2 mm of a 1448 mm bowden ⇒ ~464 mm) | ~315 mm |

| 09-14 17:22–17:40 | 1 ×3, 0 ×2 | loosened +1.5 turns | **70** | ✅ **5/5 clean** (fast moves 21 s; gate-1 homing 76–79 mm) | — | — |

The buzz confirms loss of sync (not gear-on-filament slip). Taut at +1.5 turns ⇒ still not slack.

**Resolution (2026-09-14):** `gear_unload_speed: 80 → 70` persisted in `mmu_parameters.cfg`, with the
rewinder left at +1.5 turns looser. Status stays **mitigated, not root-caused** — test #2 (rewinder
disconnect) was not run, and margin at 70 is demonstrated on one spool pair only. Fallback: 60.

**Failure mode: confirmed as gear stepper losing sync** (not gear-on-filament slip, not a
Happy Hare sensor timeout).

> Note: BTT SFS V2 is **not installed**. No encoder in the path, so commanded-vs-measured
> length comparison is unavailable as a diagnostic. Failure mode was identified by other means.

---

## 2. Root cause mechanism

The dominant load on the gear motor during unload is **spool rewind force**, not PTFE
friction in the bowden. PTFE drag is a small additive term; the rewind path is the actual
torque budget.

### 2.1 Filamentalist kinematics

- Filament is pinched by a spring-loaded tensioner arm against two o-rings on a drive roller
  of fixed radius `r_roller`.
- The roller shaft couples to the spool axle through a **one-way bearing**: locked in the
  unload direction, freewheeling during load/print.
- During unload, filament moving at axial velocity `v` spins the roller at `ω = v / r_roller`.
  The locked clutch drives the spool at that same `ω`.

### 2.2 The structural ratio mismatch

To take up filament at rate `v`, the spool must turn at:

```
ω_req = v / R          where R = current winding radius (varies with fill level)
```

But the rewinder delivers a **fixed** ratio:

```
ω_actual = v / r_roller
```

`r_roller` is constant; `R` is not. The two cannot both be satisfied. Since `r_roller << R`
for any realistic fill level, the rewinder **over-drives** the spool — it commands more
rotation than the filament being fed back actually requires.

### 2.3 The o-rings are the compliance element

The o-rings exist to absorb that ratio error. They grip up to a threshold, then slip.

- Tensioner screw sets normal force `N`
- Slip threshold ≈ `μ · N`, where `μ` = filament-surface / o-ring friction coefficient
- Vendor-documented behavior: **full spool = max slip** (largest `R`, biggest mismatch);
  **empty spool = minimal slip**

### 2.4 Why the motor stalls

The one-way clutch is locked during unload, so **the MMU gear motor supplies the torque that
turns the spool**, reflected back as axial force on the filament through the o-ring traction
interface. The motor fights:

- the spool's demand (inertia, bearing drag, rewind work) while the o-rings grip
- capped at the slip threshold once they let go

### 2.5 Where material enters

Same spring, same normal force `N` — but PETG and ABS present **different surface friction
coefficients at the o-ring nip**, hence different slip thresholds on an otherwise identical
setup.

If PETG grips the o-rings harder (higher `μ`), more spool load is transmitted to the motor
before slip relieves it.

### 2.6 Fault chain

```
PETG raises slip threshold at o-rings
  → more spool-rewind load reaches gear motor as axial force
  → at 80 mm/s, available motor torque (reduced by back-EMF at that step rate)
    falls below demand
  → loss of sync
```

Dropping to 70 mm/s recovers torque margin. Loosening the tensioner lowers the transmitted
force ceiling directly.

**Confidence: high** on the mechanism. **Medium** on PETG-vs-ABS μ at the o-ring specifically
— no measured values found, inferred from behavior.

---

## 3. Torque-speed side of the budget

Stepper torque falls with step rate as back-EMF and winding inductance choke current
establishment:

```
I_available ~ V / (R + ω·L_eff)
```

Past corner speed, torque drops roughly as `1/ω`. From 70 → 80 mm/s that is ~12% less torque
— arriving exactly when the load went up. The 80 mm/s ABS setting was running with thin
margin, not comfortable margin.

---

## 4. Open questions

1. ✅ **Tensioner adjustment direction — LOOSENED** (user, 2026-09-14), and the stall moved later.
   Consistent with §2: lower `N` lowers the force the nip passes to the motor.

2. **Why does it stall partway rather than at the start?** Partly narrowed (2026-09-14):
   - **Not the accel ramp.** `gear_unload_accel: 100` reaches 80 mm/s after 32 mm; the 09-12 stall
     left the tip 200–300 mm above the toolhead, i.e. at most ~300 mm into a ~1400 mm move.
   - **Not slack pile-up.** Filament between gate and spool was **taut** after the stall (user), so
     "spool lags, filament buckles in the rear tube" is ruled out.
   - **A rising mean load isn't required.** With thin torque margin, a *periodic* load bump trips
     loss of sync at whichever bump first exceeds the margin — so the stall point is partly random,
     and lowering the whole load (loosening) pushes it later on average. A **once-per-spool-revolution**
     disturbance (out-of-round spool, flange rub, holder bind) fits a stall inside the first
     revolution — roughly 600 mm of filament on a full 200 mm-OD spool. *Candidate, untested.*
   - **The log cannot locate a stall:** the fast move always logs its full duration whether or not the
     stepper kept sync. **Record tip position after every stall** — widely scattered positions favour
     the periodic-disturbance story; consistent positions favour a load that rises with distance.

3. **Spool-state confound — supported.** Gate 1's spool is fuller than gate 0's (user, 2026-09-14),
   and 3 of 4 stalls at 80 mm/s were gate 1 (09-12 19:32, 09-13 14:09, 09-14 16:03; gate 0 on
   09-12 20:40). A full spool is the documented worst case, so **tune against gate 1 as it is now** —
   whatever passes there only gets easier as the spool empties.

---

## 5. Diagnostic tests

| # | Test | Discriminates |
|---|---|---|
| 1 | Run ABS gate at 80 mm/s with spool at same fill state as the PETG spool | Material effect vs. spool-state confound |
| 2 | Unload with filament path disconnected from the rewinder entirely | Rewind load vs. everything else. If it sails at 80, rewinder is confirmed limiting |
| 3 | ~~Reduce `gear_from_buffer_accel`~~ — wrong knob; unloads read `gear_unload_accel` (`mmu.py:5578–5583`). Largely moot: ramp ends at 32 mm, stall is ~100–300 mm in | Accel-limited vs. velocity-limited |
| 4 | Dry the PETG spool, retest at 80 | Moisture swelling contribution |
| 5 | Listen for the signature | HH docs: motor starts, **whistles** during main move, then catches up on decel = losing steps on a single move |

---

## 6. Candidate fixes

### Mechanical (attacks the load)

- **Loosen Filamentalist tensioner.** Vendor guidance: set slip force *slightly* above overall
  system drag, err light, increase in ~1/2 turn increments only until unload packs tightly.
  Over-tension is a documented failure mode — the arm can't lift to allow slip when needed.
- **Increase bowden ID to 3 mm.** Vendor recommends 2.5 mm ID as baseline, **3 mm for
  long/high-resistance paths**. At ~1500 mm this setup qualifies.
- **Minimize path length and bends** between Filamentalist and MMU.
- **Verify one-way bearing** rotates freely in the unlocked direction (rework procedure exists
  in the ERCF_v2 troubleshooting doc if draggy).

### Firmware / config (attacks the torque margin)

- ✅ **Gear stepper microsteps — already 16 on both gears** (live `configfile`, 2026-09-14), HH's
  recommendation. Not a lever: torque loss at speed follows shaft RPM, not step count.
- ✅ **StealthChop — already off:** `stealthchop_threshold: 0` on both gear drivers (live config).
- ✅ **Speed parameter — no config bug.** Unloads read `gear_unload_speed` / `gear_unload_accel`
  (`mmu.py:5578–5583`); `gear_from_spool_*` / `gear_from_buffer_*` are load-only.
  `MMU_TEST_CONFIG GEAR_UNLOAD_SPEED=n` applies live (same attribute the move reads; resets on restart).
- **Per-gate speed override.** `gate_speed_override` — a percentage, per gate, persisted in
  `mmu_vars.cfg`, also settable as an array in `mmu_parameters.cfg`. Set the PETG gate to ~85%
  and leave ABS/ASA at 100% rather than derating globally.
  *Keyword verified: `MMU_GATE_MAP GATE=n SPEED=85` (10–150, persisted; `mmu.py:8628`).*
  ⚠️ **Not unload-only:** it scales speed **and accel** of *every* gear move on that gate — loads,
  homing, synced moves (`mmu.py:5614–5618`) — and is per gate, not per material. With PETG in both
  gates it is a global derate with side effects; `gear_unload_speed` is the narrower knob.

### Recommended order (revised 2026-09-14)

1. ~~Microsteps~~, ~~StealthChop~~ — verified already correct
2. **Loosen the tensioner further in ½-turn steps** — it helped once, and taut filament after the
   stall shows there is still no slack, so the floor hasn't been reached. Stop at the first sign of
   loose winding / slack on the spool, then back off ½ turn. Test each step at 80 mm/s on **gate 1**
   (full spool = worst case), recording tip position on any stall.
3. Test #2 — rewinder disconnect, if step 2 runs out of room without passing
4. Persist `gear_unload_speed` at whatever passes with margin (fallback 60 — ~15% more torque than 70,
   ~3 s longer per unload)

---

## 7. Retracted / weakened hypotheses

Recording these so they don't get re-litigated:

- **"PETG has higher sliding friction against PTFE than ABS."** No supporting evidence found.
  Counter-indication: a Prusa thread on PETG-specific extruder squeal argues PTFE won't produce
  a friction squeak against most materials (static and dynamic μ are similar and low), and
  attributes the noise to PETG-on-PETG contact instead. Suggests material-pair differences live
  at **non-PTFE contact points** — o-rings, printed gate and guide parts — which is consistent
  with the rewinder being the culprit. **Dropped.**

- **"Filamentalist spring winds tighter as it takes up filament, giving monotonically rising
  resistance."** Wrong mechanism. It's an o-ring slip clutch driven by the gear motor through a
  one-way bearing, not a spiral-spring rewinder. **Corrected — see §2.**

- **Tg / chamber-temperature softening.** PETG Tg ~80 °C vs ABS ~105 °C, chamber runs 55–65 °C,
  so PETG has much less margin and could soften against tube walls. Materials argument still
  stands, but **no community reports found** of this causing MMU unload stalls. **Demoted below
  the spool test and microstep check.** Cheap to test: run the same unload with a cold chamber.

- **Cut tip geometry.** FilamATrix bypasses tip-forming, but PETG is ductile where ABS is
  brittle — a blade that shears ABS cleanly can flare PETG. A flared tip drags the full 1500 mm.
  **Not ruled out; cheap to check** — pull one manually and inspect the end face. Lower priority
  given the confirmed loss-of-sync failure mode.

- **Moisture.** PETG is notably more hygroscopic than ABS; swelling increases tube friction.
  **Holds up, still worth ruling out** (test #4).

---

## 8. Sources

- Filamentalist Rewinder (Carrot Collective) — mechanism and tensioner tuning:
  https://github.com/Carrot-collective/Filamentalist_Rewinder
- Filamentalist troubleshooting (ERCF_v2) — over-tension failure mode, 3 mm ID recommendation:
  https://github.com/Enraged-Rabbit-Community/ERCF_v2/blob/master/Recommended_Options/Filamentalist_Rewinder/troubleshoot.md
- Filamentalist (SkiBikePrint) — one-way clutch / o-ring drive description:
  https://github.com/SkiBikePrint/Filamentalist
- Happy Hare — Troubleshooting and Common Issues (microsteps, whistle signature):
  https://github.com/moggieuk/Happy-Hare/wiki/Troubleshooting-and-Common-Issues
- Happy Hare — Configuring mmu_parameters.cfg (speed parameters, lost-step signature):
  https://github.com/moggieuk/Happy-Hare/wiki/Configuring-mmu_parameters.cfg
- Happy Hare — Basic Operation (`gear_from_spool_speed` vs `gear_from_buffer_speed`):
  https://github.com/moggieuk/Happy-Hare/wiki/Basic-Operation
- Happy Hare — Tool and Gate Maps (`gate_speed_override`):
  https://github.com/moggieuk/Happy-Hare/wiki/Tool-and-Gate-Maps
- Bambu forum — PETG-only AMS unload failures, resolved with added spool weight (different
  mechanism, but localizes to the spool interface):
  https://forum.bambulab.com/t/ams-and-petg/37673
- Prusa forum — PETG extruder squeal attributed to PETG-on-PETG, not PTFE:
  https://forum.prusa3d.com/forum/original-prusa-i3-mk3s-mk3-user-mods-octoprint-enclosures-nozzles/fix-for-squeaky-extruders-especially-when-printing-petg/
