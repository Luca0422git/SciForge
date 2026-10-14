# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Move/Copy (M) for bodies: the document side, no Qt. The dialog (move_ui.py) and
the golden-model builder both call build().

Options (dict, see DEFAULTS):
  bodies       the bodies to move (Move Object: Bodies)
  move_type    free | translate | rotate | point_to_point | point_to_position
  dx, dy, dz   distances along the design's X, Y, Z (free, translate)
  rx, ry, rz   angles about X, Y, Z through the pivot, in degrees (free); turned about X
               first, then Y, then Z
  pivot        [x, y, z] the point free rotations turn about (the middle of the bodies)
  axis_point, axis_dir   [x, y, z] the rotate axis (rotate); axis_label names it
  angle        degrees about the axis, right-handed (rotate)
  from_point, to_point   [x, y, z] (point_to_point); from_label / to_label name them
  px, py, pz   where from_point goes (point_to_position), design coordinates
  copy         Create Copy: new bodies are moved, the originals stay

What is built (one step per body, all sharing a MoveId, so the dialog edits them together):
  move   a "Move" step (SciForgeType "MoveCopy", MoveFeature below) at the end of each body's
         history: it takes the body's solid and moves it. Later steps build on the moved
         solid; sketches made earlier stay where they are, as in Fusion.
  copy   a "Move" step outside the bodies (CopyFeature) that copies a body's solid as it is
         at that point of the timeline (later steps of the original do not change the copy;
         edits to earlier ones do) and moves the copy; a new body starts from it.
