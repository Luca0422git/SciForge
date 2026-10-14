# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Emboss as a step in the body's timeline. No GUI code: the Emboss dialog
(emboss_ui.py) and the golden-model builder both use this module.

What it does: the picked sketch profiles (closed sketch areas, or whole texts) are laid
onto the picked faces of the body and raised out of them (Emboss) or sunk into them
(Deboss) by the Depth, along the face.

  flat faces        the profile is laid flat on the face
  cylinders, cones  the profile is wrapped round, like a label: a cylinder or a cone can
                    be unrolled flat, so letters keep their size and shape (emboss_core)
  other faces       (a sphere, a freeform face) Fusion refuses them; SciForge projects the
                    profile onto them along the sketch's direction and says so: letters
                    stretch where the face is steep

Where the profile lands: the line through the middle of the profiles along the sketch's
normal meets the face there (else the nearest point of the face). The profile's own axes
are turned onto the face at that point; Horizontal / Vertical Distance move it along
them and Rotation Angle turns it, all on the face.

How it is built (OpenCASCADE through FreeCAD's Part module): every edge of a profile
becomes a curve in the face's parameter plane (exact for flat faces and cylinders, which
unroll by a linear map; followed through points for cones and projected faces), the
curves make a face on the surface, and that face is thickened along the surface normal
(makeOffsetShape with fill). The raised letters start a hair (EPS) inside the part so
they join cleanly; a deboss's cut starts a hair outside it.

