# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Stitch with Operation Join (and its refusal), Trim with one face of a solid as the
tool, Ruled's Corner Type (surface part 3), only real input in the dialogs.

The design (built for the scenario): a 10 x 10 x 10 box at the origin; four surface walls
round x 5 .. 15, y 0 .. 10, 10 high, with a bottom patch at z 0 and a top patch at z 10
(they close a 10 x 10 x 10 cube overlapping the box by half); two loose flat patches at
x 30 .. 40.
Path S1 (Stitch Join): SURFACE > Stitch: Operation offers New Body / Join / Cut / Intersect;
        click the walls, the top patch, the bottom patch's row in the browser: "Closed";
        Join: the cube joins the box (15 x 10 x 10 = 1500) and the surfaces are used up.
        OK: "Stitch 1".
Path S2 (undo / redo, edit): Undo: the box 1000, the surfaces back; Redo: 1500; double-click
        Stitch 1: Join and the three bodies read back; Cancel.
Path S3 (refusal): Stitch the two loose patches with Join: the dialog says they do not close
        into a solid and OK waits; Cancel: nothing made.
Path T1 (Trim with a face): a surface wall along y 5 from x -5 to 25 (built). SURFACE > Trim,
        click the box's right face (x 15): that face alone is the tool, the wall is cut in
        two cells (the whole box would make three); click the piece past x 15: 20 x 10 = 200
        left. OK: "Trim 1".
Path R1 (Ruled Corner Type): sketch lines (40, 20) - (60, 20) - (60, 40) (built). SURFACE >
        Ruled, click both lines, type -5: two bands of 20 x 5 and a rounded
        corner (200 + 25 pi / 4); Corner Type Mitered: a square corner (225). OK.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def _sketch(body, plane, points, closed=False, offset=0.0):
    from sciforge import commands, sketch_ui

    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes[plane], ""))
    if offset:
        sk.AttachmentOffset = App.Placement(V(0, 0, offset), App.Rotation())
    st.add_lines(sk, points, closed=closed)
    commands.leave_edit()
    doc().recompute()
    return sk


def _surface(kind, sk, options=None):
    from sciforge import bodies, surface

    n = len(sk.Shape.Edges)
    step = surface.build(
        kind, {"refs": [(sk, "Edge%d" % (i + 1)) for i in range(n)]}, options or {}
    )
    doc().recompute()
    return bodies.body_of(step)


def new_design():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface3StitchTrimRuled")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    base = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(base, 0, 0, 10, 10)
    extrude.make(body, base, {"distance": 10.0})
    commands.leave_edit()
    s["box"] = body
    square = [(5, 0), (15, 0), (15, 10), (5, 10)]
    s["walls"] = _surface("extrude", _sketch(body, "XY_Plane", square, True), {"distance": 10.0})
    s["bottom"] = _surface("patch", _sketch(body, "XY_Plane", square, True))
    s["top"] = _surface("patch", _sketch(body, "XY_Plane", square, True, offset=10.0))
    loose = [(30, 0), (40, 0), (40, 10), (30, 10)]
    s["loose1"] = _surface("patch", _sketch(body, "XY_Plane", loose, True))
    s["loose2"] = _surface("patch", _sketch(body, "XY_Plane", loose, True, offset=10.0))
    from sciforge import bodies

    for obj in doc().Objects:
        if obj.TypeId == "Sketcher::SketchObject":
            bodies.set_shown(obj, False)
    h.fit()


def stitch_menu():
    h.check("a box of 1000", st.near(st.volume(s["box"]), 1000.0), st.volume(s["box"]))
    h.click_empty()
    st.tab("SURFACE")
    st.menu("MODIFY", "Stitch")


def click_walls():
    p = st.panel()
    h.check("Stitch dialog open", p is not None and p.kind == "stitch")
    if p is None:
        return
    box = p.rows["operation"][0]
    items = [box.itemText(i) for i in range(box.count())]
    h.check(
        "Operation: New Body, Join, Cut, Intersect",
        items == ["New Body", "Join", "Cut", "Intersect"],
        items,
    )
    h.click(V(15, 5, 4))


