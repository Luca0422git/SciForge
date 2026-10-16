# SPDX-License-Identifier: LGPL-2.1-or-later
"""Angle handles snap to 0 / 45 / 90 / 135 ... and show a protractor wheel while held (Luca's
choice: always on, Ctrl held = free; "maybe add a visual wheel of where its snapping and the
angle its at"). Only real input: the handles are pressed, moved and let go in separate steps
so the wheel can be looked at while the mouse button is down.

Setup: Create Sketch on XZ, a 10 x 20 rectangle against the Z axis, Finish; Revolve, click
the Z axis (a full turn), type 60.

  A  Revolve's angle handle, pressed: the wheel appears (ticks every 15 degrees, long ones at
     45 / 90). Moved to 89.3 degrees: the angle is exactly 90, the 90 tick is lit, the wheel
     says "90.0 deg". Let go: the wheel is gone, the dialog says 90, a quarter cylinder.
  B  Moved to 70: no snap (about 70), nothing lit.
  C  Ctrl held, moved to 89.3: about 89.3, not 90 (free); Ctrl let go.
  D  Incremental Move on (angle steps of 10): moved to 37: 40, the steps win; off again.
  E  OK: one Revolve of 90 degrees (a quarter of 2000 pi). Undo / Redo.
  F  Move/Copy (M) on the body, the turn handle about Z dragged 89.3 degrees round: Z Angle
     is exactly 90, the wheel showed it while held; Esc: nothing moved.
  G  Extrude's taper disc (a Coin dragger): a sketch rectangle on XY away from the body, E,
     the taper disc dragged to 44.2: the taper is exactly 45 (the snap also holds at the
     release); Esc.
  H  Ctrl on the taper disc: dragged to 44.2 with Ctrl: about 44.2, not 45 (free); Esc:
     nothing made.
"""

import math

import FreeCAD as App
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import revolve_input as ri

V = App.Vector
PI = math.pi
CYL = 2000.0 * PI
state = {}


def wheels():
    from sciforge import protractor

    return protractor.WHEELS


def last():
    from sciforge import protractor

    return protractor.LAST


# -- held drags (press, move and release in separate steps) -------------------------------------
def press_on(point):
    widget = h.gl_widget()
    pixel = h.screen_point(point)
    h.move(pixel)
    QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pixel)
    QtWidgets.QApplication.processEvents()
    state["at"] = pixel


def move_through(points):
    """Move with the left button held through 3D points, a small step at a time."""
    widget = h.gl_widget()
    for point in points:
        pixel = h.screen_point(point)
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            QtCore.QPointF(pixel),
            QtCore.QPointF(widget.mapToGlobal(pixel)),
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
        state["at"] = pixel


def release():
    widget = h.gl_widget()
    QtTest.QTest.mouseRelease(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, state["at"])
    QtWidgets.QApplication.processEvents()


def ctrl(down):
    """Hold / let go of Ctrl (a key event on the 3D view, as the keyboard sends it)."""
    widget = h.gl_widget()
    if down:
        QtTest.QTest.keyPress(widget, QtCore.Qt.Key_Control, QtCore.Qt.ControlModifier)
    else:
        QtTest.QTest.keyRelease(widget, QtCore.Qt.Key_Control, QtCore.Qt.NoModifier)
    QtWidgets.QApplication.processEvents()


def arc(handle, start, end, step=3.0):
    count = max(1, int(abs(end - start) / step))
    return [handle.point_at(start + (end - start) * i / count) for i in range(1, count + 1)]


def handle():
    p = ri.panel()
    return p.handles.get("angle") if p is not None else None


def turn_revolve_to(target):
    hd = handle()
    if not h.check("Revolve angle handle", hd is not None):
        return
    press_on(hd.point_at(hd.angle()))
    move_through(arc(hd, hd.angle(), target))


# -- setup --------------------------------------------------------------------------------------
def sketch():
    h.ribbon("Create Sketch")


def pick_xz():
    h.click(V(12, 0, 8))


