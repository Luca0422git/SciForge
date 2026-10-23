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

from . import bodies, drag_guard, handle_look, handles3d, increments, move, move_face
from . import profile_pick
from . import protractor, taskui, ui_icon_path, warn
from .bodies_panel import BodyPanel, edit as _edit, start as _start
from .compat import QtCore, QtWidgets
from .taskui import BoxCarrier, DistanceField, ValueBoxes

MOVE_TYPES = [
    ("Free Move", "free"),
    ("Translate", "translate"),
    ("Rotate", "rotate"),
    ("Point to Point", "point_to_point"),
    ("Point to Position", "point_to_position"),
]
# Fusion's Move Object: bodies here, components in component_move_ui.ComponentMovePanel
# (the dialog switches between the two when the choice changes).
MOVE_OBJECTS = [("Bodies", "bodies"), ("Components", "components"), ("Faces", "faces")]
# The values that stay when Move Object changes (Fusion keeps the move type and values).
CARRIED = ("move_type",) + move.NUMBERS
AXES = (App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(0, 0, 1))
COLORS = ((0.90, 0.30, 0.30), (0.35, 0.80, 0.35), (0.30, 0.55, 1.0))
HOVER = (1.0, 0.85, 0.35)
OVERLAY_CLICK_S = 0.8


