# SPDX-License-Identifier: LGPL-2.1-or-later
"""One Extrude that acts on several bodies, like Fusion's (no GUI code; extrude.py calls it).

Fusion's Extrude cuts (joins, intersects) every body it passes through, and it is still one
step in the timeline. SciForge builds that from PartDesign pieces:

  the lead       the extrude's own feature (Pad / Pocket / SciForge's ExtrudeFeature), in the
                 profile's body when that body takes part, else in the oldest body that does
  followers      hidden steps in the other bodies, driven by the lead (SciForgeRole
                 "ExtrudeFollower", link "Source" to the lead; never a timeline step):
                   cut / intersect  an ExtrudeFollower per other body: that body cut with
                                    the lead's extrusion, or only what lies inside it kept
                   join             one CombineFeature right after the lead that merges the
                                    other bodies into the lead's body; they are then used up
                                    (hidden), like Combine's tool bodies

The list of bodies is the lead's "bodies" (SciForgeExtrude JSON): what the dialog's "Bodies
to Cut" row showed when OK was pressed. touched_bodies() finds the bodies in the way;
starts_in_material() is Fusion's automatic Cut. The timeline side (Tips, suppress, delete,
move) is in timeline_ops.py; the dialog row in extrude_ui.py; pure rules (row words, the
follower plan) in extrude_bodies_core.py.

Saved documents store "sciforge.extrude_bodies.ExtrudeFollower": keep the name stable.
"""

import FreeCAD as App

from . import bodies
from .extrude import (
    FOLLOWER_ROLE,
    INTERSECT_TYPE,
    PLANE_TYPES,
    ROLE,
    TOL,
    ExtrudeError,
    _mark,
    _ref_global,
    _save_meta,
    _sign1,
    global_faces,
    load_meta,
    normalize,
    options_with_defaults,
    owner_body,
    profile_normal,
    read,
    start_offset_of,
)

WARNING = "SciForgeWarning"  # timeline_ops.WARNING: the timeline shows it in yellow
VOLUME_TOL = 1e-6  # mm^3: less overlap than this is "only touching"
# Automatic Cut: at least this share of the extrusion's first 0.01 mm must lie in a body. A
# tapered column next to a face profile flares over its edge by a sliver (0.002 %), which
# turned an extrude of that face outwards into a Cut.
START_SHARE = 0.01


def _alive(obj):
    return bodies.alive(obj)


def is_follower(obj):
    return getattr(obj, ROLE, "") == FOLLOWER_ROLE


def is_merge(obj):
    """The follower of a Join: a Combine that merges the other bodies into the lead's."""
    return is_follower(obj) and getattr(obj, "SciForgeType", "") == "Combine"


def followers_of(lead):
    """The hidden steps a multi-body extrude drives in its bodies (oldest first)."""
    if lead is None or not _alive(lead):
        return []
    found = []
    try:
        users = list(lead.InList)
    except Exception:
        return []
    for obj in users:
        if is_follower(obj) and getattr(obj, "Source", None) is lead and obj not in found:
            found.append(obj)
    return sorted(found, key=lambda o: o.ID)


def lead_of(follower):
    """The extrude a follower step belongs to (None once it was deleted)."""
    lead = getattr(follower, "Source", None)
    return lead if lead is not None and _alive(lead) else None


def stored_bodies(feature):
    """The bodies an existing extrude acts on (its "Bodies to Cut" list), or None for an
    extrude made before extrudes could act on several bodies (it acts on its own body)."""
    names = load_meta(feature).get("bodies") if feature is not None else None
    if names is None:
        return None
    doc = feature.Document
    found = []
    for name in names:
        body = doc.getObject(name)
        if body is not None and body.TypeId == "PartDesign::Body" and body not in found:
            found.append(body)
    return found


