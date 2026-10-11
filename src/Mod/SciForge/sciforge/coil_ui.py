# SPDX-License-Identifier: LGPL-2.1-or-later
"""Coil (SOLID > CREATE > Coil) with Fusion's dialog.

Pick a plane or a flat face (the origin squares, or a face; a selected one is taken at
once), click the centre, then a point on the circle (the coil's diameter). The coil
appears with a blue diameter arrow and a height arrow. Fusion's fields: Type (Revolution
and Height / Revolution and Pitch / Height and Pitch / Spiral), Diameter, Rotation
(Clockwise / Counterclockwise), Revolutions, Height, Pitch, Angle, Section (Circular,
Square, Triangular (External), Triangular (Internal)), Section Position (Inside, On
Center, Outside), Section Size, Operation. A coil running into the part becomes a Cut
(a thread groove), like Fusion, unless you picked the operation.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from . import coil, primitives, warn
from .compat import QtWidgets
from .primitives_ui import POSITION_LABELS, PlacedPanel, combo, safe, set_combo, start

TYPE_LABELS = [
    ("Revolution and Height", "rev_height"),
    ("Revolution and Pitch", "rev_pitch"),
    ("Height and Pitch", "height_pitch"),
    ("Spiral", "spiral"),
]
SECTION_LABELS = [
    ("Circular", "circular"),
    ("Square", "square"),
    ("Triangular (External)", "tri_ext"),
    ("Triangular (Internal)", "tri_int"),
]


class CoilPanel(PlacedPanel):
    title = "Coil"
    icon = "coil"
    kind = "coil"
    clicks = 2
    last = None
    HINTS = ("Click the centre on the plane.", "Click a point on the circle (the diameter).")

    def _defaults(self):
        return coil.with_defaults({})

    def _read(self, feature):
        return coil.read(feature)

    def _build(self):
        return coil.build(self.ref, self.options, feature=self.target)

    def _tool(self):
        return None

    def _auto(self, base):
        return coil.auto_operation(base, self.ref, self.options)

    def _formula_key(self, key):
        return False

    # -- form -----------------------------------------------------------------------------------------
    def _build_fields(self, form):
        self.type = combo(TYPE_LABELS, self.options["type"], "SciForgeCoil_type")
        form.addRow("Type", self.type)
        self.diameter, _ = self.distance_field(
            form, "Diameter", "diameter", name="SciForgeCoil_diameter"
        )
        self.rotation = QtWidgets.QPushButton()
        self.rotation.setCheckable(True)
        self.rotation.setObjectName("SciForgeCoil_rotation")
        self.rotation.setToolTip("Click to turn the coil the other way")
        form.addRow("Rotation", self.rotation)
        self.revolutions = QtWidgets.QDoubleSpinBox()
        self.revolutions.setObjectName("SciForgeCoil_revolutions")
        self.revolutions.setDecimals(2)
        self.revolutions.setRange(0.01, 10000.0)
        self.revolutions_label = QtWidgets.QLabel("Revolutions")
        form.addRow(self.revolutions_label, self.revolutions)
        self.height, self.height_label = self.distance_field(
            form, "Height", "height", name="SciForgeCoil_height"
        )
        self.pitch, self.pitch_label = self.distance_field(
            form, "Pitch", "pitch", name="SciForgeCoil_pitch"
        )
        self.angle, self.angle_label = self.distance_field(
            form, "Angle", "angle", unit="deg", name="SciForgeCoil_angle"
        )
        self.section = combo(SECTION_LABELS, self.options["section"], "SciForgeCoil_section")
        form.addRow("Section", self.section)
        self.section_position = combo(
            POSITION_LABELS, self.options["section_position"], "SciForgeCoil_position"
        )
        form.addRow("Section Position", self.section_position)
        self.section_size, _ = self.distance_field(
            form, "Section Size", "section_size", name="SciForgeCoil_section_size"
        )
        self.type.currentIndexChanged.connect(self._type_changed)
        self.section.currentIndexChanged.connect(self._choice)
        self.section_position.currentIndexChanged.connect(self._choice)
        self.rotation.clicked.connect(self._rotation_clicked)
        self.revolutions.valueChanged.connect(self._revolutions_typed)

    def _show_fields(self):
        o = self.options
        self._quiet = True
        try:
            set_combo(self.type, o["type"])
            self.diameter.set_value(o["diameter"])
            self.rotation.setChecked(not bool(o["clockwise"]))
            self.revolutions.setValue(float(o["revolutions"]))
            self.height.set_value(o["height"])
            self.pitch.set_value(o["pitch"])
            self.angle.set_value(o["angle"])
            set_combo(self.section, o["section"])
            set_combo(self.section_position, o["section_position"])
            self.section_size.set_value(o["section_size"])
            set_combo(self.operation, o["operation"])
        finally:
            self._quiet = False
        self._update_visibility()

    def _update_visibility(self):
        uses = coil.USES[self.type.currentData() or "rev_height"]
        self.rotation.setText("Counterclockwise" if self.rotation.isChecked() else "Clockwise")
        for widgets, key in (
            ((self.revolutions, self.revolutions_label), "revolutions"),
            ((self.height.widget, self.height_label), "height"),
            ((self.pitch.widget, self.pitch_label), "pitch"),
            ((self.angle.widget, self.angle_label), "angle"),
        ):
            for widget in widgets:
                widget.setVisible(key in uses)

    def _collect(self):
        o = self.options
        o["type"] = self.type.currentData()
        o["diameter"] = abs(self.diameter.value())
        o["clockwise"] = not self.rotation.isChecked()
        o["revolutions"] = self.revolutions.value()
        o["height"] = self.height.value()
        o["pitch"] = abs(self.pitch.value())
        o["angle"] = self.angle.value()
        o["section"] = self.section.currentData()
        o["section_position"] = self.section_position.currentData()
        o["section_size"] = abs(self.section_size.value())

    @safe
    def _type_changed(self, *_):
        """Another type: the values it now takes are filled from the coil as it is, so the
        coil keeps its shape (Fusion shows the same coil described another way)."""
        if self._quiet:
            return
        old = dict(self.options)
        new_type = self.type.currentData()
        try:
            turns, height, pitch = coil.resolved(old)
        except Exception:
            turns, height, pitch = old["revolutions"], old["height"], old["pitch"]
        if new_type == "spiral":
            pitch = max(pitch, primitives.nice(sum(coil.section_extent(old)[:2]) * 1.5))
        elif abs(height) < 1e-9:  # from a flat spiral: rise one pitch per turn
            height = float(old.get("height") or 0.0) or pitch * turns
        self.options.update(revolutions=round(turns, 4), height=height, pitch=pitch)
        self.options["type"] = new_type
        self._show_fields()
        self._changed(new_geometry=True)

    @safe
    def _rotation_clicked(self, *_):
        self._update_visibility()
        self._changed(new_geometry=True)

    @safe
    def _revolutions_typed(self, value):
        if self._quiet:
            return
        self.options["revolutions"] = value
        self._changed(new_geometry=True)

    # -- placing ----------------------------------------------------------------------------------------
    def _outline(self, points, mouse):
        return self._circle_outline(points, mouse)

    def _live(self, points, mouse):
        if points:
            r = math.hypot(mouse[0] - points[0][0], mouse[1] - points[0][1])
            self.set_field(self.diameter, 2.0 * r)

    def _placed(self, points):
        (cx, cy), (px, py) = points
        diameter = 2.0 * math.hypot(px - cx, py - cy)
        size = primitives.nice(diameter / 10.0)
        height = primitives.nice(diameter)
        revolutions = 5.0
        self.options.update(
            x=cx,
            y=cy,
            diameter=diameter,
            section_size=size,
            height=height,
            revolutions=revolutions,
            pitch=height / revolutions,
        )

    # -- handles ------------------------------------------------------------------------------------------
    def _handle_specs(self):
        o = self.options
        frame = primitives.global_frame(self.ref)
        u = frame.Rotation.multVec(App.Vector(1, 0, 0))
        n = frame.Rotation.multVec(App.Vector(0, 0, 1))
        center = frame.multVec(App.Vector(float(o["x"]), float(o["y"]), 0))
        specs = [
            (
                "diameter",
                center,
                u * -1.0,
                float(o["diameter"]),
                0.5,
                lambda v: self._size_value("diameter", self.diameter, v),
            )
        ]
        if "height" in coil.USES[o["type"]]:
            specs.append(("height", center, n, float(o["height"]), 1.0, self._height_dragged))
        return specs

    def _height_dragged(self, value):
        self._height_value(self.height, value)


def edit(feature):
    """Open the Coil dialog on an existing coil (timeline double-click)."""
    from . import commands

    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        if not coil.is_ours(feature):
            Gui.ActiveDocument.setEdit(feature.Name)
            return
        Gui.Control.showDialog(CoilPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


class CoilCommand:
    def GetResources(self):
        from . import ui_icon_path

        return {
            "MenuText": "Coil",
            "ToolTip": "Coil: pick a plane or flat face, click the centre and the diameter; "
            "revolutions, height, pitch, angle, section shape and size",
            "Pixmap": ui_icon_path("coil"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            start(CoilPanel)
        except Exception as exc:
            warn("Coil failed to start: %s" % exc)


COMMANDS = {"SciForge_Coil": CoilCommand}
EDITORS = {"SciForge::" + coil.KIND: edit}
