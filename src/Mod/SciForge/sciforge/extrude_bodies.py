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

Revolve, Sweep and Loft act on several bodies the same way (wave 4; Fusion's "Objects To
Cut"): their feature is the lead, the followers take the lead's solid from lead_tool() and
their bodies list sits in their own meta (SciForgeRevolve / SciForgeSweep / SciForgeLoft);
participants_of() is their bodies_in_way() list.

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
    ROLE,
    TOL,
    ExtrudeError,
    _mark,
    _ref_global,
    _sign1,
    extend_of,
    global_faces,
    normalize,
    options_with_defaults,
    owner_body,
    profile_normal,
    read,
    start_offset_of,
)

WARNING = "SciForgeWarning"  # timeline_ops.WARNING: the timeline shows it in yellow
USED_UP = bodies.USED_UP  # a cut that takes all of a body: the body is used up (hidden)
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


# -- the kinds of steps that act on several bodies ----------------------------------------
def lead_kind(obj):
    """Which SciForge step `obj` is when it can act on several bodies: "extrude", "revolve",
    "sweep", "loft", or "" for anything else."""
    if obj is None:
        return ""
    from . import extrude, loft, revolve, sweep

    try:
        if revolve.is_revolve(obj):
            return "revolve"
        if sweep.is_sweep(obj):
            return "sweep"
        if loft.is_loft(obj):
            return "loft"
        if extrude.is_extrude(obj):
            return "extrude"
    except Exception:
        return ""
    return ""


def _kind_module(obj):
    from . import extrude, loft, revolve, sweep

    return {"revolve": revolve, "sweep": sweep, "loft": loft}.get(lead_kind(obj), extrude)


def lead_meta(lead):
    return _kind_module(lead).load_meta(lead)


def _lead_save(lead, meta):
    _kind_module(lead)._save_meta(lead, meta)


def lead_operation(lead):
    """join | cut | intersect | new_body ... of a lead step."""
    kind = lead_kind(lead)
    if kind == "revolve":
        from . import revolve

        return revolve.read(lead)[2]["operation"]
    if kind in ("sweep", "loft"):
        return _kind_module(lead).read(lead)[-1]["operation"]
    return read(lead)[1]["operation"]


def lead_tool(lead):
    """The solid a Revolve, Sweep or Loft lead adds or takes away, in design coordinates:
    FreeCAD's own tool solid (AddSubShape) when the lead is a PartDesign Revolution, Groove,
    Pipe or Loft, else the module's tool_shape from what the step was made with."""
    if "AddSubShape" in lead.PropertiesList:
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
    kind = lead_kind(lead)
    module = _kind_module(lead)
    if kind == "revolve":
        profiles, axis, options = module.read(lead)
        return module.tool_shape(profiles, axis, options)
    if kind == "sweep":
        profiles, path, rail, options = module.read(lead)
        return module.tool_shape(profiles, path, rail, options)
    if kind == "loft":
        profiles, rails, centerline, options = module.read(lead)
        return module.tool_shape(profiles, rails, centerline, options)
    raise ExtrudeError("%s cannot act on other bodies." % lead.Label)


def bodies_in_way(doc, tool, lead=None):
    """([bodies the solid `tool` (design coordinates) passes through], [bodies it passes
    through or only touches face to face]), oldest first, each body as it was before `lead`
    (the step being previewed or edited): the bodies a Revolve, Sweep or Loft acts on by
    itself, like Extrude's in_the_way."""
    if tool is None or tool.isNull() or not tool.Solids:
        return [], []
    candidates = candidate_bodies(doc, lead)
    enough = max(VOLUME_TOL, tool.Volume * 1e-6)
    through, touching = [], []
    for body, shape in candidates:
        try:
            shared = _shared_volume(shape, tool)
            if shared is None:
                continue
            if shared > enough:
                through.append(body)
                touching.append(body)
            elif shared > VOLUME_TOL or _face_contact(shape, tool):
                touching.append(body)
        except Exception:
            continue
    return through, touching


