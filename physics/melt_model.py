#!/usr/bin/env python3
"""Lumped melt-zone model — predicts the BDPressure trace for a PA_E step.

Pure stdlib, no dependencies. Run it and it writes physics/melt_model_out.json.

WHY THIS EXISTS
    Before running a calibration sweep we want a prediction of what the sensor *should*
    show at each flow rate and pressure-advance value. If the measurement disagrees with
    a physically reasonable model, that is information; if we only look at data after the
    fact, every result looks explicable.

THE MODEL
    The melt zone is a compliance (a squishy reservoir) feeding a resistance (the nozzle):

        Q_in(t)  = A_fil * v_cmd(t)             extruder pushes filament in
        Q_out(P) = (P / K) ** (1/n)             polymer squeezes out of the nozzle
        dP/dt    = (Q_in - Q_out) / C           pressure is what the reservoir holds

    Q_out is a power law rather than linear because molten polymer is SHEAR-THINNING:
    push it harder and its apparent viscosity falls. That single non-linearity produces
    most of the interesting behaviour — in particular a response time that shortens as
    flow rises, which is why one PA value cannot be right at every flow.

    Pressure advance is Klipper's model, applied to the commanded filament motion:

        v_cmd = v_nominal + PA * a_nominal

    i.e. during acceleration PA pushes extra filament in, during deceleration it pulls
    some back. The whole calibration is a search for the PA that makes those two exactly
    cancel the reservoir's lag.

    The gauge reads force, which is pressure times an area, so the reported ADC value is
    taken as (baseline - P). Pressure therefore appears as a DIP, matching the hardware.

CALIBRATION
    Parameters are FITTED to captured waveforms by fit_model.py, not derived analytically.
    See the constants below for provenance and the one that is NOT constrained by the data.
    Run `python3 fit_model.py` to reproduce; it prints an identifiability check first, which
    is what stops the fit wandering somewhere unphysical.

    The model is here for TRENDS: direction, relative size, and how things move with flow
    and PA. It is not a characterised rheology.

THE ONE THAT MATTERS — NO SLOW RELAXATION, SO NO PLATEAU ASYMMETRY
    A single compliance gives this model a memory of ~20 ms. The slow segments either side of the
    spike last 1.6 s, roughly 80 time constants, so pressure fully re-settles and the two settled
    levels come out IDENTICAL: the model's settled asymmetry is 0.00 + 0.0*PA at every PA.

    The hardware disagrees, and not marginally: measured on settled plateaus it is
    -0.42 - 12.5*PA counts at 14.4 mm3/s, a slope 7.3 sigma from zero. Something in the real
    system remembers the spike's retraction for over a second — a slow relaxation mode, which is
    what a real polymer melt has and a single lumped element does not.

    CAREFUL, TWO DIFFERENT QUANTITIES SHARE THIS NAME. The above is the difference of SETTLED
    plateau levels. The firmware's `Hr - Hl` is NOT that: it finds H_left/H_right by a local
    MAXIMUM search near the dip edges, so it samples transient points. The two correlate only
    r = 0.69 on the same 41 steps, and the firmware's has ~4x the dynamic range. It is also the
    one that works: on the 2026-08-13 sweep the firmware metric crossed zero cleanly at PA 0.031,
    while the settled-plateau metric never crossed zero at all, at any flow we have captured.

    So reproducing the firmware's discriminator needs more than a slow mode — it needs the
    transient SHAPE near the dip edges to be right. Until then this model can describe the
    pressure trace but cannot predict what a calibration sweep will conclude from it.

OTHER SIMPLIFICATIONS
    - Nozzle resistance is isothermal; in reality the melt cools slightly at high flow, and at
      25 mm3/s the model over-predicts PA sensitivity by 1.8x, which may be this.
    - No filament-column compliance or gear slip: the commanded burst is assumed delivered.
    - Klipper's junction-deviation cornering is reduced to a plain acceleration limit, and its
      pressure_advance_smooth_time is not modelled at all.
    - No sensor mechanics: the gauge and its mount are assumed infinitely stiff and fast.
"""

import json
import math
import os

