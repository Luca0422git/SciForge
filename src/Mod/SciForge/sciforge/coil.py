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
from . import primitives_core as core
from .primitives import PrimitiveError

TYPES = core.COIL_TYPES
SECTIONS = core.COIL_SECTIONS
POSITIONS = core.POSITIONS
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

USES = core.COIL_USES
section_extent = core.coil_section_extent
section_radius = core.coil_section_radius
section_points = core.coil_section_points
resolved = core.coil_resolved
check = core.coil_check
volume = core.coil_volume


def with_defaults(options):
    out = dict(DEFAULTS)
    out.update({k: v for k, v in (options or {}).items() if v is not None})
    out.setdefault("expressions", {})
    return out


# -- the section ---------------------------------------------------------------------------------
def section_shape(options, axial=0.0):
    """The section as a closed wire in the upright plane (local coordinates), `axial` along
    the axis from the plane's origin."""
    import Part

    points = section_points(options)
    if points is None:
        circle = Part.Circle(
            App.Vector(section_radius(options), axial, 0),
            App.Vector(0, 0, 1),
            float(options["section_size"]) / 2.0,
        )
        return Part.Wire(circle.toShape())
    vectors = [App.Vector(x, y + axial, 0) for x, y in points]
    return Part.makePolygon(vectors + [vectors[0]])


# -- values -----------------------------------------------------------------------------------------
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
        # What a coil that narrows as it rises needs to start at its narrow end (see
        # narrow_end): the angle as typed, the signed height, the turns, the hand.
        add("App::PropertyAngle", "Taper", "The coil's angle (negative: it narrows)")
        add("App::PropertyDistance", "Rise", "The coil's height, signed")
        if add("App::PropertyFloat", "Turns", "The coil's revolutions"):
            obj.Turns = 1.0
        add("App::PropertyBool", "LeftHanded", "Counterclockwise coil")
        if add("App::PropertyPlacement", "BaseOffset", "Where the coil starts on its plane"):
            obj.setEditorMode("BaseOffset", 2)
            if "AttachmentOffset" in obj.PropertiesList:
                obj.BaseOffset = obj.AttachmentOffset  # a coil saved before this existed

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        options = {
            "section": obj.Section,
            "section_position": obj.SectionPosition,
            "diameter": obj.Diameter.Value,
            "section_size": obj.SectionSize.Value,
        }
        offset = obj.BaseOffset
        end = narrow_end(obj.Taper.Value, obj.Rise.Value, obj.Turns, obj.LeftHanded)
        if end is not None:
            shift, turn, narrower = end
            options["diameter"] -= narrower
            # The attachment places the section (and its V_Axis, where the helix starts):
            # a Placement set here would be overwritten by it.
            offset = offset.multiply(
                App.Placement(App.Vector(0, shift, 0), App.Rotation(App.Vector(0, 1, 0), turn))
            )
        axial = 0.0
        if abs(obj.Taper.Value) > 1e-9:
            # FreeCAD's tapered helix is only right when its axis starts level with the
            # body's origin: on a raised face the coil drifted (1.5 mm at the end of a 20 mm
            # coil, its volume 0.8 % short; found by the primitives QA). The section's own
            # origin goes down the axis to that level and the outline is drawn where it is.
            self._place(obj, offset)
            n = obj.Placement.Rotation.multVec(App.Vector(0, 1, 0))
            axial = obj.Placement.Base.dot(n)
            if abs(axial) > 1e-12:
                offset = offset.multiply(App.Placement(App.Vector(0, -axial, 0), App.Rotation()))
        self._place(obj, offset)
        shape = section_shape(options, axial)
        shape.Placement = obj.Placement
        obj.Shape = shape

    @staticmethod
    def _place(obj, offset):
        if not obj.AttachmentOffset.isSame(offset, 1e-12):
            obj.AttachmentOffset = offset
        obj.positionBySupport()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


UPRIGHT = App.Rotation(App.Vector(1, 0, 0), 90)  # plane frame -> the coil's upright plane


def narrows(options):
    """True for a coil that narrows as it rises (a negative angle)."""
    if options.get("type") == "spiral" or "angle" not in USES.get(options.get("type"), ()):
        return False
    return float(options.get("angle", 0.0)) < -1e-9


def narrow_end(taper, rise, turns, left_handed):
    """FreeCAD's helix always widens away from its section: a negative angle gave the mirror
    image (the coil went down through the plane instead of narrowing as it rose; found by
    the primitives QA). A coil that narrows is therefore swept from its narrow end back to
    the plane: the section stands at the far end (`rise` along the axis), that much nearer
    the axis, turned on by the coil's own turns so the coil still begins on the plane where
    it was clicked. Returns (shift along the axis, turn in degrees about it, how much
    smaller the diameter is there), or None for a coil that does not narrow."""
    if taper > -1e-9 or abs(rise) < 1e-9:
        return None
    narrower = 2.0 * abs(rise) * math.tan(math.radians(-taper))
    hand = -1.0 if left_handed else 1.0
    up = 1.0 if rise > 0 else -1.0
    return rise, 360.0 * float(turns) * hand * up, narrower


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
    if not section.BaseOffset.isSame(offset, 1e-12):
        section.BaseOffset = offset  # execute() adds a narrowing coil's far end (narrow_end)
    for prop, value in (
        ("Section", options["section"]),
        ("SectionPosition", options["section_position"]),
    ):
        if getattr(section, prop) != value:
            setattr(section, prop, value)
    turns, height, _pitch = resolved(options)
    for prop, value in (
        ("Diameter", float(options["diameter"])),
        ("SectionSize", float(options["section_size"])),
        ("Taper", float(options["angle"]) if "angle" in USES[options["type"]] else 0.0),
        ("Rise", height),
    ):
        if abs(getattr(section, prop).Value - value) > 1e-12:
            setattr(section, prop, value)
    if abs(section.Turns - turns) > 1e-12:
        section.Turns = turns
    if section.LeftHanded != (not bool(options.get("clockwise", True))):
        section.LeftHanded = not bool(options.get("clockwise", True))
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
            "formulas": {k: v for k, v in (options.get("expressions") or {}).items() if v},
            "helpers": [h.Name for h in helpers],
        }
    )
    primitives.save_meta(feature, meta, META)
    _apply_formulas(feature, section, options)


