# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tangent chain and Press Pull, only real input: on an extruded slot, F and one click on
a straight top edge picks the whole tangent outline (4 edges light up), drag the arrow,
OK. Then click the new round face and press Q: Press Pull edits the same fillet's radius
(it stays one timeline step). Volumes by Pappus' rule (see blend_steps)."""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
LS, W = 20.0, 5.0  # slot: straight length between centres, half width
SLOT = (LS * 2 * W + math.pi * W * W) * 10


def rounded(r):
    return SLOT - b.spandrel(r) * (2 * LS + 2 * math.pi * (W - b.xbar(r)))


def slot(sk):
    b.draw_slot(sk, 10, 15, 30, 15, 2 * W)


def fillet_start():
    h.click_empty()
    h.press("f")


def click_straight_edge():
    h.fit()
    h.click(V(20, 10, 10))


def chain_picked():
    p = b.blend_panel()
    h.check("one pick", p is not None and len(p.refs) == 1, p and p.refs)
    shown = sum(len(x.SubElementNames) for x in Gui.Selection.getSelectionEx())
    h.check("its tangent chain lights up: 4 edges", shown == 4, shown)
    v = h.solid_volume()
    h.check("preview rounds the whole outline (r 1)", b.close(v, rounded(1)), (v, rounded(1)))
    h.shot("1-chain")
    if p:
        b.type_into(p.radius.widget, "2")


def ok():
    """Click on empty canvas and press Enter: Enter over the 3D view finishes, like Fusion."""
    h.click_empty()
    h.press(QtCore.Qt.Key_Return)


def after_ok():
    h.check("Enter over the 3D view finished the dialog", not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("slot outline rounded r 2", b.close(v, rounded(2)), (v, rounded(2)))
    h.check("10 faces", len(h.body().Shape.Faces) == 10, len(h.body().Shape.Faces))


def click_round_face():
    h.fit()
    # middle of the round along the y = 10 side: axis at y = 12, z = 8, 45 degrees up
    h.click(V(20, 12 - 2 * math.sqrt(0.5), 8 + 2 * math.sqrt(0.5)))


def press_q():
    sel = [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]
    h.check("the round face is selected", len(sel) == 1 and sel[0][1][0].startswith("Face"), sel)
    h.press("q")


def type_radius():
    fields = b.task_spinboxes()
    if h.check("Press Pull shows a size field", fields, fields):
        b.type_into(fields[0], "3")


def pp_ok():
    h.task_button("OK")


def after_pp():
    v = h.solid_volume()
    h.check("Press Pull changed the fillet's radius to 3", b.close(v, rounded(3)), (v, rounded(3)))
    h.check(
        "still a single Fillet step",
        len(b.blends()) == 1 and h.body().Tip is b.blends()[0],
        [o.Name for o in h.body().Group],
    )
    h.check(
        "no kernel errors in the Report view",
        not b.report_has_kernel_errors(),
        b.report_has_kernel_errors(),
    )
    h.shot("2-end")


h.run(
    "fillet_chain",
    b.box_steps("FilletChain", profile=slot)
    + [
        fillet_start,
        click_straight_edge,
        chain_picked,
        ok,
        after_ok,
        click_round_face,
        press_q,
        type_radius,
        pp_ok,
        after_pp,
    ],
)