def click_top():
    st.settle()
    h.click(V(13, 6, 10))


def click_bottom_row():
    st.settle()
    h.check("the bottom patch's row clicked", tl.click_row(s["bottom"].Label))


def closed():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("three bodies", len(p.picks["bodies"]) == 3, p.picks["bodies"])
    h.check("Closed", "Closed" in p.open_label.text(), p.open_label.text())
    st.choose("operation", "Join")


def joined():
    st.settle()
    p = st.panel()
    from sciforge import bodies

    step = p.step if p is not None else None
    h.check("the step is in the box", step is not None and bodies.body_of(step) is s["box"])
    v = st.volume(s["box"])
    h.check("the cube joins the box (1500)", st.near(v, 1500.0, 1e-6), v)
    used = bodies.consumed(doc())
    h.check(
        "the surfaces are used up",
        all(s[k].Name in used for k in ("walls", "top", "bottom")),
        used,
    )
    h.shot("1-stitch-join")
    st.ok()


def stitch_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Stitch 1 in the timeline", "Stitch 1" in titles, titles)
    st.undo()


def stitch_undone():
    from sciforge import bodies

    h.check("Undo: the box 1000", st.near(st.volume(s["box"]), 1000.0), st.volume(s["box"]))
    h.check("the walls back", s["walls"].Name not in bodies.consumed(doc()))
    st.redo()


def stitch_redone():
    h.check("Redo: 1500", st.near(st.volume(s["box"]), 1500.0), st.volume(s["box"]))
    h.check("edited from the timeline", st.double_click_timeline("Stitch 1"))


def stitch_reads_back():
    st.settle()
    p = st.panel()
    h.check("Stitch dialog for editing", p is not None and p.kind == "stitch" and p.editing)
    if p is None:
        return
    h.check("Join read back", p.options["operation"] == "join", p.options)
    h.check("the three bodies read back", len(p.picks["bodies"]) == 3, p.picks["bodies"])
    st.cancel()


def stitch_cancelled():
    h.check("dialog closed", st.panel() is None)
    h.check("still 1500", st.near(st.volume(s["box"]), 1500.0), st.volume(s["box"]))


# -- refusal: Join with surfaces that do not close ----------------------------------------------
def refusal_menu():
    h.fit()
    h.click_empty()
    st.menu("MODIFY", "Stitch")


def refusal_pick():
    h.check("Stitch dialog open", st.panel() is not None)
    h.click(V(35, 5, 10))


def refusal_pick2():
    st.settle()
    h.check("the lower patch's row clicked", tl.click_row(s["loose1"].Label))


def refusal_join():
    st.settle()
    p = st.panel()
    h.check("two bodies", p is not None and len(p.picks["bodies"]) == 2, p and p.picks)
    st.choose("operation", "Join")


def refused():
    st.settle()
    text = st.message()
    h.check("the dialog says they do not close", "close" in text.lower(), text)
    st.ok()


def ok_waits():
    h.check("OK waits", st.panel() is not None)
    st.cancel()


def refusal_cancelled():
    h.check("Cancel closed it", st.panel() is None)
    titles = st.timeline_titles()
    h.check("no Stitch 2", "Stitch 2" not in titles, titles)
    h.check("still 1500", st.near(st.volume(s["box"]), 1500.0), st.volume(s["box"]))


# -- Trim with one face of the box ----------------------------------------------------------------
def trim_setup():
    from sciforge import bodies

    sk = _sketch(s["box"], "XY_Plane", [(-5, 5), (25, 5)])
    s["wall"] = _surface("extrude", sk, {"distance": 10.0})
    bodies.set_shown(sk, False)
    for key in ("loose1", "loose2"):
        bodies.set_shown(s[key], False)
    h.fit()
    h.click_empty()
    st.menu("MODIFY", "Trim")


def trim_tool():
    p = st.panel()
    h.check("Trim dialog open", p is not None and p.kind == "trim")
    h.check("a wall of 300", st.near(st.area(s["wall"]), 300.0), st.area(s["wall"]))
    h.click(V(15, 2, 7))


