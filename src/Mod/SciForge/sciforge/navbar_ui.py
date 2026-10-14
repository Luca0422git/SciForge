# SPDX-License-Identifier: LGPL-2.1-or-later
"""The small navigation bar floating at the bottom centre of the 3D view: Orbit, Look At,
Pan, Zoom, Fit, Display Settings, Grid and Snaps, Viewports (ribbon_config.NAV_BAR; the
commands in orbit_ui, navigate_ui, display_ui, grid_ui, viewports_ui)."""

import FreeCADGui as Gui

from . import registry, ribbon_config as cfg, ui_icon, warn
from .compat import QtCore, QtWidgets
from .ribbon_ui import build_menu, resolve, run

_bar = None


class NavBar(QtWidgets.QWidget):
    def __init__(self, area):
        super().__init__(area)
        self.setObjectName("SciForgeNavBar")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        available = registry.available_commands()
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(2)
        for entry in cfg.NAV_BAR:
            button = QtWidgets.QToolButton()
            button.setIcon(ui_icon(entry.get("icon")))
            button.setIconSize(QtCore.QSize(20, 20))
            button.setAutoRaise(True)
            if "submenu" in entry:
                tip = entry["label"]
                if entry.get("note"):
                    tip += "\n" + entry["note"]
                button.setToolTip(tip)
                button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
                button.setMenu(build_menu(button, entry["submenu"], available))
            else:
                resolved = resolve(entry["command"], available)
                tip = entry["label"] + ("  (%s)" % entry["key"] if entry.get("key") else "")
                if entry.get("note"):
                    tip += "\n" + entry["note"]
                button.setToolTip(tip)
                if resolved:
                    button.clicked.connect(lambda _=False, r=resolved, e=entry: run(r, e["label"]))
                elif not entry.get("note"):
                    button.setEnabled(False)
            row.addWidget(button)
        self._area = area
        area.installEventFilter(self)
        self.adjustSize()
        self.place()

    def place(self):
        area = self._area
        self.adjustSize()
        x = (area.width() - self.width()) // 2
        y = area.height() - self.height() - 12
        self.move(max(0, x), max(0, y))
        self.raise_()

    def eventFilter(self, obj, event):
        if obj is self._area and event.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show):
            QtCore.QTimer.singleShot(0, self.place)
        return False


def bar():
    """The navigation bar widget (None before SciForge's interface was first shown)."""
    return _bar


def show():
    global _bar
    try:
        if _bar is None:
            area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
            if area is None:
                warn("navigation bar: no 3D view area found")
                return
            _bar = NavBar(area)
        _bar.show()
        _bar.place()
    except Exception as exc:
        warn("navigation bar: %s" % exc)
    # what the bar's menus set: display settings, the layout grid (remembered choices)
    for name in ("display_ui", "grid_ui"):
        try:
            __import__("sciforge." + name, fromlist=["enable"]).enable()
        except Exception as exc:
            warn("navigation bar: %s" % exc)


def hide():
    if _bar is not None:
        _bar.hide()
    for name in ("navigate_ui", "viewports_ui", "display_ui", "grid_ui"):
        try:
            module = __import__("sciforge." + name, fromlist=["disable"])
            if name == "navigate_ui":
                module.stop()
            elif name == "viewports_ui":
                module.set_layout("Single View", quiet=True)
            else:
                module.disable()
        except Exception as exc:
            warn("navigation bar: %s" % exc)
