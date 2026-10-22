# SPDX-License-Identifier: LGPL-2.1-or-later
"""The first sixteen AI tools (brief home-cloud-ai.md section 4.2): get_design, screenshot,
measure, create_sketch, extrude, revolve, fillet, chamfer, hole, pattern, shell,
set_parameter, undo, redo, save, export. Their names and argument shapes never change (AI apps
and installed Claude extensions use them); newer, optional arguments open the rest of the
Fusion dialog behind each one (an Extrude To Object, a Revolve about an edge, a tapped Hole),
and a call with only the old arguments builds exactly the steps it always built (the unit
tests compare them with the golden models). Pure Python.
"""

import copy

from . import kit
from .kit import (
    GEOMETRY_HELP,
    MORE_GEOMETRY_HELP,
    SELECTOR_HELP,
    SKETCH_HELP,
    UNITS,
    array,
    boolean,
    either,
    enum,
    full_selector,
    is_type,
    numbers,
    obj,
    pick,
    positive,
    schema,
    string,
)
from .registry import define, example, mm

_NUMBER = {"type": "number"}
_POINT2 = numbers(2)
_VECTOR3 = numbers(3)
_POSITIVE = {"type": "number", "exclusiveMinimum": 0}
TOP4 = {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}
TOP_FACE = {"normal": [0, 0, 1], "count": 1}


def _numbers(n, description):
    return dict(numbers(n), description=description)


_GEOMETRY_ITEM = {
    "type": "object",
    "properties": {
        "rect": _numbers(4, "[x0, y0, x1, y1]: two opposite corners"),
        "center_rect": _numbers(4, "[cx, cy, width, height]"),
        "circle": _numbers(3, "[cx, cy, radius]"),
        "polyline": {
            "type": "array",
            "items": _POINT2,
            "minItems": 3,
            "description": "[[x, y], ...] the corners of a closed outline",
        },
        "polygon": {
            "type": "object",
            "properties": {
                "center": _POINT2,
                "radius": dict(_POSITIVE, description="centre to corner, mm"),
                "sides": {"type": "integer", "minimum": 3},
                "rotation": dict(_NUMBER, description="degrees", default=0),
            },
            "required": ["center", "radius", "sides"],
            "additionalProperties": False,
        },
        "slot": _numbers(5, "[x1, y1, x2, y2, width]"),
        "line": _numbers(4, "[x0, y0, x1, y1]"),
        "ellipse": _numbers(4, "[cx, cy, major, minor]: major radius along x"),
        "spline_loop": {
            "type": "array",
            "items": _POINT2,
            "minItems": 3,
            "description": "[[x, y], ...] a closed smooth curve through these points",
        },
        "segments": {
            "type": "array",
            "items": {"type": "object"},
            "minItems": 2,
            "description": "a closed chain: {line: [x0, y0, x1, y1]} | {arc: [cx, cy, r, a0, a1]} "
            "| {spline: [[x, y], ...], tangents: [[tx, ty], [tx, ty]]}",
        },
        "name": {"type": "string", "description": "names its dimensions, e.g. <name>.width"},
    },
    "additionalProperties": False,
}
GEOMETRY_ITEM = _GEOMETRY_ITEM

_OPERATION = {
    "type": "string",
    "enum": ["join", "cut", "intersect", "new_body"],
    "default": "join",
    "description": "join adds to the current body, cut removes from it, intersect keeps only "
    "the overlap, new_body makes a separate body",
}
_FEATURES = {
    "type": "array",
    "items": {"type": "string"},
    "minItems": 1,
    "description": "ids of earlier steps (from get_design's timeline)",
}
_AXIS3 = {"type": "string", "enum": ["X", "Y", "Z"]}
_BODIES = {
    "type": ["string", "array"],
    "items": {"type": "string"},
    "description": '"auto": every body the feature passes through is cut / joined (what the '
    "dialog lists by itself); or a list of step ids: exactly those bodies (the dialog's "
    '"Bodies to Cut" row)',
}
_EXTRUDE_REF = {
    "type": "object",
    "description": 'what an extent goes to or a start is measured from: {"plane": "XY"|"XZ"|'
    '"YZ"}, {"face": face selector} (a face of the current body; add "of": step id for a face '
    'of another body) or {"step": id} (the solid of that step\'s body)',
}
GEOMETRY_KINDS = (
    "rect",
    "center_rect",
    "circle",
    "polyline",
    "polygon",
    "slot",
    "line",
    "ellipse",
    "spline_loop",
    "segments",
)


# -- extra rules -------------------------------------------------------------------------------
def check_geometry(geometry, problems, path="geometry"):
    if not isinstance(geometry, list):
        return
    for i, item in enumerate(geometry):
        if not isinstance(item, dict):
            continue
        where = "%s[%d]" % (path, i)
        kinds = [k for k in GEOMETRY_KINDS if k in item]
        if len(kinds) != 1:
            problems.append("%s must have exactly one of %s" % (where, ", ".join(GEOMETRY_KINDS)))
            continue
        kind = kinds[0]
        value = item[kind]
        if "name" in item and isinstance(item["name"], str) and not kit.NAME.match(item["name"]):
            problems.append("%s.name may only use letters, digits and _" % where)
        if kind == "segments":
            for j, seg in enumerate(value if isinstance(value, list) else []):
                if not isinstance(seg, dict) or len({"line", "arc", "spline"} & set(seg)) != 1:
                    problems.append("%s.segments[%d] must be one line, arc or spline" % (where, j))
            continue
        if not isinstance(value, list) or not all(is_type(v, "number") for v in value):
            continue  # polygon / polyline / spline, or already reported by the schema check
        if kind == "circle" and len(value) == 3 and value[2] <= 0:
            problems.append("%s.circle radius must be a number above 0" % where)
        if kind == "center_rect" and len(value) == 4 and (value[2] <= 0 or value[3] <= 0):
            problems.append("%s.center_rect width and height must be above 0" % where)
        if kind == "rect" and len(value) == 4 and (value[0] == value[2] or value[1] == value[3]):
            problems.append("%s.rect has no area: its corners must differ in x and in y" % where)
        if kind == "slot" and len(value) == 5:
            if value[4] <= 0:
                problems.append("%s.slot width must be above 0" % where)
            if value[0] == value[2] and value[1] == value[3]:
                problems.append("%s.slot needs two different centre points" % where)
        if kind == "ellipse" and len(value) == 4:
            if value[3] <= 0 or value[2] < value[3]:
                problems.append(
                    "%s.ellipse: the minor radius must be above 0 and the major radius (along "
                    "x) the larger" % where
                )


def _extra_create_sketch(args, problems):
    given = [k for k in ("plane", "face", "on") if k in args]
    if len(given) != 1:
        problems.append(
            "give either plane (XY, XZ or YZ), face (a selector) or on (a construction plane's "
            "id): one of them, not both"
        )
    if "face" in args:
        kit.check_selector(args["face"], "face", "faces", problems)
    if args.get("auto_project") and "face" not in args:
        problems.append("auto_project projects the edges of the sketch's face: give face")
    check_geometry(args.get("geometry"), problems)


