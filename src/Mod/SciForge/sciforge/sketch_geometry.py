# SPDX-License-Identifier: LGPL-2.1-or-later
"""Changing or putting back a sketch's curves without losing what FreeCAD keeps on them.

Each curve of a FreeCAD 1.1.4 sketch carries extensions besides its shape: the
SketchGeometryExtension (its geometry id, which the element map, external references and
SciForge's own picks use; the construction flag; the "blocked" state; the internal-alignment
role of an ellipse's or B-spline's helper curves; the geometry layer) and, in the window,
the ViewProviderSketchGeometryExtension (visual layer, B-spline representation factor).

`sketch.Geometry = [...]` keeps them only for curves read from the sketch that kept them:
FreeCAD gives a point to Python without any (Part's GeomPoint::getPyObject builds a new
point from the coordinates), so every point came back a normal point with a new id
(a sketch fillet's old corner, construction, became a real point; an ellipse's foci lost
their role), and a curve made afresh (Part.LineSegment(...)) came back a normal curve with
a new id. `sketch.GeometryFacadeList` hands every curve with its extensions; these helpers
read and write through it, and give a replaced curve the extensions of the one it replaces.

- set_geometry(sketch, changes): replace some curves ({index: new curve}).
- snapshot(sketch) / restore(sketch, snap): the curves as they are now, and put back.
- curves(snap): the plain curves of a snapshot (to compare positions).

They do not solve or recompute: the caller does what it did after `sketch.Geometry = ...`.
"""

from . import warn


def _facades(sketch):
    try:
        return list(sketch.GeometryFacadeList)
    except Exception:
        return None  # an older FreeCAD without the facade list: the fallback below


def _carry(old, geometry):
    """`geometry` (a Part curve) as a GeometryFacade with every extension of `old` (the
    facade it replaces): its id, construction flag, blocked state, internal role, layers."""
    import Sketcher

    new = geometry.copy()
    for ext in old.getExtensions():
        try:
            new.setExtension(ext)  # (FreeCAD copies it; one of the same type is replaced)
        except Exception:
            pass
    return Sketcher.GeometryFacade(new)


def set_geometry(sketch, changes):
    """Replace some curves of the sketch ({index: new geometry}); every curve keeps its
    construction flag, geometry id, blocked state, internal-alignment role and layers (a
    replaced curve takes those of the curve it replaces)."""
    facades = _facades(sketch)
    if facades is None:
        _set_geometry_plain(sketch, changes)
        return
    for index, geometry in changes.items():
        facades[index] = _carry(facades[index], geometry)
    sketch.GeometryFacadeList = facades


def _set_geometry_plain(sketch, changes):
    """Without GeometryFacadeList: assign Geometry, then the construction flags and the ids
    again (blocked state and internal roles of points are lost there)."""
    count = len(sketch.Geometry)
    flags = [sketch.getConstruction(i) for i in range(count)]
    ids = []
    for i in range(count):
        try:
            ids.append((i, sketch.getGeometryId(i)))
        except Exception:
            pass
    geos = list(sketch.Geometry)
    for index, geometry in changes.items():
        geos[index] = geometry
    sketch.Geometry = geos
    for i, flag in enumerate(flags):
        if i < len(sketch.Geometry) and sketch.getConstruction(i) != flag:
            sketch.setConstruction(i, flag)
    if ids:
        try:
            sketch.setGeometryIds(ids)
        except Exception as exc:
            warn("sketch geometry: ids not kept (%s)" % exc)


class Snapshot:
    """The sketch's curves as they were (each with its extensions)."""

    def __init__(self, sketch):
        self.facades = _facades(sketch)
        self.geometry = None
        self.flags = None
        self.ids = None
        if self.facades is None:
            self.geometry = list(sketch.Geometry)
            self.flags = [sketch.getConstruction(i) for i in range(len(self.geometry))]
            self.ids = []
            for i in range(len(self.geometry)):
                try:
                    self.ids.append((i, sketch.getGeometryId(i)))
                except Exception:
                    pass

    def __len__(self):
        return len(self.facades if self.facades is not None else self.geometry)


def snapshot(sketch):
    """The curves as they are now, to put back with restore() (cheap: a copy of each curve,
    about 1 ms for 600 curves)."""
    return Snapshot(sketch)


def curves(snap):
    """The plain Part curves of a snapshot, in order (to compare where they are)."""
    if snap.facades is not None:
        return [f.Geometry for f in snap.facades]
    return list(snap.geometry)


def restore(sketch, snap):
    """Put the sketch's curves back as they were in `snap` (positions, construction flags,
    ids, blocked state, internal roles, layers)."""
    if snap.facades is not None:
        sketch.GeometryFacadeList = snap.facades
        return
    sketch.Geometry = snap.geometry
    for i, flag in enumerate(snap.flags):
        if i < len(sketch.Geometry) and sketch.getConstruction(i) != flag:
            sketch.setConstruction(i, flag)
    if snap.ids:
        try:
            sketch.setGeometryIds(snap.ids)
        except Exception as exc:
            warn("sketch geometry: ids not kept (%s)" % exc)


def state(sketch):
    """[(type, construction, id, internal role, blocked)] of every curve: what set_geometry
    and restore keep (for tests and diagnostics)."""
    out = []
    facades = _facades(sketch) or []
    for i, f in enumerate(facades):
        out.append((f.Geometry.TypeId, bool(f.Construction), f.Id, f.InternalType, f.Blocked))
    return out
