# SPDX-License-Identifier: LGPL-2.1-or-later
"""Centre marks, centre lines, text and the title block on a drawing, with real clicks.

The filleted block (drawing_fixtures.block), ISO A3, base view Top at 1:1 at (150, 180),
visible edges only.

A  GEOMETRY > Center Mark: a click on the hole: two dash-dot lines cross at its centre,
   3 mm past the circle; the same hole again says it has one; a straight edge says to
   click a circle; Enter ends. Undo removes the mark; Redo brings it back.
B  GEOMETRY > Centerline: the left and the right edge: a centre line midway (x = 0).
C  TEXT > Text: two corners, the text typed, OK: the note is on the sheet.
D  A double-click on the title block: its dialog; Description and Revision typed; OK: the
   fields hold them and are kept (they no longer follow the design). The design renamed:
   the Title follows, the typed Description stays.
E  The title block again, Description typed, Cancel: the old text is back.
F  A click on the note selects it; Del deletes it.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

BASE = (150.0, 180.0)
state = {}


def new_design():
    s.new_design("Marks")()
    fx.block(App.ActiveDocument)
    h.fit()


def base():
    return d.bases()[0]


def at(u, v):
    from sciforge import drawing

    return drawing.local_to_page(base(), (u, v))


def marks():
    from sciforge import drawing

    return drawing.center_marks(base())


def texts():
    from sciforge import drawing

    page = d.page()
    return [o for o in drawing.annotations(page) if o.TypeId == drawing.ANNOTATION] if page else []


def title():
    from sciforge import drawing

    return drawing.title(d.page())


# -- A ------------------------------------------------------------------------------------------
def a_command():
    h.ribbon("Center Mark")


def a_hole():
    h.check("Center Mark dialog", d.panel_of("CenterMarkPanel") is not None, d.panel())
    d.click_at(*at(0, 6))


def a_marked():
    found = marks()
    if not h.check("one centre mark", len(found) == 1, found):
        return
    mark = found[0]
    h.check("at the hole's centre", abs(mark["c"][0]) < 1e-6 and abs(mark["c"][1]) < 1e-6, mark)
    h.check("radius 6", abs(mark["r"] - 6.0) < 1e-6, mark)
    edges = [base().getCosmeticEdge(t) for t in mark["tags"]]
    lengths = sorted(round((e.End - e.Start).Length, 6) for e in edges)
    h.check("two lines 3 mm past the circle (18 mm)", lengths == [18.0, 18.0], lengths)
    d.click_at(*at(0, 6))


def a_again():
    p = d.panel_of("CenterMarkPanel")
    h.check(
        "the hole has one already",
        p is not None and "already" in p.message.text(),
        p and p.message.text(),
    )
    h.check("still one mark", len(marks()) == 1)
    d.click_at(*at(0, -20))


def a_line():
    p = d.panel_of("CenterMarkPanel")
    h.check(
        "a line: click a circle",
        p is not None and "circle" in p.message.text(),
        p and p.message.text(),
    )
    d.key(QtCore.Qt.Key_Return)


a_line.wait_ms = 1200


def a_undo():
    h.check("Enter ends", d.panel() is None)
    d.undo()


def a_undone():
    h.check("undo: no mark", not marks(), marks())
    h.check("undo: no cosmetic lines", len(base().CosmeticEdges) == 0, len(base().CosmeticEdges))
    d.redo()


a_undone.wait_ms = 1200


def a_redone():
    h.check("redo: the mark is back", len(marks()) == 1 and len(base().CosmeticEdges) == 2)


# -- B ------------------------------------------------------------------------------------------
def b_command():
    h.ribbon("Centerline")


def b_edges():
    h.check("Centerline dialog", d.panel_of("CenterlinePanel") is not None, d.panel())
    d.click_at(*at(-30, 0))
    d.click_at(*at(30, 0))


def b_made():
    h.check("one centre line", len(base().CenterLines) == 1, len(base().CenterLines))
    d.key(QtCore.Qt.Key_Escape)


def b_done():
    h.check("Esc ends and keeps it", d.panel() is None and len(base().CenterLines) == 1)


# -- C ------------------------------------------------------------------------------------------
def c_command():
    h.ribbon("Text")


def c_corners():
    h.check("Text dialog", d.panel_of("TextPanel") is not None, d.panel())
    d.click_at(40, 80)
    d.move_to(80, 70)
    d.click_at(110, 60)


def c_type():
    p = d.panel_of("TextPanel")
    if h.check("the text box", p is not None):
        p.text.setFocus()
        d.type_into(p.text, "BREAK ALL SHARP EDGES")


c_type.wait_ms = 1200


def c_ok():
    d.ok()


c_ok.wait_ms = 1200


def c_made():
    found = texts()
    if not h.check("one note", len(found) == 1, found):
        return
    note = found[0]
    h.check("its text", list(note.Text) == ["BREAK ALL SHARP EDGES"], list(note.Text))
    h.check(
        "in the box",
        abs(note.X.Value - 75) < 0.5 and abs(note.Y.Value - 70) < 0.5,
        (note.X, note.Y),
    )
    h.shot("c-text")


# -- D ------------------------------------------------------------------------------------------
def d_open():
    from sciforge import drawing_core as core

    x0, y0, x1, y1 = core.title_block_rect("ISO", "A3")
    d.double_click_at(x0 + 40, y0 + 22)  # the DESCRIPTION cell


d_open.wait_ms = 1200


def d_type():
    p = d.panel_of("TitleBlockPanel")
    if not h.check("the title block's dialog", p is not None, d.panel()):
        return
    h.check("shows the title", p.fields["Title"].text() == "Marks", p.fields["Title"].text())
    d.type_into(p.fields["Description"], "Test plate")
    d.type_into(p.fields["Revision"], "B")


d_type.wait_ms = 1000


def d_ok():
    d.ok()


def d_kept():
    values = title()
    h.check("Description typed", values.get("Description") == "Test plate", values)
    h.check("Revision typed", values.get("Revision") == "B", values)
    edits = list(d.page().SciForgeTitleEdits)
    h.check("typed fields kept", "Description" in edits and "Revision" in edits, edits)
    App.ActiveDocument.Label = "Marks2"  # (the design renamed; the subject is the title block)
    App.ActiveDocument.recompute()


d_kept.wait_ms = 1500


def d_follows():
    values = title()
    h.check("the Title follows the design's name", values.get("Title") == "Marks2", values)
    h.check("the typed Description stays", values.get("Description") == "Test plate", values)


# -- E ------------------------------------------------------------------------------------------
def e_open():
    d_open()


e_open.wait_ms = 1200


def e_type():
    p = d.panel_of("TitleBlockPanel")
    if h.check("the title block's dialog", p is not None):
        d.type_into(p.fields["Description"], "Nope")


def e_cancel():
    h.check("live: Nope", title().get("Description") == "Nope", title())
    d.cancel()


def e_back():
    h.check("Cancel: Test plate again", title().get("Description") == "Test plate", title())


# -- F ------------------------------------------------------------------------------------------
def f_select():
    note = texts()[0]
    d.click_at(note.X.Value, note.Y.Value)


def f_delete():
    selected = [o.Name for o in Gui.Selection.getSelection()]
    h.check("the note is selected", texts()[0].Name in selected, selected)
    d.key(QtCore.Qt.Key_Delete)


f_delete.wait_ms = 1200


def f_gone():
    h.check("the note is deleted", not texts(), texts())
    h.check("the view stays", len(d.bases()) == 1)


h.run(
    "drawing_annotations",
    [new_design]
    + d.drawing_steps("sheet", base_at=BASE, scale="1:1", orientation="Top", style="Visible Edges")
    + [
        a_command,
        a_hole,
        a_marked,
        a_again,
        a_line,
        a_undo,
        a_undone,
        a_redone,
        b_command,
        b_edges,
        b_made,
        b_done,
        c_command,
        c_corners,
        c_type,
        c_ok,
        c_made,
        d_open,
        d_type,
        d_ok,
        d_kept,
        d_follows,
        e_open,
        e_type,
        e_cancel,
        e_back,
        f_select,
        f_delete,
        f_gone,
    ],
)