_EXTRUDE_NEW = (
    "face",
    "more_profiles",
    "curves",
    "to",
    "extent2",
    "to2",
    "taper2",
    "measurement",
    "start",
    "start_offset",
    "start_from",
    "thin",
    "bodies",
    "extend",
    "extend2",
    "object_offset",
    "object_offset2",
)


def _check_extrude_ref(spec, path, problems):
    if not isinstance(spec, dict) or len({"plane", "face", "step"} & set(spec)) != 1:
        problems.append('%s must be {"plane": ...}, {"face": selector} or {"step": id}' % path)
        return
    if set(spec) - {"plane", "face", "step", "of"}:
        problems.append("%s takes plane, face (and of) or step" % path)
    if "plane" in spec and spec["plane"] not in kit.PLANES:
        problems.append("%s.plane must be XY, XZ or YZ" % path)
    if "face" in spec:
        kit.check_selector(spec["face"], path + ".face", "faces", problems)
    if "of" in spec and "face" not in spec:
        problems.append("%s.of goes with face" % path)


def _extra_extrude(args, problems):
    sources = [k for k in ("profile", "face") if k in args]
    if "curves" in args:
        if "thin" not in args:
            problems.append("curves (an open profile) need thin: a thin extrude")
        if "face" in args or ("profile" in args and "regions" not in args):
            problems.append("curves go alone, or with profile + regions (areas)")
        kit.check_curves(args["curves"], "curves", problems)
    elif len(sources) != 1:
        problems.append("give profile (a sketch id) or face (a flat face selector), one of them")
    if "face" in args:
        kit.check_selector(args["face"], "face", "faces", problems)
    if "regions" in args and "profile" not in args:
        problems.append("regions pick areas of the profile sketch: give profile")
    if "more_profiles" in args and "profile" not in args:
        problems.append("more_profiles go with profile")
    through = args.get("through_all") is True
    to_object = "to" in args
    if through and to_object:
        problems.append("give through_all or to, not both")
    if (through or to_object) and "distance" in args:
        problems.append("give distance, through_all or to, only one of them")
    if not through and not to_object and "distance" not in args:
        problems.append("distance is missing (or set through_all to true)")
    if to_object:
        _check_extrude_ref(args["to"], "to", problems)
    if args.get("direction") == "two_sides":
        extent2 = args.get("extent2", "distance")
        if extent2 == "distance" and "distance2" not in args:
            problems.append("distance2 is missing: direction two_sides needs it")
        if extent2 == "to_object" and "to2" not in args:
            problems.append("to2 is missing: extent2 to_object needs it")
    else:
        for key in ("distance2", "extent2", "to2", "taper2"):
            if key in args:
                problems.append("%s is only used with direction two_sides" % key)
    if "to2" in args:
        _check_extrude_ref(args["to2"], "to2", problems)
    if args.get("measurement") and args.get("direction") != "symmetric":
        problems.append("measurement is only used with direction symmetric")
    start = args.get("start", "profile")
    if start == "offset" and "start_offset" not in args:
        problems.append("start_offset is missing: start offset needs it")
    if start == "object":
        if "start_from" not in args:
            problems.append("start_from is missing: start object needs it")
        else:
            _check_extrude_ref(args["start_from"], "start_from", problems)
    bodies = args.get("bodies")
    if isinstance(bodies, str) and bodies != "auto":
        problems.append('bodies must be "auto" or a list of step ids')


def _extra_revolve(args, problems):
    if ("profile" in args) == ("face" in args):
        problems.append("give profile (a sketch id) or face (a flat face selector), one of them")
    if "face" in args:
        kit.check_selector(args["face"], "face", "faces", problems)
    if "regions" in args and "profile" not in args:
        problems.append("regions pick areas of the profile sketch: give profile")
    axis = args.get("axis")
    if isinstance(axis, str):
        if axis not in ("X", "Y", "Z", "sketch_h", "sketch_v"):
            problems.append("axis must be X, Y, Z, sketch_h, sketch_v or an axis object")
    elif isinstance(axis, dict):
        if "edge" in axis:
            if set(axis) != {"edge"}:
                problems.append('axis: an edge axis is {"edge": selector} alone')
            kit.check_selector(axis["edge"], "axis.edge", "edges", problems)
        else:
            kinds = [k for k in ("at", "construction", "axis") if k in axis]
            if "sketch" not in axis or len(kinds) != 1:
                problems.append(
                    'axis must be {"sketch": id} with exactly one of at, construction, axis, '
                    'or {"edge": selector}'
                )
            elif kinds == ["axis"] and axis["axis"] not in ("H", "V"):
                problems.append("axis.axis must be H or V (the sketch's own axes)")
    kind = args.get("type")
    if kind == "to" and "to" not in args:
        problems.append("to is missing: type to needs a pick")
    if "to" in args:
        if kind not in (None, "to"):
            problems.append("to is only used with type to")
        kit.check_pick(args["to"], "to", problems)
    if kind == "full" and "angle" in args:
        problems.append("a full revolve takes no angle")
    if "angle2" in args and args.get("direction") != "two_sides":
        problems.append("angle2 is only used with direction two_sides")
    bodies = args.get("bodies")
    if isinstance(bodies, str) and bodies != "auto":
        problems.append('bodies must be "auto" or a list of step ids')


def _extra_blend(args, problems):
    if not ({"edges", "faces", "features"} & set(args)):
        problems.append("pick what to change with edges, faces or features")
    if "edges" in args:
        kit.check_selector(args["edges"], "edges", "edges", problems)
    if "faces" in args:
        kit.check_selector(args["faces"], "faces", "faces", problems)


def _extra_chamfer(args, problems):
    _extra_blend(args, problems)
    if "distance2" in args and "angle" in args:
        problems.append("give distance2 or angle, not both")
    if args.get("flip") and "distance2" not in args:
        problems.append("flip only applies with distance2 (two distances)")


HOLE_FUSION = (
    "hole_type",
    "cbore_diameter",
    "cbore_depth",
    "csink_diameter",
    "csink_angle",
    "drill_point",
    "drill_angle",
    "tap_type",
    "standard",
    "size",
    "designation",
    "fit",
    "fastener",
    "fastener_head",
    "taper_kind",
    "taper_size",
    "thread_class",
    "thread_direction",
    "modeled",
    "full_tap",
    "tap_depth",
    "flip",
    "extent",
    "to",
)


