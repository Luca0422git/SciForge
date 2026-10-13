# SPDX-License-Identifier: LGPL-2.1-or-later
"""A hole cut while the marker is rolled back before a fillet (Fusion: Extrude switches
to Cut by itself when it goes into the part).

Box 40 x 30 x 10, r3 round on the front top edge. Drag the marker before the fillet.
Create Sketch on the top, a circle r5, E, type -4: the extrude goes into the part and
becomes a Cut. (Before, the dialog refused: "... is used by Fillet", because the fillet
rounds the edges of the step before it.) OK, marker to the end: the hole and the round
are both there and nothing is red.

Numbers by hand: box 40*30*10 = 12000; an r3 round along a 40 mm edge removes
40*9*(1 - pi/4); the hole is pi*5^2*4 = 100 pi."""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector
BOX = 12000.0
HOLE = math.pi * 25.0 * 4.0
FRONT_TOP = V(20, 0, 10)


def round_off(r):
    return 40.0 * b.spandrel(r)


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def setup():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("RolledCut")
    body = commands.ensure_body()
    sk = sketch_ui.create_sketch(body, (sketch_ui.origin_planes(body)["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    extrude.make(body, sk, {"distance": 10.0})
    App.ActiveDocument.recompute()
    h.fit()


def fillet_start():
    h.click_empty()
    h.ribbon("Fillet")


def fillet_edge():
    h.fit()
    h.click_edge(FRONT_TOP)


def fillet_radius():
    p = b.blend_panel()
    h.check("fillet dialog has the edge", p is not None and len(p.refs) == 1, p and p.refs)
    if p is not None:
        ui.type_into(p.radius.widget, "3")


def fillet_ok():
    h.task_button("OK")


def roll_back():
    h.check("box with an r3 round", t.near(t.volume(), BOX - round_off(3)), t.volume())
    t.drag_marker(before_title="Fillet 1")


def sketch_start():
    h.check("rolled back before the fillet", t.near(t.volume(), BOX), t.volume())
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_top():
    h.fit()
    h.click(V(20, 15, 10))


def circle():
    sk = h.in_sketch()
    h.check("sketch on the top face", sk is not None)
    if sk:
        x, y = h.to_sketch(sk, V(20, 15, 10))
        h.draw_circle(sk, x, y, 5)


def finish():
    h.ribbon("Finish Sketch")


def extrude_start():
    h.fit()
    h.press("e")


def into_the_part():
    p = xpanel()
    h.check("Extrude picked the circle", p is not None and len(p.profiles) == 1)
    if p is not None:
        ui.type_into(p.distance.widget, "-4")


def is_cut():
    p = xpanel()
    h.check("into the part: Cut", p is not None and p.operation.currentText() == "Cut")
    h.check(
        "no refusal in the dialog", p is not None and not p.message.text(), p and p.message.text()
    )
    h.check("the hole is in the preview", t.near(t.volume(), BOX - HOLE), t.volume())
    h.task_button("OK")


def marker_end():
    h.check("dialog closed", not t.dialog_open())
    t.drag_marker(to_end=True)


def all_there():
    h.check("hole and round", t.near(t.volume(), BOX - HOLE - round_off(3)), t.volume())
    i = t.item("Fillet 1")
    h.check(
        "the round still works", i is not None and i.status == "ok", i and (i.status, i.message)
    )
    h.check("nothing red", all(st[1] != "error" for st in t.states().values()), t.states())
    t.no_popups("a cut while rolled back")
    h.shot("1-cut-and-round")


STEPS = [
    setup,
    fillet_start,
    fillet_edge,
    fillet_radius,
    fillet_ok,
    roll_back,
    sketch_start,
    pick_top,
    circle,
    finish,
    extrude_start,
    into_the_part,
    is_cut,
    marker_end,
    all_there,
]

h.run("timeline_rolled_cut", t.watched(STEPS))
