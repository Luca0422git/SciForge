# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch constraints that explain themselves: the words, the priority order of inferred
constraints, the padlock rule and the refused-parameter message. Runs without FreeCAD."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import sketch_explain_core as core  # noqa: E402

LINE = "Part::GeomLineSegment"
CIRCLE = "Part::GeomCircle"
ARC = "Part::GeomArcOfCircle"
POINT = "Part::GeomPoint"
U = core.GEO_UNDEF


def con(kind, first, first_pos=0, second=U, second_pos=0, third=U, third_pos=0, **extra):
    c = {
        "type": kind,
        "first": first,
        "first_pos": first_pos,
        "second": second,
        "second_pos": second_pos,
        "third": third,
        "third_pos": third_pos,
        "value": 0.0,
        "name": "",
        "driving": True,
    }
    c.update(extra)
    return c


# a rectangle (lines 0-3), a circle, an arc, a point and one more line
TYPES = [LINE, LINE, LINE, LINE, CIRCLE, ARC, POINT, LINE]
NAMES = core.curve_names(TYPES)
KINDS = dict(enumerate(TYPES))


class NameTests(unittest.TestCase):
    def test_curves_numbered_per_kind(self):
        self.assertEqual(NAMES[0], "Line 1")
        self.assertEqual(NAMES[3], "Line 4")
        self.assertEqual(NAMES[4], "Circle 1")
        self.assertEqual(NAMES[5], "Arc 1")
        self.assertEqual(NAMES[6], "Point 1")
        self.assertEqual(NAMES[7], "Line 5")

    def test_axes_and_projected_curves(self):
        self.assertEqual(core.curve_name(-1, NAMES), "the X axis")
        self.assertEqual(core.curve_name(-2, NAMES), "the Y axis")
        self.assertEqual(core.curve_name(-3, NAMES), "Projected Curve 1")
        self.assertEqual(core.curve_name(U, NAMES), "")


class DescribeTests(unittest.TestCase):
    def say(self, c):
        return core.describe(c, NAMES, KINDS)

    def test_directions(self):
        self.assertEqual(self.say(con("Horizontal", 1)), "the Horizontal on Line 2")
        self.assertEqual(
            self.say(con("Vertical", 0, 1, 7, 2)), "the Vertical between Line 1 and Line 5"
        )

    def test_dimensions_say_their_value(self):
        self.assertEqual(self.say(con("Distance", 0, value=30.0)), "the 30 mm dimension")
        self.assertEqual(
            self.say(con("DistanceX", 0, 1, 0, 2, value=-12.5)), "the 12.5 mm dimension"
        )
        self.assertEqual(self.say(con("Radius", 4, value=5.0)), "the 5 mm radius")
        self.assertEqual(self.say(con("Diameter", 4, value=10.0)), "the 10 mm diameter")
        self.assertEqual(
            self.say(con("Angle", 0, 0, 1, 0, value=math.radians(45))), "the 45 deg angle"
        )
        self.assertEqual(
            self.say(con("Distance", 0, value=30.0, name="width")), "the 30 mm dimension 'width'"
        )

    def test_fusion_names(self):
        self.assertEqual(
            self.say(con("Coincident", 4, 3, 5, 3)), "the Concentric between Circle 1 and Arc 1"
        )
        self.assertEqual(
            self.say(con("Tangent", 0, 0, 7, 0)), "the Collinear between Line 1 and Line 5"
        )
        self.assertEqual(
            self.say(con("Tangent", 0, 0, 5, 0)), "the Tangent between Line 1 and Arc 1"
        )
        self.assertEqual(self.say(con("Block", 2)), "the Fix on Line 3")
        self.assertEqual(
            self.say(con("PointOnObject", 6, 1, 0)), "the Coincident between Point 1 and Line 1"
        )
        self.assertEqual(
            self.say(con("Coincident", 0, 1, -1, 1)), "the Coincident between Line 1 and the origin"
        )

    def test_symmetry_and_midpoint(self):
        self.assertEqual(
            self.say(con("Symmetric", 0, 1, 0, 2, 6, 1)), "the Midpoint between Line 1 and Point 1"
        )
        self.assertEqual(self.say(con("Symmetric", 0, 1, 2, 1, 7, 0)), "the Symmetry about Line 5")

    def test_same_curve_twice_is_named_once(self):
        self.assertEqual(self.say(con("Coincident", 0, 1, 0, 2)), "the Coincident on Line 1")


