# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude and Press Pull the way Fusion users really use them (QA, only real input).

Path 1, beginner: E and Q in an empty design, OK with nothing picked, Esc.
Path 2, wrong order: Direction and distance chosen before any profile, then the
        ring; To Object chosen, then Esc in the middle of the pick; the cancelled
        extrude leaves nothing behind and the sketch visible.
Path 3, values while the preview runs: two distances typed back to back, the arrow
        dragged far up and far down through the part (auto Cut and back to Join), a
        zero distance and an impossible taper (message in the dialog, OK refused).
Path 4, another command's key while a dialog is open: Q in Extrude, E in Press
        Pull, Ctrl+Z in a dialog with a preview.
Path 5, editing from the timeline twice, then undo / redo of both edits.
Path 6, save, close, reopen, edit the extrude and the Press Pull again.

Numbers by hand: 40 x 30 x 10 block (a ring around an r5 disc), a 10 x 10 column.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
RING = 1200.0 - 25.0 * math.pi
DISC = 25.0 * math.pi


def xpanel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def ppanel():
    from sciforge import presspull_ui

    return presspull_ui.PressPullPanel.last


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def extrudes():
    from sciforge import extrude

    return [o for o in doc().Objects if extrude.is_extrude(o)]


def presspulls():
    from sciforge import presspull

    return [o.Name for o in doc().Objects if presspull.is_press_pull(o)]


def helpers():
    from sciforge import extrude

    return [o.Name for o in doc().Objects if extrude.is_helper(o)]


def zrange():
    b = h.body().Shape.BoundBox
    return (round(b.ZMin, 4), round(b.ZMax, 4))


def shown(body=None):
    """The part is drawn: FreeCAD shows a body through its Tip feature."""
    b = body or h.body()
    if b is None or b.Tip is None:
        return False
    return bool(b.ViewObject.Visibility and b.Tip.ViewObject.Visibility)


def dialog_open():
    return bool(Gui.Control.activeDialog())


def step(fn, name):
    fn.__name__ = name
    return fn


def sketch_rect_on(tag, point, x0, y0, x1, y1, circle=None):
    """Create Sketch, click the plane/face at `point`, draw a rectangle (global x/y; the
    face is horizontal) and optionally a circle (cx, cy, r), Finish Sketch."""

    def create():
        h.click_empty()
        h.ribbon("Create Sketch")

    def pick():
        h.check("no pop-up on Create Sketch (%s)" % tag, not h.popups(), h.popups())
        h.fit()
        h.click(point)

    def draw():
        sk = h.in_sketch()
        h.check("sketch %s open" % tag, sk is not None)
        if sk:
            ax, ay = h.to_sketch(sk, V(x0, y0, point.z))
            bx, by = h.to_sketch(sk, V(x1, y1, point.z))
            h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
            if circle:
                cx, cy = h.to_sketch(sk, V(circle[0], circle[1], point.z))
                h.draw_circle(sk, cx, cy, circle[2])
            s["sketch_" + tag] = sk

    def finish():
        h.ribbon("Finish Sketch")

    def after():
        h.check("left sketch %s" % tag, h.in_sketch() is None)
        h.fit()

    return [
        step(create, "sketch_%s_create" % tag),
        step(pick, "sketch_%s_pick" % tag),
        step(draw, "sketch_%s_draw" % tag),
        step(finish, "sketch_%s_finish" % tag),
        step(after, "sketch_%s_after" % tag),
    ]


# -- Path 1: beginner, nothing to extrude --------------------------------------------------
def p1_new():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("QAEmpty")
    h.fit()


def p1_e():
    h.press("e")


def p1_e_open():
    p = xpanel()
    h.check("E in an empty design opens Extrude", dialog_open() and p is not None)
    h.check("no pop-up", not h.popups(), h.popups())
    h.check("it says what to do first", "sketch" in p.message.text().lower(), p.message.text())
    h.shot("p1-empty")
    h.task_button("OK")


