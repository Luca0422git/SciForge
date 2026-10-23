# SPDX-License-Identifier: LGPL-2.1-or-later
"""Snap Fit (PLASTIC > CREATE), the document side (FreeCAD, no Qt: the dialog, the golden-model
builder and headless tests all use it). The numbers and checks are in plastic_snap_core.py.

One Snap Fit is one timeline step, like Fusion's, built from PartDesign pieces:

  the lead      SnapFitFeature, a step of the hook body: the body with a hook joined at each
                sketch point (base block "To Next" or a distance into the body, a drafted,
                tapered beam, the catch, the base fillet)
  a follower    SnapGrooveFollower, a hidden step of the other body (modify_bodies'
                ModifyFollower: it rolls back, is suppressed, moved and deleted with the
                lead): the groove or slot cut there, or the loop joined there. It reads every
                size from the lead.

The points are the sketch's points (Automatic) or the ones picked (Manual: their geometry
indices). Values linked to the plastic rule (thickness, draft, fillet, clearance) follow the
component's rule until a value is typed (meta "linked").

Saved documents store "sciforge.plastic_snap.SnapFitFeature" and
"sciforge.plastic_snap.SnapGrooveFollower": keep the names and the properties.
"""

import FreeCAD as App

from . import bodies, log, modify_bodies, plastic
from . import plastic_snap_core as core

V = App.Vector
FP_TYPE = "PartDesign::FeaturePython"
KIND = "SnapFit"
FOLLOWER_KIND = "SnapFitGroove"
META = "SciForgeSnapFit"
WARNING = "SciForgeWarning"
FAR = 1000.0  # mm: how far "To Next" looks for the body

# property -> (option key, kind); kind: "length", "angle", "bool", or an enum's titles
PROPS = [
    (
        "SnapType",
        "type",
        core.TYPE_TITLES,
        "Parallel / Perpendicular Hook and Groove, Hook and Loop",
    ),
    ("SelectionMode", "selection", core.SELECTION_TITLES, "All the sketch's points or picked ones"),
    ("RotationType", "rotation", core.ROTATION_TITLES, "One angle, one per snap, or aligned"),
    ("RotationAngle", "angle", "angle", "Turns the catch about the sketch normal"),
    ("Flip", "flip", "bool", "Hook on the other side of the sketch plane"),
    ("Hook", "hook", "bool", "Make the hook side"),
    ("ExtentType", "extent", core.EXTENT_TITLES, "The hook's base: to the body or a distance"),
    ("ExtentDistance", "extent_distance", "length", "Length of the base (Distance)"),
    ("BeamLength", "length", "length", "From the parting plane to the beam's end"),
    ("BeamWidth", "width", "length", "Width of the beam at its root"),
    ("RootThickness", "thickness", "length", "Thickness of the beam at its root"),
    ("TipThickness", "tip_thickness", "length", "Thickness of the beam at the catch"),
    ("CatchDepth", "catch_depth", "length", "How far the catch stands out"),
    ("CatchLength", "catch_length", "length", "Catch length along the beam"),
    ("InsertionAngle", "insertion_angle", "angle", "Lead-in face angle"),
    ("RetentionAngle", "retention_angle", "angle", "Retention face angle (90: permanent)"),
    ("DraftAngle", "draft", "angle", "Draft of the beam's sides"),
    ("BaseFillet", "fillet", "length", "Fillet at the hook's base"),
    ("Groove", "groove", "bool", "Make the groove / slot / loop on the other body"),
    ("Clearance", "clearance", "length", "Gap between the catch and the other body"),
    ("LoopThickness", "loop_thickness", "length", "Thickness of the loop's frame"),
]
PROP_OF = {key: prop for prop, key, _k, _d in PROPS}


class SnapError(ValueError):
    """A snap fit cannot be built; the message says why and what to try."""


# -- reading the sketch -------------------------------------------------------------------------
def sketch_points(sketch):
    """[(geometry index, point in design coordinates)] of the sketch's points."""
    import Part

    place = sketch.getGlobalPlacement()
    found = []
    for i, geo in enumerate(sketch.Geometry):
        if isinstance(geo, Part.Point):
            found.append((i, place.multVec(V(geo.X, geo.Y, geo.Z))))
    return found


