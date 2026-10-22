# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design history on/off (Fusion's Capture Design History, outline 7.3), base features
(Create Base Feature, outline 7.13) and bodies without history: the document side, no Qt.
direct_ui.py has the commands, the confirmation and the Finish Base Feature bar.

The model (decided in docs/sciforge/parity/direct-modify.md):

* Bodies stay PartDesign Bodies in every mode, so every SciForge command keeps working on
  them. A body without history is one frozen step: FreeCAD's PartDesign::FeatureBase at the
  start of the body (the timeline calls it "Base Feature"), linked to a hidden plain
  Part::Feature (the "base shape") that keeps the solid in the file.
* A design without history (capture off) bakes every command when it is OK'd: the steps it
  made are removed again and the bodies' base shapes take the result (freeze()). That
  happens inside the command's own undo step (takes_commit()), so Undo/Redo work per
  command as in Fusion. The timeline is hidden.
* Turning history off bakes the whole design (one undo step); turning it on shows each
  body's frozen step as a Base Feature at the start of the timeline.
* A base feature session (Create Base Feature, or Edit Feature on a base feature) bakes
  only its own bodies: the bodies made while it is open, and when an existing base feature
  is edited, the bodies of that base feature (the design is rolled back to it meanwhile).
* adopt() turns a plain Part::Feature solid (a STEP file opened by FreeCAD, a mesh turned
  into a solid by FreeCAD's own tool, a Part workbench shape) into a body built on it, so
  Press Pull, Delete and the other body tools work on it.
"""

import FreeCAD as App

from . import bodies, direct_core as core, log, warn

SETTINGS = "SciForgeDesign"
ROLE = "SciForgeRole"
SHAPE_ROLE = "BaseShape"  # the hidden Part::Feature holding a frozen solid
BASE_TYPE = "BaseFeature"  # SciForgeType of a base feature step (a body's FeatureBase)
BASE_ID = "SciForgeBaseId"  # bodies baked by one session / one capture share it
FEATURE_BASE = "PartDesign::FeatureBase"
PLAIN = "Part::Feature"
CHAIN_PROPS = ("BaseFeature", "_Body", "Origin", "Tip", "Group")
TOL = 1e-6

# Set by direct_ui (GUI): schedule(doc_name, transaction) finishes a deferred commit a moment
# later. None (headless): the bake runs at once, before the caller commits.
SCHEDULER = None


class DirectError(ValueError):
    """Something the user has to change; the message says why and what to do."""


# -- the design's setting ------------------------------------------------------------------------
class DesignSettings:
    """Hidden object with the design's own settings (Capture Design History). An object, not
    Document.Meta, so turning history off is undone with Ctrl+Z like the bake it goes with.
    Saved as "sciforge.direct.DesignSettings": keep the name."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure(obj)

    @staticmethod
    def ensure(obj):
        if "CaptureHistory" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyBool",
                "CaptureHistory",
                "Design",
                "Fusion's Capture Design History: steps are recorded in the timeline",
            )
            obj.CaptureHistory = True
        bodies.hide_from_timeline(obj)

    def onDocumentRestored(self, obj):
        self.ensure(obj)

    def execute(self, obj):
        return None

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def settings(doc, create=False):
    obj = doc.getObject(SETTINGS) if doc is not None else None
    if obj is None and create:
        obj = doc.addObject("App::FeaturePython", SETTINGS)
        DesignSettings(obj)
        obj.Label = "Design settings"
    return obj


def captures_history(doc):
    """True for a parametric design (Fusion's default), False when history is off."""
    try:
        obj = settings(doc)
        return True if obj is None else bool(getattr(obj, "CaptureHistory", True))
    except Exception:
        return True


def is_direct(doc):
    return doc is not None and not captures_history(doc)


# -- bodies and their base -------------------------------------------------------------------------
def base_of(body):
    """The body's FeatureBase (always its first step), or None."""
    try:
        group = list(body.Group)
    except Exception:
        return None
    if group and group[0].TypeId == FEATURE_BASE:
        return group[0]
    return None


def is_base_step(obj):
    try:
        return obj is not None and obj.TypeId == FEATURE_BASE
    except Exception:
        return False


def _users(obj, ignore=()):
    out = []
    try:
        for user in obj.InList:
            if user is obj or user in ignore:
                continue
            out.append(user)
    except Exception:
        pass
    return out


def _is_plain(obj):
    try:
        return obj is not None and obj.TypeId == PLAIN
    except Exception:
        return False


