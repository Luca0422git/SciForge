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


def sketch_edges(sketch, include_construction=False, projected=True):
    """Edges of a sketch's own curves, in sketch coordinates (z = 0), and (`projected`)
    its profile-making projected curves.

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
    if projected:
        edges += _projected_edges(sketch)
    return edges


def _projected_edges(sketch, only=None):
    """Projected part edges that are "defining" (Fusion: projected geometry makes
    profiles; Include 3D Geometry and construction projections do not). `only`: a set of
    curve ids (the face's own edges Auto project made) to keep, None for all."""
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
            facade = Sketcher.ExternalGeometryFacade(geometry)
            if not facade.testFlag("Defining"):
                continue
            if only is not None and facade.Id not in only:
                continue
            edges.append(geometry.toShape())
        except Exception:
            continue
    return edges


def outline_only(face, projected, tolerance=1e-6):
    """True when the face's outer outline lies wholly on the `projected` edges (sketch
    coordinates): an area only the projected face's edges bound (the face itself, less
    what is drawn inside it), not a shape the person drew against them."""
    import Part

    if not projected:
        return False
    try:
        outline = face.OuterWire.Edges
    except Exception:
        return False
    for edge in outline:
        try:
            first, last = edge.ParameterRange
            probes = [edge.valueAt(first + (last - first) * k) for k in (0.25, 0.5, 0.75)]
        except Exception:
            return False
        for point in probes:
            vertex = Part.Vertex(point)
            if not any(p.distToShape(vertex)[0] <= tolerance for p in projected):
                return False
    return True


def face_areas(sketch, faces):
    """The indices of `faces` (the sketch's areas, sketch coordinates) that only the
    face's own edges Auto project made bound (not curves projected with P): with Auto
    project the face a sketch lies on is one more area of it; SciForge leaves that area
    to the face (a click there takes the face, Press Pull and Extrude work on the face as
    without the projected edges). Areas drawn against the
    projected edges (a rectangle from a projected corner) stay profiles."""
    from . import sketch_auto_project

    ids = sketch_auto_project.auto_ids(sketch)
    projected = _projected_edges(sketch, only=ids) if ids else []
    if not projected:
        return []
    return [i for i, f in enumerate(faces) if outline_only(f, projected)]


def profile_regions(sketch):
    """The sketch's areas (sketch_regions) without the face's own (face_areas)."""
    faces = sketch_regions(sketch)
    left = set(face_areas(sketch, faces))
    return [f for i, f in enumerate(faces) if i not in left]


def drawn_regions(sketch, faces):
    """The indices of `faces` (the sketch's areas with its projected curves, sketch
    coordinates) that lie inside the one area the sketch's own curves close by
    themselves, or [] when they close none or several. With the face's edges projected
    (Auto project) a circle drawn on a face makes two areas (the disc and the face
    around it) and a rectangle drawn over a face's outline is split by the face's inner
    edges: Extrude still takes what was drawn by itself, as without the projected
    curves (SciForge's choice: Fusion with its Auto project option on takes nothing)."""
    try:
        own = regions(sketch_edges(sketch, projected=False))
    except Exception:
        return []
    if len(own) != 1:
        return []
    found = []
    for i, face in enumerate(faces):
        point = inner_point(face)
        if point is not None and own[0].isInside(point, 1e-6, True):
            found.append(i)
    return found


def inner_point(face):
    """A point inside the face (its centre can be in a hole of it), or None."""
    try:
        centre = face.CenterOfMass
        if face.isInside(centre, 1e-6, True):
            return centre
        u0, u1, v0, v1 = face.ParameterRange
        # odd fractions: a grid point never falls on a drawn line at a round number
        for i in range(12):
            for j in range(12):
                u = u0 + (u1 - u0) * (i + 0.4142) / 12.0
                v = v0 + (v1 - v0) * (j + 0.6180) / 12.0
                point = face.valueAt(u, v)
                if face.isInside(point, 1e-6, True):
                    return point
    except Exception:
        return None
    return None


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
