# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tangent Chain off, and the refusals of Variable on a closed tangent chain. A slot (two
straight sides, two half circles) has one closed chain of tangent edges round its top.
With Tangent Chain on (Fusion's default) a click on the straight edge rounds the whole loop;
turned off, only that straight edge is rounded (OpenCASCADE always rounds the whole chain:
SciForge puts the material back along the other edges, cut square at the corner). Variable
on the closed loop is refused with the reason; with Tangent Chain off it works on the one
edge. Continuity G2 and Corner Type Setback are greyed with the reason. Only real input.

A round of radius r on an outside 90 degree edge of length L removes L r^2 (1 - pi/4); on
the rim of a round boss of radius R it removes, by Pappus, 2 pi (R - xbar) r^2 (1 - pi/4)
(xbar: the centroid of the round's cross-section from the face, blend_steps.xbar)."""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fillet2_steps as f2
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
SIDE = V(20, 10, 10)  # the front straight edge of the slot's top


def profile(sketch):
    b.draw_slot(sketch, 10, 15, 30, 15, 10)


def loop(r):
    return 40 * b.spandrel(r) + 2 * math.pi * (5 - b.xbar(r)) * b.spandrel(r)


def selected():
    return sum(len(x.SubElementNames) for x in Gui.Selection.getSelectionEx())


def start():
    s["v0"] = h.solid_volume()
    h.check("slot made", b.close(s["v0"], 2000 + 250 * math.pi), s["v0"])
    Gui.Selection.clearSelection()
    h.fit()
    h.press("f")


def pick():
    p = b.blend_panel()
    if p:
        greyed = [
            box.itemText(i)
            for box in (p.continuity, p.corner)
            for i in range(box.count())
            if not box.model().item(i).isEnabled()
        ]
        h.check("G2 and Setback greyed (kernel)", greyed == ["Curvature (G2)", "Setback"], greyed)
        h.check(
            "Tangent Chain on and can be turned off", p.chain.isChecked() and p.chain.isEnabled()
        )
    h.click_edge(SIDE)


def chain_on():
    v = h.solid_volume()
    h.check("Tangent Chain on: the whole loop is rounded", b.close(v, s["v0"] - loop(1)), v)
    h.check("the whole loop is highlighted", selected() == 4, selected())
    p = b.blend_panel()
    if p:
        f2.click_check(p.chain)


def chain_off():
    p = b.blend_panel()
    v = h.solid_volume()
    expect = s["v0"] - 20 * b.spandrel(1)
    h.check("Tangent Chain off: only the straight edge is rounded", b.close(v, expect), (v, expect))
    h.check("only the picked edge is highlighted", selected() == 1, selected())
    h.check("SciForge's step for Tangent Chain off", p is not None and f2.is_sets(p.target))
    h.check("valid solid", h.body().Shape.isValid())
    h.shot("1-chain-off")
    if p:
        f2.click_check(p.chain)


def chain_back_on():
    p = b.blend_panel()
    h.check("on again: the loop", b.close(h.solid_volume(), s["v0"] - loop(1)), h.solid_volume())
    if p:
        b.choose(p.radius_type, "Variable")


def variable_refused():
    p = b.blend_panel()
    text = p.message.text() if p else ""
    h.check(
        "Variable on the closed loop is refused with the reason", "all the way round" in text, text
    )
    h.check("the preview keeps the last good result", b.close(h.solid_volume(), s["v0"] - loop(1)))
    h.task_button("OK")


def ok_refused():
    p = b.blend_panel()
    h.check("OK waits", p is not None)
    if p:
        f2.click_check(p.chain)


def variable_one_edge():
    p = b.blend_panel()
    h.check(
        "Tangent Chain off: no refusal",
        p is not None and p.message.text() == "",
        p and p.message.text(),
    )
    if p:
        b.type_into(p.start_field.widget, "0.5")


def variable_end():
    p = b.blend_panel()
    if p:
        b.type_into(p.end_field.widget, "1.5")


def variable_done():
    v = h.solid_volume()
    low, high = s["v0"] - 20 * b.spandrel(1.5), s["v0"] - 20 * b.spandrel(0.5)
    h.check("variable 0.5 -> 1.5 on the straight edge only", low < v < high, (low, v, high))
    r = [f2.radius_at(V(x, 10, 10)) for x in (12, 20, 28)]
    h.check(
        "the radius grows from start to end, about 1 in the middle",
        r[0] < r[1] < r[2] and abs(r[1] - 1.0) < 0.1,
        r,
    )
    h.check("valid solid", h.body().Shape.isValid())
    p = b.blend_panel()
    if p:
        b.choose(p.radius_type, "Constant")


def constant():
    p = b.blend_panel()
    if p:
        b.type_into(p.radius.widget, "1")


def ok():
    h.task_button("OK")


def after_ok():
    v = h.solid_volume()
    h.check("kept: straight edge only", b.close(v, s["v0"] - 20 * b.spandrel(1)), v)
    steps = f2.steps()
    h.check(
        "the step keeps Tangent Chain off",
        len(steps) == 1 and f2.spec_of(steps[0])["tangent_chain"] is False,
        steps and f2.spec_of(steps[0]),
    )
    s["v"] = v
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.check("Ctrl+Z", b.close(h.solid_volume(), s["v0"]) and not f2.steps())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check("Ctrl+Y", b.close(h.solid_volume(), s["v"]))
    h.fit()
    b.timeline_double_click("Fillet 1", click_first=True)


def edit_open():
    p = b.blend_panel()
    h.check(
        "edit: Tangent Chain shown off, one edge highlighted",
        p is not None and not p.chain.isChecked() and selected() == 1,
        (p and p.chain.isChecked(), selected()),
    )
    h.press(QtCore.Qt.Key_Escape)


def end():
    h.check("Esc: unchanged", b.close(h.solid_volume(), s["v"]))
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())


h.run(
    "fillet2_chain",
    b.box_steps("Chain", profile=profile)
    + [
        start,
        pick,
        chain_on,
        chain_off,
        chain_back_on,
        variable_refused,
        ok_refused,
        variable_one_edge,
        variable_end,
        variable_done,
        constant,
        ok,
        after_ok,
        undone,
        redone,
        edit_open,
        end,
    ],
)