def _base_shape(body):
    """The plain Part::Feature the body's base takes its solid from and that nothing else
    uses (it can take a new solid), or None."""
    source = getattr(body, "BaseFeature", None)
    if not _is_plain(source):
        return None
    base = base_of(body)
    others = [u for u in _users(source, (body, base)) if u.TypeId != "App::Part"]
    return None if others else source


def rows(body):
    """The body as direct_core rows."""
    out = []
    frozen = _base_shape(body) is not None
    for obj in body.Group:
        base = obj.TypeId == FEATURE_BASE
        out.append(
            {
                "name": obj.Name,
                "solid": "BaseFeature" in obj.PropertiesList,
                "base": base,
                "frozen": base and frozen,
            }
        )
    return out


def _has_solid(obj):
    try:
        return obj is not None and not obj.Shape.isNull() and bool(obj.Shape.Solids)
    except Exception:
        return False


def freeze_point(body, fresh=None):
    """The step whose solid a bake gives the body's base, or None when there is nothing to
    bake: the Tip, or with ``fresh`` (a base feature session) the last of the run of new
    steps right after the base."""
    tip = getattr(body, "Tip", None)
    if tip is None or not _has_solid(tip):
        return None
    table = rows(body)
    if not core.needs_freeze(table, tip.Name, fresh):
        return None
    names = core.steps_to_freeze(table, tip.Name, fresh)
    if not names:
        return tip  # only the base is not frozen yet: the Tip is the base
    point = body.Document.getObject(names[-1])
    return point if _has_solid(point) else None


def needs_freeze(body, fresh=None):
    return freeze_point(body, fresh) is not None


# -- freezing ----------------------------------------------------------------------------------
def _new_shape_holder(doc, body):
    holder = doc.addObject(PLAIN, "BaseShape")
    holder.Label = "%s (base)" % body.Label
    bodies.add_prop(holder, "App::PropertyString", ROLE, "Base")
    setattr(holder, ROLE, SHAPE_ROLE)
    bodies.hide_from_timeline(holder)
    _hide(holder)
    rehome(body, holder)
    return holder


def rehome(body, holder=None):
    """The base shape lives in the body's component (FreeCAD only lets a body inside a
    component link an object of that component: else "Link(s) ... go out of the allowed
    scope"). The base feature does not move it: the body's own placement places both."""
    from . import components

    holder = holder if holder is not None else getattr(body, "BaseFeature", None)
    if holder is None or getattr(holder, ROLE, "") != SHAPE_ROLE:
        return False
    want = components.container_of(body)
    have = components.container_of(holder)
    if want is have:
        return False
    try:
        if have is not None:
            have.removeObject(holder)
        if want is not None:
            want.addObject(holder)
    except Exception as exc:
        warn("could not move %s with its body: %s" % (holder.Label, exc))
        return False
    return True


def _hide(obj):
    try:
        if App.GuiUp and obj.ViewObject is not None:
            obj.ViewObject.Visibility = False
        else:
            obj.Visibility = False
    except Exception:
        pass


def _mark_base(base, base_id=None):
    """A frozen step is a Base Feature in the timeline (also one a copy or a split made,
    which the timeline did not show before). A step another tool marked keeps its name
    ("Insert STEP")."""
    if base is None:
        return
    if not bodies.kind(base):
        bodies.mark(base, BASE_TYPE)
    if getattr(base, "SciForgeTimeline", True) is False:
        base.SciForgeTimeline = True
    if base_id:
        bodies.add_prop(base, "App::PropertyString", BASE_ID, "Base")
        if getattr(base, BASE_ID, "") != base_id:
            setattr(base, BASE_ID, base_id)


def _twin(shape, element, kind):
    """Name of the element of ``shape`` that is ``element`` (same place and size), or ''."""
    import Part

    try:
        if kind == "Vertex":
            for i, v in enumerate(shape.Vertexes, start=1):
                if (v.Point - element.Point).Length < TOL:
                    return "Vertex%d" % i
            return ""
        if kind == "Edge":
            mid = element.valueAt((element.FirstParameter + element.LastParameter) / 2.0)
            probe = Part.Vertex(mid)
            for i, e in enumerate(shape.Edges, start=1):
                if abs(e.Length - element.Length) > TOL * max(1.0, element.Length):
                    continue
                if e.distToShape(probe)[0] < TOL:
                    return "Edge%d" % i
            return ""
        if kind == "Face":
            center = element.CenterOfMass
            for i, f in enumerate(shape.Faces, start=1):
                if abs(f.Area - element.Area) > TOL * max(1.0, element.Area):
                    continue
                if (f.CenterOfMass - center).Length < 1e-5:
                    return "Face%d" % i
            return ""
    except Exception:
        return ""
    return ""


