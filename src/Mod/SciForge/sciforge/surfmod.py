# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY on surface bodies (wave 6, surface-4): the document side, no Qt. The
dialogs (surfmod_ui.py), the SOLID tools that now take surface bodies (split, delete, move,
align, pattern, scale, press pull) and the golden-model builder (ai/ops/surface3_ops.py) all
call this module. The rules without FreeCAD are in surfmod_core.py.

The steps (PartDesign::FeaturePython in the surface body, each with its SciForgeType):
  SurfaceBlendFeature   Fillet / Chamfer of edges between two faces of a surface body
  SurfaceDeleteFeature  faces removed without healing (Delete on the SURFACE tab)
  SurfaceMergeFeature   adjacent faces on one surface merged into one face
  SurfacePressPullFeature  a flat face moved along its normal, the faces around it follow

Shapes: a step's BaseFeature.Shape and its own Shape are in the body's coordinates (as every
PartDesign step); picks are element names of the step before ("Edge7", "Face3") kept in a
LinkSub property, so picks.py follows them when earlier steps change.
"""

import math

import FreeCAD as App
import Part

from . import bodies
from . import surfmod_core as core
from .surfmod_core import NeedsPick, SurfaceModifyError  # noqa: F401 (re-exported)

TYPE = "PartDesign::FeaturePython"
META = "SciForgeSurfaceModify"
SAME = 1e-6


# -- shapes ----------------------------------------------------------------------------------
def has_faces(shape):
    try:
        return shape is not None and not shape.isNull() and bool(shape.Faces)
    except Exception:
        return False


def is_open_shape(shape):
    """Faces and no solid: what a surface body holds."""
    try:
        return has_faces(shape) and not shape.Solids
    except Exception:
        return False


def body_has_faces(body):
    """A body with something in it (a solid or a surface): what Move, Scale, Align and the
    patterns of bodies can work on."""
    try:
        return bodies.alive(body) and has_faces(body.Shape)
    except Exception:
        return False


def is_surface_body(body):
    """Fusion's surface body (surface.py owns the rule: faces and no solid)."""
    try:
        from . import surface

        return surface.is_surface_body(body)
    except Exception:
        return False


def sew(faces, tolerance=0.0):
    from . import surface_geom

    return surface_geom.sew(list(faces), tolerance)


def _result(shape, what):
    if shape is None or shape.isNull() or not shape.Faces:
        raise SurfaceModifyError("%s leaves no face of the body." % what)
    if not shape.isValid():
        fixed = shape.copy()
        try:
            fixed.fix(1e-7, 1e-7, 1e-4)
        except Exception:
            pass
        if not fixed.isValid():
            raise SurfaceModifyError(
                "%s makes a broken surface here. Try other values or other picks." % what
            )
        shape = fixed
    return shape


def element(shape, name):
    try:
        return shape.getElement(name)
    except Exception:
        raise SurfaceModifyError(
            "%s no longer exists (an earlier step changed the body). Edit the step and pick "
            "again." % name
        )


def faces_of_edge(shape, edge):
    try:
        return list(shape.ancestorsOfType(edge, Part.Face))
    except Exception:
        return []


def _index(items, item):
    for i, other in enumerate(items, start=1):
        if other.isSame(item):
            return i
    return 0


def edge_name(shape, edge):
    i = _index(shape.Edges, edge)
    return "Edge%d" % i if i else ""


def face_name(shape, face):
    i = _index(shape.Faces, face)
    return "Face%d" % i if i else ""


# -- Fillet / Chamfer --------------------------------------------------------------------------
def _tangent_at(edge, vertex):
    """The edge's direction leaving `vertex`."""
    p = vertex.Point
    first = (edge.valueAt(edge.FirstParameter) - p).Length
    last = (edge.valueAt(edge.LastParameter) - p).Length
    if first <= last:
        return edge.tangentAt(edge.FirstParameter)
    return edge.tangentAt(edge.LastParameter) * -1.0


