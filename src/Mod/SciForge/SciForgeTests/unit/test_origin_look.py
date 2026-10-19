# SPDX-License-Identifier: LGPL-2.1-or-later
"""How the origin planes and axes look (sciforge/origin_look.py): one colour per axis, a
plane in the colour of the axis it faces, small squares, labels away from the part. Runs
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


class SquareCorner(unittest.TestCase):
    """Fusion's layout: each square in the + quarter of its plane, a little off the axes,
    moved beside a part that would hide it."""

    def test_empty_design_plus_quarter_with_a_gap(self):
        for key in ("XY", "XZ_Plane", "YZ"):
            self.assertEqual(look.square_corner(key, 20.0), (2.0, 2.0))

    def test_part_away_from_the_square_leaves_it(self):
        # all at negative x and y: nothing of it in any + quarter
        box = (-50, -10, -40, -5, -30, -1)
        for key in ("XY", "XZ", "YZ"):
            self.assertEqual(look.square_corner(key, 20.0, box), (2.0, 2.0))

    def test_part_centred_on_the_origin_moves_it_beside(self):
        # a 40 x 30 x 10 box centred in x and y, on XY: each square goes past the part
        # along u by a quarter of its side
        box = (-20, 20, -15, 15, 0, 10)
        self.assertEqual(look.square_corner("XY", 20.0, box), (25.0, 2.0))  # past x = 20
        self.assertEqual(look.square_corner("XZ", 20.0, box), (25.0, 2.0))  # past x = 20
        self.assertEqual(look.square_corner("YZ", 20.0, box), (20.0, 2.0))  # past y = 15

    def test_moved_to_the_side_facing_the_viewer(self):
        # seen from -y (the usual front view), YZ goes in front of the part, not behind it
        box = (-30, 30, -20, 20, 0, 20)
        self.assertEqual(look.square_corner("YZ", 20.0, box, viewer_u=-1.0), (-45.0, 2.0))
        self.assertEqual(look.square_corner("YZ", 20.0, box, viewer_u=1.0), (25.0, 2.0))

    def test_part_above_the_plane_keeps_the_square_first(self):
        # a wall z 20..30 over the XY quarter does not meet XY: the usual place comes
        # first (the picker checks the screen), the places round it after
        box = (-50, 50, -1, 1, 20, 30)
        self.assertEqual(look.square_corner("XY", 20.0, box), (2.0, 2.0))
        self.assertGreater(len(look.square_corners("XY", 20.0, box)), 1)

    def test_part_below_the_plane_keeps_the_vertical_squares(self):
        # all under z = 0: XZ and YZ (their + quarters are above z = 0) stay put
        box = (-20, 20, -15, 15, -10, -1)
        self.assertEqual(look.square_corner("XZ", 20.0, box), (2.0, 2.0))
        # nor does it meet XY (all under z = 0): the usual place first, the screen decides
        self.assertEqual(look.square_corner("XY", 20.0, box), (2.0, 2.0))

    def test_part_size_for_the_pick_tolerances(self):
        self.assertAlmostEqual(look.part_size((0, 100, 0, 60, 0, 20)), 60.0)
        self.assertEqual(look.part_size(None), look.EMPTY_SIZE)


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
