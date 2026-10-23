# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flange maths and rule-list helpers of sciforge/sheetmetal_core.py (sm-forming)."""

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sciforge import sheetmetal_core as core  # noqa: E402

T, R = 1.0, 1.0


class FlangeMathsTests(unittest.TestCase):
    def test_thickness_sides(self):
        self.assertEqual(core.thickness_offsets("side1", 2.0), (0.0, 2.0))
        self.assertEqual(core.thickness_offsets("side2", 2.0), (-2.0, 0.0))
        self.assertEqual(core.thickness_offsets("centered", 2.0), (-1.0, 1.0))

    def test_bend_positions_at_90(self):
        # research 4.4: the bend centre for Inside is at -(T + R), Outside -R, Adjacent 0
        self.assertAlmostEqual(core.bend_start_x("inside", 90, R, T), -2.0)
        self.assertAlmostEqual(core.bend_start_x("outside", 90, R, T), -1.0)
        self.assertAlmostEqual(core.bend_start_x("adjacent", 90, R, T), 0.0)
        self.assertAlmostEqual(core.bend_start_x("tangent", 90, R, T), -2.0)

    def test_tangent_differs_from_inside_above_90(self):
        inside = core.bend_start_x("inside", 135, R, T)
        tangent = core.bend_start_x("tangent", 135, R, T)
        self.assertAlmostEqual(inside, -2.0 * math.tan(math.radians(67.5)))
        self.assertAlmostEqual(tangent, -2.0)
        self.assertAlmostEqual(
            core.bend_start_x("tangent", 45, R, T), -2.0 * math.tan(math.radians(22.5))
        )

    def test_no_inside_position_at_180(self):
        with self.assertRaises(ValueError) as ctx:
            core.bend_start_x("inside", 180, R, T)
        self.assertIn("Adjacent or Tangent", str(ctx.exception))
        self.assertAlmostEqual(core.bend_start_x("tangent", 180, R, T), -2.0)
        self.assertAlmostEqual(core.bend_start_x("adjacent", 180, R, T), 0.0)

    def test_wall_length_per_datum(self):
        # research 4.3: tops at T + H (inner), H (outer), T + R + H (tangent) for 90 degrees
        self.assertAlmostEqual(core.wall_length(10, "inner", 90, R, T), 9.0)
        self.assertAlmostEqual(core.wall_length(10, "outer", 90, R, T), 8.0)
        self.assertAlmostEqual(core.wall_length(10, "tangent", 90, R, T), 10.0)
        self.assertAlmostEqual(
            core.wall_length(10, "inner", 45, R, T), 10 - math.tan(math.radians(22.5))
        )

    def test_wall_length_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            core.wall_length(5, "inner", 180, R, T)
        self.assertIn("Tangent To Bend", str(ctx.exception))
        self.assertAlmostEqual(core.wall_length(5, "tangent", 180, R, T), 5.0)
        with self.assertRaises(ValueError) as ctx:
            core.wall_length(1.5, "outer", 90, R, T)
        self.assertIn("more than 2.000", str(ctx.exception))

    def test_width_types(self):
        self.assertEqual(core.width_range("full", 30), (0.0, 30.0))
        self.assertEqual(core.width_range("symmetric", 30, width=10), (10.0, 20.0))
        self.assertEqual(core.width_range("two_sides", 30, distance1=5, distance2=8), (10.0, 23.0))
        self.assertEqual(core.width_range("two_offsets", 30, distance1=2, distance2=3), (2.0, 27.0))
        with self.assertRaises(ValueError):
            core.width_range("two_offsets", 30, distance1=20, distance2=20)

    def test_contour_corner_radius_keeps_the_inside_radius(self):
        s0, s1 = core.thickness_offsets("side1", T)
        self.assertEqual(core.path_radius(True, s0, s1, R), 2.0)  # line on the outside
        self.assertEqual(core.path_radius(False, s0, s1, R), 1.0)  # line on the inside
        s0, s1 = core.thickness_offsets("centered", T)
        self.assertEqual(core.path_radius(True, s0, s1, R), 1.5)
        self.assertEqual(core.path_radius(False, s0, s1, R), 1.5)

    def test_reliefs_only_where_the_flange_stops_inside(self):
        self.assertEqual(core.relief_ends(0, 30, 30, 1, 2), [])
        self.assertEqual(core.relief_ends(10, 20, 30, 1, 2), [(9.0, 10.0), (20.0, 21.0)])
        self.assertEqual(core.relief_ends(0, 20, 30, 1, 2), [(20.0, 21.0)])

    def test_remnant_sliver_is_cut(self):
        # 1.5 mm would be left beyond the relief: narrower than the 2 mm remnant, so cut to the end
        cuts = core.relief_ends(10, 27.5, 30, 1, 2)
        self.assertEqual(cuts[0], (9.0, 10.0))
        self.assertEqual(cuts[1][0], 27.5)
        self.assertGreater(cuts[1][1], 30.0)

    def test_l_bracket_flat_length(self):
        # research 4.2 worked example: 50 x 50 outer flattens to 98.26195
        flat = 100 - core.bend_deduction(90, R, T, 0.44)
        self.assertAlmostEqual(flat, 98.26195, places=4)


class RuleListTests(unittest.TestCase):
    def test_library_matches_research(self):
        names = [r["name"] for r in core.LIBRARY]
        self.assertEqual(names[0], "Steel (mm)")
        for material in ("Steel", "Stainless Steel", "Aluminum", "Copper"):
            self.assertIn("%s (mm)" % material, names)
            self.assertIn("%s (in)" % material, names)
        for rule in core.LIBRARY:
            self.assertEqual(rule["k_factor"], "0.44")
            self.assertEqual(rule["bend_radius"], "Thickness")
        self.assertEqual(core.library_rule("Aluminum (mm)")["thickness"], "1.5")

    def test_unique_and_checked_names(self):
        self.assertEqual(core.unique_name("Steel (mm)", ["Steel (mm)"]), "Steel (mm) 2")
        self.assertEqual(core.unique_name("A", ["A", "A 2"]), "A 3")
        self.assertEqual(core.unique_name("B", ["A"]), "B")
        self.assertIn("already", core.check_name("A", ["A", "B"]))
        self.assertEqual(core.check_name("A", ["A", "B"], old="A"), "")
        self.assertIn("name", core.check_name("  ", []))

    def test_lengths_as_typed(self):
        self.assertEqual(core.parse_length("1.5 mm", "mm"), "1.5")
        self.assertEqual(core.parse_length("Thickness * 2", "mm"), "Thickness * 2")
        with self.assertRaises(ValueError):
            core.parse_length("1 in", "mm")
        with self.assertRaises(ValueError):
            core.parse_length("Thick * 2", "mm")
        rule = core.make_rule("X")
        self.assertEqual(core.display_value(rule, "thickness"), "1.0 mm")
        self.assertEqual(core.display_value(rule, "bend_radius"), "Thickness")


if __name__ == "__main__":
    unittest.main()
