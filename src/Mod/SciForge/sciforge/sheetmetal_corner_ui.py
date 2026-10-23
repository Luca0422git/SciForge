# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > MODIFY > Corner Closure, with Fusion's dialog.

Click the Dominant Edge and the Submissive Edge: an edge at the end of each of the two flanges
that meet at a corner (where they face each other). Alignment Symmetric Gap (both close to the
corner's bisector, the Gap between them) or Overlap (the dominant runs over the other's end;
Overlap 0..1 of the thickness, Flip Overlap swaps which), the Gap (the rule's Miter/Rip/Seam
gap unless you set your own), Extend Aligned, and the relief shape (Trim To Bend; Round and
Square are greyed with the reason). Geometry: sheetmetal_corner.py.
"""

import FreeCAD as App

from . import sheetmetal_bend as sb, sheetmetal_bend_core as core, sheetmetal_corner as sc
from . import ui_icon_path
from . import sheetmetal_bend_panel as smp

ALIGN_ITEMS = [
    ("Symmetric Gap", "symmetric", True, "Both flanges close to the corner, the gap between"),
    ("Overlap", "overlap", True, "One flange runs over the other's end"),
]
RELIEF_ITEMS = [
    ("Trim To Bend", "trim_to_bend", True, "The bends end where they are; the corner stays open"),
    (
        "Round",
        "round",
        False,
        "Not available yet in SciForge: needs the flat-state relief "
        "mapped onto the folded corner",
    ),
    (
        "Square",
        "square",
        False,
        "Not available yet in SciForge: needs the flat-state relief "
        "mapped onto the folded corner",
    ),
]


class CornerPanel(smp.SmPanel):
    title = "Corner Closure"
    icon = "sm_corner_closure"
    BOXES = [
        ("dominant", "Dominant Edge", "Select an edge", False),
        ("submissive", "Submissive Edge", "Select an edge", False),
    ]
    last = None

    def default_options(self):
        opts = sc.default_options()
        try:
            opts["gap_value"] = float(sb.rule_values(self.body)[3]["miter_gap"])
        except Exception:
            opts["gap_value"] = 1.0
        opts["use_rule_gap"] = True
        return opts

    def build_fields(self):
        self.add_combo("alignment", "Alignment", ALIGN_ITEMS)
        self.add_check("use_rule_gap", "Rule Gap", "Use the rule's Miter/Rip/Seam gap")
        self.add_length("gap_value", "Gap", "Space left at the corner")
        self.add_number("overlap", "Overlap", "0 = none, 1 = the full thickness", 0.0, 1.0, 2)
        self.add_check("flip_overlap", "Flip Overlap", "The other flange runs over")
        self.add_check(
            "extend_aligned",
            "Extend Aligned",
            "Close in line with the flanges (off: not available yet)",
        )
        self.fields["extend_aligned"].setEnabled(False)
        self.add_combo("relief", "Relief Shape", RELIEF_ITEMS, "Corner relief")
        self.fields_changed("alignment")

    def fields_changed(self, key):
        overlap = self.value("alignment") == "overlap"
        self.show_row("overlap", overlap)
        self.show_row("flip_overlap", overlap)
        self.show_row("gap_value", not self.value("use_rule_gap"))

    def hint(self):
        if not self.picks["dominant"]:
            return "Click an edge at the end of the first flange, at the corner."
        if not self.picks["submissive"]:
            return "Click an edge at the end of the other flange, at the same corner."
        return "The corner is closed. Change the alignment or the gap, then OK."

    def accept_pick(self, box, obj, short):
        if obj is not self.base or not short.startswith("Edge"):
            return False
        thickness = sb.rule_values(self.body)[0]
        try:
            sc.end_frame(self.base.Shape, short, thickness)
        except sb.SheetMetalError:
            return False
        other = "submissive" if box == "dominant" else "dominant"
        return not any(s == short for _o, s, _p in self.picks[other])

    def collect(self):
        opts = super().collect()
        opts["gap"] = None if opts.get("use_rule_gap") else float(opts.get("gap_value") or 0.0)
        return opts

    def check(self, options):
        if options.get("relief") != "trim_to_bend":
            raise sb.SheetMetalError("Only Trim To Bend relief is available yet.")
        core.closure_reach(
            options["alignment"], options["gap"] or 0.0, 1.0, float(options.get("overlap", 1.0))
        )

    def _edges(self):
        return self.picks["dominant"][0][1], self.picks["submissive"][0][1]

    def make_feature(self, options):
        dominant, submissive = self._edges()
        return sc.make(self.body, self.base, dominant, submissive, options)

    def apply_feature(self, options):
        dominant, submissive = self._edges()
        sc.apply(self.target, self.base, dominant, submissive, options)
        self.target.touch()

    def read_feature(self, feature):
        base, dominant, submissive, options = sc.read(feature)
        if dominant:
            self.picks["dominant"] = [(base, dominant, None)]
        if submissive:
            self.picks["submissive"] = [(base, submissive, None)]
        options["use_rule_gap"] = options.get("gap") is None
        options["gap_value"] = (
            float(feature.Gap)
            if options.get("gap") is not None
            else float(sb.rule_values(self.body)[3]["miter_gap"])
        )
        return options


class ViewProviderCornerClosure(smp.StepViewProvider):
    ICON = "sm_corner_closure"

    def edit(self, obj):
        edit(obj)


def edit(obj):
    smp.edit(CornerPanel, obj)


class CornerCommand:
    def GetResources(self):
        return {
            "MenuText": "Corner Closure",
            "ToolTip": "Close the corner where two flanges meet: symmetric gap or overlap",
            "Pixmap": ui_icon_path("sm_corner_closure"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        smp.start(CornerPanel)


COMMANDS = {"SciForge_SheetMetalCornerClosure": CornerCommand}
EDITORS = {"SciForge::" + sc.KIND: edit}
smp.register_kinds(
    {sc.KIND: ("Corner Closure", "sm_corner_closure")},
    {sc.KIND: [("Gap", "Gap"), ("Overlap", "Overlap")]},
)
