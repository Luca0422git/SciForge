# SPDX-License-Identifier: LGPL-2.1-or-later
"""Picking sketch areas inside an open sketch (sciforge/sketch_areas_core.py): which area
is under the pointer and what a click does to the picked areas. Runs without FreeCAD."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import sketch_areas_core as core  # noqa: E402


def square(x0, y0, x1, y1):
    """A rectangle as two triangles."""
    return core.Region([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], [(0, 1, 2), (0, 2, 3)])


# Two separate squares A (0..20) and B (30..50).
A = square(0, 0, 20, 20)
B = square(30, 0, 50, 20)
AREAS = [A, B]


class UnderThePointer(unittest.TestCase):
    def test_inside_each_square(self):
        self.assertEqual(core.region_at(AREAS, 10, 10), 0)
        self.assertEqual(core.region_at(AREAS, 40, 5), 1)

    def test_between_and_outside(self):
        self.assertIsNone(core.region_at(AREAS, 25, 10))
        self.assertIsNone(core.region_at(AREAS, 10, 30))

    def test_on_a_shared_edge_the_smaller_area_wins(self):
        big = square(0, 0, 40, 40)
        small = square(10, 10, 20, 20)  # touches nothing else; on its edge both contain
        self.assertEqual(core.region_at([big, small], 10, 15), 1)

    def test_triangle_edges_count_as_inside(self):
        self.assertTrue(core.in_triangle(0, 0, (0, 0), (1, 0), (0, 1)))
        self.assertTrue(core.in_triangle(0.5, 0.5, (0, 0), (1, 0), (0, 1)))
        self.assertFalse(core.in_triangle(0.6, 0.6, (0, 0), (1, 0), (0, 1)))

    def test_area_of_the_triangles(self):
        self.assertAlmostEqual(A.area, 400.0)

    def test_an_empty_region_contains_nothing(self):
        self.assertFalse(core.Region([], []).contains(0, 0))


class Clicks(unittest.TestCase):
    def test_click_picks_the_area(self):
        self.assertEqual(core.click([], AREAS, (10, 10), False), [(10, 10)])

    def test_the_remembered_point_is_the_anchor(self):
        self.assertEqual(core.click([], AREAS, (1, 1), False, anchor=(10, 10)), [(10, 10)])

    def test_plain_click_on_another_area_replaces(self):
        self.assertEqual(core.click([(10, 10)], AREAS, (40, 10), False), [(40, 10)])

    def test_ctrl_or_shift_click_adds(self):
        self.assertEqual(core.click([(10, 10)], AREAS, (40, 10), True), [(10, 10), (40, 10)])

    def test_clicking_a_picked_area_again_drops_it(self):
        self.assertEqual(core.click([(10, 10)], AREAS, (5, 5), False), [])
        self.assertEqual(core.click([(10, 10), (40, 10)], AREAS, (5, 5), False), [(40, 10)])
        self.assertEqual(core.click([(10, 10), (40, 10)], AREAS, (45, 15), True), [(10, 10)])

    def test_plain_click_on_empty_space_clears(self):
        self.assertEqual(core.click([(10, 10), (40, 10)], AREAS, (25, 10), False), [])

    def test_ctrl_click_on_empty_space_keeps(self):
        self.assertEqual(core.click([(10, 10)], AREAS, (25, 10), True), [(10, 10)])


class AfterTheSketchChanged(unittest.TestCase):
    def test_points_outside_every_area_are_dropped(self):
        self.assertEqual(core.keep_valid([(10, 10), (25, 10)], AREAS), [(10, 10)])

    def test_two_points_in_one_area_count_once(self):
        merged = [square(0, 0, 50, 20)]  # the line between A and B was deleted
        self.assertEqual(core.keep_valid([(10, 10), (40, 10)], merged), [(10, 10)])
        self.assertEqual(core.picked_regions([(10, 10), (40, 10)], merged), [0])

    def test_picked_regions_in_pick_order(self):
        self.assertEqual(core.picked_regions([(40, 10), (10, 10)], AREAS), [1, 0])



class InFrontOfTheFace(unittest.TestCase):
    """front_shift: a finished sketch drawn a hair toward the camera (sketch_area_pick)."""

    def test_toward_the_camera(self):
        self.assertGreater(core.front_shift(-1.0, 100.0), 0)  # normal points at the camera
        self.assertLess(core.front_shift(1.0, 100.0), 0)  # seen from behind
        self.assertLess(core.front_shift(0.0, 100.0), 0)  # edge-on: either way is fine

    def test_tiny_and_a_power_of_two(self):
        for distance in (0.0, 1.0, 50.0, 300.0, 5000.0, 1e6):
            size = core.front_shift(-1.0, distance)
            self.assertGreaterEqual(size, core.SHIFT_MIN)
            self.assertLessEqual(size, max(2 * core.SHIFT_MIN, 2 * core.SHIFT_PER_MM * distance))
            exponent = math.log(size, 2)
            self.assertAlmostEqual(exponent, round(exponent))

    def test_grows_with_the_distance_in_steps(self):
        near = core.front_shift(-1.0, 100.0)
        self.assertEqual(near, core.front_shift(-1.0, 110.0))  # small zoom: no change
        self.assertGreater(core.front_shift(-1.0, 10000.0), near)  # far camera: larger

    def test_never_visible_on_a_part(self):
        # 300 mm away (a 40 mm part filling the view): well under a tenth of a pixel
        self.assertLess(core.front_shift(-1.0, 300.0), 0.02)


if __name__ == "__main__":
    unittest.main()
