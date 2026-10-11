# SPDX-License-Identifier: LGPL-2.1-or-later
"""The golden-model format of the body-tool steps (combine, split_body, move_bodies,
delete_face, body_tool_edit, measure_bodies). Runs without FreeCAD."""
import copy
import glob
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from SciForgeTests.golden import schema  # noqa: E402

GOOD = {
    "id": "t",
    "title": "test",
    "steps": [
        {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]},
        {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10},
        {"op": "sketch", "id": "s2", "plane": "XY", "geometry": [{"rect": [30, 0, 70, 30]}]},
        {"op": "extrude", "id": "e2", "profile": "s2", "distance": 10, "operation": "new_body"},
        {"op": "combine", "id": "c1", "target": "e1", "tools": ["e2"], "operation": "cut"},
        {"op": "split_body", "id": "x1", "body": "e1", "tool": "YZ"},
        {"op": "move_bodies", "id": "m1", "bodies": ["e1"], "move_type": "translate", "dx": 5},
        {"op": "delete_face", "id": "d1", "faces": {"type": "cylinder", "count": 1}},
        {"op": "body_tool_edit", "target": "c1", "set": {"operation": "join"}},
        {"op": "measure_bodies", "steps": ["e1", "e2"]},
    ],
    "expect": {"volume": 1, "source": "analytic"},
}


def model(index, **changes):
    m = copy.deepcopy(GOOD)
    step = m["steps"][index]
    for key, value in changes.items():
        if value is None:
            step.pop(key, None)
        else:
            step[key] = value
    return m


class BodiesSchemaTests(unittest.TestCase):
    def test_good(self):
        schema.validate(copy.deepcopy(GOOD))

    def test_combine(self):
        for bad in (
            {"target": "nope"},
            {"tools": []},
            {"tools": ["e1"]},
            {"operation": "glue"},
            {"keep": True},
        ):
            with self.assertRaises(schema.ModelError, msg=str(bad)):
                schema.validate(model(4, **bad))
        schema.validate(model(4, new_body=True, keep_tools=True, operation="intersect"))

    def test_split_tools(self):
        for tool in (
            "XZ",
            {"face": {"normal": [0, -1, 0], "count": 1}, "of": "e2"},
            {"body": "e2"},
            {"sketch": "s2", "edge": 1},
        ):
            schema.validate(model(5, tool=tool))
        for tool in (
            "AB",
            {"face": {}, "of": "zz"},
            {"body": "zz"},
            {"plane": "XY"},
            {"sketch": "e1"},
            3,
        ):
            with self.assertRaises(schema.ModelError, msg=str(tool)):
                schema.validate(model(5, tool=tool))

    def test_move(self):
        schema.validate(model(6, move_type="rotate", axis="Z", angle=90))
        schema.validate(
            model(6, move_type="point_to_point", from_point=[0, 0, 0], to_point=[1, 1, 1])
        )
        schema.validate(model(6, move_type="free", rz=90, copy=True))
        for bad in (
            {"move_type": "teleport"},
            {"move_type": "rotate"},
            {"move_type": "rotate", "axis": "W"},
            {"move_type": "point_to_point", "from_point": [0, 0, 0]},
            {"bodies": []},
            {"bodies": ["zz"]},
            {"dx": "far"},
        ):
            with self.assertRaises(schema.ModelError, msg=str(bad)):
                schema.validate(model(6, **bad))

    def test_edit_and_measure(self):
        with self.assertRaises(schema.ModelError):
            schema.validate(model(8, target="e1"))
        with self.assertRaises(schema.ModelError):
            schema.validate(model(9, steps=["zz"]))

    def test_models_on_disk(self):
        folder = os.path.join(os.path.dirname(HERE), "golden", "models")
        paths = sorted(glob.glob(os.path.join(folder, "bodies_*.json")))
        self.assertGreaterEqual(len(paths), 20)
        for path in paths:
            with open(path, encoding="utf-8") as handle:
                schema.validate(json.load(handle))


if __name__ == "__main__":
    unittest.main()
