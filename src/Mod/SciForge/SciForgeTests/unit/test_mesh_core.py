# SPDX-License-Identifier: LGPL-2.1-or-later
"""The MESH tab's maths and mesh algorithms (sciforge/mesh_core.py). Runs without FreeCAD."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import mesh_core as mc  # noqa: E402


def box(x0=0.0, y0=0.0, z0=0.0, x1=20.0, y1=10.0, z1=5.0):
    """A closed box, facets facing out (12 triangles)."""
    pts = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    facets = []
    for a, b, c, d in quads:
        facets += [(a, b, c), (a, c, d)]
    return pts, facets


def sphere(r=10.0, n=16):
    """A closed UV sphere, facets facing out."""
    pts = [(0.0, 0.0, r)]
    m = 2 * n
    for i in range(1, n):
        th = math.pi * i / n
        for j in range(m):
            ph = 2 * math.pi * j / m
            pts.append(
                (r * math.sin(th) * math.cos(ph), r * math.sin(th) * math.sin(ph), r * math.cos(th))
            )
    pts.append((0.0, 0.0, -r))
    facets = [(0, 1 + j, 1 + (j + 1) % m) for j in range(m)]
    for i in range(n - 2):
        for j in range(m):
            a = 1 + i * m + j
            b = 1 + i * m + (j + 1) % m
            c = 1 + (i + 1) * m + j
            d = 1 + (i + 1) * m + (j + 1) % m
            facets += [(a, c, d), (a, d, b)]
    last = len(pts) - 1
    base = 1 + (n - 2) * m
    facets += [(last, base + (j + 1) % m, base + j) for j in range(m)]
    return pts, facets


def closed(facets):
    return not mc.boundary_edges(facets) and not mc.non_manifold_edges(facets)


class ChoicesTests(unittest.TestCase):
    def test_fusion_orders_and_defaults(self):
        self.assertEqual(mc.REPAIR_TYPES, ["Close Holes", "Stitch and Remove", "Wrap", "Rebuild"])
        self.assertEqual(mc.DEFAULT_REPAIR, "Stitch and Remove")
        self.assertEqual(mc.REBUILD_TYPES, ["Fast", "Preserve Sharp Edges", "Accurate", "Blocky"])
        self.assertEqual(mc.REBUILD_DENSITY, (8, 256, 128))
        self.assertEqual(mc.REMESH_TYPES, ["Adaptive", "Uniform"])
        self.assertEqual((mc.REMESH_DENSITY, mc.SHAPE_PRESERVATION), (0.25, 0.5))
        self.assertEqual(mc.REDUCE_TARGETS, ["Tolerance", "Proportion", "Face Count"])
        self.assertEqual(mc.CUT_TYPES, ["Trim", "Split Body", "Split Faces"])
        self.assertEqual(mc.FILL_TYPES, ["No Fill", "Uniform", "Minimal"])
        self.assertEqual(
            mc.SEPARATE_TYPES, ["Mesh Shells", "All Face Groups", "Select Face Groups"]
        )
        self.assertEqual(mc.COMBINE_OPERATIONS, ["Join", "Cut", "Intersect", "Merge"])
        self.assertAlmostEqual(mc.ANGLE_THRESHOLD, 24.98, places=1)

    def test_reduce_targets(self):
        self.assertIsNone(mc.reduce_target_count(1000, "Tolerance"))
        self.assertEqual(mc.reduce_target_count(1000, "Proportion", 25), 250)
        self.assertEqual(mc.reduce_target_count(1000, "Face Count", face_count=300), 300)
        self.assertEqual(mc.reduce_target_count(1000, "Face Count"), 500)

    def test_reduce_refusals_say_why(self):
        with self.assertRaises(mc.MeshError) as ctx:
            mc.reduce_target_count(1000, "Face Count", face_count=2)
        self.assertIn("at least 4", str(ctx.exception))
        with self.assertRaises(mc.MeshError) as ctx:
            mc.reduce_target_count(1000, "Face Count", face_count=1000)
        self.assertIn("fewer", str(ctx.exception))
        with self.assertRaises(mc.MeshError):
            mc.reduce_target_count(1000, "Sideways")

    def test_tolerance_and_density_mappings(self):
        self.assertAlmostEqual(mc.quadric_tolerance(0.1), 0.01)
        with self.assertRaises(mc.MeshError):
            mc.quadric_tolerance(0)
        coarse = mc.remesh_edge_length(100.0, 0.0)
        default = mc.remesh_edge_length(100.0, 0.25)
        fine = mc.remesh_edge_length(100.0, 1.0)
        self.assertAlmostEqual(coarse, 10.0)
        self.assertAlmostEqual(fine, 0.1)
        self.assertTrue(coarse > default > fine)
        self.assertEqual(mc.remesh_face_count(100.0, 0.0), 0)
        self.assertGreater(mc.remesh_face_count(100.0, 1.0), 200)

    def test_smoothness_and_rebuild_cells(self):
        self.assertEqual(mc.smooth_iterations(0), 0)
        self.assertEqual(mc.smooth_iterations(0.02), 2)
        self.assertEqual(mc.smooth_iterations(1.0), 60)
        self.assertEqual(mc.smooth_iterations(7), 60)
        self.assertAlmostEqual(mc.rebuild_cell(256.0, 128), 2.0)
        self.assertAlmostEqual(mc.rebuild_cell(256.0, 1000), 1.0)  # clamped to 256
        self.assertAlmostEqual(mc.rebuild_cell(256.0, 2), 32.0)  # clamped to 8
        with self.assertRaises(mc.MeshError):
            mc.rebuild_cell(0.0, 128)

    def test_erase_fill_area(self):
        self.assertAlmostEqual(mc.erase_fill_area(1.0, 0.0), 4.0)
        self.assertAlmostEqual(mc.erase_fill_area(1.0, 1.0), 4.0 / 64.0)
        self.assertGreater(mc.erase_fill_area(1.0, 0.25), mc.erase_fill_area(1.0, 0.75))


class TopologyTests(unittest.TestCase):
    def test_closed_box(self):
        pts, facets = box()
        self.assertTrue(closed(facets))
        self.assertEqual(mc.boundary_loops(facets), [])
        self.assertEqual(mc.orientation_conflicts(facets), 0)
        self.assertAlmostEqual(mc.signed_volume(pts, facets), 1000.0)

    def test_hole_found_as_one_loop(self):
        _pts, facets = box()
        loops = mc.boundary_loops(facets[2:])  # the bottom's two triangles gone
        self.assertEqual(len(loops), 1)
        self.assertEqual(sorted(loops[0]), [0, 1, 2, 3])

    def test_bow_tie_gives_two_loops(self):
        # two triangles touching at point 0 only: two open loops through one point
        facets = [(0, 1, 2), (0, 3, 4)]
        loops = mc.boundary_loops(facets)
        self.assertEqual(len(loops), 2)
        self.assertEqual(sorted(len(loop) for loop in loops), [3, 3])

    def test_flipped_facet_is_a_conflict(self):
        _pts, facets = box()
        facets = mc.flip(facets, [3])
        self.assertEqual(mc.orientation_conflicts(facets), 3)

    def test_components_biggest_first(self):
        _pts, facets = box()
        small = [(a + 8, b + 8, c + 8) for a, b, c in facets[:6]]
        found = mc.components(small + facets)
        self.assertEqual([len(c) for c in found], [12, 6])

    def test_non_manifold_edge(self):
        facets = [(0, 1, 2), (1, 0, 3), (0, 1, 4)]
        self.assertEqual(mc.non_manifold_edges(facets), [(0, 1)])

    def test_compact_and_degenerate(self):
        pts = [(0, 0, 0), (9, 9, 9), (1, 0, 0), (0, 1, 0)]
        new_pts, new_facets = mc.compact(pts, [(0, 2, 3)])
        self.assertEqual(new_pts, [(0, 0, 0), (1, 0, 0), (0, 1, 0)])
        self.assertEqual(new_facets, [(0, 1, 2)])
        self.assertEqual(mc.drop_degenerate([(0, 1, 1), (0, 1, 2), (2, 0, 1)]), [(0, 1, 2)])


class RepairHelperTests(unittest.TestCase):
    def test_weld_closes_a_triangle_soup(self):
        pts, facets = box()
        soup, soup_facets = [], []
        for a, b, c in facets:
            i = len(soup)
            soup += [pts[a], pts[b], pts[c]]
            soup_facets.append((i, i + 1, i + 2))
        self.assertEqual(len(mc.boundary_edges(soup_facets)), 36)
        welded, merged = mc.weld_open_edges(soup, soup_facets, 1e-6)
        self.assertEqual(merged, 28)
        self.assertTrue(closed(welded))

    def test_weld_closes_a_crack_within_tolerance(self):
        pts, facets = box()
        # the top's corner 6 is doubled 0.004 away and used by one triangle: a crack
        pts = pts + [(20.004, 10.0, 5.0)]
        facets = [f if f != (4, 5, 6) else (4, 5, 8) for f in facets]
        self.assertTrue(mc.boundary_edges(facets))
        welded, _merged = mc.weld_open_edges(pts, facets, 0.01)
        self.assertTrue(closed(welded))
        unchanged, merged = mc.weld_open_edges(pts, facets, 0.001)
        self.assertEqual(merged, 0)
        self.assertFalse(closed(unchanged))

    def test_analysis_lines_and_advice(self):
        lines = mc.analysis_lines({"holes": 2, "flipped": 1, "shells": 3, "duplicated": 0})
        self.assertEqual(lines, ["2 holes", "1 flipped face", "3 separate shells"])
        self.assertEqual(mc.analysis_lines({"shells": 1}), [])
        self.assertEqual(
            mc.analysis_lines({"inside_out": True}), ["inside out (the faces point inward)"]
        )
        self.assertIn("closed", mc.repair_advice({"closed": True}, "Close Holes"))
        self.assertIn("try Wrap", mc.repair_advice({"holes": 1}, "Close Holes"))
        self.assertIn("1 hole left", mc.repair_advice({"holes": 1}, "Stitch and Remove"))
        self.assertIn("try Rebuild", mc.repair_advice({"holes": 3}, "Wrap"))
        self.assertIn("cannot be repaired", mc.repair_advice({"holes": 3}, "Rebuild"))


class RefineTests(unittest.TestCase):
    def test_split_long_edges_keeps_a_closed_mesh_closed(self):
        pts, facets = box()
        new_pts, new_facets, done = mc.split_long_edges(pts, facets, 3.0)
        self.assertTrue(done)
        self.assertTrue(closed(new_facets))
        self.assertAlmostEqual(mc.signed_volume(new_pts, new_facets), 1000.0)
        longest = max(
            mc.length(mc.sub(new_pts[u], new_pts[v])) for u, v in mc.edge_facets(new_facets)
        )
        self.assertLessEqual(longest, 3.0 + 1e-9)

    def test_split_stops_at_the_limit(self):
        pts, facets = box()
        _p, new_facets, done = mc.split_long_edges(pts, facets, 0.01, max_facets=100)
        self.assertFalse(done)
        self.assertTrue(closed(new_facets))

    def test_split_needs_a_length(self):
        pts, facets = box()
        with self.assertRaises(mc.MeshError):
            mc.split_long_edges(pts, facets, 0.0)


class FaceGroupTests(unittest.TestCase):
    def test_box_has_six_groups(self):
        pts, facets = box()
        groups = mc.face_groups(pts, facets)
        self.assertEqual(mc.group_count(groups), 6)
        for i in range(0, 12, 2):
            self.assertEqual(groups[i], groups[i + 1])  # a side's two triangles together

    def test_sphere_is_one_group(self):
        pts, facets = sphere()
        self.assertEqual(mc.group_count(mc.face_groups(pts, facets)), 1)

    def test_small_groups_join_a_neighbour(self):
        # a 20 x 10 x 0.05 plate: its four thin sides are each under 2 % of the area
        pts, facets = box(z1=0.05)
        groups = mc.face_groups(pts, facets, min_size=0.02)
        self.assertEqual(mc.group_count(groups), 2)
        self.assertEqual(mc.group_count(mc.face_groups(pts, facets, min_size=0.0)), 6)

    def test_a_low_angle_makes_more_groups(self):
        pts, facets = sphere()
        self.assertGreater(mc.group_count(mc.face_groups(pts, facets, angle=1.0, min_size=0)), 1)

    def test_colours_one_per_facet(self):
        colours = mc.group_colors([0, 0, 1, 2])
        self.assertEqual(len(colours), 4)
        self.assertEqual(colours[0], colours[1])
        self.assertNotEqual(colours[0], colours[2])
        for c in colours:
            self.assertTrue(all(0.0 <= v <= 1.0 for v in c))


class PlaneTests(unittest.TestCase):
    def test_basis_is_orthonormal_and_right_handed(self):
        for normal in [(0, 0, 1), (0, 1, 0), (1, 0, 0), (1, 2, 3), (0, 0, -1)]:
            u, v = mc.plane_basis(normal)
            n = mc.unit(normal)
            self.assertAlmostEqual(mc.dot(u, v), 0.0)
            self.assertAlmostEqual(mc.dot(u, n), 0.0)
            self.assertAlmostEqual(mc.length(u), 1.0)
            w = mc.cross(u, v)
            for a in range(3):
                self.assertAlmostEqual(w[a], n[a])

    def test_rotate(self):
        r = mc.rotate((1, 0, 0), (0, 0, 1), 90)
        self.assertAlmostEqual(r[0], 0.0)
        self.assertAlmostEqual(r[1], 1.0)

    def test_nesting_hole_and_island(self):
        outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
        hole = [(10, 10), (10, 90), (90, 90), (90, 10)]
        island = [(40, 40), (60, 40), (60, 60), (40, 60)]
        other = [(200, 0), (210, 0), (210, 10), (200, 10)]
        regions = sorted(mc.nest_loops_2d([outer, hole, island, other]))
        self.assertEqual(regions, [(0, [1]), (2, []), (3, [])])

    def test_point_in_polygon(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(mc.point_in_polygon_2d((5, 5), square))
        self.assertFalse(mc.point_in_polygon_2d((15, 5), square))
        self.assertAlmostEqual(mc.signed_area_2d(square), 100.0)

    def test_segment_hits_and_fan_split(self):
        segments = [((0, 0), (10, 0)), ((10, 0), (10, 10))]
        points = [(2.5, 0.0), (7.5, 1e-9), (5, 5), (10, 4)]
        hits = mc.segment_hits(points, segments, 1e-6)
        self.assertEqual(hits, {0: [(0.25, 0), (0.75, 1)], 1: [(0.4, 3)]})
        # facet (0, 1, 2) with the points 7, 8 put on its edge 0 -> 1
        self.assertEqual(mc.fan_split((2, 0, 1), (0, 1), [7, 8]), [(0, 7, 2), (7, 8, 2), (8, 1, 2)])
        with self.assertRaises(mc.MeshError):
            mc.fan_split((0, 1, 2), (1, 0), [7])


def polyline_length(line):
    return sum(mc.length(mc.sub(a, b)) for a, b in zip(line, line[1:]))


class SectionTests(unittest.TestCase):
    def section(self, pts, facets, z, normal=(0, 0, 1)):
        segments = mc.plane_section_segments(pts, facets, (0, 0, z), normal, 1e-9)
        return mc.chain_segments(segments, 1e-7)

    def test_box_through_the_middle(self):
        lines = self.section(*box(), 2.5)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0][0], lines[0][-1])  # closed
        self.assertAlmostEqual(polyline_length(lines[0]), 60.0)

    def test_flat_bottom_gives_its_outline_either_way(self):
        for normal in [(0, 0, 1), (0, 0, -1)]:
            lines = self.section(*box(), 0.0, normal)
            self.assertEqual(len(lines), 1, normal)
            self.assertAlmostEqual(polyline_length(lines[0]), 60.0)  # no diagonals

    def test_ring_of_corners_on_the_plane_is_not_doubled(self):
        pts, facets = sphere(10.0, 16)  # a ring of 32 corners at z = 0
        lines = self.section(pts, facets, 0.0)
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(polyline_length(lines[0]), 32 * 20.0 * math.sin(math.pi / 32))

    def test_touching_gives_nothing(self):
        self.assertEqual(self.section(*box(), 9.0), [])  # above the box
        # two faces meeting at an edge that lies on the plane, both above it (a ridge)
        pts = [(0, 0, 0), (1, 0, 0), (0.5, 1, 1), (0.5, -1, 1)]
        self.assertEqual(self.section(pts, [(0, 1, 2), (1, 0, 3)], 0.0), [])

    def test_a_face_on_the_plane_gives_its_outline(self):
        lines = self.section(*box(), 5.0)  # the plane on the top face
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(polyline_length(lines[0]), 60.0)

    def test_two_bodies_two_lines(self):
        a_pts, a_facets = box()
        b_pts, b_facets = box(30, 0, 0, 40, 10, 5)
        pts = a_pts + b_pts
        facets = a_facets + [tuple(i + len(a_pts) for i in f) for f in b_facets]
        lines = self.section(pts, facets, 1.0)
        self.assertEqual(len(lines), 2)
        self.assertEqual(sorted(round(polyline_length(x), 6) for x in lines), [40.0, 60.0])

    def test_chain_open_line_and_doubled_segment(self):
        segments = [
            ((0, 0, 0), (1, 0, 0)),
            ((1, 0, 0), (2, 0, 0)),
            ((2, 0, 0), (1, 0, 0)),  # the same segment met again
        ]
        lines = mc.chain_segments(segments, 1e-6)
        self.assertEqual(len(lines), 1)
        self.assertEqual(sorted([lines[0][0], lines[0][-1]]), [(0, 0, 0), (2, 0, 0)])
        self.assertEqual(len(lines[0]), 3)


class HelperTests(unittest.TestCase):
    def test_offset_box_out_and_in(self):
        pts, facets = box()
        out = mc.offset_points(pts, facets, 1.0)
        self.assertAlmostEqual(mc.signed_volume(out, facets), 22 * 12 * 7, places=2)
        inner = mc.offset_points(pts, facets, -1.0)
        self.assertAlmostEqual(mc.signed_volume(inner, facets), 18 * 8 * 3, places=2)

    def test_fill_loop_closes_a_hole(self):
        pts, facets = box()
        open_facets = [f for f in facets if not all(pts[i][2] == 5.0 for i in f)]  # no top
        loops = mc.boundary_loops(open_facets)
        self.assertEqual(len(loops), 1)
        patch = mc.fill_loop(pts, loops[0])
        self.assertTrue(closed(open_facets + patch))
        self.assertAlmostEqual(mc.signed_volume(pts, open_facets + patch), 1000.0)

    def test_triangulate_l_shape(self):
        poly = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]
        tris = mc.triangulate_polygon_2d(poly)
        self.assertEqual(len(tris), 4)
        area = sum(mc.signed_area_2d([poly[a], poly[b], poly[c]]) for a, b, c in tris)
        self.assertAlmostEqual(area, 3.0)

    def test_simplify_polyline(self):
        line = [(float(x), 1e-6 * (x % 2), 0.0) for x in range(11)]
        self.assertEqual(mc.simplify_polyline(line, 1e-3), [line[0], line[-1]])
        square = [(0, 0, 0), (5, 0, 0), (10, 0, 0), (10, 5, 0), (10, 10, 0), (0, 10, 0)]
        self.assertEqual(
            sorted(mc.simplify_polyline(square, 1e-6, closed=True)),
            sorted([(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]),
        )

    def test_find_facets_by_centre(self):
        pts, facets = box()
        picks = [mc.centroid(pts, facets[3]), mc.centroid(pts, facets[7]), (99.0, 99.0, 99.0)]
        found, lost = mc.find_facets(pts, facets, picks, 1e-6)
        self.assertEqual(sorted(found), [3, 7])
        self.assertEqual(lost, 1)

    def test_brush_takes_the_faces_nearby(self):
        pts, facets = sphere(10.0, 16)
        few = mc.facets_near(pts, facets, 0, 2.0)
        self.assertIn(0, few)
        self.assertLess(len(few), len(facets) // 10)
        self.assertEqual(len(mc.facets_near(pts, facets, 0, 100.0)), len(facets))

    def test_match_points_2d(self):
        targets = [(0.0, 0.0), (1.0, 0.0)]
        self.assertEqual(mc.match_points_2d(targets, [(1.0000001, 0.0), (5.0, 5.0)], 1e-4), {0: 1})


class RebuildTests(unittest.TestCase):
    def test_blocky_box_is_exact(self):
        pts, facets = box()
        new_pts, new_facets = mc.rebuild(pts, facets, 32, "Blocky")
        self.assertTrue(closed(new_facets))
        self.assertAlmostEqual(mc.signed_volume(new_pts, new_facets), 1000.0, places=6)
        self.assertEqual(mc.orientation_conflicts(new_facets), 0)

    def test_sharp_edges_keep_the_corners(self):
        pts, facets = box()
        new_pts, new_facets = mc.rebuild(pts, facets, 32, "Preserve Sharp Edges")
        self.assertTrue(closed(new_facets))
        self.assertAlmostEqual(mc.signed_volume(new_pts, new_facets), 1000.0, delta=2.0)
        lo, hi = mc.bounds(new_pts)
        for a, b in zip(lo + hi, (0, 0, 0, 20, 10, 5)):
            self.assertAlmostEqual(a, b, places=6)

    def test_rebuild_closes_a_hole(self):
        pts, facets = box()
        new_pts, new_facets = mc.rebuild(pts, facets[2:], 32, "Accurate")
        self.assertTrue(closed(new_facets))
        self.assertAlmostEqual(mc.signed_volume(new_pts, new_facets), 1000.0, delta=20.0)

    def test_inside_out_mesh_still_has_an_inside(self):
        pts, facets = box()
        new_pts, new_facets = mc.rebuild(pts, mc.flip(facets), 32, "Fast")
        self.assertGreater(mc.signed_volume(new_pts, new_facets), 900.0)

    def test_sphere_rebuilds_round(self):
        pts, facets = sphere(10.0, 20)
        new_pts, new_facets = mc.rebuild(pts, facets, 40, "Accurate")
        self.assertTrue(closed(new_facets))
        volume = mc.signed_volume(new_pts, new_facets)
        self.assertAlmostEqual(volume, mc.signed_volume(pts, facets), delta=60.0)

    def test_a_flat_surface_has_no_inside(self):
        facets = [(0, 1, 2), (0, 2, 3)]
        pts = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
        with self.assertRaises(mc.MeshError) as ctx:
            mc.rebuild(pts, facets, 32, "Fast")
        self.assertIn("no volume", str(ctx.exception))

    def test_too_many_cells_refused(self):
        pts, facets = box(x1=1000.0, y1=1000.0, z1=1000.0)
        grid = mc.Grid((0, 0, 0), (1000, 1000, 1000), 1000.0 / 400)
        with self.assertRaises(mc.MeshError):
            mc.solid_cells(pts, facets, grid)


if __name__ == "__main__":
    unittest.main()
