# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rectangular Pattern, Circular Pattern and Pattern on Path with Fusion's dialogs
(Mirror, which shares this dialog, is in mirror_ui.py).

How it is used, like in Fusion:
  * Pattern Type: Features (click steps in the timeline, or a face of the part: the step
    that made it is taken), Faces (click every face of a hole or a boss) or Bodies.
    Things selected before the command starts are taken at once.
  * A selection box is blue while it takes the clicks; click a box to make it the one.
    Directions and axes: click an edge, a flat face (its normal), a round face (its axis)
    or one of the origin axes, which are drawn while such a box waits.
  * The copies are previewed live. The blue arrows drag the distances (Rectangular, Pattern
    on Path), the blue curved handle the total angle (Circular, Angle/Symmetric).
  * Values take parameters and formulas. Problems are said in the dialog; OK waits for a
    fix. Esc / Cancel leave the model as it was; the whole pattern is one undo step.
  * Double-click the pattern in the timeline to change it.
Geometry and the FreeCAD features behind each choice: pattern.py.
"""
import math
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, pattern, preview, ui_icon_path, warn
from . import hole_common as common
from . import profile_pick
from .compat import QtCore, QtGui, QtWidgets
from .pattern_core import PatternError, default_distance
from .taskui import ArrowDragger, DistanceField, Panel

PATTERN_TYPES = [
    ("Faces", "faces"),
    ("Bodies", "bodies"),
    ("Features", "features"),
    ("Components", "components"),
]
DISTRIBUTIONS = [("Extent", "extent"), ("Spacing", "spacing")]
DIRECTION_TYPES = [("One Direction", "one"), ("Symmetric", "symmetric")]
CIRCULAR_TYPES = [("Full", "full"), ("Angle", "angle"), ("Symmetric", "symmetric")]
ORIENTATIONS = [("Identical", "identical"), ("Path Direction", "path")]
OPERATIONS = [("Join", "join"), ("New Body", "new_body")]
COMPUTE = [("Identical", "identical"), ("Optimized", "optimized"), ("Adjust", "adjust")]
AXES = ("X_Axis", "Y_Axis", "Z_Axis")
AXIS_COLORS = {
    "X_Axis": (0.92, 0.30, 0.30),
    "Y_Axis": (0.35, 0.80, 0.35),
    "Z_Axis": (0.35, 0.55, 1.00),
}
PICKED = (0.12, 0.53, 0.90)
REF = (1.0, 0.62, 0.15)  # the picked direction / axis, drawn orange over the part
OVERLAY_CLICK_S = 0.6  # a click the axis/plane overlay took: the selection it makes is ignored


def _combo(pairs, current=None, disabled=()):
    box = common.combo(pairs, current)
    model = box.model()
    for i in range(box.count()):
        if box.itemData(i) in disabled and hasattr(model, "item"):
            item = model.item(i)
            item.setEnabled(False)
            item.setToolTip(disabled[box.itemData(i)])
    return box


def _bold(text):
    label = QtWidgets.QLabel("<b>%s</b>" % text)
    return label


def _same_edge(a, b, tol=1e-6):
    if a.Curve.TypeId != b.Curve.TypeId or abs(a.Length - b.Length) > tol * max(1.0, a.Length):
        return False
    pa = sorted((v.Point.x, v.Point.y, v.Point.z) for v in a.Vertexes)
    pb = sorted((v.Point.x, v.Point.y, v.Point.z) for v in b.Vertexes)
    if len(pa) != len(pb):
        return False
    for p, q in zip(pa, pb):
        if (App.Vector(*p) - App.Vector(*q)).Length > 1e-5:
            return False
    return (a.CenterOfMass - b.CenterOfMass).Length < 1e-5


def _local(shape, body):
    copy = shape.copy()
    if body is not None:
        place = body.getGlobalPlacement()
        if not place.isIdentity():
            copy.transformShape(place.inverse().toMatrix())
    return copy


def _global(shape, body):
    copy = shape.copy()
    if body is not None:
        place = body.getGlobalPlacement()
        if not place.isIdentity():
            copy.transformShape(place.toMatrix())
    return copy


def _is_dragging(handle):
    return common.is_dragging(handle)


# -- overlays in the 3D view -------------------------------------------------------------------
class Marks:
    """Picked faces shaded blue and the picked direction/axis drawn orange, over the part.
    Not clickable: clicks go through to the part."""

    def __init__(self, view):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        offset = coin.SoPolygonOffset()
        offset.factor = -1.0
        offset.units = -1.0
        self.root.addChild(offset)
        self.content = coin.SoSeparator()
        self.root.addChild(self.content)
        view.getSceneGraph().addChild(self.root)

    def show(self, faces=(), lines=()):
        coin = self.coin
        self.content.removeAllChildren()
        for face in faces:
            try:
                points, triangles = face.tessellate(0.1)
            except Exception:
                continue
            if not triangles:
                continue
            sep = coin.SoSeparator()
            material = coin.SoMaterial()
            material.diffuseColor.setValue(*PICKED)
            material.emissiveColor.setValue(*[c * 0.5 for c in PICKED])
            material.transparency.setValue(0.3)
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
            index = []
            for a, b, c in triangles:
                index += [a, b, c, -1]
            mesh = coin.SoIndexedFaceSet()
            mesh.coordIndex.setValues(0, len(index), index)
            sep.addChild(material)
            sep.addChild(coords)
            sep.addChild(mesh)
            self.content.addChild(sep)
        for start, end in lines:
            sep = coin.SoSeparator()
            common.on_top(sep)
            material = coin.SoMaterial()
            material.diffuseColor.setValue(*REF)
            material.emissiveColor.setValue(*REF)
            style = coin.SoDrawStyle()
            style.lineWidth = 4
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, 2, [(start.x, start.y, start.z), (end.x, end.y, end.z)])
            line = coin.SoLineSet()
            line.numVertices.setValue(2)
            sep.addChild(material)
            sep.addChild(style)
            sep.addChild(coords)
            sep.addChild(line)
            self.content.addChild(sep)

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


class AxisPicker:
    """The body's origin axes, drawn as long lines while a direction or axis box waits for a
    click (FreeCAD keeps them hidden; Fusion's origin axes can be clicked). The one under the
    mouse lights up; a click picks it: on_pick(axis object)."""

    def __init__(self, view, body, on_pick, size):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.on_pick = on_pick
        self.last_click = 0.0
        self.axes = {}
        place = body.getGlobalPlacement()
        for feature in body.Origin.OriginFeatures:
            role = getattr(feature, "Role", "") or feature.Name
            for key in AXES:
                if role.startswith(key):
                    base, direction = pattern._line_of_datum(feature)
                    start = place.multVec(base - direction * size)
                    end = place.multVec(base + direction * size)
                    self.axes[key] = (feature, start, end)
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.looks = {}
        for key, (_feature, start, end) in self.axes.items():
            sep = coin.SoSeparator()
            material = coin.SoMaterial()
            material.diffuseColor.setValue(*AXIS_COLORS[key])
            material.emissiveColor.setValue(*[c * 0.6 for c in AXIS_COLORS[key]])
            style = coin.SoDrawStyle()
            style.lineWidth = 2
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, 2, [(start.x, start.y, start.z), (end.x, end.y, end.z)])
            line = coin.SoLineSet()
            line.numVertices.setValue(2)
            sep.addChild(material)
            sep.addChild(style)
            sep.addChild(coords)
            sep.addChild(line)
            self.root.addChild(sep)
            self.looks[key] = (material, style)
        self.hovered = None
        view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]

    def axis_at(self, position, reach=6.0):
        """Origin axis within `reach` pixels of the mouse and not behind the part, or None
        (where the part hides an axis, the click is the part's)."""
        best = None
        px, py = float(position[0]), float(position[1])
        for key, (_feature, start, end) in self.axes.items():
            try:
                ax, ay = self.view.getPointOnViewport(start)
                bx, by = self.view.getPointOnViewport(end)
            except Exception:
                continue
            dx, dy = bx - ax, by - ay
            length = dx * dx + dy * dy
            t = 0.0 if length < 1e-9 else ((px - ax) * dx + (py - ay) * dy) / length
            t = min(max(t, 0.0), 1.0)
            dist = math.hypot(ax + t * dx - px, ay + t * dy - py)
            if dist <= reach and (best is None or dist < best[1]):
                best = (key, dist)
        if best is None or self._hidden(best[0], position):
            return None
        return best[0]

    def _hidden(self, key, position):
        """True if a face or edge of the part is in front of the axis under the mouse."""
        try:
            info = self.view.getObjectInfo(tuple(position))
        except Exception:
            info = None
        if not info or not str(info.get("Component", "")).startswith(("Face", "Edge")):
            return False
        try:
            origin, direction = profile_pick.mouse_ray(self.view, position)
            _feature, start, end = self.axes[key]
            axis = end - start
            axis.normalize()
            # the point of the axis nearest to the mouse ray
            w0 = start - origin
            b = axis.dot(direction)
            denom = 1.0 - b * b
            if abs(denom) < 1e-9:
                return False
            s_axis = (b * direction.dot(w0) - axis.dot(w0)) / denom
            point = start + axis * s_axis
            hit = App.Vector(info["x"], info["y"], info["z"])
            return (hit - origin).dot(direction) < (point - origin).dot(direction) - 1e-6
        except Exception:
            return False

    def clicked_recently(self):
        return time.time() - self.last_click < OVERLAY_CLICK_S

    def _moved(self, info):
        try:
            key = self.axis_at(info["Position"])
            if key != self.hovered:
                for name, (material, style) in self.looks.items():
                    lit = name == key
                    color = AXIS_COLORS[name]
                    material.emissiveColor.setValue(*[c * (1.0 if lit else 0.6) for c in color])
                    style.lineWidth = 5 if lit else 2
                self.hovered = key
        except Exception as exc:
            warn("axis hover: %s" % exc)

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            position = tuple(info["Position"])
            if profile_pick.handle_at(self.view, position):
                return  # a press on a drag arrow drags it
            key = self.axis_at(position)
            if key is not None:
                self.last_click = time.time()
                self.on_pick(self.axes[key][0])  # the panel defers the work
        except Exception as exc:
            warn("axis pick: %s" % exc)

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


def _part_depth(view, position):
    """Distance along the mouse ray to the part under the mouse, or None."""
    try:
        info = view.getObjectInfo(tuple(position))
    except Exception:
        return None
    if not info or not str(info.get("Component", "")).startswith(("Face", "Edge", "Vertex")):
        return None
    origin, direction = profile_pick.mouse_ray(view, position)
    return (App.Vector(info["x"], info["y"], info["z"]) - origin).dot(direction)


def front_planes():
    """sketch_ui.PlanePicker (the three big origin squares) that also takes a click on a
    square in front of the part, like Fusion (the original leaves any click over the part to
    the part, which suits Create Sketch but made the Mirror Plane unpickable from most
    views). Made on demand: sketch_ui is imported only when the box waits."""
    from .sketch_ui import PlanePicker

    class FrontPlanePicker(PlanePicker):
        def front_plane_at(self, position):
            best = None
            for role in self.objects:
                base, normal, u, v = self._frame(role)
                hit = profile_pick.ray_plane(self.view, position, base, normal)
                if hit is None:
                    continue
                point, t = hit
                local = point - base
                half = self.size / 2.0
                if abs(local.dot(u)) <= half and abs(local.dot(v)) <= half:
                    if best is None or t < best[1]:
                        best = (role, t)
            if best is None:
                return None
            depth = _part_depth(self.view, position)
            if depth is not None and depth < best[1]:
                return None  # the part is in front of the square: the click is the part's
            return best[0]

        def _moved(self, info):
            try:
                role = self.front_plane_at(info["Position"])
                material = self.materials.get(role)
                if material is not self.hovered:
                    from .sketch_ui import HOVER, IDLE

                    for m, look in ((self.hovered, IDLE), (material, HOVER)):
                        if m is not None:
                            m.diffuseColor.setValue(*look[0])
                            m.emissiveColor.setValue(*[c * 0.5 for c in look[0]])
                            m.transparency.setValue(look[1])
                    self.hovered = material
            except Exception as exc:
                warn("plane hover: %s" % exc)

        def _button(self, info):
            try:
                if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                    return
                position = tuple(info["Position"])
                if profile_pick.handle_at(self.view, position):
                    return
                role = self.front_plane_at(position)
                if role is not None:
                    self.on_pick(self.objects[role])
            except Exception as exc:
                warn("plane pick: %s" % exc)

    return FrontPlanePicker


class InstanceDots:
    """Fusion's Suppression: a dot on every copy. Click a dot to leave that copy out (the dot
    turns grey) or to put it back: on_toggle(index). Drawn over the part, not selectable."""

    ON = (0.30, 0.62, 0.95)
    OFF = (0.55, 0.55, 0.55)

    def __init__(self, view, points, suppressed, on_toggle, radius):
        from pivy import coin

        self.view = view
        self.points = list(points)
        self.on_toggle = on_toggle
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        common.on_top(self.root)
        for i, point in enumerate(self.points):
            sep = coin.SoSeparator()
            material = coin.SoMaterial()
            color = self.OFF if i in suppressed else self.ON
            material.diffuseColor.setValue(*color)
            material.emissiveColor.setValue(*[c * 0.6 for c in color])
            move = coin.SoTranslation()
            move.translation.setValue(point.x, point.y, point.z)
            ball = coin.SoSphere()
            ball.radius = radius
            sep.addChild(material)
            sep.addChild(move)
            sep.addChild(ball)
            self.root.addChild(sep)
        view.getSceneGraph().addChild(self.root)
        self.callback = view.addEventCallback("SoMouseButtonEvent", self._button)

    def dot_at(self, position, reach=10.0):
        best = None
        px, py = float(position[0]), float(position[1])
        for i, point in enumerate(self.points):
            try:
                x, y = self.view.getPointOnViewport(point)
            except Exception:
                continue
            dist = math.hypot(x - px, y - py)
            if dist <= reach and (best is None or dist < best[1]):
                best = (i, dist)
        return best[0] if best else None

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            position = tuple(info["Position"])
            if profile_pick.handle_at(self.view, position):
                return
            index = self.dot_at(position)
            if index is not None:
                self.on_toggle(index)  # the panel defers the work
        except Exception as exc:
            warn("suppression dot: %s" % exc)

    def remove(self):
        try:
            self.view.removeEventCallback("SoMouseButtonEvent", self.callback)
        except Exception:
            pass
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


class CountBox(QtWidgets.QSpinBox):
    """The Quantity field: a whole number, or a parameter / formula typed over it (Fusion's
    fields take both; preview.FormulaInput evaluates the text when the field is left)."""

    def validate(self, text, pos):
        return (QtGui.QValidator.Acceptable, text, pos)

    on_step = None  # called before the arrows / wheel / Up-Down change the count

    def valueFromText(self, text):
        try:
            return max(self.minimum(), min(self.maximum(), int(round(float(text)))))
        except (TypeError, ValueError):
            return self.value()  # a formula: FormulaInput puts its value in

    def stepBy(self, steps):
        # A count set with the arrows is a plain number again (no formula behind it).
        if self.on_step is not None:
            try:
                self.on_step()
            except Exception as exc:
                warn("quantity step: %s" % exc)
        super().stepBy(steps)


class _CountAdapter:
    """CountBox seen as a value field by preview.FormulaInput."""

    def __init__(self, spin):
        self.widget = spin

    def set_value(self, value):
        self.widget.blockSignals(True)
        try:
            self.widget.setValue(max(1, int(round(float(value)))))
        finally:
            self.widget.blockSignals(False)


class ViewProviderPattern:
    """View provider of SciForge's own pattern feature (pattern.PatternFeature)."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        kind = pattern.kind_of(getattr(self, "Object", None))
        return ui_icon_path(ICONS.get(kind, "pattern_rect"))

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


ICONS = {
    "rectangular": "pattern_rect",
    "circular": "pattern_circ",
    "path": "pattern_rect",
    "mirror": "mirror",
}


# -- the dialog -----------------------------------------------------------------------------------
class PatternPanel(Panel):
    """Rectangular / Circular Pattern, Pattern on Path (kind) and, in mirror_ui, Mirror."""

    kind = "rectangular"
    last = None  # the most recent panel (tests and diagnostics)

    def __init__(self, doc, kind=None, feature=None, preselection=None):
        self.kind = kind or self.kind
        self.title = pattern.TITLES[self.kind]
        self.icon = ICONS[self.kind]
        super().__init__(doc, self.title if feature is None else "Edit " + self.title)
        PatternPanel.last = self
        self.target = feature
        self.editing = feature is not None
        self.error = ""
        self.waiting = ""
        self.formula_error = ""
        self.dirty = False
        self._geometry_changed = False
        self._quiet = False
        self._syncing = False
        self.handles = {}
        self.dots = None
        self.marks = None
        self.axis_picker = None
        self.plane_picker = None
        self.observer = None
        self.gate = None
        self.watch = None
        self.view = Gui.ActiveDocument.ActiveView
        self.options = pattern.with_defaults({"quantity": 3 if self.kind == "circular" else 2})
        if feature is not None:
            self.body = pattern.feature_body(feature)
            self.base = pattern.base_of(feature)
            try:
                _kind, read = pattern.read(feature)
                self.options.update(read)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        else:
            self.body = commands.find_body()
            self.base = self.body.Tip if self.body is not None else None
        self.active = "objects"
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self._build_form()
        self._show_options()
        try:
            self.marks = Marks(self.view)
        except Exception as exc:
            warn("%s: no highlight: %s" % (self.title, exc))
        self._watch()
        if feature is None:
            self._start(preselection or [])
        else:
            self._refresh()
            self._make_handles()
            self._update_dots()
        self._show_active()

    # -- form ---------------------------------------------------------------------------------
    def _selection(self, name, empty, label):
        field = common.SelectionField(self, name, empty)
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, field.widget)
        self.fields[name] = field
        self.captions[name] = caption
        return field

    def _build_form(self):
        form = self.layout
        self.fields = {}
        self.captions = {}
        self.pattern_type = _combo(
            PATTERN_TYPES,
            self.options["pattern_type"],
            disabled={"components": "SciForge designs have no components yet."},
        )
        form.addRow("Pattern Type", self.pattern_type)
        self._selection("objects", "Select", "Objects")
        self.objects_label = QtWidgets.QLabel("")
        self.objects_label.setWordWrap(True)
        self.objects_label.setStyleSheet("color: #b8c7d9;")
        form.addRow(self.objects_label)
        self._kind_fields()
        self.compute = _combo(
            COMPUTE,
            "identical",
            disabled={
                "optimized": "Not available in SciForge yet: copies are identical.",
                "adjust": "Not available in SciForge yet: copies are identical.",
            },
        )
        self.compute_label = QtWidgets.QLabel("Compute Option")
        form.addRow(self.compute_label, self.compute)
        self.info = QtWidgets.QLabel("")  # what the dialog waits for (not a problem)
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color: #8cc4ff;")
        form.addRow(self.info)
        self.formulas = QtWidgets.QLabel("")
        self.formulas.setWordWrap(True)
        self.formulas.setStyleSheet("color: #b8c7d9;")
        form.addRow(self.formulas)
        self.finish_layout()
        self.formula_inputs = [
            preview.FormulaInput(self, key, field) for key, field in self._value_fields().items()
        ]
        for key in ("quantity", "quantity2"):
            spin = getattr(self, key, None)
            if spin is not None:  # a count can follow a parameter too (Fusion)
                self.formula_inputs.append(preview.FormulaInput(self, key, _CountAdapter(spin)))
                spin.on_step = lambda key=key: self._forget_formula(key)
        self.pattern_type.currentIndexChanged.connect(self._type_changed)

    def _value_fields(self):
        """{options key: DistanceField} of the value fields that take formulas."""
        fields = {}
        for key in ("distance", "distance2", "angle"):
            field = getattr(self, key + "_field", None)
            if field is not None:
                fields[key] = field
        return fields

    def _suppression(self):
        box = QtWidgets.QCheckBox()
        box.setChecked(bool(self.options.get("suppressed")))
        box.setToolTip(
            "Show a dot on every copy: click a dot to leave that copy out, again to put it back"
        )
        box.toggled.connect(self._suppression_toggled)
        self.layout.addRow("Suppression", box)
        return box

    def _quantity(self, value, on_change):
        spin = CountBox()
        spin.setRange(1, 1000)
        spin.setValue(int(value))
        spin.valueChanged.connect(on_change)
        return spin

    def _kind_fields(self):
        form = self.layout
        if self.kind == "rectangular":
            self.distribution = _combo(DISTRIBUTIONS, self.options["distribution"])
            form.addRow("Distribution", self.distribution)
            self.suppression = self._suppression()
            form.addRow(_bold("Direction 1"))
            self._selection("direction", "Select", "Direction")
            self.quantity = self._quantity(self.options["quantity"], self._typed)
            form.addRow("Quantity", self.quantity)
            self.distance_field = DistanceField(
                self.options["distance"], on_change=self._distance_typed
            )
            form.addRow("Distance", self.distance_field.widget)
            self.direction_type = _combo(DIRECTION_TYPES, self.options["direction_type"])
            form.addRow("Direction Type", self.direction_type)
            form.addRow(_bold("Direction 2"))
            self._selection("direction2", "Select", "Direction")
            self.quantity2 = self._quantity(self.options["quantity2"], self._typed)
            form.addRow("Quantity", self.quantity2)
            self.distance2_field = DistanceField(
                self.options["distance2"], on_change=self._distance2_typed
            )
            form.addRow("Distance", self.distance2_field.widget)
            self.direction_type2 = _combo(DIRECTION_TYPES, self.options["direction_type2"])
            form.addRow("Direction Type", self.direction_type2)
            for box in (self.distribution, self.direction_type, self.direction_type2):
                box.currentIndexChanged.connect(self._typed)
        elif self.kind == "circular":
            self._selection("axis", "Select", "Axis")
            self.circular_type = _combo(CIRCULAR_TYPES, self.options["circular_type"])
            form.addRow("Type", self.circular_type)
            self.quantity = self._quantity(self.options["quantity"], self._typed)
            form.addRow("Quantity", self.quantity)
            self.angle_field = DistanceField(
                self.options["angle"], unit="deg", on_change=self._angle_typed
            )
            self.angle_label = QtWidgets.QLabel("Total Angle")
            form.addRow(self.angle_label, self.angle_field.widget)
            self.suppression = self._suppression()
            self.circular_type.currentIndexChanged.connect(self._circular_type_changed)
        elif self.kind == "path":
            self._selection("path", "Select", "Path")
            self.distance_field = DistanceField(
                self.options["distance"], on_change=self._distance_typed
            )
            form.addRow("Distance", self.distance_field.widget)
            self.quantity = self._quantity(self.options["quantity"], self._typed)
            form.addRow("Quantity", self.quantity)
            self.distribution = _combo(DISTRIBUTIONS, self.options["distribution"])
            form.addRow("Distribution", self.distribution)
            self.direction_type = _combo(DIRECTION_TYPES, self.options["direction_type"])
            form.addRow("Direction Type", self.direction_type)
            self.orientation = _combo(ORIENTATIONS, self.options["orientation"])
            form.addRow("Orientation", self.orientation)
            self.suppression = self._suppression()
            for box in (self.distribution, self.direction_type, self.orientation):
                box.currentIndexChanged.connect(self._typed)
        elif self.kind == "mirror":
            self._selection("plane", "Select", "Mirror Plane")
            self.operation = _combo(OPERATIONS, self.options["operation"])
            self.operation_label = QtWidgets.QLabel("Operation")
            form.addRow(self.operation_label, self.operation)
            self.operation.currentIndexChanged.connect(self._typed)

    def _show_options(self):
        """Put self.options into the widgets (without reacting)."""
        self._quiet = True
        try:
            common.set_combo(self.pattern_type, self.options["pattern_type"])
            for name in (
                "distribution",
                "direction_type",
                "direction_type2",
                "orientation",
                "operation",
            ):
                box = getattr(self, name, None)
                if box is not None:
                    common.set_combo(box, self.options[name])
            if getattr(self, "circular_type", None) is not None:
                common.set_combo(self.circular_type, self.options["circular_type"])
            if getattr(self, "suppression", None) is not None:
                self.suppression.blockSignals(True)
                self.suppression.setChecked(bool(self.options.get("suppressed")))
                self.suppression.blockSignals(False)
            for name in ("quantity", "quantity2"):
                spin = getattr(self, name, None)
                if spin is not None:
                    spin.setValue(int(self.options[name]))
            for key, field in self._value_fields().items():
                field.set_value(float(self.options[key]))
        finally:
            self._quiet = False
        self._update_visibility()
        self._refresh()
        self.show_formulas()

    def _update_visibility(self):
        features = self.options["pattern_type"] == "features"
        self.compute.setVisible(features)
        self.compute_label.setVisible(features)
        if self.kind == "circular":
            full = self.circular_type.currentData() == "full"
            self.angle_field.widget.setVisible(not full)
            self.angle_label.setVisible(not full)
        if self.kind == "mirror":
            bodies = self.options["pattern_type"] == "bodies"
            self.operation.setVisible(bodies)
            self.operation_label.setVisible(bodies)

    def _collect(self):
        options = self.options
        options["pattern_type"] = self.pattern_type.currentData()
        for name in (
            "distribution",
            "direction_type",
            "direction_type2",
            "orientation",
            "operation",
        ):
            box = getattr(self, name, None)
            if box is not None:
                options[name] = box.currentData()
        if getattr(self, "circular_type", None) is not None:
            options["circular_type"] = self.circular_type.currentData()
        for name in ("quantity", "quantity2"):
            spin = getattr(self, name, None)
            if spin is not None:
                options[name] = int(spin.value())
        for key, field in self._value_fields().items():
            options[key] = field.value()

    # -- formulas (preview.FormulaInput calls these) --------------------------------------------
    NAMES = {
        "distance": "Distance",
        "distance2": "Distance (direction 2)",
        "angle": "Total Angle",
        "quantity": "Quantity",
        "quantity2": "Quantity (direction 2)",
    }

    def show_formulas(self):
        rows = [
            "%s = %s" % (self.NAMES.get(k, k), v)
            for k, v in sorted(self.options.get("expressions", {}).items())
            if v
        ]
        self.formulas.setText("\n".join(rows))

    def _forget_formula(self, key):
        """Drop the formula of a field without rebuilding (the new value rebuilds)."""
        if self.options["expressions"].pop(key, None) is not None:
            self.formula_error = ""
            self.show_formulas()

    def drop_formula(self, key):
        self.formula_error = ""
        if self.options["expressions"].pop(key, None) is not None:
            self.show_formulas()
            self._changed()

    def formula_typed(self, key, text, value):
        self.formula_error = ""
        if key.startswith("quantity"):
            problem = ""
            if self.options["pattern_type"] == "bodies" and self.kind != "mirror":
                problem = "A pattern of bodies takes a plain number as its quantity."
            elif value < 0.5:
                problem = "'%s' is less than 1: the quantity must be 1 or more." % text
            if problem:
                _CountAdapter(getattr(self, key)).set_value(self.options[key])  # as it was
                self.formula_failed(key, problem)
                return
        self.options["expressions"][key] = text
        handler = {
            "distance": self._distance_typed,
            "distance2": self._distance2_typed,
            "angle": self._angle_typed,
            "quantity": self._typed,
            "quantity2": self._typed,
        }.get(key)
        if handler is not None:
            handler(value)
        self.show_formulas()

    def formula_cleared(self, key):
        self.drop_formula(key)

    def formula_failed(self, key, text):
        self.formula_error = text
        self.message.setText("⚠ " + text)

    # -- selection boxes --------------------------------------------------------------------------
    def activate(self, name):
        if name not in self.fields:
            return
        self.active = name
        self._show_active()

    def _show_active(self):
        for name, field in self.fields.items():
            field.set_active(name == self.active)
        self._update_pickers()

    def clear_field(self, name):
        if name == "objects":
            self.options["objects"] = []
        else:
            self.options[name] = None
        self.activate(name)
        self._changed(new_geometry=True)

    def _update_pickers(self):
        """Origin axes while a direction/axis box waits, origin planes for the mirror plane."""
        wants_axes = self.active in ("direction", "direction2", "axis") and not self._closed
        wants_planes = self.active == "plane" and not self._closed
        if wants_axes and self.axis_picker is None and self.body is not None:
            try:
                self.axis_picker = AxisPicker(
                    self.view, self.body, self._axis_clicked, self._size()
                )
            except Exception as exc:
                warn("%s: origin axes unavailable: %s" % (self.title, exc))
        elif not wants_axes and self.axis_picker is not None:
            self.axis_picker.remove()
            self.axis_picker = None
        if wants_planes and self.plane_picker is None and self.body is not None:
            try:
                self.plane_picker = front_planes()(self.view, self.body, self._plane_clicked)
            except Exception as exc:
                warn("%s: origin planes unavailable: %s" % (self.title, exc))
        elif not wants_planes and self.plane_picker is not None:
            self.plane_picker.remove()
            self.plane_picker = None

    def _size(self):
        """Length of the drawn origin axes: a bit more than the part."""
        try:
            shape = self.base.Shape if self.base is not None else None
            if shape is not None and not shape.isNull():
                box = shape.BoundBox
                return max(20.0, 0.75 * box.DiagonalLength + (box.Center.Length))
        except Exception:
            pass
        return 50.0

    def _axis_clicked(self, axis):
        """An origin axis was pressed (inside FreeCAD's mouse handling: work comes later)."""
        self._overlay_time = time.time()
        if self._closed:
            return
        QtCore.QTimer.singleShot(0, lambda: self._reference_later((axis, "")))

    def _reference_later(self, ref):
        if self._closed:
            return
        try:
            self._reference_picked(ref)
        except Exception as exc:
            warn("%s pick: %s" % (self.title, exc))

    def _plane_clicked(self, plane):
        self._overlay_time = time.time()
        if self._closed:
            return
        try:
            QtCore.QTimer.singleShot(0, lambda: self._reference_later((plane, "")))
        except Exception as exc:
            warn("%s plane: %s" % (self.title, exc))

    def _overlay_clicked_recently(self):
        """True right after a click on a drawn origin axis or plane: the face behind it that
        FreeCAD selects on the same click is not a pick."""
        return time.time() - getattr(self, "_overlay_time", 0.0) < OVERLAY_CLICK_S

    # -- start ------------------------------------------------------------------------------------
    def _start(self, preselection):
        if self.body is None or self.base is None or self.base.Shape.isNull():
            self.message.setText("⚠ Make a solid first (Create Sketch, then Extrude).")
            return
        objects, ptype = self._from_selection(preselection)
        if objects:
            self.options["pattern_type"] = ptype
            self.options["objects"] = objects
            self._quiet = True
            common.set_combo(self.pattern_type, ptype)
            self._quiet = False
            self._update_visibility()
            self.active = self._next_box()
            self._changed(new_geometry=True)
            self._timer.stop()
            self._recompute()  # the preview is there when the dialog appears
        else:
            self.info.setText(self._hint())
        self._refresh()

    def _from_selection(self, preselection):
        """(objects, pattern type) from what was selected before the command started."""
        features, faces, bodies = [], [], []
        for obj, sub in preselection:
            if obj is None or obj.Document is not self.doc:
                continue
            if obj.TypeId == "PartDesign::Body":
                if not sub:
                    bodies.append((obj, ""))
                    continue
                obj = obj.Tip
            if sub.startswith("Face"):
                ref = self._base_face(obj, sub)
                if ref is not None and ref not in faces:
                    faces.append(ref)
            elif not sub and self._usable_feature(obj):
                if (obj, "") not in features:
                    features.append((obj, ""))
        if features:
            return features, "features"
        if faces:
            return faces, "faces"
        if bodies:
            return bodies[:1], "bodies"
        return [], self.options["pattern_type"]

    def _next_box(self):
        for name in ("direction", "axis", "plane", "path"):
            if name in self.fields and self.options.get(name) is None:
                return name
        return "objects"

    def _hint(self):
        ptype = self.options["pattern_type"]
        if ptype == "features":
            return "Click the features to repeat in the timeline (or a face they made)."
        if ptype == "faces":
            return "Click the faces to repeat: every face of a hole, a pocket or a boss."
        if self.kind == "mirror":
            return "Click the body to mirror (on the part, or in the browser)."
        return "Click the body to repeat: each copy becomes a new body."

    # -- watching clicks ----------------------------------------------------------------------------
    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                if not panel._syncing:
                    QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _unwatch(self):
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        for picker in (self.axis_picker, self.plane_picker):
            if picker is not None:
                try:
                    picker.remove()
                except Exception:
                    pass
        self.axis_picker = self.plane_picker = None

    def _selection_changed(self):
        if self._closed:
            return
        try:
            picks = [p for p in common.picks() if p[0].Document is self.doc]
            if not picks:
                return
            self._syncing = True
            try:
                Gui.Selection.clearSelection()
            finally:
                self._syncing = False
            if self._overlay_clicked_recently():
                return  # the origin axis/plane drawn over the part took this click
            for obj, short, _point in picks:
                self._picked(obj, short)
        except Exception as exc:
            warn("%s pick: %s" % (self.title, exc))

    def _picked(self, obj, short):
        if self.active == "objects":
            self._object_picked(obj, short)
        else:
            self._reference_picked((obj, short))

    # -- objects --------------------------------------------------------------------------------
    def _usable_feature(self, obj):
        """A solid step of this body before the pattern."""
        body = self.body
        if body is None or not pattern.is_solid_feature(obj):
            return False
        if pattern.owner_body(obj) is not body or obj is self.target:
            return False
        if self.base is None:
            return False
        return obj is self.base or pattern.before(body, self.base, obj)

    def _object_picked(self, obj, short):
        ptype = self.options["pattern_type"]
        if obj.TypeId == "PartDesign::Body" and short:
            obj = obj.Tip
        if ptype == "bodies":
            body = pattern.owner_body(obj)
            if body is None:
                self.message.setText("⚠ Pick a body.")
                return
            if self.editing and body is not self.body:
                self.message.setText("⚠ This pattern copies %s." % self.body.Label)
                return
            self.body = body
            if self.target is None:
                self.base = body.Tip
            self.options["objects"] = [(body, "")]
            self._changed(new_geometry=True)
            return
        if ptype == "features":
            feature = None
            if not short:
                if obj.TypeId == "Sketcher::SketchObject":
                    self.message.setText(
                        "⚠ A sketch cannot be patterned here: pick the feature made from it."
                    )
                    return
                if not self._usable_feature(obj):
                    self.message.setText(
                        "⚠ Pick a feature of %s that comes before this pattern."
                        % (self.body.Label if self.body else "the body")
                    )
                    return
                feature = obj
            elif short.startswith("Face"):
                feature = self._feature_of_face(obj, short)
                if feature is None:
                    self.message.setText(
                        "⚠ No feature to repeat made that face. Click a feature in the timeline."
                    )
                    return
            else:
                return
            self._toggle((feature, ""))
            return
        if ptype == "faces":
            if not short.startswith("Face"):
                if not short:
                    self.message.setText("⚠ Pattern Type is Faces: click faces of the part.")
                return
            ref = self._base_face(obj, short)
            if ref is None:
                self.message.setText("⚠ That face is one of the copies. Click an original face.")
                return
            self._toggle(ref)

    def _toggle(self, ref):
        objects = list(self.options["objects"])
        if ref in objects:
            objects.remove(ref)
        else:
            objects.append(ref)
        self.options["objects"] = objects
        self.message.setText("")
        self._changed(new_geometry=True)

    def _feature_of_face(self, obj, short):
        face = profile_pick.global_face(obj, short)
        if face is None or self.body is None:
            return None
        local = _local(face, self.body)
        found = pattern.feature_of_face(self.body, local, until=self.target)
        if found is not None and self._usable_feature(found):
            return found
        return None

    def _base_face(self, obj, short):
        """(base feature, "FaceN") for a face clicked on whatever is shown (the preview)."""
        if self.base is None:
            return None
        if obj is self.base:
            return (obj, short)
        face = profile_pick.global_face(obj, short)
        if face is None:
            return None
        name = profile_pick.face_name_in(self.base, face)
        return (self.base, name) if name else None

    def _base_ref(self, obj, short):
        """A clicked edge/face of the shown part, as an element of the base feature (the
        pattern itself or later steps cannot be its own reference)."""
        if not short or self.base is None or obj is self.base:
            return (obj, short)
        body = pattern.owner_body(obj)
        if body is not self.body or not pattern.is_solid_feature(obj):
            return (obj, short)
        if self._usable_feature(obj):
            return (obj, short)
        if short.startswith("Face"):
            return self._base_face(obj, short)
        if short.startswith("Edge"):
            try:
                edge = obj.Shape.getElement(short)  # same body: same coordinates as the base
            except Exception:
                return None
            for i, candidate in enumerate(self.base.Shape.Edges, start=1):
                if _same_edge(edge, candidate):
                    return (self.base, "Edge%d" % i)
        return None

    # -- references (directions, axis, plane, path) ------------------------------------------------
    def _reference_picked(self, ref):
        name = self.active
        if name == "objects" or name not in self.fields:
            return
        obj, short = ref
        if obj.TypeId == "PartDesign::Body" and short:
            obj = obj.Tip
        if obj.TypeId in pattern.LINE_TYPES + pattern.PLANE_TYPES:
            short = ""  # a datum axis or plane is used whole, wherever it was clicked
        if short.startswith("Vertex"):
            self.message.setText("⚠ Pick an edge, a face or an axis, not a point.")
            return
        if obj.TypeId == "PartDesign::Body" and not short:
            self.message.setText("⚠ Pick an edge, a face, an axis or a plane, not a whole body.")
            return
        ref = self._base_ref(obj, short)
        if ref is None:
            self.message.setText("⚠ That belongs to the copies. Pick an edge of the original part.")
            return
        try:
            if name in ("direction", "direction2"):
                pattern.direction_of(ref)
            elif name == "axis":
                pattern.axis_of(ref)
            elif name == "plane":
                pattern.plane_of(ref)
            elif name == "path":
                if ref[0].TypeId == "Sketcher::SketchObject" and short.startswith("Edge"):
                    ref = (ref[0], short)
                pattern.path_edges(ref)
        except PatternError as exc:
            self.message.setText("⚠ %s" % exc)
            return
        self.options[name] = ref
        self.message.setText("")
        if name == "direction" and self.options.get("direction2") is None:
            self.options["direction2"] = self._perpendicular(ref)
        self._default_distances(name)
        self.activate("objects")
        self._changed(new_geometry=True)

    def _perpendicular(self, ref):
        """Fusion offers the second direction at right angles to the first, in the floor plane
        (an origin axis or an edge of the part that runs that way)."""
        try:
            _p, d1 = pattern.direction_of(ref)
        except PatternError:
            return None
        up = App.Vector(0, 0, 1)
        d2 = up.cross(d1)
        if d2.Length < 1e-6:
            d2 = App.Vector(1, 0, 0)
        d2.normalize()
        for feature in self.body.Origin.OriginFeatures:
            role = getattr(feature, "Role", "")
            if role in AXES:
                _b, axis = pattern._line_of_datum(feature)
                if abs(abs(axis.dot(d2)) - 1.0) < 1e-9:
                    return (feature, "")
        if self.base is not None:
            for i, edge in enumerate(self.base.Shape.Edges, start=1):
                if pattern._is_line(edge):
                    t = pattern._unit(edge.tangentAt(edge.FirstParameter))
                    if abs(abs(t.dot(d2)) - 1.0) < 1e-9:
                        return (self.base, "Edge%d" % i)
        return None

    def _default_distances(self, name):
        """A new direction starts with copies that clear the original (like Fusion), unless
        a distance was typed, dragged or given as a formula already."""
        if self.editing or self.kind != "rectangular":
            return
        for suffix in {"direction": ("", "2"), "direction2": ("2",)}.get(name, ()):
            ref = self.options.get("direction" + suffix)
            if ref is None or self.options["expressions"].get("distance" + suffix):
                continue
            if getattr(self, "_distance%s_set" % suffix, False):
                continue
            size = self._size_along(ref)
            quantity = self.options["quantity" + suffix]
            if self.options["distribution"] == "spacing":
                value = default_distance(size, 2)
            else:
                value = default_distance(size, max(quantity, 2))
            self.options["distance" + suffix] = value
            getattr(self, "distance%s_field" % suffix).set_value(value)

    def _size_along(self, ref):
        try:
            _p, d = pattern.direction_of(ref)
            _c, box = pattern.objects_center(self.options)
            if box is None:
                return 10.0
            corners = [
                App.Vector(x, y, z)
                for x in (box.XMin, box.XMax)
                for y in (box.YMin, box.YMax)
                for z in (box.ZMin, box.ZMax)
            ]
            values = [c.dot(d) for c in corners]
            return max(values) - min(values)
        except Exception:
            return 10.0

    # -- values ----------------------------------------------------------------------------------
    def _type_changed(self, *_):
        if self._quiet:
            return
        # Fusion clears the objects when the pattern type changes (they are another kind).
        self.options["objects"] = []
        self.options["pattern_type"] = self.pattern_type.currentData()
        self.activate("objects")
        self.info.setText(self._hint())
        self._update_visibility()
        self._changed(new_geometry=True)

    def _suppression_toggled(self, on):
        """Fusion: Suppression on shows the dots; off makes every copy again."""
        if self._quiet or self._closed:
            return
        try:
            if not on and self.options.get("suppressed"):
                self.options["suppressed"] = []
                self._changed(new_geometry=True)
            self._update_dots()
        except Exception as exc:
            warn("%s suppression: %s" % (self.title, exc))

    def _dot_clicked(self, index):
        """A suppression dot was pressed (inside FreeCAD's mouse handling: work comes later)."""
        self._overlay_time = time.time()
        if not self._closed:
            QtCore.QTimer.singleShot(0, lambda: self._toggle_instance(index))

    def _toggle_instance(self, index):
        if self._closed:
            return
        try:
            suppressed = set(self.options.get("suppressed") or [])
            suppressed ^= {index}
            self.options["suppressed"] = sorted(suppressed)
            self._changed(new_geometry=True)
            self._update_dots()
        except Exception as exc:
            warn("%s suppression: %s" % (self.title, exc))

    def _instance_points(self):
        """Global position of every copy (suppressed ones too), at the objects' centre."""
        center, box = pattern.objects_center(self.options)
        moves = pattern.all_placements(self.kind, self.options, center=center)
        if box is not None:  # on top of what is patterned, like the arrows
            center = App.Vector(center.x, center.y, box.ZMax)
        return [pattern.to_global(self.body, move.multVec(center)) for move in moves]

    def _update_dots(self):
        if self.dots is not None:
            self.dots.remove()
            self.dots = None
        box = getattr(self, "suppression", None)
        if box is None or not box.isChecked() or self._closed or self.body is None:
            return
        if not self.options["objects"] or self.error or self.waiting:
            return
        try:
            points = self._instance_points()
            count = len(points)
            kept = [i for i in self.options.get("suppressed") or [] if i < count]
            if kept != list(self.options.get("suppressed") or []):
                self.options["suppressed"] = kept  # fewer copies now
            _center, objects_box = pattern.objects_center(self.options)
            radius = max(0.6, self._arrow_size(objects_box) * 0.12)
            self.dots = InstanceDots(self.view, points, set(kept), self._dot_clicked, radius)
        except PatternError:
            return
        except Exception as exc:
            warn("%s suppression dots unavailable: %s" % (self.title, exc))

    def _circular_type_changed(self, *_):
        if self._quiet:
            return
        ctype = self.circular_type.currentData()
        if ctype != "full" and abs(self.angle_field.value() - 360.0) < 1e-9:
            # an angle pattern over the whole circle is a Full one: start at a quarter
            self._quiet = True
            self.angle_field.set_value(180.0 if ctype == "angle" else 90.0)
            self._quiet = False
        self._update_visibility()
        self._changed(new_geometry=True)

    def _typed(self, *_):
        if not self._quiet:
            self._changed(new_geometry=True)

    def _distance_typed(self, value):
        if self._quiet:
            return
        self._distance_set = True
        handle = self.handles.get("distance")
        if handle is not None:
            handle.set_distance(value)
        self._changed()

    def _distance2_typed(self, value):
        if self._quiet:
            return
        self._distance2_set = True
        handle = self.handles.get("distance2")
        if handle is not None:
            handle.set_distance(value)
        self._changed()

    def _angle_typed(self, value):
        if self._quiet:
            return
        handle = self.handles.get("angle")
        if handle is not None:
            handle.set_angle(max(-180.0, min(180.0, value)))
        self._changed()

    def _dragged(self, key, value):
        if self._closed:
            return
        self.drop_formula(key)
        value = round(value, 2)
        if key == "distance":
            self._distance_set = True
        elif key == "distance2":
            self._distance2_set = True
        field = self._value_fields().get(key)
        if field is not None:
            self._quiet = True
            try:
                field.set_value(value)
            finally:
                self._quiet = False
        self._changed()

    def _angle_dragged(self, value):
        if self._closed:
            return
        self.drop_formula("angle")
        value = round(value, 1)
        if abs(value) < 1.0:
            value = 1.0 if value >= 0 else -1.0
        self._quiet = True
        try:
            self.angle_field.set_value(value)
        finally:
            self._quiet = False
        self._changed()

    def _changed(self, new_geometry=False):
        if self._closed:
            return
        self._update_visibility()
        self._collect()
        self.dirty = True
        if new_geometry:
            self._geometry_changed = True
        self._refresh()
        self.schedule()

    # -- preview ---------------------------------------------------------------------------------
    def schedule(self):
        if not self._closed:
            super().schedule()

    def _recompute(self):
        if self._closed:
            return
        try:
            if getattr(self.doc, "Recomputing", False):
                self.schedule()  # a long recompute is still running: try again shortly
                return
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self.show_status()
            self._refresh()
            if self._geometry_changed or self._handles_stale():
                self._geometry_changed = False
                self._make_handles()
            self._update_dots()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        self.waiting = ""
        self.error = ""
        try:
            pattern.check(self.kind, self.options)
        except pattern.NeedsPick as exc:
            self.waiting = str(exc)
            if not self.options["objects"] and self.target is not None and not self.editing:
                self._drop_preview()
            return
        except PatternError as exc:
            self.error = str(exc)
            return
        try:
            self.target = pattern.build(self.kind, self.options, feature=self.target)
        except PatternError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This pattern cannot be built: %s" % exc

    def _drop_preview(self):
        body = pattern.owner_body(self.target)
        pattern.remove(self.target)
        self.target = None
        self._remove_handles()
        if body is not None:
            pattern.show_tip(body)

    def feature(self):
        return self.target

    def show_status(self):
        self.info.setText(self.waiting)
        if self.formula_error:
            self.message.setText("⚠ " + self.formula_error)
            return
        if self.waiting:
            self.message.setText("")
            return
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = _plain(preview.failure(self.target))
        self.message.setText("⚠ " + text if text else "")

    def _refresh(self):
        """Selection boxes, the list of picks, the highlight in the 3D view."""
        if self._closed:
            return
        objects = [ref for ref in self.options["objects"] if pattern.alive(ref[0])]
        self.options["objects"] = objects
        count = len(objects)
        self.fields["objects"].set_text("%d selected" % count if count else "")
        names = []
        refs = [self.options.get(n) for n in ("direction", "direction2", "axis", "plane", "path")]
        titles = self._titles() if objects or any(refs) else {}
        for obj, sub in objects:
            title = titles.get(obj.Name, obj.Label)
            text = title if not sub else "%s of %s" % (sub.rstrip("0123456789"), title)
            if text not in names:
                names.append(text)
        self.objects_label.setText(", ".join(names[:6]) + (" ..." if len(names) > 6 else ""))
        for name in ("direction", "direction2", "axis", "plane", "path"):
            if name in self.fields:
                self.fields[name].set_text(self._ref_text(self.options.get(name), titles))
        self._show_marks()

    @staticmethod
    def _ref_text(ref, titles):
        """A picked reference as the user knows it: "X Axis", "Edge of Extrude 1"."""
        text = pattern.ref_label(ref)
        if not ref or not ref[1] or not pattern.alive(ref[0]):
            return text
        title = titles.get(ref[0].Name)
        if title:
            return "%s of %s" % (ref[1].rstrip("0123456789") or ref[1], title)
        return text

    def _titles(self):
        """{object name: its title in the timeline} ("Extrude 2"), as the user knows them."""
        try:
            from . import timeline_ops

            timeline = timeline_ops.timeline(self.doc, deps=False)
            return {item.name: item.display for item in timeline.items}
        except Exception:
            return {}

    def _show_marks(self):
        if self.marks is None or self.body is None:
            return
        faces, lines = [], []
        try:
            picked = list(self.options["objects"])
            plane = self.options.get("plane")
            if plane is not None and plane[1].startswith("Face"):
                picked.append(plane)  # a flat face picked as the mirror plane is shown too
            for obj, sub in picked:
                if sub.startswith("Face"):
                    face = profile_pick.global_face(obj, sub)
                    if face is not None:
                        faces.append(face)
            size = self._size()
            for name in ("direction", "direction2", "axis", "path"):
                ref = self.options.get(name)
                if ref is None or name not in self.fields:
                    continue
                try:
                    if name == "path":
                        for edge in pattern.path_edges(ref):
                            pts = edge.discretize(24)
                            for a, b in zip(pts, pts[1:]):
                                lines.append(
                                    (
                                        pattern.to_global(self.body, a),
                                        pattern.to_global(self.body, b),
                                    )
                                )
                        continue
                    point, d = pattern.axis_of(ref) if name == "axis" else pattern.direction_of(ref)
                    if name != "axis":
                        center, _box = pattern.objects_center(self.options)
                        if self.options["objects"]:
                            point = center
                    lines.append(
                        (
                            pattern.to_global(self.body, point - d * (size * 0.15)),
                            pattern.to_global(self.body, point + d * (size * 0.6)),
                        )
                    )
                except Exception:
                    continue
            self.marks.show(faces, lines)
        except Exception as exc:
            warn("%s highlight: %s" % (self.title, exc))

    # -- handles ---------------------------------------------------------------------------------
    def _remove_handles(self):
        for handle in self.handles.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.handles = {}

    def _arrow_size(self, box=None):
        """Arrows about an eighth of the part's size (Fusion's are about that on screen)."""
        try:
            part = self.base.Shape.BoundBox
            return max(3.0, min(part.DiagonalLength * 0.12, 25.0))
        except Exception:
            diag = box.DiagonalLength if box is not None else 30.0
            return max(3.0, min(diag * 0.5, 25.0))

    def _wanted_handles(self):
        wanted = set()
        if self.target is None or self.error:
            return wanted
        if self.kind == "rectangular":
            wanted.add("distance")
            if self.options["direction2"] is not None:
                wanted.add("distance2")
        elif self.kind == "circular" and self.options["circular_type"] != "full":
            wanted.add("angle")
        elif self.kind == "path":
            wanted.add("distance")
        return wanted

    def _handles_stale(self):
        if any(_is_dragging(h) for h in self.handles.values()):
            return False
        return self._wanted_handles() != set(self.handles)

    def _make_handles(self):
        if self._closed or any(_is_dragging(h) for h in self.handles.values()):
            return
        self._remove_handles()
        wanted = self._wanted_handles()
        if not wanted or self.body is None:
            return
        try:
            center, box = pattern.objects_center(self.options)
            size = self._arrow_size(box)
            # The arrows start on top of what is patterned (a hole's centre would be inside
            # the part, where it can be neither seen nor grabbed), a little above it.
            if box is not None:
                center = App.Vector(center.x, center.y, box.ZMax + size * 0.15)
            if self.kind == "rectangular":
                for suffix in ("", "2"):
                    key = "distance" + suffix
                    if key not in wanted:
                        continue
                    _p, d = pattern.direction_of(self.options["direction" + suffix])
                    origin = pattern.to_global(self.body, center)
                    direction = pattern.to_global(self.body, vector=d)
                    self.handles[key] = ArrowDragger(
                        origin,
                        direction,
                        float(self.options[key]),
                        size,
                        on_drag=lambda v, k=key: self._dragged(k, v),
                        on_release=lambda v, k=key: self._dragged(k, v),
                    )
                    common.on_top(self.handles[key].root)  # Fusion never hides its arrows
                    self.handles[key].origin = origin  # tests aim at the arrow
                    self.handles[key].direction = direction
            elif self.kind == "path":
                path = pattern._Path(pattern.path_edges(self.options["path"]))
                start = path.locate(center)
                point, tangent = path.at(start)
                origin = pattern.to_global(self.body, point)
                direction = pattern.to_global(self.body, vector=tangent)
                self.handles["distance"] = ArrowDragger(
                    origin,
                    direction,
                    float(self.options["distance"]),
                    size,
                    on_drag=lambda v: self._dragged("distance", v),
                    on_release=lambda v: self._dragged("distance", v),
                )
                common.on_top(self.handles["distance"].root)
                self.handles["distance"].origin = origin
                self.handles["distance"].direction = direction
            elif self.kind == "circular":
                from .extrude_ui import AngleDragger

                point, axis = pattern.axis_of(self.options["axis"])
                offset = center - point
                radial = offset - axis * offset.dot(axis)
                if radial.Length < 1e-6:
                    radial = axis.cross(App.Vector(1, 0, 0))
                    if radial.Length < 1e-6:
                        radial = axis.cross(App.Vector(0, 1, 0))
                radius = max(radial.Length, 5.0)
                radial.normalize()
                pivot = point + axis * offset.dot(axis)
                angle = max(-180.0, min(180.0, float(self.options["angle"])))
                self.handles["angle"] = AngleDragger(
                    pattern.to_global(self.body, pivot),
                    pattern.to_global(self.body, vector=axis),
                    pattern.to_global(self.body, vector=radial),
                    angle,
                    radius,
                    size * 0.3,
                    on_drag=self._angle_dragged,
                    on_release=self._angle_dragged,
                )
                common.on_top(self.handles["angle"].root)
        except Exception as exc:
            warn("%s handles unavailable: %s" % (self.title, exc))

    # -- OK / Cancel -----------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        if self.formula_error:
            self.message.setText("⚠ " + self.formula_error)
            return False
        self._timer.stop()
        self._collect()
        self.dirty = False
        self._apply()
        if self.waiting or self.target is None:
            self.message.setText("⚠ " + (self.waiting or "Select what to pattern first."))
            self.info.setText("")
            return False
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        preview.recompute(self.doc)
        text = _plain(preview.failure(self.target))
        if text:
            self.message.setText("⚠ " + text)
            return False
        body = pattern.owner_body(self.target)
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        if body is not None:
            pattern.show_tip(body)
        log("%s done" % self.title)
        return True

    def reject(self):
        if self._closed:
            return True
        self._timer.stop()
        body = self.body
        self.cleanup()
        preview.end_transaction(self.doc, abort=True)
        preview.recompute(self.doc)
        self._close()
        if body is not None and pattern.alive(body):
            pattern.show_tip(body)
        return True

    def cleanup(self):
        self._closed = True
        self._unwatch()
        for guard in (self.escape, self.undo_guard, self.enter):
            try:
                guard.remove()
            except Exception:
                pass
        self._remove_handles()
        if self.dots is not None:
            self.dots.remove()
            self.dots = None
        if self.marks is not None:
            self.marks.remove()
            self.marks = None
        super().cleanup()


# FreeCAD's failure texts said the way a Fusion user needs them.
PLAIN = (
    ("Pattern length too small", "The distance must not be 0."),
    ("Pattern angle can't be null", "The total angle must not be 0."),
    ("At least one occurrence", "The quantity must be at least 1."),
    (
        "Only additive and subtractive",
        "These features cannot be repeated as features. Pick their faces instead "
        "(Pattern Type: Faces).",
    ),
    ("shape is empty", "There is nothing to repeat: the picked feature adds or removes nothing."),
)


def _plain(text):
    for needle, said in PLAIN:
        if needle.lower() in (text or "").lower():
            return said
    return text


# -- commands ---------------------------------------------------------------------------------------
def _selection_now():
    found = []
    for sel in Gui.Selection.getSelectionEx():
        for name in list(sel.SubElementNames) or [""]:
            obj, short = common.resolve(sel.Object, name)
            if obj is not None:
                found.append((obj, short))
    return found


def _selected_body(selection):
    for obj, _sub in selection:
        body = pattern.owner_body(obj)
        if body is not None:
            return body
    return None


def start(kind, panel_class=None):
    """Run a pattern command; things selected before it starts are its objects."""
    panel_class = panel_class or PatternPanel
    selection = _selection_now()
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    if doc is None:
        commands.tell("Open or start a design first.")
        return None
    body = _selected_body(selection)
    if body is not None and body is not commands.active_body():
        try:
            Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        except Exception as exc:
            warn("could not activate %s: %s" % (body.Label, exc))
    body = commands.find_body()
    tip = body.Tip if body is not None else None
    if tip is None or tip.Shape.isNull() or not tip.Shape.Solids:
        commands.tell(
            "%s needs a solid to repeat: make one first (Create Sketch, then Extrude)."
            % pattern.TITLES[kind]
        )
        return None
    panel = None
    try:
        panel = panel_class(doc, kind=kind, preselection=selection)
        Gui.Control.showDialog(panel)
    except Exception:
        if panel is not None and not panel._closed:
            try:
                panel.reject()
            except Exception:
                pass
        raise
    log("%s started" % pattern.TITLES[kind].lower())
    return panel


class _PatternCommand:
    kind = "rectangular"
    tip = ""

    def GetResources(self):
        return {
            "MenuText": pattern.TITLES[self.kind],
            "ToolTip": self.tip,
            "Pixmap": ui_icon_path(ICONS[self.kind]),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start(self.kind)
        except Exception as exc:
            warn("%s could not start: %s" % (pattern.TITLES[self.kind], exc))


class RectangularPatternCommand(_PatternCommand):
    kind = "rectangular"
    tip = (
        "Repeat features, faces or a body in rows and columns: quantity and distance in one "
        "or two directions, with a live preview and drag arrows"
    )


class CircularPatternCommand(_PatternCommand):
    kind = "circular"
    tip = "Repeat features, faces or a body around an axis: full circle, an angle or symmetric"


class PatternOnPathCommand(_PatternCommand):
    kind = "path"
    tip = "Repeat features, faces or a body along an edge or a sketch curve"


def edit(feature):
    """Open the pattern's dialog on an existing pattern (timeline double-click)."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        kind = pattern.kind_of(feature)
        if kind == "mirror":
            from .mirror_ui import MirrorPanel

            Gui.Control.showDialog(MirrorPanel(feature.Document, kind=kind, feature=feature))
        else:
            Gui.Control.showDialog(PatternPanel(feature.Document, kind=kind, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


class _DeleteWatch:
    """Deleting a pattern of bodies (the timeline's Delete) also deletes the bodies it made, as
    in Fusion. The copies are removed a moment later, as their own undo step: nothing is
    removed inside FreeCAD's delete."""

    def slotDeletedObject(self, obj):
        try:
            if pattern.is_body_pattern(obj):
                name = obj.Document.Name
                QtCore.QTimer.singleShot(0, lambda: _remove_orphans(name))
        except Exception:
            pass


def _remove_orphans(doc_name):
    try:
        if doc_name not in App.listDocuments():
            return
        doc = App.getDocument(doc_name)
        if not pattern.orphan_copies(doc):
            return  # an undo took the copies away with their pattern
        doc.openTransaction("Delete pattern copies")
        try:
            pattern.remove_orphans(doc)
        except Exception:
            doc.abortTransaction()
            raise
        doc.commitTransaction()
        preview.recompute(doc)
        log("copies of a deleted pattern removed")
    except Exception as exc:
        warn("could not remove the copies of a deleted pattern: %s" % exc)


_WATCH = {"observer": None}


def install_delete_watch():
    if _WATCH["observer"] is None:
        _WATCH["observer"] = _DeleteWatch()
        App.addDocumentObserver(_WATCH["observer"])


try:
    install_delete_watch()
except Exception as _exc:  # never let an import fail the commands
    warn("pattern delete watch unavailable: %s" % _exc)


COMMANDS = {
    "SciForge_RectangularPattern": RectangularPatternCommand,
    "SciForge_CircularPattern": CircularPatternCommand,
    "SciForge_PatternOnPath": PatternOnPathCommand,
}
EDITORS = {
    "PartDesign::LinearPattern": edit,
    "PartDesign::PolarPattern": edit,
    "SciForge::RectangularPattern": edit,
    "SciForge::CircularPattern": edit,
    "SciForge::PatternOnPath": edit,
}
