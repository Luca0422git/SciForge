# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSERT > Hardware...: a real-size screw, nut, washer, heat-set insert or magnet as its own
component, placed in the hole it goes into, and (when asked) that hole made in the part as a
normal Hole step. No Qt: the dialog (hardware_ui.py) and the golden-model builder run this.
The sizes come from hardware_core.py (pure Python, unit tested).

What one insert makes (one undo step, the dialog's transaction):

  a component     named after the part ("M3x10 ISO 4762"), with one body holding one step
                  "Hardware" (a PartDesign::FeaturePython, SciForgeType "Hardware") whose
                  solid is built from the tables. Fusion inserts a library part as its own
                  component too. The component's Placement puts the part's own frame on the
                  hole: origin on the hole's axis at the clicked face, +z out of the part.
  a Hole step     in the clicked body (SciForge's Hole: hole.py), at the same spot: a
                  clearance hole with the counterbore or countersink of the head, an insert's
                  hole or a magnet's pocket. Its options are SciForge's Hole options, so the
                  Hole dialog can edit it like any other hole.

Placing: click a round edge of the part (a hole's rim, a boss's edge: the part goes on its
axis, the head on the face the rim lies in) or a flat face (the part goes where you clicked,
square to the face). A rim that is already a hole does not get another one by default, and
the size is read off it (Fusion's Insert Fastener sizes itself from the hole: Automatic).

The step remembers its options and where it was clicked as JSON (property
"SciForgeHardware"); double-clicking it in the timeline opens the dialog again.
"""

import json
import math

import FreeCAD as App

from . import bodies, components, hole, log, warn
from . import hardware_core as core
from .hardware_core import HardwareError

TYPE = "PartDesign::FeaturePython"
KIND = "Hardware"  # SciForgeType of the step
META = "SciForgeHardware"
Z = App.Vector(0, 0, 1)
TOL = 1e-6
RIM_PROBE = 0.05  # mm beside a rim where the material is looked for
LOOKS = {  # appearance.LIBRARY keys
    "screw": "cast_iron",
    "nut": "steel_satin",
    "washer": "steel_satin",
    "insert": "brass",
    "magnet": "steel_polished",
}


# -- the solids ------------------------------------------------------------------------------------
def _cylinder(radius, z0, z1):
    import Part

    return Part.makeCylinder(radius, z1 - z0, App.Vector(0, 0, z0), Z)


def _hex_prism(s, z0, z1):
    """A hexagon s across the flats (flats parallel to x) from z0 to z1."""
    import Part

    r = s / math.sqrt(3.0)  # the corner radius
    points = [
        App.Vector(r * math.cos(math.radians(60 * i)), r * math.sin(math.radians(60 * i)), z0)
        for i in range(6)
    ]
    wire = Part.makePolygon(points + [points[0]])
    return Part.Face(wire).extrude(App.Vector(0, 0, z1 - z0))


def _cap(base_radius, height, z0):
    """A spherical cap (a button head): base radius, height, its flat side at z0."""
    import Part

    big = core.cap_radius(base_radius, height)
    sphere = Part.makeSphere(big, App.Vector(0, 0, z0 + height - big))
    box = Part.makeBox(4 * big, 4 * big, height, App.Vector(-2 * big, -2 * big, z0))
    return sphere.common(box)


def _cone(r_top, r_bottom, z_bottom, z_top):
    import Part

    return Part.makeCone(r_bottom, r_top, z_top - z_bottom, App.Vector(0, 0, z_bottom), Z)


def _one(shape):
    shape = shape.removeSplitter()
    return shape.Solids[0] if len(shape.Solids) == 1 else shape


def raw_solid(options):
    """The part in its own frame before the seat and flip (hardware_core.extent): screws
    with the head's bearing face at z = 0 (a countersunk head: its top), nuts and washers
    from z = 0 up, inserts and magnets from z = 0 down."""
    o = core.check(options)
    dm = core.dims(o["standard"], o["size"])
    kind = o["kind"]
    if kind == "nut":
        return _one(
            _hex_prism(dm["s"], 0.0, dm["m"]).cut(_cylinder(dm["d"] / 2.0, -1, dm["m"] + 1))
        )
    if kind == "washer":
        ring = _cylinder(dm["d2"] / 2.0, 0.0, dm["h"]).cut(
            _cylinder(dm["d1"] / 2.0, -1, dm["h"] + 1)
        )
        return _one(ring)
    if kind == "insert":
        tube = _cylinder(dm["outside"] / 2.0, -dm["length"], 0.0)
        return _one(tube.cut(_cylinder(dm["d"] / 2.0, -dm["length"] - 1, 1)))
    if kind == "magnet":
        return _one(_cylinder(dm["diameter"] / 2.0, -dm["thickness"], 0.0))
    d, dk, k, s, t = dm["d"], dm["dk"], dm["k"], dm["s"], dm["t"]
    length = o["length"]
    if o["standard"] == "iso10642":
        head = _cone(dk / 2.0, d / 2.0, -k, 0.0)
        shank = _cylinder(d / 2.0, -length, -k)
        top = 0.0
    else:
        if o["standard"] == "iso7380":
            head = _cap(dk / 2.0, k, 0.0)
        else:
            head = _cylinder(dk / 2.0, 0.0, k)
        shank = _cylinder(d / 2.0, -length, 0.0)
        top = k
    socket = _hex_prism(s, top - t, top + 1.0)
    return _one(head.fuse(shank).cut(socket))


def local_placement(options):
    """The part's placement in its component: lifted to its seat, turned round by Flip."""
    o = core.with_defaults(options)
    place = App.Placement(App.Vector(0, 0, core.seat(o)), App.Rotation())
    if o["flip"]:
        place = App.Placement(App.Vector(), App.Rotation(App.Vector(1, 0, 0), 180)).multiply(place)
    return place


def solid(options):
    """The part in its component's coordinates (the frame on the hole)."""
    shape = raw_solid(options).copy()
    place = local_placement(options)
    if not place.isIdentity():
        # baked into the geometry: a PartDesign feature puts its own Placement on its Shape
        # (a copy of the geometry moved, so circles stay circles)
        shape.transformShape(place.toMatrix(), True)
    return shape


# -- the step --------------------------------------------------------------------------------------
class HardwareFeature:
    """The Hardware step: its solid comes from the options in "SciForgeHardware". Saved in
    files as "sciforge.hardware.HardwareFeature": keep the name."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        bodies.mark(obj, KIND)
        if META not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", META, "SciForge", "Hardware options", 4)
        if "Refine" not in obj.PropertiesList:
            obj.addProperty("App::PropertyBool", "Refine", "Base", "Merge coplanar faces")
            obj.Refine = True

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            obj.Shape = solid(load_meta(obj).get("options", {}))
        except Exception:
            bodies.pass_through(obj)
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def load_meta(obj):
    try:
        return json.loads(getattr(obj, META, "") or "{}")
    except Exception:
        return {}


def _save_meta(obj, meta):
    text = json.dumps(meta, sort_keys=True)
    if getattr(obj, META, None) != text:
        setattr(obj, META, text)


def is_hardware(obj):
    try:
        return obj is not None and getattr(obj, "SciForgeType", "") == KIND
    except Exception:
        return False


def steps(doc):
    return [o for o in doc.Objects if is_hardware(o)]


def body_of(feature):
    return bodies.body_of(feature)


def component_of(feature):
    return components.container_of(body_of(feature))


def hole_of(feature):
    """The Hole step this part made, or None (deleted, or none asked for)."""
    name = load_meta(feature).get("hole")
    obj = feature.Document.getObject(name) if name else None
    return obj if hole.is_hole(obj) else None


def _attach_view(obj):
    if not App.GuiUp:
        return
    try:
        from .bodies_gui import attach_view_provider

        attach_view_provider(obj)
    except Exception:
        pass


def _look(body, kind):
    try:
        from . import appearance

        look = appearance.find(LOOKS.get(kind, "steel_satin"))
        if look is not None:
            appearance.set_body(body, look)
            appearance.apply(body)
    except Exception as exc:
        warn("hardware look: %s" % exc)


# -- where it goes ---------------------------------------------------------------------------------
def _global_element(obj, sub):
    element = obj.Shape.getElement(sub).copy()
    parent = obj.getParentGeoFeatureGroup()
    if parent is not None:
        place = parent.getGlobalPlacement()
        if not place.isIdentity():
            element.transformShape(place.toMatrix())
    return element


def _global_shape(obj):
    shape = obj.Shape.copy()
    parent = obj.getParentGeoFeatureGroup()
    if parent is not None:
        place = parent.getGlobalPlacement()
        if not place.isIdentity():
            shape.transformShape(place.toMatrix())
    return shape


def _perpendicular(axis):
    other = App.Vector(1, 0, 0) if abs(axis.x) < 0.9 else App.Vector(0, 1, 0)
    side = axis.cross(other)
    side.normalize()
    return side


def _inside(shape, point):
    try:
        return shape.isInside(point, 1e-7, False)
    except Exception:
        return False


def _on_face(shape, point, normal, tol=1e-6):
    """True when `point` lies on a flat face of `shape` square to `normal`."""
    import Part

    vertex = Part.Vertex(point)
    for face in shape.Faces:
        try:
            if face.Surface.TypeId != "Part::GeomPlane":
                continue
            if abs(hole.face_normal_at(face, point).dot(normal)) < 1.0 - 1e-9:
                continue
            box = face.BoundBox
            box.enlarge(1e-3)
            if box.isInside(point) and face.distToShape(vertex)[0] <= tol:
                return True
        except Exception:
            continue
    return False


def spot(obj, sub, point=None):
    """Where a click puts the part: {"center", "normal" (out of the part), "body", "rim"
    (the click was a round edge), "diameter" (the rim's), "is_hole" (the rim is a hole's),
    "face_point" (a point on the face the hole is drilled from)}, all global. Raises
    HardwareError when the click is no round edge or flat face of a solid."""
    if obj is None or not sub:
        raise HardwareError("Click a round edge (a hole's rim) or a flat face of the part.")
    body = bodies.body_of(obj)
    if body is None or obj.Shape.isNull() or not obj.Shape.Solids:
        raise HardwareError("Click a round edge or a flat face of a solid body.")
    try:
        element = _global_element(obj, sub)
    except Exception:
        raise HardwareError("That edge or face is gone. Click the part again.")
    shape = _global_shape(obj)
    if sub.startswith("Edge"):
        curve = getattr(element, "Curve", None)
        if curve is None or curve.TypeId != "Part::GeomCircle":
            raise HardwareError("That edge is not round. Click a hole's rim or a flat face.")
        center = App.Vector(curve.Center)
        axis = App.Vector(curve.Axis)
        axis.normalize()
        r = curve.Radius
        side = _perpendicular(axis)
        rim = center + side * r
        outside = rim + side * RIM_PROBE
        inside = rim - side * RIM_PROBE
        # Out of the part is the side of the rim's face with no material.
        if _inside(shape, outside - axis * RIM_PROBE) or _inside(shape, inside - axis * RIM_PROBE):
            normal = axis
        else:
            normal = -axis
        # A hole's rim has material outside the circle (under the face); a boss's inside.
        is_hole = _inside(shape, outside - normal * RIM_PROBE)
        # The face the rim lies in: beside the rim on one side (the top face around a hole,
        # a boss's top, the floor of a counterbore).
        if _on_face(shape, outside, normal):
            face_point = outside
        elif _on_face(shape, inside, normal):
            face_point = inside
        else:
            raise HardwareError(
                "That round edge has no flat face beside it. Click the rim on a flat face."
            )
        return {
            "center": center,
            "normal": normal,
            "body": body,
            "rim": True,
            "diameter": 2.0 * r,
            "is_hole": is_hole,
            "face_point": face_point,
        }
    if not sub.startswith("Face"):
        raise HardwareError("Click a round edge (a hole's rim) or a flat face of the part.")
    surface = getattr(element, "Surface", None)
    if surface is None or surface.TypeId != "Part::GeomPlane":
        raise HardwareError(
            "That face is curved. Click a flat face, or the round edge at a hole's opening."
        )
    if point is None:
        point = element.CenterOfMass
    point = hole.snap_to_face(element, point)
    normal = hole.face_normal_at(element, point)
    return {
        "center": App.Vector(point),
        "normal": normal,
        "body": body,
        "rim": False,
        "diameter": None,
        "is_hole": False,
        "face_point": App.Vector(point),
    }


def frame(place, flip=False):
    """The part's frame (global): origin on the hole's axis at the face, +z out of the part."""
    return App.Placement(App.Vector(place["center"]), App.Rotation(Z, App.Vector(place["normal"])))


def _parent_for_new(doc, body):
    """Fusion puts a new component under the active component (never inside a hardware part)."""
    parent = None
    if App.GuiUp:
        try:
            parent = components.active_component(doc)
        except Exception:
            parent = None
    else:
        parent = components.container_of(body)
    while parent is not None and any(is_hardware(o) for o in _features_in(parent)):
        parent = components.container_of(parent)
    return parent


def _features_in(component):
    found = []
    for b in components.bodies_in(component.Document, component):
        found += list(b.Group)
    return found


def _unique_label(doc, text, mine=None):
    taken = {o.Label for o in doc.Objects if o is not mine}
    label, n = text, 1
    while label in taken:
        n += 1
        label = "%s (%d)" % (text, n)
    return label


def _place_component(component, place):
    parent = components.container_of(component)
    base = parent.getGlobalPlacement() if parent is not None else App.Placement()
    wanted = base.inverse().multiply(frame(place))
    if not component.Placement.isSame(wanted, 1e-12):
        component.Placement = wanted


# -- the hole --------------------------------------------------------------------------------------
def _hole_base(body, own_hole):
    if own_hole is not None and hole.owner_body(own_hole) is body:
        return own_hole.BaseFeature
    tip = body.Tip
    if tip is None or tip.Shape.isNull() or not tip.Shape.Solids:
        return None
    return tip


def _place_hole(feature, place, wanted, old):
    """Make, move, change or remove the part's Hole step. Returns the hole or None."""
    body = place["body"]
    if old is not None and hole.owner_body(old) is not body:
        hole.remove(old)  # placed on another body: its hole goes there
        old = None
    if wanted is None:
        if old is not None:
            hole.remove(old)
        return None
    base = _hole_base(body, old)
    if base is None:
        raise HardwareError("%s has no solid to make the hole in." % body.Label)
    rotation = body.getGlobalPlacement().Rotation.inverted()
    on_face = hole.to_local(body, place["face_point"])
    center = hole.to_local(body, place["center"])
    face = hole.base_face_at(base, on_face, rotation.multVec(place["normal"]))
    if face is None:
        raise HardwareError("No face of %s there to make the hole in." % body.Label)
    try:
        if old is None:
            made = hole.make_single(body, base, face, on_face, wanted, name="Hole")
        else:
            made = old
            hole.set_position(made, base, face, on_face)
            hole.apply(made, dict(hole.options_with_defaults(wanted), placement="single"))
        if (center - on_face).Length > TOL:
            sketch = hole.helper_sketch(made)
            hole.move_to(made, hole._sketch_xy(sketch, center))
    except hole.HoleError as exc:
        raise HardwareError(str(exc))
    return made


# -- making and changing ---------------------------------------------------------------------------
def _pick_json(obj, sub, point):
    return {
        "object": obj.Name,
        "sub": sub,
        "point": [point.x, point.y, point.z] if point is not None else None,
    }


def pick_of(feature):
    """(object, sub, point) where the part was placed, or None (the object is gone)."""
    data = load_meta(feature).get("pick") or {}
    obj = feature.Document.getObject(data.get("object") or "")
    if obj is None:
        return None
    point = data.get("point")
    return obj, data.get("sub", ""), App.Vector(*point) if point else None


def read(feature):
    """(pick, options) of an existing part, as the dialog shows them."""
    meta = load_meta(feature)
    options = core.with_defaults(meta.get("options", {}))
    if hole_of(feature) is None:
        options["make_hole"] = False  # none asked for, or the hole step was deleted
    return pick_of(feature), options


def make(doc, pick, options):
    """Insert a part at `pick` = (object, sub, global point): a new component with the
    Hardware step, and its hole. Returns the step."""
    options = core.check(options)
    obj, sub, point = pick
    place = spot(obj, sub, point)
    body_target = place["body"]
    parent = _parent_for_new(doc, body_target)
    label = _unique_label(doc, core.name(options))
    component = components.new_component(doc, label=label, parent=parent)
    body = components.new_body_in(doc, component)
    feature = bodies.insert_after_tip(body, TYPE, "Hardware")
    HardwareFeature(feature)
    _attach_view(feature)
    _save_meta(
        feature,
        {
            "v": 1,
            "options": options,
            "pick": _pick_json(obj, sub, point),
            "hole": None,
            "label": label,
        },
    )
    _place_component(component, place)
    made = _place_hole(feature, place, core.hole_options(options), None)
    meta = load_meta(feature)
    meta["hole"] = made.Name if made is not None else None
    _save_meta(feature, meta)
    _look(body, options["kind"])
    hole.show_tip(body_target)
    log(
        "hardware %s inserted on %s%s"
        % (label, body_target.Label, " with %s" % made.Label if made is not None else "")
    )
    return feature


def update(feature, pick=None, options=None):
    """Change a part: new options and/or a new place (pick). Its hole follows. Returns the
    step."""
    meta = load_meta(feature)
    merged = dict(meta.get("options", {}))
    merged.update(options or {})
    merged = core.check(merged)
    if pick is None:
        pick = pick_of(feature)
        if pick is None:
            raise HardwareError("The face it was placed on is gone. Click a new place.")
    obj, sub, point = pick
    place = spot(obj, sub, point)
    component = component_of(feature)
    old_hole = hole_of(feature)
    made = _place_hole(feature, place, core.hole_options(merged), old_hole)
    if component is not None:
        _place_component(component, place)
        wanted = core.name(merged)
        if component.Label == meta.get("label") and core.name(meta.get("options", {})) != wanted:
            component.Label = _unique_label(feature.Document, wanted, mine=component)
            meta["label"] = component.Label
    kind_before = core.with_defaults(meta.get("options", {}))["kind"]
    meta.update(
        {
            "v": 1,
            "options": merged,
            "pick": _pick_json(obj, sub, point),
            "hole": made.Name if made is not None else None,
        }
    )
    _save_meta(feature, meta)
    if kind_before != merged["kind"]:
        _look(body_of(feature), merged["kind"])
    hole.show_tip(place["body"])
    return feature


def remove(feature):
    """Delete a part's component (with its body) and its hole."""
    made = hole_of(feature)
    component = component_of(feature)
    if made is not None:
        hole.remove(made)
    if component is not None:
        components.remove(feature.Document, component)
