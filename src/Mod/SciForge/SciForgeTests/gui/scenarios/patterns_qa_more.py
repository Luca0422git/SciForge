# SPDX-License-Identifier: LGPL-2.1-or-later
"""More Fusion habits with patterns (QA, only real input).

Path 11, Press Pull after a pattern: the front face of the patterned part is pulled out 5 mm.
         Then the pattern is edited to Pattern Type Faces (the hole's wall picked in the view):
         the step is rebuilt as SciForge's feature and the Press Pull still pulls the front face
         (before, it lost its face and failed).
Path 12, a pattern of a pattern: Rectangular Pattern of the hole and "Rectangular Pattern 1"
         (picked in the timeline) along Y gives a second row; editing the first pattern
         (Quantity 2) changes both rows.
Path 13, Circular Pattern, Type Angle, Total Angle 270 typed: the curved handle sits at 270 (it
         showed 180, and touching it made the angle jump back to 180). There the handle is seen
         almost edge-on: it is still easy to grab by its middle (it was a sliver, the press
         missed it and the box behind it joined the objects). Dragged on to about 290; Full;
         Cancel leaves the part as it was.

Hand-derived: box 40 x 30 x 10 = 12000; a through hole r 2 removes pi 2^2 10; the Press Pull
makes the box 40 x 35 x 10 = 14000.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
s = {}
R = 2.0
HOLE = ps.hole(R)
PULLED = 14000.0


def doc():
    return App.ActiveDocument


def centres():
    return ps.circle_centres(h.body().Shape, R, z=10)


def press_pull():
    found = [o for o in doc().Objects if getattr(o, "SciForgeType", "") == "PressPull"]
    return found[0] if found else None


def message():
    p = ps.panel()
    return p.message.text() if p is not None else ""


# -- the first pattern --------------------------------------------------------------------------------
def make_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def make_pick():
    ps.timeline_click("Extrude 2")


def make_box():
    ps.click_box("direction")


def make_axis():
    h.fit()
    h.click(V(-12, 0, 0))


def make_values():
    p = ps.panel()
    ps.type_quantity(p.quantity, 3)
    ps.type_value(p.distance_field.widget, "24")


def make_ok():
    h.task_button("OK")


# -- Path 11: Press Pull after the pattern, the pattern rebuilt -------------------------------------------
def p11_q():
    h.check("3 holes", centres() == [(8, 8), (20, 8), (32, 8)], centres())
    Gui.Selection.clearSelection()
    h.fit()
    h.press("q")


def p11_front():
    h.click(V(30, 0, 4))


def p11_distance():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    h.check("the front face is picked", p is not None and p.target is not None)
    if p is not None:
        b.type_into(p.field.widget, "5")


def p11_ok():
    h.task_button("OK")


p11_ok.wait_ms = 1200


def p11_pulled():
    pp = press_pull()
    h.check("Press Pull made", pp is not None)
    h.check("it pulls a face of the pattern", pp and pp.Faces and pp.Faces[0] is ps.patterns()[0])
    h.check("box 35 deep", ps.close(h.solid_volume(), PULLED - 3 * HOLE), h.solid_volume())
    ps.timeline_double_click("Rectangular Pattern 1")


def p11_faces_type():
    p = ps.panel()
    h.check("edit open", p is not None and p.editing)
    if p is not None:
        b.choose(p.pattern_type, "Faces")


def p11_click_wall():
    h.fit()
    h.click(V(8 - R * 0.7071, 8 + R * 0.7071, 9))


def p11_wall_taken():
    p = ps.panel()
    objs = p.options["objects"] if p else []
    h.check("the hole's wall is the object", len(objs) == 1 and objs[0][1].startswith("Face"), objs)
    h.task_button("OK")


p11_wall_taken.wait_ms = 1500


def p11_after():
    pat = ps.patterns()[0] if ps.patterns() else None
    h.check("rebuilt as SciForge's feature", pat and pat.TypeId == "PartDesign::FeaturePython")
    pp = press_pull()
    h.check("the Press Pull follows the new step", pp and pp.Faces and pp.Faces[0] is pat)
    face = pat.Shape.getElement(pp.Faces[1][0]) if pp and pp.Faces else None
    h.check(
        "it still pulls the front face",
        face is not None and abs(face.CenterOfMass.y) < 1e-6,
        face and face.CenterOfMass,
    )
    h.check("same part", ps.close(h.solid_volume(), PULLED - 3 * HOLE), h.solid_volume())
    broken = [o.Label for o in doc().Objects if set(o.State) & {"Invalid", "Error"}]
    h.check("nothing broken", not broken, broken)
    h.shot("11-press-pull")


# -- Path 12: a pattern of a pattern -----------------------------------------------------------------------
def p12_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def p12_pick_pattern():
    ps.timeline_click("Rectangular Pattern 1")


def p12_taken():
    p = ps.panel()
    objs = p.options["objects"] if p else []
    h.check("the pattern step is taken", len(objs) == 1 and objs[0][0] is ps.patterns()[0])
    h.check("no complaint", message() == "", message())
    # Like Fusion, a pattern step stands for its copies; the hole itself is its own step.
    ps.timeline_click("Extrude 2")


def p12_both_taken():
    p = ps.panel()
    objs = p.options["objects"] if p else []
    h.check("the hole and its pattern are the objects", len(objs) == 2, objs)
    ps.click_box("direction")


def p12_y_axis():
    h.fit()
    h.click(V(0, -12, 0))


def p12_values():
    p = ps.panel()
    ps.type_quantity(p.quantity, 2)
    ps.type_value(p.distance_field.widget, "14")


def p12_preview():
    want = [(x, y) for x in (8, 20, 32) for y in (8, 22)]
    h.check("a second row of 3 holes at y = 22", centres() == want, centres())
    h.task_button("OK")


p12_preview.wait_ms = 1200


def p12_edit_first():
    h.check("6 holes", ps.close(h.solid_volume(), PULLED - 6 * HOLE), h.solid_volume())
    ps.timeline_double_click("Rectangular Pattern 1")


def p12_quantity_2():
    p = ps.panel()
    if h.check("edit open", p is not None):
        ps.type_quantity(p.quantity, 2)


def p12_edit_ok():
    h.task_button("OK")


p12_edit_ok.wait_ms = 1500


def p12_both_rows():
    want = [(x, y) for x in (8, 32) for y in (8, 22)]
    h.check("both rows follow the first pattern", centres() == want, centres())
    broken = [o.Label for o in doc().Objects if set(o.State) & {"Invalid", "Error"}]
    h.check("nothing broken", not broken, broken)
    s["v"] = h.solid_volume()


# -- Path 13: Total Angle past 180 typed, then the handle dragged ---------------------------------------------
def p13_start():
    Gui.Selection.clearSelection()
    ps.menu("Circular Pattern")


def p13_pick():
    ps.timeline_click("Extrude 2")


def p13_box():
    ps.click_box("axis")


def p13_axis():
    h.fit()
    h.click(V(0, 0, 18))  # the Z axis above the box's corner


def p13_angle_type():
    p = ps.panel()
    h.check("Z axis picked", p and p.options["axis"] and p.options["axis"][0].Role == "Z_Axis")
    b.choose(p.circular_type, "Angle")


def p13_type_270():
    ps.type_value(ps.panel().angle_field.widget, "270")


def p13_handle_at_270():
    p = ps.panel()
    handle = p.handles.get("angle")
    h.check("the curved handle is shown", handle is not None, list(p.handles))
    if handle is None:
        return
    h.check("the handle sits at 270", abs(handle.angle() - 270.0) < 1.0, handle.angle())
    s["objects"] = list(p.options["objects"])
    # A click in the middle of the handle, where the box's corner is right behind it. There
    # the handle is seen almost edge-on: it was a sliver, the press missed it and picked the
    # box (whose feature joined the objects).
    h.click(handle.screen_points(270.0)[1])


def p13_press_is_no_pick():
    p = ps.panel()
    h.check(
        "a press on the handle picks nothing behind it",
        p is not None and p.options["objects"] == s["objects"],
        p and p.options["objects"],
    )
    handle = p.handles.get("angle")
    if handle is not None:
        ps.drag_turn(handle, 270.0, 290.0)  # grabbed by its middle, turned on by 20 degrees


def p13_dragged_on():
    p = ps.panel()
    angle = p.angle_field.value()
    h.check("dragging on from 270 gives about 290 (no jump back to 180)", 280 < angle < 300, angle)
    h.check("no message", message() == "", message())
    b.choose(p.circular_type, "Full")


def p13_full():
    p = ps.panel()
    h.check("Full: no Total Angle", not p.angle_field.widget.isVisible())
    h.check("no curved handle for Full", "angle" not in p.handles, list(p.handles))
    h.task_button("Cancel")


def p13_cancelled():
    h.check("Cancel: the part as it was", ps.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("two patterns", len(ps.patterns()) == 2, ps.patterns())
    h.check("valid", h.body().Shape.isValid())


h.run(
    "patterns_qa_more",
    b.box_steps("PatternQAMore")
    + ps.make_cut("hole", (8, 8), R)
    + [
        make_start,
        make_pick,
        make_box,
        make_axis,
        make_values,
        make_ok,
        p11_q,
        p11_front,
        p11_distance,
        p11_ok,
        p11_pulled,
        p11_faces_type,
        p11_click_wall,
        p11_wall_taken,
        p11_after,
        p12_start,
        p12_pick_pattern,
        p12_taken,
        p12_both_taken,
        p12_y_axis,
        p12_values,
        p12_preview,
        p12_edit_first,
        p12_quantity_2,
        p12_edit_ok,
        p12_both_rows,
        p13_start,
        p13_pick,
        p13_box,
        p13_axis,
        p13_angle_type,
        p13_type_270,
        p13_handle_at_270,
        p13_press_is_no_pick,
        p13_dragged_on,
        p13_full,
        p13_cancelled,
    ],
)
