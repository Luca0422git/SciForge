# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Extrude on top of PartDesign. No GUI code: the Extrude command and the
golden-model builder both call this module, so they behave the same.

Profiles (what is extruded), a list of (object, sub-element):
  (sketch, "InternalFace2")   one closed region of a sketch, like a Fusion profile. A
                              circle inside a rectangle gives two regions (the ring and
                              the disc); crossing curves split regions too. FreeCAD makes
                              them when the sketch's MakeInternals is on (ensure_regions).
  (sketch, "")                the whole sketch (holes stay holes), as FreeCAD does
  (feature, "Face6")          a flat face of a body
  (sketch, "Edge3")           a sketch curve (thin extrude only: connected curves are one
                              open profile, and the wall follows it)

Options (dict, see DEFAULTS):
  operation    join | cut | intersect | new_body
  start        profile | offset | object      (+ start_offset mm / start_object ref; an
               object start follows the object when an earlier step moves it: a hidden
               ExtrudeStart helper measures the offset on every recompute)
  direction    one_side | two_sides | symmetric
  extent       distance | to_object | all     (side 1; extent2 for side 2)
  distance     mm along the profile normal; negative goes the other way (one side, two
               sides). Symmetric: each side's length ("half") or the total ("whole"),
               see measurement.
  extent_object  (object, sub) where "to_object" ends: a face, a plane or a body
  extend       To Object's Extend choice (Fusion): "face" To Selected Face (the face's surface
               extended, the default for a face), "adjacent" To Adjacent Faces (the face and
               the faces next to it, as they are: the extrusion follows the part's shape
               there), "body" To Body (where the extrusion first meets the body, the
               default for a body), "through" Through Body (on through the body to where
               it leaves it); "" = the default for the object; extend2 for side two
  object_offset  mm past the object along the extrusion (negative: stops short of it);
               object_offset2 for side two (Guess: Fusion measures it along the extrusion)
  taper        degrees, positive widens (Fusion: outward)
  distance2 / extent2 / extent_object2 / taper2   the second side (two_sides)
  flip         extent "all": go against the profile normal
  thin         Fusion's Thin Extrude: a wall along the profile's outline (closed areas,
               flat faces) or along open sketch curves, instead of the filled profile
  wall_location  side1 | center | side2: where the wall lies against the outline (side1:
               into a closed profile, on the left of an open curve), wall_thickness its
               thickness (mm); wall_location2 / wall_thickness2 for side two (two_sides)
  expressions  {"distance" | "distance2" | "taper" | "taper2": "width * 2"}: values typed as
               a formula of parameters (Fusion's fields take "width", "width*2"); they
               become expressions on the feature, so it follows the parameters
  bodies       the bodies a Join, Cut or Intersect acts on (the dialog's "Bodies to Cut"
               row): a list of bodies, "auto" (every body the extrusion passes through,
               see touched_bodies), or None (an existing extrude keeps its own list; a new
               one acts on the profile's body only, as the first version did)

What is built:
  join / cut     a PartDesign Pad / Pocket in the body the profile belongs to
  new_body       a new PartDesign Body holding a Pad (the first solid of an empty body is
                 simply a Pad there: that already is a new body)
  intersect      SciForge's ExtrudeFeature: the body keeps what lies inside the extrusion
  thin, tapers PartDesign cannot build (up to an object or a body, a join through All)
                 SciForge's ExtrudeFeature too, which then joins, cuts or intersects
A hidden PartDesign SubShapeBinder carries the profile into the feature when FreeCAD
cannot link it directly: a start offset, profiles from several sketches, or a profile
in another body. Fusion-only choices (start, measurement, operation, original picks)
are stored as JSON in the feature's hidden "SciForgeExtrude" property, so editing the
extrude from the timeline offers them again.

Several bodies (Fusion's extrude acts on every body it passes through, one timeline step):
the feature above is the "lead", in the profile's body when that body takes part, else in
the oldest one that does. Every other body gets a hidden "follower" step that the lead
drives (SciForgeRole "ExtrudeFollower", never a timeline step of its own):
  cut / intersect  an ExtrudeFollower (below) that cuts that body with the lead's
                   extrusion, or keeps only what lies inside it
  join             one CombineFeature right after the lead that merges the other bodies
                   into the lead's body; they are then used up (hidden), like Combine's
                   tools
A Join that touches no body at all makes a new body (Fusion). Followers link the lead
("Source"), so edits, formulas and reopened files flow through it.
"""

import json

import FreeCAD as App

OPERATIONS = ("join", "cut", "intersect", "new_body", "new_component")
DIRECTIONS = ("one_side", "two_sides", "symmetric")
EXTENTS = ("distance", "to_object", "all")
STARTS = ("profile", "offset", "object")
MEASUREMENTS = ("half", "whole")
EXTENDS = ("face", "adjacent", "body", "through")
# SciForge's own feature stores the Extend choice as one of these (feature enum).
EXTEND_NAMES = {
    "face": "Selected",
    "adjacent": "Adjacent",
    "body": "Selected",
    "through": "Through",
}
WALL_LOCATIONS = ("side1", "center", "side2")
WALL_NAMES = {"side1": "Side 1", "center": "Center", "side2": "Side 2"}  # feature enum

DEFAULTS = {
    "operation": "join",
    "start": "profile",
    "start_offset": 0.0,
    "start_object": None,
    "direction": "one_side",
    "extent": "distance",
    "distance": 10.0,
    "extent_object": None,
    "extend": "",
    "object_offset": 0.0,
    "taper": 0.0,
    "extent2": "distance",
    "distance2": 10.0,
    "extent_object2": None,
    "extend2": "",
    "object_offset2": 0.0,
    "taper2": 0.0,
    "measurement": "whole",
    "flip": False,
    "bodies": None,
    "thin": False,
    "wall_location": "side1",
    "wall_thickness": 1.0,
    "wall_location2": "side1",
    "wall_thickness2": 1.0,
}

META = "SciForgeExtrude"
ROLE = "SciForgeRole"
FOLLOWER_ROLE = "ExtrudeFollower"  # hidden steps a multi-body extrude drives
INTERSECT_TYPE = "PartDesign::FeaturePython"
PLANE_TYPES = ("App::Plane", "PartDesign::Plane")
Z = App.Vector(0, 0, 1)
TOL = 1e-7


class ExtrudeError(ValueError):
    """The extrude cannot be built as asked; the message says why and what to do."""


class NeedsPick(ExtrudeError):
    """A selection box (To Object, Start: Object) waits for its click: not a mistake, the
    dialog shows it as a hint and keeps the last preview, like Fusion."""


# -- profiles -------------------------------------------------------------------------
def is_sketch(obj):
    return obj is not None and obj.isDerivedFrom("Sketcher::SketchObject")


def is_text(obj):
    """A sketch text (text.py): one profile made of all its letters."""
    return obj is not None and getattr(obj, "SciForgeType", "") == "SketchText"


def ensure_regions(sketch):
    """Turn on the sketch's regions (FreeCAD's MakeInternals): every closed area becomes
    an "InternalFaceN" that a Pad can use as its profile."""
    from . import preview, sketch_area_fill

    sketch_area_fill.install()  # the areas FreeCAD cannot make are added after its compute
    if not sketch.MakeInternals:
        sketch.MakeInternals = True
        with preview.quiet():  # a sketch FreeCAD cannot make areas from just has none
            sketch.recompute()
        _remember_empty(sketch)
    elif "Touched" in sketch.State and _being_edited(sketch):
        # A sketch open for editing with changes: FreeCAD makes its areas when it is
        # recomputed (Finish Sketch), so they would be the ones from before the changes.
        # (SciForge turns the areas on for every new sketch, so the recompute above no
        # longer does this the first time a sketch is looked at.) Only an open sketch:
        # recomputing a touched sketch inside a dialog's undo step threw away the Redo
        # list (sweep_loft_qa_sweep P4).
        with preview.quiet():
            sketch.recompute()
        _remember_empty(sketch)
    elif sketch.InternalShape.isNull() and not sketch.Shape.isNull():
        # A sketch with no closed area (a path, a rib line) never gets an InternalShape: it
        # was recomputed every time a dialog looked for areas, and inside a dialog's undo
        # step that recompute threw away the Redo list (sweep_loft_qa_sweep P4).
        stamp = _stamp(sketch)
        if stamp is not None and _EMPTY.get((sketch.Document.Name, sketch.Name)) == stamp:
            return
        with preview.quiet():
            sketch.recompute()
        _remember_empty(sketch)


_EMPTY = {}  # (document, sketch) -> stamp of a sketch shape that has no closed area


def _being_edited(sketch):
    """True if the sketch is open for editing (only with a GUI; never headless)."""
    try:
        import FreeCADGui as Gui

        gdoc = Gui.getDocument(sketch.Document.Name)
        edit = gdoc.getInEdit() if gdoc is not None else None
        return edit is not None and edit.Object is sketch
    except Exception:
        return False


def _stamp(sketch):
    try:
        return sketch.Shape.hashCode()
    except Exception:
        return None


def _remember_empty(sketch):
    try:
        if sketch.InternalShape.isNull():
            _EMPTY[(sketch.Document.Name, sketch.Name)] = _stamp(sketch)
    except Exception:
        pass


def regions(sketch):
    """[(sub-element, face in global coordinates)] for every closed region of a sketch."""
    ensure_regions(sketch)
    placement = sketch.getGlobalPlacement()
    found = []
    for i, face in enumerate(sketch.InternalShape.Faces, start=1):
        face = face.copy()
        face.Placement = placement.multiply(face.Placement)
        found.append(("InternalFace%d" % i, face))
    return found


_FACE_AREAS = {}  # (document, sketch) -> (shape stamp, {"InternalFaceN"})


def face_areas(sketch):
    """{"InternalFaceN"} of the sketch's areas that only its projected edges bound (the
    face it lies on, sketch_regions.face_areas): they are left to the face."""
    try:
        if sketch.InternalShape.isNull():
            return set()
        key = (sketch.Document.Name, sketch.Name)
        stamp = (_stamp(sketch), sketch.InternalShape.hashCode())
        cached = _FACE_AREAS.get(key)
        if cached is not None and cached[0] == stamp:
            return cached[1]
        from . import sketch_regions

        faces = list(sketch.InternalShape.Faces)
        found = {"InternalFace%d" % (i + 1) for i in sketch_regions.face_areas(sketch, faces)}
        _FACE_AREAS[key] = (stamp, found)
        return found
    except Exception:
        return set()


def profile_regions(sketch):
    """regions() without the areas only the face's projected edges bound (face_areas):
    the profiles a click or an automatic pick offers."""
    own = face_areas(sketch)
    return [(sub, face) for sub, face in regions(sketch) if sub not in own]


def taken_by_itself(sketch):
    """The areas ("InternalFaceN") Extrude / Revolve take by themselves from a sketch, or
    []: its one area; with the face's edges projected (Auto project), the areas inside the
    one area the sketch's own curves close (a rectangle drawn from a face's edge, a disc
    on a face, a rectangle over a rim split by its inner edges: what was drawn, as without
    the projected edges), else its one area that is a profile (profile_regions)."""
    named = regions(sketch)
    if len(named) > 1:
        from . import sketch_regions

        local = list(sketch.InternalShape.Faces)
        drawn = sketch_regions.drawn_regions(sketch, local) if len(local) == len(named) else []
        if drawn:
            return [named[i][0] for i in drawn]
        named = profile_regions(sketch)
    return [named[0][0]] if len(named) == 1 else []


def lost_area(sketch):
    """How much area (mm^2) the sketch's curves close that FreeCAD's own areas
    ("InternalFaceN") leave out: FreeCAD 1.1.4 makes no area where an arc ends tangent on
    the middle of a line (a rectangle drawn over a projected rounded outline), while the
    sketch's shading (sketch_regions) shows it. 0.0 when they agree or on any doubt."""
    try:
        from . import sketch_regions

        if not sketch.MakeInternals or sketch.InternalShape.isNull():
            return 0.0
        made = sum(f.Area for f in sketch.InternalShape.Faces)
        closed = sum(f.Area for f in sketch_regions.sketch_regions(sketch))
        return max(0.0, closed - made) if closed - made > 1e-6 * max(1.0, closed) else 0.0
    except Exception:
        return 0.0


