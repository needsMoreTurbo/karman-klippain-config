#!/usr/bin/env python3
"""
hh_extract.py - Extract the Happy Hare parameters that govern a tip-cutting
toolchange, and compute the derived values that follow from them.

Reads your config files only. Makes no changes, moves no motors, talks to
nothing. Safe to run at any time, including mid-print.

By default it writes two files into the current directory and also prints the
report to the terminal:

    hh_extract_report.txt   human-readable report
    hh_extract.json         machine-readable values

Usage:
    python3 hh_extract.py                          # write both files here
    python3 hh_extract.py -o ~/                    # write them somewhere else
    python3 hh_extract.py -q                       # files only, no terminal output
    python3 hh_extract.py --no-files               # old behaviour, all to stdout
    python3 hh_extract.py --stdout                 # also dump JSON for copy/paste
    python3 hh_extract.py -d /path/to/config/mmu   # non-default config dir

Requires: python3 only. No pip installs.
"""

import argparse
import glob
import json
import math
import os
import re
import sys

VERSION = "1.1"

DEFAULT_REPORT = "hh_extract_report.txt"
DEFAULT_JSON = "hh_extract.json"
JSON_BEGIN = "----- BEGIN HAPPY_HARE_CONFIG_JSON -----"
JSON_END = "----- END HAPPY_HARE_CONFIG_JSON -----"

# ----------------------------------------------------------------------------
# Klipper-ish config parsing
# ----------------------------------------------------------------------------
#
# Rules that make this reliable without pulling in configparser:
#   * a section is "[name]" or "[type name]" at column 0
#   * a setting is "key: value" or "key = value" at column 0 (no leading space)
#   * continuation lines and gcode: bodies are always indented, so ignoring
#     indented lines skips every jinja block without needing to understand it
#   * '#' and ';' start a comment anywhere on the line

SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*(?:[#;].*)?$")
SETTING_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_\.\-]*)\s*[:=]\s*(.*)$")


def strip_comment(text):
    for ch in ("#", ";"):
        idx = text.find(ch)
        if idx >= 0:
            text = text[:idx]
    return text.strip()


def parse_cfg(path):
    """Return {section_name: {key: value}} for one .cfg file."""
    sections = {}
    current = None
    try:
        with open(path, "r", errors="replace") as fh:
            lines = fh.readlines()
    except IOError as exc:
        sys.stderr.write("  ! cannot read %s: %s\n" % (path, exc))
        return sections

    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith(("#", ";")):
            continue
        if line[:1].isspace():
            continue  # continuation / gcode body

        m = SECTION_RE.match(line)
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, {})
            continue

        m = SETTING_RE.match(line)
        if m and current is not None:
            key = m.group(1).strip().lower()
            sections[current][key] = strip_comment(m.group(2))

    return sections


class Config(object):
    """All parsed .cfg files, with provenance for every value."""

    def __init__(self):
        self.files = {}       # relpath -> {section: {key: value}}
        self.missing = []
        self.sources = {}     # "section/key" -> relpath (first file that had it)

    def load_dir(self, root):
        found = sorted(glob.glob(os.path.join(root, "**", "*.cfg"), recursive=True))
        for path in found:
            rel = os.path.relpath(path, root)
            self.files[rel] = parse_cfg(path)
        return found

    def load_file(self, path, label=None):
        if not os.path.isfile(path):
            return False
        self.files[label or os.path.basename(path)] = parse_cfg(path)
        return True

    def sections_named(self, name):
        """Every (relpath, dict) whose section name matches exactly."""
        out = []
        for rel, secs in sorted(self.files.items()):
            if name in secs:
                out.append((rel, secs[name]))
        return out

    def section_startswith(self, prefix):
        out = []
        for rel, secs in sorted(self.files.items()):
            for sec_name, body in secs.items():
                if sec_name == prefix or sec_name.startswith(prefix + " "):
                    out.append((rel, sec_name, body))
        return out

    def get(self, section, key, default=None, record=True):
        key = key.lower()
        for rel, body in self.sections_named(section):
            if key in body:
                if record:
                    self.sources["%s/%s" % (section, key)] = rel
                return body[key]
        if record and default is None:
            self.missing.append("%s / %s" % (section, key))
        return default


# ----------------------------------------------------------------------------
# Value coercion
# ----------------------------------------------------------------------------

def as_float(val, default=None):
    if val is None or val == "":
        return default
    try:
        return float(str(val).strip())
    except ValueError:
        return default


