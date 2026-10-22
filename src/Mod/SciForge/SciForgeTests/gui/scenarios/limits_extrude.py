# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude: a taper angle past what the profile can take stops at the steepest one that
works (Luca, 2026-10-21; Fusion refuses it, this is Luca's decision). Only real input.

A 40 x 30 rectangle, E, 10 mm. Taper -60 typed: the sides would meet before the top (the
profile shrinks 10 tan 60 = 17.3 mm a side, more than half of 30): held at the steepest
taper that works and said ("-60° does not fit: limited to ..."), no error, the preview is
that frustum. Taper 0 again. The taper disc turned far inward stops at the same limit
without a new search; OK: the frustum is made."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl

V = App.Vector
s = {}


def panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def note(p):
    return p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""


def msg(p):
    return p.message.text() if p is not None else ""


def near(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


def frustum(deg):
    """The 40 x 30 rectangle shrinking by 10 tan(deg) a side over 10 mm (Simpson: exact)."""
    d = 10.0 * math.tan(math.radians(abs(deg)))
    return 10.0 / 6.0 * (40 * 30 + 4 * (40 - d) * (30 - d) + (40 - 2 * d) * (30 - 2 * d))


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("LimitsExtrude")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")


def draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)


def finish_sketch():
    h.ribbon("Finish Sketch")


def extrude_it():
    h.fit()
    h.press("e")
    arrows.type_distance("10")


def started():
    p = panel()
    h.check("10 mm: 12000", near(h.solid_volume(), 12000.0), h.solid_volume())
    if p:
        ui.type_into(p.taper.widget, "-60")


def taper_held():
    p = panel()
    t = p.options["taper"] if p else 0
    s["t"] = t
    h.check("-60 is held at the steepest taper that works", -60.0 < t < -40.0, t)
    h.check("and said", note(p) == "-60° does not fit: limited to %.1f°" % t, note(p))
    h.check("no error", msg(p) == "", msg(p))
    h.check("the box shows the limit", p is not None and abs(p.taper.value() - t) < 1e-9)
    v = h.solid_volume()
    h.check("the preview is that frustum", near(v, frustum(t), 1e-5), (v, frustum(t)))
    s["searches"] = p.limits.searches if p else 0
    if p:
        ui.type_into(p.taper.widget, "0")


taper_held.wait_ms = 4000


def back_to_zero():
    p = panel()
    h.check("taper 0 again: 12000, no note", near(h.solid_volume(), 12000.0) and note(p) == "")
    h.fit()


def turn_far():
    p = panel()
    disc = p.draggers.get("taper") if p else None
    if disc is None:
        h.check("the taper disc", False, p and list(p.draggers))
        return
    here, there = disc.screen_points(-80.0)
    s["drag"] = arrows.HeldDrag(h.screen_point(here), h.screen_point(there), moves=30, every_ms=40)
    s["drag"].run()


def turned_far():
    p = panel()
    t = p.options["taper"] if p else 0
    h.check("turned far, the taper stops at the same limit", abs(t - s["t"]) < 1e-9, (t, s["t"]))
    h.check("the note", note(p) == "Furthest that fits here: %.1f°" % t, note(p))
    h.check(
        "no new search: the limit was known",
        p is not None and p.limits.searches == s["searches"],
        p and (p.limits.searches, s["searches"]),
    )
    disc = p.draggers.get("taper") if p else None
    h.check(
        "the disc stopped there too",
        disc is not None and abs(disc.angle() - t) < 0.05,
        disc and (disc.angle(), t),
    )
    h.shot("1-taper-held")
    h.task_button("OK")


turned_far.wait_ms = 3000


def made():
    h.check("OK worked at once", panel() is None and not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("the frustum is made", near(v, frustum(s["t"]), 1e-5), (v, frustum(s["t"])))


h.run(
    "limits_extrude",
    [
        new_design,
        pick_xy,
        draw,
        finish_sketch,
        extrude_it,
        started,
        taper_held,
        back_to_zero,
        turn_far,
        turned_far,
        made,
    ],
)
