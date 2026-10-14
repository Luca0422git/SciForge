# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's own Fillet / Chamfer step, for what FreeCAD's PartDesign::Fillet / Chamfer cannot
hold (one constant size for every edge): several selection sets with their own size (Fusion's
"+" rows), Chord Length and Variable radius, Tangent Chain off, Rule Fillet, Full Round
Fillet, and chamfer sets. No Qt: the dialog (fillet_ui.py) and the golden-model builder use it.

A plain fillet / chamfer (one row, one constant size, Tangent Chain on) stays FreeCAD's
feature (blend.py), so Press Pull and the parameters table keep editing it; the dialog
swaps the step for this one the moment an option needs it.

The step: a PartDesign::FeaturePython with SciForgeType "FilletSets" / "ChamferSets":
  Picks          the picked edges / faces of every row, in row order (one link, so FreeCAD
                 and picks.py keep them through edits). Rule Fillet: the faces of the first
                 box; Full Round: side face, centre face, side face of each row
  Picks2         Rule Fillet, Between Faces/Features: the faces of the second box
  RuleFeatures, RuleFeatures2   Rule Fillet: whole steps picked in the two boxes
  SciForgeBlend  the settings (fillet_core: rows, types, rule, corner...), JSON
  Size<i>        row i's radius / chord length / distance (a parameter can drive it)
  SizeB<i>, Angle<i>   chamfer row i's second distance / angle
  Refine         merge faces that end up in one plane

How it is built (OpenCASCADE through FreeCAD's Python API):
  * one BRepFilletAPI_MakeFillet run with a radius per edge: FreeCAD's Python makeFillet
    takes one radius for all edges, so a radius per edge goes through a Part::Fillet in a
    throw-away hidden document (kernel()); likewise Part::Chamfer for chamfer rows;
  * Chord Length: the radius that gives that chord at each end of each edge;
  * Variable: the edge (with its tangent chain) is cut at the radius points by a vertex
    (generalFuse), each piece gets its two end radii, and OpenCASCADE runs one smooth
    law through them;
  * Tangent Chain off: OpenCASCADE always rounds the whole tangent chain. The material it
    removes along the chain edges that were not picked is put back (cut at the corner where
    the picked edge meets them);
  * Full Round: the slab under the centre face, minus a cylinder of half the width between
    the side faces, is cut away;
  * Rule Fillet: the edges are found again from the faces / steps at every compute, so an
    edit that adds edges to them gets those rounded too (Fusion's "rule").
"""

import contextlib
import math

import FreeCAD as App

from . import blend, bodies, fillet_core as core

TYPE = "PartDesign::FeaturePython"
SCIFORGE_TYPES = {"fillet": "FilletSets", "chamfer": "ChamferSets"}
KIND_BY_TYPE = {v: k for k, v in SCIFORGE_TYPES.items()}
SPEC = "SciForgeBlend"
TOL = 1e-6


def kind_of(obj):
    """ "fillet" / "chamfer" for a SciForge fillet step, else None."""
    return KIND_BY_TYPE.get(bodies.kind(obj))


def is_sets(obj):
    return kind_of(obj) is not None


def _error(exc):
    return blend.BlendError(str(exc))


class KernelError(blend.BlendError):
    """OpenCASCADE could not build the blend (its own words; compute() says which set)."""


# -- the kernel ----------------------------------------------------------------------------
@contextlib.contextmanager
def _scratch(type_id):
    """A Part::Fillet / Part::Chamfer in a hidden throw-away document (FreeCAD's only Python
    route to a size per edge). The document is closed again at once; the design that was
    active stays active."""
    active = App.ActiveDocument.Name if App.ActiveDocument is not None else None
    doc = App.newDocument("SciForgeKernel", "kernel", True, True)
    try:
        # No undo here: a dialog's undo step is the application's active transaction, and a
        # document that joined it and was closed ended it (the dialog's step was committed
        # half-way, its Cancel / Ctrl+Z then left a "Delete" step behind)
        doc.UndoMode = 0
        # Element names in plain text (not as references into this document's string table,
        # which goes away with it): renamed() makes them the part's own (see there)
        doc.UseHasher = False
        base = doc.addObject("Part::Feature", "Base")
        feature = doc.addObject(type_id, "Blend")
        feature.Base = base
        yield base, feature
    finally:
        try:
            App.closeDocument(doc.Name)
        except Exception:
            pass
        if (
            active
            and active in App.listDocuments()
            and (App.ActiveDocument is None or App.ActiveDocument.Name != active)
        ):
            try:
                App.setActiveDocument(active)
            except Exception:
                pass


def renamed(shape, scratch_tag, tag):
    """The throw-away document's result with element names of the part's own: they are
    built from the input's names plus the tag of the throw-away input object (a number that
    changes at every compute, so a step after this one would lose its edge every time).
    That tag is replaced by `tag`, the input shape's own, as FreeCAD's makeFillet names a
    result: stable, and FreeCAD still follows the history of every element."""
    import re

    out = shape.copy()
    try:
        names = dict(shape.ElementMap)
        if tag and names:
            pattern = re.compile(re.escape(":H%x" % scratch_tag) + r"(?=[,:;]|$)")
            mapping = {pattern.sub(":H%x" % tag, k): v for k, v in names.items()}
            out.ElementMap = {}
            out.ElementMap = mapping
        else:
            out.ElementMap = {}  # no names rather than names that change every time
        out.Tag = 0
    except Exception:
        pass
    return out


def kernel(kind, shape, items, tag=None):
    """`shape` blended along each (edge index, size 1, size 2) of `items` in one OpenCASCADE
    run. Fillet: radius 1 at the edge's first vertex, radius 2 at its last (a straight law in
    between, smoothed through every edge). Chamfer: distance 1 on the edge's first face,
    distance 2 on the other. Raises blend.BlendError."""
    if not items:
        raise blend.BlendError("Select the edges to %s." % ("round" if kind == "fillet" else kind))
    sizes = {(round(a, 12), round(b, 12)) for _i, a, b in items}
    edges = [shape.Edges[i - 1] for i, _a, _b in items]
    try:
        if len(sizes) == 1:
            a, b = items[0][1], items[0][2]
            if kind == "fillet":
                result = (
                    shape.makeFillet(a, b, edges)
                    if abs(a - b) > 1e-12
                    else (shape.makeFillet(a, edges))
                )
            else:
                result = (
                    shape.makeChamfer(a, b, edges)
                    if abs(a - b) > 1e-12
                    else (shape.makeChamfer(a, edges))
                )
        else:
            type_id = "Part::Fillet" if kind == "fillet" else "Part::Chamfer"
            with blend.quiet(), _scratch(type_id) as (base, feature):
                base.Shape = shape
                feature.Edges = [(int(i), float(a), float(b)) for i, a, b in items]
                feature.recompute()
                state = list(feature.State)
                if "Invalid" in state or "Error" in state or feature.Shape.isNull():
                    raise KernelError(feature.getStatusString() or "command not done")
                import Part

                result = renamed(Part.Shape(feature.Shape), base.ID, tag or shape.Tag)
    except blend.BlendError as exc:
        raise KernelError(str(exc))
    except Exception as exc:
        raise KernelError(str(exc) or "command not done")
    if result is None or result.isNull() or not result.Solids:
        raise KernelError("command not done")
    return result


# -- edges and their faces ------------------------------------------------------------------
def _index(name):
    """1 for "Edge1" / "Face1"."""
    return int(name[4:])


def turn_at(info, name, parameter):
    """The angle (radians) the normals of an edge's two faces turn by at `parameter` of the
    edge (90 degrees on a box edge), and the corner's material angle (gamma), or None."""
    edge = blend.element(info.shape, name)
    faces = info.faces_of(name)
    if edge is None or len(faces) != 2:
        return None
    point = edge.valueAt(parameter)
    normals = []
    for face in faces:
        try:
            u, v = face.Surface.parameter(point)
            normal = face.normalAt(u, v)
        except Exception:
            return None
        if normal.Length < TOL:
            return None
        normal.normalize()
        normals.append(normal)
    turn = normals[0].getAngle(normals[1])
    return turn, math.pi - turn


