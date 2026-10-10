# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real mouse and keyboard input on Qt widgets (the timeline, the browser, menus),
for scenario tests. Same mechanism as harness.click() on the 3D view: Qt test
events delivered to the widget, so the widget's own event handlers run exactly as
for a person's click, drag or key press.

    right_click(widget, pos, "Suppress Features")   # opens the menu, clicks the entry
"""
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

LEFT = QtCore.Qt.LeftButton
NONE = QtCore.Qt.NoModifier


def _process():
    QtWidgets.QApplication.processEvents()


def center(widget):
    return widget.rect().center()


def move(widget, pos):
    QtTest.QTest.mouseMove(widget, pos)
    _process()


def click(widget, pos=None, modifiers=NONE, button=LEFT):
    pos = center(widget) if pos is None else pos
    move(widget, pos)
    QtTest.QTest.mouseClick(widget, button, modifiers, pos)
    _process()


def double_click(widget, pos=None):
    """The events of a real double-click: press, release, double-click, release."""
    pos = center(widget) if pos is None else pos
    move(widget, pos)
    QtTest.QTest.mousePress(widget, LEFT, NONE, pos)
    QtTest.QTest.mouseRelease(widget, LEFT, NONE, pos)
    QtTest.QTest.mouseDClick(widget, LEFT, NONE, pos)
    QtTest.QTest.mouseRelease(widget, LEFT, NONE, pos)
    _process()


def _menu_action(menu, text):
    for action in menu.actions():
        if action.text().replace("&", "").strip() == text:
            return action
    return None


def menu_texts(widget, pos):
    """The entries of the right-click menu at pos (the menu is closed again with Esc)."""
    found = {}

    def read():
        menu = QtWidgets.QApplication.activePopupWidget()
        if isinstance(menu, QtWidgets.QMenu):
            found["seen"] = True
            found["texts"] = [
                (a.text().replace("&", "").strip(), a.isEnabled())
                for a in menu.actions()
                if not a.isSeparator()
            ]
            QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
        elif found.get("tries", 0) < 20:
            found["tries"] = found.get("tries", 0) + 1
            QtCore.QTimer.singleShot(50, read)

    QtCore.QTimer.singleShot(50, read)
    _open_menu(widget, pos, found)
    return found.get("texts", [])


def right_click(widget, pos, choose):
    """Right-click at pos, then click the menu entry `choose` (like a person). Returns
    True if the entry was there and enabled. Esc closes the menu when choose is None."""
    result = {"ok": False}

    def pick():
        menu = QtWidgets.QApplication.activePopupWidget()
        if isinstance(menu, QtWidgets.QMenu):
            result["seen"] = True
        else:
            if result.get("tries", 0) < 20:
                result["tries"] = result.get("tries", 0) + 1
                QtCore.QTimer.singleShot(50, pick)
            return
        action = _menu_action(menu, choose) if choose else None
        if action is None or not action.isEnabled():
            result["texts"] = [a.text() for a in menu.actions()]
            QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
            return
        rect = menu.actionGeometry(action)
        # A person moves the mouse onto the entry; QMenu ignores a click that comes
        # without any movement since it opened (it could be the opening click).
        for i in range(8):
            QtTest.QTest.mouseMove(menu, QtCore.QPoint(rect.left() + 10 + 8 * i, rect.center().y()))
        QtTest.QTest.mouseMove(menu, rect.center())
        QtTest.QTest.mouseClick(menu, LEFT, NONE, rect.center())
        result["ok"] = True

    QtCore.QTimer.singleShot(50, pick)
    _open_menu(widget, pos, result)
    _process()
    return result["ok"]


def _open_menu(widget, pos, state):
    """A right button press/release, then the context-menu event the window system
    sends for it, unless the release already opened the menu."""
    move(widget, pos)
    QtTest.QTest.mousePress(widget, QtCore.Qt.RightButton, NONE, pos)
    QtTest.QTest.mouseRelease(widget, QtCore.Qt.RightButton, NONE, pos)
    _process()
    if state.get("seen"):
        return
    event = QtGui.QContextMenuEvent(
        QtGui.QContextMenuEvent.Mouse, pos, widget.mapToGlobal(pos), NONE
    )
    QtWidgets.QApplication.sendEvent(widget, event)


def drag(widget, start, end_global, steps=10):
    """Press on widget at start, move to end_global (screen coordinates), release."""
    move(widget, start)
    QtTest.QTest.mousePress(widget, LEFT, NONE, start)
    begin = widget.mapToGlobal(start)
    for i in range(1, steps + 1):
        g = QtCore.QPointF(
            begin.x() + (end_global.x() - begin.x()) * i / steps,
            begin.y() + (end_global.y() - begin.y()) * i / steps,
        )
        local = widget.mapFromGlobal(g.toPoint())
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove, QtCore.QPointF(local), g, QtCore.Qt.NoButton, LEFT, NONE
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        _process()
    local = widget.mapFromGlobal(end_global)
    release = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonRelease,
        QtCore.QPointF(local),
        QtCore.QPointF(end_global),
        LEFT,
        QtCore.Qt.NoButton,
        NONE,
    )
    QtWidgets.QApplication.sendEvent(widget, release)
    _process()


def key(widget, k, modifiers=NONE):
    widget.setFocus()
    QtTest.QTest.keyClick(widget, k, modifiers)
    _process()


def type_text(widget, text):
    QtTest.QTest.keyClicks(widget, text)
    _process()


def tree_row_pos(tree, item, x=None):
    """Point inside a tree row (x from the row's left edge, default: the label)."""
    rect = tree.visualItemRect(item)
    return QtCore.QPoint(rect.left() + (x if x is not None else 40), rect.center().y())


def quick_access(tooltip_start):
    """The quick-access button (Undo, Redo...) whose tooltip starts with the text."""
    import FreeCADGui as Gui

    main = Gui.getMainWindow()
    for button in main.findChildren(QtWidgets.QToolButton):
        if button.isVisible() and button.toolTip().startswith(tooltip_start):
            return button
    return None
