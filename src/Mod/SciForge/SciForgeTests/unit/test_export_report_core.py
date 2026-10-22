# SPDX-License-Identifier: LGPL-2.1-or-later
"""What an export leaves out and what an import skipped (sciforge/export_report_core.py):
the rules per format, the sentences, combining several files, and the helpers that read
FreeCAD's DXF statistics, SVG, 3MF and OBJ files. Runs without FreeCAD (the counts that
come from a real design are checked by the golden models' export_report_expect steps)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import export_report_core as core  # noqa: E402

# a design like Luca's: a bracket with a fillet, a second body, a parameter, a plane
DESIGN = {
    "scope": "design",
    "solids": 2,
    "mesh_bodies": 0,
    "timeline": 6,
    "sketches": 2,
    "construction": 1,
    "parameters": 1,
    "joints": 0,
    "components": 0,
    "names_lost": 2,
    "looks": 1,
    "see_through": 0,
    "materials": 1,
    "curved": 4,
    "deviation": 0.0508,
    "unit": "Millimeter",
}


def keys(items):
    return [i["key"] for i in items]


class Formats(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(core.format_key("STEP"), "step")
        self.assertEqual(core.format_key("STL (Binary)"), "stl")
        self.assertEqual(core.format_key("STL (ASCII)"), "stl_ascii")
        self.assertEqual(core.format_key(".stp"), "step")
        self.assertEqual(core.format_key("igs"), "iges")
        self.assertEqual(core.format_key("3MF"), "3mf")
        self.assertEqual(core.format_key("drawing_dxf"), "drawing_dxf")
        self.assertEqual(core.format_key("PDF"), "drawing_pdf")
        self.assertEqual(core.format_name("STL (ASCII)"), "STL")

    def test_unknown(self):
        with self.assertRaises(core.ReportError):
            core.format_key("FBX")


class NothingLost(unittest.TestCase):
    def test_empty_design_says_nothing(self):
        for fmt in ("STEP", "IGES", "STL (Binary)", "3MF", "OBJ", "DXF", "drawing_pdf"):
            self.assertEqual(core.items(fmt, {}), [], fmt)
            self.assertEqual(core.summary("x", core.items(fmt, {})), "")

    def test_plain_box_in_step(self):
        """One body, a sketch and an extrude: STEP still loses the history only."""
        facts = {"solids": 1, "timeline": 2, "sketches": 1, "colours_written": True}
        self.assertEqual(keys(core.items("STEP", facts)), ["timeline", "sketches"])


class Step(unittest.TestCase):
    def test_headless_step_loses_colours(self):
        items = core.items("STEP", dict(DESIGN, colours_written=False))
        self.assertIn("looks", keys(items))
        text = [i["text"] for i in items if i["key"] == "looks"][0]
        self.assertIn("1 body", text)
        self.assertIn("window", text)

    def test_gui_step_keeps_colours_not_transparency(self):
        items = core.items("STEP", dict(DESIGN, colours_written=True, see_through=1))
        self.assertNotIn("looks", keys(items))
        self.assertIn("see_through", keys(items))

    def test_flat_step_loses_components(self):
        """A STEP written body by body (Selected bodies, Export Everything) has no
        component structure (review F3)."""
        self.assertIn("components", keys(core.items("STEP", dict(DESIGN, components=1, flat=True))))

    def test_iges_does_not_claim_the_file_has_no_names(self):
        """FreeCAD's IGES writer keeps the names (406 name property, entity labels); only
        SciForge's reader loses them (review F5)."""
        text = [i for i in core.items("IGES", DESIGN) if i["key"] == "names"][0]["text"]
        self.assertNotIn("unnamed", text)
        self.assertIn("when SciForge opens the file", text)
        brep = [i for i in core.items("BREP", DESIGN) if i["key"] == "names"][0]["text"]
        self.assertIn("unnamed", brep)

    def test_singular_wording(self):
        """One of a thing reads right (review F8)."""
        texts = " | ".join(
            i["text"]
            for i in core.items(
                "STEP",
                {"parameters": 1, "hidden_components": 1, "meshes": 1, "colours_written": True},
            )
        )
        self.assertIn("1 parameter (its value is built in)", texts)
        self.assertIn("1 component hidden, with its bodies", texts)
        self.assertIn("export it as STL", texts)
        texts = " | ".join(i["text"] for i in core.items("STL", {"solids": 1, "curved": 1}))
        self.assertIn("1 curved face becomes small flat triangles", texts)
        texts = " | ".join(i["text"] for i in core.items("STL", {"parameters": 2}))
        self.assertIn("2 parameters (their values are built in)", texts)
        loose = core.cad_items({"loose_faces": 1})[0]["text"]
        self.assertTrue(loose.startswith("1 loose face that is not part of a solid"), loose)
        self.assertIn("5 loose faces that are not", core.cad_items({"loose_faces": 5})[0]["text"])
        dims = core.items("drawing_dxf", {"drawing_dimensions": 1})[0]["text"]
        self.assertIn("it no longer measures the view", dims)

    def test_step_keeps_components_and_reports_names(self):
        items = core.items("STEP", dict(DESIGN, components=3))
        self.assertNotIn("components", keys(items))
        names = [i for i in items if i["key"] == "names"][0]
        self.assertEqual(names["count"], 2)
        self.assertIn("Body1", names["text"])

    def test_meshes_left_out(self):
        items = core.items("STEP", {"meshes": 2})
        self.assertEqual(keys(items), ["meshes"])
        self.assertIn("2 mesh bodies", items[0]["text"])
        self.assertIn("STL", items[0]["text"])
        # mesh formats take mesh bodies
        self.assertEqual(core.items("STL", {"meshes": 2}), [])

    def test_history_lines(self):
        items = core.items("STEP", DESIGN)
        texts = " | ".join(i["text"] for i in items)
        self.assertIn("the timeline (6 steps)", texts)
        self.assertIn("2 sketches", texts)
        self.assertIn("1 construction feature", texts)
        self.assertIn("1 parameter (its value is built in)", texts)
        self.assertIn("the physical material of 1 body", texts)
        self.assertNotIn("curves", texts)  # STEP keeps exact curves

    def test_joints_only_for_the_design(self):
        self.assertIn("joints", keys(core.items("STEP", {"joints": 2, "scope": "design"})))
        self.assertNotIn("joints", keys(core.items("STEP", {"joints": 2, "scope": "bodies"})))


