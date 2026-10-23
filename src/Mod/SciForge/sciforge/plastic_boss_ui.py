# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC > CREATE > Boss: Fusion's screw boss dialog (plastic_boss.py does the geometry).

Click the sketch points on the parting plane (or select a sketch first: all its points are
taken). Each point gets a boss on both sides: Side 1 (the head side, along the sketch's
normal) and Side 2 (the thread side); Flip swaps them; Offset Position moves the parting
face along the normal (the blue arrow drags it). The tabs hold Fusion's sections: the side
settings (shape, hole type and extent, diameters, drafts, alignment step, clearance, root
and tip radius) and the Ribs. Values that come from the component's plastic rule (drafts,
wall and rib thickness, root radius, clearance) follow the rule until you type over them.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, curve_pick, curves, extrude, log, plastic, plastic_boss as pb, preview
from . import profile_pick, ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .hole_common import SelectionField
from .taskui import ArrowDragger, DistanceField, Panel, ValueBoxes

safe = curve_pick.safe("boss")

SHAPE_LABELS = [
    ("Blank (no hole)", "blank"),
    ("Constant Diameter", "constant_diameter"),
    ("Constant Thickness (SciForge extra)", "constant_thickness"),
]
HOLE_LABELS = [("Simple", "simple"), ("Counterbore", "counterbore"), ("Countersink", "countersink")]
EXTENT_LABELS = [("Through", "through"), ("From Top", "from_top"), ("From Bottom", "from_bottom")]
STEP_LABELS = [("None", "none"), ("In", "in"), ("Out", "out")]
# Fusion's rib shapes: chamfered or filleted top corner (its None means no ribs: the Side
# check boxes here)
RIB_PROFILE_LABELS = [("Chamfer", "chamfer"), ("Fillet", "fillet")]
HEAD_LABELS = [("Pan", "pan"), ("Flat (countersunk)", "flat"), ("Hex", "hex")]
RIB_EXTENT_LABELS = [("Length", "length"), ("To Next", "to_next")]

SIDE_FIELDS = [
    ("diameter", "Outer Diameter", "mm"),
    ("wall", "Wall Thickness", "mm"),
    ("draft", "Draft Angle", "deg"),
    ("hole_diameter", "Hole Diameter", "mm"),
    ("hole_draft", "Hole Draft Angle", "deg"),
    ("hole_depth", "Hole Depth", "mm"),
    ("major_diameter", "Major Diameter", "mm"),
    ("major_depth", "Major Depth", "mm"),
    ("countersink_angle", "Countersink Angle", "deg"),
    ("step_diameter", "Alignment Diameter", "mm"),
    ("step_depth", "Alignment Depth", "mm"),
    ("step_draft", "Alignment Draft Angle", "deg"),
    ("clearance", "Offset Clearance", "mm"),
    ("root_radius", "Root Radius", "mm"),
    ("tip_radius", "Tip Radius", "mm"),
    ("hole_start_radius", "Hole Start Radius", "mm"),
    ("hole_end_radius", "Hole End Radius", "mm"),
]
RIB_FIELDS = [
    ("rib_total_angle", "Total Angle", "deg"),
    ("rib_rotation", "Rotation Angle", "deg"),
    ("rib_thickness", "Thickness", "mm"),
    ("rib_draft", "Draft Angle", "deg"),
    ("rib_length", "Rib Length", "mm"),
    ("rib_offset", "Step Offset", "mm"),
    ("rib_cut", "Cut Size", "mm"),
    ("rib_chamfer_angle", "Chamfer Angle", "deg"),
    ("rib_outer_draft", "Outer Draft Angle", "deg"),
]


def selected_points():
    """Sketch points picked before the command: a picked vertex, or every lone point of a
    picked sketch."""
    found = []
    for obj, short in profile_pick.picks():
        if not curves.is_sketch(obj):
            continue
        if short.startswith("Vertex"):
            found.append((obj, short))
        elif not short:
            found += [(obj, n) for n in pb.point_names(obj)]
    return found


