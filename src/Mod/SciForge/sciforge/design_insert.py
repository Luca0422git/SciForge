# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insert into Current Design (Fusion's Insert > Insert into Current Design, the Data
Panel's right-click): another saved design comes in as one component named after it,
linked to its file, and Break Link makes it independent. No Qt. Spec and sources:
docs/sciforge/parity/insert-export.md ("Part 2") and parity/versions.md.

Fusion (help "Insert designs"): "The design is inserted as an external component ... An
Insert feature displays in the Timeline. The external component instance is associatively
linked to the source design"; then the Initial Position dialog places it. Autodesk blog:
right-click > Break Link: "Your component now becomes a stand-alone part, and you're free
to edit its features within your current file".

How it is built on FreeCAD: the component is an App::Part (SciForgeType Component, the
file's name in `SciForgeLinkedFile`, relative to this design) holding, for every body of
the other design, a copy body whose first step is a `LinkedCopy` (Part::FeaturePython in
the component, hidden from the timeline) that copies the other design's body through an
App::PropertyXLink: FreeCAD stores the link by the file's path relative to this design and
opens the other design (hidden) with it, so a project folder moved as a whole keeps
working. Bodies of the other design's components come in flat (as in a copy of a
component). Break Link copies the other design's bodies with every feature
(``Document.copyObject`` across documents) into the component in place of the copies.
"""

import os

import FreeCAD as App

from . import bodies, components, log, warn

LINKED_FILE = "SciForgeLinkedFile"
COPY_TYPE = "LinkedCopy"


class LinkedCopy:
    """The first step of a linked body: the solid of a body of another design. Saved as
    "sciforge.design_insert.LinkedCopy": keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        if "Source" not in obj.PropertiesList:
            obj.addProperty("App::PropertyXLink", "Source", "Linked", "The body it repeats")
        bodies.mark(obj, COPY_TYPE)
        bodies.hide_from_timeline(obj)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        source = obj.Source
        if source is None or not bodies.alive(source):
            return  # the other design is not there: the copy keeps its last shape
        if source.Shape.isNull() or not source.Shape.Solids:
            return
        obj.Shape = bodies.global_shape(source)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


# -- reading -----------------------------------------------------------------------------------
def is_copy_feature(obj):
    return bodies.kind(obj) == COPY_TYPE and isinstance(getattr(obj, "Proxy", None), LinkedCopy)


def is_linked(component):
    """True for a component inserted from another design and still linked to it."""
    return components.is_component(component) and bool(getattr(component, LINKED_FILE, ""))


def linked_components(doc):
    return [c for c in components.list_components(doc) if is_linked(c)]


def copy_features(component):
    return [o for o in getattr(component, "Group", []) if is_copy_feature(o)]


def copy_body(feature):
    for obj in feature.InList:
        if bodies.is_body(obj) and obj.BaseFeature is feature:
            return obj
    return None


def broken(doc):
    """Labels of the linked components whose design was not found."""
    found = []
    for comp in linked_components(doc):
        if any(f.Source is None for f in copy_features(comp)):
            found.append(comp.Label)
    return found


def source_bodies(other):
    """The bodies of another design that come in (those with a solid)."""
    found = [o for o in other.Objects if o.TypeId == "PartDesign::Body"]
    return sorted([b for b in found if bodies.has_solid(b)], key=lambda b: b.ID)


def design_name(path):
    return os.path.splitext(os.path.basename(path or ""))[0] or "Design"


# -- inserting ---------------------------------------------------------------------------------
def insert_linked(doc, other, parent=None, label=None):
    """The design `other` (an open document, saved) as a linked component in `parent`
    (None: the root). No undo step of its own. Returns the component."""
    sources = source_bodies(other)
    if not sources:
        raise ValueError("%s has no bodies to insert." % design_name(other.FileName))
    name = label or design_name(other.FileName)
    taken = {c.Label for c in components.list_components(doc)}
    unique, n = name, 1
    while unique in taken:  # a second insert of the same design: "Wheel (2)"
        n += 1
        unique = "%s (%d)" % (name, n)
    comp = components.new_component(doc, unique, parent)
    bodies.add_prop(comp, "App::PropertyString", LINKED_FILE, "SciForge")
    setattr(comp, LINKED_FILE, _relative(doc, other.FileName))
    for source in sources:
        _add_copy(doc, comp, source)
    doc.recompute()
    log("inserted %s as a linked component (%d bodies)" % (name, len(sources)))
    return comp


def _relative(doc, path):
    try:
        from . import versions

        return versions.relative_path(doc.FileName, path)
    except Exception:
        return os.path.basename(path)


