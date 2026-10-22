# SPDX-License-Identifier: LGPL-2.1-or-later
"""The building blocks of the AI tool catalogue (sciforge/ai/catalog): the shared help texts an
AI model reads (selectors, picks, sketch planes, curves), small helpers that write the JSON
Schemas of the tools' arguments, and the hand-written validator that checks arguments against
them and answers in plain sentences an AI can act on.

The schemas use a small subset of JSON Schema 2020-12 (type, properties, required,
additionalProperties false, enum, items, minItems, maxItems, minimum, maximum,
exclusiveMinimum, default, description), so every AI app and provider takes them (Gemini's
translator in providers/gemini.py knows exactly these) and nothing has to be installed.
Arguments that may take two shapes (an origin plane name or a face selector, a sketch id or
a curve pick) are typed ["string", "object"] and checked further by the tool's own rules.

Pure Python: no FreeCAD, no Qt (the MCP server an AI app starts imports it).
"""

import math
import re

UNITS = "All lengths are in millimetres (mm) and all angles in degrees."

EDGE_TYPES = ("line", "circle", "ellipse", "bspline")
FACE_TYPES = ("plane", "cylinder", "cone", "sphere", "torus", "bspline", "extrusion")
SELECTOR_KEYS = (
    "type",
    "normal",
    "parallel",
    "along",
    "radius",
    "on_faces",
    "not_on_faces",
    "at",
    "all",
    "count",
    "any_of",
)

# Matches SciForgeTests/golden/README.md "Selectors" and sciforge/ai/ops/selectors.py.
SELECTOR_HELP = "\n".join(
    [
        "A selector picks edges or faces by their geometry, the way a person would click them"
        ' (never by names like "Edge7"). It is an object; every filter is optional, they '
        "combine with AND and apply in this order:",
        "  type: for edges line, circle, ellipse or bspline; for faces plane, cylinder, cone,"
        " sphere, torus, bspline or extrusion (the side of an extruded spline or ellipse).",
        "  normal: [x, y, z] (faces only) flat faces whose outward normal points this way.",
        "  parallel: [x, y, z] straight edges parallel to this direction (either sense).",
        "  along: [x, y, z] (faces only) faces running along this direction: the side walls of"
        " a part extruded that way (flat, round or free-form).",
        "  radius: a number (mm): circles, cylinders and spheres with this radius.",
        "  on_faces: a face selector (edges only): the edges that bound the faces it picks.",
        "  not_on_faces: a face selector (edges only): the edges that do NOT bound those faces.",
        '  at: {"axis": "x" | "y" | "z", "value": "max" | "min" | a number in mm}, or a list '
        "of them: keeps the elements whose centre lies at the extreme (or at that coordinate)"
        " along the axis, among those the filters above kept; a list applies each condition "
        "in turn.",
        "  all: true: every edge or face (combine with nothing else except count).",
        "  count: a whole number: the pick must contain exactly this many, or the tool fails "
        "instead of changing the wrong geometry. Always give it.",
        "  any_of: [selector, ...]: the union of several selectors (each may have its own "
        "count).",
        'Examples: the 4 top edges of a box {"type": "line", "at": {"axis": "z", "value": '
        '"max"}, "count": 4}; the top face {"normal": [0, 0, 1], "count": 1}; one specific '
        'edge {"type": "line", "parallel": [0, 1, 0], "at": [{"axis": "x", "value": 5}, '
        '{"axis": "z", "value": 5}], "count": 1}.',
        "Selectors look at the current body as it is now; call get_design first to see its "
        "size.",
    ]
)

SKETCH_HELP = (
    "Sketch planes are the origin planes: XY (normal +Z, sketch x/y are X/Y), XZ (normal -Y, "
    "sketch x/y are X/Z) and YZ (normal +X, sketch x/y are Y/Z). offset moves the sketch along "
    "that normal. Instead of a plane you can give face, a selector that picks exactly one flat "
    "face of the part; the sketch's x/y axes are then the ones SciForge gives that face, so "
    "prefer an origin plane with an offset when you can."
)