def ordered_chain(info, name):
    """The tangent chain of edge `name` in order from one end to the other, as
    [(edge name, reversed)], starting at the end on the side of the picked edge's first
    vertex (Fusion's position 0 is the start of the picked edge). Raises SetError for a
    chain that closes on itself (it has no start and end)."""
    chain = info.chain(name)
    shape = info.shape
    edges = {n: blend.element(shape, n) for n in chain}

    def ends(n):
        e = edges[n]
        return e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)

    def touches(n, point):
        return [m for m in chain if m != n and any((p - point).Length < 1e-6 for p in ends(m))]

    start = None
    closed = any((ends(n)[0] - ends(n)[1]).Length < 1e-6 for n in chain)  # a circle
    for n in [] if closed else chain:
        for point in ends(n):
            if not touches(n, point):
                start = (n, point)
                break
        if start:
            break
    if start is None:
        raise core.SetError(
            "This edge runs all the way round (a closed tangent chain): a Variable radius "
            "needs an edge with a start and an end. Use Constant or Chord Length here."
        )
    order, seen = [], set()
    current, at = start
    while current is not None and current not in seen:
        seen.add(current)
        first, last = ends(current)
        reversed_ = (first - at).Length > (last - at).Length
        order.append((current, reversed_))
        at = first if reversed_ else last
        nxt = [m for m in touches(current, at) if m not in seen]
        current = nxt[0] if nxt else None
    if any(n == name and rev for n, rev in order):
        order = [(n, not rev) for n, rev in reversed(order)]
    return order


def split_at(shape, points):
    """`shape` with a vertex put into its edges at `points` (no face changes)."""
    import Part

    if not points:
        return shape
    pieces = shape.generalFuse([Part.Vertex(p) for p in points])[0]
    solids = pieces.Solids
    if not solids:
        raise blend.BlendError("The edge could not be cut at the radius points.")
    return solids[0] if len(solids) == 1 else Part.makeCompound(solids)


def _edge_on(shape, start, end, middle):
    """Index of the edge of `shape` running between `start` and `end` through `middle`,
    and True if it runs the other way; (None, False) if there is none."""
    import Part

    probe = Part.Vertex(middle)
    for i, edge in enumerate(shape.Edges, start=1):
        a = edge.valueAt(edge.FirstParameter)
        b = edge.valueAt(edge.LastParameter)
        if (a - start).Length < 1e-5 and (b - end).Length < 1e-5:
            flipped = False
        elif (a - end).Length < 1e-5 and (b - start).Length < 1e-5:
            flipped = True
        else:
            continue
        try:
            if edge.distToShape(probe)[0] < 1e-5:
                return i, flipped
        except Exception:
            continue
    return None, False


def _point_on(edge, reversed_, fraction):
    """The point `fraction` of the way along `edge` from its chain-start end."""
    length = edge.Length
    along = (1.0 - fraction) * length if reversed_ else fraction * length
    try:
        parameter = edge.getParameterByLength(min(max(along, 0.0), length))
    except Exception:
        t0, t1 = edge.FirstParameter, edge.LastParameter
        parameter = t0 + (t1 - t0) * (along / length if length > TOL else 0.0)
    return edge.valueAt(parameter)


# -- the rows -------------------------------------------------------------------------------
def _expand(info, refs, chain=True):
    """Edge names a row's picks round (faces: their sharp edges), with their tangent chains
    when `chain` is set (OpenCASCADE rounds those anyway: each gets its size explicitly)."""
    names = blend.blended_edges(info, refs)
    if not chain:
        return names
    out = []
    for name in names:
        for member in info.chain(name):
            if member not in out:
                out.append(member)
    return out


def _edge_item(info, row, name):
    """(edge index, r1, r2) of edge `name` in a Constant or Chord Length row: its radius at its
    first and last vertex."""
    rtype = row.get("radius_type", "constant")
    if rtype == "constant":
        r = float(row.get("radius", 1.0))
        if r <= 0:
            raise core.SetError("The radius must be more than 0 mm.")
        return _index(name), r, r
    if rtype == "chord":
        chord = float(row.get("chord", 1.0))
        edge = blend.element(info.shape, name)
        ends = []
        for t in (edge.FirstParameter, edge.LastParameter):
            found = turn_at(info, name, t)
            if found is None:
                raise core.SetError("An edge of this set has no corner to round.")
            ends.append(core.chord_radius(chord, found[0]))
        return _index(name), ends[0], ends[1]
    raise core.SetError("unknown radius type %r" % (rtype,))


