# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press Pull (Q) on a surface body, real input.

An open box of surfaces (30 x 20 floor, 10 high walls: area 1600) and a curved surface
(an arc extruded). Q with nothing picked opens Press Pull; a click on the box's floor hands
over to the surface Press Pull (the face moves, the walls follow). Type -5: the floor goes
5 down (its normal points up into the box), the walls grow by 5: area 2100. OK: a "Press
Pull" step. Double-click it in the timeline: -5 reads back; type 3: the floor goes up 3,
the walls are cut back: area 1300; OK. Undo: 2100 again; Redo. A vertical edge selected,
Q: Press Pull on an edge of a surface body is its Fillet (the surface Fillet dialog opens
with the edge); Esc. A refusal: Q, click the curved surface: it says Press Pull pushes flat
faces of a surface body; Esc leaves everything as it was.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def setup():
    from sciforge import bodies, surface

    s4.new_design("Surface4PressPull")
    s["box"] = s4.surface_box()
    arc = s4.arc_sketch(80, -40, 52, 60, 120, plane="XZ_Plane")
    step = surface.build("extrude", {"refs": s4.edges(arc)}, {"distance": 20.0})
    doc().recompute()
    bodies.set_shown(arc, False)
    s["curved"] = bodies.body_of(step)
    h.fit()
    h.check("the open box", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    h.press("q")


def click_floor():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    shown = p is not None and not p._closed
    h.check("Press Pull opened, waiting", shown)
    if shown:
        h.check("no 'make a solid first'", "solid" not in p.message.text(), p.message.text())
        h.check("says to click a surface face", "surface body" in p.what.text(), p.what.text())
    h.click(V(8, 16, 0))


def handed_over():
    s4.settle()
    p = s4.panel()
    h.check("the surface Press Pull dialog", p is not None and p.kind == "surface_press_pull")
    h.check("the floor picked", p is not None and len(p.picked) == 1, p and p.picked)
    h.check("an arrow on the face", p is not None and len(p.arrows) == 1)
    s4.type_main("-5")


def pulled_down():
    s4.settle()
    h.check("preview: the walls grew", st.near(st.area(s["box"]), 2100.0), st.area(s["box"]))
    h.check("still 5 faces", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    h.shot("1-press-pull")
    st.ok()


def done():
    h.check("dialog closed", s4.panel() is None)
    h.check("area 2100", st.near(st.area(s["box"]), 2100.0), st.area(s["box"]))
    bb = s["box"].Shape.BoundBox
    h.check("the floor at z = -5", abs(bb.ZMin + 5) < 1e-6, bb)
    titles = st.timeline_titles()
    s["title"] = next((t for t in titles if t.startswith("Press Pull")), None)
    h.check("Press Pull in the timeline", s["title"] is not None, titles)
    h.check("double-clicked it", st.double_click_timeline(s["title"] or "Press Pull 1"))


def edit_open():
    s4.settle()
    p = s4.panel()
    h.check("edit dialog", p is not None and p.editing)
    if p is None:
        return
    h.check("-5 reads back", s4.near(p.fields["distance"][0].value(), -5.0))
    s4.type_main("3")


def edit_ok():
    s4.settle()
    st.ok()


def edited():
    h.check("area 1300", st.near(st.area(s["box"]), 1300.0), st.area(s["box"]))
    st.undo()


def undone():
    h.check("undo: 2100 again", st.near(st.area(s["box"]), 2100.0), st.area(s["box"]))
    st.redo()


def redone():
    h.check("redo: 1300", st.near(st.area(s["box"]), 1300.0), st.area(s["box"]))
    Gui.Selection.clearSelection()
    h.fit()


def select_edge():
    h.click_edge(V(0, 20, 7))


def q_on_edge():
    h.check("an edge selected", bool(Gui.Selection.getSelectionEx()))
    h.press("q")


def fillet_on_edge():
    s4.settle()
    p = s4.panel()
    h.check(
        "Press Pull on a surface edge is its Fillet", p is not None and p.kind == "surface_fillet"
    )
    h.check("with the edge", p is not None and len(p.picked) == 1, p and p.picked)
    s4.type_main("2")


def fillet_ok():
    s4.settle()
    st.ok()


def q_on_fillet_face():
    h.check("filleted: one face more", s4.faces(s["box"]) == 6, s4.faces(s["box"]))
    Gui.Selection.clearSelection()
    h.press("q")


def click_fillet_face():
    h.click(V(2 - 2**0.5, 18 + 2**0.5, 6.5))


def fillet_edit_opens():
    s4.settle()
    p = s4.panel()
    h.check(
        "Press Pull on the fillet's face changes that fillet",
        p is not None and p.kind == "surface_fillet" and p.editing,
        p and (p.kind, p.editing),
    )
    h.check("Radius 2 reads back", p is not None and s4.near(p.fields["radius"][0].value(), 2.0))
    st.esc()


def q_again():
    s4.settle()
    h.check("closed", s4.panel() is None)
    s["area"] = st.area(s["box"])
    Gui.Selection.clearSelection()
    h.press("q")


def click_curved():
    h.click(V(80, -10, 12))


def refused():
    s4.settle()
    text = s4.message()
    h.check("says flat faces only", "flat faces" in text, text)
    st.esc()


def unchanged():
    s4.settle()
    h.check("closed", s4.panel() is None)
    h.check("the box unchanged", st.near(st.area(s["box"]), s["area"]))
    from sciforge import surfmod

    h.check("the curved surface unchanged", surfmod.is_surface_body(s["curved"]))
    h.check("no step on it", surfmod.kind_of(s["curved"].Tip) is None)


h.run(
    "surface4_presspull",
    [
        setup,
        click_floor,
        handed_over,
        pulled_down,
        done,
        edit_open,
        edit_ok,
        edited,
        undone,
        redone,
        select_edge,
        q_on_edge,
        fillet_on_edge,
        fillet_ok,
        q_on_fillet_face,
        click_fillet_face,
        fillet_edit_opens,
        q_again,
        click_curved,
        refused,
        unchanged,
    ],
)
