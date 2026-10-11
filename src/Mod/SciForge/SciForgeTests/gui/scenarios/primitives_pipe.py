# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pipe like a Fusion user, only real input (the path sketch's curves are added like
harness.draw_rectangle does; sketching itself has its own scenarios).

Create Sketch on XY: a line (0,0)-(20,0), a tangent arc r10 to (30,10), a line up to
(30,30); Finish Sketch. Pipe with nothing selected: click the first line; Chain
Selection (on) takes the arc and the second line too. Type Section Size 2; drag the
Distance ball half way along the path; type 0.5; Chain Selection off (only the clicked
line); on again; Square; Hollow with a 0.25 wall (Circular again); Distance 1; OK.
The sketch is hidden (it is used). Undo / redo. Double-click Pipe 1: Triangular, not
hollow, OK.
Second use from a selection: a Box 40 x 20 x 10 next to it; click its top front edge,
then Pipe: the edge is taken at once, the pipe runs along it; Cut takes the quarter
inside the box away; OK. Cancel and Esc change nothing.

Hand-derived volumes (the section square to the path, which bends gently, so Pappus:
area x length):
  path L = 20 + 10 pi / 2 + 20 = 40 + 5 pi
  circle d2: pi L; half way: pi L / 2; the first line alone, half: pi 10
  square (circumscribed d2): area 2: 2 L / 2 = L
  hollow circle d2, wall 0.25: pi (1 - 0.75^2) = 0.4375 pi, x L
  triangle (circumscribed d2): area 3 sqrt(3) / 4: x L
  box 40 x 20 x 10 = 8000, minus a quarter of a d2 pipe along a 40 mm edge: 10 pi
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi

V = App.Vector
PI = math.pi
L = 40.0 + 5.0 * PI
TRI = 3.0 * math.sqrt(3.0) / 4.0
s = {}


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def panel():
    return pi.pipe_panel()


def pipes():
    return [o for o in App.ActiveDocument.Objects if getattr(o, "SciForgeType", "") == "Pipe"]


# -- the path sketch -------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Pipes")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(15, -15, 0))


def draw_path():
    sk = h.in_sketch()
    h.check("sketch open", sk is not None)
    if sk is None:
        return
    sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(20, 0, 0)))
    sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(20, 10, 0), V(0, 0, 1), 10), -PI / 2, 0))
    sk.addGeometry(Part.LineSegment(V(30, 10, 0), V(30, 30, 0)))
    sk.addConstraint(Sketcher.Constraint("Tangent", 0, 2, 1, 1))
    sk.addConstraint(Sketcher.Constraint("Tangent", 1, 2, 2, 1))
    App.ActiveDocument.recompute()
    s["sketch"] = sk


def finish_sketch():
    h.ribbon("Finish Sketch")


def after_finish():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()


# -- Pipe, nothing selected --------------------------------------------------------------------------
def pipe_start():
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    pi.menu("Pipe")


