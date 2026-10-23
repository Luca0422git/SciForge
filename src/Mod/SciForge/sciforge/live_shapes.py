# SPDX-License-Identifier: LGPL-2.1-or-later
"""Live pictures for Press Pull / Offset Face, Shell and Extrude: while their handle is
dragged, the faces that move follow every mouse move as a picture (a fraction of a
millisecond per move), and the exact solid is built only when the mouse rests or is let go
(taskui.Panel.schedule(settle=True)), as Draft does since 2026-10-22 (draft_live.py).

    OffsetPicture   Press Pull / Offset Face: the picked faces moved along their normals
                    (flat faces slide, cylinders and spheres change radius), their points on
                    the faces beside them sliding along those faces, and side quads between
                    the old and the new outline where material is added.
    ShellPicture    Shell: the kept faces offset inward (and / or outward) by the wall, the
                    opened faces' rims drawn as the ring between the outlines.
    ExtrudePicture  Extrude (distances, taper, thin wall, both sides / symmetric): the
                    profile's triangles at both ends and quads along its outline.

Each point moves along a straight line as the value changes (live_core.py): its start and
one or two directions are worked out once per set of picks, a mouse move only scales them.
Every picture is drawn by draft_live.Overlay (the part's colour with dark edges, never
picked, nodes the dialog owns). Live (below) keeps one per dialog: it hides the preview solid
while the picture shows, shows the part before the step see-through, and puts everything
back when the exact solid comes, at OK / Cancel / Undo, or when the value is refused.
"""

from . import live_core as core
from . import log, warn

try:  # FreeCAD ships numpy; the plain loop is the fallback
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None


def _tuple(v):
    return (float(v.x), float(v.y), float(v.z))


class Mesh:
    """Points that move with the values (start + a * A + b * B, a and b per group), their
    triangles and their polylines. Subclasses give coefficients(values) -> {group: (a, b)}."""

    def __init__(self, shape_size, placement=None):
        diag = max(float(shape_size), 1e-3)
        self.deflection = max(0.0015 * diag, 0.01)
        self.tol = max(1e-5, 1e-7 * diag)
        self.placement = placement
        self.points, self.pa, self.pb, self.pg = [], [], [], []
        self.line_points, self.la, self.lb, self.lg = [], [], [], []
        self.triangles = []
        self.lines = []  # point counts per polyline
        self._arrays = None

    # -- building -------------------------------------------------------------------------------
    def add_point(self, p, a, b=(0.0, 0.0, 0.0), group=0):
        self.points.append(p)
        self.pa.append(a)
        self.pb.append(b)
        self.pg.append(group)
        return len(self.points) - 1

    def add_line(self, items):
        """items: [(point, A, B, group)]."""
        if len(items) < 2:
            return
        for p, a, b, g in items:
            self.line_points.append(p)
            self.la.append(a)
            self.lb.append(b)
            self.lg.append(g)
        self.lines.append(len(items))

    def compile(self):
        if _np is None:
            return
        self._arrays = [
            (
                _np.array(self.points, dtype=float).reshape(-1, 3),
                _np.array(self.pa, dtype=float).reshape(-1, 3),
                _np.array(self.pb, dtype=float).reshape(-1, 3),
                _np.array(self.pg, dtype=int),
            ),
            (
                _np.array(self.line_points, dtype=float).reshape(-1, 3),
                _np.array(self.la, dtype=float).reshape(-1, 3),
                _np.array(self.lb, dtype=float).reshape(-1, 3),
                _np.array(self.lg, dtype=int),
            ),
        ]

    # -- moving ---------------------------------------------------------------------------------
    def coefficients(self, values):
        raise NotImplementedError

    def _table(self, values):
        coef = self.coefficients(values)
        size = max([0] + list(coef.keys())) + 1
        ta, tb = [0.0] * size, [0.0] * size
        for g, (a, b) in coef.items():
            ta[g], tb[g] = float(a), float(b)
        return ta, tb

    def points_at(self, values, _unused=None):
        """(face points, line points) for the values, in global coordinates (lists)."""
        ta, tb = self._table(values)
        if self._arrays is not None:
            out = []
            ca, cb = _np.array(ta), _np.array(tb)
            for p, a, b, g in self._arrays:
                if len(p) == 0:
                    out.append([])
                    continue
                q = p + ca[g][:, None] * a + cb[g][:, None] * b
                out.append(self._place_np(q).tolist())
            return out[0], out[1]
        faces = self._move_py(self.points, self.pa, self.pb, self.pg, ta, tb)
        lines = self._move_py(self.line_points, self.la, self.lb, self.lg, ta, tb)
        return self._place_py(faces), self._place_py(lines)

    @staticmethod
    def _move_py(points, pa, pb, pg, ta, tb):
        out = []
        for p, a, b, g in zip(points, pa, pb, pg):
            s, t = ta[g], tb[g]
            out.append(
                (p[0] + s * a[0] + t * b[0], p[1] + s * a[1] + t * b[1], p[2] + s * a[2] + t * b[2])
            )
        return out

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