def _map_subs(step, subs, shape):
    """The sub-element names ``subs`` of ``step`` on ``shape``, or None when one is gone."""
    out = []
    for sub in subs:
        if not sub:
            out.append(sub)
            continue
        short = sub.split(".")[-1]
        kind = short.rstrip("0123456789")
        try:
            element = step.Shape.getElement(short)
        except Exception:
            return None
        name = _twin(shape, element, kind)
        if not name:
            return None
        out.append(name)
    return out


def _relink_users(doc, step, base, shape, gone):
    """Whatever used ``step`` (a sketch on one of its faces, a projected edge, a datum plane,
    a Combine's tool...) uses the base instead, on the same faces/edges found by place.
    A sketch or plane whose face is gone stays where it is (attachment off)."""
    for user in _users(step):
        if user.Name in gone or user.Name == step.Name:
            continue
        if user.TypeId == "PartDesign::Body":
            continue
        for prop in user.PropertiesList:
            if prop in CHAIN_PROPS:
                continue
            try:
                kind = user.getTypeIdOfProperty(prop)
            except Exception:
                continue
            if not kind.startswith(("App::PropertyLink", "App::PropertyXLink")):
                continue
            try:
                value = getattr(user, prop)
            except Exception:
                continue
            if prop == "ExternalGeometry":
                _relink_external(user, step, base, shape)
                continue
            new, changed, lost = _replace(value, step, base, shape)
            if not changed:
                continue
            if lost and prop in ("AttachmentSupport", "Support"):
                _detach(user)
                continue
            if lost:
                continue  # the step will be red with its reason (an outside step)
            try:
                setattr(user, prop, new)
            except Exception as exc:
                warn("could not re-link %s.%s: %s" % (user.Label, prop, exc))


def _replace(value, step, base, shape):
    """(new value, changed, lost) for a link property value with ``step`` replaced."""
    if value is None:
        return value, False, False
    if hasattr(value, "TypeId") and hasattr(value, "Name"):
        return (base, True, False) if value is step else (value, False, False)
    if isinstance(value, tuple) and len(value) == 2 and hasattr(value[0], "Name"):
        if value[0] is not step:
            return value, False, False
        subs = [value[1]] if isinstance(value[1], str) else list(value[1])
        mapped = _map_subs(step, subs, shape)
        if mapped is None:
            return value, True, True
        return (base, mapped if not isinstance(value[1], str) else mapped[0]), True, False
    if isinstance(value, list):
        out, changed, lost = [], False, False
        for entry in value:
            new, c, ls = _replace(entry, step, base, shape)
            out.append(new)
            changed = changed or c
            lost = lost or ls
        return out, changed, lost
    return value, False, False


def _detach(obj):
    try:
        if getattr(obj, "MapMode", "Deactivated") != "Deactivated":
            obj.MapMode = "Deactivated"  # keeps where it is
    except Exception:
        pass


def _relink_external(sketch, step, base, shape):
    """Projected edges of a step that goes now come from the base (same edges found by
    place); one that cannot be found there is taken out of the sketch with its
    constraints.

    FreeCAD 1.1 makes ExternalGeometry read-only (it was set directly before, which failed:
    "could not re-link the projected edges"), and one link can hold several curves (a face
    projected whole: Auto project). So each link of the step is projected again from the
    base (addExternal, same Defining / intersection), the constraints on the old curves
    move to the new ones in the same order, the old curves are deleted, and Auto project's
    record of its curves (sketch_auto_project.PROPERTY) follows."""
    try:
        import Sketcher

        geos = list(sketch.ExternalGeo)
    except Exception:
        return
    types = list(getattr(sketch, "ExternalTypes", []) or [])
    groups = {}  # sub of the step -> [(geo id, persistent id, defining, intersection)]
    order = []
    for index, geo in enumerate(geos):
        if index < 2:
            continue  # the sketch's own axes
        try:
            facade = Sketcher.ExternalGeometryFacade(geo)
            ref = facade.Ref
        except Exception:
            continue
        owner, _dot, sub = ref.rpartition(".")
        if owner.split(".")[-1] != step.Name or not sub:
            continue
        if sub not in groups:
            groups[sub] = []
            order.append(sub)
        intersection = index < len(types) and types[index] == 1
        groups[sub].append(
            (-(index + 1), facade.Id, bool(facade.testFlag("Defining")), intersection)
        )
    if not groups:
        return
    remap, ids = {}, {}
    try:
        for sub in order:
            curves = groups[sub]
            mapped = _map_subs(step, [_plain_sub(step, sub)], shape)
            if mapped is None:
                continue  # gone from the base: taken out with its constraints
            before = len(sketch.ExternalGeo)
            sketch.addExternal(base.Name, mapped[0], curves[0][2], curves[0][3])
            sketch.recompute()  # (the new curves exist after it)
            made = list(sketch.ExternalGeo)[before:]
            for k, (geo_id, persistent, _d, _i) in enumerate(curves):
                if k < len(made):
                    remap[geo_id] = -(before + k + 1)
                    ids[persistent] = Sketcher.ExternalGeometryFacade(made[k]).Id
        if remap:
            moved = []
            for constraint in sketch.Constraints:
                for attr in ("First", "Second", "Third"):
                    value = getattr(constraint, attr)
                    if value in remap:
                        setattr(constraint, attr, remap[value])
                moved.append(constraint)
            sketch.Constraints = moved
        # FreeCAD deletes every curve of a link with one of them: once per old link
        for sub in order:
            ref_index = _external_index(sketch, step.Name, sub)
            if ref_index is not None:
                sketch.delExternal(-(ref_index + 1))
        _follow_auto_ids(sketch, ids)
    except Exception as exc:
        warn("could not re-link the projected edges of %s: %s" % (sketch.Label, exc))


