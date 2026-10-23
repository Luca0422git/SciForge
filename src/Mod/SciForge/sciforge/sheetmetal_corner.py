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

Relief: Trim To Bend (the bends end where they are and the corner stays open under the
closed walls). Round and Square corner reliefs need the bends cut in the flat state, which
SciForge cannot map onto the folded corner yet: refused in the dialog with the reason
(docs/sciforge/parity/sheet-metal-more.md, Known gaps).
Sources: docs/sciforge/dev/research/fusion-sheet-metal.md 2.9 (geometry G).
"""

import FreeCAD as App

from . import bodies, log, sheetmetal_bend as sb, sheetmetal_bend_core as core

V = App.Vector
TYPE = "PartDesign::FeaturePython"
KIND = "SheetMetalCornerClosure"
ALIGNMENTS = [core.CLOSURE_LABELS[k] for k in core.CLOSURE_ALIGNMENTS]
RELIEFS = [core.CLOSURE_RELIEF_LABELS[k] for k in core.CLOSURE_RELIEFS]
BUILT_RELIEFS = ("trim_to_bend", "round", "square")


def default_options():
    return {
        "alignment": "symmetric",
        "gap": None,  # None: the rule's miter gap
        "overlap": 1.0,
        "flip_overlap": False,
        "extend_aligned": True,
        "relief": "trim_to_bend",
        "relief_size": None,  # None: the rule's 2-bend corner relief size
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
    if abs(sb.plane_normal(wall).dot(sb.plane_normal(end))) > 1e-4:
        raise sb.SheetMetalError("The flange's end must be square to the flange.")
    start, stop = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    return {
        "edge": edge,
        "start": start,
        "end": stop,
        "dir": sb.unit(stop - start),
        "length": (stop - start).Length,
        "top": wall,
        "normal": sb.plane_normal(wall),
        "side": end,
        "out": sb.plane_normal(end),
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


def closure_shape(
    shape, dominant, submissive, options, thickness, miter_gap, k_factor=0.44, relief_size=None
):
    """The body's solid with the corner closed (and its relief cut). Raises
    sb.SheetMetalError."""
    relief = options.get("relief", "trim_to_bend")
    if relief not in BUILT_RELIEFS:
        raise sb.SheetMetalError(
            "%s corner relief is not available yet in SciForge; use Trim To Bend."
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
            prism = fr["side"].extrude(way[id(fr)] * big)
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
        end_d = fd["side"].CenterOfMass
        planes = [
            (fs["start"] - end_d).dot(fd["out"]),
            (fs["start"] - fs["normal"] * thickness - end_d).dot(fd["out"]),
        ]
        far = max(planes) - core.closure_reach("overlap", gap, thickness, overlap, True)
        end_s = fs["side"].CenterOfMass
        planes = [
            (fd["start"] - end_s).dot(fs["out"]),
            (fd["start"] - fd["normal"] * thickness - end_s).dot(fs["out"]),
        ]
        near = min(planes) - gap
        if far > 1e-6:
            step = way[id(fd)]
            pieces.append(fd["side"].extrude(step * (far / max(step.dot(fd["out"]), 1e-6))))
        if near > 1e-6:
            step = way[id(fs)]
            pieces.append(fs["side"].extrude(step * (near / max(step.dot(fs["out"]), 1e-6))))
    else:
        raise sb.SheetMetalError("Alignment must be Symmetric Gap or Overlap.")
    pieces = [p for p in pieces if not p.isNull() and p.Volume > 1e-9]
    if not pieces:
        raise sb.SheetMetalError("The corner is already closed this far; nothing to add.")
    size = relief_size if relief_size is not None else options.get("relief_size")
    size = float(size or 4 * thickness)
    if relief in ("round", "square") and alignment == "overlap":
        raise sb.SheetMetalError(
            "An overlapped corner lies over itself when laid flat, so a Round or Square relief "
            "cannot be cut there: use Trim To Bend, or Symmetric Gap."
        )
    merged = sb.fuse_all(shape, pieces)
    closed = sb.one_solid(merged, "This corner closure")
    if relief in ("round", "square") and alignment != "overlap":
        closed = corner_relief(closed, corner, _dl, relief, size, thickness, k_factor)
    return closed


def corner_relief(solid, corner, line_dir, shape_kind, size, thickness, k_factor):
    """Cut a 2-bend corner relief where the two bends meet: the part is laid flat (sm-flat's
    unfolder), a circle of diameter `size` (Round) or a square of side `size` (Square) is cut
    centred where the two bends' centre lines cross (Placement Intersection), and the cut is
    folded back onto the bends and walls (the unfolder's refold). Raises SheetMetalError."""
    import Part

    from . import sheetmetal_unfold as uf

    if size <= 0:
        raise sb.SheetMetalError("The relief size must be more than 0.")
    base = None
    for i, face in enumerate(solid.Faces, start=1):
        if not sb.is_plane(face) or abs(abs(sb.plane_normal(face).dot(line_dir)) - 1) > 1e-6:
            continue
        if not sb.face_thickness(solid, face, thickness):
            continue
        if base is None or face.Area > base[1].Area:
            base = ("Face%d" % i, face)
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
    lines = []
    for bend in result.bends:
        a, b = bend.centre
        if (b - a).Length > 1e-9:
            lines.append((a, sb.unit(b - a)))
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            (pa, da), (pb, db) = lines[i], lines[j]
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
                best = (gap, point, da, db)
    if best is None or best[0] > 4.0 * (thickness + max(b.inner_radius for b in result.bends)):
        raise sb.SheetMetalError("The two flanges' bends do not meet at this corner.")
    _gap, centre, da, db = best
    reach = thickness * 4.0
    if shape_kind == "round":
        tool = Part.makeCylinder(size / 2.0, 2 * reach, centre - normal * reach, normal)
    else:
        e2 = normal.cross(da)
        corner_pt = centre - da * (size / 2.0) - e2 * (size / 2.0) - normal * reach
        tool = sb.frame_box(corner_pt, da, e2, normal, 0, size, 0, size, 0, 2 * reach)
    flat_after = result.shape.cut(tool)
    if abs(flat_after.Volume - result.shape.Volume) < 1e-9:
        return solid
    try:
        out = uf.refold(solid, result, flat_after)
    except uf.UnfoldError as exc:
        raise sb.SheetMetalError("The corner relief could not be folded back: %s" % exc)
    return sb.one_solid(out, "This corner relief")


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
        if add("App::PropertyBool", "UseRuleRelief", "Relief size from the rule"):
            obj.UseRuleRelief = True
        if add("App::PropertyLength", "ReliefSize", "Round: diameter, Square: side"):
            obj.ReliefSize = 4.0
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
