# SPDX-License-Identifier: LGPL-2.1-or-later
"""Makes pattern_bodies_v1.FCStd, a design saved by SciForge before the fix of 2026-10-16
(patterns and mirrors of bodies copied the body's current shape). Run inside FreeCAD's GUI,
at a commit before that fix (it was made at d5a3690b9d):

    xvfb-run freecad SciForgeTests/fixtures/make_old_pattern.py

Run with today's code it writes the new format instead, so the file in the repository is
the one made then. The design (hand-checkable):
  Body      a 40 x 30 x 10 box from the origin (Sketch + Extrude, 12000 mm3), then a Move
            of 20 up made AFTER both patterns (the old code moved the copies with it)
  Rectangular Pattern 1   Pattern Type Bodies along X, quantity 3, spacing 50: Body2 at
            x 50..90, Body3 at x 100..140
  Mirror 1  Pattern Type Bodies, Operation New Body, across the YZ plane: Body4 at x -40..0
The old code saved every copy at z 20..30 (moved with the original); the fixed code puts
them back at z 0..10 when the file is opened (scenario fixpattern_old_file).
"""

import os
import sys

import FreeCAD as App
import FreeCADGui as Gui
import Part

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[-1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[-1]) else HERE
V = App.Vector


def rect_sketch(body, x0, y0, x1, y1):
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]  # XY plane
    sk.MapMode = "FlatFace"
    pts = [V(x0, y0, 0), V(x1, y0, 0), V(x1, y1, 0), V(x0, y1, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    return sk


def origin(body, role):
    for feature in body.Origin.OriginFeatures:
        if getattr(feature, "Role", "") == role:
            return feature
    raise RuntimeError(role)


def main():
    Gui.activateWorkbench("SciForgeWorkbench")
    from sciforge import extrude, move, pattern

    doc = App.newDocument("OldPatterns")
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = rect_sketch(body, 0, 0, 40, 30)
    doc.recompute()
    extrude.make(body, sketch, {"operation": "new_body", "distance": 10.0}, "Extrude")
    doc.recompute()
    rect = {
        "pattern_type": "bodies",
        "objects": [(body, "")],
        "direction": (origin(body, "X_Axis"), ""),
        "quantity": 3,
        "distance": 50,
        "distribution": "spacing",
    }
    pattern.build("rectangular", rect)
    doc.recompute()
    mirror = {
        "pattern_type": "bodies",
        "objects": [(body, "")],
        "plane": (origin(body, "YZ_Plane"), ""),
        "operation": "new_body",
    }
    pattern.build("mirror", mirror)
    doc.recompute()
    move.build({"bodies": [body], "move_type": "translate", "dz": 20})
    doc.recompute()
    for b in sorted(doc.findObjects("PartDesign::Body"), key=lambda o: o.ID):
        box = b.Shape.BoundBox
        print(
            "[SciForge] old pattern file: %s x %.1f..%.1f z %.1f..%.1f"
            % (b.Label, box.XMin, box.XMax, box.ZMin, box.ZMax),
            flush=True,
        )
    path = os.path.join(OUT, "pattern_bodies_v1.FCStd")
    doc.saveAs(path)
    print("[SciForge] wrote %s" % path, flush=True)


try:
    main()
finally:
    os._exit(0)
