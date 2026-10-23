# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sheet metal Rip (MODIFY > Rip), FreeCAD only, no Qt.

A rip opens a closed or overlapping sheet (a tube, a box) so it can be laid flat:

- Face: the whole face is cut away through the thickness (a bend face or a corner face):
  the flanges either side come apart there.
- Along Edge: a gap of the given width, through the thickness, centred on the plane that
  halves the corner at a sharp edge where two walls meet.
- Between Points: a straight slot of the given width between two points on one face (a
  vertex, or an edge with an offset along it from the edge's start).

    tool(shape, spec)            the solid cut away (spec: see DEFAULTS)
    build(shape, spec)           the shape with the rip
    make(body, base, spec)       a Rip step at the marker
"""

import FreeCAD as App
import Part

from . import bodies, sheetmetal
from . import sheetmetal_unfold as unfolder

RIP_TYPE = "Rip"
FP_TYPE = "PartDesign::FeaturePython"
TYPES = ("face", "edge", "points")
LABELS = {"face": "Face", "edge": "Along Edge", "points": "Between Points"}
DEFAULTS = {
    "type": "edge",
    "face": "",
    "edge": "",
    "point1": "",
    "point2": "",
    "offset1": 0.0,
    "offset2": 0.0,
    "gap": 1.0,
}


class RipError(ValueError):
    """A refusal with the reason."""


def _element(shape, name):
    try:
        return shape.getElement(name)
    except Exception:
        raise RipError("%s is not on the body any more: pick it again" % name)


def _thickness(shape, face):
    try:
        return unfolder.thickness_at(shape.Solids[0], face)
    except unfolder.UnfoldError as exc:
        raise RipError(str(exc))


def _point(shape, name, offset):
    """A picked vertex, or a point on a picked edge at offset from its start."""
    item = _element(shape, name)
    if name.startswith("Vertex"):
        return item.Point
    if name.startswith("Edge"):
        length = item.Length
        if offset < 0 or offset > length + 1e-9:
            raise RipError("the offset %.3f mm is off %s (%.3f mm long)" % (offset, name, length))
        return item.valueAt(item.getParameterByLength(offset))
    raise RipError("a rip point is a vertex or an edge (with an offset)")


def _face_slab(solid, face):
    T = _thickness(solid, face)
    if unfolder.is_planar(face):
        n = unfolder.normal_at(face, unfolder.inner_point(face))
        return face.extrude(n * (-T))
    try:
        slab = face.makeOffsetShape(-T, 1e-6, fill=True)
        if slab.Volume < 0:
            slab.reverse()
        return slab
    except Exception as exc:
        raise RipError("that face could not be ripped: %s" % exc)


def _edge_tool(solid, edge, gap):
    if not isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
        raise RipError("Along Edge rips a straight edge where two walls meet")
    faces = solid.ancestorsOfType(edge, Part.Face)
    if len(faces) < 2:
        raise RipError("that edge is not where two faces meet")
    mid = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
    n1 = unfolder.normal_at(faces[0], mid)
    n2 = unfolder.normal_at(faces[1], mid)
    if n1.dot(n2) > 1 - 1e-6:
        raise RipError("the faces at that edge are tangent: rip the bend face instead (Face)")
    d = edge.Vertexes[-1].Point - edge.Vertexes[0].Point
    d.normalize()
    m = n1 - n2
    m = m - d * m.dot(d)
    m.normalize()
    q = d.cross(m)
    T = min(_thickness(solid, faces[0]), _thickness(solid, faces[1]))
    depth = 2.5 * T + gap
    p0 = edge.Vertexes[0].Point
    length = (edge.Vertexes[-1].Point - p0).Length
    origin = p0 - m * (gap / 2.0) - q * depth
    return _box(origin, d, m, q, length, gap, 2 * depth)


def _box(origin, u, v, w, lu, lv, lw):
    """A box at origin with edges lu, lv, lw along the unit vectors u, v, w."""
    pts = [origin, origin + u * lu, origin + u * lu + v * lv, origin + v * lv, origin]
    face = Part.Face(Part.makePolygon(pts))
    return face.extrude(w * lw)


def _common_face(solid, p1, p2):
    best = None
    for face in solid.Faces:
        if (
            face.distToShape(Part.Vertex(p1))[0] < 1e-4
            and face.distToShape(Part.Vertex(p2))[0] < 1e-4
        ):
            if best is None or (unfolder.is_planar(face) and not unfolder.is_planar(best)):
                best = face
    return best


def _points_tool(solid, p1, p2, gap):
    if (p2 - p1).Length < 1e-6:
        raise RipError("the two rip points are the same point")
    face = _common_face(solid, p1, p2)
    if face is None:
        raise RipError("point 2 is not on the same face as point 1")
    mid = (p1 + p2) * 0.5
    n = unfolder.normal_at(face, _on(face, mid))
    u = p2 - p1
    u = u - n * u.dot(n)
    if u.Length < 1e-6:
        raise RipError("the rip line runs into the sheet; pick points on its face")
    length = u.Length
    u.normalize()
    w = n.cross(u)
    T = _thickness(solid, face)
    margin = 0.01
    origin = p1 - u * margin - w * (gap / 2.0) + n * margin
    return _box(origin, u, w, -n, length + 2 * margin, gap, T + 2 * margin)


def _on(face, point):
    """The point of the face nearest to point."""
    dist, pairs, _info = face.distToShape(Part.Vertex(point))
    return pairs[0][0] if pairs else point


def tool(shape, spec):
    """The solid a rip cuts away."""
    spec = dict(DEFAULTS, **(spec or {}))
    if shape is None or shape.isNull() or len(shape.Solids) != 1:
        raise RipError("Rip needs one sheet metal solid")
    solid = shape.Solids[0]
    kind = spec["type"]
    gap = float(spec["gap"])
    if kind != "face" and gap <= 0:
        raise RipError("the gap must be more than 0")
    if kind == "face":
        if not spec["face"]:
            raise RipError("pick the face to rip away")
        return _face_slab(solid, _element(solid, spec["face"]))
    if kind == "edge":
        if not spec["edge"]:
            raise RipError("pick the edge to rip along")
        return _edge_tool(solid, _element(solid, spec["edge"]), gap)
    if kind == "points":
        if not spec["point1"] or not spec["point2"]:
            raise RipError("pick two points on one face (vertices, or edges with offsets)")
        p1 = _point(solid, spec["point1"], float(spec["offset1"]))
        p2 = _point(solid, spec["point2"], float(spec["offset2"]))
        return _points_tool(solid, p1, p2, gap)
    raise RipError("unknown rip type %s" % kind)


def build(shape, spec):
    cutter = tool(shape, spec)
    out = shape.cut(cutter)
    try:
        out = out.removeSplitter()
    except Exception:
        pass
    solids = out.Solids
    if not solids:
        raise RipError("the rip removes the whole body")
    if len(solids) > 1:
        raise RipError(
            "the rip would cut the body in %d pieces: a rip only opens a closed shape" % len(solids)
        )
    if abs(solids[0].Volume - shape.Volume) < 1e-6:
        raise RipError("the rip cuts nothing there")
    return solids[0]


def default_gap(body):
    try:
        if body is not None and sheetmetal.is_sheet_metal_body(body):
            return float(sheetmetal.rule_for_body(body)["miter_gap"])
    except Exception:
        pass
    return DEFAULTS["gap"]


# -- the step ---------------------------------------------------------------------------------
class RipFeature:
    """Saved files store "sciforge.rip.RipFeature": never rename."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Rip"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        if add("App::PropertyEnumeration", "RipType", "Face, Along Edge or Between Points"):
            obj.RipType = [LABELS[t] for t in TYPES]
            obj.RipType = LABELS["edge"]
        add("App::PropertyLinkSub", "Face", "Face rip: the face")
        add("App::PropertyLinkSub", "Edge", "Along Edge: the edge")
        add("App::PropertyLinkSub", "Point1", "Between Points: point 1 (vertex or edge)")
        add("App::PropertyLinkSub", "Point2", "Between Points: point 2 (vertex or edge)")
        add("App::PropertyLength", "Offset1", "Offset of point 1 along its edge")
        add("App::PropertyLength", "Offset2", "Offset of point 2 along its edge")
        if add("App::PropertyLength", "Gap", "Width of the rip"):
            obj.Gap = DEFAULTS["gap"]
        bodies.mark(obj, RIP_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            base = obj.BaseFeature
            if base is None or base.Shape.isNull():
                raise RipError("Rip needs a sheet metal body before it in the timeline")
            obj.Shape = build(base.Shape, spec_of(obj))
        except Exception:
            bodies.pass_through(obj)
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _sub(link):
    if not link:
        return ""
    subs = link[1]
    if isinstance(subs, str):
        subs = [subs]
    subs = [s for s in subs or [] if s]
    return subs[0].lstrip("?") if subs else ""


def spec_of(obj):
    kind = next((t for t in TYPES if LABELS[t] == obj.RipType), "edge")
    return {
        "type": kind,
        "face": _sub(obj.Face),
        "edge": _sub(obj.Edge),
        "point1": _sub(obj.Point1),
        "point2": _sub(obj.Point2),
        "offset1": obj.Offset1.Value,
        "offset2": obj.Offset2.Value,
        "gap": obj.Gap.Value,
    }


def apply(step, base, spec):
    spec = dict(DEFAULTS, **(spec or {}))
    step.RipType = LABELS[spec["type"]]
    for prop, key in (
        ("Face", "face"),
        ("Edge", "edge"),
        ("Point1", "point1"),
        ("Point2", "point2"),
    ):
        value = (base, [spec[key]]) if spec[key] else None
        setattr(step, prop, value)
    step.Offset1 = float(spec["offset1"])
    step.Offset2 = float(spec["offset2"])
    step.Gap = max(float(spec["gap"]), 1e-6)
    step.touch()


def make(body, base, spec, name="Rip"):
    if body is None or not sheetmetal.is_sheet_metal_body(body):
        raise RipError("Rip works on sheet metal: use Convert to Sheet Metal first")
    step = bodies.insert_after_tip(body, FP_TYPE, name)
    RipFeature(step)
    step.BaseFeature = base
    if App.GuiUp:
        try:
            from .unfold_ui import ViewProviderFlatStep

            ViewProviderFlatStep(step.ViewObject, "rip")
        except Exception:
            pass
    apply(step, base, spec)
    return step
