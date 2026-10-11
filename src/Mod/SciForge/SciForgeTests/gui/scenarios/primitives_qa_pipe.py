# SPDX-License-Identifier: LGPL-2.1-or-later
"""Primitives QA, Pipe along the edges of a part (only real input).

Q1. A new design with nothing in it: Pipe says to draw a path first (next to the mouse, no
    dialog left open, no pop-up).
Q2. A 40 x 30 x 10 block. Pipe with nothing selected: OK says to pick the path, the dialog
    stays. The top front edge clicked: a pipe d2 along it (a quarter inside: Join).
    Cut. Hollow with a wall of 1 (as thick as the radius): said, OK waits; 0.5: a hollow
    groove. The top right edge clicked too: the pipe turns the corner. Clicked again:
    dropped. 5 typed with the mouse over the 3D view: Section Size 5 (Fusion's box next
    to the handle; FreeCAD's key 5 would have turned the view). OK. Picking or dropping
    curves keeps the section size and the typed wall (they were worked out again from
    the path's length: the wall 0.5 became 0.2), and the corner is mitred like Fusion's
    (FreeCAD's default corner failed: "A fatal error occurred when making the pipe").
Q3. Extrude 1 edited to 20: the pipe follows its edge up (the groove stays on the top
    edge). Ctrl+Z.
Q4. Pipe 1 edited from the timeline: the path box shows 1 selected; its x clears it: said,
    OK waits; the edge clicked again; Triangular; OK. Ctrl+Z, Ctrl+Y.

Hand-derived volumes (pi = PI): block 12000; along a 40 mm edge a d2 pipe is 40 pi, a
quarter of it inside: Join adds 30 pi, Cut takes 10 pi; hollow d2 wall 0.5: a ring of
pi (1 - 0.25) = 0.75 pi, a quarter of it x 40 = 7.5 pi; d5 wall 0.5: pi (6.25 - 4) x 40 / 4
= 22.5 pi; block 20 high: 24000. Mitred corner (front 40 + right 30, the cut on the
bisecting plane): each leg's quarter minus the wedge the mitre takes off, the integral of
the distance across the leg over the quarter ring = (1^3 - 0.5^3) / 3, twice:
0.75 pi / 4 x 70 - 7 / 12 = 13.125 pi - 7 / 12. Triangular (circumscribed d5, a corner up) hollow:
area 3 sqrt(3) / 16 (5^2 - 3^2) = 3 sqrt(3); the part inside the block is bounded.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
PI = math.pi
FRONT = V(20, 0, 10)
RIGHT = V(40, 15, 10)
s = {}


def doc():
    return App.ActiveDocument


def near(a, b_, tol=1e-6):
    return pi.near(a, b_, tol)


def vol():
    return pi.total_volume()


def msg(p):
    return p.message.text() if p is not None else ""


def panel():
    return pi.pipe_panel()


def helpers():
    return [o for o in doc().Objects if getattr(o, "SciForgeRole", "").startswith("Pipe")]


def extrude_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


# == Q1: Pipe in an empty design ==================================================================
def q1_empty():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("PrimQAPipeEmpty")
    h.fit()
    pi.menu("Pipe")


def q1_told():
    h.check("Q1 no dialog left open", pi.no_dialog())
    h.check("Q1 no pop-up", not h.popups(), h.popups())
    App.closeDocument(doc().Name)


# == Q2: along the block's edges ====================================================================
def q2_pipe():
    h.click_empty()
    pi.menu("Pipe")


def q2_ok_nothing():
    p = panel()
    h.check("Q2 Pipe waits for a path", p is not None and not p.path, p and p.path)
    h.task_button("OK")


def q2_said():
    p = panel()
    h.check("Q2 OK with nothing picked keeps the dialog", p is not None)
    h.check("Q2 it says to pick the path", "path" in msg(p).lower(), msg(p))
    h.check("Q2 no pop-up", not h.popups(), h.popups())
    h.click_edge(FRONT)


q2_said.wait_ms = 1000


def q2_front():
    p = panel()
    h.check("Q2 one edge", p is not None and len(p.path) == 1, p and p.path)
    if p is None:
        return
    h.check("Q2 a d2 section", near(p.size.value(), 2.0), p.size.value())
    h.check(
        "Q2 a quarter inside: Join", p.operation.currentText() == "Join", p.operation.currentText()
    )
    h.check("Q2 + 30 pi", near(vol(), 12000.0 + 30.0 * PI, 1e-5), vol())
    ui.choose(p.operation, "Cut")


q2_front.wait_ms = 2000


def q2_hollow():
    h.check("Q2 Cut: - 10 pi", near(vol(), 12000.0 - 10.0 * PI, 1e-5), vol())
    p = panel()
    if p is not None:
        pi.tick(p.hollow)


q2_hollow.wait_ms = 2000


def q2_wall():
    p = panel()
    h.check("Q2 the wall field shows", p is not None and p.thickness.widget.isVisible())
    if p is not None:
        ui.type_into(p.thickness.widget, "1")


q2_wall.wait_ms = 2000


def q2_wall_said():
    p = panel()
    h.check("Q2 a wall as thick as the radius is said", "thick" in msg(p), msg(p))
    h.task_button("OK")


def q2_wall_waits():
    p = panel()
    h.check("Q2 OK waits", p is not None)
    if p is not None:
        ui.type_into(p.thickness.widget, "0.5")


q2_wall_waits.wait_ms = 2000


def q2_hollow_cut():
    p = panel()
    h.check("Q2 the message went", msg(p) == "", msg(p))
    h.check("Q2 a hollow groove: - 7.5 pi", near(vol(), 12000.0 - 7.5 * PI, 1e-5), vol())
    h.click_edge(RIGHT)


q2_hollow_cut.wait_ms = 2000


def q2_corner():
    p = panel()
    h.check("Q2 two edges", p is not None and len(p.path) == 2, p and p.path)
    h.check("Q2 no message", msg(p) == "", msg(p))
    h.check("Q2 the section size stays d2", near(p.size.value(), 2.0), p and p.size.value())
    h.check("Q2 the wall stays 0.5", near(p.thickness.value(), 0.5), p and p.thickness.value())
    h.check(
        "Q2 the groove turns the corner, mitred: - (13.125 pi - 7 / 12)",
        near(vol(), 12000.0 - 13.125 * PI + 7.0 / 12.0, 1e-5),
        vol(),
    )
    h.click_edge(RIGHT)


q2_corner.wait_ms = 2500


def q2_dropped():
    p = panel()
    h.check("Q2 clicked again: dropped", p is not None and len(p.path) == 1, p and p.path)
    h.check("Q2 back to the front groove", near(vol(), 12000.0 - 7.5 * PI, 1e-5), vol())
    pi.hover(V(20, -10, 10))
    s["camera"] = tuple(round(q, 6) for q in h.view().getCameraOrientation().Q)
    h.press("5")


q2_dropped.wait_ms = 2500


def q2_size_typed():
    p = panel()
    camera = tuple(round(q, 6) for q in h.view().getCameraOrientation().Q)
    h.check("Q2 the view did not turn (FreeCAD's key 5)", camera == s["camera"])
    h.check(
        "Q2 5 went into Section Size",
        p is not None and near(p.size.value(), 5.0),
        p and p.size.value(),
    )


q2_size_typed.wait_ms = 2500


def q2_ok():
    h.check("Q2 a d5 hollow groove: - 22.5 pi", near(vol(), 12000.0 - 22.5 * PI, 1e-5), vol())
    h.task_button("OK")


q2_ok.wait_ms = 1500


def q2_kept():
    h.check("Q2 OK closed it", pi.no_dialog())
    h.check("Q2 kept", near(vol(), 12000.0 - 22.5 * PI, 1e-5), vol())
    h.check("Q2 timeline", ti.titles()[-1:] == ["Pipe 1"], ti.titles())
    h.shot("q2")


# == Q3: the block under the pipe changes ========================================================
def q3_edit_block():
    h.check("Q3 double-click Extrude 1", ti.double_click("Extrude 1"), ti.titles())


def q3_twenty():
    p = extrude_panel()
    h.check("Q3 editing Extrude 1", p is not None)
    if p is not None:
        ui.type_into(p.distance.widget, "20")


q3_twenty.wait_ms = 1500


def q3_ok():
    h.task_button("OK")


q3_ok.wait_ms = 2500


def q3_followed():
    h.check("Q3 the edit closed", pi.no_dialog())
    h.check("Q3 the groove follows its edge up", near(vol(), 24000.0 - 22.5 * PI, 1e-5), vol())
    pipe = ti.obj("Pipe 1")
    h.check(
        "Q3 Pipe 1 fine",
        pipe is not None and "Invalid" not in list(pipe.State),
        pipe and list(pipe.State),
    )
    h.fit()
    h.shot("q3")
    h.press("z", QtCore.Qt.ControlModifier)


q3_followed.wait_ms = 1500


def q3_undone():
    h.check("Q3 Ctrl+Z: 10 high again", near(vol(), 12000.0 - 22.5 * PI, 1e-5), vol())
    h.fit()


# == Q4: edit the pipe, clear its path, pick again ===============================================
def q4_edit():
    h.check("Q4 double-click Pipe 1", ti.double_click("Pipe 1"), ti.titles())


def q4_shows():
    p = panel()
    h.check("Q4 editing", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "Q4 the path box shows the edge",
        p.path_field.button.text() == "1 selected",
        p.path_field.button.text(),
    )
    h.check(
        "Q4 hollow, d5, wall 0.5, Cut",
        p.hollow.isChecked()
        and near(p.size.value(), 5.0)
        and near(p.thickness.value(), 0.5)
        and p.operation.currentText() == "Cut",
        (p.hollow.isChecked(), p.size.value(), p.thickness.value(), p.operation.currentText()),
    )
    ui.click(p.path_field.clear)


q4_shows.wait_ms = 2000


def q4_cleared():
    p = panel()
    h.check("Q4 cleared: said", p is not None and "curve" in msg(p).lower(), msg(p))
    h.task_button("OK")


def q4_waits():
    p = panel()
    h.check("Q4 OK waits for a path", p is not None)
    h.fit()
    h.click_edge(FRONT)


q4_waits.wait_ms = 1500


def q4_again():
    p = panel()
    h.check("Q4 the edge again", p is not None and len(p.path) == 1, p and p.path)
    h.check("Q4 the message went", msg(p) == "", msg(p))
    if p is not None:
        ui.choose(p.section, "Triangular")


q4_again.wait_ms = 2000


def q4_ok():
    p = panel()
    h.check(
        "Q4 a triangular groove",
        p is not None and vol() < 12000.0 and msg(p) == "",
        (vol(), msg(p)),
    )
    s["tri"] = vol()
    h.task_button("OK")


q4_ok.wait_ms = 1500


def q4_done():
    h.check("Q4 OK closed it", pi.no_dialog())
    h.check("Q4 still one Pipe 1", ti.titles().count("Pipe 1") == 1, ti.titles())
    h.check("Q4 two hidden helpers", len(helpers()) == 2, [o.Name for o in helpers()])
    h.press("z", QtCore.Qt.ControlModifier)


q4_done.wait_ms = 1200


def q4_undone():
    h.check("Q4 Ctrl+Z: the round groove", near(vol(), 12000.0 - 22.5 * PI, 1e-5), vol())
    h.press("y", QtCore.Qt.ControlModifier)


q4_undone.wait_ms = 1500


def q4_redone():
    h.check("Q4 Ctrl+Y: triangular", near(vol(), s["tri"], 1e-6), vol())
    h.shot("q4")


h.run(
    "primitives_qa_pipe",
    [q1_empty, q1_told]
    + b.box_steps("PrimQAPipe", height=10)
    + [
        q2_pipe,
        q2_ok_nothing,
        q2_said,
        q2_front,
        q2_hollow,
        q2_wall,
        q2_wall_said,
        q2_wall_waits,
        q2_hollow_cut,
        q2_corner,
        q2_dropped,
        q2_size_typed,
        q2_ok,
        q2_kept,
        q3_edit_block,
        q3_twenty,
        q3_ok,
        q3_followed,
        q3_undone,
        q4_edit,
        q4_shows,
        q4_cleared,
        q4_waits,
        q4_again,
        q4_ok,
        q4_done,
        q4_undone,
        q4_redone,
    ],
)
