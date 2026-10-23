# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Join by Bend (Sep 2026): one bend that joins two sheet metal bodies of the same
thickness into one. FreeCAD side, no Qt: the dialog (sheetmetal_bend_join_ui.py) and the
golden-model builder both call make().

The First Edge is on the body that is changed (the step goes into its timeline); the Second
Edge is on another sheet metal body, which is used up (hidden while the step is part of the
design, like Combine's tool bodies). Both plates are extended or trimmed so that a bend of the
rule's inner radius (or the Bend Radius override) meets each tangentially; the bend runs
where the two edges overlap along the bend's axis. Each build keeps a copy of the other body
as it joined it (FrozenOther, FrozenEdge): once that body is deleted the step goes on joining
the copy (Fusion consumes the other body; a Combine keeps a deleted tool body the same way).

Refused, with the reason: different thicknesses, parallel sheets (no bend joins them), edges
that do not run along the line where the sheets would meet, edges that do not overlap.
Sources: docs/sciforge/dev/research/fusion-sheet-metal.md 2.5 (geometry G).
"""

import FreeCAD as App

from . import bodies, log, sheetmetal, sheetmetal_bend as sb, sheetmetal_bend_core as core

V = App.Vector
TYPE = "PartDesign::FeaturePython"
KIND = "SheetMetalJoinBend"


def default_options():
    return {"use_rule_radius": True, "radius": None}


def _proj2(p, origin, e1, e2):
    rel = p - origin
    return (rel.dot(e1), rel.dot(e2))


def join_shapes(shape_a, edge_a, shape_b, edge_b, thickness, radius, thickness_b=None):
    """One solid: shape_a and shape_b (both in design coordinates) joined by a bend between
    edge_a and edge_b. Raises sb.SheetMetalError."""
    if thickness_b is not None and abs(thickness_b - thickness) > 1e-6:
        raise sb.SheetMetalError(
            "The two bodies have different thicknesses (%.4g and %.4g mm): Join by Bend needs "
            "sheets of the same thickness." % (thickness, thickness_b)
        )
    fa = sb.edge_frame(shape_a, edge_a, thickness)
    fb = sb.edge_frame(shape_b, edge_b, thickness)
    na, nb = fa["normal"], fb["normal"]
    axis = na.cross(nb)
    if axis.Length < 1e-6:
        raise sb.SheetMetalError(
            "The two sheets are parallel: no bend can join them. Pick edges of sheets that "
            "meet at an angle."
        )
    d = sb.unit(axis)
    if abs(fa["dir"].dot(d)) < 1.0 - 1e-4 or abs(fb["dir"].dot(d)) < 1.0 - 1e-4:
        raise sb.SheetMetalError(
            "The edges must run along the line where the two sheets would meet (parallel to "
            "each other and to both sheets)."
        )
    into_a = fa["out"] * -1.0
    into_b = fb["out"] * -1.0
    mid_a = fa["start"] - na * (thickness / 2.0)
    mid_b = fb["start"] - nb * (thickness / 2.0)
    origin = mid_a
    e1 = into_a
    e2 = d.cross(e1)
    pa, ua = _proj2(mid_a, origin, e1, e2), (1.0, 0.0)
    pb = _proj2(mid_b, origin, e1, e2)
    ub = (into_b.dot(e1), into_b.dot(e2))
    meet = core.line_intersection(pa, ua, pb, ub)
    if meet is None:
        raise sb.SheetMetalError("The two sheets are parallel: no bend can join them.")
    s, _t = meet
    x = (pa[0] + s * ua[0], pa[1] + s * ua[1])
    rm = radius + thickness / 2.0
    try:
        ta, tb, centre, bend_deg = core.fillet_2d(x, ua, ub, rm)
    except ValueError as exc:
        raise sb.SheetMetalError(str(exc))
    if bend_deg < 0.5:
        raise sb.SheetMetalError("The sheets are in line: they need no bend to join.")

    def to3(p2, a=0.0):
        return origin + e1 * p2[0] + e2 * p2[1] + d * a

    # where along the bend's axis both edges are
    ra = sorted(((fa["start"] - origin).dot(d), (fa["end"] - origin).dot(d)))
    rb = sorted(((fb["start"] - origin).dot(d), (fb["end"] - origin).dot(d)))
    a0, a1 = max(ra[0], rb[0]), min(ra[1], rb[1])
    if a1 - a0 < 1e-3:
        raise sb.SheetMetalError("The two edges do not overlap along the bend; line them up.")
    big = (shape_a.BoundBox.DiagonalLength + shape_b.BoundBox.DiagonalLength) * 2.0 + 10.0
    pieces = []

    def prepare(shape, mid, into, normal, tangent2):
        """The plate cut back to (or extended out to) the bend's tangent line."""
        reach = (to3(tangent2) - mid).dot(into)  # > 0: the tangent line is inside the plate
        side = normal.cross(into)
        if reach > 1e-6:
            depth = max((v.Point - mid).dot(into) for v in shape.Vertexes)
            if reach >= depth - 1e-6:
                raise sb.SheetMetalError(
                    "From this edge the bend would cut away the whole plate: pick the edges "
                    "where the two plates come closest to each other."
                )
            cut = sb.frame_box(
                mid, into, side, normal, -big, reach, -big, big, -thickness, thickness
            )
            return shape.cut(cut)
        if reach < -1e-6:
            # a0 / a1 are measured along the bend's axis from `origin` (the first edge's
            # start), not from this edge's start: the two edges' starts may be at different
            # places along the axis (the edges run opposite ways, or overlap only in part)
            start = mid + into * reach - d * (mid - origin).dot(d)
            corners = [
                start + d * a0 + normal * (thickness / 2.0),
                start + d * a1 + normal * (thickness / 2.0),
                start + d * a1 - normal * (thickness / 2.0),
                start + d * a0 - normal * (thickness / 2.0),
            ]
            import Part

            section = Part.Face(Part.makePolygon(corners + [corners[0]]))
            pieces.append(section.extrude(into * (-reach)))
        return shape

    part_a = prepare(shape_a, mid_a, into_a, na, ta)
    part_b = prepare(shape_b, mid_b, into_b, nb, tb)
    import Part

    t3 = to3(ta)
    corners = [
        t3 + d * a0 + na * (thickness / 2.0),
        t3 + d * a1 + na * (thickness / 2.0),
        t3 + d * a1 - na * (thickness / 2.0),
        t3 + d * a0 - na * (thickness / 2.0),
    ]
    section = Part.Face(Part.makePolygon(corners + [corners[0]]))
    centre3 = to3(centre)
    target = to3(tb)
    probe = V(t3)
    turned = App.Rotation(d, bend_deg).multVec(probe - centre3) + centre3
    sign = 1.0 if (turned - target).Length < 1e-4 else -1.0
    bend = section.revolve(centre3, d, sign * bend_deg)
    if bend.ShapeType != "Solid" and bend.Solids:
        bend = bend.Solids[0]
    if bend.Volume < 0:
        bend.reverse()
    merged = sb.fuse_all(part_a, [part_b, bend] + pieces)
    return sb.one_solid(merged, "Join by Bend")


class JoinBendFeature:
    """Saved in files as "sciforge.sheetmetal_bend_join.JoinBendFeature": keep the name."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Join by Bend", doc)
                return True
            return False

        add("App::PropertyLinkSub", "FirstEdge", "Edge of this body")
        # Global link: the second edge sits in another body
        add("App::PropertyLinkSubGlobal", "SecondEdge", "Edge of the other body")
        if add("App::PropertyBool", "UseRuleRadius", "Use the rule's bend radius"):
            obj.UseRuleRadius = True
        if add("App::PropertyLength", "BendRadius", "Inner bend radius when not the rule's"):
            obj.BendRadius = 1.0
        if "FrozenOther" not in obj.PropertiesList:
            # The other body as the last build joined it (design coordinates), and its edge:
            # joined instead once that body is deleted.
            obj.addProperty("Part::PropertyPartShape", "FrozenOther", "Join by Bend", "", 4)
        if "FrozenEdge" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "FrozenEdge", "Join by Bend", "", 4)
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane"):
            obj.Refine = True
        bodies.mark(obj, KIND)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)
        show_used(obj)

    def onChanged(self, obj, prop):
        if prop == "UseRuleRadius":
            show_used(obj)

    def execute(self, obj):
        try:
            obj.Shape = build(obj)
        except Exception:
            bodies.pass_through(obj)
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def show_used(obj):
    """Bend Radius is shown (property editor, Change Parameters) only when it is used."""
    try:
        obj.setEditorMode("BendRadius", 2 if obj.UseRuleRadius else 0)
    except Exception:
        pass


def build(obj):
    base = obj.BaseFeature
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise sb.SheetMetalError("There is no sheet before this step.")
    body = bodies.body_of(obj)
    radius = None if obj.UseRuleRadius else float(obj.BendRadius)
    thickness, radius, _k, _rule = sb.rule_values(body, radius)
    first = obj.FirstEdge
    live = live_other(obj)
    if not first or not first[1] or (live is None and not kept_other(obj)):
        raise sb.SheetMetalError("Pick the First Edge and the Second Edge.")
    if live is not None:
        other, edge_b = live
        other_body = bodies.body_of(other)
        if other_body is None or not sheetmetal.is_sheet_metal_body(other_body):
            raise sb.SheetMetalError("The Second Edge must be on another sheet metal body.")
        thickness_b = sb.rule_values(other_body)[0]
        shape_b = bodies.global_shape(other)
    else:
        # the other body was deleted: its copy as the last build joined it (the edge check
        # still refuses a sheet of another thickness)
        shape_b, edge_b, thickness_b = obj.FrozenOther.copy(), obj.FrozenEdge, None
    shape_a = bodies.global_shape(base)
    joined = join_shapes(shape_a, first[1][0], shape_b, edge_b, thickness, radius, thickness_b)
    if live is not None:
        _keep(obj, shape_b, edge_b)
    if obj.Refine:
        try:
            joined = joined.removeSplitter()
        except Exception:
            pass
    return bodies.to_local(joined, body)


def live_other(obj):
    """(the other body's step, its edge name) while that step is in the design, else None."""
    second = getattr(obj, "SecondEdge", None)
    if not second or not second[1] or not bodies.alive(second[0]):
        return None
    return second[0], second[1][0]


def kept_other(obj):
    """True when the other body is gone and the step joins the copy kept of it."""
    if live_other(obj) is not None:
        return False
    frozen = getattr(obj, "FrozenOther", None)
    edge = getattr(obj, "FrozenEdge", "")
    return bool(edge) and frozen is not None and not frozen.isNull()


def _keep(obj, shape, edge):
    """Keep the other body as this build joined it (for when it is deleted)."""
    if "FrozenOther" not in obj.PropertiesList or "FrozenEdge" not in obj.PropertiesList:
        return
    obj.FrozenOther = shape
    if obj.FrozenEdge != edge:
        obj.FrozenEdge = edge


def used_up(obj):
    """The other body a Join by Bend uses up while it is part of the design."""
    link = getattr(obj, "SecondEdge", None)
    if not link:
        return []
    other = bodies.body_of(link[0])
    return [other] if other is not None else []


bodies.CONSUMERS[KIND] = used_up


def make(body, base, first_edge, other, second_edge, options=None, name="JoinByBend"):
    """A Join by Bend step at the history marker of `body` (built on `base`); `other` is the
    other body's step that holds second_edge."""
    opts = default_options()
    opts.update(options or {})
    obj = bodies.insert_after_tip(body, TYPE, name)
    JoinBendFeature(obj)
    obj.BaseFeature = base
    apply(obj, base, first_edge, other, second_edge, opts)
    _view(obj)
    log("join by bend %s made" % obj.Name)
    return obj


def apply(obj, base, first_edge, other, second_edge, options):
    """other None: an edit that keeps joining the copy of a deleted other body."""
    obj.FirstEdge = (base, [first_edge])
    if other is not None:
        obj.SecondEdge = (other, [second_edge])
    obj.UseRuleRadius = bool(options.get("use_rule_radius", True))
    if options.get("radius") is not None:
        obj.BendRadius = float(options["radius"])


def read(obj):
    first = obj.FirstEdge
    second = obj.SecondEdge
    return (
        obj.BaseFeature,
        first[1][0] if first and first[1] else "",
        second[0] if second else None,
        second[1][0] if second and second[1] else "",
        {"use_rule_radius": bool(obj.UseRuleRadius), "radius": float(obj.BendRadius)},
    )


def _view(obj):
    if not App.GuiUp:
        return
    try:
        from . import sheetmetal_bend_join_ui

        sheetmetal_bend_join_ui.ViewProviderJoinBend(obj.ViewObject)
    except Exception:
        pass
