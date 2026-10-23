# SPDX-License-Identifier: LGPL-2.1-or-later
"""Opacity Control in the browser's right-click menu: a submenu with Fusion's percentages
and Custom Opacity... (a slider with a value box; the part shows each value while the
slider moves, OK keeps it as one undo step, Cancel puts the old look back). opacity.py
does the work."""

import FreeCADGui as Gui

from . import commands, log, warn
from . import opacity
from . import opacity_core as core
from .compat import QtCore, QtWidgets

MENU_TEXT = "Opacity Control"
CUSTOM_TEXT = "Custom Opacity..."
_DIALOG = {"open": None}


def add_menu(menu, objects, handlers):
    """Add the Opacity Control submenu for `objects` to `menu`; each entry's work goes into
    `handlers` (action -> function), run by the browser after the menu closes."""
    objects = [o for o in objects if opacity.supports(o)]
    if not objects:
        return None
    sub = menu.addMenu(MENU_TEXT)
    sub.setObjectName("SciForgeOpacityMenu")
    current = core.common([opacity.get(o) for o in objects])
    for text, value, checked in core.menu_entries(current):
        action = sub.addAction(text)
        action.setCheckable(True)
        action.setChecked(checked)
        handlers[action] = lambda v=value, objs=list(objects): set_now(objs, v)
    sub.addSeparator()
    custom = sub.addAction(CUSTOM_TEXT)
    handlers[custom] = lambda objs=list(objects): open_custom(objs)
    return sub


def set_now(objects, value):
    if not commands.finish_open_dialog():  # an undo step of its own, never in a command's
        return
    try:
        changed = opacity.set_opacity(objects, value)
        if changed:
            commands.tell(
                "%s at %s opacity." % (", ".join(o.Label for o in changed), core.label(value))
            )
    except Exception as exc:
        warn("opacity: %s" % exc)
        commands.tell("The opacity could not be changed: %s" % exc)


def open_custom(objects):
    """Fusion's Custom Opacity: any value from 0 to 100 %."""
    if not commands.finish_open_dialog():
        return None
    old = _DIALOG.get("open")
    try:
        if old is not None and old.isVisible():
            old.reject()
    except RuntimeError:
        pass
    dialog = CustomOpacityDialog(objects)
    _DIALOG["open"] = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


def dialog():
    """The open Custom Opacity dialog, or None (tests)."""
    d = _DIALOG.get("open")
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


class CustomOpacityDialog(QtWidgets.QDialog):
    def __init__(self, objects):
        super().__init__(Gui.getMainWindow())
        self.setObjectName("SciForgeOpacityDialog")
        self.objects = list(objects)
        self.doc = self.objects[0].Document if self.objects else None
        names = ", ".join(o.Label for o in self.objects)
        self.setWindowTitle("Custom Opacity")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        layout = QtWidgets.QVBoxLayout(self)
        text = QtWidgets.QLabel("Opacity of %s" % names)
        text.setWordWrap(True)
        layout.addWidget(text)
        row = QtWidgets.QHBoxLayout()
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setObjectName("SciForgeOpacitySlider")
        self.slider.setRange(0, 100)
        self.slider.setMinimumWidth(220)
        self.value = QtWidgets.QSpinBox()
        self.value.setObjectName("SciForgeOpacityValue")
        self.value.setRange(0, 100)
        self.value.setSuffix(" %")
        start = core.common([opacity.get(o) for o in self.objects])
        start = core.DEFAULT if start is None else start
        self.slider.setValue(start)
        self.value.setValue(start)
        row.addWidget(self.slider, 1)
        row.addWidget(self.value)
        layout.addLayout(row)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setObjectName("SciForgeOpacityOk")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.slider.valueChanged.connect(self._slid)
        self.value.valueChanged.connect(self._typed)

    def _slid(self, value):
        if self.value.value() != value:
            self.value.blockSignals(True)
            self.value.setValue(value)
            self.value.blockSignals(False)
        self._preview(value)

    def _typed(self, value):
        if self.slider.value() != value:
            self.slider.blockSignals(True)
            self.slider.setValue(value)
            self.slider.blockSignals(False)
        self._preview(value)

    def _preview(self, value):
        try:
            opacity.preview(self.objects, value)
        except Exception as exc:
            warn("opacity preview: %s" % exc)

    def accept(self):
        value = self.value.value()
        super().accept()
        try:
            opacity.set_opacity(self.objects, value)
            log("custom opacity %s" % core.label(value))
        except Exception as exc:
            warn("opacity: %s" % exc)
            commands.tell("The opacity could not be changed: %s" % exc)

    def reject(self):
        super().reject()
        try:
            opacity.apply(self.doc)  # the design's own values back on screen
        except Exception as exc:
            warn("opacity: %s" % exc)