The feature is a PartDesign::FeaturePython (SciForgeType "Emboss"): later steps build on
it, editing earlier steps recomputes it, it shows in the timeline and its dialog opens
with a double-click there. Saved documents store "sciforge.emboss.EmbossFeature": keep
the name and the properties stable.
"""

import json
import math

import FreeCAD as App

from . import emboss_core as core
from . import extrude, warn

TYPE = "PartDesign::FeaturePython"
KIND = "Emboss"
META = "SciForgeEmboss"
TOL = 1e-7
EFFECT_NAMES = {"emboss": "Emboss", "deboss": "Deboss"}


class EmbossError(core.EmbossError):
    """The emboss cannot be made; the message says why and what to try."""


def is_emboss(obj):
    try:
        return obj is not None and obj.TypeId == TYPE and getattr(obj, "SciForgeType", "") == KIND
    except Exception:
        return False


# -- profiles -----------------------------------------------------------------------------------
def _is_text(obj):
    return getattr(obj, "SciForgeType", "") == "SketchText"


def profile_frame(profiles, body):
    """(faces, origin, normal, x axis, y axis) of the profiles in `body`'s coordinates:
    the faces to wrap and the profile's own axes (its sketch's) at the middle of them."""
    if not profiles:
        raise EmbossError("Pick a sketch profile: click inside a closed sketch area or a text.")
    to_body = body.getGlobalPlacement().inverse() if body is not None else App.Placement()
    faces = []
    for obj, sub in profiles:
        try:
            found = extrude.local_faces(obj, sub)
        except Exception as exc:
            raise EmbossError("%s cannot be used: %s" % (obj.Label, exc))
        for face in found:
            face = extrude._to_global(face, obj).copy()
            face.transformShape(to_body.toMatrix())
            faces.append(face)
    if not faces:
        raise EmbossError(
            "The picked profile has no closed area. Close the sketch's outline, or use a font "
            "that is not a single-line one."
        )
    first = profiles[0][0]
    if extrude.is_sketch(first) or _is_text(first):
        rotation = to_body.Rotation.multiply(first.getGlobalPlacement().Rotation)
    else:
        rotation = App.Rotation(App.Vector(0, 0, 1), extrude.face_normal(faces[0]))
    normal = rotation.multVec(App.Vector(0, 0, 1))
    x_axis = rotation.multVec(App.Vector(1, 0, 0))
    y_axis = rotation.multVec(App.Vector(0, 1, 0))
    box = faces[0].BoundBox
    for face in faces[1:]:
        box.add(face.BoundBox)
    origin = App.Vector(box.Center)
    # (the middle of the box lies in the profiles' plane)
    for face in faces:
        if abs(face_normal_at_middle(face).dot(normal)) < 1.0 - 1e-6:
            raise EmbossError("All profiles must lie in one sketch plane.")
    return faces, origin, normal, x_axis, y_axis


def face_normal_at_middle(face):
    try:
        u0, u1, v0, v1 = face.ParameterRange
        return face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    except Exception:
        return App.Vector(0, 0, 1)


# -- the faces to emboss on ------------------------------------------------------------------------
def surface_kind(face):
    try:
        return core.kind_of(face.Surface.TypeId)
    except Exception:
        return "other"


def _same_surface(a, b, tol=1e-6):
    """True if two faces lie on the same plane / cylinder / cone."""
    sa, sb = a.Surface, b.Surface
    kind = core.kind_of(sa.TypeId)
    if kind != core.kind_of(sb.TypeId):
        return False
    try:
        if kind == "plane":
            na, nb = sa.Axis, sb.Axis
            if abs(abs(na.dot(nb)) - 1.0) > 1e-7:
                return False
            return abs((sb.Position - sa.Position).dot(na)) < tol * 10
        if kind in ("cylinder", "cone"):
            if abs(abs(sa.Axis.dot(sb.Axis)) - 1.0) > 1e-7:
                return False
            if abs(sa.Radius - sb.Radius) > tol * 10 and kind == "cylinder":
                return False
            d = sb.Center - sa.Center
            off_axis = d - sa.Axis * d.dot(sa.Axis)
            if off_axis.Length > tol * 10:
                return False
            if kind == "cone":
                return (
                    abs(abs(sa.SemiAngle) - abs(sb.SemiAngle)) < 1e-7
                    and (sa.Apex - sb.Apex).Length < tol * 10
                )
            return True
    except Exception:
        return False
    return a.isSame(b)


def tangent_chain(shape, face_name):
    """Names of the faces joined smoothly (tangent) to `face_name`, with it."""
    try:
        faces = shape.Faces
        start = shape.getElement(face_name)
    except Exception:
        return [face_name]
    index = {}
    for i, f in enumerate(faces, start=1):
        index[f.hashCode()] = i
    chain = [face_name]
    todo = [start]
    seen = {start.hashCode()}
    while todo:
        face = todo.pop()
        for edge in face.Edges:
            for other in shape.ancestorsOfType(edge, _face_type()):
                if other.hashCode() in seen:
                    continue
                if _tangent_along(face, other, edge):
                    seen.add(other.hashCode())
                    todo.append(other)
                    number = index.get(other.hashCode())
                    if number is not None:
                        chain.append("Face%d" % number)
    return chain


def _face_type():
    import Part

    return Part.Face


def _tangent_along(a, b, edge, tol=1e-3):
    """True if faces a and b meet smoothly at the middle of their shared edge."""
    try:
        t = edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) / 2.0
        p = edge.valueAt(t)
        ua, va = a.Surface.parameter(p)
        ub, vb = b.Surface.parameter(p)
        na, nb = a.normalAt(ua, va), b.normalAt(ub, vb)
        return na.dot(nb) > 1.0 - tol
    except Exception:
        return False


# -- laying the profile onto the face -------------------------------------------------------------
class Wrap:
    """Where profile points (body coordinates) land on the face: the anchor, the face's
    parameter directions there, and the maps of emboss_core."""

    def __init__(self, targets, origin, normal, x_axis, y_axis, options):
        self.targets = list(targets)
        self.origin = App.Vector(origin)
        self.normal = App.Vector(normal)
        self.x_axis = App.Vector(x_axis)
        self.y_axis = App.Vector(y_axis)
        self.h = float(options.get("h", 0.0))
        self.v = float(options.get("v", 0.0))
        self.angle = float(options.get("angle", 0.0))
        self.note = ""
        self.anchor, self.face = self._anchor()
        self.surface = self.face.Surface
        self.kind = core.kind_of(self.surface.TypeId)
        self.u0, self.v0 = self.surface.parameter(self.anchor)
        self.face_normal = App.Vector(self.face.normalAt(self.u0, self.v0))
        self.face_normal.normalize()
        du = App.Vector(self.surface.getDN(self.u0, self.v0, 1, 0))
        dv = App.Vector(self.surface.getDN(self.u0, self.v0, 0, 1))
        if du.Length < 1e-12 or dv.Length < 1e-12:
            if self.kind != "other":
                raise EmbossError("The profile lands on a pinched point of the face: move it.")
            # (a ball's pole: a projection needs no parameter directions; any two do)
            du = self.face_normal.cross(App.Vector(1, 0, 0))
            if du.Length < 1e-6:
                du = self.face_normal.cross(App.Vector(0, 1, 0))
            dv = self.face_normal.cross(du)
        self.e_u = du.normalize()
        self.e_v = dv.normalize()
        natural = self.e_u.cross(self.e_v)
        self.side = 1.0 if natural.dot(self.face_normal) >= 0 else -1.0
        # the sketch's axes turned onto the face (the normal onto the face's normal)
        turn = App.Rotation(self.normal, self.face_normal)
        tx = turn.multVec(self.x_axis)
        ty = turn.multVec(self.y_axis)
        self.tx, self.ty = tx, ty
        self.turn = turn
        self.xa, self.xb = tx.dot(self.e_u), tx.dot(self.e_v)
        self.ya, self.yb = ty.dot(self.e_u), ty.dot(self.e_v)
        self.affine = self.kind in ("plane", "cylinder")
        if self.kind == "other":
            self.note = (
                "This face is curved in two directions: the profile is projected onto it "
                "along the sketch's direction (Fusion wraps only onto flat, cylindrical and "
                "conical faces). Letters stretch where the face is steep."
            )

    def _anchor(self):
        """The point where the profile's middle lands, and the face it lands on."""
        import Part

        reach = self.origin
        size = 0.0
        for face in self.targets:
            size = max(size, face.BoundBox.DiagonalLength)
            reach = face.BoundBox.Center
        length = 4.0 * (size + (reach - self.origin).Length + 1.0)
        line = Part.makeLine(self.origin - self.normal * length, self.origin + self.normal * length)
        hits = []
        for face in self.targets:
            try:
                section = face.section(line)
            except Exception:
                continue
            for vertex in section.Vertexes:
                p = vertex.Point
                try:
                    u, v = face.Surface.parameter(p)
                    facing = face.normalAt(u, v).dot(self.normal)
                except Exception:
                    facing = 0.0
                t = (p - self.origin).dot(self.normal)
                # a face looking back at the sketch's side first, then the nearest
                hits.append((0 if facing > 1e-9 else 1, abs(t), p, face))
        if hits:
            hits.sort(key=lambda h: (h[0], h[1]))
            return App.Vector(hits[0][2]), hits[0][3]
        # the sketch's normal misses the faces: the nearest point of them
        best = None
        probe = Part.Vertex(self.origin)
        for face in self.targets:
            try:
                d, points, _info = face.distToShape(probe)
            except Exception:
                continue
            if best is None or d < best[0]:
                best = (d, App.Vector(points[0][0]), face)
        if best is None:
            raise EmbossError("The profile cannot be laid onto the picked faces.")
        return best[1], best[2]

    # -- maps ----------------------------------------------------------------------------------
    def xy(self, point):
        """The profile point's own 2D coordinates (its sketch's axes, from the middle)."""
        d = App.Vector(point) - self.origin
        return d.dot(self.x_axis), d.dot(self.y_axis)

    def ab(self, point):
        """The tangent-plane coordinates of a profile point after the Alignment."""
        x, y = self.xy(point)
        x, y = core.align(x, y, self.h, self.v, self.angle)
        return core.to_tangent(x, y, self.xa, self.xb, self.ya, self.yb)

    def uv(self, point):
        """The face's parameters where a profile point lands."""
        if self.kind == "other":
            return self._projected(point)
        a, b = self.ab(point)
        if self.kind == "plane":
            return (self.u0 + a, self.v0 + b)
        if self.kind == "cylinder":
            return core.cylinder_uv(a, b, self.surface.Radius, self.u0, self.v0)
        return core.cone_uv(a, b, self.surface.Radius, self.surface.SemiAngle, self.u0, self.v0)

    def _projected(self, point):
        """A profile point moved by the Alignment, then along the sketch's normal onto the
        face (a face curved in two directions cannot be unrolled)."""
        import Part

        x, y = self.xy(point)
        x, y = core.align(x, y, self.h, self.v, self.angle)
        p = self.origin + self.x_axis * x + self.y_axis * y
        reach = max(self.face.BoundBox.DiagonalLength, 1.0) * 4.0 + (p - self.anchor).Length
        line = Part.makeLine(p - self.normal * reach, p + self.normal * reach)
        try:
            section = self.face.section(line)
        except Exception:
            section = None
        hits = [v.Point for v in section.Vertexes] if section is not None else []
        if not hits:
            raise EmbossError(
                "Part of the profile does not land on the face: move it (Horizontal / "
                "Vertical Distance) or make it smaller."
            )
        hit = min(hits, key=lambda q: (q - self.anchor).Length)
        return self.surface.parameter(hit)

    def alignment(self):
        """The Alignment as a placement of the profile in its own plane: turned by the
        Rotation Angle about the profile's middle, moved by the two distances."""
        shift = self.x_axis * self.h + self.y_axis * self.v
        return App.Placement(shift, App.Rotation(self.normal, self.angle), self.origin)

    def flat_matrix(self, lift=0.0):
        """For a flat face: the profile moved rigidly onto it (the Alignment, then the
        sketch's normal turned onto the face's, the middle onto the anchor), `lift` mm
        along the face's normal. The same map as uv() for a plane, but it keeps circles
        circles (exact faces, exact volumes)."""
        onto = App.Placement(self.anchor + self.face_normal * lift, self.turn).multiply(
            App.Placement(-self.origin, App.Rotation())
        )
        return onto.multiply(self.alignment()).toMatrix()

    def hit(self, point, faces=None):
        """Where the line through `point` along the sketch's normal meets the faces (the
        meeting nearest the anchor), or None."""
        import Part

        faces = faces if faces is not None else self.targets
        size = max(f.BoundBox.DiagonalLength for f in faces) if faces else 1.0
        reach = size * 4.0 + (App.Vector(point) - self.anchor).Length + 1.0
        line = Part.makeLine(point - self.normal * reach, point + self.normal * reach)
        best = None
        for face in faces:
            try:
                section = face.section(line)
            except Exception:
                continue
            for v in section.Vertexes:
                d = (v.Point - self.anchor).Length
                if best is None or d < best[0]:
                    best = (d, App.Vector(v.Point))
        return best[1] if best is not None else None

    # -- the handles' frame ------------------------------------------------------------------------
    def frame(self):
        """(anchor after the Alignment, face normal there, profile x, profile y) in body
        coordinates: where the dialog draws its arrows."""
        u, v = self.uv(self.origin)
        try:
            point = App.Vector(self.surface.value(u, v))
            normal = App.Vector(self.face.normalAt(u, v))
            normal.normalize()
        except Exception:
            point, normal = self.anchor, self.face_normal
        turn = App.Rotation(self.face_normal, normal)
        a = math.radians(self.angle)
        x = self.tx * math.cos(a) + self.ty * math.sin(a)
        y = self.ty * math.cos(a) - self.tx * math.sin(a)
        return point, normal, turn.multVec(x), turn.multVec(y)


