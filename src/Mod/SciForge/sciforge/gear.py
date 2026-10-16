# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gear (SOLID > CREATE > Gear): spur, internal (ring) and rack gears as one timeline step.
No GUI code: the Gear dialog (gear_ui.py) and the golden-model builder both call this
module. The tooth outline and every check are in gear_core.py (unit tested).

What is built: a PartDesign Pad (Join, New Body, New Component) or Pocket (Cut) of
SciForge's own GearProfile, a hidden 2D object lying flat on the plane the user clicked,
centred on the clicked point. The profile computes the outline from its own properties
(Module, Teeth, ...), so a parameter typed in the dialog keeps driving the gear, and the
step has no sketch of its own (Fusion's sample script leaves a sketch and an extrude that
do not know they are a gear). The dialog's values are kept as JSON in the hidden property
"SciForgeGear" of the Pad / Pocket, as the Coil does.
"""

import FreeCAD as App

from . import gear_core as core
from . import primitives
from .primitives import PrimitiveError

META = "SciForgeGear"
KIND = "Gear"
PROFILE_ROLE = "GearProfile"
DEFAULTS = core.DEFAULTS
TYPES = core.TYPES
OPERATIONS = core.OPERATIONS
with_defaults = core.with_defaults
check = core.check
sizes = core.sizes

# Dialog field -> the profile's property holding it (the thickness is the Pad's Length).
PROFILE_PROPS = {
    "module": "Module",
    "diametral_pitch": "DiametralPitch",
    "teeth": "Teeth",
    "backlash": "Backlash",
    "fillet": "RootFillet",
    "hole": "HoleDiameter",
    "rim": "RimThickness",
    "rack_length": "RackLength",
    "rack_height": "RackHeight",
}


# -- the profile object ---------------------------------------------------------------------------
class GearProfile:
    """The gear's outline: a hidden 2D object attached flat to the gear's plane, its origin
    on the gear's centre. Saved documents store "sciforge.gear.GearProfile": keep the name
    stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Gear", doc)
                return True
            return False

        if add("App::PropertyEnumeration", "GearType", "Spur, internal (ring) or rack"):
            obj.GearType = list(core.TYPES)
        if add("App::PropertyEnumeration", "Standard", "Metric (module) or English (DP)"):
            obj.Standard = list(core.STANDARDS)
        if add("App::PropertyLength", "Module", "Pitch diameter / number of teeth"):
            obj.Module = core.DEFAULTS["module"]
        if add("App::PropertyFloat", "DiametralPitch", "Teeth per inch of pitch diameter"):
            obj.DiametralPitch = core.DEFAULTS["diametral_pitch"]
        if add("App::PropertyInteger", "Teeth", "Number of teeth"):
            obj.Teeth = core.DEFAULTS["teeth"]
        if add("App::PropertyFloat", "PressureAngle", "Pressure angle (degrees)"):
            obj.PressureAngle = core.DEFAULTS["pressure_angle"]
        add("App::PropertyLength", "Backlash", "Each tooth this much thinner (pitch circle)")
        add("App::PropertyLength", "RootFillet", "Root fillet radius")
        add("App::PropertyLength", "HoleDiameter", "Bore hole (spur gear; 0 = none)")
        if add("App::PropertyLength", "RimThickness", "Ring outside the root (internal)"):
            obj.RimThickness = core.DEFAULTS["rim"]
        if add("App::PropertyEnumeration", "RackSize", "A rack's size: teeth or length"):
            obj.RackSize = list(core.RACK_SIZES)
        if add("App::PropertyLength", "RackLength", "The rack's length (size by length)"):
            obj.RackLength = core.DEFAULTS["rack_length"]
        if add("App::PropertyLength", "RackHeight", "Material under the rack's root"):
            obj.RackHeight = core.DEFAULTS["rack_height"]

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    @staticmethod
    def options(obj):
        """The gear values the profile holds, as gear_core options."""
        return core.with_defaults(
            {
                "type": obj.GearType,
                "standard": obj.Standard,
                "module": obj.Module.Value,
                "diametral_pitch": float(obj.DiametralPitch),
                "teeth": int(obj.Teeth),
                "pressure_angle": float(obj.PressureAngle),
                "backlash": obj.Backlash.Value,
                "fillet": obj.RootFillet.Value,
                "hole": obj.HoleDiameter.Value,
                "rim": obj.RimThickness.Value,
                "rack_size": obj.RackSize,
                "rack_length": obj.RackLength.Value,
                "rack_height": obj.RackHeight.Value,
                "thickness": 1.0,  # the Pad's
            }
        )

    def execute(self, obj):
        loops = core.check(self.options(obj))  # GearError says what to change
        wires = [loop_wire(loop) for loop in loops]
        obj.positionBySupport()
        shape = wires[0] if len(wires) == 1 else _compound(wires)
        shape.Placement = obj.Placement
        obj.Shape = shape

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _compound(shapes):
    import Part

    return Part.Compound(shapes)


