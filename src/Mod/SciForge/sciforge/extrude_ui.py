# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude command (E) with Fusion's dialog.

Profiles: click inside closed sketch areas (they are shaded blue and light up under
the mouse; a circle inside a rectangle gives the ring and the disc separately) or on
flat faces of the part. Click more areas to add them, click a picked one again to
drop it. What is selected before pressing E is taken at once: sketch areas clicked
after Finish Sketch or inside the open sketch, flat faces, a whole sketch (its areas);
with nothing selected, the one area of a sketch just finished.

The fields follow Fusion's Extrude: Start (Profile Plane / Offset / Object), Direction
(One Side / Two Sides / Symmetric), Extent (Distance / To Object / All), Taper Angle,
Operation (Join / Cut / Intersect / New Body). The blue arrows in the 3D view set the
distances (each with a value box next to it, to read or type the value), the blue disc
the taper angle. Dragging into the part switches to Cut, as Fusion does, unless you
picked the operation yourself; a cut shows in red while the dialog is open. A new
extrude starts at 0 and shows nothing until you drag or type; the profile's sketch stays
in view until OK. Problems are shown in the dialog, which then stays open.
"""
import math
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, cut_preview, drag_guard, extrude, log, preview, profile_pick, taskui
from . import bodies, extrude_bodies, ui_icon_path, warn
from . import extrude_bodies_core as bodies_core
from .compat import QtCore, QtWidgets
from .taskui import ArrowDragger, ArrowValueBox, DistanceField, Panel

ZERO_HINT = "Drag the arrow or type a distance."

START_LABELS = [("Profile Plane", "profile"), ("Offset", "offset"), ("Object", "object")]
DIRECTION_LABELS = [
    ("One Side", "one_side"),
    ("Two Sides", "two_sides"),
    ("Symmetric", "symmetric"),
]
EXTENT_LABELS = [("Distance", "distance"), ("To Object", "to_object"), ("All", "all")]
MEASUREMENT_LABELS = [("Half Length", "half"), ("Whole Length", "whole")]
OPERATION_LABELS = [
    ("Join", "join"),
    ("Cut", "cut"),
    ("Intersect", "intersect"),
    ("New Body", "new_body"),
]
ACTIVE_STYLE = "QPushButton { background: #1f6fbf; color: white; border: 1px solid #5aa0e6; }"
# An arrow drag rebuilds the preview many times a second: when testing the bodies in the
# way took longer than this (seconds; a detailed part), a drag reuses the last answer.
DRAG_TEST_BUDGET = 0.05


def _combo(pairs, current):
    box = QtWidgets.QComboBox()
    for label, value in pairs:
        box.addItem(label, value)
    values = [v for _, v in pairs]
    box.setCurrentIndex(values.index(current) if current in values else 0)
    return box


def _set_combo(box, value):
    for i in range(box.count()):
        if box.itemData(i) == value:
            box.setCurrentIndex(i)
            return


class SelectionField:
    """Fusion's selection box: shows what is picked, is blue while it takes the clicks in
    the 3D view (click it to make it the one), and has an x to clear it."""

    def __init__(self, panel, name, empty):
        self.panel = panel
        self.name = name
        self.empty = empty
        self.widget = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(self.widget)
        row.setContentsMargins(0, 0, 0, 0)
        self.button = QtWidgets.QPushButton(empty)
        self.button.setCheckable(True)
        self.button.clicked.connect(self._clicked)
        self.clear = QtWidgets.QToolButton()
        self.clear.setText("✕")
        self.clear.setToolTip("Clear")
        self.clear.clicked.connect(self._cleared)
        row.addWidget(self.button, 1)
        row.addWidget(self.clear)

    def _clicked(self, *_):
        try:
            self.panel.activate(self.name)
        except Exception as exc:
            warn("extrude field: %s" % exc)

    def _cleared(self, *_):
        try:
            self.panel.clear_field(self.name)
        except Exception as exc:
            warn("extrude field: %s" % exc)

    def set_active(self, active):
        self.button.setChecked(active)
        self.button.setStyleSheet(ACTIVE_STYLE if active else "")

    def set_text(self, text):
        self.button.setText(text or self.empty)


class AngleDragger:
    """Fusion's taper handle: a short curved blue arrow at the end of the extrusion that
    turns about the profile's edge (`pivot`, axis `axis`). At angle 0 it sits `radius`
    along `zero` (the extrusion direction); positive angles turn it to axis x zero, the
    outward side. Watched with a Qt timer like taskui.ArrowDragger (Coin's dragger
    callbacks run Python without its lock and crashed FreeCAD)."""

    POLL_MS = 30

    def __init__(self, pivot, axis, zero, angle, radius, width, on_drag=None, on_release=None):
        from pivy import coin

        self.view = Gui.ActiveDocument.ActiveView
        self.pivot = App.Vector(pivot)
        self.axis = App.Vector(axis).normalize()
        self.zero = App.Vector(zero).normalize()
        self.radius = radius
        self.root = coin.SoSeparator()
        place = coin.SoTransform()
        place.translation.setValue(pivot.x, pivot.y, pivot.z)
        x = self.zero
        z = self.axis
        y = z.cross(x)
        matrix = App.Matrix(x.x, y.x, z.x, 0, x.y, y.y, z.y, 0, x.z, y.z, z.z, 0, 0, 0, 0, 1)
        place.rotation.setValue(*App.Placement(matrix).Rotation.Q)
        self.dragger = coin.SoRotateDiscDragger()
        self.dragger.setPart("rotator", self._arc(coin, radius, width, (0.30, 0.62, 0.95)))
        self.dragger.setPart("rotatorActive", self._arc(coin, radius, width, (0.55, 0.80, 1.0)))
        self.dragger.setPart("feedback", coin.SoSeparator())
        self.dragger.setPart("feedbackActive", coin.SoSeparator())
        self.root.addChild(place)
        self.root.addChild(self.dragger)
        self.set_angle(angle)
        self.on_drag = on_drag
        self.on_release = on_release
        self._last = self.angle()
        self._was_active = False
        self.view.getSceneGraph().addChild(self.root)
        self._timer = QtCore.QTimer()
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    @staticmethod
    def _arc(coin, radius, width, color):
        """A flat curved band with an arrow head at each end, around local +X."""
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(color[0] * 0.5, color[1] * 0.5, color[2] * 0.5)
        sep.addChild(material)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.COUNTERCLOCKWISE
        hints.shapeType = coin.SoShapeHints.UNKNOWN_SHAPE_TYPE  # lit from both sides
        sep.addChild(hints)
        span = min(0.3, 1.6 * width / max(radius, 1e-6))  # half the arc, radians
        steps = 12
        points, index = [], []
        r_in, r_out = radius - width * 0.25, radius + width * 0.25
        for i in range(steps + 1):
            a = -span + 2.0 * span * i / steps
            points.append((r_in * math.cos(a), r_in * math.sin(a), 0.0))
            points.append((r_out * math.cos(a), r_out * math.sin(a), 0.0))
        for i in range(steps):
            a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2
            index += [a, b, c, -1, a, c, d, -1]
        for sign in (-1.0, 1.0):  # arrow heads, pointing along the arc
            tip_angle = sign * (span + 1.2 * width / max(radius, 1e-6))
            base_angle = sign * span
            first = len(points)
            points.append(
                (
                    (radius - width * 0.6) * math.cos(base_angle),
                    (radius - width * 0.6) * math.sin(base_angle),
                    0.0,
                )
            )
            points.append(
                (
                    (radius + width * 0.6) * math.cos(base_angle),
                    (radius + width * 0.6) * math.sin(base_angle),
                    0.0,
                )
            )
            points.append((radius * math.cos(tip_angle), radius * math.sin(tip_angle), 0.0))
            index += [first, first + 1, first + 2, -1]
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), points)
        faces = coin.SoIndexedFaceSet()
        faces.coordIndex.setValues(0, len(index), index)
        sep.addChild(coords)
        sep.addChild(faces)
        return sep

    def screen_points(self, degrees):
        """(where the handle is now, where it is at `degrees`) in 3D, for tests and hints."""
        out = self.zero.cross(self.axis) * -1.0  # local +Y: the outward side

        def at(angle):
            a = math.radians(angle)
            return self.pivot + (self.zero * math.cos(a) + out * math.sin(a)) * self.radius

        return at(self.angle()), at(degrees)

    def angle(self):
        q = self.dragger.rotation.getValue().getValue()  # (x, y, z, w) about local z
        value = math.degrees(2.0 * math.atan2(q[2], q[3]))
        if value > 180.0:
            value -= 360.0
        if value < -180.0:
            value += 360.0
        return value

    def set_angle(self, degrees):
        from pivy import coin

        half = math.radians(degrees) / 2.0
        self.dragger.rotation.setValue(coin.SbRotation(0, 0, math.sin(half), math.cos(half)))
        self._last = degrees

    def _poll(self):
        try:
            active = drag_guard.guard_coin_dragger(self.dragger, self.root, self.view)
            value = self.angle()
            if abs(value - self._last) > 1e-6:
                self._last = value
                if self.on_drag:
                    self.on_drag(value)
            if self._was_active and not active and self.on_release:
                self.on_release(value)
            self._was_active = active
        except Exception as exc:
            warn("taper drag: %s" % exc)

    def remove(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            drag_guard.before_remove(self.dragger, self.root, self.view)
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


class ViewProviderExtrude:
    """View provider of the Intersect extrude (a SciForge feature)."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("extrude")

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


