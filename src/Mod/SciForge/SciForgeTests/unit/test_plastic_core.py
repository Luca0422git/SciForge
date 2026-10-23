# SPDX-License-Identifier: LGPL-2.1-or-later
"""Unit tests (no FreeCAD) for the PLASTIC part 1: plastic rules (plastic_core), the Boss's
settings (plastic_boss_core) and the PLASTIC tab's wiring (ribbon_config)."""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import plastic_boss_core as boss  # noqa: E402
from sciforge import plastic_core as core  # noqa: E402
from sciforge import ribbon_config as cfg  # noqa: E402

# The research's library table (fusion-plastic.md 3.3): name -> (material, thickness, min,
# max, draft, min draft, clearance)
RESEARCH = {
    "Default (mm)": ("ABS", 2.0, 1.0, 4.0, 1.0, 0.5, 0.1),
    "ABS 2 mm": ("ABS", 2.0, 1.2, 3.5, 1.0, 0.5, 0.1),
    "ABS 1.5 mm": ("ABS", 1.5, 1.2, 3.5, 1.0, 0.5, 0.1),
    "PC 2 mm": ("Polycarbonate", 2.0, 1.0, 3.8, 1.0, 0.5, 0.1),
    "PC/ABS 2 mm": ("PC/ABS", 2.0, 1.0, 3.5, 1.0, 0.5, 0.1),
    "PP 1.5 mm": ("Polypropylene", 1.5, 0.8, 3.8, 1.5, 1.0, 0.15),
    "PA66 1.5 mm": ("Nylon 6/6", 1.5, 0.8, 3.0, 1.0, 0.5, 0.1),
    "POM 1.5 mm": ("Acetal", 1.5, 0.8, 3.0, 1.0, 0.5, 0.1),
    "HIPS 2 mm": ("Polystyrene (HI)", 2.0, 1.0, 3.8, 1.0, 0.5, 0.1),
    "HDPE 2 mm": ("Polyethylene HD", 2.0, 0.8, 5.0, 1.5, 1.0, 0.15),
    "PBT 1.8 mm": ("PBT", 1.8, 0.8, 3.0, 1.0, 0.5, 0.1),
    "PMMA 2.5 mm": ("Acrylic", 2.5, 0.8, 3.8, 1.0, 0.5, 0.1),
    "TPE 1.5 mm": ("TPE", 1.5, 0.6, 3.0, 2.0, 1.0, 0.1),
    "FDM PLA 2 mm": ("PLA", 2.0, 0.8, 6.0, 0.0, 0.0, 0.3),
    "FDM PETG 2 mm": ("PETG", 2.0, 0.8, 6.0, 0.0, 0.0, 0.3),
}


def rule(name="Default (mm)"):
    return core.evaluated(core.library_rule(name))


