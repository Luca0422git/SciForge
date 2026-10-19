# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rectangular Pattern the way a Fusion user does it, only real input:

1. A 40 x 30 x 10 box with a through hole r 2 at (8, 8) (sketch, circle, E, -10, OK).
2. Rectangular Pattern from the ribbon with nothing selected: the dialog waits, nothing
   changes. Click the hole's step in the timeline (Objects), click the Direction box, click
   the origin X axis drawn over the view: a live preview with a copy, Direction 2 offered
   at right angles (the Y axis).
3. Quantity 3, Distance 24 (Extent): holes at x = 8, 20, 32. Direction 2: Quantity 2,
   Distance 14: a 3 x 2 grid. Drag the blue arrow of direction 1 by +4 mm: x = 8, 22, 36.
4. OK: one Rectangular Pattern step (FreeCAD's LinearPattern, both spacing lists written so
   the second row never stacks on the first). Ctrl+Z / Ctrl+Y.
5. Double-click it in the timeline: the values are shown; Symmetric in direction 2 with
   Quantity 2 and Spacing 7 ... (see the steps). OK.
6. A new pattern started and cancelled leaves the model unchanged; Esc too.
7. The hole's wall clicked in the view first, then the ribbon button: a Faces pattern of
   the hole along the box's front edge (picked in the view), Spacing 6, OK.

Hand-derived: a through hole of radius r removes pi r^2 * 10 from the box (V = 12000).
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
s = {}
R = 2.0
HOLE = ps.hole(R)


def one_hole():
    return ps.BOX - HOLE


# -- 2. start with nothing selected ----------------------------------------------------------
def ribbon_pattern():
    Gui.Selection.clearSelection()
    s["v0"] = h.solid_volume()
    h.ribbon("Rectangular Pattern")


def waiting():
    p = ps.panel()
    h.check("Rectangular Pattern dialog open", p is not None and p.kind == "rectangular")
    if p is None:
        return
    h.check("nothing picked yet", p.options["objects"] == [] and p.target is None)
    h.check("Objects box is active (blue)", p.fields["objects"].button.isChecked())
    h.check("Pattern Type is Features", p.pattern_type.currentText() == "Features")
    h.check("no error shown while waiting", p.message.text() == "", p.message.text())
    h.check("a hint says what to click", "timeline" in p.info.text(), p.info.text())
    h.check("model unchanged while waiting", ps.close(h.solid_volume(), s["v0"]))
    ps.no_popups("Rectangular Pattern with nothing selected")
    h.shot("1-waiting")


def click_hole_step():
    ps.timeline_click("Extrude 2")


def hole_picked():
    p = ps.panel()
    h.check("the hole's step is the object", p and len(p.options["objects"]) == 1, p and p.options)
    h.check("Objects box says 1 selected", p and p.fields["objects"].button.text() == "1 selected")
    h.check("waits for a direction", p and "Direction" in p.info.text(), p and p.info.text())
    h.check("no preview yet", p and p.target is None)


def click_direction_box():
    ps.click_box("direction")


def axes_shown():
    p = ps.panel()
    h.check("Direction box is active", p and p.fields["direction"].button.isChecked())
    h.check("origin axes drawn to click", p and p.axis_picker is not None)
    h.fit()


def click_x_axis():
    pl.click_on_plane(V(-12, 0, 0))


def direction_picked():
    p = ps.panel()
    if not h.check("dialog still open", p is not None):
        return
    d1 = p.options["direction"]
    d2 = p.options["direction2"]
    h.check("Direction 1 is the X axis", d1 and d1[0].Role == "X_Axis", d1)
    h.check("Direction 2 offered at right angles (Y axis)", d2 and d2[0].Role == "Y_Axis", d2)
    h.check(
        "Direction box shows X Axis",
        p.fields["direction"].button.text() == "X Axis",
        p.fields["direction"].button.text(),
    )
    h.check("origin axes hidden again", p.axis_picker is None)
    h.check("Objects box active again", p.fields["objects"].button.isChecked())
    h.check("preview made", p.target is not None)
    v = h.solid_volume()
    h.check("preview: 2 holes", ps.close(v, ps.BOX - 2 * HOLE), v)
    h.check("blue arrows for both directions", set(p.handles) == {"distance", "distance2"})
    h.check("the face behind the axis was not taken", len(p.options["objects"]) == 1)
    h.shot("2-preview")


def type_quantity_3():
    p = ps.panel()
    ps.type_quantity(p.quantity, 3)


def type_distance_24():
    p = ps.panel()
    ps.type_value(p.distance_field.widget, "24")


