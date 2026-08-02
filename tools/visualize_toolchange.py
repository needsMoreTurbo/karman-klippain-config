# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2"]
# ///
"""
Simulate Karman's toolchange choreography offline and render the toolhead path
over a bed map with the keep-out zones, so a swap can be inspected BEFORE the
printer moves.

How it works
------------
* Reuses render_macro.py's Klipper-faithful Jinja2 environment to render the
  real macro bodies from this repo (cut, blobifier, park move, wipe, shake).
* Harvests every `variable_*` from the cfg files so the simulation always uses
  the CURRENT tuned values (pin_loc, tray_top, brush_start, min_toolchange_z...).
* Expands nested macro calls (e.g. BLOBIFIER -> BLOBIFIER_SERVO,
  _CUT_TIP_DO_CUT_MOTION), tracks G90/G91 + SAVE/RESTORE_GCODE_STATE, and
  threads the toolhead position through every step.
* Happy Hare's Python-side moves (toolchange z-hop / restore) are approximated
  from park_toolchange + min_toolchange_z and clearly labeled "inferred".
* Emits a self-contained HTML file: top-down SVG per scenario, phase-colored
  path, event markers, violation list, and a segment table.

Zone rules checked automatically
--------------------------------
1. Front-left idler keep-out  : x<10, y<17, ANY Z (cutter arm vs idler).
2. Depressor pin volume       : x in [-1,16], y in [336,346], z<15.
3. y_max feature-row entry    : crossing INTO y>=350 must happen in a clear
                                lane (15<x<40 or x>95).

Usage:
    uv run tools/visualize_toolchange.py                  # all scenarios
    uv run tools/visualize_toolchange.py --scenario midprint_swap
    uv run tools/visualize_toolchange.py --out my_viz.html
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_macro import extract_macro_body  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# Files that own the macros we simulate
MACRO_FILES = [
    REPO / "mmu/base/mmu_cut_tip.cfg",
    REPO / "mmu/addons/blobifier.cfg",
    REPO / "overrides.cfg",
]
# Files that own gcode_macro variable_* blocks we must harvest
VAR_FILES = [
    REPO / "mmu/base/mmu_macro_vars.cfg",
    REPO / "mmu/addons/blobifier.cfg",
]

AXIS_MAX = {"x": 351.0, "y": 359.0}
BED = 350.0

# ---------------------------------------------------------------------------#
# Config harvesting
# ---------------------------------------------------------------------------#
_SEC_RE = re.compile(r"^\[gcode_macro\s+([^\]]+)\]")
_VAR_RE = re.compile(r"^\s*variable_(\w+)\s*:\s*(.*)$")


def _strip_comment(v: str) -> str:
    in_q = None
    for i, ch in enumerate(v):
        if in_q:
            if ch == in_q:
                in_q = None
        elif ch in "'\"":
            in_q = ch
        elif ch in ";#":
            return v[:i]
    return v


def _convert(raw: str):
    v = _strip_comment(raw).strip()
    if v in ("True", "true"):
        return True
    if v in ("False", "false"):
        return False
    if v in ("None", ""):
        return None
    if v == "{}":
        return {}
    if (v[0] == v[-1] == "'") or (v[0] == v[-1] == '"'):
        return v[1:-1]
    if "," in v:
        parts = [p.strip() for p in v.split(",")]
        try:
            return tuple(float(p) for p in parts)
        except ValueError:
            return tuple(parts)
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def harvest_variables() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in VAR_FILES:
        section = None
        for line in f.read_text().splitlines():
            m = _SEC_RE.match(line.strip())
            if m:
                section = m.group(1).strip()
                out.setdefault(section, {})
                continue
            if line.strip().startswith("["):
                section = None
                continue
            if section:
                vm = _VAR_RE.match(line)
                if vm:
                    out[section][vm.group(1)] = _convert(vm.group(2))
    return out


def load_macros() -> dict[str, str]:
    """name -> raw jinja body, for every [gcode_macro] in MACRO_FILES."""
    bodies: dict[str, str] = {}
    for f in MACRO_FILES:
        text = f.read_text()
        for m in re.finditer(r"^\[gcode_macro\s+([^\]]+)\]", text, re.M):
            name = m.group(1).strip()
            try:
                bodies[name] = extract_macro_body(text, name)
            except SystemExit:
                pass  # macro without a gcode: block
    return bodies


# ---------------------------------------------------------------------------#
# Simulator
# ---------------------------------------------------------------------------#
@dataclass
class Seg:
    idx: int
    phase: str
    macro: str
    a: tuple[float, float, float]
    b: tuple[float, float, float]
    feed: float | None
    e: float = 0.0


@dataclass
class Marker:
    phase: str
    label: str
    pos: tuple[float, float, float]


@dataclass
class Sim:
    vars: dict[str, dict]
    bodies: dict[str, str]
    pos: list[float] = field(default_factory=lambda: [175.0, 175.0, 0.4])
    absolute: bool = True
    feed: float | None = None
    segs: list[Seg] = field(default_factory=list)
    marks: list[Marker] = field(default_factory=list)
    states: dict[str, tuple] = field(default_factory=dict)
    phase: str = "?"
    depth: int = 0
    unknown: dict[str, int] = field(default_factory=dict)

    # -- jinja ----------------------------------------------------------------
    def env(self) -> jinja2.Environment:
        # Klipper's delimiters, but Klipper's default (non-strict) Undefined
        return jinja2.Environment(
            "{%", "%}", "{", "}", extensions=["jinja2.ext.do"], undefined=jinja2.Undefined
        )

    def printer_obj(self) -> dict:
        x, y, z = self.pos
        p = {
            "toolhead": {
                "homed_axes": "xyz",
                "position": {"x": x, "y": y, "z": z},
                "axis_maximum": {"x": AXIS_MAX["x"], "y": AXIS_MAX["y"], "z": 310},
                "axis_minimum": {"x": 0, "y": 0, "z": -5},
                "max_accel": 21000,
                "minimum_cruise_ratio": 0.5,
            },
            "gcode_move": {"gcode_position": {"x": x, "y": y, "z": z, "e": 0},
                           "speed_factor": 1.0},
            "quad_gantry_level": {"applied": True},
            "extruder": {"temperature": 245.0, "target": 245.0, "pressure_advance": 0.035},
            "fan": {"speed": 0.0},
            "mmu": {
                "extruder_filament_remaining": 27.0,   # residual 25 + cut frag 2
                "last_tool": 0, "tool": 1,
                "slicer_tool_map": {"purge_volumes": [[0, 220], [45, 0]]},
                "sync_feedback_enabled": 1,
                "clog_runout_detected": False,
                "enabled": True,
            },
            "configfile": {"config": {"extruder": {"filament_diameter": "1.75"}}},
            "exclude_object": {"objects": []},
            "save_variables": {"variables": {}},
            "print_stats": {"state": "printing"},
        }
        for name, vals in self.vars.items():
            p[f"gcode_macro {name}"] = vals
        p.setdefault("gcode_macro _MMU_PARK", {})["retracted_length"] = 2.0
        return p

    # -- gcode handling -------------------------------------------------------
    # The sign group must accept a leading '+': Klippain's and Blobifier's wipe
    # loops emit `G1 X+35`, and a '-'-only pattern drops those moves silently —
    # which made a one-sided wipe look clean.
    _WORD = re.compile(r"([XYZEF])\s*([-+]?\d+\.?\d*)", re.I)

    def _move(self, line: str, macro: str):
        words = {k.upper(): float(v) for k, v in self._WORD.findall(line)}
        if "F" in words:
            self.feed = words["F"]
        tgt = list(self.pos)
        e = words.get("E", 0.0) if not self.absolute else words.get("E", 0.0)
        for i, ax in enumerate("XYZ"):
            if ax in words:
                tgt[i] = (self.pos[i] + words[ax]) if not self.absolute else words[ax]
        if tgt != self.pos or e:
            self.segs.append(Seg(len(self.segs), self.phase, macro,
                                 tuple(self.pos), tuple(tgt), self.feed, e))
            self.pos = tgt

    def run_macro(self, name: str, params: dict | None = None):
        if self.depth > 8:
            raise RuntimeError(f"macro recursion too deep at {name}")
        body = self.bodies.get(name)
        if body is None:
            self.unknown[name] = self.unknown.get(name, 0) + 1
            return
        ctx = dict(self.vars.get(name, {}))
        ctx.update({
            "printer": self.printer_obj(),
            "params": {k.upper(): str(v) for k, v in (params or {}).items()},
            "rawparams": "",
            "action_respond_info": lambda msg: "",
            "action_raise_error": lambda msg: (_ for _ in ()).throw(RuntimeError(msg)),
            "action_emergency_stop": lambda msg: (_ for _ in ()).throw(RuntimeError(msg)),
        })
        out = self.env().from_string(body).render(**ctx)
        self.depth += 1
        try:
            for raw in out.splitlines():
                self.dispatch(raw.strip(), name)
        finally:
            self.depth -= 1

    def dispatch(self, line: str, macro: str):
        if not line or line.startswith(";"):
            return
        cmdline = line.split(";", 1)[0].strip()
        if not cmdline:
            return
        cmd = cmdline.split()[0]
        u = cmd.upper()
        if u in ("G0", "G1"):
            self._move(cmdline, macro)
        elif u == "G90":
            self.absolute = True
        elif u == "G91":
            self.absolute = False
        elif u == "G92":
            pass
        elif u == "M83" or u == "M82":
            pass
        elif u == "SAVE_GCODE_STATE":
            n = _param(cmdline, "NAME") or "default"
            self.states[n] = (tuple(self.pos), self.absolute)
        elif u == "RESTORE_GCODE_STATE":
            n = _param(cmdline, "NAME") or "default"
            saved = self.states.get(n)
            if saved:
                spos, sabs = saved
                if (_param(cmdline, "MOVE") or "0") == "1" and tuple(self.pos) != spos:
                    self.segs.append(Seg(len(self.segs), self.phase, macro + " (restore)",
                                         tuple(self.pos), spos, self.feed))
                    self.pos = list(spos)
                self.absolute = sabs
        elif u == "SET_SERVO":
            ang = _param(cmdline, "ANGLE")
            if ang is not None:
                lbl = "tray OUT" if float(ang) < 90 else "tray IN"
                self.marks.append(Marker(self.phase, lbl, tuple(self.pos)))
        elif u == "SET_GCODE_VARIABLE":
            mac, var, val = _param(cmdline, "MACRO"), _param(cmdline, "VARIABLE"), _param(cmdline, "VALUE")
            if mac and var:
                import ast
                for conv in (ast.literal_eval, float):
                    try:
                        val = conv(val)
                        break
                    except (TypeError, ValueError, SyntaxError):
                        continue
                self.vars.setdefault(mac, {})[var] = val
        elif cmd in self.bodies:
            self.run_macro(cmd, _params(cmdline))
        else:
            self.unknown[cmd] = self.unknown.get(cmd, 0) + 1

    # -- inferred HH moves ----------------------------------------------------
    def inferred(self, label: str, x=None, y=None, z=None):
        tgt = [self.pos[0] if x is None else x,
               self.pos[1] if y is None else y,
               self.pos[2] if z is None else z]
        if tgt != self.pos:
            self.segs.append(Seg(len(self.segs), self.phase, f"HH inferred: {label}",
                                 tuple(self.pos), tuple(tgt), None))
            self.pos = tgt

    def mark(self, label: str):
        self.marks.append(Marker(self.phase, label, tuple(self.pos)))


def _param(line: str, key: str):
    m = re.search(rf"{key}=(\"[^\"]*\"|'[^']*'|\S+)", line, re.I)
    if not m:
        return None
    return m.group(1).strip("'\"")


def _params(line: str) -> dict:
    return {m.group(1): m.group(2).strip("'\"")
            for m in re.finditer(r"(\w+)=(\"[^\"]*\"|'[^']*'|\S+)", line)}


# ---------------------------------------------------------------------------#
# Scenarios
# ---------------------------------------------------------------------------#
def seq_vars(v):
    return v.get("_MMU_SEQUENCE_VARS", {})


def toolchange_plane(v, zhop_key_index=2) -> float:
    sv = seq_vars(v)
    park = sv.get("park_toolchange", (-999, -999, 1, 5, 2))
    zhop = park[zhop_key_index] if isinstance(park, tuple) else 1
    return float(max(0.4 + zhop, sv.get("min_toolchange_z", 1.0)))


def scen_midprint_swap(sim: Sim, shake: bool):
    v = sim.vars
    if shake:
        v.setdefault("_BLOBIFIER_COUNT", {}).update(current_blobs=5, next_shake=6, last_shake=0)
    else:
        v.setdefault("_BLOBIFIER_COUNT", {}).update(current_blobs=5, next_shake=100, last_shake=0)
    v.setdefault("_BLOBIFIER_SAFE_DESCEND", {}).update(
        tray=True, brush=True, shake=True, first_layer=False,
        print_height=0.4, print_previous_height=0.2, print_layer_height=0.3)
    v.setdefault("BLOBIFIER_PARK", {}).setdefault("restore_z", 0)

    sim.phase = "1 park (HH)"
    plane = toolchange_plane(v)
    sim.inferred(f"z-hop to toolchange plane (min_toolchange_z)", z=plane)
    sim.phase = "2 cut"
    sim.run_macro("_MMU_CUT_TIP")
    sim.phase = "3 park on tray"
    sim.run_macro("BLOBIFIER_PARK")
    sim.mark("UNLOAD T0 / LOAD T1 (no toolhead motion)")
    sim.phase = "4 purge (blobifier)"
    sim.run_macro("BLOBIFIER")
    sim.phase = "5 restore (HH)"
    sim.inferred("travel to next print position", x=150, y=150)
    sim.inferred("descend to print z", z=0.4)


def scen_pause_park(sim: Sim):
    v = sim.vars
    sv = seq_vars(v)
    park = sv.get("park_pause", (45, 359, 5, 0, 2))
    plane = float(max(0.4 + park[2], sv.get("min_toolchange_z", 1.0)))
    sim.phase = "1 lift (HH)"
    sim.inferred("z-hop for pause park", z=plane)
    sim.phase = "2 park to nozzle rest"
    sim.run_macro("_KARMAN_PARK_MOVE", {"X": park[0], "Y": park[1], "F": 12000})
    sim.mark("parked on nozzle rest (RTV cup)")
    sim.phase = "3 resume (leave rest)"
    sim.run_macro("_KARMAN_PARK_MOVE", {"X": 175, "Y": 175, "F": 12000, "RESTORE": 1})
    sim.inferred("descend to print z", z=0.4)


def scen_complete_park(sim: Sim):
    v = sim.vars
    sv = seq_vars(v)
    park = sv.get("park_complete", (45, 359, 10, 0, 5))
    plane = float(max(0.4 + park[2], sv.get("min_toolchange_z", 1.0)))
    sim.phase = "1 lift (HH)"
    sim.inferred("z-hop for print-complete park", z=plane)
    sim.phase = "2 park to nozzle rest"
    sim.run_macro("_KARMAN_PARK_MOVE", {"X": park[0], "Y": park[1], "F": 12000})
    sim.mark("parked on nozzle rest (print complete)")


SCENARIOS = {
    "midprint_swap": ("Mid-print toolchange T0→T1 (cut → tray park → purge → resume)",
                      lambda s: scen_midprint_swap(s, shake=False)),
    "midprint_swap_shake": ("Mid-print toolchange with bucket shake",
                            lambda s: scen_midprint_swap(s, shake=True)),
    "pause_park": ("Pause → park on nozzle rest → resume", scen_pause_park),
    "complete_park": ("Print complete → park on nozzle rest", scen_complete_park),
}

# ---------------------------------------------------------------------------#
# Zone checks
# ---------------------------------------------------------------------------#
def check_zones(segs: list[Seg]) -> list[str]:
    """Sample each segment and apply the three zone rules."""
    problems: list[str] = []
    for s in segs:
        ax, ay, az = s.a
        bx, by, bz = s.b
        length = math.dist(s.a, s.b)
        n = max(2, int(length) + 1)
        hit_idler = hit_pin = False
        for i in range(n + 1):
            t = i / n
            x, y, z = ax + (bx - ax) * t, ay + (by - ay) * t, az + (bz - az) * t
            if x < 10 and y < 17 and not hit_idler:
                problems.append(f"seg {s.idx} [{s.phase} / {s.macro}]: enters FRONT-LEFT IDLER keep-out at ({x:.0f},{y:.0f},z{z:.1f})")
                hit_idler = True
            if -1 <= x <= 16 and 336 <= y <= 346 and z < 15 and not hit_pin:
                problems.append(f"seg {s.idx} [{s.phase} / {s.macro}]: enters DEPRESSOR PIN volume below z15 at ({x:.0f},{y:.0f},z{z:.1f})")
                hit_pin = True
        # lane rule: crossing INTO y>=350 from below
        if ay < 350 <= by:
            t = (350 - ay) / (by - ay)
            x_at = ax + (bx - ax) * t
            if not (15 < x_at < 40 or x_at > 95):
                problems.append(f"seg {s.idx} [{s.phase} / {s.macro}]: enters y_max feature row OUTSIDE clear lanes at x={x_at:.1f}")
    return problems


# ---------------------------------------------------------------------------#
# HTML output
# ---------------------------------------------------------------------------#
PHASE_COLORS = ["#1f77b4", "#d62728", "#9467bd", "#2ca02c", "#ff7f0e", "#8c564b", "#17becf"]


def svg_map(segs: list[Seg], marks: list[Marker]) -> str:
    S = 1.7  # px per mm
    W, H = int(AXIS_MAX["x"] * S) + 60, int(AXIS_MAX["y"] * S) + 60
    def X(x): return 30 + x * S
    def Y(y): return H - 30 - y * S

    p = [f'<svg viewBox="0 0 {W} {H}" style="max-width:680px;width:100%;background:#fafafa;border:1px solid #ccc">']
    # envelope + bed
    p.append(f'<rect x="{X(0)}" y="{Y(AXIS_MAX["y"])}" width="{AXIS_MAX["x"]*S}" height="{AXIS_MAX["y"]*S}" fill="none" stroke="#999" stroke-dasharray="4 3"/>')
    p.append(f'<rect x="{X(0)}" y="{Y(BED)}" width="{BED*S}" height="{BED*S}" fill="#fff" stroke="#666"/>')
    # zones
    p.append(f'<rect x="{X(0)}" y="{Y(17)}" width="{10*S}" height="{17*S}" fill="#d6272833" stroke="#d62728"/>')          # idler
    p.append(f'<rect x="{X(0)}" y="{Y(346)}" width="{16*S}" height="{10*S}" fill="#ff7f0e33" stroke="#ff7f0e"/>')         # pin
    p.append(f'<rect x="{X(0)}" y="{Y(AXIS_MAX["y"])}" width="{20*S}" height="{(AXIS_MAX["y"]-335)*S}" fill="#8c564b22" stroke="#8c564b" stroke-dasharray="3 3"/>')  # back-left z<15
    # lanes
    for lo, hi in ((15, 40), (95, AXIS_MAX["x"])):
        p.append(f'<rect x="{X(lo)}" y="{Y(AXIS_MAX["y"])}" width="{(hi-lo)*S}" height="{(AXIS_MAX["y"]-345)*S}" fill="#2ca02c1a"/>')
    # y_max features
    feats = [("tray", 2, 17, "#8c564b"), ("shaker", 3, 5, "#e377c2"), ("rest", 43, 47, "#7f7f7f"), ("brush", 53, 88, "#bcbd22")]
    for name, lo, hi, col in feats:
        p.append(f'<rect x="{X(lo)}" y="{Y(AXIS_MAX["y"])}" width="{(hi-lo)*S}" height="{6}" fill="{col}"/>'
                 f'<text x="{X(lo)}" y="{Y(AXIS_MAX["y"])-3}" font-size="9" fill="{col}">{name}</text>')
    # depressor cut line
    p.append(f'<line x1="{X(0)}" y1="{Y(341)}" x2="{X(15)}" y2="{Y(341)}" stroke="#ff7f0e" stroke-width="3"/>'
             f'<text x="{X(17)}" y="{Y(341)+3}" font-size="9" fill="#ff7f0e">cut line z15</text>')

    phases = []
    for s in segs:
        if s.phase not in phases:
            phases.append(s.phase)
    # collapse XY-stationary purge moves; draw others
    drawn = 0
    for s in segs:
        col = PHASE_COLORS[phases.index(s.phase) % len(PHASE_COLORS)]
        if (abs(s.a[0]-s.b[0]) < 0.01 and abs(s.a[1]-s.b[1]) < 0.01):
            continue  # pure z/e move: shown in table + markers
        dash = ' stroke-dasharray="6 3"' if min(s.a[2], s.b[2]) >= 14.99 else ""
        p.append(f'<line x1="{X(s.a[0])}" y1="{Y(s.a[1])}" x2="{X(s.b[0])}" y2="{Y(s.b[1])}" stroke="{col}" stroke-width="2"{dash} opacity="0.85"/>')
        # arrowhead
        mx, my = (s.a[0]+s.b[0])/2, (s.a[1]+s.b[1])/2
        ang = math.degrees(math.atan2(-(s.b[1]-s.a[1]), s.b[0]-s.a[0]))
        p.append(f'<polygon points="0,-3 6,0 0,3" fill="{col}" transform="translate({X(mx)},{Y(my)}) rotate({ang})"/>')
        drawn += 1
    # markers
    for mk in marks:
        p.append(f'<circle cx="{X(mk.pos[0])}" cy="{Y(mk.pos[1])}" r="4" fill="#000" opacity="0.6"/>'
                 f'<text x="{X(mk.pos[0])+6}" y="{Y(mk.pos[1])+3}" font-size="9">{mk.label}</text>')
    # start
    if segs:
        p.append(f'<circle cx="{X(segs[0].a[0])}" cy="{Y(segs[0].a[1])}" r="5" fill="none" stroke="#000" stroke-width="2"/>'
                 f'<text x="{X(segs[0].a[0])+7}" y="{Y(segs[0].a[1])}" font-size="10" font-weight="bold">start</text>')
    # legend
    ly = 14
    for i, ph in enumerate(phases):
        col = PHASE_COLORS[i % len(PHASE_COLORS)]
        p.append(f'<rect x="{W-190}" y="{ly-9}" width="14" height="4" fill="{col}"/>'
                 f'<text x="{W-172}" y="{ly-4}" font-size="10">{ph}</text>')
        ly += 14
    p.append(f'<text x="{W-190}" y="{ly-2}" font-size="9" fill="#555">dashed = at z≥15 · solid = lower</text>')
    p.append("</svg>")
    return "".join(p)


def html_report(results: dict) -> str:
    css = ("body{font-family:system-ui,sans-serif;margin:1.5em;max-width:760px}"
           "h2{margin-top:1.4em} .viol{color:#b00;font-weight:600}"
           ".ok{color:#080;font-weight:600} table{border-collapse:collapse;font-size:12px}"
           "td,th{border:1px solid #ccc;padding:2px 6px;text-align:right}"
           "td:nth-child(2),td:nth-child(3){text-align:left}"
           "@media (prefers-color-scheme: dark){body{background:#111;color:#ddd}"
           "svg{background:#eee!important} td,th{border-color:#555}}")
    h = [f"<title>Karman toolchange paths</title><style>{css}</style>",
         "<h1>Karman — toolchange path visualization</h1>",
         "<p>Simulated from the live macro/config files. Dashed segments travel at z≥15 "
         "(the toolchange plane); solid segments are lower. Zones: red = front-left idler "
         "keep-out, orange = depressor pin (z<15), brown dash = back-left low-z zone, "
         "green tint = clear y_max approach lanes.</p>"]
    for key, (title, segs, marks, problems, unknown) in results.items():
        h.append(f"<h2>{title}</h2>")
        if problems:
            h.append("<p class=viol>⚠ " + str(len(problems)) + " zone violation(s):</p><ul>")
            h += [f"<li class=viol>{p}</li>" for p in problems]
            h.append("</ul>")
        else:
            h.append("<p class=ok>✓ no zone violations detected</p>")
        h.append(svg_map(segs, marks))
        rows = "".join(
            f"<tr><td>{s.idx}</td><td>{s.phase}</td><td>{s.macro}</td>"
            f"<td>{s.a[0]:.1f},{s.a[1]:.1f},{s.a[2]:.1f}</td>"
            f"<td>{s.b[0]:.1f},{s.b[1]:.1f},{s.b[2]:.1f}</td>"
            f"<td>{'' if s.feed is None else int(s.feed)}</td><td>{s.e:+.1f}" f"</td></tr>"
            for s in segs)
        h.append(f"<details><summary>{len(segs)} segments</summary><table>"
                 "<tr><th>#</th><th>phase</th><th>macro</th><th>from</th><th>to</th>"
                 f"<th>F</th><th>E</th></tr>{rows}</table></details>")
        if unknown:
            skip = ", ".join(f"{k}×{n}" for k, n in sorted(unknown.items()))
            h.append(f"<p style='font-size:11px;color:#777'>non-motion commands ignored: {skip}</p>")
    return "\n".join(h)


# ---------------------------------------------------------------------------#
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", choices=[*SCENARIOS, "all"], default="all")
    ap.add_argument("--out", default=str(REPO / "tools" / "toolchange_viz.html"))
    args = ap.parse_args()

    bodies = load_macros()
    keys = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    results = {}
    status = 0
    for k in keys:
        title, fn = SCENARIOS[k]
        sim = Sim(vars=harvest_variables(), bodies=bodies)
        try:
            fn(sim)
        except Exception as e:  # noqa: BLE001
            print(f"[{k}] SIMULATION ERROR: {type(e).__name__}: {e}")
            status = 1
            continue
        problems = check_zones(sim.segs)
        results[k] = (title, sim.segs, sim.marks, problems, sim.unknown)
        flag = f"{len(problems)} VIOLATION(S)" if problems else "clean"
        print(f"[{k}] {len(sim.segs)} segments, {len(sim.marks)} markers — {flag}")
        for p in problems:
            print(f"    ⚠ {p}")

    out = Path(args.out)
    out.write_text(html_report(results))
    print(f"\nwrote {out}")
    return status


if __name__ == "__main__":
    sys.exit(main())