def loop_wire(loop):
    """A closed Part.Wire of a gear_core loop."""
    import Part

    V = App.Vector
    edges = []
    for seg in loop:
        kind = seg[0]
        if kind == "circle":
            (cx, cy), r = seg[1], seg[2]
            edges.append(Part.Circle(V(cx, cy, 0), V(0, 0, 1), r).toShape())
        elif kind == "line":
            edges.append(Part.LineSegment(V(*seg[1], 0), V(*seg[2], 0)).toShape())
        elif kind == "arc":
            edges.append(Part.Arc(V(*seg[1], 0), V(*seg[2], 0), V(*seg[3], 0)).toShape())
        else:
            curve = Part.BezierCurve()
            curve.setPoles([V(x, y, 0) for x, y in seg[1]])
            edges.append(curve.toShape())
    return Part.Wire(edges)


def tool_face(options):
    """The gear's face in its own plane (for checks and the golden models)."""
    import Part

    wires = [loop_wire(loop) for loop in core.check(options)]
    return Part.makeFace(wires, "Part::FaceMakerBullseye")


def _profile(body, feature, old):
    """The gear's profile object (re-used from the last update when there is one)."""
    for helper in list(old):
        if isinstance(getattr(helper, "Proxy", None), GearProfile):
            old.remove(helper)
            return helper
    obj = primitives.insert_helper(
        body, feature, "Part::Part2DObjectPython", "GearProfile", PROFILE_ROLE
    )
    GearProfile(obj)
    return obj


# -- building -------------------------------------------------------------------------------------
def type_id(operation):
    return "PartDesign::Pocket" if operation == "cut" else "PartDesign::Pad"


def is_gear(obj):
    return (
        obj is not None
        and obj.TypeId in ("PartDesign::Pad", "PartDesign::Pocket")
        and getattr(obj, "SciForgeType", "") == KIND
    )


def _tool_shape(ref, options):
    """The gear as a solid in global coordinates (for the Join-touches-nothing test)."""
    face = tool_face(options)
    t = float(options["thickness"])
    if options.get("symmetric"):
        face.translate(App.Vector(0, 0, -abs(t) / 2.0))
        t = abs(t)
    solid = face.extrude(App.Vector(0, 0, t))
    place = primitives.global_frame(ref).multiply(
        App.Placement(App.Vector(float(options["x"]), float(options["y"]), 0), App.Rotation())
    )
    solid.Placement = place.multiply(solid.Placement)
    return solid


def _joins_nothing(src, feature, ref, options):
    """True when a Join would not even touch the part it is made in: Fusion then makes a
    new body (it never leaves a separate piece in a body)."""
    if src is None:
        return False
    before = feature if feature is not None and primitives.owner_body(feature) is src else None
    base = primitives.base_shape(src, before=before)
    if base is None:
        return False  # the first solid of a body is a new body already
    try:
        tool = _tool_shape(ref, options)
        return primitives.auto_operation(base, tool) == "new_body"
    except Exception:
        return False


def build(ref, options, feature=None, name="Gear"):
    """Create the gear, or rebuild `feature`. Returns the step (another object when the
    operation changed its kind)."""
    options = with_defaults(options)
    if options["operation"] not in OPERATIONS:
        raise PrimitiveError("A gear can Join, Cut, make a New Body or a New Component.")
    check(options)
    ref = primitives.check_ref(ref)
    src = primitives.owner_body(ref[0])
    if feature is not None and ref[0] is feature:
        raise PrimitiveError("That face belongs to this gear itself. Pick another plane.")
    if options["operation"] == "join" and _joins_nothing(src, feature, ref, options):
        options = dict(options, operation="new_body")  # Fusion: a new body, not a lump
    operation = options["operation"]

    def setup(new):
        primitives.mark_type(new, KIND)

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
    profile = _profile(body, feature, old)
    helpers.append(profile)
    primitives.drop_helpers(doc, old_names, {h.Name for h in helpers})
    profile.Label = "%s profile" % feature.Label
    primitives.set_support(profile, support)
    offset = App.Placement(App.Vector(float(options["x"]), float(options["y"]), 0), App.Rotation())
    offset = primitives.attachment_offset(body, support, ref, offset)
    if not profile.AttachmentOffset.isSame(offset, 1e-12):
        profile.AttachmentOffset = offset
    _set_profile(profile, options)
    primitives.hide(profile)
    profile.recompute()
    if feature.Profile is None or feature.Profile[0] is not profile:
        feature.Profile = (profile, [""])
    _apply(feature, options)
    meta.update(
        {
            "v": 1,
            "kind": "gear",
            "ref": [ref[0].Name, ref[1]],
            "options": {k: v for k, v in options.items() if k != "expressions"},
            "formulas": {k: v for k, v in (options.get("expressions") or {}).items() if v},
            "helpers": [h.Name for h in helpers],
        }
    )
    primitives.save_meta(feature, meta, META)
    _apply_formulas(feature, profile, options)


