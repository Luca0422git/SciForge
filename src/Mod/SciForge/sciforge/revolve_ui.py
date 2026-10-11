# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve command with Fusion's dialog.

Profile: click inside closed sketch areas (shaded blue, as for Extrude) or on flat faces
of the part. Axis: click a line of a sketch, a straight edge of the part, a construction
axis, or one of the origin axes, which are drawn as long red / green / blue lines while
the axis is being picked (a sketch's construction lines are drawn too, dashed orange).
A click on a line always sets the axis, a click inside an area always picks a profile,
so the two can be picked in any order. Whatever is selected before Revolve starts is
taken (profiles and an axis), and the one area of a sketch just finished is taken by
itself, like Fusion.

The fields follow Fusion's Revolve: Type (Angle / Full), Direction (One Side / Two Sides
/ Symmetric), Angle (and the angle of side two), Operation (Join / Cut / Intersect / New
Body). The blue arrow next to the part turns about the axis: drag it to set the angle.
Revolving into material switches to Cut, unless you picked the operation yourself.
Problems are shown in the dialog, which then stays open.
"""
import math
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, extrude, log, preview, profile_pick, revolve, ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .taskui import DistanceField, Panel

TYPE_LABELS = [("Angle", "angle"), ("Full", "full")]
DIRECTION_LABELS = [
    ("One Side", "one_side"),
    ("Two Sides", "two_sides"),
    ("Symmetric", "symmetric"),
]
OPERATION_LABELS = [
    ("Join", "join"),
    ("Cut", "cut"),
    ("Intersect", "intersect"),
    ("New Body", "new_body"),
]
ACTIVE_STYLE = "QPushButton { background: #1f6fbf; color: white; border: 1px solid #5aa0e6; }"
HANDLE = (0.30, 0.62, 0.95)  # Fusion's manipulator blue
HANDLE_ACTIVE = (0.55, 0.80, 1.0)
HANDLE_TWO = (0.25, 0.75, 0.85)
AXIS_COLORS = {
    "X": (0.90, 0.28, 0.28),
    "Y": (0.35, 0.78, 0.35),
    "Z": (0.30, 0.52, 0.98),
    "construction": (0.95, 0.62, 0.22),
}
AXIS_HOVER = (0.55, 0.80, 1.0)
AXIS_PICKED = (0.12, 0.53, 0.90)
PICK_PIXELS = 8.0  # how near a drawn axis a click must be (viewport pixels)
ON_LINE_PIXELS = 4.0  # this near, the drawn axis wins over what else is under the mouse


def _combo(pairs, current):
    box = QtWidgets.QComboBox()
    for label, value in pairs:
        box.addItem(label, value)
    _set_combo(box, current)
    return box


def _set_combo(box, value):
    for i in range(box.count()):
        if box.itemData(i) == value:
            box.setCurrentIndex(i)
            return


def _safe(method):
    """Dialog reactions (Qt slots) never let an exception out: it would print a traceback
    in the Report view. It is logged (SciForge's Diagnostics) and shown in the dialog."""
    import functools

    @functools.wraps(method)
    def wrapper(self, *args):
        try:
            return method(self, *args)
        except Exception as exc:
            warn("revolve: %s" % exc)
            try:
                self.message.setText("⚠ %s" % exc)
            except Exception:
                pass
        return None

    return wrapper


class SelectionField:
    """Fusion's selection box: shows what is picked, blue while it waits for clicks in
    the 3D view (click it to make it the one), with an x to clear it."""

    def __init__(self, panel, name, empty):
        self.panel = panel
        self.name = name
        self.empty = empty
        self.widget = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(self.widget)
        row.setContentsMargins(0, 0, 0, 0)
        self.button = QtWidgets.QPushButton(empty)
        self.button.setCheckable(True)
        self.button.setObjectName("SciForgeRevolve_" + name)
        self.button.clicked.connect(self._clicked)
        self.clear = QtWidgets.QToolButton()
        self.clear.setText("✕")
        self.clear.setToolTip("Clear")
        self.clear.setObjectName("SciForgeRevolve_clear_" + name)
        self.clear.clicked.connect(self._cleared)
        row.addWidget(self.button, 1)
        row.addWidget(self.clear)

    def _clicked(self, *_):
        try:
            self.panel.activate(self.name)
        except Exception as exc:
            warn("revolve field: %s" % exc)

    def _cleared(self, *_):
        try:
            self.panel.clear_field(self.name)
        except Exception as exc:
            warn("revolve field: %s" % exc)

    def set_active(self, active):
        self.button.setChecked(active)
        self.button.setStyleSheet(ACTIVE_STYLE if active else "")

    def set_text(self, text):
        self.button.setText(text or self.empty)


# -- the angle handle ----------------------------------------------------------------------------
class AngleHandle:
    """Fusion's revolve manipulator: a blue ball with an arrow next to the part that
    travels round the axis, and a thin arc showing the angle swept. It sits `radius` from
    the axis at `center`, at angle 0 along `zero`; positive angles turn right-handed about
    `axis`, like the revolve itself. The arrow points the way the angle grows (`pointing`
    -1 for side two).

    Like Fusion's manipulators it is drawn on top of the part and can be grabbed even
    where the part is in front of it, so it is not a Coin dragger (Coin only lets the
    nearest object take a click, and its dragger callbacks run Python without its lock).
    FreeCAD's own mouse callbacks (view.addEventCallback, safe) only record where the
    mouse is; a Qt timer applies the angle, as taskui.ArrowDragger does."""

    POLL_MS = 30
    GRAB_PIXELS = 14.0

    def __init__(
        self,
        center,
        axis,
        zero,
        radius,
        angle,
        size,
        color=HANDLE,
        pointing=1.0,
        on_drag=None,
        on_release=None,
    ):
        from pivy import coin

        self.coin = coin
        self.view = Gui.ActiveDocument.ActiveView
        self.center = App.Vector(center)
        self.axis = App.Vector(axis).normalize()
        self.zero = App.Vector(zero).normalize()
        self.side = self.axis.cross(self.zero)
        self.radius = float(radius)
        self.size = float(size)
        self.color = color
        self.pointing = 1.0 if pointing >= 0 else -1.0
        self.on_drag = on_drag
        self.on_release = on_release
        self._value = float(angle)
        self._shown = None  # the angle the drawing shows
        self._pending = None  # the angle the mouse asks for (set by the mouse callbacks)
        self._released = False
        self._drag = False
        self._offset = 0.0
        self._last_pos = None
        self._last_event = 0.0
        self._hover = False
        self._painted_hover = None
        self.root = coin.SoAnnotation()  # drawn over the part, like Fusion's handles
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.material = coin.SoMaterial()
        self.root.addChild(self.material)
        self.arc_coords = coin.SoCoordinate3()
        self.arc_lines = coin.SoLineSet()
        arc = coin.SoSeparator()
        arc_style = coin.SoDrawStyle()
        arc_style.lineWidth.setValue(1.5)
        arc.addChild(arc_style)
        arc.addChild(self.arc_coords)
        arc.addChild(self.arc_lines)
        self.root.addChild(arc)
        self.place = coin.SoTransform()
        self.root.addChild(self.place)
        self.root.addChild(self._arrow(coin))
        self._paint()
        self._draw()
        self.view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", self.view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", self.view.addEventCallback("SoLocation2Event", self._moved)),
        ]
        self._timer = QtCore.QTimer()
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _arrow(self, coin):
        """The ball to grab and an arrow along the circle (local +Y), at the origin."""
        s = self.size
        sep = coin.SoSeparator()
        ball = coin.SoSphere()
        ball.radius.setValue(0.3 * s)
        sep.addChild(ball)
        turn = coin.SoRotationXYZ()  # the cylinder and cone point along +Y
        turn.axis.setValue(coin.SoRotationXYZ.Z)
        turn.angle.setValue(0.0 if self.pointing > 0 else math.pi)
        sep.addChild(turn)
        shaft_move = coin.SoTranslation()
        shaft_move.translation.setValue(0.0, 0.55 * s, 0.0)
        sep.addChild(shaft_move)
        shaft = coin.SoCylinder()
        shaft.radius.setValue(0.09 * s)
        shaft.height.setValue(0.7 * s)
        sep.addChild(shaft)
        tip_move = coin.SoTranslation()
        tip_move.translation.setValue(0.0, 0.35 * s + 0.2 * s, 0.0)
        sep.addChild(tip_move)
        tip = coin.SoCone()
        tip.bottomRadius.setValue(0.25 * s)
        tip.height.setValue(0.45 * s)
        sep.addChild(tip)
        return sep

    # -- geometry ------------------------------------------------------------------------------
    def point_at(self, degrees):
        """Where the handle's ball is at `degrees` (3D, global)."""
        a = math.radians(degrees)
        return self.center + (self.zero * math.cos(a) + self.side * math.sin(a)) * self.radius

    def _tangent(self, degrees):
        a = math.radians(degrees)
        return self.zero * -math.sin(a) + self.side * math.cos(a)

    def angle(self):
        return self._value

    def set_angle(self, degrees):
        """Show the handle at this angle (typed in the dialog)."""
        self._value = float(degrees)
        self._pending = None
        self._draw()

    def _draw(self):
        if self._shown is not None and abs(self._shown - self._value) < 1e-9:
            return
        self._shown = self._value
        p = self.point_at(self._value)
        self.place.translation.setValue(p.x, p.y, p.z)
        x = self._tangent(self._value).cross(self.axis)  # outward
        y = self._tangent(self._value)
        z = self.axis
        matrix = App.Matrix(x.x, y.x, z.x, 0, x.y, y.y, z.y, 0, x.z, y.z, z.z, 0, 0, 0, 0, 1)
        self.place.rotation.setValue(*App.Placement(matrix).Rotation.Q)
        steps = max(2, int(abs(self._value) / 5.0) + 1)
        points = [self.point_at(self._value * i / float(steps)) for i in range(steps + 1)]
        self.arc_coords.point.setValues(0, len(points), [(q.x, q.y, q.z) for q in points])
        self.arc_coords.point.setNum(len(points))
        self.arc_lines.numVertices.setValue(len(points))

    def _paint(self):
        if self._painted_hover == (self._hover or self._drag):
            return
        self._painted_hover = self._hover or self._drag
        color = HANDLE_ACTIVE if self._painted_hover else self.color
        self.material.diffuseColor.setValue(*color)
        self.material.emissiveColor.setValue(color[0] * 0.5, color[1] * 0.5, color[2] * 0.5)

    # -- the mouse -------------------------------------------------------------------------------
    def _screen(self, point):
        x, y = self.view.getPointOnViewport(point)
        return float(x), float(y)

    def hit(self, position):
        """True if the mouse at `position` (viewport pixels) is on the ball."""
        try:
            bx, by = self._screen(self.point_at(self._value))
            edge = self.point_at(self._value) + self.axis * (0.3 * self.size)
            ex, ey = self._screen(edge)
            reach = max(self.GRAB_PIXELS, math.hypot(ex - bx, ey - by) + 4.0)
            return math.hypot(float(position[0]) - bx, float(position[1]) - by) <= reach
        except Exception:
            return False

    def _absolute(self, position, near):
        """The angle under the mouse where its ray meets the handle's circle plane, or
        None when that plane is seen nearly edge-on."""
        point, direction = profile_pick.mouse_ray(self.view, tuple(position))
        denom = direction.dot(self.axis)
        if abs(denom) < 0.2:
            return None
        t = (self.center - point).dot(self.axis) / denom
        v = point + direction * t - self.center
        if v.Length < 1e-9:
            return None
        raw = math.degrees(math.atan2(v.dot(self.side), v.dot(self.zero)))
        return _nearest_turn(raw, near)

    def _incremental(self, position, current):
        """Edge-on view: the mouse moving along the arrow's direction on screen."""
        if self._last_pos is None:
            return current
        x0, y0 = self._screen(self.point_at(current))
        x1, y1 = self._screen(self.point_at(current + 1.0))
        tx, ty = x1 - x0, y1 - y0
        length2 = tx * tx + ty * ty
        if length2 < 1e-6:
            return current
        dx = float(position[0]) - self._last_pos[0]
        dy = float(position[1]) - self._last_pos[1]
        return current + (dx * tx + dy * ty) / length2

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1":
                return
            position = info["Position"]
            if info.get("State") == "DOWN":
                if self.hit(position) and time.time() - _GRAB["time"] > 0.05:
                    _GRAB["time"] = time.time()  # one press moves one handle (they can meet)
                    self._drag = True
                    self._last_event = time.time()
                    self._last_pos = (float(position[0]), float(position[1]))
                    start = self._absolute(position, self._value)
                    self._offset = 0.0 if start is None else start - self._value
            elif self._drag:
                self._drag = False
                self._released = True
                self._last_event = time.time()
        except Exception as exc:
            warn("revolve handle: %s" % exc)

    def _moved(self, info):
        try:
            position = info["Position"]
            if not self._drag:
                self._hover = self.hit(position)
                return
            self._last_event = time.time()
            current = self._pending if self._pending is not None else self._value
            value = self._absolute(position, current + self._offset)
            if value is None:
                value = self._incremental(position, current)
            else:
                value -= self._offset
            self._last_pos = (float(position[0]), float(position[1]))
            self._pending = value
        except Exception as exc:
            warn("revolve handle: %s" % exc)

    def dragging(self):
        return self._drag

    def busy(self, seconds=0.6):
        """True while dragging and just after: the click is the handle's, not a pick."""
        return self._drag or time.time() - self._last_event < seconds

    def _poll(self):
        try:
            if Gui.ActiveDocument is None:
                self._timer.stop()  # the document was closed under the dialog
                return
            self._paint()
            pending = self._pending
            if pending is not None and abs(pending - self._value) > 1e-6:
                self._value = pending
                self._draw()
                if self.on_drag:
                    self.on_drag(pending)
            if self._released and not self._drag:
                self._released = False
                self._pending = None
                if self.on_release:
                    self.on_release(self._value)
        except Exception as exc:
            warn("revolve drag: %s" % exc)

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


