# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mirror (Operation Join: stitched), Move/Copy and Scale of a surface body, real input.

Half an open box of surfaces: a 30 x 20 floor with walls (10 high) on three sides, open at
x = 0 (area 1400). SURFACE > CREATE > Mirror: click a wall (the surface body is mirrored as
a body: Pattern Type turns to Bodies), Operation Join, Mirror Plane: the YZ origin square.
The copy is stitched to the original along x = 0: one surface (one shell) of area 2800 whose
only open edges are the 6 round the top. OK: a "Mirror" step, still a surface body. Undo,
Redo. M with a wall selected: X Distance 50, OK: the body moves (x 20 .. 80). M again,
Create Copy, Y Distance 40, OK: a new surface body, the same area. SURFACE > MODIFY > Scale
with the copy selected: Scale Factor 2, OK: 4 x the area.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def free_edges(body):
    from sciforge import surface_geom

    return len(surface_geom.free_edges(body.Shape))


def setup():
    s4.new_design("Surface4Mirror")
    s["half"] = s4.surface_box(open_side=True)
    h.fit()
    h.check("the half box: 4 faces, 1400", st.near(st.area(s["half"]), 1400.0))


def mirror_menu():
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    st.menu("CREATE", "Mirror")


def click_wall():
    p = ps.panel()
    h.check("the Mirror dialog", p is not None and p.kind == "mirror")
    h.click(V(15, 0, 5))


def choose_join():
    p = ps.panel()
    h.check(
        "the surface body is the object, as a body",
        p is not None and p.options["objects"] == [(s["half"], "")],
        p and p.options["objects"],
    )
    h.check("Pattern Type is Bodies", p is not None and p.pattern_type.currentData() == "bodies")
    b.choose(p.operation, "Join")


def plane_box():
    ps.click_box("plane")


def click_yz():
    h.fit()
    pl.click_square("YZ_Plane")


def stitched_preview():
    s4.settle()
    h.idle_step()()
    body = s["half"]
    h.check("one surface", len(body.Shape.Shells) == 1, len(body.Shape.Shells))
    h.check("area 2800", st.near(st.area(body), 2800.0), st.area(body))
    h.check("only the top is open (6 edges)", free_edges(body) == 6, free_edges(body))
    p = ps.panel()
    h.check(
        "Stitch Tolerance shown, 1 mm",
        p is not None
        and p.stitch_field.widget.isVisible()
        and st.near(p.stitch_field.value(), 1.0),
    )
    h.shot("1-mirror-join")
    h.task_button("OK")


def mirrored():
    from sciforge import surfmod

    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("still a surface body", surfmod.is_surface_body(s["half"]))
    titles = st.timeline_titles()
    h.check("Mirror in the timeline", any(t.startswith("Mirror") for t in titles), titles)
    st.undo()


def undone():
    h.check("undo: the half again", st.near(st.area(s["half"]), 1400.0), st.area(s["half"]))
    st.redo()


def redone():
    h.check("redo: 2800", st.near(st.area(s["half"]), 2800.0), st.area(s["half"]))
    titles = [t for t in st.timeline_titles() if t.startswith("Mirror")]
    h.check("double-clicked the Mirror", st.double_click_timeline(titles[0] if titles else ""))


def mirror_edit_open():
    p = ps.panel()
    h.check("the Mirror dialog on it", p is not None and p.editing)
    if p is None:
        return
    h.check("Join reads back", p.operation.currentData() == "join", p.operation.currentData())
    h.check("Stitch Tolerance shown", p.stitch_field.widget.isVisible())
    bs.type_value(p.stitch_field.widget, "0.5")


def mirror_edit_ok():
    h.idle_step()()
    h.task_button("OK")


def mirror_edited():
    from sciforge import pattern

    found = [o for o in doc().Objects if pattern.kind_of(o) == "mirror"]
    h.check(
        "Stitch Tolerance 0.5 kept",
        found and abs(found[0].StitchTolerance.Value - 0.5) < 1e-9,
        found and found[0].StitchTolerance,
    )
    h.check("still 2800, one surface", st.near(st.area(s["half"]), 2800.0))
    Gui.Selection.clearSelection()
    h.fit()
    h.click(V(15, 0, 5))


def press_m():
    h.check("a wall selected", bool(Gui.Selection.getSelectionEx()))
    h.press("m")


def move_x():
    p = bs.panel()
    h.check(
        "Move/Copy with the surface body",
        p is not None and p.options["bodies"] == [s["half"]],
        p and p.options.get("bodies"),
    )
    if p is None:
        return
    b.choose(p.move_type, "Translate")


def type_x():
    p = bs.panel()
    if p is not None:
        bs.type_value(p.distance_fields[0].widget, "50")


def move_ok():
    h.idle_step()()
    h.task_button("OK")


def moved():
    bb = s["half"].Shape.BoundBox
    h.check(
        "moved 50 along X: x 20 .. 80", abs(bb.XMin - 20) < 1e-6 and abs(bb.XMax - 80) < 1e-6, bb
    )
    Gui.Selection.clearSelection()
    h.fit()
    h.click(V(65, 0, 5))


def press_m_copy():
    h.press("m")


def copy_options():
    p = bs.panel()
    if p is None:
        h.check("Move/Copy open", False)
        return
    b.choose(p.move_type, "Translate")
    bs.toggle(p.copy)


def type_y():
    p = bs.panel()
    if p is not None:
        bs.type_value(p.distance_fields[1].widget, "40")


def copy_ok():
    h.idle_step()()
    h.task_button("OK")


def copied():
    from sciforge import surfmod

    found = [x for x in st.surface_bodies() if x is not s["half"] and bs.shown(x)]
    h.check("a new surface body", len(found) == 1, [x.Label for x in found])
    if not found:
        return
    s["copy"] = found[0]
    h.check("the same area", st.near(st.area(s["copy"]), 2800.0), st.area(s["copy"]))
    bb = s["copy"].Shape.BoundBox
    h.check("40 along Y", abs(bb.YMin - 40) < 1e-6, bb)
    h.check("a surface body", surfmod.is_surface_body(s["copy"]))
    Gui.Selection.clearSelection()
    h.fit()
    h.click(V(65, 40, 5))


def scale_menu():
    h.check("the copy selected", bool(Gui.Selection.getSelectionEx()))
    st.menu("MODIFY", "Scale")


def scale_factor():
    from sciforge import scale_ui

    p = scale_ui.ScalePanel.last
    h.check("the Scale dialog on the copy", p is not None and p.body is s["copy"], p and p.body)
    if p is not None:
        bs.type_value(p.factor.widget, "2")


def scale_ok():
    h.idle_step()()
    h.task_button("OK")


def scaled():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("4 x the area", st.near(st.area(s["copy"]), 4 * 2800.0, 1e-6), st.area(s["copy"]))


h.run(
    "surface4_move_mirror",
    [
        setup,
        mirror_menu,
        click_wall,
        choose_join,
        plane_box,
        click_yz,
        stitched_preview,
        mirrored,
        undone,
        redone,
        mirror_edit_open,
        mirror_edit_ok,
        mirror_edited,
        press_m,
        move_x,
        type_x,
        move_ok,
        moved,
        press_m_copy,
        copy_options,
        type_y,
        copy_ok,
        copied,
        scale_menu,
        scale_factor,
        scale_ok,
        scaled,
    ],
)
