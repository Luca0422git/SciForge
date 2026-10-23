# SPDX-License-Identifier: LGPL-2.1-or-later
"""Opacity Control's numbers (opacity_core). Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import opacity_core as core  # noqa: E402


class OpacityTests(unittest.TestCase):
    def test_clamp_keeps_percentages_and_refuses_junk(self):
        self.assertEqual(core.clamp(40), 40)
        self.assertEqual(core.clamp(39.6), 40)
        self.assertEqual(core.clamp(-5), 0)
        self.assertEqual(core.clamp(250), 100)
        self.assertEqual(core.clamp("60"), 60)
        self.assertEqual(core.clamp(None), core.DEFAULT)
        self.assertEqual(core.clamp("half"), core.DEFAULT)

    def test_a_body_shows_its_own_times_its_components(self):
        self.assertEqual(core.effective(100), 100)
        self.assertEqual(core.effective(60), 60)
        self.assertEqual(core.effective(100, [40]), 40)  # the component rules a solid body
        self.assertEqual(core.effective(50, [40]), 20)
        self.assertEqual(core.effective(50, [50, 50]), 12)  # 12.5 rounds to 12 (half to even)
        self.assertEqual(core.effective(80, [100, 100]), 80)
        self.assertEqual(core.effective(0, [100]), 0)

    def test_transparency_is_freecads_other_way_round(self):
        self.assertEqual(core.transparency(100), 0)
        self.assertEqual(core.transparency(0), 100)
        self.assertEqual(core.transparency(40), 60)

    def test_a_see_through_look_stays_see_through(self):
        # glass 60 % see-through at 50 % opacity: 20 % of it shows
        self.assertEqual(core.transparency(50, 60), 80)
        self.assertEqual(core.transparency(100, 60), 60)
        self.assertEqual(core.transparency(0, 60), 100)

    def test_menu_lists_fusions_steps_and_ticks_the_current_one(self):
        entries = core.menu_entries(60)
        self.assertEqual([t for t, _v, _c in entries], ["100%", "80%", "60%", "40%", "20%"])
        self.assertEqual([v for _t, v, c in entries if c], [60])

    def test_a_custom_value_shows_ticked_in_its_place(self):
        entries = core.menu_entries(55)
        self.assertEqual([v for _t, v, _c in entries], [100, 80, 60, 55, 40, 20])
        self.assertEqual([v for _t, v, c in entries if c], [55])

    def test_rows_that_differ_tick_nothing(self):
        self.assertIsNone(core.common([100, 40]))
        self.assertEqual(core.common([40, 40]), 40)
        entries = core.menu_entries(None)
        self.assertFalse(any(c for _t, _v, c in entries))
        self.assertEqual(len(entries), len(core.PRESETS))

    def test_label(self):
        self.assertEqual(core.label(20), "20%")
        self.assertEqual(core.label(130), "100%")


if __name__ == "__main__":
    unittest.main()
