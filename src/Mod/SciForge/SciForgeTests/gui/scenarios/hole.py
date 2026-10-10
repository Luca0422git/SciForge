# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole (H) the way a Fusion user does it, only real input, on a 40 x 30 x 10 box:

1. Hole button with nothing selected: the dialog waits for a face, nothing changes.
2. Click the top face: the hole is where the click was. Type X 12 / Y 8, depth 6.
3. Drag the blue depth arrow down; Drill Point Flat; Counterbore 10 x 3; Countersink
   10 x 90 degrees; a counterbore wider than allowed is explained in the dialog; Simple; OK.
4. Ctrl+Z takes the whole hole (and its hidden sketch) away, Ctrl+Y brings it back.
5. Double-click the hole in the timeline: click two edges of the part as references, type
   15 and 20: the hole moves to (20, 15). Drag the centre point. OK.
6. H, click the top face elsewhere: a preview; Cancel: the model is as it was.
7. Click the top face, then H: the second hole is drilled where that click was; Enter.
Geometry checked with hand-derived formulas (hole_steps.py).
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs

V = App.Vector
s = {}


def ribbon_hole():
    Gui.Selection.clearSelection()
    h.ribbon("Hole")


def waiting():
    p = hs.hole_panel()
    h.check("Hole dialog open", p is not None and p.title == "Hole")
    if p is None:
        return
    h.check("nothing placed yet", p.target is None)
    h.check("face box waits for a click", p.fields["face"].button.isChecked())
    h.check("no error before picking", p.message.text() == "", p.message.text())
    h.check("Single Hole is the placement", p.placement.currentText() == "Single Hole")
    h.check("model unchanged while waiting", hs.close(h.solid_volume(), hs.BOX))
    hs.no_popups("Hole with nothing selected")
    h.shot("1-waiting")


def click_top():
    h.fit()
    h.click(V(12, 8, 10))


def placed():
    p = hs.hole_panel()
    h.check("a hole is previewed", p is not None and p.target is not None)
    if p is None or p.target is None:
        return
    c = hs.centre_of(p.target)
    h.check("the hole is where the click was", hs.vnear(c, V(12, 8, 10), 0.5), c)
    h.check("hole goes down into the part", hs.vnear(hs.centres_dir(p.target), V(0, 0, -1)))
    helpers = hs.helper_sketches()
    h.check("one hidden helper sketch", len(helpers) == 1 and not hs.visible(helpers[0]))
    h.check("X / Y fields shown", p.pos_x.widget.isVisible() and p.pos_y.widget.isVisible())
    h.check("depth arrow shown", "depth" in p.draggers and "centre" in p.draggers)
    v = h.solid_volume()
    expect = hs.BOX - hs.cylinder(5, 10)
    h.check("default hole d5 x 10 (tip below the part)", hs.close(v, expect), (v, expect))
    h.shot("2-placed")


def type_position():
    p = hs.hole_panel()
    if p:
        hs.type_into(p.pos_x.widget, "12")
        hs.type_into(p.pos_y.widget, "8")


def type_depth():
    p = hs.hole_panel()
    c = hs.centre_of(p.target) if p and p.target else None
    h.check("typed X / Y moved the hole to (12, 8)", hs.vnear(c, V(12, 8, 10)), c)
    if p:
        hs.type_into(p.depth.widget, "6")


def depth_6():
    v = h.solid_volume()
    expect = hs.BOX - hs.cylinder(5, 6) - hs.tip_cone(5)
    h.check("depth 6 with a 118 degree tip", hs.close(v, expect), (v, expect))
    h.shot("3-depth6")


def drag_depth():
    p = hs.hole_panel()
    arrow = p.draggers.get("depth") if p else None
    if arrow is None:
        h.check("depth arrow to drag", False)
        return
    s["before"] = p.depth.value()
    hs.drag_arrow(p.depth_origin, p.depth_direction, arrow.distance(), 2.0)