def normalize(profile):
    """Profiles in the list form [(obj, sub), ...] from the forms callers use."""
    if profile is None:
        return []
    items = profile if isinstance(profile, list) else [profile]
    found, seen = [], set()
    for item in items:
        if isinstance(item, tuple):
            obj, subs = item[0], item[1] if len(item) > 1 else ""
            subs = [subs] if isinstance(subs, str) else (list(subs) or [""])
        else:
            obj, subs = item, [""]
        for sub in subs:
            key = (obj.Name, sub)
            if key not in seen:
                seen.add(key)
                found.append((obj, sub))
    return found


def key(profile):
    return (profile[0].Name, profile[1])


def owner_body(obj):
    if obj is None:
        return None
    if obj.TypeId == "PartDesign::Body":
        return obj
    parent = obj.getParentGeoFeatureGroup()
    while parent is not None and parent.TypeId != "PartDesign::Body":
        parent = parent.getParentGeoFeatureGroup()
    return parent


def _whole_sketch_faces(sketch):
    import Part

    wires = [w for w in sketch.Shape.Wires if w.isClosed()]
    if not wires:
        return []
    return list(Part.makeFace(wires, "Part::FaceMakerBullseye").Faces)


def local_faces(obj, sub):
    """Faces of one profile in its body's coordinates."""
    if is_sketch(obj):
        if sub.startswith("Internal"):
            ensure_regions(obj)
        if not sub:
            return _whole_sketch_faces(obj)
    shape = obj.getSubObject(sub) if sub else obj.Shape
    if shape is None or shape.isNull():
        return []
    return list(shape.Faces)


def _to_global(shape, obj):
    body = owner_body(obj)
    if body is None or (obj is body):
        return shape
    shape = shape.copy()
    shape.Placement = body.getGlobalPlacement().multiply(shape.Placement)
    return shape


def global_faces(profiles):
    found = []
    for obj, sub in normalize(profiles):
        found += [_to_global(face, obj) for face in local_faces(obj, sub)]
    return found


# -- curves (thin extrude) --------------------------------------------------------------------
def is_curve(profile):
    """True for a sketch curve picked as a thin extrude's open profile."""
    obj, sub = profile
    return is_sketch(obj) and (sub or "").startswith("Edge")


def local_curves(obj, sub):
    """[(key, edge)] of one profile's curves in its body's coordinates: a sketch curve, or
    the loose curves a hidden profile binder carries (key orders them as drawn)."""
    if is_sketch(obj):
        if not (sub or "").startswith("Edge"):
            return []
        try:
            edge = obj.getSubObject(sub)
        except Exception:
            return []
        if edge is None or edge.isNull() or edge.ShapeType != "Edge":
            return []
        return [((obj.Name, int(sub[4:])), edge)]
    if sub or obj is None or getattr(obj, ROLE, "") != "ExtrudeProfile":
        return []
    shape = obj.Shape
    if shape.isNull():
        return []
    taken = [e for f in shape.Faces for e in f.Edges]
    free = [e for e in shape.Edges if not any(e.isSame(t) for t in taken)]
    return [((obj.Name, i), e) for i, e in enumerate(free)]


def chain_wires(keyed_edges):
    """Connected curves as wires, each running the way its first-drawn curve runs (so
    "Side 1", on the left of the curve, does not depend on the order of the picks)."""
    import Part

    edges = [e for _k, e in keyed_edges]
    if not edges:
        return []
    try:
        groups = Part.sortEdges(edges, 1e-6)
    except Exception:
        groups = [[e] for e in edges]
    wires = []
    for group in groups:
        try:
            wire = Part.Wire(group)
        except Exception:
            continue
        first = min(
            (k for k, e in keyed_edges if any(_same_edge(e, g) for g in group)),
            default=None,
        )
        drawn = next((e for k, e in keyed_edges if k == first), None)
        if drawn is not None and _runs_against(wire, drawn):
            wire = wire.reversed()
        wires.append(wire)
    return wires


def _same_edge(a, b):
    try:
        if a.isSame(b):
            return True
        u = (a.FirstParameter + a.LastParameter) / 2.0
        v = (b.FirstParameter + b.LastParameter) / 2.0
        return (a.valueAt(u) - b.valueAt(v)).Length < 1e-7 and abs(a.Length - b.Length) < 1e-7
    except Exception:
        return False


def _travel(edge, ordered=None):
    """The way `edge` runs at its middle (its orientation in a wire counts)."""
    mid = (edge.FirstParameter + edge.LastParameter) / 2.0
    tangent = edge.tangentAt(mid)
    if (ordered or edge).Orientation == "Reversed":
        tangent = tangent * -1.0
    return edge.valueAt(mid), tangent


def _runs_against(wire, drawn):
    point, way = _travel(drawn)
    for edge in wire.OrderedEdges:
        mid = (edge.FirstParameter + edge.LastParameter) / 2.0
        if (edge.valueAt(mid) - point).Length < 1e-6:
            return _travel(edge, edge)[1].dot(way) < 0
    return False


def global_wires(profiles):
    """The open curves of a thin extrude's profiles, chained, in global coordinates."""
    keyed = []
    for obj, sub in normalize(profiles):
        keyed += [(k, _to_global(e, obj)) for k, e in local_curves(obj, sub)]
    return chain_wires(keyed)


def section_faces(profiles, options):
    """The faces the extrusion starts from (global): the profile's areas and faces, or the
    walls of a thin extrude (side one's)."""
    faces = global_faces(profiles)
    if not options.get("thin"):
        return faces
    from . import extrude_prism

    try:
        walls = extrude_prism.thin_walls(
            faces,
            global_wires(profiles),
            profile_normal(profiles),
            options["wall_location"],
            options["wall_thickness"],
        )
    except extrude_prism.PrismError as exc:
        raise ExtrudeError(str(exc))
    return [w.face for w in walls]


def profile_point(profiles):
    """A point on the profile: inside its first area or face, else the middle of its first
    curve (global)."""
    faces = global_faces(profiles)
    if faces:
        return interior_point(faces[0])
    wires = global_wires(profiles)
    if wires:
        edge = wires[0].OrderedEdges[0]
        return edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
    raise ExtrudeError("The profile has no closed area to extrude.")


def face_normal(face):
    """Outward normal at the middle of a face (normalAt already handles Reversed faces)."""
    u0, u1, v0, v1 = face.ParameterRange
    return face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)


def interior_point(face):
    """A point inside the face (a ring's centre of mass is in its hole)."""
    center = face.CenterOfMass
    try:
        if face.isInside(center, 1e-6, True):
            return center
        u0, u1, v0, v1 = face.ParameterRange
        n = 20
        points, inside = {}, set()
        for i in range(n + 1):
            for j in range(n + 1):
                p = face.valueAt(u0 + (u1 - u0) * i / float(n), v0 + (v1 - v0) * j / float(n))
                points[(i, j)] = p
                if face.isInside(p, 1e-6, True):
                    inside.add((i, j))
        # Prefer a sample whose neighbours are inside too: clear of the edges.
        deep = [
            k
            for k in inside
            if all((k[0] + a, k[1] + b) in inside for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        ]
        for pool in (deep, list(inside)):
            if pool:
                # the one nearest the middle (a ring: next to the hole)
                return min((points[k] for k in pool), key=lambda p: (p - center).Length)
    except Exception:
        pass
    return center


def profile_normal(profiles, local=False):
    """The Fusion extrude direction for distance > 0: the sketch's normal, or the outward
    normal of a picked body face. Global unless local=True (body coordinates)."""
    profiles = normalize(profiles)
    if not profiles:
        raise ExtrudeError("Select a profile first.")
    obj, sub = profiles[0]
    if is_sketch(obj) or is_text(obj):
        placement = obj.Placement if local else obj.getGlobalPlacement()
        return placement.Rotation.multVec(Z)
    faces = local_faces(obj, sub)
    if not faces:
        raise ExtrudeError("The picked face no longer exists. Pick the profile again.")
    normal = face_normal(faces[0])
    if not local:
        body = owner_body(obj)
        if body is not None and body is not obj:
            normal = body.getGlobalPlacement().Rotation.multVec(normal)
    return normal


def profile_frame(profiles):
    """(a point inside the first profile, its normal), global: where the arrow goes."""
    return profile_point(profiles), profile_normal(profiles)


def check_profiles(profiles, thin=False):
    """Raise ExtrudeError unless the profiles can be extruded together. A thin extrude also
    takes sketch curves (open profiles)."""
    profiles = normalize(profiles)
    if not profiles:
        raise ExtrudeError("Select a profile: click inside a sketch area or on a flat face.")
    normal = profile_normal(profiles)
    for obj, sub in profiles:
        if is_curve((obj, sub)):
            if not thin:
                raise ExtrudeError(
                    "A sketch curve is a profile of a thin extrude only. Choose Thin Extrude, "
                    "or click inside a closed area."
                )
            if not local_curves(obj, sub):
                raise ExtrudeError("A curve picked from %s is gone. Pick it again." % obj.Label)
            own = obj.getGlobalPlacement().Rotation.multVec(Z)
            if abs(abs(own.dot(normal)) - 1.0) > 1e-6:
                raise ExtrudeError(
                    "All profiles must lie in parallel planes. Extrude the others separately."
                )
            continue
        faces = local_faces(obj, sub)
        if not faces:
            raise ExtrudeError(
                "%s has no closed area to extrude. Close the sketch's outline." % obj.Label
            )
        for face in faces:
            if face.Surface.TypeId != "Part::GeomPlane":
                raise ExtrudeError("Only flat faces can be extruded. Pick a flat face or a sketch.")
            n = _to_global(face, obj)
            if abs(abs(face_normal(n).dot(normal)) - 1.0) > 1e-6:
                raise ExtrudeError(
                    "All profiles must lie in parallel planes. Extrude the others separately."
                )
    return profiles


def expand_whole(profiles):
    """Profiles with every "whole sketch" entry replaced by the sketch areas it covers
    (holes stay out), so a dialog can show and toggle them one by one."""
    found = []
    for obj, sub in normalize(profiles):
        if not (is_sketch(obj) and sub == ""):
            found.append((obj, sub))
            continue
        try:
            whole = [_to_global(f, obj) for f in _whole_sketch_faces(obj)]
            for name, face in regions(obj):
                point = interior_point(face)
                if any(w.isInside(point, 1e-6, True) for w in whole):
                    found.append((obj, name))
        except Exception:
            found.append((obj, sub))
    return normalize(found)


def profile_label(profiles):
    profiles = normalize(profiles)
    if not profiles:
        return "Nothing selected"
    curves = [p for p in profiles if is_curve(p)]
    if curves:
        names = sorted({obj.Label for obj, _ in profiles})
        areas = len(profiles) - len(curves)
        text = "%d curve%s" % (len(curves), "" if len(curves) == 1 else "s")
        if areas:
            text += " + %d profile%s" % (areas, "" if areas == 1 else "s")
        return "%s (%s)" % (text, ", ".join(names))
    if len(profiles) == 1:
        obj, sub = profiles[0]
        if is_sketch(obj):
            return "%s (whole sketch)" % obj.Label if not sub else "1 profile of %s" % obj.Label
        if is_text(obj):
            return "%s (text)" % obj.Label
        return "1 face of %s" % obj.Label
    names = sorted({obj.Label for obj, _ in profiles})
    return "%d profiles (%s)" % (len(profiles), ", ".join(names))


# -- options ----------------------------------------------------------------------------
def options_with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in (options or {}).items() if v is not None or k in merged})
    if merged["operation"] not in OPERATIONS:
        raise ExtrudeError("unknown operation %r" % merged["operation"])
    if merged["direction"] not in DIRECTIONS:
        raise ExtrudeError("unknown direction %r" % merged["direction"])
    for name in ("extent", "extent2"):
        if merged[name] == "through_all":
            merged[name] = "all"
        if merged[name] not in EXTENTS:
            raise ExtrudeError("unknown extent %r" % merged[name])
    if merged["start"] not in STARTS:
        raise ExtrudeError("unknown start %r" % merged["start"])
    if merged["measurement"] not in MEASUREMENTS:
        raise ExtrudeError("unknown measurement %r" % merged["measurement"])
    merged["thin"] = bool(merged.get("thin"))
    for name in ("wall_location", "wall_location2"):
        if merged[name] not in WALL_LOCATIONS:
            raise ExtrudeError("unknown wall location %r" % merged[name])
    for name in ("extend", "extend2"):
        merged[name] = merged.get(name) or ""
        if merged[name] and merged[name] not in EXTENDS:
            raise ExtrudeError("unknown extend %r" % merged[name])
    for name in ("object_offset", "object_offset2"):
        merged[name] = float(merged.get(name) or 0.0)
    return merged


