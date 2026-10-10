# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole command (H) with Fusion's dialog.

Single Hole: click a face and the hole goes where you clicked; click elsewhere to move it,
drag its blue centre point, or type its X / Y position on the face. Click up to two
straight edges of the part to measure the hole from them, and type the distances (Fusion's
references). From Sketch: click the points and circles of a sketch, one hole at each.

Fields as in Fusion: Placement, Extents (Distance / To / All), Hole Type (Simple /
Counterbore / Countersink), Hole Tap Type (Simple / Clearance / Tapped with ISO metric or
ANSI sizes, Modeled), Drill Point (Flat / Angle) and the sizes. The blue arrow above the
hole sets its depth (drag it down to drill deeper), the one at its rim its diameter.
Problems are shown in the dialog, which then stays open. One undo step; double-click the
hole in the timeline to edit it.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, hole, log, preview, ui_icon_path, warn
from . import hole_common as common
from . import thread_tables as tables
from .compat import QtCore, QtWidgets
from .taskui import ArrowDragger, DistanceField, Panel

PLACEMENT_LABELS = [("Single Hole", "single"), ("From Sketch (Multiple Holes)", "sketch")]
EXTENT_LABELS = [("Distance", "distance"), ("To", "to"), ("All", "all")]
HOLE_TYPE_LABELS = [
    ("Simple", "simple"),
    ("Counterbore", "counterbore"),
    ("Countersink", "countersink"),
]
TAP_TYPE_LABELS = [("Simple", "simple"), ("Clearance", "clearance"), ("Tapped", "tapped")]
DRILL_LABELS = [("Flat", "flat"), ("Angle", "angle")]
FIT_LABELS = [("Close", "close"), ("Normal", "normal"), ("Loose", "loose")]
DIRECTION_LABELS = [("Right hand", "right"), ("Left hand", "left")]
BLUE = (0.30, 0.62, 0.95)
LINE_TYPES = ("Part::GeomLine", "Part::GeomLineSegment")


class PointDragger:
    """Fusion's centre point: a blue dot you drag over the face. It moves in the plane of
    `placement` (global; the hole's sketch) and reports (x, y) in that plane. Watched with a
    Qt timer like taskui.ArrowDragger (Coin's dragger callbacks crashed FreeCAD)."""

    POLL_MS = 30

    def __init__(self, placement, xy, radius, on_drag=None, on_release=None):
        from pivy import coin

        self.view = Gui.ActiveDocument.ActiveView
        self.root = coin.SoSeparator()
        place = coin.SoTransform()
        base = placement.Base
        place.translation.setValue(base.x, base.y, base.z)
        place.rotation.setValue(*placement.Rotation.Q)
        self.dragger = coin.SoTranslate2Dragger()
        self.dragger.setPart("translator", self._disc(coin, radius, BLUE))
        self.dragger.setPart("translatorActive", self._disc(coin, radius, (0.55, 0.80, 1.0)))
        for part in ("feedback", "feedbackActive", "xAxisFeedback", "yAxisFeedback"):
            try:
                self.dragger.setPart(part, coin.SoSeparator())
            except Exception:
                pass
        self.root.addChild(place)
        self.root.addChild(self.dragger)
        common.on_top(self.root)
        self.radius = radius
        self.placement = placement
        self.set_xy(xy)
        self.on_drag = on_drag
        self.on_release = on_release
        self._was_active = False
        self.view.getSceneGraph().addChild(self.root)
        self._timer = QtCore.QTimer()
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    @staticmethod
    def _disc(coin, radius, color):
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(color[0] * 0.5, color[1] * 0.5, color[2] * 0.5)
        sep.addChild(material)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.COUNTERCLOCKWISE
        hints.shapeType = coin.SoShapeHints.UNKNOWN_SHAPE_TYPE
        sep.addChild(hints)
        lift = coin.SoTranslation()
        lift.translation.setValue(0, 0, radius * 0.05)
        sep.addChild(lift)
        steps = 24
        points = [(0.0, 0.0, 0.0)]
        for i in range(steps + 1):
            a = 2.0 * math.pi * i / steps
            points.append((radius * math.cos(a), radius * math.sin(a), 0.0))
        index = []
        for i in range(1, steps + 1):
            index += [0, i, i + 1, -1]
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), points)
        faces = coin.SoIndexedFaceSet()
        faces.coordIndex.setValues(0, len(index), index)
        sep.addChild(coords)
        sep.addChild(faces)
        return sep

    def xy(self):
        t = self.dragger.translation.getValue()
        return float(t[0]), float(t[1])

    def point(self):
        """Where the dot is now (global)."""
        x, y = self.xy()
        return self.placement.multVec(App.Vector(x, y, 0))

    def set_xy(self, xy):
        self.dragger.translation.setValue(float(xy[0]), float(xy[1]), 0.0)
        self._last = self.xy()

    def dragging(self):
        return common.is_dragging(self)

    def _poll(self):
        try:
            active = self.dragging()
            value = self.xy()
            if abs(value[0] - self._last[0]) + abs(value[1] - self._last[1]) > 1e-9:
                self._last = value
                if self.on_drag:
                    self.on_drag(value)
            if self._was_active and not active and self.on_release:
                self.on_release(value)
            self._was_active = active
        except Exception as exc:
            warn("hole centre drag: %s" % exc)

    def remove(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


def _face_centre(face):
    """A point on the face near its middle (a face selected before H has no clicked point)."""
    point = face.CenterOfMass
    try:
        u, v = face.Surface.parameter(point)
        on = face.valueAt(u, v)
        if face.isInside(on, 1e-6, True):
            return on
    except Exception:
        pass
    u0, u1, v0, v1 = face.ParameterRange
    return face.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)


# FreeCAD's failure texts, said the way a Fusion user needs them.
PLAIN = (
    (
        "Hole cut depth must be less than hole depth",
        "The counterbore is as deep as the hole or deeper. Make the hole deeper or the "
        "counterbore shallower.",
    ),
    (
        "Hole cut diameter too small",
        "The counterbore or countersink must be wider than the hole.",
    ),
    (
        "Invalid countersink",
        "This countersink does not fit the hole: make it wider or the hole deeper.",
    ),
    ("Diameter too small", "The diameter is too small."),
    ("Invalid hole depth", "The depth must be more than 0."),
    ("Invalid drill point", "The drill point does not fit this hole."),
    (
        "multiple solids",
        "This hole would cut the part into separate pieces. Make it shallower or move it.",
    ),
    ("not a solid", "Nothing is left of the part here."),
    ("Thread could not be built", "This thread cannot be modeled here. Untick Modeled."),
    ("Boolean operation failed", "The hole cannot be cut here. Move it or make it smaller."),
)


