# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Coil (SOLID > CREATE > Coil) on PartDesign's Helix. No GUI code: the Coil
dialog (coil_ui.py) and the golden-model builder both call this module.

The coil stands on a plane (`ref`, as in primitives.py) with its axis along the plane's
normal through the clicked centre (x, y). Fusion's fields (options, see DEFAULTS):

  type              rev_height    Revolution and Height
                    rev_pitch     Revolution and Pitch
                    height_pitch  Height and Pitch
                    spiral        flat spiral: Revolutions and Pitch (the growth of the
                                  radius per turn), no angle
  diameter          the coil's diameter (the circle the section is placed against)
  clockwise         True: turns clockwise while it rises (a right-hand coil, like a
                    standard thread), False: counterclockwise
  revolutions, height (signed: negative rises the other way), pitch
  angle             taper (degrees): positive widens the coil as it rises
  section           circular | square | tri_ext (triangle pointing out) | tri_int (in)
  section_position  inside | center | outside the coil diameter
  section_size      the section's size: the diameter of the circle round it (Fusion)
  operation         join | cut | intersect | new_body

What is built: PartDesign::AdditiveHelix (join, new body) or SubtractiveHelix (cut; with
Outside on, it keeps what is inside the coil: intersect), sweeping SciForge's own section
(CoilSection: a hidden 2D object on the plane, standing up through the axis) round the
axis. The section is computed from the dialog's values, so the coil has no sketch of its
own, like in Fusion. Options are kept as JSON in the hidden property "SciForgeCoil".
"""
import math

import FreeCAD as App

from . import primitives
from .primitives import PrimitiveError

TYPES = ("rev_height", "rev_pitch", "height_pitch", "spiral")
SECTIONS = ("circular", "square", "tri_ext", "tri_int")
POSITIONS = ("inside", "center", "outside")
OPERATIONS = primitives.OPERATIONS
META = "SciForgeCoil"
KIND = "Coil"
SECTION_ROLE = "CoilSection"

DEFAULTS = {
    "x": 0.0,
    "y": 0.0,
    "type": "rev_height",
    "diameter": 20.0,
    "clockwise": True,
    "revolutions": 5.0,
    "height": 20.0,
    "pitch": 4.0,
    "angle": 0.0,
    "section": "circular",
    "section_position": "inside",
    "section_size": 2.0,
    "operation": "join",
}

# Which values each type takes from the dialog (the others are worked out).
USES = {
    "rev_height": ("revolutions", "height", "angle"),
    "rev_pitch": ("revolutions", "pitch", "angle"),
    "height_pitch": ("height", "pitch", "angle"),
    "spiral": ("revolutions", "pitch"),
}


def with_defaults(options):
    out = dict(DEFAULTS)
    out.update({k: v for k, v in (options or {}).items() if v is not None})
    out.setdefault("expressions", {})
    return out


# -- the section ---------------------------------------------------------------------------------
def section_extent(options):
    """(how far the section reaches outward, inward, along the axis) from its centre."""
    size = float(options["section_size"])
    kind = options["section"]
    if kind == "square":
        half = size / (2.0 * math.sqrt(2.0))
        return half, half, 2.0 * half
    if kind in ("tri_ext", "tri_int"):
        r = size / 2.0  # the circle round the triangle
        side = r * math.sqrt(3.0)
        return (r, r / 2.0, side) if kind == "tri_ext" else (r / 2.0, r, side)
    return size / 2.0, size / 2.0, size


def section_radius(options):
    """Distance of the section's centre from the axis (the path radius at the start)."""
    out, inward, _ = section_extent(options)
    half = float(options["diameter"]) / 2.0
    position = options["section_position"]
    if position == "inside":
        return half - out
    if position == "outside":
        return half + inward
    return half


def section_points(options):
    """Outline of the section in the coil's upright plane: x away from the axis, y along it
    (None for the circle)."""
    rc = section_radius(options)
    size = float(options["section_size"])
    kind = options["section"]
    if kind == "square":
        h = size / (2.0 * math.sqrt(2.0))
        return [(rc - h, -h), (rc + h, -h), (rc + h, h), (rc - h, h)]
    if kind in ("tri_ext", "tri_int"):
        r = size / 2.0
        sign = 1.0 if kind == "tri_ext" else -1.0
        return [
            (rc + sign * r, 0.0),
            (rc - sign * r / 2.0, r * math.sqrt(3.0) / 2.0),
            (rc - sign * r / 2.0, -r * math.sqrt(3.0) / 2.0),
        ]
    return None


