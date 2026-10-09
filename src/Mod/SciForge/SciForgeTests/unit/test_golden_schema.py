# SPDX-License-Identifier: LGPL-2.1-or-later
"""The golden-model files and the format checker. Runs without FreeCAD."""
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
        {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 1, 1]}]},
        {"op": "extrude", "id": "e1", "profile": "s1", "distance": 1},
    ],
    "expect": {"volume": 1, "source": "analytic"},
}


def bad(mutate):
    model = copy.deepcopy(GOOD)
    mutate(model)
    return model


class ModelFilesTests(unittest.TestCase):
    def test_all_model_files_are_valid(self):
        models = runner.load_models()
        self.assertGreaterEqual(len(models), 30, "outline 2.3 asks for at least 30 golden models")

    def test_every_model_says_where_its_numbers_come_from(self):
        for model in runner.load_models():
            self.assertIn(model["expect"]["source"], schema.SOURCES, model["id"])
            self.assertTrue(
                model["expect"].get("note"), "%s: explain the expected values" % model["id"]
            )

    def test_reference_stability_models_exist(self):
        tags = [t for m in runner.load_models() for t in m.get("tags", [])]
        self.assertGreaterEqual(tags.count("reference-stability"), 3)


class SchemaTests(unittest.TestCase):
    def test_good_model_passes(self):
        schema.validate(copy.deepcopy(GOOD))

    def assertRejected(self, model, fragment):
        with self.assertRaises(schema.ModelError) as ctx:
            schema.validate(model)
        self.assertIn(fragment, str(ctx.exception))

    def test_unknown_op(self):
        self.assertRejected(bad(lambda m: m["steps"].append({"op": "sculpt"})), "unknown op")

    def test_profile_must_be_an_earlier_sketch(self):
        self.assertRejected(bad(lambda m: m["steps"][1].update(profile="nope")), "earlier sketch")

    def test_duplicate_ids(self):
        self.assertRejected(bad(lambda m: m["steps"][1].update(id="s1")), "duplicate step id")

    def test_expect_needs_source(self):
        self.assertRejected(bad(lambda m: m["expect"].pop("source")), "source")

    def test_expect_needs_a_measurement(self):
        self.assertRejected(bad(lambda m: m.update(expect={"source": "analytic"})), "at least one")

    def test_extrude_distance_positive(self):
        self.assertRejected(bad(lambda m: m["steps"][1].update(distance=-3)), "must be > 0")

    def test_unknown_step_key(self):
        self.assertRejected(bad(lambda m: m["steps"][1].update(lenght=3)), "does not take")

    def test_edit_target_must_exist(self):
        self.assertRejected(
            bad(lambda m: m["steps"].append({"op": "edit", "target": "zz", "set": {}})),
            "unknown step",
        )

    def test_bad_geometry(self):
        self.assertRejected(
            bad(lambda m: m["steps"][0].update(geometry=[{"circle": [0, 0]}])), "circle"
        )

    def test_unknown_top_level_key(self):
        self.assertRejected(bad(lambda m: m.update(xfial="typo")), "unknown top-level")


class CompareTests(unittest.TestCase):
    GOT = {
        "volume": 100.0,
        "area": 50.0,
        "bbox": [0, 0, 0, 1, 1, 1],
        "faces": 6,
        "edges": 12,
        "solids": 1,
        "valid": True,
    }

    def test_match(self):
        self.assertEqual(
            runner.compare({"volume": 100.0, "faces": 6, "source": "analytic"}, self.GOT), []
        )

    def test_volume_mismatch_reports_percent(self):
        problems = runner.compare({"volume": 90.0, "source": "analytic"}, self.GOT)
        self.assertEqual(len(problems), 1)
        self.assertIn("+11.1111%", problems[0])

    def test_invalid_shape_fails(self):
        got = dict(self.GOT, valid=False)
        self.assertTrue(runner.compare({"volume": 100.0, "source": "analytic"}, got))


if __name__ == "__main__":
    unittest.main()
