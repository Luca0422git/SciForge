# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole standards without FreeCAD: sciforge/hole_tables.py (clearance holes by fastener, taper
pipe threads) and the tolerance classes in sciforge/thread_tables.py (where a modeled thread
sits), plus thread_core's turned / bored limit."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import hole_tables as holes  # noqa: E402
from sciforge import thread_core as core  # noqa: E402
from sciforge import thread_tables as tables  # noqa: E402


class ClearanceTests(unittest.TestCase):
    def test_iso_273_m6(self):
        # ISO 273 for M6: fine 6.4, medium 6.6, coarse 7.0 (Fusion's Close / Normal / Loose)
        self.assertEqual(holes.clearance_diameter("iso", "6", 6.0, "close"), 6.4)
        self.assertEqual(holes.clearance_diameter("iso", "6", 6.0, "normal"), 6.6)
        self.assertEqual(holes.clearance_diameter("iso", "6", 6.0, "loose"), 7.0)

    def test_iso_273_more_rows(self):
        self.assertEqual(holes.clearance_diameter("iso", "3", 3.0, "normal"), 3.4)
        self.assertEqual(holes.clearance_diameter("iso", "8", 8.0, "normal"), 9.0)
        self.assertEqual(holes.clearance_diameter("iso", "10", 10.0, "loose"), 12.0)
        self.assertEqual(holes.clearance_diameter("iso", "20", 20.0, "close"), 21.0)

    def test_sizes_iso_273_leaves_out(self):
        # M9 is not in ISO 273: FreeCAD's factors (and so SciForge's) apply
        self.assertAlmostEqual(holes.clearance_diameter("iso", "9", 9.0, "normal"), 9.9)
        self.assertAlmostEqual(holes.clearance_diameter("iso", "9", 9.0, "close"), 9.54)

    def test_asme_b18_2_8(self):
        self.assertEqual(holes.clearance_diameter("ansi", "1/4", 6.35, "close"), 6.8)
        self.assertEqual(holes.clearance_diameter("ansi", "1/4", 6.35, "normal"), 7.1)
        self.assertEqual(holes.clearance_diameter("ansi", "#10", 4.826, "loose"), 6.0)
        self.assertAlmostEqual(holes.clearance_diameter("ansi", "#12", 5.486, "normal"), 5.92488)

    def test_every_fit_grows(self):
        for size, row in holes.ISO_273.items():
            self.assertTrue(row[0] <= row[1] <= row[2], size)
            self.assertGreater(row[0], float(size))
        for size, row in holes.ASME_B18_2_8.items():
            self.assertTrue(row[0] <= row[1] <= row[2], size)

    def test_unknown_fit(self):
        with self.assertRaises(ValueError):
            holes.clearance_diameter("iso", "6", 6.0, "medium")


class FastenerTests(unittest.TestCase):
    def test_types_by_hole_type(self):
        cbore = [f.key for f in holes.fasteners("iso", "counterbore")]
        self.assertEqual(cbore, ["socket_head", "hex_head"])
        csink = [f.key for f in holes.fasteners("iso", "countersink")]
        self.assertEqual(csink, ["countersunk"])
        self.assertEqual(len(holes.fasteners("iso", "simple")), 3)
        self.assertEqual(len(holes.fasteners("ansi", "simple")), 3)

    def test_socket_head_m6(self):
        # DIN 974-1: an M6 socket head cap screw (ISO 4762, head 10 x 6) sits in an
        # 11 mm counterbore, 6.4 deep
        cut = holes.head_cut("iso", "socket_head", "6")
        self.assertEqual(cut["hole_type"], "counterbore")
        self.assertEqual(cut["diameter"], 11.0)
        self.assertAlmostEqual(cut["depth"], 6.4)

    def test_countersunk_m6(self):
        cut = holes.head_cut("iso", "countersunk", "6")
        self.assertEqual(cut, {"hole_type": "countersink", "diameter": 13.44, "angle": 90.0})

    def test_inch_heads(self):
        cut = holes.head_cut("ansi", "socket_head", "1/4")
        self.assertAlmostEqual(cut["diameter"], 0.4375 * 25.4)
        self.assertAlmostEqual(cut["depth"], 0.25 * 25.4)
        flat = holes.head_cut("ansi", "countersunk", "1/4")
        self.assertEqual(flat["angle"], 82.0)
        self.assertAlmostEqual(flat["diameter"], 0.531 * 25.4)
        hex_bolt = holes.head_cut("ansi", "hex_head", "1/2")
        self.assertAlmostEqual(hex_bolt["diameter"], 1.3125 * 25.4)  # 1.75 x 3/4, up to 1/16

    def test_counterbore_holds_the_head(self):
        for f in holes.FASTENERS:
            for size, (diameter, depth) in f.heads.items():
                if f.cut == "counterbore":
                    self.assertGreater(depth, 0.0, (f.label, size))
                nominal = holes.clearance_diameter(f.standard, size, 1.0, "loose")
                self.assertGreater(diameter, nominal, (f.label, size))

    def test_missing_size(self):
        self.assertIsNone(holes.head_cut("iso", "countersunk", "1.6"))
        self.assertIsNone(holes.head_cut("iso", "nothing", "6"))


