# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of Fusion's joints (sciforge/joints_core.py). Runs without FreeCAD."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import joints_core as core  # noqa: E402


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class RotationTests(unittest.TestCase):
    def test_axis_angle_turns_x_onto_y(self):
        r = core.rot_axis_angle(core.Z, 90)
        self.assertTrue(close(core.rot_apply(r, core.X), core.Y))

    def test_compose_then_inverse_is_identity(self):
        f = core.frame((3, -2, 5), core.rot_axis_angle((1, 1, 0), 37))
        back = core.compose(f, core.inverse(f))
        self.assertTrue(core.same_frame(back, core.frame()))

    def test_rot_from_z_is_right_handed_and_follows_the_hint(self):
        r = core.rot_from_z((0, 0, 1), x_hint=(0.3, 0.8, 0.5))
        x, y, z = (core.axis_of(r, i) for i in range(3))
        self.assertTrue(close(z, core.Z))
        self.assertTrue(close(core.cross(x, y), z))
        self.assertAlmostEqual(x[2], 0.0)
        self.assertAlmostEqual(math.atan2(x[1], x[0]), math.atan2(0.8, 0.3))

    def test_rot_from_z_without_hint_is_stable(self):
        a = core.rot_from_z((0, 1, 0))
        b = core.rot_from_z((0, 1, 0))
        self.assertEqual(a, b)
        self.assertTrue(close(core.axis_of(a, 2), core.Y))

    def test_motion_axis_choice(self):
        f = core.frame((1, 2, 3))
        fx = core.to_motion_axis(f, "x")
        self.assertTrue(close(core.axis_of(fx[1], 2), core.X))  # new Z is the old X
        fy = core.to_motion_axis(f, "y")
        self.assertTrue(close(core.axis_of(fy[1], 2), core.Y))
        self.assertEqual(core.to_motion_axis(f, "z"), f)
        for axis in ("x", "y", "z"):
            r = core.to_motion_axis(f, axis)[1]
            x, y, z = (core.axis_of(r, i) for i in range(3))
            self.assertTrue(close(core.cross(x, y), z))  # still right-handed
        with self.assertRaises(core.JointError):
            core.to_motion_axis(f, "w")


