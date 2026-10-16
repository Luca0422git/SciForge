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


def run(
    raw, start=None, acquired=(), lines=(), vertices=(), curves=(), par_lines=(), anchors=(), **opts
):
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
        list(anchors),
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

    def test_a_shapes_own_placed_points_make_no_guide(self):
        """A rectangle's first corner (an anchor, known to a pixel or so) gives no guide
        to its second corner; a far point still does."""
        corner = ((7, 1), (10.0, 5.0))
        other = ((3, 2), (40.0, 30.0))
        self.assertIsNone(run((10.5, 20.0), acquired=[corner], anchors=[(10.0, 5.0)]))
        self.assertIsNone(run((10.5, 20.0), acquired=[corner], anchors=[(10.4, 5.3)]))  # 2 px
        r = run((10.5, 29.4), acquired=[corner, other], anchors=[(10.0, 5.0)])
        self.assertEqual(r.point, (10.5, 30.0))
        self.assertEqual([g.key for g in r.guides], [(3, 2)])


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

    def test_level_and_upright_marks_sit_beside_the_line_near_its_end(self):
        level = core.level_mark((0.0, 0.0), (20.0, 0.0), 2.0)
        self.assertEqual(
            [tuple(round(v, 9) for v in p) for p in level[0]], [(16.8, -2.4), (20.0, -2.4)]
        )
        upright = core.upright_mark((5.0, 0.0), (5.0, 10.0), 2.0)
        self.assertEqual(
            [tuple(round(v, 9) for v in p) for p in upright[0]], [(7.4, 7.6), (7.4, 10.8)]
        )

    def test_tangent_mark_lies_outside_the_joint(self):
        strokes = core.tangent_mark((0.0, 0.0), (1.0, 0.0), (0.0, -1.0), 2.0)
        self.assertEqual(strokes, [[(-1.6, -2.4), (1.6, -2.4)]])


