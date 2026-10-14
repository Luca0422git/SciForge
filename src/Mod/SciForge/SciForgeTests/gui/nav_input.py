# SPDX-License-Identifier: LGPL-2.1-or-later
"""The navigation bar at the bottom of the 3D view, used like a person: click a button, or
open its drop-down and click an entry (through submenus such as Display Settings > Visual
Style). For the navbar_*.py scenarios."""

import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w


def bar():
    return Gui.getMainWindow().findChild(QtWidgets.QWidget, "SciForgeNavBar")


def button(label):
    found = bar()
    if found is None:
        return None
    for b in found.findChildren(QtWidgets.QToolButton):
        if b.toolTip().split("\n")[0].split("  (")[0].strip() == label:
            return b
    return None


def click(label):
    """Click a plain button of the bar (Pan, Fit...)."""
    b = button(label)
    h.check("the navigation bar has %s" % label, b is not None)
    if b is not None:
        w.click(b)
    return b is not None


def _find(menu, label):
    for action in menu.actions():
        text = action.text().split("\t")[0].replace("&", "").strip()
        if text == label:
            return [(menu, action)]
        if action.menu() is not None:
            deeper = _find(action.menu(), label)
            if deeper:
                return [(menu, action)] + deeper
    return []


def entry_state(button_label, label):
    """(enabled, checked) of a drop-down entry, read when its menu would open."""
    b = button(button_label)
    if b is None or b.menu() is None:
        return None
    b.menu().aboutToShow.emit()
    path = _find(b.menu(), label)
    if not path:
        return None
    for menu, _action in path:
        menu.aboutToShow.emit()
    action = path[-1][1]
    return action.isEnabled(), action.isChecked()


def choose(button_label, label):
    """Open the button's drop-down and click `label` in it with the mouse (submenus open
    on the way by hovering). True if it was clicked."""
    b = button(button_label)
    if b is None or b.menu() is None:
        h.check("the navigation bar has a %s drop-down" % button_label, False)
        return False
    path = _find(b.menu(), label)
    if not path:
        h.check("%s > %s exists" % (button_label, label), False)
        return False
    done = {"clicked": False}

    def click_step(step, tries=0):
        try:
            menu, action = path[step]
            if not menu.isVisible():
                if tries == 3 and step > 0:
                    parent, parent_action = path[step - 1]
                    parent.setActiveAction(parent_action)
                    QtTest.QTest.keyClick(parent, QtCore.Qt.Key_Right)
                if tries < 20:
                    QtCore.QTimer.singleShot(150, lambda: click_step(step, tries + 1))
                return
            rect = menu.actionGeometry(action)
            QtTest.QTest.mouseMove(menu, rect.center())
            if action.menu() is not None:
                QtCore.QTimer.singleShot(400, lambda: click_step(step + 1))
                return
            QtTest.QTest.mouseClick(menu, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
            done["clicked"] = True
        except Exception as exc:
            h.check("click %s > %s" % (button_label, label), False, exc)
            _close_popups()

    QtCore.QTimer.singleShot(300, lambda: click_step(0))
    guard = QtCore.QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(_close_popups)
    guard.start(5000)
    w.click(b)  # the drop-down runs its own loop until it closes
    guard.stop()
    QtWidgets.QApplication.processEvents()
    h.check("clicked %s > %s" % (button_label, label), done["clicked"])
    return done["clicked"]


def _close_popups():
    popup = QtWidgets.QApplication.activePopupWidget()
    while popup is not None:
        popup.close()
        popup = QtWidgets.QApplication.activePopupWidget()
