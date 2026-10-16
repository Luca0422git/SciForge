# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's 3D Sketch, the document side (no Qt): a sketch's lines and splines whose points
may leave the sketch plane.

FreeCAD's sketches are flat (every curve of a Sketcher::SketchObject lies in its plane),
so the 3D curves of a sketch live in a companion object of it, "3D Curves"
(SciForgeType Sketch3DCurves, sketch_companions.py): listed under the sketch in the
browser, shown and hidden with it, part of its timeline step, deleted with it. Its points
are kept in the sketch's own coordinates, so the curves move with the sketch (a sketch on
a face that moves takes them along). A point placed on a point of the flat sketch is tied
to it (it follows when that point moves); the others are where they were put (Fusion's
3D points keep their place unless constrained).

The shape: one edge per line (in the order drawn), then one per spline (a curve through
its points): edges of a sketch can be a path (Sweep picks "EdgeN" of it).
"""

import FreeCAD as App

from . import log, warn
from . import sketch3d_core as core

KIND = "Sketch3DCurves"
LABEL = "3D Curves"
BLUE = (0.36, 0.70, 1.0)  # the sketch's blue for curves that can still move


def _vec(p):
    return App.Vector(p[0], p[1], p[2])


def _tuple(v):
    return (v.x, v.y, v.z)


def geo_index(sketch, geo_id):
    """The current index of the sketch geometry with id `geo_id`, or None."""
    try:
        for i in range(len(sketch.Geometry)):
            if sketch.getGeometryId(i) == geo_id:
                return i
    except Exception:
        pass
    return None


def ref_of(sketch, geo, pos):
    """The stored tie of a point to sketch vertex (geo, pos): "v:<geometry id>:<pos>"."""
    if geo is None or geo < 0:
        return ""
    try:
        return "v:%d:%d" % (sketch.getGeometryId(geo), int(pos))
    except Exception:
        return ""


def resolve(sketch, ref):
    """The sketch point a tie names (sketch coordinates), or None."""
    if not ref or not ref.startswith("v:"):
        return None
    try:
        _v, gid, pos = ref.split(":")
        index = geo_index(sketch, int(gid))
        if index is None:
            return None
        p = sketch.getPoint(index, int(pos))
        return (p.x, p.y, 0.0)
    except Exception:
        return None


class Curves3D:
    """FeaturePython proxy of a sketch's 3D curves. Saved documents store
    "sciforge.sketch3d.Curves3D": keep the name and the property names stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.setup(obj)

    def setup(self, obj):
        props = obj.PropertiesList

        def add(kind, name, doc):
            if name not in props:
                obj.addProperty(kind, name, "3D Sketch", doc)

        add("App::PropertyVectorList", "Points", "The points (sketch coordinates)")
        add("App::PropertyStringList", "PointTies", "Per point: tied to a sketch point, or ''")
        add("App::PropertyIntegerList", "Lines", "The lines: pairs of point numbers")
        add("App::PropertyStringList", "Splines", "The splines: their point numbers")
        obj.setEditorMode("Placement", 2)

    def onDocumentRestored(self, obj):
        self.setup(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def execute(self, obj):
        import Part

        from . import sketch_companions

        sketch = sketch_companions.owner(obj)
        if sketch is None:
            obj.Shape = Part.Shape()
            return
        points = resolved_points(obj, sketch)
        place = sketch_companions.sketch_placement(sketch, obj)
        world = [place.multVec(_vec(p)) for p in points]
        edges = []
        for a, b in core.pairs(list(obj.Lines)):
            if a < len(world) and b < len(world) and (world[a] - world[b]).Length > 1e-9:
                edges.append(Part.LineSegment(world[a], world[b]).toShape())
        for text in obj.Splines:
            idx = [i for i in core.parse_spline(text) if i < len(world)]
            pts = [world[i] for i in idx]
            if len(pts) >= 2:
                curve = Part.BSplineCurve()
                curve.interpolate(pts)
                edges.append(curve.toShape())
        obj.Shape = Part.makeCompound(edges) if edges else Part.Shape()


class ViewCurves3D:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from . import ui_icon_path

        return ui_icon_path("sk_spline")

    def dumps(self):
        return None

    def loads(self, state):
        return None


def resolved_points(obj, sketch):
    """The points (sketch coordinates), tied ones where their sketch point is now."""
    points = [_tuple(p) for p in obj.Points]
    ties = list(obj.PointTies)
    for i, ref in enumerate(ties[: len(points)]):
        found = resolve(sketch, ref)
        if found is not None:
            points[i] = found
    return points


def curves_of(sketch):
    """The sketch's 3D curves object, or None."""
    from . import sketch_companions

    found = sketch_companions.companions(sketch, KIND)
    return found[0] if found else None


def ensure(sketch):
    """The sketch's 3D curves object, made when there is none (no transaction here)."""
    from . import components, sketch_companions

    obj = curves_of(sketch)
    if obj is not None:
        return obj
    doc = sketch.Document
    obj = doc.addObject("Part::FeaturePython", "Curves3D")
    Curves3D(obj)
    sketch_companions.adopt(obj, sketch, KIND)
    obj.Label = LABEL
    if App.GuiUp:
        try:
            ViewCurves3D(obj.ViewObject)
            obj.ViewObject.LineColor = BLUE
            obj.ViewObject.PointColor = BLUE
            obj.ViewObject.LineWidth = 2.0
            obj.ViewObject.PointSize = 6.0
        except Exception as exc:
            warn("3D Sketch: %s" % exc)
    try:
        holder = components.container_of(sketch)
        if holder is not None:
            holder.addObject(obj)
    except Exception as exc:
        warn("3D Sketch: %s" % exc)
    return obj


def _store_point(obj, point, tie=""):
    """The index of `point` (a stored point there is shared), adding it if new."""
    points = [_tuple(p) for p in obj.Points]
    index = core.join_index(points, point)
    if index is not None:
        return index
    ties = list(obj.PointTies) + [""] * (len(points) - len(obj.PointTies))
    points.append(tuple(point))
    ties.append(tie)
    obj.Points = [_vec(p) for p in points]
    obj.PointTies = ties
    return len(points) - 1


def add_line(sketch, a, b, tie_a="", tie_b=""):
    """A 3D line from a to b (sketch coordinates); returns (object, its edge number)."""
    obj = ensure(sketch)
    ia = _store_point(obj, a, tie_a)
    ib = _store_point(obj, b, tie_b)
    lines = list(obj.Lines) + [ia, ib]
    obj.Lines = lines
    obj.recompute()
    log("3D Sketch: line (%.4g, %.4g, %.4g) - (%.4g, %.4g, %.4g)" % (tuple(a) + tuple(b)))
    return obj, len(lines) // 2


def add_spline(sketch, points, ties=None):
    """A 3D spline through the points; returns (object, its edge number)."""
    obj = ensure(sketch)
    ties = list(ties or [""] * len(points))
    idx = [_store_point(obj, p, t) for p, t in zip(points, ties)]
    splines = list(obj.Splines) + [",".join(str(i) for i in idx)]
    obj.Splines = splines
    obj.recompute()
    log("3D Sketch: spline through %d points" % len(points))
    return obj, len(obj.Lines) // 2 + len(splines)


def move_point(obj, index, point):
    """Put point `index` at `point` (sketch coordinates); a tie to a sketch point is
    dropped (Fusion: dragging a point off what it sat on frees it)."""
    points = [_tuple(p) for p in obj.Points]
    if not 0 <= index < len(points):
        raise ValueError("there is no 3D point %d" % index)
    points[index] = tuple(point)
    obj.Points = [_vec(p) for p in points]
    ties = list(obj.PointTies)
    if index < len(ties) and ties[index]:
        ties[index] = ""
        obj.PointTies = ties
    obj.recompute()


def global_points(obj):
    """The points in the coordinates of the 3D view (global)."""
    from . import sketch_companions

    sketch = sketch_companions.owner(obj)
    if sketch is None:
        return []
    place = sketch.getGlobalPlacement()
    return [place.multVec(_vec(p)) for p in resolved_points(obj, sketch)]