# -- building the tool ----------------------------------------------------------------------------
def _vec2(p):
    return App.Base.Vector2d(float(p[0]), float(p[1]))


def _edge_on(edge, wrap, surface):
    """`edge` (a profile edge) as an edge on `surface`, through the face's parameters."""
    import Part

    nurbs = edge.toNurbs().Edges[0]
    curve = nurbs.Curve
    first, last = nurbs.FirstParameter, nurbs.LastParameter
    if wrap.affine:
        poles = [_vec2(wrap.uv(p)) for p in curve.getPoles()]
        c2 = Part.Geom2d.BSplineCurve2d()
        c2.buildFromPolesMultsKnots(
            poles,
            curve.getMultiplicities(),
            curve.getKnots(),
            curve.isPeriodic(),
            curve.Degree,
            curve.getWeights(),
        )
        return c2.toShape(surface, first, last)
    count = core.samples(edge.Length)
    points = []
    for i in range(count):
        t = first + (last - first) * i / float(count - 1)
        points.append(_vec2(wrap.uv(nurbs.valueAt(t))))
    if edge.isClosed() and (points[0].distance(points[-1]) > 1e-9):
        points[-1] = points[0]
    c2 = Part.Geom2d.BSplineCurve2d()
    c2.interpolate(points)
    return c2.toShape(surface)


