# SPDX-License-Identifier: LGPL-2.1-or-later
"""What the timeline does to the document: roll the history marker, suppress,
delete, reorder and rename steps. No Qt here, so the golden-model builder and
headless tests run exactly the code behind the timeline's buttons and menus.

Every operation is one undo step. A step that breaks because of what the user did
(suppressing what it was built on, deleting its sketch) is shown red in the
timeline with the reason, like Fusion, instead of FreeCAD printing errors in the
Report view: the recomputes started here run with the Report view's error output
muted, and the timeline reads every step's state afterwards.
"""
import json

import FreeCAD as App

from . import timeline_core as core

# Console observers that show messages to the user (FreeCAD's Report view, its
# notification pop-ups and the status bar).
QUIET_OBSERVERS = ("ReportOutput", "NotificationAreaObserver", "StatusBar")
QUIET_TYPES = ("Err", "Wrn", "Critical")

# Steps that are never in the timeline (origin, parameters, groups...).
NOT_STEPS = {
    "PartDesign::Body",
    "App::Origin",
    "App::Line",
    "App::Plane",
    "App::Point",
    "App::VarSet",
    "App::Part",
    "App::DocumentObjectGroup",
    "App::DocumentObjectGroupPython",
    "Spreadsheet::Sheet",
    "App::Link",
    "App::LinkGroup",
    "App::FeatureTest",
}
# Link properties that hold the body's history chain: PartDesign re-links them
# itself when steps move, so they are not "uses" for reordering.
CHAIN_PROPS = {"BaseFeature", "_Body", "Origin", "Tip", "Group"}
RANK = "SciForgeRank"  # creation-order key after a move between bodies
SUPPRESSED = "SciForgeSuppressed"  # sketches/datums: FreeCAD cannot suppress them
SUPPRESS_INFO = "SciForgeSuppressInfo"
WARNING = "SciForgeWarning"
ROLE = "SciForgeRole"  # set on helpers made for a step (extrude.py, revolve.py, hole.py)
GROUP = "SciForgeGroup"  # timeline group id of a step
GROUP_NAME = "SciForgeGroupName"
ROLLED_HIDDEN = "SciForgeRolledHidden"  # a shown sketch/plane hidden by the marker
MARKER_NOTE = "SciForge.MarkerBefore"  # Document.Meta: the step right after the marker


class TimelineError(RuntimeError):
    """An operation that cannot be done; the message says why (shown to the user)."""


# -- quiet recompute ---------------------------------------------------------------
class quiet:
    """Context manager: FreeCAD's error/warning output to the Report view, its
    notification pop-ups and the status bar is off inside (nesting is fine)."""

    depth = 0
    saved = []

    def __enter__(self):
        if quiet.depth == 0:
            quiet.saved = []
            for observer in QUIET_OBSERVERS:
                for kind in QUIET_TYPES:
                    try:
                        before = App.Console.GetStatus(observer, kind)
                    except Exception:
                        continue
                    if before is None:
                        continue
                    try:
                        App.Console.SetStatus(observer, kind, False)
                        quiet.saved.append((observer, kind, bool(before)))
                    except Exception:
                        pass
        quiet.depth += 1
        return self

    def __exit__(self, *exc):
        quiet.depth -= 1
        if quiet.depth == 0:
            for observer, kind, before in quiet.saved:
                try:
                    App.Console.SetStatus(observer, kind, before)
                except Exception:
                    pass
            quiet.saved = []
        return False


_settling = set()  # documents whose recompute is SciForge's own (already quiet and settled)


def recompute(doc):
    """doc.recompute() the Fusion way: quiet, then settle() (failed steps add nothing,
    steps whose base changed keep their edges)."""
    _settling.add(doc.Name)
    try:
        with quiet():
            doc.recompute()
            settle(doc)
    finally:
        _settling.discard(doc.Name)


def settle(doc):
    """What Fusion shows after any recompute, whoever started it (a feature dialog, an
    undo, the timeline):

    - a fillet/chamfer/shell/Press Pull whose base step changed (a step added at the
      rolled-back marker, a step before it deleted) keeps its edges/faces: FreeCAD keeps
      their old names on the new base, which are other edges or none (red);
    - a step in error adds nothing and the steps after it build on what came before it;
    - a body with nothing left shows nothing."""
    _settling.add(doc.Name)
    try:
        with quiet():
            if repair_references(doc):
                doc.recompute()
            _pass_through_failures(doc)
            _clear_empty_bodies(doc)
            remember_references(doc)
    finally:
        _settling.discard(doc.Name)


def _is_solid_step(obj):
    """A PartDesign feature that changes the solid (datums and sketches do not)."""
    return "BaseFeature" in obj.PropertiesList


def _pass_through_failures(doc):
    """Fusion: a step in error adds nothing, and the steps after it still build on
    what came before it. FreeCAD keeps a failed step's old shape (the 3D view would
    still show it) and skips everything after it. So a failed step passes its base
    shape through, and the steps after it are computed again on that."""
    import Part

    for body in bodies(doc):
        failed = False
        for obj in body.Group:
            if not _is_solid_step(obj) or is_suppressed(obj):
                continue
            state = list(obj.State)
            if "Invalid" in state or "Error" in state:
                base = getattr(obj, "BaseFeature", None)
                try:
                    if base is not None and not base.Shape.isNull():
                        obj.Shape = base.Shape.copy()
                    else:
                        obj.Shape = Part.Shape()
                except Exception:
                    pass
                failed = True
            elif failed:  # FreeCAD skipped it: build it again on the passed-through shape
                try:
                    obj.touch()
                    obj.recompute()
                except Exception:
                    pass
                if "Invalid" in list(obj.State):
                    base = getattr(obj, "BaseFeature", None)
                    try:
                        obj.Shape = base.Shape.copy() if base is not None else Part.Shape()
                    except Exception:
                        pass
        if failed:
            try:
                body.recompute()
            except Exception:
                pass


