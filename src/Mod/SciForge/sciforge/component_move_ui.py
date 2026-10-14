# SPDX-License-Identifier: LGPL-2.1-or-later
"""Move/Copy (M) with Move Object "Components": Fusion's dialog for moving whole components.

  Move Object       Components (Bodies switches to the bodies dialog, move_ui.py)
  Objects           click a component: in the 3D view (anything of it; the component just
                    below the active one is taken, as in Fusion) or its browser row; a
                    component selected before M is taken at once
  Move Type         Free Move (arrows, turn handles, X/Y/Z Distance and Angle, Set Pivot),
                    Translate, Rotate (about an axis), Point to Point, Point to Position
  Create Copy       the component stays; a linked copy ("Name:2", instances.py) is moved
  Capture Position  record the move in the timeline as a Move step (edit it, suppress it,
                    roll the marker back before it); off, the component just stands there
                    (Fusion's position pending)

The component itself moves (its Placement), with everything in it. Grounded components and
the copies a pattern placed are refused with the reason. Live preview; OK / Enter keeps it
as one undo step, Cancel / Esc puts everything back. The document side is
component_move.py.
"""

import time

import FreeCAD as App

from . import bodies, component_move, components, log, move, warn
from . import components_core as core
from .bodies_panel import edit as _edit
from .move_ui import OVERLAY_CLICK_S, MovePanel, _ref_text, _snap


def component_shapes(doc, part):
    """The solids of a component (its bodies, nested ones too), design coordinates."""
    shapes = []
    for body in components.bodies_in(doc, part, recursive=True):
        try:
            if bodies.has_solid(body):
                shapes.append(bodies.global_shape(body))
        except Exception:
            continue
    return [s for s in shapes if not s.isNull()]


