# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Hole on top of FreeCAD's PartDesign::Hole. No Qt here: the golden-model
builder and the headless tests run exactly the code behind the Hole dialog.

Placement
  Single Hole   click a face: the hole goes where you clicked. Under the hood a hidden
                sketch named after the hole ("Hole Sketch") sits on that face with one point
                at the clicked spot, and the hole is drilled from it. Up to two straight
                edges can be picked as references, each with a distance from the hole's
                centre (Fusion's way of placing a hole exactly); they are Distance
                constraints to the edges projected into that sketch, so the hole follows the
                edges when the part changes. Without references the X / Y position of the
                point on the face can be typed. Editing the hole moves the point.
  From Sketch   pick points and circles of a sketch you drew: one hole at each point and at
                each circle's centre. The holes go into the material (flipped automatically
                when the sketch lies under the part; Flip turns them round).

Extents Distance / To (a face or plane) / All. Hole Type Simple / Counterbore /
Countersink. Hole Tap Type Simple / Clearance (ISO metric or ANSI sizes with a Close /
Normal / Loose fit) / Tapped (size, designation, class, direction, Modeled, full or partial
tap depth). Drill Point Flat / Angle (118 degrees by default). The depth is measured to the
end of the full diameter; an angled drill point comes on top, as a drill makes it.

