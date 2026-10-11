# SPDX-License-Identifier: LGPL-2.1-or-later
"""After Undo / Redo, re-link the formulas FreeCAD forgot.

FreeCAD 1.1 bug (found 2026-10-11, primitives work): undo a step that put a formula on a
value (a parameter typed in a dialog field, "=width"), then redo it: the formula is back
on the property, but its link to the parameter is not (the object's OutList lacks the
parameters object). Changing the parameter then changes nothing until the file is
reopened. It happens to PartDesign features (Pad, the primitives) and to SciForge's 2D
helper objects; plain App::FeaturePython keeps its link.

Setting the same expression again rebuilds the link. That change is made outside any undo
step (FreeCAD records nothing, the undo/redo lists stay as they are), only for objects
whose links are really missing, and the touched objects are recomputed (same values).
install() is called once when the SciForge commands load.
"""
import re

import FreeCAD as App

_STATE = {"observer": None}
_NAME = re.compile(r"(?:<<([^>]+)>>|\b([A-Za-z_][A-Za-z0-9_]*))\s*\.")


def referenced(doc, expression):
    """The document objects a FreeCAD expression reads (by name or <<label>>)."""
    found = []
    for label, name in _NAME.findall(expression or ""):
        obj = None
        if name:
            obj = doc.getObject(name)
        elif label:
            matches = doc.getObjectsByLabel(label)
            obj = matches[0] if matches else None
        if obj is not None and obj not in found:
            found.append(obj)
    return found


def broken(obj):
    """[(path, expression)] of obj's formulas whose objects are missing from its links."""
    out = []
    try:
        engine = list(obj.ExpressionEngine)
        links = {o.Name for o in obj.OutList}
    except Exception:
        return out
    for path, expression in engine:
        needed = [o for o in referenced(obj.Document, expression) if o is not obj]
        if any(o.Name not in links for o in needed):
            out.append((path, expression))
    return out


def relink(doc):
    """Set the forgotten formulas again; returns the objects that were fixed."""
    fixed = []
    for obj in list(doc.Objects):
        for path, expression in broken(obj):
            try:
                obj.setExpression(path, None)
                obj.setExpression(path, expression)
                if obj not in fixed:
                    fixed.append(obj)
            except Exception:
                pass
    if fixed:
        try:
            from . import preview

            preview.recompute(doc)
        except Exception:
            pass
    return fixed


def _later(doc):
    try:
        from .compat import QtCore

        name = doc.Name
        QtCore.QTimer.singleShot(0, lambda: _run(name))
    except Exception:
        pass


def _run(name):
    try:
        doc = App.getDocument(name)
    except Exception:
        return
    try:
        if doc is None or doc.Recomputing:
            return
        fixed = relink(doc)
        if fixed:
            from . import log

            log("formulas re-linked after undo/redo: %s" % ", ".join(o.Label for o in fixed))
    except Exception as exc:
        from . import warn

        warn("could not re-link formulas: %s" % exc)


class _Observer:
    def slotUndoDocument(self, doc):
        _later(doc)

    def slotRedoDocument(self, doc):
        _later(doc)


def install():
    if _STATE["observer"] is not None:
        return
    _STATE["observer"] = _Observer()
    App.addDocumentObserver(_STATE["observer"])
