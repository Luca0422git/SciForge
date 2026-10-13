# SPDX-License-Identifier: LGPL-2.1-or-later
"""The value boxes next to the handles of Revolve, Box, Rectangular Pattern and Rib (the
dialogs whose handles are not Extrude's arrows), only real input on the dialogs. For each
box: it shows the dialog field's text, follows the handle when the view pans, never covers
the handle's grabbable part, takes a value typed in it (a click away keeps it), and Cancel
removes it.

Revolve: a 10 x 20 rectangle on XZ revolved about Z, Type Angle, 90 typed in the box: a
quarter cylinder (2000 pi / 4). Box: 40 x 20 placed by two corners, 10 typed in the
height box: 8000. Pattern: a hole r2 in a 40 x 30 x 10 box repeated along X, 24 typed in
the distance box. Rib: an L bracket with a rib line, 3 typed in the thickness box.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import revolve_input as ri
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
s = {}
PAN = -80
CYL = 2000.0 * math.pi


def panel():
    from sciforge import taskui

    return taskui.current()


def near(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


def check_box(what, key, field, handle):
    """The common checks of one dialog's value box. Returns the box (or None)."""
    p = panel()
    box = a.value_box(key, p)
    if not h.check("%s: a value box next to its handle" % what, box is not None and box.isVisible(),
                   (key, p and sorted(p.value_boxes.boxes))):
        return None
    h.check("%s: the box shows the field's text" % what, box.text() == field.widget.text(),
            (box.text(), field.widget.text()))
    h.check("%s: the box does not have the keyboard" % what, not box.hasFocus(), a.focus_name())
    anchor, tail, tip, _radius = handle.box_geometry()
    for name, point in (("tail", tail), ("middle", anchor), ("tip", tip)):
        pos = h.screen_point(point)
        h.check("%s: the box is not over the handle's %s" % (what, name),
                a.top_name(pos) != a.BOX_NAME, (pos.x(), pos.y(), a.top_name(pos)))
    s["box_x"] = box.pos().x()
    s["box"] = box
    return box


def pan_view():
    h.pan(PAN, 0)


def box_followed(what):
    box = s.get("box")
    moved = box.pos().x() - s["box_x"] if box is not None else None
    h.check("%s: the box follows the handle when the view pans" % what,
            moved is not None and abs(moved - PAN) <= 25, (moved, PAN))


def type_in_box(text, field):
    box = s.get("box")
    if box is None:
        return
    a.type_in_box(box, text, enter=False)
    h.check("the box has the keyboard while typing", box.hasFocus(), a.focus_name())
    b.click_widget(field.widget)  # a click away keeps what was typed


def gone(what):
    h.check("%s: Cancel closed the dialog" % what, panel() is None and not Gui.Control.activeDialog())
    h.check("%s: no value box left" % what, not a.value_boxes(visible_only=False),
            len(a.value_boxes(visible_only=False)))


# -- Revolve -----------------------------------------------------------------------------------
def revolve_setup():
    from sciforge import commands, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("ValueBoxRevolve")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XZ_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 10, 20)
    App.ActiveDocument.recompute()
    h.fit()
    Gui.Selection.clearSelection()
    h.ribbon("Revolve")


def revolve_click_z():
    p = ri.panel()
    h.check("Revolve: the sketch's profile is taken", p is not None and len(p.profiles) == 1)
    h.fit()
    h.click(V(0, 0, 32))


def revolve_angle_type():
    p = ri.panel()
    h.check("Revolve: a cylinder", near(h.solid_volume(), CYL), h.solid_volume())
    if p is not None:
        h.check("Revolve: Type Angle", ui.choose(p.type, "Angle"))


def revolve_box():
    p = ri.panel()
    h.check("Revolve: the angle handle is there", p is not None and "angle" in p.handles,
            p and list(p.handles))
    if p is None or "angle" not in p.handles:
        return
    check_box("Revolve", "angle", p.angle, p.handles["angle"])
    pan_view()


def revolve_typed():
    p = ri.panel()
    box_followed("Revolve")
    if p is not None:
        type_in_box("90", p.angle)


def revolve_90():
    p = ri.panel()
    h.check("Revolve: 90 typed in the box is the angle", p is not None and near(p.angle.value(), 90.0),
            p and p.angle.value())
    h.check("Revolve: a quarter cylinder", near(h.solid_volume(), CYL / 4), h.solid_volume())
    h.task_button("Cancel")


def revolve_gone():
    gone("Revolve")


# -- Box ------------------------------------------------------------------------------------------
def box_start():
    App.newDocument("ValueBoxBox")
    h.fit()
    pi.menu("Box")


def box_plane():
    h.click(V(15, -15, 0))


def box_first_corner():
    pi.hover(V(5, 5, 0))
    h.click(V(0, 0, 0))


def box_second_corner():
    pi.hover(V(30, 10, 0))
    h.click(V(40, 20, 0))


box_second_corner.wait_ms = 1200