The hole and its sketch are created in one undo step by the dialog (taskui.Panel).
"""
import json
import math

import FreeCAD as App

from . import thread_tables as tables

TYPE = "PartDesign::Hole"
SKETCH_TYPE = "Sketcher::SketchObject"
META = "SciForgeHole"  # JSON: the Fusion options FreeCAD's Hole has no property for
ROLE = "SciForgeRole"  # same marker property as extrude.py's helpers
SKETCH_ROLE = "HoleSketch"
TIMELINE = "SciForgeTimeline"  # False: the timeline does not show this object
PLANE_TYPES = ("App::Plane", "PartDesign::Plane")
Z = App.Vector(0, 0, 1)
TOL = 1e-6

# FreeCAD's screw-standard hole cuts that are countersinks (the others are counterbores).
COUNTERSINK_CUTS = (
    "Countersink",
    "ISO 10642",
    "ISO 2009",
    "ISO 7046",
    "ISO 14583",
    "ISO 14583 (partial)",
)

PLACEMENTS = ("single", "sketch")
EXTENTS = ("distance", "to", "all")
HOLE_TYPES = ("simple", "counterbore", "countersink")
TAP_TYPES = ("simple", "clearance", "tapped")
DRILL_POINTS = ("flat", "angle")

DEFAULTS = {
    "placement": "single",
    "extent": "distance",
    "depth": 10.0,
    "to": None,  # (object, "FaceN" or "") for extent "to"
    "flip": False,
    "hole_type": "simple",
    "tap_type": "simple",
    "diameter": 5.0,
    "cbore_diameter": 10.0,
    "cbore_depth": 5.0,
    "csink_diameter": 10.0,
    "csink_angle": 90.0,
    "drill_point": "angle",
    "drill_angle": 118.0,
    "standard": "iso",
    "size": "6",
    "designation": "M6x1",
    "fit": "normal",
    "thread_class": "6H",
    "direction": "right",
    "modeled": False,
    "full_tap": True,
    "tap_depth": 8.0,
}


class HoleError(ValueError):
    """The hole cannot be built as asked; the message says why and what to do."""


def options_with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in (options or {}).items() if v is not None or k == "to"})
    return merged


# -- objects -----------------------------------------------------------------------------------
def owner_body(obj):
    if obj is None:
        return None
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        return None
    if parent is not None and parent.TypeId == "PartDesign::Body":
        return parent
    return None


def is_hole(obj):
    return obj is not None and getattr(obj, "TypeId", "") == TYPE


def is_helper(obj):
    return obj is not None and getattr(obj, ROLE, "") == SKETCH_ROLE


def profile_sketch(hole):
    """The sketch the hole is drilled from, or None."""
    link = hole.Profile
    if not link:
        return None
    obj = link[0]
    return obj if obj is not None and obj.isDerivedFrom(SKETCH_TYPE) else None


def helper_sketch(hole):
    """The hidden sketch SciForge made for a Single Hole, or None."""
    sketch = profile_sketch(hole)
    return sketch if is_helper(sketch) else None


def hole_of(sketch):
    """The hole a helper sketch places, or None."""
    for obj in getattr(sketch, "InList", []):
        if is_hole(obj) and profile_sketch(obj) is sketch:
            return obj
    return None


def placement_of(hole):
    return "single" if helper_sketch(hole) is not None else "sketch"


def _mark(obj, role):
    if ROLE not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", ROLE, "SciForge", "What SciForge made this for", 0)
        obj.setEditorMode(ROLE, 2)
    setattr(obj, ROLE, role)
    if TIMELINE not in obj.PropertiesList:
        obj.addProperty(
            "App::PropertyBool", TIMELINE, "SciForge", "Shown in the timeline (helpers are not)", 0
        )
        obj.setEditorMode(TIMELINE, 2)
    setattr(obj, TIMELINE, False)
    # Double-clicking it (browser) or "Edit Profile Sketch" (timeline) opens the Hole dialog:
    # taskui looks editors up by "SciForge::<SciForgeType>".
    if "SciForgeType" not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)  # hidden
    obj.SciForgeType = role


def load_meta(hole):
    try:
        text = getattr(hole, META, "")
        return json.loads(text) if text else {}
    except Exception:
        return {}


def _save_meta(hole, meta):
    if META not in hole.PropertiesList:
        hole.addProperty("App::PropertyString", META, "SciForge", "Fusion hole options", 0)
        hole.setEditorMode(META, 2)
    text = json.dumps(meta, sort_keys=True)
    if getattr(hole, META) != text:
        setattr(hole, META, text)


def _ref_json(ref):
    if not ref or ref[0] is None:
        return None
    return [ref[0].Name, ref[1]]


def _ref_load(doc, data):
    if not data:
        return None
    obj = doc.getObject(data[0])
    return (obj, data[1]) if obj is not None else None


def _hide(obj):
    try:
        if App.GuiUp and obj.ViewObject is not None:
            obj.ViewObject.Visibility = False
    except Exception:
        pass
    try:
        obj.Visibility = False
    except Exception:
        pass


def display_name(hole):
    """What the timeline calls the hole ("Hole 2", or the name the user gave it)."""
    try:
        from . import timeline_ops

        for item in timeline_ops.timeline(hole.Document, deps=False).items:
            if item.name == hole.Name:
                return item.display
    except Exception:
        pass
    return hole.Label


def helper_label(hole):
    return "%s Sketch" % display_name(hole)


def sync_label(hole):
    """Keep the helper sketch named after its hole (the user may rename the hole)."""
    sketch = helper_sketch(hole)
    if sketch is not None and sketch.Label != helper_label(hole):
        sketch.Label = helper_label(hole)


# -- coordinates -------------------------------------------------------------------------------
def body_placement(obj):
    body = owner_body(obj)
    return body.getGlobalPlacement() if body is not None else App.Placement()


def to_local(body, point):
    return body.getGlobalPlacement().inverse().multVec(App.Vector(point))


def to_global(body, point):
    return body.getGlobalPlacement().multVec(App.Vector(point))


def face_normal_at(face, point):
    """Outward normal of a face at a point on it (normalAt already points out of the solid)."""
    try:
        u, v = face.Surface.parameter(App.Vector(point))
        normal = face.normalAt(u, v)
    except Exception:
        normal = face.normalAt(0, 0)
    if normal.Length < TOL:
        return App.Vector(Z)
    normal.normalize()
    return normal


PICK_TOL = 0.3  # mm: a click on a curved face lands on its drawn facets, not the true surface


def base_face_at(base, point, normal_hint=None, tol=1e-4, loose=PICK_TOL):
    """'FaceN' of `base` (a feature, body coordinates) that contains `point` (body
    coordinates). A point clicked on the part with this hole already in it (on a face it
    shrank) is looked up on the part before the hole. Among faces through the point (an
    edge), the one facing `normal_hint` wins. A clicked point can be a little off a curved
    face (it lies on the face's drawn facets): if no face holds the point exactly, the
    nearest one within `loose` is taken. None if no face is there."""
    import Part

    if base is None or base.Shape.isNull():
        return None
    point = App.Vector(point)
    vertex = Part.Vertex(point)
    found = []
    for i, face in enumerate(base.Shape.Faces, start=1):
        try:
            box = face.BoundBox
            box.enlarge(max(tol * 10, loose))
            if not box.isInside(point):
                continue
            gap = face.distToShape(vertex)[0]
        except Exception:
            continue
        if gap <= max(tol, loose):
            score = 0.0
            if normal_hint is not None:
                score = -face_normal_at(face, point).dot(normal_hint)
            found.append((gap > tol, score, gap, i))
    if not found:
        return None
    found.sort()
    return "Face%d" % found[0][3]


def snap_to_face(face, point):
    """The point of `face` nearest to `point` (a click on a curved face lands on its
    facets, a little off the true surface)."""
    import Part

    try:
        return App.Vector(face.distToShape(Part.Vertex(App.Vector(point)))[1][0][0])
    except Exception:
        return App.Vector(point)


def base_edge_like(base, edge):
    """'EdgeN' of `base` that is the same straight edge as `edge` (body coordinates) or the
    longer edge it lies on (an edge of the part the hole cut in two)."""
    if base is None or base.Shape.isNull():
        return None
    ends = [v.Point for v in edge.Vertexes]
    if len(ends) < 2 or edge.Curve.TypeId not in ("Part::GeomLine", "Part::GeomLineSegment"):
        return None
    import Part

    for i, candidate in enumerate(base.Shape.Edges, start=1):
        other = [v.Point for v in candidate.Vertexes]
        if len(other) < 2 or abs(candidate.Length - edge.Length) > 1e-6:
            continue
        same = (other[0] - ends[0]).Length < 1e-6 and (other[-1] - ends[-1]).Length < 1e-6
        swapped = (other[0] - ends[-1]).Length < 1e-6 and (other[-1] - ends[0]).Length < 1e-6
        if same or swapped:
            return "Edge%d" % i
    for i, candidate in enumerate(base.Shape.Edges, start=1):
        if candidate.Curve.TypeId not in ("Part::GeomLine", "Part::GeomLineSegment"):
            continue
        try:
            if all(candidate.distToShape(Part.Vertex(p))[0] < 1e-6 for p in ends):
                return "Edge%d" % i
        except Exception:
            continue
    return None


# -- the helper sketch (Single Hole) -----------------------------------------------------------
def _origin_plane(body, role="XY_Plane"):
    for feature in body.Origin.OriginFeatures:
        if (getattr(feature, "Role", "") or feature.Name).startswith(role):
            return feature
    raise HoleError("The body has no %s." % role)


def _attach(sketch, body, base, face_name, point):
    """Put the sketch flat on the face (planar faces: parametric attachment, the sketch
    follows the face). On a curved face the sketch is tangent to the face at `point`
    (body coordinates), its normal the face's outward normal there."""
    face = base.Shape.getElement(face_name)
    point = snap_to_face(face, point)
    if face.Surface.TypeId == "Part::GeomPlane":
        sketch.AttachmentOffset = App.Placement()
        sketch.AttachmentSupport = [(base, face_name)]
        sketch.MapMode = "FlatFace"
        return "planar"
    normal = face_normal_at(face, point)
    rotation = App.Rotation(Z, normal)
    sketch.AttachmentSupport = [(_origin_plane(body), "")]
    sketch.MapMode = "FlatFace"
    sketch.AttachmentOffset = App.Placement(App.Vector(point), rotation)
    return "curved"


def _sketch_xy(sketch, point):
    """Body coordinates -> (x, y) in the sketch."""
    local = sketch.Placement.inverse().multVec(App.Vector(point))
    return local.x, local.y


def _line_xy(sketch, edge_ref):
    """The reference edge projected into the sketch: ((x1, y1), (x2, y2)) or None."""
    obj, sub = edge_ref
    try:
        edge = obj.Shape.getElement(sub)
    except Exception:
        return None
    if edge.Curve.TypeId not in ("Part::GeomLine", "Part::GeomLineSegment"):
        return None
    body = owner_body(sketch)
    owner = owner_body(obj)
    a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    if owner is not body and body is not None:  # another body: through global coordinates
        a, b = body_placement(obj).multVec(a), body_placement(obj).multVec(b)
        a, b = to_local(body, a), to_local(body, b)
    pa, pb = _sketch_xy(sketch, a), _sketch_xy(sketch, b)
    if math.hypot(pb[0] - pa[0], pb[1] - pa[1]) < 1e-7:
        return None  # the edge stands straight up from the face: it projects to a point
    return pa, pb


def point_line_distance(p, line):
    (x1, y1), (x2, y2) = line
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    return abs((p[0] - x1) * dy - (p[1] - y1) * dx) / length


def check_reference(sketch, edge_ref):
    """None if the edge can be a reference for the hole, else why not."""
    if _line_xy(sketch, edge_ref) is None:
        return "Pick a straight edge that does not stand straight up from the face."
    return None


def _parallel(line_a, line_b):
    (ax1, ay1), (ax2, ay2) = line_a
    (bx1, by1), (bx2, by2) = line_b
    cross = (ax2 - ax1) * (by2 - by1) - (ay2 - ay1) * (bx2 - bx1)
    la = math.hypot(ax2 - ax1, ay2 - ay1)
    lb = math.hypot(bx2 - bx1, by2 - by1)
    return abs(cross) < 1e-9 * la * lb


def _rebuild_sketch(sketch, xy, references):
    """The sketch's content: one point at xy, the reference edges projected, a distance
    from the point to each. references: [((obj, "EdgeN"), distance), ...]."""
    import Part
    import Sketcher

    sketch.deleteAllGeometry()
    while len(sketch.ExternalGeometry) > 0:
        sketch.delExternal(len(sketch.ExternalGeometry) - 1)
    sketch.addGeometry(Part.Point(App.Vector(xy[0], xy[1], 0)))
    for i, (ref, distance) in enumerate(references):
        obj, sub = ref
        sketch.addExternal(obj.Name, sub)
        index = sketch.addConstraint(
            Sketcher.Constraint("Distance", 0, 1, -3 - i, max(float(distance), 1e-6))
        )
        sketch.renameConstraint(index, "Reference%d" % (i + 1))


def hole_xy(hole):
    """(x, y) of a Single Hole's point in its sketch."""
    sketch = helper_sketch(hole)
    if sketch is None or sketch.GeometryCount == 0:
        return None
    p = sketch.getPoint(0, 1)
    return p.x, p.y


def hole_point(hole):
    """Body coordinates of a Single Hole's centre on its face, or None."""
    sketch = helper_sketch(hole)
    xy = hole_xy(hole)
    if sketch is None or xy is None:
        return None
    return sketch.Placement.multVec(App.Vector(xy[0], xy[1], 0))


def placed_face(hole):
    """(base feature, 'FaceN') a Single Hole sits on, or None."""
    return _ref_load(hole.Document, load_meta(hole).get("face"))


def references(hole):
    """[((obj, "EdgeN"), distance), ...] of a Single Hole."""
    sketch = helper_sketch(hole)
    if sketch is None:
        return []
    links = []
    for obj, subs in sketch.ExternalGeometry:
        for sub in subs:
            links.append((obj, sub))
    found = []
    for c in sketch.Constraints:
        if c.Name.startswith("Reference") and c.Type == "Distance":
            k = -3 - c.Second
            if 0 <= k < len(links):
                found.append((links[k], c.Value))
    return found


def set_position(hole, base, face_name, point, refs=None):
    """Put a Single Hole on `face_name` of `base` at `point` (body coordinates). refs:
    [((obj, "EdgeN"), distance or None), ...]; a None distance takes the distance the point
    has now. Two parallel edges cannot both be references (the second is dropped). Returns
    the hole's (x, y) in its sketch after the references moved it."""
    sketch = helper_sketch(hole)
    if sketch is None:
        raise HoleError("This hole is placed from a sketch; edit that sketch to move it.")
    body = owner_body(hole)
    try:
        point = snap_to_face(base.Shape.getElement(face_name), point)
    except Exception:
        raise HoleError("That face is gone. Click a face of the part.")
    current = sketch.AttachmentSupport
    same_face = (
        current
        and current[0][0] is base
        and list(current[0][1]) == [face_name]
        and sketch.MapMode == "FlatFace"
        and sketch.AttachmentOffset.isIdentity()
    )
    if not same_face:
        _attach(sketch, body, base, face_name, point)
        sketch.recompute()
    xy = _sketch_xy(sketch, point)
    wanted, lines = [], []
    for ref, distance in refs or []:
        line = _line_xy(sketch, ref)
        if line is None or any(_parallel(line, other) for other in lines):
            continue
        if distance is None:
            distance = point_line_distance(xy, line)
        wanted.append((ref, distance))
        lines.append(line)
    _rebuild_sketch(sketch, xy, wanted[:2])
    sketch.solve()
    meta = load_meta(hole)
    meta["face"] = _ref_json((base, face_name))
    _save_meta(hole, meta)
    return hole_xy(hole)


def move_to(hole, xy):
    """Move a Single Hole's point to (x, y) in its sketch (the centre dragged or typed). The
    reference distances follow, like Fusion's dimensions while you drag."""
    sketch = helper_sketch(hole)
    if sketch is None:
        return
    refs = []
    for ref, _old in references(hole):
        line = _line_xy(sketch, ref)
        if line is not None:
            refs.append((ref, point_line_distance(xy, line)))
    _rebuild_sketch(sketch, xy, refs)
    sketch.solve()


def set_reference_distance(hole, index, distance):
    """Type a reference distance (index 0 or 1)."""
    sketch = helper_sketch(hole)
    if sketch is None:
        return
    name = "Reference%d" % (index + 1)
    for i, c in enumerate(sketch.Constraints):
        if c.Name == name:
            if distance <= 0:
                raise HoleError("A reference distance must be more than 0.")
            sketch.setDatum(i, App.Units.Quantity("%r mm" % float(distance)))
            sketch.solve()
            return


def drop_orphans(body):
    """Helper sketches whose hole was deleted (timeline Delete keeps a hole's sketch)."""
    doc = body.Document
    for obj in list(body.Group):
        if is_helper(obj) and hole_of(obj) is None:
            try:
                body.removeObject(obj)
                doc.removeObject(obj.Name)
            except Exception:
                pass


# -- making holes ------------------------------------------------------------------------------
def _new_hole(body, name):
    hole = body.newObject(TYPE, name)
    hole.Refine = True
    # Points, circles and arcs (FreeCAD's bit mask 1 | 2 | 4): Fusion drills at sketch points
    # and circle centres, whatever FreeCAD's preference for new holes says.
    try:
        hole.BaseProfileType = 7
    except Exception:
        pass
    return hole


def _check_base(base):
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise HoleError("A hole needs a solid. Extrude a sketch first.")


def make_single(body, base, face_name, point, options=None, name="Hole", refs=None):
    """A Single Hole on face `face_name` of `base` at `point` (body coordinates)."""
    _check_base(base)
    drop_orphans(body)
    sketch = body.newObject(SKETCH_TYPE, "HoleSketch")
    _mark(sketch, SKETCH_ROLE)
    hole = _new_hole(body, name)
    _attach(sketch, body, base, face_name, point)
    sketch.recompute()
    hole.Profile = (sketch, [""])
    body.Tip = hole
    sketch.Label = helper_label(hole)
    _hide(sketch)
    set_position(hole, base, face_name, point, refs)
    apply(hole, dict(options_with_defaults(options), placement="single", flip=False))
    return hole


def sketch_targets(sketch):
    """Sub-elements of a sketch a hole can be drilled at: lone points ('VertexN', not the
    end of a curve) and circles / arcs ('EdgeN', at their centre)."""
    shape = sketch.Shape
    found = []
    in_edges = set()
    for edge in shape.Edges:
        for v in edge.Vertexes:
            in_edges.add((round(v.Point.x, 7), round(v.Point.y, 7), round(v.Point.z, 7)))
    for i, edge in enumerate(shape.Edges, start=1):
        if edge.Curve.TypeId == "Part::GeomCircle":
            found.append("Edge%d" % i)
    for i, v in enumerate(shape.Vertexes, start=1):
        key = (round(v.Point.x, 7), round(v.Point.y, 7), round(v.Point.z, 7))
        if key not in in_edges:
            found.append("Vertex%d" % i)
    return found


def pick_target(sketch, sub):
    """What a click on a sketch element drills at: a circle or arc -> its edge (centre), a
    point -> that vertex (a curve's end point too, as Fusion's sketch points), None for
    lines and other curves."""
    try:
        element = sketch.Shape.getElement(sub)
    except Exception:
        return None
    if sub.startswith("Edge"):
        return sub if element.Curve.TypeId == "Part::GeomCircle" else None
    if sub.startswith("Vertex"):
        # A circle's seam vertex is not a point the user drew: use the circle.
        for i, edge in enumerate(sketch.Shape.Edges, start=1):
            if edge.Curve.TypeId == "Part::GeomCircle" and edge.isClosed():
                if any(v.isSame(element) for v in edge.Vertexes):
                    return "Edge%d" % i
        return sub
    return None


def make_from_sketch(body, sketch, subs, options=None, name="Hole"):
    """Holes at sketch points/circles (subs empty: every point and circle of the sketch)."""
    base = body.Tip
    _check_base(base)
    if not (subs or sketch_targets(sketch)):
        raise HoleError("That sketch has no points or circles to drill at.")
    hole = _new_hole(body, name)
    hole.Profile = (sketch, list(subs or []))
    body.Tip = hole
    opts = dict(options_with_defaults(options), placement="sketch")
    if "flip" not in (options or {}):
        opts["flip"] = auto_flip(hole)
    apply(hole, opts)
    return hole


def set_sketch_points(hole, sketch, subs):
    hole.Profile = (sketch, list(subs or []))


def picked_targets(hole):
    """The sketch and sub-elements a From Sketch hole drills at."""
    link = hole.Profile
    if not link:
        return None, []
    return link[0], [s for s in (link[1] or []) if s]


# -- where the holes are -----------------------------------------------------------------------
def centres(hole):
    """[(centre, direction)] in global coordinates: where each hole starts and the way it
    goes into the part."""
    sketch = profile_sketch(hole)
    if sketch is None:
        return []
    body = owner_body(hole)
    place = body.getGlobalPlacement() if body is not None else App.Placement()
    normal = sketch.Placement.Rotation.multVec(Z)
    direction = normal * (1.0 if hole.Reversed else -1.0)
    subs = [s for s in (hole.Profile[1] or []) if s] if hole.Profile else []
    subs = subs or sketch_targets(sketch)
    found = []
    shape = sketch.Shape
    for sub in subs:
        try:
            element = shape.getElement(sub)
        except Exception:
            continue
        if sub.startswith("Edge"):
            if element.Curve.TypeId != "Part::GeomCircle":
                continue
            point = element.Curve.Center
        else:
            point = element.Point
        found.append((place.multVec(point), place.Rotation.multVec(direction)))
    return found


def auto_flip(hole):
    """True when the holes must go the other way to reach material (a sketch under the
    part): Fusion drills into the part."""
    base = hole.BaseFeature
    if base is None or base.Shape.isNull():
        return False
    sketch = profile_sketch(hole)
    if sketch is None:
        return False
    body = owner_body(hole)
    place = body.getGlobalPlacement().inverse() if body is not None else App.Placement()
    was = hole.Reversed
    hole.Reversed = False
    try:
        spots = centres(hole)
    finally:
        hole.Reversed = was
    for point, direction in spots:
        p = place.multVec(point)
        d = place.Rotation.multVec(direction)
        eps = 1e-3
        ahead = _inside(base.Shape, p + d * eps)
        behind = _inside(base.Shape, p - d * eps)
        if ahead != behind:
            return behind
    return False


def _inside(shape, point):
    try:
        return shape.isInside(point, 1e-7, False)
    except Exception:
        return False


def _axis_hits(shape, start, direction, length):
    """Distances along the ray where it is inside `shape`: [(t_in, t_out), ...]."""
    import Part

    line = Part.makeLine(start, start + direction * length)
    try:
        common = shape.common(line)
    except Exception:
        return []
    spans = []
    for edge in common.Edges:
        a = (edge.Vertexes[0].Point - start).dot(direction)
        b = (edge.Vertexes[-1].Point - start).dot(direction)
        spans.append((min(a, b), max(a, b)))
    return sorted(spans)


def through_length(hole, base=None):
    """How far the first hole runs through material (from its start to where it leaves the
    part for the last time), or 0."""
    base = base if base is not None else hole.BaseFeature
    spots = centres(hole)
    if base is None or base.Shape.isNull() or not spots:
        return 0.0
    body = owner_body(hole)
    inv = body.getGlobalPlacement().inverse() if body is not None else App.Placement()
    point, direction = spots[0]
    p, d = inv.multVec(point), inv.Rotation.multVec(direction)
    reach = base.Shape.BoundBox.DiagonalLength * 2.0 + 1.0
    spans = _axis_hits(base.Shape, p, d, reach)
    return spans[-1][1] if spans else 0.0


def depth_to(hole, ref):
    """The depth that takes the first hole to the face or plane `ref` = (obj, sub)."""
    import Part

    obj, sub = ref
    spots = centres(hole)
    if not spots:
        raise HoleError("Place the hole first.")
    point, direction = spots[0]
    if obj.TypeId in PLANE_TYPES:
        # Origin and construction planes: an infinite plane through their placement.
        place = obj.getGlobalPlacement()
        return _plane_distance(point, direction, place.Base, place.Rotation.multVec(Z))
    try:
        face = obj.Shape.getElement(sub)
    except Exception:
        raise HoleError("That face no longer exists. Pick the face again.")
    face = face.copy()
    base_place = body_placement(obj)
    if not base_place.isIdentity():
        face.transformShape(base_place.toMatrix())
    if face.Surface.TypeId == "Part::GeomPlane":
        c = face.Vertexes[0].Point if face.Vertexes else face.CenterOfMass
        return _plane_distance(point, direction, c, face.normalAt(0, 0))
    else:
        reach = face.BoundBox.DiagonalLength + (face.BoundBox.Center - point).Length + 1.0
        line = Part.makeLine(point, point + direction * reach)
        hits = [
            (v.Point - point).dot(direction)
            for v in line.section(face).Vertexes
            if (v.Point - point).dot(direction) > TOL
        ]
        if not hits:
            raise HoleError("The hole does not reach that face. Pick another face.")
        t = min(hits)
    if t <= TOL:
        raise HoleError("That face is not ahead of the hole. Pick a face the hole runs into.")
    return t


def _plane_distance(point, direction, origin, normal):
    denom = direction.dot(normal)
    if abs(denom) < 1e-9:
        raise HoleError("The hole runs parallel to that face and never reaches it.")
    t = (origin - point).dot(normal) / denom
    if t <= TOL:
        raise HoleError("That face is not ahead of the hole. Pick a face the hole runs into.")
    return t


# -- options <-> the PartDesign::Hole ----------------------------------------------------------
def _set(obj, prop, value):
    """Set a property only when it changes (every write marks the feature for recompute)."""
    current = getattr(obj, prop)
    if hasattr(current, "Value"):
        if abs(current.Value - float(value)) <= 1e-12:
            return
    elif current == value:
        return
    setattr(obj, prop, value)


def designation_of(options):
    d = tables.find(options["standard"], options["designation"])
    if d is None:
        sizes = tables.designations(options["standard"], options["size"])
        d = sizes[0] if sizes else None
    if d is None:
        raise HoleError("Unknown thread size %s." % options["designation"])
    return d


def apply(hole, options):
    """Write the Fusion options onto the PartDesign::Hole (and remember the rest)."""
    o = options_with_defaults(options)
    for key, allowed in (
        ("extent", EXTENTS),
        ("hole_type", HOLE_TYPES),
        ("tap_type", TAP_TYPES),
        ("drill_point", DRILL_POINTS),
    ):
        if o[key] not in allowed:
            raise HoleError("%s must be one of %s" % (key, ", ".join(allowed)))
    tap = o["tap_type"]
    pitch = 0.0
    if tap == "simple":
        _set(hole, "ThreadType", "None")
        if hole.Threaded:
            hole.Threaded = False
        if o["diameter"] <= 0:
            raise HoleError("The diameter must be more than 0.")
        _set(hole, "Diameter", o["diameter"])
    else:
        d = designation_of(o)
        pitch = d.pitch
        _set(hole, "ThreadType", d.series)
        _set(hole, "ThreadSize", d.freecad)
        if tap == "clearance":
            if hole.Threaded:
                hole.Threaded = False
            _set(hole, "ThreadFit", tables.clearance_fit(d.series, o["fit"]))
        else:
            if not hole.Threaded:
                hole.Threaded = True
            _set(hole, "ThreadClass", tables.freecad_class(d.series, o["thread_class"]))
            _set(hole, "ThreadDirection", "Left" if o["direction"] == "left" else "Right")
            _set(hole, "ModelThread", bool(o["modeled"]))
    _set(hole, "Reversed", bool(o["flip"]) and placement_of(hole) == "sketch")
    if o["extent"] == "all":
        _set(hole, "DepthType", "ThroughAll")
    else:
        if o["extent"] == "to":
            if not o.get("to"):
                raise HoleError("Pick the face or plane the hole goes to.")
            depth = depth_to(hole, o["to"])
            o["depth"] = depth
        else:
            depth = float(o["depth"])
        if depth <= 0:
            raise HoleError("The depth must be more than 0.")
        _set(hole, "DepthType", "Dimension")
        _set(hole, "Depth", depth)
    _set(hole, "DrillPoint", "Angled" if o["drill_point"] == "angle" else "Flat")
    if o["drill_point"] == "angle":
        if not 0 < o["drill_angle"] < 180:
            raise HoleError("The drill point angle must be between 0 and 180 degrees.")
        _set(hole, "DrillPointAngle", o["drill_angle"])
    if tap == "tapped":
        if o["full_tap"] and not (o["extent"] == "all" and o["modeled"]):
            _set(hole, "ThreadDepthType", "Hole Depth")
        else:
            if o["full_tap"]:
                # A through hole: a modeled thread as long as the part is thick, not as long
                # as FreeCAD's through-all length (twice the part's size: far too slow).
                length = through_length(hole) + pitch
            else:
                length = float(o["tap_depth"])
                if length <= 0:
                    raise HoleError("The tap depth must be more than 0.")
            _set(hole, "ThreadDepthType", "Dimension")
            _set(hole, "ThreadDepth", length)
    kind = o["hole_type"]
    if kind == "simple":
        _set(hole, "HoleCutType", "None")
    elif kind == "counterbore":
        _set(hole, "HoleCutType", "Counterbore")
        _set(hole, "HoleCutDiameter", o["cbore_diameter"])
        _set(hole, "HoleCutDepth", o["cbore_depth"])
    else:
        _set(hole, "HoleCutType", "Countersink")
        _set(hole, "HoleCutCountersinkAngle", o["csink_angle"])
        _set(hole, "HoleCutDiameter", o["csink_diameter"])
    meta = load_meta(hole)
    meta.update(
        {
            "v": 1,
            "placement": placement_of(hole),
            "extent": o["extent"],
            "to": _ref_json(o.get("to")),
            "fit": o["fit"],
            "thread_class": o["thread_class"],
            "full_tap": bool(o["full_tap"]),
            "tap_depth": float(o["tap_depth"]),
            "tap_type": tap,
            "standard": o["standard"],
            "designation": o["designation"],
            "user_flip": bool(o.get("user_flip", meta.get("user_flip", False))),
        }
    )
    _save_meta(hole, meta)
    sync_label(hole)


def read(hole):
    """The Fusion options of an existing hole (SciForge's or one made in FreeCAD)."""
    o = dict(DEFAULTS)
    meta = load_meta(hole)
    o["placement"] = placement_of(hole)
    o["flip"] = bool(hole.Reversed)
    o["user_flip"] = bool(meta.get("user_flip", False))
    if hole.DepthType == "ThroughAll":
        o["extent"] = "all"
    else:
        o["extent"] = "to" if meta.get("extent") == "to" else "distance"
        o["depth"] = hole.Depth.Value
        if o["extent"] == "to":
            o["to"] = _ref_load(hole.Document, meta.get("to"))
            if o["to"] is None:
                o["extent"] = "distance"
    o["drill_point"] = "angle" if hole.DrillPoint == "Angled" else "flat"
    o["drill_angle"] = hole.DrillPointAngle.Value
    cut = hole.HoleCutType
    if cut == "None":
        o["hole_type"] = "simple"
    elif cut in COUNTERSINK_CUTS:
        o["hole_type"] = "countersink"
        o["csink_diameter"] = hole.HoleCutDiameter.Value
        o["csink_angle"] = hole.HoleCutCountersinkAngle.Value
    else:
        o["hole_type"] = "counterbore"
        o["cbore_diameter"] = hole.HoleCutDiameter.Value
        o["cbore_depth"] = hole.HoleCutDepth.Value
    series = hole.ThreadType
    o["diameter"] = hole.Diameter.Value
    if series == "None" or series not in tables.TABLES:
        o["tap_type"] = "simple"
    else:
        d = tables.from_freecad(series, hole.ThreadSize)
        if d is not None:
            o["standard"] = d.standard
            o["size"] = d.size
            o["designation"] = d.label
        if hole.Threaded:
            o["tap_type"] = "tapped"
            o["thread_class"] = hole.ThreadClass
            remembered = meta.get("thread_class")
            if remembered in tables.classes(o["standard"], True):
                o["thread_class"] = remembered
            o["direction"] = "left" if hole.ThreadDirection == "Left" else "right"
            o["modeled"] = bool(hole.ModelThread)
            if hole.ThreadDepthType == "Hole Depth":
                o["full_tap"] = True
            else:
                o["full_tap"] = bool(meta.get("full_tap", False)) and o["extent"] == "all"
                o["tap_depth"] = float(meta.get("tap_depth", hole.ThreadDepth.Value))
                if not o["full_tap"]:
                    o["tap_depth"] = hole.ThreadDepth.Value
        else:
            o["tap_type"] = "clearance"
            o["fit"] = tables.fit_from_freecad(series, hole.ThreadFit)
    return o


def thread_pitch(hole):
    if hole.ThreadType in tables.TABLES:
        d = tables.from_freecad(hole.ThreadType, hole.ThreadSize)
        if d is not None:
            return d.pitch
    return 0.0


def cosmetic_threads(hole):
    """Where a tapped hole that is not modeled has its thread (drawn as a cosmetic thread):
    [{"start", "direction" (global), "radius" (drilled), "major", "length", "pitch",
    "left"}], or [] for any other hole."""
    if not hole.Threaded or hole.ModelThread or hole.ThreadType not in tables.TABLES:
        return []
    d = tables.from_freecad(hole.ThreadType, hole.ThreadSize)
    if d is None:
        return []
    if hole.ThreadDepthType == "Dimension":
        length = hole.ThreadDepth.Value
    elif hole.DepthType == "ThroughAll":
        length = through_length(hole)
    else:
        length = hole.Depth.Value
    found = []
    for centre, direction in centres(hole):
        found.append(
            {
                "start": centre,
                "direction": direction,
                "radius": hole.Diameter.Value / 2.0,
                "major": d.diameter / 2.0,
                "length": length,
                "pitch": d.pitch,
                "left": hole.ThreadDirection == "Left",
            }
        )
    return found


# -- removing ----------------------------------------------------------------------------------
def _delete(obj):
    doc = obj.Document
    body = owner_body(obj)
    try:
        if body is not None:
            body.removeObject(obj)
    except Exception:
        pass
    try:
        doc.removeObject(obj.Name)
    except Exception:
        pass


def remove(hole):
    """Delete a hole and the helper sketch SciForge made for it."""
    body = owner_body(hole)
    base = hole.BaseFeature
    helper = helper_sketch(hole)
    was_tip = body is not None and body.Tip is hole
    _delete(hole)
    if helper is not None:
        _delete(helper)
    if was_tip and base is not None:
        try:
            body.Tip = base
        except Exception:
            pass
