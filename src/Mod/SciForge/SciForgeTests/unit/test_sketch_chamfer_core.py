# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch Chamfer: the corner, the setbacks of its three types (no FreeCAD)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sciforge import sketch_chamfer_core as core  # noqa: E402

BOTTOM = ((0.0, 0.0), (40.0, 0.0))
RIGHT = ((40.0, 0.0), (40.0, 20.0))


class Corner(unittest.TestCase):
    def test_shared_end(self):
        point, u1, u2, r1, r2, angle = core.corner(BOTTOM, RIGHT)
        self.assertAlmostEqual(point[0], 40.0)
        self.assertAlmostEqual(point[1], 0.0)
        self.assertAlmostEqual(u1[0], -1.0)  # along the bottom, back to (0, 0)
        self.assertAlmostEqual(u2[1], 1.0)  # up the right side
        self.assertAlmostEqual(r1, 40.0)
        self.assertAlmostEqual(r2, 20.0)
        self.assertAlmostEqual(angle, math.pi / 2)

    def test_lines_that_do_not_touch(self):
        # the extensions cross at (10, 0); the clicks say which parts stay
        point, u1, u2, r1, r2, _ = core.corner(
            ((0.0, 0.0), (8.0, 0.0)), ((10.0, 3.0), (10.0, 20.0)), (4.0, 0.0), (10.0, 15.0)
        )
        self.assertAlmostEqual(point[0], 10.0)
        self.assertAlmostEqual(point[1], 0.0)
        self.assertAlmostEqual(r1, 10.0)
        self.assertAlmostEqual(r2, 20.0)

    def test_crossing_lines_keep_the_clicked_parts(self):
        # an X: keep the right part of the level line and the top of the upright one
        _point, u1, u2, r1, r2, _ = core.corner(
            ((-10.0, 0.0), (10.0, 0.0)), ((0.0, -10.0), (0.0, 10.0)), (5.0, 0.0), (0.0, 5.0)
        )
        self.assertAlmostEqual(u1[0], 1.0)
        self.assertAlmostEqual(u2[1], 1.0)
        self.assertAlmostEqual(r1, 10.0)
        self.assertAlmostEqual(r2, 10.0)

    def test_parallel_lines_refused(self):
        with self.assertRaises(core.ChamferError):
            core.corner(((0.0, 0.0), (10.0, 0.0)), ((0.0, 5.0), (10.0, 5.0)))


