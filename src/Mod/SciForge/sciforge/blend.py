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

import contextlib
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


def _into_face_slow(face, point, tangent, normal):
    """Direction into `face` found by testing points on both sides (classifies the point
    against all the face's boundaries: slow on faces with many holes). Fallback only."""
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
    toward = face.CenterOfMass - point  # last resort: towards the middle of the face
    return side if toward.dot(side) >= 0 else -side


def orientation_in(face, edge):
    """ "Forward"/"Reversed": how `edge` runs in `face`'s boundary, or None."""
    for candidate in face.Edges:
        if candidate.isSame(edge):
            return candidate.Orientation
    return None


def _into_face(face, point, tangent, normal, orientation):
    """Unit direction from an edge point into `face`, across the edge, along the face.
    OpenCASCADE orients every boundary edge so the face lies on its left, seen from the
    outward normal: into = normal x (edge direction in that face)."""
    if orientation not in ("Forward", "Reversed"):
        return _into_face_slow(face, point, tangent, normal)
    side = normal.cross(tangent if orientation == "Forward" else -tangent)
    if side.Length < TOL:
        return None
    side.normalize()
    return side


def frame(shape, edge, faces=None, orientations=None):
    """Geometry at the middle of `edge`, or None if the edge cannot be blended:
    {"point", "tangent", "faces", "normals", "into", "convex", "gamma"}.
    gamma is the angle of the wedge the blend fills (the material for an outside
    edge, the air for an inside corner): 90 degrees on a box.
    `faces` / `orientations`: the edge's faces and how it runs in each, if already known
    (ShapeInfo keeps a map)."""
    if faces is None:
        faces = faces_of(shape, edge)
    if len(faces) != 2:
        return None
    if orientations is None:
        orientations = [orientation_in(face, edge) for face in faces]
    t = (edge.FirstParameter + edge.LastParameter) / 2.0
    point = edge.valueAt(t)
    tangent = edge.tangentAt(t)
    if tangent.Length < TOL:
        return None
    tangent.normalize()
    normals = []
    for face in faces:
        try:
            u, v = face.Surface.parameter(point)
            normal = face.normalAt(u, v)  # already points out of the solid (feature guide #4)
        except Exception:
            return None
        if normal.Length < TOL:
            return None
        normal.normalize()
        normals.append(normal)
    phi = normals[0].getAngle(normals[1])
    if phi < SMOOTH:
        return None  # tangent faces: a smooth edge, nothing to round off
    into = []
    for face, normal, orientation in zip(faces, normals, orientations):
        direction = _into_face(face, point, tangent, normal, orientation)
        if direction is None:
            return None
        into.append(direction)
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


def _hash(shape):
    try:
        return shape.hashCode()
    except Exception:
        return 0


class ShapeInfo:
    """Which edges of a shape can be blended, cached (the dialog asks on every mouse move)."""

    def __init__(self, shape):
        self.shape = shape
        self.edges = shape.Edges
        self.faces = shape.Faces
        self._sharp = {}
        self._face_edges = {}
        self._chain = {}
        self._edge_index = None
        self._edge_faces = None

    def edge_name(self, edge):
        """ "EdgeN" of an edge of this shape; a hash lookup, so big parts stay fast."""
        if self._edge_index is None:
            self._edge_index = {}
            for i, candidate in enumerate(self.edges, start=1):
                self._edge_index.setdefault(_hash(candidate), []).append(i)
        for i in self._edge_index.get(_hash(edge), []):
            if self.edges[i - 1].isSame(edge):
                return "Edge%d" % i
        return edge_name(self.shape, edge)

    def faces_of(self, name):
        """The faces next to edge `name`, from a map built once for the whole shape (asking
        OpenCASCADE per edge re-maps the shape each time: slow on big parts)."""
        if self._edge_faces is None:
            self._edge_faces = {}
            for face in self.faces:
                for edge in face.Edges:
                    key = self.edge_name(edge)
                    found = self._edge_faces.setdefault(key, [])
                    if not any(face.isSame(f) for f, _o in found):
                        found.append((face, edge.Orientation))
        return [face for face, _o in self._edge_faces.get(name, [])]

    def frame(self, name):
        edge = element(self.shape, name)
        if edge is None:
            return None
        self.faces_of(name)
        sides = self._edge_faces.get(name, [])
        return frame(self.shape, edge, [f for f, _o in sides], [o for _f, o in sides])

    def sharp(self, name):
        if name not in self._sharp:
            self._sharp[name] = self.frame(name) is not None
        return self._sharp[name]

    def face_edges(self, name):
        """(sharp edge names, True if the face has smooth edges too) of a face."""
        if name not in self._face_edges:
            face = element(self.shape, name)
            sharp, smooth = [], False
            for edge in face.Edges if face is not None else []:
                ename = self.edge_name(edge)
                if ename and self.sharp(ename):
                    if ename not in sharp:
                        sharp.append(ename)
                elif ename:
                    smooth = smooth or len(self.faces_of(ename)) == 2
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
                other_name = info.edge_name(other)
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


