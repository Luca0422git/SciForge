# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole Tap Types and Extents, only real input, on a 40 x 30 x 10 box:

1. H, click the top face, X 10 / Y 10. Hole Tap Type Tapped: the size comes from the
   diameter (M6x1, class 6H), the diameter becomes the tap drill (5).
2. Extents All: a through tapped hole, drawn as a cosmetic thread (dashed helix and the
   major diameter at the mouth).
3. Modeled: FreeCAD cuts the real thread. Checked on a 1 mm slab of the part, where every
   cross-section of a thread has the same area (see below).
4. Modeled off, Distance 8, Full Tap Depth off, Tap Depth 6.
5. Clearance: ISO 273 M6 Normal / Close / Loose = 6.6 / 6.4 / 7.0; ANSI 1/4 Normal is
   ASME B18.2.8's 0.281 in.
6. Extents To, click the XY origin plane in the browser: the hole ends on it. OK.
7. Edit from the timeline: To and the plane are shown; Cancel.

Hand-derived: FreeCAD's tapped-hole thread groove is P - 0.002 wide at R - 7H/8 + 0.001 tan 60
and P/8 wide at the major radius R (H = sqrt(3)/2 P). In a slice across the axis the groove
takes the fraction w(r)/P of each circle of radius r, so the slab of thickness 1 loses
pi r_drill^2 + (2 pi / P) * integral from r_drill to R of r w(r) dr.
"""
import math

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


def drawn():
    from sciforge import thread_ui

    return thread_ui.CosmeticThreads.count(App.ActiveDocument.Name)


def freecad_thread_slab(r_drill, major, pitch):
    """Area of a cross-section of the box taken by a modeled FreeCAD tapped hole."""
    hh = math.sqrt(3.0) / 2.0 * pitch
    r1 = major - 7.0 * hh / 8.0 + math.tan(math.radians(60.0)) * 0.001
    w1, w2 = pitch - 0.002, pitch / 8.0
    slope = (w2 - w1) / (major - r1)
    c0 = w1 - slope * r1

    def f(r):
        return c0 * r * r / 2.0 + slope * r**3 / 3.0

    return math.pi * r_drill**2 + 2.0 * math.pi / pitch * (f(major) - f(r_drill))


def ribbon_hole():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Hole")


def click_top():
    h.click(V(10, 10, 10))


def position():
    p = hs.hole_panel()
    h.check("hole placed", p is not None and p.target is not None, hs.message(p))
    if p:
        hs.type_into(p.pos_x.widget, "10")
        hs.type_into(p.pos_y.widget, "10")
        b.choose(p.drill_point, "Flat")


def tapped():
    p = hs.hole_panel()
    if p:
        b.choose(p.tap_type, "Tapped")


def tapped_fields():
    p = hs.hole_panel()
    if p is None:
        return
    h.check(
        "size from the diameter: M6x1",
        p.designation.currentText() == "M6x1",
        p.designation.currentText(),
    )
    h.check(
        "tapped hole class 6H", p.thread_class.currentText() == "6H", p.thread_class.currentText()
    )
    h.check(
        "the diameter is the tap drill (5)",
        abs(p.diameter.value() - 5.0) < 1e-9,
        p.diameter.value(),
    )
    h.check("the diameter is set by the size", not p.diameter.widget.isEnabled())
    h.check(
        "Modeled, Full Tap Depth, Class, Direction shown",
        hs.task_widgets_visible(p.modeled, p.full_tap, p.thread_class, p.direction),
    )
    h.check("Full Tap Depth is on", p.full_tap.isChecked())
    b.choose(p.extent, "All")


def through():
    v = h.solid_volume()
    expect = hs.BOX - hs.cylinder(5, 10)
    h.check("a through tapped hole: the tap drill", hs.close(v, expect), (v, expect))
    p = hs.hole_panel()
    h.check("the tip angle goes for a through hole", p and not p.drill_angle.widget.isVisible())
    h.check("the thread is drawn as a cosmetic thread", drawn() == 1, drawn())
    h.shot("1-cosmetic")
    if p:
        hs.click_checkbox(p.modeled)


through.wait_ms = 3000  # FreeCAD blocks input while it models the thread


def modeled():
    shape = h.body().Shape
    slab = shape.common(Part.makeBox(40, 30, 1, V(0, 0, 4))).Volume
    expect = 1200.0 - freecad_thread_slab(2.5, 3.0, 1.0)
    h.check("modeled M6x1: a 1 mm slab of the part", hs.close(slab, expect, 1e-5), (slab, expect))
    h.check("valid solid", shape.isValid())
    h.check("no cosmetic drawing for a modeled thread", drawn() == 0, drawn())
    h.shot("2-modeled")
    p = hs.hole_panel()
    if p:
        hs.click_checkbox(p.modeled)


modeled.wait_ms = 1500


def blind():
    p = hs.hole_panel()
    h.check("cosmetic again", drawn() == 1, drawn())
    if p:
        b.choose(p.extent, "Distance")
        hs.type_into(p.depth.widget, "8")
        hs.click_checkbox(p.full_tap)


def tap_depth():
    p = hs.hole_panel()
    h.check("Tap Depth shown once Full Tap Depth is off", p and p.tap_depth.widget.isVisible())
    if p:
        hs.type_into(p.tap_depth.widget, "6")


def tap_depth_set():
    p = hs.hole_panel()
    t = p.target if p else None
    h.check(
        "the thread is 6 deep in an 8 deep hole",
        t is not None and abs(t.ThreadDepth.Value - 6) < 1e-9 and abs(t.Depth.Value - 8) < 1e-9,
        t and (t.ThreadDepth, t.Depth),
    )
    v = h.solid_volume()
    expect = hs.BOX - hs.cylinder(5, 8)
    h.check("blind tapped hole d5 x 8", hs.close(v, expect), (v, expect))
    from sciforge import hole

    spots = hole.cosmetic_threads(t) if t is not None else []
    h.check(
        "the cosmetic thread is 6 long",
        len(spots) == 1 and abs(spots[0]["length"] - 6) < 1e-9,
        spots,
    )
    if p:
        b.choose(p.tap_type, "Clearance")


def clearance():
    p = hs.hole_panel()
    h.check("Fit shown, Class hidden", p and p.fit.isVisible() and not p.thread_class.isVisible())
    h.check("the drop-down says Standard", p and p.standard_label.text() == "Standard")
    v = h.solid_volume()
    expect = hs.BOX - hs.cylinder(6.6, 8)
    h.check(
        "ISO 273 M6 normal clearance: 6.6",
        p and abs(p.diameter.value() - 6.6) < 1e-9,
        p and p.diameter.value(),
    )
    h.check("clearance hole volume", hs.close(v, expect), (v, expect))
    h.check("no cosmetic thread in a clearance hole", drawn() == 0, drawn())
    if p:
        b.choose(p.fit, "Close")


def close_fit():
    p = hs.hole_panel()
    h.check(
        "M6 close fit: 6.4", p and abs(p.diameter.value() - 6.4) < 1e-9, p and p.diameter.value()
    )
    if p:
        b.choose(p.fit, "Loose")


def loose_fit():
    p = hs.hole_panel()
    h.check(
        "M6 loose fit: 7.0", p and abs(p.diameter.value() - 7.0) < 1e-9, p and p.diameter.value()
    )
    if p:
        b.choose(p.fit, "Normal")
        b.choose(p.standard, "ANSI Unified Screw Threads")


def ansi():
    p = hs.hole_panel()
    h.check(
        "ANSI: the nearest size is 1/4",
        p and p.size.currentText() == "1/4",
        p and p.size.currentText(),
    )
    d = p.diameter.value() if p else 0
    h.check("1/4 normal clearance 0.281 in (ASME B18.2.8)", abs(d - 0.281 * 25.4) < 0.05, d)
    h.shot("3-ansi")
    if p:
        b.choose(p.extent, "To")


def to_waiting():
    p = hs.hole_panel()
    h.check("To: the object box takes the clicks", p and p.fields["to"].button.isChecked())


def expand_origin():
    t = hs.browser()
    item = t.row("Origin")
    if h.check("browser has Origin", item is not None, t.labels()):
        w.click(t.viewport(), t.label_point(item))
        w.key(t, QtCore.Qt.Key_Right)


def click_xy():
    t = hs.browser()
    item = t.row("XY")
    if h.check("browser has the XY plane", item is not None, t.labels()):
        w.click(t.viewport(), t.label_point(item))


def to_plane():
    p = hs.hole_panel()
    h.check(
        "To the XY plane",
        p and p.options.get("to") and p.options["to"][0].Name.startswith("XY"),
        p and p.options.get("to"),
    )
    h.check(
        "depth worked out: 10",
        p and p.target and abs(p.target.Depth.Value - 10) < 1e-9,
        p and p.target and p.target.Depth,
    )
    v = h.solid_volume()
    expect = hs.BOX - hs.cylinder(0.281 * 25.4, 10)
    h.check("the hole ends on the plane", hs.close(v, expect, 1e-2), (v, expect))
    s["v"] = v
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("hole kept", hs.close(h.solid_volume(), s["v"]))
    h.check("valid solid", h.body().Shape.isValid())


def edit():
    b.timeline_double_click("Hole 1")


def edit_open():
    p = hs.hole_panel()
    h.check("editing the hole", p is not None and p.editing)
    if p is None:
        return
    h.check("Extents To is shown", p.extent.currentText() == "To", p.extent.currentText())
    h.check(
        "with the plane",
        p.fields["to"].button.text().startswith("XY"),
        p.fields["to"].button.text(),
    )
    h.check(
        "Clearance, ANSI 1/4, Normal",
        p.tap_type.currentText() == "Clearance"
        and p.size.currentText() == "1/4"
        and p.fit.currentText() == "Normal",
        (p.tap_type.currentText(), p.size.currentText(), p.fit.currentText()),
    )
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel kept the hole as it was", hs.close(h.solid_volume(), s["v"]))
    h.check("no kernel errors in the Report view", not b.report_has_kernel_errors())
    hs.no_popups("tapped and clearance holes")


h.run(
    "hole_tapped",
    b.box_steps("HoleTapped")
    + [
        ribbon_hole,
        click_top,
        position,
        tapped,
        tapped_fields,
        through,
        modeled,
        blind,
        tap_depth,
        tap_depth_set,
        clearance,
        close_fit,
        loose_fit,
        ansi,
        to_waiting,
        expand_origin,
        click_xy,
        to_plane,
        after_ok,
        edit,
        edit_open,
        after_cancel,
    ],
)
