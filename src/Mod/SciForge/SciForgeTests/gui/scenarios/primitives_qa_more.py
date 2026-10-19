# SPDX-License-Identifier: LGPL-2.1-or-later
"""Primitives QA: a conical spring, a ring groove, another command's key (only real input).

M1. A conical spring. Coil on XY, centre on the origin, a point at (10, 0): d20. Type
    Revolution and Pitch (the same coil described another way: 5 revolutions, pitch 4);
    Revolutions 4, Pitch 5; Angle -10: Fusion's coil narrows as it rises. It must stay
    above the plane (FreeCAD's helix gave the mirror image: down through the plane,
    widening). Angle -60 closes the coil before its end: said, OK waits; -10 again, OK.
    Edited from the timeline: the dialog shows what was left; Section Triangular
    (Internal), Section Position Outside; OK. Ctrl+Z, Ctrl+Y. Saved to a temporary file,
    closed, reopened: the same spring; edited again to Angle 10 (it widens), OK.
M2. A ring groove in a block. Box 40 x 40, Height 10 typed, beside the spring (New Body by
    itself). Its top selected, Torus: the face is taken at once; centre in the middle, a
    point 8 mm out: inner d16, the torus d5 sits half in, half out of the block: Join.
    Torus Diameter 4; Position Inside; Cut: a groove. The torus arrow dragged to 3: the
    field and the groove follow; 4 typed again; OK. Edited from the timeline: it shows
    Inside, 4, Cut; Outside; OK. Ctrl+Z, Ctrl+Y.
M3. Another command's key while the Pipe dialog is open: Pipe, the block's top front edge
    clicked (a pipe d2 along it, mostly outside: Join), then E: Fusion keeps the pipe and
    starts Extrude; Esc closes Extrude; the pipe stays.

Hand-derived volumes (Pappus: section area x the path its centre of area travels round
the axis; pi = PI, t = tan 10 deg):
  coil d20, circle d2 inside (centre at r 9): 5 turns 90 pi^2, 4 turns 72 pi^2 (the pitch
  changes nothing); narrowing by 10 deg over 20 mm, mean radius 9 - 10 t:
  pi x 2 pi x 4 x (9 - 10 t); triangle (circumscribed d2, area 3 sqrt(3) / 4) pointing
  in, outside the diameter (centre at r 10 + 1): A x 2 pi x 4 x (11 -+ 10 t).
  block 40 x 40 x 10 = 16000. Torus ring radius R, tube r, V = 2 pi^2 R r^2; half of it
  lies in the block (its middle is on the top face): d5 on centre (R 8, r 2.5): + 50 pi^2;
  d4 (r 2): + 32 pi^2; Inside (R 6): + 24 pi^2; Cut: - 24 pi^2; tube t: - pi^2 (8 - t/2)
  (t/2)^2; Outside (R 10): - 40 pi^2. Pipe d2 along a 40 mm top edge, 3/4 outside: + 30 pi.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
PI = math.pi
T10 = math.tan(math.radians(10.0))
TRI = 3.0 * math.sqrt(3.0) / 4.0
NARROW = PI * 2.0 * PI * 4.0 * (9.0 - 10.0 * T10)
TRI_NARROW = TRI * 2.0 * PI * 4.0 * (11.0 - 10.0 * T10)
TRI_WIDE = TRI * 2.0 * PI * 4.0 * (11.0 + 10.0 * T10)
BLOCK = 16000.0
s = {}


def doc():
    return App.ActiveDocument


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def msg(p):
    return p.message.text() if p is not None else ""


def coil_panel():
    return pi.panel("CoilPanel")


def torus_panel():
    return pi.panel("TorusPanel")


def coil_shape():
    coils = [o for o in doc().Objects if getattr(o, "SciForgeType", "") == "Coil"]
    return coils[0].Shape if coils else None


def coil_z():
    shape = coil_shape()
    if shape is None or shape.isNull():
        return None
    box = shape.optimalBoundingBox(False, False)
    return round(box.ZMin, 3), round(box.ZMax, 3)


def above_plane():
    z = coil_z()
    # The coil rises 20 from the plane (its section reaches 1 mm or less past both ends);
    # the mirror image FreeCAD made of a narrowing coil went down to -21.
    return z is not None and -1.01 < z[0] < 0.0 and 20.0 < z[1] < 21.01


# == M1: a conical spring =========================================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("PrimQAMore")
    h.fit()
    pi.menu("Coil")


def m1_plane():
    pl.click_square("XY_Plane")  # where the XY square shows


def m1_centre():
    p = coil_panel()
    h.check("M1 placing on XY", p is not None and p.state == "place", p and p.state)
    pl.click_on_plane(V(0, 0, 0))


def m1_circle():
    pl.click_on_plane(V(10, 0, 0))


m1_circle.wait_ms = 2000


def m1_ready():
    p = coil_panel()
    h.check("M1 a coil d20", p is not None and near(p.diameter.value(), 20.0), p and p.state)
    h.check("M1 5 turns: 90 pi^2", near(vol(), 90.0 * PI * PI, 1e-5), vol())
    if p is not None:
        ui.choose(p.type, "Revolution and Pitch")


m1_ready.wait_ms = 1500


def m1_rev_pitch():
    p = coil_panel()
    if p is None:
        return
    h.check(
        "M1 Revolution and Pitch: Revolutions, Pitch and Angle, no Height",
        p.revolutions.widget.isVisible()
        and p.pitch.widget.isVisible()
        and p.angle.widget.isVisible()
        and not p.height.widget.isVisible(),
    )
    h.check(
        "M1 the same coil: 5 revolutions, pitch 4",
        near(p.revolutions.value(), 5.0) and near(p.pitch.value(), 4.0),
        (p.revolutions.value(), p.pitch.value()),
    )
    h.check("M1 still 90 pi^2", near(vol(), 90.0 * PI * PI, 1e-5), vol())
    ui.type_into(p.revolutions.widget, "4")


m1_rev_pitch.wait_ms = 1500


def m1_four():
    h.check("M1 4 turns: 72 pi^2", near(vol(), 72.0 * PI * PI, 1e-5), vol())
    p = coil_panel()
    if p is not None:
        ui.type_into(p.pitch.widget, "5")


m1_four.wait_ms = 1500


def m1_pitch():
    h.check("M1 pitch 5: still 72 pi^2", near(vol(), 72.0 * PI * PI, 1e-5), vol())
    h.check("M1 pitch 5: 20 high", coil_z() == (-1.0, 21.0), coil_z())
    p = coil_panel()
    if p is not None:
        ui.type_into(p.angle.widget, "-10")


m1_pitch.wait_ms = 1500


def m1_narrows():
    p = coil_panel()
    h.check("M1 no message", msg(p) == "", msg(p))
    h.check("M1 Angle -10: it still rises from the plane", above_plane(), coil_z())
    h.check(
        "M1 Angle -10: it narrows (pi 2 pi 4 (9 - 10 tan 10))",
        near(vol(), NARROW, 1e-4),
        (vol(), NARROW),
    )
    h.shot("m1-narrow")
    if p is not None:
        ui.type_into(p.angle.widget, "-60")


m1_narrows.wait_ms = 2500


def m1_too_steep():
    p = coil_panel()
    h.check("M1 -60 closes the coil: said", "narrows" in msg(p), msg(p))
    h.task_button("OK")


m1_too_steep.wait_ms = 1500


def m1_waits():
    p = coil_panel()
    h.check("M1 OK waits", p is not None)
    if p is not None:
        ui.type_into(p.angle.widget, "-10")


def m1_ok():
    p = coil_panel()
    h.check("M1 the message went", msg(p) == "", msg(p))
    h.check("M1 the narrowing coil again", near(vol(), NARROW, 1e-4), vol())
    h.task_button("OK")


m1_ok.wait_ms = 2500


def m1_done():
    h.check("M1 OK closed it", pi.no_dialog())
    h.check("M1 kept, above the plane", near(vol(), NARROW, 1e-4) and above_plane(), coil_z())
    s["narrow"] = vol()
    h.check("M1 timeline: Coil 1", ti.titles() == ["Coil 1"], ti.titles())
    h.check("M1 double-click Coil 1", ti.double_click("Coil 1"))


def m1_edit():
    p = coil_panel()
    h.check("M1 editing", p is not None and p.editing)
    if p is None:
        return
    shown = (
        p.type.currentText(),
        round(p.revolutions.value(), 6),
        round(p.pitch.value(), 6),
        round(p.angle.value(), 6),
    )
    h.check(
        "M1 the dialog shows the spring as left",
        shown == ("Revolution and Pitch", 4.0, 5.0, -10.0),
        shown,
    )
    ui.choose(p.section, "Triangular (Internal)")


m1_edit.wait_ms = 2000


def m1_triangle():
    p = coil_panel()
    if p is not None:
        ui.choose(p.section_position, "Outside")


m1_triangle.wait_ms = 2000


def m1_outside():
    p = coil_panel()
    h.check("M1 no message", msg(p) == "", msg(p))
    h.check(
        "M1 a triangle pointing in, outside the diameter",
        near(vol(), TRI_NARROW, 1e-4),
        (vol(), TRI_NARROW),
    )
    h.check("M1 still rising from the plane", above_plane(), coil_z())
    h.task_button("OK")


m1_outside.wait_ms = 1500


def m1_undo():
    h.check("M1 OK closed it", pi.no_dialog())
    s["tri"] = vol()
    h.press("z", QtCore.Qt.ControlModifier)


m1_undo.wait_ms = 1200


def m1_undone():
    h.check("M1 Ctrl+Z: the round section again", near(vol(), s["narrow"], 1e-6), vol())
    h.press("y", QtCore.Qt.ControlModifier)


m1_undone.wait_ms = 1500


def m1_redone():
    h.check("M1 Ctrl+Y: the triangle", near(vol(), s["tri"], 1e-6), vol())
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-prim-"), "primitives_qa_more.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("M1 saved", os.path.isfile(path), path)


def m1_close():
    App.closeDocument(doc().Name)


def m1_open():
    App.openDocument(s["path"])
    h.fit()


m1_open.wait_ms = 2500


def m1_reopened():
    h.check("M1 reopened: the same spring", near(vol(), s["tri"], 1e-6), (vol(), s["tri"]))
    doc().recompute()
    h.check("M1 a recompute keeps it", near(vol(), s["tri"], 1e-6), vol())
    h.check("M1 above the plane after reopening", above_plane(), coil_z())
    h.check("M1 double-click Coil 1 after reopening", ti.double_click("Coil 1"))


m1_reopened.wait_ms = 2000


def m1_reedit():
    p = coil_panel()
    h.check("M1 editing after reopening", p is not None and p.editing)
    if p is None:
        return
    shown = (
        p.section.currentText(),
        p.section_position.currentText(),
        round(p.angle.value(), 6),
    )
    h.check(
        "M1 remembered after reopening",
        shown == ("Triangular (Internal)", "Outside", -10.0),
        shown,
    )
    ui.type_into(p.angle.widget, "10")


m1_reedit.wait_ms = 2000


def m1_widens():
    h.check("M1 Angle 10: it widens", near(vol(), TRI_WIDE, 1e-4), (vol(), TRI_WIDE))
    h.check("M1 widening, still above the plane", above_plane(), coil_z())
    h.task_button("OK")


m1_widens.wait_ms = 2000


def m1_widened():
    h.check("M1 OK closed it", pi.no_dialog())
    s["coil"] = vol()
    h.check("M1 kept", near(s["coil"], TRI_WIDE, 1e-4), s["coil"])
    h.shot("m1")
    h.click_empty()
    pi.menu("Box")


# == M2: a ring groove in a block =================================================================
def m2_plane():
    pl.click_square("XY_Plane")  # where the XY square shows


def m2_corner1():
    p = pi.panel("BoxPanel")
    h.check("M2 placing the box", p is not None and p.state == "place", p and p.state)
    pl.click_on_plane(V(30, -20, 0))


def m2_corner2():
    pl.click_on_plane(V(70, 20, 0))


m2_corner2.wait_ms = 1500


def m2_height():
    p = pi.panel("BoxPanel")
    h.check(
        "M2 40 x 40", p is not None and near(p.length.value(), 40.0) and near(p.width.value(), 40.0)
    )
    if p is not None:
        h.check(
            "M2 away from the spring: New Body",
            p.operation.currentText() == "New Body",
            p.operation.currentText(),
        )
        ui.type_into(p.height.widget, "10")


m2_height.wait_ms = 1500


def m2_box_ok():
    h.check("M2 the block", near(vol() - s["coil"], BLOCK, 1e-6), vol() - s["coil"])
    h.task_button("OK")


m2_box_ok.wait_ms = 1000


def m2_top():
    h.check("M2 OK closed it", pi.no_dialog())
    h.fit()
    h.click(V(60, 10, 10))


def m2_torus():
    h.check("M2 the top face is selected", bool(Gui.Selection.getSelectionEx()))
    pi.menu("Torus")


def m2_centre():
    p = torus_panel()
    h.check("M2 the face is taken at once", p is not None and p.state == "place", p and p.state)
    pl.click_on_plane(V(50, 0, 10))


def m2_inner():
    pl.click_on_plane(V(58, 0, 10))


m2_inner.wait_ms = 2000


def m2_ready():
    p = torus_panel()
    if p is None:
        h.check("M2 a torus", False)
        return
    shown = (
        round(p.inner.value(), 6),
        round(p.tube.value(), 6),
        p.position.currentText(),
        p.operation.currentText(),
    )
    h.check(
        "M2 inner d16, d5 on centre, half in the block: Join",
        shown == (16.0, 5.0, "On Center", "Join"),
        shown,
    )
    h.check(
        "M2 + 50 pi^2", near(vol() - s["coil"], BLOCK + 50.0 * PI * PI, 1e-6), vol() - s["coil"]
    )
    ui.type_into(p.tube.widget, "4")


m2_ready.wait_ms = 2000


def m2_four():
    h.check(
        "M2 d4: + 32 pi^2", near(vol() - s["coil"], BLOCK + 32.0 * PI * PI, 1e-6), vol() - s["coil"]
    )
    p = torus_panel()
    if p is not None:
        ui.choose(p.position, "Inside")


m2_four.wait_ms = 1500


def m2_inside():
    h.check(
        "M2 Inside (R 6): + 24 pi^2",
        near(vol() - s["coil"], BLOCK + 24.0 * PI * PI, 1e-6),
        vol() - s["coil"],
    )
    p = torus_panel()
    if p is not None:
        ui.choose(p.operation, "Cut")


m2_inside.wait_ms = 1500


def m2_cut():
    p = torus_panel()
    h.check(
        "M2 Cut: a groove, - 24 pi^2",
        near(vol() - s["coil"], BLOCK - 24.0 * PI * PI, 1e-6),
        vol() - s["coil"],
    )
    handle = p.handles.get("torus_diameter") if p is not None else None
    h.check("M2 a torus diameter arrow", handle is not None, p and list(p.handles))
    if handle is not None:
        pi.drag_handle(handle, 3.0)


m2_cut.wait_ms = 1500


def m2_dragged():
    p = torus_panel()
    if p is None:
        return
    t = p.tube.value()
    h.check("M2 dragged to about 3", abs(t - 3.0) < 0.06, t)
    groove = PI * PI * (8.0 - t / 2.0) * (t / 2.0) ** 2
    h.check(
        "M2 the groove follows the field",
        near(vol() - s["coil"], BLOCK - groove, 1e-6),
        (vol() - s["coil"], BLOCK - groove),
    )
    ui.type_into(p.tube.widget, "4")


m2_dragged.wait_ms = 2000


def m2_ok():
    h.check(
        "M2 4 again: - 24 pi^2",
        near(vol() - s["coil"], BLOCK - 24.0 * PI * PI, 1e-6),
        vol() - s["coil"],
    )
    h.task_button("OK")


m2_ok.wait_ms = 1500


def m2_edit():
    h.check("M2 OK closed it", pi.no_dialog())
    h.check("M2 timeline", ti.titles() == ["Coil 1", "Box 1", "Torus 1"], ti.titles())
    h.check("M2 double-click Torus 1", ti.double_click("Torus 1"))


def m2_edit_shows():
    p = torus_panel()
    h.check("M2 editing", p is not None and p.editing)
    if p is None:
        return
    shown = (
        round(p.inner.value(), 6),
        round(p.tube.value(), 6),
        p.position.currentText(),
        p.operation.currentText(),
    )
    h.check("M2 it shows Inside, 4, Cut", shown == (16.0, 4.0, "Inside", "Cut"), shown)
    ui.choose(p.position, "Outside")


m2_edit_shows.wait_ms = 2000


def m2_outside():
    h.check(
        "M2 Outside (R 10): - 40 pi^2",
        near(vol() - s["coil"], BLOCK - 40.0 * PI * PI, 1e-6),
        vol() - s["coil"],
    )
    h.task_button("OK")


m2_outside.wait_ms = 1500


def m2_undo():
    h.check("M2 OK closed it", pi.no_dialog())
    h.press("z", QtCore.Qt.ControlModifier)


m2_undo.wait_ms = 1200


def m2_undone():
    h.check(
        "M2 Ctrl+Z: Inside again",
        near(vol() - s["coil"], BLOCK - 24.0 * PI * PI, 1e-6),
        vol() - s["coil"],
    )
    h.press("y", QtCore.Qt.ControlModifier)


m2_undone.wait_ms = 1500


def m2_redone():
    h.check(
        "M2 Ctrl+Y: Outside",
        near(vol() - s["coil"], BLOCK - 40.0 * PI * PI, 1e-6),
        vol() - s["coil"],
    )
    s["part"] = vol()
    h.shot("m2")
    h.click_empty()
    pi.menu("Pipe")


# == M3: another command's key with the Pipe dialog open ==========================================
def m3_edge():
    p = pi.pipe_panel()
    h.check("M3 Pipe waits for a path", p is not None and not p.path)
    h.click_edge(V(50, -20, 10))


def m3_path():
    p = pi.pipe_panel()
    h.check("M3 the edge", p is not None and len(p.path) == 1, p and p.path)
    if p is not None:
        h.check(
            "M3 mostly outside: Join",
            p.operation.currentText() == "Join",
            p.operation.currentText(),
        )
    h.check("M3 + 30 pi", near(vol(), s["part"] + 30.0 * PI, 1e-6), (vol(), s["part"]))
    h.press("e")


m3_path.wait_ms = 2000


def m3_extrude():
    from sciforge import extrude_ui

    h.check("M3 E: the pipe dialog closed", pi.pipe_panel() is None)
    ext = extrude_ui.ExtrudePanel.last
    h.check("M3 Extrude started", ext is not None and not ext._closed)
    h.check("M3 the pipe is kept", "Pipe 1" in ti.titles(), ti.titles())
    h.check("M3 + 30 pi kept", near(vol(), s["part"] + 30.0 * PI, 1e-6), vol())
    h.press(QtCore.Qt.Key_Escape)


m3_extrude.wait_ms = 2000


def m3_esc():
    h.check("M3 Esc closed Extrude", pi.no_dialog())
    h.check("M3 the pipe stays", near(vol(), s["part"] + 30.0 * PI, 1e-6), vol())
    h.check("M3 one step for it", ti.titles().count("Pipe 1") == 1, ti.titles())
    h.shot("m3")


m3_esc.wait_ms = 1000


h.run(
    "primitives_qa_more",
    [
        new_design,
        m1_plane,
        m1_centre,
        m1_circle,
        m1_ready,
        m1_rev_pitch,
        m1_four,
        m1_pitch,
        m1_narrows,
        m1_too_steep,
        m1_waits,
        m1_ok,
        m1_done,
        m1_edit,
        m1_triangle,
        m1_outside,
        m1_undo,
        m1_undone,
        m1_redone,
        m1_close,
        m1_open,
        m1_reopened,
        m1_reedit,
        m1_widens,
        m1_widened,
        m2_plane,
        m2_corner1,
        m2_corner2,
        m2_height,
        m2_box_ok,
        m2_top,
        m2_torus,
        m2_centre,
        m2_inner,
        m2_ready,
        m2_four,
        m2_inside,
        m2_cut,
        m2_dragged,
        m2_ok,
        m2_edit,
        m2_edit_shows,
        m2_outside,
        m2_undo,
        m2_undone,
        m2_redone,
        m3_edge,
        m3_path,
        m3_extrude,
        m3_esc,
    ],
)
