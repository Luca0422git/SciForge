# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Align (Modify > Align): the document side, no Qt. align_ui.py is the dialog;
the maths is align_core.py.

Options (dict, see DEFAULTS):
  objects     "bodies" | "components": what moves (Fusion's Objects)
  from_pick   (object, sub, point): the geometry on what moves (a corner, an edge, a
              face, a plane, an axis); its body (or component) is what moves
  to_pick     (object, sub, point): the geometry it goes to
  flip        Fusion's Flip: the result turned 180 degrees
  turns       Fusion's Angle: quarter turns about the To geometry

What is built (recorded like Move/Copy, the movement stored as numbers: Fusion's Align
makes no relationship, a later change does not keep things aligned):
  bodies      an "Align" step (SciForgeType "Align", AlignFeature) at the history marker of
              the body: it moves the body's solid; later steps build on the moved solid
  components  an "Align" step outside the bodies (AlignComponentStep) that set the
              component's placement when it was made (and when it is edited); the timeline
              lists it, Undo takes it back
"""

import json

import FreeCAD as App

from . import align_core as core
from . import bodies

TYPE = "PartDesign::FeaturePython"
COMPONENT_TYPE = "App::FeaturePython"
SCIFORGE_TYPE = "Align"
META = "SciForgeAlign"
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
LINE_TYPES = ("App::Line", "PartDesign::Line", "Part::DatumLine")
POINT_TYPES = ("App::Point", "PartDesign::Point", "Part::DatumPoint")
DEFAULTS = {"objects": "bodies", "from_pick": None, "to_pick": None, "flip": False, "turns": 0}


class AlignError(ValueError):
    """Align cannot be made as asked; the message says why and what to do."""


class NeedsPick(AlignError):
    """A selection box still waits for its click."""


def with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update(options or {})
    return merged


def is_align(obj):
    return bodies.kind(obj) == SCIFORGE_TYPE


# -- what a pick means -------------------------------------------------------------------------
def _global(obj, element):
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


def _flat_face_normal_at(obj, edge):
    """The outward normal of a flat face of ``obj`` bounded by ``edge``, or None."""
    try:
        shape = obj.Shape
        for face in shape.Faces:
            if type(face.Surface).__name__ != "Plane":
                continue
            if any(e.isSame(edge) for e in face.Edges):
                u0, u1, v0, v1 = face.ParameterRange
                return face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    except Exception:
        pass
    return None


def frame_of(obj, sub, point=None):
    """The frame (align_core) a pick means, in design coordinates, or None."""
    if obj is None:
        return None
    if obj.TypeId in PLANE_TYPES and not sub:
        place = obj.getGlobalPlacement()
        return core.frame(place.Base, place.Rotation.multVec(App.Vector(0, 0, 1)), True)
    if obj.TypeId in LINE_TYPES and not sub:
        place = obj.getGlobalPlacement()
        axis = App.Vector(1, 0, 0) if obj.TypeId == "App::Line" else App.Vector(0, 0, 1)
        return core.frame(place.Base, place.Rotation.multVec(axis))
    if obj.TypeId in POINT_TYPES and not sub:
        return core.frame(obj.getGlobalPlacement().Base)
    if not sub:
        return None
    try:
        element = obj.Shape.getElement(sub)
    except Exception:
        return None
    world = _global(obj, element)
    if sub.startswith("Vertex"):
        return core.frame(world.Point)
    if sub.startswith("Edge"):
        curve = world.Curve
        if curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
            ends = [world.valueAt(world.FirstParameter), world.valueAt(world.LastParameter)]
            middle = world.valueAt((world.FirstParameter + world.LastParameter) / 2.0)
            snap = middle
            if point is not None:
                snap = min(ends + [middle], key=lambda p: (p - App.Vector(point)).Length)
            direction = ends[1] - ends[0]
            if direction.Length < 1e-12:
                return core.frame(snap)
            return core.frame(snap, direction)
        if hasattr(curve, "Center") and hasattr(curve, "Axis"):
            normal = _flat_face_normal_at(obj, element)
            if normal is not None:
                normal = _global_direction(obj, normal)
                return core.frame(curve.Center, normal, True)
            return core.frame(curve.Center, curve.Axis)
        return core.frame(world.valueAt((world.FirstParameter + world.LastParameter) / 2.0))
    if sub.startswith("Face"):
        surface = world.Surface
        kind = type(surface).__name__
        if kind == "Plane":
            u0, u1, v0, v1 = world.ParameterRange
            normal = world.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            return core.frame(world.CenterOfMass, normal, True)
        if kind in ("Cylinder", "Cone"):
            axis = App.Vector(surface.Axis).normalize()
            center = App.Vector(surface.Center if kind == "Cylinder" else surface.Apex)
            com = world.CenterOfMass
            on_axis = center + axis * axis.dot(com - center)
            return core.frame(on_axis, axis)
        if kind == "Sphere":
            return core.frame(surface.Center)
        return core.frame(world.CenterOfMass)
    return None


def snap_points(obj, sub):
    """The points Align offers on a face or an edge (Fusion: face centres, edge midpoints,
    corners, circle centres), in design coordinates: [{"kind", "point" (App.Vector)}], the
    one a plain click takes first (a face's centre, a round edge's centre, an edge's
    middle). Same points as a joint's snaps (joints._shape_snaps)."""
    if obj is None or not sub or not sub.startswith(("Face", "Edge")):
        return []
    from . import joints

    try:
        shape = _global(obj, obj.Shape)
        snaps = joints._shape_snaps(shape, sub)
    except Exception:
        return []
    if sub.startswith("Edge"):  # the middle first, as frame_of takes it (a circle: its centre)
        snaps.sort(key=lambda s: {"circle": 0, "midpoint": 1}.get(s["kind"], 2))
    found = []
    for snap in snaps:
        point = App.Vector(snap["point"])
        if all((point - f["point"]).Length > 1e-7 for f in found):
            found.append({"kind": snap["kind"], "point": point})
    return found


def at_point(frame, point):
    """`frame` (align_core) moved to `point` (a snap the person chose), its direction kept:
    a face's normal still says which way the part faces."""
    if frame is None or point is None:
        return frame
    return core.frame(App.Vector(point), frame.get("axis"), frame.get("oriented"))


def _global_direction(obj, vector):
    try:
        parent = obj.getParentGeoFeatureGroup()
        if parent is not None:
            return parent.getGlobalPlacement().Rotation.multVec(vector)
    except Exception:
        pass
    return vector


def describe_pick(pick):
    if not pick:
        return ""
    obj, sub = pick[0], pick[1]
    if obj is None:
        return ""
    if not sub:
        return obj.Label
    body = bodies.body_of(obj)
    where = body.Label if body is not None else obj.Label
    return "%s of %s" % (sub.rstrip("0123456789"), where)


def moving(pick, objects):
    """What the From pick moves: its body, or (Objects: Components) its component."""
    if not pick:
        return None
    obj = pick[0]
    if objects == "components":
        from . import components

        return components.component_of(obj)
    return bodies.body_of(obj)


def placement(options):
    """The movement as a placement in design coordinates."""
    options = with_defaults(options)
    src = options.get("from_frame") or frame_of(*_pick3(options["from_pick"]))
    dst = options.get("to_frame") or frame_of(*_pick3(options["to_pick"]))
    if src is None:
        raise NeedsPick(
            "Select the From geometry: a corner, an edge, a face or a plane of what moves."
        )
    if dst is None:
        raise NeedsPick("Select the To geometry it goes to.")
    rotation, translation = core.movement(src, dst, bool(options["flip"]), int(options["turns"]))
    return App.Placement(App.Vector(*translation), App.Rotation(*rotation))


def _pick3(pick):
    if not pick:
        return (None, "", None)
    obj, sub = pick[0], pick[1]
    point = pick[2] if len(pick) > 2 else None
    return (obj, sub, point)


# -- the steps ---------------------------------------------------------------------------------
def _properties(obj):
    def add(kind, name, doc):
        if name not in obj.PropertiesList:
            obj.addProperty(kind, name, "Align", doc)

    add("App::PropertyPlacement", "Movement", "The movement, in design coordinates")
    add("App::PropertyString", "AlignId", "Steps made by one Align share this")
    bodies.mark(obj, SCIFORGE_TYPE)


class AlignFeature:
    """The Align step inside a body. Saved as "sciforge.align.AlignFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        _properties(obj)

    def onDocumentRestored(self, obj):
        _properties(obj)

    def execute(self, obj):
        try:
            base = obj.BaseFeature
            if base is None or base.Shape.isNull() or not base.Shape.Solids:
                raise AlignError("There is no solid before this step to move.")
            body = bodies.body_of(obj)
            moved = bodies.baked(bodies.global_shape(base))
            if not _identity(obj.Movement):
                moved.transformShape(obj.Movement.toMatrix(), True)
            obj.Shape = bodies.to_local(moved, body)
        except Exception:
            bodies.pass_through(obj)
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class AlignComponentStep:
    """An Align of a component: a step outside the bodies that set the component's
    placement. Saved as "sciforge.align.AlignComponentStep"."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure(obj)

    @staticmethod
    def ensure(obj):
        _properties(obj)
        if "Component" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Component", "Align", "The component moved")
        if "Before" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyPlacement", "Before", "Align", "Its placement before the Align"
            )

    def onDocumentRestored(self, obj):
        self.ensure(obj)

    def execute(self, obj):
        return None

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _identity(place, tol=1e-12):
    return place.Base.Length < tol and abs(place.Rotation.Angle) < tol


