# SPDX-License-Identifier: LGPL-2.1-or-later
"""Box, Cylinder, Sphere and Torus (SOLID > CREATE) with Fusion's way of placing them.

1. Pick a plane: the origin planes show as big squares (click one), or click a flat face
   of the part. A plane or flat face selected before the command is taken at once.
2. Place it with the mouse on that plane (the mouse ray meets the plane; a blue outline
   follows the mouse): the Box takes two corner clicks, Cylinder / Torus / Coil the
   centre and then a point on the circle, Sphere the centre.
3. The part appears with blue handles: drag the height arrow (Box, Cylinder), the size
   arrows, or type exact values in the dialog. Dragging into the part switches the
   operation to Cut, like Fusion, unless you picked one yourself.

OK keeps it (one undo step), Cancel or Esc removes it, Enter is OK. Problems are said in
the dialog, which then stays open. Double-click the step in the timeline to edit it.

The dialog base (PlacedPanel), the placing tool (Placer) and the drag handle
(LinearHandle) are shared with the Coil dialog (coil_ui.py).
"""
import math
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, preview, primitives, profile_pick, ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .primitives import PrimitiveError
from .primitives_core import nice_floor, round_to
from .taskui import DistanceField, Panel

OPERATION_LABELS = [
    ("Join", "join"),
    ("Cut", "cut"),
    ("Intersect", "intersect"),
    ("New Body", "new_body"),
]
POSITION_LABELS = [("Inside", "inside"), ("On Center", "center"), ("Outside", "outside")]
ACTIVE_STYLE = "QPushButton { background: #1f6fbf; color: white; border: 1px solid #5aa0e6; }"
HANDLE = (0.30, 0.62, 0.95)  # Fusion's manipulator blue
HANDLE_ACTIVE = (0.55, 0.80, 1.0)
OUTLINE = (0.35, 0.70, 1.0)
SNAP_PIXELS = 10.0  # a click this near the plane's origin lands on it


def combo(pairs, current, name=""):
    box = QtWidgets.QComboBox()
    for label, value in pairs:
        box.addItem(label, value)
    set_combo(box, current)
    if name:
        box.setObjectName(name)
    return box


def set_combo(box, value):
    for i in range(box.count()):
        if box.itemData(i) == value:
            box.setCurrentIndex(i)
            return


def safe(method):
    """Dialog reactions (Qt slots, timers) never let an exception out: it would print a
    traceback in the Report view. It is logged and shown in the dialog."""
    import functools

    @functools.wraps(method)
    def wrapper(self, *args):
        try:
            return method(self, *args)
        except Exception as exc:
            warn("%s: %s" % (getattr(self, "title", "dialog"), exc))
            try:
                self.message.setText("⚠ %s" % exc)
            except Exception:
                pass
        return None

    return wrapper


class SelectionField:
    """Fusion's selection box: shows what is picked, blue while it waits for clicks in the
    3D view (click it to pick again), with an x to clear it."""

    def __init__(self, panel, name, empty):
        self.panel = panel
        self.name = name
        self.empty = empty
        self.widget = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(self.widget)
        row.setContentsMargins(0, 0, 0, 0)
        self.button = QtWidgets.QPushButton(empty)
        self.button.setCheckable(True)
        self.button.setObjectName("SciForgePrimitive_" + name)
        self.button.clicked.connect(self._clicked)
        self.clear = QtWidgets.QToolButton()
        self.clear.setText("✕")
        self.clear.setToolTip("Clear")
        self.clear.setObjectName("SciForgePrimitive_clear_" + name)
        self.clear.clicked.connect(self._cleared)
        row.addWidget(self.button, 1)
        row.addWidget(self.clear)

    def _clicked(self, *_):
        try:
            self.panel.activate(self.name)
        except Exception as exc:
            warn("selection box: %s" % exc)

    def _cleared(self, *_):
        try:
            self.panel.clear_field(self.name)
        except Exception as exc:
            warn("selection box: %s" % exc)

    def set_active(self, active):
        self.button.setChecked(active)
        self.button.setStyleSheet(ACTIVE_STYLE if active else "")

    def set_text(self, text):
        self.button.setText(text or self.empty)


def view_scale(view, point):
    """World length of one pixel of the 3D view near `point` (global)."""
    try:
        x, y = view.getPointOnViewport(point)
        a = view.getPoint((int(x), int(y)))
        b = view.getPoint((int(x) + 10, int(y)))
        return max((a - b).Length / 10.0, 1e-6)
    except Exception:
        return 0.1


_GRAB = {"time": 0.0}  # when a handle last took a press (one press moves one handle)


