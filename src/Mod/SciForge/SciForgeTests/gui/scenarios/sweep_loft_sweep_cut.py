# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sweep a cut along a path picked before the command, then sweep a face of the part with a
taper. Only real input.

Box: a 40 x 20 rectangle (x -20..20, y -10..10) on XY, Extrude 10. Sketch on YZ: a circle
r3 at (y 0, z 8). Sketch on XZ: a line from x -25 to x 25 at z 8, which passes through the
circle: the profile sits in the middle of the path. Click the line, then CREATE > Sweep:
the path is taken from the selection, the circle by itself, and the sweep goes both ways
along the whole path. It runs mostly inside the box, so Fusion's Cut is chosen by itself: a
groove along the top. OK. Edit it from the timeline: Distance One 0.5 (x 0..12.5) and
Distance Two 0.25 (x -6.25..0), OK. Undo / redo.

Second use: a sketch on XZ with a line from (20, 5) to (30, 5). Sweep: click the end face of
the box (x 20) as the profile, then the line: Join, the box grows by 10. Taper 5 degrees:
the end grows like a pyramid frustum. OK.

Hand-derived: circle r3 whose centre is 2 below the top face: the part above the top is the
segment 9 acos(2/3) - 2 sqrt(5); inside the box the groove's section is A = 9 pi - segment;
groove volume = A * length inside the box. Taper: the end face 20 x 10 is scaled about its
centre by k = 1 + 10 tan(5 deg) / 5 (its nearest side is 5 from the path), so the added
volume is 10 * 200 * (1 + k + k^2) / 3.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
PI = math.pi
BOX = 40.0 * 20.0 * 10.0
SEGMENT = 9.0 * math.acos(2.0 / 3.0) - 2.0 * math.sqrt(5.0)
SECTION = 9.0 * PI - SEGMENT
GROOVE = SECTION * 40.0
GROOVE_PART = SECTION * (12.5 + 6.25)
K = 1.0 + 10.0 * math.tan(math.radians(5.0)) / 5.0
TAPERED = 10.0 * 200.0 * (1.0 + K + K * K) / 3.0
s = {}


def panel():
    return st.panel("sweep")


# -- the box -----------------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SweepCut")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def draw_box():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, -20, -10, 20, 10)


def finish_box_sketch():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def extrude_distance():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last if hasattr(extrude_ui.ExtrudePanel, "last") else None
    field = getattr(getattr(p, "distance", None), "widget", None) if p is not None else None
    if field is None:
        from sciforge import taskui

        p = taskui.current()
        field = getattr(getattr(p, "distance", None), "widget", None)
    h.check("extrude dialog has a distance box", field is not None)
    if field is not None:
        ui.type_into(field, "10")


def extrude_ok():
    h.task_button("OK")


def box_made():
    h.check("box 40 x 20 x 10", st.near(h.solid_volume(), BOX), h.solid_volume())
    h.fit()
    h.ribbon("Create Sketch")


# -- the profile on YZ and the path on XZ -------------------------------------------------------------
def pick_yz():
    pl.click_square("YZ_Plane")  # where the square shows (was 0, 12, 22)


def draw_profile():
    sk = h.in_sketch()
    h.check("sketch open on YZ", sk is not None and sk.AttachmentSupport[0][0].Role == "YZ_Plane")
    if sk:
        h.draw_circle(sk, 0, 8, 3)
        s["profile"] = sk


def finish_profile():
    h.ribbon("Finish Sketch")


def path_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    pl.click_square("XZ_Plane")  # where the square shows (was 24, 0, 24)


def draw_path():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_lines(sk, [(-25, 8), (25, 8)])
        s["path"] = sk


def finish_path():
    h.ribbon("Finish Sketch")


def select_path_first():
    h.fit()
    h.check("clicked the path where it sticks out", h.click_edge(V(-23, 0, 8)))


