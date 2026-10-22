# SPDX-License-Identifier: LGPL-2.1-or-later
"""Editing a pattern or an older revolve from the timeline rolls the design back to it, as
Fusion does (G-07 and G-08 of docs/sciforge/dev/remaining-gaps.md, checked 2026-10-22 after
the review of the parity work list: edit_rollback.py already covers both).

A  A 40 x 30 x 10 box, a round hole (r 2), a Rectangular Pattern of the hole (3 along X,
   24 mm), then a boss on the top (a later step), all with real input. Double-click
   "Rectangular Pattern 1" in the timeline: while its dialog is open the boss is gone (the
   volume is the pattern step's); OK: the boss is back.
B  A part as an older file has it: a 90 degree ring revolve (section x 10..20, z 0..5 on XZ,
   about Z), then a pad (a cylinder r 2 at x 15, 10 high) on it. Double-click "Revolve 1" in
   the timeline: while SciForge's Revolve dialog is open the pad is gone (the volume is the
   ring's); Esc: the pad is back.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import revolve_input as ri

V = App.Vector
s = {}
R = 2.0
HOLE = ps.hole(R)
BOSS = math.pi * 9.0 * 4.0
RING = 1500.0 * math.pi / 4.0  # 90 degrees of the ring section x 10..20, z 0..5


# -- A: a pattern --------------------------------------------------------------------------------
def a_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def a_pick():
    ps.timeline_click("Extrude 2")


def a_box():
    ps.click_box("direction")


def a_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def a_quantity():
    ps.type_quantity(ps.panel().quantity, 3)


def a_distance():
    ps.type_value(ps.panel().distance_field.widget, "24")


def a_ok():
    h.task_button("OK")


def a_made():
    s["pattern"] = h.solid_volume()
    h.check("A: the box less three holes", abs(s["pattern"] - (12000 - 3 * HOLE)) < 1e-3, s["pattern"])


def a_edit():
    s["full"] = h.solid_volume()
    h.check(
        "A: the boss added", abs(s["full"] - (s["pattern"] + BOSS)) < 1e-3, (s["full"], s["pattern"])
    )
    ps.timeline_double_click("Rectangular Pattern 1")


def a_editing():
    p = ps.panel()
    h.check("A: the pattern's dialog edits it", p is not None and getattr(p, "editing", False))
    v = h.solid_volume()
    h.check(
        "A: while the pattern is edited, the later boss is rolled away (G-07)",
        abs(v - s["pattern"]) < 1e-3,
        (v, s["pattern"], s["full"]),
    )
    h.task_button("OK")


def a_after():
    v = h.solid_volume()
    h.check("A: after OK the boss is back", abs(v - s["full"]) < 1e-3, (v, s["full"]))


# -- B: an older revolve ------------------------------------------------------------------------
def b_part():
    import Part

    doc = App.newDocument("RollRevolve")
    body = doc.addObject("PartDesign::Body", "Body")
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    origin = {f.Role: f for f in body.Origin.OriginFeatures}
    ring = body.newObject("Sketcher::SketchObject", "Sketch")
    ring.AttachmentSupport = [(origin["XZ_Plane"], "")]
    ring.MapMode = "FlatFace"
    pts = [V(10, 0, 0), V(20, 0, 0), V(20, 5, 0), V(10, 5, 0)]
    for i in range(4):
        ring.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    rev = body.newObject("PartDesign::Revolution", "Revolution")
    rev.Profile = ring
    rev.ReferenceAxis = (ring, ["V_Axis"])
    rev.Angle = 90
    post = body.newObject("Sketcher::SketchObject", "Sketch001")
    post.AttachmentSupport = [(origin["XY_Plane"], "")]
    post.MapMode = "FlatFace"
    post.addGeometry(Part.Circle(V(15, 0, 0), V(0, 0, 1), 2.0))
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = post
    pad.Length = 10
    doc.recompute()
    ring.ViewObject.Visibility = False
    post.ViewObject.Visibility = False
    s["body"] = body
    h.fit()


def b_edit():
    s["ring_full"] = s["body"].Shape.Volume
    h.check(
        "B: the pad adds to the ring", s["ring_full"] > RING + 1.0, (s["ring_full"], RING)
    )
    h.check(
        "B: double-click Revolve 1 in the timeline",
        ui.double_click_timeline("Revolve 1"),
        ui.timeline_titles(),
    )


b_edit.wait_ms = 1500


def b_editing():
    p = ri.panel()
    h.check("B: SciForge's Revolve dialog edits it", p is not None and p.editing)
    v = s["body"].Shape.Volume
    h.check(
        "B: while the revolve is edited, the later pad is rolled away (G-08)",
        abs(v - RING) < 1e-3,
        (v, RING, s["ring_full"]),
    )
    h.task_button("Cancel")


def b_after():
    v = s["body"].Shape.Volume
    h.check("B: after Cancel the pad is back", abs(v - s["ring_full"]) < 1e-3, (v, s["ring_full"]))


h.run(
    "gaps_edit_rollback",
    b.box_steps("RollPattern")
    + ps.make_cut("hole", (8, 8), R)
    + [a_start, a_pick, a_box, a_axis, a_quantity, a_distance, a_ok, a_made]
    + ps.make_boss("boss", (30, 22), 3, 4, V(36, 27, 10))
    + [a_edit, a_editing, a_after]
    + [b_part, b_edit, b_editing, b_after],
)