def dragged():
    p = hs.hole_panel()
    depth = p.depth.value() if p else 0
    h.check(
        "dragging the arrow down drills deeper", depth > s["before"] + 0.5, (s["before"], depth)
    )
    v = h.solid_volume()
    expect = hs.BOX - hs.cylinder(5, depth) - hs.tip_cone(5)
    h.check("preview follows the dragged depth", hs.close(v, expect), (v, expect))
    if p:
        hs.type_into(p.depth.widget, "6")


def flat_point():
    p = hs.hole_panel()
    if p:
        b.choose(p.drill_point, "Flat")


def flat():
    v = h.solid_volume()
    expect = hs.BOX - hs.cylinder(5, 6)
    h.check("flat drill point: d5 x 6", hs.close(v, expect), (v, expect))
    p = hs.hole_panel()
    h.check("tip angle hidden for a flat hole", p and not p.drill_angle.widget.isVisible())


def counterbore():
    p = hs.hole_panel()
    if p:
        b.choose(p.hole_type, "Counterbore")


def counterbore_sizes():
    p = hs.hole_panel()
    h.check("counterbore fields shown", p and p.cbore_diameter.widget.isVisible())
    if p:
        hs.type_into(p.cbore_diameter.widget, "10")
        hs.type_into(p.cbore_depth.widget, "3")


def counterbore_made():
    v = h.solid_volume()
    expect = hs.BOX - hs.cylinder(5, 6) - (hs.cylinder(10, 3) - hs.cylinder(5, 3))
    h.check("counterbore 10 x 3 on d5 x 6", hs.close(v, expect), (v, expect))
    h.shot("4-counterbore")
    p = hs.hole_panel()
    if p:
        hs.type_into(p.cbore_diameter.widget, "4")


def counterbore_too_small():
    p = hs.hole_panel()
    text = hs.message(p)
    h.check("a counterbore narrower than the hole is explained", "wider" in text, text)
    h.check(
        "nothing about it in the Report view",
        not b.report_has_kernel_errors(),
        b.report_has_kernel_errors(),
    )
    hs.no_popups("a bad counterbore")
    if p:
        hs.type_into(p.cbore_diameter.widget, "10")


def countersink():
    p = hs.hole_panel()
    h.check("error gone again", p is not None and p.message.text() == "", hs.message(p))
    if p:
        b.choose(p.hole_type, "Countersink")


def countersink_sizes():
    p = hs.hole_panel()
    if p:
        hs.type_into(p.csink_diameter.widget, "10")
        hs.type_into(p.csink_angle.widget, "90")


def countersink_made():
    v = h.solid_volume()
    expect = hs.BOX - hs.countersink(5, 10, 6)
    h.check("countersink 10 x 90 deg on d5 x 6", hs.close(v, expect), (v, expect))
    h.shot("5-countersink")
    p = hs.hole_panel()
    if p:
        b.choose(p.hole_type, "Simple")


def ok():
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", hs.hole_panel() is None and not Gui.Control.activeDialog())
    shape = h.body().Shape
    expect = hs.BOX - hs.cylinder(5, 6)
    h.check("hole 1: d5 x 6 flat at (12, 8)", hs.close(shape.Volume, expect), shape.Volume)
    h.check("hole 1: 8 faces", len(shape.Faces) == 8, len(shape.Faces))
    h.check("valid solid", shape.isValid())
    hl = hs.holes()
    h.check("one Hole, the end of the timeline", len(hl) == 1 and h.body().Tip is hl[0], hl)
    h.check("hole at (12, 8)", hl and hs.vnear(hs.centre_of(hl[0]), V(12, 8, 10)))
    titles = hs.timeline_titles()
    h.check(
        "timeline shows Hole 1 and no helper sketch",
        "Hole 1" in titles and not any("Sketch 2" in t for t in titles),
        titles,
    )
    helpers = hs.helper_sketches()
    h.check(
        "helper sketch named after the hole and hidden",
        len(helpers) == 1 and helpers[0].Label == "Hole 1 Sketch" and not hs.visible(helpers[0]),
        [(x.Label, hs.visible(x)) for x in helpers],
    )
    h.check("no leftover selection", not Gui.Selection.getSelectionEx())
    h.shot("6-hole1")


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check(
        "Ctrl+Z removes the whole hole and its sketch",
        hs.close(h.solid_volume(), hs.BOX) and not hs.holes() and not hs.helper_sketches(),
        (h.solid_volume(), hs.holes(), hs.helper_sketches()),
    )


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check(
        "Ctrl+Y brings it back",
        hs.close(h.solid_volume(), hs.BOX - hs.cylinder(5, 6)) and len(hs.holes()) == 1,
        h.solid_volume(),
    )
    h.fit()


