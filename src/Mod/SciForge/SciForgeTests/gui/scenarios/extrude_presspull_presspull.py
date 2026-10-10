# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press Pull like Fusion, only real input.

Box 40 x 20 x 10. Q with nothing selected waits; click the top face, then the right
face: both move together and the corner between them fills (Fusion extends the
faces). Click the top face again to drop it, again to take it back. Drag the arrow,
type 2, OK: 42 x 20 x 12. Undo/redo. Edit from the timeline: 3 -> 43 x 20 x 13.
Cancel and Esc leave the part alone. Q on an edge rounds it. A second part: a
trapezoid prism whose top is pulled up; the sloped sides extend (Fusion), they do not
leave a step.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def panel():
    from sciforge import presspull_ui

    return presspull_ui.PressPullPanel.last


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def faces():
    return len(h.body().Shape.Faces)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("PressPull")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 20)


def finish_sketch():
    h.ribbon("Finish Sketch")


def extrude_box():
    h.fit()
    h.press("e")


def box_ok():
    h.task_button("OK")


def box_done():
    h.check("box 40 x 20 x 10", near(h.solid_volume(), 8000.0), h.solid_volume())
    h.fit()


def press_pull_nothing_selected():
    h.click_empty()
    h.press("q")


def waiting():
    p = panel()
    h.check("Q opens Press Pull", p is not None and not p._closed)
    h.check("nothing selected: waiting", p.target is None)
    h.check("no pop-up", not h.popups(), h.popups())
    h.fit()


def click_top():
    h.click(V(20, 10, 10))


def top_picked():
    p = panel()
    h.check(
        "top face picked", p.target is not None and len(p.names) == 1, (p.names, p.message.text())
    )
    h.fit()


def click_right():
    h.click(V(40, 10, 5))


def right_picked():
    p = panel()
    h.check("right face added", len(p.names) == 2, (p.names, p.message.text()))
    ui.type_into(p.field.widget, "2")


def corner_filled():
    p = panel()
    h.check(
        "both faces +2 and the corner filled: 42 x 20 x 12",
        near(h.solid_volume(), 10080.0),
        (h.solid_volume(), p.message.text()),
    )
    h.check("6 faces (no step at the corner)", faces() == 6, faces())
    h.shot("1-corner")
    h.fit()


def click_top_again():
    # The top face where the preview has moved it (away from the arrow in its middle).
    h.click(V(8, 5, 12))


def top_dropped():
    p = panel()
    h.check("clicking the moved top face again drops it", len(p.names) == 1, p.names)
    h.check(
        "only the right face moves: 42 x 20 x 10", near(h.solid_volume(), 8400.0), h.solid_volume()
    )
    h.fit()


def click_top_back():
    h.click(V(8, 5, 10))


def top_back():
    p = panel()
    h.check("top face back", len(p.names) == 2, p.names)
    h.check("42 x 20 x 12 again", near(h.solid_volume(), 10080.0), h.solid_volume())
    h.fit()


def drag_arrow():
    p = panel()
    h.check("arrow shown", p.dragger is not None)
    if p.dragger is None:
        return
    s["before"] = p.field.value()
    place = p.dragger.root.getChild(0)
    origin = place.translation.getValue().getValue()
    axis = place.rotation.getValue().multVec(p.dragger.coin.SbVec3f(1, 0, 0)).getValue()
    tip = V(*origin) + V(*axis) * (p.dragger.distance() + p.dragger.size * 0.9)
    end = V(*origin) + V(*axis) * (p.dragger.distance() + p.dragger.size * 0.9 + 4.0)
    h.drag(h.screen_point(tip), h.screen_point(end))


def dragged():
    p = panel()
    h.check(
        "dragging the arrow changes the distance",
        p.field.value() > s["before"] + 0.5,
        (p.field.value(), s["before"]),
    )
    ui.type_into(p.field.widget, "2")


