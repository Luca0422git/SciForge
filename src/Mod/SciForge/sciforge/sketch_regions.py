# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch "profiles": the closed regions a sketch's curves enclose.

Fusion shades every area the curves close off, also where curves cross each other
(two overlapping circles make three profiles; a line across a rectangle makes two).
FreeCAD's face makers only accept separate, non-crossing loops, so the regions are
found here with the planar split OpenCASCADE does in a general fuse: a large flat
sheet is cut by all curves, and every piece that does not touch the sheet's border
is a closed region.

No Qt, no GUI: used by the sketch shading (sketch_mode.py), unit-checked by the golden
runner through the same code.
"""

import FreeCAD as App

TOLERANCE = 1e-7
TYPES_WITHOUT_AREA = ("Part::GeomPoint",)


def sketch_edges(sketch, include_construction=False):
    """Edges of a sketch's own curves, in sketch coordinates (z = 0).

    Construction curves and points never make profiles in Fusion."""
    edges = []
    for index, geometry in enumerate(sketch.Geometry):
        try:
            if not include_construction and sketch.getConstruction(index):
                continue
            if geometry.TypeId in TYPES_WITHOUT_AREA or type(geometry).__name__ == "Point":
                continue
            edges.append(geometry.toShape())
        except Exception:
            continue
    edges += _projected_edges(sketch)
    return edges


def _projected_edges(sketch):
    """Projected part edges that are "defining" (Fusion: projected geometry makes
    profiles; Include 3D Geometry and construction projections do not)."""
    edges = []
    try:
        import Sketcher

        external = list(sketch.ExternalGeo)[2:]  # the first two are the sketch axes
    except Exception:
        return edges
    for geometry in external:
        try:
            if geometry.TypeId in TYPES_WITHOUT_AREA:
                continue
            if not Sketcher.ExternalGeometryFacade(geometry).testFlag("Defining"):
                continue
            edges.append(geometry.toShape())
        except Exception:
            continue
    return edges


def regions(edges, tolerance=TOLERANCE):
    """Faces of all closed regions the edges (flat, z = 0) enclose, smallest pieces;
    [] when nothing is closed."""
    import Part

    edges = [e for e in edges if e is not None and not e.isNull() and e.Length > tolerance]
    if not edges:
        return []
    box = Part.Compound(edges).BoundBox
    pad = max(box.DiagonalLength, 1.0)
    x0, y0 = box.XMin - pad, box.YMin - pad
    x1, y1 = box.XMax + pad, box.YMax + pad
    sheet = Part.makePlane(x1 - x0, y1 - y0, App.Vector(x0, y0, 0))
    pieces, _ = sheet.generalFuse(edges, tolerance)
    found = []
    limit = 1e-6 * max(1.0, pad)
    for face in pieces.Faces:
        on_border = False
        for vertex in face.Vertexes:
            p = vertex.Point
            if (
                abs(p.x - x0) < limit
                or abs(p.y - y0) < limit
                or abs(p.x - x1) < limit
                or abs(p.y - y1) < limit
            ):
                on_border = True
                break
        if not on_border and face.Area > tolerance:
            found.append(face)
    return found


def sketch_regions(sketch):
    """Closed regions of a sketch in sketch coordinates."""
    return regions(sketch_edges(sketch))


def _ends(geometry):
    """End points (App.Vector) of an open curve; [] for closed curves and points."""
    try:
        if geometry.TypeId in ("Part::GeomCircle", "Part::GeomEllipse", "Part::GeomPoint"):
            return []
        return [geometry.StartPoint, geometry.EndPoint]
    except Exception:
        return []


def connected_chain(sketch, start_ids, tolerance=1e-6):
    """Fusion's chain selection: the curves joined end to end with the given ones
    (0-based geometry indices; construction curves only if picked)."""
    geometry = sketch.Geometry
    picked = [i for i in start_ids if 0 <= i < len(geometry)]
    usable = {i for i in range(len(geometry)) if i in picked or not sketch.getConstruction(i)}
    ends = {i: _ends(geometry[i]) for i in usable}
    chain = set(picked)
    todo = list(picked)
    while todo:
        current = todo.pop()
        for point in ends.get(current, []):
            for other in usable:
                if other in chain:
                    continue
                if any((point - q).Length <= tolerance for q in ends[other]):
                    chain.add(other)
                    todo.append(other)
    return sorted(chain)