def as_int(val, default=None):
    f = as_float(val, None)
    return default if f is None else int(f)


def as_bool(val, default=None):
    if val is None:
        return default
    s = str(val).strip().strip("'\"").lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return default


def as_list(val, default=None):
    """'-999, -999, 1, 5, 2' -> [-999.0, -999.0, 1.0, 5.0, 2.0]"""
    if val is None or val == "":
        return default
    parts = [p.strip() for p in str(val).replace("[", "").replace("]", "").split(",")]
    out = []
    for p in parts:
        f = as_float(p, None)
        out.append(f if f is not None else p.strip("'\""))
    return out


def as_str(val, default=""):
    if val is None:
        return default
    return str(val).strip().strip("'\"")


def is_real_pin(val):
    """Empty, placeholder ({foo}) and bare-comment values mean 'not fitted'."""
    s = as_str(val, "")
    if not s:
        return False
    if s.startswith("{") and s.endswith("}"):
        return False
    return True


# ----------------------------------------------------------------------------
# Extraction
# ----------------------------------------------------------------------------

# section, key, json_name, type, shipped default (for reference only)
TOOLHEAD_KEYS = [
    ("toolhead_extruder_to_nozzle",   "float", 72.0),
    ("toolhead_sensor_to_nozzle",     "float", 62.0),
    ("toolhead_entry_to_extruder",    "float", 8.0),
    ("toolhead_residual_filament",    "float", 0.0),
    ("toolhead_ooze_reduction",       "float", 0.0),
    ("toolhead_unload_safety_margin", "float", 10.0),
    ("toolhead_homing_max",           "float", 40.0),
    ("toolhead_move_error_tolerance", "float", 60.0),
    ("toolhead_post_load_tighten",    "float", 60.0),
    ("toolhead_entry_tension_test",   "int",   1),
]

PATH_KEYS = [
    ("gate_homing_endstop",       "str",   "encoder"),
    ("gate_homing_max",           "float", 70.0),
    ("gate_parking_distance",     "float", 23.0),
    ("gate_unload_buffer",        "float", 50.0),
    ("gate_endstop_to_encoder",   "float", 10.0),
    ("bowden_homing_max",         "float", 2000.0),
    ("bowden_apply_correction",   "int",   0),
    ("bowden_pre_unload_test",    "int",   1),
    ("extruder_homing_endstop",   "str",   "collision"),
    ("extruder_homing_max",       "float", 80.0),
    ("extruder_homing_buffer",    "float", 25.0),
    ("extruder_force_homing",     "int",   0),
]

TIP_KEYS = [
    ("form_tip_macro",             "str",   "_MMU_FORM_TIP"),
    ("force_form_tip_standalone",  "int",   1),
    ("extruder_form_tip_current",  "float", 100.0),
    ("slicer_tip_park_pos",        "float", 0.0),
    ("sync_form_tip",              "int",   0),
]

PURGE_KEYS = [
    ("purge_macro",              "str",   ""),
    ("force_purge_standalone",   "int",   0),
    ("extruder_purge_current",   "float", 100.0),
    ("sync_purge",               "int",   0),
]

SYNC_KEYS = [
    ("sync_to_extruder",              "int",   0),
    ("sync_gear_current",             "float", 70.0),
    ("sync_feedback_enabled",         "int",   0),
    ("sync_feedback_buffer_range",    "float", 6.0),
    ("sync_feedback_buffer_maxrange", "float", 12.0),
]

CUT_TIP_VARS = [
    ("blade_pos",              "float", 37.5),
    ("retract_length",         "float", 32.5),
    ("rip_length",             "float", 1.0),
    ("pushback_length",        "float", 15.0),
    ("pushback_dwell_time",    "float", 0.0),
    ("simple_tip_forming",     "bool",  True),
    ("restore_position",       "bool",  False),
    ("cutting_axis",           "str",   "x"),
    ("pin_loc_xy",             "list",  None),
    ("pin_loc_compressed_xy",  "list",  None),
    ("pin_park_dist",          "float", 5.0),
    ("cut_stepper_current",    "float", 100.0),
    ("cut_axis_steppers",      "str",   ""),
    ("cut_fast_move_speed",    "float", 32.0),
    ("cut_slow_move_speed",    "float", 8.0),
    ("cut_fast_move_fraction", "float", 1.0),
    ("cut_dwell_time",         "float", 50.0),
    ("extruder_move_speed",    "float", 25.0),
    ("travel_speed",           "float", 150.0),
    ("evacuate_speed",         "float", 150.0),
    ("rip_speed",              "float", 3.0),
    ("safe_margin_xy",         "list",  None),
    ("gantry_servo_enabled",   "bool",  False),
]

