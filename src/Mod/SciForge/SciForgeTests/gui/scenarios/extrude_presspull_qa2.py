# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude and Press Pull on real parts (QA, only real input).

Path 7, a part made of several features: box, fillet, Press Pull the end face next to
        the fillet, a hole cut through All, Press Pull the hole's wall to widen it, then
        the first extrude made taller from the timeline: every later step follows.
Path 8, two bodies: New Body on the block's top (it becomes the active body), Press Pull
        on a face of the other body, an extrude whose sketch sits on the new body joins
        that body, the New Body extrude switched to Join from the timeline and back
        with undo.
Path 9, a ring-only extrude whose sketch is edited afterwards (the ring stays the ring),
        Intersect, save, close, reopen, edit the Intersect again.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
SPANDREL2 = 4.0 * (1.0 - math.pi / 4.0)  # a radius-2 round on a square edge


def xpanel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def ppanel():
    from sciforge import presspull_ui

    return presspull_ui.PressPullPanel.last


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def bodies():
    return doc().findObjects("PartDesign::Body")


def body_named(label):
    for b in bodies():
        if b.Label == label:
            return b
    return None


def vol(body):
    try:
        return body.Shape.Volume
    except Exception:
        return 0.0


def dialog_open():
    return bool(Gui.Control.activeDialog())


def step(fn, name):
    fn.__name__ = name
    return fn


def sketch_on(tag, point, draw_fn):
    """Create Sketch, click the plane/face at `point`, draw_fn(sketch), Finish Sketch."""

    def create():
        h.click_empty()
        h.ribbon("Create Sketch")

    def pick():
        h.fit()
        h.click(point)

    def draw():
        sk = h.in_sketch()
        h.check("sketch %s open" % tag, sk is not None)
        if sk:
            draw_fn(sk)
            s["sketch_" + tag] = sk

    def finish():
        h.ribbon("Finish Sketch")

    def after():
        h.check("left sketch %s" % tag, h.in_sketch() is None)
        h.fit()

    return [
        step(create, "sketch_%s_create" % tag),
        step(pick, "sketch_%s_pick" % tag),
        step(draw, "sketch_%s_draw" % tag),
        step(finish, "sketch_%s_finish" % tag),
        step(after, "sketch_%s_after" % tag),
    ]


def rect(x0, y0, x1, y1, z):
    def draw(sk):
        ax, ay = h.to_sketch(sk, V(x0, y0, z))
        bx, by = h.to_sketch(sk, V(x1, y1, z))
        h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    return draw


def circle(cx, cy, r, z):
    def draw(sk):
        x, y = h.to_sketch(sk, V(cx, cy, z))
        h.draw_circle(sk, x, y, r)

    return draw


def extrude_steps(tag, distance, check=None):
    """E (the newest sketch's only profile is taken), type the distance, OK."""

    def press():
        h.fit()
        h.press("e")

    def typed():
        p = xpanel()
        h.check(
            "extrude %s: profile picked by itself" % tag, p.target is not None, p.message.text()
        )
        ui.type_into(p.distance.widget, "%g" % distance)

    def ok():
        h.task_button("OK")

    def done():
        h.check("extrude %s closed" % tag, not dialog_open())
        if check:
            check()

    return [
        step(press, "extrude_%s" % tag),
        step(typed, "extrude_%s_type" % tag),
        step(ok, "extrude_%s_ok" % tag),
        step(done, "extrude_%s_done" % tag),
    ]


# -- Path 7: several features, then an early edit -------------------------------------------
def p7_new():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("QAParts")
    h.fit()


def p7_box_done():
    h.check("box 40 x 30 x 10", near(h.solid_volume(), 12000.0), h.solid_volume())


def p7_fillet():
    h.click_empty()
    h.fit()
    h.click_edge(V(20, 0, 10))


def p7_fillet_key():
    h.check("front top edge selected", len(Gui.Selection.getSelectionEx()) == 1)
    h.press("f")


def p7_fillet_radius():
    from SciForgeTests.gui import blend_steps as b

    p = b.blend_panel()
    h.check("Fillet started on the edge", p is not None and len(p.refs) == 1)
    if p is not None:
        b.type_into(p.radius.widget, "2")


def p7_fillet_ok():
    h.task_button("OK")