def restore_view_providers(doc):
    for obj in doc.Objects:
        if extrude.is_intersect(obj) and obj.ViewObject is not None:
            if not isinstance(getattr(obj.ViewObject, "Proxy", None), ViewProviderExtrude):
                ViewProviderExtrude(obj.ViewObject)


class FollowerViewProvider:
    """View provider of a multi-body extrude's hidden step in another body
    (extrude_bodies.py): it is never in the timeline or the browser, and a double-click
    that reaches it anyway edits the extrude it follows. Saved in files as
    "sciforge.extrude_ui.FollowerViewProvider": keep the name."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("extrude")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        self._edit(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        self._edit(vobj.Object)
        return True

    @staticmethod
    def _edit(obj):
        try:
            lead = extrude_bodies.lead_of(obj)
            if lead is not None:
                QtCore.QTimer.singleShot(0, lambda: edit(lead))
        except Exception as exc:
            warn("could not edit the extrude of %s: %s" % (obj.Label, exc))

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


# -- what is selected before the command starts ---------------------------------------------
def _used_profiles(body):
    """Names of sketches already used by an extrude (kept for older callers)."""
    return profile_pick.used_sketches(body.Document) if body is not None else set()


def selected_profiles(body):
    """Profiles from the selection: a sketch (whole sketch), a sketch area, or flat faces."""
    used = _used_profiles(body)
    found = []
    for obj, short in profile_pick.picks():
        if extrude.is_sketch(obj):
            if short.startswith("InternalFace"):
                found.append((obj, short))
                continue
            if short.startswith(("Edge", "Vertex")):
                continue
            # A sketch already extruded and hidden is a leftover selection, not a pick.
            try:
                hidden = not obj.ViewObject.Visibility
            except Exception:
                hidden = False
            if obj.Name in used and hidden:
                continue
            # A selected sketch (the whole sketch, e.g. in the browser) is its profiles: one
            # area is that profile; with several, the sketch's areas as FreeCAD extrudes
            # the whole sketch (a plate keeps its holes). Each one can then be dropped, or
            # a hole's disc added, by clicking it.
            try:
                areas = extrude.regions(obj)
            except Exception:
                areas = []
            if len(areas) == 1:
                found.append((obj, areas[0][0]))
            elif areas:
                try:
                    whole = [p for p in extrude.expand_whole([(obj, "")]) if p[1]]
                except Exception:
                    whole = []
                found.extend(whole or [(obj, name) for name, _face in areas])
        elif short.startswith("Face"):
            try:
                face = obj.Shape.getElement(short)
            except Exception:
                continue
            if face.Surface.TypeId == "Part::GeomPlane":
                found.append((obj, short))
    return found


def selected_profile(body):
    """First-version name: the first selected profile, or None."""
    found = selected_profiles(body)
    return found[0] if found else None


def single_region(sketch):
    """[(sketch, area)] when the sketch has exactly one closed area, else []."""
    try:
        found = extrude.regions(sketch)
    except Exception:
        return []
    return [(sketch, found[0][0])] if len(found) == 1 else []


def newest_single_region(body):
    """The only area of the newest sketch no extrude uses yet (Fusion picks a sketch's
    single profile by itself), or None."""
    if body is None:
        return None
    used = _used_profiles(body)
    for obj in reversed(body.Group):
        if extrude.is_sketch(obj) and obj.Name not in used:
            try:
                found = extrude.regions(obj)
            except Exception:
                return None
            return (obj, found[0][0]) if len(found) == 1 else None
    return None


# -- the dialog -------------------------------------------------------------------------------
class ExtrudePanel(Panel):
    title = "Extrude"
    icon = "extrude"
    last = None
    auto_pick = True  # take the single area of a sketch just finished, like Fusion

    def __init__(self, doc, feature=None, profiles=None, sketch=None):
        super().__init__(doc, "Extrude" if feature is None else "Edit Extrude")
        ExtrudePanel.last = self
        # The sketch that was open when E was pressed: its areas are the profiles, also
        # when an extrude already uses it (Fusion extrudes the sketch you are in).
        self.from_sketch = sketch
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.target = feature
        self.editing = feature is not None
        self.body = commands.find_body() if feature is None else extrude.owner_body(feature)
        self.profiles = []
        self.options = dict(extrude.DEFAULTS)
        self.options["measurement"] = "half"  # Fusion's default for Symmetric
        if feature is None:
            # Fusion's Extrude starts at 0: nothing pops out before you drag the arrow or
            # type a distance (Luca, R5). extrude.DEFAULTS keeps 10 for scripts.
            self.options["distance"] = 0.0
            self.options["distance2"] = 0.0
        self.user_picked_operation = feature is not None
        self.error = ""
        self.waiting = ""  # the selection box that waits for a click, said as a hint
        self.formula_error = ""  # a formula typed in a field that is no value
        self.options["expressions"] = {}  # formulas typed in value fields (FormulaInput)
        self.dirty = False
        self._geometry_changed = False
        self.active = "profiles"
        self.draggers = {}
        self.dragger = None  # the distance arrow (tests and older callers)
        self.picker = None
        self.observer = None
        self._quiet = False
        self.value_boxes = {}  # the value box next to each arrow ({"distance": box, ...})
        self.cut_view = None  # the red cut preview (cut_preview.CutPreview)
        self._init_bodies()
        if feature is not None:
            try:
                self.profiles, read = extrude.read(feature)
                self._read_bodies(read)
                self.options.update(read)
                # A whole-sketch profile shows as its areas, each one can be dropped.
                self.profiles = extrude.expand_whole(self.profiles)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._build_form()
        self._show_options()
        self._watch()
        if feature is not None:
            self._refresh_profiles()
            self._make_draggers()
            self._update_bodies_row(compute=True)  # the bodies it was saved with
            # A cut being edited shows in red at once (R7), not only after the first change.
            self._update_cut_preview()
        else:
            self._start(profiles)

    # -- form -----------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.fields = {
            "profiles": SelectionField(self, "profiles", "Select profiles"),
            "start_object": SelectionField(self, "start_object", "Select start face"),
            "extent_object": SelectionField(self, "extent_object", "Select object"),
            "extent_object2": SelectionField(self, "extent_object2", "Select object (side 2)"),
        }
        self.profile_hint = QtWidgets.QLabel(
            "Click inside sketch areas (shaded blue) or on flat faces.\n"
            "Click a picked one again to drop it."
        )
        self.profile_hint.setWordWrap(True)
        form.addRow("Profiles", self.fields["profiles"].widget)
        form.addRow(self.profile_hint)
        self.profile = QtWidgets.QLabel("")  # what is picked, in words
        form.addRow(self.profile)
        self.start = _combo(START_LABELS, self.options["start"])
        form.addRow("Start", self.start)
        self.start_offset = DistanceField(
            self.options["start_offset"], on_change=self._offset_typed
        )
        self.start_offset_label = QtWidgets.QLabel("Offset")
        form.addRow(self.start_offset_label, self.start_offset.widget)
        self.start_object_label = QtWidgets.QLabel("Object")
        form.addRow(self.start_object_label, self.fields["start_object"].widget)
        self.direction = _combo(DIRECTION_LABELS, self.options["direction"])
        form.addRow("Direction", self.direction)
        self.side1_label = QtWidgets.QLabel("<b>Side One</b>")
        form.addRow(self.side1_label)
        self.extent = _combo(EXTENT_LABELS, self.options["extent"])
        form.addRow("Extent Type", self.extent)
        self.distance = DistanceField(self.options["distance"], on_change=self._distance_typed)
        self.distance_label = QtWidgets.QLabel("Distance")
        form.addRow(self.distance_label, self.distance.widget)
        self.extent_object_label = QtWidgets.QLabel("Object")
        form.addRow(self.extent_object_label, self.fields["extent_object"].widget)
        self.flip = QtWidgets.QPushButton("Flip")
        self.flip.setCheckable(True)
        self.flip.setToolTip("Go the other way")
        self.flip.clicked.connect(self._flipped)
        self.flip_label = QtWidgets.QLabel("Direction")
        form.addRow(self.flip_label, self.flip)
        self.measurement = _combo(MEASUREMENT_LABELS, self.options["measurement"])
        self.measurement_label = QtWidgets.QLabel("Measurement")
        form.addRow(self.measurement_label, self.measurement)
        self.taper = DistanceField(self.options["taper"], unit="deg", on_change=self._taper_typed)
        form.addRow("Taper Angle", self.taper.widget)
        self.side2_label = QtWidgets.QLabel("<b>Side Two</b>")
        form.addRow(self.side2_label)
        self.extent2 = _combo(EXTENT_LABELS, self.options["extent2"])
        self.extent2_label = QtWidgets.QLabel("Extent Type")
        form.addRow(self.extent2_label, self.extent2)
        self.distance2 = DistanceField(self.options["distance2"], on_change=self._distance2_typed)
        self.distance2_label = QtWidgets.QLabel("Distance")
        form.addRow(self.distance2_label, self.distance2.widget)
        self.extent_object2_label = QtWidgets.QLabel("Object")
        form.addRow(self.extent_object2_label, self.fields["extent_object2"].widget)
        self.taper2 = DistanceField(self.options["taper2"], unit="deg", on_change=self._typed)
        self.taper2_label = QtWidgets.QLabel("Taper Angle")
        form.addRow(self.taper2_label, self.taper2.widget)
        self.operation = _combo(OPERATION_LABELS, self.options["operation"])
        form.addRow("Operation", self.operation)
        self._build_bodies_row(form)
        self.info = QtWidgets.QLabel("")  # what the dialog waits for (not a problem)
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color: #8cc4ff;")
        form.addRow(self.info)
        self.formulas = QtWidgets.QLabel("")  # values that follow a parameter
        self.formulas.setWordWrap(True)
        self.formulas.setStyleSheet("color: #b8c7d9;")
        form.addRow(self.formulas)
        self.finish_layout()
        self.formula_inputs = [
            preview.FormulaInput(self, key, field)
            for key, field in (
                ("distance", self.distance),
                ("distance2", self.distance2),
                ("taper", self.taper),
                ("taper2", self.taper2),
            )
        ]
        for box in (self.start, self.direction, self.extent, self.extent2, self.measurement):
            box.currentIndexChanged.connect(self._typed)
        self.operation.activated.connect(self._operation_picked)
        # The row's label follows the operation, also when it changes by itself.
        self.operation.currentIndexChanged.connect(lambda _i: self._update_bodies_row())
        if self.editing:
            self.active = "profiles"
        self._show_active()

    def _show_options(self):
        """Put self.options into the widgets (without reacting to it)."""
        self._quiet = True
        try:
            _set_combo(self.start, self.options["start"])
            _set_combo(self.direction, self.options["direction"])
            _set_combo(self.extent, self.options["extent"])
            _set_combo(self.extent2, self.options["extent2"])
            _set_combo(self.measurement, self.options["measurement"])
            _set_combo(self.operation, self.options["operation"])
            self.start_offset.set_value(self.options["start_offset"])
            self.distance.set_value(self.options["distance"])
            self.distance2.set_value(self.options["distance2"])
            self.taper.set_value(self.options["taper"])
            self.taper2.set_value(self.options["taper2"])
            self.flip.setChecked(bool(self.options.get("flip")))
            for name in ("start_object", "extent_object", "extent_object2"):
                self.fields[name].set_text(_ref_text(self.options.get(name)))
        finally:
            self._quiet = False
        self._update_visibility()
        self.show_formulas()

    def _update_visibility(self):
        start = self.start.currentData()
        direction = self.direction.currentData()
        extent = self.extent.currentData()
        extent2 = self.extent2.currentData()
        two = direction == "two_sides"
        symmetric = direction == "symmetric"
        for widget, show in (
            (self.start_offset.widget, start == "offset"),
            (self.start_offset_label, start == "offset"),
            (self.fields["start_object"].widget, start == "object"),
            (self.start_object_label, start == "object"),
            (self.side1_label, two),
            (self.distance.widget, extent == "distance"),
            (self.distance_label, extent == "distance"),
            (self.fields["extent_object"].widget, extent == "to_object"),
            (self.extent_object_label, extent == "to_object"),
            (self.flip, extent == "all" and not symmetric),
            (self.flip_label, extent == "all" and not symmetric),
            (self.measurement, symmetric),
            (self.measurement_label, symmetric),
            (self.side2_label, two),
            (self.extent2, two),
            (self.extent2_label, two),
            (self.distance2.widget, two and extent2 == "distance"),
            (self.distance2_label, two and extent2 == "distance"),
            (self.fields["extent_object2"].widget, two and extent2 == "to_object"),
            (self.extent_object2_label, two and extent2 == "to_object"),
            (self.taper2.widget, two),
            (self.taper2_label, two),
        ):
            widget.setVisible(show)
        # Fusion: a symmetric extrude goes a distance or through all, never to an object.
        model = self.extent.model()
        to_object = self.extent.findData("to_object")
        if to_object >= 0 and hasattr(model, "item"):
            model.item(to_object).setEnabled(not symmetric)
        # Every extent takes a taper, like Fusion (what PartDesign cannot taper, SciForge's
        # own extrude feature builds).
        for field in (self.taper, self.taper2):
            field.widget.setEnabled(True)
        self._update_bodies_row()

    def _collect(self):
        self.options["start"] = self.start.currentData()
        self.options["start_offset"] = self.start_offset.value()
        self.options["direction"] = self.direction.currentData()
        self.options["extent"] = self.extent.currentData()
        self.options["distance"] = self.distance.value()
        self.options["measurement"] = self.measurement.currentData()
        self.options["taper"] = self.taper.value()
        self.options["extent2"] = self.extent2.currentData()
        self.options["distance2"] = self.distance2.value()
        self.options["taper2"] = self.taper2.value()
        self.options["operation"] = self.operation.currentData()
        self.options["flip"] = self.flip.isChecked()
        if self.options["direction"] == "symmetric" and self.options["extent"] == "to_object":
            self.options["extent"] = "distance"
            self._quiet = True
            _set_combo(self.extent, "distance")
            self._quiet = False

    # -- formulas ----------------------------------------------------------------------------
    FORMULA_NAMES = {
        "distance": "Distance",
        "distance2": "Distance (side two)",
        "taper": "Taper Angle",
        "taper2": "Taper Angle (side two)",
    }

    def show_formulas(self):
        """Fusion shows the formula in the field; FreeCAD's number field cannot, so the values
        that follow a parameter are listed under the fields."""
        rows = [
            "%s = %s" % (self.FORMULA_NAMES[k], v)
            for k, v in sorted(self.options.get("expressions", {}).items())
            if v
        ]
        self.formulas.setText("\n".join(rows))

    def drop_formula(self, key):
        """A plain number typed or a handle dragged: the value no longer follows a formula."""
        self.formula_error = ""
        if self.options.get("expressions", {}).pop(key, None) is not None:
            self.show_formulas()
            self._changed()

    # preview.FormulaInput calls these three.
    def formula_typed(self, key, text, value):
        self.formula_error = ""
        self.options["expressions"][key] = text
        handler = {
            "distance": self._distance_typed,
            "distance2": self._distance2_typed,
            "taper": self._taper_typed,
        }.get(key, self._typed)
        handler(value)
        self.show_formulas()

    def formula_cleared(self, key):
        self.drop_formula(key)

    def formula_failed(self, key, text):
        # Kept until the field gets a value again (a preview rebuild must not wipe it).
        self.formula_error = text
        self.message.setText("⚠ " + text)

    # -- selection fields ------------------------------------------------------------------
    def activate(self, name):
        """Make this selection box the one that takes clicks in the 3D view."""
        self.active = name
        self._show_active()
        self._update_bodies_row()  # its hint says what a click on a body does

    def _show_active(self):
        for name, field in self.fields.items():
            field.set_active(name == self.active)

    def clear_field(self, name):
        if name == "profiles":
            self.profiles = []
            self._profiles_changed()
        elif name == "bodies":
            self._clear_bodies()
        else:
            self.options[name] = None
            self.fields[name].set_text("")
            self._changed()
        self.activate(name)

    # -- start ----------------------------------------------------------------------------
    def _start(self, given=None):
        if self.body is None:
            self.message.setText("Create a sketch first (Create Sketch).")
            return
        if given:
            picked = list(given)
        elif self.from_sketch is not None:
            # Never "the newest unused sketch" instead: with several areas, the user
            # clicks the ones wanted in this sketch.
            picked = single_region(self.from_sketch)
        else:
            picked = selected_profiles(self.body)
        if not picked and self.auto_pick and self.from_sketch is None:
            single = newest_single_region(self.body)
            picked = [single] if single else []
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        if picked:
            self.profiles = picked
            self._profiles_changed()
            # Started from a selection: the preview is there when the dialog appears (this
            # runs in the command itself, not inside FreeCAD's click handling).
            self._timer.stop()
            self._recompute()
        else:
            self._refresh_profiles()

    def _watch(self):
        """Wait for clicks: inside a shaded sketch area, on a face, plane or body. Work is
        deferred to a Qt timer so nothing runs inside FreeCAD's click handling."""
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        extra = [obj for obj, _ in self.profiles if extrude.is_sketch(obj)]
        if self.from_sketch is not None:
            extra.append(self.from_sketch)
        try:
            self.picker = profile_pick.ProfilePicker(
                Gui.ActiveDocument.ActiveView,
                profile_pick.candidate_sketches(self.body, extra),
                lambda sketch, sub: QtCore.QTimer.singleShot(
                    0, lambda: self._region_clicked(sketch, sub)
                ),
                occluder=self._occluder,
                clicks_through=True,  # the sketch stays in view: its arrows stay grabbable
            )
        except Exception as exc:
            warn("profile shading unavailable: %s" % exc)

    def _occluder(self):
        """The part as it was before this extrude (global): it hides regions behind it."""
        base = self._base_feature()
        if base is None or base.Shape.isNull():
            return None
        return extrude._to_global(base.Shape, base)

    def _unwatch(self):
        self._pause_body_sync(False)
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        if self.picker is not None:
            self.picker.remove()
            self.picker = None

    # -- picks ------------------------------------------------------------------------------
    def _region_clicked(self, sketch, sub):
        if self._closed:
            return
        try:
            if self.active != "profiles" or taskui.box_click_taken():
                return  # (the click that left an arrow's value box: not a pick)
            self._toggle((sketch, sub))
        except Exception as exc:
            warn("extrude pick: %s" % exc)

    def _selection_changed(self):
        if self._closed:
            return
        try:
            # Only this design's objects: a click in another open document is not a pick.
            picks = [pk for pk in profile_pick.picks() if pk[0].Document.Name == self.doc.Name]
            if not picks:
                return
            Gui.Selection.clearSelection()
            if taskui.box_click_taken():
                return  # the click that left an arrow's value box: not a pick
            recent = self.picker is not None and self.picker.clicked_region_recently()
            for obj, short in picks:
                self._picked(obj, short, recent)
        except Exception as exc:
            warn("extrude pick: %s" % exc)

    def _picked(self, obj, short, region_clicked):
        if self.active == "bodies":
            self._body_picked(obj)
            return
        if self.active == "profiles":
            if extrude.is_sketch(obj):
                if short.startswith("InternalFace") and not region_clicked:
                    self._toggle((obj, short))
                return  # sketch lines: the shaded areas are the profiles
            if region_clicked or not short.startswith("Face"):
                return
            ref = self._base_face(obj, short)
            if ref is None:
                picked = self._picked_face_moved(obj, short)
                if picked is not None:
                    self._toggle(picked)  # the end of the preview: the face it came from
                    return
                self.message.setText("That face belongs to this extrude itself.")
                return
            face = ref[0].Shape.getElement(ref[1])
            if face.Surface.TypeId != "Part::GeomPlane":
                self.message.setText("Only flat faces can be extruded. Pick a flat face.")
                return
            self._toggle(ref)
            return
        ref = self._object_ref(obj, short)
        if ref is None:
            return
        self.options[self.active] = ref
        self.fields[self.active].set_text(_ref_text(ref))
        self.activate("profiles")
        self._changed()

    def _object_ref(self, obj, short):
        """A pick for Start / To Object: a plane, a face or a whole body."""
        if obj.TypeId in extrude.PLANE_TYPES:
            return (obj, "")
        if extrude.is_sketch(obj):
            self.message.setText("Pick a face, a plane or a body.")
            return None
        if short.startswith("Face"):
            ref = self._base_face(obj, short)
            if ref is None:
                self.message.setText("That face belongs to this extrude itself.")
                return None
            if self.active == "start_object":
                face = ref[0].Shape.getElement(ref[1])
                if face.Surface.TypeId != "Part::GeomPlane":
                    self.message.setText("The extrude can start from a flat face or a plane.")
                    return None
            return ref
        if self.active == "start_object":
            self.message.setText("Pick a flat face or a plane to start from.")
            return None
        body = extrude.owner_body(obj)
        if short == "" and body is not None:
            if body is extrude.owner_body(self.target) or body is self._source_body():
                self.message.setText("Pick a face of this body, a plane, or another body.")
                return None
            return (body.Tip, "") if body.Tip is not None else None
        self.message.setText("Pick a face, a plane or a body.")
        return None

    def _base_face(self, obj, short):
        """(feature, "FaceN") as it was before this extrude: a face clicked on the preview
        is looked up on the part before the extrude. None if only the extrude has it."""
        if extrude_bodies.is_follower(obj):
            return self._follower_face(obj, short)
        base = self._base_feature()
        body = extrude.owner_body(obj)
        ours = self.target is not None and (obj is self.target or extrude.is_helper(obj))
        later = base is not None and body is extrude.owner_body(base) and obj is not base
        if not ours and not later:
            return (obj, short)
        face = profile_pick.global_face(obj, short)
        if face is None or base is None:
            return None
        name = profile_pick.face_name_in(base, face)
        return (base, name) if name else None

    def _picked_face_moved(self, obj, short):
        """The picked profile (a face or a sketch area) whose extruded end was clicked: the
        preview covers the profile, so clicking "it" again lands on the end of the preview
        (Fusion's preview cannot be picked; the click goes to the profile)."""
        face = profile_pick.global_face(obj, short)
        if face is None or face.Surface.TypeId != "Part::GeomPlane":
            return None
        normal = extrude.face_normal(face)
        point = extrude.interior_point(face)
        for ref in self.profiles:
            try:
                starts = extrude.global_faces([ref])
            except Exception:
                continue
            for start in starts:
                axis = extrude.face_normal(start)
                if abs(abs(normal.dot(axis)) - 1.0) > 1e-6:
                    continue
                shift = (point - start.CenterOfMass).dot(axis)
                if abs(shift) < 1e-6:
                    continue
                if profile_pick.inside(start, point - axis * shift):
                    return ref
        return None

    def _source_body(self):
        if self.profiles:
            body = extrude.owner_body(self.profiles[0][0])
            if body is not None:
                return body
        return self.body

    def _base_feature(self):
        """The body's solid feature just before this extrude."""
        if self.target is not None:
            body = extrude.owner_body(self.target)
            if body is self._source_body():
                return self.target.BaseFeature
        body = self._source_body()
        if body is None:
            return None
        tip = body.Tip
        if tip is not None and tip is self.target:
            return tip.BaseFeature
        return tip

    def _toggle(self, ref):
        if any(sub == "" and obj is ref[0] for obj, sub in self.profiles):
            self.profiles = extrude.expand_whole(self.profiles)  # whole sketch -> its areas
        keys = [extrude.key(p) for p in self.profiles]
        if extrude.key(ref) in keys:
            self.profiles = [p for p in self.profiles if extrude.key(p) != extrude.key(ref)]
        else:
            self.profiles = self.profiles + [ref]
        self._profiles_changed()

    def _refresh_profiles(self):
        """Show the picked profiles (field text, blue areas, highlighted faces)."""
        count = len(self.profiles)
        self.fields["profiles"].set_text("%d selected" % count if count else "")
        self.profile.setText(extrude.profile_label(self.profiles) if count else "")
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

    def _profiles_changed(self):
        self._refresh_profiles()
        if not self.profiles:
            if not self.editing:
                if self.target is not None:
                    extrude.remove(self.target)
                    self.target = None
                    self.schedule()
                # The arrows (and their value boxes) go with the last profile, also before
                # any distance was given (no preview yet at 0).
                self._remove_draggers()
            self.message.setText("" if not self.editing else "Pick at least one profile.")
            self.error = "Pick at least one profile." if self.editing else ""
            self.waiting = ""
            self.info.setText("")
            return
        try:
            extrude.check_profiles(self.profiles)
        except extrude.ExtrudeError as exc:
            self.error = str(exc)
            self.message.setText("⚠ " + self.error)
            return
        self._changed(new_geometry=True)

    # -- changes ----------------------------------------------------------------------------
    def _typed(self, *_):
        if not self._quiet:
            self._changed()

    def _offset_typed(self, *_):
        if not self._quiet:
            self._changed(new_geometry=True)  # the arrows start at the new offset

    def _distance_typed(self, value):
        if self._quiet:
            return
        arrow = self.draggers.get("distance")
        if arrow is not None:
            arrow.set_distance(self._arrow_value(value))
        self._changed()

    def _distance2_typed(self, value):
        if self._quiet:
            return
        arrow = self.draggers.get("distance2")
        if arrow is not None:
            arrow.set_distance(value)
        self._changed()

    def _taper_typed(self, value):
        if self._quiet:
            return
        disc = self.draggers.get("taper")
        if disc is not None:
            disc.set_angle(value)
        self._changed()

    def _flipped(self, *_):
        self._changed(new_geometry=True)

    def _operation_picked(self, _index):
        self.user_picked_operation = True
        self._changed()

    def _arrow_value(self, distance):
        """Where the arrow sits for a distance (the symmetric whole length is split)."""
        if (
            self.direction.currentData() == "symmetric"
            and self.measurement.currentData() == "whole"
        ):
            return distance / 2.0
        return distance

    def _dragged(self, value):
        self.drop_formula("distance")
        value = round(value, 2)
        if self.direction.currentData() == "symmetric":
            value = abs(value)
            if self.measurement.currentData() == "whole":
                value *= 2.0
        self._quiet = True
        try:
            self.distance.set_value(value)
        finally:
            self._quiet = False
        self._changed()

    def _dragged2(self, value):
        self.drop_formula("distance2")
        self._quiet = True
        try:
            self.distance2.set_value(round(max(value, 0.0), 2))
        finally:
            self._quiet = False
        self._changed()

    def _offset_dragged(self, value):
        self._quiet = True
        try:
            self.start_offset.set_value(round(value, 2))
        finally:
            self._quiet = False
        self._changed()

    def _offset_released(self, value):
        self._offset_dragged(value)
        self._changed(new_geometry=True)

    def _taper_dragged(self, value):
        self.drop_formula("taper")
        value = max(-60.0, min(60.0, round(value, 1)))
        self._quiet = True
        try:
            self.taper.set_value(value)
        finally:
            self._quiet = False
        self._changed()

    def _auto_operation(self):
        """Fusion: extruding into material (of any body) becomes a cut; touching a body, a
        join; touching none, a new body."""
        if self.user_picked_operation or not self.profiles:
            return
        try:
            # What the preview builds (Two Sides with side one still at 0: side two alone).
            options = extrude.options_with_defaults(self._build_options() or self.options)
            key = self._way_signature()
        except Exception:
            return
        cached = getattr(self, "_auto_cache", None)
        if cached is not None and cached[0] == key:
            wanted = cached[1]
        else:
            into = self._starts_inside(options)
            way = self._in_the_way()
            touches = bool(way[1]) if way is not None else self._base_has_solid()
            wanted = bodies_core.auto_operation(
                into, touches, symmetric=options["direction"] == "symmetric"
            )
            self._auto_cache = (key, wanted)
        if wanted != self.options["operation"]:
            self.options["operation"] = wanted
            self._quiet = True
            _set_combo(self.operation, wanted)
            self._quiet = False

    def _changed(self, new_geometry=False):
        """Something changed: rebuild the preview shortly (coalesces drags)."""
        self._update_visibility()
        self._collect()
        # Fusion: choosing "To Object" or "Start: Object" makes that selection box active.
        for name, wanted in (
            ("start_object", self.options["start"] == "object"),
            ("extent_object", self.options["extent"] == "to_object"),
            (
                "extent_object2",
                self.options["direction"] == "two_sides" and self.options["extent2"] == "to_object",
            ),
        ):
            if wanted and self.options.get(name) is None and self.active != name:
                self.activate(name)
                new_geometry = True
        # The automatic operation tests every body in the way: it is decided when the
        # preview is rebuilt (_apply, 60 ms after the last change), so the digits of a typed
        # value and the mouse moves of a drag are not each waiting for it.
        self.dirty = True
        if new_geometry:
            self._geometry_changed = True
        self.schedule()

    def _recompute(self):
        """Apply the dialog's values to the document and rebuild the preview."""
        if self._closed:
            return  # a change that arrived as the dialog closed
        if getattr(self, "_rebuilding", False):
            # FreeCAD lets the window work while it rebuilds a detailed part, so a change
            # (an arrow let go) can come in the middle: it is applied right after.
            self.schedule()
            return
        self._rebuilding = True
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            if self._closed:
                return  # closed (Esc) while the part was rebuilt
            self._bodies_built()  # a cut that takes a whole body is known only now
            self.show_status()
            if self._geometry_changed or self._handles_moved():
                self._geometry_changed = False
                self._make_draggers()
        except Exception as exc:
            try:
                if not self._closed:
                    self.message.setText("⚠ %s" % exc)
            except RuntimeError:
                pass  # the dialog's widgets went with it
        finally:
            self._rebuilding = False
        self._update_cut_preview()

    # -- a distance of 0 -------------------------------------------------------------------
    def _zero_sides(self):
        """The sides whose distance is still 0: {1}, {2}, {1, 2} or an empty set."""
        options = self.options
        zero = set()
        if options["extent"] == "distance" and abs(float(options["distance"])) < 1e-6:
            zero.add(1)
        if (
            options["direction"] == "two_sides"
            and options["extent2"] == "distance"
            and abs(float(options["distance2"])) < 1e-6
        ):
            zero.add(2)
        return zero

    def _build_options(self):
        """The options the preview is built with, or None when there is nothing to build
        yet. A new extrude starts at 0 (Fusion): a side still at 0 is left out of the
        preview, so dragging one side of Two Sides already shows it. Editing an existing
        extrude builds what the dialog says (a 0 there is an error, the step stays)."""
        options = self.options
        zero = self._zero_sides()
        if not zero or self.editing:
            return options
        if options["direction"] != "two_sides" or zero == {1, 2}:
            return None
        if zero == {2}:
            return dict(options, direction="one_side")
        # Side one is at 0: side two alone, as a one-sided extrude the other way.
        alone = dict(
            options,
            direction="one_side",
            extent=options["extent2"],
            taper=options["taper2"],
            extent_object=options.get("extent_object2"),
            flip=False,
        )
        if options["extent2"] == "distance":
            alone["distance"] = -float(options["distance2"])
        elif options["extent2"] == "all":
            alone["distance"] = -1.0  # All keeps the side its distance is on
        return alone

    def _zero_message(self):
        if self._zero_sides() == {2}:
            return "The distance of side two must not be zero: drag its arrow or type a distance."
        return "The distance must not be zero: drag the arrow or type a distance."

    def _apply(self):
        if not self.profiles:
            return
        self._auto_operation()
        self.waiting = ""
        options = self._build_options()
        if options is None:
            # Nothing to show at 0: no preview (an old one would stay as if it were still
            # there), the arrows stay to be dragged, and the dialog says what to do.
            if self.target is not None and not self.editing:
                extrude.remove(self.target)
                self.target = None
            self.error = ""
            self.waiting = ZERO_HINT
            return
        try:
            before = self.target
            bodies_wanted = self._bodies_for_build()
            self.options["bodies"] = bodies_wanted
            if options is not self.options:
                options = dict(options, bodies=bodies_wanted)  # one side left out at 0
            # hide=False: the profile's sketch stays in view until OK (Fusion; Luca R6).
            self.target = extrude.build(self.profiles, options, feature=self.target, hide=False)
            self._bodies_built()
            self.error = ""
            if before is None or self.target is not before:
                self._geometry_changed = True
        except extrude.NeedsPick as exc:
            # A selection box waits for its click: the last preview stays, no warning.
            self.error = self.waiting = str(exc)
        except extrude.ExtrudeError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This extrude cannot be built: %s" % exc
        if self.error and self.options["operation"] != self._feature_operation():
            # Show the operation that is really in place.
            self.options["operation"] = self._feature_operation()
            self._quiet = True
            _set_combo(self.operation, self.options["operation"])
            self._quiet = False

    def _feature_operation(self):
        if self.target is None:
            return self.options["operation"]
        try:
            return extrude.read(self.target)[1]["operation"]
        except Exception:
            return self.options["operation"]

    def picks_sketch_areas(self):
        """Sketch areas (profiles) can be clicked while the Profiles box takes the clicks; otherwise
        a click goes through them to what is behind (sketch_area_pick)."""
        return not self._closed and self.active == "profiles"

    def feature(self):
        return self.target

    def show_status(self):
        self._update_bodies_row()
        waiting = getattr(self, "waiting", "")
        self.info.setText(waiting)
        if self.formula_error:
            self.message.setText("⚠ " + self.formula_error)
            return
        if waiting:
            self.message.setText("")
            return
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = _plain(preview.failure(self.target)) or self._followers_failure()
        text = text or self._bodies_problem
        self.message.setText("⚠ " + text if text else "")

    # -- several bodies: the "Bodies to Cut" row (R8) ------------------------------------------
    # Fusion's Extrude acts on every body in its way and lists them in the dialog; a click on
    # a body (with the row active) leaves it out or takes it back. The document side is
    # extrude_bodies.py, the wording and rules extrude_bodies_core.py.
    def _init_bodies(self):
        self.excluded = set()  # names of bodies in the way that the user clicked away
        self._stored_bodies = None  # editing: the names the extrude was saved with
        self._way = None  # (bodies it cuts through, bodies it touches): names, or None
        self._way_key = None
        self._way_cost = 0.0  # seconds the last test of the bodies in the way took
        self._way_side = None  # _way_signature(side_only=True) of that test
        self._auto_cache = None  # (signature, automatic operation) of the last decision
        self._inside_cache = None  # (signature by side, starts inside a body) of the last test
        self._sync_paused = False
        self._bodies_problem = ""  # e.g. a cut that goes through no body (OK refused)

    def _read_bodies(self, read):
        stored = read.pop("bodies", None)
        if stored is not None:
            self._stored_bodies = [b.Name for b in stored]
        else:
            # Made before extrudes acted on several bodies: it acts on its own body only.
            body = extrude.owner_body(self.target) if self.target is not None else None
            self._stored_bodies = [body.Name] if body is not None else None

    def _build_bodies_row(self, form):
        self.fields["bodies"] = SelectionField(self, "bodies", "No bodies")
        self.fields["bodies"].button.setToolTip(
            "The bodies this extrude changes. Click here, then click a body in the view to "
            "leave it out or take it back."
        )
        self.bodies_label = QtWidgets.QLabel(bodies_core.row_label("cut"))
        form.addRow(self.bodies_label, self.fields["bodies"].widget)
        self.bodies_names = QtWidgets.QLabel("")  # which bodies, by name
        self.bodies_names.setWordWrap(True)
        form.addRow(self.bodies_names)

    def _way_signature(self, side_only=False):
        """What the extrusion's solid depends on (the cache key of the bodies in its way).
        side_only: the distances by their sign only (where the extrusion starts and which
        way it goes, all the automatic Cut test needs)."""
        keys = (
            "start",
            "start_offset",
            "direction",
            "extent",
            "distance",
            "extent2",
            "distance2",
            "taper",
            "taper2",
            "measurement",
            "flip",
        )
        picked = [self.options.get(k) for k in ("start_object", "extent_object", "extent_object2")]
        refs = tuple((ref[0].Name, ref[1]) if ref else None for ref in picked)
        values = []
        for k in keys:
            value = self.options.get(k)
            if side_only and k in ("distance", "distance2"):
                try:
                    value = float(value) >= 0
                except Exception:
                    pass
            values.append(repr(value))
        return (
            tuple(extrude.key(p) for p in self.profiles),
            tuple(values),
            refs,
            self.target.Name if self.target is not None else None,
        )

    def _starts_inside(self, options):
        """Fusion's automatic Cut test (the extrusion starts inside a body). It depends only
        on where the extrusion starts and which way it goes: typing 5 then 6 tests once."""
        try:
            # Which sides the preview leaves out at 0 counts too: Two Sides with side one
            # still at 0 is built as side two alone, the other way (review finding).
            zero = None if self.editing else frozenset(self._zero_sides())
            key = (self._way_signature(side_only=True), zero)
        except Exception:
            key = None
        cached = getattr(self, "_inside_cache", None)
        if key is not None and cached is not None and cached[0] == key:
            return cached[1]
        into = extrude_bodies.starts_in_material(self.profiles, options, lead=self.target)
        self._inside_cache = (key, into)
        return into

    def _in_the_way(self):
        """(names it cuts through, names it touches) for the extrusion as it is set now
        (cached until the profiles or the values change); None when it cannot be told."""
        if not self.profiles:
            return ([], [])
        try:
            key = self._way_signature()
            if key == self._way_key:
                return self._way
            side = self._way_signature(side_only=True)
            if (
                self._way_key is not None
                and self._way_cost > DRAG_TEST_BUDGET
                and side == self._way_side
                and any(_is_dragging(handle) for handle in self.draggers.values())
            ):
                # An arrow drag on a detailed part: the bodies in the way are tested again
                # when the arrow is let go (its release rebuilds the preview once more), or
                # when it crosses to the other side of the profile.
                return self._way
            options = extrude.options_with_defaults(self._build_options() or self.options)
            started = time.monotonic()
            found = extrude_bodies.in_the_way(self.profiles, options, lead=self.target)
            self._way_cost = time.monotonic() - started
            self._way_side = side
        except Exception as exc:
            warn("extrude bodies: %s" % exc)
            key, found = None, None
        self._way = None if found is None else tuple([b.Name for b in f] for f in found)
        self._way_key = key
        if self._way is not None and self._stored_bodies is not None:
            # Editing: start from the saved list (bodies clicked away stay away).
            touched = self._way[1] if self.options["operation"] == "join" else self._way[0]
            self.excluded = bodies_core.excluded_for_edit(touched, self._stored_bodies)
            self._stored_bodies = None
        return self._way

    def _touched_names(self, compute=True):
        """The bodies in the way for the operation (names). compute=False: as last tested
        (the row is redrawn on every keystroke; the test runs with the preview)."""
        way = self._in_the_way() if compute else self._way
        if way is None:
            return None
        return way[1] if self.options.get("operation") == "join" else way[0]

    def _participant_names(self, compute=True):
        touched = self._touched_names(compute)
        if touched is None:
            return None
        return bodies_core.participants(touched, self.excluded)

    def _base_has_solid(self):
        base = self._base_feature()
        return base is not None and not base.Shape.isNull() and bool(base.Shape.Solids)

    def _bodies_for_build(self):
        """options["bodies"] for extrude.build: the bodies in the way minus those clicked
        away; None when it cannot be told (the profile's body only, as before)."""
        self._bodies_problem = ""
        operation = self.options.get("operation")
        if operation not in ("join", "cut", "intersect"):
            return None
        touched = self._touched_names()
        if touched is None:
            return None
        if not touched and operation in ("cut", "intersect"):
            # Nothing in the way: the preview stays a cut of the profile's own body (it
            # removes nothing), the operation stays as picked (the next change, a Flip,
            # may reach a body), and the dialog says why OK is refused.
            self._bodies_problem = extrude_bodies.nothing_touched({"operation": operation})
            return None
        names = bodies_core.participants(touched, self.excluded)
        if touched and not names:
            raise extrude.ExtrudeError(
                "%s is empty. Click it, then click a body to take it back."
                % bodies_core.row_label(operation)
            )
        found = [self.doc.getObject(n) for n in names]
        return [b for b in found if b is not None]

    def _bodies_built(self):
        """After a build: a Join that merges bodies, or a cut that takes all of one, keeps
        them shown while the dialog is open (the used-up body would vanish from under the
        next click)."""
        if self.target is None:
            return
        followers = extrude_bodies.followers_of(self.target)
        merging = any(extrude_bodies.is_merge(f) for f in followers)
        # A body the cut takes completely is used up too: it stays shown (and clickable, to
        # leave it out) until OK.
        self._pause_body_sync(merging or bool(extrude_bodies.used_up_by(self.target)))

    def _pause_body_sync(self, on):
        try:
            if on and not self._sync_paused:
                bodies.pause(self.doc)
                self._sync_paused = True
            elif not on and self._sync_paused:
                bodies.resume(self.doc)
                self._sync_paused = False
        except Exception as exc:
            warn("extrude bodies: %s" % exc)

    def _update_bodies_row(self, compute=False):
        """The row shows the bodies the extrude acts on: "2 bodies" and their names."""
        if not hasattr(self, "bodies_names"):
            return
        try:
            self._show_bodies_row(compute)
        except Exception as exc:
            warn("extrude bodies row: %s" % exc)

    def _show_bodies_row(self, compute):
        if compute:
            self._in_the_way()
        operation = self.operation.currentData()
        label = bodies_core.row_label(operation)
        show = bool(label) and bool(self.profiles)
        for widget in (self.bodies_label, self.fields["bodies"].widget, self.bodies_names):
            widget.setVisible(show)
        if not show:
            if self.active == "bodies":
                self.activate("profiles")
            return
        self.bodies_label.setText(label)
        names = self._participant_names(compute=False) if self._way is not None else None
        if names is None:
            body = self._source_body()
            names = [body.Name] if body is not None else []
        labels = []
        for name in names:
            obj = self.doc.getObject(name)
            labels.append(obj.Label if obj is not None else name)
        self.fields["bodies"].set_text(bodies_core.count_text(len(labels)))
        text = bodies_core.names_text(labels)
        if not labels:
            text = (
                "Touches no body: a new body is made."
                if operation == "join"
                else "The extrusion goes through no body."
            )
        gone = self._used_up_labels()
        if gone:
            text += "\n" + bodies_core.used_up_text(gone)
        if self.active == "bodies":
            text += "\nClick a body to leave it out or take it back."
        self.bodies_names.setText(text)

    def _used_up_labels(self):
        """Labels of the bodies the cut takes completely (they go when OK is pressed)."""
        try:
            if self.target is None or self.operation.currentData() != "cut":
                return []
            return [b.Label for b in extrude_bodies.used_up_by(self.target)]
        except Exception:
            return []

    def _body_picked(self, obj):
        """A click on a body with the row active: leave it out, or take it back."""
        body = bodies.body_of(obj)
        solid = bodies.is_body(obj) or "BaseFeature" in obj.PropertiesList
        if body is None or not solid:  # a sketch or a plane is no body
            self.message.setText("Click a body to leave it out or take it back.")
            return
        touched = self._touched_names() or []
        excluded, what = bodies_core.toggle(touched, self.excluded, body.Name)
        if what == "not_in_way":
            self.message.setText(
                "%s is not in the extrusion's way, so the extrude cannot change it." % body.Label
            )
            return
        self.excluded = excluded
        self.message.setText("")
        log("extrude: %s %s" % (body.Label, "left out" if what == "dropped" else "taken back"))
        self._changed()

    def _clear_bodies(self):
        """The row's x: every body left out (the dialog then asks for one)."""
        self.excluded = set(self._touched_names() or [])
        self._changed()

    def _followers_failure(self):
        try:
            kind, reason = extrude_bodies.follower_problem(self.target)
        except Exception:
            return ""
        return reason if kind == "error" else ""

    def _follower_face(self, obj, short):
        """A face clicked on the preview of another body: the same face before the extrude
        changed that body (None if only the extrude made it)."""
        if extrude_bodies.is_merge(obj):
            return None
        base = obj.BaseFeature
        face = profile_pick.global_face(obj, short)
        if face is None or base is None:
            return None
        name = profile_pick.face_name_in(base, face)
        return (base, name) if name else None

    # -- handles in the 3D view -----------------------------------------------------------------
    def _remove_draggers(self):
        for handle in self.draggers.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.draggers = {}
        self.dragger = None

    def _handles_moved(self):
        """True when the handles no longer match the values (the taper arrow sits at the
        end of the extrusion; the second arrow and the taper come and go with options)."""
        if any(_is_dragging(h) for h in self.draggers.values()):
            return False
        wanted = set()
        if self.profiles:  # also with no preview yet: the arrows start at 0 (R5)
            if self.options["start"] == "offset":
                wanted.add("offset")
            if self.options["extent"] == "distance":
                wanted.update(("distance", "taper"))
            if self.options["direction"] == "two_sides" and self.options["extent2"] == "distance":
                wanted.add("distance2")
        if wanted != set(self.draggers):
            return True
        taper = self.draggers.get("taper")
        if taper is not None:
            length = self._arrow_value(self.options["distance"])
            sign = 1.0 if length >= 0 else -1.0
            moved = abs(taper.radius - max(abs(length), 1.0)) > 1e-6
            return moved or getattr(taper, "sign", sign) != sign
        return False

    def _make_draggers(self):
        """Blue arrows for the distances (and the start offset), a curved one for the taper."""
        if self._closed:
            return
        active = [h for h in self.draggers.values() if _is_dragging(h)]
        if active:
            # never pull a handle from under the mouse: the arrows are made again once the
            # drag is over (its on_release asks for one more preview)
            self._geometry_changed = True
            return
        self._remove_draggers()
        if not self.profiles:
            return
        try:
            point, normal = extrude.profile_frame(self.profiles)
            faces = extrude.global_faces(self.profiles)
            box = faces[0].BoundBox
            for face in faces[1:]:
                box.add(face.BoundBox)
            size = max(4.0, min(box.DiagonalLength * 0.15, 30.0))
            options = self.options
            offset = 0.0
            if options["start"] != "profile":
                try:
                    offset = extrude.start_offset_of(self.profiles, options)
                except extrude.ExtrudeError:
                    offset = 0.0
            start = point + normal * offset
            if options["start"] == "offset":
                self.draggers["offset"] = ArrowDragger(
                    point,
                    normal,
                    options["start_offset"],
                    size * 0.7,
                    on_drag=self._offset_dragged,
                    on_release=self._offset_released,
                    value_box=self._value_box("offset"),
                )
            if options["extent"] == "distance":
                self.dragger = self.draggers["distance"] = ArrowDragger(
                    start,
                    normal,
                    self._arrow_value(options["distance"]),
                    size,
                    on_drag=self._dragged,
                    on_release=self._dragged,
                    value_box=self._value_box("distance"),
                )
            if options["direction"] == "two_sides" and options["extent2"] == "distance":
                self.draggers["distance2"] = ArrowDragger(
                    start,
                    normal * -1.0,
                    options["distance2"],
                    size,
                    on_drag=self._dragged2,
                    on_release=self._dragged2,
                    value_box=self._value_box("distance2"),
                )
            self._make_taper_handle(faces, start, normal, size)
        except Exception as exc:
            warn("extrude handles unavailable: %s" % exc)

    # -- the value boxes next to the arrows ---------------------------------------------------
    def _value_box(self, key):
        """The box that shows (and takes) the value of the arrow `key`. Made once and kept by
        the dialog: the arrows are rebuilt often, and what is being typed must survive that."""
        box = self.value_boxes.get(key)
        if box is not None and taskui._alive(box):
            return box
        field = {
            "distance": self.distance,
            "distance2": self.distance2,
            "offset": self.start_offset,
        }[key]
        try:
            box = ArrowValueBox(
                lambda: field.widget.text(),
                lambda text: self._box_typed(key, text),
                cancel=self.escape.press,
                # At 0 the distance arrow sits on the offset arrow, and side two's on side
                # one's: their boxes start elsewhere (side two's on the other side, the
                # offset's past its tip), so none covers another.
                other_side=key == "distance2",
                past_tip=key == "offset",
            )
        except Exception as exc:
            warn("value box unavailable: %s" % exc)
            return None
        self.value_boxes[key] = box
        return box

    def _box_typed(self, key, text):
        """A value typed in the box next to an arrow: taken like the same text typed in the
        dialog's field (numbers with units, parameters, formulas)."""
        if self._closed:
            return
        formulas = {f.key: f for f in self.formula_inputs}
        if key in formulas:
            formulas[key].take(text)
            return
        # The start offset: a value (its field takes no formula either).
        try:
            value = self.start_offset.parse(text.strip().lstrip("="))
        except ValueError as exc:
            self.message.setText("⚠ " + str(exc))
            return
        self.start_offset.take(value)

    def _discard_value_boxes(self):
        for box in self.value_boxes.values():
            try:
                box.discard()
            except Exception:
                pass
        self.value_boxes = {}

    # -- the red cut preview -------------------------------------------------------------------
    def _update_cut_preview(self):
        """Fusion shows a cut in red while the dialog is open: the volume the extrude takes
        away, drawn over the part (a picture only; the features keep their colours)."""
        if self._closed:
            return
        shape = None
        try:
            if (
                self.options.get("operation") == "cut"
                and self.target is not None
                and not self.error
                and not preview.failure(self.target)
            ):
                shape = extrude.tool_shape(self.target)
        except Exception:
            shape = None
        try:
            if shape is None:
                if self.cut_view is not None:
                    self.cut_view.clear()
            else:
                if self.cut_view is None:
                    self.cut_view = cut_preview.CutPreview(self._view())
                self.cut_view.show(shape)
            if self.picker is not None:
                self.picker.dim_picked(shape is not None)
        except Exception as exc:
            warn("cut preview: %s" % exc)

    def _view(self):
        try:
            return Gui.getDocument(self.doc.Name).ActiveView
        except Exception:
            return Gui.ActiveDocument.ActiveView

    def _remove_cut_preview(self):
        view, self.cut_view = self.cut_view, None
        if view is not None:
            view.clear()

    def _make_taper_handle(self, faces, start, normal, size):
        """The taper disc sits on the profile's edge, turning outward from the normal."""
        if self.options["extent"] != "distance":
            return
        view = Gui.ActiveDocument.ActiveView
        look = App.Vector(view.getViewDirection())
        outward = look.cross(normal)
        if outward.Length < 1e-6:
            outward = normal.cross(App.Vector(1, 0, 0))
            if outward.Length < 1e-6:
                outward = normal.cross(App.Vector(0, 1, 0))
        outward.normalize()
        reach = 0.0
        for face in faces:
            for edge in face.Edges:
                for p in edge.discretize(24):
                    reach = max(reach, (p - start).dot(outward))
        if reach <= 0:
            reach = faces[0].BoundBox.DiagonalLength / 2.0
        length = self._arrow_value(self.options["distance"])
        sign = 1.0 if length >= 0 else -1.0
        pivot = start + outward * reach
        along = normal * sign
        self.taper_length = abs(length)
        self.draggers["taper"] = AngleDragger(
            pivot,
            along.cross(outward),
            along,
            self.options["taper"],
            max(abs(length), 1.0),
            size * 0.3,
            on_drag=self._taper_dragged,
            on_release=self._taper_dragged,
        )
        self.draggers["taper"].sign = sign

    # -- OK / Cancel ----------------------------------------------------------------------------
    def accept(self):
        if not self.profiles:
            self.message.setText(
                "⚠ Pick a profile first: click inside a sketch area or on a flat face."
            )
            return False
        if self.formula_error:  # Enter right after a typo: Fusion keeps the dialog open
            self.message.setText("⚠ " + self.formula_error)
            return False
        self._timer.stop()
        if self.dirty:  # a value typed and Enter at once: build it before deciding
            self.dirty = False
            self._apply()
        if not self.editing and self._zero_sides():
            # Fusion makes nothing of a 0 distance: the dialog stays open and says why. A
            # preview the 0 just took away goes from the view too (its red cut included).
            try:
                preview.recompute(self.doc)
                self._update_cut_preview()
            except Exception as exc:
                warn("extrude preview: %s" % exc)
            self.info.setText(ZERO_HINT)
            self.message.setText("⚠ " + self._zero_message())
            return False
        if self.error:
            self.info.setText("")
            self.message.setText("⚠ " + self.error)
            return False
        if self.target is None:
            self.message.setText(
                "⚠ Pick a profile first: click inside a sketch area or on a flat face."
            )
            return False
        preview.recompute(self.doc)
        text = _plain(preview.failure(self.target)) or self._followers_failure()
        text = text or self._bodies_problem
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        # Fusion hides the profile's sketch once the extrude is made (inside this step:
        # Undo shows it again).
        extrude.hide_sketches(self.profiles)
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        new_body = extrude.owner_body(feature)
        if new_body is not None and new_body is not self.body:
            try:
                Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", new_body)
            except Exception as exc:
                warn("could not activate %s: %s" % (new_body.Label, exc))
        log("%s done" % self.title)
        return True

    def reject(self):
        self._timer.stop()
        self.cleanup()
        preview.end_transaction(self.doc, abort=True)
        preview.recompute(self.doc)
        self._close()
        return True

    def cleanup(self):
        self._unwatch()
        self.escape.remove()
        self.undo_guard.remove()
        self.enter.remove()
        self._remove_draggers()
        self._discard_value_boxes()
        try:
            self._remove_cut_preview()
        except Exception as exc:
            warn("cut preview: %s" % exc)
        super().cleanup()


