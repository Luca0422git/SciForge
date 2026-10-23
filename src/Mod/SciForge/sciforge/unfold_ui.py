# SPDX-License-Identifier: LGPL-2.1-or-later
"""MODIFY > Unfold and Refold of the SHEET METAL tab (Fusion's behaviour, sheetmetal_flat.py
does the work).

Unfold: pick the Stationary Entity (a flat top or bottom face of a wall) and the Bends to lay
flat (their inner or outer faces), or tick Unfold All Bends (off by default, like Fusion's).
The body is shown flat at once (the preview is the step itself); the steps after it (a
sketch and an extrude cut across a bend) work on the flat body until a Refold.
Refold: folds every bend the open Unfold laid flat back, carrying cuts made meanwhile onto
the folded walls and bends; the Unfold ... Refold steps are grouped in the timeline.

Also the timeline names and icons of the flat steps (Unfold, Refold, Rip, Convert to Sheet
Metal) and the view provider they share.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, log, sheetmetal, sheetmetal_flat, taskui, ui_icon_path, warn
from .compat import QtWidgets
from .unfold_panel import SheetPanel, bend_face, planar_face

ICONS = {
    "Unfold": "sm_unfold",
    "Refold": "sm_refold",
    "Rip": "sm_rip",
    "ConvertToSheetMetal": "sm_convert",
}


def _register_timeline():
    try:
        from . import parameters, timeline_core

        timeline_core.KINDS.update(
            {
                "unfold": ("Unfold", "sm_unfold"),
                "refold": ("Refold", "sm_refold"),
                "rip": ("Rip", "sm_rip"),
                "convert_to_sheet_metal": ("Convert to Sheet Metal", "sm_convert"),
            }
        )
        parameters.SCIFORGE_PROPS.setdefault("Rip", [("Gap", "Gap")])
    except Exception as exc:
        warn("sheet metal timeline kinds: %s" % exc)


_register_timeline()


class ViewProviderFlatStep:
    """Browser / timeline look of Unfold, Refold, Rip and Convert steps. Saved files store
    "sciforge.unfold_ui.ViewProviderFlatStep": never rename."""

    def __init__(self, vobj, kind=None):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        kind = bodies.kind(getattr(self, "Object", None))
        return ui_icon_path(ICONS.get(kind, "sm_unfold"))

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        _edit_later(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        _edit_later(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _edit_later(obj):
    try:
        from .compat import QtCore

        def run():
            try:
                taskui.edit_object(obj)
            except Exception as exc:
                warn("edit %s: %s" % (getattr(obj, "Label", "?"), exc))

        QtCore.QTimer.singleShot(0, run)
    except Exception as exc:
        warn("edit %s: %s" % (getattr(obj, "Label", "?"), exc))


# -- Unfold --------------------------------------------------------------------------------------
class UnfoldPanel(SheetPanel):
    title = "Unfold"
    icon = "sm_unfold"
    SLOTS = (
        ("face", "Stationary Entity", planar_face, False),
        ("bends", "Bends", bend_face, True),
    )

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Unfold" if feature is None else "Edit Unfold", feature)

    def build_fields(self):
        self.add_slot_rows()
        self.all_bends = QtWidgets.QCheckBox("Unfold All Bends")
        self.all_bends.setObjectName("SciForgeUnfoldAll")
        self.all_bends.toggled.connect(lambda _on: self.update())
        self.layout.addRow(self.all_bends)
        self.info = QtWidgets.QLabel("Pick a flat face that stays put, then the bends to lay flat.")
        self.info.setWordWrap(True)
        self.layout.addRow(self.info)

    def load(self, feature):
        link = feature.Stationary
        if link:
            subs = link[1] if isinstance(link[1], (list, tuple)) else [link[1]]
            self.picks["face"] = [s.lstrip("?") for s in subs if s][:1]
        names = []
        for _obj, subs in feature.Bends or []:
            subs = subs if isinstance(subs, (list, tuple)) else [subs]
            names += [s.lstrip("?") for s in subs if s]
        self.picks["bends"] = names
        self.all_bends.blockSignals(True)
        self.all_bends.setChecked(bool(feature.UnfoldAll))
        self.all_bends.blockSignals(False)

    def active_slots(self):
        if self.all_bends.isChecked():
            return self.SLOTS[:1]
        return self.SLOTS

    def update(self):
        try:
            self._update()
        except Exception as exc:
            self.say("⚠ %s" % exc)

    def _update(self):
        if self._closed or self.base is None:
            return
        face = self.pick("face")
        bends = [] if self.all_bends.isChecked() else list(self.picks["bends"])
        if not face:
            self.say("Pick the Stationary Entity: a flat top or bottom face of a wall.")
            return
        if not bends and not self.all_bends.isChecked():
            self.say("Pick the bends to unfold, or tick Unfold All Bends.")
            return
        if self.target is None:
            self.target = sheetmetal_flat.make_unfold(
                self.body, self.base, face, bends, self.all_bends.isChecked()
            )
        else:
            sheetmetal_flat.update_unfold(
                self.target, self.base, face, bends, self.all_bends.isChecked()
            )
        self.quiet_recompute()
        self.show_preview(True)
        state = list(self.target.State)
        if "Invalid" in state or "Error" in state:
            self.say("⚠ " + self.target.getStatusString())
        else:
            self.say("")
            self.info.setText("%d bend(s) laid flat." % self.target.BendCount)

    def ready(self):
        face = self.pick("face")
        unfold_all = self.all_bends.isChecked()
        bends = [] if unfold_all else list(self.picks["bends"])
        if not face:
            return "Pick the Stationary Entity: a flat top or bottom face of a wall."
        if not bends and not unfold_all:
            return "Pick the bends to unfold, or tick Unfold All Bends."
        if self.target is None:
            return "Pick the stationary face and the bends (or Unfold All Bends) first."
        # OK keeps what the dialog shows now (QA: a bend cleared or Unfold All Bends unticked
        # after the preview left the step with the old picks, and OK kept those)
        sheetmetal_flat.update_unfold(self.target, self.base, face, bends, unfold_all)
        self.doc.recompute()
        state = list(self.target.State)
        if "Invalid" not in state and "Error" not in state and self.target.BendCount == 0:
            # (QA: OK made an Unfold that changed nothing, and Refold then had nothing to do)
            return "There is no bend to unfold: the body is flat already."
        return None


# -- Refold --------------------------------------------------------------------------------------
class RefoldPanel(taskui.Panel):
    title = "Refold"
    icon = "sm_refold"
    last = None

    def __init__(self, doc, body=None, feature=None):
        super().__init__(doc, "Refold" if feature is None else "Edit Refold")
        RefoldPanel.last = self
        self.target = feature
        self.body = bodies.body_of(feature) if feature is not None else body
        label = QtWidgets.QLabel("")
        label.setWordWrap(True)
        self.layout.addRow(label)
        self.finish_layout()
        try:
            if feature is None:
                self.target = sheetmetal_flat.make_refold(self.body)
                doc.recompute()
            unfold = self.target.Unfold
            label.setText(
                "Folds the bends of %s back (%d bend(s)); cuts made while they were flat "
                "follow them." % (unfold.Label if unfold else "?", getattr(unfold, "BendCount", 0))
            )
            self.show_status()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def feature(self):
        return self.target

    def accept(self):
        if self.target is None:
            self.message.setText("⚠ There is nothing to refold.")
            return False
        return super().accept()


def open_body(doc):
    """The body with an open Unfold (the active one first)."""
    candidates = []
    try:
        found = commands.find_body()
        if found is not None:
            candidates.append(found)
    except Exception:
        pass
    candidates += sheetmetal.sheet_metal_bodies(doc)
    for body in candidates:
        if sheetmetal_flat.open_unfold(body) is not None:
            return body
    return None


def _start_unfold():
    try:
        if not commands.finish_open_dialog():
            return
        doc = App.ActiveDocument
        if doc is None:
            return
        if not sheetmetal.sheet_metal_bodies(doc):
            commands.tell(
                "Unfold works on sheet metal: make a Flange or use Convert to Sheet Metal first."
            )
            return
        body = open_body(doc)
        if body is not None:
            commands.tell("%s is already unfolded: Refold it first." % body.Label)
            return
        Gui.Control.showDialog(UnfoldPanel(doc))
        log("unfold started")
    except Exception as exc:
        warn("Unfold failed to start: %s" % exc)


def _start_refold():
    try:
        if not commands.finish_open_dialog():
            return
        doc = App.ActiveDocument
        if doc is None:
            return
        body = open_body(doc)
        if body is None:
            commands.tell("There is nothing to refold: Unfold some bends first.")
            return
        Gui.Control.showDialog(RefoldPanel(doc, body))
        log("refold started")
    except Exception as exc:
        warn("Refold failed to start: %s" % exc)


def edit_unfold(feature):
    try:
        Gui.Control.showDialog(UnfoldPanel(feature.Document, feature))
    except Exception as exc:
        warn("Edit Unfold: %s" % exc)


def edit_refold(feature):
    try:
        Gui.Control.showDialog(RefoldPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("Edit Refold: %s" % exc)


def edit_convert(feature):
    commands.tell(
        "Convert to Sheet Metal is one way (as in Fusion): change the rule in Sheet Metal "
        "Rules, or delete the step."
    )


class UnfoldCommand:
    def GetResources(self):
        return {
            "MenuText": "Unfold",
            "ToolTip": "Lay some or all bends of a sheet metal body flat, to cut across them",
            "Pixmap": ui_icon_path("sm_unfold"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start_unfold()


class RefoldCommand:
    def GetResources(self):
        return {
            "MenuText": "Refold",
            "ToolTip": "Fold the bends of the open Unfold back, with the cuts made meanwhile",
            "Pixmap": ui_icon_path("sm_refold"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start_refold()


COMMANDS = {"SciForge_Unfold": UnfoldCommand, "SciForge_Refold": RefoldCommand}
EDITORS = {
    "SciForge::Unfold": edit_unfold,
    "SciForge::Refold": edit_refold,
    "SciForge::ConvertToSheetMetal": edit_convert,
}