def section_shape(options):
    """The section as a closed wire in the upright plane (local coordinates)."""
    import Part

    points = section_points(options)
    if points is None:
        circle = Part.Circle(
            App.Vector(section_radius(options), 0, 0),
            App.Vector(0, 0, 1),
            float(options["section_size"]) / 2.0,
        )
        return Part.Wire(circle.toShape())
    vectors = [App.Vector(x, y, 0) for x, y in points]
    return Part.makePolygon(vectors + [vectors[0]])


# -- values -----------------------------------------------------------------------------------------
def resolved(options):
    """(revolutions, height, pitch) as the coil will have them, whatever the type."""
    kind = options["type"]
    turns = float(options["revolutions"])
    height = float(options["height"])
    pitch = float(options["pitch"])
    if kind == "rev_height":
        pitch = abs(height) / turns if turns > 0 else 0.0
    elif kind == "rev_pitch":
        height = turns * pitch * (-1.0 if height < 0 else 1.0)
    elif kind == "height_pitch":
        turns = abs(height) / pitch if pitch > 0 else 0.0
    else:
        height = 0.0
    return turns, height, pitch


def check(options):
    """Raise PrimitiveError with what to change when the values cannot make a coil."""
    for key, values in (
        ("type", TYPES),
        ("section", SECTIONS),
        ("section_position", POSITIONS),
        ("operation", OPERATIONS),
    ):
        if options.get(key) not in values:
            raise PrimitiveError("Unknown %s %r." % (key.replace("_", " "), options.get(key)))
    kind = options["type"]
    if float(options["diameter"]) <= 1e-6:
        raise PrimitiveError("The diameter must be larger than 0.")
    if float(options["section_size"]) <= 1e-6:
        raise PrimitiveError("The section size must be larger than 0.")
    uses = USES[kind]
    if "revolutions" in uses and float(options["revolutions"]) <= 1e-6:
        raise PrimitiveError("Revolutions must be more than 0.")
    if "height" in uses and abs(float(options["height"])) <= 1e-6:
        raise PrimitiveError("The height cannot be 0.")
    if "pitch" in uses and float(options["pitch"]) <= 1e-6:
        raise PrimitiveError("The pitch must be more than 0.")
    angle = float(options.get("angle", 0.0)) if "angle" in uses else 0.0
    if abs(angle) >= 89.0:
        raise PrimitiveError("The angle must stay between -89 and 89 degrees.")
    out, inward, along = section_extent(options)
    rc = section_radius(options)
    if rc - inward <= 1e-6:
        raise PrimitiveError(
            "The section reaches the coil's axis: make the section smaller than the coil "
            "or place it outside the diameter."
        )
    turns, height, pitch = resolved(options)
    if kind == "spiral":
        if pitch <= out + inward + 1e-6:
            raise PrimitiveError(
                "The turns of the spiral touch each other: the pitch must be larger than the "
                "section (%.4g mm)." % (out + inward)
            )
    else:
        # Turns closer than the section would cut into each other (OpenCASCADE then fails).
        axial = pitch * math.cos(math.radians(angle))
        if turns > 1.0 + 1e-9 and axial <= along + 1e-6:
            raise PrimitiveError(
                "The turns touch each other: the pitch (%.4g mm) must be larger than the "
                "section (%.4g mm). Make the coil taller, use fewer revolutions or a smaller "
                "section." % (pitch, along)
            )
        top = rc + abs(height) * math.tan(math.radians(angle))
        if top - inward <= 1e-6:
            raise PrimitiveError(
                "With this angle the coil narrows to its axis before the end. Make the "
                "angle smaller or the coil shorter."
            )
    return options


def helix_points(ref, options, count=None):
    """Points along the coil's middle line (global), for picking an operation."""
    turns, height, pitch = resolved(options)
    rc = section_radius(options)
    if count is None:
        count = max(24, min(400, int(36 * max(turns, 1.0))))
    place = primitives.global_frame(ref)
    angle = math.radians(float(options.get("angle", 0.0))) if options["type"] != "spiral" else 0
    sign = 1.0 if options.get("clockwise", True) else -1.0
    if height < 0:
        sign = -sign
    x0, y0 = float(options["x"]), float(options["y"])
    points = []
    for i in range(count + 1):
        t = i / float(count)
        theta = 2.0 * math.pi * turns * t
        z = height * t
        if options["type"] == "spiral":
            r = rc + pitch * turns * t
        else:
            r = rc + abs(z) * math.tan(angle)
        points.append(
            place.multVec(App.Vector(x0 + r * math.cos(theta), y0 + sign * r * math.sin(theta), z))
        )
    return points


