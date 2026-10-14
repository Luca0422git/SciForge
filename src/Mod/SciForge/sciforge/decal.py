# SPDX-License-Identifier: LGPL-2.1-or-later
"""Decal (INSERT > Decal), the document side (no Qt): a picture laid on a face of a body, flat
or curved, that follows the body. decal_ui.py is the dialog and the drawing; the maths without
FreeCAD is decal_core.py. Spec and sources: docs/sciforge/parity/misc.md.

A decal is an App::FeaturePython (SciForgeType "Decal", a step in the timeline after the step
whose face it is on; in the body's component, in the browser's Decals folder) holding:
  Body / FaceName      the body and the face (found again by where the decal sits when the
                       body changes: FreeCAD renames faces)
  Anchor               the decal's frame on the face (origin, the face's outward normal as Z)
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
        bodies.mark(obj, TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

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


def find_face(shape, origin, normal, hint=""):
    """The face the decal sits on: `hint` when it still holds the decal's origin with the
    same normal, else the face nearest to the origin with that normal (faces are renamed when
    the body changes). (name, face) or (None, None)."""
    candidates = []
    if hint:
        try:
            candidates.append((hint, shape.getElement(hint)))
        except Exception:
            pass
    candidates += [("Face%d" % (i + 1), f) for i, f in enumerate(shape.Faces)]
    best, best_d = (None, None), None
    point = App.Vector(origin)
    for name, face in candidates:
        try:
            d = face.distToShape(_point_shape(point))[0]
        except Exception:
            continue
        if d > 1e-3 * max(1.0, shape.BoundBox.DiagonalLength):
            continue
        try:
            if _normal_at(face, point).dot(normal) < 0.99:
                continue
        except Exception:
            continue
        if name == hint:
            return name, face
        if best_d is None or d < best_d:
            best, best_d = (name, face), d
    return best


def _point_shape(point):
    import Part

    return Part.Vertex(point)


def _moved_plane(obj, shape, normal):
    """A flat face moved along its normal (the body was made thicker): the face with the same
    normal under the decal; the decal's frame goes onto it."""
    anchor = obj.Anchor
    best, best_d = (None, None), None
    for i, face in enumerate(shape.Faces):
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
            if face.distToShape(_point_shape(projected))[0] > 1e-4:
                continue
        except Exception:
            continue
        if best_d is None or abs(offset) < best_d:
            best, best_d = ("Face%d" % (i + 1), face, projected), abs(offset)
    if best[0] is None:
        return None, None
    name, face, projected = best
    obj.Anchor = App.Placement(projected, anchor.Rotation)
    return name, face


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
def frame_at(face, point):
    """(Anchor placement, surface kind, cylinder data or None) of a decal laid at `point` of
    `face`: Z = the outward normal there; on a wall the picture stands upright."""
    normal = _normal_at(face, point)
    kind = surface_kind(face)
    cylinder = None
    if kind == "Cylinder":
        surface = face.Surface
        axis = App.Vector(surface.Axis).normalize()
        if axis.z < -1e-9 or (
            abs(axis.z) < 1e-9 and (axis.y < -1e-9 or abs(axis.y) < 1e-9 and axis.x < 0)
        ):
            axis = axis * -1.0  # the picture's up along +Z (or +Y / +X)
        y = axis
        x = y.cross(normal).normalize()
        cylinder = {"point": App.Vector(surface.Center), "axis": axis, "radius": surface.Radius}
    else:
        hint = core.upright_hint(_v(normal))
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
    """(points, uv, normals, triangles) of the decal on its body as it is now; DecalError
    when its face is gone."""
    shape = shape if shape is not None else body_shape(obj.Body)
    anchor = obj.Anchor
    normal = anchor.Rotation.multVec(App.Vector(0, 0, 1))
    name, face = find_face(shape, anchor.Base, normal, obj.FaceName)
    if face is None and obj.Surface == "Plane":
        name, face = _moved_plane(obj, shape, normal)
    if face is None:
        raise DecalError(
            "The face under the decal is gone (an earlier step changed it). Edit the decal and "
            "click a face again, or delete it."
        )
    if name != obj.FaceName:
        obj.FaceName = name
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
    return points, uvs, normals, tris


def build(obj):
    """Recompute the drawn mesh (FeaturePython execute)."""
    points, uvs, normals, tris = mesh(obj)
    obj.MeshPoints = [_vec(p) for p in points]
    obj.MeshUV = [App.Vector(u, v, 0) for u, v in uvs]
    obj.MeshNormals = [_vec(n) for n in normals]
    flat = []
    for tri in tris:
        flat += list(tri)
    obj.MeshTriangles = flat


# -- making one ----------------------------------------------------------------------------------
def make(body, face_name, point, image_path, pixels, label=None):
    """A decal on `face_name` of `body` at `point` (the body's component's coordinates) with
    the picture `image_path` of `pixels` (w, h). Returns it (recomputed)."""
    if not image_path or not os.path.isfile(image_path):
        raise DecalError("The image was not found: %s" % (image_path or "(no file)"))
    if os.path.splitext(image_path)[1].lower() not in IMAGE_EXTENSIONS:
        raise DecalError("Choose a PNG, JPEG, TIFF or BMP image.")
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
    anchor, kind, cylinder = frame_at(face, point)
    doc = body.Document
    obj = doc.addObject("App::FeaturePython", "Decal")
    DecalFeature(obj)
    obj.Label = label or unique_label(doc, os.path.splitext(os.path.basename(image_path))[0])
    obj.Body = body
    obj.FaceName = face_name
    obj.Anchor = anchor
    obj.Surface = kind
    if cylinder:
        obj.AxisPoint = cylinder["point"]
        obj.AxisDirection = cylinder["axis"]
        obj.Radius = cylinder["radius"]
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
