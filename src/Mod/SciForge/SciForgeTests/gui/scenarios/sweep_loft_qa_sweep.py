# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sweep the way a Fusion user really uses it, trying to break it (QA, only real input).

Every sketch is drawn with the mouse (C and two clicks for a circle; L, a click and a typed
length for a line), and the expected volumes are worked out by hand from what was drawn.

Path 1, beginner: CREATE > Sweep in an empty design says a sketch is needed (no dialog, no
        pop-up). A circle (about r 4) on XY, a line 40 up on XZ. Sweep: the circle is taken
        by itself; OK and Enter over the 3D view with no path keep the dialog open and say
        why; a background click changes nothing; click the line: a tube (New Body). Enter
        over the 3D view is OK. One undo step.
Path 2, with Create Sketch and Extrude: a sketch on the tube's top face, a circle (about
        r 2), E, 5: a boss. Double-click Sweep 1 in the timeline, Taper 3: the tube becomes a
        frustum and the boss stays on its top face (Fusion edits the sweep and keeps what is
        built on it). OK. Edit it again, Distance 0.5: the tube is 20 high, the boss follows
        its top face down. OK. Ctrl+Z twice, Ctrl+Y once.
Path 3, values while the preview runs (a third edit): Distance 0 (said, OK waits), "0,25",
        Taper 89 and -60 (said), back to 3, Twist 720 (a round profile keeps its volume), the
        ball dragged far past the end of the path (it stops at 1) and far below its start
        (0 is said), then Ctrl+Z in the dialog cancels the edit.
Path 4, Esc in the middle of picking: Ctrl+Z, Sweep, click the boss's top face (a flat face
        profile), Esc: nothing changes, no undo step is left open and Ctrl+Y still brings the
        undone edit back.
Path 5, picks in the wrong order and another command's key: two circles (about r 1.5) on
        XY at x 15, a line 12 up through the first on XZ. Sweep: nothing is taken (two
        areas); click the line first (the Profile box keeps waiting), then inside the first
        circle: the pin does not touch the part, so it is a New Body by itself (Fusion);
        click the second circle, then the first again (it is dropped). Press E: the sweep
        is finished and Extrude starts; Esc.

Hand-derived: a round profile r swept straight L is pi r^2 L; with Fusion's taper a its side
tilts by a, so the end radius is r + L tan a and the volume pi L (r^2 + r R + R^2) / 3.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
PI = math.pi
L1 = 40.0
BOSS = 5.0
PIN = 12.0
s = {}


def panel():
    return st.panel("sweep")


def msg():
    return st.message("sweep")


def near(a, c, tol=1e-6):
    return st.near(a, c, tol)


def vol():
    return h.solid_volume()


def vol_of_first():
    bodies = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Body"]
    return st.volume(bodies[0]) if bodies else 0.0


def xz_click(point):
    si.click(point, approach=V(1.0, 0, 0.6))


def tube_frustum(length, taper):
    return st.frustum(s["r1"], length, taper) if taper else PI * s["r1"] ** 2 * length


def boss():
    return PI * s["r2"] ** 2 * BOSS


# == Path 1: beginner =============================================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SweepQA")
    h.fit()
    h.click_empty()
    st.menu("Sweep")


def p1_empty():
    h.check("P1 Sweep in an empty design opens no dialog", not st.dialog_open())
    h.check("P1 no pop-up", not h.popups(), h.popups())
    h.check("P1 says a sketch is needed", "sketch" in si.tooltip().lower(), si.tooltip())
    h.ribbon("Create Sketch")


def p1_xy():
    h.click(V(12, -8, 0))


def p1_circle_key():
    s["s1"] = h.in_sketch()
    h.check("P1 sketch open on XY", s["s1"] is not None)
    h.press("c")


def p1_centre():
    si.click(V(0, 0, 0))


def p1_radius():
    si.click(V(4, 0, 0))


def p1_finish():
    st.esc()
    h.ribbon("Finish Sketch")


