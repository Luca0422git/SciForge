# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC > CREATE > Snap Fit, with Fusion's dialog.

Pick a sketch whose points sit on the parting plane between the two halves (Selection Mode
Automatic: every point of the sketch; Manual: click the points one by one). A cantilever hook
grows from the body behind the sketch plane at each point, and the part it catches is made
on the other body: a groove in the wall it slides along (Parallel Hook and Groove), a slot
through the wall it crosses with the catch under it (Perpendicular Hook and Groove), or a
loop standing on the other body (Hook and Loop). Rotation turns every catch (Uniform), each
one (Independent: one angle per point) or turns them away from the middle of the points
(Aligned). The sizes start from the component's plastic rule (thickness, draft, base
fillet, clearance) and follow it until a value is typed. The blue arrows drag the beam's
length and the catch's depth; the strain at the beam's root is checked against the
material's allowable strain. One timeline step; double-click it to edit.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, components, curve_pick, extrude, log, plastic, plastic_snap
from . import plastic_core, preview, profile_pick, ui_icon_path, warn
from . import plastic_snap_core as core
from .compat import QtCore, QtWidgets
from .hole_common import SelectionField
from .taskui import ArrowDragger, DistanceField, Panel, ValueBoxes

safe = curve_pick.safe("snap fit")

TYPE_LABELS = [(core.TYPE_TITLES[k], k) for k in core.TYPES]
SELECTION_LABELS = [(core.SELECTION_TITLES[k], k) for k in core.SELECTIONS]
ROTATION_LABELS = [(core.ROTATION_TITLES[k], k) for k in core.ROTATIONS]
EXTENT_LABELS = [(core.EXTENT_TITLES[k], k) for k in core.EXTENTS]
HOOK_FIELDS = [
    ("extent_distance", "mm"),
    ("length", "mm"),
    ("width", "mm"),
    ("thickness", "mm"),
    ("tip_thickness", "mm"),
    ("catch_depth", "mm"),
    ("catch_length", "mm"),
    ("insertion_angle", "deg"),
    ("retention_angle", "deg"),
    ("draft", "deg"),
    ("fillet", "mm"),
]
OTHER_FIELDS = [("clearance", "mm"), ("loop_thickness", "mm")]
OTHER_TITLES = {"parallel": "Groove", "perpendicular": "Hook Undercut", "loop": "Loop"}
MAX_TURN_HANDLES = 12  # Independent: a rotation handle for each of the first 12 snap fits


def point_index(sketch, short):
    """The geometry index of the sketch point picked as `short` ("VertexN"), or None."""
    try:
        at = bodies.global_shape(sketch).getElement(short).Point
    except Exception:
        return None
    best, best_d = None, 1e-3
    for i, point in plastic_snap.sketch_points(sketch):
        d = (point - at).Length
        if d < best_d:
            best, best_d = i, d
    return best


def preselected():
    """(sketch, [point indices]) from the selection made before the command."""
    sketch, indices = None, []
    for obj, short in profile_pick.picks():
        if not extrude.is_sketch(obj):
            continue
        sketch = sketch or obj
        if obj is sketch and short.startswith("Vertex"):
            i = point_index(obj, short)
            if i is not None and i not in indices:
                indices.append(i)
    return sketch, indices


def _rule_here(doc, feature=None):
    try:
        if feature is not None:
            return plastic.rule_for_body(bodies.body_of(feature))
        return plastic.rule_for_component(doc, components.active_component(doc), fallback=True)
    except Exception as exc:
        warn("Snap Fit: plastic rule: %s" % exc)
        return None


