# SPDX-License-Identifier: LGPL-2.1-or-later
"""Undo and Redo without rebuilding the design when FreeCAD already put every shape back.

Fusion recomputes after Undo / Redo, and so does SciForge (timeline_ui.after_undo): FreeCAD
restores the properties a step had, but marks the steps it restored "touched", and steps
left touched would be rebuilt by the next recompute anyway. Measured on a design of 1700
faces and one of 120 steps (SciForge speed with big designs, 2026-10-21): every Ctrl+Z and
Ctrl+Y rebuilt the edited chain again, 15-23 s, although the shapes FreeCAD restored were
already the right ones. When a dialog's OK recomputes inside its transaction (they all do),
the transaction holds the new shapes as well as the new values, so Undo brings back the old
values together with the old shapes that were built from them.

That is only true when nothing changed outside the transaction, so this module keeps a
ledger per document, from FreeCAD's document signals:

- every property change made outside a transaction (not by Undo / Redo themselves, not while
  a file is read) moves a counter (`seq`);
- when a transaction starts, the counter and whether the design was up to date then (no step
  touched, invalid or in error; an object the transaction itself creates does not count: its
  Undo deletes it) are written down; when it is committed, whether it was up to date at its
  end;
- during an Undo / Redo, the objects whose Shape FreeCAD put back are noted.

An Undo may skip the rebuild when the transaction it undoes started on an up-to-date design
and the counter has not moved since it started; a Redo, when the transaction ended on an
up-to-date design and the counter has not moved since it was undone. And, in both cases,
every object left touched had its Shape put back by that Undo / Redo (an object without a
Shape, a spreadsheet, a component: rebuilt as before), and none is in error. Anything the
ledger cannot vouch for (a transaction it did not see start, its stack out of step with
FreeCAD's) is rebuilt as before. The touched marks are then cleared (the design is up to
date: nothing for the next recompute to redo).

Ledger (the decisions) is pure Python and unit tested (test_undo_fast.py); install() and
the observer need FreeCAD.
"""

PROBLEMS = ("Touched", "Invalid", "Error")
# Objects that hold only values (no shape, nothing computed): an Undo / Redo that puts their
# values back leaves them exactly as they were (user parameters).
VALUE_ONLY = {"App::VarSet"}
# Objects without a Shape that depend on the restored shapes but compute nothing that an Undo
# could have left stale (groups, links, the origin, value holders: what they show is in their
# properties or is the linked shape itself). Every other dependent without a Shape (a drawing
# view keeps its projected lines in memory, an analysis its picture) is recomputed after an
# Undo / Redo that skipped the rebuild.
NOTHING_COMPUTED = {"App::Origin", "App::Line", "App::Plane", "App::Point", "App::VarSet", "Spreadsheet::Sheet"}
NOTHING_COMPUTED_EXTENSIONS = ("App::GroupExtension", "App::LinkBaseExtension")
# Properties that never feed a shape: changed outside a transaction (a dialog shows its
# sketch again after OK, a step is renamed), they leave every shape as it was built.
NOT_GEOMETRY = {"Visibility", "_GroupTouched", "Label", "Label2"}


