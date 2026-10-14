# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rectangular / Circular Pattern and Pattern on Path with Pattern Type "Components" (Fusion's
pattern of components): the document side, no Qt. The dialog is pattern_ui's (the pattern
type drop-down); pattern.build / check / read / remove hand components over to this module.

Fusion repeats the component: every copy is an occurrence of it ("Bracket:2", ":3" ...),
so a change to the component shows in every copy, and the pattern is one step in the
timeline that can be edited, suppressed, rolled back and deleted (its copies go with it).

On FreeCAD: one ``ComponentPattern`` step (an ``App::FeaturePython`` outside the bodies,
SciForgeType RectangularPattern / CircularPattern / PatternOnPath like the other patterns,
plus "SciForgeRolls" so it rolls back with the marker) keeps the dialog's choices and works
out each copy's movement in design coordinates (``Moves``); each copy is an instance
(instances.make_instance with ``pattern``) whose copy bodies take the original's solids
moved by their ``Moves`` entry. The references (directions, axis, path) may be anywhere:
each is taken in the frame of the body or component it belongs to.
"""

import FreeCAD as App

from . import bodies, components, instances, log, pattern, warn
from . import pattern_core as core
from .pattern_core import PatternError

OBJECT = "App::FeaturePython"
PROPS = pattern.BODY_PROPS
ENUM_PROPS = pattern.BODY_ENUMS


def is_component_pattern(obj):
    return (
        obj is not None
        and pattern.kind_of(obj) is not None
        and isinstance(getattr(obj, "Proxy", None), ComponentPatternFeature)
    )


def source_of(feature):
    try:
        source = feature.Source
    except Exception:
        return None
    return source if components.alive(source) else None


def copies(feature):
    """The instance parts a pattern made, in order."""
    from . import timeline_ops

    found = timeline_ops._pattern_parts(feature.Document, feature)
    return sorted(found, key=lambda p: int(getattr(p, instances.INDEX, 0) or 0))


# -- references in design coordinates ------------------------------------------------------------
def frame_of(obj):
    """The global placement of the frame pattern.direction_of / axis_of / path_edges give
    their coordinates in for `obj`: the body or component it (or its origin) belongs to."""
    owner = components.origin_owner(obj)
    if owner is None:
        try:
            owner = obj.getParentGeoFeatureGroup()
        except Exception:
            owner = None
    if owner is None:
        return App.Placement()
    try:
        return owner.getGlobalPlacement()
    except Exception:
        return App.Placement(owner.Placement)


def global_direction(ref):
    point, direction = pattern.direction_of(ref)
    frame = frame_of(ref[0])
    return frame.multVec(point), frame.Rotation.multVec(direction)


def global_axis(ref):
    point, axis = pattern.axis_of(ref)
    frame = frame_of(ref[0])
    return frame.multVec(point), frame.Rotation.multVec(axis)


def source_center(source):
    shapes = []
    for body in components.bodies_in(source.Document, source, recursive=True):
        try:
            if bodies.has_solid(body):
                shapes.append(bodies.global_shape(body))
        except Exception:
            continue
    if not shapes:
        return App.Vector()
    box = shapes[0].BoundBox
    for shape in shapes[1:]:
        box.add(shape.BoundBox)
    return box.Center


def all_moves(kind, options, source):
    """Every copy's movement in design coordinates, suppressed copies included."""
    core.check_total(pattern.total_instances(kind, options))
    if kind == "rectangular":
        _p, u1 = global_direction(options["direction"])
        offsets1 = core.linear_offsets(
            options["quantity"],
            options["distance"],
            options["distribution"],
            options["direction_type"],
        )
        offsets2 = [0.0]
        u2 = App.Vector()
        if options["direction2"] is not None:
            _p, u2 = global_direction(options["direction2"])
            offsets2 = core.linear_offsets(
                options["quantity2"],
                options["distance2"],
                options["distribution"],
                options["direction_type2"],
            )
        return [
            App.Placement(u1 * a + u2 * b, App.Rotation())
            for a, b in core.grid(offsets1, offsets2)[1:]
        ]
    if kind == "circular":
        point, axis = global_axis(options["axis"])
        angles = core.circular_angles(
            options["quantity"], options["angle"], options["circular_type"]
        )
        return [App.Placement(App.Vector(), App.Rotation(axis, a), point) for a in angles[1:]]
    if kind == "path":
        frame = frame_of(options["path"][0])
        center = frame.inverse().multVec(source_center(source))
        local = pattern.path_placements(options, None, center)
        return [frame.multiply(m).multiply(frame.inverse()) for m in local]
    raise PatternError("A pattern of components can be rectangular, circular or on a path.")


def moves(kind, options, source):
    skip = set(options.get("suppressed") or [])
    return [m for i, m in enumerate(all_moves(kind, options, source)) if i not in skip]


