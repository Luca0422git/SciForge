# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fillet's and Chamfer's live picture: the round (or bevel) of every picked edge following
the radius / distance arrow on every mouse move, in a few milliseconds, while the exact solid
is built only when the mouse rests or is let go (fillet_ui.BlendPanel), as Draft does
(draft_live.py). Before, nothing moved on a big part until the mouse rested.

Picture(info, spec, groups, ...) prepares the picked edges once per set of picks and options
(which edges each selection set rounds, sample points along each edge with the two faces'
normals there: fillet_live_core.py); points(spec) works out the band of every edge for the
sizes in `spec` (numpy: one multiply-add per point for a round). Overlay draws them over the
see-through part before the step, in the part's colour with the lines where the round meets
the faces, never pickable: Coin nodes the dialog owns, so nothing stays behind.

The picture is the rolling ball's band (a round) or the flat band (a chamfer) in the plane
square to the edge at each sample, cut where two picked edges meet: exact for flat faces and
for a flat face meeting a cylinder, a cone or an extruded wall (the usual cases), close
elsewhere (a round's corner patch where three rounded edges meet is not drawn); the exact
solid replaces it as soon as the mouse rests.
"""

import math

from . import blend, fillet_core, fillet_sets
from . import fillet_live_core as core

try:  # FreeCAD ships numpy
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None

ARC_STEPS = 8  # segments across a round
MAX_SAMPLES = 96  # along one curved edge


def _t(v):
    return (float(v.x), float(v.y), float(v.z))


def plan(info, spec, groups, refs2=(), features=(), features2=()):
    """[(edge name, how its size is found)] of the edges the step rounds or bevels, each once,
    as fillet_sets builds them (an edge picked on its own beats a face that has it; a set with
    Tangent Chain off rounds only its picked edges). The size is a dict:
      {"kind": "ball", "row": i, "type": "constant" | "chord" | "variable" | "rule",
       "chain": (reversed, start, end)}   (Variable: where the edge lies along the chain)
      {"kind": "bevel", "row": i, "ref": 0 | 1}   (the face Distance 1 is measured on)
    Full Round has no arrow to drag: nothing (an empty list)."""
    out = []
    rows = spec.get("sets", [])
    if spec.get("kind") == "chamfer":
        owner, taken = {}, set()
        for i, refs in enumerate(groups):
            picked = [r for r in refs if r.startswith("Edge")]
            for name in blend.blended_edges(info, picked):
                owner.setdefault(name, i)
        for i, (row, refs) in enumerate(zip(rows, groups)):
            if not refs:
                continue
            flip = bool(row.get("flip"))
            for name in fillet_sets._expand(info, refs):
                if name in taken or owner.get(name, i) != i:
                    continue
                taken.add(name)
                ref = blend.reference_face(info, name, flip)
                out.append((name, {"kind": "bevel", "row": i, "ref": ref}))
        return out
    mode = spec.get("mode", "fillet")
    if mode == "full_round":
        return []
    if mode == "rule":
        names = fillet_sets.rule_edges(
            info, spec, groups[0] if groups else [], features, refs2, features2
        )
        return [(n, {"kind": "ball", "row": None, "type": "rule"}) for n in names]
    taken = set()
    for i, (row, refs) in enumerate(zip(rows, groups)):
        if not refs or row.get("radius_type") != "variable":
            continue
        chain = bool(row.get("tangent_chain", True))
        for name, rev, s0, s1 in fillet_sets.chain_points(info, refs, chain):
            out.append(
                (name, {"kind": "ball", "row": i, "type": "variable", "chain": (rev, s0, s1)})
            )
        for name in blend.blended_edges(info, refs):
            taken.update(info.chain(name))
    for name, i, wanted in fillet_sets._claims(info, rows, groups, taken):
        if wanted:
            rtype = rows[i].get("radius_type", "constant")
            out.append((name, {"kind": "ball", "row": i, "type": rtype}))
    return out


class _Edge:
    """One edge's samples: points, tangents, the faces' normals and the directions across
    them, and (a round) the ball directions V of fillet_live_core.ball_dirs."""

    def __init__(self, info, name, size, deflection):
        edge = blend.element(info.shape, name)
        faces = info.faces_of(name)
        if edge is None or len(faces) != 2:
            raise ValueError("%s has no two faces" % name)
        self.name, self.size = name, size
        orientations = [blend.orientation_in(f, edge) for f in faces]
        t0, t1 = edge.FirstParameter, edge.LastParameter
        length = edge.Length
        curved = edge.Curve.__class__.__name__ not in ("Line", "LineSegment")
        if curved:
            try:
                count = len(edge.discretize(Deflection=deflection))
            except Exception:
                count = 16
            count = max(8, min(MAX_SAMPLES, count))
        else:
            variable = size.get("type") in ("variable", "chord")
            count = 9 if variable else 2
        params = []
        for k in range(count):
            f = k / float(count - 1)
            try:
                params.append((f, edge.getParameterByLength(f * length)))
            except Exception:
                params.append((f, t0 + (t1 - t0) * f))
        steps = ARC_STEPS if size["kind"] == "ball" else 1
        self.points, self.tangents, self.n0, self.n1 = [], [], [], []
        self.into0, self.into1, self.fractions, self.dirs = [], [], [], []
        for f, t in params:
            point = edge.valueAt(t)
            tangent = edge.tangentAt(t)
            if tangent.Length < 1e-12:
                continue
            tangent.normalize()
            normals, into = [], []
            for face, orientation in zip(faces, orientations):
                try:
                    u, v = face.Surface.parameter(point)
                    normal = face.normalAt(u, v)
                except Exception:
                    normal = None
                if normal is None or normal.Length < 1e-12:
                    break
                normal.normalize()
                direction = blend._into_face(face, point, tangent, normal, orientation)
                if direction is None:
                    break
                normals.append(normal)
                into.append(direction)
            if len(normals) != 2:
                continue
            n0, n1 = _t(normals[0]), _t(normals[1])
            convex = normals[1].dot(into[0]) < 0
            try:
                dirs = core.ball_dirs(n0, n1, convex, steps) if steps > 1 else None
            except ValueError:
                continue  # tangent faces here (a smooth end): nothing to round
            if steps == 1 and core.turn(n0, n1) < 1e-6:
                continue
            self.points.append(_t(point))
            self.tangents.append(_t(tangent))
            self.n0.append(n0)
            self.n1.append(n1)
            self.into0.append(_t(into[0]))
            self.into1.append(_t(into[1]))
            self.fractions.append(f)
            self.dirs.append(dirs)
        if len(self.points) < 2:
            raise ValueError("%s: no corner to round" % name)
        self.cols = steps + 1
        self.planes = []  # (plane, rows it cuts)
        self._end_faces(info, edge, faces)
        if _np is not None:
            self.P = _np.array(self.points, dtype=float)
            self.T = _np.array(self.tangents, dtype=float)
            self.I0 = _np.array(self.into0, dtype=float)
            self.I1 = _np.array(self.into1, dtype=float)
            cos = _np.clip(_np.einsum("ij,ij->i", _np.array(self.n0), _np.array(self.n1)), -1, 1)
            self.turn = _np.arccos(cos)
            if steps > 1:
                self.V = _np.array(self.dirs, dtype=float)  # (rows, cols, 3)
            rev, s0, s1 = size.get("chain", (False, 0.0, 1.0))
            f = _np.array(self.fractions, dtype=float)
            self.position = s0 + (s1 - s0) * ((1.0 - f) if rev else f)

    def _end_faces(self, info, edge, faces):
        """The band ends on a flat face at each end of the edge (the side face a round stops
        on, when it is not square to the edge: the end of a spline wall's top edge): the
        points past that face are slid back onto it."""
        import Part

        for point, away, rows in self.ends():
            try:
                vertex = min(
                    edge.Vertexes,
                    key=lambda v: (v.Point - __import__("FreeCAD").Vector(*point)).Length,
                )
                around = info.shape.ancestorsOfType(vertex, Part.Face)
            except Exception:
                continue
            for face in around:
                if any(face.isSame(f) for f in faces):
                    continue
                if face.Surface.__class__.__name__ != "Plane":
                    continue
                try:
                    u, v = face.Surface.parameter(vertex.Point)
                    normal = _t(face.normalAt(u, v))
                except Exception:
                    continue
                if abs(core.dot(normal, away)) < 0.05:
                    continue  # along the edge: it does not end the band
                # keep the material side of that face (its outward normal points away)
                self.planes.append(((_t(vertex.Point), core.scale(normal, -1.0)), list(rows)))

    def ends(self):
        """[(end point, direction leaving it along the edge, rows near it)] of both ends."""
        n = len(self.points)
        half = max(1, (n + 1) // 2)
        first = (self.points[0], self.tangents[0], range(0, half))
        last = (self.points[-1], core.scale(self.tangents[-1], -1.0), range(n - half, n))
        return [first, last]


class Picture:
    """The bands of one step's picked edges for one set of picks and options (not sizes)."""

    def __init__(self, info, spec, groups, refs2=(), features=(), features2=(), placement=None):
        if _np is None:
            raise ValueError("numpy is not available")
        self.kind = spec.get("kind", "fillet")
        self.placement = placement
        diag = max(info.shape.BoundBox.DiagonalLength, 1e-3)
        self.deflection = max(0.002 * diag, 0.01)
        self.tol = max(1e-5, 1e-6 * diag)
        self.edges = []
        for name, size in plan(info, spec, groups, refs2, features, features2):
            try:
                self.edges.append(_Edge(info, name, size, self.deflection))
            except ValueError:
                continue
        if not self.edges:
            raise ValueError("nothing to draw")
        self._mitres()
        self._index()

    def _mitres(self):
        """Where two drawn edges meet, each band is cut at the plane halving the corner."""
        ends = [(e, end) for e in self.edges for end in e.ends()]
        for edge, (point, away, rows) in ends:
            for other, (opoint, oaway, _r) in ends:
                if other is edge:
                    continue
                if core.norm(core.sub(point, opoint)) > self.tol * 10.0:
                    continue
                plane = core.mitre(point, away, oaway)
                if plane is not None:
                    edge.planes.append((plane, list(rows)))

    def _index(self):
        """The triangles and outline polylines (indices into points()), set once."""
        self.triangles, self.lines = [], []
        base = 0
        for e in self.edges:
            rows, cols = len(e.points), e.cols

            def at(i, j, base=base, cols=cols):
                return base + i * cols + j

            for i in range(rows - 1):
                for j in range(cols - 1):
                    self.triangles.append((at(i, j), at(i + 1, j), at(i + 1, j + 1)))
                    self.triangles.append((at(i, j), at(i + 1, j + 1), at(i, j + 1)))
            self.lines.append([at(i, 0) for i in range(rows)])  # where it meets face 0
            self.lines.append([at(i, cols - 1) for i in range(rows)])  # ... face 1
            self.lines.append([at(0, j) for j in range(cols)])  # the ends
            self.lines.append([at(rows - 1, j) for j in range(cols)])
            base += rows * cols
        self.count = base

    # -- the sizes --------------------------------------------------------------------------
    @staticmethod
    def _row(spec, size):
        row = size.get("row")
        if row is None:
            return spec
        sets = spec.get("sets", [])
        if row >= len(sets):
            raise ValueError("the selection set is gone")
        return sets[row]

    def _radii(self, spec, e):
        data = self._row(spec, e.size)
        kind = e.size.get("type")
        n = len(e.points)
        if kind == "rule":
            r = _np.full(n, float(spec.get("radius", 1.0)))
        elif kind == "chord":
            half = _np.sin(e.turn / 2.0)
            if (half < 1e-6).any():
                raise ValueError("tangent faces")
            r = float(data.get("chord", 1.0)) / (2.0 * half)
        elif kind == "variable":
            law = fillet_core.variable_points(
                data.get("start", 1.0),
                data.get("end", 1.0),
                [tuple(p) for p in data.get("points", [])],
            )
            r = _np.interp(e.position, [p for p, _r in law], [x for _p, x in law])
        else:
            r = _np.full(n, float(data.get("radius", 1.0)))
        if (r <= 0).any() or not _np.isfinite(r).all():
            raise ValueError("a radius must be more than 0")
        return r

    def _distances(self, spec, e):
        """(distance on face 0, distance on face 1) per sample."""
        data = self._row(spec, e.size)
        ctype = data.get("chamfer_type", "equal")
        n = len(e.points)
        d1 = float(data.get("distance", 1.0))
        if d1 <= 0:
            raise ValueError("a distance must be more than 0")
        first = _np.full(n, d1)
        if ctype == "two":
            d2 = float(data.get("distance2", d1))
            if d2 <= 0:
                raise ValueError("a distance must be more than 0")
            second = _np.full(n, d2)
        elif ctype == "angle":
            a = math.radians(float(data.get("angle", 45.0)))
            gamma = math.pi - e.turn
            far = _np.sin(gamma + a)
            if not 0.0 < a < math.pi or (a + gamma >= math.pi - 1e-9).any() or (far <= 1e-9).any():
                raise ValueError("the bevel never reaches the other face")
            second = d1 * math.sin(a) / far
        else:
            second = first
        if e.size.get("ref", 0) == 0:
            return first, second
        return second, first

    def points(self, spec):
        """(rows*cols) x 3 numpy array of every band's points for the sizes in `spec`, in
        global coordinates; ValueError when a size cannot make a band (0 or less)."""
        blocks = []
        for e in self.edges:
            if e.size["kind"] == "ball":
                r = self._radii(spec, e)
                pts = e.P[:, None, :] + r[:, None, None] * e.V
            else:
                a, b = self._distances(spec, e)
                pts = _np.stack([e.P + a[:, None] * e.I0, e.P + b[:, None] * e.I1], axis=1)
            for (origin, normal), rows in e.planes:
                o = _np.array(origin)
                m = _np.array(normal)
                sub = pts[rows]
                d = (sub - o) @ m
                along = e.T[rows] @ m
                ok = _np.abs(along) > 1e-9
                shift = _np.where((d < 0) & ok[:, None], d / _np.where(ok, along, 1.0)[:, None], 0.0)
                pts[rows] = sub - shift[:, :, None] * e.T[rows][:, None, :]
            blocks.append(pts.reshape(-1, 3))
        out = _np.concatenate(blocks, axis=0)
        return self._place(out)

    def _place(self, pts):
        if self.placement is None:
            return pts
        m = self.placement.toMatrix()
        a = _np.array(
            [
                (m.A11, m.A12, m.A13, m.A14),
                (m.A21, m.A22, m.A23, m.A24),
                (m.A31, m.A32, m.A33, m.A34),
            ],
            dtype=float,
        )
        return pts @ a[:, :3].T + a[:, 3]


def picture_of(feature):
    """(Picture in the feature's own coordinates, base shape) of an existing Fillet / Chamfer
    (FreeCAD's or SciForge's) at its sizes: the golden checks compare it with the result."""
    if fillet_sets.is_sets(feature):
        base, spec, flat, refs2, features, features2 = fillet_sets.read(feature)
        groups = fillet_core.split_refs(spec, flat)
    else:
        kind = blend.kind_of(feature)
        base, flat = blend.refs_of(feature)
        spec = fillet_core.default_spec(kind)
        spec["sets"][0].update(blend.read(feature))
        groups, refs2, features, features2 = [list(flat)], [], [], []
    info = blend.ShapeInfo(base.Shape)
    return Picture(info, spec, groups, refs2, features, features2), spec


class Overlay:
    """The live picture in the 3D view: the bands in the part's colour, the lines where they
    meet the faces dark, never picked. show() moves the points only (the triangles are set
    once per picture)."""

    NAME = "SciForgeBlendLive"

    def __init__(self, view, color=(0.8, 0.8, 0.8), line_color=(0.1, 0.1, 0.1)):
        from pivy import coin

        self.view = view
        self.picture = None
        self.root = coin.SoSeparator()
        self.root.setName(self.NAME)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        offset = coin.SoPolygonOffset()  # in front of the see-through faces it touches
        offset.factor = -1.0
        offset.units = -1.0
        self.root.addChild(offset)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        hints.shapeType = coin.SoShapeHints.UNKNOWN_SHAPE_TYPE  # lit from both sides
        hints.creaseAngle = 0.8  # a round shades smoothly
        self.root.addChild(hints)
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.specularColor.setValue(0.2, 0.2, 0.2)
        material.shininess = 0.3
        self.root.addChild(material)
        self.coords = coin.SoCoordinate3()
        self.root.addChild(self.coords)
        self.faces = coin.SoIndexedFaceSet()
        self.root.addChild(self.faces)
        lines = coin.SoSeparator()  # takes the coordinates above
        style = coin.SoDrawStyle()
        style.lineWidth = 2.0
        lines.addChild(style)
        line_material = coin.SoMaterial()
        line_material.diffuseColor.setValue(*line_color)
        line_material.emissiveColor.setValue(*line_color)
        lines.addChild(line_material)
        light = coin.SoLightModel()
        light.model = coin.SoLightModel.BASE_COLOR
        lines.addChild(light)
        self.line_set = coin.SoIndexedLineSet()
        lines.addChild(self.line_set)
        self.root.addChild(lines)
        self.shown = False
        self.spec = None

    def set_picture(self, picture):
        self.picture = picture
        index = []
        for a, b, c in picture.triangles:
            index += [a, b, c, -1]
        self.faces.coordIndex.setNum(0)
        if index:
            self.faces.coordIndex.setValues(0, len(index), index)
        lines = []
        for line in picture.lines:
            lines += list(line) + [-1]
        self.line_set.coordIndex.setNum(0)
        if lines:
            self.line_set.coordIndex.setValues(0, len(lines), lines)
        self.spec = None

    def show(self, spec):
        """Draw the bands for the sizes in `spec` (adds the node to the view the first time).
        ValueError when a size makes no band (the caller hides the picture)."""
        pts = self.picture.points(spec).tolist()
        self.coords.point.setNum(len(pts))
        if pts:
            self.coords.point.setValues(0, len(pts), pts)
        if not self.shown:
            self.view.getSceneGraph().addChild(self.root)
            self.shown = True
        self.spec = spec

    def hide(self):
        if not self.shown:
            return
        self.shown = False
        self.spec = None
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass  # the view went with its document
