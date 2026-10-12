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

The fields follow Fusion's Revolve: Type (Angle / To / Full), Direction (One Side / Two
Sides / Symmetric), Angle (and the angle of side two), Operation (Join / Cut / Intersect /
New Body). The blue arrow next to the part turns about the axis: drag it to set the angle.
Type To turns as far as an object: click an origin plane (its square is drawn while the
Object box waits), a flat face, an edge or a corner of the part, a construction plane or
point; the revolve stops there and follows the object when it moves.
Revolving into material switches to Cut, unless you picked the operation yourself.
Problems are shown in the dialog, which then stays open.
"""
import math
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, extrude, log, preview, profile_pick, revolve, ui_icon_path, warn
from . import drag_guard
from .compat import QtCore, QtWidgets
from .taskui import DistanceField, Panel

TYPE_LABELS = [("Angle", "angle"), ("To", "to"), ("Full", "full")]
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
PLANE_IDLE = ((0.55, 0.65, 0.80), 0.82)  # the origin squares offered as a To object
PLANE_HOVER = ((0.55, 0.80, 1.0), 0.6)
PLANE_PICKED = ((0.30, 0.62, 0.95), 0.78)  # light: it stays shown
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


class TypeOverView:
    """Fusion: with a command open, a number typed while the mouse is over the 3D view goes
    into the command's value (its box next to the handle) and Enter finishes. FreeCAD
    took those digits as its view keys (0 isometric, 1 front, 2 top ...): the view jumped
    and the number was lost, so Enter then made the old angle. Digits, a minus sign and a
    decimal point typed while the 3D view has the keyboard now go into the dialog's value
    field (`panel.typing_field()`), replacing its text like Fusion's box; the next keys
    follow there, and Enter there is OK. remove() when the dialog closes."""

    KEYS = set("0123456789-.,")

    def __init__(self, panel):
        self.panel = panel
        guard = self

        class KeyFilter(QtCore.QObject):
            def eventFilter(self, obj, event):
                return guard._filter(event)

        self.filter = KeyFilter()
        QtWidgets.QApplication.instance().installEventFilter(self.filter)

    @staticmethod
    def _on_view(widget):
        while widget is not None:
            name = widget.metaObject().className()
            if name in ("Gui::View3DInventorViewer", "QOpenGLWidget", "Gui::View3DInventor"):
                return True
            if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox)):
                return False
            widget = widget.parentWidget()
        return False

    def _filter(self, event):
        from .compat import QtGui

        try:
            kind = event.type()
            if kind not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
                return False
            if self.panel is None or getattr(self.panel, "_closed", True):
                return False
            if not isinstance(event, QtGui.QKeyEvent):
                return False
            mods = event.modifiers()
            if mods & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.MetaModifier):
                return False
            text = event.text()
            if not text or text not in self.KEYS:
                return False
            if not self._on_view(QtWidgets.QApplication.focusWidget()):
                return False
            field = self.panel.typing_field()
            if field is None:
                return False
            event.accept()  # ShortcutOverride accepted: FreeCAD's view key does not fire
            if kind == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
                key, typed = event.key(), text
                QtCore.QTimer.singleShot(0, lambda: self._type(field, key, typed))
            return True
        except Exception:
            return False

    def _type(self, field, key, text):
        from .compat import QtGui

        try:
            if self.panel is None or getattr(self.panel, "_closed", True):
                return
            edit = field.widget.findChild(QtWidgets.QLineEdit)
            if edit is None:
                return
            field.widget.setFocus()
            edit.selectAll()
            # Sent as a key press, so the field reacts as to a person's typing.
            press = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.NoModifier, text)
            QtWidgets.QApplication.sendEvent(edit, press)
            release = QtGui.QKeyEvent(QtCore.QEvent.KeyRelease, key, QtCore.Qt.NoModifier, text)
            QtWidgets.QApplication.sendEvent(edit, release)
        except Exception as exc:
            warn("revolve typing: %s" % exc)

    def remove(self):
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self.filter)
        except Exception:
            pass
        self.panel = None


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
        self.holder = _skip_fit(coin, self.root)
        self.view.getSceneGraph().addChild(self.holder)
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
            drag_guard.end_lost_drag(self, idle=False)  # its release never came (drag_guard)
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
            self.view.getSceneGraph().removeChild(self.holder)
        except Exception:
            pass


_GRAB = {"time": 0.0}  # when a handle last took a press


def _skip_fit(coin, node):
    """`node` inside FreeCAD's SoSkipBoundingGroup: Fit (fit all) then frames the part, not
    the long axis lines or the handle drawn for picking (FreeCAD does the same for its
    rotation-centre mark)."""
    try:
        group = coin.SoType.fromName("SoSkipBoundingGroup").createInstance()
        group.addChild(node)
        return group
    except Exception:
        return node


def _nearest_turn(raw, near):
    """raw + k * 360 closest to `near` (so the angle can go past 180, to a full turn)."""
    k = round((near - raw) / 360.0)
    return raw + 360.0 * k


# -- clickable axes ----------------------------------------------------------------------------
class AxisPicker:
    """The origin axes (and the construction lines of sketches) as long coloured lines
    you can click, like Create Sketch's big plane squares. They light up under the mouse;
    a click is matched to them by distance on screen. Like Fusion's origin axes they are
    hidden where the part is in front of them, and a click there is the part's (an edge
    of the part next to a hidden axis is what the person aims at); they are long enough to
    stick out of the part, where they can always be clicked."""

    def __init__(self, view, lines, on_pick, blocked=None, competing=None):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.on_pick = on_pick
        self.blocked = blocked  # (position) -> True when another handle takes the click
        self.competing = competing  # (position) -> True when something else is there
        self.lines = []  # [ref, kind, start, end, switch, material, style]
        self.root = coin.SoSeparator()
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
        self.holder = _skip_fit(coin, self.root)
        view.getSceneGraph().addChild(self.holder)
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
        if self._hidden_at(position, best[1]):
            return None
        return best[1]

    def _hidden_at(self, position, line):
        """True if the part is in front of the drawn line under the mouse (the line is
        hidden there, so the click is the part's)."""
        try:
            info = self.view.getObjectInfo((int(position[0]), int(position[1])))
        except Exception:
            return False
        if not info or not info.get("Object") or "x" not in info:
            return False
        try:
            hit = App.Vector(float(info["x"]), float(info["y"]), float(info["z"]))
            p0, d = profile_pick.mouse_ray(self.view, tuple(position))
            a, u = App.Vector(line[2]), line[3] - line[2]
            length = u.Length
            if length < 1e-9:
                return False
            u = u * (1.0 / length)
            w0 = p0 - a
            b, dd, e = d.dot(u), d.dot(w0), u.dot(w0)
            denom = 1.0 - b * b
            s = 0.0 if denom < 1e-9 else (e - b * dd) / denom  # where the axis passes the ray
            s = max(0.0, min(length, s))
            q = a + u * s
            tol = max(0.01, 1e-4 * length)
            return (hit - p0).dot(d) < (q - p0).dot(d) - tol
        except Exception:
            return False

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
            self.view.getSceneGraph().removeChild(self.holder)
        except Exception:
            pass
        self.lines = []


class _RegionPicker(profile_pick.ProfilePicker):
    """Extrude's profile picker, except that a click on a line (an axis line or a sketch
    line / part edge under the mouse) is left to the axis: in Revolve those are axes."""

    def __init__(self, view, sketches, on_pick, occluder=None, on_line=None, paused=None):
        self._on_line = on_line
        self._paused = paused  # () -> True while another box (Type To's object) waits
        super().__init__(view, sketches, on_pick, occluder=occluder)

    def _is_paused(self):
        try:
            return bool(self._paused is not None and self._paused())
        except Exception:
            return False

    def _moved(self, info):
        if self._is_paused():
            if self.hovered is not None:
                previous, self.hovered = self.hovered, None
                self._paint(previous)
            return
        super()._moved(info)

    def _button(self, info):
        if self._is_paused():
            return  # the click is for the object to revolve to (the part under the area)
        try:
            if self._on_line is not None and self._on_line(info.get("Position")):
                return
        except Exception:
            pass
        super()._button(info)


class ToPlanes:
    """Type To: the origin planes that contain the axis, as big squares you can click (like
    Create Sketch's squares), shown while the Object box waits; and a mark on the object
    picked (the square turns blue, a point or an edge is drawn blue). Where the part is
    under the mouse the click is the part's (a face, an edge or a corner to revolve to);
    the squares are bigger than the part, so each can be clicked beside it."""

    def __init__(self, view, planes, half, on_pick):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.on_pick = on_pick
        self.planes = []  # [plane object, base, normal, u, v, material, switch]
        self.half = half
        self.shown = False
        self.picked = None
        self.hovered = None
        self.last_click = 0.0
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        squares = coin.SoSeparator()
        squares.addChild(coin.SoPolygonOffset())
        self.root.addChild(squares)
        self.mark = coin.SoSeparator()  # the picked point / edge
        self.root.addChild(self.mark)
        for plane, base, normal, u, v in planes:
            material, switch = self._square(squares, base, u, v)
            self.planes.append([plane, base, normal, u, v, material, switch])
        self.holder = _skip_fit(coin, self.root)
        view.getSceneGraph().addChild(self.holder)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]
        self.set_shown(False)

    def _square(self, parent, base, u, v):
        coin = self.coin
        h = self.half
        corners = [base + u * a * h + v * b * h for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, 4, [(p.x, p.y, p.z) for p in corners])
        faces = coin.SoFaceSet()
        faces.numVertices.setValue(4)
        outline_coords = coin.SoCoordinate3()
        loop = corners + [corners[0]]
        outline_coords.point.setValues(0, 5, [(p.x, p.y, p.z) for p in loop])
        outline = coin.SoLineSet()
        outline.numVertices.setValue(5)
        for node in (material, coords, faces, outline_coords, outline):
            sep.addChild(node)
        switch = coin.SoSwitch()
        switch.addChild(sep)
        parent.addChild(switch)
        return material, switch

    def _paint(self):
        for entry in self.planes:
            picked = self.picked is not None and entry[0] is self.picked
            if picked:
                look = PLANE_PICKED
            elif entry is self.hovered:
                look = PLANE_HOVER
            else:
                look = PLANE_IDLE
            material = entry[5]
            material.diffuseColor.setValue(*look[0])
            material.emissiveColor.setValue(*[c * 0.5 for c in look[0]])
            material.transparency.setValue(look[1])
            entry[6].whichChild = 0 if self.shown or picked else -1

    def set_shown(self, shown):
        """The squares are there only while the Object box waits; the picked one stays."""
        self.shown = bool(shown)
        if not self.shown:
            self.hovered = None
        self._paint()

    def set_target(self, target, points=None, edge=None):
        """Show what is picked: an origin plane's square in blue, a point or an edge drawn
        blue (global points)."""
        self.picked = target[0] if target and not target[1] else None
        if not any(entry[0] is self.picked for entry in self.planes):
            self.picked = None
        self.mark.removeAllChildren()
        coin = self.coin
        if points or edge:
            material = coin.SoMaterial()
            material.diffuseColor.setValue(*AXIS_PICKED)
            material.emissiveColor.setValue(*AXIS_PICKED)
            style = coin.SoDrawStyle()
            style.pointSize.setValue(9.0)
            style.lineWidth.setValue(4.0)
            self.mark.addChild(material)
            self.mark.addChild(style)
            drawn = list(edge or points)
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, len(drawn), [(p.x, p.y, p.z) for p in drawn])
            self.mark.addChild(coords)
            if edge:
                lines = coin.SoLineSet()
                lines.numVertices.setValue(len(drawn))
                self.mark.addChild(lines)
            else:
                self.mark.addChild(coin.SoPointSet())
        self.set_shown(self.shown)

    def plane_at(self, position):
        """The square under the mouse in front of the part, or None."""
        if not self.shown:
            return None
        best = None
        for entry in self.planes:
            _plane, base, normal, u, v = entry[:5]
            hit = profile_pick.ray_plane(self.view, position, base, normal)
            if hit is None:
                continue
            point, t = hit
            local = point - base
            if abs(local.dot(u)) <= self.half and abs(local.dot(v)) <= self.half:
                if best is None or t < best[1]:
                    best = (entry, t)
        if best is None:
            return None
        try:
            info = self.view.getObjectInfo((int(position[0]), int(position[1])))
        except Exception:
            info = None
        if info and str(info.get("Component", "")).startswith(("Face", "Edge", "Vertex")):
            # The part under the mouse gets the click, as in Create Sketch: its faces, edges
            # and corners are objects to revolve to as well, and the big squares would hide
            # them from most views. Each square sticks out of the part, where it is clicked.
            return None
        return best[0]

    def _moved(self, info):
        try:
            hit = self.plane_at(info["Position"])
            if hit is not self.hovered:
                self.hovered = hit
                self._paint()
        except Exception as exc:
            warn("plane hover: %s" % exc)

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            position = tuple(info["Position"])
            if profile_pick.handle_at(self.view, position):
                return
            hit = self.plane_at(position)
            if hit is not None:
                self.last_click = time.time()
                plane = hit[0]
                QtCore.QTimer.singleShot(0, lambda: self.on_pick(plane, ""))
        except Exception as exc:
            warn("plane pick: %s" % exc)

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
            self.view.getSceneGraph().removeChild(self.holder)
        except Exception:
            pass
        self.planes = []


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


