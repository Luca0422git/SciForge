# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dialog pieces shared by Sweep, Loft, Rib and Web (sweep_ui.py, loft_ui.py, rib_ui.py).

- RegionPicker: Extrude's profile shading, except that a click on a line is left to the
  curve boxes (a path, a rail, a rib curve).
- CurveOverlay: the picked curves drawn thick over the part, as Fusion highlights them.
- PathHandle: a blue ball on the path that slides along it (Sweep's distance).
- RatioBox: a 0..1 number box (Sweep's Distance) that reads "0,5" and "0.5" alike.
- base_element(): an edge or face clicked on the preview, as it was before the step.
- line_under_mouse(): a sketch line or a part edge under the mouse.

Mouse events come through FreeCAD's view.addEventCallback (safe), work is done from Qt
timers (feature guide rules 1 and 2), and nothing here keeps a FreeCAD-owned Coin node.
"""

import functools
import math
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import drag_guard, handles3d, profile_pick, warn
from .compat import QtCore, QtGui, QtWidgets

HANDLE = (0.30, 0.62, 0.95)  # Fusion's manipulator blue
HANDLE_ACTIVE = (0.55, 0.80, 1.0)
PATH_COLOR = (0.12, 0.53, 0.90)
RAIL_COLOR = (0.95, 0.55, 0.15)


def safe(prefix):
    """Decorator for dialog reactions (Qt slots): an exception is logged and shown in the
    dialog's message, never printed as a traceback in the Report view."""

    def wrap(method):
        @functools.wraps(method)
        def wrapper(self, *args):
            try:
                return method(self, *args)
            except Exception as exc:
                warn("%s: %s" % (prefix, exc))
                try:
                    self.message.setText("⚠ %s" % exc)
                except Exception:
                    pass
            return None

        return wrapper

    return wrap


def combo(pairs, current=None):
    box = QtWidgets.QComboBox()
    for item in pairs:
        label, value = item[0], item[1]
        box.addItem(label, value)
        if len(item) > 2 and not item[2]:
            model_item = box.model().item(box.count() - 1)
            if model_item is not None:
                model_item.setEnabled(False)
            if len(item) > 3:
                box.setItemData(box.count() - 1, item[3], QtCore.Qt.ToolTipRole)
    set_combo(box, current)
    return box


def set_combo(box, value):
    for i in range(box.count()):
        if box.itemData(i) == value:
            box.setCurrentIndex(i)
            return True
    return False


# -- clicks ----------------------------------------------------------------------------------------
def info_at(position):
    try:
        view = Gui.ActiveDocument.ActiveView
        return view.getObjectInfo((int(position[0]), int(position[1])))
    except Exception:
        return None


def line_under_mouse(doc, position, sketch_only=False):
    """True if a sketch line (or, unless sketch_only, an edge of the part) is under the
    mouse: such a click picks a curve, not the area around it."""
    info = info_at(position)
    if not info or not str(info.get("Component", "")).startswith("Edge"):
        return False
    obj = doc.getObject(str(info.get("Object", "")))
    if obj is None:
        return False
    return obj.isDerivedFrom("Sketcher::SketchObject") or not sketch_only


class RegionPicker(profile_pick.ProfilePicker):
    """Extrude's profile picker; a click on a line or a handle is left to the dialog."""

    def __init__(self, view, sketches, on_pick, occluder=None, skip=None):
        self._skip = skip
        super().__init__(view, sketches, on_pick, occluder=occluder)
        # The shading lies on the preview's own end face (a sweep or loft starts there);
        # pulled towards the viewer it shows cleanly instead of in flickering stripes.
        try:
            for i in range(self.root.getNumChildren()):
                node = self.root.getChild(i)
                if node.isOfType(self.coin.SoPolygonOffset.getClassTypeId()):
                    node.factor.setValue(-1.0)
                    node.units.setValue(-4.0)
        except Exception:
            pass

    def _button(self, info):
        try:
            if self._skip is not None and self._skip(info.get("Position")):
                return
        except Exception:
            pass
        super()._button(info)


def prepare_regions(body, extra=()):
    """Turn on the closed areas of every sketch a dialog offers *before* the dialog opens its
    undo step. Turning them on changes the sketch (FreeCAD's MakeInternals, a recompute
    after an undo); inside the step that change was the first one, and FreeCAD then threw
    away the Redo list, even when the dialog was cancelled with Esc."""
    from . import extrude

    try:
        sketches = profile_pick.candidate_sketches(body, extra)
    except Exception:
        return
    for sketch in sketches:
        try:
            extrude.ensure_regions(sketch)
        except Exception:
            pass


def base_element(base, obj, short):
    """(base, name) of the edge / face `short` of `obj` (the preview, or a later step) that
    is also in `base` (the step before), matched by geometry; None if only obj has it."""
    if base is None or obj is None:
        return None
    if obj is base:
        return (obj, short)
    try:
        item = obj.Shape.getElement(short)
    except Exception:
        return None
    kind = "Edge" if short.startswith("Edge") else "Face"
    pool = base.Shape.Edges if kind == "Edge" else base.Shape.Faces
    for i, cand in enumerate(pool, start=1):
        if _same_element(cand, item, kind):
            return (base, "%s%d" % (kind, i))
    return None


def _same_element(a, b, kind):
    if a.isSame(b):
        return True
    if kind == "Face":
        return profile_pick.same_face(a, b)
    try:
        if abs(a.Length - b.Length) > 1e-6 * max(1.0, a.Length):
            return False
        ends_a = [v.Point for v in a.Vertexes]
        ends_b = [v.Point for v in b.Vertexes]
        if len(ends_a) != len(ends_b):
            return False
        if not all(min((p - q).Length for q in ends_b) < 1e-6 for p in ends_a):
            return False
        mid_a = a.valueAt(a.FirstParameter + (a.LastParameter - a.FirstParameter) / 2)
        return b.distToShape(_vertex(mid_a))[0] < 1e-6
    except Exception:
        return False


def _vertex(point):
    import Part

    return Part.Vertex(point)


# -- drawing picked curves ---------------------------------------------------------------------
class CurveOverlay:
    """Picked curves drawn thick over the part (one colour per set)."""

    def __init__(self, view):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.root = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.sets = {}
        view.getSceneGraph().addChild(self.root)

    def show(self, name, edges, color, width=4.0, dashed=False):
        """Draw `edges` (global Part edges) as set `name`, replacing what it showed."""
        coin = self.coin
        old = self.sets.pop(name, None)
        if old is not None:
            try:
                self.root.removeChild(old)
            except Exception:
                pass
        if not edges:
            return
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(*color)
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(width)
        if dashed:
            style.linePattern.setValue(0xF0F0)
        coords = coin.SoCoordinate3()
        lines = coin.SoLineSet()
        points, counts = [], []
        for edge in edges:
            try:
                straight = edge.Curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment")
                pts = edge.discretize(2 if straight else 32)
            except Exception:
                continue
            points += [(p.x, p.y, p.z) for p in pts]
            counts.append(len(pts))
        if not points:
            return
        coords.point.setValues(0, len(points), points)
        lines.numVertices.setValues(0, len(counts), counts)
        for node in (material, style, coords, lines):
            sep.addChild(node)
        self.root.addChild(sep)
        self.sets[name] = sep

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass
        self.sets = {}


# -- a handle that slides along the path ---------------------------------------------------------
_GRAB = {"time": 0.0}


class PathHandle:
    """A blue ball on the path, at `value` (0..1) of `samples` = [(0..1, global point)],
    with an arrow along the path. Dragging it slides it along the path (the nearest sample
    to the mouse on screen); on_drag(value) while dragging, on_release(value) at the end.
    Drawn over the part and grabbed by distance on screen (like revolve_ui.AngleHandle),
    so it is not a Coin dragger."""

    POLL_MS = 30
    GRAB_PIXELS = 14.0

    def __init__(self, samples, value, size, on_drag=None, on_release=None, color=HANDLE):
        from pivy import coin

        self.coin = coin
        self.view = Gui.ActiveDocument.ActiveView
        self.samples = [(float(f), App.Vector(p)) for f, p in samples]
        self.size = float(size)
        self.color = color
        self.on_drag = on_drag
        self.on_release = on_release
        self._value = float(value)
        self._shown = None
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
        self.place = coin.SoTransform()
        self.root.addChild(self.place)
        self.root.addChild(self._shape(coin))
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

    def _shape(self, coin):
        s = self.size
        sep = coin.SoSeparator()
        ball = coin.SoSphere()
        ball.radius.setValue(0.3 * s)
        sep.addChild(ball)
        move = coin.SoTranslation()
        move.translation.setValue(0.0, 0.55 * s, 0.0)
        sep.addChild(move)
        cone = coin.SoCone()
        cone.bottomRadius.setValue(0.22 * s)
        cone.height.setValue(0.45 * s)
        sep.addChild(cone)
        return sep

    def point_at(self, value):
        """Global point of the path at `value` (between samples, linear)."""
        value = max(0.0, min(1.0, value))
        for (f0, p0), (f1, p1) in zip(self.samples, self.samples[1:]):
            if f0 - 1e-12 <= value <= f1 + 1e-12:
                t = 0.0 if f1 - f0 < 1e-12 else (value - f0) / (f1 - f0)
                return p0 + (p1 - p0) * t
        return self.samples[-1][1]

    def _direction(self, value):
        a = self.point_at(max(0.0, value - 0.01))
        b = self.point_at(min(1.0, value + 0.01))
        d = b - a
        if d.Length < 1e-12:
            d = self.samples[-1][1] - self.samples[0][1]
        if d.Length < 1e-12:
            return App.Vector(0, 0, 1)
        d.normalize()
        return d

    def value(self):
        return self._value

    def set_value(self, value):
        self._value = float(value)
        self._pending = None
        self._draw()

    def _draw(self):
        if self._shown is not None and abs(self._shown - self._value) < 1e-9:
            return
        self._shown = self._value
        p = self.point_at(self._value)
        self.place.translation.setValue(p.x, p.y, p.z)
        rotation = App.Rotation(App.Vector(0, 1, 0), self._direction(self._value))
        self.place.rotation.setValue(*rotation.Q)

    def _paint(self):
        state = self._hover or self._drag
        if self._painted == state:
            return
        self._painted = state
        color = HANDLE_ACTIVE if state else self.color
        self.material.diffuseColor.setValue(*color)
        self.material.emissiveColor.setValue(color[0] * 0.5, color[1] * 0.5, color[2] * 0.5)

    def _screen(self, point):
        x, y = self.view.getPointOnViewport(point)
        return float(x), float(y)

    def hit(self, position):
        try:
            bx, by = self._screen(self.point_at(self._value))
            return math.hypot(float(position[0]) - bx, float(position[1]) - by) <= self.GRAB_PIXELS
        except Exception:
            return False

    def _nearest(self, position):
        """The value of the path point nearest the mouse on screen."""
        px, py = float(position[0]), float(position[1])
        best = None
        screen = [(f, self._screen(p)) for f, p in self.samples]
        for (f0, (x0, y0)), (f1, (x1, y1)) in zip(screen, screen[1:]):
            dx, dy = x1 - x0, y1 - y0
            length2 = dx * dx + dy * dy
            t = 0.0 if length2 < 1e-9 else ((px - x0) * dx + (py - y0) * dy) / length2
            t = max(0.0, min(1.0, t))
            d = math.hypot(px - (x0 + dx * t), py - (y0 + dy * t))
            if best is None or d < best[0]:
                best = (d, f0 + (f1 - f0) * t)
        return self._value if best is None else best[1]

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
                    # The release of a drag ending over the part is kept by FreeCAD's
                    # selection; Qt's is watched too (handles3d.ReleaseWatch).
                    handles3d.watch_release(self)
            elif self._drag:
                self._drag = False
                self._released = True
                self._last_event = time.time()
                handles3d.stop_watching(self)
        except Exception as exc:
            warn("path handle: %s" % exc)

    def _moved(self, info):
        try:
            position = info["Position"]
            if not self._drag:
                self._hover = self.hit(position)
                return
            self._last_event = time.time()
            self._pending = self._nearest(position)
        except Exception as exc:
            warn("path handle: %s" % exc)

    def dragging(self):
        return self._drag

    def busy(self, seconds=0.6):
        return self._drag or time.time() - self._last_event < seconds

    def _poll(self):
        try:
            if Gui.ActiveDocument is None:
                self._timer.stop()
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
            warn("path handle: %s" % exc)

    def remove(self):
        try:
            self._timer.stop()
        except Exception:
            pass
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


# -- a 0..1 number box ------------------------------------------------------------------------------
class RatioBox(QtWidgets.QDoubleSpinBox):
    """Fusion's Distance box of a sweep: a share of the path from 0 to 1. A decimal comma
    or point both work (Fusion reads either); the value counts when typing is finished.
    formulas=True: a parameter or a formula can be typed too ("share", "share / 2"); the
    dialog reads it through RatioField and preview.FormulaInput."""

    def __init__(self, value=1.0, parent=None, formulas=False):
        super().__init__(parent)
        self.formulas = formulas
        self.setDecimals(3)
        self.setRange(0.0, 1.0)
        self.setSingleStep(0.05)
        self.setKeyboardTracking(False)
        self.setLocale(QtCore.QLocale.c())
        self.setValue(float(value))

    def validate(self, text, pos):
        if self.formulas and any(c.isalpha() or c in "()*/+_=" for c in text):
            # A formula is being typed: let it be (FormulaInput reads it when typing ends;
            # the box itself keeps its last number).
            return (QtGui.QValidator.Intermediate, text, pos)
        return super().validate(text.replace(",", "."), pos)

    def valueFromText(self, text):
        try:
            return float(text.replace(",", ".").strip() or 0.0)
        except ValueError:
            return self.value()


class RatioField:
    """A RatioBox seen as a taskui.DistanceField by preview.FormulaInput: a plain number
    (unit ""), parse / take / set_value."""

    unit = ""

    def __init__(self, box):
        self.widget = box

    def parse(self, text):
        try:
            return float((text or "").strip().replace(",", "."))
        except ValueError:
            raise ValueError("'%s' is not a value. Type a number from 0 to 1." % text)

    def value(self):
        return self.widget.value()

    def take(self, value):
        """Show `value` and tell the dialog (valueChanged), as if typed in the box."""
        self.widget.setValue(float(value))

    def set_value(self, value):
        """Show `value` without telling the dialog."""
        self.widget.blockSignals(True)
        try:
            self.widget.setValue(float(value))
        finally:
            self.widget.blockSignals(False)


def checkbox(text, checked):
    box = QtWidgets.QCheckBox(text)
    box.setChecked(bool(checked))
    return box


def keep_font(widget):
    """Bold section labels like Fusion's dialog headers."""
    font = QtGui.QFont(widget.font())
    font.setBold(True)
    widget.setFont(font)
    return widget