# -- the manipulator ---------------------------------------------------------------------------------
class Triad(BoxCarrier):
    """Fusion's move manipulator: three arrows (X red, Y green, Z blue) and, for Free Move,
    three curved handles that turn about those axes. on_drag(kind, index, value) while
    dragging: kind "move" (value in mm along axis `index` since the press) or "turn" (degrees
    about it since the press); on_release() at the end.

    Fusion shows the value of the handle in use beside it (the distance along the arrow
    being dragged, the angle of the turn handle): the triad carries one value box
    (taskui.BoxCarrier) and moves it to the handle last dragged or under the mouse;
    on_handle((kind, index)) tells the dialog which one that is, so it gives the box that
    handle's field (X / Y / Z Distance or Angle)."""

    POLL_MS = 30
    GRAB_PIXELS = 9.0

    def __init__(
        self, view, center, size, turns=True, on_drag=None, on_release=None, on_handle=None
    ):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.center = App.Vector(center)
        # The triad keeps its size on the screen (handle_look_core.TRIAD_PX from the centre
        # to an arrow's tip) whatever the part or the zoom: `size` (its old size in mm) is
        # no longer used; self.size is that length in mm now.
        self.size_hint = float(size)
        self.turns = turns
        self.on_drag = on_drag
        self.on_release = on_release
        self.on_handle = on_handle
        self.in_use = None  # (kind, index): the handle the value box sits beside
        self._hover = None
        self._painted = None
        self._drag = None  # (kind, index); None or False when no drag
        self._drag_center = None
        self._start = None  # value at the press (mm along the axis / angle vector)
        self._pending = None
        self._last_angle = 0.0
        self._released = False
        self._last_event = 0.0
        self._mark = None  # the snap angle a turn sits on (protractor)
        self._wheel = protractor.Wheel()  # shown while a turn handle is held
        # on top of the part, like Fusion's manipulators (handle_look), drawn in pixels
        self.root = handle_look.top_root(coin)
        self.place = coin.SoTranslation()
        self.root.addChild(self.place)
        self.shapes = coin.SoSeparator()  # in pixels from the centre
        self.pixels = handle_look.PixelScale(coin, self.shapes, view, self.center)
        self.root.addChild(self.pixels.node)
        self.materials = {}  # (kind, index): its paint (set(hot))
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
        self._move_poll = taskui.poll_on_move(self._poll)  # dragged: polled on every mouse move

    # -- drawing -------------------------------------------------------------------------------
    @property
    def size(self):
        """Centre to an arrow's tip (mm) at the triad's place in the view now."""
        return handle_look.mm(self.view, self.center, handle_look.core.TRIAD_PX)

    def _arrow(self, coin, index):
        """Axis `index`'s arrow (pixels, from the centre), in its axis colour."""
        core = handle_look.core
        sep = coin.SoSeparator()
        turn = coin.SoRotation()  # the arrow is built along +Y
        rot = App.Rotation(App.Vector(0, 1, 0), AXES[index])
        turn.rotation.setValue(*rot.Q)
        sep.addChild(turn)
        arrow, paint = handle_look.arrow_shape(
            coin,
            COLORS[index],
            HOVER,
            length=core.TRIAD_PX,
            start=core.TRIAD_GAP * core.TRIAD_PX,
        )
        sep.addChild(arrow)
        self.shapes.addChild(sep)
        return paint

    def _frame(self, index):
        """Two directions spanning the plane a turn handle lies in (perpendicular to its axis)."""
        u = AXES[(index + 1) % 3]
        v = AXES[(index + 2) % 3]
        return u, v

    def arc_points(self, index, steps=16, radius=None):
        """A turn handle's arc relative to the centre (mm; `radius` in other units)."""
        u, v = self._frame(index)
        r = handle_look.core.TRIAD_RING * self.size if radius is None else radius
        return [
            u * (r * math.cos(a)) + v * (r * math.sin(a))
            for a in [math.radians(15 + 60.0 * i / steps) for i in range(steps + 1)]
        ]

    def _turn_handle(self, coin, index):
        """Turn handle `index`: an arc in its axis colour and a disc on it (pixels)."""
        core = handle_look.core
        sep = coin.SoSeparator()
        arc = handle_look.Line(coin, COLORS[index], width=core.TRIAD_RING_WIDTH_PX)
        ring = core.TRIAD_RING * core.TRIAD_PX
        arc.set_points([(p.x, p.y, p.z) for p in self.arc_points(index, radius=ring)])
        sep.addChild(arc.node)
        ball_at = coin.SoTranslation()
        mid = self.ball(index, radius=ring)
        ball_at.translation.setValue(mid.x, mid.y, mid.z)
        sep.addChild(ball_at)
        disc, disc_paint = handle_look.disc_shape(coin, COLORS[index], HOVER)
        sep.addChild(disc)
        self.shapes.addChild(sep)
        return _TurnPaint(arc, disc_paint, COLORS[index])

    def ball(self, index, radius=None):
        """Where a turn handle's disc is, relative to the centre (mm)."""
        u, v = self._frame(index)
        r = handle_look.core.TRIAD_RING * self.size if radius is None else radius
        a = math.radians(45.0)
        return u * (r * math.cos(a)) + v * (r * math.sin(a))

    def tip(self, index):
        """The end of an arrow (3D, global)."""
        return self.center + AXES[index] * self.size

    def ball_point(self, index):
        return self.center + self.ball(index)

    # -- the value box (taskui.BoxCarrier) ------------------------------------------------------
    def box_geometry(self):
        """The handle in use as the box sees it: an arrow from just off the centre to its
        tip (anchored at its middle), or a turn handle's arc (anchored at its ball)."""
        if not self.in_use:
            raise ValueError("no handle in use yet")
        return self._part(self.in_use)

    def box_active(self):
        return bool(self._drag)

    def _part(self, handle):
        """(anchor, tail, tip, radius) of one of the triad's handles (see box_geometry)."""
        kind, index = handle
        core = handle_look.core
        if kind == "move":
            tail = self.center + AXES[index] * (core.TRIAD_GAP * self.size)
            tip = self.tip(index)
            width = handle_look.mm(self.view, self.center, core.half_width_px("arrow"))
            return (tail + tip) * 0.5, tail, tip, width
        points = self.arc_points(index, 8)
        return (
            self.ball_point(index),
            self.center + points[0],
            self.center + points[-1],
            handle_look.mm(self.view, self.center, core.half_width_px("disc")),
        )

    def box_avoid(self):
        """The box never covers the triad's other arrows, arcs and balls (they stay
        grabbable, and the mouse over them moves the box to them)."""
        parts = []
        for kind in ("move", "turn") if self.turns else ("move",):
            for index in range(3):
                if (kind, index) == self.in_use:
                    continue
                parts.append(self._part((kind, index)))
                if kind == "turn":
                    ball = self.ball_point(index)
                    radius = handle_look.mm(
                        self.view, ball, handle_look.core.half_width_px("disc")
                    )
                    parts.append((ball, ball, ball, radius))
        return parts

    def use(self, handle):
        """Make `handle` ((kind, index)) the one the value box sits beside."""
        if not handle or handle == self.in_use:
            return
        if handle[0] == "turn" and not self.turns:
            return
        self.in_use = handle
        if self.on_handle is not None:
            try:
                self.on_handle(handle)
            except Exception as exc:
                warn("move value box: %s" % exc)

    def attach_box(self, box, owner=None, key=None):
        """A box for another handle: the one shown before steps aside (one box at a time,
        beside the handle in use), unless the user is typing in it."""
        old = self.value_box
        if old is not None and old is not box:
            try:
                if not old.hasFocus():
                    old.hide()
            except RuntimeError:
                pass
        super().attach_box(box, owner, key)

    def set_center(self, center):
        self.center = App.Vector(center)
        self.place.translation.setValue(self.center.x, self.center.y, self.center.z)

    def _paint(self):
        active = self._drag or self._hover
        if active == self._painted:
            return
        self._painted = active
        for key, paint in self.materials.items():
            paint.set(key == active)

    # -- the mouse ---------------------------------------------------------------------------------
    def _screen(self, point):
        x, y = self.view.getPointOnViewport(point)
        return float(x), float(y)

    def handle_at(self, position):
        """("move"|"turn", axis index) of the handle under the mouse, or None."""
        px, py = float(position[0]), float(position[1])
        best = None
        core = handle_look.core
        size = self.size
        arrow_reach = core.grab_px("arrow", at_least=self.GRAB_PIXELS)
        disc_reach = core.grab_px("disc", at_least=self.GRAB_PIXELS + 3)
        for i in range(3):
            a = self._screen(self.center + AXES[i] * (core.TRIAD_GAP * size))
            b = self._screen(self.center + AXES[i] * size)
            d = _segment_distance((px, py), a, b)
            if d <= arrow_reach and (best is None or d < best[0]):
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
            if d <= disc_reach and (best is None or d < best[0]):
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
                # FreeCAD's selection keeps the release of a drag that ends over the part
                # (the moved body follows the handle there); Qt's release is watched too
                # (handles3d.ReleaseWatch, which ends the drag with _drag = False).
                handles3d.watch_release(self)
            elif self._drag:
                self._drag = None
                self._released = True
                self._last_event = time.time()
                handles3d.stop_watching(self)
        except Exception as exc:
            warn("move handle: %s" % exc)

    def _drag_done(self):
        self._drag_center = None

    def _wheel_frame(self, index):
        """(centre, axis, zero, radius) of the protractor of turn handle `index`: about its
        axis, angle 0 where the hand took it, as big as the turn handles' arcs."""
        u, v = self._frame(index)
        a = math.radians(self._start or 0.0)
        zero = u * math.cos(a) + v * math.sin(a)
        return self._origin(), AXES[index], zero, handle_look.core.TRIAD_RING * self.size

    def _moved(self, info):
        try:
            position = info["Position"]
            if not self._drag:
                self._hover = self.handle_at(position)
                return
            self._last_event = time.time()
            kind, index = self._drag
            if kind == "move":
                value = self._along(position, index)
                if value is not None:
                    # Incremental Move (navigation bar): in steps of the increment
                    self._pending = (kind, index, increments.linear(value - self._start))
            else:
                angle = self._angle(position, index)
                if angle is not None:
                    delta = angle - self._start
                    # follow the hand past half a turn: the step nearest the last one
                    delta += 360.0 * round((self._last_angle - delta) / 360.0)
                    self._last_angle = delta
                    # 0 / 45 / 90... pull the turn, Ctrl turns freely, Incremental Move
                    # keeps its steps (protractor)
                    delta, self._mark = protractor.snap_angle(
                        self.view, delta, *self._wheel_frame(index)
                    )
                    self._pending = (kind, index, delta)
        except Exception as exc:
            warn("move handle: %s" % exc)

    def dragging(self):
        return bool(self._drag)

    def busy(self, seconds=0.6):
        """True while dragging and just after: the click is the handle's, not a pick."""
        return bool(self._drag) or time.time() - self._last_event < seconds

    def _poll(self):
        try:
            if Gui.ActiveDocument is None:
                self._timer.stop()
                return
            drag_guard.end_lost_drag(self, idle=None)  # its release never came (drag_guard)
            self._paint()
            self.pixels.update(self.view, self.center)
            self.use(self._drag or self._hover)
            if self._drag and self._drag[0] == "turn" and not self._wheel.shown():
                # the protractor wheel while a turn handle is held (made here, not in the
                # mouse callback: no nodes added while Coin traverses)
                self._wheel.show(self.view, *self._wheel_frame(self._drag[1]))
                self._wheel.update(0.0, 0.0)
            pending, self._pending = self._pending, None
            if pending is not None and pending[0] == "turn":
                self._wheel.update(pending[2], self._mark)
            if pending is not None and self.on_drag:
                self.on_drag(*pending)
            if not self._drag:
                self._wheel.hide()
            if self._released and not self._drag:
                self._released = False
                self._drag_done()
                if self.on_release:
                    self.on_release()
            if self.in_use:
                self.follow_box()
        except Exception as exc:
            warn("move drag: %s" % exc)

    def remove(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        taskui.drop_poll_on_move(self)
        self._wheel.hide()
        try:
            handles3d.stop_watching(self)
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
        self.drop_box()


class _TurnPaint:
    """A turn handle's colours: its arc and its disc, lit together under the mouse."""

    def __init__(self, arc, disc, colour):
        self.arc = arc
        self.disc = disc
        self.colour = colour
        self._state = None

    def set(self, hot):
        if self._state == bool(hot):
            return
        self._state = bool(hot)
        self.arc.base.rgb.setValue(*(HOVER if hot else self.colour))
        self.disc.set(hot)


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
    object_type = "bodies"  # Fusion's Move Object

    def __init__(self, doc, feature=None, carry=None, picks=None):
        self.options = move.with_defaults({"move_object": "bodies", "faces": None})
        self.steps = []
        if feature is not None:
            try:
                self.options, self.steps = self.read_feature(feature)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        if carry:
            self.options.update(carry)  # the move type and values kept from Move Object
        self.triad = None
        self.turn_handle = None
        self.axis_picker = None
        # The value box beside the handle in use (Fusion): one per field, made once.
        self.value_boxes = ValueBoxes(self)
        self._box_handle = None  # (kind, index) of the triad handle last in use
        self.marks = None  # the picked faces, shaded (Move Object Faces)
        self._overlay_time = 0.0
        self._drag_start = None
        self.setting_pivot = False  # Set Pivot: the manipulator moves, the objects stay
        self._pivot_drag_start = None
        super().__init__(doc, "Move" if feature is None else "Edit Move", feature is not None)
        self.target = self.steps[0] if self.steps else None
        self._show_options()
        if feature is not None:
            self.activate("objects")
            self._make_handles()
        else:
            self.activate("objects")
            if picks:
                self.take_picks(picks)  # Paste: the pasted objects are picked
            else:
                self.start_from_selection()
            self.dirty = True
            self._timer.stop()
            self._recompute()

    def read_feature(self, feature):
        if move_face.is_move_face(feature):
            return move_face.read(feature), [feature]
        options, steps = move.read(feature)
        options["move_object"] = "bodies"
        return options, steps

    def take_picks(self, objects):
        for obj in objects:
            try:
                self.picked(obj, "", None)
            except Exception as exc:
                warn("%s pick: %s" % (self.title, exc))

    # -- form ----------------------------------------------------------------------------------------
    def build_form(self):
        self.move_object, _ = self.combo(
            "Move Object", MOVE_OBJECTS, self._object_kind(), self._object_changed
        )
        self.move_object.setEnabled(not self.editing)  # a step keeps what it moves
        self.selection_box("objects", "Objects")
        self.move_type, _ = self.combo(
            "Move Type", MOVE_TYPES, self.options["move_type"], self._type_changed
        )
        self._pivot_form()
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
        self.show_row(self.pivot_row, self.pivot_caption, kind == "free")
        pivoting = kind == "free" and self.setting_pivot
        self.pivot_done.setVisible(pivoting)
        for field, caption in zip(self.pivot_fields, self.pivot_captions):
            self.show_row(field.widget, caption, pivoting)
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
        # Create Copy makes new bodies: it is for Bodies only (faces are moved in their body)
        self.copy.setVisible(not self._faces_mode())
        caption = self.layout.labelForField(self.copy)
        if caption is not None:
            caption.setVisible(not self._faces_mode())

    def _faces_mode(self):
        return self.options.get("move_object") == "faces"

    def _object_changed(self):
        """Move Object changed. Fusion clears the selection and keeps the move type and
        values: Bodies and Faces switch inside this dialog; Components opens the components
        dialog (component_move_ui) with them, and back."""
        wanted = self.move_object.currentData()
        if self._closed or wanted == self._object_kind():
            return
        if wanted == "components" or self.object_type == "components":
            carry = {key: self.options[key] for key in CARRIED}
            if wanted != "components":
                carry["move_object"] = wanted
            name = self.doc.Name
            QtCore.QTimer.singleShot(0, lambda: switch_object_type(self, name, wanted, carry))
            return
        self.options["move_object"] = wanted
        if not self.editing:
            for step in self.steps:
                if bodies.alive(step):
                    (move_face.remove if move_face.is_move_face(step) else move.remove)(step)
            self.steps = []
            self.target = None
        self.options["bodies"] = []
        self.options["faces"] = None
        self.options["pivot"] = None
        if self._faces_mode():
            self.options["copy"] = False
            self.copy.setChecked(False)
        self._update_visibility()
        self._show_picks()
        self.activate("objects")
        self._make_handles()
        self.changed()

    def _show_picks(self):
        from . import bodies_gui

        if self._faces_mode():
            faces = self.options.get("faces")
            count = len(faces[1]) if faces else 0
            self.fields["objects"].set_text(
                "%d face%s" % (count, "" if count == 1 else "s") if count else ""
            )
            self._show_marks()
        else:
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
        if self.options["move_type"] != "free":
            self._finish_pivot()
        self._update_visibility()
        # With no body picked yet the Objects box keeps the clicks: the first click must pick
        # the body to move, not be taken as an axis or a point (then nothing could move).
        if not self._moving() or not self._next_box():
            if self.active not in self._boxes():
                self.activate("objects")
        else:
            self.activate(self._next_box())
        self._make_handles()
        self.changed()

    # -- Set Pivot ---------------------------------------------------------------------------------
    def _pivot_form(self):
        """Fusion's Set Pivot (Free Move): press it, then click a point of the model or drag
        the manipulator's arrows (the objects stay put), or type where the pivot goes;
        Done (the check) keeps it: turns are about it from then on."""
        self.pivot_row = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(self.pivot_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.set_pivot = QtWidgets.QPushButton("Set Pivot")
        self.set_pivot.setCheckable(True)
        self.set_pivot.setToolTip(
            "Move the manipulator without moving the objects: click a corner, an edge or a "
            "round edge's centre, or drag the arrows; then Done"
        )
        self.set_pivot.toggled.connect(lambda on: self._guarded(lambda: self._pivot_toggled(on)))
        self.pivot_done = QtWidgets.QPushButton("✓ Done")
        self.pivot_done.setToolTip("Keep this pivot")
        self.pivot_done.clicked.connect(lambda *_: self._guarded(self._finish_pivot))
        row.addWidget(self.set_pivot)
        row.addWidget(self.pivot_done)
        row.addStretch(1)
        self.pivot_caption = QtWidgets.QLabel("Pivot")
        self.layout.addRow(self.pivot_caption, self.pivot_row)
        self.pivot_fields = []
        self.pivot_captions = []
        for index, label in enumerate(("Pivot X", "Pivot Y", "Pivot Z")):
            field = DistanceField(0.0, on_change=lambda v, i=index: self._pivot_typed(i, v))
            caption = QtWidgets.QLabel(label)
            self.layout.addRow(caption, field.widget)
            self.pivot_fields.append(field)
            self.pivot_captions.append(caption)

    def _pivot_toggled(self, on):
        if self._quiet:
            return
        if on:
            self._start_pivot()
        else:
            self._finish_pivot()

    def _start_pivot(self):
        if not self._moving() or self.options["move_type"] != "free":
            self._quiet = True
            self.set_pivot.setChecked(False)
            self._quiet = False
            self.message.setText("Pick what to move first, then set the pivot.")
            return
        self.setting_pivot = True
        self.message.setText("")
        self.info.setText(
            "Set Pivot: click a point of the model (a corner, an edge, a round edge's centre) "
            "or drag the arrows, then Done."
        )
        self._show_pivot_values()
        self._update_visibility()
        self._make_handles()

    def _finish_pivot(self):
        if not self.setting_pivot:
            return
        self.setting_pivot = False
        self._pivot_drag_start = None
        self._quiet = True
        try:
            self.set_pivot.setChecked(False)
        finally:
            self._quiet = False
        self.info.setText("")
        self._update_visibility()
        self._make_handles()

    def _moving(self):
        """What the dialog moves: the bodies, or the picked faces (Move Object Faces); the
        components in the components dialog."""
        if self._faces_mode():
            faces = self.options.get("faces")
            return list(faces[1]) if faces and faces[1] else []
        return self.options["bodies"]

    def _object_kind(self):
        """Move Object as shown: components in the components dialog, else bodies or faces."""
        if self.object_type != "bodies":
            return self.object_type
        return self.options.get("move_object") or "bodies"

    def _show_pivot_values(self):
        center = self._triad_center()
        self._quiet = True
        try:
            for field, value in zip(self.pivot_fields, (center.x, center.y, center.z)):
                field.set_value(round(value, 9) + 0.0)
        finally:
            self._quiet = False

    def _pivot_typed(self, index, value):
        if self._quiet or self._closed or not self.setting_pivot:
            return
        target = self._triad_center()
        coords = [target.x, target.y, target.z]
        coords[index] = float(value)
        self._guarded(lambda: self._set_pivot_at(App.Vector(*coords)))

    def _set_pivot_at(self, point):
        """Put the manipulator at `point` (design coordinates, where it is shown) without
        moving anything: the pivot becomes the point it was before the move, and the
        distances change so the result stays the same (components_core.pivot_shift)."""
        from . import components_core

        place = move.transform(self.options)
        old = self._pivot()
        new = place.inverse().multVec(App.Vector(point))
        matrix = place.Rotation.toMatrix()
        rows = (
            (matrix.A11, matrix.A12, matrix.A13),
            (matrix.A21, matrix.A22, matrix.A23),
            (matrix.A31, matrix.A32, matrix.A33),
        )
        distances = (self.options["dx"], self.options["dy"], self.options["dz"])
        shifted = components_core.pivot_shift(rows, distances, tuple(old), tuple(new))
        self.options["pivot"] = [round(c, 9) + 0.0 for c in new]
        self._pivot_user = True
        self._quiet = True
        try:
            for field, key, value in zip(self.distance_fields, ("dx", "dy", "dz"), shifted):
                self.options[key] = round(value, 9) + 0.0
                field.set_value(self.options[key])
        finally:
            self._quiet = False
        if self.triad is not None:
            self.triad.set_center(self._triad_center())
        self._show_pivot_values()
        self.changed()

    def _pivot_picked(self, obj, short, point):
        """A click while setting the pivot: the corner, edge middle or centre under it."""
        found = _snap(obj, short, point)
        if found is None:
            found = move.point_of(obj, short)
        if found is None and point is not None:
            found = App.Vector(point)
        if found is None:
            self.message.setText("Click a corner, an edge or a face for the pivot.")
            return
        self.message.setText("")
        self._set_pivot_at(found)

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
            self._finish_pivot()
            self.options["bodies"] = []
            self.options["faces"] = None
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
        if self.setting_pivot:
            self._pivot_picked(obj, short, point)
            return
        if self.active == "objects" and self._faces_mode():
            self._face_picked(obj, short)
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

    # -- Move Object Faces (modify-2) --------------------------------------------------------
    def _has_objects(self):
        return bool(self._moving())

    def _first_body(self):
        if self._faces_mode():
            faces = self.options.get("faces")
            return bodies.body_of(faces[0]) if faces else None
        return (self.options["bodies"] or [None])[0]

    def _face_base(self, body):
        """The step the moved faces are on: the step before this Move, else the body's end."""
        for step in self.steps:
            if bodies.alive(step) and move_face.is_move_face(step) and bodies.body_of(step) is body:
                return step.BaseFeature
        return body.Tip

    def _face_picked(self, obj, short):
        """Fusion's Move Object Faces: a click on a face picks it (again: drops it). The faces
        are those of one body, as it is before this Move."""
        if not short.startswith("Face"):
            self.message.setText("Move Object is Faces: click faces of a body.")
            return
        body = bodies.body_of(obj)
        if body is None:
            return
        faces = self.options.get("faces")
        if faces and bodies.body_of(faces[0]) is not body:
            self.message.setText(
                "Move the faces of one body at a time (they are on %s)."
                % bodies.body_of(faces[0]).Label
            )
            return
        base = self._face_base(body)
        if base is None or base.Shape.isNull():
            return
        name = self._base_face(obj, short, base)
        if name is None:
            self.message.setText("That face is not on the part before this Move.")
            return
        names = list(faces[1]) if faces else []
        if name in names:
            names.remove(name)
        else:
            names.append(name)
        self.options["faces"] = (base, names) if names else None
        self.message.setText("")
        first = len(names) == 1 and name in names
        self._new_pivot()
        self._show_picks()
        if first and self._next_box():
            self.activate(self._next_box())
        self._make_handles()
        self.changed()

    def _base_face(self, obj, short, base):
        """The name on `base` of the face `short` of `obj` clicked in the view (the preview
        shows the moved faces: a moved face is found back where it was)."""
        if obj is base:
            return short
        try:
            face = obj.Shape.getElement(short)
        except Exception:
            return None
        found = move_face._face_at(base.Shape, move_face._inner_point(face))
        if found is None:
            for step in self.steps:
                if bodies.alive(step) and move_face.is_move_face(step) and step is obj:
                    body = bodies.body_of(step)
                    place = body.getGlobalPlacement()
                    back = place.inverse().multiply(step.Movement.inverse()).multiply(place)
                    moved = face.copy()
                    moved.transformShape(back.toMatrix(), True)
                    found = move_face._face_at(base.Shape, move_face._inner_point(moved))
        if found is None:
            return None
        for i, candidate in enumerate(base.Shape.Faces, start=1):
            if candidate.isSame(found):
                return "Face%d" % i
        return None

    def _show_marks(self):
        try:
            if self.marks is None:
                from .pattern_ui import Marks

                self.marks = Marks(self.view)
            faces = self.options.get("faces")
            shapes = []
            if faces and self._faces_mode():
                base, names = faces
                body = bodies.body_of(base)
                place = body.getGlobalPlacement() if body is not None else App.Placement()
                try:  # the faces are shaded where the movement puts them, like in Fusion
                    place = move.transform(self.options).multiply(place)
                except Exception:
                    pass
                for name in names:
                    try:
                        face = base.Shape.getElement(name).copy()
                        face.Placement = place.multiply(face.Placement)
                        shapes.append(face)
                    except Exception:
                        continue
            self.marks.show(faces=shapes)
        except Exception as exc:
            warn("Move: picked faces not shown: %s" % exc)

    def _step_of(self, body):
        for step in self.steps:
            if move_face.is_move_face(step):
                continue  # a Move of faces: points on the rest of the part did not move
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

    def _axis_frame(self):
        """Whose origin axes are drawn while the Axis box waits."""
        return self._first_body() or bodies.find_body(self.doc)

    def _update_axis_picker(self):
        wants = self.active == "axis" and not self._closed
        body = self._axis_frame()
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
        """The bodies' solids as they are before this move (design coordinates); the picked
        faces for Move Object Faces."""
        if self._faces_mode():
            faces = self.options.get("faces")
            if not faces:
                return []
            base, names = faces
            body = bodies.body_of(base)
            place = body.getGlobalPlacement() if body is not None else App.Placement()
            found = []
            for name in names:
                try:
                    face = base.Shape.getElement(name).copy()
                    face.transformShape(place.toMatrix(), True)
                    found.append(face)
                except Exception:
                    continue
            return found
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
        if getattr(self, "_pivot_user", False) and self.options["pivot"] is not None:
            return  # a pivot set with Set Pivot stays
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
        if self._closed or not self._moving():
            return
        kind = self.options["move_type"]
        try:
            if kind in ("free", "translate"):
                self.triad = Triad(
                    self.view,
                    self._triad_center(),
                    self._size(),
                    turns=kind == "free" and not self.setting_pivot,
                    on_drag=self._dragged,
                    on_release=self._released,
                    on_handle=self._triad_handle,
                )
                last = self._box_handle
                if last and (last[0] == "move" or self.triad.turns):
                    self.triad.use(last)  # the box stays beside the handle last used
            elif kind == "rotate" and self.options["axis_dir"] is not None:
                self._make_turn_handle()
        except Exception as exc:
            warn("Move: no manipulator: %s" % exc)

    # -- the value boxes (Fusion shows the value beside the handle in use) -----------------------
    def _box_field(self, handle):
        """The dialog field a triad handle sets: X / Y / Z Distance or Angle (Pivot X / Y / Z
        while Set Pivot moves the manipulator)."""
        kind, index = handle
        if kind == "move":
            return (self.pivot_fields if self.setting_pivot else self.distance_fields)[index]
        return self.angle_fields[index]

    def _triad_handle(self, handle):
        """The triad's handle in use changed: its box (its field's value) goes beside it."""
        if self._closed or self.triad is None:
            return
        self._box_handle = handle
        field = self._box_field(handle)
        key = "%s%s%d" % (
            "pivot_" if self.setting_pivot and handle[0] == "move" else "",
            handle[0],
            handle[1],
        )
        self.value_boxes.attach(
            self.triad,
            key,
            lambda: field.widget.text(),
            lambda text: self._box_typed(field, text),
        )

    def _box_typed(self, field, text):
        """A value typed in a handle's box: as if typed in its field (a plain number is in
        the field's unit)."""
        if self._closed:
            return
        try:
            value = field.parse(text.strip().lstrip("="))
        except ValueError as exc:
            self.message.setText("⚠ %s" % exc)
            return
        self.message.setText("")
        field.take(value)

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
        field = self.angle
        self.value_boxes.attach(
            self.turn_handle,
            "angle",
            lambda: field.widget.text(),
            lambda text: self._box_typed(field, text),
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
        if self.setting_pivot:
            if kind != "move":
                return
            if self._pivot_drag_start is None:
                self._pivot_drag_start = App.Vector(self._triad_center())
            self._set_pivot_at(self._pivot_drag_start + AXES[index] * value)
            return
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
        self._pivot_drag_start = None
        self.busy()
        self.changed()

    def remove_handles(self, keep_picker=False):
        if not keep_picker and self.marks is not None:
            try:
                self.marks.remove()
            except Exception:
                pass
            self.marks = None
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
        if self._faces_mode():
            self._apply_faces()
            return
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

    def _apply_faces(self):
        """Move Object Faces: one Move step (move_face.py) in the faces' body."""

        def drop():
            if self.steps and not self.editing:
                for step in self.steps:
                    if bodies.alive(step):
                        move_face.remove(step)
                self.steps = []
                self.target = None

        try:
            move_face.check(self.options)
        except move.NeedsPick:
            drop()
            raise
        current = self.steps[0] if self.steps and bodies.alive(self.steps[0]) else None
        step = move_face.build(self.options, current)
        self.steps = [step]
        self.target = step
        self._show_marks()

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

    def show_status(self):
        super().show_status()
        if self.setting_pivot and not self.waiting:
            self.info.setText(
                "Set Pivot: click a point of the model (a corner, an edge, a round edge's "
                "centre) or drag the arrows, then Done."
            )

    def cleanup(self):
        super().cleanup()
        self.value_boxes.discard()

    def can_finish(self):
        if self._faces_mode() and not self._has_objects():
            return "Select the faces to move."
        if not self._faces_mode() and not self.options["bodies"]:
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
            _start(panel_for_selection())
        except Exception as exc:
            warn("Move/Copy could not start: %s" % exc)


def panel_for_selection():
    """Fusion's Move takes what is selected: a component selected first (a browser row)
    opens it with Move Object Components."""
    try:
        from . import components
        from .bodies_panel import preselection

        if any(components.is_component(obj) and not short for obj, short, _p in preselection()):
            from .component_move_ui import ComponentMovePanel

            return ComponentMovePanel
    except Exception as exc:
        warn("Move/Copy: %s" % exc)
    return MovePanel


def switch_object_type(panel, doc_name, wanted, carry):
    """Move Object changed: this dialog closes (nothing done yet is kept) and the dialog
    for the other kind of object opens with the move type and values."""
    try:
        if panel._closed:
            return
        panel.reject()
    except Exception as exc:
        warn("Move: %s" % exc)
        return

    def reopen():
        try:
            if doc_name not in App.listDocuments():
                return
            from .bodies_panel import _open

            if wanted == "components":
                from .component_move_ui import ComponentMovePanel as panel_class
            else:
                panel_class = MovePanel
            _open(panel_class, App.getDocument(doc_name), carry=carry)
        except Exception as exc:
            warn("Move could not switch to %s: %s" % (wanted, exc))

    QtCore.QTimer.singleShot(0, reopen)


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
EDITORS = {"SciForge::MoveCopy": edit, "SciForge::" + move_face.SCIFORGE_TYPE: edit}