def is_component_step(obj):
    return is_align(obj) and isinstance(getattr(obj, "Proxy", None), AlignComponentStep)


def steps_of(align_id, doc):
    if not align_id:
        return []
    found = [o for o in doc.Objects if is_align(o) and getattr(o, "AlignId", "") == align_id]
    return sorted(found, key=lambda o: o.ID)


def _meta(options):
    def pick(p):
        if not p or p[0] is None:
            return None
        return {"object": p[0].Name, "sub": p[1], "label": describe_pick(p)}

    return {
        "v": 1,
        "objects": options["objects"],
        "from": pick(options["from_pick"]),
        "to": pick(options["to_pick"]),
        "from_frame": options.get("from_frame") or frame_of(*_pick3(options["from_pick"])),
        "to_frame": options.get("to_frame") or frame_of(*_pick3(options["to_pick"])),
        "flip": bool(options["flip"]),
        "turns": int(options["turns"]) % 4,
    }


def new_id():
    import uuid

    return uuid.uuid4().hex[:12]


def check(options):
    if options["objects"] not in ("bodies", "components"):
        raise AlignError("Pick Bodies or Components.")
    if not options["from_pick"] and not options.get("from_frame"):
        raise NeedsPick(
            "Select the From geometry: a corner, an edge, a face or a plane of what moves."
        )
    if not options["to_pick"] and not options.get("to_frame"):
        raise NeedsPick("Select the To geometry it goes to.")


