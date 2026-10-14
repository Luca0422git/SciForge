# SPDX-License-Identifier: LGPL-2.1-or-later
"""Offset Plane with Extent To Object (Fusion: the plane goes through a picked corner or
point and follows it), only real input.

Part: a 40 x 30 x 10 box and a 10 x 10 post on its top (x, y 10..20), 15 high.
Path O1, CONSTRUCT > Offset Plane: click the box's top face; Extent To Object: the Object box
         waits and the Distance box goes; click the post's top corner (20, 10, 25): Plane1
         at z = 25, no arrow. OK.
Path O2, the post edited from the timeline to 20 high: Plane1 follows its corner to z = 30.
Path O3, Plane1 edited from the timeline: Extent reads To Object with the corner; Extent
         Distance: the plane stays at z = 30 and the box shows 20; type 5: z = 15. OK.
         Undo: z = 30 again; Redo: z = 15."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s

V = App.Vector
BOX = 12000.0
POST = 1500.0
st = {}


def plane():
    name = st.get("plane")
    return App.ActiveDocument.getObject(name) if name else None


def plane_z(datum):
    return datum.getGlobalPlacement().Base.z if datum is not None else None


def flat(datum):
    return datum is not None and abs(s.normal_of(datum).z) > 1 - 1e-9


# -- the post -------------------------------------------------------------------------------------
def post_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def post_face():
    h.click(V(30, 20, 10))


def post_draw():
    sk = h.in_sketch()
    if h.check("sketch on the top face", sk is not None):
        x0, y0 = h.to_sketch(sk, V(10, 10, 10))
        x1, y1 = h.to_sketch(sk, V(20, 20, 10))
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def post_finish():
    h.ribbon("Finish Sketch")


def post_extrude():
    h.fit()
    h.press("e")


def post_distance():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    if h.check("extrude dialog", p is not None and not p._closed):
        ui.type_into(p.distance.widget, "15")


def post_ok():
    h.task_button("OK")


def post_made():
    h.check("box + post: 13500", s.close(h.solid_volume(), BOX + POST), h.solid_volume())
    extrudes = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Pad"]
    if extrudes:
        st["post"] = extrudes[-1].Name


# -- O1: To Object --------------------------------------------------------------------------------
def offset_start():
    h.click_empty()
    h.fit()
    h.ribbon("Offset Plane")


def click_top():
    h.click(V(32, 5, 10))


def choose_to_object():
    p = s.construct_panel()
    if not h.check("Offset Plane open, the top face taken", p is not None and p.picks[0]):
        return
    labels = [p.extent.itemText(i) for i in range(p.extent.count())]
    h.check("Extent: Distance / To Object", labels == ["Distance", "To Object"], labels)
    h.check("the Object box is not there yet", not p.boxes[1].widget.isVisible())
    h.check("choose To Object", ui.choose(p.extent, "To Object"))


def object_waits():
    p = s.construct_panel()
    if p is None:
        return
    h.check("the Object box waits", p.active == 1 and p.boxes[1].widget.isVisible(), p.active)
    h.check("the Distance box goes", not p.distance.widget.isVisible())
    h.fit()
    h.check("the post's corner clicked", s.click_vertex(V(20, 10, 25)))


def through_corner():
    p = s.construct_panel()
    if p is None:
        return
    h.check("the corner is the object", p.picks[1] is not None, p.picks)
    h.check(
        "Plane1 through the corner: z = 25",
        flat(p.datum) and s.close(plane_z(p.datum), 25.0),
        p.datum and p.datum.Placement,
    )
    h.check("no arrow (the point sets it)", p.handle is None)
    h.check("no message", "⚠" not in p.message.text(), p.message.text())
    h.shot("1-to-object")
    h.task_button("OK")


def made():
    planes = s.datums("PartDesign::Plane")
    h.check("Plane1 made", len(planes) == 1 and planes[0].Label == "Plane1", planes)
    if planes:
        st["plane"] = planes[0].Name
    h.check("at z = 25", s.close(plane_z(plane()), 25.0), plane_z(plane()))


# -- O2: the post grows, the plane follows ------------------------------------------------------
def edit_post():
    h.click_empty()
    s.double_click_timeline(App.ActiveDocument.getObject(st["post"]))


def post_twenty():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    if h.check("the post's extrude opens", p is not None and not p._closed):
        ui.type_into(p.distance.widget, "20")


def post_twenty_ok():
    h.task_button("OK")


def followed():
    h.check("the post is 20 high", s.close(h.solid_volume(), BOX + 2000.0), h.solid_volume())
    h.check("Plane1 followed its corner: z = 30", s.close(plane_z(plane()), 30.0), plane_z(plane()))
    bad = [o.Label for o in App.ActiveDocument.Objects if "Invalid" in o.State]
    h.check("nothing broken", not bad, bad)


# -- O3: back to Distance in an edit ------------------------------------------------------------
def edit_plane():
    h.click_empty()
    s.double_click_timeline(plane())


def reads_to_object():
    p = s.construct_panel()
    if not h.check("Offset Plane opens for Plane1", p is not None and p.editing):
        return
    h.check("Extent reads To Object", p.extent.currentText() == "To Object", p.extent.currentText())
    h.check("with the corner", p.picks[1] is not None, p.picks)
    h.check("choose Distance", ui.choose(p.extent, "Distance"))


def distance_kept():
    p = s.construct_panel()
    if p is None:
        return
    h.check("the Distance box is back", p.distance.widget.isVisible())
    h.check("it shows 20", s.close(p.distance.value(), 20.0), p.distance.value())
    h.check("the plane stays at z = 30", s.close(plane_z(p.datum), 30.0), plane_z(p.datum))
    s.type_into(p.distance.widget, "5")


def five():
    p = s.construct_panel()
    if p is None:
        return
    h.check("z = 15", s.close(plane_z(p.datum), 15.0), plane_z(p.datum))
    h.task_button("OK")


def edited():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("Plane1 at z = 15", s.close(plane_z(plane()), 15.0), plane_z(plane()))
    s.undo()


def undone():
    h.check("Undo: z = 30 again", s.close(plane_z(plane()), 30.0), plane_z(plane()))
    s.redo()


def redone():
    h.check("Redo: z = 15", s.close(plane_z(plane()), 15.0), plane_z(plane()))
    s.no_popups("the end")
    h.shot("2-end")


h.run(
    "gaps_offset_plane_to",
    b.box_steps("OffsetPlaneTo")
    + [
        post_sketch,
        post_face,
        post_draw,
        post_finish,
        post_extrude,
        post_distance,
        post_ok,
        post_made,
        offset_start,
        click_top,
        choose_to_object,
        object_waits,
        through_corner,
        made,
        edit_post,
        post_twenty,
        post_twenty_ok,
        followed,
        edit_plane,
        reads_to_object,
        distance_kept,
        five,
        edited,
        undone,
        redone,
    ],
)
