# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY on surface bodies (surface-4): the pure rules in sciforge/surfmod_core.py,
the ribbon wiring and the icons (no FreeCAD)."""

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import ribbon_config as cfg  # noqa: E402
from sciforge import surfmod_core as core  # noqa: E402

ICONS = os.path.join(ROOT, "sciforge", "icons", "ui")


class Kinds(unittest.TestCase):
    def test_every_kind_has_a_type_a_title_and_an_icon(self):
        for kind in core.TYPES:
            self.assertIn(kind, core.TIMELINE_KINDS)
            self.assertIn(kind, core.TITLES)
            self.assertIn(kind, core.DEFAULTS)
            icon = core.TIMELINE_KINDS[kind][1]
            self.assertTrue(os.path.isfile(os.path.join(ICONS, icon + ".svg")), icon)

    def test_types_round_trip(self):
        for kind, sciforge_type in core.TYPES.items():
            self.assertEqual(core.kind_of_type(sciforge_type), kind)
        self.assertIsNone(core.kind_of_type("Fillet"))
        self.assertIsNone(core.kind_of_type(None))

    def test_timeline_titles_are_fusions(self):
        self.assertEqual(core.TIMELINE_KINDS["surface_fillet"][0], "Fillet")
        self.assertEqual(core.TIMELINE_KINDS["surface_delete_face"][0], "Delete Face")
        self.assertEqual(core.TIMELINE_KINDS["surface_press_pull"][0], "Press Pull")

    def test_timeline_shares_the_solid_kinds(self):
        from sciforge import timeline_core

        for sciforge_type, kind in core.TIMELINE_SHARED.items():
            self.assertIn(sciforge_type, core.KIND_BY_TYPE)
            if kind != "surface_merge":
                self.assertIn(kind, timeline_core.KINDS)
                title = timeline_core.KINDS[kind][0]
                self.assertEqual(title, core.TIMELINE_KINDS[core.KIND_BY_TYPE[sciforge_type]][0])
        for kind, icon in core.DIALOG_ICONS.items():
            self.assertTrue(os.path.isfile(os.path.join(ICONS, icon + ".svg")), icon)

    def test_defaults_do_not_leak(self):
        a = core.with_defaults("surface_fillet", {"radius": 4})
        self.assertEqual(a["radius"], 4)
        self.assertEqual(core.DEFAULTS["surface_fillet"]["radius"], 1.0)
        self.assertTrue(core.with_defaults("surface_chamfer")["tangent_chain"])


class Values(unittest.TestCase):
    def test_fillet_needs_a_radius(self):
        with self.assertRaises(core.NeedsPick):
            core.check_values("surface_fillet", core.with_defaults("surface_fillet", {"radius": 0}))
        core.check_values("surface_fillet", core.with_defaults("surface_fillet", {"radius": 2}))

    def test_chamfer_values(self):
        ok = core.with_defaults("surface_chamfer", {"chamfer_type": "two", "distance2": 3})
        core.check_values("surface_chamfer", ok)
        with self.assertRaises(core.NeedsPick):
            core.check_values("surface_chamfer", dict(ok, distance2=0))
        with self.assertRaises(core.SurfaceModifyError):
            core.check_values("surface_chamfer", dict(ok, chamfer_type="angle", angle=95))
        with self.assertRaises(core.SurfaceModifyError):
            core.check_values("surface_chamfer", dict(ok, chamfer_type="round"))

    def test_press_pull_needs_a_distance(self):
        with self.assertRaises(core.NeedsPick):
            core.check_values("surface_press_pull", {"distance": 0.0})
        core.check_values("surface_press_pull", {"distance": -2.0})

    def test_chamfer_distances(self):
        o = core.with_defaults("surface_chamfer", {"distance": 2})
        self.assertEqual(core.chamfer_distances(o), (2.0, 2.0))
        o.update(chamfer_type="two", distance2=4)
        self.assertEqual(core.chamfer_distances(o), (2.0, 4.0))
        o["flip"] = True
        self.assertEqual(core.chamfer_distances(o), (4.0, 2.0))
        o.update(chamfer_type="angle", angle=45.0, flip=False)
        d1, d2 = core.chamfer_distances(o)
        self.assertAlmostEqual(d2, 2.0 * math.tan(math.radians(45.0)))
        o.update(chamfer_type="equal", flip=True)
        self.assertEqual(core.chamfer_distances(o), (2.0, 2.0))  # flip means nothing here


class Rules(unittest.TestCase):
    def test_delete_heals_only_a_solid_on_the_solid_tab(self):
        self.assertTrue(core.delete_heals("solid", False))
        self.assertTrue(core.delete_heals(None, False))
        self.assertFalse(core.delete_heals("surface", False))
        self.assertFalse(core.delete_heals("solid", True))  # a surface body: nothing to heal
        self.assertFalse(core.delete_heals("surface", True))

    def test_press_pull_neighbour_action(self):
        # a wall running down from the floor's edge (against its normal), the floor pulled down
        self.assertEqual(core.press_pull_action(-1.0, -5.0), "trim")
        self.assertEqual(core.press_pull_action(-1.0, 5.0), "extend")
        self.assertEqual(core.press_pull_action(1.0, 5.0), "trim")
        self.assertEqual(core.press_pull_action(1.0, -5.0), "extend")
        with self.assertRaises(core.SurfaceModifyError):
            core.press_pull_action(0.0, 5.0)

    def test_merge_outcome(self):
        self.assertIn("one face", core.merge_outcome(2, 1))
        self.assertIn("3 faces", core.merge_outcome(4, 3))
        with self.assertRaises(core.NeedsPick):
            core.merge_outcome(1, 1)
        with self.assertRaises(core.SurfaceModifyError):
            core.merge_outcome(2, 2)

    def test_stitch_tolerance_default(self):
        self.assertEqual(core.STITCH_TOLERANCE, 1.0)


class Ribbon(unittest.TestCase):
    def test_merge_is_wired(self):
        entry = cfg.find(cfg.SURFACE_MODIFY, "Merge")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["command"], "SciForge_SurfaceMerge")
        self.assertEqual(entry["icon"], "surfmod_merge")

    def test_surface_modify_has_fusions_solid_tools(self):
        for label in ("Press Pull", "Fillet", "Chamfer", "Split Body", "Scale", "Move/Copy"):
            self.assertIsNotNone(cfg.find(cfg.SURFACE_MODIFY, label), label)
        for label in ("Align", "Delete", "Combine", "Physical Material", "Appearance"):
            self.assertIsNotNone(cfg.find(cfg.SURFACE_MODIFY, label), label)
        self.assertIsNotNone(cfg.find(cfg.SURFACE_CREATE, "Mirror"))
        self.assertIsNotNone(cfg.find(cfg.SURFACE_CREATE, "Rectangular Pattern"))


if __name__ == "__main__":
    unittest.main()