class Ledger:
    """One document's bookkeeping. Transactions are kept as a stack mirroring FreeCAD's undo
    stack (and one for redo); `count` arguments are FreeCAD's UndoCount after the event, to
    check the two stacks are still in step."""

    def __init__(self):
        self.seq = 0  # property changes made outside a transaction
        self.pending = None  # the transaction being recorded
        self.undo = []  # entries, oldest first
        self.redo = []  # entries undone, the next to redo last
        self.restored = set()  # objects whose Shape the running Undo / Redo put back
        self.decision = None  # {"ok", "seq", "restored"} of the last Undo / Redo
        # FreeCAD applies an Undo / Redo, then lets some objects finish it before it signals
        # the Undo / Redo (SketchObject::onUndoRedoFinished solves the sketch again), with
        # its "undoing" flag already cleared: those changes are part of the Undo / Redo.
        self.applying = False  # an Undo / Redo (or an abort) is being applied
        self.follow_up = 0  # sketch changes since, not counted (yet) as outside changes

    # -- recording
    def outside_change(self, sketch=False):
        """A change made outside a transaction. `sketch`: a sketch's own change, which right
        after an Undo / Redo was applied is FreeCAD finishing it (the sketch solved again)."""
        if sketch and self.applying:
            self.follow_up += 1
            return
        self.seq += 1
        self.restored = set()  # (an Undo / Redo is one block of changes)

    def transacting_change(self):
        """FreeCAD changed a property while it applies an Undo / Redo (or an abort)."""
        self.applying = True

    def shape_restored(self, name):
        self.applying = True
        self.restored.add(name)

    def _end_applying(self, finished):
        """The Undo / Redo was signalled (`finished`: its follow-up changes were part of it),
        or something else came first (they count as outside changes, the safe side)."""
        if not finished:
            self.seq += self.follow_up
        self.applying, self.follow_up = False, 0

    def opened(self, clean, dirty=()):
        """A transaction started; `clean`: the design was up to date then, `dirty`: the names
        of the objects that were not (see created)."""
        self._end_applying(False)
        self.pending = {"start": self.seq, "clean_start": bool(clean), "dirty": set(dirty)}
        self.restored = set()

    def created(self, name):
        """An object was created inside the transaction being recorded. FreeCAD opens a
        transaction at its first change, and when that change is a new object (a dialog's or
        the AI's new step) the object is already there, touched, when the transaction is
        opened: the Undo deletes it, so it never made the start "not up to date"."""
        p = self.pending
        if p is None or p["clean_start"] or name not in p.get("dirty", ()):
            return
        p["dirty"].discard(name)
        if not p["dirty"]:
            p["clean_start"] = True

    def committed(self, clean, count):
        self._end_applying(False)
        entry, self.pending = self.pending, None
        self.redo = []  # FreeCAD drops its redo stack on a new transaction
        if entry is None:
            self.forget()  # a transaction it did not see start
            return
        entry["clean_end"] = bool(clean)
        self.undo.append(entry)
        if count is not None:
            if len(self.undo) < count:
                self.forget()  # out of step: from here on, nothing is vouched for
            else:
                del self.undo[: len(self.undo) - count]  # FreeCAD forgot its oldest

    def aborted(self):
        self._end_applying(False)
        self.pending = None
        self.restored = set()

    def forget(self):
        self._end_applying(False)
        self.undo, self.redo, self.pending = [], [], None
        self.decision = None

    # -- Undo / Redo
    def undone(self, count):
        """FreeCAD undid its newest transaction (`count`: UndoCount after it)."""
        self._end_applying(True)
        restored, self.restored = self.restored, set()
        if not self.undo or len(self.undo) - 1 != count:
            why = "the ledger is out of step with FreeCAD's undo stack (%d, %s)" % (len(self.undo), count)
            self.forget()
            self.decision = {"ok": False, "seq": self.seq, "restored": restored, "why": why}
            return self.decision
        entry = self.undo.pop()
        entry["undone_at"] = self.seq
        self.redo.append(entry)
        if not entry.get("clean_start", False):
            why = "the design was not up to date when the transaction started"
        elif entry.get("start") != self.seq:
            why = "%d changes outside a transaction since it started" % (self.seq - entry["start"])
        else:
            why = ""
        self.decision = {"ok": not why, "seq": self.seq, "restored": restored, "why": why}
        return self.decision

    def redone(self, count):
        """FreeCAD redid the transaction undone last (`count`: UndoCount after it)."""
        self._end_applying(True)
        restored, self.restored = self.restored, set()
        if not self.redo or len(self.undo) + 1 != count:
            why = "the ledger is out of step with FreeCAD's redo stack (%d, %s)" % (len(self.undo), count)
            self.forget()
            self.decision = {"ok": False, "seq": self.seq, "restored": restored, "why": why}
            return self.decision
        entry = self.redo.pop()
        self.undo.append(entry)  # (redone, it can be undone again: it starts where it started)
        if not entry.get("clean_end", False):
            why = "the design was not up to date when the transaction ended"
        elif entry.get("undone_at") != self.seq:
            why = "%d changes outside a transaction since the undo" % (self.seq - entry["undone_at"])
        else:
            why = ""
        self.decision = {"ok": not why, "seq": self.seq, "restored": restored, "why": why}
        return self.decision

    def may_skip(self, touched):
        """True when the last Undo / Redo left the design as built: its decision holds, the
        counter has not moved since, and every touched object (name, has a Shape, in
        error) had its Shape put back."""
        return not self.why_not(touched)

    def why_not(self, touched):
        """Why the design must be rebuilt after the last Undo / Redo ("" when it need not)."""
        d = self.decision
        if not d:
            return "no Undo / Redo seen"
        if not d["ok"]:
            return d.get("why") or "cannot vouch for the shapes"
        if d["seq"] != self.seq:
            return "changed outside a transaction since the Undo / Redo"
        for name, has_shape, broken in touched:
            if broken:
                return "%s is in error" % name
            if not has_shape:
                return "%s has no shape to put back" % name
            if name not in d["restored"]:
                return "the shape of %s was not put back" % name
        return ""


