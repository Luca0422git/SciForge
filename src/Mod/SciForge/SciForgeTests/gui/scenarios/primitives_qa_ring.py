# SPDX-License-Identifier: LGPL-2.1-or-later
"""Primitives QA, Pipe round a closed sketch circle (a ring), only real input (the sketch's
circle is added like harness.draw_circle does; sketching has its own scenarios).

R1. A user parameter r = 10 (Change Parameters made it). Create Sketch on XY: a circle on
    the origin whose radius is r; Finish Sketch. Pipe: the circle clicked, then Esc in the
    middle of the pick: nothing is left (no pipe, no hidden helper, the sketch still shown).
R2. Pipe again, the circle clicked: a ring, the first solid (New Body). Section Size 2;
    Distance 0.5 (half the ring); Hollow with the wall of 0.5; OK: the sketch is hidden
    (the pipe uses it). Ctrl+Z: no pipe, the sketch shown again; Ctrl+Y.
R3. r = 15 in Change Parameters: the ring follows the circle. Pipe 1 edited from the
    timeline (the sketch shows while editing): Distance 1 (the whole ring, still hollow:
    FreeCAD's pipe made a closed hollow ring solid), Square; Esc: as it was, the sketch
    hidden again.
R4. Saved to a temporary file, closed, reopened: the same ring; edited: Section Size 3;
    OK.
R5. Pipe 1 deleted in the timeline: its hidden helpers go with it (the path helper stayed
    behind before: the section helper used it); Ctrl+Z brings the ring back.

Hand-derived volumes (Pappus: section area x 2 pi x the radius of the circle its centre of
area runs on, times the part of the ring; pi = PI):
  circle d2 round r 10: pi x 2 pi 10 = 20 pi^2; half: 10 pi^2; hollow wall 0.5: a ring of
  pi (1 - 0.25) = 0.75 pi: 7.5 pi^2. Round r 15: 11.25 pi^2; the whole ring: 22.5 pi^2;
  a square in a circle d2 (side sqrt 2, area 2) with a wall 0.5 (inner side sqrt 2 - 1):
  2 sqrt 2 - 1, x 2 pi 15 = 30 pi (2 sqrt 2 - 1). Circle d3, wall 0.5: pi (2.25 - 1) =
  1.25 pi, half the ring round r 15: 18.75 pi^2.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
PI = math.pi
ON_CIRCLE = V(10.0 * math.cos(-PI / 4.0), 10.0 * math.sin(-PI / 4.0), 0)  # nearest the eye
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
    return pi.pipe_panel()


def pipes():
    return [o for o in doc().Objects if getattr(o, "SciForgeType", "") == "Pipe"]


def helpers():
    return [o for o in doc().Objects if getattr(o, "SciForgeRole", "").startswith("Pipe")]


def sketch():
    found = [o for o in doc().Objects if o.TypeId == "Sketcher::SketchObject"]
    return found[0] if found else None


def sketch_shown():
    sk = sketch()
    return sk is not None and bool(sk.ViewObject.Visibility)


# == R1: the circle, Esc in the middle of the pick ================================================
def new_design():
    from sciforge import parameters

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("PrimQARing")
    parameters.add_user(App.ActiveDocument, "r", "mm", "10")  # in Change Parameters
    App.ActiveDocument.recompute()
    h.fit()
    h.ribbon("Create Sketch")


def r1_xy():
    pl.click_on_plane(V(15, -15, 0))


def r1_draw():
    sk = h.in_sketch()
    h.check("R1 sketch open", sk is not None)
    if sk is None:
        return
    sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 10.0))
    sk.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
    radius = sk.addConstraint(Sketcher.Constraint("Radius", 0, 10.0))
    sk.setExpression(".Constraints[%d]" % radius, "Parameters.r")
    App.ActiveDocument.recompute()


def r1_finish():
    h.ribbon("Finish Sketch")


def r1_pipe():
    h.check("R1 left the sketch", h.in_sketch() is None)
    h.fit()
    pi.menu("Pipe")


def r1_click():
    p = panel()
    h.check("R1 Pipe waits for the path", p is not None and not p.path)
    h.click_edge(ON_CIRCLE)


def r1_picked():
    p = panel()
    h.check("R1 the circle", p is not None and len(p.path) == 1, p and p.path)
    h.check("R1 a preview", p is not None and p.target is not None and vol() > 0, vol())
    h.press(QtCore.Qt.Key_Escape)


r1_picked.wait_ms = 2000


def r1_gone():
    h.check("R1 Esc closed it", pi.no_dialog())
    h.check("R1 no pipe left", not pipes(), [o.Name for o in pipes()])
    h.check("R1 no hidden helper left", not helpers(), [o.Name for o in helpers()])
    h.check("R1 nothing built", near(vol(), 0.0), vol())
    h.check("R1 the sketch is still shown", sketch_shown())
    h.check("R1 timeline: Sketch 1", ti.titles() == ["Sketch 1"], ti.titles())
    pi.menu("Pipe")


r1_gone.wait_ms = 1000


# == R2: the ring ==================================================================================
def r2_click():
    h.click_edge(ON_CIRCLE)


def r2_picked():
    p = panel()
    h.check("R2 the circle", p is not None and len(p.path) == 1, p and p.path)
    if p is None:
        return
    h.check(
        "R2 the first solid: New Body",
        p.operation.currentText() == "New Body",
        p.operation.currentText(),
    )
    ui.type_into(p.size.widget, "2")


r2_picked.wait_ms = 2000


def r2_size():
    p = panel()
    h.check("R2 d2 round r 10: 20 pi^2", near(vol(), 20.0 * PI * PI, 1e-5), vol())
    if p is not None:
        ui.type_into(p.distance, "0.5")


r2_size.wait_ms = 2000


def r2_half():
    p = panel()
    h.check("R2 Distance 0.5: half the ring", near(vol(), 10.0 * PI * PI, 1e-5), vol())
    h.check(
        "R2 the Distance ball at the end",
        p is not None and "distance" in p.handles,
        p and list(p.handles),
    )
    if p is not None:
        pi.tick(p.hollow)


r2_half.wait_ms = 2000


def r2_hollow():
    p = panel()
    h.check("R2 the wall: 0.5", p is not None and near(p.thickness.value(), 0.5), p and p.thickness)
    h.check("R2 hollow: 7.5 pi^2", near(vol(), 7.5 * PI * PI, 1e-5), vol())
    h.check("R2 no message", msg(p) == "", msg(p))
    h.task_button("OK")


r2_hollow.wait_ms = 2000


def r2_ok():
    h.check("R2 OK closed it", pi.no_dialog())
    h.check("R2 kept", near(vol(), 7.5 * PI * PI, 1e-5), vol())
    h.check("R2 the sketch is hidden (used)", not sketch_shown())
    h.check("R2 timeline", ti.titles() == ["Sketch 1", "Pipe 1"], ti.titles())
    s["ring"] = vol()
    h.shot("r2")
    h.press("z", QtCore.Qt.ControlModifier)


r2_ok.wait_ms = 1200


def r2_undone():
    h.check("R2 Ctrl+Z: no pipe", not pipes() and near(vol(), 0.0), vol())
    h.check("R2 Ctrl+Z: the sketch shown again", sketch_shown())
    h.press("y", QtCore.Qt.ControlModifier)


r2_undone.wait_ms = 1500


def r2_redone():
    from sciforge import parameters

    h.check("R2 Ctrl+Y: the ring", near(vol(), s["ring"], 1e-9), vol())
    h.check("R2 Ctrl+Y: the sketch hidden", not sketch_shown())
    parameters.set_user(doc(), "r", "15")  # in Change Parameters
    doc().recompute()


r2_redone.wait_ms = 1500


# == R3: the circle grows, edit, Esc ===============================================================
def r3_follows():
    h.check("R3 r = 15: the ring follows", near(vol(), 11.25 * PI * PI, 1e-5), vol())
    pipe = pipes()[0] if pipes() else None
    h.check(
        "R3 Pipe 1 fine",
        pipe is not None and "Invalid" not in list(pipe.State),
        pipe and list(pipe.State),
    )
    s["ring15"] = vol()
    h.fit()
    h.check("R3 double-click Pipe 1", ti.double_click("Pipe 1"))


r3_follows.wait_ms = 1500


def r3_edit():
    p = panel()
    h.check("R3 editing", p is not None and p.editing)
    if p is None:
        return
    h.check("R3 the sketch shows while editing", sketch_shown())
    shown = (
        round(p.distance.value(), 6),
        p.hollow.isChecked(),
        round(p.size.value(), 6),
        round(p.thickness.value(), 6),
    )
    h.check("R3 the dialog shows the ring as left", shown == (0.5, True, 2.0, 0.5), shown)
    ui.type_into(p.distance, "1")


r3_edit.wait_ms = 2000


def r3_whole():
    h.check("R3 the whole ring: 22.5 pi^2", near(vol(), 22.5 * PI * PI, 1e-5), vol())
    p = panel()
    if p is not None:
        ui.choose(p.section, "Square")


r3_whole.wait_ms = 2000


def r3_square():
    want = 30.0 * PI * (2.0 * math.sqrt(2.0) - 1.0)
    h.check("R3 a hollow square ring", near(vol(), want, 1e-5), (vol(), want))
    h.press(QtCore.Qt.Key_Escape)


r3_square.wait_ms = 2000


def r3_esc():
    h.check("R3 Esc closed it", pi.no_dialog())
    h.check("R3 Esc: as it was", near(vol(), s["ring15"], 1e-9), vol())
    h.check("R3 the sketch hidden again", not sketch_shown())
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-prim-"), "primitives_qa_ring.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("R4 saved", os.path.isfile(path), path)


r3_esc.wait_ms = 1200


# == R4: reopened, edited ==========================================================================
def r4_close():
    App.closeDocument(doc().Name)


def r4_open():
    App.openDocument(s["path"])
    h.fit()


r4_open.wait_ms = 2500


def r4_reopened():
    h.check("R4 reopened: the same ring", near(vol(), s["ring15"], 1e-6), vol())
    doc().recompute()
    h.check("R4 a recompute keeps it", near(vol(), s["ring15"], 1e-6), vol())
    h.check("R4 double-click Pipe 1", ti.double_click("Pipe 1"))


r4_reopened.wait_ms = 2000


def r4_edit():
    p = panel()
    h.check("R4 editing after reopening", p is not None and p.editing)
    if p is not None:
        ui.type_into(p.size.widget, "3")


r4_edit.wait_ms = 2000


def r4_ok():
    p = panel()
    h.check("R4 Section Size 3: 18.75 pi^2", near(vol(), 18.75 * PI * PI, 1e-5), vol())
    h.check("R4 no message", msg(p) == "", msg(p))
    h.task_button("OK")


r4_ok.wait_ms = 2000


def r4_done():
    h.check("R4 OK closed it", pi.no_dialog())
    h.check("R4 kept", near(vol(), 18.75 * PI * PI, 1e-5), vol())
    h.check("R4 one Pipe 1", ti.titles() == ["Sketch 1", "Pipe 1"], ti.titles())
    h.check("R4 two hidden helpers", len(helpers()) == 2, [o.Name for o in helpers()])
    s["final"] = vol()
    h.shot("r4")
    ti.menu("Pipe 1", "Delete")


r4_done.wait_ms = 1000


# == R5: deleted in the timeline ===================================================================
def r5_deleted():
    h.check("R5 Delete: no pipe", not pipes(), [o.Name for o in pipes()])
    h.check("R5 its hidden helpers went with it", not helpers(), [o.Name for o in helpers()])
    h.check("R5 nothing built", near(vol(), 0.0), vol())
    h.check("R5 timeline: Sketch 1", ti.titles() == ["Sketch 1"], ti.titles())
    h.press("z", QtCore.Qt.ControlModifier)


r5_deleted.wait_ms = 1500


def r5_back():
    h.check("R5 Ctrl+Z: the ring is back", near(vol(), s["final"], 1e-9), vol())
    h.check("R5 with its two helpers", len(helpers()) == 2, [o.Name for o in helpers()])
    h.check("R5 timeline", ti.titles() == ["Sketch 1", "Pipe 1"], ti.titles())


r5_back.wait_ms = 1500


h.run(
    "primitives_qa_ring",
    [
        new_design,
        r1_xy,
        r1_draw,
        r1_finish,
        r1_pipe,
        r1_click,
        r1_picked,
        r1_gone,
        r2_click,
        r2_picked,
        r2_size,
        r2_half,
        r2_hollow,
        r2_ok,
        r2_undone,
        r2_redone,
        r3_follows,
        r3_edit,
        r3_whole,
        r3_square,
        r3_esc,
        r4_close,
        r4_open,
        r4_reopened,
        r4_edit,
        r4_ok,
        r4_done,
        r5_deleted,
        r5_back,
    ],
)