# -- faces of a solid: normals, edges, what each point lies on -----------------------------------
class Faces:
    """Questions about the faces of one shape, answered once per face / edge / vertex."""

    def __init__(self, shape, deflection, tol):
        import Part

        self.shape = shape
        self.deflection = deflection
        self.tol = tol
        self._Face = Part.Face
        self._flat = {}
        self._edge_faces = {}
        self._vertex_faces = {}
        self._polylines = {}

    def key(self, shape):
        return (shape.hashCode(), str(shape.Orientation))

    def index(self, face):
        for i, f in enumerate(self.shape.Faces):
            if f.isSame(face):
                return i
        return None

    def flat_normal(self, face):
        """The outward normal of a flat face (one for all its points), else None."""
        k = self.key(face)
        if k in self._flat:
            return self._flat[k]
        normal = None
        if face.Surface.__class__.__name__ == "Plane":
            try:
                u0, u1, v0, v1 = face.ParameterRange
                normal = core.unit(_tuple(face.normalAt(0.5 * (u0 + u1), 0.5 * (v0 + v1))))
            except Exception:
                normal = None
        self._flat[k] = normal
        return normal

    def normal(self, face, p):
        flat = self.flat_normal(face)
        if flat is not None:
            return flat
        import FreeCAD as App

        try:
            u, v = face.Surface.parameter(App.Vector(*p))
            return core.unit(_tuple(face.normalAt(u, v)))
        except Exception:
            return None

    def faces_of_edge(self, edge):
        k = edge.hashCode()
        if k not in self._edge_faces:
            try:
                self._edge_faces[k] = list(self.shape.ancestorsOfType(edge, self._Face))
            except Exception:
                self._edge_faces[k] = []
        return self._edge_faces[k]

    def faces_of_vertex(self, vertex):
        k = vertex.hashCode()
        if k not in self._vertex_faces:
            try:
                self._vertex_faces[k] = list(self.shape.ancestorsOfType(vertex, self._Face))
            except Exception:
                self._vertex_faces[k] = []
        return self._vertex_faces[k]

    def polyline(self, edge):
        k = edge.hashCode()
        if k not in self._polylines:
            try:
                pts = [_tuple(q) for q in edge.discretize(Deflection=self.deflection)]
            except Exception:
                pts = []
            box = edge.BoundBox
            box.enlarge(self.deflection * 2.0 + self.tol * 10.0)
            self._polylines[k] = (pts, box)
        return self._polylines[k]

    def boundary(self, face):
        """[(edge, polyline, box, [vertex (point, faces)])] of a face."""
        out = []
        for edge in face.Edges:
            pts, box = self.polyline(edge)
            ends = [(_tuple(v.Point), v) for v in edge.Vertexes]
            out.append((edge, pts, box, ends))
        return out

    def on(self, p, face, bounds):
        """The faces point p (on `face`) lies on: itself, the faces across the edges it lies
        on, and every face of a vertex it sits at."""
        import FreeCAD as App

        found = [face]
        reach = self.deflection * 1.5 + self.tol * 10.0
        vec = None

        def take(faces):
            for f in faces:
                if not any(f.isSame(g) for g in found):
                    found.append(f)

        for edge, pts, box, ends in bounds:
            if vec is None:
                vec = App.Vector(*p)
            if not box.isInside(vec):
                continue
            at_vertex = False
            for q, vertex in ends:
                if core.norm(core.sub(p, q)) <= self.tol * 100.0:
                    take(self.faces_of_vertex(vertex))
                    at_vertex = True
            if at_vertex or core.near_polyline(p, pts, reach):
                take(self.faces_of_edge(edge))
        return found