# -- the drag handle ----------------------------------------------------------------------------
class LinearHandle:
    """Fusion's blue arrow you drag along a line: a ball with an arrow head, at
    origin + direction * value * scale. Drawn on top of the part, so it can be grabbed
    where the part is in front of it (a Coin dragger cannot); FreeCAD's mouse callbacks
    (view.addEventCallback, safe) only record the mouse, a Qt timer applies it (pivy
    dragger callbacks run Python without its lock and crash FreeCAD)."""

    POLL_MS = 30
    GRAB_PIXELS = 14.0

    def __init__(
        self,
        origin,
        direction,
        value,
        size,
        on_drag=None,
        on_release=None,
        scale=1.0,
        color=HANDLE,
        name="",
    ):
        from pivy import coin

        self.view = Gui.ActiveDocument.ActiveView
        self.origin = App.Vector(origin)
        self.direction = App.Vector(direction)
        self.direction.normalize()
        self.scale = float(scale)
        self.size = float(size)
        self.color = color
        self.name = name
        self.on_drag = on_drag
        self.on_release = on_release
        self._value = float(value)
        self._shown = None
        self._pending = None
        self._released = False
        self._drag = False
        self._grab = 0.0
        self._last_pos = None
        self._last_event = 0.0
        self._hover = False
        self._painted = None
        self.root = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.material = coin.SoMaterial()
        self.root.addChild(self.material)
        self.place = coin.SoTransform()
        self.root.addChild(self.place)
        self.flip = coin.SoRotationXYZ()
        self.flip.axis.setValue(coin.SoRotationXYZ.Z)
        self.root.addChild(self.flip)
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
        """A ball to grab and an arrow head pointing along local +Y."""
        s = self.size
        sep = coin.SoSeparator()
        ball = coin.SoSphere()
        ball.radius.setValue(0.3 * s)
        sep.addChild(ball)
        move = coin.SoTranslation()
        move.translation.setValue(0.0, 0.55 * s, 0.0)
        sep.addChild(move)
        shaft = coin.SoCylinder()
        shaft.radius.setValue(0.09 * s)
        shaft.height.setValue(0.7 * s)
        sep.addChild(shaft)
        tip_move = coin.SoTranslation()
        tip_move.translation.setValue(0.0, 0.55 * s, 0.0)
        sep.addChild(tip_move)
        tip = coin.SoCone()
        tip.bottomRadius.setValue(0.25 * s)
        tip.height.setValue(0.45 * s)
        sep.addChild(tip)
        return sep

    # -- geometry ---------------------------------------------------------------------------------
    def point_at(self, value):
        return self.origin + self.direction * (float(value) * self.scale)

    def position(self):
        return self.point_at(self._value)

    def value(self):
        return self._value

    def set_value(self, value):
        """Show the handle at this value (typed in the dialog)."""
        self._value = float(value)
        self._pending = None
        self._draw()

    def _draw(self):
        if self._shown is not None and abs(self._shown - self._value) < 1e-12:
            return
        self._shown = self._value
        p = self.position()
        self.place.translation.setValue(p.x, p.y, p.z)
        rotation = App.Rotation(App.Vector(0, 1, 0), self.direction)
        self.place.rotation.setValue(*rotation.Q)
        self.flip.angle.setValue(math.pi if self._value * self.scale < 0 else 0.0)

    def _paint(self):
        hot = self._hover or self._drag
        if self._painted == hot:
            return
        self._painted = hot
        color = HANDLE_ACTIVE if hot else self.color
        self.material.diffuseColor.setValue(*color)
        self.material.emissiveColor.setValue(color[0] * 0.5, color[1] * 0.5, color[2] * 0.5)

    # -- the mouse ----------------------------------------------------------------------------------
    def _screen(self, point):
        x, y = self.view.getPointOnViewport(point)
        return float(x), float(y)

    def hit(self, position):
        """True if the mouse at `position` (viewport pixels) is on the handle."""
        try:
            p = self.position()
            bx, by = self._screen(p)
            sign = -1.0 if self._value * self.scale < 0 else 1.0
            tip = p + self.direction * (sign * 1.1 * self.size)
            tx, ty = self._screen(tip)
            edge = p + self._side() * (0.3 * self.size)
            ex, ey = self._screen(edge)
            reach = max(self.GRAB_PIXELS, math.hypot(ex - bx, ey - by) + 4.0)
            mx, my = float(position[0]), float(position[1])
            if math.hypot(mx - bx, my - by) <= reach:
                return True
            # along the arrow's shaft
            dx, dy = tx - bx, ty - by
            length2 = dx * dx + dy * dy
            if length2 < 1e-6:
                return False
            t = max(0.0, min(1.0, ((mx - bx) * dx + (my - by) * dy) / length2))
            return math.hypot(mx - (bx + dx * t), my - (by + dy * t)) <= self.GRAB_PIXELS * 0.7
        except Exception:
            return False

    def _side(self):
        side = self.direction.cross(App.Vector(0, 0, 1))
        if side.Length < 1e-6:
            side = self.direction.cross(App.Vector(1, 0, 0))
        side.normalize()
        return side

    def _along(self, position):
        """The handle value under the mouse: the point of the handle's line nearest the
        mouse ray. None when the line points at the viewer."""
        point, ray = profile_pick.mouse_ray(self.view, tuple(position))
        d = self.direction
        w0 = self.origin - point
        b = d.dot(ray)
        denom = 1.0 - b * b
        if denom < 0.02:  # the arrow points (almost) at the viewer
            return None
        t = (b * ray.dot(w0) - d.dot(w0)) / denom
        return t / self.scale

    def _incremental(self, position, current):
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
                    _GRAB["time"] = time.time()
                    self._drag = True
                    self._last_event = time.time()
                    self._last_pos = (float(position[0]), float(position[1]))
                    start = self._along(position)
                    self._grab = 0.0 if start is None else start - self._value
            elif self._drag:
                self._drag = False
                self._released = True
                self._last_event = time.time()
        except Exception as exc:
            warn("handle: %s" % exc)

    def _moved(self, info):
        try:
            position = info["Position"]
            if not self._drag:
                self._hover = self.hit(position)
                return
            self._last_event = time.time()
            current = self._pending if self._pending is not None else self._value
            value = self._along(position)
            if value is None:
                value = self._incremental(position, current)
            else:
                value -= self._grab
            self._last_pos = (float(position[0]), float(position[1]))
            self._pending = value
        except Exception as exc:
            warn("handle: %s" % exc)

    def dragging(self):
        return self._drag

    def busy(self, seconds=0.6):
        """True while dragging and just after: the click was the handle's, not a pick."""
        return self._drag or time.time() - self._last_event < seconds

    def _poll(self):
        try:
            if Gui.ActiveDocument is None:
                self._timer.stop()
                return
            self._paint()
            pending = self._pending
            if pending is not None and abs(pending - self._value) > 1e-9:
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
            warn("handle drag: %s" % exc)

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