FORM_TIP_VARS = [
    ("ramming_volume",            "float", 0.0),
    ("ramming_volume_standalone", "float", 0.0),
    ("cooling_tube_position",     "float", 35.0),
    ("cooling_tube_length",       "float", 10.0),
    ("cooling_moves",             "float", 4.0),
    ("unloading_speed_start",     "float", 80.0),
    ("unloading_speed",           "float", 18.0),
    ("use_skinnydip",             "bool",  False),
    ("parking_distance",          "float", 0.0),
    ("toolchange_temp",           "float", 0.0),
]

SEQUENCE_VARS = [
    ("park_toolchange",              "list", None),
    ("park_runout",                  "list", None),
    ("park_pause",                   "list", None),
    ("restore_xy_pos",               "str",  "last"),
    ("enable_park_printing",         "str",  ""),
    ("enable_park_standalone",       "str",  ""),
    ("min_toolchange_z",             "float", 1.0),
    ("retract_speed",                "float", 30.0),
    ("unretract_speed",              "float", 30.0),
    ("pre_unload_position",          "list",  None),
    ("post_form_tip_position",       "list",  None),
    ("pre_load_position",            "list",  None),
    ("user_pre_unload_extension",    "str",   ""),
    ("user_post_form_tip_extension", "str",   ""),
    ("user_post_unload_extension",   "str",   ""),
    ("user_pre_load_extension",      "str",   ""),
    ("user_post_load_extension",     "str",   ""),
]

BLOBIFIER_VARS = [
    ("purge_length_minimum",  "float", 30.0),
    ("purge_length_maximum",  "float", 150.0),
    ("purge_length",          "float", 150.0),
    ("purge_length_modifier", "float", 0.6),
    ("purge_length_addition", "float", 0.0),
    ("purge_spd",             "float", 400.0),
    ("purge_temp_min",        "float", 200.0),
    ("max_blobs",             "float", 400.0),
    ("z_raise",               "float", 12.0),
    ("z_raise_exp",           "float", 0.85),
    ("purge_start",           "float", 0.2),
    ("retract_between_blobs", "float", 2.0),
    ("part_cooling_fan",      "float", None),
    ("toolhead_x",            "float", None),
    ("toolhead_y",            "float", None),
]

STATE_VARS = [
    "mmu__revision",
    "mmu_state_filament_remaining",
    "mmu_state_filament_remaining_color",
    "mmu_state_last_tool",
    "mmu_state_filament_pos",
    "mmu_state_gate_selected",
    "mmu_state_tool_selected",
    "mmu_calibration_bowden_lengths",
    "mmu_calibration_bowden_home",
    "mmu_calibration_clog_length",
    "mmu_encoder_resolution",
    "mmu_gear_rotation_distances",
    "mmu_statistics_counters",
]

COERCE = {
    "float": as_float,
    "int": as_int,
    "str": as_str,
    "bool": as_bool,
    "list": as_list,
}


def pull(cfg, section, spec):
    """Pull a table of keys out of one section. Returns (values, defaulted)."""
    values = {}
    defaulted = []
    for key, kind, fallback in spec:
        lookup = key if section == "mmu" else "variable_" + key
        raw = cfg.get(section, lookup, default="__MISSING__", record=False)
        if raw == "__MISSING__":
            values[key] = fallback
            defaulted.append(key)
        else:
            values[key] = COERCE[kind](raw, fallback)
            for rel, body in cfg.sections_named(section):
                if lookup in body:
                    cfg.sources["[%s] %s" % (section, lookup)] = rel
                    break
    return values, defaulted


def detect_sensors(cfg):
    s = {}
    sensors = {}
    for _rel, body in cfg.sections_named("mmu_sensors"):
        sensors.update(body)

    s["toolhead"] = is_real_pin(sensors.get("toolhead_switch_pin"))
    s["extruder_entry"] = is_real_pin(sensors.get("extruder_switch_pin"))
    s["gate"] = is_real_pin(sensors.get("gate_switch_pin"))
    s["sync_tension"] = is_real_pin(sensors.get("sync_feedback_tension_pin"))
    s["sync_compression"] = is_real_pin(sensors.get("sync_feedback_compression_pin"))
    s["sync_proportional"] = is_real_pin(sensors.get("sync_feedback_analog_pin"))
    s["pre_gate_count"] = sum(
        1 for k, v in sensors.items()
        if k.startswith("pre_gate_switch_pin_") and is_real_pin(v))
    s["post_gear_count"] = sum(
        1 for k, v in sensors.items()
        if k.startswith("post_gear_switch_pin_") and is_real_pin(v))
    s["encoder"] = bool(cfg.section_startswith("mmu_encoder"))
    s["espooler"] = bool(cfg.section_startswith("mmu_espooler"))
    s["leds"] = bool(cfg.section_startswith("mmu_leds"))
    return s


