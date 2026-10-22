# SPDX-License-Identifier: LGPL-2.1-or-later
"""Calls EVERY AI tool of the catalogue (sciforge/ai/catalog) at least once, in real FreeCAD
without a window, through the headless backend (sciforge/ai/headless.py: the same executor
the app's AI bridge uses), and checks each answer: what was made, the volumes, the files
written, the plain-sentence errors. The tools that need the SciForge window are called too
and must answer that they need it.

    freecadcmd -c "from SciForgeTests.headless import runner; runner.main()"

tools/sciforge/run_tests.sh runs it with --only base (and --only headless). It writes
headless-report.json / .md to SCIFORGE_HEADLESS_OUT (default: FreeCAD's user data folder);
SCIFORGE_HEADLESS_FILTER runs only the calls whose label contains that text (the calls
before them still run, they build what the later ones need).

A session is a list of calls, each {"tool", "args", "save": a name for the id the answer
reports, "expect": "ok" | "error", "contains": [texts], "check": function(answer, run)}.
"$name" in the arguments is replaced by the id saved under that name.
"""

import json
import math
import os
import platform
import re
import tempfile
import time
import traceback

TOP = {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}
TOP4 = {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}
BOTTOM4 = {"type": "line", "at": {"axis": "z", "value": "min"}, "count": 4}
SIDES4 = {"along": [0, 0, 1], "type": "plane", "count": 4}


class Run:
    """The state of one session: saved ids, the temporary folder, results."""

    def __init__(self, folder):
        from sciforge.ai import headless

        self.folder = folder
        self.host = headless.HeadlessHost(allow_overwrite=False)
        self.ids = {}
        self.called = set()
        self.results = []
        self.broken = set()

    def path(self, name):
        return os.path.join(self.folder, name)

    # helpers the checks use
    def doc(self):
        import FreeCAD as App

        return App.ActiveDocument

    def obj(self, name):
        doc = self.doc()
        ident = self.ids.get(name, name)
        found = doc.getObject(ident) if doc is not None else None
        if found is None and doc is not None:
            labels = [o for o in doc.Objects if o.Label == ident]
            found = labels[0] if labels else None
        return found

    def body_volume(self, name):
        from sciforge import bodies

        obj = self.obj(name)
        body = obj if bodies.is_body(obj) else bodies.body_of(obj)
        return body.Shape.Volume if body is not None and not body.Shape.isNull() else None


def json_of(answer):
    text = answer["text"]
    start = text.find("{")
    return json.loads(text[start:]) if start >= 0 else None


def _substitute(value, ids):
    if isinstance(value, str) and value.startswith("$"):
        return ids.get(value[1:], value[1:])
    if isinstance(value, str) and "{tmp}" in value:
        return value
    if isinstance(value, dict):
        return {k: _substitute(v, ids) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, ids) for v in value]
    return value


def _paths(value, folder):
    if isinstance(value, str) and "{tmp}" in value:
        return value.replace("{tmp}", folder)
    if isinstance(value, dict):
        return {k: _paths(v, folder) for k, v in value.items()}
    if isinstance(value, list):
        return [_paths(v, folder) for v in value]
    return value


def close(expected, rel=1e-6):
    def check(got):
        if got is None or abs(got - expected) > rel * max(1.0, abs(expected)):
            return "expected %.9g, got %s" % (expected, got)
        return None

    return check


# -- the session ------------------------------------------------------------------------------
def _volume(name, expected, rel=1e-6):
    def check(answer, run):
        return close(expected, rel)(run.body_volume(name))

    return check


def _volume_between(name, low, high):
    def check(answer, run):
        got = run.body_volume(name)
        if got is None or not low < got < high:
            return "volume %s not between %g and %g" % (got, low, high)
        return None

    return check


def _json_check(fn):
    def check(answer, run):
        data = json_of(answer)
        if data is None:
            return "no JSON in the answer"
        return fn(data, run)

    return check


def _file(name, min_size=1):
    def check(answer, run):
        path = run.path(name)
        if not os.path.isfile(path) or os.path.getsize(path) < min_size:
            return "%s was not written" % path
        return None

    return check


def _all(*checks):
    def check(answer, run):
        for fn in checks:
            problem = fn(answer, run)
            if problem:
                return problem
        return None

    return check


def _inspected(data, run):
    body = data["bodies"][0] if data.get("bodies") else {}
    if not body.get("valid") or body.get("solids") != 1:
        return "the plate is not one valid solid: %s" % body
    if body["bbox_mm"]["size"] != [40.0, 30.0, 10.0]:
        return "the plate is %s" % body["bbox_mm"]["size"]
    if not any(s.get("definition") for s in data["timeline"]):
        return "detail full gave no step definitions"
    if data["summary"]["failed_steps"]:
        return "failed steps %s" % data["summary"]["failed_steps"]
    run.ids["snapshot"] = data["snapshot"]
    return None


def _hole_face(data, run):
    if data["count"] != 1:
        return "%d faces of radius 3" % data["count"]
    row = data["elements"][0]
    if row["type"] != "cylinder" or abs(row["radius_mm"] - 3) > 1e-9 or not row.get("ref"):
        return "the hole's face: %s" % row
    run.ids["hole_pick"] = row["pick"]
    return None


def _every_ref(data, run):
    missing = [r["name"] for r in data["elements"] if not r.get("ref")]
    return "no ref for %s" % missing if missing or not data["elements"] else None


def _later_steps(data, run):
    later = [s["id"] for s in data["later_steps"]]
    if run.ids["hole"] not in later or "volume_mm3" not in data["changes"]:
        return "later steps %s, changes %s" % (later, data["changes"])
    return None