def _claims(info, rows, groups, taken):
    """[(edge name, row index, wanted)] of the Constant / Chord Length rows: first every
    edge picked on its own, then the edges of picked faces (an edge picked by itself beats a
    face that has it, whatever the order of the sets), then the edges tangent to them: those
    of a set with Tangent Chain on are rounded with it (wanted), those of a set with it off
    only get a size for OpenCASCADE (which rounds the whole chain) and are put back
    afterwards (_local). Otherwise an edge goes to the first set that claims it."""
    claimed, out = set(taken), []

    def claim(name, i, wanted):
        if name not in claimed:
            claimed.add(name)
            out.append((name, i, wanted))

    usable = [
        (i, row, refs)
        for i, (row, refs) in enumerate(zip(rows, groups))
        if refs and row.get("radius_type") != "variable"
    ]
    for faces in (False, True):
        for i, _row, refs in usable:
            picked = [ref for ref in refs if ref.startswith("Face") == faces]
            for name in blend.blended_edges(info, picked):
                claim(name, i, True)
    for chained in (True, False):
        for i, row, refs in usable:
            if bool(row.get("tangent_chain", True)) != chained:
                continue
            for name in blend.blended_edges(info, refs):
                for member in info.chain(name):
                    claim(member, i, chained)
    return out


def variable_plan(info, row, refs, chain=True):
    """(cut points, [(start point, end point, middle point, r at start, r at end)], rest) of
    a Variable row: where its edge (and tangent chain) is cut and the radius at each piece's
    ends. Tangent Chain off (`chain` False): only the picked edge carries the law; `rest`
    are the other edges of its chain (OpenCASCADE rounds them anyway; they are put back
    afterwards), each with the radius of the end it touches. Raises SetError."""
    edges = blend.blended_edges(info, refs)
    if len(edges) != 1:
        raise core.SetError(
            "A Variable radius set rounds one edge (with the edges tangent to it). Put the "
            "other edges in a set of their own (+)."
        )
    points = core.variable_points(
        row.get("start", 1.0), row.get("end", 1.0), [tuple(p) for p in row.get("points", [])]
    )
    order = ordered_chain(info, edges[0]) if chain else [(edges[0], False)]
    shapes = [blend.element(info.shape, n) for n, _r in order]
    cuts, pieces = core.split_plan([e.Length for e in shapes], points)
    rest = []
    if not chain:
        picked = shapes[0]
        first = picked.valueAt(picked.FirstParameter)
        last = picked.valueAt(picked.LastParameter)
        for name in info.chain(edges[0]):
            if name == edges[0]:
                continue
            edge = blend.element(info.shape, name)
            a, b = edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)
            m = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
            near_start = min((a - first).Length, (b - first).Length)
            near_end = min((a - last).Length, (b - last).Length)
            r = points[0][1] if near_start <= near_end else points[-1][1]
            rest.append((a, b, m, r, r))
    cut_points = [_point_on(shapes[i], order[i][1], f) for i, f in cuts]
    total = sum(e.Length for e in shapes)
    bounds = [0.0]
    for e in shapes:
        bounds.append(bounds[-1] + e.Length / total)
    out = []
    for i, s0, s1, r0, r1 in pieces:
        span = bounds[i + 1] - bounds[i]
        f0 = (s0 - bounds[i]) / span if span > TOL else 0.0
        f1 = (s1 - bounds[i]) / span if span > TOL else 1.0
        fm = (f0 + f1) / 2.0
        edge, rev = shapes[i], order[i][1]
        out.append(
            (
                _point_on(edge, rev, f0),
                _point_on(edge, rev, f1),
                _point_on(edge, rev, fm),
                r0,
                r1,
            )
        )
    return cut_points, out, rest


def _relocate(old_shape, new_shape, index):
    """Index in `new_shape` of edge `index` of `old_shape` (same ends and middle), or None."""
    edge = old_shape.Edges[index - 1]
    a, b = edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)
    m = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
    found, flipped = _edge_on(new_shape, a, b, m)
    return found, flipped


def _local(base, result, wanted, chains):
    """Tangent Chain off: put back the material the round took off along chain edges that
    were not picked. `wanted`: picked edges; `chains`: every edge the round ran along (edges
    of `base`). The removed material is cut where a picked edge meets an unpicked one (a
    plane square to the picked edge there), and only the pieces along picked edges stay
    removed."""
    import Part

    unwanted = [e for e in chains if not any(e.isSame(w) for w in wanted)]
    if not unwanted:
        return result
    removed = base.cut(result)
    if removed.isNull() or not removed.Solids:
        return result
    size = base.BoundBox.DiagonalLength * 2.0 + 10.0
    discs = []
    for w in wanted:
        for t in (w.FirstParameter, w.LastParameter):
            p = w.valueAt(t)
            if not any(
                (u.valueAt(u.FirstParameter) - p).Length < 1e-6
                or (u.valueAt(u.LastParameter) - p).Length < 1e-6
                for u in unwanted
            ):
                continue
            d = w.tangentAt(t)
            if d.Length < TOL:
                continue
            d.normalize()
            discs.append(Part.Face(Part.Wire(Part.Circle(p, d, size).toShape())))
    if not discs:
        return result
    pieces = removed.generalFuse(discs)[0].Solids
    keep = []
    for piece in pieces:
        center = piece.CenterOfMass
        probe = Part.Vertex(center)
        near_w = min(w.distToShape(probe)[0] for w in wanted)
        near_u = min(u.distToShape(probe)[0] for u in unwanted)
        if near_w <= near_u:
            keep.append(piece)
    if not keep:
        raise core.SetError(
            "With Tangent Chain off nothing of the round is left on the picked edges here."
        )
    cutter = keep[0] if len(keep) == 1 else keep[0].multiFuse(keep[1:])
    out = base.cut(cutter)
    return out


