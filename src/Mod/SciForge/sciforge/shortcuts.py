"""Apply the Fusion-style shortcut map while the SciForge workbench is active."""

import json
import os

from . import config, log, warn

_saved = {}  # command name -> shortcut it had before we changed it


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


def apply():
    import FreeCADGui as Gui

    applied, skipped = 0, []
    for name, key in current_map().items():
        try:
            cmd = Gui.Command.get(name)
            if cmd is None:
                skipped.append(name)
                continue
            if name not in _saved:
                _saved[name] = cmd.getShortcut() or ""
            cmd.setShortcut(key)
            applied += 1
        except Exception:
            skipped.append(name)
    log("shortcuts applied: %d, skipped: %d" % (applied, len(skipped)))
    if skipped:
        warn("no shortcut set for: %s" % ", ".join(skipped))


def restore():
    import FreeCADGui as Gui

    for name, previous in list(_saved.items()):
        try:
            cmd = Gui.Command.get(name)
            if cmd is not None:
                cmd.setShortcut(previous)
        except Exception:
            pass
    _saved.clear()