def sketch_axes(sketch):
    """(normal, x axis) of the sketch plane in design coordinates."""
    rot = sketch.getGlobalPlacement().Rotation
    return rot.multVec(V(0, 0, 1)), rot.multVec(V(1, 0, 0))


def chosen_points(sketch, indices):
    """The points a snap fit uses: all (indices empty: Automatic) or the picked ones."""
    found = sketch_points(sketch)
    if indices:
        wanted = set(indices)
        found = [(i, p) for i, p in found if i in wanted]
    return found


def frames(sketch, options, indices=()):
    """[(origin, (ex, ey, ez))] of every snap fit (App.Vectors, design coordinates)."""
    points = chosen_points(sketch, indices)
    normal, x_axis = sketch_axes(sketch)
    n = (normal.x, normal.y, normal.z)
    x = (x_axis.x, x_axis.y, x_axis.z)
    angles = core.angles_for(options, len(points))
    out = []
    ref = None
    if options.get("rotation") == "aligned" and points:
        ref = options.get("align_point")
        if ref is None:
            c = V()
            for _i, p in points:
                c = c + p
            c = c * (1.0 / len(points))
            ref = (c.x, c.y, c.z)
    for k, (_i, p) in enumerate(points):
        if ref is not None:
            try:
                x_k = core.aligned_x((p.x, p.y, p.z), ref, n, not options.get("align_inward"))
                axes = core.frame(n, x_k, options["angle"], options["flip"])
            except ValueError:
                axes = core.frame(n, x, options["angle"], options["flip"])
        else:
            axes = core.frame(n, x, angles[k], options["flip"])
        out.append((p, tuple(V(*a) for a in axes)))
    return out


# -- geometry --------------------------------------------------------------------------------
def _matrix(origin, axes):
    ex, ey, ez = axes
    return App.Matrix(
        ex.x,
        ey.x,
        ez.x,
        origin.x,
        ex.y,
        ey.y,
        ez.y,
        origin.y,
        ex.z,
        ey.z,
        ez.z,
        origin.z,
        0,
        0,
        0,
        1,
    )


def _placed(shape, origin, axes):
    shape.transformShape(_matrix(origin, axes), True)
    return shape


def local_box(origin, axes, box):
    import Part

    x0, x1, y0, y1, z0, z1 = box
    solid = Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
    return _placed(solid, origin, axes)


def ray_hit(shape, origin, direction, far=FAR):
    """(distance to where the ray enters the solid, length it runs inside it) or None."""
    import Part

    if shape is None or shape.isNull() or not shape.Solids:
        return None
    d = V(direction)
    d.normalize()
    seg = Part.LineSegment(origin, origin + d * far).toShape()
    try:
        inside = shape.common(seg)
    except Exception:
        return None
    best = None
    for edge in inside.Edges:
        ends = [v.Point for v in edge.Vertexes]
        if not ends:
            continue
        near = min((p - origin).dot(d) for p in ends)
        if best is None or near < best[0]:
            best = (max(0.0, near), edge.Length)
    return best


def hook_solid(origin, axes, options, base_len, margin):
    """The hook of one snap fit (design coordinates): the base block from `base_len` behind
    the parting plane (plus `margin` into the body), the beam and the catch."""
    import Part

    o = options
    parts = []
    x0, x1, y0, y1 = core.base_footprint(o)
    back = base_len + margin
    if back > 1e-6:
        parts.append(local_box(origin, axes, (x0, x1, y0, y1, -back, 0.0)))
    root, tip = core.beam_sections(o)
    wires = [Part.makePolygon([V(*p) for p in sec + [sec[0]]]) for sec in (root, tip)]
    beam = Part.makeLoft(wires, True, True)
    parts.append(_placed(beam, origin, axes))
    w = core.tip_width(o) / 2.0
    outline = core.catch_profile(o)
    pts = [V(x, -w, z) for x, z in outline]
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    catch = face.extrude(V(0, 2.0 * w, 0))
    parts.append(_placed(catch, origin, axes))
    result = parts[0]
    for piece in parts[1:]:
        result = result.fuse(piece)
    try:
        result = result.removeSplitter()
    except Exception:
        pass
    return result