def participants_of(feature, doc, options, tool_fn):
    """The bodies a Revolve, Sweep or Loft acts on, oldest first, from options["bodies"]: a
    list (the dialog's row), "auto" (every body the solid passes through; a Join also those
    it touches; tool_fn() gives the solid) or None (an existing step keeps its saved list;
    without one: None = the profile's body only, as before)."""
    op = options["operation"]
    if op not in ("join", "cut", "intersect"):
        return None
    wanted = options.get("bodies")
    if wanted is None and feature is not None:
        wanted = stored_bodies(feature)
    if wanted is None:
        return None
    if isinstance(wanted, str):
        found = bodies_in_way(doc, tool_fn(), lead=feature)
        wanted = found[1] if op == "join" else found[0]
    result = []
    for body in wanted:
        if _alive(body) and body.TypeId == "PartDesign::Body" and body not in result:
            result.append(body)
    return sorted(result, key=lambda b: b.ID)


def stored_bodies(feature):
    """The bodies an existing extrude (revolve, sweep, loft) acts on (its "Bodies to Cut"
    list), or None for a step made before it could act on several bodies (it acts on its
    own body)."""
    names = lead_meta(feature).get("bodies") if feature is not None else None
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


def nothing_touched(options, what="extrusion"):
    if what != "extrusion":
        # a revolve, sweep or loft
        if options["operation"] == "intersect":
            return (
                "The %s does not go through any body, so Intersect would leave nothing. "
                "Change the profile or the operation." % what
            )
        return (
            "The %s does not go through any body, so it cuts nothing. Change the profile, "
            "or use Join or New Body." % what
        )
    if options["operation"] == "intersect":
        return (
            "The extrusion does not go through any body, so Intersect would leave nothing. "
            "Change the distance or the direction."
        )
    return "The cut does not go through any body. Flip it, change the distance or the " "direction."


def step_times(doc):
    """{name: place in the design timeline} of every timeline step, of every follower (at
    the place of its extrude) and of every split-off piece (at the place of its Split Body):
    the order the timeline shows across all bodies."""
    from . import split, timeline_ops

    try:
        names = timeline_ops.timeline(doc, deps=False).names()
    except Exception:
        return {}
    times = {name: i for i, name in enumerate(names)}
    for obj in doc.Objects:
        if is_follower(obj):
            lead = getattr(obj, "Source", None)
            if lead is not None and lead.Name in times:
                times[obj.Name] = times[lead.Name]
        elif split.is_piece(obj):
            # A body split off later starts with this hidden step (and the body's own
            # FeatureBase holding it, below): without a time they read as older than every
            # step, so editing the first Extrude of the split body found its own later piece
            # "in the way" (journey_surface3: "Bodies to Join is empty", the edit refused).
            made_by = getattr(obj, "Split", None)
            if made_by is not None and made_by.Name in times:
                times[obj.Name] = times[made_by.Name]
    for obj in doc.Objects:
        if obj.TypeId == "PartDesign::FeatureBase" and obj.Name not in times:
            held = getattr(obj, "BaseFeature", None)
            if held is not None and held.Name in times:
                times[obj.Name] = times[held.Name]
    return times


def place_in(body, lead, times=None, at_marker=True, skip=()):
    """The step of `body` the extrude `lead` acts after: the last one that comes before the
    extrude in the timeline (an older extrude being edited changes each body as it was at
    that point, like Fusion rolls back to the step it edits), never past the body's Tip
    (where the marker stands) unless `at_marker` is False (a timeline move sets the Tips
    afterwards). `skip`: steps left out of the search (the follower being placed again).
    None: the body has no solid step before the extrude (it was made later)."""
    if times is None:
        times = step_times(lead.Document)
    at = times.get(lead.Name)
    tip = body.Tip
    found = None
    for obj in bodies.solid_steps(body):
        if obj is lead:
            break
        if any(obj is s for s in skip):
            continue
        t = times.get(obj.Name)
        if t is not None and at is not None and t >= at:
            break
        found = obj  # a step before the extrude (or a helper that goes with the one before)
        if at_marker and obj is tip:
            break
    return found


