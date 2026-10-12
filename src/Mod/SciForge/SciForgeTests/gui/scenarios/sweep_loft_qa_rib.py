# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rib the way a Fusion user really uses it, trying to break it (QA, only real input).

Sketches are drawn with the mouse and typed lengths and angles (L, a click, length Tab
angle Enter, the tool going on from the end); expected volumes come from what was drawn.

Path 1, the rib line before the part: a line on XZ from about (5, 25), 28.2843 long at
        315 degrees (across the corner the bracket will have). CREATE > Rib: the Curve box
        waits; OK says to pick the curve; click the line: the dialog says a rib needs a part
        (nothing is built); Esc.
Path 2, the bracket, then the gusset while values change: an L on XZ (legs 40, 5 thick),
        Extrude Symmetric 10. Click the rib line, CREATE > Rib: it is taken and To Next fills
        the corner (a gusset). Thickness 0 and -3 are said (OK waits), 3 works; the
        thickness arrow dragged far out and then back past its start; One Side, Flip Side
        (the other side of the sketch plane, same volume); Depth 4 (a strip); OK. Ctrl+Z,
        Ctrl+Y.
Path 3, an earlier step edited and the rib edited twice: double-click Extrude 1, 6 instead
        of 10 (the bracket gets narrower, the rib stays); double-click the rib, Symmetric,
        To Next, Thickness 4, OK; double-click it again, Thickness 9, Cancel (unchanged).
Path 4, save, close, reopen and edit: the rib comes back; double-click it, Thickness 2,
        Enter in the field (OK).

Hand-derived: the L's area is 40 * 5 + 35 * 5 = 375 times the bracket's width. The rib line
(carried on to the inner walls x = 5 and z = 5) closes the triangle between the walls; its
legs come from where the drawn line meets them. To Next = thickness * triangle. Depth d (a
45 degree line): the strip between the line and the line moved d towards the corner, inside
the walls: a trapezoid of area (L^2 - (L - d sqrt 2)^2) / 2 with L the triangle's leg.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
SQ2 = math.sqrt(2.0)
s = {}


def panel():
    return st.panel("rib")


def msg():
    return st.message("rib")


def near(a, c, tol=1e-6):
    return st.near(a, c, tol)


def vol():
    return h.solid_volume()


def xz_click(point):
    si.click(point, approach=V(1.0, 0, 0.6))


def typed_segment(length, angle):
    si.type_text(str(length), enter=False)
    si.tab()
    si.type_text(str(angle))


def triangle():
    """(leg along x = 5, leg along z = 5, area) of the corner the drawn rib line closes."""
    p, q = s["line"]
    d = q - p
    t1 = (5.0 - p.x) / d.x
    z_w = p.z + d.z * t1
    t2 = (5.0 - p.z) / d.z
    x_w = p.x + d.x * t2
    return z_w - 5.0, x_w - 5.0, 0.5 * (z_w - 5.0) * (x_w - 5.0)


def gusset(t):
    return s["bracket"] + t * triangle()[2]


def strip(t, d):
    leg = triangle()[0]
    return s["bracket"] + t * (leg * leg - (leg - d * SQ2) ** 2) / 2.0


def bracket_volume():
    box = st.bbox(h.body().Shape)
    s["width"] = box[4] - box[1]
    return 375.0 * s["width"]


# == Path 1: the rib line before the part ========================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("RibQA")
    h.fit()
    h.ribbon("Create Sketch")


def p1_xz():
    h.click(V(12, 0, 8))


def p1_line_key():
    s["sl"] = h.in_sketch()
    h.check("P1 sketch open on XZ", s["sl"] is not None)
    h.press("l")


def p1_line_start():
    xz_click(V(5, 0, 25))


def p1_line_typed():
    si.move_towards(V(15, 0, 15.3), V(0.7, 0, -0.7))
    typed_segment("28.2843", "315")


def p1_line_done():
    st.esc()
    st.esc()
    lines = si.lines(s["sl"])
    h.check("P1 one line", len(lines) == 1, s["sl"].Geometry)
    if lines:
        g = s["sl"].getGlobalPlacement()
        s["line"] = (g.multVec(lines[0][1].StartPoint), g.multVec(lines[0][1].EndPoint))
        p, q = s["line"]
        h.check(
            "P1 the line runs down at 45 degrees",
            abs((q - p).Length - 28.2843) < 1e-6 and abs((q - p).x - (p - q).z) < 1e-4,
            s["line"],
        )
    h.ribbon("Finish Sketch")


def p1_rib():
    h.fit()
    h.click_empty()
    st.menu("Rib")


