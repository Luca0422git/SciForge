# SPDX-License-Identifier: LGPL-2.1-or-later
"""Digits typed with the mouse over the 3D view go into the arrow's value box (Fusion takes
them at once; before, the box had to be clicked first). Only real input.

Box 40 x 30: sketch, Finish, E (the dialog starts at 0). With the 3D view holding the
keyboard, type 1: the distance box takes the keyboard with "1" in it, the view does not jump
to FreeCAD's front view (its key 1); type 5 and Enter: 15 is the distance and Enter is OK
(40 x 30 x 15). Q, click the top face, type 4, Enter: pulled 4 (40 x 30 x 19).
Inside an open sketch (Create Sketch on the top) a digit goes nowhere near a box. A 10 x 10
square there, Finish, E: a click in the dialog's Distance field keeps the keyboard there
(7 typed goes into the field, never into the box); the mouse over the taper handle, then 3
typed: it goes into the taper's box (the handle hovered last), Enter: a 10 x 10 x 7 boss
with a 3 degree taper.

Hand-derived: 40 x 30 = 1200 per mm; 1200 * 15 = 18000; 1200 * 19 = 22800.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import blend_steps as bs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl

V = App.Vector
s = {}
AREA = 1200.0


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def ppanel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def near(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


def camera():
    return tuple(round(q, 6) for q in Gui.ActiveDocument.ActiveView.getCameraOrientation().Q)


def focused_box():
    """The value box that has the keyboard, or None."""
    widget = QtWidgets.QApplication.focusWidget()
    if widget is not None and widget.objectName() == a.BOX_NAME:
        return widget
    return None


def keys_to_focus(text, enter=False):
    """Keys on whatever has the keyboard now (after the first digit over the view the box
    has it, as with a real keyboard)."""
    target = QtWidgets.QApplication.focusWidget() or h.gl_widget()
    if text:
        QtTest.QTest.keyClicks(target, text)
    if enter:
        target = QtWidgets.QApplication.focusWidget() or target
        QtTest.QTest.keyClick(target, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()


def extrudes():
    from sciforge import extrude

    return [o for o in App.ActiveDocument.Objects if extrude.is_extrude(o)]


# -- the box ------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("ExtrudeKeys")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)


def finish_sketch():
    h.ribbon("Finish Sketch")


def press_e():
    h.fit()
    h.press("e")


def opened():
    p = xpanel()
    h.check("E opens the Extrude dialog at 0", p is not None and near(p.distance.value(), 0.0))
    h.check("one arrow box (the distance)", len(a.value_boxes(arrows_only=True)) == 1,
            len(a.value_boxes(arrows_only=True)))
    h.check("the box does not have the keyboard yet", focused_box() is None, a.focus_name())
    s["camera"] = camera()
    h.press("1")  # over the 3D view: FreeCAD's key 1 is its front view


def digit_in_box():
    p = xpanel()
    box = focused_box()
    h.check("1 typed over the view: the distance box takes the keyboard", box is not None,
            a.focus_name())
    h.check("the box shows the 1", box is not None and box.text() == "1", box and box.text())
    h.check("the view did not jump (FreeCAD's key 1)", camera() == s["camera"],
            (camera(), s["camera"]))
    h.check("the dialog stays open", p is not None)
    keys_to_focus("5", enter=True)  # typing goes on in the box; Enter is OK


digit_in_box.wait_ms = 1500


def done_15():
    h.check("Enter finished the extrude", xpanel() is None and not Gui.Control.activeDialog())
    h.check("15 typed: 40 x 30 x 15", near(h.solid_volume(), AREA * 15), h.solid_volume())
    h.check("one extrude", len(extrudes()) == 1, [o.Name for o in extrudes()])
    h.check("no value box left", not a.value_boxes(visible_only=False))
    h.fit()
    h.shot("1-typed-15")


# -- Press Pull: the same -----------------------------------------------------------------
def press_q():
    h.press("q")


def click_top():
    h.click(V(20, 15, 15))


def pp_type_4():
    p = ppanel()
    h.check("Press Pull took the top face", p is not None and p.mode == "faces", p and p.mode)
    h.check("Press Pull: one value box", len(a.value_boxes()) == 1, len(a.value_boxes()))
    h.press("4")


def pp_digit_in_box():
    box = focused_box()
    h.check("4 typed over the view goes into Press Pull's box", box is not None and
            box.text() == "4", (a.focus_name(), box and box.text()))
    keys_to_focus("", enter=True)


pp_digit_in_box.wait_ms = 1500


def pp_done():
    h.check("Enter finished Press Pull", ppanel() is None and not Gui.Control.activeDialog())
    h.check("pulled 4: 40 x 30 x 19", near(h.solid_volume(), AREA * 19), h.solid_volume())
    h.check("no value box left", not a.value_boxes(visible_only=False))
    h.fit()


# -- inside a sketch digits are the sketch's -----------------------------------------------
def sketch_on_top():
    h.ribbon("Create Sketch")


def click_top_face():
    h.click(V(30, 22, 19))


def digit_in_sketch():
    sk = h.in_sketch()
    h.check("sketch open on the top face", sk is not None)
    s["square"] = sk
    h.press("5")


def sketch_kept_digit():
    h.check("a digit in a sketch reaches no value box", focused_box() is None, a.focus_name())
    h.check("no value box exists in a sketch", not a.value_boxes(visible_only=False))
    sk = s.get("square")
    if sk is not None:
        x0, y0 = h.to_sketch(sk, V(10, 5, 19))
        x1, y1 = h.to_sketch(sk, V(20, 15, 19))
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    s["volume"] = h.solid_volume()
    h.ribbon("Finish Sketch")


# -- a dialog field with the keyboard keeps the digits ---------------------------------------
def e_again():
    h.fit()
    h.press("e")


def field_keeps_keys():
    p = xpanel()
    h.check("E opens Extrude on the square", p is not None and len(p.profiles) == 1,
            p and p.profiles)
    if p is None:
        return
    bs.click_widget(p.distance.widget)  # the person clicked into the Distance field
    edit = p.distance.widget.findChild(QtWidgets.QLineEdit)
    h.check("the Distance field has the keyboard", edit is not None and edit.hasFocus(),
            a.focus_name())
    QtTest.QTest.keyClick(edit, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(edit, "7")
    QtWidgets.QApplication.processEvents()
    h.check("7 went into the field, not into the box", focused_box() is None and
            edit.text() == "7", (a.focus_name(), edit.text()))
    QtTest.QTest.keyClick(edit, QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()


def boss_7():
    p = xpanel()
    h.check("7: a 10 x 10 x 7 boss", near(h.solid_volume(), s["volume"] + 700.0), h.solid_volume())
    h.check("the taper handle has a value box", p is not None and "taper" in p.draggers
            and "taper" in p.value_boxes.shown(), p and list(p.value_boxes.shown()))
    if p is None or "taper" not in p.draggers:
        return
    taper = p.draggers["taper"]
    h.move(h.screen_point(taper.point_at(taper.angle())))  # the mouse over the taper handle


def hover_then_digit():
    p = xpanel()
    h.check("the taper handle is the one hovered", p is not None and p.value_boxes.last == "taper",
            p and p.value_boxes.last)
    h.press("3")


def digit_in_taper_box():
    p = xpanel()
    box = focused_box()
    h.check("3 typed goes into the taper's box", box is not None and p is not None
            and box is p.value_boxes.boxes.get("taper") and box.text() == "3",
            (a.focus_name(), box and box.text()))
    keys_to_focus("", enter=True)


digit_in_taper_box.wait_ms = 1500


def tapered_done():
    from sciforge import extrude

    h.check("Enter finished the tapered boss", xpanel() is None)
    feats = extrudes()
    h.check("two extrudes", len(feats) == 2, [o.Name for o in feats])
    taper = extrude.read(feats[-1])[1]["taper"] if len(feats) == 2 else None
    h.check("the taper is 3 degrees", taper is not None and near(taper, 3.0), taper)
    h.check("the boss is tapered (not 700)", not near(h.solid_volume(), s["volume"] + 700.0),
            h.solid_volume())
    h.check("no value box left", not a.value_boxes(visible_only=False))
    h.shot("2-tapered")


h.run(
    "extrude_feel_keys",
    [
        new_design,
        pick_xy,
        draw,
        finish_sketch,
        press_e,
        opened,
        digit_in_box,
        done_15,
        press_q,
        click_top,
        pp_type_4,
        pp_digit_in_box,
        pp_done,
        sketch_on_top,
        click_top_face,
        digit_in_sketch,
        sketch_kept_digit,
        e_again,
        field_keeps_keys,
        boss_7,
        hover_then_digit,
        digit_in_taper_box,
        tapered_done,
    ],
)