def _extra_hole(args, problems):
    fusion = [k for k in HOLE_FUSION if k in args]
    placed = "face" in args or "at" in args
    if placed:
        if "sketch" in args:
            problems.append("give sketch (hole centres) or face + at (one hole), not both")
        if not ("face" in args and "at" in args):
            problems.append("a single hole needs both face (a selector) and at ([x, y, z])")
        if "face" in args:
            kit.check_selector(args["face"], "face", "faces", problems)
    elif "sketch" not in args:
        problems.append("give sketch (a sketch with the hole centres) or face + at")
    if "references" in args and not placed:
        problems.append("references go with a single hole (face + at)")
    for i, ref in enumerate(args.get("references") or []):
        if isinstance(ref, dict) and "edge" in ref:
            kit.check_selector(ref["edge"], "references[%d].edge" % i, "edges", problems)
    extent = args.get("extent")
    through = args.get("through_all") is True or extent == "all"
    if extent == "to":
        if "to" not in args:
            problems.append("to is missing: extent to needs a plane or face")
    elif "to" in args:
        problems.append("to is only used with extent to")
    if extent is None and not (fusion or placed):
        if through == ("depth" in args):
            problems.append("give either depth or through_all: true")
    elif not through and extent != "to" and "depth" not in args and not args.get("tap_type"):
        if "depth" not in args:
            problems.append("give depth, through_all: true or extent all / to")
    if args.get("through_all") and extent not in (None, "all"):
        problems.append("through_all contradicts extent %s" % extent)
    if "counterbore" in args and "countersink" in args:
        problems.append("give counterbore or countersink, not both")
    if ("counterbore" in args or "countersink" in args) and "hole_type" in args:
        problems.append("give counterbore / countersink or hole_type with its sizes, not both")
    diameter = args.get("diameter")
    for key in ("counterbore", "countersink"):
        head = args.get(key)
        if (
            isinstance(head, dict)
            and is_type(head.get("diameter"), "number")
            and is_type(diameter, "number")
            and head["diameter"] <= diameter
        ):
            problems.append("%s.diameter must be bigger than the hole's diameter" % key)
    if "diameter" not in args and not args.get("tap_type") and not args.get("designation"):
        problems.append("diameter is missing (or give tap_type with a designation / size)")
    if isinstance(args.get("to"), dict):
        spec = args["to"]
        if len({"plane", "face"} & set(spec)) != 1:
            problems.append('to must be {"plane": "XY"|"XZ"|"YZ"} or {"face": selector}')
        elif "face" in spec:
            kit.check_selector(spec["face"], "to.face", "faces", problems)


def _extra_pattern(args, problems):
    kind = args.get("kind")
    rect_keys = ("direction", "spacing", "direction2", "count2", "spacing2")
    if kind == "rectangular":
        for key in ("direction", "spacing"):
            if key not in args:
                problems.append("%s is missing: a rectangular pattern needs it" % key)
        second = [k for k in ("direction2", "count2", "spacing2") if k in args]
        if second and len(second) != 3:
            problems.append("a second direction needs direction2, count2 and spacing2 together")
        for key in ("spacing", "spacing2"):
            if args.get(key) == 0:
                problems.append("%s must not be 0" % key)
        for key in ("axis", "angle"):
            if key in args:
                problems.append("%s is only used by a circular pattern" % key)
    elif kind == "circular":
        if "axis" not in args:
            problems.append("axis is missing: a circular pattern needs it")
        for key in rect_keys:
            if key in args:
                problems.append("%s is only used by a rectangular pattern" % key)


_SHELL_NEW = ("body", "inside", "outside", "shell_type", "bodies")


def _extra_shell(args, problems):
    new = [k for k in _SHELL_NEW if k in args] or args.get("direction") == "both"
    if "bodies" in args:
        if "faces" in args or "body" in args:
            problems.append("bodies (several bodies at once) goes without faces / body")
        for i, item in enumerate(args["bodies"]):
            if not isinstance(item, dict) or "body" not in item or set(item) - {"body", "faces"}:
                problems.append('bodies[%d] must be {"body": step id, "faces": selector}' % i)
            elif "faces" in item:
                kit.check_selector(item["faces"], "bodies[%d].faces" % i, "faces", problems)
    elif ("faces" in args) == bool(args.get("body")):
        problems.append("give faces (the faces to remove) or body: true (hollow, closed)")
    if "faces" in args:
        kit.check_selector(args["faces"], "faces", "faces", problems)
    if not new and "thickness" not in args:
        problems.append("thickness is missing")
    if new and not ({"thickness", "inside", "outside"} & set(args)):
        problems.append("give thickness (or inside / outside thicknesses)")


def _extra_set_parameter(args, problems):
    name = args.get("name")
    if isinstance(name, str) and not kit.NAME.match(name):
        problems.append("name must start with a letter and use only letters, digits and _")
    value = args.get("value")
    if isinstance(value, str) and not value.strip():
        problems.append("value must not be empty")


def _extra_save(args, problems):
    path = args.get("path")
    if isinstance(path, str) and not path.lower().endswith(".fcstd"):
        problems.append("path must end in .FCStd")


EXPORT_EXTENSIONS = {
    "step": (".step", ".stp"),
    "iges": (".igs", ".iges"),
    "stl": (".stl",),
    "stl_ascii": (".stl",),
    "3mf": (".3mf",),
    "obj": (".obj",),
    "brep": (".brep", ".brp"),
    "dxf": (".dxf",),
}


def _extra_export(args, problems):
    path, fmt = args.get("path"), args.get("format")
    if isinstance(path, str) and fmt in EXPORT_EXTENSIONS:
        if not path.strip():
            problems.append("path must not be empty")
        elif not path.lower().endswith(EXPORT_EXTENSIONS[fmt]):
            problems.append(
                "path must end in %s for format %s" % (" or ".join(EXPORT_EXTENSIONS[fmt]), fmt)
            )
    if fmt == "dxf":
        if "sketch" not in args and "face" not in args:
            problems.append("format dxf writes one sketch or one flat face: give sketch or face")
    elif "sketch" in args or "face" in args:
        problems.append("sketch / face are only used with format dxf")
    if "sketch" in args and "face" in args:
        problems.append("give sketch or face, not both")
    if "face" in args:
        kit.check_selector(args["face"], "face", "faces", problems)
    if fmt not in ("stl", "stl_ascii", "3mf", "obj"):
        for key in ("refinement", "unit", "one_file_per_body"):
            if key in args:
                problems.append("%s is only used with mesh formats (stl, 3mf, obj)" % key)


def _extra_measure(args, problems):
    for key in ("a", "b"):
        if key in args:
            kit.check_pick(args[key], key, problems)


# -- design steps ---------------------------------------------------------------------------
def _int(value):
    return int(value) if is_type(value, "integer") else value


def _copy_geometry(geometry):
    result = copy.deepcopy(geometry)
    for item in result:
        if "polygon" in item:
            item["polygon"]["sides"] = _int(item["polygon"]["sides"])
    return result


