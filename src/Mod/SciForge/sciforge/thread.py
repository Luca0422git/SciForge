# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Thread as a parametric feature in the body's timeline. No Qt here: the golden
models and headless tests build exactly what the Thread dialog builds.

Pick cylindrical faces (a shaft: an external thread; a hole: an internal one). The size is
taken from the diameter (Fusion does the same), the thread runs the full length of the face
or a given length from one end. Two ways to show it, like Fusion's Modeled checkbox:

  cosmetic (Modeled off)  the part is not changed; the thread is recorded (size, length,
                          class, hand) and drawn as a dashed helix on the face (thread_ui).
  modeled  (Modeled on)   the real thread is cut: an ISO 68-1 groove swept along a helix
                          (thread_core.py has the numbers). A shaft wider than the thread's
                          major diameter is turned down to it, a hole narrower than the minor
                          diameter is bored up to it, as Fusion's modeled threads do.

The feature is a PartDesign::FeaturePython, so later steps build on it and editing earlier
steps recomputes it. Saved documents store "sciforge.thread.ThreadFeature": keep that name.
"""
import json
import math

import FreeCAD as App

from . import thread_core as core
from . import thread_tables as tables

TYPE = "PartDesign::FeaturePython"
KIND = "Thread"
TOL = 1e-7

DEFAULTS = {
    "standard": "iso",
    "size": "",  # "" = taken from the face's diameter
    "designation": "",
    "thread_class": "",  # "" = the standard's usual class (6g / 6H, 2A / 2B)
    "direction": "right",
    "modeled": False,
    "full_length": True,
    "length": 10.0,
    "offset": 0.0,
}


class ThreadError(ValueError):
    """The thread cannot be made as asked; the message says why and what to do."""


def options_with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in (options or {}).items() if v is not None})
    return merged


# -- the cylinders ------------------------------------------------------------------------------
class Cylinder:
    """A cylindrical face to thread, in the coordinates of the shape it came from."""

    def __init__(self, face):
        surface = face.Surface
        if surface.TypeId != "Part::GeomCylinder":
            raise ThreadError("Pick a cylindrical face: the side of a shaft or the wall of a hole.")
        axis = App.Vector(surface.Axis)
        axis.normalize()
        self.axis = axis
        self.radius = float(surface.Radius)
        # Positions along the axis, measured from the surface's own base point.
        self.base = App.Vector(surface.Center)
        zs = []
        for edge in face.Edges:
            for p in edge.discretize(16):
                zs.append((p - self.base).dot(axis))
        if not zs:
            raise ThreadError("That face has no length to thread.")
        self.z0, self.z1 = min(zs), max(zs)
        # Fusion: a shaft gets an outside thread, a hole an inside one. The face's normal
        # points out of the material: towards the axis for a hole.
        u0, u1, v0, v1 = face.ParameterRange
        point = face.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
        normal = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
        foot = self.base + axis * (point - self.base).dot(axis)
        out = point - foot
        self.internal = normal.dot(out) < 0
        # The whole circle? (a half cylinder cannot hold a thread the way Fusion makes one)
        self.full = abs((u1 - u0) - 2.0 * math.pi) < 1e-6 or len(face.Wires) >= 2

    @property
    def length(self):
        return self.z1 - self.z0

    @property
    def diameter(self):
        return 2.0 * self.radius

    def at(self, z):
        return self.base + self.axis * z

    def same_as(self, other, tol=1e-6):
        return (
            abs(self.radius - other.radius) < tol
            and abs(abs(self.axis.dot(other.axis)) - 1.0) < 1e-9
            and abs(self.z0 - other.z0) < tol
            and abs(self.z1 - other.z1) < tol
            and (self.base - other.base).cross(self.axis).Length < tol
        )


def cylinder_of(shape, face_name):
    try:
        face = shape.getElement(face_name)
    except Exception:
        raise ThreadError(
            "The face %s is gone (an earlier step changed the part). Edit the thread and pick "
            "the face again." % face_name
        )
    return Cylinder(face)


def is_cylinder(face):
    return getattr(face.Surface, "TypeId", "") == "Part::GeomCylinder"


# -- sizes --------------------------------------------------------------------------------------
def size_for(cylinder, standard):
    """The designation Fusion proposes for a cylinder: a shaft at its own (major) diameter, a
    hole at its tap drill."""
    return tables.closest(standard, cylinder.diameter, internal=cylinder.internal)


def resolve(options, cylinder):
    """The Designation the options ask for (picking it from the face when not given)."""
    o = options_with_defaults(options)
    d = tables.find(o["standard"], o["designation"]) if o["designation"] else None
    if d is None and o["size"]:
        found = tables.designations(o["standard"], o["size"])
        d = found[0] if found else None
    if d is None:
        d = size_for(cylinder, o["standard"])
    if d is None:
        raise ThreadError("No standard thread fits this face.")
    return d


def thread_class(options, internal):
    o = options_with_defaults(options)
    wanted = o["thread_class"]
    known = tables.classes(o["standard"], internal)
    if wanted in known:
        return wanted
    # "6g" asked for a hole: the matching internal class ("6H"); else the usual one.
    swapped = wanted[:-1] + wanted[-1:].swapcase() if wanted else ""
    if o["standard"] == "ansi" and wanted[-1:] in ("A", "B"):
        swapped = wanted[:-1] + ("B" if internal else "A")
    if swapped in known:
        return swapped
    return tables.default_class(o["standard"], internal)


# -- the geometry -------------------------------------------------------------------------------
def _frame(cylinder):
    """Placement taking the thread's local frame (z = the axis) to the shape's coordinates."""
    rotation = App.Rotation(App.Vector(0, 0, 1), cylinder.axis)
    return App.Placement(cylinder.base, rotation)


def cutter(cylinder, designation, z0, z1, left_hand=False):
    """The solid a modeled thread removes from the part (shape coordinates)."""
    import Part

    if z1 - z0 <= TOL:
        raise ThreadError("The thread length must be more than 0.")
    pitch = designation.pitch
    major = designation.diameter / 2.0
    internal = cylinder.internal
    corners = core.groove(major, pitch, internal)
    # Start one pitch early and end one late: inside [z0, z1] every turn is complete.
    start = z0 - pitch
    height = (z1 - z0) + 2.0 * pitch
    helix = Part.makeLongHelix(pitch, height, major, 0.0, bool(left_hand))
    profile = Part.makePolygon([App.Vector(r, 0, z) for r, z in corners + [corners[0]]])
    sweep = Part.Wire(helix).makePipeShell([profile], True, True)
    if sweep.isNull() or not sweep.Solids:
        raise ThreadError("This thread could not be built. Try another size or untick Modeled.")
    sweep.translate(App.Vector(0, 0, start))
    h = core.fundamental_height(pitch)
    reach = major + h + cylinder.radius + 1.0
    bound = Part.makeCylinder(reach, z1 - z0, App.Vector(0, 0, z0))
    tool = sweep.common(bound)
    extra = None
    if internal:
        minor = major - 5.0 * h / 8.0
        if cylinder.radius < minor - TOL:  # bore the hole up to the minor diameter
            extra = Part.makeCylinder(minor, z1 - z0, App.Vector(0, 0, z0))
    elif cylinder.radius > major + TOL:  # turn the shaft down to the major diameter
        outer = Part.makeCylinder(cylinder.radius + 1.0, z1 - z0, App.Vector(0, 0, z0))
        inner = Part.makeCylinder(major, z1 - z0, App.Vector(0, 0, z0))
        extra = outer.cut(inner)
    if extra is not None:
        tool = tool.fuse(extra)
    tool.Placement = _frame(cylinder).multiply(tool.Placement)
    return tool


def build(base_shape, cylinders, designation, z_spans, left_hand=False, refine=True):
    """base_shape with modeled threads cut (one cylinder and span per face)."""
    tools = [cutter(c, designation, z0, z1, left_hand) for c, (z0, z1) in zip(cylinders, z_spans)]
    result = base_shape
    for tool in tools:
        result = result.cut(tool)
    if refine:
        try:
            result = result.removeSplitter()
        except Exception:
            pass
    solids = result.Solids
    if not solids:
        raise ThreadError("Nothing is left of the part here.")
    if len(solids) > 1:
        raise ThreadError("This thread cuts the part into pieces. Make it shorter or smaller.")
    return solids[0]


# -- the feature --------------------------------------------------------------------------------
class ThreadFeature:
    """Saved documents store "sciforge.thread.ThreadFeature": keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Thread"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSub", "Faces", "The cylindrical faces that are threaded")
        add("App::PropertyString", "Standard", "iso (ISO Metric profile) or ansi (Unified)")
        add("App::PropertyString", "Designation", "The thread, e.g. M6x1 or 1/4-20 UNC")
        add("App::PropertyString", "ThreadClass", "Tolerance class, e.g. 6g / 6H, 2A / 2B")
        if add("App::PropertyBool", "LeftHanded", "Left-hand thread"):
            obj.LeftHanded = False
        if add("App::PropertyBool", "Modeled", "Cut the real thread (off: cosmetic only)"):
            obj.Modeled = False
        if add("App::PropertyBool", "FullLength", "Thread the whole face"):
            obj.FullLength = True
        add("App::PropertyDistance", "Length", "Thread length when not full length")
        add("App::PropertyDistance", "Offset", "Distance from the face's end to the thread")
        if add("App::PropertyBool", "FromEnd", "Measure from the face's other end"):
            obj.FromEnd = False
        if add("App::PropertyBool", "Refine", "Merge faces that end up coplanar, like Fusion"):
            obj.Refine = True
        # What execute() found (read by the dialog and the cosmetic drawing; not user input).
        add("App::PropertyString", "Computed", "Where the threads are (JSON)", "Thread (result)")
        obj.setEditorMode("Computed", 1)
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)  # hidden
            obj.SciForgeType = KIND

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise ThreadError("A thread needs a solid before it in the timeline.")
        link = obj.Faces
        if not link or not link[1]:
            raise ThreadError("Pick a cylindrical face to thread.")
        source, names = link[0], list(link[1])
        shape = source.Shape
        cylinders = [cylinder_of(shape, name) for name in names]
        options = read(obj)
        designation = resolve(options, cylinders[0])
        spans = [
            core.span(
                c.z0,
                c.z1,
                obj.FullLength,
                obj.Length.Value,
                obj.Offset.Value,
                obj.FromEnd,
            )
            for c in cylinders
        ]
        for z0, z1 in spans:
            if z1 - z0 <= TOL:
                raise ThreadError(
                    "The thread is 0 long here: make it longer or the offset smaller."
                )
        computed = []
        for c, (z0, z1) in zip(cylinders, spans):
            if not c.full:
                raise ThreadError("Pick a full cylinder (not part of one) to thread.")
            computed.append(
                {
                    "base": list(c.base),
                    "axis": list(c.axis),
                    "radius": c.radius,
                    "z0": z0,
                    "z1": z1,
                    "internal": c.internal,
                }
            )
        record = {
            "threads": computed,
            "designation": designation.label,
            "pitch": designation.pitch,
            "major": designation.diameter,
            "left": bool(obj.LeftHanded),
        }
        if obj.Modeled:
            obj.Shape = build(
                base.Shape, cylinders, designation, spans, obj.LeftHanded, refine=obj.Refine
            )
        else:
            obj.Shape = base.Shape.copy()
        text = json.dumps(record, sort_keys=True)
        if obj.Computed != text:
            obj.Computed = text

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def is_thread(obj):
    return getattr(obj, "SciForgeType", "") == KIND