# FreeCAD's failure texts that talk about FreeCAD, said the way a Fusion user needs them.
PLAIN = (
    (
        "multiple solids",
        "This would make separate solids, and a body holds one solid. Pick profiles that "
        "touch the part (or each other), or extrude them one at a time.",
    ),
    (
        "parallel to extrusion",
        "The object is parallel to the extrusion, so it cannot end there. Pick another face "
        "or plane.",
    ),
    (
        "Unable to reach",
        "The extrusion does not reach that object in this direction. Pick another object or "
        "flip the direction.",
    ),
    ("not a solid", "Nothing is left: the extrusion does not touch the body here."),
)


def _plain(text):
    for needle, said in PLAIN:
        if needle.lower() in (text or "").lower():
            return said
    return text


def _is_dragging(handle):
    """True while the handle is dragged, and just after the release until the handle's own
    timer has noticed it and run its end-of-drag work (on_release): an arrow removed in
    between never took the final value."""
    try:
        if handle.dragger.isActive.getValue():
            return True
    except Exception:
        return False
    return bool(getattr(handle, "_was_active", False))


def _ref_text(ref):
    if not ref:
        return ""
    obj, sub = ref
    if obj.TypeId in extrude.PLANE_TYPES:
        return obj.Label
    if sub:
        return "%s of %s" % (sub.rstrip("0123456789") or sub, obj.Label)
    body = extrude.owner_body(obj)
    return body.Label if body is not None else obj.Label