def _offset_surface(surface, distance, normal=None):
    """The surface moved `distance` along its own normal (a plane: moved along `normal`,
    keeping its parameter directions, so the same (u, v) lands on the same spot)."""
    import Part

    if abs(distance) < 1e-12:
        return surface
    if core.kind_of(surface.TypeId) == "plane":
        moved = surface.copy()
        axis = App.Vector(surface.Axis)
        moved.translate(axis * distance)
        return moved
    return Part.OffsetSurface(surface, distance)


def _face_on(profile_face, wrap, surface):
    """The profile face laid on `surface` (its holes kept)."""
    import Part

    wires = []
    for wire in [profile_face.OuterWire] + [
        w for w in profile_face.Wires if not w.isSame(profile_face.OuterWire)
    ]:
        edges = [_edge_on(e, wrap, surface) for e in wire.OrderedEdges]
        wires.append(Part.Wire(edges))
    face = Part.Face(surface, wires[0])
    if len(wires) > 1:
        face.cutHoles(wires[1:])
    face.validate()
    return face


def _check_on_face(profile_faces, wrap):
    """Refuse a profile that hangs over the edge of the picked faces."""
    outside = 0
    for face in profile_faces:
        for edge in face.Edges:
            first, last = edge.FirstParameter, edge.LastParameter
            for i in range(5):
                p = edge.valueAt(first + (last - first) * i / 4.0)
                u, v = wrap.uv(p)
                point = wrap.surface.value(u, v)
                if not any(t.isInside(point, 1e-3, True) for t in wrap.targets):
                    outside += 1
                    break
            if outside:
                break
        if outside:
            break
    if outside:
        raise EmbossError(
            "The profile goes past the edge of the picked face%s. Move it (Horizontal / "
            "Vertical Distance), make it smaller, or pick the faces next to it too."
            % ("s" if len(wrap.targets) > 1 else "")
        )