class Iges(unittest.TestCase):
    def test_iges(self):
        items = core.items("IGES", dict(DESIGN, components=2, colours_written=True))
        k = keys(items)
        self.assertIn("components", k)
        self.assertIn("looks", k)  # IGES has no colours, window or not
        names = [i for i in items if i["key"] == "names"][0]
        self.assertEqual(names["count"], 2)
        self.assertIn("IGES", names["text"])

    def test_brep(self):
        """BREP (the AI export tool's brep): exact solids only, no names, colours or
        structure, like IGES; mesh bodies are left out like STEP / IGES."""
        self.assertEqual(core.format_key(".brp"), "brep")
        items = core.items("brep", dict(DESIGN, components=2, meshes=1, colours_written=True))
        k = keys(items)
        for key in ("timeline", "components", "looks", "names", "meshes"):
            self.assertIn(key, k)
        self.assertNotIn("curved", k)  # exact curves stay exact
        names = [i for i in items if i["key"] == "names"][0]
        self.assertIn("BREP", names["text"])


class Meshes(unittest.TestCase):
    def test_stl_merges_and_facets(self):
        items = core.items("STL (Binary)", DESIGN)
        k = keys(items)
        self.assertIn("merged", k)
        self.assertIn("curved", k)
        self.assertIn("looks", k)
        self.assertNotIn("names", k)
        curved = [i for i in items if i["key"] == "curved"][0]
        self.assertIn("4 curved faces", curved["text"])
        self.assertIn("0.0508 mm", curved["text"])

    def test_stl_one_file_per_body_is_not_merged(self):
        self.assertNotIn("merged", keys(core.items("STL", dict(DESIGN, per_body=True))))

    def test_one_body_is_not_merged(self):
        self.assertNotIn("merged", keys(core.items("STL", dict(DESIGN, solids=1))))

    def test_mesh_bodies_count_in_merge(self):
        items = core.items("STL", {"solids": 1, "mesh_bodies": 1})
        self.assertEqual(keys(items), ["merged"])
        self.assertIn("2 bodies become one mesh", items[0]["text"])

    def test_3mf_keeps_names_and_unit(self):
        k = keys(core.items("3MF", dict(DESIGN, unit="Inch")))
        self.assertNotIn("merged", k)
        self.assertNotIn("unit", k)
        self.assertIn("looks", k)

    def test_unit_for_stl_and_obj(self):
        for fmt in ("STL (Binary)", "OBJ"):
            items = core.items(fmt, {"unit": "Inch"})
            self.assertEqual(keys(items), ["unit"], fmt)
            self.assertIn("inches", items[0]["text"])
        self.assertEqual(core.items("STL", {"unit": "Millimeter"}), [])

    def test_open_mesh_bodies(self):
        items = core.items("3MF", {"mesh_bodies": 1, "open_meshes": 1})
        self.assertEqual(keys(items), ["open_meshes"])
        self.assertIn("1 mesh body not closed", items[0]["text"])
        self.assertEqual(core.items("STEP", {"open_meshes": 1}), [])
        self.assertEqual(keys(core.items("STL", {"open_meshes": 1}, "print")), ["open_meshes"])

    def test_components_flattened(self):
        self.assertIn("components", keys(core.items("3MF", {"components": 2})))

    def test_print_purpose(self):
        facts = dict(DESIGN, hidden=1, threads=1)
        k = keys(core.items("STL (Binary)", facts, purpose="print"))
        self.assertEqual(k, ["hidden", "merged", "looks", "threads"])

    def test_order(self):
        k = keys(core.items("STL", dict(DESIGN, hidden=1, surfaces=1)))
        self.assertEqual(k[:3], ["hidden", "surfaces", "timeline"])


