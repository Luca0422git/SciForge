# SPDX-License-Identifier: LGPL-2.1-or-later
"""Opacity Control and the 3D view's hover lighting the browser row (Luca's requests of
2026-10-23; docs/sciforge/parity/bodies.md "Opacity Control", timeline-browser.md "Hover").

A design with a box "Plate" at the top and a component "Arm" holding a box "Link".
Path 1, right-click Plate > Opacity Control > 40 %: Plate shows 60 % see-through (its view
  and its step's), the submenu ticks 40 %; Ctrl+Z makes it solid again, Ctrl+Y 40 % again.
Path 2, right-click the component Arm > Opacity Control > 20 %: Link (in Arm) shows 80 %
  see-through, Plate stays at 40 %; a new step in Link is see-through at once.
Path 3, Custom Opacity...: the slider shows each value on the part while it moves; OK keeps
  70 % (one undo step); Cancel puts the old look back.
Path 4, the mouse over Plate in the 3D view lights Plate's row in the browser; over Link,
  Link's row; with Arm closed in the browser, Arm's row; off the part, nothing.
Path 5, saved and opened again: the opacities are still there.
"""

import os
import shutil
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

s = {}


def doc():
    return App.getDocument(s["doc"])


def obj(name):
    return doc().getObject(s[name])


def transparency(name):
    """(the body's own Transparency, its steps') as FreeCAD shows them."""
    body = obj(name)
    steps = [
        int(f.ViewObject.Transparency)
        for f in body.Group
        if f.isDerivedFrom("PartDesign::Feature") and f.ViewObject is not None
    ]
    return int(body.ViewObject.Transparency), steps


def see_through(name, value):
    own, steps = transparency(name)
    return own == value and steps and all(v == value for v in steps)


def browser():
    from sciforge import browser_ui

    tree = browser_ui.widget()
    if tree is not None:
        tree.refresh(force=True)
    return tree


def opacity_menu(label, entry):
    tree, pos = t.row_point(label)
    if pos is None:
        return {"ok": False}
    result = w.right_click_sub(tree.viewport(), pos, "Opacity Control", entry)
    h.check("browser menu %s > Opacity Control > %s" % (label, entry), result["ok"], result)
    return result


def add_box(document, body, size, name):
    box = document.addObject("PartDesign::AdditiveBox", name)
    body.addObject(box)
    box.Length = box.Width = box.Height = size
    return box


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    from sciforge import components

    document = App.newDocument("Opacity")
    s["doc"] = document.Name
    plate = document.addObject("PartDesign::Body", "Body")
    plate.Label = "Plate"
    add_box(document, plate, 10, "PlateBox")
    arm = components.new_component(document, "Arm", None)
    link = components.new_body_in(document, arm, label="Link")
    box = add_box(document, link, 6, "LinkBox")
    link.Placement = App.Placement(App.Vector(40, 0, 0), App.Rotation())
    document.recompute()
    s["plate"], s["arm"], s["link"], s["link_box"] = plate.Name, arm.Name, link.Name, box.Name
    h.fit()
    browser()


setup.wait_ms = 1500


# -- Path 1 -------------------------------------------------------------------------------------
def p1_menu():
    h.check("P1 Plate starts solid", see_through("plate", 0), transparency("plate"))
    tree, pos = t.row_point("Plate")
    texts = [x for x, _on in w.menu_texts(tree.viewport(), pos)] if pos else []
    h.check("P1 the body's menu has Opacity Control", "Opacity Control" in texts, texts)
    result = opacity_menu("Plate", "40%")
    texts = [x for x, _c in result.get("texts", [])]
    h.check(
        "P1 the submenu: Fusion's steps and Custom Opacity",
        texts == ["100%", "80%", "60%", "40%", "20%", "Custom Opacity..."],
        texts,
    )
    h.check(
        "P1 100 % ticked before",
        [x for x, c in result.get("texts", []) if c] == ["100%"],
        result.get("texts"),
    )


p1_menu.wait_ms = 800