def p1_path_sketch():
    centre, r = st.circle_of(s["s1"])
    s["r1"] = r
    h.check("P1 a circle of about r 4 at the origin", abs(r - 4) < 0.3 and centre.Length < 0.3, r)
    h.fit()
    h.ribbon("Create Sketch")


def p1_xz():
    h.click(V(12, 0, 8))


def p1_line_key():
    s["s2"] = h.in_sketch()
    h.check("P1 sketch open on XZ", s["s2"] is not None)
    h.press("l")


def p1_line_start():
    xz_click(V(0, 0, 0))


def p1_line_typed():
    si.move_towards(V(0.4, 0, 15), V(0, 0, 1))
    si.type_text("40", enter=False)
    si.tab()
    si.type_text("90")


def p1_line_done():
    st.esc()
    st.esc()
    lines = si.lines(s["s2"])
    ok = len(lines) == 1
    if ok:
        g = s["s2"].getGlobalPlacement()
        a, c = g.multVec(lines[0][1].StartPoint), g.multVec(lines[0][1].EndPoint)
        ok = (a - V(0, 0, 0)).Length < 1e-6 and (c - V(0, 0, 40)).Length < 1e-6
    h.check("P1 the path runs from the origin 40 up", ok, s["s2"].Geometry)
    h.ribbon("Finish Sketch")


def p1_sweep():
    h.fit()
    h.click_empty()
    s["undo1"] = st.undo_counts()[0]
    st.menu("Sweep")


def p1_open():
    p = panel()
    h.check("P1 Sweep opens", p is not None and st.dialog_open())
    if p is None:
        return
    h.check("P1 the circle is taken by itself", len(p.profiles) == 1, p.profiles)
    h.check("P1 the Path box waits", p.active == "path" and not p.path, p.active)
    h.check("P1 New Body for the first solid", p.operation.currentText() == "New Body")
    h.task_button("OK")


def p1_ok_refused():
    h.check("P1 OK without a path keeps the dialog open", st.dialog_open() and panel() is not None)
    h.check("P1 the dialog says to pick the path", "path" in msg().lower(), msg())
    h.check("P1 nothing was built", not st.features("sweep") and vol() == 0.0)
    h.check("P1 no pop-up", not h.popups(), h.popups())
    h.shot("p1-ok-refused")
    h.press(QtCore.Qt.Key_Return)


def p1_enter_refused():
    h.check("P1 Enter without a path keeps the dialog", st.dialog_open() and panel() is not None)
    h.click_empty()


def p1_background():
    p = panel()
    h.check("P1 a background click keeps the profile", p is not None and len(p.profiles) == 1)
    h.check("P1 still no path", p is not None and not p.path)
    h.click_edge(V(0, 0, 22))


def p1_preview():
    p = panel()
    if p is None:
        h.check("P1 dialog still open", False)
        return
    h.check("P1 the line is the path", len(p.path) == 1, p.path)
    s["tube"] = PI * s["r1"] ** 2 * L1
    h.check("P1 tube pi r^2 40", near(vol(), s["tube"]), (vol(), s["tube"]))
    h.check("P1 New Body", p.operation.currentText() == "New Body")
    h.check("P1 no message", msg() == "", msg())
    h.press(QtCore.Qt.Key_Return)


def p1_done():
    h.check("P1 Enter over the 3D view is OK", not st.dialog_open())
    h.check("P1 the tube is kept", near(vol(), s["tube"]), vol())
    h.check("P1 one undo step", st.undo_counts()[0] == s["undo1"] + 1, st.undo_counts())
    h.check("P1 sketches hidden", not s["s1"].ViewObject.Visibility)
    h.check("P1 Sweep 1 in the timeline", "Sweep 1" in st.timeline_titles(), st.timeline_titles())
    h.shot("p1-tube")


# == Path 2: Create Sketch + Extrude on the sweep, then edit the sweep ===========================
def p2_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def p2_top():
    h.click(V(1.5, 1.0, L1))


def p2_circle_key():
    s["s3"] = h.in_sketch()
    sk = s["s3"]
    support = sk.AttachmentSupport if sk is not None else None
    h.check(
        "P2 sketch on the tube's top face",
        bool(support) and support[0][0] in st.features("sweep"),
        support,
    )
    h.press("c")


