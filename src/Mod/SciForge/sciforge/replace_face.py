# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Replace Face (Modify > Replace Face): the document side, no Qt. replace_face_ui.py
is the dialog; the golden-model builder calls build() too.

Options (dict, see DEFAULTS):
  faces          (feature, ["FaceN", ...]): the source faces, on the body's current end
  tangent_chain  also the faces that continue them smoothly (Fusion's default: on)
  target         (object, "FaceN") a face of any body, or (plane, "") an origin or
                 construction plane: where the source faces go

What happens (Fusion: "the source faces are removed, the faces around them are extended or
trimmed to the target, the new face is stitched in"): the column of material straight over
the source faces (along their normal) is filled up to the target where the target lies
outside the part, and cut back to it where it lies inside; the steps the column's sides leave
next to sloped neighbours are healed by OpenCASCADE's defeaturing, which extends those
neighbours (the same healing as Press Pull, presspull_core). Flat targets are taken as their
whole plane, round and spherical ones as the whole cylinder / sphere (Fusion requires the
target to cross the whole region; SciForge extends it). Other curved targets are refused.

What is built: a "Replace Face" step (SciForgeType "ReplaceFace", ReplaceFaceFeature) at the
history marker of the body: editable later, rebuilt when earlier steps change; the target
is linked, so moving the target face or plane moves the result (Fusion's Replace Face is
parametric the same way).
"""

import FreeCAD as App

from . import bodies, curves, presspull_core as pp

TYPE = "PartDesign::FeaturePython"
SCIFORGE_TYPE = "ReplaceFace"
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
DEFAULTS = {"faces": None, "tangent_chain": True, "target": None}
TOL = 1e-6


class ReplaceFaceError(ValueError):
    """The faces cannot be replaced as asked; the message says why and what to do."""


class NeedsPick(ReplaceFaceError):
    """A selection box still waits for its click."""


def with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update(options or {})
    return merged


def is_replace_face(obj):
    return bodies.kind(obj) == SCIFORGE_TYPE


# -- geometry ----------------------------------------------------------------------------------
def _direction(faces):
    """The direction the faces are replaced along: the mean outward normal of the faces that
    face the same way as the first (a flat face's normal for a flat face)."""
    first = pp.face_normal(faces[0])
    total = App.Vector()
    for face in faces:
        normal = pp.face_normal(face)
        if normal.dot(first) > 0.1:
            total += normal * face.Area
    if total.Length < TOL:
        return App.Vector(first).normalize()
    return total.normalize()


def _movable(faces, direction):
    """The faces a column along ``direction`` can replace (a wall parallel to it cannot: a
    Tangent Chain that reaches the side walls leaves them as they are)."""
    return [f for f in faces if pp.face_normal(f).dot(direction) > 0.1]


def _crossing(target, point, direction, size):
    """Where the line through ``point`` along ``direction`` meets the target surface: the
    signed distance (the one nearest the face), or None."""
    import Part

    line = Part.LineSegment(point - direction * size, point + direction * size).toShape()
    try:
        section = line.section(target)
    except Exception:
        return None
    best = None
    for vertex in section.Vertexes:
        t = (vertex.Point - point).dot(direction)
        if best is None or abs(t) < abs(best):
            best = t
    return best


def target_surface(target, around, size):
    """The target as an extended face in the body's coordinates: a flat face or a plane is
    its whole plane, a round face its whole cylinder, a spherical face its whole sphere."""
    import Part

    kind = type(target.Surface).__name__
    if kind == "Plane":
        normal = pp.face_normal(target)
        plane = Part.Plane(target.CenterOfMass, normal)
        center = around.BoundBox.Center
        u, v = plane.parameter(center)
        return plane.toShape(u - size, u + size, v - size, v + size)
    if kind == "Cylinder":
        surf = target.Surface
        axis = App.Vector(surf.Axis).normalize()
        center = App.Vector(surf.Center)
        reach = size + (around.BoundBox.Center - center).Length
        return Part.makeCylinder(surf.Radius, 2 * reach, center - axis * reach, axis).Faces[0]
    if kind == "Sphere":
        surf = target.Surface
        return Part.makeSphere(surf.Radius, App.Vector(surf.Center)).Faces[0]
    raise ReplaceFaceError(
        "Replace Face can move faces onto a flat face, a plane, a round (cylindrical) or a "
        "spherical face. Pick one of those as the target."
    )


def _inner_region(target, kind, point_in, size, around):
    """The solid on the part's side of the extended target (the side ``point_in`` is on)."""
    import Part

    if kind == "Plane":
        normal = pp.face_normal(target)
        if (point_in - target.CenterOfMass).dot(normal) < 0:
            normal = normal * -1  # towards the part's side
        slab = target.copy()
        return slab.extrude(normal * size * 2)
    surf = target.Surface
    if kind == "Cylinder":
        axis = App.Vector(surf.Axis).normalize()
        center = App.Vector(surf.Center)
        reach = size + (around.BoundBox.Center - center).Length
        solid = Part.makeCylinder(surf.Radius, 2 * reach, center - axis * reach, axis)
    else:
        solid = Part.makeSphere(surf.Radius, App.Vector(surf.Center))
    if solid.isInside(point_in, TOL, True):
        return solid
    box = _big_box(around, size)
    return box.cut(solid)


def _big_box(around, size):
    import Part

    center = around.BoundBox.Center
    return Part.makeBox(
        4 * size, 4 * size, 4 * size, center - App.Vector(2 * size, 2 * size, 2 * size)
    )


def replace(base, sources, target, refine=True, report=None):
    """New shape: ``base`` with the faces ``sources`` (Part.Face objects of base) replaced by
    the target face ``target`` (a Part.Face, body coordinates). Raises ReplaceFaceError."""
    if not sources:
        raise ReplaceFaceError("Select the faces to replace.")
    if base.isNull() or not base.Solids:
        raise ReplaceFaceError("There is no solid before this step.")
    direction = _direction(sources)
    faces = _movable(sources, direction)
    if not faces:
        raise ReplaceFaceError(
            "These faces cannot be moved onto the target. Pick the faces that face the target."
        )
    size = max(base.BoundBox.DiagonalLength, 1.0) * 3.0 + 50.0
    kind = type(target.Surface).__name__
    surface = target_surface(target, base, size)
    center = faces[0].CenterOfMass
    t = _crossing(surface, center, direction, size * 2)
    if t is None:
        raise ReplaceFaceError(
            "The target does not lie in front of or behind the faces: pick a target the faces "
            "can be moved straight onto."
        )
    meet = center + direction * t
    region = _inner_region(surface, kind, meet - direction * 0.01, size, base)
    columns_out, columns_in = [], []
    for face in faces:
        columns_out.append(face.extrude(direction * size))
        back = face.copy()
        back.translate(direction * -size)
        columns_in.append(back.extrude(direction * size))
    try:
        out = _fuse_all(columns_out)
        column = out.fuse(_fuse_all(columns_in))
        add = out.common(region)
        cut = column.cut(region)
        result = base
        if not add.isNull() and add.Volume > TOL:
            result = result.fuse(add)
        if not cut.isNull() and cut.Volume > TOL:
            result = result.cut(cut)
        if refine:
            result = result.removeSplitter()
    except Exception as exc:
        raise ReplaceFaceError("The kernel could not move the faces there: %s" % exc)
    steps = pp.step_faces(base, faces, columns_out + columns_in, result)
    if steps:
        healed = pp.extend_neighbours(result, steps, refine)
        if healed is not None:
            result = healed
        elif report is not None:
            report.append(
                "The faces next to the replaced ones could not be extended to meet the "
                "target; the result keeps a step there."
            )
    if result.isNull() or not result.Solids:
        raise ReplaceFaceError("Moving the faces there would remove the whole body.")
    if len(result.Solids) > len(base.Solids):
        raise ReplaceFaceError(
            "Moving the faces there would cut the body into pieces. Pick a target that "
            "does not cross the whole body."
        )
    if not result.isValid():
        raise ReplaceFaceError("The result is not a valid solid. Try another target.")
    return result


def _fuse_all(shapes):
    if len(shapes) == 1:
        return shapes[0]
    return shapes[0].multiFuse(shapes[1:])


# -- the step ----------------------------------------------------------------------------------
def _local_target(obj, sub, body):
    """The target face (or the plane, as a face) in ``body``'s coordinates."""
    import Part

    if obj is None:
        raise ReplaceFaceError(
            "Its target is gone (deleted?). Edit the Replace Face and pick a target."
        )
    if obj.TypeId in PLANE_TYPES or (not sub and obj.TypeId.endswith("Plane")):
        place = obj.getGlobalPlacement()
        normal = place.Rotation.multVec(App.Vector(0, 0, 1))
        face = Part.Plane(place.Base, normal).toShape(-1, 1, -1, 1)
    else:
        if not sub.startswith("Face"):
            raise ReplaceFaceError("Pick a face or a plane as the target.")
        try:
            face = _global_face(obj, sub)
        except Exception:
            raise ReplaceFaceError(
                "The target face no longer exists (an earlier step changed the model). Edit the "
                "Replace Face and pick the target again."
            )
    return bodies.to_local(face, body)


def _global_face(obj, sub):
    face = obj.Shape.getElement(sub).copy()
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        parent = None
    if parent is not None:
        place = parent.getGlobalPlacement()
        if not place.isIdentity():
            face.transformShape(place.toMatrix(), True)
    return face


class ReplaceFaceFeature:
    """The Replace Face step. Saved as "sciforge.replace_face.ReplaceFaceFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Replace Face", doc)
                return True
            return False

        add("App::PropertyLinkSub", "Faces", "The faces replaced (source faces)")
        if add("App::PropertyBool", "TangentChain", "Also the faces that continue them smoothly"):
            obj.TangentChain = True
        add("App::PropertyLinkSubGlobal", "Target", "The face or plane they go to")
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane"):
            obj.Refine = True
        bodies.mark(obj, SCIFORGE_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            self._build(obj)
        except Exception:
            bodies.pass_through(obj)  # the faces stay as they were, the step red
            raise

    def _build(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise ReplaceFaceError("There is no solid before this step.")
        curves.refind(obj, ("Faces",))
        link = obj.Faces
        if not link or not link[1]:
            raise ReplaceFaceError("Select the faces to replace.")
        source, names = link[0], list(link[1])
        if obj.TangentChain:
            names = pp.tangent_chain(source.Shape, names)
        faces = []
        for name in names:
            try:
                faces.append(source.Shape.getElement(name))
            except Exception:
                raise ReplaceFaceError(
                    "The face %s no longer exists (an earlier step changed the model). Edit "
                    "the Replace Face and pick the faces again." % name
                )
        target = obj.Target
        if not target or target[0] is None:
            raise ReplaceFaceError(
                "Its target is gone (deleted?). Edit the Replace Face and pick a target."
            )
        sub = (list(target[1]) or [""])[0]
        body = bodies.body_of(obj)
        face = _local_target(target[0], sub, body)
        notes = []
        obj.Shape = replace(base.Shape, faces, face, bool(obj.Refine), notes)
        curves.remember(obj, ("Faces",))
        self.note = " ".join(notes)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def check(options):
    faces, target = options["faces"], options["target"]
    if not faces or not faces[1]:
        raise NeedsPick("Select the faces to replace (faces of one body).")
    if target is None:
        raise NeedsPick("Select the target: a face of any body, or a plane.")


def build(options, feature=None, name="ReplaceFace"):
    """Create the Replace Face step (or update ``feature``). Returns it."""
    options = with_defaults(options)
    check(options)
    source, names = options["faces"]
    body = bodies.body_of(source)
    if body is None:
        raise ReplaceFaceError("The faces must be faces of a body.")
    if feature is not None and bodies.alive(feature) and bodies.body_of(feature) is not body:
        bodies.remove_step(feature)
        feature = None
    if feature is None or not bodies.alive(feature):
        feature = bodies.insert_after_tip(body, TYPE, name)
        ReplaceFaceFeature(feature)
        _attach_view_provider(feature)
    feature.Faces = (source, list(names))
    if bool(feature.TangentChain) != bool(options["tangent_chain"]):
        feature.TangentChain = bool(options["tangent_chain"])
    obj, sub = options["target"]
    current = feature.Target
    if not current or current[0] is not obj or (list(current[1]) or [""])[0] != sub:
        feature.Target = (obj, [sub])
    return feature


def read(feature):
    link = feature.Faces
    target = feature.Target
    return with_defaults(
        {
            "faces": (link[0], list(link[1])) if link else None,
            "tangent_chain": bool(feature.TangentChain),
            "target": (target[0], (list(target[1]) or [""])[0]) if target else None,
        }
    )


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .bodies_gui import StepViewProvider

        StepViewProvider(obj.ViewObject)
    except Exception:
        pass
