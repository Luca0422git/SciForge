# SPDX-License-Identifier: LGPL-2.1-or-later
"""Coil like a Fusion user, only real input.

New design, nothing selected, Coil: click the XY square, the centre on the origin, a
point at (10, 0): diameter 20. First values: Revolution and Height, 5 revolutions,
height 20, circular section 2 mm placed Inside the diameter, New Body. Type 4
revolutions; Section Position On Center; Section Square; Rotation -> Counterclockwise;
Type Spiral (flat); Type Height and Pitch; drag the height arrow; type Height 20; OK.
The coil is one step "Coil 1" (no sketch of its own). Undo / redo. Double-click it in the
timeline: Section Size 1.5, OK.
Second use: a Box 40 x 40 x 30 next to it, then Coil from its selected top face, centre
(60, 0), diameter 20, height -20: running down into the block, Fusion switches to Cut by
itself (the coil's turns are cut into the block). Cancel and Esc change nothing.

Hand-derived volumes (Pappus: section area x the path its centre travels round the axis,
FreeCAD's coil sweeps the upright section, so rising adds nothing):
  circle d2, inside D20 (centre at r9), 5 turns:  pi * 1 * 2 pi 9 * 5 = 90 pi^2
  4 turns: 72 pi^2; On Center (r10): 80 pi^2
  square (circumscribed d2: area 2), r10, 4 turns: 2 * 2 pi 10 * 4 = 160 pi
  spiral, pitch 5, 4 turns: mean radius 10 + 5*4/2 = 20: 2 * 2 pi 20 * 4 = 320 pi
  square d1.5 (area 1.125), r10, 4 turns: 1.125 * 2 pi 10 * 4 = 90 pi
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi

V = App.Vector
PI = math.pi
s = {}


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def panel():
    return pi.panel("CoilPanel")


def coil_steps():
    return [o for o in App.ActiveDocument.Objects if getattr(o, "SciForgeType", "") == "Coil"]


# -- first coil -----------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Coils")
    h.fit()


def coil_start():
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    pi.menu("Coil")


def coil_waits():
    p = panel()
    h.check("Coil dialog open, waiting for a plane", p is not None and p.state == "plane")
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check(
        "Fusion's types",
        [p.type.itemText(i) for i in range(p.type.count())]
        == ["Revolution and Height", "Revolution and Pitch", "Height and Pitch", "Spiral"],
    )
    h.check(
        "Fusion's sections",
        [p.section.itemText(i) for i in range(p.section.count())]
        == ["Circular", "Square", "Triangular (External)", "Triangular (Internal)"],
    )
    h.check(
        "Fusion's section positions",
        [p.section_position.itemText(i) for i in range(3)] == ["Inside", "On Center", "Outside"],
    )


def coil_xy():
    h.click(V(15, -15, 0))


def coil_centre():
    p = panel()
    h.check("placing", p is not None and p.state == "place", p and p.state)
    h.click(V(0, 0, 0))


def coil_circle():
    h.click(V(10, 0, 0))


coil_circle.wait_ms = 2500


def coil_first():
    p = panel()
    if p is None:
        return
    h.check(
        "first values",
        (
            p.diameter.value(),
            p.revolutions.value(),
            p.height.value(),
            p.section_size.value(),
            p.section_position.currentText(),
            p.rotation.text(),
        )
        == (20.0, 5.0, 20.0, 2.0, "Inside", "Clockwise"),
        (
            p.diameter.value(),
            p.revolutions.value(),
            p.height.value(),
            p.section_size.value(),
            p.section_position.currentText(),
            p.rotation.text(),
        ),
    )
    h.check("first solid: New Body", p.operation.currentText() == "New Body")
    h.check("coil 90 pi^2", near(vol(), 90.0 * PI * PI, 1e-5), vol())
    h.check("one step, no sketch", len(coil_steps()) == 1 and not pi.steps_of("Sketcher"))
    h.check("handles", set(p.handles) == {"diameter", "height"}, list(p.handles))
    h.check("pitch hidden for this type", not p.pitch.widget.isVisible())
    h.fit()
    h.shot("1-coil")
    ui.type_into(p.revolutions.widget, "4")


coil_first.wait_ms = 1500


def four_turns():
    h.check("4 turns: 72 pi^2", near(vol(), 72.0 * PI * PI, 1e-5), vol())
    h.check("On Center", ui.choose(panel().section_position, "On Center"))


four_turns.wait_ms = 1500


def on_center():
    h.check("On Center: 80 pi^2", near(vol(), 80.0 * PI * PI, 1e-5), vol())
    h.check("Square", ui.choose(panel().section, "Square"))


on_center.wait_ms = 1500


def square():
    h.check("square section: 160 pi", near(vol(), 160.0 * PI, 1e-5), vol())
    h.shot("2-square")
    ui.click(panel().rotation)


square.wait_ms = 1500


def counterclockwise():
    p = panel()
    h.check("Rotation says Counterclockwise", p.rotation.text() == "Counterclockwise")
    h.check("left-handed now", p.target is not None and p.target.LeftHanded)
    h.check("same volume", near(vol(), 160.0 * PI, 1e-5), vol())
    h.check("Spiral", ui.choose(p.type, "Spiral"))


counterclockwise.wait_ms = 1500


def spiral():
    p = panel()
    h.check(
        "Spiral takes revolutions and pitch",
        p.pitch.widget.isVisible() and not p.height.widget.isVisible(),
    )
    h.check("pitch 5 (the coil's own)", near(p.pitch.value(), 5.0), p.pitch.value())
    h.check("flat spiral: 320 pi", near(vol(), 320.0 * PI, 1e-4), vol())
    h.check("no height handle for a spiral", set(p.handles) == {"diameter"}, list(p.handles))
    h.fit()
    h.shot("3-spiral")
    h.check("Height and Pitch", ui.choose(p.type, "Height and Pitch"))


spiral.wait_ms = 2500


def height_pitch():
    p = panel()
    h.check("back to a rising coil: 160 pi", near(vol(), 160.0 * PI, 1e-5), vol())
    h.check("height shown again", p.height.widget.isVisible())
    h.fit()


height_pitch.wait_ms = 2000


def drag_height():
    p = panel()
    handle = p.handles.get("height")
    h.check("height handle", handle is not None, list(p.handles))
    if handle is not None:
        pi.drag_handle(handle, 26.0)


drag_height.wait_ms = 2500


def dragged():
    p = panel()
    height = p.height.value()
    h.check("dragging changed the height", 22.0 < height < 30.0, height)
    h.check(
        "turns follow (height / pitch)",
        near(vol(), 2 * 2 * PI * 10 * height / 5.0, 1e-4),
        (vol(), height),
    )
    ui.type_into(p.height.widget, "20")


dragged.wait_ms = 1500


def coil_ok():
    h.check("160 pi", near(vol(), 160.0 * PI, 1e-5), vol())
    h.task_button("OK")


coil_ok.wait_ms = 1500


def coil_kept():
    h.check("dialog closed", pi.no_dialog())
    h.check("kept", near(vol(), 160.0 * PI, 1e-5), vol())
    h.check("Coil 1 in the timeline", "Coil 1" in ui.timeline_titles(), ui.timeline_titles())
    h.check(
        "its section is hidden and no step",
        all(
            not o.ViewObject.Visibility
            for o in App.ActiveDocument.Objects
            if getattr(o, "SciForgeRole", "") == "CoilSection"
        ),
    )
    h.check("Undo button", ui.quick_access("Undo"))


def coil_undone():
    h.check("Undo removes it", vol() == 0.0, vol())
    h.check("Redo button", ui.quick_access("Redo"))


coil_undone.wait_ms = 1500


def coil_redone():
    h.check("Redo brings it back", near(vol(), 160.0 * PI, 1e-5), vol())
    h.fit()
    h.check("double-click Coil 1", ui.double_click_timeline("Coil 1"), ui.timeline_titles())


coil_redone.wait_ms = 1500


def coil_editing():
    p = panel()
    h.check("editing the coil", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "edit shows it as left",
        (p.type.currentText(), p.section.currentText(), p.rotation.text(), p.height.value())
        == ("Height and Pitch", "Square", "Counterclockwise", 20.0),
        (p.type.currentText(), p.section.currentText(), p.rotation.text(), p.height.value()),
    )
    ui.type_into(p.section_size.widget, "1.5")


def coil_edit_ok():
    h.check("section 1.5: 90 pi", near(vol(), 90.0 * PI, 1e-5), vol())
    h.task_button("OK")


coil_edit_ok.wait_ms = 1500


def coil_edited():
    h.check("edit kept", near(vol(), 90.0 * PI, 1e-5), vol())
    h.check("still one coil", len(coil_steps()) == 1)
    s["coil"] = vol()
    h.fit()


# -- second use: a coil cut into a block -----------------------------------------------------------
def box_start():
    h.click_empty()
    pi.menu("Box")


def box_plane():
    h.click(V(10, -12, 0))


def box_corner():
    p = pi.panel("BoxPanel")
    h.check("box placing", p is not None and p.state == "place", p and p.state)
    h.click(V(40, -20, 0))


def box_corner2():
    h.click(V(80, 20, 0))


box_corner2.wait_ms = 1200


def box_height():
    p = pi.panel("BoxPanel")
    if p is None:
        return
    ui.type_into(p.height.widget, "30")


def box_ok():
    h.task_button("OK")


def box_done():
    h.check("block 40 x 40 x 30", near(vol() - s["coil"], 48000.0), vol() - s["coil"])
    s["before"] = vol()
    h.fit()


def select_block_top():
    h.click(V(70, 10, 30))


def coil2_start():
    h.check("block top selected", bool(Gui.Selection.getSelectionEx()))
    pi.menu("Coil")


def coil2_centre():
    p = panel()
    h.check("the face is taken at once", p is not None and p.state == "place", p and p.state)
    h.click(V(60, 0, 30))


def coil2_circle():
    h.click(V(70, 0, 30))


coil2_circle.wait_ms = 2500


def coil2_down():
    p = panel()
    if p is None:
        return
    h.check("diameter 20", near(p.diameter.value(), 20.0), p.diameter.value())
    ui.type_into(p.height.widget, "-20")


coil2_down.wait_ms = 2500


def coil2_cut():
    p = panel()
    h.check(
        "running into the block: Cut by itself",
        p.operation.currentText() == "Cut",
        p.operation.currentText(),
    )
    removed = s["before"] - vol()
    whole = 90.0 * PI * PI  # circle d2 inside D20, 5 turns
    h.check("nearly the whole coil is cut out", 0.93 * whole < removed < whole, (removed, whole))
    h.shot("4-cut-coil")
    h.task_button("OK")


coil2_cut.wait_ms = 2500


def coil2_kept():
    h.check("a SubtractiveHelix", len(pi.steps_of("SubtractiveHelix")) == 1)
    h.check("Coil 2 in the timeline", "Coil 2" in ui.timeline_titles(), ui.timeline_titles())
    s["volume"] = vol()
    s["count"] = len(App.ActiveDocument.Objects)
    h.fit()


# -- Cancel and Esc --------------------------------------------------------------------------------
def cancel_start():
    h.click_empty()
    pi.menu("Coil")


def cancel_plane():
    h.click(V(70, 10, 30))


def cancel_centre():
    h.click(V(60, 0, 30))


def cancel_circle():
    h.click(V(65, 0, 30))


cancel_circle.wait_ms = 2500


def cancel_now():
    p = panel()
    h.check("a coil preview", p is not None and p.target is not None)
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel closes", pi.no_dialog())
    h.check("Cancel changes nothing", near(vol(), s["volume"]), vol())
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["count"])
    pi.menu("Coil")


def esc_now():
    h.check("Coil dialog open", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes", pi.no_dialog())
    h.check("Esc changes nothing", near(vol(), s["volume"]), vol())
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["count"])
    h.shot("5-end")


h.run(
    "primitives_coil",
    [
        new_design,
        coil_start,
        coil_waits,
        coil_xy,
        coil_centre,
        coil_circle,
        coil_first,
        four_turns,
        on_center,
        square,
        counterclockwise,
        spiral,
        height_pitch,
        drag_height,
        dragged,
        coil_ok,
        coil_kept,
        coil_undone,
        coil_redone,
        coil_editing,
        coil_edit_ok,
        coil_edited,
        box_start,
        box_plane,
        box_corner,
        box_corner2,
        box_height,
        box_ok,
        box_done,
        select_block_top,
        coil2_start,
        coil2_centre,
        coil2_circle,
        coil2_down,
        coil2_cut,
        coil2_kept,
        cancel_start,
        cancel_plane,
        cancel_centre,
        cancel_circle,
        cancel_now,
        cancelled,
        esc_now,
        after_esc,
    ],
)