def tangent_chain(shape, edges):
    """The picked edges plus every edge between two faces that continues one of them
    smoothly (Fusion's Tangent Chain)."""
    found = [e for e in edges]
    queue = list(edges)
    while queue:
        edge = queue.pop()
        for vertex in edge.Vertexes:
            try:
                others = shape.ancestorsOfType(vertex, Part.Edge)
            except Exception:
                others = []
            for other in others:
                if any(other.isSame(f) for f in found):
                    continue
                if len(faces_of_edge(shape, other)) != 2:
                    continue
                try:
                    a = _tangent_at(edge, vertex)
                    b = _tangent_at(other, vertex)
                except Exception:
                    continue
                if a.Length < SAME or b.Length < SAME:
                    continue
                if a.getAngle(b) > math.pi - math.radians(1.0):  # one runs on into the other
                    found.append(other)
                    queue.append(other)
    return found


def blend_edges(shape, names, tangent=True):
    """The edges (of `shape`) a surface fillet / chamfer rounds; refused with the reason."""
    if not names:
        raise NeedsPick("Select edges of a surface body: each between two of its faces.")
    edges = [element(shape, n) for n in names]
    for edge in edges:
        owners = faces_of_edge(shape, edge)
        if len(owners) < 2:
            raise SurfaceModifyError(
                "That edge is on the outside of the surface (it touches one face): there is "
                "nothing to round. Fillet an edge between two faces of one body; two separate "
                "surface bodies are stitched first (Stitch), as in Fusion."
            )
    if tangent:
        edges = tangent_chain(shape, edges)
    return edges


def blend_shape(shape, names, kind, options):
    """The surface `shape` with its edges `names` rounded (kind "surface_fillet") or
    bevelled ("surface_chamfer")."""
    options = core.with_defaults(kind, options)
    core.check_values(kind, options)
    edges = blend_edges(shape, names, bool(options.get("tangent_chain", True)))
    try:
        if kind == "surface_fillet":
            made = shape.makeFillet(float(options["radius"]), edges)
        else:
            d1, d2 = core.chamfer_distances(options)
            if abs(d1 - d2) < 1e-9:
                made = shape.makeChamfer(d1, edges)
            else:
                made = shape.makeChamfer(d1, d2, edges)
    except Exception as exc:
        size = "radius" if kind == "surface_fillet" else "distance"
        raise SurfaceModifyError(
            "The %s is too big for the faces around the edge (or the kernel failed: %s). "
            "Try a smaller %s." % (size, _text(exc), size)
        )
    if made.isNull() or not made.Faces:
        raise SurfaceModifyError("The edges could not be rounded here. Try a smaller size.")
    if len(made.Faces) <= len(shape.Faces) - 1:
        raise SurfaceModifyError("The size is too big: faces would disappear. Try smaller.")
    result = sew(made.Faces) if not made.Shells or made.ShapeType == "Compound" else made
    return _result(result, core.TITLES[kind])


def _text(exc):
    text = str(exc).strip()
    return text if text and "unknown" not in text.lower() else "no reason given"


# -- Delete without healing ---------------------------------------------------------------------
def remove_faces(shape, names):
    """Fusion's Delete on the SURFACE tab: the faces go, the hole stays (a solid becomes an
    open surface). The faces left are sewn where they still meet."""
    if not names:
        raise NeedsPick("Select the faces to delete.")
    picked = [element(shape, n) for n in names]
    rest = [f.copy() for f in shape.Faces if not any(f.isSame(p) for p in picked)]
    if len(rest) == len(shape.Faces):
        raise SurfaceModifyError("None of the picked faces is on the body.")
    if not rest:
        raise SurfaceModifyError(
            "That would delete every face of the body. Delete the body instead (select it in "
            "the browser, then Delete)."
        )
    return _result(sew(rest), "Delete Face")


# -- Merge -------------------------------------------------------------------------------------
def _unify(shape):
    try:
        from Part import ShapeUpgrade

        usd = ShapeUpgrade.UnifySameDomain(shape, True, True, False)
        usd.build()
        return usd.shape()
    except Exception:
        return shape.removeSplitter()