def p1_ok_refused():
    p = xpanel()
    h.check("OK with nothing picked keeps the dialog open", dialog_open() and not p._closed)
    h.check("nothing was created", len(doc().Objects) == 0, [o.Name for o in doc().Objects])
    h.check("the dialog says why", p.message.text() != "", p.message.text())
    h.press(QtCore.Qt.Key_Escape)


def p1_esc():
    h.check("Esc closes Extrude", not dialog_open())
    h.check("still nothing in the design", len(doc().Objects) == 0)
    h.press("q")


def p1_q_open():
    p = ppanel()
    h.check("Q in an empty design opens Press Pull", dialog_open() and p is not None)
    h.check("it says a solid is needed", "solid" in p.message.text().lower(), p.message.text())
    h.task_button("OK")


def p1_q_ok():
    h.check("Press Pull OK with nothing picked stays open", dialog_open())
    h.task_button("Cancel")


def p1_done():
    h.check("Cancel closes Press Pull", not dialog_open())
    h.check("the empty design is still empty", len(doc().Objects) == 0)


# -- Path 2: options before the profile; Esc while picking -----------------------------------
def p2_new():
    App.newDocument("QAOrder")
    h.fit()


def p2_e():
    h.press("e")


def p2_options_first():
    p = xpanel()
    h.check("two profiles: nothing picked by itself", p.target is None, p.profiles)
    h.check("choose Direction: Symmetric first", ui.choose(p.direction, "Symmetric"))
    ui.type_into(p.distance.widget, "20")


def p2_nothing_built():
    p = xpanel()
    h.check("options alone build nothing", p.target is None and not extrudes())
    h.check("no message yet", "⚠" not in p.message.text(), p.message.text())
    h.fit()
    h.click(V(5, 5, 0))


def p2_ring_symmetric():
    p = xpanel()
    h.check("the ring takes the options chosen before", p.target is not None, p.message.text())
    h.check(
        "symmetric half length 20: ring x 40",
        near(h.solid_volume(), RING * 40.0),
        (h.solid_volume(), p.message.text()),
    )
    h.check("z -20 to 20", zrange() == (-20.0, 20.0), zrange())
    texts = [p.extent.itemText(i) for i in range(p.extent.count())]
    model = p.extent.model()
    to_object = p.extent.findText("To Object")
    enabled = to_object >= 0 and bool(
        model.flags(model.index(to_object, 0)) & QtCore.Qt.ItemIsEnabled
    )
    h.check("Symmetric does not offer To Object (Fusion)", not enabled, texts)
    h.shot("p2-symmetric")
    h.check("choose Direction: One Side", ui.choose(p.direction, "One Side"))


def p2_to_object():
    p = xpanel()
    h.check("choose Extent: To Object", ui.choose(p.extent, "To Object"))


def p2_waiting_for_object():
    p = xpanel()
    h.check("the Object box takes the next click", p.active == "extent_object", p.active)
    h.check("no error while waiting for the object", "⚠" not in p.message.text(), p.message.text())
    h.press(QtCore.Qt.Key_Escape)


def p2_after_esc():
    sk = s["sketch_order"]
    h.check("Esc in the middle of a pick cancels the extrude", not dialog_open())
    h.check("no extrude left", not extrudes(), [o.Name for o in extrudes()])
    h.check("no helper left", not helpers(), helpers())
    h.check("no solid", h.solid_volume() < 1e-9, h.solid_volume())
    h.check("the sketch is visible again", sk.ViewObject.Visibility)
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    h.fit()
    h.press("e")


def p2_disc_first():
    p = xpanel()
    h.check("a new Extrude starts with the defaults", p.direction.currentText() == "One Side")
    h.click(V(20, 15, 0))


def p2_then_ring():
    p = xpanel()
    h.check("disc picked", len(p.profiles) == 1, p.profiles)
    h.click(V(5, 5, 0))


