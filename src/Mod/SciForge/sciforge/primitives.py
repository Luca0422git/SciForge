# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Box, Cylinder, Sphere and Torus (SOLID > CREATE) on top of PartDesign. No GUI
code: the dialogs (primitives_ui.py) and the golden-model builder both call this module.

Where a primitive sits, `ref` = (object, sub-element), the plane the user clicked:
  (origin plane, "")      XY / XZ / YZ of a body's origin (App::Plane)
  (datum plane, "")       a construction plane (PartDesign::Plane)
  (feature, "FaceN")      a flat face of a body

Positions and sizes are given in that plane's own frame, the frame FreeCAD's FlatFace
attachment gives it (the same one a sketch on that plane gets): x along the plane's
first axis, y along its second, the height along its normal (out of a face's solid).

Options (dict, see DEFAULTS), lengths in mm:
  box       x, y        first corner clicked
            sx, sy      +1 / -1: the side of the first corner the box goes to
            length      along x (> 0), width along y (> 0)
            height      along the normal, signed: negative goes the other way
  cylinder  x, y        centre; diameter; height (signed)
  sphere    x, y        centre (the sphere's centre lies on the plane); diameter
  torus     x, y        centre (the ring's middle lies on the plane)
            inner_diameter   the circle the torus is measured from
            torus_diameter   thickness of the ring
            position         inside | center | outside: where the ring's section sits
                             against that circle (inside: tangent from the inside...)
  all       operation   join | cut | intersect | new_body
            expressions {field: formula} typed in the dialog (parameters)

What is built:
  join / new_body   PartDesign::Additive<Kind> attached to the plane (FlatFace) with the
                    position in AttachmentOffset; new_body puts it in a new body (the first
                    solid of an empty body already is a new body)
  cut               PartDesign::Subtractive<Kind>
  intersect         SciForge's PrimitiveFeature (the body keeps what lies inside)
Changing the operation swaps the step for one of the other kind at the same place in the
timeline. Fusion-only data (the corners as clicked, the operation) is kept as JSON in the
hidden property "SciForgePrimitive", so the timeline edit shows the dialog as it was left.
"""
import json

import FreeCAD as App

from . import extrude
from . import primitives_core as core

KINDS = core.KINDS
OPERATIONS = core.OPERATIONS
POSITIONS = core.POSITIONS
NATIVE = {"box": "Box", "cylinder": "Cylinder", "sphere": "Sphere", "torus": "Torus"}
TITLES = dict(NATIVE)
FP_TYPE = "PartDesign::FeaturePython"
META = "SciForgePrimitive"
ROLE = "SciForgeRole"
TIMELINE = "SciForgeTimeline"
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
TOL = 1e-7

DEFAULTS = {
    "box": {
        "x": 0.0,
        "y": 0.0,
        "sx": 1.0,
        "sy": 1.0,
        "length": 10.0,
        "width": 10.0,
        "height": 10.0,
        "operation": "join",
    },
    "cylinder": {"x": 0.0, "y": 0.0, "diameter": 10.0, "height": 10.0, "operation": "join"},
    "sphere": {"x": 0.0, "y": 0.0, "diameter": 10.0, "operation": "join"},
    "torus": {
        "x": 0.0,
        "y": 0.0,
        "inner_diameter": 20.0,
        "torus_diameter": 5.0,
        "position": "center",
        "operation": "join",
    },
}

# Dialog field -> (property of the PartDesign feature, how the formula becomes its value).
FORMULA_PROPS = {
    "box": {"length": ("Length", "{}"), "width": ("Width", "{}"), "height": ("Height", "{}")},
    "cylinder": {"diameter": ("Radius", "({}) / 2"), "height": ("Height", "{}")},
    "sphere": {"diameter": ("Radius", "({}) / 2")},
    "torus": {},
}


PrimitiveError = core.PrimitiveError
nice = core.nice
torus_radii = core.torus_radii


owner_body = extrude.owner_body


# -- the plane ---------------------------------------------------------------------------------
def is_plane(obj):
    return obj is not None and obj.TypeId in PLANE_TYPES


def check_ref(ref):
    """The plane reference, or raise PrimitiveError saying what to pick instead."""
    if not ref or ref[0] is None:
        raise PrimitiveError("Select a plane or a flat face to put it on.")
    obj, sub = ref[0], ref[1] or ""
    try:
        if obj.Document.getObject(obj.Name) is None:
            raise PrimitiveError("The plane it sat on is gone. Select a plane or a flat face.")
    except ReferenceError:
        raise PrimitiveError("The plane it sat on is gone. Select a plane or a flat face.")
    if is_plane(obj):
        return (obj, "")
    if not sub.startswith("Face"):
        raise PrimitiveError("Select a plane or a flat face to put it on.")
    try:
        face = obj.Shape.getElement(sub)
    except Exception:
        raise PrimitiveError("The face it sat on is gone. Select a plane or a flat face.")
    if face.Surface.TypeId != "Part::GeomPlane":
        raise PrimitiveError("It needs a flat face or a plane. Pick a flat one.")
    if owner_body(obj) is None:
        raise PrimitiveError("Pick a face of a body or a plane.")
    return (obj, sub)


def frame(ref):
    """Placement of the plane's frame in its body's coordinates: FreeCAD's FlatFace
    attachment (the frame a sketch on that plane gets)."""
    import Part

    obj, sub = check_ref(ref)
    engine = Part.AttachEngine("Attacher::AttachEngine3D")
    engine.References = [(obj, sub)]
    engine.Mode = "FlatFace"
    try:
        return engine.calculateAttachedPlacement(App.Placement())
    except Exception as exc:
        raise PrimitiveError("Cannot put it on %s: %s" % (ref_label(ref), exc))


def body_placement(obj):
    body = owner_body(obj)
    if body is None or body is obj:
        return App.Placement()
    return body.getGlobalPlacement()


def global_frame(ref):
    """The plane's frame in global coordinates (what the mouse ray meets)."""
    return body_placement(ref[0]).multiply(frame(ref))


def ref_label(ref):
    if not ref or ref[0] is None:
        return ""
    obj, sub = ref
    if is_plane(obj):
        role = getattr(obj, "Role", "") or ""
        for key, text in (("XY", "XY Plane"), ("XZ", "XZ Plane"), ("YZ", "YZ Plane")):
            if role.startswith(key):
                return text
        return obj.Label
    if sub:
        return "Face of %s" % step_name(obj)
    return step_name(obj)


def step_name(obj):
    """What the timeline calls a step ("Extrude 2"), or its label."""
    try:
        from . import timeline_ops

        for item in timeline_ops.timeline(obj.Document, deps=False).items:
            if item.name == obj.Name:
                return item.display
    except Exception:
        pass
    return obj.Label


# -- options and shapes -----------------------------------------------------------------------
def with_defaults(kind, options):
    out = dict(DEFAULTS[kind])
    out.update({k: v for k, v in (options or {}).items() if v is not None})
    out.setdefault("expressions", {})
    return out


def check(kind, options):
    """Raise PrimitiveError when the values cannot make a solid (said in the dialog)."""
    return core.check_sizes(kind, options)


def local_offset(kind, options):
    """Where the PartDesign primitive sits in the plane's frame (its AttachmentOffset when
    attached to the plane itself)."""
    x, y = float(options["x"]), float(options["y"])
    if kind == "box":
        x0, y0, z0 = core.box_corner(options)
        return App.Placement(App.Vector(x0, y0, z0), App.Rotation())
    if kind == "cylinder":
        height = float(options["height"])
        return App.Placement(App.Vector(x, y, min(height, 0.0)), App.Rotation())
    return App.Placement(App.Vector(x, y, 0.0), App.Rotation())


def local_solid(kind, options):
    """The primitive's solid in the plane's frame."""
    import Part

    place = local_offset(kind, options)
    if kind == "box":
        shape = Part.makeBox(
            abs(float(options["length"])),
            abs(float(options["width"])),
            abs(float(options["height"])),
        )
    elif kind == "cylinder":
        shape = Part.makeCylinder(float(options["diameter"]) / 2.0, abs(float(options["height"])))
    elif kind == "sphere":
        shape = Part.makeSphere(float(options["diameter"]) / 2.0)
    else:
        major, minor = torus_radii(options)
        shape = Part.makeTorus(major, minor)
    shape.Placement = place.multiply(shape.Placement)
    return shape


def tool_shape(kind, ref, options):
    """The primitive's solid in global coordinates, as it will be added or cut."""
    options = with_defaults(kind, options)
    check(kind, options)
    shape = local_solid(kind, options)
    shape.Placement = global_frame(ref).multiply(shape.Placement)
    return shape


def corners(kind, ref, options):
    """Global points of the base outline (for the dialog's handles): the box's rectangle
    corners in the plane, or the circle's centre."""
    place = global_frame(ref)
    x, y = float(options["x"]), float(options["y"])
    if kind != "box":
        return [place.multVec(App.Vector(x, y, 0))]
    x2 = x + float(options.get("sx", 1.0)) * float(options["length"])
    y2 = y + float(options.get("sy", 1.0)) * float(options["width"])
    return [place.multVec(App.Vector(px, py, 0)) for px, py in ((x, y), (x2, y), (x2, y2), (x, y2))]


def auto_operation(base_shape, tool):
    """Fusion's choice when the user did not pick one: a primitive mostly inside the part
    cuts it, one touching or overlapping it joins, one away from every solid (or the first
    solid) is a new body (core.operation_for)."""
    if base_shape is None or base_shape.isNull() or not base_shape.Solids or tool is None:
        return "new_body"
    try:
        inside = base_shape.common(tool).Volume
    except Exception:
        return "join"
    gap = 0.0
    if inside <= 1e-9:
        try:
            gap = base_shape.distToShape(tool)[0]
        except Exception:
            gap = 0.0
    return core.operation_for(True, inside, tool.Volume - inside, gap)


def base_shape(body, before=None):
    """The body's solid the new step builds on (global coordinates), or None."""
    if body is None:
        return None
    tip = before.BaseFeature if before is not None else body.Tip
    if tip is None or tip.Shape.isNull() or not tip.Shape.Solids:
        return None
    shape = tip.Shape.copy()
    shape.Placement = body.getGlobalPlacement().multiply(shape.Placement)
    return shape


# -- meta and helpers (shared with coil.py and pipe.py) ----------------------------------------------
def load_meta(obj, prop=META):
    try:
        text = getattr(obj, prop, "")
        return json.loads(text) if text else {}
    except Exception:
        return {}


def save_meta(obj, meta, prop=META):
    if prop not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", prop, "SciForge", "Fusion options", 0)
        obj.setEditorMode(prop, 2)  # hidden
    text = json.dumps(meta, sort_keys=True)
    if getattr(obj, prop) != text:
        setattr(obj, prop, text)


def mark_type(obj, sciforge_type):
    """SciForgeType tells the timeline which Fusion step it is ("Coil", "Pipe"...)."""
    if "SciForgeType" not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
    if obj.SciForgeType != sciforge_type:
        obj.SciForgeType = sciforge_type


def mark_helper(obj, role):
    """A hidden object SciForge made for a step: never a timeline step of its own."""
    if ROLE not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", ROLE, "SciForge", "What SciForge made this for", 0)
        obj.setEditorMode(ROLE, 2)
    setattr(obj, ROLE, role)
    if TIMELINE not in obj.PropertiesList:
        obj.addProperty("App::PropertyBool", TIMELINE, "SciForge", "", 4)
    obj.SciForgeTimeline = False


def is_helper(obj):
    return bool(getattr(obj, ROLE, "")) or getattr(obj, TIMELINE, True) is False


def hide(obj):
    try:
        obj.Visibility = False
    except Exception:
        pass
    if App.GuiUp:
        try:
            obj.ViewObject.Visibility = False
            if "ShowInTree" in obj.ViewObject.PropertiesList:
                obj.ViewObject.ShowInTree = False
        except Exception:
            pass


def delete(obj):
    if obj is None:
        return
    try:
        doc = obj.Document
        name = obj.Name
    except ReferenceError:
        return
    body = owner_body(obj)
    try:
        if body is not None and body is not obj and obj in body.Group:
            body.removeObject(obj)
    except Exception:
        pass
    try:
        if doc.getObject(name) is not None:
            doc.removeObject(name)
    except Exception:
        pass


def show_tip(body):
    """FreeCAD hid the step before a new one; after removing one from Python the body's
    new Tip must be shown again, or the whole part seems to vanish."""
    if not App.GuiUp or body is None:
        return
    try:
        if body.Document.getObject(body.Name) is None:
            return
        tip = body.Tip
        if tip is not None and tip.ViewObject is not None and not tip.ViewObject.Visibility:
            tip.ViewObject.Visibility = True
    except Exception:
        pass


def has_solid(body, before=None):
    tip = before.BaseFeature if before is not None else body.Tip
    return tip is not None and not tip.Shape.isNull() and bool(tip.Shape.Solids)


def insert(body, type_id, name, before=None):
    """A new step in `body`: at the history marker, or just before `before`."""
    if before is not None:
        obj = body.Document.addObject(type_id, name)
        body.insertObject(obj, before, False)
        return obj
    return body.newObject(type_id, name)


def insert_helper(body, feature, type_id, name, role):
    """A hidden helper in `body` just before `feature`."""
    obj = body.Document.addObject(type_id, name)
    body.insertObject(obj, feature, False)
    mark_helper(obj, role)
    return obj


def new_body(src):
    from . import bodies

    return bodies.new_body(src.Document, like=src)


def remove_step(feature, keep_body=True, prop=META):
    """Delete a step with its helpers (and the body it created, when asked)."""
    meta = load_meta(feature, prop)
    doc = feature.Document
    body = owner_body(feature)
    helpers = [doc.getObject(n) for n in meta.get("helpers", [])]
    delete(feature)
    for helper in helpers:
        if helper is not None:
            delete(helper)
    if not keep_body and body is not None and meta.get("created_body") == body.Name:
        rest = [o for o in body.Group if o.TypeId != "App::Origin" and not is_origin(o)]
        if not rest:
            try:
                body.removeObjectsFromDocument()
            except Exception:
                pass
            try:
                doc.removeObject(body.Name)
            except Exception:
                pass


def is_origin(obj):
    return obj.TypeId in ("App::Origin", "App::Line", "App::Plane", "App::Point")


def structure(feature, src, operation, prop=META):
    """(target body or None for 'make a new one', the body it made before or None)."""
    meta = load_meta(feature, prop) if feature is not None else {}
    created = None
    if feature is not None and meta.get("created_body"):
        created = feature.Document.getObject(meta["created_body"])
    if operation == "new_body":
        if created is not None:
            return created, created
        if feature is not None and owner_body(feature) is src and not has_solid(src, feature):
            return src, None  # the first solid of a body already is a new body
        if feature is None and not has_solid(src):
            return src, None
        return None, None
    return src, None


def build_step(feature, src, operation, type_id, name, update, setup_new=None, prop=META):
    """Create the step, or rebuild `feature`. update(step, target body) sets everything
    (and raises PrimitiveError when it cannot). setup_new(step) runs once on a new object
    (Python features get their proxy there). Returns the step (another object when its
    kind or body had to change)."""
    if src is None:
        raise PrimitiveError("Select a plane or a face of a body first.")
    if operation in ("cut", "intersect") and not has_solid(
        src, feature if feature is not None and owner_body(feature) is src else None
    ):
        raise PrimitiveError(
            "%s needs a solid to work on, and there is none yet. Use Join or New Body."
            % {"cut": "Cut", "intersect": "Intersect"}[operation]
        )
    target, created = structure(feature, src, operation, prop)
    if feature is not None:
        same_type = feature.TypeId == type_id
        if owner_body(feature) is target and same_type:
            update(feature, target)
            return feature
        blocking = [o for o in extrude.dependents(feature) if not is_helper(o)]
        if blocking:
            raise PrimitiveError(
                "%s is used by %s, so its operation cannot change here. Make a new one "
                "instead." % (feature.Label, ", ".join(o.Label for o in blocking))
            )
    if target is None:
        target = created = new_body(src)
    before = feature if (feature is not None and owner_body(feature) is target) else None
    was_tip = before is not None and target.Tip is before
    new = insert(target, type_id, name, before)
    if hasattr(new, "Refine"):
        new.Refine = True
    if setup_new is not None:
        setup_new(new)
    save_meta(new, {"created_body": created.Name if created is not None else None}, prop)
    try:
        update(new, target)
    except Exception:
        remove_step(new, keep_body=created is None or before is not None, prop=prop)
        raise
    if feature is not None:
        label = feature.Label
        old_body = owner_body(feature)
        remove_step(feature, keep_body=old_body is target, prop=prop)
        new.Label = label
        if old_body is not None and old_body is not target:
            show_tip(old_body)
    if before is None or was_tip:
        target.Tip = new
    return new


def local_support(body, feature, ref, helpers, old_helpers):
    """A plane reference `feature` (in `body`) may attach to, standing for `ref`: the ref
    itself in its own body; the same origin plane of `body` when the bodies coincide; a
    hidden copy of the face (SubShapeBinder) for a face of another body; else `body`'s XY
    plane (the offset then carries the whole placement)."""
    obj, sub = ref
    if owner_body(obj) is body:
        return (obj, sub)
    if obj.TypeId == "App::Plane":
        role = (getattr(obj, "Role", "") or obj.Name)[:2]
        mine = _origin_plane(body, role)
        if mine is not None and body_placement(obj).isSame(body.getGlobalPlacement(), 1e-9):
            return (mine, "")
        return (_origin_plane(body, "XY"), "")
    existing = None
    for helper in list(old_helpers):
        if helper.TypeId == "PartDesign::SubShapeBinder" and getattr(helper, ROLE, "") == (
            "PrimitivePlane"
        ):
            existing = helper
            old_helpers.remove(helper)
            break
    binder = existing
    if binder is None:
        binder = insert_helper(
            body, feature, "PartDesign::SubShapeBinder", "PrimitivePlane", "PrimitivePlane"
        )
    binder.Label = "%s plane" % feature.Label
    support = [(obj, (sub,) if sub else ())]
    if list(binder.Support) != support:
        binder.Support = support
    hide(binder)
    binder.recompute()
    helpers.append(binder)
    return (binder, "Face1")


def _origin_plane(body, role):
    for feature in body.Origin.OriginFeatures:
        if (getattr(feature, "Role", "") or feature.Name).startswith(role):
            return feature
    return None


def attachment_offset(body, support, ref, offset):
    """AttachmentOffset on `support` (in `body`) that puts `offset` (given in the frame of
    `ref`, the plane the user clicked) at the same place."""
    if support[0] is ref[0] and (support[1] or "") == (ref[1] or ""):
        return offset
    wanted = global_frame(ref).multiply(offset)
    have = body.getGlobalPlacement().multiply(frame(support))
    return have.inverse().multiply(wanted)


def set_support(obj, support):
    """Attach `obj` flat to `support` = (plane or feature, "" or "FaceN"), only if needed
    (setting it again re-attaches and recomputes)."""
    obj_, sub = support
    have = [(o.Name, tuple(s for s in subs if s)) for o, subs in obj.AttachmentSupport]
    want = [(obj_.Name, (sub,) if sub else ())]
    if have != want:
        obj.AttachmentSupport = [(obj_, sub)]
    if obj.MapMode != "FlatFace":
        obj.MapMode = "FlatFace"


def drop_helpers(doc, names, keep):
    for name in names:
        helper = doc.getObject(name)
        if helper is not None and name not in keep:
            delete(helper)


# -- the intersect feature ------------------------------------------------------------------------
class PrimitiveFeature:
    """Box / Cylinder / Sphere / Torus with operation Intersect: the body keeps what lies
    inside the primitive. Its properties have the names of PartDesign's primitives, so the
    dialog sets either kind the same way. Saved documents store
    "sciforge.primitives.PrimitiveFeature": keep the name stable."""

    def __init__(self, obj, kind):
        obj.Proxy = self
        self.ensure_properties(obj, kind)

    @staticmethod
    def ensure_properties(obj, kind=None):
        def add(kind_, name, doc, group="Primitive"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind_, name, group, doc)
                return True
            return False

        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
            obj.SciForgeType = NATIVE.get(kind, "Box")
        add("App::PropertyLinkSubList", "AttachmentSupport", "The plane it sits on", "Attachment")
        if add("App::PropertyEnumeration", "MapMode", "Attached or fixed", "Attachment"):
            obj.MapMode = ["Deactivated", "FlatFace"]
            obj.MapMode = "FlatFace"
        add("App::PropertyPlacement", "AttachmentOffset", "Place on the plane", "Attachment")
        add("App::PropertyPlacement", "Frame", "Last frame of the plane", "Attachment")
        obj.setEditorMode("Frame", 2)
        for name in ("Length", "Width", "Height", "Radius", "Radius1", "Radius2"):
            if add("App::PropertyLength", name, "Size"):
                setattr(obj, name, 10.0)
        if add("App::PropertyBool", "Refine", "Merge coplanar faces, like Fusion"):
            obj.Refine = True

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        kind = KIND_OF_TYPE.get(obj.SciForgeType, "box")
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise PrimitiveError("Intersect needs a solid before it in the timeline.")
        place = obj.Frame  # where the plane was when the step was last edited
        support = list(obj.AttachmentSupport)
        if obj.MapMode == "FlatFace" and support:
            linked, subs = support[0]
            place = frame((linked, (subs or [""])[0]))
        options = _fp_options(obj, kind)
        tool = local_solid(kind, options)
        tool.Placement = place.multiply(obj.AttachmentOffset).multiply(tool.Placement)
        result = base.Shape.common(tool)
        if obj.Refine:
            result = result.removeSplitter()
        if result.isNull() or not result.Solids or result.Volume < TOL:
            raise PrimitiveError(
                "The %s does not overlap the body, so Intersect would leave nothing."
                % TITLES[kind].lower()
            )
        obj.Shape = result.Solids[0] if len(result.Solids) == 1 else result

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


KIND_OF_TYPE = {v: k for k, v in NATIVE.items()}


def _fp_options(obj, kind):
    """Options (positioned at the offset's origin) from the intersect feature's sizes."""
    options = {"x": 0.0, "y": 0.0, "sx": 1.0, "sy": 1.0}
    if kind == "box":
        options.update(length=obj.Length.Value, width=obj.Width.Value, height=obj.Height.Value)
    elif kind == "cylinder":
        options.update(diameter=2.0 * obj.Radius.Value, height=obj.Height.Value)
    elif kind == "sphere":
        options.update(diameter=2.0 * obj.Radius.Value)
    else:
        options.update(
            inner_diameter=2.0 * obj.Radius1.Value,
            torus_diameter=2.0 * obj.Radius2.Value,
            position="center",
        )
    return options


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .primitives_ui import ViewProviderPrimitive

        ViewProviderPrimitive(obj.ViewObject)
    except Exception:
        pass


# -- building ------------------------------------------------------------------------------------------
def type_id(kind, operation):
    if operation == "cut":
        return "PartDesign::Subtractive" + NATIVE[kind]
    if operation == "intersect":
        return FP_TYPE
    return "PartDesign::Additive" + NATIVE[kind]


def kind_of(feature):
    """box / cylinder / sphere / torus of a step, or None."""
    if feature is None:
        return None
    meta = load_meta(feature)
    if meta.get("kind") in KINDS:
        return meta["kind"]
    for kind, word in NATIVE.items():
        if feature.TypeId in ("PartDesign::Additive" + word, "PartDesign::Subtractive" + word):
            return kind
    if feature.TypeId == FP_TYPE and getattr(feature, "SciForgeType", "") in KIND_OF_TYPE:
        if isinstance(getattr(feature, "Proxy", None), PrimitiveFeature):
            return KIND_OF_TYPE[feature.SciForgeType]
    return None


def is_ours(feature):
    """True for a primitive SciForge's dialog made (it knows where it was clicked)."""
    return kind_of(feature) is not None and bool(load_meta(feature).get("ref"))


def build(kind, ref, options, feature=None, name=None):
    """Create the primitive, or rebuild `feature` with a new plane/options. Returns the
    step (another object when the operation changed its kind)."""
    options = with_defaults(kind, options)
    check(kind, options)
    ref = check_ref(ref)
    src = owner_body(ref[0])
    if src is None:
        raise PrimitiveError("Select a plane or a face of a body.")
    if feature is not None and _uses_itself(feature, ref):
        raise PrimitiveError(
            "That face belongs to this %s itself. Pick a face that was there before it."
            % TITLES[kind].lower()
        )
    operation = options["operation"]
    tid = type_id(kind, operation)

    def setup(new):
        if tid == FP_TYPE:
            PrimitiveFeature(new, kind)
            _attach_view_provider(new)

    def update(step, body):
        _update(step, body, kind, ref, options)

    return build_step(feature, src, operation, tid, name or NATIVE[kind], update, setup)


def _uses_itself(feature, ref):
    obj = ref[0]
    if obj is feature:
        return True
    body = owner_body(feature)
    if body is None or owner_body(obj) is not body or is_plane(obj):
        return False
    group = list(body.Group)
    try:
        return group.index(obj) > group.index(feature)
    except ValueError:
        return False


def _update(feature, body, kind, ref, options):
    meta = load_meta(feature)
    doc = feature.Document
    old_names = list(meta.get("helpers", []))
    old = [doc.getObject(n) for n in old_names]
    old = [h for h in old if h is not None]
    helpers = []
    support = local_support(body, feature, ref, helpers, old)
    drop_helpers(doc, old_names, {h.Name for h in helpers})
    offset = attachment_offset(body, support, ref, local_offset(kind, options))
    set_support(feature, support)
    _apply_sizes(feature, kind, options)
    if not feature.AttachmentOffset.isSame(offset, 1e-12):
        feature.AttachmentOffset = offset
    if feature.TypeId == FP_TYPE:
        place = frame(support)
        if not feature.Frame.isSame(place, 1e-12):
            feature.Frame = place
    if hasattr(feature, "Refine") and not feature.Refine:
        feature.Refine = True
    _apply_formulas(feature, kind, options)
    meta.update(
        {
            "v": 1,
            "kind": kind,
            "ref": [ref[0].Name, ref[1]],
            "options": {k: v for k, v in options.items() if k != "expressions"},
            "helpers": [h.Name for h in helpers],
        }
    )
    save_meta(feature, meta)


def _set(obj, prop, value):
    if abs(getattr(obj, prop).Value - value) > 1e-12:
        setattr(obj, prop, value)


def _apply_sizes(feature, kind, options):
    if kind == "box":
        _set(feature, "Length", abs(float(options["length"])))
        _set(feature, "Width", abs(float(options["width"])))
        _set(feature, "Height", abs(float(options["height"])))
    elif kind == "cylinder":
        _set(feature, "Radius", float(options["diameter"]) / 2.0)
        _set(feature, "Height", abs(float(options["height"])))
    elif kind == "sphere":
        _set(feature, "Radius", float(options["diameter"]) / 2.0)
    else:
        # Radius1 = the ring's middle, Radius2 = its section (both features). Grow before
        # shrinking so FreeCAD never sees a torus thicker than its ring on the way.
        major, minor = torus_radii(options)
        if major > feature.Radius1.Value:
            _set(feature, "Radius1", major)
            _set(feature, "Radius2", minor)
        else:
            _set(feature, "Radius2", minor)
            _set(feature, "Radius1", major)


def _apply_formulas(feature, kind, options):
    from . import preview

    formulas = options.get("expressions") or {}
    for key, (prop, template) in FORMULA_PROPS.get(kind, {}).items():
        text = formulas.get(key, "")
        try:
            if text:
                value = float(options.get(key, 1.0))
                if key == "height" and value < 0:
                    template = "-({})"
                preview.set_formula(feature, prop, template.format(text))
            else:
                preview.set_formula(feature, prop, "")
        except Exception:
            preview.set_formula(feature, prop, "")


# -- reading back --------------------------------------------------------------------------------------
def read(feature):
    """(kind, ref, options) of an existing primitive, as the dialog shows them. The sizes
    come from the feature (a parameter may drive them), the rest from the meta."""
    from . import preview

    kind = kind_of(feature)
    if kind is None:
        raise PrimitiveError("%s is not a box, cylinder, sphere or torus." % feature.Label)
    meta = load_meta(feature)
    options = with_defaults(kind, meta.get("options", {}))
    ref = None
    data = meta.get("ref")
    if data:
        obj = feature.Document.getObject(data[0])
        if obj is not None:
            ref = (obj, data[1])
    if ref is None:
        support = list(feature.AttachmentSupport)
        if support:
            obj, subs = support[0]
            ref = (obj, (subs or [""])[0] if isinstance(subs, (list, tuple)) else subs)
            off = feature.AttachmentOffset.Base
            options["x"], options["y"] = off.x, off.y
    if feature.TypeId == FP_TYPE:
        options["operation"] = "intersect"
    elif feature.TypeId.startswith("PartDesign::Subtractive"):
        options["operation"] = "cut"
    else:
        options["operation"] = (
            "new_body" if meta.get("options", {}).get("operation") == "new_body" else "join"
        )
    sign = -1.0 if float(options.get("height", 1.0) or 1.0) < 0 else 1.0
    if kind == "box":
        options["length"] = feature.Length.Value
        options["width"] = feature.Width.Value
        options["height"] = sign * feature.Height.Value
    elif kind == "cylinder":
        options["diameter"] = 2.0 * feature.Radius.Value
        options["height"] = sign * feature.Height.Value
    elif kind == "sphere":
        options["diameter"] = 2.0 * feature.Radius.Value
    expressions = {}
    for key, (prop, _template) in FORMULA_PROPS.get(kind, {}).items():
        text = preview.formula_of(feature, prop)
        if text:
            expressions[key] = _strip_template(text)
    options["expressions"] = expressions
    return kind, ref, options


def _strip_template(text):
    """The formula the user typed, from the expression set on a property."""
    t = text.strip()
    if t.startswith("-(") and t.endswith(")"):
        t = t[2:-1].strip()
    if t.endswith("/ 2") and t.startswith("("):
        t = t[: -len("/ 2")].strip()
        if t.startswith("(") and t.endswith(")"):
            t = t[1:-1].strip()
    return t


def make(kind, ref, options, name=None):
    return build(kind, ref, options, name=name)


def update(feature, ref=None, options=None):
    """Rebuild an existing primitive; what is not given stays as it is."""
    kind, old_ref, old_options = read(feature)
    merged = dict(old_options)
    merged.update(options or {})
    return build(kind, ref if ref is not None else old_ref, merged, feature=feature)


def remove(feature):
    body = owner_body(feature)
    remove_step(feature, keep_body=False)
    show_tip(body)