def _formula_targets(feature, section, kind):
    """Dialog field -> [(object, property)] that holds its value, for this coil type (the
    section also holds the angle, height and turns: it places itself by them)."""
    uses = USES[kind]
    targets = {"diameter": [(section, "Diameter")], "section_size": [(section, "SectionSize")]}
    if "revolutions" in uses:
        targets["revolutions"] = [(feature, "Turns")]
    if "height" in uses:
        targets["height"] = [(feature, "Height")]
    if "pitch" in uses:
        targets["pitch"] = [(feature, "Growth" if kind == "spiral" else "Pitch")]
    if "angle" in uses:
        targets["angle"] = [(feature, "Angle")]
    if "angle" in uses:
        targets["angle"] = targets["angle"] + [(section, "Taper")]
    if "height" in uses:
        targets["height"] = targets["height"] + [(section, "Rise")]
    if "revolutions" in uses:
        targets["revolutions"] = targets["revolutions"] + [(section, "Turns")]
    return targets


def _apply_formulas(feature, section, options):
    """A parameter typed in a field keeps driving the coil (Fusion): an expression on the
    property that holds the value. Properties the type works out itself carry none."""
    formulas = options.get("expressions") or {}
    narrowing = narrows(options)
    wanted = {}
    for key, objs in _formula_targets(feature, section, options["type"]).items():
        text = formulas.get(key, "")
        for obj, prop in objs:
            value = text
            if not text or obj is section and prop in ("Taper", "Rise"):
                pass  # the section keeps the signs as typed
            elif key == "height" and float(options.get("height", 1.0)) < 0:
                value = "-(%s)" % text  # FreeCAD's Height is positive; Reversed has the sign
            elif key == "angle" and narrowing:
                value = "-(%s)" % text  # swept from the narrow end: a widening angle
            wanted[(obj.Name, prop)] = (obj, prop, value)
    _derived_formulas(section, options, formulas, wanted)
    every = [
        (section, "Diameter"),
        (section, "SectionSize"),
        (section, "Taper"),
        (section, "Rise"),
        (section, "Turns"),
        (feature, "Turns"),
        (feature, "Height"),
        (feature, "Pitch"),
        (feature, "Growth"),
        (feature, "Angle"),
    ]
    primitives.set_formulas([wanted.get((o.Name, p), (o, p, "")) for o, p in every])


def _derived_formulas(section, options, formulas, wanted):
    """The section's height or turns when the coil type works them out (Revolution and
    Pitch: height = revolutions x pitch; Height and Pitch: turns = height / pitch) and a
    parameter drives one of the values they come from."""
    kind = options["type"]
    turns_text = formulas.get("revolutions", "")
    if kind == "rev_pitch" and (turns_text or formulas.get("pitch")):
        sign = "-" if float(options.get("height", 1.0)) < 0 else ""
        turns = "(%s)" % turns_text if turns_text else repr(float(options["revolutions"]))
        pitch = primitives.term(options, "pitch", section)
        wanted[(section.Name, "Rise")] = (section, "Rise", "%s%s * %s" % (sign, turns, pitch))
    if kind == "height_pitch" and (formulas.get("height") or formulas.get("pitch")):
        height = primitives.term(options, "height", section)
        pitch = primitives.term(options, "pitch", section)
        text = "abs(%s) / %s" % (height, pitch)
        wanted[(section.Name, "Turns")] = (section, "Turns", text)


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
        narrowing = narrows(options)
        _set(feature, "Mode", mode)
        _set(feature, "Angle", -angle if narrowing else angle)
        _set(feature, "Turns", turns)
        _set(feature, "Height", abs(height))
        _set(feature, "Pitch", pitch)
        _set(feature, "Growth", 0.0)
        # A narrowing coil is swept from its far end back to the plane (narrow_end).
        _set(feature, "Reversed", (height > 0) if narrowing else (height < 0))
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
    # The values as they are now (a parameter may drive them), not as last typed.
    section = None
    for name in meta.get("helpers", []):
        helper = feature.Document.getObject(name)
        if helper is not None and isinstance(getattr(helper, "Proxy", None), CoilSection):
            section = helper
    if section is not None:
        options["diameter"] = section.Diameter.Value
        options["section_size"] = section.SectionSize.Value
    kind = options["type"]
    narrowing = (
        section is not None
        and kind != "spiral"
        and "Taper" in section.PropertiesList
        and section.Taper.Value < -1e-9
    )
    reversed_ = bool(feature.Reversed) != narrowing  # a narrowing coil is swept back
    sign = -1.0 if reversed_ else 1.0
    options["revolutions"] = float(feature.Turns)
    if kind == "spiral":
        options["pitch"] = feature.Growth.Value
    else:
        options["height"] = sign * feature.Height.Value
        options["pitch"] = feature.Pitch.Value
        options["angle"] = section.Taper.Value if narrowing else feature.Angle.Value
    if section is not None:
        targets = _formula_targets(feature, section, kind)
        options["expressions"] = primitives.kept_formulas(meta, targets)
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