# -- placing on the plane -------------------------------------------------------------------------------
class Placer:
    """Clicks on the picked plane: the mouse ray meets the plane, the point is rounded to a
    step that suits the zoom (or snapped onto the plane's origin), and a blue outline drawn
    by `outline(points, mouse)` follows the mouse. on_click(point) gets each click (plane
    coordinates, (x, y)); on_move(points, mouse) each move. A press on a handle or on
    something `blocked(position)` says is busy is not a click. Mouse events only record
    (FreeCAD's callbacks); a Qt timer draws and calls back."""

    POLL_MS = 25

    def __init__(self, view, frame, outline, on_click, on_move=None, blocked=None):
        from pivy import coin

        self.view = view
        self.frame = frame  # global Placement of the plane
        self.outline = outline
        self.on_click = on_click
        self.on_move = on_move
        self.blocked = blocked
        self.points = []
        self.mouse = None
        self._moved_to = None
        self._clicks = []
        self._drawn = None
        self.root = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(2.0)
        self.root.addChild(style)
        color = coin.SoBaseColor()
        color.rgb.setValue(*OUTLINE)
        self.root.addChild(color)
        self.coords = coin.SoCoordinate3()
        self.lines = coin.SoLineSet()
        self.lines.numVertices.setValue(0)
        self.root.addChild(self.coords)
        self.root.addChild(self.lines)
        view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]
        self._timer = QtCore.QTimer()
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _hit(self, position):
        base = self.frame.Base
        normal = self.frame.Rotation.multVec(App.Vector(0, 0, 1))
        hit = profile_pick.ray_plane(self.view, tuple(position), base, normal)
        return None if hit is None else hit[0]

    def plane_point(self, position):
        """(x, y) on the plane under the mouse, rounded to a step of a few pixels (a plane
        seen at a slant counts its stretched pixels), or snapped onto the plane's origin."""
        point = self._hit(position)
        if point is None:
            return None
        local = self.frame.inverse().multVec(point)
        pixel = 0.0
        x, y = float(position[0]), float(position[1])
        for dx, dy in ((3, 0), (0, 3)):
            other = self._hit((x + dx, y + dy))
            if other is not None:
                pixel = max(pixel, (other - point).Length / 3.0)
        if pixel <= 0.0:
            pixel = view_scale(self.view, point)
        if math.hypot(local.x, local.y) <= SNAP_PIXELS * pixel:
            return (0.0, 0.0)
        step = nice_floor(6.0 * pixel)
        return (round_to(local.x, step), round_to(local.y, step))

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            position = tuple(info["Position"])
            if self.blocked is not None and self.blocked(position):
                return
            self._clicks.append(position)
        except Exception as exc:
            warn("placing: %s" % exc)

    def _moved(self, info):
        try:
            self._moved_to = tuple(info["Position"])
        except Exception as exc:
            warn("placing: %s" % exc)

    def _poll(self):
        try:
            if Gui.ActiveDocument is None:
                self._timer.stop()
                return
            if self._moved_to is not None:
                position, self._moved_to = self._moved_to, None
                point = self.plane_point(position)
                if point is not None:
                    self.mouse = point
                    self.redraw()
                    if self.on_move:
                        self.on_move(list(self.points), point)
            while self._clicks:
                position = self._clicks.pop(0)
                point = self.plane_point(position)
                if point is None:
                    continue
                self.mouse = point
                self.on_click(point)
                self.redraw()
        except Exception as exc:
            warn("placing: %s" % exc)

    def redraw(self):
        try:
            polylines = self.outline(list(self.points), self.mouse) if self.mouse else []
        except Exception:
            polylines = []
        points, counts = [], []
        for line in polylines:
            if len(line) < 2:
                continue
            for x, y in line:
                p = self.frame.multVec(App.Vector(x, y, 0))
                points.append((p.x, p.y, p.z))
            counts.append(len(line))
        key = (tuple(points), tuple(counts))
        if key == self._drawn:
            return
        self._drawn = key
        self.coords.point.setNum(len(points))
        if points:
            self.coords.point.setValues(0, len(points), points)
        self.lines.numVertices.setNum(len(counts))
        if counts:
            self.lines.numVertices.setValues(0, len(counts), counts)

    def remove(self):
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


def circle_points(cx, cy, r, steps=72):
    return [
        (cx + r * math.cos(2 * math.pi * i / steps), cy + r * math.sin(2 * math.pi * i / steps))
        for i in range(steps + 1)
    ]


def cross_points(x, y, size):
    return [[(x - size, y), (x + size, y)], [(x, y - size), (x, y + size)]]