def p1_shown():
    from sciforge import opacity

    h.check("P1 Plate keeps 40 %", opacity.get(obj("plate")) == 40, opacity.get(obj("plate")))
    h.check("P1 Plate shows 60 % see-through", see_through("plate", 60), transparency("plate"))
    h.check("P1 Link is untouched", see_through("link", 0), transparency("link"))
    h.shot("P1-plate-40")
    tree, pos = t.row_point("Plate")
    result = w.right_click_sub(tree.viewport(), pos, "Opacity Control", None)
    h.check(
        "P1 the submenu ticks 40 % now",
        [x for x, c in result.get("texts", []) if c] == ["40%"],
        result.get("texts"),
    )
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


p1_shown.wait_ms = 800


def p1_undone():
    from sciforge import opacity

    h.check("P1 Ctrl+Z: 100 % again", opacity.get(obj("plate")) == 100, opacity.get(obj("plate")))
    h.check("P1 Ctrl+Z: solid again", see_through("plate", 0), transparency("plate"))
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


p1_undone.wait_ms = 800


def p1_redone():
    h.check("P1 Ctrl+Y: 60 % see-through again", see_through("plate", 60), transparency("plate"))


# -- Path 2 -------------------------------------------------------------------------------------
def p2_component():
    opacity_menu("Arm", "20%")


p2_component.wait_ms = 800


def p2_shown():
    h.check(
        "P2 Link (in Arm) shows 80 % see-through", see_through("link", 80), transparency("link")
    )
    h.check("P2 Plate stays at 60 %", see_through("plate", 60), transparency("plate"))
    box = add_box(doc(), obj("link"), 3, "LinkBox2")
    box.Placement = App.Placement(App.Vector(0, 0, 6), App.Rotation())
    doc().recompute()


p2_shown.wait_ms = 1000


def p2_new_step():
    h.check(
        "P2 a new step in Link is see-through at once",
        see_through("link", 80),
        transparency("link"),
    )


# -- Path 3 -------------------------------------------------------------------------------------
def p3_custom():
    opacity_menu("Plate", "Custom Opacity...")


p3_custom.wait_ms = 800


def _dialog():
    from sciforge import opacity_ui

    return opacity_ui.dialog()


def p3_slide():
    from sciforge import opacity

    d = _dialog()
    h.check("P3 the Custom Opacity dialog", d is not None)
    if d is None:
        return
    spin = d.findChild(QtWidgets.QSpinBox, "SciForgeOpacityValue")
    slider = d.findChild(QtWidgets.QSlider, "SciForgeOpacitySlider")
    h.check("P3 it starts at 40 %", spin.value() == 40 and slider.value() == 40, spin.value())
    slider.setFocus()
    for _ in range(3):  # three PageUp presses: 10 % each
        QtTest.QTest.keyClick(slider, QtCore.Qt.Key_PageUp)
    QtWidgets.QApplication.processEvents()
    h.check("P3 the slider moved to 70 %", slider.value() == 70, slider.value())
    h.check("P3 the box follows", spin.value() == 70, spin.value())
    h.check("P3 the part shows it already", see_through("plate", 30), transparency("plate"))
    h.check("P3 the design keeps 40 % until OK", opacity.get(obj("plate")) == 40)
    w.click(d.findChild(QtWidgets.QPushButton, "SciForgeOpacityOk"))


p3_slide.wait_ms = 800


def p3_ok():
    from sciforge import opacity

    h.check("P3 OK keeps 70 %", opacity.get(obj("plate")) == 70, opacity.get(obj("plate")))
    h.check("P3 30 % see-through", see_through("plate", 30), transparency("plate"))
    h.check("P3 the dialog closed", _dialog() is None)
    opacity_menu("Plate", "Custom Opacity...")


p3_ok.wait_ms = 800


