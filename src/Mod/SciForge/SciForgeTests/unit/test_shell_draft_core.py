# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shell / Draft / Scale: the option logic of sciforge/shelling.py and the golden-model
format of their steps (sf_shell, sf_draft, sf_scale and their _edit). Runs without
FreeCAD."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from SciForgeTests.golden import schema  # noqa: E402
from sciforge import shelling  # noqa: E402

BOX = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10},
]
TOP = {"normal": [0, 0, 1], "count": 1}


def model(*steps):
    return {
        "id": "t",
        "title": "test",
        "steps": copy.deepcopy(BOX) + list(steps),
        "expect": {"volume": 1, "source": "analytic"},
    }


class ShellOptionTests(unittest.TestCase):
    def test_defaults_like_fusion(self):
        opts = shelling.default_options()
        self.assertEqual(opts["direction"], "inside")
        self.assertEqual(opts["shell_type"], "sharp")
        self.assertTrue(opts["tangent"])

    def test_thicknesses_follow_direction(self):
        opts = {"inside": 2.0, "outside": 1.0}
        self.assertEqual(shelling.thicknesses(dict(opts, direction="inside")), (2.0, 0.0))
        self.assertEqual(shelling.thicknesses(dict(opts, direction="outside")), (0.0, 1.0))
        self.assertEqual(shelling.thicknesses(dict(opts, direction="both")), (2.0, 1.0))

    def test_which_feature(self):
        # FreeCAD's Thickness: faces taken away, one side. SciForge's: hollow, or Both.
        self.assertFalse(shelling.needs_own_feature(["Face6"], {"direction": "inside"}))
        self.assertFalse(shelling.needs_own_feature(["Face6"], {"direction": "outside"}))
        self.assertTrue(shelling.needs_own_feature(["Face6"], {"direction": "both"}))
        self.assertTrue(shelling.needs_own_feature([], {"direction": "inside"}))

    def test_bad_options(self):
        with self.assertRaises(shelling.ShellError):
            shelling.with_defaults({"direction": "sideways"})
        with self.assertRaises(shelling.ShellError):
            shelling.with_defaults({"shell_type": "wavy"})

    def test_messages_are_plain(self):
        self.assertIn("thinner", shelling.too_thick("inside", 20))
        self.assertIn("thinner", shelling.friendly("Failed to make thick solid"))


class ShellDraftScaleSchemaTests(unittest.TestCase):
    def test_good_models(self):
        schema.validate(model({"op": "sf_shell", "id": "a", "faces": TOP, "inside": 2}))
        schema.validate(model({"op": "sf_shell", "id": "a", "body": True, "direction": "both"}))
        schema.validate(
            model(
                {"op": "sf_shell", "id": "a", "faces": TOP},
                {"op": "sf_shell_edit", "target": "a", "set": {"shell_type": "rounded"}},
            )
        )
        schema.validate(model({"op": "sf_draft", "id": "d", "plane": "XY", "faces": TOP}))
        schema.validate(
            model(
                {"op": "sf_draft", "id": "d", "plane": {"face": TOP}, "faces": TOP, "angle": 3},
                {"op": "sf_draft_edit", "target": "d", "set": {"flip": True}},
            )
        )
        schema.validate(model({"op": "sf_scale", "id": "c", "factor": 2}))
        schema.validate(
            model(
                {"op": "sf_scale", "id": "c", "factors": [2, 1, 0.5], "point": [40, 30, 10]},
                {"op": "sf_scale_edit", "target": "c", "set": {"factor": 1.5}},
            )
        )

    def test_bad_models(self):
        bad = [
            {"op": "sf_shell", "id": "a"},  # neither faces nor body
            {"op": "sf_shell", "id": "a", "faces": TOP, "body": True},
            {"op": "sf_shell", "id": "a", "faces": TOP, "direction": "up"},
            {"op": "sf_shell", "id": "a", "faces": TOP, "inside": 0},
            {"op": "sf_shell", "id": "a", "faces": TOP, "shell_type": "soft"},
            {"op": "sf_draft", "id": "d", "plane": "AB", "faces": TOP},
            {"op": "sf_draft", "id": "d", "plane": {"edge": TOP}, "faces": TOP},
            {"op": "sf_scale", "id": "c"},
            {"op": "sf_scale", "id": "c", "factor": 0},
            {"op": "sf_scale", "id": "c", "factors": [1, 2]},
            {"op": "sf_scale", "id": "c", "factor": 2, "factors": [1, 1, 1]},
            {"op": "sf_scale", "id": "c", "factor": 2, "point": [1, 2]},
            {"op": "sf_shell_edit", "target": "e1", "set": {"inside": 1}},  # not a shell
        ]
        for step in bad:
            with self.assertRaises(schema.ModelError, msg=str(step)):
                schema.validate(model(step))

    def test_edit_options_checked(self):
        with self.assertRaises(schema.ModelError):
            schema.validate(
                model(
                    {"op": "sf_draft", "id": "d", "plane": "XY", "faces": TOP},
                    {"op": "sf_draft_edit", "target": "d", "set": {"plane": "XZ"}},
                )
            )
        with self.assertRaises(schema.ModelError):
            schema.validate(
                model(
                    {"op": "sf_scale", "id": "c", "factor": 2},
                    {"op": "sf_scale_edit", "target": "c", "set": {}},
                )
            )


if __name__ == "__main__":
    unittest.main()
