# SPDX-License-Identifier: LGPL-2.1-or-later
"""Better PDFs from drawings, the pure parts: the PDF reader / writer
(drawing_pdf_objects), the TrueType subset (drawing_pdf_font) and the rewrite that adds
layers, searchable text, links and metadata (drawing_pdf_core). The PDFs here are built
the way Qt writes TechDraw's (a Flate content stream per page, markers as code-coloured
squares); the GUI scenario drawing_pdf_export checks the real thing."""

import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import drawing_pdf  # noqa: E402
from sciforge import drawing_pdf_core as core  # noqa: E402
from sciforge import drawing_pdf_font as pf  # noqa: E402
from sciforge import drawing_pdf_objects as po  # noqa: E402
from sciforge.drawing_pdf_objects import Name, Ref, String  # noqa: E402

A3 = (420.0, 297.0)
A4 = (297.0, 210.0)
HELVETICA_WIDTHS = pf.StandardFont._WIDTHS


def page_pdf(width_mm, height_mm, content, title="Drawing001"):
    """A one-page PDF laid out like Qt's: catalogue, page tree, Helvetica as /F1 (with
    its widths, so text can be measured), the content Flate-compressed."""
    doc = po.Document({}, {}, {}, b"1.4")
    font = doc.add(
        {
            b"Type": Name(b"Font"),
            b"Subtype": Name(b"Type1"),
            b"BaseFont": Name(b"Helvetica"),
            b"FirstChar": 32,
            b"Widths": list(HELVETICA_WIDTHS),
        }
    )
    resources = doc.add(
        {
            b"Font": {b"F1": font},
            b"ExtGState": {b"GSa": {b"Type": Name(b"ExtGState"), b"CA": 1.0}},
            b"ColorSpace": {b"CSp": Name(b"DeviceRGB")},
        }
    )
    stream = doc.add({b"Filter": Name(b"FlateDecode")}, zlib.compress(content))
    pages = doc.add({b"Type": Name(b"Pages"), b"Kids": [], b"Count": 1})
    w = round(width_mm * core.MM)
    h = round(height_mm * core.MM)
    page = doc.add(
        {
            b"Type": Name(b"Page"),
            b"Parent": pages,
            b"Contents": stream,
            b"Resources": resources,
            b"Annots": doc.add([]),
            b"MediaBox": [0, 0, w, h],
        }
    )
    doc.objects[pages.num][b"Kids"] = [page]
    root = doc.add({b"Type": Name(b"Catalog"), b"Pages": pages})
    info = doc.add(
        {
            b"Title": po.text_string(title),
            b"Creator": String(b"FreeCAD TechDraw"),
            b"CreationDate": String(b"D:20261022043408Z"),
        }
    )
    doc.trailer = {b"Root": root, b"Info": info}
    return doc.write()


def marker(code):
    r, g, b = core.MARK_RED, code // 256, code % 256
    return b"q %.9f %.9f %.9f rg 0 0 0.1 0.1 re f Q\n" % (r / 255.0, g / 255.0, b / 255.0)


def line(x1, y1, x2, y2, dash=b"[]", width=b"7"):
    return b"q %s w %s 0 d %d %d m %d %d l S Q\n" % (width, dash, x1, y1, x2, y2)


def text(x, y, value, size=10):
    return b"BT /F1 %d Tf %d %d Td (%s) Tj ET\n" % (size, x, y, value)


def segments(content):
    """[(layer or None, [operators])] of a rewritten content stream."""
    out = []
    current = None
    ops = []
    for op in po.operations(content):
        if op.op == b"BDC":
            if ops:
                out.append((current, ops))
            current, ops = bytes(op.args[1]).decode()[2:], []
        elif op.op == b"EMC":
            out.append((current, ops))
            current, ops = None, []
        else:
            ops.append(op.op)
    if ops:
        out.append((current, ops))
    return out