def _root_edges(shape, origin, axes, options, base_len):
    """The edges where the hook's base meets the body (local z = -base_len), front first
    left out when `with_front` is False."""
    ex, ey, ez = axes
    t = options["thickness"]
    w = options["width"] / 2.0
    tol = 1e-4 + 1e-6 * t
    found = {"front": [], "other": []}
    for edge in shape.Edges:
        pts = [v.Point for v in edge.Vertexes] + [
            edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
        ]
        local = [((p - origin).dot(ex), (p - origin).dot(ey), (p - origin).dot(ez)) for p in pts]
        if any(abs(z + base_len) > tol for _x, _y, z in local):
            continue
        if any(x < -t - tol or x > tol or abs(y) > w + tol for x, y, _z in local):
            continue
        xm, ym, _zm = local[-1]
        on_rect = abs(xm) < tol or abs(xm + t) < tol or abs(abs(ym) - w) < tol
        if not on_rect:
            continue
        found["front" if abs(xm) < tol else "other"].append(edge)
    return found


def fillet_roots(shape, hooks, options):
    """The base fillet on every hook's root edges (all round; else away from the catch
    side). Returns (shape, note)."""
    r = options["fillet"]
    if r <= 1e-6:
        return shape, ""
    edges_all, edges_back = [], []
    for origin, axes, base_len in hooks:
        found = _root_edges(shape, origin, axes, options, base_len)
        edges_all += found["front"] + found["other"]
        edges_back += found["other"]
    for edges in (edges_all, edges_back):
        if not edges:
            continue
        try:
            out = shape.makeFillet(r, edges)
            if out.isValid() and out.Solids:
                return out, ""
        except Exception:
            continue
    return shape, "the base fillet (%.2f mm) could not be made there: try a smaller radius" % r


def groove_tool(origin, axes, options):
    return local_box(origin, axes, core.groove_box(options))


def loop_solid(origin, axes, options, reach):
    frame_box, opening = core.loop_boxes(options, reach)
    return local_box(origin, axes, frame_box).cut(local_box(origin, axes, opening))


def loop_reach(origin, axes, options, shape):
    """Where the loop meets the loop body: the local z the frame runs down to (a little into
    the body), or None when nothing lies below it."""
    c = options["clearance"]
    t = options["loop_thickness"]
    ex, ey, ez = axes
    start_z = core.ledge_z(options)
    best = None
    for y in (-(options["width"] / 2.0 + c + 0.5 * t), options["width"] / 2.0 + c + 0.5 * t):
        start = origin + ex * (c + 0.5 * t) + ey * y + ez * start_z
        hit = ray_hit(shape, start, ez)
        if hit is None:
            return None
        reach = start_z + hit[0] + min(0.5 * t, 0.5 * hit[1])
        best = reach if best is None else max(best, reach)
    return best


# -- options on a feature -------------------------------------------------------------------------
def options_of(obj):
    meta = bodies.load_meta(obj, META)
    out = core.defaults()
    for prop, key, kind, _doc in PROPS:
        if prop not in obj.PropertiesList:
            continue
        value = getattr(obj, prop)
        if isinstance(kind, dict):
            titles = {v: k for k, v in kind.items()}
            out[key] = titles.get(value, out[key])
        elif kind in ("length", "angle"):
            out[key] = float(value.Value if hasattr(value, "Value") else value)
        else:
            out[key] = bool(value)
    out["angles"] = list(getattr(obj, "Angles", []) or [])
    out["linked"] = list(meta.get("linked", out["linked"]))
    if meta.get("align_point") is not None:
        out["align_point"] = tuple(meta["align_point"])
    out["align_inward"] = bool(meta.get("align_inward", False))
    return out


def _set(obj, prop, value):
    try:
        current = getattr(obj, prop)
        current = current.Value if hasattr(current, "Value") else current
        if current == value:
            return
    except Exception:
        pass
    setattr(obj, prop, value)


def write_options(obj, options):
    for prop, key, kind, _doc in PROPS:
        if key not in options:
            continue
        value = options[key]
        if isinstance(kind, dict):
            _set(obj, prop, kind[value])
        elif kind in ("length", "angle"):
            _set(obj, prop, float(value))
        else:
            _set(obj, prop, bool(value))
    angles = [float(a) for a in options.get("angles", [])]
    if list(obj.Angles) != angles:
        obj.Angles = angles
    meta = bodies.load_meta(obj, META)
    meta["linked"] = list(options.get("linked", []))
    meta["align_point"] = list(options["align_point"]) if options.get("align_point") else None
    meta["align_inward"] = bool(options.get("align_inward", False))
    bodies.save_meta(obj, META, meta)


