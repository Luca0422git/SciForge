# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Boss (PLASTIC > CREATE > Boss) as SciForge steps (no Qt: the Boss dialog, the
golden-model builder and headless tests all call this module).

A boss is a screw-boss connection between two halves of a plastic part (an enclosure and its
lid). You draw a sketch on the parting plane between them with a point at every boss centre.
Side 1 (the head side, where the screw head sits) grows along the sketch's normal, Side 2 (the
thread side, where the screw cuts its thread) against it; Flip swaps them. Each side finds its
body by itself: the nearest solid body a ray from the point meets in that direction.

Per side (all values are millimetres or degrees):

- shape: "blank" (a solid pin, no hole), "constant_diameter" (the outer diameter is set) or
  "constant_thickness" (outer diameter = hole diameter + 2 x wall).
- a drafted shank from the parting plane (pulled back by the side's clearance) into the body,
  joined to it, with a root fillet and a tip fillet;
- an alignment step on the tip: "in" (a recess) or "out" (a spigot that fits the mate's
  recess), or "none";
- the hole: "simple", "counterbore" or "countersink"; the head side always goes through (to
  the outside, the counterbore / countersink opening from the outside face, its floor
  `major_depth` above the tip: the material under the screw head); the thread side goes
  "through", "from_top" (hole_depth deep from the tip) or "from_bottom" (stopping hole_depth
  short of the far face, a floor), its counterbore / countersink at the tip;
- ribs (gussets) around the shank: count, total angle (360 = all round), rotation from the
  sketch's X axis, thickness, draft, length from the axis or "to_next" (to the nearest wall),
  step offset (lowered from the tip), outer draft, a chamfer or fillet on the top outer corner.

Each side is one step (``SciForge::Boss``) in its own body, like Fusion's API returns one boss
feature per side; both steps share one option set (the dialog edits them together). Values
taken from the plastic rule stay linked to it (``links``): editing the rule moves them.
"""

import copy
import json
import math

import FreeCAD as App

from . import bodies, curves, log, warn
from .plastic_boss_core import (  # noqa: F401  (the Boss's settings, re-exported)
    SHAPES,
    HOLES,
    EXTENTS,
    STEPS,
    RIB_PROFILES,
    RIB_EXTENTS,
    SIDE_NUMBERS,
    SIDE_CHOICES,
    FASTENER_DEFAULTS,
    FASTENER_HEADS,
    RULE_LINKS,
    BossError,
    side_defaults,
    default_options,
    apply_rule,
    check_options,
    outer_diameter,
    rib_angles,
    summary,
    _r,
)

FP_TYPE = "PartDesign::FeaturePython"
META = "SciForgeBoss"
TYPE = "Boss"
TOL = 1e-6


# -- maths ---------------------------------------------------------------------------------------
def segments(shape, start, direction, reach):
    """[(s0, s1)] where the ray start + s*direction (s >= 0) runs inside `shape`, sorted."""
    import Part

    if shape is None or shape.isNull():
        return []
    try:
        line = Part.LineSegment(start, start + direction * reach).toShape()
        common = shape.common(line)
    except Exception:
        return []
    found = []
    for edge in common.Edges:
        if edge.Length < 1e-7:
            continue
        a = (edge.Vertexes[0].Point - start).dot(direction)
        b = (edge.Vertexes[-1].Point - start).dot(direction)
        a, b = min(a, b), max(a, b)
        if b > 1e-7:
            found.append((max(0.0, a), b))
    found.sort()
    merged = []
    for a, b in found:
        if merged and a <= merged[-1][1] + 1e-6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def reach_of(shape):
    try:
        return max(50.0, 3.0 * shape.BoundBox.DiagonalLength)
    except Exception:
        return 1000.0


def _cone(r_start, r_end, length, start, direction):
    """A cone frustum (a cylinder when the radii match) from `start` along `direction`."""
    import Part

    if abs(r_start - r_end) < 1e-9:
        return Part.makeCylinder(r_start, length, start, direction)
    return Part.makeCone(r_start, r_end, length, start, direction)


def _tan(deg):
    return math.tan(math.radians(deg))


class Frame:
    """One boss point: A (on the parting plane), d (towards the side's body), x / y (the
    sketch's axes, for the rib angles)."""

    def __init__(self, point, direction, x_axis, normal):
        self.a = App.Vector(point)
        self.d = App.Vector(direction)
        self.d.normalize()
        x = App.Vector(x_axis)
        x = x - self.d * x.dot(self.d)
        x.normalize()
        self.x = x
        y = App.Vector(normal).cross(x)
        y.normalize()
        self.y = y

    def at(self, s, rho=0.0, e=None):
        p = self.a + self.d * s
        if e is not None and rho:
            p = p + e * rho
        return p

    def radial(self, degrees):
        a = math.radians(degrees)
        e = self.x * math.cos(a) + self.y * math.sin(a)
        e.normalize()
        return e


def side_shapes(base, frame, s, label="Side"):
    """(shapes to add, shapes to cut, root info) of one side at one point. `base` is the
    side's body (global), `s` the side's resolved settings. Raises BossError."""

    reach = reach_of(base)
    hits = segments(base, frame.a, frame.d, reach)
    if not hits:
        raise BossError(
            "%s: no body found for the boss point at (%.1f, %.1f, %.1f): put the sketch on "
            "the parting plane between the two halves." % (label, frame.a.x, frame.a.y, frame.a.z)
        )
    s_in, s_out = hits[0]
    wall = s_out - s_in
    tip = float(s["clearance"])
    root = s_in + wall / 2.0
    hole = s["shape"] != "blank"
    od = outer_diameter(s)
    adds, cuts = [], []
    shank_len = root - tip
    if shank_len > 1e-3 and s_in > tip + 1e-4:
        r_tip = od / 2.0
        r_root = r_tip + shank_len * _tan(s["draft"])
        shank = _cone(r_tip, r_root, shank_len, frame.at(tip), frame.d)
        if s["tip_radius"] > TOL:
            shank = _fillet_circle_at(shank, frame.at(tip), r_tip, s["tip_radius"], label, "tip")
        adds.append(shank)
    elif tip > s_in + 1e-4 and tip >= s_out - 1e-4:
        raise BossError(
            "%s: the clearance pulls the boss tip out of the body. Make the clearance smaller."
            % label
        )
    # the alignment step on the tip
    spigot = 0.0
    if s["step"] == "out":
        h = float(s["step_depth"])
        r_top = s["step_diameter"] / 2.0
        r_base = r_top + h * _tan(s["step_draft"])
        adds.append(_cone(r_base, r_top, h, frame.at(tip), frame.d * -1.0))
        spigot = h
    elif s["step"] == "in":
        h = float(s["step_depth"])
        if tip + h >= s_out - 1e-4:
            raise BossError("%s: the alignment recess is deeper than the boss." % label)
        r_top = s["step_diameter"] / 2.0
        r_bottom = max(0.05, r_top - h * _tan(s["step_draft"]))
        cuts.append(_cone(r_top, r_bottom, h + 0.02, frame.at(tip - 0.02), frame.d))
    # ribs
    rib_info = []
    if s.get("ribs") and shank_len > 1e-3:
        s_top = tip + float(s["rib_offset"])
        if s_top >= root - 1e-3:
            raise BossError(
                "%s: the ribs' step offset is taller than the boss. Lower the step offset." % label
            )
        for angle in rib_angles(s["rib_count"], s["rib_total_angle"], s["rib_rotation"]):
            e = frame.radial(angle)
            length = float(s["rib_length"])
            if s["rib_extent"] == "to_next":
                mid = frame.at((s_top + s_in) / 2.0)
                start = mid + e * (od / 2.0 + 1e-3)
                found = segments(base, start, e, reach)
                if not found:
                    raise BossError(
                        "%s: the rib at %.0f degrees finds no wall to run to: use a length."
                        % (label, angle)
                    )
                a0, a1 = found[0]
                length = od / 2.0 + 1e-3 + a0 + (a1 - a0) / 2.0
            rib_settings = s if s["rib_extent"] == "length" else dict(s, rib_profile="none")
            adds.append(_rib(frame, e, rib_settings, s_top, root, length, od, label))
            rib_info.append((angle, length))
    # the hole
    if hole:
        r_h = s["hole_diameter"] / 2.0
        start = tip - spigot - 0.05
        if s["side"] == 1 or s["extent"] == "through":
            end = s_out + 0.05
        elif s["extent"] == "from_top":
            end = tip + float(s["hole_depth"])
            if end >= s_out - 1e-4:
                raise BossError(
                    "%s: the hole depth (%.2f mm) reaches through the part: use Through or a "
                    "smaller depth." % (label, s["hole_depth"])
                )
        else:
            end = s_out - float(s["hole_depth"])
            if end <= tip + 1e-3:
                raise BossError(
                    "%s: the floor (%.2f mm) leaves no hole: make it thinner."
                    % (label, s["hole_depth"])
                )
        length = end - start
        r_end = r_h - length * _tan(s["hole_draft"])
        if r_end <= 0.05:
            raise BossError("%s: the hole draft closes the hole. Use a smaller angle." % label)
        cuts.append(_cone(r_h, r_end, length, frame.at(start), frame.d))
        r_m = s["major_diameter"] / 2.0
        if s["hole"] == "counterbore":
            if s["side"] == 1:
                floor = tip + float(s["major_depth"])
                if floor >= s_out - 1e-4:
                    raise BossError(
                        "%s: the counterbore leaves no material under the screw head: make "
                        "its Major Depth smaller than %.2f mm." % (label, s_out - tip)
                    )
                cuts.append(_cone(r_m, r_m, s_out + 0.05 - floor, frame.at(floor), frame.d))
            else:
                depth = float(s["major_depth"])
                if tip + depth >= end - 1e-4:
                    raise BossError("%s: the counterbore is deeper than the hole." % label)
                cuts.append(_cone(r_m, r_m, depth + spigot + 0.05, frame.at(start), frame.d))
        elif s["hole"] == "countersink":
            sink = (r_m - r_h) / math.tan(math.radians(s["countersink_angle"] / 2.0))
            if s["side"] == 1:
                if s_out - sink <= tip + 1e-4:
                    raise BossError("%s: the countersink is deeper than the boss." % label)
                cuts.append(_cone(r_m, r_h, sink, frame.at(s_out), frame.d * -1.0))
                cuts.append(_cone(r_m, r_m, 0.05, frame.at(s_out), frame.d))
            else:
                top = tip - spigot
                if top + sink >= end - 1e-4:
                    raise BossError("%s: the countersink is deeper than the hole." % label)
                cuts.append(_cone(r_m, r_h, sink, frame.at(top), frame.d))
                cuts.append(_cone(r_m, r_m, 0.05, frame.at(top - 0.05), frame.d))
    info = {"s_in": s_in, "s_out": s_out, "tip": tip, "root": root, "ribs": rib_info}
    return adds, cuts, info


def _fillet_circle_at(solid, centre, radius, fillet, label, where):
    for edge in solid.Edges:
        try:
            if edge.Curve.TypeId != "Part::GeomCircle":
                continue
            if (edge.Curve.Center - centre).Length < 1e-5 and abs(
                edge.Curve.Radius - radius
            ) < 1e-5:
                return solid.makeFillet(fillet, [edge])
        except Exception as exc:
            raise BossError(
                "%s: the %s radius (%.2f mm) could not be made: %s. Use a smaller radius."
                % (label, where, fillet, exc)
            )
    return solid


def _rib(frame, e, s, s_top, s_bottom, length, od, label):
    """One rib: a slab in the plane of the axis and `e`, `rib_thickness` thick (drafted wider
    towards the root), from the axis out to `length`, from `s_top` down to `s_bottom`."""
    import Part

    height = s_bottom - s_top
    outer = length + height * _tan(s["rib_outer_draft"])
    cut = float(s["rib_cut"])
    profile = s["rib_profile"]
    if profile != "none" and cut > TOL:
        cut = min(cut, length - od / 2.0 - 1e-3, height - 1e-3)
    if profile == "none" or cut <= TOL:
        pts = [(0.0, s_top), (length, s_top), (outer, s_bottom), (0.0, s_bottom)]
        edges = None
    elif profile == "chamfer":
        drop = cut * _tan(s["rib_chamfer_angle"])
        drop = min(drop, height - 1e-3)
        pts = [
            (0.0, s_top),
            (length - cut, s_top),
            (length + drop * _tan(s["rib_outer_draft"]), s_top + drop),
            (outer, s_bottom),
            (0.0, s_bottom),
        ]
        edges = None
    else:
        pts = None
        c_rho, c_s = length - cut, s_top + cut
        k = math.sqrt(0.5)
        p0 = frame.at(s_top) + e * 0.0
        p1 = frame.at(s_top) + e * (length - cut)
        pm = frame.at(c_s - cut * k) + e * (c_rho + cut * k)
        p2 = frame.at(s_top + cut) + e * length
        p3 = frame.at(s_bottom) + e * outer
        p4 = frame.at(s_bottom)
        edges = [
            Part.LineSegment(p0, p1).toShape(),
            Part.Arc(p1, pm, p2).toShape(),
            Part.LineSegment(p2, p3).toShape(),
            Part.LineSegment(p3, p4).toShape(),
            Part.LineSegment(p4, p0).toShape(),
        ]
    if edges is None:
        points = [frame.at(sv) + e * rho for rho, sv in pts]
        wire = Part.makePolygon(points + [points[0]])
    else:
        wire = Part.Wire(edges)
    face = Part.Face(wire)
    w = frame.d.cross(e)
    w.normalize()
    t = float(s["rib_thickness"])
    spread = height * _tan(s["rib_draft"])
    full = t + 2.0 * spread
    slab = face.translated(w * (-full / 2.0 - 0.01)).extrude(w * (full + 0.02))
    if spread > 1e-6:
        q = [
            frame.at(s_top - 0.01) + w * (-t / 2.0),
            frame.at(s_top - 0.01) + w * (t / 2.0),
            frame.at(s_bottom + 0.01) + w * (t / 2.0 + spread),
            frame.at(s_bottom + 0.01) + w * (-t / 2.0 - spread),
        ]
        trap = Part.Face(Part.makePolygon(q + [q[0]]))
        prism = trap.translated(e * -1.0).extrude(e * (outer + 2.0))
        slab = slab.common(prism)
    if slab.isNull() or not slab.Solids:
        raise BossError("%s: a rib could not be made; check its sizes." % label)
    return slab.Solids[0]


def build_shape(base, frames, side_settings, label="Side"):
    """The side's body (global solid) with the boss at every frame: shanks, steps and ribs
    joined, the root fillet, then the holes cut."""
    # removeSplitter() on a result can corrupt the shapes it was made from (FreeCAD 1.1.4,
    # shared sub-shapes): work on a copy
    base = base.copy()
    adds, cuts, roots = [], [], []
    for frame in frames:
        a, c, info = side_shapes(base, frame, side_settings, label)
        adds += a
        cuts += c
        roots.append((frame, info))
    result = base
    if adds:
        result = base.fuse(adds)
        try:
            result = result.removeSplitter()
        except Exception:
            pass
        radius = float(side_settings["root_radius"])
        if radius > TOL:
            result = _root_fillet(result, base, roots, radius, side_settings, label)
    if cuts:
        result = result.cut(cuts)
        try:
            result = result.removeSplitter()
        except Exception:
            pass
    if result.isNull() or not result.Solids or not result.isValid():
        raise BossError("%s: the boss could not be joined to the body." % label)
    return result


def _root_fillet(result, base, roots, radius, s, label):
    """Fillet the new edges where the shank (and its ribs) meet the body."""
    import Part

    od = outer_diameter(s)
    edges = []
    for edge in result.Edges:
        try:
            mid = edge.valueAt(
                edge.FirstParameter + 0.5 * (edge.LastParameter - edge.FirstParameter)
            )
        except Exception:
            continue
        near = False
        for frame, info in roots:
            axial = (mid - frame.a).dot(frame.d)
            radial = ((mid - frame.a) - frame.d * axial).Length
            reach = max([od / 2.0 + radius * 3.0] + [r[1] + radius * 3.0 for r in info["ribs"]])
            if abs(axial - info["s_in"]) < 0.5 * (info["s_out"] - info["s_in"]) + 1e-6:
                if radial <= reach:
                    near = True
                    break
        if not near:
            continue
        # a new edge lies on the body's old surface; the old edges keep their shape
        try:
            if base.distToShape(Part.Vertex(mid))[0] > 1e-5:
                continue
            on_old = False
            for old in base.Edges:
                if old.distToShape(Part.Vertex(mid))[0] < 1e-6:
                    on_old = True
                    break
            if on_old:
                continue
        except Exception:
            continue
        # concave edges only: the shank / rib meets the body here
        edges.append(edge)
    if not edges:
        return result
    try:
        filleted = result.makeFillet(radius, edges)
        if filleted.isNull() or not filleted.isValid():
            raise ValueError("the fillet is not a valid solid")
        return filleted
    except Exception as exc:
        raise BossError(
            "%s: the root radius (%.2f mm) could not be made where the boss meets the body "
            "(%s). Make the root radius smaller or 0, or keep the ribs clear of the walls "
            "(rib length, rotation, or To Next)." % (label, radius, exc)
        )


# -- points of a sketch ----------------------------------------------------------------------------
def sketch_frame(sketch):
    """(origin, normal, x axis) of the sketch, global."""
    placement = sketch.getGlobalPlacement()
    normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
    x_axis = placement.Rotation.multVec(App.Vector(1, 0, 0))
    normal.normalize()
    x_axis.normalize()
    return App.Vector(placement.Base), normal, x_axis


def point_names(sketch):
    """Every "VertexN" of the sketch that is a lone sketch point (a Part.Point), or every
    vertex when the sketch has none."""
    try:
        shape = sketch.Shape
    except Exception:
        return []
    lone = []
    edges_pts = []
    for edge in shape.Edges:
        for v in edge.Vertexes:
            edges_pts.append(v.Point)
    for i, vertex in enumerate(shape.Vertexes, start=1):
        if not any((vertex.Point - p).Length < 1e-7 for p in edges_pts):
            lone.append("Vertex%d" % i)
    return lone


def global_points(refs):
    """Global positions of [(sketch, "VertexN")]."""
    found = []
    for obj, sub in refs:
        try:
            vertex = obj.Shape.getElement(sub)
        except Exception:
            raise BossError(
                "The boss point %s.%s is gone: pick the points again." % (obj.Label, sub)
            )
        found.append(curves.to_global(vertex, obj).Vertexes[0].Point)
    return found


def check_refs(refs):
    if not refs:
        raise BossError("Select sketch points: one boss at each point.")
    sketches = {obj.Name for obj, _ in refs}
    if len(sketches) != 1:
        raise BossError("The boss points must all be in one sketch.")
    obj = refs[0][0]
    if not curves.is_sketch(obj):
        raise BossError("Pick points of a sketch drawn on the parting plane.")
    for _obj, sub in refs:
        if not sub.startswith("Vertex"):
            raise BossError("Pick sketch points (not lines or faces).")
    return obj


# -- finding the two bodies ------------------------------------------------------------------------
def candidate_bodies(doc, skip=()):
    """Solid bodies that can take a boss: shown, not used up, not sheet metal."""
    used = set()
    try:
        used = {b.Name for b in bodies.consumed(doc)}
    except Exception:
        pass
    found = []
    for body in bodies.solid_bodies(doc):
        if body.Name in used or body in skip:
            continue
        if App.GuiUp and not bodies.is_shown(body):
            continue
        found.append(body)
    return found


def body_hits(body, points, direction):
    """Distance from the nearest point to where its ray first enters the body, or None."""
    shape = bodies.global_shape(body)
    best = None
    for p in points:
        hit = segments(shape, p, direction, reach_of(shape))
        if hit and (best is None or hit[0][0] < best):
            best = hit[0][0]
    return best


def find_participants(doc, points, normal, offset=0.0):
    """{+1: body or None, -1: body or None}: the nearest solid body along +normal and along
    -normal from the (offset) points."""
    parting = [p + normal * offset for p in points]
    out = {}
    for sign in (1, -1):
        best, chosen = None, None
        for body in candidate_bodies(doc):
            d = body_hits(body, parting, normal * float(sign))
            if d is not None and (best is None or d < best - 1e-9):
                best, chosen = d, body
        out[sign] = chosen
    return out


def auto_participants(refs, options, steps=()):
    """{+1: body, -1: body} as a new boss would find them (an edited one: its bodies)."""
    found = {1: None, -1: None}
    steps = [s for s in steps or () if bodies.alive(s)]
    if steps:
        for step in steps:
            found[1 if step.Toward >= 0 else -1] = bodies.body_of(step)
        return found
    sketch = check_refs(refs)
    points = global_points(refs)
    _origin, normal, _x = sketch_frame(sketch)
    return find_participants(sketch.Document, points, normal, float(options.get("offset", 0.0)))


# -- the step --------------------------------------------------------------------------------------
def load_meta(obj):
    return bodies.load_meta(obj, META)


def is_boss(obj):
    return bodies.alive(obj) and getattr(obj, "SciForgeType", "") == TYPE


def resolved_options(obj, body=None):
    """The step's options with the rule-linked fields read from the plastic rule now."""
    meta = load_meta(obj)
    options = meta.get("options") or {}
    if not options:
        raise BossError("The boss lost its settings: edit it and press OK.")
    body = body or curves.owner_body(obj)
    try:
        from . import plastic

        rule = plastic.rule_for_body(body)
        options = apply_rule(options, rule)
    except Exception as exc:
        warn("boss: the plastic rule could not be read: %s" % exc)
    return options


def side_of(options, toward):
    """1 (head side) or 2 (thread side) for a step whose body lies `toward` (+1/-1) the
    sketch normal."""
    head = 1 if not options.get("flip") else -1
    return 1 if toward == head else 2


def frames_for(sketch, points, toward, offset):
    _origin, normal, x_axis = sketch_frame(sketch)
    direction = normal * float(toward)
    return [Frame(p + normal * offset, direction, x_axis, normal) for p in points]


class BossFeature:
    """One side of a boss (``SciForge::Boss``). Saved files store
    "sciforge.plastic_boss.BossFeature": never rename."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Boss"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSubListGlobal", "Points", "The sketch points")
        if add("App::PropertyInteger", "Toward", "+1: the body lies along the sketch normal"):
            obj.Toward = 1
        add("App::PropertyString", "BossGroup", "The boss both sides belong to")
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
    for linked, subs in obj.Points or []:
        for sub in subs or []:
            found.append((linked, sub))
    return found


def compute(obj):
    import Part

    base_feature = obj.BaseFeature
    if base_feature is None or base_feature.Shape.isNull() or not base_feature.Shape.Solids:
        raise BossError("A boss needs a body to join: make the part first.")
    base = curves.to_global(base_feature.Shape, base_feature)
    body = curves.owner_body(obj)
    options = check_options(resolved_options(obj, body))
    refs = _refs(obj)
    sketch = check_refs(refs)
    toward = 1 if obj.Toward >= 0 else -1
    side = side_of(options, toward)
    settings = dict(options["side%d" % side])
    settings["side"] = side
    if not settings.get("enabled", True):
        result = base
    else:
        points = global_points(refs)
        frames = frames_for(sketch, points, toward, float(options.get("offset", 0.0)))
        result = build_shape(base, frames, settings, "Side %d" % side)
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
        from .plastic_boss_ui import ViewProviderBoss

        ViewProviderBoss(obj.ViewObject)
    except Exception as exc:
        warn("boss view provider: %s" % exc)


def _new_step(body, name, refs, toward, group, options):
    obj = bodies.insert_after_tip(body, FP_TYPE, name)
    BossFeature(obj)
    _attach_view_provider(obj)
    obj.Toward = toward
    obj.BossGroup = group
    _write(obj, refs, options)
    return obj


def _write(obj, refs, options):
    by_obj = {}
    for linked, sub in refs:
        by_obj.setdefault(linked.Name, (linked, []))[1].append(sub)
    obj.Points = [(linked, subs) for linked, subs in by_obj.values()]
    bodies.save_meta(obj, META, {"v": 1, "options": options})


def group_steps(doc, group):
    return [o for o in doc.Objects if is_boss(o) and o.BossGroup == group]


def _new_group_id(doc):
    taken = {getattr(o, "BossGroup", "") for o in doc.Objects if is_boss(o)}
    i = 1
    while "Boss%d" % i in taken:
        i += 1
    return "Boss%d" % i


def make(refs, options, participants=None, name="Boss", steps=None):
    """Create the boss (one step per side that finds a body), or rebuild `steps` (a list of
    the group's steps) with new points and options. `participants` = {+1: body, -1: body}
    overrides the automatic search. Returns the list of steps, the head side first."""
    refs = list(refs)
    sketch = check_refs(refs)
    options = check_options(copy.deepcopy(options))
    doc = sketch.Document
    points = global_points(refs)
    _origin, normal, _x = sketch_frame(sketch)
    offset = float(options.get("offset", 0.0))
    steps = [s for s in (steps or []) if bodies.alive(s)]
    if participants is None and steps:
        # an edit keeps the bodies the boss joined (a ray along the axis now runs down
        # the boss's own hole)
        participants = {1: None, -1: None}
        for step in steps:
            participants[1 if step.Toward >= 0 else -1] = bodies.body_of(step)
    if participants is None:
        participants = find_participants(doc, points, normal, offset)
    if participants.get(1) is None and participants.get(-1) is None:
        raise BossError(
            "No body found on either side of the sketch: draw the boss points on the parting "
            "plane between the two halves (or on a face of the part)."
        )
    group = steps[0].BossGroup if steps else _new_group_id(doc)
    kept = []
    for toward in (1, -1):
        body = participants.get(toward)
        side = side_of(options, toward)
        existing = None
        for step in steps:
            if bodies.alive(step) and (1 if step.Toward >= 0 else -1) == toward:
                existing = step
        if body is None:
            if existing is not None:
                bodies.remove_step(existing)
            continue
        if existing is not None and bodies.body_of(existing) is not body:
            bodies.remove_step(existing)
            existing = None
        if existing is None:
            label = "%s%s" % (name, "" if side == 1 else "_Side2")
            existing = _new_step(body, label, refs, toward, group, options)
        else:
            _write(existing, refs, options)
            existing.touch()
        kept.append((side, existing))
    kept.sort(key=lambda item: item[0])
    log("boss %s: %d side(s)" % (group, len(kept)))
    result = [step for _side, step in kept]
    from . import plastic_boss_fastener

    plastic_boss_fastener.sync(doc, result, options)
    return result


def read(step):
    """(refs, options, participants) of an existing boss (any of its steps)."""
    doc = step.Document
    steps = group_steps(doc, step.BossGroup) or [step]
    options = load_meta(step).get("options") or {}
    participants = {1: None, -1: None}
    for s in steps:
        participants[1 if s.Toward >= 0 else -1] = bodies.body_of(s)
    return _refs(step), copy.deepcopy(options), participants, steps


def stored_options(step):
    return copy.deepcopy(load_meta(step).get("options") or {})


def to_json(options):
    return json.dumps(options, sort_keys=True)
