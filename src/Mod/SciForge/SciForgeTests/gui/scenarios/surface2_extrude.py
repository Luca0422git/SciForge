# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Extrude, part 2: Start From Object, Extent All and To Object a body, only real
input.

Create Sketch on XY: a line from (0, -15) to (30, -15). Create Sketch on XY: a rectangle
(-5, -25) .. (35, 5); Extrude it with Start Offset 20, 10 high: a box z 20 .. 30 above the
line.
Path X1 (From Object): SURFACE > CREATE > Extrude, click the line; Start From Object: the
        Start Object box lights up; click the box's top face; Distance 15: a band z 30 .. 45
        (area 450); Offset 5: z 35 .. 50. OK: "Extrude 2" in the timeline.
Path X2 (undo / redo): Ctrl+Z takes the band away, Ctrl+Y brings it back.
Path X3 (edit from the timeline, All, a refusal): double-click Extrude 2; Extent All: nothing
        lies above z 35, the dialog says so and OK waits; Flip: the band runs down through
        the box to its underside (z 20 .. 35). OK.
Path X4 (Esc): edit again, Extent Distance, Esc: still z 20 .. 35.
Path X5 (To Object, a body): the line shown again; Extrude, click the line, Extent To Object,
        click the box's row in the browser: the band rises to the box's underside (z 0 ..
        20, area 600). OK.
Path X6 (an empty design): a new design, SURFACE > Extrude: the dialog waits, nothing built,
        Start offers From Object and Extent All; Esc.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}


def band_box():
    body = s.get("band")
    if body is None or body.Shape.isNull():
        return None
    b = body.Shape.BoundBox
    return b


def z_range(lo, hi, tol=1e-4):
    b = band_box()
    return b is not None and abs(b.ZMin - lo) < tol and abs(b.ZMax - hi) < tol


def zr():
    b = band_box()
    return (round(b.ZMin, 4), round(b.ZMax, 4)) if b is not None else None


# -- the line and the box ------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface2Extrude")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_line():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        st.add_lines(sk, [(0, -15), (30, -15)])
        s["line"] = sk


def finish_line():
    h.ribbon("Finish Sketch")


def second_sketch():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy_again():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_rectangle():
    sk = h.in_sketch()
    h.check("second sketch open", sk is not None)
    if sk:
        h.draw_rectangle(sk, -5, -25, 35, 5)


def finish_rectangle():
    h.ribbon("Finish Sketch")


def extrude_box():
    h.check("left the second sketch", h.in_sketch() is None)
    h.fit()
    h.press("e")


def box_start_offset():
    from sciforge import taskui

    p = taskui.current()
    if not h.check("Extrude dialog", p is not None and hasattr(p, "start")):
        return
    h.check("Start Offset", ui.choose(p.start, "Offset"))


def box_values():
    from sciforge import taskui

    p = taskui.current()
    ui.type_into(p.start_offset.widget, "20")
    ui.type_into(p.distance.widget, "10")


def box_ok():
    h.task_button("OK")


def box_made():
    solids = [b for b in st.bodies() if b.Shape.Solids]
    h.check("one box", len(solids) == 1, [b.Label for b in st.bodies()])
    if solids:
        s["box"] = solids[0]
        b = solids[0].Shape.BoundBox
        h.check(
            "the box is z 20 .. 30, 40 x 30 x 10",
            abs(b.ZMin - 20) < 1e-6
            and abs(b.ZMax - 30) < 1e-6
            and st.near(st.volume(solids[0]), 12000.0),
            (b, st.volume(solids[0])),
        )
    h.fit()
    h.click_empty()
    st.tab("SURFACE")


# -- X1: From Object -----------------------------------------------------------------------------
def extrude_start():
    st.menu("CREATE", "Extrude")


def x1_dialog():
    p = st.panel()
    h.check("surface Extrude dialog open", p is not None and p.kind == "extrude")
    if p is None:
        return
    starts = [p.rows["start"][0].itemText(i) for i in range(p.rows["start"][0].count())]
    extents = [p.rows["extent"][0].itemText(i) for i in range(p.rows["extent"][0].count())]
    h.check("Start: Fusion's three", starts == ["Profile Plane", "Offset", "From Object"], starts)
    h.check("Extent: Fusion's three", extents == ["Distance", "To Object", "All"], extents)
    h.check("the Start Object box waits hidden", not p.is_shown("start_object"))
    h.fit()


