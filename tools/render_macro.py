# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2"]
# ///
"""
Render a Klipper [gcode_macro] / [delayed_gcode] body offline for validation.

Klipper renders macro gcode with a *customised* Jinja2 environment:
    jinja2.Environment('{%', '%}', '{', '}', extensions=['jinja2.ext.do'])
i.e. statements use {% %} but expressions use SINGLE braces { } (not {{ }}),
plus the `do` extension. This script mirrors that so templates parse and behave
exactly as they do on the printer.

Usage:
    # Render one macro with a printer-state context from JSON:
    uv run tools/render_macro.py bed_fans.cfg _BED_FAN_TICK --json state.json

    # Run the built-in bed-fan state-machine self-test (no args needed):
    uv run tools/render_macro.py --selftest

The JSON context, if given, is passed as the `printer` object. A plain nested
dict works because Jinja falls back from attribute access to item access, so
`printer.heater_bed.temperature` and `printer["temperature_sensor Chamber"]`
both resolve.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import jinja2

REPO_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Core: extract a macro body and render it the way Klipper does
# --------------------------------------------------------------------------- #
def klipper_env() -> jinja2.Environment:
    """A Jinja2 environment matching Klipper's gcode_macro delimiters."""
    return jinja2.Environment(
        "{%", "%}", "{", "}", extensions=["jinja2.ext.do"], undefined=jinja2.StrictUndefined
    )


def extract_macro_body(cfg_text: str, name: str) -> str:
    """Return the raw gcode: body of [gcode_macro NAME] or [delayed_gcode NAME]."""
    headers = {f"[gcode_macro {name}]", f"[delayed_gcode {name}]"}
    lines = cfg_text.splitlines()
    in_section = False
    in_gcode = False
    body: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped in headers:
            in_section = True
            continue
        if in_section:
            # a new section header at any indent ends this macro
            if stripped.startswith("[") and stripped.endswith("]"):
                break
            if not in_gcode:
                if stripped == "gcode:" or stripped.startswith("gcode:"):
                    in_gcode = True
                continue
            body.append(line)
    if not in_gcode:
        raise SystemExit(f"error: macro '{name}' not found (or has no gcode: block)")
    return "\n".join(body)


def render(cfg_path: Path, macro: str, printer: dict, params: dict | None = None) -> str:
    body = extract_macro_body(cfg_path.read_text(), macro)
    tmpl = klipper_env().from_string(body)
    return tmpl.render(printer=printer, params=params or {})


# --------------------------------------------------------------------------- #
# Self-test: exercise _BED_FAN_TICK across the state machine
# --------------------------------------------------------------------------- #
def build_printer(
    *,
    enable=True,
    ps="printing",
    bed_t=105.0,
    target=105.0,
    chamber=30.0,
    actual=0.10,
    commanded=0.10,
    settle_ticks=8,
    manual_latch=False,
    manual_speed=0.0,
    state="OFF",
    prev_state="printing",
    post_print=False,
) -> dict:
    """Build a mock `printer` object for _BED_FAN_TICK from scenario knobs."""
    return {
        "print_stats": {"state": ps},
        "heater_bed": {"temperature": bed_t, "target": target},
        "temperature_sensor Chamber": {"temperature": chamber},
        "fan_generic Bed_Fans": {"speed": actual},
        "gcode_macro _USER_VARIABLES": {"verbose": True},
        "gcode_macro _BED_FAN_VARS": {
            # config
            "enable": enable,
            "activation_temp": 90,
            "heating_speed": 0.10,
            "high_speed": 0.55,
            "target_tolerance": 2.0,
            "settle_time": 30,
            "ramp_step": 0.03,
            "ramp_drop_guard": 3.0,
            "reheat_band": 8.0,
            "chamber_max": 55,
            "chamber_resume": 50,
            "cool": True,
            "cool_speed": 0.40,
            "cool_temp": 40,
            "tick_interval": 4,
            # internal state
            "commanded": commanded,
            "settle_ticks": settle_ticks,
            "manual_latch": manual_latch,
            "manual_speed": manual_speed,
            "state": state,
            "prev_state": prev_state,
            "post_print": post_print,
        },
    }


