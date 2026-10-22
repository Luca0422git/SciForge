# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export PDF writes a better PDF (drawing_pdf_core.py): layers a PDF viewer can switch,
searchable text over the title block and SciForge's SVG annotations, links, metadata, and
several sheets of their own sizes in one file. Real clicks for the drawing, the dimension
and the Export PDF dialog; the PDF is read back and checked.

The filleted block (drawing_fixtures.block), ISO A3, base view Top at 1:1 at (130, 190).
By real clicks: the bottom edge's dimension (50). By script (the subject is the export):
a projected view below it with hidden edges at (130, 120), a section A-A at (230, 190), a
centre mark on the hole, a note with a URL at (60, 60), a leader note (an SVG annotation:
outlines in TechDraw's PDF) with a URL at (60, 40), a parts list at (20, 280), the title
block's Description and Drawn By typed.

A  EXPORT > Export PDF, a name, Export: one A3 page; the six layers, in order; title,
   author, subject from the title block, SciForge as the creator, its XMP too; osifont
   embedded as a subset; the title block, the leader note and the parts list are
   searchable, the dimension "50" is there once (Qt prints it as text: not added twice);
   both URLs are links. No marker is left in TechDraw's scene, nothing went into Undo.
B  Rendered (pdftoppm): with every layer on, the page looks exactly like TechDraw's own
   print of the sheet; with one layer on, only its things show (the projected view's
   hidden edges, the base view's outline, the centre mark, the section's hatching, the
   notes, the title block), each where it belongs and nothing where the others are.
C  A second sheet, A4 (by script: SciForge's Sheet Bar makes sheets of the first one's
   size), with a base view and a projection group (FreeCAD's TechDraw makes those; made by
   script, TechDraw draws its two views at the sheet's bottom left corner, not inside the
   group's item); markers go into the group and its views and all come out again; Export
   PDF of All Sheets: two pages, A3 then A4, one set of layers, the second sheet's title
   block searchable ("2 / 2").
"""

import os
import re
import shutil
import subprocess

import FreeCAD as App
from PySide import QtCore, QtGui
from PySide6 import QtTest

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

BASE = (130.0, 190.0)
BELOW = (130.0, 120.0)
SECTION_AT = (230.0, 190.0)
NOTE_AT = (60.0, 60.0)
LEADER_AT = (60.0, 40.0)
TABLE_AT = (20.0, 285.0)
OUT = os.path.join(d.OUT, "pdf_layers")
state = {}


def new_design():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    state["opened"] = d.record_opener()
    s.new_design("Bracket")()
    fx.block(App.ActiveDocument)
    h.fit()


def base():
    return d.bases()[0]


def at(u, v):
    from sciforge import drawing

    return drawing.local_to_page(base(), (u, v))


def dialog():
    from sciforge import drawing_ui

    dlg = drawing_ui.ExportDialog.last
    return dlg if dlg is not None and dlg.isVisible() else None


def click(widget):
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton)
    QtCore.QCoreApplication.processEvents()


# -- the drawing ----------------------------------------------------------------------------
def dim_start():
    h.ribbon("Dimension")


def dim_pick():
    d.click_at(*at(0, -20))
    d.move_to(*at(2, -30))


dim_pick.wait_ms = 1000


def dim_place():
    d.click_at(*at(0, -32))


dim_place.wait_ms = 1000


def dim_end():
    d.key(QtCore.Qt.Key_Escape)


def scripted():
    from sciforge import drawing, drawing_annot

    page = d.page()
    state["page"] = page
    below = drawing.add_projected(base(), "Bottom", *BELOW)
    drawing._style(below, "Visible and Hidden Edges")
    state["below"] = below
    state["section"] = drawing.add_section(base(), (0, 26), (0, -26), (10, 0), SECTION_AT)
    drawing._make_mark(base(), (0.0, 0.0), fx.HOLE_R)
    drawing.add_text(page, ["NOTE 1", "SPEC https://example.com/spec"], NOTE_AT)
    drawing_annot.add_annotation(
        page,
        {
            "kind": "leader",
            "lines": ["DEBURR ALL EDGES", "see www.sciforge.org/finish"],
            "off": list(LEADER_AT),
        },
    )
    drawing.add_parts_list(page, base(), TABLE_AT, balloons=False)
    drawing.set_title(page, {"Description": "Mounting block", "DrawnBy": "Luca"})
    page.Document.recompute()


scripted.wait_ms = 4000


def dims():
    from sciforge import drawing

    page = d.page()
    return [o for o in drawing.annotations(page) if o.TypeId == drawing.DIMENSION] if page else []


# -- A --------------------------------------------------------------------------------------
def a_command():
    h.check("the dimension is there", len(dims()) == 1, dims())
    state["undo"] = App.ActiveDocument.UndoCount
    from sciforge import drawing_pdf_export

    drawing_pdf_export.KEEP_PRINTED["path"] = os.path.join(OUT, "printed.pdf")
    h.ribbon("Export PDF")


def a_dialog():
    dlg = dialog()
    if not h.check("the Export PDF dialog", dlg is not None):
        return
    d.type_into(dlg.name, "layers")
    d.type_into(dlg.folder, OUT)
    click(dlg.export_button)


a_dialog.wait_ms = 4000


def summary(path):
    from sciforge import drawing_pdf_core

    with open(path, "rb") as handle:
        return drawing_pdf_core.summary(handle.read())


def words(path, first=None):
    if shutil.which("pdftotext") is None:
        return None
    cmd = ["pdftotext"] + (["-f", str(first), "-l", str(first)] if first else []) + [path, "-"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout


def flat(text):
    """Text without its spaces (pdftotext guesses them from the gaps)."""
    return "".join(text.split())


def a_written():
    from sciforge import drawing_pdf_core, drawing_pdf_export

    path = os.path.join(OUT, "layers.pdf")
    h.check("the dialog closed", dialog() is None)
    if not h.check("the PDF is written", os.path.isfile(path), os.listdir(OUT)):
        return
    state["path"] = path
    info = summary(path)
    h.check("one A3 page", info["pages"] == [[0, 0, 1191, 842]], info["pages"])
    names = [n for _k, n in drawing_pdf_core.LAYERS]
    h.check("the six layers, in order", info["layers"] == names, info["layers"])
    meta = info["info"]
    h.check("title from the title block", meta.get("Title") == "Bracket", meta)
    h.check("author: Drawn By", meta.get("Author") == "Luca", meta)
    h.check("subject: the description", "Mounting block" in meta.get("Subject", ""), meta)
    h.check("SciForge made it", meta.get("Creator", "").startswith("SciForge "), meta)
    with open(path, "rb") as handle:
        raw = handle.read()
    h.check("the XMP says so too", b"<xmp:CreatorTool>SciForge" in raw)
    h.check(
        "osifont embedded as a subset",
        any(re.match(r"[A-Z]{6}\+osifont", f) for f in info["fonts"]),
        info["fonts"],
    )
    h.check(
        "both URLs are links",
        "https://example.com/spec" in info["links"]
        and "http://www.sciforge.org/finish" in info["links"],
        info["links"],
    )
    text = words(path)
    if text is None:
        print("[SciForge] pdftotext not installed: the PDF's text is not checked", flush=True)
    else:
        for word in (
            "DRAWN BY",
            "Mounting block",
            "Luca",
            "SECTION A-A",
            "NOTE 1",
            "DEBURR ALL EDGES",
            "QTY",
            "Body1",
            "1 / 1",
        ):
            h.check("searchable: %s" % word, flat(word) in flat(text), text[-2000:])
        h.check("the dimension 50 once", len(re.findall(r"(?<![\d.])50(?![\d.])", text)) == 1, text)
    page = state["page"]
    scene = drawing_pdf_export.scene_of(page)
    marker = drawing_pdf_export._marker_class().TYPE
    left = [i for i in scene.items() if i.type() == marker]
    h.check("no marker left in TechDraw's scene", not left, len(left))
    h.check(
        "nothing went into Undo",
        App.ActiveDocument.UndoCount == state["undo"],
        (App.ActiveDocument.UndoCount, state["undo"]),
    )


# -- B --------------------------------------------------------------------------------------
DPI = 50


def render(path, name):
    if shutil.which("pdftoppm") is None:
        return None
    prefix = os.path.join(OUT, name)
    subprocess.run(
        ["pdftoppm", "-r", str(DPI), "-png", "-singlefile", path, prefix],
        capture_output=True,
        timeout=120,
    )
    image = QtGui.QImage(prefix + ".png")
    return None if image.isNull() else image


def only(path, key, target):
    """A copy of the PDF with every layer off but `key`."""
    from sciforge import drawing_pdf_core
    from sciforge import drawing_pdf_objects as po

    with open(path, "rb") as handle:
        doc = po.read(handle.read())
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


def b_rendered():
    from sciforge import drawing

    path = state.get("path")
    if not path:
        return
    from sciforge import drawing_pdf_export

    drawing_pdf_export.KEEP_PRINTED["path"] = None
    printed = os.path.join(OUT, "printed.pdf")
    plain = os.path.join(OUT, "plain.pdf")
    drawing.print_pdf(state["page"], plain)  # a print without markers
    ours, theirs, again = render(path, "ours"), render(printed, "printed"), render(plain, "plain")
    if ours is None or theirs is None or again is None:
        print("[SciForge] pdftoppm not installed: the PDF's pictures are not checked", flush=True)
        return

    def differ(a, b):
        return sum(
            1 for x in range(a.width()) for y in range(a.height()) if a.pixel(x, y) != b.pixel(x, y)
        )

    h.check(
        "every layer on: exactly what TechDraw printed",
        differ(ours, theirs) == 0,
        differ(ours, theirs),
    )
    # the markers change nothing either. Two prints of one sheet by TechDraw can differ in
    # a few anti-aliased pixels of SVG text (2026-10-22: 272 of 340000 between two prints
    # without markers, while a print with markers and the next one without were identical)
    h.check("... and like a print without markers", differ(ours, again) < 1000, differ(ours, again))
    bx, by = drawing.view_position(base())
    wx, wy = drawing.view_position(state["below"])
    sx, sy = drawing.view_position(state["section"])
    regions = {
        "base": (bx - 32, by - 22, bx + 32, by + 22),
        "below": (wx - 32, wy - 12, wx + 32, wy + 12),
        "section": (sx - 12, sy - 22, sx + 12, sy + 22),
        "notes": (NOTE_AT[0] - 30, LEADER_AT[1] - 8, NOTE_AT[0] + 40, NOTE_AT[1] + 6),
        "title": (290, 15, 405, 45),
        "hole": (bx - 9, by - 9, bx + 9, by + 9),
    }
    images = {}
    for key in ("visible", "hidden", "centre", "hatching", "annotations", "border"):
        images[key] = render(only(path, key, os.path.join(OUT, "only_%s.pdf" % key)), key)
    counts = {k: {r: dark(img, *box) for r, box in regions.items()} for k, img in images.items()}
    print("[SciForge] dark pixels per layer and region: %s" % counts, flush=True)
    c = counts
    h.check(
        "visible edges: the views' outlines",
        c["visible"]["base"] > 50
        and c["visible"]["below"] > 30
        and c["visible"]["title"] == 0
        and c["visible"]["notes"] == 0,
        c["visible"],
    )
    h.check(
        "hidden edges: in the view below only",
        c["hidden"]["below"] > 5 and c["hidden"]["base"] == 0 and c["hidden"]["title"] == 0,
        c["hidden"],
    )
    h.check(
        "centre lines and marks: the hole's mark only",
        c["centre"]["hole"] > 5 and c["centre"]["below"] == 0 and c["centre"]["title"] == 0,
        c["centre"],
    )
    h.check(
        "hatching and section lines: the section",
        c["hatching"]["section"] > 20
        and c["hatching"]["below"] == 0
        and c["hatching"]["title"] == 0,
        c["hatching"],
    )
    h.check(
        "dimensions and annotations: the notes",
        c["annotations"]["notes"] > 20
        and c["annotations"]["title"] == 0
        and c["annotations"]["below"] == 0,
        c["annotations"],
    )
    h.check(
        "border and title block: the title block only",
        c["border"]["title"] > 100 and c["border"]["base"] == 0 and c["border"]["below"] == 0,
        c["border"],
    )


b_rendered.wait_ms = 2000


# -- C --------------------------------------------------------------------------------------
def c_sheet():
    from sciforge import drawing, drawing_sheets

    page = state["page"]
    sheet = drawing_sheets.add_sheet(page)
    drawing._add(sheet, "App::PropertyString", "SciForgeSheet", "A4")
    sheet.Template.Template = drawing.template_file("ISO", "A4")
    sheet.Document.recompute()
    drawing.add_base_view(
        sheet, drawing.design_bodies(sheet.Document), 100.0, 120.0, orientation="Top", scale=1.0
    )
    # a projection group (FreeCAD's own TechDraw makes them; SciForge reads them): its
    # views are items inside the group's item in TechDraw's scene
    group = sheet.Document.addObject(drawing.GROUP, "ProjGroup")
    sheet.addView(group)
    group.Source = drawing.design_bodies(sheet.Document)
    group.addProjection("Front")
    group.addProjection("Right")
    group.X, group.Y = 200.0, 120.0
    group.ScaleType = "Custom"
    group.Scale = 1.0
    state["group"] = group
    drawing_sheets.refresh_titles(page)
    sheet.Document.recompute()
    state["sheet"] = sheet
    from sciforge import drawing_ui

    drawing_ui.open_drawing(page)


c_sheet.wait_ms = 5000


def c_command():
    from sciforge import drawing_pdf_export

    sheet = state["sheet"]
    h.check("the second sheet is A4", sheet.Template.Width.Value == 297.0, sheet.Template.Width)
    group_views = [v.Name for v in state["group"].Views]
    h.check("the group has its two views", len(group_views) == 2, group_views)
    scene = drawing_pdf_export.scene_of(sheet)
    markers, codes, _hidden = drawing_pdf_export.add_markers(sheet, scene)
    marked = {key for key, _kind, _band in codes.values()}
    drawing_pdf_export.remove_markers(markers)
    h.check(
        "markers for the group and the views inside it",
        set(group_views) | {state["group"].Name} <= marked,
        (marked, group_views),
    )
    left = [i for i in scene.items() if i.type() == drawing_pdf_export._marker_class().TYPE]
    h.check("... and none left", not left, len(left))
    h.ribbon("Export PDF")


def c_dialog():
    dlg = dialog()
    if not h.check("the Export PDF dialog", dlg is not None):
        return
    h.check("All Sheets", dlg.sheets.currentIndex() == 0)
    d.type_into(dlg.name, "both")
    d.type_into(dlg.folder, OUT)
    click(dlg.export_button)


c_dialog.wait_ms = 6000


def c_written():
    from sciforge import drawing_pdf_core

    path = os.path.join(OUT, "both.pdf")
    if not h.check("the two-sheet PDF is written", os.path.isfile(path), os.listdir(OUT)):
        return
    info = summary(path)
    h.check(
        "two pages: A3, then A4",
        info["pages"] == [[0, 0, 1191, 842], [0, 0, 842, 595]],
        info["pages"],
    )
    h.check(
        "one set of layers",
        info["layers"] == [n for _k, n in drawing_pdf_core.LAYERS],
        info["layers"],
    )
    leftovers = [f for f in os.listdir(OUT) if f.endswith(".tmp.pdf")]
    h.check("no part files left", not leftovers, leftovers)
    text = words(path, 2)
    if text is not None:
        h.check(
            "the A4 sheet's title block is searchable",
            "2/2" in flat(text) and "A4" in text,
            text[-1500:],
        )


h.run(
    "drawing_pdf_layers",
    [new_design]
    + d.drawing_steps("sheet", base_at=BASE, scale="1:1", orientation="Top", style="Visible Edges")
    + [dim_start, dim_pick, dim_place, dim_end, scripted]
    + [a_command, a_dialog, a_written, b_rendered]
    + [c_sheet, c_command, c_dialog, c_written],
)