def auto_operation(base, ref, options):
    """Fusion's pick when the user did not choose: a coil running mostly inside the part
    cuts it (a thread groove), one touching it joins, one away from it is a new body."""
    import Part

    if base is None or base.isNull() or not base.Solids:
        return "new_body"
    try:
        points = helix_points(ref, options, count=120)
    except Exception:
        return "join"
    inside = 0
    for p in points:
        try:
            if base.isInside(p, 1e-6, True):
                inside += 1
        except Exception:
            pass
    if inside > len(points) / 2.0:
        return "cut"
    if inside:
        return "join"
    out, inward, along = section_extent(options)
    try:
        gap = base.distToShape(Part.makePolygon(points))[0]
    except Exception:
        return "join"
    return "join" if gap <= max(out, inward, along / 2.0) + 1e-6 else "new_body"


# -- the section object ---------------------------------------------------------------------------
class CoilSection:
    """The coil's section: a hidden 2D object attached flat to the coil's plane, turned to
    stand up through the axis (its own y = the coil axis, x = away from it). The helix
    sweeps it round its V axis. Saved documents store "sciforge.coil.CoilSection": keep
    the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Coil section", doc)
                return True
            return False

        if add("App::PropertyEnumeration", "Section", "Shape of the section"):
            obj.Section = list(SECTIONS)
        if add("App::PropertyEnumeration", "SectionPosition", "Against the diameter"):
            obj.SectionPosition = list(POSITIONS)
        if add("App::PropertyLength", "Diameter", "Coil diameter"):
            obj.Diameter = 20.0
        if add("App::PropertyLength", "SectionSize", "Diameter of the circle round it"):
            obj.SectionSize = 2.0

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        obj.positionBySupport()
        options = {
            "section": obj.Section,
            "section_position": obj.SectionPosition,
            "diameter": obj.Diameter.Value,
            "section_size": obj.SectionSize.Value,
        }
        shape = section_shape(options)
        shape.Placement = obj.Placement
        obj.Shape = shape

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


UPRIGHT = App.Rotation(App.Vector(1, 0, 0), 90)  # plane frame -> the coil's upright plane


def _section(body, feature, old):
    """The coil's section object (re-used from the last update when there is one)."""
    for helper in list(old):
        if isinstance(getattr(helper, "Proxy", None), CoilSection):
            old.remove(helper)
            return helper
    obj = primitives.insert_helper(
        body, feature, "Part::Part2DObjectPython", "CoilSection", SECTION_ROLE
    )
    CoilSection(obj)
    return obj


# -- building -----------------------------------------------------------------------------------------
def type_id(operation):
    if operation in ("cut", "intersect"):
        return "PartDesign::SubtractiveHelix"
    return "PartDesign::AdditiveHelix"


def is_coil(obj):
    return (
        obj is not None
        and obj.TypeId in ("PartDesign::AdditiveHelix", "PartDesign::SubtractiveHelix")
        and getattr(obj, "SciForgeType", "") == KIND
    )


def build(ref, options, feature=None, name="Coil"):
    """Create the coil, or rebuild `feature`. Returns the step (another object when the
    operation changed its kind)."""
    options = with_defaults(options)
    check(options)
    ref = primitives.check_ref(ref)
    src = primitives.owner_body(ref[0])
    if feature is not None and ref[0] is feature:
        raise PrimitiveError("That face belongs to this coil itself. Pick another plane.")
    operation = options["operation"]

    def setup(new):
        primitives.mark_type(new, KIND)
        try:
            new.HasBeenEdited = True  # FreeCAD must not propose its own pitch
        except Exception:
            pass

    def update(step, body):
        _update(step, body, ref, options)

    return primitives.build_step(
        feature, src, operation, type_id(operation), name, update, setup, prop=META
    )


def _update(feature, body, ref, options):
    meta = primitives.load_meta(feature, META)
    doc = feature.Document
    old_names = list(meta.get("helpers", []))
    old = [doc.getObject(n) for n in old_names]
    old = [h for h in old if h is not None]
    helpers = []
    support = primitives.local_support(body, feature, ref, helpers, old)
    section = _section(body, feature, old)
    helpers.append(section)
    primitives.drop_helpers(doc, old_names, {h.Name for h in helpers})
    section.Label = "%s section" % feature.Label
    primitives.set_support(section, support)
    offset = App.Placement(App.Vector(float(options["x"]), float(options["y"]), 0), UPRIGHT)
    offset = primitives.attachment_offset(body, support, ref, offset)
    if not section.AttachmentOffset.isSame(offset, 1e-12):
        section.AttachmentOffset = offset
    for prop, value in (
        ("Section", options["section"]),
        ("SectionPosition", options["section_position"]),
    ):
        if getattr(section, prop) != value:
            setattr(section, prop, value)
    for prop, value in (
        ("Diameter", float(options["diameter"])),
        ("SectionSize", float(options["section_size"])),
    ):
        if abs(getattr(section, prop).Value - value) > 1e-12:
            setattr(section, prop, value)
    primitives.hide(section)
    section.recompute()
    if feature.Profile is None or feature.Profile[0] is not section:
        feature.Profile = (section, [""])
    axis = feature.ReferenceAxis
    if axis is None or axis[0] is not section or list(axis[1]) != ["V_Axis"]:
        feature.ReferenceAxis = (section, ["V_Axis"])
    _apply(feature, options)
    meta.update(
        {
            "v": 1,
            "kind": "coil",
            "ref": [ref[0].Name, ref[1]],
            "options": {k: v for k, v in options.items() if k != "expressions"},
            "helpers": [h.Name for h in helpers],
        }
    )
    primitives.save_meta(feature, meta, META)