class TaperTests(unittest.TestCase):
    def test_npt_eighth(self):
        # ASME B1.20.1, 1/8-27 NPT: E0 = 0.36351 in, L1 = 0.1615 in, E1 = 0.37360 in; the
        # internal thread's minor diameter at the opening is E1 - 0.8 P = 0.34397 in
        t = holes.taper_thread("npt", "1/8")
        self.assertEqual(t.label, "1/8-27 NPT")
        self.assertAlmostEqual(t.pitch, 25.4 / 27.0)
        self.assertAlmostEqual(t.minor / 25.4, 0.34397, places=4)
        self.assertAlmostEqual(t.major / 25.4, 0.40323, places=4)

    def test_npt_half_inch(self):
        t = holes.taper_thread("npt", "1/2")
        e1 = 0.840 - (0.05 * 0.840 + 1.1) / 14.0 + 0.320 / 16.0
        self.assertAlmostEqual(e1, 0.77843, places=5)  # B1.20.1's E1
        self.assertAlmostEqual(t.minor, (e1 - 0.8 / 14.0) * 25.4, places=6)

    def test_bspt_eighth(self):
        # ISO 7-1, Rc 1/8: gauge diameter 9.728, minor 8.566 at the gauge plane
        t = holes.taper_thread("bspt", "1/8")
        self.assertEqual(t.label, "Rc 1/8")
        self.assertAlmostEqual(t.pitch, 0.9071, places=4)
        self.assertAlmostEqual(t.minor, 8.566, places=3)

    def test_taper_one_in_sixteen(self):
        t = holes.taper_thread("npt", "1/4")
        self.assertAlmostEqual(t.minor - t.diameter_at(16.0), 1.0)
        self.assertAlmostEqual(holes.TAPER_HALF_ANGLE, 1.789910608, places=6)

    def test_sizes(self):
        self.assertIn("1/8", holes.taper_sizes("npt"))
        self.assertIn("1 1/2", holes.taper_sizes("bspt"))
        self.assertIsNone(holes.taper_thread("npt", "9/16"))


class ClassTests(unittest.TestCase):
    def test_m6_6h(self):
        # ISO 965-2, M6x1 6H: D2 5.350 .. 5.500, D1 4.917 .. 5.153 (the formulas give the
        # zone within about 3 % of the rounded tables)
        d = tables.find("iso", "M6x1")
        z = tables.class_zone(d, "6H", True)
        self.assertAlmostEqual(z["pitch"], 5.425, delta=0.003)
        self.assertAlmostEqual(z["minor"], 5.035, delta=0.004)
        self.assertAlmostEqual(z["shift"], z["pitch"] - (6.0 - 0.649519), places=9)

    def test_m6_6g(self):
        # M6x1 6g: d2 5.212 .. 5.324, d 5.794 .. 5.974
        d = tables.find("iso", "M6x1")
        z = tables.class_zone(d, "6g", False)
        self.assertAlmostEqual(z["pitch"], 5.268, delta=0.002)
        self.assertAlmostEqual(z["major"], 5.884, delta=0.003)
        self.assertLess(z["shift"], 0.0)

    def test_classes_order(self):
        d = tables.find("iso", "M10x1.5")
        shifts = [tables.class_zone(d, c, True)["shift"] for c in ("4H", "5H", "6H", "7H")]
        self.assertEqual(shifts, sorted(shifts))
        self.assertGreater(
            tables.class_zone(d, "6G", True)["shift"], tables.class_zone(d, "6H", True)["shift"]
        )
        self.assertLess(
            tables.class_zone(d, "6e", False)["shift"], tables.class_zone(d, "6h", False)["shift"]
        )

    def test_unified(self):
        # ASME B1.1, 1/4-20 UNC: 2A pitch dia 0.2127 .. 0.2164, 2B 0.2175 .. 0.2224 (in)
        d = tables.find("ansi", "1/4-20 UNC")
        a = tables.class_zone(d, "2A", False)
        b = tables.class_zone(d, "2B", True)
        self.assertAlmostEqual(a["pitch"] / 25.4, (0.2127 + 0.2164) / 2.0, delta=0.0002)
        self.assertAlmostEqual(b["pitch"] / 25.4, (0.2175 + 0.2224) / 2.0, delta=0.0002)
        three = tables.class_zone(d, "3A", False)
        self.assertGreater(three["shift"], a["shift"])  # 3A has no allowance

    def test_unknown_class_is_basic(self):
        d = tables.find("iso", "M6x1")
        z = tables.class_zone(d, "", False)
        self.assertEqual(z["shift"], 0.0)
        self.assertEqual(z["major"], 6.0)

    def test_class_radii(self):
        d = tables.find("iso", "M6x1")
        z = tables.class_zone(d, "6g", False)
        radius, limit = core.class_radii(6.0, False, z)
        self.assertAlmostEqual(radius, (6.0 + z["shift"]) / 2.0)
        self.assertAlmostEqual(limit, z["major"] / 2.0)

    def test_limit_in_removed_area(self):
        # turning a shaft to a smaller radius takes the ring between them as well
        plain = core.removed_area(3.0, 1.0, False, 3.0)
        turned = core.removed_area(3.0, 1.0, False, 3.0, limit=2.95)
        groove = 2.0 * math.pi * core._integral_rw(3.0, 1.0, False, 0.0, 2.95)
        self.assertAlmostEqual(turned, math.pi * (9.0 - 2.95**2) + groove)
        self.assertGreater(turned, plain)
        bored = core.removed_area(3.0, 1.0, True, 2.4, limit=2.5)
        self.assertGreater(bored, core.removed_area(3.0, 1.0, True, 2.5, limit=2.5))


if __name__ == "__main__":
    unittest.main()
