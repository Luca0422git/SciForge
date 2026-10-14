# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Breakout Section View, on TechDraw (no Qt: the command is in
drawing_breakout_ui.py).

A breakout takes material away inside a closed boundary drawn on a view, from the front
of the parts down to a depth (or through them all), so that what lies inside shows in
that same view, its cut floor hatched. TechDraw 1.1 has no breakout view: the view
itself is given a trimmed copy of its parts to draw (BreakoutCut below, a hidden shape
made again from the parts whenever they change, before the view in a recompute), so its
dimensions, annotations and the views made from it stay where they are; the hatching of
the cut floor is drawn as thin cosmetic lines of the view.

    view.SciForgeBreakout      JSON {"points": [[u, v]...] (view coordinates),
                               "depth": mm from the front, or null: through all}
    view.SciForgeCutSources    the parts the view shows
    view.SciForgeDepthClip     the trimmed copy (view.Source = [it])
    view.SciForgeBreakoutTags  the hatch lines' cosmetic tags

A section or detail view made from a view with a breakout shows the breakout too
(TechDraw cuts and enlarges what the parent view draws); projected views do not.
"""

import json

import FreeCAD as App

from . import drawing
from . import drawing_core as core
from . import log, warn

V = App.Vector
FRONT_MARGIN = 1.0  # mm in front of the parts the cut starts
HATCH_LINE = 1  # continuous
HATCH_WIDTH = 0.13


def breakout_of(view):
    try:
        data = json.loads(drawing._get(view, "SciForgeBreakout", "") or "{}")
    except ValueError:
        return None
    pts = data.get("points") or []
    if len(pts) < 3:
        return None
    return {"points": [tuple(p) for p in pts], "depth": data.get("depth")}


def has_breakout(view):
    return breakout_of(view) is not None


def real_sources(view):
    """The parts a view shows (not the trimmed copy it may draw)."""
    cut = [s for s in (drawing._get(view, "SciForgeCutSources", []) or []) if drawing.alive(s)]
    if cut:
        return cut
    return [s for s in view.Source if drawing.alive(s) and drawing.kind(s) != "DrawingDepth"]


def inside(points, p):
    """True when the point p lies inside the closed boundary `points`."""
    return core.point_in_polygon(points, p)


def _parts_shape(sources):
    import Part

    from . import bodies

    shapes = []
    for src in sources:
        try:
            shape = bodies.global_shape(src)
        except Exception:
            shape = src.Shape.copy()
        if not shape.isNull():
            shapes.append(shape)
    return Part.makeCompound(shapes) if shapes else None


def _front_back(axes, whole):
    """(front, back): how far along the view's direction the parts reach, model mm."""
    d = axes[2]
    values = [v.Point.x * d[0] + v.Point.y * d[1] + v.Point.z * d[2] for v in whole.Vertexes]
    box = whole.BoundBox
    corners = [
        (x, y, z)
        for x in (box.XMin, box.XMax)
        for y in (box.YMin, box.YMax)
        for z in (box.ZMin, box.ZMax)
    ]
    values += [c[0] * d[0] + c[1] * d[1] + c[2] * d[2] for c in corners]
    return max(values), min(values)


def _matrix(axes):
    x, y, d = axes
    return App.Matrix(x[0], x[1], x[2], 0, y[0], y[1], y[2], 0, d[0], d[1], d[2], 0, 0, 0, 0, 1)


def _centre_of_parts(axes, whole):
    """The middle of the whole parts as a view sees them (TechDraw centres a view there,
    as drawing.centre_of): the boundary's coordinates are measured from it."""
    d = axes[2]
    box = whole.transformed(_matrix(axes), True).optimalBoundingBox(False, False)
    c = box.Center
    return core.to_model(axes, (d[0] * c.z, d[1] * c.z, d[2] * c.z), c.x, c.y)


