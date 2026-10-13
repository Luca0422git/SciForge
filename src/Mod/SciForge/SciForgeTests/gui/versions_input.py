# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real input on the Save / version / history / recovery dialogs and the Data Panel, for
the versions_* scenarios (and the older QA scenarios that press Ctrl+S: Fusion's Save
dialog with the Version Description box now opens there; `accept_save()` presses Enter
in it, as a person who wants no description does)."""

import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import widget_input as wi


def _process():
    QtWidgets.QApplication.processEvents()


def dialog(object_name):
    """The visible SciForge dialog with this objectName, or None."""
    for widget in QtWidgets.QApplication.topLevelWidgets():
        try:
            if widget.objectName() == object_name and widget.isVisible():
                return widget
        except RuntimeError:
            continue
    return None


def child(parent, object_name):
    if parent is None:
        return None
    for widget in parent.findChildren(QtWidgets.QWidget):
        if widget.objectName() == object_name:
            return widget
    return None


def save_dialog():
    return dialog("SciForgeSaveDialog")


def version_dialog():
    return dialog("SciForgeVersionDialog")


def history_dialog():
    return dialog("SciForgeHistoryDialog")


def recover_dialog():
    return dialog("SciForgeRecoverDialog")


def older_dialog():
    return dialog("SciForgeOlderVersionDialog")


def compare_dialog():
    return dialog("SciForgeCompareDialog")


def type_into(line_edit, text):
    """Select what is in a text field and type `text` over it."""
    line_edit.setFocus()
    QtTest.QTest.keyClick(line_edit, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    if text:
        QtTest.QTest.keyClicks(line_edit, text)
    else:
        QtTest.QTest.keyClick(line_edit, QtCore.Qt.Key_Delete)
    _process()


def fill_save_dialog(name=None, location=None):
    """Type the name and/or location into the Save dialog. True when the dialog is there."""
    d = save_dialog()
    if d is None:
        return False
    if name is not None:
        type_into(child(d, "SciForgeSaveName"), name)
    if location is not None:
        type_into(child(d, "SciForgeSaveLocation"), location)
    return True


def click_save():
    """The Save button of the Save dialog (Name + Location)."""
    d = save_dialog()
    button = child(d, "SciForgeSaveButton")
    if button is None:
        return False
    wi.click(button)
    return True


def describe_and_save(text):
    """Type a version description and press Enter (Fusion: Enter saves)."""
    d = version_dialog()
    field = child(d, "SciForgeVersionDescription")
    if field is None:
        return False
    type_into(field, text)
    QtTest.QTest.keyClick(field, QtCore.Qt.Key_Return)
    _process()
    return True


def accept_save():
    """Enter in whichever Save dialog is open (no description); False when none is open."""
    d = version_dialog()
    if d is not None:
        field = child(d, "SciForgeVersionDescription")
        field.setFocus()
        QtTest.QTest.keyClick(field, QtCore.Qt.Key_Return)
        _process()
        return True
    return click_save()


def cancel_dialog(d):
    if d is None:
        return False
    QtTest.QTest.keyClick(d, QtCore.Qt.Key_Escape)
    _process()
    return True


def history_rows():
    """[(version, date, description, size)] as the history dialog shows them."""
    d = history_dialog()
    table = child(d, "SciForgeHistoryTable")
    if table is None:
        return []
    rows = []
    for r in range(table.rowCount()):
        rows.append(tuple(table.item(r, c).text() if table.item(r, c) else "" for c in range(4)))
    return rows


def history_select(version_label):
    """Click the row of "v2" in the history table (as a person does)."""
    d = history_dialog()
    table = child(d, "SciForgeHistoryTable")
    if table is None:
        return False
    for r in range(table.rowCount()):
        item = table.item(r, 0)
        if item is not None and item.text().split()[0] == version_label:
            rect = table.visualItemRect(item)
            wi.click(table.viewport(), rect.center())
            return True
    return False


def history_button(name):
    """Click Open / Promote / Compare in the history dialog."""
    d = history_dialog()
    button = child(d, "SciForgeHistory" + name)
    if button is None or not button.isEnabled():
        return False
    wi.click(button)
    return True


def recover_entries():
    d = recover_dialog()
    lst = child(d, "SciForgeRecoverList")
    if lst is None:
        return []
    return [lst.item(i).text() for i in range(lst.count())]


def recover_button(name):
    d = recover_dialog()
    button = child(d, "SciForgeRecover" + name)
    if button is None:
        return False
    wi.click(button)
    return True


def data_panel():
    from sciforge import versions_ui

    return versions_ui.panel()


def panel_list():
    panel = data_panel()
    return panel.list if panel is not None else None


def panel_double_click(text_start):
    """Double-click the Data Panel card whose text starts with `text_start`."""
    lst = panel_list()
    if lst is None:
        return False
    for i in range(lst.count()):
        item = lst.item(i)
        if item.text().startswith(text_start):
            rect = lst.visualItemRect(item)
            wi.double_click(lst.viewport(), rect.center())
            return True
    return False


def panel_button(name):
    panel = data_panel()
    button = child(panel, "SciForgeDataPanel" + name)
    if button is None:
        return False
    wi.click(button)
    return True


def popups_except(names):
    """Visible dialogs other than SciForge's own named ones (a stray pop-up is a failure)."""
    found = []
    for w in QtWidgets.QApplication.topLevelWidgets():
        try:
            if w.isVisible() and isinstance(w, (QtWidgets.QDialog, QtWidgets.QMessageBox)):
                if w.objectName() not in names:
                    found.append(w.windowTitle() or w.metaObject().className())
        except RuntimeError:
            continue
    return found


def main_window():
    return Gui.getMainWindow()
