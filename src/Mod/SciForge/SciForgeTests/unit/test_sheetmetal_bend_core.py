# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of Bend, Hem, Join by Bend, Corner Closure and Lofted Flange
(sciforge/sheetmetal_bend_core.py), without FreeCAD."""

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sciforge import sheetmetal_bend_core as core  # noqa: E402

T, R, K = 1.0, 1.0, 0.44
BA90 = math.pi / 2 * (R + K * T)  # 2.26195 (research 4.2 worked example)


class BendZoneTests(unittest.TestCase):
    def test_positions_place_the_zone_against_the_line(self):
        self.assertAlmostEqual(BA90, 2.2619467, places=6)
        self.assertEqual(core.bend_zone("start", 90, R, T, K), (0.0, BA90))
        s0, s1 = core.bend_zone("center", 90, R, T, K)
        self.assertAlmostEqual(s0, -BA90 / 2)
        self.assertAlmostEqual(s1, BA90 / 2)
        s0, s1 = core.bend_zone("end", 90, R, T, K)
        self.assertAlmostEqual(s0, -BA90)
        self.assertAlmostEqual(s1, 0.0)

    def test_unknown_position_refused(self):
        with self.assertRaises(ValueError):
            core.zone_start("middle", 1.0)

    def test_angle_limits(self):
        self.assertEqual(core.check_bend(90, R, T), [])
        self.assertTrue(core.check_bend(0, R, T))
        self.assertTrue(core.check_bend(181, R, T))
        self.assertTrue(core.check_bend(90, -1, T))


class StripTests(unittest.TestCase):
    def test_walk_quarter_bend_then_wall(self):
        pieces, end = core.walk([("arc", 90, R), ("line", 10)], (0.0, -T / 2), 0.0, T)
        self.assertEqual([p["kind"] for p in pieces], ["arc", "line"])
        x, y, heading = end
        self.assertAlmostEqual(heading, 90.0)
        # centre-line radius R + T/2 = 1.5: the bend ends 1.5 right and 1.5 up
        self.assertAlmostEqual(x, 1.5)
        self.assertAlmostEqual(y, -0.5 + 1.5 + 10)

    def test_strip_area_is_centre_length_times_thickness(self):
        pieces, _ = core.walk([("arc", 180, 0.5), ("line", 3)], (0.0, -0.5), 0.0, 1.0)
        self.assertAlmostEqual(core.strip_area(pieces, 1.0), math.pi * 1.0 + 3.0)

    def test_neutral_length_uses_the_k_factor(self):
        pieces, _ = core.walk([("line", 48), ("arc", 90, R), ("line", 48)], (0, 0), 0, T)
        self.assertAlmostEqual(core.neutral_length(pieces, T, K), 96 + BA90)

    def test_outline_closes(self):
        pieces, _ = core.walk([("arc", 180, 0.25), ("line", 2)], (0, -0.5), 0, 1.0)
        loop = core.outline(pieces, 1.0)

        def ends(p):
            if p["kind"] == "line":
                return p["a"], p["b"]
            return core.arc_point(p, 0), core.arc_point(p, 1)

        for a, b in zip(loop, loop[1:] + loop[:1]):
            self.assertAlmostEqual(ends(a)[1][0], ends(b)[0][0])
            self.assertAlmostEqual(ends(a)[1][1], ends(b)[0][1])


class HemTests(unittest.TestCase):
    def values(self, kind, **extra):
        v = core.hem_defaults(T)
        v["type"] = kind
        v.update(extra)
        return v

    def test_every_type_builds(self):
        for kind in core.HEM_TYPES:
            pieces, x0, inner = core.hem_profile(self.values(kind), T, R)
            self.assertTrue(pieces, kind)
            self.assertLessEqual(x0, 0.0)

    def test_inside_keeps_the_outside_at_the_edge(self):
        _p, x0, inner = core.hem_profile(self.values("open"), T, R)
        self.assertAlmostEqual(inner, 0.25)  # gap 0.5 T: inner radius gap / 2
        self.assertAlmostEqual(x0, -(inner + T))
        self.assertAlmostEqual(core.hem_start("outside", inner, T), -inner)
        self.assertEqual(core.hem_start("adjacent", inner, T), 0.0)

    def test_open_hem_leg_lies_gap_above_the_sheet(self):
        segs, inner = core.hem_segments(self.values("open", gap=0.6, length=5), T, R)
        pieces, end = core.walk(segs, (0, -T / 2), 0, T)
        # back over the sheet: heading 180, its underside gap above the sheet's top (y = 0)
        self.assertAlmostEqual(end[2], 180.0)
        self.assertAlmostEqual(end[1] - T / 2, 0.6)
        # the return reaches Length back from the hem's outside
        self.assertAlmostEqual((inner + T) - end[0], 5.0)

    def test_teardrop_comes_down_to_the_gap(self):
        segs, _inner = core.hem_segments(self.values("teardrop", gap=0.5, length=4), T, R)
        self.assertGreater(segs[0][1], 180.0)
        pieces, end = core.walk(segs, (0, -T / 2), 0, T)
        lowest = end[1] - abs(math.cos(math.radians(end[2]))) * T / 2
        self.assertAlmostEqual(lowest, 0.5, places=6)

    def test_rope_ends_flat_at_the_gap(self):
        segs, _inner = core.hem_segments(self.values("rope", gap=0.5), T, R)
        _pieces, end = core.walk(segs, (0, -T / 2), 0, T)
        self.assertAlmostEqual(end[2] % 360.0, 180.0, places=6)
        self.assertAlmostEqual(end[1] - T / 2, 0.5, places=6)

    def test_flat_hem_keeps_a_hairline(self):
        segs, inner = core.hem_segments(self.values("flat"), T, R)
        self.assertAlmostEqual(inner, core.FLAT_GAP / 2)

    def test_refusals_say_why(self):
        bad = [
            ("open", {"gap": 0}),
            ("open", {"length": 1.0}),
            ("rolled", {"angle": 400}),
            ("teardrop", {"gap": 5.0}),
            ("rope", {"gap": 5.0}),
            ("double", {"setback": 10.0}),
        ]
        for kind, extra in bad:
            with self.assertRaises(ValueError, msg=kind):
                core.hem_segments(self.values(kind, **extra), T, R)


class JoinTests(unittest.TestCase):
    def test_right_angle_bend(self):
        ta, tb, centre, deg = core.fillet_2d((0, 0), (1, 0), (0, 1), 1.5)
        self.assertAlmostEqual(deg, 90.0)
        self.assertAlmostEqual(ta[0], 1.5)
        self.assertAlmostEqual(tb[1], 1.5)
        self.assertAlmostEqual(centre[0], 1.5)
        self.assertAlmostEqual(centre[1], 1.5)

    def test_parallel_refused(self):
        with self.assertRaises(ValueError):
            core.fillet_2d((0, 0), (1, 0), (1, 0), 1.0)
        self.assertIsNone(core.line_intersection((0, 0), (1, 0), (0, 1), (1, 0)))

    def test_line_intersection(self):
        s, t = core.line_intersection((0, 0), (1, 0), (5, -2), (0, 1))
        self.assertAlmostEqual(s, 5.0)
        self.assertAlmostEqual(t, 2.0)


class ClosureTests(unittest.TestCase):
    def test_reaches(self):
        self.assertAlmostEqual(core.closure_reach("symmetric", 1.0, T), 0.5)
        self.assertAlmostEqual(core.closure_reach("overlap", 0.0, T, 1.0, True), 0.0)
        self.assertAlmostEqual(core.closure_reach("overlap", 0.2, T, 0.5, True), 0.5)
        self.assertAlmostEqual(core.closure_reach("overlap", 0.2, T, 1.0, False), 1.2)
        with self.assertRaises(ValueError):
            core.closure_reach("overlap", 0.0, T, 1.5)

    # two 90 degree bends meeting at a square corner, flat: bend A runs along y (centre line
    # x = 10), bend B along x (centre line y = 20), both zones BA wide, flanges outward
    BEND_A = ((10.0, 0.0), (0.0, 1.0), (1.0, 0.0), BA90 / 2)
    BEND_B = ((0.0, 20.0), (1.0, 0.0), (0.0, 1.0), BA90 / 2)

    def test_relief_placements(self):
        x, y = core.relief_centre("intersection", self.BEND_A, self.BEND_B, 4.0)
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 20.0)
        # Vertex: where both bends start (the inner corner of the stationary side)
        x, y = core.relief_centre("vertex", self.BEND_A, self.BEND_B, 4.0, "square")
        self.assertAlmostEqual(x, 10.0 - BA90 / 2)
        self.assertAlmostEqual(y, 20.0 - BA90 / 2)
        # Tangent: the circle (radius 2) touches the far side of both zones
        x, y = core.relief_centre("tangent", self.BEND_A, self.BEND_B, 4.0)
        self.assertAlmostEqual(x + 2.0, 10.0 + BA90 / 2)
        self.assertAlmostEqual(y + 2.0, 20.0 + BA90 / 2)

    def test_relief_placement_refusals(self):
        with self.assertRaises(ValueError):
            core.relief_centre("tangent", self.BEND_A, self.BEND_B, 4.0, "square")
        with self.assertRaises(ValueError):
            core.relief_centre("middle", self.BEND_A, self.BEND_B, 4.0)
        with self.assertRaises(ValueError):
            core.relief_centre("intersection", self.BEND_A, self.BEND_A, 4.0)


class FacetTests(unittest.TestCase):
    def test_controls(self):
        self.assertEqual(core.facets_for_arc(15, 90, "facet_number", 6), 6)
        self.assertEqual(core.facets_for_arc(15, 90, "facet_angle", 10), 5)
        # chord 2 r sin(a / 2n) <= 5 mm on r 20, 90 degrees: 7 facets
        self.assertEqual(core.facets_for_arc(20, 90, "facet_distance", 5), 7)
        n = core.facets_for_arc(15, 360, "chord_tolerance", 0.1)
        sag = 15 * (1 - math.cos(math.radians(360.0 / n) / 2))
        self.assertLessEqual(sag, 0.1 + 1e-9)
        self.assertGreater(15 * (1 - math.cos(math.radians(360.0 / (n - 1)) / 2)), 0.1)

    def test_bad_values_refused(self):
        for control in ("facet_angle", "facet_distance", "chord_tolerance"):
            with self.assertRaises(ValueError):
                core.facets_for_arc(15, 90, control, 0)


class TriangulateTests(unittest.TestCase):
    def test_square_to_circle_fans_from_corners(self):
        # square corners at 1/8, 3/8, 5/8, 7/8 of a turn, 16 circle points
        t1 = [0.0, 0.25, 0.5, 0.75]
        t2 = [i / 16.0 for i in range(16)]
        tris = core.triangulate(t1, t2, True)
        self.assertEqual(len(tris), 4 + 16)  # one per square side + one per circle chord
        per_corner = {}
        for tri in tris:
            corners = [k for k in tri if k < 4]
            if len(corners) == 1:
                per_corner[corners[0]] = per_corner.get(corners[0], 0) + 1
        self.assertEqual(sorted(per_corner.values()), [4, 4, 4, 4])  # a fan of 4 at each

    def test_equal_counts_give_quads(self):
        tris = core.triangulate([0.0, 0.5], [0.0, 0.5], True)
        self.assertEqual(len(tris), 4)
        used = sorted(set(k for tri in tris for k in tri))
        self.assertEqual(used, [0, 1, 2, 3])

    def test_open_strip(self):
        tris = core.triangulate([0.0, 1.0], [0.0, 0.5, 1.0], False)
        self.assertEqual(len(tris), 3)


class ThicknessEdgeTests(unittest.TestCase):
    def test_only_through_the_sheet(self):
        self.assertTrue(core.is_thickness_edge((0, 0, 1), (0, 0, 1), 1.0, 1.0))
        self.assertFalse(core.is_thickness_edge((1, 0, 0), (0, 0, 1), 1.0, 1.0))
        self.assertFalse(core.is_thickness_edge((0, 0, 1), (0, 0, 1), 5.0, 1.0))


if __name__ == "__main__":
    unittest.main()
