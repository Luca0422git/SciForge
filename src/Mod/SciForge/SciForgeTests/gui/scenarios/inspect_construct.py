# SPDX-License-Identifier: LGPL-2.1-or-later
"""CONSTRUCT > Offset Plane like Luca uses it in Fusion, only real input, then a sketch on
the construction plane and an extrude from it.

Part: box 40 x 30 x 10 from the origin (real input). Hand-derived expectations:
  Offset Plane on the top face (z = 10): the plane is at z = 10 + distance, normal +Z.
  A 10 x 10 square sketched on the plane at z = 15 and extruded 10 down joins the box
  (z = 5 to 15 overlaps it from 5 to 10): 12000 + 10 * 10 * 5 = 12500.

Paths: nothing selected (the dialog waits, the origin squares are drawn), a click on the top
face, the blue arrow dragged, a typed value, OK; undo / redo; double-click in the timeline
to edit; Cancel leaves the design unchanged; Esc too; a second Offset Plane started with a
face already selected and finished with Enter; an origin square clicked; Create Sketch on
the construction plane by clicking it; Extrude from that sketch."""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s

V = App.Vector
st = {}


def start_nothing_selected():
    h.click_empty()
    h.ribbon("Offset Plane")


def waits_for_a_face():
    p = s.construct_panel()
    h.check("Offset Plane dialog open", p is not None and p.title == "Offset Plane")
    if p is None:
        return
    h.check("nothing made yet", p.datum is None and not s.datums(), s.datums())
    h.check("the Plane box is blue", p.boxes[0].button.isChecked())
    h.check("it says what to click", "flat face" in p.message.text(), p.message.text())
    h.check("origin squares drawn to click", "planes" in p.overlays, list(p.overlays))
    s.no_popups("Offset Plane started")
    h.shot("1-offset-waits")


def click_top_face():
    h.fit()
    h.click(V(20, 15, 10))


def preview_10_above():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("a plane is shown at once", d is not None)
    if d is None:
        return
    gp = d.getGlobalPlacement()
    h.check("10 mm above the top face", s.close(gp.Base.z, 20.0), gp)
    h.check("parallel to it", s.near(s.normal_of(d), V(0, 0, 1)), s.normal_of(d))
    h.check("the box shows the face", "face" in s.box_value(p, 0), s.box_value(p, 0))
    h.check("the blue arrow is there", p.handle is not None and p.handle_key == "distance")
    h.shot("2-offset-preview")


def drag_arrow():
    p = s.construct_panel()
    if p is None or p.handle is None:
        return
    h.fit()
    handle = p.handle
    grab = handle.base_point() + handle.direction * (handle.size * 0.55)
    start = s.screen(grab)
    st["before_drag"] = p.values["distance"]
    s.drag_px(start, 0, -40)


def dragged_up():
    p = s.construct_panel()
    if p is None:
        return
    value = p.values["distance"]
    h.check("dragging the arrow up moved the plane up", value > st["before_drag"] + 1, value)
    field = p.distance.value()
    h.check("the Distance field follows the arrow", s.close(field, value, 1e-3), (field, value))
    gp = p.datum.getGlobalPlacement()
    h.check("plane follows the drag", s.close(gp.Base.z, 10 + value, 1e-3), (gp.Base.z, value))


def type_15():
    p = s.construct_panel()
    if p is not None:
        s.type_into(p.distance.widget, "15")


def typed_15():
    p = s.construct_panel()
    if p is None:
        return
    gp = p.datum.getGlobalPlacement()
    h.check("typed 15: plane at z = 25", s.close(gp.Base.z, 25.0), gp.Base.z)
    h.check("the arrow moved with it", s.close(p.handle.value(), 15.0), p.handle.value())


def ok_1():
    h.task_button("OK")


def made_plane1():
    planes = s.datums("PartDesign::Plane")
    h.check("one construction plane", len(planes) == 1, [o.Label for o in planes])
    if not planes:
        return
    plane = planes[0]
    st["plane"] = plane.Name
    h.check("named like Fusion: Plane1", plane.Label == "Plane1", plane.Label)
    h.check("dialog closed", s.construct_panel() is None and not Gui.Control.activeDialog())
    h.check("still at z = 25", s.close(plane.getGlobalPlacement().Base.z, 25.0))
    h.check("in the timeline", s.timeline_title_of(plane) is not None, s.timeline_titles())
    h.check("part unchanged", s.close(h.solid_volume(), 12000.0), h.solid_volume())
    h.check("nothing left selected", not Gui.Selection.getSelectionEx(), s.selection())
    h.shot("3-plane1")