def edit_from_timeline():
    b.timeline_double_click("Hole 1")


def edit_open():
    p = hs.hole_panel()
    h.check("double-click opens the Hole dialog on it", p is not None and p.editing)
    if p is None:
        return
    h.check("its depth is shown", abs(p.depth.value() - 6.0) < 1e-9, p.depth.value())
    h.check("its drill point is shown", p.drill_point.currentText() == "Flat")
    h.check(
        "its position is shown",
        abs(p.pos_x.value() - 12) < 1e-6 and abs(p.pos_y.value() - 8) < 1e-6,
        (p.pos_x.value(), p.pos_y.value()),
    )
    h.shot("7-edit")


def click_front_edge():
    h.fit()
    h.click_edge(V(30, 0, 10))


def one_reference():
    p = hs.hole_panel()
    h.check("one reference edge", p and len(hs.references(p.target)) == 1, p and p.target)
    h.check("its distance is shown", p and p.ref_fields[0].widget.isVisible())
    h.check(
        "measured from the edge as it is now (y = 8)",
        p and abs(p.ref_fields[0].value() - 8.0) < 1e-6,
        p and p.ref_fields[0].value(),
    )


def click_left_edge():
    h.click_edge(V(0, 22, 10))


def two_references():
    p = hs.hole_panel()
    refs = hs.references(p.target) if p else []
    h.check("two reference edges", len(refs) == 2, refs)
    h.check("X / Y give way to the distances", p and not p.pos_x.widget.isVisible())
    if p:
        hs.type_into(p.ref_fields[0].widget, "15")
        hs.type_into(p.ref_fields[1].widget, "20")


def moved_by_references():
    p = hs.hole_panel()
    c = hs.centre_of(p.target) if p else None
    h.check("typed distances put the hole at (20, 15)", hs.vnear(c, V(20, 15, 10)), c)
    h.shot("8-references")


def drag_centre():
    p = hs.hole_panel()
    dot = p.draggers.get("centre") if p else None
    if dot is None:
        h.check("centre point to drag", False)
        return
    start = dot.point()
    s["centre_before"] = start
    h.drag(h.screen_point(start), h.screen_point(start + V(-4, 0, 0)))


def centre_dragged():
    p = hs.hole_panel()
    c = hs.centre_of(p.target) if p else None
    before = s.get("centre_before")
    h.check(
        "dragging the dot moves the hole",
        c is not None and before is not None and (c - before).Length > 1.0,
        (before, c),
    )
    refs = hs.references(p.target) if p else []
    h.check("the references follow the drag", len(refs) == 2, refs)
    if p:
        hs.type_into(p.ref_fields[0].widget, "15")
        hs.type_into(p.ref_fields[1].widget, "20")


def edit_ok():
    h.task_button("OK")


def after_edit():
    hl = hs.holes()
    h.check("still one hole", len(hl) == 1, hl)
    c = hs.centre_of(hl[0]) if hl else None
    h.check("hole now at (20, 15)", hs.vnear(c, V(20, 15, 10), 1e-6), c)
    h.check("same volume", hs.close(h.solid_volume(), hs.BOX - hs.cylinder(5, 6)))
    s["v"] = h.solid_volume()
    s["objects"] = len(App.ActiveDocument.Objects)


def browser_sketch():
    """The hole's sketch in the browser (named after the hole): double-clicking it opens
    the hole, where its point is moved."""
    hs.browser_double_click("Hole 1 Sketch")


