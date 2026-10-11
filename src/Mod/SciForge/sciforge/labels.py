# SPDX-License-Identifier: LGPL-2.1-or-later
"""Giving a new object the name the browser shows (its Label) exactly, Fusion-style
(Plane1, Section2, Center of Mass1 ...). No FreeCAD import: works on any object.

Why this is needed: FreeCAD keeps a count of the labels in use so that no two objects share
one. A Python view provider's attach() "touches" the Label, which counts the label a second
time; when the object is deleted, or its preview is cancelled, one count stays behind and
FreeCAD refuses that label for the next object (a cancelled Section1 made the next one
"Section" or "Section3"). Each SciForge module works out a free label itself (next_label),
so:
  - SciForge's own Python objects say yes to a duplicate while SciForge sets the label
    (their proxy's allowDuplicateLabel returns allow_duplicate());
  - for FreeCAD's own objects (datum planes, axes, points) set_free tries the next number
    when FreeCAD refuses one.
"""
_SETTING = {"on": False}


def allow_duplicate():
    """True only while set_exact is setting a label (for allowDuplicateLabel)."""
    return _SETTING["on"]


def set_exact(obj, label):
    """Set `label` on a SciForge Python object whose proxy uses allow_duplicate()."""
    _SETTING["on"] = True
    try:
        obj.Label = label
    finally:
        _SETTING["on"] = False
    return obj.Label == label


def set_free(obj, base, first, tries=50):
    """Label `obj` base + number, from `first` up, with the first number FreeCAD accepts."""
    for number in range(int(first), int(first) + tries):
        wanted = "%s%d" % (base, number)
        obj.Label = wanted
        if obj.Label == wanted:
            return wanted
    return obj.Label
