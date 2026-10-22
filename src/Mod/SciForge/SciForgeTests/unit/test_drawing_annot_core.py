# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drawing annotations as shapes (drawing_annot_core): leaders, feature control frames,
datum identifiers, surface texture, ordinate dimensions, arc lengths, and their SVG and
DXF forms; plus one PDF from several (drawing_pdf)."""

import math
import os
import sys
import unittest
import xml.dom.minidom
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import drawing_annot_core as ac  # noqa: E402
from sciforge import drawing_core as core  # noqa: E402
from sciforge import drawing_pdf as pdf  # noqa: E402


def kinds(prims):
    return [p[0] for p in prims]


class LeaderTests(unittest.TestCase):
    def test_leader_to_the_right(self):
        prims = ac.leader((10.0, 10.0), (30.0, 20.0), ["NOTE", "TWO"])
        self.assertEqual(prims[0], ("line", 10.0, 10.0, 30.0, 20.0, ac.LINE))
        self.assertEqual(prims[1][1:5], (30.0, 20.0, 33.0, 20.0))  # the landing
        arrow = [p for p in prims if p[0] == "poly"][0]
        self.assertEqual(arrow[1][0], (10.0, 10.0))  # its point on the edge
        texts = [p for p in prims if p[0] == "text"]
        self.assertEqual([t[4] for t in texts], ["NOTE", "TWO"])
        self.assertEqual(texts[0][5], "start")
        self.assertLess(texts[1][2], texts[0][2])  # the second line below

    def test_leader_to_the_left(self):
        prims = ac.leader((30.0, 10.0), (10.0, 20.0), ["L"])
        self.assertEqual(prims[1][3], 7.0)
        self.assertEqual([p for p in prims if p[0] == "text"][0][5], "end")

    def test_leader_to_box(self):
        prims = ac.leader_to_box((0.0, 0.0), (10.0, -2.0, 30.0, 5.0))
        self.assertEqual(prims[0][3:5], (10.0, 1.5))
        self.assertEqual(ac.leader_to_box((10.0, 1.5), (10.0, -2.0, 30.0, 5.0)), [])


class FrameTests(unittest.TestCase):
    DATA = {
        "row1": {
            "char": "position",
            "dia": True,
            "tol": "0.05",
            "mod": "M",
            "datums": [("A", ""), ("B", "M")],
        },
    }

    def test_one_row(self):
        prims, box = ac.feature_control_frame(self.DATA, 0.0, 0.0)
        x0, y0, x1, y1 = box
        self.assertEqual((x0, y1), (0.0, 0.0))
        self.assertAlmostEqual(y0, -7.0)
        texts = ac.texts_of(prims)
        for text in ("0.05", "A", "B", "M"):
            self.assertIn(text, texts)
        # the position symbol (a circle with a cross) and the diameter sign are drawn
        circles = [p for p in prims if p[0] == "circle"]
        self.assertGreaterEqual(len(circles), 4)
        self.assertEqual(ac.fcf_text(self.DATA), "Position|⌀0.05(M)|A|B(M)")

    def test_cells_widen_for_long_tolerances(self):
        short = ac.feature_control_frame({"row1": {"tol": "0.1", "datums": []}}, 0, 0)[1]
        long_ = ac.feature_control_frame({"row1": {"tol": "0.12345", "datums": []}}, 0, 0)[1]
        self.assertGreater(long_[2] - long_[0], short[2] - short[0])

    def test_composite_shares_the_symbol_cell(self):
        data = {
            "composite": True,
            "row1": {
                "char": "position",
                "dia": True,
                "tol": "0.5",
                "datums": [("A", ""), ("B", ""), ("C", "")],
            },
            "row2": {"char": "position", "dia": True, "tol": "0.1", "datums": [("A", "")]},
        }
        prims, box = ac.feature_control_frame(data, 0.0, 0.0)
        self.assertAlmostEqual(box[1], -14.0)
        # no line across the symbol cell between the two rows
        across = [
            p
            for p in prims
            if p[0] == "line"
            and abs(p[2] + 7.0) < 1e-9
            and abs(p[4] + 7.0) < 1e-9
            and min(p[1], p[3]) < 1.0
        ]
        self.assertEqual(across, [])
        # one position symbol for both rows
        crosses = [p for p in prims if p[0] == "circle" and abs(p[3] - 0.6 * 1.75) < 1e-9]
        self.assertEqual(len(crosses), 1)
        self.assertEqual(ac.fcf_text(data).count("Position"), 2)

    def test_every_characteristic_draws(self):
        for name in ac.CHARACTERISTIC_NAMES:
            prims = ac.characteristic_symbol(name, 0.0, 0.0)
            self.assertTrue(prims, name)
            x0, y0, x1, y1 = ac.bbox(prims)
            self.assertLessEqual(max(abs(x0), abs(x1), abs(y0), abs(y1)), 2.5, name)

    def test_feature_control_with_leader(self):
        prims, box = ac.feature_control((0.0, 0.0), (20.0, 10.0), self.DATA)
        self.assertAlmostEqual((box[1] + box[3]) / 2.0, 10.0)
        self.assertEqual(box[0], 20.0)
        self.assertTrue(any(p[0] == "line" and (p[1], p[2]) == (0.0, 0.0) for p in prims))

    def test_spoken_symbols_for_searchable_pdf_text(self):
        # the drawn symbols as text for a PDF's searchable text (review PDF-6), never drawn
        data = {
            "row1": {
                "char": "position",
                "dia": True,
                "tol": "0.05",
                "mod": "M",
                "datums": [["A", ""], ["B", ""]],
            }
        }
        drawn, _box = ac.feature_control(None, (0.0, 0.0), data)
        self.assertEqual(ac.texts_of(drawn), ["0.05", "M", "A", "B"])
        spoken, _box = ac.feature_control(None, (0.0, 0.0), data, spoken=True)
        self.assertEqual(ac.texts_of(spoken), ["⌖", "⌀0.05", "M", "A", "B"])
        self.assertEqual(
            [p for p in spoken if p[0] != "text"], [p for p in drawn if p[0] != "text"]
        )
        self.assertEqual(set(ac.CHARACTERISTIC_CHARS), set(ac.CHARACTERISTIC_NAMES))


class DatumTests(unittest.TestCase):
    def test_triangle_on_the_edge_and_box(self):
        prims = ac.datum_identifier((0.0, 0.0), (0.0, 15.0), "b", tangent=(1.0, 0.0))
        tri = [p for p in prims if p[0] == "poly"][0]
        self.assertTrue(tri[2])
        base = tri[1][:2]
        self.assertAlmostEqual(base[0][1], 0.0)
        self.assertAlmostEqual(base[1][1], 0.0)
        self.assertGreater(tri[1][2][1], 0.0)  # the apex towards the box
        self.assertIn("B", ac.texts_of(prims))
        x0, y0, x1, y1 = ac.bbox([p for p in prims if p[0] == "line"][:4])
        self.assertAlmostEqual(x1 - x0, 7.0)


class TextureTests(unittest.TestCase):
    def test_kinds(self):
        basic = ac.surface_texture(None, (0.0, 0.0), {"kind": "basic"})
        removal = ac.surface_texture(None, (0.0, 0.0), {"kind": "removal"})
        none = ac.surface_texture(None, (0.0, 0.0), {"kind": "no_removal"})
        self.assertEqual(kinds(removal).count("line"), kinds(basic).count("line") + 1)
        self.assertEqual(kinds(none).count("circle"), 1)

    def test_iso_writes_the_value_under_a_line(self):
        prims = ac.surface_texture(None, (0.0, 0.0), {"value": "Ra 3.2", "lay": "="}, "ISO")
        text = [p for p in prims if p[0] == "text" and p[4] == "Ra 3.2"][0]
        level = [p for p in prims if p[0] == "line" and abs(p[2] - p[4]) < 1e-9]
        bar = max(level, key=lambda p: p[2])
        self.assertLess(text[2], bar[2])
        self.assertIn("=", ac.texts_of(prims))

    def test_asme_writes_the_value_above(self):
        prims = ac.surface_texture(None, (0.0, 0.0), {"value": "3.2"}, "ASME")
        text = [p for p in prims if p[0] == "text"][0]
        self.assertGreater(text[2], 5.0)

    def test_leader_when_away(self):
        prims = ac.surface_texture((0.0, 0.0), (10.0, 10.0), {})
        self.assertTrue(any(p[0] == "poly" and p[1][0] == (0.0, 0.0) for p in prims))
        self.assertEqual(
            ac.surface_text({"kind": "removal", "value": "Ra 1.6", "all_around": True}),
            "Material removal required, Ra 1.6, all around",
        )


class OrdinateTests(unittest.TestCase):
    def test_axis_from_the_mouse(self):
        self.assertEqual(ac.ordinate_axis((0, 0), (2, 20)), "x")
        self.assertEqual(ac.ordinate_axis((0, 0), (20, 2)), "y")

    def test_values(self):
        self.assertAlmostEqual(ac.ordinate_value((10, 10), (40, 25), "x"), 30.0)
        self.assertAlmostEqual(ac.ordinate_value((10, 10), (40, 25), "y", 0.5), 30.0)
        self.assertAlmostEqual(ac.ordinate_value((10, 10), (0, 0), "x"), 10.0)

    def test_x_ordinate_iso_turned(self):
        prims = ac.ordinate((40.0, 20.0), (41.0, 50.0), "x", "30", "ISO")
        line = prims[0]
        self.assertEqual((line[1], line[3]), (40.0, 40.0))
        self.assertEqual((line[2], line[4]), (21.5, 50.0))
        text = prims[1]
        self.assertEqual(text[6], 90.0)
        self.assertEqual(text[4], "30")

    def test_x_ordinate_asme_level(self):
        prims = ac.ordinate((40.0, 20.0), (41.0, 10.0), "x", "30", "ASME")
        self.assertEqual(prims[1][6], 0.0)
        self.assertLess(prims[1][2], 10.0)

    def test_y_ordinate(self):
        prims = ac.ordinate((40.0, 20.0), (10.0, 21.0), "y", "5")
        self.assertEqual((prims[0][2], prims[0][4]), (20.0, 20.0))
        self.assertEqual(prims[1][5], "end")

    def test_text_line_too_close_is_moved_out(self):
        prims = ac.ordinate((40.0, 20.0), (40.0, 20.5), "x", "0")
        self.assertGreaterEqual(prims[0][4], 22.0)


class ArcLengthTests(unittest.TestCase):
    def test_arc_length(self):
        prims = ac.arc_length((0.0, 0.0), 10.0, 0.0, 90.0, (10.0, 10.0), "15.71")
        arcs = [p for p in prims if p[0] == "arc"]
        self.assertEqual(len(arcs), 1)
        self.assertAlmostEqual(arcs[0][3], math.hypot(10, 10))
        self.assertEqual(len([p for p in prims if p[0] == "poly"]), 2)
        self.assertIn("⌒15.71", ac.texts_of(prims))


class SvgDxfTests(unittest.TestCase):
    def test_svg_is_valid_and_centred(self):
        prims = ac.leader((10.0, 10.0), (30.0, 20.0), ["NOTE"]) + ac.arc_length(
            (0, 0), 5.0, 0.0, 90.0, (6, 6), "7.85"
        )
        text, centre = ac.svg(prims)
        doc = xml.dom.minidom.parseString(text)
        svg = doc.documentElement
        self.assertEqual(svg.tagName, "svg")
        x0, y0, x1, y1 = ac.bbox(prims)
        self.assertAlmostEqual(centre[0], (x0 + x1) / 2.0)
        self.assertAlmostEqual(centre[1], (y0 + y1) / 2.0)
        self.assertTrue(svg.getAttribute("width").endswith("mm"))
        self.assertEqual(len(doc.getElementsByTagName("path")), 1)
        self.assertEqual(len(doc.getElementsByTagName("text")), 2)

    def test_rotated_text_in_svg(self):
        text, _c = ac.svg(ac.ordinate((40.0, 20.0), (41.0, 50.0), "x", "30"))
        self.assertIn("rotate(-90", text)

    def test_dxf(self):
        dxf = core.DxfWriter()
        prims, _box = ac.feature_control(
            (0.0, 0.0), (20.0, 10.0), {"row1": {"char": "flatness", "tol": "0.02"}}
        )
        ac.to_dxf(dxf, prims, "SYMBOLS")
        ents = core.read_dxf_entities(dxf.to_text())
        names = [e[0] for e in ents]
        self.assertIn("LINE", names)
        self.assertIn("SOLID", names)
        texts = [e[1][1][0] for e in ents if e[0] == "TEXT"]
        self.assertIn("0.02", texts)
        self.assertTrue(all(e[1][8][0] == "SYMBOLS" for e in ents))


def _tiny_pdf(width, height, text):
    """A minimal PDF like Qt writes one (plain cross-reference table)."""
    content = zlib.compress(("BT /F1 12 Tf 20 20 Td (%s) Tj ET" % text).encode())
    objs = [
        b"<< /Title (t) >>",
        b"<< /Type /Catalog /Pages 3 0 R >>",
        b"<< /Type /Pages /Kids [ 4 0 R ] /Count 1 >>",
        b"<< /Type /Page /Parent 3 0 R /Contents 5 0 R /Resources << /Font << /F1 6 0 R >> >> "
        b"/MediaBox [0 0 %d %d] >>" % (width, height),
        b"<< /Length 7 0 R /Filter /FlateDecode >>\nstream\n" + content + b"\nendstream\n",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"%d" % len(content),
    ]
    out = [b"%PDF-1.4\n"]
    offsets = []
    pos = len(out[0])
    for i, body in enumerate(objs, start=1):
        chunk = b"%d 0 obj\n" % i + body + b"\nendobj\n"
        offsets.append(pos)
        out.append(chunk)
        pos += len(chunk)
    xref = b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    xref += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out.append(xref)
    out.append(
        b"trailer\n<< /Size %d /Root 2 0 R /Info 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objs) + 1, pos)
    )
    return b"".join(out)


class PdfMergeTests(unittest.TestCase):
    def test_merge_two_files(self):
        a = _tiny_pdf(1191, 842, "ONE")
        b = _tiny_pdf(842, 595, "TWO")
        self.assertEqual(pdf.page_count(a), 1)
        merged = pdf.merge([a, b])
        self.assertEqual(pdf.page_count(merged), 2)
        # every object where the table says, the pages under the new tree
        bodies, trailer = pdf._objects(merged)
        root = pdf._ref(trailer, b"Root")
        pages = pdf._ref(bodies[root], b"Pages")
        kids = pdf._page_numbers(bodies, pages)
        self.assertEqual(len(kids), 2)
        for kid in kids:
            self.assertIn(b"/Parent %d 0 R" % pages, bodies[kid])
        self.assertIn(b"/MediaBox [0 0 842 595]", bodies[kids[1]])
        # the second file's references were moved with its objects; streams untouched
        second = bodies[kids[1]]
        contents = int(second.split(b"/Contents ")[1].split(b" ")[0])
        self.assertIn(b"stream", bodies[contents])
        data = bodies[contents].split(b"stream\n", 1)[1].rsplit(b"\nendstream", 1)[0]
        self.assertEqual(zlib.decompress(data), b"BT /F1 12 Tf 20 20 Td (TWO) Tj ET")

    def test_one_file_is_kept(self):
        a = _tiny_pdf(100, 100, "X")
        self.assertEqual(pdf.merge([a]), a)

    def test_refused_files(self):
        with self.assertRaises(pdf.PdfError):
            pdf.merge([])
        with self.assertRaises(pdf.PdfError):
            pdf.page_count(b"%PDF-1.5\nno table here\n")


if __name__ == "__main__":
    unittest.main()
