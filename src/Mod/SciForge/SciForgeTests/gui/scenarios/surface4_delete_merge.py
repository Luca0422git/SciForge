# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY > Delete (faces removed without healing) and Merge, real input.

An empty design first: MODIFY > Merge says it needs a surface body and opens nothing.
Then an open box of surfaces (30 x 20 floor, 10 high walls: area 1600), a 20 x 20 x 10
solid box beside it, and a strip of surfaces with two faces in one plane (an extruded
polyline 0-10-20 along y = 40 and a turn: three faces, two of them in the plane y = 40).

SURFACE tab: click the surface box's floor, Del: a "Delete Face" step removes it and the
hole stays (4 faces, area 1000; Fusion's SURFACE Delete). Undo, Redo. Click the solid's top
face, Del (still the SURFACE tab): the face goes without healing, the solid becomes a
surface body (5 faces, area 1200). Undo. SOLID tab: the same click and Del heals (Fusion's
SOLID Delete): a box's top cannot be healed, so it is refused with the reason and the solid
stays. Double-click the surface Delete Face in the timeline: its floor reads back; click a
wall to delete it too, OK: 3 faces. MODIFY > Merge: click the two faces in the plane y = 40:
"The 2 faces become one face", OK: 2 faces, the same area. Merge again, click the merged face
and the other one: refused (different surfaces), Esc. MODIFY > Fillet with nothing picked opens
the surface Fillet; a click on the solid's edge hands it to the SOLID Fillet (Fusion's Fillet
rounds solids on the SURFACE tab too); Esc.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def told():
    from sciforge import commands

    return commands._TOLD.get("msg") or ""


def empty_design():
    s4.new_design("Surface4Delete")
    h.fit()
    st.tab("SURFACE")
    st.menu("MODIFY", "Merge")


def nothing_to_merge():
    h.check("no dialog in an empty design", s4.panel() is None)
    h.check("says it needs a surface body", "surface bodies" in told(), told())


def setup():
    from sciforge import bodies, extrude, surface

    s["box"] = s4.surface_box()
    sk = s4.sketch([(50, 0), (70, 0), (70, 20), (50, 20)])
    solid = bodies.body_of(sk)
    extrude.make(solid, sk, {"distance": 10.0})
    doc().recompute()
    bodies.set_shown(sk, False)
    s["solid"] = solid
    strip = s4.sketch([(0, 40), (10, 40), (20, 40), (20, 50)], closed=False, body=solid)
    step = surface.build("extrude", {"refs": s4.edges(strip)}, {"distance": 10.0})
    doc().recompute()
    bodies.set_shown(strip, False)
    s["strip"] = bodies.body_of(step)
    h.fit()
    h.check("the open box", s4.faces(s["box"]) == 5)
    h.check("the solid", st.near(st.volume(s["solid"]), 4000.0), st.volume(s["solid"]))
    h.check("the strip: 3 faces", s4.faces(s["strip"]) == 3, s4.faces(s["strip"]))


def click_floor():
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    h.click(V(8, 16, 0))


def press_delete():
    h.check("the floor is selected", bool(Gui.Selection.getSelectionEx()))
    h.press(QtCore.Qt.Key_Delete)


def floor_gone():
    from sciforge import surfmod

    h.check("4 faces left", s4.faces(s["box"]) == 4, s4.faces(s["box"]))
    h.check("area 1000 (the hole stays)", st.near(st.area(s["box"]), 1000.0), st.area(s["box"]))
    h.check("a surface Delete Face step", surfmod.kind_of(s["box"].Tip) == "surface_delete_face")
    titles = st.timeline_titles()
    s["title"] = next((t for t in titles if t.startswith("Delete Face")), None)
    h.check("Delete Face in the timeline", s["title"] is not None, titles)
    h.shot("1-deleted")
    st.undo()


