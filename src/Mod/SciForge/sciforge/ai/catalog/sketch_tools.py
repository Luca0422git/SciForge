# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI tools for the SKETCH tab: sketches of open curves, adding to and reading an existing
sketch, constraints and dimensions (with Fusion's names: Collinear, Concentric, Midpoint...),
Polygon, Trim, Text. Pure Python (the work is in sciforge/ai/actions/sketch_actions.py and
the design steps of sciforge/ai/ops/sketch_ops.py)."""

from . import kit
from .core_tools import GEOMETRY_ITEM, check_geometry
from .kit import UNITS, array, boolean, enum, integer, number, obj, point2, positive, schema
from .kit import string
from .registry import define, example

_CURVE_ITEM = obj(
    {
        "line": kit.numbers(4, "[x1, y1, x2, y2]"),
        "arc": kit.numbers(5, "[cx, cy, r, a0, a1]: counter-clockwise from a0 to a1 degrees"),
        "circle": kit.numbers(3, "[cx, cy, r]"),
        "point": kit.numbers(2, "[x, y]: a sketch point"),
        "polyline": array(kit.numbers(2), "[[x, y], ...] an open chain of lines", 2),
    },
    description="exactly one of line, arc, circle, point, polyline",
)
CURVE_KINDS = ("line", "arc", "circle", "point", "polyline")


def _check_curves(items, problems, path="curves"):
    for i, item in enumerate(items if isinstance(items, list) else []):
        if isinstance(item, dict) and len([k for k in CURVE_KINDS if k in item]) != 1:
            problems.append(
                "%s[%d] must have exactly one of %s" % (path, i, ", ".join(CURVE_KINDS))
            )
        elif isinstance(item, dict) and "arc" in item:
            arc = item["arc"]
            if kit.is_type(arc[2], "number") and arc[2] <= 0:
                problems.append("%s[%d].arc radius must be above 0" % (path, i))


def _extra_curve_sketch(args, problems):
    _check_curves(args.get("curves"), problems)


define(
    "create_curve_sketch",
    "Create sketch of curves",
    "sketch",
    "SOLID > CREATE > Create Sketch (lines, arcs, points)",
    "Create a sketch of open curves and points: the paths, rails, guide curves and rib / web "
    "curves that sweep, loft, pipe, rib, web, pattern_on_path and split_body use, and points "
    "for holes and lofts. Arcs run counter-clockwise from a0 to a1 (degrees); a polyline "
    "stays open. Closed shapes (areas) are made with create_sketch. "
    + kit.SKETCH_HELP
    + " "
    + UNITS,
    schema(
        {
            "plane": enum(["XY", "XZ", "YZ"]),
            "offset": number("mm along the plane's normal", default=0),
            "curves": array(_CURVE_ITEM, "the curves and points", 1),
        },
        ["plane", "curves"],
    ),
    op="sf_curves",
    extra=_extra_curve_sketch,
    needs=(),
    id_base="Sketch",
    title_fn=lambda a: "AI: Sketch of curves on %s" % a.get("plane", ""),
    examples=[
        example(
            {"plane": "XZ", "curves": [{"line": [0, 0, 0, 40]}, {"arc": [20, 40, 20, 90, 180]}]},
            "a sweep path: a straight line up, then a quarter arc",
        ),
        example(
            {"plane": "XY", "curves": [{"point": [10, 10]}, {"point": [30, 10]}]},
            "two sketch points (hole centres)",
        ),
    ],
)


def _extra_add_to_sketch(args, problems):
    if not args.get("geometry") and not args.get("curves"):
        problems.append("give geometry (closed shapes) and / or curves (open curves, points)")
    check_geometry(args.get("geometry"), problems)
    _check_curves(args.get("curves"), problems)


define(
    "add_to_sketch",
    "Add to sketch",
    "sketch",
    "SKETCH > CREATE (Line, Rectangle, Circle, Arc, Polygon, Slot, Spline, Point)",
    "Draw more in an existing sketch (Fusion: edit the sketch and draw): closed shapes "
    "(geometry, the same items as create_sketch, with their named dimensions) and open curves "
    "or points (curves, the same items as create_curve_sketch). construction: true draws "
    "construction geometry (dashed, it makes no area: guides for constraints and axes). "
    "Coordinates are the sketch's own x / y (see get_sketch). Everything built from the "
    "sketch updates. " + kit.GEOMETRY_HELP + " " + UNITS,
    schema(
        {
            "sketch": kit.step_id("the sketch to draw in"),
            "geometry": array(GEOMETRY_ITEM, "closed shapes", 1),
            "curves": array(_CURVE_ITEM, "open curves and points", 1),
            "construction": boolean("construction geometry", default=False),
        },
        ["sketch"],
    ),
    extra=_extra_add_to_sketch,
    own_id=False,
    title_fn=lambda a: "AI: Draw in %s" % a.get("sketch", "sketch"),
    examples=[
        example(
            {"sketch": "Sketch1", "geometry": [{"circle": [20, 10, 4], "name": "bore"}]},
            "a circle (bore.diameter) added to Sketch1",
        ),
        example(
            {"sketch": "Sketch1", "curves": [{"line": [0, -5, 0, 25]}], "construction": True},
            "a construction line (for example a revolve axis)",
        ),
    ],
)

define(
    "get_sketch",
    "Get sketch",
    "sketch",
    "BROWSER > Sketches (and the Sketch Palette)",
    "Read a sketch: its plane and placement, every curve by index (type, points, radius, "
    "construction or not), every constraint by index (type, name, the curves it ties, its "
    "value for dimensions, driving or not), how many degrees of freedom are left (0: fully "
    "constrained, Fusion's padlock), the constraints that conflict or are redundant, and its "
    "closed areas (with a point inside each, for regions). Use the indexes in "
    "sketch_constraint, sketch_dimension, set_sketch_dimension and sketch_delete.",
    schema({"sketch": kit.step_id("the sketch to read")}, ["sketch"]),
    changes=False,
    examples=[example({"sketch": "Sketch1"}, "curves, constraints and areas of Sketch1")],
)

CONSTRAINTS = (
    "coincident",
    "horizontal",
    "vertical",
    "parallel",
    "perpendicular",
    "tangent",
    "equal",
    "symmetric",
    "concentric",
    "collinear",
    "midpoint",
    "fix",
    "point_on",
    "smooth",
)
_POINT_REF = obj(
    {
        "curve": integer(
            "the curve's index (get_sketch); -1 the sketch's x axis, -2 its y "
            "axis; the origin is curve -1 point start",
            minimum=-2,
        ),
        "point": enum(
            ["start", "end", "center", "whole"],
            "which point of it (whole: the " "curve itself)",
            default="whole",
        ),
    },
    ["curve"],
    "a curve, or one of its points",
)


def _extra_constraint(args, problems):
    kind = args.get("kind")
    items = args.get("items") or []
    need = {
        "horizontal": (1, 2),
        "vertical": (1, 2),
        "fix": (1, 1),
        "symmetric": (3, 3),
        "midpoint": (2, 2),
    }.get(kind, (2, 2))
    if not need[0] <= len(items) <= need[1]:
        if need[0] == need[1]:
            problems.append("%s takes %d item(s)" % (kind, need[0]))
        else:
            problems.append("%s takes %d or %d items" % (kind, need[0], need[1]))


define(
    "sketch_constraint",
    "Sketch constraint",
    "sketch",
    "SKETCH > CONSTRAINTS",
    "Add a geometric constraint to a sketch, as Fusion's Constraints panel: coincident (two "
    "points, or a point on a curve), horizontal / vertical (a line, or two points), parallel, "
    "perpendicular, tangent, equal, collinear (two lines), concentric (two circles or arcs), "
    "midpoint (a point and a line or arc), symmetric (two points or curves and the line they "
    "mirror about, third), fix (lock a curve or point), point_on (a point on a curve), smooth "
    "(G2 where a spline meets a curve; tangent only when the solver cannot keep curvature). "
    "items are curves by index (get_sketch) with the point that matters. A constraint that "
    "conflicts with the sketch is not added: the answer names the constraints it fights with.",
    schema(
        {
            "sketch": kit.step_id("the sketch"),
            "kind": enum(CONSTRAINTS),
            "items": array(_POINT_REF, "the curves / points it ties, in order", 1, 3),
        },
        ["sketch", "kind", "items"],
    ),
    extra=_extra_constraint,
    own_id=False,
    title_fn=lambda a: "AI: %s constraint" % str(a.get("kind", "")).capitalize(),
    examples=[
        example(
            {"sketch": "Sketch1", "kind": "horizontal", "items": [{"curve": 0}]},
            "make line 0 horizontal",
        ),
        example(
            {
                "sketch": "Sketch1",
                "kind": "coincident",
                "items": [{"curve": 4, "point": "center"}, {"curve": -1, "point": "start"}],
            },
            "put circle 4's centre on the sketch origin",
        ),
    ],
)

DIMENSIONS = ("distance", "distance_x", "distance_y", "radius", "diameter", "angle")


def _extra_dimension(args, problems):
    kind = args.get("kind")
    items = args.get("items") or []
    if kind in ("radius", "diameter") and len(items) != 1:
        problems.append("%s takes one circle or arc" % kind)
    if kind == "angle" and len(items) not in (1, 2):
        problems.append("angle takes one line (to the sketch x axis) or two lines")
    if ("value" in args) == ("expression" in args):
        problems.append("give value (a number) or expression (a formula), one of them")
    name = args.get("name")
    if isinstance(name, str) and not kit.NAME.match(name.replace(".", "_")):
        problems.append("name may only use letters, digits, _ and .")


define(
    "sketch_dimension",
    "Sketch dimension",
    "sketch",
    "SKETCH > CREATE > Sketch Dimension (D)",
    "Add a driving dimension to a sketch, like Fusion's Sketch Dimension: distance (between "
    "two points, a point and a line, or one line's length), distance_x / distance_y "
    "(horizontal / vertical), radius, diameter, angle (between two lines, or of one line to "
    "the x axis). value in mm or degrees, or expression: a formula with parameters "
    '("width / 2"). name names it for set_sketch_dimension and expressions. A dimension '
    "that over-constrains the sketch is refused with the constraints it conflicts with.",
    schema(
        {
            "sketch": kit.step_id("the sketch"),
            "kind": enum(DIMENSIONS),
            "items": array(_POINT_REF, "the curves / points measured", 1, 2),
            "value": number("mm (lengths) or degrees (angles)"),
            "expression": string("a formula instead of value, e.g. width / 2"),
            "name": string("a name, e.g. slot.width"),
        },
        ["sketch", "kind", "items"],
    ),
    extra=_extra_dimension,
    own_id=False,
    title_fn=lambda a: "AI: %s dimension" % str(a.get("kind", "")).replace("_", " ").capitalize(),
    examples=[
        example(
            {
                "sketch": "Sketch1",
                "kind": "diameter",
                "items": [{"curve": 4}],
                "value": 8,
                "name": "bore.diameter",
            },
            "circle 4 is 8 mm across",
        ),
        example(
            {
                "sketch": "Sketch1",
                "kind": "distance_x",
                "items": [{"curve": -1, "point": "start"}, {"curve": 4, "point": "center"}],
                "expression": "width / 2",
            },
            "the circle's centre at half the width",
        ),
    ],
)


def _extra_set_dimension(args, problems):
    if ("constraint" in args) == ("index" in args):
        problems.append("give constraint (its name) or index, one of them")
    if ("value" in args) == ("expression" in args):
        problems.append("give value (a number) or expression (a formula), one of them")


define(
    "set_sketch_dimension",
    "Set sketch dimension",
    "sketch",
    "SKETCH > double-click a dimension (or MODIFY > Change Parameters, Model Parameters)",
    "Change a sketch dimension: by its name (rectangles made by create_sketch with a name "
    "have <name>.width, <name>.height, <name>.x, <name>.y; circles <name>.diameter, "
    "<name>.x, <name>.y) or by its index (get_sketch). value in mm / degrees, or expression "
    "(a formula with parameters; an empty expression removes the formula). Everything built "
    "from the sketch updates; steps that break are named in the answer.",
    schema(
        {
            "sketch": kit.step_id("the sketch"),
            "constraint": string("the dimension's name, e.g. base.width"),
            "index": integer("the constraint's index (get_sketch)", minimum=0),
            "value": number("mm or degrees"),
            "expression": string("a formula, e.g. width * 2"),
        },
        ["sketch"],
    ),
    ops=["edit"],
    extra=_extra_set_dimension,
    own_id=False,
    title_fn=lambda a: "AI: %s = %s"
    % (a.get("constraint", "dimension"), a.get("value", a.get("expression", ""))),
    examples=[
        example(
            {"sketch": "Sketch1", "constraint": "base.width", "value": 60},
            "make the rectangle 60 mm wide",
        ),
    ],
)


def _extra_sketch_delete(args, problems):
    if not args.get("curves") and not args.get("constraints"):
        problems.append("give curves and / or constraints (indexes from get_sketch)")


define(
    "sketch_delete",
    "Delete in sketch",
    "sketch",
    "SKETCH > select > Delete",
    "Delete curves and / or constraints of a sketch by their indexes (get_sketch). Deleting "
    "a curve deletes the constraints on it too. Indexes after the deleted ones move down: "
    "call get_sketch again before the next edit.",
    schema(
        {
            "sketch": kit.step_id("the sketch"),
            "curves": array(integer(minimum=0), "curve indexes", 1),
            "constraints": array(integer(minimum=0), "constraint indexes", 1),
        },
        ["sketch"],
    ),
    extra=_extra_sketch_delete,
    own_id=False,
    destructive=True,
    examples=[example({"sketch": "Sketch1", "curves": [3]}, "delete curve 3")],
)

define(
    "sketch_polygon",
    "Polygon",
    "sketch",
    "SKETCH > CREATE > Polygon > Circumscribed / Inscribed Polygon",
    "Add a regular polygon to a sketch, Fusion's way: center and point, where point is the "
    "middle of an edge (circumscribed, default) or a corner (inscribed). diameter dimensions "
    "it (across flats when circumscribed, across corners when inscribed), named "
    "<name>.diameter. " + UNITS,
    schema(
        {
            "sketch": kit.step_id("the sketch"),
            "center": point2(),
            "point": point2("the middle of an edge (circumscribed) or a corner (inscribed)"),
            "sides": integer("number of sides", minimum=3),
            "circumscribed": boolean("point is the middle of an edge", default=True),
            "diameter": positive("across flats / corners, mm"),
            "name": string("names its dimension <name>.diameter"),
        },
        ["sketch", "center", "point", "sides"],
    ),
    op="sketch_polygon",
    own_id=False,
    title_fn=lambda a: "AI: Polygon",
    examples=[
        example(
            {
                "sketch": "Sketch1",
                "center": [0, 0],
                "point": [5, 0],
                "sides": 6,
                "diameter": 10,
                "name": "nut",
            },
            "a hexagon 10 mm across flats",
        )
    ],
)
define(
    "sketch_trim",
    "Trim",
    "sketch",
    "SKETCH > MODIFY > Trim (T)",
    "Trim sketch curves, as clicking Trim at each point in turn: the curve nearest the point "
    "loses the piece between its neighbouring intersections. Points are [x, y] in the sketch's "
    "coordinates, on the piece to remove.",
    schema(
        {
            "sketch": kit.step_id("the sketch"),
            "points": array(point2(), "one Trim click each", 1),
        },
        ["sketch", "points"],
    ),
    op="sketch_trim",
    own_id=False,
    title_fn=lambda a: "AI: Trim",
    examples=[
        example(
            {"sketch": "Sketch1", "points": [[20, 0]]}, "remove the piece of curve through (20, 0)"
        )
    ],
)


def _extra_text(args, problems):
    if not str(args.get("text", "")).strip():
        problems.append("text must not be empty")


define(
    "sketch_text",
    "Text",
    "sketch",
    "SKETCH > CREATE > Text",
    "Write text in a sketch (Fusion's sketch Text): its letters become areas you can "
    "extrude (profile: the text's id) or emboss. corner is the frame's top-left corner in "
    "sketch coordinates, height the letter height (mm); font a font family installed on the "
    "computer (default: SciForge's), bold, italic, angle (degrees), h_align left | center | "
    "right, v_align top | middle | bottom, width / frame_height: the text frame (0: fits the "
    "text), spacing (extra letter spacing).",
    schema(
        {
            "sketch": kit.step_id("the sketch to write in"),
            "text": string("the text"),
            "height": positive("letter height (mm)", default=5),
            "corner": point2("the frame's top-left corner [x, y]"),
            "font": string("a font family"),
            "bold": boolean(default=False),
            "italic": boolean(default=False),
            "angle": number("degrees", default=0),
            "h_align": enum(["left", "center", "right"], default="left"),
            "v_align": enum(["top", "middle", "bottom"], default="top"),
            "width": number("frame width (mm, 0: fits the text)", minimum=0),
            "frame_height": number("frame height (mm, 0: fits the text)", minimum=0),
            "spacing": number("extra letter spacing"),
        },
        ["sketch", "text"],
    ),
    extra=_extra_text,
    id_base="Text",
    title_fn=lambda a: "AI: Text %r" % a.get("text", ""),
    examples=[
        example(
            {"sketch": "Sketch2", "text": "SciForge", "height": 6, "corner": [2, 18]},
            "a 6 mm high text; extrude it with profile = the text's id",
        )
    ],
)
