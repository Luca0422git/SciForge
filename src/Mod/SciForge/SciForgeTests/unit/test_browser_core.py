# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Fusion-style browser's structure. Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import browser_core as core  # noqa: E402


def obj(name, type_id, visible=True, body=None, role=None, label=None, **extra):
    row = {
        "name": name,
        "label": label or name,
        "type_id": type_id,
        "visible": visible,
        "body": body,
        "role": role,
    }
    row.update(extra)
    return row


OBJECTS = [
    obj("Body", "PartDesign::Body"),
    obj("Origin", "App::Origin", body="Body"),
    obj("XY_Plane", "App::Plane", False, "Body", "XY_Plane"),
    obj("X_Axis", "App::Line", False, "Body", "X_Axis"),
    obj("Origin001", "App::Point", False, "Body", "Origin"),
    obj("Sketch", "Sketcher::SketchObject", False, "Body"),
    obj("Pad", "PartDesign::Pad", True, "Body"),
    obj("DatumPlane", "PartDesign::Plane", True, "Body"),
]


class BrowserTests(unittest.TestCase):
    def tree(self, objects=OBJECTS, **kw):
        return core.build("Design", objects, active_body="Body", **kw)

    def labels(self, node):
        return [c["label"] for c in node["children"]]

    def folder(self, tree, label):
        return [c for c in tree["children"] if c["label"] == label][0]

    def test_fusion_top_level_order(self):
        self.assertEqual(
            self.labels(self.tree()),
            ["Document Settings", "Named Views", "Origin", "Bodies", "Sketches", "Construction"],
        )

    def test_sketch_curves_are_listed_under_their_sketch(self):
        objects = OBJECTS + [
            obj(
                "Curves3D",
                "Part::FeaturePython",
                True,
                None,
                label="3D Curves",
                sciforge_type="Sketch3DCurves",
                owner_sketch="Sketch",
            ),
            obj(
                "ProjectedCurves",
                "Part::FeaturePython",
                True,
                None,
                label="Projected Curves",
                sciforge_type="ProjectedCurves",
                owner_sketch="Sketch",
            ),
        ]
        sketches = self.folder(self.tree(objects), "Sketches")
        self.assertEqual(self.labels(sketches), ["Sketch"])
        sketch = sketches["children"][0]
        self.assertEqual(self.labels(sketch), ["3D Curves", "Projected Curves"])
        icons = [c["icon"] for c in sketch["children"]]
        self.assertEqual(icons, ["sk_spline", "sk_project"])
        self.assertEqual(sketch["children"][0]["kind"], "sketch_curves")

    def test_sketch_curves_without_their_sketch_still_show(self):
        objects = [
            obj(
                "Curves3D",
                "Part::FeaturePython",
                True,
                None,
                label="3D Curves",
                sciforge_type="Sketch3DCurves",
                owner_sketch="Elsewhere",
            ),
        ]
        sketches = self.folder(self.tree(objects), "Sketches")
        self.assertEqual(self.labels(sketches), ["3D Curves"])

    def test_features_are_not_listed(self):
        names = [n["object"] for n in core.walk(self.tree())]
        self.assertNotIn("Pad", names, "features belong to the timeline, not the browser")

    def test_active_body_marked(self):
        body = self.folder(self.tree(), "Bodies")["children"][0]
        self.assertTrue(body["active"])
        self.assertEqual(body["label"], "Body")  # the mark is drawn, not part of the name
        other = core.build(
            "Design", OBJECTS + [obj("Body001", "PartDesign::Body")], active_body="Body"
        )
        bodies = self.folder(other, "Bodies")["children"]
        self.assertEqual([b["active"] for b in bodies], [True, False])

    def test_timeline_names(self):
        """Fusion's browser and timeline show one name: "Sketch 2", not "Sketch001"."""
        objects = [o for o in OBJECTS if o["name"] != "Sketch"] + [
            obj("Sketch001", "Sketcher::SketchObject", body="Body", display="Sketch 2")
        ]
        sketch = self.folder(self.tree(objects), "Sketches")["children"][0]
        self.assertEqual(sketch["label"], "Sketch 2")
        self.assertEqual(sketch["object_label"], "Sketch001")
        plane = self.folder(self.tree(), "Construction")["children"][0]
        self.assertEqual(plane["label"], "DatumPlane")  # no timeline name: the label

    def test_origin_in_fusion_order(self):
        self.assertEqual(self.labels(self.folder(self.tree(), "Origin")), ["O", "X", "XY"])

    def test_one_origin_without_an_active_body(self):
        """A reopened file with two bodies has no active body yet: still one origin."""
        second = [
            obj("Body001", "PartDesign::Body"),
            obj("XY_Plane001", "App::Plane", False, "Body001", "XY_Plane"),
            obj("X_Axis001", "App::Line", False, "Body001", "X_Axis"),
            obj("Origin003", "App::Point", False, "Body001", "Origin"),
        ]
        tree = core.build("Design", OBJECTS + second)
        origin = self.folder(tree, "Origin")["children"]
        self.assertEqual([n["label"] for n in origin], ["O", "X", "XY"])
        self.assertEqual({n["object"] for n in origin}, {"Origin001", "X_Axis", "XY_Plane"})
        # The active body's origin when there is one.
        tree = core.build("Design", OBJECTS + second, active_body="Body001")
        origin = self.folder(tree, "Origin")["children"]
        self.assertEqual({n["object"] for n in origin}, {"Origin003", "X_Axis001", "XY_Plane001"})

    def test_suppressed_is_greyed_not_a_problem(self):
        rows = [dict(o) for o in OBJECTS]
        rows[5]["suppressed"] = True
        sketch = self.folder(self.tree(rows), "Sketches")["children"][0]
        self.assertEqual(sketch["status"], "suppressed")
        self.assertIn("Suppressed", sketch["tip"])

    def test_folder_eye_follows_children(self):
        tree = self.tree()
        self.assertFalse(self.folder(tree, "Sketches")["visible"])  # the only sketch is hidden
        self.assertTrue(self.folder(tree, "Bodies")["visible"])

    def test_units_shown(self):
        settings = self.tree(units="in")["children"][0]
        self.assertEqual(settings["children"][0]["label"], "Units: in")
        self.assertEqual(core.unit_label(0), "mm")
        self.assertEqual(core.unit_label(3), "in")
        self.assertIsNone(core.unit_label(8))

    def test_named_views_with_saved_ones(self):
        views = self.folder(self.tree(views=["Corner"]), "Named Views")
        self.assertEqual(self.labels(views), ["TOP", "FRONT", "RIGHT", "HOME", "Corner"])
        self.assertEqual(views["children"][-1]["kind"], "saved_view")

    def test_empty_document(self):
        self.assertEqual(self.labels(core.build("Empty", [])), ["Document Settings", "Named Views"])

    def test_analysis_folder_once_there_is_one(self):
        rows = OBJECTS + [obj("Section", "App::FeaturePython", sciforge_type="SectionAnalysis")]
        labels = self.labels(self.tree(rows))
        self.assertEqual(labels[2], "Analysis")

    def test_analysis_menu_edits(self):
        """Fusion: an analysis in the browser is edited from its menu (and double-click)."""
        node = {"kind": "analysis", "visible": True}
        self.assertEqual(core.menu_for(node)[0], "Edit Feature")

    def test_problems_shown(self):
        rows = [dict(o) for o in OBJECTS]
        rows[5]["warning"] = "Lost its plane"
        sketch = self.folder(self.tree(rows), "Sketches")["children"][0]
        self.assertEqual(sketch["status"], "warning")
        self.assertEqual(sketch["tip"], "Lost its plane")

    def test_signature_changes_with_visibility(self):
        a = core.signature(self.tree())
        changed = [dict(o) for o in OBJECTS]
        changed[5]["visible"] = True
        b = core.signature(core.build("Design", changed, active_body="Body"))
        self.assertNotEqual(a, b)

    def test_find_helpers(self):
        tree = self.tree()
        self.assertEqual(core.node_for_object(tree, "Sketch"), "sketch:Sketch")
        # A feature is found through its body.
        self.assertEqual(core.node_for_object(tree, "Pad", "Body"), "body:Body")
        self.assertEqual(core.path_to(tree, "sketch:Sketch"), ["document", "sketches"])

    def test_menus_like_fusion(self):
        tree = self.tree()
        body = self.folder(tree, "Bodies")["children"][0]
        self.assertIn("Find in Timeline", core.menu_for(body))
        self.assertIn("Delete", core.menu_for(body))
        sketch = self.folder(tree, "Sketches")["children"][0]
        self.assertEqual(core.menu_for(sketch)[0], "Edit Sketch")
        plane = self.folder(tree, "Origin")["children"][2]
        self.assertNotIn("Delete", core.menu_for(plane))