def p2_centre():
    si.click(V(0, 0, L1))


def p2_radius():
    si.click(V(2, 0, L1))


def p2_finish():
    st.esc()
    h.ribbon("Finish Sketch")


def p2_extrude():
    _c, s["r2"] = st.circle_of(s["s3"])
    h.check("P2 a circle of about r 2", abs(s["r2"] - 2) < 0.3, s["r2"])
    h.fit()
    h.press("e")


def p2_extrude_value():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P2 Extrude opens", p is not None and not p._closed)
    if p is not None:
        ui.type_into(p.distance.widget, "5")


def p2_extrude_ok():
    h.task_button("OK")


def p2_boss():
    s["v2a"] = s["tube"] + boss()
    h.check("P2 boss on the tube", near(vol(), s["v2a"]), (vol(), s["v2a"]))
    h.check("P2 Extrude closed", not st.dialog_open())
    st.edit_in_timeline("Sweep 1")


def p2_edit_open():
    p = panel()
    h.check("P2 the Sweep dialog edits it", p is not None and p.editing)
    if p is not None:
        ui.type_into(p.taper.widget, "3")


def p2_taper():
    s["v2b"] = tube_frustum(L1, 3.0) + boss()
    h.check("P2 Taper 3 in an edit: no complaint", msg() == "", msg())
    h.check("P2 frustum + the boss on top", near(vol(), s["v2b"], 1e-5), (vol(), s["v2b"]))
    zmax = st.bbox(h.body().Shape)[5]
    h.check("P2 the boss still stands on the top face", near(zmax, L1 + BOSS), zmax)
    h.shot("p2-taper")
    h.task_button("OK")


def p2_taper_kept():
    h.check("P2 OK closes the edit", not st.dialog_open())
    h.check("P2 taper kept", near(vol(), s["v2b"], 1e-5), vol())
    st.edit_in_timeline("Sweep 1")


def p2_edit2():
    p = panel()
    h.check("P2 second edit opens", p is not None and p.editing)
    if p is not None:
        h.check("P2 the edit shows Taper 3", near(p.taper.value(), 3.0), p.taper.value())
        ui.type_into(p.distance, "0.5")


def p2_half():
    s["v2c"] = tube_frustum(L1 / 2, 3.0) + boss()
    h.check("P2 Distance 0.5: no complaint", msg() == "", msg())
    h.check("P2 half the frustum + the boss", near(vol(), s["v2c"], 1e-5), (vol(), s["v2c"]))
    zmax = st.bbox(h.body().Shape)[5]
    h.check("P2 the boss followed the top face down", near(zmax, L1 / 2 + BOSS), zmax)
    h.task_button("OK")


def p2_half_kept():
    h.check("P2 second edit kept", near(vol(), s["v2c"], 1e-5), vol())
    st.ctrl("z")


def p2_undo1():
    h.check("P2 Ctrl+Z: back to the taper", near(vol(), s["v2b"], 1e-5), (vol(), s["v2b"]))
    st.ctrl("z")


def p2_undo2():
    h.check("P2 Ctrl+Z: back to the plain tube", near(vol(), s["v2a"]), (vol(), s["v2a"]))
    st.ctrl("y")


def p2_redo():
    h.check("P2 Ctrl+Y: the taper again", near(vol(), s["v2b"], 1e-5), (vol(), s["v2b"]))
    st.edit_in_timeline("Sweep 1")


# == Path 3: values while the preview runs =======================================================
def p3_open():
    p = panel()
    h.check("P3 third edit opens", p is not None and p.editing)
    if p is not None:
        ui.type_into(p.distance, "0")


def p3_zero():
    h.check("P3 Distance 0 is said", "0" in msg() and "distance" in msg().lower(), msg())
    h.check("P3 the last good preview stays", near(vol(), s["v2b"], 1e-5), vol())
    h.task_button("OK")


