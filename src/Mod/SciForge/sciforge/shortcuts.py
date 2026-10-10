"""Fusion-style single-key shortcuts while the SciForge interface is on.

FreeCAD only honours a command's shortcut when the command sits in a visible
menu or toolbar. SciForge's commands live in the ribbon and the menu bar is
hidden, so the keys are bound here with Qt shortcuts on the main window:

  * every FreeCAD command bound to one of these keys is "parked" (shortcut
    cleared) so no key is bound twice, which would make Qt ignore both;
  * the key runs the command through Gui.runCommand;
  * typing in a text field still types: Qt gives the field the key first.

restore() deletes the shortcuts and gives the parked keys back.
Per-machine overrides: <user data>/SciForge/shortcuts.json, {"Command_Name": "Key"}.
"""

import json
import os

from . import config, log, warn

_bound = {}  # normalised key -> (command name, QShortcut)
_parked = {}  # FreeCAD command -> the shortcut it had before


def _overrides():
    try:
        import FreeCAD

        path = os.path.join(FreeCAD.getUserAppDataDir(), "SciForge", "shortcuts.json")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
    except Exception as exc:
        warn("could not read shortcuts.json: %s" % exc)
    return {}


def current_map():
    merged = dict(config.SHORTCUTS)
    merged.update(_overrides())
    return merged


def normalise(key):
    return (key or "").replace(" ", "").upper()


def bound_keys():
    """{key: command name} currently active (for tests and diagnostics)."""
    return {key: name for key, (name, _) in _bound.items()}


def _run(name):
    import FreeCADGui as Gui

    try:
        cmd = Gui.Command.get(name)
        if cmd is not None and hasattr(cmd, "isActive") and not cmd.isActive():
            return
        from . import recent

        label = name
        try:
            label = (cmd.getInfo().get("menuText") or name).replace("&", "")
        except Exception:
            pass
        recent.record(name, label)
        Gui.runCommand(name)
    except Exception as exc:
        warn("shortcut for %s failed: %s" % (name, exc))


def apply():
    import FreeCADGui as Gui

    from .compat import QtCore, QtGui

    if _bound:
        return
    mapping = current_map()
    keys = {normalise(k) for k in mapping.values() if k}
    # Park every FreeCAD shortcut on one of our keys (including on our target commands
    # themselves, e.g. the Sketcher's own "D"), so each key has exactly one owner.
    for name in Gui.listCommands():
        try:
            cmd = Gui.Command.get(name)
            current = cmd.getShortcut() if cmd else ""
            if current and normalise(current) in keys:
                _parked[name] = current
                cmd.setShortcut("")
        except Exception:
            pass
    main = Gui.getMainWindow()
    available = set(Gui.listCommands())
    skipped = []
    for name, key in mapping.items():
        better = config.PREFERRED.get(name)
        if better in available:
            name = better
        if not key or name not in available:
            skipped.append(name)
            continue
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), main)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(lambda n=name: _run(n))
        _bound[normalise(key)] = (name, shortcut)
    log("shortcuts bound: %d, FreeCAD keys parked: %d" % (len(_bound), len(_parked)))
    if skipped:
        warn("no shortcut for (command not found): %s" % ", ".join(skipped))


def restore():
    import FreeCADGui as Gui

    for _, shortcut in _bound.values():
        try:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        except Exception:
            pass
    _bound.clear()
    for name, previous in list(_parked.items()):
        try:
            cmd = Gui.Command.get(name)
            if cmd is not None:
                cmd.setShortcut(previous)
        except Exception:
            pass
    _parked.clear()
