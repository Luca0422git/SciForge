# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's SHEET METAL > MODIFY > Corner Closure: close the corner where two flanges of a
sheet metal body meet. FreeCAD side, no Qt: the dialog (sheetmetal_corner_ui.py) and the
golden-model builder both call make().

Picks: a Dominant Edge and a Submissive Edge, each an edge of a flange's end at the corner
(where the two flanges face each other). Each flange's end (its wall, and its bend when the
bend ends in the same plane) is taken further in line with the flange (Extend Aligned) until:

* Symmetric Gap: both stop half the Gap short of the corner's bisector (a mitred corner);
  Extend Aligned off takes each end square toward the other flange instead of in line;
* Overlap: the dominant flange runs over the other's end, to its outside face (less
  (1 - Overlap) of the thickness, Flip Overlap swaps which runs over); the submissive one
  stops the Gap short of the dominant's inside face.

Relief: Tear (no cut: the bends are carried to the mitre with the walls, the Gap between
them); Trim To Bend (whatever lies inside both bend zones is cut away: each bend stops where
the other one starts, the corner stays open under the closed walls; trim_to_bend); or, with
Symmetric Gap, a Round / Square hole cut in the flat state at its Relief Placement
(Intersection, Vertex, or Tangent for a Round): the closed part is laid flat with sm-flat's
unfolder and the cut folded back (corner_relief).
Sources: docs/sciforge/dev/research/fusion-sheet-metal.md 2.9 (geometry G).
"""

import FreeCAD as App

from . import bodies, log, sheetmetal_bend as sb, sheetmetal_bend_core as core

V = App.Vector
TYPE = "PartDesign::FeaturePython"
KIND = "SheetMetalCornerClosure"
ALIGNMENTS = [core.CLOSURE_LABELS[k] for k in core.CLOSURE_ALIGNMENTS]
RELIEFS = [core.CLOSURE_RELIEF_LABELS[k] for k in core.CLOSURE_RELIEFS]
PLACEMENTS = [core.CLOSURE_PLACEMENT_LABELS[k] for k in core.CLOSURE_PLACEMENTS]
BUILT_RELIEFS = ("tear", "trim_to_bend", "round", "square")
CUT_RELIEFS = ("round", "square")


def default_options():
    return {
        "alignment": "symmetric",
        "gap": None,  # None: the rule's miter gap
        "overlap": 1.0,
        "flip_overlap": False,
        "extend_aligned": True,
        "relief": "trim_to_bend",  # or tear, round, square
        "relief_size": None,  # None: the rule's 2-bend corner relief size
        "placement": "intersection",  # Round / Square: intersection, tangent or vertex
    }


def end_frame(shape, edge_name, thickness):
    """A picked edge at a flange's end: the flange's face it lies on (a face with the sheet
    behind it, T away) and the end face (the other face of the edge, square to it). The same
    keys as sheetmetal_bend.edge_frame. Raises SheetMetalError with the reason."""
    import Part

    try:
        edge = shape.getElement(edge_name)
    except Exception:
        raise sb.SheetMetalError("%s is not an edge of the body any more." % edge_name)
    if not isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
        raise sb.SheetMetalError("Pick a straight edge at the end of a flange.")
    faces = [f for f in shape.ancestorsOfType(edge, Part.Face) if sb.is_plane(f)]
    if len(faces) != 2:
        raise sb.SheetMetalError(
            "Pick an edge at the end of a flange, where its face meets its end."
        )
    walls = [f for f in faces if sb.face_thickness(shape, f, thickness)]
    ends = [f for f in faces if f not in walls]
    if len(walls) != 1 or len(ends) != 1:
        raise sb.SheetMetalError(
            "Pick an edge at the end of a flange, where its face meets its end."
        )
    wall, end = walls[0], ends[0]
    n_wall, n_end = sb.plane_normal(wall), sb.plane_normal(end)
    if abs(n_wall.dot(n_end)) > 0.99:
        raise sb.SheetMetalError(
            "Pick an edge at the end of a flange, where its face meets its end."
        )
    start, stop = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    direction = sb.unit(stop - start)
    # "out": along the flange, away from it at this end (a mitred end's face is slanted;
    # the flange still runs square to the picked edge)
    out = n_wall.cross(direction)
    if out.Length < 1e-9:
        raise sb.SheetMetalError("Pick an edge running across the flange's end.")
    out = sb.unit(out)
    if out.dot(n_end) < 0:
        out = out * -1.0
    return {
        "edge": edge,
        "start": start,
        "end": stop,
        "dir": direction,
        "length": (stop - start).Length,
        "top": wall,
        "normal": n_wall,
        "side": end,
        "out": out,
    }


def _corner_point(fd, fs, thickness):
    """Where the two flanges' middle planes meet, near the picked edges (3D), and the corner
    line's direction."""
    line = fd["normal"].cross(fs["normal"])
    if line.Length < 1e-6:
        raise sb.SheetMetalError("The two flanges are parallel: there is no corner to close.")
    dl = sb.unit(line)
    md = fd["start"] - fd["normal"] * (thickness / 2.0)
    ms = fs["start"] - fs["normal"] * (thickness / 2.0)
    e1 = fd["out"]
    e2 = dl.cross(e1)
    pd = (0.0, 0.0)
    ud = (1.0, 0.0)
    rel = ms - md
    ps = (rel.dot(e1), rel.dot(e2))
    us = (fs["out"].dot(e1), fs["out"].dot(e2))
    meet = core.line_intersection(pd, ud, ps, us)
    if meet is None:
        raise sb.SheetMetalError("The two flanges are parallel: there is no corner to close.")
    s, t = meet
    if s < -1e-6 or t < -1e-6:
        raise sb.SheetMetalError(
            "Pick the edges at the corner, on the ends of the two flanges that face each other."
        )
    return md + e1 * s, dl


