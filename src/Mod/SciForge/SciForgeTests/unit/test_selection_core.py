# SPDX-License-Identifier: LGPL-2.1-or-later
"""Selection like Fusion: the rules and the box maths (sciforge/selection_core.py). No FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import selection_core as core  # noqa: E402

BOX = core.rect_polygon(10, 10, 50, 40)  # a window from (10, 10) to (50, 40)


def square(x0, y0, x1, y1):
    """points, segments and outline of a square face on screen."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    segs = [(pts[i], pts[(i + 1) % 4]) for i in range(4)]
    return pts, segs, pts


class FilterTests(unittest.TestCase):
    def test_default_allows_everything(self):
        f = core.Filters()
        self.assertFalse(f.is_restrictive())
        for kind in core.KINDS:
            self.assertTrue(f.allows(kind))
        self.assertTrue(f.allows(None))
        self.assertTrue(f.allows("something_else"))
        self.assertFalse(f.select_through, "Select Through is off until the user turns it on")

    def test_set_toggle_and_encode(self):
        f = core.Filters()
        f.set("faces", False)
        f.toggle("edges")
        self.assertFalse(f.allows("faces"))
        self.assertFalse(f.allows("edges"))
        self.assertEqual(f.encode(), "faces,edges")
        back = core.Filters.decode("faces,edges,nonsense", select_through=True)
        self.assertEqual(sorted(back.off), ["edges", "faces"])
        self.assertTrue(back.select_through)
        f.toggle("edges")
        self.assertTrue(f.allows("edges"))
        with self.assertRaises(ValueError):
            f.set("bananas", True)

    def test_priority_is_a_preset_and_clicking_it_again_clears(self):
        f = core.Filters()
        self.assertIsNone(f.priority())
        f.apply_priority("body")
        self.assertEqual(f.priority(), "body")
        self.assertTrue(f.allows("bodies"))
        for kind in core.KINDS:
            if kind != "bodies":
                self.assertFalse(f.allows(kind), kind)
        f.apply_priority("edge")  # another priority replaces the first
        self.assertEqual(f.priority(), "edge")
        f.apply_priority("edge")  # the active one again: every filter back on
        self.assertIsNone(f.priority())
        self.assertFalse(f.is_restrictive())
        f.set("faces", False)
        self.assertIsNone(f.priority(), "two kinds off is no priority")
        with self.assertRaises(ValueError):
            f.apply_priority("component")

    def test_equality_and_copy(self):
        a = core.Filters(["faces"], False)
        b = a.copy()
        self.assertEqual(a, b)
        b.toggle("faces")
        self.assertNotEqual(a, b)


class KindTests(unittest.TestCase):
    def test_body_elements(self):
        self.assertEqual(core.kind_of("PartDesign::Pad", "Face6", True), "faces")
        self.assertEqual(core.kind_of("PartDesign::Pad", "Edge2", True), "edges")
        self.assertEqual(core.kind_of("PartDesign::AdditiveBox", "Vertex1", True), "vertices")
        self.assertEqual(core.kind_of("PartDesign::Body", "", True), "bodies")
        self.assertEqual(core.kind_of("PartDesign::Pad", "", True), "bodies")
        self.assertEqual(core.kind_of("Part::Feature", "Face1", False), "faces")
        self.assertIsNone(core.kind_of("Part::Feature", "", False))

    def test_sketch_and_work_geometry(self):
        self.assertEqual(core.kind_of("Sketcher::SketchObject", "Edge3", True), "sketch_curves")
        self.assertEqual(core.kind_of("Sketcher::SketchObject", "Vertex1", True), "sketch_points")
        self.assertIsNone(core.kind_of("Sketcher::SketchObject", "", True))
        self.assertIsNone(core.kind_of("Sketcher::SketchObject", "InternalFace1", True))
        self.assertEqual(core.kind_of("PartDesign::Plane", "", True), "work_geometry")
        self.assertEqual(core.kind_of("App::Plane", "", False), "work_geometry")
        self.assertEqual(core.kind_of("App::Line", "", False), "work_geometry")

    def test_unknown_things_are_not_filtered(self):
        self.assertIsNone(core.kind_of("App::FeaturePython", "", False))
        self.assertIsNone(core.kind_of("", "", False))
        self.assertIsNone(core.kind_of("App::FeaturePython", "Face1", False))

    def test_box_kinds(self):
        f = core.Filters()
        self.assertEqual(core.box_kinds(f), {"faces", "edges", "sketch_curves"})
        self.assertFalse(core.only_bodies(f))
        f.apply_priority("body")
        self.assertEqual(core.box_kinds(f), {"bodies"})
        self.assertTrue(core.only_bodies(f))
        f = core.Filters(["faces", "edges"])
        self.assertEqual(core.box_kinds(f), {"vertices", "sketch_curves"})
        f = core.Filters(["faces", "edges", "sketch_curves"])
        self.assertEqual(core.box_kinds(f), {"vertices"})
        f = core.Filters(["faces", "edges", "vertices", "sketch_curves"])
        self.assertEqual(core.box_kinds(f), {"bodies"})
        f = core.Filters(["sketch_curves"])
        self.assertEqual(core.box_kinds(f), {"faces", "edges"})


