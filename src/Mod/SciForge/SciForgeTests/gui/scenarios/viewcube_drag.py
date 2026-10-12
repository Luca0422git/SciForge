# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dragging the ViewCube orbits the model like Shift + middle-drag (Fusion: the cube is a
handle for the constrained orbit). Sideways drags turn about Z, up/down drags tilt, nothing
ever rolls; the cube itself does not move; a click with a shaky hand is still a click.

A block 40 x 30 x 10, isometric view. Drag the cube right 60 px: the view turned about Z
(the tilt is unchanged), level. Drag it down 40 px: tilted (the compass direction is
unchanged), level. A diagonal drag (up and left) and a loop back to the start: level. From the FRONT
view, a drag right and a Shift + middle-drag right on the view turn the same way (the
camera swings toward -X); a drag down on the cube and a Shift + middle-drag down both look
down on the model. A drag that ends over the model selects nothing. A click on RIGHT with
the mouse moving 3 px still turns to RIGHT."""
import math

import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import viewcube_input as vc

st = {}


def setup():
    vc.setup("ViewCubeDrag")


def remember():
    st["before"] = vc.orientation()
    st["axes"] = vc.axes()
    st["geometry"] = vc.cube().geometry().getRect()


def azimuth(view):
    return math.degrees(math.atan2(view.y, view.x))


def sideways():
    remember()
    vc.drag("top", 60, 0)


def sideways_done():
    view = vc.axes()[2]
    h.check("dragging the cube turned the view", vc.turned(st["before"]) > 20, vc.describe())
    h.check(
        "a sideways drag turns about Z (the tilt stays)",
        abs(view.z - st["axes"][2].z) < 1e-6,
        (view, st["axes"][2]),
    )
    h.check("no roll after the sideways drag", vc.roll() < 1e-6, vc.roll())
    h.check("the cube itself did not move", vc.cube().geometry().getRect() == st["geometry"])
    h.check("the drag was not taken as a click on TOP", not vc.looks_along((0, 0, -1), 1e-3))
    h.shot("1-sideways")
    remember()
    vc.drag("top", 0, 40)


def down_done():
    view = vc.axes()[2]
    h.check("the downward drag turned the view", vc.turned(st["before"]) > 15, vc.describe())
    h.check(
        "an up/down drag only tilts (compass direction kept)",
        abs(azimuth(view) - azimuth(st["axes"][2])) < 1e-3,
        (view, st["axes"][2]),
    )
    h.check("dragging down looks more from above", view.z < st["axes"][2].z, view)
    h.check("no roll after the downward drag", vc.roll() < 1e-6, vc.roll())
    remember()
    vc.drag("top", -50, -35)


def diagonal_done():
    h.check("the diagonal drag turned the view", vc.turned(st["before"]) > 20, vc.describe())
    h.check("no roll after the diagonal drag", vc.roll() < 1e-6, vc.roll())
    pos = vc.point("top")
    widget = vc.cube()
    QtTest.QTest.mousePress(widget, vc.LEFT, vc.NONE, pos)
    for dx, dy in ((40, 0), (40, 30), (0, 30), (0, 0)):
        for i in range(1, 7):
            vc._send_move(
                widget, QtCore.QPointF(pos.x() + dx * i / 6, pos.y() + dy * i / 6), vc.LEFT
            )
    QtTest.QTest.mouseRelease(widget, vc.LEFT, vc.NONE, pos)
    QtWidgets.QApplication.processEvents()


def loop_done():
    h.check("no roll after a loop back to the start", vc.roll() < 1e-6, vc.roll())
    h.shot("2-after-drags")
    vc.click("front")  # the cube part may have moved: aim at what is shown now


def shift_middle(dx, dy):
    """Shift + middle-drag on the 3D view (FreeCAD's orbit with Fusion's mouse)."""
    widget = h.gl_widget()
    c = QtCore.QPoint(widget.width() // 2, widget.height() // 2)
    shift, middle = QtCore.Qt.ShiftModifier, QtCore.Qt.MiddleButton
    h.move(c)
    QtTest.QTest.mousePress(widget, middle, shift, c)
    for i in range(1, 9):
        pos = QtCore.QPointF(c.x() + dx * i / 8, c.y() + dy * i / 8)
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
    QtTest.QTest.mouseRelease(widget, middle, shift, QtCore.QPoint(c.x() + dx, c.y() + dy))
    QtWidgets.QApplication.processEvents()


def front_drag_right():
    h.check("at FRONT", vc.looks_along((0, 1, 0)), vc.describe())
    vc.drag("front", 40, 0)
    st["cube_right"] = vc.axes()[2]
    vc.click("front-left")  # any visible part: then back to FRONT
    vc.click("front")
    shift_middle(40, 0)
    st["mouse_right"] = vc.axes()[2]
    vc.click("front-right")
    vc.click("front")
    vc.drag("front", 0, 40)
    st["cube_down"] = vc.axes()[2]
    vc.click("top-front")
    vc.click("front")
    shift_middle(0, 40)
    st["mouse_down"] = vc.axes()[2]


def compare_done():
    cr, mr, cd, md = st["cube_right"], st["mouse_right"], st["cube_down"], st["mouse_down"]
    h.check(
        "drag right on the cube swings the camera like Shift+middle-drag right",
        cr.x > 0.05 and mr.x > 0.05 and abs(cr.z) < 1e-6 and abs(mr.z) < 1e-6,
        (cr, mr),
    )
    h.check(
        "drag down on the cube looks down like Shift+middle-drag down",
        cd.z < -0.05 and md.z < -0.05 and abs(cd.x) < 1e-6 and abs(md.x) < 1e-6,
        (cd, md),
    )
    Gui.Selection.clearSelection()
    st["before"] = vc.orientation()
    # From the cube far out over the model: the button comes up over the 3D view.
    vc.drag("front", -200, 60, steps=20)


def over_model_done():
    h.check("a long drag out of the cube orbits too", vc.turned(st["before"]) > 30, vc.describe())
    h.check("no roll after the long drag", vc.roll() < 1e-6, vc.roll())
    h.check(
        "letting go over the model selects nothing",
        not Gui.Selection.getSelectionEx(),
        [s.ObjectName for s in Gui.Selection.getSelectionEx()],
    )
    h.fit()


def shaky_click():
    vc.click("right", wiggle=3)


def shaky_done():
    h.check(
        "a click that moved 3 px still turns to RIGHT",
        vc.looks_along((-1, 0, 0)) and vc.z_up(),
        vc.describe(),
    )
    h.shot("3-shaky-click")


h.run(
    "viewcube_drag",
    [
        setup,
        sideways,
        sideways_done,
        down_done,
        diagonal_done,
        loop_done,
        front_drag_right,
        compare_done,
        over_model_done,
        shaky_click,
        shaky_done,
    ],
)
