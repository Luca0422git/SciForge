# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loft command with Fusion's dialog.

Profiles: click them in the order the loft goes through: inside closed sketch areas (shaded
blue), flat faces of the part, or a sketch point (only first or last: a dome or a cone). They
are listed in that order; move one up or down or take it out with the buttons next to the
list, or click it again in the 3D view. Guide Type Rails: click the Rails box, then curves
the side must run along; Centerline: one curve the profiles stay square to. Closed lofts the
last profile back to the first. Tangent Edges Merge lofts profile curves joined smoothly
into one side face. First Profile / Last Profile set how the loft leaves the first profile and
meets the last (Fusion's end conditions): a sketch profile Connected or Direction (Takeoff
Weight, Takeoff Angle), a face of the part Connected (G0), Tangent (G1) or Curvature (G2), a
point Sharp or Point Tangent (a dome), with a Tangency Weight; with rails or a centerline too
(they bend the loft near its ends), and on a closed loft at the first profile (Direction: the
loop passes through it that way). Rails may be sketch curves or edges of any body. Lofting
into material switches to Cut, unless you picked the operation yourself. Problems are shown
in the dialog, which then stays open.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies_row_ui, commands, curve_pick, curves, extrude, log, loft, loft_ends_core
from . import preview, profile_pick, ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .hole_common import SelectionField
from .taskui import DistanceField, Panel

safe = curve_pick.safe("loft")

GUIDE_LABELS = [("Rails", "rails"), ("Centerline", "centerline")]
OPERATION_LABELS = [
    ("Join", "join"),
    ("Cut", "cut"),
    ("Intersect", "intersect"),
    ("New Body", "new_body"),
    ("New Component", "new_component"),
]
END_TITLES = (("start", "First Profile"), ("end", "Last Profile"))
MERGE_TIP = (
    "Profile curves joined smoothly (a slot's lines and arcs) loft into one smooth side face; "
    "off: one face per curve. Inspect's volume of a merged spline side can be a few % off "
    "(OpenCASCADE's measurement)."
)


END_PROPS = {
    "start_weight": "StartWeight",
    "start_angle": "StartAngle",
    "end_weight": "EndWeight",
    "end_angle": "EndAngle",
}


def profile_text(index, profile):
    obj, sub = profile
    if sub.startswith("Vertex"):
        what = "point of %s" % obj.Label
    elif extrude.is_sketch(obj):
        what = "%s (area)" % obj.Label if sub else "%s (whole sketch)" % obj.Label
    else:
        what = "face of %s" % obj.Label
    return "%d   %s" % (index + 1, what)


def selected():
    """Profiles from the selection, in the order they were selected (Fusion keeps it)."""
    found = []
    for obj, short in profile_pick.picks():
        if extrude.is_sketch(obj) and short.startswith("InternalFace"):
            found.append((obj, short))
        elif short.startswith("Vertex"):
            found.append((obj, short))
        elif short.startswith("Face") and not extrude.is_sketch(obj):
            try:
                face = obj.Shape.getElement(short)
            except Exception:
                continue
            if face.Surface.TypeId == "Part::GeomPlane":
                found.append((obj, short))
    return loft.normalize(found)


def _picked_points():
    """{(object name, short element name): the clicked 3D point} of the current selection."""
    points = {}
    try:
        for sel in Gui.Selection.getSelectionEx():
            for name, point in zip(sel.SubElementNames, sel.PickedPoints):
                obj, short = profile_pick.resolve(sel.Object, name)
                if obj is not None:
                    points[(obj.Name, short)] = point
    except Exception:
        pass
    return points