def detect_addons(cfg):
    """Which optional addons are present and actually wired in."""
    macros = set()
    for _rel, sec_name, _body in cfg.section_startswith("gcode_macro"):
        macros.add(sec_name.split(None, 1)[-1].upper())

    a = {}
    a["blobifier_defined"] = "BLOBIFIER" in macros
    a["erec_defined"] = "EREC_CUTTER_ACTION" in macros
    a["cut_tip_defined"] = "_MMU_CUT_TIP" in macros
    a["form_tip_defined"] = "_MMU_FORM_TIP" in macros
    a["mmu_purge_defined"] = "_MMU_PURGE" in macros
    return a


def find_filament_diameter(cfg, default=1.75):
    for _rel, body in cfg.sections_named("extruder"):
        if "filament_diameter" in body:
            d = as_float(body["filament_diameter"], None)
            if d:
                return d, True
    return default, False


# ----------------------------------------------------------------------------
# Derived values - the arithmetic the docs are built on
# ----------------------------------------------------------------------------

def derive(data):
    th = data["toolhead"]
    cut = data["cut_tip"]
    seq = data["sequence"]
    sens = data["sensors"]
    tip = data["tip"]
    blob = data["blobifier"]

    d = {}
    warn = []

    En = th["toolhead_extruder_to_nozzle"]
    Sn = th["toolhead_sensor_to_nozzle"]
    Xe = th["toolhead_entry_to_extruder"]
    Tres = th["toolhead_residual_filament"]
    Tooze = th["toolhead_ooze_reduction"]
    M = th["toolhead_unload_safety_margin"]

    B = cut["blade_pos"]
    R = cut["retract_length"]
    rip = cut["rip_length"]
    P = cut["pushback_length"]

    park_tc = seq["park_toolchange"] or []
    r_tc = as_float(park_tc[-1], 0.0) if park_tc else 0.0
    d["toolchange_retract"] = r_tc

    cutting = "cut" in as_str(tip["form_tip_macro"], "").lower()
    d["is_toolhead_cutter"] = cutting

    # -- the cut itself -------------------------------------------------
    f_prev = 0.0  # zeroed by _load_extruder() on every successful load
    e = R - (f_prev + Tres) - r_tc
    d["effective_retract_length"] = round(e, 3)
    d["effective_pushback_length"] = round(min(P, e), 3)
    d["stepper_movement"] = round(e + rip, 3)
    d["output_park_pos"] = round(B + rip, 3)
    d["filament_remaining_expected"] = round(B - R, 3)
    d["filament_remaining_physical"] = round(B - R - Tooze, 3)

    # -- load ------------------------------------------------------------
    f = d["filament_remaining_expected"]
    ref = Sn if sens["toolhead"] else En
    d["load_reference"] = "toolhead_sensor_to_nozzle" if sens["toolhead"] \
        else "toolhead_extruder_to_nozzle"
    d["load_final_move"] = round(max(ref - f - Tres - Tooze - r_tc, 0.0), 3)
    d["load_final_move_first_load"] = round(max(ref - 0.0 - Tres - Tooze - r_tc, 0.0), 3)
    d["load_homing_max"] = th["toolhead_homing_max"] if sens["toolhead"] else None

    # -- unload ----------------------------------------------------------
    if sens["extruder_entry"]:
        d["unload_branch"] = "extruder_entry_sensor"
        d["unload_moves"] = [
            {"what": "reverse home to extruder entry sensor (synced)",
             "mm": round(En + Xe + M - Tres - Tooze - r_tc, 3), "homing": True}]
    elif sens["toolhead"]:
        d["unload_branch"] = "toolhead_sensor"
        d["unload_moves"] = [
            {"what": "reverse home to toolhead sensor",
             "mm": round(Sn + M - Tres - Tooze - r_tc, 3), "homing": True},
            {"what": "move to exit extruder",
             "mm": round(En - Sn + M, 3), "homing": False}]
    else:
        d["unload_branch"] = "open_loop"
        d["unload_moves"] = [
            {"what": "move to exit extruder (uses reported park_pos)",
             "mm": round(max(0.0, En - d["output_park_pos"]) + M, 3), "homing": False}]

    # -- purge -----------------------------------------------------------
    dia = data["meta"]["filament_diameter"]
    A = math.pi * (dia / 2.0) ** 2
    d["filament_cross_section"] = round(A, 4)
    d["residual_column"] = round(f + Tres, 3)
    d["purge_volume_added_by_hh"] = round(A * (f + Tres), 3)

    purge_macro = as_str(data["purge"]["purge_macro"], "")
    post_load_ext = as_str(seq["user_post_load_extension"], "")
    blob_wired = (purge_macro.upper().startswith("BLOBIFIER")
                  or "blob" in post_load_ext.lower())
    d["purge_wiring"] = ("purge_macro" if purge_macro.upper().startswith("BLOBIFIER")
                         else "user_post_load_extension" if blob_wired
                         else "purge_macro" if purge_macro else "none")
    if blob_wired:
        d["purge_engine"] = "BLOBIFIER"
        k = blob["purge_length_modifier"]
        add = blob["purge_length_addition"]
        d["purge_formula"] = (
            "L = max(purge_length_minimum, "
            "V_slicer[from][to]*%.3g/A + f + T_res + r_tc + %.3g)" % (k, add))
        base_floor = blob["purge_length_minimum"]
        d["purge_length_zero_slicer"] = round(
            max(base_floor, 0.0 + f + Tres + r_tc + add), 3)
        d["purge_blobs_at_floor"] = int(
            math.ceil(d["purge_length_zero_slicer"] / blob["purge_length_maximum"])) \
            if blob["purge_length_maximum"] else None
    elif purge_macro:
        d["purge_engine"] = purge_macro
        d["purge_formula"] = "L = V_slicer[from][to]/A + f + T_res"
        d["purge_length_zero_slicer"] = round(f + Tres, 3)
    else:
        d["purge_engine"] = None
        d["purge_formula"] = "slicer wipe tower only"
        d["purge_length_zero_slicer"] = None

    # -- constraint checks ------------------------------------------------
    checks = []

    def check(ok, label, detail):
        checks.append({"ok": bool(ok), "check": label, "detail": detail})
        if not ok:
            warn.append("%s - %s" % (label, detail))

    check(Sn <= En, "toolhead_sensor_to_nozzle <= toolhead_extruder_to_nozzle",
          "Sn=%.2f En=%.2f" % (Sn, En))
    check(abs(Tooze) <= 5.0, "|toolhead_ooze_reduction| <= 5",
          "T_ooze=%.2f (a large value means the geometry is wrong)" % Tooze)
    if sens["toolhead"] and Sn <= 0:
        check(False, "toolhead_sensor_to_nozzle is set",
              "a toolhead sensor is fitted but Sn=%.2f" % Sn)
    if sens["extruder_entry"] and Xe <= 0:
        check(False, "toolhead_entry_to_extruder is set",
              "an extruder entry sensor is fitted but Xe=%.2f" % Xe)

    if cutting:
        check(R <= B, "retract_length <= blade_pos",
              "R=%.2f B=%.2f -> fragment %.2f mm%s"
              % (R, B, B - R, "" if R <= B else "  NEGATIVE, nothing gets cut"))
        check(R >= Tres + r_tc, "retract_length >= T_res + r_tc",
              "R=%.2f, floor=%.2f -> effective retract %.2f mm%s"
              % (R, Tres + r_tc, e, "" if e > 0 else "  NO RETRACT HAPPENS"))
        check(B + rip <= En, "blade_pos + rip_length <= toolhead_extruder_to_nozzle",
              "park_pos=%.2f En=%.2f" % (B + rip, En))
        if sens["toolhead"]:
            check(B < Sn, "blade_pos < toolhead_sensor_to_nozzle",
                  "B=%.2f Sn=%.2f (fragment must sit below the sensor)" % (B, Sn))
        check(P <= e, "pushback_length <= effective retract",
              "P=%.2f e=%.2f -> clamped to %.2f" % (P, e, min(P, e)))
        if r_tc > 0:
            enabled = (as_str(seq["enable_park_printing"]).lower() + "," +
                       as_str(seq["enable_park_standalone"]).lower())
            ok = "toolchange" in enabled
            check(ok, "toolchange parking enabled where a retract is configured",
                  ("r_tc=%.2f and 'toolchange' is in enable_park_* -> f = B - R holds"
                   % r_tc) if ok else
                  ("r_tc=%.2f but 'toolchange' is NOT in enable_park_* -> the park "
                   "retract never runs and the recorded fragment is short by %.2f mm"
                   % (r_tc, r_tc)))

    if cutting and not as_bool(str(tip["force_form_tip_standalone"]), False):
        warn.append("force_form_tip_standalone is 0 - the slicer will form tips "
                    "in print and slicer_tip_park_pos (%.1f) will be used instead "
                    "of the cutter" % tip["slicer_tip_park_pos"])

    d["checks"] = checks
    return d, warn


# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------

def hr(title=""):
    if title:
        return "\n" + title + "\n" + "-" * max(len(title), 60)
    return "-" * 60


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return ("%.4f" % v).rstrip("0").rstrip(".") if v % 1 else "%d" % int(v)
    if isinstance(v, list):
        return ", ".join(fmt(x) for x in v)
    return str(v)


def report(data):
    out = []
    a = out.append
    meta = data["meta"]
    d = data["derived"]

    a("=" * 60)
    a("HAPPY HARE TOOLCHANGE PARAMETER EXTRACT  (hh_extract %s)" % VERSION)
    a("=" * 60)
    a("config dir       : %s" % meta["config_dir"])
    a("files parsed     : %d" % meta["files_parsed"])
    a("filament diameter: %s mm%s" % (fmt(meta["filament_diameter"]),
      "" if meta["filament_diameter_found"] else "  (ASSUMED - not found in config)"))

    a(hr("MACHINE"))
    for k, v in sorted(data["machine"].items()):
        a("  %-30s %s" % (k, fmt(v)))

    a(hr("SENSORS DETECTED"))
    for k, v in sorted(data["sensors"].items()):
        a("  %-30s %s" % (k, fmt(v)))

    a(hr("TOOLHEAD GEOMETRY  (mmu_parameters.cfg)"))
    for k, _t, _dflt in TOOLHEAD_KEYS:
        a("  %-30s %s" % (k, fmt(data["toolhead"][k])))

    a(hr("FILAMENT PATH  (mmu_parameters.cfg)"))
    for k, _t, _dflt in PATH_KEYS:
        a("  %-30s %s" % (k, fmt(data["path"][k])))

    a(hr("TIP HANDLING"))
    for k, _t, _dflt in TIP_KEYS:
        a("  %-30s %s" % (k, fmt(data["tip"][k])))
    a("  %-30s %s" % ("-> treated as cutter?", fmt(d["is_toolhead_cutter"])))

    a(hr("CUTTER  (_MMU_CUT_TIP_VARS)"))
    for k, _t, _dflt in CUT_TIP_VARS:
        a("  %-30s %s" % (k, fmt(data["cut_tip"][k])))

    a(hr("PURGE"))
    for k, _t, _dflt in PURGE_KEYS:
        a("  %-30s %s" % (k, fmt(data["purge"][k])))
    if data["addons"]["blobifier_defined"]:
        a("  -- BLOBIFIER --")
        for k, _t, _dflt in BLOBIFIER_VARS:
            if data["blobifier"].get(k) is not None:
                a("  %-30s %s" % (k, fmt(data["blobifier"][k])))

    a(hr("SEQUENCE / PARKING  (_MMU_SEQUENCE_VARS)"))
    for k, _t, _dflt in SEQUENCE_VARS:
        v = data["sequence"][k]
        if v not in (None, ""):
            a("  %-30s %s" % (k, fmt(v)))
    a("  %-30s %s mm   <- toolchange_retract" % ("park_toolchange[retract]",
                                                 fmt(d["toolchange_retract"])))

    a(hr("PERSISTED STATE  (mmu_vars.cfg)"))
    if data["state"]:
        for k in STATE_VARS:
            if k in data["state"]:
                v = data["state"][k]
                if isinstance(v, str) and len(v) > 90:
                    v = v[:87] + "..."
                a("  %-34s %s" % (k, v))
    else:
        a("  (mmu_vars.cfg not found or empty)")

    a(hr("DERIVED  -  what these settings actually do"))
    a("  Symbols: En=extruder_to_nozzle  Sn=sensor_to_nozzle  Xe=entry_to_extruder")
    a("           T_res=residual  T_ooze=ooze_reduction  M=unload_safety_margin")
    a("           B=blade_pos  R=retract_length  rip=rip_length  P=pushback_length")
    a("           r_tc=toolchange retract  f=filament_remaining")
    a("")
    a("  CUT" if d["is_toolhead_cutter"]
      else "  CUT  (form_tip_macro is not a cutter - shown hypothetically)")
    a("    e   = R - (f + T_res) - r_tc          = %s mm" % fmt(d["effective_retract_length"]))
    a("    P_eff = min(P, e)                      = %s mm" % fmt(d["effective_pushback_length"]))
    a("    delta = e + rip  (net extruder move)   = %s mm" % fmt(d["stepper_movement"]))
    a("    park_pos = B + rip                     = %s mm" % fmt(d["output_park_pos"]))
    a("    f   = B - R  (fragment recorded)       = %s mm" % fmt(d["filament_remaining_expected"]))
    a("    f_physical = B - R - T_ooze            = %s mm" % fmt(d["filament_remaining_physical"]))
    a("")
    a("  LOAD  (reference: %s)" % d["load_reference"])
    if d["load_homing_max"] is not None:
        a("    home to toolhead sensor, max         = %s mm" % fmt(d["load_homing_max"]))
    a("    final move after a cut                 = %s mm" % fmt(d["load_final_move"]))
    a("    final move with no fragment (f=0)      = %s mm" % fmt(d["load_final_move_first_load"]))
    a("")
    a("  UNLOAD  (branch: %s)" % d["unload_branch"])
    for mv in d["unload_moves"]:
        a("    %-38s %s mm%s" % (mv["what"], fmt(mv["mm"]),
                                 "  (max)" if mv["homing"] else ""))
    a("")
    a("  PURGE  (engine: %s)" % (d["purge_engine"] or "none"))
    a("    cross-section A = pi*(d/2)^2           = %s mm2" % fmt(d["filament_cross_section"]))
    a("    residual column f + T_res              = %s mm" % fmt(d["residual_column"]))
    a("    volume Happy Hare adds                 = %s mm3" % fmt(d["purge_volume_added_by_hh"]))
    a("    %s" % d["purge_formula"])
    if d.get("purge_length_zero_slicer") is not None:
        a("    length with an empty purge matrix      = %s mm" % fmt(d["purge_length_zero_slicer"]))
    if d.get("purge_blobs_at_floor"):
        a("    blobs at that length                   = %s" % fmt(d["purge_blobs_at_floor"]))

    a(hr("CONSTRAINT CHECKS"))
    for c in d["checks"]:
        a("  [%s] %s" % ("OK" if c["ok"] else "!!", c["check"]))
        a("       %s" % c["detail"])

    if data["warnings"]:
        a(hr("WARNINGS"))
        for w in data["warnings"]:
            a("  !! %s" % w)

    if data["defaulted"]:
        a(hr("NOT FOUND IN YOUR CONFIG  (shipped defaults assumed above)"))
        for k in data["defaulted"]:
            a("  ?  %s" % k)

    a("")
    a("=" * 60)
    a("End of report. Machine-readable values are in the JSON companion file.")
    a("=" * 60)
    return "\n".join(out)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def failed_paths(failed):
    return set(path for path, _exc in failed)


