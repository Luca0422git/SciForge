# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sweep command with Fusion's dialog.

Profile: click inside closed sketch areas (shaded blue, as for Extrude) or on flat faces of
the part. Path: click sketch lines or edges of the part; with Chain Selection on (Fusion's
default) one click takes every curve joined to it smoothly. Guide Rail (Type Path + Guide
Rail): click the Guide Rail box, then the rail's curves. Guide Surface (Type Path + Guide
Surface): click the Guide Surface box, then faces of the part; the profile keeps its angle to
them along the path (only Distance applies, like Fusion's). A click on a picked curve or area
drops it again. Whatever is selected before Sweep starts is taken (areas and faces as the
profile, curves as the path), and the single area of the newest sketch is taken by itself.

The fields follow Fusion's Sweep: Type, Profile, Path, Chain Selection, Guide Rail,
Distance (Distance One / Two when the profile sits inside the path), Taper Angle, Twist
Angle, Profile Scaling (with a guide rail), Orientation, Operation. The blue ball at the
end of the sweep slides along the path: drag it to set the distance. Sweeping into
material switches to Cut, unless you picked the operation yourself. Problems are shown in
the dialog, which then stays open.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies_row_ui, commands, curve_pick, curves, extrude, log, preview
from . import profile_pick, sweep, ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .hole_common import SelectionField
from .taskui import DistanceField, Panel, ValueBoxes

safe = curve_pick.safe("sweep")

TYPE_LABELS = [
    ("Single Path", "single"),
    ("Path + Guide Rail", "rail"),
    ("Path + Guide Surface", "surface"),
]
ORIENTATION_LABELS = [("Perpendicular", "perpendicular"), ("Parallel", "parallel")]
SCALING_LABELS = [("Scale", "scale"), ("Stretch", "stretch"), ("None", "none")]
OPERATION_LABELS = [
    ("Join", "join"),
    ("Cut", "cut"),
    ("Intersect", "intersect"),
    ("New Body", "new_body"),
    ("New Component", "new_component"),
]


# -- what is selected before the command starts --------------------------------------------------
def selected(body):
    """(profiles, path refs) from the selection, as Fusion takes them at the start."""
    used = profile_pick.used_sketches(body.Document) if body is not None else set()
    profiles, path = [], []
    for obj, short in profile_pick.picks():
        if curves.is_curve_pick(obj, short):
            path.append((obj, short))
            continue
        if extrude.is_sketch(obj):
            if short.startswith("InternalFace"):
                profiles.append((obj, short))
                continue
            if short:
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
            elif not areas and obj.Shape.Edges:
                path += [(obj, "Edge%d" % (i + 1)) for i in range(len(obj.Shape.Edges))]
        elif short.startswith("Face"):
            try:
                face = obj.Shape.getElement(short)
            except Exception:
                continue
            if face.Surface.TypeId == "Part::GeomPlane":
                profiles.append((obj, short))
    return extrude.normalize(profiles), curves.normalize(path)


def newest_single_region(body):
    """The only area of the newest sketch with an area that no feature uses yet (with the
    face's edges projected, Auto project: what the sketch's own curves close,
    extrude.taken_by_itself)."""
    if body is None:
        return None
    used = profile_pick.used_sketches(body.Document)
    for obj in reversed(body.Group):
        if not extrude.is_sketch(obj) or obj.Name in used:
            continue
        try:
            if not extrude.profile_regions(obj):
                continue  # an open sketch (a path) does not stop the search
            found = extrude.taken_by_itself(obj)
        except Exception:
            return None
        return (obj, found[0]) if len(found) == 1 else None
    return None


# -- the dialog ----------------------------------------------------------------------------------
class SweepPanel(Panel):
    title = "Sweep"
    icon = "sweep"
    last = None
    auto_pick = True

    def __init__(self, doc, feature=None):
        extra = []
        if feature is not None:
            try:
                extra = [o for o, _ in sweep.read(feature)[0] if extrude.is_sketch(o)]
            except Exception:
                extra = []
        body = commands.find_body() if feature is None else sweep.owner_body(feature)
        curve_pick.prepare_regions(body, extra)  # before the undo step opens
        super().__init__(doc, "Sweep" if feature is None else "Edit Sweep")
        SweepPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.target = feature
        self.editing = feature is not None
        self.body = commands.find_body() if feature is None else sweep.owner_body(feature)
        self.profiles = []
        self.path = []
        self.rail = []
        self.surface = []  # Path + Guide Surface: faces of the part
        self.options = dict(sweep.DEFAULTS)
        self.user_picked_operation = feature is not None
        self.error = ""
        self.dirty = False
        self._geometry_changed = False
        self.active = "profiles"
        self.handles = {}
        # Fusion shows the Distance (a share of the path) beside each ball; typed there it
        # is taken like the dialog's field (a formula too).
        self.value_boxes = ValueBoxes(self, default="distance")
        self.picker = None
        self.overlay = None
        self.observer = None
        self.layout_info = None
        self._quiet = False
        self._shown = []
        stored = None
        if feature is not None:
            try:
                self.profiles, self.path, self.rail, read = sweep.read(feature)
                stored = read.pop("bodies", None)
                self.options.update(read)
                if self.options.get("type") == "surface":
                    self.surface, self.rail = self.rail, []
                self.profiles = extrude.expand_whole(self.profiles)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
            self._show_sketches()
        self.options["bodies"] = None  # the Objects To Cut row says it at each build
        self._build_form()
        if feature is not None:
            self.bodies_row.read(stored, feature)
        self._show_options()
        self._watch()
        if feature is not None:
            self._refresh_picks()
            self._update_layout()
            self._make_handles()
            self._test_bodies()  # the row starts from the bodies it was saved with
            self._show_bodies_row()
        else:
            self._start()

    # -- sketches shown while editing ------------------------------------------------------------
    def _show_sketches(self):
        """While a sweep is edited, its sketches are shown so their curves can be clicked
        (Fusion shows them too). They hide again at the end."""
        for obj, _ in self.profiles + self.path + self.rail:
            if not extrude.is_sketch(obj):
                continue
            try:
                if obj.ViewObject is not None and not obj.ViewObject.Visibility:
                    obj.ViewObject.Visibility = True
                    self._shown.append(obj)
            except Exception:
                pass

    def _hide_shown(self):
        for obj in self._shown:
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass
        self._shown = []

    # -- form --------------------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.type = curve_pick.combo(TYPE_LABELS, self.options["type"])
        self.type.setObjectName("SciForgeSweep_type")
        form.addRow("Type", self.type)
        self.fields = {
            "profiles": SelectionField(self, "profiles", "Select profile"),
            "path": SelectionField(self, "path", "Select path"),
            "rail": SelectionField(self, "rail", "Select guide rail"),
            "surface": SelectionField(self, "surface", "Select guide surface"),
        }
        for name, field in self.fields.items():
            field.button.setObjectName("SciForgeSweep_" + name)
            field.clear.setObjectName("SciForgeSweep_clear_" + name)
        form.addRow("Profile", self.fields["profiles"].widget)
        form.addRow("Path", self.fields["path"].widget)
        self.chain = curve_pick.checkbox("Chain Selection", self.options["chain"])
        self.chain.setObjectName("SciForgeSweep_chain")
        self.chain.setToolTip("One click takes every curve joined smoothly to the clicked one")
        form.addRow("", self.chain)
        self.rail_label = QtWidgets.QLabel("Guide Rail")
        form.addRow(self.rail_label, self.fields["rail"].widget)
        self.surface_label = QtWidgets.QLabel("Guide Surface")
        form.addRow(self.surface_label, self.fields["surface"].widget)
        self.hint = QtWidgets.QLabel(
            "Click inside sketch areas (shaded blue) or on flat faces for the profile, then "
            "click the path's curves."
        )
        self.hint.setWordWrap(True)
        form.addRow(self.hint)
        self.distance_label = QtWidgets.QLabel("Distance")
        self.distance = curve_pick.RatioBox(self.options["distance"], formulas=True)
        self.distance.setObjectName("SciForgeSweep_distance")
        self.distance.setToolTip("How far along the path: 1 is the whole path")
        form.addRow(self.distance_label, self.distance)
        self.distance2_label = QtWidgets.QLabel("Distance Two")
        self.distance2 = curve_pick.RatioBox(self.options["distance2"], formulas=True)
        self.distance2.setObjectName("SciForgeSweep_distance2")
        form.addRow(self.distance2_label, self.distance2)
        self.taper = DistanceField(self.options["taper"], unit="deg", on_change=self._value_typed)
        self.taper.widget.setObjectName("SciForgeSweep_taper")
        self.taper_label = QtWidgets.QLabel("Taper Angle")
        form.addRow(self.taper_label, self.taper.widget)
        self.twist = DistanceField(self.options["twist"], unit="deg", on_change=self._value_typed)
        self.twist.widget.setObjectName("SciForgeSweep_twist")
        self.twist_label = QtWidgets.QLabel("Twist Angle")
        form.addRow(self.twist_label, self.twist.widget)
        self.scaling = curve_pick.combo(SCALING_LABELS, self.options["scaling"])
        self.scaling.setObjectName("SciForgeSweep_scaling")
        self.scaling_label = QtWidgets.QLabel("Profile Scaling")
        form.addRow(self.scaling_label, self.scaling)
        self.orientation = curve_pick.combo(ORIENTATION_LABELS, self.options["orientation"])
        self.orientation.setObjectName("SciForgeSweep_orientation")
        self.orientation_label = QtWidgets.QLabel("Orientation")
        form.addRow(self.orientation_label, self.orientation)
        self.operation = curve_pick.combo(OPERATION_LABELS, self.options["operation"])
        self.operation.setObjectName("SciForgeSweep_operation")
        form.addRow("Operation", self.operation)
        # Fusion's Objects To Cut: the bodies a Join / Cut / Intersect acts on
        self.fields["bodies"] = SelectionField(self, "bodies", "No bodies")
        self.fields["bodies"].button.setObjectName("SciForgeSweep_bodies")
        self.fields["bodies"].clear.setObjectName("SciForgeSweep_clear_bodies")
        self.bodies_row = bodies_row_ui.BodiesRow(self, form, self.fields["bodies"], "sweep")
        self.formulas = QtWidgets.QLabel("")  # values that follow a parameter
        self.formulas.setWordWrap(True)
        self.formulas.setStyleSheet("color: #b8c7d9;")
        form.addRow(self.formulas)
        self.finish_layout()
        # Fusion takes a parameter or a formula in every value field ("share", "share / 2").
        self.formula_error = ""
        self.formula_inputs = [
            preview.FormulaInput(self, "distance", curve_pick.RatioField(self.distance)),
            preview.FormulaInput(self, "distance2", curve_pick.RatioField(self.distance2)),
            preview.FormulaInput(self, "taper", self.taper),
            preview.FormulaInput(self, "twist", self.twist),
        ]
        for key, widget in (
            ("distance", self.distance),
            ("distance2", self.distance2),
            ("taper", self.taper.widget),
            ("twist", self.twist.widget),
        ):
            edit = widget.findChild(QtWidgets.QLineEdit)
            if edit is not None:
                edit.textEdited.connect(lambda text, key=key: self._text_edited(key, text))
        lines = self.message.fontMetrics().lineSpacing()
        self.message.setMinimumHeight(lines * 3 + 4)
        self.type.currentIndexChanged.connect(self._kind_changed)
        self.orientation.currentIndexChanged.connect(self._kind_changed)
        self.scaling.currentIndexChanged.connect(self._kind_changed)
        self.operation.activated.connect(self._operation_picked)
        self.distance.valueChanged.connect(self._value_typed)
        self.distance2.valueChanged.connect(self._value_typed)
        self.chain.toggled.connect(self._chain_toggled)

    def _show_options(self):
        self._quiet = True
        try:
            curve_pick.set_combo(self.type, self.options["type"])
            curve_pick.set_combo(self.orientation, self.options["orientation"])
            curve_pick.set_combo(self.scaling, self.options["scaling"])
            curve_pick.set_combo(self.operation, self.options["operation"])
            self.distance.setValue(self.options["distance"])
            self.distance2.setValue(self.options["distance2"])
            self.taper.set_value(self.options["taper"])
            self.twist.set_value(self.options["twist"])
            self.chain.setChecked(self.options["chain"])
        finally:
            self._quiet = False
        self._update_visibility()
        self.show_formulas()

    def _update_visibility(self):
        kind = self.type.currentData()
        rail = kind == "rail"
        surface = kind == "surface"
        single = kind == "single"
        two = self.layout_info is not None and self.layout_info.two_sides and single
        parallel = self.orientation.currentData() == "parallel"
        self.distance_label.setText("Distance One" if two else "Distance")
        for widget, show in (
            (self.rail_label, rail),
            (self.fields["rail"].widget, rail),
            (self.surface_label, surface),
            (self.fields["surface"].widget, surface),
            (self.distance2_label, two),
            (self.distance2, two),
            (self.taper_label, single),
            (self.taper.widget, single),
            (self.twist_label, single),
            (self.twist.widget, single),
            (self.scaling_label, rail),
            (self.scaling, rail),
            (self.orientation_label, single),
            (self.orientation, single),
        ):
            widget.setVisible(show)
        self.twist.widget.setEnabled(not parallel)
        self.twist.widget.setToolTip(
            "Twist needs Orientation: Perpendicular" if parallel else "Turn of the profile"
        )

    def _collect(self):
        self.options["type"] = self.type.currentData()
        self.options["orientation"] = self.orientation.currentData()
        self.options["scaling"] = self.scaling.currentData()
        self.options["operation"] = self.operation.currentData()
        self.options["distance"] = float(self.distance.value())
        self.options["distance2"] = float(self.distance2.value())
        self.options["taper"] = float(self.taper.value())
        twist = float(self.twist.value())
        self.options["twist"] = 0.0 if self.options["orientation"] == "parallel" else twist
        self.options["chain"] = bool(self.chain.isChecked())

    # -- formulas (preview.FormulaInput calls formula_typed / _cleared / _failed) -----------------
    def show_formulas(self):
        """Fusion shows the formula in the field; the number boxes cannot, so the values that
        follow a parameter are listed under the fields."""
        try:
            shown = {
                "distance": True,
                "distance2": not self.distance2.isHidden(),
                "taper": not self.taper.widget.isHidden(),
                "twist": not self.twist.widget.isHidden(),
            }
            rows = [
                "%s = %s" % (sweep.FORMULAS[k][2], v)
                for k, v in sorted((self.options.get("expressions") or {}).items())
                if v and shown.get(k, False)
            ]
            self.formulas.setText("\n".join(rows))
            self.formulas.setVisible(bool(rows))
        except Exception as exc:
            warn("sweep formulas: %s" % exc)

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
        self.show_formulas()
        self._sync_handles()
        self._changed()

    def formula_cleared(self, key):
        self.drop_formula(key)

    def formula_failed(self, key, text):
        # Kept until the field gets a value again (a preview rebuild must not wipe it).
        self.formula_error = text
        self.message.setText("⚠ " + text)

    def _text_edited(self, key, text):
        """A plain number typed over a formula wins at once: the preview and OK use it
        without waiting for the field to be left."""
        try:
            from . import parameters

            if self._closed or not text.strip() or not parameters.is_plain_number(text):
                return
            self.drop_formula(key, update=False)
        except Exception as exc:
            warn("sweep field: %s" % exc)

    # -- selection boxes -------------------------------------------------------------------------
    def activate(self, name):
        self.active = name
        self._show_active()
        self._show_bodies_row()

    def _test_bodies(self):
        """The Objects To Cut row: which bodies the sweep's solid is in."""
        if self.options.get("operation") in ("join", "cut", "intersect"):
            self.bodies_row.update(
                lambda: sweep.tool_shape(self.profiles, self.path, self._guide(), self.options),
                self.target,
            )

    def _show_bodies_row(self):
        if getattr(self, "bodies_row", None) is None:
            return
        self.bodies_row.show(
            self.options.get("operation"),
            self.active == "bodies",
            bool(self.profiles) and bool(self.path),
        )

    def _show_active(self):
        for name, field in self.fields.items():
            field.set_active(name == self.active)

    def clear_field(self, name):
        if name == "bodies":
            self.bodies_row.clear_all(self.options.get("operation"))
            self.activate("bodies")
            self._changed()
            return
        if name == "profiles":
            self.profiles = []
        elif name == "path":
            self.path = []
        elif name == "surface":
            self.surface = []
        else:
            self.rail = []
        self._picks_changed()
        self.activate(name)

    def _guide(self):
        """What follows the path besides the profile: the guide rail's curves, or the guide
        surface's faces (sweep.py takes either in its rail_refs)."""
        kind = self.type.currentData()
        if kind == "surface":
            return self.surface
        return self.rail if kind == "rail" else []

    # -- start ---------------------------------------------------------------------------------------
    def _start(self):
        if self.body is None:
            self.message.setText("Create a sketch first (Create Sketch).")
            return
        profiles, path = selected(self.body)
        if not profiles and self.auto_pick:
            single = newest_single_region(self.body)
            profiles = [single] if single else []
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        self.profiles = profiles
        self.path = path
        self._refresh_picks()
        self._next_field()
        self._collect()
        self._auto_operation()
        if self.profiles and self.path:
            self._picks_changed()
            self._timer.stop()
            self._recompute()  # started from a selection: the preview is there at once

    def _next_field(self):
        if not self.profiles:
            self.activate("profiles")
        elif not self.path:
            self.activate("path")
        elif self.type.currentData() == "rail" and not self.rail:
            self.activate("rail")
        elif self.type.currentData() == "surface" and not self.surface:
            self.activate("surface")
        else:
            self.activate("path")

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        view = Gui.ActiveDocument.ActiveView
        extra = [obj for obj, _ in self.profiles if extrude.is_sketch(obj)]
        sketches = profile_pick.candidate_sketches(self.body, extra)
        try:
            self.overlay = curve_pick.CurveOverlay(view)
        except Exception as exc:
            warn("sweep: curve highlight unavailable: %s" % exc)
        try:
            self.picker = curve_pick.RegionPicker(
                view,
                sketches,
                lambda sketch, sub: QtCore.QTimer.singleShot(
                    0, lambda: self._region_clicked(sketch, sub)
                ),
                occluder=self._occluder,
                skip=self._not_an_area,
            )
        except Exception as exc:
            warn("sweep: profile shading unavailable: %s" % exc)

    def _not_an_area(self, position):
        """A press that is meant for a handle or a curve, not the area around it (or one
        that picks a body for the Objects To Cut row)."""
        if self.active == "bodies":
            return True
        if any(handle.hit(position) for handle in self.handles.values()):
            return True
        return curve_pick.line_under_mouse(self.doc, position)

    def _occluder(self):
        base = self._base_feature()
        if base is None or base.Shape.isNull():
            return None
        return curves.to_global(base.Shape, base)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        if self.picker is not None:
            self.picker.remove()
            self.picker = None
        if self.overlay is not None:
            self.overlay.remove()
            self.overlay = None

    # -- picks -----------------------------------------------------------------------------------------
    def _region_clicked(self, sketch, sub):
        if self._closed:
            return
        try:
            self._toggle_profile((sketch, sub))
        except Exception as exc:
            warn("sweep pick: %s" % exc)

    def _selection_changed(self):
        if self._closed:
            return
        try:
            picks = [(o, s) for o, s in profile_pick.picks() if o.Document is self.doc]
            if not picks:
                return
            Gui.Selection.clearSelection()
            if any(handle.busy() for handle in self.handles.values()):
                return  # the click went to a handle
            if self.picker is not None and self.picker.clicked_region_recently():
                return  # the click picked an area (FreeCAD selected what is under it)
            if self.active == "bodies":
                said = self.bodies_row.picked(picks[-1][0], self.options.get("operation"))
                self.message.setText(said)
                if not said:
                    self._changed()
                return
            for obj, short in picks:
                self._picked(obj, short)
        except Exception as exc:
            warn("sweep pick: %s" % exc)

    def _picked(self, obj, short):
        if self.active == "surface" and short.startswith("Face") and not extrude.is_sketch(obj):
            ref = curve_pick.base_element(self._base_feature(), obj, short)
            if ref is None:
                self.message.setText("⚠ That face belongs to this sweep itself.")
                return
            self._toggle_surface(ref)
            return
        if curves.is_curve_pick(obj, short):
            ref = (obj, short)
            from . import sketch_companions

            # a sketch's curves, also its 3D curves (sketch_companions, sketch-2): as they are
            if not extrude.is_sketch(obj) and not sketch_companions.is_companion(obj):
                ref = curve_pick.base_element(self._base_feature(), obj, short)
                if ref is None:
                    self.message.setText(
                        "⚠ That edge is made by this sweep. Pick a sketch line or an edge of "
                        "the part as it was before."
                    )
                    return
            box = "rail" if self.active == "rail" else "path"
            self._toggle_curve(box, ref)
            return
        if extrude.is_sketch(obj):
            if short.startswith("InternalFace"):
                self._toggle_profile((obj, short))
            return
        if short.startswith("Face"):
            ref = curve_pick.base_element(self._base_feature(), obj, short)
            if ref is None:
                self.message.setText("⚠ That face belongs to this sweep itself.")
                return
            face = ref[0].Shape.getElement(ref[1])
            if face.Surface.TypeId != "Part::GeomPlane":
                self.message.setText("⚠ Only flat faces can be swept. Pick a flat face.")
                return
            self._toggle_profile(ref)

    def _toggle_profile(self, ref):
        if any(sub == "" and obj is ref[0] for obj, sub in self.profiles):
            self.profiles = extrude.expand_whole(self.profiles)
        keys = [extrude.key(p) for p in self.profiles]
        if extrude.key(ref) in keys:
            self.profiles = [p for p in self.profiles if extrude.key(p) != extrude.key(ref)]
        else:
            self.profiles = self.profiles + [ref]
        self._picks_changed()
        if self.profiles and not self.path:
            self.activate("path")

    def _toggle_surface(self, ref):
        keys = [(o.Name, s) for o, s in self.surface]
        if (ref[0].Name, ref[1]) in keys:
            self.surface = [r for r in self.surface if (r[0].Name, r[1]) != (ref[0].Name, ref[1])]
        else:
            self.surface = self.surface + [ref]
        self.activate("surface")
        self._picks_changed()

    def _toggle_curve(self, box, ref):
        refs = list(self.path if box == "path" else self.rail)
        names = [ref[1]]
        if self.chain.isChecked():
            names = curves.chain(ref[0], ref[1])
        keys = {(o.Name, s) for o, s in refs}
        if (ref[0].Name, ref[1]) in keys:
            drop = {(ref[0].Name, n) for n in names}
            refs = [r for r in refs if (r[0].Name, r[1]) not in drop]
        else:
            refs += [(ref[0], n) for n in names if (ref[0].Name, n) not in keys]
        if box == "path":
            self.path = refs
        else:
            self.rail = refs
        # A path clicked before the profile leaves the Profile box waiting (lit up), as the
        # profile is still to be picked.
        self.activate("profiles" if not self.profiles else box)
        self._picks_changed()

    def _refresh_picks(self):
        count = len(self.profiles)
        self.fields["profiles"].set_text("%d selected" % count if count else "")
        self.fields["path"].set_text(curves.label(self.path))
        self.fields["rail"].set_text(curves.label(self.rail))
        count = len(self.surface)
        self.fields["surface"].set_text(
            "" if not count else ("1 face" if count == 1 else "%d faces" % count)
        )
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
        if self.overlay is not None:
            rail = self.rail if self.type.currentData() == "rail" else []
            for name, refs, color in (
                ("path", self.path, curve_pick.PATH_COLOR),
                ("rail", rail, curve_pick.RAIL_COLOR),
            ):
                try:
                    edges = curves.refs_edges(refs)
                except curves.CurveError:
                    edges = []
                self.overlay.show(name, edges, color)
        self._show_active()

    def _base_feature(self):
        """The body's solid step just before this sweep."""
        body = self._source_body()
        if self.target is not None and sweep.owner_body(self.target) is body:
            return self.target.BaseFeature
        if body is None:
            return None
        tip = body.Tip
        if tip is not None and tip is self.target:
            return tip.BaseFeature
        return tip

    def _source_body(self):
        if self.profiles:
            body = sweep.owner_body(self.profiles[0][0])
            if body is not None:
                return body
        return self.body

    def _check_picks(self):
        try:
            sweep.check_profiles(self.profiles)
            if self.path:
                self._collect()
                sweep.plan(self.profiles, self.path, self.options)
        except (sweep.SweepError, curves.CurveError) as exc:
            self.error = str(exc)
            self.message.setText("⚠ " + self.error)
            return self.error
        self.error = ""
        self.message.setText("")
        return ""

    def _waiting_for(self):
        """What still has to be picked, in words ('' when everything is there)."""
        if not self.profiles:
            return "Pick the profile: click inside a sketch area or on a flat face."
        if not self.path:
            return "Pick the path: click a sketch line or an edge of the part."
        if self.type.currentData() == "rail" and not self.rail:
            return "Pick the guide rail: click the Guide Rail box, then a line or an edge."
        if self.type.currentData() == "surface" and not self.surface:
            return "Pick the guide surface: click the Guide Surface box, then faces of the part."
        return ""

    def _picks_changed(self):
        self._refresh_picks()
        self._update_layout()
        waiting = self._waiting_for()
        if waiting:
            if self.target is not None and not self.editing:
                sweep.remove(self.target)
                self.target = None
                self.schedule()
            self.error = waiting if self.editing else ""
            self.message.setText(("⚠ " + waiting) if self.editing else "")
            if self.profiles and not self.editing:
                self._check_picks()
            self._remove_handles()
            return
        if self._check_picks():
            self._remove_handles()
            return
        self._changed(new_geometry=True)

    def _update_layout(self):
        self.layout_info = None
        if self.profiles and self.path:
            try:
                self._collect()
                self.layout_info = sweep.plan(self.profiles, self.path, self.options)
            except Exception:
                self.layout_info = None
        self._update_visibility()

    # -- changes -----------------------------------------------------------------------------------
    @safe
    def _kind_changed(self, *_):
        if self._quiet:
            return
        if self.type.currentData() == "rail" and not self.rail and self.path:
            self.activate("rail")
        elif self.type.currentData() == "surface" and not self.surface and self.path:
            self.activate("surface")
        elif self.active in ("rail", "surface") and self.active != self.type.currentData():
            self.activate("path")
        self._picks_changed()  # a guide rail still to pick takes the preview away

    @safe
    def _value_typed(self, *_):
        if self._quiet:
            return
        self._sync_handles()
        self._changed()

    @safe
    def _operation_picked(self, _index):
        self.user_picked_operation = True
        self._changed()

    @safe
    def _chain_toggled(self, *_):
        self.options["chain"] = bool(self.chain.isChecked())

    def _auto_operation(self):
        if self.user_picked_operation:
            return
        base = self._base_feature()
        shape = None
        if base is not None and not base.Shape.isNull():
            shape = curves.to_global(base.Shape, base)
        if shape is None or not shape.Solids:
            wanted = "new_body"  # Fusion shows it from the start when there is no solid yet
        elif not self.profiles or not self.path:
            return
        else:
            try:
                wanted = sweep.auto_operation(
                    shape, self.profiles, self.path, self._guide(), self.options
                )
            except Exception:
                return
        if wanted != self.options["operation"]:
            self.options["operation"] = wanted
            self._quiet = True
            curve_pick.set_combo(self.operation, wanted)
            self._quiet = False

    def _changed(self, new_geometry=False):
        self._update_visibility()
        self.show_formulas()  # a field hidden now (Distance Two) lists no formula
        self._collect()
        self._auto_operation()
        self.dirty = True
        if new_geometry:
            self._geometry_changed = True
        self.schedule()

    def _recompute(self):
        if self._closed:
            return
        try:
            if self.dirty:
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
        if self._waiting_for():
            return
        try:
            before = self.target
            operation = self.options["operation"]
            self._test_bodies()
            options = dict(self.options, bodies=self.bodies_row.for_build(operation))
            self.target = sweep.build(
                self.profiles,
                self.path,
                self._guide(),
                options,
                feature=self.target,
                hide=False,
            )
            self.error = self._misses()
            if before is None or self.target is not before:
                self._geometry_changed = True
        except (sweep.SweepError, curves.CurveError, ValueError) as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This sweep cannot be built: %s" % exc
        self.bodies_row.built(self.target)
        self.bodies_row.show_cut(self.options["operation"], bool(self.error))
        self._show_bodies_row()
        if self.error and self.target is not None:
            actual = self._feature_operation()
            if actual != self.options["operation"]:
                self.options["operation"] = actual
                self._quiet = True
                curve_pick.set_combo(self.operation, actual)
                self._quiet = False

    def _feature_operation(self):
        try:
            return sweep.read(self.target)[3]["operation"]
        except Exception:
            return self.options["operation"]

    def _misses(self):
        """Fusion refuses a Cut or Intersect that does not reach into the part (FreeCAD's own
        pipe would just leave the part as it was); the reason, or ''."""
        operation = self.options["operation"]
        if operation not in ("cut", "intersect"):
            return ""
        if self.bodies_row.touched(operation):
            return ""  # it goes through bodies (Objects To Cut lists them)
        if self.bodies_row.problem:
            return self.bodies_row.problem
        base = self._base_feature()
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            return "There is no part to %s yet." % operation
        try:
            tool = sweep.tool_shape(self.profiles, self.path, self._guide(), self.options)
            inside = curves.to_global(base.Shape, base).common(tool).Volume
        except Exception:
            return ""
        if inside < 1e-6:
            return (
                "The sweep does not reach into the part, so %s would change nothing. Move the "
                "profile or the path, or use Join." % ("Cut" if operation == "cut" else "Intersect")
            )
        return ""

    def picks_sketch_areas(self):
        """Sketch areas (profiles) can be clicked while the Profile box takes the clicks; otherwise
        a click goes through them to what is behind (sketch_area_pick)."""
        return not self._closed and self.active == "profiles"

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

    # -- handles ------------------------------------------------------------------------------------
    def _remove_handles(self):
        for handle in self.handles.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.handles = {}

    def _wanted_handles(self):
        if self.target is None or self.layout_info is None or self._waiting_for():
            return set()
        if self.layout_info.two_sides and self.type.currentData() == "single":
            return {"distance", "distance2"}
        return {"distance"}

    def _handles_wrong(self):
        if any(h.dragging() for h in self.handles.values()):
            return False
        return set(self.handles) != self._wanted_handles()

    def _side_samples(self, side):
        """[(0..1, point)] along side one (or two) from the profile to the path's end."""
        info = self.layout_info
        fwd = info.forward()
        start = info.start()
        if side == "distance":
            reach = fwd.length - start if not info.closed else fwd.length
            if info.at_end:
                reach = fwd.length
        else:
            reach = start
        count = 64
        samples = []
        for k in range(count + 1):
            f = k / float(count)
            s = start + reach * f if side == "distance" else start - reach * f
            samples.append((f, fwd.point_at(s)))
        return samples

    def _make_handles(self):
        if self._closed:
            return
        if any(h.dragging() for h in self.handles.values()):
            return
        self._remove_handles()
        wanted = self._wanted_handles()
        if not wanted:
            return
        try:
            faces = sweep.profile_faces(self.profiles)
            size = max(2.0, min(faces[0].BoundBox.DiagonalLength * 0.2, 8.0))
            for name in sorted(wanted):
                value = self.options[name]
                self.handles[name] = curve_pick.PathHandle(
                    self._side_samples(name),
                    value,
                    size,
                    on_drag=lambda v, n=name: self._dragged(n, v),
                    on_release=lambda v, n=name: self._dragged(n, v),
                )
                box = self.distance if name == "distance" else self.distance2
                self.value_boxes.attach(
                    self.handles[name],
                    name,
                    box.text,
                    lambda text, n=name: self._box_typed(n, text),
                )
        except Exception as exc:
            warn("sweep handles unavailable: %s" % exc)

    def _box_typed(self, key, text):
        if self._closed:
            return
        for formula in self.formula_inputs:
            if formula.key == key:
                formula.take(text)
                return

    def _sync_handles(self):
        for name, handle in self.handles.items():
            if not handle.dragging():
                handle.set_value(float(getattr(self, name).value()))

    @safe
    def _dragged(self, name, value):
        value = round(max(0.0, min(1.0, value)), 3)
        self.drop_formula(name, update=False)  # a dragged value is a plain number again
        box = self.distance if name == "distance" else self.distance2
        self._quiet = True
        try:
            box.setValue(value)
        finally:
            self._quiet = False
        self._changed()

    # -- OK / Cancel ----------------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            return self._accept()
        except Exception as exc:
            warn("Sweep OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        waiting = self._waiting_for()
        if waiting:
            self.message.setText("⚠ " + waiting)
            return False
        self._timer.stop()
        self._collect()
        if self.dirty or self.target is None:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        if self.target is None:
            self.message.setText("⚠ This sweep cannot be built.")
            return False
        preview.recompute(self.doc)
        text = _plain(preview.failure(self.target))
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        sweep.hide_sketches(self.profiles, self.path, self.rail)
        self._shown = []
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        body = sweep.owner_body(feature)
        if body is not None:
            extrude.show_tip(body)
            if body is not self.body:
                try:
                    from . import components

                    components.activate_body(body)  # and its (new) component
                except Exception as exc:
                    warn("could not activate %s: %s" % (body.Label, exc))
        log("%s done" % self.title)
        return True

    def reject(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            body = self._source_body()
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
            if body is not None and curves.owner_body(body) is not None:
                extrude.show_tip(body)
        except Exception as exc:
            warn("Sweep Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Sweep Cancel: %s" % exc)
        return True

    def cleanup(self):
        self._closed = True
        self._unwatch()
        self.bodies_row.cleanup()
        for guard in (self.escape, self.undo_guard, self.enter):
            try:
                guard.remove()
            except Exception:
                pass
        self._remove_handles()
        self.value_boxes.discard()
        self._hide_shown()
        super().cleanup()


# FreeCAD's failure texts, said the way a Fusion user needs them.
PLAIN = (
    (
        "multiple solids",
        "This would make separate solids. Sweep a profile that touches the part, or use New "
        "Body.",
    ),
    ("nothing to subtract", "There is nothing to cut yet. Use Join or New Body."),
    ("Pipe could not be built", "The profile cannot follow this path. Check the path's corners."),
    ("not a solid", "Nothing is left: the sweep does not touch the body here."),
)


def _plain(text):
    for needle, said in PLAIN:
        if needle.lower() in (text or "").lower():
            return said
    return text


class ViewProviderSweep:
    """View provider of SciForge's own sweep feature."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("sweep")

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


class SweepCommand:
    def GetResources(self):
        return {
            "MenuText": "Sweep",
            "ToolTip": "Move a profile along a path (and a guide rail): distance, taper, twist, "
            "orientation; join, cut, intersect or new body",
            "Pixmap": ui_icon_path("sweep"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            if commands.find_body() is None:
                commands.tell("Sweep needs a profile and a path: use Create Sketch first.")
                return
            Gui.Control.showDialog(SweepPanel(App.ActiveDocument))
            log("sweep started")
        except Exception as exc:
            warn("Sweep failed to start: %s" % exc)


def edit(feature):
    """Open the Sweep dialog on an existing sweep (timeline double-click)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(SweepPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


COMMANDS = {"SciForge_Sweep": SweepCommand}
EDITORS = {
    "PartDesign::AdditivePipe": edit,
    "PartDesign::SubtractivePipe": edit,
    "SciForge::Sweep": edit,
}