class LoftPanel(Panel):
    title = "Loft"
    icon = "loft"
    last = None

    def __init__(self, doc, feature=None):
        extra = []
        if feature is not None:
            try:
                extra = [o for o, _ in loft.read(feature)[0] if extrude.is_sketch(o)]
            except Exception:
                extra = []
        body = commands.find_body() if feature is None else loft.owner_body(feature)
        curve_pick.prepare_regions(body, extra)  # before the undo step opens
        super().__init__(doc, "Loft" if feature is None else "Edit Loft")
        LoftPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.target = feature
        self.editing = feature is not None
        self.body = commands.find_body() if feature is None else loft.owner_body(feature)
        self.profiles = []
        self.rails = []
        self.centerline = []
        self.options = dict(loft.DEFAULTS)
        self.formulas = {}  # end value -> the formula typed for it
        self.user_picked_operation = feature is not None
        self.error = ""
        self.dirty = False
        self.active = "profiles"
        self.picker = None
        self.overlay = None
        self.observer = None
        self._quiet = False
        self._shown = []
        stored = None
        if feature is not None:
            try:
                self.profiles, self.rails, self.centerline, read = loft.read(feature)
                stored = read.pop("bodies", None)
                self.options.update(read)
                for key, prop in END_PROPS.items():
                    text = preview.formula_of(feature, prop)
                    if text:
                        self.formulas[key] = text
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
            self._test_bodies()  # the row starts from the bodies it was saved with
            self._show_bodies_row()
        else:
            self._start()

    # -- sketches shown while editing -------------------------------------------------------------
    def _show_sketches(self):
        for obj, _ in self.profiles + self.rails + self.centerline:
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

    # -- form ---------------------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.fields = {
            "profiles": SelectionField(self, "profiles", "Select profiles"),
            "rails": SelectionField(self, "rails", "Select rails"),
            "centerline": SelectionField(self, "centerline", "Select centerline"),
        }
        for name, field in self.fields.items():
            field.button.setObjectName("SciForgeLoft_" + name)
            field.clear.setObjectName("SciForgeLoft_clear_" + name)
        form.addRow("Profiles", self.fields["profiles"].widget)
        row = QtWidgets.QWidget()
        box = QtWidgets.QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("SciForgeLoft_list")
        self.list.setMinimumHeight(90)
        self.list.setMaximumHeight(130)
        box.addWidget(self.list, 1)
        buttons = QtWidgets.QVBoxLayout()
        self.up = QtWidgets.QToolButton()
        self.up.setText("▲")
        self.up.setToolTip("Move the profile earlier in the loft")
        self.up.setObjectName("SciForgeLoft_up")
        self.down = QtWidgets.QToolButton()
        self.down.setText("▼")
        self.down.setToolTip("Move the profile later in the loft")
        self.down.setObjectName("SciForgeLoft_down")
        self.remove = QtWidgets.QToolButton()
        self.remove.setText("✕")
        self.remove.setToolTip("Take the profile out of the loft")
        self.remove.setObjectName("SciForgeLoft_remove")
        for widget in (self.up, self.down, self.remove):
            buttons.addWidget(widget)
        buttons.addStretch(1)
        box.addLayout(buttons)
        form.addRow(row)
        self.guide = curve_pick.combo(GUIDE_LABELS, self.options["guide"])
        self.guide.setObjectName("SciForgeLoft_guide")
        form.addRow("Guide Type", self.guide)
        self.rails_label = QtWidgets.QLabel("Rails")
        form.addRow(self.rails_label, self.fields["rails"].widget)
        self.centerline_label = QtWidgets.QLabel("Centerline")
        form.addRow(self.centerline_label, self.fields["centerline"].widget)
        self.chain = curve_pick.checkbox("Chain Selection", self.options["chain"])
        self.chain.setObjectName("SciForgeLoft_chain")
        form.addRow("", self.chain)
        self.hint = QtWidgets.QLabel(
            "Click the profiles in loft order: sketch areas (shaded blue), flat faces or a "
            "sketch point at an end."
        )
        self.hint.setWordWrap(True)
        form.addRow(self.hint)
        self.closed = curve_pick.checkbox("Closed", self.options["closed"])
        self.closed.setObjectName("SciForgeLoft_closed")
        form.addRow("", self.closed)
        self.merge = curve_pick.checkbox("Tangent Edges Merge", self.options.get("merge", False))
        self.merge.setObjectName("SciForgeLoft_merge")
        self.merge.setToolTip(MERGE_TIP)
        form.addRow("", self.merge)
        self.ends = {}
        self.formula_inputs = {}
        for end, title in END_TITLES:
            row = {"kind": None}
            row["combo"] = QtWidgets.QComboBox()
            row["combo"].setObjectName("SciForgeLoft_%s_condition" % end)
            row["label"] = QtWidgets.QLabel(title)
            row["weight"] = DistanceField(
                self.options[end + "_weight"], unit="", on_change=self._end_value_changed
            )
            row["weight"].widget.setObjectName("SciForgeLoft_%s_weight" % end)
            row["weight_label"] = QtWidgets.QLabel("Takeoff Weight")
            row["angle"] = DistanceField(
                self.options[end + "_angle"], unit="deg", on_change=self._end_value_changed
            )
            row["angle"].widget.setObjectName("SciForgeLoft_%s_angle" % end)
            row["angle_label"] = QtWidgets.QLabel("Takeoff Angle")
            form.addRow(row["label"], row["combo"])
            form.addRow(row["weight_label"], row["weight"].widget)
            form.addRow(row["angle_label"], row["angle"].widget)
            row["combo"].activated.connect(self._end_picked)
            self.ends[end] = row
            # Fusion's value fields take a parameter or a formula ("w * 2"): the loft then
            # follows the parameter (an expression on the loft's property)
            for name in ("weight", "angle"):
                key = "%s_%s" % (end, name)
                self.formula_inputs[key] = preview.FormulaInput(self, key, row[name])
        self.operation = curve_pick.combo(OPERATION_LABELS, self.options["operation"])
        self.operation.setObjectName("SciForgeLoft_operation")
        form.addRow("Operation", self.operation)
        # Fusion's Objects To Cut: the bodies a Join / Cut / Intersect acts on
        self.fields["bodies"] = SelectionField(self, "bodies", "No bodies")
        self.fields["bodies"].button.setObjectName("SciForgeLoft_bodies")
        self.fields["bodies"].clear.setObjectName("SciForgeLoft_clear_bodies")
        self.bodies_row = bodies_row_ui.BodiesRow(self, form, self.fields["bodies"], "loft")
        self.finish_layout()
        lines = self.message.fontMetrics().lineSpacing()
        self.message.setMinimumHeight(lines * 3 + 4)
        self.guide.currentIndexChanged.connect(self._guide_changed)
        self.closed.toggled.connect(self._value_changed)
        self.merge.toggled.connect(self._value_changed)
        self.operation.activated.connect(self._operation_picked)
        self.up.clicked.connect(lambda *_: self._move(-1))
        self.down.clicked.connect(lambda *_: self._move(1))
        self.remove.clicked.connect(self._remove_row)

    def _show_options(self):
        self._quiet = True
        try:
            curve_pick.set_combo(self.guide, self.options["guide"])
            curve_pick.set_combo(self.operation, self.options["operation"])
            self.closed.setChecked(self.options["closed"])
            self.merge.setChecked(bool(self.options.get("merge")))
            self.chain.setChecked(self.options["chain"])
            for end, row in self.ends.items():
                row["weight"].set_value(self.options[end + "_weight"])
                row["angle"].set_value(self.options[end + "_angle"])
        finally:
            self._quiet = False
        self._update_visibility()

    def _update_visibility(self):
        rails = self.guide.currentData() == "rails"
        for widget, show in (
            (self.rails_label, rails),
            (self.fields["rails"].widget, rails),
            (self.centerline_label, not rails),
            (self.fields["centerline"].widget, not rails),
        ):
            widget.setVisible(show)
        self._update_ends()

    # -- end conditions (first / last profile) ------------------------------------------------
    def _end_kind(self, end):
        if len(self.profiles) < 2:
            return None
        obj, sub = self.profiles[0] if end == "start" else self.profiles[-1]
        if sub.startswith("Vertex"):
            return "point"
        return "sketch" if extrude.is_sketch(obj) else "face"

    def _ends_possible(self, end):
        """Every end takes a condition, except the last profile of a closed loft (the loop
        goes on from it back to the first)."""
        return not (self.closed.isChecked() and end == "end")

    def _end_choices(self, end, kind):
        # Every choice of the profile stays offered (a closed loft refuses the ones it cannot
        # take, with the reason): ticking Closed and back keeps what was chosen.
        return list(loft_ends_core.LABELS.get(kind, []))

    def _update_ends(self):
        """Each end's choices follow its profile (sketch / face / point); the weight and the
        angle show for the conditions that use them."""
        for end, row in self.ends.items():
            kind = self._end_kind(end)
            combo = row["combo"]
            choices = self._end_choices(end, kind)
            keys = [key for _label, key in choices]
            if keys != [combo.itemData(i) for i in range(combo.count())]:
                row["kind"] = kind
                self._quiet = True
                try:
                    combo.clear()
                    for label, key in choices:
                        combo.addItem(label, key)
                finally:
                    self._quiet = False
            wanted = self.options.get(end + "_condition", "free")
            if kind is None or wanted not in keys:
                wanted = "free"
                self.options[end + "_condition"] = "free"
            self._quiet = True
            try:
                curve_pick.set_combo(combo, wanted)
            finally:
                self._quiet = False
            possible = self._ends_possible(end)
            shown = kind is not None and possible
            row["label"].setVisible(shown)
            combo.setVisible(shown)
            condition = combo.currentData() if possible else "free"
            row["weight_label"].setText(
                "Takeoff Weight" if condition == "direction" else "Tangency Weight"
            )
            for widget in (row["weight_label"], row["weight"].widget):
                widget.setVisible(shown and condition not in (None, "free"))
            for widget in (row["angle_label"], row["angle"].widget):
                widget.setVisible(shown and condition == "direction")

    @safe
    def _end_picked(self, _index):
        if self._quiet:
            return
        for end, row in self.ends.items():
            self.options[end + "_condition"] = row["combo"].currentData() or "free"
        self._changed()

    @safe
    def _end_value_changed(self, _value):
        if self._quiet:
            return
        self._changed()

    # preview.FormulaInput calls these for the weight and angle fields
    def formula_typed(self, key, text, value):
        self.formulas[key] = text
        log("loft: %s = %s" % (key.replace("_", " "), text))
        self._changed()

    def formula_cleared(self, key):
        if self.formulas.pop(key, None) is not None:
            self._changed()

    def formula_failed(self, key, message):
        log("loft: %s: %s" % (key.replace("_", " "), message))
        self.message.setText("⚠ " + message)

    def _apply_formulas(self):
        """The formulas typed for the end values, as expressions on the loft (SciForge's own
        loft only: FreeCAD's has no end conditions)."""
        if self.target is None or not loft.is_own(self.target):
            return
        for key, prop in END_PROPS.items():
            text = self.formulas.get(key, "")
            if self.options.get(key.split("_")[0] + "_condition", "free") == "free":
                text = ""
            try:
                preview.set_formula(self.target, prop, text)
            except Exception as exc:
                warn("loft formula: %s" % exc)

    def _collect(self):
        self.options["guide"] = self.guide.currentData()
        self.options["closed"] = bool(self.closed.isChecked())
        self.options["operation"] = self.operation.currentData()
        self.options["chain"] = bool(self.chain.isChecked())
        self.options["merge"] = bool(self.merge.isChecked())
        for end, row in self.ends.items():
            condition = row["combo"].currentData() if row["kind"] is not None else None
            self.options[end + "_condition"] = condition or "free"
            self.options[end + "_weight"] = float(row["weight"].value())
            self.options[end + "_angle"] = float(row["angle"].value())

    # -- selection boxes -------------------------------------------------------------------------
    def activate(self, name):
        self.active = name
        for key, field in self.fields.items():
            field.set_active(key == name)
        self._show_bodies_row()

    def _test_bodies(self):
        """The Objects To Cut row: which bodies the loft's solid is in."""
        if self.options.get("operation") in ("join", "cut", "intersect"):
            self.bodies_row.update(
                lambda: loft.tool_shape(self.profiles, self.rails, self.centerline, self.options),
                self.target,
            )

    def _show_bodies_row(self):
        if getattr(self, "bodies_row", None) is None:
            return
        self.bodies_row.show(
            self.options.get("operation"), self.active == "bodies", len(self.profiles) >= 2
        )

    def clear_field(self, name):
        if name == "bodies":
            self.bodies_row.clear_all(self.options.get("operation"))
            self.activate("bodies")
            self._changed()
            return
        if name == "profiles":
            self.profiles = []
        elif name == "rails":
            self.rails = []
        else:
            self.centerline = []
        self._picks_changed()
        self.activate(name)

    def _guide_box(self):
        return "rails" if self.guide.currentData() == "rails" else "centerline"

    # -- start -----------------------------------------------------------------------------------------
    def _start(self):
        if self.body is None:
            self.message.setText("Create a sketch first (Create Sketch).")
            return
        self.profiles = selected()
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        self.activate("profiles")
        self._refresh_picks()
        self._collect()
        self._auto_operation()
        if len(self.profiles) >= 2:
            self._picks_changed()
            self._timer.stop()
            self._recompute()

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
            warn("loft: curve highlight unavailable: %s" % exc)
        try:
            self.picker = curve_pick.RegionPicker(
                view,
                sketches,
                lambda sketch, sub: QtCore.QTimer.singleShot(
                    0, lambda: self._region_clicked(sketch, sub)
                ),
                occluder=self._occluder,
                skip=lambda position: self.active == "bodies"
                or curve_pick.line_under_mouse(self.doc, position),
            )
        except Exception as exc:
            warn("loft: profile shading unavailable: %s" % exc)

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

    # -- picks -------------------------------------------------------------------------------------------
    def _region_clicked(self, sketch, sub):
        if self._closed:
            return
        try:
            self._toggle_profile((sketch, sub))
        except Exception as exc:
            warn("loft pick: %s" % exc)

    def _selection_changed(self):
        if self._closed:
            return
        try:
            picks = [(o, s) for o, s in profile_pick.picks() if o.Document is self.doc]
            if not picks:
                return
            self._points = _picked_points()
            Gui.Selection.clearSelection()
            if self.picker is not None and self.picker.clicked_region_recently():
                return
            if self.active == "bodies":
                said = self.bodies_row.picked(picks[-1][0], self.options.get("operation"))
                self.message.setText(said)
                if not said:
                    self._changed()
                return
            for obj, short in picks:
                self._picked(obj, short)
        except Exception as exc:
            warn("loft pick: %s" % exc)

    def _picked(self, obj, short):
        base = self._base_feature()
        if short.startswith("Edge"):
            ref = (obj, short)
            if not extrude.is_sketch(obj) and self._own_body(obj):
                # an edge of the loft's own body: as it is before the loft
                ref = curve_pick.base_element(base, obj, short)
                if ref is None:
                    self.message.setText("⚠ That edge is made by this loft. Pick another one.")
                    return
            box = self.active if self.active in ("rails", "centerline") else self._guide_box()
            self._toggle_curve(box, ref)
            return
        if short.startswith("Vertex"):
            self._toggle_profile((obj, short))
            return
        if extrude.is_sketch(obj):
            if short.startswith("InternalFace"):
                self._toggle_profile((obj, short))
            return
        if short.startswith("Face"):
            if self.active in ("rails", "centerline"):
                # a rail is an edge: a click on a face a hair from one of its edges takes the
                # edge (an edge lying on another body's face, as a prism's edge touching the
                # slot's round end, is drawn at the same depth and the face took the click)
                point = getattr(self, "_points", {}).get((obj.Name, short))
                ref = (obj, short)
                if self._own_body(obj):  # as the body is before the loft
                    ref = curve_pick.base_element(base, obj, short)
                edge = self._edge_beside(ref[0], ref[1], point) if ref else None
                if edge is not None:
                    self._toggle_curve(self.active, (ref[0], edge))
                    return
            ref = curve_pick.base_element(base, obj, short)
            if ref is None:
                self.message.setText("⚠ That face belongs to this loft itself.")
                return
            face = ref[0].Shape.getElement(ref[1])
            if face.Surface.TypeId != "Part::GeomPlane":
                self.message.setText("⚠ Only flat faces can be lofted. Pick a flat face.")
                return
            self._toggle_profile(ref)

    def _edge_beside(self, obj, short, point):
        """The name of the edge of face `short` of `obj` within 6 pixels of the clicked
        `point`, or None."""
        import Part

        if point is None:
            return None
        view = Gui.ActiveDocument.ActiveView
        try:
            x, y = view.getPointOnViewport(point)
            reach = (view.getPointOnFocalPlane(x, y) - view.getPointOnFocalPlane(x + 6, y)).Length
        except Exception:
            reach = 0.5
        face = obj.Shape.getElement(short)
        best, near = None, reach
        for edge in face.Edges:
            for i, candidate in enumerate(obj.Shape.Edges):
                if not candidate.isSame(edge):
                    continue
                d = extrude._to_global(edge, obj).distToShape(Part.Vertex(point))[0]
                if d <= near:
                    best, near = "Edge%d" % (i + 1), d
        return best

    def _own_body(self, obj):
        """True for an object of the body the loft is built in (or its preview body)."""
        body = loft.owner_body(obj)
        if body is None:
            return False
        if body is self._source_body():
            return True
        target = self.target
        return target is not None and loft.owner_body(target) is body

    def _toggle_profile(self, ref):
        keys = [loft.key(p) for p in self.profiles]
        if loft.key(ref) in keys:
            self.profiles = [p for p in self.profiles if loft.key(p) != loft.key(ref)]
        else:
            self.profiles = self.profiles + [ref]
        self.activate("profiles")
        self._picks_changed()

    def _toggle_curve(self, box, ref):
        refs = list(self.rails if box == "rails" else self.centerline)
        names = curves.chain(ref[0], ref[1]) if self.chain.isChecked() else [ref[1]]
        keys = {(o.Name, s) for o, s in refs}
        if (ref[0].Name, ref[1]) in keys:
            drop = {(ref[0].Name, n) for n in names}
            refs = [r for r in refs if (r[0].Name, r[1]) not in drop]
        elif box == "centerline":
            refs = [(ref[0], n) for n in names]  # one centerline: a new click replaces it
        else:
            refs += [(ref[0], n) for n in names if (ref[0].Name, n) not in keys]
        if box == "rails":
            self.rails = refs
        else:
            self.centerline = refs
        self.activate(box)
        self._picks_changed()

    # -- the profile list ------------------------------------------------------------------------------
    @safe
    def _move(self, step):
        row = self.list.currentRow()
        if row < 0 or not 0 <= row + step < len(self.profiles):
            return
        items = list(self.profiles)
        items[row], items[row + step] = items[row + step], items[row]
        self.profiles = items
        self._picks_changed()
        self.list.setCurrentRow(row + step)

    @safe
    def _remove_row(self, *_):
        row = self.list.currentRow()
        if row < 0 or row >= len(self.profiles):
            return
        self.profiles = self.profiles[:row] + self.profiles[row + 1 :]
        self._picks_changed()
        if self.profiles:
            self.list.setCurrentRow(min(row, len(self.profiles) - 1))

    def _refresh_picks(self):
        current = self.list.currentRow()
        self.list.blockSignals(True)
        try:
            self.list.clear()
            for i, profile in enumerate(self.profiles):
                self.list.addItem(profile_text(i, profile))
            if 0 <= current < self.list.count():
                self.list.setCurrentRow(current)
        finally:
            self.list.blockSignals(False)
        count = len(self.profiles)
        self.fields["profiles"].set_text("%d selected" % count if count else "")
        self.fields["rails"].set_text(curves.label(self.rails))
        self.fields["centerline"].set_text(curves.label(self.centerline))
        if self.picker is not None:
            self.picker.set_selected(
                [
                    extrude.key(p)
                    for p in self.profiles
                    if extrude.is_sketch(p[0]) and "Face" in p[1]
                ]
            )
            faces = []
            for obj, sub in self.profiles:
                if not extrude.is_sketch(obj) and sub.startswith("Face"):
                    face = profile_pick.global_face(obj, sub)
                    if face is not None:
                        faces.append(face)
            self.picker.show_faces(faces)
        if self.overlay is not None:
            rails = self.rails if self.guide.currentData() == "rails" else []
            line = self.centerline if self.guide.currentData() == "centerline" else []
            for name, refs, color in (
                ("rails", rails, curve_pick.RAIL_COLOR),
                ("centerline", line, curve_pick.PATH_COLOR),
            ):
                try:
                    edges = curves.refs_edges(refs)
                except curves.CurveError:
                    edges = []
                self.overlay.show(name, edges, color)
        for key, field in self.fields.items():
            field.set_active(key == self.active)

    def _base_feature(self):
        body = self._source_body()
        if self.target is not None and loft.owner_body(self.target) is body:
            return self.target.BaseFeature
        if body is None:
            return None
        tip = body.Tip
        if tip is not None and tip is self.target:
            return tip.BaseFeature
        return tip

    def _source_body(self):
        for obj, _ in self.profiles:
            body = loft.owner_body(obj)
            if body is not None:
                return body
        return self.body

    def _waiting_for(self):
        if len(self.profiles) < 2:
            return "Pick at least two profiles, in the order the loft goes through them."
        return ""

    def _picks_changed(self):
        self._refresh_picks()
        self._update_visibility()
        waiting = self._waiting_for()
        if waiting:
            if self.target is not None and not self.editing:
                loft.remove(self.target)
                self.target = None
                self.schedule()
            self.error = waiting if self.editing else ""
            self.message.setText(("⚠ " + waiting) if self.editing else "")
            return
        self._changed()

    # -- changes ------------------------------------------------------------------------------------
    @safe
    def _guide_changed(self, *_):
        if self._quiet:
            return
        if self.active in ("rails", "centerline"):
            self.activate(self._guide_box())
        self._picks_changed()

    @safe
    def _value_changed(self, *_):
        if self._quiet:
            return
        self._changed()

    @safe
    def _operation_picked(self, _index):
        self.user_picked_operation = True
        self._changed()

    def _auto_operation(self):
        if self.user_picked_operation:
            return
        base = self._base_feature()
        shape = None
        if base is not None and not base.Shape.isNull():
            shape = curves.to_global(base.Shape, base)
        if shape is None or not shape.Solids:
            wanted = "new_body"  # Fusion shows it from the start when there is no solid yet
        elif len(self.profiles) < 2:
            return
        else:
            try:
                wanted = loft.auto_operation(
                    shape, self.profiles, self.rails, self.centerline, self.options
                )
            except Exception:
                return
        if wanted != self.options["operation"]:
            self.options["operation"] = wanted
            self._quiet = True
            curve_pick.set_combo(self.operation, wanted)
            self._quiet = False

    def _changed(self):
        self._update_visibility()
        self._collect()
        self._auto_operation()
        self.dirty = True
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
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if self._waiting_for():
            return
        try:
            operation = self.options["operation"]
            self._test_bodies()
            options = dict(self.options, bodies=self.bodies_row.for_build(operation))
            if self.target is not None:
                # first: a formula replaced by a typed number lets go of its property (the
                # build then sets the number), a new one drives it
                self._apply_formulas()
            self.target = loft.build(
                self.profiles,
                self.rails,
                self.centerline,
                options,
                feature=self.target,
                hide=False,
            )
            self._apply_formulas()
            self.error = self._misses()
        except (loft.LoftError, curves.CurveError, ValueError) as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This loft cannot be built: %s" % exc
        self.bodies_row.built(self.target)
        self.bodies_row.show_cut(self.options["operation"], bool(self.error))
        self._show_bodies_row()
        if self.error and self.target is not None:
            try:
                actual = loft.read(self.target)[3]["operation"]
            except Exception:
                actual = self.options["operation"]
            if actual != self.options["operation"]:
                self.options["operation"] = actual
                self._quiet = True
                curve_pick.set_combo(self.operation, actual)
                self._quiet = False

    def _misses(self):
        """Fusion refuses a Cut or Intersect that does not reach into the part (FreeCAD's own
        loft would just leave the part as it was); the reason, or ''."""
        if self.options["operation"] not in ("cut", "intersect"):
            return ""
        if self.bodies_row.touched(self.options["operation"]):
            return ""  # it goes through bodies (Objects To Cut lists them)
        if self.bodies_row.problem:
            return self.bodies_row.problem
        base = self._base_feature()
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            return "There is no part to %s yet." % self.options["operation"]
        try:
            tool = loft.tool_shape(self.profiles, self.rails, self.centerline, self.options)
            inside = curves.to_global(base.Shape, base).common(tool).Volume
        except Exception:
            return ""
        if inside < 1e-6:
            return (
                "The loft does not reach into the part, so %s would change nothing. Move the "
                "profiles or use Join."
                % ("Cut" if self.options["operation"] == "cut" else "Intersect")
            )
        return ""

    def picks_sketch_areas(self):
        """Sketch areas (profiles) can be clicked while the Profiles box takes the clicks; otherwise
        a click goes through them to what is behind (sketch_area_pick)."""
        return not self._closed and self.active == "profiles"

    def feature(self):
        return self.target

    def show_status(self):
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = _plain(preview.failure(self.target))
        self.message.setText("⚠ " + text if text else "")

    # -- OK / Cancel ------------------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            return self._accept()
        except Exception as exc:
            warn("Loft OK: %s" % exc)
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
            self.message.setText("⚠ This loft cannot be built.")
            return False
        preview.recompute(self.doc)
        text = _plain(preview.failure(self.target))
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        loft.hide_sketches(self.profiles, self.rails, self.centerline)
        self._shown = []
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        body = loft.owner_body(feature)
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
            warn("Loft Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Loft Cancel: %s" % exc)
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
        self._hide_shown()
        super().cleanup()


