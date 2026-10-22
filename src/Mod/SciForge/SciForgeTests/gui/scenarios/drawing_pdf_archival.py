# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export PDF and what the review of the better PDFs found (2026-10-22, PDF-1..6): PDF/A
and PDF/X files stay what they are, the file is not twice the size of TechDraw's print,
centre marks keep their own layer when hidden edges look exactly like them, and every
character and GD&T symbol can be searched.

The filleted block (drawing_fixtures.block), ISO A3, base view Top at 1:1 at (130, 190).
By script (the subject is the export): a projected view below at (130, 110) with hidden
edges, both views with a hidden line width of 0.18 mm, the width and dash of SciForge's
centre marks (TechDraw's line group "FC 0.35mm" does that), a centre mark on the hole, a feature control frame (position, diameter, 0.05, M, A, B) at (260, 120),
a leader note with angle minutes and seconds (osifont has no glyph for them) at (60, 40).

A  Export PDF (normal): the centre mark is on "Centerlines and Center Marks", not on
   "Hidden Edges"; the projected view's hidden edges are on "Hidden Edges" (rendered with
   one layer on). The file is not much bigger than TechDraw's print: nothing in it is
   unused. "30°15′20″" and the frame's "⌀0.05" and position symbol are searchable.
B  FreeCAD's PDF preference on PDF/A-1b: no layers, no marker left (no red pixel in a
   600 dpi picture, poppler finds no syntax error), the added osifont subset has a
   CIDSet like Qt's own, the XMP keeps pdfaid and xmpMM and has pdf:Trapped like the
   document information. The preference is put back afterwards.
C  PDF/X-4: the XMP keeps its PDF/X version, document ids and pdf:Trapped; layers are
   there (PDF/X-4 allows them), no link annotations (a print-ready page has none).
"""

import os
import re
import shutil
import subprocess

import FreeCAD as App
from PySide import QtGui

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

BASE = (130.0, 190.0)
BELOW = (130.0, 110.0)
FCF_AT = (260.0, 120.0)
LEADER_AT = (60.0, 40.0)
OUT = os.path.join(d.OUT, "pdf_archival")
PREFS = "User parameter:BaseApp/Preferences/Mod"
state = {}


def new_design():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    state["pdf_version"] = App.ParamGet(PREFS).GetInt("PDFVersion", 0)
    s.new_design("Archive")()
    fx.block(App.ActiveDocument)
    h.fit()


def base():
    return d.bases()[0]


def scripted():
    from sciforge import drawing, drawing_annot

    page = d.page()
    state["page"] = page
    below = drawing.add_projected(base(), "Bottom", *BELOW)
    drawing._style(below, "Visible and Hidden Edges")
    state["below"] = below
    for view in (base(), below):
        view.ViewObject.HiddenWidth = 0.18  # like TechDraw's line group "FC 0.35mm"
    drawing._make_mark(base(), (0.0, 0.0), fx.HOLE_R)
    drawing_annot.add_annotation(
        page,
        {
            "kind": "fcf",
            "fcf": {
                "row1": {
                    "char": "position",
                    "dia": True,
                    "tol": "0.05",
                    "mod": "M",
                    "datums": [["A", ""], ["B", ""]],
                }
            },
            "off": list(FCF_AT),
        },
    )
    drawing_annot.add_annotation(
        page, {"kind": "leader", "lines": ["ANGLE 30°15′20″"], "off": list(LEADER_AT)}
    )
    drawing.set_title(page, {"Description": "Archive block", "DrawnBy": "Luca"})
    page.Document.recompute()


scripted.wait_ms = 4000


def summary(path):
    from sciforge import drawing_pdf_core

    with open(path, "rb") as handle:
        return drawing_pdf_core.summary(handle.read())


def read(path):
    from sciforge import drawing_pdf_objects as po

    with open(path, "rb") as handle:
        return po.read(handle.read())


def words(path):
    if shutil.which("pdftotext") is None:
        return None
    return subprocess.run(
        ["pdftotext", path, "-"], capture_output=True, timeout=60
    ).stdout.decode("utf-8", "replace")


def flat(text):
    return "".join(text.split())


def export(name, version=None):
    """Export PDF of the sheet with FreeCAD's PDF preference at `version` (put back
    afterwards), TechDraw's own print kept as <name>-printed.pdf."""
    from sciforge import drawing, drawing_pdf_export

    prefs = App.ParamGet(PREFS)
    old = prefs.GetInt("PDFVersion", 0)
    path = os.path.join(OUT, name + ".pdf")
    try:
        if version is not None:
            prefs.SetInt("PDFVersion", version)
        drawing_pdf_export.KEEP_PRINTED["path"] = os.path.join(OUT, name + "-printed.pdf")
        drawing.export_pdf(state["page"], path)
    finally:
        drawing_pdf_export.KEEP_PRINTED["path"] = None
        prefs.SetInt("PDFVersion", old)
    return path


