import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forgecad import timeline_core as core  # noqa: E402


def feat(name, type_id):
    return {"name": name, "label": name, "type_id": type_id}


SKETCH = "Sketcher::SketchObject"
PAD = "PartDesign::Pad"
FILLET = "PartDesign::Fillet"


class ClassifyTests(unittest.TestCase):
    def test_known_and_fallbacks(self):
        self.assertEqual(core.classify(PAD), "extrude")
        self.assertEqual(core.classify("PartDesign::Pocket"), "cut")
        self.assertEqual(core.classify("PartDesign::AdditiveBox"), "primitive")
        self.assertEqual(core.classify("Something::Else"), "other")


class BuildItemsTests(unittest.TestCase):
    def setUp(self):
        self.features = [
            feat("Sketch", SKETCH),
            feat("Pad", PAD),
            feat("Sketch001", SKETCH),
            feat("Pad001", PAD),
            feat("Fillet", FILLET),
        ]

    def test_titles_count_per_kind(self):
        items = core.build_items(self.features, "Fillet")
        self.assertEqual(
            [i.title for i in items],
            ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2", "Fillet 1"],
        )

    def test_tip_at_end_all_done(self):
        items = core.build_items(self.features, "Fillet")
        self.assertEqual([i.state for i in items], ["done"] * 4 + ["tip"])

    def test_rolled_back(self):
        items = core.build_items(self.features, "Pad")
        self.assertEqual(
            [i.state for i in items],
            ["done", "tip", "rolled_back", "rolled_back", "rolled_back"],
        )

    def test_trailing_sketch_is_pending_not_rolled_back(self):
        features = [feat("Sketch", SKETCH), feat("Pad", PAD), feat("Sketch001", SKETCH)]
        items = core.build_items(features, "Pad")
        self.assertEqual([i.state for i in items], ["done", "tip", "pending"])

    def test_missing_tip_falls_back_to_last_solid(self):
        items = core.build_items(self.features, None)
        self.assertEqual(items[-1].state, "tip")

    def test_empty_and_sketch_only(self):
        self.assertEqual(core.build_items([], None), [])
        items = core.build_items([feat("Sketch", SKETCH)], None)
        self.assertEqual(items[0].state, "done")


class RollbackTests(unittest.TestCase):
    def setUp(self):
        self.items = core.build_items(
            [
                feat("Sketch", SKETCH),
                feat("Pad", PAD),
                feat("Sketch001", SKETCH),
                feat("Pad001", PAD),
            ],
            "Pad001",
        )

    def test_roll_back_to_solid(self):
        self.assertEqual(core.rollback_target(self.items, 1), "Pad")

    def test_sketch_rolls_back_to_previous_solid(self):
        self.assertEqual(core.rollback_target(self.items, 2), "Pad")

    def test_first_sketch_has_no_target(self):
        self.assertIsNone(core.rollback_target(self.items, 0))

    def test_tip_has_no_target(self):
        self.assertIsNone(core.rollback_target(self.items, 3))

    def test_roll_forward(self):
        rolled = core.build_items(
            [feat("Sketch", SKETCH), feat("Pad", PAD), feat("Pad001", PAD)], "Pad"
        )
        self.assertTrue(core.can_roll_forward(rolled))
        self.assertEqual(core.last_solid_name(rolled), "Pad001")
        self.assertFalse(core.can_roll_forward(self.items))

    def test_signature_changes_with_state(self):
        a = core.signature(self.items, "Body")
        b = core.signature(core.build_items([feat("Sketch", SKETCH)], None), "Body")
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
