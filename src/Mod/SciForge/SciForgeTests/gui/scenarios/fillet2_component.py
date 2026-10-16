# SPDX-License-Identifier: LGPL-2.1-or-later
"""Radius sets inside a component: a box at the root, a second block made by Extrude >
New Component (Component1, Body1), then F with two sets on the component's block (r 1 and
r 2). The step goes into the component's body, the root box is untouched; OK, Ctrl+Z /
Ctrl+Y, edit from the timeline. Only real input.

Volumes: the block is 20 x 20 x 8 = 3200; a round of radius r along a 20 mm edge removes
20 r^2 (1 - pi/4)."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import fillet2_steps as f2
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import timeline_input as t

V = App.Vector
s = {}
BLOCK = 3200.0
FRONT = V(70, 0, 8)
BACK = V(70, 20, 8)


def block(r1, r2):
    return BLOCK - 20 * b.spandrel(r1) - 20 * b.spandrel(r2)


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def sketch2():
    h.fit()
    h.ribbon("Create Sketch")


def plane():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def draw():
    sk = h.in_sketch()
    h.check("sketch open", sk is not None)
    if sk is not None:
        h.draw_rectangle(sk, 60, 0, 80, 20)


def finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def new_component():
    p = xpanel()
    if h.check("extrude dialog", p is not None):
        ui.choose(p.operation, "New Component")


def distance():
    h.check("distance typed", ai.give_distance("8"))


def extrude_ok():
    h.task_button("OK")


def made():
    body = h.body()
    h.check(
        "Component1's body is active",
        body is not None and cs.container_label(body) == "Component1",
        body and cs.container_label(body),
    )
    h.check("block 3200", body is not None and cs.near(cs.volume(body), BLOCK))
    s["body"] = body.Name if body else None
    s["root"] = [x.Name for x in cs.bodies() if x is not body]
    h.fit()
    h.press("f")


def pick_front():
    h.click_edge(FRONT)


def plus():
    p = b.blend_panel()
    h.check("front edge picked in the component's body", p is not None and len(p.refs) == 1)
    if p:
        b.type_into(p.radius.widget, "1")
        f2.press_plus(p)


def pick_back():
    h.click_edge(BACK)


def radius_2():
    p = b.blend_panel()
    h.check("set 2 has the back edge", p is not None and len(p.refs) == 1, p and p.refs)
    if p:
        b.type_into(p.radius.widget, "2")


def previewed():
    body = App.ActiveDocument.getObject(s["body"])
    v = cs.volume(body)
    h.check("two sets on the component's block", cs.near(v, block(1, 2)), (v, block(1, 2)))
    p = b.blend_panel()
    h.check("two arrows", p is not None and len(p.arrows) == 2)
    h.shot("1-component")
    h.task_button("OK")


def after_ok():
    body = App.ActiveDocument.getObject(s["body"])
    h.check("kept", cs.near(cs.volume(body), block(1, 2)), cs.volume(body))
    steps = [o for o in body.Group if f2.is_sets(o)]
    h.check("the step is in the component's body", len(steps) == 1, [o.Name for o in body.Group])
    root = [App.ActiveDocument.getObject(n) for n in s["root"]]
    h.check(
        "the root box is untouched",
        all(cs.near(cs.volume(x), 12000.0) for x in root),
        [cs.volume(x) for x in root],
    )
    h.check("timeline shows Fillet 1", "Fillet 1" in t.titles(), t.titles())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    body = App.ActiveDocument.getObject(s["body"])
    h.check("Ctrl+Z", cs.near(cs.volume(body), BLOCK), cs.volume(body))
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    body = App.ActiveDocument.getObject(s["body"])
    h.check("Ctrl+Y", cs.near(cs.volume(body), block(1, 2)), cs.volume(body))
    h.fit()
    t.double_click("Fillet 1")


def edit_open():
    p = b.blend_panel()
    h.check("edit: two sets", p is not None and p.rows.count() == 2)
    if p:
        f2.click_row(p, 0)


def edit_row():
    p = b.blend_panel()
    if p:
        b.type_into(p.radius.widget, "1.5")


def edit_ok():
    h.task_button("OK")


def end():
    body = App.ActiveDocument.getObject(s["body"])
    h.check("set 1 edited to 1.5", cs.near(cs.volume(body), block(1.5, 2)), cs.volume(body))
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())


h.run(
    "fillet2_component",
    b.box_steps("FilletComponent")
    + [
        sketch2,
        plane,
        draw,
        finish,
        extrude,
        new_component,
        distance,
        extrude_ok,
        made,
        pick_front,
        plus,
        pick_back,
        radius_2,
        previewed,
        after_ok,
        undone,
        redone,
        edit_open,
        edit_row,
        edit_ok,
        end,
    ],
)