def p1_open():
    p = panel()
    h.check("P1 Rib opens (there is a body)", p is not None)
    if p is None:
        return
    h.check("P1 nothing is taken", not p.refs, p.refs)
    h.task_button("OK")


def p1_ok_refused():
    h.check("P1 OK with nothing keeps the dialog", panel() is not None and st.dialog_open())
    h.check("P1 the dialog says to pick the curve", "curve" in msg().lower(), msg())
    p, q = s["line"]
    h.click_edge((p + q) * 0.5)


def p1_no_part():
    p = panel()
    h.check("P1 the line is taken", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("P1 the dialog says a rib needs a part", "part" in msg().lower(), msg())
    h.check("P1 nothing is built", not st.features("rib") and vol() == 0.0)
    h.task_button("OK")


def p1_ok_again():
    h.check("P1 OK without a part keeps the dialog", panel() is not None)
    st.esc()


def p1_esc():
    h.check("P1 Esc closes it", not st.dialog_open())
    h.check("P1 nothing is built", not st.features("rib"))
    h.check("P1 no pop-up", not h.popups(), h.popups())


# == Path 2: the bracket and the gusset ===========================================================
def p2_sketch():
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p2_xz():
    h.click(V(12, 0, 8))


def p2_line_key():
    s["sb"] = h.in_sketch()
    h.check("P2 sketch open on XZ", s["sb"] is not None and s["sb"] is not s["sl"])
    h.press("l")


def p2_origin():
    xz_click(V(0, 0, 0))


def p2_seg1():
    si.move_towards(V(15, 0, 0.3), V(1, 0, 0))
    typed_segment(40, 0)


def p2_seg2():
    si.move_towards(V(40.3, 0, 3), V(0, 0, 1))
    typed_segment(5, 90)


def p2_seg3():
    si.move_towards(V(20, 0, 5.3), V(-1, 0, 0))
    typed_segment(35, 180)


def p2_seg4():
    si.move_towards(V(5.3, 0, 20), V(0, 0, 1))
    typed_segment(35, 90)


def p2_seg5():
    si.move_towards(V(2, 0, 40.3), V(-1, 0, 0))
    typed_segment(5, 180)


def p2_close():
    xz_click(V(0, 0, 0))


def p2_finish():
    st.esc()
    st.esc()
    lines = si.lines(s["sb"])
    h.check("P2 six lines", len(lines) == 6, s["sb"].Geometry)
    try:
        from sciforge import extrude

        areas = extrude.regions(s["sb"])
        h.check(
            "P2 one closed L of area 375", len(areas) == 1 and near(areas[0][1].Area, 375.0), areas
        )
    except Exception as exc:
        h.check("P2 the L has an area", False, exc)
    h.ribbon("Finish Sketch")


def p2_extrude():
    h.fit()
    h.press("e")


def p2_symmetric():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P2 Extrude opens", p is not None and not p._closed)
    if p is not None:
        b.choose(p.direction, "Symmetric")


def p2_distance():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    if p is not None:
        ui.type_into(p.distance.widget, "10")


def p2_extrude_ok():
    h.task_button("OK")


def p2_bracket():
    box = st.bbox(h.body().Shape)
    h.check("P2 symmetric about the sketch plane", near(box[1], -box[4]), box)
    s["bracket"] = bracket_volume()
    h.check("P2 the L bracket", near(vol(), s["bracket"]), (vol(), s["bracket"]))
    h.fit()
    h.click_empty()
    p, q = s["line"]
    h.check("P2 the rib line clicked before the command", h.click_edge((p + q) * 0.5))


def p2_rib():
    st.menu("Rib")


def p2_open():
    p = panel()
    h.check("P2 Rib opens with the line taken", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("P2 To Next", p is not None and p.depth_type.currentText() == "To Next")
    h.check("P2 the gusset, 2 thick", near(vol(), gusset(2.0), 1e-6), (vol(), gusset(2.0)))
    h.check("P2 no message", msg() == "", msg())
    if p is not None:
        ui.type_into(p.thickness.widget, "0")


def p2_zero():
    h.check("P2 Thickness 0 is said", "more than 0" in msg(), msg())
    h.check("P2 the last good preview stays", near(vol(), gusset(2.0), 1e-6), vol())
    h.task_button("OK")


def p2_zero_ok():
    h.check("P2 OK with Thickness 0 keeps the dialog", panel() is not None)
    ui.type_into(panel().thickness.widget, "-3")


def p2_negative():
    h.check("P2 Thickness -3 is said", "more than 0" in msg(), msg())
    h.check("P2 the preview stays", near(vol(), gusset(2.0), 1e-6), vol())
    ui.type_into(panel().thickness.widget, "3")


def p2_three():
    h.check("P2 Thickness 3", near(vol(), gusset(3.0), 1e-6), (vol(), gusset(3.0)))
    h.check("P2 no message", msg() == "", msg())
    h.fit()


def p2_drag_out():
    p = panel()
    arrow = p.arrows.get("thickness") if p is not None else None
    h.check("P2 the thickness arrow is there", arrow is not None, p and list(p.arrows))
    if arrow is None:
        return
    mid, grow, across, size = p._frame()
    origin = mid - grow * (0.4 * size)
    hole_steps.drag_arrow(origin, across, arrow.distance(), 25.0)


p2_drag_out.wait_ms = 1500


def p2_dragged_out():
    p = panel()
    t = p.thickness.value() if p is not None else 0
    h.check("P2 dragged far out: a thick rib", t > 20.0, t)
    h.check(
        "P2 the volume follows (it sticks out of the bracket)",
        near(vol(), gusset(t), 1e-6),
        (vol(), gusset(t)),
    )
    h.check("P2 no message", msg() == "", msg())
    arrow = p.arrows.get("thickness") if p is not None else None
    if arrow is not None:
        mid, grow, across, size = p._frame()
        origin = mid - grow * (0.4 * size)
        hole_steps.drag_arrow(origin, across, arrow.distance(), -(arrow.distance() + 6.0))


p2_dragged_out.wait_ms = 1500


def p2_dragged_back():
    p = panel()
    t = p.thickness.value() if p is not None else 0
    h.check("P2 dragged back past its start: still a positive thickness", 0 < t < 20.0, t)
    h.check("P2 the volume follows", near(vol(), gusset(t), 1e-6), (vol(), gusset(t)))
    ui.type_into(p.thickness.widget, "3")


def p2_one_side():
    h.check("P2 back to 3", near(vol(), gusset(3.0), 1e-6), vol())
    b.choose(panel().side, "One Side")


def p2_one_side_check():
    p = panel()
    h.check("P2 One Side: the same volume", near(vol(), gusset(3.0), 1e-6), (vol(), gusset(3.0)))
    h.check("P2 Flip Side offered", p is not None and p.flip_side.isVisible())
    s["side1"] = _rib_y_range()
    hole_steps.click_checkbox(p.flip_side)


def p2_flipped_side():
    s["side2"] = _rib_y_range()
    h.check("P2 Flip Side: the same volume", near(vol(), gusset(3.0), 1e-6), (vol(), gusset(3.0)))
    a, c = s["side1"], s["side2"]
    h.check(
        "P2 Flip Side puts the rib on the other side of the sketch plane",
        a is not None and c is not None and near(a[0], -c[1], 1e-6) and near(a[1], -c[0], 1e-6),
        (a, c),
    )
    b.choose(panel().depth_type, "Depth")


def p2_depth():
    p = panel()
    h.check("P2 the Depth box is shown", p is not None and p.depth.widget.isVisible())
    if p is not None:
        ui.type_into(p.depth.widget, "4")


def p2_strip():
    h.check("P2 a 4 deep strip", near(vol(), strip(3.0, 4.0), 1e-6), (vol(), strip(3.0, 4.0)))
    h.check("P2 no message", msg() == "", msg())
    h.shot("p2-strip")
    h.task_button("OK")


def p2_kept():
    h.check("P2 OK", not st.dialog_open())
    h.check("P2 kept", near(vol(), strip(3.0, 4.0), 1e-6), vol())
    st.ctrl("z")


def p2_undone():
    h.check("P2 Ctrl+Z: the bracket", near(vol(), s["bracket"], 1e-6), vol())
    st.ctrl("y")


def p2_redone():
    h.check("P2 Ctrl+Y: the strip", near(vol(), strip(3.0, 4.0), 1e-6), vol())
    st.edit_in_timeline("Extrude 1")


def _rib_y_range():
    """(ymin, ymax) of the rib: the body minus the bracket, measured on the body's shape."""
    ribs = st.features("rib")
    if not ribs:
        return None
    rib = ribs[0]
    base = rib.BaseFeature
    try:
        extra = rib.Shape.cut(base.Shape)
        box = extra.optimalBoundingBox(False, False)
        return (round(box.YMin, 6), round(box.YMax, 6))
    except Exception:
        return None


# == Path 3: an earlier step edited, the rib edited twice =======================================
def p3_extrude_edit():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P3 Extrude 1 opens for editing", p is not None and not p._closed)
    if p is not None:
        ui.type_into(p.distance.widget, "6")


def p3_extrude_ok():
    h.task_button("OK")


def p3_narrower():
    h.check("P3 Extrude closed", not st.dialog_open())
    s["bracket"] = bracket_volume()
    h.check("P3 the bracket is narrower", s["width"] < 19.9, s["width"])
    h.check(
        "P3 the rib follows (still the strip)",
        near(vol(), strip(3.0, 4.0), 1e-6),
        (vol(), strip(3.0, 4.0)),
    )
    st.edit_in_timeline("Rib 1")


def p3_rib_edit():
    p = panel()
    h.check("P3 the Rib dialog edits it", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "P3 the edit shows One Side + Flip Side",
        p.side.currentText() == "One Side" and p.flip_side.isChecked(),
    )
    h.check(
        "P3 the edit shows Depth 4",
        p.depth_type.currentText() == "Depth" and near(p.depth.value(), 4.0),
    )
    b.choose(p.side, "Symmetric")


def p3_to_next():
    b.choose(panel().depth_type, "To Next")


def p3_four():
    ui.type_into(panel().thickness.widget, "4")


def p3_gusset4():
    h.check("P3 gusset 4 thick", near(vol(), gusset(4.0), 1e-6), (vol(), gusset(4.0)))
    h.task_button("OK")


def p3_again():
    h.check("P3 kept", near(vol(), gusset(4.0), 1e-6), vol())
    st.edit_in_timeline("Rib 1")


def p3_nine():
    p = panel()
    h.check(
        "P3 the edit shows Thickness 4",
        p is not None and near(p.thickness.value(), 4.0),
        p and p.thickness.value(),
    )
    if p is not None:
        ui.type_into(p.thickness.widget, "9")


def p3_cancel():
    h.check("P3 preview 9 thick", near(vol(), gusset(9.0), 1e-6), (vol(), gusset(9.0)))
    h.task_button("Cancel")


def p3_cancelled():
    h.check("P3 Cancel: back to 4", near(vol(), gusset(4.0), 1e-6), vol())
    h.check("P3 the body is shown", st.shown(h.body()))


# == Path 4: save, close, reopen, edit ============================================================
def p4_save():
    doc = App.ActiveDocument
    s["path"] = os.path.join(tempfile.mkdtemp(prefix="sfribqa"), "rib_qa.FCStd")
    doc.saveAs(s["path"])
    App.closeDocument(doc.Name)


def p4_reopen():
    App.openDocument(s["path"])


p4_reopen.wait_ms = 2000


def p4_reopened():
    h.check("P4 the rib is back", near(vol(), gusset(4.0), 1e-6), vol())
    h.check("P4 Rib 1 in the timeline", "Rib 1" in st.timeline_titles(), st.timeline_titles())
    h.fit()
    st.edit_in_timeline("Rib 1")


def p4_editing():
    p = panel()
    h.check("P4 the reopened rib opens for editing", p is not None and p.editing)
    if p is None:
        return
    h.check("P4 its curve", len(p.refs) == 1, p.refs)
    widget = p.thickness.widget
    ui.type_into(widget, "2")


def p4_enter():
    p = panel()
    if p is not None:
        widget = p.thickness.widget
        widget.setFocus()
        QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Return)


def p4_done():
    h.check("P4 Enter in the field is OK", not st.dialog_open())
    h.check("P4 thickness 2", near(vol(), gusset(2.0), 1e-6), (vol(), gusset(2.0)))
    h.check("P4 no pop-up", not h.popups(), h.popups())
    h.shot("p4-done")


h.run(
    "sweep_loft_qa_rib",
    si.watched(
        [
            new_design,
            p1_xz,
            p1_line_key,
            p1_line_start,
            p1_line_typed,
            p1_line_done,
            p1_rib,
            p1_open,
            p1_ok_refused,
            p1_no_part,
            p1_ok_again,
            p1_esc,
            p2_sketch,
            p2_xz,
            p2_line_key,
            p2_origin,
            p2_seg1,
            p2_seg2,
            p2_seg3,
            p2_seg4,
            p2_seg5,
            p2_close,
            p2_finish,
            p2_extrude,
            p2_symmetric,
            p2_distance,
            p2_extrude_ok,
            p2_bracket,
            p2_rib,
            p2_open,
            p2_zero,
            p2_zero_ok,
            p2_negative,
            p2_three,
            p2_drag_out,
            p2_dragged_out,
            p2_dragged_back,
            p2_one_side,
            p2_one_side_check,
            p2_flipped_side,
            p2_depth,
            p2_strip,
            p2_kept,
            p2_undone,
            p2_redone,
            p3_extrude_edit,
            p3_extrude_ok,
            p3_narrower,
            p3_rib_edit,
            p3_to_next,
            p3_four,
            p3_gusset4,
            p3_again,
            p3_nine,
            p3_cancel,
            p3_cancelled,
            p4_save,
            p4_reopen,
            p4_reopened,
            p4_editing,
            p4_enter,
            p4_done,
        ]
    ),
)