PLAIN = (
    (
        "multiple solids",
        "This would make separate solids. Loft profiles that touch the part, or use New Body.",
    ),
    ("At least one section", "Pick at least two profiles."),
    ("same amount of wires", "Every profile needs the same number of holes."),
    ("not a solid", "Nothing is left: the loft does not touch the body here."),
)


def _plain(text):
    for needle, said in PLAIN:
        if needle.lower() in (text or "").lower():
            return said
    return text


class ViewProviderLoft:
    """View provider of SciForge's own loft feature."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("loft")

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


class LoftCommand:
    def GetResources(self):
        return {
            "MenuText": "Loft",
            "ToolTip": "Blend through profiles in order (with rails or a centerline); join, "
            "cut, intersect or new body",
            "Pixmap": ui_icon_path("loft"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            if commands.find_body() is None:
                commands.tell("Loft needs profiles: use Create Sketch first.")
                return
            Gui.Control.showDialog(LoftPanel(App.ActiveDocument))
            log("loft started")
        except Exception as exc:
            warn("Loft failed to start: %s" % exc)


def edit(feature):
    """Open the Loft dialog on an existing loft (timeline double-click)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(LoftPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


COMMANDS = {"SciForge_Loft": LoftCommand}
EDITORS = {
    "PartDesign::AdditiveLoft": edit,
    "PartDesign::SubtractiveLoft": edit,
    "SciForge::Loft": edit,
}
