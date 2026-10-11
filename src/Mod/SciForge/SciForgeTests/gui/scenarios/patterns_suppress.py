# SPDX-License-Identifier: LGPL-2.1-or-later
"""Suppression in a pattern, the way a Fusion user does it (real input only):

1. A 40 x 30 x 10 box with a through hole r 2 at (8, 8); Rectangular Pattern of the hole
   along X: Quantity 3, Distance 24 (holes at x = 8, 20, 32).
2. Tick Suppression: a dot appears on every copy. Click the dot of the middle copy: that
   copy is left out (two holes, at 8 and 32) and its dot turns grey. OK.
3. Ctrl+Z / Ctrl+Y. Edit from the timeline: Suppression is ticked, the grey dot is there;
   click it again: three holes. Untick Suppression: still three. OK.
4. A Circular Pattern of the same hole with one copy suppressed, then Cancel: unchanged.

Hand-derived: box 12000; a through hole r 2 removes pi 2^2 10.
"""
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


def centres():
    return ps.circle_centres(h.body().Shape, R, z=10)


def tick(box):
    """Click the check box itself (a click on the middle of a wide form row does nothing)."""
    w.click(box, QtCore.QPoint(8, box.height() // 2))


def start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def pick():
    ps.timeline_click("Extrude 2")


def box():
    ps.click_box("direction")


def axis():
    h.fit()
    h.click(V(-12, 0, 0))


def quantity():
    ps.type_quantity(ps.panel().quantity, 3)


def distance():
    ps.type_value(ps.panel().distance_field.widget, "24")


def three():
    h.check("3 holes", centres() == [(8, 8), (20, 8), (32, 8)], centres())
    p = ps.panel()
    h.check("no dots before Suppression is ticked", p.dots is None)
    tick(p.suppression)


def dots_shown():
    p = ps.panel()
    h.check("Suppression ticked", p.suppression.isChecked())
    h.check(
        "a dot on each copy",
        p.dots is not None and len(p.dots.points) == 2,
        p.dots and p.dots.points,
    )
    h.shot("1-dots")


def click_middle_dot():
    p = ps.panel()
    if p.dots is None:
        return
    h.fit()
    s["dot"] = p.dots.points[0]  # the copy at x = 20
    h.click(s["dot"])


def suppressed():
    p = ps.panel()
    h.check("the middle copy is left out", p.options["suppressed"] == [0], p.options["suppressed"])
    h.check("two holes at 8 and 32", centres() == [(8, 8), (32, 8)], centres())
    v = h.solid_volume()
    h.check("volume: two holes", ps.close(v, ps.BOX - 2 * HOLE), v)
    h.check("the objects did not change", len(p.options["objects"]) == 1)
    h.shot("2-suppressed")
    h.task_button("OK")


def after_ok():
    found = ps.patterns()
    h.check("one pattern", len(found) == 1)
    h.check(
        "made by SciForge's pattern feature (FreeCAD's cannot leave a copy out)",
        found and found[0].TypeId == "PartDesign::FeaturePython",
        found and found[0].TypeId,
    )
    h.check("timeline: Rectangular Pattern 1", "Rectangular Pattern 1" in ps.timeline_titles())
    h.check("valid", h.body().Shape.isValid())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check("Ctrl+Z: one hole", ps.close(h.solid_volume(), ps.BOX - HOLE) and not ps.patterns())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check("Ctrl+Y: two holes", ps.close(h.solid_volume(), ps.BOX - 2 * HOLE))
    h.fit()


def edit():
    ps.timeline_double_click("Rectangular Pattern 1")


def edit_open():
    p = ps.panel()
    h.check("the dialog opens", p is not None and p.editing)
    if p is None:
        return
    h.check("Suppression ticked", p.suppression.isChecked())
    h.check("the left-out copy is known", p.options["suppressed"] == [0])
    h.check("dots shown", p.dots is not None and len(p.dots.points) == 2)
    h.shot("3-edit")
    h.fit()
    if p.dots is not None:
        h.click(p.dots.points[0])


def back_in():
    p = ps.panel()
    h.check(
        "clicking the grey dot puts the copy back",
        p.options["suppressed"] == [],
        p.options["suppressed"],
    )
    h.check("three holes again", centres() == [(8, 8), (20, 8), (32, 8)], centres())
    tick(p.suppression)


def unticked():
    p = ps.panel()
    h.check("Suppression off: no dots", not p.suppression.isChecked() and p.dots is None)
    h.task_button("OK")


def after_edit():
    found = ps.patterns()
    h.check("still one pattern", len(found) == 1)
    h.check(
        "without suppression it is FreeCAD's LinearPattern again",
        found and found[0].TypeId == "PartDesign::LinearPattern",
        found and found[0].TypeId,
    )
    h.check("3 holes", ps.close(h.solid_volume(), ps.BOX - 3 * HOLE))
    s["v"] = h.solid_volume()


def circ_start():
    Gui.Selection.clearSelection()
    ps.menu("Circular Pattern")


def circ_pick():
    ps.timeline_click("Extrude 2")


def circ_box():
    ps.click_box("axis")


def circ_axis():
    h.fit()
    # The Z axis above the box's front-left corner area: the hole (8, 8) turns about it.
    h.click(V(0, 0, 18))


def circ_tick():
    p = ps.panel()
    h.check("Z axis picked", p and p.options["axis"] and p.options["axis"][0].Role == "Z_Axis")
    tick(p.suppression)


def circ_dot():
    p = ps.panel()
    h.check("dots on the 2 copies", p.dots is not None and len(p.dots.points) == 2)
    if p.dots is not None:
        h.fit()
        h.click(p.dots.points[1])


def circ_cancel():
    p = ps.panel()
    h.check("copy 1 left out", p and p.options["suppressed"] == [1], p and p.options["suppressed"])
    h.task_button("Cancel")


def circ_after():
    h.check("Cancel: unchanged", ps.close(h.solid_volume(), s["v"]) and len(ps.patterns()) == 1)
    h.check("closed", not Gui.Control.activeDialog())


h.run(
    "patterns_suppress",
    b.box_steps("PatternSuppress")
    + ps.make_cut("hole", (8, 8), R)
    + [
        start,
        pick,
        box,
        axis,
        quantity,
        distance,
        three,
        dots_shown,
        click_middle_dot,
        suppressed,
        after_ok,
        after_undo,
        after_redo,
        edit,
        edit_open,
        back_in,
        unticked,
        after_edit,
        circ_start,
        circ_pick,
        circ_box,
        circ_axis,
        circ_tick,
        circ_dot,
        circ_cancel,
        circ_after,
    ],
)