def insert_point(body, after, lead, times=None):
    """The object of `body` that a step moving there right after its solid step `after`
    (from place_in) goes in behind: past the sketches and planes that come before `lead` in
    the timeline too. The timeline keeps each body's own order, so a step put in ahead of an
    older sketch of that body would jump ahead of that sketch (and of the steps of other
    bodies made in between) in the timeline."""
    if after is None or lead is None:
        return after
    if times is None:
        times = step_times(lead.Document)
    at = times.get(lead.Name)
    if at is None:
        return after
    group = list(body.Group)
    try:
        start = group.index(after)
    except ValueError:
        return after
    point = after
    for obj in group[start + 1 :]:
        if obj is lead or "BaseFeature" in obj.PropertiesList:
            break  # never past a solid step (place_in chose the last one before the lead)
        t = times.get(obj.Name)
        if t is None:
            continue  # a helper: it goes with the step after it
        if t >= at:
            break
        point = obj
    return point


def before_shape(body, lead=None, times=None):
    """`body`'s solid (design coordinates) as it was before the extrude `lead` changed it:
    the step before the lead or before its follower in that body, else the body at the
    extrude's place in the timeline (an empty shape: the body did not exist yet)."""
    import Part

    if lead is None or not _alive(lead):
        return bodies.global_shape(body)
    if owner_body(lead) is body:
        step = lead.BaseFeature
        return bodies.global_shape(step) if step is not None else Part.Shape()
    for follower in followers_of(lead):
        if owner_body(follower) is body and not is_merge(follower):
            step = follower.BaseFeature
            return bodies.global_shape(step) if step is not None else Part.Shape()
    step = place_in(body, lead, times)
    return bodies.global_shape(step) if step is not None else Part.Shape()


def _merged_by(lead, body):
    for follower in followers_of(lead):
        if is_merge(follower) and any(
            owner_body(t) is body for t in (getattr(follower, "Tools", []) or [])
        ):
            return True
    return False


def _kept_when_hidden(lead):
    """Names of the bodies an existing extrude already acts on: they stay in its list when
    hidden (only a new extrude leaves hidden bodies alone)."""
    if lead is None or not _alive(lead):
        return set()
    names = {b.Name for b in acted_on(lead)}
    names |= {b.Name for b in stored_bodies(lead) or []}
    return names


def candidate_bodies(doc, lead=None):
    """[(body, its solid before the extrude)] for the bodies an extrude can act on: those
    shown and holding a solid, not used up by another step (Combine). A hidden body is left
    out of a new extrude, as one Fusion does not show is not in the way (guess); a body the
    extrude already acts on stays, hidden or not (hiding a body to see the others must not
    drop it from the extrude on the next edit)."""
    own = {f.Name for f in followers_of(lead)} if lead is not None else set()
    used = {name for name, step in bodies.consumers(doc).items() if step.Name not in own}
    kept = _kept_when_hidden(lead)
    times = step_times(doc) if lead is not None and _alive(lead) else None
    found = []
    for body in bodies.list_bodies(doc):
        if body.Name in used:
            continue
        if not bodies.is_shown(body) and body.Name not in kept:
            continue
        try:
            shape = before_shape(body, lead, times)
        except Exception:
            continue
        if shape.isNull() or not shape.Solids:
            continue
        found.append((body, shape))
    return found


THIN = 1e-5  # mm: boxes overlapping less than this only touch (no shared volume)


def _box_overlap(a, b):
    """How far two bounding boxes overlap (the thinnest axis); negative when apart."""
    return min(
        min(a.XMax, b.XMax) - max(a.XMin, b.XMin),
        min(a.YMax, b.YMax) - max(a.YMin, b.YMin),
        min(a.ZMax, b.ZMax) - max(a.ZMin, b.ZMin),
    )


def _shared_volume(shape, tool):
    """The volume `tool` shares with `shape`; None when they are apart. Boxes that only meet
    at a face (a profile on a body's top extruded upwards) share no volume: the costly
    boolean is skipped (it took 0.25 s on a plate with 144 holes)."""
    gap = _box_overlap(shape.BoundBox, tool.BoundBox)
    if gap < -1e-4:
        return None
    if gap < THIN:
        return 0.0
    return shape.common(tool).Volume


def _overlaps(shape, tool, contact=False, volume=VOLUME_TOL):
    """True when `tool` shares volume with `shape` (with contact: or shares a piece of a
    face with it, as a profile on a body's face extruded outwards does; touching along an
    edge or at a corner does not count)."""
    try:
        shared = _shared_volume(shape, tool)
        if shared is None:
            return False
        if shared > volume:
            return True
        return bool(contact) and _face_contact(shape, tool)
    except Exception:
        return False