class AlignmentTests(unittest.TestCase):
    """Component 1 (a box, joint origin on its bottom face, Z down) onto component 2 (a
    plate, joint origin on its top face, Z up). The box's joint origin is stored turned
    over (flip_frame), so mating means making the two stored frames coincide."""

    def setUp(self):
        self.jcs2 = core.frame((20, 15, 10))  # plate top centre, Z up
        self.fusion1 = core.frame((110, 10, 0), core.rot_axis_angle(core.X, 180))  # box bottom
        self.jcs1 = core.compose(self.fusion1, core.stored_offset())  # as stored: Z up again

    def stored(self, **kw):
        return core.compose(self.fusion1, core.stored_offset(**kw))

    def test_mate_puts_the_faces_against_each_other(self):
        T = core.mate_transform(self.jcs1, self.jcs2)
        moved = core.compose(T, self.fusion1)  # the face's own frame after the move
        self.assertTrue(close(moved[0], (20, 15, 10)))
        self.assertTrue(close(core.axis_of(moved[1], 2), (0, 0, -1)))  # normals against
        self.assertTrue(close(core.axis_of(moved[1], 0), core.X))  # X kept
        self.assertTrue(close(core.rot_apply(T[1], core.Z), core.Z))  # the box is not turned

    def test_flip_turns_component_one_over(self):
        # Fusion's Flip: no mating, joint origin 1 is stored as is
        T = core.mate_transform(self.stored(mate=False), self.jcs2)
        moved = core.compose(T, self.fusion1)
        self.assertTrue(close(moved[0], (20, 15, 10)))
        self.assertTrue(close(core.axis_of(moved[1], 2), (0, 0, 1)))  # normals the same way

    def test_offsets_follow_joint_origin_two(self):
        jcs2 = core.frame((20, 15, 10), core.rot_axis_angle(core.Z, 90))  # its X is world Y
        T = core.mate_transform(self.stored(offset=(5, 0, 2)), jcs2)
        moved = core.compose(T, self.fusion1)
        self.assertTrue(close(moved[0], (20, 20, 12)))
        self.assertTrue(close(core.axis_of(moved[1], 2), (0, 0, -1)))  # still mated

    def test_angle_turns_about_z(self):
        T = core.mate_transform(self.stored(angle=90), self.jcs2)
        moved = core.compose(T, self.fusion1)
        self.assertTrue(close(core.axis_of(moved[1], 0), core.Y))
        self.assertTrue(close(moved[0], (20, 15, 10)))

    def test_own_frame_undoes_the_stored_offset(self):
        stored = self.stored(offset=(1, 2, 3), angle=30)
        own = core.own_frame(stored, offset=(1, 2, 3), angle=30)
        self.assertTrue(core.same_frame(own, self.fusion1))

    def test_fresh_joint_reads_zero_whatever_the_offsets(self):
        stored = self.stored(offset=(5, 0, 2), angle=40)
        T = core.mate_transform(stored, self.jcs2)
        moved = core.compose(T, stored)
        angle, slide = core.joint_value(moved, self.jcs2)
        self.assertAlmostEqual(angle, 0.0)
        self.assertAlmostEqual(slide, 0.0)

    def test_keep_heading_removes_the_spin_only(self):
        # a joint origin on component 1 whose X points elsewhere: a plain mate would spin
        # the component 90 degrees about the joint axis; Fusion keeps its heading
        spun = core.frame((110, 10, 0), core.rot_axis_angle(core.Z, 90))
        T = core.mate_transform(spun, self.jcs2)
        self.assertAlmostEqual(abs(core.twist_about(T[1], core.Z)), 90.0)
        kept = core.keep_heading(T, self.jcs2[0], core.axis_of(self.jcs2[1], 2))
        moved = core.compose(kept, spun)
        self.assertTrue(close(moved[0], (20, 15, 10)))  # still on the joint origin
        self.assertTrue(close(core.axis_of(moved[1], 2), (0, 0, 1)))  # still aligned
        self.assertAlmostEqual(core.twist_about(kept[1], core.Z), 0.0, places=9)
        # the component's own X did not turn
        self.assertTrue(close(core.rot_apply(kept[1], core.X), core.X))

    def test_quaternion_matches_axis_angle(self):
        r = core.rot_axis_angle((0, 0, 1), 90)
        w, x, y, z = core.quaternion(r)
        self.assertAlmostEqual(w, math.cos(math.radians(45)))
        self.assertAlmostEqual(z, math.sin(math.radians(45)))
        self.assertAlmostEqual(core.twist_about(r, (0, 0, 1)), 90.0)
        self.assertAlmostEqual(core.twist_about(r, (1, 0, 0)), 0.0)
        tilted = core.rot_mul(core.rot_axis_angle(core.Z, 40), core.rot_axis_angle(core.X, 30))
        self.assertAlmostEqual(core.twist_about(tilted, core.Z), 40.0, places=6)

    def test_the_value_counts_from_the_mated_pose(self):
        T = core.mate_transform(self.jcs1, self.jcs2)
        moved = core.compose(T, self.jcs1)
        turned = core.driven_frame(moved, self.jcs2, angle=30, slide=3)
        angle, slide = core.joint_value(turned, self.jcs2)
        self.assertAlmostEqual(angle, 30.0)
        self.assertAlmostEqual(slide, 3.0)


class DriveTests(unittest.TestCase):
    def setUp(self):
        self.jcs2 = core.frame((20, 15, 10), core.rot_axis_angle((0, 1, 0), 20))
        start = core.compose(
            core.frame((110, 10, 0), core.rot_axis_angle(core.X, 180)), core.stored_offset()
        )
        T = core.mate_transform(start, self.jcs2)
        self.jcs1 = core.compose(T, start)

    def test_drive_angle_then_read_it_back(self):
        new = core.driven_frame(self.jcs1, self.jcs2, angle=45)
        angle, slide = core.joint_value(new, self.jcs2)
        self.assertAlmostEqual(angle, 45.0)
        self.assertAlmostEqual(slide, 0.0)
        self.assertTrue(close(new[0], self.jcs1[0]))  # a turn about the axis keeps the origin

    def test_a_pin_turns_where_it_stands(self):
        slid = core.driven_frame(self.jcs1, self.jcs2, slide=6, slide_axis="x")
        turned = core.driven_frame(slid, self.jcs2, angle=30, slide_axis="x")
        self.assertTrue(close(turned[0], slid[0]))  # the pin's centre did not move
        angle, slide = core.joint_value(turned, self.jcs2, slide_axis="x")
        self.assertAlmostEqual(angle, 30.0)
        self.assertAlmostEqual(slide, 6.0)

    def test_drive_slide(self):
        new = core.driven_frame(self.jcs1, self.jcs2, slide=7)
        angle, slide = core.joint_value(new, self.jcs2)
        self.assertAlmostEqual(slide, 7.0)
        self.assertAlmostEqual(angle, 0.0)
        along = core.axis_of(self.jcs2[1], 2)
        self.assertTrue(close(new[0], core.vadd(self.jcs1[0], core.vscale(along, 7))))

    def test_pin_slot_slides_along_its_slot(self):
        new = core.driven_frame(self.jcs1, self.jcs2, slide=6, slide_axis="x")
        angle, slide = core.joint_value(new, self.jcs2, slide_axis="x")
        self.assertAlmostEqual(slide, 6.0)
        self.assertAlmostEqual(angle, 0.0)
        along = core.axis_of(self.jcs2[1], 0)
        self.assertTrue(close(new[0], core.vadd(self.jcs1[0], core.vscale(along, 6))))
        # the Z value stays 0: the pin stays in the plane
        self.assertAlmostEqual(core.joint_value(new, self.jcs2)[1], 0.0)

    def test_drive_transform_moves_the_origin_the_same_way(self):
        T = core.drive_transform(self.jcs1, self.jcs2, angle=-60, slide=2)
        moved = core.compose(T, self.jcs1)
        angle, slide = core.joint_value(moved, self.jcs2)
        self.assertAlmostEqual(angle, -60.0)
        self.assertAlmostEqual(slide, 2.0)

    def test_wobble_and_slide_keep_what_they_should(self):
        T = core.wobble_frame(self.jcs1, self.jcs2, pitch=15)
        moved = core.compose(T, self.jcs1)
        self.assertTrue(close(moved[0], self.jcs1[0]))  # a ball turns about its centre
        T = core.slide_frame(self.jcs1, self.jcs2, dx=4)
        moved = core.compose(T, self.jcs1)
        self.assertAlmostEqual(core.distance(moved[0], self.jcs1[0]), 4.0)


