# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole > From Sketch (multiple holes), only real input:

1. A 40 x 30 x 10 box; a sketch on its top face with two points and a circle.
2. H, Placement From Sketch: click the first point (a hole), the second (two), the circle
   (three, at its centre), the second point again (dropped). Extents All, diameter 3.
3. OK: the sketch is hidden (Fusion hides a used sketch). Ctrl+Z / Ctrl+Y.
4. Edit from the timeline: click the dropped point again (three holes). OK.
5. A sketch on the XY plane (under the part) with one point, selected in the browser, then
   H: From Sketch at once, and the hole is turned round to drill up into the part.
6. Esc in a new Hole dialog changes nothing.

Hand-derived: a through hole d removes pi d^2/4 * 10 from the 10 mm thick box.
"""

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
P1 = V(8, 8, 10)
P2 = V(32, 8, 10)
C = V(20, 22, 10)


def through(count, d=3.0):
    return hs.BOX - count * hs.cylinder(d, 10)


def sketch_on_top():
    h.fit()
    h.ribbon("Create Sketch")


def click_top():
    h.click(V(30, 20, 10))


def draw():
    sk = h.in_sketch()
    h.check("sketch open on the top face", sk is not None)
    if sk is None:
        return
    s["sketch"] = sk.Name
    for p in (P1, P2):
        x, y = h.to_sketch(sk, p)
        sk.addGeometry(Part.Point(V(x, y, 0)))
    x, y = h.to_sketch(sk, C)
    h.draw_circle(sk, x, y, 2)
    App.ActiveDocument.recompute()


def finish():
    h.ribbon("Finish Sketch")


def ribbon_hole():
    h.fit()
    Gui.Selection.clearSelection()
    h.ribbon("Hole")


def from_sketch():
    p = hs.hole_panel()
    h.check("Hole dialog open", p is not None)
    if p:
        b.choose(p.placement, "From Sketch (Multiple Holes)")


def options():
    p = hs.hole_panel()
    h.check("Sketch Points box is active", p and p.fields["points"].button.isChecked())
    h.check("no Face / Reference boxes", p and not p.fields["face"].widget.isVisible())
    if p:
        b.choose(p.extent, "All")
        hs.type_into(p.diameter.widget, "3")


def click_p1():
    h.click(P1)


def one():
    p = hs.hole_panel()
    h.check(
        "one hole at the first point",
        p and p.target is not None and len(hs.centres_all(p.target)) == 1,
        hs.message(p),
    )
    v = h.solid_volume()
    h.check("through hole d3", hs.close(v, through(1)), (v, through(1)))
    h.check("drills down into the part", p and p.target and not p.target.Reversed)


def click_p2():
    h.click(P2)


def two():
    v = h.solid_volume()
    h.check("two holes", hs.close(v, through(2)), (v, through(2)))


def click_circle():
    h.click_edge(C + V(2, 0, 0))


def three():
    p = hs.hole_panel()
    v = h.solid_volume()
    h.check("three holes (one at the circle's centre)", hs.close(v, through(3)), (v, through(3)))
    centres = hs.centres_all(p.target) if p and p.target else []
    h.check("a hole at the circle's centre", any(hs.vnear(c, C) for c in centres), centres)
    h.shot("1-three")


def click_p2_again():
    h.click(P2)


def dropped():
    v = h.solid_volume()
    h.check("clicking a picked point drops it", hs.close(v, through(2)), (v, through(2)))
    p = hs.hole_panel()
    h.check(
        "box says 2 point(s)",
        p and p.fields["points"].button.text() == "2 point(s)",
        p and p.fields["points"].button.text(),
    )


def ok():
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("two holes made", hs.close(h.solid_volume(), through(2)), h.solid_volume())
    sk = App.ActiveDocument.getObject(s.get("sketch", ""))
    h.check("the used sketch is hidden", sk is not None and not hs.visible(sk))
    h.check("one Hole feature", len(hs.holes()) == 1, hs.holes())
    h.check("no helper sketch for a From Sketch hole", not hs.helper_sketches())
    h.check("valid solid", h.body().Shape.isValid())
    h.shot("2-two")


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check("Ctrl+Z removes the holes", hs.close(h.solid_volume(), hs.BOX) and not hs.holes())


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check("Ctrl+Y brings them back", hs.close(h.solid_volume(), through(2)))


def edit():
    b.timeline_double_click("Hole 1")


def edit_open():
    p = hs.hole_panel()
    h.check("editing the hole", p is not None and p.editing)
    h.check("placement shown as From Sketch", p and p.placement.currentText().startswith("From"))
    h.check("the sketch shows again to pick from", p and hs.visible(p.sketch))
    h.fit()


def click_p2_edit():
    h.click(P2)


def edited():
    v = h.solid_volume()
    h.check("the point added back while editing", hs.close(v, through(3)), (v, through(3)))
    h.task_button("OK")


def after_edit():
    h.check("three holes kept", hs.close(h.solid_volume(), through(3)), h.solid_volume())
    sk = App.ActiveDocument.getObject(s.get("sketch", ""))
    h.check("the sketch is hidden again", sk is not None and not hs.visible(sk))
    s["v"] = h.solid_volume()


def sketch_below():
    """A sketch on XY (under the part) with one point, made like the others."""
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))  # the XY square in front of the part, nothing else in the way


def point_below():
    sk = h.in_sketch()
    h.check(
        "sketch on XY open",
        sk is not None
        and hs.vnear(sk.getGlobalPlacement().Rotation.multVec(V(0, 0, 1)), V(0, 0, 1)),
    )
    if sk is None:
        return
    s["below"] = sk.Name
    sk.addGeometry(Part.Point(V(20, 15, 0)))
    App.ActiveDocument.recompute()


def finish_below():
    h.ribbon("Finish Sketch")


def select_in_browser():
    t = hs.browser()
    sk = App.ActiveDocument.getObject(s.get("below", ""))
    item = t.row(sk.Label) if sk is not None else None
    h.check("the sketch is in the browser", item is not None, t.labels())
    if item is not None:
        w.click(t.viewport(), t.label_point(item))


def press_h():
    sel = [x.ObjectName for x in Gui.Selection.getSelectionEx()]
    h.check("sketch selected before H", sel == [s.get("below")], sel)
    h.press("h")


def started_from_sketch():
    p = hs.hole_panel()
    h.check(
        "H with a sketch selected starts From Sketch with its point",
        p is not None and p.target is not None and p.placement.currentText().startswith("From"),
        hs.message(p),
    )
    h.check(
        "the hole is turned round to drill up into the part",
        p and p.target and p.target.Reversed and p.flip.isChecked(),
    )
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(3, 10)
    h.check("a through hole from below", hs.close(v, expect), (v, expect))
    h.shot("3-from-below")
    h.task_button("OK")


def after_second():
    h.check("two Hole features", len(hs.holes()) == 2, hs.holes())
    h.check("valid solid", h.body().Shape.isValid())
    s["v"] = h.solid_volume()


def esc_start():
    h.press("h")


def esc_click():
    h.fit()
    h.click(V(30, 25, 10))


def esc():
    p = hs.hole_panel()
    h.check("a preview before Esc", p is not None and p.target is not None, hs.message(p))
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closed the dialog", not Gui.Control.activeDialog())
    h.check("Esc changed nothing", hs.close(h.solid_volume(), s["v"]))
    h.check("still two holes", len(hs.holes()) == 2)
    h.check("no kernel errors in the Report view", not b.report_has_kernel_errors())
    hs.no_popups("From Sketch holes")


h.run(
    "hole_sketch",
    b.box_steps("HoleSketch")
    + [
        sketch_on_top,
        click_top,
        draw,
        finish,
        ribbon_hole,
        from_sketch,
        options,
        click_p1,
        one,
        click_p2,
        two,
        click_circle,
        three,
        click_p2_again,
        dropped,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_open,
        click_p2_edit,
        edited,
        after_edit,
        sketch_below,
        pick_xy,
        point_below,
        finish_below,
        select_in_browser,
        press_h,
        started_from_sketch,
        after_second,
        esc_start,
        esc_click,
        esc,
        after_esc,
    ],
)
