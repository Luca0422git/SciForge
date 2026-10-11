# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Combine (Modify > Combine): the document side, no Qt. The dialog (combine_ui.py)
and the golden-model builder both call build().

Options (dict, see DEFAULTS):
  target      the body that is changed (a PartDesign Body)
  tools       the bodies that change it
  operation   join | cut | intersect
  new_body    the result goes into a new body; the target is then used up like the tools
  keep_tools  the tool bodies stay in the design (else they are used up: hidden while the
              Combine is part of the design, back when it is deleted, suppressed, undone or
              rolled back)

What is built: a timeline step ("Combine", SciForgeType "Combine") in the target body, or as
the first step of a new body. It is a PartDesign::FeaturePython (CombineFeature below), so it
sits in the body's history like any PartDesign feature: later steps build on it, edits to
earlier steps (in the target or in a tool body) flow through it, and it is edited from the
timeline. It links each tool body's step that was the body's end when the Combine was made, so
steps added to a kept tool body later do not change an earlier Combine (as in Fusion).

FreeCAD's own PartDesign::Boolean was not used: it adopts the tool bodies as its children
(they then move with the target body and drop out of the design's body list).
"""
import FreeCAD as App

from . import bodies

TYPE = "PartDesign::FeaturePython"
SCIFORGE_TYPE = "Combine"
OPERATIONS = ("join", "cut", "intersect")
ENUMS = ["Join", "Cut", "Intersect"]
META = "SciForgeCombine"

DEFAULTS = {
    "target": None,
    "tools": [],
    "operation": "join",
    "new_body": False,
    "keep_tools": False,
}


class CombineError(ValueError):
    """The combine cannot be built as asked; the message says why and what to do."""


class NeedsPick(CombineError):
    """A selection box still waits for its click (the dialog shows it as a hint)."""


def with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update(options or {})
    merged["tools"] = list(merged.get("tools") or [])
    return merged


def is_combine(obj):
    return bodies.kind(obj) == SCIFORGE_TYPE


# -- the feature ---------------------------------------------------------------------------------
class CombineFeature:
    """Saved in files as "sciforge.combine.CombineFeature": keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Combine", doc)
                return True
            return False

        if add("App::PropertyEnumeration", "Operation", "Join, Cut or Intersect"):
            obj.Operation = ENUMS
            obj.Operation = "Join"
        # Global links: the tool steps sit in other bodies.
        add("App::PropertyLinkListGlobal", "Tools", "The tool bodies' steps it combines with")
        add("App::PropertyLinkGlobal", "Target", "New Body: the target body's step")
        add("App::PropertyBool", "NewBody", "The result is a new body")
        add("App::PropertyBool", "KeepTools", "The tool bodies stay in the design")
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane, like Fusion"):
            obj.Refine = True
        bodies.mark(obj, SCIFORGE_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        body = bodies.body_of(obj)
        base_obj = obj.Target if obj.NewBody else obj.BaseFeature
        if base_obj is None or base_obj.Shape.isNull() or not base_obj.Shape.Solids:
            raise CombineError(
                "There is no solid in the target body to combine with. Edit the Combine and "
                "pick the target body again."
            )
        tools = [t for t in obj.Tools if bodies.alive(t)]
        tools = [t for t in tools if not t.Shape.isNull() and t.Shape.Solids]
        if not tools:
            raise CombineError(
                "Its tool bodies are gone (deleted?). Edit the Combine and pick the tool bodies."
            )
        result = combine_shapes(
            bodies.global_shape(base_obj),
            [bodies.global_shape(t) for t in tools],
            obj.Operation.lower(),
        )
        shape = bodies.as_result(result, refine=bool(obj.Refine))
        obj.Shape = bodies.to_local(shape, body)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def combine_shapes(base, tools, operation):
    """The solids of target `base` combined with the `tools` (all in design coordinates)."""
    if operation not in OPERATIONS:
        raise CombineError("Unknown operation %r." % operation)
    try:
        if operation == "join":
            result = base.fuse(tools) if len(tools) > 1 else base.fuse(tools[0])
        elif operation == "cut":
            result = base.cut(tools) if len(tools) > 1 else base.cut(tools[0])
        else:
            result = base
            for tool in tools:  # the volume the target shares with every tool
                result = result.common(tool)
    except Exception as exc:
        raise CombineError("The bodies cannot be combined: %s" % exc)
    solids = bodies.solids_of(result)
    if not solids:
        if operation == "intersect":
            raise CombineError(
                "The bodies do not overlap, so Intersect would leave nothing. Pick tool bodies "
                "that overlap the target body."
            )
        raise CombineError("Cut would leave nothing of the target body.")
    if not result.isValid():
        try:
            result.fix(1e-7, 1e-7, 1e-7)
        except Exception:
            pass
    return solids


# -- reading and building ----------------------------------------------------------------------------
def target_body(feature):
    """The body the Combine changes (with New Body: the body it was made from)."""
    if feature.NewBody:
        return bodies.body_of(feature.Target)
    return bodies.body_of(feature)


def tool_bodies(feature):
    found = []
    for step in feature.Tools:
        body = bodies.body_of(step)
        if body is not None and body not in found:
            found.append(body)
    return found


def used_up(feature):
    """The bodies a Combine uses up while it is part of the design (bodies.CONSUMERS)."""
    found = [] if feature.KeepTools else tool_bodies(feature)
    if feature.NewBody:
        target = target_body(feature)
        if target is not None:
            found.append(target)
    return found


bodies.CONSUMERS[SCIFORGE_TYPE] = used_up


def read(feature):
    """The dialog options of an existing Combine."""
    return with_defaults(
        {
            "target": target_body(feature),
            "tools": tool_bodies(feature),
            "operation": feature.Operation.lower(),
            "new_body": bool(feature.NewBody),
            "keep_tools": bool(feature.KeepTools),
        }
    )


def check(options):
    target = options["target"]
    tools = [t for t in options["tools"] if t is not None]
    if target is None:
        raise NeedsPick("Select the target body: the body that is changed.")
    if not tools:
        raise NeedsPick("Select the tool bodies: the bodies that change the target.")
    if options["operation"] not in OPERATIONS:
        raise CombineError("Pick Join, Cut or Intersect.")
    if any(t is target for t in tools):
        raise CombineError("The target body cannot be one of its own tool bodies.")
    for body in [target] + tools:
        if not bodies.has_solid(body):
            raise CombineError("%s has no solid to combine." % body.Label)


def _tool_steps(options, feature):
    """The step of each tool body: an edited Combine keeps the step it had for a body that
    is still picked; a newly picked body comes in at its end (its Tip)."""
    had = {}
    if feature is not None and bodies.alive(feature):
        for step in feature.Tools:
            body = bodies.body_of(step)
            if body is not None:
                had[body.Name] = step
    steps = []
    for body in options["tools"]:
        step = had.get(body.Name) or body.Tip
        if step is not None and step not in steps:
            steps.append(step)
    return steps


def _structure_ok(feature, options):
    if feature is None or not bodies.alive(feature):
        return False
    if bool(feature.NewBody) != bool(options["new_body"]):
        return False
    return target_body(feature) is options["target"]


def build(options, feature=None, name="Combine"):
    """Create the Combine, or update `feature` (a different object when the change needs a
    new structure: New Body switched, or another target body). Returns the feature."""
    options = with_defaults(options)
    check(options)
    target = options["target"]
    steps = _tool_steps(options, feature)
    if not _structure_ok(feature, options):
        label = None
        if feature is not None and bodies.alive(feature):
            label = feature.Label
            remove(feature)
        feature = _create(options, name)
        if label:
            feature.Label = label
    _set(feature, "Operation", options["operation"].capitalize())
    if list(feature.Tools) != steps:
        feature.Tools = steps
    _set(feature, "KeepTools", bool(options["keep_tools"]))
    _set(feature, "NewBody", bool(options["new_body"]))
    if options["new_body"]:
        if feature.Target is None or bodies.body_of(feature.Target) is not target:
            feature.Target = target.Tip
    elif feature.Target is not None:
        feature.Target = None
    return feature


def _set(obj, prop, value):
    if getattr(obj, prop) != value:
        setattr(obj, prop, value)


def _create(options, name):
    target = options["target"]
    doc = target.Document
    if options["new_body"]:
        body = bodies.new_body(doc, like=target)
        made_body = body
        try:  # the result is made of what the target was made of, and looks like it
            body.ShapeMaterial = target.ShapeMaterial
            from . import appearance

            appearance.copy_body_appearance(target, body)
        except Exception:
            pass
    else:
        body = target
        made_body = None
    obj = bodies.insert_after_tip(body, TYPE, name)
    CombineFeature(obj)
    if made_body is not None:
        bodies.save_meta(obj, META, {"created_body": made_body.Name})
    _attach_view_provider(obj)
    return obj


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .bodies_gui import StepViewProvider

        StepViewProvider(obj.ViewObject)
    except Exception:
        pass


def created_body(feature):
    """The body a New Body Combine made (None for one inside its target body)."""
    meta = bodies.load_meta(feature, META)
    name = meta.get("created_body")
    body = feature.Document.getObject(name) if name else None
    if body is not None and feature in body.Group:
        return body
    return None


def remove(feature):
    """Take a Combine out again (a cancelled preview, or a rebuild with a new structure)."""
    if not bodies.alive(feature):
        return
    made = created_body(feature)
    if made is not None:
        bodies.remove_body(made)
        return
    bodies.remove_step(feature)
