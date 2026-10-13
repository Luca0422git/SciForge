# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sweep like a Fusion user, only real input.

Create Sketch on XY: a circle r2 at the origin, Finish Sketch. Create Sketch on XZ: the
path, a line up 20 (x 0, z 0..20), a tangent bend of radius 10 to (10, 30) and a line on to
(30, 30), Finish Sketch. CREATE > Sweep with nothing selected: the circle (the newest
sketch area) is taken by itself and the Path box waits; click the top line of the path:
Chain Selection takes the whole smooth path (3 curves); the tube appears as a New Body
(the first solid). Type Distance 0.5: half the tube; drag the blue ball back to the end
of the path: the whole tube; OK. Undo / redo. Double-click it in the timeline, Distance
0.25, OK. Sweep again: nothing is taken (the circle is used), Cancel changes nothing; Esc
too. Click Sweep 1 in the timeline, Delete key: both sketches show again.

Hand-derived volumes: path length L = 20 + 10 pi / 2 + 20, tube = pi 2^2 L; a share d of
the path sweeps d of that (the profile sits at the path's start).
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sweep_loft_steps as st
from SciForgeTests.gui import widget_input as w

V = App.Vector
PI = math.pi
LENGTH = 20.0 + 10.0 * PI / 2.0 + 20.0
TUBE = PI * 4.0 * LENGTH
s = {}


def panel():
    return st.panel("sweep")


# -- the sketches ---------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Sweep")
    h.fit()


def create_profile_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    h.check("no pop-up", not h.popups(), h.popups())
    h.click(V(12, -8, 0))


def draw_circle():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None and sk.AttachmentSupport[0][0].Role == "XY_Plane")
    if sk:
        h.draw_circle(sk, 0, 0, 2)
        s["profile"] = sk


def finish_profile():
    h.ribbon("Finish Sketch")


def create_path_sketch():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    h.click(V(12, 0, 8))


def draw_path():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_lines(sk, [(0, 0), (0, 20)])
        st.add_arc(sk, (10, 20), 10, 90, 180)
        st.add_lines(sk, [(10, 30), (30, 30)])
        s["path"] = sk


def finish_path():
    h.ribbon("Finish Sketch")


def after_sketches():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.click_empty()


# -- sweep with nothing selected ------------------------------------------------------------------
def sweep_nothing_selected():
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    st.menu("Sweep")


