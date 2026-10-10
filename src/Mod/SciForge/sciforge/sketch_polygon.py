# SPDX-License-Identifier: LGPL-2.1-or-later
"""Regular polygons the way Fusion makes them (no Qt; the GUI and the golden builder
both use this).

- Inscribed polygon: the corners lie on a construction circle; the second click is
  a corner. (Same geometry as FreeCAD's polygon tool.)
- Circumscribed polygon: the polygon is drawn around a construction circle, every
  edge touches it; the second click is the middle of an edge. Dimensioning that
  circle gives the size across the flats (a hex nut's wrench size).

Both are n lines with coincident ends, equal lengths and the construction circle,
leaving exactly 4 degrees of freedom (centre x/y, size, rotation), like Fusion.
"""
import math

import FreeCAD as App

DEFAULT_SIDES = 6


def corners(center, point, sides, circumscribed):
    """Corner points (App.Vector, z = 0) of a regular polygon around `center`.

    `point` is a corner (inscribed) or the middle of an edge (circumscribed)."""
    sides = int(sides)
    if sides < 3:
        raise ValueError("a polygon needs at least 3 sides")
    dx, dy = point.x - center.x, point.y - center.y
    radius = math.hypot(dx, dy)
    if radius < 1e-9:
        raise ValueError("the polygon has no size")
    start = math.atan2(dy, dx)
    if circumscribed:
        radius /= math.cos(math.pi / sides)
        start -= math.pi / sides
    step = 2.0 * math.pi / sides
    return [
        App.Vector(
            center.x + radius * math.cos(start + i * step),
            center.y + radius * math.sin(start + i * step),
            0,
        )
        for i in range(sides)
    ]


def add_polygon(sketch, sides, center, point, circumscribed, construction=False):
    """Add the polygon to `sketch`; returns the geometry indices (n lines, then the
    construction circle, the order FreeCAD's own tool uses)."""
    import Part
    import Sketcher

    sides = int(sides)
    center = App.Vector(center.x, center.y, 0)
    point = App.Vector(point.x, point.y, 0)
    pts = corners(center, point, sides, circumscribed)
    geometry = [Part.LineSegment(pts[i], pts[(i + 1) % sides]) for i in range(sides)]
    circle_radius = (point - center).Length
    geometry.append(Part.Circle(center, App.Vector(0, 0, 1), circle_radius))
    ids = sketch.addGeometry(geometry, construction)
    sketch.setConstruction(ids[-1], True)
    constraints = []
    for i in range(sides):
        constraints.append(Sketcher.Constraint("Coincident", ids[i], 2, ids[(i + 1) % sides], 1))
    for i in range(1, sides):
        constraints.append(Sketcher.Constraint("Equal", ids[0], ids[i]))
    if circumscribed:
        # every edge touches the circle: the circle is the across-flats size
        for i in range(sides):
            constraints.append(Sketcher.Constraint("Tangent", ids[i], ids[-1]))
    else:
        for i in range(sides):
            constraints.append(Sketcher.Constraint("PointOnObject", ids[i], 2, ids[-1]))
    sketch.addConstraint(constraints)
    return list(ids)
