# SPDX-License-Identifier: LGPL-2.1-or-later
"""Box / Cylinder / Sphere / Torus / Coil / Pipe: the number logic of
sciforge/primitives_core.py (sizes, checks, the operation Fusion picks, the coil and pipe
sections) and the golden-model format of their steps. Runs without FreeCAD."""
import copy
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from SciForgeTests.golden import schema  # noqa: E402
from sciforge import primitives_core as core  # noqa: E402

PI = math.pi


class RoundingTests(unittest.TestCase):
    def test_nice_rounds_up_to_round_values(self):
        self.assertEqual(core.nice(8.0), 10.0)
        self.assertEqual(core.nice(2.2), 2.5)
        self.assertEqual(core.nice(20.0), 20.0)
        self.assertAlmostEqual(core.nice(0.3), 0.5)
        self.assertEqual(core.nice(0.0), 1.0)

    def test_click_step_is_the_largest_round_value_below(self):
        self.assertEqual(core.nice_floor(1.9), 1.0)
        self.assertEqual(core.nice_floor(2.6), 2.5)
        self.assertEqual(core.nice_floor(7.0), 5.0)
        self.assertAlmostEqual(core.nice_floor(0.6), 0.5)
        self.assertEqual(core.nice_floor(0.0), 0.0)

    def test_multiples_of_five_are_reachable(self):
        for pixel in (0.03, 0.1, 0.17, 0.3, 0.6, 0.8):
            step = core.nice_floor(6.0 * pixel)
            self.assertAlmostEqual(core.round_to(5.0, step), 5.0, msg=step)
            self.assertAlmostEqual(core.round_to(35.0, step), 35.0, msg=step)

    def test_snap_takes_the_nearest_point_in_reach(self):
        snaps = [(0.0, 0.0), (40.0, 20.0), (40.5, 20.0)]
        self.assertEqual(core.nearest_snap(0.3, -0.2, snaps, 1.0), (0.0, 0.0))
        self.assertEqual(core.nearest_snap(40.4, 20.1, snaps, 1.0), (40.5, 20.0))
        self.assertIsNone(core.nearest_snap(10.0, 10.0, snaps, 1.0))
        self.assertIsNone(core.nearest_snap(1.5, 0.0, snaps, 1.0))
        self.assertIsNone(core.nearest_snap(0.0, 0.0, [], 1.0))

    def test_round_halves_up_and_never_minus_zero(self):
        self.assertEqual(core.round_to(7.0, 2.0), 8.0)
        self.assertEqual(core.round_to(-0.1, 1.0), 0.0)
        self.assertEqual(str(core.round_to(-0.1, 1.0)), "0.0")
        self.assertEqual(core.round_to(3.2, 0.0), 3.2)


class OperationTests(unittest.TestCase):
    def test_first_solid_is_a_new_body(self):
        self.assertEqual(core.operation_for(False, 0.0, 100.0, 0.0), "new_body")

    def test_mostly_inside_cuts(self):
        self.assertEqual(core.operation_for(True, 80.0, 20.0, 0.0), "cut")

    def test_half_in_joins(self):
        self.assertEqual(core.operation_for(True, 50.0, 50.0, 0.0), "join")

    def test_touching_joins(self):
        self.assertEqual(core.operation_for(True, 0.0, 100.0, 0.0), "join")

    def test_away_from_the_part_is_a_new_body(self):
        self.assertEqual(core.operation_for(True, 0.0, 100.0, 5.0), "new_body")