def box_box():
    p = pi.panel("BoxPanel")
    h.check("Box: placed with its handles", p is not None and p.state == "ready"
            and set(p.handles) == {"height", "length", "width"}, p and (p.state, list(p.handles)))
    if p is None or "height" not in p.handles:
        return
    h.check("Box: a box per handle", sorted(p.value_boxes.shown()) == ["height", "length", "width"],
            sorted(p.value_boxes.shown()))
    check_box("Box", "height", p.height, p.handles["height"])
    pan_view()


def box_typed():
    p = pi.panel("BoxPanel")
    box_followed("Box")
    if p is not None:
        type_in_box("10", p.height)


def box_ten():
    p = pi.panel("BoxPanel")
    h.check("Box: 10 typed in the box is the height", p is not None and near(p.height.value(), 10.0),
            p and p.height.value())
    h.check("Box: 40 x 20 x 10", near(pi.total_volume(), 8000.0), pi.total_volume())
    h.task_button("Cancel")


def box_gone():
    gone("Box")


# -- Rectangular Pattern -----------------------------------------------------------------------------
def pattern_open():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Rectangular Pattern")


def pattern_click_hole_step():
    ps.timeline_click("Extrude 2")


def pattern_click_direction_box():
    ps.click_box("direction")


def pattern_click_x_axis():
    h.fit()
    h.click(V(-12, 0, 0))


def pattern_box():
    p = ps.panel()
    h.check("Pattern: arrows for both directions", p is not None and "distance" in p.handles,
            p and list(p.handles))
    if p is None or "distance" not in p.handles:
        return
    check_box("Pattern", "distance", p.distance_field, p.handles["distance"])
    pan_view()


def pattern_typed():
    p = ps.panel()
    box_followed("Pattern")
    if p is not None:
        type_in_box("24", p.distance_field)


def pattern_24():
    p = ps.panel()
    h.check("Pattern: 24 typed in the box is the distance",
            p is not None and near(p.distance_field.value(), 24.0), p and p.distance_field.value())
    centres = ps.circle_centres(h.body().Shape, 2.0, z=10)
    h.check("Pattern: the copies follow (x = 8, 32)", centres == [(8, 8), (32, 8)], centres)
    h.task_button("Cancel")


def pattern_gone():
    gone("Pattern")


# -- Rib --------------------------------------------------------------------------------------------
def rib_setup():
    from sciforge import commands, extrude, sketch_ui

    App.newDocument("ValueBoxRib")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    bracket = sketch_ui.create_sketch(body, (planes["XZ_Plane"], ""))
    st.add_lines(bracket, [(0, 0), (40, 0), (40, 5), (5, 5), (5, 40), (0, 40)], closed=True)
    extrude.make(body, bracket, {"distance": 10.0, "direction": "symmetric", "measurement": "whole"})
    App.ActiveDocument.recompute()
    line = sketch_ui.create_sketch(body, (planes["XZ_Plane"], ""))
    st.add_lines(line, [(5, 25), (25, 5)])
    App.ActiveDocument.recompute()
    s["rib_line"] = line
    s["bracket"] = h.solid_volume()
    h.fit()
    h.check("Rib: the L bracket", near(s["bracket"], 375.0 * 10.0), s["bracket"])
    h.click_empty()


def rib_click_line():
    g = s["rib_line"].getGlobalPlacement()
    mid = g.multVec(V(15, 15, 0))  # the rib line's middle (sketch coordinates)
    h.check("Rib: the line is clicked", h.click_edge(mid))


def rib_open():
    st.menu("Rib")


def rib_box():
    p = st.panel("rib")
    h.check("Rib: opens with the line taken and a thickness arrow",
            p is not None and len(p.refs) == 1 and "thickness" in p.arrows,
            p and (p.refs, list(p.arrows)))
    if p is None or "thickness" not in p.arrows:
        return
    check_box("Rib", "thickness", p.thickness, p.arrows["thickness"])
    pan_view()


def rib_typed():
    p = st.panel("rib")
    box_followed("Rib")
    if p is not None:
        type_in_box("3", p.thickness)


def rib_three():
    p = st.panel("rib")
    h.check("Rib: 3 typed in the box is the thickness", p is not None and near(p.thickness.value(), 3.0),
            p and p.thickness.value())
    h.check("Rib: the rib follows (a 3 mm gusset)", h.solid_volume() > s["bracket"] + 3.0 * 100.0,
            h.solid_volume())
    h.task_button("Cancel")


def rib_gone():
    gone("Rib")


h.run(
    "value_box_dialogs_2",
    [
        revolve_setup,
        revolve_click_z,
        revolve_angle_type,
        revolve_box,
        revolve_typed,
        revolve_90,
        revolve_gone,
        box_start,
        box_plane,
        box_first_corner,
        box_second_corner,
        box_box,
        box_typed,
        box_ten,
        box_gone,
    ]
    + b.box_steps("ValueBoxPattern")
    + ps.make_cut("hole", (8, 8), 2.0)
    + [
        pattern_open,
        pattern_click_hole_step,
        pattern_click_direction_box,
        pattern_click_x_axis,
        pattern_box,
        pattern_typed,
        pattern_24,
        pattern_gone,
        rib_setup,
        rib_click_line,
        rib_open,
        rib_box,
        rib_typed,
        rib_three,
        rib_gone,
    ],
)