def tool_shape(profile_faces, wrap, depth, effect):
    """The solid an Emboss adds (or a Deboss removes): the profiles on the face, thickened
    along the face's normal by the depth (a hair more into the part)."""
    import Part

    if wrap.kind == "cylinder" and effect == "deboss":
        core.check_deboss_depth(depth, "cylinder", wrap.surface.Radius)
    if wrap.kind == "cylinder":
        around = [wrap.ab(v.Point)[0] for face in profile_faces for v in face.Vertexes]
        if around and not core.fits_around(max(around) - min(around), wrap.surface.Radius):
            raise EmbossError(
                "The profile is longer than the way round the cylinder (%.1f mm): make it "
                "smaller." % (2.0 * math.pi * wrap.surface.Radius)
            )
    _check_on_face(profile_faces, wrap)
    if wrap.kind == "other":
        return _projected_tool(profile_faces, wrap, depth, effect)
    # a hair inside the part for Emboss, outside it for Deboss
    into = -1.0 if effect == "emboss" else 1.0
    base = None
    if wrap.kind != "plane":
        base = _offset_surface(wrap.surface, into * wrap.side * core.EPS)
    solids = []
    for face in profile_faces:
        try:
            if wrap.kind == "plane":
                on = face.copy()
                on.transformShape(wrap.flat_matrix(into * core.EPS))
            else:
                on = _face_on(face, wrap, base)
        except Exception as exc:
            raise EmbossError("A profile could not be laid on the face: %s" % exc)
        try:
            if wrap.kind == "plane":
                # a flat face: a straight prism along the face's normal
                reach = (depth + core.EPS) * (1.0 if effect == "emboss" else -1.0)
                thick = on.extrude(wrap.face_normal * reach)
            else:
                u0, u1, v0, v1 = on.ParameterRange
                facing = on.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
                along = 1.0 if facing.dot(wrap.face_normal) >= 0 else -1.0
                reach = (depth + core.EPS) * along * (1.0 if effect == "emboss" else -1.0)
                thick = on.makeOffsetShape(reach, 1e-6, False, False, 0, 0, True)
        except Exception as exc:
            raise EmbossError(
                "The profile cannot be made %s mm thick on this face: %s. Try a smaller depth."
                % (_number(depth), exc)
            )
        found = [s for s in thick.Solids if s.Volume > TOL]
        if not found:
            raise EmbossError("The profile made no solid on this face. Try a smaller depth.")
        solids += found
    return Part.Compound(solids)


