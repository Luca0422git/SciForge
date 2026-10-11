# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps and helpers for the body-tool scenarios (scenarios/bodies*.py): Combine,
Split Body, Move/Copy, Delete, Appearance, Physical Material. Everything acts like a person:
ribbon buttons and menus, clicks on the bodies, typing into fields, the timeline. Kept
outside scenarios/ because every file there is run as a scenario.

Parts are made like Luca makes them: Create Sketch on XY, a rectangle, Finish Sketch, E, the
height, (Operation New Body for a second body), OK.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector


def close(a, c, tol=1e-6):
    return abs(a - c) <= tol * max(1.0, abs(c))


def bodies():
    doc = App.ActiveDocument
    if doc is None:
        return []
    return sorted(doc.findObjects("PartDesign::Body"), key=lambda o: o.ID)


def body_named(label):
    for body in bodies():
        if body.Label == label:
            return body
    return None


def shown(obj):
    try:
        return bool(obj.ViewObject.Visibility)
    except Exception:
        return False


def volume(body):
    try:
        return body.Shape.Volume if not body.Shape.isNull() else 0.0
    except Exception:
        return 0.0


def total_volume(visible_only=True):
    return sum(volume(x) for x in bodies() if not visible_only or shown(x))


def new_design(name):
    def new_design():
        Gui.activateWorkbench("SciForgeWorkbench")
        App.newDocument(name)
        h.fit()

    new_design.__name__ = "new_design_" + name
    return new_design


def box_steps(name, rect, height, click, new_body=False, check_volume=None):
    """Steps: Create Sketch, click the XY plane at `click`, a rectangle `rect` (x0, y0, x1,
    y1), Finish Sketch, E, the height, Operation New Body (if asked), OK."""
    state = {}

    def sketch():
        state["n"] = len(bodies())
        state["v"] = total_volume()
        h.fit()
        h.ribbon("Create Sketch")

    def pick_xy():
        h.click(click)

    def draw():
        sk = h.in_sketch()
        h.check("sketch open on XY", sk is not None)
        if sk is not None:
            h.draw_rectangle(sk, *rect)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        h.fit()
        h.press("e")

    def distance():
        panel = b.active_panel()
        field = getattr(getattr(panel, "distance", None), "widget", None)
        if h.check("extrude dialog open", field is not None):
            b.type_into(field, "%g" % height)
            QtTest.QTest.keyClick(field, QtCore.Qt.Key_Tab)
            QtWidgets.QApplication.processEvents()

    def operation():
        panel = b.active_panel()
        combo = getattr(panel, "operation", None)
        if new_body and h.check("extrude has an operation", combo is not None):
            b.choose(combo, "New Body")

    def ok():
        h.task_button("OK")

    def made():
        x0, y0, x1, y1 = rect
        expect = abs(x1 - x0) * abs(y1 - y0) * height
        if new_body:
            h.check("%s: a new body" % name, len(bodies()) == state["n"] + 1, len(bodies()))
            h.check("%s: volume" % name, close(volume(bodies()[-1]), expect), volume(bodies()[-1]))
        else:
            got = check_volume if check_volume is not None else state["v"] + expect
            h.check("%s: volume" % name, close(total_volume(), got), (total_volume(), got))
        h.fit()

    steps = [sketch, pick_xy, draw, finish, extrude, distance, operation, ok, made]
    for step in steps:
        step.__name__ = "%s_%s" % (name, step.__name__)
    return steps


def panel():
    from sciforge import taskui

    return taskui.current()


def click_box(name):
    p = panel()
    fields = getattr(p, "fields", {})
    if h.check("dialog has a %s box" % name, name in fields, list(fields)):
        b.click_widget(fields[name].button)


def toggle(checkbox):
    """Click a check box on its box, as a person does."""
    style = checkbox.style()
    opt = QtWidgets.QStyleOptionButton()
    checkbox.initStyleOption(opt)
    rect = style.subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, opt, checkbox)
    QtTest.QTest.mouseClick(checkbox, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
    QtWidgets.QApplication.processEvents()


def type_value(widget, text):
    b.type_into(widget, text)
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()


def timeline_title_of(obj):
    """The timeline title of a step (as shown on its icon)."""
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    if widget is None:
        return None
    widget.refresh(force=True)
    QtWidgets.QApplication.processEvents()
    for button in widget._buttons:
        if button.item.name == obj.Name:
            return button.item.display
    return None


def timeline_double_click(obj):
    title = timeline_title_of(obj)
    if h.check("timeline shows %s" % obj.Name, title is not None, b.timeline_titles()):
        b.timeline_double_click(title)


def steps_of_kind(kind):
    doc = App.ActiveDocument
    return [o for o in doc.Objects if getattr(o, "SciForgeType", "") == kind]


def undo():
    from SciForgeTests.gui import dialog_input

    h.check("Undo button", dialog_input.quick_access("Undo"))


def redo():
    from SciForgeTests.gui import dialog_input

    h.check("Redo button", dialog_input.quick_access("Redo"))


def menu(group, label):
    from SciForgeTests.gui import sketch_input

    return sketch_input.menu_item(group, label)


def no_popups(where):
    h.check("no pop-up after %s" % where, not h.popups(), h.popups())


def browser():
    from sciforge import browser_ui

    tree = browser_ui.widget()
    if tree is not None:
        tree.refresh()
    return tree


def click_browser_row(label, modifiers=QtCore.Qt.NoModifier):
    """Click a row of the browser (a body, a sketch) on its name, as a person does."""
    from SciForgeTests.gui import widget_input as w

    tree = browser()
    item = tree.row(label) if tree is not None else None
    if h.check("browser row %r" % label, item is not None, tree.labels() if tree else None):
        w.click(tree.viewport(), tree.label_point(item), modifiers)


def click_timeline(obj):
    """Click a step's icon in the timeline (it is selected, like in Fusion)."""
    from sciforge import timeline_ui
    from SciForgeTests.gui import widget_input as w

    widget = timeline_ui.widget()
    widget.refresh(force=True)
    QtWidgets.QApplication.processEvents()
    for button in widget._buttons:
        if button.item.name == obj.Name:
            w.click(button)
            return True
    h.check("timeline shows %s" % obj.Name, False, b.timeline_titles())
    return False


def selected_names():
    return [x.ObjectName for x in Gui.Selection.getSelectionEx()]


def timeline_status(obj):
    """("error" | "warning" | "", reason) the timeline shows for a step."""
    from sciforge import timeline_ops

    return timeline_ops.problem(obj)