class LibraryTest(unittest.TestCase):
    def test_every_library_rule_validates(self):
        for r in core.LIBRARY:
            self.assertEqual(core.validate(r), [], r["name"])

    def test_library_matches_the_research_table(self):
        names = [r["name"] for r in core.LIBRARY]
        self.assertEqual(len(names), 16)
        self.assertEqual(len(set(names)), 16)
        for name, (mat, t, lo, hi, draft, min_draft, c) in RESEARCH.items():
            r = rule(name)
            self.assertEqual(r["material"], mat, name)
            self.assertAlmostEqual(r["thickness"], t, msg=name)
            self.assertAlmostEqual(r["minimum_thickness"], lo, msg=name)
            self.assertAlmostEqual(r["maximum_thickness"], hi, msg=name)
            self.assertAlmostEqual(r["draft_angle"], draft, msg=name)
            self.assertAlmostEqual(r["minimum_draft_angle"], min_draft, msg=name)
            self.assertAlmostEqual(r["clearance"], c, msg=name)
            # derived values: Thickness / 2, Thickness / 4, 25 %
            self.assertAlmostEqual(r["nominal_radius"], t / 2, msg=name)
            self.assertAlmostEqual(r["reveal_height"], t / 2, msg=name)
            self.assertAlmostEqual(r["knife_edge_threshold"], t / 4, msg=name)
            self.assertAlmostEqual(r["thickness_variation"], 25.0, msg=name)

    def test_inch_rule_in_millimetres(self):
        r = rule("Default (in)")
        self.assertAlmostEqual(r["thickness"], 0.08 * 25.4)
        self.assertAlmostEqual(r["minimum_thickness"], 0.04 * 25.4)
        self.assertAlmostEqual(r["maximum_thickness"], 0.16 * 25.4)
        self.assertAlmostEqual(r["nominal_radius"], 0.04 * 25.4)
        self.assertAlmostEqual(r["clearance"], 0.004 * 25.4)
        self.assertAlmostEqual(r["draft_angle"], 1.0)  # angles stay degrees

    def test_expressions_in_thickness(self):
        r = core.make_rule(
            "X", thickness="3", nominal_radius="Thickness / 2 + 1", maximum_thickness="5"
        )
        self.assertAlmostEqual(core.evaluated(r)["nominal_radius"], 2.5)

    def test_refusals(self):
        bad = core.make_rule("X", thickness="5")  # outside 1..4
        self.assertIn("within the thickness range", core.validate(bad)[0])
        bad = core.make_rule("X", minimum_thickness="5", maximum_thickness="4")
        self.assertIn("minimum is above its maximum", core.validate(bad)[0])
        bad = core.make_rule("X", draft_angle="50")
        self.assertIn("under 45", core.validate(bad)[0])
        bad = core.make_rule("X", thickness="0")
        self.assertIn("more than 0", core.validate(bad)[0])
        bad = core.make_rule("X", units="cm")
        self.assertIn("mm or in", core.validate(bad)[0])
        with self.assertRaises(ValueError):
            core.evaluated(core.make_rule("X", thickness="9"))

    def test_refusals_name_the_fields_as_the_dialog_does(self):
        # QA: the messages said "nominal_radius: ..." (the internal key)
        bad = core.make_rule("X", nominal_radius="abc")
        self.assertTrue(core.validate(bad)[0].startswith("Nominal Radius:"), core.validate(bad))
        bad = core.make_rule("X", clearance="-1")
        self.assertEqual(core.validate(bad), ["Clearance cannot be negative"])
        bad = core.make_rule("X", thickness="Thickness / 2")
        self.assertIn("cannot use Thickness", core.validate(bad)[0])

    def test_describe_lists_every_value_with_units(self):
        rows = dict(core.describe(core.library_rule("PC 2 mm")))
        self.assertEqual(rows["Thickness"], "2.0 mm")
        self.assertEqual(rows["Draft Angle"], "1.0 deg")
        self.assertEqual(rows["Nominal Radius"], "Thickness / 2")
        self.assertEqual(rows["Thickness Variation (%)"], "25 %")
        self.assertEqual(len(rows), len(core.FIELDS) - 1)

    def test_materials_exist_in_sciforges_library(self):
        with open(os.path.join(ROOT, "sciforge", "material.py")) as handle:
            text = handle.read()
        keys = set(re.findall(r'^\s+\("([a-z_0-9]+)", "', text, re.M))
        for name, key in core.MATERIAL_KEYS.items():
            self.assertIn(key, keys, name)
            self.assertIn(name, core.MATERIALS)


