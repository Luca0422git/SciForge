# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fillet (F) the way a Fusion user does it, only real input: ribbon button with nothing
selected, click edges (again to drop one), type a radius, drag the blue arrow, an
impossible radius (the dialog says why, OK waits, nothing in the Report view), OK,
Ctrl+Z / Ctrl+Y, edit by double-clicking the timeline, Cancel, and a second fillet
started with F on edges selected beforehand. Geometry checked with hand-derived
formulas (see blend_steps)."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
RIGHT_TOP = V(40, 15, 10)
BACK_TOP = V(20, 30, 10)
BACK_RIGHT = V(40, 30, 5)
TOP_FACE = V(20, 15, 10)


def one_edge(r):
    return b.BOX - 40 * b.spandrel(r)


def ribbon_fillet():
    Gui.Selection.clearSelection()
    h.ribbon("Fillet")


def waiting_for_picks():
    p = b.blend_panel()
    h.check("Fillet dialog open", p is not None and p.title == "Fillet")
    if p is None:
        return
    h.check("nothing picked yet", p.refs == [] and p.target is None, p.refs)
    h.check("selection box says Select", p.select_button.text() == "Select", p.select_button.text())
    h.check("no error shown before picking", p.message.text() == "", p.message.text())
    h.check("model unchanged while waiting", b.close(h.solid_volume(), b.BOX), h.solid_volume())
    b.no_popups("Fillet with nothing selected")
    h.shot("1-waiting")


def click_front_edge():
    h.fit()
    h.click(FRONT_TOP)