class Flat(unittest.TestCase):
    def test_sketch_dxf(self):
        facts = {
            "dimensions": 2,
            "constraints": 3,
            "construction_curves": 1,
            "points": 1,
            "projected": 0,
            "off_plane": True,
        }
        items = core.items("DXF", facts)
        self.assertEqual(
            keys(items), ["dimensions", "constraints", "construction_curves", "points", "off_plane"]
        )
        self.assertEqual(items[0]["text"], "2 dimensions")
        self.assertEqual(core.items("DWG", facts), items)

    def test_face_dxf(self):
        self.assertEqual(core.items("DXF", {}), [])


class Drawings(unittest.TestCase):
    FACTS = {
        "sheets_left": 1,
        "hidden_views": 1,
        "drawing_dimensions": 3,
        "symbols": 2,
        "tables": 1,
        "curves": 5,
        "hatching": 1,
        "texts": 7,
    }

    def test_dxf(self):
        k = keys(core.items("drawing_dxf", self.FACTS))
        self.assertEqual(
            k,
            [
                "sheets_left",
                "hidden_views",
                "drawing_dimensions",
                "symbols",
                "tables",
                "curves",
                "hatching",
                "fonts",
            ],
        )

    def test_pdf(self):
        self.assertEqual(
            keys(core.items("drawing_pdf", self.FACTS)), ["sheets_left", "hidden_views"]
        )