def ok():
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("OK keeps 42 x 20 x 12", near(h.solid_volume(), 10080.0), h.solid_volume())
    h.check(
        "timeline shows Press Pull 1", "Press Pull 1" in ui.timeline_titles(), ui.timeline_titles()
    )


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("Undo: back to the box", near(h.solid_volume(), 8000.0), h.solid_volume())


def redo():
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check("Redo: 42 x 20 x 12", near(h.solid_volume(), 10080.0), h.solid_volume())
    h.fit()


def edit():
    h.check(
        "double-click Press Pull 1", ui.double_click_timeline("Press Pull 1"), ui.timeline_titles()
    )


def editing():
    p = panel()
    h.check("Press Pull dialog on the feature", p is not None and p.editing and not p._closed)
    if not (p and p.editing):
        return
    h.check("both faces are back", len(p.names) == 2, p.names)
    h.check("distance 2 is back", near(p.field.value(), 2.0), p.field.value())
    ui.type_into(p.field.widget, "3")


def edit_ok():
    h.check("edit preview 43 x 20 x 13", near(h.solid_volume(), 11180.0), h.solid_volume())
    h.task_button("OK")


def after_edit():
    h.check("edit kept", near(h.solid_volume(), 11180.0), h.solid_volume())
    s["volume"] = h.solid_volume()
    s["count"] = len(h.body().Group)
    h.fit()


def cancel_start():
    # Select the top face first, then Q: Press Pull starts on it at once.
    h.click_empty()
    h.fit()
    h.click(V(20, 10, 13))


def cancel_click():
    h.check("the top face is selected", len(Gui.Selection.getSelectionEx()) == 1)
    h.press("q")
    p = panel()
    h.check("Q with a selected face starts at once", p is not None and p.target is not None)


def cancel_type():
    p = panel()
    h.check("face picked for the cancel test", p.target is not None, p.message.text())
    ui.type_into(p.field.widget, "-1")


def cancel_now():
    h.check("preview pushes the top down", h.solid_volume() < s["volume"] - 1.0)
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel leaves the part", near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.check("Cancel leaves no feature", len(h.body().Group) == s["count"])
    h.fit()


def esc_start():
    h.click_empty()
    h.press("q")


def esc_click():
    h.fit()
    h.click(V(20, 10, 13))


def esc_type():
    ui.type_into(panel().field.widget, "4")


