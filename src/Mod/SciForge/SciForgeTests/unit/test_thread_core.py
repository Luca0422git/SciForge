# SPDX-License-Identifier: LGPL-2.1-or-later
"""Thread sizes and thread geometry without FreeCAD: sciforge/thread_tables.py (the ISO / ANSI
tables behind Hole and Thread) and sciforge/thread_core.py (groove, length, volume)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import thread_core as core  # noqa: E402
from sciforge import thread_tables as tables  # noqa: E402


class TableTests(unittest.TestCase):
    def test_labels_like_fusion(self):
        self.assertIsNotNone(tables.find("iso", "M6x1"))
        self.assertIsNotNone(tables.find("iso", "M8x1.25"))
        self.assertIsNotNone(tables.find("ansi", "1/4-20 UNC"))
        self.assertIsNotNone(tables.find("ansi", "1/4-28 UNF"))
        self.assertIsNone(tables.find("iso", "M6x1.0"))  # FreeCAD's name, not Fusion's

    def test_coarse_pitch_first(self):
        found = tables.designations("iso", "8")
        self.assertEqual(found[0].label, "M8x1.25")
        self.assertEqual({d.label for d in found}, {"M8x1.25", "M8x0.75", "M8x1"})
        ansi = tables.designations("ansi", "1/4")
        self.assertEqual([d.label for d in ansi], ["1/4-20 UNC", "1/4-28 UNF", "1/4-32 UNEF"])

    def test_sizes_in_order(self):
        sizes = tables.sizes("iso")
        self.assertLess(sizes.index("5"), sizes.index("6"))
        self.assertLess(sizes.index("6"), sizes.index("10"))
        ansi = tables.sizes("ansi")
        self.assertLess(ansi.index("#10"), ansi.index("1/4"))

    def test_iso_values(self):
        d = tables.find("iso", "M6x1")
        self.assertEqual((d.diameter, d.pitch, d.drill), (6.0, 1.0, 5.0))
        self.assertEqual(d.series, "ISOMetricProfile")
        self.assertEqual(d.freecad, "M6x1.0")
        # basic minor diameter of a nut: D - 2 * 5/8 * H (ISO 68-1)
        self.assertAlmostEqual(d.minor(True), 6.0 - 1.25 * math.sqrt(3) / 2, 12)

    def test_size_from_a_face(self):
        self.assertEqual(tables.closest("iso", 6.0).label, "M6x1")  # a d6 shaft
        self.assertEqual(tables.closest("iso", 5.0, internal=True).label, "M6x1")  # tap drill
        self.assertEqual(tables.closest("iso", 6.8, internal=True).label, "M8x1.25")
        self.assertEqual(tables.closest("ansi", 6.35).label, "1/4-20 UNC")

    def test_fits_and_classes(self):
        self.assertEqual(tables.clearance_fit("ISOMetricProfile", "close"), "Fine")
        self.assertEqual(tables.clearance_fit("ISOMetricProfile", "normal"), "Medium")
        self.assertEqual(tables.clearance_fit("UNC", "loose"), "Loose")
        self.assertEqual(tables.fit_from_freecad("ISOMetricProfile", "Coarse"), "loose")
        self.assertEqual(tables.freecad_class("UNC", "3B"), "3B")
        self.assertEqual(tables.freecad_class("ISOMetricProfile", "6g"), "6H")
        self.assertEqual(tables.default_class("iso", False), "6g")
        self.assertEqual(tables.default_class("ansi", True), "2B")

    def test_freecad_names_round_trip(self):
        for d in tables.all_designations():
            self.assertIs(tables.from_freecad(d.series, d.freecad), d)


class GrooveTests(unittest.TestCase):
    P = 1.0
    H = math.sqrt(3) / 2

    def test_external_groove(self):
        g = core.groove(3.0, self.P, internal=False)
        root, out = g[0][0], g[1][0]
        self.assertAlmostEqual(root, 3.0 - 5 * self.H / 8, 12)
        self.assertAlmostEqual(core.groove_width(3.0, self.P, False, root), self.P / 4, 12)
        # the crest is P/8 wide: the groove is 7P/8 at the major radius
        self.assertAlmostEqual(core.groove_width(3.0, self.P, False, 3.0), 7 * self.P / 8, 12)
        self.assertLess(core.groove_width(3.0, self.P, False, out), self.P)  # turns never touch
        self.assertEqual(core.groove_width(3.0, self.P, False, root - 0.01), 0.0)

    def test_internal_groove(self):
        g = core.groove(3.0, self.P, internal=True)
        self.assertAlmostEqual(g[1][0], 3.0, 12)
        self.assertAlmostEqual(core.groove_width(3.0, self.P, True, 3.0), self.P / 8, 12)
        inner = g[0][0]
        self.assertAlmostEqual(core.groove_width(3.0, self.P, True, inner), 7 * self.P / 8, 12)
        # the flanks are at 60 degrees: the width grows 2 tan 30 per mm
        w1 = core.groove_width(3.0, self.P, True, 2.9)
        w2 = core.groove_width(3.0, self.P, True, 2.8)
        self.assertAlmostEqual((w2 - w1) / 0.1, 2 * math.tan(math.radians(30)), 9)

    def _numeric(self, major, internal, face, n=200000):
        """The same cross-section by brute force: a ring of radius r loses w(r)/P of itself."""
        root = core.groove(major, self.P, internal)[0][0]  # where the groove starts inward
        lo, hi = (face, major) if internal else (root, face)
        step = (hi - lo) / n
        total = 0.0
        for i in range(n):
            r = lo + (i + 0.5) * step
            total += 2 * math.pi * r * core.groove_width(major, self.P, internal, r) / self.P
        return total * step

    def test_removed_area_matches_brute_force(self):
        self.assertAlmostEqual(
            core.removed_area(3.0, self.P, False, 3.0), self._numeric(3.0, False, 3.0), 6
        )
        self.assertAlmostEqual(
            core.removed_area(3.0, self.P, True, 2.5), self._numeric(3.0, True, 2.5), 6
        )

    def test_shaft_turned_down_hole_bored_up(self):
        plain = core.removed_area(3.0, self.P, False, 3.0)
        wider = core.removed_area(3.0, self.P, False, 3.5)
        self.assertAlmostEqual(wider - plain, math.pi * (3.5**2 - 9.0), 9)
        minor = 3.0 - 5 * self.H / 8
        small = core.removed_area(3.0, self.P, True, 2.0)
        at_minor = core.removed_area(3.0, self.P, True, minor)
        self.assertAlmostEqual(small - at_minor, math.pi * (minor**2 - 4.0), 9)

    def test_volume_is_area_times_length(self):
        self.assertAlmostEqual(
            core.removed_volume(3.0, 1.0, False, 3.0, 12.0),
            12.0 * core.removed_area(3.0, 1.0, False, 3.0),
            12,
        )


class SpanTests(unittest.TestCase):
    def test_full_length(self):
        self.assertEqual(core.span(10.0, 22.0), (10.0, 22.0))
        self.assertEqual(core.span(22.0, 10.0), (10.0, 22.0))

    def test_partial_from_either_end(self):
        self.assertEqual(core.span(10.0, 22.0, False, 8.0, 2.0), (12.0, 20.0))
        self.assertEqual(core.span(10.0, 22.0, False, 5.0, 1.0, from_end=True), (16.0, 21.0))

    def test_never_past_the_face(self):
        self.assertEqual(core.span(0.0, 10.0, False, 30.0, 4.0), (4.0, 10.0))
        z0, z1 = core.span(0.0, 10.0, False, 5.0, 20.0)
        self.assertLessEqual(z1 - z0, 0.0)


class HelixTests(unittest.TestCase):
    def test_helix_points(self):
        pts = core.helix_points(3.0, 1.0, 0.0, 2.0, per_turn=8)
        self.assertEqual(len(pts), 17)
        for x, y, _z in pts:
            self.assertAlmostEqual(math.hypot(x, y), 3.0, 12)
        self.assertAlmostEqual(pts[0][2], 0.0)
        self.assertAlmostEqual(pts[-1][2], 2.0)
        # right hand: counter-clockwise going up; left hand: clockwise
        self.assertGreater(pts[2][1], 0.0)
        left = core.helix_points(3.0, 1.0, 0.0, 2.0, per_turn=8, left_hand=True)
        self.assertLess(left[2][1], 0.0)

    def test_empty(self):
        self.assertEqual(core.helix_points(3.0, 1.0, 5.0, 5.0), [])


if __name__ == "__main__":
    unittest.main()