class PrimitiveTests(unittest.TestCase):
    def test_torus_positions(self):
        base = {"inner_diameter": 20.0, "torus_diameter": 4.0}
        self.assertEqual(core.torus_radii(dict(base, position="inside")), (8.0, 2.0))
        self.assertEqual(core.torus_radii(dict(base, position="center")), (10.0, 2.0))
        self.assertEqual(core.torus_radii(dict(base, position="outside")), (12.0, 2.0))

    def test_too_thick_torus_says_how_thick_it_can_be(self):
        options = {
            "inner_diameter": 30.0,
            "torus_diameter": 25.0,
            "position": "inside",
            "operation": "join",
        }
        with self.assertRaises(core.PrimitiveError) as cm:
            core.check_sizes("torus", options)
        self.assertIn("too thick", str(cm.exception))
        self.assertIn("under 15 mm", str(cm.exception))

    def test_zero_and_negative_sizes_refused(self):
        box = {"length": 10, "width": 10, "height": 0, "operation": "join"}
        with self.assertRaises(core.PrimitiveError):
            core.check_sizes("box", box)
        with self.assertRaises(core.PrimitiveError):
            core.check_sizes("box", dict(box, height=5, length=-1))
        with self.assertRaises(core.PrimitiveError):
            core.check_sizes("cylinder", {"diameter": 0, "height": 5, "operation": "join"})
        self.assertTrue(core.check_sizes("box", dict(box, height=-5)))  # down is fine

    def test_unknown_operation_refused(self):
        with self.assertRaises(core.PrimitiveError):
            core.check_sizes("sphere", {"diameter": 5, "operation": "merge"})

    def test_box_corner_follows_the_clicked_side(self):
        options = {"x": 10, "y": 5, "length": 4, "width": 3, "height": -2, "sx": -1, "sy": 1}
        self.assertEqual(core.box_corner(options), (6.0, 5.0, -2.0))
        self.assertEqual(core.box_corner(dict(options, sx=1, sy=-1, height=2)), (10.0, 2.0, 0.0))

    def test_volumes(self):
        self.assertEqual(core.volume("box", {"length": 4, "width": 3, "height": -2}), 24.0)
        self.assertAlmostEqual(core.volume("cylinder", {"diameter": 10, "height": 5}), PI * 25 * 5)
        self.assertAlmostEqual(core.volume("sphere", {"diameter": 6}), 4.0 / 3.0 * PI * 27)
        self.assertAlmostEqual(
            core.volume(
                "torus", {"inner_diameter": 20, "torus_diameter": 4, "position": "outside"}
            ),
            2 * PI * PI * 12 * 4,
        )


COIL = {
    "x": 0.0,
    "y": 0.0,
    "type": "rev_height",
    "diameter": 20.0,
    "clockwise": True,
    "revolutions": 4.0,
    "height": 20.0,
    "pitch": 5.0,
    "angle": 0.0,
    "section": "circular",
    "section_position": "inside",
    "section_size": 2.0,
    "operation": "join",
}


class CoilTests(unittest.TestCase):
    def test_section_positions(self):
        self.assertEqual(core.coil_section_radius(COIL), 9.0)
        self.assertEqual(core.coil_section_radius(dict(COIL, section_position="center")), 10.0)
        self.assertEqual(core.coil_section_radius(dict(COIL, section_position="outside")), 11.0)

    def test_triangles_point_out_or_in(self):
        ext = dict(COIL, section="tri_ext", section_position="inside")
        out, inward, along = core.coil_section_extent(ext)
        self.assertEqual((out, inward), (1.0, 0.5))
        self.assertAlmostEqual(along, math.sqrt(3.0))
        self.assertEqual(core.coil_section_radius(ext), 9.0)  # the tip touches the diameter
        points = core.coil_section_points(ext)
        self.assertEqual(points[0], (10.0, 0.0))
        internal = core.coil_section_points(dict(ext, section="tri_int"))
        self.assertEqual(internal[0][0], core.coil_section_radius(dict(ext, section="tri_int")) - 1)

    def test_square_is_measured_round_its_corners(self):
        square = dict(COIL, section="square")
        half = core.coil_section_extent(square)[0]
        self.assertAlmostEqual(half, 1.0 / math.sqrt(2.0))

    def test_types_resolve_the_same_coil(self):
        self.assertEqual(core.coil_resolved(COIL), (4.0, 20.0, 5.0))
        self.assertEqual(core.coil_resolved(dict(COIL, type="rev_pitch")), (4.0, 20.0, 5.0))
        self.assertEqual(core.coil_resolved(dict(COIL, type="height_pitch")), (4.0, 20.0, 5.0))
        self.assertEqual(core.coil_resolved(dict(COIL, type="rev_pitch", height=-1)), (4, -20, 5))
        self.assertEqual(core.coil_resolved(dict(COIL, type="spiral")), (4.0, 0.0, 5.0))

    def test_volume_by_pappus(self):
        self.assertAlmostEqual(core.coil_volume(COIL), 72 * PI * PI)
        spiral = dict(
            COIL, type="spiral", revolutions=3, section="square", section_position="center"
        )
        self.assertAlmostEqual(core.coil_volume(spiral), 2 * 2 * PI * 17.5 * 3)

    def test_touching_turns_refused(self):
        with self.assertRaises(core.PrimitiveError) as cm:
            core.coil_check(dict(COIL, revolutions=12))  # pitch 1.67 < section 2
        self.assertIn("touch", str(cm.exception))
        with self.assertRaises(core.PrimitiveError):
            core.coil_check(dict(COIL, type="spiral", pitch=1.5))

    def test_section_over_the_axis_refused(self):
        with self.assertRaises(core.PrimitiveError):
            core.coil_check(dict(COIL, diameter=2.0, section_position="center"))

    def test_steep_angle_refused(self):
        with self.assertRaises(core.PrimitiveError):
            core.coil_check(dict(COIL, angle=89.5))
        with self.assertRaises(core.PrimitiveError):
            core.coil_check(dict(COIL, angle=-40.0))  # narrows to the axis

    def test_a_good_coil_passes(self):
        self.assertTrue(core.coil_check(dict(COIL)))
        self.assertTrue(core.coil_check(dict(COIL, type="spiral", pitch=5)))


