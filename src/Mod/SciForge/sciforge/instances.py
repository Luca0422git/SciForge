# SPDX-License-Identifier: LGPL-2.1-or-later
"""Linked instances of a component and independent copies (Fusion's Copy / Paste / Paste New,
the copies of Move's Create Copy and of a pattern of components). No Qt.

Fusion: "Copy, then Paste: the new component is linked to the original component as an
identical duplicate" (editing one changes all; the browser names them "Bracket:1",
"Bracket:2"); Paste New makes an independent component with its own features.

How an instance is built on FreeCAD (so every other SciForge tool sees an ordinary component:
the browser, joints, export, measure, drawings, interference):

- An instance is an ``App::Part`` (a component) with ``SciForgeInstanceOf`` linking the
  component it repeats (its *source*), labelled "<source>:<n>". It carries its own
  Placement: it is moved like any component.
- For every body of the source (nested components' bodies too) it holds a *copy body*
  whose first step is an ``InstanceCopy`` feature (inside the instance part, hidden from
  the timeline) that copies the source body's solid. So a change to the source (a new
  fillet, a changed extrude, a moved source body) shows in every instance at the next
  recompute, and the instance cannot be edited on its own (Fusion edits the component,
  i.e. all its occurrences: activating an instance activates its source).
- A pattern of components (component_pattern.py) makes instances whose copies are placed
  by the pattern (``Pattern`` + ``Index`` on the copy feature): they follow the pattern
  step's movements instead of their own Placement.
- ``sync(doc)`` adds a copy body when the source gets a new body and removes copies whose
  source body is gone; the labels follow the source's name. It runs after recomputes (a
  watch installed by the workbench) and after every instance operation.

Paste New copies the source component with every object in it (``doc.copyObject``): an
independent component named "<source> (1)".
"""

import FreeCAD as App

from . import bodies, components, log, warn
from . import components_core as core

INSTANCE_OF = "SciForgeInstanceOf"  # on an instance part: the component it repeats
PATTERN = "SciForgePattern"  # on a pattern's instance part: the pattern step
INDEX = "SciForgeIndex"  # which copy of the pattern (0 = the first copy)
COPY_TYPE = "InstanceCopy"
COPY_OBJECT = "Part::FeaturePython"


# -- reading ---------------------------------------------------------------------------------------
def _link(obj, prop):
    try:
        value = getattr(obj, prop, None)
    except Exception:
        return None
    return value if components.alive(value) else None


def is_instance(part):
    """True for an instance part (Paste, Create Copy or a pattern's copy)."""
    return components.is_component(part) and INSTANCE_OF in getattr(part, "PropertiesList", [])


def source_of(part):
    """The component an instance repeats (an instance of an instance: the first source);
    None when the source was deleted or `part` is no instance."""
    seen = 0
    current = part
    while is_instance(current) and seen < 20:
        seen += 1
        nxt = _link(current, INSTANCE_OF)
        if nxt is None:
            return None
        current = nxt
    return current if current is not part else None


def definition(part):
    """The component that holds the real features for `part`: its source for an instance,
    else the part itself."""
    if is_instance(part):
        return source_of(part)
    return part if components.is_component(part) else None


def instances_of(source):
    """Every instance of a component, in the order they were made."""
    if source is None:
        return []
    doc = source.Document
    found = [o for o in doc.Objects if is_instance(o) and source_of(o) is source]
    return sorted(found, key=lambda o: o.ID)


def has_instances(part):
    return bool(instances_of(part)) if components.is_component(part) else False


def pattern_of(part):
    return _link(part, PATTERN) if is_instance(part) else None


def number(part):
    """The occurrence number shown after the colon (the source is 1)."""
    if not is_instance(part):
        return 1
    return core.split_instance_label(part.Label)[1] or 0


def is_copy_feature(obj):
    return bodies.kind(obj) == COPY_TYPE and isinstance(getattr(obj, "Proxy", None), InstanceCopy)


def copy_features(part):
    """The copy features of an instance part, with their bodies: [(feature, body)]."""
    found = []
    for obj in list(getattr(part, "Group", [])):
        if is_copy_feature(obj):
            found.append((obj, copy_body(obj)))
    return found


def copy_body(feature):
    for obj in feature.InList:
        if bodies.is_body(obj) and obj.BaseFeature is feature:
            return obj
    return None


def source_body(body):
    """The source body a copy body repeats (None for an ordinary body)."""
    base = getattr(body, "BaseFeature", None) if bodies.is_body(body) else None
    if base is not None and is_copy_feature(base):
        return _link(base, "Source")
    return None


def is_copy_body(body):
    base = getattr(body, "BaseFeature", None) if bodies.is_body(body) else None
    return base is not None and is_copy_feature(base)


def source_bodies(source):
    """The bodies an instance repeats: every body in the source component, nested ones
    included (Fusion shows the nested occurrences; SciForge flattens them into the
    instance), that is not itself a copy."""
    if source is None:
        return []
    doc = source.Document
    found = components.bodies_in(doc, source, recursive=True)
    return [b for b in found if not is_copy_body(b)]