def acted_on(feature):
    """Every body an extrude changes: its own and its followers' (oldest first)."""
    found = []
    for obj in [feature] + followers_of(feature):
        body = owner_body(obj)
        if body is not None and body not in found:
            found.append(body)
        if is_merge(obj):
            for tool in getattr(obj, "Tools", []) or []:
                tool_body = owner_body(tool)
                if tool_body is not None and tool_body not in found:
                    found.append(tool_body)
    return sorted(found, key=lambda b: b.ID)


def lead_body(src, participants):
    """Where the lead feature goes: the profile's body when it takes part, else the oldest
    body that does."""
    if src in participants:
        return src
    return sorted(participants, key=lambda b: b.ID)[0]


def participants_for(feature, profiles, options):
    """The bodies the extrude acts on, oldest first; None = the profile's body only (the
    first version's way, for callers that do not say)."""
    if options["operation"] == "new_body":
        return None
    wanted = options.get("bodies")
    if wanted is None and feature is not None:
        wanted = stored_bodies(feature)
    if wanted is None:
        return None
    if isinstance(wanted, str):  # "auto": every body the extrusion passes through
        found = touched_bodies(profiles, options, lead=feature)
        if found is None:
            return None
        wanted = found
    result = []
    for body in wanted:
        if _alive(body) and body.TypeId == "PartDesign::Body" and body not in result:
            result.append(body)
    return sorted(result, key=lambda b: b.ID)


def nothing_touched(options):
    if options["operation"] == "intersect":
        return (
            "The extrusion does not go through any body, so Intersect would leave nothing. "
            "Change the distance or the direction."
        )
    return "The cut does not go through any body. Flip it, change the distance or the " "direction."


def before_shape(body, lead=None):
    """`body`'s solid (design coordinates) as it was before the extrude `lead` changed it:
    the step before the lead or before its follower in that body; else the body as it is."""
    step = None
    if lead is not None and _alive(lead):
        if owner_body(lead) is body:
            step = lead.BaseFeature
            if step is None:
                import Part

                return Part.Shape()
        else:
            for follower in followers_of(lead):
                if owner_body(follower) is body and not is_merge(follower):
                    step = follower.BaseFeature
                    break
    if step is None:
        return bodies.global_shape(body)
    return bodies.global_shape(step)


def _merged_by(lead, body):
    for follower in followers_of(lead):
        if is_merge(follower) and any(
            owner_body(t) is body for t in (getattr(follower, "Tools", []) or [])
        ):
            return True
    return False


def candidate_bodies(doc, lead=None):
    """[(body, its solid before the extrude)] for the bodies an extrude can act on: those
    shown and holding a solid, not used up by another step (Combine). A hidden body is left
    out, as one Fusion does not show is not in the way (guess)."""
    own = {f.Name for f in followers_of(lead)} if lead is not None else set()
    used = {name for name, step in bodies.consumers(doc).items() if step.Name not in own}
    found = []
    for body in bodies.list_bodies(doc):
        if body.Name in used:
            continue
        if not bodies.is_shown(body) and not _merged_by(lead, body):
            continue
        try:
            shape = before_shape(body, lead)
        except Exception:
            continue
        if shape.isNull() or not shape.Solids:
            continue
        found.append((body, shape))
    return found


def _overlaps(shape, tool, contact=False, volume=VOLUME_TOL):
    """True when `tool` shares volume with `shape` (with contact: or shares a piece of a
    face with it, as a profile on a body's face extruded outwards does; touching along an
    edge or at a corner does not count)."""
    try:
        box = tool.BoundBox
        box.enlarge(1e-4)
        if not box.intersect(shape.BoundBox):
            return False
        if shape.common(tool).Volume > volume:
            return True
        return bool(contact) and _face_contact(shape, tool)
    except Exception:
        return False


def _face_contact(shape, tool, tol=1e-6):
    """True when a face of `tool` lies on a face of `shape` over some area: a profile on a
    body's top extruded upwards, a disc filling a round hole (its side on the hole's wall)."""
    if shape.distToShape(tool)[0] > tol:
        return False
    for a in tool.Faces:
        box = a.BoundBox
        box.enlarge(1e-4)
        for b in shape.Faces:
            if not box.intersect(b.BoundBox) or b.distToShape(a)[0] > tol:
                continue
            try:
                if a.common(b).Area > tol:
                    return True
            except Exception:
                continue
    return False


