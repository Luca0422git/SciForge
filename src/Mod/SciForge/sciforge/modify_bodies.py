# SPDX-License-Identifier: LGPL-2.1-or-later
"""Modify steps over several bodies in one timeline step (no Qt; the dialogs and the
golden-model builder both use it).

Fusion's Shell, Draft and Scale take faces (or bodies) of several bodies at once, and a
Pattern of an extrude that cut several bodies repeats the cut in each of them: one item in
the timeline. In FreeCAD a step belongs to one body, so the step the dialog makes (the
"lead") lives in the first body and every other body gets a hidden follower step:

  SciForgeRole "ModifyFollower"   never a timeline step of its own (timeline_ops lists it
                                  with FOLLOWER_ROLES: rolling back, suppressing, moving and
                                  deleting the lead takes the followers along)
  Source                          the lead step; the follower reads every size from it, so
                                  dialog edits, Change Parameters, formulas and reopened
                                  files all flow through the lead
  its own picks                   the faces of its own body (Shell, Draft)

A follower keeps the body as it was (passes its solid through) when its lead is gone. The
follower kinds are the classes at the end of this file: ShellFollower, DraftFollower,
ScaleFollower and PatternFollower. Saved files store "sciforge.modify_bodies.<Class>":
keep the names and the properties.
"""

import FreeCAD as App

from . import bodies

ROLE_PROP = "SciForgeRole"
ROLE = "ModifyFollower"
TYPE = "PartDesign::FeaturePython"
WARNING = "SciForgeWarning"  # the timeline shows this text as the lead's warning


class FollowerError(ValueError):
    """A follower cannot be computed; the message says why and what to try."""


# -- finding followers ------------------------------------------------------------------------
def is_follower(obj):
    try:
        return getattr(obj, ROLE_PROP, "") == ROLE
    except Exception:
        return False


def lead_of(obj):
    """The step a follower follows (None once it was deleted)."""
    lead = getattr(obj, "Source", None)
    return lead if lead is not None and bodies.alive(lead) else None


def lead_or_self(obj):
    """The lead of a follower, else the object itself (a double-click on a follower edits
    its lead)."""
    if is_follower(obj):
        lead = lead_of(obj)
        if lead is not None:
            return lead
    return obj


def followers_of(lead):
    """The hidden steps `lead` drives in the other bodies, oldest first."""
    if lead is None or not bodies.alive(lead):
        return []
    found = []
    try:
        users = list(lead.InList)
    except Exception:
        return []
    for obj in users:
        if is_follower(obj) and getattr(obj, "Source", None) is lead and obj not in found:
            if bodies.alive(obj):
                found.append(obj)
    return sorted(found, key=lambda o: o.ID)


def follower_in(lead, body):
    """The follower of `lead` in `body`, or None."""
    for obj in followers_of(lead):
        if bodies.body_of(obj) is body:
            return obj
    return None


def bodies_of(lead):
    """The lead's body first, then the bodies of its followers."""
    found = []
    for obj in [lead] + followers_of(lead):
        body = bodies.body_of(obj)
        if body is not None and body not in found:
            found.append(body)
    return found


def orphans(doc):
    """Followers whose lead was deleted (by FreeCAD's own Delete, which knows nothing of
    them): they go too, a moment later."""
    found = []
    for obj in doc.Objects:
        if is_follower(obj) and lead_of(obj) is None:
            found.append(obj)
    return found


def remove_orphans(doc):
    for obj in orphans(doc):
        remove(obj)


# -- making and removing followers ------------------------------------------------------------
def step_times(doc):
    """{name: place in the timeline} of every step, followers at their lead's place."""
    from . import extrude_bodies

    times = extrude_bodies.step_times(doc)
    for obj in doc.Objects:
        if is_follower(obj):
            lead = getattr(obj, "Source", None)
            if lead is not None and lead.Name in times:
                times[obj.Name] = times[lead.Name]
    return times


def _place(body, lead):
    """The step of `body` a follower of `lead` comes after: the body's last step before the
    lead in the timeline (an older step being edited acts on each body as it was then), or
    its Tip for a new step at the marker. None: nothing of the body exists there yet."""
    from . import extrude_bodies

    try:
        return extrude_bodies.place_in(body, lead, step_times(lead.Document))
    except Exception:
        return body.Tip