def undone():
    h.check("undo: the floor is back", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    st.redo()


def redone():
    h.check("redo: gone again", s4.faces(s["box"]) == 4, s4.faces(s["box"]))
    Gui.Selection.clearSelection()
    h.click(V(60, 10, 10))


def delete_solid_top():
    h.press(QtCore.Qt.Key_Delete)


def solid_opened():
    from sciforge import surfmod

    h.check("the solid became a surface body", surfmod.is_surface_body(s["solid"]))
    h.check("5 faces, area 1200", st.near(st.area(s["solid"]), 1200.0), st.area(s["solid"]))
    st.undo()


def solid_back():
    h.check("undo: the solid again", st.near(st.volume(s["solid"]), 4000.0))
    st.tab("SOLID")
    Gui.Selection.clearSelection()
    h.click(V(60, 10, 10))


def delete_on_solid_tab():
    h.press(QtCore.Qt.Key_Delete)


def healed_or_refused():
    h.check("SOLID Delete heals: refused for a box top", "cannot" in told().lower(), told())
    h.check("the solid is untouched", st.near(st.volume(s["solid"]), 4000.0))
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    h.check("double-clicked the Delete Face", st.double_click_timeline(s["title"] or "Delete"))


def edit_open():
    s4.settle()
    p = s4.panel()
    h.check("the Delete Face dialog", p is not None and p.kind == "surface_delete_face")
    h.check("its floor reads back", p is not None and len(p.picked) == 1, p and p.picked)


def click_wall():
    h.click(V(15, 0, 5))


def edit_ok():
    s4.settle()
    p = s4.panel()
    h.check("two faces picked", p is not None and len(p.picked) == 2, p and p.picked)
    st.ok()


def edited():
    h.check("dialog closed", s4.panel() is None)
    h.check("3 faces left", s4.faces(s["box"]) == 3, s4.faces(s["box"]))
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Merge")


def merge_open():
    p = s4.panel()
    h.check("the Merge dialog", p is not None and p.kind == "surface_merge")
    h.click(V(5, 40, 5))


def merge_second():
    s4.settle()
    h.click(V(15, 40, 5))


def merge_preview():
    s4.settle()
    text = s4.message()
    h.check("says they become one face", "become one face" in text, text)
    h.check("preview: 2 faces", s4.faces(s["strip"]) == 2, s4.faces(s["strip"]))
    st.ok()


def merged():
    h.check("dialog closed", s4.panel() is None)
    h.check("2 faces", s4.faces(s["strip"]) == 2, s4.faces(s["strip"]))
    h.check("the same area", st.near(st.area(s["strip"]), 300.0), st.area(s["strip"]))
    titles = st.timeline_titles()
    h.check("Merge in the timeline", any(t.startswith("Merge") for t in titles), titles)
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Merge")


def merge_two_planes():
    h.click(V(10, 40, 5))


def merge_other():
    s4.settle()
    h.click(V(20, 45, 5))


def merge_refused():
    s4.settle()
    text = s4.message()
    h.check("refused: different surfaces", "different surfaces" in text, text)
    st.esc()


def closed_unchanged():
    s4.settle()
    h.check("Esc closed it", s4.panel() is None)
    h.check("still 2 faces", s4.faces(s["strip"]) == 2, s4.faces(s["strip"]))
    Gui.Selection.clearSelection()
    h.fit()
    st.menu("MODIFY", "Fillet")


def click_solid_edge():
    p = s4.panel()
    h.check("the surface Fillet dialog (a surface body is shown)", p is not None)
    h.click_edge(V(70, 0, 5))


def solid_fillet_took_it():
    from SciForgeTests.gui import blend_steps as b

    h.idle_step()()
    p = b.blend_panel()
    h.check("the SOLID Fillet took the solid's edge", p is not None, p)
    h.check("with that edge", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("the surface dialog closed", s4.panel() is None)
    st.esc()


def solid_unchanged():
    h.idle_step()()
    h.check("Esc closed it", not Gui.Control.activeDialog())
    h.check("the solid unchanged", st.near(st.volume(s["solid"]), 4000.0))


h.run(
    "surface4_delete_merge",
    [
        empty_design,
        nothing_to_merge,
        setup,
        click_floor,
        press_delete,
        floor_gone,
        undone,
        redone,
        delete_solid_top,
        solid_opened,
        solid_back,
        delete_on_solid_tab,
        healed_or_refused,
        edit_open,
        click_wall,
        edit_ok,
        edited,
        merge_open,
        merge_second,
        merge_preview,
        merged,
        merge_two_planes,
        merge_other,
        merge_refused,
        closed_unchanged,
        click_solid_edge,
        solid_fillet_took_it,
        solid_unchanged,
    ],
)