def computed(obj):
    """What the last recompute found: {"threads": [...], "designation", "pitch", ...}."""
    try:
        return json.loads(obj.Computed) if obj.Computed else {}
    except Exception:
        return {}


def owner_body(obj):
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        return None
    return parent if parent is not None and parent.TypeId == "PartDesign::Body" else None


def apply(obj, faces, options):
    """Write the dialog's options (and the picked faces: (feature, ["FaceN", ...]))."""
    o = options_with_defaults(options)
    if faces is not None:
        source, names = faces
        if list(obj.Faces[1] if obj.Faces else []) != list(names) or (
            obj.Faces and obj.Faces[0] is not source
        ):
            obj.Faces = (source, list(names))
    for prop, value in (
        ("Standard", o["standard"]),
        ("Designation", o["designation"] or ""),
        ("ThreadClass", o["thread_class"] or ""),
        ("LeftHanded", o["direction"] == "left"),
        ("Modeled", bool(o["modeled"])),
        ("FullLength", bool(o["full_length"])),
        ("FromEnd", bool(o.get("from_end", False))),
    ):
        if getattr(obj, prop) != value:
            setattr(obj, prop, value)
    for prop, value in (("Length", o["length"]), ("Offset", o["offset"])):
        if abs(getattr(obj, prop).Value - float(value)) > 1e-12:
            setattr(obj, prop, float(value))
    if not o["full_length"] and float(o["length"]) <= 0:
        raise ThreadError("The thread length must be more than 0.")
    if float(o["offset"]) < 0:
        raise ThreadError("The offset cannot be negative.")


