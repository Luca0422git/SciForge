# SPDX-License-Identifier: LGPL-2.1-or-later
"""Draft's live picture: the drafted faces following the angle handle on every mouse move,
in a few milliseconds, while the exact solid is built only when the mouse rests or is let go
(draft_ui.DraftPanel; Luca, 2026-10-22: "The whole point of being able to drag the angle of
a draft is to see it update in real time").

Picture(shape, names, spec) prepares the picked faces once per set of picks (their triangles
and edges, the height of every point above the hinge, how the shifts of the faces it lies on
move it: draft_live_core.py); points(angle, angle2) moves them for an angle (numpy when it is
there). Overlay draws them over the see-through part before the step, in the part's own
colour with its edges, never pickable: Coin nodes the dialog owns, so nothing stays behind.

The picture is the faces turned about their hinges, with their tops and bottoms kept at their
heights: what the exact draft makes of side walls between flat tops and bottoms (OpenCASCADE's
draft for flat and round faces, draft_walls.py for the others). Where the exact draft does
something else (a wall ending on a slanted face) the picture is close, and the exact solid
replaces it as soon as the mouse rests.
"""

import math

from . import draft_live_core as core

try:  # FreeCAD ships numpy; the plain loop is the fallback
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None


def _tuple(v):
    return (float(v.x), float(v.y), float(v.z))