def rule_of(body):
    try:
        return plastic.rule_for_body(body)
    except Exception:
        return None


def current_options(obj):
    """The feature's options with the rule-linked values from its component's rule."""
    return core.follow_rule(options_of(obj), rule_of(bodies.body_of(obj)))


def _note(obj, text):
    try:
        if WARNING not in obj.PropertiesList:
            if not text:
                return
            obj.addProperty("App::PropertyString", WARNING, "SciForge", "Timeline warning", 4 | 16)
        if getattr(obj, WARNING) != text:
            setattr(obj, WARNING, text)
    except Exception:
        pass


class SnapFitFeature:
    """The Snap Fit step (in the hook body). Saved documents store
    "sciforge.plastic_snap.SnapFitFeature": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Snap Fit", doc)
                return True
            return False

        add("App::PropertyLinkGlobal", "Sketch", "The sketch with the points")
        add("App::PropertyIntegerList", "PointIndices", "Manual: the picked points")
        add("App::PropertyFloatList", "Angles", "Independent: an angle per snap fit")
        defaults = core.defaults()
        for prop, key, kind, doc in PROPS:
            if isinstance(kind, dict):
                if add("App::PropertyEnumeration", prop, doc):
                    setattr(obj, prop, list(kind.values()))
                    setattr(obj, prop, kind[defaults[key]])
            elif kind == "length":
                if add("App::PropertyLength", prop, doc):
                    setattr(obj, prop, defaults[key])
            elif kind == "angle":
                if add("App::PropertyAngle", prop, doc):
                    setattr(obj, prop, defaults[key])
            elif add("App::PropertyBool", prop, doc):
                setattr(obj, prop, defaults[key])
        if add("App::PropertyBool", "Refine", "Merge coplanar faces, like Fusion"):
            obj.Refine = True
        bodies.mark(obj, KIND)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            bodies.pass_through(obj)
            raise SnapError("A Snap Fit needs a part to hold the hook: make the part first.")
        try:
            options = current_options(obj)
            sync_linked(obj, options)
            shape, note = build_hooks(obj, options, base)
        except Exception:
            bodies.pass_through(obj)
            raise
        _note(obj, note)
        obj.Shape = shape

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def sync_linked(obj, options):
    """Rule-linked values shown in the feature's properties follow the rule."""
    for key in options.get("linked", []):
        prop = PROP_OF.get(key)
        if prop is None:
            continue
        try:
            current = getattr(obj, prop)
            current = float(current.Value if hasattr(current, "Value") else current)
            if abs(current - options[key]) > 1e-9:
                setattr(obj, prop, options[key])
        except Exception:
            pass


def build_hooks(obj, options, base):
    """(the hook body's new solid in body coordinates, note)."""
    problems = core.validate(options)
    if problems:
        raise SnapError(problems[0])
    sketch = obj.Sketch
    if sketch is None or not bodies.alive(sketch):
        raise SnapError("The Snap Fit's sketch is gone: edit the Snap Fit and pick a sketch.")
    placed = frames(sketch, options, list(obj.PointIndices))
    if not placed:
        raise SnapError("The sketch has no points: add sketch points where the snap fits go.")
    body = bodies.body_of(obj)
    shape = bodies.global_shape(base)
    if not options["hook"]:
        return base.Shape.copy(), ""
    hooks = []
    tools = []
    for k, (origin, axes) in enumerate(placed):
        base_len, margin = hook_base(shape, origin, axes, options, k)
        tools.append(hook_solid(origin, axes, options, base_len, margin))
        hooks.append((origin, axes, base_len))
    result = shape
    for tool in tools:
        result = result.fuse(tool)
    try:
        result = result.removeSplitter()
    except Exception:
        pass
    result, note = fillet_roots(result, hooks, options)
    if not result.Solids:
        raise SnapError("The hooks could not be joined to the part.")
    if len(result.Solids) > len(shape.Solids):
        note = (note + "; " if note else "") + "a hook does not touch the part"
    out = bodies.to_local(result, body)
    if getattr(obj, "Refine", True):
        try:
            out = out.removeSplitter()
        except Exception:
            pass
    return out, note


