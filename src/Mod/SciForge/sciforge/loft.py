# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Loft on top of PartDesign. No GUI code: the Loft command and the golden-model
builder both call this module, so they behave the same.

Profiles, in the order they are lofted through, a list of (object, sub-element):
  (sketch, "InternalFace2")   one closed area of a sketch
  (sketch, "")                the whole sketch
  (feature, "Face6")          a flat face of a body
  (sketch, "Vertex3")         a point (only as the first or the last profile: a dome / cone)
Rails and the centerline are curve references (sketch or part edges, see curves.py).

Options (dict, see DEFAULTS):
  guide      rails | centerline    Fusion's Guide Type
  closed     the last profile lofts back to the first (a ring of profiles)
  operation  join | cut | intersect | new_body

Fusion's Tangent Edges Merge is not built: the loft keeps one side face per profile curve
(Fusion's "Keep"). Merging them means one smooth B-spline side, and OpenCASCADE's volume of
such a face came out up to 10 % wrong here (a slot lofted to the same slot: 7551 instead of
8356 mm^3, while the triangulated shape gave 8356), so Inspect and the mass would lie.

What is built:
  FreeCAD's own AdditiveLoft / SubtractiveLoft when it builds exactly the same thing (no
  rails, no centerline, join / cut / new body, everything in the body);
  otherwise SciForge's LoftFeature: OpenCASCADE's loft through the profiles, a sweep through
  them along the centerline, or a loft through extra sections fitted to the rails (rails
  need profiles in parallel planes; between two profiles the sections are moved, turned and
  scaled so they touch the rails).
