# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the sketch text and Emboss scenarios (scenarios/sketch_text_*.py,
scenarios/emboss_*.py): the Text panel's widgets, clicks at sketch points, the texts of a
sketch. Kept outside scenarios/ because every file there is run as a scenario."""

import FreeCAD as App

from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si


def dialog():
    """The open Text panel (text_ui.TextDialog), or None."""
    from sciforge import text_ui

    d = text_ui.TextDialog.last
    if d is None or d.closed:
        return None
    return d


def layer():
    from sciforge import text_ui

    return text_ui.current_layer()


def texts(sketch):
    from sciforge import text

    return text.texts_of(sketch)


def at(sketch, x, y):
    """The global point of sketch point (x, y)."""
    return sketch.getGlobalPlacement().multVec(App.Vector(x, y, 0))


def click_sketch(sketch, x, y):
    """Move towards and click sketch point (x, y) like a hand does."""
    return si.click(at(sketch, x, y))


def type_text(content):
    """Click into the Text box, select all, type (newlines as Enter keys)."""
    d = dialog()
    if d is None:
        h.check("Text panel open to type into", False)
        return
    box = d.text_box
    QtTest.QTest.mouseClick(box.viewport(), QtCore.Qt.LeftButton)
    QtTest.QTest.keyClick(box, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line:
            QtTest.QTest.keyClicks(box, line)
        if i < len(lines) - 1:
            QtTest.QTest.keyClick(box, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()


def type_field(widget, value, enter=True):
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton)
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(widget, value)
    if enter:
        QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()


def press_button(button):
    QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
    QtWidgets.QApplication.processEvents()


def ok():
    d = dialog()
    if d is None:
        h.check("Text panel open for OK", False)
        return
    press_button(d.ok_button)


def cancel():
    d = dialog()
    if d is None:
        h.check("Text panel open for Cancel", False)
        return
    box = d.findChild(QtWidgets.QDialogButtonBox, "SciForgeTextButtons")
    press_button(box.button(QtWidgets.QDialogButtonBox.Cancel))


def choose_font(family):
    d = dialog()
    combo = d.font_box
    index = combo.findText(family)
    if index < 0:
        h.check("font %s listed" % family, False, combo.count())
        return False
    combo.setCurrentIndex(index)
    combo.activated.emit(index)
    QtWidgets.QApplication.processEvents()
    return True


def letters_box(obj):
    """(xmin, ymin, xmax, ymax) of a text's letters in its sketch, from its shape."""
    shape = obj.Shape.copy()
    shape.Placement = App.Placement()
    b = shape.BoundBox
    return b.XMin, b.YMin, b.XMax, b.YMax


def middle_of_first_letter(obj):
    """A sketch point inside the first letter of a text (to click it)."""
    shape = obj.Shape.copy()
    shape.Placement = App.Placement()
    faces = sorted(shape.Faces, key=lambda f: (f.BoundBox.XMin, -f.BoundBox.YMax))
    if not faces:
        return None
    from sciforge import extrude

    p = extrude.interior_point(faces[0])
    return p.x, p.y


def open_text_tool():
    """SKETCH > CREATE > Text, with the mouse."""
    return si.menu_item("CREATE", "Text")
