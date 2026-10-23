# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the SHEET METAL forming scenarios (scenarios/sheetmetal_*.py). Kept
outside scenarios/ because every file there is run as a scenario.

Everything acts like a person: the SHEET METAL tab of the ribbon and its menus, clicks in the
3D view (edges with harness.click_edge, profiles with harness.click), typing into the
dialog's fields, choosing in its drop-downs, dragging the blue arrow, double-clicking the
timeline. Sketch geometry is added the way the surface scenarios do (the sketch itself is
opened with real clicks)."""

import math
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as ins
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import surface_steps as st

V = App.Vector
SEC = 3 * math.pi / 4 + 9  # a 90 degree flange's cross-section with T = R = 1, height 10
L_BRACKET = 1500 - 60 + 30 * SEC  # 50 x 30 plate + flange on the 30 mm edge (golden model)


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def panel():
    from sciforge import sheetmetal_flange_ui as ui_mod

    p = ui_mod.FlangePanel.last
    return p if p is not None and not p._closed else None


def rules_dialog():
    from sciforge import sheetmetal_rules_ui as ui_mod

    d = ui_mod.RulesDialog.last
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


def tab():
    return ins.ribbon_tab("sheet_metal")


def menu(group, label):
    return si.menu_item(group, label)


def settle(timeout_ms=8000):
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


def widget(key):
    p = panel()
    if p is None:
        h.check("dialog open for %s" % key, False)
        return None
    return p.rows[key][1]


def choose(key, text):
    box = widget(key)
    if box is None:
        return False
    return h.check("chose %s = %s" % (key, text), ui.choose(box, text), box.currentText())


def type_field(key, text):
    p = panel()
    if p is None:
        h.check("dialog open to type %s" % key, False)
        return False
    ui.type_into(getattr(p, "f_" + key).widget, text)
    return True


def toggle(key):
    box = widget(key)
    if box is None:
        return
    QtTest.QTest.mouseClick(box, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(6, 6))
    QtWidgets.QApplication.processEvents()


def message():
    p = panel()
    return (p.message.text() or "") if p is not None else ""


def shown(key):
    w = widget(key)
    return w is not None and w.isVisible()


def bodies():
    from sciforge import bodies as b

    return b.list_bodies(App.ActiveDocument)


def sheet_bodies():
    from sciforge import sheetmetal

    return sheetmetal.sheet_metal_bodies(App.ActiveDocument)


def volume(body):
    return st.volume(body)


def target_body():
    from sciforge import bodies as b

    p = panel()
    if p is None or p.target is None:
        return None
    return b.body_of(p.target)


def drag_arrow(key, to_distance):
    """Grab the dialog's arrow `key` at its head and drag it to about `to_distance`."""
    p = panel()
    dragger = p.arrows.get(key) if p is not None else None
    if dragger is None:
        h.check("arrow %s shown" % key, False, list(p.arrows) if p else None)
        return None
    start = h.screen_point(ai.head_point(dragger))
    target = dragger.origin + dragger.direction * (
        to_distance + (1.0 if to_distance >= dragger.distance() else -1.0) * 0.9 * dragger.size
    )
    end = h.screen_point(target)
    drag = ai.HeldDrag(start, end, moves=30, every_ms=25, hold_ms=300)
    drag.run()
    return drag


def rect_sketch(x0, y0, x1, y1):
    """Lines of a rectangle in the open sketch (the sketch was opened with clicks)."""
    sk = h.in_sketch()
    h.check("a sketch is open", sk is not None)
    if sk is not None:
        st.add_lines(sk, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)
    return sk


def timeline_titles():
    return ui.timeline_titles()


def double_click_timeline(title):
    return h.check("double-clicked %s" % title, ui.double_click_timeline(title))


def undo():
    st.undo()


def redo():
    st.redo()


def esc():
    h.press(QtCore.Qt.Key_Escape)


def ok():
    return h.task_button("OK")


def cancel():
    return h.task_button("Cancel")


def browser_icon_of(body):
    return st.browser_icon_of(body)


def browser_node(key):
    """The browser's node with this key (e.g. "settings:sheet_metal"), or None."""
    from sciforge import browser_core

    from SciForgeTests.gui import timeline_input as tl

    widget = tl.tree()
    tree = getattr(widget, "_tree", None)
    return browser_core.find(tree, key) if tree is not None else None


def wait(ms):
    QtTest.QTest.qWait(ms)


def click_rules_button(name):
    """Click a button of the Sheet Metal Rules dialog by its object name suffix."""
    d = rules_dialog()
    if d is None:
        h.check("Sheet Metal Rules open", False)
        return False
    button = d.findChild(QtWidgets.QPushButton, "SciForgeSheetMetalRules_" + name)
    if not h.check("button %s" % name, button is not None and button.isVisible()):
        return False
    ui.click(button)
    return True


def pick_rule(list_key, name):
    """Click the rule `name` in the design or library list."""
    d = rules_dialog()
    if d is None:
        return False
    widget = d.design if list_key == "design" else d.library
    for i in range(widget.count()):
        item = widget.item(i)
        if item.data(QtCore.Qt.UserRole) == name:
            rect = widget.visualItemRect(item)
            QtTest.QTest.mouseClick(
                widget.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center()
            )
            QtWidgets.QApplication.processEvents()
            return h.check("picked rule %s" % name, widget.currentItem() is item)
    h.check("rule %s listed" % name, False, [widget.item(i).text() for i in range(widget.count())])
    return False


def rule_field(key, text):
    d = rules_dialog()
    field = d.name_field if key == "name" else d.fields[key]
    if isinstance(field, QtWidgets.QComboBox):
        return h.check("rule %s = %s" % (key, text), ui.choose(field, text))
    QtTest.QTest.mouseClick(field, QtCore.Qt.LeftButton)
    field.setFocus()
    QtTest.QTest.keyClick(field, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(field, text)
    QtWidgets.QApplication.processEvents()
    return True


def rules_message():
    d = rules_dialog()
    return d.message.text() if d is not None else ""


def doc():
    return App.ActiveDocument


def selection_clear():
    Gui.Selection.clearSelection()
