# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude and Press Pull on a sloped face (QA, only real input).

A trapezoid prism (40 wide at the bottom, 20 at the top, 20 high, 20 deep; sketched on XZ).
Path 25, Press Pull the right sloped face out by 2: the top and bottom faces extend to
         meet it (Fusion), the new trapezoid is 2.236 wider at every height.
Path 26, Create Sketch on that sloped face, a circle, Extrude: the boss stands square on
         the slope; its arrow and the taper handle sit on the slope; taper from the
         timeline; Press Pull the boss's end.

Numbers by hand: the slope's outward normal is (2, 0, 1) / sqrt(5); moving the face by d
along it widens the trapezoid by d * sqrt(5) / 2 at every height.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
SHIFT = 2.0 * math.sqrt(5.0) / 2.0  # 2.2361
NORMAL = V(2, 0, 1).normalize()


def xpanel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def ppanel():
    from sciforge import presspull_ui

    return presspull_ui.PressPullPanel.last


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def dialog_open():
    return bool(Gui.Control.activeDialog())


def broken():
    return [
        o.Label for o in App.ActiveDocument.Objects if "Invalid" in o.State or "Error" in o.State
    ]


def frustum_cone(r, height, taper):
    r2 = r + height * math.tan(math.radians(taper))
    return math.pi * height / 3.0 * (r * r + r * r2 + r2 * r2)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("QASlope")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    h.click(V(15, 0, 12))


def draw_trapezoid():
    import Part
    import Sketcher

    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None)
    if not sk:
        return
    pts = [V(0, 0, 0), V(40, 0, 0), V(30, 20, 0), V(10, 20, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    App.ActiveDocument.recompute()


def finish():
    h.ribbon("Finish Sketch")


def extrude_prism():
    h.fit()
    h.press("e")


def prism_depth():
    p = xpanel()
    h.check("trapezoid picked by itself", p.target is not None, p.message.text())
    ui.type_into(p.distance.widget, "20")


def prism_ok():
    h.task_button("OK")


def prism_done():
    h.check("trapezoid prism 12000", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.click_empty()
    h.press("q")


# -- Path 25: Press Pull the sloped face --------------------------------------------------
def p25_pick_slope():
    h.fit()
    h.click(V(35, -10, 10))


def p25_type():
    p = ppanel()
    h.check("the sloped face picked", p.target is not None and len(p.names) == 1, p.message.text())
    h.check("the arrow stands on the slope", p.dragger is not None)
    if p.dragger is not None:
        place = p.dragger.root.getChild(0)
        axis = place.rotation.getValue().multVec(p.dragger.coin.SbVec3f(1, 0, 0)).getValue()
        h.check(
            "the arrow points along the slope's normal",
            (V(*axis) - NORMAL).Length < 1e-4,
            axis,
        )
    ui.type_into(p.field.widget, "2")


def p25_ok():
    want = ((40.0 + SHIFT) + (20.0 + SHIFT)) / 2.0 * 20.0 * 20.0
    h.check(
        "the slope moved 2 along its normal, top and bottom extended",
        near(h.solid_volume(), want, 1e-6),
        (h.solid_volume(), want, ppanel().message.text()),
    )
    h.check("still 6 faces (no step)", len(h.body().Shape.Faces) == 6, len(h.body().Shape.Faces))
    s["prism"] = want
    h.shot("p25-slope")
    h.task_button("OK")


# -- Path 26: a boss on the slope ------------------------------------------------------------
def p26_sketch():
    h.check("Press Pull kept", not dialog_open())
    h.click_empty()
    h.ribbon("Create Sketch")


def p26_pick():
    h.fit()
    s["centre"] = V(35 + SHIFT * 1.0, -10, 10)  # the moved slope's middle
    h.click(s["centre"])


def p26_circle():
    sk = h.in_sketch()
    h.check("sketch on the slope", sk is not None)
    if sk:
        normal = sk.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
        h.check("the sketch lies on the slope", abs(abs(normal.dot(NORMAL)) - 1) < 1e-6, normal)
        x, y = h.to_sketch(sk, s["centre"])
        h.draw_circle(sk, x, y, 3)


def p26_finish():
    h.ribbon("Finish Sketch")


def p26_e():
    h.fit()
    h.press("e")


def p26_type():
    p = xpanel()
    h.check("the circle picked by itself", p.target is not None, p.message.text())
    h.check("Join out of the slope", p.operation.currentText() == "Join", p.operation.currentText())
    h.check("distance arrow and taper handle", {"distance", "taper"} <= set(p.draggers))
    ui.type_into(p.distance.widget, "5")


def p26_ok():
    want = s["prism"] + 45.0 * math.pi
    h.check(
        "boss r3 x 5 square to the slope", near(h.solid_volume(), want), (h.solid_volume(), want)
    )
    h.shot("p26-boss")
    h.task_button("OK")


def p26_edit():
    h.check("kept", not dialog_open())
    titles = ui.timeline_titles()
    s["boss"] = [t for t in titles if t.startswith("Extrude")][-1]
    h.check("double-click %s" % s["boss"], ui.double_click_timeline(s["boss"]), titles)


def p26_taper():
    p = xpanel()
    h.check("editing the boss", p is not None and p.editing and not p._closed)
    if p is not None and p.editing:
        ui.type_into(p.taper.widget, "-10")


def p26_taper_ok():
    want = s["prism"] + frustum_cone(3.0, 5.0, -10.0)
    h.check("tapered boss narrows", near(h.solid_volume(), want, 1e-6), (h.solid_volume(), want))
    h.task_button("OK")


def p26_pp():
    h.check("kept", not dialog_open())
    s["volume"] = h.solid_volume()
    h.click_empty()
    h.press("q")


def p26_pp_end():
    h.fit()
    h.click(s["centre"] + NORMAL * 5.0 + V(0, 0.5, 0))


def p26_pp_type():
    p = ppanel()
    h.check("the boss's end picked", p.target is not None and len(p.names) == 1, p.message.text())
    ui.type_into(p.field.widget, "2")


def p26_pp_ok():
    p = ppanel()
    want = s["prism"] + frustum_cone(3.0, 7.0, -10.0)
    h.check(
        "the end moved 2 out and the tapered side followed it (no step)",
        near(h.solid_volume(), want, 1e-6),
        (h.solid_volume(), want, p.message.text()),
    )
    h.check("no warning or note", p.message.text() == "", p.message.text())
    h.task_button("OK")


def p26_done():
    h.check("kept", not dialog_open())
    h.check("nothing in error", not broken(), broken())
    h.shot("p26-end")


h.run(
    "extrude_presspull_qa6",
    [
        new_design,
        pick_xz,
        draw_trapezoid,
        finish,
        extrude_prism,
        prism_depth,
        prism_ok,
        prism_done,
        p25_pick_slope,
        p25_type,
        p25_ok,
        p26_sketch,
        p26_pick,
        p26_circle,
        p26_finish,
        p26_e,
        p26_type,
        p26_ok,
        p26_edit,
        p26_taper,
        p26_taper_ok,
        p26_pp,
        p26_pp_end,
        p26_pp_type,
        p26_pp_ok,
        p26_done,
    ],
)