def _end_prism(face, way, big, along_flange=True):
    """The flange's end face swept `big` along `way`. A slanted (mitred) end is swept from its
    outline seen along `way`, starting behind it inside the flange: its bend's end is then an
    arc swept along the bend's axis, a true cylinder (an elliptic arc swept would not lay
    flat). Other ends, and ends taken square to the other flange, are swept as they are."""
    import Part

    if not along_flange or abs(abs(sb.plane_normal(face).dot(way)) - 1.0) < 1e-6:
        return face.extrude(way * big)
    lo = None
    for edge in face.Edges:
        for k in range(9):
            t = edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) * k / 8.0
            d = edge.valueAt(t).dot(way)
            lo = d if lo is None else min(lo, d)

    def flat(p):
        return p - way * (p.dot(way) - lo)

    edges = []
    try:
        for edge in face.OuterWire.OrderedEdges:
            a, b = flat(edge.Vertexes[0].Point), flat(edge.Vertexes[-1].Point)
            if (b - a).Length < 1e-7:
                continue
            if isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
                edges.append(Part.LineSegment(a, b).toShape())
                continue
            m = flat(edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter)))
            if ((m - a).cross(b - a)).Length < 1e-9:
                edges.append(Part.LineSegment(a, b).toShape())
            else:
                edges.append(Part.Arc(a, m, b).toShape())
        section = Part.Face(Part.Wire(Part.__sortEdges__(edges)))
        if not section.isValid() or section.Area < 1e-9:
            raise ValueError("no section")
    except Exception:
        return face.extrude(way * big)
    return section.extrude(way * big)


