# SPDX-License-Identifier: LGPL-2.1-or-later
"""The arithmetic of Draft's live picture (sciforge/draft_live_core.py, Luca 2026-10-22: the
drafted faces follow the angle handle on every mouse move): how far a point of a drafted face
moves, how a corner point on two faces moves, and how the picture bends at the hinge of a Two
Side draft. Also the limit search run one build at a time (value_limits.search_steps and
Limiter.find_steps give what search() and find() give). Runs without FreeCAD."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import draft_live_core as core  # noqa: E402
from sciforge import value_limits as vl  # noqa: E402

UP = (0.0, 0.0, 1.0)


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def moved(weights, shifts):
    d = (0.0, 0.0, 0.0)
    for w, s in zip(weights, shifts):
        d = core.add(d, core.scale(w, s))
    return d


class Shifts(unittest.TestCase):
    def test_a_wall_leans_in_toward_the_pull(self):
        # positive angle: the part gets narrower toward the pull direction
        k = core.k_factor(5.0, 0.0)
        self.assertAlmostEqual(-10.0 * k, -10.0 * math.tan(math.radians(5.0)))
        # below the hinge (One Side about a fixed plane) the face goes on turning: outward
        self.assertGreater(-(-10.0) * core.k_factor(5.0, 0.0, below=True), 0.0)

    def test_negative_angle_leans_out(self):
        self.assertGreater(-10.0 * core.k_factor(-5.0, 0.0), 0.0)

    def test_the_angle_is_absolute(self):
        # OpenCASCADE sets the angle: a face leaning 5 deg drafted 3 deg ends at 3 deg
        tb = math.tan(math.radians(5.0))
        k = core.k_factor(3.0, tb)
        self.assertAlmostEqual(k, math.tan(math.radians(3.0)) - tb)
        self.assertLess(k, 0.0)  # it leans back out a little

    def test_lean_of_a_face(self):
        n = (math.cos(math.radians(5.0)), 0.0, math.sin(math.radians(5.0)))
        self.assertAlmostEqual(core.lean_tan(n, UP), math.tan(math.radians(5.0)))
        self.assertAlmostEqual(core.lean_tan((1.0, 0.0, 0.0), UP), 0.0)

    def test_two_side_and_symmetric(self):
        # the far side turns away from the hinge too (narrower away from it)
        h = -4.0
        two = -h * core.k_factor(6.0, 0.0, "two", "fixed", True, 3.0)
        self.assertAlmostEqual(two, -4.0 * math.tan(math.radians(3.0)))
        sym = -h * core.k_factor(6.0, 0.0, "symmetric", "fixed", True)
        self.assertAlmostEqual(sym, -4.0 * math.tan(math.radians(6.0)))

    def test_parting_line_one_side_keeps_the_far_side(self):
        self.assertEqual(core.k_factor(6.0, 0.0, "one", "parting", True), 0.0)
        self.assertFalse(core.splits("one", "fixed"))
        self.assertTrue(core.splits("one", "parting"))
        self.assertTrue(core.splits("two", "fixed"))


class Corners(unittest.TestCase):
    def test_one_face_moves_straight_out(self):
        w = core.solve([(1.0, 0.0, 0.0)], UP)
        self.assertTrue(close(w[0], (1.0, 0.0, 0.0)))

    def test_a_cap_does_not_hold_the_point(self):
        w = core.solve([(0.0, -1.0, 0.0), (0.0, 0.0, 1.0)], UP)
        self.assertTrue(close(w[0], (0.0, -1.0, 0.0)))
        self.assertTrue(close(w[1], (0.0, 0.0, 0.0)))

    def test_the_corner_of_a_box_moves_with_both_sides(self):
        # front (-y) and right (+x) both drafted: the corner moves out of both by their shift
        w = core.solve([(0.0, -1.0, 0.0), (1.0, 0.0, 0.0)], UP)
        d = moved(w, [-0.5, -0.5])
        self.assertTrue(close(d, (-0.5, 0.5, 0.0)))

    def test_a_side_that_is_not_drafted_holds_the_corner_on_it(self):
        # the front drafted, the right side not: the corner slides along the right side
        w = core.solve([(0.0, -1.0, 0.0), (1.0, 0.0, 0.0)], UP)
        d = moved(w, [-0.5, 0.0])
        self.assertTrue(close(d, (0.0, 0.5, 0.0)))

    def test_a_slanted_neighbour(self):
        a = (0.0, -1.0, 0.0)
        b = core.unit((1.0, -1.0, 0.0))
        w = core.solve([a, b], UP)
        d = moved(w, [0.3, 0.7])
        self.assertAlmostEqual(core.dot(d, a), 0.3)
        self.assertAlmostEqual(core.dot(d, b), 0.7)

    def test_tangent_faces_share_one_shift(self):
        # a flat side and the rounded corner going on from it
        w = core.solve([(0.0, -1.0, 0.0), (0.0, -1.0, 0.0)], UP)
        d = moved(w, [-0.5, -0.5])
        self.assertTrue(close(d, (0.0, 0.5, 0.0)))

    def test_leaning_normals_are_laid_flat(self):
        n = core.unit((0.0, -1.0, 0.2))
        w = core.solve([n], UP)
        self.assertTrue(close(w[0], (0.0, -1.0, 0.0)))


class Bend(unittest.TestCase):
    def test_a_triangle_across_the_hinge_is_cut_there(self):
        heights = [-1.0, 1.0, 1.0]
        made, tris = core.split_triangles(heights, [(0, 1, 2)])
        self.assertEqual(len(made), 2)
        for i, j, t in made:
            self.assertAlmostEqual(heights[i] + (heights[j] - heights[i]) * t, 0.0)
        self.assertEqual(len(tris), 3)
        # every piece lies on one side of the hinge
        all_h = heights + [0.0] * len(made)
        for tri in tris:
            hs = [all_h[k] for k in tri]
            self.assertTrue(min(hs) >= -1e-12 or max(hs) <= 1e-12, hs)

    def test_a_triangle_on_one_side_stays(self):
        made, tris = core.split_triangles([0.0, 1.0, 2.0], [(0, 1, 2)])
        self.assertEqual(made, [])
        self.assertEqual(tris, [(0, 1, 2)])

    def test_a_corner_on_the_hinge(self):
        made, tris = core.split_triangles([0.0, -1.0, 1.0], [(0, 1, 2)])
        self.assertEqual(len(made), 1)
        self.assertEqual(len(tris), 2)

    def test_shared_cuts_are_one_point(self):
        made, tris = core.split_triangles([-1.0, 1.0, 1.0, -1.0], [(0, 1, 2), (0, 2, 3)])
        self.assertEqual(len(made), 3)  # edges 0-1, 0-2 (shared), 2-3

    def test_a_line_gets_its_crossing(self):
        out = core.split_line([-2.0, 2.0, 3.0])
        self.assertEqual(out[0], (0, 0, 0.0))
        self.assertEqual(out[1], (0, 1, 0.5))
        self.assertEqual(len(out), 4)


class StepByStep(unittest.TestCase):
    """The limit search one build at a time gives what the search at once gives."""

    def works(self, edge):
        calls = []

        def run(value):
            calls.append(value)
            return value <= edge

        return run, calls

    def test_steps_yield_before_every_build(self):
        works, calls = self.works(3.4789)
        steps = vl.search_steps(works, 0.01, 100.0, 0.01)
        yields = 0
        try:
            while True:
                before = len(calls)
                next(steps)
                yields += 1
                self.assertLessEqual(len(calls) - before, 1)
        except StopIteration as stop:
            limit, exact = stop.value
        self.assertAlmostEqual(limit, 3.47)
        self.assertTrue(exact)
        self.assertGreaterEqual(yields, len(calls))

    def test_same_as_at_once(self):
        a, _ = self.works(7.43)
        b, _ = self.works(7.43)
        self.assertEqual(
            vl.search(a, 1.0, 19.4, 0.1), vl.run_steps(vl.search_steps(b, 1.0, 19.4, 0.1))
        )

    def test_find_steps_stores_the_limit(self):
        limiter = vl.Limiter("deg")
        works, _ = self.works(7.43)
        key = vl.make_key("draft", "inputs")
        limit = vl.run_steps(limiter.find_steps(key, works, 19.4, 1.0))
        self.assertAlmostEqual(limit, 7.4)
        self.assertEqual(limiter.cached(key, 25.0, 1.0), (True, limit))
        self.assertEqual(limiter.cached(vl.make_key("other"), 25.0, 1.0), (False, None))

    def test_budget_counts_build_time(self):
        # a clock that only moves while building (what Background gives the search)
        spent = [0.0]

        def clock():
            return spent[0]

        def works(value):
            spent[0] += 0.4  # a slow part
            return value <= 7.43

        limiter = vl.Limiter("deg")
        limit = vl.run_steps(limiter.find_steps(vl.make_key("k"), works, 19.4, 1.0, clock=clock))
        self.assertIsNotNone(limit)
        self.assertLessEqual(limit, 7.43)
        self.assertLess(spent[0], vl.BUDGET + vl.VERIFY_TRIES * 0.4 + 1.0)


if __name__ == "__main__":
    unittest.main()
