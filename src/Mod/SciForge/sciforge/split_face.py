# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Split Face (Modify > Split Face): the document side, no Qt. split_face_ui.py is
the dialog; the golden-model builder calls build() too.

Options (dict, see DEFAULTS):
  faces       (feature, ["FaceN", ...]) the faces to split, on the body's current end
  tool        the splitting tool: (sketch, "") its curves, (sketch, "EdgeN") one curve,
              (plane, "") an origin or construction plane, (feature, "FaceN") a face of
              any body, (body, "") another body's faces
  extend      Extend Splitting Tool (Split with Surface only): a flat face is taken as its
              whole plane, a round face as its whole cylinder, a sketch line as its whole
              line (Fusion's checkbox; off by default)
  split_type  "surface" Split with Surface (default): where the tool's surface crosses the
              faces (a sketch's curves stand straight up from the sketch, both ways)
              "vector" Along Vector: the tool's curves projected onto the faces along
              ``direction``
              "closest" Closest Point: the tool's curves projected onto the faces at their
              nearest points
  direction   (object, sub) Along Vector's direction: a straight edge, a flat face or a
              plane (its normal), an axis

What is built: a "Split Face" step (SciForgeType "SplitFace", SplitFaceFeature) at the
history marker of the body: the body stays one solid, the faces are divided along the new
edges (OpenCASCADE's general fuse with the edges on the faces). The step keeps its faces
apart (no tidy-up of faces in one plane: it would merge them again).
"""

import FreeCAD as App

from . import bodies, curves

TYPE = "PartDesign::FeaturePython"
SCIFORGE_TYPE = "SplitFace"
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
LINE_TYPES = ("App::Line", "PartDesign::Line", "Part::DatumLine")
SPLIT_TYPES = ("surface", "vector", "closest")
SPLIT_TYPE_LABELS = {
    "surface": "Split with Surface",
    "vector": "Along Vector",
    "closest": "Closest Point",
}
DEFAULTS = {
    "faces": None,
    "tool": None,
    "extend": False,
    "split_type": "surface",
    "direction": None,
}
TOL = 1e-6


class SplitFaceError(ValueError):
    """The faces cannot be split as asked; the message says why and what to do."""


class NeedsPick(SplitFaceError):
    """A selection box still waits for its click."""


def with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update(options or {})
    return merged


def is_split_face(obj):
    return bodies.kind(obj) == SCIFORGE_TYPE


# -- geometry ----------------------------------------------------------------------------------
def _global(obj, element):
    """``element`` (a shape of ``obj``) in design coordinates."""
    out = element.copy()
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        parent = None
    if parent is not None:
        place = parent.getGlobalPlacement()
        if not place.isIdentity():
            out.transformShape(place.toMatrix(), True)
    return out


def _sketch_normal(sketch):
    return sketch.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))


def tool_curves(tool):
    """The tool's curves in design coordinates (Along Vector, Closest Point)."""
    import Part

    obj, sub = tool
    if obj.TypeId == "Sketcher::SketchObject":
        edges = [obj.Shape.getElement(sub)] if sub.startswith("Edge") else list(obj.Shape.Edges)
        edges = [_global(obj, e) for e in edges if not e.isNull()]
        return edges
    if sub.startswith("Edge"):
        return [_global(obj, obj.Shape.getElement(sub))]
    if sub.startswith("Face"):
        return [_global(obj, e) for e in obj.Shape.getElement(sub).Edges]
    if bodies.is_body(obj):
        shape = bodies.global_shape(obj)
        return list(shape.Edges)
    raise SplitFaceError(
        "Along Vector and Closest Point project curves: pick a sketch, a sketch curve, an "
        "edge or a face (its edges)."
    )
    return [Part.Shape()]


def tool_surface(tool, extend, around):
    """The tool as a surface in design coordinates (Split with Surface)."""
    import Part

    obj, sub = tool
    size = max(around.BoundBox.DiagonalLength, 1.0) * 4.0 + 50.0
    if obj.TypeId in PLANE_TYPES:
        place = obj.getGlobalPlacement()
        normal = place.Rotation.multVec(App.Vector(0, 0, 1))
        return _plane(place.Base, normal, around, size)
    if obj.TypeId == "Sketcher::SketchObject":
        normal = _sketch_normal(obj)
        edges = tool_curves(tool)
        swept = []
        for edge in edges:
            curve = edge.Curve
            if extend and curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
                start = edge.valueAt(edge.FirstParameter)
                end = edge.valueAt(edge.LastParameter)
                if (end - start).Length < TOL:
                    continue
                side = (end - start).normalize().cross(normal)
                swept.append(_plane(start, side, around, size))
                continue
            moved = edge.copy()
            moved.translate(normal * -size)
            swept.append(moved.extrude(normal * (2 * size)))
        if not swept:
            raise SplitFaceError("The sketch has no curves to split with.")
        return Part.makeCompound(swept)
    if bodies.is_body(obj) or (not sub and obj.isDerivedFrom("Part::Feature")):
        shape = bodies.global_shape(obj)
        if shape.isNull():
            raise SplitFaceError("%s has no faces to split with." % obj.Label)
        return Part.makeCompound(shape.Faces)
    if sub.startswith("Face"):
        face = _global(obj, obj.Shape.getElement(sub))
        if extend:
            kind = type(face.Surface).__name__
            if kind == "Plane":
                u0, u1, v0, v1 = face.ParameterRange
                normal = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
                return _plane(face.CenterOfMass, normal, around, size)
            if kind == "Cylinder":
                surf = face.Surface
                axis = App.Vector(surf.Axis).normalize()
                center = App.Vector(surf.Center)
                reach = size + (around.BoundBox.Center - center).Length
                return Part.makeCylinder(surf.Radius, 2 * reach, center - axis * reach, axis).Faces[
                    0
                ]
        return face
    raise SplitFaceError("Split with a sketch, a plane, a face or a body.")


def _plane(point, normal, around, size):
    import Part

    plane = Part.Plane(App.Vector(point), App.Vector(normal))
    u, v = plane.parameter(around.BoundBox.Center)
    return plane.toShape(u - size, u + size, v - size, v + size)


def direction_of(ref):
    """Along Vector's direction (design coordinates) from a straight edge, a flat face, a
    plane or an axis; None when ``ref`` gives none."""
    if ref is None:
        return None
    obj, sub = ref
    if obj.TypeId in PLANE_TYPES and not sub:
        return obj.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
    if obj.TypeId in LINE_TYPES and not sub:
        place = obj.getGlobalPlacement()
        axis = App.Vector(1, 0, 0) if obj.TypeId == "App::Line" else App.Vector(0, 0, 1)
        return place.Rotation.multVec(axis)
    try:
        element = _global(obj, obj.Shape.getElement(sub))
    except Exception:
        return None
    if sub.startswith("Edge"):
        curve = element.Curve
        if curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
            a = element.valueAt(element.FirstParameter)
            b = element.valueAt(element.LastParameter)
            return (b - a).normalize() if (b - a).Length > TOL else None
        if hasattr(curve, "Axis"):
            return App.Vector(curve.Axis).normalize()
        return None
    if sub.startswith("Face"):
        surface = element.Surface
        if type(surface).__name__ == "Plane":
            u0, u1, v0, v1 = element.ParameterRange
            return element.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
        if hasattr(surface, "Axis"):
            return App.Vector(surface.Axis).normalize()
    return None


def split_edges(faces, options, around):
    """The new edges on ``faces`` (design coordinates) that split them."""
    import Part

    kind = options["split_type"]
    tool = options["tool"]
    found = []
    if kind == "surface":
        surface = tool_surface(tool, bool(options["extend"]), around)
        for face in faces:
            try:
                section = face.section(surface)
            except Exception as exc:
                raise SplitFaceError("The splitting tool cannot be crossed with a face: %s" % exc)
            found += list(section.Edges)
    else:
        curves_ = tool_curves(tool)
        if not curves_:
            raise SplitFaceError("The splitting tool has no curves to project.")
        wire = Part.makeCompound(curves_)
        for face in faces:
            try:
                if kind == "vector":
                    direction = direction_of(options["direction"])
                    if direction is None:
                        raise NeedsPick(
                            "Pick the direction: a straight edge, a flat face, a plane or an "
                            "axis."
                        )
                    projected = face.makeParallelProjection(wire, direction)
                else:
                    projected = face.project(curves_)
            except SplitFaceError:
                raise
            except Exception as exc:
                raise SplitFaceError("The tool cannot be projected onto a face: %s" % exc)
            found += list(projected.Edges)
    return [e for e in found if e.Length > 1e-6]


def split(base, faces, options):
    """New solid: ``base`` (design coordinates) with ``faces`` divided by the tool."""
    import Part

    edges = split_edges(faces, options, base)
    if not edges:
        raise SplitFaceError(
            "The splitting tool does not cross the faces. Pick a tool that crosses them, "
            "turn on Extend Splitting Tool, or try another Split Type."
        )
    try:
        result, _map = base.generalFuse([Part.makeCompound(edges)])
    except Exception as exc:
        raise SplitFaceError("The faces cannot be split there: %s" % exc)
    solids = [s for s in result.Solids if s.Volume > TOL]
    if len(solids) != len(base.Solids) or not solids:
        raise SplitFaceError("Splitting the faces broke the solid. Try another splitting tool.")
    out = solids[0] if len(solids) == 1 else Part.makeCompound(solids)
    if not out.isValid():
        raise SplitFaceError("Splitting the faces gave an invalid solid. Try another tool.")
    if len(out.Faces) <= len(base.Faces):
        raise SplitFaceError(
            "The splitting tool only touches the faces' edges: nothing to split. Pick a tool "
            "that crosses them."
        )
    return out


# -- the step ----------------------------------------------------------------------------------
class SplitFaceFeature:
    """The Split Face step. Saved as "sciforge.split_face.SplitFaceFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Split Face", doc)
                return True
            return False

        add("App::PropertyLinkSub", "Faces", "The faces divided")
        add("App::PropertyLinkSubGlobal", "Tool", "The splitting tool")
        if add("App::PropertyBool", "Extend", "Extend Splitting Tool"):
            obj.Extend = False
        if add("App::PropertyEnumeration", "SplitType", "How the tool divides the faces"):
            obj.SplitType = list(SPLIT_TYPES)
            obj.SplitType = "surface"
        add("App::PropertyLinkSubGlobal", "Direction", "Along Vector's direction")
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
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise SplitFaceError("There is no solid before this step.")
        curves.refind(obj, ("Faces",))
        link = obj.Faces
        if not link or not link[1]:
            raise SplitFaceError("Select the faces to split.")
        tool = obj.Tool
        if not tool or tool[0] is None:
            raise SplitFaceError(
                "Its splitting tool is gone (deleted?). Edit the Split Face and pick a tool."
            )
        source, names = link[0], list(link[1])
        body = bodies.body_of(obj)
        shape = bodies.global_shape(base)
        faces = []
        for name in names:
            try:
                faces.append(_global(source, source.Shape.getElement(name)))
            except Exception:
                raise SplitFaceError(
                    "The face %s no longer exists (an earlier step changed the model). Edit "
                    "the Split Face and pick the faces again." % name
                )
        direction = obj.Direction
        options = with_defaults(
            {
                "tool": (tool[0], (list(tool[1]) or [""])[0]),
                "extend": bool(obj.Extend),
                "split_type": obj.SplitType,
                "direction": (
                    (direction[0], (list(direction[1]) or [""])[0])
                    if direction and direction[0] is not None
                    else None
                ),
            }
        )
        result = split(shape, faces, options)
        obj.Shape = bodies.to_local(result, body)
        curves.remember(obj, ("Faces",))

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def check(options):
    if not options["faces"] or not options["faces"][1]:
        raise NeedsPick("Select the faces to split.")
    if options["tool"] is None:
        raise NeedsPick("Select the splitting tool: a sketch, a plane, a face or a body.")
    if options["split_type"] == "vector" and options["direction"] is None:
        raise NeedsPick("Select the direction: a straight edge, a flat face, a plane or an axis.")


def build(options, feature=None, name="SplitFace"):
    """Create the Split Face step (or update ``feature``). Returns it."""
    options = with_defaults(options)
    check(options)
    source, names = options["faces"]
    body = bodies.body_of(source)
    if body is None:
        raise SplitFaceError("The faces must be faces of a body.")
    if feature is not None and bodies.alive(feature) and bodies.body_of(feature) is not body:
        bodies.remove_step(feature)
        feature = None
    if feature is None or not bodies.alive(feature):
        feature = bodies.insert_after_tip(body, TYPE, name)
        SplitFaceFeature(feature)
        _attach_view_provider(feature)
    feature.Faces = (source, list(names))
    obj, sub = options["tool"]
    current = feature.Tool
    if not current or current[0] is not obj or (list(current[1]) or [""])[0] != sub:
        feature.Tool = (obj, [sub])
    if bool(feature.Extend) != bool(options["extend"]):
        feature.Extend = bool(options["extend"])
    if feature.SplitType != options["split_type"]:
        feature.SplitType = options["split_type"]
    direction = options["direction"]
    current = feature.Direction
    if direction is None:
        if current:
            feature.Direction = None
    elif (
        not current
        or current[0] is not direction[0]
        or (list(current[1]) or [""])[0] != direction[1]
    ):
        feature.Direction = (direction[0], [direction[1]])
    return feature


def read(feature):
    link = feature.Faces
    tool = feature.Tool
    direction = feature.Direction
    return with_defaults(
        {
            "faces": (link[0], list(link[1])) if link else None,
            "tool": (tool[0], (list(tool[1]) or [""])[0]) if tool else None,
            "extend": bool(feature.Extend),
            "split_type": feature.SplitType,
            "direction": (direction[0], (list(direction[1]) or [""])[0]) if direction else None,
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
