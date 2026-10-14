# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drawings without FreeCAD: sheets, scales, the title block template, projected and
section view maths, dimension inference, the parts list and the DXF writer."""
import math
import os
import sys
import unittest
import xml.dom.minidom

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import drawing_core as core  # noqa: E402


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def vclose(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class SheetTests(unittest.TestCase):
    def test_sizes_follow_the_standard(self):
        self.assertEqual(core.sheet_names("ISO"), ["A4", "A3", "A2", "A1", "A0"])
        self.assertEqual(core.sheet_names("ASME"), ["A", "B", "C", "D", "E"])
        self.assertEqual(core.sheet_size("ISO", "A3"), (420.0, 297.0))
        self.assertEqual(core.sheet_size("ASME", "B"), (431.8, 279.4))
        # an unknown size falls back to the standard's default sheet
        self.assertEqual(core.sheet_size("ISO", "B"), (420.0, 297.0))

    def test_projection_angle(self):
        self.assertEqual(core.projection_of("ISO"), "First angle")
        self.assertEqual(core.projection_of("ASME"), "Third angle")
        self.assertEqual(core.default_standard("in"), "ASME")
        self.assertEqual(core.default_standard("mm"), "ISO")

    def test_drawing_area_is_above_the_title_block(self):
        x0, y0, x1, y1 = core.drawing_area("ISO", "A3")
        tx0, ty0, tx1, ty1 = core.title_block_rect("ISO", "A3")
        self.assertGreater(y0, ty1)
        self.assertEqual(tx1, 410.0)
        self.assertEqual(ty0, 10.0)
        self.assertEqual(tx1 - tx0, core.TITLE_W)
        self.assertLess(x1, 410.0)
        self.assertLess(y1, 287.0)
        self.assertGreater(x0, 20.0)


class ScaleTests(unittest.TestCase):
    def test_format_and_parse(self):
        self.assertEqual(core.format_scale(0.5), "1:2")
        self.assertEqual(core.format_scale(2.0), "2:1")
        self.assertEqual(core.format_scale(1.0), "1:1")
        self.assertEqual(core.format_scale(0.4), "1:2.5")
        self.assertEqual(core.parse_scale("1:2"), 0.5)
        self.assertEqual(core.parse_scale("2:1"), 2.0)
        self.assertEqual(core.parse_scale("1/4"), 0.25)
        self.assertEqual(core.parse_scale("0,5"), 0.5)
        self.assertIsNone(core.parse_scale("1:0"))
        self.assertIsNone(core.parse_scale("abc"))
        self.assertIsNone(core.parse_scale("-2"))

    def test_fit_scale_takes_the_largest_standard_scale_that_fits(self):
        self.assertEqual(core.fit_scale(100, 50, 300, 200), 2.0)
        self.assertEqual(core.fit_scale(100, 50, 99, 200), 0.5)
        self.assertEqual(core.fit_scale(1000, 50, 300, 200), 0.25)
        self.assertEqual(core.fit_scale(10, 10, 300, 200), 20.0)
        self.assertEqual(core.fit_scale(1e6, 1, 300, 200), 1.0 / 200)

    def test_choices_are_unique(self):
        choices = core.scale_choices()
        self.assertEqual(len(choices), len(set(choices)))
        self.assertIn("1:1", choices)


class TemplateTests(unittest.TestCase):
    def values(self):
        return core.title_values(
            design="Bracket",
            author="Luca",
            date="2026-10-14",
            scale="1:2",
            standard="ISO",
            sheet="A3",
            material="Steel",
        )

    def test_title_values(self):
        values = self.values()
        self.assertEqual(values["Title"], "Bracket")
        self.assertEqual(values["PartNumber"], "Bracket")
        self.assertEqual(values["Scale"], "1:2")
        self.assertEqual(values["Sheet"], "1 / 1")
        self.assertEqual(values["Size"], "A3")
        self.assertEqual(set(values), set(core.TITLE_KEYS))

    def test_svg_is_valid_and_has_every_editable_field(self):
        text = core.template_svg("ISO", "A3", self.values())
        doc = xml.dom.minidom.parseString(text.encode("utf-8"))
        svg = doc.documentElement
        self.assertEqual(svg.getAttribute("width"), "420mm")
        self.assertEqual(svg.getAttribute("height"), "297mm")
        fields = {}
        for node in doc.getElementsByTagName("text"):
            key = node.getAttribute("freecad:editable")
            if key:
                spans = node.getElementsByTagName("tspan")
                self.assertEqual(len(spans), 1, key)  # TechDraw replaces the tspan's text
                fields[key] = "".join(n.data for n in spans[0].childNodes)
        self.assertEqual(set(fields), set(core.TITLE_KEYS))
        self.assertEqual(fields["Title"], "Bracket")
        self.assertEqual(fields["Scale"], "1:2")

    def test_title_block_cells_tile_the_block(self):
        area = sum(c[4] * c[5] for c in core.TITLE_CELLS)
        area += core.PROJECTION_CELL[2] * core.PROJECTION_CELL[3]
        area += core.BRAND_CELL[2] * core.BRAND_CELL[3]
        self.assertTrue(close(area, core.TITLE_W * core.TITLE_H))

    def test_special_characters_are_escaped(self):
        text = core.template_svg("ASME", "A", {"Title": "A & B <1>"})
        xml.dom.minidom.parseString(text.encode("utf-8"))
        self.assertIn("A &amp; B &lt;1&gt;", text)

    def test_projection_symbol_sides(self):
        first = core.projection_symbol("First angle", 0.0, 0.0)
        third = core.projection_symbol("Third angle", 0.0, 0.0)
        circle_first = [p for p in first if p[0] == "circle"][0][1]
        circle_third = [p for p in third if p[0] == "circle"][0][1]
        self.assertGreater(circle_first, 0.0)  # first angle: circles on the right
        self.assertLess(circle_third, 0.0)

    def test_no_title_block_leaves_only_the_frame(self):
        prims = core.template_primitives("ISO", "A4", {}, title_block=False)
        self.assertFalse([p for p in prims if p[0] == "text" and p[5]])


class LabelTests(unittest.TestCase):
    def test_next_label_skips_used_and_confusing_letters(self):
        self.assertEqual(core.next_label([]), "A")
        self.assertEqual(core.next_label(["A", "B"]), "C")
        self.assertEqual(core.next_label(list("ABCDEFGH")), "J")  # no I
        self.assertEqual(core.next_label(core.LABEL_LETTERS), "AA")


class ProjectedViewTests(unittest.TestCase):
    def test_third_angle_directions(self):
        p = "Third angle"
        self.assertEqual(core.projected_kind(50, 0, p), "Right")
        self.assertEqual(core.projected_kind(0, 50, p), "Top")
        self.assertEqual(core.projected_kind(-50, 3, p), "Left")
        self.assertEqual(core.projected_kind(0, -50, p), "Bottom")
        self.assertEqual(core.projected_kind(40, 40, p), "FrontTopRight")
        self.assertEqual(core.projected_kind(-40, -40, p), "FrontBottomLeft")

    def test_first_angle_mirrors(self):
        p = "First angle"
        self.assertEqual(core.projected_kind(50, 0, p), "Left")
        self.assertEqual(core.projected_kind(0, 50, p), "Bottom")
        self.assertEqual(core.projected_kind(0, -50, p), "Top")
        self.assertEqual(core.projected_kind(40, 40, p), "FrontBottomLeft")

    def test_orthographic_views_stay_lined_up(self):
        self.assertEqual(core.projected_offset("Right", 60, 7), (60, 0.0))
        self.assertEqual(core.projected_offset("Top", 3, -50), (0.0, -50))
        self.assertEqual(core.projected_offset("FrontTopRight", 40, 30), (40, 30))

    def test_outside_the_parent(self):
        self.assertFalse(core.outside(10, 10, 30, 20))
        self.assertTrue(core.outside(40, 0, 30, 20))


class FrameTests(unittest.TestCase):
    def test_view_axes(self):
        x, y, d = core.view_axes((0, -1, 0), (1, 0, 0))
        self.assertTrue(vclose(x, (1, 0, 0)))
        self.assertTrue(vclose(y, (0, 0, 1)))  # front view: up is +Z
        self.assertTrue(vclose(d, (0, -1, 0)))

    def test_round_trip(self):
        axes = core.view_axes((0, 0, 1), (1, 0, 0))
        point = core.to_model(axes, (30, 20, 10), -10, 5)
        self.assertTrue(vclose(point, (20, 25, 10)))
        self.assertTrue(vclose(core.to_view(axes, (30, 20, 10), point), (-10, 5)))


class SectionTests(unittest.TestCase):
    FRONT = core.view_axes((0, -1, 0), (1, 0, 0))

    def test_vertical_cut_view_on_the_right_third_angle(self):
        line = core.section_line((0, -20), (0, 20), (50, 0), "Third angle")
        direction, xdir, normal = core.section_axes(self.FRONT, line)
        # like TechDraw's Right view: looking from +X, paper x = +Y
        self.assertTrue(vclose(direction, (1, 0, 0)))
        self.assertTrue(vclose(xdir, (0, 1, 0)))
        self.assertTrue(vclose(normal, direction))

    def test_vertical_cut_view_on_the_right_first_angle(self):
        line = core.section_line((0, -20), (0, 20), (50, 0), "First angle")
        direction, xdir, normal = core.section_axes(self.FRONT, line)
        # first angle: the view on the right is seen from the left (TechDraw's Left view)
        self.assertTrue(vclose(direction, (-1, 0, 0)))
        self.assertTrue(vclose(xdir, (0, -1, 0)))
        self.assertTrue(vclose(normal, direction))

    def test_horizontal_cut_view_above(self):
        line = core.section_line((-30, 0), (30, 0), (0, 40), "Third angle")
        direction, xdir, _normal = core.section_axes(self.FRONT, line)
        self.assertTrue(vclose(direction, (0, 0, 1)))  # the Top view
        self.assertTrue(vclose(xdir, (1, 0, 0)))

    def test_line_drawn_the_other_way_gives_the_same_view(self):
        a = core.section_axes(self.FRONT, core.section_line((0, 20), (0, -20), (50, 0), "Third angle"))
        b = core.section_axes(self.FRONT, core.section_line((0, -20), (0, 20), (50, 0), "Third angle"))
        self.assertTrue(vclose(a[0], b[0]))

    def test_slanted_line_is_a_right_handed_frame(self):
        line = core.section_line((0, 0), (10, 10), (10, -10), "Third angle")
        direction, xdir, normal = core.section_axes(self.FRONT, line)
        self.assertTrue(close(core.v_dot(direction, xdir), 0.0))
        self.assertTrue(close(math.sqrt(core.v_dot(direction, direction)), 1.0))
        self.assertTrue(vclose(normal, direction))

    def test_no_length(self):
        self.assertIsNone(core.section_line((1, 1), (1, 1), (5, 5), "Third angle"))

    def test_offset_moves_along_the_side_only(self):
        line = core.section_line((0, -20), (0, 20), (50, 0), "Third angle")
        self.assertTrue(vclose(core.section_offset(line, 60, 13) + (0,), (60, 0, 0)))


class DimensionTests(unittest.TestCase):
    def line(self, p1, p2):
        return {"kind": "line", "p1": p1, "p2": p2}

    def test_one_line(self):
        self.assertEqual(core.infer_dimension([self.line((0, 0), (40, 0))])["type"], "DistanceX")
        self.assertEqual(core.infer_dimension([self.line((0, 0), (0, 20))])["type"], "DistanceY")
        slanted = [self.line((0, 0), (30, 40))]
        self.assertEqual(core.infer_dimension(slanted)["type"], "Distance")
        self.assertEqual(core.infer_dimension(slanted, (15, 60))["type"], "DistanceX")
        self.assertEqual(core.infer_dimension(slanted, (50, 20))["type"], "DistanceY")

    def test_circles_and_arcs(self):
        circle = {"kind": "circle", "center": (0, 0), "radius": 6}
        arc = {"kind": "arc", "center": (0, 0), "radius": 5}
        self.assertEqual(core.infer_dimension([circle])["type"], "Diameter")
        self.assertEqual(core.infer_dimension([arc])["type"], "Radius")

    def test_two_lines(self):
        a = self.line((0, 0), (40, 0))
        b = self.line((0, 20), (40, 20))
        self.assertEqual(core.infer_dimension([a, b])["type"], "DistanceY")
        c = self.line((0, 0), (0, 20))
        d = self.line((40, 0), (40, 20))
        self.assertEqual(core.infer_dimension([c, d])["type"], "DistanceX")
        self.assertEqual(core.infer_dimension([a, c])["type"], "Angle")
        e = self.line((0, 0), (10, 10))
        self.assertEqual(core.infer_dimension([a, e])["type"], "Angle")

    def test_points(self):
        v1 = {"kind": "vertex", "point": (0, 0)}
        v2 = {"kind": "vertex", "point": (30, 10)}
        self.assertEqual(core.infer_dimension([v1]), {"need": "more"})
        self.assertEqual(core.infer_dimension([v1, v2])["type"], "Distance")
        self.assertEqual(core.infer_dimension([v1, v2], (15, 40))["type"], "DistanceX")
        self.assertIn("error", core.infer_dimension([v1, v1]))

    def test_circle_centres(self):
        c1 = {"kind": "circle", "center": (0, 0), "radius": 3}
        c2 = {"kind": "circle", "center": (40, 0), "radius": 3}
        result = core.infer_dimension([c1, c2])
        self.assertEqual(result["type"], "DistanceX")
        self.assertEqual(result["use_centers"], [0, 1])
        edge = self.line((-10, 20), (50, 20))
        result = core.infer_dimension([c1, edge])
        self.assertEqual(result["type"], "DistanceY")
        self.assertEqual(result["use_centers"], [0])

    def test_refusals(self):
        spline = {"kind": "curve"}
        self.assertIn("error", core.infer_dimension([spline]))
        three = [self.line((0, 0), (1, 0))] * 3
        self.assertIn("error", core.infer_dimension(three))

    def test_value_format(self):
        self.assertEqual(core.format_value(60.0, "mm"), "60")
        self.assertEqual(core.format_value(12.5, "mm"), "12.5")
        self.assertEqual(core.format_value(60.0, "in"), "2.362")
        self.assertEqual(core.dimension_format("mm", "ISO"), "%.2w")


class PartsListTests(unittest.TestCase):
    def test_rows_count_identical_parts(self):
        rows = core.parts_rows(
            [
                {"name": "Plate", "material": "Aluminum"},
                {"name": "Pin", "material": "Steel"},
                {"name": "Pin", "material": "Steel"},
            ]
        )
        self.assertEqual([(r["Item"], r["PartNumber"], r["Qty"]) for r in rows], [(1, "Plate", 1), (2, "Pin", 2)])

    def test_table_layout(self):
        rows = core.parts_rows([{"name": "Plate"}, {"name": "Pin"}])
        layout = core.table_layout(rows)
        self.assertEqual(layout["height"], 3 * core.ROW_H)
        self.assertEqual(layout["width"], sum(c[2] for c in core.PARTS_COLUMNS))
        header = [t for t in layout["texts"] if t[3] == "ITEM"][0]
        first = [t for t in layout["texts"] if t[3] == "Plate"][0]
        self.assertGreater(header[1], first[1])  # header on top
        flipped = core.table_layout(rows, header_at_bottom=True)
        header = [t for t in flipped["texts"] if t[3] == "ITEM"][0]
        first = [t for t in flipped["texts"] if t[3] == "Plate"][0]
        second = [t for t in flipped["texts"] if t[3] == "Pin"][0]
        self.assertLess(header[1], first[1])  # header at the bottom
        self.assertLess(first[1], second[1])  # item 1 just above it

    def test_table_svg_parses(self):
        svg = core.table_svg(core.table_layout(core.parts_rows([{"name": "A&B"}])))
        xml.dom.minidom.parseString(svg.encode("utf-8"))

    def test_balloon_spot_is_outside_the_view(self):
        x, y = core.balloon_spot((100, 100), (110, 100), 30, 20, 0)
        self.assertGreater(x, 130)


class DxfTests(unittest.TestCase):
    def test_round_trip(self):
        dxf = core.DxfWriter()
        dxf.layer("HIDDEN", 8, "HIDDEN")
        dxf.line(0, 0, 10, 0, "OUTLINE")
        dxf.circle(5, 5, 2, "OUTLINE")
        dxf.arc(0, 0, 3, 0, 90, "HIDDEN")
        dxf.text(1, 2, 3.5, "60", "DIMENSIONS", align="center")
        dxf.solid([(0, 0), (1, 0), (0, 1)], "DIMENSIONS")
        text = dxf.to_text()
        self.assertTrue(text.startswith("  0\nSECTION\n"))
        self.assertTrue(text.rstrip().endswith("EOF"))
        entities = core.read_dxf_entities(text)
        kinds = [e[0] for e in entities]
        self.assertEqual(kinds, ["LINE", "CIRCLE", "ARC", "TEXT", "SOLID"])
        self.assertEqual(entities[3][1][1], ["60"])
        self.assertEqual(entities[0][1][8], ["OUTLINE"])
        self.assertIn("HIDDEN", text)


if __name__ == "__main__":
    unittest.main()
