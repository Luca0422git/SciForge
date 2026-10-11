# SPDX-License-Identifier: LGPL-2.1-or-later
"""The CONSTRUCT commands (SciForge_Construct_<Key>) and their Fusion-style dialog.

Each command opens a dialog with one selection box per input (blue while it takes the
clicks; click a box to make it the one, x to clear it). A click on something that fits the
blue box fills it and the next box turns blue; a click on a picked item drops it again.
Only what the blue box can take lights up under the mouse. Planes, axes and points of the
origin are drawn to click while a box waits for one (big squares, long X/Y/Z lines, a dot
at the origin), like Create Sketch. What is selected before the command starts is taken.

As soon as the inputs are complete the construction is shown (a real plane, axis or point
in the design, inside the dialog's undo step) with Fusion's handle: a blue arrow for Offset
Plane, a blue ball turning about the line for Plane at Angle and Tangent Plane, a ball
sliding along the path for Plane / Point Along Path. Values take parameters and formulas.
Problems are shown in the dialog, which then stays open. OK keeps it (one undo step),
Cancel / Esc / Ctrl+Z leave the design as it was. Double-click it in the timeline to edit.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from . import bodypick, commands, construct, handles3d, hole_common, log, pickpanel, preview, warn
from . import ui_icon_path
from .compat import QtCore, QtWidgets
from .taskui import DistanceField

ICONS = {
    "OffsetPlane": "offset_plane",
    "PlaneAtAngle": "plane_angle",
    "TangentPlane": "tangent_plane",
    "Midplane": "midplane",
    "PlaneTwoEdges": "plane_two_edges",
    "PlaneThreePoints": "plane_three_points",
    "PlaneAtPoint": "tangent_plane",
    "PlaneAlongPath": "plane_along_path",
    "AxisCylinder": "axis",
    "AxisNormal": "axis",
    "AxisTwoPlanes": "axis",
    "AxisTwoPoints": "axis_two_points",
    "AxisEdge": "axis_edge",
}
ORIGIN_DOT = (0.95, 0.85, 0.35)
DISTANCE_TYPES = [("Proportional", "proportional"), ("Physical", "physical")]


def _safe(method):
    """Dialog reactions never let an exception out (it would print a traceback in the
    Report view): logged for SciForge's Diagnostics and shown in the dialog."""
    import functools

    @functools.wraps(method)
    def wrapper(self, *args):
        try:
            return method(self, *args)
        except construct.ConstructError as exc:
            self.say(str(exc))
        except Exception as exc:
            warn("%s: %s" % (getattr(self, "title", "Construct"), exc))
            try:
                self.say("⚠ %s" % exc)
            except Exception:
                pass
        return None

    return wrapper


def _resolve_gate(obj, sub):
    """(object, element) of what a gate is asked about: FreeCAD names the top object (a
    Body) and a path ("Pad.Face6", "Plane001.Plane")."""
    leaf, short = obj, sub or ""
    if "." in short:
        path, short = short.rsplit(".", 1)
        try:
            inner = obj.getSubObject(path + ".", retType=1)
        except Exception:
            inner = None
        if inner is not None:
            leaf = inner
    if leaf is not None and leaf.TypeId == "PartDesign::Body" and short:
        leaf = leaf.Tip
    return construct.normalize_pick(leaf, short)


class _Gate:
    """Only what the blue selection box can take lights up and can be picked."""

    def __init__(self, panel):
        self.panel = panel

    def allow(self, doc, obj, sub):
        try:
            panel = self.panel
            if panel is None or panel._closed or obj is None:
                return True
            leaf, short = _resolve_gate(obj, sub)
            return bool(panel.allow(leaf, short))
        except Exception:
            return False


def _depth_under_mouse(view, position):
    """Distance along the mouse ray to the part (or anything FreeCAD can pick) under the
    mouse, or None."""
    from .profile_pick import mouse_ray

    try:
        info = view.getObjectInfo(tuple(position))
    except Exception:
        return None
    if not info or not info.get("Object"):
        return None
    try:
        hit = App.Vector(info["x"], info["y"], info["z"])
    except Exception:
        return 0.0
    point, direction = mouse_ray(view, tuple(position))
    return (hit - point).dot(direction)