def front_edge_picked():
    p = b.blend_panel()
    h.check("one edge picked", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("selection box says 1 selected", p and p.select_button.text() == "1 selected")
    h.check("blue arrow on the edge", p is not None and len(p.arrows) == 1)
    v = h.solid_volume()
    h.check("preview: radius 1 round (V = 12000 - 40 r^2 (1 - pi/4))", b.close(v, one_edge(1)), v)
    picked = [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]
    h.check("the picked edge is highlighted", len(picked) == 1 and len(picked[0][1]) == 1, picked)
    h.shot("2-one-edge")


def type_radius_3():
    p = b.blend_panel()
    if p:
        b.type_into(p.radius.widget, "3")


def radius_3_preview():
    p = b.blend_panel()
    v = h.solid_volume()
    h.check("typed radius 3 previews", b.close(v, one_edge(3)), (v, one_edge(3)))
    h.check(
        "arrow follows the typed radius",
        p and abs(p.arrows[0][0].distance() - 3.0) < 1e-6,
        p and p.arrows[0][0].distance(),
    )


def click_right_edge():
    h.click(RIGHT_TOP)


def two_edges():
    p = b.blend_panel()
    h.check("two edges picked", p is not None and len(p.refs) == 2, p and p.refs)
    v = h.solid_volume()
    expect = b.BOX - (40 + 30) * b.spandrel(3) + b.corner(3)
    h.check("two rounds meeting at a corner", b.close(v, expect), (v, expect))
    h.shot("3-two-edges")


def click_right_edge_again():
    h.click(RIGHT_TOP)


def right_edge_dropped():
    p = b.blend_panel()
    h.check("clicking a picked edge drops it", p is not None and len(p.refs) == 1, p and p.refs)
    v = h.solid_volume()
    h.check("preview back to one round", b.close(v, one_edge(3)), v)


def drag_arrow():
    p = b.blend_panel()
    if p is None or not p.arrows:
        h.check("arrow to drag", False)
        return
    start, end = b.arrow_screen(p, along=2.0)
    s["before"] = p.radius.value()
    h.drag(start, end)


def dragged():
    p = b.blend_panel()
    r = p.radius.value() if p else 0
    h.check(
        "dragging the arrow away from the edge grows the radius",
        r > s["before"] + 0.5,
        (s["before"], r),
    )
    v = h.solid_volume()
    h.check("preview matches the dragged radius", b.close(v, one_edge(r)), (v, one_edge(r)))
    h.shot("4-dragged")


def type_impossible():
    p = b.blend_panel()
    s["good"] = h.solid_volume()
    if p:
        b.type_into(p.radius.widget, "50")


def impossible_reported():
    p = b.blend_panel()
    text = p.message.text() if p else ""
    h.check("too-big radius explained in the dialog", "too big" in text, text)
    h.check(
        "preview keeps the last good result", b.close(h.solid_volume(), s["good"]), h.solid_volume()
    )
    h.check(
        "nothing about it in the Report view",
        not b.report_has_kernel_errors(),
        b.report_has_kernel_errors(),
    )
    b.no_popups("an impossible radius")
    h.shot("5-too-big")


impossible_reported.wait_ms = 1500  # the "largest radius that fits" hint is worked out


def hint_shown():
    p = b.blend_panel()
    text = p.message.text() if p else ""
    h.check("dialog suggests the largest radius that fits", "largest radius" in text, text)


def ok_refused():
    h.task_button("OK")


def still_open():
    p = b.blend_panel()
    h.check("OK waits while the radius does not fit", p is not None and Gui.Control.activeDialog())


def type_radius_2():
    p = b.blend_panel()
    if p:
        b.type_into(p.radius.widget, "2")


def ok():
    p = b.blend_panel()
    h.check(
        "error gone after a good radius",
        p is not None and p.message.text() == "",
        p and p.message.text(),
    )
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", b.blend_panel() is None and not Gui.Control.activeDialog())
    shape = h.body().Shape
    h.check(
        "fillet 1: V = 12000 - 40 * 4 * (1 - pi/4)",
        b.close(shape.Volume, one_edge(2)),
        shape.Volume,
    )
    h.check("fillet 1: 7 faces (refined)", len(shape.Faces) == 7, len(shape.Faces))
    h.check("valid solid", shape.isValid())
    bb = shape.BoundBox
    h.check("bounding box unchanged", b.close(bb.XLength, 40) and b.close(bb.ZLength, 10), bb)
    fl = b.blends()
    h.check(
        "one Fillet feature, the end of the timeline",
        len(fl) == 1 and h.body().Tip is fl[0] and fl[0].Refine,
        fl,
    )
    h.check("no leftover selection", not Gui.Selection.getSelectionEx())
    extrude = App.ActiveDocument.getObject("Extrude")
    h.check(
        "only the fillet is shown (no see-through leftover)",
        fl and fl[0].ViewObject.isVisible() and not extrude.ViewObject.isVisible(),
    )
    h.shot("6-fillet1")


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check(
        "Ctrl+Z removes the whole fillet",
        b.close(h.solid_volume(), b.BOX) and not b.blends(),
        h.solid_volume(),
    )


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check(
        "Ctrl+Y brings it back",
        b.close(h.solid_volume(), one_edge(2)) and len(b.blends()) == 1,
        h.solid_volume(),
    )
    h.fit()


def edit_from_timeline():
    b.timeline_double_click("Fillet 1")


def edit_open():
    p = b.blend_panel()
    h.check(
        "double-click opens the Fillet dialog on the feature",
        p is not None and p.target is not None and not p.created,
    )
    h.check("its edge is shown picked", p is not None and len(p.refs) == 1, p and p.refs)
    sel = [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]
    h.check("and highlighted", len(sel) == 1 and len(sel[0][1]) == 1, sel)
    h.check(
        "radius shown", p is not None and abs(p.radius.value() - 2.0) < 1e-9, p and p.radius.value()
    )
    h.shot("7-edit")
    if p:
        b.type_into(p.radius.widget, "4")


def edit_ok():
    h.task_button("OK")


def after_edit():
    h.check("edited to radius 4", b.close(h.solid_volume(), one_edge(4)), h.solid_volume())
    h.check("still one fillet", len(b.blends()) == 1, b.blends())
    s["v"] = h.solid_volume()


def cancel_start():
    h.press("f")


def cancel_pick_face():
    h.fit()
    h.click(TOP_FACE)


def cancel_preview():
    p = b.blend_panel()
    h.check(
        "clicking the top face picks it",
        p is not None and p.refs and p.refs[0].startswith("Face"),
        p and p.refs,
    )
    h.check("preview changes the part", not b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.shot("8-face-preview")
    h.task_button("Cancel")


def after_cancel():
    shown = [
        o.Name
        for o in h.body().Group
        if o.isDerivedFrom("PartDesign::Feature") and o.ViewObject.isVisible()
    ]
    h.check("after Cancel the body shows its last step only", shown == [h.body().Tip.Name], shown)
    h.check(
        "Cancel leaves the model as it was", b.close(h.solid_volume(), s["v"]), h.solid_volume()
    )
    h.check("no new feature", len(b.blends()) == 1, b.blends())
    h.check("dialog closed", not Gui.Control.activeDialog())


def preselect():
    h.fit()
    h.click(BACK_TOP)
    h.click(BACK_RIGHT, modifiers=QtCore.Qt.ControlModifier)


def press_f():
    sel = [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]
    h.check("two edges selected before F", sum(len(x[1]) for x in sel) == 2, sel)
    h.press("f")


def started_with_picks():
    p = b.blend_panel()
    h.check(
        "F with edges selected starts with them", p is not None and len(p.refs) == 2, p and p.refs
    )
    if p:
        b.type_into(p.radius.widget, "2")


def second_ok():
    h.task_button("OK")


def after_second():
    shape = h.body().Shape
    expect = s["v"] - (40 + 10) * b.spandrel(2) + b.corner(2)
    h.check(
        "second fillet (back-top + back-right edges, r 2)",
        b.close(shape.Volume, expect),
        (shape.Volume, expect),
    )
    h.check(
        "two Fillet features in the timeline",
        len(b.blends()) == 2 and "Fillet 2" in b.timeline_titles(),
        b.timeline_titles(),
    )
    h.check("valid solid at the end", shape.isValid())
    h.check(
        "no kernel errors in the Report view",
        not b.report_has_kernel_errors(),
        b.report_has_kernel_errors(),
    )
    h.shot("9-end")


def undo_inside_start():
    s["v"] = h.solid_volume()
    h.press("f")


def undo_inside_pick():
    h.fit()
    h.click(RIGHT_TOP)


def undo_inside_press():
    p = b.blend_panel()
    h.check("third fillet previewed", p is not None and p.refs and p.target is not None)
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undo_inside_after():
    h.check(
        "Ctrl+Z inside the dialog ends it",
        b.blend_panel() is None and not Gui.Control.activeDialog(),
    )
    h.check(
        "and takes the unfinished fillet away",
        b.close(h.solid_volume(), s["v"]) and len(b.blends()) == 2,
        (h.solid_volume(), b.blends()),
    )
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redo_after_inside():
    shape = h.body().Shape
    h.check(
        "Ctrl+Y brings that fillet back as a valid step",
        len(b.blends()) == 3 and shape.isValid() and shape.Volume < s["v"],
        (len(b.blends()), shape.Volume),
    )
    fl = b.blends()[-1]
    h.check(
        "the redone fillet is shown and clickable",
        fl.ViewObject.isVisible() and fl.ViewObject.Selectable,
    )


h.run(
    "fillet",
    b.box_steps("Fillet")
    + [
        ribbon_fillet,
        waiting_for_picks,
        click_front_edge,
        front_edge_picked,
        type_radius_3,
        radius_3_preview,
        click_right_edge,
        two_edges,
        click_right_edge_again,
        right_edge_dropped,
        drag_arrow,
        dragged,
        type_impossible,
        impossible_reported,
        hint_shown,
        ok_refused,
        still_open,
        type_radius_2,
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
        cancel_pick_face,
        cancel_preview,
        after_cancel,
        preselect,
        press_f,
        started_with_picks,
        second_ok,
        after_second,
        undo_inside_start,
        undo_inside_pick,
        undo_inside_press,
        undo_inside_after,
        redo_after_inside,
    ],
)