"""
import json

import FreeCAD as App

from . import curves, extrude

GUIDES = ("rails", "centerline")
OPERATIONS = ("join", "cut", "intersect", "new_body")
DEFAULTS = {"operation": "join", "guide": "rails", "closed": False, "chain": True}

META = "SciForgeLoft"
FP_TYPE = "PartDesign::FeaturePython"
NATIVE = ("PartDesign::AdditiveLoft", "PartDesign::SubtractiveLoft")
TOL = 1e-7
RAIL_STATIONS = 8  # extra sections between two profiles when rails guide the loft

owner_body = extrude.owner_body
is_sketch = extrude.is_sketch


class LoftError(ValueError):
    """The loft cannot be built as asked; the message says why and what to do."""


# -- options --------------------------------------------------------------------------------
def options_with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in (options or {}).items() if v is not None})
    if merged["guide"] not in GUIDES:
        raise LoftError("unknown guide type %r" % merged["guide"])
    if merged["operation"] not in OPERATIONS:
        raise LoftError("unknown operation %r" % merged["operation"])
    for name in ("closed", "chain"):
        merged[name] = bool(merged[name])
    return merged


def key(profile):
    return (profile[0].Name, profile[1])


def normalize(profiles):
    """Profiles in order, without repeats (the order is the loft's order)."""
    found, seen = [], set()
    for item in profiles or []:
        obj, sub = item[0], item[1] if len(item) > 1 else ""
        if obj is None:
            continue
        k = (obj.Name, sub)
        if k not in seen:
            seen.add(k)
            found.append((obj, sub))
    return found


def is_point(profile):
    return profile[1].startswith("Vertex")


# -- sections ---------------------------------------------------------------------------------
class Section:
    """One profile in global coordinates: its closed wires (outer first) or a point."""

    def __init__(self, profile):
        obj, sub = profile
        self.profile = profile
        self.point = None
        self.wires = []
        self.face = None
        if is_point(profile):
            try:
                vertex = obj.Shape.getElement(sub)
            except Exception:
                raise LoftError("A point picked as a profile is gone. Pick it again.")
            self.point = curves.to_global(vertex, obj).Point
            return
        faces = [extrude._to_global(f, obj) for f in extrude.local_faces(obj, sub)]
        if not faces:
            raise LoftError(
                "%s has no closed area to loft. Close the sketch's outline." % obj.Label
            )
        if len(faces) > 1:
            raise LoftError(
                "%s has %d separate areas; a loft goes through one area per profile. Pick the "
                "areas one at a time." % (obj.Label, len(faces))
            )
        face = faces[0]
        if face.Surface.TypeId != "Part::GeomPlane":
            raise LoftError("Only flat faces can be lofted. Pick a flat face or a sketch.")
        self.face = face
        outer = face.OuterWire
        self.wires = [outer] + [w for w in face.Wires if not w.isSame(outer)]

    @property
    def center(self):
        return self.point if self.point is not None else self.face.CenterOfMass

    @property
    def normal(self):
        if self.face is None:
            return None
        return extrude.face_normal(self.face)


def sections_of(profiles):
    profiles = normalize(profiles)
    if len(profiles) < 2:
        raise LoftError("Pick at least two profiles, in the order the loft goes through them.")
    sections = [Section(p) for p in profiles]
    for i, sec in enumerate(sections):
        if sec.point is not None and 0 < i < len(sections) - 1:
            raise LoftError("A point can only be the first or the last profile of a loft.")
    shaped = [s for s in sections if s.point is None]
    if not shaped:
        raise LoftError("A loft needs at least one profile with an area, not only points.")
    count = len(shaped[0].wires)
    for sec in shaped[1:]:
        if len(sec.wires) != count:
            raise LoftError(
                "Every profile needs the same number of holes (%s has %d, %s has %d)."
                % (
                    shaped[0].profile[0].Label,
                    count - 1,
                    sec.profile[0].Label,
                    len(sec.wires) - 1,
                )
            )
    for a, b in zip(sections, sections[1:]):
        if (a.center - b.center).Length < 1e-6 and _coplanar(a, b):
            raise LoftError(
                "Two profiles lie on top of each other. Pick profiles in different places."
            )
    return sections


def _coplanar(a, b):
    if a.normal is None or b.normal is None:
        return False
    return (
        abs(abs(a.normal.dot(b.normal)) - 1.0) < 1e-9
        and abs((b.center - a.center).dot(a.normal)) < 1e-6
    )


def check_profiles(profiles):
    sections_of(profiles)
    return normalize(profiles)


# -- building the solid -------------------------------------------------------------------------
def _ends(section, index):
    """What OpenCASCADE lofts through for this section: a wire or a vertex."""
    import Part

    if section.point is not None:
        return Part.Vertex(section.point)
    return section.wires[index]


def _solid(shape):
    import Part

    if shape.ShapeType == "Solid":
        solid = shape
    elif shape.Solids:
        solid = shape.Solids[0]
    else:
        try:
            solid = Part.Solid(Part.Shell(shape.Faces))
        except Exception:
            raise LoftError("The loft does not close into a solid. Check the profiles.")
    if solid.Volume < 0:
        solid = solid.copy()
        solid.reverse()
    return solid


def _thru(items, closed):
    import Part

    try:
        shape = Part.makeLoft(items, True, False, closed)
    except Exception as exc:
        raise LoftError(
            "The profiles cannot be lofted (%s). Check that they face the same way and do not "
            "cross each other." % (str(exc) or type(exc).__name__)
        )
    return _solid(shape)


def _along(centerline, items):
    import Part

    try:
        mk = Part.BRepOffsetAPI.MakePipeShell(centerline.wire())
        mk.setTolerance(1e-6, 1e-4, 1e-2)
        mk.setFrenetMode(False)
        for item in items:
            mk.add(item, False, False)
        if not mk.isReady():
            raise LoftError("The loft cannot follow this centerline.")
        mk.build()
        if not mk.makeSolid():
            raise LoftError("The loft does not close into a solid along the centerline.")
        return _solid(mk.shape())
    except LoftError:
        raise
    except Exception as exc:
        raise LoftError(
            "The profiles cannot follow this centerline (%s). The centerline must run through "
            "the profiles' order." % (str(exc) or type(exc).__name__)
        )


def _plane_hit(path, center, normal):
    """Point where a curve crosses the plane (center, normal), nearest the center, or None."""
    import Part

    reach = path.wire().BoundBox.DiagonalLength + (path.start - center).Length + 100.0
    plane = Part.Plane(center, normal).toShape(-reach, reach, -reach, reach)
    try:
        hits = [x.Point for x in path.wire().section(plane).Vertexes]
    except Exception:
        hits = []
    if not hits:
        return None
    return min(hits, key=lambda p: (p - center).Length)


def _similarity(c1, c2, r1, r2, normal):
    """Matrix of the turn + uniform scale about `normal` + move taking c1 -> r1, c2 -> r2
    (all points in one plane square to `normal`)."""
    import math

    a = c2 - c1
    b = r2 - r1
    if a.Length < 1e-9:
        m = App.Matrix()
        m.move(r1 - c1)
        return m
    scale = b.Length / a.Length
    an, bn = App.Vector(a), App.Vector(b)
    an.normalize()
    bn.normalize()
    angle = math.atan2(an.cross(bn).dot(normal), an.dot(bn))
    rot = App.Rotation(normal, math.degrees(angle))
    m = App.Placement(App.Vector(), rot).toMatrix()
    m.scale(scale, scale, scale)
    shift = r1 - m.multVec(c1)
    m.move(shift)
    return m


def _rail_loft(sections, rails):
    """A loft through the profiles plus extra sections that touch the rails."""
    if any(s.point is not None for s in sections):
        raise LoftError("Rails need profiles with an area at both ends (no points).")
    if any(len(s.wires) > 1 for s in sections):
        raise LoftError("Rails work with profiles without holes. Cut the holes afterwards.")
    normal = App.Vector(sections[0].normal)
    for s in sections[1:]:
        if abs(abs(s.normal.dot(normal)) - 1.0) > 1e-6:
            raise LoftError("Rails need profiles in parallel planes (all square to one direction).")
    origin = sections[0].center
    heights = [(s.center - origin).dot(normal) for s in sections]
    steps = [b - a for a, b in zip(heights, heights[1:])]
    if any(abs(d) < 1e-6 for d in steps) or (
        any(d > 0 for d in steps) and any(d < 0 for d in steps)
    ):
        raise LoftError("With rails, the profiles must follow each other in one direction.")
    contacts = []
    for j, rail in enumerate(rails):
        row = []
        for i, s in enumerate(sections):
            hit = _plane_hit(rail, s.center, normal)
            if hit is None or s.wires[0].distToShape(_vertex(hit))[0] > 1e-3:
                raise LoftError(
                    "Rail %d does not touch profile %d. A rail must run through every profile."
                    % (j + 1, i + 1)
                )
            row.append(s.wires[0].distToShape(_vertex(hit))[1][0][0])
        contacts.append(row)
    base = _thru([s.wires[0] for s in sections], False)
    items = []
    for i in range(len(sections) - 1):
        items.append(sections[i].wires[0])
        for k in range(1, RAIL_STATIONS + 1):
            t = k / float(RAIL_STATIONS + 1)
            h = heights[i] + (heights[i + 1] - heights[i]) * t
            level = origin.dot(normal) + h
            try:
                cut = base.slice(normal, level)
            except Exception:
                cut = []
            if not cut:
                continue
            wire = max(cut, key=lambda w: w.BoundBox.DiagonalLength)
            center = origin + normal * h
            pairs = []
            for j, rail in enumerate(rails):
                guess = contacts[j][i] + (contacts[j][i + 1] - contacts[j][i]) * t
                on_wire = wire.distToShape(_vertex(guess))[1][0][0]
                target = _plane_hit(rail, guess, normal)
                if target is None:
                    raise LoftError("Rail %d stops between two profiles." % (j + 1))
                pairs.append((on_wire, target))
            if len(pairs) == 1:
                m = App.Matrix()
                m.move(pairs[0][1] - pairs[0][0])
            else:
                m = _similarity(pairs[0][0], pairs[1][0], pairs[0][1], pairs[1][1], normal)
            items.append(wire.transformGeometry(m))
    items.append(sections[-1].wires[0])
    return _thru(items, False)


def _vertex(point):
    import Part

    return Part.Vertex(point)


def tool_shape(profiles, rail_refs, centerline_refs, options):
    """The lofted solid (global coordinates)."""
    options = options_with_defaults(options)
    sections = sections_of(profiles)
    guide = options["guide"]
    if guide == "centerline" and curves.normalize(centerline_refs):
        if options["closed"]:
            raise LoftError("A closed loft cannot follow a centerline. Clear Closed or the line.")
        try:
            line = curves.Path(curves.refs_edges(centerline_refs), start_near=sections[0].center)
        except curves.CurveError as exc:
            raise LoftError("Centerline: %s" % exc)
        count = len(sections[[s.point is None for s in sections].index(True)].wires)
        solids = [_along(line, [_ends(s, k) for s in sections]) for k in range(count)]
        return _holes(solids)
    if guide == "rails" and curves.normalize(rail_refs):
        if options["closed"]:
            raise LoftError("A closed loft cannot follow rails. Clear Closed or the rails.")
        return _rail_loft(sections, _rail_groups(rail_refs, sections[0].center))
    if options["closed"] and len(sections) < 3:
        raise LoftError("A closed loft needs at least three profiles.")
    count = len(sections[[s.point is None for s in sections].index(True)].wires)
    solids = [_thru([_ends(s, k) for s in sections], options["closed"]) for k in range(count)]
    return _holes(solids)


def _holes(solids):
    solid = solids[0]
    for hole in solids[1:]:
        solid = solid.cut(hole)
    return solid


def _rail_groups(rail_refs, near):
    """Each connected run of rail curves is one rail (a Path)."""
    import Part

    edges = curves.refs_edges(rail_refs)
    try:
        groups = Part.sortEdges(edges, 1e-5)
    except Exception:
        groups = [edges]
    paths = []
    for group in groups:
        try:
            paths.append(curves.Path(group, start_near=near))
        except curves.CurveError as exc:
            raise LoftError("Rail: %s" % exc)
    return paths


def auto_operation(base_shape, profiles, rail_refs, centerline_refs, options):
    if base_shape is None or base_shape.isNull() or not base_shape.Solids:
        return "new_body"
    try:
        tool = tool_shape(profiles, rail_refs, centerline_refs, options)
        inside = base_shape.common(tool).Volume
        outside = tool.Volume - inside
        if inside < 1e-9 and base_shape.distToShape(tool)[0] > 1e-6:
            return "new_body"  # Fusion: a loft that does not touch the part is a new body
    except Exception:
        return "join"
    return "cut" if inside > outside + 1e-6 * max(1.0, tool.Volume) else "join"


# -- meta ---------------------------------------------------------------------------------------
def _refs_json(refs):
    return [[obj.Name, sub] for obj, sub in refs or [] if obj is not None]


def _refs_load(doc, data):
    found = []
    for name, sub in data or []:
        obj = doc.getObject(name)
        if obj is not None:
            found.append((obj, sub))
    return found


def load_meta(feature):
    try:
        text = getattr(feature, META, "")
        return json.loads(text) if text else {}
    except Exception:
        return {}


def _save_meta(feature, meta):
    if META not in feature.PropertiesList:
        feature.addProperty("App::PropertyString", META, "SciForge", "Fusion loft options", 0)
        feature.setEditorMode(META, 2)
    text = json.dumps(meta, sort_keys=True)
    if getattr(feature, META) != text:
        setattr(feature, META, text)


def is_own(obj):
    return obj is not None and getattr(obj, "SciForgeType", "") == "Loft" and obj.TypeId == FP_TYPE


def is_loft(obj):
    return obj is not None and (obj.TypeId in NATIVE or is_own(obj))


# -- SciForge's own loft feature ------------------------------------------------------------------
class LoftFeature:
    """Loft with what FreeCAD's Loft cannot do: rails, a centerline, Intersect, profiles
    from other bodies. Saved documents store
    "sciforge.loft.LoftFeature": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Loft"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSubListGlobal", "Profiles", "The profiles, in loft order")
        add("App::PropertyLinkSubListGlobal", "Rails", "Rails the loft follows")
        add("App::PropertyLinkSubListGlobal", "Centerline", "Centerline the loft follows")
        if add("App::PropertyEnumeration", "GuideType", "Rails or centerline"):
            obj.GuideType = ["Rails", "Centerline"]
        if add("App::PropertyEnumeration", "Operation", "Join, cut or intersect"):
            obj.Operation = ["Join", "Cut", "Intersect"]
        add("App::PropertyBool", "Closed", "Loft the last profile back to the first")
        if add("App::PropertyBool", "Refine", "Merge coplanar faces, like Fusion"):
            obj.Refine = True
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
            obj.SciForgeType = "Loft"

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        has_base = base is not None and not base.Shape.isNull() and bool(base.Shape.Solids)
        operation = obj.Operation
        if not has_base and operation != "Join":
            raise LoftError(
                "%s needs a solid before it in the timeline."
                % ("Cut" if operation == "Cut" else "Intersect")
            )
        options = fp_options(obj)
        renamed = curves.refind(obj, LINKS)  # a picked face / edge of the part FreeCAD lost
        if renamed:
            meta = load_meta(obj)
            meta["profiles"] = [
                [name, renamed.get((name, sub), sub)] for name, sub in meta.get("profiles") or []
            ]
            _save_meta(obj, meta)
        tool = tool_shape(ordered_profiles(obj), _links(obj.Rails), _links(obj.Centerline), options)
        body = owner_body(obj)
        if body is not None:
            inverse = body.getGlobalPlacement().inverse()
            if not inverse.isIdentity():
                tool = tool.copy()
                tool.transformShape(inverse.toMatrix(), True)
        if not has_base:
            result = tool
        elif operation == "Intersect":
            result = base.Shape.common(tool)
        elif operation == "Cut":
            result = base.Shape.cut(tool)
        else:
            result = base.Shape.fuse(tool)
        if obj.Refine:
            try:
                result = result.removeSplitter()
            except Exception:
                pass
        if result.isNull() or not result.Solids or result.Volume < TOL:
            if operation == "Cut":
                raise LoftError("This cut would remove the whole body.")
            if operation == "Intersect":
                raise LoftError(
                    "The loft does not overlap the body, so Intersect would leave nothing."
                )
            raise LoftError("The loft has no volume. Check the profiles.")
        if operation == "Cut" and abs(result.Volume - base.Shape.Volume) < 1e-9:
            raise LoftError("The cut does not touch the body. Move the profiles.")
        obj.Shape = result.Solids[0] if len(result.Solids) == 1 else result
        curves.remember(obj, LINKS)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


LINKS = ("Profiles", "Rails", "Centerline")


def _links(value):
    found = []
    for linked, subs in value or []:
        if linked is None:
            continue
        for sub in subs or [""]:
            found.append((linked, sub))
    return found


def ordered_profiles(obj):
    """The loft feature's profiles in loft order. FreeCAD's link list groups the entries of one
    object together, so the order is kept in the meta too."""
    linked = _links(obj.Profiles)
    order = load_meta(obj).get("profiles")
    if not order:
        return linked
    by_key = {(o.Name, s): (o, s) for o, s in linked}
    ordered = [by_key.get((name, sub)) for name, sub in order]
    if len(ordered) == len(linked) and all(p is not None for p in ordered):
        return ordered
    return linked


def fp_options(obj):
    return {
        "guide": obj.GuideType.lower(),
        "operation": obj.Operation.lower(),
        "closed": bool(obj.Closed),
    }


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .loft_ui import ViewProviderLoft

        ViewProviderLoft(obj.ViewObject)
    except Exception:
        pass


# -- which FreeCAD feature ------------------------------------------------------------------------
def _native_section(profile, body):
    """A profile as FreeCAD's Loft takes it, or None."""
    obj, sub = profile
    if owner_body(obj) is not body or obj is body:
        return None
    if is_point(profile):
        return (obj, [sub]) if is_sketch(obj) else None
    if is_sketch(obj):
        try:
            whole = {extrude.key(p) for p in extrude.expand_whole([(obj, "")])}
            picked = {extrude.key(p) for p in extrude.expand_whole([profile])}
        except Exception:
            return None
        return (obj, [""]) if whole == picked and len(whole) == 1 else None
    # A face of the part: SciForge's loft, which finds the face again when FreeCAD loses its
    # name after an earlier step is edited (FreeCAD's Loft then just fails).
    return None


def native_type(profiles, rail_refs, centerline_refs, options, body):
    if body is None:
        return None
    if options["operation"] not in ("join", "cut", "new_body"):
        return None
    if options["guide"] == "rails" and curves.normalize(rail_refs):
        return None
    if options["guide"] == "centerline" and curves.normalize(centerline_refs):
        return None
    profiles = normalize(profiles)
    if len({p[0].Name for p in profiles}) != len(profiles):
        return None  # two profiles from one sketch: FreeCAD's Loft takes whole sketches
    if any(_native_section(p, body) is None for p in profiles):
        return None
    return "PartDesign::SubtractiveLoft" if options["operation"] == "cut" else NATIVE[0]


# -- building -----------------------------------------------------------------------------------
def _has_solid(body, before=None):
    tip = before.BaseFeature if before is not None else body.Tip
    return tip is not None and not tip.Shape.isNull() and bool(tip.Shape.Solids)


def _insert(body, type_id, name, before=None):
    if before is not None:
        obj = body.Document.addObject(type_id, name)
        body.insertObject(obj, before, False)
        return obj
    return body.newObject(type_id, name)


def _source_body(profiles):
    for obj, _ in profiles:
        body = owner_body(obj)
        if body is not None:
            return body
    raise LoftError("The profiles must belong to a body. Use Create Sketch first.")


def _target(feature, profiles, options):
    src = _source_body(profiles)
    meta = load_meta(feature) if feature is not None else {}
    created = None
    if feature is not None and meta.get("created_body"):
        created = feature.Document.getObject(meta["created_body"])
    if options["operation"] == "new_body":
        if created is not None:
            return created, src
        if feature is not None and owner_body(feature) is src and not _has_solid(src, feature):
            return src, src
        if feature is None and not _has_solid(src):
            return src, src
        return None, src
    return src, src


def _new_body(src_body):
    doc = src_body.Document
    count = len([o for o in doc.Objects if o.TypeId == "PartDesign::Body"]) + 1
    body = doc.addObject("PartDesign::Body", "Body")
    container = src_body.getParentGeoFeatureGroup()
    if container is not None and hasattr(container, "addObject"):
        container.addObject(body)
    body.Label = "Body%d" % count
    return body


def build(profiles, rail_refs, centerline_refs, options, name="Loft", feature=None, hide=True):
    """Create the loft, or rebuild `feature`. Returns the feature (a different object when
    its kind had to change)."""
    profiles = check_profiles(profiles)
    options = options_with_defaults(options)
    rail_refs = curves.normalize(rail_refs) if options["guide"] == "rails" else []
    centerline_refs = curves.normalize(centerline_refs) if options["guide"] == "centerline" else []
    tool_shape(profiles, rail_refs, centerline_refs, options)  # fails early with the reason
    target, src = _target(feature, profiles, options)
    native = native_type(profiles, rail_refs, centerline_refs, options, target) if target else None
    type_id = native or FP_TYPE
    if feature is not None:
        same = feature.TypeId == type_id and (type_id != FP_TYPE or is_own(feature))
        if owner_body(feature) is target and same:
            _update(feature, profiles, rail_refs, centerline_refs, options, hide)
            return feature
        # Rebuilt in its own body, later steps are moved onto the new step (relink_users
        # below); only a move to another body cannot take them along.
        blocking = [] if owner_body(feature) is target else extrude.dependents(feature)
        if blocking:
            raise LoftError(
                "%s is used by %s, so it cannot move to a new body. Use Join, or make a new "
                "loft." % (feature.Label, ", ".join(o.Label for o in blocking))
            )
    old_meta = load_meta(feature) if feature is not None else {}
    created = None
    if target is None:
        target = created = _new_body(src)
        type_id = FP_TYPE
    elif old_meta.get("created_body") == target.Name:
        created = target
    before = feature if (feature is not None and owner_body(feature) is target) else None
    was_tip = before is not None and target.Tip is before
    new = _insert(target, type_id, name, before)
    if type_id == FP_TYPE:
        LoftFeature(new)
        _attach_view_provider(new)
    _save_meta(new, {"created_body": created.Name if created is not None else None})
    try:
        _update(new, profiles, rail_refs, centerline_refs, options, hide)
    except Exception:
        _remove(new, keep_body=created is None or before is not None)
        raise
    if before is not None and curves.computed(new):
        curves.relink_users(feature, new)
    if feature is not None:
        label = feature.Label
        old_body = owner_body(feature)
        _remove(feature, keep_body=old_body is target)
        new.Label = label
        if old_body is not None and old_body is not target:
            extrude.show_tip(old_body)
    if before is None or was_tip:
        target.Tip = new
    return new


def _update(feature, profiles, rail_refs, centerline_refs, options, hide=True):
    body = owner_body(feature)
    if feature.TypeId in NATIVE:
        native = [_native_section(p, body) for p in profiles]
        if any(n is None for n in native):
            raise LoftError("internal: these profiles need SciForge's own loft")
        first = native[0]
        feature.Profile = first if first[1] != [""] else first[0]
        feature.Sections = [(o, subs) if subs != [""] else (o, "") for o, subs in native[1:]]
        if feature.Closed != options["closed"]:
            feature.Closed = options["closed"]
        if feature.Ruled:
            feature.Ruled = False
        feature.Refine = True
    else:
        feature.Profiles = [(obj, [sub]) for obj, sub in profiles]
        feature.Rails = [(obj, [sub]) for obj, sub in rail_refs]
        feature.Centerline = [(obj, [sub]) for obj, sub in centerline_refs]
        guide = "Rails" if options["guide"] == "rails" else "Centerline"
        if feature.GuideType != guide:
            feature.GuideType = guide
        operation = {"cut": "Cut", "intersect": "Intersect"}.get(options["operation"], "Join")
        if feature.Operation != operation:
            feature.Operation = operation
        if feature.Closed != options["closed"]:
            feature.Closed = options["closed"]
        feature.Refine = True
    meta = load_meta(feature)
    meta.update(
        {
            "v": 1,
            "operation": options["operation"],
            "guide": options["guide"],
            "closed": options["closed"],
            "chain": options["chain"],
            "profiles": _refs_json(profiles),
            "rails": _refs_json(rail_refs),
            "centerline": _refs_json(centerline_refs),
        }
    )
    _save_meta(feature, meta)
    if hide:
        hide_sketches(profiles, rail_refs, centerline_refs)


def hide_sketches(profiles, rail_refs=(), centerline_refs=()):
    if not App.GuiUp:
        return
    for obj, _ in list(profiles) + list(rail_refs) + list(centerline_refs):
        if is_sketch(obj):
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass


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


def _remove(feature, keep_body=True):
    meta = load_meta(feature)
    doc = feature.Document
    body = owner_body(feature)
    was_tip = body is not None and body.Tip is feature
    _delete(feature)
    if not keep_body and body is not None and meta.get("created_body") == body.Name:
        rest = [o for o in body.Group if o.TypeId != "App::Origin"]
        if not rest:
            body.removeObjectsFromDocument()
            doc.removeObject(body.Name)
            return
    if was_tip:
        extrude.show_tip(body)


def remove(feature):
    _remove(feature, keep_body=False)


def make(profiles, options=None, rail_refs=None, centerline_refs=None, name="Loft"):
    """New loft through `profiles` (in order) with Fusion-style options."""
    return build(normalize(profiles), rail_refs or [], centerline_refs or [], options or {}, name)


def update(feature, profiles=None, rail_refs=None, centerline_refs=None, options=None):
    old_profiles, old_rails, old_line, old_options = read(feature)
    merged = dict(old_options)
    merged.update(options or {})
    return build(
        normalize(profiles) if profiles is not None else old_profiles,
        rail_refs if rail_refs is not None else old_rails,
        centerline_refs if centerline_refs is not None else old_line,
        merged,
        feature=feature,
    )


# -- reading back ----------------------------------------------------------------------------------
def read(feature):
    """(profiles in order, rail refs, centerline refs, options) of an existing loft."""
    meta = load_meta(feature)
    doc = feature.Document
    options = dict(DEFAULTS)
    for name in DEFAULTS:
        if name in meta:
            options[name] = meta[name]
    profiles = _refs_load(doc, meta.get("profiles"))
    if is_own(feature):
        options.update(fp_options(feature))
        if meta.get("operation") == "new_body":
            options["operation"] = "new_body"
        if not profiles:
            profiles = _links(feature.Profiles)
        return (
            profiles,
            _links(feature.Rails),
            _links(feature.Centerline),
            options_with_defaults(options),
        )
    options["operation"] = (
        "cut"
        if feature.TypeId == "PartDesign::SubtractiveLoft"
        else ("new_body" if meta.get("operation") == "new_body" else "join")
    )
    options["closed"] = bool(feature.Closed)
    if not profiles:
        items = []
        value = feature.Profile
        if isinstance(value, tuple):
            items.append((value[0], list(value[1] or [])))
        elif value is not None:
            items.append((value, []))
        for obj, subs in feature.Sections:
            items.append((obj, list(subs or [])))
        for obj, subs in items:
            if obj is None:
                continue
            subs = [s for s in subs if s]
            if subs:
                profiles += [(obj, s) for s in subs]
            else:
                profiles.append((obj, ""))
    return profiles, [], [], options_with_defaults(options)
