# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole (H) the way Fusion users really use it, trying to break it (QA, only real input).

Path 1, beginner: H with nothing selected, OK, Enter over the view, a click on the empty
        background, Esc. Nothing is made, nothing is left in the undo history.
Path 2, wrong order: Counterbore and its sizes typed before any pick, then an edge clicked
        before a face, then the face: the hole has the typed sizes. Enter over the 3D view
        finishes it (Fusion: Enter is OK).
Path 3, Esc in the middle of picking (face and a reference edge picked): the part is as it
        was, nothing selected, the next H starts empty. Ctrl+Z, H, Esc, Ctrl+Y: the Redo list
        survives a dialog closed without a change.
Path 4, values while the preview runs: three diameters typed back to back, 0 and a negative
        value (said in the dialog, OK waits), the depth arrow dragged far down and far up,
        the diameter arrow dragged in through the centre, the centre dot dragged off the part.
Path 5, edit from the timeline three times with a person's double-click (two reference edges
        and their distances, a Cancel, a new depth), then undo / redo through the edits.
Path 6, another command's key while the dialog is open: E keeps a good hole and opens
        Extrude; F drops a hole that cannot be made and opens Fillet; Delete deletes nothing.
Path 7, Ctrl+S with the dialog open: the file never holds a half-made hole. Close, reopen,
        edit the hole from the timeline, undo the edit.
Path 8, a parameter typed in the Depth field (Fusion takes parameters and formulas in every
        value field): the hole follows when the parameter changes; a typo is explained.

Numbers by hand on a 40 x 30 x 10 box (hole_steps has the formulas).
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import timeline_input as ti
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
LEFT_TOP = V(0, 22, 10)
RIGHT_TOP = V(40, 20, 10)


def step(fn, name):
    fn.__name__ = name
    return fn


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def panel():
    return hs.hole_panel()


def msg():
    return hs.message(panel())


def near(a, c, tol=1e-6):
    return abs(a - c) <= tol * max(1.0, abs(c))


def body_shown():
    tip = h.body().Tip
    return tip is not None and tip.ViewObject.isVisible() and h.body_visible()


def hole_named(title):
    return ti.obj(title)


# -- Path 1: beginner, nothing picked ---------------------------------------------------------
def p1_h():
    s["undo"] = doc().UndoCount
    s["objects"] = len(doc().Objects)
    h.click_empty()
    h.press("h")


def p1_ok():
    p = panel()
    h.check("P1 H with nothing selected opens Hole", p is not None and dialog_open())
    hs.no_popups("H with nothing selected")
    h.task_button("OK")


def p1_refused():
    p = panel()
    h.check("P1 OK with nothing placed keeps the dialog open", p is not None and dialog_open())
    h.check("P1 the dialog says to click a face", "face" in msg().lower(), msg())
    h.check("P1 nothing was made", len(doc().Objects) == s["objects"], len(doc().Objects))
    h.shot("p1-ok-refused")
    h.click_empty()


def p1_empty_click():
    p = panel()
    h.check("P1 a click on the background places nothing", p is not None and p.target is None)
    h.press(QtCore.Qt.Key_Return)


def p1_enter():
    h.check("P1 Enter over the view with nothing placed keeps the dialog", dialog_open())
    h.press(QtCore.Qt.Key_Escape)


def p1_esc():
    h.check("P1 Esc closes the dialog", not dialog_open())
    h.check("P1 still nothing new", len(doc().Objects) == s["objects"], len(doc().Objects))
    h.check("P1 undo history unchanged", doc().UndoCount == s["undo"], doc().UndoCount)
    h.check("P1 no undo step left open", not doc().HasPendingTransaction)
    h.check("P1 the box is unchanged", hs.close(h.solid_volume(), hs.BOX), h.solid_volume())


# -- Path 2: values first, an edge before the face ----------------------------------------------
P2 = V(25, 18, 10)


def p2_h():
    h.press("h")


def p2_values_first():
    p = panel()
    if p is None:
        h.check("P2 Hole dialog open", False)
        return
    b.choose(p.hole_type, "Counterbore")
    hs.type_into(p.diameter.widget, "6")
    hs.type_into(p.depth.widget, "8")
    hs.type_into(p.cbore_diameter.widget, "11")
    hs.type_into(p.cbore_depth.widget, "3")