def _picture(width, height):
    def check(answer, run):
        import base64

        from sciforge.ai import render_core

        if not answer.get("image_png_base64"):
            return "no picture"
        size = render_core.png_info(base64.b64decode(answer["image_png_base64"]))
        return None if size == (width, height) else "the picture is %s" % (size,)

    return check


HOLE = 12000.0 - math.pi * 9.0 * 10.0  # 40 x 30 x 10 plate, a 6 mm hole through it

SESSION = [
    # -- before any design ------------------------------------------------------------------------
    {
        "tool": "list_tools",
        "args": {},
        "check": _json_check(
            lambda d, r: None if d["count"] >= 100 else "only %d tools" % d["count"]
        ),
    },
    {"tool": "get_help", "args": {"topic": "selectors"}, "contains": ["selector"]},
    {"tool": "get_help", "args": {}, "contains": ["SciForge"]},
    {"tool": "get_help", "args": {"topic": "docs"}, "contains": ["docs_search"]},
    {
        "tool": "docs_search",
        "args": {"query": "fillet radius too big", "limit": 3},
        "check": _json_check(lambda d, r: None if d["results"] else "docs_search found nothing"),
    },
    {
        "tool": "docs_read",
        "args": {"path": "handbook.md", "section": "units-and-coordinates"},
        "contains": ["Units and coordinates", "millimetres"],
    },
    {
        "tool": "docs_read",
        "args": {"path": "nothing.md"},
        "expect": "error",
        "contains": ["There is no document"],
    },
    {
        "tool": "examples_search",
        "args": {"query": "flange bolt circle", "limit": 3},
        "contains": ["flange-bolt-pattern"],
    },
    {"tool": "get_design", "args": {}, "contains": ["No design is open"]},
    {"tool": "inspect_design", "args": {}, "contains": ["No design is open"]},
    {"tool": "list_designs", "args": {}},
    {"tool": "list_materials", "args": {}, "contains": ["aluminium", "plastic_red"]},
    {
        "tool": "fillet",
        "args": {"edges": TOP4, "radius": 1},
        "expect": "error",
        "contains": ["No design is open"],
    },
    {
        "tool": "extrude",
        "args": {"profile": "x"},
        "expect": "error",
        "contains": ["distance is missing"],
    },
    {"tool": "new_design", "args": {"name": "HeadlessTools"}, "contains": ["HeadlessTools"]},
    # -- a plate with a hole, rounded and chamfered --------------------------------------------------
    {
        "tool": "create_sketch",
        "save": "s_plate",
        "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 40, 30], "name": "base"}]},
    },
    {
        "tool": "extrude",
        "save": "plate",
        "args": {"profile": "$s_plate", "distance": 10},
        "check": _volume("plate", 12000.0),
    },
    {
        "tool": "create_sketch",
        "save": "s_hole",
        "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [20, 15, 3]}]},
    },
    {
        "tool": "hole",
        "save": "hole",
        "args": {"sketch": "$s_hole", "diameter": 6, "through_all": True},
        "check": _volume("plate", HOLE),
    },
    {
        "tool": "fillet",
        "save": "fillet",
        "args": {"edges": TOP4, "radius": 2},
        "check": _volume_between("plate", HOLE - 200, HOLE - 1),
    },
    {"tool": "chamfer", "save": "chamfer", "args": {"edges": BOTTOM4, "distance": 1}},
    {
        "tool": "get_design",
        "args": {},
        "check": _json_check(
            lambda d, r: (
                None if len(d["bodies"]) == 1 and d["timeline"] else "bodies %s" % d["bodies"]
            )
        ),
    },
    {
        "tool": "get_timeline",
        "args": {},
        "check": _json_check(
            lambda d, r: (
                None
                if any(s["id"] == r.ids["hole"] for s in d["steps"])
                else "the hole is not in the timeline"
            )
        ),
    },
    {"tool": "get_step", "args": {"step": "$plate"}, "contains": ["definition", "distance"]},
    {
        "tool": "edit_step",
        "args": {"step": "$plate", "set": {"distance": 12}},
        "check": _volume_between("plate", HOLE, 15000),
    },
    {"tool": "edit_step", "args": {"step": "$plate", "set": {"distance": 10}}},
    {"tool": "edit_step", "args": {"step": "$fillet", "set": {"radius": 1.5}}},
    {"tool": "set_parameter", "args": {"name": "width", "value": 40, "unit": "mm"}},
    {
        "tool": "set_sketch_dimension",
        "args": {"sketch": "$s_plate", "constraint": "base.width", "expression": "width"},
    },
    {"tool": "set_parameter", "args": {"name": "width", "value": 50}},
    {
        "tool": "get_sketch",
        "args": {"sketch": "$s_plate"},
        "check": _json_check(
            lambda d, r: (
                None
                if abs(d["geometry"][0]["length"] - 50) < 1e-6
                else "the rectangle is %s long" % d["geometry"][0]["length"]
            )
        ),
    },
    {"tool": "set_parameter", "args": {"name": "width", "value": 40}},
    {"tool": "list_parameters", "args": {}, "contains": ["width", "Distance"]},
    {"tool": "set_model_parameter", "args": {"step": "$plate", "label": "Distance", "value": 10}},
    {"tool": "set_parameter", "args": {"name": "unused", "value": "width / 4"}},
    {"tool": "delete_parameter", "args": {"name": "unused"}},
    {
        "tool": "delete_parameter",
        "args": {"name": "width"},
        "expect": "error",
        "contains": ["used by"],
    },
    {
        "tool": "measure",
        "args": {"a": {"face": TOP}, "b": {"plane": "XY"}},
        "contains": ["distance 10 mm"],
    },
    {
        "tool": "physical_properties",
        "args": {},
        "check": _json_check(lambda d, r: None if d["bodies"][0]["valid"] else "not valid"),
    },
    {
        "tool": "physical_material",
        "args": {"body": "$plate", "material": "aluminium"},
        "contains": ["Aluminium"],
    },
    {"tool": "appearance", "args": {"body": "$plate", "look": "plastic_red"}},
    {"tool": "appearance", "args": {"faces": TOP, "color": [0.1, 0.3, 0.8]}},
    {"tool": "center_of_mass", "args": {}, "contains": ["Centre of mass"]},
    {
        "tool": "section_analysis",
        "args": {"plane": {"plane": "XZ"}, "distance": -15},
        "check": _json_check(
            lambda d, r: (
                None
                if d["bodies"][0]["cut_area_mm2"] > 100 and d["plane_point_mm"][1] == 15
                else "the cut through the middle of the plate: %s" % d
            )
        ),
    },
    # -- the checking tools (sciforge/ai/actions/verify_actions.py) --------------------------------
    {"tool": "inspect_design", "args": {"detail": "full"}, "check": _json_check(_inspected)},
    {
        "tool": "query_geometry",
        "args": {"select": {"type": "cylinder", "radius": 3}},
        "check": _json_check(_hole_face),
    },
    {
        "tool": "measure",
        "args": {"a": "$hole_pick"},
        "contains": ["Measured a (face)", "radius 3 mm"],
    },
    {
        "tool": "query_geometry",
        "args": {"element": "edges", "select": {"at": {"axis": "z", "value": "max"}}},
        "check": _json_check(_every_ref),
    },
    {
        "tool": "query_geometry",
        "args": {
            "of": "$plate",
            "element": "vertices",
            "select": {"at": {"axis": "z", "value": "min"}},
        },
        "check": _json_check(
            lambda d, r: None if d["count"] == 4 else "%d corners at the bottom" % d["count"]
        ),
    },
    {
        "tool": "query_geometry",
        "args": {"select": {"type": "torus", "count": 1}},
        "expect": "error",
        "contains": ["does not fit"],
    },
    {
        "tool": "check_design",
        "args": {},
        "check": _json_check(lambda d, r: None if d["ok"] else "not ok: %s" % d["problems"]),
    },
    {"tool": "diff_design", "args": {"since": "$snapshot"}, "contains": ["nothing changed"]},
    {
        "tool": "diff_design",
        "args": {"since": "$plate"},
        "check": _json_check(_later_steps),
    },
    {
        "tool": "diff_design",
        "args": {"since": "S999"},
        "expect": "error",
        "contains": ["no snapshot"],
    },
    {
        "tool": "render",
        "args": {
            "width": 320,
            "height": 240,
            "highlight": {"faces": {"type": "cylinder", "radius": 3}},
        },
        "check": _picture(320, 240),
        "contains": ["software renderer", "in orange"],
    },
    {
        "tool": "render",
        "args": {"view": "top", "renderer": "window"},
        "expect": "error",
        "contains": ["needs the SciForge window"],
    },
    {"tool": "undo", "args": {}, "contains": ["Undo"]},
    {"tool": "redo", "args": {}, "contains": ["Redo"]},
    {"tool": "suppress_step", "args": {"steps": ["$chamfer"]}, "contains": ["Suppressed"]},
    {
        "tool": "suppress_step",
        "args": {"steps": ["$chamfer"], "suppress": False},
        "contains": ["Unsuppressed"],
    },
    {"tool": "roll_timeline", "args": {"after": "$plate"}, "contains": ["after"]},
    {"tool": "roll_timeline", "args": {"to": "end"}, "contains": ["at the end"]},
    {"tool": "move_step", "args": {"step": "$fillet", "after": "$chamfer"}, "contains": ["Moved"]},
    {
        "tool": "rename",
        "args": {"target": "$plate", "name": "Base plate"},
        "contains": ["Base plate"],
    },
    {
        "tool": "group_steps",
        "save_group": "group",
        "args": {"steps": ["$chamfer", "$fillet"], "name": "Edges"},
        "contains": ["Grouped"],
    },
    {
        "tool": "group_steps",
        "args": {"ungroup": True, "group": "$group"},
        "contains": ["Ungrouped"],
    },
    {
        "tool": "pattern",
        "save": "pattern",
        "args": {
            "kind": "rectangular",
            "features": ["$hole"],
            "direction": "Y",
            "count": 2,
            "spacing": 8,
        },
    },
    {
        "tool": "rectangular_pattern",
        "save": "rpattern",
        "args": {
            "features": ["$hole"],
            "direction": "X",
            "quantity": 2,
            "distance": 8,
            "distribution": "spacing",
        },
    },
    {
        "tool": "create_curve_sketch",
        "save": "path_line",
        "args": {"plane": "XY", "offset": 10, "curves": [{"line": [20, 15, 8, 15]}]},
    },
    {
        "tool": "pattern_on_path",
        "save": "ppattern",
        "args": {
            "features": ["$hole"],
            "path": {"sketch": "$path_line"},
            "quantity": 2,
            "distance": 10,
            "distribution": "spacing",
        },
    },
    {
        "tool": "create_sketch",
        "save": "s_label",
        "args": {"plane": "XY", "offset": 15, "geometry": [{"center_rect": [30, 8, 6, 3]}]},
    },
    {
        "tool": "emboss",
        "save": "emboss",
        "args": {"sketch": "$s_label", "faces": TOP, "depth": 0.5},
    },
    {
        "tool": "insert_hardware",
        "save": "screw",
        "args": {"face": TOP, "at": [8, 22, 10], "standard": "iso4762", "size": "3", "length": 8},
    },
    {"tool": "delete_step", "args": {"steps": ["$screw"]}, "contains": ["Deleted"]},
    # -- sketch editing -------------------------------------------------------------------------------
    {
        "tool": "create_sketch",
        "save": "s_edit",
        "args": {"plane": "XY", "offset": -20, "geometry": [{"line": [0, 0, 10, 1]}]},
    },
    {
        "tool": "sketch_constraint",
        "args": {"sketch": "$s_edit", "kind": "horizontal", "items": [{"curve": 0}]},
    },
    {
        "tool": "sketch_constraint",
        "expect": "error",
        "args": {"sketch": "$s_edit", "kind": "vertical", "items": [{"curve": 0}]},
        "contains": ["Vertical: not added"],
    },
    {
        "tool": "sketch_dimension",
        "args": {
            "sketch": "$s_edit",
            "kind": "distance",
            "items": [{"curve": 0}],
            "value": 12,
            "name": "len",
        },
    },
    {
        "tool": "add_to_sketch",
        "args": {
            "sketch": "$s_edit",
            "geometry": [{"circle": [30, 0, 4]}, {"circle": [30, 0, 2]}],
            "curves": [{"line": [40, -5, 40, 5]}, {"line": [35, 0, 45, 0]}],
        },
    },
    {
        "tool": "sketch_constraint",
        "expect": "error",
        "args": {"sketch": "$s_edit", "kind": "concentric", "items": [{"curve": 1}, {"curve": 2}]},
        "contains": ["conflicts with"],
    },
    {
        "tool": "add_to_sketch",
        "args": {"sketch": "$s_edit", "curves": [{"circle": [70, 30, 4]}, {"circle": [71, 31, 2]}]},
    },
    {
        "tool": "sketch_constraint",
        "args": {"sketch": "$s_edit", "kind": "concentric", "items": [{"curve": 5}, {"curve": 6}]},
    },
    {
        "tool": "set_sketch_dimension",
        "args": {"sketch": "$s_edit", "constraint": "len", "value": 15},
        "contains": ["15"],
    },
    {"tool": "sketch_trim", "args": {"sketch": "$s_edit", "points": [[44, 0]]}},
    {
        "tool": "sketch_polygon",
        "args": {
            "sketch": "$s_edit",
            "center": [60, 0],
            "point": [65, 0],
            "sides": 6,
            "diameter": 10,
            "name": "nut",
        },
    },
    {"tool": "get_sketch", "args": {"sketch": "$s_edit"}, "contains": ["nut.diameter"]},
    {
        "tool": "sketch_delete",
        "args": {"sketch": "$s_edit", "constraints": [0]},
        "contains": ["deleted"],
    },
    {
        "tool": "sketch_text",
        "save": "text",
        "args": {"sketch": "$s_edit", "text": "SF", "height": 5, "corner": [0, 20]},
    },
    # -- more solids, each in a body of its own ----------------------------------------------------------
    {
        "tool": "primitive",
        "save": "box2",
        "args": {
            "kind": "box",
            "plane": "XY",
            "x": 100,
            "y": 0,
            "length": 20,
            "width": 20,
            "height": 20,
            "operation": "new_body",
        },
        "check": _volume("box2", 8000.0),
    },
    {
        "tool": "press_pull",
        "args": {"faces": TOP, "distance": 5},
        "check": _volume("box2", 10000.0),
    },
    {
        "tool": "fillet_sets",
        "args": {
            "sets": [{"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4}, "radius": 2}]
        },
    },
    {
        "tool": "shell",
        "args": {"faces": TOP, "inside": 1.5, "shell_type": "sharp"},
        "check": _volume_between("box2", 1000, 4000),
    },
    {
        "tool": "primitive",
        "save": "cyl",
        "args": {
            "kind": "cylinder",
            "plane": "XY",
            "x": -60,
            "y": 0,
            "diameter": 20,
            "height": 30,
            "operation": "new_body",
        },
    },
    {"tool": "thread", "args": {"faces": {"type": "cylinder", "count": 1}}},
    {
        "tool": "construct_axis",
        "save": "axis",
        "args": {"preset": "AxisCylinder", "refs": [{"face": {"type": "cylinder", "count": 1}}]},
    },
    {
        "tool": "construct_point",
        "save": "point",
        "args": {
            "preset": "PointCenter",
            "refs": [{"edge": {"type": "circle", "at": {"axis": "z", "value": "max"}, "count": 1}}],
        },
    },
    {
        "tool": "split_face",
        "args": {"faces": {"type": "cylinder", "count": 1}, "of": "$cyl", "tool": "XZ"},
    },
    {
        "tool": "construct_plane",
        "save": "plane",
        "args": {"preset": "OffsetPlane", "refs": [{"plane": "XY"}], "distance": 40},
    },
    {
        "tool": "create_sketch",
        "save": "s_on_plane",
        "args": {"on": "$plane", "geometry": [{"circle": [-60, 0, 3]}]},
    },
    {
        "tool": "primitive",
        "save": "wall",
        "args": {
            "kind": "box",
            "plane": "XY",
            "x": 0,
            "y": 100,
            "length": 4,
            "width": 20,
            "height": 10,
            "operation": "new_body",
        },
    },
    {
        "tool": "full_round_fillet",
        "args": {"faces": [{"normal": [0, 1, 0], "count": 1}]},
        "check": _volume("wall", 800.0 - 10.0 * (8.0 - math.pi * 2.0)),
    },
    {
        "tool": "primitive",
        "save": "block",
        "args": {
            "kind": "box",
            "plane": "XY",
            "x": 50,
            "y": 100,
            "length": 20,
            "width": 20,
            "height": 10,
            "operation": "new_body",
        },
    },
    {
        "tool": "rule_fillet",
        "args": {"radius": 0.5, "features": ["$block"]},
        "check": _volume_between("block", 3900, 3999.9),
    },
    {
        "tool": "primitive",
        "save": "block2",
        "args": {
            "kind": "box",
            "plane": "XY",
            "x": 50,
            "y": 150,
            "length": 20,
            "width": 20,
            "height": 10,
            "operation": "new_body",
        },
    },
    {
        "tool": "draft",
        "args": {"plane": "XY", "faces": SIDES4, "angle": 3},
        "check": _volume_between("block2", 3000, 3999.9),
    },
    {"tool": "scale", "args": {"factor": 1.5}},
    {
        "tool": "create_sketch",
        "save": "s_ring",
        "args": {"plane": "XZ", "geometry": [{"rect": [10, 0, 15, 10]}]},
    },
    {
        "tool": "revolve",
        "save": "ring",
        "args": {"profile": "$s_ring", "axis": "Z", "operation": "new_body"},
        "check": _volume("ring", math.pi * (225 - 100) * 10),
    },
    {"tool": "interference", "args": {}, "contains": ["overlap"]},
    {
        "tool": "create_sketch",
        "save": "s_swp",
        "args": {"plane": "XY", "geometry": [{"circle": [200, 0, 2]}]},
    },
    {
        "tool": "create_curve_sketch",
        "save": "s_path",
        "args": {"plane": "XZ", "curves": [{"line": [200, 0, 200, 30]}]},
    },
    {
        "tool": "sweep",
        "save": "sweep",
        "args": {"profile": "$s_swp", "path": "$s_path", "operation": "new_body"},
        "check": _volume("sweep", math.pi * 4 * 30, 1e-4),
    },
    {
        "tool": "create_sketch",
        "save": "s_loft1",
        "args": {"plane": "XY", "geometry": [{"center_rect": [300, 0, 20, 20]}]},
    },
    {
        "tool": "create_sketch",
        "save": "s_loft2",
        "args": {"plane": "XY", "offset": 20, "geometry": [{"circle": [300, 0, 8]}]},
    },
    {
        "tool": "loft",
        "save": "loft",
        "args": {
            "profiles": [{"profile": "$s_loft1"}, {"profile": "$s_loft2"}],
            "operation": "new_body",
        },
    },
    {
        "tool": "create_sketch",
        "save": "s_tray",
        "args": {"plane": "XY", "geometry": [{"rect": [380, -20, 420, 20]}]},
    },
    {
        "tool": "extrude",
        "save": "tray",
        "args": {"profile": "$s_tray", "distance": 10, "operation": "new_body"},
    },
    {
        "tool": "create_sketch",
        "save": "s_pocket",
        "args": {"plane": "XY", "offset": 10, "geometry": [{"rect": [382, -18, 418, 18]}]},
    },
    {
        "tool": "extrude",
        "args": {"profile": "$s_pocket", "distance": 8, "flip": True, "operation": "cut"},
    },
    {
        "tool": "create_curve_sketch",
        "save": "s_web",
        "args": {
            "plane": "XY",
            "offset": 10,
            "curves": [{"line": [390, 0, 410, 0]}, {"line": [400, -10, 400, 10]}],
        },
    },
    {"tool": "web", "args": {"curves": "$s_web"}},
    {
        "tool": "create_sketch",
        "save": "s_gusset",
        "args": {
            "plane": "XZ",
            "geometry": [
                {"polyline": [[450, 0], [490, 0], [490, 5], [455, 5], [455, 40], [450, 40]]}
            ],
        },
    },
    {
        "tool": "extrude",
        "save": "gusset",
        "args": {"profile": "$s_gusset", "distance": 20, "operation": "new_body"},
    },
    {
        "tool": "create_curve_sketch",
        "save": "s_rib",
        "args": {"plane": "XZ", "offset": 10, "curves": [{"line": [455, 25, 475, 5]}]},
    },
    {
        "tool": "rib",
        "args": {"curves": "$s_rib", "thickness": 2},
        "check": _volume_between(
            "gusset", 20 * (40 * 5 + 5 * 35) + 1, 20 * (40 * 5 + 5 * 35) + 400
        ),
    },
    {
        "tool": "coil",
        "save": "coil",
        "args": {
            "plane": "XY",
            "x": 500,
            "y": 0,
            "diameter": 20,
            "revolutions": 3,
            "height": 15,
            "section_size": 2,
            "operation": "new_body",
        },
    },
    {
        "tool": "create_curve_sketch",
        "save": "s_pipe",
        "args": {"plane": "XY", "curves": [{"line": [600, 0, 600, 40]}]},
    },
    {
        "tool": "pipe",
        "save": "pipe",
        "args": {
            "path": {"sketch": "$s_pipe", "edge": 1},
            "section_size": 4,
            "operation": "new_body",
        },
        "check": _volume("pipe", math.pi * 4 * 40, 1e-4),
    },
    {
        "tool": "gear",
        "save": "gear",
        "args": {"x": 700, "module": 1, "teeth": 20, "thickness": 5, "hole": 5},
    },
    {
        "tool": "move_copy",
        "args": {"bodies": ["$gear"], "move_type": "translate", "dx": 10},
        "contains": ["Done"],
    },
    {
        "tool": "primitive",
        "save": "sphere",
        "args": {
            "kind": "sphere",
            "plane": "XY",
            "x": 800,
            "y": 0,
            "diameter": 20,
            "operation": "new_body",
        },
    },
    {
        "tool": "silhouette_split",
        "args": {"body": "$sphere", "direction": "Z", "operation": "body"},
    },
    {
        "tool": "primitive",
        "save": "low",
        "args": {
            "kind": "box",
            "plane": "XY",
            "x": 900,
            "y": 0,
            "length": 20,
            "width": 20,
            "height": 10,
            "operation": "new_body",
        },
    },
    {
        "tool": "primitive",
        "save": "high",
        "args": {
            "kind": "box",
            "plane": "XY",
            "x": 930,
            "y": 0,
            "length": 20,
            "width": 20,
            "height": 15,
            "operation": "new_body",
        },
    },
    {
        "tool": "replace_face",
        "args": {"faces": TOP, "of": "$low", "target": {"face": TOP, "of": "$high"}},
        "check": _volume("low", 6000.0),
    },
    {
        "tool": "move_copy",
        "args": {"faces": {"normal": [1, 0, 0], "count": 1}, "dx": 2},
        "check": _volume("low", 22 * 20 * 15),
    },
    {
        "tool": "align",
        "args": {
            "from": {"face": {"normal": [0, 0, -1], "count": 1}, "of": "$low"},
            "to": {"face": TOP, "of": "$high"},
        },
    },
    {
        "tool": "primitive",
        "save": "plate2",
        "args": {
            "kind": "box",
            "plane": "XY",
            "x": 1000,
            "y": 0,
            "length": 20,
            "width": 20,
            "height": 10,
            "operation": "new_body",
        },
    },
    {
        "tool": "hole",
        "save": "hole2",
        "args": {"face": TOP, "at": [1010, 10, 10], "diameter": 5, "extent": "all"},
        "check": _volume("plate2", 4000 - math.pi * 6.25 * 10),
    },
    {
        "tool": "delete_face",
        "args": {"faces": {"type": "cylinder", "count": 1}},
        "check": _volume("plate2", 4000.0),
    },
    {"tool": "split_body", "args": {"body": "$ring", "tool": "YZ"}},
    {"tool": "circular_pattern", "args": {"body": True, "axis": "Z", "quantity": 2}, "check": None},
    {"tool": "activate", "args": {"target": "$plate"}, "contains": ["active body"]},
    {"tool": "mirror", "args": {"body": True, "plane": "YZ", "operation": "new_body"}},
    {
        "tool": "combine",
        "args": {"target": "$cyl", "tools": ["$sweep"], "operation": "join", "keep_tools": True},
        "expect": "any",
    },
    {"tool": "new_body", "args": {"label": "Spare"}, "contains": ["Spare"]},
    {"tool": "remove_bodies", "args": {"bodies": ["$loft"]}},
    {"tool": "delete_bodies", "args": {"bodies": ["$gear"]}},
    {"tool": "show_hide", "args": {"targets": ["$s_plate"], "visible": False}, "contains": ["Hid"]},
    # -- surfaces -------------------------------------------------------------------------------------
    {
        "tool": "create_curve_sketch",
        "save": "s_surf",
        "args": {"plane": "XY", "offset": 50, "curves": [{"line": [0, -50, 30, -50]}]},
    },
    {
        "tool": "surface",
        "save": "surf",
        "args": {
            "kind": "extrude",
            "refs": [{"sketch": "$s_surf", "at": [15, -50]}],
            "options": {"distance": 10},
        },
    },
    {
        "tool": "surface",
        "args": {"kind": "thicken", "refs": [{"step": "$surf"}], "options": {"thickness": 1}},
    },
    # -- assembly ---------------------------------------------------------------------------------------
    {
        "tool": "new_component",
        "save_component": "comp",
        "args": {"label": "Bracket"},
        "contains": ["Bracket"],
    },
    {
        "tool": "create_sketch",
        "save": "s_br",
        "args": {"plane": "XY", "offset": 100, "geometry": [{"circle": [0, 0, 10]}]},
    },
    {"tool": "extrude", "save": "br", "args": {"profile": "$s_br", "distance": 5}},
    {
        "tool": "components_from_bodies",
        "save": "cup",
        "args": {"bodies": ["$box2"], "label": "Cup"},
    },
    {"tool": "copy_component", "save": "cup2", "args": {"component": "$cup", "dx": 60}},
    {"tool": "ground", "args": {"component": "Bracket"}, "contains": ["grounded"]},
    {
        "tool": "joint",
        "save_joint": "joint",
        "args": {
            "type": "revolute",
            "first": {
                "component": "$cup",
                "face": {"normal": [0, 0, -1], "count": 1},
                "snap": "centre",
            },
            "second": {"component": "Bracket", "face": TOP, "snap": "centre"},
        },
    },
    {"tool": "drive_joint", "args": {"joint": "$joint", "angle": 30}, "contains": ["angle"]},
    {
        "tool": "pattern_components",
        "args": {
            "component": "$cup",
            "kind": "rectangular",
            "direction": "Y",
            "quantity": 2,
            "distance": 40,
        },
    },
    {
        "tool": "move_copy",
        "args": {"components": ["$cup2"], "move_type": "translate", "dz": 5},
        "expect": "any",
    },
    # -- drawings ---------------------------------------------------------------------------------------
    {
        "tool": "create_drawing",
        "save_drawing": "drawing",
        "args": {"bodies": ["$plate"], "base_view": "Front", "projected": ["Top", "Right"]},
        "contains": ["drawing"],
    },
    {"tool": "get_drawing", "args": {"edges": True}, "contains": ["views", "elements"]},
    {
        "tool": "add_drawing_view",
        "args": {"kind": "projected", "parent": "BaseView", "direction": "FrontTopRight"},
    },
    {
        "tool": "add_drawing_view",
        "args": {"kind": "section", "parent": "BaseView", "line": [[-30, 0], [30, 0]]},
        "expect": "any",
    },
    {
        "tool": "add_drawing_dimension",
        "args": {"view": "BaseView", "picks": [{"kind": "line", "near": [0, 5]}]},
        "contains": ["dimension"],
    },
    {
        "tool": "add_drawing_annotation",
        "args": {"kind": "text", "text": "Break sharp edges", "at": [30, 30]},
    },
    {
        "tool": "export_drawing",
        "args": {"format": "dxf", "path": "{tmp}/drawing.dxf"},
        "check": _file("drawing.dxf"),
        # what the DXF leaves out (export_report, as the drawing's Export message)
        "contains": ["Not kept in this file:", "as plain lines and text"],
    },
    {
        "tool": "export_drawing",
        "args": {"format": "pdf", "path": "{tmp}/drawing.pdf"},
        "expect": "error",
        "contains": ["window"],
    },
    # -- the window's tools say they need it --------------------------------------------------------
    {"tool": "screenshot", "args": {}, "expect": "error", "contains": ["window"]},
    {"tool": "set_view", "args": {"orientation": "top"}, "expect": "error", "contains": ["window"]},
    {"tool": "get_view", "args": {}, "expect": "error", "contains": ["window"]},
    {"tool": "named_view", "args": {"action": "list"}},
    {
        "tool": "named_view",
        "args": {"action": "save", "name": "Top"},
        "expect": "error",
        "contains": ["3D view"],
    },
    # -- files ------------------------------------------------------------------------------------------
    {"tool": "save", "args": {}, "expect": "error", "contains": ["never been saved"]},
    {"tool": "save_as", "args": {"path": "{tmp}/tools.FCStd"}, "check": _file("tools.FCStd")},
    {"tool": "save", "args": {}, "contains": ["Saved"]},
    {"tool": "save", "args": {"path": "{tmp}/tools.FCStd"}, "contains": ["Saved"]},
    {
        "tool": "export",
        "args": {"format": "step", "path": "{tmp}/all.step"},
        "check": _file("all.step"),
        "contains": ["Not kept in this file:", "- the timeline ("],
    },
    {
        "tool": "export",
        "args": {"format": "step", "path": "{tmp}/all.step"},
        "expect": "error",
        "contains": ["already exists"],
    },
    {
        "tool": "export",
        "args": {"format": "stl", "path": "{tmp}/plate.stl", "bodies": ["$plate"]},
        "check": _file("plate.stl"),
        "contains": ["Not kept in this file:", "- the timeline ("],
    },
    {
        "tool": "export",
        "args": {"format": "3mf", "path": "{tmp}/plate.3mf", "bodies": ["$plate"]},
        "check": _file("plate.3mf"),
    },
    {
        "tool": "export",
        "args": {"format": "obj", "path": "{tmp}/plate.obj", "bodies": ["$plate"]},
        "check": _file("plate.obj"),
    },
    {
        "tool": "export",
        "args": {"format": "iges", "path": "{tmp}/plate.igs", "bodies": ["$plate"]},
        "check": _file("plate.igs"),
    },
    {
        "tool": "export",
        "args": {"format": "brep", "path": "{tmp}/plate.brep", "bodies": ["$plate"]},
        "check": _file("plate.brep"),
        "contains": ["BREP holds unnamed shapes"],
    },
    {
        "tool": "export",
        "args": {"format": "dxf", "path": "{tmp}/sketch.dxf", "sketch": "$s_plate"},
        "check": _file("sketch.dxf"),
    },
    {"tool": "list_designs", "args": {}, "contains": ["HeadlessTools"]},
    {"tool": "new_design", "args": {"name": "Imports"}},
    {"tool": "import_file", "args": {"path": "{tmp}/plate.stl"}, "contains": ["mesh body"]},
    {"tool": "import_file", "args": {"path": "{tmp}/sketch.dxf"}, "contains": ["curves"]},
    {"tool": "import_file", "args": {"path": "{tmp}/plate.igs"}, "contains": ["Inserted"]},
    {
        "tool": "import_file",
        "args": {"path": "{tmp}/tools.FCStd"},
        "expect": "error",
        "contains": ["Save this design first"],
    },
    {"tool": "save_as", "args": {"path": "{tmp}/imports.FCStd"}},
    {"tool": "import_file", "args": {"path": "{tmp}/tools.FCStd"}, "contains": ["linked"]},
    {"tool": "capture_design_history", "args": {"on": False}},
    {"tool": "capture_design_history", "args": {"on": True}},
    {"tool": "switch_design", "args": {"design": "tools"}, "contains": ["tools"]},
    {
        "tool": "close_design",
        "args": {"design": "imports"},
        "expect": "error",
        "contains": ["unsaved changes"],
    },
    {
        "tool": "close_design",
        "args": {"design": "imports", "discard_changes": True},
        "contains": ["Closed"],
    },
    {"tool": "open_design", "args": {"path": "{tmp}/all.step"}, "contains": ["Opened"]},
    {"tool": "open_design", "args": {"path": "{tmp}/tools.FCStd"}, "contains": ["Opened"]},
]


def _ids_from(answer):
    match = re.search(r"Its id is '([^']+)'", answer["text"])
    if match:
        return match.group(1)
    match = re.search(r"\(id '([^']+)'\)", answer["text"])
    return match.group(1) if match else None


def run_session(run, session=SESSION, text_filter=""):
    from sciforge.ai import headless

    for i, entry in enumerate(session):
        tool = entry["tool"]
        args = _paths(_substitute(entry.get("args", {}), run.ids), run.folder)
        label = "%03d %s" % (i, tool)
        start = time.time()
        problems = []
        try:
            answer = headless.call(tool, args, run.host)
        except Exception as exc:  # executor.run never raises: this would be a bug
            answer = {
                "text": "raised: %s\n%s" % (exc, traceback.format_exc()),
                "is_error": True,
                "image_png_base64": None,
            }
            problems.append("the call raised")
        run.called.add(tool)
        expect = entry.get("expect", "ok")
        if expect == "ok" and answer["is_error"]:
            problems.append("failed: %s" % answer["text"][:600])
        if expect == "error" and not answer["is_error"]:
            problems.append("should have failed: %s" % answer["text"][:300])
        if expect in ("ok", "error"):
            for text in entry.get("contains", []):
                if text not in answer["text"]:
                    problems.append("the answer lacks %r: %s" % (text, answer["text"][:400]))
        made = _ids_from(answer)
        for key in ("save", "save_component", "save_drawing", "save_joint", "save_group"):
            if key in entry and not answer["is_error"]:
                if key == "save_group":
                    match = re.search(r"group id '([^']+)'", answer["text"])
                    made = match.group(1) if match else None
                if made:
                    run.ids[entry[key]] = made
                else:
                    problems.append("no id in the answer: %s" % answer["text"][:200])
        check = entry.get("check")
        if check is not None and not problems and not answer["is_error"]:
            try:
                problem = check(answer, run)
            except Exception as exc:
                problem = "check raised %s" % exc
            if problem:
                problems.append(problem)
        if answer["is_error"] and expect == "error" and not answer["text"].strip():
            problems.append("an error without words")
        broken = _broken_objects(run)
        newly = sorted(set(broken) - run.broken)
        run.broken = set(broken)
        if text_filter and text_filter not in label:
            continue
        run.results.append(
            {
                "newly_broken": newly,
                "label": label,
                "tool": tool,
                "status": "fail" if problems else "pass",
                "problems": problems,
                "answer": answer["text"][:1000],
                "is_error": answer["is_error"],
                "seconds": round(time.time() - start, 3),
            }
        )


def _broken_objects(run):
    """Every object of the active design whose state is Invalid / Error (helpers too)."""
    doc = run.doc()
    if doc is None:
        return []
    found = []
    for obj in doc.Objects:
        try:
            state = list(obj.State)
        except Exception:
            continue
        if "Invalid" in state or "Error" in state:
            found.append("%s/%s" % (doc.Name, obj.Label))
    return found


def missing_tools(run):
    from sciforge.ai import catalog

    return sorted(set(catalog.TOOL_NAMES) - run.called)


def markdown(report):
    lines = [
        "# Headless AI tools report",
        "",
        "FreeCAD %s, %s. %d calls, %d tools: %s"
        % (
            report["freecad"],
            report["platform"],
            len(report["results"]),
            report["tools_called"],
            "PASS" if report["passed"] else "FAIL",
        ),
        "",
    ]
    if report["missing"]:
        lines += ["Tools never called: %s" % ", ".join(report["missing"]), ""]
    lines += ["| Call | Result | Time (s) | Details |", "|---|---|---|---|"]
    for r in report["results"]:
        detail = (
            "; ".join(r["problems"]) or r["answer"].splitlines()[0][:160] if r["answer"] else ""
        )
        lines.append(
            "| %s | %s | %.2f | %s |"
            % (
                r["label"],
                r["status"].upper(),
                r["seconds"],
                detail.replace("|", "/").replace("\n", " "),
            )
        )
    return "\n".join(lines) + "\n"


def main():
    import FreeCAD as App

    out_dir = os.environ.get("SCIFORGE_HEADLESS_OUT") or App.getUserAppDataDir()
    os.makedirs(out_dir, exist_ok=True)
    folder = tempfile.mkdtemp(prefix="sciforge-headless-")
    report = {
        "freecad": ".".join(App.Version()[:3]),
        "platform": platform.platform(),
        "folder": folder,
        "results": [],
    }
    try:
        run = Run(folder)
        run_session(run, SESSION, os.environ.get("SCIFORGE_HEADLESS_FILTER", ""))
        report["results"] = run.results
        report["missing"] = [] if os.environ.get("SCIFORGE_HEADLESS_FILTER") else missing_tools(run)
        report["tools_called"] = len(run.called)
    except Exception as exc:
        report["results"].append(
            {
                "label": "session",
                "tool": "",
                "status": "fail",
                "problems": ["%s\n%s" % (exc, traceback.format_exc())],
                "answer": "",
                "is_error": True,
                "seconds": 0,
            }
        )
        report["missing"] = []
        report["tools_called"] = 0
    report["passed"] = not report["missing"] and all(
        r["status"] == "pass" for r in report["results"]
    )
    for r in report["results"]:
        App.Console.PrintMessage(
            "[SciForge] headless %s %s %s\n"
            % (r["status"].upper(), r["label"], "; ".join(r["problems"])[:800])
        )
    if report["missing"]:
        App.Console.PrintMessage("[SciForge] headless MISSING %s\n" % ", ".join(report["missing"]))
    with open(os.path.join(out_dir, "headless-report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    with open(os.path.join(out_dir, "headless-report.md"), "w", encoding="utf-8") as handle:
        handle.write(markdown(report))
    App.Console.PrintMessage(
        "[SciForge] headless summary: %d calls, %d failed, %d tools called, %d missing\n"
        % (
            len(report["results"]),
            len([r for r in report["results"] if r["status"] != "pass"]),
            report["tools_called"],
            len(report["missing"]),
        )
    )
    return report
