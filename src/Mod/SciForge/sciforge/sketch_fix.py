# SPDX-License-Identifier: LGPL-2.1-or-later
"""Repairs for sketch data that FreeCAD 1.1.4's own tools can leave behind (no Qt).

Trim: cutting a curve exactly at the 0-degree point of a full circle or ellipse (a line
through the centre of a circle, for example) creates "Coincident with the circle's
start point". A full circle has no start point, so the sketch becomes invalid
("Sketcher constraint number N is malformed!", the whole sketch turns orange) and
anything extruded from it fails. Core patch #7 fixes the trim itself; this repair
keeps SciForge builds without that C++ change (quick updates) working: the bad
constraint becomes "point on the circle", which is what the trim meant.
"""

CLOSED_CURVES = ("Part::GeomCircle", "Part::GeomEllipse")


def _closed(sketch, geo_id):
    if geo_id < 0 or geo_id >= len(sketch.Geometry):
        return False
    geometry = sketch.Geometry[geo_id]
    if geometry.TypeId in CLOSED_CURVES:
        return True
    return geometry.TypeId == "Part::GeomBSplineCurve" and geometry.isPeriodic()


def bad_coincidences(sketch):
    """[(constraint index, point geo, point pos, curve geo)] for every Coincident that
    uses the start/end point of a full circle, ellipse or periodic spline."""
    found = []
    for index, c in enumerate(sketch.Constraints):
        if c.Type != "Coincident":
            continue
        if c.SecondPos in (1, 2) and _closed(sketch, c.Second):
            found.append((index, c.First, c.FirstPos, c.Second))
        elif c.FirstPos in (1, 2) and _closed(sketch, c.First):
            found.append((index, c.Second, c.SecondPos, c.First))
    return found


def repair(sketch):
    """Turn those coincidences into point-on-curve constraints. Returns how many."""
    import Sketcher

    bad = bad_coincidences(sketch)
    if not bad:
        return 0
    replacements = [
        Sketcher.Constraint("PointOnObject", geo, pos, curve) for _, geo, pos, curve in bad
    ]
    for index, _, _, _ in sorted(bad, reverse=True):
        sketch.delConstraint(index)
    sketch.addConstraint(replacements)
    return len(bad)
