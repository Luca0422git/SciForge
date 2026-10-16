# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gear (SOLID > CREATE > Gear): spur, internal (ring) and rack gears with a live preview.

Pick a plane or a flat face (the origin squares, or a face; a selected one is taken at
once); the gear's outline follows the mouse; click its centre (a rack: the middle of its
pitch line). The gear appears with a blue thickness arrow (drag it, or type in its box).
The fields are those of Fusion's Spur Gear sample (Standard, Pressure Angle, Module or
Diametral Pitch, Number of Teeth, Backlash, Root Fillet Radius, Thickness, Hole Diameter,
Pitch Diameter read-only) plus Type (Spur / Internal / Rack), Symmetric, an internal
gear's Rim Thickness and a rack's size and height. Every change redraws the gear at once;
a parameter typed in a field keeps driving it. OK keeps it as one timeline step "Gear"
(double-click it to edit), Cancel or Esc removes it. Operation Join / Cut / New Body (the
first choice, like Fusion's sample, which always makes a new component) / New Component.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import gear, gear_core, warn
from .compat import QtWidgets
from .primitives_ui import PlacedPanel, combo, cross_points, safe, set_combo, start

TYPE_LABELS = [("Spur", "spur"), ("Internal", "internal"), ("Rack", "rack")]
STANDARD_LABELS = [("Metric", "metric"), ("English", "english")]
ANGLE_LABELS = [("14.5 deg", 14.5), ("20 deg", 20.0), ("25 deg", 25.0)]
RACK_SIZE_LABELS = [("Number of Teeth", "teeth"), ("Length", "length")]
# Values that stay as they were left for the next gear of this session (Fusion's sample
# remembers its last inputs); the place, operation and formulas never carry over.
REMEMBERED = (
    "type",
    "standard",
    "module",
    "diametral_pitch",
    "teeth",
    "pressure_angle",
    "backlash",
    "fillet",
    "thickness",
    "symmetric",
    "hole",
    "rim",
    "rack_size",
    "rack_length",
    "rack_height",
)


class GearPanel(PlacedPanel):
    FORMULA_KEYS = gear_core.NUMBER_KEYS
    TYPE_ORDER = ()
    READY_KEY = "thickness"
    title = "Gear"
    icon = "gear"
    kind = "gear"
    clicks = 1
    last = None
    remembered = {}
    HINTS = ("Click the gear's centre on the plane (a rack: the middle of its pitch line).",)

    def _defaults(self):
        return gear.with_defaults(dict(GearPanel.remembered))

    def _read(self, feature):
        return gear.read(feature)

    def _build(self):
        return gear.build(self.ref, self.options, feature=self.target)

    def _tool(self):
        return None

    def _auto(self, base):
        return "new_body"  # Fusion's sample always makes a new component; never a guess

    # -- form -------------------------------------------------------------------------------------
    def _build_form(self):
        self._outline_cache = (None, [])
        super()._build_form()
        index = self.operation.findData("intersect")
        if index >= 0:
            self.operation.removeItem(index)  # a Pad / Pocket: no Intersect
        set_combo(self.operation, self.options["operation"])

    def _build_fields(self, form):
        o = self.options
        self.type = combo(TYPE_LABELS, o["type"], "SciForgeGear_type")
        form.addRow("Type", self.type)
        self.standard = combo(STANDARD_LABELS, o["standard"], "SciForgeGear_standard")
        form.addRow("Standard", self.standard)
        self.angle = combo(ANGLE_LABELS, float(o["pressure_angle"]), "SciForgeGear_angle")
        form.addRow("Pressure Angle", self.angle)
        self.module, self.module_label = self.distance_field(
            form, "Module", "module", name="SciForgeGear_module"
        )
        self.dp, self.dp_label = self.distance_field(
            form, "Diametral Pitch", "diametral_pitch", unit="", name="SciForgeGear_dp"
        )
        self.dp.widget.setToolTip("Teeth per inch of pitch diameter")
        self.rack_size = combo(RACK_SIZE_LABELS, o["rack_size"], "SciForgeGear_rack_size")
        self.rack_size_label = QtWidgets.QLabel("Rack Size")
        form.addRow(self.rack_size_label, self.rack_size)
        self.teeth, self.teeth_label = self.distance_field(
            form, "Number of Teeth", "teeth", unit="", name="SciForgeGear_teeth"
        )
        self.rack_length, self.rack_length_label = self.distance_field(
            form, "Rack Length", "rack_length", name="SciForgeGear_rack_length"
        )
        self.backlash, _ = self.distance_field(
            form, "Backlash", "backlash", name="SciForgeGear_backlash"
        )
        self.backlash.widget.setToolTip("Each tooth is this much thinner at the pitch circle")
        self.fillet, _ = self.distance_field(
            form, "Root Fillet Radius", "fillet", name="SciForgeGear_fillet"
        )
        self.thickness, _ = self.distance_field(
            form, "Thickness", "thickness", name="SciForgeGear_thickness"
        )
        self.symmetric = QtWidgets.QCheckBox("Symmetric")
        self.symmetric.setObjectName("SciForgeGear_symmetric")
        self.symmetric.setToolTip("Half the thickness on each side of the plane")
        form.addRow("", self.symmetric)
        self.hole, self.hole_label = self.distance_field(
            form, "Hole Diameter", "hole", name="SciForgeGear_hole"
        )
        self.hole.widget.setToolTip("Bore hole through the gear's centre (0 = none)")
        self.rim, self.rim_label = self.distance_field(
            form, "Rim Thickness", "rim", name="SciForgeGear_rim"
        )
        self.rim.widget.setToolTip("The ring of material outside the teeth's roots")
        self.rack_height, self.rack_height_label = self.distance_field(
            form, "Height", "rack_height", name="SciForgeGear_rack_height"
        )
        self.rack_height.widget.setToolTip("Material under the roots of the rack's teeth")
        self.pitch_value = QtWidgets.QLineEdit()
        self.pitch_value.setReadOnly(True)
        self.pitch_value.setObjectName("SciForgeGear_pitch_diameter")
        self.pitch_label = QtWidgets.QLabel("Pitch Diameter")
        form.addRow(self.pitch_label, self.pitch_value)
        self.type.currentIndexChanged.connect(self._type_changed)
        self.standard.currentIndexChanged.connect(self._standard_changed)
        self.angle.currentIndexChanged.connect(self._choice)
        self.rack_size.currentIndexChanged.connect(self._rack_size_changed)
        self.symmetric.toggled.connect(self._choice)

    def _show_fields(self):
        o = self.options
        self._quiet = True
        try:
            set_combo(self.type, o["type"])
            set_combo(self.standard, o["standard"])
            set_combo(self.angle, float(o["pressure_angle"]))
            set_combo(self.rack_size, o["rack_size"])
            for key in gear_core.NUMBER_KEYS:
                field = self.fields.get(key)
                if field is not None:
                    field.set_value(float(o[key]))
            self.symmetric.setChecked(bool(o["symmetric"]))
            set_combo(self.operation, o["operation"])
        finally:
            self._quiet = False
        self._update_visibility()
        self.show_formulas()
        self._show_sizes()

    def _update_visibility(self):
        kind = self.type.currentData() or "spur"
        english = self.standard.currentData() == "english"
        by_length = kind == "rack" and self.rack_size.currentData() == "length"
        shown = {
            (self.module.widget, self.module_label): not english,
            (self.dp.widget, self.dp_label): english,
            (self.rack_size, self.rack_size_label): kind == "rack",
            (self.teeth.widget, self.teeth_label): not by_length,
            (self.rack_length.widget, self.rack_length_label): by_length,
            (self.hole.widget, self.hole_label): kind == "spur",
            (self.rim.widget, self.rim_label): kind == "internal",
            (self.rack_height.widget, self.rack_height_label): kind == "rack",
        }
        for widgets, visible in shown.items():
            for widget in widgets:
                widget.setVisible(visible)
        self.pitch_label.setText("Pitch" if kind == "rack" else "Pitch Diameter")

    def _show_sizes(self):
        """The read-only Pitch Diameter (a rack: its pitch, the distance between teeth)."""
        try:
            s = gear_core.sizes(self.options)
            value = s["pitch"] if self.options["type"] == "rack" else s["pitch_diameter"]
            text = App.Units.Quantity(value, App.Units.Length).UserString
        except Exception:
            text = ""
        if self.pitch_value.text() != text:
            self.pitch_value.setText(text)

    def _collect(self):
        o = self.options
        o["type"] = self.type.currentData()
        o["standard"] = self.standard.currentData()
        o["pressure_angle"] = float(self.angle.currentData())
        o["rack_size"] = self.rack_size.currentData()
        for key in gear_core.NUMBER_KEYS:
            field = self.fields.get(key)
            if field is None:
                continue
            value = field.value()
            if key == "thickness":
                o[key] = value
            elif key == "teeth":
                o[key] = int(round(value)) if abs(value - round(value)) < 1e-6 else value
            else:
                o[key] = abs(value)
        o["symmetric"] = self.symmetric.isChecked()

    def _changed(self, new_geometry=False):
        super()._changed(new_geometry)
        self._show_sizes()

    @safe
    def _type_changed(self, *_):
        if self._quiet:
            return
        self._collect()
        uses = gear_core.USES[self.options["type"]]
        for key in ("hole", "rim", "rack_length", "rack_height"):
            if key not in uses:
                self.drop_formula(key)  # a hidden field's formula no longer drives anything
        self._update_visibility()
        self._changed(new_geometry=True)

    @safe
    def _standard_changed(self, *_):
        """Metric <-> English: the other measure of the same tooth size (the gear keeps its
        size, as the Coil keeps its shape when its type changes)."""
        if self._quiet:
            return
        old = self.options.get("standard", "metric")
        new = self.standard.currentData()
        if new == old:
            return
        try:
            m = gear_core.module_of(self.options)
        except gear_core.GearError:
            m = float(gear_core.DEFAULTS["module"])
        if new == "english":
            self.options["diametral_pitch"] = round(gear_core.INCH / m, 4)
            self.drop_formula("module")
        else:
            self.options["module"] = round(m, 4)
            self.drop_formula("diametral_pitch")
        self.options["standard"] = new
        self._show_fields()
        self._changed(new_geometry=True)

    @safe
    def _rack_size_changed(self, *_):
        if self._quiet:
            return
        self._collect()
        try:
            if self.options["rack_size"] == "length":
                s = gear_core.sizes(dict(self.options, rack_size="teeth"))
                self.options["rack_length"] = round(s["rack_length"], 3)  # the same rack
                self.drop_formula("rack_length")
            else:
                s = gear_core.sizes(dict(self.options, rack_size="length"))
                self.options["teeth"] = max(1, s["rack_teeth"])  # the whole teeth it held
                self.drop_formula("teeth")
        except gear_core.GearError:
            pass  # a module of 0: the dialog says so
        self._show_fields()
        self._changed(new_geometry=True)

    # -- placing ----------------------------------------------------------------------------------
    def _local_outline(self):
        """The gear's outline around its own centre (cached: it changes only with the
        values, not with the mouse)."""
        key = tuple(
            (k, repr(v))
            for k, v in sorted(self.options.items())
            if k not in ("x", "y", "thickness", "symmetric", "operation", "expressions")
        )
        if self._outline_cache[0] != key:
            try:
                lines = gear_core.polylines(self.options)
            except Exception:
                lines = []
            self._outline_cache = (key, lines)
        return self._outline_cache[1]

    def _outline(self, points, mouse):
        x, y = mouse
        out = [[(x + px, y + py) for px, py in line] for line in self._local_outline()]
        return out + cross_points(x, y, self._mark())

    def _placed(self, points):
        x, y = points[0]
        self.options.update(x=x, y=y)

    # -- handles ----------------------------------------------------------------------------------
    def _handle_specs(self):
        o = self.options
        frame = gear.primitives.global_frame(self.ref)
        n = frame.Rotation.multVec(App.Vector(0, 0, 1))
        center = frame.multVec(App.Vector(float(o["x"]), float(o["y"]), 0))
        scale = 0.5 if o.get("symmetric") else 1.0
        return [("thickness", center, n, float(o["thickness"]), scale, self._thickness_dragged)]

    def _thickness_dragged(self, value):
        value = round(value, 2)
        if abs(value) < 0.01:
            value = 0.01 if value >= 0 else -0.01
        self.options["thickness"] = value
        self.set_field(self.thickness, value)

    # -- OK ---------------------------------------------------------------------------------------
    def _finishing(self, feature):
        GearPanel.remembered = {k: self.options[k] for k in REMEMBERED if k in self.options}


def edit(feature):
    """Open the Gear dialog on an existing gear (timeline double-click)."""
    from . import commands

    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        if not gear.is_ours(feature):
            Gui.ActiveDocument.setEdit(feature.Name)
            return
        Gui.Control.showDialog(GearPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


class GearCommand:
    def GetResources(self):
        from . import ui_icon_path

        return {
            "MenuText": "Gear",
            "ToolTip": "Gear: spur, internal (ring) or rack. Pick a plane or flat face and "
            "click the centre; module or diametral pitch, teeth, pressure angle, backlash, "
            "root fillet, thickness and bore hole, with a live preview",
            "Pixmap": ui_icon_path("gear"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            start(GearPanel)
        except Exception as exc:
            warn("Gear failed to start: %s" % exc)


COMMANDS = {"SciForge_Gear": GearCommand}
EDITORS = {"SciForge::" + gear.KIND: edit}