def p7_fillet_done():
    want = 12000.0 - 40.0 * SPANDREL2
    h.check("round r2 on the 40 mm edge", near(h.solid_volume(), want), (h.solid_volume(), want))
    s["volume"] = h.solid_volume()
    h.click_empty()
    h.press("q")


def p7_pp_end():
    h.fit()
    h.click(V(40, 15, 5))


def p7_pp_end_type():
    p = ppanel()
    h.check("right end face picked", p.target is not None and len(p.names) == 1, p.message.text())
    ui.type_into(p.field.widget, "5")


def p7_pp_end_ok():
    want = s["volume"] + 5.0 * (300.0 - SPANDREL2)
    h.check(
        "the end moves 5 and the round follows it",
        near(h.solid_volume(), want),
        (h.solid_volume(), want, ppanel().message.text()),
    )
    h.shot("p7-end-pulled")
    h.task_button("OK")


def p7_pp_end_done():
    s["volume"] = h.solid_volume()
    h.check("Press Pull kept", not dialog_open())


def p7_hole_cut():
    p = xpanel()
    h.check("hole profile picked by itself", p.target is not None, p.message.text())
    h.check("choose Operation: Cut", ui.choose(p.operation, "Cut"))
    h.check("choose Extent: All", ui.choose(p.extent, "All"))


def p7_hole_flip():
    p = xpanel()
    want = s["volume"] - 16.0 * math.pi * 10.0
    if not near(h.solid_volume(), want):
        ui.click(p.flip)  # All goes the way the distance pointed: flip it down into the part
    s["hole_want"] = want


def p7_hole_ok():
    h.check(
        "a through hole r4",
        near(h.solid_volume(), s["hole_want"]),
        (h.solid_volume(), s["hole_want"], xpanel().message.text()),
    )
    h.task_button("OK")


def p7_hole_done():
    s["volume"] = h.solid_volume()
    h.check("hole kept", not dialog_open())
    h.click_empty()
    h.press("q")


def p7_pp_hole():
    h.fit()
    # The far wall of the hole as seen from the camera (iso view looks from +x -y +z).
    h.click(V(20 - 4.0 * math.cos(math.radians(30)), 15 + 4.0 * math.sin(math.radians(30)), 6))


def p7_pp_hole_type():
    p = ppanel()
    h.check("the hole's wall picked", p.target is not None and len(p.names) == 1, p.message.text())
    ui.type_into(p.field.widget, "-1")


def p7_pp_hole_ok():
    want = s["volume"] - (25.0 - 16.0) * math.pi * 10.0
    h.check(
        "the wall pushed back 1: hole r5",
        near(h.solid_volume(), want),
        (h.solid_volume(), want, ppanel().message.text()),
    )
    h.shot("p7-hole")
    h.task_button("OK")


def p7_pp_hole_done():
    h.check("hole Press Pull kept", not dialog_open())
    h.check(
        "double-click Extrude 1 (the first step)",
        ui.double_click_timeline("Extrude 1"),
        ui.timeline_titles(),
    )


def p7_edit_first():
    p = xpanel()
    h.check("editing the first extrude", p is not None and p.editing and not p._closed)
    if p is not None and p.editing:
        ui.type_into(p.distance.widget, "14")


def p7_edit_first_ok():
    h.task_button("OK")


def p7_all_followed():
    want = 40 * 30 * 14 - 40.0 * SPANDREL2 + 5.0 * (30 * 14 - SPANDREL2) - 25.0 * math.pi * 14
    h.check(
        "every later step follows the taller block",
        near(h.solid_volume(), want, 1e-5),
        (h.solid_volume(), want),
    )
    bad = [o.Label for o in h.body().Group if "Invalid" in o.State or "Error" in o.State]
    h.check("no step in error", not bad, bad)
    h.shot("p7-edited")


# -- Path 8: two bodies ---------------------------------------------------------------------
def p8_new():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("QABodies")
    h.fit()


def p8_new_body():
    p = xpanel()
    h.check("square on the block picked by itself", p.target is not None, p.message.text())
    h.check("choose Operation: New Body", ui.choose(p.operation, "New Body"))


def p8_new_body_ok():
    h.check("two bodies in the preview", len(bodies()) == 2, [b.Label for b in bodies()])
    h.task_button("OK")