def p3_zero_ok():
    h.check("P3 OK with Distance 0 keeps the dialog", panel() is not None)
    ui.type_into(panel().distance, "0,25")


def p3_quarter():
    s["v3"] = tube_frustum(L1 / 4, 3.0) + boss()
    h.check("P3 a comma works: a quarter", near(vol(), s["v3"], 1e-5), (vol(), s["v3"]))
    h.check("P3 no message", msg() == "", msg())
    ui.type_into(panel().taper.widget, "89")


def p3_taper_89():
    h.check("P3 Taper 89 is said", "89" in msg(), msg())
    h.check("P3 the preview stays", near(vol(), s["v3"], 1e-5), vol())
    ui.type_into(panel().taper.widget, "-60")


def p3_taper_neg():
    h.check("P3 Taper -60 (shrinks to nothing) is said", "nothing" in msg(), msg())
    h.check("P3 the preview stays", near(vol(), s["v3"], 1e-5), vol())
    ui.type_into(panel().taper.widget, "3")


def p3_taper_back():
    h.check("P3 Taper 3 again: no message", msg() == "", msg())
    ui.type_into(panel().twist.widget, "720")


def p3_twist():
    h.check("P3 Twist 720: no message", msg() == "", msg())
    h.check("P3 a round profile keeps its volume", near(vol(), s["v3"], 1e-4), (vol(), s["v3"]))
    h.fit()


def p3_drag_far():
    p = panel()
    handle = p.handles.get("distance") if p is not None else None
    h.check("P3 the distance ball is there", handle is not None, p and list(p.handles))
    if handle is not None:
        st.drag_ball_to(handle, V(0, 0, L1 + 30))


p3_drag_far.wait_ms = 1500


def p3_dragged_far():
    p = panel()
    d = p.distance.value() if p is not None else None
    h.check("P3 dragged far past the end: Distance stops at 1", d is not None and d > 0.99, d)
    h.check("P3 the whole tapered tube", near(vol(), s["v2b"], 1e-4), (vol(), s["v2b"]))
    handle = p.handles.get("distance") if p is not None else None
    if handle is not None:
        st.drag_ball_to(handle, V(0, 0, -30))


p3_dragged_far.wait_ms = 1500


def p3_dragged_back():
    p = panel()
    d = p.distance.value() if p is not None else None
    h.check("P3 dragged below the start: Distance 0", d is not None and d < 0.01, d)
    h.check("P3 Distance 0 is said", "distance" in msg().lower(), msg())
    h.check("P3 the dialog stays open", st.dialog_open())
    h.shot("p3-dragged-back")
    s["counts3"] = st.undo_counts()
    st.ctrl("z")


def p3_cancelled():
    h.check("P3 Ctrl+Z in the dialog cancels the edit", not st.dialog_open())
    h.check("P3 the sweep is as before the edit", near(vol(), s["v2b"], 1e-5), (vol(), s["v2b"]))
    h.check("P3 the body is shown", st.shown(h.body()))
    st.ctrl("z")


# == Path 4: Esc in the middle of picking ========================================================
def p4_undone():
    h.check("P4 Ctrl+Z: the plain tube", near(vol(), s["v2a"]), (vol(), s["v2a"]))
    s["counts4"] = st.undo_counts()
    h.fit()
    st.menu("Sweep")


def p4_open():
    p = panel()
    h.check("P4 Sweep opens", p is not None)
    if p is None:
        return
    h.check("P4 nothing is taken (the circles are used)", not p.profiles, p.profiles)
    h.check("P4 the Profile box waits", p.active == "profiles", p.active)
    h.click(V(0.8, 0.5, L1 + BOSS))


def p4_face():
    p = panel()
    h.check(
        "P4 the boss's top face is the profile",
        p is not None and len(p.profiles) == 1,
        p and p.profiles,
    )
    h.check("P4 the Path box waits", p is not None and p.active == "path", p and p.active)
    st.esc()


