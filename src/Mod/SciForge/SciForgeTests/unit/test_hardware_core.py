# SPDX-License-Identifier: LGPL-2.1-or-later
"""The hardware library's tables and rules without FreeCAD: sciforge/hardware_core.py
(INSERT > Hardware...). The numbers checked are the ISO standards' own."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import hardware_core as core  # noqa: E402

SHCS = {"standard": "iso4762", "size": "3", "length": 10.0}


class TableTests(unittest.TestCase):
    def test_iso_4762_m3(self):
        d = core.dims("iso4762", "3")
        self.assertEqual((d["d"], d["dk"], d["k"], d["s"]), (3.0, 5.5, 3.0, 2.5))
        self.assertEqual(d["t"], 1.3)

    def test_iso_4762_other_sizes(self):
        self.assertEqual(core.dims("iso4762", "8")["dk"], 13.0)
        self.assertEqual(core.dims("iso4762", "2.5")["s"], 2.0)
        self.assertEqual(core.sizes("iso4762"), ["2", "2.5", "3", "4", "5", "6", "8"])

    def test_iso_4032_m3_nut(self):
        d = core.dims("iso4032", "3")
        self.assertEqual((d["s"], d["m"]), (5.5, 2.4))
        self.assertAlmostEqual(d["e"], 5.5 * 2 / math.sqrt(3))

    def test_iso_7089_m3_washer(self):
        d = core.dims("iso7089", "3")
        self.assertEqual((d["d1"], d["d2"], d["h"]), (3.2, 7.0, 0.5))

    def test_iso_10642_head_is_a_90_degree_cone(self):
        for size in core.sizes("iso10642"):
            d = core.dims("iso10642", size)
            self.assertAlmostEqual(d["k"], (d["dk"] - d["d"]) / 2.0, places=9, msg=size)

    def test_iso_7380_starts_at_m3(self):
        self.assertEqual(core.sizes("iso7380")[0], "3")
        with self.assertRaises(core.HardwareError):
            core.dims("iso7380", "2")

    def test_magnets_and_inserts(self):
        self.assertEqual(core.dims("magnet", "6x3"), {"diameter": 6.0, "thickness": 3.0})
        self.assertIn("10x5", core.sizes("magnet"))
        self.assertEqual(core.sizes("magnet")[0], "3x2")
        self.assertEqual(core.sizes("insert"), ["2", "2.5", "3", "4", "5"])
        self.assertEqual(core.dims("insert", "3")["hole"], 4.0)

    def test_labels(self):
        self.assertEqual(core.size_label("iso4762", "2.5"), "M2.5")
        self.assertEqual(core.size_label("magnet", "6x3"), "6 x 3 mm")
        kinds = [k for k, _ in core.KINDS]
        self.assertEqual(kinds, ["screw", "nut", "washer", "insert", "magnet"])
        self.assertEqual(
            [k for k, _ in core.standards("screw")], ["iso4762", "iso7380", "iso10642"]
        )


class LengthTests(unittest.TestCase):
    def test_iso_4762_m3_lengths(self):
        self.assertEqual(core.lengths("iso4762", "3"), [5, 6, 8, 10, 12, 16, 20, 25, 30])
        self.assertEqual(core.lengths("iso4032", "3"), [])

    def test_default_lengths(self):
        found = [core.default_length("iso4762", s) for s in core.sizes("iso4762")]
        self.assertEqual(found, [6, 8, 10, 12, 16, 20, 25])

    def test_length_kept_when_the_size_has_it(self):
        self.assertEqual(core.fit_length("iso4762", "4", 16), 16)
        self.assertEqual(core.fit_length("iso4762", "2", 40), core.default_length("iso4762", "2"))


class NameTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(core.name(SHCS), "M3x10 ISO 4762")
        self.assertEqual(core.name({"standard": "iso4032", "size": "3"}), "M3 ISO 4032")
        self.assertEqual(core.name({"standard": "iso7089", "size": "8"}), "M8 ISO 7089")
        self.assertEqual(core.name({"standard": "insert", "size": "3"}), "M3 Heat-set insert")
        self.assertEqual(core.name({"standard": "magnet", "size": "6x3"}), "Magnet 6x3")
        self.assertEqual(
            core.name({"standard": "iso10642", "size": "5", "length": 12.0}), "M5x12 ISO 10642"
        )

    def test_defaults_fill_in(self):
        o = core.with_defaults({"kind": "magnet", "standard": "magnet"})
        self.assertEqual(o["size"], "6x3")
        self.assertEqual(core.with_defaults({})["standard"], "iso4762")

    def test_change_standard_keeps_the_size(self):
        o = core.change_standard(dict(SHCS, size="5"), "iso4032")
        self.assertEqual((o["kind"], o["size"]), ("nut", "5"))
        o = core.change_standard(dict(SHCS, size="2"), "iso7380")
        self.assertEqual(o["size"], "3")  # ISO 7380 has no M2
        self.assertFalse(o["sink_head"])  # a button head sits on the face

    def test_check(self):
        with self.assertRaises(core.HardwareError):
            core.check(dict(SHCS, length=0))
        with self.assertRaises(core.HardwareError):
            core.check({"standard": "iso10642", "size": "3", "length": 1.5})
        with self.assertRaises(core.HardwareError):
            core.check(dict(SHCS, fit="snug"))


class HoleTests(unittest.TestCase):
    def test_clearance_m3_normal(self):
        self.assertEqual(core.clearance(SHCS), 3.4)
        self.assertEqual(core.clearance(dict(SHCS, fit="close")), 3.2)
        self.assertEqual(core.clearance(dict(SHCS, fit="loose")), 3.6)

    def test_socket_head_counterbore(self):
        want = core.hole_options(SHCS)
        self.assertEqual(want["tap_type"], "clearance")
        self.assertEqual((want["size"], want["fit"]), ("3", "normal"))
        self.assertEqual(want["hole_type"], "counterbore")
        self.assertEqual((want["cbore_diameter"], want["cbore_depth"]), (6.5, 3.4))
        self.assertEqual(want["extent"], "all")
        self.assertEqual(core.seat(SHCS), -3.4)  # the head at the counterbore's bottom

    def test_head_on_the_face(self):
        o = dict(SHCS, sink_head=False)
        self.assertEqual(core.hole_options(o)["hole_type"], "simple")
        self.assertEqual(core.seat(o), 0.0)

    def test_countersunk(self):
        o = {"standard": "iso10642", "size": "4", "length": 12.0}
        want = core.hole_options(o)
        self.assertEqual(want["hole_type"], "countersink")
        self.assertEqual((want["csink_diameter"], want["csink_angle"]), (8.96, 90.0))
        self.assertEqual(core.seat(o), 0.0)  # flush
        self.assertEqual(core.seat(dict(o, sink_head=False)), 2.48)  # its cone on the face

    def test_button_head_counterbore(self):
        o = {"standard": "iso7380", "size": "4", "length": 10.0, "sink_head": True}
        want = core.hole_options(o)
        self.assertEqual(want["cbore_diameter"], 8.6)  # dk 7.6 + 1
        self.assertAlmostEqual(want["cbore_depth"], 2.6)  # k 2.2 + 0.4

    def test_screw_length_depth(self):
        want = core.hole_options(dict(SHCS, hole_depth="length"))
        self.assertEqual(want["extent"], "distance")
        self.assertAlmostEqual(want["depth"], 13.4)  # 10 under the head + the counterbore
        cs = core.hole_options(
            {"standard": "iso10642", "size": "3", "length": 10.0, "hole_depth": "length"}
        )
        self.assertEqual(cs["depth"], 10.0)  # its length counts the head

    def test_nut_and_washer_get_a_clearance_hole(self):
        for standard in ("iso4032", "iso7089"):
            want = core.hole_options({"standard": standard, "size": "4"})
            self.assertEqual(want["tap_type"], "clearance")
            self.assertEqual(want["hole_type"], "simple")
            self.assertEqual(want["extent"], "all")

    def test_insert_hole(self):
        want = core.hole_options({"standard": "insert", "size": "3"})
        self.assertEqual((want["tap_type"], want["diameter"]), ("simple", 4.0))
        self.assertAlmostEqual(want["depth"], 6.7)  # 5.7 long + 1
        self.assertEqual(want["drill_point"], "flat")

    def test_magnet_pocket(self):
        want = core.hole_options({"standard": "magnet", "size": "6x3"})
        self.assertEqual((want["diameter"], want["depth"]), (6.2, 3.0))
        want = core.hole_options({"standard": "magnet", "size": "6x3", "clearance": 0.3})
        self.assertAlmostEqual(want["diameter"], 6.3)

    def test_no_hole(self):
        self.assertIsNone(core.hole_options(dict(SHCS, make_hole=False)))


class AutoSizeTests(unittest.TestCase):
    def test_clearance_and_tapped_holes(self):
        self.assertEqual(core.size_for_hole("iso4762", 3.4), "3")
        self.assertEqual(core.size_for_hole("iso4762", 4.5), "4")
        self.assertEqual(core.size_for_hole("iso4762", 2.5), "3")  # an M3 tap drill
        self.assertIsNone(core.size_for_hole("iso4762", 30.0))

    def test_counterbore_rim(self):
        self.assertEqual(core.size_for_hole("iso4762", 6.5), "3")
        self.assertTrue(core.head_fits_rim("iso4762", "3", 6.5))
        self.assertFalse(core.head_fits_rim("iso4762", "3", 3.4))

    def test_magnets_and_inserts_prefer_the_current_size(self):
        self.assertEqual(core.size_for_hole("magnet", 6.2, current="6x3"), "6x3")
        self.assertEqual(core.size_for_hole("magnet", 6.2, current="6x2"), "6x2")
        self.assertEqual(core.size_for_hole("insert", 4.0, current="3"), "3")
        self.assertEqual(core.size_for_hole("insert", 5.6), "4")


class VolumeTests(unittest.TestCase):
    def test_socket_head(self):
        hexagon = math.sqrt(3) / 2 * 2.5**2
        expect = math.pi * 2.75**2 * 3 - hexagon * 1.3 + math.pi * 1.5**2 * 10
        self.assertAlmostEqual(core.volume(SHCS), expect)

    def test_simple_parts(self):
        self.assertAlmostEqual(core.volume({"standard": "magnet", "size": "6x3"}), math.pi * 9 * 3)
        self.assertAlmostEqual(
            core.volume({"standard": "iso7089", "size": "3"}), math.pi / 4 * (49 - 3.2**2) * 0.5
        )
        nut = (math.sqrt(3) / 2 * 5.5**2 - math.pi * 2.25) * 2.4
        self.assertAlmostEqual(core.volume({"standard": "iso4032", "size": "3"}), nut)

    def test_button_head_socket_is_less_than_a_full_prism(self):
        dk, k, s, t = 7.6, 2.2, 2.5, 1.3
        cut = core.dome_socket(dk, k, s, t)
        self.assertLess(cut, core.hex_area(s) * t)
        self.assertGreater(cut, 0.8 * core.hex_area(s) * t)
        # a shallow socket well inside the flat top of a very wide dome: nearly a prism
        flat = core.dome_socket(1000.0, 1.0, 2.0, 0.5)
        self.assertAlmostEqual(flat, core.hex_area(2.0) * 0.5, places=4)

    def test_extent(self):
        self.assertEqual(core.extent(SHCS), (-10.0, 3.0))
        self.assertEqual(core.extent({"standard": "magnet", "size": "6x3"}), (-3.0, 0.0))


if __name__ == "__main__":
    unittest.main()
