# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shapes drawn against projected edges are profiles of their own (Luca: "When lines are
connected to a projection on a face, any shape that is sketched will not be selectable to
extrude; only the whole face"), with real mouse moves and clicks.

A block 40 x 30 x 10. Create Sketch on its top face: the face's edges are projected (Auto
project, sciforge/sketch_auto_project.py).
1. R: a rectangle from 3 px off the projected corner (0, 0) to (12, 10): its corner lands
   exactly on the projected corner (sketch_infer snapping), not a hair beside it.
2. L: two lines from the projected bottom edge at (26, 0) up to (26, 12) and right onto
   the projected right edge at (40, 12): with the projected edges they close an area.
3. In the open sketch: three areas, 120 (the rectangle), 168 (the one against the corner)
   and 912 (the rest of the face).
4. Finish Sketch, E: Extrude takes the rectangle by itself (the one area the drawn curves
   close on their own, as without the projected edges); a click inside the U adds it; 5
   mm, OK: the block grows by (120 + 168) x 5 = 1440, not by the whole face.
5. Undo / Redo.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}
Z = 10.0


def g(x, y):
    return V(x, y, Z)


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def about(found, want, tol=2.0):
    return len(found) == len(want) and all(abs(a - b) <= tol for a, b in zip(found, want))


def esc():
    h.press(QtCore.Qt.Key_Escape)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("ProjectedProfiles")
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    sk.AttachmentSupport = [(doc.getObject("XY_Plane"), "")]
    sk.MapMode = "FlatFace"
    h.draw_rectangle(sk, 0, 0, 40, 30)
    pad = body.newObject("PartDesign::Pad", "Extrude")
    pad.Profile = sk
    pad.Length = Z
    doc.recompute()
    sk.Visibility = False
    h.fit()


def create_sketch():
    h.check("the block", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.ribbon("Create Sketch")


def click_top():
    h.click(g(33, 24))


def ready():
    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open on the top face", sk is not None)
    if sk is None:
        return
    s["px"] = si.mm_per_pixel(sk)
    h.check(
        "the face's edges are projected (Auto project)",
        len(sk.ExternalGeo) == 6,
        list(sk.ExternalGeo),
    )
    h.press("r")


def rect_first():
    k = 3.0 * s["px"] / math.hypot(1.0, 0.7)
    si.click(g(1.0 * k, 0.7 * k))


def rect_second():
    si.click(g(12, 10))


def lines_key():
    esc()
    sk = s["sk"]
    corners = [
        (i, pos)
        for i, geo in enumerate(sk.Geometry)
        for pos in (1, 2)
        if (sk.getPoint(i, pos) - V(0, 0, 0)).Length < 1e-9
    ]
    h.check("the rectangle's corner is exactly the projected corner", len(corners) == 2, corners)
    h.press("l")


def l1():
    si.click(g(26, 0), V(0.0, 1.0, 0))


def l2():
    si.click(g(26, 12))


def l3():
    si.click(g(40, 12), V(-1.0, 0.0, 0))


def areas():
    esc()
    from sciforge import sketch_mode, sketch_regions

    found = sorted(round(f.Area, 6) for f in sketch_regions.sketch_regions(s["sk"]))
    # (the two lines' clicked points lie on a pixel: within a pixel's worth of area)
    h.check(
        "three areas: the rectangle, the U, the rest", about(found, [120.0, 168.0, 912.0]), found
    )
    ses = sketch_mode.current()
    h.check(
        "... all three shaded",
        ses is not None and ses.shading.count == 3,
        ses and ses.shading.count,
    )
    h.shot("1-areas")
    h.ribbon("Finish Sketch")


def finished():
    h.check("left the sketch", h.in_sketch() is None)
    h.check("the sketch is valid", "Invalid" not in s["sk"].State, s["sk"].State)
    h.fit()
    h.press("e")


def extrude_open():
    from sciforge import extrude_ui

    panel = extrude_ui.ExtrudePanel.last
    s["panel"] = panel
    h.check("E opens Extrude", panel is not None)
    h.check(
        "E takes the rectangle by itself (120 mm^2, not the whole face)",
        areas_of(panel) == [120.0],
        areas_of(panel),
    )


def areas_of(panel):
    from sciforge import extrude

    regions = dict(extrude.regions(s["sk"]))
    found = []
    for _obj, sub in (panel.profiles if panel is not None else None) or []:
        face = regions.get(sub)
        found.append(round(face.Area, 6) if face is not None else None)
    return sorted(found)


def click_u():
    h.click(g(32, 6))


def picked():
    panel = s["panel"]
    h.check("a click inside the U adds it", about(areas_of(panel), [120.0, 168.0]), areas_of(panel))
    arrows.type_distance("5")


def ok():
    h.task_button("OK")


def extruded():
    v = h.solid_volume()
    h.check(
        "the block grew by the rectangle and the U only: 12000 + 1440", abs(v - 13440.0) < 10.0, v
    )
    s["extruded"] = v
    Gui.runCommand("Std_Undo")


def undone():
    v = h.solid_volume()
    h.check("Undo: the block again", near(v, 12000.0), v)
    Gui.runCommand("Std_Redo")


def redone():
    v = h.solid_volume()
    h.check("Redo: as before", near(v, s["extruded"]), v)
    for obj in App.ActiveDocument.Objects:
        h.check("%s has no error" % obj.Label, "Invalid" not in obj.State, obj.State)
    h.shot("2-extruded")


h.run(
    "sketch_projected_profiles",
    si.watched(
        [
            new_design,
            create_sketch,
            click_top,
            ready,
            rect_first,
            rect_second,
            lines_key,
            l1,
            l2,
            l3,
            areas,
            finished,
            extrude_open,
            click_u,
            picked,
            ok,
            extruded,
            undone,
            redone,
        ]
    ),
)
