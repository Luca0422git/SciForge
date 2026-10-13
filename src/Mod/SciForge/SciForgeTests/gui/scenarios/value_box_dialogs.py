# SPDX-License-Identifier: LGPL-2.1-or-later
"""Every dialog's drag handle has a value box next to it, like Extrude's (Fusion shows the
value beside every manipulator). Hole, Fillet, Shell and Thread on one 40 x 30 x 10 box,
only real input. For each dialog's box: it shows exactly the dialog field's text (units),
it follows the handle when the view is panned, it never covers the handle's grabbable part
(the pixels of the handle belong to the 3D view), a value typed in it and a click away
sets the field, and Cancel removes it.

Hand-derived: hole d5 x 6 flat-less = 12000 - pi * 2.5^2 * 6 - tip cone; fillet r3 on a
40 mm edge removes 40 * 9 * (1 - pi/4); shell 3 mm with the top open leaves
12000 - 34 * 24 * 7; a boss d6 x 12 adds pi * 9 * 12.
"""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}
PAN = -80


def panel():
    from sciforge import taskui

    return taskui.current()


def near(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


def check_box(what, key, field, handle):
    """The common checks of one dialog's value box. Returns the box (or None)."""
    p = panel()
    box = a.value_box(key, p)
    if not h.check("%s: a value box next to its handle" % what, box is not None and box.isVisible(),
                   (key, p and sorted(p.value_boxes.boxes))):
        return None
    h.check("%s: the box shows the field's text" % what, box.text() == field.widget.text(),
            (box.text(), field.widget.text()))
    h.check("%s: with units" % what, box.text().strip()[-1:].isalpha(), box.text())
    h.check("%s: the box does not have the keyboard" % what, not box.hasFocus(), a.focus_name())
    anchor, tail, tip, _radius = handle.box_geometry()
    for name, point in (("tail", tail), ("middle", anchor), ("tip", tip)):
        pos = h.screen_point(point)
        h.check("%s: the box is not over the handle's %s" % (what, name),
                a.top_name(pos) != a.BOX_NAME, (pos.x(), pos.y(), a.top_name(pos)))
    s["box_x"] = box.pos().x()
    s["box"] = box
    return box


def pan_view():
    h.pan(PAN, 0)


def box_followed(what):
    box = s.get("box")
    moved = box.pos().x() - s["box_x"] if box is not None else None
    h.check("%s: the box follows the handle when the view pans" % what,
            moved is not None and abs(moved - PAN) <= 25, (moved, PAN))


def type_in_box(text, field):
    """Type in the box, then click the dialog's field: the click only leaves the box."""
    box = s.get("box")
    if box is None:
        return
    a.type_in_box(box, text, enter=False)
    h.check("the box has the keyboard while typing", box.hasFocus(), a.focus_name())
    b.click_widget(field.widget)


def gone(what):
    h.check("%s: Cancel closed the dialog" % what, panel() is None and not Gui.Control.activeDialog())
    h.check("%s: no value box left" % what, not a.value_boxes(visible_only=False),
            len(a.value_boxes(visible_only=False)))


# -- Hole ------------------------------------------------------------------------------------
def hole_open():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Hole")


def hole_click_top():
    h.click(V(12, 8, 10))


def hole_box():
    p = hs.hole_panel()
    h.check("Hole: a hole is previewed with a depth arrow", p is not None and "depth" in p.draggers)
    if p is None or "depth" not in p.draggers:
        return
    check_box("Hole", "depth", p.depth, p.draggers["depth"])
    pan_view()


def hole_typed():
    p = hs.hole_panel()
    box_followed("Hole")
    if p is not None:
        type_in_box("6", p.depth)


def hole_six():
    p = hs.hole_panel()
    h.check("Hole: 6 typed in the box is the depth", p is not None and near(p.depth.value(), 6.0),
            p and p.depth.value())
    v = h.solid_volume()
    expect = hs.BOX - hs.cylinder(5, 6) - hs.tip_cone(5)
    h.check("Hole: the part follows (d5 x 6)", hs.close(v, expect), (v, expect))
    h.task_button("Cancel")


def hole_gone():
    gone("Hole")


# -- Fillet ------------------------------------------------------------------------------------
def fillet_open():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Fillet")


def fillet_click_edge():
    h.click_edge(V(20, 0, 10))  # the front-top edge


def fillet_box():
    p = b.blend_panel()
    h.check("Fillet: one arrow", p is not None and len(p.arrows) == 1, p and len(p.arrows))
    if p is None or not p.arrows:
        return
    check_box("Fillet", "radius#0", p.radius, p.arrows[0][0])
    pan_view()


def fillet_typed():
    p = b.blend_panel()
    box_followed("Fillet")
    if p is not None:
        type_in_box("3", p.radius)


def fillet_three():
    p = b.blend_panel()
    h.check("Fillet: 3 typed in the box is the radius", p is not None and near(p.radius.value(), 3.0),
            p and p.radius.value())
    v = h.solid_volume()
    h.check("Fillet: the part follows (r3)", b.close(v, b.BOX - 40 * b.spandrel(3)), v)
    h.task_button("Cancel")


def fillet_gone():
    gone("Fillet")


# -- Shell ------------------------------------------------------------------------------------
def shell_open():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Shell")


def shell_click_top():
    h.click(V(20, 15, 10))


def shell_box():
    p = sd.shell_panel()
    h.check("Shell: the top is picked, one arrow", p is not None and len(p.arrows) == 1,
            p and len(p.arrows))
    if p is None or not p.arrows:
        return
    check_box("Shell", "inside#0", p.inside, p.arrows[0][0])
    pan_view()


def shell_typed():
    p = sd.shell_panel()
    box_followed("Shell")
    if p is not None:
        type_in_box("3", p.inside)


def shell_three():
    p = sd.shell_panel()
    h.check("Shell: 3 typed in the box is the thickness",
            p is not None and near(p.inside.value(), 3.0), p and p.inside.value())
    v = h.solid_volume()
    h.check("Shell: the part follows (3 mm walls)", sd.close(v, sd.open_top(3)), (v, sd.open_top(3)))
    h.task_button("Cancel")


def shell_gone():
    gone("Shell")


# -- Thread (on a boss) ------------------------------------------------------------------------
def thread_open():
    Gui.Selection.clearSelection()
    h.fit()
    si.menu_item("CREATE", "Thread")


def thread_click_side():
    import math

    h.click(V(20 + 3 * math.cos(math.radians(-45)), 15 + 3 * math.sin(math.radians(-45)), 19))


def thread_untick_full():
    p = hs.thread_panel()
    h.check("Thread: a thread is previewed", p is not None and p.target is not None, hs.message(p))
    if p is not None:
        hs.click_checkbox(p.full_length)


thread_untick_full.wait_ms = 2000


def thread_box():
    p = hs.thread_panel()
    h.check("Thread: the length arrow is there", p is not None and "length" in p.draggers,
            p and list(p.draggers))
    if p is None or "length" not in p.draggers:
        return
    check_box("Thread", "length", p.length, p.draggers["length"])
    pan_view()


def thread_typed():
    p = hs.thread_panel()
    box_followed("Thread")
    if p is not None:
        type_in_box("5", p.length)


thread_typed.wait_ms = 2000


def thread_five():
    p = hs.thread_panel()
    h.check("Thread: 5 typed in the box is the length", p is not None and near(p.length.value(), 5.0),
            p and p.length.value())
    h.task_button("Cancel")


def thread_gone():
    gone("Thread")


h.run(
    "value_box_dialogs",
    b.box_steps("ValueBoxDialogs")
    + [
        hole_open,
        hole_click_top,
        hole_box,
        hole_typed,
        hole_six,
        hole_gone,
        fillet_open,
        fillet_click_edge,
        fillet_box,
        fillet_typed,
        fillet_three,
        fillet_gone,
        shell_open,
        shell_click_top,
        shell_box,
        shell_typed,
        shell_three,
        shell_gone,
    ]
    + hs.make_boss("boss")
    + [
        thread_open,
        thread_click_side,
        thread_untick_full,
        thread_box,
        thread_typed,
        thread_five,
        thread_gone,
    ],
)