def tool_prism(profiles, options, reach=()):
    """The solid the extrusion sweeps, in design coordinates (no boolean with any body).
    "All" goes past everything in `reach`. Raises ExtrudeError when it cannot be built
    here (an extrusion up to a whole body: FreeCAD's Pad measures that itself)."""
    from . import extrude_prism

    profiles = normalize(profiles)
    options = options_with_defaults(options)
    faces = global_faces(profiles)
    if not faces:
        raise ExtrudeError("The profile has no closed area to extrude.")
    normal = profile_normal(profiles)
    sign = _sign1(profiles, options)
    distance = float(options["distance"])
    if options["direction"] == "symmetric":
        length = abs(distance) if options["measurement"] == "whole" else 2.0 * abs(distance)
    else:
        length = abs(distance)
    kind = {"distance": "Length", "all": "ThroughAll", "to_object": "UpToFace"}

    def target(key, extent):
        ref = options.get(key)
        if options[extent] != "to_object" or not ref:
            return None
        obj, sub = ref
        if not sub and obj.TypeId not in PLANE_TYPES:
            raise ExtrudeError("An extrusion up to a whole body is measured by FreeCAD's Pad.")
        return _ref_global(ref)

    spec = {
        "side_type": {"one_side": "One side", "two_sides": "Two sides", "symmetric": "Symmetric"}[
            options["direction"]
        ],
        "reversed": sign < 0,
        "start_offset": start_offset_of(profiles, options),
        "type": kind[options["extent"]],
        "length": length,
        "taper": float(options["taper"]),
        "target": target("extent_object", "extent"),
        "type2": kind[options["extent2"]],
        "length2": abs(float(options["distance2"])),
        "taper2": float(options["taper2"]),
        "target2": (
            target("extent_object2", "extent2") if options["direction"] == "two_sides" else None
        ),
    }
    try:
        return extrude_prism.build(faces, normal, spec, reach=list(reach))
    except extrude_prism.PrismError as exc:
        raise ExtrudeError(str(exc))


def touched_bodies(profiles, options, lead=None, contact=None):
    """The bodies the extrusion passes through, oldest first: Fusion's automatic list of
    bodies to cut (or join, intersect). A Join also counts bodies it only touches (a
    profile on a face, extruded outwards). Each body is taken as it was before `lead` (the
    extrude being previewed or edited). None when it cannot be told here (an extrusion up
    to a whole body)."""
    options = options_with_defaults(options)
    if contact is None:
        contact = options["operation"] == "join"
    found = in_the_way(profiles, options, lead)
    if found is None:
        return None
    return found[1] if contact else found[0]


def in_the_way(profiles, options, lead=None):
    """([bodies the extrusion passes through], [bodies it passes through or only touches]),
    oldest first, each body as it was before `lead`; None when it cannot be told here. One
    extrusion solid for both lists (the dialog needs both: Cut lists the first, Join and
    the automatic operation the second)."""
    profiles = normalize(profiles)
    if not profiles:
        return [], []
    options = options_with_defaults(options)
    doc = profiles[0][0].Document
    candidates = candidate_bodies(doc, lead)
    if not candidates:
        return [], []
    try:
        prism = tool_prism(profiles, options, [shape for _body, shape in candidates])
    except Exception:
        return None
    # A sliver (a tapered neighbour flaring over the profile's edge) does not count.
    enough = max(VOLUME_TOL, prism.Volume * 1e-6)
    through, touching = [], []
    for body, shape in candidates:
        if _overlaps(shape, prism, volume=enough):
            through.append(body)
            touching.append(body)
        elif _overlaps(shape, prism, contact=True):
            touching.append(body)
    return through, touching