class OtherTools(unittest.TestCase):
    """The previews of the other drawing tools: where the direction starts and which
    preview point follows the pointer."""

    RECT = [[(5.0, 7.0), (25.0, 7.0)], [(25.0, 7.0), (25.0, 20.0)],
            [(25.0, 20.0), (5.0, 20.0)], [(5.0, 20.0), (5.0, 7.0)]]  # fmt: skip

    def slot(self):
        # two half circles (arc ends opposite each other) and two lines
        arc1 = [(2.7, 10.9), (0.0, 7.0), (7.9, 2.9)]
        arc2 = [(27.9, 16.0), (30.0, 20.0), (22.6, 24.0)]
        return [arc1, arc2, [(2.7, 10.9), (22.6, 24.0)], [(7.9, 2.9), (27.9, 16.0)]]

    def test_every_drawing_command_has_a_kind_and_a_point_count(self):
        for command, kind in core.TOOLS.items():
            self.assertIn(kind, core.POINTS, command)
        self.assertEqual(core.TOOLS["SciForge_SketchLine"], "line")
        self.assertEqual(core.POINTS["slot"], 2)  # the third click is the width

    def test_line_direction_starts_at_its_first_point(self):
        self.assertEqual(core.preview_anchor("line", [[(1.0, 2.0), (9.0, 2.0)]]), (1.0, 2.0))
        self.assertIsNone(core.preview_anchor("line", []))
        self.assertIsNone(core.preview_anchor("line", [[(1.0, 2.0)]]))

    def test_slot_direction_starts_at_its_first_centre(self):
        anchor = core.preview_anchor("slot", self.slot())
        self.assertAlmostEqual(anchor[0], 5.3)
        self.assertAlmostEqual(anchor[1], 6.9)
        self.assertIsNone(core.preview_anchor("slot", [[(0.0, 0.0), (1.0, 1.0)]]))

    def test_shapes_without_a_direction(self):
        self.assertIsNone(core.preview_anchor("rect", self.RECT))
        self.assertIsNone(core.preview_anchor("circle", [[(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)]]))

    def test_what_a_preview_shows(self):
        circle = [[(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0), (1.0, 0.0)]]
        self.assertIsNone(core.preview_kind([]))
        self.assertEqual(core.preview_kind([[(1.0, 2.0), (9.0, 2.0)]]), "line")
        self.assertEqual(core.preview_kind(circle), "circle")
        self.assertEqual(core.preview_kind(self.RECT), "rect")
        self.assertEqual(core.preview_kind(self.RECT + [[(0.0, 0.0), (1.0, 1.0)]]), "polygon")
        self.assertEqual(core.preview_kind(self.slot()), "slot")
        self.assertEqual(core.preview_kind(circle + self.RECT[:2]), "arc")
        self.assertEqual(core.preview_kind(circle + self.RECT[:1]), "arc3")

    def test_a_tool_started_another_way_is_told_by_its_preview(self):
        # SciForge last ran the circle tool, but FreeCAD previews a rectangle
        self.assertEqual(core.tool_kind("circle", self.RECT), "rect")
        self.assertEqual(core.tool_kind("circle", []), "circle")  # nothing shown yet
        circle = [[(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (1.0, 0.0)]]
        self.assertEqual(core.tool_kind("arc", circle), "arc")  # an arc starts as a circle
        self.assertEqual(core.tool_kind("polygon", self.RECT), "polygon")  # four sides
        self.assertIsNone(core.tool_kind(None, self.RECT))  # an unknown tool stays unknown

    def test_the_preview_point_that_follows_the_pointer(self):
        self.assertEqual(
            core.preview_pointer("line", [[(1.0, 2.0), (9.0, 2.0)]], (9.0, 2.0)), (9.0, 2.0)
        )
        self.assertEqual(core.preview_pointer("rect", self.RECT, (24.8, 19.7)), (25.0, 20.0))
        pointer = core.preview_pointer("slot", self.slot(), (25.0, 20.0))
        self.assertAlmostEqual(pointer[0], 25.25)
        self.assertAlmostEqual(pointer[1], 20.0)
        self.assertIsNone(core.preview_pointer("circle", [], (0.0, 0.0)))


class TangentArc(unittest.TestCase):
    """Fusion's tangent arc from the end of a line: press, drag, release."""

    def test_arc_turning_left(self):
        arc = core.tangent_arc((0.0, 0.0), (1.0, 0.0), (10.0, 10.0), 2.0)
        self.assertAlmostEqual(arc.centre[0], 0.0)
        self.assertAlmostEqual(arc.centre[1], 10.0)
        self.assertAlmostEqual(arc.radius, 10.0)
        self.assertEqual(arc.joint_pos, 1)  # counterclockwise: the joint is the start
        self.assertEqual(arc.free_pos, 2)
        s, e = arc.point(arc.a1), arc.point(arc.a2)
        self.assertAlmostEqual(s[0], 0.0)
        self.assertAlmostEqual(s[1], 0.0)
        self.assertAlmostEqual(e[0], 10.0)
        self.assertAlmostEqual(e[1], 10.0)
        self.assertAlmostEqual(arc.a2 - arc.a1, math.pi / 2)

    def test_arc_turning_right_runs_the_other_way_round(self):
        arc = core.tangent_arc((0.0, 0.0), (1.0, 0.0), (10.0, -10.0), 2.0)
        self.assertAlmostEqual(arc.centre[1], -10.0)
        self.assertEqual(arc.joint_pos, 2)  # clockwise: as a ccw arc the joint is its end
        self.assertEqual(arc.free_pos, 1)
        p, s = arc.point(arc.a1), arc.point(arc.a2)
        self.assertAlmostEqual(p[0], 10.0)
        self.assertAlmostEqual(p[1], -10.0)
        self.assertAlmostEqual(s[0], 0.0)
        self.assertAlmostEqual(s[1], 0.0)

    def test_dragging_back_behind_the_start_makes_a_big_arc(self):
        arc = core.tangent_arc((0.0, 0.0), (1.0, 0.0), (-10.0, 10.0), 2.0)
        self.assertAlmostEqual(arc.radius, 10.0)
        self.assertAlmostEqual(arc.a2 - arc.a1, 1.5 * math.pi)

    def test_straight_ahead_or_too_close_is_no_arc(self):
        self.assertIsNone(core.tangent_arc((0.0, 0.0), (1.0, 0.0), (10.0, 0.05), 2.0))
        self.assertIsNone(core.tangent_arc((0.0, 0.0), (1.0, 0.0), (-10.0, 0.05), 2.0))
        self.assertIsNone(core.tangent_arc((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), 2.0))

    def test_a_slanted_tangent(self):
        t = core.unit((3.0, 4.0))
        arc = core.tangent_arc((1.0, 1.0), t, (-3.0, 4.0), 0.5)
        # the centre is on the normal through the start, both ends on the circle
        radial = core.sub((1.0, 1.0), arc.centre)
        self.assertAlmostEqual(core.dot(radial, t), 0.0)
        self.assertAlmostEqual(core.dist(arc.centre, (-3.0, 4.0)), arc.radius)
        pts = arc.points(10)
        self.assertEqual(len(pts), 11)
        self.assertAlmostEqual(core.dist(pts[0], arc.centre), arc.radius)

    def test_chain_tangent_from_the_newest_line_ending_here(self):
        curves = [("line", 4, (0.0, 0.0), (10.0, 0.0)), ("line", 2, (10.0, 0.0), (10.0, 5.0))]
        t, end = core.chain_tangent((10.0, 0.0), curves, 1e-6)
        self.assertEqual(end, (4, 2))
        self.assertEqual(t, (1.0, 0.0))

    def test_chain_tangent_from_a_line_starting_here_goes_backwards(self):
        curves = [("line", 2, (10.0, 0.0), (10.0, 5.0))]
        t, end = core.chain_tangent((10.0, 0.0), curves, 1e-6)
        self.assertEqual(end, (2, 1))
        self.assertEqual(t, (0.0, -1.0))

    def test_chain_tangent_follows_an_arc_round(self):
        # a quarter arc about (0, 10) from (0, 0) counterclockwise up to (10, 10)
        arc = ("arc", 5, (0.0, 10.0), (0.0, 0.0), (10.0, 10.0))
        t, end = core.chain_tangent((10.0, 10.0), [arc], 1e-6)
        self.assertEqual(end, (5, 2))
        self.assertAlmostEqual(t[0], 0.0)
        self.assertAlmostEqual(t[1], 1.0)
        # the chain leaving at the arc's start runs the arc backwards
        t, end = core.chain_tangent((0.0, 0.0), [arc], 1e-6)
        self.assertEqual(end, (5, 1))
        self.assertAlmostEqual(t[0], -1.0)
        self.assertAlmostEqual(t[1], 0.0)

    def test_no_curve_ends_here(self):
        self.assertIsNone(
            core.chain_tangent((3.0, 3.0), [("line", 1, (0.0, 0.0), (1.0, 0.0))], 1e-6)
        )


if __name__ == "__main__":
    unittest.main()


class SnapPoints(unittest.TestCase):
    """Fusion: ends, middles (the triangle), centres; SciForge adds circle quadrants and
    crossings. The sketch's own curves and the projected ones (geo -3, -4...) alike."""

    def kinds(self, points):
        return sorted((s.kind, tuple(round(c, 9) for c in s.point)) for s in points)

    def test_a_line_has_two_ends_and_a_middle(self):
        pts = core.snap_points([("line", 0, (0.0, 0.0), (10.0, 4.0))])
        self.assertEqual(
            self.kinds(pts),
            [(core.END, (0.0, 0.0)), (core.END, (10.0, 4.0)), (core.MIDDLE, (5.0, 2.0))],
        )
        ends = {s.key for s in pts if s.kind == core.END}
        self.assertEqual(ends, {(0, 1), (0, 2)})
        middle = [s for s in pts if s.kind == core.MIDDLE][0]
        self.assertEqual((middle.key, middle.geo), (None, 0))

    def test_a_projected_line_snaps_the_same(self):
        pts = core.snap_points([("line", -3, (0.0, 0.0), (40.0, 0.0))])
        self.assertIn((core.MIDDLE, (20.0, 0.0)), self.kinds(pts))
        self.assertEqual({s.key for s in pts if s.kind == core.END}, {(-3, 1), (-3, 2)})

    def test_a_circle_has_its_centre_and_four_quadrants(self):
        pts = core.snap_points([("circle", 2, (1.0, 1.0), 5.0)])
        self.assertEqual(
            self.kinds(pts),
            [
                (core.CENTRE, (1.0, 1.0)),
                (core.QUADRANT, (-4.0, 1.0)),
                (core.QUADRANT, (1.0, -4.0)),
                (core.QUADRANT, (1.0, 6.0)),
                (core.QUADRANT, (6.0, 1.0)),
            ],
        )
        self.assertEqual([s.key for s in pts if s.kind == core.CENTRE], [(2, 3)])

    def test_an_arc_has_ends_centre_middle_and_the_quadrants_on_it(self):
        # a quarter-and-a-bit from 30 to 150 degrees round (0, 0), r 10: 90 degrees is
        # its middle (not a second point), no other quadrant lies on it
        r = 10.0
        start = (r * math.cos(math.radians(30)), r * math.sin(math.radians(30)))
        end = (r * math.cos(math.radians(150)), r * math.sin(math.radians(150)))
        pts = core.snap_points([("arc", 1, (0.0, 0.0), r, start, end, (0.0, r))])
        kinds = sorted(s.kind for s in pts)
        self.assertEqual(kinds, sorted([core.END, core.END, core.CENTRE, core.MIDDLE]))

    def test_the_quadrants_of_a_long_arc(self):
        # from -60 to 240 degrees counterclockwise: 0, 90 and 180 lie on it, 270 not
        r = 4.0
        a0, a1 = math.radians(-60), math.radians(240)
        start = (r * math.cos(a0), r * math.sin(a0))
        end = (r * math.cos(a1), r * math.sin(a1))
        mid = (r * math.cos(math.radians(90)), r * math.sin(math.radians(90)))
        pts = core.snap_points([("arc", 1, (0.0, 0.0), r, start, end, mid)])
        quads = sorted(tuple(round(c, 9) for c in s.point) for s in pts if s.kind == core.QUADRANT)
        self.assertEqual(quads, [(-4.0, 0.0), (4.0, 0.0)])  # 90 is the middle already

    def test_an_arc_running_the_other_way_round(self):
        # the same ends, through 270 degrees (the long way): 0, 180 and 270 on it
        r = 4.0
        start = (r * math.cos(math.radians(240)), r * math.sin(math.radians(240)))
        end = (r * math.cos(math.radians(-60)), r * math.sin(math.radians(-60)))
        self.assertTrue(
            core.on_arc(math.radians(270), math.radians(240), math.radians(-60), math.radians(270))
        )
        self.assertFalse(
            core.on_arc(math.radians(90), math.radians(240), math.radians(-60), math.radians(270))
        )
        pts = core.snap_points([("arc", 1, (0.0, 0.0), r, start, end, (0.0, -r))])
        quads = [s for s in pts if s.kind == core.QUADRANT]
        self.assertEqual(quads, [])  # 270 is its middle; 0 and 180 are not on the short way

    def test_points_ellipses_conic_arcs_and_splines(self):
        pts = core.snap_points(
            [
                ("point", 0, (3.0, 3.0)),
                ("ellipse", 1, (0.0, 0.0)),
                ("conic_arc", 2, (5.0, 5.0), (6.0, 5.0), (5.0, 7.0)),
                ("spline", 3, (0.0, 9.0), (9.0, 9.0)),
            ]
        )
        keys = sorted(s.key for s in pts)
        self.assertEqual(keys, [(0, 1), (1, 3), (2, 1), (2, 2), (2, 3), (3, 1), (3, 2)])

    def test_the_nearest_within_the_radius(self):
        pts = core.snap_points([("line", 0, (0.0, 0.0), (10.0, 0.0))])
        self.assertEqual(core.nearest_snap((4.6, 0.3), pts, 1.0).kind, core.MIDDLE)
        self.assertEqual(core.nearest_snap((9.5, 0.2), pts, 1.0).key, (0, 2))
        self.assertIsNone(core.nearest_snap((7.5, 0.0), pts, 1.0))

    def test_a_sketch_corner_on_a_projected_corner_is_the_sketch_point(self):
        pts = core.snap_points(
            [("line", -3, (0.0, 0.0), (40.0, 0.0)), ("line", 4, (0.0, 0.0), (0.0, 10.0))]
        )
        hit = core.nearest_snap((0.2, 0.1), pts, 1.0)
        self.assertEqual(hit.key, (4, 1))

    def test_an_end_beats_a_middle_on_the_same_spot(self):
        pts = core.snap_points(
            [("line", 0, (0.0, 0.0), (10.0, 0.0)), ("line", 1, (5.0, 0.0), (5.0, 5.0))]
        )
        hit = core.nearest_snap((5.1, 0.1), pts, 1.0)
        self.assertEqual((hit.kind, hit.key), (core.END, (1, 1)))

    def test_snap_result(self):
        s = core.SnapPoint(core.QUADRANT, (5.0, 0.0), geo=2)
        r = core.snap_result(s, (1.0, 1.0))
        self.assertEqual((r.point, r.snap, r.start, r.kind), ((5.0, 0.0), s, (1.0, 1.0), None))


class Crossings(unittest.TestCase):
    def test_two_lines_crossing_near_the_pointer(self):
        items = [("line", 0, (0.0, 0.0), (10.0, 10.0)), ("line", -3, (0.0, 10.0), (10.0, 0.0))]
        found = core.crossings((5.2, 4.9), items, 1.0)
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0].kind, found[0].geo, found[0].other), (core.CROSSING, 0, -3))
        self.assertAlmostEqual(found[0].point[0], 5.0)
        self.assertAlmostEqual(found[0].point[1], 5.0)

    def test_far_from_the_pointer_nothing(self):
        items = [("line", 0, (0.0, 0.0), (10.0, 10.0)), ("line", 1, (0.0, 10.0), (10.0, 0.0))]
        self.assertEqual(core.crossings((8.0, 8.0), items, 1.0), [])

    def test_lines_meeting_at_their_ends_are_end_points_not_crossings(self):
        items = [("line", 0, (0.0, 0.0), (10.0, 0.0)), ("line", 1, (10.0, 0.0), (10.0, 5.0))]
        self.assertEqual(core.crossings((10.0, 0.2), items, 1.0), [])

    def test_a_line_through_a_circle(self):
        items = [("line", 0, (-10.0, 0.0), (10.0, 0.0)), ("circle", 1, (0.0, 0.0), 5.0)]
        found = core.crossings((4.8, 0.3), items, 1.0)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0].point[0], 5.0)

    def test_two_circles(self):
        items = [("circle", 0, (0.0, 0.0), 5.0), ("circle", 1, (6.0, 0.0), 5.0)]
        found = core.crossings((3.0, 4.0), items, 0.5)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0].point[0], 3.0)
        self.assertAlmostEqual(found[0].point[1], 4.0)

    def test_an_arc_crossing_only_where_the_arc_is(self):
        r = 5.0
        arc = ("arc", 1, (0.0, 0.0), r, (r, 0.0), (-r, 0.0), (0.0, r))  # the upper half
        line = ("line", 0, (0.0, -10.0), (0.0, 10.0))
        self.assertEqual(len(core.crossings((0.2, 4.9), [line, arc], 1.0)), 1)
        self.assertEqual(core.crossings((0.2, -4.9), [line, arc], 1.0), [])


