# SPDX-License-Identifier: LGPL-2.1-or-later
"""ISO 286 limits and fits (drawing_fits): the IT grades, shaft and hole deviations
checked against values printed in the standard's tables, fits and their types."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import drawing_fits as fits  # noqa: E402


class GradeTests(unittest.TestCase):
    def test_it_values(self):
        self.assertAlmostEqual(fits.it_value(7, 20.0), 0.021)
        self.assertAlmostEqual(fits.it_value(6, 20.0), 0.013)
        self.assertAlmostEqual(fits.it_value(7, 50.0), 0.025)
        self.assertAlmostEqual(fits.it_value(11, 10.0), 0.090)
        self.assertAlmostEqual(fits.it_value(8, 120.0), 0.054)

    def test_boundaries_belong_to_the_lower_step(self):
        # "over 18 up to and including 30": 18 is in 10-18, 30 in 18-30
        self.assertAlmostEqual(fits.it_value(7, 18.0), 0.018)
        self.assertAlmostEqual(fits.it_value(7, 18.01), 0.021)
        self.assertAlmostEqual(fits.it_value(7, 30.0), 0.021)
        self.assertAlmostEqual(fits.it_value(7, 3.0), 0.010)

    def test_out_of_range_sizes_are_refused(self):
        with self.assertRaises(fits.FitError):
            fits.it_value(7, 0.0)
        with self.assertRaises(fits.FitError) as ctx:
            fits.deviations("H7", 600.0)
        self.assertIn("500", str(ctx.exception))


class ShaftTests(unittest.TestCase):
    # (class, size, upper, lower) from the ISO 286-2 tables
    CASES = (
        ("g6", 20.0, -0.007, -0.020),
        ("h6", 20.0, 0.0, -0.013),
        ("k6", 25.0, 0.015, 0.002),
        ("n6", 20.0, 0.028, 0.015),
        ("p6", 20.0, 0.035, 0.022),
        ("s6", 20.0, 0.048, 0.035),
        ("s6", 50.0, 0.059, 0.043),
        ("u6", 50.0, 0.086, 0.070),
        ("f7", 50.0, -0.025, -0.050),
        ("d9", 20.0, -0.065, -0.117),
        ("c11", 10.0, -0.080, -0.170),
        ("e8", 30.0, -0.040, -0.073),
        ("m6", 40.0, 0.025, 0.009),
        ("r6", 70.0, 0.062, 0.043),
        ("t6", 40.0, 0.064, 0.048),
        ("k8", 20.0, 0.033, 0.0),
    )

    def test_table_values(self):
        for cls, size, upper, lower in self.CASES:
            got = fits.deviations(cls, size)
            self.assertAlmostEqual(got[0], upper, msg="%s at %s" % (cls, size))
            self.assertAlmostEqual(got[1], lower, msg="%s at %s" % (cls, size))

    def test_js_is_symmetric(self):
        self.assertEqual(fits.deviations("js6", 20.0), (0.0065, -0.0065))

    def test_t_starts_above_24_mm(self):
        with self.assertRaises(fits.FitError):
            fits.deviations("t6", 20.0)


class HoleTests(unittest.TestCase):
    CASES = (
        ("H7", 20.0, 0.021, 0.0),
        ("H7", 12.0, 0.018, 0.0),
        ("H8", 20.0, 0.033, 0.0),
        ("H11", 10.0, 0.090, 0.0),
        ("G7", 20.0, 0.028, 0.007),
        ("F8", 20.0, 0.053, 0.020),
        ("D9", 20.0, 0.117, 0.065),
        ("C11", 10.0, 0.170, 0.080),
        ("K7", 20.0, 0.006, -0.015),
        ("M7", 20.0, 0.0, -0.021),
        ("N7", 20.0, -0.007, -0.028),
        ("N9", 20.0, 0.0, -0.052),
        ("P7", 20.0, -0.014, -0.035),
        ("S7", 50.0, -0.034, -0.059),
        ("U7", 50.0, -0.061, -0.086),
        ("M7", 2.0, -0.002, -0.012),
        ("K7", 2.0, 0.0, -0.010),
        ("P9", 20.0, -0.022, -0.074),
    )

    def test_table_values(self):
        for cls, size, upper, lower in self.CASES:
            got = fits.deviations(cls, size)
            self.assertAlmostEqual(got[0], upper, msg="%s at %s" % (cls, size))
            self.assertAlmostEqual(got[1], lower, msg="%s at %s" % (cls, size))

    def test_limits(self):
        self.assertEqual(fits.limits("H7", 12.0), (12.018, 12.0))
        self.assertEqual(fits.limits("g6", 20.0), (19.993, 19.98))


class ClassTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(fits.parse_class("H7"), ("H", 7))
        self.assertEqual(fits.parse_class(" g6 "), ("g", 6))
        self.assertEqual(fits.parse_class("js6"), ("js", 6))
        self.assertEqual(fits.parse_class("JS7"), ("JS", 7))
        self.assertTrue(fits.is_hole_class("H11"))
        self.assertFalse(fits.is_hole_class("h11"))

    def test_bad_classes_say_why(self):
        for text in ("", "7H", "Q7", "H0", "H17", "zz9"):
            with self.assertRaises(fits.FitError):
                fits.parse_class(text)


class FitTests(unittest.TestCase):
    def test_parse_fit(self):
        self.assertEqual(fits.parse_fit("H7/g6"), ("H7", "g6"))
        with self.assertRaises(fits.FitError):
            fits.parse_fit("g6/H7")
        with self.assertRaises(fits.FitError):
            fits.parse_fit("H7")

    def test_types_of_the_preferred_fits(self):
        for name, _basis, kind, _use in fits.PREFERRED_FITS:
            hole, shaft = fits.parse_fit(name)
            for size in (6.0, 20.0, 50.0, 120.0):
                self.assertEqual(fits.fit_type(hole, shaft, size), kind, "%s at %s" % (name, size))

    def test_lists(self):
        self.assertEqual(len(fits.preferred_fits()), 20)
        self.assertIn("H7/g6", fits.preferred_fits("Hole", "Clearance"))
        self.assertNotIn("H7/g6", fits.preferred_fits("Shaft"))
        self.assertEqual(fits.preferred_fits("Shaft", "Interference"), ["P7/h6", "S7/h6", "U7/h6"])
        self.assertEqual(fits.fit_use("H7/k6"), "Locational transition")

    def test_clearance(self):
        # H7/g6 at 20: hole 20.000..20.021, shaft 19.980..19.993
        self.assertEqual(fits.clearance("H7", "g6", 20.0), (0.041, 0.007))


if __name__ == "__main__":
    unittest.main()