def _add_copy(doc, comp, source):
    feature = doc.addObject("Part::FeaturePython", COPY_TYPE)
    LinkedCopy(feature)
    feature.Source = source
    comp.addObject(feature)
    body = components.new_body_in(doc, comp, label=source.Label)
    body.BaseFeature = feature
    for obj in body.Group:
        if obj.TypeId == "PartDesign::FeatureBase":
            bodies.hide_from_timeline(obj)
    try:
        from . import appearance

        appearance.copy_body_appearance(source, body)
    except Exception:
        pass
    if App.GuiUp:
        try:
            feature.ViewObject.Visibility = False
        except Exception:
            pass
    return body


def refresh(doc):
    """Recompute the linked copies whose design changed since they were computed (the
    other design was saved again): True when something changed."""
    changed = False
    for comp in linked_components(doc):
        for feature in copy_features(comp):
            source = feature.Source
            if source is None or not bodies.alive(source):
                continue
            try:
                new = bodies.global_shape(source)
                old = feature.Shape
                if old.isNull() or not _same(old, new):
                    feature.touch()
                    changed = True
            except Exception as exc:
                warn("linked %s: %s" % (comp.Label, exc))
    return changed


def _same(a, b):
    try:
        if abs(a.Volume - b.Volume) > 1e-6 * max(1.0, abs(b.Volume)):
            return False
        return (
            a.BoundBox.isInside(b.BoundBox.Center)
            and abs(a.BoundBox.DiagonalLength - b.BoundBox.DiagonalLength) < 1e-6
        )
    except Exception:
        return False


# -- Break Link --------------------------------------------------------------------------------
def break_link(component):
    """Make a linked component independent: the other design's bodies with all their
    features are copied in (their steps join the timeline), the linked copies go. No undo
    step of its own. Returns the new bodies."""
    if not is_linked(component):
        raise ValueError("%s is not linked to another design." % component.Label)
    doc = component.Document
    features = copy_features(component)
    sources = [f.Source for f in features]
    if not sources or any(s is None or not bodies.alive(s) for s in sources):
        raise ValueError(
            "The design %s is not found, so its features cannot be copied in. Put it back "
            "in the project folder first." % getattr(component, LINKED_FILE)
        )
    made = []
    for feature, source in zip(features, sources):
        old = copy_body(feature)
        label = old.Label if old is not None else source.Label
        copied = doc.copyObject(source, True)
        if isinstance(copied, (list, tuple)):
            copied = [c for c in copied if bodies.is_body(c)][0]
        try:
            outer = source.getParentGeoFeatureGroup()
            if outer is not None:
                copied.Placement = outer.getGlobalPlacement().multiply(copied.Placement)
        except Exception:
            pass
        current = components.container_of(copied)
        if current is not None:
            current.removeObject(copied)
        component.addObject(copied)
        copied.Label = label
        try:
            from . import appearance

            appearance.copy_body_appearance(source, copied)
        except Exception:
            pass
        if old is not None:
            bodies.remove_body(old)
        try:
            doc.removeObject(feature.Name)
        except Exception:
            pass
        made.append(copied)
    component.removeProperty(LINKED_FILE)
    _component_step_first(component)
    doc.recompute()
    log("%s is no longer linked (%d bodies copied in)" % (component.Label, len(made)))
    return made


def _component_step_first(part):
    try:
        from . import instances

        instances._step_before_its_features(part)
    except Exception as exc:
        warn("Break Link: %s" % exc)


# -- the watch: a design opened with linked components -----------------------------------------
class _Watch:
    """After a design opens, its linked copies are recomputed when the other design changed
    since (Fusion offers Get Latest; the copies show the saved design at once here)."""

    def slotCreatedDocument(self, doc):
        try:
            name = doc.Name
            from .compat import QtCore

            QtCore.QTimer.singleShot(400, lambda: _refresh_later(name))
        except Exception:
            pass


def _refresh_later(name, tries=20):
    try:
        if name not in App.listDocuments():
            return
        doc = App.getDocument(name)
        if doc.Restoring or doc.Transacting:
            if tries > 0:
                from .compat import QtCore

                QtCore.QTimer.singleShot(300, lambda: _refresh_later(name, tries - 1))
            return
        if not linked_components(doc):
            return
        if refresh(doc):
            doc.recompute()
            log("linked designs brought up to date in %s" % doc.Label)
    except Exception as exc:
        warn("linked designs: %s" % exc)


_WATCH = {"observer": None}


def install_watch():
    if _WATCH["observer"] is None and App.GuiUp:
        _WATCH["observer"] = _Watch()
        App.addDocumentObserver(_WATCH["observer"])