def _plain_sub(obj, sub):
    """ "FaceN" / "EdgeN" for a sub-element name FreeCAD keeps in its mapped form
    (";Face6;:M(...)", what a projection made with the topological naming records)."""
    if sub and (sub.startswith(";") or ":" in sub):
        try:
            name = obj.Shape.getElementName(sub, 0)
            if name and not name.startswith(";"):
                return name
        except Exception:
            pass
    return sub


def _external_index(sketch, owner_name, sub):
    """Index in ExternalGeo of a curve projected from `owner_name`.`sub`, or None."""
    import Sketcher

    for index, geo in enumerate(sketch.ExternalGeo):
        if index < 2:
            continue
        try:
            owner, _dot, name = Sketcher.ExternalGeometryFacade(geo).Ref.rpartition(".")
        except Exception:
            continue
        if owner.split(".")[-1] == owner_name and name == sub:
            return index
    return None


def _follow_auto_ids(sketch, ids):
    from . import sketch_auto_project as auto

    if auto.PROPERTY not in sketch.PropertiesList:
        return
    try:
        kept = [ids.get(i, i) for i in getattr(sketch, auto.PROPERTY)]
        setattr(sketch, auto.PROPERTY, kept)
    except Exception as exc:
        log("sketch: Auto project ids not kept: %s" % exc)


def freeze(doc, targets, base_id=None, fresh=None):
    """Bake ``targets`` ([(body, step)]): each body's solid at ``step`` (its Tip, or the
    last new step of a base feature session) becomes its base shape and the solid steps
    between the base and that step are removed, with the helpers only they used; bodies
    those steps used up (a Combine's tools, a Remove) are deleted. Steps after it stay and
    build on the new base. No undo step of its own. Returns the bases."""
    plans = []
    gone = set()
    for body, tip in targets:
        if not bodies.alive(body) or tip is None or not bodies.alive(tip):
            continue
        try:
            shape = tip.Shape
            if shape.isNull() or not shape.Solids:
                continue
        except Exception:
            continue
        names = core.steps_to_freeze(rows(body), tip.Name, fresh)
        if not names and _base_shape(body) is not None and base_of(body) is not None:
            if base_id:
                _mark_base(base_of(body), base_id)
            continue
        plans.append((body, tip, bodies.baked(shape), names))
        gone.update(names)
    if not plans:
        return []
    # A body used up by a step that goes (a Combine's tool, a body with its own Remove) would
    # come back once that step is baked away: it goes too (it is no longer in the design).
    users = bodies.consumers(doc)
    doomed_names = {name for name, step in users.items() if step.Name in gone}
    plans = [p for p in plans if p[0].Name not in doomed_names]
    doomed = [doc.getObject(name) for name in sorted(doomed_names)]
    replaced = []  # bases of bodies that were other features (copies, split pieces...)
    made = []
    for body, tip, shape, names in plans:
        holder = _base_shape(body)
        if holder is None:
            old = getattr(body, "BaseFeature", None)
            if old is not None:
                replaced.append(old)
            holder = _new_shape_holder(doc, body)
        holder.Shape = shape
        if body.BaseFeature is not holder:
            body.BaseFeature = holder
        base = base_of(body)
        _mark_base(base, base_id)
        made.append((body, base, holder, names))
    from . import timeline_ops

    for body, base, holder, names in made:
        for name in names:
            step = doc.getObject(name)
            if step is not None:
                _relink_users(doc, step, base, holder.Shape, gone)
    helpers = timeline_ops._helpers_of(doc, sorted(gone), gone)
    for body, base, holder, names in made:
        tip = body.Tip
        was_tip = tip is None or tip.Name in names or tip is base
        for name in reversed(names):
            step = doc.getObject(name)
            if step is None:
                continue
            try:
                if step in body.Group:
                    body.removeObject(step)
            except Exception:
                pass
            try:
                doc.removeObject(name)
            except Exception as exc:
                warn("could not remove %s: %s" % (name, exc))
        if base is not None and was_tip:
            body.Tip = base
            _show_only(body, base)
    for obj in helpers:
        if bodies.alive(obj):
            owner = bodies.body_of(obj)
            try:
                if owner is not None and obj in owner.Group:
                    owner.removeObject(obj)
                doc.removeObject(obj.Name)
            except Exception:
                pass
    for body in doomed:
        if bodies.alive(body):
            log("%s was taken out of the design (Combine / Remove): deleted" % body.Label)
            _remove_body(body)
    _drop_dead_history(doc, replaced)
    return [base for _b, base, _h, _n in made if base is not None]