# ------------------------------------------------------------------ objects
class ObjectTests(unittest.TestCase):
    def test_values_round_trip(self):
        value = {
            b"Type": Name(b"Annot"),
            b"Odd": Name(b"A B#"),
            b"Text": String(b"a (b) \\ c\n"),
            b"Hex": po.HexString(b"\x00\xff"),
            b"Ref": Ref(12),
            b"List": [1, -2.5, True, None, [Name(b"x")]],
        }
        back = po.parse_value(po.serialize(value))
        self.assertEqual(back, value)
        self.assertIsInstance(back[b"Odd"], Name)
        self.assertIsInstance(back[b"Hex"], po.HexString)
        self.assertEqual(back[b"Ref"], Ref(12))

    def test_literal_string_escapes(self):
        self.assertEqual(po.parse_value(b"(a\\(b\\)\\101\\\nc (d))"), b"a(b)Ac (d)")

    def test_text_strings(self):
        self.assertEqual(po.text_string("Bracket"), b"Bracket")
        raw = po.text_string("Staffa Ø20")
        self.assertTrue(raw.startswith(b"\xfe\xff"))
        self.assertEqual(po.decode_text_string(raw), "Staffa Ø20")

    def test_operations_keep_their_bytes(self):
        content = (
            b"q 1 0 0 1 5 5 cm\nBT /F1 12 Tf [(A) -120 (B)] TJ ET\nBI /W 1 /H 1 ID \x00\x01 EI\nQ"
        )
        ops = po.operations(content)
        self.assertEqual(
            [o.op for o in ops], [b"q", b"cm", b"BT", b"Tf", b"TJ", b"ET", b"BI", b"Q"]
        )
        self.assertEqual(ops[4].args, [[b"A", -120, b"B"]])
        self.assertEqual(content[ops[1].start : ops[1].stop], b"1 0 0 1 5 5 cm")

    def test_file_round_trip(self):
        data = page_pdf(*A4, line(0, 0, 10, 10))
        doc = po.read(data)
        self.assertEqual(len(doc.pages()), 1)
        page = doc.objects[doc.pages()[0]]
        self.assertIn(b"10 10 l", doc.stream_data(page[b"Contents"].num))
        again = po.read(doc.write(b"1.5"))
        self.assertEqual(again.version, b"1.5")
        self.assertEqual(sorted(again.objects), sorted(doc.objects))

    def test_refused_files(self):
        with self.assertRaises(po.PdfError):
            po.read(b"not a pdf")
        data = page_pdf(*A4, b"")
        with self.assertRaises(po.PdfError):
            po.read(data.replace(b"startxref", b"startxrex"))


# ------------------------------------------------------------------ the font
def tiny_font(fs_type=0):
    """A TrueType font with 4 glyphs: .notdef, A and B (simple), C (made of A)."""

    def simple(x):
        # one contour, 3 points
        return (
            struct.pack(">hhhhh", 1, 0, 0, x, 700)
            + struct.pack(">H", 2)
            + struct.pack(">H", 0)
            + bytes([1, 1, 1])
            + struct.pack(">hhh", 0, x, -x)
            + struct.pack(">hhh", 0, 700, -700)
        )

    composite = struct.pack(">hhhhh", -1, 0, 0, 500, 700) + struct.pack(">HHbb", 0x0000, 1, 0, 0)
    glyphs = [b"", simple(500), simple(600), composite]
    glyf = b""
    loca = []
    for g in glyphs:
        loca.append(len(glyf))
        glyf += g + b"\0" * (-len(g) % 4)
    loca.append(len(glyf))
    head = struct.pack(">IIIIHH", 0x00010000, 0, 0, 0x5F0F3CF5, 0, 1000) + b"\0" * 16
    head += struct.pack(">hhhh", 0, -200, 600, 800) + struct.pack(">HHhhh", 0, 8, 2, 1, 0)
    hhea = struct.pack(">I", 0x00010000) + struct.pack(">hhh", 800, -200, 0) + b"\0" * 24
    hhea += struct.pack(">H", 4)
    maxp = struct.pack(">IH", 0x00010000, 4) + b"\0" * 26
    hmtx = b"".join(struct.pack(">Hh", w, 0) for w in (500, 600, 650, 700))
    # cmap format 4: A B C -> 1 2 3
    seg = struct.pack(">HHHHHHH", 4, 0, 0, 4, 4, 1, 0)
    sub = seg + struct.pack(">HH", 0x43, 0xFFFF) + b"\0\0" + struct.pack(">HH", 0x41, 0xFFFF)
    sub += struct.pack(">hh", -0x40, 1) + struct.pack(">HH", 0, 0)
    sub = sub[:2] + struct.pack(">H", len(sub)) + sub[4:]
    cmap = struct.pack(">HHHHI", 0, 1, 3, 1, 12) + sub
    os2 = struct.pack(">HhHHH", 3, 500, 400, 5, fs_type) + b"\0" * 76 + struct.pack(">hh", 500, 700)
    post = struct.pack(">Ii", 0x00030000, 0) + b"\0" * 24
    tables = {
        "head": head,
        "hhea": hhea,
        "maxp": maxp,
        "hmtx": hmtx,
        "loca": b"".join(struct.pack(">I", o) for o in loca),
        "glyf": glyf,
        "cmap": cmap,
        "OS/2": os2,
        "post": post,
    }
    return pf._assemble(tables)


