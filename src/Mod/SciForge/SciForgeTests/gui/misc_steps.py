# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the misc_* scenarios (Derive, Decal, Preferences, Scripts and
Add-Ins, Manage Materials, Compute All). Not a scenario."""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

V = App.Vector
FILES = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"


def near(a, b, tol=1e-3):
    return a is not None and b is not None and abs(a - b) <= tol


def process(ms=0):
    QtWidgets.QApplication.processEvents()
    if ms:
        QtTest.QTest.qWait(ms)


def project_folder():
    """A fresh project folder for the scenario (Fusion's project, Luca's NAS folder)."""
    folder = tempfile.mkdtemp(prefix="sciforge-misc-")
    App.ParamGet(FILES).SetString("ProjectFolder", folder)
    App.ParamGet(FILES).SetBool("AskDescription", True)
    return folder


def make_box_design(
    folder,
    name,
    length=20,
    width=10,
    height=5,
    component=None,
    offset=None,
    sketch=True,
    plane=True,
    parameter=("width", "12"),
):
    """A saved design `name` with a box body (optionally inside a component moved by
    `offset`), a sketch with a line and a circle, a construction plane and a user parameter;
    closed again. Returns its path."""
    import Part

    from sciforge import parameters

    doc = App.newDocument(name)
    container = None
    if component:
        container = doc.addObject("App::Part", component)
        container.Label = component
        if offset is not None:
            container.Placement.Base = offset
    body = doc.addObject("PartDesign::Body", "Body")
    body.Label = "Body1"
    if container is not None:
        container.addObject(body)
    box = doc.addObject("PartDesign::AdditiveBox", "Box")
    body.addObject(box)
    box.Length, box.Width, box.Height = length, width, height
    if sketch:
        sk = body.newObject("Sketcher::SketchObject", "Sketch")
        sk.Label = "Outline"
        sk.MapMode = "Deactivated"
        sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(length, 0, 0)))
        sk.addGeometry(Part.Circle(V(5, 5, 0), V(0, 0, 1), 2))
    if plane:
        datum = body.newObject("PartDesign::Plane", "DatumPlane")
        datum.Label = "Top Plane"
        datum.MapMode = "Deactivated"
        datum.Placement.Base = V(0, 0, height)
    if parameter:
        parameters.add_user(doc, parameter[0], "mm", parameter[1])
    doc.recompute()
    path = os.path.join(folder, name + ".FCStd")
    doc.saveAs(path)
    Gui.getDocument(doc.Name).Modified = False
    App.closeDocument(doc.Name)
    return path


def edit_saved(path, change):
    """Open a saved design, change(doc), save it, close it (as a person editing the source
    in its own tab does)."""
    doc = App.openDocument(path)
    change(doc)
    doc.recompute()
    doc.save()
    Gui.getDocument(doc.Name).Modified = False
    App.closeDocument(doc.Name)


def close_all():
    for name in list(App.listDocuments()):
        try:
            Gui.getDocument(name).Modified = False
        except Exception:
            pass
        App.closeDocument(name)


# -- the Derive dialog ---------------------------------------------------------------------------
def derive_panel():
    from sciforge import derive_ui, taskui

    current = taskui.current()
    return current if isinstance(current, derive_ui.DerivePanel) else None


def tree_item(panel, key):
    return panel.item_for(key) if panel is not None else None


def tick(panel, key, on=True):
    """Click an item's tick box in the Derive dialog's tree, like a person."""
    item = tree_item(panel, key)
    if not h.check("Derive dialog lists %s" % key, item is not None):
        return False
    tree = panel.tree
    tree.scrollToItem(item)
    process()
    rect = tree.visualItemRect(item)
    option = QtWidgets.QStyleOptionViewItem()
    option.rect = rect
    option.features = QtWidgets.QStyleOptionViewItem.HasCheckIndicator
    box = tree.style().subElementRect(QtWidgets.QStyle.SE_ItemViewItemCheckIndicator, option, tree)
    point = (
        box.center()
        if box.isValid() and box.width() > 0
        else QtCore.QPoint(rect.left() + 10, rect.center().y())
    )
    wanted = QtCore.Qt.Checked if on else QtCore.Qt.Unchecked
    if item.checkState(0) != wanted:
        w.click(tree.viewport(), point)
    if item.checkState(0) != wanted:  # a style that draws the box elsewhere
        w.click(tree.viewport(), QtCore.QPoint(rect.left() + 8, rect.center().y()))
    return h.check(
        "%s %s in the Derive dialog" % (key, "ticked" if on else "unticked"),
        item.checkState(0) == wanted,
    )


def set_check(checkbox, on):
    """Click a check box on its box (as a person does) until it shows `on`."""
    from SciForgeTests.gui import bodies_steps

    if checkbox.isChecked() != bool(on):
        bodies_steps.toggle(checkbox)
    return h.check(
        "%s %s" % (checkbox.text() or checkbox.objectName(), "on" if on else "off"),
        checkbox.isChecked() == bool(on),
    )


def click_widget(widget):
    if widget is None:
        return False
    w.click(widget)
    return True


def find_child(parent, object_name):
    if parent is None:
        return None
    for child in parent.findChildren(QtWidgets.QWidget):
        if child.objectName() == object_name:
            return child
    return None


# -- the timeline ----------------------------------------------------------------------------------
def timeline_title(obj):
    """The timeline's name for a step object, or None."""
    for item in t.tl().items():
        if item.name == obj.Name:
            return item.display
    return None


def timeline_item(obj):
    for item in t.tl().items():
        if item.name == obj.Name:
            return item
    return None


def told():
    from sciforge import commands

    return commands._TOLD["msg"] or ""
