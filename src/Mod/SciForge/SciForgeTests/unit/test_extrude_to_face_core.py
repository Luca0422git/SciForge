# SPDX-License-Identifier: LGPL-2.1-or-later
"""A click on a face while extruding ends the extrusion there (Luca's request; Fusion):
which faces give a height, which side of the extrude they set, the number and the words
(sciforge/extrude_to_face_core.py). Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import extrude_to_face_core as core  # noqa: E402

UP = (0.0, 0.0, 1.0)


def opts(**kw):
    base = {
        "direction": "one_side",
        "measurement": "half",
        "distance": 0.0,
        "extent": "distance",
        "extent2": "distance",
    }
    base.update(kw)
    return base


class KindTests(unittest.TestCase):
    def test_parallel_flat_face_gives_a_height(self):
        self.assertEqual(core.kind_of("flat", (0, 0, 1), UP), "height")
        self.assertEqual(core.kind_of("flat", (0, 0, -1), UP), "height")  # a face looking down
        self.assertEqual(core.kind_of("plane", (0, 0, 1), UP), "height")

    def test_vertex_gives_a_height(self):
        self.assertEqual(core.kind_of("vertex", None, UP), "height")

    def test_face_along_the_extrusion_cannot_end_it(self):
        self.assertEqual(core.kind_of("flat", (1, 0, 0), UP), "along")
        self.assertEqual(core.kind_of("plane", (0, 1, 0), UP), "along")

    def test_curved_or_tilted_face_is_to_object(self):
        self.assertEqual(core.kind_of("curved", None, UP), "object")
        tilted = (0.0, 0.6, 0.8)
        self.assertEqual(core.kind_of("flat", tilted, UP), "object")
        self.assertEqual(core.what_of("flat", "object"), "sloped")
        self.assertEqual(core.what_of("curved", "object"), "curved")
        self.assertEqual(core.what_of("flat", "height"), "face")
        self.assertEqual(core.what_of("vertex", "height"), "point")
        self.assertEqual(core.what_of("plane", "height"), "plane")

    def test_height_is_signed_along_the_normal(self):
        self.assertAlmostEqual(core.height((3, 4, 12.5), (0, 0, 0), UP), 12.5)
        self.assertAlmostEqual(core.height((3, 4, -7), (0, 0, 2), UP), -9.0)

    def test_in_the_profile_plane(self):
        self.assertTrue(core.in_profile_plane(0.0, [0.0]))
        self.assertTrue(core.in_profile_plane(5.00001, [0.0, 5.0]))
        self.assertFalse(core.in_profile_plane(5.0, [0.0]))


class PlanTests(unittest.TestCase):
    def test_one_side_up_to_a_taller_face(self):
        p = core.plan("height", 12.5, opts())
        self.assertEqual(p["action"], "distance")
        self.assertEqual(p["key"], "distance")
        self.assertEqual(p["value"], 12.5)
        self.assertEqual(p["extent"], "distance")
        self.assertEqual(p["note"], "Up to the face: 12.5 mm")

    def test_one_side_down_to_a_lower_face_is_negative(self):
        p = core.plan("height", -20.0, opts(distance=5.0))
        self.assertEqual((p["key"], p["value"]), ("distance", -20.0))
        self.assertEqual(p["note"], "Up to the face: -20 mm")

    def test_all_becomes_distance(self):
        p = core.plan("height", 8.0, opts(extent="all"))
        self.assertEqual((p["action"], p["extent"], p["value"]), ("distance", "distance", 8.0))

    def test_point_and_plane_words(self):
        self.assertEqual(core.plan("height", 3.0, opts(), "point")["note"], "Up to the point: 3 mm")
        self.assertEqual(core.plan("height", 3.0, opts(), "plane")["note"], "Up to the plane: 3 mm")

    def test_where_it_starts_is_refused(self):
        p = core.plan("height", 0.00001, opts())
        self.assertEqual(p["action"], "refuse")
        self.assertIn("where the extrusion starts", p["message"])
        self.assertTrue(p["message"].startswith("That face"))

    def test_face_along_the_extrusion_is_refused(self):
        p = core.plan("along", 4.0, opts())
        self.assertEqual(p["action"], "refuse")
        self.assertTrue(p["message"].startswith("That face runs along the extrusion"))

    def test_two_sides_picks_the_side_the_face_is_on(self):
        above = core.plan("height", 12.0, opts(direction="two_sides", distance=5.0))
        self.assertEqual((above["key"], above["value"]), ("distance", 12.0))
        self.assertEqual(above["note"], "Side One up to the face: 12 mm")
        below = core.plan("height", -8.0, opts(direction="two_sides", distance=5.0))
        self.assertEqual((below["key"], below["value"]), ("distance2", 8.0))
        self.assertEqual(below["note"], "Side Two up to the face: 8 mm")

    def test_two_sides_with_side_one_pointing_down(self):
        down = core.plan("height", -6.0, opts(direction="two_sides", distance=-4.0))
        self.assertEqual((down["key"], down["value"]), ("distance", -6.0))
        up = core.plan("height", 6.0, opts(direction="two_sides", distance=-4.0))
        self.assertEqual((up["key"], up["value"]), ("distance2", 6.0))

    def test_two_sides_at_zero_side_one_goes_up(self):
        self.assertEqual(core.side_for(3.0, "two_sides", 0.0), 1)
        self.assertEqual(core.side_for(-3.0, "two_sides", 0.0), 2)
        self.assertEqual(core.side_for(-3.0, "one_side", 0.0), 1)

    def test_symmetric_half_and_whole(self):
        half = core.plan("height", -7.5, opts(direction="symmetric"))
        self.assertEqual((half["key"], half["value"]), ("distance", 7.5))
        self.assertEqual(half["note"], "Up to the face: 7.5 mm on each side")
        whole = core.plan("height", 7.5, opts(direction="symmetric", measurement="whole"))
        self.assertEqual(whole["value"], 15.0)
        self.assertEqual(whole["note"], "Up to the face: 15 mm in all (7.5 mm on each side)")

    def test_to_object_side_takes_the_parallel_face_as_its_object(self):
        p = core.plan("height", 9.0, opts(extent="to_object"))
        self.assertEqual((p["action"], p["side"]), ("to_object", 1))
        self.assertEqual(p["note"], "Ends on the face (To Object)")
        # a point is no To Object target: the distance is set instead
        q = core.plan("height", 9.0, opts(extent="to_object"), "point")
        self.assertEqual((q["action"], q["value"]), ("distance", 9.0))

    def test_curved_face_switches_to_to_object(self):
        p = core.plan("object", 14.0, opts(), "curved")
        self.assertEqual((p["action"], p["side"]), ("to_object", 1))
        self.assertEqual(p["note"], "Ends on the curved face (To Object)")
        q = core.plan("object", -5.0, opts(direction="two_sides", distance=3.0), "sloped")
        self.assertEqual((q["action"], q["side"]), ("to_object", 2))
        self.assertEqual(q["note"], "Side Two ends on the sloped face (To Object)")

    def test_symmetric_cannot_end_on_a_curved_face(self):
        p = core.plan("object", 14.0, opts(direction="symmetric"), "curved")
        self.assertEqual(p["action"], "refuse")
        self.assertIn("One Side", p["message"])
        self.assertIn("curved face", p["message"])


class DragTests(unittest.TestCase):
    def test_side_one_arrow(self):
        self.assertEqual(core.drag_value("distance", 12.5, "one_side", "half"), 12.5)
        self.assertEqual(core.drag_value("distance", -4.0, "one_side", "half"), -4.0)
        self.assertIsNone(core.drag_value("distance", 0.0, "one_side", "half"))

    def test_side_two_arrow_points_the_other_way(self):
        self.assertEqual(core.drag_value("distance2", -6.0, "two_sides", "half"), 6.0)
        self.assertIsNone(core.drag_value("distance2", 6.0, "two_sides", "half"))

    def test_symmetric_arrow(self):
        self.assertEqual(core.drag_value("distance", -5.0, "symmetric", "half"), 5.0)
        self.assertEqual(core.drag_value("distance", 5.0, "symmetric", "whole"), 10.0)

    def test_snap_words(self):
        self.assertEqual(core.snap_note("distance", 12.5, "one_side"), "Up to the face: 12.5 mm")
        self.assertEqual(
            core.snap_note("distance2", 6.0, "two_sides", what="point"),
            "Side Two up to the point: 6 mm",
        )

    def test_length_text(self):
        self.assertEqual(core.length_text(12.5), "12.5 mm")
        self.assertEqual(core.length_text(20.0), "20 mm")
        self.assertEqual(core.length_text(1.0 / 3.0), "0.333 mm")
        self.assertEqual(core.length_text(-0.0001), "0 mm")


if __name__ == "__main__":
    unittest.main()
