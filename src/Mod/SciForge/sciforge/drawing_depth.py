# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Section Depth (Full / Slice / Distance) on TechDraw, and sections without
TechDraw's line across a cut hole (no Qt).

TechDraw cuts what the parent view shows and draws everything that lies behind the cut;
it has no depth. A Slice or Distance section keeps TechDraw's section (its cut faces and
hatching stay TechDraw's own) and switches off the lines that lie beyond the depth:

1. the parts TechDraw cuts are cut the same way, and what lies behind the cut is
   trimmed to the depth (Slice: a hair's breadth, so only the cut faces are left);
2. that trimmed copy is seen along the section's direction with hidden-line removal
   (TechDraw.projectEx, TechDraw's own algorithm), in the section's coordinates;
3. a line of the section that no line of the trimmed copy covers lies deeper: it is
   switched off with TechDraw's per-line format (visible = off), which the sheet, the
   PDF and the DXF all respect.

TechDraw also draws a line along a hole cut in half where the round face's seam (or the
join of its two halves) runs (Fusion draws none): a line of a straight section that only
such a seam covers, and no other edge of the parts, is switched off the same way.

The lines are worked out again when the section's lines or the parts change
(drawing.refresh calls refresh()).

    section.SciForgeDepth        JSON {"mode", "value"}       (drawing.section_depth)
    section.SciForgeDepthHidden  JSON [[index, x, y]...]: the lines switched off and
                                 their middles (getEdgeByIndex coordinates)

What they were worked out from is kept in memory only (a property written on every
first look would mark a design as changed just by opening its drawing): after opening,
the first look works them out again, and writes nothing when they are the same.
"""

import json

import FreeCAD as App

from . import drawing
from . import log, warn

V = App.Vector
TOLERANCE = 0.05  # mm (unscaled) a line of the section may lie off a line of the copy
SAMPLES = (0.1, 0.3, 0.5, 0.7, 0.9)  # where along a line it is tested (not its ends)
FRONT = 0.001  # mm in front of the cut the trimmed copy starts
MAX_LINES = 4000  # a section with more lines than this is left whole (too slow)
SILHOUETTE = 0.05  # a seam whose face is this square to the view is the hole's outline


# ------------------------------------------------------------------ the parts
def _sources(section):
    """The parts TechDraw cuts: what the section's parent view shows."""
    parent = drawing._get(section, "BaseView", None)
    found = []
    if drawing.alive(parent):
        found = [s for s in getattr(parent, "Source", []) if drawing.alive(s)]
    return found or [s for s in getattr(section, "Source", []) if drawing.alive(s)]


def _whole(sources):
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


def _fingerprint(whole):
    if whole is None:
        return "none"
    box = whole.BoundBox
    try:
        volume = whole.Volume
    except Exception:
        volume = 0.0
    return "%.4f %.4f %.4f %.4f %.4f %.4f %.4f" % (
        volume,
        box.XMin,
        box.YMin,
        box.ZMin,
        box.XMax,
        box.YMax,
        box.ZMax,
    )


def _slab(section, size, back, front):
    """A box square to the section's cut: from `back` mm behind the cut to `front` in
    front of it (behind: away from the viewer)."""
    import Part

    normal = V(section.SectionNormal)
    normal.normalize()
    origin = V(section.SectionOrigin)
    box = Part.makeBox(size, size, back + front, V(-size / 2.0, -size / 2.0, -back))
    box.Placement = App.Placement(origin, App.Rotation(V(0, 0, 1), normal))
    return box


def _common(whole, tool):
    import Part

    solids = []
    for solid in whole.Solids:
        try:
            part = solid.common(tool)
            if not part.isNull():
                solids += part.Solids
        except Exception as exc:
            warn("section depth: %s" % exc)
    return Part.makeCompound(solids) if solids else None


class _Frame:
    """The section's own coordinates: unscaled, +Y up, from the middle TechDraw centres
    the section on (the box of what lies behind the cut, seen its way)."""

    def __init__(self, section, behind):
        x, y, d = drawing.axes_of(section)
        self.d = d
        self.matrix = App.Matrix(
            x[0], x[1], x[2], 0, y[0], y[1], y[2], 0, d[0], d[1], d[2], 0, 0, 0, 0, 1
        )
        box = behind.transformed(self.matrix, True).optimalBoundingBox(True, False)
        self.middle = ((box.XMin + box.XMax) / 2.0, (box.YMin + box.YMax) / 2.0)
        self.depth = (box.ZMin + box.ZMax) / 2.0
        self.move = App.Matrix()
        self.move.move(V(-self.middle[0], -self.middle[1], 0))

    def shape(self, shape):
        return shape.transformed(self.matrix, True).transformed(self.move, True)

    def point(self, p):
        q = self.move.multVec(self.matrix.multVec(V(p)))
        return V(q.x, q.y, 0)


_CENTRES = {}  # (document, section) -> (what it was worked out from, the centre)


def cut_centre(section):
    """The model point TechDraw centres a straight section on (the middle of the box of
    what lies behind its cut, seen its way), or None. Kept until the parts or the cut
    change."""
    from . import drawing_core as core

    whole = _whole(_sources(section))
    if whole is None:
        return None
    key = _key(section)
    sig = "%s | %s %s %s %s" % (
        _fingerprint(whole),
        tuple(section.SectionOrigin),
        tuple(section.SectionNormal),
        tuple(section.Direction),
        tuple(section.XDirection),
    )
    known = _CENTRES.get(key)
    if known is not None and known[0] == sig:
        return known[1]
    size = max(whole.BoundBox.DiagonalLength * 2.0, 10.0)
    behind = _common(whole, _slab(section, size, size, FRONT))
    if behind is None:
        return None
    frame = _Frame(section, behind)
    axes = drawing.axes_of(section)
    d = axes[2]
    lift = (d[0] * frame.depth, d[1] * frame.depth, d[2] * frame.depth)
    centre = core.to_model(axes, lift, frame.middle[0], frame.middle[1])
    _CENTRES[key] = (sig, centre)
    return centre


def _seen(flat):
    """The lines of a shape (already in the section's coordinates) seen along the
    section, hidden ones too, as TechDraw's hidden-line removal finds them."""
    import Part
    import TechDraw

    edges = []
    for group in TechDraw.projectEx(flat, V(0, 0, 1)):
        try:
            edges += group.Edges
        except Exception:
            pass
    return Part.makeCompound(edges)


def kept_lines(section, whole, frame, mode, value):
    """The lines of the parts behind the cut, trimmed to the depth, as the section sees
    them (a compound of edges in the section's coordinates)."""
    import Part

    size = max(whole.BoundBox.DiagonalLength * 2.0, 10.0)
    depth = drawing.SLICE_DEPTH if mode == "Slice" else max(value, drawing.SLICE_DEPTH)
    kept = _common(whole, _slab(section, size, depth, FRONT))
    if kept is None:
        return Part.makeCompound([])
    return _seen(frame.shape(kept))


# ------------------------------------------------------------------ seams of cut holes
def _same_cylinder(a, b):
    try:
        if abs(a.Radius - b.Radius) > 1e-6:
            return False
        axis = V(a.Axis)
        axis.normalize()
        other = V(b.Axis)
        other.normalize()
        if axis.cross(other).Length > 1e-6:
            return False
        rel = V(b.Center) - V(a.Center)
        return (rel - axis * rel.dot(axis)).Length < 1e-6
    except Exception:
        return False


def _smooth_join(shape, face, edge):
    """True when the round face goes on across this straight edge: its seam, or the join
    with another piece of the same cylinder (a boolean leaves such joins)."""
    import Part

    try:
        if edge.isSeam(face):
            return True
    except Exception:
        pass
    try:
        faces = shape.ancestorsOfType(edge, Part.Face)
    except Exception:
        return False
    for other in faces:
        if other.isSame(face):
            continue
        if isinstance(other.Surface, Part.Cylinder) and _same_cylinder(face.Surface, other.Surface):
            return True
    return False


def _flat_edges(edges, frame):
    """Edges seen straight along the section (no hidden-line removal), as polylines in
    the section's coordinates."""
    import Part

    found = []
    for edge in edges:
        try:
            points = [frame.point(p) for p in edge.discretize(Number=24)]
        except Exception:
            continue
        clean = [points[0]]
        for p in points[1:]:
            if (p - clean[-1]).Length > 1e-7:
                clean.append(p)
        if len(clean) >= 2:
            found.append(Part.makePolygon(clean))
    return Part.makeCompound(found)


def seam_lines(behind, frame):
    """(seams, others): what lies behind the cut seen along the section, as compounds in
    its coordinates: the straight seams and joins of round faces that do not stand at
    the face's outline (those make TechDraw's line across a cut hole), and every other
    edge of the parts."""
    import Part

    seams = []
    others = []
    seen = set()
    d = V(*frame.d)
    for face in behind.Faces:
        surface = face.Surface
        round_face = isinstance(surface, Part.Cylinder)
        for edge in face.Edges:
            key = edge.hashCode()
            if key in seen:
                continue
            seen.add(key)
            seam = False
            if (
                round_face
                and isinstance(edge.Curve, Part.Line)
                and _smooth_join(behind, face, edge)
            ):
                m = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
                axis = V(surface.Axis)
                axis.normalize()
                rel = m - V(surface.Center)
                normal = rel - axis * rel.dot(axis)
                if normal.Length > 1e-9:
                    normal.normalize()
                    seam = abs(normal.dot(d)) > SILHOUETTE
            (seams if seam else others).append(edge)
    return _flat_edges(seams, frame), _flat_edges(others, frame)


# ------------------------------------------------------------------ the section's lines
def section_lines(section):
    """[(index, edge)] of the section's own lines (its cosmetic lines left out), as
    getEdgeByIndex gives them (unscaled, from the section's middle)."""
    found = []
    i = 0
    while i < MAX_LINES + 1:
        try:
            edge = section.getEdgeByIndex(i)
        except Exception:
            break
        if edge is None:
            break
        found.append((i, edge))
        i += 1
    cosmetic = len(drawing._get(section, "CosmeticEdges", []) or []) + len(
        drawing._get(section, "CenterLines", []) or []
    )
    return found[: max(len(found) - cosmetic, 0)]


def _signature(lines):
    total = 0.0
    for _i, edge in lines:
        try:
            a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
            total += round(a.x, 3) + 3 * round(a.y, 3) + 5 * round(b.x, 3) + 7 * round(b.y, 3)
        except Exception:
            pass
    return "%d %.3f" % (len(lines), total)


def _middle(edge):
    p = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
    return p.x, p.y


def _covered(edge, lines, flip):
    """True when the compound `lines` runs along the whole of `edge`."""
    import Part

    if lines is None or not lines.Edges:
        return False
    first, last = edge.FirstParameter, edge.LastParameter
    for t in SAMPLES:
        p = edge.valueAt(first + (last - first) * t)
        try:
            gap = Part.Vertex(V(p.x, flip * p.y, 0)).distToShape(lines)[0]
        except Exception:
            return True
        if gap > TOLERANCE:
            return False
    return True


def _flip(lines, reference):
    """Which way up the section's lines come (+1: as the parts' lines, -1: mirrored):
    the way that more of them are covered (tried on the first 40)."""
    if reference is None or not reference.Edges:
        return 1.0
    probe = lines[:40]
    return min(
        (1.0, -1.0), key=lambda f: sum(1 for _i, e in probe if not _covered(e, reference, f))
    )


def hidden_lines(section, lines, whole, mode, value):
    """{index: edge} of the section's lines to switch off: deeper than its depth, or only
    on a cut hole's seam."""
    import Part

    size = max(whole.BoundBox.DiagonalLength * 2.0, 10.0)
    behind = _common(whole, _slab(section, size, size, FRONT))
    if behind is None:
        return {}
    frame = _Frame(section, behind)
    seams, others = seam_lines(behind, frame)
    flip = _flip(lines, Part.makeCompound(others.Edges + seams.Edges))
    hidden = {}
    if mode != "Full":
        kept = kept_lines(section, whole, frame, mode, value)
        deeper = {i: e for i, e in lines if not _covered(e, kept, flip)}
        if len(deeper) == len(lines):
            # nothing of the copy covers any line: something is off (do no harm)
            warn("section depth of %s: no line lies within the depth" % section.Label)
        else:
            hidden.update(deeper)
    if seams.Edges:
        for i, e in lines:
            if i not in hidden and _covered(e, seams, flip) and not _covered(e, others, flip):
                hidden[i] = e
    return hidden


# ------------------------------------------------------------------ keeping it up to date
def stored(section):
    try:
        return json.loads(drawing._get(section, "SciForgeDepthHidden", "") or "[]")
    except ValueError:
        return []


_SIGNATURES = {}  # (document, section) -> what its lines were worked out from


def _key(section):
    doc = section.Document
    return (getattr(doc, "Uid", "") or doc.Name, section.Name)


def signature(section):
    """What the section's switched-off lines were last worked out from ("" not yet)."""
    return _SIGNATURES.get(_key(section), "")


def _apply(section, hidden, data):
    """Switch off exactly the lines `hidden` ({index: edge}); writes nothing when that is
    what is stored already. True when it changed."""
    if data == stored(section):
        return False
    try:
        section.clearGeomFormats()
    except Exception:
        pass
    for i in sorted(hidden):
        section.formatGeometricEdge(i, 1, 0.35, (0.0, 0.0, 0.0), 0)
    drawing._add(section, "App::PropertyString", "SciForgeDepthHidden", json.dumps(data))
    _repaint(section)
    return True


def clear(section):
    """Every line of the section shows again."""
    _SIGNATURES.pop(_key(section), None)
    return _apply(section, {}, [])


def _repaint(section):
    try:
        section.requestPaint()
    except Exception:
        pass


def refresh(section, force=False):
    """Switch off a straight section's lines beyond its depth and on cut holes' seams
    (again when its lines or the parts changed). True when what shows changed."""
    if not drawing.is_section(section):
        return False
    if section.TypeId != drawing.SECTION:
        return clear(section)  # (a bent cut line: TechDraw's own lines)
    mode, value = drawing.section_depth(section)
    lines = section_lines(section)
    if not lines:
        return False  # TechDraw has not drawn it yet: the next look does it
    if len(lines) > MAX_LINES:
        warn("section %s has too many lines to look through" % section.Label)
        return clear(section)
    whole = _whole(_sources(section))
    if whole is None:
        return False
    sig = "%s %g | %s | %s" % (mode, value, _signature(lines), _fingerprint(whole))
    if not force and sig == signature(section):
        return False
    try:
        hidden = hidden_lines(section, lines, whole, mode, value)
    except Exception as exc:
        # (do no harm: every line shows, the next change tries again)
        warn("lines of %s: %s" % (section.Label, exc))
        hidden = {}
    data = [[i] + [round(c, 4) for c in _middle(e)] for i, e in sorted(hidden.items())]
    changed = _apply(section, hidden, data)
    _SIGNATURES[_key(section)] = sig
    if changed:
        log(
            "section %s (depth %s): %d of %d lines switched off"
            % (
                section.Label,
                mode if mode != "Distance" else "%g mm" % value,
                len(hidden),
                len(lines),
            )
        )
    return changed


def is_hidden(section, edge, scale):
    """True when a line of the section (getVisibleEdges(True) / getHiddenEdges(True):
    scaled, +Y up) is one switched off (for the DXF)."""
    data = stored(section)
    if not data:
        return False
    try:
        mx, my = _middle(edge)
    except Exception:
        return False
    # (getEdgeByIndex gives the same lines unscaled, the same way up)
    s = scale or 1.0
    for item in data:
        if len(item) >= 3 and abs(mx / s - item[1]) < 1e-3 and abs(my / s - item[2]) < 1e-3:
            return True
    return False