# -- Press Pull / Offset Face --------------------------------------------------------------------
class OffsetPicture(Mesh):
    """Faces `names` of `shape` moved by the value along their outward normals; the faces beside
    them stay (the moved points slide along them). Side quads join the old and the new outline
    where no other moved face continues it; they show only while the value adds material
    (`grows`: values > 0)."""

    MOVE, BASE = 0, 1

    def __init__(self, shape, names, placement=None):
        super().__init__(shape.BoundBox.DiagonalLength, placement)
        self.info = Faces(shape, self.deflection, self.tol)
        self.moved = [shape.getElement(n) for n in names]
        if not self.moved:
            raise ValueError("no faces")
        self._build()
        self.compile()

    def _is_moved(self, face):
        return any(face.isSame(f) for f in self.moved)

    def _move_of(self, p, faces):
        rows = []
        for f in faces:
            n = self.info.normal(f, p)
            if n is not None:
                rows.append((n, 1.0 if self._is_moved(f) else 0.0))
        return core.offset_move(rows)

    def _build(self):
        done = []
        for face in self.moved:
            bounds = self.info.boundary(face)
            pts, tris = face.tessellate(self.deflection)
            base = len(self.points)
            for q in pts:
                p = _tuple(q)
                self.add_point(p, self._move_of(p, self.info.on(p, face, bounds)), group=self.MOVE)
            self.triangles += [(a + base, b + base, c + base) for a, b, c in tris]
            for edge, line, _box, _ends in bounds:
                if any(edge.isSame(e) for e in done) or len(line) < 2:
                    continue
                done.append(edge)
                moves = [self._move_of(p, self.info.on(p, face, bounds)) for p in line]
                self.add_line([(p, w, (0.0, 0.0, 0.0), self.MOVE) for p, w in zip(line, moves)])
                others = [f for f in self.info.faces_of_edge(edge) if not f.isSame(face)]
                if any(self._is_moved(f) for f in others):
                    continue  # two moved faces meet here: no side
                first_old = len(self.points)
                for p, w in zip(line, moves):
                    self.add_point(p, w, group=self.BASE)
                first_new = len(self.points)
                for p, w in zip(line, moves):
                    self.add_point(p, w, group=self.MOVE)
                self.triangles += core.strip(len(line), first_old, first_new)

    def coefficients(self, values):
        d = float(values["distance"])
        # the side quads only where material is added; else folded flat onto the moved face
        return {self.MOVE: (d, 0.0), self.BASE: (0.0 if d > 0 else d, 0.0)}


