# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI tools: one list that both the MCP server (sciforge_mcp.py, for AI apps such as
Claude Desktop) and the built-in chat panel offer, so every AI sees the same tools with
the same arguments (docs/sciforge/dev/briefs/home-cloud-ai.md, section 4.2).

Each tool has a name, a title, a description written for an AI model (what it does, mm and
degrees, how to point at faces and edges), a JSON Schema for its arguments and a flag that
says whether it changes the design (read-only tools run without asking).

The design-changing tools turn into design steps, the JSON language of the golden models
(SciForgeTests/golden/README.md): the bridge runs those steps with sciforge/ai/ops/, the
same code the 434 golden models prove. Tools that are not steps (get_design, screenshot,
measure, undo, redo, save, export) are done by the bridge itself.

The schemas use a small subset of JSON Schema 2020-12 (type, properties, required,
additionalProperties false, enum, items, minItems, maxItems, minimum, maximum,
exclusiveMinimum, default, description), checked here by a small hand-written validator
so nothing has to be installed. validate() adds the checks a schema cannot say ("give
distance or through_all") and answers in plain sentences an AI can act on.

Pure Python: no FreeCAD, no Qt.
"""

import copy
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
    "a disc area)."
)

_NUMBER = {"type": "number"}
_POINT2 = {"type": "array", "items": _NUMBER, "minItems": 2, "maxItems": 2}
_VECTOR3 = {"type": "array", "items": _NUMBER, "minItems": 3, "maxItems": 3}
_POSITIVE = {"type": "number", "exclusiveMinimum": 0}


def _numbers(n, description):
    return {
        "type": "array",
        "items": _NUMBER,
        "minItems": n,
        "maxItems": n,
        "description": description,
    }


def _selector(description):
    return {
        "type": "object",
        "description": description + " " + SELECTOR_HELP,
        "properties": {
            "type": {"type": "string", "enum": sorted(set(EDGE_TYPES + FACE_TYPES))},
            "normal": dict(_VECTOR3, description="[x, y, z] outward normal of flat faces"),
            "parallel": dict(_VECTOR3, description="[x, y, z] direction of straight edges"),
            "along": dict(
                _VECTOR3,
                description="[x, y, z]: faces running along it (the side walls of a part "
                "extruded that way)",
            ),
            "radius": dict(_POSITIVE, description="radius in mm"),
            "on_faces": {"type": "object", "description": "a face selector"},
            "not_on_faces": {"type": "object", "description": "a face selector"},
            "at": {
                "description": '{"axis": "x"|"y"|"z", "value": "max"|"min"|number} or a list '
                "of them"
            },
            "all": {"type": "boolean"},
            "count": {"type": "integer", "minimum": 1},
            "any_of": {"type": "array", "items": {"type": "object"}, "minItems": 1},
        },
        "additionalProperties": False,
    }


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
        "name": {"type": "string", "description": "names its dimensions, e.g. <name>.width"},
    },
    "additionalProperties": False,
}

_PICK = {
    "type": "object",
    "description": 'One of {"plane": "XY"|"XZ"|"YZ"}, {"axis": "X"|"Y"|"Z"}, {"origin": true}, '
    '{"face": face selector}, {"edge": edge selector} or {"vertex": [x, y, z]} (a corner of the '
    "part). Face and edge selectors must pick exactly one element.",
    "properties": {
        "plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
        "axis": {"type": "string", "enum": ["X", "Y", "Z"]},
        "origin": {"type": "boolean"},
        "face": {"type": "object"},
        "edge": {"type": "object"},
        "vertex": _VECTOR3,
    },
    "additionalProperties": False,
}

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


def _schema(properties, required=()):
    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = list(required)
    return schema


TOOLS = [
    {
        "name": "get_design",
        "title": "Get design",
        "description": "Describe the open SciForge design: its bodies (volume in mm3, "
        "bounding box in mm), the timeline steps with their ids (use these ids in profile, "
        "sketch and features arguments), the user parameters and the sketches with their "
        "areas. Call it before changing a design and after each change to check the result. "
        + UNITS,
        "input_schema": _schema({}),
        "changes_design": False,
    },
    {
        "name": "screenshot",
        "title": "Screenshot",
        "description": "Take a picture (PNG) of the design as SciForge shows it, to see what "
        "you built. view picks the camera: iso (default), front, back, top, bottom, left or "
        "right.",
        "input_schema": _schema(
            {
                "view": {
                    "type": "string",
                    "enum": ["iso", "front", "back", "top", "bottom", "left", "right"],
                    "default": "iso",
                },
                "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 1024},
                "height": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 768},
            }
        ),
        "changes_design": False,
    },
    {
        "name": "measure",
        "title": "Measure",
        "description": "Measure between two picks a and b of the current body or the origin: "
        "the minimum distance (mm) and, where it makes sense, the angle (degrees), like "
        "SciForge's Measure tool. " + _PICK["description"] + " " + SELECTOR_HELP,
        "input_schema": _schema({"a": _PICK, "b": _PICK}, ["a", "b"]),
        "changes_design": False,
    },
    {
        "name": "create_sketch",
        "title": "Create sketch",
        "description": "Create a sketch with closed shapes (and lines) in it, ready for "
        "extrude, revolve or hole. It becomes one timeline step; its id is the profile for "
        "the next tools. " + SKETCH_HELP + " " + GEOMETRY_HELP + " " + UNITS,
        "input_schema": _schema(
            {
                "plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
                "offset": dict(_NUMBER, default=0, description="mm along the plane's normal"),
                "face": _selector("Instead of plane: the flat face to sketch on (one face)."),
                "geometry": {
                    "type": "array",
                    "items": _GEOMETRY_ITEM,
                    "minItems": 1,
                    "description": GEOMETRY_HELP,
                },
            },
            ["geometry"],
        ),
        "changes_design": True,
    },
    {
        "name": "extrude",
        "title": "Extrude",
        "description": "Extrude a sketch's areas into a solid (SciForge's Extrude). distance "
        "goes along the sketch normal; flip: true goes the other way, for cuts too: a cut "
        "from a sketch lying on top of the part needs flip: true. regions picks some areas by "
        "a point inside each ([x, y] in sketch coordinates); without it every area is used. "
        "direction one_side (default), symmetric (distance is the whole length, half on each "
        "side) or two_sides (distance one way, distance2 the other). through_all goes through "
        "the whole part instead of a distance. taper in degrees. " + UNITS,
        "input_schema": _schema(
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
            },
            ["profile"],
        ),
        "changes_design": True,
    },
    {
        "name": "revolve",
        "title": "Revolve",
        "description": "Revolve a sketch's areas around an axis (SciForge's Revolve). axis: "
        "X, Y or Z (origin axes) or sketch_h / sketch_v (the sketch's own horizontal or "
        "vertical axis). angle in degrees, 360 (default) for a full turn. regions picks areas "
        "by a point inside each, as for extrude. operation auto (default) lets SciForge "
        "choose like its Revolve dialog does.",
        "input_schema": _schema(
            {
                "profile": {"type": "string", "description": "id of a create_sketch step"},
                "regions": {"type": "array", "items": _POINT2, "minItems": 1},
                "axis": {"type": "string", "enum": ["X", "Y", "Z", "sketch_h", "sketch_v"]},
                "angle": {"type": "number", "exclusiveMinimum": 0, "maximum": 360, "default": 360},
                "operation": {
                    "type": "string",
                    "enum": ["auto", "join", "cut", "intersect", "new_body"],
                    "default": "auto",
                },
            },
            ["profile", "axis"],
        ),
        "changes_design": True,
    },
    {
        "name": "fillet",
        "title": "Fillet",
        "description": "Round edges of the current body with a radius (SciForge's Fillet). "
        "Pick them with edges (an edge selector), faces (every sharp edge around the faces a "
        "face selector picks) and/or features (the edges earlier steps made, by step id). "
        "Errors such as 'the radius is too big for this edge' come back as sentences. " + UNITS,
        "input_schema": _schema(
            {
                "edges": _selector("The edges to round."),
                "faces": _selector("Round every sharp edge around these faces."),
                "features": _FEATURES,
                "radius": _POSITIVE,
            },
            ["radius"],
        ),
        "changes_design": True,
    },
    {
        "name": "chamfer",
        "title": "Chamfer",
        "description": "Bevel edges of the current body (SciForge's Chamfer). distance alone: "
        "equal distances; distance and distance2: two distances (flip swaps the sides); "
        "distance and angle: a distance and an angle in degrees. Pick edges as for fillet. "
        + UNITS,
        "input_schema": _schema(
            {
                "edges": _selector("The edges to bevel."),
                "faces": _selector("Bevel every sharp edge around these faces."),
                "features": _FEATURES,
                "distance": _POSITIVE,
                "distance2": _POSITIVE,
                "angle": {"type": "number", "exclusiveMinimum": 0, "maximum": 89},
                "flip": {"type": "boolean", "default": False},
            },
            ["distance"],
        ),
        "changes_design": True,
    },
    {
        "name": "hole",
        "title": "Hole",
        "description": "Drill holes into the part (SciForge's Hole). First create_sketch on "
        "the face where the holes start (for example plane XY with offset = the top's height) "
        "with a small circle at each hole centre; the holes go at the circles' centres, "
        "whatever their size. Give depth or through_all. Optional counterbore {diameter, "
        "depth} or countersink {diameter, angle} (angle in degrees, default 90). " + UNITS,
        "input_schema": _schema(
            {
                "sketch": {"type": "string", "description": "id of the sketch with the centres"},
                "diameter": _POSITIVE,
                "depth": _POSITIVE,
                "through_all": {"type": "boolean", "default": False},
                "counterbore": _schema(
                    {"diameter": _POSITIVE, "depth": _POSITIVE}, ["diameter", "depth"]
                ),
                "countersink": _schema(
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
            },
            ["sketch", "diameter"],
        ),
        "changes_design": True,
    },
    {
        "name": "pattern",
        "title": "Pattern",
        "description": "Repeat earlier steps (features: their ids, e.g. a cut or a hole). "
        "kind rectangular: count copies spaced by spacing (mm) along direction X, Y or Z, "
        "optionally a second row with direction2, count2, spacing2. kind circular: count "
        "copies around axis X, Y or Z over angle degrees (default 360). Counts include the "
        "original.",
        "input_schema": _schema(
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
        "changes_design": True,
    },
    {
        "name": "shell",
        "title": "Shell",
        "description": "Hollow the current body out with a wall thickness (SciForge's Shell). "
        'faces: the faces to remove (open), a face selector, e.g. the top face {"normal": '
        '[0, 0, 1], "count": 1}. direction inside (default: the outside stays where it is) '
        "or outside. " + UNITS,
        "input_schema": _schema(
            {
                "faces": _selector("The faces to remove."),
                "thickness": _POSITIVE,
                "direction": {"type": "string", "enum": ["inside", "outside"], "default": "inside"},
            },
            ["faces", "thickness"],
        ),
        "changes_design": True,
    },
    {
        "name": "set_parameter",
        "title": "Set parameter",
        "description": "Create or change a user parameter (SciForge's Change Parameters). "
        'value is a number or an expression using other parameters, e.g. "width / 4". '
        "unit: mm (default), deg or empty for a plain number. Everything that uses the "
        "parameter updates.",
        "input_schema": _schema(
            {
                "name": {"type": "string", "description": "letters, digits and _"},
                "value": {"type": ["number", "string"]},
                "unit": {"type": "string", "default": "mm"},
            },
            ["name", "value"],
        ),
        "changes_design": True,
    },
    {
        "name": "undo",
        "title": "Undo",
        "description": "Undo the last change in SciForge (each AI change is one undo step).",
        "input_schema": _schema({}),
        "changes_design": True,
    },
    {
        "name": "redo",
        "title": "Redo",
        "description": "Redo the change undo took back.",
        "input_schema": _schema({}),
        "changes_design": True,
    },
    {
        "name": "save",
        "title": "Save",
        "description": "Save the design. Without path it is saved where it is (a new design "
        "asks for a place in SciForge). With path (a full path ending in .FCStd) it is saved "
        "there; saving over another existing file must be confirmed by the person in SciForge.",
        "input_schema": _schema({"path": {"type": "string"}}),
        "changes_design": False,
        "writes_files": True,
        "confirm_overwrite": True,
    },
    {
        "name": "export",
        "title": "Export",
        "description": "Export the design's bodies to a file: format step (.step / .stp), stl "
        "or 3mf (for 3D printing). path is a full path; replacing an existing file must be "
        "confirmed by the person in SciForge.",
        "input_schema": _schema(
            {
                "format": {"type": "string", "enum": ["step", "stl", "3mf"]},
                "path": {"type": "string"},
            },
            ["format", "path"],
        ),
        "changes_design": False,
        "writes_files": True,
        "confirm_overwrite": True,
    },
]

for _tool in TOOLS:
    _tool.setdefault("writes_files", False)
    _tool.setdefault("confirm_overwrite", False)
del _tool

_BY_NAME = {tool["name"]: tool for tool in TOOLS}
TOOL_NAMES = tuple(_BY_NAME)


def tool(name):
    """The tool dict for this name, or None."""
    return _BY_NAME.get(name)


def mcp_tools():
    """The tools in MCP "tools/list" shape."""
    result = []
    for item in TOOLS:
        result.append(
            {
                "name": item["name"],
                "title": item["title"],
                "description": item["description"],
                "inputSchema": copy.deepcopy(item["input_schema"]),
                "annotations": {
                    "title": item["title"],
                    "readOnlyHint": not (item["changes_design"] or item["writes_files"]),
                    "destructiveHint": False,
                    "openWorldHint": False,
                },
            }
        )
    return result


# -- validation -------------------------------------------------------------------------
_TYPE_WORDS = {
    "number": "a number",
    "integer": "a whole number",
    "string": "text",
    "boolean": "true or false",
    "object": "an object",
    "array": "a list",
    "null": "null",
}


def _is_type(value, kind):
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


def _fmt(number):
    return "%g" % number


def _check(schema, value, path, problems):
    """Check value against the schema subset; add a plain sentence per problem."""
    name = path or "the arguments"
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if not any(_is_type(value, kind) for kind in kinds):
            words = " or ".join(_TYPE_WORDS.get(kind, kind) for kind in kinds)
            problems.append("%s must be %s" % (name, words))
            return
    if "enum" in schema and value not in schema["enum"]:
        problems.append("%s must be one of: %s" % (name, ", ".join(str(v) for v in schema["enum"])))
        return
    if _is_type(value, "number"):
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            problems.append(
                "%s must be a number above %s" % (name, _fmt(schema["exclusiveMinimum"]))
            )
        if "minimum" in schema and value < schema["minimum"]:
            problems.append("%s must be at least %s" % (name, _fmt(schema["minimum"])))
        if "maximum" in schema and value > schema["maximum"]:
            problems.append("%s must be at most %s" % (name, _fmt(schema["maximum"])))
    if isinstance(value, list):
        low, high = schema.get("minItems"), schema.get("maxItems")
        if low is not None and low == high and len(value) != low:
            problems.append("%s must have exactly %d items" % (name, low))
        elif low is not None and len(value) < low:
            problems.append(
                "%s must have at least %d item%s" % (name, low, "" if low == 1 else "s")
            )
        elif high is not None and len(value) > high:
            problems.append("%s must have at most %d items" % (name, high))
        if "items" in schema:
            for i, item in enumerate(value):
                _check(schema["items"], item, "%s[%d]" % (path, i), problems)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        prefix = path + "." if path else ""
        for key in schema.get("required", []):
            if key not in value:
                problems.append("%s%s is missing" % (prefix, key))
        for key, item in value.items():
            if key in props:
                _check(props[key], item, prefix + key, problems)
            elif schema.get("additionalProperties") is False:
                where = (" in %s" % path) if path else ""
                problems.append("%s is not a known argument%s" % (key, where))


def _check_selector(spec, path, element, problems):
    """The selector rules of sciforge/ai/ops/selectors.py, as sentences."""
    if not isinstance(spec, dict):
        problems.append("%s must be a selector object" % path)
        return
    for key in spec:
        if key not in SELECTOR_KEYS:
            problems.append(
                "%s.%s is not a selector filter (use %s)" % (path, key, ", ".join(SELECTOR_KEYS))
            )
    if "count" in spec and not (_is_type(spec["count"], "integer") and spec["count"] >= 1):
        problems.append("%s.count must be a whole number of at least 1" % path)
    if "any_of" in spec:
        subs = spec["any_of"]
        if not isinstance(subs, list) or not subs:
            problems.append("%s.any_of must be a non-empty list of selectors" % path)
            return
        for i, sub in enumerate(subs):
            _check_selector(sub, "%s.any_of[%d]" % (path, i), element, problems)
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
                isinstance(vec, list) and len(vec) == 3 and all(_is_type(v, "number") for v in vec)
            ):
                problems.append("%s.%s must be [x, y, z]" % (path, key))
            elif all(abs(v) < 1e-12 for v in vec):
                problems.append("%s.%s must not be [0, 0, 0]" % (path, key))
    if "radius" in spec and not (_is_type(spec["radius"], "number") and spec["radius"] > 0):
        problems.append("%s.radius must be a number above 0" % path)
    for key in ("on_faces", "not_on_faces"):
        if key in spec:
            if element != "edges":
                problems.append("%s.%s only applies to edges" % (path, key))
            _check_selector(spec[key], "%s.%s" % (path, key), "faces", problems)
    if "on_faces" in spec and "not_on_faces" in spec:
        problems.append("%s: give on_faces or not_on_faces, not both" % path)
    if "at" in spec:
        conditions = spec["at"] if isinstance(spec["at"], list) else [spec["at"]]
        for i, at in enumerate(conditions):
            where = "%s.at" % path if not isinstance(spec["at"], list) else "%s.at[%d]" % (path, i)
            if not isinstance(at, dict) or set(at) != {"axis", "value"}:
                problems.append(
                    '%s must be {"axis": "x"|"y"|"z", "value": "max"|"min"|number}' % where
                )
                continue
            if not isinstance(at["axis"], str) or at["axis"].lower() not in ("x", "y", "z"):
                problems.append("%s.axis must be x, y or z" % where)
            if at["value"] not in ("max", "min") and not _is_type(at["value"], "number"):
                problems.append("%s.value must be max, min or a number" % where)


def _check_pick(pick, path, problems):
    if not isinstance(pick, dict):
        return
    kinds = [k for k in ("plane", "axis", "origin", "face", "edge", "vertex") if k in pick]
    if len(kinds) != 1:
        problems.append(
            "%s must have exactly one of plane, axis, origin, face, edge, vertex" % path
        )
        return
    if kinds[0] == "face":
        _check_selector(pick["face"], path + ".face", "faces", problems)
    elif kinds[0] == "edge":
        _check_selector(pick["edge"], path + ".edge", "edges", problems)
    elif kinds[0] == "origin" and pick["origin"] is not True:
        problems.append("%s.origin must be true" % path)


_GEOMETRY_KINDS = ("rect", "center_rect", "circle", "polyline", "polygon", "slot", "line")
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _extra_create_sketch(args, problems):
    if ("plane" in args) == ("face" in args):
        problems.append("give either plane (XY, XZ or YZ) or face (a selector), not both")
    if "face" in args:
        _check_selector(args["face"], "face", "faces", problems)
    geometry = args.get("geometry")
    if not isinstance(geometry, list):
        return
    for i, item in enumerate(geometry):
        if not isinstance(item, dict):
            continue
        where = "geometry[%d]" % i
        kinds = [k for k in _GEOMETRY_KINDS if k in item]
        if len(kinds) != 1:
            problems.append("%s must have exactly one of %s" % (where, ", ".join(_GEOMETRY_KINDS)))
            continue
        kind = kinds[0]
        value = item[kind]
        if not isinstance(value, list) or not all(_is_type(v, "number") for v in value):
            continue  # polygon / polyline, or already reported by the schema check
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
        if "name" in item and isinstance(item["name"], str) and not _NAME.match(item["name"]):
            problems.append("%s.name may only use letters, digits and _" % where)


def _extra_extrude(args, problems):
    through = args.get("through_all") is True
    if through and "distance" in args:
        problems.append("give distance or through_all, not both")
    if not through and "distance" not in args:
        problems.append("distance is missing (or set through_all to true)")
    if args.get("direction") == "two_sides":
        if "distance2" not in args:
            problems.append("distance2 is missing: direction two_sides needs it")
    elif "distance2" in args:
        problems.append("distance2 is only used with direction two_sides")


def _extra_blend(args, problems):
    if not ({"edges", "faces", "features"} & set(args)):
        problems.append("pick what to change with edges, faces or features")
    if "edges" in args:
        _check_selector(args["edges"], "edges", "edges", problems)
    if "faces" in args:
        _check_selector(args["faces"], "faces", "faces", problems)


def _extra_chamfer(args, problems):
    _extra_blend(args, problems)
    if "distance2" in args and "angle" in args:
        problems.append("give distance2 or angle, not both")
    if args.get("flip") and "distance2" not in args:
        problems.append("flip only applies with distance2 (two distances)")


def _extra_hole(args, problems):
    through = args.get("through_all") is True
    if through == ("depth" in args):
        problems.append("give either depth or through_all: true")
    if "counterbore" in args and "countersink" in args:
        problems.append("give counterbore or countersink, not both")
    diameter = args.get("diameter")
    for key in ("counterbore", "countersink"):
        head = args.get(key)
        if (
            isinstance(head, dict)
            and _is_type(head.get("diameter"), "number")
            and _is_type(diameter, "number")
            and head["diameter"] <= diameter
        ):
            problems.append("%s.diameter must be bigger than the hole's diameter" % key)


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


def _extra_set_parameter(args, problems):
    name = args.get("name")
    if isinstance(name, str) and not _NAME.match(name):
        problems.append("name must start with a letter and use only letters, digits and _")
    value = args.get("value")
    if isinstance(value, str) and not value.strip():
        problems.append("value must not be empty")


def _extra_save(args, problems):
    path = args.get("path")
    if isinstance(path, str) and not path.lower().endswith(".fcstd"):
        problems.append("path must end in .FCStd")


_EXTENSIONS = {"step": (".step", ".stp"), "stl": (".stl",), "3mf": (".3mf",)}


def _extra_export(args, problems):
    path, fmt = args.get("path"), args.get("format")
    if isinstance(path, str) and fmt in _EXTENSIONS:
        if not path.strip():
            problems.append("path must not be empty")
        elif not path.lower().endswith(_EXTENSIONS[fmt]):
            problems.append(
                "path must end in %s for format %s" % (" or ".join(_EXTENSIONS[fmt]), fmt)
            )


def _extra_measure(args, problems):
    for key in ("a", "b"):
        _check_pick(args.get(key), key, problems)


def _extra_shell(args, problems):
    _check_selector(args.get("faces"), "faces", "faces", problems)


_EXTRA = {
    "create_sketch": _extra_create_sketch,
    "extrude": _extra_extrude,
    "fillet": _extra_blend,
    "chamfer": _extra_chamfer,
    "hole": _extra_hole,
    "pattern": _extra_pattern,
    "set_parameter": _extra_set_parameter,
    "save": _extra_save,
    "export": _extra_export,
    "measure": _extra_measure,
    "shell": _extra_shell,
}


def validate(tool_name, args):
    """A list of plain-sentence problems with these arguments (empty: they are fine)."""
    item = _BY_NAME.get(tool_name)
    if item is None:
        return ["there is no tool called %r (tools: %s)" % (tool_name, ", ".join(TOOL_NAMES))]
    if args is None:
        args = {}
    problems = []
    _check(item["input_schema"], args, "", problems)
    if isinstance(args, dict) and tool_name in _EXTRA and not problems:
        _EXTRA[tool_name](args, problems)
    return problems


# -- design steps ---------------------------------------------------------------------
def _int(value):
    return int(value) if _is_type(value, "integer") else value


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


def to_steps(tool_name, args, step_id):
    """The design steps (golden step language) a valid call makes; [] for the tools the
    bridge does itself. Call validate() first: this assumes the arguments are valid."""
    if tool_name not in _BY_NAME:
        raise ValueError("there is no tool called %r" % tool_name)
    a = args or {}
    if tool_name == "create_sketch":
        step = {"op": "sketch", "id": step_id}
        if "plane" in a:
            step["plane"] = a["plane"]
        else:
            step["face"] = copy.deepcopy(a["face"])
        if a.get("offset"):
            step["offset"] = a["offset"]
        step["geometry"] = _copy_geometry(a["geometry"])
        return [step]
    if tool_name == "extrude":
        step = {"op": "extrude", "id": step_id, "profile": a["profile"]}
        if "regions" in a:
            step["regions"] = copy.deepcopy(a["regions"])
        if a.get("through_all"):
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
        return [step]
    if tool_name == "revolve":
        axis = a["axis"]
        if axis in ("sketch_h", "sketch_v"):
            axis = {"sketch": a["profile"], "axis": "H" if axis == "sketch_h" else "V"}
        step = {"op": "sf_revolve", "id": step_id, "profile": a["profile"], "axis": axis}
        if "regions" in a:
            step["regions"] = copy.deepcopy(a["regions"])
        angle = a.get("angle", 360)
        if angle >= 360:
            step["type"] = "full"
        else:
            step["type"] = "angle"
            step["angle"] = angle
        step["operation"] = a.get("operation", "auto")
        return [step]
    if tool_name == "fillet":
        return [_blend_refs({"op": "blend_fillet", "id": step_id, "radius": a["radius"]}, a)]
    if tool_name == "chamfer":
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
    if tool_name == "hole":
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
    if tool_name == "pattern":
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
    if tool_name == "shell":
        return [
            {
                "op": "shell",
                "id": step_id,
                "faces": copy.deepcopy(a["faces"]),
                "thickness": a["thickness"],
                "direction": a.get("direction", "inside"),
            }
        ]
    if tool_name == "set_parameter":
        step = {"op": "parameter", "name": a["name"], "value": a["value"]}
        if "unit" in a:
            step["unit"] = a["unit"]
        return [step]
    return []


def step_title(tool_name, args):
    """The undo / timeline title of a call, e.g. "AI: Extrude 10 mm"."""
    a = args if isinstance(args, dict) else {}
    item = _BY_NAME.get(tool_name)
    base = item["title"] if item else str(tool_name)

    def mm(key):
        value = a.get(key)
        return " %s mm" % _fmt(value) if _is_type(value, "number") else ""

    if tool_name == "create_sketch":
        where = a.get("plane") or ("face" if "face" in a else "")
        return "AI: Sketch" + (" on %s" % where if where else "")
    if tool_name == "extrude":
        if a.get("through_all"):
            return "AI: Extrude through all"
        return "AI: Extrude" + mm("distance")
    if tool_name == "revolve":
        angle = a.get("angle", 360)
        return (
            "AI: Revolve %s degrees" % _fmt(angle) if _is_type(angle, "number") else "AI: Revolve"
        )
    if tool_name == "fillet":
        return "AI: Fillet" + mm("radius")
    if tool_name == "chamfer":
        return "AI: Chamfer" + mm("distance")
    if tool_name == "hole":
        return "AI: Hole" + mm("diameter")
    if tool_name == "shell":
        return "AI: Shell" + mm("thickness")
    if tool_name == "pattern":
        kind = "Circular" if a.get("kind") == "circular" else "Rectangular"
        count = a.get("count")
        return "AI: %s pattern" % kind + (" x%d" % int(count) if _is_type(count, "integer") else "")
    if tool_name == "set_parameter":
        if "name" in a and "value" in a:
            return "AI: Parameter %s = %s" % (a["name"], a["value"])
        return "AI: Parameter"
    if tool_name == "export" and a.get("format"):
        return "AI: Export %s" % str(a["format"]).upper()
    return "AI: " + base
