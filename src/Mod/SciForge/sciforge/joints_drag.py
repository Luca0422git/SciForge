# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Component Drag: press the left button on a component in the canvas and drag it.
It moves within the freedom its joints leave it (a revolute arm turns, a slider slides, a
component held by nothing moves in the plane facing you), live, and the whole drag is one
undo step. Grounded components and components held to them by rigid joints stay where
they are (a note says why). Joint limits stop the motion; with contact sets on, the parts
stop where they touch. Motion links make their other joint follow.

This is the only place a canvas drag moves components (the Move dialog is components-2's).
The mouse reaches it through selection_ui's view filter: a press that moves more than a
few pixels on a component (not inside a command, not in a sketch, no Shift / Ctrl) is a
component drag instead of a selection box. The maths is in motion_core.py, the plan of
what moves in joints.drag_plan. Spec: docs/sciforge/parity/joints.md, "Dragging".
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import joints, log, motion_core, preview, warn

PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge"
KEY = "ComponentDrag"
_STATE = {"session": None, "last": None}


# -- the SELECT menu's Component Drag tick ---------------------------------------------------------
def enabled():
    try:
        return bool(App.ParamGet(PARAMS).GetBool(KEY, True))
    except Exception:
        return True


def set_enabled(on):
    App.ParamGet(PARAMS).SetBool(KEY, bool(on))
    log("Component Drag %s" % ("on" if on else "off"))


def toggle():
    set_enabled(not enabled())


def reset():
    """Back to Fusion's default (on): the test harness calls this before each scenario."""
    try:
        App.ParamGet(PARAMS).RemBool(KEY)
    except Exception:
        pass


def active():
    """The drag under way (tests), or None."""
    return _STATE["session"]


def last():
    """What the last drag did (tests): a dict, or None."""
    return _STATE["last"]


# -- the pointer ----------------------------------------------------------------------------------
def _coin_pixel(gl, pos):
    ratio = gl.devicePixelRatioF()
    return pos.x() * ratio, (gl.height() - pos.y()) * ratio


def ray(view, gl, pos):
    """(origin, direction) of the line from the eye through widget pixel `pos`."""
    x, y = _coin_pixel(gl, pos)
    point = App.Vector(view.getPoint(int(round(x)), int(round(y))))
    try:
        perspective = view.getCameraType() == "Perspective"
    except Exception:
        perspective = False
    if perspective:
        cam = view.getCameraNode()
        eye = App.Vector(*cam.position.getValue())
        direction = point - eye
        if direction.Length < 1e-9:
            direction = App.Vector(view.getViewDirection())
        return eye, direction.normalize()
    direction = App.Vector(view.getViewDirection()).normalize()
    return point - direction * 10000.0, direction


def _t(v):
    return (float(v.x), float(v.y), float(v.z))


def _pick_at(view, gl, pos):
    """(part, grab point) under widget pixel `pos`: a solid of a component or body the
    assembly knows, else (None, None)."""
    x, y = _coin_pixel(gl, pos)
    info = view.getObjectInfo((int(round(x)), int(round(y))))
    if not info or not info.get("Object"):
        return None, None
    doc = App.getDocument(info["Document"]) if info.get("Document") else App.ActiveDocument
    root = info.get("ParentObject")
    sub = info.get("SubName") or ""
    if root is None:
        root = doc.getObject(info.get("Object"))
        sub = info.get("Component") or ""
    elif isinstance(root, str):
        root = doc.getObject(root)
    if root is None:
        return None, None
    pick = joints.resolve_selection(root, sub, App.Vector(info["x"], info["y"], info["z"]))
    if pick is None or not pick.element.startswith(("Face", "Edge", "Vertex")):
        return None, None
    obj = pick.obj
    try:
        if obj.TypeId.startswith("Sketcher") or obj.isDerivedFrom("Part::Datum"):
            return None, None
        if not obj.Shape.Solids:
            return None, None
    except Exception:
        return None, None
    return pick.part, App.Vector(info["x"], info["y"], info["z"])


def can_start(gl, view, pos):
    """True when a drag starting at widget pixel `pos` is a Component Drag."""
    if not enabled():
        return False
    part, _grab = _pick_at(view, gl, pos)
    return part is not None and joints.takes_part_in_assembly(part)


def start(gl, view, pos):
    """Start a Component Drag at widget pixel `pos` (where the button went down), or return
    None when what is there is not a component that drags (the press then draws a box)."""
    try:
        if not enabled() or _STATE["session"] is not None:
            return None
        part, grab = _pick_at(view, gl, pos)
        if part is None or not joints.takes_part_in_assembly(part):
            return None
        session = DragSession(part.Document, view, gl, part, grab)
        _STATE["session"] = session
        return session
    except Exception as exc:
        warn("Component Drag: %s" % exc)
        return None


# -- one drag -------------------------------------------------------------------------------------
class DragSession:
    """One press-move-release on a component: everything starts from where the parts stood
    at the press, so nothing drifts; release keeps it (one undo step), Esc puts it back."""

    def __init__(self, doc, view, gl, part, grab):
        self.doc = doc
        self.view = view
        self.gl = gl
        self.part = part
        self.grab = App.Vector(grab)
        self.plan = joints.drag_plan(part)
        self.kind = self.plan["kind"]
        self.moved = False
        self.done = False
        self.blocked_by = None
        self.prev_turn = 0.0
        self.values = None  # (angle, slide) the joint reads now
        self.told = False
        self.joint = None
        if self.kind == "held":
            self._tell(self.plan["why"])
            log("Component Drag: %s" % self.plan["why"])
            self.start_places = None
            _STATE["last"] = {
                "part": part.Name,
                "kind": "held",
                "moved": False,
                "why": self.plan["why"],
            }
            return
        doc.openTransaction("Drag %s" % part.Label)
        movers = self.plan.get("movers") or [part]
        joints.remember_places(doc, movers)
        self.start_places = joints.placements(doc)
        self.view_dir = App.Vector(view.getViewDirection()).normalize()
        joint = self.plan.get("joint")
        if joint is not None:
            self.joint = joint
            self.start_values = joints.value(joint)
            self.values = self.start_values
            j2 = joints.jcs_global(joint, 1)
            self.center = j2.Base
            self.axis = j2.Rotation.multVec(App.Vector(0, 0, 1))
            slide_axis = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[joints.slide_axis(joint)]
            self.slide_dir = j2.Rotation.multVec(App.Vector(*slide_axis))
        else:
            self.joint = None
        self.pairs = joints.contact_pairs(doc, movers)
        log(
            "Component Drag: %s (%s%s)"
            % (part.Label, self.kind, ", %s" % joint.Label if joint is not None else "")
        )

    def _tell(self, text):
        if self.told:
            return
        self.told = True
        try:
            from . import commands

            commands.tell(text)
        except Exception:
            log(text)

    # -- moves ----------------------------------------------------------------------------------
    def follow(self, pos):
        """The pointer is at widget pixel `pos`: put the parts where the drag says."""
        if self.done or self.kind == "held":
            return
        try:
            origin, direction = ray(self.view, self.gl, pos)
            o, d = _t(origin), _t(direction)
            if self.kind == "free":
                self._free(o, d)
            else:
                self._along_joint(o, d)
            self.moved = True
        except Exception as exc:
            warn("Component Drag: %s" % exc)

    def _restore(self):
        joints.apply_placements(self.doc, self.start_places)

    def _free(self, o, d):
        move = motion_core.free_move_from_ray(_t(self.grab), _t(self.view_dir), o, d)
        if move is None:
            return
        movers = self.plan["movers"]

        def put(fraction):
            self._restore()
            shift = App.Vector(*move) * fraction
            joints.move_parts(movers, App.Placement(shift, App.Rotation()))

        self._with_contact(put)
        joints.solve(self.doc)

    def _along_joint(self, o, d):
        joint = self.joint
        kind = motion_core.DRAG_KIND.get(joints.fusion_type(joint))
        sign = 1.0 if self.plan["side"] == 0 else -1.0
        a0, s0 = self.start_values
        grab = _t(self.grab)
        target_angle = target_slide = None
        move = turn = None
        if kind in ("slide", "turn+slide"):
            ds = motion_core.slide_from_ray(grab, _t(self.slide_dir), o, d)
            if ds is not None:
                target_slide = s0 + sign * ds
                grab = _t(self.grab + self.slide_dir * ds)
        if kind in ("turn", "turn+slide"):
            dt = motion_core.turn_from_ray(
                _t(self.center), _t(self.axis), grab, o, d, previous=self.prev_turn
            )
            if dt is not None:
                self.prev_turn = dt
                target_angle = a0 + sign * dt
        if kind == "plane":
            move = motion_core.plane_move_from_ray(grab, _t(self.axis), o, d)
        if kind == "ball":
            turn = motion_core.ball_turn_from_ray(_t(self.center), grab, o, d)
        movers = self.plan["movers"]
        side = self.plan["side"]
        if target_angle is not None or target_slide is not None:
            target_angle, target_slide = joints.clamp_values(joint, target_angle, target_slide)

            def put(fraction):
                self._restore()
                angle = slide = None
                if target_angle is not None:
                    angle = a0 + (target_angle - a0) * fraction
                if target_slide is not None:
                    slide = s0 + (target_slide - s0) * fraction
                joints.place_joint(joint, angle, slide, side, movers=movers)
                joints.follow_links(joint)

            self._with_contact(put)
        elif move is not None or turn is not None:

            def put(fraction):
                self._restore()
                if move is not None:
                    shift = App.Vector(*move) * fraction
                    joints.move_parts(movers, App.Placement(shift, App.Rotation()))
                else:
                    rot = joints.from_frame(((0.0, 0.0, 0.0), turn)).Rotation
                    if fraction < 1.0:
                        axis, angle = rot.Axis, rot.Angle * fraction
                        rot = App.Rotation(axis, angle * 57.29577951308232)
                    c = self.center
                    about = (
                        App.Placement(c, App.Rotation())
                        * App.Placement(App.Vector(), rot)
                        * App.Placement(c * -1, App.Rotation())
                    )
                    joints.move_parts(movers, about)

            self._with_contact(put)
        else:
            return
        code = joints.solve(self.doc, keep=self.plan.get("anchor"))
        if code not in (0,):
            # the other joints cannot follow there: the drag stops where it last could
            self._restore()
            if self.values is not None and self.values != self.start_values:
                joints.place_joint(joint, self.values[0], self.values[1], side, movers=movers)
                joints.follow_links(joint)
                joints.solve(self.doc, keep=self.plan.get("anchor"))
            return
        self.values = joints.value(joint)

    def _with_contact(self, put):
        """Put the parts at the whole move, or (contact sets on and they run into each
        other) at the last fraction of it where they still only touch."""
        put(1.0)
        if not self.pairs:
            return
        hit = joints.blocked(self.doc, self.pairs)
        if hit is None:
            self.blocked_by = None
            return
        self.blocked_by = hit

        def blocked(fraction):
            put(fraction)
            return joints.blocked(self.doc, self.pairs) is not None

        fraction = motion_core.last_free(blocked, steps=12)
        put(fraction)

    # -- the end ------------------------------------------------------------------------------
    def finish(self):
        """The button came up: keep where the parts are (one undo step)."""
        if self.done:
            return
        self.done = True
        _STATE["session"] = None
        if self.kind == "held" or self.start_places is None:
            return
        try:
            moved = self.moved and self._changed()
            if moved:
                self.doc.commitTransaction()
                preview.recompute(self.doc)
            else:
                self.doc.abortTransaction()
            self._report(moved)
        except Exception as exc:
            warn("Component Drag: %s" % exc)
        self._refresh()

    def cancel(self):
        """Esc while dragging: everything goes back where it was."""
        if self.done:
            return
        self.done = True
        _STATE["session"] = None
        if self.kind == "held" or self.start_places is None:
            return
        try:
            self._restore()
            joints.solve(self.doc)
            self.doc.abortTransaction()
            preview.recompute(self.doc)
            self._report(False)
            log("Component Drag cancelled")
        except Exception as exc:
            warn("Component Drag: %s" % exc)

    def _changed(self):
        now = joints.placements(self.doc)
        for name, values in self.start_places.items():
            if name == joints.ANGLES_KEY:
                continue
            if now.get(name) is None:
                continue
            if any(abs(a - b) > 1e-9 for a, b in zip(values, now[name])):
                return True
        return False

    def _report(self, moved):
        record = {"part": self.part.Name, "kind": self.kind, "moved": moved}
        if self.joint is not None:
            record["joint"] = self.joint.Name
            record["values"] = joints.value(self.joint)
        if self.blocked_by is not None:
            record["contact"] = [p.Name for p in self.blocked_by]
        _STATE["last"] = record
        if moved:
            log(
                "Component Drag: %s moved%s"
                % (
                    self.part.Label,
                    (
                        (
                            " (%s at %.2f°, %.3f mm)"
                            % ((self.joint.Label,) + tuple(record["values"]))
                        )
                        if self.joint is not None
                        else ""
                    ),
                )
            )

    def _refresh(self):
        try:
            from . import joints_ui

            joints_ui._refresh_browser()
            Gui.updateGui()
        except Exception:
            pass