def _projected_tool(profile_faces, wrap, depth, effect):
    """A face curved in two directions (a ball, a free-form face) cannot be unrolled: the
    profile goes straight along the sketch's normal onto it. The tool is what the
    profile's prism along that normal cuts out of a skin of the faces `depth` thick (a
    hair into the part for Emboss, out of it for Deboss), so the depth is measured
    along the face's normal and the walls follow the sketch's direction."""
    import Part

    normal = App.Vector(wrap.normal)
    normal.normalize()
    matrix = wrap.alignment().toMatrix()
    moved = []
    for face in profile_faces:
        copy = face.copy()
        copy.transformShape(matrix)
        moved.append(copy)
    # how far along the normal the faces are under the profile
    spans = []
    for face in moved:
        for edge in face.Edges:
            first, last = edge.FirstParameter, edge.LastParameter
            for i in range(9):
                p = edge.valueAt(first + (last - first) * i / 8.0)
                hit = wrap.hit(p)
                if hit is None:
                    raise EmbossError(
                        "Part of the profile does not land on the face: move it (Horizontal "
                        "/ Vertical Distance) or make it smaller."
                    )
                spans.append((hit - p).dot(normal))
    margin = 5.0 * (depth + core.EPS) + 0.2
    low, high = min(spans) - margin, max(spans) + margin
    prisms = []
    for face in moved:
        start = face.copy()
        start.translate(normal * low)
        prisms.append(start.extrude(normal * (high - low)))
    # the skin: from a hair inside to the depth outside (Emboss), or the other way round
    into = -core.EPS if effect == "emboss" else core.EPS
    thick = (depth + core.EPS) if effect == "emboss" else -(depth + core.EPS)
    skins = []
    for target in wrap.targets:
        try:
            skins.append(_skin(target, into, thick))
        except Exception as exc:
            raise EmbossError(
                "The face cannot be made %s mm thick here: %s. Try a smaller depth."
                % (_number(depth), exc)
            )
    try:
        tool = Part.Compound(prisms).common(Part.Compound(skins))
    except Exception as exc:
        raise EmbossError("The profile cannot be laid onto this face: %s" % exc)
    found = [x for x in tool.Solids if x.Volume > TOL]
    if not found:
        raise EmbossError("The profile made no solid on this face. Try a smaller depth.")
    return Part.Compound(found)


def _skin(face, start_at, thick):
    """The solid between `face` moved `start_at` along its normal and that moved `thick`
    further. A face with no edge round it (a whole ball) has nothing to fill between:
    the two closed skins become solids and one is cut from the other."""
    import Part

    start = face.makeOffsetShape(start_at, 1e-6)
    try:
        return start.makeOffsetShape(thick, 1e-6, False, False, 0, 0, True)
    except Exception:
        inner = Part.Shell(start.Faces)
        outer = Part.Shell(start.makeOffsetShape(thick, 1e-6).Faces)
        if not (inner.isClosed() and outer.isClosed()):
            raise
        a, b = Part.Solid(inner), Part.Solid(outer)
        return b.cut(a) if abs(b.Volume) > abs(a.Volume) else a.cut(b)


def _number(value):
    return ("%.3f" % value).rstrip("0").rstrip(".")


def build(base_shape, profiles, targets, options, body=None):
    """(result shape, tool shape, Wrap) of an emboss on `base_shape` (body coordinates).
    `targets`: the faces (Part faces, body coordinates) to emboss on. Raises EmbossError."""
    if base_shape is None or base_shape.isNull() or not base_shape.Solids:
        raise EmbossError("Emboss needs a solid before it in the timeline.")
    if not targets:
        raise EmbossError("Pick the faces of the body to emboss on.")
    depth, effect = core.effect_of(options.get("depth", core.DEFAULT_DEPTH), options["effect"])
    core.check_depth(depth)
    faces, origin, normal, x_axis, y_axis = profile_frame(profiles, body)
    wrap = Wrap(targets, origin, normal, x_axis, y_axis, options)
    same = [t for t in targets if _same_surface(t, wrap.face)]
    wrap.targets = same or [wrap.face]
    tool = tool_shape(faces, wrap, depth, effect)
    try:
        if effect == "emboss":
            result = base_shape.fuse(tool)
        else:
            result = base_shape.cut(tool)
        result = result.removeSplitter()
    except Exception as exc:
        raise EmbossError("The emboss could not be joined to the part: %s" % exc)
    if result.isNull() or not result.Solids:
        raise EmbossError("Nothing is left of the part. Make the deboss shallower.")
    if len(result.Solids) > 1:
        raise EmbossError(
            "The emboss would leave %d separate pieces; a body holds one solid. "
            "Change the depth or the profile." % len(result.Solids)
        )
    solid = result.Solids[0]
    if abs(solid.Volume - base_shape.Volume) < 1e-9:
        raise EmbossError("The emboss does not touch the part: pick the faces under the profile.")
    return solid, tool, wrap


# -- remembering the faces ------------------------------------------------------------------------
def signature(face):
    """What a picked face is, to find it again when the names of the part's faces change
    (an earlier step edited)."""
    kind = surface_kind(face)
    data = {"kind": kind, "area": face.Area, "center": list(face.CenterOfMass)}
    s = face.Surface
    try:
        if kind == "plane":
            data.update(axis=list(face.normalAt(0, 0)), position=list(s.Position))
        elif kind in ("cylinder", "cone"):
            data.update(axis=list(s.Axis), position=list(s.Center), radius=s.Radius)
    except Exception:
        pass
    return data