class HoverTests(unittest.TestCase):
    """A hover in the 3D view lights the browser row of what is under the mouse."""

    OBJECTS = [
        obj("Part", "App::Part", label="Arm"),
        obj("Body", "PartDesign::Body", component="Part"),
        obj("Pad", "PartDesign::Pad", True, "Body", component="Part"),
        obj("Sketch", "Sketcher::SketchObject", False, "Body", component="Part"),
        obj("Body001", "PartDesign::Body"),
    ]

    def tree(self):
        return core.build("Design", self.OBJECTS, active_body="Body001")

    def test_the_body_wins_over_its_component(self):
        # a face of Pad in Body in the component Part (browser_ui adds Pad's body after it)
        key = core.hover_row(self.tree(), ["Part", "Body", "Pad", "Body"])
        self.assertEqual(key, "body:Body")

    def test_a_sketch_lights_its_own_row(self):
        self.assertEqual(core.hover_row(self.tree(), ["Part", "Body", "Sketch"]), "sketch:Sketch")

    def test_a_component_alone(self):
        self.assertEqual(core.hover_row(self.tree(), ["Part"]), "component:Part")

    def test_nothing_known(self):
        self.assertIsNone(core.hover_row(self.tree(), []))
        self.assertIsNone(core.hover_row(self.tree(), ["Pad"]))

    def test_a_closed_folder_shows_it(self):
        tree = self.tree()
        everything_open = core.shown_row(tree, "body:Body", lambda key: True)
        self.assertEqual(everything_open, "body:Body")
        closed = {"bodies:Part"}
        self.assertEqual(
            core.shown_row(tree, "body:Body", lambda key: key not in closed), "bodies:Part"
        )
        closed = {"component:Part", "bodies:Part"}
        self.assertEqual(
            core.shown_row(tree, "body:Body", lambda key: key not in closed), "component:Part"
        )
        self.assertIsNone(core.shown_row(tree, "body:Nothing", lambda key: True))

    def test_opacity_control_on_bodies_and_components(self):
        tree = self.tree()
        self.assertIn("Opacity Control", core.menu_for(core.find(tree, "body:Body")))
        self.assertIn("Opacity Control", core.menu_for(core.find(tree, "component:Part")))
        self.assertNotIn("Opacity Control", core.menu_for(core.find(tree, "sketch:Sketch")))


if __name__ == "__main__":
    unittest.main()
