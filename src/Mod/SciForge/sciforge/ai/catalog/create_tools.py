# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI tools for SOLID > CREATE beyond the first sixteen: Sweep, Loft, Rib, Web, Emboss,
Thread, Box / Cylinder / Sphere / Torus, Coil, Pipe, Gear, the Pattern dialogs (Rectangular,
Circular, On Path, Mirror, components) and INSERT > Hardware. Each one builds the design step
of sciforge/ai/ops that runs the same code as the Fusion-style dialog. Pure Python."""

import copy

from . import kit
from .kit import (
    EXPRESSION_HELP,
    UNITS,
    angle,
    array,
    boolean,
    either,
    enum,
    integer,
    length,
    number,
    point2,
    positive,
    schema,
    step_id,
    step_ids,
    string,
)
from .registry import define, example

_OPERATION_AUTO = enum(
    ["auto", "join", "cut", "intersect", "new_body"],
    "auto (default: what the dialog picks by itself), join, cut, intersect or new_body",
    default="auto",
)
_BODIES = {
    "type": ["string", "array"],
    "items": {"type": "string"},
    "description": 'Objects To Cut: "auto" (every body in the way) or a list of step ids',
}
_EXPRESSIONS = kit.free_object(
    "{field: formula}: a parameter or formula typed in a field (it keeps driving it)"
)
_PLANE_OR_FACE = either(
    '"XY" | "XZ" | "YZ" (an origin plane of the current body) or '
    '{"face": selector} (a flat face of the part, as clicked)'
)
_PROFILE_DOC = (
    "profile: a sketch id (its one area; a sketch with several areas is taken whole), with "
    "regions [[x, y], ...] to click some areas, or face: a flat face of the part."
)


def _check_bodies(args, problems):
    bodies = args.get("bodies")
    if isinstance(bodies, str) and bodies != "auto":
        problems.append('bodies must be "auto" or a list of step ids')


def _check_profile(args, problems, required=True):
    if required and ("profile" in args) == ("face" in args):
        problems.append("give profile (a sketch id) or face (a flat face selector), one of them")
    if "face" in args:
        kit.check_selector(args["face"], "face", "faces", problems)
    if "regions" in args and "profile" not in args:
        problems.append("regions pick areas of the profile sketch: give profile")


# -- Sweep --------------------------------------------------------------------------------------
def _extra_sweep(args, problems):
    _check_profile(args, problems)
    kit.check_curves(args.get("path"), "path", problems)
    kind = args.get(
        "type", "rail" if "rail" in args else "surface" if "surface" in args else "single"
    )
    if kind == "rail" and "rail" not in args:
        problems.append("type rail needs rail (a guide rail)")
    if kind == "surface" and "surface" not in args:
        problems.append("type surface needs surface (the guide faces)")
    if "rail" in args:
        kit.check_curves(args["rail"], "rail", problems)
    if "surface" in args:
        kit.check_selector(args["surface"], "surface", "faces", problems)
    _check_bodies(args, problems)


def _steps_sweep(a, sid):
    step = {"op": "sf_sweep", "id": sid}
    for key, value in a.items():
        step[key] = copy.deepcopy(value)
    if "surface" in a:
        step["surface"] = {"faces": copy.deepcopy(a["surface"])}
    if "type" not in a:
        if "rail" in a:
            step["type"] = "rail"
        elif "surface" in a:
            step["type"] = "surface"
    return [step]


define(
    "sweep",
    "Sweep",
    "create",
    "SOLID > CREATE > Sweep",
    "Sweep a profile along a path (Fusion's Sweep). " + _PROFILE_DOC + " path (and rail): "
    "curves. " + kit.CURVES_HELP + " type single (path only), rail (path + guide rail: the "
    "profile follows the rail, scaling scale | stretch | none) or surface (path + guide "
    "surface faces). distance / distance2: how far along the path, 0..1 (1 = all the way); "
    "taper and twist (degrees, single path); orientation perpendicular | parallel; operation; "
    "bodies (Objects To Cut). " + EXPRESSION_HELP + " " + UNITS,
    schema(
        {
            "profile": step_id("the profile sketch"),
            "regions": array(point2(), "areas of the profile sketch, a point inside each", 1),
            "face": kit.selector("instead of profile: a flat face as the profile"),
            "path": either("the path"),
            "rail": either("type rail: the guide rail"),
            "surface": kit.selector("type surface: the guide surface faces"),
            "type": enum(["single", "rail", "surface"], default="single"),
            "distance": number("how far along the path, 0..1", default=1, minimum=0, maximum=1),
            "distance2": number("side two, 0..1", minimum=0, maximum=1),
            "taper": angle("taper angle", default=0),
            "twist": angle("twist angle", default=0),
            "orientation": enum(["perpendicular", "parallel"], default="perpendicular"),
            "scaling": enum(["scale", "stretch", "none"], "type rail", default="scale"),
            "operation": _OPERATION_AUTO,
            "bodies": _BODIES,
            "expressions": _EXPRESSIONS,
        },
        ["path"],
    ),
    ops=["sf_sweep"],
    steps=_steps_sweep,
    extra=_extra_sweep,
    id_base="Sweep",
    title_fn=lambda a: "AI: Sweep",
    examples=[
        example(
            {"profile": "Sketch1", "path": "Sketch2"},
            "sweep Sketch1's circle along every curve of Sketch2",
        ),
        example(
            {"profile": "Sketch1", "path": {"sketch": "Sketch2", "at": [0, 20]}, "twist": 90},
            "along the chain through (0, 20), a quarter turn of twist",
        ),
    ],
)


# -- Loft ---------------------------------------------------------------------------------------
def _extra_loft(args, problems):
    profiles = args.get("profiles") or []
    if len(profiles) < 2:
        problems.append("a loft needs at least 2 profiles")
    for i, spec in enumerate(profiles):
        where = "profiles[%d]" % i
        if not isinstance(spec, dict):
            problems.append("%s must be an object" % where)
            continue
        kinds = [k for k in ("profile", "face", "point") if k in spec]
        if len(kinds) != 1 or set(spec) - {"profile", "region", "face", "point"}:
            problems.append(
                '%s must be {"profile": id (, "region": [x, y])}, {"face": selector} '
                'or {"point": {"sketch": id, "at": [x, y]}}' % where
            )
            continue
        if "face" in spec:
            kit.check_selector(spec["face"], where + ".face", "faces", problems)
        if "point" in spec and 0 < i < len(profiles) - 1:
            problems.append("%s: a point can only be the first or last profile" % where)
    for i, rail in enumerate(args.get("rails") or []):
        kit.check_curves(rail, "rails[%d]" % i, problems)
    if "centerline" in args:
        kit.check_curves(args["centerline"], "centerline", problems)
        if args.get("rails"):
            problems.append("give rails or centerline, not both")
    _check_bodies(args, problems)


_END = enum(["free", "direction", "tangent", "curvature", "point_tangent"], default="free")
define(
    "loft",
    "Loft",
    "create",
    "SOLID > CREATE > Loft",
    'Loft through profiles in order (Fusion\'s Loft). Each profile is {"profile": sketch id} '
    '(its one area, else the whole sketch), {"profile": id, "region": [x, y]} (one area), '
    '{"face": selector} or {"point": {"sketch": id, "at": [x, y]}} (a sketch point, first or '
    "last only). rails: guide rails (each a curves spec), or centerline: one centre line. "
    "closed: the loft comes back to the first profile. start_* / end_*: Fusion's end "
    "conditions of the first / last profile (free, direction, tangent, curvature, "
    "point_tangent) with weight 0.1..2 and angle. merge: merge tangent edges. operation, "
    "bodies. " + kit.CURVES_HELP,
    schema(
        {
            "profiles": array(kit.free_object("one profile (see above)"), "in loft order", 2),
            "rails": array(either("a rail (curves)"), "guide rails", 1),
            "centerline": either("a centre line (curves)"),
            "guide": enum(["rails", "centerline"], default="rails"),
            "closed": boolean(default=False),
            "merge": boolean("merge tangent edges", default=False),
            "start_condition": _END,
            "start_weight": number(
                "how strongly the start condition pulls (0.1..2)", default=1, minimum=0.1, maximum=2
            ),
            "start_angle": angle(default=0),
            "end_condition": _END,
            "end_weight": number(
                "how strongly the end condition pulls (0.1..2)", default=1, minimum=0.1, maximum=2
            ),
            "end_angle": angle(default=0),
            "operation": _OPERATION_AUTO,
            "bodies": _BODIES,
        },
        ["profiles"],
    ),
    op="sf_loft",
    extra=_extra_loft,
    id_base="Loft",
    title_fn=lambda a: "AI: Loft",
    examples=[
        example(
            {"profiles": [{"profile": "Sketch1"}, {"profile": "Sketch2"}]},
            "a loft from a square to a circle on an offset plane",
        )
    ],
)


# -- Rib / Web ----------------------------------------------------------------------------------
def _rib_tool(kind):
    def steps(a, sid):
        step = {"op": "sf_rib", "id": sid, "kind": kind}
        step.update(copy.deepcopy(a))
        return [step]

    def extra(a, problems):
        kit.check_curves(a.get("curves"), "curves", problems)
        if a.get("depth_type") == "depth" and "depth" not in a:
            problems.append("depth_type depth needs depth")

    what = (
        "one open sketch curve; the rib grows in the sketch plane to the part"
        if kind == "rib"
        else "open sketch curves; the web grows out of the sketch plane"
    )
    define(
        kind,
        kind.capitalize(),
        "create",
        "SOLID > CREATE > %s" % kind.capitalize(),
        "Fusion's %s: a thin wall from %s, always joined to the part. curves: %s "
        "thickness (mm), thickness_side symmetric | one_side (flip_side: the other side), "
        "depth_type to_next (up to the part) | depth (with depth), flip (the other "
        "direction), extend (the ends reach the part). %s"
        % (kind.capitalize(), what, kit.CURVES_HELP, UNITS),
        schema(
            {
                "curves": either("the curves"),
                "thickness": positive("wall thickness (mm)", default=2),
                "thickness_side": enum(["symmetric", "one_side"], default="symmetric"),
                "flip_side": boolean(default=False),
                "depth_type": enum(["to_next", "depth"], default="to_next"),
                "depth": positive("depth (mm), depth_type depth"),
                "flip": boolean(default=False),
                "extend": boolean(default=True),
            },
            ["curves"],
        ),
        ops=["sf_rib"],
        steps=steps,
        extra=extra,
        needs=("solid",),
        id_base=kind.capitalize(),
        title_fn=lambda a, k=kind: "AI: %s" % k.capitalize(),
        examples=[
            example({"curves": "Sketch3", "thickness": 2}, "a 2 mm %s from Sketch3's curve" % kind)
        ],
    )


_rib_tool("rib")
_rib_tool("web")


# -- Emboss -------------------------------------------------------------------------------------
define(
    "emboss",
    "Emboss",
    "create",
    "SOLID > CREATE > Emboss",
    "Emboss (raise) or deboss (sink) a sketch's areas onto faces of the part, wrapping them "
    "onto curved faces (Fusion's Emboss). Every closed area of the sketch is a profile (a "
    "sketch_text works too). faces: the faces to wrap onto; depth (mm; negative swaps the "
    "effect); effect emboss | deboss; h / v (mm): horizontal / vertical offset along the "
    "face; angle (degrees): rotation; tangent_chain (default true).",
    schema(
        {
            "sketch": step_id("the sketch (or text) with the areas"),
            "faces": kit.selector("the faces to wrap onto"),
            "depth": number("mm", default=1),
            "effect": enum(["emboss", "deboss"], default="emboss"),
            "h": length("horizontal offset", default=0),
            "v": length("vertical offset", default=0),
            "angle": angle("rotation", default=0),
            "tangent_chain": boolean(default=True),
        },
        ["sketch", "faces"],
    ),
    op="emboss",
    selectors={"faces": "faces"},
    needs=("solid",),
    id_base="Emboss",
    title_fn=lambda a: "AI: %s" % str(a.get("effect", "emboss")).capitalize(),
    examples=[
        example(
            {"sketch": "Sketch3", "faces": {"type": "cylinder", "count": 1}, "depth": 0.5},
            "raise Sketch3's text 0.5 mm on a round face",
        )
    ],
)

# -- Thread -------------------------------------------------------------------------------------
define(
    "thread",
    "Thread",
    "create",
    "SOLID > CREATE > Thread",
    "Put a thread on round faces (Fusion's Thread). faces: cylinder faces (a shaft or a "
    "hole). The size comes from the face unless designation (e.g. M6x1, 1/4-20 UNC) or size "
    "is given; standard iso | ansi; thread_class; direction right | left. modeled: true cuts "
    "the real ISO 68-1 groove (false: cosmetic, nothing changes in the solid). full_length, "
    "or length (mm) with offset (mm from the start) and from_end.",
    schema(
        {
            "faces": kit.selector("the cylinder faces"),
            "standard": enum(["iso", "ansi"], default="iso"),
            "size": string("nominal size"),
            "designation": string("e.g. M6x1"),
            "thread_class": string("e.g. 6g"),
            "direction": enum(["right", "left"], default="right"),
            "modeled": boolean("cut the real thread", default=False),
            "full_length": boolean(default=True),
            "length": positive("mm (full_length false)"),
            "offset": number("mm from the start", minimum=0),
            "from_end": boolean("measure from the other end", default=False),
        },
        ["faces"],
    ),
    op="thread",
    selectors={"faces": "faces"},
    needs=("solid",),
    id_base="Thread",
    title_fn=lambda a: ("AI: Thread %s" % a.get("designation", "")).rstrip(),
    examples=[
        example(
            {
                "faces": {"type": "cylinder", "radius": 3, "count": 1},
                "modeled": True,
                "full_length": False,
                "length": 8,
            },
            "an 8 mm modeled thread on the 6 mm shaft",
        )
    ],
)


# -- Primitives ---------------------------------------------------------------------------------
def _extra_primitive(args, problems):
    kind = args.get("kind")
    allowed = {
        "box": {"x", "y", "sx", "sy", "length", "width", "height"},
        "cylinder": {"x", "y", "diameter", "height"},
        "sphere": {"x", "y", "diameter"},
        "torus": {"x", "y", "inner_diameter", "torus_diameter", "position"},
    }.get(kind, set())
    sizes = {
        "x",
        "y",
        "sx",
        "sy",
        "length",
        "width",
        "height",
        "diameter",
        "inner_diameter",
        "torus_diameter",
        "position",
    }
    for key in sorted(sizes & set(args)):
        if key not in allowed:
            problems.append("%s is not a field of a %s" % (key, kind))
    if "plane" in args:
        kit.check_plane_or_face(args["plane"], "plane", problems)
    for key in ("sx", "sy"):
        if key in args and args[key] not in (1, -1):
            problems.append("%s must be 1 or -1 (the side the box goes to)" % key)


define(
    "primitive",
    "Box / Cylinder / Sphere / Torus",
    "create",
    "SOLID > CREATE > Box, Cylinder, Sphere, Torus",
    "Make a box, cylinder, sphere or torus (Fusion's primitives) on an origin plane or a flat "
    "face, in that plane's own x / y frame. box: x, y (first corner), length, width, height "
    "(signed: a negative height goes below the plane), sx / sy (+1 / -1: the side the box "
    "goes to); cylinder: x, y (centre), diameter, height; sphere: x, y, diameter; torus: x, "
    "y, inner_diameter, torus_diameter, position inside | center | outside. operation auto "
    "(what the dialog picks: join when it touches the part, else new_body), join, cut, "
    "intersect, new_body or new_component. " + EXPRESSION_HELP + " " + UNITS,
    schema(
        {
            "kind": enum(["box", "cylinder", "sphere", "torus"]),
            "plane": _PLANE_OR_FACE,
            "x": length("x in the plane", default=0),
            "y": length("y in the plane", default=0),
            "sx": integer("+1 / -1", default=1),
            "sy": integer("+1 / -1", default=1),
            "length": length("box length (x)"),
            "width": length("box width (y)"),
            "height": length("height along the plane's normal"),
            "diameter": positive("mm"),
            "inner_diameter": positive("torus: inner diameter (mm)"),
            "torus_diameter": positive("torus: the tube's diameter (mm)"),
            "position": enum(["inside", "center", "outside"], "torus", default="inside"),
            "operation": enum(
                ["auto", "join", "cut", "intersect", "new_body", "new_component"], default="auto"
            ),
            "expressions": _EXPRESSIONS,
        },
        ["kind"],
    ),
    op="sf_primitive",
    extra=_extra_primitive,
    needs=(),
    id_base="Primitive",
    title_fn=lambda a: "AI: %s" % str(a.get("kind", "primitive")).capitalize(),
    examples=[
        example(
            {"kind": "box", "plane": "XY", "length": 40, "width": 20, "height": 10},
            "a 40 x 20 x 10 box at the origin",
        ),
        example(
            {
                "kind": "cylinder",
                "plane": {"face": {"normal": [0, 0, 1], "count": 1}},
                "x": 20,
                "y": 10,
                "diameter": 8,
                "height": 5,
            },
            "a boss on the top face",
        ),
    ],
)


def _extra_coil(args, problems):
    if "plane" in args:
        kit.check_plane_or_face(args["plane"], "plane", problems)


define(
    "coil",
    "Coil",
    "create",
    "SOLID > CREATE > Coil",
    "Make a coil (spring, helix) or a flat spiral (Fusion's Coil): plane and x / y of its "
    "centre, diameter, type rev_height (revolutions + height), rev_pitch, height_pitch or "
    "spiral; revolutions, height, pitch (mm per turn), angle (taper, degrees), clockwise; "
    "section circular | square | tri_ext | tri_int, section_position inside | center | "
    "outside, section_size (mm). operation auto, join, cut, intersect, new_body. " + UNITS,
    schema(
        {
            "plane": _PLANE_OR_FACE,
            "x": length(default=0),
            "y": length(default=0),
            "diameter": positive("mm", default=20),
            "type": enum(
                ["rev_height", "rev_pitch", "height_pitch", "spiral"], default="rev_height"
            ),
            "revolutions": positive(default=5),
            "height": length(default=20),
            "pitch": positive("mm per turn", default=4),
            "angle": angle("taper", default=0),
            "clockwise": boolean(default=True),
            "section": enum(["circular", "square", "tri_ext", "tri_int"], default="circular"),
            "section_position": enum(["inside", "center", "outside"], default="inside"),
            "section_size": positive("mm", default=2),
            "operation": _OPERATION_AUTO,
            "expressions": _EXPRESSIONS,
        },
    ),
    op="sf_coil",
    extra=_extra_coil,
    needs=(),
    id_base="Coil",
    title_fn=lambda a: "AI: Coil",
    examples=[
        example(
            {"plane": "XY", "diameter": 20, "revolutions": 6, "height": 30, "section_size": 2},
            "a 6-turn spring, 30 mm tall",
        )
    ],
)


def _extra_pipe(args, problems):
    path = args.get("path")
    if isinstance(path, dict):
        if "edges" in path:
            if set(path) != {"edges"}:
                problems.append('path {"edges": selector} takes nothing else')
            kit.check_selector(path["edges"], "path.edges", "edges", problems)
        elif "sketch" not in path or set(path) - {"sketch", "edge"}:
            problems.append('path must be {"sketch": id, "edge": n} or {"edges": selector}')
    if args.get("hollow") and "thickness" not in args:
        problems.append("a hollow pipe needs thickness")


define(
    "pipe",
    "Pipe",
    "create",
    "SOLID > CREATE > Pipe",
    'Make a pipe along a path (Fusion\'s Pipe): path {"sketch": id, "edge": n} (the '
    "sketch's n-th curve, 1 = first, with the curves chained to it when chain is true) or "
    '{"edges": edge selector} (edges of the part). section circular | square | triangular, '
    "section_size (mm), hollow with thickness (mm), distance 0..1 (how far along the path). "
    "operation auto, join, cut, intersect, new_body. " + UNITS,
    schema(
        {
            "path": kit.free_object('{"sketch": id, "edge": n} or {"edges": selector}'),
            "chain": boolean("follow the curves joined to it", default=True),
            "section": enum(["circular", "square", "triangular"], default="circular"),
            "section_size": positive("mm", default=2),
            "hollow": boolean(default=False),
            "thickness": positive("wall (mm), hollow", default=0.5),
            "distance": number("0..1 of the path", default=1, minimum=0, maximum=1),
            "operation": _OPERATION_AUTO,
            "expressions": _EXPRESSIONS,
        },
        ["path"],
    ),
    op="sf_pipe",
    extra=_extra_pipe,
    id_base="Pipe",
    title_fn=lambda a: "AI: Pipe",
    examples=[
        example(
            {"path": {"sketch": "Sketch2", "edge": 1}, "section_size": 4},
            "a 4 mm pipe along Sketch2's path",
        )
    ],
)


def _extra_gear(args, problems):
    if "plane" in args:
        kit.check_plane_or_face(args["plane"], "plane", problems)


define(
    "gear",
    "Gear",
    "create",
    "SOLID > CREATE > Gear",
    "Make an involute gear (SciForge's Gear tool): type spur | internal (a ring with teeth "
    "inside: rim) | rack (rack_size teeth or length with rack_length, rack_height); standard "
    "metric (module, mm) | english (diametral_pitch, teeth per inch); teeth, pressure_angle "
    "(14.5, 20 or 25 degrees), backlash, fillet (root fillet, mm), thickness, symmetric "
    "(both sides of the plane), hole (bore diameter, 0 none), plane, x / y. operation join | "
    "cut | new_body (default) | new_component. " + EXPRESSION_HELP + " " + UNITS,
    schema(
        {
            "plane": _PLANE_OR_FACE,
            "x": length(default=0),
            "y": length(default=0),
            "type": enum(["spur", "internal", "rack"], default="spur"),
            "standard": enum(["metric", "english"], default="metric"),
            "module": positive("mm", default=2),
            "diametral_pitch": positive("teeth per inch", default=12),
            "teeth": integer(default=24, minimum=1, maximum=400),
            "pressure_angle": number("degrees: 14.5, 20 or 25", default=20),
            "backlash": number("mm", default=0, minimum=0),
            "fillet": number("root fillet (mm)", default=0.5, minimum=0),
            "thickness": positive("mm", default=10),
            "symmetric": boolean(default=False),
            "hole": number("bore diameter (mm, 0: none)", default=10, minimum=0),
            "rim": positive("internal gear: rim (mm)", default=5),
            "rack_size": enum(["teeth", "length"], default="teeth"),
            "rack_length": positive("mm", default=100),
            "rack_height": positive("mm", default=5),
            "operation": enum(["join", "cut", "new_body", "new_component"], default="new_body"),
            "expressions": _EXPRESSIONS,
        },
    ),
    op="sf_gear",
    extra=_extra_gear,
    needs=(),
    id_base="Gear",
    title_fn=lambda a: "AI: Gear",
    examples=[
        example(
            {"module": 1.5, "teeth": 30, "thickness": 8, "hole": 8},
            "a 30-tooth spur gear, module 1.5",
        )
    ],
)


# -- Patterns -----------------------------------------------------------------------------------
_WHAT = {
    "features": step_ids("Pattern Type Features: the steps to repeat"),
    "faces": kit.selector("Pattern Type Faces: faces of the part to repeat"),
    "body": boolean("Pattern Type Bodies: the whole current body (the copies are new bodies)"),
    "expressions": _EXPRESSIONS,
    "suppressed": array(
        integer(minimum=1), "copies left out, by their number among the " "copies (Suppression)"
    ),
    "compute": enum(["optimized", "identical", "adjust"], "Compute Option"),
}


def _check_what(args, problems):
    found = [k for k in ("features", "faces", "body") if k in args]
    if len(found) != 1:
        problems.append("give exactly one of features, faces, body (what is patterned)")
    if "faces" in args:
        kit.check_selector(args["faces"], "faces", "faces", problems)
    if "body" in args and args["body"] is not True:
        problems.append("body must be true")


def _extra_rect(args, problems):
    _check_what(args, problems)
    kit.check_axis_or_pick(args.get("direction"), "direction", problems)
    if "direction2" in args:
        kit.check_axis_or_pick(args["direction2"], "direction2", problems)


define(
    "rectangular_pattern",
    "Rectangular pattern",
    "create",
    "SOLID > CREATE > Pattern > Rectangular Pattern",
    "Fusion's Rectangular Pattern dialog: repeat features (step ids), faces or the whole body "
    'in rows. direction X | Y | Z, or {"edge": selector} / {"face": selector} (along a '
    "straight edge, or a flat face's normal); quantity (copies, the original counted); "
    "distance with distribution extent (the whole span) or spacing (between copies); "
    "direction_type one | symmetric; a second direction with direction2, quantity2, "
    "distance2, direction_type2; suppressed: copies left out. " + EXPRESSION_HELP + " " + UNITS,
    schema(
        dict(
            _WHAT,
            direction=either("X, Y, Z or a pick"),
            quantity=integer(minimum=1, default=2),
            distance=length("span or spacing", default=20),
            distribution=enum(["extent", "spacing"], default="extent"),
            direction_type=enum(["one", "symmetric"], default="one"),
            direction2=either("X, Y, Z or a pick"),
            quantity2=integer(minimum=1),
            distance2=length(),
            direction_type2=enum(["one", "symmetric"]),
        ),
        ["direction"],
    ),
    op="rectangular_pattern",
    extra=_extra_rect,
    needs=("solid",),
    id_base="Pattern",
    title_fn=lambda a: "AI: Rectangular pattern",
    examples=[
        example(
            {
                "features": ["Extrude2"],
                "direction": "X",
                "quantity": 4,
                "distance": 60,
                "distribution": "extent",
            },
            "four copies spread over 60 mm along X",
        )
    ],
)


def _extra_circ(args, problems):
    _check_what(args, problems)
    kit.check_axis_or_pick(args.get("axis"), "axis", problems)
    if args.get("type", "full") == "full" and "angle" in args:
        problems.append("a full circular pattern takes no angle (type angle or symmetric)")


define(
    "circular_pattern",
    "Circular pattern",
    "create",
    "SOLID > CREATE > Pattern > Circular Pattern",
    "Fusion's Circular Pattern dialog: repeat features, faces or the whole body around an "
    'axis: X | Y | Z, {"edge": selector} (a straight edge) or {"face": selector} (a round '
    "face's axis). quantity; type full (360 degrees) | angle (the total angle) | symmetric. "
    + EXPRESSION_HELP,
    schema(
        dict(
            _WHAT,
            axis=either("X, Y, Z or a pick"),
            quantity=integer(minimum=1, default=3),
            type=enum(["full", "angle", "symmetric"], default="full"),
            angle=angle("total angle"),
        ),
        ["axis"],
    ),
    op="circular_pattern",
    extra=_extra_circ,
    needs=("solid",),
    id_base="Pattern",
    title_fn=lambda a: "AI: Circular pattern",
    examples=[
        example(
            {
                "features": ["Hole1"],
                "axis": {"face": {"type": "cylinder", "radius": 20, "count": 1}},
                "quantity": 8,
            },
            "eight holes around a round face's axis",
        )
    ],
)


def _extra_path(args, problems):
    _check_what(args, problems)
    path = args.get("path")
    if not isinstance(path, dict) or "sketch" not in path or set(path) - {"sketch", "edge"}:
        problems.append('path must be {"sketch": id} or {"sketch": id, "edge": n}')


define(
    "pattern_on_path",
    "Pattern on path",
    "create",
    "SOLID > CREATE > Pattern > Pattern on Path",
    "Fusion's Pattern on Path: repeat features, faces or the body along a sketch curve. "
    'path {"sketch": id} or {"sketch": id, "edge": n} (n-th curve, 1 = first); quantity; '
    "distance with distribution extent | spacing; direction_type one | symmetric; "
    "orientation identical (copies keep their direction) | path (they turn with the path); "
    "start_point 0..1 (where on the path it starts). " + UNITS,
    schema(
        dict(
            _WHAT,
            path=kit.free_object('{"sketch": id} or {"sketch": id, "edge": n}'),
            quantity=integer(minimum=1, default=2),
            distance=length(default=20),
            distribution=enum(["extent", "spacing"], default="extent"),
            direction_type=enum(["one", "symmetric"], default="one"),
            orientation=enum(["identical", "path"], default="identical"),
            start_point=number("0 (start) .. 1 (end)", minimum=0, maximum=1),
        ),
        ["path"],
    ),
    op="path_pattern",
    extra=_extra_path,
    needs=("solid",),
    id_base="Pattern",
    title_fn=lambda a: "AI: Pattern on path",
    examples=[
        example(
            {
                "features": ["Extrude2"],
                "path": {"sketch": "Sketch3"},
                "quantity": 5,
                "distance": 80,
            },
            "five copies along Sketch3's curve",
        )
    ],
)


def _extra_mirror(args, problems):
    _check_what(args, problems)
    kit.check_plane_or_face(args.get("plane"), "plane", problems)
    if "operation" in args and "body" not in args:
        problems.append("operation (join / new_body) only applies to a body mirror")


define(
    "mirror",
    "Mirror",
    "create",
    "SOLID > CREATE > Mirror",
    "Fusion's Mirror: mirror features, faces or the whole body about a plane: XY | XZ | YZ "
    'or {"face": selector} (a flat face of the part). A body mirror takes operation join '
    "(one body with the original) or new_body.",
    schema(
        dict(
            _WHAT,
            plane=either('XY, XZ, YZ or {"face": selector}'),
            operation=enum(["join", "new_body"], "body mirror only", default="new_body"),
        ),
        ["plane"],
    ),
    ops=["fusion_mirror"],
    op="fusion_mirror",
    extra=_extra_mirror,
    needs=("solid",),
    id_base="Mirror",
    title_fn=lambda a: "AI: Mirror",
    examples=[
        example(
            {"body": True, "plane": "YZ", "operation": "join"},
            "mirror the whole body about YZ into one body",
        )
    ],
)


def _extra_component_pattern(args, problems):
    kind = args.get("kind")
    if kind == "circular" and "axis" not in args:
        problems.append("a circular pattern of components needs axis")
    if kind == "rectangular" and "direction" not in args:
        problems.append("a rectangular pattern of components needs direction")


define(
    "pattern_components",
    "Pattern components",
    "assemble",
    "SOLID > CREATE > Pattern (Pattern Type: Components)",
    "Pattern a whole component (its copies are linked instances, as Fusion's): kind "
    "rectangular (direction, direction2: origin axes X / Y / Z; quantity, quantity2, "
    "distance, distance2, distribution extent | spacing) or circular (axis, quantity, angle, "
    "circular_type full | angle | symmetric). component: the component's id.",
    schema(
        {
            "component": step_id("the component"),
            "kind": enum(["rectangular", "circular"]),
            "axis": enum(kit.AXES),
            "direction": enum(kit.AXES),
            "direction2": enum(kit.AXES),
            "quantity": integer(minimum=1, default=2),
            "quantity2": integer(minimum=1),
            "distance": length(),
            "distance2": length(),
            "angle": angle(default=360),
            "circular_type": enum(["full", "angle", "symmetric"], default="full"),
            "distribution": enum(["extent", "spacing"], default="extent"),
            "direction_type": enum(["one", "symmetric"]),
            "direction_type2": enum(["one", "symmetric"]),
        },
        ["component", "kind"],
    ),
    op="component_pattern",
    extra=_extra_component_pattern,
    id_base="ComponentPattern",
    title_fn=lambda a: "AI: Pattern of components",
    examples=[
        example(
            {"component": "Part", "kind": "circular", "axis": "Z", "quantity": 6},
            "six copies of a component around Z",
        )
    ],
)


# -- Hardware -----------------------------------------------------------------------------------
def _extra_hardware(args, problems):
    if ("face" in args) == ("edge" in args):
        problems.append("give face + at (a click on a flat face) or edge (a hole's round rim)")
    if "face" in args:
        if "at" not in args:
            problems.append("face needs at: the clicked point [x, y, z]")
        kit.check_selector(args["face"], "face", "faces", problems)
    if "edge" in args:
        kit.check_selector(args["edge"], "edge", "edges", problems)


define(
    "insert_hardware",
    "Insert hardware",
    "assemble",
    "INSERT > Hardware (McMaster-Carr / fasteners in Fusion)",
    "Insert a fastener with the hole it needs: click a flat face of the current body at at "
    "([x, y, z], design coordinates) or a round edge (a hole's rim). standard iso4762 "
    "(socket head cap screw), iso7380 (button head), iso10642 (countersunk), iso4032 (hex "
    'nut), iso7089 (washer), insert (heat-set insert), magnet; size ("3" for M3, "6x3" for '
    "a magnet), length (mm), flip, make_hole (default true), fit close | normal | loose, "
    "sink_head (counterbore / countersink for the head), hole_depth all | length, clearance "
    "(a magnet's pocket, mm). The part becomes its own component.",
    schema(
        {
            "face": kit.selector("the flat face clicked"),
            "at": kit.point3("where on it"),
            "edge": kit.selector("instead: a round edge (a hole's rim)", "edges"),
            "standard": enum(
                ["iso4762", "iso7380", "iso10642", "iso4032", "iso7089", "insert", "magnet"],
                default="iso4762",
            ),
            "size": string("e.g. 3 (M3) or 6x3"),
            "length": positive("mm"),
            "flip": boolean(default=False),
            "make_hole": boolean(default=True),
            "fit": enum(["close", "normal", "loose"], default="normal"),
            "sink_head": boolean(
                "counterbore / countersink for the head; default true, false for iso7380 (a "
                "button head sits on the face)"
            ),
            "hole_depth": enum(["all", "length"], default="all"),
            "clearance": number("mm", minimum=0),
        },
    ),
    op="sf_hardware",
    extra=_extra_hardware,
    needs=("solid",),
    id_base="Hardware",
    title_fn=lambda a: "AI: Hardware %s" % a.get("standard", ""),
    examples=[
        example(
            {
                "face": {"normal": [0, 0, 1], "count": 1},
                "at": [10, 10, 10],
                "standard": "iso4762",
                "size": "3",
                "length": 10,
            },
            "an M3 x 10 socket head screw with its hole",
        )
    ],
)