def p8_new_body_done():
    from sciforge import commands

    h.check("two bodies", len(bodies()) == 2, [b.Label for b in bodies()])
    first = body_named("Body")
    second = commands.active_body()
    s["first"], s["second"] = first, second
    h.check("the new body is active", second is not None and second is not first)
    h.check("new body 10 x 10 x 10", near(vol(second), 1000.0), vol(second))
    h.check("first body untouched", near(vol(first), 12000.0), vol(first))
    h.check(
        "the first body is still drawn", first.Tip is not None and first.Tip.ViewObject.Visibility
    )
    h.shot("p8-new-body")
    h.click_empty()
    h.press("q")


def p8_pp_other_body():
    h.fit()
    h.click(V(5, 5, 10))  # the first body's top, the new body is active


def p8_pp_other_type():
    p = ppanel()
    h.check(
        "Press Pull takes a face of the other body",
        p.target is not None and len(p.names) == 1,
        p.message.text(),
    )
    ui.type_into(p.field.widget, "2")


def p8_pp_other_ok():
    h.check("first body top +2", near(vol(s["first"]), 14400.0), vol(s["first"]))
    h.check("new body untouched", near(vol(s["second"]), 1000.0), vol(s["second"]))
    h.task_button("OK")


def p8_pp_other_done():
    h.check("kept", near(vol(s["first"]), 14400.0) and not dialog_open())
    h.check(
        "the Press Pull is in the first body",
        any(o.Label.startswith("PressPull") or "Press" in o.Label for o in s["first"].Group),
        [o.Label for o in s["first"].Group],
    )


def p8_join_on_second_check():
    h.check(
        "an extrude of a sketch on the new body joins the new body",
        near(vol(s["second"]), 1000.0 + 16.0 * 5.0),
        vol(s["second"]),
    )
    h.check("first body still 14400", near(vol(s["first"]), 14400.0), vol(s["first"]))


def p8_edit_new_body():
    h.check(
        "double-click Extrude 2 (the New Body one)",
        ui.double_click_timeline("Extrude 2"),
        ui.timeline_titles(),
    )


def p8_editing_new_body():
    p = xpanel()
    h.check("editing", p is not None and p.editing and not p._closed)
    if p is None or not p.editing:
        return
    h.check("New Body shown", p.operation.currentText() == "New Body", p.operation.currentText())
    h.check("choose Operation: Join", ui.choose(p.operation, "Join"))


def p8_join_refused():
    p = xpanel()
    # The later extrude sits on the new body's face: Fusion keeps it; here the dialog says
    # why the body cannot go away, and nothing breaks.
    h.check(
        "the dialog explains, nothing breaks",
        "⚠" in p.message.text() or len(bodies()) == 2,
        (p.message.text(), [b.Label for b in bodies()]),
    )
    h.task_button("Cancel")


def p8_cancelled():
    h.check("Cancel: two bodies", len(bodies()) == 2, [b.Label for b in bodies()])
    h.check("new body back", near(vol(s["second"]), 1080.0), vol(s["second"]))
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("nothing in error", not bad, bad)


# -- Path 9: ring extrude, sketch edit, intersect, save / reopen ---------------------------------
def p9_new():
    App.newDocument("QARing")
    h.fit()


def p9_e():
    h.fit()
    h.press("e")


def p9_ring():
    h.click(V(3, 3, 0))


def p9_ring_ok():
    p = xpanel()
    want = (1200.0 - 25.0 * math.pi) * 10.0
    h.check("ring only", near(h.solid_volume(), want), (h.solid_volume(), p.message.text()))
    h.task_button("OK")


def p9_edit_sketch():
    h.check("double-click Sketch 1", ui.double_click_timeline("Sketch 1"), ui.timeline_titles())


def p9_change_circle():
    import Part

    sk = h.in_sketch()
    h.check("the sketch opens for editing", sk is not None)
    if sk is None:
        return
    for i, geo in enumerate(sk.Geometry):
        if isinstance(geo, Part.Circle):
            c = geo.copy()
            c.Radius = 8.0
            sk.delGeometry(i)
            sk.addGeometry(c)
            break
    doc().recompute()


def p9_finish():
    h.ribbon("Finish Sketch")


def p9_ring_followed():
    want = (1200.0 - 64.0 * math.pi) * 10.0
    h.check(
        "the ring is still the ring (bigger hole)",
        near(h.solid_volume(), want),
        (h.solid_volume(), want),
    )
    h.fit()