def _single_region(sketch):
    """[(sketch, area)] when the sketch has exactly one closed area, else []."""
    try:
        found = extrude.regions(sketch)
    except Exception:
        return []
    return [(sketch, found[0][0])] if len(found) == 1 else []


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

    def __init__(self, doc, feature=None, sketch=None):
        super().__init__(doc, "Revolve" if feature is None else "Edit Revolve")
        RevolvePanel.last = self
        # The sketch that was open when Revolve started: its area is the profile (Fusion
        # revolves the sketch you are in), also when a feature already uses it.
        self.from_sketch = sketch
        # Fusion's keys while a command is open: Esc cancels, Enter (also over the 3D view)
        # is OK, Ctrl+Z cancels the step being made, Ctrl+S/N/O finish the dialog first.
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.typing = TypeOverView(self)
        self.target = feature
        self.editing = feature is not None
        self.body = commands.find_body() if feature is None else revolve.owner_body(feature)
        if feature is None and sketch is not None and revolve.owner_body(sketch) is not None:
            self.body = revolve.owner_body(sketch)
        self.profiles = []
        self.axis = None
        self.options = dict(revolve.DEFAULTS)
        self.options["expressions"] = {}  # formulas typed in the angle fields (FormulaInput)
        self.user_picked_operation = feature is not None
        self.error = ""
        self.formula_error = ""  # a formula typed in a field that is no value
        self._last_handle = "angle"  # the handle dragged last (typed numbers go to its value)
        self.dirty = False
        self._geometry_changed = False
        self.active = "profiles"
        self.handles = {}
        self.picker = None
        self.axes = None
        self.to_planes = None  # Type To: the origin squares and the picked object's mark
        self._to_planes_key = None
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
        # Type To: the object the revolve goes to (shown for that type only).
        self.fields["to"] = SelectionField(self, "to", "Select object")
        self.to_label = QtWidgets.QLabel("Object")
        form.addRow(self.to_label, self.fields["to"].widget)
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
        self.formulas = QtWidgets.QLabel("")  # values that follow a parameter
        self.formulas.setWordWrap(True)
        self.formulas.setStyleSheet("color: #b8c7d9;")
        form.addRow(self.formulas)
        self.finish_layout()
        # Fusion takes a parameter or a formula in every value field ("turn", "turn / 2").
        self.formula_inputs = [
            preview.FormulaInput(self, "angle", self.angle),
            preview.FormulaInput(self, "angle2", self.angle2),
        ]
        for key, field in (("angle", self.angle), ("angle2", self.angle2)):
            edit = field.widget.findChild(QtWidgets.QLineEdit)
            if edit is not None:
                edit.textEdited.connect(lambda text, key=key: self._text_edited(key, text))
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
        self.show_formulas()

    def _update_visibility(self):
        kind = self.type.currentData()
        full = kind in ("full", "to")  # no direction or angle: the angle comes from the object
        two = self.direction.currentData() == "two_sides"
        for widget, show in (
            (self.to_label, kind == "to"),
            (self.fields["to"].widget, kind == "to"),
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

    def typing_field(self):
        """The value field a number typed over the 3D view goes to (Fusion's box next to
        the handle), or None: the side-two angle right after its handle was dragged, else
        the angle; none for a full turn."""
        if self._closed or self.type.currentData() in ("full", "to"):
            return None
        if self._last_handle == "angle2" and self.angle2.widget.isVisible():
            return self.angle2
        return self.angle if self.angle.widget.isVisible() else None

    def _collect(self):
        self.options["type"] = self.type.currentData()
        self.options["direction"] = self.direction.currentData()
        self.options["angle"] = self.angle.value()
        self.options["angle2"] = self.angle2.value()
        self.options["operation"] = self.operation.currentData()

    # -- formulas (preview.FormulaInput calls formula_typed / _cleared / _failed) -----------------
    FORMULA_NAMES = {"angle": "Angle", "angle2": "Side Two angle"}

    def formula_of(self, key):
        """The formula the value field `key` follows, or ''."""
        return (self.options.get("expressions") or {}).get(key, "")

    def show_formulas(self):
        """Fusion shows the formula in the field; FreeCAD's number field cannot, so the values
        that follow a parameter are listed under the fields."""
        shown = dict(
            self.options, type=self.type.currentData(), direction=self.direction.currentData()
        )
        rows = [
            "%s = %s" % (self.FORMULA_NAMES.get(k, k), v)
            for k, v in sorted((self.options.get("expressions") or {}).items())
            if v and revolve._formula_used(k, shown)  # not for a field that is hidden
        ]
        self.formulas.setText("\n".join(rows))
        self.formulas.setVisible(bool(rows))

    def drop_formula(self, key, update=True):
        """A plain number typed or a handle dragged: the value no longer follows a formula."""
        self.formula_error = ""
        if self.options.setdefault("expressions", {}).pop(key, None) is not None:
            self.show_formulas()
            if update:
                self._changed()

    def formula_typed(self, key, text, value):
        self.formula_error = ""
        self.options.setdefault("expressions", {})[key] = text
        if key == "angle":
            self._angle_typed(value)
        else:
            self._angle2_typed(value)
        self.show_formulas()

    def formula_cleared(self, key):
        self.drop_formula(key)

    def formula_failed(self, key, text):
        # Kept until the field gets a value again (a preview rebuild must not wipe it).
        self.formula_error = text
        self.message.setText("⚠ " + text)

    def _text_edited(self, key, text):
        """A plain number typed over a formula (or over a typo) wins at once: the preview and
        OK use it without waiting for the field to be left."""
        try:
            from . import parameters

            if self._closed or not text.strip() or not parameters.is_plain_number(text):
                return
            self.drop_formula(key)  # also forgets a typo typed in a field before
        except Exception as exc:
            warn("revolve field: %s" % exc)

    # -- selection fields --------------------------------------------------------------------------
    def activate(self, name):
        """Make this selection box the one that waits for clicks in the 3D view."""
        self.active = name
        self._show_active()

    def _show_active(self):
        if self.active == "to" and self.type.currentData() != "to":
            self.active = "profiles"
        for name, field in self.fields.items():
            field.set_active(name == self.active)
        picking_to = self.active == "to"
        if self.axes is not None:
            self.axes.set_show_all(self.active == "axis" or (self.axis is None and not picking_to))
        self._show_to_planes()

    def _picking_to(self):
        """True while the Object box (Type To) waits for a click."""
        return not self._closed and self.active == "to" and self.type.currentData() == "to"

    def clear_field(self, name):
        if name == "profiles":
            self.profiles = []
        elif name == "to":
            self.options["to"] = None
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
        if not profiles and self.from_sketch is not None:
            # Never "the newest unused sketch" instead: with several areas, the user
            # clicks the ones wanted in this sketch.
            profiles = _single_region(self.from_sketch)
        elif not profiles and self.auto_pick:
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
        elif self._needs_to():
            self.activate("to")
        else:
            self.activate("profiles")

    def _needs_to(self):
        return self.type.currentData() == "to" and not self.options.get("to")

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
        if self.from_sketch is not None:
            extra.append(self.from_sketch)
        sketches = profile_pick.candidate_sketches(self.body, extra)
        try:
            self.axes = AxisPicker(
                view,
                revolve.overlay_lines(self.body, sketches, self._axis_length(sketches)),
                self._axis_clicked,
                blocked=lambda position: self._picking_to() or self._handle_at(position),
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
                paused=self._picking_to,
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
        if self.to_planes is not None:
            self.to_planes.remove()
            self.to_planes = None

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
            # Only this design's objects: a click in another open design is no pick.
            picks = [pk for pk in profile_pick.picks() if _in_doc(pk[0], self.doc)]
            if not picks:
                return
            Gui.Selection.clearSelection()
            if any(handle.busy() for handle in self.handles.values()):
                return  # the click grabbed a handle (the part under it is not a pick)
            if self.to_planes is not None and self.to_planes.clicked_recently():
                return  # the click went to an origin square (the object to revolve to)
            if self._picking_to():
                obj, short = picks[-1]
                self._to_picked(obj, short)
                return
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
        self.activate("to" if self._needs_to() else "profiles")

    def _to_clicked(self, obj, sub):
        """An origin square was clicked (deferred from the click)."""
        if self._closed:
            return
        try:
            self._to_picked(obj, sub)
        except Exception as exc:
            warn("revolve to: %s" % exc)

    def _to_picked(self, obj, short):
        """The object for Type To: a plane, a flat face, an edge or a corner of the part, a
        construction point... A click on the preview means the part as it was before."""
        if obj is not None and short and self._is_ours(obj):
            if short.startswith("Face"):
                ref = self._base_face(obj, short) or self._coplanar_base_face(obj, short)
            elif short.startswith("Edge"):
                ref = self._base_edge(obj, short)
            elif short.startswith("Vertex"):
                ref = self._base_vertex(obj, short)
            else:
                ref = None
            if ref is None:
                self.message.setText(
                    "⚠ That belongs to this revolve itself. Pick a plane, or a face or a point "
                    "of the part."
                )
                return
            obj, short = ref
        try:
            target = revolve.target_from_pick(obj, short)
            if self.profiles and self.axis is not None:
                revolve.stop_angle(revolve.global_faces(self.profiles), self.axis, target)
        except revolve.RevolveError as exc:
            self.message.setText("⚠ " + str(exc))
            return
        self.options["to"] = target
        self._refresh_picks()
        self.activate("profiles")
        self._changed(new_geometry=True)

    def _coplanar_base_face(self, obj, short):
        """(feature, "FaceN") of the part before this revolve that lies in the plane of the
        clicked face of the preview (the revolve merged its own side into that face), or
        None. Type To only needs the plane and the side of the axis the face is on."""
        base = self._base_feature()
        face = profile_pick.global_face(obj, short)
        if base is None or base.Shape.isNull() or face is None:
            return None
        if face.Surface.TypeId != "Part::GeomPlane":
            return None
        normal = extrude.face_normal(face)
        origin = face.Vertexes[0].Point
        size = max(1.0, face.BoundBox.DiagonalLength)
        inside = extrude.interior_point(face)
        best = None
        for i, candidate in enumerate(revolve.to_global(base.Shape, base).Faces, start=1):
            if candidate.Surface.TypeId != "Part::GeomPlane":
                continue
            other = extrude.face_normal(candidate)
            if abs(abs(other.dot(normal)) - 1.0) > 1e-7:
                continue
            if abs((candidate.Vertexes[0].Point - origin).dot(normal)) > 1e-6 * size:
                continue
            distance = candidate.distToShape(_vertex(inside))[0]
            if best is None or distance < best[0]:
                best = (distance, i)
        return (base, "Face%d" % best[1]) if best is not None else None

    def _base_vertex(self, obj, short):
        """(feature, "VertexN") as it was before this revolve, or None if only it has it."""
        base = self._base_feature()
        if base is None or base.Shape.isNull():
            return None
        try:
            point = revolve.to_global(obj.Shape.getElement(short), obj).Point
        except Exception:
            return None
        for i, vertex in enumerate(revolve.to_global(base.Shape, base).Vertexes, start=1):
            if (vertex.Point - point).Length < 1e-6:
                return (base, "Vertex%d" % i)
        return None

    def _to_plane_entries(self):
        """[(plane, base, normal, u, v)] of the origin planes that contain the axis (all
        three before there is an axis), global."""
        body = self._source_body()
        if body is None:
            return []
        try:
            features = body.Origin.OriginFeatures
        except Exception:
            return []
        line = None
        if self.axis is not None:
            try:
                line = revolve.axis_line(self.axis)
            except Exception:
                line = None
        entries = []
        for plane in features:
            if plane.TypeId != "App::Plane":
                continue
            placement = plane.getGlobalPlacement()
            rot = placement.Rotation
            base = App.Vector(placement.Base)
            normal = rot.multVec(App.Vector(0, 0, 1))
            if line is not None:
                point, direction = line
                if abs(normal.dot(direction)) > 1e-6 or abs((point - base).dot(normal)) > 1e-6:
                    continue
            u = rot.multVec(App.Vector(1, 0, 0))
            v = rot.multVec(App.Vector(0, 1, 0))
            entries.append((plane, base, normal, u, v))
        return entries

    def _show_to_planes(self):
        """Origin squares while the Object box waits, and the mark on the picked object."""
        wanted = self.type.currentData() == "to" and not self._closed
        key = None
        if wanted:
            body = self._source_body()
            key = (
                revolve._ref_json(self.axis) if self.axis is not None else None,
                body.Name if body is not None else None,
            )
        if self.to_planes is not None and (not wanted or key != self._to_planes_key):
            self.to_planes.remove()
            self.to_planes = None
        if not wanted:
            return
        if self.to_planes is None:
            try:
                view = Gui.ActiveDocument.ActiveView
                half = max(15.0, self._axis_length(self._sketches_shown()) / 1.4)
                self.to_planes = ToPlanes(view, self._to_plane_entries(), half, self._to_clicked)
                self._to_planes_key = key
            except Exception as exc:
                warn("origin planes unavailable: %s" % exc)
                return
        target = self.options.get("to")
        points = edge = None
        if target and target[1]:
            try:
                element = revolve.to_global(target[0].Shape.getElement(target[1]), target[0])
                if target[1].startswith("Vertex"):
                    points = [element.Point]
                elif target[1].startswith("Edge"):
                    edge = element.discretize(24)
            except Exception:
                pass
        elif target and target[0] is not None and target[0].TypeId in revolve.POINT_TYPES:
            points = [App.Vector(target[0].getGlobalPlacement().Base)]
        self.to_planes.set_target(target, points, edge)
        self.to_planes.set_shown(self._picking_to())

    def _sketches_shown(self):
        sketches = [obj for obj, _ in self.profiles if extrude.is_sketch(obj)]
        if self.from_sketch is not None:
            sketches.append(self.from_sketch)
        return sketches

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
        self.fields["to"].set_text(revolve.to_label(self.options.get("to")))
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
            target = self.options.get("to")
            if self.type.currentData() == "to" and target and target[1].startswith("Face"):
                face = profile_pick.global_face(target[0], target[1])
                if face is not None:
                    faces.append(face)  # the face the revolve goes to, blue as well
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
                self.drop_formula("angle", update=False)
            if direction == "two_sides":
                a2 = self.angle2.value()
                if a2 <= 0:
                    a2 = 90.0
                    self.angle2.set_value(a2)
                    self.drop_formula("angle2", update=False)
                if abs(a1) + a2 > 360.0:
                    self.angle.set_value(math.copysign(360.0 - a2, a1 if a1 else 1.0))
                    self.drop_formula("angle", update=False)
        finally:
            self._quiet = False
        self._changed(new_geometry=True)
        if self.type.currentData() == "to":
            self._refresh_picks()
            if self._needs_to() and self.profiles and self.axis is not None:
                self.activate("to")  # Fusion waits for the object next
        elif self.active == "to":
            self.activate("profiles")
        else:
            self._refresh_picks()

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
        self._last_handle = "angle"
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
        self.drop_formula("angle", update=False)
        self._changed()

    @_safe
    def _released(self, value):
        self._dragged(value)
        self._changed(new_geometry=True)  # the arrow turns round when the side changes

    @_safe
    def _dragged2(self, value):
        self._last_handle = "angle2"
        value = round(-self._side_sign() * value, 1)
        value = max(0.1, min(360.0 - abs(self.angle.value()), value))
        self._quiet = True
        try:
            self.angle2.set_value(value)
        finally:
            self._quiet = False
        self.drop_formula("angle2", update=False)
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
        self.show_formulas()
        self._auto_operation()
        self.dirty = True
        if new_geometry:
            self._geometry_changed = True
        self.schedule()

    def _recompute(self):
        if self._closed:
            return  # a change that arrived as the dialog closed
        if self._busy():
            self._timer.start()  # a long recompute runs timers: never start a second one
            return
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            if self._closed:
                return  # finished or cancelled while the recompute ran
            self.show_status()
            if self._geometry_changed or self._handles_wrong():
                self._geometry_changed = False
                self._make_handles()
        except Exception as exc:
            if not self._closed:
                try:
                    self.message.setText("⚠ %s" % exc)
                except RuntimeError:
                    pass  # the dialog's widgets are gone

    def _busy(self):
        """True while FreeCAD recomputes: OK, Cancel and another command wait for it."""
        try:
            return bool(self.doc.Recomputing)
        except Exception:
            return False

    def _apply(self):
        if not self.profiles or self.axis is None:
            return
        if self.options["type"] == "to" and not self.options.get("to"):
            # Nothing to show until the object is picked (the old angle would be a lie).
            self.error = TO_WAIT
            if self.target is not None and not self.editing:
                revolve.remove(self.target)
                self.target = None
                self._remove_handles()
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
        if self.formula_error:
            self.message.setText("⚠ " + self.formula_error)
            return
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = _plain(preview.failure(self.target)) or revolve.problem(self.target)
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
        if self.options["type"] in ("full", "to"):
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
    def finish(self):
        """Another command is starting: keep the revolve if it is good, else drop it. Not in
        the middle of a recompute (the other command then says to finish this one first)."""
        if self._busy():
            return
        super().finish()

    def accept(self):
        if self._closed:
            return True
        if self._busy():
            self.message.setText("⚠ Still working out the preview; press OK again in a moment.")
            return False
        try:
            return self._accept()
        except Exception as exc:
            warn("Revolve OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        if self.formula_error:  # Enter right after a typo: Fusion keeps the dialog open
            self.message.setText("⚠ " + self.formula_error)
            return False
        self._collect()
        if self.options["type"] == "to" and not self.options.get("to") and self.profiles:
            self.message.setText("⚠ " + TO_WAIT)
            self.activate("to")
            return False
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
        text = _plain(preview.failure(self.target)) or revolve.problem(self.target)
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        revolve.hide_sketches(self.profiles)
        self.cleanup()
        # Also closes the step's name when nothing changed (else the next change anywhere
        # took that name and threw away the Redo list).
        preview.end_transaction(self.doc)
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
        if self._closed:
            return True
        if self._busy():
            QtCore.QTimer.singleShot(200, self.reject)  # once the recompute is over
            return False
        body = self.body
        try:
            self._timer.stop()
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
        except Exception as exc:
            warn("Revolve Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Revolve Cancel: %s" % exc)
        revolve._show_tip(body)
        return True

    def cleanup(self):
        self._unwatch()
        for guard in (self.escape, self.undo_guard, self.enter, self.typing):
            try:
                guard.remove()
            except Exception:
                pass
        self._remove_handles()
        self._hide_shown()
        super().cleanup()


TO_WAIT = (
    "Click the object to revolve to: an origin plane, a flat face, an edge or a corner of the "
    "part, or a construction plane or point."
)

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


def _vertex(point):
    import Part

    return Part.Vertex(point)


def _in_doc(obj, doc):
    try:
        return obj.Document.Name == doc.Name
    except Exception:
        return False


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
            sketch = _sketch_in_edit()  # Revolve started in a sketch: revolve that sketch
            if not commands.finish_open_dialog():
                return
            if commands.find_body() is None:
                commands.tell("Revolve needs a sketch: use Create Sketch first.")
                return
            Gui.Control.showDialog(RevolvePanel(App.ActiveDocument, sketch=sketch))
            log("revolve started")
        except Exception as exc:
            warn("Revolve failed to start: %s" % exc)


def _sketch_in_edit():
    try:
        edit = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument is not None else None
        obj = edit.Object if edit is not None else None
    except Exception:
        return None
    return obj if obj is not None and extrude.is_sketch(obj) else None


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
