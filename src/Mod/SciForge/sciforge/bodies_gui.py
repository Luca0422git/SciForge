# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI pieces the body tools share (Combine, Split Body, Move/Copy, Delete, Appearance,
Physical Material):

- StepViewProvider: the view provider of their timeline steps (icon, double-click edits).
  Saved in files as "sciforge.bodies_gui.StepViewProvider": keep the name.
- Watch: one document observer that, after every recompute, undo/redo and delete, shows
  bodies a Combine no longer uses up (and hides the ones it does), re-applies appearances,
  and removes the extra bodies of a deleted Split Body or copy. Nothing is done inside
  FreeCAD's own callbacks: the work runs a moment later from a Qt timer.
- BodyPick: what a click in the 3D view (or the browser) means for a body tool.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, log, ui_icon_path, warn
from .compat import QtCore

ICONS = {
    "Combine": "combine",
    "SplitBody": "split_body",
    "MoveCopy": "move",
    "DeleteFace": "delete",
    "Remove": "remove",
    "Align": "align",
    "ReplaceFace": "replace_face",
    "SplitFace": "split_face",
    "SilhouetteSplit": "silhouette_split",
}


# Steps that made or used other bodies: when one is deleted, its extra bodies go too.
MAKERS = ("Combine", "SplitBody", "SilhouetteSplit", "MoveCopy")


