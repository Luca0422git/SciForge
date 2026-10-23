# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Flange as a SciForge step (document side, no Qt): the dialog
(sheetmetal_flange_ui.py), the golden-model builder (ai/ops/sheetmetal_ops.py) and the AI
tools all call make() / update().

A flange is one ``PartDesign::FeaturePython`` (FlangeFeature, timeline type
"SciForge::Flange") in a sheet metal body's history (sheetmetal.py: a body with a rule):

- Base flange: closed sketch profiles -> a plate of the rule's thickness. New Body (default),
  New Component (a Sheet Metal component with that rule active) or Join (a plate added to a
  sheet metal body, in that body's rule).
- Contour flange: an open chain of sketch lines and arcs -> a bent strip, every sharp corner
  bent with the rule's radius.
- Edge flange: edges of a sheet metal body -> a bend and a wall on each, with the Height
  Datum, Bend Position, Angle, Flip, width types, bend reliefs, mitred corners and the rule
  overrides of Fusion's dialog (geometry in sheetmetal_form.py).

Every computation reads the body's rule (sheetmetal.rule_for_body) when the step runs, so
editing the rule recomputes every flange that follows it.
"""

import FreeCAD as App

from . import bodies, curves, log, sheetmetal, warn
from . import sheetmetal_core as core
from . import sheetmetal_form as form
from .sheetmetal_form import FormError

TYPE = "PartDesign::FeaturePython"
SCIFORGE_TYPE = "Flange"
KINDS = ("base", "contour", "edge")
OPERATIONS = ("new_body", "new_component", "join")

# option value <-> the enumeration text the property shows (Fusion's words)
LABELS = {
    "kind": {"base": "Base", "contour": "Contour", "edge": "Edge"},
    "orientation": {"side1": "Side 1", "side2": "Side 2", "centered": "Centered"},
    "direction": {"one_side": "One Side", "symmetric": "Symmetric", "two_sides": "Two Sides"},
    "extent": {"distance": "Distance", "to_object": "To Object"},
    "datum": {"inner": "Inner Faces", "outer": "Outer Faces", "tangent": "Tangent To Bend"},
    "position": {
        "inside": "Inside",
        "outside": "Outside",
        "adjacent": "Adjacent",
        "tangent": "Tangent",
    },
    "width_type": {
        "full": "Full Edge",
        "symmetric": "Symmetric",
        "two_sides": "Two Sides",
        "two_offsets": "Two Offsets",
    },
    "relief_shape": {"straight": "Straight", "tear": "Tear", "round": "Round"},
    "corner_shape": {
        "round": "Round",
        "square": "Square",
        "tear": "Tear",
        "trim_to_bend": "Trim To Bend",
        "linear_weld": "Linear Weld",
        "arc_weld": "Arc Weld",
        "laser_weld": "Laser Weld",
    },
    "corner_placement": {"intersection": "Intersection", "tangent": "Tangent"},
    "corner3_shape": {
        "no_replacement": "No Replacement",
        "intersection": "Intersection",
        "full_round": "Full Round",
        "round_with_radius": "Round With Radius",
    },
}
# option -> (property, property type, group, tooltip)
ENUMS = {
    "kind": ("FlangeType", "Flange"),
    "orientation": ("Orientation", "Flange"),
    "direction": ("Direction", "Flange"),
    "extent": ("HeightExtent", "Flange"),
    "datum": ("HeightDatum", "Flange"),
    "position": ("BendPosition", "Flange"),
    "width_type": ("WidthType", "Flange"),
    "relief_shape": ("ReliefShape", "Overrides"),
    "corner_shape": ("CornerReliefShape", "Overrides"),
    "corner_placement": ("CornerReliefPlacement", "Overrides"),
    "corner3_shape": ("Corner3ReliefShape", "Overrides"),
}
LENGTHS = {
    "height": ("Height", "Flange", 10.0),
    "distance": ("Distance", "Flange", 10.0),
    "distance2": ("Distance2", "Flange", 10.0),
    "width": ("Width", "Flange", 10.0),
    "distance1": ("Width1", "Flange", 5.0),
    "width2": ("Width2", "Flange", 5.0),
    "target_offset": ("TargetOffset", "Flange", 0.0),
    "bend_radius": ("BendRadius", "Overrides", 1.0),
    "relief_width": ("ReliefWidth", "Overrides", 1.0),
    "relief_depth": ("ReliefDepth", "Overrides", 0.5),
    "relief_remnant": ("ReliefRemnant", "Overrides", 2.0),
    "corner_size": ("CornerReliefSize", "Overrides", 4.0),
    "corner3_radius": ("Corner3ReliefRadius", "Overrides", 4.0),
}
BOOLS = {
    "flip": ("Flip", "Flange"),
    "override_bend_radius": ("OverrideBendRadius", "Overrides"),
    "override_bend_relief": ("OverrideBendRelief", "Overrides"),
    "override_corner_relief": ("OverrideCornerRelief", "Overrides"),
    "override_corner3_relief": ("OverrideCorner3Relief", "Overrides"),
}

DEFAULTS = {
    "kind": "base",
    "orientation": "side1",
    "direction": "one_side",
    "distance": 10.0,
    "distance2": 10.0,
    "flip": False,
    "extent": "distance",
    "height": 10.0,
    "datum": "inner",
    "position": "inside",
    "angle": 90.0,
    "width_type": "full",
    "width": 10.0,
    "distance1": 5.0,
    "width2": 5.0,
    "target_offset": 0.0,
    "override_bend_radius": False,
    "bend_radius": 1.0,
    "override_bend_relief": False,
    "relief_shape": "round",
    "relief_width": 1.0,
    "relief_depth": 0.5,
    "relief_remnant": 2.0,
    "override_corner_relief": False,
    "corner_shape": "round",
    "corner_placement": "intersection",
    "corner_size": 4.0,
    "override_corner3_relief": False,
    "corner3_shape": "round_with_radius",
    "corner3_radius": 4.0,
}


def defaults(kind="base", rule=None):
    """The dialog's starting options; override values start at the rule's (lengths in mm)."""
    out = dict(DEFAULTS, kind=kind)
    if rule is not None:
        out["bend_radius"] = rule["bend_radius"]
        out["relief_shape"] = rule["bend_relief_shape"]
        out["relief_width"] = rule["bend_relief_width"]
        out["relief_depth"] = rule["bend_relief_depth"]
        out["relief_remnant"] = rule["bend_relief_remnant"]
        out["corner_shape"] = rule["corner_relief_2bend_shape"]
        out["corner_placement"] = rule["corner_relief_2bend_placement"]
        out["corner_size"] = rule["corner_relief_2bend_size"]
        out["corner3_shape"] = rule["corner_relief_3bend_shape"]
        out["corner3_radius"] = rule["corner_relief_3bend_radius"]
    return out


def check_options(options):
    """Raise FormError for a choice that is not one of Fusion's."""
    for key, labels in LABELS.items():
        if key in options and options[key] not in labels:
            raise FormError("%s must be one of %s" % (key, ", ".join(labels)))


def is_flange(obj):
    return obj is not None and bodies.kind(obj) == SCIFORGE_TYPE and obj.TypeId == TYPE


class FlangeFeature:
    """SciForge's Flange step. Saved documents store "sciforge.sheetmetal_flange.
    FlangeFeature": never rename the module or the class."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(prop_type, name, group, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(prop_type, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSubListGlobal", "Profiles", "Flange", "Sketch profiles or curves")
        add("App::PropertyLinkSubList", "Edges", "Flange", "Edges of the sheet metal body")
        add("App::PropertyLinkSubGlobal", "Target", "Flange", "To Object: face or plane")
        for key, (prop, group) in ENUMS.items():
            if add("App::PropertyEnumeration", prop, group, key):
                setattr(obj, prop, list(LABELS[key].values()))
                setattr(obj, prop, LABELS[key][DEFAULTS[key]])
        for key, (prop, group, value) in LENGTHS.items():
            if add("App::PropertyLength", prop, group, key):
                setattr(obj, prop, value)
        if add("App::PropertyAngle", "Angle", "Flange", "Bend angle"):
            obj.Angle = 90.0
        for key, (prop, group) in BOOLS.items():
            add("App::PropertyBool", prop, group, key)
        if add("App::PropertyBool", "Refine", "Base", "Merge coplanar faces, like Fusion"):
            obj.Refine = True
        bodies.mark(obj, SCIFORGE_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            shape = compute(obj)
        except Exception:
            bodies.pass_through(obj)
            raise
        obj.Shape = shape

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _value(obj, key):
    prop = LENGTHS[key][0]
    return float(getattr(obj, prop).Value)


def options_of(obj):
    """The options dict of a flange step (the same keys the dialog and golden steps use)."""
    out = {}
    for key, (prop, _group) in ENUMS.items():
        text = getattr(obj, prop, None)
        reverse = {v: k for k, v in LABELS[key].items()}
        out[key] = reverse.get(text, DEFAULTS[key])
    for key in LENGTHS:
        out[key] = _value(obj, key)
    out["angle"] = float(obj.Angle.Value)
    for key, (prop, _group) in BOOLS.items():
        out[key] = bool(getattr(obj, prop, False))
    return out


def apply_options(obj, options):
    """Write options into the step's properties (only what changed)."""
    check_options(options)
    for key, (prop, _group) in ENUMS.items():
        if key in options:
            text = LABELS[key][options[key]]
            if getattr(obj, prop) != text:
                setattr(obj, prop, text)
    for key, (prop, _group, _default) in LENGTHS.items():
        if key in options and options[key] is not None:
            value = float(options[key])
            if abs(getattr(obj, prop).Value - value) > 1e-12:
                setattr(obj, prop, value)
    if "angle" in options and abs(obj.Angle.Value - float(options["angle"])) > 1e-12:
        obj.Angle = float(options["angle"])
    for key, (prop, _group) in BOOLS.items():
        if key in options and bool(getattr(obj, prop)) != bool(options[key]):
            setattr(obj, prop, bool(options[key]))


def form_options(options):
    """The edge flange options sheetmetal_form wants (overrides None when not ticked)."""
    out = {
        "height": options["height"],
        "extent": options["extent"],
        "datum": options["datum"],
        "position": options["position"],
        "angle": options["angle"],
        "flip": options["flip"],
        "width_type": options["width_type"],
        "width": options["width"],
        "distance1": options["distance1"],
        "distance2": options["width2"],
        "target_offset": options["target_offset"],
    }
    if options.get("override_bend_radius"):
        out["bend_radius"] = options["bend_radius"]
    if options.get("override_bend_relief"):
        out["relief_shape"] = options["relief_shape"]
        out["relief_width"] = options["relief_width"]
        out["relief_depth"] = options["relief_depth"]
        out["relief_remnant"] = options["relief_remnant"]
    return out


def owner_body(obj):
    return curves.owner_body(obj)


def _sketch_plane(sketch):
    place = sketch.getGlobalPlacement()
    rot = place.Rotation
    return form.Plane2D(
        place.Base, rot.multVec(App.Vector(1, 0, 0)), rot.multVec(App.Vector(0, 1, 0))
    )


def _profile_faces(refs):
    from . import extrude

    faces, normal = [], None
    for sketch, sub in refs:
        found = dict(extrude.regions(sketch))
        if sub not in found:
            raise FormError("A profile of %s is gone: pick the profile again." % sketch.Label)
        faces.append(found[sub])
        if normal is None:
            normal = _sketch_plane(sketch).n
    return faces, normal


def _links(value):
    found = []
    for linked, subs in value or []:
        if linked is None:
            continue
        for sub in subs or [""]:
            found.append((linked, sub))
    return found


def _target_plane(obj):
    """(point, normal) in design coordinates of the To Object pick, or None."""
    target = obj.Target
    if not target:
        return None
    linked, subs = target[0], list(target[1]) if len(target) > 1 else []
    sub = subs[0] if subs else ""
    if sub:
        face = linked.Shape.getElement(sub)
        face = curves.to_global(face, linked)
        face = bodies.baked(face)
        if face.ShapeType != "Face":
            raise FormError("To Object: pick a flat face or a plane.")
        u0, u1, v0, v1 = face.ParameterRange
        u, v = (u0 + u1) / 2.0, (v0 + v1) / 2.0
        return face.valueAt(u, v), face.normalAt(u, v)
    place = linked.getGlobalPlacement()
    return place.Base, place.Rotation.multVec(App.Vector(0, 0, 1))


def compute(obj):
    """The step's solid in its body's own coordinates."""
    body = owner_body(obj)
    if body is None:
        raise FormError("A flange must be in a body.")
    rule = sheetmetal.rule_for_body(body)
    options = options_of(obj)
    base_feature = obj.BaseFeature
    base = None
    if base_feature is not None and not base_feature.Shape.isNull() and base_feature.Shape.Solids:
        base = bodies.baked(curves.to_global(base_feature.Shape, base_feature))
    kind = options["kind"]
    if kind == "edge":
        names = [sub for _o, sub in _links(obj.Edges)]
        if base is None:
            raise FormError("An edge flange needs a sheet metal body: make a base flange first.")
        opts = form_options(options)
        if options["extent"] == "to_object":
            opts["target"] = _target_plane(obj)
        result = form.edge_flange(base, names, rule, opts)
    else:
        refs = _links(obj.Profiles)
        if not refs:
            raise FormError("Pick a sketch profile for the flange.")
        if kind == "base":
            faces, normal = _profile_faces(refs)
            result = form.base_flange(faces, normal, rule["thickness"], options["orientation"])
        else:
            edges = curves.refs_edges(refs)
            plane = _sketch_plane(refs[0][0])
            radius = rule["bend_radius"]
            if options["override_bend_radius"]:
                radius = options["bend_radius"]
            result = form.contour_flange(
                edges,
                plane,
                rule["thickness"],
                radius,
                options["distance"],
                options["orientation"],
                options["direction"],
                options["distance2"],
                options["flip"],
            )
        if base is not None:
            result = base.fuse(result)
            result = form._clean(result)
    if result.isNull() or not result.Solids:
        raise FormError("The flange made no solid.")
    return bodies.to_local(result, body)


# -- making and editing -------------------------------------------------------------------------
def _attach_view_provider(step):
    if not App.GuiUp:
        return
    try:
        from .sheetmetal_flange_ui import ViewProviderFlange

        ViewProviderFlange(step.ViewObject)
    except Exception as exc:
        warn("flange view: %s" % exc)


def new_sheet_body(doc, rule_name, operation="new_body", component=None):
    """A new sheet metal body following rule_name, in `component` (None: the active one when
    the GUI runs, else the root), or in a new Sheet Metal component (New Component)."""
    from . import components

    if component is None and App.GuiUp:
        component = components.active_component(doc)
    if operation == "new_component":
        component = components.new_component(doc, parent=component)
        sheetmetal.set_active_rule(doc, rule_name, component)
        mark_sheet_metal_component(component)
    body = components.new_body_in(doc, component)
    sheetmetal.make_sheet_metal_body(body, rule_name)
    return body


def mark_sheet_metal_component(component):
    """Fusion's component Type: Sheet Metal (one way: a sheet metal component stays one)."""
    if "SciForgeComponentKind" not in component.PropertiesList:
        component.addProperty(
            "App::PropertyString", "SciForgeComponentKind", "SheetMetal", "Standard or SheetMetal"
        )
    component.SciForgeComponentKind = "SheetMetal"


def is_sheet_metal_component(component):
    return getattr(component, "SciForgeComponentKind", "") == "SheetMetal"


def default_rule_name(doc, component=None):
    """The rule a new flange starts with: the component's active rule (Fusion)."""
    return sheetmetal.active_rule_name(doc, component)


def _set_refs(step, kind, refs, target=None):
    if kind == "edge":
        grouped = {}
        for obj, sub in refs:
            grouped.setdefault(obj.Name, (obj, []))[1].append(sub)
        step.Edges = [(obj, subs) for obj, subs in grouped.values()]
        step.Profiles = []
    else:
        grouped = {}
        for obj, sub in refs:
            grouped.setdefault(obj.Name, (obj, []))[1].append(sub)
        step.Profiles = [(obj, subs) for obj, subs in grouped.values()]
        step.Edges = []
    if target:
        step.Target = (target[0], [target[1]] if target[1] else [])
    else:
        step.Target = None


def make(
    doc,
    kind,
    refs,
    options=None,
    rule_name=None,
    operation="new_body",
    body=None,
    name=None,
    target=None,
):
    """Make a flange step. kind: base / contour / edge. refs: [(sketch, "InternalFaceN")]
    (base), [(sketch, "EdgeN")] (contour) or [(feature, "EdgeN")] (edge, the body's last
    step). operation (base/contour): new_body, new_component or join (into `body`, a sheet
    metal body). Returns the step; raises FormError with the reason (nothing is left behind)."""
    if kind not in KINDS:
        raise FormError("kind must be base, contour or edge")
    opts = dict(DEFAULTS)
    opts.update(options or {})
    opts["kind"] = kind
    check_options(opts)
    made_body = None
    marked = None
    if kind == "edge":
        body = owner_body(refs[0][0]) if refs else body
        if body is None or not sheetmetal.is_sheet_metal_body(body):
            raise FormError(
                "An edge flange goes on a sheet metal body: pick an edge of one (make it with a "
                "base flange first)."
            )
    elif operation == "join":
        if body is None or not sheetmetal.is_sheet_metal_body(body):
            raise FormError("Join adds the flange to a sheet metal body: pick or make one first.")
    else:
        rule_name = rule_name or default_rule_name(doc)
        if sheetmetal.find_rule(doc, rule_name) is None and core.library_rule(rule_name) is None:
            raise FormError("There is no sheet metal rule named '%s'." % rule_name)
        host = owner_body(refs[0][0]) if refs else None
        if operation == "new_body" and host is not None and _empty(host):
            # the sketch's own body has no solid yet (Create Sketch made it): it becomes the
            # sheet metal body, as an Extrude's first solid goes into the sketch's body
            sheetmetal.make_sheet_metal_body(host, rule_name)
            body = host
            marked = host
        else:
            made_body = new_sheet_body(doc, rule_name, operation)
            body = made_body
    step = bodies.insert_after_tip(body, TYPE, name or "Flange")
    FlangeFeature(step)
    _attach_view_provider(step)
    try:
        _set_refs(step, kind, refs, target)
        apply_options(step, opts)
        doc.recompute()
        problem = problem_of(step)
        if problem:
            raise FormError(problem)
    except Exception:
        _undo_make(step, made_body)
        if marked is not None:
            setattr(marked, sheetmetal.RULE_PROP, "")
        raise
    hide_sketches(refs if kind != "edge" else [])
    log("flange (%s) %s made in %s" % (kind, step.Name, body.Label))
    return step


def _empty(body):
    """True when a body has no solid step yet (only sketches / planes)."""
    for obj in bodies.solid_steps(body):
        if not obj.Shape.isNull():
            return False
    return True


def _undo_make(step, made_body):
    try:
        if made_body is not None:
            from . import components

            container = components.container_of(made_body)
            bodies.remove_body(made_body)
            if container is not None:
                components.drop_if_empty(container)
        else:
            bodies.remove_step(step)
    except Exception as exc:
        warn("could not take the failed flange away: %s" % exc)


def problem_of(step):
    """The reason a step did not compute, or ""."""
    try:
        state = list(step.State)
    except Exception:
        state = []
    if "Invalid" in state or "Error" in state:
        try:
            compute(step)
        except Exception as exc:
            return str(exc)
        return "The flange could not be computed."
    return ""


def update(step, refs=None, options=None, target=None):
    """Change a flange's picks and/or options (the caller recomputes)."""
    opts = options_of(step)
    opts.update(options or {})
    kind = opts["kind"]
    if refs is not None:
        _set_refs(step, kind, refs, target)
    elif target is not None:
        step.Target = (target[0], [target[1]] if target[1] else [])
    apply_options(step, opts)


def hide_sketches(refs):
    if not App.GuiUp:
        return
    for obj, _sub in refs:
        if curves.is_sketch(obj):
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass


def picks_of(step):
    """[(object, sub)] of the step's profiles or edges."""
    if options_of(step)["kind"] == "edge":
        return _links(step.Edges)
    return _links(step.Profiles)


def thickness_of(body):
    """The rule thickness of a sheet metal body (mm), or None."""
    try:
        return sheetmetal.rule_for_body(body)["thickness"]
    except Exception:
        return None


__all__ = [
    "FlangeFeature",
    "FormError",
    "make",
    "update",
    "options_of",
    "defaults",
    "core",
]