GEOMETRY_HELP = (
    "Each geometry item is an object with exactly one of: rect [x0, y0, x1, y1] (two opposite "
    "corners), center_rect [cx, cy, width, height], circle [cx, cy, radius], polyline "
    "[[x, y], ...] (at least 3 corners, always closed), polygon {center: [x, y], radius, sides, "
    "rotation} (a regular polygon with its corners on that radius; rotation in degrees), slot "
    "[x1, y1, x2, y2, width] (a straight slot between two centre points), line [x0, y0, x1, y1] "
    "(one open line: it makes no area). Optional name: dimensions <name>.width, <name>.height, "
    "<name>.x, <name>.y (rectangles) or <name>.diameter, <name>.x, <name>.y (circles). Shapes "
    "inside each other make separate areas (a circle inside a rectangle makes a ring area and "
    "a disc area); extrude and revolve without regions use the outer areas with the shapes "
    "inside them as holes (that rectangle with its circle extrudes as a plate with a hole)."
)

MORE_GEOMETRY_HELP = (
    "Also: ellipse [cx, cy, major, minor] (major radius along x, the larger), spline_loop "
    "[[x, y], ...] (a closed smooth curve through at least 3 points), segments [{line: [x0, y0, "
    "x1, y1]} | {arc: [cx, cy, r, a0, a1]} | {spline: [[x, y], ...], tangents: [[tx, ty], [tx, "
    "ty]]}, ...] (a closed chain of lines, arcs counter-clockwise from a0 to a1 degrees, and "
    "open splines; each piece starts where the one before ends)."
)

PICK_HELP = (
    'A pick is one of {"plane": "XY"|"XZ"|"YZ"}, {"axis": "X"|"Y"|"Z"}, {"origin": true}, '
    '{"face": face selector}, {"edge": edge selector}, {"vertex": [x, y, z]} (a corner of the '
    'part) or {"construct": id} (a construction plane, axis or point made earlier). Face and '
    "edge selectors must pick exactly one element of the current body."
)

BODY_PICK_HELP = (
    'A body pick is "XY" | "XZ" | "YZ" (an origin plane), "X" | "Y" | "Z" (an origin axis), '
    '{"face": selector, "of": step id}, {"edge": selector, "of": step id}, {"vertex": '
    '{"at": ...}, "of": step id} (a corner: the vertex selector takes only "at" conditions) or '
    '{"body": step id} (a whole body). "of" names a step whose body the selector looks at; '
    "left out, the body you are working on."
)

CURVES_HELP = (
    'Curves (paths, rails, rib curves) are given as "<sketch id>" (every curve of that sketch), '
    '{"sketch": id, "at": [x, y]} (the curve through that sketch point and the curves joined '
    'smoothly to it, like Fusion\'s chain selection; "chain": false for that curve alone; "at" '
    'may also be a list of points) or {"edge": edge selector} (edges of the part as it is now).'
)

STEP_HELP = (
    "Steps, sketches, bodies and components are named by the ids the tools report and "
    "get_design / get_timeline list (for example 'Sketch1', 'Extrude2'). A body is named by "
    "any step in it (the step that made it, usually)."
)

EXPRESSION_HELP = (
    "Value fields can follow a parameter: expressions {field: formula} (for example "
    '{"distance": "width / 2"}) keeps the field driven by that formula.'
)

# -- schema helpers ---------------------------------------------------------------------------
_NUMBER = {"type": "number"}


def number(description="", default=None, minimum=None, maximum=None, above=None):
    out = {"type": "number"}
    if description:
        out["description"] = description
    if above is not None:
        out["exclusiveMinimum"] = above
    if minimum is not None:
        out["minimum"] = minimum
    if maximum is not None:
        out["maximum"] = maximum
    if default is not None:
        out["default"] = default
    return out


def positive(description="", default=None, maximum=None):
    return number(description, default=default, above=0, maximum=maximum)


def length(description="", default=None):
    """A length in mm, any sign."""
    return number((description + " (mm)").strip(), default=default)


def angle(description="", default=None, minimum=None, maximum=None):
    return number(
        (description + " (degrees)").strip(), default=default, minimum=minimum, maximum=maximum
    )


def integer(description="", default=None, minimum=None, maximum=None):
    out = {"type": "integer"}
    if description:
        out["description"] = description
    if minimum is not None:
        out["minimum"] = minimum
    if maximum is not None:
        out["maximum"] = maximum
    if default is not None:
        out["default"] = default
    return out