def p4_esc():
    h.check("P4 Esc closes the dialog", not st.dialog_open())
    h.check("P4 nothing changed", near(vol(), s["v2a"]), vol())
    h.check(
        "P4 no undo step left behind",
        st.undo_counts() == s["counts4"],
        (st.undo_counts(), s["counts4"]),
    )
    h.check("P4 nothing selected", not Gui.Selection.getSelectionEx())
    st.ctrl("y")


def p4_redo():
    h.check("P4 Ctrl+Y still brings the taper back", near(vol(), s["v2b"], 1e-5), (vol(), s["v2b"]))
    s["v4"] = vol()


# == Path 5: picks in the wrong order, another command's key =====================================
def p5_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def p5_xy():
    h.click(V(14, -10, 0))


def p5_c1():
    s["s5"] = h.in_sketch()
    h.check(
        "P5 sketch open on XY",
        s["s5"] is not None and s["s5"].AttachmentSupport[0][0].Role == "XY_Plane",
    )
    h.press("c")


def p5_c1_centre():
    si.click(V(15, 0, 0))


def p5_c1_radius():
    si.click(V(16.5, 0, 0))


def p5_c2():
    st.esc()
    h.press("c")


def p5_c2_centre():
    si.click(V(15, 8, 0))


def p5_c2_radius():
    si.click(V(16.5, 8, 0))


def p5_finish():
    st.esc()
    st.esc()
    h.ribbon("Finish Sketch")


def p5_path_sketch():
    s["ca"], s["ra"] = st.circle_of(s["s5"], 0)
    s["cb"], s["rb"] = st.circle_of(s["s5"], 1)
    h.check("P5 two circles", s["ra"] > 1.0 and s["rb"] > 1.0, (s["ra"], s["rb"]))
    h.fit()
    h.ribbon("Create Sketch")


def p5_xz():
    h.click(V(24, 0, 10))


def p5_line_key():
    s["s6"] = h.in_sketch()
    h.check(
        "P5 sketch open on XZ",
        s["s6"] is not None and s["s6"].AttachmentSupport[0][0].Role == "XZ_Plane",
    )
    h.press("l")


def p5_line_start():
    xz_click(V(s["ca"].x, 0, 0))


def p5_line_typed():
    si.move_towards(V(s["ca"].x + 0.4, 0, 6), V(0, 0, 1))
    si.type_text("12", enter=False)
    si.tab()
    si.type_text("90")


def p5_line_done():
    st.esc()
    st.esc()
    h.ribbon("Finish Sketch")


