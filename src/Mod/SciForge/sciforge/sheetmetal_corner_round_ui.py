# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > MODIFY > Fillet / Chamfer: Fusion's sheet metal Fillet and Chamfer (Sep 2026).

Only the edges that run straight through the sheet's thickness (a plate's corners) light up
and can be picked, so the part can still be laid flat. Fillet takes radius sets: pick corners,
set the radius, press "+ New Set" to start another set with its own radius (Fusion's sets);
Chamfer takes a distance. On a body that is not sheet metal the commands open the SOLID
Fillet / Chamfer instead (the same buttons as Fusion's MODIFY menu repeat for solids).
Geometry: sheetmetal_corner_round.py.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, pickpanel, sheetmetal, sheetmetal_bend as sb
from . import sheetmetal_corner_round as sr
from . import ui_icon_path, warn
from . import sheetmetal_bend_panel as smp
from .compat import QtWidgets


class RoundPanel(smp.SmPanel):
    title = "Sheet Metal Fillet"
    icon = "sm_fillet"
    KIND = "fillet"
    BOXES = [("edges", "Edges", "Select corners", True)]
    last = None

    def default_options(self):
        return {"value": 2.0}

    def build_fields(self):
        label = "Radius" if self.KIND == "fillet" else "Distance"
        self.add_length("value", label, "%s of the corners in this set" % label)
        self.sets_label = QtWidgets.QLabel("")
        self.sets_label.setWordWrap(True)
        self.layout.addRow(self.sets_label)
        if self.KIND == "fillet":
            self.new_set = QtWidgets.QPushButton("+ New Set")
            self.new_set.setToolTip("Keep these corners with their radius and pick another set")
            self.new_set.clicked.connect(self._new_set)
            self.layout.addRow(self.new_set)
        if not hasattr(self, "sets"):
            self.sets = []
        self._show_sets()

    def _show_sets(self):
        lines = []
        for i, entry in enumerate(self.sets, start=1):
            lines.append(
                "Set %d: %d corner%s, %.4g mm"
                % (i, len(entry["edges"]), "" if len(entry["edges"]) == 1 else "s", entry["value"])
            )
        if lines:
            lines.append("Set %d: being picked" % (len(self.sets) + 1))
        self.sets_label.setText("\n".join(lines))

    def _new_set(self, *_):
        try:
            if self._closed or not self.picks["edges"]:
                return
            self.sets.append(
                {
                    "edges": [s for _o, s, _p in self.picks["edges"]],
                    "value": float(self.value("value")),
                }
            )
            self.picks["edges"] = []
            self._sync()
            self._picks_updated(schedule=False)
            self._show_sets()
            self.schedule()
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def all_sets(self):
        sets = [dict(s) for s in getattr(self, "sets", [])]
        if self.picks["edges"]:
            sets.append(
                {
                    "edges": [s for _o, s, _p in self.picks["edges"]],
                    "value": float(self.value("value")),
                }
            )
        return sets

    def ready(self):
        return bool(self.all_sets())

    def hint(self):
        if not self.picks["edges"] and not getattr(self, "sets", []):
            return "Click the plate's corners (the short edges through the sheet's thickness)."
        return "Click more corners, or a picked one to drop it."

    def accept_pick(self, box, obj, short):
        if obj is not self.base or not short.startswith("Edge"):
            return False
        for entry in getattr(self, "sets", []):
            if short in entry["edges"]:
                return False
        thickness = sb.rule_values(self.body)[0]
        return not sr.thickness_edge(self.base.Shape, short, thickness)

    def check(self, options):
        for entry in self.all_sets():
            if entry["value"] <= 0:
                raise sb.SheetMetalError(
                    "The %s must be more than 0."
                    % ("radius" if self.KIND == "fillet" else "distance")
                )

    def make_feature(self, options):
        return sr.make(self.body, self.base, self.KIND, self.all_sets())

    def apply_feature(self, options):
        sr.apply(self.target, self.base, self.all_sets())
        self.target.touch()

    def read_feature(self, feature):
        base, _kind, sets = sr.read(feature)
        self.sets = [dict(s) for s in sets[:-1]]
        last = sets[-1] if sets else {"edges": [], "value": 2.0}
        self.picks["edges"] = [(base, n, None) for n in last["edges"]]
        return {"value": last["value"]}


class ChamferPanel(RoundPanel):
    title = "Sheet Metal Chamfer"
    icon = "sm_chamfer"
    KIND = "chamfer"
    last = None


class ViewProviderRound(smp.StepViewProvider):
    ICON = "sm_fillet"

    def getIcon(self):
        from . import ui_icon_path as path

        try:
            if sr.kind_of(self.Object) == "chamfer":
                return path("sm_chamfer")
        except Exception:
            pass
        return path("sm_fillet")

    def edit(self, obj):
        edit(obj)


def edit(obj):
    smp.edit(ChamferPanel if sr.kind_of(obj) == "chamfer" else RoundPanel, obj)


def _start(panel_class, solid_commands):
    """The sheet metal dialog on a sheet metal body; on a solid body, the SOLID command."""
    try:
        preferred = pickpanel.selected_body() or commands.active_body()
        if preferred is not None and not sheetmetal.is_sheet_metal_body(preferred):
            for name in solid_commands:
                if name in Gui.listCommands():
                    Gui.runCommand(name)
                    return
        smp.start(panel_class)
    except Exception as exc:
        warn("%s could not start: %s" % (panel_class.title, exc))


class FilletCommand:
    def GetResources(self):
        return {
            "MenuText": "Fillet",
            "ToolTip": "Round the corners of sheet metal plates (only the edges through the "
            "thickness, so the part still lays flat); on a solid body, the SOLID Fillet",
            "Pixmap": ui_icon_path("sm_fillet"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start(RoundPanel, ("SciForge_Fillet", "PartDesign_Fillet"))


class ChamferCommand:
    def GetResources(self):
        return {
            "MenuText": "Chamfer",
            "ToolTip": "Chamfer the corners of sheet metal plates (only the edges through the "
            "thickness); on a solid body, the SOLID Chamfer",
            "Pixmap": ui_icon_path("sm_chamfer"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start(ChamferPanel, ("SciForge_Chamfer", "PartDesign_Chamfer"))


COMMANDS = {
    "SciForge_SheetMetalFillet": FilletCommand,
    "SciForge_SheetMetalChamfer": ChamferCommand,
}
EDITORS = {"SciForge::" + sr.KIND_FILLET: edit, "SciForge::" + sr.KIND_CHAMFER: edit}
smp.register_kinds(
    {sr.KIND_FILLET: ("Fillet", "sm_fillet"), sr.KIND_CHAMFER: ("Chamfer", "sm_chamfer")},
    {sr.KIND_FILLET: [("Size", "Radius")], sr.KIND_CHAMFER: [("Size", "Distance")]},
)
