# SPDX-License-Identifier: LGPL-2.1-or-later
"""sciforge/ai/value_fit.py: an AI tool's value that does not fit is refused with the largest
value that fits (found with value_limits.search, the dialogs' bisection), never built in its
place. Pure Python: the trial build is a fake."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge.ai import value_fit  # noqa: E402


class Candidates(unittest.TestCase):
    def test_tools_and_paths(self):
        self.assertEqual(
            [c[0] for c in value_fit.candidates("fillet", {"radius": 5, "edges": {}})],
            [("radius",)],
        )
        found = value_fit.candidates("chamfer", {"distance": 2, "distance2": 30})
        self.assertEqual([c[0] for c in found], [("distance",), ("distance2",)])
        found = value_fit.candidates("extrude", {"distance": 10, "thin": {"thickness": 3}})
        self.assertEqual([c[0] for c in found], [("thin", "thickness")])
        found = value_fit.candidates(
            "fillet_sets", {"sets": [{"radius": 1}, {"radius": 9, "chord": 2}]}
        )
        self.assertEqual(
            [c[0] for c in found],
            [("sets", 0, "radius"), ("sets", 1, "radius"), ("sets", 1, "chord")],
        )

    def test_left_alone(self):
        self.assertEqual(value_fit.candidates("extrude", {"distance": 10, "taper": 0}), [])
        self.assertEqual(value_fit.candidates("hole", {"diameter": 5}), [])
        self.assertEqual(
            value_fit.candidates("surface", {"kind": "offset", "options": {"thickness": 2}}), []
        )
        self.assertTrue(
            value_fit.candidates("surface", {"kind": "thicken", "options": {"thickness": 2}})
        )
        # a value from a formula is never searched (the dialogs leave a formula alone too)
        self.assertEqual(
            value_fit.candidates("pipe", {"thickness": 3, "expressions": {"thickness": "w / 4"}}),
            [],
        )

    def test_with_value_copies(self):
        args = {"sets": [{"radius": 9}]}
        out = value_fit.with_value(args, ("sets", 0, "radius"), 2.5)
        self.assertEqual(out["sets"][0]["radius"], 2.5)
        self.assertEqual(args["sets"][0]["radius"], 9)


class Largest(unittest.TestCase):
    def test_radius(self):
        calls = []

        def trial(args):
            calls.append(args["radius"])
            return args["radius"] < 3.4789

        text = value_fit.largest("fillet", {"radius": 20, "edges": {}}, trial)
        self.assertIn("Largest radius that fits here: 3.47 mm", text)
        self.assertIn("20 mm does not", text)
        self.assertIn("radius 3.47 or less", text)
        self.assertTrue(all(v <= 20 for v in calls))

    def test_second_value_is_the_culprit(self):
        """distance fits whatever its size; distance2 is what is too big."""

        def trial(args):
            return args["distance2"] <= 6

        text = value_fit.largest("chamfer", {"distance": 2, "distance2": 30}, trial)
        self.assertIn("Largest second distance that fits here: 6.00 mm", text)
        self.assertIn("distance2 6.00 or less", text)

    def test_push_into_the_part(self):
        text = value_fit.largest("press_pull", {"distance": -50}, lambda a: a["distance"] > -9.99)
        self.assertIn("Furthest distance that fits here: -9.98 mm", text)
        self.assertIn("between -9.98 and 0", text)

    def test_angle(self):
        text = value_fit.largest("draft", {"angle": 80}, lambda a: a["angle"] <= 37.25)
        self.assertIn("Largest angle that fits here: 37.2°", text)

    def test_nested_name(self):
        text = value_fit.largest(
            "extrude", {"thin": {"thickness": 8}}, lambda a: a["thin"]["thickness"] < 2.5
        )
        self.assertIn("thin.thickness 2.49 or less", text)

    def test_no_smaller_value_helps(self):
        self.assertEqual(value_fit.largest("fillet", {"radius": 5}, lambda a: False), "")

    def test_trial_that_raises_counts_as_no(self):
        def trial(args):
            if args["radius"] > 1:
                raise RuntimeError("OCC")
            return True

        self.assertIn("1.00 mm", value_fit.largest("fillet", {"radius": 4}, trial))

    def test_limit_words(self):
        self.assertTrue(value_fit.is_limit("Radius 10 mm is too big here: the round does not fit"))
        self.assertFalse(value_fit.is_limit("selector picked 2 faces, expected 1"))


if __name__ == "__main__":
    unittest.main()