# -- A --------------------------------------------------------------------------------------
DPI = 50


def render(path, name, dpi=DPI):
    if shutil.which("pdftoppm") is None:
        return None, ""
    prefix = os.path.join(OUT, name)
    run = subprocess.run(
        ["pdftoppm", "-r", str(dpi), "-png", "-singlefile", path, prefix],
        capture_output=True,
        timeout=180,
    )
    image = QtGui.QImage(prefix + ".png")
    return (None if image.isNull() else image), run.stderr.decode("utf-8", "replace")


def only(path, key, target):
    from sciforge import drawing_pdf_core
    from sciforge import drawing_pdf_objects as po

    doc = read(path)
    root = doc.get(doc.trailer[b"Root"])
    props = root[b"OCProperties"]
    ocgs = props[b"OCGs"]
    name = drawing_pdf_core.LAYER_NAMES[key]
    keep = [r for r in ocgs if po.decode_text_string(doc.get(r)[b"Name"]) == name]
    props[b"D"][b"ON"] = keep
    props[b"D"][b"OFF"] = [r for r in ocgs if r not in keep]
    with open(target, "wb") as handle:
        handle.write(doc.write())
    return target


def dark(image, x0, y0, x1, y1):
    """Dark pixels in a page rectangle (mm, y up)."""
    k = DPI / 25.4
    count = 0
    for px in range(int(x0 * k), int(x1 * k)):
        for py in range(int((297.0 - y1) * k), int((297.0 - y0) * k)):
            if QtGui.QColor(image.pixel(px, py)).lightness() < 160:
                count += 1
    return count


def a_normal():
    from sciforge import drawing

    path = export("normal")
    if not h.check("the PDF is written", os.path.isfile(path), os.listdir(OUT)):
        return
    info = summary(path)
    h.check("the centre lines layer is there", "Centerlines and Center Marks" in info["layers"], info["layers"])
    printed = os.path.getsize(os.path.join(OUT, "normal-printed.pdf"))
    size = os.path.getsize(path)
    # the added font subset, text and layers are a few tens of kilobytes; before the
    # review every page's old content stayed in the file too (about twice the size)
    h.check("not much bigger than TechDraw's print", size < printed * 1.25 + 30000, (size, printed))
    text = words(path)
    if text is not None:
        for word in ("ANGLE 30°15′20″", "⌀0.05", "⌖"):
            h.check("searchable: %s" % word, flat(word) in flat(text), text[-1500:])
    bx, by = drawing.view_position(base())
    wx, wy = drawing.view_position(state["below"])
    regions = {"hole": (bx - 9, by - 9, bx + 9, by + 9), "below": (wx - 32, wy - 12, wx + 32, wy + 12)}
    counts = {}
    for key in ("hidden", "centre"):
        image, _err = render(only(path, key, os.path.join(OUT, "only_%s.pdf" % key)), key)
        if image is None:
            print("[SciForge] pdftoppm not installed: the layers are not rendered", flush=True)
            return
        counts[key] = {r: dark(image, *box) for r, box in regions.items()}
    print("[SciForge] dark pixels per layer and region: %s" % counts, flush=True)
    h.check("the centre mark is on its own layer", counts["centre"]["hole"] > 5, counts)
    h.check("... not on Hidden Edges", counts["hidden"]["hole"] == 0, counts)
    h.check("the view below's hidden edges are hidden edges", counts["hidden"]["below"] > 5, counts)


a_normal.wait_ms = 3000