# ---------------------------------------------------------------------------
# machine + material constants
# ---------------------------------------------------------------------------
FILAMENT_D   = 1.75
A_FIL        = math.pi / 4 * FILAMENT_D ** 2      # 2.405 mm^2
E_PER_MM     = 0.046                              # PA_E extrudes 0.046 mm filament per mm of travel
SAMPLE_HZ    = 87.4                               # measured ADS1220 output rate
ADC_SMOOTH   = 1                                  # extra smoothing on top of the ADC, in samples.
                                                  # 1 = none, and none is right: the ADS1220
                                                  # integrates over each conversion already, so a
                                                  # boxcar on the decimated stream double-counts.
                                                  # The measured 23 ms 10-90 rise is under two
                                                  # sample periods, which a 3-sample average
                                                  # cannot produce at all.
BASELINE_ADC = 6598                               # measured quiescent level

# Melt parameters, FITTED by fit_model.py against all 50 PA steps of the 14.4 mm3/s sweep
# (2026-08-13). Every one of the five fitted features lands within 1 sigma of the measurement.
#
# Do NOT re-derive these from a two-point analytic fit. That route treats the fast-segment spike as
# a steady-state value, which it is not, and drives n to 1.0 — where tau = C*K*n*Q^(n-1) loses its
# Q term entirely and the model's central mechanism switches itself off. calibrate() below is kept
# as documentation of that trap.
#
# Nor fit them against whole-trace RMS: ~88% of a trace is plateau, which pressure advance does not
# affect, so RMS pays an optimiser to abandon the spike. That produced a set with a better score
# and a PA response of +5% against a measured +85%.
N_SHEAR = 0.653
K_PRESS = 3.939
C_COMPL = 0.02043

# Rate-INDEPENDENT force present whenever filament moves — friction of the filament through the
# heatbreak, plus the melt's entrance pressure. Not part of the original model, added because the
# data demanded it: the apparent exponent of P vs Q rises with flow (0.32 -> 0.58 -> 0.72 across
# the four measured flows), which a pure power law cannot do and an additive offset explains
# exactly. P = F0 + K*Q^n fits all four to 0.09 counts against 0.77 for the power law alone.
#
# Verified as force, not as a zeroing artifact: during the 300 mm/s travel move with no extrusion
# the gauge reads -0.5 +- 0.4 counts, the same as standing still, so toolhead motion contributes
# nothing and the extruding levels are not sitting on a shifted zero.
F_STATIC = 2.31
V_FRIC = 0.05            # filament speed (mm/s) over which that friction reverses with direction

DT = 50e-6                                        # integration step, 50 us

# PA_E geometry at SCALE = 1 (the vendor's fixed pattern)
SEG_SLOW_MM = 20.0
SEG_FAST_MM = 40.0
TRAVEL_MM   = 80.0
TRAVEL_MMS  = 300.0


def segment_plan(max_volumetric, scale, accel):
    """Commanded XY speed as (duration, target_speed, extruding) over one PA_E step."""
    low_mms  = 51.0 * max_volumetric / 60.0       # PA_CALIBRATE: low_speed  = 51*MV  mm/min
    high_mms = 537.0 * max_volumetric / 60.0      # PA_CALIBRATE: high_speed = 537*MV mm/min
    return [
        (0.40,                                   0.0,        False),  # settle, shows baseline
        (TRAVEL_MM * scale / TRAVEL_MMS,         TRAVEL_MMS, False),  # travel back, no extrusion
        (SEG_SLOW_MM * scale / low_mms,          low_mms,    True),
        (SEG_FAST_MM * scale / high_mms,         high_mms,   True),
        (SEG_SLOW_MM * scale / low_mms,          low_mms,    True),
        (1.00,                                   0.0,        False),  # dwell/overhead
    ], low_mms, high_mms


