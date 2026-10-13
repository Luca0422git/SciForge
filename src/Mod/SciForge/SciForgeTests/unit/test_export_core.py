# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export / 3D Print / Export Everything helpers (sciforge/export.py). Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import export  # noqa: E402


class FormatTests(unittest.TestCase):
    def test_formats_and_endings(self):
        self.assertEqual(export.extension_of("STEP"), ".step")
        self.assertEqual(export.extension_of("STL (Binary)"), ".stl")
        self.assertEqual(export.extension_of("STL (ASCII)"), ".stl")
        self.assertEqual(export.extension_of("3MF"), ".3mf")
        self.assertEqual(export.extension_of("OBJ"), ".obj")

    def test_step_is_the_only_exact_format(self):
        self.assertFalse(export.is_mesh_format("STEP"))
        for label in export.MESH_FORMATS:
            self.assertTrue(export.is_mesh_format(label))

    def test_print_formats_are_fusions(self):
        self.assertEqual(export.PRINT_FORMATS, ["3MF", "STL (Binary)", "STL (ASCII)", "OBJ"])

    def test_unknown_format(self):
        with self.assertRaises(export.ExportError):
            export.extension_of("F3D")


class RefinementTests(unittest.TestCase):
    def test_presets(self):
        self.assertEqual(export.REFINEMENTS, ["Low", "Medium", "High", "Custom"])
        self.assertEqual(export.DEFAULT_REFINEMENT, "Medium")
        low = export.refinement_values("Low")
        high = export.refinement_values("High")
        self.assertGreater(low[0], high[0])  # finer = smaller deviation
        self.assertGreater(low[1], high[1])

    def test_custom_takes_the_typed_values(self):
        self.assertEqual(export.refinement_values("Custom", 0.2, 20.0), (0.2, 20.0))

    def test_custom_needs_positive_values(self):
        with self.assertRaises(export.ExportError):
            export.refinement_values("Custom", 0.0, 20.0)
        with self.assertRaises(export.ExportError):
            export.refinement_values("Custom", None, None)

    def test_normal_deviation_is_capped(self):
        self.assertEqual(export.refinement_values("Custom", 0.1, 400.0), (0.1, 90.0))


class NamingTests(unittest.TestCase):
    def test_safe_name_strips_forbidden_characters(self):
        self.assertEqual(export.safe_name('my:de/sign?*"'), "my_de_sign_")
        self.assertEqual(export.safe_name("   "), "design")
        self.assertEqual(export.safe_name("..hidden.."), "hidden")

    def test_with_extension(self):
        self.assertEqual(export.with_extension("/a/b", ".stl"), "/a/b.stl")
        self.assertEqual(export.with_extension("/a/b.STL", ".stl"), "/a/b.STL")
        self.assertEqual(export.with_extension("/a/b.step", ".stl"), "/a/b.step.stl")

    def test_one_file_per_body_names(self):
        files = export.body_file_names(["Plate", "Peg", "Plate"], "/out", "design", ".stl")
        self.assertEqual(
            [os.path.basename(f) for f in files],
            ["design-Plate.stl", "design-Peg.stl", "design-Plate-2.stl"],
        )

    def test_unit_factor(self):
        self.assertEqual(export.unit_factor("Millimeter"), 1.0)
        self.assertAlmostEqual(export.unit_factor("Inch"), 25.4)
        with self.assertRaises(export.ExportError):
            export.unit_factor("Parsec")


class EverythingTests(unittest.TestCase):
    def test_plan_lists_every_open_format(self):
        plan = export.export_everything_plan("/out", "bracket")
        self.assertEqual(
            sorted(os.path.basename(p) for p in plan.values()),
            [
                "README.txt",
                "bracket.3mf",
                "bracket.obj",
                "bracket.png",
                "bracket.step",
                "bracket.stl",
            ],
        )

    def test_folder_beside_the_design(self):
        folder = export.export_folder_for("/designs/Bracket v3.FCStd", "/home/luca")
        self.assertEqual(folder, os.path.join("/designs", "Bracket v3-export"))

    def test_unsaved_design_goes_to_home(self):
        self.assertEqual(export.export_folder_for("", "/home/luca"), "/home/luca/design-export")

    def test_readme_names_every_file(self):
        plan = export.export_everything_plan("/out", "bracket")
        text = export.readme_text("Bracket", plan, ["Body1", "Lid"])
        for name in ("bracket.step", "bracket.stl", "bracket.3mf", "bracket.obj", "bracket.png"):
            self.assertIn(name, text)
        self.assertIn("Body1, Lid", text)

    def test_slicer_command(self):
        self.assertEqual(
            export.slicer_command("/usr/bin/slicer", "/a.3mf"), ["/usr/bin/slicer", "/a.3mf"]
        )
        with self.assertRaises(export.ExportError):
            export.slicer_command("", "/a.3mf")

    def test_big_mesh_note(self):
        self.assertEqual(export.estimate_time_note(1000), "")
        self.assertTrue(export.estimate_time_note(5000000))


if __name__ == "__main__":
    unittest.main()
