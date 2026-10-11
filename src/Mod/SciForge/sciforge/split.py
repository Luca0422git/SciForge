# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Split Body (Modify > Split Body): the document side, no Qt. The dialog
(split_ui.py) and the golden-model builder both call build().

Options (dict, see DEFAULTS):
  body     the body to split
  tool     the splitting tool, (object, sub-element):
             (origin plane or construction plane, "")   an endless plane
             (feature, "FaceN")                        a face of a body (this one or another)
             (body, "")                                another body: split along its faces
  extend   Extend Splitting Tool: a flat face is taken as its whole plane, a round face as
           its whole cylinder (Fusion's default, on). Off: only where the face is.

What is built: a "Split Body" step (SciForgeType "SplitBody", SplitFeature below) in the body
to split; the body keeps one piece (the biggest; for equal pieces the one nearest the origin
in X, then Y, then Z) and every other piece becomes a new body, whose first step
(SplitPiece, hidden from the timeline) takes that piece from the split. Pieces are matched
by where they were when the split was made, so editing an earlier step keeps each piece
in its own body. Deleting the Split Body step removes the new bodies again (bodies_gui.Watch
and delete.py), as in Fusion.
"""
import FreeCAD as App
import Part

from . import bodies

TYPE = "PartDesign::FeaturePython"
PIECE_TYPE = "Part::FeaturePython"
SCIFORGE_TYPE = "SplitBody"
META = "SciForgeSplit"
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")

DEFAULTS = {"body": None, "tool": None, "extend": True}


class SplitError(ValueError):
    """The split cannot be made as asked; the message says why and what to do."""


class NeedsPick(SplitError):
    """A selection box still waits for its click."""


def with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update(options or {})
    return merged


def is_split(obj):
    return bodies.kind(obj) == SCIFORGE_TYPE


def is_piece(obj):
    return obj is not None and isinstance(getattr(obj, "Proxy", None), SplitPiece)


# -- geometry ---------------------------------------------------------------------------------
def tool_shape(tool, extend, around):
    """The splitting tool in design coordinates. `around`: the shape to split (an endless
    plane is made big enough to cross all of it)."""
    obj, sub = tool
    size = max(around.BoundBox.DiagonalLength, 1.0) * 4.0 + _far(obj, around)
    if obj.TypeId in PLANE_TYPES:
        place = obj.getGlobalPlacement()
        normal = place.Rotation.multVec(App.Vector(0, 0, 1))
        return _plane_face(place.Base, normal, around, size)
    if bodies.is_body(obj) or (not sub and obj.isDerivedFrom("Part::Feature")):
        shape = bodies.global_shape(obj)
        if shape.isNull() or not shape.Solids:
            raise SplitError("%s has no solid to split with." % obj.Label)
        return shape
    if not sub.startswith("Face"):
        raise SplitError("Split with a plane, a face or a body.")
    face = _global_face(obj, sub)
    surface = face.Surface
    if extend:
        if surface.TypeId == "Part::GeomPlane":
            normal = face.normalAt(*_mid_uv(face))
            return _plane_face(face.CenterOfMass, normal, around, size)
        if surface.TypeId == "Part::GeomCylinder":
            axis = App.Vector(surface.Axis).normalize()
            center = App.Vector(surface.Center)
            base = center - axis * size
            return Part.makeCylinder(surface.Radius, 2 * size, base, axis).Faces[0]
    return face


def _far(obj, around):
    """How far the tool is from the shape (an endless plane must still reach it)."""
    try:
        return around.BoundBox.Center.Length + obj.getGlobalPlacement().Base.Length
    except Exception:
        return 0.0


def _mid_uv(face):
    u0, u1, v0, v1 = face.ParameterRange
    return (u0 + u1) / 2.0, (v0 + v1) / 2.0


def _plane_face(point, normal, around, size):
    plane = Part.Plane(App.Vector(point), App.Vector(normal))
    # Centre the face on the shape: the projection of its centre onto the plane.
    center = around.BoundBox.Center
    u, v = plane.parameter(center)
    return plane.toShape(u - size, u + size, v - size, v + size)


def _global_face(obj, sub):
    try:
        face = obj.Shape.getElement(sub)
    except Exception:
        raise SplitError(
            "The splitting face no longer exists (an earlier step changed the model). Edit the "
            "Split Body and pick the splitting tool again."
        )
    face = face.copy()
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        parent = None
    if parent is not None:
        place = parent.getGlobalPlacement()
        if not place.isIdentity():
            face.transformShape(place.toMatrix(), True)
    return face


def split_shape(shape, tool):
    """The solids `shape` falls into when split by `tool` (both in design coordinates)."""
    import BOPTools.SplitAPI as split_api

    try:
        result = split_api.slice(shape, [tool], "Split")
    except Exception as exc:
        raise SplitError("The body cannot be split there: %s" % exc)
    return [s for s in result.Solids if s.Volume > 1e-9]


def order(pieces, centers=None):
    """Pieces in a stable order. Without remembered `centers` (a new split): the biggest
    first, equal ones by position. With them: each remembered centre takes the nearest piece,
    so every body keeps its own piece after earlier steps change."""

    def key(s):
        c = s.CenterOfMass
        return (-round(s.Volume, 6), round(c.x, 6), round(c.y, 6), round(c.z, 6))

    pieces = sorted(pieces, key=key)
    if not centers:
        return pieces
    left = list(pieces)
    out = []
    for center in centers:
        if not left:
            break
        point = App.Vector(*center)
        best = min(left, key=lambda s: (s.CenterOfMass - point).Length)
        out.append(best)
        left.remove(best)
    return out + left


# -- the features ---------------------------------------------------------------------------------
class SplitFeature:
    """The Split Body step in the body that is split. Saved as "sciforge.split.SplitFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Split Body", doc)
                return True
            return False

        add("App::PropertyLinkSubGlobal", "Tool", "The splitting tool")
        if add("App::PropertyBool", "Extend", "Extend Splitting Tool"):
            obj.Extend = True
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane"):
            obj.Refine = True
        if "OtherPieces" not in obj.PropertiesList:
            # The pieces that went to new bodies (design coordinates), read by SplitPiece.
            obj.addProperty("Part::PropertyPartShape", "OtherPieces", "Split Body", "", 4 | 16)
        bodies.mark(obj, SCIFORGE_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        body = bodies.body_of(obj)
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise SplitError("There is no solid before this step to split.")
        link = obj.Tool
        if not link or link[0] is None:
            raise SplitError(
                "Its splitting tool is gone (deleted?). Edit the Split Body and pick a tool."
            )
        sub = (list(link[1]) or [""])[0]
        shape = bodies.global_shape(base)
        tool = tool_shape((link[0], sub), bool(obj.Extend), shape)
        pieces = split_shape(shape, tool)
        if len(pieces) < 2:
            raise SplitError(
                "The splitting tool does not cut the body in two. Pick a tool that crosses the "
                "body, or turn on Extend Splitting Tool."
            )
        meta = bodies.load_meta(obj, META)
        pieces = order(pieces, meta.get("centers"))
        refine = bool(obj.Refine)
        first = bodies.as_result([pieces[0]], refine)
        obj.Shape = bodies.to_local(first, body)
        others = [bodies.as_result([p], refine) for p in pieces[1:]]
        obj.OtherPieces = Part.makeCompound(others) if others else Part.Shape()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class SplitPiece:
    """The first step of a body made by a split: one of the pieces. Saved as
    "sciforge.split.SplitPiece"."""

    def __init__(self, obj):
        obj.Proxy = self
        if "Split" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkGlobal", "Split", "Split Body", "The split")
        if "Index" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyInteger", "Index", "Split Body", "Which piece (1 = first)"
            )
        bodies.hide_from_timeline(obj)

    def execute(self, obj):
        split = obj.Split
        if split is None:
            return  # the body that was split is gone: this body keeps its shape
        others = split.OtherPieces.Solids if not split.OtherPieces.isNull() else []
        if obj.Index - 1 >= len(others):
            return  # fewer pieces now: keeps its last shape (the dialog says so)
        obj.Shape = others[obj.Index - 1].copy()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


