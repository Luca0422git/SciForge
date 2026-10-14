# SPDX-License-Identifier: LGPL-2.1-or-later
"""The text of a drawing dimension as Fusion's Dimension dialog sets it: override, text
before and after the value, symbols, precision, tolerances (None, Symmetric, Deviation,
Limits, Fit with ISO 286 classes), Basic (a box) and Reference (parentheses). Pure
Python (no FreeCAD, no Qt), unit tested (SciForgeTests/unit/test_drawing_dims_core.py).

drawing.py turns the result into TechDraw's dimension properties: the main text, the
two small stacked tolerance texts beside it and the frame of a basic dimension.
"""

import json

from . import drawing_fits as fits

MM_PER_IN = 25.4
TOLERANCES = ("None", "Symmetric", "Deviation", "Limits", "Fit")
FIT_DISPLAYS = ("Class", "Class and tolerances", "Limits", "Fit")
FIT_MEMBERS = ("Hole", "Shaft")
# Fusion's precision list: 0, 0.1, 0.12, 0.123, 0.1234 (decimals); "Default" keeps the
# drawing's own setting (up to 2 decimals in mm, 3 in inches, no trailing zeros).
PRECISIONS = ("Default", "0", "0.1", "0.12", "0.123", "0.1234")
SYMBOLS = (
    ("⌀", "Diameter"),
    ("R", "Radius"),
    ("□", "Square"),
    ("°", "Degree"),
    ("±", "Plus / minus"),
    ("⌓", "Arc length"),
    ("↕", "Depth"),
    ("⌴", "Counterbore"),
    ("⌵", "Countersink"),
)
DIAMETER = "⌀"
PLUS_MINUS = "±"

DEFAULTS = {
    "override": "",
    "prefix": "",
    "suffix": "",
    "precision": "Default",
    "tolerance": "None",
    "upper": 0.0,
    "lower": 0.0,
    "fit_basis": "Hole",
    "fit": "H7/g6",
    "fit_member": "Hole",
    "fit_display": "Class",
    "tol_precision": "Default",
    "basic": False,
    "reference": False,
}


def settings(data=None):
    """A full settings dict (defaults filled in) from a dict or its JSON text."""
    if isinstance(data, str):
        try:
            data = json.loads(data) if data.strip() else {}
        except ValueError:
            data = {}
    out = dict(DEFAULTS)
    for key, value in (data or {}).items():
        if key in DEFAULTS:
            out[key] = value
    if out["tolerance"] not in TOLERANCES:
        out["tolerance"] = "None"
    if out["fit_display"] not in FIT_DISPLAYS:
        out["fit_display"] = "Class"
    if out["fit_member"] not in FIT_MEMBERS:
        out["fit_member"] = "Hole"
    for key in ("upper", "lower"):
        try:
            out[key] = float(out[key])
        except (TypeError, ValueError):
            out[key] = 0.0
    out["basic"] = bool(out["basic"])
    out["reference"] = bool(out["reference"])
    return out


def to_json(data):
    """Only what differs from the defaults (an untouched dimension stores nothing)."""
    full = settings(data)
    return json.dumps({k: v for k, v in full.items() if v != DEFAULTS[k]}, sort_keys=True)


def is_default(data):
    return to_json(data) == "{}"


# ------------------------------------------------------------------ numbers
def decimals_of(precision, units, kind="length"):
    """Decimals a precision choice gives ("Default": None, meaning up to 2 in mm, 3 in
    inches, 2 for angles, with no trailing zeros)."""
    if precision in (None, "", "Default"):
        return None
    text = str(precision)
    if "." in text:
        return len(text.split(".")[1])
    try:
        return max(0, int(text)) if text != "0" else 0
    except ValueError:
        return None


def number(value, decimals=None, units="mm", kind="length", plus=False):
    """A value as written on the drawing: lengths in mm or inches (value is mm), angles
    in degrees. decimals None: the default, trailing zeros dropped."""
    if kind == "length" and units == "in":
        value = value / MM_PER_IN
    if decimals is None:
        places = 3 if (kind == "length" and units == "in") else 2
        text = ("%." + str(places) + "f") % value
        text = text.rstrip("0").rstrip(".")
    else:
        text = ("%." + str(int(decimals)) + "f") % value
    if text in ("-0", "") or (text.startswith("-") and float(text) == 0.0):
        text = text.lstrip("-") or "0"
    if plus and not text.startswith("-") and float(text) != 0.0:
        text = "+" + text
    return text


def tolerance_number(value, decimals, units):
    """A tolerance value (mm): signed, 0 written as 0 (Fusion: +0.015 / 0)."""
    if abs(value) < 1e-12:
        return "0"
    places = decimals if decimals is not None else (4 if units == "in" else 3)
    return number(value, places, units, "length", plus=True)


# ------------------------------------------------------------------ the dimension's text
def symbol_for(kind):
    """The symbol before a value: the diameter sign, R for a radius."""
    return {"Diameter": DIAMETER, "Radius": "R"}.get(kind, "")


def _wrap(prefix, body, suffix):
    return "%s%s%s" % (prefix or "", body, suffix or "")