class Picture:
    """The drafted faces of one body for one set of picks and options (not the angles)."""

    def __init__(self, shape, names, spec, placement=None, deflection=None):
        import Part

        self.pull = core.unit(_tuple(spec["pull"]))
        self.sides = spec.get("sides", "one")
        self.kind = spec.get("type", "fixed")
        self.bends = core.splits(self.sides, self.kind)
        self.placement = placement
        diag = max(shape.BoundBox.DiagonalLength, 1e-3)
        self.deflection = deflection or max(0.0015 * diag, 0.01)
        self.tol = max(1e-5, 1e-7 * diag)
        self._plane = None
        self._curves = None
        if spec.get("plane") is not None:
            origin, normal = spec["plane"]
            normal = core.unit(_tuple(normal))
            denom = core.dot(normal, self.pull)
            if abs(denom) < 1e-9:
                raise ValueError("the hinge plane runs along the pull direction")
            self._plane = (_tuple(origin), normal, denom)
        elif spec.get("curves") is not None:
            self._curves = spec["curves"]
            self._vertex = Part.Vertex
        else:
            raise ValueError("no hinge")
        faces = []
        for name in names:
            faces.append(shape.getElement(name))
        self.drafted = faces
        # every face sharing an edge with a drafted face: (face, drafted?)
        self._edge_faces = {}
        # the points: position, height, terms [(weight (3), tb, drafted)]
        self.points, self.heights, self.terms = [], [], []
        self.triangles = []
        self.line_points, self.line_heights, self.line_terms = [], [], []
        self.lines = []  # point counts per polyline
        self._prepare(shape)
        self._compile()

    # -- heights and normals ------------------------------------------------------------------
    def height(self, p):
        if self._plane is not None:
            origin, normal, denom = self._plane
            return core.dot(core.sub(p, origin), normal) / denom
        import FreeCAD as App

        _d, pairs, _info = self._curves.distToShape(self._vertex(App.Vector(*p)))
        near = _tuple(pairs[0][0])
        return core.dot(core.sub(p, near), self.pull)

    @staticmethod
    def _normal(face, point, plane_normal=None):
        if plane_normal is not None:
            return plane_normal
        import FreeCAD as App

        try:
            u, v = face.Surface.parameter(App.Vector(*point))
            return _tuple(face.normalAt(u, v))
        except Exception:
            return None

    def _flat_normal(self, face):
        """The outward normal of a flat face (one for all its points), else None; kept per
        face (asked for every point of the face and of the faces beside it)."""
        try:
            key = (face.hashCode(), str(face.Orientation))
        except Exception:
            key = None
        cache = self.__dict__.setdefault("_flat", {})
        if key is not None and key in cache:
            return cache[key]
        normal = None
        if face.Surface.__class__.__name__ == "Plane":
            try:
                u0, u1, v0, v1 = face.ParameterRange
                normal = _tuple(face.normalAt(0.5 * (u0 + u1), 0.5 * (v0 + v1)))
            except Exception:
                normal = None
        if key is not None:
            cache[key] = normal
        return normal

    def _is_drafted(self, face):
        return any(face.isSame(f) for f in self.drafted)

    def _neighbours(self, shape, face):
        """[(edge, [other faces on it])] of a face."""
        found = []
        for edge in face.Edges:
            others = []
            try:
                for other in shape.ancestorsOfType(edge, __import__("Part").Face):
                    if not other.isSame(face):
                        others.append(other)
            except Exception:
                pass
            found.append((edge, others))
        return found

    def _terms(self, p, own, normals_faces):
        """The weighted terms of a point on `own` (drafted) and the faces of `normals_faces`
        [(face, normal)] it also lies on."""
        entries = [(own, self._normal(own, p, self._flat_normal(own)))]
        entries += normals_faces
        entries = [(f, n) for f, n in entries if n is not None]
        normals = [n for _f, n in entries]
        weights = core.solve(normals, self.pull)
        out = []
        for (face, normal), w in zip(entries, weights):
            if abs(w[0]) + abs(w[1]) + abs(w[2]) < 1e-15:
                continue
            drafted = face is own or self._is_drafted(face)
            out.append((w, core.lean_tan(normal, self.pull) if drafted else 0.0, drafted))
        return out

    def _beside(self, p, sides, others):
        """[(face, its outward normal at p)] of the faces beside the drafted one that point p
        also lies on: `others` (the faces of the edge it is on) and the faces across the
        upright edges it touches (a corner of the face: the top corner of a box's side lies on
        the next side too)."""
        found = list(others)
        for a, direction, length, faces in sides:
            rel = core.sub(p, a)
            t = core.dot(rel, direction)
            if t < -self.tol or t > length + self.tol:
                continue
            off = core.sub(rel, core.scale(direction, t))
            if core.dot(off, off) > self.tol * self.tol * 100.0:
                continue
            for other in faces:
                if not any(other.isSame(f) for f in found):
                    found.append(other)
        return [(o, self._normal(o, p, self._flat_normal(o))) for o in found]

    def _prepare(self, shape):
        done_edges = []
        for face in self.drafted:
            neighbours = self._neighbours(shape, face)
            # straight edges that run up the face (the corners with the faces beside it)
            sides = []
            for edge, others in neighbours:
                if edge.Curve.__class__.__name__ not in ("Line", "LineSegment") or not others:
                    continue
                a = _tuple(edge.Vertexes[0].Point)
                b = _tuple(edge.Vertexes[-1].Point)
                d = core.sub(b, a)
                length = math.sqrt(core.dot(d, d))
                if length < 1e-9 or abs(core.dot(core.scale(d, 1.0 / length), self.pull)) < 1e-6:
                    continue  # a top / bottom edge: nothing beside it moves across
                sides.append((a, core.scale(d, 1.0 / length), length, others))
            points, triangles = face.tessellate(self.deflection)
            base = len(self.points)
            heights = []
            for q in points:
                p = _tuple(q)
                beside = self._beside(p, sides, [])
                h = self.height(p)
                heights.append(h)
                self.points.append(p)
                self.heights.append(h)
                self.terms.append(self._terms(p, face, beside))
            tris = [tuple(t) for t in triangles]
            if self.bends:
                made, tris = core.split_triangles(heights, tris)
                for i, j, t in made:
                    self.points.append(core.lerp(self.points[base + i], self.points[base + j], t))
                    self.heights.append(0.0)  # on the hinge: it does not move
                    self.terms.append([])
            self.triangles += [(a + base, b + base, c + base) for a, b, c in tris]
            # the face's edges (each once)
            for edge, others in neighbours:
                if any(edge.isSame(e) for e in done_edges):
                    continue
                done_edges.append(edge)
                try:
                    line = [_tuple(q) for q in edge.discretize(Deflection=self.deflection)]
                except Exception:
                    continue
                if len(line) < 2:
                    continue
                hs = [self.height(p) for p in line]
                recipe = core.split_line(hs) if self.bends else [(k, k, 0.0) for k in range(len(line))]
                count = 0
                for i, j, t in recipe:
                    if i == j:
                        p = line[i]
                        beside = self._beside(p, sides, others)
                        self.line_points.append(p)
                        self.line_heights.append(hs[i])
                        self.line_terms.append(self._terms(p, face, beside))
                    else:
                        self.line_points.append(core.lerp(line[i], line[j], t))
                        self.line_heights.append(0.0)
                        self.line_terms.append([])
                    count += 1
                self.lines.append(count)

    # -- moving the points ------------------------------------------------------------------------
    def _compile(self):
        """numpy arrays of the points and their terms (when numpy is there)."""
        self._arrays = None
        if _np is None:
            return
        self._arrays = [
            self._pack(self.points, self.heights, self.terms),
            self._pack(self.line_points, self.line_heights, self.line_terms),
        ]

    @staticmethod
    def _pack(points, heights, terms):
        idx, w, tb, dr = [], [], [], []
        for i, items in enumerate(terms):
            for weight, lean, drafted in items:
                idx.append(i)
                w.append(weight)
                tb.append(lean)
                dr.append(1.0 if drafted else 0.0)
        return {
            "p": _np.array(points, dtype=float).reshape(-1, 3),
            "h": _np.array(heights, dtype=float),
            "idx": _np.array(idx, dtype=int),
            "w": _np.array(w, dtype=float).reshape(-1, 3),
            "tb": _np.array(tb, dtype=float),
            "dr": _np.array(dr, dtype=float),
        }

    def _k(self, tb, below, angle, angle2):
        return core.k_factor(angle, tb, self.sides, self.kind, below, angle2)

    def _move_np(self, pack, angle, angle2):
        p, h = pack["p"], pack["h"]
        out = p.copy()
        if len(pack["idx"]) == 0:
            return out
        idx = pack["idx"]
        hi = h[idx]
        tb = pack["tb"]
        ta = math.tan(math.radians(angle))
        k_above = ta - tb
        if self.sides == "one" and self.kind == "fixed":
            k_below = k_above
        elif self.sides == "one":
            k_below = _np.zeros_like(tb)
        else:
            other = angle if self.sides == "symmetric" or angle2 is None else angle2
            k_below = -(math.tan(math.radians(other)) + tb)
        k = _np.where(hi < 0.0, k_below, k_above) * pack["dr"]
        moves = pack["w"] * (-hi * k)[:, None]
        _np.add.at(out, idx, moves)
        return out

    def _move_py(self, points, heights, terms, angle, angle2):
        out = []
        for p, h, items in zip(points, heights, terms):
            dx = dy = dz = 0.0
            for w, tb, drafted in items:
                if not drafted:
                    continue
                s = -h * self._k(tb, h < 0.0, angle, angle2)
                dx += w[0] * s
                dy += w[1] * s
                dz += w[2] * s
            out.append((p[0] + dx, p[1] + dy, p[2] + dz))
        return out

    def points_at(self, angle, angle2=None):
        """(face points, line points) at the angles, in global coordinates, as lists of
        (x, y, z)."""
        if self._arrays is not None:
            faces = self._move_np(self._arrays[0], angle, angle2)
            lines = self._move_np(self._arrays[1], angle, angle2)
            faces, lines = self._place_np(faces), self._place_np(lines)
            return faces.tolist(), lines.tolist()
        faces = self._move_py(self.points, self.heights, self.terms, angle, angle2)
        lines = self._move_py(self.line_points, self.line_heights, self.line_terms, angle, angle2)
        return self._place_py(faces), self._place_py(lines)

    def _matrix(self):
        if self.placement is None:
            return None
        m = self.placement.toMatrix()
        return (
            (m.A11, m.A12, m.A13, m.A14),
            (m.A21, m.A22, m.A23, m.A24),
            (m.A31, m.A32, m.A33, m.A34),
        )

    def _place_np(self, pts):
        m = self._matrix()
        if m is None or len(pts) == 0:
            return pts
        a = _np.array(m, dtype=float)
        return pts @ a[:, :3].T + a[:, 3]

    def _place_py(self, pts):
        m = self._matrix()
        if m is None:
            return pts
        return [
            (
                m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
                m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
                m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
            )
            for x, y, z in pts
        ]


