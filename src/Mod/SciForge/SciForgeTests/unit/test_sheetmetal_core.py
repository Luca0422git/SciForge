# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sheet metal rules and bend maths (sciforge/sheetmetal_core.py)."""

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sciforge import sheetmetal_core as core  # noqa: E402


class RuleTests(unittest.TestCase):
    def test_library_rules_validate(self):
        for rule in core.LIBRARY:
            self.assertEqual(core.validate(rule), [], rule["name"])

    def test_default_rule_is_first(self):
        self.assertEqual(core.DEFAULT_RULE, core.LIBRARY[0]["name"])

    def test_expressions_follow_thickness(self):
        rule = core.make_rule("T", thickness="2", bend_relief_depth="Thickness / 2")
        values = core.evaluated(rule)
        self.assertAlmostEqual(values["bend_radius"], 2.0)
        self.assertAlmostEqual(values["bend_relief_depth"], 1.0)
        self.assertAlmostEqual(values["corner_relief_2bend_size"], 8.0)

    def test_inch_rule_in_mm(self):
        values = core.evaluated(core.make_rule("I", units="in", thickness="0.1"))
        self.assertAlmostEqual(values["thickness"], 2.54)
        self.assertAlmostEqual(values["bend_radius"], 2.54)

    def test_bad_values_are_refused_with_a_reason(self):
        self.assertIn(
            "Thickness must be more than 0", core.validate(core.make_rule("Z", thickness="0"))
        )
        self.assertTrue(core.validate(core.make_rule("K", k_factor="1.5")))
        self.assertTrue(core.validate(core.make_rule("E", miter_gap="Width * 2")))
        bad = core.make_rule("C")
        bad["bend_relief_shape"] = "oval"
        self.assertTrue(core.validate(bad))
        with self.assertRaises(ValueError):
            core.evaluated(core.make_rule("Z", thickness="-1"))

    def test_expression_names_and_operators(self):
        self.assertAlmostEqual(core.evaluate_expression("thickness * 1.5 + 1", 2), 4.0)
        self.assertAlmostEqual(core.evaluate_expression("-(2)"), -2.0)
        with self.assertRaises(ValueError):
            core.evaluate_expression("__import__('os')")
        with self.assertRaises(ValueError):
            core.evaluate_expression("1/0")

    def test_unknown_field_refused(self):
        with self.assertRaises(KeyError):
            core.make_rule("X", colour="red")


class BendMathTests(unittest.TestCase):
    def test_bend_allowance(self):
        # 90 degrees, R = T = 1, K = 0.44: pi/2 * 1.44
        self.assertAlmostEqual(core.bend_allowance(90, 1, 1, 0.44), math.pi / 2 * 1.44)

    def test_bend_deduction_right_angle(self):
        # 2 * (R + T) * tan(45) - BA
        expected = 2 * 2.0 - math.pi / 2 * 1.44
        self.assertAlmostEqual(core.bend_deduction(90, 1, 1, 0.44), expected)

    def test_neutral_radius(self):
        self.assertAlmostEqual(core.neutral_radius(2, 1, 0.5), 2.5)


if __name__ == "__main__":
    unittest.main()