def dialog_open():
    p = panel()
    h.check("Sweep dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check("the circle is taken as the profile", len(p.profiles) == 1, p.profiles)
    h.check("the Path box waits for a click", p.active == "path" and not p.path, p.active)
    h.check("no solid before the path is picked", h.solid_volume() == 0.0, h.solid_volume())
    h.check(
        "Fusion's fields",
        [p.type.itemText(i) for i in range(p.type.count())]
        == ["Single Path", "Path + Guide Rail", "Path + Guide Surface"]
        and [p.orientation.itemText(i) for i in range(p.orientation.count())]
        == ["Perpendicular", "Parallel"]
        and [p.operation.itemText(i) for i in range(p.operation.count())]
        == ["Join", "Cut", "Intersect", "New Body", "New Component"],
    )
    h.check("Chain Selection on by default", p.chain.isChecked())
    h.check(
        "Distance, Taper, Twist, Orientation shown",
        p.distance.isVisible() and p.taper.widget.isVisible() and p.twist.widget.isVisible(),
    )
    h.check("no Guide Rail box for Single Path", not p.fields["rail"].widget.isVisible())
    h.shot("1-waiting-for-path")


def click_path():
    h.fit()
    h.check("clicked the path's top line", h.click_edge(V(22, 0, 30)))


def tube():
    p = panel()
    if p is None:
        return
    h.check("chain selection took the whole path", len(p.path) == 3, p.path)
    h.check(
        "path box shows it",
        "3 curves" in p.fields["path"].button.text(),
        p.fields["path"].button.text(),
    )
    h.check(
        "first solid: New Body", p.operation.currentText() == "New Body", p.operation.currentText()
    )
    h.check(
        "FreeCAD's own pipe builds it",
        p.target is not None and p.target.TypeId == "PartDesign::AdditivePipe",
        p.target and p.target.TypeId,
    )
    h.check("tube volume pi r^2 L", st.near(h.solid_volume(), TUBE), (h.solid_volume(), TUBE))
    h.check("bbox", st.bbox(h.body().Shape) == [-2, -2, 0, 30, 2, 32], st.bbox(h.body().Shape))
    h.check("the distance ball is shown", "distance" in p.handles, list(p.handles))
    h.check("no error text", p.message.text() == "", p.message.text())
    h.fit()
    h.shot("2-tube")


def type_half():
    ui.type_into(panel().distance, "0.5")


def half():
    p = panel()
    h.check("half the path", st.near(h.solid_volume(), TUBE / 2), (h.solid_volume(), TUBE / 2))
    h.check(
        "SciForge's sweep for a part of the path",
        p.target is not None and p.target.SciForgeType == "Sweep",
        p.target and p.target.TypeId,
    )
    handle = p.handles.get("distance")
    h.check("the ball moved to 0.5", handle is not None and st.near(handle.value(), 0.5))
    h.shot("3-half")


def drag_ball():
    p = panel()
    handle = p.handles.get("distance")
    if handle is not None:
        st.drag_path_handle(handle, 1.0)


drag_ball.wait_ms = 1200


def dragged():
    p = panel()
    d = p.distance.value()
    h.check("dragging the ball to the end set the distance", d > 0.95, d)
    h.check(
        "volume follows the distance",
        st.near(h.solid_volume(), TUBE * d, 1e-5),
        (h.solid_volume(), TUBE * d),
    )


def type_one():
    ui.type_into(panel().distance, "1")


def ok_first():
    h.check("whole tube", st.near(h.solid_volume(), TUBE), h.solid_volume())
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept: the tube", st.near(h.solid_volume(), TUBE), h.solid_volume())
    h.check("the profile sketch is hidden", not s["profile"].ViewObject.Visibility)
    h.check("the path sketch is hidden", not s["path"].ViewObject.Visibility)
    h.check("one sweep", len(st.features("sweep")) == 1, st.features("sweep"))
    h.check("Sweep 1 in the timeline", "Sweep 1" in st.timeline_titles(), st.timeline_titles())
    h.check("nothing selected after OK", not Gui.Selection.getSelectionEx())
    h.check("the body is shown", st.shown(h.body()))
    h.shot("4-ok")


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("Undo removes the sweep (one step)", h.solid_volume() == 0.0, h.solid_volume())


def redo():
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check("Redo brings it back", st.near(h.solid_volume(), TUBE), h.solid_volume())


def edit_again():
    h.check("double-click Sweep 1", st.edit_in_timeline("Sweep 1"))


def editing():
    p = panel()
    h.check("the Sweep dialog edits it", p is not None and p.editing)
    if p is None:
        return
    h.check("edit shows the distance 1", st.near(p.distance.value(), 1.0), p.distance.value())
    h.check("edit shows the path", len(p.path) == 3, p.path)
    h.check("edit shows the profile", len(p.profiles) == 1, p.profiles)
    h.check("edit keeps New Body", p.operation.currentText() == "New Body")
    ui.type_into(p.distance, "0.25")


def edit_ok():
    h.check("edit preview: a quarter", st.near(h.solid_volume(), TUBE / 4), h.solid_volume())
    h.task_button("OK")


def after_edit():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("edit kept", st.near(h.solid_volume(), TUBE / 4), h.solid_volume())
    h.check("still one sweep", len(st.features("sweep")) == 1, st.features("sweep"))
    s["volume"] = h.solid_volume()
    h.fit()


# -- Cancel and Esc ---------------------------------------------------------------------------------
def sweep_again():
    st.menu("Sweep")


def cancel_now():
    p = panel()
    h.check("dialog open", p is not None)
    if p is not None:
        h.check("nothing taken: the circle is used", not p.profiles, p.profiles)
        h.check("the Profile box waits", p.active == "profiles", p.active)
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel closes the dialog", not Gui.Control.activeDialog())
    h.check("Cancel changes nothing", st.near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.check("still one sweep", len(st.features("sweep")) == 1)


def sweep_esc():
    st.menu("Sweep")


def esc_now():
    h.check("dialog open", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("Esc changes nothing", st.near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.check("the body is shown", st.shown(h.body()))


# -- Delete shows both sketches again (Fusion) ----------------------------------------------------
def select_sweep():
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    widget.refresh()
    for button in widget._buttons:
        if button.item.display == "Sweep 1":
            s["button"] = button
            w.click(button)
            return
    h.check("timeline has Sweep 1", False, st.timeline_titles())


def delete_key():
    h.check("the path sketch is hidden (used)", not s["path"].ViewObject.Visibility)
    if "button" in s:
        w.key(s["button"], QtCore.Qt.Key_Delete)


def sweep_deleted():
    titles = st.timeline_titles()
    h.check("Sweep 1 is gone", "Sweep 1" not in titles, titles)
    h.check("the profile sketch shows again", s["profile"].ViewObject.Visibility)
    h.check("the path sketch shows again", s["path"].ViewObject.Visibility)
    h.check("no solid left", h.solid_volume() == 0.0, h.solid_volume())


h.run(
    "sweep_loft_sweep",
    [
        new_design,
        create_profile_sketch,
        pick_xy,
        draw_circle,
        finish_profile,
        create_path_sketch,
        pick_xz,
        draw_path,
        finish_path,
        after_sketches,
        sweep_nothing_selected,
        dialog_open,
        click_path,
        tube,
        type_half,
        half,
        drag_ball,
        dragged,
        type_one,
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
        sweep_again,
        cancel_now,
        cancelled,
        sweep_esc,
        esc_now,
        after_esc,
        select_sweep,
        delete_key,
        sweep_deleted,
    ],
)
