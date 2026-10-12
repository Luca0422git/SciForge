# SPDX-License-Identifier: LGPL-2.1-or-later
"""The ViewCube's shape and camera maths (sciforge/viewcube.py). Runs without FreeCAD."""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import viewcube as vc  # noqa: E402

# FreeCAD 1.1.4's own camera orientations (View3DInventorPy.viewFront() etc., read in the
# real program), quaternion (x, y, z, w).
FREECAD_VIEWS = {
    "front": (0.70710678, 0.0, 0.0, 0.70710678),
    "top": (0.0, 0.0, 0.0, 1.0),
    "right": (0.5, 0.5, 0.5, 0.5),
    "back": (0.0, 0.70710678, 0.70710678, 0.0),
    "left": (-0.5, 0.5, 0.5, -0.5),
    "bottom": (1.0, 0.0, 0.0, 0.0),
    "top-front-right": (0.42470813, 0.17592004, 0.33985109, 0.82047326),  # viewIsometric
}
CX, CY, SIZE = 72.0, 78.0, 33.0


def close(a, b, tol=1e-9):
    return all(abs(x - y) < tol for x, y in zip(a, b))


class RegionTests(unittest.TestCase):
    def test_26_parts(self):
        kinds = [r["kind"] for r in vc.REGIONS]
        self.assertEqual(len(vc.REGIONS), 26)
        self.assertEqual(
            (kinds.count("face"), kinds.count("edge"), kinds.count("corner")), (6, 12, 8)
        )
        self.assertEqual(len({r["name"] for r in vc.REGIONS}), 26)

    def test_names(self):
        self.assertEqual(vc.direction_of("front"), (0, -1, 0))
        self.assertEqual(vc.direction_of("top-front"), (0, -1, 1))
        self.assertEqual(vc.direction_of("bottom-back-left"), (-1, 1, -1))

    def test_pieces_are_flat_and_face_outwards(self):
        for region in vc.REGIONS:
            n = vc.unit(region["direction"])
            heights = [vc.dot(p, n) for p in region["points"]]
            self.assertLess(max(heights) - min(heights), 1e-9, region["name"])
            self.assertGreater(heights[0], 0.9, region["name"])


class TargetTests(unittest.TestCase):
    def test_faces_and_iso_match_freecad(self):
        for name, q in FREECAD_VIEWS.items():
            self.assertTrue(vc.same_orientation(vc.target_orientation(name), q, 1e-7), name)

    def test_every_part_looks_straight_at_it(self):
        for region in vc.REGIONS:
            q = vc.target_orientation(region["name"])
            right, up, view = vc.camera_axes(q)
            want = vc.scale(vc.unit(region["direction"]), -1.0)
            self.assertTrue(close(view, want), region["name"])
            self.assertAlmostEqual(vc.dot(right, up), 0.0)
            if region["name"] not in ("top", "bottom"):
                self.assertLess(abs(right[2]), 1e-9, "level: " + region["name"])
                self.assertGreater(up[2], 0.0, "Z up: " + region["name"])

    def test_top_and_bottom_up_directions(self):
        self.assertTrue(close(vc.camera_axes(vc.target_orientation("top"))[1], (0, 1, 0)))
        self.assertTrue(close(vc.camera_axes(vc.target_orientation("bottom"))[1], (0, -1, 0)))

    def test_edge_is_halfway(self):
        view = vc.camera_axes(vc.target_orientation("front-right"))[2]
        self.assertTrue(close(view, (-1 / math.sqrt(2), 1 / math.sqrt(2), 0.0)))


class ArrowTests(unittest.TestCase):
    def test_turns_reach_the_neighbouring_faces(self):
        front = vc.target_orientation("front")
        self.assertTrue(vc.same_orientation(vc.turn(front, "up"), vc.target_orientation("top")))
        self.assertTrue(
            vc.same_orientation(vc.turn(front, "right"), vc.target_orientation("right"))
        )
        self.assertTrue(vc.same_orientation(vc.turn(front, "left"), vc.target_orientation("left")))
        self.assertTrue(
            vc.same_orientation(vc.turn(front, "down"), vc.target_orientation("bottom"))
        )

    def test_turns_undo_each_other_and_stay_exact(self):
        q = vc.target_orientation("front")
        for a, b in (("up", "down"), ("left", "right")):
            self.assertTrue(vc.same_orientation(vc.turn(vc.turn(q, a), b), q, 1e-12), a)
        r = q
        for _ in range(4):
            r = vc.turn(r, "up")
        self.assertTrue(vc.same_orientation(r, q, 1e-12))

    def test_roll(self):
        q = vc.target_orientation("front")
        right, up, view = vc.camera_axes(vc.roll(q, True))
        self.assertTrue(close(view, (0, 1, 0)))
        self.assertTrue(close(up, (-1, 0, 0)), up)  # clockwise: the top now points right
        self.assertTrue(close(right, (0, 0, 1)))
        self.assertTrue(vc.same_orientation(vc.roll(vc.roll(q, True), False), q, 1e-12))
        r = q
        for _ in range(4):
            r = vc.roll(r, False)
        self.assertTrue(vc.same_orientation(r, q, 1e-12))

    def test_face_on(self):
        self.assertEqual(vc.face_on(vc.target_orientation("back")), "back")
        self.assertEqual(vc.face_on(vc.roll(vc.target_orientation("top"), True)), "top")
        self.assertIsNone(vc.face_on(vc.target_orientation("top-front-right")))
        self.assertIsNone(vc.face_on(vc.target_orientation("front-left")))


