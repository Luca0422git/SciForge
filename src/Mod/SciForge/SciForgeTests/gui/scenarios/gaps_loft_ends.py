# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's loft end conditions (how the loft leaves its first profile and meets its last),
only real input.

Box: a 20 x 20 square on XY, Extrude 10. Offset Plane 20 above the top face (z 30), a
10 x 10 square sketched on it (the plane hidden with its eye).
Path E1, CREATE > Loft: the box's top face, then inside the square. First Profile offers
         Connected (G0) / Tangent (G1) / Curvature (G2) (a face of the part), Last Profile
         Connected / Direction (a sketch). Tangent (G1): the loft leaves the top face going
         straight up like the box's walls (Tangency Weight shown); Direction on the last
         profile: it meets the square straight too (Takeoff Weight and Angle shown). OK.
Path E2, double-click Loft 1 in the timeline: it reads Tangent (G1) and Direction; Takeoff
         Weight 2: the loft meets the square more steeply. OK. Undo / redo.
Path E3, a point sketched on XZ 15 above the loft's top. The loft's top face selected, then
         Loft: the face is taken; click the point: Last Profile offers Sharp / Point Tangent;
         Point Tangent: a dome, flat at the top. OK.

Hand-derived (loft_ends_core: a cubic per side line, end derivative = weight x the distance
between the profiles; a square of side L(v) at height z(v)): V = integral L^2 z' dv.
  Connected both ends: 20 (400 - 200 + 100/3) = 4666.67 (straight sides)
  Tangent + Connected: L = 20 - 10 (1.5 v^2 - 0.5 v^3), z = 20 v: 5471.43
  Tangent + Direction (weight 1): L = 20 - 10 (3 v^2 - 2 v^3), z = 20 v: 4742.86
  Tangent + Direction weight 2: z = 20 v^3 - 20 v^2 + 20 v: 87800 / 21 = 4180.95
  Dome on the 10 x 10 face, 15 high: L = 10 (1 - 0.43934 v - 0.56066 v^3),
  z = 30 + 22.5 v - 7.5 v^3: 939.19."""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
BOX = 4000.0
FREE = 20.0 * (400.0 - 200.0 + 100.0 / 3.0)
TANGENT = 5471.428571428571
BOTH = 20.0 * (400.0 - 200.0 + 100.0 * 13.0 / 35.0)
HEAVY = 87800.0 / 21.0
DOME = 939.1933360207186
s = {}


def panel():
    return st.panel("loft")


def items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def vol():
    return h.solid_volume()


# -- the box, the plane, the square ----------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("LoftEnds")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw_square():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, -10, -10, 10, 10)


def finish_square():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def extrude_distance():
    from sciforge import taskui

    p = taskui.current()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude dialog", field is not None):
        ui.type_into(field, "10")


def extrude_ok():
    h.task_button("OK")


def box_made():
    h.check("box 20 x 20 x 10", st.near(vol(), BOX), vol())
    h.fit()
    h.click_empty()
    h.ribbon("Offset Plane")


def pick_top_face():
    h.click(V(5, -5, 10))


def plane_distance():
    from sciforge import construct_ui

    p = construct_ui.ConstructPanel.last
    if h.check("offset plane dialog", p is not None and p.field is not None):
        ui.type_into(p.field.widget, "20")


def plane_ok():
    h.task_button("OK")


def plane_made():
    planes = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Plane"]
    h.check("a plane at z 30", len(planes) == 1 and st.near(planes[0].Placement.Base.z, 30.0))
    if planes:
        s["plane"] = planes[0]
    h.fit()
    h.ribbon("Create Sketch")


def pick_plane():
    h.click(V(-6, 6, 30))


def draw_small_square():
    sk = h.in_sketch()
    h.check(
        "sketch open on the plane", sk is not None and sk.AttachmentSupport[0][0] is s.get("plane")
    )
    if sk:
        h.draw_rectangle(sk, -5, -5, 5, 5)


def finish_small_square():
    h.ribbon("Finish Sketch")


def hide_plane():
    from SciForgeTests.gui import timeline_input as ti

    h.check("plane eye clicked", ti.click_eye(s["plane"].Label))


# -- E1: Tangent (G1) and Direction ----------------------------------------------------------
def loft_start():
    h.check("the plane is hidden", not s["plane"].ViewObject.Visibility)
    h.fit()
    h.click_empty()
    st.menu("Loft")


def click_top_face():
    h.check("Loft dialog open", panel() is not None)
    h.fit()
    h.click(V(5, -5, 10))


def click_square():
    p = panel()
    h.check("the top face is profile 1", p is not None and len(p.profiles) == 1)
    h.click(V(-3, 3, 30))


def lofted_free():
    p = panel()
    if not h.check("two profiles", p is not None and len(p.profiles) == 2, p and p.profiles):
        return
    start, end = p.ends["start"], p.ends["end"]
    h.check(
        "First Profile (a face): Connected (G0) / Tangent (G1) / Curvature (G2)",
        items(start["combo"]) == ["Connected (G0)", "Tangent (G1)", "Curvature (G2)"],
        items(start["combo"]),
    )
    h.check(
        "Last Profile (a sketch): Connected / Direction",
        items(end["combo"]) == ["Connected", "Direction"],
        items(end["combo"]),
    )
    h.check("both Connected at first", start["combo"].currentText() == "Connected (G0)")
    h.check("no weight shown yet", not start["weight"].widget.isVisible())
    h.check("straight sides: + 4666.67", st.near(vol(), BOX + FREE, 1e-6), vol())
    h.check("choose Tangent (G1)", ui.choose(start["combo"], "Tangent (G1)"))


def tangent():
    p = panel()
    if p is None:
        return
    start = p.ends["start"]
    h.check(
        "Tangency Weight shown, no angle",
        start["weight"].widget.isVisible()
        and start["weight_label"].text() == "Tangency Weight"
        and not start["angle"].widget.isVisible(),
    )
    h.check(
        "the loft leaves the top face straight up like the walls: + 5471.43",
        st.near(vol(), BOX + TANGENT, 1e-6),
        (vol(), BOX + TANGENT),
    )
    h.check("no message", p.message.text() == "", p.message.text())
    h.check("choose Direction for the last profile", ui.choose(p.ends["end"]["combo"], "Direction"))


def direction():
    p = panel()
    if p is None:
        return
    end = p.ends["end"]
    h.check(
        "Takeoff Weight and Takeoff Angle shown",
        end["weight"].widget.isVisible()
        and end["weight_label"].text() == "Takeoff Weight"
        and end["angle"].widget.isVisible(),
    )
    h.check(
        "it meets the square straight too: + 4742.86",
        st.near(vol(), BOX + BOTH, 1e-6),
        (vol(), BOX + BOTH),
    )
    h.check("no message", p.message.text() == "", p.message.text())
    h.fit()
    h.shot("1-tangent-and-direction")
    h.task_button("OK")


def e1_kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(vol(), BOX + BOTH, 1e-6), vol())
    h.check("Loft 1 in the timeline", "Loft 1" in st.timeline_titles(), st.timeline_titles())


# -- E2: edit, weight 2, undo / redo ---------------------------------------------------------
def edit_loft():
    h.click_empty()
    st.edit_in_timeline("Loft 1")


def edit_reads():
    p = panel()
    if not h.check("edit dialog open", p is not None):
        return
    start, end = p.ends["start"], p.ends["end"]
    h.check(
        "it reads Tangent (G1) and Direction",
        start["combo"].currentText() == "Tangent (G1)"
        and end["combo"].currentText() == "Direction",
        (start["combo"].currentText(), end["combo"].currentText()),
    )
    ui.type_into(end["weight"].widget, "2")


def weight_two():
    p = panel()
    if p is None:
        return
    h.check(
        "weight 2: it meets the square more steeply: + 4180.95",
        st.near(vol(), BOX + HEAVY, 1e-6),
        (vol(), BOX + HEAVY),
    )
    h.task_button("OK")


def e2_kept():
    h.check("edit kept", st.near(vol(), BOX + HEAVY, 1e-6), vol())
    st.ctrl("z")


def undone():
    h.check("Undo: weight 1 again", st.near(vol(), BOX + BOTH, 1e-6), vol())
    st.ctrl("y")


def redone():
    h.check("Redo: weight 2", st.near(vol(), BOX + HEAVY, 1e-6), vol())
    s["volume"] = vol()
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


# -- E3: a dome to a point ------------------------------------------------------------------------
def pick_xz():
    h.click(V(-17, 0, 12))


def draw_point():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None)
    if sk:
        st.add_point(sk, 0, 45)


def finish_point():
    h.ribbon("Finish Sketch")


def select_loft_top():
    h.fit()
    h.click_empty()
    h.click(V(-2, 2, 30))


def loft_dome():
    h.check("the loft's top face selected", len(Gui.Selection.getSelectionEx()) == 1)
    st.menu("Loft")


def click_point():
    p = panel()
    h.check("the top face is taken", p is not None and len(p.profiles) == 1, p and p.profiles)
    h.click(V(0, 0, 45))


def point_offers():
    p = panel()
    if not h.check("the point is profile 2", p is not None and len(p.profiles) == 2):
        return
    end = p.ends["end"]
    h.check(
        "Last Profile (a point): Sharp / Point Tangent",
        items(end["combo"]) == ["Sharp", "Point Tangent"],
        items(end["combo"]),
    )
    h.check("choose Point Tangent", ui.choose(end["combo"], "Point Tangent"))


def dome():
    p = panel()
    if p is None:
        return
    end = p.ends["end"]
    h.check("Tangency Weight shown", end["weight"].widget.isVisible())
    h.check(
        "a dome on top: + 939.19",
        st.near(vol(), s["volume"] + DOME, 1e-6),
        (vol(), s["volume"] + DOME),
    )
    h.check("no message", p.message.text() == "", p.message.text())
    h.fit()
    h.shot("2-dome")
    h.task_button("OK")


def dome_kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(vol(), s["volume"] + DOME, 1e-6), vol())
    h.check("Loft 2 in the timeline", "Loft 2" in st.timeline_titles(), st.timeline_titles())
    h.check("the part is valid", h.body().Shape.isValid())


h.run(
    "gaps_loft_ends",
    [
        new_design,
        pick_xy,
        draw_square,
        finish_square,
        extrude,
        extrude_distance,
        extrude_ok,
        box_made,
        pick_top_face,
        plane_distance,
        plane_ok,
        plane_made,
        pick_plane,
        draw_small_square,
        finish_small_square,
        hide_plane,
        loft_start,
        click_top_face,
        click_square,
        lofted_free,
        tangent,
        direction,
        e1_kept,
        edit_loft,
        edit_reads,
        weight_two,
        e2_kept,
        undone,
        redone,
        pick_xz,
        draw_point,
        finish_point,
        select_loft_top,
        loft_dome,
        click_point,
        point_offers,
        dome,
        dome_kept,
    ],
)
