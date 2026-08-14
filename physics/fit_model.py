#!/usr/bin/env python3
"""Fit melt_model to the captured sweeps — on the features that matter, not on raw RMS.

    python3 extract_traces.py     # first, if measured.json is absent
    python3 fit_model.py

WHY THIS IS THE SECOND VERSION
    The first version minimised RMS over whole traces and produced a set that scored better and
    predicted worse: peak response to PA fell to +5% where the hardware shows +85%. Two separate
    causes, both fixed here.

    1. THE OBJECTIVE WAS DOMINATED BY THE PART THAT CARRIES NO INFORMATION. ~88% of each trace is
       baseline or plateau — steady-state flow, which pressure advance does not affect. The spike
       is ~12% of the samples and is the entire signal. RMS therefore paid the optimiser to fit
       the plateau and abandon the spike.
    2. THE SEARCH COULD NOT REACH THE ANSWER. Coordinate descent stepped each parameter by at most
       +-50% of its current value, so C, starting at 0.073, was confined to [0.036, 0.110]. The
       value that reproduces the data is 0.013. No objective would have found it through that
       window. Parameters here are swept over their full physical range on a log grid instead.

THE OBJECTIVE
    Chi-square over five features, each measured by IDENTICAL code on model and hardware traces
    (features() below), each normalised by the scatter of that feature across the 50 measured
    steps, so the fit weights each by how well it is actually known:

        peak_intercept   spike height extrapolated to PA=0   - what flow alone produces
        peak_slope       d(peak)/d(PA)                        - THE quantity a sweep exists to find
        plateau          settled slow-segment depth           - steady-state, anchors K and n
        rise_ms          10-90% of the spike                  - anchors C
        fall_ms          90-10% after it                      - tests the nonlinearity's asymmetry

    peak_slope comes from a regression over every PA step in the sweep, which is why
    extract_traces.py recovers all 50 rather than the 12 the firmware reported.

STAGES
    1. FEATURES + UNCERTAINTIES from the measured sweeps.
    2. IDENTIFIABILITY on the features: which parameter moves which feature, and are any two
       parameters redundant. Run first, because it says whether the fit is even meaningful.
    3. GLOBAL COORDINATE SWEEPS over the full range of each parameter.
    4. HOLD-OUT against the 25 mm3/s sweep, never seen by the fit.
    5. WAVEFORM RMS reported alongside, so a trade against the old objective stays visible.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import melt_model as mm

FIT_DT = 200e-6          # integration step during fitting; convergence checked against 50 us
PA_GRID = 7              # PA values simulated per regression
PHASES  = 6              # ADC sampling phases averaged per PA value (see model_features)


# ---------------------------------------------------------------------------
# features — ONE definition, applied to measured and modelled traces alike
# ---------------------------------------------------------------------------
def features(dep, rate, onset, t_slow):
    """Describe one spike. `onset` is the sample index where the fast segment begins.

    Levels are taken relative to the settled slow-segment plateau that precedes the spike, so
    'rise' means rise above the plateau, not above zero — the same thing the eye reads off the
    trace, and well defined for both sources.
    """
    n = len(dep)
    a = max(0, onset - int(t_slow * rate))
    lo = sum(dep[a + int((onset - a) * 0.66):onset]) / max(1, onset - a - int((onset - a) * 0.66))

    tail = min(n, onset + int(t_slow * rate * 1.2))
    seg = dep[onset:tail]
    if not seg:
        return None
    peak = max(seg)
    ip = onset + seg.index(peak)
    amp = peak - lo
    if amp <= 0:
        return None


    # walk BACK from the peak to where it last passed each level, and FORWARD to where it decays
    r10 = next((i for i in range(ip, a - 1, -1) if dep[i] <= lo + 0.1 * amp), None)
    r90 = next((i for i in range(ip, a - 1, -1) if dep[i] <= lo + 0.9 * amp), None)
    f90 = next((i for i in range(ip, n) if dep[i] <= lo + 0.9 * amp), None)
    f10 = next((i for i in range(ip, n) if dep[i] <= lo + 0.1 * amp), None)

    return {
        'peak': peak,
        'plateau': lo,
        'rise_ms': (r90 - r10) / rate * 1000 if (r10 is not None and r90 is not None and r90 > r10) else None,
        'fall_ms': (f10 - f90) / rate * 1000 if (f10 is not None and f90 is not None and f10 > f90) else None,
    }


def regress(xy):
    """Least squares, returning intercept, slope and the 1-sigma uncertainty of each."""
    n = len(xy)
    sx = sum(x for x, _ in xy)
    sy = sum(y for _, y in xy)
    sxx = sum(x * x for x, _ in xy)
    sxy = sum(x * y for x, y in xy)
    den = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / den
    a = (sy - b * sx) / n
    if n <= 2:
        return a, b, 0.0, 0.0
    resid = sum((y - a - b * x) ** 2 for x, y in xy) / (n - 2)
    return a, b, math.sqrt(resid * sxx / den), math.sqrt(resid * n / den)


def mean_sd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, 0.0
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


# ---------------------------------------------------------------------------
# measured side
# ---------------------------------------------------------------------------
def slow_seconds(mv):
    return mm.SEG_SLOW_MM / (51.0 * mv / 60.0)


def measured_features(traces, mv):
    t_slow = slow_seconds(mv)
    pk, rows = [], []
    for t in traces:
        onset = int(-t['t0'] * t['rate'])
        f = features(t['dep'], t['rate'], onset, t_slow)
        if f is None:
            continue
        rows.append(f)
        pk.append((t['pa'], f['peak']))
    a, b, sa, sb = regress(pk)
    pl, spl = mean_sd([r['plateau'] for r in rows])
    ri, sri = mean_sd([r['rise_ms'] for r in rows])
    fa, sfa = mean_sd([r['fall_ms'] for r in rows])
    return {
        'n': len(rows), 'pa_max': max(p for p, _ in pk),
        'peak_intercept': (a, sa), 'peak_slope': (b, sb),
        'plateau': (pl, spl), 'rise_ms': (ri, sri), 'fall_ms': (fa, sfa),
    }


# ---------------------------------------------------------------------------
# model side — same features, same code
# ---------------------------------------------------------------------------
def model_features(mv, pa_max, P, smooth, accel=3000.0, grid=None, phases=PHASES):
    """Features of the modelled sweep, averaged over ADC sampling phase.

    The phase average is not cosmetic. The spike is a few sample periods wide, so where the ADC
    grid lands changes the recorded peak by 2-3 counts out of a ~12-count PA signal. The hardware
    re-randomises that phase every step and the measured scatter already contains it; the model
    must therefore predict the EXPECTATION over phase, not one arbitrary alignment. Sampling the
    same integration at several phases costs almost nothing — integration is the expensive part.
    """
    n, k, c, f0 = P
    mm.N_SHEAR, mm.K_PRESS, mm.C_COMPL, mm.F_STATIC, mm.ADC_SMOOTH = n, k, c, f0, smooth
    t_slow = slow_seconds(mv)
    grid = grid or PA_GRID
    pk, rows = [], []
    for i in range(grid):
        pa = pa_max * i / (grid - 1)
        raw, _, _, _ = mm.integrate(mv, pa, 1.0, accel)
        _, step = mm.sample(raw, 0)
        acc = []
        for ph in range(0, step, max(1, step // phases)):
            sm, _ = mm.sample(raw, ph)
            dep = [float(round(x)) for x in sm]
            rate = 1.0 / (step * mm.DT)
            onset = int((0.40 + mm.TRAVEL_MM / mm.TRAVEL_MMS + t_slow) * rate)
            f = features(dep, rate, onset, t_slow)
            if f:
                acc.append(f)
        if not acc:
            return None
        avg = {kk: mean_sd([a[kk] for a in acc])[0] for kk in acc[0]}
        rows.append(avg)
        pk.append((pa, avg['peak']))
    a, b, _, _ = regress(pk)
    return {
        'peak_intercept': a, 'peak_slope': b,
        'plateau': sum(r['plateau'] for r in rows) / len(rows),
        'rise_ms': mean_sd([r['rise_ms'] for r in rows])[0],
        'fall_ms': mean_sd([r['fall_ms'] for r in rows])[0],
    }


FEATS = ('peak_intercept', 'peak_slope', 'plateau', 'rise_ms', 'fall_ms')


def chi2(meas, mv, P, smooth, detail=False, accel=3000.0, grid=None):
    mf = model_features(mv, meas['pa_max'], P, smooth, accel, grid)
    if mf is None:
        return (1e9, []) if detail else 1e9
    tot, rows = 0.0, []
    for f in FEATS:
        d, sd = meas[f]
        m = mf[f]
        if d is None or m is None or not sd:
            continue
        z = (m - d) / sd
        tot += z * z
        rows.append((f, d, sd, m, z))
    return (tot, rows) if detail else tot


# ---------------------------------------------------------------------------
# waveform RMS — the OLD objective, kept only so the trade stays visible
# ---------------------------------------------------------------------------
def waveform_rms(traces, mv, P, smooth, limit=8, accel=3000.0):
    n, k, c, f0 = P
    mm.N_SHEAR, mm.K_PRESS, mm.C_COMPL, mm.F_STATIC, mm.ADC_SMOOTH = n, k, c, f0, smooth
    t_slow = slow_seconds(mv)
    tot, cnt = 0.0, 0
    step = max(1, len(traces) // limit)
    for t in traces[::step]:
        r = mm.simulate(mv, t['pa'], scale=1.0, accel=accel)
        dep = [mm.BASELINE_ADC - x for x in r['adc']]
        onset_m = int((0.40 + mm.TRAVEL_MM / mm.TRAVEL_MMS + t_slow) * r['rate'])
        onset_d = int(-t['t0'] * t['rate'])
        for j in range(len(t['dep'])):
            i = onset_m + (j - onset_d)
            if 0 <= i < len(dep):
                tot += (t['dep'][j] - dep[i]) ** 2
                cnt += 1
    return math.sqrt(tot / max(cnt, 1))


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------
def identifiability(meas, mv, P, smooth):
    n, k, c, f0 = P
    print('=' * 74)
    print('STAGE 2 — IDENTIFIABILITY, on the features')
    print('=' * 74)
    base = model_features(mv, meas['pa_max'], P, smooth)
    print('   %-16s %10s %10s %10s %10s'
          % ('feature', 'd/dn +10%', 'd/dK +10%', 'd/dC +10%', 'd/dF0 +10%'))
    vecs = {}
    for name, p in (('n', (n * 1.1, k, c, f0)), ('K', (n, k * 1.1, c, f0)),
                    ('C', (n, k, c * 1.1, f0)), ('F0', (n, k, c, f0 * 1.1))):
        f = model_features(mv, meas['pa_max'], p, smooth)
        vecs[name] = {ft: (f[ft] - base[ft]) / meas[ft][1]
                      for ft in FEATS if base[ft] is not None and f[ft] is not None and meas[ft][1]}
    for ft in FEATS:
        print('   %-16s %10s %10s %10s %10s' % (ft,
              *['%+.2f' % vecs[p][ft] if ft in vecs[p] else '—' for p in ('n', 'K', 'C', 'F0')]))
    print('   (units: sigma of the measured scatter, so >1 means the fit can see it)\n')

    def corr(x, y):
        ks = [f for f in FEATS if f in x and f in y]
        mx = sum(x[f] for f in ks) / len(ks)
        my = sum(y[f] for f in ks) / len(ks)
        nx = math.sqrt(sum((x[f] - mx) ** 2 for f in ks))
        ny = math.sqrt(sum((y[f] - my) ** 2 for f in ks))
        if not nx or not ny:
            return 0.0
        return sum((x[f] - mx) * (y[f] - my) for f in ks) / (nx * ny)
    for i, j in (('n', 'K'), ('n', 'C'), ('n', 'F0'), ('K', 'C'), ('K', 'F0'), ('C', 'F0')):
        r = corr(vecs[i], vecs[j])
        print('     %s vs %s : r = %+.3f%s' % (i, j, r,
              '   <-- REDUNDANT, cannot be separated' if abs(r) > 0.95 else ''))
    print()


def logspace(lo, hi, n):
    return [lo * (hi / lo) ** (i / (n - 1)) for i in range(n)]


def fit(meas, mv, P, smooth, rounds=3):
    n, k, c, f0 = P
    print('=' * 74)
    print('STAGE 3 — GLOBAL COORDINATE SWEEPS  (full range each time, not a local step)')
    print('=' * 74)
    best = chi2(meas, mv, (n, k, c, f0), smooth)
    print('   start    n=%.3f K=%.3f C=%.5f F0=%.2f   chi2=%.1f' % (n, k, c, f0, best))
    grids = {
        'n': [0.30 + 0.02 * i for i in range(36)],
        'K': logspace(0.5, 12.0, 34),
        'C': logspace(0.0008, 0.30, 40),
        'F0': [0.4 * i for i in range(21)],
    }
    for rnd in range(rounds):
        for which in ('C', 'F0', 'n', 'K'):
            for t in grids[which]:
                cand = {'n': (t, k, c, f0), 'K': (n, t, c, f0),
                        'C': (n, k, t, f0), 'F0': (n, k, c, t)}[which]
                e = chi2(meas, mv, cand, smooth)
                if e < best:
                    best, (n, k, c, f0) = e, cand
        print('   round %d  n=%.3f K=%.3f C=%.5f F0=%.2f   chi2=%.1f'
              % (rnd + 1, n, k, c, f0, best))
        grids = {'n': [n * (1 + 0.04 * (i - 8) / 8) for i in range(17)],
                 'K': [k * (1 + 0.20 * (i - 8) / 8) for i in range(17)],
                 'C': [c * (1 + 0.40 * (i - 8) / 8) for i in range(17)],
                 'F0': [max(0.0, f0 * (1 + 0.30 * (i - 8) / 8)) for i in range(17)]}
    print()
    return (n, k, c, f0), best


def report(meas, mv, P, smooth, tag, accel=3000.0, grid=None):
    _, rows = chi2(meas, mv, P, smooth, detail=True, accel=accel, grid=grid)
    print('   %-16s %12s %10s %10s %8s' % ('feature', 'measured', '+-sigma', 'model', 'z'))
    for f, d, sd, m, z in rows:
        flag = '   <-- off' if abs(z) > 3 else ''
        print('   %-16s %12.1f %10.1f %10.1f %8.1f%s' % (f, d, sd, m, z, flag))
    print('   chi2 = %.1f over %d features  [%s]\n' % (sum(r[4] ** 2 for r in rows), len(rows), tag))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, 'measured.json')
    if not os.path.exists(path):
        sys.exit('measured.json missing — run extract_traces.py first')
    M = json.load(open(path))
    t144 = [t for t in M['m144'] if not t['prime']]
    t25 = [t for t in M['m25'] if not t['prime']]

    mm.DT = FIT_DT
    smooth = 1          # see the note in melt_model.py: the ADS1220 already integrates each
                        # conversion, so an extra multi-sample boxcar double-counts. The measured
                        # 23 ms 10-90 rise is under two sample periods, which a 3-sample average
                        # cannot produce at all.

    d144 = measured_features(t144, 14.4)
    d25 = measured_features(t25, 25.0)
    print('=' * 74)
    print('STAGE 1 — MEASURED FEATURES  (%d steps at 14.4, %d at 25.0)' % (d144['n'], d25['n']))
    print('=' * 74)
    for tag, d in (('14.4', d144), ('25.0', d25)):
        print('   %s mm3/s, PA 0 to %.3f' % (tag, d['pa_max']))
        for f in FEATS:
            v, s = d[f]
            print('      %-16s %9.2f  +- %.2f' % (f, v, s) if v is not None else '      %-16s —' % f)
    print()

    P0 = (mm.N_SHEAR, mm.K_PRESS, mm.C_COMPL, mm.F_STATIC)
    identifiability(d144, 14.4, P0, smooth)

    print('BEFORE (constants as they stand):')
    report(d144, 14.4, P0, smooth, 'pre-fit, 14.4')

    P, best = fit(d144, 14.4, P0, smooth)

    print('=' * 74)
    print('STAGE 4 — RESULT AND HOLD-OUT')
    print('=' * 74)
    print('AFTER  n=%.3f K=%.3f C=%.5f F0=%.2f:' % P)
    report(d144, 14.4, P, smooth, 'fitted, 14.4')
    print('   5 features, 4 free parameters -> 1 degree of freedom. A low chi2 HERE is close to')
    print('   arithmetic; the hold-out below, with nothing free, is the test that means anything.\n')
    identifiability(d144, 14.4, P, smooth)

    # The 25 mm3/s sweep is a hold-out with a catch: it ran at a different commanded
    # acceleration AND a different nozzle temperature, and the runbook records a vendor bug that
    # discarded ACC_WALL and used 4000 regardless. Acceleration is not a free knob to be tuned —
    # but the sweep's own rise time is an independent observable of it, so try the three
    # candidates and report which the data is consistent with, rather than assuming one.
    print('HELD OUT — 25 mm3/s, never seen by the fit.')
    print('   Its acceleration is uncertain (commanded 5000; the ACC_WALL bug would force 4000).')
    print('   Ramp time Dv/a is 202.5/a, and the measured 10-90%% rise is %.1f +- %.1f ms:\n'
          % d25['rise_ms'])
    for accel in (3000.0, 4000.0, 5000.0):
        e, rows = chi2(d25, 25.0, P, smooth, detail=True, accel=accel)
        rise = [r for r in rows if r[0] == 'rise_ms']
        print('   accel %4.0f  ramp %4.1f ms  chi2 %7.1f   %s'
              % (accel, 202.5 / accel * 1000, e,
                 'rise z=%+.1f' % rise[0][4] if rise else ''))
    print()
    # The 25 sweep spans only PA 0 to 0.046, over which the peak moves ~4 counts — comparable to
    # the ADC's own 1-count quantisation. Its slope must therefore be estimated from a dense PA
    # grid, as the measurement itself does with 24 steps; 7 points leaves ~10% sampling noise.
    print('   slope estimate vs number of PA points simulated (measurement uses 24 steps):')
    for g in (7, 13, 21, 31):
        mf = model_features(25.0, d25['pa_max'], P, smooth, 3000.0, g)
        print('      %2d points -> slope %5.1f  (measured %.1f +- %.1f)'
              % (g, mf['peak_slope'], *d25['peak_slope']))
    print()
    report(d25, 25.0, P, smooth, 'held out, 25.0 @ 3000, 21 PA points', accel=3000.0, grid=21)

    print('=' * 74)
    print('STAGE 5 — WAVEFORM RMS (the OLD objective) — is the trade real?')
    print('=' * 74)
    for tag, p in (('pre-fit ', P0), ('fitted  ', P)):
        print('   %s n=%.3f K=%.3f C=%.5f F0=%.2f   rms 14.4 = %.2f counts   rms 25 = %.2f'
              % (tag, p[0], p[1], p[2], p[3],
                 waveform_rms(t144, 14.4, p, smooth),
                 waveform_rms(t25, 25.0, p, smooth, accel=4000.0)))

    print('\n   convergence check — same fit at the production 50 us step:')
    mm.DT = 50e-6
    print('      chi2 at %.0f us = %.1f' % (FIT_DT * 1e6, best))
    print('      chi2 at  50 us = %.1f' % chi2(d144, 14.4, P, smooth))
    mm.DT = FIT_DT

    json.dump({'n': P[0], 'K': P[1], 'C': P[2], 'F0': P[3],
               'adc_smooth': smooth, 'chi2': best},
              open(os.path.join(here, 'fit_result.json'), 'w'), indent=1)
    print('\nfinal: n=%.3f K=%.3f C=%.5f F0=%.2f smooth=%d  (fit_result.json)'
          % (P + (smooth,)))


if __name__ == '__main__':
    main()
