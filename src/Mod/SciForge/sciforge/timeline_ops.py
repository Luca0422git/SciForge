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
GROUP = "SciForgeGroup"  # timeline group id of a step
GROUP_NAME = "SciForgeGroupName"


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


def recompute(doc):
    with quiet():
        doc.recompute()
        _pass_through_failures(doc)
        _clear_empty_bodies(doc)


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
    """Document observer: while a design has steps in error or suppressed (shown red
    or greyed in the timeline), FreeCAD would print the same errors again on every
    recompute, flooding the Report view. Mute it during those recomputes only."""

    def __init__(self):
        self._active = {}

    def slotBeforeRecomputeDocument(self, doc):
        try:
            if _has_known_problems(doc):
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


def _has_known_problems(doc):
    for obj in doc.Objects:
        if getattr(obj, "Suppressed", False) is True or getattr(obj, SUPPRESSED, False):
            return True
        state = getattr(obj, "State", [])
        if "Invalid" in state or "Error" in state:
            return True
    return False


_guard = {"observer": None}


def install_guard():
    if _guard["observer"] is None:
        _guard["observer"] = RecomputeGuard()
        App.addDocumentObserver(_guard["observer"])


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


def _is_step(obj):
    if obj.TypeId in NOT_STEPS or getattr(obj, "SciForgeTimeline", True) is False:
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
        kind, reason = problem(obj)
        features.append(
            {
                "name": obj.Name,
                "label": obj.Label,
                "type_id": type_key(obj),
                "body": body.Name if body is not None else None,
                "key": _key(obj),
                "suppressed": is_suppressed(obj),
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
    return core.build(features, tips)


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
def roll(doc, tips, title="Roll History Marker"):
    """Set the bodies' Tips (the history marker). One undo step."""
    if not tips:
        return False
    _transaction(doc, title)
    try:
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


def suppress(doc, name):
    """Suppress a step and, like Fusion, the steps that depend on it. Returns the
    names suppressed with it."""
    obj = doc.getObject(name)
    if obj is None or not can_suppress(obj):
        raise TimelineError("This step cannot be suppressed.")
    if is_suppressed(obj):
        return []
    links = _link_snapshot(doc)
    broken_before = _errors(doc)
    title = _label(doc, name)
    _transaction(doc, "Suppress %s" % title)
    try:
        group = {name} | dependents(doc, [name])
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
            for n in more - group:
                _set_suppressed(doc.getObject(n), True)
            group |= more
            recompute(doc)
        _add_prop(obj, "App::PropertyString", SUPPRESS_INFO, "Suppressed together with this")
        setattr(
            obj,
            SUPPRESS_INFO,
            json.dumps({"with": sorted(group - {name}), "links": links}),
        )
    except Exception:
        doc.abortTransaction()
        recompute(doc)
        raise
    doc.commitTransaction()
    return sorted(group - {name})


def unsuppress(doc, name):
    """Turn a suppressed step back on, with the steps that went off with it."""
    obj = doc.getObject(name)
    if obj is None or not is_suppressed(obj):
        return []
    try:
        info = json.loads(getattr(obj, SUPPRESS_INFO, "") or "{}")
    except ValueError:
        info = {}
    title = _label(doc, name)
    _transaction(doc, "Unsuppress %s" % title)
    try:
        group = [name] + [n for n in info.get("with", []) if doc.getObject(n) is not None]
        for n in group:
            _set_suppressed(doc.getObject(n), False)
        recompute(doc)
        links = {
            k: {p: tuple(v) for p, v in props.items()} for k, props in info.get("links", {}).items()
        }
        if _restore_links(doc, links):
            recompute(doc)
        if SUPPRESS_INFO in obj.PropertiesList:
            setattr(obj, SUPPRESS_INFO, "")
    except Exception:
        doc.abortTransaction()
        recompute(doc)
        raise
    doc.commitTransaction()
    return group[1:]


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
        for n in reversed(order):
            obj = doc.getObject(n)
            if obj is None:
                continue
            _show_profile_again(doc, obj, gone)
            body = body_of(obj)
            if body is not None and obj in body.Group:
                body.removeObject(obj)
            doc.removeObject(n)
        if at_end:
            after = timeline(doc)
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


def _show_profile_again(doc, obj, gone):
    if not App.GuiUp:
        return
    sketch = profile_sketch(obj)
    if sketch is None or sketch.Name in gone or sketch.ViewObject is None:
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
        b = c.BoundBox
        if (
            abs(b.XMin - box.XMin) > tol
            or abs(b.XMax - box.XMax) > tol
            or abs(b.YMin - box.YMin) > tol
            or abs(b.YMax - box.YMax) > tol
            or abs(b.ZMin - box.ZMin) > tol
            or abs(b.ZMax - box.ZMax) > tol
        ):
            continue
        if prefix == "Edge" and abs(c.Length - element.Length) <= tol * 10:
            return "Edge%d" % (i + 1)
        if prefix == "Face" and abs(c.Area - element.Area) <= tol * 100:
            return "Face%d" % (i + 1)
    return None


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
    title = "Suppress Features" if on else "Unsuppress Features"
    _transaction(doc, title)
    try:
        for n in names:
            obj = doc.getObject(n)
            if obj is not None and can_suppress(obj) and is_suppressed(obj) != on:
                _set_suppressed(obj, on)
        recompute(doc)
    except Exception:
        doc.abortTransaction()
        recompute(doc)
        raise
    doc.commitTransaction()


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
