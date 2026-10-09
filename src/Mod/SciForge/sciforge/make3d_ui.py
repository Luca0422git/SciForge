# SPDX-License-Identifier: LGPL-2.1-or-later
"""3D Print dialog: pick a body, format and quality, save, optionally open the folder."""
import os

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, make3d, ui_icon, ui_icon_path, warn
from .compat import QtCore, QtGui, QtWidgets


class PrintDialog(QtWidgets.QDialog):
    last = None

    def __init__(self, doc, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        PrintDialog.last = self
        self.doc = doc
        self.setWindowTitle("3D Print")
        self.setWindowIcon(ui_icon("insert_mesh"))
        form = QtWidgets.QFormLayout(self)
        self.body = QtWidgets.QComboBox()
        bodies = [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]
        active = commands.active_body()
        for body in bodies:
            self.body.addItem(body.Label, body.Name)
        if active is not None:
            self.body.setCurrentIndex(max(0, self.body.findData(active.Name)))
        form.addRow("Body", self.body)
        self.format = QtWidgets.QComboBox()
        self.format.addItems(["3MF", "STL"])
        form.addRow("Format", self.format)
        self.quality = QtWidgets.QComboBox()
        self.quality.addItems(list(make3d.QUALITY))
        self.quality.setCurrentText("Medium")
        form.addRow("Refinement", self.quality)
        self.open_folder = QtWidgets.QCheckBox("Open the folder after saving")
        self.open_folder.setChecked(True)
        form.addRow(self.open_folder)
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        form.addRow(self.message)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        if not bodies:
            self.message.setText("There is no body to print yet.")

    def default_path(self):
        folder = (
            os.path.dirname(self.doc.FileName) if self.doc.FileName else os.path.expanduser("~")
        )
        return os.path.join(
            folder, "%s.%s" % (self.body.currentText() or "part", self.format.currentText().lower())
        )

    def save(self, path=None):
        body = self.doc.getObject(self.body.currentData() or "")
        if body is None:
            self.message.setText("Pick a body.")
            return False
        if path is None:
            ext = self.format.currentText().lower()
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save for 3D printing", self.default_path(), "%s (*.%s)" % (ext.upper(), ext)
            )
            if not path:
                return False
        try:
            mesh = make3d.export(body.Shape, path, self.quality.currentText())
        except make3d.ExportError as exc:
            self.message.setText("⚠ %s" % exc)
            return False
        log("3D print: %s (%d triangles)" % (path, mesh.CountFacets))
        if self.open_folder.isChecked():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.dirname(path)))
        self.accept()
        return True


class PrintCommand:
    def GetResources(self):
        return {
            "MenuText": "3D Print",
            "ToolTip": "Save a body as 3MF or STL for your slicer",
            "Pixmap": ui_icon_path("insert_mesh"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            PrintDialog(App.ActiveDocument).show()
        except Exception as exc:
            warn("3D Print failed to open: %s" % exc)