def merge_faces(shape, names):
    """Fusion's Merge: picked adjacent faces of one surface body become one face where they
    lie on one surface. Returns (shape, the dialog's message)."""
    picked = [element(shape, n) for n in names]
    if len(picked) < 2:
        raise NeedsPick("Select two or more faces next to each other on one surface body.")
    from . import surface_geom

    group = sew(picked)
    if len(surface_geom.shells_or_faces(group)) > 1:
        raise SurfaceModifyError("The picked faces must touch each other (share edges).")
    merged = _unify(group)
    message = core.merge_outcome(len(picked), len(merged.Faces))
    rest = [f.copy() for f in shape.Faces if not any(f.isSame(p) for p in picked)]
    result = sew(rest + [f.copy() for f in merged.Faces])
    return _result(result, "Merge"), message


# -- Press Pull on a surface face ---------------------------------------------------------------
def _plane_of(face):
    if face.Surface.TypeId != "Part::GeomPlane":
        raise SurfaceModifyError(
            "SciForge pushes or pulls flat faces of a surface body. For a curved face use "
            "Offset (SURFACE > CREATE), or Move."
        )
    u0, u1, v0, v1 = face.ParameterRange
    normal = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    return face.CenterOfMass, App.Vector(normal).normalize()


def _into(face, edge, point):
    """The direction from `point` on `edge` into `face` (in the face, square to the edge)."""
    from . import surface_geom

    u = edge.Curve.parameter(point)
    try:
        u = edge.parameterAt(Part.Vertex(point))
    except Exception:
        pass
    tangent = edge.tangentAt(u)
    return surface_geom.away_in_face(face, edge, point, tangent) * -1.0  # (away: out of it)


def _keep_side(pieces, origin, normal, sign):
    kept = []
    for piece in pieces:
        try:
            c = piece.CenterOfMass
        except Exception:
            c = piece.BoundBox.Center
        if (c - origin).dot(normal) * sign > SAME:
            kept.append(piece)
    return kept


def _trim(face, origin, normal, sign, around):
    """`face` cut back to the plane (origin, normal): the part on the `sign` side stays."""
    import BOPTools.SplitAPI as split_api

    size = max(around.BoundBox.DiagonalLength, 1.0) * 4.0
    plane = Part.Plane(origin, normal)
    u, v = plane.parameter(face.CenterOfMass)
    cutter = plane.toShape(u - size, u + size, v - size, v + size)
    try:
        pieces = split_api.slice(face, [cutter], "Split").Faces
    except Exception as exc:
        raise SurfaceModifyError("A face next to it cannot be cut back (%s)." % _text(exc))
    kept = _keep_side(pieces, origin, normal, sign)
    if not kept:
        raise SurfaceModifyError(
            "That is further than the faces next to it reach: they would disappear. Use a "
            "smaller distance."
        )
    return kept