def integrate(max_volumetric, pa, scale=1.0, accel=3000.0):
    """Integrate one PA_E step at DT resolution. Returns the continuous gauge force, unsampled.

    Split out from simulate() because ADC SAMPLING PHASE matters: the spike is only a few sample
    periods wide, so where the ADC's grid happens to land relative to the peak changes the
    recorded peak by 2-3 counts — a quarter of the whole pressure-advance signal. The hardware
    randomises that phase from step to step, and it is part of the measured scatter. To predict
    the EXPECTED peak, sample this one integration at several phases and average
    (fit_model.model_features() does exactly that). Integrating once and sampling many times keeps that
    free; the integration is the expensive part.
    """
    plan, low_mms, high_mms = segment_plan(max_volumetric, scale, accel)

    v_xy = 0.0          # current XY speed  (mm/s)
    press = 0.0         # melt pressure, in ADC counts
    t = 0.0
    raw_t, raw_p = [], []

    for dur, target, extruding in plan:
        steps = max(1, int(round(dur / DT)))
        for _ in range(steps):
            # --- acceleration-limited approach to the commanded speed ---
            dv_max = accel * DT
            if v_xy < target:
                v_xy = min(target, v_xy + dv_max)
            elif v_xy > target:
                v_xy = max(target, v_xy - dv_max)
            a_xy = (target - v_xy) / DT
            a_xy = max(-accel, min(accel, a_xy))

            # --- commanded filament motion, with pressure advance ---
            if extruding:
                v_fil = E_PER_MM * v_xy
                a_fil = E_PER_MM * a_xy
            else:
                v_fil = a_fil = 0.0
            v_cmd = v_fil + pa * a_fil            # <- Klipper's pressure advance

            # --- reservoir: what goes in, minus what escapes the nozzle ---
            q_in = A_FIL * v_cmd
            q_out = (max(press, 0.0) / K_PRESS) ** (1.0 / N_SHEAR)
            press += (q_in - q_out) / C_COMPL * DT
            press = max(press, 0.0)               # the melt cannot pull a vacuum

            # what the gauge feels: melt pressure plus rate-independent friction, which acts
            # against whichever way the filament is currently moving
            force = press + F_STATIC * math.tanh(v_cmd / V_FRIC)

            raw_t.append(t)
            raw_p.append(force)
            t += DT

    return raw_p, plan, low_mms, high_mms


def sample(raw_p, phase=0):
    """Sample a raw force trace the way the ADC does: decimate, smooth, quantise to counts."""
    step = int(round(1.0 / SAMPLE_HZ / DT))
    samp = [raw_p[i] for i in range(phase, len(raw_p), step)]
    out = []
    for i in range(len(samp)):
        w = samp[max(0, i - ADC_SMOOTH + 1): i + 1]
        out.append(sum(w) / len(w))
    return out, step


def simulate(max_volumetric, pa, scale=1.0, accel=3000.0, phase=0):
    """Integrate one PA_E step and sample it. Returns the ADC trace and the analyser's metrics."""
    raw_p, plan, low_mms, high_mms = integrate(max_volumetric, pa, scale, accel)

    # --- sample at the ADC rate, smooth, quantise: what the firmware actually sees ---
    step = int(round(1.0 / SAMPLE_HZ / DT))
    samp = [raw_p[i] for i in range(phase, len(raw_p), step)]
    smoothed = []
    for i in range(len(samp)):
        w = samp[max(0, i - ADC_SMOOTH + 1): i + 1]
        smoothed.append(sum(w) / len(w))
    adc = [int(round(BASELINE_ADC - p)) for p in smoothed]

    # --- metrics the firmware analyser cares about ---
    # plateau levels either side of the spike, and the run length below a threshold
    n_settle = int(0.40 * SAMPLE_HZ)
    t_travel = plan[1][0]
    t_slow   = plan[2][0]
    t_fast   = plan[3][0]
    i_slow1 = n_settle + int(t_travel * SAMPLE_HZ)
    i_fast  = i_slow1 + int(t_slow * SAMPLE_HZ)
    i_slow2 = i_fast + int(t_fast * SAMPLE_HZ)
    i_end   = i_slow2 + int(t_slow * SAMPLE_HZ)

    def level(a, b):
        w = smoothed[max(0, a):max(a + 1, b)]
        return sum(w) / len(w) if w else 0.0

    # sample the last third of each slow segment, where it has settled
    h_left  = level(i_slow1 + int(0.66 * (i_fast - i_slow1)), i_fast)
    h_right = level(i_slow2 + int(0.66 * (i_end - i_slow2)), i_end)
    spike   = max(smoothed[i_fast:i_slow2]) if i_slow2 > i_fast else 0.0

    runs = {}
    for thr in (2, 5, 10):
        best = cur = 0
        for p in smoothed:
            if p >= thr:
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        runs[thr] = best

    return {
        'mv': max_volumetric, 'pa': pa, 'scale': scale,
        'adc': adc,
        'rate': SAMPLE_HZ,
        'event_s': t_slow * 2 + t_fast,
        'plateau': round(h_left, 2),
        'spike': round(spike, 2),
        # the analyser's key discriminator, in the firmware's x10 units and ADC sign
        # (ADC falls as pressure rises, so a LOWER right plateau = MORE residual pressure)
        'hr_minus_hl': round((h_left - h_right) * 10, 1),
        'run_below': runs,
        'low_mms': round(low_mms, 2), 'high_mms': round(high_mms, 2),
    }


