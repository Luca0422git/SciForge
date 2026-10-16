# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's own sketch drawing handler: the base of the Fusion tools FreeCAD's Sketcher
does not have (Midpoint Line, 3-Point Rectangle, 2-Point / 2-Tangent / 3-Tangent Circle,
Tangent Arc, Edge Polygon, the slots, the conic; sketch_draw_tools.py), of Trim / Extend /
Break (sketch_modify_tools.py), the pick-two constraints (sketch_constrain_tools.py) and
Project to Surface (sketch_project_tool.py).

How a tool runs (the way FreeCAD's own tools feel, and Fusion's):

- The open sketch's view filter (sketch_mode._ViewFilter) gives every mouse event to the
  running tool first, its key filter every key. Moves go on to FreeCAD too (it lights up
  the point or curve under the pointer, as in its own tools); left presses and releases
  are the tool's (FreeCAD never selects or drags while a SciForge tool runs). Right
  click: the sketch's marking menu (OK / Cancel), middle button and wheel: the view.
- Where a click lands: on a sketch point (Coincident), the middle of a line (Symmetric,
  Fusion's midpoint), a curve (PointOnObject), a dashed guide from a hovered point
  (Horizontal / Vertical between the points) or the grid, like FreeCAD's own snapping
  and SciForge's inference (sketch_infer_core); Ctrl: exactly where the pointer is,
  nothing added (Fusion).
- Value boxes beside the shape (length, angle, diameter, width, sides, rho): digits go
  into the current box, Tab moves on, Enter takes the values; a typed value holds while
  the pointer gives the rest, and becomes a dimension (Fusion).
- The shape and all its constraints are one undo step named after the tool. The tool
  then waits for the next shape (Fusion's tools repeat); Esc stops it, OK in the
  right-click menu or Enter with nothing typed ends it.
- The cursor is a cross while the tool runs (sketch_mode.SketchSession.tool_running
  reads it, as for FreeCAD's tools). A FreeCAD tool started meanwhile (its own cursor)
  ends the SciForge tool.

Never lets an exception out of an event handler or timer (warn() and carry on).
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from . import log, warn
from . import sketch_infer_core as icore
from .compat import QtCore, QtGui, QtWidgets

PRESSES = (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonDblClick)
VERTEX_POSITIONS = {
    "Part::GeomPoint": (1,),
    "Part::GeomLineSegment": (1, 2),
    "Part::GeomCircle": (3,),
    "Part::GeomEllipse": (3,),
    "Part::GeomArcOfCircle": (1, 2, 3),
    "Part::GeomArcOfEllipse": (1, 2, 3),
    "Part::GeomArcOfHyperbola": (1, 2, 3),
    "Part::GeomArcOfParabola": (1, 2, 3),
    "Part::GeomBSplineCurve": (1, 2),
}
CROSS = QtCore.Qt.CrossCursor
LINE_TYPE = "Part::GeomLineSegment"


def _xy(v):
    return (v.x, v.y)


def _v(p):
    return App.Vector(p[0], p[1], 0)


def _rgb(hex_color):
    value = int(hex_color.lstrip("#"), 16)
    return ((value >> 16) / 255.0, ((value >> 8) & 0xFF) / 255.0, (value & 0xFF) / 255.0)


# -- where the pointer is ----------------------------------------------------------------
class Snap:
    """Where a point goes and what it sits on.

    point   the sketch point (x, y)
    raw     the pointer itself
    key     (geo, pos) of the sketch point it sits on (Coincident), or None
    mid_of  a line whose middle it sits on (Symmetric), or None
    curve   a curve it sits on (PointOnObject; -1 / -2 the axes), or None
    curve2  a second curve it sits on (where two curves cross), or None
    target  the sketch_infer_core.SnapPoint it snapped to exactly (an end, middle, centre,
            quadrant or crossing: the glyph shown), or None
    result  sketch_infer_core.Result of a guide / direction, or None
    free    Ctrl: nothing snapped, nothing added
    """

    def __init__(
        self,
        point,
        raw=None,
        key=None,
        mid_of=None,
        curve=None,
        result=None,
        free=False,
        target=None,
        curve2=None,
    ):
        self.point = point
        self.raw = raw if raw is not None else point
        self.key = key
        self.mid_of = mid_of
        self.curve = curve
        self.curve2 = curve2
        self.target = target
        self.result = result
        self.free = free

    @property
    def kind(self):
        return self.result.kind if self.result is not None else None

    def __repr__(self):
        return "Snap(%r, key=%r, mid=%r, curve=%r, kind=%r)" % (
            self.point,
            self.key,
            self.mid_of,
            self.curve,
            self.kind,
        )


class Geometry:
    """The sketch's points and curves for snapping, rebuilt when the sketch changed."""

    def __init__(self, sketch):
        from .sketch_infer import _add_geometry, describe

        verts = [((-1, 1), (0.0, 0.0))]  # the origin
        curves = [("line", (0.0, 0.0), (1.0, 0.0)), ("line", (0.0, 0.0), (0.0, 1.0))]
        lines = []
        # (geo, curve) for "which curve is under the pointer" (axes -1, -2 first)
        self.hits = [(-1, curves[0]), (-2, curves[1])]
        items = [("point", -1, (0.0, 0.0))]  # snap point descriptions (sketch_infer_core)
        for i, geo in enumerate(sketch.Geometry):
            try:
                construction = bool(sketch.getConstruction(i))
            except Exception:
                construction = False
            n = len(curves)
            _add_geometry(verts, curves, lines, i, geo, construction)
            for c in curves[n:]:
                self.hits.append((i, c))
            items.append(describe(i, geo))
        try:
            external = list(sketch.ExternalGeo)[2:]
        except Exception:
            external = []
        for k, geo in enumerate(external):
            n = len(curves)
            _add_geometry(verts, curves, lines, -3 - k, geo, False)
            for c in curves[n:]:
                self.hits.append((-3 - k, c))
            items.append(describe(-3 - k, geo))
        # the ends, middles, centres and quadrants of the sketch's curves and of the
        # projected ones (Fusion: projected geometry snaps like sketch geometry)
        self.items = [item for item in items if item is not None]
        self.snaps = icore.snap_points(self.items)
        self.verts = verts
        self.curves = curves
        self.lines = lines
        self.keyed = dict(verts)
        self.sketch = sketch

    def curve_at(self, raw, tol, kinds=None, own=False):
        """(geo, distance) of the curve nearest to raw within tol, or None. `kinds`:
        TypeIds the curve must have (None: any); `own`: only the sketch's own curves (a
        line lying on an axis is the line, not the axis)."""
        best = None
        for geo, curve in self.hits:
            if own and geo < 0:
                continue
            if kinds is not None and _type_of(self.sketch, geo) not in kinds:
                continue
            if not icore.near_curve(raw, curve, tol):
                continue
            d = icore.curve_distance(raw, curve)
            if best is None or d < best[1]:
                best = (geo, d)
        return best


def _type_of(sketch, geo):
    try:
        if geo >= 0:
            return sketch.Geometry[geo].TypeId
        return list(sketch.ExternalGeo)[-geo - 1].TypeId
    except Exception:
        return ""


def project_on(sketch, geo, raw):
    """The point of curve `geo` nearest to raw (sketch coordinates)."""
    if geo in (-1, -2):
        return (raw[0], 0.0) if geo == -1 else (0.0, raw[1])
    try:
        from .sketch_build import geometry

        g = geometry(sketch, geo)
        t = g.parameter(_v(raw))
        p = g.value(t)
        return (p.x, p.y)
    except Exception:
        return raw


def snap_pixels(ratio=1.0):
    """How close (screen pixels) the pointer must be to a snap point (sketch_infer)."""
    from . import sketch_infer

    return sketch_infer.snap_pixels(ratio)


def pick_pixels():
    try:
        return max(
            5.0,
            float(
                App.ParamGet("User parameter:BaseApp/Preferences/View").GetFloat("PickRadius", 5.0)
            ),
        )
    except Exception:
        return 5.0


# -- the preview ----------------------------------------------------------------------------
# (part, colour, line width, dash pattern): the shape being drawn (the colour of new
# curves), its construction parts, picked curves (a constraint's or a circle's lines),
# the piece Trim removes (red, as Fusion shows it), guides and marks.
PARTS = (
    ("curves", "BLUE", 2.0, None),
    ("construction", "ORANGE", 1.5, 0xF0F0),
    ("picked", "#ffd43b", 3.0, None),
    ("remove", "#ff5c5c", 3.0, None),
    ("guides", "GUIDE", 1.5, 0xF0F0),
    ("marks", "GUIDE", 2.0, None),
)
PART_NAMES = tuple(p[0] for p in PARTS)


class Preview:
    """The shape being drawn and its hints, drawn over the sketch (Coin nodes of our own
    under the view's root, never FreeCAD's edit nodes): solid curves in the colour of new
    curves (orange while new curves are construction), dashed construction parts, the
    picked curves of a pick step, dashed guides, marks and handle points."""

    def __init__(self, session):
        from pivy import coin

        from . import sketch_infer, sketch_mode

        self.session = session
        self.attached = False
        self.root = coin.SoAnnotation()
        self.root.setName("SciForgeSketchTool")
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.transform = coin.SoTransform()
        self.root.addChild(self.transform)
        self.parts = {}
        for name, colour, width, pattern in PARTS:
            colour = {"BLUE": sketch_mode.BLUE, "ORANGE": sketch_mode.ORANGE}.get(colour, colour)
            if colour == "GUIDE":
                colour = sketch_infer.GUIDE_COLOR
            sep = coin.SoSeparator()
            col = coin.SoBaseColor()
            col.rgb.setValue(*_rgb(colour))
            style = coin.SoDrawStyle()
            style.lineWidth = width
            if pattern:
                style.linePattern.setValue(pattern)
            coords = coin.SoCoordinate3()
            lines = coin.SoLineSet()
            for node in (col, style, coords, lines):
                sep.addChild(node)
            self.root.addChild(sep)
            self.parts[name] = (col, coords, lines)
        sep = coin.SoSeparator()
        col = coin.SoBaseColor()
        col.rgb.setValue(*_rgb(sketch_infer.GUIDE_COLOR))
        style = coin.SoDrawStyle()
        style.pointSize = 7.0
        self.point_coords = coin.SoCoordinate3()
        self.point_set = coin.SoPointSet()
        for node in (col, style, self.point_coords, self.point_set):
            sep.addChild(node)
        self.root.addChild(sep)
        self._drawn = {}
        self.clear()

    def _attach(self):
        if self.attached:
            return
        self.session.view.getSceneGraph().addChild(self.root)
        self.attached = True

    def show(
        self, curves=(), construction=(), picked=(), guides=(), marks=(), points=(), remove=()
    ):
        """Polylines (lists of (x, y) sketch points) for each part; points: (x, y)."""
        from . import sketch_mode

        placement = self.session.sketch.getGlobalPlacement()
        self.transform.translation.setValue(*placement.Base)
        self.transform.rotation.setValue(*placement.Rotation.Q)
        colour = sketch_mode.ORANGE if sketch_mode.construction_mode() else sketch_mode.BLUE
        self.parts["curves"][0].rgb.setValue(*_rgb(colour))
        given = {
            "curves": curves,
            "construction": construction,
            "picked": picked,
            "remove": remove,
            "guides": guides,
            "marks": marks,
        }
        drawn = {name: [list(c) for c in given[name]] for name in PART_NAMES}
        drawn["points"] = list(points)
        for name in PART_NAMES:
            _col, coords, lines = self.parts[name]
            _set(coords, lines, drawn[name])
        self.point_coords.point.setNum(0)
        if drawn["points"]:
            pts = [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in drawn["points"]]
            self.point_coords.point.setValues(0, len(pts), pts)
        self._drawn = drawn
        self._attach()

    def clear(self):
        for name in PART_NAMES:
            _col, coords, lines = self.parts[name]
            _set(coords, lines, [])
        self.point_coords.point.setNum(0)
        self._drawn = {}

    def drawn(self):
        return {key: list(value) for key, value in self._drawn.items()}

    def remove(self):
        try:
            if self.attached:
                self.session.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass
        self.attached = False


def _set(coords, lineset, polylines):
    points, counts = [], []
    for poly in polylines:
        if len(poly) < 2:
            continue
        points += [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in poly]  # (3D Sketch)
        counts.append(len(poly))
    coords.point.setNum(0)
    lineset.numVertices.setNum(0)
    if points:
        coords.point.setValues(0, len(points), points)
        lineset.numVertices.setValues(0, len(counts), counts)


def circle_points(centre, radius, n=64):
    return [
        (
            centre[0] + radius * math.cos(2 * math.pi * i / n),
            centre[1] + radius * math.sin(2 * math.pi * i / n),
        )
        for i in range(n + 1)
    ]


def arc_points(centre, radius, a1, a2, n=48):
    step = (a2 - a1) / n
    return [
        (centre[0] + radius * math.cos(a1 + i * step), centre[1] + radius * math.sin(a1 + i * step))
        for i in range(n + 1)
    ]


def curve_points(sketch, geo, n=48):
    """A polyline along a sketch curve (for showing it picked)."""
    try:
        from .sketch_build import geometry

        if geo in (-1, -2):
            return []
        g = geometry(sketch, geo)
        if g.TypeId == "Part::GeomLineSegment":
            return [_xy(g.StartPoint), _xy(g.EndPoint)]
        return [_xy(p) for p in g.discretize(n)]
    except Exception:
        return []


# -- value boxes --------------------------------------------------------------------------
LENGTH, ANGLE, COUNT, RATIO = "length", "angle", "count", "ratio"


class Field:
    """One value a tool asks for while drawing (Fusion's value box)."""

    def __init__(self, name, kind, label="", low=None, high=None):
        self.name = name
        self.kind = kind
        self.label = label
        self.low = low
        self.high = high
        self.value = None  # what the pointer gives now (mm, radians, count, ratio)
        self.typed = None  # the value typed and taken (holds until the shape is made)
        self.anchor = None  # sketch point the box sits beside

    def shown(self):
        value = self.typed if self.typed is not None else self.value
        if value is None:
            return ""
        if self.kind == LENGTH:
            return "%s mm" % _num(value)
        if self.kind == ANGLE:
            return "%s deg" % _num(math.degrees(value))
        if self.kind == COUNT:
            return "%d" % int(value)
        return _num(value, 3)

    def parse(self, text):
        """The value typed (mm, radians, count or ratio); ValueError with the reason."""
        text = text.strip()
        if not text:
            raise ValueError("Type a value.")
        if self.kind in (COUNT, RATIO):
            try:
                value = float(text.replace(",", "."))
            except ValueError:
                raise ValueError("Not a number: %s" % text)
            if self.kind == COUNT:
                value = int(round(value))
        else:
            try:
                q = App.Units.Quantity(text)
            except Exception:
                raise ValueError("Not a value: %s" % text)
            unit = "deg" if self.kind == ANGLE else "mm"
            if q.Unit == App.Units.Quantity(1.0).Unit:
                q = App.Units.Quantity("%r %s" % (q.Value, unit))
            if q.Unit != App.Units.Quantity("1 %s" % unit).Unit:
                raise ValueError(
                    "Type %s" % ("an angle, e.g. 30" if self.kind == ANGLE else "a length, e.g. 25")
                )
            value = q.getValueAs(unit).Value
            if self.kind == ANGLE:
                value = math.radians(value)
        if self.kind == LENGTH and value <= 1e-7:
            raise ValueError("The value must be more than 0.")
        if self.low is not None and value < self.low:
            raise ValueError("The value must be at least %s." % _num(self.low))
        if self.high is not None and value > self.high:
            raise ValueError("The value must be at most %s." % _num(self.high))
        return value


def _num(value, digits=2):
    text = ("%." + str(digits) + "f") % value
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text if text not in ("-0", "") else "0"


BOX_STYLE = (
    "QLineEdit { background: #f5f5f5; color: #111111; border: 1px solid #9aa4b1;"
    " border-radius: 2px; padding: 1px 4px; }"
    ' QLineEdit[current="true"] { border: 2px solid #3fa9f5; background: #ffffff; }'
    ' QLineEdit[typed="true"] { font-weight: bold; }'
    ' QLineEdit[bad="true"] { border: 2px solid #d9480f; }'
)
BOX_NAME = "SciForgeSketchValue"


class Boxes:
    """The value boxes of the step being drawn. They never take the keyboard: keys
    typed on the 3D view come here (DrawTool.key)."""

    def __init__(self, tool):
        self.tool = tool
        self.fields = []
        self.current = 0
        self.typing = None  # text being typed into the current box (None: not typing)
        self.widgets = {}

    def set_fields(self, fields):
        """The boxes of a new step (the old ones go)."""
        self.discard()
        self.fields = list(fields)
        self.current = 0
        self.typing = None
        gl = self.tool.session.gl
        for field in self.fields:
            box = QtWidgets.QLineEdit(gl)
            box.setObjectName(BOX_NAME)
            box.setFocusPolicy(QtCore.Qt.NoFocus)
            box.setReadOnly(True)
            # the pointer passes over a box to the view (the drawing goes on under it)
            box.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            box.setStyleSheet(BOX_STYLE)
            box.setProperty("field", field.name)
            box.hide()
            self.widgets[field.name] = box

    def field(self, name):
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def typed(self, name):
        f = self.field(name)
        return f.typed if f is not None else None

    def refresh(self):
        """Put each box beside its anchor with its value (called after every move)."""
        session = self.tool.session
        gl = session.gl
        if gl is None:
            return
        placement = session.sketch.getGlobalPlacement()
        ratio = gl.devicePixelRatioF() or 1.0
        for i, field in enumerate(self.fields):
            box = self.widgets.get(field.name)
            if box is None:
                continue
            if field.anchor is None or (
                field.value is None and field.typed is None and self.typing is None
            ):
                box.hide()
                continue
            text = field.label + " " if field.label else ""
            if i == self.current and self.typing is not None:
                text += self.typing
            else:
                text += field.shown()
            if box.text() != text:
                box.setText(text)
            for prop, value in (
                ("current", i == self.current),
                ("typed", field.typed is not None),
            ):
                if bool(box.property(prop)) != value:
                    box.setProperty(prop, value)
                    box.style().unpolish(box)
                    box.style().polish(box)
            width = box.fontMetrics().horizontalAdvance(text + "00") + 14
            if box.width() != max(64, width):
                box.setFixedWidth(max(64, width))
            try:
                x, y = session.view.getPointOnViewport(placement.multVec(_v(field.anchor)))
            except Exception:
                box.hide()
                continue
            px, py = int(x / ratio) + 14, int(gl.height() - y / ratio) + 10 + 26 * i
            px = max(2, min(px, gl.width() - box.width() - 2))
            py = max(2, min(py, gl.height() - box.height() - 2))
            box.move(px, py)
            if not box.isVisible():
                box.show()
                box.raise_()

    def key(self, event):
        """A key for the boxes; True when it was used."""
        if not self.fields:
            return False
        key = event.key()
        text = event.text()
        mods = event.modifiers() & ~(QtCore.Qt.KeypadModifier | QtCore.Qt.ShiftModifier)
        if mods != QtCore.Qt.NoModifier:
            return False
        if key == QtCore.Qt.Key_Tab or key == QtCore.Qt.Key_Backtab:
            if self.typing is not None and not self.take():
                return True
            step = -1 if key == QtCore.Qt.Key_Backtab else 1
            self.current = (self.current + step) % len(self.fields)
            self.refresh()
            return True
        if key == QtCore.Qt.Key_Backspace:
            if self.typing is not None:
                self.typing = self.typing[:-1]
                self.refresh()
            return True
        value_char = text and (text.isdigit() or text in ".,-+*/()")
        unit_char = text and text.isalpha() and self.typing
        if value_char or unit_char or (text == " " and self.typing):
            if self.typing is None:
                self.typing = ""
            self.typing += text
            self._bad(False)
            self.refresh()
            return True
        return False

    def take(self):
        """Take what was typed into the current box. False (box marked) when it is not a
        value for that box."""
        if self.typing is None:
            return True
        field = self.fields[self.current]
        try:
            value = field.parse(self.typing)
        except ValueError as exc:
            self._bad(True)
            self.tool.say(str(exc))
            return False
        field.typed = value
        self.typing = None
        self._bad(False)
        self.refresh()
        return True

    def _bad(self, on):
        try:
            box = self.widgets.get(self.fields[self.current].name)
            if box is not None and bool(box.property("bad")) != on:
                box.setProperty("bad", on)
                box.style().unpolish(box)
                box.style().polish(box)
        except Exception:
            pass

    def busy(self):
        """Something is typed or taken in this step."""
        return self.typing is not None or any(f.typed is not None for f in self.fields)

    def discard(self):
        for box in self.widgets.values():
            try:
                box.hide()
                box.setParent(None)
                box.deleteLater()
            except Exception:
                pass
        self.widgets = {}
        self.fields = []
        self.typing = None


def remove_stray_boxes(gl):
    """Value boxes and hints of an earlier tool left on the 3D view (they are children
    of it)."""
    try:
        for box in gl.findChildren(QtWidgets.QLineEdit, BOX_NAME):
            box.hide()
            box.deleteLater()
        for label in gl.findChildren(QtWidgets.QLabel, HINT_NAME):
            label.hide()
            label.deleteLater()
    except Exception:
        pass


HINT_NAME = "SciForgeSketchHint"
HINT_STYLE = (
    "QLabel { background: rgba(32, 36, 44, 220); color: #f0f0f0; border: 1px solid #56606f;"
    " border-radius: 2px; padding: 2px 6px; }"
    ' QLabel[warning="true"] { color: #ffb86b; }'
)


class Hint(QtWidgets.QLabel):
    """What the tool wants next, beside the pointer (Fusion shows its prompts there).
    A child of the 3D view that lets the mouse through, so it never blocks the drawing
    (a tooltip under the pointer took the mouse moves). A refusal shows for a moment in
    orange, then the prompt again."""

    def __init__(self, gl):
        super().__init__(gl)
        self.setObjectName(HINT_NAME)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(HINT_STYLE)
        self.prompt = ""
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._back)
        self.hide()

    def set_prompt(self, text):
        self.prompt = text
        if not self._timer.isActive():
            self._show(text, False)

    def warn_text(self, text):
        self._show(text, True)
        self._timer.start(2500)

    def _back(self):
        try:
            self._show(self.prompt, False)
        except Exception:
            pass

    def _show(self, text, warning):
        self.setText(text)
        if bool(self.property("warning")) != warning:
            self.setProperty("warning", warning)
            self.style().unpolish(self)
            self.style().polish(self)
        self.adjustSize()
        self.follow()
        if text and not self.isVisible():
            self.show()
            self.raise_()

    def follow(self, pos=None):
        """Sit just above the pointer (the value boxes are below their points), to its
        right, or to its left in the right part of the view (FreeCAD's panels float over
        the view's right side)."""
        parent = self.parentWidget()
        if parent is None:
            return
        if pos is None:
            pos = parent.mapFromGlobal(QtGui.QCursor.pos())
        px, py = int(pos.x()), int(pos.y())
        right = self._right_limit(parent)
        if px + 18 + self.width() > right:
            x = px - self.width() - 18
        else:
            x = px + 18
        y = py - self.height() - 18
        x = max(2, min(x, right - self.width() - 2))
        y = max(2, min(y, parent.height() - self.height() - 2))
        if self.pos() != QtCore.QPoint(x, y):
            self.move(x, y)

    @staticmethod
    def _right_limit(parent):
        """Where the view stops being visible on the right: the left edge of FreeCAD's
        panel floating over it (the sketch palette's), else the view's own edge."""
        limit = parent.width()
        try:
            main = Gui.getMainWindow()
            panel = main.findChild(QtWidgets.QFrame, "SciForgeSketchPalette")
            if panel is not None and panel.isVisible():
                left = parent.mapFromGlobal(panel.mapToGlobal(QtCore.QPoint(0, 0))).x()
                if 0 < left < limit:
                    limit = left
        except Exception:
            pass
        return limit

    def discard(self):
        try:
            self._timer.stop()
            self.hide()
            self.setParent(None)
            self.deleteLater()
        except RuntimeError:
            pass


# -- the tool ------------------------------------------------------------------------------
class DrawTool:
    """Base of SciForge's own sketch tools. A subclass sets `title` and implements
    prompt(), fields(), moved(snap) / clicked(snap) and, for drawing tools, build()."""

    title = ""
    command = ""
    repeat = True  # Fusion: the tool stays on for the next shape
    direction_steps = ()  # steps whose point is the end of a direction from the last point
    pick_steps = ()  # steps that pick a curve (no point snapping)

    def __init__(self, session):
        self.session = session
        self.sketch = session.sketch
        self.doc = session.doc
        self.active = False
        self.step = 0
        self.snaps = []  # the Snap of each click of the shape being drawn
        self.picks = []  # curves picked (pick steps)
        self.last = None  # Snap at the last move
        self.boxes = Boxes(self)
        self.preview = Preview(session)
        self.acquired = []  # hovered sketch points (guides), newest last
        self._geometry = None
        self._pressed = None
        self.press_pos = None  # widget position of the last left press
        self.drag_pixels = 0  # how far the pointer went since the press (pixels)
        self._busy = False
        self._applying = False
        self.hint = None  # the prompt beside the pointer (Hint)

    # -- life cycle --------------------------------------------------------------------------
    def start(self):
        session = self.session
        old = getattr(session, "tool", None)
        if old is not None and old is not self:
            old.stop()
        session.tool = self
        self.active = True
        self._enter_step(0)
        gl = session.gl
        if gl is not None:
            remove_stray_boxes(gl)
            try:
                self.hint = Hint(gl)
            except Exception as exc:
                warn("%s: %s" % (self.title, exc))
        self._set_cursor()
        try:
            if session.viewer is not None:
                session.viewer.setFocus()
        except Exception:
            pass
        self._tell()
        log("%s: %s" % (self.title, self.prompt()))

    def _cursor_widget(self):
        """The widget FreeCAD's tools put their cursor on (the 3D viewer; its drawing
        area inherits it, and SketchSession.tool_running reads it there)."""
        session = self.session
        return session.viewer if session.viewer is not None else session.gl

    def _set_cursor(self):
        widget = self._cursor_widget()
        try:
            if widget is not None and widget.cursor().shape() != CROSS:
                widget.setCursor(QtGui.QCursor(CROSS))
        except Exception:
            pass

    def _taken_over(self):
        """A FreeCAD tool started while this one ran (L, C, D... go straight to FreeCAD's
        tools): its own picture cursor is on the view. (Panning and orbiting show
        FreeCAD's picture cursors too, but only while a mouse button is held.)"""
        widget = self._cursor_widget()
        try:
            if QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton:
                return False
            return widget is not None and widget.cursor().shape() == QtCore.Qt.BitmapCursor
        except Exception:
            return False

    def _take_keys(self):
        """The pointer is over the 3D view: typed values go to the tool's boxes, as with
        FreeCAD's tools (they give their value field the keyboard). Never taken from a
        field the user is typing in."""
        viewer = self.session.viewer
        try:
            focus = QtWidgets.QApplication.focusWidget()
            if viewer is None or focus is viewer:
                return
            if isinstance(
                focus, (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox, QtWidgets.QTextEdit)
            ):
                return
            viewer.setFocus()
        except Exception:
            pass

    def stop(self):
        """End the tool (Esc, OK, another tool, the sketch closing)."""
        if not self.active:
            return
        self.active = False
        session = self.session
        if getattr(session, "tool", None) is self:
            session.tool = None
        self.boxes.discard()
        self.preview.clear()
        self.preview.remove()
        if self.hint is not None:
            self.hint.discard()
            self.hint = None
        widget = self._cursor_widget()
        try:
            from .sketch_mode import _is_valid

            if widget is not None and _is_valid(widget) and widget.cursor().shape() == CROSS:
                widget.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        except Exception:
            pass
        log("%s: ended" % self.title)

    def finish(self):
        """OK / Enter with nothing typed: what can be kept is made, then the tool ends."""
        try:
            self.on_finish()
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
        self.stop()

    def on_finish(self):
        """A tool whose last step only adjusts a value (the conic's rho) makes the shape."""

    def changed(self):
        """The sketch changed (a commit, undo...): snapping lists are rebuilt."""
        self._geometry = None

    def undone(self):
        """Undo / redo while the tool runs: the half-drawn shape may refer to curves that
        are gone; it starts afresh."""
        self._geometry = None
        if self.step:
            self._enter_step(0)
            self.preview.clear()

    # -- steps ---------------------------------------------------------------------------------
    def _enter_step(self, step):
        self.step = step
        if step == 0:
            self.snaps = []
            self.picks = []
        self.boxes.set_fields(self.fields())

    def next_step(self):
        """The click of this step is done: on to the next one (or make the shape)."""
        if self.step + 1 >= self.steps():
            self.make()
            return
        self._enter_step(self.step + 1)
        self._tell()

    def steps(self):
        return 2

    def prompt(self):
        return "click"

    def fields(self):
        return []

    def _tell(self):
        """Show what the tool wants next beside the pointer."""
        try:
            if self.hint is not None:
                self.hint.set_prompt("%s: %s" % (self.title, self.prompt()))
        except Exception:
            pass

    def say(self, text):
        """A refusal or note beside the pointer for a moment (and in the log)."""
        text = text if text.startswith(self.title) else "%s: %s" % (self.title, text)
        log(text)
        try:
            if self.hint is not None:
                self.hint.warn_text(text)
            else:
                from . import commands

                commands.tell(text)
        except Exception:
            pass

    def hint_text(self):
        """The text beside the pointer now (tests)."""
        try:
            return self.hint.text() if self.hint is not None and self.hint.isVisible() else ""
        except RuntimeError:
            return ""

    # -- the mouse ---------------------------------------------------------------------------
    def mouse(self, obj, event):
        """True when the event is the tool's (the caller swallows it)."""
        if not self.active or self._busy:
            return False
        try:
            return self._mouse(obj, event)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
            return False

    def _mouse(self, obj, event):
        session = self.session
        gl = session.gl
        if session.closed or gl is None:
            self.stop()
            return False
        kind = event.type()
        if kind == QtCore.QEvent.MouseMove:
            buttons = event.buttons()
            if buttons not in (QtCore.Qt.NoButton, QtCore.Qt.LeftButton):
                return False  # panning / orbiting (FreeCAD shows its own cursor meanwhile)
            if buttons == QtCore.Qt.NoButton and self._taken_over():
                # a FreeCAD tool started meanwhile (its own cursor): it has the view now
                self.stop()
                return False
            self._set_cursor()  # FreeCAD puts its idle cursor back after a pan or orbit
            self._take_keys()
            if self.hint is not None:
                self.hint.follow(event.position())
            view = self._view(obj, event)
            if view is None:
                return False
            snap = self.snap_for(view, event)
            self.last = snap
            if buttons == QtCore.Qt.LeftButton and self._pressed is not None:
                self.drag_pixels = (event.position() - self._pressed[0]).manhattanLength()
                self.dragged(snap, view)
                return True
            self.moved(snap)
            self.boxes.refresh()
            return False  # FreeCAD lights up what is under the pointer
        if kind in PRESSES:
            if event.button() != QtCore.Qt.LeftButton:
                return False
            view = self._view(obj, event)
            self.press_pos = event.position()
            if view is None:
                return True
            snap = self.snap_for(view, event)
            self.last = snap
            self._pressed = (event.position(), snap)
            self.drag_pixels = 0
            self.pressed(snap, view)
            return True
        if kind == QtCore.QEvent.MouseButtonRelease:
            if event.button() != QtCore.Qt.LeftButton:
                return False
            pressed, self._pressed = self._pressed, None
            if pressed is None:
                return True
            view = self._view(obj, event)
            snap = self.snap_for(view, event) if view is not None else pressed[1]
            moved = (event.position() - pressed[0]).manhattanLength() if view is not None else 0
            self.released(pressed[1], snap, moved)
            return True
        return False

    def pressed(self, snap, view):
        """A left press (the click happens at the release, as in FreeCAD's tools)."""

    def dragged(self, snap, view):
        """The pointer moved with the button held (Trim's drag)."""
        self.moved(snap)
        self.boxes.refresh()

    def released(self, press_snap, snap, moved):
        """The click: the press's snap is where it happened."""
        self._click(press_snap)

    def _click(self, snap):
        """One click of the shape (Enter makes one too, at the pointer)."""
        if self.step in self.pick_steps:
            self.pick(snap)
            return
        if not self.boxes.take():
            return
        snap = self.adjust(snap) or snap
        if not self.accept(snap):
            return
        self.snaps.append(snap)
        if snap.key is not None and snap.key not in self.acquired:
            self.acquired.append(snap.key)
        self.next_step()

    def accept(self, snap):
        """False when a click cannot be taken (the shape would have no size)."""
        return True

    def adjust(self, snap):
        """The snap with the typed values applied (a typed length moves the point)."""
        return snap

    def pick(self, snap):
        """A click in a pick step (a curve to work on)."""

    def use_selection(self, selection):
        """What was selected when the tool started ([(geo, pos)], pos 0 for a curve): a
        tool that picks curves first can take them (Fusion takes a selection made before
        the command)."""

    def moved(self, snap):
        """The pointer moved: update the preview and the boxes' values."""

    # -- where the pointer goes -----------------------------------------------------------
    def _view(self, obj, event):
        from .sketch_infer import _ViewMap

        view = _ViewMap(self.session, obj, event.position())
        return view if view.ok else None

    def geometry(self):
        if self._geometry is None:
            self._geometry = Geometry(self.sketch)
        return self._geometry

    def start_point(self):
        """The point a direction step starts from (the last click), or None."""
        if self.step in self.direction_steps and self.snaps:
            return self.snaps[-1].point
        return None

    def snap_for(self, view, event):
        ctrl = bool(event.modifiers() & QtCore.Qt.ControlModifier)
        self._ratio = view.ratio
        return self.snap(view.raw, view.px, ctrl, self.start_point())

    def snap(self, raw, px, ctrl=False, start=None):
        """Where a point at `raw` goes (Snap)."""
        from . import sketch_infer

        if ctrl and sketch_infer.setting("CtrlFree"):
            return Snap(raw, raw, free=True)
        geo = self.geometry()
        pick = pick_pixels() * px
        hit = self.snap_point(raw, px)
        if hit is not None:
            if hit.kind in icore.VERTEX_KINDS:
                self._acquire(hit.key)
                return Snap(hit.point, raw, key=hit.key, target=hit)
            if hit.kind == icore.MIDDLE and _type_of(self.sketch, hit.geo) == LINE_TYPE:
                return Snap(hit.point, raw, mid_of=hit.geo, target=hit)
            return Snap(hit.point, raw, curve=hit.geo, curve2=hit.other, target=hit)
        opt = icore.Options(
            guide_px=sketch_infer.setting("GuidePixels"),
            pick_px=pick_pixels(),
            hv_deg=sketch_infer.setting("HVDegrees"),
            perp_deg=sketch_infer.setting("PerpendicularDegrees"),
            diag_deg=sketch_infer.setting("DiagonalDegrees"),
            parallel=False,
            grid=sketch_infer._grid_size(self.session),
        )
        enabled = sketch_infer.setting("Enabled")
        on_curve = geo.curve_at(raw, pick)
        if on_curve is not None:
            if start is not None and enabled:
                result = icore._ends_on_line(raw, start, geo.lines, pick, px, opt)
                if result is not None:
                    result.start = start
                    return Snap(result.point, raw, curve=on_curve[0], result=result)
            return Snap(project_on(self.sketch, on_curve[0], raw), raw, curve=on_curve[0])
        if enabled:
            keys = [k for k in self.acquired if k in geo.keyed]
            anchors = [s.point for s in self.snaps]
            acquired = [(k, geo.keyed[k]) for k in keys]
            result = icore.infer(raw, start, acquired, geo.lines, [], [], px, opt, (), anchors)
            if result is not None:
                return Snap(result.point, raw, result=result)
        grid = opt.grid
        return Snap((icore.grid_snap(raw[0], grid), icore.grid_snap(raw[1], grid)), raw)

    def snap_point(self, raw, px):
        """The end, middle, centre, quadrant or crossing (sketch or projected curves) the
        pointer is on, within the snap radius (sketch_infer_core.SnapPoint), or None."""
        geo = self.geometry()
        tol = snap_pixels(getattr(self, "_ratio", 1.0)) * px
        points = geo.snaps + icore.crossings(raw, geo.items, tol)
        return icore.nearest_snap(raw, points, tol)

    def _acquire(self, key):
        """Hovering a point acquires it for guides (Fusion keeps the last 3)."""
        from . import sketch_infer

        keep = max(0, int(sketch_infer.setting("MaxHovered")))
        self.acquired = icore.remember(self.acquired, key, keep + len(self.snaps))

    # -- keys ------------------------------------------------------------------------------
    def key(self, obj, event):
        """A key on the 3D view while the tool runs; True when it was the tool's."""
        if not self.active:
            return False
        try:
            if isinstance(obj, QtWidgets.QAbstractSpinBox):
                return False  # FreeCAD's own value fields are its tools'
            if self._taken_over():
                self.stop()
                return False
            kind = event.type()
            if kind == QtCore.QEvent.ShortcutOverride:
                if self._wants_key(event):
                    event.accept()
                    return True
                return False
            if kind != QtCore.QEvent.KeyPress:
                return False
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                if event.isAutoRepeat():
                    return True
                return self.enter()
            if self.extra_key(event):
                return True
            return self.boxes.key(event)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
            return False

    def _wants_key(self, event):
        key = event.key()
        if key in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab, QtCore.Qt.Key_Backspace):
            return bool(self.boxes.fields)
        text = event.text()
        mods = event.modifiers() & ~(QtCore.Qt.KeypadModifier | QtCore.Qt.ShiftModifier)
        if mods != QtCore.Qt.NoModifier or not text:
            return False
        if text.isdigit() or text in ".,-+*/()":
            return bool(self.boxes.fields)
        if text.isalpha() and self.boxes.typing:
            return True  # a unit after a typed value ("12 mm")
        return self.wants_letter(text)

    def wants_letter(self, text):
        return False

    def extra_key(self, event):
        """Keys of the tool itself (the polygon's U / J)."""
        return False

    def enter(self):
        """Enter: take the typed values and place the point at the pointer (Fusion);
        with nothing typed in this step it completes the tool (returns False: the
        sketch's Enter handling ends it)."""
        if not self.boxes.busy():
            return self.enter_without_values()
        if not self.boxes.take():
            return True
        snap = self.last
        if snap is None:
            return True
        self._click(snap)
        return True

    def enter_without_values(self):
        return False

    # -- making the shape ---------------------------------------------------------------------
    def make(self):
        """All clicks are in: add the shape (one undo step), then wait for the next one."""
        construction = False
        try:
            from . import sketch_mode

            construction = sketch_mode.construction_mode()
        except Exception:
            pass
        doc = self.doc
        sketch = self.sketch
        self._applying = True
        doc.openTransaction(self.title)
        try:
            first = len(sketch.Constraints)
            ours = self.build(construction) or []
            kept = self._add_checked(ours)
            sketch.solve()
        except Exception as exc:
            doc.abortTransaction()
            self._applying = False
            try:
                sketch.solve()
            except Exception:
                pass
            warn("%s: could not add the shape: %s" % (self.title, exc))
            self._enter_step(0)
            self.preview.clear()
            return
        doc.commitTransaction()
        self._applying = False
        log(
            "%s: added (%s)"
            % (
                self.title,
                ", ".join(c.Type for c in sketch.Constraints[first:]) or "no constraints",
            )
        )
        self.after_make(kept)
        self._geometry = None
        self.preview.clear()
        if self.repeat:
            self._enter_step(0)
            self._tell()
        else:
            self.stop()

    def build(self, construction):
        """Add the geometry (and the constraints that make the shape); return the extra
        constraints (snaps, dimensions) to add if they fit (_add_checked)."""
        return []

    def after_make(self, kept):
        pass

    def _add_checked(self, constraints):
        """Add constraints; those that turn out redundant or conflicting are dropped (a
        snap that repeats what the shape already says). Returns the ones kept."""
        sketch = self.sketch
        constraints = [c for c in constraints if c is not None]
        if not constraints:
            return []
        first = len(sketch.Constraints)
        sketch.addConstraint(constraints)
        sketch.solve()
        bad = set(sketch.RedundantConstraints) | set(sketch.ConflictingConstraints)
        drop = [i for i in range(first, len(sketch.Constraints)) if i + 1 in bad]
        for i in reversed(drop):
            sketch.delConstraint(i)
        if drop:
            sketch.solve()
        return list(sketch.Constraints[first:])

    # -- constraints for a placed point -----------------------------------------------------
    def snap_constraints(self, anchor, snap, line=None):
        """The constraints that tie the new point `anchor` (geo, pos) to what its click
        snapped to; `line` is the new line that runs along the snap's direction (level,
        upright, perpendicular)."""
        import Sketcher

        if snap is None or snap.free or anchor is None:
            return []
        geo, pos = anchor
        out = []
        if snap.key is not None:
            out.append(Sketcher.Constraint("Coincident", geo, pos, snap.key[0], snap.key[1]))
        elif snap.mid_of is not None:
            out.append(Sketcher.Constraint("Symmetric", snap.mid_of, 1, snap.mid_of, 2, geo, pos))
        elif snap.curve is not None:
            out.append(Sketcher.Constraint("PointOnObject", geo, pos, snap.curve))
            if snap.curve2 is not None:
                out.append(Sketcher.Constraint("PointOnObject", geo, pos, snap.curve2))
        result = snap.result
        if result is not None:
            from . import sketch_infer

            if sketch_infer.setting("GuideConstraint"):
                for guide in result.guides:
                    name = "Vertical" if guide.axis == icore.SAME_X else "Horizontal"
                    out.append(Sketcher.Constraint(name, geo, pos, guide.key[0], guide.key[1]))
            if line is not None:
                if result.kind == icore.HORIZONTAL:
                    out.append(Sketcher.Constraint("Horizontal", line))
                elif result.kind == icore.VERTICAL:
                    out.append(Sketcher.Constraint("Vertical", line))
                elif result.kind == icore.PERPENDICULAR and result.other is not None:
                    out.append(Sketcher.Constraint("Perpendicular", line, result.other))
                elif result.kind == icore.DIAGONAL:
                    try:
                        geo = self.sketch.Geometry[line]
                        out.append(sketch_infer.diagonal_constraint(geo, line))
                    except Exception:
                        pass
        return out

    # -- shared preview hints ----------------------------------------------------------------
    def hint_marks(self, snap):
        """(guides, marks, points) the snap shows: dashed guides, the level / upright
        mark, a dot where the point lands on something."""
        guides, marks, points = [], [], []
        if snap is None:
            return guides, marks, points
        px = 0.25
        try:
            px = self._px()
        except Exception:
            pass
        result = snap.result
        if result is not None:
            guides = [(g.anchor, result.point) for g in result.guides]
            if result.start is not None:
                if result.kind == icore.HORIZONTAL:
                    marks += icore.level_mark(result.start, result.point, 6 * px)
                elif result.kind == icore.VERTICAL:
                    marks += icore.upright_mark(result.start, result.point, 6 * px)
                elif result.kind == icore.PERPENDICULAR and result.corner and result.along:
                    d = result.direction
                    u = d if not result.on_line else (-d[0], -d[1])
                    marks.append(icore.right_angle_mark(result.corner, u, result.along, 10 * px))
                elif result.kind == icore.DIAGONAL:
                    marks += icore.diagonal_mark(result.start, result.point, 6 * px)
        if snap.target is not None:
            # what the point sits on, as in FreeCAD's tools (sketch_infer.Overlay)
            marks += icore.snap_mark(snap.target, 6 * px)
        elif snap.key is not None or snap.mid_of is not None or snap.curve is not None:
            points.append(snap.point)
        return guides, marks, points

    def _px(self):
        """mm per screen pixel near the sketch (for mark sizes)."""
        view = self.session.view
        gl = self.session.gl
        a = view.getPointOnViewport(self.sketch.getGlobalPlacement().multVec(App.Vector(0, 0, 0)))
        b = view.getPointOnViewport(self.sketch.getGlobalPlacement().multVec(App.Vector(10, 0, 0)))
        ratio = gl.devicePixelRatioF() or 1.0
        d = math.hypot(a[0] - b[0], a[1] - b[1]) / ratio
        return 10.0 / d if d > 1e-9 else 0.25

    # -- for tests and diagnostics ------------------------------------------------------------
    def state(self):
        return {
            "title": self.title,
            "step": self.step,
            "snaps": list(self.snaps),
            "picks": list(self.picks),
            "last": self.last,
            "fields": {f.name: (f.value, f.typed) for f in self.boxes.fields},
            "typing": self.boxes.typing,
            "preview": self.preview.drawn(),
        }


def current_tool():
    """The SciForge tool running in the open sketch, or None."""
    try:
        from . import sketch_mode

        session = sketch_mode.current()
        tool = getattr(session, "tool", None) if session is not None else None
        return tool if tool is not None and tool.active else None
    except Exception:
        return None


def run(tool_class, *args):
    """Start a SciForge tool in the open sketch (the command's job): FreeCAD's running
    tool and SciForge's line chain stop first."""
    from . import commands, sketch_mode

    sketch = sketch_mode.editing_sketch()
    if sketch is None:
        commands.tell(
            "%s works inside a sketch: click Create Sketch (or edit a sketch) first."
            % tool_class.title
        )
        return None
    session = sketch_mode.current()
    if session is None or session.sketch is not sketch:
        commands.tell("%s: the sketch is not ready yet, try again." % tool_class.title)
        return None
    old = getattr(session, "tool", None)
    if old is not None:
        old.stop()
    session.line.stop()
    if session.infer is not None:
        session.infer.reset()
    try:
        from . import sketch_pick_ui, sketch_tools_ui

        sketch_tools_ui.stop_waiting()
        sketch_pick_ui.stop_waiting()
    except Exception:
        pass
    selection = selected_elements(sketch)
    try:
        if session.tool_running():
            spline = session._spline_tool()
            Gui.runCommand("Sketcher_StopOperation")
            if spline:
                session._drop_spline()  # a half-drawn spline goes, as with Esc
    except Exception as exc:
        warn("%s: %s" % (tool_class.title, exc))
    tool = tool_class(session, *args)
    tool.preselected = selection
    tool.start()
    try:
        tool.use_selection(selection)
    except Exception as exc:
        warn("%s: %s" % (tool_class.title, exc))
    return tool


def selected_elements(sketch):
    """What is selected in the open sketch: [(geo, pos)] (pos 0 for a whole curve;
    the axes -1 / -2, the origin (-1, 1), projected curves from -3)."""
    out = []
    try:
        for sel in Gui.Selection.getSelectionEx():
            if sel.Object is not sketch:
                continue
            for name in sel.SubElementNames:
                item = element(sketch, name.rsplit(".", 1)[-1])
                if item is not None and item not in out:
                    out.append(item)
    except Exception:
        pass
    return out


def element(sketch, short):
    """A sketch sub-element name ("Edge3", "Vertex5", "RootPoint", "H_Axis",
    "ExternalEdge2") as (geo, pos), or None."""
    try:
        if short.startswith("Edge"):
            return (int(short[4:]) - 1, 0)
        if short.startswith("ExternalEdge"):
            return (-int(short[12:]) - 2, 0)
        if short.startswith("Vertex"):
            geo, pos = sketch.getGeoVertexIndex(int(short[6:]) - 1)
            return (geo, int(pos))
        if short == "RootPoint":
            return (-1, 1)
        if short == "H_Axis":
            return (-1, 0)
        if short == "V_Axis":
            return (-2, 0)
    except Exception:
        return None
    return None
