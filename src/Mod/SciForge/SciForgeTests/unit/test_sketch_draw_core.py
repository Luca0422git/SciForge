# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of SciForge's own sketch tools (sketch_draw_core.py). Runs without FreeCAD.
Every expected value is worked out by hand in the test's docstring or comment."""

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import sketch_draw_core as core  # noqa: E402


def near(test, a, b, tol=1e-9):
    test.assertAlmostEqual(a[0], b[0], delta=tol)
    test.assertAlmostEqual(a[1], b[1], delta=tol)


def line_distance(p, line):
    return core.point_line_distance(p, line[0], line[1])


class MidpointLineTests(unittest.TestCase):
    def test_symmetric_about_the_middle(self):
        a, b = core.midpoint_line((10, 5), (13, 9))
        near(self, b, (13, 9))
        near(self, a, (7, 1))  # 2 * (10, 5) - (13, 9)

    def test_typed_length_is_the_whole_line(self):
        # length 20 along +x from the middle (0, 0): ends at -10 and +10
        a, b = core.midpoint_line((0, 0), (3, 0), length_=20.0)
        near(self, a, (-10, 0))
        near(self, b, (10, 0))

    def test_typed_angle_keeps_the_pointer_distance_along_it(self):
        # angle 90 deg, pointer at (2, 7): its distance along +y is 7
        a, b = core.midpoint_line((0, 0), (2, 7), angle=math.radians(90))
        near(self, b, (0, 7))
        near(self, a, (0, -7))

    def test_no_line_on_the_middle(self):
        self.assertIsNone(core.midpoint_line((1, 1), (1, 1)))


class CircleTests(unittest.TestCase):
    def test_two_point_circle(self):
        centre, r = core.circle_2point((0, 0), (6, 8))
        near(self, centre, (3, 4))
        self.assertAlmostEqual(r, 5.0)  # half of the 6-8-10 triangle's hypotenuse

    def test_two_point_circle_typed_diameter(self):
        centre, r = core.circle_2point((0, 0), (6, 8), diameter=20.0)
        self.assertAlmostEqual(r, 10.0)
        near(self, centre, (6, 8))  # 10 along (0.6, 0.8)

    def test_three_point_circle(self):
        centre, r = core.circle_3point((5, 0), (0, 5), (-5, 0))
        near(self, centre, (0, 0))
        self.assertAlmostEqual(r, 5.0)
        self.assertIsNone(core.circle_3point((0, 0), (1, 1), (2, 2)))


class TwoTangentCircleTests(unittest.TestCase):
    X_AXIS = ((0, 0), (10, 0))
    Y_AXIS = ((0, 0), (0, 10))

    def test_follows_the_pointer_in_its_quadrant(self):
        # lines x = 0 and y = 0, pointer (3, 5) in the first quadrant: the centre is the
        # pointer's projection on the bisector y = x: t = (3+5)/sqrt2, centre (4, 4), r 4
        centre, r = core.tangent_circle_2lines(self.X_AXIS, self.Y_AXIS, (3, 5))
        near(self, centre, (4, 4))
        self.assertAlmostEqual(r, 4.0)

    def test_other_quadrant(self):
        centre, r = core.tangent_circle_2lines(self.X_AXIS, self.Y_AXIS, (-2, 6))
        near(self, centre, (-4, 4))
        self.assertAlmostEqual(r, 4.0)

    def test_typed_radius(self):
        centre, r = core.tangent_circle_2lines(self.X_AXIS, self.Y_AXIS, (30, -1), radius=2.5)
        near(self, centre, (2.5, -2.5))
        self.assertAlmostEqual(r, 2.5)

    def test_touches_both_lines_at_an_angle(self):
        # a 60 degree corner: the circle touches both lines whatever the radius
        line2 = ((0, 0), (math.cos(math.radians(60)), math.sin(math.radians(60))))
        centre, r = core.tangent_circle_2lines(self.X_AXIS, line2, (5, 1), radius=3.0)
        self.assertAlmostEqual(line_distance(centre, self.X_AXIS), 3.0)
        self.assertAlmostEqual(line_distance(centre, line2), 3.0)

    def test_parallel_lines(self):
        # y = 0 and y = 6: radius 3, centre on y = 3 under the pointer
        centre, r = core.tangent_circle_2lines(self.X_AXIS, ((0, 6), (5, 6)), (7, 1))
        near(self, centre, (7, 3))
        self.assertAlmostEqual(r, 3.0)