class ModifierTests(unittest.TestCase):
    def test_box_plan(self):
        self.assertEqual(core.plan(False, False, False), "replace")
        self.assertEqual(core.plan(False, False, True), "add")
        self.assertEqual(core.plan(True, False, False), "add")
        self.assertEqual(core.plan(False, True, False), "toggle")
        self.assertEqual(core.plan(True, True, False), "add", "Shift wins: it never removes")

    def test_click_plan(self):
        self.assertEqual(core.click_plan(False, False, False, False), "replace")
        self.assertEqual(core.click_plan(False, False, True, False), "add")
        self.assertEqual(core.click_plan(True, False, False, False), "add")
        self.assertEqual(core.click_plan(True, False, False, True), "keep")
        self.assertEqual(core.click_plan(False, True, False, True), "toggle")

    def test_mode_keys_and_labels(self):
        self.assertEqual(core.MODE_KEYS["1"], "window")
        self.assertEqual(core.MODE_KEYS["2"], "freeform")
        self.assertEqual(core.MODE_KEYS["3"], "paint")
        self.assertEqual(core.DEFAULT_MODE, "window")
        for mode in core.MODES:
            self.assertIn(mode, core.MODE_LABELS)


class BoxMathsTests(unittest.TestCase):
    def test_direction(self):
        self.assertEqual(core.box_mode(10, 50), "window")
        self.assertEqual(core.box_mode(50, 10), "crossing")
        self.assertEqual(core.box_mode(30, 30), "window")

    def test_rect_polygon_is_normalised(self):
        self.assertEqual(core.rect_polygon(50, 40, 10, 10), BOX)
        self.assertEqual(core.bounds(BOX), (10, 10, 50, 40))

    def test_point_in_polygon(self):
        self.assertTrue(core.point_in_polygon(20, 20, BOX))
        self.assertTrue(core.point_in_polygon(10, 20, BOX), "the boundary counts as inside")
        self.assertTrue(core.point_in_polygon(50, 40, BOX))
        self.assertFalse(core.point_in_polygon(60, 20, BOX))
        self.assertFalse(core.point_in_polygon(20, 5, BOX))
        concave = [(0, 0), (40, 0), (40, 40), (20, 10), (0, 40)]
        self.assertTrue(core.point_in_polygon(5, 30, concave))
        self.assertFalse(core.point_in_polygon(20, 30, concave), "inside the notch")
        self.assertFalse(core.point_in_polygon(1, 1, [(0, 0), (1, 1)]), "no polygon yet")

    def test_segments_cross(self):
        self.assertTrue(core.segments_cross((0, 0), (10, 10), (0, 10), (10, 0)))
        self.assertFalse(core.segments_cross((0, 0), (10, 0), (0, 5), (10, 5)))
        self.assertTrue(core.segments_cross((0, 0), (10, 0), (5, 0), (5, 5)), "touching counts")
        self.assertTrue(core.segments_cross((0, 0), (10, 0), (5, -1), (5, 1)))
        self.assertFalse(core.segments_cross((0, 0), (1, 0), (2, 0), (3, 0)), "collinear apart")
        self.assertTrue(core.segments_cross((0, 0), (2, 0), (1, 0), (3, 0)), "collinear overlap")

    def test_window_takes_only_what_is_fully_inside(self):
        inside = square(20, 20, 30, 30)
        half = square(40, 20, 60, 30)  # sticks out to the right
        outside = square(70, 70, 80, 80)
        self.assertTrue(core.element_selected(*inside[:2], BOX, "window", inside[2]))
        self.assertFalse(core.element_selected(*half[:2], BOX, "window", half[2]))
        self.assertFalse(core.element_selected(*outside[:2], BOX, "window", outside[2]))
        self.assertFalse(core.element_selected([], [], BOX, "window"))

    def test_crossing_takes_what_the_box_touches(self):
        half = square(40, 20, 60, 30)
        outside = square(70, 70, 80, 80)
        self.assertTrue(core.element_selected(*half[:2], BOX, "crossing", half[2]))
        self.assertFalse(core.element_selected(*outside[:2], BOX, "crossing", outside[2]))
        # An edge passing straight through the box, both ends outside.
        edge = [(0, 25), (100, 25)]
        self.assertTrue(core.element_selected(edge, [(edge[0], edge[1])], BOX, "crossing"))
        self.assertFalse(core.element_selected(edge, [(edge[0], edge[1])], BOX, "window"))
        # An edge that only touches the box's corner.
        corner = [(0, 0), (10, 10)]
        self.assertTrue(core.element_selected(corner, [(corner[0], corner[1])], BOX, "crossing"))

    def test_small_box_inside_a_big_face_crosses_it(self):
        big = square(0, 0, 100, 100)
        self.assertTrue(core.element_selected(*big[:2], BOX, "crossing", big[2]))
        self.assertFalse(core.element_selected(*big[:2], BOX, "window", big[2]))
        # Without its outline, an element the box lies inside is not known to be touched.
        self.assertFalse(core.element_selected(*big[:2], BOX, "crossing"))

    def test_lasso(self):
        lasso = [(0, 0), (60, 0), (60, 60), (30, 30), (0, 60)]  # a notch at the top
        inside = square(5, 5, 20, 20)
        in_notch = square(27, 38, 33, 45)  # clear of the notch's sides
        self.assertTrue(core.element_selected(*inside[:2], lasso, "window", inside[2]))
        self.assertFalse(core.element_selected(*in_notch[:2], lasso, "window", in_notch[2]))
        self.assertFalse(core.element_selected(*in_notch[:2], lasso, "crossing", in_notch[2]))
        simple = core.simplify_lasso([(0, 0), (1, 0), (2, 0), (5, 0), (5.5, 0.5), (9, 0)])
        self.assertEqual(simple, [(0, 0), (5, 0), (9, 0)])

    def test_quick_reject(self):
        self.assertTrue(core.quick_reject([(70, 70), (80, 80)], BOX))
        self.assertFalse(core.quick_reject([(45, 35), (80, 80)], BOX))
        self.assertTrue(core.quick_reject([], BOX))