# Quick tests before a costly boolean: a point strictly inside both solids (or inside one face
# and on another) answers at once; only when none is found does the exact boolean decide.
# The points sit at irrational fractions of a face's parameter range (a symmetric design puts
# edges at 1/2, 1/3, 1/4: a point on an edge next to a tapered neighbour said "inside") and
# keep a margin of 1 % of that range from the face's edges.
FRACTIONS = (
    (0.4142, 0.5858),
    (0.2929, 0.3820),
    (0.7071, 0.6180),
    (0.3820, 0.7071),
    (0.6180, 0.2929),
)
MARGIN = 0.01


def _face_samples(face):
    """A few points well inside a face (clear of its edges by a margin)."""
    found = []
    try:
        u0, u1, v0, v1 = face.ParameterRange
        du, dv = (u1 - u0) * MARGIN, (v1 - v0) * MARGIN
        for fu, fv in FRACTIONS:
            u, v = u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv
            if all(
                face.isPartOfDomain(u + a, v + b)
                for a, b in ((0.0, 0.0), (du, 0.0), (-du, 0.0), (0.0, dv), (0.0, -dv))
            ):
                found.append(face.valueAt(u, v))
    except Exception:
        pass
    return found


def _on_face(face, point):
    """True when `point` (on the face's surface) lies on the face."""
    import math

    try:
        u, v = face.Surface.parameter(point)
        shifts = [0.0]
        if type(face.Surface).__name__ == "Cylinder":
            shifts += [2 * math.pi, -2 * math.pi]  # the face may use another turn of u
        return any(face.isPartOfDomain(u + du, v) for du in shifts)
    except Exception:
        return False


def _inner_points(prism, faces, normal, limit=12):
    """Points strictly inside the extrusion: points inside the profile, carried along its
    direction to the middle, a fifth and four fifths of the extrusion's length."""
    try:
        heights = [v.Point.dot(normal) for v in prism.Vertexes]
    except Exception:
        return []
    if not heights:
        return []
    low, high = min(heights), max(heights)
    found = []
    for face in faces:
        for point in _face_samples(face):
            here = point.dot(normal)
            for t in (0.5, 0.21, 0.79):
                p = point + normal * (low + (high - low) * t - here)
                try:
                    if prism.isInside(p, 1e-7, False):
                        found.append(p)
                except Exception:
                    continue
                if len(found) >= limit:
                    return found
    return found


def _starts(profiles, options):
    """The faces the extrusion starts from (global): the profile, or a thin extrude's walls
    (the hollow inside a thin wall is no part of the extrusion)."""
    from .extrude import section_faces

    try:
        return section_faces(profiles, options)
    except ExtrudeError:
        return []


def _holds_any(shape, points):
    """True when one of `points` lies strictly inside the solid `shape`."""
    box = shape.BoundBox
    for p in points:
        if not box.isInside(p):
            continue
        try:
            if shape.isInside(p, 1e-7, False):
                return True
        except Exception:
            continue
    return False


KNOWN_SURFACES = ("Plane", "Cylinder")


def _same_surface(a, b, tol):
    """False when faces `a` and `b` surely do not lie on one surface (two planes that are
    not the same plane, two cylinders not on one axis and radius, a plane and a cylinder);
    True when they may (then their common area decides)."""
    try:
        sa, sb = a.Surface, b.Surface
    except Exception:
        return True
    ta, tb = type(sa).__name__, type(sb).__name__
    if ta in KNOWN_SURFACES and tb in KNOWN_SURFACES and ta != tb:
        return False
    if ta == tb == "Plane":
        if abs(abs(sa.Axis.dot(sb.Axis)) - 1.0) > 1e-9:
            return False
        return abs((sb.Position - sa.Position).dot(sa.Axis)) <= tol
    if ta == tb == "Cylinder":
        if abs(sa.Radius - sb.Radius) > tol or abs(abs(sa.Axis.dot(sb.Axis)) - 1.0) > 1e-9:
            return False
        offset = sb.Center - sa.Center
        across = offset - sa.Axis * offset.dot(sa.Axis)
        return across.Length <= tol
    try:
        return b.distToShape(a)[0] <= tol
    except Exception:
        return True


