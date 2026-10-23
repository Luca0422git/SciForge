# SPDX-License-Identifier: LGPL-2.1-or-later
"""The arithmetic of the live pictures of Press Pull, Shell and Extrude
(sciforge/live_core.py): how a point of a moved face moves (alone, at an edge beside a face
that stays, at a corner of two moved faces), how an outline corner moves in its plane for a
taper, where the ends of an extrusion are, and the quads between two rows. Runs without
FreeCAD; the pictures against FreeCAD's exact solids: test_live_shapes_freecad.py."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import live_core as core  # noqa: E402

X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class OffsetMove(unittest.TestCase):
    def test_a_face_alone_moves_along_its_normal(self):
        self.assertTrue(close(core.offset_move([(Z, 1.0)]), Z))

    def test_beside_a_face_that_stays_it_slides_along_it(self):
        # a box's top pulled up: its edge with a side stays on the side's plane
        w = core.offset_move([(Z, 1.0), (X, 0.0)])
        self.assertTrue(close(w, Z))
        # a corner: on two sides
        self.assertTrue(close(core.offset_move([(Z, 1.0), (X, 0.0), (Y, 0.0)]), Z))

    def test_beside_a_sloping_face_it_keeps_the_slope(self):
        s = core.unit((1.0, 0.0, 1.0))  # a 45 deg slope beside the top
        w = core.offset_move([(Z, 1.0), (s, 0.0)])
        self.assertAlmostEqual(core.dot(w, Z), 1.0)
        self.assertAlmostEqual(core.dot(w, s), 0.0)

    def test_two_moved_faces_meet_in_a_sharp_corner(self):
        w = core.offset_move([(Z, 1.0), (X, 1.0)])
        self.assertTrue(close(w, (1.0, 0.0, 1.0)))
        w = core.offset_move([(Z, 1.0), (X, 1.0), (Y, 1.0)])
        self.assertTrue(close(w, (1.0, 1.0, 1.0)))

    def test_tangent_faces_count_once(self):
        # a flat face continued smoothly by a round one: one direction
        self.assertTrue(close(core.offset_move([(Z, 1.0), (Z, 1.0)]), Z))
        # the moved one decides over a tangent face that stays
        self.assertTrue(close(core.offset_move([(Z, 0.0), (Z, 1.0)]), Z))

    def test_nothing_moves(self):
        self.assertTrue(close(core.offset_move([(X, 0.0), (Y, 0.0)]), (0.0, 0.0, 0.0)))
        self.assertTrue(close(core.offset_move([]), (0.0, 0.0, 0.0)))

    def test_shell_rim_point(self):
        # Shell: a side wall moved inward (its outward normal X, by -t) at the opened top
        w = core.offset_move([(X, 1.0), (Z, 0.0)])
        self.assertTrue(close(core.scale(w, -2.0), (-2.0, 0.0, 0.0)))

    def test_four_directions_keep_the_moved_ones(self):
        tilted = core.unit((1.0, 1.0, 1.0))
        w = core.offset_move([(Z, 1.0), (X, 0.0), (Y, 0.0), (tilted, 0.0)])
        self.assertAlmostEqual(core.dot(w, Z), 1.0)


class InPlane(unittest.TestCase):
    def test_a_straight_side_moves_square_to_itself(self):
        self.assertTrue(close(core.in_plane_move([X], Z), X))

    def test_a_corner_moves_along_its_bisector(self):
        w = core.in_plane_move([X, Y], Z)
        self.assertTrue(close(w, (1.0, 1.0, 0.0)))  # both sides move by 1

    def test_stays_in_the_plane(self):
        w = core.in_plane_move([core.unit((1.0, 0.0, 0.3))], Z)
        self.assertAlmostEqual(w[2], 0.0)


class ExtrudeEnds(unittest.TestCase):
    def test_one_side(self):
        self.assertEqual(core.extrude_ends("one_side", 10.0), [(0.0, 0.0), (10.0, 10.0)])
        self.assertEqual(core.extrude_ends("one_side", 5.0, start=2.0), [(2.0, 0.0), (7.0, 5.0)])

    def test_symmetric(self):
        self.assertEqual(core.extrude_ends("symmetric", 10.0), [(-5.0, 5.0), (5.0, 5.0)])
        self.assertEqual(
            core.extrude_ends("symmetric", 10.0, measurement="half"), [(-10.0, 10.0), (10.0, 10.0)]
        )

    def test_two_sides(self):
        self.assertEqual(core.extrude_ends("two_sides", 8.0, 3.0), [(-3.0, 3.0), (8.0, 8.0)])

    def test_taper_inset(self):
        self.assertAlmostEqual(core.taper_inset(10.0, 45.0), 10.0)
        self.assertAlmostEqual(core.taper_inset(10.0, 0.0), 0.0)
        self.assertAlmostEqual(core.taper_inset(4.0, 10.0), 4.0 * math.tan(math.radians(10.0)))


class Quads(unittest.TestCase):
    def test_strip(self):
        tris = core.strip(3, 0, 10)
        self.assertEqual(len(tris), 4)
        self.assertEqual(tris[0], (0, 1, 11))
        self.assertEqual(tris[1], (0, 11, 10))

    def test_near_polyline(self):
        line = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)]
        self.assertTrue(core.near_polyline((5.0, 0.001, 0.0), line, 0.01))
        self.assertTrue(core.near_polyline((10.0, 5.0, 0.0), line, 0.01))
        self.assertFalse(core.near_polyline((5.0, 5.0, 0.0), line, 0.01))


if __name__ == "__main__":
    unittest.main()
