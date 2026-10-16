# SPDX-License-Identifier: LGPL-2.1-or-later
"""How the origin planes and axes look (sciforge/origin_look.py): one colour per axis, a
plane in the colour of the axis it faces, smaller squares, labels away from the part. Runs
without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import origin_look as look  # noqa: E402


class Colours(unittest.TestCase):
    def test_plane_takes_the_colour_of_its_normal(self):
        self.assertEqual(look.plane_colour("XY_Plane"), look.AXIS_RGB["Z"])
        self.assertEqual(look.plane_colour("XZ_Plane001"), look.AXIS_RGB["Y"])
        self.assertEqual(look.plane_colour("YZ_Plane"), look.AXIS_RGB["X"])

    def test_red_green_blue(self):
        r, g, b = (look.AXIS_RGB[k] for k in "XYZ")
        self.assertEqual(max(range(3), key=lambda i: r[i]), 0)
        self.assertEqual(max(range(3), key=lambda i: g[i]), 1)
        self.assertEqual(max(range(3), key=lambda i: b[i]), 2)

    def test_keys(self):
        self.assertEqual(look.plane_key("XZ_Plane002"), "XZ")
        self.assertEqual(look.plane_key("Sketch"), "")
        self.assertEqual(look.axis_key("Y_Axis"), "Y")
        self.assertEqual(look.axis_key("construction"), "")
        self.assertEqual(look.plane_key_of_normal((0, -1, 0)), "XZ")
        self.assertEqual(look.plane_key_of_normal((0.1, 0.2, -0.9)), "XY")
        self.assertEqual(look.plane_key_of_normal((1, 0, 0)), "YZ")

    def test_hover_is_brighter_and_less_see_through(self):
        idle = look.look("XY_Plane", False)
        lit = look.look("XY_Plane", True)
        self.assertGreater(sum(lit[0]), sum(idle[0]))
        self.assertLess(lit[1], idle[1])
        self.assertGreater(lit[3], idle[3])


class Size(unittest.TestCase):
    def test_smaller_than_the_part(self):
        self.assertAlmostEqual(look.square_size(100.0), 60.0)

    def test_minimum_and_empty(self):
        self.assertEqual(look.square_size(5.0), look.MIN_SIZE)
        self.assertEqual(look.square_size(0.0, empty=True), look.EMPTY_SIZE)


class SizeForBox(unittest.TestCase):
    def test_part_beside_the_origin(self):
        # a part in the + octant leaves 3/4 of each square free: 0.6 x the part
        self.assertEqual(
            look.square_sizes_for((0, 100, 0, 60, 0, 20)), {"XY": 60.0, "XZ": 60.0, "YZ": 60.0}
        )
        self.assertEqual(look.square_size_for((0, 20, 0, 20, 0, 20)), look.MIN_SIZE)

    def test_part_centred_on_the_origin(self):
        # a 40 x 30 x 10 box centred in x and y: XY sticks out of the nearer sides (y = +-15)
        # by 15 % of the part (6): half 21; XZ and YZ stand 6 above its top (half 16)
        sizes = look.square_sizes_for((-20, 20, -15, 15, 0, 10))
        self.assertAlmostEqual(sizes["XY"], 42.0)
        self.assertAlmostEqual(sizes["XZ"], 32.0)
        self.assertAlmostEqual(sizes["YZ"], 32.0)

    def test_thin_plate_centred(self):
        # 30 x 20 x 5: sides at 10, margin 5 (at least 5 mm); 5 above its top
        sizes = look.square_sizes_for((-15, 15, -10, 10, 0, 5))
        self.assertAlmostEqual(sizes["XY"], 30.0)
        self.assertAlmostEqual(sizes["XZ"], 20.0)

    def test_part_on_one_side_of_a_plane(self):
        # centred in x, all at y > 0: XZ is seen from the front, it stays 0.6 x
        sizes = look.square_sizes_for((-20, 20, 0, 30, 0, 10))
        self.assertAlmostEqual(sizes["XZ"], 24.0)


class AxisLabel(unittest.TestCase):
    def test_on_the_plus_half_near_the_middle(self):
        spot = look.axis_label_spot((-100, 0, 0), (100, 0, 0))
        self.assertAlmostEqual(spot[0], 40.0)
        self.assertEqual(spot[1:], (0.0, 0.0))


class LabelCorner(unittest.TestCase):
    CORNERS = [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)]

    def test_default_corner(self):
        self.assertEqual(look.label_corner(self.CORNERS), 2)

    def test_away_from_the_part(self):
        # a part in the +x +y quadrant: the label goes to the -x -y corner
        self.assertEqual(look.label_corner(self.CORNERS, (5, 5, 3)), 0)
        self.assertEqual(look.label_corner(self.CORNERS, (-5, 5, 3)), 1)


if __name__ == "__main__":
    unittest.main()