def _origin_planes_class():
    """sketch_ui.PlanePicker (the big origin squares) where a square in front of whatever
    else is under the mouse takes the click (the part, a construction plane...)."""
    from .profile_pick import ray_plane
    from .sketch_ui import HOVER, IDLE, PlanePicker

    class OriginPlanes(PlanePicker):
        def front_plane_at(self, position):
            best = None
            for role in self.objects:
                base, normal, u, v = self._frame(role)
                hit = ray_plane(self.view, position, base, normal)
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
            depth = _depth_under_mouse(self.view, position)
            if depth is not None and depth < best[1] - 1e-6:
                return None  # something is in front of the square: the click is its
            return best[0]

        def _moved(self, info):
            try:
                role = self.front_plane_at(info["Position"])
                material = self.materials.get(role)
                if material is not self.hovered:
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
                role = self.front_plane_at(info["Position"])
                if role is not None:
                    import time

                    self.last_click = time.time()
                    plane = self.objects[role]
                    QtCore.QTimer.singleShot(0, lambda: self.on_pick(plane))
            except Exception as exc:
                warn("plane pick: %s" % exc)

        def clicked_recently(self, seconds=0.6):
            import time

            return time.time() - getattr(self, "last_click", 0.0) < seconds

    return OriginPlanes


def _origin_features(body):
    found = {}
    if body is None:
        return found
    try:
        for feature in body.Origin.OriginFeatures:
            found[getattr(feature, "Role", "") or feature.Name] = feature
    except Exception:
        pass
    return found


def _size_of(body):
    try:
        box = body.Shape.BoundBox
        if body.Shape.isNull() or not body.Shape.Solids:
            return 50.0
        return max(10.0, box.DiagonalLength)
    except Exception:
        return 50.0