# -- later steps keep their edges -------------------------------------------------------
# Fusion keeps every later step attached to "its" edges when an earlier step changes: a
# fillet inserted earlier in the timeline (marker rolled back), or an earlier fillet edited
# to round one more edge. FreeCAD's element names do not survive an edge that the change
# trims or lengthens: the later fillet failed with "Invalid edge link" in the Report view.
# References keeps what the later blends point at as geometry and finds it again.
DRESS_UPS = (FILLET, CHAMFER, "PartDesign::Draft", "PartDesign::Thickness")


def _link_prop(obj):
    """The property holding what a later step picked: a dress-up's Base, or the Picks of
    SciForge's own fillet / chamfer step (fillet_sets.py); None for other steps."""
    if getattr(obj, "TypeId", "") in DRESS_UPS:
        return "Base"
    if getattr(obj, "SciForgeType", "") in ("FilletSets", "ChamferSets"):
        return "Picks"
    return None


def later_steps(body, after):
    """Features of `body` after `after` in the timeline (body order)."""
    if body is None or after is None:
        return []
    group = list(body.Group)
    names = [o.Name for o in group]
    if after.Name not in names:
        return []
    return group[names.index(after.Name) + 1 :]


def _same_curve(old, new, tol):
    try:
        # (a degenerated edge where rounds meet at a corner has no curve: TypeError)
        a, b = old.Curve, new.Curve
    except Exception:
        return False
    kind = type(a).__name__
    if kind != type(b).__name__:
        return False
    try:
        if kind in ("Line", "LineSegment"):
            da, db = a.Direction, b.Direction
            if abs(abs(da.dot(db)) - 1.0) > 1e-9:
                return False
            p = new.valueAt((new.FirstParameter + new.LastParameter) / 2.0)
            off = p - a.Location
            return (off - da * off.dot(da)).Length < tol
        if kind in ("Circle", "ArcOfCircle"):
            return (
                (a.Center - b.Center).Length < tol
                and abs(a.Radius - b.Radius) < tol
                and abs(abs(a.Axis.dot(b.Axis)) - 1.0) < 1e-9
            )
        return bool(a.isSame(b, tol, 1e-9))
    except Exception:
        return False


def _same_edge(old, new, tol=1e-6):
    """True if `new` is (a piece of) the same edge as `old`: same curve, overlapping."""
    import Part

    if not _same_curve(old, new, tol):
        return False

    def mid(edge):
        return edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)

    try:
        return (
            old.distToShape(Part.Vertex(mid(new)))[0] < tol
            or new.distToShape(Part.Vertex(mid(old)))[0] < tol
        )
    except Exception:
        return False


def _same_surface(a, b, tol):
    kind = type(a).__name__
    if kind != type(b).__name__:
        return False
    try:
        if kind == "Plane":
            na, nb = a.Axis, b.Axis
            if abs(abs(na.dot(nb)) - 1.0) > 1e-9:
                return False
            return abs((b.Position - a.Position).dot(na)) < tol
        if kind == "Cylinder":
            off = b.Center - a.Center
            return (
                abs(a.Radius - b.Radius) < tol
                and abs(abs(a.Axis.dot(b.Axis)) - 1.0) < 1e-9
                and (off - a.Axis * off.dot(a.Axis)).Length < tol
            )
        return bool(a.isSame(b, tol, 1e-9))
    except Exception:
        return False


def _same_face(old, new, tol=1e-6):
    """True if `new` is (a piece of) the same face as `old`: same surface, overlapping."""
    try:
        if not _same_surface(old.Surface, new.Surface, tol):
            return False
    except Exception:
        return False
    try:
        if old.distToShape(new)[0] > tol:
            return False
        return old.common(new).Area > 1e-6 * max(1.0, min(old.Area, new.Area))
    except Exception:
        return False


def find_same(shape, old, tol=1e-6):
    """Names of the elements of `shape` that are the edge/face `old` (from an earlier
    version of the part), possibly trimmed or lengthened by an earlier change."""
    names = []
    if old.ShapeType == "Edge":
        for i, edge in enumerate(shape.Edges, start=1):
            if _same_edge(old, edge, tol):
                names.append("Edge%d" % i)
    elif old.ShapeType == "Face":
        for i, face in enumerate(shape.Faces, start=1):
            if _same_face(old, face, tol):
                names.append("Face%d" % i)
    return names