class BossSettingsTest(unittest.TestCase):
    def test_m3_defaults(self):
        o = boss.default_options(rule(), 3.0)
        s1, s2 = o["side1"], o["side2"]
        self.assertEqual((s1["hole"], s1["extent"], s1["step"]), ("counterbore", "through", "in"))
        self.assertEqual((s2["hole"], s2["extent"], s2["step"]), ("simple", "from_bottom", "out"))
        self.assertAlmostEqual(s1["hole_diameter"], 3.4)  # clearance d + 0.4
        self.assertAlmostEqual(s2["hole_diameter"], 2.4)  # pilot 0.8 d
        self.assertAlmostEqual(s1["diameter"], 10.0)
        # Side 1's recess takes Side 2's tip with the clearance all round (critic C8)
        self.assertAlmostEqual(s1["step_diameter"], s2["diameter"] + 2 * 0.1)
        self.assertAlmostEqual(s2["step_diameter"], s2["diameter"])
        self.assertAlmostEqual(s2["diameter"], 7.5)
        self.assertAlmostEqual(s1["major_diameter"], 6.5)
        # the spigot fits the recess with the rule's clearance all round
        self.assertAlmostEqual(s2["step_diameter"], s1["step_diameter"] - 2 * 0.1)
        self.assertAlmostEqual(s1["clearance"] + s2["clearance"], 0.1)
        self.assertAlmostEqual(s1["draft"], 1.0)
        self.assertAlmostEqual(s1["wall"], 1.2)  # 0.6 x 2 mm
        self.assertEqual(boss.check_options(o), o)

    def test_rule_links_follow_the_rule_until_typed_over(self):
        o = boss.default_options(rule(), 3.0)
        o["links"]["side2.draft"] = False
        o["side2"]["draft"] = 3.0
        pc = core.evaluated(
            core.make_rule("Y", thickness="3", draft_angle="2", maximum_thickness="4")
        )
        out = boss.apply_rule(o, pc)
        self.assertAlmostEqual(out["side1"]["draft"], 2.0)  # linked
        self.assertAlmostEqual(out["side2"]["draft"], 3.0)  # typed over
        self.assertAlmostEqual(out["side1"]["wall"], 1.8)  # 0.6 x 3
        self.assertAlmostEqual(out["side1"]["root_radius"], 1.5)  # nominal radius
        self.assertAlmostEqual(o["side1"]["draft"], 1.0)  # a copy: the input is kept

    def test_new_boss_shows_what_the_rule_link_builds(self):
        # QA: a rule whose nominal radius is more than half its wall: the new dialog's root
        # radius was clamped to T / 2 while the step was built with the rule's radius
        pc = core.evaluated(core.make_rule("R", thickness="2", nominal_radius="1.6"))
        o = boss.default_options(pc, 3.0)
        built = boss.apply_rule(o, pc)
        for side in ("side1", "side2"):
            for key in boss.RULE_LINKS:
                self.assertAlmostEqual(o[side][key], built[side][key], msg=key)
        self.assertAlmostEqual(o["side1"]["root_radius"], 1.6)

    def test_constant_thickness_diameter(self):
        s = dict(boss.side_defaults(2, rule()), shape="constant_thickness")
        self.assertAlmostEqual(boss.outer_diameter(s), 2.4 + 2 * 1.2)

    def refused(self, side, **change):
        o = boss.default_options(rule(), 3.0)
        o["side%d" % side].update(change)
        with self.assertRaises(boss.BossError) as ctx:
            boss.check_options(o)
        return str(ctx.exception)

    def test_major_draft(self):
        # Fusion's Major Draft Angle (the counterbore wall), added by the QA pass: 0 by
        # default, 0-30 degrees, and a boss saved before it existed reads as 0
        o = boss.default_options(rule(), 3.0)
        self.assertEqual(o["side1"]["major_draft"], 0.0)
        self.assertIn("0-30 degrees", self.refused(1, major_draft=35))
        old = boss.default_options(rule(), 3.0)
        del old["side1"]["major_draft"]
        self.assertEqual(boss.check_options(old)["side1"]["major_draft"], 0.0)

    def test_refusals(self):
        self.assertIn("smaller than the outer diameter", self.refused(1, hole_diameter=20))
        self.assertIn("larger than the hole", self.refused(1, major_diameter=3.0))
        self.assertIn("quantity of 1", self.refused(2, ribs=True, rib_count=0))
        self.assertIn("must reach past the boss", self.refused(2, ribs=True, rib_length=2))
        self.assertIn("0-30 degrees", self.refused(2, draft=40))
        self.assertIn("unknown shape", self.refused(1, shape="square"))
        self.assertIn("recess must be narrower", self.refused(1, step_diameter=12))
        self.assertIn("spigot must be wider", self.refused(2, step_diameter=2.0))
        self.assertIn("countersink angle", self.refused(1, hole="countersink", countersink_angle=5))
        self.assertIn("cannot be negative", self.refused(2, clearance=-1))

    def test_a_blank_side_needs_no_hole(self):
        o = boss.default_options(rule(), 3.0)
        o["side2"].update(shape="blank", hole_diameter=50, step="none")
        boss.check_options(o)

    def test_disabled_side_is_not_checked(self):
        o = boss.default_options(rule(), 3.0)
        o["side1"].update(enabled=False, hole_diameter=50)
        boss.check_options(o)

    def test_rib_angles(self):
        self.assertEqual(boss.rib_angles(4, 360, 0), [0, 90, 180, 270])
        self.assertEqual(boss.rib_angles(3, 90, 45), [45, 90, 135])
        self.assertEqual(boss.rib_angles(1, 120, 10), [10])
        self.assertEqual(boss.rib_angles(0, 360, 0), [])

    def test_summary(self):
        text = boss.summary(boss.default_options(rule(), 3.0))
        self.assertIn("side 1: dia 10.00, counterbore", text)
        self.assertIn("side 2: dia 7.50, simple", text)