class CulpritListTests(unittest.TestCase):
    def test_most_telling_first(self):
        items = [
            dict(con("Coincident", 0, 2, 1, 1), index=0),
            dict(con("Vertical", 1), index=6),
            dict(con("Distance", 0, value=30.0), index=8),
        ]
        self.assertEqual(
            core.culprit_list(items, NAMES, KINDS),
            "the 30 mm dimension, the Vertical on Line 2 and the Coincident between Line 1 "
            "and Line 2",
        )

    def test_leftover_corners_are_counted(self):
        items = [dict(con("Coincident", i, 2, (i + 1) % 4, 1), index=i) for i in range(4)]
        items += [
            dict(con("Vertical", 1), index=6),
            dict(con("Vertical", 3), index=7),
            dict(con("DistanceX", 0, 1, 0, 2, value=30.0), index=8),
        ]
        self.assertEqual(
            core.culprit_list(items, NAMES, KINDS),
            "the 30 mm dimension, the Vertical on Line 2, the Vertical on Line 4 and "
            "4 Coincidents",
        )

    def test_join_list(self):
        self.assertEqual(core.join_list([]), "")
        self.assertEqual(core.join_list(["a"]), "a")
        self.assertEqual(core.join_list(["a", "b"]), "a and b")
        self.assertEqual(core.join_list(["a", "b", "c", "d", "e"]), "a, b, c and 2 more")


class MessageTests(unittest.TestCase):
    def test_conflict(self):
        text = core.refused_constraint(
            "Equal", "conflict", "the 30 mm dimension and the 20 mm dimension", 2
        )
        self.assertEqual(
            text,
            "Equal: not added, it conflicts with the 30 mm dimension and the 20 mm dimension "
            "(highlighted in the sketch).",
        )

    def test_redundant(self):
        text = core.refused_constraint(
            "Parallel", "redundant", "the Horizontal on Line 1 and the Horizontal on Line 3", 2
        )
        self.assertIn("already make it so", text)
        one = core.refused_constraint("Horizontal", "redundant", "the Perpendicular", 1)
        self.assertIn("already makes it so", one)

    def test_without_culprits(self):
        self.assertIn("does not fit", core.refused_constraint("Equal", "conflict", "", 0))
        self.assertIn("is so already", core.refused_constraint("Equal", "redundant", "", 0))

    def test_driven_and_value(self):
        self.assertIn(
            "already set by the 30 mm dimension", core.driven_dimension("the 30 mm dimension")
        )
        self.assertIn("driven", core.driven_dimension(""))
        self.assertIn("conflicts with the Vertical", core.value_conflict("the Vertical on Line 2"))
        self.assertIn("does not fit", core.value_conflict(""))

    def test_constraint_step_titles(self):
        self.assertEqual(core.constraint_step_title("Add horizontal constraint"), "Horizontal")
        self.assertEqual(core.constraint_step_title("Add equality constraint"), "Equal")
        self.assertEqual(core.constraint_step_title("Add 'Lock' constraint"), "Fix")
        self.assertEqual(
            core.constraint_step_title("Add perpendicularity constraint"), "Perpendicular"
        )
        # dimensions are not refused (made driven), other steps are not constraints
        self.assertIsNone(core.constraint_step_title("Add length constraint"))
        self.assertIsNone(core.constraint_step_title("Add sketch line"))
        self.assertIsNone(core.constraint_step_title("Inferred Constraints"))
        self.assertIsNone(core.constraint_step_title(""))


