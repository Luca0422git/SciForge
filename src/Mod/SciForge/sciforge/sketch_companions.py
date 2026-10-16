# SPDX-License-Identifier: LGPL-2.1-or-later
"""Curves that belong to a sketch but cannot live in FreeCAD's flat sketch: Project to
Surface's curves (sketch_project.py) and the 3D Sketch's lines and splines (sketch3d.py).

Fusion keeps both in the sketch itself: they are drawn with it, hidden with it, listed
with it and gone with it, and the sketch's timeline step is theirs (Fusion has no step of
their own). FreeCAD's sketches are flat, so SciForge keeps them in a "companion" object
of the sketch (a Part feature that follows the sketch and its sources when the design
recomputes) and makes it behave as part of the sketch:

- it links its sketch (hidden property SciForgeSketch) and is a helper of the sketch's
  step (SciForgeRole "SketchCurves"): no timeline step of its own; deleting the sketch
  deletes it (timeline_ops.GOES_WITH_STEP, delete.py);
- the browser lists it under its sketch (browser_core: a child row of the sketch);
- it is shown and hidden with its sketch: whenever the sketch's eye changes (the user,
  the history marker rolled back before the sketch, Suppress, a feature that hides its
  sketch) the companion follows (an observer, work done from a Qt timer).

No Qt in the document functions; the observer only schedules work.
"""

import FreeCAD as App

from . import warn

OWNER = "SciForgeSketch"
ROLE_PROP = "SciForgeRole"
ROLE = "SketchCurves"
TYPES = ("ProjectedCurves", "Sketch3DCurves")

_state = {"observer": None}


def is_companion(obj):
    try:
        return getattr(obj, "SciForgeType", "") in TYPES and getattr(obj, OWNER, None) is not None
    except Exception:
        return False


def owner(obj):
    """The sketch a companion belongs to, or None."""
    return getattr(obj, OWNER, None) if is_companion(obj) else None


def companions(sketch, kind=None):
    """The companions of a sketch (of one SciForgeType when `kind` is given), oldest first."""
    found = []
    try:
        for obj in sketch.InList:  # (an object that links the sketch twice is listed twice)
            if obj in found or not is_companion(obj) or getattr(obj, OWNER, None) is not sketch:
                continue
            if kind is None or obj.SciForgeType == kind:
                found.append(obj)
    except Exception:
        return []
    return sorted(found, key=lambda o: getattr(o, "ID", 0))


def adopt(obj, sketch, kind):
    """Make `obj` a companion of `sketch` (SciForgeType `kind`)."""
    props = obj.PropertiesList
    if OWNER not in props:
        obj.addProperty("App::PropertyLinkGlobal", OWNER, "SciForge", "The sketch it belongs to")
        obj.setEditorMode(OWNER, 2)
    if "SciForgeType" not in props:
        obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
    if ROLE_PROP not in props:
        obj.addProperty("App::PropertyString", ROLE_PROP, "SciForge", "", 4)
    setattr(obj, OWNER, sketch)
    obj.SciForgeType = kind
    setattr(obj, ROLE_PROP, ROLE)


def sketch_placement(sketch, obj=None):
    """The placement that takes sketch coordinates to the coordinates the companion's
    shape is in: the sketch's global placement, seen from the component the companion
    sits in (the root: global)."""
    place = sketch.getGlobalPlacement()
    try:
        from . import components

        holder = components.container_of(obj) if obj is not None else None
        if holder is not None:
            place = holder.getGlobalPlacement().inverse().multiply(place)
    except Exception:
        pass
    return place


def follow_visibility(sketch):
    """Show / hide the companions as the sketch is (GUI only)."""
    if not App.GuiUp:
        return
    try:
        shown = bool(sketch.ViewObject.Visibility)
    except Exception:
        return
    for obj in companions(sketch):
        try:
            vobj = obj.ViewObject
            if vobj is not None and bool(vobj.Visibility) != shown:
                vobj.Visibility = shown
        except Exception as exc:
            warn("sketch curves: %s" % exc)


def _later(doc_name, name):
    try:
        doc = App.getDocument(doc_name)
        sketch = doc.getObject(name)
        if sketch is not None:
            follow_visibility(sketch)
    except Exception:
        pass


class _Observer:
    """A sketch's eye changed: its companions follow (from a Qt timer)."""

    def slotChangedObject(self, obj, prop):
        if prop != "Visibility":
            return
        try:
            if obj.TypeId != "Sketcher::SketchObject" or not companions(obj):
                return
            from .compat import QtCore

            doc_name, name = obj.Document.Name, obj.Name
            QtCore.QTimer.singleShot(0, lambda: _later(doc_name, name))
        except Exception:
            pass


def enable():
    if _state["observer"] is not None:
        return
    try:
        observer = _Observer()
        App.addDocumentObserver(observer)
        _state["observer"] = observer
    except Exception as exc:
        warn("sketch curves: cannot follow sketches: %s" % exc)


def disable():
    observer, _state["observer"] = _state["observer"], None
    if observer is not None:
        try:
            App.removeDocumentObserver(observer)
        except Exception:
            pass