class ConstructPanel(bodypick.Tones, pickpanel.PickPanel):
    """One CONSTRUCT entry's dialog (see the module text)."""

    last = None

    def __init__(self, doc, key, datum=None, initial=()):
        self.key = key
        self.spec = construct.SPECS[key]
        self.title = self.spec["label"]
        self.icon = ICONS.get(key, "point")
        name = ("Edit %s" % datum.Label) if datum is not None else self.title
        super().__init__(doc, name)
        ConstructPanel.last = self
        self.datum = datum
        self.editing = datum is not None
        self.inputs = self.spec["inputs"]
        self.picks = [None] * len(self.inputs)
        self.active = 0
        self.values = construct.default_values(key)
        self.formulas = {}
        self.work_body = commands.find_body()
        self.handle = None
        self.handle_key = None
        self.overlays = {}
        self.error = ""
        self.boxes = []
        self._formula_inputs = []
        self._repick = None
        if datum is not None:
            info = construct.read(datum)
            if info is not None:
                _key, refs, points, values, formulas = info
                for i, ref in enumerate(refs[: len(self.picks)]):
                    point = points[i] if i < len(points) else None
                    self.picks[i] = (ref[0], ref[1], point)
                self.values.update(values)
                self.formulas.update(formulas)
            self.work_body = construct.owner_body(datum) or self.work_body
        self._build()
        if datum is None:
            for obj, short, point in initial:
                self._place(obj, short, point, initial=True)
        self.active = self._first_empty()
        if self.active is None:
            self.active = len(self.inputs) - 1
        self.start_picking()
        self._install_gate()
        self._show_boxes()
        self._update_overlays()
        self._prompt()
        self._apply_now()

    # -- the dialog ------------------------------------------------------------------------
    def _build(self):
        self.message.setObjectName("SciForgeConstruct_message")
        for i, spec in enumerate(self.inputs):
            empty = "Select" if not spec["optional"] else "Select (optional)"
            box = hole_common.SelectionField(self, i, empty)
            box.button.setObjectName("SciForgeConstruct_input%d" % i)
            box.button.setToolTip("Click %s in the design" % spec["hint"])
            box.clear.setObjectName("SciForgeConstruct_clear%d" % i)
            self.boxes.append(box)
            self.layout.addRow(spec["name"], box.widget)
        self.distance = self.angle = self.fraction = self.path_type = None
        self.distance_stack = None
        kind = self.spec["value"]
        if kind == "distance":
            self.distance = DistanceField(self.values["distance"], on_change=self._typed_distance)
            self.distance.widget.setObjectName("SciForgeConstruct_distance")
            self.layout.addRow("Distance", self.distance.widget)
            self._formula_inputs.append(preview.FormulaInput(self, "distance", self.distance))
            if self.formulas.get("distance"):
                self._show_formula(self.distance, self.formulas["distance"])
        elif kind == "angle":
            self.angle = DistanceField(
                self.values["angle"], unit="deg", on_change=self._typed_angle
            )
            self.angle.widget.setObjectName("SciForgeConstruct_angle")
            self.layout.addRow("Angle", self.angle.widget)
            self._formula_inputs.append(preview.FormulaInput(self, "angle", self.angle))
            if self.formulas.get("angle"):
                self._show_formula(self.angle, self.formulas["angle"])
        elif kind == "path":
            self.path_type = pickpanel.combo(DISTANCE_TYPES, self.values["distance_type"])
            self.path_type.setObjectName("SciForgeConstruct_distance_type")
            self.path_type.currentIndexChanged.connect(self._type_changed)
            self.layout.addRow("Distance Type", self.path_type)
            self.fraction = QtWidgets.QDoubleSpinBox()
            self.fraction.setObjectName("SciForgeConstruct_fraction")
            self.fraction.setRange(0.0, 1.0)
            self.fraction.setDecimals(3)
            self.fraction.setSingleStep(0.05)
            self.fraction.setKeyboardTracking(False)
            self.fraction.setValue(self.values["fraction"])
            self.fraction.valueChanged.connect(self._typed_fraction)
            self.distance = DistanceField(self.values["distance"], on_change=self._typed_distance)
            self.distance.widget.setObjectName("SciForgeConstruct_distance")
            self.distance_stack = QtWidgets.QStackedWidget()
            self.distance_stack.addWidget(self.fraction)
            self.distance_stack.addWidget(self.distance.widget)
            height = max(
                self.fraction.sizeHint().height(), self.distance.widget.sizeHint().height()
            )
            self.distance_stack.setFixedHeight(height)
            self.layout.addRow("Distance", self.distance_stack)
            self._formula_inputs.append(preview.FormulaInput(self, "distance", self.distance))
            self._show_path_type()
        self.finish_layout()

    def _show_formula(self, field, text):
        try:
            from .compat import QtWidgets as W

            edit = field.widget.findChild(W.QLineEdit)
            if edit is not None:
                edit.setToolTip("Formula: %s" % text)
        except Exception:
            pass

    def _show_path_type(self):
        if self.distance_stack is None:
            return
        physical = self.values["distance_type"] == "physical"
        self.distance_stack.setCurrentIndex(1 if physical else 0)

    def _show_boxes(self):
        for i, box in enumerate(self.boxes):
            pick = self.picks[i]
            box.set_text(construct.describe(pick[0], pick[1]) if pick else "")
            box.set_active(i == self.active and not self._closed)

    def _prompt(self):
        if self.error:
            self.say(self.error)
            return
        if not self._complete():
            spec = self.inputs[self.active] if self.active is not None else None
            if spec is not None:
                self.hint("Click %s." % spec["hint"])
            return
        self.hint("")

    def _complete(self):
        return all(
            self.picks[i] is not None for i, s in enumerate(self.inputs) if not s["optional"]
        )

    def _first_empty(self):
        for i, pick in enumerate(self.picks):
            if pick is None and not self.inputs[i]["optional"]:
                return i
        for i, pick in enumerate(self.picks):
            if pick is None:
                return i
        return None

    def refs(self):
        refs, points = [], []
        for pick in self.picks:
            if pick is None:
                continue
            refs.append((pick[0], pick[1]))
            points.append(pick[2])
        return refs, points

    # -- selection boxes (hole_common.SelectionField calls these) --------------------------
    @_safe
    def activate(self, index):
        self.active = int(index)
        self._repick = self.active
        self._show_boxes()
        self._update_overlays()
        self._prompt()

    @_safe
    def clear_field(self, index):
        index = int(index)
        self.picks[index] = None
        self.active = index
        self.error = ""
        self._sync()
        self._show_boxes()
        self._update_overlays()
        self.schedule()

    # -- picking -----------------------------------------------------------------------------
    def _install_gate(self):
        """PickPanel's gate only sees the last part of FreeCAD's path; a construction plane
        inside a body is reported as the body plus "Plane001.Plane": resolve it."""
        try:
            if self.gate is not None:
                hole_common.remove_gate(self.gate)
            self.gate = _Gate(self)
            Gui.Selection.addSelectionGate(self.gate)
        except Exception as exc:
            warn("%s: selection filter unavailable: %s" % (self.title, exc))
            self.gate = None

    def _own(self, obj):
        """The preview (or the construction being edited) and its helper: never a pick."""
        if obj is None or self.datum is None or not construct.alive(self.datum):
            return False
        if obj is self.datum:
            return True
        helper = construct.helper_of(self.datum)
        return helper is not None and obj is helper

    def _is_pick(self, obj, short):
        for pick in self.picks:
            if pick is not None and pick[0] is obj and pick[1] == short:
                return True
        return False

    def allow(self, obj, short):
        obj, short = construct.normalize_pick(obj, short)
        if obj is None or self._own(obj):
            return False
        if self._is_pick(obj, short):
            return True
        if self.active is None:
            return False
        if construct.is_helper(obj) or obj.TypeId == "PartDesign::Body":
            return False
        return construct.fits(self.key, self.active, obj, short)

    def shown(self):
        out = []
        for pick in self.picks:
            if pick is None or not construct.alive(pick[0]):
                continue
            out.append((pick[0], [pick[1]] if pick[1] else []))
        return out

    def _overlay_busy(self):
        for overlay in self.overlays.values():
            recent = getattr(overlay, "clicked_recently", None)
            if recent is not None and recent():
                return True
        return False

    def picks_changed(self, added, dropped):
        if self.handle is not None and self.handle.busy():
            return False  # the press was on the handle, not a pick
        changed = False
        for obj, short, _point in dropped:
            obj, short = construct.normalize_pick(obj, short)
            for i, pick in enumerate(self.picks):
                if pick is not None and pick[0] is obj and pick[1] == short:
                    self.picks[i] = None
                    self.active = i
                    changed = True
        if self._overlay_busy():
            added = []  # FreeCAD's selection of what is behind the origin square / axis
        for obj, short, point in added:
            if self._place(obj, short, point):
                changed = True
        if changed:
            self.error = ""
            self._repick = None
            self._show_boxes()
            self._update_overlays()
        return changed

    def _place(self, obj, short, point, initial=False):
        """Put a pick in the blue box (or the first empty box it fits). True if placed."""
        obj, short = construct.normalize_pick(obj, short)
        if obj is None or self._own(obj) or self._is_pick(obj, short):
            return False
        order = []
        if self.active is not None:
            order.append(self.active)
        order += [i for i, p in enumerate(self.picks) if p is None and i not in order]
        for i in order:
            fitted = construct.as_input(self.key, i, obj, short)
            if fitted is None:
                continue
            if self.picks[i] is not None and i != self.active:
                continue
            if self._is_pick(*fitted):
                return False
            point = App.Vector(point) if point is not None else None
            self.picks[i] = (fitted[0], fitted[1], point)
            following = self._first_empty()
            self.active = following if following is not None else i
            return True
        if not initial:
            commands.tell("That does not fit %s: pick %s." % (self.title, self._wanted()))
        return False

    def _wanted(self):
        if self.active is None:
            return "something else"
        return self.inputs[self.active]["hint"]

    @_safe
    def _overlay_pick(self, obj):
        if self._closed:
            return
        if self._place(obj, "", None):
            self.error = ""
            self._repick = None
            self._sync()
            self._show_boxes()
            self._update_overlays()
            self.schedule()

    # -- origin planes, axes and point to click --------------------------------------------
    def _update_overlays(self):
        """The origin planes / axes / point are drawn while the blue box waits for a pick
        (empty, or clicked to pick it again), like Fusion offers them then."""
        kinds = set()
        if self.active is not None and not self._closed:
            if self.picks[self.active] is None or self._repick == self.active:
                kinds = set(self.inputs[self.active]["kinds"])
        want = {
            "planes": "plane" in kinds,
            "axes": "line" in kinds,
            "point": "point" in kinds,
        }
        for name, on in want.items():
            if on and name not in self.overlays:
                try:
                    self.overlays[name] = self._make_overlay(name)
                except Exception as exc:
                    warn("%s: origin %s unavailable: %s" % (self.title, name, exc))
            elif not on and name in self.overlays:
                overlay = self.overlays.pop(name)
                try:
                    overlay.remove()
                except Exception:
                    pass

    def _make_overlay(self, name):
        view = Gui.ActiveDocument.ActiveView
        body = self.work_body or commands.find_body()
        if name == "planes":
            cls = _origin_planes_class()
            return cls(view, body, self._overlay_pick)
        origin = _origin_features(body)
        place = body.getGlobalPlacement() if body is not None else App.Placement()
        size = _size_of(body) * 0.75
        if name == "axes":
            from .revolve_ui import AxisPicker

            lines = []
            for role, key in (("X_Axis", "X"), ("Y_Axis", "Y"), ("Z_Axis", "Z")):
                feature = origin.get(role)
                if feature is None:
                    continue
                direction = feature.getGlobalPlacement().Rotation.multVec(App.Vector(1, 0, 0))
                lines.append(
                    (feature, key, place.Base - direction * size, place.Base + direction * size)
                )
            return AxisPicker(view, lines, self._overlay_pick, competing=self._something_under)
        feature = origin.get("Origin")
        dots = [(feature, place.Base, ORIGIN_DOT)] if feature is not None else []
        return handles3d.PointDots(view, dots, self._overlay_pick, size=size * 0.04)

    def _something_under(self, position):
        try:
            info = Gui.ActiveDocument.ActiveView.getObjectInfo(tuple(position))
            return bool(info and info.get("Object"))
        except Exception:
            return False

    def _remove_overlays(self):
        for overlay in self.overlays.values():
            try:
                overlay.remove()
            except Exception:
                pass
        self.overlays = {}

    # -- values ------------------------------------------------------------------------------
    @_safe
    def _typed_distance(self, value):
        self.values["distance"] = float(value)
        self.formulas.pop("distance", None)
        if self.handle_key == "distance" and self.handle is not None:
            self.handle.set_value(value)
        self._path_moved()
        self.schedule()

    @_safe
    def _typed_angle(self, value):
        self.values["angle"] = float(value)
        self.formulas.pop("angle", None)
        if self.handle_key == "angle" and self.handle is not None:
            self.handle.set_angle(value)
        self.schedule()

    @_safe
    def _typed_fraction(self, value):
        self.values["fraction"] = float(value)
        self._path_moved()
        self.schedule()

    @_safe
    def _type_changed(self, *_):
        kind = self.path_type.currentData()
        if kind == self.values["distance_type"]:
            return
        edge = self._path_edge()
        length = edge.Length if edge is not None else 0.0
        if kind == "physical":
            self.values["distance"] = self.values["fraction"] * length
            self.distance.set_value(self.values["distance"])
        elif length > 0:
            self.values["fraction"] = max(0.0, min(1.0, self.values["distance"] / length))
            self.fraction.blockSignals(True)
            self.fraction.setValue(self.values["fraction"])
            self.fraction.blockSignals(False)
        self.values["distance_type"] = kind
        self.formulas.pop("distance", None)
        self._show_path_type()
        self.schedule()

    # preview.FormulaInput calls these
    def formula_typed(self, key, text, value):
        self.formulas[key] = text
        self.values[key] = float(value)
        if self.handle is not None and self.handle_key == key:
            if key == "angle":
                self.handle.set_angle(value)
            else:
                self.handle.set_value(value)
        self.schedule()

    def formula_cleared(self, key):
        if self.formulas.pop(key, None) is not None:
            self.schedule()

    def formula_failed(self, key, message):
        self.say(message)

    # -- handles -----------------------------------------------------------------------------
    def _remove_handle(self):
        if self.handle is not None:
            try:
                self.handle.remove()
            except Exception:
                pass
        self.handle = None
        self.handle_key = None

    def _handle_size(self):
        return max(4.0, 0.2 * _size_of(self.work_body))

    def _update_handle(self):
        """Make (or move) the blue handle for the inputs picked now."""
        kind = self.spec["value"]
        if kind is None or not self._complete() or self.error:
            self._remove_handle()
            return
        refs, points = self.refs()
        signature = (kind, tuple((r[0].Name, r[1]) for r in refs))
        if self.handle is not None and getattr(self, "_handle_for", None) == signature:
            return
        self._remove_handle()
        self._handle_for = signature
        size = self._handle_size()
        if self.key == "OffsetPlane":
            origin, normal = construct.plane_of(refs[0])
            self.handle = handles3d.LinearHandle(
                origin,
                normal,
                self.values["distance"],
                size,
                on_drag=self._dragged_distance,
                on_release=self._dragged_distance,
            )
            self.handle_key = "distance"
        elif kind == "angle":
            from .revolve_ui import AngleHandle

            centre, axis, zero, radius = self._angle_frame(refs, points)
            self.handle = AngleHandle(
                centre,
                axis,
                zero,
                radius,
                self.values["angle"],
                size * 0.6,
                on_drag=self._dragged_angle,
                on_release=self._dragged_angle,
            )
            self.handle_key = "angle"
        elif kind == "path":
            edge = self._path_edge()
            if edge is None:
                return
            u = construct.path_parameter(edge, self.values)
            self.handle = handles3d.PathHandle(
                edge, u, size, on_drag=self._dragged_path, on_release=self._dragged_path
            )
            self.handle_key = "path"

    def _angle_frame(self, refs, points):
        """(centre, axis, zero direction, radius) of the angle handle: the ball stays in the
        plane (Plane at Angle) or just outside the round face (Tangent Plane)."""
        if self.key == "PlaneAtAngle":
            p, d, length = construct.line_of(refs[0])
            if length:
                p = p + d * (length / 2.0)
            n0 = construct.zero_normal(refs[0], d)
            zero = n0.cross(d)
            radius = max(self._handle_size() * 2.0, (length or 0.0) * 0.35)
            return p, d, zero, radius
        face = construct.face_of(refs[0])
        centre, axis, kind = construct.revolution_of(refs[0])
        u, v = construct._face_point(face, points[0] if points else None)
        p0 = face.valueAt(u, v)
        foot = centre + axis * (p0 - centre).dot(axis)
        radial = p0 - foot
        if radial.Length < 1e-9:
            radial = construct.any_perpendicular(axis)
        r = radial.Length
        radial.normalize()
        return foot, axis, radial, r + self._handle_size() * 1.2

    def _path_edge(self):
        refs, _points = self.refs()
        if not refs:
            return None
        try:
            return construct.edge_of(refs[0])
        except construct.ConstructError:
            return None

    @_safe
    def _dragged_distance(self, value):
        value = round(float(value), 3)
        self.values["distance"] = value
        self.formulas.pop("distance", None)
        if self.distance is not None:
            self.distance.set_value(value)
        self.schedule()

    @_safe
    def _dragged_angle(self, value):
        value = round(float(value), 2)
        self.values["angle"] = value
        self.formulas.pop("angle", None)
        if self.angle is not None:
            self.angle.set_value(value)
        self.schedule()

    @_safe
    def _dragged_path(self, parameter):
        edge = self._path_edge()
        if edge is None:
            return
        first = edge.FirstParameter
        try:
            s = edge.Curve.length(first, float(parameter)) if parameter > first else 0.0
        except Exception:
            s = 0.0
        length = edge.Length
        if self.values["distance_type"] == "physical":
            self.values["distance"] = round(s, 3)
            self.distance.set_value(self.values["distance"])
            self.formulas.pop("distance", None)
        else:
            self.values["fraction"] = round(s / length, 4) if length > 0 else 0.0
            self.fraction.blockSignals(True)
            self.fraction.setValue(self.values["fraction"])
            self.fraction.blockSignals(False)
        self.schedule()

    def _path_moved(self):
        if self.handle_key != "path" or self.handle is None:
            return
        edge = self._path_edge()
        if edge is None:
            return
        try:
            self.handle.set_value(construct.path_parameter(edge, self.values))
        except construct.ConstructError:
            pass

    # -- the construction itself -------------------------------------------------------------
    def schedule(self):
        if not self._closed:
            self._timer.start()

    def _preview(self):
        self._apply_now()

    def _apply_now(self):
        """Build or update the construction for what the dialog holds now."""
        if self._closed:
            return
        if self.doc.Recomputing:
            QtCore.QTimer.singleShot(200, self.schedule)
            return
        refs, points = self.refs()
        if not self._complete():
            self.error = ""
            self._remove_handle()
            if self.datum is not None and not self.editing and construct.alive(self.datum):
                self._looks.restore()
                construct.delete(self.datum)
                self.datum = None
                preview.recompute(self.doc)
            self._prompt()
            return
        try:
            construct.compute(self.key, refs, points, self.values)
        except construct.ConstructError as exc:
            self.error = str(exc)
            self._remove_handle()
            self._prompt()
            return
        self.error = ""
        if self.datum is None or not construct.alive(self.datum):
            self.datum = construct.make(self.work_body, self.key, refs, self.values, points)
            if self.formulas:
                construct.update(self.datum, self.key, refs, self.values, points, self.formulas)
        else:
            construct.update(self.datum, self.key, refs, self.values, points, self.formulas)
        preview.recompute(self.doc)
        self._not_pickable()
        problem = construct.failure(self.datum)
        if problem:
            self.error = problem
        self._update_handle()
        self._prompt()

    def _not_pickable(self):
        """The construction being made is drawn over the part: clicks go through it to what
        is behind (Fusion's preview never takes a click)."""
        if self.datum is None or self.datum.ViewObject is None:
            return
        tag = "unpickable:" + self.datum.Name
        if self._looks.done(tag):
            return
        try:
            for node in pickpanel.nodes(self.datum.ViewObject.RootNode, "SoPickStyle"):
                self._looks.set(node, "style", node.UNPICKABLE)
        except Exception as exc:
            warn("%s: preview stays clickable: %s" % (self.title, exc))

    # -- OK / Cancel -------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            self._apply_now()
            if not self._complete():
                self._prompt()
                return False
            if self.error or self.datum is None:
                self.say(self.error or "Select %s." % self._wanted())
                return False
            problem = construct.failure(self.datum)
            if problem:
                self.say(problem)
                return False
            datum = self.datum
            done = self.finish_ok()
            log("%s: %s made" % (self.title, datum.Label))
            return done
        except Exception as exc:
            warn("%s OK: %s" % (self.title, exc))
            self.say("⚠ %s" % exc)
            return False

    def feature(self):
        return self.datum

    def cleanup(self):
        self._remove_handle()
        self._remove_overlays()
        for fi in self._formula_inputs:
            fi.panel = None
        self._formula_inputs = []
        super().cleanup()
        self._show_boxes()