# -- the dialog base ----------------------------------------------------------------------------------------
class PlacedPanel(Panel):
    """A primitive placed on a plane with the mouse (Box, Cylinder, Sphere, Torus, Coil).

    Subclasses set: title, icon, kind, clicks (mouse clicks to place it) and implement
    _build_fields(form), _show_fields(), _collect(), _placed(points) (the clicks set the
    options), _outline(points, mouse), _wanted_handles() / _handle_specs(), _build(),
    _read(feature) and _auto(base)."""

    title = "Primitive"
    icon = "box"
    kind = "box"
    clicks = 2
    last = None
    MESSAGE_LINES = 3
    HINTS = ("Click to place it.",)

    def __init__(self, doc, feature=None):
        super().__init__(doc, self.title if feature is None else "Edit %s" % self.title)
        type(self).last = self
        PlacedPanel.last = self
        try:
            primitives.drop_orphans(doc)  # helpers a timeline Delete left behind
        except Exception as exc:
            warn("could not tidy up helpers: %s" % exc)
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.target = feature
        self.editing = feature is not None
        self.ref = None
        self.options = self._defaults()
        self.user_picked_operation = feature is not None
        self.error = ""
        self.dirty = False
        self.state = "plane"
        self.points = []
        self.handles = {}
        self.planes = None
        self.placer = None
        self.observer = None
        self._quiet = False
        self._geometry_changed = False
        self.formula_error = ""
        self.body = None
        if feature is not None:
            self.body = primitives.owner_body(feature)
            try:
                self.ref, read = self._read(feature)
                self.options.update(read)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        else:
            self.body = self._ensure_body()
        self._build_form()
        self._show_fields()
        self._watch()
        if feature is not None:
            self.state = "ready"
            self.activate(None)
            self._show_plane()
            self._make_handles()
        else:
            self._start()

    # -- to override --------------------------------------------------------------------------------------
    def _defaults(self):
        return primitives.with_defaults(self.kind, {})

    def _read(self, feature):
        kind, ref, options = primitives.read(feature)
        return ref, options

    def _build(self):
        return primitives.build(self.kind, self.ref, self.options, feature=self.target)

    def _tool(self):
        return primitives.tool_shape(self.kind, self.ref, self.options)

    def _auto(self, base):
        return primitives.auto_operation(base, self._tool())

    def _build_fields(self, form):
        pass

    def _show_fields(self):
        pass

    def _collect(self):
        pass

    def _placed(self, points):
        pass

    def _outline(self, points, mouse):
        return []

    def _live(self, points, mouse):
        """The mouse moved while placing: show the values it would give (the fields)."""

    def _handle_specs(self):
        """[(name, origin, direction, value, scale, on_drag)] for the blue handles."""
        return []

    # -- form -------------------------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.plane_field = SelectionField(self, "plane", "Select plane")
        form.addRow("Plane", self.plane_field.widget)
        self.info = QtWidgets.QLabel("")  # what the dialog waits for (not a problem)
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color: #8cc4ff;")
        form.addRow(self.info)
        self._build_fields(form)
        self.operation = combo(OPERATION_LABELS, self.options["operation"], "SciForgeOperation")
        form.addRow("Operation", self.operation)
        self.formulas = QtWidgets.QLabel("")
        self.formulas.setWordWrap(True)
        self.formulas.setStyleSheet("color: #b8c7d9;")
        form.addRow(self.formulas)
        self.finish_layout()
        try:
            lines = self.message.fontMetrics().lineSpacing()
            self.message.setMinimumHeight(lines * self.MESSAGE_LINES + 4)
        except Exception:
            pass
        self.operation.activated.connect(self._operation_picked)

    def distance_field(self, form, label, key, unit="mm", name=""):
        field = DistanceField(
            self.options.get(key, 0.0),
            unit=unit,
            on_change=lambda value, key=key: self._typed(key, value),
        )
        if name:
            field.widget.setObjectName(name)
        caption = QtWidgets.QLabel(label)
        form.addRow(caption, field.widget)
        if self._formula_key(key):
            self.formula_inputs = getattr(self, "formula_inputs", [])
            self.formula_inputs.append(preview.FormulaInput(self, key, field))
        return field, caption

    def _formula_key(self, key):
        """True if a formula typed in this field stays linked (a parameter drives it)."""
        return key in primitives.FORMULA_PROPS.get(self.kind, {})

    def activate(self, name):
        """The Plane box clicked: pick another plane (Fusion re-opens the selection)."""
        if name == "plane" and self.state == "ready":
            self._wait_for_plane()
            return
        self.plane_field.set_active(name == "plane")

    def clear_field(self, name):
        if name == "plane" and self.state in ("ready", "place"):
            self._wait_for_plane()

    # -- start ------------------------------------------------------------------------------------------
    def _ensure_body(self):
        """The body to work in: the active one, else the first one, else a new one (made
        inside this command's undo step, like Fusion's first primitive in a new design)."""
        body = commands.find_body()
        if body is not None:
            return body
        from . import bodies

        body = bodies.new_body(self.doc)
        try:
            Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        except Exception as exc:
            warn("could not activate %s: %s" % (body.Label, exc))
        self.doc.recompute()
        return body

    def _start(self):
        from . import sketch_ui

        target = None
        try:
            target = sketch_ui.sketch_target()
        except Exception:
            target = None
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        if target is not None:
            self._set_plane(target)
        else:
            self._wait_for_plane()

    def _wait_for_plane(self):
        from . import sketch_ui

        self._stop_placing()
        self.state = "plane" if self.target is None else "replane"
        self.plane_field.set_active(True)
        self.info.setText("Click a plane or a flat face to put the %s on." % self.title.lower())
        if self.planes is None and self.body is not None:
            try:
                self.planes = sketch_ui.PlanePicker(
                    Gui.ActiveDocument.ActiveView,
                    self.body,
                    lambda plane: QtCore.QTimer.singleShot(0, lambda: self._plane_clicked(plane)),
                )
            except Exception as exc:
                warn("origin planes unavailable: %s" % exc)

    def _remove_planes(self):
        if self.planes is not None:
            self.planes.remove()
            self.planes = None

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        self._remove_planes()
        self._stop_placing()

    @safe
    def _plane_clicked(self, plane):
        if self._closed or self.state not in ("plane", "replane"):
            return
        self._set_plane((plane, ""))

    @safe
    def _selection_changed(self):
        if self._closed:
            return
        from . import sketch_ui

        selection = Gui.Selection.getSelectionEx()
        if not selection:
            return
        if self.state not in ("plane", "replane") or self._handle_busy():
            Gui.Selection.clearSelection()  # placing / sizing: clicks are not picks
            return
        mine = [s for s in selection if s.Object.Document.Name == self.doc.Name]
        target = sketch_ui.sketch_target(mine) if mine else None
        Gui.Selection.clearSelection()
        if target is None:
            if mine:
                self.message.setText("⚠ Pick a flat face or a plane.")
            return
        target = self._before_this(target)
        if target is None:
            self.message.setText(
                "⚠ That face belongs to this %s itself. Pick a face that was there before it."
                % self.title.lower()
            )
            return
        self._set_plane(target)

    def _before_this(self, ref):
        """A face clicked on this step's own preview, looked up on the part before it."""
        obj, sub = ref
        if self.target is None or primitives.is_plane(obj):
            return ref
        body = primitives.owner_body(self.target)
        if obj is not self.target and not self._later(obj, body):
            return ref
        base = self.target.BaseFeature
        if base is None or base.Shape.isNull():
            return None
        face = profile_pick.global_face(obj, sub)
        if face is None:
            return None
        name = profile_pick.face_name_in(base, face)
        return (base, name) if name else None

    def _later(self, obj, body):
        if body is None or primitives.owner_body(obj) is not body:
            return False
        group = list(body.Group)
        try:
            return group.index(obj) > group.index(self.target)
        except ValueError:
            return False

    def _set_plane(self, ref):
        try:
            ref = primitives.check_ref(ref)
            primitives.global_frame(ref)
        except PrimitiveError as exc:
            self.message.setText("⚠ %s" % exc)
            return
        self.ref = ref
        self._remove_planes()
        self.activate(None)
        self.message.setText("")
        self._show_plane()
        owner = primitives.owner_body(ref[0])
        if owner is not None and owner is not self.body and self.target is None:
            self.body = owner
            try:
                Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", owner)
            except Exception as exc:
                warn("could not activate %s: %s" % (owner.Label, exc))
        if self.state == "replane" or self.target is not None:
            self.state = "ready"
            self.info.setText("")
            self._changed(new_geometry=True)
            return
        self._start_placing()

    def _show_plane(self):
        self.plane_field.set_text(primitives.ref_label(self.ref) if self.ref else "")

    # -- placing ------------------------------------------------------------------------------------------
    def _start_placing(self):
        self.state = "place"
        self.points = []
        self.info.setText(self.HINTS[0])
        try:
            self.placer = Placer(
                Gui.ActiveDocument.ActiveView,
                primitives.global_frame(self.ref),
                self._outline,
                self._clicked,
                on_move=self._mouse_moved,
                blocked=self._handle_at,
            )
        except Exception as exc:
            warn("%s placing unavailable: %s" % (self.title, exc))

    def _stop_placing(self):
        if self.placer is not None:
            self.placer.remove()
            self.placer = None

    @safe
    def _mouse_moved(self, points, mouse):
        if self.state == "place":
            self._live(points, mouse)

    @safe
    def _clicked(self, point):
        if self._closed or self.state != "place":
            return
        if self.points and math.hypot(
            point[0] - self.points[-1][0], point[1] - self.points[-1][1]
        ) < (1e-6):
            return  # the same spot twice: a size cannot be 0
        self.points.append(point)
        if self.placer is not None:
            self.placer.points = list(self.points)
        if len(self.points) < self.clicks:
            self.info.setText(self.HINTS[min(len(self.points), len(self.HINTS) - 1)])
            return
        self._placed(list(self.points))
        self._stop_placing()
        self.state = "ready"
        self.info.setText("")
        self._show_fields()
        self._changed(new_geometry=True)

    # -- changes --------------------------------------------------------------------------------------------
    @safe
    def _typed(self, key, value):
        if self._quiet:
            return
        self.options[key] = value
        handle = self.handles.get(key)
        if handle is not None:
            handle.set_value(value)
        self._changed(new_geometry=True)

    # -- shared drawing helpers ------------------------------------------------------------------------
    def _mark(self):
        """Half the size of the + drawn at the mouse while placing (a few pixels)."""
        try:
            frame = primitives.global_frame(self.ref)
            return 6.0 * view_scale(Gui.ActiveDocument.ActiveView, frame.Base)
        except Exception:
            return 1.0

    def _circle_outline(self, points, mouse):
        if not points:
            return cross_points(mouse[0], mouse[1], self._mark())
        cx, cy = points[0]
        r = math.hypot(mouse[0] - cx, mouse[1] - cy)
        return [circle_points(cx, cy, r)] + cross_points(cx, cy, self._mark())

    def _height_value(self, field, value):
        value = round(value, 2)
        if abs(value) < 0.01:
            value = 0.01 if value >= 0 else -0.01
        self.options["height"] = value
        self.set_field(field, value)

    def _size_value(self, key, field, value):
        value = max(0.02, round(abs(value), 2))
        self.options[key] = value
        self.set_field(field, value)

    @safe
    def _choice(self, *_):
        if self._quiet:
            return
        self._collect()
        self._changed(new_geometry=True)

    @safe
    def _operation_picked(self, _index):
        self.user_picked_operation = True
        self._changed()

    def _base_shape(self):
        """The part the step builds on (global), for the operation Fusion picks."""
        body = primitives.owner_body(self.ref[0]) if self.ref else self.body
        if body is None:
            return None
        if self.target is not None and primitives.owner_body(self.target) is body:
            return primitives.base_shape(body, before=self.target)
        return primitives.base_shape(body)

    def _auto_operation(self):
        if self.user_picked_operation or self.ref is None or self.state != "ready":
            return
        try:
            wanted = self._auto(self._base_shape())
        except PrimitiveError:
            return
        except Exception:
            return
        if wanted != self.options["operation"]:
            self.options["operation"] = wanted
            self._quiet = True
            set_combo(self.operation, wanted)
            self._quiet = False

    def _changed(self, new_geometry=False):
        self._collect()
        self.options["operation"] = self.operation.currentData()
        self._auto_operation()
        self.dirty = True
        if new_geometry:
            self._geometry_changed = True
        self.schedule()

    def _recompute(self):
        try:
            if self.doc.Recomputing:
                self._timer.start()  # FreeCAD is still busy: try again shortly
                return
            if self.dirty and self.state == "ready":
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
        if self.ref is None:
            return
        try:
            before = self.target
            self.target = self._build()
            self.error = ""
            if before is None or self.target is not before:
                self._geometry_changed = True
        except PrimitiveError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This %s cannot be built: %s" % (self.title.lower(), exc)
        if self.error and self.target is not None:
            actual = self._feature_operation()
            if actual != self.options["operation"]:
                self.options["operation"] = actual
                self._quiet = True
                set_combo(self.operation, actual)
                self._quiet = False

    def _feature_operation(self):
        try:
            return self._read(self.target)[1]["operation"]
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
        text = _plain(preview.failure(self.target))
        self.message.setText("⚠ " + text if text else "")

    # -- formulas (preview.FormulaInput calls these) -------------------------------------------------------
    def formula_typed(self, key, text, value):
        self.formula_error = ""
        self.options.setdefault("expressions", {})[key] = text
        self._typed(key, value)
        self.show_formulas()

    def formula_cleared(self, key):
        self.formula_error = ""
        if self.options.get("expressions", {}).pop(key, None) is not None:
            self.show_formulas()
            self._changed()

    def formula_failed(self, key, text):
        self.formula_error = text
        self.message.setText("⚠ " + text)

    def show_formulas(self):
        rows = [
            "%s = %s" % (k.replace("_", " ").capitalize(), v)
            for k, v in sorted(self.options.get("expressions", {}).items())
            if v
        ]
        self.formulas.setText("\n".join(rows))

    def drop_formula(self, key):
        if self.options.get("expressions", {}).pop(key, None) is not None:
            self.show_formulas()

    # -- handles ------------------------------------------------------------------------------------------
    def _handle_at(self, position):
        return any(h.hit(position) for h in self.handles.values())

    def _handle_busy(self):
        return any(h.busy() for h in self.handles.values())

    def _remove_handles(self):
        for handle in self.handles.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.handles = {}

    def _handles_wrong(self):
        if any(h.dragging() for h in self.handles.values()):
            return False
        wanted = {spec[0] for spec in self._specs()}
        return set(self.handles) != wanted

    def _specs(self):
        if self.state != "ready" or self.ref is None or self.target is None:
            return []
        try:
            return self._handle_specs()
        except Exception as exc:
            warn("%s handles: %s" % (self.title, exc))
            return []

    HANDLE_PIXELS = 26.0  # Fusion's arrows keep their size on screen

    def handle_size(self):
        try:
            frame = primitives.global_frame(self.ref)
            o = self.options
            at = frame.multVec(App.Vector(float(o.get("x", 0)), float(o.get("y", 0)), 0))
            return self.HANDLE_PIXELS * view_scale(Gui.ActiveDocument.ActiveView, at)
        except Exception:
            return 5.0

    def _make_handles(self):
        if self._closed:
            return
        if any(h.dragging() for h in self.handles.values()):
            return  # never pull a handle from under the mouse
        self._remove_handles()
        specs = self._specs()
        if not specs:
            return
        size = self.handle_size()
        for name, origin, direction, value, scale, on_drag in specs:
            try:
                self.handles[name] = LinearHandle(
                    origin,
                    direction,
                    value,
                    size,
                    on_drag=lambda v, n=name, f=on_drag: self._handle_dragged(n, f, v),
                    on_release=lambda v, n=name, f=on_drag: self._handle_released(n, f, v),
                    scale=scale,
                    name=name,
                )
            except Exception as exc:
                warn("%s handle %s unavailable: %s" % (self.title, name, exc))

    @safe
    def _handle_dragged(self, name, apply, value):
        self.drop_formula(name)
        apply(value)
        self._changed()

    @safe
    def _handle_released(self, name, apply, value):
        apply(value)
        self._changed(new_geometry=True)

    def set_field(self, field, value):
        self._quiet = True
        try:
            field.set_value(value)
        finally:
            self._quiet = False

    # -- OK / Cancel ------------------------------------------------------------------------------------------
    def accept(self):
        try:
            return self._accept()
        except Exception as exc:
            warn("%s OK: %s" % (self.title, exc))
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        if self.target is None:
            if self.ref is None:
                text = "Pick a plane or a flat face first."
            elif self.state == "place":
                text = self.HINTS[min(len(self.points), len(self.HINTS) - 1)]
            else:
                text = self.error or "This %s cannot be built." % self.title.lower()
            self.message.setText("⚠ " + text)
            return False
        if self.formula_error:
            self.message.setText("⚠ " + self.formula_error)
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
        self._finishing(feature)
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        body = primitives.owner_body(feature)
        if body is not None and body is not commands.active_body():
            try:
                Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
            except Exception as exc:
                warn("could not activate %s: %s" % (body.Label, exc))
        log("%s done" % self.title)
        return True

    def _finishing(self, feature):
        """Just before OK closes the dialog (Pipe hides its path sketch here)."""

    def reject(self):
        try:
            self._timer.stop()
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
        except Exception as exc:
            warn("%s Cancel: %s" % (self.title, exc))
        try:
            self._close()
        except Exception as exc:
            warn("%s Cancel: %s" % (self.title, exc))
        return True

    def cleanup(self):
        self._unwatch()
        self.escape.remove()
        self.undo_guard.remove()
        self.enter.remove()
        self._remove_handles()
        super().cleanup()


