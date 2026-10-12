# SPDX-License-Identifier: LGPL-2.1-or-later
"""Move/Copy (M) with Fusion's dialog, for bodies.

  Move Object   Bodies
  Objects       click the bodies to move (a click on a picked one drops it); bodies selected
                before M are taken at once
  Move Type     Free Move     drag the manipulator: three arrows move along X / Y / Z, three
                              curved handles turn about X / Y / Z (through the middle of the
                              bodies); or type X / Y / Z Distance and X / Y / Z Angle
                Translate     the three arrows, or X / Y / Z Distance
                Rotate        click an axis (one of the drawn origin axes, a straight edge, a
                              round edge or face), then drag the blue handle round it or type
                              the Angle
                Point to Point  click the point to move from, then the point to move to (a
                              corner, a circle's centre, the middle of a straight edge)
  Create Copy   the bodies stay; moved copies become new bodies

Live preview; OK / Enter keeps it as one "Move" step in the timeline (one undo step), Cancel /
Esc puts everything back; double-click the Move in the timeline to change it. The
manipulator is drawn over the part and grabbed even where the part is in front of it; it is
watched with a Qt timer (FreeCAD's own mouse callbacks only record the mouse). The document
side is move.py.
"""
import math
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, drag_guard, move, profile_pick, ui_icon_path, warn
from .bodies_panel import BodyPanel, edit as _edit, start as _start
from .compat import QtCore, QtWidgets
from .taskui import DistanceField

MOVE_TYPES = [
    ("Free Move", "free"),
    ("Translate", "translate"),
    ("Rotate", "rotate"),
    ("Point to Point", "point_to_point"),
    ("Point to Position", "point_to_position"),
]
AXES = (App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(0, 0, 1))
COLORS = ((0.90, 0.30, 0.30), (0.35, 0.80, 0.35), (0.30, 0.55, 1.0))
HOVER = (1.0, 0.85, 0.35)
OVERLAY_CLICK_S = 0.8


