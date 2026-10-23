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
# Thicknesses: SciForge's own starting values (fusion-sheet-metal.md 3.2, marked G there:
# Fusion's exact library could not be read); K 0.44 and bend radius = Thickness are Fusion's.
LIBRARY = (
    make_rule("Steel (mm)", thickness="1.0"),
    make_rule("Steel (in)", units="in", thickness="0.06"),
    make_rule("Stainless Steel (mm)", thickness="1.0"),
    make_rule("Stainless Steel (in)", units="in", thickness="0.048"),
    make_rule("Aluminum (mm)", thickness="1.5"),
    make_rule("Aluminum (in)", units="in", thickness="0.063"),
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


def unique_name(name, taken):
    """`name`, or "name 2", "name 3"... the first one not in `taken` (Fusion: a rule's name is
    unique within its list)."""
    taken = set(taken)
    if name not in taken:
        return name
    n = 2
    while "%s %d" % (name, n) in taken:
        n += 1
    return "%s %d" % (name, n)


def check_name(name, taken, old=None):
    """'' when `name` can be a rule's name in a list holding `taken` (old: the rule's current
    name, which it may keep), else the reason."""
    name = (name or "").strip()
    if not name:
        return "A rule needs a name."
    if name != old and name in set(taken):
        return "There is already a rule named '%s': names are unique in a list." % name
    return ""


def display_value(rule, key):
    """A rule field as the dialog shows it: the expression text, with the rule's units for a
    plain-number length ("1.0 mm", "Thickness * 2")."""
    text = str(rule.get(key, FIELDS[key][1]))
    if FIELDS[key][0] == "length":
        try:
            float(text)
            return "%s %s" % (text, rule.get("units", "mm"))
        except ValueError:
            return text
    return text


def parse_length(text, units):
    """What a user typed in a rule's length field, as stored: an expression stays as typed;
    a number may carry the rule's units ("1.5 mm"), other units are refused."""
    text = (text or "").strip()
    for unit in UNITS:
        if text.endswith(unit):
            if unit != units:
                raise ValueError("this rule is in %s (units are fixed when a rule is made)" % units)
            text = text[: -len(unit)].strip()
            break
    evaluate_expression(text, 1.0)  # raises ValueError with a reason
    return text


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


# -- flange maths (sm-forming; pure, unit tested) ----------------------------------------------
# Flange options as Fusion names them (fusion-sheet-metal.md 2.2): the thickness side of a base
# or contour flange, the edge flange's Bend Position, Height Datum, width types and extents.
ORIENTATIONS = ("side1", "side2", "centered")
BEND_POSITIONS = ("inside", "outside", "adjacent", "tangent")
HEIGHT_DATUMS = ("inner", "outer", "tangent")
WIDTH_TYPES = ("full", "symmetric", "two_sides", "two_offsets")
HEIGHT_EXTENTS = ("distance", "to_object")
CONTOUR_DIRECTIONS = ("one_side", "symmetric", "two_sides")
# A Tear bend relief removes no material in Fusion (the bend's ends are split from the plate);
# a solid cannot hold a zero-width cut, so SciForge makes it a slit this wide (mm; G).
TEAR_SLIT = 0.05


def thickness_offsets(orientation, thickness):
    """(s0, s1): where the sheet lies across a sketch profile, as signed offsets from the
    sketched line (or plane) along its left side (contour) / normal (base). Side 1 puts the
    thickness on the positive side, Side 2 on the negative side, Centered half on each."""
    if orientation == "side2":
        return (-thickness, 0.0)
    if orientation == "centered":
        return (-thickness / 2.0, thickness / 2.0)
    return (0.0, thickness)


def bend_start_x(position, angle_deg, inner_radius, thickness):
    """Where an edge flange's bend starts, measured from the picked edge along the plate,
    outwards (negative: the plate is cut back that far). Fusion's Bend Position:

    inside   the outer faces' virtual sharp stays on the edge (outer size kept)
    outside  the inner faces' virtual sharp is on the edge
    adjacent the bend starts at the edge (the plate is not cut)
    tangent  the bend's outside is tangent to the edge's side face (angles of 90 and more;
             below 90 it is the same as inside, a SciForge choice)"""
    half = math.radians(angle_deg) / 2.0
    if position == "adjacent":
        return 0.0
    if position in ("inside", "outside") and angle_deg >= 180.0 - 1e-6:
        raise ValueError(
            "at 180 degrees the faces never meet: use Bend Position Adjacent or Tangent"
        )
    if position == "outside":
        return -inner_radius * math.tan(half)
    if position == "tangent" and angle_deg >= 90.0 - 1e-9:
        return -(inner_radius + thickness)
    return -(inner_radius + thickness) * math.tan(half)


def wall_length(height, datum, angle_deg, inner_radius, thickness):
    """The straight wall after the bend for a flange Height measured from a Height Datum
    (along the wall): inner faces' sharp (H - R tan(a/2)), outer faces' sharp
    (H - (R + T) tan(a/2)) or the bend's tangent line (H). Raises ValueError when the
    datum has no sharp (a 180 degree fold) or the height does not reach past the bend."""
    if datum in ("inner", "outer") and angle_deg >= 180.0 - 1e-9:
        raise ValueError(
            "a 180 degree flange has no corner to measure from: use Height Datum Tangent To Bend"
        )
    half = math.radians(angle_deg) / 2.0
    if datum == "inner":
        length = height - inner_radius * math.tan(half)
    elif datum == "outer":
        length = height - (inner_radius + thickness) * math.tan(half)
    else:
        length = height
    if length <= 1e-6:
        raise ValueError(
            "the height must reach past the bend: more than %.3f mm" % (height - length)
        )
    return length


def width_range(width_type, edge_length, width=0.0, distance1=0.0, distance2=0.0):
    """(t0, t1): the part of an edge (0 .. edge_length) a flange covers. Full Edge: all of
    it; Symmetric: `width` centred on the edge's middle; Two Sides: distance1 before the
    middle and distance2 after it; Two Offsets: distance1 in from the start and distance2 in
    from the end. Raises ValueError for an empty range."""
    mid = edge_length / 2.0
    if width_type == "symmetric":
        t0, t1 = mid - width / 2.0, mid + width / 2.0
    elif width_type == "two_sides":
        t0, t1 = mid - distance1, mid + distance2
    elif width_type == "two_offsets":
        t0, t1 = distance1, edge_length - distance2
    else:
        t0, t1 = 0.0, edge_length
    if t1 - t0 <= 1e-6:
        raise ValueError("the flange width must be more than 0")
    return t0, t1


def width_between(t_a, t_b, offset_a=0.0, offset_b=0.0):
    """(t0, t1): Fusion's Two Offsets width between two references that cross the edge at
    t_a and t_b (mm along it), each offset inwards by its own distance. Raises ValueError for
    an empty range."""
    if t_a <= t_b:
        t0, t1 = t_a + offset_a, t_b - offset_b
    else:
        t0, t1 = t_b + offset_b, t_a - offset_a
    if t1 - t0 <= 1e-6:
        raise ValueError("the offsets leave no width between the two references")
    return t0, t1


def path_radius(turns_left, s0, s1, inner_radius):
    """Radius a contour flange's sketched line gets at a sharp corner so that the bend's
    inside radius is the rule's: the sheet lies between left offsets s0..s1 of the line; at
    a left turn the inside of the bend is the left (largest offset), at a right turn the
    right (smallest offset)."""
    if turns_left:
        return inner_radius + s1
    return inner_radius - s0


def relief_ends(t0, t1, edge_length, relief_width, remnant):
    """The bend reliefs an edge flange of range t0..t1 needs on an edge of edge_length:
    [(a, b), ...] ranges along the edge to cut. An end of the flange that stops inside the
    edge gets one, Relief Width wide, on the side away from the flange; a sliver of plate
    narrower than Relief Remnant left beyond it is cut too (the cut then runs 1 mm past the
    edge's end so no skin of material is left)."""
    cuts = []
    tol = 1e-6
    if t0 > tol:
        a = t0 - relief_width
        if a < remnant - tol:
            a = min(a, 0.0) - 1.0
        cuts.append((a, t0))
    if t1 < edge_length - tol:
        b = t1 + relief_width
        if edge_length - b < remnant - tol:
            b = max(b, edge_length) + 1.0
        cuts.append((t1, b))
    return cuts