def undo_plane():
    s.undo()


def plane_undone():
    h.check("Undo removes the plane", App.ActiveDocument.getObject(st["plane"]) is None)
    s.redo()


def plane_redone():
    plane = App.ActiveDocument.getObject(st["plane"])
    h.check("Redo brings it back", plane is not None)
    if plane is not None:
        h.check("at z = 25 again", s.close(plane.getGlobalPlacement().Base.z, 25.0))


def edit_from_timeline():
    s.double_click_timeline(App.ActiveDocument.getObject(st["plane"]))


def edit_dialog():
    p = s.construct_panel()
    h.check("double-click opens Offset Plane again", p is not None and p.editing, p)
    if p is None:
        return
    h.check("with its face", "face" in s.box_value(p, 0), s.box_value(p, 0))
    h.check("and its distance", s.close(p.distance.value(), 15.0), p.distance.value())
    s.type_into(p.distance.widget, "5")


def edit_ok():
    h.task_button("OK")


def edited():
    plane = App.ActiveDocument.getObject(st["plane"])
    h.check("edited: z = 15", s.close(plane.getGlobalPlacement().Base.z, 15.0))
    h.check("still one plane", len(s.datums("PartDesign::Plane")) == 1)
    h.check("still Plane1", plane.Label == "Plane1", plane.Label)


def cancel_start():
    h.click_empty()
    h.ribbon("Offset Plane")


def cancel_pick():
    """Plane1 (z = 15) lies over the part: the click takes Plane1 itself."""
    h.click(V(30, 20, 10))


def cancel_type():
    p = s.construct_panel()
    h.check("second dialog previews a plane", p is not None and p.datum is not None)
    if p is None or p.datum is None:
        return
    h.check("offset from Plane1 (it is in front)", "Plane1" in s.box_value(p, 0), s.box_value(p, 0))
    h.check("10 above Plane1", s.close(p.datum.getGlobalPlacement().Base.z, 25.0))
    s.type_into(p.distance.widget, "30")


def cancel_press():
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel: still one plane", len(s.datums("PartDesign::Plane")) == 1, s.datums())
    h.check("Cancel: part unchanged", s.close(h.solid_volume(), 12000.0))
    plane = App.ActiveDocument.getObject(st["plane"])
    h.check("Cancel: Plane1 untouched", s.close(plane.getGlobalPlacement().Base.z, 15.0))


def esc_start():
    h.ribbon("Offset Plane")


def esc_pick():
    h.click(V(30, 20, 10))


def esc_press():
    s.press_escape()


def escaped():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("Esc: still one plane", len(s.datums("PartDesign::Plane")) == 1, s.datums())


def hide_plane1():
    h.click_empty()
    s.eye("Plane1")


def preselect_face():
    plane = App.ActiveDocument.getObject(st["plane"])
    h.check("Plane1 hidden with its eye", not plane.ViewObject.Visibility)
    h.fit()
    h.click(V(5, 5, 10))


def preselected_start():
    h.check("the face is selected", bool(Gui.Selection.getSelectionEx()), s.selection())
    h.ribbon("Offset Plane")


def preselected_preview():
    p = s.construct_panel()
    h.check("the selected face is taken", p is not None and p.datum is not None)
    if p is not None and p.datum is not None:
        z = p.datum.getGlobalPlacement().Base.z
        h.check("a new plane 10 above the top", s.close(z, 20.0), z)
    s.press_enter()


def entered():
    planes = s.datums("PartDesign::Plane")
    h.check("Enter finished it: two planes", len(planes) == 2, [o.Label for o in planes])
    h.check("the new one is Plane2", sorted(o.Label for o in planes) == ["Plane1", "Plane2"])


def hide_plane2():
    s.eye("Plane2")


def origin_square_start():
    h.click_empty()
    h.ribbon("Offset Plane")


