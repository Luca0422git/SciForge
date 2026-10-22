# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch constraints that explain themselves: the words. Pure Python, unit tested.

Fusion never leaves a sketch silently broken: a constraint or dimension that would fight the
others is refused, and the user can see which ones it fights. FreeCAD's solver knows them
(SketchObject.ConflictingConstraints / RedundantConstraints, numbered from 1); the FreeCAD
side (sketch_explain.py) finds them, this module says them the way a Fusion user reads a
sketch: "conflicts with the Horizontal on Line 2 and the 30 mm dimension".

Also here, because they are pure logic:
- the order in which inferred constraints are tried when not all of them fit (the strong
  guesses first: a point that snapped onto another before a line that looked parallel);
- the "left to define" note of the Sketch Palette (degrees of freedom);
- the message of a parameter change that is refused because it would break a step.

A constraint is described from a plain dict (built by sketch_explain.constraint_info):
{"index", "type", "first", "first_pos", "second", "second_pos", "third", "value", "name",
"driving"}; curves are named by a {geo index: name} dict (curve_names).
"""

import math

GEO_UNDEF = -2000  # FreeCAD's "no curve" in a constraint
DIMENSIONS = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")
LENGTHS = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter")

# FreeCAD geometry -> what Fusion calls the curve
KIND_NAMES = {
    "Part::GeomLineSegment": "Line",
    "Part::GeomCircle": "Circle",
    "Part::GeomArcOfCircle": "Arc",
    "Part::GeomEllipse": "Ellipse",
    "Part::GeomArcOfEllipse": "Elliptical Arc",
    "Part::GeomBSplineCurve": "Spline",
    "Part::GeomPoint": "Point",
    "Part::GeomArcOfHyperbola": "Conic Curve",
    "Part::GeomArcOfParabola": "Conic Curve",
}

# FreeCAD constraint -> Fusion's name for it (the pick tools' titles, ribbon CONSTRAINTS)
FUSION_NAMES = {
    "Coincident": "Coincident",
    "PointOnObject": "Coincident",
    "Horizontal": "Horizontal",
    "Vertical": "Vertical",
    "Parallel": "Parallel",
    "Perpendicular": "Perpendicular",
    "Tangent": "Tangent",
    "Equal": "Equal",
    "Symmetric": "Symmetry",
    "Block": "Fix",
    "SnellsLaw": "Refraction",
    "Weight": "Weight",
}


# -- names ---------------------------------------------------------------------------------
def curve_names(type_ids):
    """{geo index: "Line 2"} for the sketch's own curves, numbered per kind in drawing order
    (the 2nd line is Line 2), from the list of their FreeCAD TypeIds."""
    names = {}
    counts = {}
    for index, type_id in enumerate(type_ids):
        kind = KIND_NAMES.get(type_id, "Curve")
        counts[kind] = counts.get(kind, 0) + 1
        names[index] = "%s %d" % (kind, counts[kind])
    return names


def curve_name(geo, names):
    """What to call curve `geo` (negative: the sketch's axes and projected curves)."""
    if geo is None or geo == GEO_UNDEF:
        return ""
    if geo >= 0:
        return names.get(geo, "Curve %d" % (geo + 1))
    if geo == -1:
        return "the X axis"
    if geo == -2:
        return "the Y axis"
    return "Projected Curve %d" % (-geo - 2)


def _point_owner(geo, pos, names):
    """The curve a constraint's point belongs to; the origin for the root point."""
    if geo == -1 and pos == 1:
        return "the origin"
    return curve_name(geo, names)


def format_value(c):
    """The dimension's value the way it is shown: "30 mm", "45 deg"."""
    value = c.get("value") or 0.0
    if c.get("type") == "Angle":
        return "%s deg" % _number(math.degrees(abs(value)))
    return "%s mm" % _number(abs(value))


def _number(value):
    text = "%.3f" % value
    text = text.rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _between(parts):
    parts = [p for p in parts if p]
    unique = []
    for p in parts:
        if p not in unique:
            unique.append(p)
    if not unique:
        return ""
    if len(unique) == 1:
        return " on %s" % unique[0]
    return " between %s and %s" % (", ".join(unique[:-1]), unique[-1])


def describe(c, names, kinds=None):
    """One constraint in words: "the Horizontal on Line 2", "the 30 mm dimension", "the
    Concentric between Circle 1 and Arc 1". `kinds`: {geo: TypeId} (tells a line-line
    Tangent, Fusion's Collinear, from a real tangency)."""
    kind = c.get("type", "")
    kinds = kinds or {}
    first, second, third = c.get("first"), c.get("second"), c.get("third", GEO_UNDEF)
    p1, p2 = c.get("first_pos", 0), c.get("second_pos", 0)
    label = (" '%s'" % c["name"]) if c.get("name") else ""
    if kind in DIMENSIONS:
        value = format_value(c)
        if kind == "Radius":
            return "the %s radius%s" % (value, label)
        if kind == "Diameter":
            return "the %s diameter%s" % (value, label)
        if kind == "Angle":
            return "the %s angle%s" % (value, label)
        return "the %s dimension%s" % (value, label)
    if kind == "Coincident" and p1 == 3 and p2 == 3:
        return "the Concentric%s" % _between([curve_name(first, names), curve_name(second, names)])
    if kind == "Tangent" and _is_line(first, kinds) and _is_line(second, kinds) and p1 == 0:
        return "the Collinear%s" % _between([curve_name(first, names), curve_name(second, names)])
    if kind == "Symmetric":
        if third is not None and third != GEO_UNDEF:
            mirror = c.get("third_pos", 0)
            if first == second and mirror != 0:
                return "the Midpoint%s" % _between(
                    [curve_name(first, names), _point_owner(third, mirror, names)]
                )
            return "the Symmetry about %s" % (
                _point_owner(third, mirror, names)
                if mirror
                else (curve_name(third, names) or "a line")
            )
    if kind == "InternalAlignment":
        return "the shape of %s" % (curve_name(second, names) or "a curve")
    word = FUSION_NAMES.get(kind, kind)
    owners = [_point_owner(first, p1, names)]
    if second is not None and second != GEO_UNDEF:
        owners.append(_point_owner(second, p2, names))
    if third is not None and third != GEO_UNDEF:
        owners.append(_point_owner(third, c.get("third_pos", 0), names))
    return "the %s%s" % (word, _between(owners))


def _is_line(geo, kinds):
    return kinds.get(geo) == "Part::GeomLineSegment"


# FreeCAD's constraint tools name their undo step "Add horizontal constraint" and so on: the
# Fusion title of the tool behind each (dimension steps are not here: a dimension that repeats
# the sketch becomes a driven one instead, sketch_mode._make_driven_if_redundant).
STEP_TITLES = {
    "horizontal": "Horizontal",
    "vertical": "Vertical",
    "coincident": "Coincident",
    "point on object": "Coincident",
    "parallel": "Parallel",
    "perpendicular": "Perpendicular",
    "perpendicularity": "Perpendicular",
    "tangent": "Tangent",
    "equality": "Equal",
    "symmetric": "Symmetry",
    "'lock'": "Fix",
    "relative 'lock'": "Fix",
    "block": "Fix",
    "fixed": "Fix",
}


def constraint_step_title(step):
    """The Fusion title of the constraint tool whose undo step is called `step`, or None
    when it is not a constraint tool's step."""
    text = (step or "").strip().lower()
    if not (text.startswith("add ") and text.endswith(" constraint")):
        return None
    return STEP_TITLES.get(text[len("add ") : -len(" constraint")].strip())


# -- which culprits to name first -----------------------------------------------------------
def meaning_rank(c):
    """How much a constraint means to the user, for the order culprits are named in:
    dimensions and Fix first, then directions (Horizontal/Vertical), then relations
    (Parallel, Equal...), and the joins (Coincident) last: almost every conflict runs through
    a few corners, which says little."""
    kind = c.get("type", "")
    if kind in DIMENSIONS or kind == "Block":
        return 0
    if kind in ("Horizontal", "Vertical"):
        return 1
    if kind in ("Coincident", "PointOnObject"):
        return 3
    if kind == "InternalAlignment":
        return 4
    return 2


def order_culprits(items):
    """Culprits (constraint dicts) in the order they are named: by meaning, then by their
    place in the sketch."""
    return sorted(items, key=lambda c: (meaning_rank(c), c.get("index", 0)))


def join_list(texts, limit=3):
    """["a", "b", "c", "d"] -> "a, b, c and 1 more"."""
    texts = [t for t in texts if t]
    if not texts:
        return ""
    if len(texts) > limit:
        rest = len(texts) - limit
        return "%s and %d more" % (", ".join(texts[:limit]), rest)
    if len(texts) == 1:
        return texts[0]
    return "%s and %s" % (", ".join(texts[:-1]), texts[-1])


def culprit_list(items, names, kinds=None, limit=3):
    """The culprits in words, most telling first, at most `limit` named. When the ones left
    over are all joins (Coincident), they are counted as such: "and 4 Coincidents"."""
    ordered = order_culprits(items)
    rest = ordered[limit:]
    if len(rest) > 1 and all(c.get("type") in ("Coincident", "PointOnObject") for c in rest):
        named = [describe(c, names, kinds) for c in ordered[:limit]]
        return "%s and %d Coincidents" % (", ".join(named), len(rest))
    return join_list([describe(c, names, kinds) for c in ordered], limit)


# -- the messages ------------------------------------------------------------------------------
SHOWN = " (highlighted in the sketch)"


def refused_constraint(title, kind, culprits_text, count=1):
    """A constraint tool's refusal. kind "conflict": it fights others; "redundant": the
    sketch already says it (`count` culprits make it so)."""
    if kind == "conflict":
        if culprits_text:
            return "%s: not added, it conflicts with %s%s." % (title, culprits_text, SHOWN)
        return "%s: not added, it does not fit the sketch's other constraints." % title
    if culprits_text:
        return "%s: not added, %s already make%s it so%s." % (
            title,
            culprits_text,
            "" if count > 1 else "s",
            SHOWN,
        )
    return "%s: not added, it is so already." % title


def driven_dimension(culprits_text):
    """A dimension on a size the sketch already sets: it is added as a driven dimension."""
    if culprits_text:
        return (
            "That size is already set by %s%s: added as a driven dimension (it shows the "
            "size, it does not change it)." % (culprits_text, SHOWN)
        )
    return (
        "That size is already set by other dimensions: added as a driven dimension "
        "(it shows the size, it does not change it)."
    )


def value_conflict(culprits_text):
    """A dimension's new value the sketch cannot take."""
    if culprits_text:
        return "That value does not fit: it conflicts with %s%s." % (culprits_text, SHOWN)
    return "That value does not fit the other dimensions and constraints of the sketch."


# -- inferred constraints in priority order ------------------------------------------------------
def inference_rank(kind, first_pos=0, second_pos=0, lines=False, touching=True):
    """The strength of an inferred constraint: lower is tried first when not all of them fit.
    Coincident (and the other snaps of a point onto something), then concentric and tangent,
    then horizontal/vertical, collinear, perpendicular where the lines touch, and parallel
    and equal last (CADCraft's order, docs/sciforge/dev/cadcraft-lessons.md). `lines`: both
    curves are lines (a line-line Tangent is Fusion's Collinear). A dimension among them is a
    length the user typed while drawing: it goes before every guess (an Angle can be a guess:
    the 45 degree snap)."""
    if kind in LENGTHS:
        return -1
    if kind == "Coincident":
        return 1 if (first_pos == 3 and second_pos == 3) else 0
    if kind in ("PointOnObject", "Symmetric"):
        return 0
    if kind == "Tangent":
        return 3 if lines else 1
    if kind in ("Horizontal", "Vertical", "Angle"):
        return 2
    if kind == "Perpendicular":
        return 4 if touching else 5
    if kind in ("Parallel", "Equal"):
        return 5
    return 6


def priority_order(items, rank):
    """`items` sorted by `rank(item)`, keeping their order within a rank (stable)."""
    return [item for _r, _i, item in sorted((rank(x), i, x) for i, x in enumerate(items))]


def add_in_order(items, rank, try_add):
    """Fallback when the inferred constraints did not all fit: try them one by one, strongest
    first; `try_add(item)` adds one and returns True when it fits (it removes it itself
    otherwise). Returns the items kept, in the order they were added."""
    kept = []
    for item in priority_order(items, rank):
        if try_add(item):
            kept.append(item)
    return kept


# -- fully constrained ---------------------------------------------------------------------------
def is_fully_constrained(curves, flagged, dof, conflicting, malformed, redundant):
    """Fusion's padlock: the sketch has curves and nothing can move. `flagged` is FreeCAD's
    FullyConstrained (saved with the file, but not updated by a solve that only found
    redundant constraints, and left True when the sketch goes into conflict); `dof` is the
    solver's last count (0 before the first solve after opening a file)."""
    if curves <= 0 or conflicting or malformed:
        return False
    if dof != 0:
        return False
    return bool(flagged) or bool(redundant)


def freedom_note(dof, locked, conflicting=False):
    """The Sketch Palette's note: "Fully constrained", "2 left to define"."""
    if conflicting:
        return "Conflicting constraints"
    if locked:
        return "Fully constrained"
    if dof is None or dof <= 0:
        return ""
    return "%d left to define" % dof


# -- Change Parameters checked on a trial ----------------------------------------------------------
def parameter_refusal(what, problems):
    """Why a parameter change was not applied. `what`: "width = 5 mm"; `problems`: [(step,
    reason)] of the steps that would break."""
    if not problems:
        return ""
    step, reason = problems[0]
    text = "Not changed: with %s, %s would break: %s." % (what, step, reason.rstrip("."))
    if len(problems) == 2:
        text += " %s would break too." % problems[1][0]
    elif len(problems) > 2:
        text += " %d more steps would break too." % (len(problems) - 1)
    return text


GEO_UNDEF = -2000  # FreeCAD's "no curve" in a constraint's First / Second


def is_offset(kind, first, second):
    """True for a horizontal or vertical distance between two different curves' points (or a
    point and the origin): a signed offset, where 0 only says the two are lined up, as the AI's
    create_sketch writes the place of a shape drawn at the origin ('g0.x' = 0). A curve's own
    width or height (both ends of one curve, or the curve alone) is a size."""
    return kind in ("DistanceX", "DistanceY") and second != GEO_UNDEF and first != second


def bad_size(kind, value, offset=False):
    """True when a dimension's value is no size at all: a length or radius of 0 or less, a
    horizontal or vertical distance of 0 (FreeCAD keeps those signed: the sign is their
    direction). Fusion refuses a dimension of 0 (SciForge's dimension box too). `offset`
    (is_offset): a horizontal / vertical offset between two points, which may be 0."""
    if kind in ("Distance", "Radius", "Diameter"):
        return value <= 1e-7
    if kind in ("DistanceX", "DistanceY"):
        return not offset and abs(value) <= 1e-7
    return False


def bad_size_reason(c, names):
    """Why a sketch breaks when dimension `c` (a dict, see describe) has no size: "its radius
    'r' of Circle 1 would be -2 mm, and a size must be more than 0"."""
    what = {"Radius": "radius", "Diameter": "diameter"}.get(c.get("type"), "dimension")
    label = (" '%s'" % c["name"]) if c.get("name") else ""
    if not label and c.get("index") is not None:
        label = " d%d" % (c["index"] + 1)  # what Change Parameters calls an unnamed one
    owner = curve_name(c.get("first"), names)
    where = (" of %s" % owner) if owner else ""
    return "its %s%s%s would be %s mm, and a size must be more than 0" % (
        what,
        label,
        where,
        _number(c.get("value") or 0.0),
    )
