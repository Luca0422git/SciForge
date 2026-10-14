# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export PDF and Export DXF (EXPORT group of the DRAWING tab), with real clicks; the
files are read back and checked.

The filleted block (drawing_fixtures.block), ISO A3, base view Top at 1:1 at (130, 190):
the 12 mm hole is at the view's centre. Set up with real clicks: the bottom edge's
dimension (50) and a centre mark on the hole. Set up by script (the subject here is the
export): a section A-A through the hole at (230, 190) and a note "NOTE 1" at (60, 60).

A  EXPORT > Export PDF: the dialog (the drawing's name, Open afterwards ticked); the name
   and the folder typed; Export: the file is a one-page A3 PDF, it was opened, the dialog
   closed. Rendered (pdftoppm, when there): the paper is white, the cut faces of the
   section are hatched, the hole between them is not; the text has SECTION A-A.
B  EXPORT > Export DXF: Open afterwards not ticked; Export: the DXF has the hole as a
   circle (R6) at the view's centre on VISIBLE, the dimension 50 on DIMENSIONS, the centre
   mark's two lines (18 mm: 3 mm past the hole) on CENTER, the hatching (45 degree lines)
   on HATCH, the caption and the note on TEXT, the title on SHEET; it was not opened.
C  Export PDF with the name emptied: the dialog says to give a name and stays; Cancel:
   no file.
D  A second drawing in inches (ASME): the bottom edge's dimension reads 1.969, the title
   block says in; its DXF has 1.969.
"""

import math
import os
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
SECTION_AT = (230.0, 190.0)
OUT = os.path.join(d.OUT, "export")
state = {}


def new_design():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    state["opened"] = d.record_opener()
    s.new_design("Exp")()
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


def dxf_of(path):
    from sciforge import drawing_core as core

    with open(path, encoding="utf-8") as handle:
        return core.read_dxf_entities(handle.read())


def on(entities, kind, layer):
    return [e[1] for e in entities if e[0] == kind and e[1].get(8, [""])[0] == layer]


def num(entity, code):
    return float(entity[code][0])


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


def mark_start():
    h.ribbon("Center Mark")


def mark_pick():
    d.click_at(*at(0, 6))


mark_pick.wait_ms = 1000


def mark_end():
    d.key(QtCore.Qt.Key_Return)


def scripted():
    from sciforge import drawing

    h.check("the dimension is there", len(dims()) == 1, dims())
    h.check("the centre mark is there", len(drawing.center_marks(base())) == 1)
    page = d.page()
    state["section"] = drawing.add_section(base(), (0, 26), (0, -26), (10, 0), SECTION_AT)
    drawing.add_text(page, ["NOTE 1"], (60.0, 60.0))
    page.Document.recompute()


scripted.wait_ms = 3000


def dims():
    from sciforge import drawing

    page = d.page()
    return [o for o in drawing.annotations(page) if o.TypeId == drawing.DIMENSION] if page else []


# -- A ------------------------------------------------------------------------------------------
def a_command():
    h.check("the section has its hatching", state["section"].CutSurfaceDisplay == "PatHatch")
    h.ribbon("Export PDF")


def a_dialog():
    dlg = dialog()
    if not h.check("the Export PDF dialog", dlg is not None):
        return
    h.check("named after the drawing", dlg.name.text() == d.page().Label, dlg.name.text())
    h.check("Open afterwards ticked", dlg.open_after.isChecked())
    d.type_into(dlg.name, "exp_sheet")
    d.type_into(dlg.folder, OUT)
    click(dlg.export_button)


a_dialog.wait_ms = 2500


def render(path, dpi):
    """The PDF as an image (None when pdftoppm is not installed)."""
    if shutil.which("pdftoppm") is None:
        return None
    prefix = os.path.join(OUT, "render")
    subprocess.run(
        ["pdftoppm", "-r", str(dpi), "-png", "-singlefile", path, prefix],
        capture_output=True,
        timeout=60,
    )
    image = QtGui.QImage(prefix + ".png")
    return None if image.isNull() else image


def dark_share(image, dpi, x0, y0, x1, y1):
    """The share of dark pixels in a page rectangle (mm, y up)."""
    height_mm = 297.0
    k = dpi / 25.4
    dark = total = 0
    for px in range(int(x0 * k), int(x1 * k)):
        for py in range(int((height_mm - y1) * k), int((height_mm - y0) * k)):
            c = QtGui.QColor(image.pixel(px, py))
            total += 1
            if c.lightness() < 200:
                dark += 1
    return dark / float(total or 1)


def a_written():
    path = os.path.join(OUT, "exp_sheet.pdf")
    h.check("the dialog closed", dialog() is None)
    if not h.check("the PDF is written", os.path.isfile(path), os.listdir(OUT)):
        return
    with open(path, "rb") as handle:
        head = handle.read(5)
    h.check("it is a PDF", head == b"%PDF-", head)
    h.check("it was opened", state["opened"] == [path], state["opened"])
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", path], capture_output=True, text=True).stdout
        h.check("one page", "Pages:           1" in info, info)
        h.check("A3", "(A3)" in info, info)
    dpi = 150
    image = render(path, dpi)
    if image is None:
        print("[SciForge] pdftoppm not installed: the PDF picture is not checked", flush=True)
        return
    paper = QtGui.QColor(image.pixel(int(300 * dpi / 25.4), int((297 - 100) * dpi / 25.4)))
    h.check("the paper is white", paper.lightness() >= 254, paper.name())
    from sciforge import drawing

    x, y = drawing.view_position(state["section"])
    cut = dark_share(image, dpi, x - 8, y + 8, x + 8, y + 18)
    hole = dark_share(image, dpi, x - 8, y + 1.5, x + 8, y + 4.5)  # (between its lines)
    blank = dark_share(image, dpi, 300, 120, 340, 150)
    h.check("the cut faces are hatched", cut > 0.04, cut)
    h.check("the hole is not", hole < 0.01, (hole, cut))
    h.check("empty paper is empty", blank == 0.0, blank)
    if shutil.which("pdftotext"):
        text = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True).stdout
        h.check("the PDF has SECTION A-A", "SECTION A-A" in text, text)


# -- B ------------------------------------------------------------------------------------------
def b_command():
    h.ribbon("Export DXF")


def b_dialog():
    dlg = dialog()
    if not h.check("the Export DXF dialog", dlg is not None and dlg.kind == "dxf"):
        return
    h.check("Open afterwards not ticked", not dlg.open_after.isChecked())
    d.type_into(dlg.name, "exp_sheet")
    d.type_into(dlg.folder, OUT)
    click(dlg.export_button)


b_dialog.wait_ms = 2000


def b_written():
    path = os.path.join(OUT, "exp_sheet.dxf")
    if not h.check("the DXF is written", os.path.isfile(path), os.listdir(OUT)):
        return
    h.check("it was not opened", len(state["opened"]) == 1, state["opened"])
    from sciforge import drawing

    entities = dxf_of(path)
    bx, by = drawing.view_position(base())  # (where the click put it)
    holes = [
        c
        for c in on(entities, "CIRCLE", "VISIBLE")
        if abs(num(c, 40) - 6.0) < 1e-3
        and abs(num(c, 10) - bx) < 1e-3
        and abs(num(c, 20) - by) < 1e-3
    ]
    h.check("the hole: a circle R6 at the view's centre", len(holes) == 1, len(holes))
    texts = [t[1][0] for t in on(entities, "TEXT", "DIMENSIONS")]
    h.check("the dimension 50", "50" in texts, texts)
    centre = on(entities, "LINE", "CENTER")
    crossing = [
        e
        for e in centre
        if abs((num(e, 10) + num(e, 11)) / 2 - bx) < 1e-3
        and abs((num(e, 20) + num(e, 21)) / 2 - by) < 1e-3
        and abs(math.hypot(num(e, 11) - num(e, 10), num(e, 21) - num(e, 20)) - 18.0) < 1e-3
    ]
    h.check("the centre mark: two lines across the hole", len(crossing) == 2, len(crossing))
    hatch = on(entities, "LINE", "HATCH")
    slopes = {
        round((num(e, 21) - num(e, 20)) / ((num(e, 11) - num(e, 10)) or 1e-9), 6) for e in hatch
    }
    h.check("the hatching: 45 degree lines", len(hatch) >= 8 and slopes == {1.0}, slopes)
    x, y = drawing.view_position(state["section"])  # (lined up with the base view)
    inside = all(
        x - 10 - 1e-6 <= num(e, k) <= x + 10 + 1e-6
        and (6 - 1e-6 <= abs(num(e, k + 10) - y) <= 20 + 1e-6)
        for e in hatch
        for k in (10, 11)
    )
    h.check("... on the cut faces only (not in the hole)", inside)
    words = [t[1][0] for t in on(entities, "TEXT", "TEXT")]
    h.check("the caption", "SECTION A-A" in words, words)
    h.check("the note", "NOTE 1" in words, words)
    sheet = [t[1][0] for t in on(entities, "TEXT", "SHEET")]
    h.check("the title block's title", "Exp" in sheet, sheet)


# -- C ------------------------------------------------------------------------------------------
def c_command():
    state["files"] = sorted(os.listdir(OUT))
    h.ribbon("Export PDF")


def c_empty():
    dlg = dialog()
    if not h.check("the dialog", dlg is not None):
        return
    dlg.name.setFocus()
    QtTest.QTest.keyClick(dlg.name, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClick(dlg.name, QtCore.Qt.Key_Delete)
    click(dlg.export_button)


def c_says():
    dlg = dialog()
    h.check("it stays", dlg is not None)
    h.check(
        "says to give a name",
        dlg is not None and "name" in dlg.message.text().lower(),
        dlg and dlg.message.text(),
    )
    if dlg is not None:
        for button in dlg.findChildren(QtCore.QObject):
            if getattr(button, "text", None) and callable(button.text):
                try:
                    if button.text().replace("&", "") == "Cancel":
                        click(button)
                        return
                except Exception:
                    pass


def c_nothing():
    h.check("Cancel closes it", dialog() is None)
    h.check("no new file", sorted(os.listdir(OUT)) == state["files"], os.listdir(OUT))


# -- D ------------------------------------------------------------------------------------------
def d_check_units():
    from sciforge import drawing

    page = d.page()
    h.check("the drawing is in inches", drawing.units_of(page) == "in", drawing.units_of(page))
    h.check("ASME", drawing.standard_of(page) == "ASME", drawing.standard_of(page))
    h.check(
        "the title block says in", drawing.title(page).get("Units") == "in", drawing.title(page)
    )


def d_dim():
    found = dims()
    if not h.check("one dimension on the inch drawing", len(found) == 1, found):
        return
    from sciforge import drawing

    dim = found[0]
    h.check("its value is 50 mm", abs(drawing.dimension_value(dim) - 50.0) < 1e-6)
    h.check("it reads 1.969", drawing.dimension_text(dim) == "1.969", drawing.dimension_text(dim))
    h.check("... on the sheet", dim.Arbitrary and dim.FormatSpec == "1.969", dim.FormatSpec)
    h.shot("d-inches")
    h.ribbon("Export DXF")


def d_dialog():
    dlg = dialog()
    if not h.check("the Export DXF dialog", dlg is not None):
        return
    d.type_into(dlg.name, "exp_inches")
    d.type_into(dlg.folder, OUT)
    click(dlg.export_button)


d_dialog.wait_ms = 2000


def d_written():
    path = os.path.join(OUT, "exp_inches.dxf")
    if not h.check("the inch DXF is written", os.path.isfile(path), os.listdir(OUT)):
        return
    texts = [t[1][0] for t in on(dxf_of(path), "TEXT", "DIMENSIONS")]
    h.check("its dimension reads 1.969", "1.969" in texts, texts)


h.run(
    "drawing_export",
    [new_design]
    + d.drawing_steps("sheet", base_at=BASE, scale="1:1", orientation="Top", style="Visible Edges")
    + [dim_start, dim_pick, dim_place, dim_end, mark_start, mark_pick, mark_end, scripted]
    + [a_command, a_dialog, a_written, b_command, b_dialog, b_written]
    + [c_command, c_empty, c_says, c_nothing]
    + d.drawing_steps(
        "inches",
        standard="ASME",
        units="in",
        base_at=BASE,
        scale="1:1",
        orientation="Top",
        style="Visible Edges",
    )
    + [d_check_units, dim_start, dim_pick, dim_place, dim_end, d_dim, d_dialog, d_written],
)
