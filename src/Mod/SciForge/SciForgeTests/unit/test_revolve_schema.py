# SPDX-License-Identifier: LGPL-2.1-or-later
"""The golden-model format of Fusion's Revolve steps (sf_revolve, sf_revolve_edit).
Runs without FreeCAD."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from SciForgeTests.golden import runner, schema  # noqa: E402

GOOD = {
    "id": "t",
    "title": "test",
    "steps": [
        {"op": "sketch", "id": "s1", "plane": "XZ", "geometry": [{"rect": [0, 0, 10, 20]}]},
        {"op": "sf_revolve", "id": "r1", "profile": "s1", "axis": "Z", "type": "full"},
        {"op": "sf_revolve_edit", "target": "r1", "set": {"type": "angle", "angle": 90}},
    ],
    "expect": {"volume": 1, "source": "analytic"},
}


def model(**changes):
    m = copy.deepcopy(GOOD)
    for key, value in changes.items():
        index, name = key.split("__")
        step = m["steps"][int(index)]
        if value is None:
            step.pop(name, None)
        else:
            step[name] = value
    return m


class RevolveSchemaTests(unittest.TestCase):
    def test_good(self):
        schema.validate(copy.deepcopy(GOOD))

    def test_axis_forms(self):
        for axis in (
            "X",
            {"sketch": "s1", "at": [10, 5]},
            {"sketch": "s1", "construction": [[30, 0], [30, 10]]},
            {"sketch": "s1", "axis": "V"},
            {"edge": {"type": "line", "count": 1}},
        ):
            schema.validate(model(**{"1__axis": axis}))

    def test_bad_axes(self):
        for axis in (
            "W",
            {"sketch": "nope", "at": [0, 0]},
            {"sketch": "s1"},
            {"sketch": "s1", "at": [0, 0], "axis": "H"},
            {"sketch": "s1", "axis": "Q"},
            {"sketch": "s1", "construction": [[0, 0]]},
            {"edge": {}, "sketch": "s1"},
            5,
        ):
            with self.assertRaises(schema.ModelError, msg=str(axis)):
                schema.validate(model(**{"1__axis": axis}))

    def test_profile_or_face(self):
        with self.assertRaises(schema.ModelError):
            schema.validate(model(**{"1__profile": None}))
        with self.assertRaises(schema.ModelError):
            schema.validate(model(**{"1__face": {"normal": [1, 0, 0], "count": 1}}))
        schema.validate(model(**{"1__profile": None, "1__face": {"normal": [1, 0, 0]}}))
        with self.assertRaises(schema.ModelError):
            schema.validate(model(**{"1__profile": "r1"}))

    def test_options(self):
        schema.validate(model(**{"1__direction": "two_sides", "1__angle": 90, "1__angle2": 30}))
        schema.validate(model(**{"1__operation": "auto"}))
        for key, value in (
            ("1__type", "to"),
            ("1__direction", "both"),
            ("1__operation", "glue"),
            ("1__angle", 400),
            ("1__angle", "90"),
        ):
            with self.assertRaises(schema.ModelError, msg=key):
                schema.validate(model(**{key: value}))

    def test_edit(self):
        for bad in ({}, {"distance": 3}, {"angle": -500}):
            with self.assertRaises(schema.ModelError, msg=str(bad)):
                schema.validate(model(**{"2__set": bad}))
        with self.assertRaises(schema.ModelError):
            schema.validate(model(**{"2__target": "s1"}))

    def test_model_files(self):
        ids = [m["id"] for m in runner.load_models()]
        for name in (
            "sf_revolve_cylinder",
            "sf_revolve_cone",
            "sf_revolve_torus",
            "sf_revolve_groove_auto_cut",
        ):
            self.assertIn(name, ids)


if __name__ == "__main__":
    unittest.main()