def _alive(obj):
    try:
        return obj is not None and bool(obj.Name) and obj.isAttachedToDocument()
    except Exception:
        return False


class References:
    """The edges/faces the blends after `after` (in `body`) are attached to, as geometry.
    Take it before an earlier step changes; repair() afterwards."""

    def __init__(self, body, after):
        self.items = []  # (feature, [(element name, element shape copy)])
        for obj in later_steps(body, after):
            prop = _link_prop(obj)
            if prop is None:
                continue
            try:
                base = getattr(obj, prop)
                if not base or base[0] is None or base[0].Shape.isNull():
                    continue
                shape = base[0].Shape
                found = []
                for sub in base[1]:
                    name = (sub or "").split(".")[-1].lstrip("?")
                    item = element(shape, name) if name else None
                    if item is not None:
                        found.append((name, item.copy()))
                if found:
                    self.items.append((obj, found))
            except Exception:
                continue

    def broken(self):
        """The later steps that lost an edge/face or no longer compute."""
        found = []
        for obj, _subs in self.items:
            if not _alive(obj):
                continue
            try:
                link = getattr(obj, _link_prop(obj) or "Base")
                subs = list(link[1]) if link else []
                state = list(obj.State)
            except Exception:
                continue
            if any((s or "").startswith("?") for s in subs) or "Invalid" in state:
                found.append(obj)
        return found

    def repair(self):
        """Point each broken later step at the same edges/faces of its new base shape (an
        edge an earlier change trimmed is still that edge). Returns the features changed;
        the caller recomputes."""
        changed = []
        broken = self.broken()
        for obj, subs in self.items:
            if obj not in broken:
                continue
            try:
                prop = _link_prop(obj) or "Base"
                link = getattr(obj, prop)
                src = link[0] if link else obj.BaseFeature
                if src is None or src.Shape.isNull():
                    continue
                if prop != "Base":
                    # SciForge's fillet step keeps its picks in row order: each pick is
                    # found again in its place (a lost one stays, marked, for the dialog)
                    names = list(link[1]) if link else []
                    original = [(n or "").split(".")[-1].lstrip("?") for n in names]
                    for name, old in subs:
                        found = find_same(src.Shape, old)
                        for i, current in enumerate(original):
                            if found and current == name:
                                names[i] = found[0]
                else:
                    names = []
                    for _name, old in subs:
                        for match in find_same(src.Shape, old):
                            if match not in names:
                                names.append(match)
                if names and list(link[1] if link else []) != names:
                    setattr(obj, prop, (src, names))
                    changed.append(obj)
            except Exception:
                continue
        return changed


@contextlib.contextmanager
def quiet():
    """Mute FreeCAD's error/warning output (Report view, console) for a recompute whose
    passing failures SciForge repairs or explains itself."""
    import FreeCAD as App

    muted = []
    try:
        for name in App.Console.GetObservers():
            for kind in ("Err", "Wrn"):
                try:
                    if App.Console.GetStatus(name, kind):
                        App.Console.SetStatus(name, kind, False)
                        muted.append((name, kind))
                except Exception:
                    pass
    except Exception:
        pass
    try:
        yield
    finally:
        for name, kind in muted:
            try:
                App.Console.SetStatus(name, kind, True)
            except Exception:
                pass


def recompute_keeping(doc, keep, rounds=4):
    """Recompute; later blends that lost their edges are put back on them (a repaired step
    can uncover the next one, hence the rounds). Quiet: what still fails afterwards is
    reported by the caller (the dialog says which later steps no longer work)."""
    from . import preview

    # preview.recompute: while a dialog is open the steps after the marker wait
    with quiet():
        preview.recompute(doc)
        if keep is None:
            return []
        changed = []
        for _ in range(rounds):
            fixed = keep.repair()
            if not fixed:
                break
            changed.extend(fixed)
            preview.recompute(doc)
    return changed


def insert(body, base, refs, kind, options, name=None):
    """make() for a blend that may land before later steps (timeline marker rolled back):
    builds, recomputes and keeps the later blends on their edges. Returns the feature."""
    keep = References(body, base)
    feature = make(body, base, refs, kind, options, name)
    recompute_keeping(body.Document, keep)
    return feature


