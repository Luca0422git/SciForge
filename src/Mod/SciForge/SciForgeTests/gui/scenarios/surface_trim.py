# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Trim like a Fusion user, only real input.

A wall: a sketch line on XY from (0, 0) to (30, 0) surface-extruded 10 each way (Symmetric):
30 x 20 in the plane y = 0. Trim with nothing selected: the Trimming Tool box waits and the
origin planes are drawn to click; click the XY plane: the wall is cut in two cells and the
Remove box takes the clicks. Click the lower cell: it turns red and goes; OK: the wall is
30 x 10 above z 0, "Trim 1" in the timeline.
A second wall: a line on XY from (10, -10) to (10, 10), extruded 10 up: it crosses the
first one. Trim with the second wall as the tool: both walls are cut (each by the other);
remove the first wall's piece left of x 10 and the second wall's piece in front of y 0:
one Trim step changes both bodies (20 x 10 and 10 x 10 left). Undo / Redo. Edit "Trim 2":
the two pieces read back; click the second wall's red piece to keep it; OK: 20 x 10 again.
Refusal: Trim with the YZ plane, which touches nothing: the dialog says the tool cuts no
surface and OK waits; Cancel.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SurfaceTrim")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_line():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        st.add_lines(sk, [(0, 0), (30, 0)])


def finish():
    h.ribbon("Finish Sketch")


def extrude_wall():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Extrude")


def click_line():
    h.check("clicked the line", h.click_edge(V(20, 0, 0)))
    st.choose("direction", "Symmetric")


def wall_distance():
    st.type_field("distance", "10")


def wall_ok():
    st.settle()
    body = st.step_body()
    h.check("a 30 x 20 wall", body is not None and st.near(st.area(body), 600.0), st.area(body))
    s["wall"] = body
    st.ok()


def trim_nothing_selected():
    h.check("wall made", st.panel() is None)
    h.fit()
    st.menu("MODIFY", "Trim")


def trim_waits():
    p = st.panel()
    h.check("Trim dialog open", p is not None and p.kind == "trim")
    if p is None:
        return
    h.check("the Trimming Tool box waits", p.active == "tool", p.active)
    h.check("the origin planes are drawn to click", p.planes is not None)
    h.check("nothing changed yet", p.step is None)


def click_xy_plane():
    h.click(V(15, -15, 0))  # the XY square, nothing behind it there


def cells_shown():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check(
        "the XY plane is the tool",
        len(p.picks["tool"]) == 1 and p.picks["tool"][0][0].Role == "XY_Plane",
        p.picks["tool"],
    )
    h.check("the Remove box takes the clicks", p.active == "cells", p.active)
    h.check("two cells", len(p.cell_data) == 2, len(p.cell_data))
    h.check("OK waits for a piece", "pieces" in st.message().lower(), st.message())
    h.shot("1-cells")


def click_lower_cell():
    h.click(V(15, 0, -5))


def lower_gone():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("one piece to remove", len(p.removed) == 1, p.removed)
    h.check("the wall keeps its top half", st.near(st.area(s["wall"]), 300.0), st.area(s["wall"]))
    h.check("above z 0", st.near(s["wall"].Shape.BoundBox.ZMin, 0.0), s["wall"].Shape.BoundBox)
    h.shot("2-trimmed")
    st.ok()


def trim_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Trim 1 in the timeline", "Trim 1" in titles, titles)
    from sciforge import surface

    h.check("still a surface body", surface.is_surface_body(s["wall"]))


def second_sketch():
    st.tab("SOLID")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy_2():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_second():
    sk = h.in_sketch()
    h.check("second sketch open", sk is not None)
    if sk:
        st.add_lines(sk, [(10, -10), (10, 10)])


def finish_2():
    h.ribbon("Finish Sketch")


def extrude_second():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Extrude")


def click_second_line():
    h.check("clicked the second line", h.click_edge(V(10, -6, 0)))
    st.type_field("distance", "10")


def second_ok():
    st.settle()
    body = st.step_body()
    h.check(
        "a 20 x 10 wall across", body is not None and st.near(st.area(body), 200.0), st.area(body)
    )
    s["wall2"] = body
    st.ok()


def mutual_trim():
    h.fit()
    st.menu("MODIFY", "Trim")


def click_second_wall():
    h.click(V(10, -7, 8))  # a face of the second wall: the whole wall is the tool


