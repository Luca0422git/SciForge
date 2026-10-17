# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loft the way a Fusion user really uses it, trying to break it (QA, only real input).

Circles drawn with the mouse: about r 8 on XY at the origin, about r 4 at the origin of an
Offset Plane 30 above XY (CONSTRUCT, typed 30; its eye then clicked off in the browser).

Path 1, wrong order and OK with nothing: CREATE > Loft opens with New Body already chosen
        (there is no solid yet) and nothing picked; OK keeps the dialog and says to pick two
        profiles. Click the top circle first, then the bottom one: the loft goes top to
        bottom, the same frustum. Enter over the 3D view is OK; one undo step.
Path 2, Esc and another command's key in the middle of picking: Ctrl+Z, Loft, click the
        bottom circle, Esc: nothing changes, no undo step is left behind. Loft again, click
        the bottom circle, press Q: the half-made loft is dropped and Press Pull starts; Esc.
        Ctrl+Y still brings the loft back (the Redo list survives both).
Path 3, with Create Sketch and Extrude, and a guide added later: a circle (about r 2) on
        the loft's top face, E 5: a boss. A line on XZ at x 12 from z 0, 30 long. Double-click
        Loft 1 in the timeline, Guide Type Centerline, click the line: the loft follows it
        (the same frustum, now SciForge's loft) and the boss stays on the top face. OK. Edit
        it again: back to Rails with no rail (FreeCAD's loft again), OK. Ctrl+Z, Ctrl+Y.
Path 4, save, close, reopen, edit: the loft and the boss come back; the line's sketch
        shown with its eye in the browser; double-click Loft 1: its two profiles are listed
        in their order; Centerline + the line again, OK.
Path 5, a used profile is not taken again: E right after (Extrude must not take the loft's
        top circle by itself: it is used), Esc; Sweep, nothing taken, Esc.

Hand-derived: a loft between two coaxial circles r1 and r2, h apart, is a frustum,
pi h (r1^2 + r1 r2 + r2^2) / 3 (FreeCAD's loft and SciForge's centerline loft are both
straight between two sections); the boss is pi r^2 5.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sweep_loft_steps as st
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
PI = math.pi
H = 30.0
BOSS = 5.0
s = {}


def panel():
    return st.panel("loft")


def msg():
    return st.message("loft")


def near(a, c, tol=1e-6):
    return st.near(a, c, tol)


def vol():
    return h.solid_volume()


def frustum():
    ra, rb = s["ra"], s["rb"]
    return PI * H * (ra * ra + ra * rb + rb * rb) / 3.0


def boss():
    return PI * s["rc"] ** 2 * BOSS


def bottom(faces):
    return min(faces, key=lambda f: f.CenterOfMass.z)


def list_texts(p):
    return [p.list.item(i).text() for i in range(p.list.count())]


# == the two circles ==============================================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("LoftQA")
    h.fit()
    h.ribbon("Create Sketch")


def a_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def a_circle_key():
    s["sa"] = h.in_sketch()
    h.check("sketch open on XY", s["sa"] is not None)
    h.press("c")


def a_centre():
    si.click(V(0, 0, 0))


def a_radius():
    # Ctrl: placed freely, as a person drawing "about 8" does. Without it the sketch grid's
    # snap can take the point to the 10 mm line (it did once the document tabs moved to the
    # top and the 3D view became 13 px shorter: the grid's spacing follows the zoom)
    si.click_held(V(8, 0, 0), QtCore.Qt.ControlModifier)


def a_finish():
    st.esc()
    h.ribbon("Finish Sketch")


def plane_start():
    centre, s["ra"] = st.circle_of(s["sa"])
    h.check("a circle of about r 8 at the origin", abs(s["ra"] - 8) < 0.3 and centre.Length < 1e-6)
    h.fit()
    h.click_empty()
    h.ribbon("Offset Plane")


def plane_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def plane_distance():
    from sciforge import construct_ui

    p = construct_ui.ConstructPanel.last
    h.check("offset plane dialog", p is not None and p.field is not None)
    if p is not None and p.field is not None:
        ui.type_into(p.field.widget, "30")


def plane_ok():
    h.task_button("OK")


def b_sketch():
    planes = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Plane"]
    h.check("a plane at z 30", len(planes) == 1 and near(planes[0].Placement.Base.z, H), planes)
    s["plane"] = planes[0] if planes else None
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def b_plane():
    h.click(V(2, -2, H))


def b_circle_key():
    s["sb"] = h.in_sketch()
    sk = s["sb"]
    h.check(
        "sketch open on the plane",
        sk is not None and s["plane"] is not None and sk.AttachmentSupport[0][0] is s["plane"],
    )
    h.press("c")


def b_centre():
    si.click(V(0, 0, H))


def b_radius():
    si.click(V(4, 0, H))


def b_finish():
    st.esc()
    h.ribbon("Finish Sketch")


def hide_plane():
    centre, s["rb"] = st.circle_of(s["sb"])
    h.check(
        "a circle of about r 4 above the first",
        abs(s["rb"] - 4) < 0.3 and (centre - V(0, 0, H)).Length < 1e-6,
        (centre, s["rb"]),
    )
    s["sa_label"], s["sb_label"] = s["sa"].Label, s["sb"].Label
    h.check("the plane's eye clicked", ti.click_eye(s["plane"].Label))


# == Path 1: OK with nothing, the wrong order ===================================================
def p1_loft():
    h.check("the plane is hidden", not s["plane"].ViewObject.Visibility)
    h.fit()
    h.click_empty()
    s["undo1"] = st.undo_counts()[0]
    st.menu("Loft")


def p1_open():
    p = panel()
    h.check("P1 Loft opens", p is not None)
    if p is None:
        return
    h.check("P1 nothing is picked", not p.profiles, p.profiles)
    h.check("P1 New Body is shown at once (no solid yet)", p.operation.currentText() == "New Body")
    h.task_button("OK")


def p1_ok_refused():
    h.check("P1 OK with nothing keeps the dialog", st.dialog_open() and panel() is not None)
    h.check("P1 the dialog says to pick two profiles", "two profiles" in msg(), msg())
    h.check("P1 no pop-up", not h.popups(), h.popups())
    st.region_click(s["sb"])


def p1_top_first():
    p = panel()
    h.check("P1 the top circle is profile 1", p is not None and len(p.profiles) == 1)
    st.region_click(s["sa"])


def p1_lofted():
    p = panel()
    h.check("P1 two profiles", p is not None and len(p.profiles) == 2, p and p.profiles)
    if p is None:
        return
    texts = list_texts(p)
    h.check(
        "P1 the list keeps the click order (top first)",
        len(texts) == 2 and s["sb"].Label in texts[0] and s["sa"].Label in texts[1],
        texts,
    )
    h.check("P1 top to bottom: the same frustum", near(vol(), frustum(), 1e-6), (vol(), frustum()))
    h.check("P1 no message", msg() == "", msg())
    h.press(QtCore.Qt.Key_Return)


def p1_done():
    h.check("P1 Enter over the 3D view is OK", not st.dialog_open())
    h.check("P1 kept", near(vol(), frustum(), 1e-6), vol())
    h.check("P1 one undo step", st.undo_counts()[0] == s["undo1"] + 1, st.undo_counts())
    h.check("P1 Loft 1 in the timeline", "Loft 1" in st.timeline_titles(), st.timeline_titles())
    h.check("P1 the sketches are hidden", not s["sa"].ViewObject.Visibility)
    h.shot("p1-frustum")
    st.ctrl("z")


# == Path 2: Esc and another command's key in the middle of picking =============================
def p2_undone():
    h.check("P2 Ctrl+Z took the loft away", vol() == 0.0, vol())
    s["counts2"] = st.undo_counts()
    h.check("P2 one step to redo", s["counts2"][1] == 1, s["counts2"])
    h.fit()
    st.menu("Loft")


def p2_open():
    h.check("P2 Loft opens", panel() is not None)
    st.region_click(s["sa"])


def p2_one():
    p = panel()
    h.check("P2 one profile", p is not None and len(p.profiles) == 1, p and p.profiles)
    st.esc()


def p2_esc():
    h.check("P2 Esc closes the dialog", not st.dialog_open())
    h.check("P2 nothing changed", vol() == 0.0, vol())
    h.check(
        "P2 no undo step left", st.undo_counts() == s["counts2"], (st.undo_counts(), s["counts2"])
    )
    st.menu("Loft")


def p2_again():
    h.check("P2 Loft opens again", panel() is not None)
    st.region_click(s["sa"])


def p2_q():
    p = panel()
    h.check("P2 one profile again", p is not None and len(p.profiles) == 1)
    h.press("q")


def p2_presspull():
    from sciforge import taskui

    h.check("P2 Q dropped the half-made loft", panel() is None)
    current = taskui.current()
    h.check(
        "P2 and started Press Pull",
        current is not None and "Press" in getattr(current, "title", ""),
        current and getattr(current, "title", ""),
    )
    h.check("P2 nothing was built", vol() == 0.0 and not st.features("loft"), vol())
    st.esc()


def p2_closed():
    h.check("P2 Esc closed Press Pull", not st.dialog_open())
    h.check(
        "P2 the Redo list is still there",
        st.undo_counts() == s["counts2"],
        (st.undo_counts(), s["counts2"]),
    )
    st.ctrl("y")


def p2_redone():
    h.check("P2 Ctrl+Y: the loft is back", near(vol(), frustum(), 1e-6), (vol(), frustum()))


# == Path 3: a boss on the loft, then a centerline added in an edit ==============================
def p3_sketch():
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p3_top():
    h.click(V(1.5, -1.0, H))


def p3_circle_key():
    s["sc"] = h.in_sketch()
    sk = s["sc"]
    support = sk.AttachmentSupport if sk is not None else None
    h.check(
        "P3 sketch on the loft's top face",
        bool(support) and support[0][0] in st.features("loft"),
        support,
    )
    h.press("c")


def p3_centre():
    si.click(V(0, 0, H))


def p3_radius():
    si.click(V(2, 0, H))


def p3_finish():
    st.esc()
    h.ribbon("Finish Sketch")


def p3_extrude():
    _c, s["rc"] = st.circle_of(s["sc"])
    h.check("P3 a circle of about r 2", abs(s["rc"] - 2) < 0.3, s["rc"])
    h.fit()
    h.press("e")


def p3_extrude_value():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P3 Extrude opens", p is not None and not p._closed)
    if p is not None:
        ui.type_into(p.distance.widget, "5")


def p3_extrude_ok():
    h.task_button("OK")


def p3_line_sketch():
    s["v3a"] = frustum() + boss()
    h.check("P3 the boss on the loft", near(vol(), s["v3a"], 1e-6), (vol(), s["v3a"]))
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p3_xz():
    pl.click_square("XZ_Plane")  # where the square shows (was 20, 0, 22)


def p3_line_key():
    s["sd"] = h.in_sketch()
    sk = s["sd"]
    h.check(
        "P3 sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane"
    )
    h.press("l")


def p3_line_start():
    si.click(V(12, 0, 0), approach=V(1.0, 0, 0.6))


def p3_line_typed():
    si.move_towards(V(12.4, 0, 15), V(0, 0, 1))
    si.type_text("30", enter=False)
    si.tab()
    si.type_text("90")


def p3_line_done():
    st.esc()
    st.esc()
    h.ribbon("Finish Sketch")


def p3_edit():
    lines = si.lines(s["sd"])
    h.check("P3 one line", len(lines) == 1, s["sd"].Geometry)
    g = s["sd"].getGlobalPlacement()
    if lines:
        s["line_mid"] = g.multVec((lines[0][1].StartPoint + lines[0][1].EndPoint) * 0.5)
    s["sd_label"] = s["sd"].Label
    h.fit()
    st.edit_in_timeline("Loft 1")


def p3_editing():
    p = panel()
    h.check("P3 the Loft dialog edits it", p is not None and p.editing)
    if p is not None:
        b.choose(p.guide, "Centerline")


def p3_centerline_box():
    p = panel()
    h.check(
        "P3 the Centerline box is shown",
        p is not None and p.fields["centerline"].widget.isVisible(),
    )
    h.click_edge(s["line_mid"])


def p3_centerline():
    p = panel()
    h.check(
        "P3 the line is the centerline",
        p is not None and len(p.centerline) == 1,
        p and p.centerline,
    )
    h.check("P3 no message", msg() == "", msg())
    h.check(
        "P3 SciForge's loft follows the line",
        p is not None and p.target is not None and getattr(p.target, "SciForgeType", "") == "Loft",
        p and p.target and p.target.TypeId,
    )
    h.check(
        "P3 the same frustum, the boss still on top", near(vol(), s["v3a"], 1e-5), (vol(), s["v3a"])
    )
    zmax = st.bbox(h.body().Shape)[5]
    h.check("P3 the boss stands on the top face", near(zmax, H + BOSS), zmax)
    h.shot("p3-centerline")
    h.task_button("OK")


def p3_kept():
    h.check("P3 OK closes the edit", not st.dialog_open())
    h.check("P3 kept", near(vol(), s["v3a"], 1e-5), vol())
    st.edit_in_timeline("Loft 1")


def p3_edit2():
    p = panel()
    h.check("P3 second edit opens", p is not None and p.editing)
    if p is not None:
        h.check("P3 the edit shows Centerline", p.guide.currentText() == "Centerline")
        b.choose(p.guide, "Rails")


def p3_rails():
    p = panel()
    h.check("P3 no message", msg() == "", msg())
    h.check(
        "P3 FreeCAD's own loft again",
        p is not None and p.target is not None and p.target.TypeId == "PartDesign::AdditiveLoft",
        p and p.target and p.target.TypeId,
    )
    h.check("P3 the same part", near(vol(), s["v3a"], 1e-5), (vol(), s["v3a"]))
    h.task_button("OK")


def p3_undo():
    h.check("P3 second edit kept", near(vol(), s["v3a"], 1e-5), vol())
    st.ctrl("z")


def p3_undone():
    h.check("P3 Ctrl+Z: the centerline loft and the boss", near(vol(), s["v3a"], 1e-5), vol())
    loft_ = st.features("loft")
    h.check(
        "P3 Ctrl+Z brought SciForge's loft back",
        len(loft_) == 1 and getattr(loft_[0], "SciForgeType", "") == "Loft",
        [o.TypeId for o in loft_],
    )
    st.ctrl("y")


def p3_redone():
    loft_ = st.features("loft")
    h.check(
        "P3 Ctrl+Y: FreeCAD's loft again",
        len(loft_) == 1 and loft_[0].TypeId == "PartDesign::AdditiveLoft",
        [o.TypeId for o in loft_],
    )
    h.check("P3 the same part", near(vol(), s["v3a"], 1e-5), vol())


# == Path 4: save, close, reopen, edit ==========================================================
def p4_save():
    doc = App.ActiveDocument
    s["path"] = os.path.join(tempfile.mkdtemp(prefix="sfloftqa"), "loft_qa.FCStd")
    doc.saveAs(s["path"])
    App.closeDocument(doc.Name)


def p4_reopen():
    h.check("P4 the design is closed", App.ActiveDocument is None or not st.features("loft"))
    App.openDocument(s["path"])


p4_reopen.wait_ms = 2000


def p4_reopened():
    h.check("P4 reopened: the loft and the boss", near(vol(), s["v3a"], 1e-5), vol())
    h.check("P4 Loft 1 in the timeline", "Loft 1" in st.timeline_titles(), st.timeline_titles())
    h.fit()
    # the line's sketch was hidden when the loft used it: shown again with its eye
    h.check("P4 the line sketch's eye clicked", ti.click_eye(s["sd_label"]))


def p4_shown():
    found = App.ActiveDocument.getObjectsByLabel(s["sd_label"])
    h.check("P4 the line's sketch is shown", bool(found) and found[0].ViewObject.Visibility)
    st.edit_in_timeline("Loft 1")


def p4_editing():
    p = panel()
    h.check("P4 the reopened loft opens for editing", p is not None and p.editing)
    if p is None:
        return
    texts = list_texts(p)
    h.check(
        "P4 its two profiles in their order",
        len(texts) == 2 and s["sb_label"] in texts[0] and s["sa_label"] in texts[1],
        texts,
    )
    b.choose(p.guide, "Centerline")


def p4_centerline_box():
    p = panel()
    h.check(
        "P4 the Centerline box is shown",
        p is not None and p.fields["centerline"].widget.isVisible(),
    )
    h.click_edge(s["line_mid"])


def p4_centerline():
    p = panel()
    h.check("P4 the centerline", p is not None and len(p.centerline) == 1, p and p.centerline)
    h.check("P4 no message", msg() == "", msg())
    h.check("P4 the same part", near(vol(), s["v3a"], 1e-5), (vol(), s["v3a"]))
    h.task_button("OK")


def p4_done():
    h.check("P4 OK", not st.dialog_open())
    h.check("P4 kept", near(vol(), s["v3a"], 1e-5), vol())
    h.check("P4 the boss is still on top", near(st.bbox(h.body().Shape)[5], H + BOSS))


# == Path 5: a used profile is not taken again ===================================================
def p5_extrude():
    h.fit()
    h.click_empty()
    h.press("e")


def p5_extrude_open():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P5 Extrude opens", p is not None and not p._closed)
    h.check(
        "P5 Extrude does not take a loft's profile by itself",
        p is not None and not p.profiles,
        p and p.profiles,
    )
    h.check("P5 the part is unchanged", near(vol(), s["v3a"], 1e-5), vol())
    st.esc()


def p5_sweep():
    h.check("P5 Esc closed Extrude", not st.dialog_open())
    st.menu("Sweep")


def p5_sweep_open():
    p = st.panel("sweep")
    h.check("P5 Sweep opens", p is not None)
    h.check("P5 Sweep takes no used profile", p is not None and not p.profiles, p and p.profiles)
    st.esc()


def p5_done():
    h.check("P5 all closed", not st.dialog_open())
    h.check("P5 the part is unchanged", near(vol(), s["v3a"], 1e-5), vol())
    h.check("P5 no pop-up", not h.popups(), h.popups())
    h.shot("p5-done")


h.run(
    "sweep_loft_qa_loft",
    si.watched(
        [
            new_design,
            a_xy,
            a_circle_key,
            a_centre,
            a_radius,
            a_finish,
            plane_start,
            plane_xy,
            plane_distance,
            plane_ok,
            b_sketch,
            b_plane,
            b_circle_key,
            b_centre,
            b_radius,
            b_finish,
            hide_plane,
            p1_loft,
            p1_open,
            p1_ok_refused,
            p1_top_first,
            p1_lofted,
            p1_done,
            p2_undone,
            p2_open,
            p2_one,
            p2_esc,
            p2_again,
            p2_q,
            p2_presspull,
            p2_closed,
            p2_redone,
            p3_sketch,
            p3_top,
            p3_circle_key,
            p3_centre,
            p3_radius,
            p3_finish,
            p3_extrude,
            p3_extrude_value,
            p3_extrude_ok,
            p3_line_sketch,
            p3_xz,
            p3_line_key,
            p3_line_start,
            p3_line_typed,
            p3_line_done,
            p3_edit,
            p3_editing,
            p3_centerline_box,
            p3_centerline,
            p3_kept,
            p3_edit2,
            p3_rails,
            p3_undo,
            p3_undone,
            p3_redone,
            p4_save,
            p4_reopen,
            p4_reopened,
            p4_shown,
            p4_editing,
            p4_centerline_box,
            p4_centerline,
            p4_done,
            p5_extrude,
            p5_extrude_open,
            p5_sweep,
            p5_sweep_open,
            p5_done,
        ]
    ),
)