def p9_intersect():
    p = xpanel()
    h.check("square on the ring picked", p.target is not None, p.message.text())
    h.check("choose Operation: Intersect", ui.choose(p.operation, "Intersect"))
    ui.type_into(p.distance.widget, "-6")


def p9_intersect_ok():
    p = xpanel()
    # Square 0..10 x 0..10 on the top, 6 down: the ring's material inside it (no hole there).
    h.check(
        "intersect keeps 10 x 10 x 6",
        near(h.solid_volume(), 600.0),
        (h.solid_volume(), p.message.text()),
    )
    h.shot("p9-intersect")
    h.task_button("OK")


def p9_save():
    h.check("intersect kept", near(h.solid_volume(), 600.0) and not dialog_open())
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-qa-"), "qa_ring.FCStd")
    s["path"] = path
    doc().saveAs(path)
    App.closeDocument(doc().Name)


def p9_open():
    App.openDocument(s["path"])
    h.fit()


def p9_reopened():
    h.check("reopened: 600", near(h.solid_volume(), 600.0), h.solid_volume())
    h.check("double-click Extrude 2", ui.double_click_timeline("Extrude 2"), ui.timeline_titles())


def p9_editing():
    p = xpanel()
    h.check("Intersect editing after reopening", p is not None and p.editing and not p._closed)
    if p is None or not p.editing:
        return
    h.check("Intersect shown", p.operation.currentText() == "Intersect", p.operation.currentText())
    h.check("-6 shown", near(p.distance.value(), -6.0), p.distance.value())
    ui.type_into(p.distance.widget, "-4")


def p9_edit_ok():
    h.check("intersect 10 x 10 x 4", near(h.solid_volume(), 400.0), h.solid_volume())
    h.task_button("OK")


def p9_done():
    h.check("kept", near(h.solid_volume(), 400.0) and not dialog_open())
    h.shot("p9-end")


h.run(
    "extrude_presspull_qa2",
    [
        p7_new,
        *sketch_on("box", V(12, -8, 0), rect(0, 0, 40, 30, 0)),
        *extrude_steps("box", 10, p7_box_done),
        p7_fillet,
        p7_fillet_key,
        p7_fillet_radius,
        p7_fillet_ok,
        p7_fillet_done,
        p7_pp_end,
        p7_pp_end_type,
        p7_pp_end_ok,
        p7_pp_end_done,
        *sketch_on("hole", V(10, 20, 10), circle(20, 15, 4, 10)),
        step(lambda: (h.fit(), h.press("e")), "p7_hole_e"),
        p7_hole_cut,
        p7_hole_flip,
        p7_hole_ok,
        p7_hole_done,
        p7_pp_hole,
        p7_pp_hole_type,
        p7_pp_hole_ok,
        p7_pp_hole_done,
        p7_edit_first,
        p7_edit_first_ok,
        p7_all_followed,
        p8_new,
        *sketch_on("base", V(12, -8, 0), rect(0, 0, 40, 30, 0)),
        *extrude_steps("base", 10),
        *sketch_on("square", V(30, 25, 10), rect(25, 10, 35, 20, 10)),
        step(lambda: (h.fit(), h.press("e")), "p8_square_e"),
        p8_new_body,
        p8_new_body_ok,
        p8_new_body_done,
        p8_pp_other_body,
        p8_pp_other_type,
        p8_pp_other_ok,
        p8_pp_other_done,
        *sketch_on("boss", V(26, 11, 20), rect(28, 13, 32, 17, 20)),
        *extrude_steps("boss", 5, p8_join_on_second_check),
        p8_edit_new_body,
        p8_editing_new_body,
        p8_join_refused,
        p8_cancelled,
        p9_new,
        *sketch_on(
            "ring",
            V(12, -8, 0),
            lambda sk: (rect(0, 0, 40, 30, 0)(sk), circle(20, 15, 5, 0)(sk)),
        ),
        p9_e,
        p9_ring,
        p9_ring_ok,
        p9_edit_sketch,
        p9_change_circle,
        p9_finish,
        p9_ring_followed,
        *sketch_on("square", V(5, 5, 10), rect(0, 0, 10, 10, 10)),
        step(lambda: (h.fit(), h.press("e")), "p9_square_e"),
        p9_intersect,
        p9_intersect_ok,
        p9_save,
        p9_open,
        p9_reopened,
        p9_editing,
        p9_edit_ok,
        p9_done,
    ],
)