def pipe_waits():
    p = panel()
    h.check("Pipe dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check("waits for the path", not p.path and p.path_field.button.isChecked())
    h.check(
        "Fusion's fields",
        [p.section.itemText(i) for i in range(p.section.count())]
        == ["Circular", "Square", "Triangular"]
        and p.chain.isChecked()
        and near(p.distance.value(), 1.0)
        and not p.thickness.widget.isVisible(),
    )
    h.shot("1-waiting")


def click_line():
    h.click_edge(V(10, 0, 0))


click_line.wait_ms = 2000


def chained():
    p = panel()
    if p is None:
        return
    h.check("the chain: line, arc, line", len(p.path) == 3, p.path)
    h.check("path box says 3 selected", p.path_field.button.text() == "3 selected")
    h.check("a pipe preview", p.target is not None and vol() > 0, vol())
    h.check("first solid: New Body", p.operation.currentText() == "New Body")
    h.check("handles", set(p.handles) == {"distance", "section_size"}, list(p.handles))
    ui.type_into(p.size.widget, "2")


chained.wait_ms = 1500


def size_2():
    h.check("d2 along the path: pi L", near(vol(), PI * L, 1e-5), vol())
    h.fit()
    h.shot("2-pipe")


def drag_distance():
    p = panel()
    handle = p.handles.get("distance")
    h.check("the distance ball at the end", handle is not None and near(handle.value(), 1.0))
    if handle is not None:
        pi.drag_handle(handle, 0.5)


drag_distance.wait_ms = 2000


def distance_dragged():
    p = panel()
    d = p.distance.value()
    h.check("dragging along the path changed the distance", 0.35 < d < 0.65, d)
    h.check("the pipe follows", near(vol(), PI * L * d, 2e-3), (vol(), d))
    ui.type_into(p.distance, "0.5")


distance_dragged.wait_ms = 1500


def half():
    h.check("half way: pi L / 2", near(vol(), PI * L / 2.0, 1e-5), vol())
    pi.tick(panel().chain)


half.wait_ms = 1500


def no_chain():
    p = panel()
    h.check("Chain Selection off: only the clicked line", len(p.path) == 1, p.path)
    h.check("half of the line: 10 pi", near(vol(), 10.0 * PI, 1e-5), vol())
    pi.tick(p.chain)


no_chain.wait_ms = 1500


def chain_again():
    p = panel()
    h.check("chain again", len(p.path) == 3, p.path)
    h.check("Square", ui.choose(p.section, "Square"))


chain_again.wait_ms = 1500


def square():
    h.check("square: L", near(vol(), L, 1e-5), vol())
    h.check("Circular", ui.choose(panel().section, "Circular"))


square.wait_ms = 1500


def hollow():
    pi.tick(panel().hollow)


hollow.wait_ms = 1500


def hollow_on():
    p = panel()
    h.check(
        "Hollow shows Section Thickness", p.hollow.isChecked() and p.thickness.widget.isVisible()
    )
    ui.type_into(p.thickness.widget, "0.25")


hollow_on.wait_ms = 1500


def wall():
    p = panel()
    h.check("hollow half: 0.4375 pi L / 2", near(vol(), 0.4375 * PI * L / 2.0, 1e-5), vol())
    ui.type_into(p.distance, "1")


wall.wait_ms = 1500


def full():
    h.check("hollow, whole path", near(vol(), 0.4375 * PI * L, 1e-5), vol())
    h.shot("3-hollow")
    h.task_button("OK")


full.wait_ms = 1500


def pipe_kept():
    h.check("dialog closed", pi.no_dialog())
    h.check("kept", near(vol(), 0.4375 * PI * L, 1e-5), vol())
    h.check("one pipe step", len(pipes()) == 1, pipes())
    h.check("Pipe 1 in the timeline", "Pipe 1" in ui.timeline_titles(), ui.timeline_titles())
    h.check("the path sketch is hidden (used)", not s["sketch"].ViewObject.Visibility)
    h.check("Undo button", ui.quick_access("Undo"))


def pipe_undone():
    h.check("Undo removes it", vol() == 0.0, vol())
    h.check("Redo button", ui.quick_access("Redo"))


pipe_undone.wait_ms = 1500


def pipe_redone():
    h.check("Redo brings it back", near(vol(), 0.4375 * PI * L, 1e-5), vol())
    h.fit()
    h.check("double-click Pipe 1", ui.double_click_timeline("Pipe 1"), ui.timeline_titles())


pipe_redone.wait_ms = 1500


def pipe_editing():
    p = panel()
    h.check("editing the pipe", p is not None and p.editing)
    if p is None:
        return
    h.check("edit shows the path", len(p.path) == 3)
    h.check("edit shows hollow 0.25", p.hollow.isChecked() and near(p.thickness.value(), 0.25))
    h.check("the sketch shows while editing", s["sketch"].ViewObject.Visibility)
    h.check("Triangular", ui.choose(p.section, "Triangular"))


def pipe_not_hollow():
    pi.tick(panel().hollow)


pipe_not_hollow.wait_ms = 1500


def pipe_edit_ok():
    h.check("triangle along the path", near(vol(), TRI * L, 1e-5), vol())
    h.task_button("OK")


pipe_edit_ok.wait_ms = 1500


def pipe_edited():
    h.check("edit kept", near(vol(), TRI * L, 1e-5), vol())
    h.check("the sketch hidden again", not s["sketch"].ViewObject.Visibility)
    s["pipe"] = vol()
    h.fit()


# -- second use: along a model edge, from a selection --------------------------------------------------
def box_start():
    h.click_empty()
    pi.menu("Box")


def box_plane():
    h.click(V(5, -15, 0))


def box_corner():
    p = pi.panel("BoxPanel")
    h.check("box placing", p is not None and p.state == "place", p and p.state)
    h.click(V(40, -40, 0))


def box_corner2():
    h.click(V(80, -20, 0))


box_corner2.wait_ms = 1200


def box_height():
    ui.type_into(pi.panel("BoxPanel").height.widget, "10")


def box_ok():
    h.task_button("OK")


def box_done():
    h.check("box 40 x 20 x 10", near(vol() - s["pipe"], 8000.0), vol() - s["pipe"])
    h.fit()


def select_edge():
    h.click_edge(V(60, -40, 10))


def pipe2_start():
    h.check("the edge is selected", bool(Gui.Selection.getSelectionEx()), h.state.get("last_click"))
    pi.menu("Pipe")


pipe2_start.wait_ms = 2000


def pipe2_taken():
    p = panel()
    h.check("the selected edge is taken at once", p is not None and len(p.path) == 1, p and p.path)
    if p is None:
        return
    h.check("section d2 (a twentieth of 40)", near(p.size.value(), 2.0), p.size.value())
    h.check("mostly outside: Join", p.operation.currentText() == "Join", p.operation.currentText())
    h.check("joined: + 3/4 of the pipe", near(vol() - s["pipe"], 8000.0 + 30.0 * PI, 1e-5))
    h.check("Cut", ui.choose(p.operation, "Cut"))


pipe2_taken.wait_ms = 1500


def pipe2_cut():
    h.check("Cut: the quarter inside is gone", near(vol() - s["pipe"], 8000.0 - 10.0 * PI, 1e-5))
    h.shot("4-edge-cut")
    h.task_button("OK")


pipe2_cut.wait_ms = 1500


def pipe2_kept():
    h.check("a SubtractivePipe", len(pi.steps_of("SubtractivePipe")) == 1)
    h.check("Pipe 2 in the timeline", "Pipe 2" in ui.timeline_titles(), ui.timeline_titles())
    s["volume"] = vol()
    s["count"] = len(App.ActiveDocument.Objects)


# -- Cancel and Esc ------------------------------------------------------------------------------------------
def cancel_start():
    h.click_empty()
    pi.menu("Pipe")


def cancel_pick():
    h.click_edge(V(80, -30, 10))


cancel_pick.wait_ms = 1500


def cancel_now():
    p = panel()
    h.check("a pipe preview", p is not None and p.target is not None, p and p.path)
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel closes", pi.no_dialog())
    h.check("Cancel changes nothing", near(vol(), s["volume"]), vol())
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["count"])
    pi.menu("Pipe")


def esc_now():
    h.check("Pipe dialog open", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes", pi.no_dialog())
    h.check("Esc changes nothing", near(vol(), s["volume"]), vol())
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["count"])
    h.shot("5-end")


h.run(
    "primitives_pipe",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_path,
        finish_sketch,
        after_finish,
        pipe_start,
        pipe_waits,
        click_line,
        chained,
        size_2,
        drag_distance,
        distance_dragged,
        half,
        no_chain,
        chain_again,
        square,
        hollow,
        hollow_on,
        wall,
        full,
        pipe_kept,
        pipe_undone,
        pipe_redone,
        pipe_editing,
        pipe_not_hollow,
        pipe_edit_ok,
        pipe_edited,
        box_start,
        box_plane,
        box_corner,
        box_corner2,
        box_height,
        box_ok,
        box_done,
        select_edge,
        pipe2_start,
        pipe2_taken,
        pipe2_cut,
        pipe2_kept,
        cancel_start,
        cancel_pick,
        cancel_now,
        cancelled,
        esc_now,
        after_esc,
    ],
)
