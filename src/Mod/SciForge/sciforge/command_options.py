# SPDX-License-Identifier: LGPL-2.1-or-later
"""A command's options, like Fusion's three-dot menu next to a command in a toolbar panel's
drop-down: Pin to Toolbar / Unpin from Toolbar and Change Keyboard Shortcut (Luca,
2026-10-16: "There should be a way to change the keybinds of each tool within SciForge";
"there should be a way to pin tools to the toolbar").

The rules are data in shortcuts_core and ribbon_pins (unit tested); this module is the Qt
side: the options menu, the Change Keyboard Shortcut dialog, saving and re-binding.
"""

import json
import os

import FreeCADGui as Gui

from . import config, log, registry, ribbon_pins, shortcuts, shortcuts_core as core, warn
from .compat import QtCore, QtGui, QtWidgets


# -- the keys ---------------------------------------------------------------------------------
def overrides():
    return dict(shortcuts._overrides())


def save_overrides(data):
    """Write <user data>/SciForge/shortcuts.json and bind the keys again at once."""
    import FreeCAD as App

    folder = os.path.join(App.getUserAppDataDir(), "SciForge")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "shortcuts.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    rebind()


def rebind():
    """Take SciForge's keys off and put the current map on (FreeCAD's parked keys are given
    back and parked again by shortcuts.restore / apply)."""
    try:
        shortcuts.restore()
        shortcuts.apply()
    except Exception as exc:
        warn("shortcuts: %s" % exc)
    refresh_ribbon()


def refresh_ribbon():
    try:
        from . import shell

        ribbon = shell.ribbon()
        if ribbon is not None:
            ribbon.refresh_customization()
    except Exception as exc:
        warn("ribbon refresh: %s" % exc)


def _names(entry):
    """The command names an entry may run (none for a menu button or a missing command)."""
    command = entry.get("command")
    if not command or command == "__menu__":
        return ()
    return tuple(n.partition("#")[0] for n in registry.alternatives(command) if n)


def command_of(entry):
    """The FreeCAD command an entry runs here (SciForge's version first), or None."""
    available = set(Gui.listCommands())
    for name in _names(entry):
        if name in available:
            return name
    return None


def key_for(entry):
    """The key shown for a ribbon entry: the current map's (the user may have changed it),
    else the entry's own (keys a mode handles itself, e.g. a sketch's letters)."""
    mapping = shortcuts.current_map()
    for base in _names(entry):
        own = core.canonical(base, config.SHORTCUTS, config.PREFERRED)
        if own in mapping:
            return mapping.get(own) or ""
    return entry.get("key", "")


def label_of(name):
    """A command's menu text, for messages ("Fillet", not "PartDesign_Fillet")."""
    try:
        from . import ribbon_config as cfg

        wanted = core.canonical(name, config.SHORTCUTS, config.PREFERRED)
        for entry in cfg.all_items():
            for base in _names(entry):
                if core.canonical(base, config.SHORTCUTS, config.PREFERRED) == wanted:
                    return entry["label"]
        cmd = Gui.Command.get(name)
        if cmd is not None:
            return (cmd.getInfo().get("menuText") or name).replace("&", "")
    except Exception:
        pass
    return name