class FontTests(unittest.TestCase):
    def test_metrics_and_map(self):
        font = pf.TrueType(tiny_font())
        self.assertEqual([font.glyph(c) for c in "ABCZ"], [1, 2, 3, 0])
        self.assertEqual(font.width("AB"), 1250.0)
        self.assertEqual(font.units, 1000)

    def test_subset_keeps_numbers_and_components(self):
        font = pf.TrueType(tiny_font())
        small = pf.TrueType(font.subset([3]))  # C, made of A
        self.assertEqual(small.num_glyphs, 4)
        offsets = small._offsets()
        sizes = [offsets[i + 1] - offsets[i] for i in range(4)]
        self.assertGreater(sizes[3], 0)  # C
        self.assertGreater(sizes[1], 0)  # A, a part of C
        self.assertEqual(sizes[2], 0)  # B emptied
        self.assertEqual(small.width("C"), 700.0)
        self.assertEqual(pf._checksum(font.subset([3])), 0xB1B0AFBA)

    def test_licence_is_respected(self):
        with self.assertRaises(pf.FontRefused):
            pf.TrueType(tiny_font(fs_type=0x0002)).subset([1])
        whole = pf.TrueType(tiny_font(fs_type=0x0100))  # no subsetting: all of it
        self.assertEqual(whole.subset([1]), whole.data)
        path = os.path.join(tempfile.mkdtemp(), "restricted.ttf")
        with open(path, "wb") as handle:
            handle.write(tiny_font(fs_type=0x0002))
        font, why = pf.load(path)
        self.assertIsInstance(font, pf.StandardFont)
        self.assertIn("licence", why)
        shutil.rmtree(os.path.dirname(path))

    def test_embedded_font_objects(self):
        font = pf.EmbeddedFont(pf.TrueType(tiny_font()))
        self.assertEqual(font.encode("CA"), b"\x00\x03\x00\x01")
        doc = po.Document({}, {}, {})
        ref = font.objects(doc)
        type0 = doc.objects[ref.num]
        self.assertEqual(type0[b"Encoding"], b"Identity-H")
        self.assertTrue(re.match(rb"[A-Z]{6}\+", type0[b"BaseFont"]))
        cmap = doc.stream_data(type0[b"ToUnicode"].num)
        self.assertIn(b"<0003> <0043>", cmap)

    def test_missing_font_falls_back(self):
        font, why = pf.load("/no/such/font.ttf")
        self.assertIsInstance(font, pf.StandardFont)
        self.assertTrue(why)
        self.assertEqual(font.width("AB"), 1334.0)


# ------------------------------------------------------------------ layers
CODES_ITEMS = [("View1", "view"), ("Dim1", "other")]


def coded_page():
    """Template, a view (caption, hatching, a visible, a hidden and a centre edge, a centre
    mark, a section line), a dimension, then something after every item."""
    plan, codes = core.marker_plan(CODES_ITEMS)
    c = {(k, band): code for k, band, _z, code, _rgb in plan}
    content = b"/GSa gs\n0.06 0 0 -0.06 0 842 cm\n"
    content += b"q 1 1 1 rg 0 0 100 100 re f Q\n"  # the paper (template)
    content += line(0, 0, 100, 0)  # the frame (template)
    content += b"h\n"  # a stray closepath, as Qt writes
    content += marker(c["View1", "begin"]) + text(10, 10, b"SECTION A-A")
    content += marker(c["View1", "faces"]) + line(1, 1, 2, 2, width=b"1")
    content += marker(c["View1", "edges"])
    content += line(3, 3, 4, 4) + line(5, 5, 6, 6, b"[42 10.5]", b"3.5")
    content += line(7, 7, 8, 8, b"[21.6 5.4]", b"1.8") + line(9, 9, 10, 10, b"[24 3 1 3]", b"1.8")
    content += marker(c["View1", "cosmetic"])  # SciForge's centre marks, a solid cosmetic line
    content += line(19, 19, 20, 20, b"[21.6 5.4]", b"1.8") + line(21, 21, 22, 22, width=b"1.8")
    content += marker(c["View1", "marks"]) + line(11, 11, 12, 12, width=b"1")
    content += marker(c["View1", "lines"]) + line(13, 13, 14, 14, b"[84 42 42 42]", b"3.5")
    content += b"/CSp CS\nSCN\n"  # a colour without its values (Qt)
    content += marker(c["View1", "end"])
    content += marker(c["Dim1", "begin"]) + line(15, 15, 16, 16, width=b"2") + text(20, 20, b"50")
    content += marker(c["Dim1", "end"])
    content += line(17, 17, 18, 18)  # after every item: on no layer
    return content, codes


