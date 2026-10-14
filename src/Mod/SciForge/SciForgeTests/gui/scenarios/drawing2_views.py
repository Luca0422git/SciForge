# SPDX-License-Identifier: LGPL-2.1-or-later
"""More of the Drawing View dialog and the GEOMETRY / TEXT groups, with real clicks:
automated centre marks and centre lines, Edge Extension, the view label, a text box
dragged open, hidden edges per view.

The plate (drawing_fixtures.plate), ISO A3 (first angle), base view Top at 1:1, and a
projected view below it (the plate seen from the front).

A  Double-click the base view: its dialog; Center marks: Holes: a centre mark on each
   hole (two crosses); OK. Undo: gone; Redo: back.
B  The projected view's dialog: Holes: the holes seen from the side get centre lines
   (two, upright, a little past the plate); Round Extrudes: nothing more (no bosses).
   Visible and Hidden Edges: its hidden lines show. OK.
C  GEOMETRY > Edge Extension: the top edge and the right edge (they would meet where
   the R8 corner is): two thin lines to that corner and a point there; then D from the
   bottom left corner to that point: 80 across.
D  The base view's dialog: View label "TOP VIEW", shown: it is written under the view;
   OK. Undo: no label.
E  TEXT > Text dragged open (press, move, release) instead of two clicks: the text box;
   typed; OK.
F  The design changes (hole 1 moved 5 mm right, by script): the centre marks follow.
"""

from PySide import QtCore

from SciForgeTests.gui import drawing2_steps as w
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

state = {}


def projected():
    found = [v for v in d.views() if getattr(v, "SciForgeKind", "")]
    return found[0] if found else None


def auto(view):
    from sciforge import drawing

    return drawing.auto_marks_of(view)


def open_view(view_fn):
    def open_():
        from sciforge import drawing

        view = view_fn()
        if not h.check("the view is there", view is not None):
            return
        x, y = drawing.view_position(view)
        half_w, half_h = drawing.view_extent(view)
        d.double_click_at(x + half_w - 3.0, y - half_h + 1.0)

    open_.wait_ms = 1500
    open_.__name__ = "open_%s" % view_fn.__name__
    return open_


# -- set-up: a projected view below -------------------------------------------------------------
def p_command():
    h.ribbon("Projected View")


def p_place():
    x, y = w.at(0.0, 0.0)
    d.move_to(x + 2, y - 50)
    d.move_to(x, y - 55)


p_place.wait_ms = 2000


def p_click():
    x, y = w.at(0.0, 0.0)
    d.click_at(x, y - 55)
    d.key(QtCore.Qt.Key_Return)


p_click.wait_ms = 2500


def p_made():
    h.check("a projected view", projected() is not None, [v.Label for v in d.views()])


# -- A ------------------------------------------------------------------------------------------
def a_holes():
    p = d.panel_of("BaseViewPanel")
    if h.check("the base view's dialog", p is not None, d.panel()):
        w.toggle(p.auto_boxes["holes"])


a_holes.wait_ms = 2500


def a_marks():
    marks = auto(w.base()).get("marks", [])
    centres = sorted((round(m[0], 3), round(m[1], 3)) for m in marks)
    h.check("a mark on each hole", centres == [w.HOLE1, w.HOLE2], marks)
    h.check("as cosmetic lines (4)", len(w.base().SciForgeAutoTags) == 4, w.base().SciForgeAutoTags)
    d.ok()


a_marks.wait_ms = 1500


def a_undo():
    d.undo()


a_undo.wait_ms = 2500


def a_undone():
    tags = list(getattr(w.base(), "SciForgeAutoTags", []) or [])
    h.check("undo: no automatic marks", not tags, tags)
    d.redo()


a_undone.wait_ms = 2500


def a_redone():
    marks = auto(w.base()).get("marks", [])
    h.check("redo: two marks", len(marks) == 2, marks)


# -- B ------------------------------------------------------------------------------------------
def b_holes():
    p = d.panel_of("EditViewPanel")
    if h.check("the projected view's dialog", p is not None, d.panel()):
        w.toggle(p.auto_boxes["holes"])


b_holes.wait_ms = 2500


def b_lines():
    lines = auto(projected()).get("lines", [])
    h.check("two centre lines", len(lines) == 2, lines)
    xs = sorted(round(line[0], 3) for line in lines)
    h.check("at the holes", xs == [-20.0, 20.0], lines)
    h.check("upright", all(abs(line[0] - line[2]) < 1e-6 for line in lines), lines)
    h.check(
        "a little past the plate (3 mm each side)",
        all(abs(abs(line[1] - line[3]) - 16.0) < 1e-6 for line in lines),
        lines,
    )
    w.toggle(d.panel_of("EditViewPanel").auto_boxes["extrudes"])


b_lines.wait_ms = 2500


def b_extrudes():
    lines = auto(projected()).get("lines", [])
    h.check("no bosses: still two", len(lines) == 2, lines)
    d.choose(d.panel_of("EditViewPanel").style, "Visible and Hidden Edges")


b_extrudes.wait_ms = 1500


def b_hidden():
    h.check("hidden edges on", projected().HardHidden)
    d.ok()


