# SPDX-License-Identifier: LGPL-2.1-or-later
"""The arithmetic of Fillet's and Chamfer's live picture (sciforge/fillet_live_core.py: the
round or bevel follows the radius / distance arrow on every mouse move). The round's points
lie on the rolling ball's circle and touch both faces, outside and inside edges, any corner
angle; Chord Length and Distance and Angle give fillet_core's sizes; the Variable law goes
through its points; two bands meeting at a corner are cut on the plane halving it. Runs
without FreeCAD (the golden models' live_blend_expect checks the picture on real results)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import fillet_core  # noqa: E402
from sciforge import fillet_live_core as core  # noqa: E402

UP = (0.0, 0.0, 1.0)


def normal_at(degrees):
    """A unit normal in the XZ plane, `degrees` from +Z toward +X... (the edge runs along Y)."""
    a = math.radians(degrees)
    return (math.sin(a), 0.0, math.cos(a))


def plane_distance(p, origin, normal):
    return core.dot(core.sub(p, origin), normal)


class Ball(unittest.TestCase):
    def check_round(self, n0, n1, convex, r):
        p = (1.0, 2.0, 3.0)
        dirs = core.ball_dirs(n0, n1, convex, 8)
        centre = core.ball_centre(p, n0, n1, convex, r)
        s = core.side(convex)
        # the centre is r from both faces' planes, on the material side (outside edge) or
        # the air side (inside edge)
        self.assertAlmostEqual(plane_distance(centre, p, n0), s * r)
        self.assertAlmostEqual(plane_distance(centre, p, n1), s * r)
        points = [core.add(p, core.scale(v, r)) for v in dirs]
        for q in points:  # every point on the ball's circle, square to the edge (Y)
            self.assertAlmostEqual(core.norm(core.sub(q, centre)), r)
            self.assertAlmostEqual(q[1], p[1])
        # the ends touch the faces (on their planes)
        self.assertAlmostEqual(plane_distance(points[0], p, n0), 0.0)
        self.assertAlmostEqual(plane_distance(points[-1], p, n1), 0.0)
        return points, centre

    def test_box_edge(self):
        # top face (+Z) and front face (+X) of a box: outside edge, the round cuts the corner
        points, centre = self.check_round(UP, (1.0, 0.0, 0.0), True, 2.0)
        self.assertTrue(all(q[0] <= 1.0 + 1e-12 and q[2] <= 3.0 + 1e-12 for q in points))
        mid = points[4]
        # the middle of the arc is r(sqrt(2) - 1) from the corner
        self.assertAlmostEqual(core.norm(core.sub(mid, (1.0, 2.0, 3.0))), 2.0 * (2**0.5 - 1))

    def test_inside_edge(self):
        # an L's inside corner: floor (+Z) and wall facing -X... the round fills the air
        points, centre = self.check_round(UP, (-1.0, 0.0, 0.0), False, 1.5)
        self.assertGreater(centre[2], 3.0)
        self.assertLess(centre[0], 1.0)

    def test_any_angle(self):
        for degrees in (30.0, 60.0, 120.0, 150.0):
            for convex in (True, False):
                self.check_round(UP, normal_at(degrees), convex, 0.7)

    def test_radius_scales_the_points(self):
        dirs = core.ball_dirs(UP, (1.0, 0.0, 0.0), True, 4)
        p = (0.0, 0.0, 0.0)
        for r in (0.5, 1.0, 3.0):
            for v in dirs:
                q = core.add(p, core.scale(v, r))
                self.assertAlmostEqual(core.norm(q), r * core.norm(v))

    def test_tangent_faces_refused(self):
        with self.assertRaises(ValueError):
            core.ball_dirs(UP, UP, True, 4)
        with self.assertRaises(ValueError):
            core.ball_dirs(UP, (0.0, 0.0, -1.0), True, 4)


class Sizes(unittest.TestCase):
    def test_chord_matches_fillet_core(self):
        for degrees in (90.0, 60.0, 120.0):
            n1 = normal_at(degrees)
            self.assertAlmostEqual(
                core.chord_radius(3.0, UP, n1),
                fillet_core.chord_radius(3.0, math.radians(degrees)),
            )

    def test_angle_chamfer_matches_fillet_core(self):
        for degrees in (90.0, 60.0, 135.0):
            n1 = normal_at(degrees)
            gamma = math.pi - math.radians(degrees)
            self.assertAlmostEqual(
                core.angle_second(2.0, 30.0, UP, n1),
                fillet_core.angle_distance2(2.0, 30.0, gamma),
            )
        # past what reaches the other face: no band
        self.assertIsNone(core.angle_second(2.0, 95.0, UP, (1.0, 0.0, 0.0)))

    def test_straight_law(self):
        self.assertAlmostEqual(core.interp([0.0, 0.5, 1.0], [1.0, 3.0, 1.5], 0.25), 2.0)
        self.assertAlmostEqual(core.interp([0.0, 1.0], [1.0, 2.0], 2.0), 2.0)

    def test_smooth_law_goes_through_its_points(self):
        pos, rad = [0.0, 0.5, 1.0], [1.0, 3.0, 1.5]
        for p, r in zip(pos, rad):
            self.assertAlmostEqual(core.smooth(pos, rad, p), r)
        # two points: a straight line
        self.assertAlmostEqual(core.smooth([0.0, 1.0], [1.0, 2.0], 0.3), 1.3)
        # rounded off over the straight law near the peak (as OpenCASCADE's is)
        self.assertGreater(core.smooth(pos, rad, 0.375), core.interp(pos, rad, 0.375))
        # measured on OpenCASCADE's round (40 mm edge): within 0.1 mm everywhere
        measured = {0.125: 1.4952, 0.25: 2.1343, 0.375: 2.7068, 0.625: 2.8664, 0.75: 2.4387}
        for p, r in measured.items():
            self.assertLess(abs(core.smooth(pos, rad, p) - r), 0.1)


class Corners(unittest.TestCase):
    def test_mitre_halves_a_square_corner(self):
        # two top edges of a box meeting at the origin: one runs along +X, the other +Y
        plane = core.mitre((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        origin, normal = plane
        self.assertAlmostEqual(normal[0], -normal[1])
        # a point of the X edge's band past the diagonal is slid back onto it along X
        q = core.clamp((0.2, 0.5, -0.3), (1.0, 0.0, 0.0), plane)
        self.assertAlmostEqual(q[0], 0.5)
        self.assertAlmostEqual(q[1], 0.5)
        # a point on the kept side stays
        self.assertEqual(core.clamp((2.0, 0.5, 0.0), (1.0, 0.0, 0.0), plane), (2.0, 0.5, 0.0))

    def test_straight_on_cuts_square(self):
        # a tangent chain: the next edge carries on the same way: the cut is square to it
        origin, normal = core.mitre((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
        self.assertAlmostEqual(normal[0], 1.0)

    def test_doubling_back_has_no_cut(self):
        self.assertIsNone(core.mitre((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)))


if __name__ == "__main__":
    unittest.main()
