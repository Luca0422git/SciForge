# SPDX-License-Identifier: LGPL-2.1-or-later
"""The design timeline's logic (sciforge/timeline_core.py). Runs without FreeCAD."""
import os
import sys
import unittest

# The module root (src/Mod/SciForge) holds the sciforge package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import timeline_core as core  # noqa: E402

SKETCH = "Sketcher::SketchObject"
PAD = "PartDesign::Pad"
FILLET = "PartDesign::Fillet"
PLANE = "PartDesign::Plane"


def feat(name, type_id, key, body="Body", deps=(), **extra):
    row = {"name": name, "label": name, "type_id": type_id, "key": key, "body": body}
    row["deps"] = list(deps)
    row.update(extra)
    return row


def one_body():
    return [
        feat("Sketch", SKETCH, 1),
        feat("Pad", PAD, 2, deps=["Sketch"]),
        feat("Sketch001", SKETCH, 3, deps=["Pad"]),  # sketch on a face of Pad
        feat("Pad001", PAD, 4, deps=["Sketch001"]),
        feat("Fillet", FILLET, 5),
    ]


def build(features=None, tip="Fillet"):
    return core.build(features or one_body(), {"Body": tip})


class ClassifyTests(unittest.TestCase):
    def test_known_and_fallbacks(self):
        self.assertEqual(core.classify(PAD), "extrude")
        self.assertEqual(core.classify("PartDesign::Pocket"), "extrude")  # Fusion naming
        self.assertEqual(core.classify("PartDesign::LinearPattern"), "pattern_rect")
        self.assertEqual(core.classify("PartDesign::AdditiveBox"), "box")
        self.assertEqual(core.classify("PartDesign::AdditiveWedge"), "primitive")
        self.assertEqual(core.classify("Something::Else"), "other")

    def test_sciforge_types(self):
        self.assertEqual(core.classify("SciForge::PressPull"), "presspull")
        self.assertEqual(core.classify("SciForge::Coil"), "coil")
        self.assertEqual(core.classify("SciForge::SplitBody"), "split_body")
        self.assertEqual(core.classify("SciForge::WeirdThing"), "other")
        self.assertEqual(core.title_base("SciForge::WeirdThing", "other"), "Weird Thing")

    def test_every_kind_has_a_title_and_icon(self):
        for kind in core.KINDS:
            self.assertTrue(core.icon_for(kind))
            self.assertTrue(core.KINDS[kind][0])

    def test_default_labels(self):
        self.assertTrue(core.is_default_label("Pad001", "Pad001"))
        self.assertTrue(core.is_default_label("Extrude", "Extrude003"))
        self.assertFalse(core.is_default_label("Base plate", "Pad"))


class BuildTests(unittest.TestCase):
    def test_titles_count_per_kind(self):
        tl = build()
        self.assertEqual(
            [i.title for i in tl.items],
            ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2", "Fillet 1"],
        )

    def test_renamed_step_shows_its_name(self):
        rows = one_body()
        rows[3]["label"] = "Boss"
        tl = build(rows)
        self.assertEqual(tl.items[3].display, "Boss")
        self.assertEqual(tl.items[3].title, "Extrude 2")

    def test_marker_at_end(self):
        tl = build()
        self.assertTrue(tl.at_end)
        self.assertEqual({i.state for i in tl.items}, {"done"})

    def test_rolled_back_marker_sits_before_first_inactive_solid(self):
        tl = build(tip="Pad")
        self.assertEqual(tl.marker, 3)  # Sketch, Pad, Sketch001 | Pad001, Fillet
        self.assertEqual(
            [i.state for i in tl.items], ["done", "done", "done", "rolled_back", "rolled_back"]
        )

    def test_status_and_suppressed(self):
        rows = one_body()
        rows[4]["error"] = "Edges are gone"
        rows[3]["suppressed"] = True
        tl = build(rows)
        self.assertEqual(tl.items[4].status, "error")
        self.assertIn("Edges are gone", core.tooltip(tl.items[4]))
        self.assertTrue(tl.items[3].suppressed)
        self.assertIn("Suppressed", core.tooltip(tl.items[3]))

    def test_empty(self):
        tl = core.build([], {})
        self.assertEqual(tl.items, ())
        self.assertIsNone(core.tips_for_step(tl, "end"))