class SnapFitPanel(Panel):
    title = "Snap Fit"
    icon = "pl_snap_fit"
    last = None

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Snap Fit" if feature is None else "Edit Snap Fit")
        SnapFitPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.target = feature
        self.editing = feature is not None
        self.sketch = None
        self.indices = []
        self.rule = _rule_here(doc, feature)
        self.options = core.defaults(self.rule)
        self.error = ""
        self.dirty = False
        self.find_other = False
        self.other_pick = None  # the other body picked in its box (None: found)
        self.hook_pick = None  # the hook body picked in its box (None: found)
        self.active = "points"
        self.hidden_other = None  # (body, was visible) while Hide Other Body is on
        self.arrows = {}
        self.value_boxes = ValueBoxes(self, default="length")
        self.observer = None
        self._quiet = False
        self._shown = []
        if feature is not None:
            try:
                self.sketch, self.indices, read, _other = plastic_snap.read(feature)
                self.options = core.follow_rule(read, self.rule)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._build_form()
        self._show_options()
        self._watch()
        if feature is not None:
            self._show_sketch()
            self._refresh_picks()
            self._make_arrows()
            self.show_status()
        else:
            self._start()

    # -- form ----------------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.type = curve_pick.combo(TYPE_LABELS, self.options["type"])
        self.type.setObjectName("SciForgeSnap_type")
        form.addRow("Type", self.type)
        self.selection = curve_pick.combo(SELECTION_LABELS, self.options["selection"])
        self.selection.setObjectName("SciForgeSnap_selection")
        form.addRow("Selection Mode", self.selection)
        self.field = SelectionField(self, "points", "Select sketch points")
        self.field.button.setObjectName("SciForgeSnap_points")
        self.field.clear.setObjectName("SciForgeSnap_clear_points")
        self.field.set_active(True)
        form.addRow("Points", self.field.widget)
        self.rotation = curve_pick.combo(ROTATION_LABELS, self.options["rotation"])
        self.rotation.setObjectName("SciForgeSnap_rotation")
        form.addRow("Rotation Type", self.rotation)
        self.angle = DistanceField(
            self.options["angle"], unit="deg", on_change=self._typed("angle")
        )
        self.angle.widget.setObjectName("SciForgeSnap_angle")
        self.angle_label = QtWidgets.QLabel("Rotation Angle")
        form.addRow(self.angle_label, self.angle.widget)
        self.angles = QtWidgets.QLineEdit()
        self.angles.setObjectName("SciForgeSnap_angles")
        self.angles.setToolTip("Independent: one angle per snap fit, in order (degrees)")
        self.angles.editingFinished.connect(self._angles_typed)
        self.angles_label = QtWidgets.QLabel("Angles")
        form.addRow(self.angles_label, self.angles)
        self.inward = curve_pick.checkbox("Face In", False)
        self.inward.setObjectName("SciForgeSnap_inward")
        self.inward.setToolTip("Aligned: the catches face the middle of the points")
        form.addRow("", self.inward)
        self.align_field = SelectionField(self, "align", "Middle of the points")
        self.align_field.button.setObjectName("SciForgeSnap_align")
        self.align_field.clear.setObjectName("SciForgeSnap_clear_align")
        self.align_label = QtWidgets.QLabel("Align To")
        form.addRow(self.align_label, self.align_field.widget)
        self.flip = curve_pick.checkbox("Flip", self.options["flip"])
        self.flip.setObjectName("SciForgeSnap_flip")
        self.flip.setToolTip("The hook on the other side of the sketch plane")
        form.addRow("", self.flip)
        # Hook
        hook_box = QtWidgets.QGroupBox("Hook")
        hook = QtWidgets.QFormLayout(hook_box)
        self.hook = curve_pick.checkbox("Hook", self.options["hook"])
        self.hook.setObjectName("SciForgeSnap_hook")
        hook.addRow("", self.hook)
        self.hook_field = SelectionField(self, "hook", "Found")
        self.hook_field.button.setObjectName("SciForgeSnap_hook_body")
        self.hook_field.clear.setObjectName("SciForgeSnap_clear_hook_body")
        hook.addRow("Hook Body", self.hook_field.widget)
        self.extent = curve_pick.combo(EXTENT_LABELS, self.options["extent"])
        self.extent.setObjectName("SciForgeSnap_extent")
        hook.addRow("Extent Type", self.extent)
        self.fields = {}
        self.labels = {}
        for key, unit in HOOK_FIELDS:
            self._add_field(hook, key, unit)
        form.addRow(hook_box)
        # Groove / Hook Undercut / Loop
        self.other_box = QtWidgets.QGroupBox(OTHER_TITLES[self.options["type"]])
        other = QtWidgets.QFormLayout(self.other_box)
        self.groove = curve_pick.checkbox(
            OTHER_TITLES[self.options["type"]], self.options["groove"]
        )
        self.groove.setObjectName("SciForgeSnap_groove")
        other.addRow("", self.groove)
        for key, unit in OTHER_FIELDS:
            self._add_field(other, key, unit)
        self.other_label = QtWidgets.QLabel("")
        self.other_label.setObjectName("SciForgeSnap_other_body")
        self.other_field = SelectionField(self, "other", "Found")
        self.other_field.button.setObjectName("SciForgeSnap_other")
        self.other_field.clear.setObjectName("SciForgeSnap_clear_other")
        other.addRow("Body", self.other_field.widget)
        other.addRow("", self.other_label)
        self.hide_other = curve_pick.checkbox("Hide Other Body", False)
        self.hide_other.setObjectName("SciForgeSnap_hide_other")
        self.hide_other.setToolTip("See the hooks: the other body hidden while the dialog is open")
        other.addRow("", self.hide_other)
        form.addRow(self.other_box)
        self.rule_label = QtWidgets.QLabel(self._rule_text())
        self.rule_label.setObjectName("SciForgeSnap_rule")
        self.rule_label.setWordWrap(True)
        form.addRow(self.rule_label)
        self.strain = QtWidgets.QLabel("")
        self.strain.setObjectName("SciForgeSnap_strain")
        self.strain.setWordWrap(True)
        form.addRow(self.strain)
        self.finish_layout()
        for box in (self.type, self.selection, self.rotation, self.extent):
            box.currentIndexChanged.connect(self._choice_changed)
        for box in (self.flip, self.hook, self.groove, self.inward):
            box.toggled.connect(self._choice_changed)
        self.hide_other.toggled.connect(self._hide_other_toggled)

    def _add_field(self, layout, key, unit):
        field = DistanceField(self.options[key], unit=unit, on_change=self._typed(key))
        field.widget.setObjectName("SciForgeSnap_" + key)
        label = QtWidgets.QLabel(core.LABELS[key])
        layout.addRow(label, field.widget)
        self.fields[key] = field
        self.labels[key] = label

    def _rule_text(self):
        rule = self.rule or {}
        name = rule.get("name", plastic_core.DEFAULT_RULE)
        return "Plastic rule: %s (%s)" % (name, rule.get("material", "ABS"))

    def _show_options(self):
        self._quiet = True
        try:
            curve_pick.set_combo(self.type, self.options["type"])
            curve_pick.set_combo(self.selection, self.options["selection"])
            curve_pick.set_combo(self.rotation, self.options["rotation"])
            curve_pick.set_combo(self.extent, self.options["extent"])
            self.angle.set_value(self.options["angle"])
            self.angles.setText(", ".join("%g" % a for a in self.options.get("angles", [])))
            self.flip.setChecked(self.options["flip"])
            self.hook.setChecked(self.options["hook"])
            self.groove.setChecked(self.options["groove"])
            self.inward.setChecked(bool(self.options.get("align_inward")))
            self.align_field.set_text("Picked point" if self.options.get("align_point") else "")
            for key, field in self.fields.items():
                field.set_value(self.options[key])
        finally:
            self._quiet = False
        self._update_visibility()

    def _update_visibility(self):
        kind = self.options["type"]
        rotation = self.options["rotation"]
        title = OTHER_TITLES[kind]
        self.other_box.setTitle(title)
        self.groove.setText(title)
        shows = (
            (self.angle_label, rotation != "independent"),
            (self.angle.widget, rotation != "independent"),
            (self.angles_label, rotation == "independent"),
            (self.angles, rotation == "independent"),
            (self.inward, rotation == "aligned"),
            (self.align_label, rotation == "aligned"),
            (self.align_field.widget, rotation == "aligned"),
            (self.labels["extent_distance"], self.options["extent"] == "distance"),
            (self.fields["extent_distance"].widget, self.options["extent"] == "distance"),
            (self.labels["loop_thickness"], kind == "loop"),
            (self.fields["loop_thickness"].widget, kind == "loop"),
        )
        for widget, show in shows:
            widget.setVisible(show)

    # -- values ------------------------------------------------------------------------------------
    def _typed(self, key):
        def typed(value):
            if self._quiet or self._closed:
                return
            try:
                self.options[key] = float(value)
                if key in core.RULE_FIELDS:
                    self.options = core.unlink(self.options, key)
                self._changed()
            except Exception as exc:
                warn("Snap Fit: %s" % exc)

        return typed

    @safe
    def _angles_typed(self, *_):
        if self._quiet or self._closed:
            return
        text = self.angles.text().replace(";", ",")
        try:
            values = [float(t) for t in text.split(",") if t.strip()]
        except ValueError:
            self.message.setText("⚠ Angles: numbers separated by commas, e.g. 0, 90, 180")
            return
        self.options["angles"] = values
        self._changed()

    @safe
    def _choice_changed(self, *_):
        if self._quiet:
            return
        old_type, old_groove = self.options["type"], self.options["groove"]
        old_selection = self.options["selection"]
        self.options["type"] = self.type.currentData()
        self.options["selection"] = self.selection.currentData()
        self.options["rotation"] = self.rotation.currentData()
        self.options["extent"] = self.extent.currentData()
        self.options["flip"] = bool(self.flip.isChecked())
        self.options["hook"] = bool(self.hook.isChecked())
        self.options["groove"] = bool(self.groove.isChecked())
        self.options["align_inward"] = bool(self.inward.isChecked())
        if self.options["type"] != old_type or self.options["groove"] != old_groove:
            self.find_other = True
        if self.options["selection"] == "automatic":
            self.indices = []
        self._update_visibility()
        if self.options["selection"] != old_selection:
            self._picks_changed()  # Manual starts with no point picked
            return
        self._refresh_picks()
        self._changed()

    def _changed(self):
        self.dirty = True
        self.schedule()

    # -- picking -----------------------------------------------------------------------------------
    def activate(self, name):
        self.active = name
        self.field.set_active(name == "points")
        self.align_field.set_active(name == "align")
        self.other_field.set_active(name == "other")
        self.hook_field.set_active(name == "hook")

    def clear_field(self, name):
        if name == "align":
            self.options["align_point"] = None
            self.options["align_line"] = None
            self.align_field.set_text("")
            self.activate("points")
            self._changed()
            return
        if name == "hook":
            self.hook_pick = None
            self.hook_field.set_text("")
            self._rebuild_in_hook_body()
            self.activate("points")
            self._changed()
            return
        if name == "other":
            self.other_pick = None
            self.other_field.set_text("")
            self.find_other = True
            self.activate("points")
            self._changed()
            return
        self.sketch = None
        self.indices = []
        self._picks_changed()

    def _align_picked(self, obj, short):
        line = None
        try:
            shape = bodies.global_shape(obj)
            item = shape.getElement(short) if short else shape
            if item.ShapeType == "Vertex":
                at = item.Point
            elif item.ShapeType == "Edge" and type(item.Curve).__name__ in ("Line", "LineSegment"):
                ends = [v.Point for v in item.Vertexes]
                at = (ends[0] + ends[-1]) * 0.5
                line = [(q.x, q.y, q.z) for q in (ends[0], ends[-1])]
            else:
                at = item.CenterOfMass if hasattr(item, "CenterOfMass") else item.BoundBox.Center
        except Exception as exc:
            self.message.setText("⚠ Pick a point, an edge or a face to align to: %s" % exc)
            return
        self.options["align_point"] = (at.x, at.y, at.z)
        self.options["align_line"] = line
        self.align_field.set_text("%s %s" % (obj.Label, short) if short else obj.Label)
        self.activate("points")
        self._changed()

    def _hook_picked(self, obj, short):
        body = obj if bodies.is_body(obj) else bodies.body_of(obj)
        if body is None or not bodies.has_solid(body):
            self.message.setText("⚠ Click a solid body for the hooks.")
            return
        if body is self.other_pick:
            self.message.setText("⚠ The hooks cannot go on the body that takes the grooves.")
            return
        self.hook_pick = body
        self.hook_field.set_text(body.Label)
        self._rebuild_in_hook_body()
        self.activate("points")
        self._changed()

    def _rebuild_in_hook_body(self):
        """A snap fit lives in its hook body: a new hook body makes it again there."""
        if self.target is None or self.editing:
            return
        wanted = self.hook_pick
        if wanted is None or bodies.body_of(self.target) is not wanted:
            plastic_snap.remove(self.target)
            self.target = None
            self.find_other = True

    def _other_picked(self, obj, short):
        body = obj if bodies.is_body(obj) else bodies.body_of(obj)
        hook_body = bodies.body_of(self.target) if self.target is not None else None
        if body is None or not bodies.has_solid(body):
            self.message.setText("⚠ Click a solid body for the groove, slot or loop.")
            return
        if body is hook_body:
            self.message.setText("⚠ The other body cannot be the hook's own body.")
            return
        self.other_pick = body
        self.other_field.set_text(body.Label)
        self.activate("points")
        self._changed()

    @safe
    def _hide_other_toggled(self, on):
        self._show_other()
        if on:
            other = plastic_snap.other_body(self.target) if self.target is not None else None
            if other is not None and other.ViewObject is not None:
                self.hidden_other = (other, bool(other.ViewObject.Visibility))
                other.ViewObject.Visibility = False

    def _show_other(self):
        if self.hidden_other is None:
            return
        body, was = self.hidden_other
        self.hidden_other = None
        try:
            if bodies.alive(body) and body.ViewObject is not None:
                body.ViewObject.Visibility = was
        except Exception:
            pass

    def _start(self):
        if not bodies.solid_bodies(self.doc):
            self.message.setText("⚠ Make the two halves first: Snap Fit joins two solid bodies.")
            return
        sketch, indices = preselected()
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        if sketch is not None:
            self.sketch = sketch
            if indices:
                self.indices = indices
                self.options["selection"] = "manual"
                self._quiet = True
                curve_pick.set_combo(self.selection, "manual")
                self._quiet = False
            self._picks_changed()
        else:
            self.message.setText(
                "Click a sketch with points on the parting plane (Manual: click the points)."
            )

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

    def _selection_changed(self):
        if self._closed:
            return
        try:
            picks = [(o, s) for o, s in profile_pick.picks() if o.Document is self.doc]
            if not picks:
                return
            Gui.Selection.clearSelection()
            if any(_dragging(a) for a in self.arrows.values()):
                return
            for obj, short in picks:
                self._picked(obj, short)
        except Exception as exc:
            warn("Snap Fit pick: %s" % exc)

    def _picked(self, obj, short):
        if self.active == "align":
            self._align_picked(obj, short)
            return
        if self.active == "other":
            self._other_picked(obj, short)
            return
        if self.active == "hook":
            self._hook_picked(obj, short)
            return
        if not extrude.is_sketch(obj):
            self.message.setText(
                "⚠ Snap fits go at sketch points: click a sketch with points on the parting "
                "plane."
            )
            return
        points = plastic_snap.sketch_points(obj)
        if not points:
            self.message.setText(
                "⚠ %s has no points: sketch points where the snap fits go." % obj.Label
            )
            return
        if self.options["selection"] == "automatic":
            self.sketch = obj
            self.indices = []
        else:
            if self.sketch is not obj:
                self.sketch = obj
                self.indices = []
            if not short.startswith("Vertex"):
                self.message.setText("Manual: click the sketch's points one by one.")
                self._refresh_picks()
                return
            i = point_index(obj, short)
            if i is None:
                self.message.setText("⚠ That is not a sketch point: click a point.")
                return
            if i in self.indices:
                self.indices.remove(i)
            else:
                self.indices.append(i)
        self._picks_changed()

    def _show_sketch(self):
        if self.sketch is None:
            return
        try:
            if self.sketch.ViewObject is not None and not self.sketch.ViewObject.Visibility:
                self.sketch.ViewObject.Visibility = True
                if self.sketch not in self._shown:
                    self._shown.append(self.sketch)
        except Exception:
            pass

    def _hide_shown(self):
        for obj in self._shown:
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass
        self._shown = []

    def _count(self):
        if self.sketch is None:
            return 0
        if self.options.get("selection") == "manual" and not self.indices:
            return 0  # Manual: nothing until points are clicked
        return len(plastic_snap.chosen_points(self.sketch, self.indices))

    def _refresh_picks(self):
        if self.sketch is None:
            self.field.set_text("")
            return
        n = self._count()
        self.field.set_text("%d point%s (%s)" % (n, "" if n == 1 else "s", self.sketch.Label))

    def _picks_changed(self):
        self._refresh_picks()
        self._show_sketch()
        if self.sketch is None or self._count() == 0:
            if self.target is not None and not self.editing:
                plastic_snap.remove(self.target)
                self.target = None
                self.schedule()
            self._remove_arrows()
            self.error = "Pick the snap fits' points." if self.editing else ""
            self.message.setText(("⚠ " + self.error) if self.error else "")
            return
        self.find_other = self.find_other or not self.editing
        self._changed()

    # -- building ----------------------------------------------------------------------------------
    def _recompute(self):
        if self._closed:
            return
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self._show_sketch()
            self.show_status()
            if not any(_dragging(a) for a in self.arrows.values()):
                self._make_arrows()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if self.sketch is None or self._count() == 0:
            return
        try:
            other = self.other_pick if bodies.alive(self.other_pick) else None
            if self.target is None:
                hook = self.hook_pick if bodies.alive(self.hook_pick) else None
                self.target = plastic_snap.make(
                    self.sketch, dict(self.options), self.indices, hook_body=hook, groove_body=other
                )
            else:
                keep = other if other is not None else (None if self.find_other else False)
                plastic_snap.update(
                    self.target,
                    sketch=self.sketch,
                    options=dict(self.options),
                    indices=self.indices,
                    groove_body=keep,
                )
            self.find_other = False
            self.error = ""
        except plastic_snap.SnapError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This snap fit cannot be built: %s" % exc

    def feature(self):
        return self.target

    def show_status(self):
        other = plastic_snap.other_body(self.target) if self.target is not None else None
        if self.options["groove"]:
            self.other_label.setText(other.Label if other is not None else "(none found)")
        else:
            self.other_label.setText("(off)")
        material = (self.rule or {}).get("material", "ABS")
        try:
            state, text = core.strain_note(
                self.options, material, plastic_core.ALLOWABLE_STRAIN.get(material)
            )
        except Exception:
            state, text = "ok", ""
        self.strain.setText(("⚠ " if state == "warn" else "") + text)
        self.strain.setStyleSheet("color: #ffcc33;" if state == "warn" else "")
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = preview.failure(self.target)
        if not text and self.target is not None:
            notes = [getattr(self.target, "SciForgeWarning", "")]
            notes += [getattr(f, "SciForgeWarning", "") for f in _followers(self.target)]
            notes = [n for n in notes if n]
            if notes:
                self.message.setText("Note: " + "; ".join(notes))
                return
        self.message.setText("⚠ " + text if text else "")

    # -- arrows ------------------------------------------------------------------------------------
    def _remove_arrows(self):
        for arrow in self.arrows.values():
            try:
                arrow.remove()
            except Exception:
                pass
        self.arrows = {}

    def _make_arrows(self):
        if self._closed:
            return
        self._remove_arrows()
        if self.target is None or self.error or self.sketch is None:
            return
        try:
            placed = plastic_snap.frames(self.sketch, self.options, self.indices)
            if not placed:
                return
            origin, (ex, _ey, ez) = placed[0]
            size = 4.0
            back = origin - ex * (self.options["thickness"] + 1.5)
            self.arrows["length"] = ArrowDragger(
                back,
                ez,
                self.options["length"],
                size,
                on_drag=self._dragged("length"),
                on_release=self._dragged("length"),
            )
            self._attach_box("length")
            tip = origin + ez * (self.options["length"] - 0.5 * self.options["catch_length"])
            self.arrows["catch_depth"] = ArrowDragger(
                tip,
                ex,
                self.options["catch_depth"],
                size,
                on_drag=self._dragged("catch_depth"),
                on_release=self._dragged("catch_depth"),
            )
            self._attach_box("catch_depth")
            self._make_turn_handles(placed)
        except Exception as exc:
            warn("Snap Fit arrows unavailable: %s" % exc)

    def _make_turn_handles(self, placed):
        """Fusion's rotation manipulators: one for Uniform (the first snap fit's), one per
        snap fit for Independent; none for Aligned (the reference sets the turn)."""
        from . import handles3d

        rotation = self.options["rotation"]
        if rotation == "aligned":
            return
        normal, x_axis = plastic_snap.sketch_axes(self.sketch)
        radius = max(4.0, 0.9 * self.options["width"])
        count = 1 if rotation == "uniform" else min(len(placed), MAX_TURN_HANDLES)
        angles = core.angles_for(self.options, len(placed))
        for i in range(count):
            origin = placed[i][0]
            key = "angle" if rotation == "uniform" else "angle%d" % (i + 1)
            self.arrows[key] = handles3d.angle_handle(
                origin,
                normal,
                x_axis,
                radius,
                angles[i],
                2.0,
                on_drag=self._turned(i),
                on_release=self._turned(i),
            )
            if rotation == "uniform":
                field = self.angle
                self.value_boxes.attach(
                    self.arrows[key],
                    key,
                    lambda: field.widget.text(),
                    lambda text: self._angle_box_typed(None, text),
                )
            else:
                self.value_boxes.attach(
                    self.arrows[key],
                    key,
                    (lambda i=i: "%.2f°" % core.angles_for(self.options, i + 1)[i]),
                    (lambda text, i=i: self._angle_box_typed(i, text)),
                )

    def _turned(self, index):
        @safe
        def turned(value):
            value = round(float(value), 2)
            if self.options["rotation"] == "uniform":
                self._quiet = True
                try:
                    self.angle.set_value(value)
                finally:
                    self._quiet = False
                self.options["angle"] = value
            else:
                self._set_angle(index, value)
            self._changed()

        return turned

    def _set_angle(self, index, value):
        count = len(plastic_snap.chosen_points(self.sketch, self.indices)) if self.sketch else 0
        angles = core.angles_for(self.options, max(count, index + 1))
        angles[index] = float(value)
        self.options["angles"] = angles
        self._quiet = True
        try:
            self.angles.setText(", ".join("%g" % a for a in angles))
        finally:
            self._quiet = False

    def _angle_box_typed(self, index, text):
        if self._closed:
            return
        try:
            value = self.angle.parse(text.strip().lstrip("="))
        except ValueError as exc:
            self.message.setText("⚠ " + str(exc))
            return
        if index is None:
            self.angle.take(value)
            return
        self._set_angle(index, value)
        self._changed()

    def _attach_box(self, key):
        field = self.fields[key]
        return self.value_boxes.attach(
            self.arrows.get(key),
            key,
            lambda: field.widget.text(),
            lambda text: self._box_typed(key, text),
        )

    def _box_typed(self, key, text):
        if self._closed:
            return
        field = self.fields[key]
        try:
            value = field.parse(text.strip().lstrip("="))
        except ValueError as exc:
            self.message.setText("⚠ " + str(exc))
            return
        field.take(value)

    def _dragged(self, key):
        @safe
        def dragged(distance):
            value = max(0.1, abs(round(distance, 2)))
            self._quiet = True
            try:
                self.fields[key].set_value(value)
            finally:
                self._quiet = False
            self.options[key] = value
            self._changed()

        return dragged

    # -- OK / Cancel -------------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            return self._accept()
        except Exception as exc:
            warn("Snap Fit OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        if self.sketch is None or self._count() == 0:
            self.message.setText("⚠ Pick a sketch with points first.")
            return False
        self._timer.stop()
        if self.dirty or self.target is None:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        if self.target is None:
            self.message.setText("⚠ This snap fit cannot be built.")
            return False
        preview.recompute(self.doc)
        text = preview.failure(self.target)
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        sketch = self.sketch
        self._shown = []
        self.cleanup()
        try:
            sketch.ViewObject.Visibility = False
        except Exception:
            pass
        preview.end_transaction(self.doc)
        self._close()
        extrude.show_tip(bodies.body_of(feature))
        log("Snap Fit done")
        return True

    def reject(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
            for body in bodies.solid_bodies(self.doc):
                extrude.show_tip(body)
        except Exception as exc:
            warn("Snap Fit Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Snap Fit Cancel: %s" % exc)
        return True

    def cleanup(self):
        self._closed = True
        self._unwatch()
        for guard in (self.escape, self.undo_guard, self.enter):
            try:
                guard.remove()
            except Exception:
                pass
        self._remove_arrows()
        self.value_boxes.discard()
        self._hide_shown()
        self._show_other()
        super().cleanup()


def _followers(feature):
    try:
        from . import modify_bodies

        return modify_bodies.followers_of(feature)
    except Exception:
        return []


def _dragging(arrow):
    try:
        if getattr(arrow, "_drag", False):
            return True  # an angle handle being turned
        return bool(arrow.dragger.isActive.getValue())
    except Exception:
        return False


class ViewProviderSnapFit:
    """View provider of the Snap Fit step. Saved documents store
    "sciforge.plastic_snap_ui.ViewProviderSnapFit": keep the name stable."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("pl_snap_fit")

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


def start():
    try:
        if not commands.finish_open_dialog():
            return
        doc = App.ActiveDocument
        if doc is None or not bodies.solid_bodies(doc):
            commands.tell("Snap Fit joins two solid bodies: make the two halves first.")
            return
        Gui.Control.showDialog(SnapFitPanel(doc))
        log("Snap Fit started")
    except Exception as exc:
        warn("Snap Fit failed to start: %s" % exc)


class SnapFitCommand:
    def GetResources(self):
        return {
            "MenuText": "Snap Fit",
            "ToolTip": "Cantilever snap fits at sketch points between two bodies: the hook on "
            "one, the groove, slot or loop it catches on the other",
            "Pixmap": ui_icon_path("pl_snap_fit"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        start()


def edit(feature):
    """Open the Snap Fit dialog on an existing one (timeline double-click)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(SnapFitPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


def _register():
    """The timeline's name and icon for the step, its fields in Change Parameters."""
    try:
        from . import parameters, timeline_core

        timeline_core.KINDS.setdefault("snap_fit", ("Snap Fit", "pl_snap_fit"))
        parameters.SCIFORGE_PROPS.setdefault(
            "SnapFit",
            [
                ("BeamLength", "Beam Length"),
                ("BeamWidth", "Beam Width"),
                ("RootThickness", "Thickness at Root"),
                ("CatchDepth", "Catch Depth"),
                ("Clearance", "Clearance"),
            ],
        )
    except Exception as exc:
        warn("Snap Fit: timeline registration: %s" % exc)


_register()

COMMANDS = {"SciForge_SnapFit": SnapFitCommand}
EDITORS = {"SciForge::SnapFit": edit}
