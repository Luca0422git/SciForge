# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > CREATE > Join by Bend, with Fusion's dialog (Fusion, Sep 2026).

Click the First Edge (an edge of this sheet metal body's outline), then the Second Edge (on
another sheet metal body of the same thickness): both plates are extended or trimmed so one
bend of the rule's radius (or your Bend Radius) joins them into one body; the other body is
used up (hidden while the step is in the design, back when it is deleted or undone).
Refusals (different thickness, parallel sheets, edges that do not line up) are explained in
the dialog. Geometry: sheetmetal_bend_join.py.
"""

import FreeCAD as App

from . import bodies, sheetmetal, sheetmetal_bend as sb, sheetmetal_bend_join as sj
from . import ui_icon_path
from . import sheetmetal_bend_panel as smp


class JoinBendPanel(smp.SmPanel):
    title = "Join by Bend"
    icon = "sm_join_bend"
    BOXES = [
        ("first", "First Edge", "Select an edge", False),
        ("second", "Second Edge", "Select an edge", False),
    ]
    last = None

    def default_options(self):
        opts = sj.default_options()
        try:
            opts["radius"] = sb.rule_values(self.body)[1]
        except Exception:
            opts["radius"] = 1.0
        return opts

    def build_fields(self):
        self.add_check(
            "use_rule_radius",
            "Use Rule Bend Radius",
            "The joining bend takes the sheet metal rule's radius",
        )
        self.add_length("radius", "Bend Radius", "Inner radius of the joining bend")
        self.fields_changed("use_rule_radius")

    def fields_changed(self, key):
        self.show_row("radius", not self.value("use_rule_radius"))

    def _kept(self):
        """Editing a step whose other body was deleted, no new Second Edge picked: the step
        goes on joining the copy it kept of that body."""
        return (
            self.editing
            and not self.picks["second"]
            and self.target is not None
            and sj.kept_other(self.target)
        )

    def ready(self):
        return bool(self.picks["first"]) and (bool(self.picks["second"]) or self._kept())

    def _refresh_boxes(self):
        super()._refresh_boxes()
        if self._kept() and "second" in self.boxes:
            self.boxes["second"].set_text("Deleted body (kept)")

    def hint(self):
        if not self.picks["first"]:
            return "Click an edge of this sheet metal body where the bend should start."
        if self._kept():
            return (
                "The other body was deleted: the step joins it as it was. Click an edge of "
                "another sheet metal body to join that one instead."
            )
        if not self.picks["second"]:
            return "Click an edge of the other sheet metal body to join."
        return "The two plates are joined by one bend. OK to keep it."

    def _other_body(self, obj):
        body = bodies.body_of(obj)
        if body is None or body is self.body or not sheetmetal.is_sheet_metal_body(body):
            return None
        return body if body.Tip is obj else None

    def accept_pick(self, box, obj, short):
        if not short.startswith("Edge"):
            return False
        if box == "first":
            if obj is not self.base:
                return False
            thickness = sb.rule_values(self.body)[0]
            shape = self.base.Shape
        else:
            other = self._other_body(obj)
            if other is None:
                return False
            thickness = sb.rule_values(other)[0]
            shape = obj.Shape
        try:
            sb.edge_frame(shape, short, thickness)
        except sb.SheetMetalError:
            return False
        return True

    def check(self, options):
        if not self.picks["second"]:
            return  # the kept copy of a deleted body: its edge was checked when picked
        other = bodies.body_of(self.picks["second"][0][0])
        mine = sb.rule_values(self.body)[0]
        theirs = sb.rule_values(other)[0]
        if abs(mine - theirs) > 1e-6:
            raise sb.SheetMetalError(
                "The two bodies have different thicknesses (%.4g and %.4g mm): Join by Bend "
                "needs sheets of the same thickness." % (mine, theirs)
            )

    def _refs(self):
        first = self.picks["first"][0][1]
        if not self.picks["second"]:
            return first, None, ""  # the kept copy of a deleted body (an edit)
        other, second = self.picks["second"][0][0], self.picks["second"][0][1]
        return first, other, second

    def make_feature(self, options):
        first, other, second = self._refs()
        return sj.make(self.body, self.base, first, other, second, options)

    def apply_feature(self, options):
        first, other, second = self._refs()
        sj.apply(self.target, self.base, first, other, second, options)
        self.target.touch()

    def read_feature(self, feature):
        base, first, other, second, options = sj.read(feature)
        if first:
            self.picks["first"] = [(base, first, None)]
        if other is not None and second:
            self.picks["second"] = [(other, second, None)]
        self.active = "second"
        return options

    def finished(self, obj):
        try:
            bodies.sync_consumed(self.doc)
        except Exception:
            pass


class ViewProviderJoinBend(smp.StepViewProvider):
    ICON = "sm_join_bend"

    def edit(self, obj):
        edit(obj)


def edit(obj):
    smp.edit(JoinBendPanel, obj)


class JoinBendCommand:
    def GetResources(self):
        return {
            "MenuText": "Join by Bend",
            "ToolTip": "Join two sheet metal bodies of the same thickness with one bend",
            "Pixmap": ui_icon_path("sm_join_bend"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        smp.start(JoinBendPanel)


COMMANDS = {"SciForge_SheetMetalJoinBend": JoinBendCommand}
EDITORS = {"SciForge::" + sj.KIND: edit}
smp.register_kinds(
    {sj.KIND: ("Join by Bend", "sm_join_bend")}, {sj.KIND: [("BendRadius", "Bend Radius")]}
)
