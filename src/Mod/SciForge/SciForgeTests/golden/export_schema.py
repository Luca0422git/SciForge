# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model checks for the export report steps (pure Python, unit tested):
export_report_expect and its two test setups, hide_bodies and sketch_extras
(golden/export_checks.py runs them). Imported at the end of schema.py; it adds its step keys
and wraps schema.validate, as hardware_schema does.

  {"op": "export_report_expect", "format": "STEP" | "IGES" | "STL (Binary)" | "STL (ASCII)"
   | "3MF" | "OBJ" | "DXF", "target": null | ["e1", ...] (the steps' bodies) | "k1" (a
   component step) | "s1" (a sketch, for DXF), "expect": {"timeline": 7, ...},
   "unit": "Inch", "per_body": false, "roundtrip": true}
      sciforge/export_report.losses() must list exactly the keys of `expect` with those
      counts; with roundtrip (the default) the file is written and read back to prove the
      claims (what is lost is gone, what is kept is there).
  {"op": "import_report_expect", "file": "open_box.stl" | "two_objects_inch.3mf" |
   "tetra_micron.3mf" | "mixed.step" | "faces.igs" | "extras.dxf" | "extras.svg", "expect": {"open_edges": 4}}
      a file made on the spot (export_checks.make_import_file) is read the way Insert /
      Open read it; what export_report says did not come in must be exactly `expect`.
  {"op": "hide_bodies", "bodies": ["e3"]}       hide the steps' bodies (as the eye icon)
  {"op": "sketch_extras", "target": "s1", "points": [[x, y]], "construction": [[x0, y0, x1,
   y1]], "references": [["e1", "Edge3"]]}       add points / construction lines / projected
                                                reference curves (not defining) to a sketch
"""

from . import schema

FORMATS = ("STEP", "IGES", "STL (Binary)", "STL (ASCII)", "3MF", "OBJ", "DXF")
UNITS = ("Millimeter", "Centimeter", "Meter", "Inch", "Foot")
COMPONENT_OPS = ("components_from_bodies", "component_paste")

schema.STEP_KEYS["export_report_expect"] = (
    {"format", "expect"},
    {"target", "unit", "per_body", "roundtrip", "comment"},
)
schema.STEP_KEYS["hide_bodies"] = ({"bodies"}, {"comment"})
schema.STEP_KEYS["import_report_expect"] = ({"file", "expect"}, {"comment"})
IMPORT_FILES = (
    "open_box.stl",
    "two_objects_inch.3mf",
    "tetra_micron.3mf",
    "mixed.step",
    "faces.igs",
    "extras.dxf",
    "extras.svg",
)
schema.STEP_KEYS["sketch_extras"] = (
    {"target"},
    {"points", "construction", "references", "comment"},
)


def _pairs(here, value, size):
    if not isinstance(value, list) or not all(
        isinstance(v, list) and len(v) == size for v in value
    ):
        schema._fail(here, "a list of [%s] lists" % ", ".join(["n"] * size))
    for i, item in enumerate(value):
        for j, number in enumerate(item):
            schema._check_number("%s[%d][%d]" % (here, i, j), number)


def check_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "export_report_expect":
            if step["format"] not in FORMATS:
                schema._fail(here, "'format' must be one of %s" % (FORMATS,))
            expect = step["expect"]
            if not isinstance(expect, dict) or any(
                not isinstance(k, str) or not isinstance(v, int) or isinstance(v, bool)
                for k, v in expect.items()
            ):
                schema._fail(here, "'expect' is {item key: count}")
            target = step.get("target")
            if isinstance(target, list):
                if not target or any(t not in seen for t in target):
                    schema._fail(here, "'target' names unknown steps")
            elif isinstance(target, str):
                kind = seen.get(target)
                if step["format"] == "DXF":
                    if kind != "sketch":
                        schema._fail(here, "a DXF 'target' must name an earlier sketch")
                elif kind not in COMPONENT_OPS:
                    schema._fail(here, "'target' must name an earlier component step")
            elif target is not None:
                schema._fail(here, "'target' is null, a list of step ids or one step id")
            if step["format"] == "DXF" and not isinstance(target, str):
                schema._fail(here, "DXF needs a sketch 'target'")
            if "unit" in step and step["unit"] not in UNITS:
                schema._fail(here, "'unit' must be one of %s" % (UNITS,))
            for flag in ("per_body", "roundtrip"):
                if flag in step and not isinstance(step[flag], bool):
                    schema._fail(here, "'%s' is true or false" % flag)
        if op == "import_report_expect":
            if step["file"] not in IMPORT_FILES:
                schema._fail(here, "'file' must be one of %s" % (IMPORT_FILES,))
            expect = step["expect"]
            if not isinstance(expect, dict) or any(
                not isinstance(v, int) or isinstance(v, bool) for v in expect.values()
            ):
                schema._fail(here, "'expect' is {item key: count}")
        if op == "hide_bodies":
            if not isinstance(step["bodies"], list) or any(b not in seen for b in step["bodies"]):
                schema._fail(here, "'bodies' names unknown steps")
        if op == "sketch_extras":
            if seen.get(step["target"]) != "sketch":
                schema._fail(here, "'target' must name an earlier sketch")
            if "points" in step:
                _pairs(here + ".points", step["points"], 2)
            if "construction" in step:
                _pairs(here + ".construction", step["construction"], 4)
            refs = step.get("references", [])
            if not isinstance(refs, list) or any(
                not isinstance(r, list)
                or len(r) != 2
                or r[0] not in seen
                or not str(r[1]).startswith(("Edge", "Vertex"))
                for r in refs
            ):
                schema._fail(here, "'references' is [[earlier step id, 'EdgeN'], ...]")
        if "id" in step:
            seen[step["id"]] = op


_validate_before_export = schema.validate


def validate(model):
    _validate_before_export(model)
    check_steps(model)
    return model


schema.validate = validate
