# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the Sweep / Loft / Rib / Web scenarios (scenarios/sweep_loft*.py).
Kept outside scenarios/ because every file there is run as a scenario.

Everything acts like a person: ribbon menu entries, clicks in the 3D view (curves are
clicked with harness.click_edge), typing into the dialog's fields, dragging handles,
double-clicking the timeline."""
import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si

V = App.Vector


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def bbox(shape):
    b = shape.optimalBoundingBox(False, False)
    return [round(v, 3) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]


def volume(body=None):
    body = body or h.body()
    try:
        return body.Shape.Volume if body is not None and not body.Shape.isNull() else 0.0
    except Exception:
        return 0.0


def total_volume(doc=None):
    doc = doc or App.ActiveDocument
    total = 0.0
    for obj in doc.Objects:
        if obj.TypeId == "PartDesign::Body":
            try:
                if not obj.Shape.isNull():
                    total += obj.Shape.Volume
            except Exception:
                pass
    return total


def panel(kind):
    """The open Sweep / Loft / Rib / Web dialog, or None."""
    import importlib

    module, name = {
        "sweep": ("sweep_ui", "SweepPanel"),
        "loft": ("loft_ui", "LoftPanel"),
        "rib": ("rib_ui", "RibPanel"),
        "web": ("rib_ui", "RibPanel"),
    }[kind]
    cls = getattr(importlib.import_module("sciforge." + module), name)
    p = cls.last
    return p if p is not None and not p._closed else None


def menu(label):
    """CREATE > label in the ribbon, clicked with the mouse."""
    return si.menu_item("CREATE", label)


def sketch_on(plane_point):
    """Create Sketch from the ribbon, then (next step) click the plane at plane_point."""
    h.ribbon("Create Sketch")


def add_lines(sketch, points, closed=False):
    """Connected lines through sketch points [(x, y), ...] (coincident ends)."""
    import Sketcher

    first = sketch.GeometryCount
    count = len(points) if closed else len(points) - 1
    for i in range(count):
        a = points[i]
        b = points[(i + 1) % len(points)]
        sketch.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(b[0], b[1], 0)))
    for i in range(count - 1 if not closed else count):
        sketch.addConstraint(
            Sketcher.Constraint("Coincident", first + i, 2, first + (i + 1) % count, 1)
        )
    App.ActiveDocument.recompute()
    return list(range(first, first + count))


def add_arc(sketch, center, radius, a0, a1):
    """Arc (degrees, counter-clockwise from a0 to a1) in sketch coordinates."""
    import math

    arc = Part.ArcOfCircle(
        Part.Circle(V(center[0], center[1], 0), V(0, 0, 1), radius),
        math.radians(a0),
        math.radians(a1),
    )
    index = sketch.addGeometry(arc)
    App.ActiveDocument.recompute()
    return index


def add_point(sketch, x, y):
    index = sketch.addGeometry(Part.Point(V(x, y, 0)))
    App.ActiveDocument.recompute()
    return index


def drag_path_handle(handle, target, steps=20):
    """Drag a PathHandle's ball along its path to `target` (0..1), as a hand does."""
    widget = h.gl_widget()
    start = handle.value()
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


def timeline_titles():
    from SciForgeTests.gui import blend_steps

    return blend_steps.timeline_titles()


def edit_in_timeline(title):
    """A person's double-click on the timeline step (the first click selects it)."""
    from SciForgeTests.gui import blend_steps

    return blend_steps.timeline_double_click(title, click_first=True)


def features(kind, doc=None):
    doc = doc or App.ActiveDocument
    found = []
    for o in doc.Objects:
        t = o.TypeId
        sf = getattr(o, "SciForgeType", "")
        if kind == "sweep" and (
            t in ("PartDesign::AdditivePipe", "PartDesign::SubtractivePipe") or sf == "Sweep"
        ):
            found.append(o)
        elif kind == "loft" and (
            t in ("PartDesign::AdditiveLoft", "PartDesign::SubtractiveLoft") or sf == "Loft"
        ):
            found.append(o)
        elif kind in ("rib", "web") and sf == kind.capitalize():
            found.append(o)
    return found


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


def add_arc3(sketch, a, b, c):
    """Arc through three sketch points [(x, y), (x, y), (x, y)]."""
    index = sketch.addGeometry(Part.Arc(V(a[0], a[1], 0), V(b[0], b[1], 0), V(c[0], c[1], 0)))
    App.ActiveDocument.recompute()
    return index


def hide_in_browser(obj):
    """Click the eye of `obj`'s row in the browser."""
    from SciForgeTests.gui import timeline_input as ti

    return ti.click_eye(obj.Label)


def simpson(f, a, b, n=2000):
    """Integral of f from a to b (Simpson's rule, n even)."""
    hstep = (b - a) / n
    total = f(a) + f(b)
    for k in range(1, n):
        total += f(a + k * hstep) * (4 if k % 2 else 2)
    return total * hstep / 3.0


# -- QA helpers (scenarios/sweep_loft_qa*.py) ---------------------------------------------------
def esc():
    h.press(QtCore.Qt.Key_Escape)


def ctrl(letter):
    """Ctrl+<letter> on the 3D view (Ctrl+Z, Ctrl+Y, Ctrl+S), like a person's keyboard."""
    h.press(getattr(QtCore.Qt, "Key_" + letter.upper()), QtCore.Qt.ControlModifier)


def message(kind):
    p = panel(kind)
    return p.message.text() if p is not None else ""


def dialog_open():
    return bool(Gui.Control.activeDialog())


def undo_counts():
    doc = App.ActiveDocument
    return (doc.UndoCount, doc.RedoCount)


def drag_ball_to(handle, point, steps=20):
    """Press on a PathHandle's ball and drag it to the screen spot of the 3D `point` (which
    may lie far off the path: the ball follows the nearest point of the path)."""
    h.drag(h.screen_point(handle.point_at(handle.value())), h.screen_point(point), steps)


def circle_of(sketch, index=0):
    """(centre (global), radius) of the sketch's index-th circle as it was drawn."""
    found = si.circles(sketch, construction=False)
    if len(found) <= index:
        return None, 0.0
    g = found[index][1]
    return sketch.getGlobalPlacement().multVec(g.Center), g.Radius


def frustum(r, length, taper_deg):
    """Volume of a round profile r swept straight `length` with Fusion's taper angle (its
    side tilts by the angle: the end radius is r + length tan(angle))."""
    import math

    big = r + length * math.tan(math.radians(taper_deg))
    return math.pi * length * (r * r + r * big + big * big) / 3.0


def region_click(sketch, which=None, occluder=None):
    """Click inside an area of `sketch` (which(faces) picks one; default the only one) at a
    spot the camera sees past `occluder` (a global shape, or None)."""
    from SciForgeTests.gui import revolve_input as ri

    faces = [f for _sub, f in ri.regions(sketch)]
    face = which(faces) if which is not None else (faces[0] if faces else None)
    point = ri.visible_point(face, occluder) if face is not None else None
    h.check("a visible spot inside the area of %s" % sketch.Label, point is not None)
    if point is not None:
        pl.click_on_plane(point)
    return point


def named(name, fn, wait_ms=None):
    """A scenario step called `name` (the harness logs step names)."""

    def step():
        fn()

    step.__name__ = name
    if wait_ms:
        step.wait_ms = wait_ms
    return step
