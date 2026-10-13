# SPDX-License-Identifier: LGPL-2.1-or-later
"""Align's maths (align_core.py). Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import align_core as core  # noqa: E402


def close(a, b, tol=1e-9):
    return all(abs(x - y) < tol for x, y in zip(a, b))


class RotationTests(unittest.TestCase):
    def test_quarter_turn_about_z(self):
        q = core.axis_angle((0, 0, 1), 90)
        self.assertTrue(close(core.rotate(q, (1, 0, 0)), (0, 1, 0)))

    def test_between_takes_a_onto_b(self):
        for a, b in [((1, 0, 0), (0, 0, 1)), ((0, 0, 1), (0, 0, -1)), ((1, 1, 0), (0, 1, 1))]:
            q = core.between(a, b)
            self.assertTrue(close(core.rotate(q, core.unit(a)), core.unit(b)), (a, b))

    def test_multiply_applies_right_first(self):
        q = core.multiply(core.axis_angle((0, 0, 1), 90), core.axis_angle((1, 0, 0), 90))
        # (0,1,0) -> about X -> (0,0,1) -> about Z -> (0,0,1)
        self.assertTrue(close(core.rotate(q, (0, 1, 0)), (0, 0, 1)))


class MovementTests(unittest.TestCase):
    def test_point_to_point_is_a_shift(self):
        q, t = core.movement(core.frame((1, 2, 3)), core.frame((4, 6, 3)))
        self.assertEqual(q, core.IDENTITY)
        self.assertTrue(close(t, (3, 4, 0)))

    def test_faces_end_up_facing_each_other(self):
        # A block's bottom face (normal -Z, centre (5, 5, 0)) onto a table's top face
        # (normal +Z, centre (50, 0, 20)): no turn, the block sits on the table.
        bottom = core.frame((5, 5, 0), (0, 0, -1), oriented=True)
        top = core.frame((50, 0, 20), (0, 0, 1), oriented=True)
        q, t = core.movement(bottom, top)
        self.assertTrue(close(core.rotate(q, (0, 0, 1)), (0, 0, 1)))
        self.assertTrue(close(core.apply(q, t, (5, 5, 0)), (50, 0, 20)))
        self.assertTrue(close(core.apply(q, t, (5, 5, 10)), (50, 0, 30)))  # the block's top

    def test_a_side_face_onto_a_top_face_turns_the_block(self):
        side = core.frame((10, 5, 5), (1, 0, 0), oriented=True)  # the block's +X side
        top = core.frame((0, 0, 20), (0, 0, 1), oriented=True)
        q, t = core.movement(side, top)
        self.assertTrue(close(core.rotate(q, (1, 0, 0)), (0, 0, -1)))
        self.assertTrue(close(core.apply(q, t, (10, 5, 5)), (0, 0, 20)))

    def test_flip_turns_the_result_over(self):
        bottom = core.frame((0, 0, 0), (0, 0, -1), oriented=True)
        top = core.frame((0, 0, 20), (0, 0, 1), oriented=True)
        q, t = core.movement(bottom, top, flip=True)
        self.assertTrue(close(core.rotate(q, (0, 0, -1)), (0, 0, 1)))
        self.assertTrue(close(core.apply(q, t, (0, 0, 0)), (0, 0, 20)))
        self.assertTrue(close(core.apply(q, t, (0, 0, 10)), (0, 0, 10)))  # now below

    def test_angle_turns_90_degrees_per_click_about_the_target(self):
        bottom = core.frame((0, 0, 0), (0, 0, -1), oriented=True)
        top = core.frame((0, 0, 20), (0, 0, 1), oriented=True)
        q, t = core.movement(bottom, top, turns=1)
        self.assertTrue(close(core.rotate(q, (1, 0, 0)), (0, 1, 0)))
        q4, _t4 = core.movement(bottom, top, turns=4)
        self.assertTrue(close(core.rotate(q4, (1, 0, 0)), (1, 0, 0)))

    def test_edges_take_the_smaller_turn(self):
        a = core.frame((0, 0, 0), (1, 0, 0))
        b = core.frame((0, 0, 0), (-1, 0.0001, 0))
        q, _t = core.movement(a, b)
        # an edge has no direction of its own: no half turn
        self.assertGreater(core.dot(core.rotate(q, (1, 0, 0)), (1, 0, 0)), 0.99)

    def test_point_onto_a_face_only_shifts(self):
        corner = core.frame((1, 1, 1))
        top = core.frame((0, 0, 20), (0, 0, 1), oriented=True)
        q, t = core.movement(corner, top)
        self.assertEqual(q, core.IDENTITY)
        self.assertTrue(close(core.apply(q, t, (1, 1, 1)), (0, 0, 20)))

    def test_describe(self):
        self.assertEqual(core.describe(False, 0), "")
        self.assertEqual(core.describe(True, 1), "flipped, turned 90 degrees")
        self.assertEqual(core.describe(False, 6), "turned 180 degrees")

    def test_a_zero_axis_is_refused(self):
        with self.assertRaises(ValueError):
            core.frame((0, 0, 0), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