class PriorityTests(unittest.TestCase):
    def test_order(self):
        kinds = [
            ("Parallel", 0, 0, True, True),
            ("Perpendicular", 0, 0, True, False),
            ("Perpendicular", 0, 0, True, True),
            ("Tangent", 0, 0, True, True),  # collinear
            ("Horizontal", 0, 0, False, True),
            ("Tangent", 0, 0, False, True),
            ("Coincident", 3, 3, False, True),  # concentric
            ("Coincident", 1, 2, False, True),
            ("Distance", 0, 0, False, True),  # a typed length
        ]
        ranked = core.priority_order(kinds, lambda k: core.inference_rank(*k))
        self.assertEqual(
            [(k[0], k[1]) for k in ranked],
            [
                ("Distance", 0),
                ("Coincident", 1),
                ("Tangent", 0),  # an arc's tangency, as strong as a concentric
                ("Coincident", 3),
                ("Horizontal", 0),
                ("Tangent", 0),
                ("Perpendicular", 0),
                ("Parallel", 0),
                ("Perpendicular", 0),
            ],
        )
        # the touching perpendicular before the parallel, the far one with it (stable)
        self.assertTrue(ranked[6] is kinds[2])
        self.assertTrue(ranked[8] is kinds[1])

    def test_inferred_angle_is_a_direction(self):
        self.assertEqual(core.inference_rank("Angle"), core.inference_rank("Horizontal"))
        self.assertEqual(core.inference_rank("Equal"), core.inference_rank("Parallel"))
        self.assertLess(core.inference_rank("PointOnObject"), core.inference_rank("Vertical"))

    def test_weak_guess_never_pushes_out_a_strong_one(self):
        # a sketch that takes either the coincidence or the parallel, not both
        added = []

        def try_add(item):
            if item == "Parallel" and "Coincident" in added:
                return False
            if item == "Coincident" and "Parallel" in added:
                return False
            added.append(item)
            return True

        rank = {"Parallel": core.inference_rank("Parallel"), "Coincident": 0}
        kept = core.add_in_order(["Parallel", "Coincident"], rank.get, try_add)
        self.assertEqual(kept, ["Coincident"])


class PadlockTests(unittest.TestCase):
    def test_rule(self):
        ok = core.is_fully_constrained
        self.assertTrue(ok(4, True, 0, [], [], []))
        self.assertFalse(ok(0, True, 0, [], [], []), "an empty sketch has no padlock")
        self.assertFalse(ok(4, True, 2, [], [], []), "a solve found freedom left")
        self.assertFalse(ok(4, True, 0, [3, 5], [], []), "FreeCAD's flag stays on in a conflict")
        self.assertFalse(ok(4, True, -1, [], [], []))
        self.assertFalse(ok(4, True, 0, [], [2], []))
        # FreeCAD does not update its flag when the solve only found redundancy
        self.assertTrue(ok(4, False, 0, [], [], [7]))
        self.assertFalse(ok(4, False, 0, [], [], []))

    def test_freedom_note(self):
        self.assertEqual(core.freedom_note(0, True), "Fully constrained")
        self.assertEqual(core.freedom_note(3, False), "3 left to define")
        self.assertEqual(core.freedom_note(0, False), "")
        self.assertEqual(core.freedom_note(None, False), "")
        self.assertEqual(core.freedom_note(2, False, True), "Conflicting constraints")


class ParameterTests(unittest.TestCase):
    def test_bad_sizes(self):
        self.assertTrue(core.bad_size("Distance", 0.0))
        self.assertTrue(core.bad_size("Radius", -2.0))
        self.assertFalse(core.bad_size("Distance", 0.5))
        self.assertTrue(core.bad_size("DistanceX", 0.0))
        self.assertFalse(core.bad_size("DistanceX", -5.0), "the sign is the direction")
        self.assertFalse(core.bad_size("Angle", 0.0))

    def test_refusal(self):
        reason = core.bad_size_reason(con("Radius", 4, value=-2.0, name="r"), NAMES)
        self.assertEqual(
            reason, "its radius 'r' of Circle 1 would be -2 mm, and a size must be more than 0"
        )
        text = core.parameter_refusal("r = -2 mm", [("Sketch 1", reason), ("Extrude 1", "x")])
        self.assertTrue(text.startswith("Not changed: with r = -2 mm, Sketch 1 would break: its"))
        self.assertTrue(text.endswith("Extrude 1 would break too."))
        three = core.parameter_refusal("w = 0", [("A", "a"), ("B", "b"), ("C", "c")])
        self.assertTrue(three.endswith("2 more steps would break too."))
        self.assertEqual(core.parameter_refusal("w = 1", []), "")


if __name__ == "__main__":
    unittest.main()