class LayerTests(unittest.TestCase):
    def test_marker_plan(self):
        plan, codes = core.marker_plan(CODES_ITEMS)
        self.assertEqual(len(plan), len(core.VIEW_BANDS) + len(core.OTHER_BANDS))
        self.assertEqual(plan[0][4], (165, 0, 1))
        self.assertEqual(codes[1], ("View1", "view", "begin"))
        self.assertEqual(codes[8], ("Dim1", "other", "begin"))
        zs = [z for _k, _b, z, _c, _rgb in plan[:7]]
        self.assertEqual(zs, sorted(zs))
        # between TechDraw's z-values: captions 0 < faces 10 < edges 70 < cosmetic edges
        # (lifted to COSMETIC_Z while printing) < marks 80 < lines 90
        self.assertTrue(zs[0] < 0 < zs[1] < 10 and 41 < zs[2] < 60)
        self.assertTrue(70 < zs[3] < core.COSMETIC_Z < zs[4] < 80 < zs[5] < 90)

    def test_edge_layers(self):
        self.assertEqual(core.edge_layer([], 7, 3.5), "visible")
        self.assertEqual(core.edge_layer([0], 7, 3.5), "visible")
        self.assertEqual(core.edge_layer([42, 10.5], 3.5, 3.5), "hidden")
        self.assertEqual(core.edge_layer([42, 10.5], 3.5, None), "hidden")
        self.assertEqual(core.edge_layer([21.6, 5.4], 1.8, 3.5), "centre")  # SciForge's marks
        self.assertEqual(core.edge_layer([24, 3, 1, 3], 3.5, 3.5), "centre")

    def test_layers_of_a_page(self):
        content, codes = coded_page()
        out, used, found = core.layer_content(content, codes, {"View1": 3.5})
        self.assertEqual(sorted(found), sorted(codes))
        self.assertEqual(used, {k for k, _n in core.LAYERS})
        segs = segments(out)
        painted = [
            (layer, ops)
            for layer, ops in segs
            if any(o in core.PAINT_OPS or o == b"Tj" for o in ops)
        ]
        layers = []
        for layer, ops in painted:
            for o in ops:
                if o in core.PAINT_OPS or o == b"Tj":
                    layers.append(layer)
        self.assertEqual(
            layers,
            [
                "border",
                "border",
                "annotations",
                "hatching",
                "visible",
                "hidden",
                "centre",
                "centre",
                "centre",
                "visible",
                "centre",
                "hatching",
                "annotations",
                "annotations",
                None,
            ],
        )
        # the markers are gone, and so are Qt's stray closepath and empty colour
        self.assertNotIn(b"0.1 0.1 re", out)
        self.assertNotIn(b"\nh\n", out)
        self.assertNotIn(b"\nSCN\n", out)
        # never a q or Q inside a marked-content sequence
        depth = None
        for op in po.operations(out):
            if op.op == b"BDC":
                depth = 0
            elif op.op == b"EMC":
                depth = None
            elif depth is not None:
                self.assertNotIn(op.op, (b"q", b"Q"))

    def test_line_group_where_marks_and_hidden_edges_look_alike(self):
        # TechDraw's line group "FC 0.35mm": hidden edges at 0.18 mm, dashed exactly like
        # SciForge's centre marks; only the cosmetic band tells them apart (PDF-4)
        content, codes = coded_page()
        out, used, _found = core.layer_content(content, codes, {"View1": 1.8})
        layers = []
        for layer, ops in segments(out):
            layers += [layer] * sum(1 for o in ops if o == b"S")
        # edges: solid, dashed at 0.35 mm (not the hidden width now), dashed at the hidden
        # width, four dashes; cosmetic: dashed, solid; centre marks
        self.assertEqual(
            layers[2:9], ["visible", "centre", "hidden", "centre", "centre", "visible", "centre"]
        )

    def test_pdf_a_markers_go_without_layers(self):
        # PDF/A: Qt paints the markers opaque; they and Qt's empty colours go, no layer
        content, codes = coded_page()
        out, used, found = core.layer_content(content, codes, {"View1": 3.5}, layers=False)
        self.assertEqual(used, set())
        self.assertEqual(sorted(found), sorted(codes))
        self.assertNotIn(b"0.1 0.1 re", out)
        self.assertNotIn(b"\nSCN\n", out)
        self.assertNotIn(b"BDC", out)
        # it does not mind marked content already there
        out, _u, _f = core.layer_content(b"/Span BMC " + marker(1) + b"EMC", codes, layers=False)
        self.assertNotIn(b"re", out)

    def test_without_markers_everything_is_the_template(self):
        content = line(0, 0, 1, 1) + text(1, 1, b"A3")
        out, used, found = core.layer_content(content, {})
        self.assertEqual(used, {"border"})
        self.assertEqual(found, [])

    def test_marked_content_already_there_is_left_alone(self):
        with self.assertRaises(core.LayerError):
            core.layer_content(b"/Span BMC " + line(0, 0, 1, 1) + b"EMC", {})


