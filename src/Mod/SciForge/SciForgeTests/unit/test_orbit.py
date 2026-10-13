# SPDX-License-Identifier: LGPL-2.1-or-later
"""The orbit modes and the orbit about a chosen centre (sciforge/orbit.py). No FreeCAD."""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import orbit, viewcube as vc  # noqa: E402

ISO = vc.q_unit((0.42470813, 0.17592004, 0.33985109, 0.82047326))  # FreeCAD's isometric view


def close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


class ModeTests(unittest.TestCase):
    def test_modes_and_default(self):
        self.assertEqual(orbit.normalise_mode("free"), "free")
        self.assertEqual(orbit.normalise_mode(" Constrained "), "constrained")
        self.assertEqual(orbit.normalise_mode(""), "constrained")
        self.assertEqual(orbit.normalise_mode(None), "constrained")
        self.assertEqual(orbit.normalise_mode("trackball"), "constrained")

    def test_freecad_styles(self):
        # Constrained = FreeCAD's Free Turntable (2), Free = FreeCAD's Rounded Arcball (4)
        self.assertEqual(orbit.freecad_style("constrained"), 2)
        self.assertEqual(orbit.freecad_style("free"), 4)
        self.assertEqual(orbit.freecad_style("nonsense"), 2)
        self.assertEqual(orbit.mode_of_style(2), "constrained")
        self.assertEqual(orbit.mode_of_style(4), "free")
        self.assertIsNone(orbit.mode_of_style(1))

    def test_degrees_per_pixel_follow_the_view_size(self):
        dx, dy = orbit.degrees_per_pixel(1000, 500)
        self.assertAlmostEqual(dx, math.degrees(2.0 * 2.0 / (1000 * 0.8)))  # sensitivity 2
        self.assertAlmostEqual(dy, 2 * dx)
        self.assertAlmostEqual(orbit.degrees_per_pixel(1000, 500, 3.0)[0], 1.5 * dx)
        self.assertAlmostEqual(orbit.degrees_per_pixel(1000, 500, 0.5)[0], dx / 2)  # <= 1: off
        self.assertGreater(orbit.degrees_per_pixel(0, 0)[0], 0)


class TurnTests(unittest.TestCase):
    def test_no_move_no_turn(self):
        for mode in orbit.MODES:
            self.assertTrue(vc.same_orientation(orbit.turn(ISO, 0, 0, mode), ISO, 1e-9), mode)

    def test_constrained_matches_the_viewcube_orbit(self):
        for dx, dy in ((40, 0), (0, 25), (-30, 17), (120, -90)):
            mine = orbit.turn(ISO, dx, dy, "constrained", vc.ORBIT_DEG_PER_PIXEL)
            self.assertTrue(vc.same_orientation(mine, vc.orbit(ISO, dx, dy), 1e-9))

    def test_constrained_never_rolls(self):
        rng = random.Random(7)
        q = ISO
        for _ in range(300):
            q = orbit.turn(q, rng.uniform(-60, 60), rng.uniform(-60, 60), "constrained", 0.3, 0.5)
            self.assertLess(vc.roll_of(q), 1e-6)

    def test_constrained_sideways_keeps_the_tilt(self):
        before = vc.camera_axes(ISO)[2]
        after = vc.camera_axes(orbit.turn(ISO, 80, 0, "constrained", 0.3, 0.5))[2]
        self.assertAlmostEqual(before[2], after[2], places=9)

    def test_free_turns_about_the_cameras_own_axes(self):
        right, up, _ = vc.camera_axes(ISO)
        # a sideways move keeps the camera's up axis; an up/down move keeps its right axis
        sideways = orbit.turn(ISO, 50, 0, "free", 0.5, 0.5)
        self.assertTrue(close(vc.camera_axes(sideways)[1], up, 1e-9))
        self.assertGreater(vc.angle_between(ISO, sideways), 20)
        updown = orbit.turn(ISO, 0, 50, "free", 0.5, 0.5)
        self.assertTrue(close(vc.camera_axes(updown)[0], right, 1e-9))

    def test_free_can_roll_over_a_loop(self):
        q = ISO
        for dx, dy in ((60, 0), (0, 60), (-60, 0), (0, -60)):
            q = orbit.turn(q, dx, dy, "free", 0.5, 0.5)
        self.assertGreater(vc.roll_of(q), 0.01)


class PivotTests(unittest.TestCase):
    def test_pivot_stays_where_the_camera_sees_it(self):
        rng = random.Random(3)
        for mode in orbit.MODES:
            for _ in range(60):
                position = tuple(rng.uniform(-300, 300) for _ in range(3))
                pivot = tuple(rng.uniform(-50, 50) for _ in range(3))
                q = vc.q_unit(tuple(rng.uniform(-1, 1) for _ in range(4)))
                dx, dy = rng.uniform(-100, 100), rng.uniform(-100, 100)
                new_position, new_q = orbit.orbit_camera(position, q, pivot, dx, dy, mode, 0.2, 0.3)
                before = orbit.in_camera(position, q, pivot)
                after = orbit.in_camera(new_position, new_q, pivot)
                self.assertTrue(close(before, after, 1e-6), (mode, before, after))
                # the camera stays as far from the pivot as it was
                d0 = math.dist(position, pivot)
                d1 = math.dist(new_position, pivot)
                self.assertAlmostEqual(d0, d1, places=6)

    def test_orientation_is_the_plain_turn(self):
        new_position, new_q = orbit.orbit_camera(
            (0, -100, 50), ISO, (10, 20, 5), 30, -20, "free", 0.4
        )
        self.assertTrue(vc.same_orientation(new_q, orbit.turn(ISO, 30, -20, "free", 0.4), 1e-9))

    def test_about_the_focal_point_is_freecads_own_orbit(self):
        """With the pivot at the point the camera looks at, the focal point does not move:
        that is what FreeCAD's orbit (and the ViewCube's drag) does."""
        position = (0.0, -200.0, 120.0)
        focal = orbit.focal_point(position, ISO, 230.0)
        new_position, new_q = orbit.orbit_camera(position, ISO, focal, 45, 15, "constrained", 0.3)
        self.assertTrue(close(orbit.focal_point(new_position, new_q, 230.0), focal, 1e-6))

    def test_no_move_leaves_the_camera(self):
        position, new_q = orbit.orbit_camera((1, 2, 3), ISO, (7, 8, 9), 0, 0)
        self.assertTrue(close(position, (1, 2, 3), 1e-9))
        self.assertTrue(vc.same_orientation(new_q, ISO, 1e-9))


if __name__ == "__main__":
    unittest.main()
