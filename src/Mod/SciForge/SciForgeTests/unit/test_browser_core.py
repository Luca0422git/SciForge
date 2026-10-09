# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Fusion-style browser's structure. Runs without FreeCAD."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import browser_core as core  # noqa: E402


def obj(name, type_id, visible=True, body=None, role=None, label=None):
    return {
        "name": name,
        "label": label or name,
        "type_id": type_id,
        "visible": visible,
        "body": body,
        "role": role,
    }


OBJECTS = [
    obj("Body", "PartDesign::Body"),
    obj("Origin", "App::Origin", body="Body"),
    obj("XY_Plane", "App::Plane", False, "Body", "XY_Plane"),
    obj("X_Axis", "App::Line", False, "Body", "X_Axis"),
    obj("Sketch", "Sketcher::SketchObject", False, "Body"),
    obj("Pad", "PartDesign::Pad", True, "Body"),
    obj("DatumPlane", "PartDesign::Plane", True, "Body"),
]


class BrowserTests(unittest.TestCase):
    def tree(self, **kw):
        return core.build("Design", OBJECTS, active_body="Body", **kw)

    def labels(self, node):
        return [c["label"] for c in node["children"]]

    def test_fusion_top_level_order(self):
        self.assertEqual(
            self.labels(self.tree()),
            ["Document Settings", "Named Views", "Origin", "Bodies", "Sketches", "Construction"],
        )

    def test_features_are_not_listed(self):
        names = [n["object"] for n in core.walk(self.tree())]
        self.assertNotIn("Pad", names, "features belong to the timeline, not the browser")

    def test_active_body_marked(self):
        bodies = [c for c in self.tree()["children"] if c["label"] == "Bodies"][0]
        self.assertTrue(bodies["children"][0]["label"].endswith("●"))

    def test_origin_in_fusion_order(self):
        origin = [c for c in self.tree()["children"] if c["label"] == "Origin"][0]
        self.assertEqual(self.labels(origin), ["X", "XY"])

    def test_folder_eye_follows_children(self):
        tree = self.tree()
        sketches = [c for c in tree["children"] if c["label"] == "Sketches"][0]
        self.assertFalse(sketches["visible"])  # the only sketch is hidden
        bodies = [c for c in tree["children"] if c["label"] == "Bodies"][0]
        self.assertTrue(bodies["visible"])

    def test_units_shown(self):
        settings = self.tree(units="in")["children"][0]
        self.assertEqual(settings["children"][0]["label"], "Units: in")

    def test_empty_document(self):
        self.assertEqual(self.labels(core.build("Empty", [])), ["Document Settings", "Named Views"])

    def test_signature_changes_with_visibility(self):
        a = core.signature(self.tree())
        changed = [dict(o) for o in OBJECTS]
        changed[4]["visible"] = True
        b = core.signature(core.build("Design", changed, active_body="Body"))
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