# -- reading and building -----------------------------------------------------------------------
def check(options):
    body, tool = options["body"], options["tool"]
    if body is None:
        raise NeedsPick("Select the body to split.")
    if tool is None:
        raise NeedsPick("Select the splitting tool: a plane, a face or another body.")
    if not bodies.has_solid(body):
        raise SplitError("%s has no solid to split." % body.Label)
    obj, sub = tool
    if bodies.is_body(obj) and obj is body:
        raise SplitError("A body cannot split itself. Pick a plane, a face or another body.")


def tool_link(tool):
    """What the feature links: a body is linked through its last step (its Tip)."""
    obj, sub = tool
    if bodies.is_body(obj):
        return (obj.Tip, "")
    return (obj, sub)


def preview_pieces(options, feature=None):
    """The pieces the split makes now, in order (design coordinates)."""
    body = options["body"]
    base = feature.BaseFeature if feature is not None else body.Tip
    shape = bodies.global_shape(base)
    tool = tool_shape(tool_link(options["tool"]), bool(options["extend"]), shape)
    pieces = split_shape(shape, tool)
    if len(pieces) < 2:
        raise SplitError(
            "The splitting tool does not cut the body in two. Pick a tool that crosses the "
            "body, or turn on Extend Splitting Tool."
        )
    meta = bodies.load_meta(feature, META) if feature is not None else {}
    return order(pieces, meta.get("centers"))