PIPE = {
    "distance": 1.0,
    "section": "circular",
    "section_size": 2.0,
    "hollow": False,
    "thickness": 0.25,
    "operation": "join",
}


class PipeTests(unittest.TestCase):
    def test_section_areas(self):
        self.assertAlmostEqual(core.pipe_section_area(PIPE), PI)
        self.assertAlmostEqual(core.pipe_section_area(dict(PIPE, section="square")), 2.0)
        self.assertAlmostEqual(
            core.pipe_section_area(dict(PIPE, section="triangular")), 3 * math.sqrt(3) / 4
        )
        self.assertAlmostEqual(core.pipe_section_area(dict(PIPE, hollow=True)), PI * 0.4375)
        square = dict(PIPE, section="square", hollow=True, thickness=0.2)
        side = math.sqrt(2.0)
        self.assertAlmostEqual(core.pipe_section_area(square), 2.0 - (side - 0.4) ** 2)

    def test_walls_as_thick_as_the_section_refused(self):
        with self.assertRaises(core.PrimitiveError) as cm:
            core.pipe_check(dict(PIPE, hollow=True, thickness=1.0))
        self.assertIn("smaller than 1 mm", str(cm.exception))
        with self.assertRaises(core.PrimitiveError):
            core.pipe_check(dict(PIPE, section="triangular", hollow=True, thickness=0.5))

    def test_distance_is_a_fraction(self):
        with self.assertRaises(core.PrimitiveError):
            core.pipe_check(dict(PIPE, distance=0.0))
        with self.assertRaises(core.PrimitiveError):
            core.pipe_check(dict(PIPE, distance=1.5))
        self.assertTrue(core.pipe_check(dict(PIPE, distance=0.25)))


BOX = {"op": "sf_primitive", "id": "b1", "kind": "box", "length": 4, "width": 3, "height": 2}


def model(*steps):
    return {
        "id": "t",
        "title": "test",
        "steps": [copy.deepcopy(s) for s in steps],
        "expect": {"volume": 1, "source": "analytic"},
    }


class GoldenFormatTests(unittest.TestCase):
    def test_valid_steps(self):
        schema.validate(model(BOX))
        schema.validate(
            model(
                BOX,
                {
                    "op": "sf_primitive",
                    "id": "c",
                    "kind": "cylinder",
                    "plane": {"face": {"normal": [0, 0, 1], "count": 1}},
                    "diameter": 2,
                    "height": -1,
                },
                {"op": "sf_coil", "id": "k", "plane": "XZ", "type": "spiral", "pitch": 3},
                {"op": "sf_path_sketch", "id": "p", "segments": [{"line": [[0, 0], [5, 0]]}]},
                {"op": "sf_pipe", "id": "pp", "path": {"sketch": "p", "edge": 1}, "hollow": True},
                {"op": "sf_primitive_edit", "target": "pp", "set": {"section": "square"}},
            )
        )

    def test_unknown_kind(self):
        with self.assertRaises(schema.ModelError):
            schema.validate(model(dict(BOX, kind="cone")))

    def test_bad_plane(self):
        with self.assertRaises(schema.ModelError):
            schema.validate(model(dict(BOX, plane="XX")))

    def test_bad_operation(self):
        with self.assertRaises(schema.ModelError):
            schema.validate(model(dict(BOX, operation="merge")))

    def test_edit_needs_a_primitive_target(self):
        with self.assertRaises(schema.ModelError):
            schema.validate(
                model(BOX, {"op": "sf_primitive_edit", "target": "zz", "set": {"x": 1}})
            )
        with self.assertRaises(schema.ModelError):
            schema.validate(
                model(BOX, {"op": "sf_primitive_edit", "target": "b1", "set": {"pitch": 1}})
            )

    def test_pipe_path_forms(self):
        with self.assertRaises(schema.ModelError):
            schema.validate(model({"op": "sf_pipe", "id": "pp", "path": {"sketch": "nope"}}))
        schema.validate(model(BOX, {"op": "sf_pipe", "id": "pp", "path": {"edges": {"all": True}}}))

    def test_arc_segment_shape(self):
        with self.assertRaises(schema.ModelError):
            schema.validate(
                model({"op": "sf_path_sketch", "id": "p", "segments": [{"arc": [0, 0]}]})
            )


if __name__ == "__main__":
    unittest.main()
