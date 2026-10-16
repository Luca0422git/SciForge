# SPDX-License-Identifier: LGPL-2.1-or-later
"""The angle snap of the turn handles (sciforge/angle_snap_core.py): 0 / 45 / 90... pull the
angle within a few pixels along the ring, Ctrl is free, Incremental Move keeps its steps,
the wheel's ticks. Runs without FreeCAD."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import angle_snap_core as core  # noqa: E402


class Tolerance(unittest.TestCase):
    def test_pixels_along_the_ring(self):
        # a ring of 200 px: 6 px of arc = 1.72 degrees
        self.assertAlmostEqual(core.tolerance_degrees(200.0), math.degrees(6.0 / 200.0))

    def test_five_degrees_off_stays_free(self):
        # a small ring pulls at most 4 degrees: 40 and 85 stay (drags that mean them)
        self.assertEqual(core.snap(40.0, core.tolerance_degrees(30.0)), (40.0, None))
        self.assertEqual(core.snap(85.0, core.tolerance_degrees(30.0)), (85.0, None))

    def test_clamped(self):
        self.assertEqual(core.tolerance_degrees(20.0), core.MAX_TOLERANCE)
        self.assertEqual(core.tolerance_degrees(5000.0), core.MIN_TOLERANCE)
        self.assertEqual(core.tolerance_degrees(0.0), core.MAX_TOLERANCE)
        self.assertEqual(core.tolerance_degrees(None), core.MAX_TOLERANCE)


class Snap(unittest.TestCase):
    def test_pulls_onto_45_multiples(self):
        self.assertEqual(core.snap(43.0, 3.0), (45.0, 45.0))
        self.assertEqual(core.snap(-88.5, 3.0), (-90.0, -90.0))
        self.assertEqual(core.snap(181.0, 3.0), (180.0, 180.0))
        self.assertEqual(core.snap(1.5, 3.0), (0.0, 0.0))
        self.assertEqual(core.snap(359.0, 3.0), (360.0, 360.0))

    def test_free_between(self):
        self.assertEqual(core.snap(30.0, 3.0), (30.0, None))
        self.assertEqual(core.snap(41.9, 3.0), (41.9, None))

    def test_ctrl_is_free(self):
        self.assertEqual(core.snap(43.0, 3.0, free=True), (43.0, None))
        self.assertEqual(core.snap(45.0, 3.0, free=True), (45.0, 45.0))

    def test_incremental_steps(self):
        self.assertEqual(core.snap(37.0, 3.0, step=5.0), (35.0, None))
        self.assertEqual(core.snap(44.0, 3.0, step=15.0), (45.0, 45.0))
        self.assertEqual(core.snap(37.0, 3.0, step=5.0, free=True), (37.0, None))


class Wheel(unittest.TestCase):
    def test_ticks(self):
        ticks = core.ticks()
        self.assertEqual(len(ticks), 24)
        self.assertEqual([d for d, long in ticks if long], [0, 45, 90, 135, 180, 225, 270, 315])

    def test_text(self):
        self.assertEqual(core.text(45.0), "45.0 deg")
        self.assertEqual(core.text(-0.01), "0.0 deg")
        self.assertEqual(core.text(37.26), "37.3 deg")

    def test_on_snap(self):
        self.assertEqual(core.on_snap(90.0), 90.0)
        self.assertIsNone(core.on_snap(30.0))


if __name__ == "__main__":
    unittest.main()
