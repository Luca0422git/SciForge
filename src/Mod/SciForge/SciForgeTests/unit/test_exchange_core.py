# SPDX-License-Identifier: LGPL-2.1-or-later
"""Import and export with structure (sciforge/exchange_core.py): which file is what, how a
STEP tree becomes components and bodies, how a design is written so it reads back the same.
Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import exchange_core as core  # noqa: E402

N = core.node


def robot():
    """Robot: Base (a part), Drive (an assembly: Axle, Wheel, Wheel again)."""
    wheel = N("Wheel", core.PART, key="W", pieces=["w"])
    return N(
        "Robot",
        core.ASSEMBLY,
        key="R",
        children=[
            N("Base", core.PART, key="B", pieces=["b"]),
            N(
                "Drive",
                core.ASSEMBLY,
                key="D",
                children=[
                    N("Axle", core.PART, key="A", pieces=["a"]),
                    wheel,
                    N("Wheel", core.PART, key="W", link="W", pieces=["w"]),
                ],
            ),
        ],
    )


class FileKinds(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(core.file_kind("/a/Robot.STEP"), "step")
        self.assertEqual(core.file_kind("C:\\x\\part.stp"), "step")
        self.assertEqual(core.file_kind("a.igs"), "iges")
        self.assertEqual(core.file_kind("a.IGES"), "iges")
        self.assertEqual(core.file_kind("Cart.FCStd"), "design")

    def test_sat_is_refused_with_the_reason(self):
        with self.assertRaises(core.ExchangeError) as ctx:
            core.file_kind("bracket.sat")
        self.assertIn("STEP", str(ctx.exception))
        self.assertIn("kernel", str(ctx.exception))

    def test_unknown_files_say_what_is_taken(self):
        with self.assertRaises(core.ExchangeError) as ctx:
            core.file_kind("notes.txt")
        self.assertIn(".txt", str(ctx.exception))
        self.assertIn("STEP", str(ctx.exception))

    def test_base_name(self):
        self.assertEqual(core.base_name("/nas/parts/Robot arm.step"), "Robot arm")
        self.assertEqual(core.base_name("C:\\parts\\M3.stp"), "M3")
        self.assertEqual(core.base_name(""), "Imported")


class Structure(unittest.TestCase):
    def test_open_makes_the_top_product_the_design(self):
        level = core.plan([robot()], core.OPEN, "robot")
        self.assertIsNone(level["component"])
        self.assertEqual([c["name"] for c in level["children"]], ["Base", "Drive"])
        self.assertEqual(level["pieces"], [])

    def test_insert_makes_one_component_named_after_the_file(self):
        level = core.plan([robot()], core.INSERT, "robot")
        self.assertEqual(level["component"], "robot")
        self.assertEqual([c["name"] for c in level["children"]], ["Base", "Drive"])

    def test_a_single_part_is_bodies_of_the_design(self):
        part = N("Bracket", core.PART, key="P", pieces=["s1"])
        level = core.plan([part], core.OPEN, "bracket")
        self.assertEqual(level["pieces"], ["s1"])
        self.assertEqual(level["children"], [])
        self.assertEqual(level["part_name"], "Bracket")

    def test_several_free_parts_become_components(self):
        tops = [N("Plate", core.PART, key="1", pieces=["p"]), N("Peg", core.PART, key="2")]
        level = core.plan(tops, core.OPEN, "two_parts")
        self.assertEqual([c["name"] for c in level["children"]], ["Plate", "Peg"])
        self.assertIsNone(level["part_name"])

    def test_a_part_named_like_its_assembly_is_folded_into_it(self):
        asm = N(
            "Base",
            core.ASSEMBLY,
            key="A",
            children=[N("Base", core.PART, key="P", pieces=["s1", "s2"])],
        )
        out = core.normalize(asm)
        self.assertEqual(out["pieces"], ["s1", "s2"])
        self.assertEqual(out["children"], [])
        self.assertEqual(out["folded"], "P")

    def test_other_parts_are_not_folded(self):
        asm = N("Base", core.ASSEMBLY, children=[N("Screw", core.PART, pieces=["s"])])
        out = core.normalize(asm)
        self.assertEqual(out["pieces"], [])
        self.assertEqual(len(out["children"]), 1)

    def test_a_repeated_occurrence_is_not_folded(self):
        asm = N("Wheel", core.ASSEMBLY, children=[N("Wheel", core.PART, link="W", pieces=["w"])])
        self.assertEqual(len(core.normalize(asm)["children"]), 1)

    def test_counts(self):
        self.assertEqual(core.count_nodes([robot()]), (5, 1, 3))
        self.assertEqual(core.occurrences([robot()])["W"], 2)
        self.assertEqual(
            core.describe(4, 1, 3, "robot.step"), "robot.step: 4 components, 1 copy, 3 bodies"
        )

    def test_body_names(self):
        self.assertEqual(core.body_labels(2), ["Body1", "Body2"])
        self.assertEqual(core.body_labels(1, at_root=True, part_name="Bracket"), ["Bracket"])
        self.assertEqual(core.body_labels(2, at_root=True, part_name="Bracket"), ["Body1", "Body2"])
        self.assertEqual(core.body_labels(0), [])


class Export(unittest.TestCase):
    def test_types_in_order(self):
        labels = [t[0] for t in core.EXPORT_TYPES]
        self.assertEqual(labels[:2], ["STEP", "IGES"])
        self.assertIn("DXF", labels)
        self.assertIn("DWG", labels)
        self.assertEqual(core.export_kind("STL (Binary)"), "stl")
        self.assertEqual(core.export_extension("IGES"), ".igs")
        with self.assertRaises(core.ExchangeError):
            core.export_kind("F3D")

    def test_mirror_plan(self):
        units = [
            {"id": "Base", "bodies": 1, "children": []},
            {
                "id": "Drive",
                "bodies": 1,
                "children": [
                    {"id": "Wheel", "bodies": 1, "children": []},
                    {"id": "Wheel2", "bodies": 1, "children": [], "instance_of": "Wheel"},
                    {"id": "Empty", "bodies": 0, "children": []},
                ],
            },
            {"id": "Lonely", "bodies": 1, "children": [], "instance_of": "Gone"},
        ]
        plans = core.mirror_plan(units)
        self.assertEqual([p["as"] for p in plans], ["part", "assembly", "part"])
        drive = plans[1]
        self.assertTrue(drive["bodies_part"])
        self.assertEqual([c["as"] for c in drive["children"]], ["part", "link"])
        # a copy whose original is not written is written as a part of its own

    def test_dxf_name(self):
        self.assertEqual(core.dxf_name("Sketch1"), "Sketch1.dxf")
        self.assertEqual(core.dxf_name("a/b:c"), "a_b_c.dxf")
        self.assertEqual(core.dxf_name(""), "sketch.dxf")

    def test_dwg_says_what_to_install(self):
        self.assertIn("LibreDWG", core.DWG_NONE)
        self.assertIn("ODA", core.DWG_NONE)


if __name__ == "__main__":
    unittest.main()