def cut_tool(axes, points, depth, whole):
    """The prism a breakout takes away: the boundary (view coordinates) from 1 mm in front
    of the parts back `depth` mm (or through them all)."""
    import Part

    d = axes[2]
    centre = _centre_of_parts(axes, whole)
    front, back = _front_back(axes, whole)
    reach = (front - back) + 2 * FRONT_MARGIN if depth is None else depth + FRONT_MARGIN
    top = front + FRONT_MARGIN
    lift = top - (centre[0] * d[0] + centre[1] * d[1] + centre[2] * d[2])
    corners = []
    for u, v in points:
        p = core.to_model(axes, centre, u, v)
        corners.append(V(p[0] + d[0] * lift, p[1] + d[1] * lift, p[2] + d[2] * lift))
    corners.append(corners[0])
    face = Part.Face(Part.makePolygon(corners))
    return face.extrude(V(-d[0] * reach, -d[1] * reach, -d[2] * reach))


def breakout_shape(axes, sources, points, depth):
    """The parts with the breakout taken away."""
    import Part

    whole = _parts_shape(sources)
    if whole is None:
        return Part.Shape()
    tool = cut_tool(axes, points, depth, whole)
    solids = []
    for solid in whole.Solids:
        try:
            solids += solid.cut(tool).Solids
        except Exception as exc:
            warn("breakout: %s" % exc)
            solids.append(solid)
    return Part.makeCompound(solids) if solids else Part.Shape()


# ------------------------------------------------------------------ the trimmed copy
class BreakoutCut:
    """The trimmed copy a breakout view draws (a hidden Part::FeaturePython): its parts
    with the breakout taken away. It links the parts, so a recompute makes it again
    before the view that draws it (the view never draws a stale copy)."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Breakout", doc, 4)

        add("App::PropertyLinkListGlobal", "Parts", "The parts the view shows")
        add("App::PropertyVector", "ViewDirection", "The view's direction")
        add("App::PropertyVector", "ViewXDirection", "The view's X direction")
        add("App::PropertyString", "Boundary", "[[u, v]...] in the view's coordinates")
        add("App::PropertyFloat", "Depth", "mm from the front (0: through all)")

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            obj.Shape = cut_shape(obj)
        except Exception as exc:
            warn("breakout %s: %s" % (obj.Label, exc))

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def cut_shape(clip):
    import Part

    d, x = clip.ViewDirection, clip.ViewXDirection
    axes = core.view_axes((d.x, d.y, d.z), (x.x, x.y, x.z))
    try:
        points = [tuple(p) for p in json.loads(clip.Boundary or "[]")]
    except ValueError:
        points = []
    sources = [s for s in clip.Parts if drawing.alive(s)]
    if len(points) < 3 or not sources:
        return Part.Shape()
    depth = clip.Depth if clip.Depth > 0 else None
    return breakout_shape(axes, sources, points, depth)


def _write(view, clip, points, depth):
    """The breakout's boundary and depth on the view (its dialog) and on its copy."""
    drawing._add(
        view,
        "App::PropertyString",
        "SciForgeBreakout",
        json.dumps({"points": [list(p) for p in points], "depth": depth}),
    )
    boundary = json.dumps([list(p) for p in points])
    if clip.Boundary != boundary:
        clip.Boundary = boundary
    value = 0.0 if depth is None else float(depth)
    if abs(clip.Depth - value) > 1e-9:
        clip.Depth = value


def _follow_view(view, clip):
    """The copy is cut as the view looks (a base view turned later). True when changed."""
    changed = False
    for prop, wanted in (("ViewDirection", view.Direction), ("ViewXDirection", view.XDirection)):
        if (getattr(clip, prop) - wanted).Length > 1e-9:
            setattr(clip, prop, V(wanted))
            changed = True
    return changed


