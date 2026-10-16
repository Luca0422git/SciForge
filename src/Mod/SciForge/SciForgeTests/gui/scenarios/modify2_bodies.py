# SPDX-License-Identifier: LGPL-2.1-or-later
"""Patterns of an extrude that cut two bodies, the Modify tools in an empty design, and a Shell
across a component, only real input.

Path E, an empty design: MODIFY > Draft, Shell and Scale say what to make first; no dialog.
Path B1, Body1 (x 0..20) and Body2 (x 30..50), each 20 x 20 x 10 (Body2's sketch is beside
        Body1: New Body by itself). A slot sketched on Body1's top across the gap (x 10..40,
        y 2..6), E, -5: Cut through both (Fusion's Objects To Cut): 3800 / 3800.
Path B2, Rectangular Pattern of that cut along Y, Quantity 3, Distance 12: Fusion repeats the
        extrude's change in every body it changed: 3400 / 3400. OK: one pattern step; Body2
        gets its hidden step.
Path B3, Ctrl+Z: 3800 / 3800, no hidden step; Ctrl+Y: 3400 / 3400.
Path B4, the pattern edited from the timeline: Quantity 2: 3600 / 3600. OK.
Path B5, save, close, open again: 3600 / 3600; the pattern deleted from the timeline: 3800 /
        3800 and its step in Body2 goes with it (the cut's own step there stays); the cut
        deleted too: 4000 / 4000, no hidden step left.
Path C1, a sketch beside the bodies, E, Operation New Component, 8: Component1 with a 20 x 20
        x 8 body. MODIFY > Shell, click Body2's top, then the component body's top: one Shell
        over both (the component's body gets the hidden step); OK; Ctrl+Z.

Volumes: a slot 10 x 4 x 5 = 200 per body and copy; an open-topped box a x b x c with an
inside wall t: a b c - (a-2t)(b-2t)(c-t).
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import modify2_steps as m
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
s = {}


def told():
    from sciforge import commands

    return commands._TOLD["msg"] or ""


def body(key):
    return App.ActiveDocument.getObject(s.get(key, "")) if App.ActiveDocument else None


def volumes():
    return m.body_volume(body("b1")), m.body_volume(body("b2"))


def both(v):
    v1, v2 = volumes()
    return m.close(v1, v) and m.close(v2, v)


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def open_box(a, bb, c, t):
    return a * bb * c - (a - 2 * t) * (bb - 2 * t) * (c - t)


# -- E --------------------------------------------------------------------------------------------
def empty_draft():
    bs.new_design("Modify2Bodies")()
    h.click_empty()
    sd.modify_menu("Draft")


def empty_draft_told():
    h.check("Draft: no dialog in an empty design", m.no_dialog())
    h.check("Draft says what to make first", "make one first" in told(), told())
    sd.modify_menu("Shell")


def empty_shell_told():
    h.check("Shell: no dialog", m.no_dialog())
    h.check("Shell says what to make first", told().startswith("Shell needs"), told())
    sd.modify_menu("Scale")


def empty_scale_told():
    h.check("Scale: no dialog", m.no_dialog())
    h.check("Scale says what to make first", told().startswith("Scale needs"), told())


def boxes_made():
    found = m.bodies_list()
    h.check("two bodies", len(found) == 2, [b.Label for b in found])
    if len(found) == 2:
        s["b1"], s["b2"] = found[0].Name, found[1].Name
    h.check("4000 / 4000", both(4000.0), volumes())


# -- B1 -------------------------------------------------------------------------------------------
def slot_sketch():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def slot_top():
    h.click(V(5, 12, 10))  # Body1's top face


def slot_draw():
    sk = h.in_sketch()
    if h.check("sketch on Body1's top", sk is not None):
        ax, ay = h.to_sketch(sk, V(10, 2, 10))
        bx, by = h.to_sketch(sk, V(40, 6, 10))
        h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def slot_finish():
    h.ribbon("Finish Sketch")


def slot_extrude():
    h.fit()
    h.press("e")


def slot_depth():
    p = xpanel()
    if h.check("extrude dialog open", p is not None):
        ui.type_into(p.distance.widget, "-5")


def slot_cut():
    p = xpanel()
    h.check("Cut by itself", p is not None and p.operation.currentText() == "Cut")
    h.check("both cut", both(3800.0), volumes())
    h.task_button("OK")


def slot_made():
    h.check("dialog closed", m.no_dialog())
    h.check("kept: 3800 / 3800", both(3800.0), volumes())
    titles = sd.timeline_titles()
    s["cut"] = titles[-1] if titles else "?"


# -- B2 -------------------------------------------------------------------------------------------
def pattern_start():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.ribbon("Rectangular Pattern")


def click_cut():
    ps.timeline_click(s["cut"])


def direction_box():
    ps.click_box("direction")


def click_y_axis():
    h.fit()
    h.click(V(0, -12, 0))


def three():
    p = ps.panel()
    if p is None:
        return
    h.check("the Y axis is the direction", p.options["direction"] is not None, p.options)
    ps.type_quantity(p.quantity, 3)


def twelve():
    ps.type_value(ps.panel().distance_field.widget, "12")


def both_repeated():
    h.check("the cut repeated in both bodies: 3400 / 3400", both(3400.0), volumes())
    h.shot("1-two-bodies")
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", m.no_dialog())
    h.check("kept", both(3400.0), volumes())
    h.check("Body2 has the hidden step", len(m.followers()) == 1, m.followers())
    h.check("both valid", body("b1").Shape.isValid() and body("b2").Shape.isValid())
    titles = sd.timeline_titles()
    s["pattern"] = [t for t in titles if "Pattern" in t][-1:] or ["?"]
    h.check("one pattern step", len([t for t in titles if "Pattern" in t]) == 1, titles)


# -- B3 -------------------------------------------------------------------------------------------
def undo():
    m.undo()


def after_undo():
    h.check("Ctrl+Z: 3800 / 3800", both(3800.0), volumes())
    h.check("no hidden step", not m.followers(), m.followers())


def redo():
    m.redo()


def after_redo():
    h.check("Ctrl+Y: 3400 / 3400", both(3400.0), volumes())
    h.check("the hidden step is back", len(m.followers()) == 1, m.followers())
    h.fit()


# -- B4 -------------------------------------------------------------------------------------------
def edit():
    ps.timeline_double_click(s["pattern"][0])


def edit_two():
    p = ps.panel()
    if h.check("the pattern opens for editing", p is not None and p.editing):
        ps.type_quantity(p.quantity, 2)


def two():
    h.check("Quantity 2: 3600 / 3600", both(3600.0), volumes())
    h.task_button("OK")


def after_edit():
    h.check("dialog closed", m.no_dialog())
    h.check("kept", both(3600.0), volumes())
    h.check("still one hidden step", len(m.followers()) == 1, m.followers())


# -- B5 -------------------------------------------------------------------------------------------
def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-modify2-"), "bodies.FCStd")
    s["path"] = path
    App.ActiveDocument.saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def close():
    App.closeDocument(App.ActiveDocument.Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    found = m.bodies_list()
    if len(found) == 2:
        s["b1"], s["b2"] = found[0].Name, found[1].Name
    h.check("after reopening: 3600 / 3600", both(3600.0), volumes())
    ti.menu(s["pattern"][0], "Delete")


def after_delete():
    h.check("deleting the pattern: 3800 / 3800", both(3800.0), volumes())
    h.check("its step in Body2 went with it", not m.followers(), m.followers())
    h.check("the cut's own step in Body2 stays", len(extrude_followers()) == 1)
    ti.menu(s["cut"], "Delete")


def cut_deleted():
    h.check("deleting the cut: 4000 / 4000", both(4000.0), volumes())
    h.check("its step in Body2 went with it", not extrude_followers(), extrude_followers())


def extrude_followers():
    from sciforge import extrude_bodies

    return [o.Name for o in App.ActiveDocument.Objects if extrude_bodies.is_follower(o)]


# -- C1 -------------------------------------------------------------------------------------------
def comp_sketch():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def comp_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def comp_draw():
    sk = h.in_sketch()
    if h.check("sketch open", sk is not None):
        h.draw_rectangle(sk, 60, 0, 80, 20)


def comp_finish():
    h.ribbon("Finish Sketch")


def comp_extrude():
    h.fit()
    h.press("e")


def comp_operation():
    p = xpanel()
    if h.check("extrude dialog", p is not None):
        h.check("choose New Component", ui.choose(p.operation, "New Component"))


def comp_distance():
    h.check("distance typed", ai.give_distance("8"))


def comp_ok():
    h.task_button("OK")


def comp_made():
    part = cs.component("Component1")
    h.check("Component1 made", part is not None, [p.Label for p in cs.components()])
    found = [b for b in m.bodies_list() if b.Name not in (s["b1"], s["b2"])]
    h.check("its body", len(found) == 1, [b.Label for b in found])
    if found:
        s["b3"] = found[0].Name
        h.check("20 x 20 x 8", m.close(m.body_volume(found[0]), 3200.0))


def shell_start():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    sd.modify_menu("Shell")


def shell_body2():
    h.click(V(45, 16, 10))  # Body2's top, beside the slot


def shell_component():
    p = m.panel_of("shell_ui", "ShellPanel")
    h.check("Body2's top picked", p is not None and p.body is body("b2"), p and p.body)
    h.click(V(70, 10, 8))


def shell_both():
    p = m.panel_of("shell_ui", "ShellPanel")
    if p is None:
        return
    h.check(
        "the component's body joined the Shell",
        len(p.members) == 1 and p.members[0].body is body("b3"),
        [x.body.Label for x in p.members],
    )
    v3 = m.body_volume(body("b3"))
    h.check("the component's body shelled 1 mm", m.close(v3, open_box(20, 20, 8, 1)), v3)
    v2 = m.body_volume(body("b2"))
    h.check("Body2 shelled 1 mm", m.close(v2, open_box(20, 20, 10, 1)), v2)
    h.check("no message", not m.message(p), m.message(p))
    h.shot("2-component")
    h.task_button("OK")


def shell_ok():
    h.check("dialog closed", m.no_dialog())
    h.check("one hidden step, in the component's body", len(m.followers()) == 1, m.followers())
    follower = m.followers()[0] if m.followers() else None
    h.check(
        "the hidden step is in Component1",
        follower is not None and cs.container_label(follower) == "Component1",
        follower and cs.container_label(follower),
    )
    h.check("valid", body("b2").Shape.isValid() and body("b3").Shape.isValid())


def shell_undone():
    h.check("Ctrl+Z: Body2 4000 again", m.close(m.body_volume(body("b2")), 4000.0))
    h.check("Ctrl+Z: the component's body 3200 again", m.close(m.body_volume(body("b3")), 3200.0))
    h.check("no hidden step", not m.followers(), m.followers())
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("3-end")


h.run(
    "modify2_bodies",
    [
        empty_draft,
        empty_draft_told,
        empty_shell_told,
        empty_scale_told,
    ]
    + bs.box_steps("box1", (0, 0, 20, 20), 10, V(6, -6, 0))
    + bs.box_steps("box2", (30, 0, 50, 20), 10, V(6, -6, 0), new_body=True)
    + [
        boxes_made,
        slot_sketch,
        slot_top,
        slot_draw,
        slot_finish,
        slot_extrude,
        slot_depth,
        slot_cut,
        slot_made,
        pattern_start,
        click_cut,
        direction_box,
        click_y_axis,
        three,
        twelve,
        both_repeated,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_two,
        two,
        after_edit,
        save,
        close,
        reopen,
        reopened,
        after_delete,
        cut_deleted,
        comp_sketch,
        comp_plane,
        comp_draw,
        comp_finish,
        comp_extrude,
        comp_operation,
        comp_distance,
        comp_ok,
        comp_made,
        shell_start,
        shell_body2,
        shell_component,
        shell_both,
        shell_ok,
        undo,
        shell_undone,
    ],
)