class MultiBodyTests(unittest.TestCase):
    """One timeline for the whole design, in the order things were made."""

    ROWS = [
        feat("Sketch", SKETCH, 1, "A"),
        feat("Pad", PAD, 2, "A", ["Sketch"]),
        feat("Sketch001", SKETCH, 5, "B"),
        feat("Pad001", PAD, 6, "B", ["Sketch001"]),
        feat("Fillet", FILLET, 7, "A"),
    ]

    def test_merged_by_creation_order(self):
        tl = core.build(self.ROWS, {"A": "Fillet", "B": "Pad001"})
        self.assertEqual(tl.names(), ["Sketch", "Pad", "Sketch001", "Pad001", "Fillet"])

    def test_body_order_is_kept(self):
        rows = [dict(r) for r in self.ROWS]
        rows[0], rows[1] = rows[1], rows[0]  # body A's list says Pad, then Sketch
        tl = core.build(rows, {"A": "Fillet", "B": "Pad001"})
        names = tl.names()
        self.assertLess(names.index("Pad"), names.index("Sketch"))

    def test_step_inserted_at_marker_stays_there(self):
        # Body A rolled back to Pad; a new sketch (key 9) was inserted after it.
        rows = [
            feat("Sketch", SKETCH, 1, "A"),
            feat("Pad", PAD, 2, "A"),
            feat("New", SKETCH, 9, "A"),
            feat("Pad002", PAD, 3, "A"),
            feat("Sketch001", SKETCH, 5, "B"),
        ]
        tl = core.build(rows, {"A": "Pad"})
        self.assertEqual(tl.names(), ["Sketch", "Pad", "New", "Pad002", "Sketch001"])

    def test_roll_back_sets_every_body(self):
        tl = core.build(self.ROWS, {"A": "Fillet", "B": "Pad001"})
        self.assertEqual(core.tips_for_item(tl, 1), {"A": "Pad", "B": None})
        self.assertEqual(core.tips_for_item(tl, 3), {"A": "Pad", "B": "Pad001"})

    def test_outside_any_body_never_rolls_back(self):
        rows = self.ROWS + [feat("Box", "Part::Box", 8, None)]
        tl = core.build(rows, {"A": "Pad", "B": None})
        box = tl.find("Box")
        self.assertEqual(box.state, "done")
        self.assertFalse(box.solid)


class MarkerTests(unittest.TestCase):
    def test_roll_here(self):
        tl = build()
        self.assertEqual(core.tips_for_item(tl, 1), {"Body": "Pad"})
        # A sketch rolls to the solid before it.
        self.assertEqual(core.tips_for_item(tl, 2), {"Body": "Pad"})
        self.assertIsNone(core.tips_for_item(tl, 4))  # already there

    def test_drop_before_everything_snaps_after_first_solid(self):
        self.assertEqual(core.tips_for_slot(build(), 0), {"Body": "Pad"})

    def test_drop_at_end_rolls_forward(self):
        self.assertEqual(core.tips_for_slot(build(tip="Pad"), 5), {"Body": "Fillet"})

    def test_drop_where_it_already_is(self):
        self.assertIsNone(core.tips_for_slot(build(tip="Pad001"), 4))

    def test_steps_skip_sketches(self):
        tl = build()
        self.assertEqual(core.tips_for_step(tl, "prev"), {"Body": "Pad001"})
        self.assertEqual(core.tips_for_step(tl, "start"), {"Body": "Pad"})
        self.assertIsNone(core.tips_for_step(tl, "next"))
        self.assertIsNone(core.tips_for_step(tl, "end"))

    def test_steps_from_the_middle(self):
        tl = build(tip="Pad001")
        self.assertEqual(core.tips_for_step(tl, "next"), {"Body": "Fillet"})
        self.assertEqual(core.tips_for_step(tl, "prev"), {"Body": "Pad"})
        self.assertEqual(core.tips_for_step(tl, "end"), {"Body": "Fillet"})
        self.assertTrue(core.can_roll_forward(tl))

    def test_nothing_before_the_first_solid(self):
        self.assertIsNone(core.tips_for_step(build(tip="Pad"), "prev"))
        self.assertIsNone(core.tips_for_step(build(tip="Pad"), "start"))


