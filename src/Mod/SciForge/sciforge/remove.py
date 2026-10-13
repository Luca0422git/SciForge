# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Remove (Modify > Remove, a body's or component's right-click menu): the document
side, no Qt. remove_ui.py has the command and the dialog.

Remove is not Delete: Delete takes the features that made a body away, Remove adds a step
to the timeline from which on the body is gone. Rolling the history marker before the
Remove, suppressing it or deleting it brings the body back (Fusion's typical use: throw
away one half after a Split Body).

What is built: a "Remove" step (SciForgeType "Remove", RemoveFeature below) at the history
marker of each removed body. It keeps the body's solid as it is (later steps of the design
that used the body keep working) and marks the body as used up while the step is part of
the design (bodies.USED_UP): bodies_gui then hides the body and the browser leaves it out,
the way a Combine's tool bodies go. A component's Remove is one such step in each of its
bodies (all levels); the steps share a RemoveId and are named after the component.
"""

import FreeCAD as App

from . import bodies

TYPE = "PartDesign::FeaturePython"
SCIFORGE_TYPE = "Remove"


class RemoveError(ValueError):
    """Nothing can be removed as asked; the message says why."""


class RemoveFeature:
    """Saved as "sciforge.remove.RemoveFeature": keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        bodies.mark(obj, SCIFORGE_TYPE)
        if bodies.add_prop(obj, "App::PropertyBool", bodies.USED_UP, "Base"):
            setattr(obj, bodies.USED_UP, True)
        if "RemoveId" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyString", "RemoveId", "Remove", "Steps of one Remove share it"
            )
        if "Target" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyString", "Target", "Remove", "What was removed (body or component)"
            )

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        import Part

        base = obj.BaseFeature
        if base is None or base.Shape.isNull():
            obj.Shape = Part.Shape()
            return
        obj.Shape = base.Shape.copy()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def is_remove(obj):
    return bodies.kind(obj) == SCIFORGE_TYPE


def targets_of(objects):
    """Bodies to remove for the picked objects: a body (or a step / face of one) is its
    body, a component is every body inside it. Returns (bodies, components)."""
    from . import components

    found, parts = [], []
    for obj in objects:
        if obj is None:
            continue
        if components.is_component(obj):
            if obj not in parts:
                parts.append(obj)
            for body in components.bodies_in(obj.Document, obj, recursive=True):
                if body not in found:
                    found.append(body)
            continue
        body = bodies.body_of(obj)
        if body is not None and body not in found:
            found.append(body)
    return found, parts


def removed(body):
    """The active Remove step of a body, or None."""
    for obj in body.Group:
        if is_remove(obj) and bodies.is_active_step(obj):
            return obj
    return None


def make(targets, components_removed=(), remove_id=None):
    """A Remove step at the history marker of each body (no undo step of its own). Returns
    the steps. A body already removed is refused (nothing to remove)."""
    import uuid

    if not targets:
        raise RemoveError("Select the bodies or components to remove.")
    remove_id = remove_id or uuid.uuid4().hex[:12]
    names = {}
    for part in components_removed:
        for body in _bodies_in(part):
            names[body.Name] = part.Label
    made = []
    for body in targets:
        if removed(body) is not None:
            continue
        if not bodies.has_solid(body):
            continue
        step = bodies.insert_after_tip(body, TYPE, "Remove")
        RemoveFeature(step)
        step.RemoveId = remove_id
        step.Target = names.get(body.Name, body.Label)
        if body.Name in names:
            step.Label = "Remove %s" % names[body.Name]
        _attach_view_provider(step)
        made.append(step)
    if not made:
        raise RemoveError("Those bodies are removed already (or have no solid).")
    return made


def _bodies_in(part):
    from . import components

    return components.bodies_in(part.Document, part, recursive=True)


def steps_of(remove_id, doc):
    if not remove_id:
        return []
    found = [o for o in doc.Objects if is_remove(o) and getattr(o, "RemoveId", "") == remove_id]
    return sorted(found, key=lambda o: o.ID)


def leave_removed_body(doc):
    """A removed body must not stay the active one (new work would go into a body nobody
    sees): the first body still there takes over, else none."""
    active = bodies.active_body(doc)
    if active is None or removed(active) is None:
        return
    for body in bodies.list_bodies(doc):
        if removed(body) is None and bodies.has_solid(body):
            bodies.set_active_body(body)
            return
    if App.GuiUp:
        try:
            import FreeCADGui as Gui

            Gui.getDocument(doc.Name).ActiveView.setActiveObject("pdbody", None)
        except Exception:
            pass


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .bodies_gui import StepViewProvider

        StepViewProvider(obj.ViewObject)
    except Exception:
        pass
