# SPDX-License-Identifier: LGPL-2.1-or-later
"""Components: the pure logic (components_core.py) and the browser tree with
components (browser_core.py). Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import browser_core as browser  # noqa: E402
from sciforge import components_core as core  # noqa: E402

# root: BodyA, Comp1 [Body1, Comp2 [Body2]], Comp3 [Body3]
PARENTS = {
    "BodyA": None,
    "Comp1": None,
    "Body1": "Comp1",
    "Comp2": "Comp1",
    "Body2": "Comp2",
    "Comp3": None,
    "Body3": "Comp3",
}
COMPONENTS = {"Comp1", "Comp2", "Comp3"}


class LabelTests(unittest.TestCase):
    def test_first_component_is_component1(self):
        self.assertEqual(core.next_label([]), "Component1")

    def test_numbering_skips_names_in_use(self):
        self.assertEqual(core.next_label(["Component1", "Component2"]), "Component3")
        # The number after the ones in use (a gap is not filled), like SciForge's bodies.
        self.assertEqual(core.next_label(["Component1", "Component3"]), "Component4")

    def test_renamed_components_do_not_count(self):
        self.assertEqual(core.next_label(["Bracket", "Lid"]), "Component1")

    def test_bodies_are_numbered_per_component(self):
        self.assertEqual(core.body_label([]), "Body1")
        self.assertEqual(core.body_label(["Body1"]), "Body2")
        # every body counts, as in bodies._next_label: FreeCAD's first "Body" then Body2
        self.assertEqual(core.body_label(["Body"]), "Body2")
        self.assertEqual(core.body_label(["Body", "Body2"]), "Body3")
        self.assertEqual(core.body_label(["Wheel"]), "Body2")


class TreeTests(unittest.TestCase):
    def test_ancestors_nearest_first(self):
        self.assertEqual(core.ancestors(PARENTS, "Body2"), ["Comp2", "Comp1"])
        self.assertEqual(core.ancestors(PARENTS, "BodyA"), [])

    def test_descendants(self):
        self.assertEqual(sorted(core.descendants(PARENTS, "Comp1")), ["Body1", "Body2", "Comp2"])
        self.assertEqual(core.descendants(PARENTS, "Body3"), [])

    def test_is_inside(self):
        self.assertTrue(core.is_inside(PARENTS, "Body2", "Comp1"))
        self.assertTrue(core.is_inside(PARENTS, "Comp1", "Comp1"))
        self.assertFalse(core.is_inside(PARENTS, "Body3", "Comp1"))
        self.assertTrue(core.is_inside(PARENTS, "Body3", None), "the root holds everything")

    def test_isolate_hides_everything_but_the_unit_its_parents_and_its_contents(self):
        # Comp2 keeps Comp1 (above it) and Body2 (inside it); everything else goes.
        self.assertEqual(
            sorted(core.isolate_hidden(PARENTS, "Comp2")), ["Body1", "Body3", "BodyA", "Comp3"]
        )
        self.assertEqual(
            sorted(core.isolate_hidden(PARENTS, "BodyA")),
            ["Body1", "Body2", "Body3", "Comp1", "Comp2", "Comp3"],
        )
        self.assertEqual(sorted(core.isolate_hidden(PARENTS, "Comp1")), ["Body3", "BodyA", "Comp3"])

    def test_move_targets(self):
        # Body1 is in Comp1: it may go to the root, Comp2 or Comp3, not stay in Comp1.
        self.assertEqual(
            core.move_targets(PARENTS, sorted(COMPONENTS), ["Body1"]), [None, "Comp2", "Comp3"]
        )
        # Comp1 cannot go into itself or into Comp2 (which is inside it); it is at the root.
        self.assertEqual(core.move_targets(PARENTS, sorted(COMPONENTS), ["Comp1"]), ["Comp3"])
        # Two units from different containers: every component (one of them moves in each
        # case) and the root are offered.
        self.assertEqual(
            core.move_targets(PARENTS, sorted(COMPONENTS), ["Body1", "Body3"]),
            [None, "Comp1", "Comp2", "Comp3"],
        )

    def test_visible_steps_follow_the_active_component(self):
        steps = {
            "SketchA": None,
            "PadA": None,
            "Comp1": "Comp1",
            "Pad1": "Comp1",
            "Comp2": "Comp2",
            "Pad2": "Comp2",
            "Pad3": "Comp3",
        }
        self.assertEqual(core.visible_steps(steps, PARENTS, None), set(steps))
        self.assertEqual(
            core.visible_steps(steps, PARENTS, "Comp1"), {"Comp1", "Pad1", "Comp2", "Pad2"}
        )
        self.assertEqual(core.visible_steps(steps, PARENTS, "Comp2"), {"Comp2", "Pad2"})


def obj(name, type_id, visible=True, body=None, role=None, label=None, component=None):
    return {
        "name": name,
        "label": label or name,
        "type_id": type_id,
        "visible": visible,
        "body": body,
        "role": role,
        "component": component,
    }


OBJECTS = [
    obj("Body", "PartDesign::Body"),
    obj("XY_Plane", "App::Plane", False, "Body", "XY_Plane"),
    obj("Sketch", "Sketcher::SketchObject", False, "Body"),
    obj("Comp", "App::Part", label="Bracket"),
    obj("XY_Plane001", "App::Plane", False, None, "XY_Plane", component="Comp"),
    obj("Body001", "PartDesign::Body", label="Body1", component="Comp"),
    obj("XY_Plane002", "App::Plane", False, "Body001", "XY_Plane", component="Comp"),
    obj("Sketch001", "Sketcher::SketchObject", False, "Body001", component="Comp"),
    obj("Pad", "PartDesign::Pad", True, "Body001", component="Comp"),
    obj("Comp001", "App::Part", label="Lid", component="Comp"),
    obj("Body002", "PartDesign::Body", label="Body1", component="Comp001"),
]


class BrowserComponentTests(unittest.TestCase):
    def tree(self, **kw):
        return browser.build("Design", OBJECTS, active_body="Body", **kw)

    def labels(self, node):
        return [c["label"] for c in node["children"]]

    def child(self, node, label):
        return [c for c in node["children"] if c["label"] == label][0]

    def test_components_come_after_the_root_folders(self):
        self.assertEqual(
            self.labels(self.tree()),
            ["Document Settings", "Named Views", "Origin", "Bodies", "Sketches", "Bracket"],
        )

    def test_component_has_its_own_folders_and_nested_component(self):
        bracket = self.child(self.tree(), "Bracket")
        self.assertEqual(bracket["kind"], "component")
        self.assertEqual(bracket["object"], "Comp")
        self.assertEqual(self.labels(bracket), ["Origin", "Bodies", "Sketches", "Lid"])
        self.assertEqual(self.labels(self.child(bracket, "Bodies")), ["Body1"])
        self.assertEqual(self.labels(self.child(bracket, "Origin")), ["XY"])
        lid = self.child(bracket, "Lid")
        self.assertEqual(self.labels(lid), ["Bodies"])
        self.assertEqual(self.labels(self.child(lid, "Bodies")), ["Body1"])

    def test_root_shows_only_its_own_bodies_and_origin(self):
        tree = self.tree()
        self.assertEqual(self.labels(self.child(tree, "Bodies")), ["Body"])
        self.assertEqual(self.labels(self.child(tree, "Sketches")), ["Sketch"])
        names = [n["object"] for n in browser.walk(tree)]
        self.assertNotIn("Pad", names)

    def test_active_marks(self):
        tree = self.tree()
        self.assertTrue(tree["active"], "the root is active when no component is")
        self.assertFalse(self.child(tree, "Bracket")["active"])
        tree = self.tree(active_component="Comp001")
        self.assertFalse(tree["active"])
        bracket = self.child(tree, "Bracket")
        self.assertFalse(bracket["active"])
        self.assertTrue(self.child(bracket, "Lid")["active"])

    def test_find_component_node(self):
        tree = self.tree()
        self.assertEqual(browser.node_for_object(tree, "Comp001"), "component:Comp001")
        self.assertEqual(browser.path_to(tree, "component:Comp001"), ["document", "component:Comp"])

    def test_menus(self):
        self.assertIn("Activate", browser.MENUS["component"])
        self.assertIn("Create Components from Bodies", browser.MENUS["body"])
        self.assertIn("Move to Component", browser.MENUS["body"])
        self.assertIn("New Component", browser.MENUS["document"])


if __name__ == "__main__":
    unittest.main()