PLAIN = (
    ("multiple solids", "This would make separate solids. Use New Body or move it onto the part."),
    ("command not done", "These sizes cannot make this shape. Change them."),
    ("not a solid", "Nothing is left: it does not touch the body here."),
)


def _plain(text):
    for needle, said in PLAIN:
        if needle.lower() in (text or "").lower():
            return said
    return text


# -- Box ---------------------------------------------------------------------------------------------------------
class BoxPanel(PlacedPanel):
    title = "Box"
    icon = "box"
    kind = "box"
    clicks = 2
    last = None
    HINTS = ("Click the first corner on the plane.", "Click the opposite corner.")

    def _build_fields(self, form):
        self.length, _ = self.distance_field(form, "Length", "length", name="SciForgeBox_length")
        self.width, _ = self.distance_field(form, "Width", "width", name="SciForgeBox_width")
        self.height, _ = self.distance_field(form, "Height", "height", name="SciForgeBox_height")

    def _show_fields(self):
        self._quiet = True
        try:
            self.length.set_value(self.options["length"])
            self.width.set_value(self.options["width"])
            self.height.set_value(self.options["height"])
            set_combo(self.operation, self.options["operation"])
        finally:
            self._quiet = False
        self.show_formulas()

    def _collect(self):
        self.options["length"] = abs(self.length.value())
        self.options["width"] = abs(self.width.value())
        self.options["height"] = self.height.value()

    def _outline(self, points, mouse):
        if not points:
            return cross_points(mouse[0], mouse[1], self._mark())
        (x0, y0), (x1, y1) = points[0], mouse
        return [[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]]

    def _live(self, points, mouse):
        if points:
            self.set_field(self.length, abs(mouse[0] - points[0][0]))
            self.set_field(self.width, abs(mouse[1] - points[0][1]))

    def _placed(self, points):
        (x0, y0), (x1, y1) = points
        length, width = abs(x1 - x0), abs(y1 - y0)
        if length < 1e-6 or width < 1e-6:
            # Two corners on one line: a square from the longer side, sized in the fields.
            side = max(length, width) or 10.0
            length = length or side
            width = width or side
        self.options.update(
            x=x0,
            y=y0,
            sx=1.0 if x1 >= x0 else -1.0,
            sy=1.0 if y1 >= y0 else -1.0,
            length=length,
            width=width,
            height=primitives.nice(min(length, width)),
        )

    def _handle_specs(self):
        o = self.options
        frame = primitives.global_frame(self.ref)
        u = frame.Rotation.multVec(App.Vector(1, 0, 0))
        v = frame.Rotation.multVec(App.Vector(0, 1, 0))
        n = frame.Rotation.multVec(App.Vector(0, 0, 1))
        sx, sy = float(o.get("sx", 1.0)), float(o.get("sy", 1.0))
        length, width, height = float(o["length"]), float(o["width"]), float(o["height"])
        corner = frame.multVec(App.Vector(float(o["x"]), float(o["y"]), 0))
        center = corner + u * (sx * length / 2.0) + v * (sy * width / 2.0)
        mid = n * (height / 2.0)
        return [
            ("height", center, n, height, 1.0, lambda v: self._height_value(self.height, v)),
            (
                "length",
                corner + v * (sy * width / 2.0) + mid,
                u * sx,
                length,
                1.0,
                lambda v: self._size_value("length", self.length, v),
            ),
            (
                "width",
                corner + u * (sx * length / 2.0) + mid,
                v * sy,
                width,
                1.0,
                lambda v: self._size_value("width", self.width, v),
            ),
        ]


