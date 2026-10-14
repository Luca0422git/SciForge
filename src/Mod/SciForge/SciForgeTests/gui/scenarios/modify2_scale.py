# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scale of two bodies in one step and Scale of a sketch (Fusion's Scale takes bodies and
sketches in its Entities box), only real input.

Part: Body1 the 40 x 30 x 10 box (blend_steps.box_steps); Body2 a 20 x 30 x 10 box at x = 50
(Create Sketch on XY, a rectangle, E, 10, OK: it touches nothing, so it is a new body); a
sketch on XY left of them with a rectangle (-30, 0) - (-10, 10), used by nothing.

Path C1, MODIFY > Scale with nothing selected: click Body1 (the Point box takes the next
        click, as before), click the Entities box again, click Body2: both in the Entities
        box; Scale Factor 0.5 about the origin: both bodies half size (1/8 the volume). OK:
        one Scale step in the timeline, Body2 gets its hidden follower step.
Path C2, Ctrl+Z: both full size again in one undo step; Ctrl+Y: both half size.
Path C3, the sketch's browser row clicked, MODIFY > Scale: the dialog opens on the sketch.
        Scale Type Non Uniform: refused with the reason (Fusion scales sketches uniformly);
        back to Uniform, factor 2: the rectangle (-60, 0) - (-20, 20). OK: a Scale step.
        Ctrl+Z: the rectangle as drawn; Ctrl+Y: doubled again.
Path C4, the sketch's Scale edited from the timeline: it reads 2; 1.5 typed: (-45, 0) - (-15, 15)
        from the rectangle as drawn (not from the doubled one). OK.
Path C5, the sketch's Scale deleted from the timeline: the rectangle is as drawn again.

Volumes: Body1 12000 -> 1500, Body2 6000 -> 750 (factor 0.5: x 1/8).
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import modify2_steps as m
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import timeline_input as ti
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}


def panel():
    return m.panel_of("scale_ui", "ScalePanel")


def body1():
    return App.ActiveDocument.getObject(s.get("b1", ""))


def body2():
    return App.ActiveDocument.getObject(s.get("b2", ""))


def volumes():
    return m.body_volume(body1()), m.body_volume(body2())


def sketch():
    return App.ActiveDocument.getObject(s.get("sketch", ""))


def rect():
    """The free sketch's rectangle in the design: (xmin, ymin, xmax, ymax)."""
    sk = sketch()
    if sk is None:
        return None
    box = sk.Shape.BoundBox
    return (round(box.XMin, 6), round(box.YMin, 6), round(box.XMax, 6), round(box.YMax, 6))


def scale_titles():
    return [t for t in sd.timeline_titles() if t.startswith("Scale")]


# -- the second body and the free sketch --------------------------------------------------------
def second_sketch():
    s["b1"] = h.body().Name
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def second_plane():
    h.click(V(12, -8, 0))


def second_draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 50, 0, 70, 30)


def second_finish():
    h.ribbon("Finish Sketch")


def second_extrude():
    h.fit()
    h.press("e")


def second_distance():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None) if p else None
    if h.check("Extrude open", field is not None):
        b.type_into(field, "10")


def second_ok():
    h.task_button("OK")


def two_bodies():
    found = m.bodies_list()
    h.check("two bodies", len(found) == 2, [x.Label for x in found])
    others = [x for x in found if x.Name != s["b1"]]
    if others:
        s["b2"] = others[0].Name
    v1, v2 = volumes()
    h.check("Body1 12000, Body2 6000", m.close(v1, 12000.0) and m.close(v2, 6000.0), (v1, v2))


def free_sketch():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def free_plane():
    h.click(V(12, -8, 0))


def free_draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        s["sketch"] = sk.Name
        h.draw_rectangle(sk, -30, 0, -10, 10)


def free_finish():
    h.ribbon("Finish Sketch")


def free_made():
    h.check("the free rectangle", rect() == (-30, 0, -10, 10), rect())
    h.fit()


# -- C1 -------------------------------------------------------------------------------------------
def scale_start():
    Gui.Selection.clearSelection()
    h.click_empty()
    sd.modify_menu("Scale")


def click_body1():
    p = panel()
    h.check("Scale waits for what to scale", p is not None and not p.has_entities())
    h.fit()
    h.click(V(20, 15, 10))


def entities_box_again():
    p = panel()
    h.check("Body1 picked", p is not None and p.body is body1() and p.base is not None)
    h.check("the Point box takes the next click", p is not None and p.active == "point")
    if p is not None:
        w.click(p.entities.button)


def click_body2():
    p = panel()
    h.check("the Entities box takes clicks again", p is not None and p.active == "entities")
    h.click(V(60, 15, 10))


def both():
    p = panel()
    if p is None:
        return
    h.check("Body2 joined the same Scale", len(p.members) == 1 and p.members[0].body is body2())
    text = p.entities.button.text()
    h.check("the Entities box names both", "Body" in text and "," in text, text)
    sd.type_into(p.factor.widget, "0.5")


