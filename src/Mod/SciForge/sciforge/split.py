# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Split Body (Modify > Split Body): the document side, no Qt. The dialog
(split_ui.py) and the golden-model builder both call build().

Options (dict, see DEFAULTS):
  body     the body to split
  tools    the splitting tools (Fusion's Splitting Tool(s): several at once, one step), each
           (object, sub-element) as below; ``tool`` is the first of them
  tool     the splitting tool, (object, sub-element):
             (origin plane or construction plane, "")   an endless plane
             (feature, "FaceN")                        a face of a body (this one or another)
             (body, "")                                another body: split along its faces
             (sketch, "EdgeN")                         a sketch curve, cut straight through
                                                       along the sketch's normal
  extend   Extend Splitting Tool: a flat face (a sketch line) is taken as its whole plane, a
           round face (a sketch arc) as its whole cylinder (Fusion's default, on). Off: only
           where the face (curve) is.

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

from . import bodies, split_core

TYPE = "PartDesign::FeaturePython"
PIECE_TYPE = "Part::FeaturePython"
SCIFORGE_TYPE = "SplitBody"
META = "SciForgeSplit"
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")

DEFAULTS = {"body": None, "tool": None, "tools": None, "extend": True}


class SplitError(ValueError):
    """The split cannot be made as asked; the message says why and what to do."""


class NeedsPick(SplitError):
    """A selection box still waits for its click."""


def with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update(options or {})
    tools = merged.get("tools")
    if tools is None:  # one tool given the old way
        tools = [merged["tool"]] if merged.get("tool") is not None else []
    elif merged.get("tool") is not None and (not tools or tools[0] != merged["tool"]):
        tools = [merged["tool"]] + list(tools[1:])  # "tool" changed: the first tool
    merged["tools"] = [t for t in tools if t is not None]
    merged["tool"] = merged["tools"][0] if merged["tools"] else None
    return merged


# Steps whose extra pieces live in bodies of their own (SplitPiece): Split Body, and
# Silhouette Split's Split Solid Body / Split Shelled Body (silhouette.py).
SPLIT_KINDS = (SCIFORGE_TYPE, "SilhouetteSplit")


def is_split(obj):
    return bodies.kind(obj) in SPLIT_KINDS


def is_piece(obj):
    return obj is not None and isinstance(getattr(obj, "Proxy", None), SplitPiece)


# -- geometry ---------------------------------------------------------------------------------
def tool_shape(tool, extend, around, fit=False):
    """The splitting tool in design coordinates. `around`: the shape to split (an endless
    plane is made big enough to cross all of it). fit: the dialog's red preview of the tool
    (split_core): the same plane or cylinder, only as big as `around` and the picked face
    (or sketch curve) together, plus a margin."""
    obj, sub = tool
    size = max(around.BoundBox.DiagonalLength, 1.0) * 4.0 + _far(obj, around)
    if obj.TypeId in PLANE_TYPES:
        place = obj.getGlobalPlacement()
        normal = place.Rotation.multVec(App.Vector(0, 0, 1))
        return _plane_face(place.Base, normal, around, size, fit)
    if obj.TypeId == "Sketcher::SketchObject":
        if not sub.startswith("Edge"):
            raise SplitError("Pick a curve of the sketch (a line, an arc...).")
        return _sketch_tool(obj, sub, extend, around, size, fit)
    if bodies.is_body(obj) or (not sub and obj.isDerivedFrom("Part::Feature")):
        shape = bodies.global_shape(obj)
        if shape.isNull() or not shape.Faces:
            raise SplitError("%s has nothing to split with." % obj.Label)
        if not shape.Solids:
            # A surface body as the Splitting Tool (Fusion: "body (solid or open)", the
            # classic hybrid workflow: cut a solid with a sculpted surface). Extend
            # Splitting Tool carries its open edges on (surfmod, surface-4).
            from . import surfmod

            return surfmod.extended_tool(shape, around) if extend and not fit else shape
        return shape
    if not sub.startswith("Face"):
        raise SplitError("Split with a plane, a face or a body.")
    face = _global_face(obj, sub)
    surface = face.Surface
    if fit:
        around = _with(around, face)  # the extension still holds the face itself
    if extend:
        if surface.TypeId == "Part::GeomPlane":
            normal = face.normalAt(*_mid_uv(face))
            return _plane_face(face.CenterOfMass, normal, around, size, fit)
        if surface.TypeId == "Part::GeomCylinder":
            axis = App.Vector(surface.Axis).normalize()
            return _cylinder_face(
                surface.Radius, App.Vector(surface.Center), axis, around, size, fit
            )
    return face


def _sketch_tool(sketch, sub, extend, around, size, fit=False):
    """A sketch curve cuts straight through, along the sketch's normal (Fusion). Extend
    Splitting Tool: a line is taken as its whole plane, an arc as its whole cylinder."""
    edge = _global_face(sketch, sub)
    normal = sketch.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
    curve = edge.Curve
    if fit:
        around = _with(around, edge)
    if extend and curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
        start = edge.valueAt(edge.FirstParameter)
        end = edge.valueAt(edge.LastParameter)
        if (end - start).Length < 1e-9:
            raise SplitError("That sketch line has no length.")
        side = (end - start).normalize().cross(normal)
        return _plane_face(start, side, around, size, fit)
    if extend and hasattr(curve, "Radius") and hasattr(curve, "Center"):
        return _cylinder_face(curve.Radius, App.Vector(curve.Center), normal, around, size, fit)
    low, high = -size, size
    if fit:
        low, high = split_core.cover_axis(_box(around), edge.valueAt(edge.FirstParameter), normal)
    swept = edge.copy()
    swept.translate(normal * low)
    return swept.extrude(normal * (high - low))


def _cylinder_face(radius, center, axis, around, size, fit=False):
    """The whole cylinder through a round face (or a sketch arc), along its axis: as long as
    the body plus a margin with fit, else far past it."""
    axis = App.Vector(axis).normalize()
    low, high = -size, size
    if fit:
        low, high = split_core.cover_axis(_box(around), center, axis)
    return Part.makeCylinder(radius, high - low, center + axis * low, axis).Faces[0]


def _with(around, shape):
    """`around` and `shape` together (only their size counts: the preview's cover)."""
    try:
        return Part.makeCompound([around, shape])
    except Exception:
        return around


def _box(shape):
    b = shape.BoundBox
    return (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)


def _far(obj, around):
    """How far the tool is from the shape (an endless plane must still reach it)."""
    try:
        return around.BoundBox.Center.Length + obj.getGlobalPlacement().Base.Length
    except Exception:
        return 0.0


def _mid_uv(face):
    u0, u1, v0, v1 = face.ParameterRange
    return (u0 + u1) / 2.0, (v0 + v1) / 2.0


def _plane_face(point, normal, around, size, fit=False):
    plane = Part.Plane(App.Vector(point), App.Vector(normal))
    if fit:  # the preview: just over the body's outline in this plane (split_core)
        box = _box(around)
        uvs = [plane.parameter(App.Vector(*c)) for c in split_core.corners(box)]
        u0, u1, v0, v1 = split_core.cover_uv(uvs, split_core.margin(box))
        return plane.toShape(u0, u1, v0, v1)
    # Centre the face on the shape: the projection of its centre onto the plane.
    center = around.BoundBox.Center
    u, v = plane.parameter(center)
    return plane.toShape(u - size, u + size, v - size, v + size)


def _global_face(obj, sub):
    """Element `sub` of `obj` (a face, or a sketch's edge) in design coordinates."""
    try:
        face = obj.Shape.getElement(sub)
    except Exception:
        raise SplitError(
            "The splitting tool no longer exists (an earlier step changed the model). Edit the "
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
    """The solids `shape` falls into when split by `tool` (both in design coordinates; a list
    of tools splits by all of them at once). A surface body (faces, no solid: Fusion's
    "open body") falls into surfaces: its connected pieces (surface-4)."""
    import BOPTools.SplitAPI as split_api

    tools = list(tool) if isinstance(tool, (list, tuple)) else [tool]
    try:
        result = split_api.slice(shape, tools, "Split")
    except Exception as exc:
        raise SplitError("The body cannot be split there: %s" % exc)
    if not shape.Solids:
        from . import surfmod

        return surfmod.open_pieces(result)
    return [s for s in result.Solids if s.Volume > 1e-9]


def _size(shape):
    """A piece's size: its volume, or its area for a surface piece."""
    return shape.Volume if shape.Solids else shape.Area


def order(pieces, centers=None):
    """Pieces in a stable order. Without remembered `centers` (a new split): the biggest
    first, equal ones by position. With them: each remembered centre takes the nearest piece,
    so every body keeps its own piece after earlier steps change."""

    def key(s):
        c = s.CenterOfMass
        return (-round(_size(s), 6), round(c.x, 6), round(c.y, 6), round(c.z, 6))

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
        # Fusion's Splitting Tool(s): the tools after the first (components-2)
        add("App::PropertyLinkSubListGlobal", "MoreTools", "More splitting tools")
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
        if base is None or base.Shape.isNull() or not base.Shape.Faces:
            raise SplitError("There is no body before this step to split.")
        refs = feature_tools(obj)
        if not refs:
            raise SplitError(
                "Its splitting tool is gone (deleted?). Edit the Split Body and pick a tool."
            )
        shape = bodies.global_shape(base)
        tools = [tool_shape(ref, bool(obj.Extend), shape) for ref in refs]
        pieces = split_shape(shape, tools)
        if len(pieces) < 2:
            raise SplitError(
                "The splitting tool does not cut the body in two. Pick a tool that crosses the "
                "body, or turn on Extend Splitting Tool."
            )
        meta = bodies.load_meta(obj, META)
        pieces = order(pieces, meta.get("centers"))
        refine = bool(obj.Refine) and bool(shape.Solids)  # surface pieces keep their faces
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
        others = _pieces_in(split.OtherPieces)
        if obj.Index - 1 >= len(others):
            return  # fewer pieces now: keeps its last shape (the dialog says so)
        # The pieces are in design coordinates; the new body takes its piece in its own (a
        # body in a moved component would otherwise be moved twice: components-2).
        body = piece_body(obj)
        piece = others[obj.Index - 1]
        obj.Shape = bodies.to_local(piece, body) if body is not None else piece.copy()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def feature_tools(obj):
    """[(object, sub)] of a Split Body step: its Tool, then MoreTools."""
    refs = []
    link = obj.Tool
    if link and link[0] is not None:
        refs.append((link[0], (list(link[1]) or [""])[0]))
    for entry in getattr(obj, "MoreTools", []) or []:
        other, subs = entry[0], entry[1]
        if other is None:
            continue
        if isinstance(subs, str):
            subs = [subs]
        refs.append((other, (list(subs) or [""])[0]))
    return refs


# -- reading and building -----------------------------------------------------------------------
def check(options):
    options = with_defaults(options)
    body, tools = options["body"], options["tools"]
    if body is None:
        raise NeedsPick("Select the body to split.")
    if not tools:
        raise NeedsPick(
            "Select the splitting tool: a plane, a face, another body or a sketch curve."
        )
    if not _has_faces(body):
        raise SplitError("%s has nothing to split." % body.Label)
    for obj, sub in tools:
        if bodies.is_body(obj) and obj is body:
            raise SplitError("A body cannot split itself. Pick a plane, a face or another body.")


def _has_faces(body):
    """A solid or a surface body (Fusion's Body to Split: "solid or open bodies")."""
    from . import surfmod

    return surfmod.body_has_faces(body)


def _pieces_in(compound):
    """The pieces kept in OtherPieces: solids, or the surface pieces of a split surface."""
    if compound is None or compound.isNull():
        return []
    if compound.Solids:
        return list(compound.Solids)
    return list(compound.childShapes())


def tool_link(tool):
    """What the feature links: a body is linked through its last step (its Tip)."""
    obj, sub = tool
    if bodies.is_body(obj):
        return (obj.Tip, "")
    return (obj, sub)


def preview_pieces(options, feature=None):
    """The pieces the split makes now, in order (design coordinates)."""
    options = with_defaults(options)
    body = options["body"]
    base = feature.BaseFeature if feature is not None else body.Tip
    shape = bodies.global_shape(base)
    tools = [tool_shape(tool_link(t), bool(options["extend"]), shape) for t in options["tools"]]
    pieces = split_shape(shape, tools)
    if len(pieces) < 2:
        raise SplitError(
            "The splitting tool does not cut the body in two. Pick a tool that crosses the "
            "body, or turn on Extend Splitting Tool."
        )
    meta = bodies.load_meta(feature, META) if feature is not None else {}
    return order(pieces, meta.get("centers"))


def tool_preview(options, feature=None):
    """The splitting tool(s) as the dialog draws them in red (design coordinates): with
    Extend Splitting Tool a face's whole plane or cylinder, cut down to the body to split
    plus a margin (split_core); without it the face itself; a body as the tool: its faces.
    The same planes and cylinders the split cuts with, so the picture shows where the cut
    goes. None while there is nothing to show; a tool that cannot be made is left out."""
    options = with_defaults(options)
    body = options["body"]
    if body is None or not options["tools"]:
        return None
    if feature is not None and bodies.alive(feature):
        base = feature.BaseFeature
    else:
        base = body.Tip
    if base is None:
        return None
    around = bodies.global_shape(base)
    if around.isNull():
        return None
    shapes = []
    for tool in options["tools"]:
        try:
            shape = tool_shape(tool_link(tool), bool(options["extend"]), around, fit=True)
        except Exception:
            continue
        if shape is not None and not shape.isNull():
            shapes.append(shape)
    if not shapes:
        return None
    return shapes[0] if len(shapes) == 1 else Part.makeCompound(shapes)


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
    links = [tool_link(t) for t in options["tools"]]
    link = links[0]
    current = feature.Tool
    if not current or current[0] is not link[0] or (list(current[1]) or [""])[0] != link[1]:
        feature.Tool = (link[0], [link[1]])
    more = [(obj, sub) for obj, sub in links[1:]]
    if feature_tools(feature)[1:] != more:
        feature.MoreTools = [(obj, [sub]) for obj, sub in more]
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
        try:  # in the new body's component: FreeCAD refuses a base outside the body's scope
            container = body.getParentGeoFeatureGroup()
            if container is not None and hasattr(container, "addObject"):
                container.addObject(piece)
        except Exception:
            pass
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
    source = bodies.body_of(feature)
    tools = []
    for obj, sub in feature_tools(feature):
        other = bodies.body_of(obj)
        if not sub and other is not None and other is not source and obj is other.Tip:
            tools.append((other, ""))  # a whole body was picked
        else:
            tools.append((obj, sub))
    return with_defaults({"body": source, "tools": tools, "extend": bool(feature.Extend)})


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
