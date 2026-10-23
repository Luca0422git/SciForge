# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Flat Pattern of a sheet metal body (FreeCAD, no Qt).

CREATE > Create Flat Pattern lays a sheet metal body flat from a stationary face (a top or
bottom face of a wall): the face lies on the XY plane facing up (z = 0, the sheet below it),
every bend developed by the rule's K-factor. Fusion keeps one flat pattern per component; it
follows later edits of the folded body. It is shown only in the FLAT PATTERN environment
(flatpattern_ui), which exports it as DXF.

The flat pattern is a ``Part::FeaturePython`` beside the body (in its component), never in
the body's history: its shape is the flat solid plus the bend lines (centre and extent
lines). BendsJson keeps every bend (up/down, angle, inner radius, allowance, lines in the
flat's XY coordinates) for the DXF and the browser.

    create(body, face)           -> the flat pattern (face: 'FaceN' of body.Shape)
    of_body(body), of_component(doc, component), all_of(doc)
    bends(fp)                    the bend dicts
    dxf_entities(fp, options)    (outer, interior, bends) for flatpattern_dxf.write
    export_dxf(fp, path, options)
"""

import json
import math

import FreeCAD as App
import Part

from . import bodies, components, curves, log, warn
from . import flatpattern_dxf as fdxf
from . import sheetmetal, sheetmetal_flat
from . import sheetmetal_unfold as unfolder

FP_KIND = "FlatPattern"


class FlatPatternError(ValueError):
    """A refusal with the reason."""


def _vec(values):
    return App.Vector(*values)


def face_memo(face):
    p = unfolder.inner_point(face)
    n = unfolder.normal_at(face, p)
    return {"p": [p.x, p.y, p.z], "n": [n.x, n.y, n.z]}


def refind(shape, name, memo):
    """The face name on shape that is the stationary face remembered in memo (the name can
    change when the folded body is edited). A face that moved along its normal (the rule's
    Thickness changed: the plate's top face is higher now) is still found: the face facing
    the same way that lies over (or under) the remembered point, the nearest one."""
    if not memo:
        return name
    p = _vec(memo["p"])
    n = _vec(memo["n"])

    def fits(face, moved=False):
        if not unfolder.is_planar(face):
            return None
        fn = unfolder.normal_at(face, unfolder.inner_point(face))
        if fn.dot(n) < 1 - 1e-6:
            return None
        plane = face.Surface
        height = (p - plane.Position).dot(plane.Axis)
        if not moved:
            if abs(height) > 1e-3:
                return None
            return face.distToShape(Part.Vertex(p))[0]
        # the point brought onto the face's plane must lie on the face
        q = p - plane.Axis * height
        if face.distToShape(Part.Vertex(q))[0] > 1e-3:
            return None
        return abs(height)

    try:
        face = shape.getElement(name)
        d = fits(face)
        if d is not None and d < 1e-3:
            return name
    except Exception:
        pass
    best = None
    for moved in (False, True):
        for i, face in enumerate(shape.Faces):
            d = fits(face, moved)
            if d is not None and (best is None or d < best[0]):
                best = (d, "Face%d" % (i + 1))
        if best is not None:
            break
    if best is None:
        raise FlatPatternError(
            "the stationary face is gone after an edit: pick it again (Edit Flat Pattern)"
        )
    return best[1]


def _xy(v):
    return (round(v.x, 9), round(v.y, 9))


class FlatPatternFeature:
    """Saved files store "sciforge.flatpattern.FlatPatternFeature": never rename."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, mode=0, group="Flat Pattern"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc, mode)
                return True
            return False

        add("App::PropertyLink", "Body", "The sheet metal body")
        add("App::PropertyString", "Face", "Stationary face of the body")
        add("App::PropertyString", "FaceMemo", "Where the stationary face is", 4)
        add("App::PropertyString", "BendsJson", "The bends (flat coordinates)", 4)
        if add("App::PropertyBool", "ShowBendLines", "Show the bend centre lines"):
            obj.ShowBendLines = True
        if add("App::PropertyBool", "ShowBendExtents", "Show the bend extent lines"):
            obj.ShowBendExtents = True
        if add("App::PropertyBool", "CornerReliefs", "The rule's corner reliefs where bends meet"):
            obj.CornerReliefs = True
        for name, doc in (
            ("Thickness", "Sheet thickness"),
            ("FlatLength", "Length of the flat (X)"),
            ("FlatWidth", "Width of the flat (Y)"),
        ):
            if add("App::PropertyLength", name, doc):
                obj.setEditorMode(name, 1)
        if add("App::PropertyFloat", "KFactor", "K-factor used"):
            obj.setEditorMode("KFactor", 1)
        if add("App::PropertyInteger", "BendCount", "Bends"):
            obj.setEditorMode("BendCount", 1)
        bodies.mark(obj, FP_KIND)
        bodies.hide_from_timeline(obj)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        body = obj.Body
        if body is None or not bodies.alive(body):
            raise FlatPatternError("the flat pattern's body is gone")
        shape = body.Shape
        if shape.isNull() or not shape.Solids:
            raise FlatPatternError("%s has no solid to lay flat" % body.Label)
        memo = json.loads(obj.FaceMemo or "{}")
        name = refind(shape, obj.Face, memo)
        if name != obj.Face:
            obj.Face = name
        k = sheetmetal_flat.k_factor(body)
        try:
            result = unfolder.unfold(shape, name, k)
        except unfolder.UnfoldError as exc:
            raise FlatPatternError(sheetmetal_flat.why_not_flat(body, str(exc)))
        frame = unfolder.flat_frame(result)
        flat = result.shape.copy()
        flat.transformShape(frame)
        bends = []
        lines = []
        for bend in result.bends:
            d = bend.as_dict()
            for key in ("start", "centre", "end"):
                a, b = getattr(bend, key)
                a, b = frame.multiply(a), frame.multiply(b)
                d[key] = [_xy(a), _xy(b)]
                shown = obj.ShowBendLines if key == "centre" else obj.ShowBendExtents
                if shown:  # the lines drawn: line_kinds() says which is which
                    lines.append(Part.makeLine(App.Vector(a.x, a.y, 0), App.Vector(b.x, b.y, 0)))
            bends.append(d)
        if obj.CornerReliefs:
            flat = with_corner_reliefs(flat, bends, body, result.thickness, folded=shape)
        text = json.dumps(bends, sort_keys=True)
        if obj.BendsJson != text:
            obj.BendsJson = text
        obj.Shape = Part.makeCompound([flat] + lines)  # after BendsJson: the view colours
        face = result.stationary
        obj.FaceMemo = json.dumps(face_memo(face))
        bb = flat.BoundBox
        obj.Thickness = result.thickness
        obj.FlatLength = bb.XLength
        obj.FlatWidth = bb.YLength
        obj.KFactor = k
        obj.BendCount = len(bends)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


CLOSURE_KIND = "SheetMetalCornerClosure"  # sm-more's Corner Closure step


def _bend_axis(folded, bend):
    """(centre, direction) of a bend's axis in the folded part, or None."""
    try:
        surface = folded.Faces[bend["face"] - 1].Surface
        c, a = surface.Center, surface.Axis
    except Exception:
        return None
    return (c.x, c.y, c.z), (a.x, a.y, a.z)


def corner_settings(body):
    """What the body's own steps say about its 2-bend corners: (closures, flanges).
    closures: [(edge, edge)] the two flange ends of each Corner Closure step (sm-more): that
    corner keeps the Corner Closure's own relief (already in the folded part, or none).
    flanges: [((x, y, z), corner)] the corners an edge Flange (sm-forming) mitres, with the
    relief it asks for there (its Override Corner Relief, else the rule's)."""
    closures, flanges = [], []
    try:
        from . import sheetmetal_flange as flange
    except ImportError:
        flange = None
    try:
        steps = list(body.Group)
    except Exception:
        steps = []
    for obj in steps:
        try:
            if bodies.kind(obj) == CLOSURE_KIND:
                edges = []
                for link in (obj.DominantEdge, obj.SubmissiveEdge):
                    if link and link[1]:
                        edge = curves.edge_of(link[0], link[1][0])
                        if edge is not None:
                            edges.append(edge)
                if len(edges) == 2:
                    closures.append(tuple(edges))
            elif flange is not None and flange.is_flange(obj):
                for corner in flange.corner_reliefs(obj):
                    p = corner["point"]
                    flanges.append(((p.x, p.y, p.z), corner))
        except Exception as exc:
            warn("flat pattern: the corner settings of %s not read: %s" % (obj.Label, exc))
    return closures, flanges


def _closed(closures, meet, reach):
    point = Part.Vertex(App.Vector(*meet))
    for pair in closures:
        try:
            if all(edge.distToShape(point)[0] <= reach for edge in pair):
                return True
        except Exception:
            continue
    return False


def with_corner_reliefs(flat, bends, body, thickness, folded=None):
    """The flat with a 2-bend corner relief (Round: a hole of the Size's diameter, Square: a
    square of that side) where two bends meet at a corner, at the Relief Placement
    (Intersection: where their centre lines cross; Tangent: reaching the far side of both
    bend zones). With `folded` (the folded part, whose bend faces the bends name) a relief
    goes only at the corners an edge Flange mitred, the Flange's own (its Override Corner
    Relief, else the rule's); a corner a Corner Closure step closed keeps the closure's
    relief, and corners made otherwise (sm-more's Bend lines or Hems, a converted part) keep
    what the folded part has. Without `folded`: the rule's relief at every corner. The folded
    part keeps its corner as the Flange made it (sm-forming's known gap): this relief is the
    flat's."""
    from . import flatpattern_core as core

    if len(bends) < 2:
        return flat
    thickness = float(thickness)
    try:
        rule = sheetmetal.rule_for_body(body)
    except Exception:
        return flat
    rule_shape, rule_size = core.relief_size(rule)
    rule_place = rule.get("corner_relief_2bend_placement", "intersection")
    closures, flanges = corner_settings(body) if folded is not None else ([], [])
    radius = max(b["radius"] for b in bends)
    reach_3d = 2.0 * (radius + thickness) + 2.0
    biggest = max([rule_size] + [float(c.get("size") or 0.0) for _p, c in flanges])
    reach = max(b["allowance"] for b in bends) + 2 * thickness + biggest
    tools = []
    for x, y, i, j in core.corner_points(bends, reach):
        shape, size, place = rule_shape, rule_size, rule_place
        if folded is not None:
            a, b = _bend_axis(folded, bends[i]), _bend_axis(folded, bends[j])
            meet = core.axes_meet(a[0], a[1], b[0], b[1]) if a and b else None
            if meet is not None and _closed(closures, meet, reach_3d):
                log(
                    "flat pattern: the corner at bends %d and %d is the Corner Closure's"
                    % (i + 1, j + 1)
                )
                continue
            k = None if meet is None else core.nearest(meet, [p for p, _c in flanges], reach_3d)
            if k is None:
                # a corner no edge Flange mitred (sm-more's Bend lines or Hems, a converted
                # part): the folded part has the corner it was made with, the flat keeps it
                continue
            corner = flanges[k][1]
            shape = corner.get("shape", shape)
            place = corner.get("placement", place)
            size = float(corner.get("size", 0.0) or 0.0)
        if shape not in core.RELIEF_SHAPES or size <= 0:
            continue
        centre = core.relief_centre(
            place, core.bend_frame(bends[i]), core.bend_frame(bends[j]), size
        )
        cx, cy = centre if centre is not None else (x, y)
        base = App.Vector(cx, cy, -thickness - 1.0)
        if shape == "round":
            tools.append(Part.makeCylinder(size / 2.0, thickness + 2.0, base))
        else:
            (x1, y1), (x2, y2) = [p[:2] for p in bends[i]["centre"]]
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            box = Part.makeBox(size, size, thickness + 2.0, App.Vector(-size / 2, -size / 2, 0))
            box.rotate(App.Vector(), App.Vector(0, 0, 1), angle)
            box.translate(base)
            tools.append(box)
    if not tools:
        return flat
    try:
        cut = flat.cut(tools).removeSplitter()
    except Exception as exc:
        warn("corner reliefs not cut: %s" % exc)
        return flat
    if len(cut.Solids) != 1:
        warn("corner reliefs would cut the flat apart: left out")
        return flat
    return cut.Solids[0]


def is_flat_pattern(obj):
    return bodies.alive(obj) and bodies.kind(obj) == FP_KIND


def all_of(doc):
    return [o for o in doc.Objects if is_flat_pattern(o)] if doc is not None else []


def of_body(body):
    if body is None:
        return None
    for obj in all_of(body.Document):
        if obj.Body is body:
            return obj
    return None


def of_component(doc, component):
    """Fusion: one flat pattern per component (component None: the root)."""
    for obj in all_of(doc):
        if components.container_of(obj) is component:
            return obj
    return None


def check_face(body, face):
    """Raise FlatPatternError when face cannot be the stationary face of body's flat."""
    if body is None or not sheetmetal.is_sheet_metal_body(body):
        raise FlatPatternError(
            "a flat pattern is made of a sheet metal body: use Convert to Sheet Metal first"
        )
    try:
        unfolder.unfold(body.Shape, face, sheetmetal_flat.k_factor(body))
    except unfolder.UnfoldError as exc:
        raise FlatPatternError(sheetmetal_flat.why_not_flat(body, str(exc)))


def create(body, face, name="FlatPattern"):
    """A flat pattern of body from its face 'FaceN' (of body.Shape), in the body's component.
    Raises FlatPatternError (nothing made) when it cannot be laid flat."""
    doc = body.Document
    component = components.container_of(body)
    other = of_component(doc, component)
    if other is not None:
        raise FlatPatternError(
            "this component already has a flat pattern (%s): Fusion keeps one per component; "
            "delete it to make a new one" % other.Label
        )
    check_face(body, face)
    obj = doc.addObject("Part::FeaturePython", name)
    FlatPatternFeature(obj)
    obj.Label = "Flat Pattern"
    obj.Body = body
    obj.Face = face
    obj.FaceMemo = json.dumps(face_memo(body.Shape.getElement(face)))
    if component is not None:
        try:
            component.addObject(obj)
        except Exception as exc:
            warn("flat pattern not put in %s: %s" % (component.Label, exc))
    if App.GuiUp:
        try:
            from .flatpattern_ui import ViewProviderFlatPattern

            ViewProviderFlatPattern(obj.ViewObject)
        except Exception as exc:
            warn("flat pattern view: %s" % exc)
    obj.recompute()
    log("flat pattern of %s from %s" % (body.Label, face))
    return obj


def line_kinds(fp):
    """'up' / 'down' / 'extent' of the bend lines drawn after the flat solid's edges, in
    the order execute() adds them."""
    kinds = []
    for bend in bends(fp):
        if fp.ShowBendExtents:
            kinds.append("extent")
        if fp.ShowBendLines:
            kinds.append("up" if bend.get("up") else "down")
        if fp.ShowBendExtents:
            kinds.append("extent")
    return kinds


def bends(fp):
    try:
        return json.loads(fp.BendsJson or "[]")
    except Exception:
        return []


def flat_solid(fp):
    solids = fp.Shape.Solids
    return solids[0] if solids else None


# -- DXF ------------------------------------------------------------------------------------
def _edge_entity(edge, opts):
    curve = edge.Curve
    a = edge.valueAt(edge.FirstParameter)
    b = edge.valueAt(edge.LastParameter)
    if isinstance(curve, (Part.Line, Part.LineSegment)):
        return ("line", a.x, a.y, b.x, b.y)
    if isinstance(curve, Part.Circle):
        c = curve.Center
        if edge.isClosed():
            return ("circle", c.x, c.y, curve.Radius)
        s = math.degrees(math.atan2(a.y - c.y, a.x - c.x))
        e = math.degrees(math.atan2(b.y - c.y, b.x - c.x))
        if curve.Axis.z < 0:
            s, e = e, s
        return ("arc", c.x, c.y, curve.Radius, s, e)
    if not opts["splines_to_polylines"]:
        try:
            nurbs = edge.toNurbs().Edges[0].Curve
            if isinstance(nurbs, Part.BSplineCurve) and not nurbs.isRational():
                poles = [(p.x, p.y) for p in nurbs.getPoles()]
                return ("spline", nurbs.Degree, list(nurbs.KnotSequence), poles)
        except Exception:
            pass
    pts = edge.discretize(Deflection=max(float(opts["tolerance"]), 1e-4))
    return ("polyline", [(p.x, p.y) for p in pts], False)


def dxf_entities(fp, options=None):
    """(outer, interior, bends) of the flat pattern's top face, for flatpattern_dxf.write."""
    opts = dict(fdxf.DEFAULT_OPTIONS, **(options or {}))
    solid = flat_solid(fp)
    if solid is None:
        raise FlatPatternError("the flat pattern has no shape: it could not be computed")
    top = unfolder.flat_top_face(solid)
    if top is None:
        raise FlatPatternError("the flat pattern has no top face")
    outer = [_edge_entity(e, opts) for e in top.OuterWire.OrderedEdges]
    interior = []
    for wire in top.Wires:
        if wire.isSame(top.OuterWire):
            continue
        interior.extend(_edge_entity(e, opts) for e in wire.OrderedEdges)
    return outer, interior, bends(fp)


def export_dxf(fp, path, options=None):
    """Write the flat pattern as DXF; returns the path written."""
    if not path.lower().endswith(".dxf"):
        path += ".dxf"
    outer, interior, bend_list = dxf_entities(fp, options)
    text = fdxf.write(outer, interior, bend_list, options)
    with open(path, "w", encoding="ascii", errors="replace") as handle:
        handle.write(text)
    log(
        "flat pattern DXF: %s (%d outline, %d interior, %d bends)"
        % (path, len(outer), len(interior), len(bend_list))
    )
    return path