def boolean(description="", default=None):
    out = {"type": "boolean"}
    if description:
        out["description"] = description
    if default is not None:
        out["default"] = default
    return out


def string(description="", default=None):
    out = {"type": "string"}
    if description:
        out["description"] = description
    if default is not None:
        out["default"] = default
    return out


def enum(values, description="", default=None):
    out = {"type": "string", "enum": list(values)}
    if description:
        out["description"] = description
    if default is not None:
        out["default"] = default
    return out


def array(items, description="", min_items=None, max_items=None):
    out = {"type": "array", "items": items}
    if description:
        out["description"] = description
    if min_items is not None:
        out["minItems"] = min_items
    if max_items is not None:
        out["maxItems"] = max_items
    return out


def numbers(n, description=""):
    return array(dict(_NUMBER), description, n, n)


def point2(description="[x, y] in sketch coordinates (mm)"):
    return numbers(2, description)


def point3(description="[x, y, z] in design coordinates (mm)"):
    return numbers(3, description)


def vector3(description="[x, y, z] direction"):
    return numbers(3, description)


def obj(properties, required=(), description=""):
    out = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        out["required"] = list(required)
    if description:
        out["description"] = description
    return out


def free_object(description):
    """An object whose keys the tool's own rules check (a pick, a set of options)."""
    return {"type": "object", "description": description}


def either(description):
    """A string or an object (an origin name, a sketch id, or a pick)."""
    return {"type": ["string", "object"], "description": description}


def step_id(description="id of an earlier step"):
    return string(description)


def step_ids(description="ids of earlier steps", min_items=1):
    return array(string(), description, min_items)


_MARKED = {}  # id(schema node) -> "faces" | "edges": the compact selectors, checked by walk


def selector(description, element="faces"):
    """A selector in the compact form the newer tools use: the rules are in the server's
    instructions and get_help("selectors"); validate() checks it with check_selector."""
    if element == "faces":
        words = "a face selector: filters type, normal, along, radius, at, all, count, any_of"
    else:
        words = (
            "an edge selector: filters type, parallel, radius, on_faces, not_on_faces, at, "
            "all, count, any_of"
        )
    node = {
        "type": "object",
        "description": "%s (%s; see get_help topic selectors). Give count." % (description, words),
    }
    _MARKED[id(node)] = element
    return node


def check_marked(schema_obj, value, path, problems):
    """Check every value whose schema is a compact selector (anywhere in the arguments)."""
    element = _MARKED.get(id(schema_obj))
    if element is not None:
        check_selector(value, path, element, problems)
        return
    if isinstance(value, dict):
        prefix = path + "." if path else ""
        for key, sub in schema_obj.get("properties", {}).items():
            if key in value:
                check_marked(sub, value[key], prefix + key, problems)
    elif isinstance(value, list) and isinstance(schema_obj.get("items"), dict):
        for i, item in enumerate(value):
            check_marked(schema_obj["items"], item, "%s[%d]" % (path, i), problems)


def _selector_properties():
    return {
        "type": {"type": "string", "enum": sorted(set(EDGE_TYPES + FACE_TYPES))},
        "normal": dict(numbers(3), description="[x, y, z] outward normal of flat faces"),
        "parallel": dict(numbers(3), description="[x, y, z] direction of straight edges"),
        "along": dict(
            numbers(3),
            description="[x, y, z]: faces running along it (the side walls of a part "
            "extruded that way)",
        ),
        "radius": positive("radius in mm"),
        "on_faces": {"type": "object", "description": "a face selector"},
        "not_on_faces": {"type": "object", "description": "a face selector"},
        "at": {
            "description": '{"axis": "x"|"y"|"z", "value": "max"|"min"|number} or a list ' "of them"
        },
        "all": {"type": "boolean"},
        "count": {"type": "integer", "minimum": 1},
        "any_of": {"type": "array", "items": {"type": "object"}, "minItems": 1},
    }


def full_selector(description):
    """A selector with the whole selector help in its description (the first 16 tools)."""
    return {
        "type": "object",
        "description": description + " " + SELECTOR_HELP,
        "properties": _selector_properties(),
        "additionalProperties": False,
    }


