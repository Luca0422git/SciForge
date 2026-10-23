# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY > Fillet and Chamfer on a surface body, like a Fusion user, real input.

An open box of surfaces (30 x 20 floor, 10 high walls, no lid: one surface body, area 1600).
SURFACE tab, MODIFY > Fillet with nothing picked: the surface Fillet dialog opens on the
shown surface body. Click a vertical corner edge, type Radius 3, OK: a "Fillet" step, the
corner round: 6 faces, area 1600 - 2*3*10 + (pi*3/2)*10 - (9 - 9 pi/4). Undo / Redo.
Double-click the Fillet in the timeline: Radius 3 reads back; type the parameter r (2 mm),
OK: the area follows; r changed to 1.5: the fillet follows it; back to 2.
Click another vertical edge (selected), MODIFY > Chamfer: the dialog starts with it; Distance
2, OK: one face more, area 1600-ish minus 2*2*10 plus the 2 sqrt 2 x 10 bevel. A refusal:
Fillet, click a top edge (on the outside of the surface: one face): the dialog says why and
OK is refused; Esc leaves the body as it was. Fillet on the last corner, Radius Type
Variable, 1 to 3, OK. Double-click it: Radius Type Chord Length (the field reads Chord
Length), 2 sqrt 2, OK: the walls meet at 90 degrees, so it is a round of radius 2.
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
    from sciforge import parameters

    s4.new_design("Surface4Fillet")
    s["box"] = s4.surface_box()
    parameters.add_user(App.ActiveDocument, "r", "mm", "2")  # a user parameter
    App.ActiveDocument.recompute()
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
    s4.type_main("r")  # Fusion's fields take a parameter


def edit_ok():
    s4.settle()
    st.ok()


def edited():
    from sciforge import parameters

    h.check("dialog closed", s4.panel() is None)
    h.check("radius r = 2 now", s4.near(st.area(s["box"]), fillet_area(2), 1e-5), st.area(s["box"]))
    parameters.set_user(App.ActiveDocument, "r", "1.5 mm")
    App.ActiveDocument.recompute()
    h.check(
        "the fillet follows r = 1.5",
        s4.near(st.area(s["box"]), fillet_area(1.5), 1e-5),
        st.area(s["box"]),
    )
    parameters.set_user(App.ActiveDocument, "r", "2 mm")
    App.ActiveDocument.recompute()
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
    s["area"] = st.area(s["box"])
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Fillet")


def click_last_corner():
    h.click_edge(V(30, 20, 5))


def variable():
    from SciForgeTests.gui import blend_steps as b

    s4.settle()
    p = s4.panel()
    h.check("one edge picked", p is not None and len(p.picked) == 1, p and p.picked)
    if p is None:
        return
    b.choose(p.radius_type, "Variable")
    h.check("End Radius shown", p.fields["radius2"][0].widget.isVisible())
    s4.type_main("1")


def end_radius():
    from SciForgeTests.gui import dialog_input as ui

    s4.settle()
    p = s4.panel()
    if p is not None:
        ui.type_into(p.fields["radius2"][0].widget, "3")


def variable_ok():
    s4.settle()
    st.ok()


def variable_made():
    from sciforge import surfmod

    h.check("dialog closed", s4.panel() is None)
    h.check("one face more", s4.faces(s["box"]) == s["faces"] + 1, s4.faces(s["box"]))
    step = s["box"].Tip
    options = surfmod.options_of(step) if surfmod.is_step(step) else {}
    h.check(
        "a Variable fillet 1 .. 3",
        options.get("radius_type") == "variable"
        and s4.near(options.get("radius", 0), 1.0)
        and s4.near(options.get("radius2", 0), 3.0),
        options,
    )
    lost = s["area"] - st.area(s["box"])
    # between a constant radius 1 and a constant radius 3 corner
    h.check("the area lies between r 1 and r 3", 4.5 < lost < 14.9, lost)
    titles = [t for t in st.timeline_titles() if t.startswith("Fillet")]
    h.check("double-clicked the Variable fillet", titles and st.double_click_timeline(titles[-1]))


def chord_type():
    from SciForgeTests.gui import blend_steps as b

    s4.settle()
    p = s4.panel()
    h.check("its dialog", p is not None and p.editing and p.kind == "surface_fillet")
    if p is None:
        return
    b.choose(p.radius_type, "Chord Length")
    h.check("End Radius hidden", not p.fields["radius2"][0].widget.isVisible())
    caption = p.fields["radius"][1].text()
    h.check("the field reads Chord Length", caption == "Chord Length", caption)
    s4.type_main("%.9f" % (2 * math.sqrt(2)))


def chord_ok():
    s4.settle()
    text = s4.message()
    h.check("not refused", "\u26a0" not in text, text)
    st.ok()


def chord_made():
    from sciforge import surfmod

    h.check("dialog closed", s4.panel() is None)
    step = s["box"].Tip
    options = surfmod.options_of(step) if surfmod.is_step(step) else {}
    h.check("a Chord Length fillet", options.get("radius_type") == "chord", options)
    lost = s["area"] - st.area(s["box"])
    # the walls meet at 90 degrees: a chord of 2 sqrt 2 is a radius of 2
    h.check("the corner of radius 2", s4.near(lost, AREA - fillet_area(2), 1e-6), lost)


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
        click_last_corner,
        variable,
        end_radius,
        variable_ok,
        variable_made,
        chord_type,
        chord_ok,
        chord_made,
    ],
)