# -- Cylinder ----------------------------------------------------------------------------------------------------
class CylinderPanel(PlacedPanel):
    title = "Cylinder"
    icon = "cylinder"
    kind = "cylinder"
    clicks = 2
    last = None
    HINTS = ("Click the centre on the plane.", "Click a point on the circle (its size).")

    def _build_fields(self, form):
        self.diameter, _ = self.distance_field(
            form, "Diameter", "diameter", name="SciForgeCylinder_diameter"
        )
        self.height, _ = self.distance_field(
            form, "Height", "height", name="SciForgeCylinder_height"
        )

    def _show_fields(self):
        self._quiet = True
        try:
            self.diameter.set_value(self.options["diameter"])
            self.height.set_value(self.options["height"])
            set_combo(self.operation, self.options["operation"])
        finally:
            self._quiet = False
        self.show_formulas()

    def _collect(self):
        self.options["diameter"] = abs(self.diameter.value())
        self.options["height"] = self.height.value()

    def _outline(self, points, mouse):
        return self._circle_outline(points, mouse)

    def _live(self, points, mouse):
        if points:
            r = math.hypot(mouse[0] - points[0][0], mouse[1] - points[0][1])
            self.set_field(self.diameter, 2.0 * r)

    def _placed(self, points):
        (cx, cy), (px, py) = points
        diameter = 2.0 * math.hypot(px - cx, py - cy)
        self.options.update(x=cx, y=cy, diameter=diameter, height=primitives.nice(diameter))

    def _handle_specs(self):
        o = self.options
        frame = primitives.global_frame(self.ref)
        u = frame.Rotation.multVec(App.Vector(1, 0, 0))
        n = frame.Rotation.multVec(App.Vector(0, 0, 1))
        center = frame.multVec(App.Vector(float(o["x"]), float(o["y"]), 0))
        height = float(o["height"])
        return [
            ("height", center, n, height, 1.0, lambda v: self._height_value(self.height, v)),
            (
                "diameter",
                center + n * (height / 2.0),
                u,
                float(o["diameter"]),
                0.5,
                lambda v: self._size_value("diameter", self.diameter, v),
            ),
        ]


