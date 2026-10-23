# SPDX-License-Identifier: LGPL-2.1-or-later
"""A drawing of a flat pattern (Fusion: Drawing > From Design with the flat pattern as the
view source), real input only: a U channel with a hole and its Flat Pattern (setup). File >
New Drawing; Contents Select lists "Flat Pattern / Body" (not ticked); tick it, untick the
body; OK: the drawing opens and its Base View shows the flat pattern from the top (the flat
lies on XY): the outline, the hole and the bend lines are its 11 visible edges; a click places
it; OK. TABLES > Bend Table: a table of the two bends (B1, B2: UP, 90 degrees, R 1.00, K 0.44)
and an identifier balloon on each bend centre line; undo / redo; the design's rule set to K
0.33: the table and the identifiers follow."""

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


def bend_table():
    d.group_menu("TABLES", "Bend Table")


bend_table.wait_ms = 1500


def table_made():
    from sciforge import drawing, flatpattern_drawing as fpd

    page = d.page()
    table = fpd.bend_table_of(page) if page is not None else None
    h.check("a bend table on the drawing", table is not None)
    if table is None:
        return
    rows = drawing.table_rows(table)
    h.check("two bends: B1, B2", [r["Item"] for r in rows] == ["B1", "B2"], rows)
    h.check(
        "both up, 90 degrees, R 1.00, K 0.44",
        all(
            r["Direction"] == "UP"
            and r["Angle"] == "90\u00b0"
            and r["Radius"] == "1.00"
            and r["KFactor"] == "0.44"
            for r in rows
        ),
        rows,
    )
    balloons = [b for b in d.of_type("TechDraw::DrawViewBalloon")]
    h.check(
        "an identifier on each bend",
        sorted(b.Text for b in balloons) == ["B1", "B2"],
        [b.Text for b in balloons],
    )
    for b in balloons:
        ox, oy = b.OriginX.Value, b.OriginY.Value
        # the U's bend centre lines are 28 + BA/2 from each end: 29.131 from the middle
        h.check(
            "%s points at the middle of its bend centre line" % b.Text,
            abs(abs(ox) - (58.26195 - 28 - fs.BA / 2)) < 0.01 and abs(oy) < 0.01,
            (ox, oy),
        )
        h.check("%s sits above the flat" % b.Text, b.Y.Value > 10.0, b.Y.Value)
    h.shot("2-bend-table")


def undo_table():
    d.undo()


def table_undone():
    from sciforge import flatpattern_drawing as fpd

    h.check("undo takes the bend table away", fpd.bend_table_of(d.page()) is None)


def redo_table():
    d.redo()


def table_redone():
    from sciforge import flatpattern_drawing as fpd

    h.check("redo brings it back", fpd.bend_table_of(d.page()) is not None)


def change_k():
    # the design's rule changes (Sheet Metal Rules: K 0.33): the flat and its table follow
    from sciforge import sheetmetal

    doc = App.ActiveDocument
    body = fs.STATE["body"]
    rule = sheetmetal.find_rule(doc, sheetmetal.body_rule_name(body))
    rule["k_factor"] = "0.33"
    sheetmetal.save_rule(doc, rule)
    doc.recompute()


change_k.wait_ms = 3000


def table_follows():
    from sciforge import drawing, flatpattern_drawing as fpd

    table = fpd.bend_table_of(d.page())
    rows = drawing.table_rows(table) if table is not None else []
    h.check(
        "the table follows the rule: K 0.33", [r["KFactor"] for r in rows] == ["0.33"] * 2, rows
    )
    ba = 3.141592653589793 / 2 * 1.33
    want = 28 + ba / 2
    offsets = sorted(abs(b.OriginX.Value) for b in d.of_type("TechDraw::DrawViewBalloon"))
    h.check(
        "the identifiers follow the bend lines (28 + BA/2 from the middle)",
        len(offsets) == 2 and all(abs(o - want) < 0.01 for o in offsets),
        (offsets, want),
    )


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
        bend_table,
        table_made,
        undo_table,
        table_undone,
        redo_table,
        table_redone,
        change_k,
        table_follows,
    ],
)