def starts_in_material(profiles, options, lead=None):
    """Fusion's automatic Cut: True when the first 0.01 mm of the extrusion lies inside a
    body (any body it can act on, not only the profile's own; one point of the profile was
    tested before, so a profile across a gap between two bodies stayed a Join). At least 1 %
    of that slice must be inside (START_SHARE)."""
    try:
        profiles = normalize(profiles)
        options = options_with_defaults(options)
        if not profiles or options["direction"] == "symmetric":
            return False
        candidates = candidate_bodies(profiles[0][0].Document, lead)
        if not candidates:
            return False
        sign = _sign1(profiles, options)
        normal = profile_normal(profiles)
        offset = start_offset_of(profiles, options)
        pieces = []
        for face in global_faces(profiles):
            face = face.copy()
            if abs(offset) > TOL:
                face.translate(normal * offset)
            pieces.append(face.extrude(normal * (0.01 * sign)))
        for _body, shape in candidates:
            for piece in pieces:
                if _overlaps(shape, piece, volume=max(1e-9, piece.Volume * START_SHARE)):
                    return True
    except Exception:
        return False
    return False


def follower_tool(lead, reach=None):
    """The lead's extrusion as a solid in design coordinates, for its followers: FreeCAD's
    own tool solid (AddSubShape) when the lead has one, else built again with `reach` (the
    follower's body) as the end of "All": PartDesign sizes All from the lead's body only,
    which stopped short of a body further away."""
    profiles, options = read(lead)
    options = options_with_defaults(dict(options, bodies=None))
    sides = [options["extent"]]
    if options["direction"] == "two_sides":
        sides.append(options["extent2"])
    sub = None
    if "AddSubShape" in lead.PropertiesList and "all" not in sides:
        try:
            sub = lead.AddSubShape
        except Exception:
            sub = None
    if sub is not None and not sub.isNull() and sub.Solids:
        out = bodies.baked(sub)
        body = owner_body(lead)
        if body is not None:
            place = body.getGlobalPlacement()
            if not place.isIdentity():
                out.transformShape(place.toMatrix(), True)
        return out
    return tool_prism(profiles, options, [reach] if reach is not None else [])


def _off(obj):
    return bodies.is_suppressed(obj) or not bodies.is_active_step(obj)


def _failed(obj):
    state = list(getattr(obj, "State", []))
    return "Invalid" in state or "Error" in state


