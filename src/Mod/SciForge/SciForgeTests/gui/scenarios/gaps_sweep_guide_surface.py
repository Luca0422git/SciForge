# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sweep, Type Path + Guide Surface (Fusion's third sweep type), only real input.

A cylinder r20, 60 high (Create Sketch on XY, a circle, E 60), its top cut along the slanted
line z = 30 + x / 2 (a sketch on XZ, E through both sides, Cut): the cut's edge on the
cylinder is an ellipse. A 1 x 6 rectangle sketched on XZ across the cylinder's side where the
ellipse passes (20, 0, 40).
Path G1, CREATE > Sweep: the rectangle is taken as the profile by itself (the newest
         sketch's only area); click the ellipse (the path).
         Type Path + Guide Surface: the Guide Surface box waits; click the cylinder's side:
         the strip keeps hugging the cylinder all the way round (within 19.5 .. 20.6 of its
         axis; a Single Path sweep turns it out to 17.3 .. 22.7). Only Distance is offered
         (Fusion's fields for this type). New Body, OK.
Path G2, double-click Sweep 1 in the timeline: it reads Path + Guide Surface and 1 face; Esc
         keeps it. Undo / redo.

Volume: the profile stays square to the path with its centre on it: 6 x the ellipse's
perimeter (semi-axes 20 sqrt(1.25) and 20) = 799.10."""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
STRIP = 799.1000665878644
s = {}


def panel():
    return st.panel("sweep")


def strip_body():
    bodies = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Body"]
    return bodies[-1] if len(bodies) > 1 else None


def radii(shape):
    points = []
    for face in shape.Faces:
        points += [v.Point for v in face.Vertexes]
        points += face.tessellate(0.1)[0]
    values = [math.hypot(p.x, p.y) for p in points]
    return min(values), max(values)


# -- the cut cylinder and the profile ------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("GuideSurface")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw_circle():
    sk = h.in_sketch()
    if h.check("sketch open on XY", sk is not None):
        h.draw_circle(sk, 0, 0, 20)


def finish_circle():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def extrude_distance():
    from sciforge import taskui

    p = taskui.current()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude dialog", field is not None):
        ui.type_into(field, "60")


def extrude_ok():
    h.task_button("OK")


def cylinder_made():
    h.check("cylinder r20 h60", st.near(h.solid_volume(), math.pi * 400 * 60), h.solid_volume())
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_xz():
    h.click(V(-35, 0, 30))


def draw_cut():
    sk = h.in_sketch()
    if not h.check("sketch open on XZ", sk is not None):
        return
    st.add_lines(sk, [(-30, 15), (30, 45), (30, 70), (-30, 70)], closed=True)


def finish_cut():
    h.ribbon("Finish Sketch")


def cut_extrude():
    h.fit()
    h.press("e")


def cut_options():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    if not h.check("extrude dialog", p is not None and not p._closed):
        return
    h.check("Symmetric", ui.choose(p.direction, "Symmetric"))
    ui.type_into(p.distance.widget, "60")


def cut_operation():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    if p is not None:
        h.check("Cut", ui.choose(p.operation, "Cut"))


def cut_ok():
    h.task_button("OK")


def cut_made():
    full = math.pi * 400 * 60
    h.check("the top is cut off", h.solid_volume() < full - 1000, h.solid_volume())
    s["volume"] = h.solid_volume()
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_xz_2():
    h.click(V(-24, 0, 20))  # the squares are smaller now (the part is 40 high)


def draw_profile():
    sk = h.in_sketch()
    if h.check("sketch open on XZ", sk is not None):
        h.draw_rectangle(sk, 19.5, 37, 20.5, 43)


def finish_profile():
    h.ribbon("Finish Sketch")


# -- G1: the sweep --------------------------------------------------------------------------
def sweep_start():
    h.fit()
    h.click_empty()
    st.menu("Sweep")


def click_path():
    p = panel()
    h.check("Sweep open", p is not None)
    # The newest sketch's only area is taken by itself (Fusion takes it too).
    h.check(
        "the rectangle is the profile", p is not None and len(p.profiles) == 1, p and p.profiles
    )
    h.fit()
    h.check("the ellipse clicked", h.click_edge(V(14.1421, -14.1421, 37.0711)))


def path_taken():
    p = panel()
    if p is None:
        return
    h.check(
        "the ellipse is the path",
        len(p.path) == 1 and p.path[0][1].startswith("Edge"),
        p.path,
    )
    labels = [p.type.itemText(i) for i in range(p.type.count())]
    h.check("Path + Guide Surface offered", "Path + Guide Surface" in labels, labels)
    h.check("choose Path + Guide Surface", ui.choose(p.type, "Path + Guide Surface"))


def surface_box():
    p = panel()
    if p is None:
        return
    h.check("the Guide Surface box waits", p.active == "surface", p.active)
    h.check(
        "only Distance offered (no taper, twist or orientation)",
        p.distance.isVisible()
        and not p.taper.widget.isVisible()
        and not p.twist.widget.isVisible()
        and not p.orientation.isVisible(),
    )
    h.check("New Body", ui.choose(p.operation, "New Body"))
    h.fit()
    h.click(V(10, -17.3205, 10))


surface_box.wait_ms = 1500


def hugging():
    p = panel()
    if p is None:
        return
    h.check("the side is the guide surface", len(p.surface) == 1, p.surface)
    h.check(
        "the Guide Surface box says 1 face",
        p.fields["surface"].button.text() == "1 face",
        p.fields["surface"].button.text(),
    )
    body = strip_body()
    if not h.check("a body of its own", body is not None):
        return
    low, high = radii(body.Shape)
    h.check("the strip hugs the cylinder: 19.45 .. 20.6", low > 19.45 and high < 20.6, (low, high))
    h.check(
        "6 x the ellipse's length: 799.10",
        st.near(body.Shape.Volume, STRIP, 1e-3),
        body.Shape.Volume,
    )
    h.check("no message", p.message.text() == "", p.message.text())
    h.fit()
    h.shot("1-guide-surface")
    h.task_button("OK")


hugging.wait_ms = 2000


def kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    body = strip_body()
    h.check("kept", body is not None and st.near(body.Shape.Volume, STRIP, 1e-3))
    h.check("Sweep 1 in the timeline", "Sweep 1" in st.timeline_titles(), st.timeline_titles())


# -- G2: edit, undo / redo ------------------------------------------------------------------
def edit():
    h.click_empty()
    st.edit_in_timeline("Sweep 1")


def editing():
    p = panel()
    if not h.check("edit dialog open", p is not None):
        return
    h.check(
        "it reads Path + Guide Surface",
        p.type.currentText() == "Path + Guide Surface",
        p.type.currentText(),
    )
    h.check("with 1 face", len(p.surface) == 1, p.surface)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closed it", not Gui.Control.activeDialog())
    body = strip_body()
    h.check("still there", body is not None and st.near(body.Shape.Volume, STRIP, 1e-3))
    st.ctrl("z")


def undone():
    h.check("Undo: no strip", strip_body() is None, strip_body())
    st.ctrl("y")


def redone():
    body = strip_body()
    h.check("Redo: the strip is back", body is not None and st.near(body.Shape.Volume, STRIP, 1e-3))
    first = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Body"][0]
    h.check("the cut cylinder unchanged", st.near(first.Shape.Volume, s["volume"]), first.Label)


h.run(
    "gaps_sweep_guide_surface",
    [
        new_design,
        pick_xy,
        draw_circle,
        finish_circle,
        extrude,
        extrude_distance,
        extrude_ok,
        cylinder_made,
        pick_xz,
        draw_cut,
        finish_cut,
        cut_extrude,
        cut_options,
        cut_operation,
        cut_ok,
        cut_made,
        pick_xz_2,
        draw_profile,
        finish_profile,
        sweep_start,
        click_path,
        path_taken,
        surface_box,
        hugging,
        kept,
        edit,
        editing,
        after_esc,
        undone,
        redone,
    ],
)