def find_face(shape, name, sig):
    """The face of `shape` a picked face is now: its name when it still is that face, else
    the face on the same surface nearest to where it was. Returns (name, face) or None."""
    try:
        face = shape.getElement(name.lstrip("?"))
    except Exception:
        face = None
    if face is not None and (not sig or _matches(face, sig)):
        return name.lstrip("?"), face
    if not sig:
        return None
    best = None
    center = App.Vector(*sig.get("center", (0, 0, 0)))
    for i, other in enumerate(shape.Faces, start=1):
        if surface_kind(other) != sig.get("kind") or not _matches(other, sig, loose=True):
            continue
        d = (other.CenterOfMass - center).Length
        if best is None or d < best[0]:
            best = (d, "Face%d" % i, other)
    return (best[1], best[2]) if best is not None else None


def _matches(face, sig, loose=False):
    kind = sig.get("kind")
    if surface_kind(face) != kind:
        return False
    s = face.Surface
    try:
        if kind == "plane":
            axis = App.Vector(*sig["axis"])
            if abs(abs(face.normalAt(0, 0).dot(axis)) - 1.0) > 1e-6:
                return False
            return abs((s.Position - App.Vector(*sig["position"])).dot(axis)) < 1e-5
        if kind in ("cylinder", "cone"):
            axis = App.Vector(*sig["axis"])
            if abs(abs(s.Axis.dot(axis)) - 1.0) > 1e-6 or abs(s.Radius - sig["radius"]) > 1e-5:
                return kind == "cone" and loose  # a cone's reference radius may move
            d = s.Center - App.Vector(*sig["position"])
            return (d - axis * d.dot(axis)).Length < 1e-5
    except Exception:
        return not loose
    if loose:
        return True
    return abs(face.Area - sig.get("area", face.Area)) < 1e-6 * max(1.0, face.Area)


# -- the feature ----------------------------------------------------------------------------------
def _add(obj, kind, name, doc, group="Emboss"):
    if name in obj.PropertiesList:
        return False
    obj.addProperty(kind, name, group, doc)
    return True


class EmbossFeature:
    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        _add(obj, "App::PropertyLinkSubList", "Profiles", "The sketch profiles and texts")
        _add(obj, "App::PropertyLinkSubList", "Faces", "The faces to emboss on")
        if _add(obj, "App::PropertyEnumeration", "Effect", "Emboss adds, Deboss removes"):
            obj.Effect = ["Emboss", "Deboss"]
        if _add(obj, "App::PropertyLength", "Depth", "How high / deep"):
            obj.Depth = core.DEFAULT_DEPTH
        _add(obj, "App::PropertyDistance", "HorizontalDistance", "Move along the profile's x")
        _add(obj, "App::PropertyDistance", "VerticalDistance", "Move along the profile's y")
        _add(obj, "App::PropertyAngle", "RotationAngle", "Turn the profile on the face")
        if _add(obj, "App::PropertyBool", "TangentChain", "Faces joined smoothly go too"):
            obj.TangentChain = True
        if _add(obj, "App::PropertyBool", "Refine", "Merge faces that end up in one plane"):
            obj.Refine = True
        if META not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", META, "SciForge", "Remembered faces", 0)
            obj.setEditorMode(META, 2)
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
        obj.SciForgeType = KIND

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise EmbossError("Emboss needs a solid before it in the timeline.")
        profiles = []
        for linked, subs in obj.Profiles:
            for sub in subs or [""]:
                profiles.append((linked, sub))
        targets = target_faces(obj)
        options = read_options(obj)
        result, tool, wrap = build(base.Shape, profiles, targets, options, owner_body(obj))
        self.tool = tool
        self.wrap = wrap
        obj.Shape = result

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def load_meta(obj):
    try:
        text = getattr(obj, META, "")
        return json.loads(text) if text else {}
    except Exception:
        return {}


def target_faces(obj):
    """The picked faces on the shape before this step (found again after earlier edits)."""
    base = obj.BaseFeature
    shape = base.Shape
    sigs = load_meta(obj).get("faces", {})
    found = []
    for linked, subs in obj.Faces:
        for sub in subs:
            hit = find_face(shape, sub, sigs.get(sub.lstrip("?")))
            if hit is None:
                raise EmbossError(
                    "The face %s the emboss was on is gone (an earlier step changed the "
                    "part). Edit the emboss and pick the face again." % sub.lstrip("?")
                )
            found.append(hit[1])
    return found


