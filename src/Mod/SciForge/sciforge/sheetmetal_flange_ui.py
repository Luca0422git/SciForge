# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Flange command (SHEET METAL > CREATE > Flange), one dialog for every mode.

What is picked decides the mode, as in Fusion: a click inside a closed sketch profile makes a
base flange (a plate of the rule's thickness), a click on an open sketch line takes its chain
for a contour flange (every sharp corner bent with the rule's radius), a click on an edge of a
sheet metal body makes an edge flange (bend + wall, mitred where two picked edges meet). The
options of the mode show below; the blue arrow sets the height (edge) or distance (contour)
by dragging, with its value box; the preview is the real step, so OK keeps it and Cancel / Esc
leaves the design as it was. A choice that cannot be built is explained in the dialog, which
stays open. The geometry is sheetmetal_form.py, the step sheetmetal_flange.py.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, curve_pick, curves, extrude, log, preview, profile_pick, sheetmetal
from . import sheetmetal_core as core
from . import sheetmetal_flange as flange
from . import sheetmetal_form as form
from . import ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .hole_common import SelectionField
from .taskui import ArrowDragger, DistanceField, Panel, ValueBoxes

safe = curve_pick.safe("Flange")

MODE_TEXT = {
    None: "Click a closed sketch profile (base flange), an open sketch line (contour flange) "
    "or edges of a sheet metal body (edge flange).",
    "base": "Base flange: a plate of the rule's thickness.",
    "contour": "Contour flange: the line's sharp corners become bends of the rule's radius.",
    "edge": "Edge flange: a bend and a wall on each picked edge.",
}
OPERATIONS = [("New Body", "new_body"), ("New Component", "new_component"), ("Join", "join")]


def _pairs(key):
    return [(label, value) for value, label in flange.LABELS[key].items()]


class FlangePanel(Panel):
    title = "Flange"
    icon = "sm_flange"
    last = None

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Flange" if feature is None else "Edit Flange")
        FlangePanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.target = feature
        self.editing = feature is not None
        self.body = commands.find_body() if feature is None else flange.owner_body(feature)
        self.kind = None
        self.refs = []
        self.to_object = None  # (object, sub) the flange runs to (To Object)
        self.offset_refs = [None, None]  # Two Offsets: the two faces / planes
        self.active = "selection"
        self.made_with = None  # (kind, operation, rule) the preview step was made with
        self.component = self._component()
        self.rule_name = flange.default_rule_name(doc, self.component)
        self.operation = "new_body"
        self.options = flange.defaults("base", self._rule(self.rule_name))
        self.error = ""
        self.dirty = False
        self.arrows = {}
        self.value_boxes = ValueBoxes(self, default="height")
        self.picker = None
        self.observer = None
        self.overlay = None
        self._quiet = False
        self.rows = {}
        self.formula_inputs = {}
        self.formulas = {}  # field key -> formula typed ("" once a number replaced it)
        self.owns_body = False
        # the design's rules when the dialog opened: a library rule tried in the Rule box and
        # then left for another is taken out of the design again on OK (QA)
        self.rules_at_start = {r["name"] for r in sheetmetal.design_rules(doc)}
        self.attached = None  # (edge, point): a contour drawn from the end of a sheet edge
        if feature is not None:
            try:
                self.options = flange.options_of(feature)
                self.kind = self.options["kind"]
                self.refs = flange.picks_of(feature)
                if feature.Target:
                    subs = list(feature.Target[1]) if len(feature.Target) > 1 else []
                    self.to_object = (feature.Target[0], subs[0] if subs else "")
                self.offset_refs = flange.offset_refs_of(feature)
                self._check_attached()
                self.rule_name = sheetmetal.body_rule_name(self.body) or self.rule_name
                self.made_with = (self.kind, "existing", self.rule_name)
                # the flange that made its body: its Rule box swaps the body's rule (Fusion
                # swaps rules, never detaches them)
                self.owns_body = flange.made_body(feature)
                for key, (prop, _g, _d) in list(flange.LENGTHS.items()) + [
                    ("angle", ("Angle", None, None))
                ]:
                    text = preview.formula_of(feature, prop)
                    if text:
                        self.formulas[key] = text
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._build_form()
        self._show_options()
        self._watch()
        self._refresh_picks()
        if feature is not None:
            self._make_arrows()
        else:
            self._start()

    # -- helpers -----------------------------------------------------------------------------
    def _component(self):
        try:
            from . import components

            return components.active_component(self.doc)
        except Exception:
            return None

    def _rule(self, name):
        rule = sheetmetal.find_rule(self.doc, name) or core.library_rule(name)
        try:
            return core.evaluated(rule) if rule else None
        except ValueError:
            return None

    def _join_body(self):
        return sheetmetal.find_sheet_body(self.doc, active=self.body)

    # -- form ---------------------------------------------------------------------------------
    def _row(self, key, label, widget):
        label_widget = QtWidgets.QLabel(label) if label else None
        if label_widget is not None:
            self.layout.addRow(label_widget, widget)
        else:
            self.layout.addRow("", widget)
        widget.setObjectName("SciForgeFlange_" + key)
        self.rows[key] = (label_widget, widget)
        return widget

    def _combo(self, key, label, pairs, value):
        box = curve_pick.combo(pairs, value)
        self._row(key, label, box)
        box.currentIndexChanged.connect(self._value_typed)
        return box

    def _length(self, key, label, value, unit="mm"):
        field = DistanceField(value, unit=unit, on_change=self._value_typed)
        self._row(key, label, field.widget)
        setattr(self, "f_" + key, field)
        # a parameter or a formula typed here drives the value (Fusion's value fields)
        self.formula_inputs[key] = preview.FormulaInput(self, key, field)
        return field

    # -- formulas typed in the fields (preview.FormulaInput) ----------------------------------
    def formula_typed(self, key, text, value):
        self.formulas[key] = text
        self._changed(new_geometry=True)

    def formula_cleared(self, key):
        if key in self.formulas:
            self.formulas[key] = ""
            self._changed(new_geometry=True)

    def formula_failed(self, key, message):
        self.message.setText("⚠ %s" % message)

    def _store_formulas(self):
        """Put the formulas on the step's properties (an empty one removes it)."""
        if self.target is None:
            return
        for key, text in self.formulas.items():
            prop = "Angle" if key == "angle" else flange.LENGTHS.get(key, (None,))[0]
            if prop:
                preview.set_formula(self.target, prop, text)

    def _check(self, key, text, value):
        box = curve_pick.checkbox(text, value)
        self._row(key, "", box)
        box.toggled.connect(self._value_typed)
        return box

    def _build_form(self):
        self.mode = QtWidgets.QLabel(MODE_TEXT[None])
        self.mode.setWordWrap(True)
        self._row("mode", "", self.mode)
        self.field = SelectionField(self, "selection", "Select profile or edges")
        self.field.set_active(True)
        self._row("selection", "Selection", self.field.widget)
        self.field.button.setObjectName("SciForgeFlange_selection_button")
        self.rule = self._combo("rule", "Rule", self._rule_pairs(), self.rule_name)
        self.operation_box = self._combo("operation", "Operation", OPERATIONS, self.operation)
        o = self.options
        self.orientation = self._combo(
            "orientation", "Orientation", _pairs("orientation"), o["orientation"]
        )
        self._length("distance", "Distance", o["distance"])
        self.direction = self._combo("direction", "Direction", _pairs("direction"), o["direction"])
        self._length("distance2", "Distance 2", o["distance2"])
        self.extent = self._combo("extent", "Height Extent", _pairs("extent"), o["extent"])
        self._length("height", "Height", o["height"])
        self.object_field = SelectionField(self, "object", "Select face or plane")
        self._row("object", "Object", self.object_field.widget)
        self.object_field.button.setObjectName("SciForgeFlange_object_button")
        self._length("target_offset", "Offset", o["target_offset"])
        self.datum = self._combo("datum", "Height Datum", _pairs("datum"), o["datum"])
        self.position = self._combo("position", "Bend Position", _pairs("position"), o["position"])
        self._length("angle", "Angle", o["angle"], unit="deg")
        self.flip = self._check("flip", "Flip", o["flip"])
        self.width_type = self._combo("width_type", "Width", _pairs("width_type"), o["width_type"])
        self._length("width", "Width", o["width"])
        self._length("distance1", "Distance 1", o["distance1"])
        self._length("width2", "Distance 2", o["width2"])
        self.ref_fields = []
        for i in (1, 2):
            box = SelectionField(self, "ref%d" % i, "Select face or plane")
            self._row("ref%d" % i, "Offset Object %d" % i, box.widget)
            box.button.setObjectName("SciForgeFlange_ref%d_button" % i)
            self.ref_fields.append(box)
        self.ov_radius = self._check(
            "override_bend_radius", "Bend Radius", o["override_bend_radius"]
        )
        self._length("bend_radius", "Radius", o["bend_radius"])
        self.ov_relief = self._check(
            "override_bend_relief", "Bend Relief", o["override_bend_relief"]
        )
        self.relief_shape = self._combo(
            "relief_shape", "Relief Shape", _pairs("relief_shape"), o["relief_shape"]
        )
        self._length("relief_width", "Relief Width", o["relief_width"])
        self._length("relief_depth", "Relief Depth", o["relief_depth"])
        self._length("relief_remnant", "Relief Remnant", o["relief_remnant"])
        self.ov_corner = self._check(
            "override_corner_relief", "Corner Relief (2 bends)", o["override_corner_relief"]
        )
        self.corner_shape = self._combo(
            "corner_shape", "Corner Shape", _pairs("corner_shape"), o["corner_shape"]
        )
        self.corner_placement = self._combo(
            "corner_placement", "Placement", _pairs("corner_placement"), o["corner_placement"]
        )
        self._length("corner_size", "Relief Size", o["corner_size"])
        self.ov_corner3 = self._check(
            "override_corner3_relief", "Corner Relief (3 bends)", o["override_corner3_relief"]
        )
        self.corner3_shape = self._combo(
            "corner3_shape", "Corner Shape", _pairs("corner3_shape"), o["corner3_shape"]
        )
        self._length("corner3_radius", "Relief Radius", o["corner3_radius"])
        self.f_corner_size.widget.setToolTip(
            "Measured on the flat pattern; for Round, the relief's diameter (SciForge's choice)"
        )
        self.finish_layout()
        lines = self.message.fontMetrics().lineSpacing()
        self.message.setMinimumHeight(lines * 3 + 4)

    def _rule_pairs(self):
        pairs, names = [], set()
        for rule in sheetmetal.design_rules(self.doc):
            pairs.append((rule["name"], rule["name"]))
            names.add(rule["name"])
        for rule in core.LIBRARY:
            if rule["name"] not in names:
                pairs.append((rule["name"] + " (Library)", rule["name"]))
        return pairs

    def _show_options(self):
        self._quiet = True
        try:
            o = self.options
            for key in flange.LABELS:
                box = self.rows.get(key, (None, None))[1]
                if isinstance(box, QtWidgets.QComboBox) and key in o:
                    curve_pick.set_combo(box, o[key])
            for key in flange.LENGTHS:
                field = getattr(self, "f_" + key, None)
                if field is not None:
                    field.set_value(o[key])
            self.f_angle.set_value(o["angle"])
            for key in flange.BOOLS:
                box = self.rows.get(key, (None, None))[1]
                if box is not None:
                    box.setChecked(bool(o[key]))
            curve_pick.set_combo(self.rule, self.rule_name)
            curve_pick.set_combo(self.operation_box, self.operation)
        finally:
            self._quiet = False
        self._update_visibility()

    def _shown_keys(self):
        o = self.options
        keys = {"mode", "selection"}
        if self.kind in ("base", "contour"):
            keys |= {"orientation"}
            if not self.editing:
                keys |= {"operation"}
                if self.operation_box.currentData() != "join":
                    keys.add("rule")
            elif self.owns_body:
                keys.add("rule")
        if self.kind == "contour" and self.attached is not None:
            keys -= {"orientation"}  # the side that carries the sheet on
            keys.add("override_bend_radius")
        elif self.kind == "contour":
            keys |= {"distance", "direction", "flip", "override_bend_radius"}
            if o["direction"] == "two_sides":
                keys.add("distance2")
            if o["override_bend_radius"]:
                keys.add("bend_radius")
        if self.kind == "edge":
            keys |= {"extent", "position", "angle", "flip", "width_type"}
            if o["extent"] == "to_object":
                keys |= {"object", "target_offset"}
            else:
                keys |= {"height", "datum"}
            if o["width_type"] == "symmetric":
                keys.add("width")
            elif o["width_type"] in ("two_sides", "two_offsets"):
                keys |= {"distance1", "width2"}
                if o["width_type"] == "two_offsets":
                    keys |= {"ref1", "ref2"}
            keys |= {"override_bend_radius", "override_bend_relief", "override_corner_relief"}
            keys.add("override_corner3_relief")
            if o["override_bend_radius"]:
                keys.add("bend_radius")
            if o["override_bend_relief"]:
                keys |= {"relief_shape", "relief_width", "relief_depth", "relief_remnant"}
            if o["override_corner_relief"]:
                keys |= {"corner_shape", "corner_size"}
                if o["corner_shape"] in ("round", "square"):
                    keys.add("corner_placement")
            if o["override_corner3_relief"]:
                keys.add("corner3_shape")
                if o["corner3_shape"] == "round_with_radius":
                    keys.add("corner3_radius")
        return keys

    def _update_visibility(self):
        shown = self._shown_keys()
        for key, (label, widget) in self.rows.items():
            visible = key in shown
            widget.setVisible(visible)
            if label is not None:
                label.setVisible(visible)
        self.mode.setText(
            "Contour flange on the edge of %s: it runs the whole edge, bent out of the sheet."
            % (self._join_body().Label if self._join_body() is not None else "the body")
            if self.kind == "contour" and self.attached is not None
            else MODE_TEXT[self.kind]
        )
        offsets = self.options.get("width_type") == "two_offsets"
        for key, word in (("distance1", 1), ("width2", 2)):
            label = self.rows[key][0]
            if label is not None:
                label.setText(("Offset %d" if offsets else "Distance %d") % word)
        join = self.operation_box.model().item(2)
        if join is not None:
            join.setEnabled(self._join_body() is not None)

    def _collect(self):
        o = self.options
        for key in flange.LABELS:
            box = self.rows.get(key, (None, None))[1]
            if isinstance(box, QtWidgets.QComboBox) and box.currentData() is not None:
                o[key] = box.currentData()
        for key in flange.LENGTHS:
            field = getattr(self, "f_" + key, None)
            if field is not None:
                o[key] = float(field.value())
        o["angle"] = float(self.f_angle.value())
        for key in flange.BOOLS:
            box = self.rows.get(key, (None, None))[1]
            if box is not None:
                o[key] = bool(box.isChecked())
        o["kind"] = self.kind or "base"
        self.rule_name = self.rule.currentData() or self.rule_name
        self.operation = self.operation_box.currentData() or "new_body"
        return dict(o)

    # -- selection boxes --------------------------------------------------------------------
    def activate(self, name):
        self.active = name
        self.field.set_active(name == "selection")
        self.object_field.set_active(name == "object")
        for i, box in enumerate(self.ref_fields):
            box.set_active(name == "ref%d" % (i + 1))
        if self.picker is not None:
            self.picker.paused = name != "selection"

    def clear_field(self, name):
        if name in ("ref1", "ref2"):
            self.offset_refs[int(name[3]) - 1] = None
            self._refresh_picks()
            self._changed()
            return
        if name == "object":
            self.to_object = None
            self._refresh_picks()
            self._changed()
            return
        self.refs = []
        self._picks_changed()

    # -- start and picking ------------------------------------------------------------------
    def _start(self):
        picks = [(o, s) for o, s in profile_pick.picks() if o.Document is self.doc]
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        for obj, short in picks:
            if short.startswith("Edge") and not extrude.is_sketch(obj):
                self._edge_clicked(obj, short)

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        view = Gui.ActiveDocument.ActiveView
        extra = [o for o, _s in self.refs if extrude.is_sketch(o)]
        try:
            self.picker = profile_pick.ProfilePicker(
                view,
                profile_pick.candidate_sketches(self.body, extra),
                lambda obj, sub: QtCore.QTimer.singleShot(
                    0, lambda: self._region_clicked(obj, sub)
                ),
                clicks_through=True,
                on_curve=lambda obj, sub: QtCore.QTimer.singleShot(
                    0, lambda: self._curve_clicked(obj, sub)
                ),
            )
        except Exception as exc:
            warn("Flange: profile shading unavailable: %s" % exc)
        try:
            self.overlay = curve_pick.CurveOverlay(view)
        except Exception as exc:
            warn("Flange: edge highlight unavailable: %s" % exc)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        for name in ("picker", "overlay"):
            item = getattr(self, name)
            setattr(self, name, None)
            if item is not None:
                try:
                    item.remove()
                except Exception:
                    pass

    def _busy(self):
        return any(_dragging(a) for a in self.arrows.values())

    @safe
    def _selection_changed(self):
        if self._closed:
            return
        picks = [(o, s) for o, s in profile_pick.picks() if o.Document is self.doc]
        if not picks:
            return
        Gui.Selection.clearSelection()
        if self._busy():
            return
        for obj, short in picks:
            if self.active == "object":
                self._object_clicked(obj, short)
            elif self.active in ("ref1", "ref2"):
                self._ref_clicked(obj, short, int(self.active[3]) - 1)
            elif short.startswith("Edge") and not extrude.is_sketch(obj):
                self._edge_clicked(obj, short)

    def _switch(self, kind):
        """Picks of another kind start over (Fusion switches the flange's mode)."""
        if self.kind == kind:
            return True
        if self.editing and self.kind is not None:
            self.message.setText(
                "⚠ This flange is a %s flange: pick %s." % (self.kind, _what(self.kind))
            )
            return False
        self._discard()
        self.refs = []
        self.kind = kind
        self.options.update({"kind": kind})
        return True

    @safe
    def _region_clicked(self, sketch, sub):
        if self._closed or self._busy() or self.active != "selection":
            return
        if not self._switch("base"):
            return
        key = (sketch.Name, sub)
        keys = [(o.Name, s) for o, s in self.refs]
        if key in keys:
            self.refs = [r for r in self.refs if (r[0].Name, r[1]) != key]
        else:
            self.refs = self.refs + [(sketch, sub)]
        self._picks_changed()

    @safe
    def _curve_clicked(self, sketch, sub):
        if self._closed or self._busy() or self.active != "selection":
            return
        names, closed = _chain(sketch, sub)
        if closed:
            self.message.setText(
                "⚠ That line closes a profile: click inside it for a base flange (a plate)."
            )
            return
        if not self._switch("contour"):
            return
        current = {(o.Name, s) for o, s in self.refs}
        if (sketch.Name, sub) in current:
            self.refs = []
        else:
            self.refs = [(sketch, n) for n in names]
        self._check_attached()
        self._picks_changed()

    def _check_attached(self):
        """A contour drawn from the end of a sheet edge joins that edge (Fusion): Operation
        Join, the Distance options hidden (it runs the whole edge)."""
        self.attached = None
        if self.kind != "contour" or not self.refs:
            return
        body = sheetmetal.find_sheet_body(self.doc, active=self.body)
        if body is None:
            return
        base_obj = None
        if self.target is not None and flange.owner_body(self.target) is body:
            base_obj = self.target.BaseFeature
        self.attached = flange.attachment(self.refs, body, base_obj)
        if self.attached is not None and not self.editing:
            self._quiet = True
            try:
                curve_pick.set_combo(self.operation_box, "join")
            finally:
                self._quiet = False

    def _edge_clicked(self, obj, short):
        body = curves.owner_body(obj)
        if body is None or not sheetmetal.is_sheet_metal_body(body):
            self.message.setText(
                "⚠ An edge flange goes on a sheet metal body: pick an edge of one, or a sketch "
                "profile to start one."
            )
            return
        if self.target is not None and obj is self.target:
            base = self.target.BaseFeature
            mapped = _same_edge(obj, short, base)
            if mapped is None:
                self.message.setText(
                    "⚠ That edge belongs to the flange being made: OK this one first, then "
                    "flange its edges with a new Flange."
                )
                return
            obj, short = base, mapped
        if self.refs and self.kind == "edge" and curves.owner_body(self.refs[0][0]) is not body:
            self.message.setText("⚠ The edges must be on one sheet metal body.")
            return
        if not self._switch("edge"):
            return
        self.body = body
        key = (obj.Name, short)
        keys = [(o.Name, s) for o, s in self.refs]
        if key in keys:
            self.refs = [r for r in self.refs if (r[0].Name, r[1]) != key]
        else:
            self.refs = self.refs + [(obj, short)]
        self._picks_changed()

    def _object_clicked(self, obj, short):
        if short and not short.startswith("Face"):
            self.message.setText("⚠ To Object: pick a flat face or a plane.")
            return
        if self.target is not None and obj is self.target:
            obj = self.target.BaseFeature
        self.to_object = (obj, short)
        self.activate("selection")
        self._refresh_picks()
        self._changed()

    def _ref_clicked(self, obj, short, index):
        """A Two Offsets reference: a flat face or a plane crossing the edge."""
        if short and not short.startswith("Face"):
            self.message.setText("⚠ Two Offsets: pick a flat face or a plane.")
            return
        if self.target is not None and obj is self.target:
            obj = self.target.BaseFeature
        self.offset_refs[index] = (obj, short)
        self.activate("ref2" if index == 0 and self.offset_refs[1] is None else "selection")
        self._refresh_picks()
        self._changed()

    def _refresh_picks(self):
        if self.kind == "edge":
            text = "%d edge%s" % (len(self.refs), "" if len(self.refs) == 1 else "s")
        elif self.kind == "base":
            text = "%d profile%s" % (len(self.refs), "" if len(self.refs) == 1 else "s")
        elif self.kind == "contour":
            text = curves.label(self.refs)
        else:
            text = ""
        self.field.set_text(text if self.refs else "")
        self.object_field.set_text(
            "%s %s" % (self.to_object[0].Label, self.to_object[1]) if self.to_object else ""
        )
        for box, ref in zip(self.ref_fields, self.offset_refs):
            box.set_text("%s %s" % (ref[0].Label, ref[1]) if ref else "")
        if self.picker is not None:
            try:
                keys = {(o.Name, s) for o, s in self.refs if self.kind == "base"}
                self.picker.set_selected(keys)
            except Exception:
                pass
        if self.overlay is not None:
            try:
                edges = []
                if self.kind == "contour":
                    edges = curves.refs_edges(self.refs)
                elif self.kind == "edge":
                    edges = [curves.edge_of(o, s) for o, s in self.refs]
                    edges = [e for e in edges if e is not None]
                self.overlay.show("flange", edges, curve_pick.PATH_COLOR)
            except Exception:
                pass

    def _picks_changed(self):
        self._refresh_picks()
        if not self.refs:
            if not self.editing:
                self._discard()
            self._remove_arrows()
            self.error = "Pick a profile or edges." if self.editing else ""
            self.message.setText(("⚠ " + self.error) if self.error else "")
            self._update_visibility()
            return
        self._changed(new_geometry=True)

    def _discard(self):
        if self.target is not None and not self.editing:
            try:
                flange.discard(self.target)
            except Exception as exc:
                warn("Flange: %s" % exc)
            self.target = None
            self.made_with = None
            preview.recompute(self.doc)

    # -- changes ------------------------------------------------------------------------------
    @safe
    def _value_typed(self, *_):
        if self._quiet:
            return
        self._changed(new_geometry=True)
        if (
            self.kind == "edge"
            and self.options["width_type"] == "two_offsets"
            and self.offset_refs == [None, None]
            and self.active == "selection"
        ):
            self.activate("ref1")  # Two Offsets: the next clicks pick the two references
            self.message.setText(
                "Click the two faces or planes the width runs between (none: the offsets "
                "count from the edge's ends)."
            )
        if (
            self.kind == "edge"
            and self.options["extent"] == "to_object"
            and self.to_object is None
            and self.active != "object"
        ):
            self.activate("object")  # To Object: the next click picks what it runs to
            self.message.setText("Click the face or plane the flange runs to.")

    def _changed(self, new_geometry=False):
        self._collect()
        self._update_visibility()
        self.dirty = True
        self._arrows_due = new_geometry or getattr(self, "_arrows_due", False)
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
            if getattr(self, "_arrows_due", False) and not self._busy():
                self._arrows_due = False
                self._make_arrows()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if not self.refs or self.kind is None:
            return
        options = self._collect()
        made_with = (self.kind, self.operation, self.rule_name)
        try:
            if self.target is not None and not self.editing and self.made_with != made_with:
                if self.made_with and self.made_with[:2] == made_with[:2]:
                    body = flange.owner_body(self.target)
                    sheetmetal.make_sheet_metal_body(body, self.rule_name)
                    if self.operation == "new_component":
                        # the new Sheet Metal component's active rule follows the Rule box
                        from . import components

                        part = components.container_of(body)
                        if part is not None:
                            sheetmetal.set_active_rule(self.doc, self.rule_name, part)
                    self.target.touch()  # it reads the body's rule when it computes
                    self.made_with = made_with
                else:
                    self._discard()
            if self.target is None:
                self.target = flange.make(
                    self.doc,
                    self.kind,
                    self.refs,
                    options,
                    rule_name=self.rule_name,
                    operation=self.operation,
                    body=self._join_body(),
                    target=self.to_object,
                    hide=False,  # the sketch stays in view while picking; OK hides it
                    offset_refs=self.offset_refs,
                )
                self.made_with = made_with
            else:
                if self.editing and self.owns_body:
                    body = flange.owner_body(self.target)
                    if sheetmetal.body_rule_name(body) != self.rule_name:
                        from . import sheetmetal_rules

                        sheetmetal_rules.set_body_rule(body, self.rule_name)
                flange.update(
                    self.target,
                    refs=self.refs,
                    options=options,
                    target=self.to_object,
                    offset_refs=self.offset_refs,
                )
                if not self.to_object:
                    self.target.Target = None
            self._store_formulas()
            self.error = ""
        except (form.FormError, curves.CurveError, ValueError) as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This flange cannot be built: %s" % exc

    def feature(self):
        return self.target

    def show_status(self):
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = flange.problem_of(self.target) if self.target is not None else ""
        self.message.setText("⚠ " + text if text else "")

    # -- the blue arrow -----------------------------------------------------------------------
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
        if not self.refs or self.target is None or self.error:
            return
        if "Invalid" in list(getattr(self.target, "State", [])):
            return  # the message says why; no arrow on a flange that is not built
        try:
            if self.kind == "edge":
                origin, direction = self._edge_arrow()
                if self.options["extent"] == "distance":
                    self.arrows["height"] = ArrowDragger(
                        origin,
                        direction,
                        self.options["height"],
                        5.0,
                        on_drag=self._height_dragged,
                        on_release=self._height_dragged,
                    )
                    self._attach_box("height")
                self._make_angle_handle()
            elif self.kind == "contour" and self.attached is None:
                origin, direction = self._contour_arrow()
                self.arrows["distance"] = ArrowDragger(
                    origin,
                    direction,
                    self.options["distance"],
                    5.0,
                    on_drag=self._distance_dragged,
                    on_release=self._distance_dragged,
                )
                self._attach_box("distance")
        except Exception as exc:
            warn("Flange arrows unavailable: %s" % exc)

    def _edge_arrow(self):
        """(datum point, wall direction) of the first picked edge, in design coordinates."""
        import math

        from . import bodies

        base_obj = self.target.BaseFeature
        shape = bodies.baked(curves.to_global(base_obj.Shape, base_obj))
        rule = form.effective_rule(
            sheetmetal.rule_for_body(self.body), flange.form_options(self.options)
        )
        T, R = rule["thickness"], rule["bend_radius"]
        name = self.refs[0][1]
        frame = form.edge_frame(shape, name, T, self.options["flip"])
        angle = self.options["angle"]
        a = math.radians(angle)
        xc = core.bend_start_x(self.options["position"], angle, R, T)
        datum = self.options["datum"]
        half = math.tan(a / 2.0) if angle < 179.999 else 0.0
        if datum == "inner":
            x, z = xc + R * half, T
        elif datum == "outer":
            x, z = xc + (R + T) * half, 0.0
        else:
            x, z = xc + (R + T) * math.sin(a), T + R - (R + T) * math.cos(a)
        t0, t1 = core.width_range(
            self.options["width_type"],
            frame.length,
            self.options["width"],
            self.options["distance1"],
            self.options["width2"],
        )
        origin = frame.point(x, z, (t0 + t1) / 2.0)
        direction = frame.out * math.cos(a) + frame.up * math.sin(a)
        # the bend's axis, for the angle handle: it turns `out` towards `up`
        self._bend = (frame.point(xc, T + R, (t0 + t1) / 2.0), frame.out.cross(frame.up), frame.out)
        self._bend_reach = R + T + 4.0
        return origin, direction

    def _make_angle_handle(self):
        """Fusion's angle manipulator on the bend: the ball turns about the bend's axis."""
        from . import handles3d

        center, axis, zero = self._bend
        self.arrows["angle"] = handles3d.angle_handle(
            center,
            axis,
            zero,
            self._bend_reach,
            self.options["angle"],
            2.0,
            on_drag=self._angle_dragged,
            on_release=self._angle_dragged,
        )
        self._attach_box("angle")

    @safe
    def _angle_dragged(self, angle):
        value = min(180.0, max(1.0, round(float(angle), 1)))
        if self.formulas.get("angle"):
            self.formulas["angle"] = ""
        self._quiet = True
        try:
            self.f_angle.set_value(value)
        finally:
            self._quiet = False
        self._changed()

    def _contour_arrow(self):
        edges = curves.refs_edges(self.refs)
        sketch = self.refs[0][0]
        normal = sketch.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
        if self.options["flip"]:
            normal = normal * -1.0
        start = edges[0].valueAt(edges[0].FirstParameter)
        if self.options["direction"] == "symmetric":
            start = start - normal * (self.options["distance"] / 2.0)
        return start, normal

    def _attach_box(self, key):
        field = getattr(self, "f_" + key)
        return self.value_boxes.attach(
            self.arrows.get(key),
            key,
            lambda: field.widget.text(),
            lambda text: self._box_typed(key, text),
        )

    def _box_typed(self, key, text):
        """A number, parameter or formula typed in the arrow's value box: as if typed in
        the field."""
        if self._closed:
            return
        self.formula_inputs[key].take(text)

    @safe
    def _height_dragged(self, distance):
        self._dragged("height", distance)

    @safe
    def _distance_dragged(self, distance):
        self._dragged("distance", distance)

    def _dragged(self, key, distance):
        value = max(0.1, abs(round(distance, 2)))
        if self.formulas.get(key):
            self.formulas[key] = ""  # dragging gives a plain value: the formula goes
        self._quiet = True
        try:
            getattr(self, "f_" + key).set_value(value)
        finally:
            self._quiet = False
        self._changed()

    # -- OK / Cancel ----------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            return self._accept()
        except Exception as exc:
            warn("Flange OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        if not self.refs:
            self.message.setText("⚠ " + MODE_TEXT[None])
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
            self.message.setText("⚠ This flange cannot be built.")
            return False
        preview.recompute(self.doc)
        text = flange.problem_of(self.target)
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        self._drop_tried_rules()
        flange.hide_sketches([r for r in self.refs if extrude.is_sketch(r[0])])
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        extrude.show_tip(flange.owner_body(feature))
        log("Flange done (%s)" % self.kind)
        return True

    def _drop_tried_rules(self):
        """Library rules this dialog copied into the design for the Rule box that nothing
        follows in the end (another rule was chosen after them) leave the design again."""
        try:
            from . import sheetmetal_rules

            parts = [o for o in self.doc.Objects if o.TypeId == "App::Part"]
            for rule in sheetmetal.design_rules(self.doc):
                name = rule["name"]
                if name in self.rules_at_start or name == self.rule_name:
                    continue
                if sheetmetal_rules.in_use(self.doc, name):
                    continue
                if name == sheetmetal.active_rule_name(self.doc):
                    continue
                if any(getattr(p, sheetmetal.RULE_PROP, "") == name for p in parts):
                    continue
                sheetmetal.delete_rule(self.doc, name)
        except Exception as exc:
            warn("Flange: %s" % exc)

    def reject(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            body = self.body if self.editing else None
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
            if body is not None and curves.owner_body(body) is not None:
                extrude.show_tip(body)
        except Exception as exc:
            warn("Flange Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Flange Cancel: %s" % exc)
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
        super().cleanup()


def _what(kind):
    return {
        "base": "closed sketch profiles",
        "contour": "an open sketch line",
        "edge": "edges of its sheet metal body",
    }.get(kind, "")


def _chain(sketch, sub):
    """(["EdgeN", ...], closed): the sketch curves joined end to end with `sub`."""
    edges = list(sketch.Shape.Edges)
    try:
        start = int(sub[4:]) - 1
    except ValueError:
        return [sub], False

    def ends(edge):
        return [edge.Vertexes[0].Point, edge.Vertexes[-1].Point]

    picked = {start}
    todo = [start]
    while todo:
        current = todo.pop()
        for point in ends(edges[current]):
            for i, other in enumerate(edges):
                if i in picked:
                    continue
                if any((point - q).Length < 1e-6 for q in ends(other)):
                    picked.add(i)
                    todo.append(i)
    points = []
    for i in picked:
        points += ends(edges[i])
    free = [p for p in points if sum(1 for q in points if (p - q).Length < 1e-6) == 1]
    return ["Edge%d" % (i + 1) for i in sorted(picked)], not free


def _same_edge(obj, short, base):
    """The name in `base`'s shape of the straight edge that the edge `short` of `obj` (the
    flange being previewed) is part of: the preview cuts the plate back next to the first
    picked edge, so a neighbouring edge shows shortened. None for an edge only the preview
    has (its wall)."""
    import Part

    try:
        edge = obj.Shape.getElement(short)
    except Exception:
        return None
    if base is None or base.Shape.isNull() or edge.ShapeType != "Edge":
        return None
    if not isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
        return None
    a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    direction = b - a
    if direction.Length < 1e-9:
        return None
    direction.normalize()
    mid = Part.Vertex((a + b) * 0.5)
    for i, other in enumerate(base.Shape.Edges, 1):
        if not isinstance(other.Curve, (Part.Line, Part.LineSegment)):
            continue
        p, q = other.Vertexes[0].Point, other.Vertexes[-1].Point
        along = q - p
        if along.Length < 1e-9:
            continue
        along.normalize()
        if abs(abs(along.dot(direction)) - 1.0) > 1e-9:
            continue
        if other.distToShape(mid)[0] < 1e-6:
            return "Edge%d" % i
    return None


def _dragging(arrow):
    try:
        if hasattr(arrow, "busy"):
            return bool(arrow.busy())
        return bool(arrow.dragger.isActive.getValue())
    except Exception:
        return False


class ViewProviderFlange:
    """View provider of SciForge's Flange step. Saved as "sciforge.sheetmetal_flange_ui.
    ViewProviderFlange": never rename."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("sm_flange")

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


def _start():
    try:
        if not commands.finish_open_dialog():
            return
        doc = App.ActiveDocument
        if doc is None:
            commands.tell("Open or create a design first.")
            return
        Gui.Control.showDialog(FlangePanel(doc))
        log("Flange started")
    except Exception as exc:
        warn("Flange failed to start: %s" % exc)


class FlangeCommand:
    def GetResources(self):
        return {
            "MenuText": "Flange",
            "ToolTip": "Sheet metal from a closed profile (a plate), an open line (bent with the "
            "rule's radius) or edges of a sheet metal body (a bend and a wall)",
            "Pixmap": ui_icon_path("sm_flange"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start()


def edit(feature):
    """Open the Flange dialog on an existing flange (timeline double-click)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(FlangePanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


def _register():
    """The timeline's name and icon for a flange, Change Parameters' fields."""
    try:
        from . import parameters, timeline_core

        timeline_core.KINDS.setdefault("flange", ("Flange", "sm_flange"))
        parameters.SCIFORGE_PROPS.setdefault(
            "Flange", [("Height", "Height"), ("Angle", "Angle"), ("Distance", "Distance")]
        )
    except Exception as exc:
        warn("Flange registration: %s" % exc)


_register()

COMMANDS = {"SciForge_Flange": FlangeCommand}
EDITORS = {"SciForge::Flange": edit}
