# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fillet (F) the way Fusion users really use it, trying to break it (QA, only real input).

Path 1, beginner: F with nothing selected, OK, Enter over the view, Esc. Nothing is made,
        nothing is left in the undo history.
Path 2, wrong order: the radius typed before any pick, then an edge, then the face that
        edge belongs to (the edge is rounded once, not twice), OK.
Path 3, Esc in the middle of picking: the part comes back exactly as it was (no
        see-through leftover, nothing selected), and the next F starts empty.
Path 4, values while the preview runs: three radii typed back to back, the arrow dragged
        far out (too big: said in the dialog, OK refused) and back through the edge
        (the radius stops at its smallest and the arrow comes back to it).
Path 5, edit from the timeline three times (add an edge, drop it again, Cancel), then
        undo / redo through the edits.
Path 6, another command's key while the dialog is open: E keeps a good fillet and opens
        Extrude; Q drops a fillet that does not fit and opens Press Pull; F again keeps
        the fillet and starts a new one with nothing picked (not the old picks).
Path 7, save while the dialog is open (Ctrl+S): the file never holds a half-made
        fillet. Close, reopen, edit the fillet from the timeline, Press Pull its face.

Numbers by hand: a 40 x 30 x 10 box (see blend_steps for the round/corner formulas).
"""
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
RIGHT_TOP = V(40, 15, 10)
RIGHT_BOTTOM = V(40, 15, 0)
BACK_TOP = V(20, 30, 10)
LEFT_TOP = V(0, 15, 10)
FRONT_RIGHT = V(40, 0, 5)
TOP_FACE = V(20, 15, 10)


def step(fn, name):
    fn.__name__ = name
    return fn


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def one_edge(r, length=40.0):
    return b.BOX - length * b.spandrel(r)


def top_face(r):
    """All four top edges rounded: four edge rounds, four corners where two meet."""
    return b.BOX - 140.0 * b.spandrel(r) + 4 * b.corner(r)


def picks():
    p = b.blend_panel()
    return list(p.refs) if p else None


# -- Path 1: beginner, nothing picked ---------------------------------------------------------
def p1_f():
    s["undo"] = doc().UndoCount
    s["objects"] = len(doc().Objects)
    h.click_empty()
    h.press("f")


def p1_ok():
    p = b.blend_panel()
    h.check("P1 F with nothing selected opens Fillet", p is not None and dialog_open())
    b.no_popups("F with nothing selected")
    h.task_button("OK")


def p1_refused():
    p = b.blend_panel()
    h.check("P1 OK with nothing picked keeps the dialog open", p is not None and dialog_open())
    text = p.message.text() if p else ""
    h.check("P1 the dialog says to pick edges", "select the edges" in text.lower(), text)
    h.check("P1 nothing was made", len(doc().Objects) == s["objects"], len(doc().Objects))
    h.shot("p1-ok-refused")
    h.click_empty()
    h.press(QtCore.Qt.Key_Return)


def p1_enter():
    h.check("P1 Enter over the view with nothing picked keeps the dialog", dialog_open())
    h.press(QtCore.Qt.Key_Escape)


def p1_esc():
    h.check("P1 Esc closes the dialog", not dialog_open())
    h.check("P1 still nothing new", len(doc().Objects) == s["objects"], len(doc().Objects))
    h.check("P1 undo history unchanged", doc().UndoCount == s["undo"], doc().UndoCount)
    h.check("P1 no step left half open", not doc().HasPendingTransaction)
    h.check("P1 the box is unchanged", b.close(h.solid_volume(), b.BOX), h.solid_volume())


# -- Path 2: the radius before the picks, an edge and then its face ---------------------------
def p2_f():
    h.press("f")


def p2_radius_first():
    p = b.blend_panel()
    if p:
        b.type_into(p.radius.widget, "3")


def p2_nothing_yet():
    p = b.blend_panel()
    h.check("P2 a radius alone builds nothing", p is not None and p.target is None)
    h.check("P2 and shows no error", p is not None and "⚠" not in p.message.text())
    h.check("P2 the box is unchanged", b.close(h.solid_volume(), b.BOX), h.solid_volume())
    h.fit()
    h.click_edge(FRONT_TOP)


def p2_edge():
    p = b.blend_panel()
    v = h.solid_volume()
    h.check("P2 the edge takes the radius typed before", b.close(v, one_edge(3)), v)
    h.check("P2 one pick", p is not None and len(p.refs) == 1, picks())
    h.click(TOP_FACE)


def p2_face():
    p = b.blend_panel()
    h.check("P2 the face is added", p is not None and len(p.refs) == 2, picks())
    v = h.solid_volume()
    h.check(
        "P2 preview: all four top edges r 3 (the front edge once)",
        b.close(v, top_face(3)),
        (v, top_face(3), p and p.message.text()),
    )
    h.check("P2 no error in the dialog", p is not None and "⚠" not in p.message.text())
    h.shot("p2-edge-and-face")
    h.task_button("OK")


def p2_ok():
    h.check("P2 OK closes the dialog", not dialog_open())
    fl = b.blends()
    shape = h.body().Shape
    h.check("P2 one fillet", len(fl) == 1, fl)
    h.check("P2 the result is the four rounds", b.close(shape.Volume, top_face(3)), shape.Volume)
    h.check(
        "P2 the fillet computed cleanly", fl and "Invalid" not in fl[0].State, fl and fl[0].State
    )
    h.check("P2 valid solid", shape.isValid())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p2_undone():
    h.check("P2 Ctrl+Z removes it", b.close(h.solid_volume(), b.BOX) and not b.blends())


# -- Path 3: Esc in the middle of picking -----------------------------------------------------
def p3_f():
    h.click_empty()
    h.press("f")


def p3_pick():
    h.fit()
    h.click_edge(FRONT_TOP)


def p3_second_pick():
    p = b.blend_panel()
    h.check("P3 first edge picked", p is not None and len(p.refs) == 1, picks())
    h.click_edge(RIGHT_TOP)


def p3_esc():
    p = b.blend_panel()
    h.check("P3 second edge picked", p is not None and len(p.refs) == 2, picks())
    h.press(QtCore.Qt.Key_Escape)


def p3_after_esc():
    h.check("P3 Esc cancels the fillet", not dialog_open() and not b.blends())
    h.check("P3 the box is as it was", b.close(h.solid_volume(), b.BOX), h.solid_volume())
    h.check("P3 nothing selected", not Gui.Selection.getSelectionEx())
    h.check("P3 no see-through leftover", not b.see_through(), b.see_through())
    tip = h.body().Tip
    h.check("P3 the part is drawn", tip.ViewObject.isVisible() and h.body_visible())
    h.check("P3 the part is clickable", tip.ViewObject.Selectable)
    h.shot("p3-after-esc")
    h.press("f")


def p3_fresh():
    p = b.blend_panel()
    h.check("P3 the next F starts with nothing picked", p is not None and p.refs == [], picks())
    h.press(QtCore.Qt.Key_Escape)


# -- Path 4: values while the preview runs ----------------------------------------------------
def p4_f():
    h.check("P4 Esc closed the empty dialog", not dialog_open())
    h.press("f")


def p4_pick():
    h.fit()
    h.click_edge(FRONT_TOP)


def p4_type_fast():
    p = b.blend_panel()
    if p:
        for text in ("2", "5", "0.5"):
            b.type_into(p.radius.widget, text)


def p4_fast_result():
    p = b.blend_panel()
    v = h.solid_volume()
    h.check("P4 the last radius typed wins (0.5)", b.close(v, one_edge(0.5)), v)
    h.check("P4 the field shows it", p is not None and abs(p.radius.value() - 0.5) < 1e-9)


def p4_drag_far():
    p = b.blend_panel()
    if p is None or not p.arrows:
        h.check("P4 arrow to drag", False)
        return
    s["good"] = h.solid_volume()
    start, end = b.arrow_screen(p, along=25.0)
    h.drag(start, end)


def p4_too_big():
    p = b.blend_panel()
    r = p.radius.value() if p else 0
    h.check("P4 dragging far out makes the radius big", r > 15, r)
    text = p.message.text() if p else ""
    h.check("P4 too big: said in the dialog", "too big" in text, text)
    h.check(
        "P4 the preview keeps the last good result",
        b.close(h.solid_volume(), s["good"]),
        h.solid_volume(),
    )
    h.shot("p4-too-big")
    h.task_button("OK")


def p4_refused():
    h.check("P4 OK refused while too big", dialog_open() and b.blend_panel() is not None)


p4_refused.wait_ms = 1500  # the dialog works out the largest radius that fits


def p4_full_message():
    p = b.blend_panel()
    if p is None:
        return
    text = p.message.text()
    h.check("P4 the hint names the largest radius", "largest radius" in text, text)
    shown = p.message.height() >= p.message.heightForWidth(p.message.width()) - 1
    visible = p.message.visibleRegion().boundingRect().height()
    h.check(
        "P4 the whole message is readable (not cut off)",
        shown and visible >= p.message.height() - 1,
        (p.message.height(), p.message.heightForWidth(p.message.width()), visible),
    )
    h.shot("p4-message")


def p4_drag_back():
    p = b.blend_panel()
    if p is None or not p.arrows:
        h.check("P4 arrow to drag back", False)
        return
    start, end = b.arrow_screen(p, along=-(p.radius.value() + 15.0))
    h.drag(start, end)


def p4_dragged_back():
    p = b.blend_panel()
    if p is None:
        return
    r = p.radius.value()
    h.check("P4 through the edge: the radius stops at its smallest, not below 0", 0 < r < 1, r)
    dragger, spot = p.arrows[0][0], p.arrows[0][1]
    h.check(
        "P4 the arrow comes back to the radius shown",
        abs(dragger.distance() - r * spot["per_unit"]) < 1e-6,
        (dragger.distance(), r),
    )
    h.check("P4 no error once it fits again", "⚠" not in p.message.text(), p.message.text())
    h.check("P4 the preview follows", b.close(h.solid_volume(), one_edge(r)), h.solid_volume())
    b.type_into(p.radius.widget, "1.5")


def p4_ok():
    p = b.blend_panel()
    h.check(
        "P4 typed 1.5 moves the arrow",
        p is not None and abs(p.arrows[0][0].distance() - 1.5 * p.arrows[0][1]["per_unit"]) < 1e-6,
    )
    h.task_button("OK")


def p4_done():
    h.check("P4 closed", not dialog_open())
    h.check("P4 fillet r 1.5 kept", b.close(h.solid_volume(), one_edge(1.5)), h.solid_volume())
    h.check("P4 one fillet", len(b.blends()) == 1, b.blends())
    h.fit()


# -- Path 5: edit from the timeline three times, undo / redo through the edits -----------------
def p5_edit1():
    b.timeline_double_click("Fillet 1")


def p5_editing1():
    p = b.blend_panel()
    h.check("P5 editing Fillet 1", p is not None and not p.created, p)
    h.check("P5 its edge is picked", p is not None and len(p.refs) == 1, picks())
    h.check("P5 radius 1.5 shown", p is not None and abs(p.radius.value() - 1.5) < 1e-9)
    h.click_edge(RIGHT_TOP)


def p5_added():
    p = b.blend_panel()
    h.check("P5 a second edge added while editing", p is not None and len(p.refs) == 2, picks())
    if p:
        b.type_into(p.radius.widget, "2")


def p5_ok1():
    v = h.solid_volume()
    expect = b.BOX - 70.0 * b.spandrel(2) + b.corner(2)
    h.check("P5 preview two edges r 2", b.close(v, expect), (v, expect))
    h.task_button("OK")


def p5_edit2():
    s["two"] = h.solid_volume()
    h.check("P5 still one fillet", len(b.blends()) == 1)
    h.fit()
    b.timeline_double_click("Fillet 1")


def p5_editing2():
    p = b.blend_panel()
    h.check("P5 second edit shows both edges", p is not None and len(p.refs) == 2, picks())
    h.click_edge(RIGHT_TOP)


def p5_dropped():
    p = b.blend_panel()
    h.check("P5 clicking the edge again drops it", p is not None and len(p.refs) == 1, picks())
    h.task_button("OK")


def p5_edit3():
    h.check("P5 one edge r 2 now", b.close(h.solid_volume(), one_edge(2)), h.solid_volume())
    h.fit()
    b.timeline_double_click("Fillet 1")


def p5_editing3():
    p = b.blend_panel()
    if p:
        b.type_into(p.radius.widget, "0.16 in")


def p5_cancel():
    r = 0.16 * 25.4
    p = b.blend_panel()
    h.check(
        "P5 a value in inches is taken (0.16 in = 4.064 mm)", p and abs(p.radius.value() - r) < 1e-9
    )
    h.check("P5 preview r 4.064", b.close(h.solid_volume(), one_edge(r)), h.solid_volume())
    h.task_button("Cancel")


def p5_cancelled():
    h.check("P5 Cancel keeps r 2", b.close(h.solid_volume(), one_edge(2)), h.solid_volume())
    h.check("P5 the fillet is shown again", h.body().Tip.ViewObject.isVisible())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p5_undo1():
    h.check("P5 Ctrl+Z: two edges again", b.close(h.solid_volume(), s["two"]), h.solid_volume())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p5_undo2():
    h.check("P5 Ctrl+Z: one edge r 1.5", b.close(h.solid_volume(), one_edge(1.5)))
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p5_redo1():
    h.check("P5 Ctrl+Y: two edges", b.close(h.solid_volume(), s["two"]), h.solid_volume())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p5_redo2():
    h.check("P5 Ctrl+Y: one edge r 2", b.close(h.solid_volume(), one_edge(2)), h.solid_volume())
    h.check("P5 one fillet, valid", len(b.blends()) == 1 and h.body().Shape.isValid())
    s["v"] = h.solid_volume()


# -- Path 6: another command's key while the dialog is open -------------------------------------
def p6_f():
    h.click_empty()
    h.press("f")


def p6_pick():
    h.fit()
    h.click_edge(BACK_TOP)


def p6_press_e():
    p = b.blend_panel()
    h.check("P6 back edge picked", p is not None and len(p.refs) == 1, picks())
    h.press("e")


def p6_extrude_open():
    from sciforge import extrude_ui

    h.check("P6 E finished the fillet", len(b.blends()) == 2, b.blends())
    expect = s["v"] - 40 * b.spandrel(1)
    h.check("P6 the fillet was kept", b.close(h.solid_volume(), expect), h.solid_volume())
    x = extrude_ui.ExtrudePanel.last
    h.check("P6 Extrude is open now", dialog_open() and x is not None and not x._closed)
    b.no_popups("E in the Fillet dialog")
    s["v"] = expect
    h.press(QtCore.Qt.Key_Escape)


def p6_f2():
    h.check("P6 Esc closed Extrude", not dialog_open())
    h.press("f")


def p6_pick2():
    h.fit()
    h.click_edge(FRONT_RIGHT)


def p6_too_big():
    p = b.blend_panel()
    h.check("P6 vertical edge picked", p is not None and len(p.refs) == 1, picks())
    if p:
        b.type_into(p.radius.widget, "45")


def p6_press_q():
    p = b.blend_panel()
    h.check("P6 45 is too big", p is not None and "too big" in p.message.text())
    h.press("q")


def p6_presspull_open():
    from sciforge import presspull_ui

    h.check("P6 Q dropped the fillet that does not fit", len(b.blends()) == 2, b.blends())
    h.check("P6 the part is unchanged", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    pp = presspull_ui.PressPullPanel.last
    h.check("P6 Press Pull is open now", dialog_open() and pp is not None and not pp._closed)
    h.press(QtCore.Qt.Key_Escape)


def p6_f3():
    h.check("P6 Esc closed Press Pull", not dialog_open())
    h.press("f")


def p6_pick3():
    h.fit()
    h.click_edge(LEFT_TOP)


def p6_press_f_again():
    p = b.blend_panel()
    h.check("P6 left edge picked", p is not None and len(p.refs) == 1, picks())
    s["first_panel"] = p
    h.press("f")


def p6_new_fillet():
    p = b.blend_panel()
    h.check("P6 F again kept the first fillet", len(b.blends()) == 3, b.blends())
    h.check(
        "P6 and opened a new Fillet dialog",
        p is not None and p is not s["first_panel"] and dialog_open(),
    )
    h.check("P6 the new one starts with nothing picked", p is not None and p.refs == [], picks())
    h.check("P6 it shows no error", p is not None and "⚠" not in p.message.text())
    h.check("P6 the model is valid", h.body().Shape.isValid())
    h.press(QtCore.Qt.Key_Escape)


def p6_done():
    h.check("P6 Esc closed it", not dialog_open())
    h.check("P6 three fillets", len(b.blends()) == 3, b.blends())
    s["v"] = h.solid_volume()
    h.shot("p6-end")


# -- Path 7: Ctrl+S with the dialog open; save, close, reopen, edit --------------------------------
def p7_save_first():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-fillet-qa-"), "fillet_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("P7 saved", os.path.isfile(path), path)
    h.press("f")


def p7_pick():
    h.fit()
    h.click_edge(RIGHT_BOTTOM)


def p7_ctrl_s():
    p = b.blend_panel()
    h.check("P7 picked, preview shown", p is not None and p.target is not None, picks())
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p7_saved():
    h.check("P7 Ctrl+S finished the dialog first", not dialog_open())
    h.check("P7 the fillet was kept", len(b.blends()) == 4, b.blends())
    h.check("P7 the design is saved (nothing unsaved)", not doc().isTouched() and not b.modified())
    s["v"] = h.solid_volume()
    App.closeDocument(doc().Name)


def p7_open():
    App.openDocument(s["path"])
    h.fit()


def p7_reopened():
    h.check("P7 reopened: same part", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("P7 four fillets in the file", len(b.blends()) == 4, b.blends())
    h.check("P7 all of them computed", all("Invalid" not in f.State for f in b.blends()))
    b.timeline_double_click("Fillet 1")


def p7_editing():
    p = b.blend_panel()
    h.check("P7 editing Fillet 1 after reopening", p is not None and not p.created)
    h.check("P7 its edge is picked", p is not None and len(p.refs) == 1, picks())
    h.check("P7 radius 2 remembered", p is not None and abs(p.radius.value() - 2) < 1e-9)
    s["before"] = h.solid_volume()
    if p:
        b.type_into(p.radius.widget, "3")


def p7_edit_ok():
    h.task_button("OK")


def p7_edited():
    v = h.solid_volume()
    h.check("P7 the edit changed the part", v < s["before"] - 1, (v, s["before"]))
    h.check(
        "P7 every later fillet still computes", all("Invalid" not in f.State for f in b.blends())
    )
    h.check("P7 valid solid", h.body().Shape.isValid())
    h.check("P7 the last step is shown", h.body().Tip.ViewObject.isVisible())
    h.shot("p7-end")


h.run(
    "fillet_qa",
    b.box_steps("FilletQA")
    + [
        p1_f,
        p1_ok,
        p1_refused,
        p1_enter,
        p1_esc,
        p2_f,
        p2_radius_first,
        p2_nothing_yet,
        p2_edge,
        p2_face,
        p2_ok,
        p2_undone,
        p3_f,
        p3_pick,
        p3_second_pick,
        p3_esc,
        p3_after_esc,
        p3_fresh,
        p4_f,
        p4_pick,
        p4_type_fast,
        p4_fast_result,
        p4_drag_far,
        p4_too_big,
        p4_refused,
        p4_full_message,
        p4_drag_back,
        p4_dragged_back,
        p4_ok,
        p4_done,
        p5_edit1,
        p5_editing1,
        p5_added,
        p5_ok1,
        p5_edit2,
        p5_editing2,
        p5_dropped,
        p5_edit3,
        p5_editing3,
        p5_cancel,
        p5_cancelled,
        p5_undo1,
        p5_undo2,
        p5_redo1,
        p5_redo2,
        p6_f,
        p6_pick,
        p6_press_e,
        p6_extrude_open,
        p6_f2,
        p6_pick2,
        p6_too_big,
        p6_press_q,
        p6_presspull_open,
        p6_f3,
        p6_pick3,
        p6_press_f_again,
        p6_new_fillet,
        p6_done,
        p7_save_first,
        p7_pick,
        p7_ctrl_s,
        p7_saved,
        p7_open,
        p7_reopened,
        p7_editing,
        p7_edit_ok,
        p7_edited,
    ],
)
