# SPDX-License-Identifier: LGPL-2.1-or-later
"""How the drag handles look and how big they are (sciforge/handle_look_core.py): Fusion's
small blue arrow and white angle disc, one size on the screen. Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import handle_look_core as core  # noqa: E402


class Sizes(unittest.TestCase):
    def test_arrow_is_fusion_small(self):
        # Luca's picture of Fusion's Extrude: the arrow about 30-35 px, the disc 18-20 px
        self.assertTrue(30.0 <= core.ARROW_PX <= 35.0)
        self.assertTrue(18.0 <= 2 * core.DISC_RADIUS_PX <= 20.0)

    def test_short_shaft_wide_head(self):
        self.assertGreater(core.HEAD_RADIUS_PX, 3 * core.SHAFT_RADIUS_PX)
        self.assertGreater(2 * core.HEAD_RADIUS_PX, core.HEAD_PX)  # the head is wider than long
        shaft = core.ARROW_PX - core.HEAD_PX
        self.assertLess(shaft, 2 * core.HEAD_PX)  # a short shaft

    def test_one_size_on_the_screen(self):
        # the same pixels whatever millimetres one pixel covers (a tiny or a huge part, any zoom)
        for mm_per_px in (0.004, 0.08, 2.2, 150.0):
            self.assertAlmostEqual(core.length_mm(mm_per_px) / mm_per_px, core.ARROW_PX)
        self.assertGreater(core.length_mm(0.0), 0.0)  # never zero

    def test_grab_area_covers_the_drawing(self):
        for kind in ("arrow", "disc", "ball"):
            self.assertGreaterEqual(core.grab_px(kind), core.half_width_px(kind) + 2.0)
        self.assertEqual(core.grab_px("arrow", at_least=40.0), 40.0)
        self.assertTrue(core.on_arrow((5.0, core.HEAD_RADIUS_PX), (0.0, 0.0), (32.0, 0.0)))
        self.assertFalse(core.on_arrow((5.0, 30.0), (0.0, 0.0), (32.0, 0.0)))
        self.assertTrue(core.on_arrow((34.0, 0.0), (0.0, 0.0), (32.0, 0.0)))  # just past the tip

    def test_grab_area_follows_the_drawing(self):
        # A slim zone round the shaft, a wide one round the head, nothing behind the foot:
        # the foot stands on what is measured from (a profile, a pattern copy's dot), and a
        # click there must reach it (patterns_qa_edit, pi5_case).
        parts = core.grab_parts()
        centre, height, radius = parts["shaft"]
        self.assertAlmostEqual(centre - height / 2.0, 0.0)  # starts at the foot, not behind
        self.assertLess(radius, core.HEAD_RADIUS_PX + core.OUTLINE_PX)
        self.assertGreaterEqual(radius, core.SHAFT_RADIUS_PX + core.OUTLINE_PX + 2.0)
        head_centre, head_height, head_radius = parts["head"]
        self.assertAlmostEqual(head_centre - head_height / 2.0, core.ARROW_PX - core.HEAD_PX)
        self.assertGreater(head_centre + head_height / 2.0, core.ARROW_PX)  # past the tip
        self.assertEqual(head_radius, core.grab_px("arrow"))
        shaft = core.grab_parts(length=96.0, start=14.4)["shaft"]
        self.assertAlmostEqual(shaft[0] - shaft[1] / 2.0, 14.4)  # Move's arrows: off the centre
        foot, tip = (0.0, 0.0), (core.ARROW_PX, 0.0)
        self.assertFalse(core.on_arrow((-4.0, 0.0), foot, tip))  # behind the foot
        self.assertFalse(core.on_arrow((3.0, 10.0), foot, tip))  # beside the shaft
        self.assertTrue(core.on_arrow((28.0, 10.0), foot, tip))  # beside the head

    def test_aim_is_on_the_head(self):
        self.assertGreater(core.HEAD_AIM * core.ARROW_PX, core.ARROW_PX - core.HEAD_PX)
        self.assertLess(core.HEAD_AIM, 1.0)


class Geometry(unittest.TestCase):
    def test_arrow_parts_fill_foot_to_tip(self):
        parts = core.arrow_parts()
        centre, height, radius = parts["shaft"]
        self.assertAlmostEqual(centre - height / 2.0, 0.0)  # the foot
        head_centre, head_height, head_radius = parts["head"]
        self.assertAlmostEqual(head_centre + head_height / 2.0, core.ARROW_PX)  # the tip
        self.assertAlmostEqual(centre + height / 2.0, head_centre - head_height / 2.0)
        self.assertEqual(radius, core.SHAFT_RADIUS_PX)
        self.assertEqual(head_radius, core.HEAD_RADIUS_PX)

    def test_arrow_from_off_the_centre(self):
        parts = core.arrow_parts(length=96.0, start=14.4)
        centre, height, _ = parts["shaft"]
        self.assertAlmostEqual(centre - height / 2.0, 14.4)

    def test_outline_grows_all_round(self):
        grown = core.outline_parts(core.arrow_parts())
        for name, (centre, height, radius) in core.arrow_parts().items():
            self.assertEqual(grown[name][0], centre)
            self.assertAlmostEqual(grown[name][1], height + 2 * core.OUTLINE_PX)
            self.assertAlmostEqual(grown[name][2], radius + core.OUTLINE_PX)

    def test_arc_reaches_pixels_each_side(self):
        import math

        span = core.arc_span(50.0, 0.1)  # 30 px = 3 mm of arc at 50 mm
        self.assertAlmostEqual(math.radians(span) * 50.0, 3.0)
        self.assertEqual(core.arc_span(0.001, 10.0), 180.0)  # never more than a half turn

    def test_sign(self):
        self.assertEqual(core.sign(2.0), 1.0)
        self.assertEqual(core.sign(0.0), 1.0)
        self.assertEqual(core.sign(-0.5), -1.0)


class Colours(unittest.TestCase):
    def test_lighter_when_hot(self):
        hot = core.hot_colour(core.BLUE, True)
        self.assertTrue(all(h >= c for h, c in zip(hot, core.BLUE)))
        self.assertEqual(core.hot_colour(core.BLUE, False), core.BLUE)
        self.assertEqual(core.hot_colour(core.BLUE, True, core.BLUE_HOT), core.BLUE_HOT)
        self.assertTrue(all(h >= c for h, c in zip(core.BLUE_HOT, core.BLUE)))

    def test_blue_arrow_white_disc_dark_dot(self):
        r, g, b = core.BLUE
        self.assertGreater(b, r + 0.4)
        self.assertGreater(min(core.DISC), 0.9)
        self.assertLess(max(core.DOT), 0.3)
        self.assertGreater(min(core.OUTLINE), 0.9)

    def test_shading_never_dark(self):
        diffuse, emissive = core.shaded(core.BLUE)
        self.assertTrue(all(e > 0 for e in emissive))
        self.assertLessEqual(max(d + e for d, e in zip(diffuse, emissive)), 1.2)


if __name__ == "__main__":
    unittest.main()