def object_kind(ref):
    """What a To Object pick is: "plane" (an origin or construction plane, a flat face's
    plane is a face), "face" or "body" (a whole solid), or "" for nothing."""
    if not ref or ref[0] is None:
        return ""
    obj, sub = ref
    if obj.TypeId in PLANE_TYPES:
        return "plane"
    if sub and sub.startswith("Face"):
        return "face"
    if not sub:
        try:
            if obj.Shape.Solids:
                return "body"
        except Exception:
            pass
    return "face"


def extend_choices(ref):
    """Fusion's Extend choices for a To Object pick: a face [face, adjacent], a body [body,
    through], a plane none (a plane is endless)."""
    kind = object_kind(ref)
    if kind == "face":
        return ["face", "adjacent"]
    if kind == "body":
        return ["body", "through"]
    return []


def extend_of(options, side=1):
    """The Extend choice in use for a side (the object's default when none was made)."""
    suffix = "" if side == 1 else "2"
    ref = options.get("extent_object" + suffix)
    choices = extend_choices(ref)
    if not choices:
        return ""
    wanted = options.get("extend" + suffix) or ""
    if wanted in choices:
        return wanted
    return choices[0]


def adjacent_names(shape, face_name):
    """The face and the faces sharing an edge with it ("FaceN" names of `shape`): Fusion's
    To Adjacent Faces ends the extrusion on all of them as they are."""
    import Part

    face = shape.getElement(face_name)
    names = [face_name]
    for edge in face.Edges:
        try:
            neighbours = shape.ancestorsOfType(edge, Part.Face)
        except Exception:
            continue
        for other in neighbours:
            for i, candidate in enumerate(shape.Faces, start=1):
                if candidate.isSame(other):
                    name = "Face%d" % i
                    if name not in names:
                        names.append(name)
                    break
    return names


def _side_target(shape, sub, extend):
    """The shape a side ends on: the picked face (or body), or for To Adjacent Faces the
    face and its neighbours as one compound (never extended)."""
    import Part

    if extend == "adjacent" and sub.startswith("Face"):
        names = adjacent_names(shape, sub)
        return Part.Compound([shape.getElement(n) for n in names])
    return shape.getElement(sub) if sub else shape


def thin_spec(options):
    """The prism builder's "thin" entry (extrude_prism.build), or None."""
    if not options.get("thin"):
        return None
    two = options["direction"] == "two_sides"
    return {
        "location": options["wall_location"],
        "thickness": float(options["wall_thickness"]),
        "location2": options["wall_location2" if two else "wall_location"],
        "thickness2": float(options["wall_thickness2" if two else "wall_thickness"]),
    }


def taper_possible(options, extent):
    """True if a taper can be built with this extent. Always: what PartDesign's Pad and
    Pocket cannot taper (up to an object, a join through All) SciForge's own extrude
    feature builds (see own_feature_needed)."""
    return True


def native_taper(operation, extent):
    """True if PartDesign tapers this extent itself: Distance, and a cut's All (ThroughAll).
    FreeCAD's Pad and Pocket silently ignore a taper up to a face, and a Pad's UpToLast."""
    return extent == "distance" or (extent == "all" and operation == "cut")


def own_feature_needed(options):
    """True when the extrude is SciForge's own feature instead of a Pad/Pocket: Intersect,
    thin extrudes (PartDesign has no thin Pad) and tapers PartDesign cannot build (Fusion
    tapers every extent)."""
    if options["operation"] == "intersect" or options.get("thin"):
        return True
    sides = [("extent", "taper", 1)]
    if options["direction"] == "two_sides":
        sides.append(("extent2", "taper2", 2))
    for extent, taper, side in sides:
        if abs(float(options[taper])) > 1e-9 and not native_taper(
            options["operation"], options[extent]
        ):
            return True
        if options[extent] == "to_object":
            # Fusion's To Adjacent Faces, Through Body and an offset from the object: Pad and
            # Pocket have none of them (their "up to face" extends the face).
            suffix = "" if side == 1 else "2"
            if extend_of(options, side) in ("adjacent", "through"):
                return True
            if abs(float(options.get("object_offset" + suffix) or 0.0)) > 1e-9:
                return True
    return False


def curved_face(ref):
    """True when a To Object pick is a face that is not flat (a cylinder, a sphere...)."""
    if object_kind(ref) != "face":
        return False
    try:
        faces = _ref_shape(ref).Faces
    except Exception:
        return False
    return any(face.Surface.TypeId != "Part::GeomPlane" for face in faces)


def curved_elsewhere(options, target):
    """True when a side ends To Object on a curved face of another body than `target` (the
    body the extrude goes in; None: a new one). FreeCAD's Pad / Pocket "up to face" ends in
    the wrong place there (a post up to a cylinder of another body went through it: 22494
    mm^3 instead of 4753, golden extrude_to_cylinder_face); SciForge's own feature ends
    exactly on the face. A curved face of the same body is right with the Pad, which stays
    (an older Pad with later steps on it could not change its kind)."""
    sides = [("extent", "")]
    if options["direction"] == "two_sides":
        sides.append(("extent2", "2"))
    for extent, suffix in sides:
        ref = options.get("extent_object" + suffix)
        if options[extent] != "to_object" or not curved_face(ref):
            continue
        if target is None or owner_body(ref[0]) is not target:
            return True
    return False


def check_options(options):
    """Raise ExtrudeError for values Fusion's dialog would reject."""
    sides = [("extent", "distance", "extent_object", "taper", "")]
    if options["direction"] == "two_sides":
        sides.append(("extent2", "distance2", "extent_object2", "taper2", " (side two)"))
    for extent, distance, target, taper, where in sides:
        if options[extent] == "distance" and abs(float(options[distance])) < 1e-6:
            raise ExtrudeError("The distance%s must not be zero." % where)
        if options[extent] == "to_object" and options.get(target) is None:
            raise NeedsPick("Click the face, plane or body to extrude to%s." % where)
        if abs(float(options[taper])) >= 89.9:
            raise ExtrudeError("The taper angle%s must be between -89.9 and 89.9 degrees." % where)
    if options.get("thin"):
        walls = [("wall_thickness", "")]
        if options["direction"] == "two_sides":
            walls.append(("wall_thickness2", " (side two)"))
        for key, where in walls:
            if float(options[key]) < 1e-6:
                raise ExtrudeError("The wall thickness%s must be more than zero." % where)
    if options["direction"] == "symmetric" and options["extent"] == "to_object":
        raise ExtrudeError("Symmetric extrudes go a distance or through all.")
    if options["start"] == "object" and options.get("start_object") is None:
        raise NeedsPick("Click the face or plane the extrusion starts from.")


def feature_type(operation, options=None):
    """FreeCAD type of the feature an operation (with these options) builds."""
    if operation == "intersect" or (options is not None and own_feature_needed(options)):
        return INTERSECT_TYPE
    if operation == "cut":
        return "PartDesign::Pocket"
    return "PartDesign::Pad"


# The operation of SciForge's own extrude feature (its "Operation" property).
OWN_OPERATIONS = {
    "intersect": "Intersect",
    "join": "Join",
    "new_body": "Join",
    "new_component": "Join",
    "cut": "Cut",
}


def _ref_shape(ref):
    obj, sub = ref
    if sub:
        return obj.getSubObject(sub)
    return obj.Shape


def _ref_global(ref):
    obj, sub = ref
    shape = obj.getSubObject(sub) if sub else obj.Shape
    if obj.TypeId in PLANE_TYPES:
        shape = obj.Shape.copy()
        shape.Placement = obj.getGlobalPlacement()
        return shape
    return _to_global(shape, obj)


def _plane_of_ref(ref):
    """(point, normal) of a flat face or plane reference (global), or None."""
    shape = _ref_global(ref)
    if shape is None or shape.isNull():
        return None
    faces = shape.Faces
    if len(faces) != 1 or faces[0].Surface.TypeId != "Part::GeomPlane":
        return None
    return faces[0].CenterOfMass, face_normal(faces[0])


def start_offset_of(profiles, options):
    """Signed start offset along the profile normal (mm)."""
    if options["start"] == "offset":
        return float(options["start_offset"])
    if options["start"] == "object":
        if not options.get("start_object"):
            raise NeedsPick("Click the face or plane the extrusion starts from.")
        plane = _plane_of_ref(options["start_object"])
        if plane is None:
            raise ExtrudeError("Start from a flat face or a plane.")
        point, normal = plane
        n = profile_normal(profiles)
        if abs(abs(normal.dot(n)) - 1.0) > 1e-6:
            raise ExtrudeError(
                "The start face must be parallel to the profile. Pick a parallel face or plane."
            )
        origin = profile_point(profiles)
        return (point - origin).dot(n)
    return 0.0


