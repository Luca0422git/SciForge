# SPDX-License-Identifier: LGPL-2.1-or-later
"""A drawing of a flat pattern (Fusion: Drawing > From Design with the flat pattern as the
view source), real input only: a U channel with a hole and its Flat Pattern (setup). File >
New Drawing; Contents Select lists "Flat Pattern / Body" (not ticked); tick it, untick the
body; OK: the drawing opens and its Base View shows the flat pattern from the top (the flat
lies on XY): the outline, the hole and the bend lines are its 11 visible edges; a click places
it; OK. TABLES > Bend Table: a table of the two bends (B1, B2: UP, 90 degrees, R 1.00, K 0.44)
and an identifier balloon on each bend centre line; undo / redo. TEXT > Bend Note: a click on
B1's centre line writes "UP 90° R 1.00" along it (turned with the line), a click on the flat
away from the bend lines is refused, B2's line gets its note, B1 again is refused; OK; undo /
redo. The design's rule set to K 0.33: the table, the identifiers and the notes follow."""

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


def _line_point(index, at):
    """The page point `at` of the way along bend `index`'s centre line (identifier order)."""
    from sciforge import flatpattern_drawing as fpd

    view = d.bases()[0]
    fp = fpd.flat_of(view)
    a, b = fpd._centre_local(view, fp, fpd._ordered(fp)[index])
    return d.to_page(view, (a[0] + (b[0] - a[0]) * at, a[1] + (b[1] - a[1]) * at))


def _notes():
    from sciforge import flatpattern_drawing as fpd

    return fpd.bend_notes_of(d.page())


def bend_note():
    d.group_menu("TEXT", "Bend Note")


bend_note.wait_ms = 1500


def click_b1():
    p = d.panel_of("BendNotePanel")
    h.check("Bend Note dialog open", p is not None, d.panel())
    x, y = _line_point(0, 0.3)
    d.click_at(x, y)


def b1_noted():
    from sciforge import flatpattern_drawing as fpd

    notes = _notes()
    h.check("one bend note", len(notes) == 1, len(notes))
    if not notes:
        return
    note = notes[0]
    h.check("it says UP 90\u00b0 R 1.00", list(note.Text) == ["UP 90\u00b0 R 1.00"], note.Text)
    h.check("turned with the (vertical) line", abs(note.Rotation.Value - 90.0) < 1e-6)
    view = d.bases()[0]
    fp = fpd.flat_of(view)
    x, y, _a = fpd.note_place(view, fp, fpd._ordered(fp)[0])
    mx, my = _line_point(0, 0.5)
    h.check(
        "beside the middle of B1's centre line",
        abs(note.X.Value - x) < 1e-6 and abs(note.Y.Value - my) < 1e-6 and 2 < mx - x < 5,
        (note.X.Value, note.Y.Value, mx, my),
    )


def click_outline():
    from sciforge import flatpattern_drawing as fpd

    view = d.bases()[0]
    fp = fpd.flat_of(view)
    bb = fp.Shape.BoundBox
    # on the flat, 10 mm in from its left end: far from both bend lines
    x, y = d.to_page(view, (-bb.XLength / 2.0 + 10.0, 0.0))
    d.click_at(x, y)


def outline_refused():
    p = d.panel_of("BendNotePanel")
    text = p.message.text() if p is not None else ""
    h.check("away from the bend lines: refused", "not a bend centre line" in text, text)
    h.check("still one note", len(_notes()) == 1)


def click_b2():
    x, y = _line_point(1, 0.7)
    d.click_at(x, y)


def click_b1_again():
    h.check("two bend notes", len(_notes()) == 2, len(_notes()))
    x, y = _line_point(0, 0.6)
    d.click_at(x, y)


def again_refused():
    p = d.panel_of("BendNotePanel")
    text = p.message.text() if p is not None else ""
    h.check("B1 has its note already", "already" in text, text)
    h.check("still two notes", len(_notes()) == 2)
    h.shot("3-bend-notes")


def notes_ok():
    d.ok()


def undo_notes():
    h.check("Bend Note closed", d.panel_of("BendNotePanel") is None)
    d.undo()


def notes_undone():
    h.check("undo takes both notes away (one step)", len(_notes()) == 0, len(_notes()))
    d.redo()


def notes_redone():
    h.check("redo brings them back", len(_notes()) == 2, len(_notes()))


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
    view = d.bases()[0]
    lefts = []
    for note in _notes():
        mx, _my = _line_point(int(note.SciForgeBend), 0.5)
        lefts.append(mx - note.X.Value)
    h.check(
        "the bend notes follow their lines",
        len(lefts) == 2 and all(abs(v - 3.15) < 1e-3 for v in lefts),
        (lefts, view.Label),
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
        bend_note,
        click_b1,
        b1_noted,
        click_outline,
        outline_refused,
        click_b2,
        click_b1_again,
        again_refused,
        notes_ok,
        undo_notes,
        notes_undone,
        notes_redone,
        change_k,
        table_follows,
    ],
)
