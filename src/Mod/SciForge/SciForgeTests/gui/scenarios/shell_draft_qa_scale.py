# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scale the way Fusion users use it, trying to break it (QA, only real input).
A 40 x 30 x 10 box made with Create Sketch / E.

Path 1, a beginner: Scale, OK with nothing picked (the dialog says to pick the body and
        stays), Enter (same); a click on the part picks the body; 2 typed; Esc: nothing
        made, no undo step added.
Path 2, shrinking by dragging the arrow back into the part, then grabbing the same arrow
        again where it now is (inside the see-through part) and dragging it out: Fusion's
        handles always take the click. The arrow dragged through the scale point stops at
        the smallest factor. 1.5 typed, OK.
Path 3, Create Sketch on the scaled top, a square, E 5 mm (a boss); Scale edited from the
        timeline to 2: the boss stays on the top. Edited again to Non Uniform 2 / 1 / 1:
        the boss still on the top. Ctrl+Z twice, Ctrl+Y twice.
Path 4, E pressed while a second Scale previews: the scale is kept, Extrude opens; Esc.
Path 5, a new design: Scale 0.5 about a corner of the part; the box's Extrude edited from
        10 to 12 mm high: the scale still uses that corner (no warning in the Report view).
Path 6, parameters: X Scale = k, Z Scale = k / 2 (Non Uniform); Change Parameters lists
        the scale's factors; k changed there: the part follows.
Path 7, save, close, reopen; the scale edited back to Uniform 1.5; Ctrl+Z.

