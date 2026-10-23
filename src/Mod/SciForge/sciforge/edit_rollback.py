# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion: editing a step rolls the history marker to it while its dialog is open, and back
afterwards (Autodesk University "Under the Hood of Fusion 360": the later features are greyed
out and not computed; everything is computed on the way forward when the edit ends).

The design is shown as it is at that step, and the steps after it wait instead of being
rebuilt on every preview (preview.hold: a dialog's previews rebuild only what is before the
marker).

The roll is part of the edit's own undo step: taskui.edit_object asks for it (request()), the
SciForge dialog rolls the marker once its undo step is open (take(), from taskui.Panel) and
puts it back inside that step when it closes with OK (restore(), from end_transaction);
Cancel aborts the step and the roll with it. Rolled outside the step, an edit that replaces
the step it edits (Fillet becoming a selection-set fillet, Draft switching kinds) moved the
marker in the step, and Ctrl+Z left the design rolled back to the edited step.
"""

from . import timeline_core as core
from . import timeline_ops as ops
from . import warn

_PENDING = {}  # document name -> name of the step whose dialog is about to open
_ACTIVE = {}  # document name -> (solid steps before the marker, marker note) to go back to


def request(obj):
    """The next SciForge dialog of obj's document edits ``obj``: roll to it (take())."""
    try:
        _PENDING[obj.Document.Name] = obj.Name
    except Exception:
        pass


def unclaimed(doc):
    """Forget a request no SciForge dialog took (FreeCAD's own editor, a sketch)."""
    try:
        return _PENDING.pop(doc.Name, None)
    except Exception:
        return None


def take(doc):
    """A SciForge dialog opened its undo step: roll the marker to the step it edits."""
    try:
        name = _PENDING.pop(doc.Name, None)
    except Exception:
        return
    obj = doc.getObject(name) if name else None
    if obj is None:
        return
    back = roll_to(obj)
    if back is not None:
        _ACTIVE[doc.Name] = back[0]


def restore(doc):
    """The dialog closes with OK: the marker goes back where it was, in its undo step."""
    try:
        before = _ACTIVE.pop(doc.Name, None)
    except Exception:
        return
    if before is None:
        return
    try:
        timeline = ops.timeline(doc, deps=False)
        count, note = before
        ops.set_marker_untracked(doc, core.tips_for_count(timeline, count), note)
    except Exception as exc:
        warn("could not roll the timeline back after the edit: %s" % exc)


def drop(doc):
    """The dialog was cancelled: the aborted undo step took the roll back already."""
    try:
        _ACTIVE.pop(doc.Name, None)
    except Exception:
        pass


def roll_to(obj):
    """Put the marker right after ``obj`` (a step of the timeline). Returns ((marker
    before), (marker now)), or None when the marker stays."""
    try:
        doc = obj.Document
        timeline = ops.timeline(doc, deps=False)
        item = timeline.find(obj.Name)
        if item is None:
            return None
        index = item.index
        for other in _companions(obj):
            found = timeline.find(other.Name)
            if found is not None:
                index = max(index, found.index)
        tips, note = core.marker_for_slot(timeline, index + 1)
        if tips is None and (note or "") == (timeline.before or ""):
            return None  # the marker is there already
        before = (core.active_count(timeline), timeline.before)
        ops.set_marker_untracked(doc, tips, note)
        now = ops.timeline(doc, deps=False)
        return before, (core.active_count(now), now.before)
    except Exception as exc:
        warn("could not roll the timeline to %s: %s" % (getattr(obj, "Label", obj), exc))
        return None


def _companions(obj):
    """Steps the dialog of ``obj`` edits with it (a hardware part's Hole step): the marker
    goes after them too."""
    try:
        from . import hardware

        if hardware.is_hardware(obj):
            own = hardware.hole_of(obj)
            return [own] if own is not None else []
    except Exception:
        pass
    return []


def roll_forward(obj):
    """A step after the marker is about to be edited: roll forward to it before its editor
    opens, outside any undo step (a sketch is opened as it is at that point); back_later()
    puts the marker back. Returns back_later()'s arguments, or None."""
    try:
        item = ops.timeline(obj.Document, deps=False).find(obj.Name)
    except Exception:
        return None
    if item is None or item.state != "rolled_back":
        return None
    return roll_to(obj)


def back_later(doc_name, before, during, interval=150):
    """Once nothing is edited any more, put the marker back where it was (unless the user
    moved it meanwhile): the steps after the edited one are rebuilt then."""
    from . import timeline_ui
    from .compat import QtCore

    timer = QtCore.QTimer()
    timer.setInterval(interval)
    _TIMERS.append(timer)

    def stop():
        timer.stop()
        if timer in _TIMERS:
            _TIMERS.remove(timer)

    def check():
        try:
            if timeline_ui._command_open():
                return
            stop()
            import FreeCAD as App

            if doc_name not in App.listDocuments():
                return
            doc = App.getDocument(doc_name)
            timeline = ops.timeline(doc, deps=False)
            if (core.active_count(timeline), timeline.before) != during:
                return  # the user rolled the marker himself
            count, note = before
            ops.set_marker_untracked(doc, core.tips_for_count(timeline, count), note)
            bar = timeline_ui.widget()
            if bar is not None:
                bar.refresh(force=True)
        except Exception as exc:
            stop()
            warn("timeline: %s" % exc)

    timer.timeout.connect(check)
    timer.start()


_TIMERS = []  # running back_later() timers (a timer without a reference would be lost)