def p2_nothing_yet():
    p = panel()
    h.check("P2 values alone build nothing", p is not None and p.target is None)
    h.check("P2 and show no warning", "⚠" not in msg(), msg())
    h.check("P2 the box is unchanged", hs.close(h.solid_volume(), hs.BOX), h.solid_volume())
    h.fit()
    h.click_edge(FRONT_TOP)


def p2_edge_first():
    p = panel()
    h.check("P2 an edge first places nothing", p is not None and p.target is None)
    h.check("P2 the dialog says to click a face first", "face" in msg().lower(), msg())
    h.check("P2 nothing left selected", not Gui.Selection.getSelectionEx())
    h.click(P2)


def p2_expected():
    return hs.BOX - (hs.cylinder(6, 8) + hs.tip_cone(6) + hs.cylinder(11, 3) - hs.cylinder(6, 3))


def p2_face():
    p = panel()
    h.check("P2 the face places the hole", p is not None and p.target is not None, msg())
    c = hs.centre_of(p.target) if p and p.target else None
    h.check("P2 where the face was clicked", hs.vnear(c, P2, 0.5), c)
    v = h.solid_volume()
    h.check("P2 the sizes typed before are used", hs.close(v, p2_expected()), (v, p2_expected()))
    h.check("P2 no warning", "⚠" not in msg(), msg())
    h.shot("p2-values-first")
    if p:
        hs.type_into(p.pos_x.widget, "25")
        hs.type_into(p.pos_y.widget, "18")


def p2_enter():
    h.click_empty()  # the mouse over the 3D view, nothing picked
    h.press(QtCore.Qt.Key_Return)


def p2_done():
    h.check("P2 Enter over the view finishes the hole (Fusion)", not dialog_open())
    hl = hs.holes()
    h.check("P2 one hole", len(hl) == 1, hl)
    v = h.solid_volume()
    h.check("P2 kept: counterbore 11 x 3 on d6 x 8", hs.close(v, p2_expected()), v)
    h.check("P2 valid solid", h.body().Shape.isValid())
    h.check("P2 the part is shown", body_shown())
    s["v"] = v


# -- Path 3: Esc in the middle of picking; Redo survives an unchanged dialog ---------------------
P3 = V(8, 22, 10)


def p3_h():
    s["objects"] = len(doc().Objects)
    s["undo"] = doc().UndoCount
    h.press("h")


def p3_face():
    h.fit()
    h.click(P3)


def p3_edge():
    p = panel()
    h.check("P3 a preview", p is not None and p.target is not None, msg())
    h.click_edge(LEFT_TOP)


def p3_esc():
    p = panel()
    h.check("P3 the edge is a reference", p is not None and len(hs.references(p.target)) == 1)
    h.press(QtCore.Qt.Key_Escape)


