# SPDX-License-Identifier: LGPL-2.1-or-later
"""Move/Copy (M) on bodies, only real input.

Body = rectangle 0..40 x 0..30, extruded 10 (12000); its middle (the pivot) is (20, 15, 5).

  A  nothing selected, M: the dialog waits for the bodies; click the body: the manipulator
     (3 arrows, 3 turn handles) appears at the middle. Drag the X arrow about 15 mm: the body
     follows. Type X Distance 10 and Z Angle 90: the body turns about its middle and moves
     10 in X: x 15..45, y -5..35. OK: one Move step. Ctrl+Z / Ctrl+Y.
  B  double-click the Move in the timeline: Z Angle 0, Y Distance 5: x 10..50, y 5..35. OK.
  C  body selected first, M: it is taken; Translate; drag the Z arrow up, then type Z
     Distance 20: z 20..30. OK: two Move steps.
  D  Rotate: M, click the body, Rotate: the origin axes are drawn; click the Z axis; type
     Angle 90: (x, y) -> (-y, x): x -35..-5, y 10..50. Drag the blue handle a bit, type 90
     again. OK.
  E  Point to Point with Create Copy: M, click the body, Point to Point, click the corner
     (-35, 10, 30), then the corner (-5, 10, 30): a copy 30 to the right, the original stays.
     OK: two bodies; Ctrl+Z removes the copy.
  F  Cancel: M, click the body, X Distance 30, Cancel: nothing moved. Esc the same.
  G  Point to Position: click the corner (-35, 10, 30): X / Y / Z show it; type X 0: the body
     moves 35 to the right. OK.
"""
import math

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
state = {}


def body():
    return s.bodies()[0]


def moves():
    return s.steps_of_kind("MoveCopy")


def bbox(x=None):
    return (x or body()).Shape.BoundBox


def box_is(name, box, expect, tol=1e-6):
    got = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
    ok = all(abs(a - c) <= tol for a, c in zip(got, expect))
    return h.check(name, ok, (got, expect))


def field(panel, name):
    return {
        "dx": panel.distance_fields[0],
        "dy": panel.distance_fields[1],
        "dz": panel.distance_fields[2],
        "rx": panel.angle_fields[0],
        "ry": panel.angle_fields[1],
        "rz": panel.angle_fields[2],
        "angle": panel.angle,
    }[name].widget


def drag_arrow(index, along):
    """Drag arrow `index` of the manipulator by `along` mm (on its shaft, like a hand)."""
    p = s.panel()
    triad = getattr(p, "triad", None)
    if not h.check("manipulator shown", triad is not None):
        return
    axis = [V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)][index]
    start = triad.center + axis * (0.75 * triad.size)
    h.drag(h.screen_point(start), h.screen_point(start + axis * along))


def drag_along(handle, start, end, step=5.0):
    """Drag the blue turn handle round its arc from `start` to `end` degrees, the way a hand
    follows it."""
    from PySide import QtGui, QtWidgets
    from PySide6 import QtTest

    widget = h.gl_widget()
    count = max(1, int(abs(end - start) / step))
    pixels = [
        h.screen_point(handle.point_at(start + (end - start) * i / count)) for i in range(count + 1)
    ]
    h.move(pixels[0])
    QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pixels[0])
    for pixel in pixels[1:]:
        pos = QtCore.QPointF(pixel)
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            pos,
            QtCore.QPointF(widget.mapToGlobal(pixel)),
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
    QtTest.QTest.mouseRelease(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pixels[-1])
    QtWidgets.QApplication.processEvents()


# -- A --------------------------------------------------------------------------------------------
def a_press_m():
    h.click_empty()
    h.fit()
    h.press("m")


def a_waits():
    p = s.panel()
    h.check("Move/Copy dialog open", p is not None and p.title == "Move/Copy", p)
    s.no_popups("M")
    if p is not None:
        h.check("Free Move first", p.move_type.currentText() == "Free Move")
        h.check("objects box waits", p.active == "objects", p.active)
        h.check("hint asks for bodies", "bodies" in p.info.text().lower(), p.info.text())


def a_click_body():
    h.click(V(20, 15, 10))


def a_manipulator():
    p = s.panel()
    h.check("body picked", p is not None and p.options["bodies"] == [body()], p and p.options)
    triad = getattr(p, "triad", None)
    if h.check("manipulator shown", triad is not None):
        h.check(
            "at the middle of the body", (triad.center - V(20, 15, 5)).Length < 1e-6, triad.center
        )
    h.shot("A-manipulator")


def a_drag_x():
    drag_arrow(0, 15)


def a_dragged():
    p = s.panel()
    dx = p.options["dx"] if p is not None else 0
    h.check("drag moved about 15 in X", abs(dx - 15) < 2.0, dx)
    h.check("the body follows", abs(bbox().XMin - dx) < 1e-6, (bbox().XMin, dx))
    h.shot("A-dragged")