Volumes by hand: a scale by (sx, sy, sz) multiplies the volume by sx sy sz; a boss
w x w x h on top adds w^2 h.
"""
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}
TOP = V(20, 15, 10)
BOSS = 10.0  # the boss is BOSS x BOSS, 5 high


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def msg(p):
    return p.message.text() if p is not None else ""


def bbox(expect, tol=1e-6):
    box = h.body().Shape.BoundBox
    got = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
    return all(abs(a - b_) < tol for a, b_ in zip(got, expect)), [round(x, 4) for x in got]


def part_ok(where):
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("%s: nothing in error" % where, not bad, bad)
    h.check("%s: valid solid" % where, h.body().Shape.isValid())
    tip = h.body().Tip
    h.check("%s: the part is shown" % where, tip is not None and tip.ViewObject.isVisible())
    h.check("%s: nothing left see-through" % where, not b.see_through(), b.see_through())


def made():
    s["undo"] = list(doc().UndoNames)


# -- Path 1: a beginner ----------------------------------------------------------------------
def p1_scale():
    Gui.Selection.clearSelection()
    h.ribbon("Scale")


def p1_ok():
    h.check("P1 the dialog waits for the body", sd.scale_panel() is not None)
    h.task_button("OK")


def p1_refused():
    p = sd.scale_panel()
    h.check("P1 OK with nothing picked keeps the dialog", p is not None and dialog_open())
    h.check("P1 and says to pick the body", "body" in msg(p), msg(p))
    sd.no_popups("OK with nothing picked")
    h.press(QtCore.Qt.Key_Return)


def p1_enter():
    h.check("P1 Enter: still open", sd.scale_panel() is not None and dialog_open())
    h.fit()
    h.click(TOP)


def p1_body():
    p = sd.scale_panel()
    h.check("P1 a click on the part picks the body", p is not None and p.base is not None)
    if p:
        ui.type_into(p.factor.widget, "2")


def p1_esc():
    v = h.solid_volume()
    h.check("P1 twice as big previewed (x8)", sd.close(v, 8 * sd.BOX), v)
    h.press(QtCore.Qt.Key_Escape)


def p1_closed():
    h.check("P1 Esc closed it", not dialog_open())
    h.check("P1 nothing made", not sd.scales() and sd.close(h.solid_volume(), sd.BOX))
    h.check("P1 no undo step added", list(doc().UndoNames) == s["undo"], doc().UndoNames)
    part_ok("P1")


# -- Path 2: shrink by dragging, grab the arrow again ------------------------------------------
def p2_scale():
    h.ribbon("Scale")


def p2_body():
    h.fit()
    h.click(TOP)


def p2_shrink():
    p = sd.scale_panel()
    if not h.check("P2 one arrow", p is not None and len(p.arrows) == 1):
        return
    h.fit()
    spot = p.arrows[0][1]
    start, end = sd.arrow_screen(p, along=-0.6 * spot["length"])
    h.drag(start, end)


def p2_shrunk():
    p = sd.scale_panel()
    f = p.factor.value() if p else 1.0
    h.check("P2 dragged back: smaller", 0.2 < f < 0.7, f)
    v = h.solid_volume()
    h.check("P2 the preview is that size", sd.close(v, sd.BOX * f**3), (v, f))
    s["f2"] = f
    h.shot("p2-shrunk")
    if p is None or not p.arrows:
        return
    h.fit()
    start, end = sd.arrow_screen(p, along=0.5 * p.arrows[0][1]["length"])
    h.drag(start, end)


def p2_grabbed_again():
    p = sd.scale_panel()
    f = p.factor.value() if p else 0
    h.check(
        "P2 the arrow inside the see-through part is grabbed again", f > s["f2"] + 0.3, (s["f2"], f)
    )
    h.check("P2 the point is still the origin", p is not None and p.point_ref is None)
    h.check("P2 no corner picked by those presses", p is not None and not sd.selected())
    if p is None or not p.arrows:
        return
    h.fit()
    start, end = sd.arrow_screen(p, along=-3.0 * p.arrows[0][1]["length"])
    h.drag(start, end)


def p2_through():
    p = sd.scale_panel()
    f = p.factor.value() if p else 0
    h.check("P2 dragged through the point: the smallest factor", 0 < f <= 0.01, f)
    h.check("P2 no message", msg(p) == "", msg(p))
    if p:
        ui.type_into(p.factor.widget, "1.5")


def p2_ok():
    h.check("P2 1.5", sd.close(h.solid_volume(), 3.375 * sd.BOX), h.solid_volume())
    h.task_button("OK")


def p2_done():
    h.check("P2 Scale 1 made", "Scale 1" in sd.timeline_titles(), sd.timeline_titles())
    ok, got = bbox([0, 0, 0, 60, 45, 15])
    h.check("P2 60 x 45 x 15", ok, got)
    part_ok("P2")


# -- Path 3: a boss on the scaled top, the scale edited twice --------------------------------
def p3_sketch():
    Gui.Selection.clearSelection()
    h.ribbon("Create Sketch")


def p3_top():
    h.fit()
    h.click(V(30, 22.5, 15))


def p3_draw():
    sk = h.in_sketch()
    if not h.check("P3 a sketch on the scaled top", sk is not None):
        return
    z = sk.getGlobalPlacement().Base.z
    h.check("P3 at z = 15", abs(z - 15) < 1e-6, z)
    x0, y0 = h.to_sketch(sk, V(10, 10, 15))
    x1, y1 = h.to_sketch(sk, V(10 + BOSS, 10 + BOSS, 15))
    h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def p3_finish():
    h.ribbon("Finish Sketch")


def p3_e():
    h.fit()
    h.press("e")


def p3_distance():
    p = b.active_panel()
    if p is not None and getattr(p, "distance", None) is not None:
        ui.type_into(p.distance.widget, "5")


def p3_extrude_ok():
    h.task_button("OK")


def p3_boss():
    v = h.solid_volume()
    expect = 3.375 * sd.BOX + BOSS * BOSS * 5
    h.check("P3 the boss on top", sd.close(v, expect), (v, expect))
    part_ok("P3 boss")
    s["undo3"] = len(doc().UndoNames)
    h.fit()
    b.timeline_double_click("Scale 1", click_first=True)


def p3_edit():
    p = sd.scale_panel()
    h.check("P3 editing Scale 1", p is not None and p.editing)
    h.check("P3 1.5 shown", p is not None and abs(p.factor.value() - 1.5) < 1e-9)
    if p:
        ui.type_into(p.factor.widget, "2")


def p3_ok():
    h.task_button("OK")


def p3_two():
    v = h.solid_volume()
    expect = 8 * sd.BOX + BOSS * BOSS * 5
    h.check("P3 twice as big, the boss on the new top", sd.close(v, expect), (v, expect))
    ok, got = bbox([0, 0, 0, 80, 60, 25])
    h.check("P3 the boss ends at z = 25", ok, got)
    part_ok("P3 scale 2")
    b.timeline_double_click("Scale 1", click_first=True)


def p3_edit2():
    p = sd.scale_panel()
    if p:
        ui.choose(p.scale_type, "Non Uniform")


def p3_axes():
    p = sd.scale_panel()
    if p:
        ui.type_into(p.axis_fields["x"].widget, "2")
        ui.type_into(p.axis_fields["y"].widget, "1")
        ui.type_into(p.axis_fields["z"].widget, "1")


def p3_ok2():
    v = h.solid_volume()
    expect = 2 * sd.BOX  # edited with the timeline rolled to the scale: the boss waits
    h.check("P3 Non Uniform previews, the boss waits", sd.close(v, expect, 1e-5), (v, expect))
    p = sd.scale_panel()
    h.check("P3 no message", msg(p) == "", msg(p))
    h.task_button("OK")


def p3_non_uniform():
    v = h.solid_volume()
    expect = 2 * sd.BOX + BOSS * BOSS * 5
    h.check("P3 80 x 30 x 10 with the boss on top", sd.close(v, expect, 1e-5), (v, expect))
    ok, got = bbox([0, 0, 0, 80, 30, 15], 1e-5)
    h.check("P3 the boss ends at z = 15", ok, got)
    part_ok("P3 non uniform")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p3_undo1():
    h.check("P3 Ctrl+Z: 2", sd.close(h.solid_volume(), 8 * sd.BOX + 500), h.solid_volume())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p3_undo2():
    h.check("P3 Ctrl+Z: 1.5", sd.close(h.solid_volume(), 3.375 * sd.BOX + 500), h.solid_volume())
    part_ok("P3 undo")
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p3_redo1():
    h.check("P3 Ctrl+Y: 2", sd.close(h.solid_volume(), 8 * sd.BOX + 500), h.solid_volume())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p3_redo2():
    v = h.solid_volume()
    h.check("P3 Ctrl+Y: Non Uniform", sd.close(v, 2 * sd.BOX + 500, 1e-5), v)
    part_ok("P3 redo")
    s["v3"] = v


# -- Path 4: E while a second Scale previews ------------------------------------------------------
def p4_scale():
    Gui.Selection.clearSelection()
    h.ribbon("Scale")


def p4_body():
    h.fit()
    h.click(V(80, 15, 5))


def p4_type():
    p = sd.scale_panel()
    if p:
        ui.type_into(p.factor.widget, "0.5")


def p4_e():
    v = h.solid_volume()
    h.check("P4 half size previewed", sd.close(v, s["v3"] / 8, 1e-5), v)
    h.press("e")


def p4_after():
    from sciforge import taskui

    h.check("P4 E kept the scale", len(sd.scales()) == 2 and sd.scale_panel() is None)
    h.check("P4 as previewed", sd.close(h.solid_volume(), s["v3"] / 8, 1e-5))
    current = taskui.current()
    h.check("P4 Extrude is open", current is not None and current.title == "Extrude")
    sd.no_popups("E with Scale open")
    h.press(QtCore.Qt.Key_Escape)


def p4_closed():
    h.check("P4 closed", not dialog_open())
    part_ok("P4")


# -- Path 5: about a corner, the box made taller ---------------------------------------------
CORNER = V(40, 30, 10)


def p5_scale():
    h.check("P5 a new box", sd.close(h.solid_volume(), sd.BOX), h.solid_volume())
    Gui.Selection.clearSelection()
    h.ribbon("Scale")


def p5_body():
    h.fit()
    h.click(TOP)


def p5_corner():
    h.fit()
    sd.click_vertex(CORNER)


def p5_type():
    p = sd.scale_panel()
    h.check(
        "P5 the corner is the point",
        p is not None and p.point_ref is not None and p.point_ref[1].startswith("Vertex"),
        p and p.point_ref,
    )
    if p:
        ui.type_into(p.factor.widget, "0.5")


def p5_ok():
    h.task_button("OK")


def p5_made():
    ok, got = bbox([20, 15, 5, 40, 30, 10])
    h.check("P5 shrunk toward the corner", ok, got)
    h.fit()
    b.timeline_double_click("Extrude 1", click_first=True)


def p5_extrude():
    p = b.active_panel()
    h.check("P5 the box's Extrude opens", p is not None and p.title == "Extrude")
    if p is not None and getattr(p, "distance", None) is not None:
        ui.type_into(p.distance.widget, "12")


def p5_extrude_ok():
    h.task_button("OK")


def p5_followed():
    ok, got = bbox([20, 15, 6, 40, 30, 12])
    h.check("P5 the scale still uses the (moved) corner", ok, got)
    h.check("P5 1800", sd.close(h.solid_volume(), 1800.0), h.solid_volume())
    part_ok("P5")
    h.check("P5 nothing in the Report view", not sd.report_errors(), sd.report_errors())


# -- Path 6: parameters ---------------------------------------------------------------------
def p6_parameter():
    from sciforge import parameters

    parameters.add_user(doc(), "k", "", "2")  # as in Change Parameters
    doc().recompute()
    b.timeline_double_click("Scale 1", click_first=True)


def p6_non_uniform():
    p = sd.scale_panel()
    h.check("P6 editing", p is not None and p.editing)
    if p:
        ui.choose(p.scale_type, "Non Uniform")


def p6_formulas():
    p = sd.scale_panel()
    if p:
        ui.type_into(p.axis_fields["x"].widget, "k")
        ui.type_into(p.axis_fields["y"].widget, "1")
        ui.type_into(p.axis_fields["z"].widget, "k / 2")


def p6_preview():
    p = sd.scale_panel()
    h.check(
        "P6 the formulas are shown",
        p is not None and "X Scale = k" in p.formula_label.text(),
        p and p.formula_label.text(),
    )
    v = h.solid_volume()
    h.check("P6 2 x 1 x 1 about the corner", sd.close(v, 14400 * 2, 1e-5), v)
    h.task_button("OK")


def p6_parameters_dialog():
    from sciforge import parameters_ui

    Gui.runCommand("SciForge_ChangeParameters")
    dialog = parameters_ui.ParametersDialog.last
    h.check("P6 Change Parameters opens", dialog is not None and dialog.isVisible())
    if dialog is None:
        return
    rows = [dialog.model.topLevelItem(i) for i in range(dialog.model.topLevelItemCount())]
    scale_rows = [r for r in rows if r.text(0).startswith("Scale")]
    labels = []
    for r in scale_rows:
        labels += [r.child(i).text(1) for i in range(r.childCount())]
    h.check(
        "P6 the scale's factors are listed (X, Y, Z: it is Non Uniform)",
        labels == ["X Scale", "Y Scale", "Z Scale"],
        labels,
    )
    users = [dialog.user.item(i, 0).text() for i in range(dialog.user.rowCount())]
    h.check("P6 k is listed", "k" in users, users)
    row = users.index("k") if "k" in users else -1
    if row >= 0:
        dialog.user.item(row, 2).setText("3")  # typed into the Value column
    h.shot("p6-parameters")
    dialog.accept()


def p6_followed():
    v = h.solid_volume()
    h.check("P6 k = 3: 3 x 1 x 1.5", sd.close(v, 14400 * 4.5, 1e-5), v)
    part_ok("P6")
    s["v6"] = v


# -- Path 7: save, close, reopen, edit -----------------------------------------------------------
def p7_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-scale-qa-"), "scale_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("P7 saved", os.path.isfile(path), path)
    App.closeDocument(doc().Name)


def p7_open():
    App.openDocument(s["path"])
    h.fit()


def p7_reopened():
    h.check("P7 same part", sd.close(h.solid_volume(), s["v6"], 1e-5), h.solid_volume())
    part_ok("P7 reopened")
    b.timeline_double_click("Scale 1", click_first=True)


def p7_edit():
    p = sd.scale_panel()
    h.check("P7 opens after reopening", p is not None and p.editing)
    h.check("P7 Non Uniform shown", p is not None and p.scale_type.currentText() == "Non Uniform")
    h.check("P7 X = k kept", p is not None and "X Scale = k" in p.formula_label.text())
    h.check("P7 the corner kept", p is not None and p.point_ref is not None)
    if p:
        ui.choose(p.scale_type, "Uniform")
        ui.type_into(p.factor.widget, "1.5")


def p7_ok():
    h.task_button("OK")


def p7_uniform():
    v = h.solid_volume()
    h.check("P7 Uniform 1.5 about the corner", sd.close(v, 14400 * 3.375), v)
    ok, got = bbox([-20, -15, -6, 40, 30, 12])
    h.check("P7 grown away from the corner", ok, got)
    part_ok("P7")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p7_undo():
    h.check("P7 Ctrl+Z", sd.close(h.solid_volume(), s["v6"], 1e-5), h.solid_volume())
    part_ok("P7 undo")
    h.check("P7 nothing in the Report view", not sd.report_errors(), sd.report_errors())


h.run(
    "shell_draft_qa_scale",
    tl.watched(
        sd.box_steps("ScaleQA")
        + [
            made,
            p1_scale,
            p1_ok,
            p1_refused,
            p1_enter,
            p1_body,
            p1_esc,
            p1_closed,
            p2_scale,
            p2_body,
            p2_shrink,
            p2_shrunk,
            p2_grabbed_again,
            p2_through,
            p2_ok,
            p2_done,
            p3_sketch,
            p3_top,
            p3_draw,
            p3_finish,
            p3_e,
            p3_distance,
            p3_extrude_ok,
            p3_boss,
            p3_edit,
            p3_ok,
            p3_two,
            p3_edit2,
            p3_axes,
            p3_ok2,
            p3_non_uniform,
            p3_undo1,
            p3_undo2,
            p3_redo1,
            p3_redo2,
            p4_scale,
            p4_body,
            p4_type,
            p4_e,
            p4_after,
            p4_closed,
        ]
        + sd.box_steps("ScaleQA2")
        + [
            p5_scale,
            p5_body,
            p5_corner,
            p5_type,
            p5_ok,
            p5_made,
            p5_extrude,
            p5_extrude_ok,
            p5_followed,
            p6_parameter,
            p6_non_uniform,
            p6_formulas,
            p6_preview,
            p6_parameters_dialog,
            p6_followed,
            p7_save,
            p7_open,
            p7_reopened,
            p7_edit,
            p7_ok,
            p7_uniform,
            p7_undo,
        ]
    ),
)