def main():
    ap = argparse.ArgumentParser(
        description="Extract Happy Hare tip-cutting / toolchange parameters.")
    ap.add_argument("-d", "--config-dir",
                    default=os.path.expanduser("~/printer_data/config/mmu"),
                    help="Happy Hare config dir (default: ~/printer_data/config/mmu)")
    ap.add_argument("-p", "--printer-config", default=None,
                    help="printer.cfg, scanned for [extruder] filament_diameter "
                         "(default: <config-dir>/../printer.cfg)")
    ap.add_argument("-o", "--out-dir", default=".",
                    help="directory for the output files (default: current dir)")
    ap.add_argument("--report-out", default=None,
                    help="report path (default: <out-dir>/%s)" % DEFAULT_REPORT)
    ap.add_argument("--json-out", default=None,
                    help="JSON path (default: <out-dir>/%s)" % DEFAULT_JSON)
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="write the files but don't print the report")
    ap.add_argument("--stdout", action="store_true",
                    help="also print the JSON to stdout for copy/paste")
    ap.add_argument("--no-files", action="store_true",
                    help="don't write any files, print report and JSON instead")
    args = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(args.config_dir))
    if not os.path.isdir(root):
        sys.stderr.write("Config dir not found: %s\n"
                         "Pass the right one with -d /path/to/config/mmu\n" % root)
        return 2

    cfg = Config()
    found = cfg.load_dir(root)
    if not found:
        sys.stderr.write("No .cfg files under %s\n" % root)
        return 2

    printer_cfg = args.printer_config or os.path.join(root, os.pardir, "printer.cfg")
    cfg.load_file(os.path.abspath(printer_cfg), label="printer.cfg")

    dia, dia_found = find_filament_diameter(cfg)

    data = {}
    defaulted = []

    data["meta"] = {
        "tool": "hh_extract",
        "tool_version": VERSION,
        "config_dir": root,
        "files_parsed": len(cfg.files),
        "file_list": sorted(cfg.files.keys()),
        "filament_diameter": dia,
        "filament_diameter_found": dia_found,
    }

    machine = {}
    for _rel, body in cfg.sections_named("mmu_machine"):
        for k in ("num_gates", "mmu_vendor", "mmu_version", "homing_extruder",
                  "selector_type", "variable_bowden_lengths",
                  "variable_rotation_distances", "require_bowden_move",
                  "filament_always_gripped"):
            if k in body:
                machine.setdefault(k, as_str(body[k]))
    data["machine"] = machine

    data["sensors"] = detect_sensors(cfg)
    data["addons"] = detect_addons(cfg)

    for name, section, spec in (
            ("toolhead", "mmu", TOOLHEAD_KEYS),
            ("path", "mmu", PATH_KEYS),
            ("tip", "mmu", TIP_KEYS),
            ("purge", "mmu", PURGE_KEYS),
            ("sync", "mmu", SYNC_KEYS),
            ("cut_tip", "gcode_macro _MMU_CUT_TIP_VARS", CUT_TIP_VARS),
            ("form_tip", "gcode_macro _MMU_FORM_TIP_VARS", FORM_TIP_VARS),
            ("sequence", "gcode_macro _MMU_SEQUENCE_VARS", SEQUENCE_VARS),
            ("blobifier", "gcode_macro BLOBIFIER", BLOBIFIER_VARS)):
        values, missing = pull(cfg, section, spec)
        data[name] = values
        defaulted.extend("%s.%s" % (name, k) for k in missing)

    state = {}
    for _rel, body in cfg.sections_named("Variables"):
        for k, v in body.items():
            state[k] = v
    data["state"] = {k: state[k] for k in STATE_VARS if k in state}
    data["state_all_keys"] = sorted(state.keys())

    data["derived"], warnings = derive(data)
    data["warnings"] = warnings
    data["defaulted"] = defaulted
    data["sources"] = dict(sorted(cfg.sources.items()))

    payload = json.dumps(data, indent=2, sort_keys=True, default=str)
    text = report(data)

    if args.no_files:
        print(text)
        print(JSON_BEGIN)
        print(payload)
        print(JSON_END)
        return 0

    out_dir = os.path.abspath(os.path.expanduser(args.out_dir))
    report_path = os.path.abspath(os.path.expanduser(args.report_out)) \
        if args.report_out else os.path.join(out_dir, DEFAULT_REPORT)
    json_path = os.path.abspath(os.path.expanduser(args.json_out)) \
        if args.json_out else os.path.join(out_dir, DEFAULT_JSON)

    written, failed = [], []
    for path, body in ((report_path, text + "\n\nJSON companion: %s\n" % json_path),
                       (json_path, payload + "\n")):
        try:
            parent = os.path.dirname(path)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            with open(path, "w") as fh:
                fh.write(body)
            written.append(path)
        except (IOError, OSError) as exc:
            failed.append((path, exc))

    for path, exc in failed:
        sys.stderr.write("! could not write %s: %s\n" % (path, exc))

    # Nothing may be silently lost: anything that failed to reach a file goes to
    # stdout instead, whatever the flags said.
    report_shown = not args.quiet
    json_shown = args.stdout
    if report_path in failed_paths(failed) and not report_shown:
        sys.stderr.write("! printing the report to stdout instead\n")
        report_shown = True
    if json_path in failed_paths(failed) and not json_shown:
        sys.stderr.write("! printing the JSON to stdout instead\n")
        json_shown = True

    if report_shown:
        print(text)
    if json_shown:
        print(JSON_BEGIN)
        print(payload)
        print(JSON_END)

    if written:
        sys.stderr.write("\nWrote:\n")
        for path in written:
            sys.stderr.write("  %s  (%d bytes)\n" % (path, os.path.getsize(path)))
        if json_path in written:
            sys.stderr.write("\nSend %s to have the documentation rebuilt "
                             "against your machine.\n" % os.path.basename(json_path))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
