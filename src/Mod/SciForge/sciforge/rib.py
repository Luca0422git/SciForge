# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Rib and Web as one SciForge PartDesign feature (FreeCAD has neither). No GUI code:
the Rib / Web commands and the golden-model builder both call this module.

Rib: an open sketch curve (a chain of lines and arcs). The rib is `thickness` thick across
the sketch plane (Symmetric about it, or One Side) and grows in the sketch plane, square to
the curve's chord, from the curve to the part: To Next fills up to the nearest faces (a
gusset in a corner), Depth grows it that far. Its ends are carried on along the curve until
they meet the part, so a rib drawn short of the walls still meets them. Flip turns the
growing side round (by default it grows towards the part).

Web: a network of open sketch curves. Each curve is `thickness` thick in the sketch plane
(Symmetric about the curve, or One Side) and grows square to the sketch plane: To Next down
to the nearest faces, Depth that far. Extend Curves carries the free ends of the curves on
until they meet the part. Flip turns the growing direction round (by default towards the
part).

Both always join the body (Fusion's rib and web have no operation choice). What would not
touch the part, or To Next with nothing to stop at, is refused with the reason.

Options (dict, see DEFAULTS): kind (rib | web), thickness, thickness_side (symmetric |
one_side), flip_side, depth_type (to_next | depth), depth, flip, extend.
"""

import json

import FreeCAD as App

from . import curves, extrude

KINDS = ("rib", "web")
SIDES = ("symmetric", "one_side")
DEPTHS = ("to_next", "depth")
DEFAULTS = {
    "kind": "rib",
    "thickness": 2.0,
    "thickness_side": "symmetric",
    "flip_side": False,
    "depth_type": "to_next",
    "depth": 10.0,
    "flip": False,
    "extend": True,
    "chain": True,
}

META = "SciForgeRib"
FP_TYPE = "PartDesign::FeaturePython"
TOL = 1e-6

owner_body = extrude.owner_body
is_sketch = extrude.is_sketch


class RibError(ValueError):
    """The rib / web cannot be built as asked; the message says why and what to do."""


def options_with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in (options or {}).items() if v is not None})
    for name, allowed in (
        ("kind", KINDS),
        ("thickness_side", SIDES),
        ("depth_type", DEPTHS),
    ):
        if merged[name] not in allowed:
            raise RibError("unknown %s %r" % (name, merged[name]))
    for name in ("thickness", "depth"):
        merged[name] = float(merged[name])
    for name in ("flip_side", "flip", "extend", "chain"):
        merged[name] = bool(merged[name])
    return merged


def check_options(options):
    if options["thickness"] <= 1e-6:
        raise RibError("The thickness must be more than 0.")
    if options["depth_type"] == "depth" and options["depth"] <= 1e-6:
        raise RibError("The depth must be more than 0.")


def word(options):
    return "web" if options["kind"] == "web" else "rib"


# -- the curves and their plane ------------------------------------------------------------------
def sketch_of(refs):
    """The one sketch all curves belong to (its plane is the rib's plane)."""
    refs = curves.normalize(refs)
    if not refs:
        raise RibError("Select a curve: click an open sketch line or arc.")
    objs = {obj.Name: obj for obj, _ in refs}
    if len(objs) != 1:
        raise RibError("Pick curves of one sketch: they must lie in one plane.")
    obj = list(objs.values())[0]
    if not is_sketch(obj):
        raise RibError("Pick sketch curves: a rib is drawn as an open line in a sketch.")
    return obj


def plane_of(sketch):
    """(a point, unit normal) of a sketch's plane, global."""
    placement = sketch.getGlobalPlacement()
    normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
    normal.normalize()
    return App.Vector(placement.Base), normal


def base_shape(feature_or_body, before=None):
    """The part the rib joins (global), or None."""
    if before is not None:
        base = before
    else:
        base = feature_or_body.Tip if feature_or_body is not None else None
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        return None
    return curves.to_global(base.Shape, base)


def _hit_distance(shape, start, direction, reach):
    """Distance from `start` along `direction` to where the ray first enters `shape`, or None."""
    import Part

    if shape is None:
        return None
    try:
        segment = Part.LineSegment(start, start + direction * reach).toShape()
        common = shape.common(segment)
    except Exception:
        return None
    best = None
    for edge in common.Edges:
        if edge.Length < 1e-9:
            continue
        for vertex in edge.Vertexes:
            d = (vertex.Point - start).dot(direction)
            if d > -1e-9 and (best is None or d < best):
                best = max(0.0, d)
    return best


def _reach(base, items):
    box = App.BoundBox()
    for shape in [base] + list(items):
        if shape is None:
            continue
        try:
            box.add(shape.BoundBox)
        except Exception:
            pass
    return max(50.0, 3.0 * box.DiagonalLength)


def _end_tangents(path):
    """((start point, outward direction), (end point, outward direction)) of an open Path."""
    t0 = path.tangent_at(0.0)
    t1 = path.tangent_at(path.length)
    return (path.start, t0 * -1.0), (path.end, t1)


def _stub(point, direction, length):
    import Part

    return Part.LineSegment(point, point + direction * length).toShape()


def _keep_touching(pieces, touch, far, word_):
    """Pieces of (region - part) that touch the curve; refuse ones that run off to the far
    end (nothing stopped them: To Next found no face)."""
    kept = []
    for piece in pieces:
        try:
            if piece.distToShape(touch)[0] > 1e-5:
                continue
        except Exception:
            continue
        if far is not None:
            try:
                if piece.distToShape(far)[0] < 1e-5:
                    raise RibError(
                        "The %s does not reach a face of the part in this direction. Flip it, "
                        "or use Depth." % word_
                    )
            except RibError:
                raise
            except Exception:
                pass
        kept.append(piece)
    return kept


# -- rib -----------------------------------------------------------------------------------------------
def _rib_tool(refs, options, base):
    import Part

    sketch = sketch_of(refs)
    origin, normal = plane_of(sketch)
    try:
        path = curves.Path(curves.refs_edges(refs))
    except curves.CurveError as exc:
        raise RibError("Rib curve: %s" % exc)
    if path.closed:
        raise RibError("A rib curve must be open (a line or an arc, not a closed loop).")
    chord = path.end - path.start
    if chord.Length < TOL:
        raise RibError("The rib curve starts and ends at the same point. Draw an open curve.")
    chord.normalize()
    side = normal.cross(chord)
    side.normalize()
    reach = _reach(base, path.edges)
    mid = path.point_at(path.length / 2.0)
    direction = _toward_part(base, mid, side, reach)
    if options["flip"]:
        direction = direction * -1.0
    # carry the ends on along the curve until they meet the part
    edges = list(path.edges)
    for (point, out), at_start in zip(_end_tangents(path), (True, False)):
        hit = _hit_distance(base, point, out, reach)
        if hit is not None and hit > 1e-6:
            stub = _stub(point, out, hit)
            edges = [stub] + edges if at_start else edges + [stub]
    length = reach if options["depth_type"] == "to_next" else options["depth"]
    extended = curves.Path(edges)
    wire = extended.wire()
    far = wire.copy()
    far.translate(direction * length)
    try:
        start_v, end_v = extended.start, extended.end
        loop = Part.Wire(
            Part.__sortEdges__(
                list(wire.Edges)
                + list(far.Edges)
                + [
                    Part.LineSegment(start_v, start_v + direction * length).toShape(),
                    Part.LineSegment(end_v, end_v + direction * length).toShape(),
                ]
            )
        )
        face = Part.Face(loop)
    except Exception as exc:
        raise RibError("The rib's outline cannot be made from this curve (%s)." % exc)
    touch = curves.Path(path.edges).wire()
    if options["depth_type"] == "to_next":
        # Like Fusion, the outline is found in the sketch plane: the band from the curve up to
        # where the plane cuts the part. (Cutting the thickened band by the part instead left
        # the rib unbounded wherever its thickness reached past the part's side.)
        if base is None:
            raise RibError("To Next needs a part to grow to. Use Depth, or make the part first.")
        section = _plane_section(base, origin, normal, reach)
        if section is None:
            raise RibError(
                "The sketch plane does not cut the part, so there is nothing for the rib to "
                "reach. Draw the rib on a plane through the part, or use Depth."
            )
        try:
            pieces = face.cut(section).Faces
        except Exception as exc:
            raise RibError("The rib's outline cannot be found (%s)." % exc)
        kept = _keep_touching(pieces, touch, far, "rib")
        if not kept:
            raise RibError("The rib curve lies inside the part: there is nothing to fill. Flip it.")
        face = kept[0] if len(kept) == 1 else kept[0].fuse(kept[1:])
    slab = _thicken(face, normal, options)
    if options["depth_type"] == "depth" and base is not None:
        if slab.distToShape(base)[0] > 1e-5:
            raise RibError("The rib does not touch the part. Move the curve onto the part.")
    return slab


def _plane_section(base, origin, normal, reach):
    """Faces where the plane (origin, normal) cuts the part, or None."""
    import Part

    plane = Part.Plane(origin, normal).toShape(-reach, reach, -reach, reach)
    try:
        cut = base.common(plane)
    except Exception:
        return None
    faces = [f for f in cut.Faces if f.Area > 1e-9]
    if not faces:
        return None
    return faces[0] if len(faces) == 1 else Part.Compound(faces)


def _thicken(face, normal, options):
    """The in-plane outline made `thickness` thick across the plane."""
    t = options["thickness"]
    face = face.copy()
    if options["thickness_side"] == "symmetric":
        face.translate(normal * (-t / 2.0))
        solid = face.extrude(normal * t)
    else:
        sign = -1.0 if options["flip_side"] else 1.0
        solid = face.extrude(normal * (t * sign))
    solids = solid.Solids
    if not solids:
        raise RibError("The rib cannot be made this thick.")
    return _fuse(solids)


def _toward_part(base, point, direction, reach):
    """`direction` or its opposite: the one where the part is nearer (default +)."""
    a = _hit_distance(base, point, direction, reach)
    b = _hit_distance(base, point, direction * -1.0, reach)
    if a is None and b is not None:
        return direction * -1.0
    if a is not None and b is not None and b < a - 1e-9:
        return direction * -1.0
    return App.Vector(direction)


# -- web -------------------------------------------------------------------------------------------------
def _band(edge, normal, left, right):
    """Face of the band around one edge in its plane, from `right` on one side to `left` on
    the other (in-plane normal = normal x tangent), with square ends. Lines and arcs are
    exact."""
    import Part

    kind = edge.Curve.TypeId
    a, b = edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)
    if kind in ("Part::GeomLine", "Part::GeomLineSegment"):
        tangent = b - a
        tangent.normalize()
        m = normal.cross(tangent)
        pts = [a - m * right, b - m * right, b + m * left, a + m * left]
        return Part.Face(Part.makePolygon(pts + [pts[0]]))
    if kind == "Part::GeomCircle":
        circle = edge.Curve
        center = App.Vector(circle.Center)
        r = circle.Radius
        axis = App.Vector(circle.Axis)
        # the in-plane normal points to the left of the curve's direction
        t0 = edge.tangentAt(edge.FirstParameter)
        m0 = normal.cross(t0)
        outward = (a - center).dot(m0) > 0  # left side is away from the centre
        r_left = r + left if outward else r - left
        r_right = r - right if outward else r + right
        if r_left <= 1e-6 or r_right <= 1e-6:
            raise RibError("The thickness is bigger than an arc's radius. Make it thinner.")
        u0, u1 = edge.FirstParameter, edge.LastParameter
        inner = Part.Circle(center, axis, min(r_left, r_right))
        outer = Part.Circle(center, axis, max(r_left, r_right))
        e_in = inner.toShape(u0, u1)
        e_out = outer.toShape(u0, u1)
        caps = [
            Part.LineSegment(e_in.valueAt(u0), e_out.valueAt(u0)).toShape(),
            Part.LineSegment(e_in.valueAt(u1), e_out.valueAt(u1)).toShape(),
        ]
        return Part.Face(Part.Wire(Part.__sortEdges__([e_in, e_out] + caps)))
    if abs(left - right) > 1e-9:
        raise RibError("One Side works with lines and arcs. Use Symmetric for this curve.")
    shape = Part.Wire([edge]).makeOffset2D(left, 2, True, True)
    faces = shape.Faces
    if not faces:
        raise RibError("This curve cannot be thickened. Use lines and arcs.")
    return faces[0]


def _free_ends(edges):
    """[(point, outward direction)] of curve ends no other curve meets."""
    ends = []
    for i, edge in enumerate(edges):
        for param, sign in ((edge.FirstParameter, -1.0), (edge.LastParameter, 1.0)):
            p = edge.valueAt(param)
            shared = any(
                (other.valueAt(other.FirstParameter) - p).Length < 1e-6
                or (other.valueAt(other.LastParameter) - p).Length < 1e-6
                for j, other in enumerate(edges)
                if j != i
            )
            if shared:
                continue
            t = App.Vector(edge.tangentAt(param)) * sign
            if t.Length > 1e-12:
                t.normalize()
                ends.append((i, param, p, t))
    return ends


def _web_tool(refs, options, base):
    import Part

    sketch = sketch_of(refs)
    _origin, normal = plane_of(sketch)
    edges = curves.refs_edges(refs)
    for edge in edges:
        if edge.isClosed():
            raise RibError("Web curves must be open lines or arcs, not closed loops.")
    reach = _reach(base, edges)
    center = App.Vector()
    for e in edges:
        center += e.valueAt(e.FirstParameter + (e.LastParameter - e.FirstParameter) / 2.0)
    center = center * (1.0 / len(edges))
    direction = _toward_part(base, center, normal * -1.0, reach)
    if options["flip"]:
        direction = direction * -1.0
    length = reach if options["depth_type"] == "to_next" else options["depth"]
    t = options["thickness"]
    if options["thickness_side"] == "symmetric":
        left, right = t / 2.0, t / 2.0
    else:
        left, right = (0.0, t) if options["flip_side"] else (t, 0.0)
    pieces = list(edges)
    if options["extend"] and base is not None:
        # carry free ends on until they meet the part, at the depth the web reaches
        for i, param, point, out in _free_ends(edges):
            hits = []
            for frac in (0.02, 0.25, 0.5, 0.75, 0.98):
                step = min(length, reach) * frac
                hit = _hit_distance(base, point + direction * step, out, reach)
                if hit is not None:
                    hits.append(hit)
            if hits:
                stretch = min(hits) + max(left, right)
                pieces.append(_stub(point, out, stretch))
    bands = [_band(e, normal, left, right) for e in pieces]
    region = bands[0] if len(bands) == 1 else bands[0].fuse(bands[1:])
    try:
        region = region.removeSplitter()
    except Exception:
        pass
    prism = region.extrude(direction * length)
    if not prism.Solids:
        raise RibError("The web cannot be made from these curves.")
    if options["depth_type"] == "depth":
        tool = _fuse(prism.Solids)
        if base is not None and tool.distToShape(base)[0] > 1e-5:
            raise RibError("The web does not touch the part. Move the curves onto the part.")
        return tool
    if base is None:
        raise RibError("To Next needs a part to grow to. Use Depth, or make the part first.")
    start = Part.Compound([_band(e, normal, left, right) for e in edges])
    far = region.copy()
    far.translate(direction * length)
    kept = _keep_touching(prism.cut(base).Solids, start, far, "web")
    if not kept:
        raise RibError("The web curves lie inside the part: there is nothing to fill. Flip it.")
    return _fuse(kept)


def _fuse(solids):
    if len(solids) == 1:
        return solids[0]
    result = solids[0].multiFuse(solids[1:])
    try:
        result = result.removeSplitter()
    except Exception:
        pass
    return result


def tool_shape(refs, options, base):
    """The rib / web solid (global) that is added to `base` (global, or None)."""
    options = options_with_defaults(options)
    check_options(options)
    if options["kind"] == "web":
        return _web_tool(refs, options, base)
    return _rib_tool(refs, options, base)


# -- meta ------------------------------------------------------------------------------------------------
def load_meta(feature):
    try:
        text = getattr(feature, META, "")
        return json.loads(text) if text else {}
    except Exception:
        return {}


def _save_meta(feature, meta):
    if META not in feature.PropertiesList:
        feature.addProperty("App::PropertyString", META, "SciForge", "Fusion rib options", 0)
        feature.setEditorMode(META, 2)
    text = json.dumps(meta, sort_keys=True)
    if getattr(feature, META) != text:
        setattr(feature, META, text)


def is_rib(obj):
    return (
        obj is not None
        and obj.TypeId == FP_TYPE
        and getattr(obj, "SciForgeType", "") in ("Rib", "Web")
    )


class RibFeature:
    """SciForge's Rib / Web step. Saved documents store "sciforge.rib.RibFeature": keep the
    name stable."""

    def __init__(self, obj, kind="rib"):
        obj.Proxy = self
        self.ensure_properties(obj, kind)

    @staticmethod
    def ensure_properties(obj, kind=None):
        def add(prop_type, name, doc, group="Rib"):
            if name not in obj.PropertiesList:
                obj.addProperty(prop_type, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSubListGlobal", "Curves", "The sketch curves")
        if add("App::PropertyLength", "Thickness", "How thick"):
            obj.Thickness = DEFAULTS["thickness"]
        if add("App::PropertyEnumeration", "ThicknessOptions", "Symmetric or one side"):
            obj.ThicknessOptions = ["Symmetric", "One Side"]
        add("App::PropertyBool", "FlipSide", "One side: the other side")
        if add("App::PropertyEnumeration", "DepthOptions", "To the next face or a depth"):
            obj.DepthOptions = ["To Next", "Depth"]
        if add("App::PropertyLength", "Depth", "How far (Depth)"):
            obj.Depth = DEFAULTS["depth"]
        add("App::PropertyBool", "Flip", "Grow the other way")
        if add("App::PropertyBool", "ExtendCurves", "Web: carry free ends on to the part"):
            obj.ExtendCurves = True
        if add("App::PropertyBool", "Refine", "Merge coplanar faces, like Fusion"):
            obj.Refine = True
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
            obj.SciForgeType = "Web" if kind == "web" else "Rib"

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base_feature = obj.BaseFeature
        base = None
        if base_feature is not None and not base_feature.Shape.isNull():
            if base_feature.Shape.Solids:
                base = curves.to_global(base_feature.Shape, base_feature)
        options = fp_options(obj)
        if base is None:
            raise RibError("A %s needs a part to join. Make the part first." % word(options))
        refs = _links(obj.Curves)
        tool = tool_shape(refs, options, base)
        result = base.fuse(tool)
        if obj.Refine:
            try:
                result = result.removeSplitter()
            except Exception:
                pass
        body = owner_body(obj)
        if body is not None:
            inverse = body.getGlobalPlacement().inverse()
            if not inverse.isIdentity():
                result = result.copy()
                result.transformShape(inverse.toMatrix(), True)
        if result.isNull() or not result.Solids:
            raise RibError("The %s could not be joined to the part." % word(options))
        obj.Shape = result.Solids[0] if len(result.Solids) == 1 else result

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _links(value):
    found = []
    for linked, subs in value or []:
        if linked is None:
            continue
        for sub in subs or [""]:
            found.append((linked, sub))
    return found


def fp_options(obj):
    return {
        "kind": "web" if obj.SciForgeType == "Web" else "rib",
        "thickness": obj.Thickness.Value,
        "thickness_side": "symmetric" if obj.ThicknessOptions == "Symmetric" else "one_side",
        "flip_side": bool(obj.FlipSide),
        "depth_type": "to_next" if obj.DepthOptions == "To Next" else "depth",
        "depth": obj.Depth.Value,
        "flip": bool(obj.Flip),
        "extend": bool(obj.ExtendCurves),
    }


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .rib_ui import ViewProviderRib

        ViewProviderRib(obj.ViewObject)
    except Exception:
        pass


# -- building ----------------------------------------------------------------------------------------------
def build(refs, options, name=None, feature=None, hide=True):
    """Create the rib / web, or rebuild `feature` with new curves / options."""
    options = options_with_defaults(options)
    check_options(options)
    refs = curves.normalize(refs)
    sketch = sketch_of(refs)
    body = owner_body(sketch)
    if body is None:
        raise RibError("The curve's sketch must belong to a body.")
    before = feature.BaseFeature if feature is not None else body.Tip
    base = None
    if before is not None and not before.Shape.isNull() and before.Shape.Solids:
        base = curves.to_global(before.Shape, before)
    if base is None:
        raise RibError("A %s needs a part to join: make the part first (Extrude)." % word(options))
    tool_shape(refs, options, base)  # fails early with the reason
    if feature is not None and owner_body(feature) is not body:
        raise RibError("The curves must be in the body of the %s." % word(options))
    if feature is None:
        feature = body.newObject(FP_TYPE, name or ("Web" if options["kind"] == "web" else "Rib"))
        RibFeature(feature, options["kind"])
        _attach_view_provider(feature)
        body.Tip = feature
    _update(feature, refs, options, hide)
    return feature


def _update(feature, refs, options, hide=True):
    feature.Curves = [(obj, [sub]) for obj, sub in refs]
    feature.Thickness = options["thickness"]
    side = "Symmetric" if options["thickness_side"] == "symmetric" else "One Side"
    if feature.ThicknessOptions != side:
        feature.ThicknessOptions = side
    if feature.FlipSide != options["flip_side"]:
        feature.FlipSide = options["flip_side"]
    depth = "To Next" if options["depth_type"] == "to_next" else "Depth"
    if feature.DepthOptions != depth:
        feature.DepthOptions = depth
    feature.Depth = options["depth"]
    if feature.Flip != options["flip"]:
        feature.Flip = options["flip"]
    if feature.ExtendCurves != options["extend"]:
        feature.ExtendCurves = options["extend"]
    feature.Refine = True
    meta = load_meta(feature)
    meta.update({"v": 1, "chain": options["chain"], "curves": [[o.Name, s] for o, s in refs]})
    _save_meta(feature, meta)
    if hide:
        hide_sketches(refs)


def hide_sketches(refs):
    if not App.GuiUp:
        return
    for obj, _ in refs:
        if is_sketch(obj):
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass


def remove(feature):
    body = owner_body(feature)
    was_tip = body is not None and body.Tip is feature
    doc = feature.Document
    try:
        if body is not None:
            body.removeObject(feature)
    except Exception:
        pass
    try:
        doc.removeObject(feature.Name)
    except Exception:
        pass
    if was_tip:
        extrude.show_tip(body)


def make(refs, options, name=None):
    return build(refs, options, name)


def update(feature, refs=None, options=None):
    old_refs, old_options = read(feature)
    merged = dict(old_options)
    merged.update(options or {})
    return build(refs if refs is not None else old_refs, merged, feature=feature)


def read(feature):
    """(curve refs, options) of an existing rib / web."""
    meta = load_meta(feature)
    options = dict(DEFAULTS)
    options.update(fp_options(feature))
    options["chain"] = bool(meta.get("chain", True))
    return _links(feature.Curves), options_with_defaults(options)