def _clear_empty_bodies(doc):
    """A body whose last step has no solid (everything suppressed) fails in FreeCAD
    and keeps showing its old shape; Fusion shows nothing. Empty it."""
    for body in bodies(doc):
        tip = getattr(body, "Tip", None)
        try:
            if tip is not None and tip.Shape.isNull() and not body.Shape.isNull():
                import Part

                body.Shape = Part.Shape()
        except Exception:
            pass


class RecomputeGuard:
    """Document observer.

    - While a design has steps in error or suppressed (shown red or greyed in the
      timeline), or a step whose base just changed (it is repaired right after),
      FreeCAD would print errors on every recompute, flooding the Report view: mute it
      during those recomputes only.
    - After every recompute (a feature dialog's preview, an undo...), settle() the
      design, deferred with ``defer`` (the GUI passes a Qt timer): nothing may change
      the document inside FreeCAD's own recompute signal."""

    def __init__(self, defer=None):
        self._active = {}
        self.defer = defer
        self._pending = set()

    def slotBeforeRecomputeDocument(self, doc):
        try:
            if doc.Name in _settling or _has_known_problems(doc) or references_pending(doc):
                q = quiet()
                q.__enter__()
                self._active[doc.Name] = q
        except Exception:
            pass

    def slotRecomputedDocument(self, doc):
        q = self._active.pop(doc.Name, None)
        if q is not None:
            try:
                q.__exit__(None, None, None)
            except Exception:
                pass
        try:
            name = doc.Name
            if self.defer is None or name in _settling or name in self._pending:
                return
            self._pending.add(name)
            self.defer(lambda: self._settle(name))
        except Exception:
            pass

    def slotDeletedDocument(self, doc):
        try:
            forget(doc.Name)
        except Exception:
            pass

    def _settle(self, name):
        self._pending.discard(name)
        try:
            doc = App.getDocument(name)
        except Exception:
            return  # closed meanwhile
        try:
            if _recomputing(doc):  # a long recompute runs Qt timers (MEMORY): later
                self._pending.add(name)
                self.defer(lambda: self._settle(name), 100)
                return
            settle(doc)
        except Exception as exc:
            from . import _remember

            _remember("info", "timeline settle skipped: %s" % exc)


def _recomputing(doc):
    try:
        return bool(doc.Recomputing)
    except Exception:
        return False


def _has_known_problems(doc):
    for obj in doc.Objects:
        if getattr(obj, "Suppressed", False) is True or getattr(obj, SUPPRESSED, False):
            return True
        state = getattr(obj, "State", [])
        if "Invalid" in state or "Error" in state:
            return True
    return False


_guard = {"observer": None}


def install_guard(defer=None):
    if _guard["observer"] is None:
        _guard["observer"] = RecomputeGuard(defer)
        App.addDocumentObserver(_guard["observer"])
    elif defer is not None:
        _guard["observer"].defer = defer


def remove_guard():
    observer = _guard["observer"]
    _guard["observer"] = None
    if observer is not None:
        try:
            App.removeDocumentObserver(observer)
        except Exception:
            pass
        for q in list(observer._active.values()):
            q.__exit__(None, None, None)


# -- reading the document ------------------------------------------------------------
def type_key(obj):
    kind = getattr(obj, "SciForgeType", "")
    return "SciForge::" + kind if kind else obj.TypeId


def bodies(doc):
    return [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]


def body_of(obj):
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        return None
    if parent is not None and parent.TypeId == "PartDesign::Body":
        return parent
    return None


def is_helper(obj):
    """An object SciForge made for a step (an extrude's profile binder, a revolve's
    axis link, a Single Hole's sketch...): never a step of its own in Fusion."""
    return bool(getattr(obj, ROLE, "")) or getattr(obj, "SciForgeTimeline", True) is False


def _is_step(obj):
    if obj.TypeId in NOT_STEPS or is_helper(obj):
        return False
    kind = getattr(obj, "SciForgeType", "")
    if "Analysis" in kind or "Section" in kind:
        return False
    if obj.TypeId in core.KIND_BY_TYPEID or kind:
        return True
    try:
        return obj.isDerivedFrom("Part::Feature")
    except Exception:
        return False


def steps(doc):
    """[(object, body or None)] in each body's own order, then the rest."""
    result = []
    inside = set()
    for body in bodies(doc):
        for obj in body.Group:
            inside.add(obj.Name)
            if _is_step(obj):
                result.append((obj, body))
    for obj in doc.Objects:
        if obj.Name in inside or not _is_step(obj):
            continue
        if body_of(obj) is not None:
            continue  # in a body but not in its list (origin...)
        result.append((obj, None))
    return result


def _objects_in(value):
    """Document objects inside a link property value (any nesting)."""
    found = []
    if value is None:
        return found
    if hasattr(value, "TypeId") and hasattr(value, "Name"):
        return [value]
    if isinstance(value, (list, tuple)):
        for v in value:
            found += _objects_in(v)
    return found


_LINK_PROPS = {}


def _link_props(obj):
    """[(property, type)] of the link properties of an object (cached per type)."""
    props = obj.PropertiesList
    cache_key = (obj.TypeId, len(props), getattr(obj, "SciForgeType", ""))
    found = _LINK_PROPS.get(cache_key)
    if found is None:
        found = []
        for prop in props:
            try:
                kind = obj.getTypeIdOfProperty(prop)
            except Exception:
                continue
            if kind.startswith(("App::PropertyLink", "App::PropertyXLink")):
                found.append((prop, kind))
        _LINK_PROPS[cache_key] = found
    return found


