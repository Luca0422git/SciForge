# SPDX-License-Identifier: LGPL-2.1-or-later
"""Opacity Control (Fusion's browser right-click > Opacity Control): the numbers. Pure
Python, unit tested (test_opacity_core.py). The FreeCAD side is opacity.py, the menu and
the Custom Opacity dialog opacity_ui.py.

Fusion (Autodesk support "How to adjust the opacity of a body in Fusion"): right-click a
body (or a component) in the browser > Opacity Control > a percentage from the list, or
Custom Opacity to type one. Its API says 1.0 is completely opaque and 0.0 completely
transparent. With a component's opacity set, it rules over the bodies in it ("opacity
controls for inactive components override opacity controls for bodies").

SciForge's rule (written down in docs/sciforge/parity/bodies.md): a body shows its own
opacity times the opacity of every component it is in, so a component at 40 % makes all
its bodies 40 % (a body of its own at 100 % included), and a 50 % body in a 40 % component
shows at 20 %. A see-through appearance (glass) is see-through on top of that.
"""

# The list in the menu (Fusion's steps of 20; "Custom Opacity..." for any other value).
PRESETS = (100, 80, 60, 40, 20)
DEFAULT = 100  # a body nobody set: fully opaque


def clamp(value):
    """A percentage 0..100 (junk gives the default)."""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULT
    return max(0, min(100, number))


def effective(own, ancestors=()):
    """The opacity a body shows (0..100): its own times its components' (nearest first)."""
    value = clamp(own) / 100.0
    for component in ancestors:
        value *= clamp(component) / 100.0
    return clamp(value * 100.0)


def transparency(opacity, base=0):
    """FreeCAD's Transparency (0 = solid .. 100 = clear) for an opacity, over a look that is
    `base` % see-through already (an appearance like glass)."""
    base = clamp(base)
    seen = (100 - base) / 100.0 * clamp(opacity) / 100.0
    return clamp(100 - seen * 100.0)


def label(value):
    return "%d%%" % clamp(value)


def menu_entries(current):
    """[(text, value, checked)] of the submenu: the presets, the current one ticked. A value
    off the list (set with Custom Opacity) is shown ticked at its place in the list."""
    current = None if current is None else clamp(current)
    values = list(PRESETS)
    if current is not None and current not in values:
        values.append(current)
        values.sort(reverse=True)
    return [(label(v), v, v == current) for v in values]


def common(values):
    """The value shared by all the rows a menu acts on, or None when they differ."""
    found = {clamp(v) for v in values}
    return found.pop() if len(found) == 1 else None
