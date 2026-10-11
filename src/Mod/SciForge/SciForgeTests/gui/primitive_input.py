# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the primitive scenarios (scenarios/primitives*.py): Box,
Cylinder, Sphere, Torus, Coil, Pipe. Kept outside scenarios/ because every file there is
run as a scenario."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h


def menu(label):
    """SOLID > CREATE > `label` (Box, Cylinder, Sphere, Torus, Coil, Pipe) with the mouse:
    the group's menu opens and the entry is clicked."""
    from SciForgeTests.gui import sketch_input

    return sketch_input.menu_item("CREATE", label)


def panel(cls_name=None):
    """The primitive dialog that is open (Box, Cylinder... or the class named), or None."""
    from sciforge import primitives_ui

    p = primitives_ui.PlacedPanel.last
    if cls_name is not None and (p is None or type(p).__name__ != cls_name):
        return None
    return p if p is not None and not p._closed else None


def pipe_panel():
    from sciforge import pipe_ui

    p = pipe_ui.PipePanel.last
    return p if p is not None and not p._closed else None


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def bbox(shape):
    b = shape.optimalBoundingBox(False, False)
    return [round(v, 3) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]


def drag_handle(handle, value, steps=20):
    """Drag a blue handle's ball to where its value is `value`, as a hand does: press on
    the ball, move in small steps, release."""
    widget = h.gl_widget()
    start = handle.value()
    points = [
        h.screen_point(handle.point_at(start + (value - start) * i / float(steps)))
        for i in range(steps + 1)
    ]
    h.move(points[0])
    QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, points[0])
    for p in points[1:]:
        pos = QtCore.QPointF(p)
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            pos,
            QtCore.QPointF(widget.mapToGlobal(p)),
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
    QtTest.QTest.mouseRelease(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, points[-1])
    QtWidgets.QApplication.processEvents()


def hover(point):
    """Move the mouse over a 3D point (the placing outline follows it)."""
    h.move(h.screen_point(point))


def steps_of(type_id_part, doc=None):
    doc = doc or App.ActiveDocument
    return [o for o in doc.Objects if type_id_part in o.TypeId]


def bodies(doc=None):
    doc = doc or App.ActiveDocument
    return [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]


def total_volume(doc=None):
    total = 0.0
    for body in bodies(doc):
        try:
            if not body.Shape.isNull():
                total += body.Shape.Volume
        except Exception:
            pass
    return total


def shown(body):
    try:
        tip = body.Tip
        return bool(
            body.ViewObject.Visibility
            and tip is not None
            and tip.ViewObject.Visibility
            and not tip.Shape.isNull()
        )
    except Exception:
        return False


def no_dialog():
    return not Gui.Control.activeDialog()