# -- commands -----------------------------------------------------------------------------------
def start(key, picks=None):
    """Open the dialog of CONSTRUCT entry `key` (picks: what was selected, or the
    selection now)."""
    if picks is None:
        picks = hole_common.picks()
    if not commands.finish_open_dialog():
        return None
    if App.ActiveDocument is None:
        App.newDocument("Design")
    commands.ensure_body()
    panel = ConstructPanel(App.ActiveDocument, key, initial=picks)
    Gui.Control.showDialog(panel)
    log("%s started" % panel.title)
    return panel


def edit(datum):
    """Timeline / browser double-click on a construction: its own dialog again. A datum
    SciForge's CONSTRUCT did not make opens FreeCAD's attachment panel."""
    info = construct.read(datum)
    if info is None:
        Gui.ActiveDocument.setEdit(datum.Name)
        return None
    body = construct.owner_body(datum)
    if body is not None:
        pickpanel.activate(body)
    panel = ConstructPanel(datum.Document, info[0], datum=datum)
    Gui.Control.showDialog(panel)
    log("editing %s" % datum.Label)
    return panel


def _command_class(key):
    label = construct.SPECS[key]["label"]

    class ConstructCommand:
        def GetResources(self):
            return {
                "MenuText": label,
                "ToolTip": label + " (select geometry before or after)",
                "Pixmap": ui_icon_path(ICONS.get(key, "point")),
            }

        def IsActive(self):
            return True

        def Activated(self):
            try:
                start(key)
            except Exception as exc:
                warn("%s failed to start: %s" % (label, exc))

    return ConstructCommand


def command_classes():
    return {"SciForge_Construct_" + key: _command_class(key) for key in construct.SPECS}


COMMANDS = command_classes()
EDITORS = {"PartDesign::Plane": edit, "PartDesign::Line": edit, "PartDesign::Point": edit}
