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
# QActions of FreeCAD's that hold one of SciForge's keys without being a command with a
# shortcut of its own (Freeze View's Shift+F is an entry of the Std_FreezeViews group): two
# owners of a key make Qt ignore both, so they are parked too: [(action, its key)].
_parked_actions = []

# A shortcut set from Python goes into FreeCAD's preferences, and FreeCAD saves those when
# it quits: after quitting with SciForge on, FreeCAD's own keys (L, C, D...) were saved
# empty and never came back. The parked keys are kept here too, until they are given back.
PARKED = "User parameter:BaseApp/Preferences/Mod/SciForge/ParkedShortcuts"
SHORTCUT_PREFS = "User parameter:BaseApp/Preferences/Shortcut"  # FreeCAD's own


def _kept():
    import FreeCAD

    return FreeCAD.ParamGet(PARKED)


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
    """Comparable form of a key: "Del" and "Delete", "ctrl+z" and "Ctrl+Z" are the same key."""
    text = (key or "").replace(" ", "")
    try:
        from .compat import QtGui

        portable = QtGui.QKeySequence(text).toString(QtGui.QKeySequence.PortableText)
        if isinstance(portable, str) and portable:
            text = portable
    except Exception:
        pass
    return text.upper()


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
    try:
        kept = _kept()
        stored = {name: kept.GetString(name) for name in kept.GetStrings()}
    except Exception as exc:  # the keys still work, only not kept across a quit
        warn("shortcuts: cannot keep FreeCAD's keys: %s" % exc)
        kept, stored = None, {}
    for name in Gui.listCommands():
        try:
            cmd = Gui.Command.get(name)
            current = cmd.getShortcut() if cmd else ""
            if name in stored:
                # parked in a session that ended with SciForge on: that key is the user's
                _parked[name] = stored[name]
                if current:
                    cmd.setShortcut("")
            elif current and normalise(current) in keys:
                _parked[name] = current
                if kept is not None:
                    kept.SetString(name, current)
                cmd.setShortcut("")
        except Exception:
            pass
    main = Gui.getMainWindow()
    _park_actions(main, keys)
    available = set(Gui.listCommands())
    skipped = []
    for name, key in mapping.items():
        better = config.PREFERRED.get(name)
        if better in available:
            name = better
        if not key:
            continue  # no key for this command (Change Keyboard Shortcut: blank, or taken)
        if name not in available:
            skipped.append(name)
            continue
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), main)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(lambda n=name: _run(n))
        _bound[normalise(key)] = (name, shortcut)
    log("shortcuts bound: %d, FreeCAD keys parked: %d" % (len(_bound), len(_parked)))
    if skipped:
        warn("no shortcut for (command not found): %s" % ", ".join(skipped))


def _park_actions(main, keys):
    """Take SciForge's keys off FreeCAD's other actions (given back by restore())."""
    try:
        from .compat import QtGui

        for action in main.findChildren(QtGui.QAction):
            try:
                seq = action.shortcut()
                if seq.isEmpty():
                    continue
                text = seq.toString(QtGui.QKeySequence.PortableText)
                if normalise(text) in keys:
                    _parked_actions.append((action, text))
                    action.setShortcut(QtGui.QKeySequence())
            except RuntimeError:
                continue
    except Exception as exc:
        warn("shortcuts: FreeCAD's other keys not parked: %s" % exc)


def _give_back_actions():
    from .compat import QtGui

    for action, text in _parked_actions:
        try:
            action.setShortcut(QtGui.QKeySequence(text))
        except RuntimeError:
            pass  # the action is gone
    del _parked_actions[:]


def restore():
    _give_back_actions()
    for _, shortcut in _bound.values():
        try:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        except Exception:
            pass
    _bound.clear()
    _give_back(dict(_parked))
    _parked.clear()


def _give_back(parked):
    """Give FreeCAD's own keys back: `parked` {command: key} plus any kept from a session
    that ended with SciForge on."""
    import FreeCAD
    import FreeCADGui as Gui

    try:
        kept = _kept()
        for name in kept.GetStrings():
            parked.setdefault(name, kept.GetString(name))
    except Exception as exc:
        warn("shortcuts: cannot read the kept keys: %s" % exc)
        kept = None
    for name, previous in parked.items():
        try:
            cmd = Gui.Command.get(name)
            if cmd is not None:
                cmd.setShortcut(previous)
            else:  # (its workbench is not loaded yet: FreeCAD reads it from here then)
                FreeCAD.ParamGet(SHORTCUT_PREFS).SetString(name, previous)
            if kept is not None:
                kept.RemString(name)
        except Exception as exc:
            warn("could not give back the key of %s: %s" % (name, exc))


def give_back_left_over():
    """SciForge is off: give back FreeCAD's keys a session that ended with SciForge on left
    parked (nothing to do when none are kept)."""
    if _bound:
        return
    try:
        _give_back({})
    except Exception as exc:
        warn("shortcuts: %s" % exc)
