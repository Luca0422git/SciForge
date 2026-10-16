# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drag handles and clickable markers drawn in the 3D view for the CONSTRUCT and INSPECT
dialogs (construct_ui.py, section_ui.py, measure_ui.py).

  LinearHandle  Fusion's blue arrow: drag it along its line to set a distance.
  PathHandle    a blue ball on an edge: drag it along the edge (Plane / Point Along Path).
  PointDots     points drawn as dots that can be clicked (the origin point, snap points).
  Overlay       lines, dots and text drawn over the part (measure results).

Like revolve_ui.AngleHandle they are drawn over the part (Fusion's handles are never hidden
by it) and they are not Coin draggers: Coin lets only the nearest object take a click, and
its dragger callbacks run Python without its lock. FreeCAD's own mouse callbacks
(view.addEventCallback, safe) only record where the mouse is; a Qt timer applies it.
Nothing here keeps a FreeCAD-owned Coin node: every node is made and owned here.
"""

import math
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import drag_guard, increments, warn
from .compat import QtCore
from .taskui import BoxCarrier

BLUE = (0.30, 0.62, 0.95)  # Fusion's manipulator blue
BLUE_ACTIVE = (0.55, 0.80, 1.0)
GRAB = {"time": 0.0}  # one press moves one handle
USED = {"time": 0.0}  # when any handle was last pressed, dragged or let go
JUST_USED_S = 0.6


def touch():
    USED["time"] = time.time()


# The release watchers alive: one per handle whose drag is under way (made at the press by
# watch_release, removed at the release). Handles that take the mouse through FreeCAD's
# view callbacks (these handles, Move's triad, Revolve's angle handle, the primitives'
# handles, the curve picker's path handle) all start one, so this is the one place that
# knows "a handle owns this drag": the box selection (selection_ui) must not take it.
WATCHES = set()


def dragging():
    """True while a handle's drag is under way (pressed on the handle, not released yet).
    A watcher left behind by a lost release does not count once the button is up."""
    try:
        if not WATCHES:
            return False
        if not drag_guard.left_held():
            return False
        return any(watch.handle is not None for watch in list(WATCHES))
    except Exception:
        return False


def just_used(seconds=JUST_USED_S):
    """True while a handle is in use and just after. FreeCAD's selection also takes the
    press and the release of a handle's drag as a click on what is under the mouse (the
    face behind the handle, or the face under the mouse where the drag ends): that is not
    a pick. A dialog often makes new handles when a drag ends (the old one's own memory of
    the drag is gone then), so this is remembered here, for every handle."""
    return time.time() - USED["time"] < seconds


def _mouse_ray(view, position):
    from .profile_pick import mouse_ray

    return mouse_ray(view, position)


def _screen(view, point):
    x, y = view.getPointOnViewport(App.Vector(point))
    return float(x), float(y)


def _segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


class ReleaseWatch:
    """Ends a handle's drag on any left-button release in the application. FreeCAD's
    selection keeps the release of a drag that ends over a face (it selects the face and
    marks the event handled), so a view callback never saw it: the handle stayed "grabbed",
    followed the mouse with no button down and swallowed every later pick. Qt sees every
    release first: this filter is installed while the button is down on the handle."""

    def __init__(self, handle):
        from .compat import QtWidgets

        self.handle = handle
        self.filter = None
        watch = self

        class _Filter(QtCore.QObject):
            def eventFilter(self, obj, event):
                try:
                    if event.type() == QtCore.QEvent.MouseButtonRelease and (
                        event.button() == QtCore.Qt.LeftButton
                    ):
                        watch.released()
                except Exception:
                    pass
                return False

        self.filter = _Filter()
        QtWidgets.QApplication.instance().installEventFilter(self.filter)
        WATCHES.add(self)

    def released(self):
        handle = self.handle
        if handle is not None and getattr(handle, "_drag", False):
            handle._drag = False
            handle._released = True
            handle._last_event = time.time()
            touch()
        self.remove()

    def remove(self):
        from .compat import QtWidgets

        WATCHES.discard(self)
        self.handle = None
        if self.filter is not None:
            try:
                QtWidgets.QApplication.instance().removeEventFilter(self.filter)
            except Exception:
                pass
            # deleted later, never inside its own eventFilter call
            QtCore.QTimer.singleShot(0, self.filter.deleteLater)
            self.filter = None


def watch_release(handle):
    """Start watching for the release of a drag on `handle` (see ReleaseWatch)."""
    old = getattr(handle, "_release_watch", None)
    if old is not None:
        old.remove()
    touch()  # a handle took this press: it is not a pick, nor the start of a box
    try:
        handle._release_watch = ReleaseWatch(handle)
    except Exception as exc:
        handle._release_watch = None
        warn("handle: %s" % exc)


def stop_watching(handle):
    old = getattr(handle, "_release_watch", None)
    if old is not None:
        old.remove()
    handle._release_watch = None


def _rotation_y_to(direction):
    """Rotation that turns +Y (Coin's cylinder/cone axis) onto `direction`."""
    return App.Rotation(App.Vector(0, 1, 0), App.Vector(direction))


class _Handle(BoxCarrier):
    """What LinearHandle and PathHandle share: callbacks, polling, hover colour, and a
    value box when the dialog gives one (taskui.BoxCarrier)."""

    POLL_MS = 30
    GRAB_PIXELS = 12.0

    def __init__(self, view, on_drag, on_release):
        from pivy import coin

        self.coin = coin
        self.view = view or Gui.ActiveDocument.ActiveView
        self.on_drag = on_drag
        self.on_release = on_release
        self._pending = None
        self._released = False
        self._drag = False
        self._hover = False
        self._painted = None
        self._last_event = 0.0
        self.root = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.material = coin.SoMaterial()
        self.root.addChild(self.material)
        self.callbacks = []
        self._timer = QtCore.QTimer()
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)

    def _start(self):
        self._paint()
        self.view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", self.view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", self.view.addEventCallback("SoLocation2Event", self._moved)),
        ]
        self._timer.start()

    def _paint(self):
        state = self._hover or self._drag
        if self._painted == state:
            return
        self._painted = state
        color = BLUE_ACTIVE if state else BLUE
        self.material.diffuseColor.setValue(*color)
        self.material.emissiveColor.setValue(color[0] * 0.5, color[1] * 0.5, color[2] * 0.5)

    def hit(self, position):
        return False

    def _press(self, position):
        pass

    def _drag_to(self, position):
        return None

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1":
                return
            position = info["Position"]
            if info.get("State") == "DOWN":
                if self.hit(position) and time.time() - GRAB["time"] > 0.05:
                    GRAB["time"] = time.time()
                    self._drag = True
                    self._last_event = time.time()
                    touch()
                    self._press(position)
                    watch_release(self)
            elif self._drag:
                self._drag = False
                self._released = True
                self._last_event = time.time()
                touch()
                stop_watching(self)
        except Exception as exc:
            warn("handle: %s" % exc)

    def _moved(self, info):
        try:
            position = info["Position"]
            if not self._drag:
                self._hover = self.hit(position)
                return
            self._last_event = time.time()
            touch()
            value = self._drag_to(position)
            if value is not None:
                self._pending = value
        except Exception as exc:
            warn("handle: %s" % exc)

    def dragging(self):
        return self._drag

    def box_active(self):
        return bool(self._drag or self._hover)

    def busy(self, seconds=0.6):
        """True while dragging and just after: that click is the handle's, not a pick."""
        return self._drag or time.time() - self._last_event < seconds

    def _apply(self, value):
        pass

    def value(self):
        return None

    def _poll(self):
        try:
            if Gui.ActiveDocument is None:
                self._timer.stop()
                return
            drag_guard.end_lost_drag(self, idle=False)  # its release never came (drag_guard)
            self._paint()
            pending = self._pending
            if pending is not None and abs(pending - self.value()) > 1e-9:
                self._apply(pending)
                if self.on_drag:
                    self.on_drag(pending)
            if self._released and not self._drag:
                self._released = False
                self._pending = None
                touch()  # also a release found from Qt's mouse state (pickpanel.Arrow)
                if self.on_release:
                    self.on_release(self.value())
            self.follow_box()
        except Exception as exc:
            warn("handle drag: %s" % exc)

    def remove(self):
        stop_watching(self)
        try:
            self._timer.stop()
        except Exception:
            pass
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
        self.drop_box()


