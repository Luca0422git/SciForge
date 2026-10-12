# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of SciForge's sketch inference (sciforge/sketch_infer_core.py): guides,
level/upright, perpendicular, parallel. Runs without FreeCAD."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import sketch_infer_core as core  # noqa: E402

PX = 0.2  # mm per pixel in these tests: 6 px = 1.2 mm


def rot(v, deg):
    r = math.radians(deg)
    return (v[0] * math.cos(r) - v[1] * math.sin(r), v[0] * math.sin(r) + v[1] * math.cos(r))


def run(raw, start=None, acquired=(), lines=(), vertices=(), curves=(), par_lines=(), **opts):
    opt = core.Options(**opts)
    return core.infer(
        raw,
        start,
        list(acquired),
        list(lines),
        list(vertices),
        list(curves),
        PX,
        opt,
        list(par_lines),
    )


class UnderThePointer(unittest.TestCase):
    def test_a_point_under_the_pointer_is_freecads_snap(self):
        a = ((3, 1), (10.0, 5.0))
        self.assertIsNone(run((10.5, 5.3), acquired=[a], vertices=[a]))

    def test_a_curve_under_the_pointer_is_freecads_snap(self):
        curve = ("seg", (0.0, 0.0), (50.0, 0.0))
        a = ((3, 1), (20.3, 30.0))
        self.assertIsNone(run((20.0, 0.4), acquired=[a], curves=[curve]))

    def test_the_axes_count_as_curves(self):
        axis = ("line", (0.0, 0.0), (0.0, 1.0))
        self.assertAlmostEqual(core.curve_distance((0.5, 70.0), axis), 0.5)


class Guides(unittest.TestCase):
    def test_straight_below_an_acquired_point_snaps_onto_its_x(self):
        a = ((3, 2), (10.0, 5.0))
        r = run((10.5, 20.0), acquired=[a])
        self.assertEqual(r.point, (10.0, 20.0))
        self.assertEqual([(g.key, g.axis) for g in r.guides], [((3, 2), core.SAME_X)])

    def test_too_far_from_the_guide_nothing_happens(self):
        a = ((3, 2), (10.0, 5.0))
        self.assertIsNone(run((11.5, 20.0), acquired=[a]))  # 7.5 px

    def test_two_guides_meet(self):
        a = ((1, 1), (10.0, 5.0))
        b = ((2, 1), (40.0, 30.0))
        r = run((10.4, 29.3), acquired=[a, b])
        self.assertEqual(r.point, (10.0, 30.0))
        self.assertEqual(sorted(g.axis for g in r.guides), [core.SAME_X, core.SAME_Y])

    def test_the_free_coordinate_keeps_the_grid_snap(self):
        a = ((3, 2), (10.3, 5.0))
        r = run((10.6, 21.1), acquired=[a], grid=10.0)
        self.assertEqual(r.point, (10.3, 20.0))
        r = run((10.6, 24.0), acquired=[a], grid=10.0)
        self.assertEqual(r.point, (10.3, 24.0))  # 4 mm off the grid: not snapped

    def test_the_lines_own_start_makes_no_guide(self):
        start = (0.0, 0.0)
        a = ((1, 1), start)
        # 30 degrees: no level/upright; straight above the start would be a guide
        self.assertIsNone(run((0.5, 30.0), start=start, acquired=[a], hv_deg=0.1))


class LevelUpright(unittest.TestCase):
    def test_within_4_degrees_becomes_level(self):
        r = run((30.0, 1.5), start=(0.0, 0.0))  # 2.9 degrees
        self.assertEqual(r.kind, core.HORIZONTAL)
        self.assertEqual(r.point, (30.0, 0.0))

    def test_upright_downwards(self):
        r = run((-1.0, -30.0), start=(0.0, 0.0))
        self.assertEqual(r.kind, core.VERTICAL)
        self.assertEqual(r.direction, (0.0, -1.0))
        self.assertAlmostEqual(r.point[0], 0.0)

    def test_beyond_the_tolerance_stays_free(self):
        self.assertIsNone(run((30.0, 3.0), start=(0.0, 0.0)))  # 5.7 degrees

    def test_freecads_own_2_degrees_when_set(self):
        self.assertIsNone(run((30.0, 1.5), start=(0.0, 0.0), hv_deg=2.0))

    def test_level_line_length_snaps_to_the_grid(self):
        r = run((31.0, 1.5), start=(0.0, 0.0), grid=10.0)
        self.assertEqual(r.point, (30.0, 0.0))

    def test_too_short_to_tell(self):
        self.assertIsNone(run((1.0, 0.05), start=(0.0, 0.0)))  # 5 px

    def test_level_meets_a_guide(self):
        a = ((4, 2), (20.3, 15.0))
        r = run((20.0, 0.8), start=(0.0, 0.0), acquired=[a])
        self.assertEqual(r.kind, core.HORIZONTAL)
        self.assertEqual(r.point, (20.3, 0.0))
        self.assertEqual([g.axis for g in r.guides], [core.SAME_X])