def click_xz_square():
    """The XZ square at y = 0 below the part: from the iso view nothing else is in front
    of (8, 0, -8) (the line of sight meets z = 0 at x = 16, beyond the XY square's 12; the
    YZ square is behind). The squares are 0.6 x the part (24 mm)."""
    h.fit()
    h.click(V(8, 0, -8))


def offset_from_xz():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("the XZ origin square was taken", d is not None and "XZ" in s.box_value(p, 0))
    if d is None:
        return
    n = s.normal_of(d)
    gp = d.getGlobalPlacement()
    h.check("parallel to XZ", abs(abs(n.y) - 1) < 1e-9, n)
    h.check("10 from it", s.close(abs(gp.Base.y), 10.0), gp)
    h.task_button("Cancel")


def show_plane1():
    s.eye("Plane1")


def sketch_on_plane():
    plane = App.ActiveDocument.getObject(st["plane"])
    h.check("Plane1 shown again", plane.ViewObject.Visibility)
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def click_plane1():
    """Plane1 (z = 15) is drawn bigger than the part: click it beside the part."""
    plane = App.ActiveDocument.getObject(st["plane"])
    p = plane.getGlobalPlacement().Base
    h.click(V(-6, 34, p.z))


def sketch_opened_on_plane1():
    sk = h.in_sketch()
    h.check("a sketch opened", sk is not None)
    if sk is None:
        return
    st["sketch"] = sk.Name
    support = [o.Name for o, _s in sk.AttachmentSupport]
    h.check("on Plane1", support == [st["plane"]], support)
    h.check("at z = 15", s.close(sk.getGlobalPlacement().Base.z, 15.0), sk.getGlobalPlacement())
    h.draw_rectangle(sk, 15, 10, 25, 20)
    h.shot("4-sketch-on-plane")


def finish_sketch():
    h.ribbon("Finish Sketch")


def extrude_down():
    h.fit()
    h.press("e")


def extrude_minus_10():
    from SciForgeTests.gui import blend_steps as bs

    panel = bs.active_panel()
    field = getattr(getattr(panel, "distance", None), "widget", None)
    h.check("Extrude took the sketch", field is not None)
    if field is not None:
        s.type_into(field, "-10")


def extrude_ok():
    h.task_button("OK")


def cut_from_plane():
    v = h.solid_volume()
    h.check("the square joined the box: 12500", s.close(v, 12500.0), v)
    h.shot("5-cut")


def sketch_over_part():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def click_plane1_over_part():
    """Plane1 seen in front of the part (and of the origin XY square behind it)."""
    h.click(V(30, 22, 15))


def sketch_on_plane1_again():
    sk = h.in_sketch()
    h.check("a second sketch opened", sk is not None)
    if sk is None:
        return
    support = [o.Name for o, _s in sk.AttachmentSupport]
    h.check("on Plane1, not on the origin behind it", support == [st["plane"]], support)
    h.ribbon("Finish Sketch")


def the_end():
    h.check("no pop-ups at the end", not h.popups(), h.popups())
    h.shot("6-end")


h.run(
    "inspect_construct",
    b.box_steps("InspectConstruct")
    + [
        start_nothing_selected,
        waits_for_a_face,
        click_top_face,
        preview_10_above,
        drag_arrow,
        dragged_up,
        type_15,
        typed_15,
        ok_1,
        made_plane1,
        undo_plane,
        plane_undone,
        plane_redone,
        edit_from_timeline,
        edit_dialog,
        edit_ok,
        edited,
        cancel_start,
        cancel_pick,
        cancel_type,
        cancel_press,
        cancelled,
        esc_start,
        esc_pick,
        esc_press,
        escaped,
        hide_plane1,
        preselect_face,
        preselected_start,
        preselected_preview,
        entered,
        hide_plane2,
        origin_square_start,
        click_xz_square,
        offset_from_xz,
        show_plane1,
        sketch_on_plane,
        click_plane1,
        sketch_opened_on_plane1,
        finish_sketch,
        extrude_down,
        extrude_minus_10,
        extrude_ok,
        cut_from_plane,
        sketch_over_part,
        click_plane1_over_part,
        sketch_on_plane1_again,
        the_end,
    ],
)