def hook_base(shape, origin, axes, options, k=0):
    """(length of the hook's base behind the parting plane, overlap into the body)."""
    ex, ey, ez = axes
    centre = origin - ex * (0.5 * options["thickness"])
    if options["extent"] == "distance":
        hit = ray_hit(shape, centre - ez * 1e-3, ez * -1.0)
        margin = 0.0
        if hit is not None and hit[0] <= options["extent_distance"] + 1e-6:
            margin = 0.0
        return options["extent_distance"], margin
    hit = ray_hit(shape, centre + ez * 1e-3, ez * -1.0)
    if hit is None:
        raise SnapError(
            "Snap fit %d: no part behind the sketch point to hold the hook. Put the point "
            "against the hook body, or use Flip or a Distance extent." % (k + 1)
        )
    distance, inside = hit
    distance = max(0.0, distance - 1e-3)
    margin = min(0.5 * options["thickness"], 0.5 * inside)
    return distance, margin


# -- the follower in the other body --------------------------------------------------------------
class SnapGrooveFollower(modify_bodies._Follower):
    """The groove, slot or loop a Snap Fit makes in the other body. Saved documents store
    "sciforge.plastic_snap.SnapGrooveFollower": keep the name stable."""

    KIND = FOLLOWER_KIND

    def build(self, obj, lead, base_shape):
        options = current_options(lead)
        problems = core.validate(options)
        if problems:
            raise SnapError(problems[0])
        if not options["groove"]:
            return base_shape
        body = bodies.body_of(obj)
        place = body.getGlobalPlacement() if body is not None else App.Placement()
        shape = base_shape.copy()
        if not place.isIdentity():
            shape.transformShape(place.toMatrix(), True)
        result, _note = other_side(lead, options, shape)
        if not place.isIdentity():
            result = result.copy()
            result.transformShape(place.inverse().toMatrix(), True)
        return result


def other_side(lead, options, shape):
    """(the other body's solid with the grooves cut / loops joined, design coordinates; note)."""
    placed = frames(lead.Sketch, options, list(lead.PointIndices))
    result = shape
    missed = 0
    for origin, axes in placed:
        if options["type"] == "loop":
            reach = loop_reach(origin, axes, options, shape)
            if reach is None:
                missed += 1
                continue
            result = result.fuse(loop_solid(origin, axes, options, reach))
        else:
            tool = groove_tool(origin, axes, options)
            if tool.common(shape).Volume < 1e-9:
                missed += 1
                continue
            result = result.cut(tool)
    try:
        result = result.removeSplitter()
    except Exception:
        pass
    note = ""
    if missed:
        note = "%d of %d snap fits found nothing of this body to %s" % (
            missed,
            len(placed),
            "stand the loop on" if options["type"] == "loop" else "cut the groove in",
        )
    return result, note


def find_groove_body(doc, hook_body, sketch, options, indices=()):
    """The body the grooves / loops go in: the one the first groove box cuts most (parallel,
    perpendicular) or the first one under the loop (Hook and Loop); None when none."""
    placed = frames(sketch, options, indices)
    if not placed:
        return None
    origin, axes = placed[0]
    best, best_value = None, 0.0
    for body in bodies.solid_bodies(doc):
        if body is hook_body:
            continue
        try:
            shape = bodies.global_shape(body)
        except Exception:
            continue
        if shape.isNull() or not shape.Solids:
            continue
        if options["type"] == "loop":
            reach = loop_reach(origin, axes, options, shape)
            value = 1.0 / (1.0 + reach) if reach is not None else 0.0
        else:
            try:
                value = groove_tool(origin, axes, options).common(shape).Volume
            except Exception:
                value = 0.0
        if value > best_value + 1e-12:
            best, best_value = body, value
    return best


def find_hook_body(doc, sketch, options, indices=()):
    """The body behind the first sketch point (on the hook side of the sketch plane)."""
    placed = frames(sketch, options, indices)
    if not placed:
        return None
    origin, axes = placed[0]
    ex, ey, ez = axes
    centre = origin - ex * (0.5 * options["thickness"]) + ez * 1e-3
    best, best_d = None, None
    for body in bodies.solid_bodies(doc):
        try:
            hit = ray_hit(bodies.global_shape(body), centre, ez * -1.0)
        except Exception:
            hit = None
        if hit is not None and (best_d is None or hit[0] < best_d):
            best, best_d = body, hit[0]
    return best