def a_type():
    p = s.panel()
    if p is not None:
        s.type_value(field(p, "dx"), "10")
        s.type_value(field(p, "rz"), "90")


def a_typed():
    box_is("turned 90 about the middle, 10 in X", bbox(), [15, -5, 0, 45, 35, 10])
    h.check("volume kept", s.close(s.volume(body()), 12000), s.volume(body()))


def a_ok():
    h.task_button("OK")


def a_done():
    h.check("dialog closed", s.panel() is None)
    h.check("one Move step", len(moves()) == 1, moves())
    box_is("moved body", bbox(), [15, -5, 0, 45, 35, 10])
    h.check("timeline shows the Move", s.timeline_title_of(moves()[0]) is not None)


def a_undo():
    s.undo()


def a_undone():
    box_is("undo: back at the origin", bbox(), [0, 0, 0, 40, 30, 10])
    h.check("undo: no Move", not moves(), moves())


def a_redo():
    s.redo()


def a_redone():
    box_is("redo: moved again", bbox(), [15, -5, 0, 45, 35, 10])


# -- B --------------------------------------------------------------------------------------------
def b_edit():
    s.timeline_double_click(moves()[0])


def b_change():
    p = s.panel()
    if h.check("edit dialog open", p is not None and p.editing, p):
        h.check("edit shows Z Angle 90", abs(p.options["rz"] - 90) < 1e-9, p.options["rz"])
        s.type_value(field(p, "rz"), "0")
        s.type_value(field(p, "dy"), "5")


def b_ok():
    h.task_button("OK")


def b_done():
    box_is("edited move", bbox(), [10, 5, 0, 50, 35, 10])
    h.check("still one Move step", len(moves()) == 1, moves())


# -- C --------------------------------------------------------------------------------------------
def c_select():
    h.fit()
    h.click(V(30, 20, 10))


def c_press_m():
    h.press("m")


def c_translate():
    p = s.panel()
    if h.check("dialog open", p is not None):
        h.check("preselected body taken", p.options["bodies"] == [body()], p.options)
        b.choose(p.move_type, "Translate")


def c_drag_z():
    p = s.panel()
    if p is not None:
        h.check("no turn handles in Translate", p.triad is not None and not p.triad.turns)
    drag_arrow(2, 8)


def c_dragged():
    p = s.panel()
    dz = p.options["dz"] if p is not None else 0
    h.check("dragged up", dz > 3, dz)


def c_type():
    p = s.panel()
    if p is not None:
        s.type_value(field(p, "dz"), "20")


def c_ok():
    h.task_button("OK")


def c_done():
    box_is("translated up 20", bbox(), [10, 5, 20, 50, 35, 30])
    h.check("two Move steps", len(moves()) == 2, moves())


# -- D --------------------------------------------------------------------------------------------
def d_open():
    h.click_empty()
    h.fit()
    h.press("m")


def d_click_body():
    h.click(V(30, 20, 30))


def d_rotate():
    p = s.panel()
    if h.check("dialog open", p is not None):
        b.choose(p.move_type, "Rotate")


def d_axes_shown():
    p = s.panel()
    if p is not None:
        h.check("axis box waits", p.active == "axis", p.active)
        h.check("origin axes drawn", p.axis_picker is not None)
    h.fit()


def d_click_z_axis():
    p = s.panel()
    picker = getattr(p, "axis_picker", None)
    if h.check("axis picker", picker is not None):
        _feature, start, end = picker.axes["Z_Axis"]
        h.click(start + (end - start) * 0.85)


def d_type_angle():
    p = s.panel()
    if p is not None:
        h.check(
            "Z axis picked",
            p.options["axis_dir"] is not None and abs(abs(p.options["axis_dir"][2]) - 1) < 1e-9,
            p.options,
        )
        h.check("turn handle shown", p.turn_handle is not None)
        s.type_value(field(p, "angle"), "90")


def d_turned():
    box_is("turned 90 about Z", bbox(), [-35, 10, 20, -5, 50, 30])
    h.shot("D-rotate")


def d_drag_handle():
    p = s.panel()
    handle = getattr(p, "turn_handle", None)
    if h.check("turn handle", handle is not None):
        drag_along(handle, 90, 120)


def d_dragged():
    p = s.panel()
    angle = p.options["angle"] if p is not None else 0
    h.check("handle turned it further", angle > 100, angle)
    if p is not None:
        s.type_value(field(p, "angle"), "90")


def d_ok():
    h.task_button("OK")


def d_done():
    box_is("rotated body", bbox(), [-35, 10, 20, -5, 50, 30])
    h.check("three Move steps", len(moves()) == 3, moves())


# -- E --------------------------------------------------------------------------------------------
def e_open():
    h.click_empty()
    h.fit()
    h.press("m")


def e_click_body():
    h.click(V(-20, 30, 30))


def e_point_to_point():
    p = s.panel()
    if h.check("dialog open", p is not None):
        b.choose(p.move_type, "Point to Point")
        s.toggle(p.copy)