# -- Shell ------------------------------------------------------------------------------------------
class ShellPicture(Mesh):
    """The walls of a Shell: every face of `shape` but the opened ones (`names`) offset by the
    inside wall inward and / or by the outside wall outward (`direction`). The rim of each
    opened face is the ring between the two outlines. Curved faces are offset point by point
    along their normals (exact for cylinders and spheres)."""

    INNER, OUTER, ZERO = 0, 1, 2

    def __init__(self, shape, names, direction="inside", placement=None):
        super().__init__(shape.BoundBox.DiagonalLength, placement)
        self.info = Faces(shape, self.deflection, self.tol)
        self.direction = direction
        self.opened = [shape.getElement(n.lstrip("?")) for n in names]
        self.kept = [f for f in shape.Faces if not any(f.isSame(o) for o in self.opened)]
        self.walls = []
        if direction in ("inside", "both"):
            self.walls.append(self.INNER)
        if direction in ("outside", "both"):
            self.walls.append(self.OUTER)
        if not self.walls:
            raise ValueError("no wall")
        self._build()
        self.compile()

    def _is_opened(self, face):
        return any(face.isSame(f) for f in self.opened)

    def _move_of(self, p, faces):
        rows = []
        for f in faces:
            n = self.info.normal(f, p)
            if n is not None:
                rows.append((n, 0.0 if self._is_opened(f) else 1.0))
        return core.offset_move(rows)

    def _build(self):
        done = []
        for face in self.kept:
            bounds = self.info.boundary(face)
            pts, tris = face.tessellate(self.deflection)
            moves = [self._move_of(_tuple(q), self.info.on(_tuple(q), face, bounds)) for q in pts]
            for wall in self.walls:
                base = len(self.points)
                for q, w in zip(pts, moves):
                    self.add_point(_tuple(q), w, group=wall)
                self.triangles += [(a + base, b + base, c + base) for a, b, c in tris]
            for edge, line, _box, _ends in bounds:
                if any(edge.isSame(e) for e in done) or len(line) < 2:
                    continue
                done.append(edge)
                lmoves = [self._move_of(p, self.info.on(p, face, bounds)) for p in line]
                for wall in self.walls:
                    self.add_line([(p, w, (0.0, 0.0, 0.0), wall) for p, w in zip(line, lmoves)])
                others = self.info.faces_of_edge(edge)
                if not any(self._is_opened(f) for f in others):
                    continue
                # the rim: between the inner and the outer outline (the part's own edge when
                # the wall is on one side only)
                low = self.INNER if self.INNER in self.walls else self.ZERO
                high = self.OUTER if self.OUTER in self.walls else self.ZERO
                first_a = len(self.points)
                for p, w in zip(line, lmoves):
                    self.add_point(p, w, group=low)
                first_b = len(self.points)
                for p, w in zip(line, lmoves):
                    self.add_point(p, w, group=high)
                self.triangles += core.strip(len(line), first_a, first_b)

    def coefficients(self, values):
        return {
            self.INNER: (-float(values.get("inside", 0.0)), 0.0),
            self.OUTER: (float(values.get("outside", 0.0)), 0.0),
            self.ZERO: (0.0, 0.0),
        }