def both_cut():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the second wall is the tool", p.picks["tool"] == [(s["wall2"], "")], p.picks["tool"])
    h.check(
        "four cells (each wall cut in two)",
        len(p.cell_data) == 4,
        [(c["body"], round(c["size"], 2)) for c in p.cell_data],
    )


def click_wall1_left():
    p = st.panel()
    h.check("the cells can be clicked", p is not None and p.cells is not None)
    # high on wall 1's left piece: lower down, wall 2 stands in front of it (seen from the
    # front-right-top)
    h.click(V(2, 0, 8))


def click_wall2_front():
    p = st.panel()
    h.check("wall 1's left piece is marked", p is not None and len(p.removed) == 1, p and p.removed)
    h.click(V(10, -5, 5))


def both_trimmed():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("two pieces to remove", len(p.removed) == 2, p.removed)
    h.check("wall 1: 20 x 10 left", st.near(st.area(s["wall"]), 200.0), st.area(s["wall"]))
    h.check("wall 2: 10 x 10 left", st.near(st.area(s["wall2"]), 100.0), st.area(s["wall2"]))
    h.shot("3-mutual")
    st.ok()


def mutual_done():
    titles = st.timeline_titles()
    h.check(
        "one Trim step for both bodies",
        titles.count("Trim 2") == 1 and "Trim 3" not in titles,
        titles,
    )
    st.undo()


def undone():
    h.check("undo: wall 1 back to 300", st.near(st.area(s["wall"]), 300.0), st.area(s["wall"]))
    h.check("undo: wall 2 back to 200", st.near(st.area(s["wall2"]), 200.0), st.area(s["wall2"]))
    st.redo()


def redone():
    h.check("redo: wall 1 200", st.near(st.area(s["wall"]), 200.0), st.area(s["wall"]))
    h.check("redo: wall 2 100", st.near(st.area(s["wall2"]), 100.0), st.area(s["wall2"]))


def edit_trim():
    h.check("double-clicked Trim 2", st.double_click_timeline("Trim 2"))


def edit_open():
    st.settle()
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing)
    if p is None:
        return
    h.check("two pieces read back", len(p.removed) == 2, p.removed)
    h.check("the tool read back", p.picks["tool"] == [(s["wall2"], "")], p.picks["tool"])
    st.click_box("cells")


def keep_wall2_piece():
    h.click(V(10, -5, 5))  # the red piece: kept again


def kept():
    st.settle()
    p = st.panel()
    h.check(
        "one piece left to remove", p is not None and len(p.removed) == 1, p.removed if p else None
    )
    h.check("wall 2 whole again", st.near(st.area(s["wall2"]), 200.0), st.area(s["wall2"]))
    st.ok()


def edit_done():
    h.check("dialog closed", st.panel() is None)
    h.check("wall 1 still 200", st.near(st.area(s["wall"]), 200.0), st.area(s["wall"]))
    h.check("wall 2 still 200", st.near(st.area(s["wall2"]), 200.0), st.area(s["wall2"]))


def trim_nothing_cut():
    h.fit()
    st.menu("MODIFY", "Trim")


def click_yz_plane():
    h.click(V(0, -15, 15))


def refused():
    st.settle()
    p = st.panel()
    if p is None:
        return
    note = p.cells_note.text()
    h.check("the YZ plane is the tool", len(p.picks["tool"]) == 1, p.picks["tool"])
    h.check("it cuts nothing: said", "does not cut" in note, note)
    st.ok()


def ok_waits():
    h.check("OK waits", st.panel() is not None)
    st.cancel()


def cancelled():
    h.check("Cancel closed it", st.panel() is None)
    h.check("nothing changed", st.near(st.area(s["wall"]), 200.0), st.area(s["wall"]))


h.run(
    "surface_trim",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_line,
        finish,
        extrude_wall,
        click_line,
        wall_distance,
        wall_ok,
        trim_nothing_selected,
        trim_waits,
        click_xy_plane,
        cells_shown,
        click_lower_cell,
        lower_gone,
        trim_done,
        second_sketch,
        pick_xy_2,
        draw_second,
        finish_2,
        extrude_second,
        click_second_line,
        second_ok,
        mutual_trim,
        click_second_wall,
        both_cut,
        click_wall1_left,
        click_wall2_front,
        both_trimmed,
        mutual_done,
        undone,
        redone,
        edit_trim,
        edit_open,
        keep_wall2_piece,
        kept,
        edit_done,
        trim_nothing_cut,
        click_yz_plane,
        refused,
        ok_waits,
        cancelled,
    ],
)