def build(options, feature=None, name="SplitBody"):
    """Create the split (or update `feature`); returns it. Adds a body for every piece but
    the first, and removes bodies of pieces that are no longer there."""
    options = with_defaults(options)
    check(options)
    body = options["body"]
    if feature is not None and bodies.alive(feature) and bodies.body_of(feature) is not body:
        remove(feature)
        feature = None
    pieces = preview_pieces(options, feature if bodies.alive(feature) else None)
    if feature is None or not bodies.alive(feature):
        feature = bodies.insert_after_tip(body, TYPE, name)
        SplitFeature(feature)
        _attach_view_provider(feature)
    link = tool_link(options["tool"])
    current = feature.Tool
    if not current or current[0] is not link[0] or (list(current[1]) or [""])[0] != link[1]:
        feature.Tool = (link[0], [link[1]])
    if bool(feature.Extend) != bool(options["extend"]):
        feature.Extend = bool(options["extend"])
    # Remembered in design coordinates: the pieces are matched in the same frame.
    centers = [list(p.CenterOfMass) for p in pieces]
    bodies.save_meta(feature, META, {"v": 1, "centers": centers})
    _sync_bodies(feature, len(pieces) - 1)
    return feature


def pieces_of(feature):
    found = [o for o in feature.InList if is_piece(o) and o.Split is feature]
    return sorted(found, key=lambda o: o.Index)


def piece_body(piece):
    for obj in piece.InList:
        if bodies.is_body(obj) and obj.BaseFeature is piece:
            return obj
    return None


def piece_bodies(feature):
    return [b for b in (piece_body(p) for p in pieces_of(feature)) if b is not None]


def _sync_bodies(feature, count):
    doc = feature.Document
    pieces = pieces_of(feature)
    for piece in pieces[count:]:
        _remove_piece(piece)
    source = bodies.body_of(feature)
    for index in range(len(pieces) + 1, count + 1):
        piece = doc.addObject(PIECE_TYPE, "SplitPiece")
        SplitPiece(piece)
        piece.Split = feature
        piece.Index = index
        bodies.save_meta(piece, META, {"source": source.Name})
        body = bodies.new_body(doc, like=source)
        body.BaseFeature = piece
        for obj in body.Group:
            if obj.TypeId == "PartDesign::FeatureBase":
                bodies.hide_from_timeline(obj)
        if App.GuiUp:
            try:
                piece.ViewObject.Visibility = False
            except Exception:
                pass
        _copy_look(source, body)


def _copy_look(source, body):
    """A piece keeps the material (and so the look) of the body it came from."""
    try:
        body.ShapeMaterial = source.ShapeMaterial
    except Exception:
        pass
    try:
        from . import appearance

        appearance.copy_body_appearance(source, body)
    except Exception:
        pass


def _remove_piece(piece):
    body = piece_body(piece)
    if body is not None:
        bodies.remove_body(body)
    try:
        piece.Document.removeObject(piece.Name)
    except Exception:
        pass


def remove(feature):
    """Take a split out again with the bodies it made (cancel, or Delete)."""
    if not bodies.alive(feature):
        return
    for piece in pieces_of(feature):
        _remove_piece(piece)
    bodies.remove_step(feature)


def read(feature):
    link = feature.Tool
    tool = None
    if link and link[0] is not None:
        obj, sub = link[0], (list(link[1]) or [""])[0]
        source = bodies.body_of(feature)
        other = bodies.body_of(obj)
        if not sub and other is not None and other is not source and obj is other.Tip:
            tool = (other, "")  # a whole body was picked
        else:
            tool = (obj, sub)
    return with_defaults(
        {"body": bodies.body_of(feature), "tool": tool, "extend": bool(feature.Extend)}
    )


def orphan_pieces(doc):
    """Pieces whose split step was deleted while the split body still exists (the timeline's
    Delete of the Split Body step): their bodies go too."""
    return [o for o in doc.Objects if is_piece(o) and o.Split is None and _was_split(o)]


def _was_split(piece):
    meta = bodies.load_meta(piece, META)
    name = meta.get("source")
    if not name:
        return False
    return piece.Document.getObject(name) is not None


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .bodies_gui import StepViewProvider

        StepViewProvider(obj.ViewObject)
    except Exception:
        pass