def angle_handle(*args, **kwargs):
    """revolve_ui.AngleHandle (the blue ball turning about a line) whose drag also ends on a
    release FreeCAD's selection kept (see ReleaseWatch)."""
    from .revolve_ui import AngleHandle

    # Incremental Move (navigation bar) steps, the 45-degree snap and Ctrl's free turn are
    # the handle's own (protractor.snap_angle), as for every angle handle.

    class WatchedAngleHandle(AngleHandle):
        def _button(self, info):
            try:
                pressed = info.get("Button") == "BUTTON1" and info.get("State") == "DOWN"
                if pressed and not self._drag and time.time() - GRAB["time"] <= 0.05:
                    return  # an arrow of this dialog took this press (one press, one handle)
            except Exception:
                pass
            was = self._drag
            super()._button(info)
            try:
                if self._drag and not was:
                    GRAB["time"] = time.time()
                    touch()
                    watch_release(self)
                elif was and not self._drag:
                    touch()
                    stop_watching(self)
            except Exception as exc:
                warn("handle: %s" % exc)

        def _moved(self, info):
            super()._moved(info)
            if self._drag:
                touch()

        def remove(self):
            stop_watching(self)
            super().remove()

    return WatchedAngleHandle(*args, **kwargs)


class LinearHandle(_Handle):
    """A blue arrow at origin + direction * value, pointing along `direction`. Drag it to
    change `value` (signed, mm). on_drag(value) while dragging, on_release(value) after."""

    def __init__(
        self, origin, direction, value, size, on_drag=None, on_release=None, view=None, step=0.0
    ):
        super().__init__(view, on_drag, on_release)
        self.origin = App.Vector(origin)
        self.direction = App.Vector(direction)
        self.direction.normalize()
        self.size = float(size)
        self.step = float(step)
        self._value = float(value)
        self._offset = 0.0
        self._last_pos = None
        coin = self.coin
        self.place = coin.SoTransform()
        self.root.addChild(self.place)
        self.root.addChild(self._arrow())
        self._draw()
        self._start()

    def _arrow(self):
        coin = self.coin
        s = self.size
        sep = coin.SoSeparator()
        ball = coin.SoSphere()
        ball.radius.setValue(0.12 * s)
        sep.addChild(ball)
        move = coin.SoTranslation()
        move.translation.setValue(0.0, 0.35 * s, 0.0)
        sep.addChild(move)
        shaft = coin.SoCylinder()
        shaft.radius.setValue(0.05 * s)
        shaft.height.setValue(0.7 * s)
        sep.addChild(shaft)
        tip_move = coin.SoTranslation()
        tip_move.translation.setValue(0.0, 0.35 * s + 0.15 * s, 0.0)
        sep.addChild(tip_move)
        tip = coin.SoCone()
        tip.bottomRadius.setValue(0.16 * s)
        tip.height.setValue(0.3 * s)
        sep.addChild(tip)
        return sep

    def base_point(self):
        return self.origin + self.direction * self._value

    def tip_point(self):
        return self.base_point() + self.direction * self.size

    def box_geometry(self):
        """The ball (0.12 sizes) at the base, the shaft and the head up to the tip."""
        base = self.base_point()
        anchor = base + self.direction * (0.5 * self.size)
        tail = base - self.direction * (0.12 * self.size)
        return anchor, tail, self.tip_point(), 0.16 * self.size

    def value(self):
        return self._value

    def set_value(self, value):
        self._value = float(value)
        self._pending = None
        self._draw()

    def set_line(self, origin, direction):
        self.origin = App.Vector(origin)
        self.direction = App.Vector(direction)
        self.direction.normalize()
        self._draw()

    def _apply(self, value):
        self._value = float(value)
        self._draw()

    def _draw(self):
        p = self.base_point()
        self.place.translation.setValue(p.x, p.y, p.z)
        self.place.rotation.setValue(*_rotation_y_to(self.direction).Q)

    def hit(self, position):
        try:
            px, py = float(position[0]), float(position[1])
            ax, ay = _screen(self.view, self.base_point())
            bx, by = _screen(self.view, self.tip_point())
            return _segment_distance(px, py, ax, ay, bx, by) <= self.GRAB_PIXELS
        except Exception:
            return False

    def _along(self, position):
        """Distance along the line to where it passes closest to the mouse ray, or None
        when the line points (nearly) at the eye."""
        point, ray = _mouse_ray(self.view, tuple(position))
        d = self.direction
        b = d.dot(ray)
        denom = 1.0 - b * b
        if denom < 0.02:
            return None
        w0 = self.origin - point
        return (b * ray.dot(w0) - d.dot(w0)) / denom

    def _press(self, position):
        self._last_pos = (float(position[0]), float(position[1]))
        start = self._along(position)
        self._offset = 0.0 if start is None else start - self._value

    def _drag_to(self, position):
        t = self._along(position)
        if t is None:  # edge-on: follow the mouse along the arrow on screen
            if self._last_pos is None:
                return None
            ax, ay = _screen(self.view, self.base_point())
            bx, by = _screen(self.view, self.tip_point())
            tx, ty = bx - ax, by - ay
            length2 = tx * tx + ty * ty
            if length2 < 1e-6:
                return None
            dx = float(position[0]) - self._last_pos[0]
            dy = float(position[1]) - self._last_pos[1]
            value = self._value + (dx * tx + dy * ty) / length2 * self.size
        else:
            # Incremental Move (navigation bar): the arrow goes in steps of the increment
            value = increments.linear(t - self._offset)
        self._last_pos = (float(position[0]), float(position[1]))
        if self.step > 0:
            value = round(value / self.step) * self.step
        return value