def _show_only(body, tip):
    if not App.GuiUp:
        return
    try:
        for obj in body.Group:
            if obj.isDerivedFrom("PartDesign::Feature") and obj.ViewObject is not None:
                want = obj is tip
                if obj.ViewObject.Visibility != want:
                    obj.ViewObject.Visibility = want
    except Exception:
        pass


def _remove_body(body):
    """A body with its base shape (if it was ours)."""
    holder = getattr(body, "BaseFeature", None)
    bodies.remove_body(body)
    if holder is not None and getattr(holder, ROLE, "") == SHAPE_ROLE and not _users(holder):
        try:
            holder.Document.removeObject(holder.Name)
        except Exception:
            pass


def _drop_dead_history(doc, replaced):
    """History steps outside the bodies that nothing uses any more after a bake: the copy
    step of a Create Copy, the piece of a Split Body, the copies and the step of a body
    pattern (their bodies now keep their own solid)."""
    from . import move, pattern, split

    candidates = list(replaced)
    for obj in doc.Objects:
        if move.is_copy(obj) or split.is_piece(obj) or pattern.is_body_copy(obj):
            candidates.append(obj)
    for obj in candidates:
        if not bodies.alive(obj):
            continue
        if not (move.is_copy(obj) or split.is_piece(obj) or pattern.is_body_copy(obj)):
            continue
        if any(bodies.is_body(u) for u in _users(obj)):
            continue
        try:
            doc.removeObject(obj.Name)
        except Exception:
            pass
    for obj in list(doc.Objects):
        if not pattern.is_body_pattern(obj):
            continue
        copies = [u for u in _users(obj) if pattern.is_body_copy(u)]
        if copies:
            continue
        try:
            doc.removeObject(obj.Name)
        except Exception:
            pass


# -- what is waiting to be baked ---------------------------------------------------------------
class Session:
    """An open base feature (Create Base Feature, or Edit Feature on one)."""

    def __init__(self, doc, base_id, members=(), editing=False, saved=None):
        self.doc_name = doc.Name
        self.base_id = base_id
        self.members = set(members)  # body names
        self.known = {b.Name for b in bodies.list_bodies(doc)} - self.members
        self.editing = editing
        self.saved = saved  # (at end, active solid count, marker note) before the edit
        self.label = ""
        # Objects get growing ids: what is made from now on is the session's own work.
        self.start_id = max([o.ID for o in doc.Objects] or [0])

    def fresh(self, doc):
        """Names of the steps made since the session started."""
        return {o.Name for o in doc.Objects if o.ID > self.start_id}


SESSIONS = {}  # document name -> Session


def session(doc):
    return SESSIONS.get(doc.Name) if doc is not None else None


def candidates(doc):
    """The bodies whose new steps are baked now: every body without history, or the open
    base feature's bodies."""
    if is_direct(doc):
        return bodies.list_bodies(doc)
    s = session(doc)
    if s is None:
        return []
    found = bodies.list_bodies(doc)
    names = core.session_members(s.known, [b.Name for b in found], s.members)
    return [b for b in found if b.Name in names]


def _fresh(doc):
    s = session(doc)
    if s is None or is_direct(doc):
        return None
    return s.fresh(doc)


