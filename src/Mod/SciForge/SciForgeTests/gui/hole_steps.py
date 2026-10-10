# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps and helpers for the Hole / Thread scenarios (scenarios/hole*.py). Everything
acts like a person: ribbon buttons and menus, keys, clicks in the 3D view, typing into the
dialog's fields, double-clicking the timeline. Kept outside scenarios/ because every file
there is run as a scenario.

Hand-derived geometry (box 40 x 30 x 10 from the origin, V = 12000):
  a flat-bottomed hole of diameter d and depth t removes pi d^2/4 t;
  an angled drill point of angle a on radius r adds a cone of height r / tan(a/2);
  a counterbore D x c adds pi (D^2 - d^2)/4 c;
  a 90 degree countersink of diameter D on a hole d is a cone frustum of height (D - d)/2:
      pi h/3 (R^2 + R r + r^2) instead of the cylinder pi r^2 h.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
BOX = 12000.0


def close(a, c, tol=1e-6):
    return abs(a - c) <= tol * max(1.0, abs(c))


def cylinder(d, t):
    return math.pi * d * d / 4.0 * t


def tip_cone(d, angle=118.0):
    r = d / 2.0
    return math.pi * r * r * (r / math.tan(math.radians(angle / 2.0))) / 3.0


def countersink(d, big, depth, angle=90.0):
    """Volume of a countersunk hole: the cone from `big` down to `d`, then the hole."""
    r, R = d / 2.0, big / 2.0
    height = (R - r) / math.tan(math.radians(angle / 2.0))
    return math.pi * height / 3.0 * (R * R + R * r + r * r) + math.pi * r * r * (depth - height)


def hole_panel():
    from sciforge import hole_ui

    panel = hole_ui.HolePanel.last
    if panel is None or panel._closed:
        return None
    return panel


def thread_panel():
    from sciforge import thread_ui

    panel = thread_ui.ThreadPanel.last
    if panel is None or panel._closed:
        return None
    return panel


def holes():
    body = h.body()
    return [o for o in body.Group if o.TypeId == "PartDesign::Hole"] if body else []


def threads():
    from sciforge import thread

    body = h.body()
    return [o for o in body.Group if thread.is_thread(o)] if body else []


def helper_sketches():
    from sciforge import hole

    return [o for o in App.ActiveDocument.Objects if hole.is_helper(o)]


def centre_of(feature):
    from sciforge import hole

    spots = hole.centres(feature)
    return spots[0][0] if spots else None


def centres_dir(feature):
    from sciforge import hole

    spots = hole.centres(feature)
    return spots[0][1] if spots else None


def references(feature):
    from sciforge import hole

    return hole.references(feature) if feature is not None else []


def vnear(a, c, tol=1e-6):
    return a is not None and (a - c).Length <= tol


def type_into(widget, text):
    b.type_into(widget, text)


def click_checkbox(box):
    """Click a check box on its box (Qt ignores clicks beside the box and its text)."""
    from SciForgeTests.gui import widget_input as w

    w.click(box, QtCore.QPoint(8, box.height() // 2))


def drag_arrow(origin, direction, distance, along):
    """Drag a taskui.ArrowDragger whose middle is at origin + direction * distance by
    `along` mm along its direction."""
    centre = origin + direction * distance
    h.drag(h.screen_point(centre), h.screen_point(centre + direction * along))


def make_boss(name, radius=3.0, height=12.0, at=(20.0, 15.0)):
    """Steps: Create Sketch on the box's top face, a circle, Finish, E, height, OK: a boss."""
    s = {}

    def sketch_on_top():
        h.fit()
        h.ribbon("Create Sketch")

    def click_top():
        h.click(V(35, 25, 10))

    def draw_circle():
        sk = h.in_sketch()
        h.check("sketch open on the top face", sk is not None)
        if sk is not None:
            x, y = h.to_sketch(sk, V(at[0], at[1], 10))
            h.draw_circle(sk, x, y, radius)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        h.fit()
        h.press("e")

    def distance():
        panel = b.active_panel()
        field = getattr(getattr(panel, "distance", None), "widget", None)
        if field is not None:
            type_into(field, "%g" % height)

    def ok():
        h.task_button("OK")

    def boss_made():
        v = h.solid_volume()
        s["v"] = BOX + math.pi * radius * radius * height
        h.check("boss r %g x %g on the box" % (radius, height), close(v, s["v"]), (v, s["v"]))
        h.fit()

    for step in (sketch_on_top, click_top, draw_circle, finish, extrude, distance, ok, boss_made):
        step.__name__ = "%s_%s" % (name, step.__name__)
    return [sketch_on_top, click_top, draw_circle, finish, extrude, distance, ok, boss_made]


def browser():
    from sciforge import browser_ui

    t = browser_ui.widget()
    t.refresh()
    return t


def browser_double_click(label):
    """Double-click a row of the browser, like a person."""
    from SciForgeTests.gui import widget_input as w

    t = browser()
    item = t.row(label)
    if not h.check("browser row %r" % label, item is not None, t.labels()):
        return False
    w.double_click(t.viewport(), t.label_point(item))
    return True


def no_popups(where):
    h.check("no pop-up after %s" % where, not h.popups(), h.popups())


def timeline_titles():
    return b.timeline_titles()


def visible(obj):
    try:
        return bool(obj.ViewObject.Visibility)
    except Exception:
        return False


def task_widgets_visible(*widgets):
    return all(w.isVisible() for w in widgets)


def message(panel):
    return panel.message.text() if panel is not None else ""


def process():
    QtWidgets.QApplication.processEvents()


def press_key(key, modifiers=QtCore.Qt.NoModifier):
    h.press(key, modifiers)


def gui_doc():
    return Gui.ActiveDocument