def half():
    v1, v2 = volumes()
    h.check("Body1 half size", m.close(v1, 1500.0), v1)
    h.check("Body2 half size", m.close(v2, 750.0), v2)
    h.shot("1-two-bodies")
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", m.no_dialog())
    h.check("one Scale step", len(scale_titles()) == 1, sd.timeline_titles())
    h.check("Body2 has the hidden follower step", len(m.followers()) == 1, m.followers())
    v1, v2 = volumes()
    h.check("kept", m.close(v1, 1500.0) and m.close(v2, 750.0), (v1, v2))
    s["bodies_scale"] = scale_titles()[0] if scale_titles() else "?"


# -- C2 -------------------------------------------------------------------------------------------
def undo():
    m.undo()


def after_undo():
    v1, v2 = volumes()
    h.check("Ctrl+Z: both full size", m.close(v1, 12000.0) and m.close(v2, 6000.0), (v1, v2))
    h.check("no follower left", not m.followers(), m.followers())


def redo():
    m.redo()


def after_redo():
    v1, v2 = volumes()
    h.check("Ctrl+Y: both half size", m.close(v1, 1500.0) and m.close(v2, 750.0), (v1, v2))


# -- C3 -------------------------------------------------------------------------------------------
def click_sketch_row():
    Gui.Selection.clearSelection()
    m.click_row(sketch().Label if sketch() else "Sketch")


def sketch_scale_start():
    h.check(
        "the sketch is selected", m.selected_names()[:1] == [(s["sketch"], [])], m.selected_names()
    )
    sd.modify_menu("Scale")


def sketch_taken():
    p = panel()
    h.check("Scale opens on the sketch", p is not None and p.sketches == [sketch()])
    if p is None:
        return
    h.check("the Entities box names it", sketch().Label in p.entities.button.text())
    h.check("choose Non Uniform", b.choose(p.scale_type, "Non Uniform"))


def non_uniform_refused():
    p = panel()
    text = m.message(p)
    h.check("Non Uniform with a sketch: the reason", "uniform" in text.lower(), text)
    h.check("the sketch is unchanged", rect() == (-30, 0, -10, 10), rect())
    h.check("choose Uniform", b.choose(p.scale_type, "Uniform"))


def factor_two():
    p = panel()
    if p:
        sd.type_into(p.factor.widget, "2")


def doubled():
    h.check("the rectangle doubled about the origin", rect() == (-60, 0, -20, 20), rect())
    h.check("no message", not m.message(panel()), m.message(panel()))
    h.shot("2-sketch")
    h.task_button("OK")


def sketch_ok():
    h.check("dialog closed", m.no_dialog())
    titles = scale_titles()
    h.check("a second Scale step", len(titles) == 2, sd.timeline_titles())
    s["sketch_scale"] = [t for t in titles if t != s["bodies_scale"]][:1] or ["?"]
    h.check("kept", rect() == (-60, 0, -20, 20), rect())


def after_sketch_undo():
    h.check("Ctrl+Z: the rectangle as drawn", rect() == (-30, 0, -10, 10), rect())


def after_sketch_redo():
    h.check("Ctrl+Y: doubled again", rect() == (-60, 0, -20, 20), rect())


# -- C4 -------------------------------------------------------------------------------------------
def edit():
    sd.timeline_double_click(s["sketch_scale"][0])


def edit_open():
    p = panel()
    h.check("the Scale dialog opens on the step", p is not None and p.editing)
    if p is None:
        return
    h.check("it reads 2", abs(p.factor.value() - 2.0) < 1e-9, p.factor.value())
    sd.type_into(p.factor.widget, "1.5")


def edited():
    h.check("1.5 from the rectangle as drawn", rect() == (-45, 0, -15, 15), rect())
    h.task_button("OK")


def after_edit():
    h.check("dialog closed", m.no_dialog())
    h.check("kept", rect() == (-45, 0, -15, 15), rect())


# -- C5 -------------------------------------------------------------------------------------------
def delete_step():
    ti.menu(s["sketch_scale"][0], "Delete")


def after_delete():
    h.check("deleting the Scale: the rectangle as drawn", rect() == (-30, 0, -10, 10), rect())
    h.check("one Scale step left", len(scale_titles()) == 1, sd.timeline_titles())
    v1, v2 = volumes()
    h.check("the bodies are still half size", m.close(v1, 1500.0) and m.close(v2, 750.0))
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("3-end")


h.run(
    "modify2_scale",
    sd.box_steps("Modify2Scale")
    + [
        second_sketch,
        second_plane,
        second_draw,
        second_finish,
        second_extrude,
        second_distance,
        second_ok,
        two_bodies,
        free_sketch,
        free_plane,
        free_draw,
        free_finish,
        free_made,
        scale_start,
        click_body1,
        entities_box_again,
        click_body2,
        both,
        half,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        click_sketch_row,
        sketch_scale_start,
        sketch_taken,
        non_uniform_refused,
        factor_two,
        doubled,
        sketch_ok,
        undo,
        after_sketch_undo,
        redo,
        after_sketch_redo,
        edit,
        edit_open,
        edited,
        after_edit,
        delete_step,
        after_delete,
    ],
)
