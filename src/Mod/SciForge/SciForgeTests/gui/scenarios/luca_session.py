# SPDX-License-Identifier: LGPL-2.1-or-later
"""Luca's session of 2026-10-10, only real buttons/keys/clicks: sketch on XY,
Finish Sketch, extrude, extrude again (face), sketch on the part, Finish Sketch,
extrude the new sketch. Reported: second extrude makes the part disappear,
Finish Sketch on a face sketch errors, errors everywhere."""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Luca")
    h.fit()


def create_sketch_xy():
    h.ribbon("Create Sketch")


def pick_xy():
    h.check("no pop-up", not h.popups(), h.popups())
    h.click(V(12, -8, 0))


def draw_rect():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)
        s["sk1"] = sk
    h.shot("1-sketch")


def finish_sketch_1():
    h.ribbon("Finish Sketch")


def after_finish_1():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()


def extrude_1():
    h.press("e")


def extrude_1_drag():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("extrude 1 has a target", p is not None and p.target is not None)
    if p and p.dragger:
        h.fit()
        head = V(20, 15, p.dragger.distance() + p.dragger.size * 0.9)
        a = h.screen_point(head)
        h.drag(a, a.__class__(a.x(), a.y() - 40))


def extrude_1_ok():
    h.task_button("OK")


def check_1():
    h.check("part visible after extrude 1", h.body_visible())
    s["v1"] = h.solid_volume()
    h.check("extrude 1 volume > 12000", s["v1"] > 12000, s["v1"])
    h.shot("2-extrude1")
    h.fit()


def extrude_2():
    h.press("e")


def extrude_2_click_top():
    h.fit()
    top = h.body().Shape.BoundBox.ZMax
    h.click(V(20, 15, top))


def extrude_2_drag():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("extrude 2 picked the face", p is not None and p.target is not None)
    if p and p.dragger:
        h.fit()
        top = h.body().Shape.BoundBox.ZMax
        a = h.screen_point(V(20, 15, top + p.dragger.distance() + p.dragger.size * 0.9))
        h.drag(a, a.__class__(a.x(), a.y() - 30))
    h.shot("3-extrude2-preview")


def extrude_2_ok():
    h.task_button("OK")


def check_2():
    h.check("part visible after extrude 2", h.body_visible())
    v = h.solid_volume()
    feats = [
        (
            o.Name,
            o.TypeId,
            getattr(o, "Profile", None),
            getattr(o, "Length", None),
            getattr(o, "Reversed", None),
        )
        for o in h.body().Group
        if o.TypeId.startswith("PartDesign::P")
    ]
    h.check("extrude 2 added material", v > s["v1"], (v, s["v1"], feats))
    s["v2"] = v
    h.shot("4-extrude2")
    h.fit()


def create_sketch_face():
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_top_face():
    h.fit()
    top = h.body().Shape.BoundBox.ZMax
    s["top"] = top
    h.click(V(20, 15, top))


def draw_circle():
    sk = h.in_sketch()
    h.check("sketch open on the top face", sk is not None)
    if sk:
        x, y = h.to_sketch(sk, V(20, 15, s["top"]))
        h.draw_circle(sk, x, y, 5)
    h.shot("5-sketch2")


def finish_sketch_2():
    h.ribbon("Finish Sketch")


def after_finish_2():
    h.check("left sketch 2", h.in_sketch() is None)
    h.check("part visible after sketch 2", h.body_visible())
    h.shot("6-after-sketch2")
    h.fit()


def extrude_3():
    h.press("e")


def extrude_3_ok():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("extrude 3 picked the circle", p is not None and p.target is not None)
    h.task_button("OK")


def check_3():
    h.check("part visible after extrude 3", h.body_visible())
    v = h.solid_volume()
    h.check("extrude 3 added a boss", v > s["v2"], (v, s["v2"]))
    h.shot("7-end")


h.run(
    "luca",
    [
        new_design,
        create_sketch_xy,
        pick_xy,
        draw_rect,
        finish_sketch_1,
        after_finish_1,
        extrude_1,
        extrude_1_drag,
        extrude_1_ok,
        check_1,
        extrude_2,
        extrude_2_click_top,
        extrude_2_drag,
        extrude_2_ok,
        check_2,
        create_sketch_face,
        pick_top_face,
        draw_circle,
        finish_sketch_2,
        after_finish_2,
        extrude_3,
        extrude_3_ok,
        check_3,
    ],
)
