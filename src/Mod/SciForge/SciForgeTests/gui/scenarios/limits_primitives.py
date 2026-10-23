# SPDX-License-Identifier: LGPL-2.1-or-later
"""Torus: a ring dragged thicker than its diameter allows stops at the thickest one that
works (Luca, 2026-10-21; Fusion refuses it, this is Luca's decision). Only real input.

Torus on XY, centre on the origin, a point at (20, 0): inner diameter 40, On Center. The
Torus Diameter arrow dragged far out (to 80) stops just under 40 (the ring would close up
in the middle), the arrow too, the dialog says "Largest that fits here: 39.99 mm", no
error, the preview is that torus (2 pi^2 R r^2), the limit was worked out once for the
whole drag. Dragged back to 10: the note goes. OK: the torus R20 r5."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import primitive_input as pi

V = App.Vector
s = {}


def panel():
    return pi.panel("TorusPanel")


def note(p):
    return p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""


def torus(major, minor):
    return 2.0 * math.pi**2 * major * minor**2


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("LimitsTorus")
    h.fit()
    pi.menu("Torus")


def xy():
    pl.click_square("XY_Plane")


def centre():
    pl.click_on_plane(V(0, 0, 0))


def circle():
    pl.click_on_plane(V(20, 0, 0))


circle.wait_ms = 1500


def built():
    p = panel()
    h.check("inner 40, On Center", p is not None and pi.near(p.inner.value(), 40.0))
    h.fit()
    s["searches"] = p.limits.searches if p else 0


def drag_far():
    p = panel()
    handle = p.handles.get("torus_diameter") if p else None
    h.check("the Torus Diameter arrow", handle is not None, p and list(p.handles))
    if handle is not None:
        pi.drag_handle(handle, 80.0, steps=30)


drag_far.wait_ms = 2000


def dragged_far():
    p = panel()
    if p is None:
        h.check("Torus dialog open", False)
        return
    d = p.options["torus_diameter"]
    h.check("the ring stopped just under 40 mm", pi.near(d, 39.99), d)
    h.check("the box shows it", pi.near(p.tube.value(), 39.99), p.tube.value())
    h.check("the note", note(p) == "Largest that fits here: 39.99 mm", note(p))
    h.check("no error", p.message.text() == "", p.message.text())
    v = pi.total_volume()
    h.check("the preview is that torus", pi.near(v, torus(20.0, d / 2.0), 1e-5), v)
    h.check(
        "worked out once for the whole drag",
        p.limits.searches - s["searches"] == 1,
        p.limits.searches - s["searches"],
    )
    handle = p.handles.get("torus_diameter")
    h.check(
        "the arrow stopped there too",
        handle is not None and pi.near(handle.value(), d),
        handle and handle.value(),
    )
    h.shot("1-torus-held")
    if handle is not None:
        pi.drag_handle(handle, 10.0, steps=20)


dragged_far.wait_ms = 2000


def dragged_back():
    p = panel()
    d = p.options["torus_diameter"] if p else 0
    h.check("dragged back to about 10", 8.0 < d < 12.0, d)
    h.check("the note went", note(p) == "", note(p))
    if p is not None:
        from SciForgeTests.gui import dialog_input as ui

        ui.type_into(p.tube.widget, "10")
    h.task_button("OK")


dragged_back.wait_ms = 1500


def made():
    h.check("OK closed it", pi.no_dialog())
    v = pi.total_volume()
    h.check("torus R20 r5", pi.near(v, torus(20.0, 5.0), 1e-5), v)


h.run(
    "limits_primitives",
    [new_design, xy, centre, circle, built, drag_far, dragged_far, dragged_back, made],
)