# ------------------------------------------------------------------ text and links
class TextTests(unittest.TestCase):
    def runs(self, content):
        doc = po.read(page_pdf(*A4, content))
        return core.text_runs(doc, doc.pages()[0])

    def test_runs_lines_and_spaces(self):
        content = b"BT /F1 10 Tf 100 700 Td (NOTE) Tj 40 0 Td (1) Tj ET\n"
        content += b"BT /F1 10 Tf 1 0 0 1 100 680 Tm [(see ) -50 (www.example.com)] TJ ET"
        runs = self.runs(content)
        self.assertEqual([r["text"] for r in runs], ["NOTE 1", "see www.example.com"])
        box = runs[0]["boxes"][0]
        self.assertAlmostEqual(box[0], 100.0)
        self.assertAlmostEqual(box[2], 100.0 + 7.22, places=2)  # N is 722/1000 wide
        self.assertLess(runs[1]["boxes"][0][1], runs[0]["boxes"][0][1])

    def test_runs_follow_the_transformation(self):
        content = b"q 0.06 0 0 -0.06 0 842 cm BT /F1 100 Tf 1 0 0 -1 1000 1000 Tm (A) Tj ET Q"
        box = self.runs(content)[0]["boxes"][0]
        self.assertAlmostEqual(box[0], 60.0)
        self.assertAlmostEqual(box[1], 842 - 60.0 - 0.2 * 6.0, places=4)  # (its descent)
        self.assertAlmostEqual(box[3], 842 - 60.0 + 0.8 * 6.0, places=4)

    def test_type0_text_via_to_unicode(self):
        data, _cmap = core._parse_cmap(pf._to_unicode([(5, "Ø"), (6, "2")])), None
        self.assertEqual(data[0], {5: "Ø", 6: "2"})
        self.assertEqual(data[1], 2)

    def test_links(self):
        self.assertEqual(
            core.find_links("see https://sciforge.org/spec. and www.example.com, mailto:a@b.c"),
            [
                (4, 29, "https://sciforge.org/spec"),
                (35, 50, "http://www.example.com"),
                (52, 64, "mailto:a@b.c"),
            ],
        )
        self.assertEqual(core.find_links("no link here: www."), [])

    def test_overlay(self):
        font = pf.StandardFont()
        texts = [
            {
                "text": "Bracket",
                "x": 100,
                "y": 50,
                "size": 5,
                "anchor": "middle",
                "layer": "border",
            },
            {
                "text": "go www.sciforge.org",
                "x": 10,
                "y": 10,
                "size": 3.5,
                "width": 30,
                "layer": "annotations",
            },
        ]
        content, links, used = core.overlay(texts, font, A4, [0, 0, 842, 595])
        self.assertEqual(used, {"border", "annotations"})
        self.assertIn(b"3 Tr", content)
        ops = po.operations(content)
        tms = [o.args for o in ops if o.op == b"Tm"]
        width = font.width("Bracket") / 1000.0 * 5 * core.MM
        self.assertAlmostEqual(tms[0][4], 100 * core.MM - width / 2, places=3)
        self.assertAlmostEqual(tms[0][5], 595 - (210 - 50) * core.MM, places=3)
        tz = [o.args[0] for o in ops if o.op == b"Tz"]
        natural = font.width("go www.sciforge.org") / 1000.0 * 3.5 * core.MM
        self.assertAlmostEqual(tz[0], 100 * 30 * core.MM / natural, places=2)
        self.assertEqual(len(links), 1)
        rect, uri, layer = links[0]
        self.assertEqual((uri, layer), ("http://www.sciforge.org", "annotations"))
        self.assertGreater(rect[0], 10 * core.MM)
        self.assertLessEqual(rect[2], 10 * core.MM + 30 * core.MM + 1e-6)


# ------------------------------------------------------------------ the whole file
META = {
    "title": "Bracket",
    "author": "Luca",
    "subject": "BR-001 - Mounting bracket",
    "keywords": "Material: Steel",
    "creator": "SciForge 0.1.0",
    "producer": "SciForge 0.1.0 (FreeCAD TechDraw, Qt PDF)",
}