def read(obj):
    """The dialog's options of an existing thread."""
    return {
        "standard": obj.Standard or "iso",
        "size": "",
        "designation": obj.Designation,
        "thread_class": obj.ThreadClass,
        "direction": "left" if obj.LeftHanded else "right",
        "modeled": bool(obj.Modeled),
        "full_length": bool(obj.FullLength),
        "length": obj.Length.Value,
        "offset": obj.Offset.Value,
        "from_end": bool(obj.FromEnd),
    }


def make(body, base, face_names, options=None, name="Thread"):
    """A Thread after `base` (normally body.Tip) on faces `face_names` of `base`. The
    designation is filled in from the face when the options leave it open."""
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise ThreadError("A thread needs a solid. Extrude a sketch first.")
    o = options_with_defaults(options)
    cylinders = [cylinder_of(base.Shape, n) for n in face_names]
    check_faces(cylinders)
    if not o["designation"]:
        d = resolve(o, cylinders[0])
        o["designation"] = d.label
        o["size"] = d.size
    if not o["thread_class"]:
        o["thread_class"] = tables.default_class(o["standard"], cylinders[0].internal)
    obj = body.newObject(TYPE, name)
    ThreadFeature(obj)
    obj.BaseFeature = base
    apply(obj, (base, list(face_names)), o)
    body.Tip = obj
    attach_view(obj)
    return obj


