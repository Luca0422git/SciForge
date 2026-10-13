# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the component scenarios (scenarios/components_*.py): the
browser's activate ring, the New Component dialog, nested browser rows, the bodies of a
component. Not a scenario (it lives outside scenarios/)."""

import FreeCAD as App
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

V = App.Vector


def doc():
    return App.ActiveDocument


def components():
    from sciforge import components as c

    return c.list_components(doc())


def component(label):
    for part in components():
        if part.Label == label:
            return part
    return None


def active_component():
    from sciforge import components as c

    return c.active_component(doc())


def active_label():
    part = active_component()
    return part.Label if part is not None else None


def container_label(obj):
    from sciforge import components as c

    part = c.container_of(obj)
    return part.Label if part is not None else None


def bodies():
    return sorted(doc().findObjects("PartDesign::Body"), key=lambda o: o.ID)


def body_labelled(label):
    for body in bodies():
        if body.Label == label:
            return body
    return None


def volume(obj):
    try:
        return obj.Shape.Volume if obj is not None and not obj.Shape.isNull() else 0.0
    except Exception:
        return 0.0


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


# -- the browser -------------------------------------------------------------------------------
def row_item(path):
    """The browser item at a path of labels from the top, e.g. ["Bracket", "Bodies"]."""
    tree = t.tree()
    item = tree.topLevelItem(0)  # the design's row holds everything
    for label in path:
        found = None
        rows = [item.child(i) for i in range(item.childCount())]
        for row in rows:
            node = row.data(1, QtCore.Qt.UserRole)
            if node["label"] == label or row.text(1) == label:
                found = row
                break
        if found is None:
            return tree, None
        item = found
    return tree, item


def children_of(path):
    """Labels of the rows under the row at ``path`` (None when the path is not there)."""
    tree, item = row_item(path)
    if item is None:
        return None
    return [item.child(i).data(1, QtCore.Qt.UserRole)["label"] for i in range(item.childCount())]


def top_labels():
    tree = t.tree()
    return [
        tree.topLevelItem(0).child(i).data(1, QtCore.Qt.UserRole)["label"]
        for i in range(tree.topLevelItem(0).childCount())
    ]


def node_of(label):
    tree = t.tree()
    item = tree.row(label)
    return item.data(1, QtCore.Qt.UserRole) if item is not None else None


def click_radio(label):
    """Click the activate ring at the end of a component row (or the design's row)."""
    tree = t.tree()
    item = tree.row(label)
    if not h.check("browser row %r" % label, item is not None, tree.labels()):
        return False
    w.click(tree.viewport(), tree.radio_point(item))
    return True


def drag_row(label, onto):
    """Drag a browser row onto another row (a body onto a component), as a person does."""
    tree = t.tree()
    item, target = tree.row(label), tree.row(onto)
    ok = item is not None and target is not None
    if not h.check("rows %r and %r" % (label, onto), ok, tree.labels()):
        return False
    start = tree.label_point(item)
    end = tree.viewport().mapToGlobal(tree.label_point(target))
    w.drag(tree.viewport(), start, end)
    return True


def rename_row(label, text):
    """Rename a row through its menu: type the new name, Enter."""
    if not t.row_menu(label, "Rename"):
        return False
    field = t.browser_field()
    if not h.check("rename field open for %r" % label, field is not None):
        return False
    QtWidgets.QApplication.processEvents()
    field.selectAll()
    w.type_text(field, text)
    w.key(field, QtCore.Qt.Key_Return)
    return True


# -- the New Component dialog --------------------------------------------------------------------
def new_component_panel():
    from sciforge import components_ui

    panel = components_ui.NewComponentPanel.last
    return panel if panel is not None and not panel._closed else None


def type_name(text):
    from SciForgeTests.gui import dialog_input as ui

    panel = new_component_panel()
    if not h.check("New Component dialog open", panel is not None):
        return False
    ui.type_into(panel.name, text)
    return True


def toggle(checkbox):
    """Click a check box on its box, as a person does."""
    style = checkbox.style()
    opt = QtWidgets.QStyleOptionButton()
    checkbox.initStyleOption(opt)
    rect = style.subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, opt, checkbox)
    from PySide6 import QtTest

    QtTest.QTest.mouseClick(checkbox, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
    QtWidgets.QApplication.processEvents()


def timeline_titles():
    """The titles the timeline shows (the active component's steps)."""
    return t.titles()


def all_timeline_titles():
    return t.tl().all_titles()


def hidden_note():
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    label = widget.findChild(QtWidgets.QLabel, "SciForgeTimelineHiddenNote") if widget else None
    return label.text() if label is not None and label.isVisible() else None
