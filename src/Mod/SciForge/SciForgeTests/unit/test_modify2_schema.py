# SPDX-License-Identifier: LGPL-2.1-or-later
"""The golden-model format of the Modify part 2 steps (Pattern Compute Option and Start Point,
Draft Two Side / Symmetric / Parting Line, Shell / Draft / Scale over several bodies, Scale of a
sketch, Move of faces, Press Pull Offset Type). Runs without FreeCAD."""

import copy
import glob
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from SciForgeTests.golden import schema  # noqa: E402

SIDES = {"type": "plane", "normal": [1, 0, 0]}
TOP = {"type": "plane", "normal": [0, 0, 1], "count": 1}
GOOD = {
    "id": "t",
    "title": "test",
    "steps": [
        {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]},
        {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10},
        {"op": "sketch", "id": "s2", "plane": "XY", "geometry": [{"rect": [50, 0, 70, 30]}]},
        {"op": "extrude", "id": "e2", "profile": "s2", "distance": 10, "operation": "new_body"},
        {
            "op": "rectangular_pattern",
            "id": "p1",
            "features": ["e1"],
            "direction": "X",
            "quantity": 2,
            "distance": 10,
            "compute": "adjust",
        },
        {
            "op": "path_pattern",
            "id": "p2",
            "features": ["e1"],
            "path": {"sketch": "s1"},
            "start_point": 0.25,
        },
        {
            "op": "sf_draft2",
            "id": "d1",
            "faces": SIDES,
            "plane": "XY",
            "draft_type": "parting",
            "parting": "XY",
            "sides": "two",
            "angle": 5,
            "angle2": 3,
        },
        {"op": "sf_draft2_edit", "target": "d1", "set": {"sides": "symmetric"}},
        {
            "op": "sf_shell_bodies",
            "id": "sh",
            "bodies": [{"body": "e1", "faces": TOP}, {"body": "e2"}],
        },
        {"op": "sf_scale_bodies", "id": "sc", "bodies": ["e1", "e2"], "factor": 2},
        {"op": "sf_scale_sketch", "id": "ss", "sketch": "s1", "factor": 1.5},
        {"op": "sf_scale_sketch_edit", "target": "ss", "factor": 2},
        {"op": "move_face", "id": "mf", "faces": TOP, "move": [0, 0, 5]},
        {"op": "move_face_edit", "target": "mf", "rotate": {"axis": [0, 1, 0], "angle": 5}},
        {"op": "press_pull_type", "id": "pp", "faces": TOP, "distance": 2, "offset_type": "modify"},
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


class Modify2SchemaTests(unittest.TestCase):
    def test_good(self):
        schema.validate(copy.deepcopy(GOOD))

    def bad(self, index, **changes):
        with self.assertRaises(schema.ModelError, msg=str(changes)):
            schema.validate(model(index, **changes))

    def test_compute_option(self):
        self.bad(4, compute="fast")
        schema.validate(model(4, compute="optimized"))
        schema.validate(model(4, compute="identical"))
        schema.validate(model(4, compute=None))

    def test_start_point(self):
        self.bad(5, start_point=1.5)
        self.bad(5, start_point=-0.1)
        self.bad(5, start_point="half")
        schema.validate(model(5, start_point=0.0))
        schema.validate(model(5, start_point=1.0))

    def test_start_point_only_on_path(self):
        self.bad(4, start_point=0.5)

    def test_draft(self):
        self.bad(6, sides="three")
        self.bad(6, draft_type="moving")
        self.bad(6, parting=None)  # a Parting Line draft needs its parting tool
        self.bad(6, angle="five")
        self.bad(6, plane=None)
        schema.validate(model(6, draft_type="fixed", parting=None))

    def test_draft_edit(self):
        self.bad(7, target="e1")
        self.bad(7, set={"sides": "four"})

    def test_bodies(self):
        self.bad(8, bodies=[])
        self.bad(8, bodies=[{"body": "nope"}])
        self.bad(9, bodies=["e1", "zz"])
        self.bad(9, factors=[1, 2, 3])  # factor and factors together
        schema.validate(model(9, factor=None, factors=[1, 2, 3]))

    def test_sketch_scale(self):
        self.bad(10, sketch="e1")
        self.bad(10, factor=0)
        self.bad(11, target="s1")
        self.bad(11, factor=-1)

    def test_move_face(self):
        self.bad(12, move=[0, 5])
        self.bad(12, move=None)
        self.bad(13, target="e1")
        self.bad(13, rotate={"axis": [0, 1, 0]})

    def test_offset_type(self):
        self.bad(14, offset_type="edit")
        schema.validate(model(14, offset_type="new"))
        schema.validate(model(14, offset_type="automatic"))

    def test_models_on_disk(self):
        folder = os.path.join(os.path.dirname(HERE), "golden", "models")
        found = sorted(glob.glob(os.path.join(folder, "modify2_*.json")))
        self.assertGreaterEqual(len(found), 20)
        for path in found:
            with open(path) as handle:
                schema.validate(json.load(handle))


if __name__ == "__main__":
    unittest.main()
