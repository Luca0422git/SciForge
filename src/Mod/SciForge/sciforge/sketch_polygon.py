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
    """Add the polygon to `sketch`; returns the geometry indices.

    Inscribed (FreeCAD's own polygon): n lines, then the construction circle through
    the corners. Circumscribed: n lines, the construction circle touching the edges
    (the across-flats size, the one to dimension), a construction line from the centre
    to the middle of the first edge, then the circle through the corners.

    The corners stay on a circle in both, because equal sides on a circle is the
    only description of a regular polygon the solver handles at every size and
    number of sides (equal sides touching a circle can lean over into a rhombus).

    FreeCAD's polygon tool adds the constraints for what was under the mouse after
    this runs: the first click's to the centre of the LAST curve, the second click's
    to the end of the curve before it. The order above puts them on the centre and
    on the clicked point (a corner, or the middle of an edge).
    """
    import Part
    import Sketcher

    sides = int(sides)
    center = App.Vector(center.x, center.y, 0)
    point = App.Vector(point.x, point.y, 0)
    pts = corners(center, point, sides, circumscribed)
    normal = App.Vector(0, 0, 1)
    geometry = [Part.LineSegment(pts[i], pts[(i + 1) % sides]) for i in range(sides)]
    outer_radius = (pts[0] - center).Length
    if circumscribed:
        geometry.append(Part.Circle(center, normal, (point - center).Length))
        geometry.append(Part.LineSegment(center, point))  # centre -> middle of edge 0
    geometry.append(Part.Circle(center, normal, outer_radius))
    ids = list(sketch.addGeometry(geometry, construction))
    lines = ids[:sides]
    outer = ids[-1]
    for extra in ids[sides:]:
        sketch.setConstruction(extra, True)
    constraints = []
    for i in range(sides):
        constraints.append(
            Sketcher.Constraint("Coincident", lines[i], 2, lines[(i + 1) % sides], 1)
        )
    for i in range(1, sides):
        constraints.append(Sketcher.Constraint("Equal", lines[0], lines[i]))
    for i in range(sides):
        constraints.append(Sketcher.Constraint("PointOnObject", lines[i], 2, outer))
    if circumscribed:
        inner, helper = ids[sides], ids[sides + 1]
        constraints.append(Sketcher.Constraint("Coincident", inner, 3, outer, 3))
        constraints.append(Sketcher.Constraint("Tangent", lines[0], inner))
        constraints.append(Sketcher.Constraint("Coincident", helper, 1, outer, 3))
        constraints.append(Sketcher.Constraint("Symmetric", lines[0], 1, lines[0], 2, helper, 2))
    sketch.addConstraint(constraints)
    return ids
