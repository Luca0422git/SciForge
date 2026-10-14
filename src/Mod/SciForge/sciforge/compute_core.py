# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compute All's summary without FreeCAD or Qt (unit tested); compute_ui.py runs it."""


def counts(found):
    """(errors, warnings) of [(name, label, "error" | "warning", reason)]."""
    errors = sum(1 for f in found if f[2] == "error")
    warnings = sum(1 for f in found if f[2] == "warning")
    return errors, warnings


def summary_words(count, seconds, found):
    """ "Compute All: 12 steps in 0.3 s, all computed." or "...: 1 could not be computed, 2
    with warnings." (the words of the timeline's red and yellow steps)."""
    errors, warnings = counts(found)
    head = "Compute All: %d step%s in %.1f s" % (count, "" if count == 1 else "s", seconds)
    if not errors and not warnings:
        return head + ", all computed."
    parts = []
    if errors:
        parts.append("%d could not be computed" % errors)
    if warnings:
        parts.append("%d with %s" % (warnings, "a warning" if warnings == 1 else "warnings"))
    return head + ": " + ", ".join(parts) + "."


def ordered(found):
    """Errors first (they stop what comes after them), then warnings, each in timeline order."""
    return [f for f in found if f[2] == "error"] + [f for f in found if f[2] != "error"]