class EnhanceTests(unittest.TestCase):
    def two_sheets(self):
        content, codes = coded_page()
        content += b"BT /F1 10 Tf 100 100 Td (see https://sciforge.org/spec) Tj ET\n"
        first = page_pdf(*A3, content)
        second = page_pdf(*A4, line(0, 0, 50, 50) + text(5, 5, b"A4"))
        texts = [
            {"text": "Bracket", "x": 300, "y": 30, "size": 5, "layer": "border"},
            # Qt printed "50" as text near the top left corner (its 20, 20 are in the page's
            # flipped, scaled coordinates): not added there again...
            {"text": "50", "x": 1.0, "y": 296.0, "size": 3.5, "layer": "annotations"},
            # ...but a "50" elsewhere is added
            {"text": "50", "x": 200, "y": 100, "size": 3.5, "layer": "annotations"},
        ]
        sheets = [
            {"size": A3, "codes": codes, "hidden": {"View1": 3.5}, "texts": texts},
            {
                "size": A4,
                "codes": {},
                "hidden": {},
                "texts": [{"text": "Sheet 2", "x": 200, "y": 20, "size": 3.5, "layer": "border"}],
            },
        ]
        merged = drawing_pdf.merge([first, second])
        return core.enhance(merged, sheets, META, pf.StandardFont())

    def test_layers_text_links_metadata(self):
        out, report = self.two_sheets()
        info = core.summary(out)
        self.assertEqual(info["layers"], [n for _k, n in core.LAYERS])
        self.assertEqual(info["pages"], [[0, 0, 1191, 842], [0, 0, 842, 595]])
        self.assertEqual(info["info"]["Title"], "Bracket")
        self.assertEqual(info["info"]["Author"], "Luca")
        self.assertEqual(info["info"]["Subject"], "BR-001 - Mounting bracket")
        self.assertEqual(info["info"]["Creator"], "SciForge 0.1.0")
        self.assertEqual(info["info"]["CreationDate"], "D:20261022043408Z")
        self.assertEqual(info["links"], ["https://sciforge.org/spec"])
        self.assertEqual(report["pages"][0]["texts"], 2)  # one "50" was printed already
        self.assertEqual(report["pages"][1]["layers"], ["border"])
        doc = po.read(out)
        self.assertEqual(doc.version, b"1.5")
        root = doc.get(doc.trailer[b"Root"])
        meta = doc.stream_data(root[b"Metadata"].num).decode("utf-8")
        self.assertIn("<xmp:CreatorTool>SciForge 0.1.0</xmp:CreatorTool>", meta)
        self.assertIn("Bracket", meta)
        # one set of layers for both pages
        first, second = doc.pages()
        props1 = doc.get(doc.get(doc.objects[first][b"Resources"])[b"Properties"])
        props2 = doc.get(doc.get(doc.objects[second][b"Resources"])[b"Properties"])
        self.assertEqual(props1[b"SFborder"], props2[b"SFborder"])

    def test_pdf_a_gets_no_layers(self):
        content, codes = coded_page()
        data = page_pdf(*A4, content)
        doc = po.read(data)
        root = doc.get(doc.trailer[b"Root"])
        root[b"Metadata"] = doc.add(
            {b"Type": Name(b"Metadata")},
            b"<pdfaid:part>1</pdfaid:part>" b"<pdfaid:conformance>B</pdfaid:conformance>",
        )
        out, report = core.enhance(doc.write(), [{"size": A4, "codes": codes, "texts": []}], META)
        self.assertTrue(report["pdfa"])
        self.assertEqual(core.summary(out)["layers"], [])
        meta = po.read(out)
        root = meta.get(meta.trailer[b"Root"])
        self.assertIn(b"<pdfaid:part>1</pdfaid:part>", meta.stream_data(root[b"Metadata"].num))
        self.assertEqual(meta.version, b"1.4")

    def test_no_markers_printed_means_no_layers(self):
        data = page_pdf(*A4, line(0, 0, 1, 1))
        out, report = core.enhance(data, [{"size": A4, "codes": {1: ("V", "view", "begin")}}], META)
        self.assertEqual(core.summary(out)["layers"], [])
        self.assertIn("no markers", report["pages"][0]["note"])

    def test_dates(self):
        self.assertEqual(core._iso_date("D:20261022043408Z"), "2026-10-22T04:34:08Z")
        self.assertEqual(core._iso_date("D:20261022043408+02'00'"), "2026-10-22T04:34:08+02:00")
        self.assertIsNone(core._iso_date("yesterday"))

    @unittest.skipUnless(
        shutil.which("pdftotext") and shutil.which("pdfinfo"), "poppler not installed"
    )
    def test_poppler_reads_it(self):
        out, _report = self.two_sheets()
        folder = tempfile.mkdtemp()
        try:
            path = os.path.join(folder, "two.pdf")
            with open(path, "wb") as handle:
                handle.write(out)
            info = subprocess.run(["pdfinfo", path], capture_output=True, text=True)
            self.assertIn("Pages:           2", info.stdout)
            self.assertIn("Title:           Bracket", info.stdout)
            self.assertNotIn("Syntax Error", info.stderr)
            words = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True)
            self.assertIn("Bracket", words.stdout)
            self.assertIn("Sheet 2", words.stdout)
            self.assertEqual(words.stdout.count("50"), 2)
            self.assertNotIn("Syntax Error", words.stderr)
            # the added text is where it was asked for (page mm, y up), not moved by the
            # transformation the page's drawing left behind
            boxes = subprocess.run(
                ["pdftotext", "-bbox", "-f", "1", "-l", "1", path, "-"],
                capture_output=True,
                text=True,
            ).stdout
            found = re.search(
                r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">Bracket<', boxes
            )
            self.assertIsNotNone(found, boxes)
            self.assertAlmostEqual(float(found.group(1)), 300 * core.MM, delta=0.5)
            baseline_from_top = (297 - 30) * core.MM + (842 - 297 * core.MM)
            self.assertLess(float(found.group(2)), baseline_from_top)
            self.assertGreater(float(found.group(3)), baseline_from_top - 1)
        finally:
            shutil.rmtree(folder)