def side_of(ref, profiles, options):
    """+1 if the object lies along the profile normal, else -1 (To Object picks the side)."""
    shape = _ref_global(ref)
    origin = profile_point(profiles)
    origin = origin + profile_normal(profiles) * start_offset_of(profiles, options)
    n = profile_normal(profiles)
    if shape is None or shape.isNull():
        return 1.0
    if shape.Faces and len(shape.Faces) == 1:
        target = shape.Faces[0].CenterOfMass
    else:
        target = shape.BoundBox.Center
    if shape.Faces and len(shape.Faces) == 1 and shape.Faces[0].Surface.TypeId == "Part::GeomPlane":
        plane = shape.Faces[0]
        normal = face_normal(plane)
        denom = n.dot(normal)
        if abs(denom) > 1e-9:  # where the profile normal line meets the plane
            t = (plane.CenterOfMass - origin).dot(normal) / denom
            return 1.0 if t >= 0 else -1.0
    return 1.0 if (target - origin).dot(n) >= 0 else -1.0


def _sign1(profiles, options):
    if options["direction"] == "symmetric":
        return 1.0
    if options["extent"] == "to_object":
        return side_of(options["extent_object"], profiles, options)
    sign = 1.0 if float(options["distance"]) >= 0 else -1.0
    if options["extent"] == "all" and options.get("flip"):
        sign = -sign  # "All" keeps the side the distance was on; Flip turns it round
    return sign


# -- meta --------------------------------------------------------------------------------
def _ref_json(ref):
    if not ref:
        return None
    return [ref[0].Name, ref[1]]


def _ref_load(doc, data):
    if not data:
        return None
    obj = doc.getObject(data[0])
    return (obj, data[1]) if obj is not None else None


def load_meta(feature):
    try:
        text = getattr(feature, META, "")
        return json.loads(text) if text else {}
    except Exception:
        return {}


def _save_meta(feature, meta):
    if META not in feature.PropertiesList:
        feature.addProperty("App::PropertyString", META, "SciForge", "Fusion extrude options", 0)
        feature.setEditorMode(META, 2)  # hidden
    text = json.dumps(meta, sort_keys=True)
    if getattr(feature, META) != text:
        setattr(feature, META, text)


def _mark(obj, role):
    if ROLE not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", ROLE, "SciForge", "What SciForge made this for", 0)
        obj.setEditorMode(ROLE, 2)
    setattr(obj, ROLE, role)


def is_helper(obj):
    return getattr(obj, ROLE, "") in ("ExtrudeProfile", "ExtrudeRef", START_ROLE, FOLLOWER_ROLE)


# -- Start: Object follows the object ------------------------------------------------------
START_ROLE = "ExtrudeStart"
START_TYPE = "Part::Part2DObjectPython"  # a Body takes only sketch-like helpers


class ExtrudeStart:
    """Fusion's Start: Object keeps the extrusion starting on its object when an earlier
    step moves that face or plane. The start offset is the profile's binder's placement
    (_binder); this hidden helper (in the body, just before the binder) measures the offset
    from the profile to the object on every recompute, and the binder's Placement is an
    expression on its Shift. Saved documents store "sciforge.extrude.ExtrudeStart": keep the
    name and the properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Extrude Start", doc)

        add("App::PropertyLinkSubListGlobal", "Profiles", "The profiles that are extruded")
        add(
            "App::PropertyLinkSubGlobal", "StartObject", "The face or plane the extrusion starts on"
        )
        add("App::PropertyDistance", "Offset", "From the profile to the object (worked out)")
        add("App::PropertyPlacement", "Shift", "The profile moved onto the object (body coords)")
        for name in ("Offset", "Shift"):
            try:
                obj.setPropertyStatus(name, "Output")
            except Exception:
                pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        import Part

        profiles = []
        for linked, subs in obj.Profiles:
            for sub in subs or [""]:
                profiles.append((linked, sub))
        link = obj.StartObject
        if not profiles or not link or link[0] is None:
            raise ExtrudeError("The extrusion's start object is gone. Edit it and pick one.")
        ref = (link[0], (list(link[1]) or [""])[0])
        offset = start_offset_of(profiles, {"start": "object", "start_object": ref})
        if abs(obj.Offset.Value - offset) > 1e-12:
            obj.Offset = offset
        body = owner_body(obj)
        rot = body.getGlobalPlacement().Rotation if body is not None else App.Rotation()
        shift = App.Placement(
            rot.inverted().multVec(profile_normal(profiles) * offset), App.Rotation()
        )
        if not obj.Shift.isSame(shift, 1e-12):
            obj.Shift = shift
        a = profile_point(profiles)
        obj.Shape = Part.Vertex(a + profile_normal(profiles) * offset)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _start_helper(body, feature, binder, profiles, ref, existing=None):
    """The ExtrudeStart helper that keeps `binder` on the start object (made or updated)."""
    helper = existing
    if helper is None:
        helper = body.Document.addObject(START_TYPE, "ExtrudeStart")
        ExtrudeStart(helper)
        body.insertObject(helper, binder, False)  # just before the binder
        _mark(helper, START_ROLE)
        try:
            if App.GuiUp:
                helper.ViewObject.Visibility = False
                if "ShowInTree" in helper.ViewObject.PropertiesList:
                    helper.ViewObject.ShowInTree = False
        except Exception:
            pass
    links = {}
    order = []
    for obj, sub in profiles:
        if obj.Name not in links:
            links[obj.Name] = (obj, [])
            order.append(obj.Name)
        if sub:
            links[obj.Name][1].append(sub)
    helper.Profiles = [(links[n][0], links[n][1] or [""]) for n in order]
    helper.StartObject = (ref[0], [ref[1]] if ref[1] else [])
    helper.Label = "%s start" % feature.Label
    helper.recompute()
    expr = "%s.Shift" % helper.Name
    if dict(binder.ExpressionEngine).get("Placement") != expr:
        binder.setExpression("Placement", expr)
    return helper


# -- the intersect feature -----------------------------------------------------------------
def _set_enum(obj, prop, items):
    """(Re)set an enumeration's choices, keeping its value (older files lack new ones)."""
    try:
        current = getattr(obj, prop)
    except Exception:
        current = None
    try:
        if list(obj.getEnumerationsOfProperty(prop) or []) == list(items):
            return
    except Exception:
        pass
    setattr(obj, prop, list(items))
    if current in items:
        setattr(obj, prop, current)


class ExtrudeFeature:
    """SciForge's own extrude: Intersect (the body keeps what lies inside the extrusion),
    thin extrudes, and Join/Cut with a taper PartDesign cannot build (up to an object or
    a body, a join through All). Saved documents store "sciforge.extrude.ExtrudeFeature":
    keep the name stable; files from before "Operation" existed are Intersect extrudes."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Extrude"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSubList", "Profiles", "The profiles that are extruded")
        if add("App::PropertyEnumeration", "Operation", "Intersect, join or cut"):
            obj.Operation = ["Intersect", "Join", "Cut"]
        if add("App::PropertyEnumeration", "SideType", "One side, two sides or symmetric"):
            obj.SideType = ["One side", "Two sides", "Symmetric"]
        for suffix in ("", "2"):
            add("App::PropertyEnumeration", "Type" + suffix, "How far the side goes")
            _set_enum(obj, "Type" + suffix, ["Length", "ThroughAll", "UpToFace", "UpToLast"])
            add("App::PropertyLength", "Length" + suffix, "Distance")
            add("App::PropertyAngle", "TaperAngle" + suffix, "Taper angle (+ widens)")
            add("App::PropertyLinkSub", "UpToFace" + suffix, "Face or plane where the side ends")
            if add(
                "App::PropertyEnumeration",
                "Extend" + suffix,
                "To Object: the face extended, the face and its neighbours, or through the body",
            ):
                setattr(obj, "Extend" + suffix, ["Selected", "Adjacent", "Through"])
            add("App::PropertyDistance", "ObjectOffset" + suffix, "Offset past the object")
        add("App::PropertyBool", "Reversed", "Go against the profile's normal")
        add("App::PropertyDistance", "StartOffset", "Start this far from the profile plane")
        if add("App::PropertyBool", "Refine", "Merge coplanar faces, like Fusion"):
            obj.Refine = True
        # Thin extrude (files from before these existed are solid extrudes).
        add("App::PropertyBool", "Thin", "A wall along the profile instead of the area", "Thin")
        for suffix in ("", "2"):
            if add(
                "App::PropertyEnumeration",
                "WallLocation" + suffix,
                "Where the wall lies against the profile",
                "Thin",
            ):
                setattr(obj, "WallLocation" + suffix, [WALL_NAMES[k] for k in WALL_LOCATIONS])
            if add("App::PropertyLength", "WallThickness" + suffix, "Wall thickness", "Thin"):
                setattr(obj, "WallThickness" + suffix, 1.0)
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
            obj.SciForgeType = "Extrude"

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        from . import extrude_prism as prism

        base = obj.BaseFeature
        has_base = base is not None and not base.Shape.isNull() and bool(base.Shape.Solids)
        operation = getattr(obj, "Operation", "Intersect")
        if not has_base and operation != "Join":
            raise ExtrudeError(
                "%s needs a solid before it in the timeline."
                % ("Cut" if operation == "Cut" else "Intersect")
            )
        thin = bool(getattr(obj, "Thin", False))
        faces, curves = [], []
        for linked, subs in obj.Profiles:
            for sub in subs or [""]:
                faces += local_faces(linked, sub)
                if thin:
                    curves += local_curves(linked, sub)
        wires = chain_wires(curves)
        if not faces and not wires:
            raise ExtrudeError("Select a profile to extrude.")
        profiles = [(linked, (subs or [""])[0]) for linked, subs in obj.Profiles]
        normal = _profile_normal_in_body(profiles, obj)

        def target(link, suffix):
            if not link or link[0] is None:
                return None
            linked, subs = link[0], link[1]
            sub = subs[0] if subs else ""
            extend = getattr(obj, "Extend" + suffix, "Selected")
            if extend == "Adjacent" and sub.startswith("Face"):
                return _side_target(linked.Shape, sub, "adjacent")
            return _ref_shape((linked, sub))

        def extend(suffix):
            value = getattr(obj, "Extend" + suffix, "Selected")
            return {"Adjacent": "adjacent", "Through": "through"}.get(value, "")

        def offset(suffix):
            prop = getattr(obj, "ObjectOffset" + suffix, None)
            return prop.Value if prop is not None else 0.0

        spec = {
            "side_type": obj.SideType,
            "reversed": obj.Reversed,
            "start_offset": obj.StartOffset.Value,
            "type": obj.Type,
            "length": obj.Length.Value,
            "taper": obj.TaperAngle.Value,
            "target": target(obj.UpToFace, ""),
            "extend": extend(""),
            "offset": offset(""),
            "type2": obj.Type2,
            "length2": obj.Length2.Value,
            "taper2": obj.TaperAngle2.Value,
            "target2": target(obj.UpToFace2, "2"),
            "extend2": extend("2"),
            "offset2": offset("2"),
        }
        if thin:
            names = {v: k for k, v in WALL_NAMES.items()}
            spec["thin"] = {
                "location": names.get(obj.WallLocation, "side1"),
                "thickness": obj.WallThickness.Value,
                "location2": names.get(obj.WallLocation2, "side1"),
                "thickness2": obj.WallThickness2.Value,
            }
            if obj.SideType != "Two sides":
                spec["thin"]["location2"] = spec["thin"]["location"]
                spec["thin"]["thickness2"] = spec["thin"]["thickness"]
        self.tool = None
        try:
            tool = prism.build(
                faces, normal, spec, reach=[base.Shape] if has_base else [], wires=wires
            )
            self.tool = tool  # the extruded volume (body coordinates), for the cut preview
            if operation == "Intersect":
                result = base.Shape.common(tool)
            elif operation == "Cut":
                result = base.Shape.cut(tool)
            else:
                result = base.Shape.fuse(tool) if has_base else tool
            if obj.Refine:
                result = result.removeSplitter()
        except prism.PrismError as exc:
            raise ExtrudeError(str(exc))
        if result.isNull() or not result.Solids or result.Volume < TOL:
            if operation == "Cut":
                raise ExtrudeError("This cut would remove the whole body.")
            raise ExtrudeError(
                "The extrusion does not overlap the body, so Intersect would leave nothing."
            )
        if len(result.Solids) > 1 and not _allows_pieces(obj):
            raise ExtrudeError(
                "%s would leave %d separate pieces; a body holds one solid. "
                "Change the profile or the distance." % (operation, len(result.Solids))
            )
        if operation == "Cut" and abs(result.Volume - base.Shape.Volume) < 1e-9:
            raise ExtrudeError("The cut does not touch the body. Flip it or pick another object.")
        if len(result.Solids) == 1:
            obj.Shape = result.Solids[0]
        else:
            import Part

            obj.Shape = Part.makeCompound(result.Solids)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _allows_pieces(feature):
    """True when the feature's body may hold several separate solids (FreeCAD 1.1's
    "AllowCompound", on by default; PartDesign's Pad accepts a join that leaves two pieces
    there too, and a thin extrude of a ring is two walls)."""
    body = owner_body(feature)
    return body is None or bool(getattr(body, "AllowCompound", False))


def _profile_normal_in_body(profiles, feature):
    """Profile normal in the coordinates of the feature's body."""
    obj = profiles[0][0]
    if is_helper(obj) or owner_body(obj) is not owner_body(feature):
        normal = _helper_normal(obj, feature)
        if normal is not None:
            return normal
    return profile_normal(profiles, local=True)


