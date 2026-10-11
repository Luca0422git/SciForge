# SPDX-License-Identifier: LGPL-2.1-or-later
"""A sketch on a face hangs on the step that made the face (Fusion), not on the last step.

Block 40 x 30 x 10, a hole drilled in its top. Create Sketch, click the top beside the
hole: the sketch is on the block's top (the Extrude), not on the Hole. A circle r 3, E, 5,
OK: a boss. Suppress the hole in the timeline: the sketch and the boss stay (before, the
sketch hung on the hole, and suppressing the unrelated hole took the sketch and the boss
along; found by the hole QA).

Hand-derived: block 40*30*10 = 12000; boss pi*9*5 = 141.371...; with the hole suppressed
the part is block + boss."""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
BOSS = math.pi * 9.0 * 5.0


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def timeline_button(name):
    from sciforge import timeline_ui

    tl = timeline_ui.widget()
    tl.refresh()
    QtWidgets.QApplication.processEvents()
    for b in tl._buttons:
        if b.item.name == name:
            return b
    h.check("timeline shows %s" % name, False, tl.titles())
    return None


def setup():
    from sciforge import commands, extrude, hole, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("EarliestFace")
    body = commands.ensure_body()
    sk = sketch_ui.create_sketch(body, (sketch_ui.origin_planes(body)["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    s["block"] = extrude.make(body, sk, {"distance": 10.0})
    doc.recompute()
    top = [
        "Face%d" % (i + 1)
        for i, f in enumerate(s["block"].Shape.Faces)
        if abs(f.CenterOfMass.z - 10) < 1e-6
    ][0]
    s["hole"] = hole.make_single(body, s["block"], top, V(10, 10, 10))
    doc.recompute()
    s["drilled"] = h.solid_volume()
    h.check("the hole cut the block", s["drilled"] < 12000.0 - 1.0, s["drilled"])
    h.fit()


def create_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def click_top():
    h.click(V(30, 20, 10))


def on_the_block():
    sk = h.in_sketch()
    s["sketch"] = sk
    h.check("sketch open", sk is not None)
    if sk is not None:
        support = sk.AttachmentSupport[0][0] if sk.AttachmentSupport else None
        h.check(
            "it hangs on the block's top (the Extrude), not on the Hole",
            support is s["block"],
            support and support.Name,
        )
        x, y = h.to_sketch(sk, V(30, 20, 10))
        h.draw_circle(sk, x, y, 3)


def finish():
    h.ribbon("Finish Sketch")


def extrude_start():
    h.fit()
    h.press("e")


def boss_5():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("Extrude took the circle", p is not None and p.target is not None)
    if p is not None:
        ui.type_into(p.distance.widget, "5")


def ok():
    h.task_button("OK")


def boss_made():
    v = h.solid_volume()
    h.check("boss on the drilled block", near(v, s["drilled"] + BOSS), v)
    button = timeline_button(s["hole"].Name)
    if button is not None:
        w.right_click(button, w.center(button), "Suppress Features")


def hole_suppressed():
    v = h.solid_volume()
    h.check("hole suppressed: block + boss", near(v, 12000.0 + BOSS), v)
    sk = s["sketch"]
    from sciforge import timeline_ops

    h.check("the sketch is not suppressed", not timeline_ops.is_suppressed(sk))
    bad = [o.Name for o in App.ActiveDocument.Objects if "Invalid" in o.State]
    h.check("nothing in error", not bad, bad)
    h.shot("1-hole-suppressed")


h.run(
    "sketch_earliest_face",
    [
        setup,
        create_sketch,
        click_top,
        on_the_block,
        finish,
        extrude_start,
        boss_5,
        ok,
        boss_made,
        hole_suppressed,
    ],
)