# -- Extrude ------------------------------------------------------------------------------------------
class ExtrudePicture(Mesh):
    """The extrusion of flat profile faces (global coordinates) along `normal`: each face's
    triangles at both ends, quads along its outline between them, and the outline's corners
    as lines. A taper moves the outline inward in the profile's plane (live_core)."""

    END0, END1 = 0, 1

    def __init__(self, faces, normal):
        import Part

        size = Part.makeCompound(faces).BoundBox.DiagonalLength if faces else 1.0
        super().__init__(size, None)
        if not faces:
            raise ValueError("no profile")
        self.normal = core.unit(_tuple(normal))
        for face in faces:
            self._face(face)
        self.compile()

    def _outward(self, face, edge):
        """A function p -> the outline's in-plane outward normal at p on this edge."""
        import FreeCAD as App

        n = self.normal

        def raw(p):
            try:
                u = edge.Curve.parameter(App.Vector(*p))
                t = _tuple(edge.tangentAt(u))
            except Exception:
                a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
                t = _tuple(b - a)
            return core.unit(core.cross(t, n))

        mid = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
        m = raw(_tuple(mid))
        step = max(self.tol * 100.0, self.deflection)
        probe = App.Vector(*core.add(_tuple(mid), core.scale(m, step)))
        sign = 1.0
        try:
            if face.isInside(probe, self.tol, True):
                sign = -1.0
        except Exception:
            pass
        return lambda p: core.scale(raw(p), sign)

    def _face(self, face):
        n = self.normal
        edges = []
        for edge in face.Edges:
            try:
                line = [_tuple(q) for q in edge.discretize(Deflection=self.deflection)]
            except Exception:
                continue
            if len(line) < 2:
                continue
            box = edge.BoundBox
            box.enlarge(self.deflection * 2.0 + self.tol * 10.0)
            ends = [_tuple(v.Point) for v in edge.Vertexes]
            edges.append((edge, line, box, ends, self._outward(face, edge)))
        reach = self.deflection * 1.5 + self.tol * 10.0

        def inset(p):
            import FreeCAD as App

            ms = []
            vec = App.Vector(*p)
            for edge, line, box, ends, outward in edges:
                if not box.isInside(vec):
                    continue
                at_end = any(core.norm(core.sub(p, q)) <= self.tol * 100.0 for q in ends)
                if at_end or core.near_polyline(p, line, reach):
                    ms.append(outward(p))
            if not ms:
                return (0.0, 0.0, 0.0)
            return core.in_plane_move(ms, n)

        pts, tris = face.tessellate(self.deflection)
        pts = [_tuple(q) for q in pts]
        moves = [inset(p) for p in pts]
        # the ends: the second one's triangles turned (both face outward)
        for group, flip in ((self.END0, True), (self.END1, False)):
            base = len(self.points)
            for p, w in zip(pts, moves):
                self.add_point(p, n, w, group)
            for a, b, c in tris:
                self.triangles.append(
                    (a + base, c + base, b + base) if flip else (a + base, b + base, c + base)
                )
        for edge, line, _box, _ends, _outward in edges:
            moves = [inset(p) for p in line]
            first0 = len(self.points)
            for p, w in zip(line, moves):
                self.add_point(p, n, w, self.END0)
            first1 = len(self.points)
            for p, w in zip(line, moves):
                self.add_point(p, n, w, self.END1)
            self.triangles += core.strip(len(line), first0, first1)
            self.add_line([(p, n, w, self.END0) for p, w in zip(line, moves)])
            self.add_line([(p, n, w, self.END1) for p, w in zip(line, moves)])
            p, w = line[0], moves[0]
            self.add_line([(p, n, w, self.END0), (p, n, w, self.END1)])

    def coefficients(self, values):
        """values: {"ends": [(position, inset), (position, inset)]} (ExtrudePanel._live_values):
        the position of each end along the normal and how far its outline moves inward."""
        (a0, i0), (a1, i1) = values["ends"]
        return {self.END0: (a0, -i0), self.END1: (a1, -i1)}


def extrude_ends(options, start=0.0):
    """[(position, inset)] of the two ends of an extrude with these (built) options, along the
    profile's normal times sign (see ExtrudePanel._live_picture)."""
    direction = options["direction"]
    ends = core.extrude_ends(
        direction,
        options["distance"],
        options.get("distance2", 0.0),
        options.get("measurement", "whole"),
        0.0,
    )
    (p0, l0), (p1, l1) = ends
    if direction == "symmetric":
        t0 = t1 = float(options.get("taper", 0.0))
    elif direction == "two_sides":
        t0, t1 = float(options.get("taper2", 0.0)), float(options.get("taper", 0.0))
    else:
        t0, t1 = 0.0, float(options.get("taper", 0.0))
    if direction != "symmetric":
        # the side is measured from the profile whichever way it goes (the sign is in the
        # picture's normal)
        p1 = abs(p1)
        p0 = -abs(p0)
    return [(start + p0, core.taper_inset(l0, t0)), (start + p1, core.taper_inset(l1, t1))]