def _blend_refs(step, args):
    for key in ("edges", "faces"):
        if key in args:
            step[key] = copy.deepcopy(args[key])
    if "features" in args:
        step["features"] = list(args["features"])
    return step


def _steps_create_sketch(a, step_id):
    step = {"op": "sketch", "id": step_id}
    if "plane" in a:
        step["plane"] = a["plane"]
    elif "on" in a:
        step["on"] = a["on"]
    else:
        step["face"] = copy.deepcopy(a["face"])
        if a.get("auto_project"):
            step["auto_project"] = True
    if a.get("offset"):
        step["offset"] = a["offset"]
    step["geometry"] = _copy_geometry(a["geometry"])
    return [step]


def _steps_extrude(a, step_id):
    step = {"op": "extrude", "id": step_id}
    if "profile" in a:
        step["profile"] = a["profile"]
    if "regions" in a:
        step["regions"] = copy.deepcopy(a["regions"])
    if "to" in a:
        step["extent"] = "to_object"
        step["to"] = copy.deepcopy(a["to"])
    elif a.get("through_all"):
        step["extent"] = "through_all"
    else:
        step["distance"] = a["distance"]
    step["operation"] = a.get("operation", "join")
    if a.get("direction", "one_side") != "one_side":
        step["direction"] = a["direction"]
    if "distance2" in a:
        step["distance2"] = a["distance2"]
    if a.get("taper"):
        step["taper"] = a["taper"]
    if a.get("flip"):
        step["flip"] = True
    for key in _EXTRUDE_NEW:
        if key in a and key != "to":
            value = copy.deepcopy(a[key])
            if key == "extent2" and value == "through_all":
                value = "through_all"
            step[key] = value
    return [step]


def _steps_revolve(a, step_id):
    axis = a["axis"]
    if axis in ("sketch_h", "sketch_v"):
        axis = {"sketch": a["profile"], "axis": "H" if axis == "sketch_h" else "V"}
    step = {"op": "sf_revolve", "id": step_id}
    if "profile" in a:
        step["profile"] = a["profile"]
    else:
        step["face"] = copy.deepcopy(a["face"])
    step["axis"] = copy.deepcopy(axis)
    if "regions" in a:
        step["regions"] = copy.deepcopy(a["regions"])
    kind = a.get("type")
    angle = a.get("angle", 360)
    if kind == "to":
        step["type"] = "to"
        step["to"] = copy.deepcopy(a["to"])
    elif kind == "full" or (kind is None and angle >= 360):
        step["type"] = "full"
    else:
        step["type"] = "angle"
        step["angle"] = angle
    for key in ("direction", "angle2", "bodies"):
        if key in a:
            step[key] = copy.deepcopy(a[key])
    step["operation"] = a.get("operation", "auto")
    return [step]


def _steps_fillet(a, step_id):
    return [_blend_refs({"op": "blend_fillet", "id": step_id, "radius": a["radius"]}, a)]


def _steps_chamfer(a, step_id):
    step = {"op": "blend_chamfer", "id": step_id, "distance": a["distance"]}
    if "distance2" in a:
        step["chamfer_type"] = "two"
        step["distance2"] = a["distance2"]
        if a.get("flip"):
            step["flip"] = True
    elif "angle" in a:
        step["chamfer_type"] = "angle"
        step["angle"] = a["angle"]
    else:
        step["chamfer_type"] = "equal"
    return [_blend_refs(step, a)]


def _fusion_hole_options(a):
    options = {}
    for key in HOLE_FUSION:
        if key in a and key not in ("to",):
            options["direction" if key == "thread_direction" else key] = copy.deepcopy(a[key])
    if "to" in a:
        options["to"] = copy.deepcopy(a["to"])
    if "diameter" in a:
        options["diameter"] = a["diameter"]
    if a.get("through_all"):
        options["extent"] = "all"
    elif "depth" in a:
        options["depth"] = a["depth"]
        options.setdefault("extent", "distance")
    if "counterbore" in a:
        options["hole_type"] = "counterbore"
        options["cbore_diameter"] = a["counterbore"]["diameter"]
        options["cbore_depth"] = a["counterbore"]["depth"]
    elif "countersink" in a:
        options["hole_type"] = "countersink"
        options["csink_diameter"] = a["countersink"]["diameter"]
        options["csink_angle"] = a["countersink"].get("angle", 90)
    return options


def _steps_hole(a, step_id):
    if "face" in a:  # Fusion's Single Hole: a click on a face
        step = {"op": "hole_at", "id": step_id, "face": copy.deepcopy(a["face"])}
        step["at"] = list(a["at"])
        if "references" in a:
            step["references"] = copy.deepcopy(a["references"])
        step.update(_fusion_hole_options(a))
        return [step]
    if any(k in a for k in HOLE_FUSION):  # From Sketch with the dialog's options
        step = {"op": "hole_points", "id": step_id, "sketch": a["sketch"]}
        step.update(_fusion_hole_options(a))
        return [step]
    step = {"op": "hole", "id": step_id, "sketch": a["sketch"], "diameter": a["diameter"]}
    if a.get("through_all"):
        step["through_all"] = True
    else:
        step["depth"] = a["depth"]
    if "counterbore" in a:
        step["counterbore"] = {
            "diameter": a["counterbore"]["diameter"],
            "depth": a["counterbore"]["depth"],
        }
    elif "countersink" in a:
        step["countersink"] = {
            "diameter": a["countersink"]["diameter"],
            "angle": a["countersink"].get("angle", 90),
        }
    return [step]


def _steps_pattern(a, step_id):
    features = list(a["features"])
    if a["kind"] == "rectangular":
        step = {
            "op": "pattern_rect",
            "id": step_id,
            "features": features,
            "direction": a["direction"],
            "count": _int(a["count"]),
            "spacing": a["spacing"],
        }
        if "direction2" in a:
            step.update(
                direction2=a["direction2"], count2=_int(a["count2"]), spacing2=a["spacing2"]
            )
        return [step]
    step = {
        "op": "pattern_circ",
        "id": step_id,
        "features": features,
        "axis": a["axis"],
        "count": _int(a["count"]),
    }
    if "angle" in a:
        step["angle"] = a["angle"]
    return [step]


def _steps_shell(a, step_id):
    new = [k for k in _SHELL_NEW if k in a] or a.get("direction") == "both"
    if not new:
        return [
            {
                "op": "shell",
                "id": step_id,
                "faces": copy.deepcopy(a["faces"]),
                "thickness": a["thickness"],
                "direction": a.get("direction", "inside"),
            }
        ]
    direction = a.get("direction", "inside")
    step = {"op": "sf_shell_bodies" if "bodies" in a else "sf_shell", "id": step_id}
    if "bodies" in a:
        step["bodies"] = copy.deepcopy(a["bodies"])
    elif a.get("body"):
        step["body"] = True
    else:
        step["faces"] = copy.deepcopy(a["faces"])
    step["direction"] = direction
    for key in ("inside", "outside", "shell_type"):
        if key in a:
            step[key] = a[key]
    if "thickness" in a:
        if direction in ("inside", "both"):
            step.setdefault("inside", a["thickness"])
        if direction in ("outside", "both"):
            step.setdefault("outside", a["thickness"])
    return [step]


