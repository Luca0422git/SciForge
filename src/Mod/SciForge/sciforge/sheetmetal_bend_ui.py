# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > CREATE > Bend, with Fusion's dialog (Fusion's Fold).

Click the Stationary Side (a top or bottom face of the sheet, on the side that stays), then
the Bend Lines (straight sketch lines drawn on that face; several can be picked). Angle,
Bend Line position Start / Center / End (where the line sits on the bend zone in the flat
sheet), Flip (bend down instead of up), Bend Relief / Corner Relief, and a Bend Radius
override. The sheet swings round live; the round handle on the bend drags the angle, with its
value box. Double-click the step in the timeline to edit. Geometry: sheetmetal_bend.py.
"""

import FreeCAD as App

from . import bodies, sheetmetal_bend as sb, sheetmetal_bend_core as core, ui_icon_path, warn
from . import sheetmetal_bend_panel as smp

POSITION_ITEMS = [
    ("Start", "start", True, "The line is where the bend starts (stationary side)"),
    ("Center", "center", True, "The line is the middle of the bend"),
    ("End", "end", True, "The line is where the bend ends (moving side)"),
]


class BendPanel(smp.SmPanel):
    title = "Bend"
    icon = "sm_bend"
    BOXES = [
        ("stationary", "Stationary Side", "Select a face", False),
        ("lines", "Bend Lines", "Select lines", True),
    ]
    last = None

    def default_options(self):
        opts = sb.default_options()
        try:
            opts["radius"] = sb.rule_values(self.body)[1]
        except Exception:
            opts["radius"] = 1.0
        return opts

    def build_fields(self):
        self.add_angle("angle", "Angle", "How far the sheet is bent (90° = square)")
        self.add_combo(
            "position",
            "Bend Line",
            POSITION_ITEMS,
            "Where the sketch line sits on the bend zone in the flat sheet",
        )
        self.add_check("flip", "Flip", "Bend the other way (down instead of up)")
        self.add_check(
            "bend_relief",
            "Bend Relief",
            "SciForge bends the sheet right across, so no relief cut is needed",
        )
        self.add_check(
            "corner_relief",
            "Corner Relief",
            "Corner relief where bend lines meet (bend lines may not cross yet)",
        )
        self.add_check(
            "override_radius",
            "Override Bend Radius",
            "Use this radius instead of the sheet metal rule's",
        )
        self.add_length("radius", "Bend Radius", "Inner bend radius")
        self.fields_changed("override_radius")

    def fields_changed(self, key):
        self.show_row("radius", bool(self.value("override_radius")))
        if key in ("angle", "flip", "position"):
            self.after_preview()

    def hint(self):
        if not self.picks["stationary"]:
            return "Click the face that stays where it is (top or bottom of the sheet)."
        if not self.picks["lines"]:
            return "Click the sketch lines to bend along (draw them on that face first)."
        return "Click more lines, or a picked one to drop it. Drag the round handle for the angle."

    def accept_pick(self, box, obj, short):
        if box == "stationary":
            if obj is not self.base or not short.startswith("Face"):
                return False
            thickness = sb.rule_values(self.body)[0]
            face = self.base.Shape.getElement(short)
            return sb.is_plane(face) and sb.face_thickness(self.base.Shape, face, thickness)
        if box == "lines":
            if obj.TypeId != "Sketcher::SketchObject" or not short.startswith("Edge"):
                return False
            import Part

            edge = obj.Shape.getElement(short)
            return isinstance(edge.Curve, (Part.Line, Part.LineSegment))
        return False

    def _local_point(self):
        obj, short, point = self.picks["stationary"][0]
        place = self.body.getGlobalPlacement()
        if point is None:
            return obj.Shape.getElement(short).CenterOfMass
        return place.inverse().multVec(point)

    def _lines(self):
        grouped = []
        for obj, short, _p in self.picks["lines"]:
            for entry in grouped:
                if entry[0] is obj:
                    entry[1].append(short)
                    break
            else:
                grouped.append((obj, [short]))
        return grouped

    def collect(self):
        opts = super().collect()
        opts["radius"] = float(self.value("radius"))
        return opts

    def check(self, options):
        problems = core.check_bend(float(options["angle"]), 1.0, 1.0)
        if problems:
            raise sb.SheetMetalError(problems[0])

    def make_feature(self, options):
        face = self.picks["stationary"][0][1]
        return sb.make(self.body, self.base, face, self._local_point(), self._lines(), options)

    def apply_feature(self, options):
        face = self.picks["stationary"][0][1]
        sb.apply(self.target, self.base, face, self._local_point(), self._lines(), options)
        self.target.touch()

    def read_feature(self, feature):
        base, face, point, lines, options = sb.read(feature)
        place = bodies.body_of(feature).getGlobalPlacement()
        if face:
            self.picks["stationary"] = [(base, face, place.multVec(point))]
        self.picks["lines"] = [(o, s, None) for o, subs in lines for s in subs]
        self.active = "lines"
        return options

    # -- the angle handle ----------------------------------------------------------------
    def after_preview(self):
        try:
            self._make_handle()
        except Exception as exc:
            warn("Bend handle unavailable: %s" % exc)

    def _make_handle(self):
        from . import revolve_ui

        if self._closed:
            return
        handle = self.handles.get("angle")
        if handle is not None:
            try:
                if handle.dragging():
                    return
            except Exception:
                pass
            handle.remove()
            self.handles.pop("angle", None)
        if not self.ready() or self.target is None:
            return
        opts = self.collect()
        frame = bend_frame(
            self.base, self.picks["stationary"][0][1], self._local_point(), self._lines(), opts
        )
        if frame is None:
            return
        place = self.body.getGlobalPlacement()
        centre, axis, zero, size = frame
        centre = place.multVec(centre)
        axis = place.Rotation.multVec(axis)
        zero = place.Rotation.multVec(zero)
        self.handles["angle"] = revolve_ui.AngleHandle(
            centre,
            axis,
            zero,
            size,
            float(opts["angle"]),
            size * 0.3,
            on_drag=self._dragged,
            on_release=self._dragged,
        )
        field = self.fields["angle"]
        self.value_boxes.attach(
            self.handles["angle"], "angle", lambda: field.widget.text(), self._typed_angle
        )

    def _dragged(self, angle):
        if self._closed:
            return
        value = max(1.0, min(180.0, round(abs(float(angle)), 1)))
        self.set_value("angle", value)
        self.schedule()

    def _typed_angle(self, text):
        if self._closed:
            return
        field = self.fields["angle"]
        try:
            field.take(field.parse(text))
        except Exception:
            pass
        self.schedule()


def bend_frame(base, face_name, point, lines, options):
    """(centre, axis, zero, size) of the angle handle for the first bend line (body-local):
    on the bend's axis, turning the way the bend does, from the flat moving side."""
    try:
        shape = base.Shape
        face = shape.getElement(face_name)
        flat = sb.bend_lines_on(face, sb.line_points(lines))
    except Exception:
        return None
    if not flat:
        return None
    normal = sb.plane_normal(face)
    a, b = flat[0]
    along = sb.unit(b - a)
    across = normal.cross(along)
    if (point - a).dot(across) > 0:
        along = along * -1.0
        across = across * -1.0
    up = not bool(options.get("flip"))
    mid = (a + b) * 0.5
    size = max(4.0, min(shape.BoundBox.DiagonalLength * 0.15, 25.0))
    axis = along if up else along * -1.0
    return mid, axis, across, size


class ViewProviderBend(smp.StepViewProvider):
    ICON = "sm_bend"

    def edit(self, obj):
        edit(obj)


def edit(obj):
    smp.edit(BendPanel, obj)


class BendCommand:
    def GetResources(self):
        return {
            "MenuText": "Bend",
            "ToolTip": "Bend a flat sheet metal body along sketch lines: pick the face that "
            "stays, then the lines; angle, bend line position and flip",
            "Pixmap": ui_icon_path("sm_bend"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        smp.start(BendPanel)


COMMANDS = {"SciForge_SheetMetalBend": BendCommand}
EDITORS = {"SciForge::" + sb.KIND: edit}
smp.register_kinds({sb.KIND: ("Bend", "sm_bend")}, {sb.KIND: [("Angle", "Angle")]})
