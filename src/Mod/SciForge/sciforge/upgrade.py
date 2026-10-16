# SPDX-License-Identifier: LGPL-2.1-or-later
"""Steps saved by an older SciForge, rebuilt with today's code when the design is opened.

FreeCAD keeps the shapes stored in a file and recomputes nothing when it opens one, so a coil
or a pipe saved before the primitives QA fixes of 2026-10-11 kept its old (wrong) shape until
it was edited once: a coil with a negative angle was its mirror image (it went down through
its plane instead of narrowing as it rose), a tapered coil on a raised face drifted, a hollow
pipe round a closed path was a solid ring. Their hidden section objects notice it while the
file is read (a property the fixes added is missing, or the old path link is still set) and
mark themselves; once the file is open the step is rebuilt from its own saved options (the
same as editing it and pressing OK) and a log line says so. The design then shows as
changed, so a save keeps the new shape.

A pattern or mirror of bodies saved before 2026-10-16 linked the body itself (its copies
followed every later Move or edit of the original): while the file is read it is linked to
the body's step right before it (pattern._upgrade) and marks itself ("body_pattern"); once
the file is open its copies are computed again from that step.
"""

import FreeCAD as App

from . import log, warn

_OLD = {}  # document name -> [(kind, section name)]
WHY = {
    "coil": "a coil with a negative angle was its mirror image, a tapered coil on a raised "
    "face drifted",
    "pipe": "a hollow pipe round a closed path was a solid ring",
    "body_pattern": "a pattern or mirror of bodies copied the body as it is now, so a Move or "
    "an edit of the original after the pattern reached every copy",
}


def mark(section, kind):
    """`section` (a CoilSection / PipeSection being read from a file) was saved by an older
    SciForge: rebuild its step once the file is open."""
    try:
        name = section.Document.Name
    except Exception:
        return
    entries = _OLD.setdefault(name, [])
    if (kind, section.Name) not in entries:
        entries.append((kind, section.Name))
    if App.GuiUp and len(entries) == 1:
        _later(name)


def _later(name, tries=0):
    from .compat import QtCore

    def run():
        try:
            if name not in App.listDocuments():
                _OLD.pop(name, None)
                return
            doc = App.getDocument(name)
            if getattr(doc, "Restoring", False) or getattr(doc, "Recomputing", False):
                if tries < 100:
                    _later(name, tries + 1)
                return
            after_open(doc)
        except Exception as exc:
            warn("rebuilding steps of an older SciForge: %s" % exc)

    QtCore.QTimer.singleShot(0 if tries == 0 else 100, run)


def _owner(doc, section, kind):
    from . import coil, pipe, primitives

    module = coil if kind == "coil" else pipe
    is_kind = coil.is_coil if kind == "coil" else pipe.is_pipe
    for obj in doc.Objects:
        try:
            if is_kind(obj) and section.Name in primitives.load_meta(obj, module.META).get(
                "helpers", []
            ):
                return obj
        except Exception:
            continue
    return None


def after_open(doc):
    """Rebuild the steps marked while `doc` was read. Returns the rebuilt steps."""
    from . import coil, pipe, timeline_ops

    done = []
    hide_copies = False
    for kind, name in _OLD.pop(doc.Name, []):
        if kind == "copy_view":
            hide_copies = True  # a pattern of bodies' copy feature (pattern.BodyCopyFeature)
            continue
        if kind == "body_pattern":
            # pattern.py linked it to the body's step before it while the file was read; the
            # copies are computed again from that step (no rebuild needed)
            step = doc.getObject(name)
            if step is not None and step not in done:
                step.touch()
                done.append(step)
                log(
                    "%s was saved by an older SciForge (%s): its copies are computed again"
                    % (step.Label, WHY[kind])
                )
            continue
        section = doc.getObject(name)
        feature = _owner(doc, section, kind) if section is not None else None
        if feature is None or feature in done:
            continue
        label = feature.Label
        module = coil if kind == "coil" else pipe
        try:
            if not module.is_ours(feature):
                continue
            done.append(module.update(feature))
            log(
                "%s was saved by an older SciForge (before the fixes of 2026-10-11: %s): "
                "rebuilt with today's %s" % (label, WHY[kind], kind)
            )
        except Exception as exc:
            warn("%s, saved by an older SciForge, could not be rebuilt: %s" % (label, exc))
    if done:
        timeline_ops.recompute(doc)
    if hide_copies and App.GuiUp:
        # FreeCAD shows the copy features of patterns of bodies while it opens a design (a
        # click on a copy then picked that hidden feature, not the copy's body): hide them,
        # now and once more a moment later
        try:
            from . import pattern_ui

            pattern_ui.keep_copy_features_hidden(doc)
            pattern_ui.keep_hidden_later(doc.Name)
        except Exception as exc:
            warn("the copies of a pattern of bodies could not be hidden: %s" % exc)
    return done