def press_pull(shape, names, distance):
    """The surface `shape` with its flat faces `names` moved by `distance` along their
    normals (Fusion's Press Pull / Offset Face on a surface body). The faces around a picked
    face follow it: a face that runs from the shared edge along the move grows by a band
    or is cut back to the moved face. Refused with the reason when a face around it does
    not run along the move (SciForge's kernel has no general face offset for open bodies)."""
    core.check_values("surface_press_pull", {"distance": distance})
    d = float(distance)
    if not names:
        raise NeedsPick("Select a flat face of a surface body.")
    picked = [element(shape, n) for n in names]
    planes = [_plane_of(f) for f in picked]
    normal0 = planes[0][1]
    for _o, n in planes[1:]:
        if n.getAngle(normal0) > 1e-6:
            raise SurfaceModifyError("Pick faces that face the same way (parallel).")
    moved = []
    for face, (_origin, n) in zip(picked, planes):
        copy = face.copy()
        copy.translate(n * d)
        moved.append(copy)
    changed = {}  # index of a neighbour face -> its new faces
    order = []
    for face, (origin, n) in zip(picked, planes):
        for edge in face.Edges:
            owners = [
                f
                for f in faces_of_edge(shape, edge)
                if not f.isSame(face) and not any(f.isSame(p) for p in picked)
            ]
            for other in owners:
                key = _index(shape.Faces, other)
                current = changed.get(key)
                if current is None:
                    current = [other.copy()]
                    order.append(key)
                mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
                for frac in (0.25, 0.5, 0.75):
                    p = edge.valueAt(
                        edge.FirstParameter + frac * (edge.LastParameter - edge.FirstParameter)
                    )
                    uv = other.Surface.parameter(p)
                    if abs(App.Vector(other.normalAt(*uv)).dot(n)) > 1e-4:
                        raise SurfaceModifyError(
                            "The faces around it do not run along the pull (they meet it at an "
                            "angle). SciForge can push or pull a surface face when the faces "
                            "next to it run along the move, like the walls under a lid. Use "
                            "Offset (SURFACE > CREATE) or Move instead."
                        )
                into = _into(other, edge, mid)
                action = core.press_pull_action(into.dot(n), d)
                if action == "extend":
                    band = edge.copy().extrude(n * d)
                    current = _join_band(current, band)
                else:
                    sign = 1.0 if into.dot(n) > 0 else -1.0
                    target = origin + n * d
                    trimmed = []
                    for piece in current:
                        trimmed += _trim(piece, target, n, sign, shape)
                    current = trimmed
                changed[key] = current
    faces = []
    for i, f in enumerate(shape.Faces, start=1):
        if any(f.isSame(p) for p in picked):
            continue
        if i in changed:
            faces += changed[i]
        else:
            faces.append(f.copy())
    faces += moved
    result = sew(faces)
    from . import surface_geom

    if len(surface_geom.free_edges(result)) > len(surface_geom.free_edges(shape)) + 4 * len(picked):
        raise SurfaceModifyError(
            "The moved face no longer meets the faces around it. Try a smaller distance."
        )
    return _result(result, "Press Pull")


def _join_band(faces, band):
    """A neighbour face grown by `band`: one face again where they lie on one surface."""
    joined = sew([f for f in faces] + list(band.Faces))
    try:
        joined = _unify(joined)
    except Exception:
        pass
    return [f.copy() for f in joined.Faces]


# -- the steps ---------------------------------------------------------------------------------
class SurfaceModifyFeature:
    """Every surface-4 step. Saved in files as "sciforge.surfmod.SurfaceModifyFeature": keep
    the name and the properties. Its SciForgeType says what it does (surfmod_core.TYPES)."""

    def __init__(self, obj, kind):
        obj.Proxy = self
        self.ensure_properties(obj, kind)

    @staticmethod
    def ensure_properties(obj, kind=None):
        def add(kind_, name, doc, group="Surface Modify", mode=0):
            if name not in obj.PropertiesList:
                obj.addProperty(kind_, name, group, doc, mode)
                return True
            return False

        if kind is not None:
            bodies.mark(obj, core.TYPES[kind])
        kind = kind_of(obj)
        add("App::PropertyLinkSub", "Picks", "The picked edges or faces (on the step before)")
        if kind == "surface_fillet":
            if add("App::PropertyLength", "Radius", "Radius"):
                obj.Radius = 1.0
        if kind == "surface_chamfer":
            if add("App::PropertyEnumeration", "ChamferType", "Chamfer Type"):
                obj.ChamferType = [core.CHAMFER_LABELS[k] for k in core.CHAMFER_TYPES]
            if add("App::PropertyLength", "Distance", "Distance"):
                obj.Distance = 1.0
            if add("App::PropertyLength", "Distance2", "Distance 2"):
                obj.Distance2 = 1.0
            if add("App::PropertyAngle", "Angle", "Angle"):
                obj.Angle = 45.0
            add("App::PropertyBool", "Flip", "Flip the sides of the chamfer")
        if kind in ("surface_fillet", "surface_chamfer"):
            if add("App::PropertyBool", "TangentChain", "Tangent Chain"):
                obj.TangentChain = True
        if kind == "surface_press_pull":
            add("App::PropertyDistance", "Distance", "Distance (+ along the face's normal)")

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            base = obj.BaseFeature
            if base is None or base.Shape.isNull() or not base.Shape.Faces:
                raise SurfaceModifyError("There is no body before this step.")
            obj.Shape = compute(obj, base.Shape)
        except Exception:
            bodies.pass_through(obj)  # the body as it was before it; the step shows red
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def kind_of(obj):
    return core.kind_of_type(bodies.kind(obj))


