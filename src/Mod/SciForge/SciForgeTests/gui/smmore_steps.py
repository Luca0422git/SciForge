# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the sm-more SHEET METAL scenarios (scenarios/smmore_*.py): Bend,
Hem, Join by Bend, Corner Closure, Lofted Flange, sheet metal Fillet / Chamfer. Kept outside
scenarios/ because every file there is run as a scenario.

The starting sheet (a base flange plate, made with sm-forming's Flange code, and sketches
with bend lines) is set up in code, like other scenarios' setup; everything the tested
command does is real input: the SHEET METAL tab, its buttons and menus, clicks on faces and
edges in the 3D view, typing in the dialog, its handles, OK / Cancel / Esc, the timeline."""

import math

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as ins
from SciForgeTests.gui import sketch_input as si

V = App.Vector
T, R, K = 1.0, 1.0, 0.44
BA90 = math.pi / 2 * (R + K * T)
BENT90 = math.pi / 2 * ((R + T) ** 2 - R**2) / 2  # bent zone volume per mm of width


def close(a, b, tol=1e-4):
    return abs(a - b) <= tol * max(1.0, abs(b))


def new_design(name):
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument(name)
    return App.ActiveDocument


def plate(x0, y0, x1, y1, holes=(), label=None, z=0.0, body=None, plane="XY_Plane",
          outline=None):
    """A flat sheet metal plate 1 mm thick (rule Steel (mm): T = R = 1) from a rectangle on
    the XY plane (offset z): an extrude of the sheet's thickness in a body flagged as sheet
    metal, which is what a base flange makes."""
    from sciforge import commands, extrude, sheetmetal, sketch_ui

    doc = App.ActiveDocument
    if body is None:
        body = commands.ensure_body() if not doc.findObjects("PartDesign::Body") else None
        if body is None:
            from sciforge import components

            body = components.new_body_in(doc, None)
    planes = sketch_ui.origin_planes(body)
    sketch = body.newObject("Sketcher::SketchObject", "PlateSketch")
    sketch.AttachmentSupport = [(planes[plane], "")]
    sketch.MapMode = "FlatFace"
    sketch.AttachmentOffset = App.Placement(V(0, 0, z), App.Rotation())
    pts = [V(x0, y0, 0), V(x1, y0, 0), V(x1, y1, 0), V(x0, y1, 0)]
    if outline:
        pts = [V(x, y, 0) for x, y in outline]
    for i in range(len(pts)):
        sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % len(pts)]))
    for cx, cy, r in holes:
        sketch.addGeometry(Part.Circle(V(cx, cy, 0), V(0, 0, 1), r))
    doc.recompute()
    feature = extrude.make(body, sketch, {"distance": 1.0})
    sheetmetal.make_sheet_metal_body(body, "Steel (mm)")
    doc.recompute()
    if label:
        body.Label = label
    return body, feature


def new_body():
    from sciforge import components

    return components.new_body_in(App.ActiveDocument, None)


def edge_flange(body, point, height):
    """An edge flange (sm-forming's Flange code) on the straight edge of the body's end
    through `point`."""
    from sciforge import sheetmetal_flange as flange

    tip = body.Tip
    vertex = Part.Vertex(point)
    name = None
    for i, edge in enumerate(tip.Shape.Edges, 1):
        if edge.distToShape(vertex)[0] < 1e-4:
            name = "Edge%d" % i
            break
    feature = flange.make(App.ActiveDocument, "edge", [(tip, name)], {"height": height})
    App.ActiveDocument.recompute()
    return feature


def profile_sketch(body, curves, z=0.0):
    """A sketch on XY at height z with lines (x0, y0, x1, y1) and circles ("c", cx, cy, r)."""
    from sciforge import sketch_ui

    planes = sketch_ui.origin_planes(body)
    sketch = body.newObject("Sketcher::SketchObject", "Profile")
    sketch.AttachmentSupport = [(planes["XY_Plane"], "")]
    sketch.MapMode = "FlatFace"
    sketch.AttachmentOffset = App.Placement(V(0, 0, z), App.Rotation())
    for c in curves:
        if c[0] == "c":
            sketch.addGeometry(Part.Circle(V(c[1], c[2], 0), V(0, 0, 1), c[3]))
        else:
            sketch.addGeometry(Part.LineSegment(V(c[0], c[1], 0), V(c[2], c[3], 0)))
    App.ActiveDocument.recompute()
    return sketch


def bend_sketch(body, lines, z=1.0):
    """A sketch on the plate's top face (offset XY plane at z) with these lines [(x0, y0, x1,
    y1)]: the bend lines, drawn the way Fusion users do (on the face)."""
    from sciforge import sketch_ui

    doc = App.ActiveDocument
    planes = sketch_ui.origin_planes(body)
    sketch = body.newObject("Sketcher::SketchObject", "BendLines")
    sketch.AttachmentSupport = [(planes["XY_Plane"], "")]
    sketch.MapMode = "FlatFace"
    sketch.AttachmentOffset = App.Placement(V(0, 0, z), App.Rotation())
    for x0, y0, x1, y1 in lines:
        sketch.addGeometry(Part.LineSegment(V(x0, y0, 0), V(x1, y1, 0)))
    doc.recompute()
    return sketch


def tab():
    return ins.ribbon_tab("sheet_metal")


def menu(group, label):
    return si.menu_item(group, label)


def settle(panel=None, timeout_ms=8000):
    import time

    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        QtTest.QTest.qWait(50)
        p = panel
        if p is None:
            break
        timer = getattr(p, "_timer", None)
        busy = (
            (timer is not None and timer.isActive())
            or getattr(p, "_pending", False)
            or getattr(App.ActiveDocument, "Recomputing", False)
        )
        if not busy:
            break
    QtTest.QTest.qWait(80)


def panel(cls):
    p = getattr(cls, "last", None)
    if p is None or p._closed:
        return None
    return p


def type_into(p, key, text):
    field = p.number_fields[key]
    widget = getattr(field, "widget", field)
    ui.type_into(widget, text)


def choose(p, key, text):
    return ui.choose(p.fields[key], text)


def toggle(p, key):
    box = p.fields[key]
    QtTest.QTest.mouseClick(box, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(6, 6))
    QtWidgets_process()


def QtWidgets_process():
    from PySide import QtWidgets

    QtWidgets.QApplication.processEvents()


def click_box(p, name):
    ui.click(p.boxes[name].button)


def ok():
    return h.task_button("OK")


def cancel():
    return h.task_button("Cancel")


def esc():
    h.press(QtCore.Qt.Key_Escape)


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def timeline_titles():
    return ui.timeline_titles()


def double_click_timeline(title):
    return ui.double_click_timeline(title)


def steps(kind):
    from sciforge import bodies

    doc = App.ActiveDocument
    return [o for o in doc.Objects if bodies.kind(o) == kind]


def volume(body):
    try:
        shape = body.Shape
        return shape.Volume if not shape.isNull() and shape.Solids else 0.0
    except Exception:
        return 0.0


def message(p):
    return p.message.text() if p is not None else ""


def edge_point(a, b, f=0.5):
    return a + (b - a) * f