def browser_opened():
    p = hs.hole_panel()
    h.check(
        "double-clicking the hole's sketch opens that hole's dialog",
        p is not None and p.editing and p.target is hs.holes()[0],
    )
    h.check("its sketch stays hidden", not hs.visible(hs.helper_sketches()[0]))
    h.check("no sketch editing", h.in_sketch() is None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closed the dialog", hs.hole_panel() is None and not Gui.Control.activeDialog())
    h.check("Esc changed nothing", hs.close(h.solid_volume(), s["v"]))


def cancel_start():
    h.press("h")


def cancel_click():
    h.fit()
    h.click(V(32, 24, 10))


def cancel_preview():
    p = hs.hole_panel()
    h.check("a second hole is previewed", p is not None and p.target is not None)
    h.check("the preview changes the part", not hs.close(h.solid_volume(), s["v"]))
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel leaves the model as it was", hs.close(h.solid_volume(), s["v"]))
    h.check(
        "no new objects",
        len(App.ActiveDocument.Objects) == s["objects"],
        [o.Name for o in App.ActiveDocument.Objects],
    )
    h.check("dialog closed", not Gui.Control.activeDialog())
    shown = [
        o.Name
        for o in h.body().Group
        if o.isDerivedFrom("PartDesign::Feature") and o.ViewObject.isVisible()
    ]
    h.check("the body shows its last step only", shown == [h.body().Tip.Name], shown)


def preselect_face():
    h.fit()
    h.click(V(30, 8, 10))


def press_h():
    sel = Gui.Selection.getSelectionEx()
    h.check(
        "top face selected before H",
        len(sel) == 1,
        [(x.ObjectName, x.SubElementNames) for x in sel],
    )
    h.press("h")


def started_on_face():
    p = hs.hole_panel()
    h.check(
        "H with a face selected places the hole at once", p is not None and p.target is not None
    )
    c = hs.centre_of(p.target) if p and p.target else None
    h.check("where the face was clicked", hs.vnear(c, V(30, 8, 10), 0.5), c)
    h.check(
        "the last settings are remembered (d5, flat)",
        p and abs(p.diameter.value() - 5) < 1e-9 and p.drill_point.currentText() == "Flat",
    )
    if p:
        hs.type_into(p.pos_x.widget, "30")
        hs.type_into(p.pos_y.widget, "8")


def second_enter():
    p = hs.hole_panel()
    if p:
        hs.type_into(p.diameter.widget, "4")
        b.press_enter(p.diameter.widget)


def after_second():
    h.check("Enter finished the dialog", not Gui.Control.activeDialog())
    hl = hs.holes()
    h.check("two holes", len(hl) == 2, hl)
    expect = s["v"] - hs.cylinder(4, 6)
    h.check("second hole d4 x 6", hs.close(h.solid_volume(), expect), (h.solid_volume(), expect))
    h.check("Hole 2 in the timeline", "Hole 2" in hs.timeline_titles(), hs.timeline_titles())
    h.check("valid solid at the end", h.body().Shape.isValid())
    h.check("no kernel errors in the Report view", not b.report_has_kernel_errors())
    hs.no_popups("the second hole")
    h.shot("9-end")


h.run(
    "hole",
    b.box_steps("Hole")
    + [
        ribbon_hole,
        waiting,
        click_top,
        placed,
        type_position,
        type_depth,
        depth_6,
        drag_depth,
        dragged,
        flat_point,
        flat,
        counterbore,
        counterbore_sizes,
        counterbore_made,
        counterbore_too_small,
        countersink,
        countersink_sizes,
        countersink_made,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit_from_timeline,
        edit_open,
        click_front_edge,
        one_reference,
        click_left_edge,
        two_references,
        moved_by_references,
        drag_centre,
        centre_dragged,
        edit_ok,
        after_edit,
        browser_sketch,
        browser_opened,
        after_esc,
        cancel_start,
        cancel_click,
        cancel_preview,
        after_cancel,
        preselect_face,
        press_h,
        started_on_face,
        second_enter,
        after_second,
    ],
)
