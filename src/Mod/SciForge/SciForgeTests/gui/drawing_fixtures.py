# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parts the drawing scenarios draw (no GUI needed). The drawing is the subject of those
scenarios, so the part is built by script; the edits that must show on the drawing are
made with real input in the scenarios.

block(doc): a 60 x 40 x 20 block (PartDesign Box) with a 12 mm hole through its middle
            and its four upright edges filleted (R5). Volume 48000 - 2880*... see VOLUME.
assembly(doc): two components, Plate (80 x 50 x 8) and Post (20 x 20 x 30 standing on
            the plate at x 30..50, y 15..35)."""

import math

import FreeCAD as App

V = App.Vector
LENGTH, WIDTH, HEIGHT = 60.0, 40.0, 20.0
HOLE_R = 6.0
FILLET_R = 5.0
VOLUME = (
    LENGTH * WIDTH * HEIGHT
    - math.pi * HOLE_R**2 * HEIGHT
    - 4 * (FILLET_R**2 - math.pi * FILLET_R**2 / 4.0) * HEIGHT
)


def block(doc, label="Block"):
    body = doc.addObject("PartDesign::Body", "Body")
    body.Label = "Body1"
    box = body.newObject("PartDesign::AdditiveBox", "Box")
    box.Length, box.Width, box.Height = LENGTH, WIDTH, HEIGHT
    hole = body.newObject("PartDesign::SubtractiveCylinder", "Hole")
    hole.Radius = HOLE_R
    hole.Height = HEIGHT
    hole.Placement.Base = V(LENGTH / 2.0, WIDTH / 2.0, 0)
    doc.recompute()
    names = []
    for i, edge in enumerate(hole.Shape.Edges, start=1):
        a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        upright = abs(a.x - b.x) < 1e-6 and abs(a.y - b.y) < 1e-6 and abs(a.z - b.z) > 1
        corner = a.x in (0.0, LENGTH) and a.y in (0.0, WIDTH)
        if upright and corner:
            names.append("Edge%d" % i)
    fillet = body.newObject("PartDesign::Fillet", "Fillet")
    fillet.Base = (hole, names)
    fillet.Radius = FILLET_R
    body.Tip = fillet
    doc.recompute()
    try:
        if App.GuiUp:
            for step in (box, hole):
                step.ViewObject.Visibility = False
            fillet.ViewObject.Visibility = True
    except Exception:
        pass
    return body


def assembly(doc):
    from sciforge import components

    plate_part = components.new_component(doc, "Plate")
    plate_body = components.new_body_in(doc, plate_part, "Body1")
    plate = plate_body.newObject("PartDesign::AdditiveBox", "PlateBox")
    plate.Length, plate.Width, plate.Height = 80.0, 50.0, 8.0
    plate_body.Tip = plate
    post_part = components.new_component(doc, "Post")
    post_body = components.new_body_in(doc, post_part, "Body1")
    post = post_body.newObject("PartDesign::AdditiveBox", "PostBox")
    post.Length, post.Width, post.Height = 20.0, 20.0, 30.0
    post.Placement.Base = V(30, 15, 8)
    post_body.Tip = post
    doc.recompute()
    return (plate_part, plate_body), (post_part, post_body)
