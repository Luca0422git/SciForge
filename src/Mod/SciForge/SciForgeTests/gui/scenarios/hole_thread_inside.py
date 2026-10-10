# SPDX-License-Identifier: LGPL-2.1-or-later
"""A hole on a curved face and an inside thread, only real input:

1. A 40 x 30 x 10 box with a boss d6 x 12 on top.
2. H, click the boss's side: the hole goes in square to the surface where it was clicked
   (d2, depth 3, flat). OK.
3. H, a d5 through hole in the top face at (8, 8). OK.
4. Click the wall of that hole, then CREATE > Thread: an inside thread M6x1 (6H) starts on
   it at once, cosmetic; Modeled cuts it. OK, Ctrl+Z, Ctrl+Y.

Hand-derived:
  the radial hole starts on the plane touching the boss (R 3) at the click, so it removes
  pi a^2 t minus the sliver between that plane and the round surface:
  integral over the hole's disc of (R - sqrt(R^2 - u^2)), u across the boss (a = 1, t = 3);
  the inside thread removes (2 pi / P) * integral of r w(r) dr per mm (thread_core) over the
  plate's 10 mm.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}
BOSS = hs.BOX + math.pi * 9.0 * 12.0
ANGLE = math.radians(-45)
SIDE = V(20 + 3 * math.cos(ANGLE), 15 + 3 * math.sin(ANGLE), 16)
WALL_ANGLE = math.radians(135)
WALL = V(8 + 2.5 * math.cos(WALL_ANGLE), 8 + 2.5 * math.sin(WALL_ANGLE), 9.0)


def radial_hole_volume(a=1.0, t=3.0, R=3.0, n=20000):
    """pi a^2 t minus the sliver between the touching plane and the boss (Simpson's rule)."""

    def f(u):
        return 2.0 * math.sqrt(max(a * a - u * u, 0.0)) * (R - math.sqrt(R * R - u * u))

    hstep = 2.0 * a / n
    total = f(-a) + f(a)
    for i in range(1, n):
        total += (4 if i % 2 else 2) * f(-a + i * hstep)
    return math.pi * a * a * t - total * hstep / 3.0


def inside_removed():
    from sciforge import thread_core

    return thread_core.removed_volume(3.0, 1.0, True, 2.5, 10.0)


def hole_on_boss():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Hole")


def click_boss_side():
    h.click(SIDE)


def radial():
    p = hs.hole_panel()
    h.check("a hole on the round face", p is not None and p.target is not None, hs.message(p))
    if p is None or p.target is None:
        return
    d = hs.centres_dir(p.target)
    radial_in = V(-math.cos(ANGLE), -math.sin(ANGLE), 0)
    h.check(
        "drilled square to the surface (towards the boss's axis)",
        d is not None and hs.vnear(d, radial_in, 1e-3),
        d,
    )
    hs.type_into(p.diameter.widget, "2")
    hs.type_into(p.depth.widget, "3")
    b.choose(p.drill_point, "Flat")


def radial_made():
    v = h.solid_volume()
    expect = BOSS - radial_hole_volume()
    h.check("radial hole d2 x 3 into the boss", hs.close(v, expect, 1e-6), (v, expect))
    p = hs.hole_panel()
    h.check(
        "no X / Y on a curved face (the dot moves the hole on it)",
        p and not p.pos_x.widget.isVisible(),
    )
    h.shot("1-radial")
    dot = p.draggers.get("centre") if p else None
    if dot is None:
        h.check("centre point to drag", False)
        return
    s["start"] = hs.centre_of(p.target)
    start = dot.point()
    h.drag(h.screen_point(start), h.screen_point(start + V(0, 0, 2)))


def radial_dragged():
    p = hs.hole_panel()
    c = hs.centre_of(p.target) if p else None
    h.check(
        "dragging the dot up the boss moves the hole up",
        c is not None and c.z > s["start"].z + 1.0,
        (s["start"], c),
    )
    radial_in = V(-math.cos(ANGLE), -math.sin(ANGLE), 0)
    h.check(
        "still square to the round face",
        hs.vnear(hs.centres_dir(p.target), radial_in, 1e-6) if p else False,
        p and hs.centres_dir(p.target),
    )
    h.check(
        "still on the face", c is not None and abs(math.hypot(c.x - 20, c.y - 15) - 3) < 1e-6, c
    )
    v = h.solid_volume()
    expect = BOSS - radial_hole_volume()
    h.check("the same radial hole further up", hs.close(v, expect, 1e-6), (v, expect))
    h.task_button("OK")


def after_radial():
    h.check("radial hole kept", hs.close(h.solid_volume(), BOSS - radial_hole_volume()))
    s["v"] = h.solid_volume()


def through_hole():
    h.fit()
    h.press("h")


def click_plate():
    h.click(V(8, 8, 10))


def through_options():
    p = hs.hole_panel()
    h.check("second hole placed", p is not None and p.target is not None, hs.message(p))
    if p is None:
        return
    hs.type_into(p.pos_x.widget, "8")
    hs.type_into(p.pos_y.widget, "8")
    hs.type_into(p.diameter.widget, "5")
    b.choose(p.extent, "All")


def through_ok():
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(5, 10)
    h.check("through hole d5", hs.close(v, expect), (v, expect))
    h.task_button("OK")


def after_through():
    s["v"] = h.solid_volume()
    h.fit()


def click_wall():
    h.click(WALL)


def thread_menu():
    sel = [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]
    h.check("the hole's wall is selected", len(sel) == 1 and len(sel[0][1]) == 1, sel)
    si.menu_item("CREATE", "Thread")


def inside():
    p = hs.thread_panel()
    h.check(
        "Thread starts on the selected wall",
        p is not None and p.target is not None and len(p.faces) == 1,
        hs.message(p),
    )
    if p is None:
        return
    h.check("an inside thread", "Inside" in p.info.text(), p.info.text())
    h.check(
        "size from the tap drill: M6x1",
        p.designation.currentText() == "M6x1",
        p.designation.currentText(),
    )
    h.check(
        "inside thread class 6H", p.thread_class.currentText() == "6H", p.thread_class.currentText()
    )
    h.check("cosmetic: nothing cut", hs.close(h.solid_volume(), s["v"]))
    hs.click_checkbox(p.modeled)


inside.wait_ms = 3000  # FreeCAD blocks input while the thread is modeled


def modeled():
    v = h.solid_volume()
    expect = s["v"] - inside_removed()
    h.check("modeled inside M6x1 through 10 mm", hs.close(v, expect), (v, expect))
    h.check("valid solid", h.body().Shape.isValid())
    h.shot("2-inside")
    h.task_button("OK")


modeled.wait_ms = 1500


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("thread kept", hs.close(h.solid_volume(), s["v"] - inside_removed()))
    h.check("Thread 1 in the timeline", "Thread 1" in hs.timeline_titles(), hs.timeline_titles())


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


undo.wait_ms = 1500


def after_undo():
    h.check("Ctrl+Z removes the thread", hs.close(h.solid_volume(), s["v"]) and not hs.threads())


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


redo.wait_ms = 3000


def after_redo():
    h.check(
        "Ctrl+Y brings it back",
        hs.close(h.solid_volume(), s["v"] - inside_removed()) and len(hs.threads()) == 1,
        h.solid_volume(),
    )
    h.check("no kernel errors in the Report view", not b.report_has_kernel_errors())
    hs.no_popups("the inside thread")


h.run(
    "hole_thread_inside",
    b.box_steps("ThreadInside")
    + hs.make_boss("boss", radius=3.0, height=12.0)
    + [
        hole_on_boss,
        click_boss_side,
        radial,
        radial_made,
        radial_dragged,
        after_radial,
        through_hole,
        click_plate,
        through_options,
        through_ok,
        after_through,
        click_wall,
        thread_menu,
        inside,
        modeled,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
    ],
)