def read_options(obj):
    return {
        "effect": "deboss" if obj.Effect == "Deboss" else "emboss",
        "depth": float(obj.Depth.Value),
        "h": float(obj.HorizontalDistance.Value),
        "v": float(obj.VerticalDistance.Value),
        "angle": float(obj.RotationAngle.Value),
        "tangent_chain": bool(obj.TangentChain),
    }


def owner_body(obj):
    return extrude.owner_body(obj)


def _attach_view_provider(obj):
    try:
        if not App.GuiUp or obj.ViewObject is None:
            return
        from .emboss_ui import ViewProviderEmboss

        ViewProviderEmboss(obj.ViewObject)
    except Exception as exc:
        warn("emboss display: %s" % exc)


def _set(obj, prop, value):
    current = getattr(obj, prop)
    current = getattr(current, "Value", current)
    if isinstance(value, float) and isinstance(current, (int, float)):
        if abs(current - value) < 1e-12:
            return
    elif current == value:
        return
    setattr(obj, prop, value)


def apply(feature, base, profiles, face_names, options, formulas=None):
    """Write the dialog's picks and options onto the feature."""
    from . import preview

    if feature.BaseFeature is not base:
        feature.BaseFeature = base
    grouped, order = {}, []
    for obj, sub in profiles:
        if obj.Name not in grouped:
            grouped[obj.Name] = (obj, [])
            order.append(obj.Name)
        if sub:
            grouped[obj.Name][1].append(sub)
    value = [(grouped[n][0], tuple(grouped[n][1]) or ("",)) for n in order]
    current = [(o, tuple(s)) for o, s in feature.Profiles]
    if current != value:
        feature.Profiles = value
    faces = [(base, tuple(face_names))] if face_names else []
    if [(o, tuple(s)) for o, s in feature.Faces] != faces:
        feature.Faces = faces
    sigs = {}
    for name in face_names:
        try:
            sigs[name] = signature(base.Shape.getElement(name))
        except Exception:
            continue
    meta = json.dumps({"faces": sigs}, sort_keys=True)
    if getattr(feature, META) != meta:
        setattr(feature, META, meta)
    depth, effect = core.effect_of(options["depth"], options["effect"])
    formulas = dict(formulas or {})
    for prop, key in (
        ("Depth", "depth"),
        ("HorizontalDistance", "h"),
        ("VerticalDistance", "v"),
        ("RotationAngle", "angle"),
    ):
        preview.set_formula(feature, prop, formulas.get(key, ""))
    _set(feature, "Effect", EFFECT_NAMES[effect])
    if not formulas.get("depth"):
        _set(feature, "Depth", float(depth))
    if not formulas.get("h"):
        _set(feature, "HorizontalDistance", float(options.get("h", 0.0)))
    if not formulas.get("v"):
        _set(feature, "VerticalDistance", float(options.get("v", 0.0)))
    if not formulas.get("angle"):
        _set(feature, "RotationAngle", float(options.get("angle", 0.0)))
    _set(feature, "TangentChain", bool(options.get("tangent_chain", True)))
    if not feature.Refine:
        feature.Refine = True


def make(body, base, profiles, face_names, options, name="Emboss", formulas=None):
    """A new Emboss at the end of `body`, on `base` (normally body.Tip). Not recomputed."""
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise EmbossError("Emboss needs a solid: make the part first.")
    obj = body.newObject(TYPE, name)
    EmbossFeature(obj)
    _attach_view_provider(obj)
    obj.BaseFeature = base
    body.Tip = obj  # newObject() does not always move the Tip for Python features
    apply(obj, base, profiles, face_names, options, formulas)
    return obj


def read(feature):
    """(base, profiles, face names, options, formulas) of an existing Emboss."""
    from . import preview

    profiles = []
    for linked, subs in feature.Profiles:
        for sub in subs or [""]:
            profiles.append((linked, sub))
    names = []
    for _linked, subs in feature.Faces:
        names += [s.lstrip("?") for s in subs]
    formulas = {
        "depth": preview.formula_of(feature, "Depth"),
        "h": preview.formula_of(feature, "HorizontalDistance"),
        "v": preview.formula_of(feature, "VerticalDistance"),
        "angle": preview.formula_of(feature, "RotationAngle"),
    }
    return feature.BaseFeature, profiles, names, read_options(feature), formulas


def remove(feature):
    from . import shelling

    shelling.remove(feature)


def hide_sketches(profiles):
    """Fusion hides the profile's sketch once the emboss is made."""
    extrude.hide_sketches(profiles)