def _steps_set_parameter(a, step_id):
    step = {"op": "parameter", "name": a["name"], "value": a["value"]}
    if "unit" in a:
        step["unit"] = a["unit"]
    if "comment" in a:
        step["comment"] = a["comment"]
    return [step]


# -- titles ----------------------------------------------------------------------------------
def _title_sketch(a):
    where = a.get("plane") or ("face" if "face" in a else "") or a.get("on", "")
    return "AI: Sketch" + (" on %s" % where if where else "")


def _title_extrude(a):
    if a.get("through_all"):
        return "AI: Extrude through all"
    if "to" in a:
        return "AI: Extrude to object"
    return "AI: Extrude" + mm(a, "distance")


def _title_revolve(a):
    angle = a.get("angle", 360)
    return "AI: Revolve %s degrees" % kit.fmt(angle) if is_type(angle, "number") else "AI: Revolve"


def _title_pattern(a):
    kind = "Circular" if a.get("kind") == "circular" else "Rectangular"
    count = a.get("count")
    return "AI: %s pattern" % kind + (" x%d" % int(count) if is_type(count, "integer") else "")


def _title_parameter(a):
    if "name" in a and "value" in a:
        return "AI: Parameter %s = %s" % (a["name"], a["value"])
    return "AI: Parameter"


def _title_export(a):
    return "AI: Export %s" % str(a["format"]).upper() if a.get("format") else "AI: Export"