def _helper_normal(binder, feature):
    """For a binder-carried profile: the original profile's normal, stored in the meta."""
    meta = load_meta(feature)
    vec = meta.get("normal")
    if vec:
        return App.Vector(*vec)
    return None


def is_intersect(obj):
    return getattr(obj, "SciForgeType", "") == "Extrude" and obj.TypeId == INTERSECT_TYPE


def is_extrude(obj):
    return obj is not None and (
        obj.TypeId in ("PartDesign::Pad", "PartDesign::Pocket") or is_intersect(obj)
    )


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .extrude_ui import ViewProviderExtrude

        ViewProviderExtrude(obj.ViewObject)
    except Exception:
        pass


# -- building ---------------------------------------------------------------------------------
def _has_solid(body, before=None):
    """True if `body` already has a solid where the new feature goes."""
    tip = before.BaseFeature if before is not None else body.Tip
    return tip is not None and not tip.Shape.isNull() and bool(tip.Shape.Solids)


def _links_to(obj, target, skip=("BaseFeature",)):
    for prop in obj.PropertiesList:
        if prop in skip:
            continue
        try:
            kind = obj.getTypeIdOfProperty(prop)
        except Exception:
            continue
        if "Link" not in kind or "Hidden" in kind:
            continue
        try:
            value = getattr(obj, prop)
        except Exception:
            continue
        if _contains(value, target):
            return True
    return False


def _contains(value, target):
    if value is target:
        return True
    if isinstance(value, (list, tuple)):
        return any(_contains(v, target) for v in value)
    return False


def dependents(feature):
    """Later features that use this extrude's own faces/edges (not just its result).

    A fillet/chamfer/draft/shell right after the extrude names its edges or faces on its
    BaseFeature (`Base` is the BaseFeature): that is the history chain, which follows a
    swapped extrude, and timeline_ops.settle() finds those edges again afterwards (as
    timeline_ops.uses() treats it). Counting it blocked Join -> Cut whenever a round came
    next, e.g. an extrude added with the marker rolled back before a fillet."""
    found = []
    for obj in feature.InList:
        if obj.TypeId in ("PartDesign::Body", "App::Part") or is_helper(obj):
            continue
        skip = ("BaseFeature",)
        if getattr(obj, "BaseFeature", None) is feature and _base_object(obj) is feature:
            skip = ("BaseFeature", "Base")
        if _links_to(obj, feature, skip):
            found.append(obj)
    return found


def _base_object(obj):
    try:
        base = obj.Base
    except Exception:
        return None
    return base[0] if isinstance(base, (list, tuple)) and base else base


def _source_body(profiles):
    body = owner_body(profiles[0][0])
    if body is None:
        raise ExtrudeError("The profile must belong to a body. Use Create Sketch first.")
    return body


def _needs_binder(target_body, profiles, options):
    if options["start"] != "profile":
        return True
    if len({obj.Name for obj, _ in profiles}) != 1:
        return True
    obj = profiles[0][0]
    return owner_body(obj) is not target_body


def _direct_profile(profiles):
    obj = profiles[0][0]
    subs = [sub for _, sub in profiles]
    if "" in subs:
        return obj  # the whole sketch
    return (obj, subs)


def _insert(body, type_id, name, before=None):
    """New feature in `body`: at the timeline marker, or just before `before`."""
    doc = body.Document
    if before is not None:
        obj = doc.addObject(type_id, name)
        body.insertObject(obj, before, False)
        return obj
    obj = body.newObject(type_id, name)
    return obj


FRAME = "SciForgeFrame"  # where another body's profile sits in this body (fixed at creation)
FRAME_OF = "SciForgeFrameOf"  # the container that frame was taken against


def _container(obj):
    """(the body or part holding `obj`, or None at the document root, its global placement)."""
    body = owner_body(obj)
    if body is not None:
        return body, body.getGlobalPlacement()
    parent = obj.getParentGeoFeatureGroup()
    if parent is not None:
        return parent, parent.getGlobalPlacement()
    return None, App.Placement()


def _freeze_frame(binder, body, container, container_placement):
    """Remember, once, where the profile's container sits in `body`.

    A New Body made from a sketch in another body must stay the same solid when a joint
    later moves either body: with FreeCAD's default (Relative) binding the copied profile
    follows the sketch's *global* position, so the body's own geometry would shift every
    time the solver moved it. The frame is taken when the binder is made and kept through
    later edits, so the body keeps its shape; it is taken again only when the profile moves
    to a different body."""
    name = container.Name if container is not None else ""
    if FRAME not in binder.PropertiesList:
        binder.addProperty("App::PropertyPlacement", FRAME, "SciForge", "Profile frame", 0)
        binder.setEditorMode(FRAME, 2)
        binder.addProperty("App::PropertyString", FRAME_OF, "SciForge", "Profile container", 0)
        binder.setEditorMode(FRAME_OF, 2)
    elif getattr(binder, FRAME_OF, None) == name:
        return
    frame = body.getGlobalPlacement().inverse().multiply(container_placement)
    setattr(binder, FRAME, frame)
    setattr(binder, FRAME_OF, name)


def _frozen_placement(binder, support, container_placement, shift):
    """The binder placement for a non-relative copy: frame * start shift * where the copied
    shapes sit in the profile's container. FreeCAD copies several shapes in their object's
    parent's coordinates, a single one with its own placement stripped."""
    import Part

    frame = getattr(binder, FRAME)
    obj, subs = support[0]
    shapes = sum(max(1, len(s)) for _, s in support)
    own = obj.getGlobalPlacement().multiply(obj.Placement.inverse())  # obj's parent, global
    if shapes == 1:
        # FreeCAD strips the copied shape's own placement (a sketch's, a face's): put it back
        try:
            strip = Part.getShape(obj, subs[0] if subs else "", needSubElement=True).Placement
        except Exception:
            strip = obj.Placement
        own = own.multiply(strip)
    local = container_placement.inverse().multiply(own)  # copy -> container coordinates
    local_shift = container_placement.Rotation.inverted().multVec(shift)
    return frame.multiply(App.Placement(local_shift, App.Rotation()).multiply(local))


def _binder(body, feature, sources, offset, existing=None, role="ExtrudeProfile"):
    """A hidden SubShapeBinder in `body`, just before `feature`, copying `sources`."""
    doc = body.Document
    binder = existing
    if binder is None:
        binder = doc.addObject("PartDesign::SubShapeBinder", "ExtrudeProfile")
        body.insertObject(binder, feature, False)
        _mark(binder, role)
        binder.Label = "%s profile" % feature.Label
    grouped = {}
    order = []
    for obj, sub in sources:
        if obj.Name not in grouped:
            grouped[obj.Name] = (obj, [])
            order.append(obj.Name)
        if sub:
            grouped[obj.Name][1].append(sub)
    support = [(grouped[n][0], tuple(grouped[n][1])) for n in order]
    container, container_placement = _container(support[0][0])
    cross = role == "ExtrudeProfile" and container is not body
    if cross:
        _freeze_frame(binder, body, container, container_placement)
    if "Relative" in binder.PropertiesList and binder.Relative == cross:
        binder.Relative = not cross  # before Support: setting Support copies at once
    binder.Support = support
    shift = App.Vector(offset)
    if cross:
        binder.Placement = _frozen_placement(binder, support, container_placement, shift)
    else:
        rot = body.getGlobalPlacement().Rotation
        binder.Placement = App.Placement(rot.inverted().multVec(shift), App.Rotation())
    try:
        binder.Visibility = False
    except Exception:
        pass
    if App.GuiUp:
        try:
            binder.ViewObject.Visibility = False
            if "ShowInTree" in binder.ViewObject.PropertiesList:
                binder.ViewObject.ShowInTree = False
        except Exception:
            pass
    return binder


def _local_ref(body, feature, ref, helpers, old_refs, extend=""):
    """A reference FreeCAD may link from `feature` (same body); otherwise a hidden binder
    (re-used from the last update when there is one). To Adjacent Faces on a face of
    another body: the binder carries the face and its neighbours (linked whole)."""
    obj, sub = ref
    if obj.TypeId in PLANE_TYPES and owner_body(obj) is body:
        return (obj, "")
    if owner_body(obj) is body:
        if obj is body:
            raise ExtrudeError("Pick a face of the body, a plane, or another body to extrude to.")
        return (obj, sub)
    existing = old_refs.pop(0) if old_refs else None
    sources = [ref]
    adjacent = extend == "adjacent" and sub.startswith("Face")
    if adjacent:
        sources = [(obj, name) for name in adjacent_names(obj.Shape, sub)]
    binder = _binder(body, feature, sources, App.Vector(), existing=existing, role="ExtrudeRef")
    binder.Label = "%s target" % feature.Label
    helpers.append(binder)
    if adjacent:
        return (binder, "")
    return (binder, "Face1" if sub.startswith("Face") else "")


