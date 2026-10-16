# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps of the polish2_* scenarios (value boxes on Move / Scale / Draft, timeline
groups, milestones, closing, Move / Copy in the Data Panel, out of date, Derive with
structure): real input helpers that are not anywhere else yet. Not a scenario."""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

V = App.Vector
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"


def process():
    QtWidgets.QApplication.processEvents()


def near(a, b, tol=1e-3):
    return a is not None and b is not None and abs(a - b) <= tol * max(1.0, abs(b))


def make_box(document, name, length, width, height, at=None, part=None):
    """A PartDesign body holding an additive box (the change scenarios make by script: the
    feature under test is not the box)."""
    body = document.addObject("PartDesign::Body", name)
    if part is not None:
        part.addObject(body)
    box = document.addObject("PartDesign::AdditiveBox", name + "Box")
    body.addObject(box)
    box.Length, box.Width, box.Height = length, width, height
    if at is not None:
        box.Placement.Base = at
    document.recompute()
    return body


def volume(document=None):
    document = document or App.ActiveDocument
    total = 0.0
    for obj in document.Objects:
        if obj.TypeId == "PartDesign::Body" and not obj.Shape.isNull():
            try:
                total += obj.Shape.Volume
            except Exception:
                pass
    return total


def link_volume(document):
    total = 0.0
    for obj in document.Objects:
        if obj.TypeId == "App::Link" and not obj.Shape.isNull():
            total += obj.Shape.Volume
    return total


def doc_named(label):
    for name in App.listDocuments():
        d = App.getDocument(name)
        if d.Label == label or d.Name == label:
            return d
    return None


def subwindow_of(document):
    """The MDI sub-window (tab) of a design's 3D view."""
    gdoc = Gui.getDocument(document.Name)
    views = gdoc.mdiViewsOfType("Gui::View3DInventor")
    if not views:
        return None
    inner = views[0].graphicsView()
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for sub in area.subWindowList():
        widget = sub.widget()
        if widget is not None and (widget is inner or widget.isAncestorOf(inner)):
            return sub
    return None


def close_tab(document):
    """Close a design's tab as a person does (Ctrl+F4, Std_CloseActiveWindow: the tab's
    close button does the same)."""
    sub = subwindow_of(document)
    if not h.check("the design has a tab", sub is not None):
        return False
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    area.setActiveSubWindow(sub)
    process()
    Gui.runCommand("Std_CloseActiveWindow")
    process()
    return True


def click_menu_entry(button, entry):
    """Click a button that opens a menu (exec), then the entry `entry` in it."""
    result = {"ok": False, "tries": 0}

    def pick():
        menu = QtWidgets.QApplication.activePopupWidget()
        if not isinstance(menu, QtWidgets.QMenu):
            if result["tries"] < 30:
                result["tries"] += 1
                QtCore.QTimer.singleShot(50, pick)
            return
        result["texts"] = [a.text() for a in menu.actions()]
        action = None
        for a in menu.actions():
            if a.text().replace("&", "").strip() == entry:
                action = a
        if action is None or not action.isEnabled():
            QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
            return
        rect = menu.actionGeometry(action)
        for i in range(8):
            QtTest.QTest.mouseMove(menu, QtCore.QPoint(rect.left() + 10 + 8 * i, rect.center().y()))
        QtTest.QTest.mouseMove(menu, rect.center())
        QtTest.QTest.mouseClick(menu, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
        result["ok"] = True

    QtCore.QTimer.singleShot(50, pick)
    wi.click(button)
    process()
    return result


def dialog(object_name):
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


def click_child(parent, object_name):
    widget = child(parent, object_name)
    if widget is None or not widget.isEnabled():
        return False
    wi.click(widget)
    return True


def panel_item(text_start):
    from sciforge import versions_ui

    panel = versions_ui.panel()
    if panel is None:
        return None, None
    for i in range(panel.list.count()):
        item = panel.list.item(i)
        if item.text().startswith(text_start):
            return panel.list, item
    return panel.list, None


def panel_menu(text_start, entry):
    """Right-click a Data Panel card and choose `entry`."""
    lst, item = panel_item(text_start)
    if not h.check("the Data Panel shows %s" % text_start, item is not None):
        return False
    rect = lst.visualItemRect(item)
    return wi.right_click(lst.viewport(), rect.center(), entry)


def set_project(folder):
    App.ParamGet(PREFS).SetString("ProjectFolder", folder)
    App.ParamGet(PREFS).SetBool("UseGit", True)
    App.ParamGet(PREFS).SetBool("AskDescription", True)


def save_new(document, path):
    """Save a design by script into the project folder and record its v1 (set-up only)."""
    from sciforge import versions_ui

    os.makedirs(os.path.dirname(path), exist_ok=True)
    document.saveAs(path)
    Gui.getDocument(document.Name).Modified = False
    process()
    return versions_ui.store_of(path)