_GRAB = {"time": 0.0}  # when a handle last took a press


def _nearest_turn(raw, near):
    """raw + k * 360 closest to `near` (so the angle can go past 180, to a full turn)."""
    k = round((near - raw) / 360.0)
    return raw + 360.0 * k


# -- clickable axes ----------------------------------------------------------------------------
class AxisPicker:
    """The origin axes (and the construction lines of sketches) as long coloured lines
    you can click, like Create Sketch's big plane squares. They light up under the mouse;
    a click is matched to them by distance on screen. Drawn on top of the part so an axis
    inside it can still be seen and clicked."""

    def __init__(self, view, lines, on_pick, blocked=None, competing=None):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.on_pick = on_pick
        self.blocked = blocked  # (position) -> True when another handle takes the click
        self.competing = competing  # (position) -> True when something else is there
        self.lines = []  # [ref, kind, start, end, switch, material, style]
        self.root = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        for ref, kind, start, end in lines:
            self.lines.append(self._line(ref, kind, start, end))
        self.hovered = None
        self.picked = None
        self.show_all = True
        self.usable = lambda line: True
        self.extra = None  # the picked axis when it is not one of the drawn lines
        self.last_click = 0.0
        view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]
        self._paint_all()

    def _line(self, ref, kind, start, end):
        coin = self.coin
        switch = coin.SoSwitch()
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        style = coin.SoDrawStyle()
        if kind == "construction":
            style.linePattern.setValue(0xF0F0)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, 2, [(start.x, start.y, start.z), (end.x, end.y, end.z)])
        lineset = coin.SoLineSet()
        lineset.numVertices.setValue(2)
        sep.addChild(material)
        sep.addChild(style)
        sep.addChild(coords)
        sep.addChild(lineset)
        switch.addChild(sep)
        self.root.addChild(switch)
        return [ref, kind, App.Vector(start), App.Vector(end), switch, material, style]

    def _same(self, a, b):
        return a is not None and b is not None and a[0] is b[0] and a[1] == b[1]

    def _visible(self, line):
        if self._same(line[0], self.picked):
            return True
        return self.show_all and self.usable(line)

    def _paint(self, line):
        ref, kind, _s, _e, switch, material, style = line
        picked = self._same(ref, self.picked)
        visible = self._visible(line)
        switch.whichChild = 0 if visible else -1
        if picked:
            color, width = AXIS_PICKED, 4.0
        elif line is self.hovered:
            color, width = AXIS_HOVER, 4.0
        else:
            color, width = AXIS_COLORS.get(kind, AXIS_COLORS["construction"]), 2.0
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(*color)
        style.lineWidth.setValue(width)

    def _paint_all(self):
        for line in self.lines:
            self._paint(line)

    def set_picked(self, ref, segment=None):
        """Show `ref` as the picked axis. An axis that is not one of the drawn lines (a
        sketch line, an edge of the part) is drawn along `segment` = (start, end)."""
        self.picked = ref
        if self.extra is not None:
            try:
                self.root.removeChild(self.extra[4])
            except Exception:
                pass
            self.extra = None
        known = any(self._same(line[0], ref) for line in self.lines)
        if ref is not None and not known and segment is not None:
            self.extra = self._line(ref, "picked", segment[0], segment[1])
            self.extra[6].lineWidth.setValue(4.0)
            self.extra[5].diffuseColor.setValue(*AXIS_PICKED)
            self.extra[5].emissiveColor.setValue(*AXIS_PICKED)
            self.extra[4].whichChild = 0
        self._paint_all()

    def set_show_all(self, show):
        if show != self.show_all:
            self.show_all = show
            self._paint_all()

    def set_usable(self, usable):
        """Only lines for which usable(line) is True are offered (an axis square to the
        profile cannot be revolved about, so it is not drawn)."""
        self.usable = usable
        self._paint_all()

    def line_at(self, position):
        """The line (as in self.lines) within a few pixels of the mouse, or None. Right
        on a drawn axis, the axis wins; only near it, whatever else is under the mouse
        (a profile area, a sketch line, the part) wins: that is what the person aims at."""
        try:
            px, py = float(position[0]), float(position[1])
        except Exception:
            return None
        best = None
        for line in self.lines:
            if not self._visible(line):
                continue
            try:
                ax, ay = self.view.getPointOnViewport(line[2])
                bx, by = self.view.getPointOnViewport(line[3])
            except Exception:
                continue
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            t = 0.0 if length2 < 1e-9 else ((px - ax) * dx + (py - ay) * dy) / length2
            t = max(0.0, min(1.0, t))
            cx, cy = ax + dx * t, ay + dy * t
            distance = math.hypot(px - cx, py - cy)
            if distance <= PICK_PIXELS and (best is None or distance < best[0]):
                best = (distance, line)
        if best is None:
            return None
        if best[0] > ON_LINE_PIXELS and self.competing is not None and self.competing(position):
            return None
        return best[1]

    def _moved(self, info):
        try:
            hit = self.line_at(info["Position"])
            if hit is not self.hovered:
                previous, self.hovered = self.hovered, hit
                if previous is not None:
                    self._paint(previous)
                if hit is not None:
                    self._paint(hit)
        except Exception as exc:
            warn("axis hover: %s" % exc)

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            if self.blocked is not None and self.blocked(info["Position"]):
                return
            hit = self.line_at(info["Position"])
            if hit is not None:
                self.last_click = time.time()
                ref = hit[0]
                QtCore.QTimer.singleShot(0, lambda: self.on_pick(ref))
        except Exception as exc:
            warn("axis pick: %s" % exc)

    def clicked_recently(self, seconds=0.6):
        return time.time() - self.last_click < seconds

    def remove(self):
        for kind, callback in self.callbacks:
            try:
                self.view.removeEventCallback(kind, callback)
            except Exception:
                pass
        self.callbacks = []
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass
        self.lines = []


