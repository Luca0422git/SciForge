# SPDX-License-Identifier: LGPL-2.1-or-later
"""The golden-model format used by the Draft of curved walls (draft_walls.py): the sketch
curves "ellipse", "spline_loop" and "segments", and "volume_by": "mesh". Runs without
FreeCAD."""

import copy
import glob
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from SciForgeTests.golden import schema  # noqa: E402

MODELS = os.path.join(os.path.dirname(HERE), "golden", "models")
CURVED = [
    "sf_draft_ellipse_wall",
    "sf_draft_ellipse_wall_flip",
    "sf_draft_ellipse_wall_edit",
    "sf_draft_spline_pocket",
    "sf_draft_tangent_chain",
    "sf_draft_spline_side_corners",
]
GOOD = {
    "id": "t",
    "title": "test",
    "steps": [
        {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"ellipse": [0, 0, 12, 6]}]},
        {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10},
    ],
    "expect": {"volume": 1, "source": "analytic", "volume_by": "mesh", "rel_tol": 1e-4},
}


def with_geometry(item):
    model = copy.deepcopy(GOOD)
    model["steps"][0]["geometry"] = [item]
    return model


class CurvedDraftSchema(unittest.TestCase):
    def test_the_models_are_valid(self):
        names = [os.path.basename(p)[:-5] for p in glob.glob(os.path.join(MODELS, "*.json"))]
        for name in CURVED:
            self.assertIn(name, names)
            with open(os.path.join(MODELS, name + ".json"), encoding="utf-8") as handle:
                model = json.load(handle)
            schema.validate(model)
            self.assertEqual(model["expect"]["volume_by"], "mesh", name)
            self.assertEqual(model["expect"]["source"], "analytic", name)

    def test_curves(self):
        schema.validate(GOOD)
        schema.validate(with_geometry({"spline_loop": [[0, 0], [10, 0], [5, 8]]}))
        schema.validate(
            with_geometry(
                {
                    "segments": [
                        {"line": [0, 0, 10, 0]},
                        {"spline": [[10, 0], [12, 5], [0, 0]], "tangents": [[1, 0], [-1, 0]]},
                    ]
                }
            )
        )

    def test_bad_curves(self):
        bad = [
            {"ellipse": [0, 0, 12]},
            {"ellipse": [0, 0, 6, 12]},  # the major radius goes along X
            {"ellipse": [0, 0, 12, 0]},
            {"spline_loop": [[0, 0], [1, 1]]},
            {"segments": [{"line": [0, 0, 1, 0]}]},
            {"segments": [{"line": [0, 0, 1, 0]}, {"circle": [0, 0, 1]}]},
        ]
        for item in bad:
            with self.assertRaises(schema.ModelError, msg=item):
                schema.validate(with_geometry(item))

    def test_volume_by(self):
        model = copy.deepcopy(GOOD)
        model["expect"]["volume_by"] = "brep"
        schema.validate(model)
        model["expect"]["volume_by"] = "guess"
        with self.assertRaises(schema.ModelError):
            schema.validate(model)


if __name__ == "__main__":
    unittest.main()