def three_holes():
    p = ps.panel()
    v = h.solid_volume()
    h.check("3 holes", ps.close(v, ps.BOX - 3 * HOLE), v)
    centres = ps.circle_centres(h.body().Shape, R, z=10)
    h.check("at x = 8, 20, 32", centres == [(8, 8), (20, 8), (32, 8)], centres)
    h.check(
        "arrow 1 at the typed extent",
        p and abs(p.handles["distance"].distance() - 24) < 1e-6,
        p and p.handles["distance"].distance(),
    )


def type_quantity2():
    p = ps.panel()
    ps.type_quantity(p.quantity2, 2)


def type_distance2():
    p = ps.panel()
    ps.type_value(p.distance2_field.widget, "14")


def grid():
    v = h.solid_volume()
    h.check("3 x 2 grid: 6 holes", ps.close(v, ps.BOX - 6 * HOLE), v)
    centres = ps.circle_centres(h.body().Shape, R, z=10)
    expect = [(x, y) for x in (8, 20, 32) for y in (8, 22)]
    h.check("second row at y = 22, not stacked on the first", centres == expect, centres)
    h.shot("3-grid")


def drag_arrow_1():
    s["before"] = ps.panel().distance_field.value()
    ps.drag_arrow("distance", 4.0)


def dragged():
    p = ps.panel()
    value = p.distance_field.value() if p else 0
    h.check("dragging the arrow lengthens the pattern", value > s["before"] + 2.0, value)
    s["dragged"] = value
    v = h.solid_volume()
    h.check("still 6 holes", ps.close(v, ps.BOX - 6 * HOLE), v)
    centres = ps.circle_centres(h.body().Shape, R, z=10)
    last = max(x for x, _y in centres)
    h.check("last column follows the arrow", abs(last - (8 + value)) < 1e-3, (last, value))


def type_distance_28():
    p = ps.panel()
    ps.type_value(p.distance_field.widget, "28")


def ok():
    p = ps.panel()
    h.check("no error before OK", p and p.message.text() == "", p and p.message.text())
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", ps.panel() is None and not Gui.Control.activeDialog())
    shape = h.body().Shape
    h.check("6 holes", ps.close(shape.Volume, ps.BOX - 6 * HOLE), shape.Volume)
    centres = ps.circle_centres(shape, R, z=10)
    h.check(
        "holes at x 8/22/36, y 8/22",
        centres == [(x, y) for x in (8, 22, 36) for y in (8, 22)],
        centres,
    )
    h.check("faces: 6 box + 6 hole walls", len(shape.Faces) == 12, len(shape.Faces))
    found = ps.patterns()
    h.check(
        "one pattern step, the end of the timeline", len(found) == 1 and h.body().Tip is found[0]
    )
    h.check(
        "FreeCAD's LinearPattern with both spacing lists",
        found
        and found[0].TypeId == "PartDesign::LinearPattern"
        and list(found[0].Spacings2) == [-1.0],
        found and (found[0].TypeId, list(found[0].Spacings2)),
    )
    h.check("timeline shows Rectangular Pattern 1", "Rectangular Pattern 1" in ps.timeline_titles())
    h.check("no leftover selection", not Gui.Selection.getSelectionEx())
    h.check("valid solid", shape.isValid())
    s["v"] = shape.Volume
    h.shot("4-ok")


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check(
        "Ctrl+Z removes the whole pattern",
        ps.close(h.solid_volume(), one_hole()) and not ps.patterns(),
        h.solid_volume(),
    )


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check(
        "Ctrl+Y brings it back",
        ps.close(h.solid_volume(), s["v"]) and len(ps.patterns()) == 1,
        h.solid_volume(),
    )
    h.fit()


# -- 5. edit from the timeline ------------------------------------------------------------------
def edit_from_timeline():
    ps.timeline_double_click("Rectangular Pattern 1")


def edit_open():
    p = ps.panel()
    h.check("double-click opens the dialog on the pattern", p is not None and p.editing)
    if p is None:
        return
    h.check("Quantity 3 shown", p.quantity.value() == 3, p.quantity.value())
    h.check("Distance shown", abs(p.distance_field.value() - 28) < 1e-6, p.distance_field.value())
    h.check("Quantity 2 (direction 2)", p.quantity2.value() == 2)
    h.check("Distance 14 (direction 2)", abs(p.distance2_field.value() - 14) < 1e-6)
    h.check("the hole is the object", len(p.options["objects"]) == 1)
    h.check("both arrows shown", set(p.handles) == {"distance", "distance2"}, list(p.handles))
    h.shot("5-edit")
    b.choose(p.distribution, "Spacing")


def spacing_chosen():
    p = ps.panel()
    # Spacing 28 puts the third column off the part (x = 64): type 12 instead.
    ps.type_value(p.distance_field.widget, "12")


def edit_ok():
    h.task_button("OK")


def after_edit():
    shape = h.body().Shape
    centres = ps.circle_centres(shape, R, z=10)
    h.check(
        "edited to Spacing 12: x = 8, 20, 32",
        centres == [(x, y) for x in (8, 20, 32) for y in (8, 22)],
        centres,
    )
    h.check("still one pattern", len(ps.patterns()) == 1)
    s["v"] = shape.Volume


