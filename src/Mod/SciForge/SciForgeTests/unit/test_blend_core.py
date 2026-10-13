# SPDX-License-Identifier: LGPL-2.1-or-later
"""The pure-logic parts of sciforge/blend.py (Fillet/Chamfer). Runs without FreeCAD:
the shape questions are answered by a small fake."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import blend  # noqa: E402


class FakeInfo:
    """A box-like part: Edge1..Edge4 sharp, Edge5 smooth (tangent), Face1 has Edge1/Edge2,
    Face2 has Edge3 plus the smooth Edge5, Face3 has no sharp edge."""

    FACES = {"Face1": (["Edge1", "Edge2"], False), "Face2": (["Edge3"], True), "Face3": ([], True)}

    def sharp(self, name):
        return name in ("Edge1", "Edge2", "Edge3", "Edge4")

    def face_edges(self, name):
        return self.FACES[name]

    def pickable(self, name):
        if name.startswith("Edge"):
            return self.sharp(name)
        return bool(self.FACES.get(name, ([], False))[0])


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.info = FakeInfo()

    def test_faces_expand_to_their_sharp_edges(self):
        self.assertEqual(blend.blended_edges(self.info, ["Face1"]), ["Edge1", "Edge2"])

    def test_no_duplicates_and_order_kept(self):
        edges = blend.blended_edges(self.info, ["Edge2", "Face1", "Edge4"])
        self.assertEqual(edges, ["Edge2", "Edge1", "Edge4"])

    def test_smooth_edges_are_never_blended(self):
        self.assertEqual(blend.blended_edges(self.info, ["Edge5"]), [])

    def test_clean_faces_are_stored_as_faces(self):
        # Fusion keeps the face, so edges a later edit adds to it are rounded too.
        self.assertEqual(blend.base_subs(self.info, ["Face1", "Edge4"]), ["Face1", "Edge4"])

    def test_faces_with_smooth_edges_are_stored_as_edges(self):
        # FreeCAD would warn about the smooth edge; store the sharp ones instead.
        self.assertEqual(blend.base_subs(self.info, ["Face2"]), ["Edge3"])
        self.assertEqual(blend.base_subs(self.info, ["Face3", "Edge5"]), [])


class OptionTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(blend.default_options("fillet"), {"radius": 1.0})
        chamfer = blend.default_options("chamfer")
        self.assertEqual(chamfer["chamfer_type"], "equal")
        self.assertFalse(chamfer["flip"])

    def test_chamfer_types_round_trip(self):
        for option, freecad, _label in blend.CHAMFER_TYPES:
            self.assertEqual(blend.chamfer_type_name(option), freecad)
            self.assertEqual(blend.chamfer_type_option(freecad), option)
        with self.assertRaises(blend.BlendError):
            blend.chamfer_type_name("miter")

    def test_kind_of(self):
        class Obj:
            TypeId = "PartDesign::Chamfer"

        self.assertEqual(blend.kind_of(Obj()), "chamfer")
        self.assertTrue(blend.is_blend(Obj()))
        Obj.TypeId = "PartDesign::Pad"
        self.assertIsNone(blend.kind_of(Obj()))


class MessageTests(unittest.TestCase):
    def test_kernel_text_becomes_plain_words(self):
        text = blend.friendly("BRep_API: command not done")
        self.assertIn("smaller", text)
        self.assertNotIn("BRep", text)
        self.assertIn("pieces", blend.friendly("Result has multiple solids: enable ..."))

    def test_too_big_names_the_size(self):
        text = blend.too_big("fillet", "radius", 12)
        self.assertIn("12 mm", text)
        self.assertIn("too big", text)

    def test_trial_needs_picks_and_a_positive_size(self):
        info = FakeInfo()
        with self.assertRaises(blend.BlendError) as ctx:
            blend.trial("fillet", info, [], {"radius": 1})
        self.assertIn("Select", str(ctx.exception))
        with self.assertRaises(blend.BlendError) as ctx:
            blend.trial("fillet", info, ["Edge1"], {"radius": 0})
        self.assertIn("more than 0", str(ctx.exception))
        with self.assertRaises(blend.BlendError):
            blend.trial(
                "chamfer", info, ["Edge1"], {"chamfer_type": "angle", "distance": 1, "angle": 180}
            )

    def test_arrow_goes_on_the_face_toward_the_viewer(self):
        class Vec:
            def __init__(self, x, y, z):
                self.v = (x, y, z)

            def dot(self, other):
                return sum(a * b for a, b in zip(self.v, other.v))

        top, back = Vec(0, 0, 1), Vec(0, 1, 0)
        iso = Vec(1, -1, 1)  # out of the screen in the default iso view
        self.assertEqual(blend.toward_face([top, back], iso), 0)
        self.assertEqual(blend.toward_face([back, top], iso), 1)
        self.assertEqual(blend.toward_face([top, back], Vec(0, 1, 0.1)), 1)

    def test_angle_chamfer_must_reach_the_other_face(self):
        """Distance and Angle: the bevel leaves the measured face at the angle and meets the
        other face only if angle + corner angle < 180 (below 90 degrees on a box edge)."""
        import math

        class Corner(FakeInfo):
            shape = None

            def __init__(self, degrees):
                self.gamma = math.radians(degrees)

            def frame(self, name):
                return {"gamma": self.gamma}

        options = {"chamfer_type": "angle", "distance": 1}
        with self.assertRaises(blend.BlendError) as ctx:
            blend.trial("chamfer", Corner(90), ["Edge1"], dict(options, angle=90))
        self.assertIn("below 90", str(ctx.exception))
        # 60 degrees fits a box edge; the feature itself is then built (nothing to check here)
        self.assertIsNone(blend.trial("chamfer", Corner(90), ["Edge1"], dict(options, angle=60)))
        # a sharper (60 degree) corner takes up to 120 degrees
        self.assertIsNone(blend.trial("chamfer", Corner(60), ["Edge1"], dict(options, angle=100)))
        with self.assertRaises(blend.BlendError):
            blend.trial("chamfer", Corner(60), ["Edge1"], dict(options, angle=125))


if __name__ == "__main__":
    unittest.main()