PLANES = ("XY", "XZ", "YZ")
AXES = ("X", "Y", "Z")


def pick(description="what is picked"):
    return {
        "type": "object",
        "description": description + ". " + PICK_HELP,
        "properties": {
            "plane": {"type": "string", "enum": list(PLANES)},
            "axis": {"type": "string", "enum": list(AXES)},
            "origin": {"type": "boolean"},
            "face": {"type": "object"},
            "edge": {"type": "object"},
            "vertex": numbers(3),
            "construct": {"type": "string"},
        },
        "additionalProperties": False,
    }


def schema(properties, required=()):
    out = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        out["required"] = list(required)
    return out


# -- validation -------------------------------------------------------------------------------
_TYPE_WORDS = {
    "number": "a number",
    "integer": "a whole number",
    "string": "text",
    "boolean": "true or false",
    "object": "an object",
    "array": "a list",
    "null": "null",
}


def is_type(value, kind):
    if kind == "number":
        return (
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        )
    if kind == "integer":
        if isinstance(value, bool):
            return False
        return isinstance(value, int) or (isinstance(value, float) and value.is_integer())
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    if kind == "null":
        return value is None
    return True


def fmt(number_value):
    return "%g" % number_value


def check(schema_obj, value, path, problems):
    """Check value against the schema subset; add a plain sentence per problem."""
    name = path or "the arguments"
    kinds = schema_obj.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if not any(is_type(value, kind) for kind in kinds):
            words = " or ".join(_TYPE_WORDS.get(kind, kind) for kind in kinds)
            problems.append("%s must be %s" % (name, words))
            return
    if "enum" in schema_obj and value not in schema_obj["enum"]:
        problems.append(
            "%s must be one of: %s" % (name, ", ".join(str(v) for v in schema_obj["enum"]))
        )
        return
    if is_type(value, "number"):
        if "exclusiveMinimum" in schema_obj and value <= schema_obj["exclusiveMinimum"]:
            problems.append(
                "%s must be a number above %s" % (name, fmt(schema_obj["exclusiveMinimum"]))
            )
        if "minimum" in schema_obj and value < schema_obj["minimum"]:
            problems.append("%s must be at least %s" % (name, fmt(schema_obj["minimum"])))
        if "maximum" in schema_obj and value > schema_obj["maximum"]:
            problems.append("%s must be at most %s" % (name, fmt(schema_obj["maximum"])))
    if isinstance(value, list):
        low, high = schema_obj.get("minItems"), schema_obj.get("maxItems")
        if low is not None and low == high and len(value) != low:
            problems.append("%s must have exactly %d items" % (name, low))
        elif low is not None and len(value) < low:
            problems.append(
                "%s must have at least %d item%s" % (name, low, "" if low == 1 else "s")
            )
        elif high is not None and len(value) > high:
            problems.append("%s must have at most %d items" % (name, high))
        if "items" in schema_obj:
            for i, item in enumerate(value):
                check(schema_obj["items"], item, "%s[%d]" % (path, i), problems)
    if isinstance(value, dict):
        props = schema_obj.get("properties", {})
        prefix = path + "." if path else ""
        for key in schema_obj.get("required", []):
            if key not in value:
                problems.append("%s%s is missing" % (prefix, key))
        for key, item in value.items():
            if key in props:
                check(props[key], item, prefix + key, problems)
            elif schema_obj.get("additionalProperties") is False:
                where = (" in %s" % path) if path else ""
                problems.append("%s is not a known argument%s" % (key, where))