def is_step(obj):
    return kind_of(obj) is not None


def picks_of(obj):
    link = getattr(obj, "Picks", None)
    if not link or link[0] is None:
        return None, []
    return link[0], [s for s in link[1] if s]


def options_of(obj):
    kind = kind_of(obj)
    o = core.with_defaults(kind, {})
    if kind == "surface_fillet":
        o["radius"] = obj.Radius.Value
    if kind == "surface_chamfer":
        labels = {v: k for k, v in core.CHAMFER_LABELS.items()}
        o["chamfer_type"] = labels.get(str(obj.ChamferType), "equal")
        o["distance"] = obj.Distance.Value
        o["distance2"] = obj.Distance2.Value
        o["angle"] = obj.Angle.Value
        o["flip"] = bool(obj.Flip)
    if kind in ("surface_fillet", "surface_chamfer"):
        o["tangent_chain"] = bool(obj.TangentChain)
    if kind == "surface_press_pull":
        o["distance"] = obj.Distance.Value
    return o


def _names_on(obj, base_shape):
    """The picked element names, on the shape this step builds on."""
    source, names = picks_of(obj)
    if source is None or source is obj.BaseFeature:
        return names
    found = []
    for name in names:  # picked on an earlier step: the same element on the base now
        try:
            elem = source.Shape.getElement(name)
        except Exception:
            raise SurfaceModifyError("%s no longer exists (an earlier step changed it)." % name)
        found.append(_same_place(base_shape, elem) or name)
    return found


def _same_place(shape, elem):
    items = shape.Faces if elem.ShapeType == "Face" else shape.Edges
    prefix = "Face" if elem.ShapeType == "Face" else "Edge"
    mid = elem.CenterOfMass
    for i, other in enumerate(items, start=1):
        try:
            if abs(other.Area if prefix == "Face" else other.Length) < 0:
                continue
            if (other.CenterOfMass - mid).Length < 1e-6:
                return "%s%d" % (prefix, i)
        except Exception:
            continue
    return ""


def compute(obj, base_shape):
    kind = kind_of(obj)
    names = _names_on(obj, base_shape)
    o = options_of(obj)
    if kind in ("surface_fillet", "surface_chamfer"):
        return blend_shape(base_shape, names, kind, o)
    if kind == "surface_delete_face":
        return remove_faces(base_shape, names)
    if kind == "surface_merge":
        return merge_faces(base_shape, names)[0]
    if kind == "surface_press_pull":
        return press_pull(base_shape, names, o["distance"])
    raise SurfaceModifyError("Unknown step %r." % kind)


def check_picks(kind, base_shape, names):
    """Refuse picks the step cannot use, before its values are looked at (the dialog says
    why at the click: a free edge, a curved face for Press Pull)."""
    if kind in ("surface_fillet", "surface_chamfer"):
        blend_edges(base_shape, names, False)
    elif kind == "surface_press_pull":
        for name in names:
            _plane_of(element(base_shape, name))


def preview(kind, base_shape, names, options):
    """The result without a step (the dialog's check before OK; raises with the reason)."""
    if kind in ("surface_fillet", "surface_chamfer"):
        return blend_shape(base_shape, names, kind, options)
    if kind == "surface_delete_face":
        return remove_faces(base_shape, names)
    if kind == "surface_merge":
        return merge_faces(base_shape, names)[0]
    if kind == "surface_press_pull":
        return press_pull(base_shape, names, options.get("distance", 0.0))
    raise SurfaceModifyError("Unknown step %r." % kind)


