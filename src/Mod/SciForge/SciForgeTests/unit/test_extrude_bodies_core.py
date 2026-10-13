# SPDX-License-Identifier: LGPL-2.1-or-later
"""An Extrude through several bodies: the dialog row's words, clicks on bodies, the
automatic operation and the plan for the hidden follower steps
(sciforge/extrude_bodies_core.py). Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import extrude_bodies_core as core  # noqa: E402


class RowTextTests(unittest.TestCase):
    def test_label_follows_the_operation(self):
        self.assertEqual(core.row_label("cut"), "Bodies to Cut")
        self.assertEqual(core.row_label("join"), "Bodies to Join")
        self.assertEqual(core.row_label("intersect"), "Bodies to Intersect")
        self.assertEqual(core.row_label("new_body"), "")

    def test_count(self):
        self.assertEqual(core.count_text(0), "")
        self.assertEqual(core.count_text(1), "1 body")
        self.assertEqual(core.count_text(2), "2 bodies")

    def test_names(self):
        self.assertEqual(core.names_text(["Body1", "Body2"]), "Body1, Body2")
        self.assertEqual(core.names_text([]), "")
        many = ["B%d" % i for i in range(9)]
        self.assertEqual(core.names_text(many), "B0, B1, B2, B3, B4, B5 and 3 more")


class ClickTests(unittest.TestCase):
    def test_click_drops_then_adds_back(self):
        touched = ["Body1", "Body2"]
        excluded, what = core.toggle(touched, set(), "Body2")
        self.assertEqual((excluded, what), ({"Body2"}, "dropped"))
        self.assertEqual(core.participants(touched, excluded), ["Body1"])
        excluded, what = core.toggle(touched, excluded, "Body2")
        self.assertEqual((excluded, what), (set(), "added"))
        self.assertEqual(core.participants(touched, excluded), ["Body1", "Body2"])

    def test_body_out_of_the_way_is_not_taken(self):
        excluded, what = core.toggle(["Body1"], set(), "Body3")
        self.assertEqual((excluded, what), (set(), "not_in_way"))

    def test_edit_starts_from_the_saved_list(self):
        self.assertEqual(core.excluded_for_edit(["B1", "B2", "B3"], ["B1", "B3"]), {"B2"})
        self.assertEqual(core.excluded_for_edit(["B1", "B2"], None), set())

    def test_a_body_newly_in_the_way_is_taken(self):
        excluded = core.excluded_for_edit(["B1"], ["B1"])
        self.assertEqual(core.participants(["B1", "B2"], excluded), ["B1", "B2"])


class AutoOperationTests(unittest.TestCase):
    def test_starting_inside_a_body_cuts(self):
        self.assertEqual(core.auto_operation(True, True), "cut")

    def test_touching_joins(self):
        self.assertEqual(core.auto_operation(False, True), "join")

    def test_nothing_touched_is_a_new_body(self):
        self.assertEqual(core.auto_operation(False, False), "new_body")

    def test_symmetric_never_cuts_by_itself(self):
        self.assertEqual(core.auto_operation(True, True, symmetric=True), "join")


class FollowerPlanTests(unittest.TestCase):
    def test_new_cut_creates_one_per_other_body(self):
        plan = core.follower_plan("cut", "B1", ["B1", "B2", "B3"], [])
        self.assertEqual(plan["create"], ["B2", "B3"])
        self.assertEqual(plan["remove"], [])
        self.assertFalse(plan["new_merge"])

    def test_kept_dropped_and_added(self):
        have = [("F2", "B2", "cut"), ("F3", "B3", "cut")]
        plan = core.follower_plan("cut", "B1", ["B2", "B4"], have)
        self.assertEqual(plan["keep"], {"B2": "F2"})
        self.assertEqual(plan["remove"], ["F3"])
        self.assertEqual(plan["create"], ["B4"])

    def test_join_merges_in_the_lead_body(self):
        have = [("F2", "B2", "cut")]
        plan = core.follower_plan("join", "B1", ["B1", "B2"], have)
        self.assertEqual(plan["remove"], ["F2"])
        self.assertTrue(plan["new_merge"])
        self.assertEqual(plan["create"], [])

    def test_join_keeps_its_merge(self):
        plan = core.follower_plan("join", "B1", ["B2"], [("M", "B1", "merge")])
        self.assertEqual(plan["merge"], "M")
        self.assertFalse(plan["new_merge"])
        self.assertEqual(plan["remove"], [])

    def test_merge_in_an_old_lead_body_goes(self):
        plan = core.follower_plan("join", "B2", ["B1"], [("M", "B1", "merge")])
        self.assertEqual(plan["remove"], ["M"])
        self.assertTrue(plan["new_merge"])

    def test_new_body_has_no_followers(self):
        have = [("F2", "B2", "cut"), ("M", "B1", "merge")]
        plan = core.follower_plan("new_body", "B1", [], have)
        self.assertEqual(sorted(plan["remove"]), ["F2", "M"])
        self.assertEqual(plan["create"], [])
        self.assertFalse(plan["new_merge"])

    def test_one_body_needs_no_follower(self):
        plan = core.follower_plan("cut", "B1", ["B1"], [])
        self.assertEqual(plan["create"], [])


if __name__ == "__main__":
    unittest.main()
