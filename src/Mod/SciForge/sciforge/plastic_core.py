# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plastic rules, pure Python (no FreeCAD, no Qt), unit tested.

A plastic rule is what Fusion keeps in its Manage Plastic Rules dialog: the nominal wall
thickness of a moulded part, its draft angle, the nominal radius of its inside corners, the
lip's reveal height and the clearance between mating parts, the material, and the limits the
Design Advice check uses. A rule is assigned to a component (never to a single body); the
PLASTIC tools (Boss, Snap Fit, Lip, Rest) and the repeated SOLID tools (Shell, Thicken, Rib,
Web, Draft, Emboss, Extrude's thin wall, Fillet) take their default values from it. Lengths
may be expressions in "Thickness" ("Thickness / 2").

The values of LIBRARY are SciForge's own starting points (typical injection-moulding
guidance; docs/sciforge/dev/research/fusion-plastic.md 3.3), not Fusion's data.

This file is the shared contract of the PLASTIC builders (wave 6): plastic.py and every
plastic tool use the names below. Add to it; never rename or remove.
"""

from .sheetmetal_core import MM_PER_UNIT, evaluate_expression

UNITS = ("mm", "in")

# Field -> (kind, default). "length": a number or an expression in Thickness, in the rule's
# units; "angle": degrees; "percent": a percentage; "text": free text.
FIELDS = {
    "name": ("text", "Default (mm)"),
    "units": ("choice", "mm"),
    "material": ("text", "ABS"),
    "thickness": ("length", "2.0"),
    "draft_angle": ("angle", "1.0"),
    "nominal_radius": ("length", "Thickness / 2"),
    "reveal_height": ("length", "Thickness / 2"),
    "clearance": ("length", "0.1"),
    "minimum_thickness": ("length", "1.0"),
    "maximum_thickness": ("length", "4.0"),
    "thickness_variation": ("percent", "25"),
    "minimum_draft_angle": ("angle", "0.5"),
    "knife_edge_threshold": ("length", "Thickness / 4"),
}
CHOICES = {"units": UNITS}
LENGTH_FIELDS = tuple(k for k, (kind, _) in FIELDS.items() if kind == "length")
NUMBER_FIELDS = tuple(k for k, (kind, _) in FIELDS.items() if kind in ("angle", "percent"))


def make_rule(name, **values):
    """A rule dict with every field: the defaults, then values (numbers become text)."""
    rule = {key: default for key, (_kind, default) in FIELDS.items()}
    rule["name"] = name
    for key, value in values.items():
        if key not in FIELDS:
            raise KeyError("unknown plastic rule field: %s" % key)
        rule[key] = value if isinstance(value, str) else repr(float(value))
    return rule


def _mm(name, material, thickness, lo, hi, draft, min_draft, clearance="0.1"):
    return make_rule(
        name,
        material=material,
        thickness=thickness,
        minimum_thickness=lo,
        maximum_thickness=hi,
        draft_angle=draft,
        minimum_draft_angle=min_draft,
        clearance=clearance,
    )


LIBRARY = (
    _mm("Default (mm)", "ABS", "2.0", "1.0", "4.0", "1.0", "0.5"),
    make_rule(
        "Default (in)",
        units="in",
        material="ABS",
        thickness="0.08",
        minimum_thickness="0.04",
        maximum_thickness="0.16",
        clearance="0.004",
    ),
    _mm("ABS 2 mm", "ABS", "2.0", "1.2", "3.5", "1.0", "0.5"),
    _mm("ABS 1.5 mm", "ABS", "1.5", "1.2", "3.5", "1.0", "0.5"),
    _mm("PC 2 mm", "Polycarbonate", "2.0", "1.0", "3.8", "1.0", "0.5"),
    _mm("PC/ABS 2 mm", "PC/ABS", "2.0", "1.0", "3.5", "1.0", "0.5"),
    _mm("PP 1.5 mm", "Polypropylene", "1.5", "0.8", "3.8", "1.5", "1.0", "0.15"),
    _mm("PA66 1.5 mm", "Nylon 6/6", "1.5", "0.8", "3.0", "1.0", "0.5"),
    _mm("POM 1.5 mm", "Acetal", "1.5", "0.8", "3.0", "1.0", "0.5"),
    _mm("HIPS 2 mm", "Polystyrene (HI)", "2.0", "1.0", "3.8", "1.0", "0.5"),
    _mm("HDPE 2 mm", "Polyethylene HD", "2.0", "0.8", "5.0", "1.5", "1.0", "0.15"),
    _mm("PBT 1.8 mm", "PBT", "1.8", "0.8", "3.0", "1.0", "0.5"),
    _mm("PMMA 2.5 mm", "Acrylic", "2.5", "0.8", "3.8", "1.0", "0.5"),
    _mm("TPE 1.5 mm", "TPE", "1.5", "0.6", "3.0", "2.0", "1.0"),
    _mm("FDM PLA 2 mm", "PLA", "2.0", "0.8", "6.0", "0.0", "0.0", "0.3"),
    _mm("FDM PETG 2 mm", "PETG", "2.0", "0.8", "6.0", "0.0", "0.0", "0.3"),
)
DEFAULT_RULE = LIBRARY[0]["name"]

# Allowable strain (%) for the snap fit check, typical published values (G).
ALLOWABLE_STRAIN = {
    "ABS": 2.5,
    "Polycarbonate": 4.0,
    "PC/ABS": 3.0,
    "Polypropylene": 6.0,
    "Nylon 6/6": 4.0,
    "Acetal": 6.0,
    "Polystyrene (HI)": 2.0,
    "Polyethylene HD": 6.0,
    "PBT": 4.0,
    "Acrylic": 1.5,
    "TPE": 10.0,
    "PLA": 2.0,
    "PETG": 3.0,
}


# The rule's material -> SciForge's physical material (material.LIBRARY key); a material
# SciForge's library does not have is None (the bodies keep theirs). Added by plastic-1.
MATERIAL_KEYS = {
    "ABS": "abs",
    "Polycarbonate": "polycarbonate",
    "Polypropylene": "polypropylene",
    "Nylon 6/6": "nylon",
    "Acetal": "acetal",
    "Acrylic": "acrylic",
    "PLA": "pla",
    "PETG": "pet",
}
MATERIALS = tuple(ALLOWABLE_STRAIN)
LABELS = {
    "name": "Name",
    "units": "Units",
    "material": "Material",
    "thickness": "Thickness",
    "draft_angle": "Draft Angle",
    "nominal_radius": "Nominal Radius",
    "reveal_height": "Reveal Height",
    "clearance": "Clearance",
    "minimum_thickness": "Minimum Thickness",
    "maximum_thickness": "Maximum Thickness",
    "thickness_variation": "Thickness Variation (%)",
    "minimum_draft_angle": "Minimum Draft Angle",
    "knife_edge_threshold": "Knife Edge Threshold",
}


def describe(rule):
    """[(label, text)] of a rule's values for the dialogs (expressions as typed, units)."""
    rows = []
    unit = rule.get("units", "mm")
    for key in FIELDS:
        if key == "name":
            continue
        kind = FIELDS[key][0]
        value = str(rule.get(key, ""))
        if kind == "length":
            try:
                float(value)
                value = "%s %s" % (value, unit)
            except ValueError:
                pass
        elif kind == "angle":
            value = "%s deg" % value
        elif kind == "percent":
            value = "%s %%" % value
        rows.append((LABELS[key], value))
    return rows


