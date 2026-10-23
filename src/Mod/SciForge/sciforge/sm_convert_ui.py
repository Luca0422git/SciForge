# SPDX-License-Identifier: LGPL-2.1-or-later
"""MODIFY > Convert to Sheet Metal of the SHEET METAL tab (Fusion's behaviour; sm_convert.py
does the work).

Pick a wide flat face of a solid of even thickness: the thickness measured there is shown
(it cannot be typed, as in Fusion); the Rule is Template Rule (a new rule from that
thickness) or a rule of the design or the library, copied with the thickness set; "Show
rules with matching thickness only" filters the list. A solid that is not one sheet of even
thickness, or whose walls meet at sharp corners, is refused in the dialog with the reason.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, sm_convert, ui_icon_path, warn
from .compat import QtWidgets
from .unfold_panel import SheetPanel, planar_face


class ConvertPanel(SheetPanel):
    title = "Convert to Sheet Metal"
    icon = "sm_convert"
    SHEET_METAL = False
    SLOTS = (("face", "Face", planar_face, False),)

    def __init__(self, doc):
        self.info_data = None
        self.made = None
        super().__init__(doc, "Convert to Sheet Metal")

    def no_body_text(self):
        return "⚠ There is no solid body to convert: make a part first."

    def build_fields(self):
        self.add_slot_rows()
        self.thickness = QtWidgets.QLabel("-")
        self.thickness.setObjectName("SciForgeConvertThickness")
        self.layout.addRow("Thickness", self.thickness)
        self.rule = QtWidgets.QComboBox()
        self.rule.setObjectName("SciForgeConvertRule")
        self.layout.addRow("Rule", self.rule)
        self.matching = QtWidgets.QCheckBox("Show rules with matching thickness only")
        self.matching.setChecked(True)
        self.matching.toggled.connect(lambda _on: self._fill_rules())
        self.layout.addRow(self.matching)
        self._fill_rules()

    def _fill_rules(self):
        current = self.rule.currentData()
        self.rule.blockSignals(True)
        self.rule.clear()
        thickness = self.info_data["thickness"] if self.info_data else None
        if thickness is None:
            self.rule.addItem(sm_convert.TEMPLATE, sm_convert.TEMPLATE)
        else:
            for label, key in sm_convert.rules_for(self.doc, thickness, self.matching.isChecked()):
                self.rule.addItem(label, key)
        index = self.rule.findData(current) if current else -1
        self.rule.setCurrentIndex(max(0, index))
        self.rule.blockSignals(False)

    def update(self):
        try:
            self._update()
        except Exception as exc:
            self.say("⚠ %s" % exc)

    def _update(self):
        face = self.pick("face")
        self.info_data = None
        if not face:
            self.thickness.setText("-")
            self.say("Pick a wide flat face of the part.")
            self._fill_rules()
            return
        from . import sheetmetal

        if sheetmetal.is_sheet_metal_body(self.body):
            self.thickness.setText("-")
            self.say("⚠ %s is sheet metal already." % self.body.Label)
            self._fill_rules()
            return
        try:
            self.info_data = sm_convert.detect(self.base.Shape, face)
        except sm_convert.ConvertError as exc:
            self.thickness.setText("-")
            self.say("⚠ %s" % exc)
            self._fill_rules()
            return
        data = self.info_data
        self.thickness.setText("%.3f mm" % data["thickness"])
        self._fill_rules()
        self.say("%d bend(s) found." % data["bends"])

    def ready(self):
        face = self.pick("face")
        if not face:
            return "Pick a wide flat face first."
        if self.info_data is None:
            return "That face cannot be converted (see above)."
        try:
            self.made = sm_convert.make(
                self.body, self.base, face, self.rule.currentData() or sm_convert.TEMPLATE
            )
        except sm_convert.ConvertError as exc:
            return str(exc)
        return None

    def feature(self):
        return self.made


def _start():
    try:
        if not commands.finish_open_dialog():
            return
        doc = App.ActiveDocument
        if doc is None:
            return
        Gui.Control.showDialog(ConvertPanel(doc))
        log("convert to sheet metal started")
    except Exception as exc:
        warn("Convert to Sheet Metal failed to start: %s" % exc)


class ConvertCommand:
    def GetResources(self):
        return {
            "MenuText": "Convert to Sheet Metal",
            "ToolTip": "Make a solid of even thickness a sheet metal body",
            "Pixmap": ui_icon_path("sm_convert"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start()


COMMANDS = {"SciForge_ConvertToSheetMetal": ConvertCommand}
