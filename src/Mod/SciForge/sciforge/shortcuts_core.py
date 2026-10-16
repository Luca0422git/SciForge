# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keyboard shortcuts as data, without Qt or FreeCAD (unit tested): which command owns a
key, changing a command's key, overriding a key another command has, resetting.

Fusion (Autodesk blog "How to switch between sketching and modeling environments: keyboard
shortcuts"; Autodesk forum "Update: Customizable Keyboard Shortcuts"): a command's three-dot
menu has Change Keyboard Shortcut; the dialog takes one key (a letter, digit or function key)
with optional Shift / Ctrl / Alt; blank means no shortcut; Reset gives the default back; a
key another command uses names that command and can be overridden, the other command then
loses it. Fusion has no list of all shortcuts; SciForge's Preferences has one.

Data: `defaults` {command: key} (config.SHORTCUTS), `overrides` {command: key} (the user's
shortcuts.json; "" = no key), `preferred` {FreeCAD command: SciForge command}
(config.PREFERRED: a key of the FreeCAD command runs SciForge's version).
"""

ALIASES = {
    "DEL": "DELETE",
    "ESC": "ESCAPE",
    "RETURN": "ENTER",
    "PGUP": "PAGEUP",
    "PGDOWN": "PAGEDOWN",
    "CONTROL": "CTRL",
}
MODIFIERS = ("CTRL", "ALT", "SHIFT", "META")


def normalise(key):
    """Comparable form: "ctrl + z", "Ctrl+Z" and "Z+Ctrl" are one key; "" stays ""."""
    text = (key or "").replace(" ", "").upper()
    if not text:
        return ""
    parts = [ALIASES.get(p, p) for p in text.split("+") if p]
    mods = [m for m in MODIFIERS if m in parts]
    rest = [p for p in parts if p not in MODIFIERS]
    return "+".join(mods + rest)


def is_single_key(key):
    """Fusion's rule: exactly one non-modifier key (no chords like "Ctrl+K, Ctrl+C")."""
    text = normalise(key)
    if not text or "," in (key or ""):
        return False
    return len([p for p in text.split("+") if p not in MODIFIERS]) == 1


def canonical(name, defaults, preferred):
    """The name a command's key is kept under: SciForge's own version of a FreeCAD command
    keeps the FreeCAD command's entry (SciForge_Fillet -> PartDesign_Fillet), so changing it
    replaces the default instead of adding a second key."""
    if name in defaults:
        return name
    for freecad_name, sciforge_name in preferred.items():
        if sciforge_name == name and freecad_name in defaults:
            return freecad_name
    return name


def effective(defaults, overrides):
    """{command: key} in force (overrides win; "" means the command has no key)."""
    merged = dict(defaults)
    merged.update(overrides or {})
    return merged


def key_of(name, defaults, overrides, preferred):
    return effective(defaults, overrides).get(canonical(name, defaults, preferred), "")


def owners(key, defaults, overrides):
    """Commands that have `key` now (normally one)."""
    wanted = normalise(key)
    if not wanted:
        return []
    return sorted(
        name for name, k in effective(defaults, overrides).items() if k and normalise(k) == wanted
    )


def conflicts(name, key, defaults, overrides, preferred):
    """Other commands that have `key` (what the dialog names before an override)."""
    own = canonical(name, defaults, preferred)
    return [other for other in owners(key, defaults, overrides) if other != own]


def assign(name, key, defaults, overrides, preferred, override=False):
    """New overrides with `key` for the command. Raises ValueError for a key that is not one
    key, or for a key another command has (unless `override`: that command loses it)."""
    own = canonical(name, defaults, preferred)
    result = dict(overrides or {})
    if key and not is_single_key(key):
        raise ValueError("One key, with Shift, Ctrl or Alt if you like (not %r)" % key)
    taken = conflicts(name, key, defaults, overrides, preferred) if key else []
    if taken and not override:
        raise ValueError("%s is already the key of %s" % (key, ", ".join(taken)))
    for other in taken:
        result[other] = ""
    if (key or "") == defaults.get(own, ""):
        result.pop(own, None)  # the default again: nothing to keep
    else:
        result[own] = key or ""
    return result


def reset(name, defaults, overrides, preferred):
    """New overrides with the command's default key back; a command that had taken that key
    through an override loses it (one owner per key)."""
    own = canonical(name, defaults, preferred)
    result = dict(overrides or {})
    result.pop(own, None)
    default = defaults.get(own, "")
    for other in conflicts(name, default, defaults, result, preferred) if default else []:
        result[other] = ""
    return _tidy(result, defaults)


def reset_all():
    return {}


def _tidy(overrides, defaults):
    """Drop overrides that equal the default (nothing to keep)."""
    return {k: v for k, v in overrides.items() if defaults.get(k, "") != v}