The movement itself is stored as numbers (a placement), like Fusion's Move feature: it does
not follow the points or axis picked when it was made.
"""

import math

import FreeCAD as App

from . import bodies

TYPE = "PartDesign::FeaturePython"
COPY_TYPE = "Part::FeaturePython"
SCIFORGE_TYPE = "MoveCopy"
META = "SciForgeMove"
MOVE_TYPES = ("free", "translate", "rotate", "point_to_point", "point_to_position")

DEFAULTS = {
    "bodies": [],
    "move_type": "free",
    "dx": 0.0,
    "dy": 0.0,
    "dz": 0.0,
    "rx": 0.0,
    "ry": 0.0,
    "rz": 0.0,
    "pivot": None,
    "axis_point": None,
    "axis_dir": None,
    "axis_label": "",
    "angle": 0.0,
    "from_point": None,
    "to_point": None,
    "from_label": "",
    "to_label": "",
    "px": 0.0,
    "py": 0.0,
    "pz": 0.0,
    "copy": False,
}
NUMBERS = ("dx", "dy", "dz", "rx", "ry", "rz", "angle", "px", "py", "pz")
POINTS = ("pivot", "axis_point", "axis_dir", "from_point", "to_point")


class MoveError(ValueError):
    """The move cannot be made as asked; the message says why and what to do."""


class NeedsPick(MoveError):
    """A selection box still waits for its click."""


def with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update(options or {})
    merged["bodies"] = list(merged.get("bodies") or [])
    return merged


def is_move(obj):
    return bodies.kind(obj) == SCIFORGE_TYPE


def is_copy(obj):
    return is_move(obj) and isinstance(getattr(obj, "Proxy", None), CopyFeature)


def _vec(value):
    if value is None:
        return None
    return App.Vector(*value) if not isinstance(value, App.Vector) else App.Vector(value)


# -- the movement ---------------------------------------------------------------------------------
def turn(rx, ry, rz):
    """Turn about X, then Y, then Z (degrees)."""
    rot_x = App.Rotation(App.Vector(1, 0, 0), rx)
    rot_y = App.Rotation(App.Vector(0, 1, 0), ry)
    rot_z = App.Rotation(App.Vector(0, 0, 1), rz)
    return rot_z.multiply(rot_y.multiply(rot_x))


def transform(options):
    """The movement as a placement in design coordinates (applied to the whole body)."""
    options = with_defaults(options)
    kind = options["move_type"]
    if kind == "translate":
        return App.Placement(
            App.Vector(options["dx"], options["dy"], options["dz"]), App.Rotation()
        )
    if kind == "free":
        pivot = _vec(options["pivot"]) or App.Vector()
        rot = turn(options["rx"], options["ry"], options["rz"])
        place = App.Placement(App.Vector(), rot, pivot)  # turn about the pivot
        shift = App.Placement(
            App.Vector(options["dx"], options["dy"], options["dz"]), App.Rotation()
        )
        return shift.multiply(place)
    if kind == "rotate":
        point, direction = _vec(options["axis_point"]), _vec(options["axis_dir"])
        if point is None or direction is None:
            raise NeedsPick("Select the axis to rotate about: an origin axis or a straight edge.")
        if direction.Length < 1e-12:
            raise MoveError("That axis has no direction.")
        rot = App.Rotation(App.Vector(direction).normalize(), options["angle"])
        return App.Placement(App.Vector(), rot, point)
    if kind == "point_to_point":
        start, end = _vec(options["from_point"]), _vec(options["to_point"])
        if start is None:
            raise NeedsPick("Select the point to move from (a corner, a circle's centre...).")
        if end is None:
            raise NeedsPick("Select the point to move to.")
        return App.Placement(end - start, App.Rotation())
    if kind == "point_to_position":
        start = _vec(options["from_point"])
        if start is None:
            raise NeedsPick("Select the point to move (a corner, a circle's centre...).")
        end = App.Vector(options["px"], options["py"], options["pz"])
        return App.Placement(end - start, App.Rotation())
    raise MoveError("Unknown move type %r." % kind)


def is_identity(place, tol=1e-9):
    if place.Base.Length > tol:
        return False
    return abs(place.Rotation.Angle) < tol


def _moved(shape, place):
    out = bodies.baked(shape)
    if not is_identity(place):
        out.transformShape(place.toMatrix(), True)
    return out


# -- the features -----------------------------------------------------------------------------------
def _properties(obj, group):
    def add(kind, name, doc):
        if name not in obj.PropertiesList:
            obj.addProperty(kind, name, group, doc)
            return True
        return False

    add("App::PropertyPlacement", "Movement", "The movement, in design coordinates")
    add("App::PropertyString", "MoveId", "Steps made by one Move/Copy share this")
    bodies.mark(obj, SCIFORGE_TYPE)


class MoveFeature:
    """The Move step inside a body. Saved as "sciforge.move.MoveFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        _properties(obj, "Move")

    def onDocumentRestored(self, obj):
        _properties(obj, "Move")

    def execute(self, obj):
        try:
            self._build(obj)
        except Exception:
            bodies.pass_through(obj)  # shown as the body was before it, the step red
            raise

    def _build(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise MoveError("There is no solid before this step to move.")
        body = bodies.body_of(obj)
        moved = _moved(bodies.global_shape(base), obj.Movement)
        obj.Shape = bodies.to_local(moved, body)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class CopyFeature:
    """The Move step of Create Copy: a moved copy of a body, the first step of a new body.
    Saved as "sciforge.move.CopyFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        _properties(obj, "Move")
        if "Source" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkGlobal", "Source", "Move", "The step copied")

    def onDocumentRestored(self, obj):
        _properties(obj, "Move")

    def execute(self, obj):
        source = obj.Source
        if source is None:
            return  # the original was deleted: the copy keeps its shape, as in Fusion
        if source.Shape.isNull() or not source.Shape.Solids:
            raise MoveError("The body it copies has no solid here.")
        shape = _moved(bodies.global_shape(source), obj.Movement)
        # The new body takes this shape in its own coordinates: a body in a moved
        # component would otherwise be moved twice (components-2).
        body = copy_body(obj)
        obj.Shape = bodies.to_local(shape, body) if body is not None else shape

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


# -- reading and building ------------------------------------------------------------------------------
def steps_of(move_id, doc):
    """Every step of one Move/Copy (one per body)."""
    if not move_id:
        return []
    found = [o for o in doc.Objects if is_move(o) and getattr(o, "MoveId", "") == move_id]
    return sorted(found, key=lambda o: o.ID)


def moved_body(step):
    """The body a step moves (for a copy: the body it copied)."""
    if is_copy(step):
        return bodies.body_of(step.Source) if step.Source is not None else None
    return bodies.body_of(step)


def copy_body(step):
    """The new body a copy step starts."""
    for obj in step.InList:
        if bodies.is_body(obj) and obj.BaseFeature is step:
            return obj
    return None


def read(step):
    """Dialog options of a Move/Copy (all its steps), and the steps."""
    steps = steps_of(getattr(step, "MoveId", ""), step.Document) or [step]
    meta = bodies.load_meta(step, META)
    options = with_defaults({})
    for key in ("move_type", "axis_label", "from_label", "to_label") + NUMBERS:
        if key in meta:
            options[key] = meta[key]
    for key in POINTS:
        if meta.get(key) is not None:
            options[key] = list(meta[key])
    options["copy"] = is_copy(step)
    found = []
    for s in steps:
        body = moved_body(s)
        if body is not None and body not in found:
            found.append(body)
    options["bodies"] = found
    return options, steps


def check(options):
    if not options["bodies"]:
        raise NeedsPick("Select the bodies to move.")
    if options["move_type"] not in MOVE_TYPES:
        raise MoveError("Pick a move type.")
    for body in options["bodies"]:
        if not bodies.has_solid(body):
            raise MoveError("%s has no solid to move." % body.Label)
    transform(options)  # raises NeedsPick while an axis or a point is still missing


def _meta(options):
    meta = {"v": 1}
    for key in ("move_type", "axis_label", "from_label", "to_label"):
        meta[key] = options[key]
    for key in NUMBERS:
        meta[key] = float(options[key])
    for key in POINTS:
        value = options[key]
        meta[key] = [float(c) for c in value] if value is not None else None
    return meta


def new_id():
    import uuid

    return uuid.uuid4().hex[:12]


def build(options, steps=None, move_id=None, name="Move"):
    """Create the Move/Copy steps, or update `steps` (one per body). Returns the steps.
    Bodies added to the selection get a step, dropped ones lose theirs; switching Create Copy
    rebuilds them as the other kind."""
    options = with_defaults(options)
    check(options)
    place = transform(options)
    steps = [s for s in (steps or []) if bodies.alive(s)]
    if steps:
        move_id = move_id or getattr(steps[0], "MoveId", "") or new_id()
    move_id = move_id or new_id()
    wanted = list(options["bodies"])
    keep = []
    for step in steps:
        body = moved_body(step)
        if is_copy(step) != bool(options["copy"]) or body not in wanted:
            remove(step)
        else:
            keep.append(step)
    have = {moved_body(s).Name: s for s in keep if moved_body(s) is not None}
    result = []
    meta = _meta(options)
    for body in wanted:
        step = have.get(body.Name)
        if step is None:
            step = _copy(body, name) if options["copy"] else _move(body, name)
        if not step.Movement.isSame(place, 1e-12):
            step.Movement = place
        if step.MoveId != move_id:
            step.MoveId = move_id
        bodies.save_meta(step, META, meta)
        result.append(step)
    return result


def _move(body, name):
    obj = bodies.insert_after_tip(body, TYPE, name)
    MoveFeature(obj)
    _attach_view_provider(obj)
    return obj


def _copy(body, name):
    doc = body.Document
    obj = doc.addObject(COPY_TYPE, name)
    CopyFeature(obj)
    obj.Source = body.Tip
    new = bodies.new_body(doc, like=body)
    try:  # in the new body's component: FreeCAD refuses a base outside the body's scope
        container = new.getParentGeoFeatureGroup()
        if container is not None and hasattr(container, "addObject"):
            container.addObject(obj)
    except Exception:
        pass
    new.BaseFeature = obj
    bodies.save_meta(new, META, {"copy_of": body.Name})
    for inner in new.Group:
        if inner.TypeId == "PartDesign::FeatureBase":
            bodies.hide_from_timeline(inner)
    try:
        new.ShapeMaterial = body.ShapeMaterial
    except Exception:
        pass
    try:
        from . import appearance

        appearance.copy_body_appearance(body, new)
    except Exception:
        pass
    if App.GuiUp:
        try:
            obj.ViewObject.Visibility = False
        except Exception:
            pass
    _attach_view_provider(obj)
    return obj


def remove(step):
    """Take a Move/Copy step out again (with the new body of a copy)."""
    if not bodies.alive(step):
        return
    if is_copy(step):
        new = copy_body(step)
        if new is not None:
            bodies.remove_body(new)
        try:
            step.Document.removeObject(step.Name)
        except Exception:
            pass
        return
    bodies.remove_step(step)


def orphan_copies(doc):
    """New bodies whose copy step was deleted (their base link is gone)."""
    found = []
    for body in bodies.list_bodies(doc):
        meta = bodies.load_meta(body, META)
        if meta.get("copy_of") and body.BaseFeature is None:
            found.append(body)
    return found


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .bodies_gui import StepViewProvider

        StepViewProvider(obj.ViewObject)
    except Exception:
        pass


def point_of(obj, sub, near=None):
    """The point Fusion snaps to for a pick: a corner, a circle's centre, a straight edge's
    middle, a flat face's centre, an origin point. Design coordinates, or None."""
    if obj is None:
        return None
    if obj.TypeId in ("App::Point", "PartDesign::Point", "Part::DatumPoint") and not sub:
        return obj.getGlobalPlacement().Base
    try:
        element = obj.Shape.getElement(sub) if sub else None
    except Exception:
        return None
    if element is None:
        return None
    if sub.startswith("Vertex"):
        try:
            circle = seam_circle(obj.Shape, element)
        except Exception:
            circle = None
        if circle is not None:
            element, sub = circle, "Edge"  # the round edge it starts: its centre
    element = element.copy()
    try:
        parent = obj.getParentGeoFeatureGroup()
        if parent is not None:
            element.transformShape(parent.getGlobalPlacement().toMatrix(), True)
    except Exception:
        pass
    if sub.startswith("Vertex"):
        return App.Vector(element.Point)
    if sub.startswith("Edge"):
        curve = element.Curve
        if hasattr(curve, "Center") and hasattr(curve, "Radius"):
            return App.Vector(curve.Center)
        return element.valueAt((element.FirstParameter + element.LastParameter) / 2.0)
    if sub.startswith("Face"):
        surface = element.Surface
        if hasattr(surface, "Center") and surface.TypeId != "Part::GeomPlane":
            return App.Vector(surface.Center)
        return element.CenterOfMass
    return None


def seam_circle(shape, vertex):
    """The full circle or ellipse that OpenCASCADE starts at `vertex`, when nothing but
    seam lines also meet there: Fusion has no such point (a round edge has no corner), so a
    click on it means the round edge. None for a real corner."""
    found = None
    for edge in shape.Edges:
        if not any(v.isSame(vertex) for v in edge.Vertexes):
            continue
        if edge.isClosed():
            if found is None and hasattr(edge.Curve, "Center"):
                found = edge
            continue
        faces = [f for f in shape.Faces if any(e.isSame(edge) for e in f.Edges)]
        if not any(edge.isSeam(f) for f in faces):
            return None  # a real edge ends here: a real corner
    return found


def axis_of(obj, sub):
    """(point, direction) of a rotate axis: an origin axis, a straight or round edge (its
    axis), a round face (its axis). Design coordinates, or None."""
    if obj is None:
        return None
    if obj.TypeId == "App::Line" and not sub:
        place = obj.getGlobalPlacement()  # an origin axis runs along its own X
        return place.Base, place.Rotation.multVec(App.Vector(1, 0, 0))
    if obj.TypeId in ("PartDesign::Line", "Part::DatumLine") and not sub:
        edges = obj.Shape.Edges if not obj.Shape.isNull() else []
        if edges:
            edge = edges[0].copy()
            try:
                parent = obj.getParentGeoFeatureGroup()
                if parent is not None:
                    edge.transformShape(parent.getGlobalPlacement().toMatrix(), True)
            except Exception:
                pass
            start = edge.valueAt(edge.FirstParameter)
            return start, edge.tangentAt(edge.FirstParameter).normalize()
        place = obj.getGlobalPlacement()
        return place.Base, place.Rotation.multVec(App.Vector(0, 0, 1))
    try:
        element = obj.Shape.getElement(sub).copy()
    except Exception:
        return None
    try:
        parent = obj.getParentGeoFeatureGroup()
        if parent is not None:
            element.transformShape(parent.getGlobalPlacement().toMatrix(), True)
    except Exception:
        pass
    if sub.startswith("Edge"):
        curve = element.Curve
        if curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
            start = element.valueAt(element.FirstParameter)
            end = element.valueAt(element.LastParameter)
            if (end - start).Length < 1e-9:
                return None
            return start, (end - start).normalize()
        if hasattr(curve, "Axis") and hasattr(curve, "Center"):
            return App.Vector(curve.Center), App.Vector(curve.Axis).normalize()
        return None
    if sub.startswith("Face"):
        surface = element.Surface
        if hasattr(surface, "Axis") and hasattr(surface, "Center"):
            return App.Vector(surface.Center), App.Vector(surface.Axis).normalize()
    return None


def angle_between(a, b):
    try:
        return math.degrees(a.getAngle(b))
    except Exception:
        return 0.0