def e_from():
    p = s.panel()
    if p is not None:
        h.check("origin point box waits", p.active == "from_point", p.active)
    h.click(V(-34.5, 10, 30))  # on the top edge, right by the corner (-35, 10, 30)


def e_to():
    p = s.panel()
    if p is not None:
        h.check(
            "corner snapped",
            p.options["from_point"] is not None
            and (V(*p.options["from_point"]) - V(-35, 10, 30)).Length < 1e-6,
            p.options["from_point"],
        )
        h.check("target box waits", p.active == "to_point", p.active)
    h.click(V(-5.5, 10, 30))


def e_preview():
    found = s.bodies()
    h.check("a copy", len(found) == 2, [x.Label for x in found])
    box_is("original stays", bbox(), [-35, 10, 20, -5, 50, 30])
    if len(found) == 2:
        box_is("copy 30 to the right", bbox(found[1]), [-5, 10, 20, 25, 50, 30])
    h.shot("E-copy")


def e_ok():
    h.task_button("OK")


def e_done():
    h.check("two bodies", len(s.bodies()) == 2)
    h.check("copy volume", s.close(s.volume(s.bodies()[-1]), 12000), s.volume(s.bodies()[-1]))


def e_undo():
    s.undo()


def e_undone():
    h.check("undo: the copy is gone", len(s.bodies()) == 1, [x.Label for x in s.bodies()])


# -- F --------------------------------------------------------------------------------------------
def f_open():
    h.click_empty()
    h.fit()
    h.press("m")


def f_click_body():
    h.click(V(-20, 30, 30))


def f_type():
    p = s.panel()
    if h.check("dialog open", p is not None):
        s.type_value(field(p, "dx"), "30")


def f_preview():
    box_is("preview moved", bbox(), [-5, 10, 20, 25, 50, 30])


def f_cancel():
    h.task_button("Cancel")


def f_cancelled():
    h.check("dialog closed", s.panel() is None)
    box_is("Cancel: not moved", bbox(), [-35, 10, 20, -5, 50, 30])
    h.check("Cancel: three Move steps", len(moves()) == 3, moves())


def f_escape_open():
    h.press("m")


def f_escape():
    h.check("dialog open", s.panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def f_escaped():
    h.check("Esc closed it", s.panel() is None)
    box_is("Esc: not moved", bbox(), [-35, 10, 20, -5, 50, 30])


# -- G: Point to Position --------------------------------------------------------------------------
def g_open():
    h.click_empty()
    h.fit()
    h.press("m")


def g_click_body():
    h.click(V(-20, 30, 30))


def g_type():
    p = s.panel()
    if h.check("dialog open", p is not None):
        b.choose(p.move_type, "Point to Position")
        h.check("point box waits", p.active == "from_point", p.active)


def g_click_corner():
    h.click(V(-34.5, 10, 30))


def g_prefilled():
    p = s.panel()
    if h.check("dialog open", p is not None):
        got = [p.options[k] for k in ("px", "py", "pz")]
        h.check(
            "X / Y / Z start at the corner",
            all(abs(a - c) < 1e-9 for a, c in zip(got, [-35, 10, 30])),
            got,
        )
        box_is("nothing moved yet", bbox(), [-35, 10, 20, -5, 50, 30])
        s.type_value(p.position_fields[0].widget, "0")


def g_moved():
    box_is("corner moved to X 0", bbox(), [0, 10, 20, 30, 50, 30])


def g_ok():
    h.task_button("OK")


def g_done():
    box_is("kept", bbox(), [0, 10, 20, 30, 50, 30])
    h.check("four Move steps", len(moves()) == 4, moves())


h.run(
    "bodies_move",
    [s.new_design("Move")]
    + s.box_steps("body", (0, 0, 40, 30), 10, V(12, -8, 0))
    + [
        a_press_m,
        a_waits,
        a_click_body,
        a_manipulator,
        a_drag_x,
        a_dragged,
        a_type,
        a_typed,
        a_ok,
        a_done,
        a_undo,
        a_undone,
        a_redo,
        a_redone,
        b_edit,
        b_change,
        b_ok,
        b_done,
        c_select,
        c_press_m,
        c_translate,
        c_drag_z,
        c_dragged,
        c_type,
        c_ok,
        c_done,
        d_open,
        d_click_body,
        d_rotate,
        d_axes_shown,
        d_click_z_axis,
        d_type_angle,
        d_turned,
        d_drag_handle,
        d_dragged,
        d_ok,
        d_done,
        e_open,
        e_click_body,
        e_point_to_point,
        e_from,
        e_to,
        e_preview,
        e_ok,
        e_done,
        e_undo,
        e_undone,
        f_open,
        f_click_body,
        f_type,
        f_preview,
        f_cancel,
        f_cancelled,
        f_escape_open,
        f_escape,
        f_escaped,
        g_open,
        g_click_body,
        g_type,
        g_click_corner,
        g_prefilled,
        g_moved,
        g_ok,
        g_done,
    ],
)