# -- the manipulator ---------------------------------------------------------------------------------
class Triad:
    """Fusion's move manipulator: three arrows (X red, Y green, Z blue) and, for Free Move,
    three curved handles that turn about those axes. on_drag(kind, index, value) while
    dragging: kind "move" (value in mm along axis `index` since the press) or "turn" (degrees
    about it since the press); on_release() at the end."""

    POLL_MS = 30
    GRAB_PIXELS = 9.0

    def __init__(self, view, center, size, turns=True, on_drag=None, on_release=None):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.center = App.Vector(center)
        self.size = float(size)
        self.turns = turns
        self.on_drag = on_drag
        self.on_release = on_release
        self._hover = None
        self._painted = None
        self._drag = None  # (kind, index)
        self._drag_center = None
        self._start = None  # value at the press (mm along the axis / angle vector)
        self._pending = None
        self._last_angle = 0.0
        self._released = False
        self._last_event = 0.0
        self.root = coin.SoAnnotation()  # on top of the part, like Fusion's manipulators
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.place = coin.SoTranslation()
        self.root.addChild(self.place)
        self.materials = {}
        for i in range(3):
            self.materials[("move", i)] = self._arrow(coin, i)
            if turns:
                self.materials[("turn", i)] = self._turn_handle(coin, i)
        self._paint()
        self.set_center(self.center)
        view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]
        self._timer = QtCore.QTimer()
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    # -- drawing -------------------------------------------------------------------------------
    def _material(self, coin, color):
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(*[c * 0.55 for c in color])
        return material

    def _arrow(self, coin, index):
        s = self.size
        sep = coin.SoSeparator()
        material = self._material(coin, COLORS[index])
        sep.addChild(material)
        turn = coin.SoRotation()  # cylinders and cones point along +Y
        rot = App.Rotation(App.Vector(0, 1, 0), AXES[index])
        turn.rotation.setValue(*rot.Q)
        sep.addChild(turn)
        shaft_at = coin.SoTranslation()
        shaft_at.translation.setValue(0, 0.5 * s, 0)
        sep.addChild(shaft_at)
        shaft = coin.SoCylinder()
        shaft.radius.setValue(0.025 * s)
        shaft.height.setValue(0.8 * s)
        sep.addChild(shaft)
        tip_at = coin.SoTranslation()
        tip_at.translation.setValue(0, 0.5 * s, 0)
        sep.addChild(tip_at)
        tip = coin.SoCone()
        tip.bottomRadius.setValue(0.08 * s)
        tip.height.setValue(0.22 * s)
        sep.addChild(tip)
        self.root.addChild(sep)
        return material

    def _frame(self, index):
        """Two directions spanning the plane a turn handle lies in (perpendicular to its axis)."""
        u = AXES[(index + 1) % 3]
        v = AXES[(index + 2) % 3]
        return u, v

    def arc_points(self, index, steps=16):
        u, v = self._frame(index)
        r = 0.6 * self.size
        return [
            u * (r * math.cos(a)) + v * (r * math.sin(a))
            for a in [math.radians(15 + 60.0 * i / steps) for i in range(steps + 1)]
        ]

    def _turn_handle(self, coin, index):
        sep = coin.SoSeparator()
        material = self._material(coin, COLORS[index])
        sep.addChild(material)
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(4.0)
        sep.addChild(style)
        points = self.arc_points(index)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
        sep.addChild(coords)
        line = coin.SoLineSet()
        line.numVertices.setValue(len(points))
        sep.addChild(line)
        ball_at = coin.SoTranslation()
        mid = self.ball(index)
        ball_at.translation.setValue(mid.x, mid.y, mid.z)
        sep.addChild(ball_at)
        ball = coin.SoSphere()
        ball.radius.setValue(0.07 * self.size)
        sep.addChild(ball)
        self.root.addChild(sep)
        return material

    def ball(self, index):
        """Where a turn handle's ball is, relative to the centre."""
        u, v = self._frame(index)
        r = 0.6 * self.size
        a = math.radians(45.0)
        return u * (r * math.cos(a)) + v * (r * math.sin(a))

    def tip(self, index):
        """The end of an arrow (3D, global)."""
        return self.center + AXES[index] * self.size

    def ball_point(self, index):
        return self.center + self.ball(index)

    def set_center(self, center):
        self.center = App.Vector(center)
        self.place.translation.setValue(self.center.x, self.center.y, self.center.z)

    def _paint(self):
        active = self._drag or self._hover
        if active == self._painted:
            return
        self._painted = active
        for key, material in self.materials.items():
            color = HOVER if key == active else COLORS[key[1]]
            material.diffuseColor.setValue(*color)
            material.emissiveColor.setValue(*[c * 0.55 for c in color])

    # -- the mouse ---------------------------------------------------------------------------------
    def _screen(self, point):
        x, y = self.view.getPointOnViewport(point)
        return float(x), float(y)

    def handle_at(self, position):
        """("move"|"turn", axis index) of the handle under the mouse, or None."""
        px, py = float(position[0]), float(position[1])
        best = None
        for i in range(3):
            a = self._screen(self.center + AXES[i] * (0.15 * self.size))
            b = self._screen(self.tip(i))
            d = _segment_distance((px, py), a, b)
            if d <= self.GRAB_PIXELS and (best is None or d < best[0]):
                best = (d, ("move", i))
            if not self.turns:
                continue
            points = [self._screen(self.center + p) for p in self.arc_points(i, 8)]
            for p, q in zip(points, points[1:]):
                d = _segment_distance((px, py), p, q)
                if d <= self.GRAB_PIXELS and (best is None or d < best[0]):
                    best = (d, ("turn", i))
            bx, by = self._screen(self.ball_point(i))
            d = math.hypot(px - bx, py - by)
            if d <= self.GRAB_PIXELS + 3 and (best is None or d < best[0]):
                best = (d, ("turn", i))
        return best[1] if best else None

    def _along(self, position, index):
        """mm along axis `index` (from the centre) closest to the mouse ray, or None when the
        axis points at the eye."""
        point, direction = profile_pick.mouse_ray(self.view, tuple(position))
        axis = AXES[index]
        b = axis.dot(direction)
        denom = 1.0 - b * b
        if denom < 0.02:
            return None
        w0 = self._origin() - point
        return (b * direction.dot(w0) - axis.dot(w0)) / denom

    def _angle(self, position, index):
        """Angle (degrees) of the mouse about axis `index` in its plane, or None edge-on."""
        axis = AXES[index]
        u, v = self._frame(index)
        hit = profile_pick.ray_plane(self.view, tuple(position), self._origin(), axis)
        if hit is None:
            return None
        point, _t = hit
        w = point - self._origin()
        if w.Length < 1e-9:
            return None
        _, direction = profile_pick.mouse_ray(self.view, tuple(position))
        if abs(direction.dot(axis)) < 0.15:
            return None
        return math.degrees(math.atan2(w.dot(v), w.dot(u)))

    def _origin(self):
        """Where the manipulator was when the drag began: it follows the bodies while they
        move, but the drag is measured from where the hand took it."""
        return self._drag_center if self._drag_center is not None else self.center

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1":
                return
            position = info["Position"]
            if info.get("State") == "DOWN":
                handle = self.handle_at(position)
                if handle is None:
                    return
                self._drag_center = App.Vector(self.center)
                kind, index = handle
                start = (
                    self._along(position, index) if kind == "move" else self._angle(position, index)
                )
                if start is None:
                    return
                self._drag = handle
                self._start = start
                self._last_angle = 0.0
                self._last_event = time.time()
            elif self._drag is not None:
                self._drag = None
                self._released = True
                self._last_event = time.time()
        except Exception as exc:
            warn("move handle: %s" % exc)

    def _drag_done(self):
        self._drag_center = None

    def _moved(self, info):
        try:
            position = info["Position"]
            if self._drag is None:
                self._hover = self.handle_at(position)
                return
            self._last_event = time.time()
            kind, index = self._drag
            if kind == "move":
                value = self._along(position, index)
                if value is not None:
                    self._pending = (kind, index, value - self._start)
            else:
                angle = self._angle(position, index)
                if angle is not None:
                    delta = angle - self._start
                    # follow the hand past half a turn: the step nearest the last one
                    delta += 360.0 * round((self._last_angle - delta) / 360.0)
                    self._last_angle = delta
                    self._pending = (kind, index, delta)
        except Exception as exc:
            warn("move handle: %s" % exc)

    def dragging(self):
        return self._drag is not None

    def busy(self, seconds=0.6):
        """True while dragging and just after: the click is the handle's, not a pick."""
        return self._drag is not None or time.time() - self._last_event < seconds

    def _poll(self):
        try:
            if Gui.ActiveDocument is None:
                self._timer.stop()
                return
            drag_guard.end_lost_drag(self, idle=None)  # its release never came (drag_guard)
            self._paint()
            pending, self._pending = self._pending, None
            if pending is not None and self.on_drag:
                self.on_drag(*pending)
            if self._released and self._drag is None:
                self._released = False
                self._drag_done()
                if self.on_release:
                    self.on_release()
        except Exception as exc:
            warn("move drag: %s" % exc)

    def remove(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        for kind, callback in getattr(self, "callbacks", []):
            try:
                self.view.removeEventCallback(kind, callback)
            except Exception:
                pass
        self.callbacks = []
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


def _segment_distance(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


# -- the dialog ---------------------------------------------------------------------------------------
class MovePanel(BodyPanel):
    title = "Move/Copy"
    icon = "move"
    needs_pick = (move.NeedsPick,)

    def __init__(self, doc, feature=None):
        self.options = move.with_defaults({})
        self.steps = []
        if feature is not None:
            try:
                self.options, self.steps = move.read(feature)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self.triad = None
        self.turn_handle = None
        self.axis_picker = None
        self._overlay_time = 0.0
        self._drag_start = None
        super().__init__(doc, "Move" if feature is None else "Edit Move", feature is not None)
        self.target = self.steps[0] if self.steps else None
        self._show_options()
        if feature is not None:
            self.activate("objects")
            self._make_handles()
        else:
            self.activate("objects")
            self.start_from_selection()
            self.dirty = True
            self._timer.stop()
            self._recompute()

    # -- form ----------------------------------------------------------------------------------------
    def build_form(self):
        self.move_object, _ = self.combo(
            "Move Object", [("Bodies", "bodies")], "bodies", lambda: None
        )
        self.selection_box("objects", "Objects")
        self.move_type, _ = self.combo(
            "Move Type", MOVE_TYPES, self.options["move_type"], self._type_changed
        )
        self.distance_fields = []
        self.distance_captions = []
        for key, label in (("dx", "X Distance"), ("dy", "Y Distance"), ("dz", "Z Distance")):
            field = DistanceField(self.options[key], on_change=lambda v, k=key: self._field(k, v))
            caption = QtWidgets.QLabel(label)
            self.layout.addRow(caption, field.widget)
            self.distance_fields.append(field)
            self.distance_captions.append(caption)
        self.angle_fields = []
        self.angle_captions = []
        for key, label in (("rx", "X Angle"), ("ry", "Y Angle"), ("rz", "Z Angle")):
            field = DistanceField(
                self.options[key], unit="deg", on_change=lambda v, k=key: self._field(k, v)
            )
            caption = QtWidgets.QLabel(label)
            self.layout.addRow(caption, field.widget)
            self.angle_fields.append(field)
            self.angle_captions.append(caption)
        self.selection_box("axis", "Axis")
        self.angle = DistanceField(
            self.options["angle"], unit="deg", on_change=lambda v: self._field("angle", v)
        )
        self.angle_caption = QtWidgets.QLabel("Angle")
        self.layout.addRow(self.angle_caption, self.angle.widget)
        self.selection_box("from_point", "Origin Point")
        self.selection_box("to_point", "Target Point")
        self.position_fields = []
        self.position_captions = []
        for key, label in (("px", "X"), ("py", "Y"), ("pz", "Z")):
            field = DistanceField(self.options[key], on_change=lambda v, k=key: self._field(k, v))
            caption = QtWidgets.QLabel(label)
            self.layout.addRow(caption, field.widget)
            self.position_fields.append(field)
            self.position_captions.append(caption)
        self.copy, _ = self.check_box(
            "Create Copy",
            self.options["copy"],
            self._copy_toggled,
            "Leave the bodies where they are and move copies of them (new bodies)",
        )

    def _show_options(self):
        self._quiet = True
        try:
            from . import hole_common

            hole_common.set_combo(self.move_type, self.options["move_type"])
            for field, key in zip(self.distance_fields, ("dx", "dy", "dz")):
                field.set_value(self.options[key])
            for field, key in zip(self.angle_fields, ("rx", "ry", "rz")):
                field.set_value(self.options[key])
            self.angle.set_value(self.options["angle"])
            for field, key in zip(self.position_fields, ("px", "py", "pz")):
                field.set_value(self.options[key])
            self.copy.setChecked(bool(self.options["copy"]))
        finally:
            self._quiet = False
        self._update_visibility()
        self._show_picks()

    def _update_visibility(self):
        kind = self.options["move_type"]
        for field, caption in zip(self.distance_fields, self.distance_captions):
            self.show_row(field.widget, caption, kind in ("free", "translate"))
        for field, caption in zip(self.angle_fields, self.angle_captions):
            self.show_row(field.widget, caption, kind == "free")
        self.show_row(self.fields["axis"].widget, self.captions["axis"], kind == "rotate")
        self.show_row(self.angle.widget, self.angle_caption, kind == "rotate")
        points = kind in ("point_to_point", "point_to_position")
        self.show_row(self.fields["from_point"].widget, self.captions["from_point"], points)
        self.captions["from_point"].setText("Origin Point" if kind == "point_to_point" else "Point")
        self.show_row(
            self.fields["to_point"].widget, self.captions["to_point"], kind == "point_to_point"
        )
        for field, caption in zip(self.position_fields, self.position_captions):
            self.show_row(field.widget, caption, kind == "point_to_position")

    def _show_picks(self):
        from . import bodies_gui

        self.fields["objects"].set_text(bodies_gui.body_text(self.options["bodies"]))
        self.fields["axis"].set_text(self.options["axis_label"] if self.options["axis_dir"] else "")
        self.fields["from_point"].set_text(
            self.options["from_label"] if self.options["from_point"] else ""
        )
        self.fields["to_point"].set_text(
            self.options["to_label"] if self.options["to_point"] else ""
        )

    def _field(self, key, value):
        self._guarded(lambda: self._typed(key, value))

    def _typed(self, key, value):
        if self._quiet or self._closed:
            return
        self.options[key] = float(value)
        self.changed()
        self._place_handles()

    def _type_changed(self):
        self.options["move_type"] = self.move_type.currentData()
        self._update_visibility()
        # With no body picked yet the Objects box keeps the clicks: the first click must pick
        # the body to move, not be taken as an axis or a point (then nothing could move).
        if not self.options["bodies"] or not self._next_box():
            if self.active not in self._boxes():
                self.activate("objects")
        else:
            self.activate(self._next_box())
        self._make_handles()
        self.changed()

    def _next_box(self):
        """The box the move type still waits for once bodies are picked, or None."""
        kind = self.options["move_type"]
        if kind == "rotate" and self.options["axis_dir"] is None:
            return "axis"
        if kind in ("point_to_point", "point_to_position") and self.options["from_point"] is None:
            return "from_point"
        if kind == "point_to_point" and self.options["to_point"] is None:
            return "to_point"
        return None

    def _boxes(self):
        kind = self.options["move_type"]
        boxes = ["objects"]
        if kind == "rotate":
            boxes.append("axis")
        if kind == "point_to_point":
            boxes += ["from_point", "to_point"]
        if kind == "point_to_position":
            boxes.append("from_point")
        return boxes

    def _copy_toggled(self):
        self.options["copy"] = self.copy.isChecked()
        self.changed()

    def cleared(self, name):
        if name == "objects":
            self.options["bodies"] = []
        elif name == "axis":
            self.options["axis_point"] = self.options["axis_dir"] = None
            self.options["axis_label"] = ""
        else:
            self.options[name] = None
            self.options[name.replace("point", "label")] = ""
        self._show_picks()
        self._make_handles()

    def activated(self, name):
        self._update_axis_picker()

    # -- clicks ----------------------------------------------------------------------------------------
    def picked(self, obj, short, point):
        if self._handles_busy() or time.time() - self._overlay_time < OVERLAY_CLICK_S:
            return
        if self.active == "objects":
            body = bodies.body_of(obj)
            if body is None or self._is_copy_body(body):
                return
            first = not self.options["bodies"]
            if body in self.options["bodies"]:
                self.options["bodies"].remove(body)
            else:
                self.options["bodies"].append(body)
            self._new_pivot()
            self._show_picks()
            if first and self._next_box():
                # Rotate / Point to Point chosen before the body: on to the axis or point
                # (click the Objects box to add more bodies).
                self.activate(self._next_box())
            self._make_handles()
            self.changed()
            return
        if self.active == "axis":
            found = move.axis_of(obj, short)
            step = self._step_of(bodies.body_of(obj))
            if found is not None and step is not None and not move.is_copy(step):
                back = step.Movement.inverse()  # an edge of the moved preview: where it was
                found = (back.multVec(found[0]), back.Rotation.multVec(found[1]))
            if found is None:
                self.message.setText(
                    "Pick an axis: an origin axis, a straight edge or a round edge or face."
                )
                return
            self._set_axis(found, _ref_text(obj, short))
            return
        if self.active in ("from_point", "to_point"):
            found = self._point(obj, short, point)
            if found is None:
                self.message.setText("Pick a point: a corner, an edge or a round edge's centre.")
                return
            self.options[self.active] = list(found)
            self.options[self.active.replace("point", "label")] = _ref_text(obj, short)
            self._show_picks()
            self.message.setText("")
            if self.options["move_type"] == "point_to_position" and self.active == "from_point":
                self._start_position(found)
            elif self.active == "from_point" and self.options["to_point"] is None:
                self.activate("to_point")
            self.changed()

    def _start_position(self, found):
        """Point to Position: X / Y / Z start at where the point is (nothing moves until
        a value is changed), like Fusion."""
        for field, key, value in zip(self.position_fields, ("px", "py", "pz"), found):
            self.options[key] = float(value)
            field.set_value(float(value))

    def _point(self, obj, short, point):
        """A clicked point, as it is before this move (a click on the moved preview is taken
        back to where that point was)."""
        found = _snap(obj, short, point)
        if found is None:
            found = move.point_of(obj, short)
        if found is None:
            return None
        body = bodies.body_of(obj)
        step = self._step_of(body)
        if step is not None and not move.is_copy(step):
            found = step.Movement.inverse().multVec(found)
        # 1e-9 mm: what a turn and back leaves behind is not a real offset (fields show -35,
        # not -34.99999999999999)
        return App.Vector(*[round(c, 9) + 0.0 for c in found])

    def _step_of(self, body):
        for step in self.steps:
            if bodies.alive(step) and move.moved_body(step) is body and not move.is_copy(step):
                return step
        return None

    def _is_copy_body(self, body):
        for step in self.steps:
            if bodies.alive(step) and move.is_copy(step) and move.copy_body(step) is body:
                return True
        return False

    def _set_axis(self, found, label):
        point, direction = found
        self.options["axis_point"] = list(point)
        self.options["axis_dir"] = list(direction)
        self.options["axis_label"] = label
        self._show_picks()
        self.message.setText("")
        self.activate("objects")
        self._make_handles()
        self.changed()

    def _update_axis_picker(self):
        wants = self.active == "axis" and not self._closed
        body = (self.options["bodies"] or [None])[0] or bodies.find_body(self.doc)
        if wants and self.axis_picker is None and body is not None:
            try:
                from .pattern_ui import AxisPicker

                self.axis_picker = AxisPicker(
                    self.view, body, self._axis_clicked, self._size() * 2.5
                )
            except Exception as exc:
                warn("Move: origin axes unavailable: %s" % exc)
        elif not wants and self.axis_picker is not None:
            self.axis_picker.remove()
            self.axis_picker = None

    def _axis_clicked(self, axis):
        self._overlay_time = time.time()
        QtCore.QTimer.singleShot(0, lambda: self._axis_later(axis))

    def _axis_later(self, axis):
        if self._closed:
            return
        try:
            found = move.axis_of(axis, "")
            if found is not None:
                self._set_axis(found, axis.Label)
        except Exception as exc:
            warn("Move axis: %s" % exc)

    # -- pivot and handles ------------------------------------------------------------------------------
    def _unmoved(self):
        """The bodies' solids as they are before this move (design coordinates)."""
        shapes = []
        for body in self.options["bodies"]:
            step = self._step_of(body)
            source = step.BaseFeature if step is not None else body
            try:
                shapes.append(bodies.global_shape(source))
            except Exception:
                pass
        return [s for s in shapes if not s.isNull()]

    def _size(self):
        shapes = self._unmoved()
        if not shapes:
            return 20.0
        box = shapes[0].BoundBox
        for shape in shapes[1:]:
            box.add(shape.BoundBox)
        return max(8.0, 0.45 * max(box.XLength, box.YLength, box.ZLength))

    def _new_pivot(self):
        shapes = self._unmoved()
        if not shapes:
            return
        box = shapes[0].BoundBox
        for shape in shapes[1:]:
            box.add(shape.BoundBox)
        self.options["pivot"] = list(box.Center)

    def _pivot(self):
        if self.options["pivot"] is None:
            self._new_pivot()
        return App.Vector(*(self.options["pivot"] or (0, 0, 0)))

    def _handles_busy(self):
        for handle in (self.triad, self.turn_handle):
            if handle is not None and handle.busy():
                return True
        return False

    def _make_handles(self):
        self.remove_handles(keep_picker=True)
        if self._closed or not self.options["bodies"]:
            return
        kind = self.options["move_type"]
        try:
            if kind in ("free", "translate"):
                self.triad = Triad(
                    self.view,
                    self._triad_center(),
                    self._size(),
                    turns=kind == "free",
                    on_drag=self._dragged,
                    on_release=self._released,
                )
            elif kind == "rotate" and self.options["axis_dir"] is not None:
                self._make_turn_handle()
        except Exception as exc:
            warn("Move: no manipulator: %s" % exc)

    def _triad_center(self):
        o = self.options
        return self._pivot() + App.Vector(o["dx"], o["dy"], o["dz"])

    def _make_turn_handle(self):
        from .revolve_ui import AngleHandle

        point = App.Vector(*self.options["axis_point"])
        axis = App.Vector(*self.options["axis_dir"]).normalize()
        pivot = self._pivot()
        foot = point + axis * (pivot - point).dot(axis)
        zero = pivot - foot
        if zero.Length < 1e-6:
            zero = _perpendicular(axis)
        radius = max(zero.Length, self._size())
        zero.normalize()
        self.turn_handle = AngleHandle(
            foot,
            axis,
            zero,
            radius,
            self.options["angle"],
            self._size() * 0.35,
            on_drag=self._turned,
            on_release=lambda _v: self._released(),
        )

    def _place_handles(self):
        if self.triad is not None:
            self.triad.set_center(self._triad_center())
        if (
            self.turn_handle is not None
            and abs(self.turn_handle.angle() - self.options["angle"]) > 1e-9
        ):
            self.turn_handle.set_angle(self.options["angle"])

    def _dragged(self, kind, index, value):
        if self._closed:
            return
        self.busy()
        keys = ("dx", "dy", "dz") if kind == "move" else ("rx", "ry", "rz")
        if self._drag_start is None:
            self._drag_start = dict(
                (k, self.options[k]) for k in ("dx", "dy", "dz", "rx", "ry", "rz")
            )
        key = keys[index]
        self.options[key] = self._drag_start[key] + value
        fields = self.distance_fields if kind == "move" else self.angle_fields
        fields[index].set_value(self.options[key])
        if kind == "move" and self.triad is not None:
            self.triad.set_center(self._triad_center())
        self.changed()

    def _turned(self, value):
        if self._closed:
            return
        self.busy()
        self.options["angle"] = float(value)
        self.angle.set_value(value)
        self.changed()

    def _released(self):
        self._drag_start = None
        self.busy()
        self.changed()

    def remove_handles(self, keep_picker=False):
        for name in ("triad", "turn_handle") + (() if keep_picker else ("axis_picker",)):
            handle = getattr(self, name, None)
            if handle is not None:
                try:
                    handle.remove()
                except Exception:
                    pass
                setattr(self, name, None)

    # -- preview --------------------------------------------------------------------------------------
    def apply(self):
        if not self.options["bodies"]:
            if self.steps and not self.editing:
                for step in self.steps:
                    move.remove(step)
                self.steps = []
                self.target = None
            move.check(self.options)
        try:
            move.transform(self.options)
        except move.NeedsPick:
            if self.steps and not self.editing:
                for step in self.steps:
                    move.remove(step)
                self.steps = []
                self.target = None
            raise
        self.steps = move.build(self.options, self.steps)
        self.target = self.steps[0] if self.steps else None

    def after_recompute(self):
        for step in self.steps:
            if not bodies.alive(step):
                continue
            body = move.copy_body(step) if move.is_copy(step) else bodies.body_of(step)
            if body is not None:
                bodies.show_tip(body)
        self._place_handles()

    def preview_steps(self):
        return [s for s in self.steps if bodies.alive(s)]

    def can_finish(self):
        if not self.options["bodies"]:
            return "Select the bodies to move."
        try:
            move.transform(self.options)
        except move.MoveError as exc:
            return str(exc)
        if not self.steps:
            return self.error or "Nothing to move yet."
        return ""


def _snap(obj, short, point):
    """Fusion lights up the corner nearest the pointer: a click on an edge or a face close to
    one of its corners takes that corner (design coordinates), else None."""
    if point is None or not short.startswith(("Edge", "Face")):
        return None
    try:
        element = obj.Shape.getElement(short).copy()
        parent = obj.getParentGeoFeatureGroup()
        if parent is not None:
            element.transformShape(parent.getGlobalPlacement().toMatrix(), True)
    except Exception:
        return None
    if short.startswith("Edge"):
        reach = 0.12 * element.Length
    else:
        reach = 0.12 * element.BoundBox.DiagonalLength
    best = None
    for vertex in _corners(element):
        d = (vertex.Point - point).Length
        if d <= reach and (best is None or d < best[0]):
            best = (d, vertex.Point)
    return App.Vector(best[1]) if best else None


def _corners(element):
    """The corners a person sees on an edge or a face. The start point OpenCASCADE gives a
    full circle, and the ends of a cylinder's seam line, are not corners: a click on a
    round edge takes its centre (Fusion), never that hidden point."""
    edges = [element] if element.ShapeType == "Edge" else list(element.Edges)
    real = []
    for edge in edges:
        if edge.isClosed():
            continue  # a full circle or ellipse: its one vertex is a seam
        if element.ShapeType == "Face" and sum(1 for e in edges if e.isSame(edge)) > 1:
            continue  # a seam line (it bounds the face twice)
        real.append(edge)
    found = []
    for edge in real:
        for vertex in edge.Vertexes:
            if not any(vertex.isSame(v) for v in found):
                found.append(vertex)
    return found


def _perpendicular(axis):
    other = App.Vector(1, 0, 0) if abs(axis.x) < 0.9 else App.Vector(0, 1, 0)
    out = axis.cross(other)
    out.normalize()
    return out


def _ref_text(obj, sub):
    if not sub:
        return obj.Label
    body = bodies.body_of(obj)
    where = body.Label if body is not None else obj.Label
    return "%s of %s" % (sub.rstrip("0123456789"), where)


class MoveCommand:
    def GetResources(self):
        return {
            "MenuText": "Move/Copy",
            "ToolTip": "Move or copy bodies: drag the arrows and turn handles, type distances "
            "and angles, rotate about an axis, or point to point (M)",
            "Pixmap": ui_icon_path("move"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if _in_sketch():
                Gui.runCommand("SciForge_SketchMove")  # M in a sketch moves sketch curves
                return
            _start(MovePanel)
        except Exception as exc:
            warn("Move/Copy could not start: %s" % exc)


def _in_sketch():
    try:
        edit = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument is not None else None
        obj = edit.Object if edit is not None else None
        return obj is not None and obj.TypeId == "Sketcher::SketchObject"
    except Exception:
        return False


def edit(feature):
    _edit(MovePanel, feature)


COMMANDS = {"SciForge_Move": MoveCommand}
EDITORS = {"SciForge::MoveCopy": edit}
