"""Command search popup (press S). Type a few letters, Enter to run."""

import FreeCADGui as Gui

from . import search_core
from .compat import QtCore, QtWidgets


def _build_entries():
    entries = []
    for name in Gui.listCommands():
        text, shortcut = name, ""
        try:
            info = Gui.Command.get(name).getInfo()
            text = (info.get("menuText") or name).replace("&", "")
            shortcut = info.get("shortcut") or ""
        except Exception:
            pass
        entries.append({"name": name, "text": text, "shortcut": shortcut})
    return entries


class CommandSearchDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.Popup)
        self.setMinimumWidth(520)
        self._entries = _build_entries()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._edit = QtWidgets.QLineEdit()
        self._edit.setPlaceholderText("Search commands...")
        self._list = QtWidgets.QListWidget()
        self._list.setMinimumHeight(300)
        layout.addWidget(self._edit)
        layout.addWidget(self._list)

        self._edit.textChanged.connect(self._refresh)
        self._edit.installEventFilter(self)
        self._list.itemActivated.connect(self._run_item)
        self._list.itemClicked.connect(self._run_item)
        self._refresh("")

    def _refresh(self, query):
        self._list.clear()
        for entry in search_core.rank(query, self._entries):
            label = entry["text"]
            if entry["shortcut"]:
                label += "    [%s]" % entry["shortcut"]
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, entry["name"])
            item.setToolTip(entry["name"])
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)

    def eventFilter(self, obj, event):
        if obj is self._edit and event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            row = self._list.currentRow()
            if key == QtCore.Qt.Key_Down:
                self._list.setCurrentRow(min(row + 1, self._list.count() - 1))
                return True
            if key == QtCore.Qt.Key_Up:
                self._list.setCurrentRow(max(row - 1, 0))
                return True
            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                item = self._list.currentItem()
                if item is not None:
                    self._run_item(item)
                return True
        return super().eventFilter(obj, event)

    def _run_item(self, item):
        name = item.data(QtCore.Qt.UserRole)
        self.close()
        # Run after the popup has closed so commands that open dialogs work.
        QtCore.QTimer.singleShot(0, lambda: Gui.runCommand(name))


def show():
    main = Gui.getMainWindow()
    dialog = CommandSearchDialog(main)
    geo = main.geometry()
    dialog.move(geo.center().x() - 260, geo.top() + 120)
    dialog.show()
    dialog._edit.setFocus()