def p3_cancel():
    d = _dialog()
    h.check("P3 the dialog again", d is not None)
    if d is None:
        return
    spin = d.findChild(QtWidgets.QSpinBox, "SciForgeOpacityValue")
    spin.setFocus()
    QtTest.QTest.keyClick(spin, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(spin, "10")
    QtWidgets.QApplication.processEvents()
    h.check("P3 typed 10 % shows", see_through("plate", 90), transparency("plate"))
    QtTest.QTest.keyClick(d, QtCore.Qt.Key_Escape)


p3_cancel.wait_ms = 800


def p3_cancelled():
    from sciforge import opacity

    h.check("P3 Cancel: still 70 %", opacity.get(obj("plate")) == 70, opacity.get(obj("plate")))
    h.check("P3 Cancel: the old look back", see_through("plate", 30), transparency("plate"))


# -- Path 4 -------------------------------------------------------------------------------------
def _hover(point):
    pos = h.screen_point(point)
    h.move(QtCore.QPoint(pos.x() + 3, pos.y()))
    h.move(pos)


def p4_plate():
    Gui.Selection.clearSelection()
    h.fit()
    s["hit_plate"] = h.under_mouse(App.Vector(5, 5, 10))
    _hover(App.Vector(5, 5, 10))


p4_plate.wait_ms = 600


def p4_plate_lit():
    tree = browser()
    key = tree.view_hover() if tree else None
    h.check(
        "P4 the mouse over Plate lights Plate's row",
        key == "body:" + s["plate"],
        (key, s.get("hit_plate"), str(Gui.Selection.getPreselection().ObjectName)),
    )
    h.shot("P4-hover-plate")
    _hover(App.Vector(43, 3, 6))


p4_plate_lit.wait_ms = 600


def p4_link_lit():
    tree = browser()
    key = tree.view_hover() if tree else None
    h.check("P4 over Link: Link's row", key == "body:" + s["link"], key)
    item = tree.row("Arm") if tree else None
    if item is not None:
        item.setExpanded(False)  # Arm closed in the browser (a person clicks its arrow)
    QtWidgets.QApplication.processEvents()
    _hover(App.Vector(42, 2, 6))


p4_link_lit.wait_ms = 600


def p4_closed():
    tree = browser()
    key = tree.view_hover() if tree else None
    h.check("P4 Arm closed: Arm's row lights", key == "component:" + s["arm"], key)
    item = tree.row("Arm") if tree else None
    if item is not None:
        item.setExpanded(True)
    widget = h.gl_widget()
    h.move(QtCore.QPoint(8, widget.height() - 8))


p4_closed.wait_ms = 600


def p4_off():
    tree = browser()
    h.check("P4 off the part: no row lit", tree.view_hover() is None, tree.view_hover())


# -- Path 5 -------------------------------------------------------------------------------------
def p5_save():
    s["dir"] = tempfile.mkdtemp(prefix="sciforge-opacity-")
    s["file"] = os.path.join(s["dir"], "Opacity.FCStd")
    doc().saveAs(s["file"])
    Gui.getDocument(s["doc"]).Modified = False
    App.closeDocument(s["doc"])
    reopened = App.openDocument(s["file"])
    s["doc"] = reopened.Name


p5_save.wait_ms = 2000


def p5_reopened():
    from sciforge import opacity

    h.check("P5 Plate still 70 %", opacity.get(obj("plate")) == 70, opacity.get(obj("plate")))
    h.check("P5 Arm still 20 %", opacity.get(obj("arm")) == 20, opacity.get(obj("arm")))
    h.check("P5 Plate shows 30 %", see_through("plate", 30), transparency("plate"))
    h.check("P5 Link shows 80 %", see_through("link", 80), transparency("link"))


def cleanup():
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)
    shutil.rmtree(s.get("dir", ""), ignore_errors=True)


h.run(
    "browser_opacity_hover",
    [
        setup,
        p1_menu,
        p1_shown,
        p1_undone,
        p1_redone,
        p2_component,
        p2_shown,
        p2_new_step,
        p3_custom,
        p3_slide,
        p3_ok,
        p3_cancel,
        p3_cancelled,
        p4_plate,
        p4_plate_lit,
        p4_link_lit,
        p4_closed,
        p4_off,
        p5_save,
        p5_reopened,
        cleanup,
    ],
)
