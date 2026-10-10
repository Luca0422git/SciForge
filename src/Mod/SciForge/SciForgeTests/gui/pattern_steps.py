# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps and helpers for the pattern and mirror scenarios (scenarios/patterns*.py).
Everything acts like a person: ribbon buttons, clicks in the 3D view, clicks on the
dialog's selection boxes and the timeline, typing into fields, dragging the blue arrows.
Kept outside scenarios/ because every file there is run as a scenario.

Hand-derived geometry (box 40 x 30 x 10 from the origin, V = 12000):
  a through hole of radius r removes pi r^2 * 10;
  a boss of radius r and height t on the top adds pi r^2 t.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
BOX = 12000.0


def close(a, c, tol=1e-6):
    return abs(a - c) <= tol * max(1.0, abs(c))


def hole(r, t=10.0):
    return math.pi * r * r * t


def panel():
    """The open pattern / mirror dialog, or None."""
    from sciforge import pattern_ui

    p = pattern_ui.PatternPanel.last
    if p is None or p._closed:
        return None
    return p


def patterns(kind=None):
    from sciforge import pattern

    body = h.body()
    if body is None:
        return []
    return [
        o
        for o in body.Group
        if pattern.kind_of(o) is not None and (kind is None or pattern.kind_of(o) == kind)
    ]


def click_box(name):
    """Click a selection box of the dialog (it turns blue and takes the next clicks)."""
    p = panel()
    if not h.check("dialog has a %s box" % name, p is not None and name in p.fields):
        return
    w.click(p.fields[name].button)


def type_value(widget, text):
    """Click into a number field, select what is there, type and Tab away."""
    b.type_into(widget, text)
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()


def type_quantity(spin, value):
    spin.setFocus()
    QtTest.QTest.mouseClick(spin, QtCore.Qt.LeftButton)
    QtTest.QTest.keyClick(spin, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(spin, str(value))
    QtTest.QTest.keyClick(spin, QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()


def timeline_button(title):
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    if widget is None:
        return None
    widget.refresh()
    QtWidgets.QApplication.processEvents()
    for button in widget._buttons:
        if button.item.display == title:
            return button
    return None


def timeline_titles():
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    if widget is None:
        return []
    widget.refresh()
    QtWidgets.QApplication.processEvents()
    return [button.item.display for button in widget._buttons]


def timeline_click(title):
    button = timeline_button(title)
    if h.check("timeline shows %s" % title, button is not None, timeline_titles()):
        w.click(button)


def timeline_double_click(title):
    button = timeline_button(title)
    if h.check("timeline shows %s" % title, button is not None, timeline_titles()):
        w.double_click(button)


def drag_arrow(key, along):
    """Drag the blue arrow `key` of the open dialog by `along` mm along its direction."""
    p = panel()
    handle = p.handles.get(key) if p is not None else None
    if not h.check("blue arrow %s shown" % key, handle is not None):
        return None
    tip = handle.origin + handle.direction * handle.distance()
    h.drag(h.screen_point(tip), h.screen_point(tip + handle.direction * along))
    return handle


def circle_centres(shape, radius, z=None):
    """Sorted (x, y) centres of the circular edges of this radius (at height z)."""
    found = set()
    for edge in shape.Edges:
        curve = edge.Curve
        if curve.TypeId not in ("Part::GeomCircle", "Part::GeomArcOfCircle"):
            continue
        if abs(curve.Radius - radius) > 1e-6:
            continue
        c = curve.Center
        if z is not None and abs(c.z - z) > 1e-6:
            continue
        found.add((round(c.x, 4), round(c.y, 4)))
    return sorted(found)


def menu(label):
    """Run a command from the CREATE menu (opened with the mouse, submenus included)."""
    from SciForgeTests.gui import sketch_input

    return sketch_input.menu_item("CREATE", label)


def no_popups(where):
    h.check("no pop-up after %s" % where, not h.popups(), h.popups())


def selection():
    return [(s.ObjectName, list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]


def make_cut(name, at, r, depth=10.0, click=None):
    """Steps: Create Sketch on the top face (clicked at `click`), a circle, Finish Sketch, E,
    -depth (a cut), OK."""
    state = {}

    def sketch_on_top():
        h.fit()
        h.ribbon("Create Sketch")

    def click_top():
        h.click(click if click is not None else V(at[0] + r + 3, at[1] + r + 3, 10))

    def draw_circle():
        sk = h.in_sketch()
        h.check("sketch open on the top face", sk is not None)
        if sk is not None:
            x, y = h.to_sketch(sk, V(at[0], at[1], 10))
            h.draw_circle(sk, x, y, r)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        state["v"] = h.solid_volume()
        h.fit()
        h.press("e")

    def distance():
        p = b.active_panel()
        field = getattr(getattr(p, "distance", None), "widget", None)
        if field is not None:
            b.type_into(field, "%g" % -depth)

    def ok():
        h.task_button("OK")

    def cut_made():
        v = h.solid_volume()
        expect = state["v"] - math.pi * r * r * depth
        h.check("hole r %g at %s cut" % (r, at), close(v, expect), (v, expect))
        h.fit()

    steps = [sketch_on_top, click_top, draw_circle, finish, extrude, distance, ok, cut_made]
    for step in steps:
        step.__name__ = "%s_%s" % (name, step.__name__)
    return steps


def make_boss(name, at, r, height, click, top=10.0):
    """Steps: Create Sketch on the top face (clicked at `click`), a circle, Finish Sketch, E,
    the height, OK: a round boss on the top."""
    state = {}

    def sketch_on_top():
        h.fit()
        h.ribbon("Create Sketch")

    def click_top():
        h.click(click)

    def draw_circle():
        sk = h.in_sketch()
        h.check("sketch open on the top face", sk is not None)
        if sk is not None:
            x, y = h.to_sketch(sk, V(at[0], at[1], top))
            h.draw_circle(sk, x, y, r)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        state["v"] = h.solid_volume()
        h.fit()
        h.press("e")

    def distance():
        p = b.active_panel()
        field = getattr(getattr(p, "distance", None), "widget", None)
        if field is not None:
            b.type_into(field, "%g" % height)

    def ok():
        h.task_button("OK")

    def boss_made():
        v = h.solid_volume()
        expect = state["v"] + math.pi * r * r * height
        h.check("boss r %g x %g at %s" % (r, height, at), close(v, expect), (v, expect))
        h.fit()

    steps = [sketch_on_top, click_top, draw_circle, finish, extrude, distance, ok, boss_made]
    for step in steps:
        step.__name__ = "%s_%s" % (name, step.__name__)
    return steps


def bodies():
    return App.ActiveDocument.findObjects("PartDesign::Body")
