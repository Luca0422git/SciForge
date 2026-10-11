# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scale the way a Fusion user does it, only real input: the ribbon's Scale with nothing
selected (the dialog waits for the body), click the part, drag the blue arrow, click a
corner as the point (again to go back to the origin), type the factor, Non Uniform X / Y /
Z, a factor of 0 (explained in the dialog, OK waits), OK, Ctrl+Z / Ctrl+Y, edit from the
timeline, Cancel and Esc leave the part as it was, and a second Scale on the body picked
in the browser beforehand, finished with Enter.

Box 40 x 30 x 10 from the origin; a scale by (sx, sy, sz) about a point p multiplies the
volume by sx * sy * sz and maps each corner c to p + (c - p) * s."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}
TOP = V(20, 15, 10)
CORNER = V(40, 30, 10)


def bbox_is(box, expect):
    got = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
    return all(abs(a - b) < 1e-6 for a, b in zip(got, expect)), got


def ribbon_scale():
    Gui.Selection.clearSelection()
    h.ribbon("Scale")


def waiting():
    p = sd.scale_panel()
    h.check("Scale dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("waits for the body", p.base is None and p.active == "entities")
    h.check("Entities box is the blue one", p.entities.button.isChecked())
    h.check("Point box says Origin", p.point_box.button.text() == "Origin")
    h.check("no step made yet", p.target is None and not sd.scales())
    h.check("no error while waiting", p.message.text() == "", p.message.text())
    h.check("Scale Factor 1 to start", abs(p.factor.value() - 1.0) < 1e-9, p.factor.value())
    h.check("Uniform: X/Y/Z hidden", not p.axis_fields["x"].widget.isVisible())
    sd.no_popups("Scale with nothing selected")
    h.shot("1-waiting")


def click_part():
    h.fit()
    h.click(TOP)


def body_picked():
    p = sd.scale_panel()
    h.check("the body is picked", p is not None and p.base is not None, p and p.message.text())
    h.check("Entities shows the body", p and p.entities.button.text() == "Body")
    h.check("the Point box takes the clicks now", p is not None and p.active == "point")
    h.check("a Scale step previewed", len(sd.scales()) == 1, sd.scales())
    h.check("factor 1: the part is unchanged", sd.close(h.solid_volume(), sd.BOX))
    h.check("a blue arrow on the far corner", p is not None and len(p.arrows) == 1)


def drag_arrow():
    p = sd.scale_panel()
    if p is None or not p.arrows:
        h.check("arrow to drag", False)
        return
    h.fit()
    start, end = sd.arrow_screen(p, along=8.0)
    h.drag(start, end)


def dragged():
    p = sd.scale_panel()
    f = p.factor.value() if p else 1.0
    h.check("dragging the arrow outward grows the factor", f > 1.05, f)
    v = h.solid_volume()
    h.check("preview: 12000 * f^3", sd.close(v, sd.BOX * f**3), (v, f))
    h.shot("2-dragged")
    if p:
        sd.type_into(p.factor.widget, "1")


def click_corner():
    h.fit()
    sd.click_vertex(CORNER)


def corner_picked():
    p = sd.scale_panel()
    h.check(
        "the corner is the point",
        p is not None and p.point_ref is not None and p.point_ref[1].startswith("Vertex"),
        p and p.point_ref,
    )
    h.check("the Point box names it", p and p.point_box.button.text().startswith("Vertex"))
    if p:
        sd.type_into(p.factor.widget, "0.5")


def half_about_corner():
    v = h.solid_volume()
    h.check("half size: 1500", sd.close(v, 1500.0), v)
    ok, got = bbox_is(h.body().Shape.BoundBox, [20, 15, 5, 40, 30, 10])
    h.check("shrunk toward the corner (40, 30, 10)", ok, got)
    h.shot("3-half")
    p = sd.scale_panel()
    if p:
        sd.choose(p.scale_type, "Non Uniform")


def non_uniform():
    p = sd.scale_panel()
    h.check(
        "Non Uniform shows X / Y / Z Scale",
        p is not None and all(p.axis_fields[a].widget.isVisible() for a in "xyz"),
    )
    h.check("and hides Scale Factor", p is not None and not p.factor.widget.isVisible())
    h.check("three arrows", p is not None and len(p.arrows) == 3, p and len(p.arrows))
    if p:
        sd.type_into(p.axis_fields["x"].widget, "2")


def type_z():
    p = sd.scale_panel()
    if p:
        sd.type_into(p.axis_fields["z"].widget, "0.5")


def non_uniform_preview():
    v = h.solid_volume()
    h.check("2 x 1 x 0.5: volume unchanged", sd.close(v, sd.BOX), v)
    ok, got = bbox_is(h.body().Shape.BoundBox, [-40, 0, 5, 40, 30, 10])
    h.check("about the corner: x -40..40, z 5..10", ok, got)
    h.shot("4-non-uniform")


def click_corner_again():
    h.fit()
    sd.click_vertex(CORNER)


def back_to_origin():
    p = sd.scale_panel()
    h.check("clicking the corner again: back to the origin", p is not None and p.point_ref is None)
    h.check("Point box says Origin", p and p.point_box.button.text() == "Origin")
    ok, got = bbox_is(h.body().Shape.BoundBox, [0, 0, 0, 80, 30, 5])
    h.check("about the origin: 80 x 30 x 5", ok, got)
    if p:
        sd.choose(p.scale_type, "Uniform")


def uniform_again():
    v = h.solid_volume()
    h.check("Uniform 0.5 about the origin: 1500", sd.close(v, 1500.0), v)
    p = sd.scale_panel()
    if p:
        sd.type_into(p.factor.widget, "0")


def zero_refused():
    p = sd.scale_panel()
    text = p.message.text() if p else ""
    h.check("a factor of 0 is explained in the dialog", "more than 0" in text, text)
    h.check("the preview keeps the last good factor", sd.close(h.solid_volume(), 1500.0))
    h.task_button("OK")


def ok_waits():
    h.check("OK waits while the factor is 0", sd.scale_panel() is not None)
    p = sd.scale_panel()
    if p:
        sd.type_into(p.factor.widget, "2")


def ok():
    p = sd.scale_panel()
    h.check("message gone", p is not None and p.message.text() == "", p and p.message.text())
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    shape = h.body().Shape
    h.check("twice the size: 96000", sd.close(shape.Volume, 96000.0), shape.Volume)
    ok_, got = bbox_is(shape.BoundBox, [0, 0, 0, 80, 60, 20])
    h.check("80 x 60 x 20 from the origin", ok_, got)
    h.check("still 6 flat faces", len(shape.Faces) == 6, len(shape.Faces))
    sc = sd.scales()
    h.check("one Scale, the end of the timeline", len(sc) == 1 and h.body().Tip is sc[0], sc)
    h.check("timeline shows Scale 1", "Scale 1" in sd.timeline_titles(), sd.timeline_titles())
    h.check("only the scale is shown", sd.shown_features() == [sc[0].Name], sd.shown_features())
    h.shot("5-scaled")


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check(
        "Ctrl+Z takes the scale away in one step",
        sd.close(h.solid_volume(), sd.BOX) and not sd.scales(),
        h.solid_volume(),
    )


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check("Ctrl+Y brings it back", sd.close(h.solid_volume(), 96000.0) and sd.scales())
    h.fit()


def edit_from_timeline():
    sd.timeline_double_click("Scale 1")


def edit_open():
    p = sd.scale_panel()
    h.check("double-click opens the Scale dialog on the step", p is not None and p.editing)
    h.check("factor 2 shown", p is not None and abs(p.factor.value() - 2) < 1e-9)
    h.check("Point Origin shown", p and p.point_box.button.text() == "Origin")
    h.shot("6-edit")
    if p:
        sd.type_into(p.factor.widget, "1.5")


def edit_ok():
    h.task_button("OK")


def after_edit():
    v = h.solid_volume()
    h.check("edited to 1.5: 12000 * 3.375", sd.close(v, 40500.0), v)
    h.check("still one scale", len(sd.scales()) == 1)
    s["v"] = v


def cancel_start():
    h.ribbon("Scale")


def cancel_pick():
    h.fit()
    h.click(V(30, 22.5, 15))  # the top of the scaled part


def cancel_type():
    p = sd.scale_panel()
    h.check("a second scale started on the body", p is not None and p.base is not None)
    if p:
        sd.type_into(p.factor.widget, "3")


def cancel_preview():
    h.check("preview changes the part", not sd.close(h.solid_volume(), s["v"]))
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel leaves the model as it was", sd.close(h.solid_volume(), s["v"]))
    h.check("no new step", len(sd.scales()) == 1, sd.scales())
    h.check("the part is shown", sd.shown_features() == [h.body().Tip.Name], sd.shown_features())


def esc_start():
    h.ribbon("Scale")


def esc_pick():
    h.fit()
    h.click(V(30, 22.5, 15))


def esc_type():
    p = sd.scale_panel()
    if p:
        sd.type_into(p.factor.widget, "3")


def esc_press():
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("Esc leaves the model as it was", sd.close(h.solid_volume(), s["v"]))
    h.check("no new step", len(sd.scales()) == 1, sd.scales())


def pick_body_in_browser():
    Gui.Selection.clearSelection()
    sd.click_browser_row("Body")


def second_scale():
    sel = [x.ObjectName for x in Gui.Selection.getSelectionEx()]
    h.check("the body is selected", sel == ["Body"], sel)
    h.ribbon("Scale")


def second_started():
    p = sd.scale_panel()
    h.check("Scale started with the body", p is not None and p.base is not None)
    h.check("the Point box takes the clicks", p is not None and p.active == "point")
    if p:
        sd.type_into(p.factor.widget, "0.5")


def second_enter():
    p = sd.scale_panel()
    if p:
        sd.press_enter(p.factor.widget)


def after_second():
    h.check("Enter finished the dialog", not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("second scale: 40500 / 8", sd.close(v, 40500.0 / 8.0), v)
    h.check("Scale 2 in the timeline", "Scale 2" in sd.timeline_titles(), sd.timeline_titles())
    h.check("valid at the end", h.body().Shape.isValid())
    h.shot("7-end")


h.run(
    "shell_draft_scale",
    sd.box_steps("Scale")
    + [
        ribbon_scale,
        waiting,
        click_part,
        body_picked,
        drag_arrow,
        dragged,
        click_corner,
        corner_picked,
        half_about_corner,
        non_uniform,
        type_z,
        non_uniform_preview,
        click_corner_again,
        back_to_origin,
        uniform_again,
        zero_refused,
        ok_waits,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit_from_timeline,
        edit_open,
        edit_ok,
        after_edit,
        cancel_start,
        cancel_pick,
        cancel_type,
        cancel_preview,
        after_cancel,
        esc_start,
        esc_pick,
        esc_type,
        esc_press,
        after_esc,
        pick_body_in_browser,
        second_scale,
        second_started,
        second_enter,
        after_second,
    ],
)
