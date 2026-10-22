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
  touched, invalid or in error) are written down; when it is committed, whether it was up to
  date at its end;
- during an Undo / Redo, the objects whose Shape FreeCAD put back are noted.

An Undo may skip the rebuild when the transaction it undoes started on an up-to-date design
and the counter has not moved since it started; a Redo, when the transaction ended on an
up-to-date design and the counter has not moved since it was undone. And, in both cases,
every object left touched had its Shape put back by that Undo / Redo (an object without a
Shape, a spreadsheet, a component: rebuilt as before), and none is in error. Anything the
ledger cannot vouch for (a transaction it did not see start, its stack out of step with
FreeCAD's) is rebuilt as before. The touched marks are then cleared (the design is up to
date: nothing for the next recompute to redo). What is built on the design but keeps no
Shape in the undo stack (a drawing's views and dimensions) is recomputed, alone (followers).

Ledger (the decisions) is pure Python and unit tested (test_undo_fast.py); install() and
the observer need FreeCAD.
"""

PROBLEMS = ("Touched", "Invalid", "Error")
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

    # -- recording
    def outside_change(self):
        self.seq += 1
        self.restored = set()  # (an Undo / Redo is one block of changes)

    def shape_restored(self, name):
        self.restored.add(name)

    def opened(self, clean):
        self.pending = {"start": self.seq, "clean_start": bool(clean)}
        self.restored = set()

    def committed(self, clean, count):
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
        self.pending = None
        self.restored = set()

    def forget(self):
        self.undo, self.redo, self.pending = [], [], None
        self.decision = None

    # -- Undo / Redo
    def undone(self, count):
        """FreeCAD undid its newest transaction (`count`: UndoCount after it)."""
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


def followers(stale, dependents):
    """Names of the objects to recompute when the design itself is not: of `dependents`
    ((name, has a Shape) of everything built on the `stale` objects, the objects an Undo /
    Redo left touched), those that keep no Shape FreeCAD could put back. A drawing's views
    and dimensions, its page, a component: what they show was computed from the old shapes
    and is not in the undo stack, so they would keep showing the undone design (a drawing
    with the R8 fillets after the R8 edit was undone, 2026-10-22). An object with a Shape is
    right: the Undo / Redo put it back, or it did not change."""
    stale = set(stale)
    out = []
    for name, has_shape in dependents:
        if not has_shape and name not in stale and name not in out:
            out.append(name)
    return out


# -- FreeCAD ----------------------------------------------------------------------------------
import os as _os

_DEBUG = bool(_os.environ.get("SCIFORGE_UNDO_DEBUG"))
_ledgers = {}
_observer = {"app": None}
# Undo / Redo settled without / with a rebuild, and the objects without a Shape recomputed
# after one settled without (followers()) (tests)
stats = {"skipped": 0, "rebuilt": 0, "followers": 0}


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


class _Watch:
    """Document observer feeding the ledgers. Never raises."""

    def slotChangedObject(self, obj, prop):
        try:
            doc = obj.Document
            if doc.Restoring:
                return
            if doc.Transacting:
                if prop == "Shape":
                    ledger(doc.Name).shape_restored(obj.Name)
                return
            if not doc.HasPendingTransaction and prop not in NOT_GEOMETRY:
                ledger(doc.Name).outside_change()
                if _DEBUG:
                    print("[SciForge] undo ledger: outside change %s.%s" % (obj.Name, prop), flush=True)
        except Exception:
            pass

    def slotCreatedObject(self, obj):
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
            if _DEBUG:
                print("[SciForge] undo ledger: open %s clean=%s" % (_name, _clean(doc)), flush=True)
            ledger(doc.Name).opened(_clean(doc))
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
    """[(name, has a Shape, in error)] of the objects not up to date."""
    out = []
    for obj in doc.Objects:
        state = obj.State
        if "Touched" in state or "Invalid" in state or "Error" in state:
            out.append(
                (obj.Name, "Shape" in obj.PropertiesList, "Invalid" in state or "Error" in state)
            )
    return out


def _dependents(doc, names):
    """The objects followers() picks among everything built on the objects `names`."""
    found = []
    for name in names:
        obj = doc.getObject(name)
        if obj is None:
            continue
        for dep in obj.InListRecursive:
            if dep.Document is doc and dep not in found:
                found.append(dep)
    keep = followers(names, [(o.Name, "Shape" in o.PropertiesList) for o in found])
    return [doc.getObject(name) for name in keep if doc.getObject(name) is not None]


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
        after = _dependents(doc, [name for name, _has_shape, _broken in stale])
        for name, _has_shape, _broken in stale:
            obj = doc.getObject(name)
            if obj is not None:
                obj.purgeTouched()
        led.decision = None  # once
        stats["skipped"] += 1
        if after:
            # (the design is as built, but a drawing of it is not: recompute those only)
            for obj in after:
                obj.touch()
            doc.recompute(after)
            stats["followers"] += len(after)
            _info("after Undo / Redo, %s: recomputed %s" % (doc.Label, ", ".join(o.Name for o in after)))
        return True
    except Exception:
        stats["rebuilt"] += 1
        return False
