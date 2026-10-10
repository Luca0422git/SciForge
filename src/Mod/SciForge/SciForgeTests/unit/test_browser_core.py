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

    def test_origin_in_fusion_order(self):
        self.assertEqual(self.labels(self.folder(self.tree(), "Origin")), ["O", "X", "XY"])

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


if __name__ == "__main__":
    unittest.main()