# -- Sphere --------------------------------------------------------------------------------------------------------
class SpherePanel(PlacedPanel):
    title = "Sphere"
    icon = "sphere"
    kind = "sphere"
    clicks = 1
    last = None
    HINTS = ("Click the centre on the plane.",)

    def _build_fields(self, form):
        self.diameter, _ = self.distance_field(
            form, "Diameter", "diameter", name="SciForgeSphere_diameter"
        )

    def _show_fields(self):
        self._quiet = True
        try:
            self.diameter.set_value(self.options["diameter"])
            set_combo(self.operation, self.options["operation"])
        finally:
            self._quiet = False
        self.show_formulas()

    def _collect(self):
        self.options["diameter"] = abs(self.diameter.value())

    def _outline(self, points, mouse):
        return cross_points(mouse[0], mouse[1], self._mark())

    def _placed(self, points):
        cx, cy = points[0]
        try:
            view = Gui.ActiveDocument.ActiveView
            frame = primitives.global_frame(self.ref)
            pixel = view_scale(view, frame.multVec(App.Vector(cx, cy, 0)))
            width = view.getSize()[0] * pixel
            diameter = primitives.nice(width / 8.0)
        except Exception:
            diameter = 10.0
        self.options.update(x=cx, y=cy, diameter=diameter)

    def _handle_specs(self):
        o = self.options
        frame = primitives.global_frame(self.ref)
        u = frame.Rotation.multVec(App.Vector(1, 0, 0))
        center = frame.multVec(App.Vector(float(o["x"]), float(o["y"]), 0))
        return [
            (
                "diameter",
                center,
                u,
                float(o["diameter"]),
                0.5,
                lambda v: self._size_value("diameter", self.diameter, v),
            )
        ]


