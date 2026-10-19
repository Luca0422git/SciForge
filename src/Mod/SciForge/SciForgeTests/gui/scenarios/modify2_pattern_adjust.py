# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rectangular Pattern with Compute Option Adjust (Fusion: every copy is computed again where
it lands), only real input, every copy measured.

Part: a wedge, 60 long, 20 wide, 10 high at x = 0 and 20 high at x = 60 (Create Sketch on
the XZ plane, the side outline, E, Symmetric 10); its top is the slope z = 10 + x / 6. A hole
r 3 at x = 10 cut from the bottom face up To Object the slope (the part turned over to reach
the bottom: Create Sketch on it, a circle, E, Cut, To Object, click the slope).

Path A1, CREATE > Pattern > Rectangular Pattern with nothing selected: the hole's step clicked
        in the timeline, the X axis as the direction, Quantity 3, Distance 40: copies at x = 30
        and 50. Compute Option lists Optimized (chosen, Fusion's default), Identical, Adjust.
        Optimized: every copy is the same hole as the first, so it stops 20/6 and 40/6 mm under
        the slope (blind holes).
Path A2, Compute Option Adjust: every copy goes up to the slope where it lands: three
        through holes. OK; the timeline shows one pattern step.
Path A3, Ctrl+Z: one hole; Ctrl+Y: the three through holes again.
Path A4, the pattern edited from the timeline: it reads Adjust; Identical is chosen: the blind
        holes again in the preview; Cancel: still Adjust.
Path A5, save, close, open again: still three through holes, the pattern still Adjust.

Hand-derived (r = 3, area 9 pi): wedge 900 x 20 = 18000. A hole from z = 0 up to the slope at
x holds 9 pi z(x) (a cylinder cut by a slanted plane holds its area times the height at its
axis): z(10) = 35/3, z(30) = 15, z(50) = 55/3. Optimized / Identical: three copies of the first
hole: 3 x 9 pi 35/3 = 315 pi; Adjust: 9 pi (35/3 + 15 + 55/3) = 405 pi. Material left inside
a copy's cylinder: Adjust 0; Identical 9 pi (z(x) - 35/3): 0, 30 pi, 60 pi.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import modify2_steps as m
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
s = {}
WEDGE = 18000.0
HOLE = 9.0 * math.pi
XS = (10.0, 30.0, 50.0)


def slope(x):
    return 10.0 + x / 6.0


def left_in(x, shape=None):
    """Material of the part inside the hole's cylinder at x (0 for a through hole)."""
    shape = shape if shape is not None else h.body().Shape
    tool = Part.makeCylinder(3.0, 40.0, V(x, 0, -5), V(0, 0, 1))
    return shape.common(tool).Volume


def copies(shape=None):
    return [round(left_in(x, shape), 4) for x in XS]


def same(values, want, tol=1e-4):
    return len(values) == len(want) and all(abs(a - b) <= tol for a, b in zip(values, want))


IDENTICAL = WEDGE - 3 * HOLE * 35.0 / 3.0
ADJUST = WEDGE - HOLE * (slope(10) + slope(30) + slope(50))
LEFT_IDENTICAL = [0.0, HOLE * (slope(30) - slope(10)), HOLE * (slope(50) - slope(10))]


def panel():
    return ps.panel()


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return None if p is None or getattr(p, "_closed", False) else p


# -- the wedge ------------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Modify2Adjust")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    pl.click_square("XZ_Plane")  # where the square shows (was 6, 0, 5)


def draw_wedge():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None)
    if sk is None:
        return
    corners = [V(0, 0, 0), V(60, 0, 0), V(60, 0, 20), V(0, 0, 10)]
    pts = [V(*h.to_sketch(sk, c), 0) for c in corners]
    first = sk.GeometryCount
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", first + i, 2, first + (i + 1) % 4, 1))
    App.ActiveDocument.recompute()


def finish_wedge():
    h.ribbon("Finish Sketch")


def extrude_wedge():
    h.fit()
    h.press("e")


def wedge_symmetric():
    p = xpanel()
    if h.check("Extrude open on the outline", p is not None):
        h.check("choose Direction: Symmetric", ui.choose(p.direction, "Symmetric"))
        ui.type_into(p.distance.widget, "10")


def wedge_ok():
    h.task_button("OK")


def wedge_made():
    v = h.solid_volume()
    h.check("wedge 900 x 20", m.close(v, WEDGE), v)
    box = h.body().Shape.BoundBox
    h.check("from y = -10 to 10", abs(box.YMin + 10) < 1e-6 and abs(box.YMax - 10) < 1e-6, box)


# -- the hole -------------------------------------------------------------------------------------
def hole_sketch():
    Gui.Selection.clearSelection()
    h.view().viewBottom()  # the person turns the part over to reach its bottom
    h.view().fitAll()
    h.ribbon("Create Sketch")


def click_bottom():
    pl.click_on_plane(V(40, 3, 0))


def draw_hole():
    sk = h.in_sketch()
    h.check("sketch open on the bottom", sk is not None)
    if sk is None:
        return
    x, y = h.to_sketch(sk, V(10, 0, 0))
    h.draw_circle(sk, x, y, 3)


def finish_hole():
    h.ribbon("Finish Sketch")


def extrude_hole():
    h.fit()
    h.press("e")


def hole_options():
    p = xpanel()
    if not h.check("Extrude open on the circle", p is not None):
        return
    h.check("choose Operation: Cut", ui.choose(p.operation, "Cut"))
    h.check("choose Extent: To Object", ui.choose(p.extent, "To Object"))


def click_slope():
    h.fit()
    h.click(V(40, 4, slope(40)))


def hole_preview():
    v = h.solid_volume()
    h.check("a hole up to the slope", m.close(v, WEDGE - HOLE * slope(10)), v)
    h.task_button("OK")


