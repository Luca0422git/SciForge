# SPDX-License-Identifier: LGPL-2.1-or-later
"""A line across a face and a circle on it: each half of the circle is a profile (Luca,
2026-10-18: "having that line there makes it impossible to extrude the circle"; Extrude
took the whole face). FreeCAD 1.1.4 makes no sketch area at all for this layout;
sciforge/sketch_area_fill.py adds the areas SciForge's own region finder sees. Real mouse
moves and clicks.

A block 100 x 40 x 10. Create Sketch on its top face (its edges projected, Auto project).
1. L: a line across the face, from the projected top edge at x 25 to the bottom edge.
2. C: a circle with its centre on the line's midpoint (it snaps there) and radius 6.
3. In the open sketch: four areas (the two halves of the circle, the face either side).
4. Finish Sketch, E: nothing is taken by itself (several areas); a click in the left half
   of the circle takes that half, a click in the right half adds it; 5 mm, OK: the block
   grows by the whole circle, not by the face.
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
BLOCK = 100.0 * 40.0 * Z


def g(x, y):
    return V(x, y, Z)


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def esc():
    h.press(QtCore.Qt.Key_Escape)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("LineThroughCircle")
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    sk.AttachmentSupport = [(doc.getObject("XY_Plane"), "")]
    sk.MapMode = "FlatFace"
    h.draw_rectangle(sk, 0, 0, 100, 40)
    pad = body.newObject("PartDesign::Pad", "Extrude")
    pad.Profile = sk
    pad.Length = Z
    doc.recompute()
    sk.Visibility = False
    h.fit()


def create_sketch():
    h.check("the block", near(h.solid_volume(), BLOCK), h.solid_volume())
    h.ribbon("Create Sketch")


def click_top():
    h.click(g(80, 30))


def ready():
    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open on the top face", sk is not None)
    if sk is None:
        return
    h.check(
        "the face's edges are projected (Auto project)",
        len(sk.ExternalGeo) == 6,
        list(sk.ExternalGeo),
    )
    h.press("l")


def line_top():
    si.click(g(25, 40), V(0.0, -1.0, 0))


def line_bottom():
    si.click(g(25, 0), V(0.0, 1.0, 0))


def circle_key():
    esc()
    sk = s["sk"]
    s["line"] = len(sk.Geometry) - 1
    h.check("one line drawn", len(sk.Geometry) == 1, len(sk.Geometry))
    h.press("c")


def centre():
    si.click(g(25, 20))


def radius():
    si.click(g(31, 20))


def areas():
    esc()
    from sciforge import sketch_regions

    sk = s["sk"]
    circles = [geo for geo in sk.Geometry if type(geo).__name__ == "Circle"]
    h.check("one circle", len(circles) == 1, [type(geo).__name__ for geo in sk.Geometry])
    if not circles:
        return
    circle = circles[0]
    s["r"] = circle.Radius
    line = sk.Geometry[s["line"]]
    middle = (line.StartPoint + line.EndPoint) * 0.5
    h.check("its centre snapped to the line's middle", (circle.Center - middle).Length < 1e-6,
            (circle.Center, middle))
    found = sorted(f.Area for f in sketch_regions.sketch_regions(sk))
    half = math.pi * s["r"] ** 2 / 2.0
    h.check(
        "four areas: two halves of the circle and the face either side",
        len(found) == 4 and near(found[0], half) and near(found[1], half),
        [round(a, 3) for a in found],
    )
    h.shot("1-areas")
    h.ribbon("Finish Sketch")


def finished():
    h.check("left the sketch", h.in_sketch() is None)
    h.check("the sketch is valid", "Invalid" not in s["sk"].State, s["sk"].State)
    from sciforge import extrude

    faces = sorted(round(face.Area, 3) for _sub, face in extrude.regions(s["sk"]))
    h.check("Extrude has the four areas to offer", len(faces) == 4, faces)
    h.fit()
    h.press("e")


def picked_areas(panel):
    from sciforge import extrude

    regions = dict(extrude.regions(s["sk"]))
    found = []
    for _obj, sub in (panel.profiles if panel is not None else None) or []:
        face = regions.get(sub)
        found.append(round(face.Area, 6) if face is not None else None)
    return sorted(found)


def extrude_open():
    from sciforge import extrude_ui

    panel = extrude_ui.ExtrudePanel.last
    s["panel"] = panel
    h.check("E opens Extrude", panel is not None)
    h.check("nothing taken by itself (several areas)", picked_areas(panel) == [],
            picked_areas(panel))


def click_left_half():
    h.click(g(22, 20))


def left_half():
    half = round(math.pi * s["r"] ** 2 / 2.0, 6)
    found = picked_areas(s["panel"])
    h.check("a click in the circle takes its left half (not the face)",
            len(found) == 1 and near(found[0], half, 1e-4), (found, half))


def click_right_half():
    h.click(g(28, 20))


def both_halves():
    half = round(math.pi * s["r"] ** 2 / 2.0, 6)
    found = picked_areas(s["panel"])
    h.check("a click in the other half adds it",
            len(found) == 2 and all(near(a, half, 1e-4) for a in found), (found, half))
    arrows.type_distance("5")


def ok():
    h.task_button("OK")


def extruded():
    v = h.solid_volume()
    want = BLOCK + math.pi * s["r"] ** 2 * 5.0
    h.check("the block grew by the circle only", near(v, want, 1e-6), (v, want))
    s["extruded"] = v
    Gui.runCommand("Std_Undo")


def undone():
    v = h.solid_volume()
    h.check("Undo: the block again", near(v, BLOCK), v)
    Gui.runCommand("Std_Redo")


def redone():
    v = h.solid_volume()
    h.check("Redo: as before", near(v, s["extruded"]), v)
    for obj in App.ActiveDocument.Objects:
        h.check("%s has no error" % obj.Label, "Invalid" not in obj.State, obj.State)
    h.shot("2-extruded")


h.run(
    "sketch_line_through_circle",
    si.watched(
        [
            new_design,
            create_sketch,
            click_top,
            ready,
            line_top,
            line_bottom,
            circle_key,
            centre,
            radius,
            areas,
            finished,
            extrude_open,
            click_left_half,
            left_half,
            click_right_half,
            both_halves,
            ok,
            extruded,
            undone,
            redone,
        ]
    ),
)