def add(body, lead, proxy, name):
    """A new follower step of `lead` in `body` (proxy: one of the classes below). Not
    recomputed. Raises FollowerError when the body has no solid at the lead's place."""
    place = _place(body, lead)
    if place is None or place.Shape.isNull() or not place.Shape.Solids:
        raise FollowerError("%s has no solid at this point of the timeline." % body.Label)
    doc = lead.Document
    if place is body.Tip:
        obj = bodies.insert_after_tip(body, TYPE, name)
    else:
        obj = doc.addObject(TYPE, name)
        body.insertObject(obj, place, True)
    proxy(obj)
    bodies.add_prop(obj, "App::PropertyString", ROLE_PROP, "SciForge")
    setattr(obj, ROLE_PROP, ROLE)
    obj.Source = lead
    if hasattr(obj, "Refine"):
        obj.Refine = True
    _hide(obj)
    return obj


def base_for(lead, body):
    """The step a follower of `lead` in `body` builds on (where its faces are picked): the
    follower's own base when it exists, else where a new one would go."""
    follower = follower_in(lead, body) if lead is not None else None
    if follower is not None and follower.BaseFeature is not None:
        return follower.BaseFeature
    if lead is None:
        return body.Tip
    return _place(body, lead)


def sync(lead, members, proxy, name):
    """Make `lead`'s followers match `members`, [(body, face names or None)] for the bodies
    other than the lead's: existing ones keep their place and get the new picks, missing
    ones are made, the others removed. Returns the followers (members' order)."""
    wanted = [(b, n) for b, n in members if b is not None and b is not bodies.body_of(lead)]
    keep = {b.Name for b, _n in wanted}
    for obj in followers_of(lead):
        body = bodies.body_of(obj)
        if body is None or body.Name not in keep or not isinstance(obj.Proxy, proxy):
            remove(obj)
    out = []
    for body, names in wanted:
        obj = follower_in(lead, body)
        if obj is None:
            obj = add(body, lead, proxy, name)
        if names is not None and "Faces" in obj.PropertiesList:
            base = obj.BaseFeature or base_for(lead, body)
            set_faces(obj, base, names)
        out.append(obj)
    return out


def remove(follower):
    bodies.remove_step(follower)


def remove_all(lead):
    for obj in followers_of(lead):
        remove(obj)


def move_followers(old, new):
    """`new` replaces the step `old` (the dialog rebuilt it as the other kind of feature):
    its followers follow `new`."""
    for obj in followers_of(old):
        try:
            obj.Source = new
        except Exception:
            pass


def _hide(obj):
    if not App.GuiUp:
        return
    try:
        if "ShowInTree" in obj.ViewObject.PropertiesList:
            obj.ViewObject.ShowInTree = False
    except Exception:
        pass
    try:
        from .modify_bodies_gui import FollowerViewProvider

        FollowerViewProvider(obj.ViewObject)
    except Exception:
        pass


# -- coordinates -------------------------------------------------------------------------------
def placement_of(obj):
    """The global placement of the body `obj` belongs to (identity outside a body)."""
    body = bodies.body_of(obj)
    try:
        return body.getGlobalPlacement() if body is not None else App.Placement()
    except Exception:
        return App.Placement()


def point_between(point, source, target):
    """A point in `source`'s body coordinates as `target`'s body coordinates."""
    glob = placement_of(source).multVec(point)
    return placement_of(target).inverse().multVec(glob)


def vector_between(vector, source, target):
    glob = placement_of(source).Rotation.multVec(vector)
    return placement_of(target).Rotation.inverted().multVec(glob)


def shape_between(shape, source, target):
    """A copy of a shape in `source`'s body coordinates in `target`'s body coordinates."""
    out = bodies.baked(shape)
    move = placement_of(target).inverse().multiply(placement_of(source))
    if not move.isIdentity():
        out.transformShape(move.toMatrix(), True)
    return out