class StepViewProvider:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        kind = bodies.kind(getattr(self, "Object", None))
        return ui_icon_path(ICONS.get(kind, "workspace_design"))

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        _edit_later(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        _edit_later(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _edit_later(obj):
    name, doc = obj.Name, obj.Document.Name

    def run():
        try:
            if doc not in App.listDocuments():
                return
            target = App.getDocument(doc).getObject(name)
            if target is not None:
                from . import taskui

                taskui.edit_object(target)
        except Exception as exc:
            warn("could not edit %s: %s" % (name, exc))

    QtCore.QTimer.singleShot(0, run)


def attach_view_provider(obj):
    try:
        if obj.ViewObject is not None and not isinstance(
            getattr(obj.ViewObject, "Proxy", None), StepViewProvider
        ):
            StepViewProvider(obj.ViewObject)
    except Exception:
        pass


# -- the document watch ------------------------------------------------------------------------
class Watch:
    """See the module text. Every slot only schedules work (rule: nothing inside FreeCAD's
    callbacks)."""

    def __init__(self):
        self._pending = set()
        self._orphans = set()

    def _later(self, doc, orphans=False):
        try:
            name = doc.Name
        except Exception:
            return
        if orphans:
            self._orphans.add(name)
        if name in self._pending:
            return
        self._pending.add(name)
        QtCore.QTimer.singleShot(0, lambda: self._run(name))

    def slotRecomputedDocument(self, doc):
        self._later(doc)

    def slotUndoDocument(self, doc):
        self._later(doc)

    def slotRedoDocument(self, doc):
        self._later(doc)

    def slotDeletedObject(self, obj):
        """A Split Body or a copy deleted (the timeline's or the browser's Delete): its
        extra bodies go too, as in Fusion. Only on a delete, never after an undo, so undoing
        that removal brings them back for good.

        A step a Combine uses (a tool body's, or a New Body Combine's target) deleted by any
        Delete: the Combine keeps it as it was, so it goes on giving the same result. This one
        is done at once, before FreeCAD drops the link, inside the same undo step."""
        try:
            freeze_for(obj)
        except Exception as exc:
            warn("body tools: %s" % exc)
        try:
            if bodies.kind(obj) in MAKERS or bodies.is_body(obj):
                self._later(obj.Document, orphans=True)
            elif _leads_followers(obj):
                # A multi-body extrude deleted by FreeCAD's own Delete: its hidden steps in
                # the other bodies go a moment later (SciForge's Delete takes them at once).
                self._later(obj.Document, orphans=True)
        except Exception:
            pass

    def slotCreatedDocument(self, doc):
        """A new design, or a file being opened. FreeCAD tells Python observers nothing when
        a file has finished loading, so that is looked at a moment later (_opened)."""
        try:
            bodies.sync_consumed(doc, initial=True)
            name = doc.Name
            QtCore.QTimer.singleShot(0, lambda: _opened(name))
        except Exception:
            pass

    def slotDeletedDocument(self, doc):
        try:
            bodies.forget(doc.Name)
            from . import components, components_ui

            components.forget(doc.Name)  # the body last active in each component
            components_ui.ISOLATED.pop(doc.Name, None)
        except Exception:
            pass

    def _run(self, name):
        self._pending.discard(name)
        try:
            if name not in App.listDocuments():
                self._orphans.discard(name)
                return
            doc = App.getDocument(name)
            if getattr(doc, "Recomputing", False) or getattr(doc, "Restoring", False):
                QtCore.QTimer.singleShot(100, lambda: self._later(doc))
                return
            if name in self._orphans and not doc.HasPendingTransaction:
                self._orphans.discard(name)
                remove_orphans(doc)
            sync(doc)
        except Exception as exc:
            warn("body tools: %s" % exc)


def _leads_followers(obj):
    try:
        from . import extrude_bodies

        if getattr(obj.Document, "Transacting", False):
            return False  # an undo / redo takes the followers along itself
        return bool(extrude_bodies.followers_of(obj))
    except Exception:
        return False


def freeze_for(obj):
    """Combines that use `obj` (being deleted) keep its solid (combine.freeze_tools). Only
    for a delete: an undo, a redo or a cancelled dialog rolling objects back changes
    nothing. Only properties of the Combines are set (no recompute): FreeCAD is in the
    middle of removing `obj`."""
    from . import combine

    doc = obj.Document
    if doc is None or getattr(doc, "Transacting", False) or getattr(doc, "Restoring", False):
        return
    for user in list(obj.InList):
        if not combine.is_combine(user) or user is obj or not bodies.alive(user):
            continue
        uses = obj in list(user.Tools) or (user.NewBody and user.Target is obj)
        if uses:
            combine.freeze_tools(user, {obj.Name})


def _opened(name, tries=0):
    """A design just created or opened: the bodies used up in it are recorded as they are
    (nothing is shown or hidden), and the active body is not a used-up one."""
    try:
        if name not in App.listDocuments():
            return
        doc = App.getDocument(name)
        if getattr(doc, "Restoring", False) or getattr(doc, "Recomputing", False):
            if tries < 50:
                QtCore.QTimer.singleShot(100, lambda: _opened(name, tries + 1))
            return
        bodies.forget(name)
        bodies.sync_consumed(doc, initial=True)
        _free_body_first(name)
    except Exception as exc:
        warn("body tools: %s" % exc)


def _free_body_first(name):
    """A design just opened has no active body, and SciForge's commands then take the first
    body of the design. When a Combine used that body up (it is hidden), a new sketch and
    extrude would go into a body nobody sees: the first body that is not used up becomes
    the active one instead."""
    try:
        if name not in App.listDocuments():
            return
        doc = App.getDocument(name)
        if bodies.active_body(doc) is not None:
            return
        found = bodies.list_bodies(doc)
        used = bodies.consumed(doc)
        if not found or found[0].Name not in used:
            return
        for body in found:
            if body.Name not in used and bodies.has_solid(body):
                bodies.set_active_body(body)
                return
    except Exception as exc:
        warn("body tools: %s" % exc)


def remove_orphans(doc):
    """The extra bodies of a deleted Split Body or copy, removed as their own undo step."""
    from . import delete as delete_core

    if not delete_core.orphans(doc):
        return False
    doc.openTransaction("Delete bodies of a deleted step")
    try:
        delete_core.remove_orphans(doc)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    from . import timeline_ops

    timeline_ops.recompute(doc)
    log("bodies of a deleted step removed")
    return True


def sync(doc):
    """Bring the view in line with the design: used-up bodies hidden (and shown again when
    free), appearances on every step."""
    bodies.sync_consumed(doc)
    try:
        from . import appearance

        appearance.sync(doc)
    except Exception as exc:
        warn("appearance: %s" % exc)


_WATCH = {"observer": None}


def install():
    if _WATCH["observer"] is None:
        _WATCH["observer"] = Watch()
        App.addDocumentObserver(_WATCH["observer"])
        for name in App.listDocuments():
            try:
                bodies.sync_consumed(App.getDocument(name), initial=True)
            except Exception:
                pass


# -- clicks ------------------------------------------------------------------------------------
def picked_bodies(doc, picks):
    """Bodies hit by the selection entries [(object, short name, point)]: a click on a face
    of a body, on the body in the browser, or on any of its steps picks the body."""
    found = []
    for obj, _short, _point in picks:
        if obj is None or obj.Document is not doc:
            continue
        body = bodies.body_of(obj)
        if body is not None and body not in found:
            found.append(body)
    return found


def body_text(found):
    if not found:
        return ""
    if len(found) == 1:
        return found[0].Label
    if len(found) <= 3:
        return ", ".join(b.Label for b in found)
    return "%d bodies" % len(found)


def selection_entries():
    """[(object, short name, point)] of the current selection (hole_common.picks)."""
    from . import hole_common

    try:
        return hole_common.picks()
    except Exception:
        return []


def clear_selection():
    try:
        Gui.Selection.clearSelection()
    except Exception:
        pass
