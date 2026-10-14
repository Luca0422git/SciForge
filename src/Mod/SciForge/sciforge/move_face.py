# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Move/Copy with Move Object "Faces": the document side, no Qt. The Move dialog
(move_ui.py) and the golden-model builder both call build().

Fusion moves the picked faces and heals the part around them (a direct edit recorded as a
Move step). SciForge does the same in two ways:
  * the faces close up into a feature (every face of a hole, a pocket or a boss: the same
    test as Pattern Type Faces, pattern.face_tool): that feature is taken out of the part
    (a hole filled, a boss cut away) and put back where the move takes it;
  * flat faces: each face's plane is moved (turned) and the faces around it are extended or
    trimmed to meet it (Replace Face's healing, replace_face.replace). A flat face moved
    within its own plane does not change the part, as in Fusion.
Other faces (a fillet's round alone, a free-form face) are refused with the reason.

Options are move.py's (move_type, dx/dy/dz, rx/ry/rz, pivot, axis, points...) plus
  faces   (feature, ["FaceN", ...]): the faces, on the body's current end
The step: "Move" in the timeline (SciForgeType "MoveFace", MoveFaceFeature), at the history
marker of the faces' body; the movement is stored as a placement in design coordinates,
like Fusion's Move feature.
"""

import FreeCAD as App

from . import bodies, move

TYPE = "PartDesign::FeaturePython"
SCIFORGE_TYPE = "MoveFace"
META = "SciForgeMove"
TOL = 1e-7


class MoveFaceError(move.MoveError):
    """The faces cannot be moved as asked; the message says why and what to try."""


def is_move_face(obj):
    return bodies.kind(obj) == SCIFORGE_TYPE


# -- geometry ----------------------------------------------------------------------------------
def _inner_point(face):
    from . import drafting

    return drafting._inner_point(face)


def _face_at(shape, point):
    import Part

    probe = Part.Vertex(point)
    for face in shape.Faces:
        try:
            if face.distToShape(probe)[0] < 1e-6:
                return face
        except Exception:
            continue
    return None


def _same_plane(a, b, tol=1e-7):
    na = a.Surface.Axis
    nb = b.Surface.Axis
    if abs(abs(na.dot(nb)) - 1.0) > 1e-9:
        return False
    return abs((b.Surface.Position - a.Surface.Position).dot(na)) < tol


def _moved(shape, place):
    out = shape.copy()
    out.transformShape(place.toMatrix(), True)
    return out


def _one_solid(base, result, what):
    solids = bodies.solids_of(result)
    if not solids:
        raise MoveFaceError("Moving the faces there would remove the whole body.")
    if len(solids) > max(1, len(bodies.solids_of(base))):
        raise MoveFaceError(
            "Moving %s there would leave the part in pieces. Move it less far." % what
        )
    out = bodies.as_result(solids, refine=True)
    if not out.isValid():
        raise MoveFaceError("Moving the faces gave an invalid solid. Try another move.")
    return out


def move_faces(shape, faces, place):
    """`shape` (design coordinates) with `faces` (faces of it) moved by `place`. Raises
    MoveFaceError with the reason."""
    from . import pattern, replace_face
    from .pattern_core import PatternError

    if not faces:
        raise MoveFaceError("Select the faces to move.")
    if move.is_identity(place):
        return shape.copy()
    try:
        solid, how = pattern.face_tool(shape, faces)
    except PatternError:
        solid = None
    except Exception:
        solid = None
    if solid is not None:
        moved = _moved(solid, place)
        try:
            if how == "cut":  # a hole or a pocket: filled where it was, cut where it goes
                result = shape.fuse(solid).cut(moved)
                what = "the hole"
            else:  # a boss: cut away where it was, joined where it goes
                result = shape.cut(solid).fuse(moved)
                what = "the boss"
        except Exception as exc:
            raise MoveFaceError("The kernel could not move the faces there: %s" % exc)
        return _one_solid(shape, result, what)
    flat = [f for f in faces if f.Surface.TypeId == "Part::GeomPlane"]
    if len(flat) != len(faces):
        raise MoveFaceError(
            "Only flat faces, or every face of a hole, a pocket or a boss, can be moved. Pick "
            "all the faces of the feature, or flat faces."
        )
    points = [_inner_point(f) for f in faces]
    result = shape
    for face, point in zip(faces, points):
        current = _face_at(result, point)
        if current is None:
            continue  # an earlier face's move took this one in
        target = _moved(current, place)
        if _same_plane(current, target):
            continue  # moved within its own plane: nothing changes (Fusion)
        try:
            result = replace_face.replace(result, [current], target, refine=True)
        except replace_face.ReplaceFaceError as exc:
            raise MoveFaceError(str(exc))
    return _one_solid(shape, result, "the faces")


# -- the step ----------------------------------------------------------------------------------
class MoveFaceFeature:
    """The Move step of faces. Saved as "sciforge.move_face.MoveFaceFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Move", doc)
                return True
            return False

        add("App::PropertyLinkSub", "Faces", "The faces moved")
        add("App::PropertyPlacement", "Movement", "The movement, in design coordinates")
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane"):
            obj.Refine = True
        bodies.mark(obj, SCIFORGE_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            self._build(obj)
        except Exception:
            bodies.pass_through(obj)
            raise

    def _build(self, obj):
        from . import curves

        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise MoveFaceError("There is no solid before this step.")
        try:
            curves.refind(obj, ("Faces",))
        except Exception:
            pass
        link = obj.Faces
        if not link or not link[1]:
            raise MoveFaceError("Select the faces to move.")
        source, names = link[0], [n.lstrip("?") for n in link[1]]
        body = bodies.body_of(obj)
        shape = bodies.global_shape(base)
        faces = []
        for name in names:
            try:
                # Faces of the shape itself (not copies): the feature test walks its edges.
                if source is base:
                    faces.append(shape.getElement(name))
                else:
                    faces.append(_matching_face(shape, _global_face(source, name)))
            except Exception:
                raise MoveFaceError(
                    "The face %s no longer exists (an earlier step changed the part). Edit "
                    "the Move and pick the faces again." % name
                )
        result = move_faces(shape, faces, obj.Movement)
        obj.Shape = bodies.to_local(result, body)
        try:
            curves.remember(obj, ("Faces",))
        except Exception:
            pass

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _matching_face(shape, face):
    """The face of `shape` at the place of `face` (a face picked on another step)."""
    point = _inner_point(face)
    found = _face_at(shape, point)
    if found is None or found.Surface.TypeId != face.Surface.TypeId:
        raise MoveFaceError("A picked face is not on the part before this step.")
    return found


def _global_face(obj, name):
    face = obj.Shape.getElement(name).copy()
    body = bodies.body_of(obj)
    if body is not None:
        place = body.getGlobalPlacement()
        if not place.isIdentity():
            face.transformShape(place.toMatrix(), True)
    return face


def check(options):
    faces = options.get("faces")
    if not faces or not faces[1]:
        raise move.NeedsPick("Select the faces to move.")
    move.transform(options)  # raises NeedsPick while an axis or a point is still missing


def build(options, feature=None, name="Move"):
    """Create the Move step of faces, or update `feature`. Returns it."""
    options = move.with_defaults(options)
    check(options)
    source, names = options["faces"]
    body = bodies.body_of(source)
    if body is None:
        raise MoveFaceError("The faces must be faces of a body.")
    if feature is not None and bodies.alive(feature) and bodies.body_of(feature) is not body:
        bodies.remove_step(feature)
        feature = None
    if feature is None or not bodies.alive(feature):
        feature = bodies.insert_after_tip(body, TYPE, name)
        MoveFaceFeature(feature)
        _attach_view_provider(feature)
    old = feature.Faces
    if not (old and old[0] is source and list(old[1]) == list(names)):
        feature.Faces = (source, list(names))
    place = move.transform(options)
    if not feature.Movement.isSame(place, 1e-12):
        feature.Movement = place
    meta = move._meta(options)
    meta["move_object"] = "faces"
    bodies.save_meta(feature, META, meta)
    return feature


def read(feature):
    """The dialog options of a Move step of faces."""
    meta = bodies.load_meta(feature, META)
    options = move.with_defaults({})
    for key in ("move_type", "axis_label", "from_label", "to_label") + move.NUMBERS:
        if key in meta:
            options[key] = meta[key]
    for key in move.POINTS:
        if meta.get(key) is not None:
            options[key] = list(meta[key])
    link = feature.Faces
    options["faces"] = (link[0], [n.lstrip("?") for n in link[1]]) if link else None
    options["move_object"] = "faces"
    return options


def remove(feature):
    bodies.remove_step(feature)


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .bodies_gui import StepViewProvider

        StepViewProvider(obj.ViewObject)
    except Exception:
        pass