def pending(doc):
    """[(body, step)] with something to bake now ([] for a parametric design without an
    open base feature)."""
    out = []
    try:
        fresh = _fresh(doc)
        for body in candidates(doc):
            point = freeze_point(body, fresh)
            if point is not None:
                out.append((body, point))
    except Exception as exc:
        warn("history check: %s" % exc)
    return out


def bake(doc):
    """Bake what is pending (no undo step of its own). Returns the bases made."""
    targets = pending(doc)
    if not targets:
        return []
    s = session(doc)
    base_id = s.base_id if s is not None and not is_direct(doc) else None
    fresh = _fresh(doc)
    made = freeze(doc, targets, base_id, fresh)
    if s is not None and not is_direct(doc):
        for body, _tip in targets:
            if bodies.alive(body):
                s.members.add(body.Name)
        _sketches_into_base(doc, fresh)
    return made


def _inside_base(body, names=None):
    """Sketches and construction planes made inside a base feature belong to it (Fusion:
    only the base feature shows in the timeline, its sketches in the browser). ``names``:
    only those (the ones a session made); None: all of the body's."""
    for obj in body.Group:
        if "BaseFeature" in obj.PropertiesList:
            continue  # solid steps (the base itself shows)
        if names is not None and obj.Name not in names:
            continue
        try:
            if obj.TypeId == "App::Origin" or getattr(obj, "Role", None):
                continue
            if getattr(obj, "SciForgeTimeline", True) is not False:
                bodies.hide_from_timeline(obj)
        except Exception:
            pass


def _sketches_into_base(doc, names):
    """Sketches and planes made inside a base feature that no recorded step uses (they made
    what the base feature holds now) leave the timeline, like _inside_base."""
    for name in names or ():
        obj = doc.getObject(name)
        if obj is None or "BaseFeature" in obj.PropertiesList:
            continue
        try:
            if obj.TypeId not in ("Sketcher::SketchObject",) and not obj.TypeId.endswith(
                ("Plane", "Line", "Point")
            ):
                continue
            if getattr(obj, "Role", None) or getattr(obj, "SciForgeTimeline", True) is False:
                continue
            users = [u for u in obj.InList if not bodies.is_body(u)]
            if any("BaseFeature" in u.PropertiesList for u in users):
                continue  # a recorded step uses it: it stays a step too
            bodies.hide_from_timeline(obj)
        except Exception:
            pass


def takes_commit(doc):
    """Called where a command's undo step ends (OK). In a design without history, or for
    the bodies of an open base feature, the steps the command made are baked into the
    bodies in that same undo step. With the GUI the bake and the commit run a moment later
    (the dialog still reads its feature after OK): returns True, the caller must not commit.
    Headless it bakes at once and returns False (the caller commits)."""
    try:
        if doc is None or not pending(doc):
            return False
    except Exception:
        return False
    if SCHEDULER is None:
        _bake_quietly(doc)
        return False
    try:
        transaction = App.getActiveTransaction()
    except Exception:
        transaction = None
    SCHEDULER(doc.Name, transaction)
    return True


def bake_before_commit(doc):
    """A command that commits its own undo step (Delete): bake what it made first."""
    if pending(doc):
        _bake_quietly(doc)


def _bake_quietly(doc):
    from . import timeline_ops

    with timeline_ops.quiet():
        made = bake(doc)
        if made:
            doc.recompute()
    return made


def finish_deferred(doc, transaction):
    """The rest of takes_commit(): bake, then close the command's undo step. If something
    else closed it meanwhile, the bake is an undo step of its own."""
    from . import timeline_ops

    try:
        current = App.getActiveTransaction()
    except Exception:
        current = None
    ours = transaction is not None and current is not None and _tid(current) == _tid(transaction)
    if ours or (transaction is None and doc.HasPendingTransaction):
        try:
            _bake_quietly(doc)
            timeline_ops.settle(doc)
        except Exception as exc:
            warn("could not apply the change to the body: %s" % exc)
        doc.commitTransaction()
        try:
            App.closeActiveTransaction(False)
        except Exception:
            pass
        return True
    return bake_step(doc)


def _tid(transaction):
    """The id of App.getActiveTransaction()'s (name, id)."""
    try:
        return tuple(transaction)[-1]
    except Exception:
        return None


def bake_step(doc, title="Apply Without History"):
    """Bake what is pending as an undo step of its own (a change made by a FreeCAD command
    in a design without history). Returns True when something was baked."""
    if not pending(doc):
        return False
    if not doc.UndoMode:
        doc.UndoMode = 1
    doc.openTransaction(title)
    try:
        made = _bake_quietly(doc)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    log("%s: %d bod%s" % (title, len(made), "y" if len(made) == 1 else "ies"))
    return bool(made)