class ExtrudeFollower:
    """A multi-body extrude's step in another body (hidden, SciForgeRole ExtrudeFollower): it
    cuts that body with the lead's extrusion, or keeps only what lies inside it. It stores no
    sizes of its own; everything comes from the lead ("Source"), so dialog edits, Change
    Parameters, formulas and reopened files all flow through the lead. Saved in files as
    "sciforge.extrude_bodies.ExtrudeFollower": keep the name and the properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        if "Source" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLinkGlobal", "Source", "Extrude", "The extrude this step follows"
            )
        if "Operation" not in obj.PropertiesList:
            obj.addProperty("App::PropertyEnumeration", "Operation", "Extrude", "Cut or Intersect")
            obj.Operation = ["Cut", "Intersect"]
            obj.Operation = "Cut"
        if "Refine" not in obj.PropertiesList:
            obj.addProperty("App::PropertyBool", "Refine", "Extrude", "Merge faces, like Fusion")
            obj.Refine = True
        if WARNING not in obj.PropertiesList:
            # 4 hidden, 16 setting it does not mark the step for recompute
            obj.addProperty(
                "App::PropertyString", WARNING, "SciForge", "Why the timeline warns", 4 | 16
            )

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            self._build(obj)
        except ExtrudeError:
            bodies.pass_through(obj)  # the body as it was before it; the extrude shows red
            raise
        except Exception as exc:
            bodies.pass_through(obj)
            raise ExtrudeError("The extrude cannot be applied to this body: %s" % exc)

    def _build(self, obj):
        base = obj.BaseFeature
        body = owner_body(obj)
        label = body.Label if body is not None else "this body"
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise ExtrudeError("%s has no solid here for the extrude to act on." % label)
        lead = lead_of(obj)
        if lead is None or _off(lead) or _failed(lead) or getattr(obj, "Suppressed", False):
            # No lead any more (deleted), or it is off: the body stays as it was.
            obj.Shape = base.Shape.copy()
            _set_note(obj, "")
            return
        before = bodies.global_shape(base)
        tool = follower_tool(lead, before)
        if obj.Operation == "Intersect":
            result = before.common(tool)
        else:
            result = before.cut(tool)
        solids = bodies.solids_of(result)
        if not solids:
            if obj.Operation == "Intersect":
                raise ExtrudeError(
                    "%s does not overlap the extrusion, so Intersect would leave nothing of it."
                    % label
                )
            raise ExtrudeError("This cut would remove all of %s." % label)
        shape = bodies.as_result(solids, refine=bool(obj.Refine))
        note = ""
        if abs(shape.Volume - before.Volume) < 1e-9 and obj.Operation == "Cut":
            note = "The extrusion no longer reaches %s; it stays as it was." % label
        _set_note(obj, note)
        obj.Shape = bodies.to_local(shape, body)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _set_note(obj, text):
    try:
        if getattr(obj, WARNING, "") != text:
            setattr(obj, WARNING, text)
    except Exception:
        pass


def _hide_helper(obj):
    if not App.GuiUp:
        return
    try:
        if "ShowInTree" in obj.ViewObject.PropertiesList:
            obj.ViewObject.ShowInTree = False
    except Exception:
        pass
    try:
        from .extrude_ui import FollowerViewProvider

        FollowerViewProvider(obj.ViewObject)
    except Exception:
        pass


def _add_source(obj, lead):
    if "Source" not in obj.PropertiesList:
        obj.addProperty(
            "App::PropertyLinkGlobal", "Source", "Extrude", "The extrude this step follows"
        )
    if obj.Source is not lead:
        obj.Source = lead


def _new_follower(body, lead, operation):
    obj = bodies.insert_after_tip(body, INTERSECT_TYPE, "ExtrudeFollower")
    ExtrudeFollower(obj)
    _mark(obj, FOLLOWER_ROLE)
    obj.Source = lead
    obj.Operation = operation
    _hide_helper(obj)
    return obj


def _new_merge(lead):
    """A Join's follower: a Combine right after the lead that merges the other bodies in."""
    from . import combine

    body = owner_body(lead)
    obj = lead.Document.addObject(INTERSECT_TYPE, "ExtrudeMerge")
    body.insertObject(obj, lead, True)
    combine.CombineFeature(obj)
    obj.Operation = "Join"
    obj.NewBody = False
    obj.KeepTools = False
    _mark(obj, FOLLOWER_ROLE)
    _add_source(obj, lead)
    _hide_helper(obj)
    return obj


def remove_follower(follower):
    bodies.remove_step(follower)


def _show_only_tip(body):
    """The body is drawn through its Tip: show exactly that step (a step added or removed
    by code left the wrong one shown)."""
    if not App.GuiUp or body is None:
        return
    tip = body.Tip
    try:
        for obj in body.Group:
            if not obj.isDerivedFrom("PartDesign::Feature") or obj.ViewObject is None:
                continue
            want = obj is tip
            if obj.ViewObject.Visibility != want:
                obj.ViewObject.Visibility = want
    except Exception:
        pass


def merge_tip(lead):
    """A Join's merge comes right after the lead: when the lead is its body's end, the
    merge is."""
    body = owner_body(lead)
    if body is None or body.Tip is not lead:
        return
    for follower in followers_of(lead):
        if is_merge(follower) and owner_body(follower) is body:
            body.Tip = follower
            _show_only_tip(body)
            return


def _save_bodies(lead, participants):
    meta = load_meta(lead)
    if participants is None:
        if "bodies" not in meta:
            return
        meta.pop("bodies")
    else:
        meta["bodies"] = [b.Name for b in participants]
    _save_meta(lead, meta)