class Combine(unittest.TestCase):
    def test_everything(self):
        step = core.items("STEP", dict(DESIGN, names_lost=0, colours_written=True))
        stl = core.items("STL", DESIGN)
        obj = core.items("OBJ", DESIGN)
        merged = core.combine([("STEP", step), ("STL", stl), ("OBJ", obj)])
        by_key = {i["key"]: i for i in merged}
        self.assertEqual(by_key["timeline"]["formats"], ["STEP", "STL", "OBJ"])
        self.assertNotIn("(", by_key["sketches"]["text"])  # every file loses them
        # the files first: never two sets of brackets at the end of a line
        self.assertTrue(by_key["looks"]["text"].startswith("STL, OBJ: the colours"))
        self.assertFalse(by_key["looks"]["text"].endswith(") (STL, OBJ)"))
        self.assertTrue(by_key["merged"]["text"].startswith("STL: "), by_key["merged"]["text"])

    def test_everything_mesh_body(self):
        """Export Everything with a mesh body: the STEP leaves it out, but the STL, 3MF and
        OBJ written with it hold it, so no advice to export it as STL, 3MF or OBJ (review
        F8)."""
        facts = {"solids": 2, "mesh_bodies": 1, "timeline": 2}
        step = core.items("STEP", dict(facts, meshes=1, solids=2, mesh_bodies=0))
        reports = [("STEP", step)] + [(f, core.items(f, facts)) for f in ("STL", "3MF", "OBJ")]
        merged = core.combine(reports)
        text = [i["text"] for i in merged if i["key"] == "meshes"][0]
        self.assertEqual(
            text, "1 mesh body not in the STEP (exact solids only): it is in the STL, 3MF, OBJ"
        )
        self.assertNotIn("export", text)

    def test_everything_flat_step_loses_components(self):
        """Export Everything writes its STEP body by body (export.export_step): flat, so the
        components are not kept in any of the four files, and the line names no format
        (review F3: it said "(STL, 3MF, OBJ)", as if the STEP had kept them)."""
        facts = {"solids": 3, "components": 1, "flat": True}
        reports = [(f, core.items(f, facts)) for f in ("STEP", "STL", "3MF", "OBJ")]
        text = [i["text"] for i in core.combine(reports) if i["key"] == "components"][0]
        self.assertEqual(text, "the components (1): every body is written on its own, flat")

    def test_summary(self):
        items = core.items("STL", {"timeline": 1, "sketches": 1})
        line = core.summary("box.stl", items)
        self.assertEqual(
            line,
            "Not in box.stl: the timeline (1 step): the file holds the finished shapes only; "
            "1 sketch.",
        )

    def test_notice_lines(self):
        items = [{"key": "k", "count": 1, "text": "t%d" % i} for i in range(10)]
        lines = core.notice_lines(items, limit=8)
        self.assertEqual(len(lines), 9)
        self.assertIn("2 more", lines[-1])