# -- turning history off and on --------------------------------------------------------------------
def _roll_to_end(doc):
    """Every body's history marker at its last step that is switched on."""
    for body in bodies.list_bodies(doc):
        last = None
        for obj in body.Group:
            if "BaseFeature" in obj.PropertiesList and not bodies.is_suppressed(obj):
                last = obj
        if last is not None and body.Tip is not last:
            body.Tip = last
    try:
        meta = dict(doc.Meta)
        if "SciForge.MarkerBefore" in meta:
            meta.pop("SciForge.MarkerBefore")
            doc.Meta = meta
    except Exception:
        pass


def history_off(doc):
    """Do Not Capture Design History (Fusion): every body keeps its shape as one frozen step,
    the history (features, the timeline) is removed; sketches and construction planes stay
    where they are. One undo step."""
    from . import timeline_ops

    if is_direct(doc):
        return False
    if session(doc) is not None:
        raise DirectError("Finish the base feature first (Finish Base Feature).")
    if not doc.UndoMode:
        doc.UndoMode = 1
    doc.openTransaction(timeline_ops.transaction_title(core.CAPTURE_OFF))
    try:
        with timeline_ops.quiet():
            _roll_to_end(doc)
            doc.recompute()
            targets = [(b, b.Tip) for b in bodies.list_bodies(doc) if b.Tip is not None]
            freeze(doc, targets)
            _drop_suppressed_leftovers(doc)
            settings(doc, create=True).CaptureHistory = False
            doc.recompute()
    except Exception:
        doc.abortTransaction()
        timeline_ops.recompute(doc)
        raise
    doc.commitTransaction()
    log("design history is off: %d bod%s kept as they are" % _count(doc))
    return True


def _count(doc):
    n = len(bodies.list_bodies(doc))
    return n, "y" if n == 1 else "ies"


def _drop_suppressed_leftovers(doc):
    """Steps that were switched off (suppressed) at the end of a body are not part of its
    shape: with history off they go too."""
    for body in bodies.list_bodies(doc):
        base = base_of(body)
        if base is None:
            continue
        for obj in reversed(list(body.Group)):
            if obj is base or "BaseFeature" not in obj.PropertiesList:
                continue
            try:
                body.removeObject(obj)
                doc.removeObject(obj.Name)
            except Exception:
                pass
        body.Tip = base


def history_on(doc):
    """Capture Design History (Fusion): the timeline comes back, each body's frozen step is a
    Base Feature at its start (they share one base feature id). One undo step."""
    from . import timeline_ops

    if not is_direct(doc):
        return False
    if not doc.UndoMode:
        doc.UndoMode = 1
    doc.openTransaction(timeline_ops.transaction_title(core.CAPTURE_ON))
    try:
        bake(doc)  # anything a FreeCAD command left unbaked
        base_id = core.next_base_id(_base_ids(doc))
        for body in bodies.list_bodies(doc):
            base = base_of(body)
            if base is not None:
                _mark_base(base, base_id)
                _inside_base(body)  # what was made without history is in the base feature
        settings(doc, create=True).CaptureHistory = True
        doc.recompute()
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    log("design history is captured again (base feature %s)" % base_id)
    return True


def _base_ids(doc):
    return [getattr(o, BASE_ID, "") for o in doc.Objects if getattr(o, BASE_ID, "")]


# -- base features -----------------------------------------------------------------------------
def base_id_of(step):
    return getattr(step, BASE_ID, "") if step is not None else ""


def members_of(step):
    """The bodies of the base feature ``step`` belongs to (one body when it has no id)."""
    doc = step.Document
    wanted = base_id_of(step)
    found = []
    for body in bodies.list_bodies(doc):
        base = base_of(body)
        if base is None:
            continue
        if base is step or (wanted and base_id_of(base) == wanted):
            found.append(body)
    return found


def start_base_feature(doc):
    """Create Base Feature: a session in which every body made is baked (one timeline item per
    body, never the single steps). Nothing is added to the document yet."""
    if is_direct(doc):
        raise DirectError(
            "This design does not capture history: every change is already direct. "
            "Turn on Capture Design History to use base features."
        )
    if session(doc) is not None:
        raise DirectError("A base feature is open: finish it first (Finish Base Feature).")
    s = Session(doc, core.next_base_id(_base_ids(doc)))
    SESSIONS[doc.Name] = s
    log("base feature %s started" % s.base_id)
    return s


