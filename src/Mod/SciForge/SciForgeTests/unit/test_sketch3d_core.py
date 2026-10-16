# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's 3D Sketch: planes, the manipulator's squares, the triad's drag, the stored
curves (no FreeCAD)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sciforge import sketch3d_core as core  # noqa: E402


def near(a, b, tol=1e-9):
    return all(abs(a[i] - b[i]) <= tol for i in range(len(a)))


class Planes(unittest.TestCase):
    def test_ray_meets_each_plane_through_the_anchor(self):
        origin, down = (5.0, 5.0, 50.0), (0.0, 0.0, -1.0)
        self.assertTrue(near(core.ray_plane(origin, down, (0, 0, 0), "XY"), (5, 5, 0)))
        self.assertTrue(near(core.ray_plane(origin, down, (0, 0, 20), "XY"), (5, 5, 20)))
        # a ray along a plane never meets it
        self.assertIsNone(core.ray_plane(origin, down, (0, 0, 0), "YZ"))
        slanted = (1.0, 0.0, -1.0)
        self.assertTrue(near(core.ray_plane((0.0, 3.0, 10.0), slanted, (4, 0, 0), "YZ"), (4, 3, 6)))

    def test_grid_snap_keeps_the_offset_and_snaps_near_lines_only(self):
        # on the ZX plane at y = 3: x and z snap, y stays
        self.assertTrue(near(core.grid_snap((9.9, 3.0, 20.1), (0, 3, 0), "ZX", 10.0), (10, 3, 20)))
        # 15 is half way between 10 and 20: not within a fifth, kept
        self.assertTrue(near(core.grid_snap((15.0, 0.0, 0.0), (0, 0, 0), "XY", 10.0), (15, 0, 0)))
        self.assertEqual(core.grid_snap((1.2, 2.3, 0.0), (0, 0, 0), "XY", None), (1.2, 2.3, 0.0))

    def test_next_plane_cycles(self):
        self.assertEqual(core.next_plane("XY"), "YZ")
        self.assertEqual(core.next_plane("ZX"), "XY")

    def test_on_sketch_plane(self):
        self.assertTrue(core.on_sketch_plane([(0, 0, 0), (3, 4, 0)]))
        self.assertFalse(core.on_sketch_plane([(0, 0, 0), (3, 4, 0.5)]))


class Manipulator(unittest.TestCase):
    def test_squares_lie_in_their_planes(self):
        sq = core.squares((1.0, 2.0, 3.0), 10.0)
        self.assertEqual(sorted(sq), ["XY", "YZ", "ZX"])
        self.assertTrue(all(abs(p[2] - 3.0) < 1e-12 for p in sq["XY"]))
        self.assertTrue(all(abs(p[0] - 1.0) < 1e-12 for p in sq["YZ"]))
        self.assertTrue(all(abs(p[1] - 2.0) < 1e-12 for p in sq["ZX"]))
        # from a fifth of the size to the size, off the anchor
        self.assertTrue(near(sq["XY"][0], (3.0, 4.0, 3.0)))
        self.assertTrue(near(sq["XY"][2], (11.0, 12.0, 3.0)))

    def test_point_in_polygon(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(core.point_in_polygon(5, 5, square))
        self.assertFalse(core.point_in_polygon(15, 5, square))

    def test_segment_distance(self):
        self.assertAlmostEqual(core.segment_distance((5, 3), (0, 0), (10, 0)), 3.0)
        self.assertAlmostEqual(core.segment_distance((13, 4), (0, 0), (10, 0)), 5.0)


class Triad(unittest.TestCase):
    def test_drag_along_an_axis(self):
        # the pointer's ray passes over x = 7 of the X axis through (0, 0, 0)
        t = core.closest_on_axis((7.0, 5.0, 20.0), (0.0, -0.3, -1.0), (0, 0, 0), (1, 0, 0))
        self.assertAlmostEqual(t, 7.0)

    def test_parallel_ray_gives_nothing(self):
        self.assertIsNone(core.closest_on_axis((0, 5, 0), (1, 0, 0), (0, 0, 0), (1, 0, 0)))

    def test_skew_lines(self):
        # Z axis through (2, 3, 0); a ray along X at height 4 crossing y = 3
        t = core.closest_on_axis((-10.0, 3.0, 4.0), (1.0, 0.0, 0.0), (2, 3, 0), (0, 0, 1))
        self.assertAlmostEqual(t, 4.0)


class Stored(unittest.TestCase):
    def test_pairs_and_splines(self):
        self.assertEqual(core.pairs([0, 1, 1, 2]), [(0, 1), (1, 2)])
        self.assertEqual(core.parse_spline("0, 3,4"), [0, 3, 4])
        self.assertEqual(core.parse_spline(""), [])

    def test_join_index(self):
        pts = [(0, 0, 0), (0, 0, 20)]
        self.assertEqual(core.join_index(pts, (0.0, 0.0, 20.0)), 1)
        self.assertIsNone(core.join_index(pts, (0.0, 0.0, 20.1)))

    def test_lengths(self):
        self.assertAlmostEqual(core.length(core.sub((3, 4, 12), (0, 0, 0))), 13.0)
        self.assertAlmostEqual(math.sqrt(core.dot((1, 2, 2), (1, 2, 2))), 3.0)


if __name__ == "__main__":
    unittest.main()
