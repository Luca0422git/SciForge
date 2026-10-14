# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loft end conditions: the math (sciforge/loft_ends_core.py). Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import loft_ends_core as core  # noqa: E402


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


class SolveTests(unittest.TestCase):
    def test_small_system(self):
        x = core.solve([[2.0, 1.0], [1.0, 3.0]], [[3.0, 5.0], [5.0, 10.0]])
        self.assertTrue(close(x[0][0], 0.8) and close(x[1][0], 1.4), x)
        self.assertTrue(close(x[0][1], 1.0) and close(x[1][1], 3.0), x)

    def test_singular_is_refused(self):
        with self.assertRaises(core.EndError):
            core.solve([[1.0, 2.0], [2.0, 4.0]], [[1.0], [2.0]])


class KnotTests(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(core.knot_vector([0.0, 1.0]), [0.0] * 4 + [1.0] * 4)
        self.assertEqual(core.knot_vector([0.0, 0.4, 1.0]), [0.0] * 4 + [0.4] + [1.0] * 4)

    def test_extra_knots_share_one_span(self):
        knots = core.knot_vector([0.0, 1.0], 1, 1)
        self.assertEqual(len(knots), 10)
        self.assertTrue(close(knots[4], 1.0 / 3.0) and close(knots[5], 2.0 / 3.0), knots)

    def test_knots_and_mults(self):
        values, mults = core.knots_and_mults([0.0] * 4 + [0.5] + [1.0] * 4)
        self.assertEqual((values, mults), ([0.0, 0.5, 1.0], [4, 1, 4]))


class InterpolateTests(unittest.TestCase):
    def test_free_ends_between_two_rows_is_straight(self):
        knots, ctrl = core.interpolate([0.0, 1.0], [[0.0, 10.0], [4.0, 20.0]])
        for t in (0.0, 0.25, 0.5, 0.9, 1.0):
            got = core.evaluate(knots, ctrl, t)
            self.assertTrue(close(got[0], 4.0 * t) and close(got[1], 10.0 + 10.0 * t), got)

    def test_first_derivatives_make_a_hermite_curve(self):
        knots, ctrl = core.interpolate(
            [0.0, 1.0], [[0.0], [1.0]], start=("d1", [0.0]), end=("d1", [0.0])
        )
        t = 0.25
        self.assertTrue(close(core.evaluate(knots, ctrl, t)[0], 3 * t * t - 2 * t**3))
        self.assertTrue(close(core.evaluate(knots, ctrl, 0.0, 1)[0], 0.0))
        self.assertTrue(close(core.evaluate(knots, ctrl, 1.0, 1)[0], 0.0))

    def test_given_derivatives_are_met(self):
        knots, ctrl = core.interpolate(
            [0.0, 0.3, 1.0],
            [[0.0, 0.0], [1.0, 2.0], [3.0, 1.0]],
            start=("d2", [5.0, -1.0], [2.0, 0.0]),
            end=("d1", [0.0, 4.0]),
        )
        self.assertEqual(len(ctrl), 3 + 2 + 1)
        for t, want in ((0.0, [0.0, 0.0]), (0.3, [1.0, 2.0]), (1.0, [3.0, 1.0])):
            got = core.evaluate(knots, ctrl, t)
            self.assertTrue(all(close(a, b) for a, b in zip(got, want)), (t, got))
        d1 = core.evaluate(knots, ctrl, 0.0, 1)
        d2 = core.evaluate(knots, ctrl, 0.0, 2)
        e1 = core.evaluate(knots, ctrl, 1.0, 1)
        self.assertTrue(close(d1[0], 5.0) and close(d1[1], -1.0), d1)
        self.assertTrue(close(d2[0], 2.0) and close(d2[1], 0.0), d2)
        self.assertTrue(close(e1[0], 0.0) and close(e1[1], 4.0), e1)

    def test_natural_end_has_no_second_derivative(self):
        knots, ctrl = core.interpolate([0.0, 0.5, 1.0], [[0.0], [2.0], [1.0]], end=("d1", [1.0]))
        self.assertTrue(close(core.evaluate(knots, ctrl, 0.0, 2)[0], 0.0, 1e-8))

    def test_both_ends_curvature(self):
        knots, ctrl = core.interpolate(
            [0.0, 1.0],
            [[0.0], [1.0]],
            start=("d2", [1.0], [0.0]),
            end=("d2", [1.0], [0.0]),
        )
        for t in (0.1, 0.5, 0.8):
            self.assertTrue(close(core.evaluate(knots, ctrl, t)[0], t), t)

    def test_bad_input(self):
        with self.assertRaises(core.EndError):
            core.interpolate([0.0], [[1.0]])
        with self.assertRaises(core.EndError):
            core.interpolate([0.0, 0.0], [[1.0], [2.0]])


class RuleTests(unittest.TestCase):
    def test_allowed_conditions(self):
        self.assertEqual(core.allowed("sketch"), ("free", "direction"))
        self.assertIn("point_tangent", core.allowed("point"))
        self.assertIn("curvature", core.allowed("face"))

    def test_check_refuses_with_a_reason(self):
        core.check("direction", "sketch", 1.0, 10.0)
        core.check("free", "point", 0.0)
        with self.assertRaises(core.EndError) as caught:
            core.check("tangent", "sketch", 1.0)
        self.assertIn("Connected, Direction", str(caught.exception))
        with self.assertRaises(core.EndError):
            core.check("direction", "sketch", 0.0)
        with self.assertRaises(core.EndError):
            core.check("direction", "sketch", 1.0, 95.0)

    def test_takeoff(self):
        d = core.takeoff((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), 0.0)
        self.assertTrue(close(d[2], 1.0) and close(d[0], 0.0))
        d = core.takeoff((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), 30.0)
        self.assertTrue(close(d[0], 0.5) and close(d[2], 3**0.5 / 2.0), d)

    def test_chord_params(self):
        params = core.chord_params([(0, 0, 0), (0, 0, 10), (0, 0, 40)])
        self.assertEqual(params, [0.0, 0.25, 1.0])
        self.assertEqual(core.magnitude(2.0, 15.0), 30.0)


if __name__ == "__main__":
    unittest.main()
