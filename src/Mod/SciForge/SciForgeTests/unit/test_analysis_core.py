# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of the INSPECT surface analyses (sciforge/analysis_core.py)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sciforge import analysis_core as c  # noqa: E402

try:
    import numpy  # noqa: F401

    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


class DraftTest(unittest.TestCase):
    def test_angles(self):
        up = (0, 0, 1)
        self.assertTrue(close(c.draft_angle((0, 0, 1), up), 90))
        self.assertTrue(close(c.draft_angle((0, 0, -1), up), -90))
        self.assertTrue(close(c.draft_angle((1, 0, 0), up), 0))
        n = (math.cos(math.radians(5)), 0, math.sin(math.radians(5)))
        self.assertTrue(close(c.draft_angle(n, up), 5, 1e-7))
        self.assertTrue(close(c.draft_angle((2, 0, 0), (0, 0, 7)), 0))  # not unit: fine

    def test_classes(self):
        self.assertEqual(c.draft_class(10, 1, 3), "positive")
        self.assertEqual(c.draft_class(3, 1, 3), "positive")
        self.assertEqual(c.draft_class(2, 1, 3), "tolerance+")
        self.assertEqual(c.draft_class(1, 1, 3), "tolerance+")
        self.assertEqual(c.draft_class(0.5, 1, 3), "vertical")
        self.assertEqual(c.draft_class(0, 1, 3), "vertical")
        self.assertEqual(c.draft_class(-0.5, 1, 3), "vertical")
        self.assertEqual(c.draft_class(-2, 1, 3), "tolerance-")
        self.assertEqual(c.draft_class(-3, 1, 3), "negative")
        self.assertEqual(c.draft_class(-90, 1, 3), "negative")
        # start and stop given the other way round or negative: same thing
        self.assertEqual(c.draft_class(2, 3, 1), "tolerance+")
        self.assertEqual(c.draft_class(2, -1, -3), "tolerance+")
        # no tolerance band: only exactly vertical is red
        self.assertEqual(c.draft_class(0.01, 0, 0), "positive")
        self.assertEqual(c.draft_class(0, 0, 0), "vertical")
        self.assertEqual(c.draft_class(-0.01, 0, 0), "negative")
        # start == stop: below red, from it on green / blue
        self.assertEqual(c.draft_class(1.9, 2, 2), "vertical")
        self.assertEqual(c.draft_class(2, 2, 2), "positive")

    def test_colors(self):
        self.assertEqual(c.draft_color(10, 1, 3), c.GREEN)
        self.assertEqual(c.draft_color(-10, 1, 3), c.BLUE)
        self.assertEqual(c.draft_color(0, 1, 3), c.RED)
        self.assertEqual(c.draft_color(2, 1, 3, tolerance_zone=True), c.YELLOW)
        self.assertEqual(c.draft_color(-2, 1, 3, tolerance_zone=True), c.YELLOW)
        mid = c.draft_color(2, 1, 3)  # halfway red -> green
        for i in range(3):
            self.assertTrue(close(mid[i], (c.RED[i] + c.GREEN[i]) / 2))
        mid = c.draft_color(-2, 1, 3)
        for i in range(3):
            self.assertTrue(close(mid[i], (c.RED[i] + c.BLUE[i]) / 2))