class Perpendicular(unittest.TestCase):
    SLANT = (5, (-20.0, -12.0), (0.0, 0.0))  # a line ending at the start, about 31 degrees

    def normal(self):
        u = core.unit((20.0, 12.0))
        return (-u[1], u[0])

    def test_starting_from_a_line_at_87_degrees_snaps_to_90(self):
        n = self.normal()
        raw = rot(n, -3.0)
        raw = (raw[0] * 25, raw[1] * 25)
        r = run(raw, start=(0.0, 0.0), lines=[self.SLANT])
        self.assertEqual(r.kind, core.PERPENDICULAR)
        self.assertEqual(r.other, 5)
        self.assertAlmostEqual(core.dot(r.direction, (20.0, 12.0)), 0.0)
        self.assertAlmostEqual(core.dot(r.point, (20.0, 12.0)), 0.0)  # on the perpendicular
        self.assertEqual(r.corner, (0.0, 0.0))

    def test_6_degrees_off_stays_free(self):
        n = self.normal()
        raw = rot(n, -6.0)
        self.assertIsNone(run((raw[0] * 25, raw[1] * 25), start=(0.0, 0.0), lines=[self.SLANT]))

    def test_level_or_upright_comes_first(self):
        flat = (6, (-20.0, 0.0), (0.0, 0.0))
        r = run((1.0, 30.0), start=(0.0, 0.0), lines=[flat])
        self.assertEqual(r.kind, core.VERTICAL)
        self.assertIsNone(r.other)

    def test_ending_on_a_line_at_88_degrees_goes_to_the_foot(self):
        line = (7, (10.0, -20.0), (50.0, 4.0))  # about 31 degrees
        u = core.unit((40.0, 24.0))
        n = (-u[1], u[0])
        foot = (10.0 + 40.0 * 0.3, -20.0 + 24.0 * 0.3)
        start = core.add(foot, core.mul(n, 18.0))
        gap = 18.0 * math.tan(math.radians(2.0))
        raw = core.add(core.add(foot, core.mul(u, gap)), core.mul(n, 1.5 * PX))
        curves = [("seg", line[1], line[2])]
        r = run(raw, start=start, lines=[line], curves=curves)
        self.assertEqual(r.kind, core.PERPENDICULAR)
        self.assertTrue(r.on_line)
        self.assertAlmostEqual(r.point[0], foot[0])
        self.assertAlmostEqual(r.point[1], foot[1])

    def test_the_middle_of_the_line_is_freecads_midpoint_snap(self):
        line = (7, (10.0, -20.0), (50.0, 4.0))
        u = core.unit((40.0, 24.0))
        n = (-u[1], u[0])
        mid = (30.0, -8.0)
        start = core.add(mid, core.mul(n, 18.0))
        curves = [("seg", line[1], line[2])]
        self.assertIsNone(run(mid, start=start, lines=[line], curves=curves))


class Parallel(unittest.TestCase):
    LINE = (8, (95.0, 2.0), (115.0, 14.0))

    def raw(self, start):
        d = core.unit(rot((20.0, 12.0), 1.5))
        return core.add(start, core.mul(d, 22.0))

    def test_off_by_default(self):
        start = (92.0, 23.0)
        self.assertIsNone(run(self.raw(start), start=start, par_lines=[self.LINE]))

    def test_switched_on_a_hovered_line_makes_it_parallel(self):
        start = (92.0, 23.0)
        r = run(self.raw(start), start=start, par_lines=[self.LINE], parallel=True)
        self.assertEqual(r.kind, core.PARALLEL)
        self.assertEqual(r.other, 8)
        self.assertAlmostEqual(core.angle_between(r.direction, (20.0, 12.0)), 0.0)


