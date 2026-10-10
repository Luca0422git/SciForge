# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole and Thread in the odd moments of a real session, only real input:

1. An empty design: H and CREATE > Thread open their dialogs, say a solid is needed, a click
   on the empty view does nothing; Esc. No error anywhere.
2. A box: H, click the top face (a preview), then Ctrl+Z with the dialog still open: the
   dialog ends and the unfinished hole goes; Ctrl+Y brings it back as a normal step.
3. A second body (a block made with New Body): clicking its face in the Hole dialog drills the
   hole in that body, which becomes the active one.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}


def empty_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Empty")
    h.fit()
    h.press("h")


def hole_needs_solid():
    p = hs.hole_panel()
    h.check("Hole dialog opens in an empty design", p is not None)
    h.check("it says a solid is needed", "solid" in hs.message(p).lower(), hs.message(p))
    hs.no_popups("Hole in an empty design")
    h.click_empty()


def esc_hole():
    h.check(
        "nothing was made",
        not App.ActiveDocument.Objects,
        [o.Name for o in App.ActiveDocument.Objects],
    )
    h.press(QtCore.Qt.Key_Escape)


def thread_empty():
    h.check("Esc closed the Hole dialog", not Gui.Control.activeDialog())
    si.menu_item("CREATE", "Thread")


def thread_needs_solid():
    p = hs.thread_panel()
    h.check("Thread dialog opens in an empty design", p is not None)
    h.check("it says a solid is needed", "solid" in hs.message(p).lower(), hs.message(p))
    hs.no_popups("Thread in an empty design")
    h.press(QtCore.Qt.Key_Escape)


def after_empty():
    h.check("Esc closed the Thread dialog", not Gui.Control.activeDialog())
    App.closeDocument(App.ActiveDocument.Name)


def start_hole():
    h.fit()
    s["v"] = h.solid_volume()
    h.ribbon("Hole")


def click_top():
    h.click(V(20, 15, 10))


def undo_inside():
    p = hs.hole_panel()
    h.check("a hole is previewed", p is not None and p.target is not None, hs.message(p))
    h.check("the preview cuts the box", not hs.close(h.solid_volume(), s["v"]))
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo_inside():
    h.check(
        "Ctrl+Z inside the dialog ends it",
        hs.hole_panel() is None and not Gui.Control.activeDialog(),
    )
    h.check(
        "and takes the unfinished hole away (with its sketch)",
        hs.close(h.solid_volume(), s["v"]) and not hs.holes() and not hs.helper_sketches(),
        (h.solid_volume(), hs.holes(), hs.helper_sketches()),
    )
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    hl = hs.holes()
    h.check("Ctrl+Y brings the hole back as a step", len(hl) == 1, hl)
    h.check(
        "a valid solid with the hole",
        h.body().Shape.isValid() and h.solid_volume() < s["v"] - 1.0,
        h.solid_volume(),
    )
    h.check("its sketch is hidden", all(not hs.visible(x) for x in hs.helper_sketches()))
    s["v"] = h.solid_volume()
    s["body1"] = h.body().Name


def block_sketch():
    """A block next to the box, in a new body (Create Sketch on XY, E, New Body)."""
    h.fit()
    h.ribbon("Create Sketch")


def block_plane():
    h.click(V(12, -8, 0))


def block_draw():
    sk = h.in_sketch()
    h.check("sketch open", sk is not None)
    if sk:
        h.draw_rectangle(sk, 50, 0, 70, 20)


def block_finish():
    h.ribbon("Finish Sketch")


def block_extrude():
    h.fit()
    h.press("e")


def block_options():
    p = b.active_panel()
    if p is not None:
        b.type_into(p.distance.widget, "8")
        b.choose(p.operation, "New Body")


def block_ok():
    h.task_button("OK")


def two_bodies():
    bodies = App.ActiveDocument.findObjects("PartDesign::Body")
    h.check("two bodies", len(bodies) == 2, bodies)
    s["body2"] = [x.Name for x in bodies if x.Name != s["body1"]][0] if len(bodies) == 2 else ""
    # The box's body is the active one again (as after editing it).
    body1 = App.ActiveDocument.getObject(s["body1"])
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body1)
    h.fit()


def hole_on_block():
    h.press("h")


def click_block():
    h.click(V(60, 10, 8))


def drilled_in_block():
    p = hs.hole_panel()
    body2 = App.ActiveDocument.getObject(s.get("body2", ""))
    h.check(
        "the hole goes into the block's body",
        p is not None and p.target is not None and p.body is body2,
        hs.message(p),
    )
    h.check("that body is active now", h.body() is body2)
    h.check(
        "the box is unchanged",
        hs.close(App.ActiveDocument.getObject(s["body1"]).Shape.Volume, s["v"]),
    )
    if p:
        hs.type_into(p.pos_x.widget, "60")
        hs.type_into(p.pos_y.widget, "10")
        b.choose(p.drill_point, "Flat")
        hs.type_into(p.depth.widget, "4")


def block_ok2():
    h.task_button("OK")


def after_block():
    body2 = App.ActiveDocument.getObject(s.get("body2", ""))
    v = body2.Shape.Volume if body2 else 0
    expect = 20 * 20 * 8 - hs.cylinder(5, 4)
    h.check("hole d5 x 4 in the block", hs.close(v, expect), (v, expect))
    h.check("no kernel errors in the Report view", not b.report_has_kernel_errors())
    hs.no_popups("holes in two bodies")


h.run(
    "hole_edges",
    [
        empty_design,
        hole_needs_solid,
        esc_hole,
        thread_empty,
        thread_needs_solid,
        after_empty,
    ]
    + b.box_steps("HoleEdges")
    + [
        start_hole,
        click_top,
        undo_inside,
        after_undo_inside,
        after_redo,
        block_sketch,
        block_plane,
        block_draw,
        block_finish,
        block_extrude,
        block_options,
        block_ok,
        two_bodies,
        hole_on_block,
        click_block,
        drilled_in_block,
        block_ok2,
        after_block,
    ],
)