class PathHandle(_Handle):
    """A blue ball on `edge` (a Part.Edge in global coordinates) at curve parameter
    `parameter`; drag it along the edge. Values are curve parameters."""

    def __init__(self, edge, parameter, size, on_drag=None, on_release=None, view=None):
        super().__init__(view, on_drag, on_release)
        self.edge = edge
        self.size = float(size)
        self._value = float(parameter)
        coin = self.coin
        self.place = coin.SoTranslation()
        self.root.addChild(self.place)
        ball = coin.SoSphere()
        ball.radius.setValue(0.12 * self.size)
        self.root.addChild(ball)
        self._probe = None
        self._draw()
        self._start()

    def value(self):
        return self._value

    def set_value(self, parameter):
        self._value = float(parameter)
        self._pending = None
        self._draw()

    def set_edge(self, edge):
        self.edge = edge
        self._draw()

    def point(self):
        return self.edge.valueAt(self._value)

    def box_geometry(self):
        point = self.point()
        return point, point, point, 0.12 * self.size

    def _apply(self, value):
        self._value = float(value)
        self._draw()

    def _draw(self):
        p = self.point()
        self.place.translation.setValue(p.x, p.y, p.z)

    def hit(self, position):
        try:
            bx, by = _screen(self.view, self.point())
            return math.hypot(float(position[0]) - bx, float(position[1]) - by) <= max(
                self.GRAB_PIXELS, 6.0
            )
        except Exception:
            return False

    def _drag_to(self, position):
        import Part

        point, ray = _mouse_ray(self.view, tuple(position))
        box = self.edge.BoundBox
        reach = 10 * max(box.DiagonalLength, 1.0) + (box.Center - point).Length
        line = Part.LineSegment(point - ray * reach, point + ray * reach).toShape()
        _dist, pairs, _info = self.edge.distToShape(line)
        if not pairs:
            return None
        nearest = pairs[0][0]
        u = self.edge.Curve.parameter(nearest)
        first, last = self.edge.FirstParameter, self.edge.LastParameter
        return min(max(u, first), last)