def placement_between(move, source, target):
    """A move (App.Placement acting on `source`'s body coordinates) as the same move acting
    on `target`'s body coordinates."""
    a, b = placement_of(source), placement_of(target)
    return b.inverse().multiply(a).multiply(move).multiply(a.inverse()).multiply(b)


# -- the follower steps ------------------------------------------------------------------------
def _set_note(obj, text):
    try:
        if WARNING not in obj.PropertiesList:
            if not text:
                return
            obj.addProperty("App::PropertyString", WARNING, "SciForge", "Timeline warning", 4 | 16)
        if getattr(obj, WARNING) != text:
            setattr(obj, WARNING, text)
    except Exception:
        pass


class _Follower:
    """What every follower shares: the Source link, Refine, and an execute that passes the
    body through when the lead is gone."""

    KIND = "Follower"

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    def ensure_properties(self, obj):
        if "Source" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkGlobal", "Source", "Follower", "The step it follows")
        if "Refine" not in obj.PropertiesList:
            obj.addProperty("App::PropertyBool", "Refine", "Follower", "Merge faces, like Fusion")
            obj.Refine = True
        bodies.mark(obj, self.KIND)
        self.extra_properties(obj)

    def extra_properties(self, obj):
        pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        body = bodies.body_of(obj)
        label = body.Label if body is not None else "this body"
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            bodies.pass_through(obj)
            raise FollowerError("%s has no solid here for the step to act on." % label)
        lead = lead_of(obj)
        if lead is None or getattr(obj, "Suppressed", False):
            obj.Shape = base.Shape.copy()  # no lead any more: the body stays as it was
            return
        try:
            shape = self.build(obj, lead, base.Shape.copy())
        except Exception as exc:
            bodies.pass_through(obj)
            raise FollowerError("%s cannot be applied to %s: %s" % (lead.Label, label, exc))
        if bool(getattr(obj, "Refine", True)):
            try:
                shape = shape.removeSplitter()
            except Exception:
                pass
        obj.Shape = shape

    def build(self, obj, lead, base_shape):
        return base_shape

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _face_names(obj):
    link = getattr(obj, "Faces", None)
    return [s.lstrip("?") for s in (link[1] if link else []) if s]


def set_faces(obj, base, names):
    """The follower's own picked faces (on `base`, the step before it)."""
    names = list(names or [])
    old = obj.Faces
    if not names:
        if old:
            obj.Faces = None
        return
    if not (old and old[0] is base and [s for s in old[1] if s] == names):
        obj.Faces = (base, names)


class ShellFollower(_Follower):
    """Shell in another body: its own faces taken away (none: the body becomes hollow), the
    lead's thicknesses, direction and shell type."""

    KIND = "ShellFollower"

    def extra_properties(self, obj):
        if "Faces" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkSub", "Faces", "Follower", "The faces taken away")

    def build(self, obj, lead, base_shape):
        from . import shelling

        _base, _names, options, _formulas = shelling.read(lead)
        return shelling.build(base_shape, _face_names(obj), options)


class DraftFollower(_Follower):
    """Draft in another body: its own faces, the lead's plane, pull direction, parting tool,
    sides and angles (read in this body's coordinates)."""

    KIND = "DraftFollower"

    def extra_properties(self, obj):
        if "Faces" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkSub", "Faces", "Follower", "The faces drafted")

    def build(self, obj, lead, base_shape):
        from . import drafting

        spec = drafting.spec_of(lead, obj)
        return drafting.draft_shape(base_shape, _face_names(obj), spec)


class ScaleFollower(_Follower):
    """Scale in another body: the lead's point and factors (the point in this body's
    coordinates)."""

    KIND = "ScaleFollower"

    def build(self, obj, lead, base_shape):
        from . import scale

        point, factors = scale.spec_of(lead, obj)
        return scale.scaled(base_shape, point, factors)


class PatternFollower(_Follower):
    """Pattern of a multi-body extrude in another body: the extrusion copies cut from this
    body too (Fusion repeats the change in every body the extrude changed)."""

    KIND = "PatternFollower"

    def build(self, obj, lead, base_shape):
        from . import pattern_adjust

        return pattern_adjust.follower_result(obj, lead, base_shape)
