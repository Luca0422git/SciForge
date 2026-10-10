# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model format for Extrude's Fusion options (regions, start, to object,
intersect, ...). Runs without FreeCAD."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from SciForgeTests.golden import schema  # noqa: E402

BASE = {
    "id": "t",
    "title": "test",
    "steps": [
        {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 4, 4]}]},
        {"op": "sketch", "id": "s2", "plane": "XY", "geometry": [{"rect": [5, 0, 9, 4]}]},
        {"op": "extrude", "id": "e1", "profile": "s1", "distance": 1},
    ],
    "expect": {"volume": 1, "source": "analytic"},
}


def model(**extrude):
    m = copy.deepcopy(BASE)
    m["steps"][-1].update(extrude)
    return m


class ExtrudeOptionsTests(unittest.TestCase):
    def ok(self, **extrude):
        schema.validate(model(**extrude))

    def fails(self, text, **extrude):
        with self.assertRaises(schema.ModelError) as ctx:
            schema.validate(model(**extrude))
        self.assertIn(text, str(ctx.exception))

    def test_regions_are_points(self):
        self.ok(regions=[[1, 1], [2, 2]])
        self.fails("[x, y]", regions=[[1, 1, 1]])
        self.fails("list of [x, y]", regions=[])

    def test_more_profiles_must_be_sketches(self):
        self.ok(more_profiles=["s2"])
        self.fails("more_profiles", more_profiles=["nope"])

    def test_operations(self):
        for op in ("join", "cut", "intersect", "new_body"):
            self.ok(operation=op)
        self.fails("operation", operation="glue")

    def test_to_object_needs_a_target(self):
        self.ok(extent="to_object", to={"plane": "XY"})
        self.ok(extent="to_object", to={"face": {"normal": [0, 0, 1], "count": 1}})
        self.ok(extent="to_object", to={"step": "e1"})
        self.fails("to", extent="to_object")
        self.fails("plane", extent="to_object", to={"plane": "XX"})
        self.fails("extent", extent="up_to")

    def test_start(self):
        self.ok(start="offset", start_offset=-3)
        self.ok(start="object", start_from={"plane": "XY"})
        self.fails("start_offset", start="offset")
        self.fails("start_from", start="object")
        self.fails("start", start="middle")

    def test_measurement_and_second_side(self):
        self.ok(direction="symmetric", measurement="half")
        self.fails("measurement", direction="symmetric", measurement="quarter")
        self.ok(direction="two_sides", distance2=2, extent2="through_all", taper2=-5)
        self.ok(direction="two_sides", distance2=2, extent2="to_object", to2={"plane": "XY"})
        self.fails("to2", direction="two_sides", distance2=2, extent2="to_object")


if __name__ == "__main__":
    unittest.main()