# name, scenario kwargs, expected (state, speed|None, duration|None, fan_set[, post_print])
# The optional 5th element asserts the post_print window flag after the tick
# ("True"/"False"); omit it where the window is irrelevant.
SCENARIOS = [
    ("idle / bed cold",        dict(ps="standby", target=0.0,   bed_t=25.0, chamber=25.0, actual=0.0,  commanded=0.0,  settle_ticks=0), ("OFF",         0.0,  10, True)),
    ("PLA (target < 90)",      dict(ps="standby", target=60.0,  bed_t=60.0, chamber=25.0, actual=0.0,  commanded=0.0,  settle_ticks=0), ("OFF",         0.0,  10, True)),
    ("preheat: bed climbing",  dict(ps="standby", target=105.0, bed_t=60.0, chamber=30.0, actual=0.10, commanded=0.10, settle_ticks=0), ("HEATING",     0.10, 4,  True)),
    ("at target, settling",    dict(ps="printing",target=105.0, bed_t=104.0,chamber=30.0, actual=0.10, commanded=0.10, settle_ticks=3), ("SETTLE",      0.10, 4,  True)),
    ("settle completes->ramp", dict(ps="printing",target=105.0, bed_t=104.0,chamber=30.0, actual=0.10, commanded=0.10, settle_ticks=7), ("RAMP",        0.13, 4,  True)),
    ("ramp starts",            dict(ps="printing",target=105.0, bed_t=104.5,chamber=30.0, actual=0.10, commanded=0.10, settle_ticks=8), ("RAMP",        0.13, 4,  True)),
    ("ramp mid",               dict(ps="printing",target=105.0, bed_t=104.5,chamber=30.0, actual=0.40, commanded=0.40, settle_ticks=8), ("RAMP",        0.43, 4,  True)),
    ("hold at high",           dict(ps="printing",target=105.0, bed_t=105.0,chamber=45.0, actual=0.55, commanded=0.55, settle_ticks=8), ("HOLD",        0.55, 4,  True)),
    ("drop-guard (small dip)", dict(ps="printing",target=105.0, bed_t=100.0,chamber=30.0, actual=0.40, commanded=0.40, settle_ticks=8), ("DROP-GUARD",  0.37, 4,  True)),
    ("large drop -> re-heat",  dict(ps="printing",target=105.0, bed_t=95.0, chamber=30.0, actual=0.40, commanded=0.40, settle_ticks=8), ("HEATING",     0.10, 4,  True)),
    ("chamber cap",            dict(ps="printing",target=105.0, bed_t=105.0,chamber=56.0, actual=0.50, commanded=0.50, settle_ticks=8), ("CHAMBER-CAP", 0.47, 4,  True)),
    ("chamber hysteresis band",dict(ps="printing",target=105.0, bed_t=105.0,chamber=52.0, actual=0.50, commanded=0.50, settle_ticks=8), ("RAMP-HOLD",   0.50, 4,  True)),
    ("manual latch held",      dict(ps="printing",target=105.0, bed_t=105.0,chamber=30.0, actual=0.40, commanded=0.40, manual_latch=True, manual_speed=0.40), ("MANUAL", None, 4, False)),
    ("manual held in cooldown", dict(ps="complete",prev_state="complete", target=0.0, bed_t=90.0, chamber=45.0, actual=0.50, commanded=0.50, manual_latch=True, manual_speed=0.50), ("MANUAL", None, 4, False)),
    ("print-end clears latch",  dict(ps="complete",prev_state="printing", target=0.0, bed_t=90.0, chamber=45.0, actual=0.50, commanded=0.50, manual_latch=True, manual_speed=0.50), ("COOL",   0.40, 4, True)),
    ("new print drops latch",   dict(ps="printing",prev_state="complete", target=105.0,bed_t=60.0, chamber=30.0, actual=0.50, commanded=0.50, manual_latch=True, manual_speed=0.50), ("HEATING",0.10, 4, True)),
    ("resume keeps latch",      dict(ps="printing",prev_state="paused",   target=105.0,bed_t=105.0,chamber=30.0, actual=0.50, commanded=0.50, manual_latch=True, manual_speed=0.50), ("MANUAL", None, 4, False)),
    ("slider moved -> latch",  dict(ps="printing",target=105.0, bed_t=105.0,chamber=30.0, actual=0.30, commanded=0.10), ("MANUAL",      None, 4,  False)),
    ("post-print cooling",     dict(ps="complete",target=0.0,   bed_t=90.0, chamber=45.0, actual=0.10, commanded=0.10), ("COOL",        0.40, 4,  True)),
    ("post-print cold -> off", dict(ps="complete",target=0.0,   bed_t=40.0, chamber=35.0, actual=0.0,  commanded=0.0),  ("OFF",         0.0,  30, True)),
    ("disabled",               dict(enable=False, ps="printing",target=105.0,bed_t=105.0, chamber=30.0,actual=0.0,  commanded=0.0),  ("DISABLED",    0.0,  30, True)),
    # --- one-shot post-print window: stale-`complete` regressions (2026-07) ---
    # print_stats.state stays "complete" until the next print loads; the window
    # flag (post_print) replaces level-triggering on that stale state.
    ("stale complete: ABS preheat",   dict(ps="complete", prev_state="complete", target=105.0, bed_t=85.0,  chamber=28.0, actual=0.0,  commanded=0.0,  settle_ticks=0), ("HEATING", 0.10, 4,  True,  "False")),
    ("stale complete: ramp",          dict(ps="complete", prev_state="complete", target=105.0, bed_t=104.5, chamber=30.0, actual=0.40, commanded=0.40, settle_ticks=8), ("RAMP",    0.43, 4,  True,  "False")),
    ("cooldown: window continues",    dict(ps="complete", prev_state="complete", post_print=True,  target=0.0,   bed_t=80.0, chamber=45.0, actual=0.40, commanded=0.40), ("COOL",    0.40, 4,  True,  "True")),
    ("cooldown: window finishes",     dict(ps="complete", prev_state="complete", post_print=True,  target=0.0,   bed_t=50.0, chamber=35.0, actual=0.10, commanded=0.10), ("OFF",     0.0,  30, True,  "False")),
    ("ABS reheat during cooldown",    dict(ps="complete", prev_state="complete", post_print=True,  target=105.0, bed_t=90.0, chamber=45.0, actual=0.10, commanded=0.10), ("HEATING", 0.10, 4,  True,  "False")),
    ("PLA reheat during cooldown",    dict(ps="complete", prev_state="complete", post_print=True,  target=60.0,  bed_t=50.0, chamber=45.0, actual=0.10, commanded=0.10), ("OFF",     0.0,  10, True,  "False")),
    ("abandoned preheat: no COOL",    dict(ps="complete", prev_state="complete", post_print=False, target=0.0,   bed_t=60.0, chamber=45.0, actual=0.0,  commanded=0.0),  ("OFF",     0.0,  10, True,  "False")),
    ("manual in cooldown keeps window", dict(ps="complete", prev_state="complete", post_print=True, target=0.0,  bed_t=80.0, chamber=45.0, actual=0.50, commanded=0.50, manual_latch=True, manual_speed=0.50), ("MANUAL", None, 4, False, "True")),
]