def apply(obj, base, names, options):
    """Set a step's picks and values (does not recompute)."""
    kind = kind_of(obj)
    options = core.with_defaults(kind, options)
    current = picks_of(obj)
    if current[0] is not base or current[1] != list(names):
        obj.Picks = (base, list(names))
    if kind == "surface_fillet":
        if abs(obj.Radius.Value - float(options["radius"])) > 1e-12:
            obj.Radius = float(options["radius"])
    if kind == "surface_chamfer":
        label = core.CHAMFER_LABELS[options["chamfer_type"]]
        if str(obj.ChamferType) != label:
            obj.ChamferType = label
        for prop, key in (("Distance", "distance"), ("Distance2", "distance2")):
            if abs(getattr(obj, prop).Value - float(options[key])) > 1e-12:
                setattr(obj, prop, float(options[key]))
        if abs(obj.Angle.Value - float(options["angle"])) > 1e-12:
            obj.Angle = float(options["angle"])
        if bool(obj.Flip) != bool(options["flip"]):
            obj.Flip = bool(options["flip"])
    if kind in ("surface_fillet", "surface_chamfer"):
        if bool(obj.TangentChain) != bool(options.get("tangent_chain", True)):
            obj.TangentChain = bool(options.get("tangent_chain", True))
    if kind == "surface_press_pull":
        if abs(obj.Distance.Value - float(options["distance"])) > 1e-12:
            obj.Distance = float(options["distance"])


def make(kind, body, base, names, options, name=None, check=True):
    """A new step of `kind` at the end of `body`, on `base` (normally body.Tip). With check
    (the default) it is refused with the reason before anything is added."""
    options = core.with_defaults(kind, options)
    if base is None or not has_faces(base.Shape):
        raise SurfaceModifyError("There is nothing in %s to work on yet." % body.Label)
    if check:
        preview(kind, base.Shape, names, options)
    step = bodies.insert_after_tip(body, TYPE, name or core.TYPES[kind])
    SurfaceModifyFeature(step, kind)
    _attach_view_provider(step)
    if step.BaseFeature is not base:
        try:
            step.BaseFeature = base
        except Exception:
            pass
    apply(step, base, names, options)
    return step


def read(step):
    """(base, names, options) of an existing step."""
    source, names = picks_of(step)
    return source or step.BaseFeature, names, options_of(step)


def _attach_view_provider(step):
    if not App.GuiUp:
        return
    try:
        from .surfmod_ui import ViewProviderSurfaceModify

        ViewProviderSurfaceModify(step.ViewObject)
    except Exception:
        try:
            from .bodies_gui import StepViewProvider

            StepViewProvider(step.ViewObject)
        except Exception:
            pass


# -- Mirror / Pattern Join on surface bodies ----------------------------------------------------
def stitch_join(base_shape, copies, tolerance=core.STITCH_TOLERANCE):
    """Mirror (or a pattern) with Operation Join on a surface body: the copies stitched to the
    original (Fusion's Stitch Tolerance closes gaps up to `tolerance`). A result that closes
    is a solid."""
    from . import surface_geom

    shapes = [base_shape] + list(copies)
    joined, _open = surface_geom.stitch(shapes, float(tolerance))
    return joined


# -- Split Body with surfaces --------------------------------------------------------------------
def extended_tool(shape, around):
    """A surface body as Split Body's tool, with Extend Splitting Tool: its open edges
    carried on (Natural where the surface allows it, else Tangent) far enough to cross
    `around`, so a sculpted surface smaller than the body still cuts it in two. The surface
    as it is when that cannot be done."""
    from . import surface_geom

    try:
        free = surface_geom.free_edges(shape)
        if not free:
            return shape
        reach = max(around.BoundBox.DiagonalLength, 1.0) + _gap(shape, around)
        grown = surface_geom.extend(shape, free, reach, "natural")
        if grown is not None and not grown.isNull() and grown.Faces:
            return grown
    except Exception:
        pass
    return shape


def _gap(shape, around):
    try:
        return shape.distToShape(around)[0]
    except Exception:
        return 0.0


def open_pieces(result):
    """The surface pieces a split surface falls into: its connected shells and loose faces."""
    from . import surface_geom

    pieces = []
    for piece in surface_geom.shells_or_faces(result):
        try:
            if piece.Area > 1e-9:
                pieces.append(piece)
        except Exception:
            continue
    return pieces
