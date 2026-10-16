# SPDX-License-Identifier: LGPL-2.1-or-later
"""Decal (INSERT > Decal), the document side (no Qt): a picture laid on a face of a body, flat
or curved, that follows the body. decal_ui.py is the dialog and the drawing; the maths without
FreeCAD is decal_core.py. Spec and sources: docs/sciforge/parity/misc.md.

A decal is an App::FeaturePython (SciForgeType "Decal", a step in the timeline after the step
whose face it is on; in the body's component, in the browser's Decals folder) holding:
  Body / FaceName      the body and the face (followed when the body changes: see follow())
  Anchor               the decal's frame on the face (origin, the face's outward normal as Z),
                       in the coordinates of the body's shape (its component's)
  BodyPlace            the body's own placement when the decal was computed: a body moved by
                       its placement since (a joint) is drawn moved (decal_ui), no recompute
  FaceRecord           the face as it was at the last good compute (where its surface's own
                       frame stood under the decal, its corners, area): how the face moved
                       since is found from it, and the decal moves the same way
  Surface              Plane, Cylinder (the picture wraps round the axis) or Other (laid
                       straight onto the frame's plane)
  ImageFile            the picture, kept inside the design file
  Opacity, ChainFaces, XDistance, YDistance, ZAngle, ScaleX, ScaleY, BaseWidth,
  BaseHeight, FlipHorizontal, FlipVertical
  MeshPoints / MeshUV / MeshNormals / MeshTriangles: the face's triangles cut to the
                       picture (what is drawn), rebuilt by every recompute.
Saved documents store "sciforge.decal.DecalFeature": keep the name.
"""

import json
import math
import os

import FreeCAD as App

from . import bodies, log
from . import decal_core as core

TYPE = "Decal"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
OPTION_PROPS = {
    "opacity": "Opacity",
    "chain": "ChainFaces",
    "dx": "XDistance",
    "dy": "YDistance",
    "angle": "ZAngle",
    "scale_x": "ScaleX",
    "scale_y": "ScaleY",
    "flip_h": "FlipHorizontal",
    "flip_v": "FlipVertical",
}
TANGENT_DEG = 2.0  # faces meeting within this angle are one surface for Chain Faces
RECORD = "FaceRecord"
GONE = (
    "The face this decal was on is gone (a step removed or replaced it). Double-click the "
    "decal and click a face to put it there, or delete it."
)


class DecalError(ValueError):
    """A decal that cannot be laid as asked; the message says why and what to try."""


def _v(p):
    return (p.x, p.y, p.z)


def _vec(t):
    return App.Vector(t[0], t[1], t[2])