# ------------------------------------------------------------------ PDF/A, PDF/X, file size
QT_XMP = (
    "<?xpacket begin='\ufeff' id='W5M0MpCehiHzreSzNTczkc9d'?>\n"
    '<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
    ' xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/" xmlns:pdf="http://ns.adobe.com/pdf/1.3/"'
    ' xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/" xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/">'
    "<rdf:RDF>"
    '<rdf:Description rdf:about="" pdf:Producer="Qt 6.8.3" pdf:Trapped="False"/>'
    '<rdf:Description rdf:about="" xmpMM:DocumentID="uuid:b4d2e09f" xmpMM:VersionID="1"'
    ' xmpMM:RenditionClass="default"/>'
    '<rdf:Description rdf:about="" %s/>'
    "</rdf:RDF></x:xmpmeta>\n<?xpacket end='w'?>"
)
PDFA_1B = 'pdfaid:part="1" pdfaid:conformance="B"'
PDFX_4 = 'pdfxid:GTS_PDFXVersion="PDF/X-4"'


def archival_pdf(identity, content):
    """A one-page PDF with Qt's XMP for PDF/A-1b or PDF/X-4 and /Trapped /False."""
    doc = po.read(page_pdf(*A4, content))
    root = doc.get(doc.trailer[b"Root"])
    root[b"Metadata"] = doc.add(
        {b"Type": Name(b"Metadata"), b"Subtype": Name(b"XML")},
        (QT_XMP % identity).encode("utf-8"),
    )
    doc.get(doc.trailer[b"Info"])[b"Trapped"] = Name(b"False")
    return doc.write()


def reachable(doc):
    seen, todo = set(), list(doc.trailer.values())
    while todo:
        value = todo.pop()
        if isinstance(value, Ref) and value.num not in seen and value.num in doc.objects:
            seen.add(value.num)
            todo.append(doc.objects[value.num])
        elif isinstance(value, dict):
            todo += list(value.values())
        elif isinstance(value, list):
            todo += value
    return seen