def closure_shape(
    shape, dominant, submissive, options, thickness, miter_gap, k_factor=0.44, relief_size=None
):
    """The body's solid with the corner closed (and its relief cut). Raises
    sb.SheetMetalError."""
    relief = options.get("relief", "trim_to_bend")
    if relief not in BUILT_RELIEFS:
        raise sb.SheetMetalError(
            "%s corner relief is not available yet in SciForge; use Trim To Bend or Tear."
            % core.CLOSURE_RELIEF_LABELS.get(relief, relief)
        )
    if dominant == submissive:
        raise sb.SheetMetalError("Pick two different edges, one on each flange.")
    fd = end_frame(shape, dominant, thickness)
    fs = end_frame(shape, submissive, thickness)
    if fd["side"].isSame(fs["side"]):
        raise sb.SheetMetalError("Both edges are on the same flange end; pick one on each flange.")
    gap = options.get("gap")
    gap = miter_gap if gap is None else float(gap)
    alignment = options.get("alignment", "symmetric")
    if options.get("flip_overlap") and alignment == "overlap":
        fd, fs = fs, fd
    corner, _dl = _corner_point(fd, fs, thickness)
    aligned = bool(options.get("extend_aligned", True))
    # the way each end is taken: in line with its flange (Extend Aligned), or square to the
    # other flange (straight toward it, across its face)
    way = {}
    for fr, other in ((fd, fs), (fs, fd)):
        if aligned:
            way[id(fr)] = fr["out"]
        else:
            toward = other["normal"] * (1.0 if other["normal"].dot(fr["out"]) > 0 else -1.0)
            way[id(fr)] = toward
    big = shape.BoundBox.DiagonalLength * 2.0 + 10.0
    pieces = []
    if alignment == "symmetric":
        reach = core.closure_reach("symmetric", gap, thickness)
        m = sb.unit(fs["out"] - fd["out"])
        for fr, sign in ((fd, 1.0), (fs, -1.0)):
            prism = _end_prism(fr["side"], way[id(fr)], big, aligned)
            normal = m * sign
            ydir = fr["normal"].cross(normal)
            if ydir.Length < 1e-9:
                ydir = normal.cross(fr["out"])
            keep = sb.frame_box(
                corner + normal * reach,
                normal,
                sb.unit(ydir),
                sb.unit(normal.cross(sb.unit(ydir))),
                0.0,
                big,
                -big,
                big,
                -big,
                big,
            )
            pieces.append(prism.common(keep))
    elif alignment == "overlap":
        overlap = float(options.get("overlap", 1.0))
        # the dominant runs to the other's outside face (less (1 - overlap) T), the
        # submissive stops the gap short of the dominant's inside face: planes across each
        # flange's way, measured along its "out"
        far = max(
            fs["start"].dot(fd["out"]), (fs["start"] - fs["normal"] * thickness).dot(fd["out"])
        ) - core.closure_reach("overlap", gap, thickness, overlap, True)
        near = (
            min(
                fd["start"].dot(fs["out"]),
                (fd["start"] - fd["normal"] * thickness).dot(fs["out"]),
            )
            - gap
        )
        for fr, limit in ((fd, far), (fs, near)):
            prism = _end_prism(fr["side"], way[id(fr)], big, aligned)
            ydir = sb.unit(fr["normal"]) if abs(fr["normal"].dot(fr["out"])) < 0.99 else None
            if ydir is None:
                continue
            zdir = fr["out"].cross(ydir)
            origin = fr["out"] * limit
            keep = sb.frame_box(
                origin, fr["out"], ydir, sb.unit(zdir), -big, 0.0, -big, big, -big, big
            )
            pieces.append(prism.common(keep))
    else:
        raise sb.SheetMetalError("Alignment must be Symmetric Gap or Overlap.")
    pieces = [p for p in pieces if not p.isNull() and p.Volume > 1e-9]
    if not pieces and relief not in ("trim_to_bend",) + CUT_RELIEFS:
        # a corner already closed to this gap (two flanges mitred by Flange) can still get
        # its relief: only a Tear there changes nothing
        raise sb.SheetMetalError("The corner is already closed this far; nothing to add.")
    size = relief_size if relief_size is not None else options.get("relief_size")
    size = float(size or 4 * thickness)
    if relief in CUT_RELIEFS and alignment == "overlap":
        raise sb.SheetMetalError(
            "An overlapped corner lies over itself when laid flat, so a Round or Square relief "
            "cannot be cut there: use Trim To Bend or Tear, or Symmetric Gap."
        )
    merged = sb.fuse_all(shape, pieces)
    closed = sb.one_solid(merged, "This corner closure")
    if relief == "trim_to_bend":
        closed = trim_to_bend(closed, fd, fs, corner, thickness)
    if relief in CUT_RELIEFS and alignment != "overlap":
        try:
            closed = corner_relief(
                closed,
                corner,
                _dl,
                relief,
                size,
                thickness,
                k_factor,
                options.get("placement") or "intersection",
            )
        except sb.SheetMetalError:
            raise
        except Exception as exc:  # an OpenCASCADE failure: say so, with what to try
            raise sb.SheetMetalError(
                "The corner relief could not be cut here (%s): try another Relief Placement "
                "or a different Relief Size." % exc
            )
    return closed