class ThreeTangentCircleTests(unittest.TestCase):
    def test_triangle_gives_incircle_and_three_excircles(self):
        # the 3-4-5 right triangle (0,0) (4,0) (0,3): inradius (3+4-5)/2 = 1 at (1, 1)
        lines = [((0, 0), (4, 0)), ((0, 0), (0, 3)), ((4, 0), (0, 3))]
        circles = core.tangent_circles_3lines(*lines)
        self.assertEqual(len(circles), 4)
        centre, r = core.nearest_circle(circles, (1.2, 0.9))
        near(self, centre, (1, 1))
        self.assertAlmostEqual(r, 1.0)
        for centre, r in circles:
            for line in lines:
                self.assertAlmostEqual(line_distance(centre, line), r)
        # excircle opposite the right angle: radius = s = (3+4+5)/2 = 6, centre (6, 6)
        centre, r = core.nearest_circle(circles, (7, 7))
        near(self, centre, (6, 6))
        self.assertAlmostEqual(r, 6.0)

    def test_two_parallel_lines_give_two_circles(self):
        lines = [((0, 0), (10, 0)), ((0, 4), (10, 4)), ((0, 0), (1, 1))]
        circles = core.tangent_circles_3lines(*lines)
        self.assertEqual(len(circles), 2)
        for centre, r in circles:
            self.assertAlmostEqual(r, 2.0)
            self.assertAlmostEqual(centre[1], 2.0)

    def test_three_parallel_lines_give_none(self):
        lines = [((0, 0), (1, 0)), ((0, 1), (1, 1)), ((0, 3), (1, 3))]
        self.assertEqual(core.tangent_circles_3lines(*lines), [])


class ArcTests(unittest.TestCase):
    def test_arc_through_counterclockwise(self):
        centre, r, a1, a2 = core.arc_through((5, 0), (0, 5), (-5, 0))
        near(self, centre, (0, 0))
        self.assertAlmostEqual(a1, 0.0)
        self.assertAlmostEqual(a2, math.pi)

    def test_arc_through_clockwise_swaps_the_ends(self):
        # (-5,0) -> (0,5) -> (5,0) is clockwise: as a counterclockwise arc 0 .. pi
        centre, r, a1, a2 = core.arc_through((-5, 0), (0, 5), (5, 0))
        self.assertAlmostEqual(a1 % (2 * math.pi), 0.0)
        self.assertAlmostEqual(a2 - a1, math.pi)

    def test_arc_through_the_long_way(self):
        # (5,0) -> (0,-5) -> (0,5): counterclockwise from 0 it reaches 90 before 270, so the
        # arc runs clockwise 0 -> -90 -> -270: as counterclockwise from 90 to 360
        centre, r, a1, a2 = core.arc_through((5, 0), (0, -5), (0, 5))
        self.assertAlmostEqual(a2 - a1, 1.5 * math.pi)


class TangentArcRadiusTests(unittest.TestCase):
    def test_turns_left_towards_the_pointer(self):
        # leaving (0, 0) along +x, pointer above: centre (0, 5) for radius 5; the pointer
        # (5, 5) is at angle 0 about it, the start at -90 deg
        centre, r, a1, a2, joint = core.tangent_arc_radius((0, 0), (1, 0), (5, 5), 5.0)
        near(self, centre, (0, 5))
        self.assertEqual(joint, 1)
        self.assertAlmostEqual(a1, -math.pi / 2)
        self.assertAlmostEqual(a2, 0.0)

    def test_turns_right(self):
        centre, r, a1, a2, joint = core.tangent_arc_radius((0, 0), (1, 0), (5, -5), 5.0)
        near(self, centre, (0, -5))
        self.assertEqual(joint, 2)  # clockwise: the start is the arc's end
        near(self, core.polar(a2, r, centre), (0, 0))

    def test_on_the_tangent_line(self):
        self.assertIsNone(core.tangent_arc_radius((0, 0), (1, 0), (9, 0), 5.0))


class EdgePolygonTests(unittest.TestCase):
    def test_square_on_the_pointer_side(self):
        corners, centre, r = core.edge_polygon((0, 0), (10, 0), 4, (5, 3))
        near(self, centre, (5, 5))
        self.assertAlmostEqual(r, math.hypot(5, 5))
        near(self, corners[0], (0, 0))
        near(self, corners[1], (10, 0))
        near(self, corners[2], (10, 10))
        near(self, corners[3], (0, 10))

    def test_other_side(self):
        corners, centre, _r = core.edge_polygon((0, 0), (10, 0), 4, (5, -3))
        near(self, centre, (5, -5))
        near(self, corners[1], (10, 0))
        near(self, corners[2], (10, -10))

    def test_hexagon_edges_are_equal(self):
        corners, centre, r = core.edge_polygon((2, 1), (8, 4), 6, (0, 9))
        side = core.dist((2, 1), (8, 4))
        for i in range(6):
            self.assertAlmostEqual(core.dist(corners[i], corners[(i + 1) % 6]), side)
            self.assertAlmostEqual(core.dist(corners[i], centre), r)
        self.assertAlmostEqual(r, side)  # a hexagon's corner radius is its side


