# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve: an angle typed past what a revolve allows is set to that limit (Luca,
2026-10-21; Fusion refuses it, this is Luca's decision; the arrow already stopped there).
Only real input.

A 10 x 20 rectangle on XZ against the Z axis, Revolve, the Z axis. Two Sides, side two 10,
side one 300: side two typed 100 would make 400 degrees: it is set to 60 and the dialog says
"100° does not fit: limited to 60.0° (both sides together make one full turn)", no error,
the preview is the full turn (2000 pi). One Side 400 typed: set to 360. Two Sides again,
side one 300, side two from a formula past the limit (parameter big = 100 deg) is not
rewritten: explained, OK waits. Side two 30 typed, OK: 330 degrees in all."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import revolve_input as ri

V = App.Vector
CYL = 2000.0 * math.pi


def panel():
    return ri.panel()


def note(p):
    return p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""


def msg(p):
    return p.message.text() if p is not None else ""


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("LimitsRevolve")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    pl.click_square("XZ_Plane")


def draw():
    sk = h.in_sketch()
    h.check("sketch open", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 10, 20)


def finish_sketch():
    h.ribbon("Finish Sketch")


def revolve_it():
    h.fit()
    h.ribbon("Revolve")


def click_z_axis():
    h.fit()
    pl.click_on_plane(V(0, 0, 32))


def two_sides():
    p = panel()
    h.check("a full turn first", p is not None and ri.near(h.solid_volume(), CYL))
    if p:
        ui.choose(p.direction, "Two Sides")


def side_one_300():
    p = panel()
    if p:
        ui.type_into(p.angle2.widget, "10")  # side two small first: 300 + 10 fits
        ui.type_into(p.angle.widget, "300")


def side_two_100():
    p = panel()
    if p:
        ui.type_into(p.angle2.widget, "100")


def side_two_held():
    p = panel()
    a2 = p.options["angle2"] if p else 0
    h.check("side two is set to 60 (both 360)", ri.near(a2, 60.0), (p and p.options["angle"], a2))
    h.check(
        "and said, with why",
        note(p) == "100° does not fit: limited to 60.0° (both sides together make one full turn)",
        note(p),
    )
    h.check("no error", msg(p) == "", msg(p))
    h.check("the box shows 60", p is not None and ri.near(p.angle2.value(), 60.0))
    h.check("the preview is the full turn", ri.near(h.solid_volume(), CYL, 1e-5), h.solid_volume())
    if p:
        ui.choose(p.direction, "One Side")


def one_side_400():
    p = panel()
    if p:
        ui.type_into(p.angle.widget, "400")


def one_side_held():
    p = panel()
    a = p.options["angle"] if p else 0
    h.check("400 is set to 360", ri.near(a, 360.0), a)
    h.check("and said", note(p) == "400° does not fit: limited to 360.0°", note(p))
    from sciforge import parameters

    parameters.add_user(App.ActiveDocument, "big", "deg", "100")
    if p:
        ui.choose(p.direction, "Two Sides")


def two_sides_300():
    p = panel()
    if p:
        ui.type_into(p.angle2.widget, "10")
        ui.type_into(p.angle.widget, "300")


def formula_100():
    p = panel()
    if p:
        ui.type_into(p.angle2.widget, "big")


def formula_explained():
    p = panel()
    h.check("the formula is kept", p is not None and p.formula_of("angle2") == "big")
    h.check("explained", "360" in msg(p), msg(p))
    h.check("no note", note(p) == "", note(p))
    h.task_button("OK")


def formula_ok_waits():
    p = panel()
    h.check("OK waits", p is not None and Gui.Control.activeDialog())
    if p:
        ui.type_into(p.angle2.widget, "30")


def ok_30():
    p = panel()
    h.check("30: no message, no note", msg(p) == "" and note(p) == "", (msg(p), note(p)))
    h.task_button("OK")


def made():
    h.check("closed", not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("330 degrees in all", ri.near(v, CYL * 330.0 / 360.0, 1e-5), v)


h.run(
    "limits_revolve",
    [
        new_design,
        pick_xz,
        draw,
        finish_sketch,
        revolve_it,
        click_z_axis,
        two_sides,
        side_one_300,
        side_two_100,
        side_two_held,
        one_side_400,
        one_side_held,
        two_sides_300,
        formula_100,
        formula_explained,
        formula_ok_waits,
        ok_30,
        made,
    ],
)