# -- the step -------------------------------------------------------------------------------
class ComponentPatternFeature:
    """A pattern of components. Saved as "sciforge.component_pattern.ComponentPatternFeature":
    keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Pattern", doc)
                return True
            return False

        for prop, _key in ENUM_PROPS:
            if add("App::PropertyEnumeration", prop, "Dialog choice (Fusion's field)"):
                setattr(obj, prop, pattern.ENUMS[prop])
        add("App::PropertyLinkGlobal", "Source", "The component that is repeated")
        for prop, _key, _kinds in PROPS:
            add("App::PropertyLinkSubGlobal", prop, prop)
        if add("App::PropertyInteger", "Quantity", "Instances (the original included)"):
            obj.Quantity = 2
        if add("App::PropertyInteger", "Quantity2", "Instances in direction 2"):
            obj.Quantity2 = 1
        add("App::PropertyDistance", "Distance", "Distance (extent or spacing)")
        add("App::PropertyDistance", "Distance2", "Distance in direction 2")
        if add("App::PropertyAngle", "Angle", "Total angle of a circular pattern"):
            obj.Angle = 360.0
        add("App::PropertyIntegerList", "SuppressedCopies", "Copies left out (Suppression)")
        if "Moves" not in obj.PropertiesList:
            # each copy's movement, design coordinates (worked out here, read by the copies)
            obj.addProperty("App::PropertyPlacementList", "Moves", "Pattern", "", 4)
        bodies.add_prop(obj, "App::PropertyBool", "SciForgeRolls", "Base")
        obj.SciForgeRolls = True

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        source = source_of(obj)
        if source is None:
            raise PatternError(
                "The component it repeated was deleted; its copies stay as they are. Delete "
                "this step, or undo the delete."
            )
        kind = pattern.kind_of(obj)
        found = moves(kind, read(obj), source)
        current = list(obj.Moves)
        if len(current) != len(found) or any(
            not a.isSame(b, 1e-12) for a, b in zip(current, found)
        ):
            obj.Moves = found

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def read(obj):
    """The dialog options of a pattern of components."""
    options = pattern.with_defaults({})
    options["pattern_type"] = "components"
    for prop, key in ENUM_PROPS:
        options[key] = pattern._enum_get(obj, prop)
    for prop, key, _kinds in PROPS:
        link = getattr(obj, prop)
        options[key] = (link[0], (list(link[1]) or [""])[0]) if link else None
    options["quantity"] = int(obj.Quantity)
    options["quantity2"] = int(obj.Quantity2)
    options["distance"] = obj.Distance.Value
    options["distance2"] = obj.Distance2.Value
    options["angle"] = obj.Angle.Value
    options["suppressed"] = list(getattr(obj, "SuppressedCopies", []) or [])
    source = source_of(obj)
    options["objects"] = [(source, "")] if source is not None else []
    meta = pattern.load_meta(obj)
    options["expressions"] = dict(meta.get("expressions") or {})
    return options


def _components(options):
    return [obj for obj, sub in options.get("objects") or [] if components.is_component(obj)]


def check(kind, options):
    """Raise pattern.NeedsPick / PatternError when the pattern cannot be built yet (the
    references are checked by pattern.check)."""
    if kind == "mirror":
        raise PatternError("Mirror of components is not built yet: use a body or features.")
    found = _components(options)
    if not found:
        raise pattern.NeedsPick("Select the component to pattern.")
    if len(found) > 1:
        raise PatternError("Select one component: each component gets its own pattern.")
    source = found[0]
    if instances.is_instance(source):
        raise PatternError(
            "%s is a copy of %s: pattern the original component."
            % (source.Label, (instances.source_of(source) or source).Label)
        )
    if pattern.quantity_formulas(options):
        raise PatternError("A pattern of components takes a plain number as its quantity.")
    if not instances.source_bodies(source):
        raise PatternError("%s has no body to repeat yet." % source.Label)


def build(kind, options, feature=None, name=None):
    """Create the pattern of components, or update `feature`. Returns the step."""
    options = pattern.with_defaults(options)
    check(kind, options)
    source = _components(options)[0]
    doc = source.Document
    if feature is not None and not (
        is_component_pattern(feature) and pattern.kind_of(feature) == kind
    ):
        label = feature.Label if pattern.alive(feature) else None
        if pattern.alive(feature):
            pattern.remove(feature)
        feature = None
    else:
        label = None
    if feature is None or not pattern.alive(feature):
        feature = doc.addObject(OBJECT, name or pattern.TITLES[kind].replace(" ", ""))
        ComponentPatternFeature(feature)
        pattern._mark(feature, kind)
        if label:
            feature.Label = label
        if App.GuiUp:
            try:
                from .pattern_ui import ViewProviderPattern

                ViewProviderPattern(feature.ViewObject)
            except Exception:
                pass
        try:
            from . import timeline_ops

            timeline_ops.place_root_step(feature)
        except Exception as exc:
            warn("pattern step: %s" % exc)
    _set_props(feature, kind, options, source)
    pattern._save_meta(
        feature,
        {
            "v": 1,
            "kind": kind,
            "pattern_type": "components",
            "expressions": {k: v for k, v in options["expressions"].items() if v},
        },
    )
    count = len(moves(kind, options, source))
    made = copies(feature)
    for part in made[count:]:
        components.remove(doc, part, _top=False)
    for index in range(len(made), count):
        instances.make_instance(source, pattern=feature, index=index)
    log("%s of %s: %d copies" % (pattern.TITLES[kind], source.Label, count))
    return feature


def _set_props(obj, kind, options, source):
    if obj.Source is not source:
        obj.Source = source
    for prop, key, kinds in PROPS:
        pattern._set_link(obj, prop, options[key] if kind in kinds else None)
    for prop, key in ENUM_PROPS:
        pattern._enum_set(obj, prop, options[key])
    pattern._set(obj, "Quantity", max(1, int(options["quantity"])))
    pattern._set(obj, "Quantity2", max(1, int(options["quantity2"])))
    for prop, key in (("Distance", "distance"), ("Distance2", "distance2"), ("Angle", "angle")):
        pattern._set(obj, prop, float(options[key]))
        pattern._expr(obj, prop, pattern._formula(options, key, obj.Document))
    pattern._set_suppressed(obj, options)


def remove(feature):
    """Take a pattern of components out again with its copies."""
    if not pattern.alive(feature):
        return
    doc = feature.Document
    for part in copies(feature):
        components.remove(doc, part, _top=False)
    try:
        doc.removeObject(feature.Name)
    except Exception:
        pass