def texts(value, kind="Distance", units="mm", data=None):
    """{"main": text, "over": small upper text, "under": small lower text, "framed":
    bool, "lines": [main lines]} of a dimension whose measured value is `value` (mm, or
    degrees for kind "Angle"). kind: Distance, Diameter, Radius or Angle."""
    s = settings(data)
    angular = kind == "Angle"
    measure = "angle" if angular else "length"
    decimals = decimals_of(s["precision"], units, measure)
    tol_decimals = decimals_of(s["tol_precision"], units, measure)
    symbol = symbol_for(kind)
    unit = "°" if angular else ""

    def show(v):
        return number(v, decimals, units, measure) + unit

    nominal = show(value)
    if s["override"].strip():
        nominal = s["override"].strip()
    over = under = ""
    framed = bool(s["basic"])
    tol = s["tolerance"] if not (s["basic"] or s["reference"]) else "None"
    if tol == "Symmetric":
        amount = abs(s["upper"])
        body = "%s %s%s" % (nominal, PLUS_MINUS, _tol_plain(amount, tol_decimals, units, angular))
        main = _wrap(s["prefix"], symbol + body, s["suffix"])
    elif tol == "Deviation":
        main = _wrap(s["prefix"], symbol + nominal, s["suffix"])
        over = _tol_signed(s["upper"], tol_decimals, units, angular)
        under = _tol_signed(s["lower"], tol_decimals, units, angular)
    elif tol == "Limits":
        top = show(value + s["upper"]) if not angular else show(value + s["upper"])
        bottom = show(value + s["lower"])
        main = "\n".join(
            [_wrap(s["prefix"], symbol + top, s["suffix"]), _wrap(s["prefix"], symbol + bottom, "")]
        )
    elif tol == "Fit" and not angular:
        main, over, under = _fit_texts(value, s, symbol, nominal, units, decimals, tol_decimals)
    else:
        main = _wrap(s["prefix"], symbol + nominal, s["suffix"])
    if s["reference"]:
        main = "\n".join("(%s)" % line for line in main.split("\n"))
    return {
        "main": main,
        "over": over,
        "under": under,
        "framed": framed,
        "lines": main.split("\n"),
    }


def _tol_plain(amount, decimals, units, angular):
    if angular:
        return number(amount, decimals if decimals is not None else 2, units, "angle") + "°"
    return tolerance_number(amount, decimals, units).lstrip("+")


def _tol_signed(amount, decimals, units, angular):
    if angular:
        if abs(amount) < 1e-12:
            return "0°"
        return number(amount, decimals, units, "angle", plus=True) + "°"
    return tolerance_number(amount, decimals, units)


def fit_classes(s):
    """(hole class, shaft class) of the settings' fit."""
    return fits.parse_fit(s["fit"])


def member_class(s):
    hole, shaft = fit_classes(s)
    return hole if s["fit_member"] == "Hole" else shaft


def _fit_texts(value, s, symbol, nominal, units, decimals, tol_decimals):
    """Main, over and under texts of a Fit tolerance."""
    try:
        hole, shaft = fit_classes(s)
        cls = hole if s["fit_member"] == "Hole" else shaft
        upper, lower = fits.deviations(cls, value)
    except fits.FitError as exc:
        return _wrap(s["prefix"], symbol + nominal, s["suffix"]) + " (%s)" % exc, "", ""
    display = s["fit_display"]
    if display == "Limits":
        top = number(value + upper, decimals if decimals is not None else 3, units)
        bottom = number(value + lower, decimals if decimals is not None else 3, units)
        main = "\n".join(
            [_wrap(s["prefix"], symbol + top, s["suffix"]), _wrap(s["prefix"], symbol + bottom, "")]
        )
        return main, "", ""
    if display == "Fit":
        return (
            _wrap(s["prefix"], "%s%s %s/%s" % (symbol, nominal, hole, shaft), s["suffix"]),
            "",
            "",
        )
    main = _wrap(s["prefix"], "%s%s %s" % (symbol, nominal, cls), s["suffix"])
    if display == "Class and tolerances":
        return (
            main,
            tolerance_number(upper, tol_decimals, units),
            tolerance_number(lower, tol_decimals, units),
        )
    return main, "", ""


def limit_values(value, data=None):
    """(largest, smallest) size the dimension allows, mm (None, None without a
    tolerance)."""
    s = settings(data)
    tol = s["tolerance"] if not (s["basic"] or s["reference"]) else "None"
    if tol == "Symmetric":
        return value + abs(s["upper"]), value - abs(s["upper"])
    if tol in ("Deviation", "Limits"):
        return value + s["upper"], value + s["lower"]
    if tol == "Fit":
        try:
            upper, lower = fits.deviations(member_class(s), value)
        except fits.FitError:
            return None, None
        return value + upper, value + lower
    return None, None


def one_line(result):
    """All of a dimension's text on one line (the DXF, logs): "12 H7 +0.018/0"."""
    main = " / ".join(result["lines"])
    if result["over"] or result["under"]:
        main = "%s %s/%s" % (main, result["over"] or "0", result["under"] or "0")
    if result["framed"]:
        main = "[%s]" % main
    return main


def validate(data, value=None, kind="Distance"):
    """A sentence saying what is wrong with the settings, or ""."""
    s = settings(data)
    if s["tolerance"] == "Fit":
        if kind == "Angle":
            return "An angle has no ISO fit: choose another tolerance."
        try:
            hole, shaft = fit_classes(s)
            if value is not None:
                fits.deviations(hole, value)
                fits.deviations(shaft, value)
        except fits.FitError as exc:
            return str(exc)
    if s["tolerance"] in ("Deviation", "Limits") and s["upper"] < s["lower"]:
        return "The upper tolerance must be above the lower one."
    if s["tolerance"] == "Symmetric" and abs(s["upper"]) < 1e-12:
        return "Type the tolerance (the value after ±)."
    return ""
