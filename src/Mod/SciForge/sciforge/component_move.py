# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Move/Copy with Object type Components: the document side, no Qt (the dialog is
component_move_ui.py; the movement maths are move.py's).

Fusion moves the component itself (its occurrence), not its bodies: everything in it moves
together, and the move is not a modelling step. Its Move dialog has "Capture Position"
(components only): ticked, the new position is recorded in the timeline as a Move step that
can be edited, suppressed and rolled back; not ticked, the component just stands somewhere
else ("position pending": joints' Capture Position / Revert can then record or undo it).

On FreeCAD a component is an ``App::Part``: moving it changes its Placement. A captured
move is a ``ComponentMove`` step (``App::FeaturePython`` outside the bodies, SciForgeType
"ComponentMove", called "Move" in the timeline) that keeps:

  Component   the component it moved
  Movement    the movement, in design coordinates (move.transform of the dialog's choices)
  Before      the component's own Placement before it (what rolling back returns to)
  MoveId      steps made by one Move share it (one per component)

The step computes nothing itself; ``apply_history(doc)`` puts each component where its
captured moves put it, counting only the moves before the history marker that are not
suppressed (run when the marker rolls, a move is suppressed / deleted, or edited).
Grounded components are never moved (joints.is_grounded), as in Fusion.
"""

import FreeCAD as App

from . import bodies, components, log, move, warn
from . import components_core as core

SCIFORGE_TYPE = "ComponentMove"
META = "SciForgeMove"
TYPE = "App::FeaturePython"


class ComponentMoveError(ValueError):
    """The move cannot be made as asked (the message says why)."""


# -- reading -----------------------------------------------------------------------------------
def is_step(obj):
    return bodies.kind(obj) == SCIFORGE_TYPE


def steps(doc):
    return sorted((o for o in doc.Objects if is_step(o)), key=lambda o: o.ID)


def steps_of(move_id, doc):
    if not move_id:
        return []
    return [s for s in steps(doc) if getattr(s, "MoveId", "") == move_id]


def steps_for(component):
    """Captured moves of one component, oldest first."""
    if component is None:
        return []
    return [s for s in steps(component.Document) if _component(s) is component]


def _component(step):
    try:
        part = step.Component
    except Exception:
        return None
    return part if components.alive(part) else None


# -- grounded / pattern copies: what may move -----------------------------------------------------
def refusal(part):
    """Why `part` cannot be moved ('' when it can)."""
    if not components.is_component(part):
        return "Pick a component."
    try:
        from . import joints

        if joints.is_part(part) and joints.is_grounded(part):
            return (
                "%s is grounded, so it cannot move. Unground it first (right-click it in the "
                "browser)." % part.Label
            )
    except Exception:
        pass
    try:
        from . import instances

        pattern = instances.pattern_of(part)
        if pattern is not None:
            return (
                "%s is a copy placed by %s: edit the pattern to move it, or move the "
                "original." % (part.Label, pattern.Label)
            )
    except Exception:
        pass
    return ""


def frame_object(doc):
    """An object with origin axes at the design's origin (drawn for Rotate's Axis box): a
    root body, else a component that stands at the origin, else any body."""
    for body in components.bodies_in(doc, None):
        try:
            if body.getGlobalPlacement().isIdentity():
                return body
        except Exception:
            continue
    for part in components.list_components(doc):
        try:
            if part.getGlobalPlacement().isIdentity():
                return part
        except Exception:
            continue
    found = bodies.list_bodies(doc)
    return found[0] if found else None


# -- the movement ----------------------------------------------------------------------------------
def container_placement(part):
    return components._container_placement(components.container_of(part))


def local_movement(part, movement):
    """A design-coordinate movement as a change of the component's own Placement (a nested
    component's Placement is relative to its parent)."""
    outer = container_placement(part)
    return outer.inverse().multiply(movement).multiply(outer)


def moved(part, before, movement):
    """The Placement `part` gets when `movement` (design coordinates) is applied to it while
    it stands at `before` (its own Placement)."""
    return local_movement(part, movement).multiply(App.Placement(before))


def place(part, placement, tol=1e-12):
    if not part.Placement.isSame(placement, tol):
        part.Placement = placement
        return True
    return False


# -- the step ------------------------------------------------------------------------------------
class ComponentMoveFeature:
    """A captured move of a component. Saved as "sciforge.component_move.ComponentMoveFeature":
    keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Move", doc)

        add("App::PropertyLinkGlobal", "Component", "The component moved")
        add("App::PropertyPlacement", "Movement", "The movement, in design coordinates")
        add("App::PropertyPlacement", "Before", "The component's placement before the move")
        add("App::PropertyString", "MoveId", "Steps made by one Move share this")
        bodies.mark(obj, SCIFORGE_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        pass  # a record: apply_history() places the component

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _meta(options):
    meta = {"v": 1}
    for key in ("move_type", "axis_label", "from_label", "to_label"):
        meta[key] = options.get(key, "")
    for key in move.NUMBERS:
        meta[key] = float(options.get(key, 0.0) or 0.0)
    for key in move.POINTS:
        value = options.get(key)
        meta[key] = [float(c) for c in value] if value is not None else None
    return meta


def record(options, befores, existing=None, move_id=None, name="Move"):
    """Make (or update) the captured Move steps: one per moved component. ``befores``:
    {component name: its own Placement before the move}. ``existing``: the steps of the
    Move being edited. Returns the steps."""
    options = move.with_defaults(options)
    movement = move.transform(options)
    wanted = list(options.get("components") or [])
    if not wanted:
        raise ComponentMoveError("Select the components to move.")
    existing = [s for s in (existing or []) if bodies.alive(s)]
    move_id = move_id or (getattr(existing[0], "MoveId", "") if existing else "") or move.new_id()
    have = {}
    for step in existing:
        part = _component(step)
        if part is None or part not in wanted:
            remove(step)
        else:
            have[part.Name] = step
    meta = _meta(options)
    result = []
    for part in wanted:
        step = have.get(part.Name)
        if step is None:
            step = part.Document.addObject(TYPE, name)
            ComponentMoveFeature(step)
            step.Component = part
            before = befores.get(part.Name, part.Placement)
            step.Before = App.Placement(before)
            _attach_view_provider(step)
            try:
                from . import timeline_ops

                timeline_ops.place_root_step(step)
            except Exception as exc:
                warn("Move step: %s" % exc)
        if not step.Movement.isSame(movement, 1e-12):
            step.Movement = movement
        if step.MoveId != move_id:
            step.MoveId = move_id
        bodies.save_meta(step, META, meta)
        result.append(step)
    return result


def read(step):
    """(dialog options, steps) of a captured Move (all its components)."""
    found = steps_of(getattr(step, "MoveId", ""), step.Document) or [step]
    meta = bodies.load_meta(step, META)
    options = move.with_defaults({})
    for key in ("move_type", "axis_label", "from_label", "to_label") + move.NUMBERS:
        if key in meta:
            options[key] = meta[key]
    for key in move.POINTS:
        if meta.get(key) is not None:
            options[key] = list(meta[key])
    options["components"] = [p for p in (_component(s) for s in found) if p is not None]
    options["capture"] = True
    return options, found


def remove(step):
    if not bodies.alive(step):
        return
    try:
        step.Document.removeObject(step.Name)
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


# -- the history marker ----------------------------------------------------------------------------
def apply_history(doc, only=None):
    """Put every component that has captured moves where those moves put it, counting the
    moves before the history marker that are not suppressed (Fusion rolls component
    positions back with the marker). ``only``: component names to do (None: all). Returns
    True when a placement changed."""
    from . import timeline_ops

    all_steps = steps(doc)
    if not all_steps:
        return False
    try:
        tl = timeline_ops.timeline(doc, deps=False)
        order = {item.name: i for i, item in enumerate(tl.items)}
        state = {item.name: item.state == "done" for item in tl.items}
    except Exception:
        order, state = {}, {}
    by_part = {}
    for step in all_steps:
        part = _component(step)
        if part is None or (only is not None and part.Name not in only):
            continue
        by_part.setdefault(part.Name, (part, []))[1].append(step)
    changed = False
    for part, found in by_part.values():
        found.sort(key=lambda s: order.get(s.Name, s.ID))
        rows = [(s.Name, state.get(s.Name, True), timeline_ops.is_suppressed(s)) for s in found]
        used = set(core.placement_steps_in_effect(rows))
        current = App.Placement(found[0].Before)
        for step in found:
            if step.Name in used:
                current = moved(part, current, step.Movement)
        try:
            changed = place(part, current, 1e-9) or changed
        except Exception as exc:
            warn("could not place %s: %s" % (part.Label, exc))
    if changed:
        log("component positions follow the timeline")
    return changed


def forget(step):
    """A captured move is about to be deleted: the component's history goes on as if it had
    never been made (the next move starts where this one started)."""
    if not is_step(step):
        return
    part = _component(step)
    if part is None:
        return
    found = steps_for(part)
    if found and found[0] is step and len(found) > 1:
        found[1].Before = App.Placement(step.Before)
    elif found == [step]:
        place(part, App.Placement(step.Before))  # its only captured move: back to before it


def steps_of_component(part):
    """The captured moves that go when a component is deleted."""
    return steps_for(part)
