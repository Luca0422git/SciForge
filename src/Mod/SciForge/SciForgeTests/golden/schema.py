# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model file format and validation. Pure Python (no FreeCAD), unit tested.

A golden model is a JSON file describing a part as a list of modeling steps,
the way a Fusion user would build it, plus the measurements the result must
have. Example:

    {
      "id": "bracket_basic",
      "title": "L bracket with fillet",
      "tags": ["bracket", "fillet"],
      "steps": [
        {"op": "sketch", "id": "s1", "plane": "XY",
         "geometry": [{"rect": [0, 0, 40, 20], "name": "base"}]},
        {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10}
      ],
      "expect": {"volume": 8000, "faces": 6,
                 "bbox": [0, 0, 0, 40, 20, 10], "source": "analytic"}
    }

See golden/README.md for every operation and option.
"""

PLANES = ("XY", "XZ", "YZ")
OPERATIONS = ("new_body", "join", "cut")
SOURCES = ("analytic", "baseline-freecad-1.1.4", "fusion")

# op -> (required keys, optional keys)
STEP_KEYS = {
    "sketch": ({"id", "plane", "geometry"}, {"offset", "comment"}),
    "extrude": (
        {"id", "profile"},
        {"distance", "distance2", "operation", "direction", "extent", "taper", "flip", "comment"},
    ),
    "revolve": ({"id", "profile", "axis"}, {"angle", "operation", "comment"}),
    "fillet": ({"id", "edges", "radius"}, {"comment"}),
    "chamfer": ({"id", "edges", "distance"}, {"distance2", "angle", "comment"}),
    "shell": ({"id", "faces", "thickness"}, {"direction", "comment"}),
    "hole": (
        {"id", "sketch", "diameter"},
        {"depth", "through_all", "counterbore", "countersink", "comment"},
    ),
    "pattern_rect": (
        {"id", "features", "direction", "count", "spacing"},
        {"direction2", "count2", "spacing2", "comment"},
    ),
    "pattern_circ": ({"id", "features", "axis", "count"}, {"angle", "comment"}),
    "mirror": ({"id", "features", "plane"}, {"comment"}),
    "press_pull": ({"id", "distance"}, {"faces", "edges", "fillet_face", "comment"}),
    "edit": ({"target"}, {"set", "constraint", "value", "comment"}),
    "check": ({"expect"}, {"comment"}),
}

GEOMETRY_KINDS = ("rect", "center_rect", "circle", "polyline", "polygon", "slot")
EXPECT_KEYS = {
    "volume",
    "area",
    "bbox",
    "faces",
    "edges",
    "solids",
    "valid",
    "source",
    "rel_tol",
    "abs_tol",
    "note",
}
AXES = ("X", "Y", "Z")


class ModelError(ValueError):
    """A golden-model file is malformed. The message says where and why."""


def _fail(where, msg):
    raise ModelError("%s: %s" % (where, msg))


def _check_number(where, value, positive=False):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        _fail(where, "expected a number, got %r" % (value,))
    if positive and value <= 0:
        _fail(where, "must be > 0, got %r" % (value,))


def _check_expect(where, expect):
    if not isinstance(expect, dict):
        _fail(where, "'expect' must be an object")
    unknown = set(expect) - EXPECT_KEYS
    if unknown:
        _fail(where, "unknown expect keys %s" % sorted(unknown))
    measured = set(expect) & {"volume", "area", "bbox", "faces", "edges", "solids"}
    if not measured:
        _fail(where, "'expect' must check at least one of volume/area/bbox/faces/edges/solids")
    if "source" not in expect:
        _fail(
            where,
            "'expect.source' is required (one of %s): where the numbers came from" % (SOURCES,),
        )
    if expect["source"] not in SOURCES:
        _fail(where, "'expect.source' must be one of %s" % (SOURCES,))
    if "bbox" in expect:
        bbox = expect["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 6:
            _fail(where, "'bbox' must be [xmin, ymin, zmin, xmax, ymax, zmax]")
        for v in bbox:
            _check_number(where + ".bbox", v)
    for key in ("volume", "area"):
        if key in expect:
            _check_number(where + "." + key, expect[key], positive=True)
    for key in ("faces", "edges", "solids"):
        if key in expect and (not isinstance(expect[key], int) or expect[key] < 0):
            _fail(where, "'%s' must be a non-negative integer" % key)


def _check_geometry(where, geometry):
    if not isinstance(geometry, list) or not geometry:
        _fail(where, "'geometry' must be a non-empty list")
    for i, item in enumerate(geometry):
        here = "%s.geometry[%d]" % (where, i)
        if not isinstance(item, dict):
            _fail(here, "must be an object")
        kinds = [k for k in GEOMETRY_KINDS if k in item]
        if len(kinds) != 1:
            _fail(here, "must have exactly one of %s" % (GEOMETRY_KINDS,))
        kind = kinds[0]
        value = item[kind]
        if kind in ("rect", "center_rect"):
            if not isinstance(value, list) or len(value) != 4:
                _fail(here, "'%s' takes 4 numbers" % kind)
        elif kind == "circle":
            if not isinstance(value, list) or len(value) != 3:
                _fail(here, "'circle' takes [cx, cy, r]")
            _check_number(here + ".r", value[2], positive=True)
        elif kind == "polyline":
            if not isinstance(value, list) or len(value) < 3:
                _fail(here, "'polyline' takes at least 3 [x, y] points (it is always closed)")
        elif kind == "polygon":
            if not isinstance(value, dict) or not {"center", "radius", "sides"} <= set(value):
                _fail(here, "'polygon' takes {center, radius, sides}")
        elif kind == "slot":
            if not isinstance(value, list) or len(value) != 5:
                _fail(here, "'slot' takes [x1, y1, x2, y2, width]")


def validate(model):
    """Raise ModelError if the model is malformed; return the model otherwise."""
    if not isinstance(model, dict):
        raise ModelError("model must be a JSON object")
    where = model.get("id", "<no id>")
    for key in ("id", "title", "steps", "expect"):
        if key not in model:
            _fail(where, "missing '%s'" % key)
    unknown_top = set(model) - {
        "id",
        "title",
        "tags",
        "steps",
        "expect",
        "xfail",
        "upstream_bug",
        "comment",
    }
    if unknown_top:
        _fail(where, "unknown top-level keys %s" % sorted(unknown_top))
    for key in ("xfail", "upstream_bug"):
        if key in model and (not isinstance(model[key], str) or not model[key].strip()):
            _fail(where, "'%s' must be a non-empty explanation" % key)
    steps = model["steps"]
    if not isinstance(steps, list) or not steps:
        _fail(where, "'steps' must be a non-empty list")

    seen = {}
    for i, step in enumerate(steps):
        here = "%s.steps[%d]" % (where, i)
        if not isinstance(step, dict) or "op" not in step:
            _fail(here, "each step needs an 'op'")
        op = step["op"]
        if op not in STEP_KEYS:
            _fail(here, "unknown op %r (known: %s)" % (op, ", ".join(sorted(STEP_KEYS))))
        required, optional = STEP_KEYS[op]
        missing = required - set(step)
        if missing:
            _fail(here, "op %r is missing %s" % (op, sorted(missing)))
        unknown = set(step) - required - optional - {"op"}
        if unknown:
            _fail(here, "op %r does not take %s" % (op, sorted(unknown)))
        if "id" in step:
            if step["id"] in seen:
                _fail(here, "duplicate step id %r" % step["id"])
            seen[step["id"]] = op

        if op == "sketch":
            plane = step["plane"]
            if plane not in PLANES:
                _fail(here, "'plane' must be one of %s" % (PLANES,))
            _check_geometry(here, step["geometry"])
        if op in ("extrude", "revolve"):
            if seen.get(step["profile"]) != "sketch":
                _fail(here, "'profile' must name an earlier sketch step, got %r" % step["profile"])
            if step.get("operation", "join") not in OPERATIONS:
                _fail(here, "'operation' must be one of %s" % (OPERATIONS,))
        if op == "extrude":
            extent = step.get("extent", "distance")
            if extent not in ("distance", "through_all"):
                _fail(here, "'extent' must be 'distance' or 'through_all'")
            if extent == "distance":
                _check_number(here + ".distance", step.get("distance"), positive=True)
            if step.get("direction", "one_side") not in ("one_side", "symmetric", "two_sides"):
                _fail(here, "'direction' must be one_side, symmetric or two_sides")
            if step.get("direction") == "two_sides":
                _check_number(here + ".distance2", step.get("distance2"), positive=True)
        if op == "revolve" and step["axis"] not in AXES + ("sketch_h", "sketch_v"):
            _fail(here, "'axis' must be X, Y, Z, sketch_h or sketch_v")
        if op in ("fillet", "chamfer"):
            _check_number(here + ".size", step.get("radius", step.get("distance")), positive=True)
        if op == "press_pull":
            modes = [k for k in ("faces", "edges", "fillet_face") if k in step]
            if len(modes) != 1:
                _fail(here, "press_pull needs exactly one of faces, edges, fillet_face")
            _check_number(here + ".distance", step["distance"])
        if op == "shell":
            _check_number(here + ".thickness", step["thickness"], positive=True)
        if op == "hole" and seen.get(step["sketch"]) != "sketch":
            _fail(here, "'sketch' must name an earlier sketch step")
        if op in ("pattern_rect", "pattern_circ", "mirror"):
            for name in step["features"]:
                if name not in seen:
                    _fail(here, "'features' names unknown step %r" % name)
        if op == "edit":
            if step["target"] not in seen:
                _fail(here, "'target' names unknown step %r" % step["target"])
            if ("constraint" in step) != ("value" in step):
                _fail(here, "'constraint' and 'value' go together")
            if "set" not in step and "constraint" not in step:
                _fail(here, "edit needs 'set' or 'constraint'+'value'")
        if op == "check":
            _check_expect(here, step["expect"])

    _check_expect(where + ".expect", model["expect"])
    return model