def add_breakout(view, points, depth=None):
    """Fusion's Breakout Section View on `view`: take away what lies inside the closed
    boundary `points` (view coordinates, 3 or more) from the front down to `depth` mm (None:
    through all)."""
    if view.TypeId not in (drawing.PART_VIEW, drawing.ITEM):
        raise drawing.DrawingError(
            "A breakout goes on a base or projected view (not on a section, detail or "
            "broken view)."
        )
    if drawing.is_isometric(view):
        raise drawing.DrawingError(
            "A breakout needs a view seen square on (front, top, side), not an isometric one."
        )
    points = [tuple(p) for p in points]
    if len(points) < 3 or abs(core.polygon_area(points)) < 1e-6:
        raise drawing.DrawingError("Click at least three points around the area to break out.")
    if depth is not None and depth <= 0:
        raise drawing.DrawingError("Type how deep the breakout goes (more than 0 mm).")
    if has_breakout(view):
        raise drawing.DrawingError(
            "This view has a breakout already: double-click it to change or remove it."
        )
    doc = view.Document
    sources = real_sources(view)
    if not sources:
        raise drawing.DrawingError("The view shows no parts.")
    drawing._add(view, "App::PropertyLinkListGlobal", "SciForgeCutSources", sources)
    clip = doc.addObject("Part::FeaturePython", "BreakoutCut")
    BreakoutCut(clip)
    drawing._mark(clip, "DrawingDepth")
    clip.Label = "%s Breakout" % view.Label
    clip.Parts = sources
    _follow_view(view, clip)
    _write(view, clip, points, depth)
    drawing._add(view, "App::PropertyLink", "SciForgeDepthClip", clip)
    clip.recompute()
    drawing._set_shown(clip, False)
    view.Source = [clip]
    refresh_hatch(view, force=True)
    log("breakout on %s (%s)" % (view.Label, "through" if depth is None else "%g mm" % depth))
    return clip


def set_depth(view, depth):
    """A new depth (None: through all); the copy is made again in the next recompute."""
    data = breakout_of(view)
    clip = drawing._get(view, "SciForgeDepthClip", None)
    if data is None or not drawing.alive(clip):
        return False
    if depth is not None and depth <= 0:
        raise drawing.DrawingError("Type how deep the breakout goes (more than 0 mm).")
    _write(view, clip, data["points"], depth)
    return True


def set_sources(view, sources):
    """The parts the view shows changed (a Full Assembly drawing took in a new body)."""
    drawing._add(view, "App::PropertyLinkListGlobal", "SciForgeCutSources", list(sources))
    clip = drawing._get(view, "SciForgeDepthClip", None)
    if drawing.alive(clip):
        clip.Parts = list(sources)
        clip.recompute()


def remove_breakout(view):
    """The view shows its whole parts again (and so do the isometric views that showed
    its cut)."""
    sources = real_sources(view)
    clear_hatch(view)
    if sources:
        view.Source = sources
    clip = drawing._get(view, "SciForgeDepthClip", None)
    for user in list(getattr(clip, "InList", []) if drawing.alive(clip) else []):
        if user is view or not drawing.is_view(user):
            continue
        if any(drawing.same(s, clip) for s in getattr(user, "Source", [])):
            own = [s for s in (drawing._get(user, "SciForgeCutSources", []) or [])]
            user.Source = [s for s in own if drawing.alive(s)] or sources
            drawing._add(user, "App::PropertyLinkListGlobal", "SciForgeCutSources", [])
    drawing._add(view, "App::PropertyString", "SciForgeBreakout", "")
    drawing._add(view, "App::PropertyLinkListGlobal", "SciForgeCutSources", [])
    clip = drawing._get(view, "SciForgeDepthClip", None)
    if drawing.alive(clip):
        drawing._add(view, "App::PropertyLink", "SciForgeDepthClip", None)
        view.Document.removeObject(clip.Name)
    return True


def refresh(view, force=False):
    """After a recompute: the view still draws its copy, cut the way it looks now; the
    floor's hatching follows the copy. True when anything changed."""
    data = breakout_of(view)
    clip = drawing._get(view, "SciForgeDepthClip", None)
    if data is None or not drawing.alive(clip):
        return False
    changed = False
    if _follow_view(view, clip):
        clip.recompute()
        changed = True
    if [s.Name for s in view.Source] != [clip.Name]:
        view.Source = [clip]
        changed = True
    if changed:
        try:
            view.recompute()
        except Exception as exc:
            warn("breakout of %s: %s" % (view.Label, exc))
    changed |= refresh_hatch(view, force=changed or force)
    return changed