def plain(text):
    for needle, said in PLAIN:
        if needle.lower() in (text or "").lower():
            return said
    return text


def _is_solid_feature(obj):
    try:
        return (
            obj.isDerivedFrom("Part::Feature")
            and not obj.isDerivedFrom(hole.SKETCH_TYPE)
            and obj.TypeId not in hole.PLANE_TYPES
            and not obj.Shape.isNull()
            and bool(obj.Shape.Solids)
        )
    except Exception:
        return False


class HolePanel(Panel):
    title = "Hole"
    icon = "hole"
    last = None
    remembered = {}  # Fusion starts a hole with the settings of the last one

    def __init__(self, doc, feature=None, selection=None):
        super().__init__(doc, "Hole" if feature is None else "Edit Hole")
        HolePanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.target = feature
        self.editing = feature is not None
        self.body = hole.owner_body(feature) if feature is not None else commands.find_body()
        self.base = feature.BaseFeature if feature is not None else self._tip()
        self.options = dict(hole.DEFAULTS)
        if feature is None:
            self.options.update(HolePanel.remembered)
            self.options["placement"] = "single"
            self.options["flip"] = False
            self.options["user_flip"] = False
            self.options["to"] = None
        self.error = ""
        self.dirty = False
        self._quiet = False
        self.active = "face"
        self.sketch = None  # From Sketch: the sketch and its picked points
        self.subs = []
        self.draggers = {}
        self.dragger = None  # the depth arrow (tests)
        self.observer = None
        self.gate = None
        self.depth_base = None
        self.watch = common.DocumentWatch(self)
        if feature is not None:
            try:
                self.options.update(hole.read(feature))
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
            if self.options["placement"] == "sketch":
                self.sketch, self.subs = hole.picked_targets(feature)
                self.active = "points"
                self._show_sketch()
        self._build_form()
        self._show_options()
        self._watch()
        if feature is not None:
            self.activate(self.active)
            self._refresh_fields()
            self._make_draggers()
        else:
            self._start(selection)

    def _show_sketch(self):
        """Editing a From Sketch hole: its (hidden) sketch shows while the dialog is open, so
        its points can be clicked, like in Fusion."""
        self._shown_sketch = None
        try:
            vobj = self.sketch.ViewObject if self.sketch is not None else None
            if vobj is not None and not vobj.Visibility:
                vobj.Visibility = True
                self._shown_sketch = self.sketch
        except Exception:
            self._shown_sketch = None

    def _hide_shown_sketch(self):
        sketch = getattr(self, "_shown_sketch", None)
        self._shown_sketch = None
        try:
            if common.alive(sketch) and sketch.ViewObject is not None:
                sketch.ViewObject.Visibility = False
        except Exception:
            pass

    # -- form -----------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.what = QtWidgets.QLabel("")
        self.what.setWordWrap(True)
        form.addRow(self.what)
        self.placement = common.combo(PLACEMENT_LABELS, self.options["placement"])
        form.addRow("Placement", self.placement)
        self.fields = {
            "face": common.SelectionField(self, "face", "Select a face"),
            "points": common.SelectionField(self, "points", "Select sketch points"),
            "reference": common.SelectionField(self, "reference", "Select edges (optional)"),
            "to": common.SelectionField(self, "to", "Select a face or plane"),
        }
        self.face_label = QtWidgets.QLabel("Face / Point")
        form.addRow(self.face_label, self.fields["face"].widget)
        self.points_label = QtWidgets.QLabel("Sketch Points")
        form.addRow(self.points_label, self.fields["points"].widget)
        self.reference_label = QtWidgets.QLabel("Reference")
        form.addRow(self.reference_label, self.fields["reference"].widget)
        self.ref_fields = []
        self.ref_labels = []
        for i in range(2):
            field = DistanceField(0.0, on_change=lambda v, i=i: self._ref_typed(i, v))
            label = QtWidgets.QLabel("Distance %d" % (i + 1))
            form.addRow(label, field.widget)
            self.ref_fields.append(field)
            self.ref_labels.append(label)
        self.pos_x = DistanceField(0.0, on_change=lambda v: self._position_typed())
        self.pos_x_label = QtWidgets.QLabel("X")
        self.pos_x.widget.setToolTip("Where the hole is on the face, from the body's origin")
        form.addRow(self.pos_x_label, self.pos_x.widget)
        self.pos_y = DistanceField(0.0, on_change=lambda v: self._position_typed())
        self.pos_y_label = QtWidgets.QLabel("Y")
        self.pos_y.widget.setToolTip("Where the hole is on the face, from the body's origin")
        form.addRow(self.pos_y_label, self.pos_y.widget)
        self.extent = common.combo(EXTENT_LABELS, self.options["extent"])
        form.addRow("Extents", self.extent)
        self.to_label = QtWidgets.QLabel("To Object")
        form.addRow(self.to_label, self.fields["to"].widget)
        self.flip = QtWidgets.QCheckBox("Flip")
        self.flip.setToolTip("Drill the other way")
        self.flip_label = QtWidgets.QLabel("Direction")
        form.addRow(self.flip_label, self.flip)
        self.hole_type = common.combo(HOLE_TYPE_LABELS, self.options["hole_type"])
        form.addRow("Hole Type", self.hole_type)
        self.tap_type = common.combo(TAP_TYPE_LABELS, self.options["tap_type"])
        form.addRow("Hole Tap Type", self.tap_type)
        self.drill_point = common.combo(DRILL_LABELS, self.options["drill_point"])
        form.addRow("Drill Point", self.drill_point)
        self.standard = common.combo([(label, key) for key, label in tables.STANDARDS])
        self.standard_label = QtWidgets.QLabel("Thread Type")
        form.addRow(self.standard_label, self.standard)
        self.size = QtWidgets.QComboBox()
        self.size_label = QtWidgets.QLabel("Size")
        form.addRow(self.size_label, self.size)
        self.designation = QtWidgets.QComboBox()
        self.designation_label = QtWidgets.QLabel("Designation")
        form.addRow(self.designation_label, self.designation)
        self.fit = common.combo(FIT_LABELS, self.options["fit"])
        self.fit_label = QtWidgets.QLabel("Fit")
        form.addRow(self.fit_label, self.fit)
        self.thread_class = QtWidgets.QComboBox()
        self.class_label = QtWidgets.QLabel("Class")
        form.addRow(self.class_label, self.thread_class)
        self.direction = common.combo(DIRECTION_LABELS, self.options["direction"])
        self.direction_label = QtWidgets.QLabel("Direction")
        form.addRow(self.direction_label, self.direction)
        self.modeled = QtWidgets.QCheckBox("Modeled")
        self.modeled.setToolTip("Cut the real thread (slower); off: the thread is recorded only")
        form.addRow("", self.modeled)
        self.full_tap = QtWidgets.QCheckBox("Full Tap Depth")
        form.addRow("", self.full_tap)
        self.tap_depth = DistanceField(self.options["tap_depth"], on_change=self._typed)
        self.tap_depth_label = QtWidgets.QLabel("Tap Depth")
        form.addRow(self.tap_depth_label, self.tap_depth.widget)
        self.sizes_label = QtWidgets.QLabel("<b>Hole</b>")
        form.addRow(self.sizes_label)
        self.diameter = DistanceField(self.options["diameter"], on_change=self._diameter_typed)
        form.addRow("Diameter", self.diameter.widget)
        self.depth = DistanceField(self.options["depth"], on_change=self._depth_typed)
        self.depth_label = QtWidgets.QLabel("Depth")
        form.addRow(self.depth_label, self.depth.widget)
        self.cbore_diameter = DistanceField(self.options["cbore_diameter"], on_change=self._typed)
        self.cbore_diameter_label = QtWidgets.QLabel("Counterbore Diameter")
        form.addRow(self.cbore_diameter_label, self.cbore_diameter.widget)
        self.cbore_depth = DistanceField(self.options["cbore_depth"], on_change=self._typed)
        self.cbore_depth_label = QtWidgets.QLabel("Counterbore Depth")
        form.addRow(self.cbore_depth_label, self.cbore_depth.widget)
        self.csink_diameter = DistanceField(self.options["csink_diameter"], on_change=self._typed)
        self.csink_diameter_label = QtWidgets.QLabel("Countersink Diameter")
        form.addRow(self.csink_diameter_label, self.csink_diameter.widget)
        self.csink_angle = DistanceField(
            self.options["csink_angle"], unit="deg", on_change=self._typed
        )
        self.csink_angle_label = QtWidgets.QLabel("Countersink Angle")
        form.addRow(self.csink_angle_label, self.csink_angle.widget)
        self.drill_angle = DistanceField(
            self.options["drill_angle"], unit="deg", on_change=self._typed
        )
        self.drill_angle_label = QtWidgets.QLabel("Tip Angle")
        form.addRow(self.drill_angle_label, self.drill_angle.widget)
        self.finish_layout()
        for box in (
            self.extent,
            self.hole_type,
            self.drill_point,
            self.fit,
            self.thread_class,
            self.direction,
        ):
            box.currentIndexChanged.connect(self._typed)
        self.placement.currentIndexChanged.connect(self._placement_changed)
        self.tap_type.currentIndexChanged.connect(self._tap_type_changed)
        self.standard.currentIndexChanged.connect(self._standard_changed)
        self.size.currentIndexChanged.connect(self._size_changed)
        self.designation.currentIndexChanged.connect(self._typed)
        for box in (self.modeled, self.full_tap):
            box.toggled.connect(self._typed)
        self.flip.toggled.connect(self._flipped)

    def _show_options(self):
        """Put self.options into the widgets (without reacting)."""
        o = self.options
        self._quiet = True
        try:
            common.set_combo(self.placement, o["placement"])
            common.set_combo(self.extent, o["extent"])
            common.set_combo(self.hole_type, o["hole_type"])
            common.set_combo(self.tap_type, o["tap_type"])
            common.set_combo(self.standard, o["standard"])
            self._fill_sizes(o["standard"], o["size"], o["designation"])
            common.set_combo(self.fit, o["fit"])
            common.set_combo(self.direction, o["direction"])
            common.set_combo(self.drill_point, o["drill_point"])
            self.flip.setChecked(bool(o["flip"]))
            self.modeled.setChecked(bool(o["modeled"]))
            self.full_tap.setChecked(bool(o["full_tap"]))
            self.tap_depth.set_value(o["tap_depth"])
            self.diameter.set_value(o["diameter"])
            self.depth.set_value(o["depth"])
            self.cbore_diameter.set_value(o["cbore_diameter"])
            self.cbore_depth.set_value(o["cbore_depth"])
            self.csink_diameter.set_value(o["csink_diameter"])
            self.csink_angle.set_value(o["csink_angle"])
            self.drill_angle.set_value(o["drill_angle"])
            self.fields["to"].set_text(_ref_text(o.get("to")))
        finally:
            self._quiet = False
        self._update_visibility()

    def _fill_sizes(self, standard, size, designation):
        sizes = tables.sizes(standard)
        if size not in sizes:
            size = "6" if standard == "iso" else "1/4"
        common.fill_combo(self.size, [(s, s) for s in sizes], size)
        found = tables.designations(standard, self.size.currentData())
        common.fill_combo(self.designation, [(d.label, d.label) for d in found], designation)
        wanted = self.options.get("thread_class")
        if wanted not in tables.classes(standard, True):
            wanted = tables.default_class(standard, True)
        common.fill_combo(
            self.thread_class, [(c, c) for c in tables.classes(standard, True)], wanted
        )

    def _update_visibility(self):
        placement = self.placement.currentData()
        extent = self.extent.currentData()
        kind = self.hole_type.currentData()
        tap = self.tap_type.currentData()
        single = placement == "single"
        threaded = tap != "simple"
        refs = hole.references(self.target) if self.target is not None and single else []
        # X / Y move the point in the face's plane: only for a hole on a flat face.
        placed = self.target is not None and single and hole.on_flat_face(self.target)
        # Through all: the hole has no bottom, so no drill point angle.
        angled = self.drill_point.currentData() == "angle" and extent != "all"
        for widget, show in (
            (self.fields["face"].widget, single),
            (self.face_label, single),
            (self.fields["points"].widget, not single),
            (self.points_label, not single),
            (self.fields["reference"].widget, single),
            (self.reference_label, single),
            (self.pos_x.widget, placed and not refs),
            (self.pos_x_label, placed and not refs),
            (self.pos_y.widget, placed and not refs),
            (self.pos_y_label, placed and not refs),
            (self.fields["to"].widget, extent == "to"),
            (self.to_label, extent == "to"),
            (self.flip, not single),
            (self.flip_label, not single),
            (self.standard, threaded),
            (self.standard_label, threaded),
            (self.size, threaded),
            (self.size_label, threaded),
            (self.designation, tap == "tapped"),
            (self.designation_label, tap == "tapped"),
            (self.fit, tap == "clearance"),
            (self.fit_label, tap == "clearance"),
            (self.thread_class, tap == "tapped"),
            (self.class_label, tap == "tapped"),
            (self.direction, tap == "tapped"),
            (self.direction_label, tap == "tapped"),
            (self.modeled, tap == "tapped"),
            (self.full_tap, tap == "tapped"),
            (self.tap_depth.widget, tap == "tapped" and not self.full_tap.isChecked()),
            (self.tap_depth_label, tap == "tapped" and not self.full_tap.isChecked()),
            (self.depth.widget, extent != "all"),
            (self.depth_label, extent != "all"),
            (self.cbore_diameter.widget, kind == "counterbore"),
            (self.cbore_diameter_label, kind == "counterbore"),
            (self.cbore_depth.widget, kind == "counterbore"),
            (self.cbore_depth_label, kind == "counterbore"),
            (self.csink_diameter.widget, kind == "countersink"),
            (self.csink_diameter_label, kind == "countersink"),
            (self.csink_angle.widget, kind == "countersink"),
            (self.csink_angle_label, kind == "countersink"),
            (self.drill_angle.widget, angled),
            (self.drill_angle_label, angled),
        ):
            widget.setVisible(show)
        self.standard_label.setText("Standard" if tap == "clearance" else "Thread Type")
        for i in range(2):
            self.ref_fields[i].widget.setVisible(i < len(refs))
            self.ref_labels[i].setVisible(i < len(refs))
        # Clearance and tapped holes take their diameter from the standard.
        self.diameter.widget.setEnabled(tap == "simple")
        self.diameter.widget.setToolTip(
            "" if tap == "simple" else "Set by the thread size (%s)" % self._tap_name(tap)
        )
        # "To" measures the depth itself.
        self.depth.widget.setEnabled(extent == "distance")

    @staticmethod
    def _tap_name(tap):
        return "clearance hole" if tap == "clearance" else "tap drill"

    def _collect(self):
        o = self.options
        o["placement"] = self.placement.currentData()
        o["extent"] = self.extent.currentData()
        o["hole_type"] = self.hole_type.currentData()
        o["tap_type"] = self.tap_type.currentData()
        o["standard"] = self.standard.currentData()
        o["size"] = self.size.currentData() or o["size"]
        designations = tables.designations(o["standard"], o["size"])
        o["designation"] = self.designation.currentData() or o["designation"]
        if o["tap_type"] == "clearance" and designations:
            o["designation"] = designations[0].label  # a clearance hole is per size
        o["fit"] = self.fit.currentData()
        o["thread_class"] = self.thread_class.currentData() or o["thread_class"]
        o["direction"] = self.direction.currentData()
        o["modeled"] = self.modeled.isChecked()
        o["full_tap"] = self.full_tap.isChecked()
        o["tap_depth"] = self.tap_depth.value()
        o["drill_point"] = self.drill_point.currentData()
        o["diameter"] = self.diameter.value()
        o["depth"] = self.depth.value()
        o["cbore_diameter"] = self.cbore_diameter.value()
        o["cbore_depth"] = self.cbore_depth.value()
        o["csink_diameter"] = self.csink_diameter.value()
        o["csink_angle"] = self.csink_angle.value()
        o["drill_angle"] = self.drill_angle.value()
        o["flip"] = self.flip.isChecked()

    # -- what can be picked -----------------------------------------------------------------
    def allow(self, obj, name):
        """The selection gate: what lights up under the mouse while the dialog is open."""
        if obj.isDerivedFrom(hole.SKETCH_TYPE):
            if hole.is_helper(obj):
                return False
            if self.active == "to":
                return False
            if not name:
                return True  # a sketch picked in the browser: all its points and circles
            if name.startswith("Vertex"):
                return True
            if name.startswith("Edge"):
                return hole.pick_target(obj, name) is not None
            return False
        if obj.TypeId in hole.PLANE_TYPES:
            return self.active == "to"
        if not name or not _is_solid_feature(obj):
            return False
        if name.startswith("Face"):
            # From Sketch takes sketch points only (a face under a point must not win).
            return self.placement.currentData() == "single" or self.active == "to"
        if name.startswith("Edge"):
            if self.active == "to" or self.placement.currentData() != "single":
                return False
            try:
                return obj.Shape.getElement(name).Curve.TypeId in LINE_TYPES
            except Exception:
                return False
        return False

    # -- selection boxes -------------------------------------------------------------------
    def activate(self, name):
        self.active = name
        for key, field in self.fields.items():
            field.set_active(key == name)

    def clear_field(self, name):
        if name == "reference":
            if self.target is not None and hole.placement_of(self.target) == "single":
                self._set_references([])
        elif name == "to":
            self.options["to"] = None
            self.fields["to"].set_text("")
            self._changed()
        elif name == "points":
            self.subs = []
            if self.target is not None and not self.editing:
                self._drop_target()
            elif self.target is not None:
                self.message.setText("Pick at least one point or circle.")
            self._refresh_fields()
        elif name == "face":
            if self.target is not None and not self.editing:
                self._drop_target()
            self._refresh_fields()
        self.activate(name)

    def _refresh_fields(self):
        target = self.target
        single = self.placement.currentData() == "single"
        if single:
            spot = hole.placed_face(target) if target is not None else None
            self.fields["face"].set_text(_ref_text(spot) if spot else "")
            refs = hole.references(target) if target is not None else []
            self.fields["reference"].set_text("%d edge(s)" % len(refs) if refs else "")
            xy = hole.hole_xy(target) if target is not None else None
            self._quiet = True
            try:
                for i, (_ref, distance) in enumerate(refs[:2]):
                    self.ref_fields[i].set_value(distance)
                if xy is not None:
                    self.pos_x.set_value(round(xy[0], 6))
                    self.pos_y.set_value(round(xy[1], 6))
            finally:
                self._quiet = False
        else:
            count = len(hole.centres(target)) if target is not None else 0
            self.fields["points"].set_text("%d point(s)" % count if count else "")
        if single:
            text = (
                "Click a face to place the hole (click again to move it, or drag the blue "
                "dot). Click edges to measure it from them."
            )
        else:
            text = (
                "Click points and circles of a sketch: a hole at each. Click one again to drop it."
            )
        if self.target is None and self.base is None:
            text = "Make a solid first (Create Sketch, then Extrude)."
        self.what.setText(text)
        self._update_visibility()

    # -- starting ------------------------------------------------------------------------
    def _tip(self):
        body = self.body
        if body is None:
            return None
        tip = body.Tip
        if tip is None or tip.Shape.isNull() or not tip.Shape.Solids:
            return None
        return tip

    def _start(self, selection=None):
        self.activate("face")
        found = list(selection) if selection is not None else common.picks()
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        sketch_picks = [
            (obj, short)
            for obj, short, _p in found
            if obj.isDerivedFrom(hole.SKETCH_TYPE) and not hole.is_helper(obj)
        ]
        faces = [(o, s, p) for o, s, p in found if s.startswith("Face") and _is_solid_feature(o)]
        if self.base is None and faces:
            owner = hole.owner_body(faces[0][0])
            if owner is not None:
                self._use_body(owner)
        if self.base is None:
            self._refresh_fields()
            self.message.setText("⚠ Make a solid first: Create Sketch, then Extrude.")
            return
        if sketch_picks:
            self._quiet = True
            common.set_combo(self.placement, "sketch")
            self._quiet = False
            self.options["placement"] = "sketch"
            self.activate("points")
            for obj, short in sketch_picks:
                self._sketch_clicked(obj, short, whole_ok=True)
        elif faces:
            obj, short, point = faces[0]
            self._face_clicked(obj, short, point)
        self._refresh_fields()
        if self.target is not None:
            # Started from a selection: the preview is there when the dialog appears.
            self._timer.stop()
            self._recompute()

    def _use_body(self, body):
        """Holes go into the body whose face was clicked (made the active one)."""
        self.body = body
        self.base = self._tip()
        try:
            Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        except Exception:
            pass

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                # Deferred: nothing is built inside FreeCAD's click handling.
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        self.gate = common.install_gate(self)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        common.remove_gate(self.gate)
        self.gate = None

    # -- clicks ---------------------------------------------------------------------------
    def _selection_changed(self):
        if self._closed:
            return
        try:
            found = common.picks()
            if not found:
                return
            Gui.Selection.clearSelection()
            for obj, short, point in found:
                self._clicked(obj, short, point)
            self._refresh_fields()
        except Exception as exc:
            warn("hole pick: %s" % exc)

    def _clicked(self, obj, short, point):
        if obj.isDerivedFrom(hole.SKETCH_TYPE):
            if hole.is_helper(obj) or self.active == "to":
                return
            if self.base is None:
                return
            if self.placement.currentData() != "sketch":
                if self.editing:
                    self.message.setText(
                        "This hole is a single hole; make a new hole to drill at sketch points."
                    )
                    return
                # A sketch point picked: Fusion's From Sketch placement.
                self._quiet = True
                common.set_combo(self.placement, "sketch")
                self._quiet = False
                self._placement_changed()
            self._sketch_clicked(obj, short, whole_ok=not short)
            return
        if self.active == "to":
            self._to_clicked(obj, short, point)
            return
        if obj.TypeId in hole.PLANE_TYPES:
            return
        if short.startswith("Edge"):
            self._edge_clicked(obj, short)
            return
        if short.startswith("Face"):
            if self.placement.currentData() != "single":
                self.message.setText("From Sketch: click points or circles of a sketch.")
            elif self.active == "reference":
                self.message.setText(
                    "Reference is active: click an edge. Click Face / Point to move the hole."
                )
            else:
                self._face_clicked(obj, short, point)

    def _face_clicked(self, obj, short, point):
        face = common.global_shape(obj, short)
        if face is None:
            return
        owner = hole.owner_body(obj)
        if owner is None:
            self.message.setText("Click a face of a body.")
            return
        if owner is not self.body:
            if self.editing:
                self.message.setText(
                    "Click a face of %s, the body this hole is in."
                    % (self.body.Label if self.body is not None else "its body")
                )
                return
            if self.target is not None:
                self._drop_target()
            self._use_body(owner)
            if self.base is None:
                self.message.setText("⚠ That body has no solid yet.")
                return
        if point is None:
            point = _face_centre(face)
        normal = hole.face_normal_at(face, point)
        local = hole.to_local(self.body, point)
        rotation = self.body.getGlobalPlacement().Rotation.inverted()
        if obj is self.base:
            name = short
        else:  # clicked on the preview: the same face of the part before the hole
            name = hole.base_face_at(self.base, local, rotation.multVec(normal))
        if name is None:
            self.message.setText("That face is made by this hole. Click a face of the part.")
            return
        self.message.setText("")
        try:
            if self.target is None:
                self.target = hole.make_single(
                    self.body, self.base, name, local, self._apply_options(), name="Hole"
                )
            else:
                same = hole.placed_face(self.target) == (self.base, name)
                refs = [(r, None) for r, _d in hole.references(self.target)] if same else []
                hole.set_position(self.target, self.base, name, local, refs)
            self.error = ""
        except hole.HoleError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "The hole cannot be placed there: %s" % exc
        self.activate("face")
        self._geometry_changed()

    def _edge_clicked(self, obj, short):
        if self.placement.currentData() != "single":
            self.message.setText("From Sketch: click points or circles of a sketch.")
            return
        if self.target is None:
            self.message.setText("Place the hole first: click a face.")
            return
        try:
            edge = obj.Shape.getElement(short).copy()
        except Exception:
            return
        owner = hole.owner_body(obj)
        if owner is not None and owner is not self.body:
            self.message.setText("Pick an edge of this body.")
            return
        name = hole.base_edge_like(self.base, edge)
        if name is None:
            self.message.setText("That edge is made by this hole. Pick an edge of the part.")
            return
        ref = (self.base, name)
        sketch = hole.helper_sketch(self.target)
        why = hole.check_reference(sketch, ref)
        if why:
            self.message.setText(why)
            return
        refs = [r for r, _d in hole.references(self.target)]
        keys = [(r[0].Name, r[1]) for r in refs]
        if (ref[0].Name, ref[1]) in keys:
            refs = [r for r in refs if (r[0].Name, r[1]) != (ref[0].Name, ref[1])]
        else:
            refs = (refs + [ref])[-2:]  # Fusion measures from two edges at most
        self._set_references(refs)
        self.activate("reference")

    def _set_references(self, refs):
        old = dict(((r[0].Name, r[1]), d) for r, d in hole.references(self.target))
        spot = hole.placed_face(self.target)
        point = hole.hole_point(self.target)
        if spot is None or point is None:
            return
        try:
            hole.set_position(
                self.target,
                spot[0],
                spot[1],
                point,
                [(r, old.get((r[0].Name, r[1]))) for r in refs],
            )
            got = len(hole.references(self.target))
            if got < len(refs):
                self.message.setText("Pick an edge that is not parallel to the first one.")
            else:
                self.message.setText("")
        except hole.HoleError as exc:
            self.message.setText("⚠ %s" % exc)
        self._refresh_fields()
        self._geometry_changed()

    def _sketch_clicked(self, sketch, short, whole_ok=False):
        if short == "" and whole_ok:
            sub = None  # the whole sketch: every point and circle
        else:
            sub = hole.pick_target(sketch, short)
            if sub is None:
                self.message.setText(
                    "Click a point or a circle of the sketch (lines do not count)."
                )
                return
        if self.editing and self.sketch is not None and sketch is not self.sketch:
            self.message.setText("This hole drills at points of %s." % self.sketch.Label)
            return
        if hole.owner_body(sketch) is not self.body:
            owner = hole.owner_body(sketch)
            if self.editing or owner is None:
                self.message.setText("Pick points of a sketch in this body.")
                return
            if self.target is not None:
                self._drop_target()
            self._use_body(owner)
            if self.base is None:
                self.message.setText("⚠ That body has no solid yet.")
                return
        if self.sketch is not sketch:
            self.sketch, self.subs = sketch, []
        if sub is None:
            self.subs = []
        elif sub in self.subs:
            self.subs = [s for s in self.subs if s != sub]
            if not self.subs:
                if self.editing:
                    self.subs = [sub]
                    self.message.setText("A hole needs at least one point.")
                    return
                self._drop_target()
                self._refresh_fields()
                return
        else:
            self.subs = self.subs + [sub]
        self.message.setText("")
        try:
            if self.target is None:
                self.target = hole.make_from_sketch(
                    self.body, sketch, self.subs, self._apply_options(auto_flip=True)
                )
                self._quiet = True
                self.flip.setChecked(bool(self.target.Reversed))
                self._quiet = False
                self.options["flip"] = bool(self.target.Reversed)
            else:
                hole.set_sketch_points(self.target, sketch, self.subs)
            self.error = ""
        except hole.HoleError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "The holes cannot be made: %s" % exc
        self.activate("points")
        self._geometry_changed()

    def _to_clicked(self, obj, short, point):
        if obj.TypeId in hole.PLANE_TYPES:
            ref = (obj, "")
        elif short.startswith("Face"):
            face = common.global_shape(obj, short)
            if face is None:
                return
            if point is None:
                point = _face_centre(face)
            owner = hole.owner_body(obj)
            if owner is self.body and self.base is not None:
                local = hole.to_local(self.body, point)
                name = hole.base_face_at(self.base, local)
                if name is None:
                    self.message.setText("That face is made by this hole. Pick a face of the part.")
                    return
                ref = (self.base, name)
            else:
                ref = (obj, short)
        else:
            self.message.setText("Pick a face or a plane for the hole to go to.")
            return
        self.options["to"] = ref
        self.fields["to"].set_text(_ref_text(ref))
        self.activate("face" if self.placement.currentData() == "single" else "points")
        self._changed()

    def _drop_target(self):
        """The picks were cleared: the preview hole goes (a new hole only)."""
        if self.target is None or self.editing:
            return
        target, self.target = self.target, None
        self._remove_draggers()
        try:
            hole.remove(target)
        except Exception as exc:
            warn("hole: could not remove the preview: %s" % exc)
        self.error = ""
        self.schedule()

    # -- changes --------------------------------------------------------------------------
    def _placement_changed(self, *_):
        if self._quiet:
            return
        wanted = self.placement.currentData()
        if self.target is not None and hole.placement_of(self.target) != wanted:
            if self.editing:
                # An existing hole keeps its placement kind.
                self._quiet = True
                common.set_combo(self.placement, hole.placement_of(self.target))
                self._quiet = False
                self.message.setText(
                    "This hole stays %s; delete it and make a new one to change that."
                    % ("a single hole" if wanted == "sketch" else "a sketch hole")
                )
                return
            self._drop_target()
        self.sketch, self.subs = None, []
        self.options["placement"] = wanted
        self.activate("face" if wanted == "single" else "points")
        self._refresh_fields()
        self._changed()

    def _tap_type_changed(self, *_):
        if self._quiet:
            return
        tap = self.tap_type.currentData()
        if tap != "simple" and self.options.get("tap_type") == "simple":
            # Start from the size nearest to the diameter the hole has now.
            d = tables.closest(
                self.standard.currentData(), self.diameter.value(), internal=tap == "tapped"
            )
            if d is not None:
                self._quiet = True
                try:
                    self._fill_sizes(d.standard, d.size, d.label)
                finally:
                    self._quiet = False
        self._changed()

    def _standard_changed(self, *_):
        if self._quiet:
            return
        standard = self.standard.currentData()
        d = tables.closest(standard, self._thread_diameter())
        self._quiet = True
        try:
            self.options["thread_class"] = tables.default_class(standard, True)
            self._fill_sizes(standard, d.size if d else "", d.label if d else "")
        finally:
            self._quiet = False
        self._changed()

    def _size_changed(self, *_):
        if self._quiet:
            return
        standard = self.standard.currentData()
        found = tables.designations(standard, self.size.currentData())
        common.fill_combo(self.designation, [(d.label, d.label) for d in found], None)
        self._changed()

    def _thread_diameter(self):
        d = tables.find(self.options["standard"], self.options["designation"])
        return d.diameter if d is not None else self.diameter.value()

    def _flipped(self, *_):
        if self._quiet:
            return
        self.options["user_flip"] = True
        self._changed()

    def _typed(self, *_):
        if not self._quiet:
            self._changed()

    def _diameter_typed(self, value):
        if self._quiet:
            return
        handle = self.draggers.get("diameter")
        if handle is not None:
            handle.set_distance(value / 2.0)
        self._changed()

    def _depth_typed(self, value):
        if self._quiet:
            return
        self._changed()

    def _ref_typed(self, index, value):
        if self._quiet or self.target is None:
            return
        try:
            hole.set_reference_distance(self.target, index, value)
            self.message.setText("")
        except hole.HoleError as exc:
            self.message.setText("⚠ %s" % exc)
            return
        self._geometry_changed()

    def _position_typed(self):
        if self._quiet or self.target is None or hole.helper_sketch(self.target) is None:
            return
        try:
            hole.move_to(self.target, (self.pos_x.value(), self.pos_y.value()))
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)
            return
        self._geometry_changed()

    def _apply_options(self, auto_flip=False):
        self._collect()
        options = dict(self.options)
        if auto_flip and not options.get("user_flip"):
            options.pop("flip", None)
        return options

    def _changed(self):
        self._update_visibility()
        self._collect()
        if self.extent.currentData() == "to" and not self.options.get("to"):
            if self.active != "to":
                self.activate("to")
        self.dirty = True
        self.schedule()

    def _geometry_changed(self):
        self.dirty = True
        self.schedule()

    def _recompute(self):
        if self._closed:
            return
        if self.doc.Recomputing:
            # A long recompute lets Qt run timers meanwhile: never start a second one.
            self._timer.start()
            return
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self.show_status()
            self._show_computed()
            self._refresh_fields()
            self._make_draggers()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if self.target is None:
            return
        self._collect()
        try:
            hole.apply(self.target, self.options)
            self.error = ""
        except hole.HoleError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This hole cannot be built: %s" % exc

    def _show_computed(self):
        """Values FreeCAD worked out: a clearance / tap drill diameter, a To depth."""
        if self.target is None:
            return
        self._quiet = True
        try:
            if self.tap_type.currentData() != "simple":
                self.diameter.set_value(self.target.Diameter.Value)
            if self.extent.currentData() == "to":
                self.depth.set_value(self.target.Depth.Value)
        finally:
            self._quiet = False

    def feature(self):
        return self.target

    def show_status(self):
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = plain(preview.failure(self.target))
        self.message.setText("⚠ " + text if text else "")

    # -- handles --------------------------------------------------------------------------
    def _remove_draggers(self):
        for handle in self.draggers.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.draggers = {}
        self.dragger = None

    def _make_draggers(self):
        """Blue handles: the centre dot (Single Hole), the depth arrow above the hole and the
        diameter arrow at its rim. Never rebuilt while one is being dragged."""
        if self._closed:
            return
        if any(common.is_dragging(h) for h in self.draggers.values()):
            return
        self._remove_draggers()
        if self.target is None or not common.alive(self.target):
            return
        if preview.failure(self.target):
            return
        try:
            spots = hole.centres(self.target)
            if not spots:
                return
            centre, direction = spots[0]
            normal = direction * -1.0
            radius = max(self.target.Diameter.Value / 2.0, 0.1)
            box = self.base.Shape.BoundBox if self.base is not None else None
            size = max(3.0, min((box.DiagonalLength if box else 50.0) * 0.08, 20.0))
            self.handle_size = size
            if self.placement.currentData() == "single":
                sketch = hole.helper_sketch(self.target)
                xy = hole.hole_xy(self.target)
                if sketch is not None and xy is not None:
                    self.draggers["centre"] = PointDragger(
                        sketch.getGlobalPlacement(),
                        xy,
                        max(min(radius * 0.45, size * 0.25), 0.4),
                        on_drag=self._centre_dragged,
                        on_release=self._centre_released,
                    )
            if self.extent.currentData() == "distance":
                self.depth_base = self.depth.value()
                self.depth_origin = centre + normal * (size * 1.6)
                self.depth_direction = direction
                arrow = ArrowDragger(
                    self.depth_origin,
                    direction,
                    0.0,
                    size,
                    on_drag=self._depth_dragged,
                    on_release=self._depth_released,
                )
                common.on_top(arrow.root)
                self.dragger = self.draggers["depth"] = arrow
            if self.tap_type.currentData() == "simple":
                side = self._side(normal)
                # The arrow is drawn around its middle: its inner end sits on the rim, clear
                # of the centre dot.
                scale = size * 0.6
                self.diameter_origin = centre + normal * (size * 0.05) + side * (1.5 * scale)
                self.diameter_direction = side
                arrow = ArrowDragger(
                    self.diameter_origin,
                    side,
                    radius,
                    scale,
                    on_drag=self._diameter_dragged,
                    on_release=self._diameter_dragged,
                )
                common.on_top(arrow.root)
                self.draggers["diameter"] = arrow
        except Exception as exc:
            warn("hole handles unavailable: %s" % exc)

    @staticmethod
    def _side(normal):
        """An in-plane direction that faces the viewer's right (the diameter arrow)."""
        try:
            look = App.Vector(Gui.ActiveDocument.ActiveView.getViewDirection())
        except Exception:
            look = App.Vector(0, 0, -1)
        side = look.cross(normal)
        if side.Length < 1e-6:
            side = normal.cross(App.Vector(1, 0, 0))
            if side.Length < 1e-6:
                side = normal.cross(App.Vector(0, 1, 0))
        side.normalize()
        return side * -1.0

    def _centre_dragged(self, xy):
        if self.target is None:
            return
        try:
            if hole.on_flat_face(self.target):
                hole.move_to(self.target, (round(xy[0], 3), round(xy[1], 3)))
            else:
                self._centre_on_curved_face()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)
            return
        self.dirty = True
        self.schedule()

    def _centre_released(self, xy):
        self._centre_dragged(xy)

    def _centre_on_curved_face(self):
        """On a curved face the dot moves on the plane touching the face where the hole was;
        the hole is placed again where the face is under the dot, square to it there."""
        dot = self.draggers.get("centre")
        spot = hole.placed_face(self.target)
        if dot is None or spot is None:
            return
        point = hole.to_local(self.body, dot.point())
        refs = [(r, None) for r, _d in hole.references(self.target)]
        hole.set_position(self.target, spot[0], spot[1], point, refs)

    def _depth_dragged(self, value):
        base = self.depth_base if self.depth_base is not None else self.depth.value()
        depth = max(round(base + value, 2), 0.1)
        self._quiet = True
        try:
            self.depth.set_value(depth)
        finally:
            self._quiet = False
        self._changed()

    def _depth_released(self, value):
        self._depth_dragged(value)
        self.depth_base = self.depth.value()
        arrow = self.draggers.get("depth")
        if arrow is not None:
            arrow.set_distance(0.0)  # the arrow goes back above the hole

    def _diameter_dragged(self, value):
        diameter = max(round(abs(value) * 2.0, 2), 0.1)
        self._quiet = True
        try:
            self.diameter.set_value(diameter)
        finally:
            self._quiet = False
        self._changed()

    # -- undo / closing while open ----------------------------------------------------------
    def document_event(self, closing):
        if closing:
            self.target = self.base = self.body = None
            common.abandon(self)
        else:
            QtCore.QTimer.singleShot(0, lambda: common.end_after_undo(self))

    # -- OK / Cancel ----------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        if self.target is None:
            if self.placement.currentData() == "single":
                self.message.setText("⚠ Click a face to place the hole first.")
            else:
                self.message.setText("⚠ Click points or circles of a sketch first.")
            return False
        self._timer.stop()
        if self.dirty:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        preview.recompute(self.doc)
        text = plain(preview.failure(self.target))
        if text:
            self.message.setText("⚠ " + text)
            return False
        if self.placement.currentData() == "sketch" and self.sketch is not None:
            try:
                self.sketch.ViewObject.Visibility = False  # Fusion hides a used sketch
            except Exception:
                pass
        self._collect()
        HolePanel.remembered = {
            k: v
            for k, v in self.options.items()
            if k not in ("placement", "to", "flip", "user_flip", "extent")
        }
        if self.options["extent"] != "to":
            HolePanel.remembered["extent"] = self.options["extent"]
        self.cleanup()
        self.doc.commitTransaction()
        self._close()
        log("%s done" % self.title)
        return True

    def reject(self):
        if self._closed:
            return True
        self._timer.stop()
        self.cleanup()
        self.doc.abortTransaction()
        preview.recompute(self.doc)
        self._close()
        return True

    def cleanup(self):
        self._hide_shown_sketch()
        self._unwatch()
        self.escape.remove()
        self._remove_draggers()
        self.watch.remove()
        super().cleanup()


