# SPDX-License-Identifier: LGPL-2.1-or-later
"""Box like a Fusion user, only real input.

New design, nothing selected, Box: the origin planes appear; click the XY square; click
the first corner on the origin (it snaps there) and the opposite corner at (40, 20): a
40 x 20 box with a first height of 20 (the shorter side), operation New Body (the first
solid). Type Height 10; drag the blue height arrow up to about 15; type 12; OK.
Undo / redo. Double-click Box 1 in the timeline: Length 50, OK.

Second use, starting from a selection: click the top face, then Box: the face is taken
at once. Corners (10, 5) and (20, 15) on it: a 10 x 10 box on top, Join. Drag the height
arrow down into the part: Fusion switches to Cut by itself; type -5; OK: a 10 x 10 x 5
pocket. Then Box, pick the top face, Cancel: nothing changes; Box, Esc: nothing changes.

Hand-derived volumes: 40*20*20 = 16000, 40*20*10 = 8000, 40*20*12 = 9600,
50*20*12 = 12000, pocket 12000 - 10*10*5 = 11500.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi

V = App.Vector
s = {}


def panel():
    return pi.panel("BoxPanel")


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def bbox():
    return pi.bbox(h.body().Shape)


# -- first box, nothing selected ----------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Boxes")
    h.fit()


def box_nothing_selected():
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    pi.menu("Box")


def waiting_for_plane():
    p = panel()
    h.check("Box dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check("waits for a plane", p.state == "plane" and p.planes is not None, p.state)
    h.check("the Plane box is blue (waiting)", p.plane_field.button.isChecked())
    h.check(
        "Fusion's fields",
        [p.operation.itemText(i) for i in range(p.operation.count())]
        == ["Join", "Cut", "Intersect", "New Body"]
        and p.length.widget.isVisible()
        and p.width.widget.isVisible()
        and p.height.widget.isVisible(),
    )
    h.check("a body to work in", len(pi.bodies()) == 1, pi.bodies())
    h.check("nothing built yet", vol() == 0.0, vol())
    h.shot("1-planes")


def pick_xy():
    h.click(V(15, -15, 0))


def placing():
    p = panel()
    if p is None:
        return
    h.check("XY plane picked", p.ref is not None and p.ref[0].Role == "XY_Plane", p.ref)
    h.check("the Plane box says so", p.plane_field.button.text() == "XY Plane")
    h.check("now placing", p.state == "place" and p.placer is not None, p.state)
    h.check("asks for the first corner", "first corner" in p.info.text(), p.info.text())
    pi.hover(V(5, 5, 0))


def first_corner():
    h.click(V(0, 0, 0))


def second_corner_hover():
    p = panel()
    h.check("one corner placed (snapped to the origin)", p.points == [(0.0, 0.0)], p.points)
    h.check("asks for the opposite corner", "opposite" in p.info.text(), p.info.text())
    pi.hover(V(30, 10, 0))


def rubber_band():
    p = panel()
    h.check(
        "the outline follows the mouse (live length / width)",
        near(p.length.value(), 30.0, 1e-3) and near(p.width.value(), 10.0, 1e-3),
        (p.length.value(), p.width.value()),
    )
    h.check("an outline is drawn", p.placer is not None and p.placer.lines.numVertices.getNum() > 0)
    h.shot("2-rubber-band")


def second_corner():
    h.click(V(40, 20, 0))


second_corner.wait_ms = 1200


def first_box():
    p = panel()
    if p is None:
        return
    h.check("placed", p.state == "ready", p.state)
    h.check(
        "fields 40 x 20 x 20",
        (p.length.value(), p.width.value(), p.height.value()) == (40.0, 20.0, 20.0),
        (p.length.value(), p.width.value(), p.height.value()),
    )
    h.check("first solid: New Body", p.operation.currentText() == "New Body")
    h.check("box 40 x 20 x 20", near(vol(), 16000.0), vol())
    h.check("bbox", bbox() == [0, 0, 0, 40, 20, 20], bbox())
    h.check("blue handles", set(p.handles) == {"height", "length", "width"}, list(p.handles))
    h.check("no error text", p.message.text() == "", p.message.text())
    h.fit()
    h.shot("3-box")
    ui.type_into(p.height.widget, "10")


def typed_10():
    h.check("height 10", near(vol(), 8000.0), vol())
    h.fit()


def drag_height():
    p = panel()
    handle = p.handles.get("height")
    h.check("height handle at 10", handle is not None and near(handle.value(), 10.0), handle)
    if handle is not None:
        pi.drag_handle(handle, 15.0)


drag_height.wait_ms = 1200


def dragged():
    p = panel()
    height = p.height.value()
    h.check("dragging the arrow changed the height", 13.0 < height < 17.0, height)
    h.check("the box follows", near(vol(), 800.0 * height, 1e-4), (vol(), height))
    h.check("still New Body (above the plane)", p.operation.currentText() == "New Body")
    h.shot("4-dragged")
    ui.type_into(p.height.widget, "12")


def ok_first():
    h.check("height 12", near(vol(), 9600.0), vol())
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", pi.no_dialog())
    h.check("kept: 9600", near(vol(), 9600.0), vol())
    boxes = pi.steps_of("AdditiveBox")
    h.check("one AdditiveBox", len(boxes) == 1, [o.Name for o in App.ActiveDocument.Objects])
    s["box"] = boxes[0] if boxes else None
    h.check("Box 1 in the timeline", "Box 1" in ui.timeline_titles(), ui.timeline_titles())
    h.check("nothing selected after OK", not Gui.Selection.getSelectionEx())
    h.check("the part is shown", pi.shown(h.body()))
    h.shot("5-ok")


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("one Undo removes the box (and the body it needed)", vol() == 0.0, vol())


def redo():
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check("Redo brings it back", near(vol(), 9600.0), vol())
    h.fit()


def edit_again():
    h.check(
        "double-click Box 1 in the timeline",
        ui.double_click_timeline("Box 1"),
        ui.timeline_titles(),
    )


def editing():
    p = panel()
    h.check("Box dialog edits it", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "edit shows 40 x 20 x 12",
        (p.length.value(), p.width.value(), p.height.value()) == (40.0, 20.0, 12.0),
        (p.length.value(), p.width.value(), p.height.value()),
    )
    h.check("edit shows the plane", p.plane_field.button.text() == "XY Plane")
    h.check("edit keeps New Body", p.operation.currentText() == "New Body")
    ui.type_into(p.length.widget, "50")


def edit_ok():
    h.check("edit preview: length 50", near(vol(), 12000.0), vol())
    h.task_button("OK")


def after_edit():
    h.check("edit kept", near(vol(), 12000.0), vol())
    h.check("still one box", len(pi.steps_of("AdditiveBox")) == 1)
    h.check("bbox 50 x 20 x 12", bbox() == [0, 0, 0, 50, 20, 12], bbox())
    h.fit()


# -- second use: start with the top face selected ------------------------------------------------
def select_top():
    h.click(V(25, 10, 12))


def box_from_selection():
    h.check("top face selected", bool(Gui.Selection.getSelectionEx()), h.state.get("last_click"))
    pi.menu("Box")


def face_taken():
    p = panel()
    h.check("Box dialog open", p is not None)
    if p is None:
        return
    h.check("the selected face is taken at once", p.state == "place", p.state)
    h.check("Face of ...", p.plane_field.button.text().startswith("Face of"), p.plane_field.button.text())


def corner_a():
    h.click(V(10, 5, 12))


def corner_b():
    h.click(V(20, 15, 12))


corner_b.wait_ms = 1200


def on_top():
    p = panel()
    if p is None:
        return
    h.check("10 x 10 on the face", (p.length.value(), p.width.value()) == (10.0, 10.0))
    h.check("on top of the part: Join", p.operation.currentText() == "Join", p.operation.currentText())
    h.check("joined", near(vol(), 12000.0 + 1000.0), vol())
    h.fit()


def drag_down():
    p = panel()
    handle = p.handles.get("height")
    if handle is not None:
        pi.drag_handle(handle, -4.0)


drag_down.wait_ms = 1500


def cut_by_itself():
    p = panel()
    h.check(
        "dragged into the part: Cut by itself",
        p.operation.currentText() == "Cut",
        (p.operation.currentText(), p.height.value()),
    )
    h.check("height went negative", p.height.value() < 0, p.height.value())
    h.shot("6-cut")
    ui.type_into(p.height.widget, "-5")


def ok_cut():
    h.check("pocket 10 x 10 x 5", near(vol(), 11500.0), vol())
    h.task_button("OK")


def after_cut():
    h.check("kept", near(vol(), 11500.0), vol())
    h.check("a SubtractiveBox", len(pi.steps_of("SubtractiveBox")) == 1)
    h.check("Box 2 in the timeline", "Box 2" in ui.timeline_titles(), ui.timeline_titles())
    s["volume"] = vol()
    s["count"] = len(App.ActiveDocument.Objects)
    h.fit()


# -- Cancel and Esc --------------------------------------------------------------------------------
def box_cancel():
    pi.menu("Box")


def cancel_pick():
    h.click(V(25, 10, 12))


def cancel_corner():
    p = panel()
    h.check("placing on the face", p is not None and p.state == "place")
    h.click(V(5, 5, 12))


def cancel_corner2():
    h.click(V(15, 12, 12))


cancel_corner2.wait_ms = 1200


def cancel_now():
    p = panel()
    h.check("a preview exists", p is not None and p.target is not None)
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel closes the dialog", pi.no_dialog())
    h.check("Cancel leaves the part unchanged", near(vol(), s["volume"]), vol())
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["count"])
    h.check("the part is shown", pi.shown(h.body()))


def box_esc():
    pi.menu("Box")


def esc_now():
    h.check("dialog open", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", pi.no_dialog())
    h.check("Esc changes nothing", near(vol(), s["volume"]), vol())
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["count"])
    h.shot("7-end")


h.run(
    "primitives_box",
    [
        new_design,
        box_nothing_selected,
        waiting_for_plane,
        pick_xy,
        placing,
        first_corner,
        second_corner_hover,
        rubber_band,
        second_corner,
        first_box,
        typed_10,
        drag_height,
        dragged,
        ok_first,
        after_ok,
        undo,
        undone,
        redo,
        redone,
        edit_again,
        editing,
        edit_ok,
        after_edit,
        select_top,
        box_from_selection,
        face_taken,
        corner_a,
        corner_b,
        on_top,
        drag_down,
        cut_by_itself,
        ok_cut,
        after_cut,
        box_cancel,
        cancel_pick,
        cancel_corner,
        cancel_corner2,
        cancel_now,
        cancelled,
        box_esc,
        esc_now,
        after_esc,
    ],
)
