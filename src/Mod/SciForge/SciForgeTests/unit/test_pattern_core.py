# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the copies of Fusion's Rectangular / Circular Pattern go (sciforge/pattern_core.py).
Runs without FreeCAD."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import pattern_core as core  # noqa: E402


def walk_positions(gaps):
    """Positions FreeCAD's pattern makes from a list of gaps (the original at 0)."""
    out, run = [0.0], 0.0
    for gap in gaps:
        run += gap
        out.append(run)
    return out


class LinearTests(unittest.TestCase):
    def test_extent_spreads_over_the_distance(self):
        self.assertEqual(core.linear_offsets(3, 40), [0.0, 20.0, 40.0])

    def test_spacing_is_the_gap(self):
        self.assertEqual(core.linear_offsets(3, 15, "spacing"), [0.0, 15.0, 30.0])

    def test_negative_distance_goes_the_other_way(self):
        self.assertEqual(core.linear_offsets(2, -26, "spacing"), [0.0, -26.0])

    def test_quantity_one_is_the_original(self):
        self.assertEqual(core.linear_offsets(1, 40), [0.0])

    def test_symmetric_mirrors_the_one_direction_pattern(self):
        offsets = core.linear_offsets(3, 20, "extent", "symmetric")
        self.assertEqual(sorted(offsets), [-20.0, -10.0, 0.0, 10.0, 20.0])
        self.assertEqual(offsets[0], 0.0)  # FreeCAD needs the original first
        self.assertEqual(core.instance_count(3, "symmetric"), 5)

    def test_quantity_below_one_is_refused(self):
        with self.assertRaises(core.PatternError):
            core.linear_offsets(0, 10)

    def test_grid_starts_with_the_original(self):
        cells = core.grid([0.0, 10.0], [0.0, 5.0, 10.0])
        self.assertEqual(cells[0], (0.0, 0.0))
        self.assertEqual(len(cells), 6)


class WalkTests(unittest.TestCase):
    def test_walk_reaches_every_offset(self):
        offsets = core.linear_offsets(4, 9, "spacing", "symmetric")
        self.assertEqual(walk_positions(core.walk(offsets)), offsets)

    def test_symmetric_terms_give_the_symmetric_positions(self):
        for quantity in range(1, 7):
            step = 2.5
            gaps = [step * t for t in core.symmetric_walk_terms(quantity)]
            positions = sorted(walk_positions(gaps))
            expect = sorted(step * k for k in range(-(quantity - 1), quantity))
            self.assertEqual(positions, expect)

    def test_minus_one_is_never_written(self):
        # A gap of exactly -1 reads as "use the Offset value" in FreeCAD.
        gaps = core.safe_walk([0.5, -1.0, 0.5])
        self.assertNotIn(-1.0, gaps)
        self.assertAlmostEqual(gaps[1], -1.0, places=6)


class CircularTests(unittest.TestCase):
    def test_full_circle(self):
        self.assertEqual(core.circular_angles(4), [0.0, 90.0, 180.0, 270.0])

    def test_angle_includes_both_ends(self):
        self.assertEqual(core.circular_angles(3, 90, "angle"), [0.0, 45.0, 90.0])

    def test_angle_of_360_is_a_full_circle(self):
        self.assertEqual(core.circular_angles(4, 360, "angle"), [0.0, 90.0, 180.0, 270.0])

    def test_negative_angle_turns_the_other_way(self):
        self.assertEqual(core.circular_angles(3, -90, "angle"), [0.0, -45.0, -90.0])

    def test_symmetric_both_sides(self):
        self.assertEqual(sorted(core.circular_angles(2, 60, "symmetric")), [-60.0, 0.0, 60.0])

    def test_zero_angle_is_refused(self):
        with self.assertRaises(core.PatternError):
            core.circular_angles(3, 0, "angle")


class DefaultTests(unittest.TestCase):
    def test_default_distance_clears_the_object(self):
        self.assertGreater(core.default_distance(4.0, 2), 4.0)
        self.assertEqual(core.default_distance(4.0, 3), 2 * core.default_distance(4.0, 2))


if __name__ == "__main__":
    unittest.main()
