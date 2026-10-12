# SPDX-License-Identifier: LGPL-2.1-or-later
"""A part of several features with a sweep along an edge of the part (QA, only real input).

A cylinder: a circle (about r 10) on XY, E, 10. A sketch on XZ (through the axis) with a
small circle (about r 1.5) inside the cylinder near its top edge.

Path 1, a model edge as the path, Cut by itself, Intersect: CREATE > Sweep takes the small
        circle by itself; click the cylinder's top edge (a part edge, one closed curve):
        the profile runs round inside the part, so Fusion's Cut is chosen by itself: a ring
        channel. Intersect: only the ring is left. Cut again, OK.
Path 2, Press Pull after the sweep, then the sweep edited: Q, the top face, 3: the cylinder
        is 3 taller. Double-click Sweep 1, Distance 0.5 (half the ring; SciForge's sweep
        replaces FreeCAD's): the Press Pull still lifts the top face. OK.
Path 3, save, close, reopen, edit: the half ring and the Press Pull come back; double-click
        Sweep 1: Distance 0.5 is shown; 0.75, OK.
Path 4, an earlier step edited: double-click Extrude 1, 12 instead of 10: the top edge, the
        path, moves up and the channel with it; the Press Pull still adds 3 on top.

Hand-derived (Pappus): the channel is the small circle's area times the length its centre
travels round the axis, pi r^2 2 pi x (x: the circle centre's distance from the axis); a
share d of the path gives d of that. The cylinder is pi R^2 h.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
PI = math.pi
s = {}


def panel():
    return st.panel("sweep")


def msg():
    return st.message("sweep")


def near(a, c, tol=1e-6):
    return st.near(a, c, tol)


def vol():
    return h.solid_volume()


def cylinder(height):
    return PI * s["R"] ** 2 * height


def ring(share=1.0):
    return PI * s["r"] ** 2 * 2.0 * PI * s["x"] * share


def edge_point(height):
    a = math.radians(-45.0)
    return V(s["R"] * math.cos(a), s["R"] * math.sin(a), height)


# == the cylinder and the small circle ===========================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SweepPart")
    h.fit()
    h.ribbon("Create Sketch")


def c_xy():
    h.click(V(12, -8, 0))


def c_key():
    s["sc"] = h.in_sketch()
    h.check("sketch open on XY", s["sc"] is not None)
    h.press("c")


def c_centre():
    si.click(V(0, 0, 0))


def c_radius():
    si.click(V(10, 0, 0))


def c_finish():
    st.esc()
    h.ribbon("Finish Sketch")


def c_extrude():
    centre, s["R"] = st.circle_of(s["sc"])
    h.check("a circle of about r 10 at the origin", abs(s["R"] - 10) < 0.3 and centre.Length < 1e-6)
    h.fit()
    h.press("e")


def c_distance():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("Extrude opens", p is not None and not p._closed)
    if p is not None:
        ui.type_into(p.distance.widget, "10")


def c_ok():
    h.task_button("OK")


def p_sketch():
    h.check("the cylinder", near(vol(), cylinder(10.0)), (vol(), cylinder(10.0)))
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p_xz():
    # left of the axis, where no part lies behind the XZ square (Create Sketch leaves a
    # click with a face of the part under the mouse to that face)
    h.click(V(-12, 0, 12))


def p_key():
    s["sp"] = h.in_sketch()
    sk = s["sp"]
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    h.press("c")


def p_centre():
    si.click(V(7, 0, 7), approach=V(1.0, 0, 0.6))


def p_radius():
    si.click(V(8.5, 0, 7), approach=V(1.0, 0, 0.6))


def p_finish():
    st.esc()
    h.ribbon("Finish Sketch")


# == Path 1: a part edge as the path ===============================================================
def p1_sweep():
    centre, s["r"] = st.circle_of(s["sp"])
    s["x"] = math.hypot(centre.x, centre.y)
    inside = s["x"] + s["r"] < s["R"] - 0.5 and centre.z + s["r"] < 9.5
    h.check("a small circle inside the cylinder near its top edge", inside, (centre, s["r"]))
    h.fit()
    h.click_empty()
    st.menu("Sweep")


def p1_open():
    p = panel()
    h.check("P1 Sweep opens with the small circle", p is not None and len(p.profiles) == 1)
    h.check("P1 the Path box waits", p is not None and p.active == "path", p and p.active)
    h.click_edge(edge_point(10.0))


def p1_path():
    p = panel()
    if p is None:
        h.check("P1 dialog open", False)
        return
    h.check("P1 the top edge is the path", len(p.path) == 1, p.path)
    h.check(
        "P1 an edge of the part as it was before the sweep (not of the preview)",
        bool(p.path) and p.path[0][0].TypeId == "PartDesign::Pad",
        p.path and p.path[0][0].TypeId,
    )
    h.check("P1 inside the part: Cut by itself", p.operation.currentText() == "Cut")
    v = cylinder(10.0) - ring()
    h.check("P1 a ring channel (Pappus)", near(vol(), v, 1e-5), (vol(), v))
    h.check("P1 no message", msg() == "", msg())
    h.shot("p1-channel")
    b.choose(p.operation, "Intersect")


def p1_intersect():
    h.check("P1 Intersect: only the ring is left", near(vol(), ring(), 1e-5), (vol(), ring()))
    h.check("P1 no message", msg() == "", msg())
    b.choose(panel().operation, "Cut")


def p1_cut():
    v = cylinder(10.0) - ring()
    h.check("P1 Cut again", near(vol(), v, 1e-5), (vol(), v))
    h.task_button("OK")


def p1_done():
    h.check("P1 OK", not st.dialog_open())
    h.check("P1 kept", near(vol(), cylinder(10.0) - ring(), 1e-5), vol())
    h.fit()
    h.click_empty()
    h.press("q")


# == Path 2: Press Pull after the sweep, then the sweep edited ===================================
def p2_top():
    h.check("P2 Q opens Press Pull", st.dialog_open())
    h.click(V(-3, 3, 10))


def p2_pull():
    from sciforge import taskui

    p = taskui.current()
    field = getattr(p, "field", None)
    h.check("P2 the top face is picked", p is not None and getattr(p, "target", None) is not None)
    if field is not None:
        ui.type_into(field.widget, "3")


def p2_pull_ok():
    h.task_button("OK")


def p2_pulled():
    v = cylinder(13.0) - ring()
    h.check("P2 3 taller", near(vol(), v, 1e-5), (vol(), v))
    h.fit()
    st.edit_in_timeline("Sweep 1")


def p2_edit():
    p = panel()
    h.check("P2 the Sweep dialog edits it", p is not None and p.editing)
    if p is not None:
        ui.type_into(p.distance, "0.5")


def p2_half():
    p = panel()
    v = cylinder(13.0) - ring(0.5)
    h.check("P2 no message", msg() == "", msg())
    h.check(
        "P2 SciForge's sweep for half the path",
        p is not None and p.target is not None and getattr(p.target, "SciForgeType", "") == "Sweep",
        p and p.target and p.target.TypeId,
    )
    h.check("P2 half the ring, the Press Pull still on top", near(vol(), v, 1e-5), (vol(), v))
    h.task_button("OK")


def p2_kept():
    h.check("P2 OK", not st.dialog_open())
    h.check("P2 kept", near(vol(), cylinder(13.0) - ring(0.5), 1e-5), vol())
    zmax = st.bbox(h.body().Shape)[5]
    h.check("P2 the top is at 13", near(zmax, 13.0), zmax)


# == Path 3: save, close, reopen, edit =============================================================
def p3_save():
    doc = App.ActiveDocument
    s["path"] = os.path.join(tempfile.mkdtemp(prefix="sfsweepqa"), "sweep_part.FCStd")
    doc.saveAs(s["path"])
    App.closeDocument(doc.Name)


def p3_reopen():
    App.openDocument(s["path"])


p3_reopen.wait_ms = 2000


def p3_reopened():
    h.check("P3 reopened: the half ring and the Press Pull", near(vol(), cylinder(13.0) - ring(0.5), 1e-5), vol())
    sweeps = st.features("sweep")
    h.check(
        "P3 SciForge's sweep is restored",
        len(sweeps) == 1 and getattr(sweeps[0], "SciForgeType", "") == "Sweep",
        [o.TypeId for o in sweeps],
    )
    h.fit()
    st.edit_in_timeline("Sweep 1")


def p3_edit():
    p = panel()
    h.check("P3 the reopened sweep opens for editing", p is not None and p.editing)
    if p is None:
        return
    h.check("P3 Distance 0.5 is shown", near(p.distance.value(), 0.5), p.distance.value())
    h.check("P3 Cut is shown", p.operation.currentText() == "Cut")
    ui.type_into(p.distance, "0.75")


def p3_three_quarters():
    v = cylinder(13.0) - ring(0.75)
    h.check("P3 three quarters of the ring", near(vol(), v, 1e-5), (vol(), v))
    h.task_button("OK")


def p3_done():
    h.check("P3 OK", not st.dialog_open())
    h.check("P3 kept", near(vol(), cylinder(13.0) - ring(0.75), 1e-5), vol())
    st.edit_in_timeline("Extrude 1")


# == Path 4: an earlier step edited ================================================================
def p4_extrude():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P4 Extrude 1 opens for editing", p is not None and not p._closed)
    if p is not None:
        ui.type_into(p.distance.widget, "12")


def p4_ok():
    h.task_button("OK")


def p4_done():
    h.check("P4 Extrude closed", not st.dialog_open())
    v = cylinder(15.0) - ring(0.75)
    h.check("P4 the channel followed its edge, the Press Pull still on top", near(vol(), v, 1e-5), (vol(), v))
    zmax = st.bbox(h.body().Shape)[5]
    h.check("P4 the top is at 15", near(zmax, 15.0), zmax)
    sweeps = st.features("sweep")
    h.check("P4 the sweep is fine", sweeps and "Invalid" not in sweeps[0].State, sweeps and sweeps[0].State)
    h.check("P4 no pop-up", not h.popups(), h.popups())
    h.shot("p4-done")


h.run(
    "sweep_loft_qa_part",
    si.watched(
        [
            new_design,
            c_xy,
            c_key,
            c_centre,
            c_radius,
            c_finish,
            c_extrude,
            c_distance,
            c_ok,
            p_sketch,
            p_xz,
            p_key,
            p_centre,
            p_radius,
            p_finish,
            p1_sweep,
            p1_open,
            p1_path,
            p1_intersect,
            p1_cut,
            p1_done,
            p2_top,
            p2_pull,
            p2_pull_ok,
            p2_pulled,
            p2_edit,
            p2_half,
            p2_kept,
            p3_save,
            p3_reopen,
            p3_reopened,
            p3_edit,
            p3_three_quarters,
            p3_done,
            p4_extrude,
            p4_ok,
            p4_done,
        ]
    ),
)