class AfterTheClick(unittest.TestCase):
    """exact_point: where the point FreeCAD placed goes exactly; grid_off: when FreeCAD's
    own grid snap must be off while it takes the point."""

    def test_level_line_keeps_freecads_grid_snapped_length(self):
        start = (-20.0, 25.03)
        r = run((19.98, 25.2), start=start, grid=10.0)
        self.assertEqual(r.kind, core.HORIZONTAL)
        # FreeCAD snapped the end's x to the grid, its y is a pixel off the start's
        self.assertEqual(core.exact_point(r, (20.0, 25.05), PX), (20.0, 25.03))

    def test_a_typed_length_along_the_level_is_kept(self):
        r = run((30.0, 1.5), start=(0.0, 0.0))
        self.assertEqual(core.exact_point(r, (25.0, 0.02), PX), (25.0, 0.0))

    def test_guide_point_placed_elsewhere_adds_nothing(self):
        a = ((3, 2), (10.0, 5.0))
        r = run((10.5, 20.0), acquired=[a])
        self.assertEqual(core.exact_point(r, (10.05, 21.3), PX), (10.0, 21.3))
        self.assertIsNone(core.exact_point(r, (12.0, 20.0), PX))  # 10 px off the guide

    def test_guide_with_freecads_grid_off_gets_the_grid_value_after_the_click(self):
        a = ((3, 2), (61.7, 8.6))
        r = run((62.0, 20.6), acquired=[a], grid=10.0)
        self.assertEqual(r.point, (61.7, 20.0))
        self.assertTrue(core.grid_off(r, 10.0, PX))  # 61.7 is 1.7 from a grid line
        self.assertEqual(core.exact_point(r, (61.66, 19.934), PX), (61.7, 20.0))

    def test_perpendicular_onto_a_line_needs_the_foot(self):
        line = (7, (10.0, -20.0), (50.0, 4.0))
        u = core.unit((40.0, 24.0))
        n = (-u[1], u[0])
        foot = (22.0, -12.8)
        start = core.add(foot, core.mul(n, 18.0))
        raw = core.add(core.add(foot, core.mul(u, 0.6)), core.mul(n, 0.2))
        r = run(raw, start=start, lines=[line], curves=[("seg", line[1], line[2])])
        self.assertEqual(core.exact_point(r, core.add(foot, core.mul(u, 0.1)), PX), r.point)
        self.assertIsNone(core.exact_point(r, core.add(foot, core.mul(u, 2.0)), PX))

    def test_grid_stays_on_when_it_cannot_pull_the_guide(self):
        on_grid = run((20.4, 33.0), acquired=[((1, 1), (20.0, 5.0))], grid=10.0)
        far = run((25.4, 33.0), acquired=[((1, 1), (25.0, 5.0))], grid=10.0)
        near = run((21.4, 33.0), acquired=[((1, 1), (21.0, 5.0))], grid=10.0)
        self.assertFalse(core.grid_off(on_grid, 10.0, PX))
        self.assertFalse(core.grid_off(far, 10.0, PX))
        self.assertTrue(core.grid_off(near, 10.0, PX))  # FreeCAD would pull x to 20
        self.assertFalse(core.grid_off(near, None, PX))  # grid snap off anyway

    def test_grid_off_for_slanted_directions(self):
        slant = (5, (-20.0, -12.0), (0.0, 0.0))
        u = core.unit((20.0, 12.0))
        raw = core.mul(rot((-u[1], u[0]), -3.0), 25.0)
        r = run(raw, start=(0.0, 0.0), lines=[slant], grid=10.0)
        self.assertTrue(core.grid_off(r, 10.0, PX))


class Helpers(unittest.TestCase):
    def test_grid_snap_like_freecad(self):
        self.assertEqual(core.grid_snap(21.9, 10.0), 20.0)
        self.assertEqual(core.grid_snap(22.0, 10.0), 22.0)  # a fifth of the spacing: not closer
        self.assertEqual(core.grid_snap(-18.5, 10.0), -20.0)
        self.assertEqual(core.grid_snap(7.0, None), 7.0)

    def test_three_hovered_points_remembered(self):
        items = []
        for k in "abcd":
            items = core.remember(items, k, 3)
        self.assertEqual(items, ["b", "c", "d"])
        self.assertEqual(core.remember(items, "b", 3), ["c", "d", "b"])

    def test_right_angle_mark(self):
        pts = core.right_angle_mark((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), 2.0)
        self.assertEqual(pts, [(2.0, 0.0), (2.0, 2.0), (0.0, 2.0)])

    def test_options_refuse_unknown_names(self):
        with self.assertRaises(AttributeError):
            core.Options(guide_pixels=3)


if __name__ == "__main__":
    unittest.main()