def build(options, steps=None, align_id=None, target=None):
    """Create the Align step (or update ``steps``). ``target``: what moves (a body or a
    component; default: the From pick's). Returns the steps."""
    options = with_defaults(options)
    check(options)
    thing = target if target is not None else moving(options["from_pick"], options["objects"])
    if thing is None:
        raise AlignError(
            "The From geometry must be on a body (or, with Components, inside a component)."
        )
    to_thing = moving(options["to_pick"], options["objects"]) if options["to_pick"] else None
    if to_thing is not None and to_thing is thing:
        raise AlignError("The To geometry is on what moves. Pick it on another body or a plane.")
    place = placement(options)
    meta = _meta(options)
    steps = [s for s in (steps or []) if bodies.alive(s)]
    align_id = align_id or (getattr(steps[0], "AlignId", "") if steps else "") or new_id()
    from . import components

    if components.is_component(thing):
        step = steps[0] if steps and is_component_step(steps[0]) else None
        for other in steps:
            if other is not step:
                remove(other)
        if step is None:
            step = thing.Document.addObject(COMPONENT_TYPE, "Align")
            AlignComponentStep(step)
            step.Component = thing
            step.Before = thing.Placement
        step.Movement = place
        step.AlignId = align_id
        bodies.save_meta(step, META, meta)
        new = place.multiply(step.Before)
        if not thing.Placement.isSame(new, 1e-12):
            thing.Placement = new
        return [step]
    if not bodies.has_solid(thing):
        raise AlignError("%s has no solid to move." % thing.Label)
    step = None
    for other in steps:
        if is_component_step(other) or bodies.body_of(other) is not thing:
            remove(other)
        else:
            step = other
    if step is None:
        step = bodies.insert_after_tip(thing, TYPE, "Align")
        AlignFeature(step)
        _attach_view_provider(step)
    if not step.Movement.isSame(place, 1e-12):
        step.Movement = place
    step.AlignId = align_id
    bodies.save_meta(step, META, meta)
    return [step]


def remove(step):
    """Take an Align step out again (a component goes back where it was)."""
    if not bodies.alive(step):
        return
    if is_component_step(step):
        part = step.Component
        if part is not None and bodies.alive(part):
            part.Placement = step.Before
        try:
            step.Document.removeObject(step.Name)
        except Exception:
            pass
        return
    bodies.remove_step(step)


def read(step):
    """Dialog options of an Align step (its picks and frames as they were stored)."""
    meta = bodies.load_meta(step, META)
    doc = step.Document

    def pick(entry):
        if not entry:
            return None
        obj = doc.getObject(entry.get("object", ""))
        return (obj, entry.get("sub", ""), None) if obj is not None else None

    options = with_defaults(
        {
            "objects": meta.get("objects", "bodies"),
            "from_pick": pick(meta.get("from")),
            "to_pick": pick(meta.get("to")),
            "flip": bool(meta.get("flip")),
            "turns": int(meta.get("turns", 0)),
        }
    )
    options["from_frame"] = meta.get("from_frame")
    options["to_frame"] = meta.get("to_frame")
    options["labels"] = (
        (meta.get("from") or {}).get("label", ""),
        (meta.get("to") or {}).get("label", ""),
    )
    return options


def moved_thing(step):
    if is_component_step(step):
        return step.Component
    return bodies.body_of(step)


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .bodies_gui import StepViewProvider

        StepViewProvider(obj.ViewObject)
    except Exception:
        pass


def dumps_frames(options):
    """The frames as JSON (diagnostics)."""
    return json.dumps(_meta(with_defaults(options)), sort_keys=True)