def x1_click_line():
    h.check("clicked the line", h.click_edge(V(15, -15, 0)))


def x1_from_object():
    st.settle()
    p = st.panel()
    h.check("the line is the profile", p is not None and len(p.picks["profile"]) == 1)
    st.choose("start", "From Object")


def x1_box_lit():
    p = st.panel()
    h.check("the Start Object box is shown", p is not None and p.is_shown("start_object"))
    h.check("and takes the clicks", p is not None and p.active == "start_object", p and p.active)
    h.check("Offset is shown with it", p is not None and p.rows["start_offset"][0].isVisible())


def x1_click_top():
    h.fit()
    h.click(V(15, -10, 30))


def x1_type_15():
    p = st.panel()
    h.check(
        "the top face is the start",
        p is not None and len(p.picks["start_object"]) == 1,
        p and p.picks,
    )
    st.type_field("distance", "15")


def x1_band():
    st.settle()
    s["band"] = st.step_body()
    h.check("a band 30 x 15", st.near(st.area(s["band"]), 450.0), st.area(s["band"]))
    h.check("starting on the top face: z 30 .. 45", z_range(30, 45), zr())
    h.shot("1-from-object")


def x1_offset():
    st.type_field("start_offset", "5")


def x1_offset_done():
    st.settle()
    h.check("Offset 5 moves the start on: z 35 .. 50", z_range(35, 50), zr())
    h.check("still 450", st.near(st.area(s["band"]), 450.0), st.area(s["band"]))


def x1_ok():
    st.ok()


def x1_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Extrude 2 in the timeline", "Extrude 2" in titles, titles)
    h.check("the line sketch is hidden", not s["line"].ViewObject.Visibility)
    from sciforge import surface

    h.check("the band is a surface body", surface.is_surface_body(s["band"]))


# -- X2: undo / redo -------------------------------------------------------------------------------
def x2_undo():
    st.undo()


def x2_undone():
    h.check("undo takes the band away", not st.surface_bodies(), st.surface_bodies())


def x2_redo():
    st.redo()


def x2_redone():
    found = st.surface_bodies()
    h.check("redo brings it back", len(found) == 1, found)
    if found:
        s["band"] = found[0]
    h.check("z 35 .. 50 again", z_range(35, 50), zr())


# -- X3: edit, All, a refusal, Flip -------------------------------------------------------------
def x3_edit():
    h.check("double-clicked Extrude 2", st.double_click_timeline("Extrude 2"))


def x3_read_back():
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing)
    if p is None:
        return
    h.check("From Object read back", p.options["start"] == "object", p.options)
    h.check("its face picked", len(p.picks["start_object"]) == 1, p.picks)
    h.check("Offset 5 read back", st.near(p.options["start_offset"], 5.0), p.options)
    st.choose("extent", "All")


def x3_nothing_above():
    st.settle()
    p = st.panel()
    text = st.message()
    h.check("All upwards: the dialog says nothing lies that way", "No visible body" in text, text)
    h.check("Flip is offered", p is not None and p.rows["flip"][0].isVisible())
    st.ok()


def x3_ok_waits():
    h.check("OK waits", st.panel() is not None)


def x3_flip():
    st.toggle_check("flip")


def x3_flipped():
    st.settle()
    p = st.panel()
    h.check("no problem now", "No visible body" not in st.message(), st.message())
    h.check("down through the box to its underside: z 20 .. 35", z_range(20, 35), zr())
    h.check("area 30 x 15", st.near(st.area(s["band"]), 450.0), st.area(s["band"]))
    h.check("the box is untouched", st.near(st.volume(s["box"]), 12000.0))
    h.check("Distance is hidden for All", p is not None and not p.rows["distance"][0].isVisible())
    h.shot("2-all-flip")
    st.ok()


def x3_done():
    h.check("dialog closed", st.panel() is None)
    h.check("kept: z 20 .. 35", z_range(20, 35), zr())


# -- X4: Esc ---------------------------------------------------------------------------------------
def x4_edit():
    h.check("double-clicked Extrude 2 again", st.double_click_timeline("Extrude 2"))


