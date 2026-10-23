# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Rest (PLASTIC > CREATE > Rest) as a SciForge step (no Qt: the Rest dialog, the
golden-model builder and headless tests call this module).

A rest is a flat landing on a curved plastic wall (for a label, a switch, a PCB standoff).
You draw a closed profile on a plane that cuts the wall; the rest makes the profile a flat
face on that plane, backed by a wall of the given thickness:

- where the body bulges past the plane inside the profile, the material is cut away;
- where the body lies below the plane, a pedestal fills the gap: a flat plate `thickness`
  thick under the face, with side walls `thickness` thick down to the old wall (drafted by
  the draft angle, wider towards the body); in a thin-walled (shelled) part the old wall
  inside the pedestal is removed, so the wall stays even and the inside stays open; in a
  solid part the pedestal is solid.

"Inside" is the side of the plane where the body's centre of mass lies; Flip turns it
round. Thickness and draft default to the plastic rule (and follow it until typed over).
"""

import math

import FreeCAD as App

from . import bodies, curves, extrude, warn

FP_TYPE = "PartDesign::FeaturePython"
META = "SciForgeRest"
TYPE = "Rest"
TOL = 1e-6


class RestError(ValueError):
    """The rest cannot be built as asked; the message says why and what to try."""


def default_options(rule):
    return {
        "thickness": round(float(rule["thickness"]), 3),
        "draft": float(rule["draft_angle"]),
        "flip": False,
        "links": {"thickness": True, "draft": True},
    }


def apply_rule(options, rule):
    out = dict(options)
    links = options.get("links") or {}
    if links.get("thickness"):
        out["thickness"] = round(float(rule["thickness"]), 3)
    if links.get("draft"):
        out["draft"] = float(rule["draft_angle"])
    return out


def check_options(options):
    try:
        t = float(options["thickness"])
        d = float(options.get("draft", 0.0))
    except (TypeError, ValueError, KeyError):
        raise RestError("Thickness and draft must be numbers.")
    if t <= TOL:
        raise RestError("The thickness must be more than 0.")
    if not 0.0 <= d < 30.0:
        raise RestError("The draft angle must be 0-30 degrees.")
    return options


def _prism(face, direction, length, draft=0.0):
    """`face` swept `length` along `direction`; with a draft the outline grows by
    length * tan(draft) on the far end (a ruled loft)."""
    import Part

    if draft <= 1e-9:
        return face.extrude(direction * length)
    if face.Wires and len(face.Wires) > 1:
        raise RestError("A drafted rest needs a profile without holes: set the draft to 0.")
    grow = length * math.tan(math.radians(draft))
    wire = face.OuterWire
    try:
        far = wire.makeOffset2D(grow, 2)
    except Exception as exc:
        raise RestError("The draft could not be applied to this profile (%s)." % exc)
    far.translate(direction * length)
    if len(far.Edges) != len(wire.Edges):
        raise RestError("The draft could not be applied to this profile: set it to 0.")
    solid = Part.makeLoft([wire, far], True, True)
    if solid.isNull() or not solid.isValid():
        raise RestError("The draft could not be applied to this profile: set it to 0.")
    return solid


def _depth_range(shape, origin, inward):
    lo, hi = None, None
    for v in shape.Vertexes:
        d = (v.Point - origin).dot(inward)
        lo = d if lo is None else min(lo, d)
        hi = d if hi is None else max(hi, d)
    return lo, hi


def _first_layer(piece, origin, inward):
    """The material the profile meets first going in. Behind a shelled box's near wall the
    profile's shadow also crosses the far wall; that wall's inside face looks out towards the
    plane like the outer skin, and the rest's walls then ran through the whole inside of the
    part (journey_plastic: a rest on the front wall filled the box up to the back wall)."""
    import Part

    solids = list(piece.Solids)
    if len(solids) < 2:
        return piece
    ranges = sorted((_depth_range(s, origin, inward), i) for i, s in enumerate(solids))
    first_hi = ranges[0][0][1]
    kept = [solids[i] for (lo, _hi), i in ranges if lo <= first_hi + 1e-6]
    return Part.makeCompound(kept)


def _face_normal(face):
    u0, u1, v0, v1 = face.ParameterRange
    return face.normalAt(0.5 * (u0 + u1), 0.5 * (v0 + v1))


def inward_direction(base, origin, normal, flip=False):
    """The unit direction from the plane into the part (towards its centre of mass)."""
    centre = base.BoundBox.Center
    try:
        solids = list(base.Solids)
        total = sum(s.Volume for s in solids)
        if total > 1e-9:
            centre = App.Vector()
            for s in solids:
                centre = centre + s.CenterOfMass * (s.Volume / total)
    except Exception:
        pass
    side = (centre - origin).dot(normal)
    inward = App.Vector(normal) * (-1.0 if side < 0 else 1.0)
    if flip:
        inward = inward * -1.0
    return inward


def rest_shape(base, faces, origin, normal, options):
    """The body (global) with the rest made on the profile faces (global, on the plane)."""
    # removeSplitter() on a result can corrupt the shapes it was made from (FreeCAD 1.1.4,
    # shared sub-shapes): work on a copy
    base = base.copy()
    t = float(options["thickness"])
    draft = float(options.get("draft", 0.0))
    inward = inward_direction(base, origin, normal, bool(options.get("flip")))
    out = inward * -1.0
    reach = max(50.0, 3.0 * base.BoundBox.DiagonalLength)
    zout = [f.extrude(out * reach) for f in faces]
    whole_in = [f.extrude(inward * reach) for f in faces]
    piece = base.common(whole_in)
    if piece.isNull() or not piece.Solids or piece.Volume < 1e-9:
        raise RestError(
            "The profile does not lie over the body: draw it on a plane that cuts the part "
            "(or flip the side)."
        )
    piece = _first_layer(piece, origin, inward)
    # the old outer skin (faces looking out) and inner skin (faces looking in) under it
    outer_depth = None
    inner = []
    for f in piece.Faces:
        try:
            n = _face_normal(f)
        except Exception:
            continue
        lo, hi = _depth_range(f, origin, inward)
        if n.dot(out) > 0.05:
            outer_depth = hi if outer_depth is None else max(outer_depth, hi)
        elif n.dot(inward) > 0.05:
            inner.append((f, lo, hi))
    if outer_depth is None:
        outer_depth = 0.0
    outer_depth = max(outer_depth, 0.0)
    walls = [f for f, lo, _hi in inner if lo <= outer_depth + 3.0 * t]
    plate = [f.extrude(inward * t) for f in faces]
    cut = list(zout)
    if not walls:
        # a solid part: a solid pedestal down into it
        depth = outer_depth + t
        add = [_prism(f, inward, depth, draft) for f in faces]
    else:
        depth = max(hi for f, lo, hi in inner if lo <= outer_depth + 3.0 * t) + 0.01
        depth = max(depth, t + 0.01)
        shadow = [f.extrude(inward * reach) for f in walls]
        shadow_shape = shadow[0].fuse(shadow[1:]) if len(shadow) > 1 else shadow[0]
        add = list(plate)
        for f in faces:
            envelope = _prism(f, inward, depth, draft)
            try:
                inner_face = f.makeOffset2D(-t, 2)
            except Exception as exc:
                raise RestError("The profile is too small for this thickness (%s)." % exc)
            if inner_face.isNull() or not inner_face.Faces or inner_face.Area < 1e-6:
                raise RestError("The profile is too small for this thickness.")
            inner_face = inner_face.Faces[0]
            inner_face.translate(inward * t)
            hollow = _prism(inner_face, inward, max(depth - t, 0.02), draft)
            pedestal = envelope.cut(hollow)
            add.append(pedestal.cut(shadow_shape))
            cut.append(hollow.cut(shadow_shape))
    result = base.cut(cut)
    result = result.fuse(add)
    try:
        result = result.removeSplitter()
    except Exception:
        pass
    if result.isNull() or not result.Solids or not result.isValid():
        raise RestError("The rest could not be joined to the body.")
    return result


# -- the step --------------------------------------------------------------------------------------
def is_rest(obj):
    return bodies.alive(obj) and getattr(obj, "SciForgeType", "") == TYPE


def load_meta(obj):
    return bodies.load_meta(obj, META)


class RestFeature:
    """SciForge's Rest step. Saved files store "sciforge.plastic_rest.RestFeature": never
    rename."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Rest"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSubListGlobal", "Profiles", "The closed sketch profiles")
        if add("App::PropertyLength", "Thickness", "Wall thickness under the flat face"):
            obj.Thickness = 2.0
        if add("App::PropertyAngle", "Draft", "Draft of the side walls"):
            obj.Draft = 0.0
        add("App::PropertyBool", "Flip", "The other side of the plane is the inside")
        if add("App::PropertyBool", "Refine", "Merge coplanar faces, like Fusion"):
            obj.Refine = True
        bodies.mark(obj, TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            compute(obj)
        except Exception:
            bodies.pass_through(obj)
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _refs(obj):
    found = []
    for linked, subs in obj.Profiles or []:
        for sub in subs or [""]:
            found.append((linked, sub))
    return found


def options_of(obj):
    meta = load_meta(obj)
    options = {
        "thickness": obj.Thickness.Value,
        "draft": obj.Draft.Value,
        "flip": bool(obj.Flip),
        "links": dict(meta.get("links") or {}),
    }
    return options


def resolved(obj, body=None):
    """The rest's options, the values linked to the rule read from the body's rule now (a
    body without a rule keeps the values the rest was made with: a design never changes with
    the user's library settings)."""
    options = options_of(obj)
    if any((options.get("links") or {}).values()):
        try:
            from . import plastic

            rule = plastic.rule_for_body(body or curves.owner_body(obj), fallback=False)
            if rule is not None:
                options = apply_rule(options, rule)
        except Exception as exc:
            warn("rest: the plastic rule could not be read: %s" % exc)
    return options


def profile_plane(refs):
    sketch = refs[0][0]
    if not curves.is_sketch(sketch):
        raise RestError("Pick a closed profile of a sketch.")
    placement = sketch.getGlobalPlacement()
    normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
    normal.normalize()
    return sketch, App.Vector(placement.Base), normal


def profile_faces(refs):
    if not refs:
        raise RestError("Select a closed sketch profile for the rest.")
    if len({o.Name for o, _ in refs}) != 1:
        raise RestError("The profiles of a rest must be in one sketch.")
    faces = extrude.global_faces(refs)
    if not faces:
        raise RestError("The profile is not closed: a rest needs a closed sketch profile.")
    return faces


def compute(obj):
    import Part

    base_feature = obj.BaseFeature
    if base_feature is None or base_feature.Shape.isNull() or not base_feature.Shape.Solids:
        raise RestError("A rest needs a body: make the part first.")
    base = curves.to_global(base_feature.Shape, base_feature)
    body = curves.owner_body(obj)
    options = check_options(resolved(obj, body))
    refs = _refs(obj)
    faces = profile_faces(refs)
    _sketch, origin, normal = profile_plane(refs)
    result = rest_shape(base, faces, origin, normal, options)
    if body is not None:
        result = bodies.to_local(result, body)
    if obj.Refine:
        try:
            result = result.removeSplitter()
        except Exception:
            pass
    solids = result.Solids
    obj.Shape = solids[0] if len(solids) == 1 else Part.makeCompound(solids)


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .plastic_rest_ui import ViewProviderRest

        ViewProviderRest(obj.ViewObject)
    except Exception as exc:
        warn("rest view provider: %s" % exc)


def write(obj, refs, options):
    by_obj = {}
    for linked, sub in refs:
        by_obj.setdefault(linked.Name, (linked, []))[1].append(sub)
    obj.Profiles = [(linked, subs) for linked, subs in by_obj.values()]
    obj.Thickness = float(options["thickness"])
    obj.Draft = float(options.get("draft", 0.0))
    if bool(obj.Flip) != bool(options.get("flip")):
        obj.Flip = bool(options.get("flip"))
    bodies.save_meta(obj, META, {"v": 1, "links": dict(options.get("links") or {})})


def make(body, refs, options, name="Rest", feature=None):
    """Create the rest in `body` (or rebuild `feature`)."""
    refs = extrude.normalize(list(refs))
    check_options(options)
    profile_faces(refs)
    if feature is None:
        if body is None:
            raise RestError("A rest needs a body: make the part first.")
        before = body.Tip
        if before is None or before.Shape.isNull() or not before.Shape.Solids:
            raise RestError("A rest needs a body with a solid: make the part first.")
        feature = bodies.insert_after_tip(body, FP_TYPE, name)
        RestFeature(feature)
        _attach_view_provider(feature)
    write(feature, refs, options)
    feature.touch()
    return feature


def read(feature):
    return _refs(feature), options_of(feature)


def body_under(doc, refs, flip=False):
    """The solid body the profile lies over (nearest along the inside direction), or None."""
    try:
        faces = profile_faces(refs)
        _sketch, origin, normal = profile_plane(refs)
    except RestError:
        return None
    sketch_body = curves.owner_body(refs[0][0])
    if sketch_body is not None and bodies.has_solid(sketch_body):
        return sketch_body
    best = None
    for body in bodies.solid_bodies(doc):
        shape = bodies.global_shape(body)
        try:
            common = shape.common([f.extrude(normal * 1000.0) for f in faces])
            common2 = shape.common([f.extrude(normal * -1000.0) for f in faces])
            vol = common.Volume + common2.Volume
        except Exception:
            continue
        if vol > 1e-6 and (best is None or vol > best[0]):
            best = (vol, body)
    return best[1] if best else None