class _RegionPicker(profile_pick.ProfilePicker):
    """Extrude's profile picker, except that a click on a line (an axis line or a sketch
    line / part edge under the mouse) is left to the axis: in Revolve those are axes."""

    def __init__(self, view, sketches, on_pick, occluder=None, on_line=None):
        self._on_line = on_line
        super().__init__(view, sketches, on_pick, occluder=occluder)

    def _button(self, info):
        try:
            if self._on_line is not None and self._on_line(info.get("Position")):
                return
        except Exception:
            pass
        super()._button(info)


# -- what is selected before the command starts ------------------------------------------------
def _is_axis_pick(obj, short):
    if obj is None:
        return False
    if obj.TypeId in revolve.LINE_TYPES:
        return True
    if extrude.is_sketch(obj) and (short in revolve.SKETCH_AXES or short.startswith("Axis")):
        return True
    return short.startswith("Edge")


def selected(body):
    """(profiles, axis or None) from the selection, as Fusion takes them at the start."""
    used = profile_pick.used_sketches(body.Document) if body is not None else set()
    profiles, axis = [], None
    for obj, short in profile_pick.picks():
        if _is_axis_pick(obj, short):
            if axis is None:
                try:
                    axis = revolve.axis_from_pick(obj, short)
                except revolve.RevolveError:
                    pass
            continue
        if extrude.is_sketch(obj):
            if short.startswith("InternalFace"):
                profiles.append((obj, short))
                continue
            if short.startswith("Vertex"):
                continue
            try:
                hidden = not obj.ViewObject.Visibility
            except Exception:
                hidden = False
            if obj.Name in used and hidden:
                continue  # a leftover selection, not a pick
            try:
                areas = extrude.regions(obj)
            except Exception:
                areas = []
            if len(areas) == 1:
                profiles.append((obj, areas[0][0]))
        elif short.startswith("Face"):
            try:
                face = obj.Shape.getElement(short)
            except Exception:
                continue
            if face.Surface.TypeId == "Part::GeomPlane":
                profiles.append((obj, short))
    return extrude.normalize(profiles), axis