def uses(obj):
    """Names of objects a step is built from, apart from its body's history chain:
    its sketch, the face/plane it sits on, the steps a pattern repeats, parameters
    in expressions... A step can never move before these."""
    names = set()
    linked = set()
    base = getattr(obj, "BaseFeature", None)
    for prop, _kind in _link_props(obj):
        try:
            value = getattr(obj, prop)
        except Exception:
            continue
        objs = _objects_in(value)
        linked.update(o.Name for o in objs)
        if prop in CHAIN_PROPS:
            continue
        if prop == "Base" and base is not None and objs and all(o is base for o in objs):
            continue  # a fillet/chamfer's edges live on the step before it
        if prop == "Faces" and base is not None and objs and all(o is base for o in objs):
            continue  # Press Pull: same
        names.update(o.Name for o in objs)
    try:
        for o in obj.OutList:  # expressions (=Sketch.Constraints.width, parameters)
            if o.Name not in linked:
                names.add(o.Name)
    except Exception:
        pass
    names.discard(obj.Name)
    return names


def problem(obj, broken_before=None):
    """("error"|"warning"|"", reason) for one step."""
    state = list(getattr(obj, "State", []))
    if "Invalid" in state or "Error" in state:
        try:
            text = obj.getStatusString()
        except Exception:
            text = ""
        return "error", _friendly(obj, text)
    note = getattr(obj, WARNING, "")
    if note:
        return "warning", note
    if obj.TypeId == "Sketcher::SketchObject":
        try:
            if obj.MalformedConstraints:
                return "warning", "The sketch has broken constraints."
            if obj.RedundantConstraints:
                return "warning", "The sketch has redundant constraints."
        except Exception:
            pass
    for prop, kind in _link_props(obj):
        if "Sub" not in kind or prop in CHAIN_PROPS:
            continue
        try:
            subs = _subs_of(getattr(obj, prop))
        except Exception:
            continue
        lost = [s for s in subs if s.startswith("?")]
        if lost:
            return "warning", "Lost a reference to %s." % ", ".join(s[1:] for s in lost)
    return "", ""


def _friendly(obj, text):
    """FreeCAD's reason in words a Fusion user knows."""
    text = _plain(text)
    low = text.lower()
    profile = getattr(obj, "Profile", None) if "Profile" in obj.PropertiesList else 0
    if profile is None or (isinstance(profile, tuple) and not profile):
        return "Its profile is gone (deleted?). Edit it and pick a new profile."
    if "edge link" in low or "face link" in low or "missing element" in low:
        return "Some edges or faces it was applied to no longer exist. Edit it and pick them again."
    if "base feature's toposhape is invalid" in low or "no base" in low:
        return "There is no solid before it to build on."
    if "multiple solids" in low:
        return "The result would be separate pieces; a body must stay one solid."
    if not text or text in ("Valid", "Touched"):
        return "This step could not be computed."
    return text