# -- in the 3D view ------------------------------------------------------------------------------------
class Live:
    """One dialog's live picture: made once per set of picks (key), shown for values, hidden
    with everything put back. `looks`: a pickpanel.Looks to ghost the part with (the dialog's
    own, kept by it), else one of its own (restored on hide)."""

    def __init__(self, name, looks=None):
        self.name = name
        self.overlay = None
        self.key = None
        self.failed = None
        self.values = None
        self._own_looks = looks is None
        if looks is None:
            from . import pickpanel

            looks = pickpanel.Looks()
        self.looks = looks
        self._visible = []  # (view object, shown before) changed while the picture shows
        self.hid = False

    @property
    def shown(self):
        return self.overlay is not None and self.overlay.shown

    def ready(self, key):
        return self.overlay is not None and self.key == key

    def prepare(self, key, make, color=(0.8, 0.8, 0.8), line=(0.1, 0.1, 0.1)):
        """The Overlay with the pictures for `key` (made by make() once), or None."""
        if key is None or key == self.failed:
            return None
        if self.overlay is not None and getattr(self, "_colors", None) != (color, line):
            self.overlay.hide()  # another colour (an extrude turned into a cut): a new one
            self.overlay = None
            self.key = None
        if self.overlay is not None and self.key == key:
            return self.overlay
        try:
            pictures = make()
            if not pictures:
                raise ValueError("nothing to show")
            if self.overlay is None:
                import FreeCADGui as Gui

                from . import draft_live

                class _Overlay(draft_live.Overlay):
                    NAME = "SciForgeLiveShape"

                self.overlay = _Overlay(Gui.ActiveDocument.ActiveView, color, line)
                self._colors = (color, line)
            self.overlay.hide()
            self.overlay.set_pictures(pictures)
            self.key = key
            return self.overlay
        except Exception as exc:
            self.failed = key
            self.key = None
            if self.overlay is not None:
                self.overlay.hide()
            log("%s: no live picture here (%s); the preview follows on pauses" % (self.name, exc))
            return None

    def show(self, key, make, values, hide=(), ghost=(), color=None, line=None):
        """Show the picture of `key` at `values`; the objects of `hide` out of sight, those of
        `ghost` shown see-through. False when there is no picture (nothing changed)."""
        kwargs = {}
        if color is not None:
            kwargs["color"] = color
        if line is not None:
            kwargs["line"] = line
        overlay = self.prepare(key, make, **kwargs)
        if overlay is None:
            self.hide()
            return False
        overlay.show(values)
        self.values = values
        self._out_of_the_way(hide, ghost)
        return True

    def _out_of_the_way(self, hide, ghost):
        if self.hid:
            return
        from . import pickpanel

        self.hid = True
        for obj in hide:
            vobj = getattr(obj, "ViewObject", None) if pickpanel.alive(obj) else None
            if vobj is None:
                continue
            self._visible.append((vobj, bool(vobj.isShow())))
            vobj.makeTemporaryVisible(False)
        for obj in ghost:
            vobj = getattr(obj, "ViewObject", None) if pickpanel.alive(obj) else None
            if vobj is None:
                continue
            self._visible.append((vobj, bool(vobj.isShow())))
            vobj.makeTemporaryVisible(True)
            if not self.looks.done("ghost:" + obj.Name):
                for node in pickpanel.nodes(vobj.RootNode, "SoMaterial"):
                    if node.getName().getString() == "ShapeMaterial":
                        self.looks.set(node, "transparency", pickpanel.GHOST / 100.0)

    def hide(self):
        """The picture away and the view as it was before it showed."""
        if self.overlay is not None:
            try:
                self.overlay.hide()
            except Exception:
                pass
        self.values = None
        if not self.hid:
            return
        self.hid = False
        visible, self._visible = self._visible, []
        for vobj, before in reversed(visible):
            try:
                vobj.makeTemporaryVisible(before)
            except Exception:
                pass  # the object went (its document closed)
        if self._own_looks:
            try:
                self.looks.restore()
            except Exception as exc:
                warn("%s live picture: %s" % (self.name, exc))

    def drop(self):
        self.hide()
        self.overlay = None
        self.key = None


