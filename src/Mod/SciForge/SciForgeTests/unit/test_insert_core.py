# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of Insert Mesh / SVG / DXF / Canvas (sciforge/insert.py). Runs without FreeCAD."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import insert  # noqa: E402


class UnitTests(unittest.TestCase):
    def test_fusion_unit_types_in_fusion_order(self):
        self.assertEqual(insert.UNIT_NAMES, ["Centimeter", "Millimeter", "Meter", "Inch", "Foot"])

    def test_mm_per_unit(self):
        self.assertEqual(insert.unit_scale("Millimeter"), 1.0)
        self.assertEqual(insert.unit_scale("Centimeter"), 10.0)
        self.assertEqual(insert.unit_scale("Meter"), 1000.0)
        self.assertAlmostEqual(insert.unit_scale("Inch"), 25.4)
        self.assertAlmostEqual(insert.unit_scale("Foot"), 304.8)

    def test_unknown_unit_is_refused(self):
        with self.assertRaises(insert.InsertError):
            insert.unit_scale("Furlong")

    def test_dxf_insunits_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a.dxf")
            with open(path, "w") as handle:
                handle.write(
                    "  0\nSECTION\n  2\nHEADER\n  9\n$INSUNITS\n 70\n     1\n  0\nENDSEC\n"
                )
            self.assertAlmostEqual(insert.dxf_file_unit(path), 25.4)
            with open(path, "w") as handle:
                handle.write("  0\nSECTION\n  2\nHEADER\n  9\n$ACADVER\n  1\nAC1014\n  0\nENDSEC\n")
            self.assertIsNone(insert.dxf_file_unit(path))
            self.assertIsNone(insert.dxf_file_unit(os.path.join(folder, "missing.dxf")))


class MeshPlacementTests(unittest.TestCase):
    BOX = ((0.0, 0.0, 0.0), (20.0, 10.0, 5.0))

    def test_scale_grows_the_box(self):
        lo, hi = insert.bounds_after(self.BOX, scale=10.0)
        self.assertEqual(lo, (0.0, 0.0, 0.0))
        self.assertEqual(hi, (200.0, 100.0, 50.0))

    def test_flip_up_turns_y_into_z(self):
        lo, hi = insert.bounds_after(self.BOX, flip=True)
        # (x, y, z) -> (x, -z, y): the old height (5) lies along -Y, the old depth (10) is up
        self.assertEqual(lo, (0.0, -5.0, 0.0))
        self.assertEqual(hi, (20.0, 0.0, 10.0))

    def test_center_puts_the_middle_on_the_origin(self):
        self.assertEqual(insert.center_offset(self.BOX), (-10.0, -5.0, -2.5))

    def test_move_to_ground_keeps_x_and_y(self):
        bounds = ((0.0, 0.0, -3.0), (20.0, 10.0, 2.0))
        self.assertEqual(insert.ground_offset(bounds, (4.0, 7.0, 99.0)), (4.0, 7.0, 3.0))

    def test_facet_warning_is_fusions_ten_thousand(self):
        self.assertEqual(insert.FACET_WARNING, 10000)


class PlaneTransformTests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(insert.plane_transform_point((3.0, 4.0)), (3.0, 4.0))

    def test_distance_moves(self):
        self.assertEqual(insert.plane_transform_point((3.0, 4.0), dx=1.0, dy=-2.0), (4.0, 2.0))

    def test_scale_about_the_origin(self):
        self.assertEqual(insert.plane_transform_point((3.0, 4.0), scale=2.0), (6.0, 8.0))

    def test_angle_turns_counter_clockwise(self):
        x, y = insert.plane_transform_point((10.0, 0.0), angle=90.0)
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 10.0)

    def test_flips_mirror_about_the_axes(self):
        self.assertEqual(insert.plane_transform_point((3.0, 4.0), flip_h=True), (-3.0, 4.0))
        self.assertEqual(insert.plane_transform_point((3.0, 4.0), flip_v=True), (3.0, -4.0))

    def test_order_is_flip_scale_turn_move(self):
        x, y = insert.plane_transform_point((1.0, 0.0), dx=5.0, angle=90.0, scale=2.0, flip_h=True)
        # flip -> (-1, 0); scale -> (-2, 0); turn 90 -> (0, -2); move -> (5, -2)
        self.assertAlmostEqual(x, 5.0)
        self.assertAlmostEqual(y, -2.0)


class CanvasTests(unittest.TestCase):
    def test_default_size_in_an_empty_design(self):
        w, h = insert.default_canvas_size((80, 40))
        self.assertEqual((w, h), (100.0, 50.0))

    def test_default_size_follows_the_design(self):
        w, h = insert.default_canvas_size((40, 80), design_extent=100.0)
        self.assertEqual((w, h), (65.0, 130.0))

    def test_tiny_design_still_gives_a_usable_canvas(self):
        w, _h = insert.default_canvas_size((100, 50), design_extent=2.0)
        self.assertEqual(w, 20.0)

    def test_no_size_is_refused(self):
        with self.assertRaises(insert.InsertError):
            insert.default_canvas_size((0, 40))

    def test_calibrate_factor(self):
        factor = insert.calibrate_scale((0, 0, 0), (30, 40, 0), 100.0)
        self.assertAlmostEqual(factor, 2.0)

    def test_calibrate_refuses_same_point_and_zero(self):
        with self.assertRaises(insert.InsertError):
            insert.calibrate_scale((1, 1, 0), (1, 1, 0), 10.0)
        with self.assertRaises(insert.InsertError):
            insert.calibrate_scale((0, 0, 0), (1, 0, 0), 0.0)

    def test_canvas_defaults_are_fusions(self):
        # Fusion's defaults since the canvas update: 50 % opacity, Display Through on
        self.assertEqual(insert.CANVAS_EMPTY_SIZE, 100.0)
        names = [name for _kind, name, _text in insert.CANVAS_PROPS]
        for wanted in ("ImageData", "CanvasOpacity", "DisplayThrough", "ScaleX", "ScaleY"):
            self.assertIn(wanted, names)


class FileKindTests(unittest.TestCase):
    def test_extensions(self):
        self.assertIn(".3mf", insert.MESH_EXTENSIONS)
        self.assertIn(".stp", insert.STEP_EXTENSIONS)
        self.assertIn(".jpeg", insert.IMAGE_EXTENSIONS)

    def test_methods_and_operations_are_fusions(self):
        self.assertEqual(insert.METHODS, ["Faceted", "Prismatic"])
        self.assertEqual(insert.OPERATIONS, ["Parametric", "Base Feature"])


if __name__ == "__main__":
    unittest.main()