def path_selected():
    sel = [(x.Object.Name, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]
    h.check(
        "the line is selected",
        len(sel) == 1 and sel[0][0] == s["path"].Name and sel[0][1] == ["Edge1"],
        sel,
    )
    st.menu("Sweep")


def preview_cut():
    p = panel()
    h.check("Sweep dialog open", p is not None)
    if p is None:
        return
    h.check("the selected line is the path", len(p.path) == 1, p.path)
    h.check("the circle is the profile", len(p.profiles) == 1, p.profiles)
    h.check("sweeping into the box: Cut by itself", p.operation.currentText() == "Cut")
    h.check(
        "the profile sits inside the path: Distance One and Two",
        p.distance2.isVisible() and p.distance_label.text() == "Distance One",
        p.distance_label.text(),
    )
    h.check("two balls, one per side", set(p.handles) == {"distance", "distance2"}, list(p.handles))
    h.check(
        "FreeCAD's own subtractive pipe",
        p.target is not None and p.target.TypeId == "PartDesign::SubtractivePipe",
        p.target and p.target.TypeId,
    )
    h.check("groove cut", st.near(h.solid_volume(), BOX - GROOVE), (h.solid_volume(), BOX - GROOVE))
    h.fit()
    h.shot("1-groove")
    h.task_button("OK")


def grooved():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("groove kept", st.near(h.solid_volume(), BOX - GROOVE), h.solid_volume())
    h.check("Sweep 1 in the timeline", "Sweep 1" in st.timeline_titles(), st.timeline_titles())
    h.check("the box is shown", st.shown(h.body()))


def edit_groove():
    h.check("double-click Sweep 1", st.edit_in_timeline("Sweep 1"))


def edit_one():
    p = panel()
    h.check("editing", p is not None and p.editing)
    if p is None:
        return
    h.check("edit keeps Cut", p.operation.currentText() == "Cut", p.operation.currentText())
    ui.type_into(p.distance, "0.5")


def edit_two():
    ui.type_into(panel().distance2, "0.25")


def edit_ok():
    p = panel()
    h.check(
        "a shorter groove",
        st.near(h.solid_volume(), BOX - GROOVE_PART),
        (h.solid_volume(), BOX - GROOVE_PART),
    )
    shape = h.body().Shape
    h.check("side one is cut up to x 12.5", not shape.isInside(V(10, 0, 7), 1e-6, True))
    h.check("side two ends at x -6.25", shape.isInside(V(-10, 0, 7), 1e-6, True))
    h.shot("2-shorter")
    if p is not None:
        h.task_button("OK")


def edited():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("edit kept", st.near(h.solid_volume(), BOX - GROOVE_PART), h.solid_volume())
    h.check("still one sweep", len(st.features("sweep")) == 1, st.features("sweep"))


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check(
        "Undo: the long groove again", st.near(h.solid_volume(), BOX - GROOVE), h.solid_volume()
    )


def redo():
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check("Redo: the short one", st.near(h.solid_volume(), BOX - GROOVE_PART), h.solid_volume())
    s["volume"] = h.solid_volume()
    h.fit()
    h.ribbon("Create Sketch")


# -- second use: a face of the part along a line, with a taper ----------------------------------
def pick_xz_2():
    pl.click_square("XZ_Plane")  # where the square shows (was 24, 0, 24)


def draw_line():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None)
    if sk:
        st.add_lines(sk, [(20, 5), (30, 5)])
        s["line"] = sk


def finish_line():
    h.ribbon("Finish Sketch")


def sweep_face():
    h.fit()
    h.click_empty()
    st.menu("Sweep")


def click_end_face():
    p = panel()
    h.check("dialog open, nothing taken", p is not None and not p.profiles, p and p.profiles)
    h.fit()
    h.click(V(20, -6, 2))


def face_taken():
    p = panel()
    h.check("the end face is the profile", p is not None and len(p.profiles) == 1, p and p.profiles)
    h.check("the Path box waits", p is not None and p.active == "path", p and p.active)
    h.check("clicked the line", h.click_edge(V(28, 0, 5)))


def joined():
    p = panel()
    if p is None:
        return
    h.check(
        "Join (out of the part)", p.operation.currentText() == "Join", p.operation.currentText()
    )
    h.check(
        "the box grows by 20 x 10 x 10",
        st.near(h.solid_volume(), s["volume"] + 2000.0),
        (h.solid_volume(), s["volume"] + 2000.0),
    )
    ui.type_into(p.taper.widget, "5")


def tapered():
    p = panel()
    want = s["volume"] + TAPERED
    h.check("tapered end: a frustum", st.near(h.solid_volume(), want), (h.solid_volume(), want))
    h.check(
        "a taper needs SciForge's sweep",
        p is not None and p.target is not None and p.target.SciForgeType == "Sweep",
    )
    bb = st.bbox(h.body().Shape)
    h.check("the end is wider", bb[1] < -10.0 and bb[4] > 10.0 and st.near(bb[3], 30.0), bb)
    h.shot("3-tapered")
    h.task_button("OK")


def taper_kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(h.solid_volume(), s["volume"] + TAPERED), h.solid_volume())
    h.check("two sweeps", len(st.features("sweep")) == 2, st.features("sweep"))
    h.check("Sweep 2 in the timeline", "Sweep 2" in st.timeline_titles(), st.timeline_titles())
    h.check("the line sketch is hidden", not s["line"].ViewObject.Visibility)


h.run(
    "sweep_loft_sweep_cut",
    [
        new_design,
        pick_xy,
        draw_box,
        finish_box_sketch,
        extrude,
        extrude_distance,
        extrude_ok,
        box_made,
        pick_yz,
        draw_profile,
        finish_profile,
        path_sketch,
        pick_xz,
        draw_path,
        finish_path,
        select_path_first,
        path_selected,
        preview_cut,
        grooved,
        edit_groove,
        edit_one,
        edit_two,
        edit_ok,
        edited,
        undo,
        undone,
        redo,
        redone,
        pick_xz_2,
        draw_line,
        finish_line,
        sweep_face,
        click_end_face,
        face_taken,
        joined,
        tapered,
        taper_kept,
    ],
)
