# SPDX-License-Identifier: LGPL-2.1-or-later
"""MODIFY > Rip of the SHEET METAL tab (Fusion's behaviour; rip.py does the work).

Type Face: pick the face to remove (a bend or a corner face). Along Edge: pick a straight
edge where two walls meet; a gap of the given width is cut along it. Between Points: pick two
points on one face (vertices, or edges with an offset from the edge's start); a straight
slot of the given width is cut between them. The gap defaults to the rule's
Miter/Rip/Seam Gap. The preview is the step itself.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, rip, sheetmetal, taskui, ui_icon_path, warn
from .compat import QtWidgets
from .unfold_panel import SheetPanel, a_point, an_edge, any_face


class RipPanel(SheetPanel):
    title = "Rip"
    icon = "sm_rip"
    SLOTS = (
        ("face", "Face", any_face, False),
        ("edge", "Edge", an_edge, False),
        ("point1", "Point 1", a_point, False),
        ("point2", "Point 2", a_point, False),
    )
    TYPE_SLOTS = {"face": ("face",), "edge": ("edge",), "points": ("point1", "point2")}

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Rip" if feature is None else "Edit Rip", feature)

    def build_fields(self):
        self.kind = QtWidgets.QComboBox()
        self.kind.setObjectName("SciForgeRipType")
        for key in rip.TYPES:
            self.kind.addItem(rip.LABELS[key], key)
        self.kind.setCurrentIndex(list(rip.TYPES).index("edge"))
        self.layout.addRow("Type", self.kind)
        self.add_slot_rows()
        self.gap = taskui.DistanceField(rip.default_gap(self.body), on_change=self._changed)
        self.offset1 = taskui.DistanceField(0.0, on_change=self._changed)
        self.offset2 = taskui.DistanceField(0.0, on_change=self._changed)
        self.layout.addRow("Gap Distance", self.gap.widget)
        self.layout.addRow("Offset 1", self.offset1.widget)
        self.layout.addRow("Offset 2", self.offset2.widget)
        self.kind.currentIndexChanged.connect(lambda _i: self._kind_changed())
        self._kind_changed(update=False)

    def _changed(self, *_args):
        self.update()

    def type_key(self):
        return self.kind.currentData() or "edge"

    def _kind_changed(self, update=True):
        keys = self.TYPE_SLOTS[self.type_key()]
        for key, box in self.boxes.items():
            box.setVisible(key in keys)
            label = self.layout.labelForField(box)
            if label is not None:
                label.setVisible(key in keys)
        points = self.type_key() == "points"
        for field in (self.offset1, self.offset2):
            field.widget.setVisible(points)
            label = self.layout.labelForField(field.widget)
            if label is not None:
                label.setVisible(points)
        self.gap.widget.setEnabled(self.type_key() != "face")
        if update:
            self._sync()
            self.update()

    def active_slots(self):
        keys = self.TYPE_SLOTS[self.type_key()]
        slots = [s for s in self.SLOTS if s[0] in keys]
        if self.type_key() == "points" and self.picks["point1"]:
            slots.reverse()  # point 1 is there: the next click is point 2
        return slots

    def shown(self):
        keys = self.TYPE_SLOTS[self.type_key()]
        names = []
        for key in keys:
            names += [n for n in self.picks.get(key, []) if n not in names]
        return [(self.base, names)] if self.base is not None and names else []

    def load(self, feature):
        spec = rip.spec_of(feature)
        for key in ("face", "edge", "point1", "point2"):
            self.picks[key] = [spec[key]] if spec[key] else []
        self.kind.blockSignals(True)
        self.kind.setCurrentIndex(list(rip.TYPES).index(spec["type"]))
        self.kind.blockSignals(False)
        self.gap.set_value(spec["gap"])
        self.offset1.set_value(spec["offset1"])
        self.offset2.set_value(spec["offset2"])
        self._kind_changed(update=False)

    def spec(self):
        return {
            "type": self.type_key(),
            "face": self.pick("face"),
            "edge": self.pick("edge"),
            "point1": self.pick("point1"),
            "point2": self.pick("point2"),
            "offset1": self.offset1.value(),
            "offset2": self.offset2.value(),
            "gap": self.gap.value(),
        }

    def update(self):
        try:
            self._update()
        except Exception as exc:
            self.say("⚠ %s" % exc)

    def _update(self):
        if self._closed or self.base is None:
            return
        spec = self.spec()
        need = self.TYPE_SLOTS[spec["type"]]
        if not all(spec[k] for k in need):
            self.say(
                {
                    "face": "Pick the face to rip away (a bend or a corner face).",
                    "edge": "Pick a straight edge where two walls meet.",
                    "points": "Pick two points on one face (vertices or edges).",
                }[spec["type"]]
            )
            return
        try:
            rip.build(self.base.Shape, spec)
        except rip.RipError as exc:
            self.say("⚠ %s" % exc)
            return
        if self.target is None:
            self.target = rip.make(self.body, self.base, spec)
        else:
            rip.apply(self.target, self.base, spec)
        self.quiet_recompute()
        self.show_preview(True)
        self.say("")

    def ready(self):
        # OK keeps what the dialog shows now (QA: after a refused pick or value the step
        # still held the last good rip, and OK kept that one under the error message)
        spec = self.spec()
        if not all(spec[k] for k in self.TYPE_SLOTS[spec["type"]]) or self.target is None:
            return "Finish the picks first."
        try:
            rip.build(self.base.Shape, spec)
        except rip.RipError as exc:
            return str(exc)
        rip.apply(self.target, self.base, spec)
        return None


def _start():
    try:
        if not commands.finish_open_dialog():
            return
        doc = App.ActiveDocument
        if doc is None:
            return
        if not sheetmetal.sheet_metal_bodies(doc):
            commands.tell(
                "Rip works on sheet metal: make a Flange or use Convert to Sheet Metal first."
            )
            return
        Gui.Control.showDialog(RipPanel(doc))
        log("rip started")
    except Exception as exc:
        warn("Rip failed to start: %s" % exc)


def edit(feature):
    try:
        Gui.Control.showDialog(RipPanel(feature.Document, feature))
    except Exception as exc:
        warn("Edit Rip: %s" % exc)


class RipCommand:
    def GetResources(self):
        return {
            "MenuText": "Rip",
            "ToolTip": "Open a closed sheet (a tube, a box) along a face, an edge or a line",
            "Pixmap": ui_icon_path("sm_rip"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start()


COMMANDS = {"SciForge_Rip": RipCommand}
EDITORS = {"SciForge::Rip": edit}
