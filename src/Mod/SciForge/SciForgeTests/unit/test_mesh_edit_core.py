# SPDX-License-Identifier: LGPL-2.1-or-later
"""Direct Edit of a mesh body, Create / Combine Face Groups (sciforge/mesh_edit_core.py).
Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import mesh_core as mc  # noqa: E402
from sciforge import mesh_edit_core as ec  # noqa: E402
from SciForgeTests.unit.test_mesh_core import box, closed, sphere  # noqa: E402


def grid(n=6, size=10.0):
    """A flat open sheet of n x n squares (2 triangles each) at z = 0, facing +Z."""
    step = size / n
    pts = [(i * step, j * step, 0.0) for j in range(n + 1) for i in range(n + 1)]
    facets = []
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            b, c, d = a + 1, a + n + 2, a + n + 1
            facets += [(a, b, c), (a, c, d)]
    return pts, facets


def top_facets(points, facets, z):
    return [i for i, f in enumerate(facets) if all(abs(points[p][2] - z) < 1e-9 for p in f)]


class EditTextTests(unittest.TestCase):
    def test_round_trip_and_description(self):
        edit = ec.make_edit("move", [(1.0, 2.0, 3.0)], vector=(0.0, 0.0, 2.5))
        back = ec.decode(ec.encode(edit))
        self.assertEqual(back["op"], "move")
        self.assertEqual(back["picks"], [(1.0, 2.0, 3.0)])
        self.assertEqual(back["vector"], [0.0, 0.0, 2.5])
        self.assertEqual(ec.describe(back), "Move: 1 face, 0, 0, 2.5 mm")
        fill = ec.make_edit("erase_fill", [(0, 0, 0), (1, 1, 1)], fill="Sideways")
        self.assertEqual(fill["fill"], "Uniform")
        self.assertEqual(ec.describe(fill), "Erase and Fill: 2 faces, Uniform")

    def test_unreadable_text_is_none(self):
        self.assertIsNone(ec.decode("not json"))
        self.assertIsNone(ec.decode('{"op": "explode", "picks": []}'))
        self.assertIsNone(ec.decode("[1, 2]"))
        with self.assertRaises(mc.MeshError):
            ec.make_edit("explode", [])

    def test_palette_choices(self):
        self.assertEqual(ec.SELECTION_TYPES, ["Paint", "Window", "Free Form"])
        self.assertEqual(ec.DEFAULT_SELECTION, "Paint")
        self.assertEqual(ec.SELECT_FILTERS, ["Faces", "Face Groups"])
        self.assertAlmostEqual(ec.DEFAULT_SMOOTHNESS, 0.02)


class OperationTests(unittest.TestCase):
    def test_delete_leaves_a_hole(self):
        pts, facets = box()
        state = ec.EditState(pts, facets)
        ec.delete_facets(state, [2, 3])  # the two triangles of the top
        self.assertEqual(len(state.facets), 10)
        self.assertEqual(len(mc.boundary_loops(state.facets)), 1)
        self.assertEqual(len(state.groups), 10)
        with self.assertRaises(mc.MeshError):
            ec.delete_facets(state, range(len(state.facets)))

    def test_erase_and_fill_closes_the_gap(self):
        pts, facets = sphere(10.0, 12)
        state = ec.EditState(pts, facets)
        top = [i for i, f in enumerate(facets) if 0 in f]  # the faces round the north pole
        before = mc.signed_volume(state.points, state.facets)
        ec.erase_and_fill(state, top, "Minimal")
        self.assertTrue(closed(state.facets))
        self.assertLess(len(state.facets), len(facets))
        after = mc.signed_volume(state.points, state.facets)
        self.assertGreater(after, 0.0)
        self.assertAlmostEqual(after, before, delta=0.05 * before)
        uniform = ec.EditState(pts, facets)
        ec.erase_and_fill(uniform, top, "Uniform", 1.0)
        self.assertTrue(closed(uniform.facets))
        self.assertGreater(len(uniform.facets), len(state.facets))

    def test_erase_keeps_old_holes_and_groups(self):
        pts, facets = grid(6)
        state = ec.EditState(pts, facets, [0] * 36 + [1] * 36)
        middle = [i for i, f in enumerate(facets) if all(2.0 < pts[p][0] < 8.0 for p in f)]
        middle = [i for i in middle if all(2.0 < pts[p][1] < 8.0 for p in facets[i])]
        ec.erase_and_fill(state, middle, "Minimal")
        # the sheet's own rim is still open, the erased hole is closed
        self.assertEqual(len(mc.boundary_loops(state.facets)), 1)
        self.assertEqual(len(state.groups), len(state.facets))

    def test_reverse_and_group(self):
        pts, facets = box()
        state = ec.EditState(pts, facets)
        ec.reverse_facets(state, [0])
        self.assertEqual(state.facets[0], (facets[0][0], facets[0][2], facets[0][1]))
        number = ec.new_group(state, [0, 1])
        self.assertEqual(number, 1)
        self.assertEqual(state.groups[:3], [1, 1, 0])
        self.assertEqual(mc.group_count(state.result_groups()), 2)
        again = ec.new_group(state, [4])
        self.assertEqual(again, 2)
        self.assertEqual(ec.EditState(pts, facets).result_groups(), [])

    def test_move_stretches_the_neighbours(self):
        pts, facets = box()
        state = ec.EditState(pts, facets)
        top = top_facets(pts, facets, 5.0)
        ec.move_facets(state, top, (0.0, 0.0, 2.0))
        zs = sorted({round(p[2], 9) for p in state.points})
        self.assertEqual(zs, [0.0, 7.0])
        self.assertTrue(closed(state.facets))
        self.assertAlmostEqual(mc.signed_volume(state.points, state.facets), 20 * 10 * 7)

    def test_smooth_region_keeps_its_rim(self):
        pts, facets = grid(8)
        bumped = list(pts)
        centre = 4 * 9 + 4  # the middle point
        bumped[centre] = (bumped[centre][0], bumped[centre][1], 3.0)
        state = ec.EditState(bumped, facets)
        region = [i for i, f in enumerate(facets) if any(p == centre for p in f)]
        region = ec.grow(facets, region)
        rim = ec.boundary_points(facets, region)
        before = {i: state.points[i] for i in rim}
        moved = ec.smooth_facets(state, region, 0.5)
        self.assertGreater(moved, 0)
        self.assertLess(state.points[centre][2], 1.0)
        for i, p in before.items():
            self.assertEqual(state.points[i], p)
        with self.assertRaises(mc.MeshError):
            ec.smooth_facets(ec.EditState(pts, facets), [0], 0.5)

    def test_replay_finds_picks_and_reports_lost(self):
        pts, facets = box()
        state = ec.EditState(pts, facets)
        top = top_facets(pts, facets, 5.0)
        edits = [
            ec.make_edit("move", state.centres(top), vector=(0.0, 0.0, 1.0)),
            ec.make_edit("group", ec.EditState(pts, facets).centres(top)),  # pre-move centres
        ]
        lost, skipped = ec.replay(state, edits)
        self.assertEqual(skipped, [])
        self.assertEqual(lost, 2)  # the moved faces are no longer where the 2nd edit looks
        self.assertEqual(max(p[2] for p in state.points), 6.0)


class SelectionTests(unittest.TestCase):
    def test_grow_shrink_invert(self):
        pts, facets = grid(6)
        seed = [30]
        grown = ec.grow(facets, seed)
        self.assertGreater(len(grown), 3)
        self.assertIn(30, grown)
        self.assertEqual(ec.shrink(facets, grown), [30])
        everything = list(range(len(facets)))
        self.assertEqual(ec.shrink(facets, everything), everything)  # no face outside
        self.assertEqual(ec.invert(5, [1, 3]), [0, 2, 4])

    def test_expand_to_groups_and_connected(self):
        pts, facets = box()
        far = [(a + 8, b + 8, c + 8) for a, b, c in facets]
        pts2 = pts + [(x + 30.0, y, z) for x, y, z in pts]
        both = facets + far
        groups = [0] * 12 + [1] * 12
        self.assertEqual(ec.expand_to_groups(groups, [13]), list(range(12, 24)))
        self.assertEqual(ec.expand_connected(both, [2]), list(range(12)))
        self.assertEqual(len(pts2), 16)

    def test_facing_and_polygon(self):
        pts, facets = box()
        look = (0.0, 0.0, -1.0)  # looking down
        front = ec.facing(pts, facets, range(len(facets)), look)
        self.assertEqual(sorted(front), top_facets(pts, facets, 5.0))
        screen = [(p[0], p[1]) for p in pts]  # top view: x, y on the screen
        square = [(-1.0, -1.0), (21.0, -1.0), (21.0, 11.0), (-1.0, 11.0)]
        self.assertEqual(len(ec.in_polygon(screen, facets, square)), 12)
        small = [(-1.0, -1.0), (21.0, -1.0), (21.0, 5.0), (-1.0, 5.0)]
        window = ec.in_polygon(screen, facets, small)
        crossing = ec.in_polygon(screen, facets, small, crossing=True)
        self.assertLess(len(window), len(crossing))
        screen[0] = None  # behind the camera
        self.assertNotIn(0, [i for i in ec.in_polygon(screen, facets, square) if 0 in facets[i]])

    def test_move_vector(self):
        self.assertEqual(ec.move_vector("Z", 2.0), (0.0, 0.0, 2.0))
        self.assertEqual(ec.move_vector("X", -1.0), (-1.0, 0.0, 0.0))
        normal = ec.move_vector("Normal", 3.0, (0.0, 0.0, 2.0))
        self.assertAlmostEqual(normal[2], 3.0)
        with self.assertRaises(mc.MeshError):
            ec.move_vector("Normal", 1.0, None)
        pts, facets = box()
        top = top_facets(pts, facets, 5.0)
        self.assertEqual(ec.mean_normal(pts, facets, top), (0.0, 0.0, 1.0))
        centre = ec.centre_of(pts, facets, top)
        self.assertAlmostEqual(centre[2], 5.0)


class FaceGroupTests(unittest.TestCase):
    def test_combine_touching_groups(self):
        pts, facets = box()
        groups = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
        joined = ec.combine_groups(facets, groups, [2, 3])  # the front and the right side
        self.assertEqual(joined.count(2), 4)
        self.assertNotIn(3, joined)
        with self.assertRaises(mc.MeshError):  # the front and the back do not touch
            ec.combine_groups(facets, groups, [2, 4])
        three = ec.combine_groups(facets, groups, [2, 4, 3])  # joined through the right side
        self.assertEqual(three.count(2), 6)
        self.assertEqual(ec.renumber([5, 5, 2, 7, 2]), [0, 0, 1, 2, 1])

    def test_combine_refuses_with_reasons(self):
        pts, facets = box()
        far = [(a + 8, b + 8, c + 8) for a, b, c in facets]
        both = facets + far
        groups = [0] * 12 + [1] * 12
        with self.assertRaises(mc.MeshError) as ctx:
            ec.combine_groups(both, groups, [0, 1])
        self.assertIn("do not touch", str(ctx.exception))
        with self.assertRaises(mc.MeshError) as ctx:
            ec.combine_groups(both, groups, [0])
        self.assertIn("two or more", str(ctx.exception))
        with self.assertRaises(mc.MeshError):
            ec.combine_groups(both, groups, [0, 9])


if __name__ == "__main__":
    unittest.main()
