# SPDX-License-Identifier: LGPL-2.1-or-later
"""Capture Image (File > Capture Image), Fusion-style: the Image Options window (the image's
size: the view's own or a chosen one, Lock aspect ratio; a transparent background), then
where to save it (PNG, JPEG, TIFF, BMP). It replaces FreeCAD's own screenshot dialog in the
File menu. Sources: docs/sciforge/parity/misc.md.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, ui_icon, ui_icon_path, warn
from .compat import QtCore, QtWidgets

PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge"
# Tests put a function(title, start, filter) -> path here instead of the save dialog.
SAVE_DIALOG = None
PRESETS = [
    ("view", "Current view size"),
    ((1280, 720), "1280 x 720 (HD)"),
    ((1920, 1080), "1920 x 1080 (Full HD)"),
    ((3840, 2160), "3840 x 2160 (4K)"),
    ("custom", "Custom"),
]
_state = {"dialog": None}


def view_size():
    try:
        view = Gui.ActiveDocument.ActiveView
        size = view.getSize()
        return int(size[0]), int(size[1])
    except Exception:
        return 1600, 1200


class ImageOptions(QtWidgets.QDialog):
    last = None

    def __init__(self, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        ImageOptions.last = self
        self.setObjectName("SciForgeImageOptions")
        self.setWindowTitle("Image Options")
        self.setWindowIcon(ui_icon("canvas"))
        form = QtWidgets.QFormLayout(self)
        self.preset = QtWidgets.QComboBox()
        self.preset.setObjectName("SciForgeImagePreset")
        for value, label in PRESETS:
            if value == "view":
                label = "%s (%d x %d)" % ((label,) + view_size())
            self.preset.addItem(label, value)
        self.preset.currentIndexChanged.connect(lambda *_: _safely(self._preset_changed))
        form.addRow("Image Resolution", self.preset)
        self.width = QtWidgets.QSpinBox()
        self.width.setObjectName("SciForgeImageWidth")
        self.height = QtWidgets.QSpinBox()
        self.height.setObjectName("SciForgeImageHeight")
        for box in (self.width, self.height):
            box.setRange(16, 8192)
            box.setSuffix(" px")
            box.setKeyboardTracking(False)
        w, h = view_size()
        self.width.setValue(w)
        self.height.setValue(h)
        self.width.valueChanged.connect(lambda v: _safely(self._locked, "w", v))
        self.height.valueChanged.connect(lambda v: _safely(self._locked, "h", v))
        form.addRow("Width", self.width)
        form.addRow("Height", self.height)
        self.lock = QtWidgets.QCheckBox("Lock aspect ratio")
        self.lock.setObjectName("SciForgeImageLock")
        self.lock.setChecked(True)
        form.addRow("", self.lock)
        self.transparent = QtWidgets.QCheckBox("Transparent background")
        self.transparent.setObjectName("SciForgeImageTransparent")
        form.addRow("", self.transparent)
        self.antialias = QtWidgets.QCheckBox("Anti-alias")
        self.antialias.setChecked(True)
        self.antialias.setEnabled(False)
        self.antialias.setToolTip(
            "Images use the 3D view's anti-aliasing (Preferences > Graphics). (Not available "
            "in SciForge yet as a separate choice.)"
        )
        form.addRow("", self.antialias)
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ff8a80;")
        form.addRow(self.message)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._ratio = w / float(max(1, h))
        self._quiet = False
        self.saved = None
        self._preset_changed()

    def _preset_changed(self):
        value = self.preset.currentData()
        custom = value == "custom"
        for box in (self.width, self.height):
            box.setEnabled(custom)
        self.lock.setEnabled(custom)
        if value == "view":
            w, h = view_size()
        elif isinstance(value, tuple):
            w, h = value
        else:
            return
        self._quiet = True
        try:
            self.width.setValue(w)
            self.height.setValue(h)
        finally:
            self._quiet = False
        self._ratio = w / float(max(1, h))

    def _locked(self, which, value):
        if self._quiet:
            return
        if not self.lock.isChecked():
            self._ratio = self.width.value() / float(max(1, self.height.value()))
            return
        self._quiet = True
        try:
            if which == "w":
                self.height.setValue(max(16, int(round(value / self._ratio))))
            else:
                self.width.setValue(max(16, int(round(value * self._ratio))))
        finally:
            self._quiet = False

    def accept(self):
        doc = App.ActiveDocument
        if doc is None or Gui.ActiveDocument is None:
            self.message.setText("⚠ Open a design first.")
            return
        start = App.ParamGet(PREFS).GetString("LastImageFolder", "") or (
            os.path.dirname(doc.FileName) if doc.FileName else os.path.expanduser("~")
        )
        start = os.path.join(start, (doc.Label or "Design") + ".png")
        filters = "PNG (*.png);;JPEG (*.jpg *.jpeg);;TIFF (*.tif *.tiff);;BMP (*.bmp)"
        if SAVE_DIALOG is not None:
            path = SAVE_DIALOG("Capture Image", start, filters)
        else:
            path, _f = QtWidgets.QFileDialog.getSaveFileName(self, "Capture Image", start, filters)
        if not path:
            return  # back to the options, like Fusion's Cancel in the save dialog
        if not os.path.splitext(path)[1]:
            path += ".png"
        try:
            save(path, self.width.value(), self.height.value(), self.transparent.isChecked())
        except Exception as exc:
            self.message.setText("⚠ The image could not be saved: %s" % exc)
            return
        App.ParamGet(PREFS).SetString("LastImageFolder", os.path.dirname(path))
        self.saved = path
        commands.tell(
            "Saved %s (%d x %d)."
            % (os.path.basename(path), self.width.value(), self.height.value())
        )
        super().accept()


def _safely(fn, *args):
    try:
        fn(*args)
    except Exception as exc:
        warn("Capture Image: %s" % exc)


def save(path, width, height, transparent=False):
    """The 3D view as an image file of width x height pixels."""
    view = Gui.ActiveDocument.ActiveView
    background = "Transparent" if transparent else "Current"
    if os.path.isfile(path):
        os.remove(path)  # the save dialog asked about replacing it: a failure must show
    view.saveImage(path, int(width), int(height), background)
    if not os.path.isfile(path):
        raise IOError("nothing was written")
    log(
        "image %s saved (%d x %d%s)" % (path, width, height, ", transparent" if transparent else "")
    )
    return path


def show():
    if App.ActiveDocument is None or Gui.ActiveDocument is None:
        commands.tell("Open a design first: Capture Image saves a picture of the 3D view.")
        return None
    dialog = ImageOptions()
    _state["dialog"] = dialog

    def closed(*_):
        from . import preferences_ui

        QtCore.QTimer.singleShot(0, preferences_ui.refocus_main)

    dialog.finished.connect(closed)
    dialog.setModal(False)
    dialog.show()
    return dialog


class CaptureImageCommand:
    def GetResources(self):
        return {
            "MenuText": "Capture Image",
            "ToolTip": "Save a picture of the 3D view (size, transparent background)",
            "Pixmap": ui_icon_path("canvas"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            show()
        except Exception as exc:
            warn("Capture Image: %s" % exc)


COMMANDS = {"SciForge_CaptureImage": CaptureImageCommand}