class LimitTests(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(core.clamp(5, 0, 3), 3.0)
        self.assertEqual(core.clamp(-5, 0, 3), 0.0)
        self.assertEqual(core.clamp(2, None, 3), 2.0)
        self.assertEqual(core.clamp(9, 10, 0), 9.0)  # swapped limits are sorted

    def test_rest_outside_the_range_is_refused(self):
        with self.assertRaises(core.JointError):
            core.normalize_limits({"min": 0, "max": 90, "rest": 100})
        limits = core.normalize_limits({"min": 90, "max": 0, "rest": 45})
        self.assertEqual((limits["min"], limits["max"], limits["rest"]), (0.0, 90.0, 45.0))

    def test_sweep_stays_inside_limits_and_returns_home(self):
        values = [core.sweep(t / 40.0, 10, low=0, high=30) for t in range(41)]
        self.assertAlmostEqual(values[0], 10.0)
        self.assertAlmostEqual(values[-1], 10.0)
        self.assertTrue(all(0 - 1e-9 <= v <= 30 + 1e-9 for v in values))
        self.assertAlmostEqual(max(values), 30.0, places=6)
        self.assertAlmostEqual(min(values), 0.0, places=6)

    def test_sweep_without_limits_swings_the_span(self):
        values = [core.sweep(t / 40.0, 0, span=25) for t in range(41)]
        self.assertAlmostEqual(max(values), 25.0, places=6)
        self.assertAlmostEqual(min(values), -25.0, places=6)
        capped = [core.sweep(t / 40.0, 0, high=5, span=25) for t in range(41)]
        self.assertAlmostEqual(max(capped), 5.0, places=6)


class SnapTests(unittest.TestCase):
    def test_nearest(self):
        points = [(0, 0, 0), (10, 0, 0), (5, 5, 0)]
        self.assertEqual(core.nearest(points, (9, 1, 0)), 1)
        self.assertIsNone(core.nearest([], (0, 0, 0)))

    def test_nearest_on_screen_within_radius(self):
        pixels = [(100, 100), (130, 100)]
        self.assertEqual(core.nearest_on_screen(pixels, (104, 103), 9), 0)
        self.assertIsNone(core.nearest_on_screen(pixels, (115, 100), 9))

    def test_dedupe_keeps_the_first_of_a_place(self):
        snaps = [
            {"kind": "vertex", "point": (0, 0, 0)},
            {"kind": "midpoint", "point": (5, 0, 0)},
            {"kind": "vertex", "point": (0, 0, 1e-9)},
        ]
        self.assertEqual([s["kind"] for s in core.dedupe(snaps)], ["vertex", "midpoint"])

    def test_label_numbers_count_up_and_skip_used(self):
        self.assertEqual(core.label_number([], "Revolute"), 1)
        self.assertEqual(core.label_number(["Revolute 1", "Rigid 1", "Revolute 3"], "Revolute"), 2)
        self.assertEqual(core.label_number(["Revolute 1", "Revolute 2"], "Revolute"), 3)


if __name__ == "__main__":
    unittest.main()
