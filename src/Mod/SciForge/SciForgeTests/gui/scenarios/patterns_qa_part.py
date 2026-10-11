# SPDX-License-Identifier: LGPL-2.1-or-later
"""Patterns on a part made of several features and bodies, mixed with other commands (QA, only
real input).

Path 8,  a second body (Extrude, Operation New Body): it becomes the active body. The first
         body's hole is still picked in the timeline and patterned (before, the dialog only
         took the active body's steps and silently ignored the click). Then a construction
         plane (Offset Plane from the right face, -20) is picked in the timeline as the Mirror
         Plane: the hole is mirrored across x = 20.
Path 9,  the hole that both steps repeat is deleted from the timeline: its copies go too (before,
         FreeCAD's pattern kept the copies of the deleted hole and froze), both steps show a
         warning in the timeline, and making the box taller still reaches the end of the
         timeline. Ctrl+Z twice: everything is back.
Path 10, another command's key while a dialog is open: E keeps a good pattern and opens
         Extrude; F drops a Circular Pattern that has nothing picked and opens Fillet; Delete
         in a Mirror dialog deletes nothing.

Hand-derived: box 40 x 30 x 10 = 12000; a through hole r 2 removes pi 2^2 10; the second body
is a cylinder r 5 x 10 = 250 pi.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
R = 2.0
HOLE = ps.hole(R)
CYL = math.pi * 25.0 * 10.0


def doc():
    return App.ActiveDocument


def body1():
    return doc().getObject("Body")


def body2():
    others = [x for x in ps.bodies() if x.Name != "Body"]
    return others[0] if others else None


def vol(body):
    return body.Shape.Volume if body is not None and not body.Shape.isNull() else 0.0


def centres():
    return ps.circle_centres(body1().Shape, R, z=10)


def problem(title):
    from sciforge import timeline_ops

    button = ps.timeline_button(title)
    obj = doc().getObject(button.item.name) if button is not None else None
    return timeline_ops.problem(obj) if obj is not None else ("missing", title)


def message():
    p = ps.panel()
    return p.message.text() if p is not None else ""


# -- Path 8: a second body, the first body's hole patterned and mirrored -------------------------------
def p8_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def p8_top():
    h.click(V(30, 20, 10))


def p8_circle():
    sk = h.in_sketch()
    h.check("sketch on the top face", sk is not None)
    if sk is not None:
        x, y = h.to_sketch(sk, V(60, 15, 10))
        h.draw_circle(sk, x, y, 5)


def p8_finish():
    h.ribbon("Finish Sketch")


def p8_extrude():
    h.fit()
    h.press("e")


def p8_new_body():
    b.choose(b.active_panel().operation, "New Body")


def p8_height():
    b.type_into(b.active_panel().distance.widget, "10")


def p8_extrude_ok():
    h.task_button("OK")


def p8_two_bodies():
    h.check("two bodies", len(ps.bodies()) == 2, [x.Label for x in ps.bodies()])
    h.check("the new body is a cylinder", ps.close(vol(body2()), CYL), vol(body2()))
    h.check("the new body is the active one", h.body() is body2(), h.body() and h.body().Label)
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def p8_pick_hole():
    ps.timeline_click("Extrude 2")


def p8_hole_taken():
    p = ps.panel()
    objs = p.options["objects"] if p else []
    h.check(
        "the first body's hole is taken while the second body is active",
        len(objs) == 1 and objs[0][0].Name == s.get("hole", objs[0][0].Name if objs else ""),
        (objs, message()),
    )
    h.check("no complaint", message() == "", message())
    h.check("the first body is the pattern's body now", p and p.body is body1())
    ps.click_box("direction")


def p8_axis():
    h.fit()
    h.click(V(-12, 0, 0))


def p8_values():
    p = ps.panel()
    ps.type_quantity(p.quantity, 2)
    ps.type_value(p.distance_field.widget, "12")


def p8_preview():
    h.check("a copy at x = 20 in the first body", centres() == [(8, 8), (20, 8)], centres())
    h.check("the second body unchanged", ps.close(vol(body2()), CYL), vol(body2()))
    h.task_button("OK")


def p8_after():
    found = [o for o in body1().Group if o.TypeId == "PartDesign::LinearPattern"]
    h.check("the pattern is a step of the first body", len(found) == 1)
    h.check("first body: 2 holes", ps.close(vol(body1()), ps.BOX - 2 * HOLE), vol(body1()))
    h.check("second body untouched", ps.close(vol(body2()), CYL) and len(body2().Group) <= 4)
    h.click_empty()
    h.ribbon("Offset Plane")


def p8_plane_face():
    h.fit()
    h.click(V(40, 15, 5))


def p8_plane_distance():
    p = b.active_panel()  # the CONSTRUCT dialog (rewritten by the inspect agent: .distance)
    field = getattr(p, "distance", None) or getattr(p, "field", None)
    b.type_into(field.widget, "-20")


def p8_plane_ok():
    h.task_button("OK")


def p8_mirror():
    planes = [o for o in doc().Objects if o.TypeId == "PartDesign::Plane"]
    h.check("a construction plane", len(planes) == 1)
    s["plane"] = planes[0].Name if planes else None
    Gui.Selection.clearSelection()
    h.ribbon("Mirror")


def p8_mirror_pick():
    ps.timeline_click("Extrude 2")


def p8_mirror_box():
    ps.click_box("plane")


def p8_mirror_plane():
    titles = [t for t in ps.timeline_titles() if "Plane" in t]
    h.check("the plane is in the timeline", len(titles) == 1, ps.timeline_titles())
    if titles:
        ps.timeline_click(titles[0])


def p8_mirrored():
    p = ps.panel()
    plane = p.options["plane"] if p else None
    h.check("the construction plane is the mirror plane", plane and plane[0].Name == s["plane"])
    h.check("hole mirrored to x = 32", centres() == [(8, 8), (20, 8), (32, 8)], centres())
    h.shot("8-mirror-plane")
    h.task_button("OK")


def p8_mirror_done():
    h.check("3 holes", ps.close(vol(body1()), ps.BOX - 3 * HOLE), vol(body1()))
    s["v"] = vol(body1())


# -- Path 9: the hole the steps repeat is deleted ----------------------------------------------------
def p9_delete():
    button = ps.timeline_button("Extrude 2")
    if h.check("the hole in the timeline", button is not None, ps.timeline_titles()):
        h.check("Delete in its menu", w.right_click(button, w.center(button), "Delete"))


p9_delete.wait_ms = 2000


def p9_deleted():
    h.check(
        "the copies went with the hole: a plain box", ps.close(vol(body1()), ps.BOX), vol(body1())
    )
    h.check("no hole left", centres() == [], centres())
    for title in ("Rectangular Pattern 1", "Mirror 1"):
        kind, why = problem(title)
        h.check("%s shows a warning in the timeline" % title, kind == "warning", (kind, why))
        h.check("%s says why" % title, "deleted" in why, why)
    h.shot("9-deleted")
    ps.timeline_double_click("Extrude 1")


def p9_taller():
    field = getattr(getattr(b.active_panel(), "distance", None), "widget", None)
    h.check("Extrude 1 opens", field is not None)
    if field is not None:
        b.type_into(field, "12")


def p9_taller_ok():
    h.task_button("OK")


p9_taller_ok.wait_ms = 1500


def p9_flows_through():
    h.check("the taller box reaches the end", ps.close(vol(body1()), 14400.0), vol(body1()))
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p9_undo_taller():
    h.check("Ctrl+Z: 10 high again", ps.close(vol(body1()), ps.BOX), vol(body1()))
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


p9_undo_taller.wait_ms = 1500


def p9_undo_delete():
    h.check(
        "Ctrl+Z: the hole and its copies are back", ps.close(vol(body1()), s["v"]), vol(body1())
    )
    h.check("3 holes", centres() == [(8, 8), (20, 8), (32, 8)], centres())
    for title in ("Rectangular Pattern 1", "Mirror 1"):
        kind, why = problem(title)
        h.check("%s fine again" % title, kind == "", (kind, why))


# -- Path 10: another command's key while a dialog is open ----------------------------------------------
def p10_start():
    Gui.Selection.clearSelection()
    s["n"] = len(ps.patterns())
    h.ribbon("Rectangular Pattern")


def p10_pick():
    ps.timeline_click("Extrude 2")


def p10_box():
    ps.click_box("direction")


def p10_axis():
    h.fit()
    h.click(V(0, -12, 0))


def p10_press_e():
    p = ps.panel()
    h.check("a preview is shown", p is not None and p.target is not None)
    h.fit()
    h.press("e")


p10_press_e.wait_ms = 1200


def p10_after_e():
    h.check("E kept the pattern", len(ps.patterns()) == s["n"] + 1, ps.patterns())
    p = b.active_panel()
    h.check("Extrude opened", p is not None and type(p).__name__ == "ExtrudePanel", p)
    h.press(QtCore.Qt.Key_Escape)


def p10_circular():
    h.check("Esc closed Extrude", not Gui.Control.activeDialog())
    Gui.Selection.clearSelection()
    s["v"] = vol(body1())
    s["n"] = len(ps.patterns())
    ps.menu("Circular Pattern")


def p10_press_f():
    p = ps.panel()
    h.check("Circular Pattern waits", p is not None and p.kind == "circular" and p.target is None)
    h.fit()
    h.press("f")


p10_press_f.wait_ms = 1200


def p10_after_f():
    h.check("the empty Circular Pattern was dropped", len(ps.patterns()) == s["n"])
    h.check("model unchanged", ps.close(vol(body1()), s["v"]), vol(body1()))
    h.check("Fillet opened", b.blend_panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def p10_mirror():
    h.check("Esc closed Fillet", not Gui.Control.activeDialog())
    Gui.Selection.clearSelection()
    h.ribbon("Mirror")


def p10_mirror_pick():
    ps.timeline_click("Extrude 2")


def p10_delete_key():
    p = ps.panel()
    h.check("the hole is picked", p is not None and len(p.options["objects"]) == 1)
    h.fit()
    h.press(QtCore.Qt.Key_Delete)


def p10_nothing_deleted():
    h.check("Delete deleted nothing", doc().getObject(s["hole"]) is not None)
    h.check("model unchanged", ps.close(vol(body1()), s["v"]), vol(body1()))
    h.check("Mirror still open", ps.panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def p10_end():
    h.check("closed", not Gui.Control.activeDialog())
    h.check("model unchanged", ps.close(vol(body1()), s["v"]), vol(body1()))
    broken = [o.Label for o in doc().Objects if set(o.State) & {"Invalid", "Error"}]
    h.check("nothing broken", not broken, broken)
    h.shot("10-end")


def remember_hole():
    button = ps.timeline_button("Extrude 2")
    s["hole"] = button.item.name if button is not None else None


h.run(
    "patterns_qa_part",
    b.box_steps("PatternQAPart")
    + ps.make_cut("hole", (8, 8), R)
    + [
        remember_hole,
        p8_sketch,
        p8_top,
        p8_circle,
        p8_finish,
        p8_extrude,
        p8_new_body,
        p8_height,
        p8_extrude_ok,
        p8_two_bodies,
        p8_pick_hole,
        p8_hole_taken,
        p8_axis,
        p8_values,
        p8_preview,
        p8_after,
        p8_plane_face,
        p8_plane_distance,
        p8_plane_ok,
        p8_mirror,
        p8_mirror_pick,
        p8_mirror_box,
        p8_mirror_plane,
        p8_mirrored,
        p8_mirror_done,
        p9_delete,
        p9_deleted,
        p9_taller,
        p9_taller_ok,
        p9_flows_through,
        p9_undo_taller,
        p9_undo_delete,
        p10_start,
        p10_pick,
        p10_box,
        p10_axis,
        p10_press_e,
        p10_after_e,
        p10_circular,
        p10_press_f,
        p10_after_f,
        p10_mirror,
        p10_mirror_pick,
        p10_delete_key,
        p10_nothing_deleted,
        p10_end,
    ],
)