def _round_fillet_rows(shape, spec, groups):
    """The Fillet type: every row, one OpenCASCADE run (a variable row cuts its edges at its
    radius points first)."""
    info = blend.ShapeInfo(shape)
    rows = spec.get("sets", [])
    cut_points, variable, taken = [], [], set()
    for row, refs in zip(rows, groups):
        if refs and row.get("radius_type") == "variable":
            chain = bool(row.get("tangent_chain", True))
            points, plan, rest = variable_plan(info, row, refs, chain)
            cut_points.extend(points)
            variable.append((plan, rest))
            # its edges (and their chain) belong to the variable set: other sets skip them
            for name in blend.blended_edges(info, refs):
                taken.update(info.chain(name))
    try:
        work = split_at(shape, cut_points) if cut_points else shape
    except Exception as exc:
        raise core.SetError("The edge could not be cut at its radius points (%s)." % exc)

    def on_work(index, a, b):
        if work is shape:
            return index, a, b
        found, flipped = _relocate(shape, work, index)
        if found is None:
            raise core.SetError("An edge of a set was lost cutting the variable edge.")
        return (found, b, a) if flipped else (found, a, b)

    items, chains, wanted = [], [], []
    for name, i, keep in _claims(info, rows, groups, taken):
        index, a, b = on_work(*_edge_item(info, rows[i], name))
        items.append((index, a, b))
        edge = work.Edges[index - 1]
        chains.append(edge)
        if keep:
            wanted.append(edge)
    for plan, rest in variable:
        for pieces, picked in ((plan, True), (rest, False)):
            for start, end, middle, r0, r1 in pieces:
                index, flipped = _edge_on(work, start, end, middle)
                if index is None:
                    raise core.SetError("The variable edge could not be cut at its radius points.")
                items.append((index, r1, r0) if flipped else (index, r0, r1))
                chains.append(work.Edges[index - 1])
                if picked:
                    wanted.append(work.Edges[index - 1])
    result = kernel("fillet", work, items, tag=shape.Tag)
    if any(refs and not row.get("tangent_chain", True) for row, refs in zip(rows, groups)):
        try:
            result = _local(work, result, wanted, chains)
        except core.SetError:
            raise
        except Exception as exc:
            raise core.SetError(
                "With Tangent Chain off the round could not be stopped at the tangent edges "
                "here (%s). Turn Tangent Chain on." % exc
            )
    return result


def _chamfer_rows(shape, spec, groups):
    info = blend.ShapeInfo(shape)
    items, taken = [], set()
    # an edge picked on its own belongs to its set even when another set has its face
    owner = {}
    for i, refs in enumerate(groups):
        for name in blend.blended_edges(info, [ref for ref in refs if ref.startswith("Edge")]):
            owner.setdefault(name, i)
    for i, (row, refs) in enumerate(zip(spec.get("sets", []), groups)):
        if not refs:
            continue
        ctype = row.get("chamfer_type", "equal")
        d1 = float(row.get("distance", 1.0))
        d2 = float(row.get("distance2", d1))
        if d1 <= 0 or (ctype == "two" and d2 <= 0):
            raise core.SetError("A chamfer distance must be more than 0 mm.")
        flip = bool(row.get("flip"))
        for name in _expand(info, refs):
            if name in taken or owner.get(name, i) != i:
                continue
            taken.add(name)
            if ctype == "equal":
                a, b = d1, d1
            elif ctype == "two":
                a, b = d1, d2
            else:
                edge = blend.element(info.shape, name)
                found = turn_at(info, name, (edge.FirstParameter + edge.LastParameter) / 2.0)
                if found is None:
                    raise core.SetError("An edge of this set has no corner to bevel.")
                a, b = d1, core.angle_distance2(d1, row.get("angle", 45.0), found[1])
            # Part::Chamfer measures size 1 on the edge's first face, like blend's reference
            # face; Flip measures the row's first distance on the other face.
            if flip:
                a, b = b, a
            items.append((_index(name), a, b))
    return kernel("chamfer", shape, items)


# -- Rule Fillet -----------------------------------------------------------------------------
def _same_face_quick(a, b):
    try:
        if not blend._same_surface(a.Surface, b.Surface, 1e-6):
            return False
        return a.distToShape(b)[0] < 1e-6
    except Exception:
        return False


def feature_faces(feature, info):
    """Faces of the shape in `info` that `feature` made (on a surface of its result that the
    step before it did not have)."""
    shape = getattr(feature, "Shape", None)
    if shape is None or shape.isNull():
        return []
    before = getattr(feature, "BaseFeature", None)
    old = before.Shape.Faces if before is not None and not before.Shape.isNull() else []
    made = [f for f in shape.Faces if not any(_same_face_quick(f, o) for o in old)]
    names = []
    for i, face in enumerate(info.faces, start=1):
        if any(_same_face_quick(face, m) for m in made):
            names.append("Face%d" % i)
    return names


def rule_edges(info, spec, faces, features, faces2=(), features2=()):
    """The edges Rule Fillet rounds now (found again at every compute)."""
    first = list(faces)
    for feature in features:
        first += [f for f in feature_faces(feature, info) if f not in first]
    rounds, fillets = spec.get("rounds", True), spec.get("fillets", True)
    if spec.get("rule", "all") == "between":
        second = list(faces2)
        for feature in features2:
            second += [f for f in feature_faces(feature, info) if f not in second]
        a, b = set(first), set(second)
        candidates = []
        for name in first:
            for edge in info.face_edges(name)[0]:
                around = [blend.face_name(info.shape, f) for f in info.faces_of(edge)]
                if len(around) == 2 and (
                    (around[0] in a and around[1] in b) or (around[1] in a and around[0] in b)
                ):
                    if edge not in candidates:
                        candidates.append(edge)
    else:
        candidates = blend.blended_edges(info, first)
    out = []
    for name in candidates:
        data = info.frame(name)
        if data is not None and core.rule_keeps(data["convex"], rounds, fillets):
            out.append(name)
    return out


# -- Full Round -----------------------------------------------------------------------------
def _plane_normal(face):
    if type(face.Surface).__name__ != "Plane":
        return None
    u0, u1, v0, v1 = face.ParameterRange
    n = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    if n.Length < TOL:
        return None
    n.normalize()
    return n