def attach_view(obj):
    try:
        if App.GuiUp and obj.ViewObject is not None:
            from .thread_ui import ViewProviderThread

            if not isinstance(getattr(obj.ViewObject, "Proxy", None), ViewProviderThread):
                ViewProviderThread(obj.ViewObject)
    except Exception:
        pass


def check_faces(cylinders):
    """All faces of one thread take the same size (Fusion threads them alike)."""
    if not cylinders:
        raise ThreadError("Pick a cylindrical face to thread.")
    first = cylinders[0]
    for c in cylinders[1:]:
        if abs(c.radius - first.radius) > 1e-6 or c.internal != first.internal:
            raise ThreadError(
                "All faces of one thread need the same diameter and side (all shafts or all "
                "holes). Make a second thread for the others."
            )
    for c in cylinders:
        if not c.full:
            raise ThreadError("Pick a full cylinder (not part of one) to thread.")


def remove(obj):
    body = owner_body(obj)
    base = obj.BaseFeature
    was_tip = body is not None and body.Tip is obj
    doc = obj.Document
    try:
        if body is not None:
            body.removeObject(obj)
    except Exception:
        pass
    try:
        doc.removeObject(obj.Name)
    except Exception:
        pass
    if was_tip and base is not None:
        try:
            body.Tip = base
        except Exception:
            pass
