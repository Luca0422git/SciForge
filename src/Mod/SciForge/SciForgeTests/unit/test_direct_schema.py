# SPDX-License-Identifier: LGPL-2.1-or-later
"""The golden-model format of the direct-modeling and Modify steps (history_off / on,
replace_face, split_face, silhouette_split, align_bodies, modify_edit, remove_bodies). Runs
without FreeCAD."""

import copy
import glob
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from SciForgeTests.golden import schema  # noqa: E402

TOP = {"type": "plane", "normal": [0, 0, 1], "count": 1}
GOOD = {
    "id": "t",
    "title": "test",
    "steps": [
        {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]},
        {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10},
        {"op": "sketch", "id": "s2", "plane": "XY", "geometry": [{"rect": [50, 0, 70, 30]}]},
        {"op": "extrude", "id": "e2", "profile": "s2", "distance": 15, "operation": "new_body"},
        {
            "op": "replace_face",
            "id": "r1",
            "faces": TOP,
            "of": "e1",
            "target": {"face": TOP, "of": "e2"},
        },
        {
            "op": "split_face",
            "id": "f1",
            "faces": TOP,
            "tool": "YZ",
            "split_type": "vector",
            "direction": "Z",
        },
        {"op": "silhouette_split", "id": "l1", "body": "e2", "direction": "Z", "operation": "body"},
        {
            "op": "align_bodies",
            "id": "a1",
            "from": {"face": TOP, "of": "e2"},
            "to": {"face": TOP, "of": "e1"},
            "flip": True,
            "turns": 3,
        },
        {"op": "modify_edit", "target": "r1", "set": {"target": "XY"}},
        {"op": "history_off"},
        {"op": "history_on"},
        {"op": "remove_bodies", "steps": ["e2"]},
    ],
    "expect": {"volume": 1, "source": "analytic"},
}


def model(index, **changes):
    m = copy.deepcopy(GOOD)
    step = m["steps"][index]
    for key, value in changes.items():
        if value is None:
            step.pop(key, None)
        else:
            step[key] = value
    return m


class DirectSchemaTest(unittest.TestCase):
    def test_good_model(self):
        schema.validate(copy.deepcopy(GOOD))

    def bad(self, m, text):
        with self.assertRaises(schema.ModelError) as ctx:
            schema.validate(m)
        self.assertIn(text, str(ctx.exception))

    def test_replace_face_needs_target(self):
        self.bad(model(4, target=None), "target")

    def test_pick_names_known_step(self):
        self.bad(model(4, target={"face": TOP, "of": "nope"}), "unknown step")

    def test_pick_has_one_kind(self):
        self.bad(model(4, target={"face": TOP, "body": "e2"}), "exactly one")

    def test_pick_plane_name(self):
        self.bad(model(5, tool="AB"), "XY/XZ/YZ")

    def test_split_type(self):
        self.bad(model(5, split_type="sideways"), "split_type")

    def test_along_vector_needs_direction(self):
        self.bad(model(5, direction=None), "direction")

    def test_silhouette_operation(self):
        self.bad(model(6, operation="halves"), "operation")

    def test_silhouette_body_known(self):
        self.bad(model(6, body="e9"), "unknown step")

    def test_align_turns(self):
        self.bad(model(7, turns=4), "turns")

    def test_modify_edit_target_kind(self):
        self.bad(model(8, target="e1"), "modify_edit")

    def test_remove_steps_known(self):
        self.bad(model(11, steps=["e7"]), "earlier steps")

    def test_unknown_key(self):
        self.bad(model(4, colour="red"), "colour")


class DirectModelsTest(unittest.TestCase):
    def test_direct_models_validate(self):
        root = os.path.join(os.path.dirname(HERE), "golden", "models")
        paths = sorted(glob.glob(os.path.join(root, "direct_*.json")))
        self.assertGreaterEqual(len(paths), 10)
        for path in paths:
            with open(path) as f:
                m = json.load(f)
            schema.validate(m)
            self.assertEqual(m["id"], os.path.basename(path)[:-5])


if __name__ == "__main__":
    unittest.main()
