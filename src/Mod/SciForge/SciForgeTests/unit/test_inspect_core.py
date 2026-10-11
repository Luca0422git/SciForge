# SPDX-License-Identifier: LGPL-2.1-or-later
"""CONSTRUCT / INSPECT logic that runs without FreeCAD: the measure text, the construct
entries and the golden-model steps for them."""
import glob
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import construct, measure, ribbon_config as cfg  # noqa: E402
from SciForgeTests.golden import schema  # noqa: E402

KINDS = {"plane", "line", "point", "face", "curved", "round", "center", "path"}


class MeasureTextTest(unittest.TestCase):
    def test_millimetres(self):
        self.assertEqual(measure.fmt(1121.46, "area", 3, "mm"), "1121.460 mm^2")
        self.assertEqual(measure.fmt(40, "length", 1, "mm"), "40.0 mm")
        self.assertEqual(measure.fmt(12785.3981634, "volume", 3, "mm"), "12785.398 mm^3")

    def test_design_units(self):
        self.assertEqual(measure.fmt(25.4, "length", 2, "in"), "1.00 in")
        self.assertEqual(measure.fmt(1000.0, "volume", 1, "cm"), "1.0 cm^3")
        self.assertEqual(measure.fmt(100.0, "area", 2, "cm"), "1.00 cm^2")
        self.assertEqual(measure.fmt(2500.0, "coordinate", 1, "m"), "2.5 m")

    def test_angles_ignore_units(self):
        self.assertEqual(measure.fmt(90, "angle", 3, "in"), "90.000 deg")

    def test_no_negative_zero(self):
        self.assertEqual(measure.fmt(-0.0001, "length", 3, "mm"), "0.000 mm")

    def test_precision_list(self):
        self.assertEqual(measure.PRECISIONS[measure.DEFAULT_PRECISION], "0.123")
        for decimals, text in enumerate(measure.PRECISIONS):
            self.assertEqual(len(text.split(".")[1]) if "." in text else 0, decimals)


class ConstructSpecsTest(unittest.TestCase):
    def test_every_entry_is_built(self):
        for key, spec in construct.SPECS.items():
            self.assertTrue(callable(getattr(construct, "_c_" + key, None)), key)
            self.assertIn(spec["type"], construct.DATUM_TYPES, key)
            self.assertTrue(spec["inputs"], key)
            for item in spec["inputs"]:
                self.assertTrue(item["kinds"] <= KINDS, (key, item))
                self.assertTrue(item["hint"], key)
            self.assertIn(spec["value"], (None, "distance", "angle", "path"), key)

    def test_required_inputs(self):
        self.assertEqual(len(construct.required("AxisNormal")), 1)
        self.assertEqual(len(construct.required("PlaneThreePoints")), 3)
        self.assertEqual(construct.NEEDS["Midplane"], 2)

    def test_ribbon_runs_construct_entries(self):
        group = [g for g in cfg.TABS[0]["groups"] if g["id"] == "construct"][0]
        names = [e["command"] for e in cfg.iter_items(group["items"]) if e["command"]]
        mine = [n for n in names if isinstance(n, str) and n.startswith("SciForge_Construct_")]
        self.assertGreaterEqual(len(mine), 19)
        for name in mine:
            self.assertIn(name[len("SciForge_Construct_") :], construct.SPECS)

    def test_inspect_ribbon_items(self):
        group = [g for g in cfg.TABS[0]["groups"] if g["id"] == "inspect"][0]
        by_label = {e["label"]: e["command"] for e in cfg.iter_items(group["items"])}
        self.assertEqual(by_label["Interference"], "SciForge_Interference")
        self.assertEqual(by_label["Center of Mass"], "SciForge_CenterOfMass")
        self.assertIn("SciForge_SectionAnalysis", by_label["Section Analysis"])
        self.assertIn("SciForge_Measure", by_label["Measure"])


class InspectGoldenStepsTest(unittest.TestCase):
    def _model(self, steps):
        return {
            "id": "t",
            "title": "t",
            "steps": [
                {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 1, 1]}]},
                {"op": "extrude", "id": "e1", "profile": "s1", "distance": 1},
            ]
            + steps,
            "expect": {"volume": 1, "source": "analytic"},
        }

    def test_valid_steps(self):
        model = self._model(
            [
                {"op": "construct", "id": "p1", "preset": "OffsetPlane", "refs": [{"plane": "XY"}]},
                {"op": "construct_expect", "target": "p1", "point": [0, 0, 1], "normal": [0, 0, 1]},
                {
                    "op": "construct_extrude",
                    "id": "e2",
                    "plane": "p1",
                    "circles": [[0.5, 0.5, 1, 0.2]],
                    "distance": 1,
                },
                {"op": "measure_expect", "a": {"axis": "Z"}, "b": {"construct": "p1"}, "angle": 90},
                {"op": "section_expect", "plane": {"plane": "XZ"}, "kept_volume": 1},
                {"op": "com_expect", "features": ["e1"], "point": [0.5, 0.5, 0.5]},
                {"op": "interference_expect", "features": ["e1", "e2"], "volume": 0},
            ]
        )
        schema.validate(model)

    def test_bad_pick(self):
        model = self._model(
            [{"op": "construct", "id": "p1", "preset": "OffsetPlane", "refs": [{"plane": "QQ"}]}]
        )
        with self.assertRaises(schema.ModelError):
            schema.validate(model)

    def test_unknown_construct_target(self):
        model = self._model([{"op": "construct_expect", "target": "nope", "point": [0, 0, 0]}])
        with self.assertRaises(schema.ModelError):
            schema.validate(model)

    def test_section_needs_a_check(self):
        model = self._model([{"op": "section_expect", "plane": {"plane": "XY"}}])
        with self.assertRaises(schema.ModelError):
            schema.validate(model)

    def test_model_files(self):
        here = os.path.join(ROOT, "SciForgeTests", "golden", "models")
        paths = sorted(glob.glob(os.path.join(here, "inspect_*.json")))
        self.assertGreaterEqual(len(paths), 6)
        for path in paths:
            with open(path, encoding="utf-8") as handle:
                schema.validate(json.load(handle))


if __name__ == "__main__":
    unittest.main()