def check_selector(spec, path, element, problems):
    """The selector rules of sciforge/ai/ops/selectors.py, as sentences."""
    if not isinstance(spec, dict):
        problems.append("%s must be a selector object" % path)
        return
    for key in spec:
        if key not in SELECTOR_KEYS:
            problems.append(
                "%s.%s is not a selector filter (use %s)" % (path, key, ", ".join(SELECTOR_KEYS))
            )
    if "count" in spec and not (is_type(spec["count"], "integer") and spec["count"] >= 1):
        problems.append("%s.count must be a whole number of at least 1" % path)
    if "any_of" in spec:
        subs = spec["any_of"]
        if not isinstance(subs, list) or not subs:
            problems.append("%s.any_of must be a non-empty list of selectors" % path)
            return
        for i, sub in enumerate(subs):
            check_selector(sub, "%s.any_of[%d]" % (path, i), element, problems)
        return
    if spec.get("all") is not None and not isinstance(spec.get("all"), bool):
        problems.append("%s.all must be true or false" % path)
    if spec.get("all") and set(spec) - {"all", "count"}:
        problems.append("%s: all combines with nothing else (except count)" % path)
    if "type" in spec:
        allowed = EDGE_TYPES if element == "edges" else FACE_TYPES
        if spec["type"] not in allowed:
            problems.append(
                "%s.type must be one of %s for %s" % (path, ", ".join(allowed), element)
            )
    for key in ("normal", "along"):
        if key in spec and element != "faces":
            problems.append("%s.%s only applies to faces" % (path, key))
    for key in ("normal", "parallel", "along"):
        if key in spec:
            vec = spec[key]
            if not (
                isinstance(vec, list) and len(vec) == 3 and all(is_type(v, "number") for v in vec)
            ):
                problems.append("%s.%s must be [x, y, z]" % (path, key))
            elif all(abs(v) < 1e-12 for v in vec):
                problems.append("%s.%s must not be [0, 0, 0]" % (path, key))
    if "radius" in spec and not (is_type(spec["radius"], "number") and spec["radius"] > 0):
        problems.append("%s.radius must be a number above 0" % path)
    for key in ("on_faces", "not_on_faces"):
        if key in spec:
            if element != "edges":
                problems.append("%s.%s only applies to edges" % (path, key))
            check_selector(spec[key], "%s.%s" % (path, key), "faces", problems)
    if "on_faces" in spec and "not_on_faces" in spec:
        problems.append("%s: give on_faces or not_on_faces, not both" % path)
    if "at" in spec:
        check_at(spec["at"], path, problems)


def check_at(value, path, problems):
    conditions = value if isinstance(value, list) else [value]
    for i, at in enumerate(conditions):
        where = "%s.at" % path if not isinstance(value, list) else "%s.at[%d]" % (path, i)
        if not isinstance(at, dict) or set(at) != {"axis", "value"}:
            problems.append('%s must be {"axis": "x"|"y"|"z", "value": "max"|"min"|number}' % where)
            continue
        if not isinstance(at["axis"], str) or at["axis"].lower() not in ("x", "y", "z"):
            problems.append("%s.axis must be x, y or z" % where)
        if at["value"] not in ("max", "min") and not is_type(at["value"], "number"):
            problems.append("%s.value must be max, min or a number" % where)


PICK_KINDS = ("plane", "axis", "origin", "face", "edge", "vertex", "construct")


def check_pick(spec, path, problems, kinds=PICK_KINDS):
    """A pick of inspect_ops (plane / axis / origin / face / edge / vertex / construct)."""
    if not isinstance(spec, dict):
        problems.append("%s must be a pick object (%s)" % (path, ", ".join(kinds)))
        return
    found = [k for k in kinds if k in spec]
    extra = [k for k in spec if k not in kinds]
    if len(found) != 1 or extra:
        problems.append("%s must have exactly one of %s" % (path, ", ".join(kinds)))
        return
    kind = found[0]
    value = spec[kind]
    if kind == "face":
        check_selector(value, path + ".face", "faces", problems)
    elif kind == "edge":
        check_selector(value, path + ".edge", "edges", problems)
    elif kind == "origin" and value is not True:
        problems.append("%s.origin must be true" % path)
    elif kind == "plane" and value not in PLANES:
        problems.append("%s.plane must be XY, XZ or YZ" % path)
    elif kind == "axis" and value not in AXES:
        problems.append("%s.axis must be X, Y or Z" % path)
    elif kind == "vertex" and not (
        isinstance(value, list) and len(value) == 3 and all(is_type(v, "number") for v in value)
    ):
        problems.append("%s.vertex must be [x, y, z]" % path)
    elif kind == "construct" and not isinstance(value, str):
        problems.append("%s.construct must be the id of a construction step" % path)