def draw():
    sk = h.in_sketch()
    h.check("sketch on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk is not None:
        h.draw_rectangle(sk, 0, 0, 10, 20)


def finish():
    h.ribbon("Finish Sketch")


def revolve():
    h.click_empty()
    h.fit()
    h.ribbon("Revolve")


def click_z():
    h.fit()
    h.click(V(0, 0, 32))


def type_60():
    p = ri.panel()
    if h.check("Z axis picked", p is not None and p.axis is not None, p and p.axis):
        ui.type_into(p.angle.widget, "60")


# -- A ------------------------------------------------------------------------------------------
def a_press():
    p = ri.panel()
    h.check("60 typed", p is not None and abs(p.angle.value() - 60.0) < 1e-6)
    h.fit()
    hd = handle()
    if h.check("Revolve angle handle", hd is not None):
        press_on(hd.point_at(hd.angle()))


def a_wheel_up():
    h.check("pressed: the protractor wheel is shown", len(wheels()) == 1, wheels())
    hd = handle()
    if hd is not None:
        move_through(arc(hd, 60.0, 89.3))


def a_snapped():
    hd = handle()
    h.check(
        "89.3 snaps to exactly 90",
        hd is not None and abs(hd.angle() - 90.0) < 1e-9,
        hd and hd.angle(),
    )
    h.check("the 90 tick is lit", last()["mark"] == 90.0, last())
    h.check("the wheel says 90.0 deg", last()["text"] == "90.0 deg", last())
    h.shot("A-wheel-90")
    release()


def a_released():
    h.check("let go: the wheel is gone", not wheels(), wheels())
    p = ri.panel()
    h.check(
        "the dialog says 90",
        p is not None and abs(p.angle.value() - 90.0) < 1e-9,
        p and p.angle.value(),
    )


a_released.wait_ms = 1500


def a_quarter():
    v = h.solid_volume()
    h.check("a quarter cylinder", ri.near(v, CYL / 4.0, 1e-6), v)


# -- B ------------------------------------------------------------------------------------------
def b_drag_70():
    turn_revolve_to(70.0)


def b_free():
    hd = handle()
    h.check(
        "70: no snap",
        hd is not None and abs(hd.angle() - 70.0) < 1.0 and abs(hd.angle() - 90.0) > 5.0,
        hd and hd.angle(),
    )
    h.check("nothing lit", last()["mark"] is None, last())
    release()


# -- C ------------------------------------------------------------------------------------------
def c_ctrl_press():
    hd = handle()
    if h.check("Revolve angle handle", hd is not None):
        press_on(hd.point_at(hd.angle()))
        ctrl(True)


def c_ctrl_move():
    hd = handle()
    if hd is not None:
        move_through(arc(hd, hd.angle(), 89.3))


def c_free():
    hd = handle()
    h.check(
        "Ctrl held: about 89.3, not snapped",
        hd is not None and abs(hd.angle() - 89.3) < 0.6 and abs(hd.angle() - 90.0) > 1e-3,
        hd and hd.angle(),
    )
    h.check("Ctrl: nothing lit", last()["mark"] is None, last())
    release()
    ctrl(False)


# -- D ------------------------------------------------------------------------------------------
def d_increments_on():
    from sciforge import increments

    increments._group().SetBool("IncrementalMove", True)
    increments.set_steps(angular=10.0)
    h.check("Incremental Move on", increments.is_on())
    turn_revolve_to(37.0)


def d_steps():
    hd = handle()
    h.check(
        "in steps of 10: 40", hd is not None and abs(hd.angle() - 40.0) < 1e-9, hd and hd.angle()
    )
    release()


def d_increments_off():
    from sciforge import increments

    increments.reset()
    turn_revolve_to(89.3)


def d_snapped_again():
    hd = handle()
    h.check("off again: 90", hd is not None and abs(hd.angle() - 90.0) < 1e-9, hd and hd.angle())
    release()


# -- E ------------------------------------------------------------------------------------------
def e_ok():
    h.task_button("OK")


def e_done():
    h.check("dialog closed", ri.panel() is None)
    revs = ri.revolves()
    h.check(
        "one Revolve of 90",
        len(revs) == 1 and abs(revs[0].Angle.Value - 90.0) < 1e-9,
        [(r.Name, r.Angle) for r in revs],
    )
    h.check("a quarter of 2000 pi", ri.near(h.solid_volume(), CYL / 4.0), h.solid_volume())


def e_undo():
    s.undo()


def e_undone():
    h.check("undo: no solid", h.solid_volume() == 0.0, h.solid_volume())
    s.redo()


def e_redone():
    h.check("redo: a quarter again", ri.near(h.solid_volume(), CYL / 4.0), h.solid_volume())


# -- F ------------------------------------------------------------------------------------------
def f_move():
    h.click_empty()
    h.fit()
    h.press("m")


def f_pick():
    bb = s.bodies()[0].Shape.BoundBox
    h.click(V(bb.Center.x, bb.Center.y, bb.ZMax))  # the top of the quarter cylinder


def f_press():
    p = s.panel()
    triad = getattr(p, "triad", None)
    if not h.check("manipulator shown", triad is not None):
        return
    state["box"] = s.bodies()[0].Shape.BoundBox
    state["centre"] = V(triad.center)
    press_on(triad.ball_point(2))


def f_turn():
    p = s.panel()
    triad = getattr(p, "triad", None)
    if triad is None:
        return
    h.check("the turn handle is held", triad.dragging(), triad._drag)
    u, v = triad._frame(2)
    r = 0.6 * triad.size
    centre = state["centre"]
    points = [
        centre + u * (r * math.cos(math.radians(a))) + v * (r * math.sin(math.radians(a)))
        for a in [45.0 + 89.3 * i / 30.0 for i in range(1, 31)]
    ]
    move_through(points)


def f_held():
    h.check("the wheel is shown while turning", len(wheels()) == 1, wheels())
    h.check("the turn sits on 90", last()["mark"] == 90.0, last())
    h.shot("F-move-wheel")
    release()


def f_turned():
    h.check("let go: the wheel is gone", not wheels(), wheels())
    p = s.panel()
    rz = p.options.get("rz") if p is not None else None
    h.check("turned exactly 90 about Z", rz is not None and abs(rz - 90.0) < 1e-9, rz)
    h.press(QtCore.Qt.Key_Escape)


f_turned.wait_ms = 1500


def f_cancelled():
    box = s.bodies()[0].Shape.BoundBox
    old = state.get("box")
    same = old is not None and all(
        abs(getattr(box, k) - getattr(old, k)) < 1e-6
        for k in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
    )
    h.check("Esc: nothing moved", same, (old, box))


# -- G ------------------------------------------------------------------------------------------
def g_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def g_pick_xy():
    h.click(V(5, -5, 0))  # inside the XY square (20 mm: the part is 20 mm)


def g_draw():
    sk = h.in_sketch()
    h.check("sketch on XY", sk is not None)
    if sk is not None:
        h.draw_rectangle(sk, 25, -40, 45, -20)


def g_finish():
    h.ribbon("Finish Sketch")


def g_extrude():
    h.click_empty()
    h.fit()
    h.press("e")


def g_profile():
    h.click(V(35, -30, 0))


def g_taper_press():
    p = s.panel()
    taper = getattr(p, "draggers", {}).get("taper") if p is not None else None
    if not h.check("taper disc shown", taper is not None, p and list(getattr(p, "draggers", {}))):
        return
    h.fit()
    press_on(taper.point_at(taper.angle()))


def g_taper_turn():
    p = s.panel()
    taper = p.draggers.get("taper") if p is not None else None
    if taper is not None:
        move_through(arc(taper, 0.0, 44.2, step=2.0))


def g_taper_held():
    h.check("the wheel is shown on the taper disc", len(wheels()) == 1, wheels())
    h.check("the taper sits on 45", last()["mark"] == 45.0, last())
    h.shot("G-taper-wheel")
    release()


def g_taper_done():
    p = s.panel()
    h.check("let go: the wheel is gone", not wheels(), wheels())
    value = p.taper.value() if p is not None else None
    h.check("the taper is exactly 45", value is not None and abs(abs(value) - 45.0) < 1e-6, value)
    if p is not None:
        ui.type_into(p.taper.widget, "0")


# -- H ------------------------------------------------------------------------------------------
def h_ctrl_press():
    p = s.panel()
    taper = p.draggers.get("taper") if p is not None else None
    if h.check("taper disc shown", taper is not None):
        h.fit()
        press_on(taper.point_at(taper.angle()))
        ctrl(True)


def h_ctrl_turn():
    p = s.panel()
    taper = p.draggers.get("taper") if p is not None else None
    if taper is not None:
        move_through(arc(taper, 0.0, 44.2, step=2.0))


def h_ctrl_free():
    release()
    ctrl(False)


def h_free_value():
    p = s.panel()
    value = p.taper.value() if p is not None else None
    h.check(
        "Ctrl: the taper is free (near 44.2, not snapped to 45)",
        value is not None and abs(abs(value) - 45.0) > 0.05 and abs(abs(value) - 44.2) < 4.0,
        value,
    )
    h.press(QtCore.Qt.Key_Escape)


def h_cancelled():
    h.check(
        "Esc: one body, the quarter cylinder",
        len(s.bodies()) == 1 and ri.near(h.solid_volume(), CYL / 4.0),
        (len(s.bodies()), h.solid_volume()),
    )
    h.check("Esc: no dialog", s.panel() is None)


h.run(
    "view_angle_snap",
    [
        s.new_design("AngleSnap"),
        sketch,
        pick_xz,
        draw,
        finish,
        revolve,
        click_z,
        type_60,
        a_press,
        a_wheel_up,
        a_snapped,
        a_released,
        a_quarter,
        b_drag_70,
        b_free,
        c_ctrl_press,
        c_ctrl_move,
        c_free,
        d_increments_on,
        d_steps,
        d_increments_off,
        d_snapped_again,
        e_ok,
        e_done,
        e_undo,
        e_undone,
        e_redone,
        f_move,
        f_pick,
        f_press,
        f_turn,
        f_held,
        f_turned,
        f_cancelled,
        g_sketch,
        g_pick_xy,
        g_draw,
        g_finish,
        g_extrude,
        g_profile,
        g_taper_press,
        g_taper_turn,
        g_taper_held,
        g_taper_done,
        h_ctrl_press,
        h_ctrl_turn,
        h_ctrl_free,
        h_free_value,
        h_cancelled,
    ],
)
