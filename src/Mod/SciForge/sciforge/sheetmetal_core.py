# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sheet metal rules and bend maths, pure Python (no FreeCAD, no Qt), unit tested.

A sheet metal rule is what Fusion keeps in its Sheet Metal Rules dialog: the sheet's
thickness, the bend radius, the K-factor that says where the neutral layer lies in a bend,
the bend relief and the corner reliefs. Every length may be a number or an expression in
"Thickness" ("Thickness * 2", "Thickness / 2"), like Fusion's rule library, so changing the
thickness of a rule moves every value that follows it.

This file is the shared contract of the SHEET METAL builders (wave 6): the field names and
the functions below are used by sheetmetal.py (where a design keeps its rules) and by every
sheet metal tool. Add to it; never rename or remove.
"""

import ast
import math
import operator

# Bend relief at the ends of a bend that does not run the whole edge (Fusion's
# BendReliefShapes: Straight, Tear, Round).
BEND_RELIEF_SHAPES = ("straight", "tear", "round")
# Relief where two bends meet at a corner (TwoBendReliefShapes).
TWO_BEND_SHAPES = (
    "round",
    "square",
    "tear",
    "trim_to_bend",
    "linear_weld",
    "arc_weld",
    "laser_weld",
)
TWO_BEND_PLACEMENTS = ("intersection", "tangent")
# Relief where three bends meet (ThreeBendReliefShapes).
THREE_BEND_SHAPES = ("no_replacement", "intersection", "full_round", "round_with_radius")
UNFOLD_RULES = ("k_factor",)
UNITS = ("mm", "in")
MM_PER_UNIT = {"mm": 1.0, "in": 25.4}

# Field -> (kind, default). kind "length": a number or an expression in Thickness (in the
# rule's units); "number": a plain number; "choice": one of the tuple named by the field.
FIELDS = {
    "name": ("text", "Steel (mm)"),
    "units": ("choice", "mm"),
    "thickness": ("length", "1.0"),
    "bend_radius": ("length", "Thickness"),
    "k_factor": ("number", "0.44"),
    "unfold_rule": ("choice", "k_factor"),
    "miter_gap": ("length", "Thickness"),
    "bend_relief_shape": ("choice", "round"),
    "bend_relief_width": ("length", "Thickness"),
    "bend_relief_depth": ("length", "Thickness / 2"),
    "bend_relief_remnant": ("length", "Thickness * 2"),
    "corner_relief_2bend_shape": ("choice", "round"),
    "corner_relief_2bend_placement": ("choice", "intersection"),
    "corner_relief_2bend_size": ("length", "Thickness * 4"),
    "corner_relief_3bend_shape": ("choice", "round_with_radius"),
    "corner_relief_3bend_radius": ("length", "Thickness * 4"),
}
CHOICES = {
    "units": UNITS,
    "unfold_rule": UNFOLD_RULES,
    "bend_relief_shape": BEND_RELIEF_SHAPES,
    "corner_relief_2bend_shape": TWO_BEND_SHAPES,
    "corner_relief_2bend_placement": TWO_BEND_PLACEMENTS,
    "corner_relief_3bend_shape": THREE_BEND_SHAPES,
}
LENGTH_FIELDS = tuple(k for k, (kind, _) in FIELDS.items() if kind == "length")


def make_rule(name, **values):
    """A rule dict with every field: the defaults, then values (numbers become text)."""
    rule = {key: default for key, (_kind, default) in FIELDS.items()}
    rule["name"] = name
    for key, value in values.items():
        if key not in FIELDS:
            raise KeyError("unknown sheet metal rule field: %s" % key)
        rule[key] = value if isinstance(value, str) else repr(float(value))
    return rule


# The rule library shipped with SciForge (Fusion ships a similar one: steel, stainless steel,
# aluminum and copper in mm and in; K-factor 0.44 everywhere, bend radius = thickness).
# The first rule is the default of a new design.
LIBRARY = (
    make_rule("Steel (mm)", thickness="1.0"),
    make_rule("Steel (in)", units="in", thickness="0.06"),
    make_rule("Stainless Steel (mm)", thickness="1.0"),
    make_rule("Stainless Steel (in)", units="in", thickness="0.06"),
    make_rule("Aluminum (mm)", thickness="2.0"),
    make_rule("Aluminum (in)", units="in", thickness="0.08"),
    make_rule("Copper (mm)", thickness="1.0"),
    make_rule("Copper (in)", units="in", thickness="0.04"),
)
DEFAULT_RULE = LIBRARY[0]["name"]


def library_rule(name):
    """A copy of the library rule with this name, or None."""
    for rule in LIBRARY:
        if rule["name"] == name:
            return dict(rule)
    return None


# -- expressions -------------------------------------------------------------------------------
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}


def _eval(node, names):
    if isinstance(node, ast.Expression):
        return _eval(node.body, names)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        for key, value in names.items():
            if key.lower() == node.id.lower():
                return float(value)
        raise ValueError("unknown name '%s' (use Thickness)" % node.id)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left, names), _eval(node.right, names))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval(node.operand, names)
        return -value if isinstance(node.op, ast.USub) else value
    raise ValueError("not a number or an expression in Thickness")


def evaluate_expression(text, thickness=None):
    """A rule value: a number, or an arithmetic expression in Thickness. Units written after
    a number ("2 mm") are not accepted here: rule values are in the rule's units. Raises
    ValueError with a reason."""
    text = str(text).strip()
    if not text:
        raise ValueError("empty value")
    names = {} if thickness is None else {"Thickness": thickness}
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        raise ValueError("'%s' is not a number or an expression in Thickness" % text)
    try:
        return _eval(tree, names)
    except ZeroDivisionError:
        raise ValueError("'%s' divides by zero" % text)


def validate(rule):
    """[] when the rule is usable, else the reasons (texts for the dialog)."""
    problems = []
    for key, (kind, _default) in FIELDS.items():
        if key not in rule:
            problems.append("%s is missing" % key)
            continue
        if kind == "choice" and rule[key] not in CHOICES[key]:
            problems.append("%s must be one of %s" % (key, ", ".join(CHOICES[key])))
    if problems:
        return problems
    try:
        thickness = evaluate_expression(rule["thickness"])
    except ValueError as exc:
        return ["Thickness: %s" % exc]
    if thickness <= 0:
        return ["Thickness must be more than 0"]
    for key in LENGTH_FIELDS:
        try:
            value = evaluate_expression(rule[key], thickness)
        except ValueError as exc:
            problems.append("%s: %s" % (key, exc))
            continue
        if value < 0:
            problems.append("%s cannot be negative" % key)
    try:
        k = float(rule["k_factor"])
        if not 0.0 <= k <= 1.0:
            problems.append("K-factor must be between 0 and 1")
    except ValueError:
        problems.append("K-factor must be a number")
    return problems


def evaluated(rule):
    """The rule with every length in millimetres (floats), the K-factor a float, choices
    as they are. Raises ValueError (the first problem) for a rule that does not validate."""
    problems = validate(rule)
    if problems:
        raise ValueError(problems[0])
    scale = MM_PER_UNIT[rule["units"]]
    thickness = evaluate_expression(rule["thickness"])
    out = dict(rule)
    for key in LENGTH_FIELDS:
        out[key] = evaluate_expression(rule[key], thickness) * scale
    out["k_factor"] = float(rule["k_factor"])
    return out


# -- bend maths --------------------------------------------------------------------------------
def neutral_radius(inner_radius, thickness, k_factor):
    """Radius of the neutral layer of a bend: inner radius + K * thickness."""
    return inner_radius + k_factor * thickness


def bend_allowance(angle_deg, inner_radius, thickness, k_factor):
    """Length of the neutral layer through a bend of angle_deg (the bend's own angle, 90 for
    a right-angle flange): angle (radians) * (R + K * T). The flat pattern gives each bend
    this length."""
    return math.radians(abs(angle_deg)) * neutral_radius(inner_radius, thickness, k_factor)


def outside_setback(angle_deg, inner_radius, thickness):
    """Distance from the tangent line of a bend to the virtual sharp (outer mould line):
    (R + T) * tan(angle / 2)."""
    return (inner_radius + thickness) * math.tan(math.radians(abs(angle_deg)) / 2.0)


def bend_deduction(angle_deg, inner_radius, thickness, k_factor):
    """2 * outside setback - bend allowance: flat length = sum of the outer flange lengths
    (to the virtual sharps) - the bend deductions."""
    return 2.0 * outside_setback(angle_deg, inner_radius, thickness) - bend_allowance(
        angle_deg, inner_radius, thickness, k_factor
    )