# -- the tools -------------------------------------------------------------------------------
define(
    "get_design",
    "Get design",
    "inspect",
    "BROWSER (the design's bodies, sketches, parameters) and TIMELINE",
    "Describe the open SciForge design: its bodies (volume in mm3, "
    "bounding box in mm), the timeline steps with their ids (use these ids in profile, "
    "sketch and features arguments), the user parameters and the sketches with their "
    "areas. Call it before changing a design and after each change to check the result. " + UNITS,
    schema({}),
    changes=False,
    needs=(),
    core=True,
    examples=[example({}, "everything about the open design, as JSON")],
)
define(
    "screenshot",
    "Screenshot",
    "view",
    "File > Capture Image",
    "Take a picture (PNG) of the design as SciForge shows it, to see what "
    "you built. view picks the camera: iso (default), front, back, top, bottom, left or "
    "right.",
    schema(
        {
            "view": {
                "type": "string",
                "enum": ["iso", "front", "back", "top", "bottom", "left", "right"],
                "default": "iso",
            },
            "width": {
                "type": "integer",
                "minimum": 64,
                "maximum": 4096,
                "default": 1024,
                "description": "picture width in pixels",
            },
            "height": {
                "type": "integer",
                "minimum": 64,
                "maximum": 4096,
                "default": 768,
                "description": "picture height in pixels",
            },
        }
    ),
    changes=False,
    needs=("design", "gui"),
    core=True,
    examples=[example({"view": "top", "width": 800, "height": 600}, "a top view, 800 x 600")],
)
define(
    "measure",
    "Measure",
    "inspect",
    "INSPECT > Measure",
    "Measure between two picks a and b of the current body or the origin: "
    "the minimum distance (mm) and, where it makes sense, the angle (degrees), like "
    "SciForge's Measure tool; also the X / Y / Z distances, the two nearest points and what "
    "each pick is (length, area, radius...). Only a: the size of that one pick (an edge's "
    "length and radius, a face's area and perimeter). " + kit.PICK_HELP + " " + SELECTOR_HELP,
    schema({"a": pick("the first pick"), "b": pick("the second pick (optional)")}, ["a"]),
    changes=False,
    needs=("design",),
    extra=_extra_measure,
    core=True,
    examples=[
        example(
            {"a": {"face": TOP_FACE}, "b": {"plane": "XY"}},
            "the height of the top face above the XY plane",
        )
    ],
)
define(
    "create_sketch",
    "Create sketch",
    "sketch",
    "SOLID > CREATE > Create Sketch",
    "Create a sketch with closed shapes (and lines) in it, ready for "
    "extrude, revolve or hole. It becomes one timeline step; its id is the profile for "
    "the next tools. " + SKETCH_HELP + " " + GEOMETRY_HELP + " " + MORE_GEOMETRY_HELP + " "
    "on: the id of a construction plane (construct_plane) to sketch on instead. auto_project "
    "(with face): the face's edges are projected into the sketch, as Fusion does. " + UNITS,
    schema(
        {
            "plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
            "offset": dict(_NUMBER, default=0, description="mm along the plane's normal"),
            "face": full_selector("Instead of plane: the flat face to sketch on (one face)."),
            "on": string("Instead of plane: the id of a construction plane to sketch on"),
            "auto_project": boolean("with face: project the face's edges into the sketch"),
            "geometry": {
                "type": "array",
                "items": _GEOMETRY_ITEM,
                "minItems": 1,
                "description": GEOMETRY_HELP,
            },
        },
        ["geometry"],
    ),
    ops=["sketch"],
    steps=_steps_create_sketch,
    extra=_extra_create_sketch,
    needs=(),
    id_base="Sketch",
    title_fn=_title_sketch,
    core=True,
    examples=[
        example(
            {"plane": "XY", "geometry": [{"rect": [0, 0, 40, 20], "name": "base"}]},
            "a 40 x 20 mm rectangle on the XY plane, its sizes named base.width / base.height",
        ),
        example(
            {"plane": "XY", "offset": 10, "geometry": [{"circle": [20, 10, 3]}]},
            "a 6 mm circle 10 mm above XY (on top of a 10 mm thick part)",
        ),
    ],
)
define(
    "extrude",
    "Extrude",
    "create",
    "SOLID > CREATE > Extrude",
    "Extrude a sketch's areas into a solid (SciForge's Extrude). distance "
    "goes along the sketch normal; flip: true goes the other way, for cuts too: a cut "
    "from a sketch lying on top of the part needs flip: true. regions picks some areas by "
    "a point inside each ([x, y] in sketch coordinates); without it the outer areas are used "
    "and shapes inside them are holes (a point in the ring and one in the disc fill it). "
    "direction one_side (default), symmetric (distance is the whole length, half on each "
    "side) or two_sides (distance one way, distance2 the other). through_all goes through "
    "the whole part instead of a distance. taper in degrees. "
    "More of Fusion's dialog: face (a flat face of the part as the profile, instead of a "
    "sketch), more_profiles (more sketches extruded together), to (Extent To Object: a plane, "
    "a face or a body to stop at), extent2 / to2 / taper2 (side two), measurement (symmetric: "
    "whole or half length), start (profile, offset with start_offset, or object with "
    "start_from), thin {location side1|center|side2, thickness, location2, thickness2} (a "
    "Thin Extrude: a wall along the profile; with curves it extrudes open sketch curves), "
    "bodies (Bodies to Cut / Join: auto or step ids), extend / object_offset (To Object). " + UNITS,
    schema(
        {
            "profile": {"type": "string", "description": "id of a create_sketch step"},
            "regions": {"type": "array", "items": _POINT2, "minItems": 1},
            "distance": _POSITIVE,
            "operation": _OPERATION,
            "direction": {
                "type": "string",
                "enum": ["one_side", "symmetric", "two_sides"],
                "default": "one_side",
            },
            "distance2": _POSITIVE,
            "through_all": {"type": "boolean", "default": False},
            "taper": {"type": "number", "minimum": -89, "maximum": 89, "default": 0},
            "flip": {"type": "boolean", "default": False},
            "face": kit.selector("instead of profile: a flat face of the part as the profile"),
            "more_profiles": kit.step_ids("more sketch steps extruded with profile"),
            "curves": either("open sketch curves for a thin extrude. " + kit.CURVES_HELP),
            "to": _EXTRUDE_REF,
            "extent2": enum(["distance", "through_all", "to_object"], "side two's extent"),
            "to2": _EXTRUDE_REF,
            "taper2": kit.number("side two's taper (degrees)", minimum=-89, maximum=89),
            "measurement": enum(
                ["whole", "half"],
                "symmetric: distance is the whole length " "or each half",
                default="whole",
            ),
            "start": enum(
                ["profile", "offset", "object"], "where the extrude starts", default="profile"
            ),
            "start_offset": kit.length("start offset along the normal"),
            "start_from": _EXTRUDE_REF,
            "thin": obj(
                {
                    "location": enum(["side1", "center", "side2"], default="side1"),
                    "thickness": positive("wall thickness (mm)"),
                    "location2": enum(["side1", "center", "side2"]),
                    "thickness2": positive("side two's wall thickness (mm)"),
                },
                description="Thin Extrude: a wall along the profile instead of a solid",
            ),
            "bodies": _BODIES,
            "extend": enum(
                ["face", "adjacent", "body", "through"],
                "To Object: how the " "target face is extended",
            ),
            "extend2": enum(["face", "adjacent", "body", "through"], "side two's extend"),
            "object_offset": kit.length("To Object: stop this far from the object"),
            "object_offset2": kit.length("side two's object offset"),
        },
    ),
    ops=["extrude"],
    steps=_steps_extrude,
    extra=_extra_extrude,
    id_base="Extrude",
    title_fn=_title_extrude,
    core=True,
    examples=[
        example({"profile": "Sketch1", "distance": 10}, "a 10 mm solid from Sketch1's areas"),
        example(
            {"profile": "Sketch2", "through_all": True, "operation": "cut", "flip": True},
            "cut a sketch lying on the top face down through the whole part",
        ),
        example(
            {
                "profile": "Sketch3",
                "to": {"face": {"normal": [0, 0, 1], "count": 1}},
                "operation": "join",
            },
            "extrude up to the top face (Extent To Object)",
        ),
    ],
)
define(
    "revolve",
    "Revolve",
    "create",
    "SOLID > CREATE > Revolve",
    "Revolve a sketch's areas around an axis (SciForge's Revolve). axis: "
    "X, Y or Z (origin axes) or sketch_h / sketch_v (the sketch's own horizontal or "
    "vertical axis). angle in degrees, 360 (default) for a full turn. regions picks areas "
    "by a point inside each, as for extrude. operation auto (default) lets SciForge "
    "choose like its Revolve dialog does. More of the dialog: face (a flat face as the "
    'profile), axis {"sketch": id, "at": [x, y]} (the sketch line through that point), '
    '{"sketch": id, "construction": [[x1, y1], [x2, y2]]} (a construction line drawn for it), '
    '{"edge": selector} (a straight edge of the part); type angle | to | full, to (a pick it '
    "revolves up to), direction one_side | two_sides | symmetric, angle2 (side two), bodies.",
    schema(
        {
            "profile": {"type": "string", "description": "id of a create_sketch step"},
            "regions": {"type": "array", "items": _POINT2, "minItems": 1},
            "axis": either("X, Y, Z, sketch_h, sketch_v or an axis object (see above)"),
            "angle": {"type": "number", "exclusiveMinimum": 0, "maximum": 360, "default": 360},
            "operation": {
                "type": "string",
                "enum": ["auto", "join", "cut", "intersect", "new_body"],
                "default": "auto",
            },
            "face": kit.selector("instead of profile: a flat face of the part as the profile"),
            "type": enum(["angle", "to", "full"], "angle (default with an angle), full or to"),
            "to": pick("type to: what the revolve goes up to"),
            "direction": enum(["one_side", "two_sides", "symmetric"], default="one_side"),
            "angle2": kit.number("side two's angle (degrees)", above=0, maximum=360),
            "bodies": _BODIES,
        },
        ["axis"],
    ),
    ops=["sf_revolve"],
    steps=_steps_revolve,
    extra=_extra_revolve,
    id_base="Revolve",
    title_fn=_title_revolve,
    core=True,
    examples=[
        example({"profile": "Sketch1", "axis": "Z"}, "a full turn about the Z axis"),
        example(
            {
                "profile": "Sketch1",
                "axis": {
                    "edge": {
                        "type": "line",
                        "parallel": [0, 0, 1],
                        "at": {"axis": "x", "value": "min"},
                        "count": 1,
                    }
                },
                "angle": 90,
            },
            "a quarter turn about a straight edge of the part",
        ),
    ],
)
define(
    "fillet",
    "Fillet",
    "modify",
    "SOLID > MODIFY > Fillet",
    "Round edges of the current body with a radius (SciForge's Fillet). "
    "Pick them with edges (an edge selector), faces (every sharp edge around the faces a "
    "face selector picks) and/or features (the edges earlier steps made, by step id). "
    "Errors such as 'the radius is too big for this edge' come back as sentences. For "
    "several radii, chord length, variable radius or tangent chain off use fillet_sets; Rule "
    "Fillet and Full Round Fillet are their own tools. With the timeline marker rolled back "
    "the fillet goes in at the marker and later fillets keep their edges. " + UNITS,
    schema(
        {
            "edges": full_selector("The edges to round."),
            "faces": full_selector("Round every sharp edge around these faces."),
            "features": _FEATURES,
            "radius": _POSITIVE,
        },
        ["radius"],
    ),
    ops=["blend_fillet", "blend_insert"],
    steps=_steps_fillet,
    extra=_extra_blend,
    needs=("solid",),
    id_base="Fillet",
    title_fn=lambda a: "AI: Fillet" + mm(a, "radius"),
    core=True,
    examples=[example({"edges": TOP4, "radius": 3}, "round the 4 top edges of a box, 3 mm")],
)
define(
    "chamfer",
    "Chamfer",
    "modify",
    "SOLID > MODIFY > Chamfer",
    "Bevel edges of the current body (SciForge's Chamfer). distance alone: "
    "equal distances; distance and distance2: two distances (flip swaps the sides); "
    "distance and angle: a distance and an angle in degrees. Pick edges as for fillet. " + UNITS,
    schema(
        {
            "edges": full_selector("The edges to bevel."),
            "faces": full_selector("Bevel every sharp edge around these faces."),
            "features": _FEATURES,
            "distance": _POSITIVE,
            "distance2": _POSITIVE,
            "angle": {"type": "number", "exclusiveMinimum": 0, "maximum": 89},
            "flip": {"type": "boolean", "default": False},
        },
        ["distance"],
    ),
    ops=["blend_chamfer", "blend_insert"],
    steps=_steps_chamfer,
    extra=_extra_chamfer,
    needs=("solid",),
    id_base="Chamfer",
    title_fn=lambda a: "AI: Chamfer" + mm(a, "distance"),
    core=True,
    examples=[example({"edges": TOP4, "distance": 1, "angle": 30}, "1 mm at 30 degrees")],
)
define(
    "hole",
    "Hole",
    "create",
    "SOLID > CREATE > Hole",
    "Drill holes into the part (SciForge's Hole). First create_sketch on "
    "the face where the holes start (for example plane XY with offset = the top's height) "
    "with a small circle at each hole centre; the holes go at the circles' centres, "
    "whatever their size. Give depth or through_all. Optional counterbore {diameter, "
    "depth} or countersink {diameter, angle} (angle in degrees, default 90). "
    "Single Hole instead of a sketch: face (the flat face clicked) and at ([x, y, z] on it), "
    "with up to two references [{edge: edge selector, distance}] that place the centre from "
    "straight edges. All of Fusion's Hole dialog: hole_type simple | counterbore | countersink "
    "(cbore_diameter, cbore_depth, csink_diameter, csink_angle), extent distance | all | to "
    "(to: a plane or face), drill_point flat | angle (drill_angle), tap_type simple | "
    "clearance | tapped | taper, standard iso | ansi, size / designation (e.g. M6x1, 1/4-20 "
    "UNC), fit close | normal | loose, fastener socket_head | hex_head | countersunk, "
    "fastener_head (head pocket sized for it), taper_kind npt | bspt with taper_size, "
    "thread_class, thread_direction right | left, modeled (real thread), full_tap, "
    "tap_depth, flip. " + UNITS,
    schema(
        {
            "sketch": {"type": "string", "description": "id of the sketch with the centres"},
            "diameter": _POSITIVE,
            "depth": _POSITIVE,
            "through_all": {"type": "boolean", "default": False},
            "counterbore": schema(
                {"diameter": _POSITIVE, "depth": _POSITIVE}, ["diameter", "depth"]
            ),
            "countersink": schema(
                {
                    "diameter": _POSITIVE,
                    "angle": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 179,
                        "default": 90,
                    },
                },
                ["diameter"],
            ),
            "face": kit.selector("Single Hole: the flat face the hole starts on (one face)"),
            "at": kit.point3("Single Hole: the clicked point on that face"),
            "references": array(
                obj(
                    {
                        "edge": kit.selector("a straight edge of the part", "edges"),
                        "distance": kit.length("distance of the centre from it"),
                    },
                    ["edge", "distance"],
                ),
                "Single Hole: up to two edges that place the centre",
                max_items=2,
            ),
            "hole_type": enum(["simple", "counterbore", "countersink"], default="simple"),
            "cbore_diameter": positive("counterbore diameter (mm)"),
            "cbore_depth": positive("counterbore depth (mm)"),
            "csink_diameter": positive("countersink diameter (mm)"),
            "csink_angle": kit.number("countersink angle (degrees)", above=0, maximum=179),
            "extent": enum(["distance", "all", "to"], default="distance"),
            "to": kit.free_object('extent to: {"plane": "XY"|"XZ"|"YZ"} or {"face": selector}'),
            "drill_point": enum(["flat", "angle"], default="flat"),
            "drill_angle": kit.number("drill point angle (degrees)", above=0, maximum=180),
            "tap_type": enum(["simple", "clearance", "tapped", "taper"], default="simple"),
            "standard": enum(["iso", "ansi"], default="iso"),
            "size": string("nominal size, e.g. 6 (M6) or 1/4"),
            "designation": string("thread designation, e.g. M6x1 or 1/4-20 UNC"),
            "fit": enum(["close", "normal", "loose"], "clearance hole fit", default="normal"),
            "fastener": enum(
                ["socket_head", "hex_head", "countersunk"],
                "clearance: the " "fastener the hole is for",
            ),
            "fastener_head": boolean("size the counterbore / countersink for that fastener"),
            "taper_kind": enum(["npt", "bspt"]),
            "taper_size": string("taper thread size, e.g. 1/8"),
            "thread_class": string("e.g. 6H or 2B"),
            "thread_direction": enum(["right", "left"], default="right"),
            "modeled": boolean("cut the real thread (default: cosmetic)"),
            "full_tap": boolean("thread the whole depth"),
            "tap_depth": positive("thread depth (mm)"),
            "flip": boolean("drill the other way"),
        },
    ),
    ops=["hole", "hole_points", "hole_at"],
    steps=_steps_hole,
    extra=_extra_hole,
    needs=("solid",),
    id_base="Hole",
    title_fn=lambda a: "AI: Hole" + mm(a, "diameter"),
    core=True,
    examples=[
        example(
            {"sketch": "Sketch2", "diameter": 6, "through_all": True},
            "6 mm holes through the part at Sketch2's circle centres",
        ),
        example(
            {
                "face": TOP_FACE,
                "at": [20, 10, 10],
                "tap_type": "tapped",
                "designation": "M6x1",
                "depth": 12,
            },
            "one tapped M6 hole 12 mm deep, clicked on the top face",
        ),
    ],
)
define(
    "pattern",
    "Pattern",
    "create",
    "SOLID > CREATE > Pattern > Rectangular / Circular Pattern (features)",
    "Repeat earlier steps (features: their ids, e.g. a cut or a hole). "
    "kind rectangular: count copies spaced by spacing (mm) along direction X, Y or Z, "
    "optionally a second row with direction2, count2, spacing2. kind circular: count "
    "copies around axis X, Y or Z over angle degrees (default 360). Counts include the "
    "original. rectangular_pattern, circular_pattern, pattern_on_path and mirror offer the "
    "whole Fusion dialogs (faces, bodies, edges as directions, symmetric, suppression).",
    schema(
        {
            "kind": {"type": "string", "enum": ["rectangular", "circular"]},
            "features": _FEATURES,
            "direction": _AXIS3,
            "count": {"type": "integer", "minimum": 2},
            "spacing": _NUMBER,
            "direction2": _AXIS3,
            "count2": {"type": "integer", "minimum": 2},
            "spacing2": _NUMBER,
            "axis": _AXIS3,
            "angle": {"type": "number", "exclusiveMinimum": 0, "maximum": 360, "default": 360},
        },
        ["kind", "features", "count"],
    ),
    ops=["pattern_rect", "pattern_circ"],
    steps=_steps_pattern,
    extra=_extra_pattern,
    needs=("solid",),
    id_base="Pattern",
    title_fn=_title_pattern,
    core=True,
    examples=[
        example(
            {
                "kind": "rectangular",
                "features": ["Extrude2"],
                "direction": "X",
                "count": 3,
                "spacing": 20,
            },
            "three copies of a cut, 20 mm apart along X",
        ),
        example(
            {"kind": "circular", "features": ["Hole1"], "axis": "Z", "count": 6},
            "six holes around the Z axis",
        ),
    ],
)
define(
    "shell",
    "Shell",
    "modify",
    "SOLID > MODIFY > Shell",
    "Hollow the current body out with a wall thickness (SciForge's Shell). "
    'faces: the faces to remove (open), a face selector, e.g. the top face {"normal": '
    '[0, 0, 1], "count": 1}. direction inside (default: the outside stays where it is) '
    "or outside. More of Fusion's dialog: body: true (hollow and closed, no face removed), "
    "direction both with inside / outside thicknesses, shell_type sharp | rounded (rounded "
    'outer corners), bodies [{"body": step id, "faces": selector}] (one Shell over several '
    "bodies). " + UNITS,
    schema(
        {
            "faces": full_selector("The faces to remove."),
            "thickness": _POSITIVE,
            "direction": {
                "type": "string",
                "enum": ["inside", "outside", "both"],
                "default": "inside",
            },
            "body": boolean("hollow the whole body, closed (no face removed)"),
            "inside": positive("inside thickness (mm)"),
            "outside": positive("outside thickness (mm)"),
            "shell_type": enum(["sharp", "rounded"], default="sharp"),
            "bodies": array(
                kit.free_object(
                    '{"body": step id, "faces": selector} (faces optional: '
                    "without them that body is made hollow)"
                ),
                "several bodies in one Shell",
                min_items=1,
            ),
        },
    ),
    ops=["shell", "sf_shell", "sf_shell_bodies"],
    steps=_steps_shell,
    extra=_extra_shell,
    needs=("solid",),
    id_base="Shell",
    title_fn=lambda a: "AI: Shell" + mm(a, "thickness"),
    core=True,
    examples=[example({"faces": TOP_FACE, "thickness": 2}, "an open box with 2 mm walls")],
)
define(
    "set_parameter",
    "Set parameter",
    "parameters",
    "MODIFY > Change Parameters (User Parameters, +)",
    "Create or change a user parameter (SciForge's Change Parameters). "
    'value is a number or an expression using other parameters, e.g. "width / 4". '
    "unit: mm (default), deg or empty for a plain number. Everything that uses the "
    "parameter updates.",
    schema(
        {
            "name": {"type": "string", "description": "letters, digits and _"},
            "value": {"type": ["number", "string"]},
            "unit": {"type": "string", "default": "mm"},
            "comment": string("a note shown in Change Parameters"),
        },
        ["name", "value"],
    ),
    ops=["parameter"],
    steps=_steps_set_parameter,
    extra=_extra_set_parameter,
    needs=(),
    id_base="Parameter",
    title_fn=_title_parameter,
    core=True,
    own_id=False,
    examples=[
        example({"name": "width", "value": "depth * 2", "unit": "mm"}, "width follows depth")
    ],
)
define(
    "undo",
    "Undo",
    "document",
    "Quick Access Toolbar > Undo (Ctrl+Z)",
    "Undo the last change in SciForge (each AI change is one undo step).",
    schema({}),
    needs=("design",),
    core=True,
    examples=[example({}, "take back the last change")],
)
define(
    "redo",
    "Redo",
    "document",
    "Quick Access Toolbar > Redo (Ctrl+Y)",
    "Redo the change undo took back (one AI call or one SciForge command at a time; a new "
    "change after an undo clears what could be redone).",
    schema({}),
    needs=("design",),
    core=True,
    examples=[example({}, "do again what undo took back")],
)
define(
    "save",
    "Save",
    "document",
    "Quick Access Toolbar > Save",
    "Save the design. Without path it is saved where it is (a new design "
    "asks for a place in SciForge). With path (a full path ending in .FCStd) it is saved "
    "there; saving over another existing file must be confirmed by the person in SciForge.",
    schema({"path": {"type": "string"}}),
    changes=False,
    writes_files=True,
    confirm_overwrite=True,
    extra=_extra_save,
    core=True,
    examples=[example({"path": "/home/me/designs/bracket.FCStd"}, "save under that name")],
)
define(
    "export",
    "Export",
    "import_export",
    "File > Export",
    "Export the design's bodies to a file: format step (.step / .stp), stl "
    "or 3mf (for 3D printing). path is a full path; replacing an existing file must be "
    "confirmed by the person in SciForge. Also: iges (.igs), stl_ascii, obj, brep, and dxf "
    "(one sketch, or one flat face, as 2D curves: give sketch or face). bodies: step ids of "
    "the bodies to write (default every visible body); mesh formats take refinement Low | "
    "Medium | High (Fusion's presets), unit (Millimeter, Centimeter, Meter, Inch, Foot) and "
    "one_file_per_body. STEP keeps the components and colours; mesh files keep only the "
    "triangles (no sketches, timeline or parameters).",
    schema(
        {
            "format": {
                "type": "string",
                "enum": ["step", "stl", "3mf", "iges", "stl_ascii", "obj", "brep", "dxf"],
            },
            "path": {"type": "string"},
            "bodies": kit.step_ids("the bodies to write (default: every visible body)"),
            "sketch": kit.step_id("format dxf: the sketch to write"),
            "face": kit.selector("format dxf: the flat face to write"),
            "refinement": enum(["Low", "Medium", "High"], default="Medium"),
            "unit": enum(
                ["Millimeter", "Centimeter", "Meter", "Inch", "Foot"], default="Millimeter"
            ),
            "one_file_per_body": boolean("mesh formats: one file per body", default=False),
        },
        ["format", "path"],
    ),
    changes=False,
    writes_files=True,
    confirm_overwrite=True,
    extra=_extra_export,
    title_fn=_title_export,
    core=True,
    examples=[
        example({"format": "stl", "path": "/home/me/part.stl"}, "an STL for 3D printing"),
        example(
            {"format": "dxf", "path": "/home/me/outline.dxf", "sketch": "Sketch1"},
            "Sketch1 as a DXF for a laser cutter",
        ),
    ],
)
