# SPDX-License-Identifier: LGPL-2.1-or-later
"""Navigation bar > Grid and Snaps with real clicks: Layout Grid (a grid on the ground; its
spacing follows the zoom), Layout Grid Lock (the spacing stays while zooming), Grid
Settings (Fixed, 5 mm, 4 subdivisions: the layout grid and a sketch opened afterwards take
it; Adaptive again changes the open sketch at once), Snap to Grid (the Sketch Palette's
Snap goes with it), Incremental Move with Set Increments (5 mm, 30 degrees): Section
Analysis' arrow and angle handle move in steps; without it, freely.

The part: the 40 x 30 x 10 box."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import analysis_steps as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import nav_input as n
from SciForgeTests.gui import widget_input as w

V = App.Vector
st = {}
GS = "Grid and Snaps"


def grid():
    from sciforge import grid_ui

    return grid_ui


def grid_node():
    return grid()._STATE["nodes"].get(App.ActiveDocument.Name)


def dialog(name):
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == name and widget.isVisible():
            return widget
    return Gui.getMainWindow().findChild(QtWidgets.QDialog, name)


# -- the layout grid ----------------------------------------------------------------------------
def grid_on():
    h.check("Layout Grid off at first", n.entry_state(GS, "Layout Grid") == (True, False))
    n.choose(GS, "Layout Grid")


def grid_shown():
    h.check("Layout Grid ticked", n.entry_state(GS, "Layout Grid") == (True, True))
    h.check("the grid is drawn", grid_node() is not None)
    st["step"] = grid().current_step()
    h.check("an adaptive spacing (a round number)", st["step"] in (1, 2, 5, 10, 20, 50), st["step"])
    h.shot("1-grid")
    n.choose("Zoom", "Zoom")


def zoom_in():
    gl = h.gl_widget()
    c = gl.rect().center()
    h.drag(c, QtCore.QPoint(c.x(), c.y() - 330), steps=20)  # up: in, about 4 times
    h.press(QtCore.Qt.Key_Escape)


zoom_in.wait_ms = 900


def finer():
    step = grid().current_step()
    h.check("zoomed in: a finer grid", step < st["step"], (st["step"], step))
    st["fine"] = step
    n.choose(GS, "Layout Grid Lock")


def locked():
    h.check("Layout Grid Lock ticked", n.entry_state(GS, "Layout Grid Lock") == (True, True))
    h.fit()


locked.wait_ms = 900


def lock_holds():
    h.check(
        "locked: the spacing stays after zooming out",
        grid().current_step() == st["fine"],
        (grid().current_step(), st["fine"]),
    )
    n.choose(GS, "Layout Grid Lock")


def unlocked():
    from sciforge import nav_core

    adaptive = nav_core.grid_step(grid().view_height(h.view()))
    h.check(
        "unlocked: it follows the zoom again",
        grid().current_step() == adaptive,
        (grid().current_step(), adaptive),
    )
    n.choose(GS, "Grid Settings")


# -- Grid Settings ------------------------------------------------------------------------------
def settings_open():
    d = dialog("SciForgeGridSettings")
    h.check("Grid Settings opens", d is not None)
    if d is None:
        return
    h.check("Adaptive at first", d.adaptive.isChecked())
    h.check("the spacing box waits while adaptive", not d.major.widget.isEnabled())
    w.click(d.fixed)
    b.type_into(d.major.widget, "5")
    a.type_spin(d.minor, 4)
    st["dialog"] = d


def settings_ok():
    d = st.get("dialog")
    if d is not None:
        buttons = d.findChild(QtWidgets.QDialogButtonBox)
        w.click(buttons.button(QtWidgets.QDialogButtonBox.Ok))


def fixed():
    h.check("Fixed kept", not grid().get("Adaptive"))
    h.check("5 mm", abs(grid().get("MajorSpacing") - 5) < 1e-9, grid().get("MajorSpacing"))
    h.check("4 subdivisions", grid().get("Subdivisions") == 4)
    h.check("the layout grid takes 5 mm", grid().current_step() == 5)
    sub = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Sketcher/General")
    h.check("FreeCAD's sketch grid: 4 subdivisions", sub.GetInt("GridNumberSubdivision") == 4)
    h.click_empty()
    h.ribbon("Create Sketch")


def sketch_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def sketch_grid():
    sk = h.in_sketch()
    h.check("a sketch is open", sk is not None)
    if sk is None:
        return
    vp = sk.ViewObject
    h.check("its grid is fixed", not vp.GridAuto)
    size = float(getattr(vp.GridSize, "Value", vp.GridSize))
    h.check("its spacing is 5 mm", abs(size - 5) < 1e-9, size)
    n.choose(GS, "Grid Settings")


def adaptive_again():
    d = dialog("SciForgeGridSettings")
    h.check("Grid Settings opens in the sketch", d is not None)
    if d is None:
        return
    h.check("it shows Fixed", d.fixed.isChecked())
    w.click(d.adaptive)
    buttons = d.findChild(QtWidgets.QDialogButtonBox)
    w.click(buttons.button(QtWidgets.QDialogButtonBox.Ok))


def sketch_adaptive():
    sk = h.in_sketch()
    h.check("the open sketch's grid is adaptive at once", sk is not None and sk.ViewObject.GridAuto)
    h.check(
        "Snap to Grid ticked (the palette's Snap)",
        n.entry_state(GS, "Snap to Grid") == (True, True),
    )
    n.choose(GS, "Snap to Grid")


def snap_off():
    from sciforge import sketch_mode

    h.check("Snap to Grid unticked", n.entry_state(GS, "Snap to Grid") == (True, False))
    h.check("the Sketch Palette's Snap is off too", not sketch_mode.option("snap"))
    snap = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Sketcher/Snap")
    h.check("FreeCAD snaps no more to the grid", not snap.GetBool("SnapToGrid", True))
    n.choose(GS, "Snap to Grid")


def snap_on():
    from sciforge import sketch_mode

    h.check("Snap to Grid on again", sketch_mode.option("snap"))
    h.ribbon("Finish Sketch")


# -- Incremental Move ---------------------------------------------------------------------------
def increments_open():
    h.check("no sketch open", h.in_sketch() is None)
    n.choose(GS, "Set Increments")


def increments_set():
    d = dialog("SciForgeIncrements")
    h.check("Set Increments opens", d is not None)
    if d is None:
        return
    b.type_into(d.linear.widget, "5")
    b.type_into(d.angular.widget, "30")
    buttons = d.findChild(QtWidgets.QDialogButtonBox)
    w.click(buttons.button(QtWidgets.QDialogButtonBox.Ok))


def increments_kept():
    from sciforge import increments

    h.check("linear 5 mm", abs(increments.linear_step() - 5) < 1e-9, increments.linear_step())
    h.check("angular 30 degrees", abs(increments.angular_step() - 30) < 1e-9)
    n.choose(GS, "Incremental Move")


def section_start():
    from sciforge import increments

    h.check("Incremental Move on", increments.is_on())
    h.check("Incremental Move ticked", n.entry_state(GS, "Incremental Move") == (True, True))
    h.click_empty()
    h.fit()
    from SciForgeTests.gui import sketch_input as si

    si.menu_item("INSPECT", "Section Analysis")


def section_plane():
    h.fit()
    # the box's front face (it lies in XZ): since view-3 the XZ square is 0.6 x the box and,
    # from the iso view, barely shows between the box and the XY / YZ squares
    h.click(V(20, 0, 5))


def section_panel():
    from sciforge import section_ui, taskui

    p = taskui.current()
    return p if isinstance(p, section_ui.SectionPanel) else None


def drag_distance(extra=8.0):
    p = section_panel()
    if p is None or "distance" not in p.handles:
        h.check("the section's arrow", False)
        return
    handle = p.handles["distance"]
    grab = handle.base_point() + handle.direction * (handle.size * 0.55)
    end = handle.base_point() + handle.direction * (handle.size * 0.55 + extra)
    h.drag(h.screen_point(grab), h.screen_point(end), steps=16)


def drag_stepped():
    drag_distance(8.0)


def stepped():
    p = section_panel()
    value = p.options["distance"] if p else None
    h.check("the arrow moved", value is not None and abs(value) > 2, value)
    h.check(
        "in steps of 5 mm",
        value is not None and abs(value / 5.0 - round(value / 5.0)) < 1e-6,
        value,
    )
    st["stepped"] = value
    n.choose(GS, "Incremental Move")


def free_again():
    from sciforge import increments

    h.check("Incremental Move off", not increments.is_on())
    drag_distance(6.3)


def free():
    p = section_panel()
    value = p.options["distance"] if p else None
    h.check(
        "without it the arrow moves freely (not on a 5 mm step)",
        value is not None and abs(value / 5.0 - round(value / 5.0)) > 1e-3,
        value,
    )
    h.task_button("Cancel")


def grid_off():
    n.choose(GS, "Layout Grid")


def gone():
    h.check("Layout Grid off: no grid drawn", grid_node() is None)
    group = App.ParamGet("User parameter:BaseApp/Preferences/Mod/SciForge/Grid")
    h.check("the settings are remembered", group.GetInt("Subdivisions") == 4)


h.run(
    "navbar_grid",
    b.box_steps("Grid")
    + [
        grid_on,
        grid_shown,
        zoom_in,
        finer,
        locked,
        lock_holds,
        unlocked,
        settings_open,
        settings_ok,
        fixed,
        sketch_plane,
        sketch_grid,
        adaptive_again,
        sketch_adaptive,
        snap_off,
        snap_on,
        increments_open,
        increments_set,
        increments_kept,
        section_start,
        section_plane,
        drag_stepped,
        stepped,
        free_again,
        free,
        grid_off,
        gone,
    ],
)
