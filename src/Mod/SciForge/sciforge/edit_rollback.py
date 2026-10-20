# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion: editing a step rolls the history marker to it while its dialog is open, and back
afterwards (Autodesk University "Under the Hood of Fusion 360": the later features are greyed
out and not computed; everything is computed on the way forward when the edit ends).

The design is shown as it is at that step, and the steps after it wait instead of being
rebuilt on every preview (preview.hold: a dialog's previews rebuild only what is before the
marker). Neither roll is something to undo: the edit itself is the undo step.
taskui.edit_object (the timeline, the browser, Edit Feature) calls roll_to() and back_later().
"""

from . import timeline_core as core
from . import timeline_ops as ops
from . import warn


def roll_to(obj):
    """Put the marker right after ``obj`` (a step of the timeline). Returns what back_later()
    needs ((marker before, marker while editing)), or None when the marker stays."""
    try:
        doc = obj.Document
        timeline = ops.timeline(doc, deps=False)
        item = timeline.find(obj.Name)
        if item is None:
            return None
        tips, note = core.marker_for_slot(timeline, item.index + 1)
        if tips is None and (note or "") == (timeline.before or ""):
            return None  # the marker is there already
        before = (core.active_count(timeline), timeline.before)
        ops.set_marker_untracked(doc, tips, note)
        now = ops.timeline(doc, deps=False)
        return before, (core.active_count(now), now.before)
    except Exception as exc:
        warn("could not roll the timeline to %s: %s" % (getattr(obj, "Label", obj), exc))
        return None


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
