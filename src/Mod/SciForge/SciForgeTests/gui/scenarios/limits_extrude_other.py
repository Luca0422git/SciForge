# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude: a taper that stops fitting because the distance changed is never rewritten (fix of
review finding L1, 2026-10-22). Only real input.

A 40 x 30 rectangle, E, 10 mm, taper -50 typed (fits at 10 mm). The distance arrow dragged
20 mm further: at 30 mm the sides would meet before the top. The taper the user typed stays
-50 (box, options and the feature in the document: the limit search's trial tapers are not
left behind), the dialog explains it with the steepest taper that fits, and that search runs
once, after the arrow is let go (not on every step of the drag). 20 typed for the distance:
still -50 and explained. OK waits (the dialog stays, nothing made with a taper the box does
not show). Taper -30 typed: it fits; OK makes the extrude with -30."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl

s = {}


def panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def msg(p):
    return p.message.text() if p is not None else ""


def feature_taper(p):
    try:
        return p.target.TaperAngle.Value
    except Exception:
        return None


def taper_kept(p, tag):
    h.check(
        "%s: the taper stays -50 (options, box)" % tag,
        p is not None and p.options["taper"] == -50.0 and abs(p.taper.value() + 50.0) < 1e-9,
        p and (p.options["taper"], p.taper.value()),
    )
    h.check(
        "%s: the feature's taper is -50 too (no trial left in the document)" % tag,
        p is not None and abs((feature_taper(p) or 0) + 50.0) < 1e-9,
        p and feature_taper(p),
    )
    text = msg(p)
    h.check(
        "%s: explained with the steepest taper that fits" % tag,
        text.startswith("⚠ ") and "Furthest that fits here: -" in text,
        text,
    )


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("LimitsExtrudeOther")
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


def taper50():
    p = panel()
    if p:
        ui.type_into(p.taper.widget, "-50")


taper50.wait_ms = 3000


def drag_distance():
    p = panel()
    h.check("-50 fits at 10 mm", p is not None and msg(p) == "" and p.options["taper"] == -50.0)
    h.check("the feature has -50", p is not None and abs((feature_taper(p) or 0) + 50.0) < 1e-9)
    s["searches"] = p.limits.searches if p else 0
    arrow = p.draggers.get("distance") if p else None
    if arrow is None:
        h.check("the distance arrow", False, p and list(p.draggers))
        return
    head = arrows.head_point(arrow)
    s["drag"] = arrows.HeldDrag(
        h.screen_point(head), h.screen_point(head + App.Vector(0, 0, 20)), moves=30, every_ms=40
    )
    s["drag"].run()


drag_distance.wait_ms = 15000


def dragged():
    p = panel()
    h.check(
        "the distance went up", p is not None and p.options["distance"] > 20, p and p.options
    )
    taper_kept(p, "after the drag")
    h.check(
        "one search, after the arrow was let go",
        p is not None and p.limits.searches - s["searches"] <= 1,
        p and (p.limits.searches, s["searches"]),
    )
    if p:
        ui.type_into(p.distance.widget, "20")


dragged.wait_ms = 5000


def typed20():
    p = panel()
    h.check("distance 20", p is not None and abs(p.options["distance"] - 20.0) < 1e-9)
    taper_kept(p, "distance 20")
    h.task_button("OK")


typed20.wait_ms = 3000


def ok_waits():
    p = panel()
    h.check("OK waits: the dialog stays", p is not None and bool(Gui.Control.activeDialog()))
    taper_kept(p, "after OK")
    if p:
        ui.type_into(p.taper.widget, "-30")


ok_waits.wait_ms = 3000


def taper30():
    p = panel()
    h.check("-30 fits at 20 mm", p is not None and msg(p) == "", msg(p))
    h.check("the feature has -30", p is not None and abs((feature_taper(p) or 0) + 30.0) < 1e-9)
    h.task_button("OK")


taper30.wait_ms = 3000


def made():
    h.check("OK worked", panel() is None and not Gui.Control.activeDialog())
    pads = [o for o in App.ActiveDocument.Objects if hasattr(o, "TaperAngle")]
    h.check(
        "the extrude has taper -30 and length 20",
        len(pads) == 1
        and abs(pads[0].TaperAngle.Value + 30.0) < 1e-9
        and abs(pads[0].Length.Value - 20.0) < 1e-9,
        [(o.Name, o.TaperAngle.Value, o.Length.Value) for o in pads],
    )


h.run(
    "limits_extrude_other",
    [
        new_design,
        pick_xy,
        draw,
        finish_sketch,
        extrude_it,
        taper50,
        drag_distance,
        dragged,
        typed20,
        ok_waits,
        taper30,
        made,
    ],
)