def _native_normal(feature):
    """The direction FreeCAD's Pad/Pocket extrudes before 'Reversed' (body coordinates)."""
    import Part

    obj, subs = feature.Profile[0], list(feature.Profile[1]) if feature.Profile else []
    if obj.isDerivedFrom("Part::Part2DObject"):
        normal = obj.Placement.Rotation.multVec(Z)
    else:
        shapes = [obj.getSubObject(s) if s else obj.Shape for s in (subs or [""])]
        shapes = [s for s in shapes if s is not None and not s.isNull()]
        compound = shapes[0] if len(shapes) == 1 else Part.Compound(shapes)
        plane = compound.findPlane()
        if plane is not None:
            normal = App.Vector(plane.Axis)
        else:
            normal = face_normal(compound.Faces[0])
    if feature.TypeId == "PartDesign::Pocket":
        normal = normal * -1.0
    return normal


def facing_faces(shape, toward):
    """Names of the faces of `shape` an extrusion going `toward` runs into: those facing back
    at it. FreeCAD's "up to shape" fails on a whole body ("Unable to reach the selected
    shape, please select faces", and an empty face list silently extrudes nothing), so a
    body picked as Fusion's To Object is handed over as these faces."""
    names = []
    for i, face in enumerate(shape.Faces, start=1):
        try:
            if face_normal(face).dot(toward) < -1e-6:
                names.append("Face%d" % i)
        except Exception:
            continue
    return names


def _side_props(feature, suffix, extent, length, taper, ref, cut, toward=None):
    setattr(feature, "TaperAngle" + suffix, float(taper))
    if extent == "distance":
        setattr(feature, "Type" + suffix, "Length")
        setattr(feature, "Length" + suffix, max(abs(float(length)), 1e-6))
    elif extent == "all":
        setattr(feature, "Type" + suffix, "ThroughAll" if cut else "UpToLast")
    else:
        obj, sub = ref
        is_shape = not sub and obj.TypeId not in PLANE_TYPES
        if is_shape and "UpToShape" + suffix in feature.PropertiesList:
            names = facing_faces(obj.Shape, toward) if toward is not None else []
            if not names:
                raise ExtrudeError(
                    "Nothing of %s faces the extrusion in this direction. Flip it, or pick a "
                    "face of it." % obj.Label
                )
            setattr(feature, "Type" + suffix, "UpToShape")
            setattr(feature, "UpToShape" + suffix, [(obj, names)])
        else:
            setattr(feature, "Type" + suffix, "UpToFace")
            setattr(feature, "UpToFace" + suffix, (obj, [sub] if sub else [""]))


def _apply(feature, body, profiles, options, refs):
    """Write the options onto the feature (its Profile/Profiles is already set)."""
    want = profile_normal(profiles, local=False)
    want = body.getGlobalPlacement().Rotation.inverted().multVec(want)
    sign = _sign1(profiles, options)
    direction = options["direction"]
    distance = float(options["distance"])
    if direction == "symmetric":
        length = abs(distance) if options["measurement"] == "whole" else 2.0 * abs(distance)
    else:
        length = abs(distance)
    side_type = {"one_side": "One side", "two_sides": "Two sides", "symmetric": "Symmetric"}[
        direction
    ]
    if is_intersect(feature):
        feature.Operation = OWN_OPERATIONS[options["operation"]]
        feature.SideType = side_type
        feature.Reversed = sign < 0
        feature.StartOffset = 0.0  # a start offset travels with the profile's binder
        _fp_side(
            feature,
            "",
            options["extent"],
            length,
            options["taper"],
            refs.get(1),
            extend_of(options, 1),
            options["object_offset"],
        )
        if direction == "two_sides":
            _fp_side(
                feature,
                "2",
                options["extent2"],
                options["distance2"],
                options["taper2"],
                refs.get(2),
                extend_of(options, 2),
                options["object_offset2"],
            )
        _fp_thin(feature, options)
        feature.Refine = True
        return
    cut = feature.TypeId == "PartDesign::Pocket"
    feature.SideType = side_type
    toward = want * sign  # body coordinates, like a binder's shape
    _side_props(feature, "", options["extent"], length, options["taper"], refs.get(1), cut, toward)
    if direction == "two_sides":
        _side_props(
            feature,
            "2",
            options["extent2"],
            options["distance2"],
            options["taper2"],
            refs.get(2),
            cut,
            toward * -1.0,
        )
    native = _native_normal(feature)
    feature.Reversed = (want * sign).dot(native) < 0
    if hasattr(feature, "Refine"):
        feature.Refine = True
    if hasattr(feature, "AllowMultiFace"):
        feature.AllowMultiFace = True


def _fp_side(feature, suffix, extent, length, taper, ref, extend="", offset=0.0):
    if ("Extend" + suffix) not in feature.PropertiesList:
        ExtrudeFeature.ensure_properties(feature)
    name = EXTEND_NAMES.get(extend, "Selected") if extent == "to_object" else "Selected"
    if getattr(feature, "Extend" + suffix) != name:
        setattr(feature, "Extend" + suffix, name)
    value = float(offset) if extent == "to_object" else 0.0
    if abs(getattr(feature, "ObjectOffset" + suffix).Value - value) > 1e-12:
        setattr(feature, "ObjectOffset" + suffix, value)
    setattr(feature, "TaperAngle" + suffix, float(taper))
    setattr(feature, "Length" + suffix, max(abs(float(length)), 1e-6))
    if extent == "distance":
        setattr(feature, "Type" + suffix, "Length")
    elif extent == "all":
        # A join goes as far as the part reaches (Pad's UpToLast); a cut through it all.
        join = getattr(feature, "Operation", "Intersect") == "Join"
        setattr(feature, "Type" + suffix, "UpToLast" if join else "ThroughAll")
    else:
        # A flat face or plane, a curved face (its whole surface) or a whole body (where the
        # extrusion first meets it): extrude_prism ends the side there, taper included.
        obj, sub = ref
        setattr(feature, "Type" + suffix, "UpToFace")
        setattr(feature, "UpToFace" + suffix, (obj, [sub] if sub else [""]))


def _fp_thin(feature, options):
    """A thin extrude's wall on SciForge's own feature (Fusion's Thin Extrude)."""
    if "Thin" not in feature.PropertiesList:
        ExtrudeFeature.ensure_properties(feature)
    thin = bool(options.get("thin"))
    if feature.Thin != thin:
        feature.Thin = thin
    for suffix, location, thickness in (
        ("", "wall_location", "wall_thickness"),
        ("2", "wall_location2", "wall_thickness2"),
    ):
        name = WALL_NAMES[options[location]]
        if getattr(feature, "WallLocation" + suffix) != name:
            setattr(feature, "WallLocation" + suffix, name)
        value = max(float(options[thickness]), 1e-6)
        if abs(getattr(feature, "WallThickness" + suffix).Value - value) > 1e-12:
            setattr(feature, "WallThickness" + suffix, value)


# Dialog value -> the feature property that holds it (Pad, Pocket and SciForge's own).
EXPRESSION_PROPS = {
    "distance": "Length",
    "distance2": "Length2",
    "taper": "TaperAngle",
    "taper2": "TaperAngle2",
    "wall_thickness": "WallThickness",
    "wall_thickness2": "WallThickness2",
    "object_offset": "ObjectOffset",
    "object_offset2": "ObjectOffset2",
}


def _expression_used(key, options):
    two = options["direction"] == "two_sides"
    if key == "distance":
        return options["extent"] == "distance"
    if key == "distance2":
        return two and options["extent2"] == "distance"
    if key == "taper2":
        return two
    if key == "wall_thickness":
        return bool(options.get("thin"))
    if key == "wall_thickness2":
        return bool(options.get("thin")) and two
    if key == "object_offset":
        return options["extent"] == "to_object"
    if key == "object_offset2":
        return two and options["extent2"] == "to_object"
    return True


def _wrap(key, expr, options):
    """The property's expression for a dialog value's formula: a negative distance is a
    reversed extrude of the positive length, a symmetric half length is half of it."""
    if key != "distance":
        return expr
    if options["direction"] == "symmetric":
        return "2 * (%s)" % expr if options["measurement"] == "half" else expr
    return "-(%s)" % expr if float(options["distance"]) < 0 else expr


def _unwrap(key, expr, options):
    for head in ("2 * (", "-("):
        if key == "distance" and expr.startswith(head) and expr.endswith(")"):
            return expr[len(head) : -1]
    return expr


def _apply_expressions(feature, options):
    """Formulas typed in the dialog become expressions on the feature's properties; a value
    typed as a plain number (or dragged) removes the formula again."""
    from . import parameters, parameters_core

    typed = options.get("expressions") or {}
    names = parameters.user_names(feature.Document)
    engine = dict(feature.ExpressionEngine)
    for key, prop in EXPRESSION_PROPS.items():
        if prop not in feature.PropertiesList:
            continue
        text = (typed.get(key) or "").strip()
        if text and _expression_used(key, options):
            expr = _wrap(key, parameters_core.to_freecad(text, names), options)
            if engine.get(prop) != expr:
                feature.setExpression(prop, expr)
        elif prop in engine:
            feature.setExpression(prop, None)


# What a field takes (its DistanceField unit) -> (what it is called, an example).
FIELD_KINDS = {"mm": ("a length", "25"), "deg": ("an angle", "30"), "": ("a number", "3")}


def _article(word):
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word


def check_kind(value, unit, text):
    """Fusion's formulas carry units and a field takes only its own kind: a length formula
    ("width", "width / 2") in an angle field, an angle in a distance field or a length in a
    count is refused (FreeCAD would take the bare number: 40 mm read as 40 degrees). A
    formula without a unit counts in the field's unit. Raises ExtrudeError with the reason."""
    if unit not in FIELD_KINDS:
        return
    found = getattr(value, "Unit", None)
    if found is None or found == App.Units.Unit():
        return
    wanted = App.Units.Quantity("1 " + unit).Unit if unit else App.Units.Unit()
    if found == wanted:
        return
    kind = (getattr(found, "Type", "") or "").lower()
    what, example = FIELD_KINDS[unit]
    raise ExtrudeError(
        "'%s' is %s, not %s. Type %s, for example %s."
        % (text, _article(kind) if kind else "a value with a unit", what, what, example)
    )


def evaluate(doc, text, unit=None):
    """Value of a formula typed in a field ("width * 2", "=width+5 mm"): a float in mm (or
    degrees for an angle). ``unit``: the field's unit ("mm", "deg", "" for a plain number);
    a formula of another kind is refused (check_kind). Raises ExtrudeError with the reason
    when it is no value."""
    from . import parameters, parameters_core

    text = (text or "").strip().lstrip("=").strip()
    expr = parameters_core.to_freecad(text, parameters.user_names(doc))
    host = parameters.container(doc)
    if host is None:
        if not doc.Objects:
            raise ExtrudeError("%s is not a value." % text)
        host = doc.Objects[0]
    try:
        value = host.evalExpression(expr)
    except Exception as exc:
        raise ExtrudeError("'%s' is not a value here: %s" % (text, exc))
    if unit is not None:
        check_kind(value, unit, text)
    try:
        return float(getattr(value, "Value", value))
    except Exception:
        raise ExtrudeError("'%s' is not a number." % text)


