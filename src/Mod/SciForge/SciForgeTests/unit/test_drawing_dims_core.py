# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dimension text (drawing_dims_core): the Dimension dialog's override, text before and
after, precision, tolerances (symmetric, deviation, limits, ISO fits), basic and
reference dimensions."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import drawing_dims_core as dc  # noqa: E402

DIA = "⌀"


class SettingsTests(unittest.TestCase):
    def test_defaults_store_nothing(self):
        self.assertEqual(dc.to_json({}), "{}")
        self.assertTrue(dc.is_default(None))
        self.assertEqual(json.loads(dc.to_json({"tolerance": "Fit"})), {"tolerance": "Fit"})

    def test_bad_values_fall_back(self):
        s = dc.settings({"tolerance": "Nonsense", "upper": "x", "unknown": 1})
        self.assertEqual(s["tolerance"], "None")
        self.assertEqual(s["upper"], 0.0)
        self.assertNotIn("unknown", s)
        self.assertEqual(dc.settings('{"basic": true}')["basic"], True)
        self.assertEqual(dc.settings("not json")["tolerance"], "None")


class NumberTests(unittest.TestCase):
    def test_default_precision(self):
        self.assertEqual(dc.number(60.0), "60")
        self.assertEqual(dc.number(12.5), "12.5")
        self.assertEqual(dc.number(12.3456), "12.35")
        self.assertEqual(dc.number(25.4, units="in"), "1")
        self.assertEqual(dc.number(-0.0001), "0")

    def test_fixed_precision_keeps_zeros(self):
        self.assertEqual(dc.decimals_of("0.123", "mm"), 3)
        self.assertEqual(dc.decimals_of("0", "mm"), 0)
        self.assertIsNone(dc.decimals_of("Default", "mm"))
        self.assertEqual(dc.number(60.0, 3), "60.000")
        self.assertEqual(dc.number(12.46, 0), "12")

    def test_tolerance_numbers(self):
        self.assertEqual(dc.tolerance_number(0.018, None, "mm"), "+0.018")
        self.assertEqual(dc.tolerance_number(-0.02, None, "mm"), "-0.020")
        self.assertEqual(dc.tolerance_number(0.0, None, "mm"), "0")
        self.assertEqual(dc.tolerance_number(0.0254, None, "in"), "+0.0010")


class TextTests(unittest.TestCase):
    def test_plain(self):
        t = dc.texts(60.0, "Distance")
        self.assertEqual(t["main"], "60")
        self.assertEqual((t["over"], t["under"], t["framed"]), ("", "", False))
        self.assertEqual(dc.texts(12.0, "Diameter")["main"], DIA + "12")
        self.assertEqual(dc.texts(5.0, "Radius")["main"], "R5")
        self.assertEqual(dc.texts(90.0, "Angle")["main"], "90°")

    def test_prefix_suffix_override(self):
        t = dc.texts(12.0, "Diameter", data={"prefix": "4x ", "suffix": " THRU"})
        self.assertEqual(t["main"], "4x " + DIA + "12 THRU")
        t = dc.texts(12.0, "Diameter", data={"override": "12.7"})
        self.assertEqual(t["main"], DIA + "12.7")

    def test_symmetric(self):
        t = dc.texts(40.0, data={"tolerance": "Symmetric", "upper": 0.1})
        self.assertEqual(t["main"], "40 ±0.100")
        t = dc.texts(40.0, data={"tolerance": "Symmetric", "upper": 0.1, "tol_precision": "0.1"})
        self.assertEqual(t["main"], "40 ±0.1")

    def test_deviation(self):
        t = dc.texts(40.0, data={"tolerance": "Deviation", "upper": 0.1, "lower": -0.05})
        self.assertEqual((t["main"], t["over"], t["under"]), ("40", "+0.100", "-0.050"))

    def test_limits(self):
        t = dc.texts(
            40.0, data={"tolerance": "Limits", "upper": 0.1, "lower": -0.05, "precision": "0.12"}
        )
        self.assertEqual(t["lines"], ["40.10", "39.95"])
        self.assertEqual(
            dc.limit_values(40.0, {"tolerance": "Limits", "upper": 0.1, "lower": -0.05}),
            (40.1, 39.95),
        )

    def test_fit_class(self):
        data = {"tolerance": "Fit", "fit": "H7/g6", "fit_member": "Hole"}
        self.assertEqual(dc.texts(12.0, "Diameter", data=data)["main"], DIA + "12 H7")
        data["fit_member"] = "Shaft"
        self.assertEqual(dc.texts(12.0, "Diameter", data=data)["main"], DIA + "12 g6")

    def test_fit_with_tolerances_and_limits(self):
        data = {"tolerance": "Fit", "fit": "H7/g6", "fit_display": "Class and tolerances"}
        t = dc.texts(12.0, "Diameter", data=data)
        self.assertEqual((t["main"], t["over"], t["under"]), (DIA + "12 H7", "+0.018", "0"))
        data["fit_display"] = "Limits"
        t = dc.texts(12.0, "Diameter", data=data)
        self.assertEqual(t["lines"], [DIA + "12.018", DIA + "12.000"])
        self.assertEqual(t["over"], "")
        data["fit_display"] = "Fit"
        self.assertEqual(dc.texts(12.0, "Diameter", data=data)["main"], DIA + "12 H7/g6")
        lim = dc.limit_values(12.0, {"tolerance": "Fit", "fit": "H7/g6"})
        self.assertAlmostEqual(lim[0], 12.018)
        self.assertAlmostEqual(lim[1], 12.0)

    def test_fit_out_of_range_says_why(self):
        t = dc.texts(600.0, "Diameter", data={"tolerance": "Fit"})
        self.assertIn("500", t["main"])
        self.assertIn("500", dc.validate({"tolerance": "Fit"}, 600.0, "Diameter"))

    def test_basic_and_reference(self):
        t = dc.texts(30.0, data={"basic": True, "tolerance": "Deviation", "upper": 0.1})
        self.assertTrue(t["framed"])
        self.assertEqual((t["main"], t["over"]), ("30", ""))
        t = dc.texts(30.0, "Diameter", data={"reference": True})
        self.assertEqual(t["main"], "(" + DIA + "30)")

    def test_angles(self):
        t = dc.texts(45.0, "Angle", data={"tolerance": "Symmetric", "upper": 0.5})
        self.assertEqual(t["main"], "45° ±0.50°")
        self.assertIn("angle", dc.validate({"tolerance": "Fit"}, 45.0, "Angle"))

    def test_inches(self):
        t = dc.texts(
            25.4, data={"tolerance": "Deviation", "upper": 0.127, "lower": 0.0}, units="in"
        )
        self.assertEqual((t["main"], t["over"], t["under"]), ("1", "+0.0050", "0"))

    def test_one_line(self):
        t = dc.texts(
            12.0, "Diameter", data={"tolerance": "Fit", "fit_display": "Class and tolerances"}
        )
        self.assertEqual(dc.one_line(t), DIA + "12 H7 +0.018/0")
        t = dc.texts(30.0, data={"basic": True})
        self.assertEqual(dc.one_line(t), "[30]")

    def test_validate(self):
        self.assertEqual(dc.validate({}), "")
        self.assertIn("upper", dc.validate({"tolerance": "Deviation", "upper": -0.1, "lower": 0.1}))
        self.assertIn("±", dc.validate({"tolerance": "Symmetric", "upper": 0.0}))
        self.assertIn("H7", dc.validate({"tolerance": "Fit", "fit": "H7"}))


if __name__ == "__main__":
    unittest.main()