def _set(obj, prop, value):
    current = getattr(obj, prop)
    current = getattr(current, "Value", current)
    if isinstance(value, bool) or isinstance(value, str):
        if current != value:
            setattr(obj, prop, value)
    elif abs(float(current) - float(value)) > 1e-12:
        setattr(obj, prop, value)


def _apply(feature, options):
    kind = options["type"]
    turns, height, pitch = resolved(options)
    angle = float(options.get("angle", 0.0)) if kind != "spiral" else 0.0
    if kind == "spiral":
        _set(feature, "Mode", "height-turns-growth")
        _set(feature, "Height", 0.0)
        _set(feature, "Turns", turns)
        _set(feature, "Growth", pitch)
        _set(feature, "Angle", 0.0)
        _set(feature, "Reversed", False)
    else:
        mode = {
            "rev_height": "height-turns-angle",
            "rev_pitch": "pitch-turns-angle",
            "height_pitch": "pitch-height-angle",
        }[kind]
        _set(feature, "Mode", mode)
        _set(feature, "Angle", angle)
        _set(feature, "Turns", turns)
        _set(feature, "Height", abs(height))
        _set(feature, "Pitch", pitch)
        _set(feature, "Growth", 0.0)
        _set(feature, "Reversed", height < 0)
    _set(feature, "LeftHanded", not bool(options.get("clockwise", True)))
    if feature.TypeId == "PartDesign::SubtractiveHelix":
        _set(feature, "Outside", options["operation"] == "intersect")
    _set(feature, "Refine", True)
    _set(feature, "HasBeenEdited", True)


# -- reading back -------------------------------------------------------------------------------------
def read(feature):
    """(ref, options) of an existing coil, as the dialog shows them."""
    meta = primitives.load_meta(feature, META)
    options = with_defaults(meta.get("options", {}))
    ref = None
    data = meta.get("ref")
    if data:
        obj = feature.Document.getObject(data[0])
        if obj is not None:
            ref = (obj, data[1])
    if feature.TypeId == "PartDesign::SubtractiveHelix":
        options["operation"] = "intersect" if feature.Outside else "cut"
    else:
        saved = meta.get("options", {}).get("operation")
        options["operation"] = "new_body" if saved == "new_body" else "join"
    options["clockwise"] = not feature.LeftHanded
    return ref, options


def is_ours(feature):
    return is_coil(feature) and bool(primitives.load_meta(feature, META).get("ref"))


def make(ref, options, name="Coil"):
    return build(ref, options, name=name)


def update(feature, ref=None, options=None):
    old_ref, old_options = read(feature)
    merged = dict(old_options)
    merged.update(options or {})
    return build(ref if ref is not None else old_ref, merged, feature=feature)


def remove(feature):
    body = primitives.owner_body(feature)
    primitives.remove_step(feature, keep_body=False, prop=META)
    primitives.show_tip(body)


def volume(options):
    """The coil's volume by Pappus (a section turned round an axis): area x the path its
    centre of area travels round the axis. FreeCAD's helix sweeps the upright section, so
    rising does not add volume. For hand-checks and the golden models."""
    out, inward, along = section_extent(options)
    size = float(options["section_size"])
    kind = options["section"]
    rc = section_radius(options)
    if kind == "circular":
        area = math.pi * size * size / 4.0
        centroid = rc
    elif kind == "square":
        area = size * size / 2.0
        centroid = rc
    else:
        r = size / 2.0
        area = 3.0 * math.sqrt(3.0) / 4.0 * r * r
        centroid = rc  # the circle's centre is the triangle's centroid
    turns, height, pitch = resolved(options)
    if options["type"] == "spiral":
        mean = centroid + pitch * turns / 2.0
    else:
        mean = centroid + abs(height) / 2.0 * math.tan(math.radians(float(options["angle"])))
    return area * 2.0 * math.pi * mean * turns