def x4_distance():
    p = st.panel()
    h.check(
        "All and Flip read back",
        p is not None and p.options["extent"] == "all" and p.options["flip"],
    )
    st.choose("extent", "Distance")


def x4_preview():
    st.settle()
    h.check("Distance 15 from the start again: z 35 .. 50", z_range(35, 50), zr())


def x4_esc():
    st.esc()


def x4_escaped():
    h.check("Esc closed the dialog", st.panel() is None)
    h.check("unchanged: z 20 .. 35", z_range(20, 35), zr())


# -- X5: To Object, a body -------------------------------------------------------------------
def x5_show_line():
    h.check("the line's eye clicked", tl.click_eye(s["line"].Label))


def x5_extrude():
    h.check("the line is shown", s["line"].ViewObject.Visibility)
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Extrude")


def x5_click_line():
    h.check("dialog open", st.panel() is not None)
    h.fit()
    h.check("clicked the line", h.click_edge(V(10, -15, 0)))


def x5_to_object():
    st.settle()
    st.choose("extent", "To Object")


def x5_click_body_row():
    p = st.panel()
    h.check(
        "the Object box takes the clicks", p is not None and p.active == "object", p and p.active
    )
    h.check("clicked the box's row", tl.click_row(s["box"].Label))


def x5_band():
    st.settle()
    p = st.panel()
    h.check("the body is the object", p is not None and len(p.picks["object"]) == 1, p and p.picks)
    body = st.step_body()
    s["band2"] = body
    h.check(
        "up to the box's underside: area 30 x 20",
        body is not None and st.near(st.area(body), 600.0, 1e-5),
        st.area(body),
    )
    b = body.Shape.BoundBox if body is not None else None
    h.check("z 0 .. 20", b is not None and abs(b.ZMin) < 1e-4 and abs(b.ZMax - 20) < 1e-4, b)
    st.ok()


def x5_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Extrude 3 in the timeline", "Extrude 3" in titles, titles)
    h.check("two surface bodies", len(st.surface_bodies()) == 2, st.surface_bodies())


# -- X6: an empty design -----------------------------------------------------------------------
def x6_new():
    App.newDocument("Surface2Empty")
    h.fit()
    st.tab("SURFACE")


def x6_extrude():
    st.menu("CREATE", "Extrude")


def x6_waits():
    p = st.panel()
    h.check("the dialog opens in an empty design", p is not None and p.kind == "extrude")
    if p is None:
        return
    h.check("nothing built", p.step is None and not st.bodies(), st.bodies())
    h.check("no pop-up", not h.popups(), h.popups())
    st.choose("start", "From Object")
    st.choose("extent", "All")


def x6_still_waits():
    st.settle()
    p = st.panel()
    h.check("still nothing built", p is not None and p.step is None)
    h.check("it asks for the profile", "profile" in st.message().lower(), st.message())


def x6_esc():
    st.esc()


def x6_done():
    h.check("Esc closed it", st.panel() is None)
    h.check("the empty design stays empty", not st.bodies(), st.bodies())


h.run(
    "surface2_extrude",
    [
        new_design,
        pick_xy,
        draw_line,
        finish_line,
        second_sketch,
        pick_xy_again,
        draw_rectangle,
        finish_rectangle,
        extrude_box,
        box_start_offset,
        box_values,
        box_ok,
        box_made,
        extrude_start,
        x1_dialog,
        x1_click_line,
        x1_from_object,
        x1_box_lit,
        x1_click_top,
        x1_type_15,
        x1_band,
        x1_offset,
        x1_offset_done,
        x1_ok,
        x1_done,
        x2_undo,
        x2_undone,
        x2_redo,
        x2_redone,
        x3_edit,
        x3_read_back,
        x3_nothing_above,
        x3_ok_waits,
        x3_flip,
        x3_flipped,
        x3_done,
        x4_edit,
        x4_distance,
        x4_preview,
        x4_esc,
        x4_escaped,
        x5_show_line,
        x5_extrude,
        x5_click_line,
        x5_to_object,
        x5_click_body_row,
        x5_band,
        x5_done,
        x6_new,
        x6_extrude,
        x6_waits,
        x6_still_waits,
        x6_esc,
        x6_done,
    ],
)