class Imports(unittest.TestCase):
    def test_mesh(self):
        items = core.mesh_items(
            {"open_edges": 4, "non_manifold": 0, "flipped": 2, "pieces": 1, "colours": True}
        )
        self.assertEqual(keys(items), ["open_edges", "flipped", "colours"])
        self.assertIn("4 open edges", items[0]["text"])

    def test_mesh_clean(self):
        self.assertEqual(core.mesh_items({"open_edges": 0, "pieces": 1, "flipped": 0}), [])

    def test_3mf_objects_and_unit(self):
        items = core.mesh_items(
            {"objects": 2, "pieces": 2, "file_unit": "Inch", "unit": "Millimeter"}
        )
        self.assertEqual(keys(items), ["objects", "unit"])
        self.assertIn("inches", items[1]["text"])
        self.assertEqual(core.mesh_items({"file_unit": "Inch", "unit": "Inch"}), [])

    def test_3mf_in_microns(self):
        """A 3MF in microns comes in 1000 times too big (Mesh.Mesh ignores the unit), and
        Unit Type has no micrometres: the card says so and how to scale it (review F11)."""
        facts = core.three_mf_facts(
            '<model unit="micron" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/'
            '2015/02"><resources><object id="1"><mesh/></object></resources></model>'
        )
        self.assertEqual(facts["file_unit"], "Micrometer")
        items = core.mesh_items(dict(facts, unit="Millimeter"))
        self.assertEqual(keys(items), ["unit"])
        self.assertIn("micrometres", items[0]["text"])
        self.assertIn("scale it by 0.001", items[0]["text"])
        cm = core.mesh_items({"file_unit": "Micrometer", "unit": "Centimeter"})[0]["text"]
        self.assertIn("scale it by 0.0001", cm)

    def test_cad(self):
        items = core.cad_items({"loose_faces": 5, "loose_curves": 1, "sewn": 0, "invalid": 1})
        self.assertEqual(keys(items), ["loose_faces", "loose_curves", "invalid"])
        self.assertIn("5 loose faces", items[0]["text"])
        self.assertIn("1 curve or point", items[1]["text"])

    def test_dxf_stats(self):
        """FreeCAD 1.1.4's importer statistics, as Import.readDXF returned them for a file
        with a line, a circle, a text, a point and a hatch."""
        stats = {
            "entityCounts": {"CIRCLE": 1, "HATCH": 1, "LINE": 1, "POINT": 1, "TEXT": 1},
            "unsupportedFeatures": {"Entity type 'HATCH'": [(68, "")]},
            "totalEntitiesCreated": 3,
        }
        facts = core.dxf_facts(stats)
        self.assertEqual(facts, {"unsupported": {"HATCH": 1}, "texts": 1, "points": 1})
        items = core.curve_items(dict(facts, skipped=0, flattened=2))
        self.assertEqual(keys(items), ["unsupported", "texts", "points", "flattened"])
        self.assertEqual(items[0]["text"], "1 hatch (FreeCAD cannot read it)")
        self.assertIn("1 text or dimension", items[1]["text"])

    def test_dxf_no_stats(self):
        self.assertEqual(core.dxf_facts(None), {"unsupported": {}, "texts": 0, "points": 0})

    def test_svg(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/>'
            '<text x="0" y="0">A</text><image href="a.png"/><text>B</text></svg>'
        )
        facts = core.svg_facts(svg)
        self.assertEqual(facts, {"texts": 2, "images": 1})
        items = core.curve_items(facts, "svg")
        self.assertEqual(items[0]["text"], "2 texts (only curves go into the sketch)")
        self.assertEqual(items[1]["text"], "1 picture")

    def test_svg_broken_xml_falls_back(self):
        self.assertEqual(core.svg_facts("<svg><text>x</text><image/>")["texts"], 1)

    def test_open_edges(self):
        # a tetrahedron is closed; without one triangle it has 3 open edges
        tet = [(0, 1, 2), (0, 3, 1), (1, 3, 2), (0, 2, 3)]
        self.assertEqual(core.open_edges(tet), (0, 0))
        self.assertEqual(core.open_edges(tet[1:]), (3, 0))
        # a fin: three triangles on one edge
        self.assertEqual(core.open_edges([(0, 1, 2), (0, 1, 3), (0, 1, 4)])[1], 1)

    def test_3mf(self):
        xml = (
            '<model unit="inch" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
            '<resources><basematerials id="1"><base name="r" displaycolor="#FF0000"/>'
            '</basematerials><object id="2" type="model"><mesh/></object>'
            '<object id="3" type="model"><mesh/></object></resources></model>'
        )
        self.assertEqual(
            core.three_mf_facts(xml), {"objects": 2, "colours": True, "file_unit": "Inch"}
        )
        plain = '<model xmlns="x"><resources><object id="1"><mesh/></object></resources></model>'
        self.assertEqual(
            core.three_mf_facts(plain),
            {"objects": 1, "colours": False, "file_unit": "Millimeter"},
        )

    def test_obj(self):
        self.assertTrue(core.obj_has_colours("mtllib a.mtl\nv 0 0 0\n"))
        self.assertTrue(core.obj_has_colours("v 0 0 0\nusemtl red\n"))
        self.assertFalse(core.obj_has_colours("# Created by FreeCAD\ng Body\nv 0 0 0\n"))


class Words(unittest.TestCase):
    def test_plural(self):
        self.assertEqual(core.plural(1, "sketch", "sketches"), "1 sketch")
        self.assertEqual(core.plural(0, "body", "bodies"), "0 bodies")
        self.assertEqual(core.plural(3, "step"), "3 steps")


if __name__ == "__main__":
    unittest.main()