def hole_made():
    h.check("dialog closed", m.no_dialog())
    h.check("the hole goes through", abs(left_in(10.0)) < 1e-4, left_in(10.0))
    s["hole"] = h.solid_volume()


# -- A1 -------------------------------------------------------------------------------------------
def pattern_start():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.ribbon("Rectangular Pattern")


def click_hole_step():
    p = panel()
    h.check("Rectangular Pattern waits", p is not None and p.options["objects"] == [])
    ps.timeline_click("Extrude 2")


def click_direction_box():
    ps.click_box("direction")


def click_x_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def three():
    p = panel()
    if p is None:
        return
    h.check("the X axis is the direction", p.options["direction"] is not None, p.options)
    ps.type_quantity(p.quantity, 3)


def forty():
    ps.type_value(panel().distance_field.widget, "40")


def optimized():
    p = panel()
    if p is None:
        return
    labels = [p.compute.itemText(i) for i in range(p.compute.count())]
    h.check("Compute Option: Optimized, Identical, Adjust", labels == [x for x, _ in m_compute()])
    h.check("all three can be chosen", all(m.item_enabled(p.compute, x)[1] for x in labels))
    h.check("Optimized is Fusion's default", p.compute.currentText() == "Optimized")
    h.check("Compute Option shows", p.compute.isVisible())
    v = h.solid_volume()
    h.check("Optimized: three copies of the first hole", m.close(v, IDENTICAL), (v, IDENTICAL))
    left = copies()
    h.check("each copy measured: blind under the slope", same(left, LEFT_IDENTICAL), left)
    h.shot("1-optimized")
    h.check("choose Adjust", ui.choose(p.compute, "Adjust"))


def m_compute():
    from sciforge import pattern_ui

    return pattern_ui.COMPUTE


# -- A2 -------------------------------------------------------------------------------------------
def adjusted():
    p = panel()
    v = h.solid_volume()
    h.check("Adjust: every copy up to the slope", m.close(v, ADJUST), (v, ADJUST))
    left = copies()
    h.check("each copy measured: all three go through", same(left, [0.0, 0.0, 0.0]), left)
    h.check("no message", p is not None and not p.message.text(), p and p.message.text())
    h.shot("2-adjust")
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", m.no_dialog())
    found = ps.patterns()
    h.check("one pattern step", len(found) == 1, found)
    v = h.solid_volume()
    h.check("kept: three through holes", m.close(v, ADJUST), v)
    h.check("valid solid", h.body().Shape.isValid())
    titles = ps.timeline_titles()
    s["title"] = [t for t in titles if "Pattern" in t][-1:] or ["?"]
    h.check("the timeline shows the pattern", s["title"][0] != "?", titles)
    h.check("no errors in the Report view", not m_report_errors(), m_report_errors())


def m_report_errors():
    from SciForgeTests.gui import shell_draft_steps as sd

    return sd.report_errors()


# -- A3 -------------------------------------------------------------------------------------------
def undo():
    m.undo()


def after_undo():
    v = h.solid_volume()
    h.check("Ctrl+Z: only the first hole", m.close(v, s["hole"]), v)


def redo():
    m.redo()


def after_redo():
    v = h.solid_volume()
    h.check("Ctrl+Y: three through holes", m.close(v, ADJUST), v)
    h.fit()


# -- A4 -------------------------------------------------------------------------------------------
def edit():
    ps.timeline_double_click(s["title"][0])


def edit_open():
    p = panel()
    h.check("the pattern opens for editing", p is not None and p.editing)
    if p is None:
        return
    h.check("it reads Adjust", p.compute.currentText() == "Adjust", p.compute.currentText())
    h.check("choose Identical", ui.choose(p.compute, "Identical"))


def identical_preview():
    v = h.solid_volume()
    h.check("Identical: blind copies again", m.close(v, IDENTICAL), v)
    left = copies()
    h.check("each copy measured", same(left, LEFT_IDENTICAL), left)
    h.task_button("Cancel")


def after_cancel():
    h.check("dialog closed", m.no_dialog())
    v = h.solid_volume()
    h.check("Cancel: still Adjust", m.close(v, ADJUST), v)


# -- A5 -------------------------------------------------------------------------------------------
def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-modify2-"), "adjust.FCStd")
    s["path"] = path
    App.ActiveDocument.saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def close():
    App.closeDocument(App.ActiveDocument.Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    v = h.solid_volume()
    h.check("after reopening: three through holes", m.close(v, ADJUST), v)
    left = copies()
    h.check("each copy measured", same(left, [0.0, 0.0, 0.0]), left)
    ps.timeline_double_click(s["title"][0])


def reopened_edit():
    p = panel()
    h.check("the pattern opens for editing", p is not None and p.editing)
    h.check("still Adjust", p is not None and p.compute.currentText() == "Adjust")
    h.task_button("Cancel")


def end():
    h.check("dialog closed", m.no_dialog())
    h.check("no errors in the Report view", not m_report_errors(), m_report_errors())
    h.shot("3-end")


h.run(
    "modify2_pattern_adjust",
    [
        new_design,
        pick_xz,
        draw_wedge,
        finish_wedge,
        extrude_wedge,
        wedge_symmetric,
        wedge_ok,
        wedge_made,
        hole_sketch,
        click_bottom,
        draw_hole,
        finish_hole,
        extrude_hole,
        hole_options,
        click_slope,
        hole_preview,
        hole_made,
        pattern_start,
        click_hole_step,
        click_direction_box,
        click_x_axis,
        three,
        forty,
        optimized,
        adjusted,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_open,
        identical_preview,
        after_cancel,
        save,
        close,
        reopen,
        reopened,
        reopened_edit,
        end,
    ],
)
