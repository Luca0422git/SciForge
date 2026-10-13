# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude tapers with every extent (Fusion tapers To Object too, and each side of Two
Sides has its own taper), only real input.

Path X1, a lid body 25 above a 50 x 40 x 5 plate, made with Start: Offset (a New Body by
         itself).
Path X2, a 20 x 20 column on the plate To Object the lid as a whole body (clicked in the
         browser), tapered 5 degrees: it ends where it meets the lid, its sides lean out;
         the lid is joined too (Fusion joins every body the extrusion touches); edited from
         the timeline back to no taper; Ctrl+Z.
Path X3, a circle on the XZ plane beside the plate, Two Sides: side one 10 widening 5
         degrees, side two 6 narrowing 10 degrees: a New Body of two cone frustums.

Numbers by hand: frustum of a square a x a growing by d per side over h: h/3 (a^2 + b^2 +
ab) with b = a + 2d; a cone frustum: pi h / 3 (r1^2 + r1 r2 + r2^2).
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}
PLATE = 50.0 * 40.0 * 5.0
LID = 60.0 * 50.0 * 10.0


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def bodies():
    return doc().findObjects("PartDesign::Body")


def shown_volume():
    total = 0.0
    for b in bodies():
        if b.ViewObject.Visibility and not b.Shape.isNull():
            total += b.Shape.Volume
    return total


def plate_volume():
    """The plate's body (a Join merges the lid into it: Fusion joins every body the
    extrusion touches)."""
    b = doc().getObject("Body")
    return b.Shape.Volume if b is not None and not b.Shape.isNull() else 0.0


def dialog_open():
    return bool(Gui.Control.activeDialog())


def broken():
    return [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def square_frustum(a, height, taper):
    b = a + 2.0 * height * math.tan(math.radians(taper))
    return height / 3.0 * (a * a + b * b + a * b)


def cone_frustum(r, height, taper):
    r2 = r + height * math.tan(math.radians(taper))
    return math.pi * height / 3.0 * (r * r + r * r2 + r2 * r2)


def step(fn, name):
    fn.__name__ = name
    return fn


def sketch_on_top(tag, x0, y0, x1, y1):
    """Create Sketch on the plate's top face and draw a rectangle (global x, y)."""

    def create():
        h.click_empty()
        h.ribbon("Create Sketch")

    def pick():
        h.fit()
        h.click(V(40, 5, 5))  # the plate's top, in front of everything on it

    def draw():
        sk = h.in_sketch()
        h.check("%s sketch open on the plate" % tag, sk is not None)
        if sk:
            ax, ay = h.to_sketch(sk, V(x0, y0, 5))
            bx, by = h.to_sketch(sk, V(x1, y1, 5))
            h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def finish():
        h.ribbon("Finish Sketch")

    return [
        step(create, "%s_sketch" % tag),
        step(pick, "%s_pick" % tag),
        step(draw, "%s_draw" % tag),
        step(finish, "%s_finish" % tag),
    ]


# -- the plate -----------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("TaperTo")
    h.fit()


def plate_sketch():
    h.ribbon("Create Sketch")


def plate_pick_xy():
    h.click(V(12, -8, 0))


def plate_draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 50, 40)


def plate_finish():
    h.ribbon("Finish Sketch")


def plate_e():
    h.fit()
    h.press("e")


def plate_distance():
    arrows.type_distance("5")


def plate_ok():
    h.task_button("OK")


def plate_done():
    h.check("plate 50 x 40 x 5", near(shown_volume(), PLATE), shown_volume())


# -- Path X1: the lid ----------------------------------------------------------------------------
def x1_e():
    h.fit()
    h.press("e")


def x1_offset():
    p = xpanel()
    h.check("X1 the lid's area picked by itself", p is not None and len(p.profiles) == 1)
    if p is None:
        return
    h.check("X1 choose Start: Offset", ui.choose(p.start, "Offset"))


def x1_offset_25():
    p = xpanel()
    ui.type_into(p.start_offset.widget, "25")


def x1_distance():
    arrows.type_distance("10")


def x1_new_body():
    p = xpanel()
    h.check(
        "X1 a New Body by itself (it touches nothing)",
        p.operation.currentText() == "New Body",
        p.operation.currentText(),
    )
    h.task_button("OK")


def x1_done():
    h.check("X1 kept", not dialog_open())
    h.check("X1 two bodies", len(bodies()) == 2, [b.Label for b in bodies()])
    h.check("X1 plate + lid", near(shown_volume(), PLATE + LID), shown_volume())
    lid = [b for b in bodies() if b.Label != "Body"]
    s["lid"] = lid[0] if lid else None
    if s["lid"] is not None:
        box = s["lid"].Shape.BoundBox
        h.check("X1 the lid from z 30 to 40", near(box.ZMin, 30.0) and near(box.ZMax, 40.0), box)


# -- Path X2: a tapered column To Object the lid (a whole body) ---------------------------------
def x2_e():
    h.click_empty()
    h.fit()
    h.press("e")


def x2_to_object():
    p = xpanel()
    h.check("X2 the column picked by itself", p is not None and len(p.profiles) == 1)
    if p is None:
        return
    h.check("X2 choose Extent: To Object", ui.choose(p.extent, "To Object"))


def x2_pick_body():
    p = xpanel()
    h.check("X2 To Object waits for its object", p.active == "extent_object", p.active)
    lid = s.get("lid")
    h.check("X2 click the lid in the browser", lid is not None and tl.click_row(lid.Label))


