# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Project to Surface (no Qt): sketch curves, edges or points projected onto
faces of a body, as 3D curves.

Fusion keeps the projected curves in the active sketch (its sketches can hold 3D
curves). FreeCAD's sketches are flat, so SciForge keeps them in an object of their own,
"Projected Curves", that follows its faces and curves when they change (a parametric
feature: SciForge's FeaturePython, recomputed with the design) and belongs to the sketch
(sketch_companions.py): listed under it in the browser, shown and hidden with it, part
of its timeline step, deleted with it.

Projection types (Fusion's): Closest Point puts every point of a curve on the nearest
point of the faces; Along Vector shoots the curves along a direction (the sketch's
normal unless another is given) and keeps the side of the faces they meet first.
"""

import FreeCAD as App

from . import log, warn

TYPES = ("Closest Point", "Along Vector")
SAMPLES = 64  # points per curve for Closest Point (the curve through them is a B-spline)


def _edges(obj, subs):
    """The edges (and points as vertices) of a linked object and its sub-elements."""
    shape = obj.Shape
    if not subs:
        return list(shape.Edges) or list(shape.Vertexes)
    out = []
    for name in subs:
        try:
            out.append(shape.getElement(name))
        except Exception as exc:
            warn("Project to Surface: %s.%s: %s" % (obj.Label, name, exc))
    return out


def _faces(links):
    faces = []
    for obj, subs in links:
        for name in subs or []:
            try:
                element = obj.Shape.getElement(name)
            except Exception:
                continue
            if element.ShapeType == "Face":
                faces.append(element)
    return faces


def project(faces, sources, kind, direction=None):
    """The projected shapes (edges and vertices) of `sources` (edges / vertices) on
    `faces` (Part faces). Raises ValueError with the reason when nothing lands."""
    import Part

    if not faces:
        raise ValueError("pick at least one face to project onto")
    if not sources:
        raise ValueError("pick the curves to project")
    target = faces[0] if len(faces) == 1 else Part.makeCompound(faces)
    out = []
    for source in sources:
        if source.ShapeType == "Vertex":
            dist, pairs, _info = target.distToShape(source)
            if pairs:
                out.append(Part.Vertex(pairs[0][0]))
            continue
        if kind == TYPES[1]:
            out += _along(target, source, direction)
        else:
            curve = _closest(target, source)
            if curve is not None:
                out.append(curve)
    if not out:
        raise ValueError("the curves do not land on the faces")
    return out


def _closest(target, edge):
    """Closest Point: the curve through the nearest face point of each sample."""
    import Part

    first, last = edge.FirstParameter, edge.LastParameter
    closed = edge.isClosed()
    count = SAMPLES if not closed else SAMPLES + 1
    points = []
    for i in range(count):
        t = first + (last - first) * i / float(SAMPLES)
        p = edge.valueAt(t)
        _dist, pairs, _info = target.distToShape(Part.Vertex(p))
        if not pairs:
            continue
        q = pairs[0][0]
        if not points or (q - points[-1]).Length > 1e-7:
            points.append(q)
    if closed and len(points) > 2 and (points[0] - points[-1]).Length < 1e-6:
        points = points[:-1]
    if len(points) < 2:
        return None
    curve = Part.BSplineCurve()
    curve.interpolate(points, PeriodicFlag=closed and len(points) > 2)
    return curve.toShape()


def _along(target, edge, direction):
    """Along Vector: the edge shot along `direction`; only the hits on the side the
    curve meets first (a cylinder would also be hit on its far side)."""
    import Part

    d = App.Vector(direction if direction is not None else App.Vector(0, 0, -1))
    if d.Length < 1e-12:
        raise ValueError("the projection direction has no length")
    d.normalize()
    try:
        result = target.makeParallelProjection(edge, d)
    except Part.OCCError:
        # OCC answers "neither wire nor edge" when nothing lands
        return []
    hits = list(result.Edges)
    if not hits:
        return []
    origin = edge.valueAt(edge.FirstParameter)

    def depth(e):
        mid = e.valueAt((e.FirstParameter + e.LastParameter) / 2.0)
        return (mid - origin).dot(d)

    depths = [depth(e) for e in hits]
    near, far = min(depths), max(depths)
    if far - near > 1e-3:
        cut = (near + far) / 2.0
        hits = [e for e, z in zip(hits, depths) if z <= cut]
    return hits


# -- the feature ---------------------------------------------------------------------------
class ProjectedCurves:
    """FeaturePython proxy: the projected curves of Curves on Faces."""

    def __init__(self, obj):
        obj.Proxy = self
        self.setup(obj)

    def setup(self, obj):
        props = obj.PropertiesList
        if "Faces" not in props:
            obj.addProperty(
                "App::PropertyLinkSubListGlobal",
                "Faces",
                "Project to Surface",
                "Faces to project onto",
            )
        if "Curves" not in props:
            obj.addProperty(
                "App::PropertyLinkSubListGlobal",
                "Curves",
                "Project to Surface",
                "Sketch curves, edges or points to project",
            )
        if "Type" not in props:
            obj.addProperty(
                "App::PropertyEnumeration", "Type", "Project to Surface", "Projection type"
            )
            obj.Type = list(TYPES)
        if "Direction" not in props:
            obj.addProperty(
                "App::PropertyVector",
                "Direction",
                "Project to Surface",
                "Direction for Along Vector (the sketch's normal pointing at the faces)",
            )
            obj.Direction = App.Vector(0, 0, -1)
        obj.setEditorMode("Placement", 2)

    def onDocumentRestored(self, obj):
        self.setup(obj)
        _upgrade(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def execute(self, obj):
        import Part

        faces = _faces(obj.Faces)
        sources = []
        for linked, subs in obj.Curves:
            sources += _edges(linked, subs)
        shapes = project(faces, sources, obj.Type, obj.Direction)
        obj.Shape = Part.makeCompound(shapes)


class ViewProjectedCurves:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from . import ui_icon_path

        return ui_icon_path("sk_project")

    def dumps(self):
        return None

    def loads(self, state):
        return None


def _upgrade(obj):
    """Projected Curves saved before they belonged to their sketch (sketch-2): the sketch
    whose curves they project becomes their owner."""
    from . import sketch_companions

    try:
        if sketch_companions.is_companion(obj):
            return
        for linked, _subs in obj.Curves:
            if linked is not None and linked.TypeId == "Sketcher::SketchObject":
                sketch_companions.adopt(obj, linked, "ProjectedCurves")
                return
    except Exception as exc:
        warn("Project to Surface: %s" % exc)


def make(sketch, faces, curves, kind=TYPES[0], direction=None):
    """Add a "Projected Curves" object for the open sketch: `faces` and `curves` are
    [(object, [sub names])]. The object goes into the sketch's component. Returns it;
    raises ValueError (nothing landed) after removing it again."""
    from . import components

    # worked out first: a feature that fails its first recompute leaves errors behind
    sources = []
    for linked, subs in curves:
        sources += _edges(linked, subs)
    project(_faces(faces), sources, kind, direction)
    doc = sketch.Document
    obj = doc.addObject("Part::FeaturePython", "ProjectedCurves")
    ProjectedCurves(obj)
    from . import sketch_companions

    sketch_companions.adopt(obj, sketch, "ProjectedCurves")  # part of the sketch (Fusion)
    if App.GuiUp:
        try:
            ViewProjectedCurves(obj.ViewObject)
            obj.ViewObject.LineColor = (0.75, 0.52, 0.99)  # projected purple, as in sketches
            obj.ViewObject.PointColor = (0.75, 0.52, 0.99)
            obj.ViewObject.LineWidth = 2.0
        except Exception as exc:
            warn("Project to Surface: %s" % exc)
    obj.Label = "Projected Curves"
    obj.Faces = [(o, tuple(s)) for o, s in faces]
    obj.Curves = [(o, tuple(s)) for o, s in curves]
    obj.Type = kind
    if direction is not None:
        obj.Direction = direction
    try:
        component = components.container_of(sketch)
        if component is not None:
            component.addObject(obj)
    except Exception as exc:
        warn("Project to Surface: %s" % exc)
    obj.recompute()
    if "Invalid" in obj.State or obj.Shape.isNull() or not (obj.Shape.Edges or obj.Shape.Vertexes):
        doc.removeObject(obj.Name)
        raise ValueError("the curves do not land on the faces")
    log(
        "Project to Surface: %d curve(s), %d point(s) on %d face(s) (%s)"
        % (
            len(obj.Shape.Edges),
            len(obj.Shape.Vertexes) if not obj.Shape.Edges else 0,
            len(faces),
            kind,
        )
    )
    return obj


def sketch_edge_name(sketch, geo):
    """The name ("EdgeN") in the sketch's shape of its curve `geo`. The sketch numbers
    its curves with the construction curves counted (Edge3 in the sketch editor is curve
    2), its shape leaves construction curves out. None for a construction curve or a
    point."""
    import Part

    g = sketch.Geometry[geo]
    if sketch.getConstruction(geo) or isinstance(g, Part.Point):
        return None
    try:
        edge = g.toShape()
    except Exception:
        return None
    edge.Placement = sketch.Placement
    probes = [
        edge.valueAt(edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) * f)
        for f in (0.0, 0.37, 1.0)
    ]
    for k, candidate in enumerate(sketch.Shape.Edges):
        if abs(candidate.Length - edge.Length) > 1e-6:
            continue
        if all(candidate.distToShape(Part.Vertex(p))[0] < 1e-6 for p in probes):
            return "Edge%d" % (k + 1)
    return None


def sketch_normal_towards(sketch, faces):
    """The sketch's normal, turned to point at the faces (Along Vector's default)."""
    placement = sketch.getGlobalPlacement()
    normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
    try:
        centre = App.Vector()
        n = 0
        for obj, subs in faces:
            for name in subs:
                centre += obj.Shape.getElement(name).CenterOfMass
                n += 1
        if n:
            centre = centre * (1.0 / n)
            if (centre - placement.Base).dot(normal) < 0:
                normal = normal * -1
    except Exception:
        pass
    return normal
