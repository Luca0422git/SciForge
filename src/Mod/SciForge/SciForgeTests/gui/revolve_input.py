# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the Revolve scenarios (scenarios/revolve*.py). Kept outside
scenarios/ because every file there is run as a scenario."""
import FreeCAD as App
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h


def panel():
    """The Revolve dialog that is open, or None."""
    from sciforge import revolve_ui

    p = revolve_ui.RevolvePanel.last
    return p if p is not None and not p._closed else None


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def bbox(shape):
    """Exact bounding box of a shape, rounded: [xmin, ymin, zmin, xmax, ymax, zmax]."""
    b = shape.optimalBoundingBox(False, False)
    return [round(v, 4) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]


def drag_handle(handle, target, steps=24):
    """Drag a revolve handle's ball round the axis to `target` degrees along its circle,
    as a hand does: press on the ball, move in small steps, release."""
    widget = h.gl_widget()
    start = handle.angle()
    points = [
        h.screen_point(handle.point_at(start + (target - start) * i / float(steps)))
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


def revolves(doc=None):
    doc = doc or App.ActiveDocument
    return [
        o
        for o in doc.Objects
        if o.TypeId in ("PartDesign::Revolution", "PartDesign::Groove")
        or getattr(o, "SciForgeType", "") == "Revolve"
    ]


def shown(body):
    """True if the body's solid is on screen (the body and its last feature visible)."""
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
