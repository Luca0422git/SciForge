# SPDX-License-Identifier: LGPL-2.1-or-later
"""sciforge/emboss_core.py: Fusion's Emboss rules (a negative depth swaps Emboss and
Deboss), the Alignment, and the unrolling of cylinders and cones (a profile wrapped onto
them keeps its lengths). Runs without FreeCAD."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import emboss_core as core  # noqa: E402


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def cone_point(radius, semi, u, v):
    """OpenCASCADE's cone (axis Z, reference circle `radius` at z = 0) at (u, v)."""
    r = radius + v * math.sin(semi)
    return (r * math.cos(u), r * math.sin(u), v * math.cos(semi))


class EffectTests(unittest.TestCase):
    def test_negative_depth_swaps_the_effect(self):
        self.assertEqual(core.effect_of(2.0, "emboss"), (2.0, "emboss"))
        self.assertEqual(core.effect_of(-2.0, "emboss"), (2.0, "deboss"))
        self.assertEqual(core.effect_of(-0.6, "deboss"), (0.6, "emboss"))
        with self.assertRaises(core.EmbossError):
            core.effect_of(1.0, "sideways")

    def test_depth_limits(self):
        core.check_depth(0.6)
        with self.assertRaises(core.EmbossError):
            core.check_depth(0.0)
        with self.assertRaises(core.EmbossError):
            core.check_depth(1e6)

    def test_signed_depth(self):
        self.assertEqual(core.signed(1.5, "emboss"), 1.5)
        self.assertEqual(core.signed(1.5, "deboss"), -1.5)

    def test_defaults(self):
        opts = core.default_options()
        self.assertEqual(opts["effect"], "emboss")
        self.assertTrue(opts["tangent_chain"])
        self.assertEqual((opts["h"], opts["v"], opts["angle"]), (0.0, 0.0, 0.0))

    def test_kinds(self):
        self.assertEqual(core.kind_of("Part::GeomPlane"), "plane")
        self.assertEqual(core.kind_of("Part::GeomCylinder"), "cylinder")
        self.assertEqual(core.kind_of("Part::GeomCone"), "cone")
        self.assertEqual(core.kind_of("Part::GeomSphere"), "other")


class AlignmentTests(unittest.TestCase):
    def test_turn_then_move(self):
        x, y = core.align(1.0, 0.0, h=2.0, v=3.0, angle_deg=90.0)
        self.assertTrue(close(x, 2.0) and close(y, 4.0))

    def test_no_alignment(self):
        self.assertEqual(core.align(1.5, -2.0), (1.5, -2.0))

    def test_axes_onto_the_tangent_plane(self):
        # profile x along -a, y along +b (a turned sketch)
        self.assertEqual(core.to_tangent(2.0, 3.0, -1.0, 0.0, 0.0, 1.0), (-2.0, 3.0))


class CylinderTests(unittest.TestCase):
    def test_arc_length_is_kept(self):
        u, v = core.cylinder_uv(math.pi * 10.0, 4.0, 20.0, 0.25, 7.0)
        self.assertTrue(close(u, 0.25 + math.pi / 2.0))
        self.assertTrue(close(v, 11.0))

    def test_goes_round_the_seam(self):
        u, _v = core.cylinder_uv(-30.0, 0.0, 10.0, 0.1, 0.0)
        self.assertTrue(close(u, 0.1 - 3.0))

    def test_fits_around(self):
        self.assertTrue(core.fits_around(100.0, 20.0))
        self.assertFalse(core.fits_around(130.0, 20.0))

    def test_deboss_stops_before_the_axis(self):
        core.check_deboss_depth(2.0, "cylinder", 10.0)
        with self.assertRaises(core.EmbossError):
            core.check_deboss_depth(10.0, "cylinder", 10.0)
        core.check_deboss_depth(50.0, "plane", None)


class ConeTests(unittest.TestCase):
    def test_the_anchor_stays(self):
        u, v = core.cone_uv(0.0, 0.0, 20.0, math.radians(-10.0), 1.0, 5.0)
        self.assertTrue(close(u, 1.0) and close(v, 5.0))

    def test_unrolling_keeps_lengths(self):
        """A step along the side keeps its length; a step around keeps its arc length
        (both measured on the cone itself)."""
        semi = math.radians(-12.0)
        radius, u0, v0 = 20.0, 0.3, 4.0
        # along the side: b = 5 mm
        u, v = core.cone_uv(0.0, 5.0, radius, semi, u0, v0)
        p0 = cone_point(radius, semi, u0, v0)
        p1 = cone_point(radius, semi, u, v)
        self.assertTrue(close(math.dist(p0, p1), 5.0, 1e-9))
        # around: a small step a has arc length a on the circle through the anchor
        a = 0.01
        u, v = core.cone_uv(a, 0.0, radius, semi, u0, v0)
        r = radius + v0 * math.sin(semi)
        self.assertTrue(close(r * (u - u0), a, 1e-7))
        self.assertTrue(abs(v - v0) < 1e-5)

    def test_the_tip_is_refused(self):
        semi = math.radians(-30.0)
        # the apex of this cone is 2 * radius up the side (v = radius / sin(30))
        with self.assertRaises(core.EmbossError):
            core.cone_uv(0.0, 0.0, 10.0, semi, 0.0, 20.0)

    def test_samples(self):
        self.assertEqual(core.samples(0.1), 8)
        self.assertEqual(core.samples(1000.0), 64)
        self.assertEqual(core.samples(10.0), 21)


if __name__ == "__main__":
    unittest.main()
