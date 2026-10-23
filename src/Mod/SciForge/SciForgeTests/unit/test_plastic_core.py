# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plastic rules (sciforge/plastic_core.py)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sciforge import plastic_core as core  # noqa: E402


class PlasticRuleTests(unittest.TestCase):
    def test_library_rules_validate(self):
        for rule in core.LIBRARY:
            self.assertEqual(core.validate(rule), [], rule["name"])

    def test_names_are_unique(self):
        names = [r["name"] for r in core.LIBRARY]
        self.assertEqual(len(names), len(set(names)))

    def test_default_rule_values(self):
        values = core.evaluated(core.library_rule(core.DEFAULT_RULE))
        self.assertAlmostEqual(values["thickness"], 2.0)
        self.assertAlmostEqual(values["nominal_radius"], 1.0)
        self.assertAlmostEqual(values["knife_edge_threshold"], 0.5)
        self.assertAlmostEqual(values["draft_angle"], 1.0)

    def test_inch_rule_in_mm(self):
        values = core.evaluated(core.library_rule("Default (in)"))
        self.assertAlmostEqual(values["thickness"], 0.08 * 25.4)
        self.assertAlmostEqual(values["clearance"], 0.004 * 25.4)

    def test_thickness_outside_its_range_refused(self):
        rule = core.make_rule("X", thickness="5", maximum_thickness="4")
        self.assertIn("Thickness must lie within the thickness range", core.validate(rule))
        rule = core.make_rule("Y", minimum_thickness="3", maximum_thickness="2", thickness="2.5")
        self.assertTrue(core.validate(rule))

    def test_bad_values_refused(self):
        self.assertTrue(core.validate(core.make_rule("Z", thickness="0")))
        self.assertTrue(core.validate(core.make_rule("D", draft_angle="50")))
        self.assertTrue(core.validate(core.make_rule("E", clearance="Width")))
        with self.assertRaises(KeyError):
            core.make_rule("K", colour="red")
        with self.assertRaises(ValueError):
            core.evaluated(core.make_rule("N", thickness="-2"))

    def test_strain_table_covers_the_library(self):
        for rule in core.LIBRARY:
            self.assertIn(rule["material"], core.ALLOWABLE_STRAIN, rule["name"])


if __name__ == "__main__":
    unittest.main()
