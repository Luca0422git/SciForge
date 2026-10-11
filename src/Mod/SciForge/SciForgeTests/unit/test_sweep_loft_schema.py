# SPDX-License-Identifier: LGPL-2.1-or-later
"""The golden-model format of the Sweep / Loft / Rib / Web steps (sf_curves, sf_sweep,
sf_sweep_edit, sf_loft, sf_loft_edit, sf_rib, sf_rib_edit). Runs without FreeCAD."""

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
        {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"circle": [0, 0, 2]}]},
        {
            "op": "sf_curves",
            "id": "p1",
            "plane": "XZ",
            "curves": [{"line": [0, 0, 0, 20]}, {"arc": [10, 20, 10, 90, 180]}],
        },
        {"op": "sf_sweep", "id": "w1", "profile": "s1", "path": {"sketch": "p1", "at": [0, 5]}},
        {"op": "sf_sweep_edit", "target": "w1", "set": {"distance": 0.5}},
        {
            "op": "sketch",
            "id": "s2",
            "plane": "XY",
            "offset": 30,
            "geometry": [{"circle": [0, 0, 4]}],
        },
        {"op": "sf_loft", "id": "l1", "profiles": [{"profile": "s1"}, {"profile": "s2"}]},
        {"op": "sf_loft_edit", "target": "l1", "set": {"operation": "new_body"}},
        {"op": "sf_curves", "id": "r", "plane": "XZ", "curves": [{"line": [5, 25, 25, 5]}]},
        {"op": "sf_rib", "id": "rib", "curves": "r", "thickness": 2},
        {"op": "sf_rib_edit", "target": "rib", "set": {"thickness": 3}},
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


class SweepLoftSchemaTests(unittest.TestCase):
    def bad(self, index, **changes):
        with self.assertRaises(schema.ModelError, msg=str(changes)):
            schema.validate(model(index, **changes))

    def test_good(self):
        schema.validate(copy.deepcopy(GOOD))

    def test_curves(self):
        self.bad(1, plane="AB")
        self.bad(1, curves=[])
        self.bad(1, curves=[{"spline": [0, 0]}])
        self.bad(1, curves=[{"line": [0, 0, 1, 1], "arc": [0, 0, 1, 0, 90]}])
        schema.validate(model(1, curves=[{"point": [0, 0]}, {"polyline": [[0, 0], [1, 1]]}]))

    def test_sweep(self):
        self.bad(2, profile=None)
        self.bad(2, face={"type": "plane"})
        self.bad(2, profile="zz")
        self.bad(2, path="zz")
        self.bad(2, path={"sketch": "p1"})
        self.bad(2, path=3)
        self.bad(2, type="rail")
        self.bad(2, distance=1.5)
        self.bad(2, orientation="sideways")
        self.bad(2, scaling="squash")
        self.bad(2, operation="glue")
        self.bad(2, taper="steep")
        schema.validate(model(2, type="rail", rail="p1", scaling="stretch"))
        schema.validate(model(2, path={"edge": {"type": "line"}}, twist=45, taper=-5))
        schema.validate(model(2, profile=None, face={"type": "plane", "count": 1}))

    def test_sweep_edit(self):
        self.bad(3, target="l1")
        self.bad(3, set={})
        self.bad(3, set={"path": "p1"})
        self.bad(3, set={"distance2": -0.1})

    def test_loft(self):
        self.bad(5, profiles=[{"profile": "s1"}])
        self.bad(5, profiles=[{"profile": "s1"}, {"profile": "zz"}])
        self.bad(5, profiles=[{"profile": "s1"}, {"profile": "s2", "face": {}}])
        self.bad(5, rails=["zz"])
        self.bad(5, centerline={"sketch": "zz", "at": [0, 0]})
        self.bad(5, guide="spine")
        self.bad(5, closed="yes")
        schema.validate(
            model(
                5,
                profiles=[{"profile": "s1"}, {"point": {"sketch": "p1", "at": [0, 20]}}],
                rails=["p1"],
                closed=False,
            )
        )
        schema.validate(model(5, centerline="p1", guide="centerline", operation="cut"))

    def test_loft_edit(self):
        self.bad(6, target="w1")
        self.bad(6, set={"profiles": []})
        self.bad(6, set={"guide": "spine"})

    def test_rib(self):
        self.bad(8, curves="zz")
        self.bad(8, kind="gusset")
        self.bad(8, thickness=0)
        self.bad(8, thickness_side="both")
        self.bad(8, depth_type="all")
        self.bad(8, depth=-1)
        self.bad(8, flip="no")
        self.bad(8, extend=1)
        schema.validate(
            model(8, kind="web", thickness_side="one_side", flip_side=True, depth_type="depth")
        )

    def test_rib_edit(self):
        self.bad(9, target="w1")
        self.bad(9, set={"kind": "web"})
        self.bad(9, set={"thickness": -2})

    def test_models_on_disk(self):
        folder = os.path.join(os.path.dirname(HERE), "golden", "models")
        counts = {}
        for prefix in ("sf_sweep_", "sf_loft_", "sf_rib_", "sf_web_"):
            paths = sorted(glob.glob(os.path.join(folder, prefix + "*.json")))
            counts[prefix] = len(paths)
            for path in paths:
                with open(path, encoding="utf-8") as handle:
                    schema.validate(json.load(handle))
        self.assertEqual(
            counts, {"sf_sweep_": 14, "sf_loft_": 9, "sf_rib_": 6, "sf_web_": 6}, counts
        )


if __name__ == "__main__":
    unittest.main()
