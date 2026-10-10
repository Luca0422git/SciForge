# SPDX-License-Identifier: LGPL-2.1-or-later
"""The sketch keys as a real keyboard sends them. A keyboard sends keys to the widget
that has the focus: the 3D view widget (not the drawing area inside it, where the mouse
goes), or, while a drawing tool runs, FreeCAD's on-screen value field next to the
pointer. Every key below goes there (si.key, si.type_text), never straight to the
drawing area as h.press does.

R1 Create Sketch, Esc: nothing is created. Create Sketch again, click the XY plane.
R2 L, click the origin, type 20, Enter (in FreeCAD's field): a 20 mm line, and the line
   tool goes on from its end. Type 12 mm, Enter: the next line, 12 up, joined to the
   first (the letters of a unit stay in the field, M does not start Move).
R3 Esc right after typing (FreeCAD keeps Esc in its field for two seconds): the tool
   stops, the sketch stays open.
R4 C, click, type 10, Enter: a circle 10 wide. L while the circle's field has the
   keyboard: the line tool starts (Fusion switches tools with their keys at any time).
R5 Select a line, M: Move/Copy starts; Esc, Esc. Select a line, Del: it goes; Ctrl+Z.
R7 Double-click the 12 dimension: the value box has the keyboard; arrow keys and Page Up
   (which the box does not use) do nothing; type 14, Enter: the line is 14 long.
R6 E: the sketch finishes, Extrude takes the circle; OK: a cylinder 10 wide, 10 high.

Hand-derived volume: pi * 5^2 * 10 = 785.398...
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
X, Y = V(1, 0, 0), V(0, 1, 0)
s = {}
FIELD = "Gui::QuantitySpinBox"  # FreeCAD's on-screen value field


def recent_command():
    from sciforge import recent

    last = recent.last()
    return last[0] if last else None


def editor():
    from sciforge import sketch_mode

    session = sketch_mode.current()
    return session.editor if session is not None else None


# == R1: Create Sketch and Esc ======================================================
def r_new():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchKeys")
    h.fit()
    h.click_empty()  # the hand was on the 3D view: it has the keyboard


def r_create():
    s["objects"] = len(App.ActiveDocument.Objects)
    h.ribbon("Create Sketch")


def r_esc_create():
    h.check("R1: Create Sketch waits for a plane", Gui.Control.activeDialog())
    si.key(QtCore.Qt.Key_Escape)


def r_cancelled():
    h.check("R1: Esc cancels Create Sketch", not Gui.Control.activeDialog())
    h.check("R1: and no sketch is made", h.in_sketch() is None)
    sketches = [o for o in App.ActiveDocument.Objects if o.TypeId == "Sketcher::SketchObject"]
    h.check("R1: no sketch in the document", not sketches, [o.Name for o in sketches])
    h.ribbon("Create Sketch")


def r_pick():
    h.click(V(12, -8, 0))


# == R2: typed lengths, Enter in FreeCAD's field ===================================
def r_line():
    s["sk"] = h.in_sketch()
    h.check("R2: sketch open", s["sk"] is not None)
    si.key("l")


def r_first():
    h.check(
        "R2: L starts the line tool", si.drawing() and recent_command() == "SciForge_SketchLine"
    )
    si.click(V(0, 0, 0))


def r_type_20():
    h.check("R2: FreeCAD's value field has the keyboard", si.focus_class() == FIELD)
    si.move_towards(V(8, 0.3, 0), X)
    si.type_text("20")


def r_after_20():
    sk = s["sk"]
    lines = si.lines(sk)
    h.check("R2: 20 and Enter draw one line", len(lines) == 1, sk.Geometry)
    if lines:
        g = lines[0][1]
        h.check(
            "R2: from the origin, 20 long, towards the pointer",
            si.vnear(g.StartPoint, V(0, 0, 0)) and si.vnear(g.EndPoint, V(20, 0, 0)),
            g,
        )
    h.check("R2: the line tool goes on from the end", si.drawing())
    si.move_towards(V(20.3, 8, 0), Y)


def r_type_12():
    si.type_text("12 mm")  # a unit: its letters stay in the field


def r_after_12():
    sk = s["sk"]
    lines = si.lines(sk)
    h.check("R2: second line", len(lines) == 2, sk.Geometry)
    if len(lines) == 2:
        g = lines[1][1]
        h.check(
            "R2: 12 up from the end of the first",
            si.vnear(g.StartPoint, V(20, 0, 0)) and si.vnear(g.EndPoint, V(20, 12, 0)),
            g,
        )
        joined = [
            c
            for c in sk.Constraints
            if c.Type == "Coincident" and {c.First, c.Second} == {lines[0][0], lines[1][0]}
        ]
        h.check("R2: joined (coincident)", bool(joined), sk.Constraints)
    dims = sorted(round(c.Value, 6) for c in sk.Constraints if c.Type == "Distance")
    h.check("R2: the typed lengths are dimensions", dims == [12.0, 20.0], dims)
    h.check("R2: the field has the keyboard again", si.focus_class() == FIELD)
    # R3: Esc at once, while FreeCAD would still keep it in its field
    s["count"] = len(sk.Geometry)
    si.key(QtCore.Qt.Key_Escape)


def r_after_esc():
    sk = s["sk"]
    h.check("R3: Esc stops the line tool", not si.drawing())
    h.check("R3: nothing more drawn", len(sk.Geometry) == s["count"], sk.Geometry)
    h.check("R3: the sketch stays open", h.in_sketch() is sk)
    h.shot("R3-two-lines")


# == R4: circle typed, then L from its field ========================================
def r_circle():
    si.key("c")


def r_centre():
    h.check("R4: C starts the circle tool", si.drawing())
    si.click(V(40, 5, 0))


def r_diameter():
    si.move_towards(V(45, 5.3, 0), X)
    si.type_text("10")


def r_circle_check():
    circles = si.circles(s["sk"], construction=False)
    h.check("R4: one circle", len(circles) == 1, s["sk"].Geometry)
    if circles:
        c = circles[0][1]
        # a free click: the centre is where the pixel is (a fraction of a mm)
        h.check("R4: centred where clicked", si.vnear(c.Center, V(40, 5, 0), 0.5), c)
        h.check("R4: typed 10 wide", si.near(c.Radius, 5.0), c)
    h.check("R4: the circle tool goes on", si.drawing())
    si.click(V(55, 12, 0))  # the next circle's centre: its diameter field comes up


def r_l_in_field():
    focus = si.focus_class()
    h.check("R4: the next circle's value field has the keyboard", focus == FIELD, focus)
    si.move_towards(V(58, 12.3, 0), X)
    si.key("l")


def r_switched():
    h.check(
        "R4: L in the circle's field starts the line tool",
        recent_command() == "SciForge_SketchLine",
    )
    h.check("R4: a drawing tool runs", si.drawing())
    h.check("R4: the half circle goes", len(s["sk"].Geometry) == 3, s["sk"].Geometry)
    si.key(QtCore.Qt.Key_Escape)


def r_stopped():
    h.check("R4: Esc stops it", not si.drawing())


# == R5: M, Del, Ctrl+Z =============================================================
def r_select_first():
    si.click(V(10, 0, 0))


def r_move():
    h.check("R5: a line selected", bool(Gui.Selection.getSelectionEx()))
    si.key("m")


def r_moving():
    h.check("R5: M starts Move/Copy for sketch curves", recent_command() == "SciForge_SketchMove")
    h.check("R5: it waits for the base point", si.drawing())
    si.key(QtCore.Qt.Key_Escape)


def r_move_esc():
    h.check("R5: Esc stops Move/Copy", not si.drawing())
    h.check("R5: nothing moved", si.vnear(s["sk"].Geometry[0].EndPoint, V(20, 0, 0)))
    si.key(QtCore.Qt.Key_Escape)


def r_select_second():
    h.check("R5: second Esc: nothing selected", not Gui.Selection.getSelectionEx())
    si.click(V(20, 6, 0))


def r_delete():
    h.check("R5: the second line selected", bool(Gui.Selection.getSelectionEx()))
    s["count"] = len(s["sk"].Geometry)
    si.key(QtCore.Qt.Key_Delete)


def r_deleted():
    sk = s["sk"]
    h.check("R5: Del deletes it", len(sk.Geometry) == s["count"] - 1, sk.Geometry)
    h.check("R5: the sketch stays open", h.in_sketch() is sk)
    si.key("z", QtCore.Qt.ControlModifier)


def r_undone():
    sk = s["sk"]
    h.check("R5: Ctrl+Z brings it back", len(sk.Geometry) == s["count"], sk.Geometry)
    h.check("R5: still in the sketch", h.in_sketch() is sk)


# == R7: the dimension box with the keyboard in it ==================================
def r_dim_open():
    sk = s["sk"]
    found = [
        i
        for i, c in enumerate(sk.Constraints)
        if c.Type == "Distance" and c.Driving and si.near(c.Value, 12.0)
    ]
    h.check("R7: the 12 dimension", len(found) == 1, [(c.Type, c.Value) for c in sk.Constraints])
    if not found:
        return
    point = si.dimension_label(sk, found[0])
    h.move(h.screen_point(point + V(2, 1, 0)))
    h.move(h.screen_point(point))
    h.double_click(point)


def r_dim_keys():
    h.check("R7: the dimension box is open", editor() is not None)
    focus = si.focus_class()
    h.check("R7: the box has the keyboard", focus == "QLineEdit", focus)
    for key in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down, QtCore.Qt.Key_PageUp):
        si.key(key)
    h.check("R7: keys the box does not use: still open", editor() is not None)
    si.type_text("14")


def r_dim_done():
    sk = s["sk"]
    h.check("R7: Enter closes the box", editor() is None)
    lines = si.lines(sk)
    h.check(
        "R7: the line is 14 long now",
        len(lines) == 2 and si.near(lines[1][1].length(), 14.0),
        [g.length() for _, g in lines],
    )
    h.check("R7: still solves", sk.solve() == 0)


# == R6: E =========================================================================
def r_extrude():
    si.key("e")


def r_extrude_open():
    from sciforge import extrude_ui

    h.check("R6: E finished the sketch", h.in_sketch() is None)
    panel = extrude_ui.ExtrudePanel.last
    h.check(
        "R6: Extrude took the circle (the only closed shape)",
        panel is not None and not panel._closed and len(panel.profiles) == 1,
        panel.profiles if panel else None,
    )
    h.task_button("OK")


def r_volume():
    v = h.solid_volume()
    h.check("R6: cylinder pi*5^2*10", si.near(v, math.pi * 25 * 10, 1e-6), v)
    h.check("R6: no pop-up", not h.popups(), h.popups())
    h.shot("R6-cylinder")


h.run(
    "sketch_qa_keys",
    si.watched(
        [
            r_new,
            r_create,
            r_esc_create,
            r_cancelled,
            r_pick,
            r_line,
            r_first,
            r_type_20,
            r_after_20,
            r_type_12,
            r_after_12,
            r_after_esc,
            r_circle,
            r_centre,
            r_diameter,
            r_circle_check,
            r_l_in_field,
            r_switched,
            r_stopped,
            r_select_first,
            r_move,
            r_moving,
            r_move_esc,
            r_select_second,
            r_delete,
            r_deleted,
            r_undone,
            r_dim_open,
            r_dim_keys,
            r_dim_done,
            r_extrude,
            r_extrude_open,
            r_volume,
        ]
    ),
)
