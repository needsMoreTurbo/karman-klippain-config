#!/usr/bin/env python3
"""Turn the raw BDPressure sweep captures into a fitting dataset.

    python3 extract_traces.py        # captures/*.json  ->  measured.json

WHY THIS EXISTS AS A SCRIPT
    The first version of measured.json was hand-built in a scratch directory and then lost,
    which cost an afternoon. The captures live in captures/ and this rebuilds the dataset from
    them, so the fit is reproducible from data the repo actually holds.

WHY IT DOES NOT USE THE FIRMWARE'S OWN OUTPUT
    The sensor firmware only transmits a result for a step it considers analysable — 12 of 51
    steps in the 14.4 mm3/s sweep. But the *raw ADC stream* contains all 51, because the stream
    is emitted continuously and independently of the analyser. Detecting the spikes ourselves
    recovers every step, which is what makes a PA-response fit possible at all: 50 points along
    the PA axis instead of 12.

LABELLING
    Steps are found by threshold crossing and numbered in order. PA is then assigned as

        pa = (index - 1) * PA_STEP

    which is checked against every read the firmware did report — those carry their own PA value,
    so they are an independent anchor. The script asserts the agreement rather than trusting it.
    Index 0 is the extra event before the sweep proper (it sits after a much longer gap than any
    other step); it is kept but flagged `prime`, and excluded from fitting by default because its
    thermal history differs from the rest.

GEOMETRY
    A capture records `geom_scale`, because PA_CALIBRATE can scale the pattern with flow. Windows
    are derived from it. NOTE: fit_model.slow_seconds() still assumes scale 1, so the scaled
    capture (m144s) is extracted and stored but must not be fed to the fit until that is fixed.

BASELINE
    Per-trace, not global. Each trace's zero is taken from the quiet samples before its own
    extrusion begins, which removes the slow thermal drift of the gauge across a 250 s sweep.
"""

import json
import math
import os

THR_ON = 15.0        # counts below baseline that mark the start of a fast-segment spike
THR_OFF = 5.0        # hysteresis: the event ends when depth falls back under this
MIN_GAP = 100        # samples to skip after an event before looking for the next
# Window, in seconds either side of onset. Sized from the SLOW SEGMENT of the capture rather than
# fixed, because segment duration scales as 1/flow: 1.63 s at 14.4 mm3/s but 4.71 s at 5. A fixed
# 2 s pre-window would sit entirely inside the slow segment at low flow, so the per-trace zero
# would be taken from extruding samples instead of the travel move, and every level would read
# ~4 counts low.
WIN_PAD = 0.55       # extra seconds before the segment starts, to catch the travel move
WIN_POST_PAD = 1.0   # extra seconds after the spike, past the second slow segment


def find_events(adc, baseline, rate):
    """Locate every fast-segment spike in the stream. Returns onset sample indices."""
    dep = [baseline - a for a in adc]
    out, i, n = [], 0, len(dep)
    while i < n:
        if dep[i] > THR_ON:
            j = i
            while j < n and dep[j] > THR_OFF:
                j += 1
            out.append(i)
            i = j + MIN_GAP
        else:
            i += 1
    return out, dep


def check_labels(onsets, reads, pa_step, rate):
    """Verify pa = (index-1)*pa_step against the PA values the firmware itself reported.

    A firmware read is stamped at the sample where its analysis window *ended*, which is a little
    after the onset it describes, so each read is matched to the nearest preceding onset.
    """
    bad = []
    for r in reads:
        prior = [k for k, s in enumerate(onsets) if s <= r['sample']]
        if not prior:
            continue
        idx = prior[-1]
        want = max(0.0, (idx - 1) * pa_step)
        if abs(want - r['pa']) > pa_step / 2:
            bad.append((idx, r['pa'], want))
    return bad


def extract(path):
    cap = json.load(open(path))
    rate = cap['rate_hz']
    onsets, dep = find_events(cap['adc'], cap['baseline'], rate)

    gaps = [onsets[i + 1] - onsets[i] for i in range(len(onsets) - 1)]
    med = sorted(gaps)[len(gaps) // 2] if gaps else 0

    bad = check_labels(onsets, cap['firmware_reads'], cap['pa_step'], rate)
    scale = cap.get('geom_scale', cap['max_volumetric'] / 25.0)
    t_slow = 20.0 * scale / (51.0 * cap['max_volumetric'] / 60.0)
    t_fast = 40.0 * scale / (537.0 * cap['max_volumetric'] / 60.0)
    pre = int((t_slow + WIN_PAD) * rate)
    post = int((t_fast + t_slow + WIN_POST_PAD) * rate)

    traces = []
    for idx, s in enumerate(onsets):
        a, b = s - pre, s + post
        if a < 0 or b > len(dep):
            continue
        # local zero: the quietest tenth of the pre-onset window, which is between-step travel
        head = sorted(dep[a:a + int(WIN_PAD * rate * 0.85)])   # the travel move, not extruding
        zero = sum(head[:max(1, len(head) // 10)]) / max(1, len(head) // 10)
        traces.append({
            'pa': round(max(0.0, (idx - 1) * cap['pa_step']), 4),
            'index': idx,
            'prime': idx == 0,
            'rate': rate,
            't0': round(-pre / rate, 4),
            'zero': round(zero, 2),
            'dep': [round(x - zero, 1) for x in dep[a:b]],
        })
    return cap, onsets, med, bad, traces


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = {}
    for fn, key in (('sweep_14p4.json', 'm144'), ('sweep_25.json', 'm25'),
                    ('sweep_5.json', 'm5'),
                    ('sweep_14p4_scaled.json', 'm144s')):
        path = os.path.join(here, 'captures', fn)
        cap, onsets, med, bad, traces = extract(path)
        print('%s  %.1f mm3/s' % (fn, cap['max_volumetric']))
        print('   %d samples, %d events found, median spacing %d samples (%.2f s)'
              % (len(cap['adc']), len(onsets), med, med / cap['rate_hz']))
        print('   first gap %d samples vs median %d  -> index 0 flagged as prime'
              % (onsets[1] - onsets[0] if len(onsets) > 1 else 0, med))
        print('   PA labels checked against %d firmware reads: %s'
              % (len(cap['firmware_reads']),
                 'ALL AGREE' if not bad else 'MISMATCH %s' % bad))
        print('   %d traces extracted, %d samples each, PA %.3f to %.3f'
              % (len(traces), len(traces[0]['dep']),
                 min(t['pa'] for t in traces), max(t['pa'] for t in traces)))
        peaks = [(t['pa'], max(t['dep'])) for t in traces if not t['prime']]
        lo = [p for _, p in peaks[:5]]
        hi = [p for _, p in peaks[-5:]]
        print('   peak depth: first five steps %s, last five %s counts\n' % (lo, hi))
        out[key] = traces
        assert not bad, 'PA labelling disagrees with the firmware — do not fit this'

    dest = os.path.join(here, 'measured.json')
    json.dump(out, open(dest, 'w'), separators=(',', ':'))
    print('wrote %s  (%s)' % (dest, ', '.join('%s=%d' % (k, len(v)) for k, v in out.items())))


if __name__ == '__main__':
    main()
