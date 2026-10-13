# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the value box next to a drag arrow goes (sciforge/arrow_box_core.py): beside the
arrow, never over its heads, inside the view. Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import arrow_box_core as core  # noqa: E402

VIEW = (1500, 800)
BOX = (77, 21)


def rect(corner, box=BOX):
    return (corner[0], corner[1], box[0], box[1])


def inside(corner, box=BOX, view=VIEW):
    return (
        corner[0] >= 0
        and corner[1] >= 0
        and corner[0] + box[0] <= view[0]
        and corner[1] + box[1] <= view[1]
    )


class Spot(unittest.TestCase):
    def check_clear(self, anchor, tail, tip, radius, view=VIEW):
        corner = core.spot(anchor, tail, tip, radius, BOX, view)
        clear = core.clearance(tail, tip, rect(corner))
        self.assertGreaterEqual(clear, radius, (corner, clear))
        self.assertTrue(inside(corner, view=view), corner)
        return corner

    def test_upright_arrow_box_on_its_right(self):
        # An arrow pointing up the screen (a top face in the iso view).
        corner = self.check_clear((700, 400), (700, 460), (700, 340), 10)
        self.assertGreater(corner[0], 700)  # right of the arrow
        self.assertLess(abs(corner[1] + BOX[1] / 2.0 - 400), 2)  # level with its middle

    def test_level_arrow_box_above_not_over_the_head(self):
        # The case found in review: Front view, a side face's arrow points right. The old
        # box sat right of the middle, over the + head.
        corner = self.check_clear((1006, 391), (921, 391), (1091, 391), 14)
        self.assertLess(corner[1] + BOX[1], 391)  # above the arrow
        for x in (1034, 1046, 1057, 1063, 1080):  # the + head's pixels
            self.assertGreater(core._rect_point(rect(corner), (x, 391)), 0.0, x)

    def test_slanted_arrow(self):
        self.check_clear((600, 400), (560, 440), (640, 360), 12)
        self.check_clear((600, 400), (640, 440), (560, 360), 12)

    def test_arrow_pointing_at_the_viewer(self):
        # Seen end on, the arrow is a disc around its middle: the box goes right of it.
        corner = self.check_clear((700, 400), (700, 400), (700, 400), 15)
        self.assertGreaterEqual(corner[0], 700 + 15)

    def test_other_side_at_the_right_edge(self):
        # An upright arrow at the right edge of the view: the box goes to its left.
        corner = self.check_clear((1480, 400), (1480, 460), (1480, 340), 10)
        self.assertLess(corner[0] + BOX[0], 1480)

    def test_level_arrow_at_the_top_edge(self):
        corner = self.check_clear((700, 8), (620, 8), (780, 8), 10)
        self.assertGreater(corner[1], 8)  # below it, as above there is no room

    def test_past_the_tip_when_the_sides_are_full(self):
        # A level arrow in a view barely taller than the box: past its tip.
        view = (1500, 30)
        corner = self.check_clear((700, 15), (620, 15), (780, 15), 6, view=view)
        self.assertGreater(corner[0], 780)

    def test_clearance(self):
        self.assertEqual(core.clearance((0, 0), (100, 0), (40, -5, 10, 10)), 0.0)  # crosses
        self.assertEqual(core.clearance((0, 0), (100, 100), (40, 40, 10, 10)), 0.0)  # inside
        self.assertAlmostEqual(core.clearance((0, 0), (100, 0), (40, 7, 10, 10)), 7.0)
        self.assertAlmostEqual(core.clearance((0, 0), (10, 0), (13, 4, 5, 5)), 5.0)


if __name__ == "__main__":
    unittest.main()
