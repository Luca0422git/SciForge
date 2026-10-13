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


def screen(sketch, x, y):
    """Widget pixel of sketch point (x, y)."""
    return h.screen_point(at(sketch, x, y))


def text_steps(state, first, second, content, height=None, label="text"):
    """The steps that make a text with the mouse and keys: SKETCH > CREATE > Text, two
    frame corners, the text typed, (the height typed), OK. state["sketch"] is the open
    sketch; the new text lands in state[label]. A corner may be a function giving the
    sketch point when the step runs."""

    def point(p):
        return p() if callable(p) else p

    def open_tool():
        state["_before"] = list(texts(state["sketch"]))
        open_text_tool()

    def corner_1():
        h.check("%s: the Text dialog opened" % label, dialog() is not None)
        click_sketch(state["sketch"], *point(first))

    def corner_2():
        click_sketch(state["sketch"], *point(second))

    def type_it():
        d = dialog()
        h.check("%s: the frame is placed" % label, d is not None and d.frame_placed)
        type_text(content)
        if height is not None and d is not None:
            type_field(d.height, str(height))

    def press_ok():
        QtCore.QThread.msleep(100)
        QtWidgets.QApplication.processEvents()
        ok()

    def made():
        new = [o for o in texts(state["sketch"]) if o not in state["_before"]]
        h.check("%s: OK made it" % label, len(new) == 1 and dialog() is None, new)
        state[label] = new[0] if new else None

    return [open_tool, corner_1, corner_2, type_it, press_ok, made]


def marking_list_click(label):
    """Click the entry `label` in the list under the open marking menu, with the mouse."""
    menu = si.marking_menu()
    if menu is None:
        h.check("marking menu open for %s" % label, False)
        return False
    listing = menu.findChild(QtWidgets.QListWidget, "SciForgeMarkingList")
    rows = [listing.item(i).text() for i in range(listing.count())] if listing else []
    for i, row in enumerate(rows):
        if row.split("    ")[0].strip() == label:
            item = listing.item(i)
            rect = listing.visualItemRect(item)
            QtTest.QTest.mouseMove(listing.viewport(), rect.center())
            QtTest.QTest.mouseClick(
                listing.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center()
            )
            QtWidgets.QApplication.processEvents()
            return True
    h.check("marking list has %s" % label, False, rows)
    menu.close()
    return False


def frame_of(obj):
    """(corner, angle, width, height) of a text's frame lines in its sketch."""
    from sciforge import text

    return text.read_frame(obj.Sketch, list(obj.FrameIds))


def points_in_frame(points, frame, tol=0.05):
    """True if every (x, y) is inside frame (corner, angle, width, height)."""
    import math

    (cx, cy), angle, width, height = frame
    a = math.radians(angle)
    co, sn = math.cos(a), math.sin(a)
    for x, y in points:
        dx, dy = x - cx, y - cy
        u, w = co * dx + sn * dy, -sn * dx + co * dy
        if u < -tol or w < -tol or u > width + tol or w > height + tol:
            return False
    return True


def preview_in_frame(d):
    """True if the open dialog's previewed letters sit in the frame it shows."""
    if d is None or d.plan is None or d.frame() is None:
        return False
    points = [p for line in d.plan.outlines() for p in line]
    return bool(points) and points_in_frame(points, d.frame())


def letters_in_frame(obj, tol=0.05):
    """True if every vertex of the text's letters is inside its (turned) frame."""
    found = frame_of(obj)
    if found is None:
        return False
    shape = obj.Shape.copy()
    shape.Placement = App.Placement()
    return points_in_frame([(v.X, v.Y) for v in shape.Vertexes], found, tol)
