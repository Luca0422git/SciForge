# SPDX-License-Identifier: LGPL-2.1-or-later
"""A counter that moves whenever something a panel shows may have changed, so the panels'
polling timers can skip their work while nothing happens.

The timeline (every 400 ms) and the browser (every 500 ms) read the whole design on each
tick to see whether it changed: on a design of 120 steps that was 30 ms and 55 ms a tick,
a quarter of the processor while the person only looks at the part, and a hitch in the
middle of an orbit every half second (SciForge speed with big designs, 2026-10-21; Fusion
does not stutter there). Now a tick first compares key(): this counter (moved by FreeCAD's
document signals: an object made, changed, deleted or recomputed, undo / redo, a document
opened, renamed, closed or switched to, a view provider changed, an edit started or ended)
and the active document, body and component (FreeCAD signals no change of those). The
whole design is read only when the key changed, and at least every SAFETY seconds in case
something changed without a signal (a flag FreeCAD sets without telling anyone). An
explicit refresh() (after a command, from a test) still always reads the design.

The pure part (Gate: the decision) has no FreeCAD in it and is unit tested
(test_doc_epoch.py); install() and key() need FreeCAD.
"""

import time

SAFETY = 5.0  # seconds: the longest a poll trusts an unchanged key

_count = [0]
_observers = {"app": None, "gui": None}


def bump(*_args):
    """Something changed (any FreeCAD signal routed here)."""
    _count[0] += 1


def value():
    return _count[0]


class Gate:
    """Should a poll read the design? ready(key) is True when the key differs from the one
    of the last read, or the last read is older than `safety` seconds; done(key) records a
    read. Pure Python (the clock can be given, for the tests)."""

    def __init__(self, safety=SAFETY, clock=time.monotonic):
        self.safety = safety
        self.clock = clock
        self.key = None
        self.at = None

    def ready(self, key):
        if self.at is None or key != self.key:
            return True
        return self.clock() - self.at >= self.safety

    def done(self, key):
        self.key = key
        self.at = self.clock()

    def forget(self):
        self.key = self.at = None


# -- FreeCAD ----------------------------------------------------------------------------------
_APP_SLOTS = (
    "slotCreatedDocument",
    "slotDeletedDocument",
    "slotRelabelDocument",
    "slotActivateDocument",
    "slotRecomputedDocument",
    "slotUndoDocument",
    "slotRedoDocument",
    "slotCommitTransaction",
    "slotAbortTransaction",
    "slotChangedDocument",
    "slotCreatedObject",
    "slotDeletedObject",
    "slotChangedObject",
    "slotRecomputedObject",
    "slotAppendDynamicProperty",
    "slotRemoveDynamicProperty",
    "slotFinishRestoreDocument",
    "slotFinishSaveDocument",
)
_GUI_SLOTS = (
    "slotCreatedDocument",
    "slotDeletedDocument",
    "slotRelabelDocument",
    "slotRenameDocument",
    "slotActivateDocument",
    "slotCreatedObject",
    "slotDeletedObject",
    "slotChangedObject",
    "slotInEdit",
    "slotResetEdit",
)


def _watcher(slots):
    cls = type("SciForgeEpochWatch", (), {name: staticmethod(bump) for name in slots})
    return cls()


def install():
    """Watch FreeCAD's documents (once). Never raises."""
    try:
        import FreeCAD as App

        if _observers["app"] is None:
            _observers["app"] = _watcher(_APP_SLOTS)
            App.addDocumentObserver(_observers["app"])
    except Exception as exc:
        _info("design change watch: %s" % exc)
    try:
        import FreeCAD as App

        if _observers["gui"] is None and App.GuiUp:
            import FreeCADGui as Gui

            _observers["gui"] = _watcher(_GUI_SLOTS)
            Gui.addDocumentObserver(_observers["gui"])
    except Exception as exc:
        _info("design change watch (views): %s" % exc)


def busy():
    """True while a document recomputes or is being opened. FreeCAD keeps the window alive
    during a long recompute (and while reading a file) by running Qt's events from inside
    it, so the panels' polls came in the middle of one and read a half-built design every
    tick (33 browser and 35 timeline reads, 4 s of a 20 s edit of a 120-step design; 30 reads
    while opening it); they wait for the end instead."""
    try:
        import FreeCAD as App

        for doc in App.listDocuments().values():
            if getattr(doc, "Recomputing", False) or getattr(doc, "Restoring", False):
                return True
        return False
    except Exception:
        return False


def installed():
    return _observers["app"] is not None


def key():
    """What a panel's poll compares: the counter, the active document, its active body and
    component slot and the object in edit. None when the watch is not installed (then every
    poll reads the design, as before)."""
    if not installed():
        return None
    try:
        import FreeCAD as App
        import FreeCADGui as Gui

        doc = App.ActiveDocument
        gdoc = Gui.ActiveDocument
        body = part = edit = view = None
        if gdoc is not None:
            view = gdoc.ActiveView
            try:
                body = view.getActiveObject("pdbody")
                part = view.getActiveObject("part")
            except Exception:
                pass
            try:
                edit = gdoc.getInEdit()
            except Exception:
                pass
        return (
            _count[0],
            doc.Name if doc is not None else None,
            gdoc.Document.Name if gdoc is not None else None,
            type(view).__name__ if view is not None else None,
            _name(body),
            _name(part),
            _name(getattr(edit, "Object", None)),
        )
    except Exception:
        return None


def _name(obj):
    try:
        return (obj.Document.Name, obj.Name) if obj is not None else None
    except Exception:
        return None


def _info(text):
    try:
        from . import _remember

        _remember("info", text)
    except Exception:
        pass
