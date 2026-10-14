# SPDX-License-Identifier: LGPL-2.1-or-later
"""Picked edges, faces and corners of the part kept through edits, saving and reopening.

A fillet, chamfer, shell, draft, hole, thread, pattern, split, a sketch on a face... names
what it picked on the part ("Edge4", "Face6"). FreeCAD 1.1 marks such a name lost after some
edits of an earlier step ("?Edge4", "missing element reference"; seen: a taper added to the
extrude under a fillet turned the fillet red, after a save and reopen too). Fusion keeps the
step on its edge. So does SciForge: where each picked element is gets remembered after every
good compute of the step (the hidden property SciForgePicks, saved in the file), and the
moment FreeCAD marks a name lost, the step is pointed at the element found again there
(curves.refind: the same kind of edge or face, facing about the same way, nearest to where
it was relative to the part's bounding box, within a quarter of its size), before the step
itself is computed in that same recompute. Only a name lost by that recompute is looked
for: a step whose edge was really removed (its step deleted or suppressed: the timeline
decides those, picks are paused meanwhile) stays red, like in Fusion.

Steps that remember their picks in their own code (Sweep, Loft, Press Pull, the
constructions: curves.MEMORY) are left to it. No GUI code: the golden-model builder installs
the watcher too.
"""

import FreeCAD as App

from . import curves, log

PICKS = "SciForgePicks"
_PAUSED = [0]  # > 0 while a timeline operation that keeps references itself runs
CHAIN = {"BaseFeature", "_Body", "Origin", "Tip", "Group", "ExpressionEngine"}
# Properties that change on every recompute and never hold picks: skipped at once.
NOT_PICKS = {"Shape", "Placement", "Label", "Label2", "Visibility", "State", PICKS}


class paused:
    """Context manager: the timeline's suppress, delete and move decide themselves which
    steps break (and put references back afterwards); nothing is found again meanwhile."""

    def __enter__(self):
        _PAUSED[0] += 1
        return self

    def __exit__(self, *exc):
        _PAUSED[0] -= 1
        return False


def _busy(doc):
    if _PAUSED[0] > 0:
        return True
    try:
        return bool(doc.Restoring or doc.Transacting)  # opening a file, undo / redo
    except Exception:
        return True


def _in_body(obj):
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        return False
    return parent is not None and parent.TypeId == "PartDesign::Body"


def _link_props(obj):
    """Link properties of `obj` that can name elements of other objects."""
    props = []
    for prop in obj.PropertiesList:
        if prop in CHAIN or prop in NOT_PICKS:
            continue
        try:
            kind = obj.getTypeIdOfProperty(prop)
        except Exception:
            continue
        if kind.startswith("App::PropertyLinkSub"):
            props.append(prop)
    return props


def _picks(obj, prop):
    """[(linked object, element name as stored)] of the part elements `prop` names (not
    sketches' own curves: a sketch keeps its own names)."""
    out = []
    try:
        value = getattr(obj, prop)
    except Exception:
        return out
    for linked, subs in curves._items(value):
        if linked is None or curves.is_sketch(linked):
            continue
        for sub in subs:
            if curves._element(sub):
                out.append((linked, sub))
    return out


def _lost(picks):
    return any(
        sub.startswith("?") or not curves._exists(linked, curves._element(sub))
        for linked, sub in picks
    )


def _off(obj):
    """Suppressed (FreeCAD's Suppressed, or SciForge's for sketches): what it picked may be
    gone while it is off; the timeline puts its picks back when it is switched on again."""
    return getattr(obj, "Suppressed", False) is True or bool(
        getattr(obj, "SciForgeSuppressed", False)
    )


def watched(obj):
    """True for a step or sketch of a body whose picks this module keeps."""
    try:
        if not _in_body(obj) or curves.MEMORY in obj.PropertiesList or _off(obj):
            return False
        return obj.isDerivedFrom("PartDesign::Feature") or curves.is_sketch(obj)
    except Exception:
        return False


def remember(obj):
    """After a good compute: where the elements `obj` picked are now."""
    if not watched(obj):
        return
    state = list(getattr(obj, "State", []))
    if "Invalid" in state or "Error" in state:
        return
    props = [p for p in _link_props(obj) if _picks(obj, p)]
    if not props or any(_lost(_picks(obj, p)) for p in props):
        return  # nothing picked, or a pick is lost (its old place must stay remembered)
    curves.remember(obj, props, memory=PICKS)


def refind(obj, props=None):
    """Point `obj`'s lost picks at the elements found again; True if any changed."""
    if _PAUSED[0] > 0 or not watched(obj) or PICKS not in obj.PropertiesList:
        return False
    props = props or _link_props(obj)
    lost = [p for p in props if _lost(_picks(obj, p))]
    if not lost:
        return False
    changed = curves.refind(obj, lost, memory=PICKS)
    if changed:
        found = ", ".join("%s %s" % (n, new) for (n, _old), new in changed.items())
        log(
            "%s: FreeCAD lost the name of what it was built on; found again where it was (%s)"
            % (obj.Label, found)
        )
    return bool(changed)


class Keeper:
    """Document observer: remembers picks after each good compute and repairs a lost one
    as soon as the step that made it lost has been computed (before the step itself)."""

    def __init__(self):
        self._pending = set()  # (document, object, property) marked lost

    def slotChangedObject(self, obj, prop):
        if prop in NOT_PICKS:
            return
        try:
            if not obj.getTypeIdOfProperty(prop).startswith("App::PropertyLinkSub"):
                return
            if _busy(obj.Document) or PICKS not in obj.PropertiesList:
                return
            if _lost(_picks(obj, prop)):
                self._pending.add((obj.Document.Name, obj.Name, prop))
        except Exception:
            pass

    def slotRecomputedObject(self, obj):
        try:
            doc = obj.Document
            if self._pending:
                self._fix(doc, obj)
            remember(obj)
        except Exception as exc:
            from . import _remember

            _remember("info", "picks: %s" % exc)

    def slotRecomputedDocument(self, doc):
        try:
            self._pending = {p for p in self._pending if p[0] != doc.Name}
        except Exception:
            pass

    slotDeletedDocument = slotRecomputedDocument

    def _fix(self, doc, just_computed=None):
        mine = [p for p in self._pending if p[0] == doc.Name]
        for item in mine:
            self._pending.discard(item)
            target = doc.getObject(item[1])
            if target is not None and target is not just_computed:
                refind(target, [item[2]])


_keeper = {"observer": None}


def install():
    """Watch every document (once)."""
    if _keeper["observer"] is None:
        _keeper["observer"] = Keeper()
        App.addDocumentObserver(_keeper["observer"])
