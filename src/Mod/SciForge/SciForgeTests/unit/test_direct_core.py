# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design history on/off and base features: the pure logic (direct_core.py). Runs without
FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import direct_core as core  # noqa: E402


def row(name, solid=True, base=False, frozen=False):
    return {"name": name, "solid": solid, "base": base, "frozen": frozen}


class MenuTests(unittest.TestCase):
    def test_the_entry_switches_the_mode(self):
        self.assertEqual(core.history_menu_label(True), "Do Not Capture Design History")
        self.assertEqual(core.history_menu_label(False), "Capture Design History")


class FreezeTests(unittest.TestCase):
    def test_a_parametric_body_freezes_every_solid_step(self):
        rows = [
            row("Sketch", solid=False),
            row("Pad"),
            row("Sketch001", solid=False),
            row("Pocket"),
        ]
        self.assertEqual(core.steps_to_freeze(rows, "Pocket"), ["Pad", "Pocket"])

    def test_steps_after_the_base_up_to_the_tip(self):
        rows = [
            row("BaseFeature", base=True, frozen=True),
            row("Sketch", solid=False),
            row("Pad"),
            row("Fillet"),
        ]
        self.assertEqual(core.steps_to_freeze(rows, "Fillet"), ["Pad", "Fillet"])

    def test_steps_after_the_tip_stay(self):
        # An edited base feature: the steps after the marker build on the new base.
        rows = [
            row("BaseFeature", base=True, frozen=True),
            row("PressPull"),  # made while editing, at the marker
            row("Hole"),  # was after the base feature already
        ]
        self.assertEqual(core.steps_to_freeze(rows, "PressPull"), ["PressPull"])

    def test_a_frozen_body_has_nothing_to_freeze(self):
        rows = [row("BaseFeature", base=True, frozen=True), row("Sketch", solid=False)]
        self.assertEqual(core.steps_to_freeze(rows, "BaseFeature"), [])
        self.assertFalse(core.needs_freeze(rows, "BaseFeature"))

    def test_a_base_that_follows_another_feature_is_frozen_too(self):
        # The body of a Create Copy or a Split Body piece: its base is not plain data yet.
        rows = [row("BaseFeature", base=True, frozen=False)]
        self.assertTrue(core.needs_freeze(rows, "BaseFeature"))

    def test_an_unknown_tip_changes_nothing(self):
        rows = [row("Pad")]
        self.assertEqual(core.steps_to_freeze(rows, "Elsewhere"), [])

    def test_no_tip_means_everything(self):
        rows = [row("BaseFeature", base=True, frozen=True), row("Pad"), row("Fillet")]
        self.assertEqual(core.steps_to_freeze(rows), ["Pad", "Fillet"])


class SessionTests(unittest.TestCase):
    def test_new_bodies_join_the_base_feature(self):
        known = {"Body", "Body001"}
        current = ["Body", "Body001", "Body002"]
        self.assertEqual(core.session_members(known, current, set()), ["Body002"])

    def test_edited_base_feature_keeps_its_bodies(self):
        known = {"Body"}
        current = ["Body", "Body001", "Body002"]
        self.assertEqual(core.session_members(known, current, {"Body001"}), ["Body001", "Body002"])

    def test_deleted_members_are_gone(self):
        self.assertEqual(core.session_members(set(), [], {"Body001"}), [])

    def test_base_ids(self):
        self.assertEqual(core.next_base_id([]), "bf1")
        self.assertEqual(core.next_base_id(["bf1", "bf2"]), "bf3")
        self.assertEqual(core.next_base_id(["bf2"]), "bf1")

    def test_marker_after_an_edit(self):
        self.assertEqual(core.marker_after_edit(True, 2, 7), 7)
        self.assertEqual(core.marker_after_edit(False, 3, 7), 3)
        self.assertEqual(core.marker_after_edit(False, 9, 7), 7)
        self.assertEqual(core.marker_after_edit(False, 0, 7), 1)


class DeleteRefusalTests(unittest.TestCase):
    def test_a_lone_flat_face(self):
        text = core.delete_refusal(["Plane"], 6)
        self.assertTrue(text.startswith("This face cannot be deleted"))
        self.assertIn("Replace Face", text)

    def test_several_faces(self):
        text = core.delete_refusal(["Plane", "Cylinder"], 10)
        self.assertTrue(text.startswith("These 2 faces cannot be deleted"))
        self.assertIn("all the faces of the feature", text)

    def test_every_face(self):
        self.assertIn("Delete the body", core.delete_refusal(["Plane"] * 6, 6))


if __name__ == "__main__":
    unittest.main()