# -- the copy feature ------------------------------------------------------------------------------
class InstanceCopy:
    """The first step of a copy body: the solid of one source body, placed for its instance.
    Saved as "sciforge.instances.InstanceCopy": keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Instance", doc)

        add("App::PropertyLinkGlobal", "Source", "The body this repeats")
        # The source component: its Placement changes recompute the copy.
        add("App::PropertyLinkGlobal", "Root", "The component the body belongs to")
        add("App::PropertyLinkGlobal", "Pattern", "The pattern that places this copy")
        add("App::PropertyInteger", "Index", "Which copy of the pattern")
        bodies.mark(obj, COPY_TYPE)
        bodies.hide_from_timeline(obj)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        source = obj.Source
        if source is None or not components.alive(source):
            return  # the source body was deleted: the copy keeps its last shape
        if source.Shape.isNull() or not source.Shape.Solids:
            return  # nothing to copy yet (a body that is rolled back): keep the last shape
        shape = bodies.global_shape(source)
        pattern = obj.Pattern
        if pattern is not None:
            moves = list(getattr(pattern, "Moves", []) or [])
            if obj.Index >= len(moves):
                return  # about to be removed (the pattern has fewer copies now)
            shape.transformShape(moves[obj.Index].toMatrix(), True)
            body = copy_body(obj)
            obj.Shape = bodies.to_local(shape, body) if body is not None else shape
            return
        root = obj.Root
        if root is not None:
            place = root.getGlobalPlacement()
            if not place.isIdentity():
                shape.transformShape(place.inverse().toMatrix(), True)
        obj.Shape = shape

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


# -- making --------------------------------------------------------------------------------------
def _mark_instance(part, source, pattern=None, index=0):
    bodies.add_prop(part, "App::PropertyLinkGlobal", INSTANCE_OF, "SciForge")
    setattr(part, INSTANCE_OF, source)
    # An instance is no step of its own (Fusion records occurrences in the browser, not the
    # timeline); a pattern's copies belong to the pattern's step.
    bodies.hide_from_timeline(part)
    if pattern is not None:
        bodies.add_prop(part, "App::PropertyLinkGlobal", PATTERN, "SciForge")
        setattr(part, PATTERN, pattern)
        bodies.add_prop(part, "App::PropertyInteger", INDEX, "SciForge")
        setattr(part, INDEX, int(index))


def _labels_in_use(source):
    return [number(p) for p in instances_of(source)]


def global_placement(obj):
    try:
        return obj.getGlobalPlacement()
    except Exception:
        return App.Placement(obj.Placement)


def make_instance(source, parent=components.KEEP, placement=None, pattern=None, index=0):
    """A new instance of `source` (an instance's own source when an instance is given),
    in `parent` (KEEP: beside the source). ``placement``: where it stands, in design
    coordinates (default: right on the source). Returns the instance part. No undo step of
    its own (the caller's transaction holds it)."""
    source = definition(source)
    if source is None:
        raise ValueError("That component's original was deleted: it cannot be copied.")
    doc = source.Document
    where = components.container_of(source) if parent is components.KEEP else parent
    if where is not None and components.is_inside(where, source):
        where = components.container_of(source)  # never an instance inside itself
    n = core.next_instance_number(_labels_in_use(source))
    part = components.new_component(doc, core.instance_label(source.Label, n), where)
    _mark_instance(part, source, pattern, index)
    if pattern is None:
        wanted = placement if placement is not None else global_placement(source)
        outer = components._container_placement(where)
        part.Placement = outer.inverse().multiply(wanted)
    for body in source_bodies(source):
        _add_copy(part, body, source, pattern, index)
    log("instance %s of %s made" % (part.Label, source.Label))
    return part


def _add_copy(part, body, source, pattern=None, index=0):
    doc = part.Document
    feature = doc.addObject(COPY_OBJECT, COPY_TYPE)
    InstanceCopy(feature)
    feature.Source = body
    feature.Root = source
    if pattern is not None:
        feature.Pattern = pattern
        feature.Index = int(index)
    part.addObject(feature)  # in the copy body's own component (FreeCAD's link scope)
    copy = components.new_body_in(doc, part, label=body.Label)
    copy.BaseFeature = feature
    for obj in copy.Group:
        if obj.TypeId == "PartDesign::FeatureBase":
            bodies.hide_from_timeline(obj)
    try:
        copy.ShapeMaterial = body.ShapeMaterial
    except Exception:
        pass
    try:
        from . import appearance

        appearance.copy_body_appearance(body, copy)
    except Exception:
        pass
    if App.GuiUp:
        try:
            feature.ViewObject.Visibility = False
        except Exception:
            pass
    return copy


def _remove_copy(feature, body):
    doc = feature.Document
    if body is not None and bodies.alive(body):
        bodies.remove_body(body)
    try:
        if components.alive(feature):
            doc.removeObject(feature.Name)
    except Exception:
        pass


# -- keeping instances in line with their source --------------------------------------------------
def sync(doc):
    """Bring every instance in line with its source: a copy body per source body, named like
    it; the instance named "<source>:<n>". True when something changed (recompute)."""
    changed = False
    if doc is None:
        return False
    for part in [o for o in doc.Objects if is_instance(o)]:
        try:
            changed = _sync_one(part) or changed
        except Exception as exc:
            warn("instance %s: %s" % (part.Label, exc))
    return changed


def _sync_one(part):
    source = source_of(part)
    if source is None:
        return False  # the original is gone: the instance keeps its last shapes
    changed = False
    base, n = core.split_instance_label(part.Label)
    if n is None or base != source.Label:
        used = [number(p) for p in instances_of(source) if p is not part]
        n = n if (n is not None and n not in used) else core.next_instance_number(used)
        part.Label = core.instance_label(source.Label, n)
        changed = True
    pattern = pattern_of(part)
    index = int(getattr(part, INDEX, 0) or 0)
    wanted = source_bodies(source)
    have = {}
    for feature, body in copy_features(part):
        src = _link(feature, "Source")
        if src is None or src not in wanted or src.Name in have or body is None:
            _remove_copy(feature, body)
            changed = True
            continue
        have[src.Name] = (feature, body)
        if body.Label != src.Label:
            body.Label = src.Label
            changed = True
    for body in wanted:
        if body.Name not in have:
            _add_copy(part, body, source, pattern, index)
            changed = True
    return changed


def paste_new(source, parent=components.KEEP):
    """Paste New: an independent copy of a component with all its features, named
    "<name> (1)", placed right on the original. Returns the new part."""
    source = definition(source)
    if source is None:
        raise ValueError("That component's original was deleted: Paste New cannot copy it.")
    doc = source.Document
    labels = [o.Label for o in components.list_components(doc)]
    copy = doc.copyObject(source, True)
    if isinstance(copy, (list, tuple)):
        copy = copy[0]
    copy.Label = core.paste_new_label(source.Label, labels)
    components.mark(copy)
    where = components.container_of(source) if parent is components.KEEP else parent
    if where is not None and components.is_inside(where, source):
        where = components.container_of(source)
    current = components.container_of(copy)
    wanted = global_placement(source)
    if current is not where:
        if current is not None:
            current.removeObject(copy)
        if where is not None:
            where.addObject(copy)
    outer = components._container_placement(where)
    copy.Placement = outer.inverse().multiply(wanted)
    # Bodies keep their names (Body1 in every component, like Fusion's): FreeCAD numbered
    # the copies' labels when duplicate labels were not allowed.
    originals = components.bodies_in(doc, source, recursive=True)
    copies = components.bodies_in(doc, copy, recursive=True)
    for original, made in zip(originals, copies):
        if made.Label != original.Label:
            made.Label = original.Label
    _step_before_its_features(copy)
    log("independent copy %s of %s made" % (copy.Label, source.Label))
    return copy


def _step_before_its_features(part):
    """FreeCAD copies a component's features before the component itself: its timeline
    step is put right before them (a component is made before what is in it)."""
    try:
        from . import timeline_ops

        keys = []
        for body in components.bodies_in(part.Document, part, recursive=True):
            keys += [timeline_ops._key(obj) for obj in body.Group]
        if keys and timeline_ops._key(part) > min(keys):
            timeline_ops._add_prop(part, "App::PropertyFloat", timeline_ops.RANK, "Order")
            setattr(part, timeline_ops.RANK, min(keys) - 0.5)
    except Exception as exc:
        warn("Paste New: %s" % exc)


# -- the watch (GUI) ------------------------------------------------------------------------------
class _Watch:
    """After a recompute (a new body in a copied component, a source renamed...), the
    instances are brought in line a moment later, never during undo / redo or a file load."""

    def __init__(self):
        self._pending = set()

    def slotRecomputedDocument(self, doc):
        self._later(doc)

    def slotChangedObject(self, obj, prop):
        try:
            if prop == "Label" and components.is_component(obj) and not is_instance(obj):
                self._later(obj.Document)
        except Exception:
            pass

    def _later(self, doc):
        try:
            name = doc.Name
            if name in self._pending or not _any_instance(doc):
                return
            self._pending.add(name)
            from .compat import QtCore

            QtCore.QTimer.singleShot(0, lambda: self._run(name))
        except Exception:
            pass

    def _run(self, name):
        self._pending.discard(name)
        try:
            if name not in App.listDocuments():
                return
            doc = App.getDocument(name)
            if doc.Restoring or doc.Transacting or getattr(doc, "Recomputing", False):
                return
            if sync(doc):
                doc.recompute()
        except Exception as exc:
            warn("instances: %s" % exc)


def _any_instance(doc):
    try:
        return any(is_instance(o) for o in doc.Objects)
    except Exception:
        return False


_WATCH = {"observer": None}


def install_watch():
    if _WATCH["observer"] is None:
        _WATCH["observer"] = _Watch()
        App.addDocumentObserver(_WATCH["observer"])