class SnapAfterTheClick(unittest.TestCase):
    def test_a_snap_point_is_placed_exactly(self):
        r = core.snap_result(core.SnapPoint(core.END, (10.0, 0.0), (-3, 2)))
        self.assertEqual(core.exact_point(r, (10.1, -0.1), PX), (10.0, 0.0))

    def test_placed_elsewhere_nothing(self):
        r = core.snap_result(core.SnapPoint(core.END, (10.0, 0.0), (-3, 2)))
        self.assertIsNone(core.exact_point(r, (11.0, 0.0), PX))

    def test_freecads_grid_is_off_for_a_snap(self):
        r = core.snap_result(core.SnapPoint(core.QUADRANT, (5.0, 0.0), geo=1))
        self.assertTrue(core.grid_off(r, 1.0, PX))


class Diagonal(unittest.TestCase):
    """45 / 135 / 225 / 315 degrees (beyond Fusion: Luca's wish; always on, Ctrl frees)."""

    def test_3_degrees_off_45_snaps_to_45(self):
        start = (0.0, 0.0)
        raw = rot((40.0, 0.0), 48.0)
        r = run(raw, start=start)
        self.assertEqual(r.kind, core.DIAGONAL)
        self.assertAlmostEqual(math.degrees(math.atan2(r.point[1], r.point[0])), 45.0)

    def test_all_four_diagonals(self):
        for deg in (135.0, 225.0, 315.0):
            r = run(rot((40.0, 0.0), deg + 2.5), start=(0.0, 0.0))
            self.assertEqual(r.kind, core.DIAGONAL, deg)
            ang = math.degrees(math.atan2(r.direction[1], r.direction[0])) % 360.0
            self.assertAlmostEqual(ang, deg)

    def test_beyond_the_tolerance_stays_free(self):
        self.assertIsNone(run(rot((40.0, 0.0), 51.0), start=(0.0, 0.0)))

    def test_its_own_tolerance_and_off(self):
        raw = rot((40.0, 0.0), 51.0)
        self.assertEqual(run(raw, start=(0.0, 0.0), diag_deg=7.0).kind, core.DIAGONAL)
        self.assertIsNone(run(rot((40.0, 0.0), 46.0), start=(0.0, 0.0), diag_deg=0.0))

    def test_level_and_upright_come_first(self):
        self.assertEqual(run(rot((40.0, 0.0), 3.0), start=(0.0, 0.0)).kind, core.HORIZONTAL)

    def test_the_grid_is_off_for_a_diagonal(self):
        r = run(rot((40.0, 0.0), 44.0), start=(0.0, 0.0), grid=1.0)
        self.assertTrue(core.grid_off(r, 1.0, PX))

    def test_placed_exactly_on_the_diagonal_after_the_click(self):
        r = run(rot((40.0, 0.0), 44.0), start=(0.0, 0.0))
        placed = (r.point[0] + 0.05, r.point[1] - 0.05)
        p = core.exact_point(r, placed, PX)
        self.assertAlmostEqual(p[0], p[1])

    def test_meets_a_guide(self):
        a = ((3, 2), (20.0, 50.0))
        r = run(rot((30.0, 0.0), 46.0), start=(0.0, 0.0), acquired=[a])
        self.assertEqual(r.kind, core.DIAGONAL)
        self.assertAlmostEqual(r.point[0], 20.0)
        self.assertAlmostEqual(r.point[1], 20.0)
        self.assertEqual([g.axis for g in r.guides], [core.SAME_X])

    def test_the_angle_constraint_value(self):
        self.assertAlmostEqual(core.diagonal_angle((1.0, 1.0)), math.pi / 4)
        self.assertAlmostEqual(core.diagonal_angle((-1.0, 1.02)), 3 * math.pi / 4)
        self.assertAlmostEqual(core.diagonal_angle((-1.0, -1.0)), -3 * math.pi / 4)
        self.assertAlmostEqual(core.diagonal_angle((1.0, -0.98)), -math.pi / 4)