class ComponentMovePanel(MovePanel):
    title = "Move/Copy"
    object_type = "components"
    last = None

    def __init__(self, doc, feature=None, carry=None, picks=None):
        self._befores = {}  # component name -> its own Placement when the dialog took it
        self._copies = {}  # component name -> the copy Create Copy made of it
        self._applied = App.Placement()  # the movement the preview shows now
        super().__init__(doc, feature, carry, picks)
        ComponentMovePanel.last = self
        if feature is not None:
            for step in self.steps:
                part = step.Component
                if part is not None:
                    self._befores[part.Name] = App.Placement(part.Placement)
            try:
                self._applied = move.transform(self.options)
            except move.MoveError:
                self._applied = App.Placement()

    def read_feature(self, feature):
        options, steps = component_move.read(feature)
        options["bodies"] = []
        return options, steps

    # -- form ----------------------------------------------------------------------------------
    def build_form(self):
        self.options.setdefault("components", [])
        self.options.setdefault("capture", False)
        super().build_form()
        self.capture, _ = self.check_box(
            "Capture Position",
            self.options["capture"],
            self._capture_toggled,
            "Record the move in the timeline (a Move step you can edit and roll back); off, "
            "the component just stands where you put it",
        )
        if self.editing:
            self.capture.setEnabled(False)  # a Move step is a captured move
            self.copy.setEnabled(False)

    def _capture_toggled(self):
        self.options["capture"] = self.capture.isChecked()

    def _show_picks(self):
        parts = self.options.get("components") or []
        if not parts:
            text = ""
        elif len(parts) == 1:
            text = parts[0].Label
        else:
            text = "%d components" % len(parts)
        self.fields["objects"].set_text(text)
        self.fields["axis"].set_text(self.options["axis_label"] if self.options["axis_dir"] else "")
        self.fields["from_point"].set_text(
            self.options["from_label"] if self.options["from_point"] else ""
        )
        self.fields["to_point"].set_text(
            self.options["to_label"] if self.options["to_point"] else ""
        )

    def _moving(self):
        return self.options.get("components") or []

    def _axis_frame(self):
        return component_move.frame_object(self.doc)

    def cleared(self, name):
        if name == "objects":
            self._finish_pivot()
            self.options["components"] = []
            self._show_picks()
            self._make_handles()
            return
        super().cleared(name)

    # -- clicks ------------------------------------------------------------------------------------
    def picked(self, obj, short, point):
        if self._handles_busy() or time.time() - self._overlay_time < OVERLAY_CLICK_S:
            return
        if self.setting_pivot:
            self._pivot_picked(obj, short, point)
            return
        if self.active == "objects":
            self._component_picked(obj)
            return
        if self.active == "axis":
            found = move.axis_of(obj, short)
            back = self._back(obj)
            if found is not None and back is not None:
                found = (back.multVec(found[0]), back.Rotation.multVec(found[1]))
            if found is None:
                self.message.setText(
                    "Pick an axis: an origin axis, a straight edge or a round edge or face."
                )
                return
            self._set_axis(found, _ref_text(obj, short))
            return
        if self.active in ("from_point", "to_point"):
            found = _snap(obj, short, point)
            if found is None:
                found = move.point_of(obj, short)
            if found is None:
                self.message.setText("Pick a point: a corner, an edge or a round edge's centre.")
                return
            back = self._back(obj)
            if back is not None:
                found = back.multVec(found)
            found = App.Vector(*[round(c, 9) + 0.0 for c in found])
            self.options[self.active] = list(found)
            self.options[self.active.replace("point", "label")] = _ref_text(obj, short)
            self._show_picks()
            self.message.setText("")
            if self.options["move_type"] == "point_to_position" and self.active == "from_point":
                self._start_position(found)
            elif self.active == "from_point" and self.options["to_point"] is None:
                self.activate("to_point")
            self.changed()

    def _component_picked(self, obj):
        part = self._component_for(obj)
        if part is None:
            self.message.setText(
                "That body is in no component. Pick a component, or set Move Object to Bodies "
                "to move the body."
            )
            return
        if part in self._copies.values():
            return  # a copy this dialog made (Create Copy)
        why = component_move.refusal(part)
        if why:
            self.message.setText(why)
            return
        self.message.setText("")
        parts = self.options["components"]
        first = not parts
        if part in parts:
            parts.remove(part)
        else:
            parts.append(part)
            self._befores.setdefault(part.Name, App.Placement(part.Placement))
        self._new_pivot()
        self._show_picks()
        if first and self._next_box():
            self.activate(self._next_box())
        self._make_handles()
        self.changed()

    def _component_for(self, obj):
        """The component a click on `obj` picks (components_core.component_to_pick)."""
        if components.is_component(obj):
            return obj
        chain = components.ancestors(obj)
        active = components.active_component(self.doc)
        name = core.component_to_pick(
            [c.Name for c in chain], active.Name if active is not None else None
        )
        return self.doc.getObject(name) if name else None

    def _back(self, obj):
        """For a click on something this dialog moves: the movement back to where it was
        (axes and points are taken before the move, like the bodies dialog does)."""
        moving = list(self._moving()) + list(self._copies.values())
        for part in moving:
            if components.is_inside(obj, part):
                return self._applied.inverse()
        return None

    # -- the pivot, the size of the manipulator ------------------------------------------------
    def _unmoved(self):
        """The components' solids as they were when the dialog took them."""
        found = []
        for part in self._moving():
            try:
                now = part.getGlobalPlacement()
                outer = component_move.container_placement(part)
                before = outer.multiply(self._befores.get(part.Name, part.Placement))
                back = before.multiply(now.inverse())
            except Exception:
                back = App.Placement()
            for shape in component_shapes(self.doc, part):
                if not back.isIdentity():
                    shape.transformShape(back.toMatrix(), True)
                found.append(shape)
        return found

    # -- preview ------------------------------------------------------------------------------
    def apply(self):
        parts = list(self._moving())
        if not parts:
            self._restore_all()
            raise move.NeedsPick("Select the components to move.")
        try:
            movement = move.transform(self.options)
        except move.NeedsPick:
            self._restore_all()
            raise
        self._applied = movement
        if self.editing:
            self._apply_edit(movement)
            return
        wanted = {p.Name for p in parts}
        for name, before in self._befores.items():
            part = self.doc.getObject(name)
            if part is not None and name not in wanted:
                component_move.place(part, before)
        if self.options["copy"]:
            for part in parts:
                before = self._befores.get(part.Name, part.Placement)
                component_move.place(part, before)
                copy = self._copies.get(part.Name)
                if copy is None or not components.alive(copy):
                    from . import instances

                    copy = instances.make_instance(part)
                    self._copies[part.Name] = copy
                component_move.place(copy, component_move.moved(part, before, movement))
            for name in [n for n in self._copies if n not in wanted]:
                self._remove_copy(name)
        else:
            for name in list(self._copies):
                self._remove_copy(name)
            for part in parts:
                before = self._befores.get(part.Name, part.Placement)
                component_move.place(part, component_move.moved(part, before, movement))

    def _apply_edit(self, movement):
        meta = component_move._meta(self.options)
        names = []
        for step in self.steps:
            if not bodies.alive(step):
                continue
            if not step.Movement.isSame(movement, 1e-12):
                step.Movement = movement
            bodies.save_meta(step, component_move.META, meta)
            if step.Component is not None:
                names.append(step.Component.Name)
        component_move.apply_history(self.doc, only=set(names))

    def _remove_copy(self, name):
        copy = self._copies.pop(name, None)
        if copy is not None and components.alive(copy):
            components.remove(self.doc, copy, _top=False)

    def _restore_all(self):
        if self.editing:
            return
        for name, before in self._befores.items():
            part = self.doc.getObject(name)
            if part is not None:
                component_move.place(part, before)
        for name in list(self._copies):
            self._remove_copy(name)

    def after_recompute(self):
        self._place_handles()

    def preview_steps(self):
        return []

    def can_finish(self):
        if not self._moving():
            return "Select the components to move."
        try:
            move.transform(self.options)
        except move.MoveError as exc:
            return str(exc)
        return ""

    def before_close(self, ok):
        if not ok or self.editing:
            return
        try:
            if self.options.get("capture") and not self.options["copy"]:
                component_move.record(self.options, self._befores)
                self.doc.recompute()
            self._joints_follow()
        except Exception as exc:
            warn("Move: could not capture the position: %s" % exc)

    def _joints_follow(self):
        """A captured move is where the component belongs now: Revert must not take it
        back. A move that is not captured leaves the position pending (joints' Capture
        Position / Revert)."""
        if not self.options.get("capture"):
            return
        try:
            from . import joints

            if joints.assembly(self.doc) is not None and not joints.positions(self.doc):
                joints.save_baseline(self.doc)
        except Exception as exc:
            warn("Move: %s" % exc)

    def after_close(self, ok):
        super().after_close(ok)
        if ok:
            log(
                "%s moved%s"
                % (
                    ", ".join(p.Label for p in self._moving()),
                    " (position captured)" if self.options.get("capture") else "",
                )
            )
        try:
            from . import browser_ui

            tree = browser_ui.widget()
            if tree is not None:
                tree.refresh(force=True)
        except Exception:
            pass


def edit(feature):
    """Double-click a captured Move of a component in the timeline."""
    _edit(ComponentMovePanel, feature)


def start(picks=None):
    """The component Move dialog, with `picks` (components) already picked (Paste)."""
    from .bodies_panel import start as _start

    return _start(ComponentMovePanel, picks=picks)


EDITORS = {"SciForge::ComponentMove": edit}
COMMANDS = {}  # reached through Move (M): its Move Object switches to this dialog