# -- checking before building ------------------------------------------------------
def reference_face(info, edge_name_, flip=False):
    """The face a chamfer measures Distance 1 on, like FreeCAD: the edge's first face, or
    its other face when flipped. Returns the index (0/1) into frame()["faces"]."""
    edge = element(info.shape, edge_name_)
    data = info.frame(edge_name_) if edge is not None else None
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
    if not names and refs:  # only smooth edges picked (an AI's selector, or a click)
        raise BlendError(
            "The picked edges are smooth: the faces on both sides already meet without a "
            "corner (the edges of an earlier fillet, for example), so there is nothing to "
            "%s. Pick sharp edges." % ("round" if kind == "fillet" else "chamfer")
        )
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
            # The bevel leaves the measured face at `angle`; it only meets the other face
            # if angle + (the corner's angle) < 180 degrees: less than 90 on a box edge.
            corners = [info.frame(n) for n in names]
            widest = max([math.degrees(c["gamma"]) for c in corners if c] or [0.0])
            limit = 180.0 - widest
            if widest and angle >= limit - 1e-9:
                raise BlendError(
                    "At %g° the bevel never reaches the face on the other side of the edge. "
                    "Use an angle below %g° here." % (angle, round(limit, 2))
                )
    edges = [element(info.shape, n) for n in names]
    try:
        result = _build(kind, info.shape, edges, options)
    except Exception as exc:
        raise BlendError(too_big(kind, label, size, exc))
    if result is None:
        return None
    if result.isNull() or not result.Solids:
        raise BlendError(too_big(kind, label, size))
    # A body may already hold several separate solids (two profiles extruded apart, like a
    # Fusion body with two lumps): only a blend that adds pieces cuts the part apart.
    if len(result.Solids) > max(1, len(info.shape.Solids)):
        raise BlendError(
            "This %s would cut the part into pieces. Use a smaller %s." % (kind, label)
        )
    if not result.isValid():
        raise BlendError(too_big(kind, label, size))
    return result


def check_build(kind, info, refs, options):
    """Raise BlendError if the blend does not work: trial(), and for a Distance and Angle
    chamfer (Part has no Python call for it, trial() cannot build it) the same bevel built
    as a Two Distances chamfer: the second distance is where a bevel leaving the measured
    face at the angle meets the other face (law of sines in the corner's triangle). Used to
    explain a refused chamfer and to find the largest size that fits (value_limits). Not
    FreeCAD's own Distance and Angle builder: OpenCASCADE crashed FreeCAD in it (segfault in
    ChFi3d_Builder) for some sizes where the bevel runs into a fillet, and a search tries
    sizes nobody typed."""
    if trial(kind, info, refs, options) is not None:
        return
    names = blended_edges(info, refs)
    label, size = _size_name(kind, options)
    angle = math.radians(float(options.get("angle", 45.0)))
    groups = {}  # the second distance -> the edges with that corner angle
    for name in names:
        frame = info.frame(name)
        gamma = frame["gamma"] if frame else math.pi / 2.0
        far = math.sin(angle + gamma)
        if far <= 1e-9:
            raise BlendError(too_big(kind, label, size))
        groups.setdefault(round(size * math.sin(angle) / far, 9), []).append(name)
    # Each edge gets its own second distance (FreeCAD's Distance and Angle chamfer does that
    # too): Part's chamfer takes one pair of distances for all its edges, so the edges are
    # checked in groups of the same corner angle. One bevel with the largest second distance
    # on every edge refused chamfers FreeCAD builds (a 90 and a 135 degree edge together).
    for second, group in groups.items():
        two = dict(options, chamfer_type="two", distance=size, distance2=second)
        try:
            trial(kind, info, group, two)
        except BlendError:
            raise BlendError(too_big(kind, label, size))


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
    data = info.frame(names[0])
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
            index = toward_face(data["normals"], toward)
        half = max(data["gamma"] / 2.0, math.radians(5))
        per_unit = min(max(1.0 / math.tan(half), 0.2), 5.0)
        return [side(index, "radius", per_unit)]
    ref = reference_face(info, names[0], bool(options.get("flip")))
    if options.get("chamfer_type") == "two":
        # One arrow per face: each sets the distance measured on its own face.
        return [side(ref, "distance", 1.0), side(1 - ref, "distance2", 1.0)]
    # Equal Distance, and Distance and Angle: one arrow, on the face toward the viewer (on
    # the reference face it was invisible behind the part for the top-back edge of a box in
    # the iso view; Luca: "the chamfer tool doesn't have an arrow to drag"). For Distance
    # and Angle it still sets Distance 1, which is measured on the reference face.
    index = ref if toward is None else toward_face(data["normals"], toward)
    return [side(index, "distance", 1.0)]


def toward_face(normals, toward):
    """Which of an edge's two faces (0 or 1) faces the viewer more: the one whose normal
    points most along `toward` (out of the screen). An arrow drawn on it can be seen."""
    return 0 if normals[0].dot(toward) >= normals[1].dot(toward) else 1