def _bend_wedge(shape, frame, corner, thickness):
    """The zone of the flange's bend nearest the corner, as a solid: the sector between the
    bend's start and end planes (both through its axis), out to three times the bend's outer
    radius and as far along the axis either side of the corner."""
    import Part

    best = None
    for face in shape.Faces:
        surf = face.Surface
        if not isinstance(surf, Part.Cylinder):
            continue
        axis = sb.unit(surf.Axis)
        if abs(abs(axis.dot(frame["out"])) - 1.0) > 1e-6:
            continue
        rel = corner - surf.Center
        dist = (rel - axis * rel.dot(axis)).Length
        if best is None or dist < best[0]:
            best = (dist, face)
    if best is None:
        raise sb.SheetMetalError(
            "No bend was found at the end of a flange at this corner: nothing to trim to."
        )
    face = best[1]
    surf = face.Surface
    axis = sb.unit(surf.Axis)
    u0, u1, v0, _v1 = face.ParameterRange
    reach = 3.0 * (surf.Radius + thickness)
    foot = surf.Center + axis * (corner - surf.Center).dot(axis) - axis * reach
    rays = []
    for u in (u0, 0.5 * (u0 + u1), u1):
        rel = surf.value(u, v0) - surf.Center
        rays.append(sb.unit(rel - axis * rel.dot(axis)))
    points = [foot] + [foot + ray * reach for ray in rays]
    sector = Part.Face(Part.makePolygon(points + points[:1]))
    return sector.extrude(axis * (2.0 * reach))


def trim_to_bend(solid, fd, fs, corner, thickness):
    """Trim To Bend: cut away whatever lies inside both flanges' bend zones at the corner, so
    each bend stops where the other one starts (in the flat state: the patch between both
    bends' start and end lines)."""
    try:
        tool = _bend_wedge(solid, fd, corner, thickness).common(
            _bend_wedge(solid, fs, corner, thickness)
        )
        if tool.isNull() or tool.Volume < 1e-9:
            return solid
        out = solid.cut(tool)
        try:
            out = out.removeSplitter()
        except Exception:
            pass
    except sb.SheetMetalError:
        raise
    except Exception as exc:  # an OpenCASCADE failure: say so
        raise sb.SheetMetalError("The corner could not be trimmed to the bends here (%s)." % exc)
    return sb.one_solid(out, "Trimming this corner to the bends")


def _bend_2d(bend, origin, e1, e2):
    """A bend laid flat by the unfolder as relief_centre wants it, in the 2D frame (origin,
    e1, e2) of the stationary face: a point on its centre line, the line's direction, the unit
    vector from its start (stationary side) toward its end, half its width."""
    a, b = bend.centre
    s0 = bend.start[0]
    s1 = bend.end[0]
    direction = sb.unit(b - a)
    across = (s1 - s0) - direction * (s1 - s0).dot(direction)
    half = across.Length / 2.0
    outward = sb.unit(across) if across.Length > 1e-9 else e2

    def flat(v, point=True):
        if point:
            v = v - origin
        return (v.dot(e1), v.dot(e2))

    return (flat(a), flat(direction, False), flat(outward, False), half)