def hide_sketches(profiles):
    """Fusion hides a profile's sketch once the extrude is made (OK), not before: while the
    dialog is open the sketch stays in view (Luca, R6)."""
    if not App.GuiUp:
        return
    for obj, _ in profiles:
        if is_text(obj):
            obj = obj.Sketch  # the text goes with its sketch (text_ui keeps them together)
        if is_sketch(obj):
            try:
                # Only a visible one: setting it again is a change FreeCAD records, and an
                # edit OK'd without a change then left an undo step that did nothing.
                if obj.ViewObject.Visibility:
                    obj.ViewObject.Visibility = False
            except Exception:
                pass


_hide_sketches = hide_sketches  # first-version name


def _new_body(src_body, component=False):
    """A new body beside the source body (New Body), or inside a new component (New
    Component, Fusion's fifth operation)."""
    from . import components

    return components.body_for_new(src_body, component)


def _structure(feature, profiles, options, participants=None):
    """(target body or None for 'make a new one', feature type, needs binder).
    `participants`: the bodies a multi-body extrude acts on (None: the profile's body)."""
    src = _source_body(profiles)
    meta = load_meta(feature) if feature is not None else {}
    created = None
    if feature is not None and meta.get("created_body"):
        created = feature.Document.getObject(meta["created_body"])
    op = options["operation"]
    if created is not None:
        from .components_core import same_new

        if not same_new(meta.get("operation"), op):
            created = None  # New Body <-> New Component: the result moves (made again)
    if op in ("new_body", "new_component"):
        if created is not None:
            target = created
        elif op == "new_component":
            target = None  # always a new component with a new body in it
        elif feature is not None and owner_body(feature) is src and not _has_solid(src, feature):
            target = src  # the first solid of a body is already a new body
        elif feature is None and not _has_solid(src):
            target = src
        else:
            target = None  # a new body
    elif participants:
        from .extrude_bodies import lead_body

        target = lead_body(src, participants)
    else:
        target = src
    type_id = feature_type(op, options)
    if type_id != INTERSECT_TYPE and curved_elsewhere(options, target):
        type_id = INTERSECT_TYPE  # SciForge's own feature (see curved_elsewhere)
    return target, type_id, src


def build(profiles, options, name="Extrude", feature=None, hide=True):
    """Create the extrude, or rebuild `feature` with new profiles/options.
    Returns the feature (a different object when its kind had to change). hide=False keeps
    the profile sketches in view (the dialog's preview; it hides them on OK)."""
    from .extrude_bodies import merge_tip, nothing_touched, participants_for, sync_followers

    options = options_with_defaults(options)
    profiles = check_profiles(profiles, thin=options["thin"])
    check_options(options)
    participants = participants_for(feature, profiles, options)
    if participants is not None and not participants:
        if options["operation"] == "join":
            # Fusion: a Join that touches no body makes a new body.
            options = dict(options, operation="new_body")
            participants = None
        else:
            raise ExtrudeError(nothing_touched(options))
    elif (
        participants is None
        and options["operation"] == "join"
        and _joins_nothing(profiles, options, feature)
    ):
        options = dict(options, operation="new_body")  # (no bodies list: scripts, old steps)
    target, type_id, src = _structure(feature, profiles, options, participants)
    if feature is not None:
        same_type = feature.TypeId == type_id and (
            type_id != INTERSECT_TYPE or is_intersect(feature)
        )
        if owner_body(feature) is target and same_type:
            _update(feature, target, profiles, options, hide)
            sync_followers(feature, participants, options)
            return feature
        blocking = dependents(feature)
        if blocking:
            raise ExtrudeError(
                "%s is used by %s, and this change needs a new kind of extrude (another "
                "operation or body, or a taper FreeCAD's extrude cannot make), so it cannot be "
                "made here. Make a new extrude instead."
                % (feature.Label, ", ".join(o.Label for o in blocking))
            )
    old_meta = load_meta(feature) if feature is not None else {}
    created = None
    if target is None:
        target = created = _new_body(src, options["operation"] == "new_component")
    elif old_meta.get("created_body") == target.Name:
        created = target  # still the body this extrude made
    before = feature if (feature is not None and owner_body(feature) is target) else None
    was_tip = before is not None and target.Tip is before
    after = None
    if feature is not None and before is None and created is None:
        # The extrude moves to another body (its sketch's body was left out, or taken
        # back): it goes in at its own place in time there, not after that body's later
        # steps (the timeline would show it jump to the end, its cut would come too late).
        from .extrude_bodies import insert_point, place_in

        after = place_in(target, feature)
        if after is target.Tip:
            after = None
    if after is not None:
        new = feature.Document.addObject(type_id, name)
        target.insertObject(new, insert_point(target, after, feature), True)
    else:
        new = _insert(target, type_id, name, before)
    if feature is not None:
        _keep_timeline_place(new, feature)
    if type_id == INTERSECT_TYPE:
        ExtrudeFeature(new)
        _attach_view_provider(new)
    _save_meta(new, {"created_body": created.Name if created is not None else None})
    try:
        _update(new, target, profiles, options, hide)
    except Exception:
        # Nothing half-made stays behind; the old feature is still there, untouched.
        _remove(new, keep_body=created is None or (feature is not None and before is not None))
        raise
    # The other bodies' steps follow the new lead (before the old one goes, with its links).
    sync_followers(new, participants, options, old=feature)
    if feature is not None:
        label = feature.Label
        _remove(feature, keep_body=owner_body(feature) is target)
        new.Label = label
    if (before is None and after is None) or was_tip:
        target.Tip = new
        show_tip(target)
    elif after is not None:
        from .extrude_bodies import _show_only_tip

        _show_only_tip(target)  # the new step is in the middle: the body's end stays shown
    merge_tip(new)
    return new


def _joins_nothing(profiles, options, feature):
    """True when a Join (acting on the profile's body only) would not even touch that
    body's solid: Fusion makes a new body then, it never leaves a separate piece."""
    from .extrude_bodies import in_the_way

    src = _source_body(profiles)
    before = feature if feature is not None and owner_body(feature) is src else None
    if not _has_solid(src, before):
        return False  # the first solid of a body is a new body already
    try:
        found = in_the_way(profiles, options, lead=feature)
    except Exception:
        return False
    if found is None:
        return False  # cannot be told here: as before
    return src not in found[1]


def _keep_timeline_place(new, old):
    """A step rebuilt as a new object (another operation, another body) keeps the place of
    the one it replaces in the timeline, and its timeline group: the timeline orders steps
    by when they were made, and the new object is younger than every later step."""
    try:
        from . import timeline_ops

        key = timeline_ops._key(old)
        rank = timeline_ops.RANK
        timeline_ops._add_prop(new, "App::PropertyFloat", rank, "Place in the design timeline")
        setattr(new, rank, float(key))
        gid = getattr(old, timeline_ops.GROUP, "") or ""
        if gid:
            timeline_ops._set_group(new, gid, getattr(old, timeline_ops.GROUP_NAME, "") or "")
    except Exception as exc:
        from . import warn

        warn("extrude: the timeline place was not kept: %s" % exc)


def _update(feature, body, profiles, options, hide=True):
    meta = load_meta(feature)
    doc = feature.Document
    old_helpers = [doc.getObject(n) for n in meta.get("helpers", [])]
    old_helpers = [h for h in old_helpers if h is not None]
    old_profile = [h for h in old_helpers if getattr(h, ROLE, "") == "ExtrudeProfile"]
    old_refs = [h for h in old_helpers if getattr(h, ROLE, "") == "ExtrudeRef"]
    old_start = [h for h in old_helpers if getattr(h, ROLE, "") == START_ROLE]
    helpers = []
    normal = profile_normal(profiles)
    if _needs_binder(body, profiles, options):
        offset = start_offset_of(profiles, options)
        existing = old_profile[0] if old_profile else None
        if existing is not None and dict(existing.ExpressionEngine).get("Placement"):
            existing.setExpression("Placement", None)  # placed again below
        binder = _binder(body, feature, profiles, normal * offset, existing=existing)
        helpers.append(binder)
        link = binder
        fp_profiles = [(binder, "")]
        same_body = all(owner_body(obj) is body for obj, _sub in profiles)
        if options["start"] == "object" and same_body and options.get("start_object"):
            # Fusion: the extrusion keeps starting on its object when that moves later
            helpers.append(
                _start_helper(
                    body,
                    feature,
                    binder,
                    profiles,
                    options["start_object"],
                    old_start[0] if old_start else None,
                )
            )
    else:
        link = _direct_profile(profiles)
        fp_profiles = list(profiles)
    if is_intersect(feature):
        feature.Profiles = [(obj, [sub]) for obj, sub in fp_profiles]  # "" = whole object
    else:
        feature.Profile = link
    refs = {}
    for side, opt, ext in ((1, "extent_object", "extent"), (2, "extent_object2", "extent2")):
        if side == 2 and options["direction"] != "two_sides":
            continue
        if options[ext] == "to_object" and options.get(opt) is not None:
            refs[side] = _local_ref(
                body, feature, options[opt], helpers, old_refs, extend_of(options, side)
            )
    # Helpers that are no longer needed go (a profile binder after "start: profile", ...).
    keep = {h.Name for h in helpers}
    for helper in old_helpers:
        if helper.Name not in keep:
            _delete(helper)
    meta["normal"] = list(body.getGlobalPlacement().Rotation.inverted().multVec(normal))
    _save_meta(feature, meta)  # the intersect feature reads the normal when it computes
    _apply(feature, body, profiles, options, refs)
    _apply_expressions(feature, options)
    meta.update(
        {
            "v": 1,
            "operation": options["operation"],
            "start": options["start"],
            "start_offset": float(options["start_offset"]),
            "start_object": _ref_json(options.get("start_object")),
            "measurement": options["measurement"],
            "flip": bool(options.get("flip")),
            "profiles": [[obj.Name, sub] for obj, sub in profiles],
            "extent_object": _ref_json(options.get("extent_object")),
            "extent_object2": _ref_json(options.get("extent_object2")),
            "extend": options.get("extend") or "",
            "extend2": options.get("extend2") or "",
            "object_offset": float(options.get("object_offset") or 0.0),
            "object_offset2": float(options.get("object_offset2") or 0.0),
            "helpers": [h.Name for h in helpers],
            "normal": list(body.getGlobalPlacement().Rotation.inverted().multVec(normal)),
        }
    )
    _save_meta(feature, meta)
    if hide:
        hide_sketches(profiles)


def _delete(obj):
    doc = obj.Document
    body = owner_body(obj)
    try:
        if body is not None and body is not obj:
            body.removeObject(obj)
    except Exception:
        pass
    try:
        doc.removeObject(obj.Name)
    except Exception:
        pass


def show_tip(body):
    """FreeCAD draws a body through its Tip feature, and a new feature hides the one before
    it. A feature removed by code (FreeCAD's own Delete does this itself) left the new Tip
    hidden: the whole part vanished from the view although it was still there."""
    tip = body.Tip if body is not None else None
    if tip is None:
        return
    try:
        if App.GuiUp and tip.ViewObject is not None:
            tip.ViewObject.Visibility = True
        else:
            tip.Visibility = True
    except Exception:
        pass