class BossMoreTest(unittest.TestCase):
    def options(self):
        return boss.default_options(rule(), 3.0)

    def test_each_rib(self):
        o = self.options()
        s2 = o["side2"]
        s2.update(ribs=True, rib_count=4, rib_extents=["length", "suppressed"])
        boss.check_options(o)
        self.assertEqual(boss.rib_extents(s2), ["length", "suppressed", "length", "length"])
        s2["rib_extents"] = ["suppressed"] * 4
        with self.assertRaises(boss.BossError) as ctx:
            boss.check_options(o)
        self.assertIn("every rib is suppressed", str(ctx.exception))
        s2["rib_extents"] = ["sideways"]
        with self.assertRaises(boss.BossError):
            boss.check_options(o)

    def test_to_next_ribs_need_no_length(self):
        o = self.options()
        o["side2"].update(ribs=True, rib_extent="to_next", rib_length=1.0)
        boss.check_options(o)  # the length only counts for By Length ribs

    def test_fastener_options(self):
        o = self.options()
        self.assertEqual(o["fastener"], {"create": False, "head": "pan", "length": 0.0})
        o["fastener"] = {"create": True, "head": "hex_washer", "length": "12"}
        self.assertEqual(boss.check_options(o)["fastener"]["length"], 12.0)
        o["fastener"]["head"] = "torx"
        with self.assertRaises(boss.BossError):
            boss.check_options(o)
        o = self.options()
        o["fastener"] = {"create": True}
        o["side1"]["shape"] = "blank"
        with self.assertRaises(boss.BossError) as ctx:
            boss.check_options(o)
        self.assertIn("no screw to place", str(ctx.exception))

    def test_hole_radii_default_to_zero_for_old_options(self):
        o = self.options()
        del o["side1"]["hole_start_radius"]
        del o["side2"]["hole_end_radius"]
        boss.check_options(o)
        self.assertEqual(o["side1"]["hole_start_radius"], 0.0)
        o["side2"]["hole_end_radius"] = -1
        with self.assertRaises(boss.BossError):
            boss.check_options(o)


class RibbonTest(unittest.TestCase):
    def test_plastic_part_1_items_wired(self):
        want = {
            "Assign Plastic Rule": ("SciForge_AssignPlasticRule", "pl_assign"),
            "Manage Plastic Rules": ("SciForge_ManagePlasticRules", "pl_manage"),
            "Boss": ("SciForge_Boss", "pl_boss"),
            "Rest": ("SciForge_Rest", "pl_rest"),
            "Rule Fillet": ("SciForge_RuleFillet", "pl_rule_fillet"),
        }
        groups = (cfg.PLASTIC_SETUP, cfg.PLASTIC_CREATE, cfg.PLASTIC_MODIFY)
        for label, (command, icon) in want.items():
            found = None
            for grp in groups:
                found = found or cfg.find(grp, label)
            self.assertIsNotNone(found, label)
            self.assertEqual(found["command"], command, label)
            self.assertEqual(found["icon"], icon, label)
            path = os.path.join(ROOT, "sciforge", "icons", "ui", icon + ".svg")
            self.assertTrue(os.path.exists(path), path)

    def test_plastic_create_order(self):
        labels = [i["label"] for i in cfg.PLASTIC_CREATE["items"] if i is not None]
        self.assertLess(labels.index("Thread"), labels.index("Boss"))
        self.assertEqual(
            labels[labels.index("Boss") : labels.index("Rest") + 1],
            ["Boss", "Snap Fit", "Lip", "Rest"],
        )


if __name__ == "__main__":
    unittest.main()