def _flat_bases(solid, line_dir, thickness):
    """The flat faces of the sheet square to the corner line (the sheet both flanges are
    bent from), largest first: [(name, face)]."""
    found = []
    for i, face in enumerate(solid.Faces, start=1):
        if not sb.is_plane(face) or abs(abs(sb.plane_normal(face).dot(line_dir)) - 1) > 1e-6:
            continue
        if not sb.face_thickness(solid, face, thickness):
            continue
        found.append(("Face%d" % i, face))
    found.sort(key=lambda item: -item[1].Area)
    return found


def _lays_flat(solid, line_dir, thickness, k_factor):
    """None when the unfolder lays the solid flat from one of its two largest sheet faces
    (top or bottom), else the reason."""
    from . import sheetmetal_unfold as uf

    reason = "no flat sheet left"
    for name, _face in _flat_bases(solid, line_dir, thickness)[:2]:
        try:
            uf.unfold(solid, name, k_factor)
            return None
        except Exception as exc:
            reason = str(exc)
    return reason


def corner_relief(
    solid, corner, line_dir, shape_kind, size, thickness, k_factor, placement="intersection"
):
    """Cut a 2-bend corner relief where the two bends meet: the part is laid flat (sm-flat's
    unfolder), a circle of diameter `size` (Round) or a square of side `size` (Square) is cut
    at the Relief Placement (Intersection: where the two bends' centre lines cross; Vertex:
    where both bends start on the flat side; Tangent: a Round touching the far side of both
    bend zones; core.relief_centre), and the cut is folded back onto the bends and walls (the
    unfolder's refold). Raises SheetMetalError."""
    import Part

    from . import sheetmetal_unfold as uf

    if size <= 0:
        raise sb.SheetMetalError("The relief size must be more than 0.")
    if placement == "tangent" and shape_kind == "square":
        raise sb.SheetMetalError(
            "Tangent placement is for a Round relief only; use Intersection or Vertex."
        )
    bases = _flat_bases(solid, line_dir, thickness)
    base = bases[0] if bases else None
    if base is None:
        raise sb.SheetMetalError("No flat sheet joins the two flanges' bends: no relief to cut.")
    try:
        result = uf.unfold(solid, base[0], k_factor)
    except uf.UnfoldError as exc:
        raise sb.SheetMetalError("The corner relief needs the part laid flat: %s" % exc)
    normal = sb.plane_normal(base[1])
    plane_point = base[1].Vertexes[0].Point
    target = corner - normal * (corner - plane_point).dot(normal)
    best = None
    bends = [bend for bend in result.bends if (bend.centre[1] - bend.centre[0]).Length > 1e-9]
    for i in range(len(bends)):
        for j in range(i + 1, len(bends)):
            pa, pb = bends[i].centre[0], bends[j].centre[0]
            da = sb.unit(bends[i].centre[1] - pa)
            db = sb.unit(bends[j].centre[1] - pb)
            if abs(da.dot(db)) > 1.0 - 1e-6:
                continue
            e1 = da
            e2 = normal.cross(e1)
            meet = core.line_intersection(
                (0.0, 0.0),
                (1.0, 0.0),
                ((pb - pa).dot(e1), (pb - pa).dot(e2)),
                (db.dot(e1), db.dot(e2)),
            )
            if meet is None:
                continue
            point = pa + da * meet[0]
            gap = (point - target).Length
            if best is None or gap < best[0]:
                best = (gap, point, da, bends[i], bends[j])
    if best is None or best[0] > 4.0 * (thickness + max(b.inner_radius for b in result.bends)):
        raise sb.SheetMetalError("The two flanges' bends do not meet at this corner.")
    _gap, crossing, da, bend_a, bend_b = best
    e2 = normal.cross(da)
    flat_a = _bend_2d(bend_a, crossing, da, e2)
    flat_b = _bend_2d(bend_b, crossing, da, e2)
    reach = thickness * 4.0
    try:
        x, y = core.relief_centre(placement, flat_a, flat_b, size, shape_kind)
    except ValueError as exc:
        raise sb.SheetMetalError(str(exc))
    if shape_kind == "round":
        centre = crossing + da * x + e2 * y
        tool = Part.makeCylinder(size / 2.0, 2 * reach, centre - normal * reach, normal)
    else:
        centre = crossing + da * x + e2 * y
        corner_pt = centre - da * (size / 2.0) - e2 * (size / 2.0) - normal * reach
        tool = sb.frame_box(corner_pt, da, e2, normal, 0, size, 0, size, 0, 2 * reach)
    flat_after = result.shape.cut(tool)
    if abs(flat_after.Volume - result.shape.Volume) < 1e-9:
        return solid
    try:
        out = uf.refold(solid, result, flat_after)
    except uf.UnfoldError as exc:
        raise sb.SheetMetalError("The corner relief could not be folded back: %s" % exc)
    except Exception as exc:  # an OpenCASCADE failure while folding the cut back
        raise sb.SheetMetalError(
            "The corner relief could not be folded back here (%s): try another Relief "
            "Placement or a different Relief Size." % exc
        )
    # folding the cut back at a mitred corner can leave specks of material (far below a
    # thousandth of the sheet's thickness cubed) beside the mitre: drop them
    solids = list(out.Solids)
    kept = [s for s in solids if s.Volume > 1e-3 * thickness**3]
    if len(solids) > 1 and len(kept) == 1:
        log("corner relief: %d specks left by the refold dropped" % (len(solids) - 1))
        out = kept[0]
    elif len(kept) > 1:
        raise sb.SheetMetalError(
            "This corner relief would split the body into %d pieces here: try another Relief "
            "Placement or a smaller Relief Size." % len(kept)
        )
    cut = sb.one_solid(out, "This corner relief")
    if cut.Volume > solid.Volume + 1e-6:
        # the boolean failed on touching geometry and the cut came back as added
        # material: refuse rather than build it
        raise sb.SheetMetalError(
            "The corner relief could not be cut cleanly at this placement: try another "
            "Relief Placement or Relief Size."
        )
    # the corner must still lay flat (flat walls and round bends only)
    reason = _lays_flat(cut, line_dir, thickness, k_factor)
    if reason:
        raise sb.SheetMetalError(
            "With this relief the corner could not be laid flat any more (%s): try another "
            "Relief Placement or Relief Size." % reason
        )
    return cut