def _plain(text):
    """FreeCAD's messages without the C++ noise."""
    text = str(text).strip()
    for prefix in ("Exception: ", "<Exception> "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text


def _subs_of(value):
    subs = []
    if isinstance(value, tuple) and len(value) == 2 and hasattr(value[0], "Name"):
        part = value[1]
        if isinstance(part, str):
            return [part] if part else []
        return [s for s in part if isinstance(s, str) and s]
    if isinstance(value, (list, tuple)):
        for v in value:
            subs += _subs_of(v)
    return subs


def is_suppressed(obj):
    return bool(getattr(obj, "Suppressed", False)) or bool(getattr(obj, SUPPRESSED, False))


def _key(obj):
    rank = getattr(obj, RANK, None)
    if isinstance(rank, float) and rank > 0:
        return rank
    return float(obj.ID)


def snapshot(doc, deps=True):
    """(features, tips) for timeline_core.build(). ``deps`` (what each step uses) is
    only needed to reorder; the timeline's 0.4 s refresh leaves it out."""
    features = []
    for obj, body in steps(doc):
        off = is_suppressed(obj)
        # A suppressed step is off, not broken: FreeCAD's complaints about it (its face
        # went with what was suppressed) are not shown, like Fusion.
        kind, reason = ("", "") if off else problem(obj)
        features.append(
            {
                "name": obj.Name,
                "label": obj.Label,
                "type_id": type_key(obj),
                "body": body.Name if body is not None else None,
                "key": _key(obj),
                "created": float(obj.ID),
                "suppressed": off,
                "error": reason if kind == "error" else "",
                "warning": reason if kind == "warning" else "",
                "deps": sorted(uses(obj)) if deps else [],
                "group": getattr(obj, GROUP, "") or "",
                "group_name": getattr(obj, GROUP_NAME, "") or "",
            }
        )
    tips = {}
    for body in bodies(doc):
        tip = getattr(body, "Tip", None)
        tips[body.Name] = tip.Name if tip is not None else None
    return features, tips


def timeline(doc, deps=True):
    features, tips = snapshot(doc, deps)
    return core.build(features, tips, marker_note(doc))


def marker_note(doc):
    """The step right after the marker when it stands before a sketch/plane (see
    timeline_core), kept in the document so it is saved with it."""
    try:
        return doc.Meta.get(MARKER_NOTE, "")
    except Exception:
        return ""


def _set_marker_note(doc, name):
    try:
        meta = dict(doc.Meta)
        if name:
            meta[MARKER_NOTE] = name
        else:
            meta.pop(MARKER_NOTE, None)
        if meta != dict(doc.Meta):
            doc.Meta = meta
    except Exception:
        pass


# -- helpers for operations ------------------------------------------------------------
def _transaction(doc, title):
    if not doc.UndoMode:
        doc.UndoMode = 1  # headless documents: a refused move must be able to roll back
    doc.openTransaction(title)


def _set_tips(doc, tips):
    for body_name, tip_name in tips.items():
        body = doc.getObject(body_name)
        if body is None:
            continue
        tip = doc.getObject(tip_name) if tip_name else None
        current = getattr(body, "Tip", None)
        if current is not tip:
            body.Tip = tip
            _show_only_tip(body, tip)
    show_marker_state(doc)


def show_marker_state(doc):
    """In Fusion a sketch or construction plane after the history marker does not exist
    yet, so it is not drawn. Those that were shown are hidden while the marker is before
    them and shown again once it passes them."""
    if not App.GuiUp:
        return
    try:
        tl = timeline(doc, deps=False)
    except Exception:
        return
    for item in tl.items:
        if item.solid or item.body is None:
            continue
        obj = doc.getObject(item.name)
        if obj is None or obj.ViewObject is None:
            continue
        try:
            if item.state == "rolled_back":
                if obj.ViewObject.Visibility:
                    _add_prop(obj, "App::PropertyBool", ROLLED_HIDDEN, "Hidden by the marker")
                    setattr(obj, ROLLED_HIDDEN, True)
                    obj.ViewObject.Visibility = False
            elif getattr(obj, ROLLED_HIDDEN, False):
                setattr(obj, ROLLED_HIDDEN, False)
                if not is_suppressed(obj):
                    obj.ViewObject.Visibility = True
        except Exception:
            pass


def _show_only_tip(body, tip):
    """A PartDesign body is drawn through its Tip, but changing the Tip from Python does not
    hide the features after it or show the new Tip: after a marker roll the 3D view showed
    the wrong step, and a click on the part could land on a face of a rolled-back feature
    (a sketch attached there then failed). Show exactly the new Tip, like FreeCAD's own
    "Set tip" command does."""
    try:
        if not App.GuiUp:
            return
        for obj in body.Group:
            if not obj.isDerivedFrom("PartDesign::Feature") or obj.ViewObject is None:
                continue
            want = obj is tip
            if obj.ViewObject.Visibility != want:
                obj.ViewObject.Visibility = want
    except Exception:
        pass


def _add_prop(obj, kind, name, doc_text=""):
    if name not in obj.PropertiesList:
        # 4 = hidden, 16 = changing it does not mark the step for recompute
        obj.addProperty(kind, name, "SciForge", doc_text, 4 | 16)


def _errors(doc):
    return {
        obj.Name
        for obj, _body in steps(doc)
        if "Invalid" in list(getattr(obj, "State", [])) or "Error" in list(obj.State)
    }


def _label(doc, name):
    tl = timeline(doc)
    item = tl.find(name)
    return item.display if item is not None else name


# -- history marker --------------------------------------------------------------------
def roll(doc, tips, title="Roll History Marker", before=None):
    """Set the bodies' Tips (the history marker), one undo step; ``before``: the step
    right after the marker when it stands before a sketch/plane."""
    if not tips:
        if (before or "") == marker_note(doc):
            return False
        _set_marker_note(doc, before)  # only sketches/planes change sides: no recompute
        show_marker_state(doc)
        return True
    _transaction(doc, title)
    try:
        _set_marker_note(doc, before)
        _set_tips(doc, tips)
        recompute(doc)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    return True


def roll_to_end(doc):
    tl = timeline(doc)
    return roll(doc, core.tips_for_step(tl, "end"), "Roll History Marker to End")


def current_tips(doc):
    return {b.Name: (b.Tip.Name if b.Tip is not None else None) for b in bodies(doc)}


def set_marker_untracked(doc, tips, before=None):
    """Move the marker without an undo step: Fusion rolls to a step while it is edited
    and back afterwards, and neither is something to undo (the edit itself is)."""
    _set_marker_note(doc, before)
    if not tips:
        show_marker_state(doc)
        return False
    with quiet():
        _set_tips(doc, tips)
    recompute(doc)
    return True


# -- suppress --------------------------------------------------------------------------
def dependents(doc, names):
    """Steps that use any of ``names``, directly or through each other."""
    users = {}
    for obj, _body in steps(doc):
        for dep in uses(obj):
            users.setdefault(dep, set()).add(obj.Name)
    found = set()
    todo = list(names)
    while todo:
        n = todo.pop()
        for user in users.get(n, ()):
            if user not in found and user not in names:
                found.add(user)
                todo.append(user)
    return found


def _link_snapshot(doc):
    """{object: {property: (kind, [[linked name, [subs]], ...])}} of every reference to
    edges/faces, so references FreeCAD marks lost while a step is off come back."""
    snap = {}
    for obj, _body in steps(doc):
        for prop, kind in _link_props(obj):
            if "Sub" not in kind or prop in CHAIN_PROPS:
                continue
            try:
                value = getattr(obj, prop)
            except Exception:
                continue
            entries = _entries(value)
            if entries and not any(s.startswith("?") for _o, subs in entries for s in subs):
                snap.setdefault(obj.Name, {})[prop] = (kind, entries)
    return snap


def _entries(value):
    if value is None:
        return []
    if isinstance(value, tuple) and len(value) == 2 and hasattr(value[0], "Name"):
        subs = value[1]
        subs = [subs] if isinstance(subs, str) else list(subs)
        return [[value[0].Name, [s for s in subs if s]]]
    entries = []
    if isinstance(value, list):
        for v in value:
            entries += _entries(v)
    return [e for e in entries if e[1]]


def _restore_links(doc, snap):
    """Put back references that went missing ('?Edge2'); True if any was restored."""
    restored = False
    for obj_name, props in snap.items():
        obj = doc.getObject(obj_name)
        if obj is None:
            continue
        for prop, (kind, entries) in props.items():
            try:
                current = _entries(getattr(obj, prop))
            except Exception:
                continue
            if not any(s.startswith("?") for _o, subs in current for s in subs):
                continue
            targets = [(doc.getObject(n), subs) for n, subs in entries]
            if any(t is None for t, _s in targets):
                continue
            try:
                if "SubList" in kind:
                    setattr(obj, prop, [(t, tuple(s)) for t, s in targets])
                else:
                    setattr(obj, prop, (targets[0][0], targets[0][1]))
                restored = True
            except Exception:
                pass
    return restored


def can_suppress(obj):
    return obj is not None and obj.TypeId not in NOT_STEPS


def _set_suppressed(obj, on):
    if "Suppressed" in obj.PropertiesList:
        if bool(obj.Suppressed) != on:
            obj.Suppressed = on
        return
    # Sketches and construction geometry: FreeCAD has no suppression for them. Off
    # means hidden and frozen where it is (its plane may be gone), like Fusion.
    _add_prop(obj, "App::PropertyBool", SUPPRESSED, "Suppressed in the timeline")
    _add_prop(obj, "App::PropertyString", SUPPRESS_INFO + "Own", "State before suppressing")
    if on and not getattr(obj, SUPPRESSED):
        state = {"visible": None, "mode": getattr(obj, "MapMode", None)}
        if App.GuiUp and obj.ViewObject is not None:
            state["visible"] = bool(obj.ViewObject.Visibility)
            obj.ViewObject.Visibility = False
        setattr(obj, SUPPRESS_INFO + "Own", json.dumps(state))
        if state["mode"] not in (None, "Deactivated"):
            obj.MapMode = "Deactivated"
        setattr(obj, SUPPRESSED, True)
    elif not on and getattr(obj, SUPPRESSED):
        try:
            state = json.loads(getattr(obj, SUPPRESS_INFO + "Own") or "{}")
        except ValueError:
            state = {}
        if state.get("mode") not in (None, "Deactivated"):
            obj.MapMode = state["mode"]
        if App.GuiUp and obj.ViewObject is not None and state.get("visible"):
            obj.ViewObject.Visibility = True
        setattr(obj, SUPPRESSED, False)
        try:
            obj.touch()
        except Exception:
            pass


def _names(names):
    return [names] if isinstance(names, str) else list(names)


def suppress(doc, names):
    """Suppress steps and, like Fusion, the steps that depend on them, as one undo
    step. Returns the names suppressed with them."""
    names = [n for n in _names(names) if doc.getObject(n) is not None]
    for n in names:
        if not can_suppress(doc.getObject(n)):
            raise TimelineError("This step cannot be suppressed.")
    names = [n for n in names if not is_suppressed(doc.getObject(n))]
    if not names:
        return []
    links = _link_snapshot(doc)
    broken_before = _errors(doc)
    title = ", ".join(_label(doc, n) for n in names[:3])
    _transaction(doc, "Suppress %s" % title)
    try:
        group = set(names) | dependents(doc, names)
        with quiet():
            for n in group:
                _set_suppressed(doc.getObject(n), True)
        recompute(doc)
        # Steps that only break now (their edges were made by it) go off too.
        for _round in range(6):
            newly = (_errors(doc) - broken_before) - group
            newly = {n for n in newly if not is_suppressed(doc.getObject(n))}
            if not newly:
                break
            more = newly | dependents(doc, newly)
            with quiet():
                for n in more - group:
                    _set_suppressed(doc.getObject(n), True)
            group |= more
            recompute(doc)
        info = json.dumps({"with": sorted(group - set(names)), "links": links})
        for n in names:
            obj = doc.getObject(n)
            _add_prop(obj, "App::PropertyString", SUPPRESS_INFO, "Suppressed together with this")
            setattr(obj, SUPPRESS_INFO, info)
    except Exception:
        doc.abortTransaction()
        recompute(doc)
        raise
    doc.commitTransaction()
    return sorted(group - set(names))


def unsuppress(doc, names):
    """Turn suppressed steps back on, with the steps that went off with them."""
    names = [n for n in _names(names) if doc.getObject(n) is not None]
    names = [n for n in names if is_suppressed(doc.getObject(n))]
    if not names:
        return []
    group, links = list(names), {}
    for n in names:
        try:
            info = json.loads(getattr(doc.getObject(n), SUPPRESS_INFO, "") or "{}")
        except ValueError:
            info = {}
        group += [m for m in info.get("with", []) if m not in group and doc.getObject(m)]
        for k, props in info.get("links", {}).items():
            links.setdefault(k, {}).update({p: tuple(v) for p, v in props.items()})
    title = ", ".join(_label(doc, n) for n in names[:3])
    _transaction(doc, "Unsuppress %s" % title)
    try:
        # Solids first: a sketch put back on its face before that face exists again
        # made FreeCAD print "subshape not found" (Report view and a pop-up balloon).
        objs = [doc.getObject(n) for n in group]
        with quiet():
            for obj in objs:
                if "Suppressed" in obj.PropertiesList:
                    _set_suppressed(obj, False)
        recompute(doc)
        if _restore_links(doc, links):
            recompute(doc)
        with quiet():
            for obj in objs:
                if "Suppressed" not in obj.PropertiesList:
                    _set_suppressed(obj, False)
        recompute(doc)
        for n in names:
            obj = doc.getObject(n)
            if SUPPRESS_INFO in obj.PropertiesList:
                setattr(obj, SUPPRESS_INFO, "")
    except Exception:
        doc.abortTransaction()
        recompute(doc)
        raise
    doc.commitTransaction()
    return [n for n in group if n not in names]


def toggle_suppress(doc, name):
    obj = doc.getObject(name)
    if obj is not None and is_suppressed(obj):
        return unsuppress(doc, name)
    return suppress(doc, name)


# -- delete ------------------------------------------------------------------------------
def _attached_to(obj, gone):
    support = getattr(obj, "AttachmentSupport", None)
    if not support:
        return False
    return any(o.Name in gone for o in _objects_in(support))


def delete(doc, names):
    """Delete steps, one undo step. Later steps keep working where possible: the
    body's history is re-linked around the gap, a sketch that sat on a deleted face
    stays where it was (with a warning), the sketch of a deleted extrude shows again."""
    names = [n for n in names if doc.getObject(n) is not None]
    if not names:
        return False
    gone = set(names)
    tl = timeline(doc)
    at_end = tl.at_end
    title = ", ".join(_label(doc, n) for n in names[:3])
    remember_references(doc)  # the steps after the gap keep their edges (settle)
    _transaction(doc, "Delete %s" % title)
    try:
        for obj, _body in steps(doc):
            if obj.Name in gone or not _attached_to(obj, gone):
                continue
            mode = getattr(obj, "MapMode", None)
            if mode and mode != "Deactivated":
                obj.MapMode = "Deactivated"  # keeps its current placement
            _add_prop(obj, "App::PropertyString", WARNING, "Why the timeline shows a warning")
            setattr(
                obj,
                WARNING,
                "Lost the face or plane it was on (deleted); it stays where it was.",
            )
        order = [n for n in tl.names() if n in gone]
        order += [n for n in names if n not in order]
        helpers = _helpers_of(doc, order, gone)
        for n in reversed(order):
            obj = doc.getObject(n)
            if obj is None:
                continue
            _show_profile_again(doc, obj, gone)
            body = body_of(obj)
            if body is not None and obj in body.Group:
                body.removeObject(obj)
            doc.removeObject(n)
        for obj in helpers:  # nothing uses them any more (they were never steps)
            if doc.getObject(obj.Name) is None:
                continue
            body = body_of(obj)
            if body is not None and obj in body.Group:
                body.removeObject(obj)
            doc.removeObject(obj.Name)
        if at_end:
            after = timeline(doc)
            _set_marker_note(doc, None)
            _set_tips(doc, core.tips_for_count(after, len(after.items)))
        recompute(doc)
    except Exception:
        doc.abortTransaction()
        recompute(doc)
        raise
    doc.commitTransaction()
    return True


def delete_bodies(doc, names):
    """Delete bodies with everything in them (Fusion: Delete on a body). Sketches of
    other bodies that sat on their faces stay where they were, with a warning."""
    targets = [doc.getObject(n) for n in names]
    targets = [b for b in targets if b is not None and b.TypeId == "PartDesign::Body"]
    if not targets:
        return False
    gone = set()
    for body in targets:
        gone.add(body.Name)
        gone.update(o.Name for o in body.Group)
    _transaction(doc, "Delete %s" % ", ".join(b.Label for b in targets[:3]))
    try:
        for obj, _body in steps(doc):
            if obj.Name in gone or not _attached_to(obj, gone):
                continue
            if getattr(obj, "MapMode", None) not in (None, "Deactivated"):
                obj.MapMode = "Deactivated"
            _add_prop(obj, "App::PropertyString", WARNING, "Why the timeline shows a warning")
            setattr(
                obj, WARNING, "Lost the face or plane it was on (deleted); it stays where it was."
            )
        for body in targets:
            for obj in reversed(list(body.Group)):
                if doc.getObject(obj.Name) is not None:
                    body.removeObject(obj)
                    doc.removeObject(obj.Name)
            doc.removeObject(body.Name)
        recompute(doc)
    except Exception:
        doc.abortTransaction()
        recompute(doc)
        raise
    doc.commitTransaction()
    return True


def profile_sketch(obj):
    """The sketch a feature was made from (Edit Profile Sketch), or None."""
    for prop in ("Profile", "Sketch"):
        value = getattr(obj, prop, None) if prop in obj.PropertiesList else None
        for o in _objects_in(value):
            if o.TypeId == "Sketcher::SketchObject":
                return o
    return None


def _helpers_of(doc, names, gone):
    """Helpers made for the steps ``names`` that nothing else uses."""
    found = []
    for n in names:
        obj = doc.getObject(n)
        if obj is None:
            continue
        for o in obj.OutList:
            if not is_helper(o) or o.Name in gone or o in found:
                continue
            users = [u for u in o.InList if u.TypeId not in NOT_STEPS and u.Name not in gone]
            if not users:
                found.append(o)
    return found


def _show_profile_again(doc, obj, gone):
    if not App.GuiUp:
        return
    sketch = profile_sketch(obj)
    if sketch is None or sketch.Name in gone or sketch.ViewObject is None or is_helper(sketch):
        return
    others = [
        o
        for o, _b in steps(doc)
        if o.Name not in gone and o is not obj and profile_sketch(o) is sketch
    ]
    if not others:
        sketch.ViewObject.Visibility = True


# -- reorder -----------------------------------------------------------------------------
def plan(doc, name, slot):
    return core.plan_move(timeline(doc), name, slot)


def move(doc, name, slot):
    """Move a step to ``slot`` of the timeline. Raises TimelineError with the reason
    (like Fusion's red marker) when the move is impossible or would break a step."""
    tl = timeline(doc)
    p = core.plan_move(tl, name, slot)
    if not p.ok:
        if p.reason:
            raise TimelineError(p.reason)
        return False
    geometry = _rebase_geometry(doc, tl, p)
    broken_before = _errors(doc)
    moving = tl.find(name)
    _transaction(doc, "Move %s" % moving.display)
    try:
        if moving.body is not None:
            body = doc.getObject(moving.body)
            new = list(p.body_orders.get(moving.body, ()))
            if [o.Name for o in body.Group if o.Name in new] != new:
                obj = doc.getObject(name)
                at = new.index(name)
                prev = doc.getObject(new[at - 1]) if at > 0 else None
                body.removeObject(obj)
                body.insertObject(obj, prev, True)
        for n, key in p.keys.items():
            obj = doc.getObject(n)
            _add_prop(obj, "App::PropertyFloat", RANK, "Place in the design timeline")
            setattr(obj, RANK, float(key))
        names = {i.group: i.group_name for i in tl.items if i.group}
        for n, gid in core.groups_after_move(tl, p).items():
            _set_group(doc.getObject(n), gid, names.get(gid, ""))
        after = timeline(doc)
        if p.marker_at_end:
            _set_marker_note(doc, None)
            tips = core.tips_for_count(after, len(after.items))
        else:
            tips = core.tips_for_count(after, p.marker_count)
        _set_tips(doc, tips)
        recompute(doc)
        _rebase(doc, p.order, geometry, tl)
        newly = _errors(doc) - broken_before
        if newly:
            item = timeline(doc).find(sorted(newly)[0])
            what = item.display if item is not None else sorted(newly)[0]
            raise TimelineError("%s would fail there." % what)
    except Exception:
        doc.abortTransaction()
        recompute(doc)
        raise
    doc.commitTransaction()
    return True


REBASE_PROPS = ("Base", "Faces")  # fillet/chamfer/draft/shell edges; Press Pull faces


def _rebase_geometry(doc, tl, p):
    """For each solid step whose previous step changes with the move: the edges/faces
    it picked on that previous step, as shapes, to find them again afterwards."""
    found = {}
    for name in core.rebased(tl, p):
        obj = doc.getObject(name)
        base = getattr(obj, "BaseFeature", None) if obj is not None else None
        if base is None:
            continue
        for prop in REBASE_PROPS:
            if prop not in obj.PropertiesList:
                continue
            value = getattr(obj, prop, None)
            if not (isinstance(value, tuple) and value and value[0] is base):
                continue
            subs = [s for s in _subs_of(value) if not s.startswith("?")]
            elements = []
            for sub in subs:
                try:
                    elements.append(base.Shape.getElement(sub).copy())
                except Exception:
                    pass
            if elements:
                found[name] = (prop, elements)
    return found


def _rebase(doc, order, geometry, tl):
    """After a move: point each rebased step at the same edges/faces on its new
    previous step (FreeCAD keeps the old names, which may mean other edges)."""
    for name in order:
        if name not in geometry:
            continue
        obj = doc.getObject(name)
        prop, elements = geometry[name]
        base = getattr(obj, "BaseFeature", None)
        title = tl.find(name).display if tl.find(name) else name
        if base is None or base.Shape.isNull():
            raise TimelineError("%s needs a solid before it." % title)
        names = [_twin_name(base.Shape, e) for e in elements]
        if None in names:
            raise TimelineError("%s uses geometry made by a step it would move before." % title)
        # Always set it again: the same "Edge2" may hide a stale internal name.
        setattr(obj, prop, (base, names))
        recompute(doc)


def _twin_name(shape, element, tol=1e-6):
    """Name ("Edge7") of the edge/face of ``shape`` at the same place as ``element``."""
    if element.ShapeType == "Edge":
        candidates, prefix = shape.Edges, "Edge"
    elif element.ShapeType == "Face":
        candidates, prefix = shape.Faces, "Face"
    else:
        return None
    box = element.BoundBox
    for i, c in enumerate(candidates):
        if not _same_place(c, element, box, prefix, tol):
            continue
        return "%s%d" % (prefix, i + 1)
    return None


def _same_place(c, element, box, prefix, tol):
    b = c.BoundBox
    if (
        abs(b.XMin - box.XMin) > tol
        or abs(b.XMax - box.XMax) > tol
        or abs(b.YMin - box.YMin) > tol
        or abs(b.YMax - box.YMax) > tol
        or abs(b.ZMin - box.ZMin) > tol
        or abs(b.ZMax - box.ZMax) > tol
    ):
        return False
    if prefix == "Edge":
        return abs(c.Length - element.Length) <= tol * 10
    return abs(c.Area - element.Area) <= tol * 100


# -- keeping edge/face references when a step's base changes ------------------------------
# {document name: {step name: ((base name, subs, base shape hash), property, [elements])}}:
# the edges/faces each fillet, chamfer, shell, draft or Press Pull was last computed on,
# as shapes. When its base step changes (a step added at the rolled-back marker, the step
# before it deleted), FreeCAD keeps the old names on the new base: other edges, or none
# ("Invalid edge link"). Fusion keeps the same edges; so does repair_references().
_REFS = {}
_TRIED = {}  # {document name: {step name: the last repair tried}}


def forget(doc_name):
    """A closed document: its remembered references must not apply to the next
    document opened under the same name."""
    _REFS.pop(doc_name, None)
    _TRIED.pop(doc_name, None)


def _ref_value(obj):
    """(property, base, [subs]) of a step's edge/face reference on its own base, or None."""
    base = getattr(obj, "BaseFeature", None)
    if base is None:
        return None
    for prop in REBASE_PROPS:
        if prop not in obj.PropertiesList:
            continue
        try:
            value = getattr(obj, prop)
        except Exception:
            continue
        if isinstance(value, tuple) and len(value) == 2 and hasattr(value[0], "Name"):
            return prop, value[0], _subs_of(value)
    return None


def remember_references(doc):
    """Record the edges/faces of every working step that picks them on its base."""
    memo = _REFS.setdefault(doc.Name, {})
    alive = set()
    for body in bodies(doc):
        for obj in body.Group:
            if not _is_solid_step(obj):
                continue
            alive.add(obj.Name)
            if is_suppressed(obj):
                continue
            state = list(getattr(obj, "State", []))
            if "Invalid" in state or "Error" in state or "Touched" in state:
                continue
            ref = _ref_value(obj)
            if ref is None:
                continue
            prop, linked, subs = ref
            base = obj.BaseFeature
            if linked is not base or not subs or any(s.startswith("?") for s in subs):
                continue
            try:
                shape = base.Shape
                if shape.isNull():
                    continue
                key = (base.Name, tuple(subs), shape.hashCode())
            except Exception:
                continue
            old = memo.get(obj.Name)
            if old is not None and old[0] == key:
                continue
            try:
                elements = [shape.getElement(s).copy() for s in subs]
            except Exception:
                continue
            memo[obj.Name] = (key, prop, elements)
    for name in [n for n in memo if n not in alive]:
        del memo[name]


def references_pending(doc):
    """True when a remembered step now sits on another base (repaired after the
    recompute; the failure FreeCAD reports meanwhile is not the user's)."""
    for name, (key, _prop, _elements) in _REFS.get(doc.Name, {}).items():
        obj = doc.getObject(name)
        base = getattr(obj, "BaseFeature", None) if obj is not None else None
        if base is not None and base.Name != key[0]:
            return True
    return False


def repair_references(doc):
    """Point steps whose base changed (or whose references FreeCAD lost) at the same
    edges/faces as before, found by geometry on their new base. True if any changed."""
    changed = False
    memo = _REFS.get(doc.Name, {})
    for name, (key, prop, elements) in list(memo.items()):
        obj = doc.getObject(name)
        if obj is None or is_suppressed(obj):
            continue
        base = getattr(obj, "BaseFeature", None)
        ref = _ref_value(obj)
        if base is None or ref is None or ref[0] != prop:
            continue
        _prop, linked, subs = ref
        state = list(getattr(obj, "State", []))
        lost = any(s.startswith("?") for s in subs)
        broken = "Invalid" in state or "Error" in state
        moved = base.Name != key[0] or linked is not base
        if not moved and [s.lstrip("?") for s in subs] != list(key[1]):
            continue  # other edges/faces were picked since (a dialog): those count
        try:
            shape = base.Shape
            if shape.isNull():
                continue
            base_changed = moved or shape.hashCode() != key[2]
            if not (lost or moved or (broken and base_changed)):
                continue  # nothing changed under it (a too-big radius is not ours to fix)
            # The same edges/faces still there, by place and size? (When an edit
            # really changed them, none is found and FreeCAD's naming decides.)
            names = [_twin_name(shape, e) for e in elements]
        except Exception:
            continue
        if None in names or (linked is base and list(names) == list(subs) and not broken):
            continue
        # Setting the same names again refreshes FreeCAD's internal element names (a
        # stale one can fail although the short name is right), but once is enough: a
        # step that still fails then fails for another reason (a radius too big...).
        attempt = (base.Name, shape.hashCode(), tuple(names))
        tried = _TRIED.setdefault(doc.Name, {})
        if linked is base and list(names) == list(subs) and tried.get(name) == attempt:
            continue
        tried[name] = attempt
        try:
            setattr(obj, prop, (base, names))
            changed = True
        except Exception:
            continue
    return changed


# -- groups ------------------------------------------------------------------------------
def _set_group(obj, gid, name):
    if obj is None:
        return
    if not gid and GROUP not in obj.PropertiesList:
        return
    _add_prop(obj, "App::PropertyString", GROUP, "Timeline group")
    _add_prop(obj, "App::PropertyString", GROUP_NAME, "Timeline group name")
    setattr(obj, GROUP, gid)
    setattr(obj, GROUP_NAME, name if gid else "")


def group(doc, names, title=None):
    """Fusion's Group Features: neighbouring steps under one folder in the timeline.
    Returns the group id."""
    tl = timeline(doc, deps=False)
    ok, reason = core.can_group(tl, names)
    if not ok:
        raise TimelineError(reason)
    gid = core.new_group_id(tl)
    title = title or core.new_group_name(tl)
    _transaction(doc, "Group Features")
    try:
        for n in names:
            _set_group(doc.getObject(n), gid, title)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    return gid


def group_members(doc, gid):
    return [i.name for i in timeline(doc, deps=False).items if i.group == gid]


def ungroup(doc, gid):
    members = group_members(doc, gid)
    if not members:
        return False
    _transaction(doc, "Ungroup")
    try:
        for n in members:
            _set_group(doc.getObject(n), "", "")
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    return True


def rename_group(doc, gid, text):
    text = (text or "").strip()
    members = group_members(doc, gid)
    if not members or not text:
        return False
    _transaction(doc, "Rename Group")
    try:
        for n in members:
            setattr(doc.getObject(n), GROUP_NAME, text)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    return True


def suppress_many(doc, names, on):
    """Suppress/unsuppress several steps (a group) as one undo step."""
    names = [n for n in names if doc.getObject(n) is not None]
    if on:
        return suppress(doc, [n for n in names if can_suppress(doc.getObject(n))])
    return unsuppress(doc, names)


# -- rename ------------------------------------------------------------------------------
def rename(doc, name, text):
    obj = doc.getObject(name)
    text = (text or "").strip()
    if obj is None or not text or text == obj.Label:
        return False
    _transaction(doc, "Rename %s" % obj.Label)
    obj.Label = text
    doc.commitTransaction()
    return True