# ------------------------------------------------------------------ the floor's hatching
def floor_segments(view):
    """Hatch lines (view coordinates) over the cut floor of a breakout: the faces of the
    trimmed copy facing the viewer at the breakout's depth, inside its boundary."""
    import Part

    data = breakout_of(view)
    clip = drawing._get(view, "SciForgeDepthClip", None)
    if data is None or data["depth"] is None or not drawing.alive(clip) or clip.Shape.isNull():
        return []
    sources = real_sources(view)
    whole = _parts_shape(sources)
    if whole is None:
        return []
    axes = drawing.axes_of(view)
    x, y, d = axes
    front, _back = _front_back(axes, whole)
    level = front + FRONT_MARGIN - (data["depth"] + FRONT_MARGIN)
    centre = drawing.centre_of(view)
    matrix = App.Matrix(x[0], x[1], x[2], 0, y[0], y[1], y[2], 0, d[0], d[1], d[2], 0, 0, 0, 0, 1)
    c_view = (
        sum(centre[i] * x[i] for i in range(3)),
        sum(centre[i] * y[i] for i in range(3)),
    )
    s = drawing.scale_of(view) or 1.0
    out = []
    for face in clip.Shape.Faces:
        try:
            if not isinstance(face.Surface, Part.Plane):
                continue
            n = face.normalAt(0, 0)
            if abs(n.x * d[0] + n.y * d[1] + n.z * d[2] - 1.0) > 1e-6:
                continue
            p = face.Vertexes[0].Point
            if abs(p.x * d[0] + p.y * d[1] + p.z * d[2] - level) > 1e-4:
                continue
        except Exception:
            continue
        flat = face.transformed(matrix, True)
        box = flat.BoundBox
        z = (box.ZMin + box.ZMax) / 2.0
        for a, b in core.hatch_lines(
            (box.XMin, box.YMin, box.XMax, box.YMax), drawing.HATCH_SPACING / s, 45.0
        ):
            line = Part.LineSegment(V(a[0], a[1], z), V(b[0], b[1], z)).toShape()
            for edge in flat.common(line).Edges:
                p1, p2 = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
                if (p2 - p1).Length > 1e-6:
                    out.append(
                        (
                            (p1.x - c_view[0], p1.y - c_view[1]),
                            (p2.x - c_view[0], p2.y - c_view[1]),
                        )
                    )
    return out


def hatch_of(view):
    try:
        return json.loads(drawing._get(view, "SciForgeBreakoutHatch", "") or "[]")
    except ValueError:
        return []


def clear_hatch(view):
    for tag in list(drawing._get(view, "SciForgeBreakoutTags", []) or []):
        try:
            view.removeCosmeticEdge(tag)
        except Exception:
            pass
    drawing._add(view, "App::PropertyStringList", "SciForgeBreakoutTags", [])
    drawing._add(view, "App::PropertyString", "SciForgeBreakoutHatch", "[]")


def refresh_hatch(view, force=False):
    if not drawing.has_geometry(view):
        return False
    segments = [[round(c, 5) for c in (a[0], a[1], b[0], b[1])] for a, b in floor_segments(view)]
    if not force and segments == hatch_of(view):
        return False
    clear_hatch(view)
    tags = []
    for x1, y1, x2, y2 in segments:
        tags.append(view.makeCosmeticLine(V(x1, y1, 0), V(x2, y2, 0), HATCH_LINE, HATCH_WIDTH))
    drawing._add(view, "App::PropertyStringList", "SciForgeBreakoutTags", tags)
    drawing._add(view, "App::PropertyString", "SciForgeBreakoutHatch", json.dumps(segments))
    return True


def default_depth(view):
    """Half way through the parts along the view (Fusion asks for a depth)."""
    whole = _parts_shape(real_sources(view))
    if whole is None:
        return 5.0
    front, back = _front_back(drawing.axes_of(view), whole)
    return max(round((front - back) / 2.0, 2), 0.1)