def sync_followers(lead, participants, options, old=None):
    """Make the follower steps match the bodies the extrude acts on: keep, update, remove,
    create (like move.build). `old`: the lead this one replaces (its followers move over).
    Cut / Intersect: one ExtrudeFollower per other body. Join: one merge after the lead."""
    from . import extrude_bodies_core as core

    op = options["operation"]
    home = owner_body(lead)
    others = []
    if participants and op in ("cut", "intersect", "join"):
        others = [b for b in participants if b is not home]
    have = []
    for obj in followers_of(lead) + (
        followers_of(old) if old is not None and old is not lead else []
    ):
        if obj not in have and owner_body(obj) is not None:
            have.append(obj)
    doc = lead.Document
    plan = core.follower_plan(
        op,
        home.Name,
        [b.Name for b in others],
        [(o.Name, owner_body(o).Name, "merge" if is_merge(o) else "cut") for o in have],
    )
    for name in plan["remove"]:
        remove_follower(doc.getObject(name))
    kind = "Intersect" if op == "intersect" else "Cut"
    touched = set()
    for body in others if op in ("cut", "intersect") else []:
        name = plan["keep"].get(body.Name)
        if name is None:
            obj = _new_follower(body, lead, kind)
            touched.add(body.Name)
        else:
            obj = doc.getObject(name)
            if obj.Source is not lead:
                obj.Source = lead
            if obj.Operation != kind:
                obj.Operation = kind
        label = "%s (%s)" % (lead.Label, body.Label)
        if obj.Label != label:
            obj.Label = label
    if op == "join" and others:
        if plan["new_merge"]:
            merge = _new_merge(lead)
        else:
            merge = doc.getObject(plan["merge"])
            _add_source(merge, lead)
        tools = [t for t in merge.Tools if _alive(t) and owner_body(t) in others]
        taken = {owner_body(t).Name for t in tools}
        for body in others:
            if body.Name not in taken and body.Tip is not None:
                tools.append(body.Tip)
        if list(merge.Tools) != tools:
            merge.Tools = tools
        label = "%s (merge)" % lead.Label
        if merge.Label != label:
            merge.Label = label
    _save_bodies(lead, participants)
    merge_tip(lead)
    doc = lead.Document
    for name in touched:
        _show_only_tip(doc.getObject(name))


def preview_cuts(lead):
    """[(body, removed solid in design coordinates)] of what a Cut extrude takes away from
    each body it acts on (for a red "this goes" overlay while the dialog is open)."""
    found = []
    if lead is None or not _alive(lead):
        return found
    try:
        cut = read(lead)[1]["operation"] == "cut"
    except Exception:
        cut = False
    if not cut:
        return found
    for obj in [lead] + followers_of(lead):
        if is_merge(obj):
            continue
        body = owner_body(obj)
        try:
            base = obj.BaseFeature
            if base is None or base.Shape.isNull():
                continue
            removed = bodies.global_shape(base).cut(bodies.global_shape(obj))
            if removed.Solids:
                found.append((body, removed))
        except Exception:
            continue
    return found


def follower_problem(lead):
    """("error" | "warning", reason) of the first follower of `lead` with a problem, or
    ("", ""): the timeline shows it on the lead, the extrude's only step."""
    for obj in followers_of(lead):
        body = owner_body(obj)
        where = body.Label if body is not None else obj.Label
        if _failed(obj) and not getattr(obj, "Suppressed", False):
            try:
                text = obj.getStatusString()
            except Exception:
                text = ""
            return "error", "%s: %s" % (where, text or "this body could not be changed.")
        note = getattr(obj, WARNING, "")
        if note:
            return "warning", note
    return "", ""


def orphan_followers(doc):
    """Follower steps whose extrude is gone (deleted with FreeCAD's own Delete)."""
    return [o for o in doc.Objects if is_follower(o) and lead_of(o) is None]