class Overlay:
    """The live picture in the 3D view: the faces of one or more Pictures, in the part's colour
    with dark edges, over the see-through part, never picked. show() moves the points only
    (the triangles are set once per set of pictures)."""

    NAME = "SciForgeDraftLive"

    def __init__(self, view, color=(0.8, 0.8, 0.8), line_color=(0.1, 0.1, 0.1)):
        from pivy import coin

        self.view = view
        self.pictures = []
        self.root = coin.SoSeparator()
        self.root.setName(self.NAME)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        offset = coin.SoPolygonOffset()  # in front of the see-through faces it lies on
        offset.factor = -1.0
        offset.units = -1.0
        self.root.addChild(offset)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        hints.shapeType = coin.SoShapeHints.UNKNOWN_SHAPE_TYPE  # lit from both sides
        hints.creaseAngle = 0.6  # round walls shade smoothly, corners stay sharp
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
        lines = coin.SoSeparator()
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
        self.line_coords = coin.SoCoordinate3()
        lines.addChild(self.line_coords)
        self.line_set = coin.SoLineSet()
        lines.addChild(self.line_set)
        self.root.addChild(lines)
        self.shown = False
        self.angles = None

    def set_pictures(self, pictures):
        """The pictures to draw (their triangles and lines; the points come with show())."""
        self.pictures = list(pictures)
        index, counts, base = [], [], 0
        for pic in self.pictures:
            for a, b, c in pic.triangles:
                index += [a + base, b + base, c + base, -1]
            base += len(pic.points)
            counts += list(pic.lines)
        self.faces.coordIndex.setNum(0)
        if index:
            self.faces.coordIndex.setValues(0, len(index), index)
        self.line_set.numVertices.setNum(0)
        if counts:
            self.line_set.numVertices.setValues(0, len(counts), counts)
        self.angles = None

    def show(self, angle, angle2=None):
        """Draw the pictures at the angles (adds the node to the view the first time)."""
        faces, lines = [], []
        for pic in self.pictures:
            f, l = pic.points_at(angle, angle2)
            faces += f
            lines += l
        self.coords.point.setNum(len(faces))
        if faces:
            self.coords.point.setValues(0, len(faces), faces)
        self.line_coords.point.setNum(len(lines))
        if lines:
            self.line_coords.point.setValues(0, len(lines), lines)
        if not self.shown:
            self.view.getSceneGraph().addChild(self.root)
            self.shown = True
        self.angles = (angle, angle2)

    def hide(self):
        if not self.shown:
            return
        self.shown = False
        self.angles = None
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass  # the view went with its document