def newest_single_region(body):
    """The only area of the newest sketch no feature uses yet (Fusion picks a sketch's
    single profile by itself), or None."""
    if body is None:
        return None
    used = profile_pick.used_sketches(body.Document)
    for obj in reversed(body.Group):
        if extrude.is_sketch(obj) and obj.Name not in used:
            try:
                found = extrude.regions(obj)
            except Exception:
                return None
            return (obj, found[0][0]) if len(found) == 1 else None
    return None


# -- the dialog ------------------------------------------------------------------------------------
class RevolvePanel(Panel):
    title = "Revolve"
    icon = "revolve"
    last = None
    auto_pick = True

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Revolve" if feature is None else "Edit Revolve")
        RevolvePanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.target = feature
        self.editing = feature is not None
        self.body = commands.find_body() if feature is None else revolve.owner_body(feature)
        self.profiles = []
        self.axis = None
        self.options = dict(revolve.DEFAULTS)
        self.user_picked_operation = feature is not None
        self.error = ""
        self.dirty = False
        self._geometry_changed = False
        self.active = "profiles"
        self.handles = {}
        self.picker = None
        self.axes = None
        self._normal = None
        self.observer = None
        self._quiet = False
        if feature is not None:
            try:
                self.profiles, self.axis, read = revolve.read(feature)
                self.options.update(read)
                self.profiles = extrude.expand_whole(self.profiles)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._shown = []
        if feature is not None:
            self._show_sketches()
        self._build_form()
        self._show_options()
        self._watch()
        if feature is not None:
            self._refresh_picks()
            self._make_handles()
        else:
            self._start()

    def _show_sketches(self):
        """While a revolve is edited its sketches are shown, so a line of them can be
        clicked as the new axis (Fusion shows them too). They hide again at the end."""
        sketches = [obj for obj, _ in self.profiles if extrude.is_sketch(obj)]
        if self.axis is not None and extrude.is_sketch(self.axis[0]):
            sketches.append(self.axis[0])
        for sketch in sketches:
            try:
                if sketch.ViewObject is not None and not sketch.ViewObject.Visibility:
                    sketch.ViewObject.Visibility = True
                    self._shown.append(sketch)
            except Exception:
                pass

    def _hide_shown(self):
        for sketch in self._shown:
            try:
                sketch.ViewObject.Visibility = False
            except Exception:
                pass
        self._shown = []

    # -- form -------------------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.fields = {
            "profiles": SelectionField(self, "profiles", "Select profiles"),
            "axis": SelectionField(self, "axis", "Select axis"),
        }
        form.addRow("Profile", self.fields["profiles"].widget)
        form.addRow("Axis", self.fields["axis"].widget)
        self.hint = QtWidgets.QLabel(
            "Click inside sketch areas (shaded blue) or on flat faces for the profile.\n"
            "Click a line, an edge or an origin axis to turn it about."
        )
        self.hint.setWordWrap(True)
        form.addRow(self.hint)
        self.picked_text = QtWidgets.QLabel("")
        self.picked_text.setWordWrap(True)
        form.addRow(self.picked_text)
        self.type = _combo(TYPE_LABELS, self.options["type"])
        self.type.setObjectName("SciForgeRevolve_type")
        form.addRow("Type", self.type)
        self.direction = _combo(DIRECTION_LABELS, self.options["direction"])
        self.direction.setObjectName("SciForgeRevolve_direction")
        self.direction_label = QtWidgets.QLabel("Direction")
        form.addRow(self.direction_label, self.direction)
        self.side1_label = QtWidgets.QLabel("<b>Side One</b>")
        form.addRow(self.side1_label)
        self.angle = DistanceField(self.options["angle"], unit="deg", on_change=self._angle_typed)
        self.angle.widget.setObjectName("SciForgeRevolve_angle")
        self.angle_label = QtWidgets.QLabel("Angle")
        form.addRow(self.angle_label, self.angle.widget)
        self.side2_label = QtWidgets.QLabel("<b>Side Two</b>")
        form.addRow(self.side2_label)
        self.angle2 = DistanceField(
            self.options["angle2"], unit="deg", on_change=self._angle2_typed
        )
        self.angle2.widget.setObjectName("SciForgeRevolve_angle2")
        self.angle2_label = QtWidgets.QLabel("Angle")
        form.addRow(self.angle2_label, self.angle2.widget)
        self.operation = _combo(OPERATION_LABELS, self.options["operation"])
        self.operation.setObjectName("SciForgeRevolve_operation")
        form.addRow("Operation", self.operation)
        self.finish_layout()
        self.type.currentIndexChanged.connect(self._kind_changed)
        self.direction.currentIndexChanged.connect(self._kind_changed)
        self.operation.activated.connect(self._operation_picked)

    def _show_options(self):
        self._quiet = True
        try:
            _set_combo(self.type, self.options["type"])
            _set_combo(self.direction, self.options["direction"])
            _set_combo(self.operation, self.options["operation"])
            self.angle.set_value(self.options["angle"])
            self.angle2.set_value(self.options["angle2"])
        finally:
            self._quiet = False
        self._update_visibility()

    def _update_visibility(self):
        full = self.type.currentData() == "full"
        two = self.direction.currentData() == "two_sides"
        for widget, show in (
            (self.direction, not full),
            (self.direction_label, not full),
            (self.side1_label, two and not full),
            (self.angle.widget, not full),
            (self.angle_label, not full),
            (self.side2_label, two and not full),
            (self.angle2.widget, two and not full),
            (self.angle2_label, two and not full),
        ):
            widget.setVisible(show)

    def _collect(self):
        self.options["type"] = self.type.currentData()
        self.options["direction"] = self.direction.currentData()
        self.options["angle"] = self.angle.value()
        self.options["angle2"] = self.angle2.value()
        self.options["operation"] = self.operation.currentData()

    # -- selection fields --------------------------------------------------------------------------
    def activate(self, name):
        """Make this selection box the one that waits for clicks in the 3D view."""
        self.active = name
        self._show_active()

    def _show_active(self):
        for name, field in self.fields.items():
            field.set_active(name == self.active)
        if self.axes is not None:
            self.axes.set_show_all(self.active == "axis" or self.axis is None)

    def clear_field(self, name):
        if name == "profiles":
            self.profiles = []
            self._picks_changed()
        else:
            self.axis = None
            self._picks_changed()
        self.activate(name)

    # -- start ---------------------------------------------------------------------------------------
    def _start(self):
        if self.body is None:
            self.message.setText("Create a sketch first (Create Sketch).")
            return
        profiles, axis = selected(self.body)
        if not profiles and self.auto_pick:
            single = newest_single_region(self.body)
            profiles = [single] if single else []
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        self.profiles = profiles
        self.axis = axis
        self._refresh_picks()
        self._next_field()
        self._collect()
        self._auto_operation()
        if self.profiles and self.axis:
            self._picks_changed()
            # Started from a selection: the preview is there when the dialog appears.
            self._timer.stop()
            self._recompute()
        elif self.profiles:
            self._check_picks()

    def _next_field(self):
        """Fusion moves on to the box that still needs a pick."""
        if not self.profiles:
            self.activate("profiles")
        elif self.axis is None:
            self.activate("axis")
        else:
            self.activate("profiles")

    def _watch(self):
        """Wait for clicks: inside a shaded sketch area, on a face, a line, an edge or an
        axis. Work is deferred to a Qt timer so nothing runs inside FreeCAD's click
        handling."""
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        view = Gui.ActiveDocument.ActiveView
        extra = [obj for obj, _ in self.profiles if extrude.is_sketch(obj)]
        if self.axis is not None and extrude.is_sketch(self.axis[0]):
            extra.append(self.axis[0])
        sketches = profile_pick.candidate_sketches(self.body, extra)
        try:
            self.axes = AxisPicker(
                view,
                revolve.overlay_lines(self.body, sketches, self._axis_length(sketches)),
                self._axis_clicked,
                blocked=self._handle_at,
                competing=self._something_else_at,
            )
        except Exception as exc:
            warn("axis lines unavailable: %s" % exc)
        try:
            self.picker = _RegionPicker(
                view,
                sketches,
                lambda sketch, sub: QtCore.QTimer.singleShot(
                    0, lambda: self._region_clicked(sketch, sub)
                ),
                occluder=self._occluder,
                on_line=self._line_under_mouse,
            )
        except Exception as exc:
            warn("profile shading unavailable: %s" % exc)

    def _axis_length(self, sketches):
        """Half the length of the drawn origin axes: past the part and the sketches."""
        box = None
        shapes = []
        base = self._base_feature()
        if base is not None and not base.Shape.isNull():
            shapes.append(revolve.to_global(base.Shape, base))
        for sketch in sketches:
            try:
                if not sketch.Shape.isNull():
                    shapes.append(revolve.to_global(sketch.Shape, sketch))
            except Exception:
                pass
        for shape in shapes:
            try:
                if box is None:
                    box = App.BoundBox(shape.BoundBox)
                else:
                    box.add(shape.BoundBox)
            except Exception:
                pass
        if box is None or not box.isValid():
            return 50.0
        origin = self.body.getGlobalPlacement().Base if self.body is not None else App.Vector()
        reach = (box.Center - origin).Length + box.DiagonalLength / 2.0
        return max(40.0, 1.4 * reach)

    def _line_under_mouse(self, position):
        """True if a click at `position` is meant for a line (an axis), not an area: a
        handle, a drawn axis, or a sketch line under the mouse. (An edge of the part does
        not count: inside an area, the area is what the person clicks.)"""
        if self._handle_at(position):
            return True
        if self.axes is not None and self.axes.line_at(position) is not None:
            return True
        try:
            info = Gui.ActiveDocument.ActiveView.getObjectInfo((int(position[0]), int(position[1])))
        except Exception:
            info = None
        if not info or not str(info.get("Component", "")).startswith("Edge"):
            return False
        obj = self.doc.getObject(str(info.get("Object", "")))
        return extrude.is_sketch(obj)

    def _something_else_at(self, position):
        """True if a profile area or anything of the model is under the mouse."""
        if self.picker is not None:
            try:
                if self.picker.region_at(position) is not None:
                    return True
            except Exception:
                pass
        try:
            info = Gui.ActiveDocument.ActiveView.getObjectInfo((int(position[0]), int(position[1])))
        except Exception:
            info = None
        return bool(info and info.get("Object"))

    def _handle_at(self, position):
        return any(handle.hit(position) for handle in self.handles.values())

    def _occluder(self):
        base = self._base_feature()
        if base is None or base.Shape.isNull():
            return None
        return revolve.to_global(base.Shape, base)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        if self.picker is not None:
            self.picker.remove()
            self.picker = None
        if self.axes is not None:
            self.axes.remove()
            self.axes = None

    # -- picks ------------------------------------------------------------------------------------------
    def _region_clicked(self, sketch, sub):
        if self._closed:
            return
        try:
            self._toggle((sketch, sub))
        except Exception as exc:
            warn("revolve pick: %s" % exc)

    def _axis_clicked(self, ref):
        if self._closed:
            return
        try:
            self._set_axis(ref)
        except Exception as exc:
            warn("revolve axis: %s" % exc)

    def _selection_changed(self):
        if self._closed:
            return
        try:
            picks = profile_pick.picks()
            if not picks:
                return
            Gui.Selection.clearSelection()
            if any(handle.busy() for handle in self.handles.values()):
                return  # the click grabbed a handle (the part under it is not a pick)
            region = self.picker is not None and self.picker.clicked_region_recently()
            axis = self.axes is not None and self.axes.clicked_recently()
            for obj, short in picks:
                self._picked(obj, short, region, axis)
        except Exception as exc:
            warn("revolve pick: %s" % exc)

    def _picked(self, obj, short, region_clicked, axis_clicked):
        if axis_clicked:
            return  # the click went to an axis line drawn by the dialog
        if region_clicked:
            return  # the click went to a profile area (FreeCAD picked what is under it)
        if _is_axis_pick(obj, short):
            ref = (obj, short)
            if short.startswith("Edge") and not extrude.is_sketch(obj):
                ref = self._base_edge(obj, short)
                if ref is None:
                    self.message.setText(
                        "⚠ That edge is made by this revolve. Pick an edge of the part or a line."
                    )
                    return
            self._set_axis(ref)
            return
        if extrude.is_sketch(obj):
            if short.startswith("InternalFace"):
                self._toggle((obj, short))
            elif short == "":
                try:
                    areas = extrude.regions(obj)
                except Exception:
                    areas = []
                if len(areas) == 1:
                    self._toggle((obj, areas[0][0]))
            return
        if short.startswith("Face"):
            ref = self._base_face(obj, short)
            if ref is None:
                self.message.setText("⚠ That face belongs to this revolve itself.")
                return
            face = ref[0].Shape.getElement(ref[1])
            if face.Surface.TypeId != "Part::GeomPlane":
                self.message.setText("⚠ Only flat faces can be revolved. Pick a flat face.")
                return
            self._toggle(ref)

    def _set_axis(self, ref):
        try:
            ref = revolve.axis_from_pick(*ref)
        except revolve.RevolveError as exc:
            self.message.setText("⚠ " + str(exc))
            return
        self.axis = ref
        self._picks_changed()
        self.activate("profiles")

    def _base_feature(self):
        """The body's solid feature just before this revolve."""
        if self.target is not None:
            if revolve.owner_body(self.target) is self._source_body():
                return self.target.BaseFeature
        body = self._source_body()
        if body is None:
            return None
        tip = body.Tip
        if tip is not None and tip is self.target:
            return tip.BaseFeature
        return tip

    def _source_body(self):
        if self.profiles:
            body = revolve.owner_body(self.profiles[0][0])
            if body is not None:
                return body
        return self.body

    def _is_ours(self, obj):
        """True for this revolve's own result (a click on the preview)."""
        base = self._base_feature()
        body = revolve.owner_body(obj)
        ours = self.target is not None and (obj is self.target or revolve.is_helper(obj))
        later = base is not None and body is revolve.owner_body(base) and obj is not base
        return ours or later

    def _base_face(self, obj, short):
        """(feature, "FaceN") as it was before this revolve, or None if only it has it."""
        if not self._is_ours(obj):
            return (obj, short)
        base = self._base_feature()
        face = profile_pick.global_face(obj, short)
        if face is None or base is None:
            return None
        name = profile_pick.face_name_in(base, face)
        return (base, name) if name else None

    def _base_edge(self, obj, short):
        """(feature, "EdgeN") as it was before this revolve, or None if only it has it."""
        if not self._is_ours(obj):
            return (obj, short)
        base = self._base_feature()
        if base is None or base.Shape.isNull():
            return None
        try:
            edge = revolve.to_global(obj.Shape.getElement(short), obj)
        except Exception:
            return None
        ends = [v.Point for v in edge.Vertexes]
        for i, candidate in enumerate(revolve.to_global(base.Shape, base).Edges, start=1):
            if candidate.Curve.TypeId != edge.Curve.TypeId or len(candidate.Vertexes) != len(ends):
                continue
            points = [v.Point for v in candidate.Vertexes]
            if all(min((p - q).Length for q in points) < 1e-6 for p in ends):
                return (base, "Edge%d" % i)
        return None

    def _toggle(self, ref):
        if any(sub == "" and obj is ref[0] for obj, sub in self.profiles):
            self.profiles = extrude.expand_whole(self.profiles)
        keys = [extrude.key(p) for p in self.profiles]
        if extrude.key(ref) in keys:
            self.profiles = [p for p in self.profiles if extrude.key(p) != extrude.key(ref)]
        else:
            self.profiles = self.profiles + [ref]
        self._picks_changed()
        if self.profiles and self.axis is None:
            self.activate("axis")

    def _refresh_picks(self):
        """Show what is picked (field texts, blue areas, highlighted faces, the axis)."""
        count = len(self.profiles)
        self.fields["profiles"].set_text("%d selected" % count if count else "")
        self.fields["axis"].set_text(revolve.axis_label(self.axis))
        words = extrude.profile_label(self.profiles) if count else ""
        self.picked_text.setText(words)
        if self.picker is not None:
            self.picker.set_selected(
                [extrude.key(p) for p in self.profiles if extrude.is_sketch(p[0])]
            )
            faces = []
            for obj, sub in self.profiles:
                if not extrude.is_sketch(obj):
                    face = profile_pick.global_face(obj, sub)
                    if face is not None:
                        faces.append(face)
            self.picker.show_faces(faces)
        if self.axes is not None:
            self.axes.set_picked(self.axis, self._axis_segment())
            self.axes.set_usable(self._usable_line)
        self._show_active()

    def _axis_segment(self):
        """(start, end) of the picked axis to draw it (global), or None."""
        if self.axis is None:
            return None
        obj, sub = self.axis
        try:
            if sub.startswith("Edge"):
                edge = revolve.to_global(obj.Shape.getElement(sub), obj)
                return edge.Vertexes[0].Point, edge.Vertexes[-1].Point
            point, direction = revolve.axis_line(self.axis)
            reach = 20.0
            if self.profiles:
                box = revolve.global_faces(self.profiles)[0].BoundBox
                reach = max(10.0, box.DiagonalLength)
            return point - direction * reach, point + direction * reach
        except Exception:
            return None

    def _usable_line(self, line):
        """False for a drawn axis square to the picked profile (FreeCAD cannot revolve
        about it, and it only gets in the way of the lines that work)."""
        if not self.profiles:
            return True
        try:
            if self._normal is None or self._normal[0] != self.profiles:
                faces = revolve.global_faces(self.profiles)
                self._normal = (list(self.profiles), extrude.face_normal(faces[0]))
            direction = line[3] - line[2]
            if direction.Length < 1e-12:
                return True
            direction.normalize()
            return abs(abs(direction.dot(self._normal[1])) - 1.0) > 1e-6
        except Exception:
            return True

    def _check_picks(self):
        """The reason the picks cannot be revolved yet, shown in the dialog ('' if fine)."""
        try:
            revolve.check_profiles(self.profiles)
            if self.axis is not None:
                revolve.check_axis(self.profiles, self.axis)
        except revolve.RevolveError as exc:
            self.error = str(exc)
            self.message.setText("⚠ " + self.error)
            return self.error
        self.error = ""
        self.message.setText("")
        return ""

    def _picks_changed(self):
        self._refresh_picks()
        if not self.profiles or self.axis is None:
            if self.target is not None and not self.editing:
                revolve.remove(self.target)
                self.target = None
                self._remove_handles()
                self.schedule()
            if self.editing:
                self.error = "Pick a profile and an axis."
                self.message.setText("⚠ " + self.error)
            else:
                self.error = ""
                if self.profiles:
                    self._check_picks()
                else:
                    self.message.setText("")
            self._remove_handles()
            return
        if self._check_picks():
            self._remove_handles()
            return
        self._changed(new_geometry=True)

    # -- changes ------------------------------------------------------------------------------------
    @_safe
    def _kind_changed(self, *_):
        if self._quiet:
            return
        direction = self.direction.currentData()
        # Angles that cannot work for the new direction are brought into range (Fusion
        # keeps the dialog valid): symmetric is per side, two sides share one turn.
        self._quiet = True
        try:
            a1 = self.angle.value()
            if direction == "symmetric" and abs(a1) > 180.0:
                self.angle.set_value(180.0 if a1 > 0 else -180.0)
            if direction == "two_sides":
                a2 = self.angle2.value()
                if a2 <= 0:
                    a2 = 90.0
                    self.angle2.set_value(a2)
                if abs(a1) + a2 > 360.0:
                    self.angle.set_value(math.copysign(360.0 - a2, a1 if a1 else 1.0))
        finally:
            self._quiet = False
        self._changed(new_geometry=True)

    @_safe
    def _angle_typed(self, value):
        if self._quiet:
            return
        handle = self.handles.get("angle")
        if handle is not None:
            handle.set_angle(self._handle_angle(value))
        self._changed()

    @_safe
    def _angle2_typed(self, value):
        if self._quiet:
            return
        handle = self.handles.get("angle2")
        if handle is not None:
            handle.set_angle(-self._side_sign() * value)
        self._changed()

    @_safe
    def _operation_picked(self, _index):
        self.user_picked_operation = True
        self._changed()

    def _side_sign(self):
        return -1.0 if self.angle.value() < 0 else 1.0

    def _handle_angle(self, value):
        """Where the side-one handle sits for an angle value."""
        if self.direction.currentData() == "symmetric":
            return abs(value)
        return value

    @_safe
    def _dragged(self, value):
        value = round(value, 1)
        if self.direction.currentData() == "symmetric":
            value = min(abs(value), 180.0)
        elif self.direction.currentData() == "two_sides":
            limit = 360.0 - self.angle2.value()
            value = max(-limit, min(limit, value))
        else:
            value = max(-360.0, min(360.0, value))
        self._quiet = True
        try:
            self.angle.set_value(value)
        finally:
            self._quiet = False
        self._changed()

    @_safe
    def _released(self, value):
        self._dragged(value)
        self._changed(new_geometry=True)  # the arrow turns round when the side changes

    @_safe
    def _dragged2(self, value):
        value = round(-self._side_sign() * value, 1)
        value = max(0.1, min(360.0 - abs(self.angle.value()), value))
        self._quiet = True
        try:
            self.angle2.set_value(value)
        finally:
            self._quiet = False
        self._changed()

    def _auto_operation(self):
        """Fusion: revolving into material becomes a cut, out of it a join (or a new body
        when there is no solid yet), unless the user picked the operation."""
        if self.user_picked_operation or not self.profiles:
            return
        base = self._base_feature()
        shape = None
        if base is not None and not base.Shape.isNull():
            shape = revolve.to_global(base.Shape, base)
        if self.axis is None and shape is not None and shape.Solids:
            return  # join or cut is known once the axis is there
        try:
            wanted = revolve.auto_operation(shape, self.profiles, self.axis, self.options)
        except Exception:
            return
        if wanted != self.options["operation"]:
            self.options["operation"] = wanted
            self._quiet = True
            _set_combo(self.operation, wanted)
            self._quiet = False

    def _changed(self, new_geometry=False):
        """Something changed: rebuild the preview shortly (coalesces drags)."""
        self._update_visibility()
        self._collect()
        self._auto_operation()
        self.dirty = True
        if new_geometry:
            self._geometry_changed = True
        self.schedule()

    def _recompute(self):
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self.show_status()
            if self._geometry_changed or self._handles_wrong():
                self._geometry_changed = False
                self._make_handles()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if not self.profiles or self.axis is None:
            return
        try:
            before = self.target
            self.target = revolve.build(
                self.profiles, self.axis, self.options, feature=self.target, hide=False
            )
            self.error = ""
            if before is None or self.target is not before:
                self._geometry_changed = True
        except revolve.RevolveError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This revolve cannot be built: %s" % exc
        if self.error and self.target is not None:
            actual = self._feature_operation()
            if actual != self.options["operation"]:
                self.options["operation"] = actual
                self._quiet = True
                _set_combo(self.operation, actual)
                self._quiet = False

    def _feature_operation(self):
        try:
            return revolve.read(self.target)[2]["operation"]
        except Exception:
            return self.options["operation"]

    def feature(self):
        return self.target

    def show_status(self):
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = _plain(preview.failure(self.target))
        self.message.setText("⚠ " + text if text else "")

    # -- handles --------------------------------------------------------------------------------------
    def _remove_handles(self):
        for handle in self.handles.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.handles = {}

    def _wanted_handles(self):
        if not self.profiles or self.axis is None or self.target is None:
            return set()
        if self.options["type"] == "full":
            return set()
        if self.options["direction"] == "two_sides":
            return {"angle", "angle2"}
        return {"angle"}

    def _handles_wrong(self):
        if any(h.dragging() for h in self.handles.values()):
            return False
        return set(self.handles) != self._wanted_handles()

    def _frame(self):
        """(center on the axis, axis, zero direction, radius, size) for the handles, global."""
        point, axis = revolve.axis_line(self.axis)
        faces = revolve.global_faces(self.profiles)
        inner = extrude.interior_point(faces[0])
        foot = point + axis * (inner - point).dot(axis)
        zero = inner - foot
        if zero.Length < 1e-9:
            zero = axis.cross(App.Vector(1, 0, 0))
            if zero.Length < 1e-9:
                zero = axis.cross(App.Vector(0, 1, 0))
        zero.normalize()
        reach = 0.0
        box = faces[0].BoundBox
        for face in faces:
            box.add(face.BoundBox)
            for vertex in face.Vertexes:
                p = vertex.Point - point
                reach = max(reach, (p - axis * p.dot(axis)).Length)
            for edge in face.Edges:
                for p in edge.discretize(16):
                    q = p - point
                    reach = max(reach, (q - axis * q.dot(axis)).Length)
        size = max(3.0, min(box.DiagonalLength * 0.2, 30.0))
        return foot, axis, zero, reach + 0.9 * size, size

    def _make_handles(self):
        """The blue arrow(s) that set the angle by dragging round the axis."""
        if self._closed:
            return
        if any(h.dragging() for h in self.handles.values()):
            return  # never pull a handle from under the mouse
        self._remove_handles()
        wanted = self._wanted_handles()
        if not wanted:
            return
        try:
            center, axis, zero, radius, size = self._frame()
            a1 = self.options["angle"]
            self.handles["angle"] = AngleHandle(
                center,
                axis,
                zero,
                radius,
                self._handle_angle(a1),
                size,
                HANDLE,
                pointing=-1.0 if a1 < 0 else 1.0,
                on_drag=self._dragged,
                on_release=self._released,
            )
            if "angle2" in wanted:
                sign = self._side_sign()
                self.handles["angle2"] = AngleHandle(
                    center,
                    axis,
                    zero,
                    radius,
                    -sign * self.options["angle2"],
                    size,
                    HANDLE_TWO,
                    pointing=-sign,
                    on_drag=self._dragged2,
                    on_release=self._dragged2,
                )
        except Exception as exc:
            warn("revolve handles unavailable: %s" % exc)

    # -- OK / Cancel ----------------------------------------------------------------------------------
    def accept(self):
        try:
            return self._accept()
        except Exception as exc:
            warn("Revolve OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        if self.target is None:
            if not self.profiles:
                text = "Pick a profile first: click inside a sketch area or on a flat face."
            elif self.axis is None:
                text = "Pick the axis: click a line, an edge or an origin axis."
            else:
                text = self.error or "This revolve cannot be built."
            self.message.setText("⚠ " + text)
            return False
        self._timer.stop()
        if self.dirty:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        preview.recompute(self.doc)
        text = _plain(preview.failure(self.target))
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        revolve.hide_sketches(self.profiles)
        self.cleanup()
        self.doc.commitTransaction()
        self._close()
        new_body = revolve.owner_body(feature)
        if new_body is not None and new_body is not self.body:
            try:
                Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", new_body)
            except Exception as exc:
                warn("could not activate %s: %s" % (new_body.Label, exc))
        log("%s done" % self.title)
        return True

    def reject(self):
        try:
            self._timer.stop()
            self.cleanup()
            self.doc.abortTransaction()
            preview.recompute(self.doc)
        except Exception as exc:
            warn("Revolve Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Revolve Cancel: %s" % exc)
        return True

    def cleanup(self):
        self._unwatch()
        self.escape.remove()
        self._remove_handles()
        self._hide_shown()
        super().cleanup()


# FreeCAD's failure texts, said the way a Fusion user needs them.
PLAIN = (
    (
        "multiple solids",
        "This would make separate solids, and a body holds one solid. Pick profiles that "
        "touch the part, or use New Body.",
    ),
    ("intersects the sketch", "The axis goes through the profile. Pick another axis."),
    (
        "perpendicular to the sketch plane",
        "The axis is square to the profile. Pick an axis that lies in the profile's plane.",
    ),
    ("not a solid", "Nothing is left: the revolve does not touch the body here."),
)


def _plain(text):
    for needle, said in PLAIN:
        if needle.lower() in (text or "").lower():
            return said
    return text


class ViewProviderRevolve:
    """View provider of the Intersect revolve (a SciForge feature)."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("revolve")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        edit(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        edit(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class RevolveCommand:
    def GetResources(self):
        return {
            "MenuText": "Revolve",
            "ToolTip": "Turn sketch areas or flat faces about an axis: angle or full turn, "
            "one side, two sides or symmetric; join, cut, intersect or new body",
            "Pixmap": ui_icon_path("revolve"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            if commands.find_body() is None:
                commands.tell("Revolve needs a sketch: use Create Sketch first.")
                return
            Gui.Control.showDialog(RevolvePanel(App.ActiveDocument))
            log("revolve started")
        except Exception as exc:
            warn("Revolve failed to start: %s" % exc)


def edit(feature):
    """Open the Revolve dialog on an existing revolve (timeline double-click)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(RevolvePanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


COMMANDS = {"SciForge_Revolve": RevolveCommand}
EDITORS = {
    "PartDesign::Revolution": edit,
    "PartDesign::Groove": edit,
    "SciForge::Revolve": edit,
}