def p2_both():
    p = xpanel()
    h.check("ring added", len(p.profiles) == 2, p.profiles)
    h.check("block 40 x 30 x 10", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.task_button("OK")


def p2_done():
    h.check("block kept", near(h.solid_volume(), 12000.0) and not dialog_open())
    h.check("one extrude", len(extrudes()) == 1)


# -- Path 2b: pick a face, click it again (nothing left), the part must stay drawn -----------
def p2b_e():
    h.click_empty()
    h.press("e")


def p2b_face():
    h.fit()
    h.click(V(30, 25, 10))


def p2b_face_picked():
    p = xpanel()
    h.check("the top face starts a face extrude", p.target is not None, p.message.text())
    h.check("preview grows the block", h.solid_volume() > 12000.5, h.solid_volume())
    # The preview now covers the picked face: a person clicks the same face where it is
    # shown, at the end of the preview.
    h.click(V(30, 25, 10 + p.distance.value()))


def p2b_face_dropped():
    p = xpanel()
    h.check("clicking it again drops it", not p.profiles and p.target is None, p.profiles)
    h.check("the block is back", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.check("the block is still drawn (its last feature shown)", shown())
    h.shot("p2b-dropped")
    h.press(QtCore.Qt.Key_Escape)


def p2b_q():
    h.check("Esc closed Extrude", not dialog_open())
    h.check("still drawn after Esc", shown())
    h.press("q")


def p2b_q_face():
    h.fit()
    h.click(V(30, 25, 10))


def p2b_q_picked():
    p = ppanel()
    h.check("Press Pull took the face", p.target is not None, p.message.text())
    h.click(V(30, 25, 10))


def p2b_q_dropped():
    p = ppanel()
    h.check("clicking it again drops it", p.target is None and not p.names, p.names)
    h.check("the block is still drawn after Press Pull dropped its face", shown())
    h.press(QtCore.Qt.Key_Escape)


def p2b_done():
    h.check("Esc closed Press Pull", not dialog_open())
    h.check("still drawn", shown() and near(h.solid_volume(), 12000.0))


# -- Path 3: values while the preview runs, handles dragged far ----------------------------
def p3_e():
    h.fit()
    h.press("e")


def p3_type_fast():
    p = xpanel()
    h.check("the column profile is picked by itself", p.target is not None, p.message.text())
    h.check("Join out of the part", p.operation.currentText() == "Join", p.operation.currentText())
    # Two values typed back to back: the preview of the first is still pending.
    ui.type_into(p.distance.widget, "25")
    ui.type_into(p.distance.widget, "-5")


def p3_auto_cut():
    p = xpanel()
    h.check("into the part: Cut by itself", p.operation.currentText() == "Cut")
    h.check(
        "the last value wins: a 10 x 10 x 5 pocket",
        near(h.solid_volume(), 11500.0),
        (h.solid_volume(), p.message.text()),
    )
    h.fit()


def _arrow_drag(p, pixels):
    origin = p.dragger.root.getChild(0).translation.getValue().getValue()
    place = p.dragger.root.getChild(0)
    axis = place.rotation.getValue().multVec(p.dragger.coin.SbVec3f(1, 0, 0)).getValue()
    head = V(*origin) + V(*axis) * (p.dragger.distance() + p.dragger.size * 0.9)
    a = h.screen_point(head)
    h.drag(a, QtCore.QPoint(a.x(), a.y() - pixels), steps=20)


def p3_drag_far_up():
    p = xpanel()
    h.check("arrow shown", p.dragger is not None)
    if p.dragger is not None:
        _arrow_drag(p, 260)


def p3_far_up():
    p = xpanel()
    h.check("dragged far up: a long distance", p.distance.value() > 10.0, p.distance.value())
    h.check("out of the part: Join again", p.operation.currentText() == "Join")
    want = 12000.0 + 100.0 * p.distance.value()
    h.check(
        "column as long as the field says", near(h.solid_volume(), want), (h.solid_volume(), want)
    )
    h.shot("p3-far-up")
    h.fit()


def p3_drag_far_down():
    p = xpanel()
    if p.dragger is not None:
        _arrow_drag(p, -520)


def p3_far_down():
    p = xpanel()
    h.check("dragged through the part: negative", p.distance.value() < -10.0, p.distance.value())
    h.check("into the part: Cut", p.operation.currentText() == "Cut")
    h.check(
        "a square hole through the block",
        near(h.solid_volume(), 11000.0),
        (h.solid_volume(), p.message.text()),
    )
    h.shot("p3-far-down")
    ui.type_into(p.distance.widget, "0")


def p3_zero():
    p = xpanel()
    h.check("zero: the dialog says so", "zero" in p.message.text().lower(), p.message.text())
    h.task_button("OK")


def p3_zero_ok():
    h.check("OK refused for a zero distance", dialog_open() and not xpanel()._closed)
    ui.type_into(xpanel().distance.widget, "5 mm")


def p3_five_mm():
    p = xpanel()
    h.check("'5 mm' typed with its unit", near(p.distance.value(), 5.0), p.distance.value())
    h.check("Join again", p.operation.currentText() == "Join", p.operation.currentText())
    h.check("column 10 x 10 x 5", near(h.solid_volume(), 12500.0), h.solid_volume())
    ui.type_into(p.taper.widget, "-60")


def p3_steep_taper():
    p = xpanel()
    h.check(
        "a taper that closes the profile is explained", "⚠" in p.message.text(), p.message.text()
    )
    h.task_button("OK")


def p3_steep_ok():
    h.check("OK refused for the impossible taper", dialog_open() and not xpanel()._closed)
    h.fit()


def p3_taper_zero():
    p = xpanel()
    ui.type_into(p.taper.widget, "10")


def p3_taper_ok():
    p = xpanel()
    h.check("taper 10 is fine", "⚠" not in p.message.text(), p.message.text())
    h.check("taper handle shown", "taper" in p.draggers, list(p.draggers))
    h.fit()


def p3_drag_taper_far():
    p = xpanel()
    handle = p.draggers.get("taper")
    if handle is None:
        return
    now, later = handle.screen_points(85.0)
    h.drag(h.screen_point(now), h.screen_point(later), steps=20)


def p3_taper_far():
    p = xpanel()
    h.check("the taper handle stops at 60 degrees", abs(p.taper.value()) <= 60.0, p.taper.value())
    ui.type_into(p.taper.widget, "0")


def p3_ok():
    p = xpanel()
    h.check("back to a straight column", near(h.solid_volume(), 12500.0), h.solid_volume())
    h.press(QtCore.Qt.Key_Return)  # with the mouse over the 3D view: Enter is OK (Fusion)


def p3_done():
    h.check("Enter over the 3D view finished the extrude", not dialog_open())
    h.check("column kept", near(h.solid_volume(), 12500.0) and shown())
    h.check("two extrudes", len(extrudes()) == 2)
    s["volume"] = h.solid_volume()


# -- Path 4: another command's key while a dialog is open -----------------------------------
def p4_e_empty():
    h.click_empty()
    h.press("e")


def p4_q_in_extrude():
    p = xpanel()
    h.check("all sketches used: nothing picked", p.target is None)
    h.press("q")


def p4_pressing_q():
    h.check("Q closes the empty Extrude", xpanel()._closed)
    p = ppanel()
    h.check("and opens Press Pull", p is not None and not p._closed and dialog_open())
    h.check("the empty Extrude left nothing", len(extrudes()) == 2)
    h.fit()
    h.click(V(30, 25, 10))


def p4_pp_face():
    p = ppanel()
    h.check("block top picked", p.target is not None and len(p.names) == 1, p.message.text())
    ui.type_into(p.field.widget, "2")


def p4_pp_2():
    want = s["volume"] + 2200.0  # the block's top around the column: 1200 - 100
    h.check("block top +2", near(h.solid_volume(), want), (h.solid_volume(), want))
    h.press("e")


def p4_e_in_pp():
    h.check("E finishes Press Pull (kept)", ppanel()._closed)
    h.check("Press Pull kept", near(h.solid_volume(), s["volume"] + 2200.0), h.solid_volume())
    p = xpanel()
    h.check("and opens Extrude", p is not None and not p._closed)
    s["volume"] = h.solid_volume()
    h.fit()
    h.click(V(30, 25, 12))


def p4_extrude_face():
    p = xpanel()
    h.check("face extrude preview", p.target is not None, p.message.text())
    h.check("preview grows the part", h.solid_volume() > s["volume"] + 1.0, h.solid_volume())
    s["objects"] = len(doc().Objects)
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p4_ctrl_z():
    h.check("Ctrl+Z in the dialog cancels it", not dialog_open(), Gui.Control.activeDialog())
    h.check(
        "the part is as before the extrude",
        near(h.solid_volume(), s["volume"]),
        (h.solid_volume(), s["volume"]),
    )
    h.check("the Press Pull is still there", len(presspulls()) == 1, presspulls())
    h.check("no helper left", not helpers(), helpers())


def p4_undo_again():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p4_undone_pp():
    want = s["volume"] - 2200.0
    h.check("the next Ctrl+Z undoes the Press Pull", near(h.solid_volume(), want), h.solid_volume())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p4_redone_pp():
    h.check("Ctrl+Y brings it back", near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.fit()


# -- Path 5: edit from the timeline twice; undo / redo the edits ----------------------------
def p5_edit():
    h.check("double-click Extrude 2", ui.double_click_timeline("Extrude 2"), ui.timeline_titles())


def p5_editing():
    p = xpanel()
    h.check("editing Extrude 2", p is not None and p.editing and not p._closed)
    if not (p and p.editing):
        return
    h.check("distance 5 back", near(p.distance.value(), 5.0), p.distance.value())
    h.check("Join back", p.operation.currentText() == "Join", p.operation.currentText())
    ui.type_into(p.distance.widget, "8")


def p5_ok():
    from PySide6 import QtTest

    h.check("preview +300", near(h.solid_volume(), s["volume"] + 300.0), h.solid_volume())
    field = xpanel().distance.widget
    field.setFocus()
    QtTest.QTest.keyClick(field, QtCore.Qt.Key_Return)  # Enter in the field: OK


def p5_edit_again():
    h.check("Enter in the distance field finished the edit", not dialog_open())
    h.check("first edit kept", near(h.solid_volume(), s["volume"] + 300.0), h.solid_volume())
    h.check(
        "double-click Extrude 2 again",
        ui.double_click_timeline("Extrude 2"),
        ui.timeline_titles(),
    )


def p5_editing_again():
    p = xpanel()
    h.check("8 is back", near(p.distance.value(), 8.0), p.distance.value())
    h.check("choose Direction: Two Sides", ui.choose(p.direction, "Two Sides"))


def p5_two_sides():
    p = xpanel()
    ui.type_into(p.distance2.widget, "3")


def p5_two_ok():
    # Side two goes down into the block: it joins nothing new.
    h.check("side two inside the block", near(h.solid_volume(), s["volume"] + 300.0))
    h.task_button("OK")


def p5_second_kept():
    h.check("second edit kept", not dialog_open())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p5_undo_1():
    h.check("undo of the 2nd edit: back to the 1st", near(h.solid_volume(), s["volume"] + 300.0))
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p5_undo_2():
    h.check("undo of the 1st edit: 5 again", near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p5_redo():
    h.check("redo: 8 again", near(h.solid_volume(), s["volume"] + 300.0), h.solid_volume())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p5_redo_2():
    h.check("redo the 2nd edit", near(h.solid_volume(), s["volume"] + 300.0))
    h.check("double-click Extrude 2", ui.double_click_timeline("Extrude 2"))


def p5_two_sides_back():
    p = xpanel()
    h.check("Two Sides back after redo", p.direction.currentText() == "Two Sides")
    h.check("side two 3 back", near(p.distance2.value(), 3.0), p.distance2.value())
    h.task_button("Cancel")


def p5_cancelled():
    h.check("Cancel on an edit changes nothing", near(h.solid_volume(), s["volume"] + 300.0))
    s["volume"] = h.solid_volume()


# -- Path 6: save, close, reopen, edit again -------------------------------------------------
def p6_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-qa-"), "qa_order.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def p6_close():
    App.closeDocument(doc().Name)


def p6_open():
    App.openDocument(s["path"])
    h.fit()


def p6_reopened():
    h.check("reopened: same volume", near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.check("timeline lists Extrude 2", "Extrude 2" in ui.timeline_titles(), ui.timeline_titles())
    h.check("double-click Extrude 2", ui.double_click_timeline("Extrude 2"))


def p6_editing():
    p = xpanel()
    h.check("editing after reopening", p is not None and p.editing and not p._closed)
    if not (p and p.editing):
        return
    h.check("Two Sides remembered", p.direction.currentText() == "Two Sides")
    h.check("8 remembered", near(p.distance.value(), 8.0), p.distance.value())
    ui.type_into(p.distance.widget, "4")


def p6_ok():
    h.check("preview 4", near(h.solid_volume(), s["volume"] - 400.0), h.solid_volume())
    h.task_button("OK")


def p6_pp_edit():
    h.check("edit kept", near(h.solid_volume(), s["volume"] - 400.0), h.solid_volume())
    s["volume"] = h.solid_volume()
    h.check("double-click Press Pull 1", ui.double_click_timeline("Press Pull 1"))


def p6_pp_editing():
    p = ppanel()
    h.check("Press Pull editing after reopening", p is not None and p.editing and not p._closed)
    if not (p and p.editing):
        return
    h.check("distance 2 back", near(p.field.value(), 2.0), p.field.value())
    ui.type_into(p.field.widget, "3")


def p6_pp_ok():
    h.check(
        "one more mm on the top", near(h.solid_volume(), s["volume"] + 1100.0), h.solid_volume()
    )
    h.task_button("OK")


def p6_done():
    h.check("kept", near(h.solid_volume(), s["volume"] + 1100.0) and not dialog_open())
    h.shot("p6-end")


h.run(
    "extrude_presspull_qa",
    [
        p1_new,
        p1_e,
        p1_e_open,
        p1_ok_refused,
        p1_esc,
        p1_q_open,
        p1_q_ok,
        p1_done,
        p2_new,
        *sketch_rect_on("order", V(12, -8, 0), 0, 0, 40, 30, circle=(20, 15, 5)),
        p2_e,
        p2_options_first,
        p2_nothing_built,
        p2_ring_symmetric,
        p2_to_object,
        p2_waiting_for_object,
        p2_after_esc,
        p2_disc_first,
        p2_then_ring,
        p2_both,
        p2_done,
        p2b_e,
        p2b_face,
        p2b_face_picked,
        p2b_face_dropped,
        p2b_q,
        p2b_q_face,
        p2b_q_picked,
        p2b_q_dropped,
        p2b_done,
        *sketch_rect_on("column", V(10, 15, 10), 5, 10, 15, 20),
        p3_e,
        p3_type_fast,
        p3_auto_cut,
        p3_drag_far_up,
        p3_far_up,
        p3_drag_far_down,
        p3_far_down,
        p3_zero,
        p3_zero_ok,
        p3_five_mm,
        p3_steep_taper,
        p3_steep_ok,
        p3_taper_zero,
        p3_taper_ok,
        p3_drag_taper_far,
        p3_taper_far,
        p3_ok,
        p3_done,
        p4_e_empty,
        p4_q_in_extrude,
        p4_pressing_q,
        p4_pp_face,
        p4_pp_2,
        p4_e_in_pp,
        p4_extrude_face,
        p4_ctrl_z,
        p4_undo_again,
        p4_undone_pp,
        p4_redone_pp,
        p5_edit,
        p5_editing,
        p5_ok,
        p5_edit_again,
        p5_editing_again,
        p5_two_sides,
        p5_two_ok,
        p5_second_kept,
        p5_undo_1,
        p5_undo_2,
        p5_redo,
        p5_redo_2,
        p5_two_sides_back,
        p5_cancelled,
        p6_save,
        p6_close,
        p6_open,
        p6_reopened,
        p6_editing,
        p6_ok,
        p6_pp_edit,
        p6_pp_editing,
        p6_pp_ok,
        p6_done,
    ],
)