# -- FreeCAD ----------------------------------------------------------------------------------
import os as _os

_DEBUG = bool(_os.environ.get("SCIFORGE_UNDO_DEBUG"))
_ledgers = {}
_observer = {"app": None}
_quiet = set()  # (document, object) whose changes are SciForge's own refresh (not counted)
stats = {"skipped": 0, "rebuilt": 0}  # Undo / Redo settled without / with a rebuild (tests)


def ledger(doc_name):
    if doc_name not in _ledgers:
        _ledgers[doc_name] = Ledger()
    return _ledgers[doc_name]


def _clean(doc):
    try:
        for obj in doc.Objects:
            state = obj.State
            if "Touched" in state or "Invalid" in state or "Error" in state:
                return False
        return True
    except Exception:
        return False


def _dirty(doc):
    """Names of the objects not up to date (None when they cannot be read)."""
    try:
        return [name for name, _shape, _broken in touched(doc)]
    except Exception:
        return None


class _Watch:
    """Document observer feeding the ledgers. Never raises."""

    def slotChangedObject(self, obj, prop):
        try:
            doc = obj.Document
            if doc.Restoring:
                return
            if doc.Transacting:
                if prop == "Shape" or obj.TypeId in VALUE_ONLY:
                    ledger(doc.Name).shape_restored(obj.Name)
                else:
                    ledger(doc.Name).transacting_change()
                return
            if (doc.Name, obj.Name) in _quiet:
                return
            if not doc.HasPendingTransaction and prop not in NOT_GEOMETRY:
                ledger(doc.Name).outside_change(obj.isDerivedFrom("Sketcher::SketchObject"))
                if _DEBUG:
                    print("[SciForge] undo ledger: outside change %s.%s" % (obj.Name, prop), flush=True)
        except Exception:
            pass

    def slotCreatedObject(self, obj):
        try:
            doc = obj.Document
            if doc.HasPendingTransaction and not doc.Transacting and not doc.Restoring:
                ledger(doc.Name).created(obj.Name)
        except Exception:
            pass
        self._structure(obj)

    def slotDeletedObject(self, obj):
        self._structure(obj)

    def _structure(self, obj):
        try:
            doc = obj.Document
            if not doc.Restoring and not doc.Transacting and not doc.HasPendingTransaction:
                ledger(doc.Name).outside_change()
        except Exception:
            pass

    def slotOpenTransaction(self, doc, _name):
        try:
            dirty = _dirty(doc)
            if _DEBUG:
                print("[SciForge] undo ledger: open %s not up to date: %s" % (_name, dirty), flush=True)
            if dirty is None:
                ledger(doc.Name).opened(False)
            else:
                ledger(doc.Name).opened(not dirty, dirty)
        except Exception:
            pass

    def slotCommitTransaction(self, doc):
        try:
            if _DEBUG:
                print("[SciForge] undo ledger: commit clean=%s" % _clean(doc), flush=True)
            ledger(doc.Name).committed(_clean(doc), doc.UndoCount)
        except Exception:
            pass

    def slotAbortTransaction(self, doc):
        try:
            ledger(doc.Name).aborted()
        except Exception:
            pass

    def slotUndoDocument(self, doc):
        try:
            ledger(doc.Name).undone(doc.UndoCount)
        except Exception:
            pass

    def slotRedoDocument(self, doc):
        try:
            ledger(doc.Name).redone(doc.UndoCount)
        except Exception:
            pass

    def slotFinishRestoreDocument(self, doc):
        try:
            _ledgers[doc.Name] = Ledger()
        except Exception:
            pass

    def slotDeletedDocument(self, doc):
        try:
            _ledgers.pop(doc.Name, None)
        except Exception:
            pass