def colors(obj):
    """(face colour, edge colour) of a part, for its live picture."""
    face, line = (0.8, 0.8, 0.8), (0.1, 0.1, 0.1)
    try:
        vobj = obj.ViewObject
        try:
            face = tuple(vobj.ShapeAppearance[0].DiffuseColor[:3])
        except Exception:
            face = tuple(vobj.ShapeColor[:3])
        line = tuple(vobj.LineColor[:3])
    except Exception:
        pass
    return face, line


CUT_COLOR = (0.85, 0.25, 0.2)  # a cut's picture: the material taken away (as cut_preview)


class LivePanel:
    """What a task dialog adds to show a live picture while its handle is dragged. The
    dialog gives live_key() (what the picture depends on besides the values; None: no
    picture), live_make() (the pictures), live_values(), and the objects to hide / show
    see-through while the picture shows; it calls live_show() on every drag step (then
    schedule(settle=True)), live_hide() once the exact solid is built, live_drop() in
    cleanup(). Nothing here lets an exception out."""

    LIVE_NAME = "Live picture"

    # -- what the dialog gives ------------------------------------------------------------------
    def live_key(self):
        return None

    def live_make(self):
        return []

    def live_values(self):
        return {}

    def live_hide_objects(self):
        return []

    def live_ghost_objects(self):
        return []

    def live_colors(self):
        return None, None

    def live_looks(self):
        return None

    def live_shown(self, values):
        """Called each time the picture shows new values (tests check it)."""

    # -- the picture ----------------------------------------------------------------------------
    def live_view(self):
        live = self.__dict__.get("_live_view")
        if live is None:
            live = Live(self.LIVE_NAME, self.live_looks())
            self._live_view = live
        return live

    def live_show(self):
        """The picture at the dialog's values now; False when there is none (the exact
        solid then follows as before)."""
        if getattr(self, "_closed", False):
            return False
        try:
            key = self.live_key()
            live = self.live_view()
            if key is None:
                live.hide()
                return False
            color, line = self.live_colors()
            values = self.live_values()
            if not live.show(
                key,
                self.live_make,
                values,
                self.live_hide_objects(),
                self.live_ghost_objects(),
                color,
                line,
            ):
                return False
            self.live_shown(values)
            return True
        except Exception as exc:
            self.live_drop()
            warn("%s: %s" % (self.LIVE_NAME, exc))
            return False

    def live_hide(self):
        live = self.__dict__.get("_live_view")
        if live is None:
            return
        try:
            live.hide()
        except Exception as exc:
            warn("%s: %s" % (self.LIVE_NAME, exc))

    def live_drop(self):
        live = self.__dict__.pop("_live_view", None)
        if live is None:
            return
        try:
            live.drop()
        except Exception as exc:
            warn("%s: %s" % (self.LIVE_NAME, exc))

    def live_soon(self):
        """Make the picture of the picks now while nothing happens, so the first move of the
        handle does not wait for it."""
        try:
            from .compat import QtCore

            QtCore.QTimer.singleShot(0, self._live_prepare)
        except Exception:
            pass

    def _live_prepare(self):
        try:
            if getattr(self, "_closed", False) or getattr(self.doc, "Recomputing", False):
                return
            key = self.live_key()
            live = self.live_view()
            if key is not None and not live.ready(key):
                color, line = self.live_colors()
                kwargs = {}
                if color is not None:
                    kwargs["color"] = color
                if line is not None:
                    kwargs["line"] = line
                live.prepare(key, self.live_make, **kwargs)
        except Exception as exc:
            warn("%s: %s" % (self.LIVE_NAME, exc))
