# SPDX-License-Identifier: LGPL-2.1-or-later
"""Helpers for the sketch_tools_* scenarios (SciForge's own sketch tools: sketch_draw.py
and the tools built on it). Real input only: menu clicks, mouse moves and clicks on the
3D view, keys typed where the keyboard is.

Kept outside scenarios/ because every file there is run as a scenario."""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}


def session():
    from sciforge import sketch_mode

    return sketch_mode.current()


def tool():
    """The SciForge tool running in the open sketch, or None."""
    from sciforge import sketch_draw

    return sketch_draw.current_tool()


def tool_title():
    t = tool()
    return t.title if t is not None else None


def sketch():
    return s.get("sk")


def g(point):
    """Sketch point -> global 3D point."""
    return sketch().getGlobalPlacement().multVec(point)


def move(point):
    """Move the pointer onto the sketch point (the screen's pointer too)."""
    pos = h.screen_point(g(point))
    QtGui.QCursor.setPos(h.gl_widget().mapToGlobal(pos))
    h.move(pos)
    return pos


def hover(point, towards=V(1.0, 0.6, 0)):
    """Come to the sketch point in a few steps, as a hand does, and rest there."""
    for f in (3.0, 1.5, 0.5, 0.0):
        move(point + towards * f)
    QtTest.QTest.qWait(60)


def click(point, towards=V(1.0, 0.6, 0), modifiers=QtCore.Qt.NoModifier):
    """Hover the sketch point, then click it (press and release there)."""
    hover(point, towards)
    pos = h.screen_point(g(point))
    QtTest.QTest.mouseClick(h.gl_widget(), QtCore.Qt.LeftButton, modifiers, pos)
    QtWidgets.QApplication.processEvents()
    return pos


def press(point):
    pos = h.screen_point(g(point))
    move(point)
    QtTest.QTest.qWait(60)
    QtTest.QTest.mousePress(h.gl_widget(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()
    return pos


def drag_to(point, steps=10):
    """Move with the left button held to the sketch point (events only: moving the
    screen's pointer during a press makes the virtual screen send a move with no
    button, which ends the gesture)."""
    widget = h.gl_widget()
    start = widget.mapFromGlobal(QtGui.QCursor.pos())
    end = h.screen_point(g(point))
    for i in range(1, steps + 1):
        pos = QtCore.QPointF(
            start.x() + (end.x() - start.x()) * i / steps,
            start.y() + (end.y() - start.y()) * i / steps,
        )
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            pos,
            QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
    return end


def release(pos):
    QtTest.QTest.mouseRelease(h.gl_widget(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()


def keys(text):
    """Type on the keyboard (to the widget with the keyboard focus, like a real one)."""
    target = QtWidgets.QApplication.focusWidget() or h.gl_widget()
    for ch in text:
        if ch == "\t":
            QtTest.QTest.keyClick(target, QtCore.Qt.Key_Tab)
        elif ch == "\n":
            QtTest.QTest.keyClick(target, QtCore.Qt.Key_Return)
        else:
            QtTest.QTest.keyClicks(target, ch)
        QtWidgets.QApplication.processEvents()
        target = QtWidgets.QApplication.focusWidget() or target


def esc():
    si.key(QtCore.Qt.Key_Escape)


def enter():
    si.key(QtCore.Qt.Key_Return)


def undo():
    h.press("z", QtCore.Qt.ControlModifier)


def redo():
    h.press("y", QtCore.Qt.ControlModifier)


def cross_cursor():
    from sciforge import sketch_mode

    sess = sketch_mode.current()
    widget = sess.viewer if sess is not None and sess.viewer is not None else h.gl_widget()
    return widget.cursor().shape() == QtCore.Qt.CrossCursor


def new_geometry(before):
    """(index, geometry) of the curves added since `before` curves."""
    sk = sketch()
    return [(i, sk.Geometry[i]) for i in range(before, len(sk.Geometry))]


def of_type(items, type_id, construction=None):
    sk = sketch()
    return [
        (i, geo)
        for i, geo in items
        if geo.TypeId == type_id
        and (construction is None or bool(sk.getConstruction(i)) == construction)
    ]


def constraints_of(geo):
    """The constraints that name curve `geo`: [(type, first, firstpos, second, secondpos)]."""
    out = []
    for c in sketch().Constraints:
        if geo in (c.First, c.Second, getattr(c, "Third", -2000)):
            out.append((c.Type, c.First, c.FirstPos, c.Second, c.SecondPos))
    return out


def types(items):
    return [c[0] for c in items]


def vnear(p, q, tol=1e-6):
    return (V(p) - V(q)).Length <= tol


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol


def preview():
    t = tool()
    return t.preview.drawn() if t is not None else {}


def field(name):
    t = tool()
    if t is None:
        return None
    return t.boxes.field(name)


def box_texts():
    """The texts of the value boxes shown on the 3D view."""
    from sciforge import sketch_draw

    return [
        b.text()
        for b in h.gl_widget().findChildren(QtWidgets.QLineEdit, sketch_draw.BOX_NAME)
        if b.isVisible()
    ]


def sketch_ok(where):
    """The sketch solves (no conflicting or redundant constraints)."""
    sk = sketch()
    code = sk.solve()
    h.check(
        "%s: the sketch solves cleanly" % where,
        code == 0 and not sk.ConflictingConstraints and not sk.RedundantConstraints,
        (code, sk.ConflictingConstraints, sk.RedundantConstraints),
    )


def new_design(name):
    def step():
        Gui.activateWorkbench("SciForgeWorkbench")
        App.newDocument(name)
        h.fit()

    step.__name__ = "new_design"
    return step


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the XY square shows


def sketch_open():
    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open", sk is not None)


def start_steps(name):
    return [new_design(name), create_sketch, pick_xy, sketch_open]


def angle_deg(a, b):
    """Angle between two directions (degrees)."""
    c = a.dot(b) / (a.Length * b.Length)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))
