# SPDX-License-Identifier: LGPL-2.1-or-later
"""ribbon_pins: Fusion's Pin to Toolbar as data."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sciforge import ribbon_pins as pins  # noqa: E402


class Pins(unittest.TestCase):
    def test_pin_appends_once(self):
        s = pins.pin({}, "solid", "create", "Coil")
        s = pins.pin(s, "solid", "create", "Coil")
        s = pins.pin(s, "solid", "create", "Pipe")
        self.assertEqual(pins.pinned(s, "solid", "create"), ["Coil", "Pipe"])
        self.assertTrue(pins.is_pinned(s, "solid", "create", "Pipe"))

    def test_groups_and_tabs_are_separate(self):
        s = pins.pin({}, "solid", "create", "Coil")
        self.assertEqual(pins.pinned(s, "surface", "create"), [])
        self.assertEqual(pins.pinned(s, "solid", "modify"), [])

    def test_a_built_in_big_icon_is_not_pinned_twice(self):
        s = pins.pin({}, "solid", "create", "Extrude", built_in=("Extrude", "Revolve"))
        self.assertEqual(s, {})

    def test_unpin(self):
        s = pins.pin({}, "solid", "create", "Coil")
        s = pins.pin(s, "solid", "create", "Pipe")
        s = pins.unpin(s, "solid", "create", "Coil")
        self.assertEqual(pins.pinned(s, "solid", "create"), ["Pipe"])
        s = pins.unpin(s, "solid", "create", "Pipe")
        self.assertEqual(s, {})

    def test_inputs_not_changed(self):
        s = pins.pin({}, "solid", "create", "Coil")
        before = {k: list(v) for k, v in s.items()}
        pins.pin(s, "solid", "create", "Pipe")
        pins.unpin(s, "solid", "create", "Coil")
        self.assertEqual(s, before)


if __name__ == "__main__":
    unittest.main()
