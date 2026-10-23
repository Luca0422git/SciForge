# SPDX-License-Identifier: LGPL-2.1-or-later
"""Helpers for the SURFACE > MODIFY on surface bodies scenarios (scenarios/surface4_*.py).
Kept outside scenarios/ because every file there is run as a scenario.

The starting surfaces are made in setup by the same SciForge code the SURFACE dialogs run
(surface.build: Extrude, Patch, Stitch; their own scenarios click them); the actions under
test are done with real input: the ribbon, keys, clicks in the 3D view, typing, the
timeline."""

import time

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st

V = App.Vector


def new_design(name):
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument(name)


def sketch(points, plane="XY_Plane", closed=True, body=None, offset=0.0):
    """A sketch of straight lines in a (new) solid body's origin plane."""
    import Sketcher

    from sciforge import commands, sketch_ui

    body = body or commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes[plane], ""))
    if offset:
        sk.AttachmentOffset = App.Placement(V(0, 0, offset), App.Rotation())
    count = len(points) if closed else len(points) - 1
    for i in range(count):
        a, b = points[i], points[(i + 1) % len(points)]
        sk.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(b[0], b[1], 0)))
    for i in range(count if closed else count - 1):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % count, 1))
    _leave()
    App.ActiveDocument.recompute()
    return sk


def arc_sketch(cx, cy, r, a0, a1, plane="XZ_Plane", body=None):
    import math

    from sciforge import commands, sketch_ui

    body = body or commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes[plane], ""))
    circle = Part.Circle(V(cx, cy, 0), V(0, 0, 1), r)
    sk.addGeometry(Part.ArcOfCircle(circle, math.radians(a0), math.radians(a1)))
    _leave()
    App.ActiveDocument.recompute()
    return sk


def _leave():
    from sciforge import commands

    try:
        commands.leave_edit()
    except Exception:
        pass
    QtWidgets.QApplication.processEvents()


def edges(sk):
    return [(sk, "Edge%d" % (i + 1)) for i in range(len(sk.Shape.Edges))]


def surface_box(width=30.0, depth=20.0, height=10.0):
    """An open box of surfaces (four walls and a floor, no lid) in one surface body: a
    surface Extrude of a rectangle, a Patch of the same rectangle, Stitch. Returns the body."""
    from sciforge import bodies, surface

    sk = sketch([(0, 0), (width, 0), (width, depth), (0, depth)])
    walls = surface.build("extrude", {"refs": edges(sk)}, {"distance": height})
    App.ActiveDocument.recompute()
    floor = surface.build("patch", {"refs": edges(sk)}, {})
    App.ActiveDocument.recompute()
    pieces = [(bodies.body_of(walls), ""), (bodies.body_of(floor), "")]
    stitch = surface.build("stitch", {"refs": pieces}, {})
    App.ActiveDocument.recompute()
    bodies.set_shown(sk, False)
    return bodies.body_of(stitch)


def panel():
    from sciforge import surfmod_ui

    p = surfmod_ui.SurfaceModifyPanel.last
    return p if p is not None and not p._closed else None


def settle(timeout_ms=8000):
    p = panel()
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        QtTest.QTest.qWait(50)
        if p is None:
            break
        timer = getattr(p, "_timer", None)
        busy = (timer is not None and timer.isActive()) or getattr(
            App.ActiveDocument, "Recomputing", False
        )
        if not busy:
            break
    QtTest.QTest.qWait(100)


def type_main(text):
    """Type into the dialog's size field (Radius / Distance)."""
    p = panel()
    if p is None:
        h.check("surface dialog open to type", False)
        return
    field = p.fields[p.main_key()][0]
    ui.type_into(field.widget, text)


def message():
    p = panel()
    return p.message.text() if p is not None else ""


def faces(body):
    try:
        return len(body.Shape.Faces)
    except Exception:
        return 0


def near(a, b, tol=1e-6):
    return st.near(a, b, tol)


def edge_name_at(body, point):
    """The edge of a body's shape through `point` (a person sees it there)."""
    probe = Part.Vertex(point)
    for i, e in enumerate(body.Shape.Edges, start=1):
        if e.distToShape(probe)[0] < 1e-6:
            return "Edge%d" % i
    return None


def press(key, modifiers=QtCore.Qt.NoModifier):
    h.press(key, modifiers)
