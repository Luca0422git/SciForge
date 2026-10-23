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
OPERATIONS = ("new_body", "join", "cut", "intersect")
EXTRUDE_EXTENTS = ("distance", "through_all", "to_object")
SOURCES = ("analytic", "baseline-freecad-1.1.4", "fusion")

# op -> (required keys, optional keys)
STEP_KEYS = {
    "sketch": ({"id", "geometry"}, {"plane", "face", "auto_project", "offset", "comment"}),
    "extrude": (
        {"id"},
        {
            "profile",
            "face",
            "distance",
            "distance2",
            "operation",
            "direction",
            "extent",
            "taper",
            "flip",
            "comment",
            # Fusion Extrude options (sciforge/extrude.py)
            "regions",
            "more_profiles",
            "measurement",
            "start",
            "start_offset",
            "start_from",
            "to",
            "extent2",
            "taper2",
            "to2",
            # Thin Extrude (sciforge/extrude.py, extrude_prism.py)
            "thin",
            "curves",
        },
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
    "parameter": ({"name", "value"}, {"unit", "comment"}),
    "edit": ({"target"}, {"set", "constraint", "value", "expressions", "comment"}),
    "check": ({"expect"}, {"comment"}),
    # SKETCH tab tools (golden/sketch_ops.py)
    "sketch_polygon": (
        {"sketch", "center", "point", "sides"},
        {"circumscribed", "diameter", "name", "comment"},
    ),
    "sketch_trim": ({"sketch", "points"}, {"comment"}),
    # Timeline (sciforge/timeline_ops.py): right-click a step / drag it / drag the marker.
    "suppress": ({"target"}, {"comment"}),
    "unsuppress": ({"target"}, {"comment"}),
    "delete": ({"target"}, {"comment"}),
    "move": ({"target"}, {"before", "after", "comment"}),
    "roll": (set(), {"after", "end", "start", "before", "comment"}),
    # File > Save, close, open again (only what is saved in the file is left).
    "reopen": (set(), {"comment"}),
    # Test setup: a coil / pipe as saved by SciForge before the primitives QA fixes.
    "age": ({"target"}, {"comment"}),
}

# Fusion-style Fillet / Chamfer (sciforge/blend.py, the same code as the F and Chamfer dialogs):
# pick edges, faces (every sharp edge around them) or features (the edges a step made).
STEP_KEYS["blend_fillet"] = ({"id", "radius"}, {"edges", "faces", "features", "comment"})
STEP_KEYS["blend_chamfer"] = (
    {"id", "distance"},
    {"chamfer_type", "distance2", "angle", "flip", "edges", "faces", "features", "comment"},
)

GEOMETRY_KINDS = ("rect", "center_rect", "circle", "polyline", "polygon", "slot", "line")
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
        elif kind == "line":
            if not isinstance(value, list) or len(value) != 4:
                _fail(here, "'line' takes [x0, y0, x1, y1]")


def _check_ref(where, spec):
    """An object a Fusion field picks: {"plane": "XY"}, {"face": selector} or {"step": id}."""
    if not isinstance(spec, dict) or len(set(spec) & {"plane", "face", "step"}) != 1:
        _fail(where, "must be {'plane': 'XY'}, {'face': selector} or {'step': id}")
    if "plane" in spec and spec["plane"] not in PLANES:
        _fail(where, "'plane' must be one of %s" % (PLANES,))


def _check_extrude(where, step, seen):
    """Extrude's Fusion options (sciforge/extrude.py)."""
    for key in ("extent", "extent2"):
        if step.get(key, "distance") not in EXTRUDE_EXTENTS:
            _fail(where, "'%s' must be one of %s" % (key, EXTRUDE_EXTENTS))
    if step.get("extent") == "to_object":
        _check_ref(where + ".to", step.get("to"))
    if step.get("extent2") == "to_object":
        _check_ref(where + ".to2", step.get("to2"))
    if step.get("measurement", "whole") not in ("half", "whole"):
        _fail(where, "'measurement' must be 'half' or 'whole'")
    start = step.get("start", "profile")
    if start not in ("profile", "offset", "object"):
        _fail(where, "'start' must be profile, offset or object")
    if start == "offset":
        _check_number(where + ".start_offset", step.get("start_offset"))
    if start == "object":
        _check_ref(where + ".start_from", step.get("start_from"))
    for name in step.get("more_profiles", []):
        if seen.get(name) != "sketch":
            _fail(where, "'more_profiles' must name earlier sketch steps, got %r" % name)
    thin = step.get("thin")
    if thin is not None:
        if not isinstance(thin, dict) or set(thin) - {
            "location",
            "thickness",
            "location2",
            "thickness2",
        }:
            _fail(where, "'thin' is {location, thickness, location2, thickness2}")
        for key in ("location", "location2"):
            if thin.get(key, "side1") not in ("side1", "center", "side2"):
                _fail(where, "'thin.%s' must be side1, center or side2" % key)
        for key in ("thickness", "thickness2"):
            if key in thin:
                _check_number(where + ".thin." + key, thin[key], positive=True)
    regions = step.get("regions")
    if regions is not None:
        if "profile" not in step or not isinstance(regions, list) or not regions:
            _fail(where, "'regions' is a list of [x, y] points inside the picked sketch areas")
        for point in regions:
            if not isinstance(point, list) or len(point) != 2:
                _fail(where, "each region is an [x, y] point in sketch coordinates")


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
        if op == "parameter":
            # A second step with the same name changes the parameter (like editing its value).
            if seen.get(step["name"], "parameter") != "parameter":
                _fail(here, "parameter name %r clashes with a step id" % step["name"])
            seen[step["name"]] = "parameter"
        if "id" in step:
            if step["id"] in seen:
                _fail(here, "duplicate step id %r" % step["id"])
            seen[step["id"]] = op

        if op == "sketch":
            if ("plane" in step) == ("face" in step):
                _fail(here, "sketch needs exactly one of 'plane' or 'face' (a selector)")
            if "plane" in step and step["plane"] not in PLANES:
                _fail(here, "'plane' must be one of %s" % (PLANES,))
            if step.get("auto_project") and "face" not in step:
                _fail(here, "'auto_project' projects the edges of the sketch's 'face'")
            _check_geometry(here, step["geometry"])
        if op == "extrude" and "curves" not in step and ("profile" in step) == ("face" in step):
            _fail(here, "extrude needs exactly one of 'profile' (a sketch) or 'face' (a selector)")
        if op == "extrude" and "curves" in step:
            if "thin" not in step:
                _fail(here, "'curves' are the profile of a thin extrude only (add 'thin')")
            if "face" in step or ("profile" in step and "regions" not in step):
                _fail(here, "'curves' go alone, or with 'profile' + 'regions' (areas)")
        if op == "revolve" or (op == "extrude" and "profile" in step):
            if seen.get(step["profile"]) != "sketch":
                _fail(here, "'profile' must name an earlier sketch step, got %r" % step["profile"])
        if op in ("extrude", "revolve"):
            if step.get("operation", "join") not in OPERATIONS:
                _fail(here, "'operation' must be one of %s" % (OPERATIONS,))
        if op == "extrude":
            _check_extrude(here, step, seen)
            extent = step.get("extent", "distance")
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
            if "set" not in step and "constraint" not in step and "expressions" not in step:
                _fail(here, "edit needs 'set', 'constraint'+'value' or 'expressions'")
        if op == "check":
            _check_expect(here, step["expect"])
        if op in ("sketch_polygon", "sketch_trim") and seen.get(step["sketch"]) != "sketch":
            _fail(here, "'sketch' must name an earlier sketch step, got %r" % step["sketch"])
        if op == "sketch_polygon":
            sides = step["sides"]
            if not isinstance(sides, int) or isinstance(sides, bool) or sides < 3:
                _fail(here, "'sides' must be a whole number >= 3")
            if "diameter" in step:
                _check_number(here + ".diameter", step["diameter"], positive=True)
        if op in ("suppress", "unsuppress", "delete", "move") and step["target"] not in seen:
            _fail(here, "'target' names unknown step %r" % step["target"])
        if op == "move":
            refs = [k for k in ("before", "after") if k in step]
            if len(refs) != 1 or step[refs[0]] not in seen:
                _fail(here, "move needs one of 'before'/'after' naming an earlier step")
        ends = [
            "after" in step,
            bool(step.get("end")),
            bool(step.get("start")),
            "before" in step,
        ]
        if op == "roll" and ends.count(True) != 1:
            _fail(
                here,
                'roll needs "after" or "before" (a step id), "end": true or "start": true',
            )
        if op == "roll" and "after" in step and step["after"] not in seen:
            _fail(here, "'after' names unknown step %r" % step["after"])
        if op == "roll" and "before" in step and step["before"] not in seen:
            _fail(here, "'before' names unknown step %r" % step["before"])

    _check_expect(where + ".expect", model["expect"])
    return model


# Fusion-style Hole and Thread (golden/hole_ops.py; sciforge/hole.py and sciforge/thread.py,
# the same code as the H and Thread dialogs).
_HOLE_OPTION_KEYS = {
    "extent",
    "depth",
    "to",
    "hole_type",
    "diameter",
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
    "direction",
    "modeled",
    "full_tap",
    "tap_depth",
    "flip",
    "comment",
}
# Fusion Emboss (the Emboss dialog's code, sciforge/emboss.py; golden/emboss_ops.py)
STEP_KEYS["emboss"] = (
    {"id", "sketch", "faces"},
    {"depth", "effect", "h", "v", "angle", "tangent_chain", "comment"},
)
STEP_KEYS["hole_at"] = ({"id", "face", "at"}, {"references"} | _HOLE_OPTION_KEYS)
STEP_KEYS["hole_points"] = ({"id", "sketch"}, set(_HOLE_OPTION_KEYS))
STEP_KEYS["thread"] = (
    {"id", "faces"},
    {
        "standard",
        "size",
        "designation",
        "thread_class",
        "direction",
        "modeled",
        "full_length",
        "length",
        "offset",
        "from_end",
        "comment",
    },
)

# -- Fusion Revolve (sciforge/revolve.py, the Revolve dialog's code; golden/revolve_ops.py) ---
STEP_KEYS["sf_revolve"] = (
    {"id", "axis"},
    {
        "profile",
        "regions",
        "face",
        "type",
        "direction",
        "angle",
        "angle2",
        "operation",
        "comment",
    },
)
STEP_KEYS["sf_revolve_edit"] = ({"target", "set"}, {"comment"})
REVOLVE_TYPES = ("angle", "full")
REVOLVE_DIRECTIONS = ("one_side", "two_sides", "symmetric")
REVOLVE_OPERATIONS = ("auto",) + OPERATIONS
REVOLVE_OPTIONS = ("type", "direction", "angle", "angle2", "operation")


def _check_revolve_options(here, options):
    if options.get("type", "angle") not in REVOLVE_TYPES:
        _fail(here, "'type' must be one of %s" % (REVOLVE_TYPES,))
    if options.get("direction", "one_side") not in REVOLVE_DIRECTIONS:
        _fail(here, "'direction' must be one of %s" % (REVOLVE_DIRECTIONS,))
    if options.get("operation", "auto") not in REVOLVE_OPERATIONS:
        _fail(here, "'operation' must be one of %s" % (REVOLVE_OPERATIONS,))
    for key in ("angle", "angle2"):
        if key in options:
            _check_number(here + "." + key, options[key])
            if abs(options[key]) > 360:
                _fail(here, "'%s' must be between -360 and 360 degrees" % key)


def _check_revolve_axis(here, axis, seen):
    if isinstance(axis, str):
        if axis not in AXES:
            _fail(here, "'axis' must be X, Y, Z or an object (see golden/README.md)")
        return
    if not isinstance(axis, dict):
        _fail(here, "'axis' must be X, Y, Z or an object")
    if "edge" in axis:
        if set(axis) != {"edge"}:
            _fail(here, "an edge axis is {'edge': selector}")
        return
    if seen.get(axis.get("sketch")) != "sketch":
        _fail(here, "the axis 'sketch' must name an earlier sketch step")
    kinds = [k for k in ("at", "construction", "axis") if k in axis]
    extra = {"name"} if kinds == ["construction"] else set()
    if len(kinds) != 1 or not {"sketch", kinds[0]} <= set(axis) <= {"sketch", kinds[0]} | extra:
        _fail(here, "a sketch axis needs exactly one of 'at', 'construction', 'axis'")
    if "name" in axis and not isinstance(axis["name"], str):
        _fail(here, "a construction line's 'name' is a string")
    if "axis" in axis and axis["axis"] not in ("H", "V"):
        _fail(here, "a sketch's own axis is 'H' or 'V'")
    if "at" in axis and (not isinstance(axis["at"], list) or len(axis["at"]) != 2):
        _fail(here, "'at' is an [x, y] point in sketch coordinates")
    if "construction" in axis:
        line = axis["construction"]
        if not isinstance(line, list) or len(line) != 2 or any(len(p) != 2 for p in line):
            _fail(here, "'construction' is [[x1, y1], [x2, y2]] in sketch coordinates")


def _check_revolve_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_revolve":
            if ("profile" in step) == ("face" in step):
                _fail(here, "sf_revolve needs exactly one of 'profile' (a sketch) or 'face'")
            if "profile" in step and seen.get(step["profile"]) != "sketch":
                _fail(here, "'profile' must name an earlier sketch step, got %r" % step["profile"])
            if "regions" in step and "profile" not in step:
                _fail(here, "'regions' go with 'profile'")
            _check_revolve_axis(here, step["axis"], seen)
            _check_revolve_options(here, step)
        if op == "sf_revolve_edit":
            if seen.get(step["target"]) != "sf_revolve":
                _fail(here, "'target' must name an earlier sf_revolve step")
            if not isinstance(step["set"], dict) or not step["set"]:
                _fail(here, "'set' is a non-empty object of revolve options")
            unknown = set(step["set"]) - set(REVOLVE_OPTIONS)
            if unknown:
                _fail(here, "sf_revolve_edit cannot set %s" % sorted(unknown))
            _check_revolve_options(here, step["set"])
        if "id" in step:
            seen[step["id"]] = op


_validate_before_revolve = validate


def validate(model):  # noqa: F811  (adds the revolve checks to the checks above)
    _validate_before_revolve(model)
    _check_revolve_steps(model)
    return model


# Fusion-style Rectangular / Circular Pattern, Pattern on Path and Mirror (golden/pattern_ops.py;
# sciforge/pattern.py, the same code as their dialogs). What is patterned: one of "features"
# (step ids), "faces" (a selector) or "body": true.
_PATTERN_WHAT = {"features", "faces", "body", "expressions", "suppressed", "comment"}
STEP_KEYS["rectangular_pattern"] = (
    {"id", "direction"},
    _PATTERN_WHAT
    | {
        "quantity",
        "distance",
        "distribution",
        "direction_type",
        "direction2",
        "quantity2",
        "distance2",
        "direction_type2",
    },
)
STEP_KEYS["circular_pattern"] = ({"id", "axis"}, _PATTERN_WHAT | {"quantity", "type", "angle"})
STEP_KEYS["path_pattern"] = (
    {"id", "path"},
    _PATTERN_WHAT | {"quantity", "distance", "distribution", "direction_type", "orientation"},
)
STEP_KEYS["fusion_mirror"] = ({"id", "plane"}, _PATTERN_WHAT | {"operation"})
STEP_KEYS["pattern_edit"] = ({"target", "set"}, {"comment"})
# -- Fusion Shell / Draft / Scale (sciforge/shelling.py, drafting.py, scale.py, the dialogs'
# code; golden/shell_draft_ops.py) ---------------------------------------------------------
STEP_KEYS["sf_shell"] = (
    {"id"},
    {"faces", "body", "inside", "outside", "direction", "shell_type", "comment"},
)
STEP_KEYS["sf_shell_edit"] = ({"target", "set"}, {"comment"})
STEP_KEYS["sf_draft"] = ({"id", "plane", "faces"}, {"angle", "flip", "comment"})
STEP_KEYS["sf_draft_edit"] = ({"target", "set"}, {"comment"})
STEP_KEYS["sf_scale"] = ({"id"}, {"factor", "factors", "point", "comment"})
STEP_KEYS["sf_scale_edit"] = ({"target", "set"}, {"comment"})
SHELL_EDIT = {"inside", "outside", "direction", "shell_type"}
DRAFT_EDIT = {"angle", "flip"}
SCALE_EDIT = {"factor", "factors"}


def _check_scale_values(here, spec):
    if ("factor" in spec) == ("factors" in spec):
        _fail(here, "give exactly one of 'factor' (uniform) or 'factors' [x, y, z]")
    values = [spec["factor"]] if "factor" in spec else spec["factors"]
    if "factors" in spec and (not isinstance(values, list) or len(values) != 3):
        _fail(here, "'factors' is [x, y, z]")
    for value in values:
        _check_number(here + ".factor", value, positive=True)


def _check_draft_plane(here, plane):
    if isinstance(plane, str):
        if plane not in PLANES:
            _fail(here, "'plane' must be XY, XZ, YZ or {'face': selector}")
    elif not isinstance(plane, dict) or set(plane) != {"face"}:
        _fail(here, "'plane' must be XY, XZ, YZ or {'face': selector}")


def _check_shell_draft_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_shell":
            if ("faces" in step) == bool(step.get("body")):
                _fail(here, "sf_shell needs exactly one of 'faces' or 'body': true")
            if step.get("direction", "inside") not in ("inside", "outside", "both"):
                _fail(here, "'direction' must be inside, outside or both")
            if step.get("shell_type", "sharp") not in ("sharp", "rounded"):
                _fail(here, "'shell_type' must be sharp or rounded")
            for key in ("inside", "outside"):
                if key in step:
                    _check_number(here + "." + key, step[key], positive=True)
        if op == "sf_draft":
            _check_draft_plane(here, step["plane"])
            if "angle" in step:
                _check_number(here + ".angle", step["angle"])
        if op == "sf_scale":
            _check_scale_values(here, step)
            point = step.get("point", "origin")
            if point != "origin" and (not isinstance(point, list) or len(point) != 3):
                _fail(here, "'point' is 'origin' or [x, y, z] (a corner of the part)")
        for edit, made, allowed in (
            ("sf_shell_edit", "sf_shell", SHELL_EDIT),
            ("sf_draft_edit", "sf_draft", DRAFT_EDIT),
            ("sf_scale_edit", "sf_scale", SCALE_EDIT),
        ):
            if op != edit:
                continue
            if seen.get(step["target"]) != made:
                _fail(here, "'target' must name an earlier %s step" % made)
            if not isinstance(step["set"], dict) or not step["set"]:
                _fail(here, "'set' is a non-empty object")
            unknown = set(step["set"]) - allowed
            if unknown:
                _fail(here, "%s cannot set %s" % (edit, sorted(unknown)))
            if edit == "sf_scale_edit":
                _check_scale_values(here, step["set"])
        if "id" in step:
            seen[step["id"]] = op


# Body tools (golden/bodies_ops.py; sciforge/combine.py, split.py, move.py, delete.py, the same
# code as their dialogs). Bodies are named by a step that made them.
STEP_KEYS["combine"] = (
    {"id", "target", "tools"},
    {"operation", "new_body", "new_component", "keep_tools", "comment"},
)
# "tools": several splitting tools at once (Fusion's Splitting Tool(s), components-2)
STEP_KEYS["split_body"] = ({"id", "body"}, {"tool", "tools", "extend", "comment"})
STEP_KEYS["move_bodies"] = (
    {"id", "bodies"},
    {
        "move_type",
        "dx",
        "dy",
        "dz",
        "rx",
        "ry",
        "rz",
        "pivot",
        "axis",
        "angle",
        "from_point",
        "to_point",
        "px",
        "py",
        "pz",
        "copy",
        "comment",
    },
)
STEP_KEYS["delete_face"] = ({"id", "faces"}, {"comment"})
STEP_KEYS["body_tool_edit"] = ({"target", "set"}, {"comment"})
STEP_KEYS["measure_bodies"] = ({"steps"}, {"comment"})
STEP_KEYS["delete_bodies"] = ({"steps"}, {"comment"})

BODY_OPERATIONS = ("join", "cut", "intersect")
MOVE_TYPES = ("free", "translate", "rotate", "point_to_point", "point_to_position")


def _check_body_steps(model):
    """References and choices of the body-tool steps (combine, split_body, move_bodies,
    delete_face, body_tool_edit, measure_bodies)."""
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (model.get("id", "?"), i)
        op = step.get("op")
        if op == "combine":
            for name in [step["target"]] + list(step["tools"]):
                if name not in seen:
                    _fail(here, "combine names unknown step %r" % name)
            if not step["tools"]:
                _fail(here, "combine needs at least one tool")
            if step["target"] in step["tools"]:
                _fail(here, "the target cannot be a tool")
            if step.get("operation", "join") not in BODY_OPERATIONS:
                _fail(here, "'operation' must be one of %s" % (BODY_OPERATIONS,))
        if op == "split_body":
            if step["body"] not in seen:
                _fail(here, "split_body names unknown step %r" % step["body"])
            if ("tool" in step) == ("tools" in step):
                _fail(here, "split_body needs 'tool' or 'tools' (a list of tools)")
            tools = step["tools"] if "tools" in step else [step["tool"]]
            if not isinstance(tools, list) or not tools:
                _fail(here, "'tools' must be a non-empty list")
            for tool in tools:
                _check_split_tool(here, tool, seen)
        if op == "move_bodies":
            if not step["bodies"] or any(b not in seen for b in step["bodies"]):
                _fail(here, "'bodies' must name earlier steps")
            kind = step.get("move_type", "free")
            if kind not in MOVE_TYPES:
                _fail(here, "'move_type' must be one of %s" % (MOVE_TYPES,))
            if kind == "rotate" and step.get("axis") not in AXES:
                _fail(here, "rotate needs 'axis' X, Y or Z")
            if kind == "point_to_point" and not ("from_point" in step and "to_point" in step):
                _fail(here, "point_to_point needs 'from_point' and 'to_point'")
            if kind == "point_to_position" and "from_point" not in step:
                _fail(here, "point_to_position needs 'from_point' (and px, py, pz)")
            for key in ("dx", "dy", "dz", "rx", "ry", "rz", "angle", "px", "py", "pz"):
                if key in step:
                    _check_number(here + "." + key, step[key])
        if op in ("body_tool_edit",) and seen.get(step["target"]) not in (
            "combine",
            "split_body",
            "move_bodies",
        ):
            _fail(here, "body_tool_edit must name a combine, split_body or move_bodies step")
        if op in ("measure_bodies", "delete_bodies") and any(s not in seen for s in step["steps"]):
            _fail(here, "%s names unknown steps" % op)
        if "id" in step:
            seen[step["id"]] = op


def _check_split_tool(here, tool, seen):
    if isinstance(tool, str):
        if tool not in PLANES:
            _fail(here, "'tool' plane must be one of %s" % (PLANES,))
    elif not isinstance(tool, dict) or len(set(tool) & {"face", "body", "sketch"}) != 1:
        _fail(
            here,
            "'tool' must be XY/XZ/YZ, {'face': selector, 'of': id}, {'body': id} or "
            "{'sketch': id, 'edge': n}",
        )
    else:
        if "sketch" in tool and seen.get(tool["sketch"]) != "sketch":
            _fail(here, "'tool' names unknown sketch %r" % tool["sketch"])
        for key in ("of", "body"):
            if key in tool and tool[key] not in seen:
                _fail(here, "'tool' names unknown step %r" % tool[key])


_validate_before_shell_draft = validate


def validate(model):  # noqa: F811  (adds the Shell / Draft / Scale checks)
    _validate_before_shell_draft(model)
    _check_shell_draft_steps(model)
    return model


_validate_before_bodies = validate


def validate(model):  # noqa: F811  (adds the body-tool checks to the checks above)
    _validate_before_bodies(model)
    _check_body_steps(model)
    return model


# History edits around Fusion-style Fillet / Chamfer (golden/blend_ops.py, the dialogs' code):
# a blend made with the timeline marker rolled back, and a blend edited to pick more edges.
_BLEND_OPTIONS = {"radius", "distance", "chamfer_type", "distance2", "angle", "flip"}
STEP_KEYS["blend_insert"] = ({"id", "kind"}, _BLEND_OPTIONS | {"edges", "faces", "comment"})
STEP_KEYS["blend_edit"] = ({"target"}, {"add_edges", "add_faces", "set", "comment"})


def _check_blend_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "blend_insert":
            if step["kind"] not in ("fillet", "chamfer"):
                _fail(here, "'kind' must be fillet or chamfer")
            size = "radius" if step["kind"] == "fillet" else "distance"
            _check_number(here + "." + size, step.get(size), positive=True)
            if "edges" not in step and "faces" not in step:
                _fail(here, "blend_insert needs 'edges' and/or 'faces'")
        if op == "blend_edit":
            if seen.get(step["target"]) not in ("blend_fillet", "blend_chamfer", "blend_insert"):
                _fail(here, "'target' must name an earlier blend_fillet/blend_chamfer step")
            unknown = set(step.get("set", {})) - _BLEND_OPTIONS
            if unknown:
                _fail(here, "blend_edit cannot set %s" % sorted(unknown))
            if not ({"add_edges", "add_faces", "set"} & set(step)):
                _fail(here, "blend_edit needs 'add_edges', 'add_faces' or 'set'")
        if "id" in step:
            seen[step["id"]] = op


_validate_before_blend = validate


def validate(model):  # noqa: F811  (adds the blend history checks to the checks above)
    _validate_before_blend(model)
    _check_blend_steps(model)
    return model


# CONSTRUCT and INSPECT (golden/inspect_ops.py: sciforge/construct.py, measure.py, section.py,
# analysis.py, the code the dialogs use)
STEP_KEYS["construct"] = ({"id", "preset", "refs"}, {"values", "points", "comment"})
STEP_KEYS["construct_expect"] = ({"target", "point"}, {"normal", "direction", "comment"})
STEP_KEYS["construct_extrude"] = (
    {"id", "plane", "circles"},
    {"distance", "operation", "direction", "flip", "comment"},
)
STEP_KEYS["measure_expect"] = ({"a", "b"}, {"distance", "angle", "comment"})
STEP_KEYS["section_expect"] = (
    {"plane"},
    {"distance", "x_angle", "y_angle", "flip", "kept_volume", "cap_area", "comment"},
)
STEP_KEYS["com_expect"] = ({"point"}, {"features", "comment"})
STEP_KEYS["interference_expect"] = (
    {"features"},
    {"include_coincident", "volume", "pairs", "comment"},
)
INSPECT_REF_KEYS = ("plane", "axis", "origin", "face", "edge", "vertex", "construct")


def _check_inspect_ref(here, spec, seen):
    if not isinstance(spec, dict) or len(spec) != 1 or not set(spec) <= set(INSPECT_REF_KEYS):
        _fail(here, "a pick is one of %s" % (INSPECT_REF_KEYS,))
    if "plane" in spec and spec["plane"] not in PLANES:
        _fail(here, "'plane' must be one of %s" % (PLANES,))
    if "axis" in spec and spec["axis"] not in AXES:
        _fail(here, "'axis' must be one of %s" % (AXES,))
    if "vertex" in spec:
        _check_point(here + ".vertex", spec["vertex"])
    if "construct" in spec and seen.get(spec["construct"]) != "construct":
        _fail(here, "'construct' must name an earlier construct step")


def _check_point(here, value):
    if not isinstance(value, list) or len(value) != 3:
        _fail(here, "expected [x, y, z]")
    for v in value:
        _check_number(here, v)


def _check_inspect_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "construct":
            if not isinstance(step["preset"], str) or not step["preset"]:
                _fail(here, "'preset' is a CONSTRUCT entry (sciforge/construct.py SPECS)")
            if not isinstance(step["refs"], list) or not step["refs"]:
                _fail(here, "'refs' is a non-empty list of picks")
            for j, spec in enumerate(step["refs"]):
                _check_inspect_ref("%s.refs[%d]" % (here, j), spec, seen)
            for j, point in enumerate(step.get("points", [])):
                if point is not None:
                    _check_point("%s.points[%d]" % (here, j), point)
        if op == "construct_expect":
            if seen.get(step["target"]) != "construct":
                _fail(here, "'target' must name an earlier construct step")
            _check_point(here + ".point", step["point"])
            for key in ("normal", "direction"):
                if key in step:
                    _check_point(here + "." + key, step[key])
        if op == "construct_extrude":
            if seen.get(step["plane"]) != "construct":
                _fail(here, "'plane' must name an earlier construct step (a plane)")
            circles = step["circles"]
            if not isinstance(circles, list) or not circles:
                _fail(here, "'circles' is a list of [x, y, z, r] (centre on the plane, global)")
            for j, circle in enumerate(circles):
                if not isinstance(circle, list) or len(circle) != 4:
                    _fail("%s.circles[%d]" % (here, j), "expected [x, y, z, r]")
                _check_number("%s.circles[%d].r" % (here, j), circle[3], positive=True)
            if step.get("operation", "join") not in OPERATIONS:
                _fail(here, "'operation' must be one of %s" % (OPERATIONS,))
            if step.get("direction", "one_side") not in ("one_side", "symmetric"):
                _fail(here, "'direction' must be one_side or symmetric")
            _check_number(here + ".distance", step.get("distance", 1.0), positive=True)
        if op == "measure_expect":
            _check_inspect_ref(here + ".a", step["a"], seen)
            _check_inspect_ref(here + ".b", step["b"], seen)
            if "distance" not in step and "angle" not in step:
                _fail(here, "measure_expect checks 'distance' and/or 'angle'")
        if op == "section_expect":
            _check_inspect_ref(here + ".plane", step["plane"], seen)
            if "kept_volume" not in step and "cap_area" not in step:
                _fail(here, "section_expect checks 'kept_volume' and/or 'cap_area'")
        if op == "com_expect":
            _check_point(here + ".point", step["point"])
        if op in ("com_expect", "interference_expect"):
            for name in step.get("features", []):
                if name not in seen:
                    _fail(here, "'features' names unknown step %r" % name)
        if "id" in step:
            seen[step["id"]] = op


_validate_before_inspect = validate


def validate(model):  # noqa: F811  (adds the CONSTRUCT / INSPECT checks)
    _validate_before_inspect(model)
    _check_inspect_steps(model)
    return model


# Fusion's Box, Cylinder, Sphere, Torus, Coil and Pipe (golden/primitive_ops.py; sciforge/
# primitives.py, coil.py and pipe.py, the same code as their dialogs).
_PRIMITIVE_OPTIONS = {
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
    "operation",
}
_COIL_OPTIONS = {
    "x",
    "y",
    "type",
    "diameter",
    "clockwise",
    "revolutions",
    "height",
    "pitch",
    "angle",
    "section",
    "section_position",
    "section_size",
    "operation",
}
_PIPE_OPTIONS = {"distance", "section", "section_size", "hollow", "thickness", "operation"}
STEP_KEYS["sf_primitive"] = (
    {"id", "kind"},
    {"plane", "expressions", "comment"} | _PRIMITIVE_OPTIONS,
)
STEP_KEYS["sf_coil"] = ({"id"}, {"plane", "expressions", "comment"} | _COIL_OPTIONS)
STEP_KEYS["sf_path_sketch"] = ({"id", "segments"}, {"plane", "comment"})
STEP_KEYS["sf_pipe"] = ({"id", "path"}, {"chain", "expressions", "comment"} | _PIPE_OPTIONS)
STEP_KEYS["sf_primitive_edit"] = ({"target", "set"}, {"comment"})
STEP_KEYS["expect_component"] = ({"step"}, {"comment"})
PRIMITIVE_KINDS = ("box", "cylinder", "sphere", "torus")
PRIMITIVE_OPERATIONS = ("auto",) + OPERATIONS + ("new_component",)


def _check_primitive_plane(here, step):
    plane = step.get("plane", "XY")
    if isinstance(plane, str):
        if plane not in PLANES:
            _fail(here, "'plane' must be XY, XZ, YZ or {'face': selector}")
    elif not isinstance(plane, dict) or set(plane) != {"face"}:
        _fail(here, "'plane' must be XY, XZ, YZ or {'face': selector}")


def _check_primitive_values(here, values, allowed):
    for key, value in values.items():
        if key not in allowed:
            _fail(here, "cannot set %r" % key)
        if key == "operation" and value not in PRIMITIVE_OPERATIONS:
            _fail(here, "'operation' must be one of %s" % (PRIMITIVE_OPERATIONS,))
        elif key in ("position", "section_position") and value not in (
            "inside",
            "center",
            "outside",
        ):
            _fail(here, "'%s' must be inside, center or outside" % key)
        elif key in ("hollow", "clockwise") and not isinstance(value, bool):
            _fail(here, "'%s' is true or false" % key)
        elif key == "type" and value not in ("rev_height", "rev_pitch", "height_pitch", "spiral"):
            _fail(here, "'type' must be rev_height, rev_pitch, height_pitch or spiral")
        elif key == "section" and value not in (
            "circular",
            "square",
            "triangular",
            "tri_ext",
            "tri_int",
        ):
            _fail(here, "unknown section %r" % value)
        elif key not in (
            "operation",
            "position",
            "section_position",
            "hollow",
            "clockwise",
            "type",
            "section",
        ):
            _check_number(here + "." + key, value)


def _check_primitive_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_primitive":
            if step["kind"] not in PRIMITIVE_KINDS:
                _fail(here, "'kind' must be one of %s" % (PRIMITIVE_KINDS,))
            _check_primitive_plane(here, step)
            values = {k: v for k, v in step.items() if k in _PRIMITIVE_OPTIONS}
            _check_primitive_values(here, values, _PRIMITIVE_OPTIONS)
        if op == "sf_coil":
            _check_primitive_plane(here, step)
            values = {k: v for k, v in step.items() if k in _COIL_OPTIONS}
            _check_primitive_values(here, values, _COIL_OPTIONS)
        if op == "sf_path_sketch":
            if step.get("plane", "XY") not in PLANES:
                _fail(here, "'plane' must be one of %s" % (PLANES,))
            segments = step["segments"]
            if not isinstance(segments, list) or not segments:
                _fail(here, "'segments' is a non-empty list of lines and arcs")
            for segment in segments:
                if not isinstance(segment, dict) or len(set(segment) & {"line", "arc"}) != 1:
                    _fail(here, "a segment is {'line': [[x0, y0], [x1, y1]]} or {'arc': [...]}")
                if "arc" in segment and len(segment["arc"]) != 5:
                    _fail(here, "an arc is [cx, cy, radius, start degrees, end degrees]")
        if op == "sf_pipe":
            path = step["path"]
            if not isinstance(path, dict) or not (
                set(path) == {"edges"} or {"sketch"} <= set(path) <= {"sketch", "edge"}
            ):
                _fail(here, "'path' is {'sketch': id, 'edge': n} or {'edges': selector}")
            if "sketch" in path and seen.get(path["sketch"]) not in ("sketch", "sf_path_sketch"):
                _fail(here, "'path' names unknown sketch %r" % path["sketch"])
            values = {k: v for k, v in step.items() if k in _PIPE_OPTIONS}
            _check_primitive_values(here, values, _PIPE_OPTIONS)
        if "expressions" in step and op in ("sf_primitive", "sf_coil", "sf_pipe"):
            allowed = {
                "sf_primitive": _PRIMITIVE_OPTIONS,
                "sf_coil": _COIL_OPTIONS,
                "sf_pipe": _PIPE_OPTIONS,
            }[op]
            formulas = step["expressions"]
            if not isinstance(formulas, dict) or any(
                k not in allowed or not isinstance(v, str) for k, v in formulas.items()
            ):
                _fail(here, "'expressions' is {field: formula} for this step's own fields")
        if op == "sf_primitive_edit":
            kind = seen.get(step["target"])
            allowed = {
                "sf_primitive": _PRIMITIVE_OPTIONS,
                "sf_coil": _COIL_OPTIONS,
                "sf_pipe": _PIPE_OPTIONS,
            }.get(kind)
            if allowed is None:
                _fail(here, "'target' must name an earlier sf_primitive, sf_coil or sf_pipe step")
            if not isinstance(step["set"], dict) or not step["set"]:
                _fail(here, "'set' is a non-empty object of options")
            _check_primitive_values(here, step["set"], allowed)
        if op == "expect_component" and step["step"] not in seen:
            _fail(here, "'step' names unknown step %r" % step["step"])
        if "id" in step:
            seen[step["id"]] = op


_validate_before_primitives = validate


def validate(model):  # noqa: F811  (adds the primitive / coil / pipe checks)
    _validate_before_primitives(model)
    _check_primitive_steps(model)
    return model


# -- Fusion Sweep / Loft / Rib / Web (golden/sweep_loft_ops.py; sciforge/sweep.py, loft.py,
# rib.py, the same code as their dialogs) ------------------------------------------------------
STEP_KEYS["sf_curves"] = ({"id", "plane", "curves"}, {"offset", "comment"})
STEP_KEYS["sf_sweep"] = (
    {"id", "path"},
    {
        "profile",
        "regions",
        "face",
        "rail",
        "surface",
        "type",
        "distance",
        "distance2",
        "taper",
        "twist",
        "orientation",
        "scaling",
        "operation",
        "comment",
    },
)
STEP_KEYS["sf_sweep_edit"] = ({"target", "set"}, {"comment"})
STEP_KEYS["expect_radius"] = ({"step", "max"}, {"min", "comment"})
SWEEP_SET = {
    "type",
    "distance",
    "distance2",
    "taper",
    "twist",
    "orientation",
    "scaling",
    "operation",
}
SWEEP_CHOICES = {
    "type": ("single", "rail", "surface"),
    "orientation": ("perpendicular", "parallel"),
    "scaling": ("scale", "stretch", "none"),
    "operation": ("auto", "join", "cut", "intersect", "new_body"),
}
CURVE_SKETCHES = ("sketch", "sf_curves")


def _check_curves_spec(here, spec, seen):
    if isinstance(spec, str):
        if seen.get(spec) not in CURVE_SKETCHES:
            _fail(here, "a curve sketch must name an earlier sketch / sf_curves step")
        return
    if not isinstance(spec, dict) or not ({"sketch", "edge"} & set(spec)):
        _fail(here, "curves are a sketch id, {'sketch', 'at'} or {'edge': selector}")
    if "sketch" in spec:
        if seen.get(spec["sketch"]) not in CURVE_SKETCHES:
            _fail(here, "'sketch' must name an earlier sketch / sf_curves step")
        if "at" not in spec:
            _fail(here, "{'sketch'} needs 'at': [x, y] (or a list of points)")


def _check_sweep_options(here, options):
    for key, allowed in SWEEP_CHOICES.items():
        if key in options and options[key] not in allowed:
            _fail(here, "'%s' must be one of %s" % (key, allowed))
    for key in ("distance", "distance2"):
        if key in options:
            _check_number(here + "." + key, options[key])
            if not 0.0 <= options[key] <= 1.0:
                _fail(here, "'%s' goes from 0 to 1" % key)
    for key in ("taper", "twist"):
        if key in options:
            _check_number(here + "." + key, options[key])


def _check_sweep_loft_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_curves":
            if step["plane"] not in PLANES:
                _fail(here, "'plane' must be one of %s" % (PLANES,))
            if not isinstance(step["curves"], list) or not step["curves"]:
                _fail(here, "'curves' is a non-empty list")
            kinds = {"line", "arc", "circle", "point", "polyline"}
            for item in step["curves"]:
                if not isinstance(item, dict) or len(set(item) & kinds) != 1:
                    _fail(here, "each curve is one of %s" % sorted(kinds))
        if op == "sf_sweep":
            if ("face" in step) == ("profile" in step):
                _fail(here, "sf_sweep needs exactly one of 'profile' (a sketch) or 'face'")
            if "profile" in step and seen.get(step["profile"]) not in CURVE_SKETCHES:
                _fail(here, "'profile' must name an earlier sketch step")
            _check_curves_spec(here + ".path", step["path"], seen)
            if "rail" in step:
                _check_curves_spec(here + ".rail", step["rail"], seen)
            if step.get("type") == "rail" and "rail" not in step:
                _fail(here, "type 'rail' needs a 'rail'")
            _check_sweep_options(here, step)
            if ("surface" in step) != (step.get("type") == "surface"):
                _fail(here, "type 'surface' goes with a 'surface': {'faces': selector}")
            if "surface" in step and set(step["surface"]) != {"faces"}:
                _fail(here, "'surface' is {'faces': selector}")
        if op == "sf_sweep" and "expressions" in step:
            formulas = step["expressions"]
            if not isinstance(formulas, dict) or any(
                k not in ("distance", "distance2", "taper", "twist") or not isinstance(v, str)
                for k, v in formulas.items()
            ):
                _fail(here, "'expressions' is {field: formula} (distance, distance2, taper, twist)")
        if op == "sf_sweep_edit":
            if seen.get(step["target"]) != "sf_sweep":
                _fail(here, "'target' must name an earlier sf_sweep step")
            if not isinstance(step["set"], dict) or not step["set"]:
                _fail(here, "'set' is a non-empty object")
            unknown = set(step["set"]) - SWEEP_SET
            if unknown:
                _fail(here, "sf_sweep_edit cannot set %s" % sorted(unknown))
            _check_sweep_options(here, step["set"])
        if op == "sf_loft":
            _check_loft_step(here, step, seen)
        if op == "sf_rib":
            _check_curves_spec(here + ".curves", step["curves"], seen)
            _check_rib_options(here, step)
        for edit, made, allowed, check in (
            ("sf_loft_edit", "sf_loft", LOFT_SET, _check_loft_options),
            ("sf_rib_edit", "sf_rib", RIB_SET, _check_rib_options),
        ):
            if op != edit:
                continue
            if seen.get(step["target"]) != made:
                _fail(here, "'target' must name an earlier %s step" % made)
            if not isinstance(step["set"], dict) or not step["set"]:
                _fail(here, "'set' is a non-empty object")
            unknown = set(step["set"]) - allowed
            if unknown:
                _fail(here, "%s cannot set %s" % (edit, sorted(unknown)))
            check(here, step["set"])
        if "id" in step:
            seen[step["id"]] = op


LOFT_END_KEYS = {
    "start_condition",
    "start_weight",
    "start_angle",
    "end_condition",
    "end_weight",
    "end_angle",
}
STEP_KEYS["sf_loft"] = (
    {"id", "profiles"},
    {"rails", "centerline", "guide", "closed", "merge", "operation", "comment"} | LOFT_END_KEYS,
)
STEP_KEYS["sf_loft_edit"] = ({"target", "set"}, {"comment"})
LOFT_SET = {"guide", "closed", "merge", "operation"} | LOFT_END_KEYS
STEP_KEYS["sf_rib"] = (
    {"id", "curves"},
    {
        "kind",
        "thickness",
        "thickness_side",
        "flip_side",
        "depth_type",
        "depth",
        "flip",
        "extend",
        "comment",
    },
)
STEP_KEYS["sf_rib_edit"] = ({"target", "set"}, {"comment"})
RIB_SET = {"thickness", "thickness_side", "flip_side", "depth_type", "depth", "flip", "extend"}


LOFT_CONDITIONS = ("free", "direction", "tangent", "curvature", "point_tangent")


def _check_loft_options(here, options):
    if options.get("guide", "rails") not in ("rails", "centerline"):
        _fail(here, "'guide' must be rails or centerline")
    if options.get("operation", "auto") not in SWEEP_CHOICES["operation"]:
        _fail(here, "'operation' must be one of %s" % (SWEEP_CHOICES["operation"],))
    if "closed" in options and not isinstance(options["closed"], bool):
        _fail(here, "'closed' is true or false")
    if "merge" in options and not isinstance(options["merge"], bool):
        _fail(here, "'merge' (Tangent Edges Merge) is true or false")
    for end in ("start", "end"):
        condition = options.get(end + "_condition", "free")
        if condition not in LOFT_CONDITIONS:
            _fail(here, "'%s_condition' must be one of %s" % (end, LOFT_CONDITIONS))
        for name in ("_weight", "_angle"):
            if end + name in options:
                _check_number(here, options[end + name], positive=name == "_weight")


def _check_loft_step(here, step, seen):
    profiles = step["profiles"]
    if not isinstance(profiles, list) or len(profiles) < 2:
        _fail(here, "'profiles' lists at least two profiles, in loft order")
    for k, spec in enumerate(profiles):
        where = "%s.profiles[%d]" % (here, k)
        if not isinstance(spec, dict) or len({"profile", "face", "point"} & set(spec)) != 1:
            _fail(where, "a profile is {'profile'}, {'face'} or {'point'}")
        if "profile" in spec and seen.get(spec["profile"]) not in CURVE_SKETCHES:
            _fail(where, "'profile' must name an earlier sketch step")
        if "point" in spec:
            _check_curves_spec(where, spec["point"], seen)
    for k, rail in enumerate(step.get("rails", [])):
        _check_curves_spec("%s.rails[%d]" % (here, k), rail, seen)
    if "centerline" in step:
        _check_curves_spec(here + ".centerline", step["centerline"], seen)
    _check_loft_options(here, step)


def _check_rib_options(here, options):
    for key, allowed in (
        ("kind", ("rib", "web")),
        ("thickness_side", ("symmetric", "one_side")),
        ("depth_type", ("to_next", "depth")),
    ):
        if key in options and options[key] not in allowed:
            _fail(here, "'%s' must be one of %s" % (key, allowed))
    for key in ("thickness", "depth"):
        if key in options:
            _check_number(here + "." + key, options[key], positive=True)
    for key in ("flip", "flip_side", "extend"):
        if key in options and not isinstance(options[key], bool):
            _fail(here, "'%s' is true or false" % key)


_validate_before_sweep_loft = validate


def validate(model):  # noqa: F811  (adds the sweep / loft / rib checks to the checks above)
    _validate_before_sweep_loft(model)
    _check_sweep_loft_steps(model)
    return model


# -- Revolve Type "To" (revolve QA): "to" names what the revolve goes to ---------------------------
STEP_KEYS["sf_revolve"] = (STEP_KEYS["sf_revolve"][0], STEP_KEYS["sf_revolve"][1] | {"to"})
REVOLVE_TYPES = ("angle", "to", "full")
_REVOLVE_TO_KEYS = ("plane", "face", "edge", "vertex", "construct")


def _check_revolve_to(model):
    for i, step in enumerate(model.get("steps", [])):
        if step.get("op") != "sf_revolve":
            continue
        here = "steps[%d] (sf_revolve)" % i
        to = step.get("to")
        if (step.get("type") == "to") != (to is not None):
            _fail(here, "type 'to' and a 'to' pick go together")
        picks = set(to) & set(_REVOLVE_TO_KEYS) if isinstance(to, dict) else set()
        if to is not None and len(picks) != 1:
            _fail(here, "'to' is one of %s" % (_REVOLVE_TO_KEYS,))


_validate_before_revolve_to = validate


def validate(model):  # noqa: F811  (adds the revolve "to" checks)
    _validate_before_revolve_to(model)
    _check_revolve_to(model)
    return model


# -- Physical Material of a body (inspect QA: a Center of Mass weighs bodies by their material) --
STEP_KEYS["body_material"] = ({"feature", "material"}, {"comment"})


def _check_body_material(model):
    seen = set()
    for i, step in enumerate(model.get("steps", [])):
        here = "steps[%d] (%s)" % (i, step.get("op"))
        if step.get("op") == "body_material":
            if step["feature"] not in seen:
                _fail(here, "'feature' names unknown step %r" % step["feature"])
            if not isinstance(step["material"], str) or not step["material"]:
                _fail(here, "'material' is a key of sciforge/material.py LIBRARY")
        if "id" in step:
            seen.add(step["id"])


_validate_before_body_material = validate


def validate(model):  # noqa: F811  (adds the body_material checks)
    _validate_before_body_material(model)
    _check_body_material(model)
    return model


# -- Extrude through several bodies (golden/extrude_bodies_ops.py; sciforge/extrude.py) ----------
STEP_KEYS["extrude"][1].add("bodies")
# To Object's Extend choice (face / adjacent / body / through) and Offset, per side
STEP_KEYS["extrude"][1].update({"extend", "extend2", "object_offset", "object_offset2"})
# Objects To Cut for Revolve, Sweep and Loft ("auto" or step ids, as for Extrude)
for _op in ("sf_revolve", "sf_sweep", "sf_loft"):
    STEP_KEYS[_op][1].add("bodies")
# A sweep's value fields take a parameter or a formula: {"distance": "share", ...}
STEP_KEYS["sf_sweep"][1].add("expressions")
STEP_KEYS["use_body"] = ({"step"}, {"comment"})
STEP_KEYS["expect_bodies"] = (set(), {"bodies", "used_up", "followers", "steps", "comment"})
STEP_KEYS["reopen_check"] = ({"bodies"}, {"comment"})
STEP_KEYS["expect_move_refused"] = ({"target"}, {"before", "after", "reason", "comment"})
_BODY_EXPECT_KEYS = {"volume", "solids", "valid"}


def _check_extrude_bodies(model):
    seen = {}
    for i, step in enumerate(model.get("steps", [])):
        here = "%s.steps[%d] (%s)" % (model.get("id", "?"), i, step.get("op"))
        op = step.get("op")
        if op == "extrude" and "bodies" in step:
            spec = step["bodies"]
            if spec != "auto":
                if not isinstance(spec, list) or any(s not in seen for s in spec):
                    _fail(here, "'bodies' is \"auto\" or a list of earlier step ids")
        if op == "use_body" and step["step"] not in seen:
            _fail(here, "'step' names unknown step %r" % step["step"])
        if op == "expect_move_refused":
            refs = [k for k in ("before", "after") if k in step]
            if step["target"] not in seen or len(refs) != 1 or step[refs[0]] not in seen:
                _fail(here, "'target' and one of 'before' / 'after' must name earlier steps")
        if op in ("expect_bodies", "reopen_check"):
            for step_id, want in step.get("bodies", {}).items():
                if step_id not in seen:
                    _fail(here, "'bodies' names unknown step %r" % step_id)
                if not isinstance(want, dict) or not want or set(want) - _BODY_EXPECT_KEYS:
                    _fail(here, "each body expects some of %s" % sorted(_BODY_EXPECT_KEYS))
            if any(s not in seen for s in step.get("used_up", [])):
                _fail(here, "'used_up' names unknown steps")
            for key in ("followers", "steps"):
                if any(s not in seen for s in step.get(key, {})):
                    _fail(here, "'%s' names unknown steps" % key)
        if "id" in step:
            seen[step["id"]] = op


_validate_before_extrude_bodies = validate


def validate(model):  # noqa: F811  (adds the multi-body extrude checks)
    _validate_before_extrude_bodies(model)
    _check_extrude_bodies(model)
    return model


# -- Direct modeling and the Modify tools (golden/direct_ops.py; sciforge/direct.py,
# replace_face.py, split_face.py, silhouette.py, align.py, remove.py) -------------------------
STEP_KEYS["history_off"] = (set(), {"comment"})
STEP_KEYS["history_on"] = (set(), {"comment"})
STEP_KEYS["replace_face"] = ({"id", "faces", "target"}, {"of", "tangent_chain", "comment"})
STEP_KEYS["split_face"] = (
    {"id", "faces", "tool"},
    {"of", "extend", "split_type", "direction", "comment"},
)
STEP_KEYS["silhouette_split"] = ({"id", "body", "direction"}, {"operation", "comment"})
STEP_KEYS["align_bodies"] = ({"id", "from", "to"}, {"flip", "turns", "comment"})
STEP_KEYS["modify_edit"] = ({"target", "set"}, {"comment"})
STEP_KEYS["remove_bodies"] = ({"steps"}, {"comment"})
SPLIT_FACE_TYPES = ("surface", "vector", "closest")
SILHOUETTE_OPERATIONS = ("faces", "body", "shelled")
MODIFY_STEPS = ("replace_face", "split_face", "silhouette_split", "align_bodies")
_PICK_KEYS = ("face", "edge", "vertex", "body")


def _check_pick(here, name, spec, seen):
    """A pick: an origin plane / axis name, {"face" | "edge" | "vertex": selector, "of": id}
    or {"body": id}."""
    if isinstance(spec, str):
        if spec not in PLANES + AXES:
            _fail(here, "'%s' must be XY/XZ/YZ, X/Y/Z or a face, edge, vertex or body" % name)
        return
    if not isinstance(spec, dict) or len(set(spec) & set(_PICK_KEYS)) != 1:
        _fail(here, "'%s' must name exactly one of %s (or a plane / axis)" % (name, _PICK_KEYS))
    for key in ("of", "body"):
        if key in spec and spec[key] not in seen:
            _fail(here, "'%s' names unknown step %r" % (name, spec[key]))


def _check_direct_steps(model):
    seen = {}
    for i, step in enumerate(model.get("steps", [])):
        here = "%s.steps[%d] (%s)" % (model.get("id", "?"), i, step.get("op"))
        op = step.get("op")
        if op in ("replace_face", "split_face") and "of" in step and step["of"] not in seen:
            _fail(here, "'of' names unknown step %r" % step["of"])
        if op == "replace_face":
            _check_pick(here, "target", step["target"], seen)
        if op == "split_face":
            _check_pick(here, "tool", step["tool"], seen)
            kind = step.get("split_type", "surface")
            if kind not in SPLIT_FACE_TYPES:
                _fail(here, "'split_type' must be one of %s" % (SPLIT_FACE_TYPES,))
            if kind == "vector" and "direction" not in step:
                _fail(here, "Along Vector needs a 'direction'")
            if "direction" in step:
                _check_pick(here, "direction", step["direction"], seen)
        if op == "silhouette_split":
            if step["body"] not in seen:
                _fail(here, "'body' names unknown step %r" % step["body"])
            _check_pick(here, "direction", step["direction"], seen)
            if step.get("operation", "faces") not in SILHOUETTE_OPERATIONS:
                _fail(here, "'operation' must be one of %s" % (SILHOUETTE_OPERATIONS,))
        if op == "align_bodies":
            _check_pick(here, "from", step["from"], seen)
            _check_pick(here, "to", step["to"], seen)
            if "turns" in step and step["turns"] not in (0, 1, 2, 3):
                _fail(here, "'turns' must be 0..3 (quarter turns)")
        if op == "modify_edit":
            if seen.get(step["target"]) not in MODIFY_STEPS:
                _fail(here, "modify_edit must name one of the %s steps" % (MODIFY_STEPS,))
            for key in ("target", "tool", "direction", "from", "to"):
                if key in step["set"]:
                    _check_pick(here, key, step["set"][key], seen)
        if op == "remove_bodies" and (
            not step["steps"] or any(s not in seen for s in step["steps"])
        ):
            _fail(here, "'steps' must name earlier steps")
        if "id" in step:
            seen[step["id"]] = op


# -- SURFACE tab (golden/surface_ops.py: the same code as the SURFACE dialogs) -------------------
STEP_KEYS["sf_surface"] = (
    {"id", "kind"},
    {"refs", "refs2", "refs3", "options", "remove", "cells", "bodies", "target", "comment"},
)
STEP_KEYS["sf_surface_edit"] = ({"target", "set"}, {"comment"})
SURFACE_KINDS = (
    "extrude",
    "revolve",
    "sweep",
    "loft",
    "patch",
    "ruled",
    "offset",
    "boundary_fill",
    "thicken",
    "trim",
    "untrim",
    "extend",
    "stitch",
    "unstitch",
    "reverse_normal",
)
_SURFACE_REF_KEYS = ("sketch", "plane", "axis", "step")


def _check_surface_ref(here, spec, seen):
    if not isinstance(spec, dict) or len(set(spec) & set(_SURFACE_REF_KEYS)) != 1:
        _fail(here, "a reference is one of %s" % (_SURFACE_REF_KEYS,))
    if "faces" in spec and "edges" in spec:
        _fail(here, "a reference picks faces or edges, not both")
    if ("faces" in spec or "edges" in spec) and "step" not in spec:
        _fail(here, "faces / edges are picked on a 'step'")
    if "sketch" in spec and seen.get(spec["sketch"]) not in CURVE_SKETCHES:
        _fail(here, "'sketch' must name an earlier sketch step")
    if "step" in spec and spec["step"] not in seen:
        _fail(here, "'step' must name an earlier step")
    if "plane" in spec and spec["plane"] not in PLANES:
        _fail(here, "'plane' must be one of %s" % (PLANES,))
    if "axis" in spec and spec["axis"] not in AXES:
        _fail(here, "'axis' must be one of %s" % (AXES,))
    if "at" in spec and (not isinstance(spec["at"], list) or len(spec["at"]) != 2):
        _fail(here, "'at' is a sketch point [x, y]")


def _check_surface_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_surface":
            if step["kind"] not in SURFACE_KINDS:
                _fail(here, "'kind' must be one of %s" % (SURFACE_KINDS,))
            for key in ("refs", "refs2", "refs3"):
                for spec in step.get(key, []):
                    _check_surface_ref("%s.%s" % (here, key), spec, seen)
            for item in step.get("remove", []):
                if item.get("step") not in seen or len(item.get("at", [])) != 3:
                    _fail(here, "each 'remove' is {step: an earlier step, at: [x, y, z]}")
            for point in step.get("cells", []):
                if not isinstance(point, list) or len(point) != 3:
                    _fail(here, "each cell is a point [x, y, z] inside it")
            for name in step.get("bodies", []) + ([step["target"]] if "target" in step else []):
                if name not in seen:
                    _fail(here, "%r is not an earlier step" % name)
            if not isinstance(step.get("options", {}), dict):
                _fail(here, "'options' is an object")
        if op == "sf_surface_edit":
            if seen.get(step["target"]) != "sf_surface":
                _fail(here, "'target' must name an earlier sf_surface step")
            if not isinstance(step["set"], dict) or not step["set"]:
                _fail(here, "'set' is a non-empty object")
        if "id" in step:
            seen[step["id"]] = op


_validate_before_direct = validate


def validate(model):  # noqa: F811  (adds the direct-modeling / Modify checks)
    _validate_before_direct(model)
    _check_direct_steps(model)
    return model


_validate_before_surface = validate


def validate(model):  # noqa: F811  (adds the SURFACE checks)
    _validate_before_surface(model)
    _check_surface_steps(model)
    return model


# Fillet / Chamfer options of SciForge's own fillet step (golden/fillet2_ops.py, the code the
# F and Chamfer dialogs use): selection sets, Chord Length, Variable, Tangent Chain off, Rule
# Fillet, Full Round, chamfer sets.
FILLET2_ROW = {
    "edges",
    "faces",
    "features",
    "radius",
    "radius_type",
    "chord",
    "start",
    "end",
    "points",
    "chamfer_type",
    "distance",
    "distance2",
    "angle",
    "flip",
    "tangent_chain",
    "comment",
}
STEP_KEYS["fillet_sets"] = ({"id", "sets"}, {"kind", "tangent_chain", "comment"})
STEP_KEYS["rule_fillet"] = (
    {"id", "radius"},
    {"rule", "faces", "features", "faces2", "features2", "rounds", "fillets", "comment"},
)
STEP_KEYS["full_round"] = ({"id", "faces"}, {"comment"})
STEP_KEYS["blend_radius_expect"] = ({"at", "radius"}, {"tol", "comment"})


def _check_fillet2_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "fillet_sets":
            if step.get("kind", "fillet") not in ("fillet", "chamfer"):
                _fail(here, "'kind' must be fillet or chamfer")
            if not isinstance(step["sets"], list) or not step["sets"]:
                _fail(here, "'sets' is a non-empty list of rows")
            for k, row in enumerate(step["sets"]):
                unknown = set(row) - FILLET2_ROW
                if unknown:
                    _fail("%s.sets[%d]" % (here, k), "unknown keys %s" % sorted(unknown))
                if not ({"edges", "faces", "features"} & set(row)):
                    _fail("%s.sets[%d]" % (here, k), "a row needs edges, faces or features")
                if row.get("radius_type", "constant") not in ("constant", "chord", "variable"):
                    _fail("%s.sets[%d]" % (here, k), "unknown radius_type")
                for name in row.get("features", []):
                    if name not in seen:
                        _fail(here, "%r is not an earlier step" % name)
        if op == "rule_fillet":
            _check_number(here + ".radius", step["radius"], positive=True)
            if step.get("rule", "all") not in ("all", "between"):
                _fail(here, "'rule' must be all or between")
            if not ({"faces", "features"} & set(step)):
                _fail(here, "rule_fillet needs 'faces' and/or 'features'")
            for name in step.get("features", []) + step.get("features2", []):
                if name not in seen:
                    _fail(here, "%r is not an earlier step" % name)
        if op == "full_round":
            if not isinstance(step["faces"], list) or not step["faces"]:
                _fail(here, "'faces' is a list of selectors, one centre face each")
        if op == "blend_radius_expect":
            if not isinstance(step["at"], list) or len(step["at"]) != 3:
                _fail(here, "'at' is a point [x, y, z]")
            _check_number(here + ".radius", step["radius"], positive=True)
        if "id" in step:
            seen[step["id"]] = op


# Whole components (golden/component_ops.py; sciforge/components.py, component_move.py,
# instances.py, component_pattern.py: the same code as their dialogs). components-2.
_COMPONENT_MOVE_KEYS = {"move_type", "dx", "dy", "dz", "rx", "ry", "rz", "pivot", "axis", "angle"}
STEP_KEYS["components_from_bodies"] = ({"id", "bodies"}, {"label", "comment"})
STEP_KEYS["component_move"] = (
    {"id", "components"},
    _COMPONENT_MOVE_KEYS | {"capture", "comment"},
)
STEP_KEYS["component_paste"] = ({"id", "component"}, {"new", "dx", "dy", "dz", "comment"})
STEP_KEYS["component_pattern"] = (
    {"id", "component", "kind"},
    {
        "axis",
        "direction",
        "direction2",
        "quantity",
        "quantity2",
        "distance",
        "distance2",
        "angle",
        "circular_type",
        "distribution",
        "direction_type",
        "direction_type2",
        "comment",
    },
)
STEP_KEYS["measure_components"] = ({"steps"}, {"comment"})
COMPONENT_PATTERN_KINDS = ("rectangular", "circular")


def _check_component_steps(model):
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (model.get("id", "?"), i)
        op = step.get("op")
        if op == "components_from_bodies":
            if not step["bodies"] or any(b not in seen for b in step["bodies"]):
                _fail(here, "'bodies' must name earlier steps")
        if op == "component_move":
            if not step["components"] or any(
                seen.get(c) != "components_from_bodies" and seen.get(c) != "component_paste"
                for c in step["components"]
            ):
                _fail(here, "'components' must name earlier component steps")
            kind = step.get("move_type", "free")
            if kind not in MOVE_TYPES[:3]:
                _fail(here, "'move_type' must be free, translate or rotate")
            if kind == "rotate" and step.get("axis") not in AXES:
                _fail(here, "rotate needs 'axis' X, Y or Z")
            for key in ("dx", "dy", "dz", "rx", "ry", "rz", "angle"):
                if key in step:
                    _check_number(here + "." + key, step[key])
        if op in ("component_paste", "component_pattern"):
            if seen.get(step["component"]) not in ("components_from_bodies", "component_paste"):
                _fail(here, "'component' must name an earlier component step")
        if op == "component_pattern":
            if step["kind"] not in COMPONENT_PATTERN_KINDS:
                _fail(here, "'kind' must be one of %s" % (COMPONENT_PATTERN_KINDS,))
            for key in ("axis", "direction", "direction2"):
                if key in step and step[key] not in AXES:
                    _fail(here, "'%s' must be X, Y or Z" % key)
            if step["kind"] == "circular" and "axis" not in step:
                _fail(here, "a circular pattern needs 'axis'")
            if step["kind"] == "rectangular" and "direction" not in step:
                _fail(here, "a rectangular pattern needs 'direction'")
        if op == "measure_components" and any(s not in seen for s in step["steps"]):
            _fail(here, "measure_components names unknown steps")
        if "id" in step:
            seen[step["id"]] = op


_validate_before_fillet2 = validate


def validate(model):  # noqa: F811  (adds the fillet-2 checks)
    _validate_before_fillet2(model)
    _check_fillet2_steps(model)
    return model


_validate_before_components = validate


def validate(model):  # noqa: F811  (adds the component checks, components-2)
    _validate_before_components(model)
    _check_component_steps(model)
    return model


from . import modify2_schema  # noqa: E402,F401  (Modify part 2 steps; it wraps validate)
from . import gear_schema  # noqa: E402,F401  (Gear steps; it wraps validate)
from . import hardware_schema  # noqa: E402,F401  (Hardware steps; it wraps validate)
from . import sheetmetal_schema  # noqa: E402,F401  (SHEET METAL forming: rules, Flange, Hem, Bend)
from . import flatpattern_schema  # noqa: E402,F401  (SHEET METAL flat: Unfold, Refold, Rip)
from . import plastic_schema  # noqa: E402,F401  (PLASTIC: rules, Boss, Rest)
from . import plastic2_schema  # noqa: E402,F401  (PLASTIC: Snap Fit, Lip)
from . import surface3_schema  # noqa: E402,F401  (SURFACE part 3)
