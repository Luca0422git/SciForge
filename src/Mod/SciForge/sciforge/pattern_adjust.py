# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pattern Compute Option "Adjust", and patterns of an extrude that changed several bodies
(no Qt: pattern.py's feature, the dialogs and the golden-model builder use it).

Fusion's Compute Option (Rectangular / Circular / Path Pattern, Mirror):
  Optimized  identical copies, fastest (Fusion copies the feature's faces)
  Identical  identical copies (the feature's result copied)
  Adjust     every copy is computed again where it lands, "almost as if it were a separate
             feature" (Autodesk Community, Jeff Strater): an extrude To Object ends on the
             object at every copy, a cut Through All goes through the part where the copy is
SciForge builds Optimized and Identical alike (the copies are the feature's tool, moved).
Adjust runs the extrude again for every copy: its profile moved to the copy, the same extent
(Distance, To Object, All), the object it goes to left where it is (extrude_prism.build, the
code of SciForge's own extrude). Features that are no extrude (holes, revolves, fillets...)
have nothing to adjust: their copies stay identical.

A pattern of a multi-body extrude: the extrude is one step that changed several bodies
(its hidden follower steps cut the other bodies, extrude_bodies.py). Fusion repeats that
change in every body, so the pattern gets a PatternFollower (modify_bodies.py) in each
body the extrude cut: it cuts the copies of the extrusion from that body too.
"""

import FreeCAD as App
import Part

from . import bodies, modify_bodies

COMPUTE = ("optimized", "identical", "adjust")
COMPUTE_LABELS = {"optimized": "Optimized", "identical": "Identical", "adjust": "Adjust"}


class AdjustError(ValueError):
    """A copy cannot be computed where it lands; the message says which and why."""


# -- reading an extrude ------------------------------------------------------------------------
def _ref_shape(obj, sub):
    """The shape an extrude goes to (a face, a plane, a body), in its body's coordinates."""
    if obj is None:
        return None
    if sub:
        try:
            return obj.getSubObject(sub)
        except Exception:
            return None
    shape = getattr(obj, "Shape", None)
    if shape is not None and not shape.isNull():
        return shape
    try:  # an origin plane has no shape: a big square in its plane
        place = obj.Placement
        normal = place.Rotation.multVec(App.Vector(0, 0, 1))
        return Part.Plane(place.Base, normal).toShape(-1e3, 1e3, -1e3, 1e3)
    except Exception:
        return None


def _link_shape(link):
    if not link or link[0] is None:
        return None
    subs = list(link[1]) if len(link) > 1 and link[1] else [""]
    return _ref_shape(link[0], subs[0] if subs else "")


def _up_to_shape(value):
    """FreeCAD's UpToShape list [(obj, [faces])] as one compound of faces."""
    faces = []
    for item in value or []:
        obj, subs = item[0], list(item[1]) if len(item) > 1 else []
        for sub in subs or [""]:
            shape = _ref_shape(obj, sub)
            if shape is not None and not shape.isNull():
                faces += list(shape.Faces)
    if not faces:
        return None
    return faces[0] if len(faces) == 1 else Part.makeCompound(faces)


NATIVE_TYPES = {
    "Length": "Length",
    "UpToLast": "UpToLast",
    "ThroughAll": "ThroughAll",
    "UpToFace": "UpToFace",
    "UpToShape": "UpToFace",
}


def extrude_spec(feature):
    """(faces, wires, normal, spec, how) to build `feature`'s extrusion again, in its body's
    coordinates; how is "add" or "cut". None when it is no extrude SciForge can run again."""
    from . import extrude

    try:
        if extrude.is_intersect(feature):
            return _own_spec(feature)
        if feature.TypeId in ("PartDesign::Pad", "PartDesign::Pocket"):
            return _native_spec(feature)
    except Exception:
        return None
    return None


def _own_spec(feature):
    from . import extrude

    operation = getattr(feature, "Operation", "Intersect")
    if operation not in ("Join", "Cut"):
        return None
    thin = bool(getattr(feature, "Thin", False))
    faces, curves = [], []
    for linked, subs in feature.Profiles:
        for sub in subs or [""]:
            faces += extrude.local_faces(linked, sub)
            if thin:
                curves += extrude.local_curves(linked, sub)
    wires = extrude.chain_wires(curves)
    profiles = [(linked, (subs or [""])[0]) for linked, subs in feature.Profiles]
    normal = extrude._profile_normal_in_body(profiles, feature)
    spec = {
        "side_type": feature.SideType,
        "reversed": feature.Reversed,
        "start_offset": feature.StartOffset.Value,
        "type": feature.Type,
        "length": feature.Length.Value,
        "taper": feature.TaperAngle.Value,
        "target": _link_shape(feature.UpToFace),
        "type2": feature.Type2,
        "length2": feature.Length2.Value,
        "taper2": feature.TaperAngle2.Value,
        "target2": _link_shape(feature.UpToFace2),
    }
    if thin:
        names = {v: k for k, v in extrude.WALL_NAMES.items()}
        spec["thin"] = {
            "location": names.get(feature.WallLocation, "side1"),
            "thickness": feature.WallThickness.Value,
            "location2": names.get(feature.WallLocation2, "side1"),
            "thickness2": feature.WallThickness2.Value,
        }
        if feature.SideType != "Two sides":
            spec["thin"]["location2"] = spec["thin"]["location"]
            spec["thin"]["thickness2"] = spec["thin"]["thickness"]
    return faces, wires, normal, spec, ("cut" if operation == "Cut" else "add")


def _native_spec(feature):
    from . import extrude

    if getattr(feature, "UseCustomVector", False):
        return None
    link = feature.Profile
    if not link or link[0] is None:
        return None
    obj, subs = link[0], list(link[1]) if link[1] else [""]
    faces = []
    for sub in subs or [""]:
        faces += extrude.local_faces(obj, sub)
    if not faces:
        return None
    sides = [("Type", "UpToFace", "UpToShape")]
    if feature.SideType == "Two sides":
        sides.append(("Type2", "UpToFace2", "UpToShape2"))
    spec = {"side_type": feature.SideType, "reversed": bool(feature.Reversed)}
    for i, (type_prop, face_prop, shape_prop) in enumerate(sides):
        method = NATIVE_TYPES.get(getattr(feature, type_prop))
        if method is None:
            return None  # UpToFirst: nothing to adjust SciForge can run again
        suffix = "" if i == 0 else "2"
        target = None
        if getattr(feature, type_prop) == "UpToFace":
            target = _link_shape(getattr(feature, face_prop))
        elif getattr(feature, type_prop) == "UpToShape":
            target = _up_to_shape(getattr(feature, shape_prop))
        if method == "UpToFace" and target is None:
            return None
        spec["type" + suffix] = method
        spec["length" + suffix] = getattr(feature, "Length" + suffix).Value
        spec["taper" + suffix] = getattr(feature, "TaperAngle" + suffix).Value
        spec["target" + suffix] = target
    normal = extrude._native_normal(feature)
    how = "cut" if feature.TypeId == "PartDesign::Pocket" else "add"
    return faces, [], normal, spec, how


# -- one copy, built again ---------------------------------------------------------------------
def _move_shape(shape, move):
    if isinstance(move, tuple):
        _tag, point, normal = move
        return shape.mirror(point, normal)
    out = shape.copy()
    out.transformShape(move.toMatrix())
    return out


def _move_vector(vector, move):
    if isinstance(move, tuple):
        _tag, _point, normal = move
        n = App.Vector(normal).normalize()
        return vector - n * (2.0 * vector.dot(n))
    return move.Rotation.multVec(vector)


def adjusted_tool(spec_tuple, move, reach):
    """The extrusion of one copy: the profile moved by `move`, the extent worked out again
    where the copy is (reach: the part it may run into). Raises AdjustError."""
    from . import extrude_prism as prism

    faces, wires, normal, spec, _how = spec_tuple
    moved = [_move_shape(f, move) for f in faces]
    moved_wires = [_move_shape(w, move) for w in wires]
    direction = _move_vector(App.Vector(normal), move)
    try:
        return prism.build(moved, direction, spec, reach=reach, wires=moved_wires)
    except prism.PrismError as exc:
        raise AdjustError(str(exc))
    except Exception as exc:
        raise AdjustError(str(exc) or "the geometry kernel failed")


def adjusted_tools(feature, moves, base_shape):
    """[(solid, "add" | "cut") for each move]: `feature` built again at every copy, or None
    when it is no extrude (its copies stay identical)."""
    spec_tuple = extrude_spec(feature)
    if spec_tuple is None:
        return None
    how = spec_tuple[4]
    reach = [base_shape] if base_shape is not None and not base_shape.isNull() else []
    out = []
    for index, move in enumerate(moves, start=1):
        try:
            out.append((adjusted_tool(spec_tuple, move, reach), how))
        except AdjustError as exc:
            raise AdjustError("Copy %d of %s: %s" % (index, feature.Label, exc))
    return out


def apply_adjusted(base_shape, per_copy, refine=True):
    """The part with every copy's own tool joined or cut: per_copy [(solid, how)]."""
    adds = [tool for tool, how in per_copy if how == "add"]
    cuts = [tool for tool, how in per_copy if how == "cut"]
    result = base_shape.copy()
    if adds:
        result = result.fuse(adds)
    if cuts:
        result = result.cut(cuts)
    if refine:
        try:
            result = result.removeSplitter()
        except Exception:
            pass
    return result


# -- multi-body extrudes ------------------------------------------------------------------------
def _extrude_followers(feature):
    """The hidden steps a multi-body extrude drives in its other bodies (cuts only: a Join
    merged the other bodies into the extrude's body, so the pattern there has them)."""
    from . import extrude_bodies

    found = []
    for obj in extrude_bodies.followers_of(feature):
        if extrude_bodies.is_merge(obj):
            continue
        if getattr(obj, "Operation", "Cut") != "Cut":
            continue
        found.append(obj)
    return found


def changed_bodies(pattern_feature):
    """{body: [original extrudes that cut it]} of the bodies other than the pattern's own
    that its originals changed."""
    from . import pattern

    home = pattern.owner_body(pattern_feature)
    found = {}
    for original in list(getattr(pattern_feature, "Originals", None) or []):
        if not bodies.alive(original):
            continue
        for follower in _extrude_followers(original):
            body = bodies.body_of(follower)
            if body is None or body is home:
                continue
            found.setdefault(body, [])
            if original not in found[body]:
                found[body].append(original)
    return found


def sync_followers(pattern_feature):
    """Give the pattern a follower in every other body its extrudes cut (and drop the ones
    no longer needed). Returns the followers."""
    from . import pattern

    if pattern_feature is None or not bodies.alive(pattern_feature):
        return []
    wanted = {}
    try:
        if pattern.kind_of(pattern_feature) is not None and not pattern.is_body_pattern(
            pattern_feature
        ):
            wanted = changed_bodies(pattern_feature)
    except Exception:
        wanted = {}
    have = modify_bodies.followers_of(pattern_feature)
    kept = []
    for obj in have:
        body = bodies.body_of(obj)
        if body in wanted:
            kept.append(obj)
            wanted.pop(body)
        else:
            modify_bodies.remove(obj)
    for body in wanted:
        try:
            kept.append(
                modify_bodies.add(body, pattern_feature, modify_bodies.PatternFollower, "Pattern")
            )
        except modify_bodies.FollowerError:
            continue
    return kept


def _moves_of(lead):
    """(kind, options, moves) of a pattern step: the copies' transforms in its body."""
    from . import pattern

    kind, options = pattern.read(lead)
    options = pattern.with_defaults(options)
    tools = None
    center = None
    if kind == "path":
        center = pattern.objects_center(options)[0]
    moves = pattern.placements(kind, options, tools, center)
    return kind, options, moves


def follower_result(obj, lead, base_shape):
    """A PatternFollower's solid: its body with the copies of every original extrude that
    cut it cut again at each copy (in that body's coordinates)."""
    from . import extrude_bodies

    body = bodies.body_of(obj)
    _kind, options, moves = _moves_of(lead)
    adjust = options.get("compute", "optimized") == "adjust"
    originals = [
        o
        for o in list(getattr(lead, "Originals", None) or [])
        if bodies.alive(o) and not getattr(o, "Suppressed", False)
    ]
    cuts = []
    for original in originals:
        if not any(bodies.body_of(f) is body for f in _extrude_followers(original)):
            continue
        spec_tuple = extrude_spec(original) if adjust else None
        if spec_tuple is not None:
            # Every copy built again where it lands, reaching this body.
            reach = [modify_bodies.shape_between(base_shape, obj, original)]
            for index, move in enumerate(moves, start=1):
                try:
                    tool = adjusted_tool(spec_tuple, move, reach)
                except AdjustError as exc:
                    raise AdjustError("Copy %d of %s: %s" % (index, original.Label, exc))
                cuts.append(modify_bodies.shape_between(tool, original, obj))
            continue
        # The extrusion as it cut this body (design coordinates), copied to every copy.
        before = bodies.global_shape(obj.BaseFeature)
        tool = extrude_bodies.follower_tool(original, before)
        home = modify_bodies.placement_of(original)
        for move in moves:
            if isinstance(move, tuple):
                _tag, point, normal = move
                moved = tool.mirror(home.multVec(point), home.Rotation.multVec(normal))
            else:
                moved = tool.copy()
                moved.transformShape(home.multiply(move).multiply(home.inverse()).toMatrix())
            cuts.append(bodies.to_local(moved, body))
    if not cuts:
        return base_shape
    result = base_shape.cut(cuts)
    solids = bodies.solids_of(result)
    if not solids:
        raise AdjustError("The copies would take all of %s." % (body.Label if body else "it"))
    return bodies.as_result(solids, refine=False)
