# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps and real-input helpers for the Fillet/Chamfer scenarios
(scenarios/fillet*.py). Everything here acts like a person: ribbon buttons, keys,
clicks in the 3D view, typing into the dialog's fields, double-clicking the timeline.

Hand-derived geometry used by the checks (box 40 x 30 x 10 from the origin):
  a round of radius r along an outside 90 degree edge of length L removes
      L * r^2 * (1 - pi/4)
  where two such rounds of the same radius meet at a box corner whose third edge stays
  sharp, the removed regions overlap by r^3 * (5/3 - pi/2), so that is added back.
  A chamfer with legs a and b along an edge of length L removes L * a * b / 2.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h

V = App.Vector
BOX = 40.0 * 30.0 * 10.0


def spandrel(r):
    """Cross-section removed by a round of radius r on a 90 degree outside edge."""
    return r * r * (1.0 - math.pi / 4.0)


def corner(r):
    """Overlap of two equal rounds meeting at a box corner (third edge sharp)."""
    return r**3 * (5.0 / 3.0 - math.pi / 2.0)


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


# -- making the box with real input (like Luca: sketch, rectangle, Finish, E, OK) --------
def box_steps(name):
    def new_design():
        Gui.activateWorkbench("SciForgeWorkbench")
        App.newDocument(name)
        h.fit()
        h.ribbon("Create Sketch")

    def pick_xy():
        h.click(V(12, -8, 0))

    def draw():
        sk = h.in_sketch()
        h.check("sketch open on XY", sk is not None)
        if sk:
            h.draw_rectangle(sk, 0, 0, 40, 30)

    def finish_sketch():
        h.ribbon("Finish Sketch")

    def extrude():
        h.fit()
        h.press("e")

    def extrude_distance():
        panel = active_panel()
        field = None
        if panel is not None:
            field = getattr(getattr(panel, "distance", None), "widget", None)
        if field is not None:
            type_into(field, "10")

    def extrude_ok():
        h.task_button("OK")

    def box_made():
        v = h.solid_volume()
        h.check("box 40 x 30 x 10 made (V = 12000)", close(v, BOX), v)
        h.fit()

    return [
        new_design,
        pick_xy,
        draw,
        finish_sketch,
        extrude,
        extrude_distance,
        extrude_ok,
        box_made,
    ]


# -- the dialog --------------------------------------------------------------------------
def active_panel():
    from sciforge import taskui

    return taskui.current()


def blend_panel():
    from sciforge import fillet_ui

    panel = fillet_ui.BlendPanel.last
    if panel is None or panel._closed:
        return None
    return panel


def type_into(widget, text):
    """Click into a field, select what is there and type, as a person does."""
    widget.setFocus()
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton)
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(widget, text)
    QtWidgets.QApplication.processEvents()


def choose(combo, label):
    """Pick an entry of a drop-down: click it open, move to the entry with the arrow keys
    and press Enter, as a person can."""
    labels = [combo.itemText(i) for i in range(combo.count())]
    if not h.check("drop-down has %r" % label, label in labels, labels):
        return False
    combo.setFocus()
    QtTest.QTest.mouseClick(combo, QtCore.Qt.LeftButton)
    QtWidgets.QApplication.processEvents()
    view = combo.view()
    target = labels.index(label)
    current = view.currentIndex().row() if view.isVisible() else combo.currentIndex()
    widget = view if view.isVisible() else combo
    key = QtCore.Qt.Key_Down if target > current else QtCore.Qt.Key_Up
    for _ in range(abs(target - current)):
        QtTest.QTest.keyClick(widget, key)
    if view.isVisible():
        QtTest.QTest.keyClick(view, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()
    return h.check("chose %r" % label, combo.currentText() == label, combo.currentText())


def click_widget(widget):
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton)
    QtWidgets.QApplication.processEvents()


def timeline_button(title):
    from sciforge import timeline_ui

    dock = timeline_ui._dock
    if dock is None:
        return None
    for button in dock.widget().findChildren(QtWidgets.QToolButton):
        if button.accessibleName() == title and button.isVisible():
            return button
    return None


def timeline_double_click(title):
    button = timeline_button(title)
    if not h.check("timeline shows %s" % title, button is not None, timeline_titles()):
        return False
    QtTest.QTest.mouseDClick(button, QtCore.Qt.LeftButton)
    QtWidgets.QApplication.processEvents()
    return True


def timeline_titles():
    from sciforge import timeline_ui

    dock = timeline_ui._dock
    return dock.widget().titles() if dock is not None else []


def blends():
    body = h.body()
    return [o for o in body.Group if o.TypeId in ("PartDesign::Fillet", "PartDesign::Chamfer")]


def arrow_screen(panel, index=0, along=3.0):
    """Widget pixels of the middle of a drag arrow and of a point `along` mm further on."""
    dragger, _spot, origin, direction = panel.arrows[index]
    center = origin + direction * dragger.distance()
    return h.screen_point(center), h.screen_point(center + direction * along)


def report_has_kernel_errors():
    text = h.report_text()
    return [
        line
        for line in text.splitlines()
        if "BRep_API" in line
        or "command not done" in line
        or "Fillet:" in line
        or "Chamfer:" in line
    ]


def no_popups(where):
    h.check("no pop-up after %s" % where, not h.popups(), h.popups())