def _ref_text(ref):
    if not ref or ref[0] is None:
        return ""
    obj, sub = ref
    if obj.TypeId in hole.PLANE_TYPES:
        return obj.Label
    if sub:
        return "%s of %s" % (sub.rstrip("0123456789") or sub, obj.Label)
    return obj.Label


class HoleCommand:
    def GetResources(self):
        return {
            "MenuText": "Hole",
            "ToolTip": "Drill a hole where you click on a face, or at sketch points: simple, "
            "counterbore or countersink, clearance or tapped, with a live preview (H)",
            "Pixmap": ui_icon_path("hole"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            install_guard()
            found = common.picks()  # a face or sketch points picked before H
            if not commands.finish_open_dialog():
                return
            Gui.Control.showDialog(HolePanel(App.ActiveDocument, selection=found))
            log("hole started")
        except Exception as exc:
            warn("Hole failed to start: %s" % exc)


def edit(feature):
    """Open the Hole dialog on an existing hole (timeline double-click)."""
    try:
        install_guard()
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        Gui.Control.showDialog(HolePanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


def edit_helper(sketch):
    """A Single Hole's sketch (browser double-click, timeline "Edit Profile Sketch"): the
    hole's own dialog, where the point is moved."""
    target = hole.hole_of(sketch)
    if target is None:
        commands.tell("The hole this sketch placed was deleted.")
        return
    edit(target)


# -- helper sketches stay hidden ----------------------------------------------------------------
class _HelperGuard:
    """Deleting a hole in the timeline shows its sketch again (as for any feature made from a
    sketch). A Single Hole's sketch is only the hole's position, Fusion never shows it: the
    sketch of a deleted hole is hidden again. An App observer: FreeCAD passes the document
    object (a Gui observer gets view providers, which crash when read while being built)."""

    def slotChangedObject(self, obj, prop):
        try:
            if prop != "Visibility" or not hole.is_helper(obj) or not obj.Visibility:
                return
            QtCore.QTimer.singleShot(
                0, lambda name=obj.Name, doc=obj.Document.Name: _rehide(doc, name)
            )
        except Exception:
            pass


def _rehide(doc_name, name):
    try:
        doc = App.listDocuments().get(doc_name)
        obj = doc.getObject(name) if doc is not None else None
        if obj is None or hole.hole_of(obj) is not None:
            return
        gdoc = Gui.getDocument(doc_name)
        edit_vp = gdoc.getInEdit() if gdoc is not None else None
        if edit_vp is not None and getattr(edit_vp, "Object", None) is obj:
            return
        if obj.ViewObject is not None and obj.ViewObject.Visibility:
            obj.ViewObject.Visibility = False
    except Exception:
        pass


_GUARD = {"observer": None}


def install_guard():
    if _GUARD["observer"] is not None:
        return
    try:
        observer = _HelperGuard()
        App.addDocumentObserver(observer)
        _GUARD["observer"] = observer
    except Exception as exc:
        log("hole sketch guard unavailable: %s" % exc)


try:
    install_guard()
except Exception:
    pass

COMMANDS = {"SciForge_Hole": HoleCommand}
EDITORS = {"PartDesign::Hole": edit, "SciForge::HoleSketch": edit_helper}
