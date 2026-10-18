# SPDX-License-Identifier: LGPL-2.1-or-later
"""How big Split Body's red splitting-tool preview is drawn (sciforge/split_core.py): over
the whole body plus a margin, in the tool's plane or along its axis. Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import split_core as core  # noqa: E402

BOX = (-20.0, -15.0, 0.0, 20.0, 15.0, 10.0)  # bodies_split's Body1


class Margin(unittest.TestCase):
    def test_a_tenth_of_the_diagonal(self):
        diagonal = (40.0**2 + 30.0**2 + 10.0**2) ** 0.5
        self.assertAlmostEqual(core.margin(BOX), core.MARGIN * diagonal)

    def test_a_tiny_body_still_gets_a_rim(self):
        self.assertEqual(core.margin((0, 0, 0, 0.1, 0.1, 0.1)), core.MIN_MARGIN)

    def test_eight_corners(self):
        found = core.corners(BOX)
        self.assertEqual(len(set(found)), 8)
        self.assertIn((-20.0, -15.0, 0.0), found)
        self.assertIn((20.0, 15.0, 10.0), found)


class Plane(unittest.TestCase):
    def test_covers_every_corner_and_the_rim(self):
        # The YZ plane: (u, v) = (y, z) of each corner.
        uvs = [(c[1], c[2]) for c in core.corners(BOX)]
        u0, u1, v0, v1 = core.cover_uv(uvs, 5.0)
        self.assertEqual((u0, u1, v0, v1), (-20.0, 20.0, -5.0, 15.0))

    def test_nothing_to_cover(self):
        self.assertEqual(core.cover_uv([], 2.0), (-2.0, 2.0, -2.0, 2.0))


class Axis(unittest.TestCase):
    def test_along_z_through_the_middle(self):
        low, high = core.cover_axis(BOX, (0, 0, 5), (0, 0, 1))
        rim = core.margin(BOX)
        self.assertAlmostEqual(low, -5.0 - rim)
        self.assertAlmostEqual(high, 5.0 + rim)

    def test_a_tilted_axis_reaches_the_far_corners(self):
        d = 2**-0.5
        low, high = core.cover_axis(BOX, (0, 0, 0), (d, d, 0))
        rim = core.margin(BOX)
        self.assertAlmostEqual(high, (20 + 15) * d + rim)
        self.assertAlmostEqual(low, -(20 + 15) * d - rim)

    def test_vectors_with_xyz(self):
        class V:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        self.assertEqual(core.along([V(1, 2, 3)], V(0, 0, 0), V(0, 1, 0)), [2])


if __name__ == "__main__":
    unittest.main()