def p3_after_esc():
    h.check("P3 Esc cancels the hole", not dialog_open() and len(hs.holes()) == 1)
    h.check("P3 the part is as it was", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("P3 no object left behind", len(doc().Objects) == s["objects"], len(doc().Objects))
    h.check("P3 one helper sketch (Hole 1's)", len(hs.helper_sketches()) == 1)
    h.check("P3 nothing selected", not Gui.Selection.getSelectionEx())
    h.check("P3 the part is shown", body_shown())
    h.check("P3 undo history unchanged", doc().UndoCount == s["undo"], doc().UndoCount)
    h.press("h")


def p3_fresh():
    p = panel()
    h.check("P3 the next H starts with nothing placed", p is not None and p.target is None)
    h.check("P3 and no message", p is not None and msg() == "", msg())
    h.press(QtCore.Qt.Key_Escape)


def p3_undo():
    h.check("P3 closed", not dialog_open())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p3_undone():
    h.check("P3 Ctrl+Z takes Hole 1 away", not hs.holes(), hs.holes())
    h.press("h")


def p3_empty_dialog():
    h.check("P3 Hole opens", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def p3_redo():
    h.check("P3 Esc closed it", not dialog_open())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p3_redone():
    h.check(
        "P3 Ctrl+Y still brings Hole 1 back after an unchanged dialog",
        len(hs.holes()) == 1 and hs.close(h.solid_volume(), s["v"]),
        (hs.holes(), h.solid_volume()),
    )
    h.check("P3 its sketch stays hidden", all(not hs.visible(x) for x in hs.helper_sketches()))


# -- Path 4: values while the preview runs -----------------------------------------------------
P4 = V(9, 9, 10)


def p4_h():
    h.press("h")


def p4_face():
    h.fit()
    h.click(P4)


def p4_simple():
    p = panel()
    h.check("P4 a preview", p is not None and p.target is not None, msg())
    h.check(
        "P4 the last settings are remembered (counterbore d6)",
        p is not None
        and p.hole_type.currentText() == "Counterbore"
        and near(p.diameter.value(), 6),
    )
    if p:
        b.choose(p.hole_type, "Simple")
        b.choose(p.drill_point, "Flat")
        hs.type_into(p.pos_x.widget, "9")
        hs.type_into(p.pos_y.widget, "9")


def p4_type_fast():
    p = panel()
    s["v_before"] = s["v"]
    if p:
        for text in ("3", "7", "4"):
            hs.type_into(p.diameter.widget, text)


def p4_fast_result():
    p = panel()
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(4, 8)
    h.check("P4 the last diameter typed wins (4)", hs.close(v, expect), (v, expect))
    h.check("P4 the field shows it", p is not None and near(p.diameter.value(), 4))
    if p:
        hs.type_into(p.diameter.widget, "0")


def p4_zero():
    h.check("P4 diameter 0 is explained", "⚠" in msg(), msg())
    h.shot("p4-zero")
    h.task_button("OK")


def p4_zero_ok():
    h.check("P4 OK waits while the diameter is 0", dialog_open() and panel() is not None)
    p = panel()
    if p:
        hs.type_into(p.diameter.widget, "-3")


def p4_negative():
    h.check("P4 a negative diameter is explained", "⚠" in msg(), msg())
    p = panel()
    if p:
        hs.type_into(p.diameter.widget, "4")


def p4_back():
    h.check("P4 a good diameter clears the warning", "⚠" not in msg(), msg())
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(4, 8)
    h.check("P4 preview d4 x 8 again", hs.close(v, expect), (v, expect))


def p4_drag_down():
    p = panel()
    arrow = p.draggers.get("depth") if p else None
    if arrow is None:
        h.check("P4 depth arrow to drag", False)
        return
    hs.drag_arrow(p.depth_origin, p.depth_direction, arrow.distance(), 25.0, arrow=arrow)


def p4_dragged_down():
    p = panel()
    depth = p.depth.value() if p else 0
    h.check("P4 dragged far down: deeper than the part", depth > 12, depth)
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(4, 10)
    h.check("P4 the hole goes through the box", hs.close(v, expect), (v, expect))
    h.check("P4 no warning", "⚠" not in msg(), msg())
    h.check("P4 valid solid", h.body().Shape.isValid())


def p4_drag_up():
    p = panel()
    arrow = p.draggers.get("depth") if p else None
    if arrow is None:
        h.check("P4 depth arrow to drag again", False)
        return
    hs.drag_arrow(p.depth_origin, p.depth_direction, arrow.distance(), -60.0, arrow=arrow)


def p4_dragged_up():
    p = panel()
    depth = p.depth.value() if p else -1
    h.check("P4 dragged far up: the depth stops above 0", 0 < depth < 1, depth)
    h.check("P4 no warning", "⚠" not in msg(), msg())
    h.check("P4 no Report-view error", not b.report_has_kernel_errors())
    if p:
        hs.type_into(p.depth.widget, "6")


def p4_drag_diameter_in():
    p = panel()
    arrow = p.draggers.get("diameter") if p else None
    if arrow is None:
        h.check("P4 diameter arrow to drag", False)
        return
    s["d_before"] = p.diameter.value()
    hs.drag_arrow(p.diameter_origin, p.diameter_direction, arrow.distance(), -8.0, arrow=arrow)


def p4_dragged_in():
    p = panel()
    d = p.diameter.value() if p else 0
    h.check(
        "P4 dragged in through the centre: the hole gets as small as it goes, not wide again",
        0 < d < s.get("d_before", 0),
        (s.get("d_before"), d),
    )
    h.check("P4 no warning", "⚠" not in msg(), msg())
    if p:
        hs.type_into(p.diameter.widget, "4")


def p4_drag_dot_off():
    p = panel()
    dot = p.draggers.get("centre") if p else None
    if dot is None:
        h.check("P4 centre dot to drag", False)
        return
    start = dot.point()
    h.drag(h.screen_point(start), h.screen_point(start + V(-30, 0, 0)))


def p4_off_part():
    p = panel()
    c = hs.centre_of(p.target) if p and p.target else None
    h.check("P4 the dot moved off the part", c is not None and c.x < -5, c)
    h.check("P4 a hole that misses the part is explained", "⚠" in msg(), msg())
    h.shot("p4-off-part")
    h.task_button("OK")


def p4_off_ok():
    h.check("P4 OK waits while the hole misses the part", dialog_open() and panel() is not None)
    p = panel()
    if p:
        hs.type_into(p.pos_x.widget, "9")
        hs.type_into(p.pos_y.widget, "9")


def p4_back_on():
    h.check("P4 back on the part: no warning", "⚠" not in msg(), msg())
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(4, 6)
    h.check("P4 preview d4 x 6 flat at (9, 9)", hs.close(v, expect), (v, expect))
    h.task_button("OK")


def p4_done():
    h.check("P4 OK closed the dialog", not dialog_open())
    h.check("P4 two holes", len(hs.holes()) == 2, hs.holes())
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(4, 6)
    h.check("P4 kept d4 x 6", hs.close(v, expect), (v, expect))
    h.check("P4 the part is shown", body_shown())
    s["v"] = v
    s["v_before_p5"] = v


# -- Path 5: edits from the timeline with a person's double-click -------------------------------
def p5_edit():
    s["undo_p5"] = doc().UndoCount
    b.timeline_double_click("Hole 2", click_first=True)


def p5_open():
    p = panel()
    h.check("P5 double-click opens Hole 2", p is not None and p.editing)
    if p is None:
        return
    h.check("P5 depth 6 shown", near(p.depth.value(), 6), p.depth.value())
    h.check("P5 flat drill point shown", p.drill_point.currentText() == "Flat")
    h.check("P5 nothing left selected", not Gui.Selection.getSelectionEx())
    h.fit()
    h.click_edge(FRONT_TOP)


def p5_ref1():
    p = panel()
    refs = hs.references(p.target) if p else []
    h.check("P5 the front edge is a reference", len(refs) == 1, (refs, msg()))
    h.click_edge(LEFT_TOP)


def p5_ref2():
    p = panel()
    refs = hs.references(p.target) if p else []
    h.check("P5 the left edge is the second reference", len(refs) == 2, (refs, msg()))
    if p and len(refs) == 2:
        hs.type_into(p.ref_fields[0].widget, "5")
        hs.type_into(p.ref_fields[1].widget, "6")


def p5_moved():
    p = panel()
    c = hs.centre_of(p.target) if p else None
    h.check("P5 the distances put the hole at (6, 5)", hs.vnear(c, V(6, 5, 10), 1e-6), c)
    h.task_button("OK")


def p5_ok():
    h.check("P5 OK closed it", not dialog_open())
    hole2 = hole_named("Hole 2")
    c = hs.centre_of(hole2) if hole2 else None
    h.check("P5 Hole 2 now at (6, 5)", hs.vnear(c, V(6, 5, 10), 1e-6), c)
    h.check("P5 same volume", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    b.timeline_double_click("Hole 2", click_first=True)


def p5_second_edit():
    p = panel()
    h.check("P5 second edit opens", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "P5 the two references are shown",
        p.ref_fields[0].widget.isVisible() and p.ref_fields[1].widget.isVisible(),
    )
    h.check(
        "P5 with their distances",
        near(p.ref_fields[0].value(), 5) and near(p.ref_fields[1].value(), 6),
        (p.ref_fields[0].value(), p.ref_fields[1].value()),
    )
    b.choose(p.hole_type, "Countersink")
    hs.type_into(p.csink_diameter.widget, "8")


def p5_cancel():
    v = h.solid_volume()
    h.check("P5 the countersink is previewed", not hs.close(v, s["v"]), v)
    h.task_button("Cancel")


def p5_cancelled():
    h.check("P5 Cancel closed it", not dialog_open())
    h.check("P5 Cancel kept the hole as it was", hs.close(h.solid_volume(), s["v"]))
    hole2 = hole_named("Hole 2")
    h.check("P5 still a simple hole", hole2 is not None and hole2.HoleCutType == "None")
    b.timeline_double_click("Hole 2", click_first=True)


def p5_third_edit():
    p = panel()
    h.check("P5 third edit opens", p is not None and p.editing)
    if p:
        hs.type_into(p.depth.widget, "9")


def p5_third_ok():
    h.task_button("OK")


def p5_deeper():
    v = h.solid_volume()
    expect = s["v"] + hs.cylinder(4, 6) - hs.cylinder(4, 9)
    h.check("P5 Hole 2 is 9 deep", hs.close(v, expect), (v, expect))
    s["v_p5"] = v
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p5_undo1():
    hole2 = hole_named("Hole 2")
    h.check("P5 Ctrl+Z: depth 6 again", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    c = hs.centre_of(hole2) if hole2 else None
    h.check("P5 still at (6, 5)", hs.vnear(c, V(6, 5, 10), 1e-6), c)
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p5_undo2():
    hole2 = hole_named("Hole 2")
    c = hs.centre_of(hole2) if hole2 else None
    h.check("P5 Ctrl+Z again: back at (9, 9)", hs.vnear(c, V(9, 9, 10), 1e-6), c)
    h.check("P5 and no references", not hs.references(hole2), hs.references(hole2))
    h.check("P5 helper sketch hidden", all(not hs.visible(x) for x in hs.helper_sketches()))
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p5_redo1():
    hole2 = hole_named("Hole 2")
    c = hs.centre_of(hole2) if hole2 else None
    h.check("P5 Ctrl+Y: at (6, 5) again", hs.vnear(c, V(6, 5, 10), 1e-6), c)
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p5_redo2():
    h.check("P5 Ctrl+Y: 9 deep again", hs.close(h.solid_volume(), s["v_p5"]), h.solid_volume())
    h.check("P5 valid solid", h.body().Shape.isValid())
    h.check("P5 the part is shown", body_shown())
    s["v"] = s["v_p5"]
    h.shot("p5-end")


# -- Path 6: another command's key while the dialog is open --------------------------------------
P6 = V(34, 24, 10)


def p6_h():
    h.press("h")


def p6_face():
    h.fit()
    h.click(P6)


def p6_e():
    p = panel()
    h.check("P6 a preview", p is not None and p.target is not None, msg())
    if p:
        hs.type_into(p.pos_x.widget, "34")
        hs.type_into(p.pos_y.widget, "24")
        hs.type_into(p.depth.widget, "5")
        s["d6"] = p.diameter.value()
    h.press("e")


def p6_extrude_open():
    from sciforge import taskui

    current = taskui.current()
    h.check("P6 E opened Extrude", current is not None and current.title == "Extrude")
    h.check("P6 the hole was kept", len(hs.holes()) == 3, hs.holes())
    expect = s["v"] - hs.cylinder(s.get("d6", 0), 5)
    h.check("P6 with its sizes", hs.close(h.solid_volume(), expect), (h.solid_volume(), expect))
    h.press(QtCore.Qt.Key_Escape)


def p6_h2():
    h.check("P6 Esc closed Extrude", not dialog_open())
    s["v"] = h.solid_volume()
    h.press("h")


def p6_face2():
    h.fit()
    h.click(V(33, 6, 10))


def p6_bad():
    p = panel()
    h.check("P6 a second preview", p is not None and p.target is not None, msg())
    if p:
        b.choose(p.hole_type, "Counterbore")
        hs.type_into(p.cbore_diameter.widget, "2")


def p6_f():
    h.check("P6 the bad counterbore is explained", "⚠" in msg(), msg())
    h.press("f")


def p6_fillet_open():
    from sciforge import taskui

    current = taskui.current()
    h.check("P6 F opened Fillet", current is not None and current.title == "Fillet", current)
    h.check("P6 the bad hole was dropped", len(hs.holes()) == 3, hs.holes())
    h.check("P6 the part is as it was", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("P6 the part is shown", body_shown())
    h.press(QtCore.Qt.Key_Escape)


def p6_h3():
    h.check("P6 Esc closed Fillet", not dialog_open())
    h.press("h")


def p6_face3():
    h.fit()
    h.click(V(15, 6, 10))


def p6_delete():
    p = panel()
    h.check("P6 a third preview", p is not None and p.target is not None, msg())
    s["objects"] = len(doc().Objects)
    h.press(QtCore.Qt.Key_Delete)


def p6_deleted_nothing():
    h.check("P6 Delete keeps the dialog", panel() is not None and dialog_open())
    h.check("P6 Delete deleted nothing", len(doc().Objects) == s["objects"], len(doc().Objects))
    hs.no_popups("Delete in the Hole dialog")
    h.press(QtCore.Qt.Key_Escape)


def p6_done():
    h.check("P6 Esc closed it", not dialog_open())
    h.check("P6 three holes", len(hs.holes()) == 3, hs.holes())
    h.check("P6 the part is as it was", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("P6 valid solid", h.body().Shape.isValid())


# -- Path 7: Ctrl+S with the dialog open; save, close, reopen, edit -----------------------------
P7 = V(12, 25, 10)


def p7_save_first():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-hole-qa-"), "hole_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("P7 saved", os.path.isfile(path), path)
    h.press("h")


def p7_face():
    h.fit()
    h.click(P7)


def p7_ctrl_s():
    p = panel()
    h.check("P7 a preview", p is not None and p.target is not None, msg())
    if p:
        hs.type_into(p.pos_x.widget, "12")
        hs.type_into(p.pos_y.widget, "25")
        hs.type_into(p.depth.widget, "4")
        s["d7"] = p.diameter.value()
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p7_describe():
    """Fusion's Save asks for a version description on a saved design; Enter skips it."""
    h.check("P7 the hole dialog finished first", not dialog_open())
    h.check(
        "P7 then the Save dialog asks for a version description", vi.version_dialog() is not None
    )
    vi.accept_save()


def p7_saved():
    h.check("P7 Ctrl+S finished the dialog first", not dialog_open())
    h.check("P7 the hole was kept", len(hs.holes()) == 4, hs.holes())
    expect = s["v"] - hs.cylinder(s.get("d7", 0), 4)
    h.check("P7 with its sizes", hs.close(h.solid_volume(), expect), (h.solid_volume(), expect))
    h.check("P7 the design is saved (nothing unsaved)", not doc().isTouched() and not b.modified())
    s["v"] = h.solid_volume()
    s["labels"] = sorted(x.Label for x in hs.helper_sketches())
    App.closeDocument(doc().Name)


def p7_open():
    App.openDocument(s["path"])
    h.fit()


def p7_reopened():
    h.check("P7 reopened: same part", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("P7 four holes in the file", len(hs.holes()) == 4, hs.holes())
    h.check("P7 all of them computed", all("Invalid" not in x.State for x in hs.holes()))
    labels = sorted(x.Label for x in hs.helper_sketches())
    h.check("P7 the hole sketches kept their names", labels == s["labels"], labels)
    h.check("P7 and stay hidden", all(not hs.visible(x) for x in hs.helper_sketches()))
    titles = hs.timeline_titles()
    h.check(
        "P7 the timeline lists the holes, not their sketches",
        all("Hole %d" % i in titles for i in range(1, 5))
        and not any(t.startswith("Hole") and "Sketch" in t for t in titles),
        titles,
    )
    b.timeline_double_click("Hole 1", click_first=True)


def p7_editing():
    p = panel()
    h.check("P7 editing Hole 1 after reopening", p is not None and p.editing)
    if p is None:
        return
    h.check("P7 its counterbore is shown", p.hole_type.currentText() == "Counterbore")
    h.check("P7 its depth 8 is shown", near(p.depth.value(), 8), p.depth.value())
    h.check(
        "P7 its face is shown",
        p.fields["face"].button.text().startswith("Face"),
        p.fields["face"].button.text(),
    )
    hs.type_into(p.depth.widget, "7")


def p7_edit_ok():
    h.task_button("OK")


def p7_edited():
    v = h.solid_volume()
    expect = s["v"] + hs.cylinder(6, 1)
    h.check("P7 the edit made Hole 1 shallower", hs.close(v, expect), (v, expect))
    h.check("P7 valid solid", h.body().Shape.isValid())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p7_undone():
    h.check("P7 Ctrl+Z undoes the edit", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("P7 the part is shown", body_shown())
    h.shot("p7-end")


# -- Path 8: a parameter in the Depth field ------------------------------------------------------
P8 = V(30, 12, 10)


def p8_parameter():
    from sciforge import parameters

    # Change Parameters (its own dialog) made this user parameter:
    parameters.add_user(doc(), "holedepth", "mm", "7")
    doc().recompute()
    h.press("h")


def p8_face():
    h.fit()
    h.click(P8)


def p8_type():
    p = panel()
    h.check("P8 a preview", p is not None and p.target is not None, msg())
    if p:
        b.choose(p.hole_type, "Simple")
        b.choose(p.drill_point, "Flat")
        hs.type_into(p.pos_x.widget, "30")
        hs.type_into(p.pos_y.widget, "12")
        hs.type_into(p.diameter.widget, "3")
        ui.type_into(p.depth.widget, "holedepth")


def p8_typed():
    p = panel()
    h.check(
        "P8 'holedepth' is 7 mm", p is not None and near(p.depth.value(), 7), p and p.depth.value()
    )
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(3, 7)
    h.check("P8 the preview is 7 deep", hs.close(v, expect), (v, expect))
    h.check("P8 no warning", "⚠" not in msg(), msg())
    h.task_button("OK")


def p8_change():
    from sciforge import parameters

    h.check("P8 kept", not dialog_open() and len(hs.holes()) == 5, hs.holes())
    parameters.set_user(doc(), "holedepth", "9")  # in Change Parameters
    doc().recompute()


def p8_followed():
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(3, 9)
    h.check("P8 the hole follows holedepth = 9", hs.close(v, expect), (v, expect))
    b.timeline_double_click("Hole 5", click_first=True)


def p8_editing():
    p = panel()
    h.check("P8 editing Hole 5", p is not None and p.editing)
    if p is None:
        return
    h.check("P8 its depth shows 9", near(p.depth.value(), 9), p.depth.value())
    ui.type_into(p.depth.widget, "holedpth")


def p8_typo():
    h.check("P8 a typo is explained", "⚠" in msg(), msg())
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(3, 9)
    h.check("P8 the hole stays 9 deep", hs.close(v, expect), (v, expect))
    p = panel()
    if p:
        b.press_enter(p.depth.widget)


def p8_enter_after_typo():
    h.check("P8 Enter right after the typo keeps the dialog", dialog_open())
    p = panel()
    if p:
        hs.type_into(p.depth.widget, "5")


def p8_plain():
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(3, 5)
    h.check("P8 a plain number replaces the parameter", hs.close(v, expect), (v, expect))
    h.task_button("OK")


def p8_done():
    from sciforge import parameters

    h.check("P8 closed", not dialog_open())
    parameters.set_user(doc(), "holedepth", "2")
    doc().recompute()
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(3, 5)
    h.check("P8 no longer follows the parameter", hs.close(v, expect), (v, expect))
    h.check("P8 valid solid", h.body().Shape.isValid())
    h.check("P8 no kernel errors in the Report view", not b.report_has_kernel_errors())
    h.shot("p8-end")


h.run(
    "hole_qa",
    ti.watched(
        b.box_steps("HoleQA")
        + [
            p1_h,
            p1_ok,
            p1_refused,
            p1_empty_click,
            p1_enter,
            p1_esc,
            p2_h,
            p2_values_first,
            p2_nothing_yet,
            p2_edge_first,
            p2_face,
            p2_enter,
            p2_done,
            p3_h,
            p3_face,
            p3_edge,
            p3_esc,
            p3_after_esc,
            p3_fresh,
            p3_undo,
            p3_undone,
            p3_empty_dialog,
            p3_redo,
            p3_redone,
            p4_h,
            p4_face,
            p4_simple,
            p4_type_fast,
            p4_fast_result,
            p4_zero,
            p4_zero_ok,
            p4_negative,
            p4_back,
            p4_drag_down,
            p4_dragged_down,
            p4_drag_up,
            p4_dragged_up,
            p4_drag_diameter_in,
            p4_dragged_in,
            p4_drag_dot_off,
            p4_off_part,
            p4_off_ok,
            p4_back_on,
            p4_done,
            p5_edit,
            p5_open,
            p5_ref1,
            p5_ref2,
            p5_moved,
            p5_ok,
            p5_second_edit,
            p5_cancel,
            p5_cancelled,
            p5_third_edit,
            p5_third_ok,
            p5_deeper,
            p5_undo1,
            p5_undo2,
            p5_redo1,
            p5_redo2,
            p6_h,
            p6_face,
            p6_e,
            p6_extrude_open,
            p6_h2,
            p6_face2,
            p6_bad,
            p6_f,
            p6_fillet_open,
            p6_h3,
            p6_face3,
            p6_delete,
            p6_deleted_nothing,
            p6_done,
            p7_save_first,
            p7_face,
            p7_ctrl_s,
            p7_describe,
            p7_saved,
            p7_open,
            p7_reopened,
            p7_editing,
            p7_edit_ok,
            p7_edited,
            p7_undone,
            p8_parameter,
            p8_face,
            p8_type,
            p8_typed,
            p8_change,
            p8_followed,
            p8_editing,
            p8_typo,
            p8_enter_after_typo,
            p8_plain,
            p8_done,
        ]
    ),
)