class BossPanel(Panel):
    title = "Boss"
    icon = "pl_boss"
    last = None

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Boss" if feature is None else "Edit Boss")
        BossPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.editing = feature is not None
        self.refs = []
        self.steps = []
        self.participants = None
        self.error = ""
        self.dirty = False
        self.arrow = None
        self.observer = None
        self._quiet = False
        self.value_boxes = ValueBoxes(self, default="offset")
        self.face_sketch = None  # the point sketch made by clicks on a face
        self.active_box = "points"  # the selection box that takes the clicks
        self.picked_bodies = {}  # side -> the body picked for it (else found)
        # {+1, -1: body} found along the sketch normal before the first preview (an edit:
        # the bodies its steps are in); a ray along a boss's axis later runs down its hole
        self.auto_found = None
        self.body = commands.find_body() if feature is None else curves.owner_body(feature)
        self.rule = plastic.rule_for_body(self.body) if self.body is not None else None
        if self.rule is None:
            self.rule = plastic.rule_for_body(None)
        self.options = pb.default_options(self.rule)
        if feature is not None:
            try:
                self.refs, options, self.participants, self.steps = pb.read(feature)
                self.options = options or self.options
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._build_form()
        self._show_options()
        self._watch()
        if feature is not None:
            self._refresh_picks()
            self._make_arrow()
        else:
            self._start()

    # -- form ------------------------------------------------------------------------------------
    def _distance(self, value, unit, on_change, name):
        field = DistanceField(value, unit=unit, on_change=on_change)
        field.widget.setObjectName(name)
        return field

    def _build_form(self):
        form = self.layout
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("SciForgeBoss_tabs")
        # the Boss tab: placement
        page = QtWidgets.QWidget()
        grid = QtWidgets.QFormLayout(page)
        self.field = SelectionField(self, "points", "Select points")
        self.field.button.setObjectName("SciForgeBoss_points")
        self.field.clear.setObjectName("SciForgeBoss_clear_points")
        self.field.set_active(True)
        grid.addRow("Points", self.field.widget)
        self.flip = curve_pick.checkbox("Flip", self.options.get("flip", False))
        self.flip.setObjectName("SciForgeBoss_flip")
        self.flip.setToolTip("Swap the head side and the thread side")
        grid.addRow("", self.flip)
        self.offset = self._distance(
            self.options.get("offset", 0.0), "mm", self._offset_typed, "SciForgeBoss_offset"
        )
        grid.addRow("Offset Position", self.offset.widget)
        self.screw = self._distance(
            self.options.get("screw", 3.0), "mm", self._screw_typed, "SciForgeBoss_screw"
        )
        self.screw.widget.setToolTip(
            "The screw's nominal diameter: sets the hole and boss sizes of both sides"
        )
        grid.addRow("Thread Diameter", self.screw.widget)
        # Fusion's participant bodies: found by themselves (the nearest visible body along
        # each side's direction), or picked here (click the box, then the body)
        self.body_fields = {}
        for side in (1, 2):
            field = SelectionField(self, "body%d" % side, "Auto")
            field.button.setObjectName("SciForgeBoss_body%d" % side)
            field.clear.setObjectName("SciForgeBoss_clear_body%d" % side)
            field.button.setToolTip(
                "The body this side joins: Auto finds the nearest one; click here, then a body"
            )
            self.body_fields[side] = field
            grid.addRow("Side %d Body" % side, field.widget)
        # Fusion's Fastener section: a screw at every boss, in a component of its own
        self.fastener = curve_pick.checkbox("Create Component (screws)", False)
        self.fastener.setObjectName("SciForgeBoss_fastener")
        self.fastener.setToolTip("A simple screw at every boss, in a new component")
        grid.addRow("Fastener", self.fastener)
        self.head = curve_pick.combo(HEAD_LABELS, "pan")
        self.head.setObjectName("SciForgeBoss_head")
        self.head_label = QtWidgets.QLabel("Head Type")
        grid.addRow(self.head_label, self.head)
        self.length = self._distance(0.0, "mm", self._fastener_typed, "SciForgeBoss_length")
        self.length.widget.setToolTip("The screw's length; 0 = to 0.5 mm above the hole's bottom")
        self.length_label = QtWidgets.QLabel("Length (0 = Auto)")
        grid.addRow(self.length_label, self.length.widget)
        self.fastener.toggled.connect(self._fastener_typed)
        self.head.currentIndexChanged.connect(self._fastener_typed)
        self.bodies_label = QtWidgets.QLabel("")
        self.bodies_label.setObjectName("SciForgeBoss_bodies")
        self.bodies_label.setWordWrap(True)
        grid.addRow(self.bodies_label)
        self.rule_label = QtWidgets.QLabel("")
        self.rule_label.setWordWrap(True)
        grid.addRow(self.rule_label)
        self.tabs.addTab(page, "Boss")
        # the two sides
        self.side_widgets = {}
        for side in (1, 2):
            page = QtWidgets.QWidget()
            grid = QtWidgets.QFormLayout(page)
            w = {}
            w["enabled"] = curve_pick.checkbox("Make this side", True)
            w["shape"] = curve_pick.combo(SHAPE_LABELS)
            w["hole"] = curve_pick.combo(HOLE_LABELS)
            w["extent"] = curve_pick.combo(EXTENT_LABELS)
            w["step"] = curve_pick.combo(STEP_LABELS)
            grid.addRow("", w["enabled"])
            grid.addRow("Shape", w["shape"])
            grid.addRow("Hole Type", w["hole"])
            grid.addRow("Hole Extent", w["extent"])
            labels = {}
            for key, text, unit in SIDE_FIELDS:
                field = self._distance(
                    0.0,
                    unit,
                    lambda v, s=side, k=key: self._side_typed(s, k),
                    "SciForgeBoss_s%d_%s" % (side, key),
                )
                w[key] = field
                labels[key] = QtWidgets.QLabel(text)
                if key == "step_diameter":
                    grid.addRow("Step Type", w["step"])
                grid.addRow(labels[key], field.widget)
            for key in ("enabled", "shape", "hole", "extent", "step"):
                widget = w[key]
                widget.setObjectName("SciForgeBoss_s%d_%s" % (side, key))
                if isinstance(widget, QtWidgets.QCheckBox):
                    widget.toggled.connect(lambda *_a, s=side, k=key: self._side_typed(s, k))
                else:
                    widget.currentIndexChanged.connect(
                        lambda *_a, s=side, k=key: self._side_typed(s, k)
                    )
            w["labels"] = labels
            self.side_widgets[side] = w
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, "Side %d (%s)" % (side, "Head" if side == 1 else "Thread"))
        # the ribs
        page = QtWidgets.QWidget()
        grid = QtWidgets.QFormLayout(page)
        self.rib_on = {}
        for side in (1, 2):
            box = curve_pick.checkbox("Side %d" % side, False)
            box.setObjectName("SciForgeBoss_s%d_ribs" % side)
            box.toggled.connect(lambda *_a, s=side: self._side_typed(s, "ribs"))
            self.rib_on[side] = box
            grid.addRow("" if side == 2 else "Ribs on", box)
        self.rib_side = curve_pick.combo([("Side 1", 1), ("Side 2", 2)], 1)
        self.rib_side.setObjectName("SciForgeBoss_rib_side")
        self.rib_side.currentIndexChanged.connect(lambda *_a: self._show_ribs())
        grid.addRow("Edit the ribs of", self.rib_side)
        self.rib_count = QtWidgets.QSpinBox()
        self.rib_count.setRange(1, 36)
        self.rib_count.setObjectName("SciForgeBoss_rib_count")
        self.rib_count.valueChanged.connect(lambda *_a: self._rib_typed("rib_count"))
        grid.addRow("Quantity", self.rib_count)
        self.rib_profile = curve_pick.combo(RIB_PROFILE_LABELS)
        self.rib_profile.setObjectName("SciForgeBoss_rib_profile")
        self.rib_profile.currentIndexChanged.connect(lambda *_a: self._rib_typed("rib_profile"))
        grid.addRow("Profile", self.rib_profile)
        self.rib_extent = curve_pick.combo(RIB_EXTENT_LABELS)
        self.rib_extent.setObjectName("SciForgeBoss_rib_extent")
        self.rib_extent.currentIndexChanged.connect(lambda *_a: self._rib_typed("rib_extent"))
        grid.addRow("Extent", self.rib_extent)
        self.rib_fields = {}
        self.rib_labels = {}
        for key, text, unit in RIB_FIELDS:
            field = self._distance(
                0.0, unit, lambda v, k=key: self._rib_typed(k), "SciForgeBoss_rib_" + key
            )
            self.rib_fields[key] = field
            self.rib_labels[key] = QtWidgets.QLabel(text)
            grid.addRow(self.rib_labels[key], field.widget)
        self.tabs.addTab(page, "Ribs")
        form.addRow(self.tabs)
        self.finish_layout()
        lines = self.message.fontMetrics().lineSpacing()
        self.message.setMinimumHeight(lines * 3 + 4)
        self.flip.toggled.connect(self._flip_typed)

    def _show_options(self):
        self._quiet = True
        try:
            o = self.options
            self.flip.setChecked(bool(o.get("flip")))
            self.offset.set_value(float(o.get("offset", 0.0)))
            self.screw.set_value(float(o.get("screw", 3.0)))
            f = dict(pb.FASTENER_DEFAULTS)
            f.update(o.get("fastener") or {})
            self.fastener.setChecked(bool(f["create"]))
            curve_pick.set_combo(self.head, f["head"])
            self.length.set_value(float(f["length"]))
            for side in (1, 2):
                s = o["side%d" % side]
                w = self.side_widgets[side]
                w["enabled"].setChecked(bool(s.get("enabled", True)))
                for key in ("shape", "hole", "extent", "step"):
                    curve_pick.set_combo(w[key], s[key])
                for key, _text, _unit in SIDE_FIELDS:
                    w[key].set_value(float(s.get(key, 0.0)))
                self.rib_on[side].setChecked(bool(s.get("ribs")))
            self._show_ribs()
        finally:
            self._quiet = False
        self._update_visibility()
        self._show_rule()

    def _show_ribs(self):
        quiet, self._quiet = self._quiet, True
        try:
            s = self.options["side%d" % self._rib_side()]
            self.rib_count.setValue(int(s["rib_count"]))
            curve_pick.set_combo(self.rib_profile, s["rib_profile"])
            curve_pick.set_combo(self.rib_extent, s["rib_extent"])
            for key, _text, _unit in RIB_FIELDS:
                self.rib_fields[key].set_value(float(s[key]))
        finally:
            self._quiet = quiet
        self._update_visibility()

    def _rib_side(self):
        return int(self.rib_side.currentData() or 1)

    def _show_rule(self):
        try:
            name = plastic.assigned_rule_name(
                self.doc, plastic.components.container_of(self.body) if self.body else None
            )
            rule = name or ("%s (default; no rule assigned)" % plastic.default_rule_name())
            self.rule_label.setText("Plastic rule: %s" % rule)
        except Exception:
            self.rule_label.setText("")

    def _update_visibility(self):
        for side in (1, 2):
            w = self.side_widgets[side]
            s = self.options["side%d" % side]
            on = bool(s.get("enabled", True))
            hole = s["shape"] != "blank"
            show = {
                "diameter": s["shape"] != "constant_thickness",
                "wall": s["shape"] == "constant_thickness",
                "hole_diameter": hole,
                "hole_draft": hole,
                "hole_depth": hole and side == 2 and s["extent"] != "through",
                "major_diameter": hole and s["hole"] != "simple",
                "major_depth": hole and s["hole"] == "counterbore",
                "countersink_angle": hole and s["hole"] == "countersink",
                "step_diameter": s["step"] != "none",
                "step_depth": s["step"] != "none",
                "step_draft": s["step"] != "none",
                "hole_start_radius": hole and (side == 1 or s["hole"] == "simple"),
                "hole_end_radius": hole and side == 2 and s["extent"] != "through",
            }
            for key, _text, _unit in SIDE_FIELDS:
                visible = show.get(key, True)
                w[key].widget.setVisible(visible)
                w["labels"][key].setVisible(visible)
                w[key].widget.setEnabled(on)
            for key in ("shape", "hole", "extent", "step"):
                w[key].setEnabled(on and (key != "hole" or hole) and (key != "extent" or hole))
            # the head side always goes through (Fusion)
            if side == 1:
                w["extent"].setEnabled(False)
            w["labels"]["hole_depth"].setText(
                "Floor Thickness" if s["extent"] == "from_bottom" else "Hole Depth"
            )
            w["labels"]["major_depth"].setText(
                "Material Under Head" if side == 1 else "Counterbore Depth"
            )
        making = self.fastener.isChecked()
        for widget in (self.head, self.head_label, self.length.widget, self.length_label):
            widget.setVisible(making)
        s = self.options["side%d" % self._rib_side()]
        for key in ("rib_cut",):
            self.rib_labels[key].setVisible(s["rib_profile"] != "none")
            self.rib_fields[key].widget.setVisible(s["rib_profile"] != "none")
        chamfer = s["rib_profile"] == "chamfer"
        self.rib_labels["rib_chamfer_angle"].setVisible(chamfer)
        self.rib_fields["rib_chamfer_angle"].widget.setVisible(chamfer)
        length = s["rib_extent"] == "length"
        self.rib_labels["rib_length"].setVisible(length)
        self.rib_fields["rib_length"].widget.setVisible(length)

    # -- typed values ------------------------------------------------------------------------------
    @safe
    def _side_typed(self, side, key):
        if self._quiet:
            return
        s = self.options["side%d" % side]
        w = self.side_widgets[side]
        if key == "enabled":
            s["enabled"] = bool(w["enabled"].isChecked())
        elif key == "ribs":
            s["ribs"] = bool(self.rib_on[side].isChecked())
        elif key in ("shape", "hole", "extent", "step"):
            s[key] = w[key].currentData()
        else:
            s[key] = float(w[key].value())
            self.options.setdefault("links", {})["side%d.%s" % (side, key)] = False
        self._changed()

    @safe
    def _rib_typed(self, key):
        if self._quiet:
            return
        side = self._rib_side()
        s = self.options["side%d" % side]
        if key == "rib_count":
            s[key] = int(self.rib_count.value())
        elif key == "rib_profile":
            s[key] = self.rib_profile.currentData()
        elif key == "rib_extent":
            s[key] = self.rib_extent.currentData()
        else:
            s[key] = float(self.rib_fields[key].value())
            self.options.setdefault("links", {})["side%d.%s" % (side, key)] = False
        self._changed()

    @safe
    def _offset_typed(self, value):
        if self._quiet:
            return
        self.options["offset"] = float(self.offset.value())
        self._changed(arrow=True)

    @safe
    def _screw_typed(self, value):
        if self._quiet:
            return
        screw = float(self.screw.value())
        if screw <= 0.1:
            self.message.setText("⚠ The thread diameter must be more than 0.1 mm.")
            return
        # the sizes follow the screw (the rule-linked values stay linked)
        self.options["screw"] = screw
        for side in (1, 2):
            fresh = pb.side_defaults(side, self.rule, screw)
            s = self.options["side%d" % side]
            for key in (
                "diameter",
                "hole_diameter",
                "hole_depth",
                "major_diameter",
                "step_diameter",
                "step_depth",
                "rib_length",
            ):
                s[key] = fresh[key]
        self._show_options()
        self._changed()

    @safe
    def _fastener_typed(self, *_):
        if self._quiet:
            return
        self.options["fastener"] = {
            "create": bool(self.fastener.isChecked()),
            "head": self.head.currentData(),
            "length": float(self.length.value()),
        }
        self._changed()

    @safe
    def _flip_typed(self, *_):
        if self._quiet:
            return
        self.options["flip"] = bool(self.flip.isChecked())
        self._changed(arrow=True)

    def _changed(self, arrow=False):
        self._update_visibility()
        self.dirty = True
        self._arrow_due = arrow or getattr(self, "_arrow_due", False)
        self.schedule()

    # -- the selection box -------------------------------------------------------------------------
    def activate(self, name):
        self.active_box = name
        self.field.set_active(name == "points")
        for side, field in self.body_fields.items():
            field.set_active(name == "body%d" % side)
        if name != "points":
            self.message.setText("Click the body Side %s joins." % name[-1])

    def clear_field(self, name):
        if name == "points":
            self.refs = []
            self._picks_changed()
            return
        side = int(name[-1])
        self.picked_bodies.pop(side, None)
        self.body_fields[side].set_text("")
        self.activate("points")
        self._changed()

    def _toward(self, side):
        head = -1 if self.options.get("flip") else 1
        return head if side == 1 else -head

    def _body_picked(self, obj):
        side = int(self.active_box[-1])
        body = obj if pb.bodies.is_body(obj) else pb.bodies.body_of(obj)
        if body is None or not pb.bodies.has_solid(body):
            self.message.setText("⚠ Click a solid body for Side %d." % side)
            return
        self.picked_bodies[side] = body
        self.body_fields[side].set_text(body.Label)
        self.activate("points")
        self.message.setText("")
        self._changed()

    def _start(self):
        if self.body is None:
            self.message.setText("Make the part first, then sketch points on its parting plane.")
        self.refs = selected_points()
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        self._refresh_picks()
        if self.refs:
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

    def _unwatch(self):
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None

    def _selection_changed(self):
        if self._closed:
            return
        try:
            picks = [p for p in _picks_with_points() if p[0].Document is self.doc]
            if not picks:
                return
            Gui.Selection.clearSelection()
            if self.arrow is not None and _dragging(self.arrow):
                return
            if self.active_box != "points":
                self._body_picked(picks[0][0])
                return
            for obj, short, point in picks:
                self._picked(obj, short, point)
        except Exception as exc:
            warn("boss pick: %s" % exc)

    def _picked(self, obj, short, point=None):
        if not curves.is_sketch(obj) and short.startswith("Face") and point is not None:
            self._face_point(obj, short, point)
            return
        if not curves.is_sketch(obj):
            self.message.setText(
                "⚠ A boss sits on sketch points: draw points on the parting plane and click "
                "them."
            )
            return
        names = [short] if short.startswith("Vertex") else ([] if short else pb.point_names(obj))
        if not names:
            self.message.setText("⚠ Click a sketch point (not a line).")
            return
        if self.refs and self.refs[0][0] is not obj:
            self.message.setText(
                "⚠ The points must be in one sketch. Clear the box to start with another one."
            )
            return
        keys = {(o.Name, s) for o, s in self.refs}
        if len(names) == 1 and (obj.Name, names[0]) in keys:
            self.refs = [r for r in self.refs if (r[0].Name, r[1]) != (obj.Name, names[0])]
        else:
            self.refs = self.refs + [(obj, n) for n in names if (obj.Name, n) not in keys]
        self._picks_changed()

    def _face_point(self, obj, short, point):
        """A click on a flat face of the part: a boss point there. SciForge keeps the points
        in a sketch on that face (made the first time, as Fusion's boss sits on sketch
        points); the parting plane starts 3 x the screw above the face (a standoff), the
        blue arrow moves it."""
        import Part

        body = pb.bodies.body_of(obj)
        if body is None:
            self.message.setText("⚠ Click a face of a part's body.")
            return
        face = obj.Shape.getElement(short)
        if face.Surface.TypeId != "Part::GeomPlane":
            self.message.setText("⚠ A boss on a face needs a flat face (or sketch points).")
            return
        sketch = self.face_sketch if pb.bodies.alive(self.face_sketch) else None
        if self.refs and (sketch is None or self.refs[0][0] is not sketch):
            self.message.setText(
                "⚠ The points must be in one sketch. Clear the box to start with another one."
            )
            return
        if sketch is not None:
            # the same face, also when the click lands on the preview's copy of it
            place = sketch.getGlobalPlacement()
            normal = place.Rotation.multVec(App.Vector(0, 0, 1))
            gface = curves.to_global(face, obj)
            n = gface.normalAt(*gface.Surface.parameter(App.Vector(point)))
            off = abs((App.Vector(point) - place.Base).dot(normal))
            if abs(abs(n.dot(normal)) - 1.0) > 1e-6 or off > 1e-4:
                self.message.setText("⚠ The points of one boss must lie on one face.")
                return
        if sketch is None:
            sketch = body.newObject("Sketcher::SketchObject", "BossPoints")
            sketch.Label = "Boss Points"
            sketch.AttachmentSupport = [(obj, short)]
            sketch.MapMode = "FlatFace"
            self.doc.recompute()
            self.face_sketch = sketch
            if abs(float(self.options.get("offset", 0.0))) < 1e-9:
                height = round(3.0 * float(self.options.get("screw", 3.0)), 2)
                self.options["offset"] = height
                quiet, self._quiet = self._quiet, True
                try:
                    self.offset.set_value(height)
                finally:
                    self._quiet = quiet
        local = sketch.getGlobalPlacement().inverse().multVec(App.Vector(point))
        sketch.addGeometry(Part.Point(App.Vector(local.x, local.y, 0)))
        self.doc.recompute()
        names = pb.point_names(sketch)
        taken = {s for o, s in self.refs}
        new = [n for n in names if n not in taken]
        self.refs = [(sketch, n) for n in names]
        self.message.setText("")
        log("boss point on %s.%s (%s)" % (obj.Label, short, ", ".join(new)))
        self._picks_changed()

    def _refresh_picks(self):
        n = len(self.refs)
        self.field.set_text("%d point%s" % (n, "" if n == 1 else "s") if n else "")

    def _picks_changed(self):
        self._refresh_picks()
        if not self.refs:
            if self.steps and not self.editing:
                for step in self.steps:
                    pb.bodies.remove_step(step)
                self.steps = []
                self.participants = None
                self.auto_found = None
                self.schedule()
            self._remove_arrow()
            self.error = "Pick the boss points." if self.editing else ""
            self.message.setText(("⚠ " + self.error) if self.error else "")
            return
        self._changed(arrow=True)

    # -- preview -----------------------------------------------------------------------------------
    def _recompute(self):
        if self._closed:
            return
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self.show_status()
            if getattr(self, "_arrow_due", False) and not (
                self.arrow is not None and _dragging(self.arrow)
            ):
                self._arrow_due = False
                self._make_arrow()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if not self.refs:
            return
        try:
            if self.auto_found is None:
                self.auto_found = pb.auto_participants(self.refs, self.options, self.steps)
            participants = dict(self.auto_found)
            for side, body in self.picked_bodies.items():
                participants[self._toward(side)] = body
            self.steps = pb.make(
                self.refs, self.options, participants=participants, steps=self.steps
            )
            self.participants = {1: None, -1: None}
            for step in self.steps:
                self.participants[1 if step.Toward >= 0 else -1] = pb.bodies.body_of(step)
            self.error = ""
            self._show_bodies()
        except pb.BossError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This boss cannot be built: %s" % exc

    def _show_bodies(self):
        parts = []
        for toward in (1, -1):
            body = (self.participants or {}).get(toward)
            side = pb.side_of(self.options, toward)
            parts.append(
                "Side %d (%s): %s"
                % (side, "head" if side == 1 else "thread", body.Label if body else "no body")
            )
        parts.sort()
        self.bodies_label.setText("\n".join(parts))

    def feature(self):
        return self.steps[0] if self.steps else None

    def show_status(self):
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        for step in self.steps:
            text = preview.failure(step)
            if text:
                self.message.setText("⚠ " + text)
                return
        self.message.setText("")

    # -- the offset arrow --------------------------------------------------------------------------
    def _remove_arrow(self):
        if self.arrow is not None:
            try:
                self.arrow.remove()
            except Exception:
                pass
            self.arrow = None

    def _make_arrow(self):
        if self._closed:
            return
        self._remove_arrow()
        if not self.refs or not self.steps or self.error:
            return
        try:
            point = pb.global_points(self.refs[:1])[0]
            _o, normal, _x = pb.sketch_frame(self.refs[0][0])
            od = max(pb.outer_diameter(self.options["side1"]), 4.0)
            origin = point + normal * 0.0
            size = max(3.0, min(10.0, od))
            self.arrow = ArrowDragger(
                origin,
                normal,
                float(self.options.get("offset", 0.0)),
                size,
                on_drag=self._offset_dragged,
                on_release=self._offset_dragged,
            )
            self.value_boxes.attach(
                self.arrow,
                "offset",
                lambda: self.offset.widget.text(),
                lambda text: self._box_typed(text),
            )
        except Exception as exc:
            warn("boss arrow unavailable: %s" % exc)

    def _box_typed(self, text):
        if self._closed:
            return
        try:
            value = self.offset.parse(text.strip().lstrip("="))
        except ValueError as exc:
            self.message.setText("⚠ " + str(exc))
            return
        self.offset.take(value)

    @safe
    def _offset_dragged(self, distance):
        value = round(distance, 2)
        self._quiet = True
        try:
            self.offset.set_value(value)
        finally:
            self._quiet = False
        self.options["offset"] = value
        self._changed()

    # -- OK / Cancel -------------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            return self._accept()
        except Exception as exc:
            warn("Boss OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        if not self.refs:
            self.message.setText("⚠ Pick the boss points first (sketch points).")
            return False
        self._timer.stop()
        if self.dirty or not self.steps:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        if not self.steps:
            self.message.setText("⚠ This boss cannot be built.")
            return False
        preview.recompute(self.doc)
        for step in self.steps:
            text = preview.failure(step)
            if text:
                self.message.setText("⚠ " + text)
                return False
        steps = list(self.steps)
        _hide_sketch(self.refs)
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        for step in steps:
            extrude.show_tip(pb.bodies.body_of(step))
        log("Boss done (%d side(s))" % len(steps))
        return True

    def reject(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
            for body in pb.bodies.list_bodies(self.doc):
                extrude.show_tip(body)
        except Exception as exc:
            warn("Boss Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Boss Cancel: %s" % exc)
        return True

    def cleanup(self):
        self._closed = True
        self._unwatch()
        for guard in (self.escape, self.undo_guard, self.enter):
            try:
                guard.remove()
            except Exception:
                pass
        self._remove_arrow()
        self.value_boxes.discard()
        super().cleanup()


def _picks_with_points():
    """[(object, short element name, global picked point or None)] of the selection."""
    found = []
    for sel in Gui.Selection.getSelectionEx():
        names = list(sel.SubElementNames) or [""]
        points = list(getattr(sel, "PickedPoints", []) or [])
        for i, name in enumerate(names):
            obj, short = profile_pick.resolve(sel.Object, name)
            if obj is not None:
                found.append((obj, short, points[i] if i < len(points) else None))
    return found


def _hide_sketch(refs):
    for obj, _ in refs[:1]:
        try:
            obj.ViewObject.Visibility = False
        except Exception:
            pass


def _dragging(arrow):
    try:
        return bool(arrow.dragger.isActive.getValue())
    except Exception:
        return False


class ViewProviderBoss:
    """View provider of a boss side (saved as "sciforge.plastic_boss_ui.ViewProviderBoss":
    never rename)."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("pl_boss")

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


class ViewProviderFastener:
    """View provider of a boss's screws (saved as "sciforge.plastic_boss_ui.
    ViewProviderFastener": never rename). Editing opens the boss."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("hardware")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        edit_fastener(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        edit_fastener(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def edit_fastener(obj):
    """The screws are the boss's: editing them opens the Boss dialog."""
    try:
        steps = [s for s in getattr(obj, "Bosses", []) if pb.is_boss(s)]
        if not steps:
            commands.tell("The boss of these screws is gone.")
            return
        edit(steps[0])
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))


def _start():
    try:
        if not commands.finish_open_dialog():
            return
        if App.ActiveDocument is None:
            commands.tell("Open or create a design first.")
            return
        if not pb.bodies.solid_bodies(App.ActiveDocument):
            commands.tell("Boss needs a part: make the enclosure (and its lid) first.")
            return
        Gui.Control.showDialog(BossPanel(App.ActiveDocument))
        log("boss started")
    except Exception as exc:
        warn("Boss failed to start: %s" % exc)


class BossCommand:
    def GetResources(self):
        return {
            "MenuText": "Boss",
            "ToolTip": "Screw bosses at sketch points on the parting plane: the head side, the "
            "thread side, holes, alignment and ribs",
            "Pixmap": ui_icon_path("pl_boss"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start()


def edit(feature):
    """Open the Boss dialog on an existing boss (either side's step)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(BossPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


def _register():
    try:
        from . import timeline_core

        # (Boss and Rest stay out of Change Parameters: their rule-linked values would
        # override a number typed there)
        timeline_core.KINDS.setdefault("boss", ("Boss", "pl_boss"))
        timeline_core.KINDS.setdefault("rest", ("Rest", "pl_rest"))
        timeline_core.KINDS.setdefault("boss_fastener", ("Fastener", "hardware"))
    except Exception as exc:
        warn("boss registration: %s" % exc)


_register()

COMMANDS = {"SciForge_Boss": BossCommand}
EDITORS = {"SciForge::Boss": edit, "SciForge::BossFastener": edit_fastener}