class PointDots:
    """Points drawn as dots that light up under the mouse and can be clicked:
    on_pick(key) for a click within a few pixels. dots: [(key, App.Vector, colour)]."""

    PICK_PIXELS = 9.0

    def __init__(self, view, dots, on_pick, size=1.0):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.on_pick = on_pick
        self.size = float(size)
        self.dots = []
        self.hovered = None
        self.enabled = True
        self.last_click = 0.0
        self.root = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.switch = coin.SoSwitch()
        self.switch.whichChild = coin.SO_SWITCH_ALL
        self.root.addChild(self.switch)
        for key, point, color in dots:
            self.dots.append(self._dot(key, point, color))
        view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]

    def _dot(self, key, point, color):
        coin = self.coin
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(*[c * 0.6 for c in color])
        move = coin.SoTranslation()
        move.translation.setValue(point.x, point.y, point.z)
        ball = coin.SoSphere()
        ball.radius.setValue(0.25 * self.size)
        sep.addChild(material)
        sep.addChild(move)
        sep.addChild(ball)
        self.switch.addChild(sep)
        return [key, App.Vector(point), color, material]

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.switch.whichChild = self.coin.SO_SWITCH_ALL if enabled else self.coin.SO_SWITCH_NONE

    def dot_at(self, position):
        if not self.enabled:
            return None
        try:
            px, py = float(position[0]), float(position[1])
        except Exception:
            return None
        best = None
        for dot in self.dots:
            try:
                x, y = _screen(self.view, dot[1])
            except Exception:
                continue
            d = math.hypot(px - x, py - y)
            if d <= self.PICK_PIXELS and (best is None or d < best[0]):
                best = (d, dot)
        return best[1] if best else None

    def _moved(self, info):
        try:
            hit = self.dot_at(info["Position"])
            if hit is self.hovered:
                return
            for dot, on in ((self.hovered, False), (hit, True)):
                if dot is not None:
                    color = BLUE_ACTIVE if on else dot[2]
                    dot[3].diffuseColor.setValue(*color)
                    dot[3].emissiveColor.setValue(*[c * 0.6 for c in color])
            self.hovered = hit
        except Exception as exc:
            warn("point hover: %s" % exc)

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            hit = self.dot_at(info["Position"])
            if hit is not None:
                self.last_click = time.time()
                key = hit[0]
                QtCore.QTimer.singleShot(0, lambda: self.on_pick(key))
        except Exception as exc:
            warn("point pick: %s" % exc)

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