def calibrate(target_plateau=8.2, target_spike=35.0, mv=25.0, verbose=True):
    """Fit (n, K) so the SIMULATED trace matches the measured plateau and spike.

    The naive fit — solving P = K*Q^n straight from the two measured numbers — is wrong,
    and the error is not small. The slow-segment plateau is genuinely settled (0.94 s against
    tau ~157 ms), but the fast-segment spike is NOT: 0.18 s is barely 2.7 tau on top of 67 ms
    of acceleration, so it never reaches equilibrium. Treating that transient peak as a
    steady-state value understates high-flow pressure and drags n down.

    Fitting against the simulation instead lets the transient be a transient.

    Physical constraint: n is bounded to <= 1.0. A polymer melt is shear-THINNING, so pressure
    must rise slower than linearly with flow. Left unbounded this fit runs to n = 1.22, which
    would mean shear-thickening — a sign the fit is ill-conditioned, not a discovery. n and C
    trade off against each other: a slower C makes the spike undershoot, which the optimiser
    then compensates for by raising n. If the search lands on the 1.0 boundary, read that as
    "the model's C is too slow", not as a measurement.
    """
    global N_SHEAR, K_PRESS
    best = None
    for n_i in range(30, 101):                     # n from 0.30 to 1.00 (shear-thinning only)
        n = n_i / 100.0
        # K that puts the settled plateau on target for this n
        q_slow = A_FIL * E_PER_MM * (51.0 * mv / 60.0)
        k = target_plateau / (q_slow ** n)
        N_SHEAR, K_PRESS = n, k
        r = simulate(mv, 0.0, scale=1.0)
        err = abs(r['plateau'] - target_plateau) + abs(r['spike'] - target_spike)
        if best is None or err < best[0]:
            best = (err, n, k, r['plateau'], r['spike'])
    _, n, k, pl, sp = best
    N_SHEAR, K_PRESS = n, k
    if verbose:
        print('calibration: n=%.2f  K=%.3f  -> simulated plateau %.1f (target %.1f), '
              'spike %.1f (target %.1f)' % (n, k, pl, target_plateau, sp, target_spike))
        print('             steady-state pressure at the fast segment would be %.1f counts;'
              % (k * (A_FIL * E_PER_MM * (537.0 * mv / 60.0)) ** n))
        print('             the spike only reaches %.0f%% of it in the 0.18 s available.\n'
              % (100 * sp / (k * (A_FIL * E_PER_MM * (537.0 * mv / 60.0)) ** n)))
    return n, k


def main():
    # calibrate()   # superseded by fit_model.py — see the constants at the top
    flows = [25.0, 14.4, 7.2]
    pas = [0.0, 0.05, 0.10]
    out = {'vendor': [], 'scaled': []}
    for mv in flows:
        for pa in pas:
            out['vendor'].append(simulate(mv, pa, scale=1.0))
            out['scaled'].append(simulate(mv, pa, scale=mv / 25.0))

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, 'melt_model_out.json')
    with open(path, 'w') as f:
        json.dump(out, f, separators=(',', ':'))

    print('%-6s %-6s %-7s %8s %8s %10s %s' %
          ('flow', 'PA', 'event', 'plateau', 'spike', 'Hr-Hl', 'longest run >= thr (samples)'))
    for key in ('vendor', 'scaled'):
        print('--- %s geometry ---' % key)
        for r in out[key]:
            print('%-6s %-6.2f %6.2fs %8.1f %8.1f %10.1f  thr2=%-4d thr5=%-4d thr10=%d' %
                  (r['mv'], r['pa'], r['event_s'], r['plateau'], r['spike'],
                   r['hr_minus_hl'], r['run_below'][2], r['run_below'][5], r['run_below'][10]))
    print('\nwrote %s' % path)


if __name__ == '__main__':
    main()
