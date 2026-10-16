# SPDX-License-Identifier: LGPL-2.1-or-later
"""shortcuts_core: changing a command's key like Fusion's Change Keyboard Shortcut."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sciforge import shortcuts_core as core  # noqa: E402

DEFAULTS = {"SciForge_Extrude": "E", "PartDesign_Fillet": "F", "Std_Undo": "Ctrl+Z", "X_Box": ""}
PREFERRED = {"PartDesign_Fillet": "SciForge_Fillet"}


class Normalise(unittest.TestCase):
    def test_same_key_written_differently(self):
        self.assertEqual(core.normalise("ctrl + z"), core.normalise("Ctrl+Z"))
        self.assertEqual(core.normalise("Z+Ctrl"), "CTRL+Z")
        self.assertEqual(core.normalise("Del"), core.normalise("Delete"))
        self.assertEqual(core.normalise(""), "")

    def test_one_key_only(self):
        self.assertTrue(core.is_single_key("E"))
        self.assertTrue(core.is_single_key("Shift+E"))
        self.assertTrue(core.is_single_key("F6"))
        self.assertFalse(core.is_single_key("Ctrl"))
        self.assertFalse(core.is_single_key("Ctrl+K, Ctrl+C"))
        self.assertFalse(core.is_single_key(""))


class Assign(unittest.TestCase):
    def test_new_key(self):
        o = core.assign("SciForge_Extrude", "Shift+E", DEFAULTS, {}, PREFERRED)
        self.assertEqual(o, {"SciForge_Extrude": "Shift+E"})
        self.assertEqual(core.key_of("SciForge_Extrude", DEFAULTS, o, PREFERRED), "Shift+E")

    def test_sciforge_version_keeps_the_freecad_entry(self):
        o = core.assign("SciForge_Fillet", "G", DEFAULTS, {}, PREFERRED)
        self.assertEqual(o, {"PartDesign_Fillet": "G"})
        self.assertEqual(core.key_of("SciForge_Fillet", DEFAULTS, o, PREFERRED), "G")
        self.assertEqual(core.owners("F", DEFAULTS, o), [])

    def test_taken_key_refused_names_the_owner(self):
        with self.assertRaises(ValueError) as caught:
            core.assign("SciForge_Extrude", "f", DEFAULTS, {}, PREFERRED)
        self.assertIn("PartDesign_Fillet", str(caught.exception))
        self.assertEqual(
            core.conflicts("SciForge_Extrude", "F", DEFAULTS, {}, PREFERRED), ["PartDesign_Fillet"]
        )

    def test_override_takes_it_away(self):
        o = core.assign("SciForge_Extrude", "F", DEFAULTS, {}, PREFERRED, override=True)
        self.assertEqual(o, {"SciForge_Extrude": "F", "PartDesign_Fillet": ""})
        self.assertEqual(core.owners("F", DEFAULTS, o), ["SciForge_Extrude"])
        self.assertEqual(core.key_of("SciForge_Fillet", DEFAULTS, o, PREFERRED), "")

    def test_blank_means_no_key(self):
        o = core.assign("SciForge_Extrude", "", DEFAULTS, {}, PREFERRED)
        self.assertEqual(o, {"SciForge_Extrude": ""})
        self.assertEqual(core.owners("E", DEFAULTS, o), [])

    def test_default_again_keeps_nothing(self):
        o = core.assign("SciForge_Extrude", "Shift+E", DEFAULTS, {}, PREFERRED)
        o = core.assign("SciForge_Extrude", "E", DEFAULTS, o, PREFERRED)
        self.assertEqual(o, {})

    def test_two_keys_refused(self):
        with self.assertRaises(ValueError):
            core.assign("SciForge_Extrude", "Ctrl+K, Ctrl+C", DEFAULTS, {}, PREFERRED)

    def test_a_command_without_a_default(self):
        o = core.assign("SciForge_Coil", "K", DEFAULTS, {}, PREFERRED)
        self.assertEqual(core.key_of("SciForge_Coil", DEFAULTS, o, PREFERRED), "K")


class Reset(unittest.TestCase):
    def test_reset_gives_the_default_back(self):
        o = core.assign("SciForge_Extrude", "Shift+E", DEFAULTS, {}, PREFERRED)
        o = core.reset("SciForge_Extrude", DEFAULTS, o, PREFERRED)
        self.assertEqual(o, {})
        self.assertEqual(core.key_of("SciForge_Extrude", DEFAULTS, o, PREFERRED), "E")

    def test_reset_takes_the_key_back_from_an_override(self):
        o = core.assign("SciForge_Extrude", "Shift+E", DEFAULTS, {}, PREFERRED)
        o = core.assign("SciForge_Coil", "E", DEFAULTS, o, PREFERRED)  # E was free
        o = core.reset("SciForge_Extrude", DEFAULTS, o, PREFERRED)
        self.assertEqual(core.owners("E", DEFAULTS, o), ["SciForge_Extrude"])
        self.assertEqual(core.key_of("SciForge_Coil", DEFAULTS, o, PREFERRED), "")

    def test_reset_of_a_command_that_lost_its_key(self):
        o = core.assign("SciForge_Extrude", "F", DEFAULTS, {}, PREFERRED, override=True)
        o = core.reset("SciForge_Fillet", DEFAULTS, o, PREFERRED)
        self.assertEqual(core.owners("F", DEFAULTS, o), ["PartDesign_Fillet"])
        self.assertEqual(core.key_of("SciForge_Extrude", DEFAULTS, o, PREFERRED), "")

    def test_reset_all(self):
        self.assertEqual(core.reset_all(), {})


if __name__ == "__main__":
    unittest.main()