def _set(obj, prop, value):
    current = getattr(obj, prop)
    current = getattr(current, "Value", current)
    if isinstance(value, (bool, str)):
        if current != value:
            setattr(obj, prop, value)
    elif isinstance(value, int) and not isinstance(current, float):
        if int(current) != value:
            setattr(obj, prop, value)
    elif abs(float(current) - float(value)) > 1e-12:
        setattr(obj, prop, value)


def _set_profile(profile, options):
    _set(profile, "GearType", options["type"])
    _set(profile, "Standard", options["standard"])
    _set(profile, "RackSize", options["rack_size"])
    _set(profile, "Module", float(options["module"]))
    _set(profile, "DiametralPitch", float(options["diametral_pitch"]))
    _set(profile, "Teeth", core.teeth_of(options))
    _set(profile, "PressureAngle", float(options["pressure_angle"]))
    for key in ("backlash", "fillet", "hole", "rim", "rack_length", "rack_height"):
        _set(profile, PROFILE_PROPS[key], max(0.0, float(options[key])))


def _apply(feature, options):
    t = float(options["thickness"])
    _set(feature, "Type", "Length")
    _set(feature, "Length", abs(t))
    _set(feature, "SideType", "Symmetric" if options.get("symmetric") else "One side")
    if feature.TypeId == "PartDesign::Pocket":
        # A Pocket cuts against the profile's normal unless reversed; the thickness is
        # signed along the normal like Fusion's (into the part is negative).
        _set(feature, "Reversed", t > 0)
    else:
        _set(feature, "Reversed", t < 0)
    _set(feature, "Refine", True)


# -- formulas -------------------------------------------------------------------------------------
def _formula_targets(feature, profile):
    targets = {key: [(profile, prop)] for key, prop in PROFILE_PROPS.items()}
    targets["thickness"] = [(feature, "Length")]
    return targets


def _apply_formulas(feature, profile, options):
    """A parameter typed in a field keeps driving the gear (Fusion): an expression on the
    property that holds the value."""
    formulas = options.get("expressions") or {}
    targets = []
    for key, objs in _formula_targets(feature, profile).items():
        text = formulas.get(key, "")
        for obj, prop in objs:
            value = text
            if text and key == "thickness" and float(options.get("thickness", 1.0)) < 0:
                value = "-(%s)" % text  # FreeCAD's Length is positive; Reversed has the sign
            targets.append((obj, prop, value))
    primitives.set_formulas(targets)


# -- reading back ---------------------------------------------------------------------------------
def profile_of(feature):
    meta = primitives.load_meta(feature, META)
    for name in meta.get("helpers", []):
        helper = feature.Document.getObject(name)
        if helper is not None and isinstance(getattr(helper, "Proxy", None), GearProfile):
            return helper
    return None


def read(feature):
    """(ref, options) of an existing gear, as the dialog shows them: the values as they
    are now (a parameter may drive them), the rest as last chosen."""
    meta = primitives.load_meta(feature, META)
    options = with_defaults(meta.get("options", {}))
    ref = None
    data = meta.get("ref")
    if data:
        obj = feature.Document.getObject(data[0])
        if obj is not None:
            ref = (obj, data[1])
    if feature.TypeId == "PartDesign::Pocket":
        options["operation"] = "cut"
        sign = 1.0 if feature.Reversed else -1.0
    else:
        saved = meta.get("options", {}).get("operation")
        options["operation"] = saved if saved in ("new_body", "new_component") else "join"
        sign = -1.0 if feature.Reversed else 1.0
    options["thickness"] = sign * feature.Length.Value
    options["symmetric"] = getattr(feature, "SideType", "One side") == "Symmetric"
    profile = profile_of(feature)
    if profile is not None:
        values = GearProfile.options(profile)
        for key in PROFILE_PROPS:
            options[key] = values[key]
        for key in ("type", "standard", "pressure_angle", "rack_size"):
            options[key] = values[key]
        options["expressions"] = primitives.kept_formulas(meta, _formula_targets(feature, profile))
    return ref, options


def is_ours(feature):
    return is_gear(feature) and bool(primitives.load_meta(feature, META).get("ref"))


def make(ref, options, name="Gear"):
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
