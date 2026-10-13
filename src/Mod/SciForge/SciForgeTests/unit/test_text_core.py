# SPDX-License-Identifier: LGPL-2.1-or-later
"""sciforge/text_core.py: the Text box (Fusion's quoted text + parameters), letter
positions (kerning, Character Spacing, alignment in the frame, lines), the frame (flips,
angle, snap points, turning about a point) and text on a path. Runs without FreeCAD."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import text_core as core  # noqa: E402


class FakeFont:
    """A font with round numbers: em 1000, every letter 500 wide, 'AV' kerned by -100."""

    units_per_em = 1000
    ascender = 800
    descender = -200
    line_gap = 100
    underline_position = -100
    underline_thickness = 50

    @property
    def line_height(self):
        return self.ascender - self.descender + self.line_gap

    def advance(self, char):
        return 250 if char == " " else 500

    def kerning(self, left, right):
        return -100 if (left, right) == ("A", "V") else 0


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


class TextBoxTests(unittest.TestCase):
    def lookup(self, name):
        values = {"version": 3.0, "name": "Luca", "ratio": 2.5}
        if name not in values:
            raise KeyError(name)
        return values[name]

    def test_plain_text_is_taken_as_typed(self):
        self.assertEqual(core.evaluate("Hello World", self.lookup), "Hello World")
        self.assertEqual(core.evaluate("two\nlines", self.lookup), "two\nlines")

    def test_quoted_text_and_parameters(self):
        self.assertEqual(core.evaluate("'Hello'", self.lookup), "Hello")
        self.assertEqual(core.evaluate("'Rev ' + version", self.lookup), "Rev 3")
        self.assertEqual(core.evaluate("name + ' ' + ratio", self.lookup), "Luca 2.5")
        self.assertEqual(core.evaluate("'v' + 2", self.lookup), "v2")

    def test_escaped_quote(self):
        self.assertEqual(core.evaluate("'Wendy\\'s'", self.lookup), "Wendy's")
        self.assertEqual(core.literal("Wendy's"), "'Wendy\\'s'")
        self.assertEqual(core.evaluate(core.literal("a\\b'c"), self.lookup), "a\\b'c")

    def test_a_bare_parameter_name(self):
        self.assertEqual(core.evaluate("version", self.lookup), "3")
        self.assertEqual(core.evaluate("unknown words", self.lookup), "unknown words")

    def test_mistakes_are_explained(self):
        with self.assertRaises(core.TextError):
            core.evaluate("'open", self.lookup)
        with self.assertRaises(core.TextError):
            core.evaluate("'a' + nothing", self.lookup)
        with self.assertRaises(core.TextError):
            core.evaluate("'a' +", self.lookup)
        with self.assertRaises(core.TextError):
            core.evaluate("'a' 'b'", self.lookup)

    def test_checks(self):
        with self.assertRaises(core.TextError):
            core.check_text("   ")
        with self.assertRaises(core.TextError):
            core.check_text("")
        core.check_text("A")
        with self.assertRaises(core.TextError):
            core.check_height(0.0)
        core.check_height(5.0)
        with self.assertRaises(core.TextError):
            core.check_spacing(-80.0)
        core.check_spacing(25.0)

    def test_value_formatting(self):
        self.assertEqual(core.format_value(3.0), "3")
        self.assertEqual(core.format_value(2.25), "2.25")
        self.assertEqual(core.format_value("x"), "x")


class LineTests(unittest.TestCase):
    def test_pens_with_kerning(self):
        pens, width = core.line_pens("AVA", FakeFont())
        self.assertEqual([p for _c, p in pens], [0.0, 400.0, 900.0])
        self.assertEqual(width, 1400.0)

    def test_character_spacing_widens_advances(self):
        pens, width = core.line_pens("AB", FakeFont(), spacing=50.0)
        self.assertEqual([p for _c, p in pens], [0.0, 750.0])
        self.assertEqual(width, 1250.0)  # no spacing after the last letter

    def test_bold_extra(self):
        _pens, width = core.line_pens("AB", FakeFont(), bold_extra=10.0)
        self.assertEqual(width, 1020.0)


class BlockTests(unittest.TestCase):
    def test_left_top_single_line(self):
        glyphs, lines = core.block(
            "AB", FakeFont(), 10.0, h_align="left", v_align="top", width=50.0, frame_height=20.0
        )
        self.assertEqual(len(glyphs), 2)
        self.assertTrue(close(glyphs[0].x, 0.0))
        self.assertTrue(close(glyphs[1].x, 5.0))
        self.assertTrue(close(glyphs[0].y, 20.0 - 8.0))  # top minus the ascender
        self.assertEqual(len(lines), 1)
        self.assertTrue(close(lines[0][1], 10.0))

    def test_center_right_bottom_middle(self):
        font = FakeFont()
        glyphs, _ = core.block("AB", font, 10.0, 0.0, "center", "bottom", 50.0, 20.0)
        self.assertTrue(close(glyphs[0].x, 20.0))
        self.assertTrue(close(glyphs[0].y, 2.0))  # baseline at the descender
        glyphs, _ = core.block("AB", font, 10.0, 0.0, "right", "middle", 50.0, 20.0)
        self.assertTrue(close(glyphs[0].x, 40.0))
        self.assertTrue(close(glyphs[0].y, 7.0))  # block 10 tall centred in 20: 15 - 8

    def test_lines_are_spaced_by_the_line_height(self):
        glyphs, lines = core.block("A\nBB", FakeFont(), 10.0, 0.0, "center", "top", 40.0, 30.0)
        self.assertEqual([g.line for g in glyphs], [0, 1, 1])
        self.assertTrue(close(lines[0][2] - lines[1][2], 11.0))
        self.assertTrue(close(glyphs[0].x, 17.5))
        self.assertTrue(close(glyphs[1].x, 15.0))

    def test_unknown_alignment(self):
        with self.assertRaises(core.TextError):
            core.block("A", FakeFont(), 10.0, 0.0, "middle", "top")

    def test_extent_and_underline(self):
        width, height = core.text_extent("AB\nA", FakeFont(), 10.0)
        self.assertTrue(close(width, 10.0))
        self.assertTrue(close(height, 10.0 + 11.0))
        x0, y0, x1, y1 = core.underline_box(FakeFont(), 10.0, 0.0, 10.0, 0.0)
        self.assertEqual((x0, x1), (0.0, 10.0))
        self.assertTrue(close(y1, -1.0))
        self.assertTrue(close(y0, -1.5))


class AffineTests(unittest.TestCase):
    def test_compose_and_inverse(self):
        t = core.chain(core.scaling(2.0), core.rotation(math.radians(90)), core.translation(1, 2))
        x, y = core.apply(t, 1.0, 0.0)
        self.assertTrue(close(x, 1.0) and close(y, 4.0))
        back = core.apply(core.inverse(t), x, y)
        self.assertTrue(close(back[0], 1.0) and close(back[1], 0.0))

    def test_rotation_about_a_point(self):
        x, y = core.apply(core.rotation(math.pi, about=(1.0, 1.0)), 2.0, 1.0)
        self.assertTrue(close(x, 0.0) and close(y, 1.0))

    def test_shear(self):
        self.assertEqual(core.apply(core.shear_x(0.5), 1.0, 2.0), (2.0, 2.0))


class FrameTests(unittest.TestCase):
    def test_from_two_clicks(self):
        corner, w, h = core.frame_from_points((10, 5), (2, 9))
        self.assertEqual(corner, (2.0, 5.0))
        self.assertEqual((w, h), (8.0, 4.0))

    def test_corners_and_back(self):
        corners = core.frame_corners((1.0, 2.0), 30.0, 10.0, 4.0)
        corner, angle, w, h = core.frame_from_corners(*corners)
        self.assertTrue(close(corner[0], 1.0) and close(corner[1], 2.0))
        self.assertTrue(close(angle, 30.0, 1e-9))
        self.assertTrue(close(w, 10.0) and close(h, 4.0))

    def test_flips_mirror_inside_the_frame(self):
        t = core.frame_transform((0, 0), 0.0, 10.0, 4.0, flip_h=True)
        self.assertEqual(core.apply(t, 1.0, 1.0), (9.0, 1.0))
        t = core.frame_transform((0, 0), 0.0, 10.0, 4.0, flip_v=True)
        self.assertEqual(core.apply(t, 1.0, 1.0), (1.0, 3.0))
        t = core.frame_transform((0, 0), 0.0, 10.0, 4.0, True, True)
        self.assertEqual(core.apply(t, 1.0, 1.0), (9.0, 3.0))

    def test_snap_points(self):
        points = core.snap_points((0, 0), 90.0, 10.0, 4.0)
        self.assertEqual(set(points), set(core.SNAP_NAMES))
        x, y = points["bottom_right"]
        self.assertTrue(close(x, 0.0) and close(y, 10.0))
        x, y = points["center"]
        self.assertTrue(close(x, -2.0) and close(y, 5.0))

    def test_turning_keeps_the_pivot(self):
        corner = core.turned_corner((0, 0), 0.0, 10.0, 4.0, "center", 90.0)
        before = core.snap_points((0, 0), 0.0, 10.0, 4.0)["center"]
        after = core.snap_points(corner, 90.0, 10.0, 4.0)["center"]
        self.assertTrue(close(before[0], after[0]) and close(before[1], after[1]))
        corner = core.turned_corner((0, 0), 0.0, 10.0, 4.0, "bottom_left", 45.0)
        self.assertTrue(close(corner[0], 0.0) and close(corner[1], 0.0))

    def test_angles(self):
        self.assertTrue(close(core.angle_about((0, 0), (1, 0), (0, 1)), 90.0))
        self.assertTrue(close(core.angle_about((0, 0), (1, 0), (-1, -0.0001)), -179.9942704, 1e-6))
        self.assertEqual(core.normal_angle(270.0), -90.0)
        self.assertEqual(core.normal_angle(-180.0), 180.0)


class PathTests(unittest.TestCase):
    def glyphs(self):
        return [core.Glyph(c, 5.0 * i, 0.0, 5.0, 0) for i, c in enumerate("ABC")]

    def test_alignment_along_the_path(self):
        left = core.path_slots(self.glyphs(), 15.0, 100.0, "left")
        self.assertEqual([d for _g, d in left], [2.5, 7.5, 12.5])
        center = core.path_slots(self.glyphs(), 15.0, 100.0, "center")
        self.assertEqual([d for _g, d in center], [45.0, 50.0, 55.0])
        right = core.path_slots(self.glyphs(), 15.0, 100.0, "right")
        self.assertEqual([d for _g, d in right], [87.5, 92.5, 97.5])

    def test_fit_spreads_letters_over_the_path(self):
        fit = core.path_slots(self.glyphs(), 15.0, 100.0, fit=True)
        self.assertEqual([d for _g, d in fit], [2.5, 50.0, 97.5])
        single = core.path_slots(self.glyphs()[:1], 5.0, 100.0, fit=True)
        self.assertEqual(single[0][1], 50.0)

    def test_fit_round_a_closed_path_leaves_even_gaps(self):
        # three letters 5 wide round a 90 mm circle: a slot of 30 mm each, the gap
        # between the last and the first as wide as the others
        fit = core.path_slots(self.glyphs(), 15.0, 90.0, fit=True, closed=True)
        spots = [d for _g, d in fit]
        for got, want in zip(spots, [15.0, 45.0, 75.0]):
            self.assertAlmostEqual(got, want)
        self.assertAlmostEqual(spots[0] + 90.0 - spots[-1], spots[1] - spots[0])

    def test_glyph_on_the_path(self):
        g = core.Glyph("A", 0.0, 0.0, 4.0, 0)
        # path going up (+y): the letter's baseline runs up, its top points to -x
        t = core.path_glyph_transform((10.0, 0.0), (0.0, 1.0), g, 0.0)
        x, y = core.apply(t, 2.0, 0.0)  # the letter's middle on the baseline
        self.assertTrue(close(x, 10.0) and close(y, 0.0))
        x, y = core.apply(t, 2.0, 1.0)  # one up in the letter: left of the path
        self.assertTrue(close(x, 9.0) and close(y, 0.0))
        # Below: the baseline sits under the path
        t = core.path_glyph_transform((0.0, 0.0), (1.0, 0.0), g, -3.0)
        self.assertEqual(core.apply(t, 2.0, 0.0), (0.0, -3.0))
        # Flip Vertical mirrors across the path
        t = core.path_glyph_transform((0.0, 0.0), (1.0, 0.0), g, -3.0, flip_v=True)
        x, y = core.apply(t, 2.0, 1.0)
        self.assertTrue(close(x, 0.0) and close(y, 2.0))

    def test_below_offset(self):
        self.assertTrue(close(core.below_offset(FakeFont(), 10.0), -8.0))


if __name__ == "__main__":
    unittest.main()