def edit_base_feature(step):
    """Edit Feature on a base feature (Fusion): its bodies take direct edits again. The
    design is rolled back to it meanwhile (the steps after it wait), and rolled forward
    again by finish_base_feature()."""
    from . import timeline_core as tcore
    from . import timeline_ops as ops

    doc = step.Document
    if is_direct(doc):
        raise DirectError("This design does not capture history: edit the bodies directly.")
    if session(doc) is not None:
        raise DirectError("A base feature is open: finish it first (Finish Base Feature).")
    members = members_of(step)
    tl = ops.timeline(doc, deps=False)
    saved = (tl.at_end, tcore.active_count(tl), tl.before)
    places = [tl.find(base.Name) for base in (base_of(b) for b in members) if base is not None]
    places = [p.index for p in places if p is not None]
    if places:
        tips, note = tcore.marker_for_slot(tl, max(places) + 1)
        ops.set_marker_untracked(doc, tips, note)
    base_id = base_id_of(step) or core.next_base_id(_base_ids(doc))
    s = Session(doc, base_id, [b.Name for b in members], editing=True, saved=saved)
    s.label = step.Label
    SESSIONS[doc.Name] = s
    log(
        "editing base feature %s (%d bod%s)"
        % (step.Label, len(members), "y" if len(members) == 1 else "ies")
    )
    return s


def finish_base_feature(doc):
    """Finish Base Feature: what is still pending is baked (an undo step of its own when
    there is any), the session ends and an edited base feature's design is rolled forward
    again to where its marker was. Returns the session."""
    from . import timeline_core as tcore
    from . import timeline_ops as ops

    s = SESSIONS.get(doc.Name)
    if s is None:
        return None
    try:
        if pending(doc) and not doc.HasPendingTransaction:
            bake_step(doc, "Finish Base Feature")
    finally:
        SESSIONS.pop(doc.Name, None)
    if s.editing and s.saved:
        at_end, count, note = s.saved
        tl = ops.timeline(doc, deps=False)
        solids = len([i for i in tl.items if i.solid])
        tips = tcore.tips_for_count(tl, core.marker_after_edit(at_end, count, solids))
        ops.set_marker_untracked(doc, tips, None if at_end else note)
    log("base feature %s finished" % s.base_id)
    return s


def forget(doc_name):
    SESSIONS.pop(doc_name, None)


# -- bodies without history (plain Part::Feature solids) ---------------------------------------
def is_adoptable(obj):
    """A plain solid outside any body: an imported STEP part, a converted mesh, a Part
    workbench shape."""
    try:
        if obj is None or bodies.body_of(obj) is not None:
            return False
        if not obj.isDerivedFrom("Part::Feature") or obj.TypeId.startswith("PartDesign::"):
            return False
        if getattr(obj, ROLE, "") or bodies.kind(obj):
            return False  # SciForge's own objects (base shapes, copies, patterns...)
        if any(bodies.is_body(u) for u in _users(obj)):
            return False  # already the base of a body (it is hidden behind it)
        return not obj.Shape.isNull() and bool(obj.Shape.Solids)
    except Exception:
        return False


def adopt(obj):
    """A body built on the plain solid ``obj`` (its base feature), named and placed like it,
    with its colour; ``obj`` is hidden (the body shows it now). No undo step of its own: it
    belongs to the command that needed a body. Returns the body."""
    from . import components

    doc = obj.Document
    container = components.container_of(obj)
    body = bodies.new_body(doc, label=obj.Label)
    if container is not None:
        components.place(body, container)
    body.BaseFeature = obj
    base = base_of(body)
    _mark_base(base)
    bodies.hide_from_timeline(obj)
    _copy_colour(obj, body)
    _hide(obj)
    try:
        doc.recompute()
    except Exception:
        pass
    bodies.show_tip(body)
    log("%s is a body now (its base feature holds the solid)" % body.Label)
    return body


def _copy_colour(obj, body):
    try:
        if not App.GuiUp or obj.ViewObject is None:
            return
        color = obj.ViewObject.ShapeColor
        if tuple(round(c, 3) for c in color[:3]) in ((0.8, 0.8, 0.8),):
            return  # FreeCAD's default grey: nothing to keep
        from . import appearance

        appearance.set_body(body, appearance.custom(tuple(color[:3])))
    except Exception:
        pass


def body_for(obj):
    """The body a pick on ``obj`` means: its own body, or a new body built on a plain
    solid (adopt). None when it is neither."""
    body = bodies.body_of(obj)
    if body is not None:
        return body
    if is_adoptable(obj):
        return adopt(obj)
    return None
