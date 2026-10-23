# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > CREATE > Hem, with Fusion's dialog.

Click the edges to hem (edges where the sheet's top or bottom face meets its side; several can
be picked, a picked one clicked again is dropped). Type Flat / Open / Rolled / Teardrop / Rope /
Double, each with its own values (Length, Gap, Radius, Angle, Setback), Bend Position Inside /
Outside / Adjacent / Tangent, Flip (hem to the other side), Miter Corners (where two hemmed
edges meet), and a Bend Radius override (the Rope's reverse bend). The blue arrow drags the
Length, with its value box. Double-click the step in the timeline to edit. Geometry:
sheetmetal_hem.py.
"""

import FreeCAD as App

from . import sheetmetal_bend as sb, sheetmetal_bend_core as core, sheetmetal_hem as sh
from . import pickpanel, ui_icon_path, warn
from . import sheetmetal_bend_panel as smp

TYPE_ITEMS = [(core.HEM_LABELS[k], k) for k in core.HEM_TYPES]
POSITION_ITEMS = [
    ("Inside", "inside", True, "The hem's outside stays at the edge (the part keeps its size)"),
    ("Outside", "outside", True, "The fold's inside is at the edge"),
    ("Adjacent", "adjacent", True, "The fold starts at the edge"),
    ("Tangent", "tangent", True, "The fold is tangent to the edge's side face"),
]
VALUE_ROWS = ("length", "gap", "radius", "angle", "setback")


class HemPanel(smp.SmPanel):
    title = "Hem"
    icon = "sm_hem"
    BOXES = [("edges", "Edges", "Select edges", True)]
    last = None

    def default_options(self):
        try:
            thickness, radius = sb.rule_values(self.body)[:2]
        except Exception:
            thickness, radius = 1.0, 1.0
        opts = sh.default_options(thickness)
        opts["radius_override"] = radius
        return opts

    def build_fields(self):
        self.add_combo("type", "Type", TYPE_ITEMS, "The hem's shape")
        self.add_length("length", "Length", "From the hem's outside back over the sheet")
        self.add_length("gap", "Gap", "Space between the sheet and the hem")
        self.add_length("radius", "Radius", "Inner radius of the roll")
        self.add_angle("angle", "Angle", "How far a Rolled hem rolls")
        self.add_length("setback", "Setback", "Double: how far the second run stops short")
        self.add_combo("position", "Bend Position", POSITION_ITEMS, "Where the fold sits")
        self.add_check("flip", "Flip", "Hem to the other side of the sheet")
        self.add_check("miter", "Miter Corners", "Mitre where two hemmed edges meet")
        self.add_check("override", "Override Rules", "Use your own bend radius (Rope)")
        self.add_length("radius_override", "Bend Radius", "Bend radius instead of the rule's")
        self.fields_changed("type")

    def fields_changed(self, key):
        kind = self.value("type")
        used = core.HEM_VALUES.get(kind, ())
        for row in VALUE_ROWS:
            self.show_row(row, row in used)
        self.show_row("radius_override", bool(self.value("override")))
        if key in ("type", "length", "flip", "position"):
            self.after_preview()

    def hint(self):
        if not self.picks["edges"]:
            return "Click the edges to hem (where the sheet's face meets its side)."
        return "Click more edges, or a picked one to drop it. Drag the arrow for the Length."

    def accept_pick(self, box, obj, short):
        if obj is not self.base or not short.startswith("Edge"):
            return False
        thickness = sb.rule_values(self.body)[0]
        try:
            sb.edge_frame(self.base.Shape, short, thickness)
        except sb.SheetMetalError:
            return False
        return True

    def names(self):
        return [short for _o, short, _p in self.picks["edges"]]

    def check(self, options):
        thickness, radius = sb.rule_values(self.body)[:2]
        if options.get("override"):
            radius = float(options.get("radius_override") or radius)
        try:
            core.hem_segments(options, thickness, radius)
        except ValueError as exc:
            raise sb.SheetMetalError(str(exc))

    def make_feature(self, options):
        return sh.make(self.body, self.base, self.names(), options)

    def apply_feature(self, options):
        sh.apply(self.target, self.base, self.names(), options)
        self.target.touch()

    def read_feature(self, feature):
        base, names, options = sh.read(feature)
        self.picks["edges"] = [(base, n, None) for n in names]
        return options

    # -- the Length arrow ----------------------------------------------------------------
    def after_preview(self):
        try:
            self._make_arrow()
        except Exception as exc:
            warn("Hem arrow unavailable: %s" % exc)

    def _make_arrow(self):
        if self._closed:
            return
        arrow = self.handles.get("length")
        if arrow is not None:
            try:
                if arrow.busy():
                    return
            except Exception:
                pass
            arrow.remove()
            self.handles.pop("length", None)
        if not self.picks["edges"] or self.value("type") == "rolled":
            return
        thickness = sb.rule_values(self.body)[0]
        frame = sb.edge_frame(self.base.Shape, self.picks["edges"][0][1], thickness)
        place = self.body.getGlobalPlacement()
        mid = (frame["start"] + frame["end"]) * 0.5
        up = frame["normal"] * (-1.0 if self.value("flip") else 1.0)
        lift = up * (thickness * 3.0)
        origin = place.multVec(mid + lift)
        direction = place.Rotation.multVec(frame["out"] * -1.0)
        size = max(3.0, min(self.base.Shape.BoundBox.DiagonalLength * 0.06, 12.0))
        handle = pickpanel.Arrow(
            origin,
            direction,
            float(self.value("length")),
            size * 2.2,
            on_drag=self._dragged,
            on_release=self._dragged,
        )
        self.handles["length"] = handle
        field = self.fields["length"]
        self.value_boxes.attach(handle, "length", lambda: field.widget.text(), self._typed)

    def _dragged(self, distance):
        if self._closed:
            return
        self.set_value("length", max(0.1, round(float(distance), 2)))
        self.schedule()

    def _typed(self, text):
        if self._closed:
            return
        field = self.fields["length"]
        try:
            field.take(field.parse(text))
        except Exception:
            pass
        self.schedule()


class ViewProviderHem(smp.StepViewProvider):
    ICON = "sm_hem"

    def edit(self, obj):
        edit(obj)


def edit(obj):
    smp.edit(HemPanel, obj)


class HemCommand:
    def GetResources(self):
        return {
            "MenuText": "Hem",
            "ToolTip": "Fold sheet metal edges back on themselves: Flat, Open, Rolled, "
            "Teardrop, Rope or Double",
            "Pixmap": ui_icon_path("sm_hem"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        smp.start(HemPanel)


COMMANDS = {"SciForge_SheetMetalHem": HemCommand}
EDITORS = {"SciForge::" + sh.KIND: edit}
smp.register_kinds(
    {sh.KIND: ("Hem", "sm_hem")},
    {sh.KIND: [("Length", "Length"), ("Gap", "Gap"), ("Radius", "Radius")]},
)
