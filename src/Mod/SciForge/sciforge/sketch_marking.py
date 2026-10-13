# SPDX-License-Identifier: LGPL-2.1-or-later
"""The right-click marking menu while a sketch is open.

Outside sketches the marking menu (marking_menu.py) offers part commands (Press Pull,
Hole, Create Sketch, part Move/Copy). In a sketch Fusion's menu is about the sketch:
drawing tools, Sketch Dimension, Trim, the sketch's own Move/Copy and Finish Sketch.
The ring and the list underneath are the same widget as the part menu, filled with
these entries (data below, like ribbon_config.MARKING_MENU).

While a tool runs (a line being drawn, a rectangle half placed) or a dialog is open, the
ring offers OK at 3 o'clock and Cancel at 9 o'clock, as Fusion's does (Luca, 2026-10-13:
"there's no way to end a line"; Autodesk's marking menu help puts OK on the drag-right
gesture, a forum answer Cancel at 9 o'clock). OK ends the tool and keeps what was drawn
(Fusion's green check); Cancel is Esc. For a dialog they press its OK / Cancel.
"""

import math

import FreeCADGui as Gui

from . import registry, ribbon_config as cfg, warn
from .compat import QtCore, QtWidgets

item = cfg.item

# Eight slots, clockwise from the top (as the part menu).
RING = [
    item("Repeat", "__repeat__", "compute"),
    item("Delete", "Std_Delete", "delete", "Del"),
    item("Line", "SciForge_SketchLine", "sk_line", "L"),
    item("Undo", "Std_Undo", "qa_undo", "Ctrl+Z"),
    item("Finish Sketch", "SciForge_FinishSketch", "finish_sketch"),
    item("Center Diameter Circle", "Sketcher_CreateCircle", "sk_circle", "C"),
    item("Sketch Dimension", "Sketcher_Dimension", "sk_dimension", "D"),
    item("2-Point Rectangle", "Sketcher_CreateRectangle", "sk_rectangle", "R"),
]

LIST = [
    item("Redo", "Std_Redo", "qa_redo", "Ctrl+Y"),
    item("Trim", "Sketcher_Trimming", "sk_trim", "T"),
    item("Offset", "SciForge_SketchOffset", "sk_offset", "O"),
    item("Project", "SciForge_SketchProject", "sk_project", "P"),
    item("Move/Copy", "SciForge_SketchMove", "sk_move", "M"),
    item("Normal/Construction", "Sketcher_ToggleConstruction", "sk_line", "X"),
    cfg.SEP,
    item("Fit", "Std_ViewFitAll", "nav_fit", "F6"),
    item("Look At", "Sketcher_ViewSketch", "nav_lookat"),
]


OK = item("OK", "__ok__", "finish_sketch")
CANCEL = item("Cancel", "__cancel__", "cancel", "Esc")


def _session():
    try:
        from . import sketch_mode

        return sketch_mode.current()
    except Exception:
        return None


def _tool_running():
    session = _session()
    try:
        return session is not None and session.tool_running()
    except Exception:
        return False


def _menu_class():
    from .marking_menu import MarkingMenu

    class SketchMarkingMenu(MarkingMenu):
        """MarkingMenu with the sketch entries (same look, same keys and clicks)."""

        def __init__(self, center, parent=None):
            # Build like MarkingMenu.__init__, from the sketch lists.
            QtWidgets.QWidget.__init__(
                self, parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint
            )
            from .marking_menu import CANCEL_SLOT, OK_SLOT, RADIUS, STYLE, _last_menu
            from .ribbon_ui import build_menu

            self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
            self.setObjectName("SciForgeMarkingMenu")
            self.setProperty("sketch", True)
            self.setStyleSheet(STYLE)
            self.ensurePolished()
            available = registry.available_commands()
            size = 2 * RADIUS + 200
            self.resize(size, size + 220)
            self.move(center.x() - size // 2, center.y() - size // 2)
            mid = QtCore.QPoint(size // 2, size // 2)
            self.slots = []
            ring = list(RING)
            if self.in_command():
                ring[OK_SLOT] = OK
                ring[CANCEL_SLOT] = CANCEL
            for i, entry in enumerate(ring):
                angle = math.radians(90 - 45 * i)
                pos = mid + QtCore.QPoint(
                    int(RADIUS * math.cos(angle)), int(-RADIUS * math.sin(angle))
                )
                self.slots.append(self._slot(entry, pos, available))
            listing = build_menu(self, LIST, available)
            self.list = QtWidgets.QListWidget(self)
            self.list.setObjectName("SciForgeMarkingList")
            self.list.setFixedWidth(200)
            for action in listing.actions():
                if action.isSeparator():
                    continue
                row = QtWidgets.QListWidgetItem(action.icon(), action.text().replace("\t", "    "))
                row.setData(QtCore.Qt.UserRole, action)
                if not action.isEnabled():
                    row.setFlags(QtCore.Qt.NoItemFlags)
                self.list.addItem(row)
            self.list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            row_height = max(self.list.sizeHintForRow(0), 24) if self.list.count() else 24
            self.list.setFixedHeight(self.list.count() * row_height + 8)
            self.list.move(mid.x() - 100, mid.y() + RADIUS + 34)
            self.list.itemClicked.connect(self._list_clicked)
            self._listing = listing
            self._shape(mid)
            _last_menu["widget"] = self

        def in_command(self):
            """A dialog is open or a drawing tool runs: OK and Cancel on the ring."""
            return MarkingMenu.in_command(self) or _tool_running()

        def can_press(self, role):
            return MarkingMenu.can_press(self, role) or _tool_running()

        def _press(self, role):
            """OK / Cancel: the dialog's button when a dialog is open; else the tool ends
            (OK keeps what was drawn, Cancel is Esc)."""
            self.close()

            def go():
                try:
                    from . import taskui

                    # Only one of SciForge's own dialogs (never the Sketcher's task panel,
                    # whose Close button would leave the sketch).
                    if taskui.current() is not None and taskui.dialog_button(role) is not None:
                        taskui.press_dialog_button(role)
                        return
                    session = _session()
                    if session is None:
                        return
                    if role == "accept":
                        session.finish_tool()
                    else:
                        session.escape()
                except Exception as exc:
                    warn("sketch marking menu: %s" % exc)

            QtCore.QTimer.singleShot(0, go)

    return SketchMarkingMenu


def open_at(global_pos):
    """Show the sketch marking menu around global_pos; returns it (or None)."""
    try:
        main = Gui.getMainWindow()
        menu = _menu_class()(global_pos, main)
        _keep_inside(menu, main)
        menu.show()
        menu.raise_()
        return menu
    except Exception as exc:
        warn("sketch marking menu: %s" % exc)
    try:  # the part menu rather than nothing
        from . import marking_menu

        return marking_menu.open_at(global_pos)
    except Exception:
        return None


def _keep_inside(menu, main):
    """A right click near the window's edge: move the menu so all of it shows."""
    try:
        area = main.frameGeometry()
        rect = menu.frameGeometry()
        dx = max(0, area.left() - rect.left()) - max(0, rect.right() - area.right())
        dy = max(0, area.top() - rect.top()) - max(0, rect.bottom() - area.bottom())
        if dx or dy:
            menu.move(rect.left() + dx, rect.top() + dy)
    except Exception as exc:
        warn("sketch marking menu: %s" % exc)