def side_faces(shape, center_name):
    """(side face name, side face name) next to the centre face: flat, square to it, facing
    away from each other, as far apart as the centre face is wide and at least half that
    tall (the walls of a rib). The pairs along the longest edges are tried first. Raises
    SetError when no pair fits, with the reason of the best one."""
    center = blend.element(shape, center_name)
    nc = _plane_normal(center) if center is not None else None
    if nc is None:
        raise core.SetError(
            "Full Round works on a flat face between two flat, parallel side faces (the top "
            "of a rib or a wall). Click such a face."
        )
    found = []
    for edge in center.Edges:
        for face in blend.faces_of(shape, edge):
            if face.isSame(center):
                continue
            n = _plane_normal(face)
            if n is None or abs(n.dot(nc)) > 1e-6:
                continue
            name = blend.face_name(shape, face)
            known = [i for i, (f, _n, _l) in enumerate(found) if f == name]
            if known:
                f, fn, length = found[known[0]]
                found[known[0]] = (f, fn, length + edge.Length)
            elif name:
                found.append((name, n, edge.Length))
    pairs = []
    for i, (a, na, la) in enumerate(found):
        for b, nb, lb in found[i + 1 :]:
            if na.dot(nb) < -1 + 1e-9:
                pairs.append((la + lb, a, b))
    if not pairs:
        raise core.SetError(
            "This face has no two parallel side faces next to it, so there is nothing to "
            "make a full round between. Click the top face of a rib or a wall."
        )
    pairs.sort(key=lambda p: -p[0])
    reason = None
    for _length, a, b in pairs:
        try:
            full_round_plan(shape, a, center_name, b)
            return a, b
        except core.SetError as exc:
            reason = reason or exc
    raise reason


def full_round_size(shape, names):
    """The radius of a full round (half the width between its side faces), or None."""
    if len(names) != 3:
        return None
    try:
        return full_round_plan(shape, *names)["radius"]
    except Exception:
        return None


def full_round_plan(shape, side1, center, side2):
    """Where the half round goes: {"radius", "axis_point", "direction", "face"}. Raises
    SetError when the three faces are not a rib's top and walls."""
    faces = [blend.element(shape, n) for n in (side1, center, side2)]
    if any(f is None for f in faces):
        raise core.SetError("A face of this full round no longer exists. Pick it again.")
    n1, nc, n2 = [_plane_normal(f) for f in faces]
    if None in (n1, nc, n2) or n1.dot(n2) > -1 + 1e-6 or abs(n1.dot(nc)) > 1e-6:
        raise core.SetError(
            "Full Round needs two flat, parallel side faces square to the centre face."
        )
    p1 = faces[0].Vertexes[0].Point
    p2 = faces[2].Vertexes[0].Point
    width = abs((p2 - p1).dot(n1))
    radius = core.full_round_radius(width)
    across = max(abs(v.Point.sub(p1).dot(n1)) for v in faces[1].Vertexes)
    if across < width - 1e-4 or across > width + 1e-4:
        raise core.SetError(
            "This face does not reach from one side face to the other: Full Round rounds a "
            "face that spans the whole width of a rib or a wall."
        )
    c = faces[1].CenterOfMass
    for side in (faces[0], faces[2]):
        depth = max((c - v.Point).dot(nc) for v in side.Vertexes)
        if depth < radius - 1e-4:
            raise core.SetError(
                "The side faces are lower than the round's radius (%g mm, half the width): "
                "the round would not fit. Full Round is for faces between tall side faces "
                "(the top of a rib or a wall)." % round(radius, 4)
            )
    mid = c - n1 * (c - p1).dot(n1) - n1 * (width / 2.0)
    direction = nc.cross(n1)
    direction.normalize()
    return {
        "radius": radius,
        "axis_point": mid - nc * radius,
        "direction": direction,
        "face": faces[1],
        "normal": nc,
    }


def full_round(shape, side1, center, side2):
    """`shape` with the centre face replaced by a half cylinder tangent to both side faces:
    the slab under the centre face, half the width deep, minus that cylinder, is cut away."""
    import Part

    plan = full_round_plan(shape, side1, center, side2)
    radius, direction, face = plan["radius"], plan["direction"], plan["face"]
    length = face.BoundBox.DiagonalLength * 2.0 + 2.0
    slab = face.extrude(plan["normal"] * -radius)
    start = plan["axis_point"] - direction * length
    cylinder = Part.makeCylinder(radius, 2.0 * length, start, direction)
    cutter = slab.cut(cylinder)
    if cutter.isNull() or cutter.Volume < 1e-9:
        return shape
    return shape.cut(cutter)


# -- the whole step ----------------------------------------------------------------------------
_RESULTS = []  # (key, input shape, result) of the last few computes: the dialog's trial and
# the step's own compute that follows it build the same thing once. The input shape is kept
# (and compared as the same shape, not only by its hash): a freed shape's memory could be
# reused by another one with the same hash.
_KEEP = 4


def _key(shape, spec, refs, refs2, features, features2):
    try:
        return (
            shape.hashCode(),
            core.dumps(spec),
            tuple(refs),
            tuple(refs2),
            tuple(f.Name for f in features),
            tuple(f.Name for f in features2),
        )
    except Exception:
        return None


def compute(shape, spec, refs, refs2=(), features=(), features2=()):
    """The blended shape. `refs`: the step's picks (all rows, in order). Raises BlendError
    with a plain-language reason."""
    key = _key(shape, spec, refs, refs2, features, features2)
    for known, source, result in _RESULTS:
        try:
            if key is not None and known == key and source.isSame(shape):
                return result
        except Exception:
            continue
    result = _compute(shape, spec, refs, refs2, features, features2)
    if key is not None:
        _RESULTS.insert(0, (key, shape, result))
        del _RESULTS[_KEEP:]
    return result


def _compute(shape, spec, refs, refs2, features, features2):
    try:
        core.check_spec(spec)
        if shape is None or shape.isNull() or not shape.Solids:
            raise core.SetError("Make a solid first (Create Sketch, then Extrude).")
        groups = core.split_refs(spec, list(refs))
        mode = spec.get("mode", "fillet")
        if spec.get("kind") == "chamfer":
            if not any(groups):
                raise core.SetError("Select the edges or faces to chamfer.")
            result = _with_rows(_chamfer_rows, shape, spec, groups)
        elif mode == "rule":
            info = blend.ShapeInfo(shape)
            edges = rule_edges(info, spec, list(refs), features, list(refs2), features2)
            if not edges:
                raise core.SetError(_rule_empty(spec, refs, refs2, features, features2))
            r = float(spec.get("radius", 1.0))
            if r <= 0:
                raise core.SetError("The radius must be more than 0 mm.")
            try:
                result = kernel("fillet", shape, [(_index(n), r, r) for n in edges])
            except KernelError:
                raise core.SetError(
                    "Radius %g mm is too big here: the rounds do not fit on the faces next "
                    "to their edges." % r
                )
        elif mode == "full_round":
            result = shape
            done = 0
            for group in groups:
                if len(group) != 3:
                    continue
                try:
                    result = full_round(result, *_carry(shape, result, group))
                except core.SetError:
                    raise
                except Exception as exc:
                    raise core.SetError("The full round could not be built here (%s)." % exc)
                done += 1
            if not done:
                raise core.SetError(
                    "Click the face to round: the top of a rib or a wall (its two side faces "
                    "are found by themselves)."
                )
        else:
            if not any(groups):
                raise core.SetError("Select the edges or faces to round.")
            result = _with_rows(_round_fillet_rows, shape, spec, groups)
    except core.SetError as exc:
        raise _error(exc)
    if result is None or result.isNull() or not result.Solids:
        raise blend.BlendError("The kernel could not build this with these sizes.")
    if len(result.Solids) > max(1, len(shape.Solids)):
        raise blend.BlendError("This would cut the part into pieces. Use a smaller size.")
    if not result.isValid():
        raise blend.BlendError(
            "The result is not a valid solid. Try a smaller size or fewer edges."
        )
    return result


