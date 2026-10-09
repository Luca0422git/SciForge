# SPDX-License-Identifier: LGPL-2.1-or-later
"""Remembers the last command run through SciForge (ribbon, keys, marking menu),
for Fusion's "Repeat <command>"."""

_last = {"name": None, "index": None, "label": None}

# Commands that make no sense to repeat.
NOT_REPEATABLE = {
    "Std_Undo",
    "Std_Redo",
    "Std_Delete",
    "SciForge_CommandSearch",
    "__menu__",
    "Std_ViewFitAll",
    "Std_Save",
    "Std_Open",
    "Std_New",
}


def record(name, label, index=None):
    if name and name not in NOT_REPEATABLE:
        _last.update(name=name, index=index, label=label)


def last():
    """(name, index, label) of the last repeatable command, or None."""
    return (_last["name"], _last["index"], _last["label"]) if _last["name"] else None
