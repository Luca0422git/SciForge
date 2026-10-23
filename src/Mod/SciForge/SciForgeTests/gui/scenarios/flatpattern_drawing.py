# SPDX-License-Identifier: LGPL-2.1-or-later
"""A drawing of a flat pattern (Fusion: Drawing > From Design with the flat pattern as the
view source), real input only: a U channel with a hole and its Flat Pattern (setup). File >
New Drawing; Contents Select lists "Flat Pattern / Body" (not ticked); tick it, untick the
body; OK: the drawing opens and its Base View shows the flat pattern from the top (the flat
lies on XY): the outline, the hole and the bend lines are its 11 visible edges; a click places
it; OK."""

import FreeCAD as App
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

s = {}


def setup():
    builder = fs.build("FlatDrawing", fs.U_STEPS, fs.TOP)
    builder.run({"op": "sf_flat_pattern", "id": "fp1", "face": fs.TOP, "measure": False})
    App.ActiveDocument.recompute()
    s["fp"] = builder.objects["fp1"].Name


def new_drawing():
    d.file_menu("New Drawing")


def _tick(widget, row):
    item = widget.item(row)
    rect = widget.visualItemRect(item)
    QtTest.QTest.mouseClick(
        widget.viewport(),
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
        QtCore.QPoint(rect.left() + 10, rect.center().y()),
    )
    QtWidgets.QApplication.processEvents()


def choose_select():
    p = d.panel_of("CreateDrawingPanel")
    if not h.check("Create Drawing dialog open", p is not None, d.panel()):
        return
    d.choose(p.contents, "Select")


def flat_listed():
    p = d.panel_of("CreateDrawingPanel")
    rows = [p.bodies.item(i).text() for i in range(p.bodies.count())] if p else []
    s["rows"] = rows
    h.check("the flat pattern is offered", "Flat Pattern / Body" in rows, rows)
    if "Flat Pattern / Body" not in rows:
        return
    i = rows.index("Flat Pattern / Body")
    h.check("not ticked by default", p.bodies.item(i).checkState() == QtCore.Qt.Unchecked)
    _tick(p.bodies, i)
    _tick(p.bodies, rows.index("Body"))


def ticked():
    p = d.panel_of("CreateDrawingPanel")
    chosen = [o.Name for o in p.chosen_bodies()] if p else []
    h.check("only the flat pattern chosen", chosen == [s["fp"]], chosen)


def press_ok():
    d.ok()


press_ok.wait_ms = 2000


def base_view_top():
    p = d.panel_of("BaseViewPanel")
    h.check("Base View dialog open", p is not None, d.panel())
    if p is not None:
        h.check("the flat pattern is drawn from the top", p.orientation.currentText() == "Top")


def place():
    d.click_at(200, 150)


place.wait_ms = 1500


def placed():
    bases = d.bases()
    h.check("a base view", len(bases) == 1, bases)
    if not bases:
        return
    view = bases[0]
    h.check("its source is the flat pattern", [o.Name for o in view.Source] == [s["fp"]])
    count = d.visible_edge_count(view)
    h.check("outline 4 + hole 1 + bend lines 6 = 11 visible edges", count == 11, count)
    h.shot("1-drawing")


def view_ok():
    d.ok()


def done():
    h.check("dialog closed", d.panel() is None)


h.run(
    "flatpattern_drawing",
    [
        setup,
        new_drawing,
        choose_select,
        flat_listed,
        ticked,
        press_ok,
        base_view_top,
        place,
        placed,
        view_ok,
        done,
    ],
)
