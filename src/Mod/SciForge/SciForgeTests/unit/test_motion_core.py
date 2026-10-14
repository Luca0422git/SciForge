# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dragging along joints, motion links, contact and motion studies (sciforge/motion_core.py),
and the joint position modes of joints_core. Runs without FreeCAD."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import joints_core as core  # noqa: E402
from sciforge import motion_core as mc  # noqa: E402


def close(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def ray_through(eye, target):
    return eye, core.unit(core.vsub(target, eye))


class TurnTests(unittest.TestCase):
    """A revolute arm turning about the Z axis through the origin; the grab point at (10, 0,
    5). Seen from above (the dial), the angle is the pointer's angle round the axis."""

    def test_view_from_above_gives_the_pointer_angle(self):
        for target_deg in (0, 30, 90, 135, -60):
            t = math.radians(target_deg)
            o, d = (20 * math.cos(t), 20 * math.sin(t), 100.0), (0.0, 0.0, -1.0)
            got = mc.turn_from_ray((0, 0, 0), (0, 0, 1), (10, 0, 5), o, d, previous=0.0)
            self.assertAlmostEqual(got, target_deg, places=6)

    def test_radius_of_the_pointer_does_not_matter(self):
        # a dial: the pointer near the axis or far away gives the same angle
        o1 = (2.0, 2.0, 50.0)
        o2 = (200.0, 200.0, 50.0)
        d = (0.0, 0.0, -1.0)
        a1 = mc.turn_from_ray((0, 0, 0), (0, 0, 1), (10, 0, 0), o1, d)
        a2 = mc.turn_from_ray((0, 0, 0), (0, 0, 1), (10, 0, 0), o2, d)
        self.assertAlmostEqual(a1, 45.0, places=6)
        self.assertAlmostEqual(a2, 45.0, places=6)

    def test_a_drag_round_and_round_keeps_counting(self):
        previous = 0.0
        for deg in range(0, 721, 30):
            t = math.radians(deg)
            o = (10 * math.cos(t), 10 * math.sin(t), 30.0)
            previous = mc.turn_from_ray(
                (0, 0, 0), (0, 0, 1), (5, 0, 0), o, (0, 0, -1), previous=previous
            )
        self.assertAlmostEqual(previous, 720.0, places=6)

    def test_slanted_view_still_gives_the_angle_in_the_plane(self):
        eye = (0.0, -60.0, 60.0)
        target = (0.0, 10.0, 0.0)  # 90 degrees round from the grab point (10, 0, 0)
        o, d = ray_through(eye, target)
        got = mc.turn_from_ray((0, 0, 0), (0, 0, 1), (10, 0, 0), o, d)
        self.assertAlmostEqual(got, 90.0, places=6)

    def test_edge_on_view_takes_the_nearest_point_of_the_circle(self):
        # looking along -Y at the arm turning about Z: the circle shows as a line; a pointer
        # at x = 5 lines up with the two points of the circle at 60 and -60 degrees
        d = (0.0, 1.0, 0.0)
        o = (5.0, -100.0, 0.0)
        got = mc.turn_from_ray((0, 0, 0), (0, 0, 1), (10, 0, 0), o, d, previous=10.0)
        self.assertAlmostEqual(got, 60.0, delta=0.01)
        got = mc.turn_from_ray((0, 0, 0), (0, 0, 1), (10, 0, 0), o, d, previous=-10.0)
        self.assertAlmostEqual(got, -60.0, delta=0.01)

    def test_grab_on_the_axis_cannot_turn(self):
        self.assertIsNone(mc.turn_from_ray((0, 0, 0), (0, 0, 1), (0, 0, 7), (1, 1, 9), (0, 0, -1)))

    def test_unwrap(self):
        self.assertAlmostEqual(mc.unwrap(-170.0, 170.0), 190.0)
        self.assertAlmostEqual(mc.unwrap(10.0, 350.0), 370.0)
        self.assertAlmostEqual(mc.unwrap(10.0, None), 10.0)


class SlideTests(unittest.TestCase):
    def test_slide_to_the_point_nearest_the_pointer(self):
        # a slider along X; the pointer looks straight down at x = 12.5
        s = mc.slide_from_ray((2, 0, 0), (1, 0, 0), (12.5, 4.0, 50.0), (0, 0, -1))
        self.assertAlmostEqual(s, 10.5, places=9)

    def test_slanted_view(self):
        o, d = ray_through((0, -40, 30), (25, 0, 0))
        s = mc.slide_from_ray((0, 0, 0), (1, 0, 0), o, d)
        self.assertAlmostEqual(s, 25.0, places=6)

    def test_seen_end_on_cannot_slide(self):
        self.assertIsNone(mc.slide_from_ray((0, 0, 0), (0, 0, 1), (3, 3, 30), (0, 0, -1)))


class PlaneTests(unittest.TestCase):
    def test_free_move_in_the_view_plane(self):
        move = mc.free_move_from_ray((1, 2, 3), (0, 0, -1), (7, -4, 50), (0, 0, -1))
        self.assertTrue(close(move, (6, -6, 0)))

    def test_planar_move_stays_in_the_plane(self):
        o, d = ray_through((0, -50, 50), (10, 5, 0))
        move = mc.plane_move_from_ray((0, 0, 0), (0, 0, 1), o, d)
        self.assertTrue(close(move, (10, 5, 0)))

    def test_plane_seen_edge_on(self):
        self.assertIsNone(mc.plane_move_from_ray((0, 0, 0), (0, 0, 1), (0, -10, 0), (0, 1, 0)))


class BallTests(unittest.TestCase):
    def test_ball_turns_the_grab_point_under_the_pointer(self):
        rot = mc.ball_turn_from_ray((0, 0, 0), (10, 0, 0), (0, 10, 50), (0, 0, -1))
        moved = core.rot_apply(rot, (10, 0, 0))
        self.assertTrue(close(moved, (0, 10, 0)))

    def test_pointer_cutting_the_sphere_takes_the_front_point(self):
        rot = mc.ball_turn_from_ray((0, 0, 0), (10, 0, 0), (6, 0, 50), (0, 0, -1))
        moved = core.rot_apply(rot, (10, 0, 0))
        self.assertTrue(close(moved, (6, 0, 8)))

    def test_rotation_between_opposite_directions(self):
        r = mc.rotation_between((1, 0, 0), (-1, 0, 0))
        self.assertTrue(close(core.rot_apply(r, (1, 0, 0)), (-1, 0, 0)))


class LinkTests(unittest.TestCase):
    def test_gear_and_rack(self):
        # a pinion of radius 10: one turn moves the rack one circumference
        ratio = mc.link_ratio(360.0, 2 * math.pi * 10)
        offset = mc.link_offset(ratio, 0.0, 0.0)
        self.assertAlmostEqual(mc.linked_value(360.0, ratio, offset), 62.83185307, places=6)
        self.assertAlmostEqual(mc.linked_value(-90.0, ratio, offset), -15.70796327, places=6)

    def test_reverse_turns_the_second_the_other_way(self):
        ratio = mc.link_ratio(360.0, 720.0, reverse=True)
        self.assertAlmostEqual(ratio, -2.0)

    def test_offset_keeps_both_where_they_are(self):
        ratio = mc.link_ratio(90.0, 30.0)
        offset = mc.link_offset(ratio, 45.0, 7.0)
        self.assertAlmostEqual(mc.linked_value(45.0, ratio, offset), 7.0)
        self.assertAlmostEqual(mc.unlinked_value(7.0, ratio, offset), 45.0)

    def test_zero_first_value_is_refused(self):
        with self.assertRaises(mc.LinkError):
            mc.link_ratio(0.0, 10.0)


class ContactTests(unittest.TestCase):
    def test_last_free_finds_the_touching_point(self):
        # a block 10 away from a wall, moved 30: it touches after a third of the move
        f = mc.last_free(lambda f: 30.0 * f > 10.0)
        self.assertAlmostEqual(f * 30.0, 10.0, delta=0.01)
        self.assertLessEqual(f * 30.0, 10.0)

    def test_a_free_move_goes_all_the_way(self):
        self.assertEqual(mc.last_free(lambda f: False), 1.0)

    def test_boxes(self):
        self.assertTrue(mc.boxes_meet((0, 0, 0, 1, 1, 1), (1, 0, 0, 2, 1, 1)))
        self.assertFalse(mc.boxes_meet((0, 0, 0, 1, 1, 1), (1.5, 0, 0, 2, 1, 1)))
        self.assertTrue(mc.boxes_meet((0, 0, 0, 1, 1, 1), (1.5, 0, 0, 2, 1, 1), tol=0.6))


class StudyTests(unittest.TestCase):
    def test_values_between_key_points(self):
        keys = [(0, 0.0), (100, 720.0)]
        self.assertAlmostEqual(mc.study_value(keys, 50), 360.0)
        self.assertAlmostEqual(mc.study_value(keys, 25), 180.0)
        self.assertAlmostEqual(mc.study_value([(20, 45.0)], 0), 45.0)
        self.assertAlmostEqual(mc.study_value([(0, 0.0), (20, 45.0)], 80), 45.0)
        self.assertIsNone(mc.study_value([], 10))

    def test_play_modes(self):
        rate = mc.STEPS_PER_SECOND
        self.assertEqual(mc.study_step(200 / rate, 100, 1.0, "once"), (100.0, True))
        step, done = mc.study_step(150 / rate, 100, 1.0, "loop")
        self.assertAlmostEqual(step, 50.0)
        self.assertFalse(done)
        step, _ = mc.study_step(150 / rate, 100, 1.0, "pingpong")
        self.assertAlmostEqual(step, 50.0)
        step, _ = mc.study_step(130 / rate, 100, 1.0, "pingpong")
        self.assertAlmostEqual(step, 70.0)
        step, _ = mc.study_step(10 / rate, 100, 2.0, "once")
        self.assertAlmostEqual(step, 20.0)

    def test_key_editing(self):
        keys = mc.set_key([(0, 0.0)], 50, 90.0)
        keys = mc.set_key(keys, 50, 45.0)
        self.assertEqual(keys, [(0.0, 0.0), (50.0, 45.0)])
        self.assertEqual(mc.drop_key(keys, 50), [(0.0, 0.0)])


class ModeTests(unittest.TestCase):
    def test_between_two_parallel_faces(self):
        point, normal = core.midplane((0, 0, 0), (0, 0, -1), (0, 0, 10), (0, 0, 1))
        self.assertTrue(close(normal, (0, 0, -1)))
        self.assertAlmostEqual(point[2], 5.0)
        # facing each other (inner walls of a bracket 4 apart)
        point, normal = core.midplane((2, 0, 0), (1, 0, 0), (6, 3, 1), (-1, 0, 0))
        self.assertAlmostEqual(point[0], 4.0)
        self.assertTrue(close(normal, (1, 0, 0)))

    def test_between_two_faces_at_an_angle(self):
        # a V: faces x = 0 (normal +x... centre at (0, 0, 5)) and y = 0 (centre (0, 0, 5)
        # shifted) meeting along the Z axis; the bisector is the plane x = y
        point, normal = core.midplane(
            (0, 5, 0), (1, 0, 0), (5, 0, 0), (0, 1, 0), c1=(0, 5, 0), c2=(5, 0, 0)
        )
        self.assertAlmostEqual(abs(normal[0]), abs(normal[1]), places=9)
        self.assertAlmostEqual(normal[2], 0.0)
        self.assertLess(normal[0] * normal[1], 0)  # x - y = 0 separates (0, 5) and (5, 0)
        self.assertGreater(normal[0], 0)  # follows face 1's normal

    def test_two_faces_in_one_plane_are_refused(self):
        with self.assertRaises(core.JointError):
            core.midplane((0, 0, 0), (0, 0, 1), (5, 5, 0), (0, 0, 1))

    def test_two_edge_intersection(self):
        point, gap = core.line_intersection((5, 0, 0), (1, 0, 0), (0, 7, 0), (0, 1, 0))
        self.assertTrue(close(point, (0, 0, 0)))
        self.assertEqual(gap, 0.0)
        point, gap = core.line_intersection((5, 0, 0), (1, 0, 0), (0, 7, 2), (0, 1, 0))
        self.assertTrue(close(point, (0, 0, 1)))
        self.assertAlmostEqual(gap, 2.0)
        with self.assertRaises(core.JointError):
            core.line_intersection((0, 0, 0), (1, 0, 0), (0, 1, 0), (2, 0, 0))

    def test_project_to_plane(self):
        self.assertTrue(close(core.project_to_plane((3, 4, 9), (0, 0, 5), (0, 0, 2)), (3, 4, 5)))


if __name__ == "__main__":
    unittest.main()