class CornerClosureFeature:
    """Saved in files as "sciforge.sheetmetal_corner.CornerClosureFeature": keep the name."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Corner Closure", doc)
                return True
            return False

        add("App::PropertyLinkSub", "DominantEdge", "Edge of the dominant flange's end")
        add("App::PropertyLinkSub", "SubmissiveEdge", "Edge of the submissive flange's end")
        if add("App::PropertyEnumeration", "Alignment", "Symmetric Gap or Overlap"):
            obj.Alignment = ALIGNMENTS
            obj.Alignment = ALIGNMENTS[0]
        if add("App::PropertyBool", "UseRuleGap", "Gap from the rule's miter gap"):
            obj.UseRuleGap = True
        add("App::PropertyLength", "Gap", "Corner gap when not the rule's")
        if add("App::PropertyFloat", "Overlap", "0 = no overlap, 1 = full thickness"):
            obj.Overlap = 1.0
        add("App::PropertyBool", "FlipOverlap", "The other flange runs over")
        if add("App::PropertyBool", "ExtendAligned", "Extend in line with the flanges"):
            obj.ExtendAligned = True
        if add("App::PropertyEnumeration", "Relief", "Corner relief shape"):
            obj.Relief = RELIEFS
            obj.Relief = core.CLOSURE_RELIEF_LABELS["trim_to_bend"]
        elif list(obj.getEnumerationsOfProperty("Relief") or []) != RELIEFS:
            # a step saved before Tear was added: offer today's list, keep its choice
            current = str(obj.Relief)
            obj.Relief = RELIEFS
            obj.Relief = current if current in RELIEFS else RELIEFS[-1]
        if add("App::PropertyBool", "UseRuleRelief", "Relief size from the rule"):
            obj.UseRuleRelief = True
        if add("App::PropertyLength", "ReliefSize", "Round: diameter, Square: side"):
            obj.ReliefSize = 4.0
        if add("App::PropertyEnumeration", "ReliefPlacement", "Where the relief is centred"):
            obj.ReliefPlacement = PLACEMENTS
            obj.ReliefPlacement = PLACEMENTS[0]
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane"):
            obj.Refine = True
        bodies.mark(obj, KIND)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

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


def _key(label, table):
    for key, text in table.items():
        if text == label:
            return key
    return label.lower()


def options_of(obj):
    return {
        "alignment": _key(str(obj.Alignment), core.CLOSURE_LABELS),
        "gap": None if obj.UseRuleGap else float(obj.Gap),
        "overlap": float(obj.Overlap),
        "flip_overlap": bool(obj.FlipOverlap),
        "extend_aligned": bool(obj.ExtendAligned),
        "relief": _key(str(obj.Relief), core.CLOSURE_RELIEF_LABELS),
        "relief_size": None if obj.UseRuleRelief else float(obj.ReliefSize),
        "placement": _key(str(obj.ReliefPlacement), core.CLOSURE_PLACEMENT_LABELS),
    }


def build(obj):
    base = obj.BaseFeature
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise sb.SheetMetalError("There is no sheet before this step.")
    body = bodies.body_of(obj)
    thickness, _r, k_factor, rule = sb.rule_values(body)
    d, s = obj.DominantEdge, obj.SubmissiveEdge
    if not d or not d[1] or not s or not s[1]:
        raise sb.SheetMetalError("Pick the Dominant Edge and the Submissive Edge.")
    shape = base.Shape.copy()
    shape.Placement = App.Placement()
    opts = options_of(obj)
    size = opts.get("relief_size")
    if size is None:
        size = float(rule["corner_relief_2bend_size"])
    result = closure_shape(
        shape,
        d[1][0],
        s[1][0],
        opts,
        thickness,
        float(rule["miter_gap"]),
        k_factor=k_factor,
        relief_size=size,
    )
    if obj.Refine:
        try:
            result = result.removeSplitter()
        except Exception:
            pass
    return result


def apply(obj, base, dominant, submissive, options):
    obj.DominantEdge = (base, [dominant])
    obj.SubmissiveEdge = (base, [submissive])
    obj.Alignment = core.CLOSURE_LABELS[options.get("alignment", "symmetric")]
    gap = options.get("gap")
    obj.UseRuleGap = gap is None
    if gap is not None:
        obj.Gap = float(gap)
    obj.Overlap = float(options.get("overlap", 1.0))
    obj.FlipOverlap = bool(options.get("flip_overlap", False))
    obj.ExtendAligned = bool(options.get("extend_aligned", True))
    obj.Relief = core.CLOSURE_RELIEF_LABELS[options.get("relief", "trim_to_bend")]
    size = options.get("relief_size")
    obj.UseRuleRelief = size is None
    if size is not None:
        obj.ReliefSize = float(size)
    obj.ReliefPlacement = core.CLOSURE_PLACEMENT_LABELS[options.get("placement") or "intersection"]


def make(body, base, dominant, submissive, options=None, name="CornerClosure"):
    opts = default_options()
    opts.update(options or {})
    obj = bodies.insert_after_tip(body, TYPE, name)
    CornerClosureFeature(obj)
    obj.BaseFeature = base
    apply(obj, base, dominant, submissive, opts)
    _view(obj)
    log("corner closure %s made" % obj.Name)
    return obj


def read(obj):
    d, s = obj.DominantEdge, obj.SubmissiveEdge
    return (
        obj.BaseFeature,
        d[1][0] if d and d[1] else "",
        s[1][0] if s and s[1] else "",
        options_of(obj),
    )


def _view(obj):
    if not App.GuiUp:
        return
    try:
        from . import sheetmetal_corner_ui

        sheetmetal_corner_ui.ViewProviderCornerClosure(obj.ViewObject)
    except Exception:
        pass
