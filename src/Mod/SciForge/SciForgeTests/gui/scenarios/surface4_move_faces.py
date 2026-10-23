# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY > Move/Copy with Move Object Faces on a surface body, real input.

An open box of surfaces (30 x 20 floor, 10 high walls: area 1600) and a curved surface (an
arc extruded) beside it. SURFACE tab, M: Move Object Faces, click the box's floor, Z Distance
-5: the floor goes 5 down and the walls grow with it (600 + 2 x 30 x 15 + 2 x 20 x 15 =
2100), still a surface body; OK: one Move step. Ctrl+Z: 1600; Ctrl+Y: 2100. A refusal: M,
Faces, click the curved surface, Z 3: only flat faces of a surface body move this way, said
in the dialog; Esc: nothing changed.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import modify2_steps as m
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def panel():
    from sciforge import move_ui

    p = bs.panel()
    return p if isinstance(p, move_ui.MovePanel) and not p._closed else None


def moves():
    return m.objects(kind="MoveFace")


def setup():
    from sciforge import bodies, surface

    s4.new_design("Surface4MoveFaces")
    s["box"] = s4.surface_box()
    arc = s4.arc_sketch(80, -40, 52, 60, 120, plane="XZ_Plane")
    step = surface.build("extrude", {"refs": s4.edges(arc)}, {"distance": 20.0})
    doc().recompute()
    bodies.set_shown(arc, False)
    s["curved"] = bodies.body_of(step)
    s["curved_area"] = st.area(s["curved"])
    h.fit()
    h.check("the open box", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    h.click_empty()
    h.press("m")


def choose_faces():
    p = panel()
    if not h.check("Move/Copy dialog open", p is not None):
        return
    h.check("choose Faces", b.choose(p.move_object, "Faces"))


def click_floor():
    p = panel()
    h.check("the Objects box waits", p is not None and p.active == "objects", p and p.active)
    h.click(V(8, 16, 0))


def type_down():
    p = panel()
    if p is None:
        return
    text = p.fields["objects"].button.text()
    h.check("the Objects box says 1 face", text == "1 face", text)
    bs.type_value(p.distance_fields[2].widget, "-5")


def lowered():
    from sciforge import surfmod

    h.idle_step()()
    area = st.area(s["box"])
    h.check("Z -5: the walls grew, area 2100", st.near(area, 2100.0), area)
    h.check("still a surface body", surfmod.is_surface_body(s["box"]))
    h.shot("1-floor-down")
    h.task_button("OK")


def after_ok():
    h.idle_step()()
    h.check("dialog closed", panel() is None)
    h.check("one Move step", len(moves()) == 1, moves())
    bb = s["box"].Shape.BoundBox
    h.check("the floor at z = -5", abs(bb.ZMin + 5) < 1e-6, bb)
    h.check("5 faces", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    m.undo()


def after_undo():
    h.check("Ctrl+Z: 1600", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    m.redo()


def after_redo():
    h.check("Ctrl+Y: 2100", st.near(st.area(s["box"]), 2100.0), st.area(s["box"]))
    Gui.Selection.clearSelection()
    h.click_empty()
    h.press("m")


def faces_again():
    p = panel()
    if not h.check("Move/Copy dialog open again", p is not None):
        return
    h.check("choose Faces", b.choose(p.move_object, "Faces"))


def click_curved():
    h.click(V(80, -10, 12))


def type_up():
    p = panel()
    if p is None:
        return
    text = p.fields["objects"].button.text()
    h.check("the curved face picked", text == "1 face", text)
    bs.type_value(p.distance_fields[2].widget, "3")


def refused():
    h.idle_step()()
    p = panel()
    text = (p.message.text() + " | " + p.info.text()) if p is not None else ""
    h.check("says only flat faces move this way", "flat faces" in text, text)
    st.esc()


def unchanged():
    h.idle_step()()
    h.check("Esc closed it", panel() is None)
    h.check("the curved surface as it was", st.near(st.area(s["curved"]), s["curved_area"]))
    h.check("the box as it was", st.near(st.area(s["box"]), 2100.0), st.area(s["box"]))
    h.check("still one Move step", len(moves()) == 1, moves())


h.run(
    "surface4_move_faces",
    [
        setup,
        choose_faces,
        click_floor,
        type_down,
        lowered,
        after_ok,
        after_undo,
        after_redo,
        faces_again,
        click_curved,
        type_up,
        refused,
        unchanged,
    ],
)