class KeyDialog(QtWidgets.QDialog):
    """Change Keyboard Shortcut: press the new key (with Shift / Ctrl / Alt if you like).
    A key another command has is named, and OK becomes Override (that command loses it).
    Reset = the default key, Clear = no key."""

    last = None

    def __init__(self, entry_label, command, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        KeyDialog.last = self
        self.setObjectName("SciForgeKeyDialog")
        self.setWindowTitle("Change Keyboard Shortcut")
        self.setMinimumWidth(460)  # the text wraps and Override fits (it was cut off)
        self.command = command
        self.entry_label = entry_label
        self.current = core.key_of(command, config.SHORTCUTS, overrides(), config.PREFERRED)
        layout = QtWidgets.QVBoxLayout(self)
        head = QtWidgets.QLabel(
            "Press the new key for <b>%s</b> (with Shift, Ctrl or Alt if you like)." % entry_label
        )
        head.setWordWrap(True)
        layout.addWidget(head)
        self.now = QtWidgets.QLabel("Current: %s" % (self.current or "none"))
        layout.addWidget(self.now)
        self.edit = QtWidgets.QKeySequenceEdit()
        self.edit.setObjectName("SciForgeKeyEdit")
        if hasattr(self.edit, "setMaximumSequenceLength"):
            self.edit.setMaximumSequenceLength(1)
        if hasattr(self.edit, "setClearButtonEnabled"):
            self.edit.setClearButtonEnabled(True)
        if self.current:
            self.edit.setKeySequence(QtGui.QKeySequence(self.current))
        self.edit.keySequenceChanged.connect(self._changed)
        layout.addWidget(self.edit)
        self.message = QtWidgets.QLabel("")
        self.message.setObjectName("SciForgeKeyMessage")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ffcc66;")
        layout.addWidget(self.message)
        row = QtWidgets.QHBoxLayout()
        self.reset_button = QtWidgets.QPushButton("Reset")
        self.reset_button.setToolTip("Give the command its default key back")
        self.reset_button.clicked.connect(self._reset)
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.setToolTip("No key for this command")
        self.clear_button.clicked.connect(lambda: self.edit.setKeySequence(QtGui.QKeySequence()))
        self.ok_button = QtWidgets.QPushButton("Override")  # its widest text sets its width
        self.ok_button.setMinimumWidth(self.ok_button.sizeHint().width() + 12)
        self.ok_button.setText("OK")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self._ok)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        # the keys are bound to the main window: it must be the active one again after this
        # dialog (without a window manager nothing gives it back)
        self.finished.connect(lambda _r: _activate_main())
        row.addWidget(self.reset_button)
        row.addWidget(self.clear_button)
        row.addStretch(1)
        row.addWidget(self.ok_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self._changed()

    def key(self):
        seq = self.edit.keySequence()
        return seq.toString(QtGui.QKeySequence.PortableText) if not seq.isEmpty() else ""

    def _changed(self, *_args):
        try:
            key = self.key()
            taken = core.conflicts(
                self.command, key, config.SHORTCUTS, overrides(), config.PREFERRED
            )
            if key and not core.is_single_key(key):
                self.message.setText("One key please, with Shift, Ctrl or Alt if you like.")
                self.ok_button.setText("OK")
                self.ok_button.setEnabled(False)
                return
            self.ok_button.setEnabled(True)
            if taken:
                names = ", ".join(label_of(t) for t in taken)
                self.message.setText(
                    "%s is the key of %s. Override gives it to %s and takes it away from %s."
                    % (key, names, self.entry_label, names)
                )
                self.ok_button.setText("Override")
            else:
                self.message.setText("" if key else "No key: the command runs from the menus.")
                self.ok_button.setText("OK")
        except Exception as exc:
            warn("shortcut dialog: %s" % exc)

    def _reset(self):
        try:
            data = core.reset(self.command, config.SHORTCUTS, overrides(), config.PREFERRED)
            save_overrides(data)
            log("shortcut of %s reset" % self.command)
            self.accept()
        except Exception as exc:
            warn("shortcut reset: %s" % exc)

    def _ok(self):
        try:
            key = self.key()
            data = core.assign(
                self.command,
                key,
                config.SHORTCUTS,
                overrides(),
                config.PREFERRED,
                override=True,  # the dialog already said who loses the key
            )
            save_overrides(data)
            log("shortcut of %s: %s" % (self.command, key or "none"))
            self.accept()
        except ValueError as exc:
            self.message.setText(str(exc))
        except Exception as exc:
            warn("shortcut change: %s" % exc)


def _activate_main():
    try:
        main = Gui.getMainWindow()
        main.activateWindow()
        main.raise_()
    except Exception:
        pass


def change_shortcut(entry_label, command):
    """Open the dialog (not blocking: a person can still look at the menus)."""
    try:
        dialog = KeyDialog(entry_label, command)
        dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        dialog.open()
        return dialog
    except Exception as exc:
        warn("Change Keyboard Shortcut: %s" % exc)
        return None


# -- the options menu -----------------------------------------------------------------------------
def options_menu(parent, entry, context=None):
    """Fusion's three-dot menu of a command: Pin to Toolbar or Unpin from Toolbar (when the
    command is in a ribbon group: context = (tab id, group id, labels of its own big icons)),
    and Change Keyboard Shortcut."""
    menu = QtWidgets.QMenu(parent)
    menu.setObjectName("SciForgeCommandOptions")
    label = entry.get("label", "")
    if context is not None:
        tab_id, group_id, built_in = context
        store = ribbon_pins.load()
        if label in built_in:
            pin = menu.addAction("Pin to Toolbar")
            pin.setEnabled(False)
            pin.setToolTip("Already on the toolbar")
        elif ribbon_pins.is_pinned(store, tab_id, group_id, label):
            menu.addAction("Unpin from Toolbar").triggered.connect(
                lambda: set_pinned(tab_id, group_id, label, False)
            )
        else:
            menu.addAction("Pin to Toolbar").triggered.connect(
                lambda: set_pinned(tab_id, group_id, label, True, built_in)
            )
    command = command_of(entry)
    change = menu.addAction("Change Keyboard Shortcut...")
    if command is None:
        change.setEnabled(False)
    else:
        change.triggered.connect(lambda: change_shortcut(label, command))
    return menu


def set_pinned(tab_id, group_id, label, on, built_in=()):
    try:
        store = ribbon_pins.load()
        if on:
            store = ribbon_pins.pin(store, tab_id, group_id, label, built_in)
        else:
            store = ribbon_pins.unpin(store, tab_id, group_id, label)
        ribbon_pins.save(store)
        log("%s %s %s/%s" % ("pinned" if on else "unpinned", label, tab_id, group_id))
    except Exception as exc:
        warn("pin to toolbar: %s" % exc)
    refresh_ribbon()


def reset_all_toolbar(parent=None):
    """Right-click on the ribbon: Reset All Toolbar Customization, after asking (Fusion does
    not ask; its users asked it to)."""
    try:
        answer = QtWidgets.QMessageBox.question(
            parent or Gui.getMainWindow(),
            "Reset All Toolbar Customization",
            "Take every pinned command off the toolbar?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return False
        ribbon_pins.save({})
        log("toolbar customization reset")
        refresh_ribbon()
        return True
    except Exception as exc:
        warn("reset toolbar: %s" % exc)
        return False


def reset_for_tests():
    """No changed keys and no pins (a CI shard shares one profile across its scenarios)."""
    import FreeCAD as App

    changed = False
    path = os.path.join(App.getUserAppDataDir(), "SciForge", "shortcuts.json")
    if os.path.isfile(path):
        os.remove(path)
        changed = True
    if ribbon_pins.load():
        ribbon_pins.save({})
        changed = True
    if changed:
        rebind()