def x2_taper():
    p = xpanel()
    h.check("X2 the lid picked", p.options.get("extent_object") is not None, p.message.text())
    want = PLATE + 20.0 * 20.0 * 25.0 + LID
    h.check("X2 the column ends at the lid", near(plate_volume(), want), (plate_volume(), want))
    ui.type_into(p.taper.widget, "5")


def x2_tapered():
    p = xpanel()
    want = PLATE + square_frustum(20.0, 25.0, 5.0) + LID
    h.check(
        "X2 tapered 5 degrees up to the lid", near(plate_volume(), want), (plate_volume(), want)
    )
    h.check("X2 no warning", "⚠" not in p.message.text(), p.message.text())
    h.check("X2 no FreeCAD dialog", not h.popups(), h.popups())
    h.shot("x2-taper-to-body")
    h.task_button("OK")


def x2_done():
    h.check("X2 kept", not dialog_open())
    want = PLATE + square_frustum(20.0, 25.0, 5.0) + LID
    h.check("X2 still there after OK", near(plate_volume(), want), plate_volume())
    h.check("X2 nothing in error", not broken(), broken())
    s["tapered"] = plate_volume()
    titles = ui.timeline_titles()
    s["column"] = [t for t in titles if t.startswith("Extrude")][-1]
    h.check("X2 edit %s" % s["column"], ui.double_click_timeline(s["column"]), titles)


def x2_editing():
    p = xpanel()
    h.check("X2 editing", p is not None and p.editing)
    if p is None:
        return
    h.check("X2 To Object back", p.extent.currentText() == "To Object")
    h.check("X2 taper 5 back", near(p.taper.value(), 5.0), p.taper.value())
    ui.type_into(p.taper.widget, "0")


def x2_untapered():
    want = PLATE + 20.0 * 20.0 * 25.0 + LID
    h.check("X2 no taper: a straight column", near(plate_volume(), want), plate_volume())
    h.task_button("OK")


def x2_undo():
    h.check("X2 kept", not dialog_open())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def x2_undone():
    h.check("X2 Ctrl+Z: the taper is back", near(plate_volume(), s["tapered"]), plate_volume())
    h.check("X2 nothing in error after undo", not broken(), broken())


# -- Path X3: Two Sides, each side its own taper -------------------------------------------------
def x3_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def x3_pick_xz():
    h.fit()
    h.click(V(-25, 0, 22))  # the XZ square left of the plate


def x3_draw():
    sk = h.in_sketch()
    h.check("X3 sketch open on XZ", sk is not None)
    if sk:
        x, y = h.to_sketch(sk, V(-25, 0, 20))
        h.draw_circle(sk, x, y, 5)


def x3_finish():
    h.ribbon("Finish Sketch")


def x3_e():
    h.click_empty()
    h.fit()
    h.press("e")


def x3_two_sides():
    p = xpanel()
    h.check("X3 the circle picked by itself", p is not None and len(p.profiles) == 1)
    if p is None:
        return
    h.check("X3 choose Direction: Two Sides", ui.choose(p.direction, "Two Sides"))


def x3_values():
    p = xpanel()
    h.check("X3 side two has its own Taper Angle", p.taper2.widget.isVisible())
    ui.type_into(p.distance.widget, "10")
    ui.type_into(p.taper.widget, "5")
    ui.type_into(p.distance2.widget, "6")
    ui.type_into(p.taper2.widget, "-10")


def x3_check():
    p = xpanel()
    h.check("X3 a New Body", p.operation.currentText() == "New Body", p.operation.currentText())
    new = [b for b in bodies() if b.Label not in ("Body", s["lid"].Label)]
    want = cone_frustum(5.0, 10.0, 5.0) + cone_frustum(5.0, 6.0, -10.0)
    got = new[0].Shape.Volume if new else 0.0
    h.check("X3 side one widens, side two narrows", near(got, want), (got, want))
    if new:
        box = new[0].Shape.BoundBox
        h.check("X3 16 long along Y", near(box.YLength, 16.0), box)
    h.shot("x3-two-sides-taper")
    h.task_button("OK")


def x3_done():
    h.check("X3 kept", not dialog_open())
    h.check("X3 three bodies", len(bodies()) == 3, [b.Label for b in bodies()])
    h.check("X3 nothing in error", not broken(), broken())
    h.fit()
    h.shot("x3-end")


h.run(
    "gaps_extrude_taper_to",
    tl.watched(
        [
            new_design,
            plate_sketch,
            plate_pick_xy,
            plate_draw,
            plate_finish,
            plate_e,
            plate_distance,
            plate_ok,
            plate_done,
        ]
        + sketch_on_top("x1", -5, -5, 55, 45)
        + [x1_e, x1_offset, x1_offset_25, x1_distance, x1_new_body, x1_done]
        + sketch_on_top("x2", 15, 10, 35, 30)
        + [
            x2_e,
            x2_to_object,
            x2_pick_body,
            x2_taper,
            x2_tapered,
            x2_done,
            x2_editing,
            x2_untapered,
            x2_undo,
            x2_undone,
            x3_sketch,
            x3_pick_xz,
            x3_draw,
            x3_finish,
            x3_e,
            x3_two_sides,
            x3_values,
            x3_check,
            x3_done,
        ]
    ),
)
