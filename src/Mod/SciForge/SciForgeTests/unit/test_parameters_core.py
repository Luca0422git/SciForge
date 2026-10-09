# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parameter names in expressions. Runs without FreeCAD."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import parameters_core as core  # noqa: E402

NAMES = {"width", "wall", "d"}


class ExpressionTests(unittest.TestCase):
    def test_bare_names_become_qualified(self):
        self.assertEqual(
            core.to_freecad("width * 2 + wall", NAMES), "Parameters.width * 2 + Parameters.wall"
        )

    def test_units_functions_and_other_objects_untouched(self):
        self.assertEqual(core.to_freecad("width + 5 mm", NAMES), "Parameters.width + 5 mm")
        self.assertEqual(core.to_freecad("max(width; 3)", NAMES), "max(Parameters.width; 3)")
        self.assertEqual(core.to_freecad("Sketch.width", NAMES), "Sketch.width")
        self.assertEqual(core.to_freecad("width2 + widths", NAMES), "width2 + widths")

    def test_quoted_text_untouched(self):
        self.assertEqual(core.to_freecad("'width'", NAMES), "'width'")

    def test_round_trip(self):
        for expr in ("width * 2 + wall", "d / 2 + 1 mm", "max(width; wall)"):
            self.assertEqual(core.from_freecad(core.to_freecad(expr, NAMES)), expr)

    def test_from_freecad_handles_bracket_syntax(self):
        self.assertEqual(core.from_freecad("<<Parameters>>.width * 2"), "width * 2")

    def test_from_freecad_leaves_other_objects(self):
        self.assertEqual(core.from_freecad("MyParameters.width"), "MyParameters.width")


class NameTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(core.check_name("wall_thickness"), "wall_thickness")

    def test_invalid(self):
        for bad in ("", "2wide", "my width", "mm", "sin", "for"):
            with self.assertRaises(core.ParameterError):
                core.check_name(bad)

    def test_duplicate(self):
        with self.assertRaises(core.ParameterError):
            core.check_name("width", existing={"width"})

    def test_units(self):
        self.assertEqual(core.property_type("mm"), "App::PropertyLength")
        self.assertEqual(core.unit_of("App::PropertyAngle"), "deg")
        with self.assertRaises(core.ParameterError):
            core.property_type("furlong")


if __name__ == "__main__":
    unittest.main()
