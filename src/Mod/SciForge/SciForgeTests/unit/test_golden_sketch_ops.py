# SPDX-License-Identifier: LGPL-2.1-or-later
"""Format checks for the golden steps of the SKETCH tab tools (sketch_polygon,
sketch_trim). Runs without FreeCAD."""

import copy
import os
import sys
import unittest

# The module root (src/Mod/SciForge) holds the SciForgeTests package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from SciForgeTests.golden import runner, schema  # noqa: E402

GOOD = {
    "id": "t",
    "title": "test",
    "steps": [
        {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [-5, -5, 5, 5]}]},
        {
            "op": "sketch_polygon",
            "sketch": "s1",
            "center": [0, 0],
            "point": [0, 2],
            "sides": 6,
            "circumscribed": True,
            "diameter": 4,
            "name": "nut",
        },
        {"op": "sketch_trim", "sketch": "s1", "points": [[0, 5]]},
        {"op": "extrude", "id": "e1", "profile": "s1", "distance": 1},
    ],
    "expect": {"volume": 1, "source": "analytic"},
}


def bad(mutate):
    model = copy.deepcopy(GOOD)
    mutate(model)
    return model


class SketchStepTests(unittest.TestCase):
    def assertRejected(self, model, fragment):
        with self.assertRaises(schema.ModelError) as ctx:
            schema.validate(model)
        self.assertIn(fragment, str(ctx.exception))

    def test_good_model_passes(self):
        schema.validate(copy.deepcopy(GOOD))

    def test_sketch_must_be_an_earlier_sketch(self):
        self.assertRejected(bad(lambda m: m["steps"][1].update(sketch="e1")), "earlier sketch")
        self.assertRejected(bad(lambda m: m["steps"][2].update(sketch="nope")), "earlier sketch")

    def test_polygon_needs_three_sides(self):
        self.assertRejected(bad(lambda m: m["steps"][1].update(sides=2)), "'sides'")
        self.assertRejected(bad(lambda m: m["steps"][1].update(sides=4.5)), "'sides'")

    def test_polygon_diameter_positive(self):
        self.assertRejected(bad(lambda m: m["steps"][1].update(diameter=0)), "must be > 0")

    def test_polygon_needs_its_points(self):
        self.assertRejected(bad(lambda m: m["steps"][1].pop("point")), "missing")

    def test_trim_unknown_key(self):
        self.assertRejected(bad(lambda m: m["steps"][2].update(curve=1)), "does not take")

    def test_sketch_tool_models_exist(self):
        ops = {s["op"] for m in runner.load_models() for s in m["steps"]}
        self.assertIn("sketch_polygon", ops)
        self.assertIn("sketch_trim", ops)


if __name__ == "__main__":
    unittest.main()