def _with_rows(build, shape, spec, groups):
    """build(shape, spec, groups); when OpenCASCADE fails, each set is tried on its own to
    say which one does not fit (Fusion names the selection set that fails)."""
    try:
        return build(shape, spec, groups)
    except KernelError:
        pass
    filled = [i for i, g in enumerate(groups) if g]
    for i in filled:
        alone = [g if j == i else [] for j, g in enumerate(groups)]
        try:
            build(shape, spec, alone)
        except KernelError:
            text = _too_big(spec, i)
            raise core.SetError(text if len(filled) == 1 else "Set %d: %s" % (i + 1, text))
        except (core.SetError, blend.BlendError) as exc:
            raise core.SetError("Set %d: %s" % (i + 1, exc))
    raise core.SetError("The sets do not fit together where they meet: make one of them smaller.")


def _too_big(spec, i):
    row = spec["sets"][i]
    if spec.get("kind") == "chamfer":
        return blend.too_big("chamfer", "distance", float(row.get("distance", 1.0)))
    rtype = row.get("radius_type", "constant")
    if rtype == "chord":
        return (
            "Chord length %g mm is too big here: the round does not fit on the faces next to "
            "it." % float(row.get("chord", 1.0))
        )
    if rtype == "variable":
        return (
            "A radius of this variable round is too big here: the round does not fit on the "
            "faces next to the edge. Make the start, end or point radii smaller."
        )
    return blend.too_big("fillet", "radius", float(row.get("radius", 1.0)))


def _rule_empty(spec, refs, refs2, features, features2):
    if not refs and not features:
        return "Select faces or features (a step in the timeline) to fillet by the rule."
    if spec.get("rule") == "between" and not refs2 and not features2:
        return "Select the second faces or features: the edges between the two are rounded."
    if not spec.get("rounds", True) and not spec.get("fillets", True):
        return "Turn on Rounds, Fillets or both."
    return "No edge of the selection fits the rule (rounds / fillets, between the two sets)."


def _carry(original, current, names):
    """The names of faces of `original` on `current` (earlier full rounds changed it)."""
    if current is original:
        return names
    out = []
    for name in names:
        face = blend.element(original, name)
        found = [
            "Face%d" % i
            for i, f in enumerate(current.Faces, start=1)
            if face is not None and _same_face_quick(face, f)
        ]
        if not found:
            raise core.SetError("Two full rounds share a face: make them one at a time.")
        out.append(found[0])
    return out


# -- the document step --------------------------------------------------------------------------
def _add(obj, kind, name, doc, hidden=False):
    if name not in obj.PropertiesList:
        obj.addProperty(kind, name, "Fillet", doc, 4 if hidden else 0)
        return True
    return False


def size_props(spec):
    """{property name: (property type, value)} of the values a parameter can drive."""
    out = {}
    kind = spec.get("kind")
    mode = spec.get("mode", "fillet")
    if kind == "fillet" and mode == "rule":
        out["Size1"] = ("App::PropertyLength", float(spec.get("radius", 1.0)))
        return out
    if mode == "full_round":
        return out
    for i, row in enumerate(spec.get("sets", []), start=1):
        if kind == "chamfer":
            out["Size%d" % i] = ("App::PropertyLength", float(row.get("distance", 1.0)))
            out["SizeB%d" % i] = ("App::PropertyLength", float(row.get("distance2", 1.0)))
            out["Angle%d" % i] = ("App::PropertyAngle", float(row.get("angle", 45.0)))
        else:
            key = "chord" if row.get("radius_type") == "chord" else "radius"
            out["Size%d" % i] = ("App::PropertyLength", float(row.get(key, 1.0)))
    return out


def prop_key(spec, prop):
    """(row index or None for the rule radius, option name) a size property drives."""
    kind = spec.get("kind")
    if kind == "fillet" and spec.get("mode") == "rule":
        return (None, "radius") if prop == "Size1" else (None, None)
    for prefix, option in (("SizeB", "distance2"), ("Angle", "angle"), ("Size", None)):
        if prop.startswith(prefix) and prop[len(prefix) :].isdigit():
            i = int(prop[len(prefix) :]) - 1
            rows = spec.get("sets", [])
            if i >= len(rows):
                return (None, None)
            if option is None:
                if kind == "chamfer":
                    option = "distance"
                else:
                    option = "chord" if rows[i].get("radius_type") == "chord" else "radius"
            return (i, option)
    return (None, None)


def read_spec(obj):
    """The step's settings, with the values the size properties hold now (a parameter may
    drive them)."""
    spec = core.loads(getattr(obj, SPEC, ""), kind_of(obj) or "fillet")
    for prop in obj.PropertiesList:
        if not (prop.startswith("Size") or prop.startswith("Angle")):
            continue
        row, option = prop_key(spec, prop)
        if option is None:
            continue
        value = getattr(obj, prop)
        value = float(getattr(value, "Value", value))
        if row is None:
            spec[option] = value
        else:
            spec["sets"][row][option] = value
    return spec


def write_spec(obj, spec):
    """Put the settings on the step (only what changed: an untouched step is not rebuilt)."""
    text = core.dumps(spec)
    if getattr(obj, SPEC, None) != text:
        setattr(obj, SPEC, text)
    for prop, (type_id, value) in size_props(spec).items():
        _add(obj, type_id, prop, "A size of this fillet / chamfer")
        if _has_expression(obj, prop):
            continue
        current = getattr(obj, prop)
        current = float(getattr(current, "Value", current))
        if abs(current - value) > 1e-12:
            setattr(obj, prop, value)
    used = _used_sizes(spec)
    for prop in obj.PropertiesList:
        if prop.startswith("Size") or prop.startswith("Angle"):
            mode = [] if prop in used else ["Hidden"]
            try:
                if list(obj.getEditorMode(prop)) != mode:
                    obj.setEditorMode(prop, mode)
            except Exception:
                pass


