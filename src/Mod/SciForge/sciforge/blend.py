# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion-style Fillet and Chamfer on top of PartDesign::Fillet / PartDesign::Chamfer.
No GUI code: the F / Chamfer dialogs and the golden-model builder both use this module,
so a model built by the test suite is built exactly like one made with the mouse.

What the user picks (Fusion's "Edges/Faces/Features" box) is a list of `refs`, element
names of the shape the blend is applied to (the previous step of the timeline):
  "Edge7"  that edge (OpenCASCADE also follows edges tangent to it: Fusion's Tangent Chain)
  "Face3"  every sharp edge around that face
Picking a whole feature (a timeline item) adds the edges that feature created.

Options, like Fusion's dialog:
  fillet   {"radius": mm}
  chamfer  {"chamfer_type": "equal" | "two" | "angle", "distance": mm, "distance2": mm,
            "angle": degrees, "flip": bool}
Distance 1 of a two-distance chamfer (and the distance of distance-and-angle) is measured on
the edge's *reference face*; "flip" moves it to the other face (reference_face() says which).

Too-big sizes: OpenCASCADE either refuses ("BRep_API: command not done") or, for some
fillets, returns a broken solid that FreeCAD would keep. trial() builds the blend first
and turns both into a plain-language BlendError, so the dialog can show it and keep the
last good preview instead of breaking the part.
"""
import math
import time

FILLET = "PartDesign::Fillet"
CHAMFER = "PartDesign::Chamfer"
TYPE_IDS = {"fillet": FILLET, "chamfer": CHAMFER}
KIND_BY_TYPE = {FILLET: "fillet", CHAMFER: "chamfer"}
# (option value, FreeCAD ChamferType, label in the dialog)
CHAMFER_TYPES = (
    ("equal", "Equal distance", "Equal Distance"),
    ("two", "Two distances", "Two Distances"),
    ("angle", "Distance and Angle", "Distance and Angle"),
)
TOL = 1e-6
SMOOTH = math.radians(0.5)  # faces meeting flatter than this form a smooth (tangent) edge


class BlendError(ValueError):
    """The fillet/chamfer cannot be made; the message says why and what to try."""


def default_options(kind):
    if kind == "fillet":
        return {"radius": 1.0}
    return {
        "chamfer_type": "equal",
        "distance": 1.0,
        "distance2": 1.0,
        "angle": 45.0,
        "flip": False,
    }


def kind_of(obj):
    return KIND_BY_TYPE.get(getattr(obj, "TypeId", ""))


def is_blend(obj):
    return kind_of(obj) is not None


# -- edges and faces ------------------------------------------------------------
def _unique(shapes):
    found = []
    for s in shapes:
        if not any(s.isSame(other) for other in found):
            found.append(s)
    return found


def faces_of(shape, edge):
    """The faces of `shape` that share `edge`."""
    import Part

    try:
        faces = shape.ancestorsOfType(edge, Part.Face)
    except Exception:
        faces = [f for f in shape.Faces if any(e.isSame(edge) for e in f.Edges)]
    return _unique(faces)


def element(shape, name):
    try:
        return shape.getElement(name)
    except Exception:
        return None


def index_of(items, item):
    for i, candidate in enumerate(items, start=1):
        if candidate.isSame(item):
            return i
    return 0


def edge_name(shape, edge):
    i = index_of(shape.Edges, edge)
    return "Edge%d" % i if i else None


def face_name(shape, face):
    i = index_of(shape.Faces, face)
    return "Face%d" % i if i else None


def _into_face(face, point, tangent, normal):
    """Unit direction from an edge point into `face`, across the edge, in the face's plane."""
    side = tangent.cross(normal)
    if side.Length < TOL:
        return None
    side.normalize()
    eps = max(1e-4, 1e-3 * min(face.BoundBox.DiagonalLength, 10.0))
    for candidate in (side, -side):
        probe = point + candidate * eps
        try:
            u, v = face.Surface.parameter(probe)
            if face.isPartOfDomain(u, v):
                return candidate
        except Exception:
            pass
    toward = face.CenterOfMass - point  # fallback: towards the middle of the face
    return side if toward.dot(side) >= 0 else -side


def frame(shape, edge):
    """Geometry at the middle of `edge`, or None if the edge cannot be blended:
    {"point", "tangent", "faces", "normals", "into", "convex", "gamma"}.
    gamma is the angle of the wedge the blend fills (the material for an outside
    edge, the air for an inside corner): 90 degrees on a box."""
    faces = faces_of(shape, edge)
    if len(faces) != 2:
        return None
    t = (edge.FirstParameter + edge.LastParameter) / 2.0
    point = edge.valueAt(t)
    tangent = edge.tangentAt(t)
    if tangent.Length < TOL:
        return None
    tangent.normalize()
    normals, into = [], []
    for face in faces:
        try:
            u, v = face.Surface.parameter(point)
            normal = face.normalAt(u, v)  # already points out of the solid (feature guide #4)
        except Exception:
            return None
        if normal.Length < TOL:
            return None
        normal.normalize()
        direction = _into_face(face, point, tangent, normal)
        if direction is None:
            return None
        normals.append(normal)
        into.append(direction)
    phi = normals[0].getAngle(normals[1])
    if phi < SMOOTH:
        return None  # tangent faces: a smooth edge, nothing to round off
    return {
        "point": point,
        "tangent": tangent,
        "faces": faces,
        "normals": normals,
        "into": into,
        "convex": normals[1].dot(into[0]) < 0,
        "gamma": math.pi - phi,
    }


def is_sharp(shape, edge):
    return frame(shape, edge) is not None


class ShapeInfo:
    """Which edges of a shape can be blended, cached (the dialog asks on every mouse move)."""

    def __init__(self, shape):
        self.shape = shape
        self.edges = shape.Edges
        self.faces = shape.Faces
        self._sharp = {}
        self._face_edges = {}
        self._chain = {}

    def sharp(self, name):
        if name not in self._sharp:
            edge = element(self.shape, name)
            self._sharp[name] = edge is not None and is_sharp(self.shape, edge)
        return self._sharp[name]

    def face_edges(self, name):
        """(sharp edge names, True if the face has smooth edges too) of a face."""
        if name not in self._face_edges:
            face = element(self.shape, name)
            sharp, smooth = [], False
            for edge in face.Edges if face is not None else []:
                ename = edge_name(self.shape, edge)
                if ename and self.sharp(ename):
                    if ename not in sharp:
                        sharp.append(ename)
                elif ename:
                    smooth = smooth or len(faces_of(self.shape, edge)) == 2
            self._face_edges[name] = (sharp, smooth)
        return self._face_edges[name]

    def pickable(self, name):
        if name.startswith("Edge"):
            return self.sharp(name)
        if name.startswith("Face"):
            return bool(self.face_edges(name)[0])
        return False

    def chain(self, name):
        """The edge and every sharp edge tangent-connected to it (Fusion's Tangent Chain;
        OpenCASCADE always fillets the whole chain)."""
        if name not in self._chain:
            self._chain[name] = tangent_chain(self, name)
        return self._chain[name]


def _end_tangent(edge, vertex):
    """Unit tangent of `edge` at its end `vertex`, pointing along the edge's direction."""
    p0 = edge.valueAt(edge.FirstParameter)
    t = (
        edge.FirstParameter
        if (p0 - vertex.Point).Length < (edge.valueAt(edge.LastParameter) - vertex.Point).Length
        else edge.LastParameter
    )
    tangent = edge.tangentAt(t)
    if tangent.Length > TOL:
        tangent.normalize()
    return tangent


def tangent_chain(info, name):
    import Part

    if not info.sharp(name):
        return [name]
    shape = info.shape
    chain, todo = [name], [name]
    while todo:
        current = element(shape, todo.pop())
        for vertex in current.Vertexes:
            try:
                neighbours = shape.ancestorsOfType(vertex, Part.Edge)
            except Exception:
                neighbours = [e for e in shape.Edges if any(v.isSame(vertex) for v in e.Vertexes)]
            here = _end_tangent(current, vertex)
            for other in neighbours:
                if other.isSame(current):
                    continue
                other_name = edge_name(shape, other)
                if not other_name or other_name in chain or not info.sharp(other_name):
                    continue
                if abs(here.dot(_end_tangent(other, vertex))) > math.cos(math.radians(1.0)):
                    chain.append(other_name)
                    todo.append(other_name)
    return chain


def blended_edges(info, refs):
    """Names of the edges a blend with these refs acts on (faces expanded), in order."""
    names = []
    for ref in refs:
        if ref.startswith("Face"):
            candidates = info.face_edges(ref)[0]
        elif ref.startswith("Edge") and info.sharp(ref):
            candidates = [ref]
        else:
            candidates = []
        for name in candidates:
            if name not in names:
                names.append(name)
    return names


def base_subs(info, refs):
    """What goes into the feature's Base: picked faces stay faces (later edits that add
    edges to the face round them too, like Fusion), except faces with smooth edges,
    which FreeCAD would warn about: those become their sharp edges."""
    subs = []
    for ref in refs:
        if ref.startswith("Face"):
            sharp, smooth = info.face_edges(ref)
            items = sharp if smooth else [ref]
        else:
            items = [ref] if info.sharp(ref) else []
        for item in items:
            if item not in subs:
                subs.append(item)
    return subs


# -- features -------------------------------------------------------------------
def _edge_key(edge, digits=5):
    t0, t1 = edge.FirstParameter, edge.LastParameter
    pts = [edge.valueAt(t0), edge.valueAt(t1)]
    ends = sorted(tuple(round(c, digits) for c in (p.x, p.y, p.z)) for p in pts)
    mid = edge.valueAt((t0 + t1) / 2.0)
    return (tuple(ends), tuple(round(c, digits) for c in (mid.x, mid.y, mid.z)))


def feature_edges(feature, info):
    """Sharp edges of the shape in `info` that `feature` created (Fusion: picking a
    feature in the timeline rounds the edges it made). [] if none."""
    shape = getattr(feature, "Shape", None)
    if shape is None or shape.isNull():
        return []
    before = getattr(feature, "BaseFeature", None)
    old = set()
    if before is not None and not before.Shape.isNull():
        old = {_edge_key(e) for e in before.Shape.Edges}
    made = {_edge_key(e) for e in shape.Edges} - old
    names = []
    for i, edge in enumerate(info.edges, start=1):
        name = "Edge%d" % i
        if _edge_key(edge) in made and info.sharp(name):
            names.append(name)
    return names


def chamfer_type_name(value):
    for option, freecad, _label in CHAMFER_TYPES:
        if option == value:
            return freecad
    raise BlendError("unknown chamfer type %r" % (value,))


def chamfer_type_option(freecad_name):
    for option, freecad, _label in CHAMFER_TYPES:
        if freecad == freecad_name:
            return option
    return "equal"


def read(feature):
    """The options of an existing Fillet/Chamfer, in the form make() takes."""
    if feature.TypeId == FILLET:
        return {"radius": feature.Radius.Value}
    return {
        "chamfer_type": chamfer_type_option(feature.ChamferType),
        "distance": feature.Size.Value,
        "distance2": feature.Size2.Value,
        "angle": feature.Angle.Value,
        "flip": bool(feature.FlipDirection),
    }


def refs_of(feature):
    """(base feature, [element names]) the blend is applied to."""
    base = feature.Base
    if not base:
        return feature.BaseFeature, []
    return base[0], [s for s in base[1] if s]


def _set(feature, prop, value):
    """Set a property only when it changes (an untouched feature is not recomputed) and
    never over an expression the user typed (=Parameters.r): that one wins."""
    try:
        if any(path in (prop, "." + prop) for path, _ in feature.ExpressionEngine):
            return
    except Exception:
        pass
    current = getattr(feature, prop)
    current = getattr(current, "Value", current)
    if isinstance(value, float) and isinstance(current, float):
        if abs(current - value) < 1e-12:
            return
    elif current == value:
        return
    setattr(feature, prop, value)


def apply(feature, options):
    """Write the dialog options onto the Fillet/Chamfer feature."""
    if feature.TypeId == FILLET:
        _set(feature, "Radius", float(options.get("radius", 1.0)))
    else:
        _set(feature, "ChamferType", chamfer_type_name(options.get("chamfer_type", "equal")))
        _set(feature, "Size", float(options.get("distance", 1.0)))
        _set(feature, "Size2", float(options.get("distance2", options.get("distance", 1.0))))
        _set(feature, "Angle", float(options.get("angle", 45.0)))
        _set(feature, "FlipDirection", bool(options.get("flip", False)))
    if not feature.Refine:
        feature.Refine = True  # Fusion never leaves seam faces


def set_refs(feature, base, subs):
    old = feature.Base
    if old and old[0] is base and list(old[1]) == list(subs):
        return
    feature.Base = (base, list(subs))


def make(body, base, refs, kind, options, name=None):
    """New Fillet/Chamfer at the end of `body`, rounding `refs` of `base` (normally
    body.Tip). Not recomputed. Returns the feature."""
    if kind not in TYPE_IDS:
        raise BlendError("unknown blend %r" % (kind,))
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise BlendError("Make a solid first (Create Sketch, then Extrude).")
    info = ShapeInfo(base.Shape)
    subs = base_subs(info, refs)
    if not subs:
        raise BlendError("Select the edges or faces to %s." % kind)
    feature = body.newObject(TYPE_IDS[kind], name or kind.capitalize())
    feature.Base = (base, subs)
    feature.Refine = True
    apply(feature, options)
    body.Tip = feature  # newObject() does not always move the Tip (feature guide #5)
    return feature


# -- checking before building ------------------------------------------------------
def reference_face(info, edge_name_, flip=False):
    """The face a chamfer measures Distance 1 on, like FreeCAD: the edge's first face, or
    its other face when flipped. Returns the index (0/1) into frame()["faces"]."""
    edge = element(info.shape, edge_name_)
    data = frame(info.shape, edge) if edge is not None else None
    if data is None:
        return 0
    import Part

    try:
        first = info.shape.ancestorsOfType(edge, Part.Face)
        ordered = [f for f in first]
    except Exception:
        ordered = data["faces"]
    pick = ordered[-1] if flip else ordered[0]
    return 0 if pick.isSame(data["faces"][0]) else 1


def _size_name(kind, options):
    if kind == "fillet":
        return "radius", float(options.get("radius", 0.0))
    return "distance", float(options.get("distance", 0.0))


def _build(kind, shape, edges, options):
    if kind == "fillet":
        return shape.makeFillet(float(options["radius"]), edges)
    ctype = options.get("chamfer_type", "equal")
    d1 = float(options.get("distance", 1.0))
    if ctype == "equal":
        return shape.makeChamfer(d1, edges)
    if ctype == "two":
        d2 = float(options.get("distance2", d1))
        if options.get("flip"):  # Part's makeChamfer measures d1 on the first face
            d1, d2 = d2, d1
        return shape.makeChamfer(d1, d2, edges)
    return None  # distance + angle: no Python kernel call; the feature itself is checked


def trial(kind, info, refs, options):
    """Build the blend on the base shape without touching the document. Returns the
    result shape (None when it can only be checked by the feature), raises BlendError
    with a plain-language reason when it does not work."""
    names = blended_edges(info, refs)
    if not names:
        raise BlendError(
            "Select the edges or faces to %s (click them in the view)." % kind
            if kind == "fillet"
            else "Select the edges or faces to chamfer (click them in the view)."
        )
    label, size = _size_name(kind, options)
    if size <= 0:
        raise BlendError("The %s must be more than 0 mm." % label)
    if kind == "chamfer":
        ctype = options.get("chamfer_type", "equal")
        if ctype == "two" and float(options.get("distance2", 0.0)) <= 0:
            raise BlendError("Distance 2 must be more than 0 mm.")
        if ctype == "angle":
            angle = float(options.get("angle", 45.0))
            if not 0.0 < angle < 180.0:
                raise BlendError("The angle must be between 0° and 180°.")
    edges = [element(info.shape, n) for n in names]
    try:
        result = _build(kind, info.shape, edges, options)
    except Exception as exc:
        raise BlendError(too_big(kind, label, size, exc))
    if result is None:
        return None
    if result.isNull() or not result.Solids:
        raise BlendError(too_big(kind, label, size))
    if len(result.Solids) > 1:
        raise BlendError(
            "This %s would cut the part into pieces. Use a smaller %s." % (kind, label)
        )
    if not result.isValid():
        raise BlendError(too_big(kind, label, size))
    return result


def too_big(kind, label, size, exc=None):
    what = "round" if kind == "fillet" else "bevel"
    return "%s %g mm is too big here: the %s does not fit on the faces next to it." % (
        label.capitalize(),
        size,
        what,
    )


def max_size(kind, info, refs, options, upper, budget=0.6):
    """Largest size that still works (bisection with trial()), or None. Stops after
    `budget` seconds: it is a hint for the message, not an exact limit."""
    key = "radius" if kind == "fillet" else "distance"
    if kind == "chamfer" and options.get("chamfer_type") == "angle":
        return None
    lo, hi = 0.0, float(upper)
    start = time.time()
    trials = dict(options)
    for _ in range(14):
        if time.time() - start > budget:
            break
        mid = (lo + hi) / 2.0
        trials[key] = mid
        if kind == "chamfer" and options.get("chamfer_type") == "two":
            ratio = float(options.get("distance2", upper)) / float(upper) if upper else 1.0
            trials["distance2"] = mid * ratio
        try:
            trial(kind, info, refs, trials)
            lo = mid
        except BlendError:
            hi = mid
    return lo if lo > 0 else None


def friendly(text):
    """FreeCAD's error text for a failed blend, in plain words."""
    low = (text or "").lower()
    if "command not done" in low or "failed" in low:
        return (
            "The kernel could not build this blend with these edges and this size. "
            "Try a smaller size or fewer edges."
        )
    if "multiple solids" in low:
        return "This would cut the part into pieces. Use a smaller size."
    if "greater than zero" in low:
        return "The size must be more than 0 mm."
    if "not possible on selected" in low or "no edges" in low:
        return "Select the edges or faces to round off."
    return text


# -- drag arrows ----------------------------------------------------------------
def arrow_spots(kind, info, refs, options, toward=None):
    """Where the blue drag arrows go, on the first picked edge: a list of
    {"what": option name, "point", "direction", "lift", "per_unit"}.
    The arrow lies on a face next to the edge, at the line where the blend starts, and
    points away from the edge; dragging it by `per_unit` mm changes the size by 1 mm."""
    names = blended_edges(info, refs[:1]) or blended_edges(info, refs)
    if not names:
        return []
    first_face = refs[0] if refs and refs[0].startswith("Face") else None
    edge = element(info.shape, names[0])
    data = frame(info.shape, edge)
    if data is None:
        return []

    def side(index, what, per_unit):
        return {
            "what": what,
            "point": data["point"],
            "direction": data["into"][index],
            "lift": data["normals"][index],
            "per_unit": per_unit,
        }

    if kind == "fillet":
        index = 0
        if first_face is not None:
            face = element(info.shape, first_face)
            index = 1 if face is not None and face.isSame(data["faces"][1]) else 0
        elif toward is not None:
            index = 0 if data["normals"][0].dot(toward) >= data["normals"][1].dot(toward) else 1
        half = max(data["gamma"] / 2.0, math.radians(5))
        per_unit = min(max(1.0 / math.tan(half), 0.2), 5.0)
        return [side(index, "radius", per_unit)]
    ref = reference_face(info, names[0], bool(options.get("flip")))
    spots = [side(ref, "distance", 1.0)]
    if options.get("chamfer_type") == "two":
        spots.append(side(1 - ref, "distance2", 1.0))
    return spots
