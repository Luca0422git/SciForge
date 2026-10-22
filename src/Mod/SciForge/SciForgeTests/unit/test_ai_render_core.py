# SPDX-License-Identifier: LGPL-2.1-or-later
"""The software renderer of the AI tool render (sciforge/ai/render_core.py): the standard
views, a box drawn with its faces shaded and edges, hidden edges left out, the highlight
colour, the PNG it writes, and the answers it refuses."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    import numpy  # noqa: F401
except ImportError:  # (FreeCAD and the CI's Python have numpy)
    numpy = None

from sciforge.ai import render_core as rc  # noqa: E402

# a 60 x 40 x 10 box, its 12 triangles and 12 edges
P = [(0, 0, 0), (60, 0, 0), (60, 40, 0), (0, 40, 0), (0, 0, 10), (60, 0, 10), (60, 40, 10), (0, 40, 10)]
T = [
    (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
    (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
]  # fmt: skip
E = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]


def box(color=rc.BODY_COLORS[0]):
    return [{"points": P, "triangles": T, "color": color}]


def edges():
    return [{"points": [P[a], P[b]]} for a, b in E]


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def near(pixel, color, tol=60):
    return sum(abs(int(p) - int(c)) for p, c in zip(pixel, color)) <= tol


class Camera(unittest.TestCase):
    def test_standard_views(self):
        right, up, forward = rc.camera("front")
        self.assertTrue(close(right, (1, 0, 0)) and close(up, (0, 0, 1)))
        self.assertTrue(close(forward, (0, 1, 0)))
        right, up, forward = rc.camera("top")
        self.assertTrue(close(right, (1, 0, 0)) and close(up, (0, 1, 0)))
        right, up, _f = rc.camera("right")
        self.assertTrue(close(right, (0, 1, 0)) and close(up, (0, 0, 1)))
        right, up, _f = rc.camera("bottom")
        self.assertTrue(close(right, (1, 0, 0)), right)
        right, up, forward = rc.camera("iso")  # Fusion's Home: from front, right and top
        self.assertLess(forward[0], 0)
        self.assertGreater(forward[1], 0)
        self.assertLess(forward[2], 0)
        self.assertGreater(up[2], 0)

    def test_any_direction_and_straight_down(self):
        right, up, forward = rc.camera(direction=(0, 0, 5))
        self.assertTrue(close(forward, (0, 0, -1)))
        self.assertAlmostEqual(sum(a * b for a, b in zip(right, up)), 0.0)

    def test_refused(self):
        with self.assertRaises(rc.RenderError):
            rc.camera("sideways")
        with self.assertRaises(rc.RenderError):
            rc.camera(direction=(0, 0, 0))


@unittest.skipIf(numpy is None, "numpy is not installed")
class Drawing(unittest.TestCase):
    def test_png_of_the_requested_size(self):
        png, info = rc.render(box(), edges(), 200, 150, "iso")
        self.assertEqual(rc.png_info(png), (200, 150))
        self.assertEqual((info["width"], info["height"], info["view"]), (200, 150, "iso"))
        self.assertGreater(info["triangles"], 0)
        self.assertGreater(info["mm_per_pixel"], 0)

    def test_top_view_fills_the_picture_with_the_box(self):
        png, info = rc.render(box(), [], 160, 120, "top", triad=False)
        rows = rc.png_pixels(png)
        self.assertEqual(len(rows), 120)
        centre = rows[60][80]
        corner = rows[1][1]
        self.assertTrue(near(corner, rc.BACKGROUND_TOP, 12), corner)
        self.assertFalse(near(centre, rc.BACKGROUND_TOP, 30), centre)
        # 60 mm wide in 160 px with a margin: about 0.43 mm per pixel
        self.assertAlmostEqual(info["mm_per_pixel"], 60.0 / (160 * (1 - 2 * rc.MARGIN)), 3)
        # the box covers the middle row from margin to margin, not beyond
        row = rows[60]
        inside = [x for x, p in enumerate(row) if not near(p, row[0], 25)]
        self.assertLessEqual(abs(min(inside) - 160 * rc.MARGIN), 2)
        self.assertLessEqual(abs(max(inside) - 160 * (1 - rc.MARGIN)), 2)

    def test_highlight_colour_shows(self):
        png, _info = rc.render(box(rc.HIGHLIGHT), [], 120, 90, "top", triad=False)
        centre = rc.png_pixels(png)[45][60]
        # flat shading darkens it a little, but it stays orange (red > green > blue)
        self.assertGreater(centre[0], centre[1])
        self.assertGreater(centre[1], centre[2])

    def test_hidden_edges_left_out(self):
        under = [{"points": [(10, 20, 0), (50, 20, 0)], "color": (255, 0, 0), "width": 3}]
        png, _ = rc.render(box(), under, 160, 120, "top", triad=False)
        reds = [p for row in rc.png_pixels(png) for p in row if p[0] > 200 and p[1] < 80]
        self.assertEqual(reds, [])  # the bottom edge is behind the top face
        under[0]["on_top"] = True
        png, _ = rc.render(box(), under, 160, 120, "top", triad=False)
        reds = [p for row in rc.png_pixels(png) for p in row if p[0] > 200 and p[1] < 80]
        self.assertTrue(reds)
        on_top = [{"points": [(10, 20, 10), (50, 20, 10)], "color": (255, 0, 0), "width": 3}]
        png, _ = rc.render(box(), on_top, 160, 120, "top", triad=False)
        reds = [p for row in rc.png_pixels(png) for p in row if p[0] > 200 and p[1] < 80]
        self.assertTrue(reds)  # an edge on the visible face is drawn

    def test_nearer_face_wins(self):
        far = {"points": [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)],
               "triangles": [(0, 1, 2), (0, 2, 3)], "color": (0, 0, 255)}  # fmt: skip
        near_face = dict(far, points=[(x, y, 5) for x, y, _z in far["points"]], color=(0, 255, 0))
        for order in ([far, near_face], [near_face, far]):
            png, _ = rc.render(order, [], 64, 64, "top", triad=False)
            centre = rc.png_pixels(png)[32][32]
            self.assertGreater(centre[1], centre[2], order)

    def test_many_small_and_big_triangles(self):
        import math

        points, tris = [(0.0, 0.0, 0.0)], []
        for i in range(400):  # a fan: thin long triangles and a disc of tiny ones
            a = 2 * math.pi * i / 400
            points.append((50 * math.cos(a), 50 * math.sin(a), 0.0))
        for i in range(400):
            tris.append((0, 1 + i, 1 + (i + 1) % 400))
        png, info = rc.render([{"points": points, "triangles": tris}], [], 300, 300, "top")
        self.assertEqual(rc.png_info(png), (300, 300))
        self.assertGreater(info["triangles"], 390)
        rows = rc.png_pixels(png)
        self.assertFalse(near(rows[150][150], rc.BACKGROUND_TOP, 30))
        self.assertFalse(near(rows[150][40], rc.BACKGROUND_TOP, 30))  # (no gaps in the fan)

    def test_refused(self):
        with self.assertRaises(rc.RenderError):
            rc.render(box(), [], 8, 8)
        with self.assertRaises(rc.RenderError):
            rc.render([{"points": P, "triangles": [(0, 1, 99)]}], [], 64, 64)

    def test_empty_scene_is_only_background(self):
        png, info = rc.render([], [], 32, 32, triad=False)
        self.assertEqual(rc.png_info(png), (32, 32))
        self.assertIsNone(info["mm_per_pixel"])


class Png(unittest.TestCase):
    def test_not_a_png(self):
        self.assertIsNone(rc.png_info(b"GIF89a" + b"\0" * 30))
        self.assertIsNone(rc.png_info(None))
        self.assertIsNone(rc.png_pixels(b"nope"))


if __name__ == "__main__":
    unittest.main()
