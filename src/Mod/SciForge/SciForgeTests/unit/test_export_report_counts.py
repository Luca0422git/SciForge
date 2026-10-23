# SPDX-License-Identifier: LGPL-2.1-or-later
"""The counting helpers of sciforge/export_report.py that must stay cheap (review of the
export / import reports, 2026-10-22), with stand-in shapes so no FreeCAD is needed:

- piece_notes: the validity check of imported parts (OpenCASCADE's BRepCheck, about 5 ms a
  face) stops after MAX_VALIDITY_FACES faces per import. Before, every part of a STEP was
  checked, which made File > Open of a plate with 324 holes 3 times slower (F2).
- _curved_faces: reads each body's shape as it is; no copy moved into design coordinates
  (those copies were 60% of the cost of an STL export of a big design, F9)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import export_report  # noqa: E402


class FakeShape:
    def __init__(self, faces, valid=True):
        self.Faces = faces
        self.valid = valid
        self.checked = 0

    def isValid(self):
        self.checked += 1
        return self.valid


class ValidityBudget(unittest.TestCase):
    def test_small_parts_are_checked(self):
        notes = {}
        good, bad = FakeShape([0] * 6), FakeShape([0] * 6, valid=False)
        export_report.piece_notes([(good, [], False), (bad, [], True)], notes)
        self.assertEqual((good.checked, bad.checked), (1, 1))
        self.assertEqual(notes.get("invalid"), 1)
        self.assertEqual(notes.get("sewn"), 1)

    def test_big_parts_are_not_checked(self):
        notes = {}
        big = FakeShape([0] * (export_report.MAX_VALIDITY_FACES + 1), valid=False)
        export_report.piece_notes([(big, [], False)], notes)
        self.assertEqual(big.checked, 0)
        self.assertNotIn("invalid", notes)

    def test_budget_is_for_the_whole_import(self):
        """Many parts of one file: the faces add up across the calls (one per part)."""
        notes = {}
        size = export_report.MAX_VALIDITY_FACES // 3
        parts = [FakeShape([0] * size) for _ in range(10)]
        for part in parts:
            export_report.piece_notes([(part, [], False)], notes)
        self.assertEqual(sum(p.checked for p in parts), 3)
        self.assertLessEqual(notes["_faces_checked"], export_report.MAX_VALIDITY_FACES)


class Surface:
    def __init__(self, type_id):
        self.TypeId = type_id


class Face:
    def __init__(self, type_id, plane=None):
        self.Surface = Surface(type_id)
        self.plane = plane

    def findPlane(self):
        return self.plane


class Shape:
    def __init__(self, faces):
        self.Faces = faces

    def copy(self):
        raise AssertionError("the shape was copied just to count its curved faces")


class Body:
    def __init__(self, faces):
        self.Shape = Shape(faces)


class CurvedFaces(unittest.TestCase):
    def test_counts_without_copies(self):
        body = Body(
            [
                Face("Part::GeomPlane"),
                Face("Part::GeomCylinder"),
                Face("Part::GeomBSplineSurface", plane=object()),  # a flat spline face
                Face("Part::GeomSphere"),
            ]
        )
        self.assertEqual(export_report._curved_faces([body]), 2)


if __name__ == "__main__":
    unittest.main()