class ExtrudeCommand:
    def GetResources(self):
        return {
            "MenuText": "Extrude",
            "ToolTip": "Extrude sketch areas or flat faces: join, cut, intersect or new body, "
            "one side, two sides or symmetric, with a live preview (E)",
            "Pixmap": ui_icon_path("extrude"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            sketch = _sketch_in_edit()  # E pressed in a sketch: extrude that sketch
            picked = sketch_areas_picked(sketch)  # areas clicked in it (read before it closes)
            if not commands.finish_open_dialog():
                return
            if sketch is not None:
                # FreeCAD keeps the undo step of leaving the sketch (which also shows the
                # sketch again) open until this command returns; a dialog opened now
                # worked inside it, and its Cancel undid that too and hid the sketch. It
                # opens right after instead, in a step of its own (as after Finish Sketch),
                # on the areas picked in the sketch (read above, before it closed).
                doc = App.ActiveDocument
                QtCore.QTimer.singleShot(0, lambda: _open_dialog(doc, sketch, picked))
                return
            _open_dialog(App.ActiveDocument, None)
        except Exception as exc:
            warn("Extrude failed to start: %s" % exc)


def _open_dialog(doc, sketch, picked=None):
    try:
        if doc is None or doc.Name not in App.listDocuments():
            return
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        profiles = sketch_areas_profiles(sketch, picked)
        Gui.Control.showDialog(ExtrudePanel(doc, sketch=sketch, profiles=profiles or None))
        log("extrude started" + (" on %d picked area(s)" % len(profiles) if profiles else ""))
    except Exception as exc:
        warn("Extrude failed to start: %s" % exc)


def sketch_areas_picked(sketch):
    """Areas picked inside the open sketch (Fusion: click a profile, then E or Q)."""
    if sketch is None:
        return []
    try:
        from . import sketch_mode

        return sketch_mode.picked_areas(sketch)
    except Exception as exc:
        warn("picked sketch areas: %s" % exc)
        return []


def sketch_areas_profiles(sketch, picked):
    """The closed sketch's areas ("InternalFaceN") for the points picked while it was
    open; [] if none."""
    if sketch is None or not picked:
        return []
    try:
        from . import sketch_areas

        return sketch_areas.profiles(sketch, picked)
    except Exception as exc:
        warn("picked sketch areas: %s" % exc)
        return []


def _sketch_in_edit():
    try:
        edit = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument is not None else None
        obj = edit.Object if edit is not None else None
    except Exception:
        return None
    return obj if obj is not None and extrude.is_sketch(obj) else None


def edit(feature):
    """Open the Extrude dialog on an existing extrude (timeline double-click)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(ExtrudePanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


COMMANDS = {}  # SciForge_Extrude is registered by commands.py
EDITORS = {"PartDesign::Pad": edit, "PartDesign::Pocket": edit, "SciForge::Extrude": edit}