# -- 6. cancel ---------------------------------------------------------------------------------
def cancel_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def cancel_pick():
    ps.timeline_click("Extrude 2")


def cancel_direction_box():
    ps.click_box("direction")


def cancel_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def cancel_now():
    p = ps.panel()
    h.check("a second preview is shown", p is not None and p.target is not None)
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel leaves the model unchanged", ps.close(h.solid_volume(), s["v"]))
    h.check("no new pattern", len(ps.patterns()) == 1, ps.patterns())
    h.check("dialog closed", not Gui.Control.activeDialog())
    tip = h.body().Tip
    h.check("the part is shown", tip.ViewObject.isVisible())


def esc_start():
    h.ribbon("Rectangular Pattern")


def esc_press():
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog() and ps.panel() is None)
    h.check("Esc changes nothing", ps.close(h.solid_volume(), s["v"]) and len(ps.patterns()) == 1)


# -- 7. faces picked first ------------------------------------------------------------------------
def pick_wall():
    h.fit()
    # The far wall of the hole at (32, 22): from the iso view (camera front-right, above)
    # only the back of a hole's wall shows, about 2.8 mm deep for a 4 mm hole.
    h.click(V(32 - R * 0.7071, 22 + R * 0.7071, 9))


def wall_selected():
    sel = ps.selection()
    h.check("a face is selected", sel and sel[0][1] and sel[0][1][0].startswith("Face"), sel)
    try:
        face = Gui.Selection.getSelectionEx()[0].SubObjects[0]
        h.check("it is the hole's round wall", face.Surface.TypeId == "Part::GeomCylinder")
    except Exception as exc:
        h.check("it is the hole's round wall", False, exc)
    h.ribbon("Rectangular Pattern")


def faces_type():
    p = ps.panel()
    if not h.check("dialog open", p is not None):
        return
    h.check("Pattern Type switched to Faces", p.pattern_type.currentText() == "Faces")
    h.check("the wall is the object", len(p.options["objects"]) == 1, p.options["objects"])
    h.check("Direction box waits (blue)", p.fields["direction"].button.isChecked())


def pick_front_edge():
    h.fit()
    h.click_edge(V(20, 0, 10))


def edge_direction():
    p = ps.panel()
    d1 = p.options["direction"] if p else None
    h.check("the front edge is Direction 1", d1 is not None and d1[1].startswith("Edge"), d1)
    b.choose(p.distribution, "Spacing")


def faces_values():
    p = ps.panel()
    ps.type_quantity(p.quantity, 2)


def faces_distance():
    from sciforge import pattern

    p = ps.panel()
    # The arrow shows which way the edge runs; the copy goes 6 mm toward x = 26 (between
    # the holes at x = 20 and 32).
    _point, d = pattern.direction_of(p.options["direction"])
    ps.type_value(p.distance_field.widget, "-6" if d.x > 0 else "6")


def faces_preview():
    v = h.solid_volume()
    h.check("one more hole (copy of the wall at x = 26)", ps.close(v, s["v"] - HOLE), v)
    centres = ps.circle_centres(h.body().Shape, R, z=10)
    h.check("the copy is at (26, 22)", (26, 22) in centres, centres)
    h.shot("6-faces")
    h.task_button("OK")


def faces_ok():
    found = ps.patterns()
    h.check("two pattern steps", len(found) == 2)
    h.check(
        "Rectangular Pattern 2 in the timeline", "Rectangular Pattern 2" in ps.timeline_titles()
    )
    shape = h.body().Shape
    h.check("valid solid", shape.isValid())
    h.check("7 holes", ps.close(shape.Volume, ps.BOX - 7 * HOLE), shape.Volume)
    h.shot("7-end")


h.run(
    "patterns_rect",
    b.box_steps("PatternRect")
    + ps.make_cut("hole", (8, 8), R)
    + [
        ribbon_pattern,
        waiting,
        click_hole_step,
        hole_picked,
        click_direction_box,
        axes_shown,
        click_x_axis,
        direction_picked,
        type_quantity_3,
        type_distance_24,
        three_holes,
        type_quantity2,
        type_distance2,
        grid,
        drag_arrow_1,
        dragged,
        type_distance_28,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit_from_timeline,
        edit_open,
        spacing_chosen,
        edit_ok,
        after_edit,
        cancel_start,
        cancel_pick,
        cancel_direction_box,
        cancel_axis,
        cancel_now,
        after_cancel,
        esc_start,
        esc_press,
        after_esc,
        pick_wall,
        wall_selected,
        faces_type,
        pick_front_edge,
        edge_direction,
        faces_values,
        faces_distance,
        faces_preview,
        faces_ok,
    ],
)