def _info(text):
    try:
        from . import _remember

        _remember("info", text)
        import os

        if os.environ.get("SCIFORGE_UNDO_DEBUG"):
            print("[SciForge] %s" % text, flush=True)
    except Exception:
        pass


def install():
    """Watch every document (once). Never raises."""
    try:
        import FreeCAD as App

        if _observer["app"] is None:
            _observer["app"] = _Watch()
            App.addDocumentObserver(_observer["app"])
    except Exception as exc:
        _info("undo ledger: %s" % exc)


def touched(doc):
    """[(name, has a Shape (or holds only values), in error)] of the objects not up to date."""
    out = []
    for obj in doc.Objects:
        state = obj.State
        if "Touched" in state or "Invalid" in state or "Error" in state:
            out.append(
                (
                    obj.Name,
                    "Shape" in obj.PropertiesList or obj.TypeId in VALUE_ONLY,
                    "Invalid" in state or "Error" in state,
                )
            )
    return out


def _computes_outside_properties(obj):
    """True for an object without a Shape that computes something an Undo cannot put back
    (a drawing view's projected lines, an analysis), see NOTHING_COMPUTED."""
    if "Shape" in obj.PropertiesList or obj.TypeId in NOTHING_COMPUTED:
        return False
    for ext in NOTHING_COMPUTED_EXTENSIONS:
        try:
            if obj.hasExtension(ext):
                return False
        except Exception:
            pass
    return True


def stale_dependents(doc, names):
    """The objects (in any open document) that depend on the objects `names` of `doc` and
    keep what they computed outside their properties: an Undo / Redo restored the shapes
    they were made from but not what they made from them (review finding F1, 2026-10-22: a
    drawing still showed the edited part after Ctrl+Z, and its dimensions the edited values)."""
    import FreeCAD as App

    wanted = {(doc.Name, name) for name in names}
    out = []
    if not wanted:
        return out
    for other in App.listDocuments().values():
        for obj in other.Objects:
            try:
                if not _computes_outside_properties(obj):
                    continue
                if any((dep.Document.Name, dep.Name) in wanted for dep in obj.OutListRecursive):
                    out.append(obj)
            except Exception:
                continue
    return out


def _refresh(objs):
    """Recompute `objs` only (the shapes they depend on are up to date), document by
    document. Their own changes are not counted as outside changes: they feed no shape."""
    by_doc = {}
    for obj in objs:
        by_doc.setdefault(obj.Document.Name, (obj.Document, []))[1].append(obj)
    for other, group in by_doc.values():
        keys = {(other.Name, obj.Name) for obj in group}
        _quiet.update(keys)
        try:
            for obj in group:
                obj.touch()
            other.recompute(group)
        finally:
            _quiet.difference_update(keys)


def settle_without_rebuild(doc):
    """After an Undo / Redo: True (and the touched marks cleared) when every shape FreeCAD
    put back is already the right one, so no recompute is needed; False to recompute."""
    if _observer["app"] is None:
        return False
    try:
        led = _ledgers.get(doc.Name)
        stale = touched(doc)
        why = "no ledger" if led is None else led.why_not(stale)
        if why:
            stats["rebuilt"] += 1
            _info("after Undo / Redo, %s rebuilt: %s" % (doc.Label, why))
            return False
        restored = set(led.decision.get("restored") or ())
        for name, _has_shape, _broken in stale:
            restored.add(name)
            obj = doc.getObject(name)
            if obj is not None:
                obj.purgeTouched()
        led.decision = None  # once
        try:
            # what depends on the shapes put back but computed something from them that the
            # Undo / Redo could not put back (a drawing view): recomputed, nothing else
            dependents = stale_dependents(doc, restored)
            if dependents:
                _refresh(dependents)
                if _DEBUG:
                    _info("after Undo / Redo, recomputed %s" % ", ".join(o.Name for o in dependents))
        except Exception as exc:
            _info("after Undo / Redo, refreshing what depends on %s: %s" % (doc.Label, exc))
            for name, _has_shape, _broken in stale:
                obj = doc.getObject(name)
                if obj is not None:
                    obj.touch()  # (the caller's recompute rebuilds the design as before)
            stats["rebuilt"] += 1
            return False
        stats["skipped"] += 1
        return True
    except Exception:
        stats["rebuilt"] += 1
        return False