class OrbitTests(unittest.TestCase):
    def test_never_rolls(self):
        rnd = random.Random(4)
        q = vc.target_orientation("top-front-right")
        for _ in range(300):
            q = vc.orbit(q, rnd.uniform(-30, 30), rnd.uniform(-30, 30))
            self.assertLess(vc.roll_of(q), 1e-9)

    def test_sideways_turns_about_z(self):
        q = vc.target_orientation("top-front-right")
        before = vc.camera_axes(q)[2]
        after = vc.camera_axes(vc.orbit(q, 50, 0))[2]
        self.assertAlmostEqual(before[2], after[2])
        self.assertAlmostEqual(
            math.degrees(math.atan2(after[1], after[0]) - math.atan2(before[1], before[0])) % 360,
            360 - 50 * vc.ORBIT_DEG_PER_PIXEL,
        )

    def test_like_shift_middle_drag(self):
        # Measured in FreeCAD with its turntable orbit, from FRONT: dragging right swings the
        # camera towards -X (it looks a little towards +X), dragging down looks from above.
        front = vc.target_orientation("front")
        self.assertGreater(vc.camera_axes(vc.orbit(front, 20, 0))[2][0], 0.1)
        self.assertLess(vc.camera_axes(vc.orbit(front, 0, 20))[2][2], -0.1)


class LayoutTests(unittest.TestCase):
    def test_front_view(self):
        parts = vc.layout(vc.target_orientation("front"), CX, CY, SIZE)
        names = {p["name"] for p in parts}
        self.assertIn("front", names)
        self.assertIn("top-front", names)
        self.assertIn("top-front-right", names)
        self.assertNotIn("top", names)  # seen exactly edge-on
        self.assertNotIn("back", names)
        self.assertEqual(vc.pick(parts, CX, CY), "front")
        self.assertEqual(vc.pick(parts, CX + 40, CY), None)

    def test_iso_view_and_order(self):
        parts = vc.layout(vc.target_orientation("top-front-right"), CX, CY, SIZE)
        names = [p["name"] for p in parts]
        for name in ("front", "right", "top", "top-front", "front-right", "top-right"):
            self.assertIn(name, names)
        self.assertEqual(names[-1], "top-front-right")  # nearest, drawn last
        depths = [p["depth"] for p in parts]
        self.assertEqual(depths, sorted(depths))
        for part in parts:  # every part's middle picks that part
            x, y = vc.centroid(part["points"])
            self.assertEqual(vc.pick(parts, x, y), part["name"])

    def test_label_reads_upright_on_front(self):
        m11, m12, m21, m22, dx, dy = vc.label_transform(
            vc.target_orientation("front"), "front", CX, CY, SIZE
        )
        self.assertTrue(close((m11, m12, m21, m22, dx, dy), (SIZE, 0, 0, SIZE, CX, CY), 1e-9))


class ControlTests(unittest.TestCase):
    def test_buttons_are_hit_at_their_middle(self):
        for control in vc.controls(CX, CY, SIZE, (6, 6, 18)):
            x, y = vc.control_centre(control)
            self.assertTrue(vc.hit_control(control, x, y), control["id"])
            hits = [
                c["id"] for c in vc.controls(CX, CY, SIZE, (6, 6, 18)) if vc.hit_control(c, x, y)
            ]
            self.assertEqual(hits, [control["id"]])

    def test_arrows_are_outside_the_face_on_cube(self):
        parts = vc.layout(vc.target_orientation("front"), CX, CY, SIZE)
        for control in vc.controls(CX, CY, SIZE, (6, 6, 18)):
            x, y = vc.control_centre(control)
            self.assertIsNone(vc.pick(parts, x, y), control["id"])


class HomeTests(unittest.TestCase):
    def test_round_trip(self):
        q = vc.target_orientation("top-front")
        home = vc.decode_home(vc.encode_home(q, True))
        self.assertTrue(vc.same_orientation(home["rotation"], q))
        self.assertTrue(home["fit"])
        text = vc.encode_home(q, False, "OrthographicCamera {\n  height 10\n}\n")
        self.assertNotIn("\n", text)  # one line in the document's XML
        home = vc.decode_home(text)
        self.assertFalse(home["fit"])
        self.assertIn("height 10", home["camera"])

    def test_bad_text_means_default(self):
        for text in (None, "", "nonsense", "{}", '{"rotation": [0, 0, 0, 0]}', '{"rotation": [1]}'):
            self.assertIsNone(vc.decode_home(text), text)
        default = vc.default_home()
        self.assertTrue(vc.same_orientation(default["rotation"], FREECAD_VIEWS["top-front-right"]))
        self.assertTrue(default["fit"])

    def test_fixed_without_camera_falls_back_to_fit(self):
        home = vc.decode_home('{"rotation": [0, 0, 0, 1], "fit": false}')
        self.assertTrue(home["fit"])


if __name__ == "__main__":
    unittest.main()
