# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shift + middle-drag orbits like Fusion's Constrained Orbit: the model turns about its up
axis (Z) and tilts toward or away from you, but never rolls, so vertical edges stay
vertical on screen. (Luca: FreeCAD's orbit "goes off axis and it's hard to get it back";
FreeCAD 1.1's default orbit, Rounded Arcball, rolls the model.)

A box 40 x 30 x 10 (real input), isometric view. Three Shift + middle drags: diagonal down
and right, a loop that ends where it started (a rolling orbit tips most there), and a long
one up and left. After each: the view turned, and the camera's sideways direction is level
(no roll: the Z axis still points straight up the screen)."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
st = {}


def camera():
    return Gui.ActiveDocument.ActiveView.getCameraOrientation()


def roll_of(rotation):
    """How far the camera's sideways direction leaves the level (0 = no roll)."""
    return abs(rotation.multVec(V(1, 0, 0)).z)


def turned_from(before):
    """Degrees between two camera orientations."""
    import math

    return math.degrees(before.inverted().multiply(camera()).Angle)


def orbit_along(points):
    """Shift + middle button down at the first pixel, through the others, up at the last."""
    widget = h.gl_widget()
    shift, middle = QtCore.Qt.ShiftModifier, QtCore.Qt.MiddleButton
    h.move(points[0])
    QtTest.QTest.mousePress(widget, middle, shift, points[0])
    for a, c in zip(points, points[1:]):
        for i in range(1, 9):
            pos = QtCore.QPointF(a.x() + (c.x() - a.x()) * i / 8, a.y() + (c.y() - a.y()) * i / 8)
            event = QtGui.QMouseEvent(
                QtCore.QEvent.MouseMove,
                pos,
                QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
                QtCore.Qt.NoButton,
                middle,
                shift,
            )
            QtWidgets.QApplication.sendEvent(widget, event)
            QtWidgets.QApplication.processEvents()
    QtTest.QTest.mouseRelease(widget, middle, shift, points[-1])
    QtWidgets.QApplication.processEvents()


def centre():
    widget = h.gl_widget()
    return QtCore.QPoint(widget.width() // 2, widget.height() // 2)


def offset(dx, dy):
    c = centre()
    return QtCore.QPoint(c.x() + dx, c.y() + dy)


def start():
    group = App.ParamGet("User parameter:BaseApp/Preferences/View")
    h.check(
        "constrained orbit is set", group.GetInt("OrbitStyle", 4) == 2, group.GetInt("OrbitStyle")
    )
    h.fit()
    st["before"] = camera()
    h.check("the isometric view is level", roll_of(st["before"]) < 1e-6, st["before"])


def diagonal():
    st["before"] = camera()
    orbit_along([offset(-60, -40), offset(140, 90)])


def diagonal_done():
    h.check("the diagonal drag turned the view", turned_from(st["before"]) > 10, camera())
    h.check("no roll after the diagonal drag", roll_of(camera()) < 1e-6, roll_of(camera()))
    h.shot("1-diagonal")
    st["before"] = camera()
    orbit_along([offset(0, 0), offset(150, 0), offset(150, 120), offset(0, 120), offset(0, 0)])


def loop_done():
    h.check("no roll after a loop back to the start", roll_of(camera()) < 1e-6, roll_of(camera()))
    st["before"] = camera()
    orbit_along([offset(160, 120), offset(-200, -150)])


def long_done():
    h.check("the long drag turned the view", turned_from(st["before"]) > 10, camera())
    h.check("no roll after the long drag", roll_of(camera()) < 1e-6, roll_of(camera()))
    h.shot("2-after-orbits")


h.run(
    "navigation_orbit",
    b.box_steps("Orbit") + [start, diagonal, diagonal_done, loop_done, long_done],
)