class DecalFeature:
    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, hidden=False, output=False):
            if name in obj.PropertiesList:
                return False
            status = (4 if hidden else 0) | (8 if output else 0)
            obj.addProperty(kind, name, "Decal", doc, status)
            return True

        add("App::PropertyLinkGlobal", "Body", "The body the decal is on")
        add("App::PropertyString", "FaceName", "The face it is on (found again when renamed)")
        add("App::PropertyPlacement", "Anchor", "Its frame on the face", True)
        if add("App::PropertyEnumeration", "Surface", "How the picture lies on the face"):
            obj.Surface = ["Plane", "Cylinder", "Other"]
        add("App::PropertyVector", "AxisPoint", "Cylinder axis point", True)
        add("App::PropertyVector", "AxisDirection", "Cylinder axis", True)
        add("App::PropertyFloat", "Radius", "Cylinder radius", True)
        add("App::PropertyFileIncluded", "ImageFile", "The picture, kept inside the design")
        add("App::PropertyInteger", "PixelWidth", "The picture's width in pixels", True)
        add("App::PropertyInteger", "PixelHeight", "The picture's height in pixels", True)
        if add("App::PropertyInteger", "Opacity", "0 (clear) .. 100 (solid)"):
            obj.Opacity = 100
        if add("App::PropertyBool", "ChainFaces", "Wraps onto the faces tangent to it"):
            obj.ChainFaces = True
        add("App::PropertyFloat", "XDistance", "Moved along the frame's X (mm)")
        add("App::PropertyFloat", "YDistance", "Moved along the frame's Y (mm)")
        add("App::PropertyFloat", "ZAngle", "Turned about the face's normal (degrees)")
        if add("App::PropertyFloat", "ScaleX", "Width factor"):
            obj.ScaleX = 1.0
        if add("App::PropertyFloat", "ScaleY", "Height factor"):
            obj.ScaleY = 1.0
        add("App::PropertyFloat", "BaseWidth", "Width at scale 1 (mm)", True)
        add("App::PropertyFloat", "BaseHeight", "Height at scale 1 (mm)", True)
        add("App::PropertyBool", "FlipHorizontal", "Mirrored left-right")
        add("App::PropertyBool", "FlipVertical", "Mirrored top-bottom")
        add("App::PropertyVectorList", "MeshPoints", "What is drawn", True, True)
        add("App::PropertyVectorList", "MeshUV", "Picture coordinates", True, True)
        add("App::PropertyVectorList", "MeshNormals", "Normals", True, True)
        add("App::PropertyIntegerList", "MeshTriangles", "Triangles", True, True)
        add("App::PropertyString", RECORD, "The face at the last compute (followed)", True, True)
        add("App::PropertyPlacement", "BodyPlace", "The body's placement then", True, True)
        bodies.mark(obj, TYPE)

    def onDocumentRestored(self, obj):
        old = "BodyPlace" not in obj.PropertiesList
        self.ensure_properties(obj)
        try:
            body = obj.Body
            if old and body is not None and bodies.alive(body):
                # saved before decals followed their body: computed where the body stood
                obj.BodyPlace = App.Placement(body.Placement)
            if not getattr(obj, RECORD, ""):
                remember_face(obj)  # saved before faces were followed: its face as saved
        except Exception as exc:
            log("decal %s: not brought up to date: %s" % (obj.Label, exc))

    def execute(self, obj):
        build(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


# -- the face ------------------------------------------------------------------------------------
def body_shape(body):
    """The body's solid as it is now (in its component's coordinates)."""
    if body is None or not bodies.alive(body):
        raise DecalError("The body of this decal is gone (deleted?). Delete the decal.")
    shape = body.Shape
    if shape.isNull() or not shape.Faces:
        raise DecalError("%s has no faces to put the decal on." % body.Label)
    return shape


def drawn_place(obj):
    """How the decal's coordinates (its body's shape's when it was computed) lie in the ones
    it is drawn in (its own component's): the way the body moved by its own placement since
    (a joint or Component Drag moves a body at the root that way, without a recompute: the
    picture goes along at once), and the way from the body's component to the decal's when
    they differ."""
    from . import components

    body = obj.Body
    if body is None or not bodies.alive(body):
        return App.Placement()
    then = getattr(obj, "BodyPlace", None)  # None: an old decal not brought up to date yet
    place = body.Placement.multiply(then.inverse()) if then is not None else App.Placement()
    own = components.container_of(obj)
    home = components.container_of(body)
    if own is not home:
        start = home.getGlobalPlacement() if home is not None else App.Placement()
        end = own.getGlobalPlacement() if own is not None else App.Placement()
        place = end.inverse().multiply(start).multiply(place)
    return place


def global_place(obj):
    """How the decal's coordinates lie in the design (the handles are drawn with it)."""
    from . import components

    own = components.container_of(obj)
    start = own.getGlobalPlacement() if own is not None else App.Placement()
    return start.multiply(drawn_place(obj))


def _normal_at(face, point):
    u, v = face.Surface.parameter(point)
    return face.normalAt(u, v)


def surface_kind(face):
    name = type(face.Surface).__name__
    if name == "Plane":
        return "Plane"
    if name == "Cylinder":
        return "Cylinder"
    return "Other"


def _named_faces(shape, hint=""):
    """[(name, face)] of the shape, `hint` first (the face the decal was on last time)."""
    faces = [("Face%d" % (i + 1), f) for i, f in enumerate(shape.Faces)]
    if hint:
        first = [nf for nf in faces if nf[0] == hint]
        faces = first + [nf for nf in faces if nf[0] != hint]
    return faces


def _tolerance(shape):
    return 1e-3 * max(1.0, shape.BoundBox.DiagonalLength)


def _on_surface(face, point, tol):
    """The point lies on the face's surface (inside the face or not: a hole may be under it)."""
    try:
        surface = face.Surface
        return (surface.value(*surface.parameter(point)) - point).Length <= tol
    except Exception:
        return False


def find_face(shape, origin, normal, hint="", slack=0.0):
    """The face the decal's middle sits on: `hint` when it still holds it with the same normal,
    else the face nearest to it with that normal (faces are renamed when the body changes).
    `slack`: how far off the face the middle may be while still on its surface (a hole cut
    under it, the face trimmed). (name, face) or (None, None)."""
    tol = _tolerance(shape)
    best, best_d = (None, None), None
    point = App.Vector(origin)
    for name, face in _named_faces(shape, hint):
        try:
            d = face.distToShape(_point_shape(point))[0]
        except Exception:
            continue
        if d > max(tol, slack) or (d > tol and not _on_surface(face, point, tol)):
            continue
        try:
            if _normal_at(face, point).dot(normal) < 0.99:
                continue
        except Exception:
            continue
        if name == hint and d <= tol:
            return name, face
        if best_d is None or d < best_d - 1e-9:
            best, best_d = (name, face), d
    return best


def _point_shape(point):
    import Part

    return Part.Vertex(point)


def _slack(obj):
    """How far the decal's middle may be off its face (a hole under it): half its smaller side."""
    try:
        return 0.5 * min(obj.BaseWidth * obj.ScaleX, obj.BaseHeight * obj.ScaleY)
    except Exception:
        return 0.0


def _moved_plane(obj, shape, normal, slack=0.0):
    """A flat face moved along its normal (pushed / pulled, the body made thicker): the face
    with the same normal under the decal's middle, nearest first. (name, face, the middle
    put onto it) or (None, None, None)."""
    anchor = obj.Anchor
    tol = _tolerance(shape)
    best, best_d = (None, None, None), None
    for name, face in _named_faces(shape, obj.FaceName):
        if surface_kind(face) != "Plane":
            continue
        try:
            fn = _normal_at(face, face.CenterOfMass)
        except Exception:
            continue
        if fn.dot(normal) < 0.9999:
            continue
        offset = (anchor.Base - face.CenterOfMass).dot(fn)
        projected = anchor.Base - fn * offset
        try:
            if face.distToShape(_point_shape(projected))[0] > max(tol, slack):
                continue
        except Exception:
            continue
        if best_d is None or abs(offset) < best_d - 1e-9:
            best, best_d = (name, face, projected), abs(offset)
    return best


def _resized_cylinder(obj, shape, slack=0.0):
    """A cylinder made thicker or thinner (Press Pull on its side, a new radius): the face on
    a cylinder about the same axis under the decal's middle. (name, face, the middle put onto
    it, the new radius) or (None, None, None, None)."""
    if obj.Radius <= 0:
        return None, None, None, None
    tol = _tolerance(shape)
    axis = App.Vector(obj.AxisDirection).normalize()
    base = App.Vector(obj.AxisPoint)
    rel = obj.Anchor.Base - base
    radial = rel - axis * rel.dot(axis)
    if radial.Length < 1e-9:
        return None, None, None, None
    radial.normalize()
    best, best_d = (None, None, None, None), None
    for name, face in _named_faces(shape, obj.FaceName):
        if surface_kind(face) != "Cylinder":
            continue
        surface = face.Surface
        if abs(App.Vector(surface.Axis).normalize().dot(axis)) < 0.9999:
            continue
        off = App.Vector(surface.Center) - base
        if (off - axis * off.dot(axis)).Length > tol:
            continue  # not the same axis
        point = base + axis * rel.dot(axis) + radial * surface.Radius
        try:
            if face.distToShape(_point_shape(point))[0] > max(tol, slack):
                continue
            outward = _normal_at(face, point)
        except Exception:
            continue
        side = obj.Anchor.Rotation.multVec(App.Vector(0, 0, 1))
        if outward.dot(side) < 0.99:
            continue
        change = abs(surface.Radius - obj.Radius)
        if best_d is None or change < best_d - 1e-9:
            best, best_d = (name, face, point, surface.Radius), change
    return best


# -- following the face ----------------------------------------------------------------------
def _frame(origin, x, z):
    """A placement at `origin` whose Z is `z` and whose X is `x` laid square to it."""
    z = App.Vector(z).normalize()
    x = App.Vector(x) - z * App.Vector(x).dot(z)
    if x.Length < 1e-9:
        x = App.Vector(1, 0, 0) if abs(z.x) < 0.9 else App.Vector(0, 1, 0)
        x = x - z * x.dot(z)
    x.normalize()
    y = z.cross(x)
    matrix = App.Matrix(
        x.x, y.x, z.x, origin.x, x.y, y.y, z.y, origin.y, x.z, y.z, z.z, origin.z, 0, 0, 0, 1
    )
    return App.Placement(matrix)


def _surface_frame(face, uv):
    """The frame the face's own surface has at the parameters `uv`: its point there, its
    first parameter direction and its normal. A move of the shape (Move/Copy, a moved
    component's body) moves this frame with it and keeps the parameters."""
    surface = face.Surface
    u, v = uv
    du, dv = surface.tangent(u, v)
    x = du if du.Length > 1e-9 else dv
    return _frame(surface.value(u, v), x, surface.normal(u, v))


def _plc_list(place):
    q = place.Rotation.Q
    return [place.Base.x, place.Base.y, place.Base.z, q[0], q[1], q[2], q[3]]


def _plc(values):
    return App.Placement(App.Vector(*values[:3]), App.Rotation(*values[3:7]))


def face_record(face, point, shape=None):
    """What is remembered of the face the decal lies on (all in the body shape's coordinates):
    the surface's frame under the decal's middle `point` and its parameters there, the face's
    middle, area, corners and outward normal; the body's volume and middle (`shape`)."""
    uv = face.Surface.parameter(point)
    corners = [_v(p.Point) for p in face.Vertexes]
    rec = {
        "v": 1,
        "kind": surface_kind(face),
        "uv": [uv[0], uv[1]],
        "frame": _plc_list(_surface_frame(face, uv)),
        "com": _v(face.CenterOfMass),
        "area": face.Area,
        "normal": _v(face.normalAt(uv[0], uv[1])),
        "corners": corners[:24],
        "count": len(corners),
    }
    mass = _mass(shape) if shape is not None else None
    if mass is not None:
        rec["bvol"], rec["bcom"] = mass[0], _v(mass[1])
    return rec


def _mass(shape):
    """(volume, middle) of the body's solids, or None."""
    try:
        solids = list(shape.Solids)
        total = sum(s.Volume for s in solids)
        if not solids or total <= 1e-12:
            return None
        middle = App.Vector()
        for s in solids:
            middle = middle + s.CenterOfMass * (s.Volume / total)
        return total, middle
    except Exception:
        return None


def _record(obj):
    try:
        data = json.loads(getattr(obj, RECORD, "") or "{}")
        return data if data.get("v") == 1 else None
    except Exception:
        return None


def _congruent(rec, face, place, tol):
    """`face` is the remembered face moved by `place`: the same kind and area, its middle,
    corners and normal where `place` takes the remembered ones."""
    if surface_kind(face) != rec["kind"]:
        return False
    if abs(face.Area - rec["area"]) > 1e-5 * max(rec["area"], 1e-9) + 1e-9:
        return False
    if (place.multVec(_vec(rec["com"])) - face.CenterOfMass).Length > tol:
        return False
    have = [p.Point for p in face.Vertexes]
    if len(have) != rec.get("count", len(have)):
        return False
    for corner in rec["corners"]:
        moved = place.multVec(_vec(corner))
        if not any((moved - p).Length <= tol for p in have):
            return False
    try:  # facing the same way under the decal's middle
        point = place.multVec(_plc(rec["frame"]).Base)
        u, v = face.Surface.parameter(point)
        if place.Rotation.multVec(_vec(rec["normal"])).dot(face.normalAt(u, v)) < 0.9999:
            return False
    except Exception:
        return False
    return True


def _rigid(rec, face, tol):
    """How the remembered face was moved to become `face` (a placement), or None when `face`
    is not the remembered face moved (another face, or the face changed shape)."""
    if surface_kind(face) != rec["kind"]:
        return None
    if abs(face.Area - rec["area"]) > 1e-5 * max(rec["area"], 1e-9) + 1e-9:
        return None
    try:
        place = _surface_frame(face, rec["uv"]).multiply(_plc(rec["frame"]).inverse())
    except Exception:
        return None
    return place if _congruent(rec, face, place, tol) else None


def _likeliest(obj, rec, shape, movers, tol):
    """The face among those the remembered face could have become (a box's top and bottom are
    alike: a turn takes one onto the other): (name, face, placement, the body moved as a
    whole). When the body moved as a whole (the same volume, its middle moved the same way:
    Move/Copy, a placement) the face of the same name, which a move keeps; else the least
    motion (a face pushed out along its normal does not turn)."""
    whole = None
    if "bvol" in rec:
        mass = _mass(shape)
        if mass is not None and abs(mass[0] - rec["bvol"]) <= 1e-6 * max(rec["bvol"], 1e-9):
            whole = mass[1]

    def together(place):
        return whole is not None and (place.multVec(_vec(rec["bcom"])) - whole).Length <= tol

    def key(mover):
        name, _face, place = mover
        moved = together(place)
        return (
            0 if moved else 1,
            0 if moved and name == obj.FaceName else 1,
            round(place.Rotation.Angle, 6),
            place.Base.Length,
        )

    name, face, place = min(movers, key=key)
    return name, face, place, together(place)


def follow(obj, shape):
    """The face the decal is stuck to in `shape` (its body as it is now) and how that face
    moved since the decal was last computed: (name, face, how) with how one of
      ("same", None)               the face did not move (renamed, cut or grown in place)
      ("moved", placement)         the face moved as a whole (the body moved, the face
                                   pushed out unchanged): the decal moves the same way
      ("plane", point)             a flat face pushed or pulled along its normal (changed)
      ("cylinder", (point, r))     a cylinder made thicker or thinner
    or (None, None, None) when the face is gone."""
    rec = _record(obj)
    tol = _tolerance(shape)
    faces = _named_faces(shape, obj.FaceName)
    if rec is not None:
        identity = App.Placement()
        for name, face in faces:  # the same face where it was
            try:
                if _congruent(rec, face, identity, tol):
                    return name, face, ("same", None)
            except Exception:
                continue
        movers = []
        for name, face in faces:  # the same face, moved
            place = _rigid(rec, face, tol)
            if place is not None:
                movers.append((name, face, place))
        if movers:
            name, face, place, whole = _likeliest(obj, rec, shape, movers, tol)
            if whole or place.Rotation.Angle < 1e-9:
                return name, face, ("moved", place)
            # Turned, though the body did not move as a whole: a face rebuilt by a later
            # step whose surface starts elsewhere (a pushed face does not turn). Where the
            # decal sits is trusted first; the turn only when nothing else fits.
            found = _in_place(obj, shape)
            return found if found[1] is not None else (name, face, ("moved", place))
    return _in_place(obj, shape)


def _in_place(obj, shape):
    """follow() without a remembered face, or when it does not tell: the face under the
    decal's middle, a flat face pushed / pulled under it, a cylinder made thicker / thinner."""
    anchor = obj.Anchor
    normal = anchor.Rotation.multVec(App.Vector(0, 0, 1))
    slack = _slack(obj)
    name, face = find_face(shape, anchor.Base, normal, obj.FaceName, slack)
    if face is not None:
        return name, face, ("same", None)
    if obj.Surface == "Plane":
        name, face, point = _moved_plane(obj, shape, normal, slack)
        if face is not None:
            return name, face, ("plane", point)
    if obj.Surface == "Cylinder":
        name, face, point, radius = _resized_cylinder(obj, shape, slack)
        if face is not None:
            return name, face, ("cylinder", (point, radius))
    return None, None, None


def _take(obj, how):
    """Move the decal's frame (and its cylinder) the way its face moved."""
    kind, data = how
    anchor = obj.Anchor
    if kind == "moved":
        if data.isIdentity():
            return
        obj.Anchor = data.multiply(anchor)
        if obj.Surface == "Cylinder":
            obj.AxisPoint = data.multVec(obj.AxisPoint)
            obj.AxisDirection = data.Rotation.multVec(obj.AxisDirection)
    elif kind == "plane":
        obj.Anchor = App.Placement(data, anchor.Rotation)
    elif kind == "cylinder":
        point, radius = data
        obj.Anchor = App.Placement(point, anchor.Rotation)
        obj.Radius = float(radius)


def stale(obj):
    """True when the decal does not match its body any more and must be computed again: its
    face moved or changed since it was computed, or a red decal whose face is back."""
    try:
        shape = body_shape(obj.Body)
        _name, face, how = follow(obj, shape)
    except Exception:
        return False
    red = "Invalid" in list(obj.State)
    if red or not obj.MeshPoints:
        # red with its face back; or not drawn and not red (a redo that took its face away
        # restores the empty mesh, not the red mark): computed again, it is flagged
        return face is not None or not red
    return face is None or how[0] != "same"


def remember_face(obj, face=None, shape=None):
    """Store where the decal's face is now (FaceRecord), for follow() the next time."""
    if face is None:
        shape = shape if shape is not None else body_shape(obj.Body)
        normal = obj.Anchor.Rotation.multVec(App.Vector(0, 0, 1))
        _name, face = find_face(shape, obj.Anchor.Base, normal, obj.FaceName, _slack(obj))
        if face is None:
            return False
    if shape is None:
        shape = body_shape(obj.Body)
    text = json.dumps(face_record(face, obj.Anchor.Base, shape), sort_keys=True)
    if getattr(obj, RECORD, "") != text:
        setattr(obj, RECORD, text)
    return True


def chained(shape, face):
    """The faces reached from `face` across edges where they meet tangentially (Chain Faces)."""
    import Part  # noqa: F401 (shape methods)

    faces = list(shape.Faces)
    done = {face.hashCode()}
    found = [face]
    queue = [face]
    limit = math.cos(math.radians(TANGENT_DEG))
    while queue:
        current = queue.pop()
        for edge in current.Edges:
            mid = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
            for other in shape.ancestorsOfType(edge, Part.Face):
                if other.hashCode() in done:
                    continue
                try:
                    if _normal_at(current, mid).dot(_normal_at(other, mid)) < limit:
                        continue
                except Exception:
                    continue
                done.add(other.hashCode())
                same = [f for f in faces if f.isSame(other)]
                found.append(same[0] if same else other)
                queue.append(other)
    return found


# -- the frame -----------------------------------------------------------------------------------
def frame_at(face, point, turn=None):
    """(Anchor placement, surface kind, cylinder data or None) of a decal laid at `point` of
    `face`: Z = the outward normal there; on a wall the picture stands upright. `turn`: the
    rotation from the face's coordinates (its body's own) to the design's, whose up the
    picture takes."""
    turn = turn if turn is not None else App.Rotation()
    back = turn.inverted()
    up = back.multVec(App.Vector(0, 0, 1))
    right = back.multVec(App.Vector(1, 0, 0))
    normal = _normal_at(face, point)
    kind = surface_kind(face)
    cylinder = None
    if kind == "Cylinder":
        surface = face.Surface
        axis = App.Vector(surface.Axis).normalize()
        seen = turn.multVec(axis)  # as the design sees it
        if seen.z < -1e-9 or (
            abs(seen.z) < 1e-9 and (seen.y < -1e-9 or abs(seen.y) < 1e-9 and seen.x < 0)
        ):
            axis = axis * -1.0  # the picture's up along +Z (or +Y / +X)
        y = axis
        x = y.cross(normal).normalize()
        cylinder = {"point": App.Vector(surface.Center), "axis": axis, "radius": surface.Radius}
    else:
        hint = core.upright_hint(_v(normal), _v(up), _v(right))
        x_t, y_t, _z = core.frame_axes(_v(normal), hint)
        x, y = _vec(x_t), _vec(y_t)
    z = normal
    matrix = App.Matrix(x.x, y.x, z.x, 0, x.y, y.y, z.y, 0, x.z, y.z, z.z, 0, 0, 0, 0, 1)
    return App.Placement(App.Vector(point), App.Placement(matrix).Rotation), kind, cylinder


def face_size(face, kind, cylinder=None):
    """The smaller side of the face (mm) for the picture's first size."""
    box = face.BoundBox
    sides = sorted([box.XLength, box.YLength, box.ZLength])
    if kind == "Cylinder" and cylinder:
        height = abs(sides[-1]) if sides else 0.0
        return min(math.pi * cylinder["radius"], height or 2 * cylinder["radius"])
    return sides[1] if sides[1] > 1e-6 else sides[2]


# -- the mesh ------------------------------------------------------------------------------------
def options(obj):
    return {
        "dx": float(obj.XDistance),
        "dy": float(obj.YDistance),
        "angle": float(obj.ZAngle),
        "scale_x": float(obj.ScaleX),
        "scale_y": float(obj.ScaleY),
        "flip_h": bool(obj.FlipHorizontal),
        "flip_v": bool(obj.FlipVertical),
        "width": float(obj.BaseWidth),
        "height": float(obj.BaseHeight),
    }


def uv_function(obj):
    """point (App.Vector) -> picture (u, v) for the decal's surface."""
    anchor = obj.Anchor
    origin = anchor.Base
    rot = anchor.Rotation
    x = rot.multVec(App.Vector(1, 0, 0))
    y = rot.multVec(App.Vector(0, 1, 0))
    opts = options(obj)
    if obj.Surface == "Cylinder" and obj.Radius > 0:
        axis = App.Vector(obj.AxisDirection)
        tangent = axis.cross((origin - obj.AxisPoint) - axis * (origin - obj.AxisPoint).dot(axis))
        sign_u = 1.0 if tangent.dot(x) >= 0 else -1.0
        sign_v = 1.0 if axis.dot(y) >= 0 else -1.0

        def uv(p):
            u, v = core.cylinder_coords(_v(p), _v(origin), _v(obj.AxisPoint), _v(axis), obj.Radius)
            return core.placed(u * sign_u, v * sign_v, opts)

        return uv

    def uv(p):
        u, v = core.flat_coords(_v(p), _v(origin), _v(x), _v(y))
        return core.placed(u, v, opts)

    return uv


def mesh(obj, shape=None):
    """(points, uv, normals, triangles) of the decal on its body as it is now, its frame
    moved the way its face moved (follow()); DecalError when its face is gone. Returns the
    face too: (points, uv, normals, triangles, face)."""
    shape = shape if shape is not None else body_shape(obj.Body)
    name, face, how = follow(obj, shape)
    if face is None:
        raise DecalError(GONE)
    _take(obj, how)
    if name != obj.FaceName:
        obj.FaceName = name
    anchor = obj.Anchor
    normal = anchor.Rotation.multVec(App.Vector(0, 0, 1))
    faces = chained(shape, face) if obj.ChainFaces else [face]
    uv_of = uv_function(obj)
    size = max(obj.BaseWidth * obj.ScaleX, obj.BaseHeight * obj.ScaleY, 1.0)
    tolerance = max(0.002, size / 1000.0)
    points, uvs, normals, tris = [], [], [], []
    for f in faces:
        try:
            verts, triangles = f.tessellate(tolerance)
        except Exception:
            continue
        if not triangles:
            continue

        def normal_of(p, f=f):
            try:
                return _v(_normal_at(f, _vec(p)))
            except Exception:
                return _v(normal)

        pts = [_v(p) for p in verts]
        p2, uv2, n2, t2 = core.cover(pts, triangles, lambda p: uv_of(_vec(p)), normal_of)
        base = len(points)
        points += p2
        uvs += uv2
        normals += n2
        tris += [(a + base, b + base, c + base) for a, b, c in t2]
    lift = max(0.005, 1e-4 * shape.BoundBox.DiagonalLength)
    points = core.lifted(points, normals, lift)
    return points, uvs, normals, tris, face


def build(obj):
    """Recompute the drawn mesh (FeaturePython execute). A decal whose face is gone is not
    drawn (and its step is red with the reason)."""
    try:
        points, uvs, normals, tris, face = mesh(obj)
    except DecalError:
        _set_mesh(obj, [], [], [], [])
        raise
    _set_mesh(obj, points, uvs, normals, tris)
    remember_face(obj, face)
    then = getattr(obj, "BodyPlace", None)
    if then is not None and not then.isSame(obj.Body.Placement, 1e-12):
        obj.BodyPlace = App.Placement(obj.Body.Placement)  # the mesh is where the body is now


def _set_mesh(obj, points, uvs, normals, tris):
    flat = []
    for tri in tris:
        flat += list(tri)
    if not points and not obj.MeshPoints:
        return  # nothing drawn already: no change (an undo step stays clean)
    obj.MeshPoints = [_vec(p) for p in points]
    obj.MeshUV = [App.Vector(u, v, 0) for u, v in uvs]
    obj.MeshNormals = [_vec(n) for n in normals]
    obj.MeshTriangles = flat


# -- making one ----------------------------------------------------------------------------------
def _laid(body, face_name, point):
    """(face, Anchor, surface kind, cylinder data) of a decal laid on `face_name` of `body`
    where `point` (the body's component's coordinates, a click) is."""
    from . import components

    shape = body_shape(body)
    try:
        face = shape.getElement(face_name)
    except Exception:
        raise DecalError("Click a face of a body.") from None
    point = App.Vector(point)
    try:
        point = face.Surface.value(*face.Surface.parameter(point))  # exactly on the face
    except Exception:
        pass
    home = components.container_of(body)
    turn = home.getGlobalPlacement().Rotation if home is not None else App.Rotation()
    anchor, kind, cylinder = frame_at(face, point, turn)
    return face, anchor, kind, cylinder


def _set_frame(obj, face_name, anchor, kind, cylinder):
    obj.FaceName = face_name
    obj.Anchor = anchor
    obj.Surface = kind
    if cylinder:
        obj.AxisPoint = cylinder["point"]
        obj.AxisDirection = cylinder["axis"]
        obj.Radius = cylinder["radius"]


def make(body, face_name, point, image_path, pixels, label=None):
    """A decal on `face_name` of `body` at `point` (the body's component's coordinates) with
    the picture `image_path` of `pixels` (w, h). Returns it (recomputed)."""
    if not image_path or not os.path.isfile(image_path):
        raise DecalError("The image was not found: %s" % (image_path or "(no file)"))
    if os.path.splitext(image_path)[1].lower() not in IMAGE_EXTENSIONS:
        raise DecalError("Choose a PNG, JPEG, TIFF or BMP image.")
    face, anchor, kind, cylinder = _laid(body, face_name, point)
    doc = body.Document
    obj = doc.addObject("App::FeaturePython", "Decal")
    DecalFeature(obj)
    obj.Label = label or unique_label(doc, os.path.splitext(os.path.basename(image_path))[0])
    obj.Body = body
    _set_frame(obj, face_name, anchor, kind, cylinder)
    obj.ImageFile = image_path
    obj.PixelWidth, obj.PixelHeight = int(pixels[0]), int(pixels[1])
    width, height = core.default_size(pixels, face_size(face, kind, cylinder))
    obj.BaseWidth, obj.BaseHeight = float(width), float(height)
    try:  # in the body's component, like the body (the browser lists it there)
        from . import components

        container = components.container_of(body)
        if container is not None:
            container.addObject(obj)
    except Exception:
        pass
    obj.recompute()
    log(
        "decal %s on %s %s (%s, %.1f x %.1f mm)"
        % (obj.Label, body.Label, face_name, kind, width, height)
    )
    return obj


def relay(obj, body, face_name, point):
    """Put a decal onto another face (Edit Decal, a face clicked: its own face was deleted, or
    the user wants it elsewhere). The picture keeps its options and size; its middle goes
    where the face was clicked (X / Y Distance back to 0)."""
    _face, anchor, kind, cylinder = _laid(body, face_name, point)
    if obj.Body is not body:
        obj.Body = body
    _set_frame(obj, face_name, anchor, kind, cylinder)
    obj.XDistance = 0.0
    obj.YDistance = 0.0
    setattr(obj, RECORD, "")  # found again where it was clicked, then followed from there
    carry(body)
    log("decal %s put on %s %s (%s)" % (obj.Label, body.Label, face_name, kind))
    return obj


def carry(body):
    """A body put into another component takes its decals along (a decal belongs to its
    body's component and is drawn in it: Fusion's decal moves with the component). Returns
    how many moved."""
    from . import components

    if body is None or not bodies.alive(body):
        return 0
    target = components.container_of(body)
    moved = 0
    for obj in decals(body.Document):
        if obj.Body is not body:
            continue
        current = components.container_of(obj)
        if current is target:
            continue
        try:
            if current is not None:
                current.removeObject(obj)
            if target is not None:
                target.addObject(obj)
            moved += 1
        except Exception as exc:
            log("decal %s: not moved with %s: %s" % (obj.Label, body.Label, exc))
    if moved:
        log(
            "%d decal(s) moved with %s to %s"
            % (moved, body.Label, target.Label if target is not None else "the root")
        )
    return moved


def unique_label(doc, base):
    """The picture's name; "name (2)", "name (3)"... when another decal has it."""
    taken = {o.Label for o in decals(doc)}
    if base not in taken:
        return base
    n = 2
    while "%s (%d)" % (base, n) in taken:
        n += 1
    return "%s (%d)" % (base, n)


def set_options(obj, **values):
    """Write dialog values (keys of OPTION_PROPS) and rebuild the mesh."""
    for key, value in values.items():
        prop = OPTION_PROPS[key]
        current = getattr(obj, prop)
        if prop in ("ChainFaces", "FlipHorizontal", "FlipVertical"):
            value = bool(value)
        elif prop == "Opacity":
            value = int(max(0, min(100, round(value))))
        else:
            value = float(value)
            if prop in ("ScaleX", "ScaleY"):
                value = max(1e-4, value)
        if current != value:
            setattr(obj, prop, value)


def option_values(obj):
    return {key: getattr(obj, prop) for key, prop in OPTION_PROPS.items()}


def centre(obj):
    """Where the decal's middle is on the face, and the directions of its X / Y / normal there
    (the handles are drawn from these)."""
    anchor = obj.Anchor
    rot = anchor.Rotation
    x = rot.multVec(App.Vector(1, 0, 0))
    y = rot.multVec(App.Vector(0, 1, 0))
    z = rot.multVec(App.Vector(0, 0, 1))
    if obj.Surface == "Cylinder" and obj.Radius > 0:
        axis = App.Vector(obj.AxisDirection)
        sign_v = 1.0 if axis.dot(y) >= 0 else -1.0
        radial0 = anchor.Base - obj.AxisPoint
        radial0 = radial0 - axis * radial0.dot(axis)
        tangent = axis.cross(radial0)
        sign_u = 1.0 if tangent.dot(x) >= 0 else -1.0
        angle = sign_u * obj.XDistance / obj.Radius
        turn = App.Rotation(axis, math.degrees(angle))
        radial = turn.multVec(radial0)
        point = obj.AxisPoint + axis * ((anchor.Base - obj.AxisPoint).dot(axis)) + radial
        point = point + axis * (obj.YDistance * sign_v)
        z = App.Vector(radial).normalize() * (1.0 if radial0.dot(z) >= 0 else -1.0)
        x = turn.multVec(x)
        return point, x, y, z
    return anchor.Base + x * obj.XDistance + y * obj.YDistance, x, y, z


def is_decal(obj):
    return bodies.kind(obj) == TYPE


def decals(doc):
    return [o for o in doc.Objects if is_decal(o)] if doc is not None else []


def summary(obj):
    return json.dumps(
        {
            "face": obj.FaceName,
            "surface": obj.Surface,
            "size": [round(obj.BaseWidth * obj.ScaleX, 3), round(obj.BaseHeight * obj.ScaleY, 3)],
            "triangles": len(obj.MeshTriangles) // 3,
        }
    )


def covered_area(obj):
    pts = [_v(p) for p in obj.MeshPoints]
    flat = list(obj.MeshTriangles)
    tris = [tuple(flat[i : i + 3]) for i in range(0, len(flat), 3)]
    return core.area(pts, tris)