class Overlay:
    """Lines, dots and labels drawn over the part (not clickable). clear() empties it."""

    def __init__(self, view=None):
        from pivy import coin

        self.coin = coin
        self.view = view or Gui.ActiveDocument.ActiveView
        self.root = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.content = coin.SoSeparator()
        self.root.addChild(self.content)
        self.view.getSceneGraph().addChild(self.root)

    def clear(self):
        self.content.removeAllChildren()

    def _material(self, color):
        material = self.coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(*color)
        return material

    def line(self, a, b, color=BLUE, width=2.0, dashed=False):
        coin = self.coin
        sep = coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(width)
        if dashed:
            style.linePattern.setValue(0xF0F0)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, 2, [(a.x, a.y, a.z), (b.x, b.y, b.z)])
        lines = coin.SoLineSet()
        lines.numVertices.setValue(2)
        sep.addChild(self._material(color))
        sep.addChild(style)
        sep.addChild(coords)
        sep.addChild(lines)
        self.content.addChild(sep)

    def polyline(self, points, color=BLUE, width=2.0):
        coin = self.coin
        if len(points) < 2:
            return
        sep = coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(width)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
        lines = coin.SoLineSet()
        lines.numVertices.setValue(len(points))
        sep.addChild(self._material(color))
        sep.addChild(style)
        sep.addChild(coords)
        sep.addChild(lines)
        self.content.addChild(sep)

    def dot(self, p, radius, color=BLUE):
        coin = self.coin
        sep = coin.SoSeparator()
        move = coin.SoTranslation()
        move.translation.setValue(p.x, p.y, p.z)
        ball = coin.SoSphere()
        ball.radius.setValue(radius)
        sep.addChild(self._material(color))
        sep.addChild(move)
        sep.addChild(ball)
        self.content.addChild(sep)

    def text(self, p, text, color=(1.0, 1.0, 1.0)):
        coin = self.coin
        sep = coin.SoSeparator()
        move = coin.SoTranslation()
        move.translation.setValue(p.x, p.y, p.z)
        font = coin.SoFont()
        font.size.setValue(14.0)
        label = coin.SoText2()
        label.string.setValue(text)
        sep.addChild(self._material(color))
        sep.addChild(move)
        sep.addChild(font)
        sep.addChild(label)
        self.content.addChild(sep)

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass
