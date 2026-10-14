# SPDX-License-Identifier: LGPL-2.1-or-later
"""The navigation bar's choices and maths (sciforge/nav_core.py)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sciforge import nav_core as n  # noqa: E402


class StyleTest(unittest.TestCase):
    def test_six_styles(self):
        self.assertEqual(len(n.VISUAL_STYLES), 6)
        self.assertEqual(n.style("Shaded"), ("Shaded", False, False))
        self.assertEqual(n.style("Shaded with Hidden Edges"), ("Flat Lines", True, False))
        self.assertEqual(n.style("Shaded with Visible Edges Only"), ("As Is", False, False))
        self.assertEqual(n.style("Wireframe"), ("Wireframe", False, False))
        self.assertEqual(n.style("Wireframe with Hidden Edges"), ("Flat Lines", True, True))
        self.assertEqual(n.style("Wireframe with Visible Edges Only"), ("Flat Lines", False, True))
        self.assertEqual(n.style("nonsense"), n.style(n.DEFAULT_STYLE))

    def test_environments(self):
        self.assertEqual(n.ENVIRONMENT_NAMES[0], "Theme")
        self.assertEqual(n.environment("nope"), n.ENVIRONMENTS[0][1])
        self.assertEqual(n.rgb("#ff8000"), (1.0, 128 / 255.0, 0.0))
        self.assertEqual(n.background_of("Theme"), n.rgb("#2a2a2a"))
        mid = n.background_of("Photo Booth")
        top, bottom = n.environment("Photo Booth")
        self.assertAlmostEqual(mid[0], (n.rgb(top)[0] + n.rgb(bottom)[0]) / 2)
        for _name, (top, bottom) in n.ENVIRONMENTS:
            self.assertEqual(len(n.rgb(top)), 3)
            self.assertEqual(len(n.rgb(bottom)), 3)


class CameraTest(unittest.TestCase):
    def test_ortho_faces(self):
        self.assertTrue(n.wants_ortho((0, 0, -1)))
        self.assertTrue(n.wants_ortho((0, 3, 0)))
        self.assertFalse(n.wants_ortho((1, 1, -1)))
        a = math.radians(0.3)
        self.assertTrue(n.wants_ortho((math.sin(a), 0, -math.cos(a))))
        a = math.radians(2)
        self.assertFalse(n.wants_ortho((math.sin(a), 0, -math.cos(a))))
        self.assertFalse(n.wants_ortho((0, 0, 0)))


class PanZoomTest(unittest.TestCase):
    def test_pan(self):
        # 100 mm shown over 500 pixels: a 50 pixel drag right moves the camera 10 mm left
        self.assertEqual(n.pan_shift(50, 0, 500, 100), (-10.0, 0.0))
        self.assertEqual(n.pan_shift(0, 25, 500, 100), (0.0, 5.0))  # drag down: camera up
        self.assertEqual(n.pan_shift(5, 5, 0, 100), (0.0, 0.0))

    def test_zoom(self):
        self.assertEqual(n.zoom_factor(0), 1.0)
        self.assertEqual(n.zoom_factor(-160), 0.5)  # up: in
        self.assertEqual(n.zoom_factor(160), 2.0)

    def test_zoom_window(self):
        self.assertIsNone(n.zoom_window(10, 10, 12, 30, 800, 600))  # a click
        cx, cy, f = n.zoom_window(0, 0, 400, 300, 800, 600)  # the top-left quarter
        self.assertEqual((cx, cy, f), (-0.25, 0.25, 0.5))
        cx, cy, f = n.zoom_window(400, 300, 300, 200, 800, 600)  # drawn backwards
        self.assertAlmostEqual(f, 1.0 / 6.0)
        self.assertAlmostEqual(cx, 350 / 800.0 - 0.5)
        # a wide thin box: the width decides
        self.assertEqual(n.zoom_window(0, 0, 800, 10, 800, 600)[2], 1.0)


class ViewportTest(unittest.TestCase):
    def test_layouts(self):
        self.assertEqual(n.cells("Single View", 800, 600), [(0, 0, 800, 600)])
        two = n.cells("Two Views Horizontal", 800, 600, gap=2)
        self.assertEqual(two, [(0, 0, 399, 600), (401, 0, 399, 600)])
        two = n.cells("Two Views Vertical", 800, 600, gap=2)
        self.assertEqual(two, [(0, 0, 800, 299), (0, 301, 800, 299)])
        four = n.cells("Multiple Views", 800, 600, gap=2)
        self.assertEqual(len(four), 4)
        self.assertEqual(four[0], (0, 0, 399, 299))
        self.assertEqual(four[3], (401, 301, 399, 299))
        self.assertEqual(n.views_of("Multiple Views"), ["top", "front", "right", "home"])
        for layout in n.LAYOUT_NAMES:
            self.assertEqual(len(n.cells(layout, 300, 200)), len(n.views_of(layout)))


class GridTest(unittest.TestCase):
    def test_step(self):
        self.assertEqual(n.grid_step(120), 10.0)
        self.assertEqual(n.grid_step(100), 10.0)
        self.assertEqual(n.grid_step(30), 5.0)
        self.assertEqual(n.grid_step(20), 2.0)
        self.assertEqual(n.grid_step(1300), 200.0)
        self.assertEqual(n.grid_step(0), 10.0)

    def test_lines(self):
        majors, minors = n.grid_lines((0, 0), 10, 10, 5)
        self.assertEqual(len(majors), 6)  # x = -10, 0, 10 and y = -10, 0, 10
        self.assertEqual(len(minors), 16)  # 4 between each pair, both ways
        self.assertIn((0.0, -10.0, 0.0, 10.0), majors)
        majors, minors = n.grid_lines((0, 0), 10, 10, 1)
        self.assertEqual(minors, [])
        self.assertEqual(n.grid_lines((0, 0), 10, 0, 5), ([], []))
        self.assertEqual(n.grid_lines((0, 0), 1e6, 0.001, 5), ([], []))  # too many: none


class IncrementTest(unittest.TestCase):
    def test_snap(self):
        self.assertEqual(n.snap(12.4, 1.0), 12.0)
        self.assertEqual(n.snap(12.6, 1.0), 13.0)
        self.assertEqual(n.snap(-7.4, 5.0), -5.0)
        self.assertEqual(n.snap(22.0, 15.0), 15.0)
        self.assertEqual(n.snap(23.0, 15.0), 30.0)
        self.assertEqual(n.snap(3.3, 0), 3.3)
        self.assertEqual(n.snap(3.3, None), 3.3)

    def test_ground(self):
        self.assertEqual(n.ground_level(5.0, 40.0, 0), 5.0)
        self.assertEqual(n.ground_level(5.0, 40.0, 25), -5.0)
        self.assertEqual(n.ground_level(5.0, 40.0, -10), 5.0)


if __name__ == "__main__":
    unittest.main()