def _used_sizes(spec):
    """The size properties the settings use now (the parameters table lists only those)."""
    if spec.get("mode") == "rule":
        return {"Size1"} if spec.get("kind") == "fillet" else set()
    if spec.get("mode") == "full_round":
        return set()
    used = set()
    for i, row in enumerate(spec.get("sets", []), start=1):
        if spec.get("kind") == "chamfer":
            used.add("Size%d" % i)
            ctype = row.get("chamfer_type", "equal")
            if ctype == "two":
                used.add("SizeB%d" % i)
            elif ctype == "angle":
                used.add("Angle%d" % i)
        elif row.get("radius_type", "constant") != "variable":
            used.add("Size%d" % i)
    return used


def _has_expression(obj, prop):
    try:
        return any(path in (prop, "." + prop) for path, _e in obj.ExpressionEngine)
    except Exception:
        return False


class FilletSetsFeature:
    """The step. Saved in files as "sciforge.fillet_sets.FilletSetsFeature": keep the name."""

    def __init__(self, obj, kind="fillet"):
        obj.Proxy = self
        self.ensure_properties(obj, kind)

    @staticmethod
    def ensure_properties(obj, kind=None):
        kind = kind or kind_of(obj) or "fillet"
        _add(obj, "App::PropertyLinkSub", "Picks", "Picked edges / faces of every set")
        _add(obj, "App::PropertyLinkSub", "Picks2", "Rule Fillet: the second faces")
        _add(obj, "App::PropertyLinkList", "RuleFeatures", "Rule Fillet: picked steps")
        _add(obj, "App::PropertyLinkList", "RuleFeatures2", "Rule Fillet: second steps")
        if _add(obj, "App::PropertyString", SPEC, "The settings (sets, types)", hidden=True):
            setattr(obj, SPEC, core.dumps(core.default_spec(kind)))
        if _add(obj, "App::PropertyBool", "Refine", "Merge faces that end up in one plane"):
            obj.Refine = True
        bodies.mark(obj, SCIFORGE_TYPES[kind])

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            self._build(obj)
        except Exception:
            bodies.pass_through(obj)  # the part as it was before this step; the step red
            raise

    def _build(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise blend.BlendError("There is no solid before this step.")
        spec = read_spec(obj)
        refs, refs2 = _subs(obj.Picks), _subs(obj.Picks2)
        if any(r.startswith("?") for r in refs + refs2):
            raise blend.BlendError(
                "An edge or face this step was built on no longer exists (an earlier step "
                "changed the model). Edit the step and pick it again."
            )
        features = [f for f in (obj.RuleFeatures or []) if f is not None]
        features2 = [f for f in (obj.RuleFeatures2 or []) if f is not None]
        result = compute(base.Shape, spec, refs, refs2, features, features2)
        if obj.Refine:
            try:
                refined = result.removeSplitter()
                if refined.isValid() and refined.Solids:
                    result = refined
            except Exception:
                pass
        obj.Shape = result

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _subs(link):
    if not link:
        return []
    return [s.split(".")[-1] for s in (link[1] or []) if s]


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .bodies_gui import StepViewProvider

        StepViewProvider(obj.ViewObject)
    except Exception:
        pass


def set_picks(obj, base, refs, refs2=(), features=(), features2=()):
    """Point the step at its picks (only what changed)."""

    def put(prop, value):
        current = getattr(obj, prop)
        if value is None or not value[1]:
            if current:
                setattr(obj, prop, None)
            return
        if current and current[0] is value[0] and list(current[1]) == list(value[1]):
            return
        setattr(obj, prop, value)

    put("Picks", (base, list(refs)))
    put("Picks2", (base, list(refs2)))
    for prop, value in (("RuleFeatures", list(features)), ("RuleFeatures2", list(features2))):
        if [o.Name for o in getattr(obj, prop) or []] != [o.Name for o in value]:
            setattr(obj, prop, value)
    if obj.Refine is not True:
        obj.Refine = True


def make(body, base, spec, refs, refs2=(), features=(), features2=(), name=None):
    """A new step at the history marker of `body` (not recomputed). Returns it."""
    kind = spec.get("kind", "fillet")
    obj = bodies.insert_after_tip(body, TYPE, name or ("Fillet" if kind == "fillet" else "Chamfer"))
    FilletSetsFeature(obj, kind)
    _attach_view_provider(obj)
    write_spec(obj, spec)
    set_picks(obj, base, refs, refs2, features, features2)
    return obj


def update(obj, base, spec, refs, refs2=(), features=(), features2=()):
    write_spec(obj, spec)
    set_picks(obj, base, refs, refs2, features, features2)
    return obj


def read(obj):
    """(base, spec, refs, refs2, features, features2) of a step."""
    picks = obj.Picks
    base = picks[0] if picks else obj.BaseFeature
    return (
        base,
        read_spec(obj),
        _subs(picks),
        _subs(obj.Picks2),
        [f for f in obj.RuleFeatures or [] if f is not None],
        [f for f in obj.RuleFeatures2 or [] if f is not None],
    )


# -- FreeCAD's fillet becomes this step ------------------------------------------------------
def replace(old, build):
    """Put a new step in the place of `old` in its body (the dialog's step turning from
    FreeCAD's Fillet into SciForge's, when a second set or another type is chosen):
    `build(body)` makes the new step (at the history marker, which is moved right after
    `old` first). The steps after it are linked to the new one; `old` is deleted. Returns
    the new step."""
    body = bodies.body_of(old)
    tip = body.Tip
    was_tip = tip is old
    body.Tip = old  # the new step goes in right after it
    new = build(body)
    expressions = []
    try:
        expressions = list(old.ExpressionEngine)
    except Exception:
        pass
    try:
        body.removeObject(old)
    except Exception:
        pass
    old.Document.removeObject(old.Name)
    body.Tip = new if (was_tip or tip is None) else tip
    return new, expressions


# -- Press Pull on a face of the step -----------------------------------------------------------
def size_of_face(step, face):
    """(size property, label for the box) of the set whose round / bevel `face` is (Press
    Pull on a fillet face edits that fillet's size, in Fusion), or (None, None) when that
    set has no single size (Variable, Full Round)."""
    try:
        spec = read_spec(step)
        if spec.get("mode") == "full_round" or face is None:
            return None, None
        if spec.get("mode") == "rule":
            return "Size1", "Fillet radius"
        base = step.BaseFeature
        info = blend.ShapeInfo(base.Shape)
        groups = core.split_refs(spec, _subs(step.Picks))
        best = None
        for i, (row, refs) in enumerate(zip(spec["sets"], groups)):
            for name in _expand(info, refs):
                edge = blend.element(info.shape, name)
                if edge is None:
                    continue
                d = edge.distToShape(face)[0]
                if best is None or d < best[0]:
                    best = (d, i)
        if best is None:
            return None, None
        row = spec["sets"][best[1]]
        number = best[1] + 1
        if spec.get("kind") == "chamfer":
            return "Size%d" % number, "Chamfer distance (set %d)" % number
        if row.get("radius_type") == "variable":
            return None, None
        if row.get("radius_type") == "chord":
            return "Size%d" % number, "Chord length (set %d)" % number
        return "Size%d" % number, "Fillet radius (set %d)" % number
    except Exception:
        return None, None


# -- handles of the dialog -------------------------------------------------------------------
def _frame_at(info, name, point):
    """blend.frame()'s data at `point` on edge `name` (frame() looks at an edge's middle: a
    short piece of the edge around the point is handed to it)."""
    import Part

    edge = blend.element(info.shape, name)
    faces = info.faces_of(name)
    if edge is None or len(faces) != 2:
        return None
    orientations = [blend.orientation_in(face, edge) for face in faces]
    piece = edge
    try:
        parameter = edge.Curve.parameter(point)
        t0, t1 = edge.FirstParameter, edge.LastParameter
        parameter = min(max(parameter, t0), t1)
        step = (t1 - t0) * 1e-3
        lo, hi = max(t0, parameter - step), min(t1, parameter + step)
        if hi - lo > 1e-12:
            piece = Part.Edge(edge.Curve, lo, hi)
            if edge.Orientation == "Reversed":
                piece.reverse()
    except Exception:
        piece = edge
    return blend.frame(info.shape, piece, faces, orientations)


def chain_points(info, refs, chain=True):
    """[(edge name, reversed, start position, end position)] of a Variable row's edge and its
    tangent chain (Tangent Chain off: the edge alone), positions 0..1 along it (as the
    radius points are measured)."""
    edges = blend.blended_edges(info, refs)
    if len(edges) != 1:
        return []
    try:
        order = ordered_chain(info, edges[0]) if chain else [(edges[0], False)]
    except core.SetError:
        return []
    shapes = [blend.element(info.shape, n) for n, _r in order]
    total = sum(e.Length for e in shapes)
    if total <= TOL:
        return []
    out, at = [], 0.0
    for (name, rev), edge in zip(order, shapes):
        nxt = at + edge.Length / total
        out.append((name, rev, at, nxt))
        at = nxt
    return out


def point_at(info, refs, position, chain=True):
    """(edge name, 3D point) at `position` (0..1) along a Variable row's chain, or None."""
    for name, rev, s0, s1 in chain_points(info, refs, chain):
        if position <= s1 + 1e-9:
            edge = blend.element(info.shape, name)
            fraction = (position - s0) / (s1 - s0) if s1 - s0 > TOL else 0.0
            return name, _point_on(edge, rev, min(max(fraction, 0.0), 1.0))
    return None


def position_of(info, refs, point, chain=True):
    """The position (0..1) along a Variable row's chain nearest to a clicked 3D point."""
    import Part

    best = None
    probe = Part.Vertex(point)
    for name, rev, s0, s1 in chain_points(info, refs, chain):
        edge = blend.element(info.shape, name)
        try:
            dist, pairs, _info = edge.distToShape(probe)
            foot = pairs[0][0]
        except Exception:
            continue
        try:
            p_foot = edge.Curve.parameter(foot)
            lo, hi = edge.FirstParameter, min(max(p_foot, edge.FirstParameter), edge.LastParameter)
            from_first = Part.Edge(edge.Curve, lo, hi).Length if hi - lo > 1e-12 else 0.0
        except Exception:
            from_first = (foot - edge.valueAt(edge.FirstParameter)).Length
        along = edge.Length - from_first if rev else from_first
        fraction = along / edge.Length if edge.Length > TOL else 0.0
        position = s0 + (s1 - s0) * min(max(fraction, 0.0), 1.0)
        if best is None or dist < best[0]:
            best = (dist, position)
    return None if best is None else best[1]


def variable_spots(info, row, refs, toward=None, chain=True):
    """The drag arrows of a Variable row: one at its start, one at each radius point, one at
    its end, each where the round starts at that place: [spot] as blend.arrow_spots gives,
    "what" = "start" / "end" / "pt<k>"."""
    marks = [("start", 0.0)]
    for k, (position, _r) in enumerate(row.get("points", [])):
        marks.append(("pt%d" % k, float(position)))
    marks.append(("end", 1.0))
    spots = []
    for what, position in marks:
        found = point_at(info, refs, min(max(position, 0.0), 1.0), chain)
        if found is None:
            continue
        name, point = found
        data = _frame_at(info, name, point)
        if data is None:
            continue
        index = 0
        if toward is not None:
            index = blend.toward_face(data["normals"], toward)
        half = max(data["gamma"] / 2.0, math.radians(5))
        spots.append(
            {
                "what": what,
                "point": point,
                "direction": data["into"][index],
                "lift": data["normals"][index],
                "per_unit": min(max(1.0 / math.tan(half), 0.2), 5.0),
            }
        )
    return spots


def chord_per_unit(info, refs):
    """How far the arrow of a Chord Length row moves for 1 mm of chord: the round starts
    chord / (2 sin(gamma / 2)) from the edge (gamma: the corner's angle)."""
    names = blend.blended_edges(info, refs[:1]) or blend.blended_edges(info, refs)
    data = info.frame(names[0]) if names else None
    if data is None:
        return 1.0
    return min(max(1.0 / (2.0 * math.sin(max(data["gamma"], 1e-3) / 2.0)), 0.2), 5.0)