b_hidden.wait_ms = 2500


# -- C ------------------------------------------------------------------------------------------
def c_command():
    w.menu("GEOMETRY", "Edge Extension")


c_command.wait_ms = 1200


def c_edges():
    p = d.panel_of("EdgeExtensionPanel")
    if not h.check("the Edge Extension dialog", p is not None, d.panel()):
        return
    w.click(0.0, 25.0)
    w.click(40.0, 0.0)


c_edges.wait_ms = 2500


def c_made():
    from sciforge import drawing, drawing_annot

    items = drawing.extensions_of(w.base())
    if not h.check("one extension", len(items) == 1, items):
        return
    point = items[0]["point"]
    h.check(
        "where the edges meet: the corner",
        abs(point[0] - 40.0) < 1e-6 and abs(point[1] - 25.0) < 1e-6,
        point,
    )
    h.check("two thin lines", len(items[0]["tags"]) == 2, items[0])
    near = [
        n
        for n, i in drawing_annot.elements(w.base())
        if i["kind"] == "vertex"
        and abs(i["point"][0] - 40.0) < 1e-6
        and abs(i["point"][1] - 25.0) < 1e-6
    ]
    h.check("a point there to dimension to", len(near) >= 1, near)
    d.key(QtCore.Qt.Key_Escape)


c_made.wait_ms = 1500


def c_measured():
    from sciforge import drawing

    dim = w.STORE.get("ext")
    if h.check("a dimension to the point", dim is not None):
        h.check(
            "80 across",
            abs(drawing.dimension_value(dim) - 80.0) < 1e-6,
            drawing.dimension_value(dim),
        )


# -- D ------------------------------------------------------------------------------------------
def d_label():
    p = d.panel_of("BaseViewPanel")
    if not h.check("the base view's dialog", p is not None, d.panel()):
        return
    h.check("not shown by default", not p.show_label.isChecked())
    d.type_into(p.label_text, "TOP VIEW")
    w.toggle(p.show_label)


d_label.wait_ms = 1500


def d_shown():
    h.check("written under the view", w.base().Caption == "TOP VIEW", w.base().Caption)
    d.ok()


d_shown.wait_ms = 1500


def d_undo():
    d.undo()


d_undo.wait_ms = 1500


def d_undone():
    h.check("undo: no label", w.base().Caption == "", w.base().Caption)
    d.redo()


d_undone.wait_ms = 1500


# -- E ------------------------------------------------------------------------------------------
def e_command():
    h.ribbon("Text")


def e_drag():
    p = d.panel_of("TextPanel")
    if not h.check("the Text dialog", p is not None, d.panel()):
        return
    view = d.gv()
    a = d.widget_point(300, 230)
    b = d.widget_point(360, 215)
    wi.drag(view.viewport(), a, view.viewport().mapToGlobal(b), 12)


e_drag.wait_ms = 1500


def e_typed():
    p = d.panel_of("TextPanel")
    if not h.check("a text box from the drag", p is not None and p.note is not None):
        return
    note = p.note
    h.check(
        "in the box's middle",
        abs(note.X.Value - 330) < 1.0 and abs(note.Y.Value - 222.5) < 1.0,
        (note.X, note.Y),
    )
    d.type_into(p.text, "MATERIAL: STEEL")
    d.ok()


e_typed.wait_ms = 1500


def e_done():
    found = [o for o in d.page().Views if getattr(o, "SciForgeType", "") == "DrawingText"]
    h.check("the note", len(found) == 1 and list(found[0].Text) == ["MATERIAL: STEEL"], found)


# -- F ------------------------------------------------------------------------------------------
def f_move():
    import FreeCAD as App

    doc = App.ActiveDocument
    hole = doc.getObject("Hole1")
    hole.Placement.Base = App.Vector(25.0, 15.0, 0)
    doc.recompute()


f_move.wait_ms = 3500


def f_followed():
    marks = auto(w.base()).get("marks", [])
    centres = sorted((round(m[0], 3), round(m[1], 3)) for m in marks)
    h.check("the marks follow", centres == [(-15.0, -10.0), w.HOLE2], marks)
    lines = auto(projected()).get("lines", [])
    xs = sorted(round(line[0], 3) for line in lines)
    h.check("the centre lines follow", xs == [-15.0, 20.0], lines)
    h.shot("f-followed")


def base_view():
    return w.base()


h.run(
    "drawing2_views",
    [w.new_design("Vw")]
    + w.sheet_steps()
    + [d.wait_geometry(1500)]
    + [p_command, p_place, p_click, p_made]
    + [open_view(base_view), a_holes, a_marks, a_undo, a_undone, a_redone]
    + [open_view(projected), b_holes, b_lines, b_extrudes, b_hidden]
    + [c_command, c_edges, c_made]
    + w.dimension_steps("ext", [(-40.0, -25.0), (40.0, 25.0)], (0.0, 40.0), "DistanceX")
    + [c_measured]
    + [open_view(base_view), d_label, d_shown, d_undo, d_undone]
    + [e_command, e_drag, e_typed, e_done]
    + [f_move, f_followed],
)
