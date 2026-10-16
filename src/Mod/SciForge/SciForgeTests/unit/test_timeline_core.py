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
        self.assertEqual(core.classify("SciForge::PatternOnPath"), "pattern_path")
        self.assertEqual(
            core.title_base("SciForge::PatternOnPath", "pattern_path"), "Pattern on Path"
        )
        self.assertEqual(core.icon_for("pattern_path"), "pattern_rect")
        self.assertEqual(core.classify("SciForge::Mirror"), "mirror")
        self.assertEqual(core.classify("SciForge::DeleteFace"), "delete_face")
        self.assertEqual(core.icon_for("delete_face"), "delete")
        self.assertEqual(core.classify("SciForge::Combine"), "combine")
        self.assertEqual(core.classify("SciForge::SplitBody"), "split_body")
        self.assertEqual(core.classify("SciForge::MoveCopy"), "move")
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

    def test_numbers_stay_when_steps_move(self):
        """Fusion names a step when it is made: moving it or adding a step before it
        never renames it."""
        rows = one_body()
        moved = [rows[0], rows[1], rows[4], rows[2], rows[3]]  # fillet before the boss
        self.assertEqual(
            [i.display for i in core.build(moved, {"Body": "Pad001"}).items],
            ["Sketch 1", "Extrude 1", "Fillet 1", "Sketch 2", "Extrude 2"],
        )
        # A third extrude inserted at the marker, before the second one.
        inserted = rows[:2] + [feat("Sketch002", SKETCH, 6), feat("Pad002", PAD, 7)] + rows[2:]
        titles = [i.display for i in core.build(inserted, {"Body": "Fillet"}).items]
        self.assertEqual(titles[2:5], ["Sketch 3", "Extrude 3", "Sketch 2"])
        # Numbers count the steps that exist (FreeCAD also counts cancelled previews).
        gone = [r for r in rows if r["name"] != "Pad"]
        self.assertIn("Extrude 1", [i.display for i in core.build(gone, {"Body": "Fillet"}).items])
        skipped = [dict(r) for r in rows]
        skipped[3].update(name="Pad004", label="Pad004")  # four previews were cancelled
        titles = [i.display for i in core.build(skipped, {"Body": "Fillet"}).items]
        self.assertEqual(titles[3], "Extrude 2")

    def test_a_step_rebuilt_as_another_kind_keeps_its_number(self):
        # SciForge's extrude turned into a cut is a new object that keeps the old label.
        rows = [
            feat("Sketch", SKETCH, 1),
            feat("Extrude002", "PartDesign::Pocket", 9, label="Extrude"),
            feat("Sketch001", SKETCH, 3),
            feat("Extrude001", PAD, 4),
        ]
        titles = [i.display for i in core.build(rows, {"Body": "Extrude001"}).items]
        self.assertEqual(titles, ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2"])

    def test_clashing_labels_get_free_numbers(self):
        rows = one_body()
        rows[3] = feat("Extrude", PAD, 4, label="Extrude")  # Pad and Extrude: both "1"
        titles = [i.display for i in core.build(rows, {"Body": "Fillet"}).items]
        self.assertEqual(titles.count("Extrude 1"), 1, titles)
        self.assertIn("Extrude 2", titles)
        self.assertEqual(core.label_number("Sketch", "Sketch"), 0)
        self.assertEqual(core.label_number("Sketch004", "Sketch004"), 4)
        self.assertIsNone(core.label_number("Base plate", "Pad"))

    def test_renamed_step_keeps_its_place_in_the_count(self):
        rows = one_body()
        rows[1]["label"] = "Base"
        tl = core.build(rows, {"Body": "Fillet"})
        self.assertEqual([tl.items[1].title, tl.items[3].title], ["Extrude 1", "Extrude 2"])

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

    def test_drop_before_everything_empties_the_design(self):
        # Fusion's timeline rolled to the beginning: no body has a Tip.
        self.assertEqual(core.tips_for_slot(build(), 0), {"Body": None})
        self.assertEqual(core.tips_for_slot(build(), 1), {"Body": None})
        self.assertEqual(core.tips_for_slot(build(), 2), {"Body": "Pad"})

    def test_marker_before_every_step(self):
        tl = build(tip=None)
        self.assertEqual(tl.marker, 1)  # before the first solid step
        self.assertEqual(tl.find("Sketch").state, "done")
        self.assertEqual(tl.find("Pad").state, "rolled_back")
        self.assertEqual(core.active_count(tl), 0)
        self.assertIsNone(core.tips_for_slot(tl, 1))  # already there
        noted = core.build(one_body(), {"Body": None}, "Sketch")
        self.assertEqual((noted.marker, noted.before), (0, "Sketch"))
        self.assertEqual(noted.find("Sketch").state, "rolled_back")

    def test_drop_at_end_rolls_forward(self):
        self.assertEqual(core.tips_for_slot(build(tip="Pad"), 5), {"Body": "Fillet"})

    def test_drop_where_it_already_is(self):
        self.assertIsNone(core.tips_for_slot(build(tip="Pad001"), 4))

    def test_steps_skip_sketches(self):
        tl = build()
        self.assertEqual(core.tips_for_step(tl, "prev"), {"Body": "Pad001"})
        self.assertEqual(core.tips_for_step(tl, "start"), {"Body": None})
        self.assertIsNone(core.tips_for_step(tl, "next"))
        self.assertIsNone(core.tips_for_step(tl, "end"))

    def test_steps_from_the_middle(self):
        tl = build(tip="Pad001")
        self.assertEqual(core.tips_for_step(tl, "next"), {"Body": "Fillet"})
        self.assertEqual(core.tips_for_step(tl, "prev"), {"Body": "Pad"})
        self.assertEqual(core.tips_for_step(tl, "end"), {"Body": "Fillet"})
        self.assertTrue(core.can_roll_forward(tl))

    def test_back_to_the_beginning(self):
        self.assertEqual(core.tips_for_step(build(tip="Pad"), "prev"), {"Body": None})
        self.assertEqual(core.tips_for_step(build(tip="Pad"), "start"), {"Body": None})
        empty = build(tip=None)
        self.assertIsNone(core.tips_for_step(empty, "prev"))
        self.assertIsNone(core.tips_for_step(empty, "start"))
        self.assertEqual(core.tips_for_step(empty, "next"), {"Body": "Pad"})

    def test_marker_before_a_sketch(self):
        """Fusion: the marker may stand before a sketch that follows the last active
        solid step; that sketch is then rolled back too."""
        tl = core.build(one_body(), {"Body": "Pad"}, "Sketch001")
        self.assertEqual(tl.marker, 2)
        self.assertEqual(tl.before, "Sketch001")
        self.assertEqual(tl.find("Sketch001").state, "rolled_back")
        self.assertEqual(tl.find("Pad").state, "done")

    def test_marker_note_that_does_not_fit_the_tips_is_ignored(self):
        # After an undo the Tips moved on: the note no longer applies.
        tl = core.build(one_body(), {"Body": "Fillet"}, "Sketch001")
        self.assertTrue(tl.at_end)
        self.assertEqual(tl.before, "")
        # A solid step is never "before the marker" by note.
        tl = core.build(one_body(), {"Body": "Pad"}, "Pad001")
        self.assertEqual(tl.marker, 3)
        self.assertEqual(tl.before, "")
        self.assertEqual(core.build(one_body(), {"Body": "Pad"}, "Gone").marker, 3)

    def test_drop_before_a_sketch(self):
        tips, before = core.marker_for_slot(build(), 2)
        self.assertEqual(tips, {"Body": "Pad"})
        self.assertEqual(before, "Sketch001")
        # Just before the next solid: the default spot, no note.
        self.assertEqual(core.marker_for_slot(build(), 3), ({"Body": "Pad"}, None))
        # Same Tips, only the side of the sketch changes.
        rolled = core.build(one_body(), {"Body": "Pad"})
        self.assertEqual(core.marker_for_slot(rolled, 2), (None, "Sketch001"))
        noted = core.build(one_body(), {"Body": "Pad"}, "Sketch001")
        self.assertEqual(core.marker_for_slot(noted, 3), (None, None))
        # Before the first solid: no Tip; before the very first step: a note too.
        self.assertEqual(core.marker_for_slot(build(), 0), ({"Body": None}, "Sketch"))
        self.assertEqual(core.marker_for_slot(build(), 1), ({"Body": None}, None))
        empty = core.build(one_body(), {"Body": None})
        self.assertEqual(core.marker_for_slot(empty, 0), (None, "Sketch"))

    def test_marker_note_changes_the_signature(self):
        a = core.build(one_body(), {"Body": "Pad"})
        b = core.build(one_body(), {"Body": "Pad"}, "Sketch001")
        self.assertNotEqual(core.signature(a), core.signature(b))


class DisplayNamesTests(unittest.TestCase):
    def test_same_names_as_the_timeline(self):
        rows = one_body() + [feat("Plane", PLANE, 6), feat("Mine", SKETCH, 7, label="Holes")]
        names = core.display_names([r for r in rows if r["type_id"] in (SKETCH, PLANE)])
        tl = core.build(rows, {"Body": "Fillet"})
        for name, shown in names.items():
            self.assertEqual(shown, tl.find(name).display)
        self.assertEqual(names["Sketch001"], "Sketch 2")
        self.assertEqual(names["Plane"], "Plane 1")
        self.assertEqual(names["Mine"], "Holes")


class PlaceAtMarkerTests(unittest.TestCase):
    """A new step goes in at the marker (FreeCAD's Body.addObject puts it before the
    next solid after the Tip, at the end without a Tip)."""

    OLD = ["Sketch", "Pad", "Sketch001", "Pad001"]
    SOLIDS = {"Pad", "Pad001", "New"}

    def place(self, new, tip, note=""):
        return core.place_at_marker(self.OLD, new, tip, note, self.SOLIDS)

    def test_no_tip_goes_before_the_first_solid(self):
        self.assertEqual(
            self.place(self.OLD + ["New"], None), ["Sketch", "New", "Pad", "Sketch001", "Pad001"]
        )

    def test_no_tip_and_the_marker_before_the_first_sketch(self):
        self.assertEqual(
            self.place(self.OLD + ["New"], None, "Sketch"),
            ["New", "Sketch", "Pad", "Sketch001", "Pad001"],
        )

    def test_marker_before_a_sketch_after_the_tip(self):
        new = ["Sketch", "Pad", "Sketch001", "New", "Pad001"]  # FreeCAD: before Pad001
        self.assertEqual(
            self.place(new, "Pad", "Sketch001"), ["Sketch", "Pad", "New", "Sketch001", "Pad001"]
        )
        self.assertIsNone(self.place(new, "Pad"))  # no note: already at the marker

    def test_at_the_end_nothing_changes(self):
        self.assertIsNone(self.place(self.OLD + ["New"], "Pad001"))

    def test_placed_on_purpose_is_left_alone(self):
        # SciForge's own insertObject (a helper just before its feature, a move).
        self.assertIsNone(self.place(["Sketch", "New", "Pad", "Sketch001", "Pad001"], None))
        self.assertIsNone(self.place(["New"] + self.OLD, "Pad"))
        self.assertIsNone(self.place(self.OLD, None))  # nothing new
        self.assertIsNone(self.place(self.OLD + ["New"], "Gone"))  # a Tip not in the body

    def test_a_body_without_solids(self):
        self.assertIsNone(core.place_at_marker(["Sketch"], ["Sketch", "New"], None, "", set()))


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


class ComponentStepTests(unittest.TestCase):
    """Steps outside the bodies: a component, a captured move of one (components-2)."""

    def rows(self):
        return one_body() + [
            feat("Comp", "App::Part", 2.5, body=None, rolls=True, own_label=True),
            feat("Move", "SciForge::ComponentMove", 6, body=None, rolls=True),
            feat("Joint", "SciForge::Joint", 7, body=None),
        ]

    def test_component_move_is_a_move_step(self):
        self.assertEqual(core.classify("SciForge::ComponentMove"), "component_move")
        self.assertEqual(core.title_base("SciForge::ComponentMove", "component_move"), "Move")
        self.assertFalse(core.is_solid("component_move"))

    def test_root_steps_stand_by_their_key(self):
        rows = self.rows()
        rows.insert(0, feat("Later", "App::Part", 4.5, body=None, rolls=True))
        tl = core.build(rows, {"Body": "Fillet"})
        names = tl.names()
        self.assertLess(names.index("Comp"), names.index("Sketch001"))
        self.assertLess(names.index("Pad001"), names.index("Later"))
        self.assertLess(names.index("Later"), names.index("Fillet"))

    def test_rolling_back_rolls_components_and_their_moves(self):
        tl = core.build(self.rows(), {"Body": "Pad"})  # marker after Pad
        state = {i.name: i.state for i in tl.items}
        self.assertEqual(state["Comp"], "done")  # made before the marker
        self.assertEqual(state["Move"], "rolled_back")
        self.assertEqual(state["Joint"], "done")  # other root steps never roll back

    def test_at_the_end_everything_is_done(self):
        tl = core.build(self.rows(), {"Body": "Fillet"})
        self.assertTrue(all(i.state == "done" for i in tl.items))

    def test_marker_before_a_component_step_at_the_end(self):
        rows = self.rows()
        tl = core.build(rows, {"Body": "Fillet"}, marker_before="Move")
        state = {i.name: i.state for i in tl.items}
        self.assertEqual(state["Move"], "rolled_back")
        self.assertEqual(state["Fillet"], "done")


class ShownWhileSketchingTests(unittest.TestCase):
    """What a body shows while one of its sketches is open (Luca: a sketch on an edited
    face showed the part as it was before the edits)."""

    def test_new_sketch_shows_the_end(self):
        # Pad, Fillet; a new sketch (index 3) on a face Pad made: the fillet stays shown
        chain = [("Fillet", 2, False), ("Pad", 1, False)]
        self.assertEqual(core.shown_while_sketching(chain, 3), "Fillet")

    def test_edited_sketch_rolls_back_to_its_place(self):
        # ... Fillet (2), the sketch (3), its boss (4), a chamfer after (5): editing the
        # sketch shows the fillet, not the boss nor what came after it
        chain = [("Chamfer", 5, True), ("Boss", 4, True), ("Fillet", 2, False), ("Pad", 1, False)]
        self.assertEqual(core.shown_while_sketching(chain, 3), "Fillet")

    def test_later_step_that_does_not_use_the_sketch(self):
        # a step made after the sketch is not there yet at the sketch's place
        chain = [("Fillet2", 4, False), ("Fillet", 2, False), ("Pad", 1, False)]
        self.assertEqual(core.shown_while_sketching(chain, 3), "Fillet")

    def test_first_sketch_shows_nothing(self):
        chain = [("Fillet", 3, True), ("Pad", 2, True)]
        self.assertIsNone(core.shown_while_sketching(chain, 1))

    def test_not_in_the_timeline(self):
        # no place known: only the steps that use the sketch are left out
        chain = [("Boss", None, True), ("Fillet", None, False)]
        self.assertEqual(core.shown_while_sketching(chain, None), "Fillet")
        self.assertIsNone(core.shown_while_sketching([], 3))


class StepAtMarkerBeforeRootStepTests(unittest.TestCase):
    """A step added to a body while the marker stands right before a pattern of bodies (a
    step outside the bodies) goes in before that pattern (fix-pattern-bodies, 2026-10-16)."""

    def rows(self):
        # Body: Sketch, Pad, then (added at the marker) Sketch2, Pad2, then the older Move;
        # the pattern of the body was made between Pad and the Move.
        return [
            feat("Sketch", SKETCH, 1),
            feat("Pad", PAD, 2),
            feat("Sketch2", SKETCH, 9),
            feat("Pad2", PAD, 10),
            feat("Move", "SciForge::MoveCopy", 6),
            feat("Pattern", "SciForge::RectangularPattern", 4, body=None, rolls=True),
        ]

    def test_by_creation_order_it_lands_after_the_pattern(self):
        names = [r["name"] for r in core.merge(self.rows())]
        self.assertLess(names.index("Pattern"), names.index("Sketch2"))

    def test_keys_put_it_right_before_the_pattern(self):
        rows = self.rows()
        keys = core.keys_to_go_before(rows, "Sketch2", "Pattern")
        self.assertTrue(keys)
        rows = [dict(r, key=keys.get(r["name"], r["key"])) for r in rows]
        keys = core.keys_to_go_before(rows, "Pad2", "Pattern")
        rows = [dict(r, key=keys.get(r["name"], r["key"])) for r in rows]
        names = [r["name"] for r in core.merge(rows)]
        self.assertEqual(names, ["Sketch", "Pad", "Sketch2", "Pad2", "Pattern", "Move"])
        tl = core.build(rows, {"Body": "Pad2"}, marker_before="Pattern")
        state = {i.name: i.state for i in tl.items}
        self.assertEqual(state["Pad2"], "done")
        self.assertEqual(state["Pattern"], "rolled_back")  # the marker is still before it
        self.assertEqual(state["Move"], "rolled_back")

    def test_nothing_to_do_when_it_is_before_already(self):
        rows = self.rows()
        self.assertEqual(core.keys_to_go_before(rows, "Pad", "Pattern"), {})
        self.assertEqual(core.keys_to_go_before(rows, "Nope", "Pattern"), {})


class MeshStepsAndTheMarkerTests(unittest.TestCase):
    """Mesh steps sit outside the bodies and roll back with the marker (mesh-inspect-2); a
    design of mesh bodies only has no solid step to carry the marker: the note does."""

    def mesh_rows(self):
        return [
            feat("MeshBody", "SciForge::InsertMesh", 1, body=None, rolls=True),
            feat("Smooth", "SciForge::MeshSmooth", 2, body=None, rolls=True),
            feat("Edit", "SciForge::MeshDirectEdit", 3, body=None, rolls=True),
        ]

    def test_new_kinds(self):
        self.assertEqual(core.classify("SciForge::MeshDirectEdit"), "mesh_direct_edit")
        self.assertEqual(
            core.title_base("SciForge::MeshDirectEdit", "mesh_direct_edit"), "Mesh Base Feature"
        )
        self.assertEqual(core.classify("SciForge::MeshCreateFaceGroup"), "mesh_create_group")
        self.assertEqual(core.classify("SciForge::MeshCombineFaceGroups"), "mesh_combine_groups")
        self.assertEqual(core.icon_for("mesh_combine_groups"), "mesh_combine_groups")

    def test_marker_anywhere_without_solids(self):
        tl = core.build(self.mesh_rows(), {})
        self.assertTrue(tl.at_end)
        self.assertEqual(core.marker_for_slot(tl, 2), (None, "Edit"))
        self.assertEqual(core.marker_for_slot(tl, 0), (None, "MeshBody"))
        self.assertEqual(core.marker_for_slot(tl, 3), (None, None))  # the end: no note
        rolled = core.build(self.mesh_rows(), {}, marker_before="Smooth")
        state = {i.name: i.state for i in rolled.items}
        self.assertEqual(
            state, {"MeshBody": "done", "Smooth": "rolled_back", "Edit": "rolled_back"}
        )
        self.assertEqual(rolled.marker, 1)
        self.assertEqual([i.title for i in rolled.items][2], "Mesh Base Feature 1")

    def test_mesh_steps_after_solids_roll_with_the_marker(self):
        rows = one_body() + [
            feat("Tess", "SciForge::Tessellate", 6, body=None, rolls=True),
            feat("Smooth", "SciForge::MeshSmooth", 7, body=None, rolls=True),
        ]
        tl = core.build(rows, {"Body": "Fillet"})
        tips, before = core.marker_for_slot(tl, 6)
        self.assertEqual((tips, before), (None, "Smooth"))
        noted = core.build(rows, {"Body": "Fillet"}, marker_before="Smooth")
        state = {i.name: i.state for i in noted.items}
        self.assertEqual(state["Tess"], "done")
        self.assertEqual(state["Smooth"], "rolled_back")
        # before the fillet: both mesh steps are rolled back with it
        early = core.build(rows, {"Body": "Pad001"})
        state = {i.name: i.state for i in early.items}
        self.assertEqual((state["Tess"], state["Smooth"]), ("rolled_back", "rolled_back"))


if __name__ == "__main__":
    unittest.main()