def check_body_pick(spec, path, problems):
    """A pick of direct_ops: origin name, {face|edge|vertex: sel, of}, {body: id}."""
    if isinstance(spec, str):
        if spec not in PLANES + AXES:
            problems.append("%s must be XY, XZ, YZ, X, Y, Z or a pick object" % path)
        return
    if not isinstance(spec, dict):
        problems.append("%s must be an origin name or a pick object" % path)
        return
    kinds = [k for k in ("face", "edge", "vertex", "body") if k in spec]
    if len(kinds) != 1 or set(spec) - {"face", "edge", "vertex", "body", "of"}:
        problems.append(
            "%s must have exactly one of face, edge, vertex, body (and maybe of)" % path
        )
        return
    kind = kinds[0]
    if kind == "body":
        if not isinstance(spec["body"], str):
            problems.append("%s.body must be a step id" % path)
        if "of" in spec:
            problems.append("%s: a body pick takes no of" % path)
        return
    if kind == "vertex":
        if not isinstance(spec["vertex"], dict) or set(spec["vertex"]) - {"at"}:
            problems.append('%s.vertex takes only "at" conditions' % path)
        elif "at" in spec["vertex"]:
            check_at(spec["vertex"]["at"], path + ".vertex", problems)
    else:
        check_selector(spec[kind], "%s.%s" % (path, kind), kind + "s", problems)
    if "of" in spec and not isinstance(spec["of"], str):
        problems.append("%s.of must be a step id" % path)


def check_curves(spec, path, problems):
    """A curves spec (sweep_loft_ops.curves_of)."""
    if isinstance(spec, str):
        if not spec.strip():
            problems.append("%s must not be empty" % path)
        return
    if not isinstance(spec, dict):
        problems.append("%s must be a sketch id or a curve pick object" % path)
        return
    if "edge" in spec:
        if set(spec) != {"edge"}:
            problems.append('%s: an edge pick is {"edge": selector} alone' % path)
        check_selector(spec["edge"], path + ".edge", "edges", problems)
        return
    if "sketch" not in spec or "at" not in spec:
        problems.append('%s must be {"sketch": id, "at": [x, y]} or {"edge": selector}' % path)
        return
    if set(spec) - {"sketch", "at", "chain"}:
        problems.append("%s takes only sketch, at and chain" % path)
    at = spec["at"]
    points = at if (isinstance(at, list) and at and isinstance(at[0], list)) else [at]
    for point in points:
        if not (
            isinstance(point, list) and len(point) == 2 and all(is_type(v, "number") for v in point)
        ):
            problems.append("%s.at must be [x, y] or a list of [x, y] points" % path)
            break
    if "chain" in spec and not isinstance(spec["chain"], bool):
        problems.append("%s.chain must be true or false" % path)


def check_plane_or_face(spec, path, problems, allow_construct=False):
    """ "XY" / "XZ" / "YZ" or {"face": selector}."""
    if isinstance(spec, str):
        if spec not in PLANES:
            problems.append('%s must be XY, XZ, YZ or {"face": selector}' % path)
        return
    if not isinstance(spec, dict) or set(spec) != {"face"}:
        problems.append('%s must be XY, XZ, YZ or {"face": selector}' % path)
        return
    check_selector(spec["face"], path + ".face", "faces", problems)


def check_axis_or_pick(spec, path, problems, keys=("edge", "face")):
    """ "X" / "Y" / "Z" or {"edge": sel} / {"face": sel} (pattern directions and axes)."""
    if isinstance(spec, str):
        if spec not in AXES:
            problems.append("%s must be X, Y, Z or a pick object" % path)
        return
    if not isinstance(spec, dict) or len(spec) != 1 or list(spec)[0] not in keys:
        problems.append(
            "%s must be X, Y, Z or one of %s"
            % (path, ", ".join('{"%s": selector}' % k for k in keys))
        )
        return
    key = list(spec)[0]
    check_selector(spec[key], "%s.%s" % (path, key), key + "s", problems)


NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def exactly_one(args, keys, problems, what=None):
    found = [k for k in keys if k in args]
    if len(found) != 1:
        problems.append(
            "give exactly one of %s%s" % (", ".join(keys), (" (%s)" % what) if what else "")
        )
    return found[0] if len(found) == 1 else None


def at_most_one(args, keys, problems):
    found = [k for k in keys if k in args]
    if len(found) > 1:
        problems.append("give only one of %s" % ", ".join(keys))