class SelectOtherTests(unittest.TestCase):
    def test_front_to_back_and_dedupe(self):
        camera = (0, 0, 100)
        direction = (0, 0, -1)
        items = [("bottom", (0, 0, 0)), ("top", (0, 0, 10)), ("middle", (0, 0, 5))]
        self.assertEqual(
            core.order_front_to_back(items, camera, direction), ["top", "middle", "bottom"]
        )
        kept = core.dedupe([(("Box", "Face6"), 1), (("Box", "Face6"), 2), (("Box", "Edge1"), 3)])
        self.assertEqual([k for k, _ in kept], [("Box", "Face6"), ("Box", "Edge1")])
        self.assertEqual(kept[0][1], 1, "the first (nearest) entry is kept")

    def test_labels(self):
        self.assertEqual(core.pretty_element("Face6"), "Face 6")
        self.assertEqual(core.pretty_element("Edge12"), "Edge 12")
        self.assertEqual(core.pretty_element(""), "Body")
        self.assertEqual(core.row_label("Face6", "Body"), "Face 6  ·  Body")
        self.assertEqual(core.row_label("", "Body"), "Body")
        self.assertIn("Body Faces", core.filter_message("faces"))

    def test_depth_tolerance(self):
        self.assertAlmostEqual(core.depth_tolerance(100.0), 0.2)
        self.assertEqual(core.depth_tolerance(0.0), 1e-4)


if __name__ == "__main__":
    unittest.main()