class MoveTests(unittest.TestCase):
    def test_fillet_can_move_earlier(self):
        plan = core.plan_move(build(), "Fillet", 2)
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.order, ("Sketch", "Pad", "Fillet", "Sketch001", "Pad001"))
        self.assertEqual(plan.body_orders["Body"], plan.order)
        self.assertEqual(plan.keys, {})  # one body: no creation-order change needed
        self.assertTrue(plan.marker_at_end)

    def test_cannot_move_before_what_it_uses(self):
        plan = core.plan_move(build(), "Pad001", 2)
        self.assertFalse(plan.ok)
        self.assertIn("uses Sketch 2", plan.reason)

    def test_cannot_move_after_its_user(self):
        plan = core.plan_move(build(), "Sketch", 3)
        self.assertFalse(plan.ok)
        self.assertIn("Extrude 1 uses Sketch 1", plan.reason)

    def test_no_change_is_not_an_error(self):
        plan = core.plan_move(build(), "Fillet", 5)
        self.assertFalse(plan.ok)
        self.assertEqual(plan.reason, "")

    def test_rebased_steps(self):
        tl = build()
        plan = core.plan_move(tl, "Fillet", 2)
        self.assertEqual(core.rebased(tl, plan), {"Fillet": "Pad", "Pad001": "Fillet"})

    def test_marker_keeps_its_place_when_rolled_back(self):
        tl = build(tip="Pad001")  # marker before Fillet
        plan = core.plan_move(tl, "Fillet", 2)  # an inactive step moves before the marker
        self.assertTrue(plan.ok)
        self.assertFalse(plan.marker_at_end)
        self.assertEqual(plan.marker_count, 3)

    def test_move_between_bodies_changes_creation_keys(self):
        rows = [
            feat("a1", SKETCH, 1, "A"),
            feat("a2", PAD, 2, "A", ["a1"]),
            feat("b1", SKETCH, 3, "B"),
        ]
        tl = core.build(rows, {"A": "a2", "B": None})
        plan = core.plan_move(tl, "b1", 0)
        self.assertTrue(plan.ok)
        self.assertEqual(plan.order, ("b1", "a1", "a2"))
        moved = [dict(r) for r in rows]
        for r in moved:
            r["key"] = plan.keys.get(r["name"], r["key"])
        self.assertEqual(core.build(moved, {"A": "a2"}).names(), ["b1", "a1", "a2"])


class GroupTests(unittest.TestCase):
    def grouped(self, expanded=(), tip="Fillet"):
        rows = one_body()
        for r in rows[2:4]:
            r["group"] = "g1"
            r["group_name"] = "Boss"
        return core.segments(core.build(rows, {"Body": tip}), expanded)

    def test_group_shows_as_one_folder(self):
        segs = self.grouped()
        self.assertEqual([s[0] for s in segs], ["step", "step", "group", "step"])
        _kind, gid, name, members, opened = segs[2]
        self.assertEqual(
            (gid, name, [m.name for m in members], opened),
            ("g1", "Boss", ["Sketch001", "Pad001"], False),
        )

    def test_open_group(self):
        self.assertTrue(self.grouped(expanded={"g1"})[2][4])

    def test_marker_inside_opens_it(self):
        rows = one_body()
        for r in rows[2:5]:
            r["group"] = "g1"
        tl = core.build(rows, {"Body": "Pad001"})
        self.assertEqual(tl.marker, 4)
        self.assertTrue(core.segments(tl)[2][4])

    def test_can_group(self):
        tl = build()
        self.assertTrue(core.can_group(tl, ["Sketch001", "Pad001"])[0])
        ok, reason = core.can_group(tl, ["Sketch", "Pad001"])
        self.assertFalse(ok)
        self.assertIn("neighbouring", reason)
        self.assertFalse(core.can_group(tl, ["Pad"])[0])
        self.assertEqual(core.new_group_id(tl), "g1")
        self.assertEqual(core.new_group_name(tl), "Group 1")

    def test_moving_out_of_a_group_leaves_it(self):
        rows = one_body()
        for r in rows[2:5]:
            r["group"] = "g1"
        tl = core.build(rows, {"Body": "Fillet"})
        plan = core.plan_move(tl, "Fillet", 1)  # out of the group, before Pad
        self.assertEqual(core.groups_after_move(tl, plan), {"Fillet": ""})

    def test_dropping_inside_a_group_joins_it(self):
        rows = one_body()
        for r in rows[1:3]:
            r["group"] = "g1"  # Pad, Sketch001
        tl = core.build(rows, {"Body": "Fillet"})
        plan = core.plan_move(tl, "Fillet", 2)  # between Pad and Sketch001
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(core.groups_after_move(tl, plan), {"Fillet": "g1"})


if __name__ == "__main__":
    unittest.main()