def library_rule(name):
    """A copy of the library rule with this name, or None."""
    for rule in LIBRARY:
        if rule["name"] == name:
            return dict(rule)
    return None


def validate(rule):
    """[] when the rule is usable, else the reasons (texts for the dialog)."""
    problems = []
    for key in FIELDS:
        if key not in rule:
            problems.append("%s is missing" % key)
    if problems:
        return problems
    if rule["units"] not in UNITS:
        return ["units must be mm or in"]
    try:
        thickness = evaluate_expression(rule["thickness"])
    except ValueError as exc:
        return ["Thickness: %s" % exc]
    if thickness <= 0:
        return ["Thickness must be more than 0"]
    values = {}
    for key in LENGTH_FIELDS + NUMBER_FIELDS:
        try:
            values[key] = evaluate_expression(rule[key], thickness)
        except ValueError as exc:
            problems.append("%s: %s" % (key, exc))
            continue
        if values[key] < 0:
            problems.append("%s cannot be negative" % key)
    if problems:
        return problems
    if values["minimum_thickness"] > values["maximum_thickness"]:
        problems.append("the thickness range's minimum is above its maximum")
    elif not values["minimum_thickness"] <= thickness <= values["maximum_thickness"]:
        problems.append("Thickness must lie within the thickness range")
    if values["draft_angle"] >= 45 or values["minimum_draft_angle"] >= 45:
        problems.append("draft angles must be under 45 degrees")
    return problems


def evaluated(rule):
    """The rule with every length in millimetres (floats), angles in degrees (floats), the
    percentage a float. Raises ValueError (the first problem) for a rule that does not
    validate."""
    problems = validate(rule)
    if problems:
        raise ValueError(problems[0])
    scale = MM_PER_UNIT[rule["units"]]
    thickness = evaluate_expression(rule["thickness"])
    out = dict(rule)
    for key in LENGTH_FIELDS:
        out[key] = evaluate_expression(rule[key], thickness) * scale
    for key in NUMBER_FIELDS:
        out[key] = evaluate_expression(rule[key], thickness)
    return out