def trim_cells():
    st.settle()
    p = st.panel()
    if p is None:
        return
    tool = p.picks["tool"]
    h.check(
        "one face of the box is the tool", len(tool) == 1 and tool[0][1].startswith("Face"), tool
    )
    h.check("two cells (the face cuts once)", len(p.cell_data) == 2, len(p.cell_data))
    pl.click_on_plane(V(21, 5, 5))


def trimmed():
    st.settle()
    p = st.panel()
    h.check("one piece to remove", p is not None and len(p.removed) == 1, p and p.removed)
    h.check(
        "the wall keeps x -5 .. 15 (200)",
        st.near(st.area(s["wall"]), 200.0, 1e-6),
        st.area(s["wall"]),
    )
    h.shot("2-trim-face")
    st.ok()


def trim_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Trim 1 in the timeline", "Trim 1" in titles, titles)


# -- Ruled Corner Type ----------------------------------------------------------------------------
def ruled_setup():
    from sciforge import bodies

    s["l_sketch"] = _sketch(s["box"], "XY_Plane", [(40, 20), (60, 20), (60, 40)])
    bodies.set_shown(s["l_sketch"], True)
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Ruled")


def ruled_click():
    p = st.panel()
    h.check("Ruled dialog open", p is not None and p.kind == "ruled")
    if p is None:
        return
    box = p.rows["corner_type"][0]
    items = [box.itemText(i) for i in range(box.count())]
    h.check("Corner Type: Rounded / Mitered", items == ["Rounded", "Mitered"], items)
    h.check("Rounded by default", box.currentText() == "Rounded", box.currentText())
    h.check("clicked a line", h.click_edge(V(50, 20, 0)))


def ruled_second():
    st.settle()
    p = st.panel()
    h.check(
        "one line (the chain follows tangent lines only)",
        p is not None and len(p.picks["edges"]) == 1,
        p and p.picks,
    )
    h.check("clicked the other line", h.click_edge(V(60, 30, 0)))


def ruled_distance():
    st.settle()
    p = st.panel()
    h.check("both lines", p is not None and len(p.picks["edges"]) == 2, p and p.picks)
    st.type_field("distance", "-5")


def ruled_rounded():
    st.settle()
    body = st.step_body()
    s["ruled"] = body
    want = 200 + 25 * math.pi / 4
    h.check("two bands and a rounded corner", st.near(st.area(body), want, 1e-5), st.area(body))
    st.choose("corner_type", "Mitered")


def ruled_mitered():
    st.settle()
    area = st.area(s["ruled"])
    h.check("Mitered: a square corner (225)", st.near(area, 225.0, 1e-5), area)
    h.shot("3-ruled-mitered")
    st.ok()


def ruled_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Ruled 1 in the timeline", "Ruled 1" in titles, titles)
    h.check("edited from the timeline", st.double_click_timeline("Ruled 1"))


def ruled_reads_back():
    st.settle()
    p = st.panel()
    h.check("Ruled dialog for editing", p is not None and p.kind == "ruled" and p.editing)
    if p is None:
        return
    h.check(
        "Mitered read back",
        p.rows["corner_type"][0].currentText() == "Mitered",
        p.rows["corner_type"][0].currentText(),
    )
    st.esc()


def ruled_escaped():
    h.check("Esc closed it", st.panel() is None)
    h.check("still 225", st.near(st.area(s["ruled"]), 225.0, 1e-5), st.area(s["ruled"]))


h.run(
    "surface3_stitch_trim_ruled",
    [
        new_design,
        stitch_menu,
        click_walls,
        click_top,
        click_bottom_row,
        closed,
        joined,
        stitch_done,
        stitch_undone,
        stitch_redone,
        stitch_reads_back,
        stitch_cancelled,
        refusal_menu,
        refusal_pick,
        refusal_pick2,
        refusal_join,
        refused,
        ok_waits,
        refusal_cancelled,
        trim_setup,
        trim_tool,
        trim_cells,
        trimmed,
        trim_done,
        ruled_setup,
        ruled_click,
        ruled_second,
        ruled_distance,
        ruled_rounded,
        ruled_mitered,
        ruled_done,
        ruled_reads_back,
        ruled_escaped,
    ],
)
