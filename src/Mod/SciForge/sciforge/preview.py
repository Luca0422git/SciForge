# SPDX-License-Identifier: LGPL-2.1-or-later
"""Live-preview helpers shared by SciForge's feature dialogs (Extrude, Press Pull).

While a Fusion dialog is open, a value that cannot be built (a zero distance, a face
the extrusion cannot reach, a taper too steep for the profile) is shown *in the
dialog* and the dialog stays open. FreeCAD prints the same failure to the Report
view as well, which a Fusion user reads as "errors everywhere". quiet() mutes
FreeCAD's error and warning output for the length of one preview recompute; the
dialog then reads the failure from the feature (obj.getStatusString()) and shows it.

Only the dialog's own recomputes are wrapped. Everything else (opening files,
editing earlier steps from the timeline) reports as usual.
"""
import contextlib

import FreeCAD as App

_TYPES = ("Err", "Wrn")


@contextlib.contextmanager
def quiet():
    saved = []
    try:
        for name in App.Console.GetObservers():
            for kind in _TYPES:
                try:
                    status = App.Console.GetStatus(name, kind)
                except Exception:
                    continue
                if status:
                    saved.append((name, kind))
                    App.Console.SetStatus(name, kind, False)
    except Exception:
        pass
    try:
        yield
    finally:
        for name, kind in saved:
            try:
                App.Console.SetStatus(name, kind, True)
            except Exception:
                pass


def recompute(doc):
    """doc.recompute() without FreeCAD's failure messages in the Report view."""
    with quiet():
        doc.recompute()


def failure(obj):
    """The error text of a feature that failed to compute, or ''."""
    if obj is None:
        return ""
    try:
        state = list(getattr(obj, "State", []))
    except Exception:
        return ""
    if "Invalid" in state or "Error" in state:
        try:
            text = obj.getStatusString()
        except Exception:
            text = ""
        return text or "This step cannot be built with these values."
    return ""