class Setbacks(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(core.setbacks("equal", math.pi / 2, 5.0), (5.0, 5.0))

    def test_two_distances(self):
        self.assertEqual(core.setbacks("two_distances", math.pi / 2, 3.0, 6.0), (3.0, 6.0))

    def test_distance_and_angle_square_corner(self):
        # 5 along the first line, 30 degrees to it: the second setback is 5 tan 30
        s1, s2 = core.setbacks("distance_angle", math.pi / 2, 5.0, math.radians(30))
        self.assertAlmostEqual(s1, 5.0)
        self.assertAlmostEqual(s2, 5.0 * math.tan(math.radians(30)))

    def test_distance_and_angle_other_corner(self):
        # 60 degree corner, 45 degrees: law of sines d2 = d sin 45 / sin 105
        s1, s2 = core.setbacks("distance_angle", math.radians(60), 4.0, math.radians(45))
        self.assertAlmostEqual(s2, 4.0 * math.sin(math.radians(45)) / math.sin(math.radians(105)))
        self.assertAlmostEqual(core.chamfer_angle(math.radians(60), s1, s2), math.radians(45))

    def test_default_angle_is_symmetric(self):
        s1, s2 = core.setbacks("distance_angle", math.radians(70), 4.0)
        self.assertAlmostEqual(s1, s2)
        self.assertAlmostEqual(core.default_angle(math.pi / 2), math.pi / 4)

    def test_angle_too_big_refused(self):
        with self.assertRaises(core.ChamferError):
            core.setbacks("distance_angle", math.pi / 2, 5.0, math.radians(95))

    def test_no_distance_refused(self):
        with self.assertRaises(core.ChamferError):
            core.setbacks("equal", math.pi / 2, 0.0)
        with self.assertRaises(core.ChamferError):
            core.setbacks("two_distances", math.pi / 2, 3.0, None)

    def test_must_fit(self):
        core.check_fits(5.0, 5.0, 40.0, 20.0)
        with self.assertRaises(core.ChamferError):
            core.check_fits(25.0, 5.0, 20.0, 40.0)
        with self.assertRaises(core.ChamferError):
            core.check_fits(5.0, 20.0, 40.0, 20.0)


class Placing(unittest.TestCase):
    def test_points(self):
        point, u1, u2, _r1, _r2, _a = core.corner(BOTTOM, RIGHT)
        p1, p2 = core.points(point, u1, u2, 5.0, 3.0)
        self.assertAlmostEqual(p1[0], 35.0)
        self.assertAlmostEqual(p2[1], 3.0)

    def test_equal_runs_through_the_pointer(self):
        point, u1, u2, _r1, _r2, angle = core.corner(BOTTOM, RIGHT)
        got = core.pointer_values("equal", point, u1, u2, angle, (37.0, 3.0))
        p1, p2 = core.points(point, u1, u2, got["distance"], got["distance"])
        # the pointer lies on the chamfer line
        cross = (p2[0] - p1[0]) * (3.0 - p1[1]) - (p2[1] - p1[1]) * (37.0 - p1[0])
        self.assertAlmostEqual(cross, 0.0)
        self.assertAlmostEqual(got["distance"], 6.0)

    def test_two_distances_from_the_pointer(self):
        point, u1, u2, _r1, _r2, angle = core.corner(BOTTOM, RIGHT)
        got = core.pointer_values("two_distances", point, u1, u2, angle, (36.0, 2.0))
        self.assertAlmostEqual(got["distance"], 4.0)
        self.assertAlmostEqual(got["distance2"], 2.0)

    def test_fillet_radius(self):
        # FreeCAD's arc touching both lines 5 from a square corner has radius 5
        self.assertAlmostEqual(core.fillet_radius(5.0, math.pi / 2), 5.0)


# a line ending on a quarter arc: (0, 0)-(40, 0), then about (55, 0) up to (55, 15)
LINE = ((0.0, 0.0), (40.0, 0.0))
ARC = ((55.0, 0.0), 15.0, math.pi / 2, math.pi)


class LineAndArc(unittest.TestCase):
    def setUp(self):
        self.data = core.line_arc_corner(LINE, ARC)

    def test_corner(self):
        d = self.data
        self.assertAlmostEqual(d["point"][0], 40.0)
        self.assertAlmostEqual(d["point"][1], 0.0)
        self.assertAlmostEqual(d["u1"][0], -1.0)
        self.assertAlmostEqual(d["u2"][1], 1.0)  # the arc leaves the corner straight up
        self.assertAlmostEqual(d["angle"], math.pi / 2)
        self.assertAlmostEqual(d["reach2"], math.pi / 2)

    def test_equal(self):
        s_line, s_arc, p1, p2 = core.line_arc_values("equal", self.data, 4.0)
        self.assertEqual((s_line, s_arc), (4.0, 4.0))
        self.assertAlmostEqual(p1[0], 36.0)
        self.assertAlmostEqual(math.hypot(p2[0] - 40.0, p2[1]), 4.0)  # straight from the corner
        self.assertAlmostEqual(math.hypot(p2[0] - 55.0, p2[1]), 15.0)  # on the arc
        self.assertGreater(p2[1], 0.0)

    def test_two_distances_follow_the_pick_order(self):
        line_first = core.line_arc_values("two_distances", self.data, 3.0, 5.0, True)
        arc_first = core.line_arc_values("two_distances", self.data, 5.0, 3.0, False)
        self.assertEqual(line_first[:2], (3.0, 5.0))
        self.assertEqual(arc_first[:2], (3.0, 5.0))

    def test_distance_and_angle(self):
        alpha = math.radians(40)
        s_line, chord, p1, p2 = core.line_arc_values("distance_angle", self.data, 5.0, alpha)
        self.assertAlmostEqual(core.angle_at_line(self.data, p1, p2), alpha)
        self.assertAlmostEqual(math.hypot(p2[0] - 55.0, p2[1]), 15.0)
        self.assertAlmostEqual(chord, math.hypot(p2[0] - 40.0, p2[1]))

    def test_refusals(self):
        with self.assertRaises(core.ChamferError):
            core.line_arc_values("equal", self.data, 45.0)  # longer than the line
        with self.assertRaises(core.ChamferError):
            core.line_arc_values("equal", self.data, 25.0)  # past the arc's other end

    def test_tangent_line_and_arc_make_no_corner(self):
        arc = ((40.0, 15.0), 15.0, -math.pi / 2, math.pi / 2)  # leaves (40, 0) along the line
        with self.assertRaises(core.ChamferError):
            core.line_arc_corner(LINE, arc)

    def test_line_that_stops_short(self):
        # the line ends at (35, 0): the corner is where it would meet the arc's circle
        d = core.line_arc_corner(((0.0, 0.0), (35.0, 0.0)), ARC, (10.0, 0.0), (44.4, 10.6))
        self.assertAlmostEqual(d["point"][0], 40.0)
        self.assertAlmostEqual(d["point"][1], 0.0)


if __name__ == "__main__":
    unittest.main()
