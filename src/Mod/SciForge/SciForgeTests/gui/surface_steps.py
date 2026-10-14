# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the SURFACE scenarios (scenarios/surface_*.py). Kept outside
scenarios/ because every file there is run as a scenario.

Everything acts like a person: the ribbon's SURFACE tab and its menus, clicks in the 3D
view (curves with harness.click_edge), typing into the dialog's fields, dragging handles,
double-clicking the timeline. Sketch geometry is added the way the sweep / loft scenarios
do (the sketch itself is opened with real clicks)."""
import time

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as ins
from SciForgeTests.gui import sketch_input as si

V = App.Vector


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def panel():
    """The open surface dialog, or None."""
    from sciforge import surface_ui

    p = surface_ui.SurfacePanel.last
    return p if p is not None and not p._closed else None


def tab(label="SURFACE"):
    return ins.ribbon_tab(label)


def menu(group, label):
    """GROUP > label in the current ribbon tab, clicked with the mouse."""
    return si.menu_item(group, label)


def settle(timeout_ms=6000):
    """Let the dialog's preview catch up (its timer done, no recompute running)."""
    p = panel()
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        QtTest.QTest.qWait(50)
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


def type_field(key, text):
    """Type into the open dialog's number field `key`."""
    p = panel()
    if p is None:
        h.check("dialog open to type %s" % key, False)
        return False
    field = p.number_fields[key]
    ui.type_into(getattr(field, "widget", field), text)
    return True


def choose(key, text):
    p = panel()
    if p is None:
        h.check("dialog open to choose %s" % key, False)
        return False
    return h.check("chose %s = %s" % (key, text), ui.choose(p.rows[key][0], text))


def click_box(name):
    """Click a selection box of the open dialog (it then takes the clicks)."""
    p = panel()
    if p is None:
        h.check("dialog open for box %s" % name, False)
        return False
    ui.click(p.fields[name].button)
    return True


def toggle_check(key):
    p = panel()
    box = p.rows[key][0]
    QtTest.QTest.mouseClick(box, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(6, 6))
    QtWidgets.QApplication.processEvents()


def bodies():
    from sciforge import bodies as b

    return b.list_bodies(App.ActiveDocument)


def surface_bodies():
    from sciforge import surface

    return surface.surface_bodies(App.ActiveDocument)


def area(body):
    try:
        return body.Shape.Area if body is not None and not body.Shape.isNull() else 0.0
    except Exception:
        return 0.0


def volume(body):
    try:
        if body is None or body.Shape.isNull() or not body.Shape.Solids:
            return 0.0
        return body.Shape.Volume
    except Exception:
        return 0.0


def step_body(p=None):
    from sciforge import bodies as b

    p = p or panel()
    if p is None or p.step is None:
        return None
    return b.body_of(p.step)


def sketch_on(point):
    """Create Sketch, then click the origin plane square at `point` (two steps for a
    person: this one presses the button)."""
    h.ribbon("Create Sketch")


def open_sketch_clicked(point):
    h.check("no pop-up", not h.popups(), h.popups())
    h.click(point)


def add_lines(sketch, points, closed=False):
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


def add_circle(sketch, cx, cy, r):
    sketch.addGeometry(Part.Circle(V(cx, cy, 0), V(0, 0, 1), r))
    App.ActiveDocument.recompute()


def handle(key):
    p = panel()
    return p.handles.get(key) if p is not None else None


def drag_arrow(key, to_distance, sample=None):
    """Grab the arrow `key` of the open dialog at its head and drag it so it shows about
    `to_distance` (as a hand does). Returns the HeldDrag (check .done in the next step)."""
    dragger = handle(key)
    if dragger is None:
        h.check("arrow %s shown" % key, False)
        return None
    start = h.screen_point(ai.head_point(dragger))
    target = dragger.origin + dragger.direction * (
        to_distance + (1.0 if to_distance >= dragger.distance() else -1.0) * 0.9 * dragger.size
    )
    end = h.screen_point(target)
    drag = ai.HeldDrag(start, end, moves=30, every_ms=25, hold_ms=300, sample=sample)
    drag.run()
    return drag


def timeline_titles():
    return ui.timeline_titles()


def double_click_timeline(title):
    from SciForgeTests.gui import timeline_input as tl

    return tl.double_click(title)


def undo():
    from SciForgeTests.gui import timeline_input as tl

    tl.undo()


def redo():
    from SciForgeTests.gui import timeline_input as tl

    tl.redo()


def browser_labels():
    from SciForgeTests.gui import timeline_input as tl

    return tl.labels()


def browser_icon_of(body):
    """The icon name the browser shows on a body's row ('surface_body' / 'box'), or None
    when the body has no row."""
    from sciforge import browser_core

    from SciForgeTests.gui import timeline_input as tl

    widget = tl.tree()
    tree = getattr(widget, "_tree", None)
    if tree is None:
        return None
    node = browser_core.find(tree, "body:" + body.Name)
    return node["icon"] if node else None


def esc():
    h.press(QtCore.Qt.Key_Escape)


def ok():
    return h.task_button("OK")


def cancel():
    return h.task_button("Cancel")


def message():
    p = panel()
    if p is None:
        return ""
    return (p.message.text() or "") + " | " + (p.info.text() or "")


def wait(ms):
    QtTest.QTest.qWait(ms)