_STATE_RE = re.compile(r"VARIABLE=state VALUE=\"'([^']*)'\"")
_FAN_RE = re.compile(r"SET_FAN_SPEED FAN=Bed_Fans SPEED=([-\d.]+)")
_DUR_RE = re.compile(r"UPDATE_DELAYED_GCODE ID=_BED_FAN_TICK DURATION=(\d+)")
_POST_RE = re.compile(r"VARIABLE=post_print VALUE=(True|False)")


def selftest(cfg_path: Path) -> int:
    print(f"Self-test: _BED_FAN_TICK in {cfg_path.relative_to(REPO_ROOT)}\n")
    failures = 0
    for name, kw, expect in SCENARIOS:
        exp_state, exp_speed, exp_dur, exp_fanset = expect[:4]
        exp_post = expect[4] if len(expect) > 4 else None
        try:
            out = render(cfg_path, "_BED_FAN_TICK", build_printer(**kw))
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL  {name}: render error: {type(e).__name__}: {e}")
            failures += 1
            continue

        got_state = (_STATE_RE.search(out) or [None, None])[1]
        fan_m = _FAN_RE.search(out)
        got_speed = float(fan_m.group(1)) if fan_m else None
        dur_m = _DUR_RE.search(out)
        got_dur = int(dur_m.group(1)) if dur_m else None

        probs = []
        if got_state != exp_state:
            probs.append(f"state={got_state!r} (want {exp_state!r})")
        if exp_fanset and fan_m is None:
            probs.append("no SET_FAN_SPEED emitted")
        if not exp_fanset and fan_m is not None:
            probs.append(f"unexpected SET_FAN_SPEED={got_speed} (manual must not touch fan)")
        if exp_speed is not None and got_speed is not None and abs(got_speed - exp_speed) > 1e-6:
            probs.append(f"speed={got_speed} (want {exp_speed})")
        if exp_dur is not None and got_dur != exp_dur:
            probs.append(f"duration={got_dur} (want {exp_dur})")
        if exp_post is not None:
            post_m = _POST_RE.search(out)
            got_post = post_m.group(1) if post_m else None
            if got_post != exp_post:
                probs.append(f"post_print={got_post} (want {exp_post})")

        if probs:
            failures += 1
            print(f"  FAIL  {name}: " + "; ".join(probs))
        else:
            sp = "-" if got_speed is None else f"{got_speed:>4}"
            print(f"  ok    {name:<26} state={got_state:<12} speed={sp} dur={got_dur}")

    total = len(SCENARIOS)
    print(f"\n{total - failures}/{total} scenarios passed.")
    return 1 if failures else 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cfg", nargs="?", help="path to a .cfg file (relative to repo root ok)")
    ap.add_argument("macro", nargs="?", help="macro name, e.g. _BED_FAN_TICK")
    ap.add_argument("--json", help="path to a JSON file providing the `printer` context")
    ap.add_argument("--selftest", action="store_true", help="run the built-in bed-fan state-machine test")
    args = ap.parse_args()

    if args.selftest:
        return selftest(REPO_ROOT / "bed_fans.cfg")

    if not args.cfg or not args.macro:
        ap.error("provide CFG and MACRO, or use --selftest")

    cfg_path = Path(args.cfg)
    if not cfg_path.is_absolute() and not cfg_path.exists():
        cfg_path = REPO_ROOT / args.cfg
    printer = json.loads(Path(args.json).read_text()) if args.json else {}
    print(render(cfg_path, args.macro, printer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
