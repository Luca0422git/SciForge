# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY > Fillet and Chamfer on a surface body, like a Fusion user, real input.

An open box of surfaces (30 x 20 floor, 10 high walls, no lid: one surface body, area 1600).
SURFACE tab, MODIFY > Fillet with nothing picked: the surface Fillet dialog opens on the
shown surface body. Click a vertical corner edge, type Radius 3, OK: a "Fillet" step, the
corner round: 6 faces, area 1600 - 2*3*10 + (pi*3/2)*10 - (9 - 9 pi/4). Undo / Redo.
Double-click the Fillet in the timeline: Radius 3 reads back; type 2, OK: the area follows.
Click another vertical edge (selected), MODIFY > Chamfer: the dialog starts with it; Distance
2, OK: one face more, area 1600-ish minus 2*2*10 plus the 2 sqrt 2 x 10 bevel. A refusal:
Fillet, click a top edge (on the outside of the surface: one face): the dialog says why and
OK is refused; Esc leaves the body as it was. The SOLID Fillet still rounds a solid.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
AREA = 1600.0


def fillet_area(r):
    return AREA - 2 * r * 10 + (math.pi * r / 2) * 10 - (r * r - math.pi * r * r / 4)


def setup():
    s4.new_design("Surface4Fillet")
    s["box"] = s4.surface_box()
    h.fit()
    h.check("an open box of surfaces", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    h.check("area 1600", s4.near(st.area(s["box"]), AREA), st.area(s["box"]))


def fillet_menu():
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Fillet")


def fillet_open():
    p = s4.panel()
    h.check("the surface Fillet dialog opened", p is not None and p.kind == "surface_fillet")
    h.check("on the surface body", p is not None and p.body is s["box"], p and p.body)


def click_corner():
    h.click_edge(V(30, 0, 5))


def type_radius():
    s4.settle()
    p = s4.panel()
    h.check("one edge picked", p is not None and len(p.picked) == 1, p and p.picked)
    s4.type_main("3")


def preview_shown():
    s4.settle()
    h.check("the preview rounds the corner", s4.faces(s["box"]) == 6, s4.faces(s["box"]))
    h.check("preview area", s4.near(st.area(s["box"]), fillet_area(3), 1e-5), st.area(s["box"]))
    h.shot("1-fillet")
    st.ok()


def filleted():
    h.check("dialog closed", s4.panel() is None)
    h.check("still a surface body", st.browser_icon_of(s["box"]) == "surface_body")
    h.check("area with the radius 3 corner", s4.near(st.area(s["box"]), fillet_area(3), 1e-5))
    titles = st.timeline_titles()
    s["title"] = next((t for t in titles if t.startswith("Fillet")), None)
    h.check("Fillet in the timeline", s["title"] is not None, titles)
    st.undo()


def undone():
    h.check("undo: the sharp corner again", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    st.redo()


def redone():
    h.check("redo: round again", s4.faces(s["box"]) == 6, s4.faces(s["box"]))
    h.check("double-clicked the Fillet", st.double_click_timeline(s["title"] or "Fillet 1"))


def edit_open():
    s4.settle()
    p = s4.panel()
    h.check("edit dialog", p is not None and p.editing, p)
    if p is None:
        return
    h.check("Radius 3 read back", s4.near(p.fields["radius"][0].value(), 3.0))
    h.check("its edge read back", len(p.picked) == 1, p.picked)
    s4.type_main("2")


def edit_ok():
    s4.settle()
    st.ok()


def edited():
    h.check("dialog closed", s4.panel() is None)
    h.check("radius 2 now", s4.near(st.area(s["box"]), fillet_area(2), 1e-5), st.area(s["box"]))
    Gui.Selection.clearSelection()
    h.fit()


def select_edge():
    h.click_edge(V(0, 20, 5))


def chamfer_menu():
    h.check("the edge is selected", bool(Gui.Selection.getSelectionEx()))
    st.menu("MODIFY", "Chamfer")


def chamfer_open():
    s4.settle()
    p = s4.panel()
    h.check("the surface Chamfer dialog", p is not None and p.kind == "surface_chamfer")
    h.check("it starts with the selected edge", p is not None and len(p.picked) == 1)
    s4.type_main("2")


def chamfer_ok():
    s4.settle()
    st.ok()


def chamfered():
    h.check("dialog closed", s4.panel() is None)
    h.check("one face more", s4.faces(s["box"]) == 7, s4.faces(s["box"]))
    expect = fillet_area(2) - 2 * 2 * 10 + 2 * math.sqrt(2) * 10 - 2
    h.check("chamfered area", s4.near(st.area(s["box"]), expect, 1e-5), (st.area(s["box"]), expect))
    s["faces"] = s4.faces(s["box"])
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Fillet")


def click_free_edge():
    h.click_edge(V(15, 0, 10))


def refused():
    s4.settle()
    text = s4.message()
    h.check("says the edge is on the outside", "outside" in text, text)
    h.check("OK refused", not st.ok() or s4.panel() is not None)


def esc_after_refusal():
    s4.settle()
    st.esc()


def unchanged():
    h.check("Esc closed it", s4.panel() is None)
    h.check("the body is as it was", s4.faces(s["box"]) == s["faces"], s4.faces(s["box"]))
    h.check("no error left", not h.popups(), h.popups())


h.run(
    "surface4_fillet",
    [
        setup,
        fillet_menu,
        fillet_open,
        click_corner,
        type_radius,
        preview_shown,
        filleted,
        undone,
        redone,
        edit_open,
        edit_ok,
        edited,
        select_edge,
        chamfer_menu,
        chamfer_open,
        chamfer_ok,
        chamfered,
        click_free_edge,
        refused,
        esc_after_refusal,
        unchanged,
    ],
)