class SlotTests(unittest.TestCase):
    def test_kinds(self):
        c1, c2, r = core.slot_centres(core.CENTER_TO_CENTER, (0, 0), (20, 0), 6)
        near(self, c1, (0, 0))
        near(self, c2, (20, 0))
        self.assertAlmostEqual(r, 3.0)
        # overall: the clicks are the far ends, the centres one radius inside
        c1, c2, r = core.slot_centres(core.OVERALL, (0, 0), (20, 0), 6)
        near(self, c1, (3, 0))
        near(self, c2, (17, 0))
        # centre point: the first click is the middle, the second an arc centre
        c1, c2, r = core.slot_centres(core.CENTER_POINT, (10, 5), (25, 5), 4)
        near(self, c1, (-5, 5))
        near(self, c2, (25, 5))
        self.assertIsNone(core.slot_centres(core.OVERALL, (0, 0), (5, 0), 6))

    def test_outline_joins_up(self):
        arc1, arc2, line1, line2 = core.slot_outline((0, 0), (20, 0), 3)
        start1 = core.polar(arc1[3], 3, (0, 0))
        end1 = core.polar(arc1[4], 3, (0, 0))
        start2 = core.polar(arc2[3], 3, (20, 0))
        end2 = core.polar(arc2[4], 3, (20, 0))
        # ("line", a, b): line 1 from arc 1's start to arc 2's end, line 2 from arc 1's end
        # to arc 2's start
        near(self, line1[2], (20, 3))
        near(self, start1, line1[1])
        near(self, end2, line1[2])
        near(self, end1, line2[1])
        near(self, start2, line2[2])
        # arc 1 faces away from c2: its middle is at (-3, 0)
        near(self, core.polar((arc1[3] + arc1[4]) / 2, 3, (0, 0)), (-3, 0))

    def test_width_from_pointer(self):
        self.assertAlmostEqual(core.slot_width_from_pointer((0, 0), (20, 0), (8, 4)), 8.0)
        self.assertAlmostEqual(core.slot_width_from_pointer((0, 0), (20, 0), (23, 4)), 10.0)

    def test_arc_slot(self):
        # end centres (10, 0) and (-10, 0), through (0, 10): the upper half of r = 10
        slot = core.arc_slot((10, 0), (-10, 0), (0, 10), 4)
        near(self, slot["centre"], (0, 0))
        self.assertAlmostEqual(slot["radius"], 10.0)
        self.assertAlmostEqual(slot["r"], 2.0)
        self.assertAlmostEqual(slot["a1"], 0.0)
        self.assertAlmostEqual(slot["a2"], math.pi)
        self.assertFalse(slot["reversed"])  # c1 is at a1
        # through the lower half: clockwise from c1, so c1 ends up at a2
        slot = core.arc_slot((10, 0), (-10, 0), (0, -10), 4)
        self.assertAlmostEqual(slot["a2"] - slot["a1"], math.pi)
        self.assertTrue(slot["reversed"])
        self.assertIsNone(core.arc_slot((10, 0), (-10, 0), (0, 10), 25))


class ConicTests(unittest.TestCase):
    S, A, E = (0, 0), (10, 10), (20, 0)

    def test_weight_and_back(self):
        self.assertAlmostEqual(core.conic_weight(0.5), 1.0)
        self.assertAlmostEqual(core.conic_weight(0.75), 3.0)
        self.assertAlmostEqual(core.conic_rho(3.0), 0.75)
        with self.assertRaises(ValueError):
            core.conic_weight(1.0)

    def test_parabola_middle(self):
        # rho 0.5: the curve's middle is halfway from the chord's middle (10, 0) to the apex
        near(self, core.conic_point(self.S, self.A, self.E, 0.5, 0.5), (10, 5))

    def test_shoulder_is_on_the_curve(self):
        for rho in (0.2, 0.5, 0.7, 0.9):
            near(
                self,
                core.conic_point(self.S, self.A, self.E, rho, 0.5),
                core.conic_shoulder(self.S, self.A, self.E, rho),
            )

    def test_ends_and_tangents(self):
        pts = core.conic_points(self.S, self.A, self.E, 0.3, n=1000)
        near(self, pts[0], self.S)
        near(self, pts[-1], self.E)
        # leaves the start towards the apex (direction (1, 1))
        d = core.unit(core.sub(pts[1], pts[0]))
        self.assertAlmostEqual(d[0], d[1], places=2)

    def test_rho_from_pointer(self):
        self.assertAlmostEqual(core.rho_from_pointer(self.S, self.A, self.E, (10, 7)), 0.7)
        self.assertAlmostEqual(core.rho_from_pointer(self.S, self.A, self.E, (4, 7)), 0.7)
        self.assertEqual(core.rho_from_pointer(self.S, self.A, self.E, (10, 30)), core.RHO_MAX)
        self.assertEqual(core.rho_from_pointer(self.S, self.A, self.E, (10, -3)), core.RHO_MIN)


if __name__ == "__main__":
    unittest.main()