def _remove(feature, keep_body=True):
    """Delete an extrude with its helpers (and the body it created, when asked)."""
    meta = load_meta(feature)
    doc = feature.Document
    from .extrude_bodies import followers_of, remove_follower

    for follower in followers_of(feature):  # the steps it drove in other bodies go too
        remove_follower(follower)
    body = owner_body(feature)
    was_tip = body is not None and body.Tip is feature
    helpers = [doc.getObject(n) for n in meta.get("helpers", [])]
    _delete(feature)
    for helper in helpers:
        if helper is not None:
            _delete(helper)
    if not keep_body and body is not None and meta.get("created_body") == body.Name:
        rest = [o for o in body.Group if o.TypeId != "App::Origin"]
        if not rest:
            from . import components

            container = components.container_of(body)
            body.removeObjectsFromDocument()
            doc.removeObject(body.Name)
            components.drop_if_empty(container)  # a New Component that failed
            return
    if was_tip:
        show_tip(body)


def remove(feature):
    _remove(feature, keep_body=False)


def make(body, profile, options, name="Extrude"):
    """New extrude with Fusion-style options. `profile`: a sketch (whole sketch),
    (feature, "FaceN"), (sketch, "InternalFaceN") or a list of those. `body` is used
    when the profile does not say (kept for callers of the first version)."""
    profiles = normalize(profile)
    if not profiles:
        raise ExtrudeError("Select a profile first.")
    feature = build(profiles, options, name)
    return feature


def update(feature, profile, options):
    return build(normalize(profile), options, feature=feature)


# -- reading back ------------------------------------------------------------------------
def profiles_of(feature):
    """The profiles of an existing extrude, as picked (binders resolved)."""
    meta = load_meta(feature)
    doc = feature.Document
    if meta.get("profiles"):
        found = []
        for name, sub in meta["profiles"]:
            obj = doc.getObject(name)
            if obj is not None:
                found.append((obj, sub))
        if found:
            return found
    if is_intersect(feature):
        return [(obj, (subs or [""])[0]) for obj, subs in feature.Profiles]
    value = feature.Profile
    obj = value[0] if isinstance(value, tuple) else value
    subs = [s for s in (list(value[1]) if isinstance(value, tuple) and len(value) > 1 else [])]
    subs = [s for s in subs if s]
    if obj is None:
        return []
    if getattr(obj, ROLE, "") == "ExtrudeProfile":
        found = []
        for linked, linked_subs in obj.Support:
            for sub in linked_subs or [""]:
                found.append((linked, sub))
        return found
    if not subs:
        return [(obj, "")]
    return [(obj, s) for s in subs]


def profile_of(feature):
    """First-version name: the profile in make()'s form."""
    profiles = profiles_of(feature)
    if len(profiles) == 1:
        obj, sub = profiles[0]
        return obj if not sub else (obj, sub)
    return profiles


def read(feature):
    """(profiles, options) of an existing extrude, the way the dialog shows them."""
    meta = load_meta(feature)
    doc = feature.Document
    profiles = profiles_of(feature)
    options = dict(DEFAULTS)
    intersect = is_intersect(feature)
    own = getattr(feature, "Operation", "Intersect") if intersect else None
    cut = feature.TypeId == "PartDesign::Pocket" or own == "Cut"
    if intersect and own == "Intersect":
        operation = "intersect"
    elif cut:
        operation = "cut"
    else:
        made = meta.get("operation")
        operation = made if made in ("new_body", "new_component") else "join"
    options["operation"] = operation
    for name in ("start", "measurement"):
        if meta.get(name) in (STARTS if name == "start" else MEASUREMENTS):
            options[name] = meta[name]
    options["start_offset"] = float(meta.get("start_offset", 0.0))
    options["start_object"] = _ref_load(doc, meta.get("start_object"))
    options["flip"] = bool(meta.get("flip", False))
    options["direction"] = {"Symmetric": "symmetric", "Two sides": "two_sides"}.get(
        feature.SideType, "one_side"
    )

    def extent_of(kind):
        if kind == "Length":
            return "distance"
        if kind in ("ThroughAll", "UpToLast"):
            return "all"
        if kind in ("UpToFace", "UpToShape"):
            return "to_object"
        return "distance"

    options["extent"] = extent_of(feature.Type)
    options["extent2"] = extent_of(feature.Type2)
    options["taper"] = feature.TaperAngle.Value
    options["taper2"] = feature.TaperAngle2.Value
    if intersect and bool(getattr(feature, "Thin", False)):
        names = {v: k for k, v in WALL_NAMES.items()}
        options["thin"] = True
        options["wall_location"] = names.get(feature.WallLocation, "side1")
        options["wall_thickness"] = feature.WallThickness.Value
        options["wall_location2"] = names.get(feature.WallLocation2, "side1")
        options["wall_thickness2"] = feature.WallThickness2.Value
    options["extent_object"] = _ref_load(doc, meta.get("extent_object")) or _link_ref(feature, "")
    options["extent_object2"] = _ref_load(doc, meta.get("extent_object2")) or _link_ref(
        feature, "2"
    )
    for name in ("extend", "extend2"):
        options[name] = meta.get(name, "") if meta.get(name, "") in EXTENDS else ""
    for name in ("object_offset", "object_offset2"):
        options[name] = float(meta.get(name, 0.0) or 0.0)
    length = feature.Length.Value
    # Direction actually used, against the profile normal: the sign of the distance.
    sign = 1.0
    try:
        if intersect:
            sign = -1.0 if feature.Reversed else 1.0
        elif profiles:
            body = owner_body(feature)
            want = profile_normal(profiles)
            if body is not None:
                want = body.getGlobalPlacement().Rotation.inverted().multVec(want)
            native = _native_normal(feature)
            used = native * (-1.0 if feature.Reversed else 1.0)
            sign = 1.0 if used.dot(want) >= 0 else -1.0
    except Exception:
        pass
    if options["direction"] == "symmetric":
        options["distance"] = length if options["measurement"] == "whole" else length / 2.0
    else:
        options["distance"] = sign * length
    options["flip"] = False  # the sign of the distance already says which side
    options["distance2"] = feature.Length2.Value
    try:
        from . import parameters_core

        engine = dict(feature.ExpressionEngine)
        options["expressions"] = {
            key: _unwrap(key, parameters_core.from_freecad(engine[prop]), options)
            for key, prop in EXPRESSION_PROPS.items()
            if prop in engine
        }
    except Exception:
        options["expressions"] = {}
    from .extrude_bodies import stored_bodies

    options["bodies"] = stored_bodies(feature)
    return profiles, options


def _link_ref(feature, suffix):
    if ("UpToFace" + suffix) in feature.PropertiesList:
        kind = getattr(feature, "Type" + suffix, "")
        if kind == "UpToFace":
            link = getattr(feature, "UpToFace" + suffix)
            if link and link[0] is not None:
                sub = link[1][0] if link[1] else ""
                return (link[0], sub)
        if kind == "UpToShape":
            links = getattr(feature, "UpToShape" + suffix)
            if links:
                return (links[0][0], "")
    return None


# -- the cut preview -----------------------------------------------------------------------
def tool_shape(feature):
    """The volume a cut extrude removes material with, in global coordinates, or None:
    what the dialog shows in red while it is open (Fusion's cut preview). A Pocket keeps
    it as AddSubShape; SciForge's own feature (a tapered cut FreeCAD cannot make) keeps it
    on its proxy. A side going through All stops at the far side of the part, like Fusion's
    preview, instead of reaching as far as FreeCAD extends it."""
    if feature is None:
        return None
    try:
        if is_intersect(feature):
            tool = getattr(getattr(feature, "Proxy", None), "tool", None)
            if tool is None or tool.isNull():
                return None
            shape = tool.copy()
            body = owner_body(feature)
            if body is not None:
                shape.Placement = body.getGlobalPlacement().multiply(shape.Placement)
        else:
            sub = getattr(feature, "AddSubShape", None)
            if sub is None or sub.isNull():
                return None
            shape = sub.copy()
            shape.Placement = feature.getGlobalPlacement().multiply(sub.Placement)
        if shape.isNull() or not shape.Solids:
            return None
        through = _through_all(feature)
        if through:
            shape = _with_far_bodies(feature, shape)
        box = _parts_box(feature) if through else None
        if box is not None:
            import Part

            box.enlarge(max(box.DiagonalLength * 1e-3, 1e-3))
            limit = Part.makeBox(
                box.XLength, box.YLength, box.ZLength, App.Vector(box.XMin, box.YMin, box.ZMin)
            )
            clipped = shape.common(limit)
            if not clipped.isNull() and clipped.Solids:
                shape = clipped
        return shape
    except Exception:
        return None


def _with_far_bodies(feature, shape):
    """A cut through All acts on every body in its way (R8), but the extrude's own tool
    (FreeCAD's) only reaches a little past the sketch's body: the tools its hidden steps in
    the other bodies use (built to reach them) are added, so the red reaches them too."""
    try:
        from . import bodies
        from .extrude_bodies import follower_tool, followers_of, is_merge

        followers = [f for f in followers_of(feature) if not is_merge(f)]
    except Exception:
        return shape
    for follower in followers:
        base = getattr(follower, "BaseFeature", None)
        try:
            if base is None or base.Shape.isNull():
                continue
            more = follower_tool(feature, bodies.global_shape(base))
            if more is not None and not more.isNull() and more.Solids:
                shape = shape.fuse(more)
        except Exception:
            continue
    return shape


def _parts_box(feature):
    """The box around every part the extrude acts on, as they were before it (its own body
    and the bodies it cuts through: R8), in global coordinates; None when there is none."""
    steps = [feature]
    try:
        from .extrude_bodies import followers_of, is_merge

        steps += [f for f in followers_of(feature) if not is_merge(f)]
    except Exception:
        pass
    box = None
    for step in steps:
        base = getattr(step, "BaseFeature", None)
        if base is None or base.Shape.isNull():
            continue
        found = _to_global(base.Shape, base).BoundBox
        if box is None:
            box = found
        else:
            box.add(found)
    return box


def _through_all(feature):
    """True if a side of the extrude goes through All."""
    for prop in ("Type", "Type2"):
        value = str(getattr(feature, prop, ""))
        if value in ("ThroughAll", "UpToLast"):
            return True
    return False


# -- auto operation ----------------------------------------------------------------------
def goes_into_material(base_shape, profiles, distance, options=None):
    """True if extruding the profile by `distance` starts inside existing material, which
    is when Fusion switches the operation to Cut on its own. base_shape is in the body's
    coordinates (a feature's Shape)."""
    if base_shape is None or base_shape.isNull() or not base_shape.Solids:
        return False
    try:
        profiles = normalize(profiles)
        obj, sub = profiles[0]
        faces = local_faces(obj, sub)
        if not faces:
            return False
        point = interior_point(faces[0])
        normal = profile_normal(profiles, local=True)
        if options is not None and options.get("start") != "profile":
            point = point + normal * start_offset_of(profiles, options)
        step = 0.01 if distance >= 0 else -0.01
        return base_shape.isInside(point + normal * step, 1e-7, True)
    except Exception:
        return False


# -- first-version names (golden builder, tests) ----------------------------------------------
def apply(feature, options):
    """Rewrite the options of an existing extrude in place (first-version API)."""
    profiles = profiles_of(feature)
    return build(profiles, options, feature=feature)


def switch(body, feature, options):
    return build(profiles_of(feature), options, feature=feature)
