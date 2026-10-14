# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tolerances, annotations, sheets and the new sections are saved with the design and
come back whole; they still undo and follow the design after reopening, with real
clicks.

The plate (drawing_fixtures.plate), ISO A3, base view Top at 1:1; set up by script
(drawing2_steps.furnish: the subject here is save and reopen) with a toleranced
dimension, an ordinate, a leader, a feature control frame, a datum, a surface texture,
automated centre marks, an edge extension, an arc length, a Slice section and an offset
section; then, with clicks, a second sheet (the sheet bar's +) renamed "Notes" by script.

A  Ctrl+S on the sheet: the Save dialog; name "Reo2" and the folder typed; Save.
B  The design closed and opened again (by script, as drawing_reopen does); the browser's
   Drawings folder lists one drawing; a double-click opens it: the sheet bar has
   "Sheet 1" and "Notes"; every annotation is back with what it says; the dimension's
   limits; the Slice section's trimmed copy and the offset section's cut line; the
   automated marks and the edge extension; the title blocks 1 / 2 and 2 / 2.
C  Double-click the dimension: Display Class: "10 H7"; OK; Ctrl+Z: the limits again;
   Ctrl+Y: the class.
D  Hole 2 moved 5 mm right (by script): the frame's leader follows it.
"""

import os
import shutil

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing2_steps as w
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as wi

OUT = os.path.join(d.OUT, "reopen2")
DIA = w.DIA
state = {}


def clean():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)


def doc():
    return App.ActiveDocument


def obj(key):
    return doc().getObject(state["made"][key])


def setup():
    state["made"] = w.furnish()
    state["label"] = d.page().Label
    state["main"] = d.page().Name


setup.wait_ms = 4000


def plus():
    from sciforge import drawing_sheets_ui

    bar = drawing_sheets_ui.bar_of(d.page())
    if h.check("the sheet bar", bar is not None):
        wi.click(bar.plus)


plus.wait_ms = 2500


def rename():
    from sciforge import drawing_sheets

    page = d.page()
    h.check("on the new sheet", page.Name != state["main"])
    state["notes"] = page.Name
    doc().openTransaction("Rename Sheet")
    drawing_sheets.rename_sheet(page, "Notes")
    doc().commitTransaction()


def before():
    from sciforge import drawing_annot

    state["said"] = {
        key: w.describe(obj(key)) for key in ("leader", "fcf", "datum", "texture", "arc")
    }
    state["ordinate"] = round(drawing_annot.ordinate_value(obj("ordinate")), 3)
    h.check("the ordinate 20", state["ordinate"] == 20.0)


# -- A ------------------------------------------------------------------------------------------
def a_save():
    d.click_at(380, 250)
    d.key(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


a_save.wait_ms = 1500


def a_dialog():
    if h.check("Ctrl+S on the sheet: the Save dialog", vi.save_dialog() is not None, h.popups()):
        vi.fill_save_dialog(name="Reo2", location=OUT)
        vi.click_save()


a_dialog.wait_ms = 4000


def a_saved():
    state["file"] = os.path.join(OUT, "Reo2.FCStd")
    h.check("Reo2.FCStd written", os.path.isfile(state["file"]), os.listdir(OUT))


# -- B ------------------------------------------------------------------------------------------
def b_close():
    App.closeDocument(doc().Name)


b_close.wait_ms = 1500


def b_open():
    App.openDocument(state["file"])


b_open.wait_ms = 5000


def b_browser():
    from sciforge import drawing

    h.check(
        "one drawing",
        len(drawing.drawings(doc())) == 1,
        [p.Label for p in drawing.all_pages(doc())],
    )
    tree = s.browser()
    item = tree.row(state["label"])
    if h.check("browser row of the drawing", item is not None, tree.labels()):
        wi.double_click(tree.viewport(), tree.label_point(item))


b_browser.wait_ms = 5000


def b_whole():
    from sciforge import drawing, drawing_annot, drawing_sheets_ui

    page = d.page()
    if not h.check("the drawing's tab", page is not None and page.Name == state["main"], page):
        return
    bar = drawing_sheets_ui.bar_of(page)
    texts = [bar.tabs.tabText(i) for i in range(bar.tabs.count())] if bar else []
    h.check("the sheet bar: Sheet 1 and Notes", texts == ["Sheet 1", "Notes"], texts)
    for key, said in state["said"].items():
        h.check(
            "%s says the same" % key, w.describe(obj(key)) == said, (w.describe(obj(key)), said)
        )
    h.check(
        "the ordinate",
        round(drawing_annot.ordinate_value(obj("ordinate")), 3) == state["ordinate"],
    )
    h.check(
        "the limits",
        obj("dim").FormatSpec == DIA + "10.015\n" + DIA + "10.000",
        obj("dim").FormatSpec,
    )
    clip = obj("slice").SciForgeDepthClip
    h.check("the slice's copy", clip is not None and clip.Shape.Volume > 0)
    h.check("the slice cuts it", [x.Name for x in obj("slice").Source] == [clip.Name])
    profile = obj("offset").CuttingToolWireObject
    h.check("the offset section's cut line", profile is not None and len(profile.Geometry) == 3)
    h.check(
        "both sections drawn",
        len(obj("slice").getVisibleEdges()) > 0 and len(obj("offset").getVisibleEdges()) > 0,
    )
    h.check("the automated marks", len(drawing.auto_marks_of(w.base()).get("marks", [])) == 2)
    h.check("the edge extension", len(drawing.extensions_of(w.base())) == 1)
    h.check("1 / 2", drawing.title(page).get("Sheet") == "1 / 2", drawing.title(page).get("Sheet"))
    notes = doc().getObject(state["notes"])
    h.check(
        "2 / 2", drawing.title(notes).get("Sheet") == "2 / 2", drawing.title(notes).get("Sheet")
    )
    import FreeCADGui as Gui

    h.check("looking at it changed nothing", not Gui.getDocument(doc().Name).Modified)
    h.shot("b-reopened")


b_whole.wait_ms = 1500


# -- C ------------------------------------------------------------------------------------------
def c_open():
    d.double_click_at(*w.label_point(obj("dim")))


c_open.wait_ms = 1500


def c_class():
    p = d.panel_of("DimensionEditPanel")
    if not h.check("the Dimension dialog", p is not None, d.panel()):
        return
    h.check(
        "its fit came back",
        p.tolerance.currentText() == "Fit" and p.display.currentText() == "Limits",
    )
    d.choose(p.display, "Class")


def c_ok():
    h.check("10 H7", obj("dim").FormatSpec == DIA + "10 H7", obj("dim").FormatSpec)
    d.ok()


c_ok.wait_ms = 1500


def c_undo():
    d.undo()


c_undo.wait_ms = 1500


def c_undone():
    h.check(
        "undo: the limits", obj("dim").FormatSpec.startswith(DIA + "10.015"), obj("dim").FormatSpec
    )
    d.redo()


c_undone.wait_ms = 1500


def c_redone():
    h.check("redo: the class", obj("dim").FormatSpec == DIA + "10 H7", obj("dim").FormatSpec)


# -- D ------------------------------------------------------------------------------------------
def d_move():
    hole = doc().getObject("Hole2")
    hole.Placement.Base = App.Vector(65.0, 35.0, 0)
    doc().recompute()


d_move.wait_ms = 4000


def d_followed():
    from sciforge import drawing_annot

    sig = drawing_annot.annotation_data(obj("fcf"))["anchor"]["sig"]
    h.check("the frame follows hole 2", abs(sig[0] - 25.0) < 1e-3, sig)


h.run(
    "drawing2_reopen",
    [clean, w.new_design("Reo2")]
    + w.sheet_steps()
    + [d.wait_geometry(2000), setup, d.wait_geometry(2000), plus, rename, before]
    + [a_save, a_dialog, a_saved]
    + [b_close, b_open, b_browser, b_whole]
    + [c_open, c_class, c_ok, c_undo, c_undone, c_redone]
    + [d_move, d_followed],
)
