"""Apply the Fusion-style shortcut map while the SciForge workbench is active."""

import json
import os

from . import config, log, warn

_saved = {}  # command name -> shortcut it had before we changed it
_parked = {}  # other commands whose shortcut clashed with ours -> their old shortcut


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
    _park_conflicts(Gui, current_map())
    log(
        "shortcuts applied: %d, skipped: %d, conflicts parked: %d"
        % (applied, len(skipped), len(_parked))
    )
    if skipped:
        warn("no shortcut set for: %s" % ", ".join(skipped))


def _park_conflicts(Gui, mapping):
    """Fusion's keys win: clear other commands bound to the same key while SciForge
    is active (e.g. the Sketcher binds L, S, E, P to constraints), and remember them."""
    ours = {key.replace(" ", "").upper(): name for name, key in mapping.items() if key}
    for name in Gui.listCommands():
        if name in mapping or name in _parked:
            continue
        try:
            cmd = Gui.Command.get(name)
            key = (cmd.getShortcut() or "").replace(" ", "").upper() if cmd else ""
            if key and key in ours:
                _parked[name] = cmd.getShortcut()
                cmd.setShortcut("")
        except Exception:
            pass


def restore():
    import FreeCADGui as Gui

    for name, previous in list(_parked.items()):
        try:
            cmd = Gui.Command.get(name)
            if cmd is not None:
                cmd.setShortcut(previous)
        except Exception:
            pass
    _parked.clear()

    for name, previous in list(_saved.items()):
        try:
            cmd = Gui.Command.get(name)
            if cmd is not None:
                cmd.setShortcut(previous)
        except Exception:
            pass
    _saved.clear()