# -- making and editing --------------------------------------------------------------------------
def is_snap_fit(obj):
    try:
        return (
            obj is not None and getattr(obj, "SciForgeType", "") == KIND and obj.TypeId == FP_TYPE
        )
    except Exception:
        return False


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .plastic_snap_ui import ViewProviderSnapFit

        ViewProviderSnapFit(obj.ViewObject)
    except Exception:
        pass


def _hide_sketch(sketch):
    if not App.GuiUp:
        return
    try:
        sketch.ViewObject.Visibility = False
    except Exception:
        pass


def _unlink_given(opts, given):
    """Values given for rule-linked fields end their link (a typed value), unless the caller
    passes "linked" itself."""
    if not given or "linked" in given:
        return opts
    for key in given:
        if key in core.RULE_FIELDS:
            opts = core.unlink(opts, key)
    return opts


def make(sketch, options=None, indices=(), hook_body=None, groove_body=None, name="SnapFit"):
    """A new Snap Fit at the sketch's points (all, or `indices`). The hook body and the other
    body are found when not given. Not recomputed. Returns the lead feature."""
    if sketch is None:
        raise SnapError("Pick a sketch with points on the parting plane.")
    doc = sketch.Document
    if hook_body is None:
        rule = rule_of(bodies.body_of(sketch))
    else:
        rule = rule_of(hook_body)
    opts = core.defaults(rule)
    opts.update(options or {})
    opts = _unlink_given(opts, options)
    problems = core.validate(opts)
    if problems:
        raise SnapError(problems[0])
    if not chosen_points(sketch, indices):
        raise SnapError("The sketch has no points: add sketch points where the snap fits go.")
    if hook_body is None:
        hook_body = find_hook_body(doc, sketch, opts, indices)
    if hook_body is None:
        raise SnapError(
            "No body lies behind the first point to hold the hook: put the sketch on the "
            "parting plane against the hook body (or use Flip)."
        )
    feature = bodies.insert_after_tip(hook_body, FP_TYPE, name)
    SnapFitFeature(feature)
    _attach_view_provider(feature)
    feature.Sketch = sketch
    feature.PointIndices = [int(i) for i in indices]
    write_options(feature, opts)
    _hide_sketch(sketch)
    set_other_body(feature, groove_body, opts)
    log("snap fit '%s' made in %s" % (feature.Label, hook_body.Label))
    return feature


def set_other_body(feature, groove_body, options=None):
    """Make the follower in the other body (found when None); returns that body or None."""
    options = options or options_of(feature)
    hook_body = bodies.body_of(feature)
    if groove_body is None and options.get("groove", True):
        groove_body = find_groove_body(
            feature.Document, hook_body, feature.Sketch, options, list(feature.PointIndices)
        )
    members = [(groove_body, None)] if groove_body is not None and options.get("groove") else []
    modify_bodies.sync(feature, members, SnapGrooveFollower, feature.Name + "Groove")
    return groove_body


def other_body(feature):
    followers = modify_bodies.followers_of(feature)
    return bodies.body_of(followers[0]) if followers else None


def update(feature, sketch=None, options=None, indices=None, groove_body=False):
    """Change an existing Snap Fit (only what is given). groove_body False: keep the other
    body; None: find it again; a body: that one."""
    if sketch is not None:
        feature.Sketch = sketch
    if indices is not None:
        feature.PointIndices = [int(i) for i in indices]
    merged = options_of(feature)
    merged.update(options or {})
    merged = _unlink_given(merged, options)
    problems = core.validate(merged)
    if problems:
        raise SnapError(problems[0])
    write_options(feature, merged)
    if groove_body is False:
        groove_body = other_body(feature)
        if groove_body is None and merged.get("groove"):
            groove_body = None
    set_other_body(feature, groove_body, merged)
    return feature


def read(feature):
    """(sketch, point indices, options, other body) of an existing Snap Fit."""
    return feature.Sketch, list(feature.PointIndices), options_of(feature), other_body(feature)


def remove(feature):
    modify_bodies.remove_all(feature)
    bodies.remove_step(feature)