def _face_contact(shape, tool, tol=1e-6):
    """True when a face of `tool` lies on a face of `shape` over some area: a profile on a
    body's top extruded upwards, a disc filling a round hole (its side on the hole's wall).
    Only faces whose boxes meet and that lie on one surface are compared (a distance from
    the whole body took 2 s on a plate with 144 holes)."""
    sbox = shape.BoundBox
    sbox.enlarge(1e-4)
    faces = None
    for a in tool.Faces:
        box = a.BoundBox
        box.enlarge(1e-4)
        if not box.intersect(sbox):
            continue
        if faces is None:
            faces = [(b, b.BoundBox) for b in shape.Faces]
        samples = None
        for b, bbox in faces:
            if not box.intersect(bbox) or not _same_surface(a, b, tol):
                continue
            if _surface_kind(a) in KNOWN_SURFACES and _surface_kind(b) == _surface_kind(a):
                # One surface: a point inside `a` that is on `b` means they share area.
                if samples is None:
                    samples = _face_samples(a)
                if any(_on_face(b, p) for p in samples):
                    return True
            try:
                if a.common(b).Area > tol:
                    return True
            except Exception:
                continue
    return False


def _surface_kind(face):
    try:
        return type(face.Surface).__name__
    except Exception:
        return ""


def tool_prism(profiles, options, reach=()):
    """The solid the extrusion sweeps, in design coordinates (no boolean with any body).
    "All" goes past everything in `reach`; To Object ends at a plane, a face or a body the
    way SciForge's own extrude feature ends there. Raises ExtrudeError when it cannot be
    built here."""
    from . import extrude_prism
    from .extrude import global_wires, thin_spec

    profiles = normalize(profiles)
    options = options_with_defaults(options)
    faces = global_faces(profiles)
    wires = global_wires(profiles) if options["thin"] else []
    if not faces and not wires:
        raise ExtrudeError("The profile has no closed area to extrude.")
    normal = profile_normal(profiles)
    sign = _sign1(profiles, options)
    distance = float(options["distance"])
    if options["direction"] == "symmetric":
        length = abs(distance) if options["measurement"] == "whole" else 2.0 * abs(distance)
    else:
        length = abs(distance)
    kind = {"distance": "Length", "all": "ThroughAll", "to_object": "UpToFace"}

    def target(key, extent, side):
        ref = options.get(key)
        if options[extent] != "to_object" or not ref:
            return None
        if extend_of(options, side) == "adjacent" and ref[1].startswith("Face"):
            # the face and its neighbours, in design coordinates
            from .extrude import _side_target, _to_global

            return _to_global(_side_target(ref[0].Shape, ref[1], "adjacent"), ref[0])
        return _ref_global(ref)  # a plane, a face, or a whole body's solid

    spec = {
        "side_type": {"one_side": "One side", "two_sides": "Two sides", "symmetric": "Symmetric"}[
            options["direction"]
        ],
        "reversed": sign < 0,
        "start_offset": start_offset_of(profiles, options),
        "type": kind[options["extent"]],
        "length": length,
        "taper": float(options["taper"]),
        "target": target("extent_object", "extent", 1),
        "extend": extend_of(options, 1),
        "offset": float(options.get("object_offset") or 0.0),
        "type2": kind[options["extent2"]],
        "length2": abs(float(options["distance2"])),
        "taper2": float(options["taper2"]),
        "target2": (
            target("extent_object2", "extent2", 2) if options["direction"] == "two_sides" else None
        ),
        "extend2": extend_of(options, 2),
        "offset2": float(options.get("object_offset2") or 0.0),
        "thin": thin_spec(options),
    }
    try:
        return extrude_prism.build(faces, normal, spec, reach=list(reach), wires=wires)
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
    inner = None
    for body, shape in candidates:
        try:
            gap = _box_overlap(shape.BoundBox, prism.BoundBox)
            if gap < -1e-4:
                continue  # apart
            if gap >= THIN:
                if inner is None:
                    inner = _inner_points(
                        prism, _starts(profiles, options), profile_normal(profiles)
                    )
                if _holds_any(shape, inner):
                    through.append(body)  # a point inside both: no boolean needed
                    touching.append(body)
                    continue
            shared = _shared_volume(shape, prism)  # one boolean per body for both lists
            if shared is None:
                continue
            if shared > enough:
                through.append(body)
                touching.append(body)
            elif shared > VOLUME_TOL or _face_contact(shape, prism):
                touching.append(body)
        except Exception:
            continue
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
        pieces, points = [], []
        for face in _starts(profiles, options):
            face = face.copy()
            if abs(offset) > TOL:
                face.translate(normal * offset)
            pieces.append(face.extrude(normal * (0.01 * sign)))
            # points inside the profile, just past it (a quick yes before the boolean)
            points += [p + normal * (0.005 * sign) for p in _face_samples(face)]
        for _body, shape in candidates:
            if _holds_any(shape, points):
                return True
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
    which stopped short of a body further away. A Revolve, Sweep or Loft lead: lead_tool."""
    if lead_kind(lead) in ("revolve", "sweep", "loft"):
        return lead_tool(lead)
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
        if USED_UP not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyBool", USED_UP, "SciForge", "The cut takes all of the body", 4 | 16
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
            body = owner_body(obj)
            raise ExtrudeError(
                "The extrude cannot be applied to %s: %s"
                % (body.Label if body is not None else "this body", exc)
            )

    def _build(self, obj):
        base = obj.BaseFeature
        body = owner_body(obj)
        label = body.Label if body is not None else "this body"
        _set_used_up(obj, False)
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
            # The cut takes all of the body: it is used up, like a Combine's tool body
            # (hidden, out of the browser, back when the extrude is undone, suppressed or
            # rolled back). Its solid stays as it was, so nothing later fails on an empty
            # body. Fusion removes a body a cut swallows instead of refusing (guess).
            obj.Shape = base.Shape.copy()
            _set_note(obj, "")
            _set_used_up(obj, True)
            return
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


def _set_used_up(obj, value):
    try:
        if USED_UP in obj.PropertiesList and bool(getattr(obj, USED_UP)) != bool(value):
            setattr(obj, USED_UP, bool(value))
    except Exception:
        pass


def used_up_by(lead):
    """The bodies the cut `lead` takes completely (they are used up), oldest first."""
    found = []
    for obj in followers_of(lead):
        body = owner_body(obj)
        if body is not None and getattr(obj, USED_UP, False) and body not in found:
            found.append(body)
    return found


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


def _new_follower(body, lead, operation, times=None):
    """A follower in `body` at the extrude's place in time: after the body's last step that
    comes before the extrude in the timeline (editing an older extrude must not put its cut
    after that body's later steps), or at the marker for a new extrude."""
    place = place_in(body, lead, times)
    if place is None or place is body.Tip:
        obj = bodies.insert_after_tip(body, INTERSECT_TYPE, "ExtrudeFollower")
    else:
        obj = lead.Document.addObject(INTERSECT_TYPE, "ExtrudeFollower")
        body.insertObject(obj, place, True)
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


def ends_body(body, step):
    """True when `step` is its body's end: the Tip, or followed only by its own Join's merge
    (an edited step rebuilt as another kind must become the end again)."""
    tip = getattr(body, "Tip", None) if body is not None else None
    if tip is None or step is None:
        return False
    if tip is step:
        return True
    return is_merge(tip) and tip in followers_of(step)


def _save_bodies(lead, participants):
    meta = lead_meta(lead)
    if participants is None:
        if "bodies" not in meta:
            return
        meta.pop("bodies")
    else:
        meta["bodies"] = [b.Name for b in participants]
    _lead_save(lead, meta)


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
    times = None
    for body in others if op in ("cut", "intersect") else []:
        name = plan["keep"].get(body.Name)
        if name is None:
            if times is None:
                times = step_times(doc)
            obj = _new_follower(body, lead, kind, times)
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
        cut = lead_operation(lead) == "cut"
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
            # The follower's own messages name the body already.
            return "error", text or ("%s could not be changed." % where)
        note = getattr(obj, WARNING, "")
        if note:
            return "warning", note
    return "", ""


def orphan_followers(doc):
    """Follower steps whose extrude is gone (deleted with FreeCAD's own Delete)."""
    return [o for o in doc.Objects if is_follower(o) and lead_of(o) is None]
