# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real keyboard/mouse input on dialog widgets for scenario tests (Extrude, Press Pull).

harness.py drives the 3D view, the ribbon and the OK/Cancel buttons. Fusion's dialogs
also have drop-downs, number fields, selection boxes and the timeline; these helpers
operate them the way a person does (clicks and key presses through Qt), never by
setting values in code. Not a scenario itself (it lives outside scenarios/).
"""
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest


def _process():
    QtWidgets.QApplication.processEvents()


def choose(combo, text):
    """Pick `text` in a drop-down with the keyboard (Up/Down, like a person who clicked it)."""
    target = combo.findText(text)
    if target < 0:
        raise ValueError("%r is not in the drop-down %s" % (text, combo.objectName()))
    combo.setFocus()
    QtTest.QTest.mouseClick(combo, QtCore.Qt.LeftButton)  # opens the list
    _process()
    view = combo.view()
    delta = target - combo.currentIndex()
    key = QtCore.Qt.Key_Down if delta > 0 else QtCore.Qt.Key_Up
    for _ in range(abs(delta)):
        QtTest.QTest.keyClick(view, key)
        _process()
    QtTest.QTest.keyClick(view, QtCore.Qt.Key_Return)
    _process()
    return combo.currentText() == text


def type_into(widget, text):
    """Click into a number field, select what is there and type `text`, then Tab away."""
    QtTest.QTest.mouseClick(
        widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(10, widget.height() // 2)
    )
    _process()
    widget.setFocus()
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(widget, text)
    _process()
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Tab)
    _process()


def click(widget):
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton)
    _process()


def timeline_button(title):
    """The timeline icon with this title ("Extrude 1"), or None."""
    for button in Gui.getMainWindow().findChildren(QtWidgets.QToolButton):
        if button.isVisible() and button.accessibleName() == title:
            return button
    return None


def timeline_titles():
    """Titles of the timeline icons (they carry a "state" property)."""
    return [
        b.accessibleName()
        for b in Gui.getMainWindow().findChildren(QtWidgets.QToolButton)
        if b.isVisible() and b.property("state") is not None
    ]


def double_click_timeline(title):
    """Double-click a timeline item, as a person edits a feature in Fusion."""
    button = timeline_button(title)
    if button is None:
        return False
    QtTest.QTest.mouseDClick(button, QtCore.Qt.LeftButton)
    _process()
    return True


def quick_access(tooltip_word):
    """Click the application-bar button whose tooltip starts with the word (Undo, Redo)."""
    for button in Gui.getMainWindow().findChildren(QtWidgets.QToolButton):
        if button.isVisible() and button.toolTip().split("\n")[0].startswith(tooltip_word):
            button.click()
            _process()
            return True
    return False