# -- Torus ----------------------------------------------------------------------------------------------------------
class TorusPanel(PlacedPanel):
    title = "Torus"
    icon = "torus"
    kind = "torus"
    clicks = 2
    last = None
    HINTS = ("Click the centre on the plane.", "Click a point on the inner circle (its size).")

    def _build_fields(self, form):
        self.inner, _ = self.distance_field(
            form, "Inner Diameter", "inner_diameter", name="SciForgeTorus_inner"
        )
        self.tube, _ = self.distance_field(
            form, "Torus Diameter", "torus_diameter", name="SciForgeTorus_tube"
        )
        self.position = combo(POSITION_LABELS, self.options["position"], "SciForgeTorus_position")
        form.addRow("Position", self.position)
        self.position.currentIndexChanged.connect(self._choice)

    def _show_fields(self):
        self._quiet = True
        try:
            self.inner.set_value(self.options["inner_diameter"])
            self.tube.set_value(self.options["torus_diameter"])
            set_combo(self.position, self.options["position"])
            set_combo(self.operation, self.options["operation"])
        finally:
            self._quiet = False

    def _collect(self):
        self.options["inner_diameter"] = abs(self.inner.value())
        self.options["torus_diameter"] = abs(self.tube.value())
        self.options["position"] = self.position.currentData()

    def _outline(self, points, mouse):
        return self._circle_outline(points, mouse)

    def _live(self, points, mouse):
        if points:
            r = math.hypot(mouse[0] - points[0][0], mouse[1] - points[0][1])
            self.set_field(self.inner, 2.0 * r)

    def _placed(self, points):
        (cx, cy), (px, py) = points
        inner = 2.0 * math.hypot(px - cx, py - cy)
        self.options.update(
            x=cx, y=cy, inner_diameter=inner, torus_diameter=primitives.nice(inner / 5.0)
        )

    def _handle_specs(self):
        o = self.options
        frame = primitives.global_frame(self.ref)
        u = frame.Rotation.multVec(App.Vector(1, 0, 0))
        n = frame.Rotation.multVec(App.Vector(0, 0, 1))
        center = frame.multVec(App.Vector(float(o["x"]), float(o["y"]), 0))
        major, _minor = primitives.torus_radii(o)
        return [
            (
                "inner_diameter",
                center,
                u * -1.0,
                float(o["inner_diameter"]),
                0.5,
                lambda v: self._size_value("inner_diameter", self.inner, v),
            ),
            (
                "torus_diameter",
                center + u * major,
                n,
                float(o["torus_diameter"]),
                0.5,
                lambda v: self._size_value("torus_diameter", self.tube, v),
            ),
        ]


# -- view provider of the intersect feature ------------------------------------------------------------------------
class ViewProviderPrimitive:
    """View provider of the Intersect primitive (a SciForge feature)."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        kind = primitives.kind_of(getattr(self, "Object", None)) or "box"
        return ui_icon_path(kind)

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


# -- commands ------------------------------------------------------------------------------------------------------
PANELS = {"box": BoxPanel, "cylinder": CylinderPanel, "sphere": SpherePanel, "torus": TorusPanel}
TIPS = {
    "box": "Box: pick a plane or flat face, click two corners, drag the height. Join, cut, "
    "intersect or new body",
    "cylinder": "Cylinder: pick a plane or flat face, click the centre and the circle, drag "
    "the height",
    "sphere": "Sphere: pick a plane or flat face and click the centre; drag the diameter",
    "torus": "Torus: pick a plane or flat face, click the centre and the inner circle; set the "
    "torus diameter and position",
}


def start(panel_class, doc=None):
    """Open a placing dialog (finishing whatever is open first)."""
    if not commands.finish_open_dialog():
        return None
    if App.ActiveDocument is None:
        App.newDocument("Design")
    panel = panel_class(doc or App.ActiveDocument)
    Gui.Control.showDialog(panel)
    log("%s started" % panel_class.title.lower())
    return panel


class PrimitiveCommand:
    kind = "box"

    def GetResources(self):
        return {
            "MenuText": primitives.TITLES[self.kind],
            "ToolTip": TIPS[self.kind],
            "Pixmap": ui_icon_path(self.kind),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            start(PANELS[self.kind])
        except Exception as exc:
            warn("%s failed to start: %s" % (primitives.TITLES[self.kind], exc))


class BoxCommand(PrimitiveCommand):
    kind = "box"


class CylinderCommand(PrimitiveCommand):
    kind = "cylinder"


class SphereCommand(PrimitiveCommand):
    kind = "sphere"


class TorusCommand(PrimitiveCommand):
    kind = "torus"


def edit(feature):
    """Open the dialog on an existing box / cylinder / sphere / torus (timeline double-click).
    One FreeCAD's own primitive command made (no SciForge data) opens FreeCAD's panel."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        if not primitives.is_ours(feature):
            Gui.ActiveDocument.setEdit(feature.Name)
            return
        kind = primitives.kind_of(feature)
        Gui.Control.showDialog(PANELS[kind](feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


COMMANDS = {
    "SciForge_Box": BoxCommand,
    "SciForge_Cylinder": CylinderCommand,
    "SciForge_Sphere": SphereCommand,
    "SciForge_Torus": TorusCommand,
}
EDITORS = {}
for _word in primitives.NATIVE.values():
    EDITORS["PartDesign::Additive" + _word] = edit
    EDITORS["PartDesign::Subtractive" + _word] = edit
    EDITORS["SciForge::" + _word] = edit