class ArchivalTests(unittest.TestCase):
    def enhanced(self, identity, font=None, texts=None):
        content, codes = coded_page()
        content += b"BT /F1 10 Tf 100 100 Td (see https://sciforge.org/spec) Tj ET\n"
        texts = texts if texts is not None else [{"text": "AB", "x": 10, "y": 10, "size": 5}]
        sheet = {"size": A4, "codes": codes, "hidden": {"View1": 3.5}, "texts": texts}
        font = font or pf.EmbeddedFont(pf.TrueType(tiny_font()))
        return core.enhance(archival_pdf(identity, content), [sheet], META, font)

    def metadata(self, doc):
        import xml.etree.ElementTree as ET

        root = doc.get(doc.trailer[b"Root"])
        packet = doc.stream_data(root[b"Metadata"].num).decode("utf-8")
        ET.fromstring(packet.split("?>", 1)[1].rsplit("<?xpacket", 1)[0])  # well formed
        return packet

    def test_pdf_a_stays_pdf_a(self):
        # PDF-1, PDF-2: CIDSet for the added subset, Info and XMP agree on Trapped, the
        # file's identity kept; markers out although no layers go in
        out, report = self.enhanced(PDFA_1B)
        self.assertTrue(report["pdfa"])
        self.assertIn("no layers", report["pages"][0]["note"])
        self.assertEqual(report["pages"][0]["texts"], 1)
        doc = po.read(out)
        self.assertEqual(doc.version, b"1.4")
        self.assertEqual(core.summary(out)["layers"], [])
        content = core.page_content(doc, doc.pages()[0])
        self.assertNotIn(b"0.1 0.1 re", content)  # the markers
        self.assertNotIn(b"\nSCN\n", content)  # Qt's colour without values
        self.assertNotIn(b"BDC", content.replace(b"/Span", b""))
        descriptors = [
            o for o in doc.objects.values()
            if isinstance(o, dict) and o.get(b"Type") == b"FontDescriptor"
        ]
        self.assertEqual(len(descriptors), 1)
        cid_set = doc.stream_data(descriptors[0][b"CIDSet"].num)
        self.assertEqual(cid_set, bytes([0b11100000]))  # .notdef, A, B
        packet = self.metadata(doc)
        for prop in (
            "<pdfaid:part>1</pdfaid:part>",
            "<pdfaid:conformance>B</pdfaid:conformance>",
            "<xmpMM:DocumentID>uuid:b4d2e09f</xmpMM:DocumentID>",
            "<pdf:Trapped>False</pdf:Trapped>",
            "<dc:title>",
        ):
            self.assertIn(prop, packet)
        info = doc.get(doc.trailer[b"Info"])
        self.assertEqual(info[b"Trapped"], b"False")
        self.assertEqual(len(core.summary(out)["links"]), 1)

    def test_pdf_a_without_an_embeddable_font_adds_no_text(self):
        out, report = self.enhanced(PDFA_1B, font=pf.StandardFont())
        self.assertEqual(report["pages"][0]["texts"], 0)
        self.assertNotIn(b"SFText", out)

    def test_pdf_x_stays_pdf_x(self):
        # PDF-3: the PDF/X-4 version, document ids and Trapped stay; X-4 may have layers
        out, report = self.enhanced(PDFX_4)
        self.assertEqual(report["pdfx"], "PDF/X-4")
        info = core.summary(out)
        self.assertEqual(info["layers"], [n for _k, n in core.LAYERS])
        self.assertEqual(info["links"], [])  # no annotations on a print-ready page
        packet = self.metadata(po.read(out))
        for prop in (
            "<pdfxid:GTS_PDFXVersion>PDF/X-4</pdfxid:GTS_PDFXVersion>",
            "<xmpMM:DocumentID>uuid:b4d2e09f</xmpMM:DocumentID>",
            "<xmpMM:VersionID>1</xmpMM:VersionID>",
            "<xmpMM:RenditionClass>default</xmpMM:RenditionClass>",
            "<pdf:Trapped>False</pdf:Trapped>",
        ):
            self.assertIn(prop, packet)

    def test_kept_xmp_reads_attributes_and_elements(self):
        found = core.kept_xmp(
            b'<a xmlns:pdfaid="x" pdfaid:part="2"/><pdfaid:conformance>U</pdfaid:conformance>'
        )
        self.assertEqual(found, [("pdfaid", "part", "2"), ("pdfaid", "conformance", "U")])
        self.assertEqual(core.kept_xmp(None), [])

    def test_no_dead_objects(self):
        # PDF-5: the replaced page contents, Length objects and merged files' catalogues
        # are not written; what is left is numbered without gaps
        content, codes = coded_page()
        first = page_pdf(*A3, content)
        second = page_pdf(*A4, line(0, 0, 50, 50))
        merged = drawing_pdf.merge([first, second])
        sheets = [{"size": A3, "codes": codes, "texts": []}, {"size": A4, "codes": {}, "texts": []}]
        out, _report = core.enhance(merged, sheets, META, pf.StandardFont())
        doc = po.read(out)
        self.assertEqual(reachable(doc), set(doc.objects))
        self.assertEqual(sorted(doc.objects), list(range(1, len(doc.objects) + 1)))

    def test_prune(self):
        doc = po.Document({}, {}, {})
        doc.add({b"Dead": True})
        length = doc.add(3)
        stream = doc.add({b"Length": length}, b"abc")
        root = doc.add({b"Type": Name(b"Catalog"), b"S": stream, b"Gone": Ref(99)})
        doc.trailer = {b"Root": root, b"Size": 9}
        self.assertEqual(doc.prune(), 2)  # the dead object and the Length object
        root = doc.get(doc.trailer[b"Root"])
        self.assertEqual(sorted(doc.objects), [1, 2])
        self.assertEqual(doc.stream_data(root[b"S"].num), b"abc")
        self.assertIsNone(root[b"Gone"])
        po.read(doc.write())

    def test_characters_the_font_lacks_stay_searchable(self):
        # PDF-6: a character the font has no glyph for: the text goes in as ActualText
        font = pf.EmbeddedFont(pf.TrueType(tiny_font()))
        texts = [{"text": "AB 30\u2032 \u672c", "x": 10, "y": 10, "size": 5}]
        content, _links, _used = core.overlay(texts, font, A4, [0, 0, 842, 595])
        self.assertIn(b"/Span << /ActualText (\xfe\xff\x00A\x00B", content)
        plain, _links, _used = core.overlay([{"text": "ABC", "x": 1, "y": 1}], font, A4, [0, 0, 842, 595])
        self.assertNotIn(b"ActualText", plain)
        self.assertNotIn(b"ActualText", core.overlay([{"text": "A\u00e9", "x": 1, "y": 1}], pf.StandardFont(), A4, [0, 0, 842, 595])[0])
        self.assertIn(b"ActualText", core.overlay([{"text": "A\u2032", "x": 1, "y": 1}], pf.StandardFont(), A4, [0, 0, 842, 595])[0])

    @unittest.skipUnless(shutil.which("pdftotext"), "poppler not installed")
    def test_poppler_reads_actual_text(self):
        font = pf.EmbeddedFont(pf.TrueType(tiny_font()))
        texts = [{"text": "AB 30\u2032 \u672c", "x": 10, "y": 100, "size": 5}]
        out, _report = core.enhance(
            page_pdf(*A4, b""), [{"size": A4, "codes": None, "texts": texts}], META, font
        )
        folder = tempfile.mkdtemp()
        try:
            path = os.path.join(folder, "actual.pdf")
            with open(path, "wb") as handle:
                handle.write(out)
            words = subprocess.run(["pdftotext", path, "-"], capture_output=True)
            self.assertIn("AB 30\u2032 \u672c", words.stdout.decode("utf-8"))
            self.assertNotIn(b"Syntax Error", words.stderr)
        finally:
            shutil.rmtree(folder)


if __name__ == "__main__":
    unittest.main()