class ZebraTest(unittest.TestCase):
    VIEW = (0, 0, -1)
    RIGHT = (1, 0, 0)
    UP = (0, 1, 0)

    def param(self, point, normal, vertical=False, centre=(0, 0, 0), radius=100):
        return c.zebra_parameter(
            point, normal, self.VIEW, self.RIGHT, self.UP, centre, radius, vertical
        )

    def test_facing_the_camera_reflects_straight_back(self):
        self.assertTrue(close(self.param((0, 0, 0), (0, 0, 1)), 0.5))

    def test_smooth_on_a_cylinder(self):
        # a horizontal cylinder (axis X) seen from the front (camera looking along +Y... here
        # along -Z, up = Y): its normal turns in the YZ plane; the reflection sweeps the
        # horizontal stripes up to the pole and folds back, without a jump
        values = []
        for k in range(-80, 81, 2):
            a = math.radians(k)
            n = (0.0, math.sin(a), math.cos(a))
            values.append(self.param((0, 0, 0), n))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in values))
        steps = [abs(b - a) for a, b in zip(values, values[1:])]
        self.assertLess(max(steps), 0.03, steps)  # no jump anywhere
        middle = values[len(values) // 2 - 10 : len(values) // 2 + 11]  # +-20 degrees
        self.assertTrue(all(b > a for a, b in zip(middle, middle[1:])), middle)
        # vertical stripes do not change along that cylinder (its points on the axis)
        vertical = [
            self.param((0, 0, 0), (0.0, math.sin(math.radians(k)), math.cos(math.radians(k))), True)
            for k in range(-80, 81, 10)
        ]
        self.assertTrue(max(vertical) - min(vertical) < 1e-9, vertical)

    def test_a_flat_face_shows_stripes_across_it(self):
        # a flat face reflects to different places of the surroundings (they are near)
        a = self.param((0, -20, 0), (0, 0, 1))
        b = self.param((0, 20, 0), (0, 0, 1))
        self.assertGreater(b, a)
        self.assertTrue(close(self.param((-20, 0, 0), (0, 0, 1)), 0.5))

    def test_seen_from_behind(self):
        self.assertTrue(close(self.param((0, 0, 0), (0, 0, -1)), 0.5))

    def test_stripes(self):
        self.assertEqual(c.stripe_of(0.0, 10), 1)
        self.assertEqual(c.stripe_of(0.06, 10), 0)
        self.assertEqual(c.stripe_of(0.1, 10), 1)
        self.assertEqual(c.stripe_of(0.3, 0), 1)  # at least one pair

    @unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
    def test_many_points_at_once(self):
        points, normals = [], []
        for k in range(-8, 9):
            a = math.radians(k * 10)
            points.append((k * 2.0, k * 1.5, -k * 0.5))
            normals.append((0.3 * math.cos(a), math.sin(a), math.cos(a)))
        for vertical in (False, True):
            many = c.zebra_parameters(
                points, normals, self.VIEW, self.RIGHT, self.UP, (1, 2, 3), 80, vertical
            )
            one = [
                c.zebra_parameter(p, n, self.VIEW, self.RIGHT, self.UP, (1, 2, 3), 80, vertical)
                for p, n in zip(points, normals)
            ]
            for a, b in zip(many, one):
                self.assertTrue(close(a, b, 1e-9), (a, b))


class CombTest(unittest.TestCase):
    def test_params(self):
        self.assertEqual(c.comb_params(0, 1, 5), [0.0, 0.25, 0.5, 0.75, 1.0])
        self.assertEqual(len(c.comb_params(0, 1, 1)), 2)  # Fusion's minimum is 2
        self.assertEqual(len(c.comb_params(0, 1, 500)), 100)  # and maximum 100
        p = c.comb_params(2.0, 6.0, 3)
        self.assertEqual(p, [2.0, 4.0, 6.0])

    def test_gain_and_teeth(self):
        # the tallest tooth is a quarter of the reference size at scale 1
        gain = c.comb_gain([0.1, 0.25, 0.2], 40.0)
        self.assertTrue(close(0.25 * gain, 10.0))
        self.assertTrue(close(0.25 * c.comb_gain([0.1, 0.25], 40.0, 2.0), 20.0))
        self.assertEqual(c.comb_gain([0, 0], 40.0), 0.0)
        # on a circle of radius 4 around the origin, at (4, 0, 0): the centre is at -X, so
        # the tooth points out along +X, as long as curvature x gain
        tip = c.comb_tooth((4, 0, 0), (-1, 0, 0), 0.25, 8.0)
        self.assertEqual(tip, (6.0, 0.0, 0.0))
        # a straight piece: no tooth
        self.assertEqual(c.comb_tooth((1, 2, 3), (0, 0, 0), 0.0, 8.0), (1, 2, 3))

    def test_colours(self):
        self.assertEqual(c.comb_color(0.0, 1.0), c.BLUE)
        self.assertEqual(c.comb_color(1.0, 1.0), c.RED)
        self.assertEqual(c.comb_color(0.3, 0.0), c.BLUE)

    def test_isocurves(self):
        self.assertEqual(c.iso_values(0, 4, 3), [1.0, 2.0, 3.0])
        self.assertEqual(c.iso_values(0, 1, 0), [])
        self.assertEqual(len(c.iso_values(-1, 1, 5)), 5)
        self.assertTrue(all(-1 < v < 1 for v in c.iso_values(-1, 1, 5)))


class CurvatureMapTest(unittest.TestCase):
    def test_gaussian(self):
        self.assertEqual(c.gaussian_level(0.0, 0.25, 50), 0.0)  # cylinder: flat one way
        dome = c.gaussian_level(-0.25, -0.25, 50)  # convex ball r = 4
        saddle = c.gaussian_level(0.25, -0.25, 50)
        self.assertGreater(dome, 0)
        self.assertLess(saddle, 0)
        self.assertTrue(close(dome, 0.625))  # sqrt(1/16) * 50 / 20
        self.assertEqual(c.gaussian_level(-1, -1, 50), 1.0)  # clamped
        self.assertTrue(close(c.gaussian_level(-0.25, -0.25, 50, 0.5), 0.3125))
        self.assertEqual(c.gaussian_color(0.0), c.GREEN)
        self.assertEqual(c.gaussian_color(1.0), c.RED)
        self.assertEqual(c.gaussian_color(-1.0), c.VIOLET)
        # bands: no blending, steps of a quarter
        self.assertEqual(c.gaussian_color(0.3, bands=True), c.gaussian_color(0.5))
        self.assertEqual(c.gaussian_color(0.25, bands=True), c.gaussian_color(0.25))

    def test_principal(self):
        self.assertEqual(c.principal_value(-0.25, 0.0, "Principal Minimum"), 0.0)
        self.assertEqual(c.principal_value(-0.25, 0.0, "Principal Maximum"), 0.25)
        self.assertEqual(c.limit_color(0.0, 10), c.GREEN)
        self.assertEqual(c.limit_color(0.1, 10), c.RED)  # radius 10: at the limit
        self.assertEqual(c.limit_color(0.25, 10), c.RED)
        half = c.limit_color(0.05, 10)
        for i in range(3):
            self.assertTrue(close(half[i], (c.GREEN[i] + c.YELLOW[i]) / 2))
        self.assertEqual(c.limit_color(0.0, 0), c.GREEN)
        self.assertEqual(c.limit_color(0.2, 0), c.RED)


class AccessibilityTest(unittest.TestCase):
    TRI = ((-1, -1, 5), (1, -1, 5), (0, 1, 5))  # a roof at z = 5 over the origin

    def test_ray(self):
        self.assertTrue(c.ray_hits_triangle((0, 0, 0), (0, 0, 1), *self.TRI))
        self.assertFalse(c.ray_hits_triangle((0, 0, 0), (0, 0, -1), *self.TRI))
        self.assertFalse(c.ray_hits_triangle((5, 0, 0), (0, 0, 1), *self.TRI))
        self.assertFalse(c.ray_hits_triangle((0, 0, 0), (1, 0, 0), *self.TRI))

    def test_accessible(self):
        up = (0, 0, 1)
        self.assertFalse(c.accessible((0, 0, 0), up, up, [self.TRI]))  # under the roof
        self.assertTrue(c.accessible((5, 0, 0), up, up, [self.TRI]))
        self.assertFalse(c.accessible((5, 0, 0), (0, 0, -1), up, [self.TRI]))  # faces away
        self.assertFalse(c.accessible((5, 0, 0), (1, 0, 0), up, []))  # a wall: no
        self.assertEqual(c.access_directions(up, "Direction 1"), [up])
        self.assertEqual(c.access_directions(up, "Direction 2"), [(0, 0, -1)])
        self.assertEqual(len(c.access_directions(up, "Both Directions")), 2)

    def test_many_points(self):
        points = [(0, 0, 0), (5, 0, 0), (0, 0, 6), (0.2, 0.1, 0)]
        normals = [(0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, -1)]
        dirs = [(0, 0, 1)]
        expect = [False, True, True, False]
        self.assertEqual(c.reachable_points(points, normals, dirs, [self.TRI]), expect)
        both = c.reachable_points(points, normals, [(0, 0, 1), (0, 0, -1)], [self.TRI])
        self.assertEqual(both, [False, True, True, True])


class MinimumRadiusTest(unittest.TestCase):
    def test_concave(self):
        self.assertIsNone(c.concave_radius(-0.25, 0.0))  # convex round
        self.assertIsNone(c.concave_radius(0.0, 0.0))  # flat
        self.assertTrue(close(c.concave_radius(0.2, 0.0), 5.0))  # a hole r = 5
        self.assertTrue(close(c.concave_radius(0.5, 0.25), 2.0))  # the tighter one

    def test_colors(self):
        self.assertEqual(c.min_radius_color(None, 1, 5), c.NEUTRAL)
        self.assertEqual(c.min_radius_color(6, 1, 5), c.GREEN)
        self.assertEqual(c.min_radius_color(5, 1, 5), c.GREEN)
        self.assertEqual(c.min_radius_color(0.5, 1, 5), c.RED)
        self.assertEqual(c.min_radius_color(3, 1, 5), c.YELLOW)
        self.assertEqual(c.min_radius_color(0.5, 0, 0), c.GREEN)  # no tool: all fits


class MeshTest(unittest.TestCase):
    def test_subdivide(self):
        pts = [(0, 0, 0), (10, 0, 0), (0, 10, 0)]
        p, t = c.subdivide(pts, [(0, 1, 2)], 100)
        self.assertEqual((len(p), len(t)), (3, 1))
        p, t = c.subdivide(pts, [(0, 1, 2)], 8)
        self.assertEqual(len(t), 4)
        self.assertEqual(len(p), 6)
        p, t = c.subdivide(pts, [(0, 1, 2)], 3)
        self.assertEqual(len(t), 64)
        # every new point lies in the old triangle (z = 0, x, y >= 0, x + y <= 10)
        for x, y, z in p:
            self.assertEqual(z, 0)
            self.assertTrue(x >= 0 and y >= 0 and x + y <= 10 + 1e-9)
        # the area is kept
        area = 0.0
        for i, j, k in t:
            area += c.length(c.cross(c.sub(p[j], p[i]), c.sub(p[k], p[i]))) / 2
        self.assertTrue(close(area, 50.0, 1e-9))
        # shared sides share their midpoints
        p, t = c.subdivide(
            [(0, 0, 0), (10, 0, 0), (0, 10, 0), (10, 10, 0)], [(0, 1, 2), (1, 3, 2)], 8
        )
        self.assertEqual(len(p), 9)

    def test_ramp(self):
        self.assertEqual(c.ramp([c.RED], 0.5), c.RED)
        self.assertEqual(c.ramp([c.RED, c.GREEN], 0.0), c.RED)
        self.assertEqual(c.ramp([c.RED, c.GREEN], 2.0), c.GREEN)


if __name__ == "__main__":
    unittest.main()