def p5_sweep():
    h.fit()
    h.click_empty()
    s["bodies"] = len([o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Body"])
    st.menu("Sweep")


def p5_open():
    p = panel()
    h.check("P5 Sweep opens", p is not None)
    if p is None:
        return
    h.check("P5 nothing is taken (two areas)", not p.profiles, p.profiles)
    line = si.lines(s["s6"])[0][1]
    g = s["s6"].getGlobalPlacement()
    s["line_mid"] = g.multVec((line.StartPoint + line.EndPoint) * 0.5)
    h.click_edge(s["line_mid"])


def p5_line_first():
    p = panel()
    h.check(
        "P5 the line clicked first is the path", p is not None and len(p.path) == 1, p and p.path
    )
    h.check(
        "P5 the Profile box still waits", p is not None and p.active == "profiles", p and p.active
    )
    h.check("P5 nothing built yet", len(st.features("sweep")) == 1)
    st.region_click(s["s5"], lambda faces: min(faces, key=lambda f: f.CenterOfMass.y))


def p5_first_area():
    p = panel()
    pin_a = PI * s["ra"] ** 2 * PIN
    h.check("P5 one profile", p is not None and len(p.profiles) == 1, p and p.profiles)
    h.check(
        "P5 a sweep away from the part is a New Body by itself (Fusion)",
        p is not None and p.operation.currentText() == "New Body",
        p and p.operation.currentText(),
    )
    h.check("P5 no message", msg() == "", msg())
    h.check(
        "P5 pin A as a new body",
        near(st.total_volume(), s["v4"] + pin_a, 1e-6),
        (st.total_volume(), s["v4"] + pin_a),
    )
    h.check("P5 the tube's body is unchanged", near(vol_of_first(), s["v4"], 1e-6), vol_of_first())
    h.shot("p5-new-body")
    st.region_click(s["s5"], lambda faces: max(faces, key=lambda f: f.CenterOfMass.y))


p5_first_area.wait_ms = 1200


def p5_second_area():
    both = PI * (s["ra"] ** 2 + s["rb"] ** 2) * PIN
    p = panel()
    h.check("P5 two profiles", p is not None and len(p.profiles) == 2, p and p.profiles)
    h.check(
        "P5 both pins",
        near(st.total_volume(), s["v4"] + both, 1e-6),
        (st.total_volume(), s["v4"] + both),
    )
    st.region_click(s["s5"], lambda faces: min(faces, key=lambda f: f.CenterOfMass.y))


def p5_dropped():
    pin_b = PI * s["rb"] ** 2 * PIN
    p = panel()
    h.check(
        "P5 clicking the first area again drops it",
        p is not None and len(p.profiles) == 1,
        p and p.profiles,
    )
    h.check(
        "P5 pin B only",
        near(st.total_volume(), s["v4"] + pin_b, 1e-6),
        (st.total_volume(), s["v4"] + pin_b),
    )
    s["v5"] = s["v4"] + pin_b
    h.press("e")


p5_dropped.wait_ms = 1200


def p5_extrude_started():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P5 E finished the sweep", panel() is None)
    h.check("P5 and started Extrude", p is not None and not p._closed and st.dialog_open())
    h.check("P5 the sweep is kept", near(st.total_volume(), s["v5"], 1e-6), st.total_volume())
    st.esc()


def p5_done():
    h.check("P5 Esc closed Extrude", not st.dialog_open())
    h.check("P5 still the pin", near(st.total_volume(), s["v5"], 1e-6), st.total_volume())
    bodies = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Body"]
    h.check("P5 a second body", len(bodies) == s["bodies"] + 1, [o.Label for o in bodies])
    h.check("P5 two sweeps in the timeline", len(st.features("sweep")) == 2, st.features("sweep"))
    h.check("P5 no pop-up", not h.popups(), h.popups())
    h.shot("p5-done")


h.run(
    "sweep_loft_qa_sweep",
    si.watched(
        [
            new_design,
            p1_empty,
            p1_xy,
            p1_circle_key,
            p1_centre,
            p1_radius,
            p1_finish,
            p1_path_sketch,
            p1_xz,
            p1_line_key,
            p1_line_start,
            p1_line_typed,
            p1_line_done,
            p1_sweep,
            p1_open,
            p1_ok_refused,
            p1_enter_refused,
            p1_background,
            p1_preview,
            p1_done,
            p2_sketch,
            p2_top,
            p2_circle_key,
            p2_centre,
            p2_radius,
            p2_finish,
            p2_extrude,
            p2_extrude_value,
            p2_extrude_ok,
            p2_boss,
            p2_edit_open,
            p2_taper,
            p2_taper_kept,
            p2_edit2,
            p2_half,
            p2_half_kept,
            p2_undo1,
            p2_undo2,
            p2_redo,
            p3_open,
            p3_zero,
            p3_zero_ok,
            p3_quarter,
            p3_taper_89,
            p3_taper_neg,
            p3_taper_back,
            p3_twist,
            p3_drag_far,
            p3_dragged_far,
            p3_dragged_back,
            p3_cancelled,
            p4_undone,
            p4_open,
            p4_face,
            p4_esc,
            p4_redo,
            p5_sketch,
            p5_xy,
            p5_c1,
            p5_c1_centre,
            p5_c1_radius,
            p5_c2,
            p5_c2_centre,
            p5_c2_radius,
            p5_finish,
            p5_path_sketch,
            p5_xz,
            p5_line_key,
            p5_line_start,
            p5_line_typed,
            p5_line_done,
            p5_sweep,
            p5_open,
            p5_line_first,
            p5_first_area,
            p5_second_area,
            p5_dropped,
            p5_extrude_started,
            p5_done,
        ]
    ),
)
