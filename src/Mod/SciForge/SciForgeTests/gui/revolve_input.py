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


# -- QA helpers (scenarios/revolve_qa*.py) ------------------------------------------------------
def regions(sketch):
    """[(sub, face in global coordinates)] of a sketch's closed areas that are profiles
    (not the face's own area Auto project makes: extrude.profile_regions)."""
    from sciforge import extrude

    return extrude.profile_regions(sketch)


def taken(sketch):
    """[(sub, face in global coordinates)] of the areas Revolve takes by itself from a
    sketch (extrude.taken_by_itself: with the face's edges projected, what was drawn)."""
    from sciforge import extrude

    names = set(extrude.taken_by_itself(sketch))
    return [(sub, face) for sub, face in extrude.regions(sketch) if sub in names]


def pappus(face, point, direction, angle=360.0):
    """Volume a flat face sweeps turning `angle` degrees about the axis line (Pappus:
    area x the path of its centroid). The face must not cross the axis."""
    import math

    d = App.Vector(direction)
    d.normalize()
    c = face.CenterOfMass - point
    r = (c - d * c.dot(d)).Length
    return face.Area * 2.0 * math.pi * r * abs(angle) / 360.0


def visible_point(face, shape=None, margin=0.8):
    """A point inside a flat face (global) that the camera sees: no solid of `shape` in
    front of it and at least `margin` mm from the face's edges, the one nearest the
    middle. What a person aims at to click inside a sketch area."""
    from sciforge import profile_pick

    direction = h.view().getViewDirection()
    u0, u1, v0, v1 = face.ParameterRange
    centre = face.CenterOfMass
    best = None
    n = 24
    edges = face.OuterWire
    for i in range(1, n):
        for j in range(1, n):
            p = face.valueAt(u0 + (u1 - u0) * i / float(n), v0 + (v1 - v0) * j / float(n))
            if not face.isInside(p, 1e-6, True):
                continue
            import Part

            if edges.distToShape(Part.Vertex(p))[0] < margin:
                continue
            if any(w.distToShape(Part.Vertex(p))[0] < margin for w in face.Wires if w is not edges):
                continue
            if shape is not None and profile_pick.hidden_by(shape, p, direction):
                continue
            if best is None or (p - centre).Length < (best - centre).Length:
                best = p
    return best


def body_shape():
    """The part as shown (global), or None."""
    b = h.body()
    if b is None or b.Shape.isNull():
        return None
    return b.Shape


def handle_screen(handle, degrees=None):
    return h.screen_point(handle.point_at(handle.angle() if degrees is None else degrees))