def esc_now():
    h.check("preview pulls the top", h.solid_volume() > s["volume"] + 1.0)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes Press Pull", not Gui.Control.activeDialog())
    h.check("Esc leaves the part", near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.fit()


def edge_start():
    h.click_empty()
    h.press("q")


def click_edge():
    h.fit()
    # Just off the top front edge (y = 0, z = 13), so the edge, not a face, is under the
    # pointer (FreeCAD picks an edge within a few pixels).
    h.click(V(15, -0.12, 13.12))


def edge_picked():
    p = panel()
    h.check(
        "an edge makes a fillet",
        p.mode == "fillet" and p.target is not None,
        (p.mode, p.message.text(), s.get("last")),
    )
    ui.type_into(p.field.widget, "2")


def edge_ok():
    h.task_button("OK")


def after_edge():
    # One straight edge 43 long rounded with r 2: removes (r^2 - pi r^2 / 4) * 43.
    want = s["volume"] - (4.0 - math.pi) * 43.0
    h.check(
        "fillet r2 on the 43 mm edge", near(h.solid_volume(), want, 1e-5), (h.solid_volume(), want)
    )
    h.shot("2-fillet")


# -- a second part: sloped neighbours ------------------------------------------------------
def second_design():
    App.newDocument("Slopes")
    h.fit()


def slope_sketch():
    h.ribbon("Create Sketch")


def pick_xz():
    # The XZ square at x > 0: nothing else is between it and the camera there.
    h.click(V(15, 0, 12))


def draw_trapezoid():
    import Part
    import Sketcher

    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None)
    if not sk:
        return
    support = sk.AttachmentSupport[0][0]
    h.check("on the XZ plane", "XZ" in (support.Role or support.Name), support.Name)
    pts = [V(0, 0, 0), V(40, 0, 0), V(30, 20, 0), V(10, 20, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    App.ActiveDocument.recompute()


def finish_trapezoid():
    h.ribbon("Finish Sketch")


def extrude_trapezoid():
    h.fit()
    h.press("e")


def trapezoid_depth():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("trapezoid picked by itself", p.target is not None, p.message.text())
    ui.type_into(p.distance.widget, "20")


def trapezoid_ok():
    h.task_button("OK")


def trapezoid_done():
    h.check("trapezoid prism (40+20)/2*20*20", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.fit()


def pull_top():
    h.click_empty()
    h.press("q")


def click_trapezoid_top():
    h.fit()
    top = h.body().Shape.BoundBox
    h.click(V(20, (top.YMin + top.YMax) / 2.0, 20))


def type_5():
    p = panel()
    h.check("top of the trapezoid picked", p.target is not None, p.message.text())
    ui.type_into(p.field.widget, "5")


def slope_ok():
    h.check(
        "sloped sides extended: (40+15)/2*25*20",
        near(h.solid_volume(), 13750.0),
        (h.solid_volume(), panel().message.text()),
    )
    h.check("6 faces: no step", faces() == 6, faces())
    h.shot("3-slopes")
    h.task_button("OK")


def slope_done():
    h.check("kept after OK", near(h.solid_volume(), 13750.0), h.solid_volume())


def sketch_on_top():
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_top_face():
    h.fit()
    h.click(V(14, -18, 25))


def draw_square():
    sk = h.in_sketch()
    h.check("sketch on the pulled top face", sk is not None)
    if sk:
        ax, ay = h.to_sketch(sk, V(15, -15, 25))
        bx, by = h.to_sketch(sk, V(25, -5, 25))
        h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def finish_square():
    h.ribbon("Finish Sketch")


def press_pull_on_profile():
    h.click_empty()
    h.fit()
    h.press("q")


def click_profile():
    p = panel()
    regions = len(p.picker.regions) if p is not None and p.picker is not None else 0
    h.check("Press Pull shades the visible sketch area", regions == 1, regions)
    h.fit()
    h.click(V(17, -12, 25))


def became_extrude():
    from sciforge import extrude_ui

    e = extrude_ui.ExtrudePanel.last
    h.check(
        "Press Pull on a sketch area starts Extrude on it",
        e is not None and not e._closed and e.target is not None,
        e and e.message.text(),
    )
    h.check("the Press Pull dialog is gone", panel()._closed)
    h.task_button("OK")


def profile_extruded():
    h.check(
        "the 10 x 10 area extruded 10 on top", near(h.solid_volume(), 14750.0), h.solid_volume()
    )
    h.shot("4-profile")


h.run(
    "presspull",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw,
        finish_sketch,
        extrude_box,
        box_ok,
        box_done,
        press_pull_nothing_selected,
        waiting,
        click_top,
        top_picked,
        click_right,
        right_picked,
        corner_filled,
        click_top_again,
        top_dropped,
        click_top_back,
        top_back,
        drag_arrow,
        dragged,
        ok,
        after_ok,
        undo,
        undone,
        redo,
        redone,
        edit,
        editing,
        edit_ok,
        after_edit,
        cancel_start,
        cancel_click,
        cancel_type,
        cancel_now,
        after_cancel,
        esc_start,
        esc_click,
        esc_type,
        esc_now,
        after_esc,
        edge_start,
        click_edge,
        edge_picked,
        edge_ok,
        after_edge,
        second_design,
        slope_sketch,
        pick_xz,
        draw_trapezoid,
        finish_trapezoid,
        extrude_trapezoid,
        trapezoid_depth,
        trapezoid_ok,
        trapezoid_done,
        pull_top,
        click_trapezoid_top,
        type_5,
        slope_ok,
        slope_done,
        sketch_on_top,
        pick_top_face,
        draw_square,
        finish_square,
        press_pull_on_profile,
        click_profile,
        became_extrude,
        profile_extruded,
    ],
)
