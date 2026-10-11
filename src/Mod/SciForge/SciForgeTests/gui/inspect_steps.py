# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared helpers for the CONSTRUCT and INSPECT scenarios (scenarios/inspect*.py).
Everything acts like a person: ribbon buttons and menus, keys, clicks and drags in the 3D
view, typing into the dialog's fields, the timeline and the browser.

The part (blend_steps.box_steps): a 40 x 30 x 10 box from the origin, made with real
input. Not a scenario itself (it lives outside scenarios/)."""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h

V = App.Vector


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def near(a, b, tol=1e-6):
    return (V(a) - V(b)).Length <= tol


def normal_of(obj):
    return obj.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))


def construct_panel():
    from sciforge import construct_ui, taskui

    panel = taskui.current()
    if isinstance(panel, construct_ui.ConstructPanel):
        return panel
    return None


def datums(type_id=None):
    from sciforge import construct

    types = (type_id,) if type_id else construct.DATUM_TYPES
    return [o for o in App.ActiveDocument.Objects if o.TypeId in types]


def menu(group, label):
    """Click the ribbon group's name and the entry in its menu (CONSTRUCT, INSPECT)."""
    from SciForgeTests.gui import sketch_input as si

    return si.menu_item(group, label)


def type_into(widget, text):
    di.type_into(widget, text)


def screen(point):
    return h.screen_point(point)


def drag_px(start, dx, dy):
    """Drag from a widget pixel by (dx, dy) pixels."""
    h.drag(start, QtCore.QPoint(start.x() + dx, start.y() + dy), steps=16)


def press_enter():
    h.press(QtCore.Qt.Key_Return)


def press_escape():
    h.press(QtCore.Qt.Key_Escape)


def no_popups(where):
    h.check("no pop-up after %s" % where, not h.popups(), h.popups())


def box_value(panel, index):
    return panel.boxes[index].button.text()


def click_box(panel, index):
    di.click(panel.boxes[index].button)


def selection():
    return [(s.ObjectName, list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]


def click_vertex(point):
    """Click a corner of the part (dots a few pixels wide: aim until one is under the mouse)."""
    from SciForgeTests.gui import shell_draft_steps as sd

    return sd.click_vertex(point)


def pixel_toward(point, direction, pixels):
    """The widget pixel `pixels` from point's pixel toward where point + direction shows."""
    a = h.screen_point(point)
    b = h.screen_point(V(point) + V(direction))
    dx, dy = b.x() - a.x(), b.y() - a.y()
    length = math.hypot(dx, dy) or 1.0
    return QtCore.QPoint(int(a.x() + dx / length * pixels), int(a.y() + dy / length * pixels))


def timeline_titles():
    from SciForgeTests.gui import timeline_input as ti

    return ti.titles()


def timeline_title_of(obj):
    from SciForgeTests.gui import timeline_input as ti

    for item in ti.tl().items():
        if item.name == obj.Name:
            return item.display
    return None


def double_click_timeline(obj):
    from SciForgeTests.gui import timeline_input as ti

    title = timeline_title_of(obj)
    h.check("%s is in the timeline" % obj.Label, title is not None, timeline_titles())
    if title is not None:
        ti.double_click(title)


def undo():
    di.quick_access("Undo")


def redo():
    di.quick_access("Redo")


def processEvents():
    QtWidgets.QApplication.processEvents()


def key(widget, k):
    widget.setFocus()
    QtTest.QTest.keyClick(widget, k)
    QtWidgets.QApplication.processEvents()


def eye(label):
    """Click the eye of a browser row (show / hide), like a person."""
    from SciForgeTests.gui import timeline_input as ti

    ok = ti.click_eye(label)
    h.check("browser row %s has an eye" % label, ok, ti.labels())
    return ok


def _active_panel():
    from sciforge import taskui

    return taskui.current()


def boss_steps():
    """Steps (real input) that put a round boss r = 5, 10 high, centre (10, 10) on the top
    face of the 40 x 30 x 10 box."""

    def sketch_top():
        h.click_empty()
        h.fit()
        h.ribbon("Create Sketch")

    def click_top():
        h.click(V(30, 20, 10))

    def circle():
        sk = h.in_sketch()
        h.check("sketch on the top face", sk is not None)
        if sk:
            x, y = h.to_sketch(sk, V(10, 10, 10))
            h.draw_circle(sk, x, y, 5)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        h.fit()
        h.press("e")

    def distance():
        panel = _active_panel()
        field = getattr(getattr(panel, "distance", None), "widget", None)
        if field is not None:
            type_into(field, "10")

    def ok():
        h.task_button("OK")

    def boss_made():
        v = h.solid_volume()
        h.check("box + boss made", close(v, 12000 + math.pi * 25 * 10), v)
        h.fit()

    return [sketch_top, click_top, circle, finish, extrude, distance, ok, boss_made]