# -- B --------------------------------------------------------------------------------------
def red_pixels(image):
    count = 0
    for x in range(image.width()):
        for y in range(image.height()):
            c = QtGui.QColor(image.pixel(x, y))
            if c.red() > c.green() + 40 and c.red() > c.blue() + 40:
                count += 1
    return count


def metadata(doc):
    root = doc.get(doc.trailer[b"Root"])
    return doc.stream_data(root[b"Metadata"].num).decode("utf-8", "replace")


def b_pdfa():
    path = export("pdfa", 1)
    if not h.check("the PDF/A file is written", os.path.isfile(path), os.listdir(OUT)):
        return
    now = App.ParamGet(PREFS).GetInt("PDFVersion", 0)
    h.check("the PDF preference is put back", now == state["pdf_version"], now)
    info = summary(path)
    h.check("no layers in PDF/A-1", info["layers"] == [], info["layers"])
    doc = read(path)
    fonts = [
        (bytes(o[b"FontName"]).decode("latin-1"), b"CIDSet" in o)
        for o in doc.objects.values()
        if isinstance(o, dict) and o.get(b"Type") == b"FontDescriptor" and b"FontFile2" in o
    ]
    h.check("SciForge's osifont subset is there", any("osifont" in n for n, _h in fonts), fonts)
    h.check("every embedded font has a CIDSet", all(has for _n, has in fonts), fonts)
    packet = metadata(doc)
    for prop in ("pdfaid:part>1<", "pdfaid:conformance>B<", "xmpMM:DocumentID>", "pdf:Trapped>False<"):
        h.check("the XMP has %s" % prop, prop in packet, packet[-1500:])
    trapped = doc.get(doc.trailer[b"Info"]).get(b"Trapped")
    h.check("the document information says Trapped False too", trapped == b"False", trapped)
    h.check("PDF 1.4 still", doc.version == b"1.4", doc.version)
    from sciforge import drawing_pdf_core

    printed = read(os.path.join(OUT, "pdfa-printed.pdf"))
    for name, pdf in (("TechDraw's print", printed), ("the export", doc)):
        content = drawing_pdf_core.page_content(pdf, pdf.pages()[0])
        _out, _used, found = drawing_pdf_core.layer_content(content, {}, layers=False)
        state[name] = len(found)
    h.check("Qt painted the markers (opaque in PDF/A)", state["TechDraw's print"] > 0, state)
    h.check("no marker left in the export's content", state["the export"] == 0, state)
    image, err = render(path, "pdfa600", 600)
    if image is None:
        print("[SciForge] pdftoppm not installed: the PDF/A picture is not checked", flush=True)
        return
    h.check("poppler finds no syntax error", "Syntax Error" not in err, err[-800:])
    h.check("no marker left (no red pixel)", red_pixels(image) == 0, red_pixels(image))


b_pdfa.wait_ms = 3000


# -- C --------------------------------------------------------------------------------------
def c_pdfx():
    path = export("pdfx4", 3)
    if not h.check("the PDF/X-4 file is written", os.path.isfile(path), os.listdir(OUT)):
        return
    printed = metadata(read(os.path.join(OUT, "pdfx4-printed.pdf")))
    h.check("Qt wrote PDF/X-4", 'GTS_PDFXVersion="PDF/X-4"' in printed, printed[-800:])
    packet = metadata(read(path))
    found = re.search(r'xmpMM:DocumentID="([^"]+)"', printed)
    for prop in (
        "pdfxid:GTS_PDFXVersion>PDF/X-4<",
        "xmpMM:DocumentID>%s<" % (found.group(1) if found else "?"),
        "xmpMM:VersionID>",
        "xmpMM:RenditionClass>",
        "pdf:Trapped>False<",
    ):
        h.check("the XMP keeps %s" % prop, prop in packet, packet[-1500:])
    info = summary(path)
    h.check("layers in PDF/X-4", "Visible Edges" in info["layers"], info["layers"])
    h.check("no link annotations", info["links"] == [], info["links"])


c_pdfx.wait_ms = 3000


h.run(
    "drawing_pdf_archival",
    [new_design]
    + d.drawing_steps("sheet", base_at=BASE, scale="1:1", orientation="Top", style="Visible Edges")
    + [scripted, a_normal, b_pdfa, c_pdfx],
)
