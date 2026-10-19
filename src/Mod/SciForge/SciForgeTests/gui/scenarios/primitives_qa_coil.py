# SPDX-License-Identifier: LGPL-2.1-or-later
"""Primitives QA, Coil like a Fusion user making a thread on a rod (only real input).

C1. A rod: Cylinder d20 on XY, Height 30. Its top face selected, Coil: the centre snaps
    onto the rod's axis, a point on its edge gives d20. The first coil rises out of the
    top (it touches the rod: Join). The height arrow dragged down into the rod: Fusion
    turns it into a Cut (a groove). Type Height and Pitch; Pitch 1 typed: the turns would
    touch, said, OK waits; Pitch 4. Section Triangular (External) (Inside the diameter:
    its tip on the rod's surface); OK. Timeline: one "Coil 1", no sketch.
C2. Edit Coil 1 twice from the timeline: the dialog shows what was left (type, section,
    pitch, a negative height); Rotation turned to Counterclockwise, OK; then an edit with
    a bigger section cancelled with Esc: unchanged. Ctrl+Z (Clockwise again), Ctrl+Y.
C3. OK after only the centre click: the dialog stays and says to click the circle; Esc
    leaves nothing. A Coil typed fully (centre clicked, 8 over the view, Enter) beside the
    rod: a New Body; Revolutions 0 typed: said, OK waits; 3; OK. Deleted in the timeline:
    its hidden section goes with it.

Hand-derived volumes (pi = PI): rod r10 h30 = 3000 pi. Coil groove: Pappus, the section
area x 2 pi r_c x turns; the first quarter turn starts half above the top face (the coil
starts on the plane), so the groove removes a little less than that (bounded checks).
  circle d2 inside (r_c 9), 5 turns = 90 pi^2; triangle (External, circumscribed d2),
  Inside (r_c 9, its centroid): area 3 sqrt(3) / 4, 5 turns: 3 sqrt(3) / 4 x 18 pi x 5
  new coil d8: circle section nice(0.8) = 1 inside (r_c 3.5), 3 turns:
  pi / 4 x 2 pi 3.5 x 3 = 5.25 pi^2
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
PI = math.pi
ROD = 3000.0 * PI
TRI = 3.0 * math.sqrt(3.0) / 4.0
s = {}


def doc():
    return App.ActiveDocument


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def msg(p):
    return p.message.text() if p is not None else ""


def panel():
    return pi.panel("CoilPanel")


def coils():
    return [o for o in doc().Objects if getattr(o, "SciForgeType", "") == "Coil"]


def sections():
    return [o for o in doc().Objects if getattr(o, "SciForgeRole", "") == "CoilSection"]


def keys_to_focus(text, enter=False):
    target = QtWidgets.QApplication.focusWidget() or h.gl_widget()
    QtTest.QTest.keyClicks(target, text)
    if enter:
        target = QtWidgets.QApplication.focusWidget() or target
        QtTest.QTest.keyClick(target, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()


# == C1: a thread groove on a rod ===================================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("PrimQACoil")
    h.fit()
    pi.menu("Cylinder")


def c1_rod_plane():
    pl.click_square("XY_Plane")  # where the XY square shows


def c1_rod_centre():
    pl.click_on_plane(V(0, 0, 0))


def c1_rod_circle():
    pl.click_on_plane(V(10, 0, 0))


c1_rod_circle.wait_ms = 1500


def c1_rod_height():
    p = pi.panel("CylinderPanel")
    if p is not None:
        ui.type_into(p.height.widget, "30")


c1_rod_height.wait_ms = 1500


def c1_rod_ok():
    h.task_button("OK")


def c1_select_top():
    h.check("C1 the rod", near(vol(), ROD), vol())
    h.fit()
    pl.click_on_plane(V(0, -5, 30))


def c1_coil():
    h.check("C1 the top face is selected", bool(Gui.Selection.getSelectionEx()))
    pi.menu("Coil")


def c1_centre():
    p = panel()
    h.check("C1 the face is taken", p is not None and p.state == "place", p and p.state)
    h.click(V(0.3, 0.2, 30))  # a hand near the axis: it snaps onto the circle's centre


def c1_edge():
    pl.click_on_plane(V(10, 0, 30))


c1_edge.wait_ms = 2500


def c1_first():
    p = panel()
    c = p.target if p is not None else None
    h.check("C1 a coil", c is not None and p.state == "ready", p and p.state)
    if p is None:
        return
    h.check(
        "C1 centred on the rod's axis",
        near(p.options["x"], 0.0) and near(p.options["y"], 0.0),
        (p.options["x"], p.options["y"]),
    )
    h.check("C1 d20", near(p.diameter.value(), 20.0), p.diameter.value())
    h.check(
        "C1 rising out of the top: Join",
        p.operation.currentText() == "Join",
        p.operation.currentText(),
    )
    handle = p.handles.get("height")
    h.check("C1 a height arrow", handle is not None, list(p.handles))
    if handle is not None:
        pi.drag_handle(handle, -20.0)


c1_first.wait_ms = 2500


def c1_cut():
    p = panel()
    if p is None:
        return
    h.check(
        "C1 dragged into the rod: Cut by itself",
        p.operation.currentText() == "Cut",
        p.operation.currentText(),
    )
    h.check("C1 height -20", near(p.height.value(), -20.0, 1e-3), p.height.value())
    groove = 90.0 * PI * PI
    h.check("C1 a groove of nearly 90 pi^2", ROD - groove < vol() < ROD - 0.95 * groove, vol())
    ui.choose(p.type, "Height and Pitch")


c1_cut.wait_ms = 2500


def c1_type():
    p = panel()
    if p is None:
        return
    h.check("C1 Height and Pitch shows the pitch", p.pitch.widget.isVisible())
    h.check(
        "C1 the same coil described another way (pitch 4)",
        near(p.pitch.value(), 4.0),
        p.pitch.value(),
    )
    ui.type_into(p.pitch.widget, "1")


c1_type.wait_ms = 2500


def c1_touching():
    p = panel()
    h.check("C1 turns that touch are said", "touch" in msg(p), msg(p))
    h.task_button("OK")


def c1_touching_waits():
    p = panel()
    h.check("C1 OK waits", p is not None)
    if p is not None:
        ui.type_into(p.pitch.widget, "4")


c1_touching_waits.wait_ms = 2500


def c1_section():
    p = panel()
    h.check("C1 the message went", msg(p) == "", msg(p))
    if p is not None:
        ui.choose(p.section, "Triangular (External)")


c1_section.wait_ms = 2500


def c1_ok():
    p = panel()
    groove = TRI * 2.0 * PI * 9.0 * 5.0
    h.check("C1 a triangular groove", ROD - groove < vol() < ROD - 0.9 * groove, vol())
    h.check("C1 no message", msg(p) == "", msg(p))
    s["thread"] = vol()
    h.task_button("OK")


def c1_done():
    h.check("C1 OK closed it", pi.no_dialog())
    h.check("C1 kept", near(vol(), s["thread"]), vol())
    h.check("C1 timeline: Cylinder 1, Coil 1", ti.titles() == ["Cylinder 1", "Coil 1"], ti.titles())
    h.check("C1 no sketch", not pi.steps_of("Sketcher"))
    h.shot("c1")


# == C2: edit twice, Esc, undo / redo ===========================================================
def c2_edit():
    h.check("C2 double-click Coil 1", ti.double_click("Coil 1"), ti.titles())


def c2_shows():
    p = panel()
    h.check("C2 editing", p is not None and p.editing)
    if p is None:
        return
    shown = (
        p.type.currentText(),
        p.section.currentText(),
        p.section_position.currentText(),
        round(p.height.value(), 6),
        round(p.pitch.value(), 6),
        p.operation.currentText(),
        p.rotation.text(),
    )
    h.check(
        "C2 the dialog shows the coil as left",
        shown
        == ("Height and Pitch", "Triangular (External)", "Inside", -20.0, 4.0, "Cut", "Clockwise"),
        shown,
    )
    ui.click(p.rotation)


c2_shows.wait_ms = 2500


def c2_ccw():
    p = panel()
    h.check(
        "C2 Counterclockwise",
        p is not None and p.rotation.text() == "Counterclockwise",
        p and p.rotation.text(),
    )
    c = p.target if p is not None else None
    h.check("C2 the coil turns the other way", c is not None and c.LeftHanded, c and c.LeftHanded)
    h.task_button("OK")


c2_ccw.wait_ms = 1500


def c2_edit_again():
    h.check("C2 OK closed it", pi.no_dialog())
    h.check("C2 same groove volume", near(vol(), s["thread"], 1e-5), vol())
    h.check("C2 still one step", ti.titles() == ["Cylinder 1", "Coil 1"], ti.titles())
    h.check("C2 double-click Coil 1 again", ti.double_click("Coil 1"))


def c2_bigger():
    p = panel()
    h.check(
        "C2 editing again (Counterclockwise kept)",
        p is not None and p.rotation.text() == "Counterclockwise",
        p and p.rotation.text(),
    )
    if p is not None:
        ui.type_into(p.section_size.widget, "3")


c2_bigger.wait_ms = 2500


def c2_esc():
    h.check("C2 the preview changed", not near(vol(), s["thread"], 1e-5), vol())
    h.press(QtCore.Qt.Key_Escape)


c2_esc.wait_ms = 1500


def c2_unchanged():
    h.check("C2 Esc closed it", pi.no_dialog())
    h.check("C2 Esc: unchanged", near(vol(), s["thread"], 1e-5), vol())
    c = coils()[0] if coils() else None
    h.check("C2 still Counterclockwise", c is not None and c.LeftHanded)
    h.press("z", QtCore.Qt.ControlModifier)


c2_unchanged.wait_ms = 1200


def c2_undone():
    c = coils()[0] if coils() else None
    h.check("C2 Ctrl+Z: Clockwise again", c is not None and not c.LeftHanded, c and c.LeftHanded)
    h.press("y", QtCore.Qt.ControlModifier)


c2_undone.wait_ms = 1500


def c2_redone():
    c = coils()[0] if coils() else None
    h.check("C2 Ctrl+Y: Counterclockwise", c is not None and c.LeftHanded, c and c.LeftHanded)
    h.check("C2 the groove", near(vol(), s["thread"], 1e-5), vol())
    h.click_empty()
    pi.menu("Coil")


# == C3: OK too early, typed sizes, wrong values, delete ========================================
def c3_plane():
    pl.click_square("XY_Plane")  # where the XY square shows


def c3_centre():
    p = panel()
    h.check("C3 placing on XY", p is not None and p.state == "place", p and p.state)
    pl.click_on_plane(V(30, 0, 0))


def c3_ok_early():
    h.task_button("OK")


def c3_says():
    p = panel()
    h.check("C3 OK after the centre only: the dialog stays", p is not None)
    h.check("C3 it says to click the circle", "circle" in msg(p).lower(), msg(p))
    h.press(QtCore.Qt.Key_Escape)


c3_says.wait_ms = 1200


def c3_nothing():
    h.check("C3 Esc closed it", pi.no_dialog())
    h.check(
        "C3 nothing left",
        len(coils()) == 1 and len(sections()) == 1,
        ([o.Name for o in coils()], [o.Name for o in sections()]),
    )
    h.check("C3 the rod as it was", near(vol(), s["thread"], 1e-5), vol())
    pi.menu("Coil")


def c3_plane2():
    pl.click_square("XY_Plane")  # where the XY square shows


def c3_centre2():
    pl.click_on_plane(V(30, 0, 0))


def c3_typed():
    pi.hover(V(33, 0, 0))
    h.press("8")


def c3_enter():
    keys_to_focus("", enter=True)


c3_enter.wait_ms = 2500


def c3_placed():
    p = panel()
    h.check(
        "C3 placed from the typed diameter", p is not None and p.state == "ready", p and p.state
    )
    if p is None:
        return
    h.check("C3 d8", near(p.diameter.value(), 8.0), p.diameter.value())
    h.check(
        "C3 beside the rod: New Body",
        p.operation.currentText() == "New Body",
        p.operation.currentText(),
    )
    ui.type_into(p.revolutions.widget, "0")


c3_placed.wait_ms = 2500


def c3_zero():
    p = panel()
    h.check("C3 Revolutions 0 is said", "Revolutions" in msg(p), msg(p))
    h.task_button("OK")


def c3_zero_waits():
    p = panel()
    h.check("C3 OK waits", p is not None)
    if p is not None:
        ui.type_into(p.revolutions.widget, "3")


c3_zero_waits.wait_ms = 2500


def c3_ok():
    p = panel()
    h.check("C3 the message went", msg(p) == "", msg(p))
    small = 5.25 * PI * PI
    h.check(
        "C3 + a small coil", near(vol(), s["thread"] + small, 1e-5), (vol(), s["thread"] + small)
    )
    h.task_button("OK")


c3_ok.wait_ms = 1500


def c3_delete():
    h.check("C3 two coils", len(coils()) == 2 and len(sections()) == 2)
    ti.menu("Coil 2", "Delete")


c3_delete.wait_ms = 1500


def c3_deleted():
    h.check(
        "C3 Coil 2 gone with its section",
        len(coils()) == 1 and len(sections()) == 1,
        ([o.Name for o in coils()], [o.Name for o in sections()]),
    )
    h.check("C3 the rod with its thread", near(vol(), s["thread"], 1e-5), vol())
    h.shot("c3")


h.run(
    "primitives_qa_coil",
    [
        new_design,
        c1_rod_plane,
        c1_rod_centre,
        c1_rod_circle,
        c1_rod_height,
        c1_rod_ok,
        c1_select_top,
        c1_coil,
        c1_centre,
        c1_edge,
        c1_first,
        c1_cut,
        c1_type,
        c1_touching,
        c1_touching_waits,
        c1_section,
        c1_ok,
        c1_done,
        c2_edit,
        c2_shows,
        c2_ccw,
        c2_edit_again,
        c2_bigger,
        c2_esc,
        c2_unchanged,
        c2_undone,
        c2_redone,
        c3_plane,
        c3_centre,
        c3_ok_early,
        c3_says,
        c3_nothing,
        c3_plane2,
        c3_centre2,
        c3_typed,
        c3_enter,
        c3_placed,
        c3_zero,
        c3_zero_waits,
        c3_ok,
        c3_delete,
        c3_deleted,
    ],
)
