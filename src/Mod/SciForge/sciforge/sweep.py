# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Sweep on top of PartDesign. No GUI code: the Sweep command and the golden-model
builder both call this module, so they behave the same.

Profiles (what is swept), a list of (object, sub-element), as for Extrude and Revolve:
  (sketch, "InternalFace2")   one closed area of a sketch
  (sketch, "")                the whole sketch
  (feature, "Face6")          a flat face of a body
Path and guide rail: lists of curve references (sketch or part edges, see curves.py).

Options (dict, see DEFAULTS):
  type         single | rail          Fusion's Single Path / Path + Guide Rail
  distance     0..1   how far along the path the sweep goes from the profile (side one,
                       towards the path's end; the whole path when the profile is at an end)
  distance2    0..1   side two, when the profile sits inside the path (single path only)
  taper        degrees: the sweep widens (+) or narrows (-) along the path, like an extrude
               taper: a side of the profile at distance R from the path tilts by the angle
  twist        degrees the profile turns round the path from one end to the other
  orientation  perpendicular | parallel   the profile stays square to the path, or keeps its
               own direction (translated only)
  scaling      scale | stretch | none     Path + Guide Rail: the profile grows with the rail
               evenly, only towards the rail, or not at all (the rail only turns it)
  operation    join | cut | intersect | new_body

What is built:
  FreeCAD's own AdditivePipe / SubtractivePipe whenever it builds exactly the same thing
  (a single path, the whole path, no taper, no twist, join / cut / new body, everything in
  the body); otherwise SciForge's SweepFeature, which sweeps with OpenCASCADE directly: the
  path trimmed to the distance, the taper as a scaled end section, the twist with a guide
  curve wound round the path, the guide rail with its scaling, and Intersect.
Fusion-only choices are stored as JSON in the hidden "SciForgeSweep" property, so editing
the sweep from the timeline offers them again.
"""
import json
import math

import FreeCAD as App

from . import curves, extrude

TYPES = ("single", "rail")
ORIENTATIONS = ("perpendicular", "parallel")
SCALINGS = ("scale", "stretch", "none")
OPERATIONS = ("join", "cut", "intersect", "new_body")

DEFAULTS = {
    "type": "single",
    "operation": "join",
    "distance": 1.0,
    "distance2": 1.0,
    "taper": 0.0,
    "twist": 0.0,
    "orientation": "perpendicular",
    "scaling": "scale",
    "chain": True,
}

META = "SciForgeSweep"
ROLE = "SciForgeRole"
FP_TYPE = "PartDesign::FeaturePython"
NATIVE = ("PartDesign::AdditivePipe", "PartDesign::SubtractivePipe")
TOL = 1e-7
END_TOL = 1e-4  # mm: a profile this near a path end sits at that end
STATIONS = 9  # sections along a guide rail that does not keep a straight course
TRANSITION_RIGHT_CORNER = 1  # sharp path corners are mitred, like Fusion's sweep


class SweepError(ValueError):
    """The sweep cannot be built as asked; the message says why and what to do."""


owner_body = extrude.owner_body
is_sketch = extrude.is_sketch
normalize = extrude.normalize
key = extrude.key


# -- options -------------------------------------------------------------------------------
def options_with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in (options or {}).items() if v is not None})
    for name, allowed in (
        ("type", TYPES),
        ("orientation", ORIENTATIONS),
        ("scaling", SCALINGS),
        ("operation", OPERATIONS),
    ):
        if merged[name] not in allowed:
            raise SweepError("unknown %s %r" % (name, merged[name]))
    for name in ("distance", "distance2", "taper", "twist"):
        merged[name] = float(merged[name])
    merged["chain"] = bool(merged["chain"])
    return merged


def check_options(options):
    for name, words in (("distance", "Distance"), ("distance2", "Distance Two")):
        value = options[name]
        if value < -1e-9 or value > 1.0 + 1e-9:
            raise SweepError("%s goes from 0 to 1 (the whole path)." % words)
    if abs(options["taper"]) >= 89.0:
        raise SweepError("The taper angle must be between -89 and 89 degrees.")
    if abs(options["twist"]) > 3600.0 + 1e-9:
        raise SweepError("The twist angle can be at most 10 turns (3600 degrees).")


def single(options):
    return options["type"] == "single"


# -- profiles ---------------------------------------------------------------------------------
def check_profiles(profiles):
    profiles = normalize(profiles)
    if not profiles:
        raise SweepError("Select a profile: click inside a sketch area or on a flat face.")
    for obj, sub in profiles:
        faces = extrude.local_faces(obj, sub)
        if not faces:
            raise SweepError(
                "%s has no closed area to sweep. Close the sketch's outline." % obj.Label
            )
        for face in faces:
            if face.Surface.TypeId != "Part::GeomPlane":
                raise SweepError("Only flat faces can be swept. Pick a flat face or a sketch.")
    return profiles


def profile_faces(profiles):
    return extrude.global_faces(profiles)


def _profile_normal(face):
    return extrude.face_normal(face)


# -- the path ---------------------------------------------------------------------------------
def make_path(refs, start_near=None):
    if not curves.normalize(refs):
        raise SweepError("Select a path: click a sketch line or an edge of the part.")
    try:
        return curves.Path(curves.refs_edges(refs), start_near=start_near)
    except curves.CurveError as exc:
        raise SweepError(str(exc))


def station(path, faces):
    """Length along the path where the profile sits: where the path crosses the profile's
    plane (the crossing nearest the profile), else the path point nearest the profile."""
    import Part

    face = faces[0]
    center = extrude.interior_point(face)
    normal = _profile_normal(face)
    reach = path.wire().BoundBox.DiagonalLength + face.BoundBox.DiagonalLength + 10.0
    best = None
    try:
        plane = Part.makePlane(2 * reach, 2 * reach, center - _spread(normal, reach), normal)
        hits = path.wire().section(plane).Vertexes
        for vertex in hits:
            d = (vertex.Point - center).Length
            if best is None or d < best[0]:
                best = (d, vertex.Point)
    except Exception:
        best = None
    point = best[1] if best is not None else None
    if point is None:
        try:
            point = path.wire().distToShape(Part.Vertex(center))[1][0][0]
        except Exception:
            point = path.start
    return path.length_at(point), point


def _spread(normal, reach):
    """Offset from the centre of a square plane of half-size `reach` to its corner."""
    u = curves.any_normal(normal)
    v = normal.cross(u)
    return u * reach + v * reach


class Plan:
    """Where and how far the sweep goes along the path (the dialog shows Distance Two only
    when there is a side two, and puts its handles at the ends)."""

    def __init__(self, path, s_p, options):
        self.path = path
        self.s_p = s_p
        self.length = path.length
        self.closed = path.closed
        self.at_start = s_p <= END_TOL
        self.at_end = (path.length - s_p) <= END_TOL
        self.two_sides = not self.closed and not self.at_start and not self.at_end
        d1, d2 = options["distance"], options["distance2"]
        if self.closed:
            self.side1 = d1 * path.length
            self.side2 = 0.0
        elif self.at_end:
            self.side1 = d1 * path.length  # from the end back towards the start
            self.side2 = 0.0
        elif self.at_start:
            self.side1 = d1 * path.length
            self.side2 = 0.0
        else:
            self.side1 = d1 * (path.length - s_p)
            self.side2 = d2 * s_p if single(options) else s_p
        if self.side1 + self.side2 < 1e-6:
            raise SweepError("The distance is 0: nothing would be swept. Make it bigger.")

    def forward(self):
        """The path running from the profile along side one."""
        if self.closed:
            return self.path.restarted(self.s_p)
        if self.at_end:
            return self.path.reversed()
        return self.path

    def start(self):
        """Length (on forward()) where the profile sits."""
        if self.closed or self.at_end:
            return 0.0
        return self.s_p

    def side_paths(self):
        """[(path starting at the profile, sign)] one per side that has length."""
        fwd = self.forward()
        start = self.start()
        sides = []
        if self.side1 > 1e-6:
            sides.append((fwd.sub(start, start + self.side1), 1.0))
        if self.side2 > 1e-6:
            sides.append((fwd.sub(start, start - self.side2), -1.0))
        return sides

    def whole(self):
        """(path covering both sides, lengths before / after the profile on it)."""
        fwd = self.forward()
        start = self.start()
        return fwd.sub(start - self.side2, start + self.side1)

    def end_points(self):
        """{"distance": end of side one, "distance2": end of side two} (global points)."""
        fwd = self.forward()
        start = self.start()
        found = {"distance": fwd.point_at(start + self.side1)}
        if self.two_sides:
            found["distance2"] = fwd.point_at(start - self.side2)
        return found


def plan(profiles, path_refs, options):
    options = options_with_defaults(options)
    faces = profile_faces(check_profiles(profiles))
    path = make_path(path_refs)
    s_p, _point = station(path, faces)
    return Plan(path, s_p, options)


# -- sweeping ---------------------------------------------------------------------------------
def _solid(shape):
    """The solid of a MakePipeShell result, outward facing."""
    import Part

    solids = list(shape.Solids) if shape.ShapeType != "Solid" else [shape]
    if not solids:
        try:
            solids = [Part.Solid(Part.Shell(shape.Faces))]
        except Exception:
            raise SweepError("The sweep does not close into a solid. Check the profile.")
    solid = solids[0]
    if solid.Volume < 0:
        solid = solid.copy()
        solid.reverse()
    return solid


def _pipe(spine, sections, orientation, aux=None):
    """OpenCASCADE's sweep of `sections` (wires of one closed profile curve, at their own
    places along the spine) along the spine wire."""
    import Part

    try:
        mk = Part.BRepOffsetAPI.MakePipeShell(spine)
        mk.setTolerance(1e-6, 1e-4, 1e-2)
        mk.setTransitionMode(TRANSITION_RIGHT_CORNER)
        if aux is not None:
            mk.setAuxiliarySpine(aux, True, 0)
        elif orientation == "parallel":
            mk.setTrihedronMode(App.Vector(0, 0, 0), App.Vector(0, 0, 1))
        else:
            mk.setFrenetMode(False)
        for section in sections:
            mk.add(section, False, False)
        if not mk.isReady():
            raise SweepError("The sweep cannot be set up with this profile and path.")
        mk.build()
        if not mk.makeSolid():
            raise SweepError("The sweep does not close into a solid. Check the profile.")
        return _solid(mk.shape())
    except SweepError:
        raise
    except Exception as exc:
        raise SweepError(
            "The profile cannot follow this path (%s). A path that turns sharper than the "
            "profile is wide often causes this." % (str(exc) or type(exc).__name__)
        )


def _transported(spine, wire, orientation, aux, count):
    """The profile wire carried along the spine: `count` sections at even lengths."""
    import Part

    try:
        mk = Part.BRepOffsetAPI.MakePipeShell(spine)
        mk.setTolerance(1e-6, 1e-4, 1e-2)
        mk.setTransitionMode(TRANSITION_RIGHT_CORNER)
        if aux is not None:
            mk.setAuxiliarySpine(aux, True, 0)
        elif orientation == "parallel":
            mk.setTrihedronMode(App.Vector(0, 0, 0), App.Vector(0, 0, 1))
        else:
            mk.setFrenetMode(False)
        mk.add(wire, False, False)
        return list(mk.simulate(count))
    except Exception as exc:
        raise SweepError("The profile cannot follow this path (%s)." % exc)


def _wires_of(face):
    outer = face.OuterWire
    inner = [w for w in face.Wires if not w.isSame(outer)]
    return outer, inner


def _stretch(wire, center, direction, factor):
    """`wire` stretched by `factor` along `direction` (unit) about `center`."""
    u = App.Vector(direction)
    m = App.Matrix()
    for i in range(3):
        for j in range(3):
            _set(m, i, j, (1.0 if i == j else 0.0) + (factor - 1.0) * u[i] * u[j])
    shift = center - m.multVec(center)
    m.A14, m.A24, m.A34 = shift.x, shift.y, shift.z
    return wire.transformGeometry(m)


def _set(matrix, i, j, value):
    setattr(matrix, "A%d%d" % (i + 1, j + 1), value)


def _scaled(wire, center, factor):
    w = wire.copy()
    w.scale(factor, center)
    return w


def _inradius(face, point):
    """Distance from the path point to the profile's outline (what a taper tilts)."""
    import Part

    try:
        r = face.OuterWire.distToShape(Part.Vertex(point))[0]
    except Exception:
        r = 0.0
    if r < 1e-6:
        r = math.sqrt(max(face.Area, 1e-12) / math.pi)
    return r


def _face_sweep(face, spine, orientation, aux=None, sections_for=None):
    """Solid swept by one profile face (holes stay holes). sections_for(wire) gives the
    sections of one closed curve of the face (default: just that curve)."""
    outer, inner = _wires_of(face)
    pick = sections_for or (lambda w: [w])
    solid = _pipe(spine, pick(outer), orientation, aux)
    for wire in inner:
        hole = _pipe(spine, pick(wire), orientation, aux)
        solid = solid.cut(hole)
    return solid


def _twist_aux(spine, turn, faces):
    radius = max(1.0, max(f.BoundBox.DiagonalLength for f in faces))
    return curves.twist_guide(spine, turn, radius)


def _taper_sections(spine, orientation, aux, factor_end, start_point):
    end_point = spine.end

    def sections(wire):
        end = _transported(spine.wire(), wire, orientation, aux, 2)[-1]
        return [wire, _scaled(end, end_point, factor_end)]

    return sections


def _rail_sections(spine, rail, orientation, mode, count):
    """Sections for Path + Guide Rail with Scale / Stretch: the profile carried along,
    resized at each station so it keeps reaching the rail."""
    p0 = spine.start
    q0 = rail.start
    t0 = spine.tangent_at(0.0)
    d0 = (q0 - p0) - t0 * (q0 - p0).dot(t0)
    if d0.Length < 1e-6:
        raise SweepError(
            "The guide rail touches the path at the profile, so the profile cannot be scaled "
            "to it. Use Profile Scaling None, or move the rail."
        )
    factors = []
    for k in range(count):
        s = spine.length * k / float(count - 1)
        p = spine.point_at(s)
        q = rail.point_at(rail.length * k / float(count - 1))
        t = spine.tangent_at(s)
        d = (q - p) - t * (q - p).dot(t)
        if d.Length < 1e-6:
            raise SweepError(
                "The guide rail meets the path, where the profile would shrink to nothing. "
                "Shorten the distance or use Profile Scaling None."
            )
        factor = d.Length / d0.Length
        direction = App.Vector(d)
        direction.normalize()
        factors.append((p, direction, factor))

    def sections(wire):
        carried = _transported(spine.wire(), wire, orientation, rail.wire(), count)
        found = [wire]
        for (p, direction, factor), section in list(zip(factors, carried))[1:]:
            if mode == "scale":
                found.append(_scaled(section, p, factor))
            else:
                found.append(_stretch(section, p, direction, factor))
        return found

    return sections


def _straight_pair(path, rail):
    return path.is_straight() and rail.is_straight()


def _sweep_side(faces, spine, options, turn, rail=None):
    """Solid of one side: `spine` starts at the profile."""
    orientation = options["orientation"]
    aux = None
    sections_for = None
    if rail is not None:
        aux = rail.wire()
        if options["scaling"] != "none":
            count = 2 if _straight_pair(spine, rail) else STATIONS
            sections_for = _rail_sections(spine, rail, orientation, options["scaling"], count)
    else:
        if abs(turn) > 1e-9 and orientation == "perpendicular":
            aux = _twist_aux(spine, turn, faces)
        if abs(options["taper"]) > 1e-9:
            tan = math.tan(math.radians(options["taper"]))
            radius = _inradius(faces[0], spine.start)
            factor = 1.0 + spine.length * tan / radius
            if factor <= 1e-3:
                raise SweepError(
                    "The taper angle shrinks the profile to nothing before the end of the path. "
                    "Use a smaller angle or a shorter distance."
                )
            sections_for = _taper_sections(spine, orientation, aux, factor, spine.start)
    solids = [_face_sweep(face, spine.wire(), orientation, aux, sections_for) for face in faces]
    return _fuse(solids)


def _fuse(solids):
    if not solids:
        raise SweepError("The sweep is empty.")
    if len(solids) == 1:
        return solids[0]
    result = solids[0].multiFuse(solids[1:])
    try:
        result = result.removeSplitter()
    except Exception:
        pass
    return result


def tool_shape(profiles, path_refs, rail_refs, options):
    """The swept solid (global coordinates), as the preview adds or removes it."""
    options = options_with_defaults(options)
    check_options(options)
    profiles = check_profiles(profiles)
    faces = profile_faces(profiles)
    path = make_path(path_refs)
    s_p, _point = station(path, faces)
    layout = Plan(path, s_p, options)
    rail = None
    if not single(options):
        if not curves.normalize(rail_refs):
            raise SweepError("Select a guide rail: click a sketch line or an edge of the part.")
        try:
            rail = curves.Path(curves.refs_edges(rail_refs), start_near=path.start)
        except curves.CurveError as exc:
            raise SweepError("Guide rail: %s" % exc)
        if rail.closed != path.closed:
            raise SweepError("The guide rail must be open or closed like the path.")
    turn = options["twist"] if single(options) else 0.0
    split = abs(options["taper"]) > 1e-9 and single(options)
    split = split or (rail is not None and options["scaling"] != "none")
    if not layout.two_sides or not split:
        spine = layout.whole() if layout.two_sides else layout.side_paths()[0][0]
        rail_part = _rail_part(rail, path, layout, spine) if rail is not None else None
        return _sweep_side(faces, spine, options, turn, rail_part)
    total = layout.side1 + layout.side2
    pieces = []
    for spine, sign in layout.side_paths():
        part_turn = turn * spine.length / total
        rail_part = _rail_part(rail, path, layout, spine, sign) if rail is not None else None
        pieces.append(_sweep_side(faces, spine, options, part_turn, rail_part))
    return _fuse(pieces)


def _rail_part(rail, path, layout, spine, sign=1.0):
    """The part of the rail that runs beside `spine` (same share of its length)."""
    fwd_rail = rail
    if layout.at_end:
        fwd_rail = rail.reversed()
    if layout.closed:
        ratio = layout.s_p / path.length
        fwd_rail = rail.restarted(ratio * rail.length)
    scale = fwd_rail.length / path.length
    start = layout.start() * scale
    if layout.two_sides and abs(spine.length - (layout.side1 + layout.side2)) < 1e-6:
        return fwd_rail.sub(start - layout.side2 * scale, start + layout.side1 * scale)
    if sign > 0:
        return fwd_rail.sub(start, start + spine.length * scale)
    return fwd_rail.sub(start, start - spine.length * scale)


def auto_operation(base_shape, profiles, path_refs, rail_refs, options):
    """Fusion: sweeping into material becomes a cut, out of it a join (a new body when there
    is no solid yet)."""
    if base_shape is None or base_shape.isNull() or not base_shape.Solids:
        return "new_body"
    try:
        tool = tool_shape(profiles, path_refs, rail_refs, options)
        inside = base_shape.common(tool).Volume
        outside = tool.Volume - inside
    except Exception:
        return "join"
    return "cut" if inside > outside + 1e-6 * max(1.0, tool.Volume) else "join"


# -- meta ---------------------------------------------------------------------------------------
def _refs_json(refs):
    return [[obj.Name, sub] for obj, sub in refs or [] if obj is not None]


def _refs_load(doc, data):
    found = []
    for name, sub in data or []:
        obj = doc.getObject(name)
        if obj is not None:
            found.append((obj, sub))
    return found


def load_meta(feature):
    try:
        text = getattr(feature, META, "")
        return json.loads(text) if text else {}
    except Exception:
        return {}


def _save_meta(feature, meta):
    if META not in feature.PropertiesList:
        feature.addProperty("App::PropertyString", META, "SciForge", "Fusion sweep options", 0)
        feature.setEditorMode(META, 2)
    text = json.dumps(meta, sort_keys=True)
    if getattr(feature, META) != text:
        setattr(feature, META, text)


def is_own(obj):
    return obj is not None and getattr(obj, "SciForgeType", "") == "Sweep" and obj.TypeId == FP_TYPE


def is_sweep(obj):
    return obj is not None and (obj.TypeId in NATIVE or is_own(obj))


# -- SciForge's own sweep feature -------------------------------------------------------------
def _set_enum(obj, prop, items):
    extrude._set_enum(obj, prop, items)


class SweepFeature:
    """Sweep with what FreeCAD's Pipe cannot do: distance, taper, twist, guide rail scaling,
    Intersect, profiles or paths from other bodies. Saved documents store
    "sciforge.sweep.SweepFeature": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Sweep"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSubListGlobal", "Profiles", "The profiles that are swept")
        add("App::PropertyLinkSubListGlobal", "Path", "The curves the profiles follow")
        add("App::PropertyLinkSubListGlobal", "GuideRail", "Path + Guide Rail: the rail")
        if add("App::PropertyEnumeration", "Operation", "Join, cut or intersect"):
            obj.Operation = ["Join", "Cut", "Intersect"]
        if add("App::PropertyEnumeration", "SweepType", "Single path or path + guide rail"):
            obj.SweepType = ["Single Path", "Path + Guide Rail"]
        if add("App::PropertyFloatConstraint", "Distance", "Share of the path (side one)"):
            obj.Distance = (1.0, 0.0, 1.0, 0.05)
        if add("App::PropertyFloatConstraint", "Distance2", "Share of the path (side two)"):
            obj.Distance2 = (1.0, 0.0, 1.0, 0.05)
        add("App::PropertyAngle", "TaperAngle", "Taper angle (+ widens)")
        add("App::PropertyAngle", "TwistAngle", "Turn of the profile along the path")
        if add("App::PropertyEnumeration", "Orientation", "Square to the path or parallel"):
            obj.Orientation = ["Perpendicular", "Parallel"]
        if add("App::PropertyEnumeration", "ProfileScaling", "Guide rail: how the profile grows"):
            obj.ProfileScaling = ["Scale", "Stretch", "None"]
        if add("App::PropertyBool", "Refine", "Merge coplanar faces, like Fusion"):
            obj.Refine = True
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
            obj.SciForgeType = "Sweep"

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        has_base = base is not None and not base.Shape.isNull() and bool(base.Shape.Solids)
        operation = obj.Operation
        if not has_base and operation != "Join":
            raise SweepError(
                "%s needs a solid before it in the timeline."
                % ("Cut" if operation == "Cut" else "Intersect")
            )
        options = fp_options(obj)
        profiles = _links(obj.Profiles)
        path = _links(obj.Path)
        rail = _links(obj.GuideRail)
        tool = tool_shape(profiles, path, rail, options)
        body = owner_body(obj)
        if body is not None:
            inverse = body.getGlobalPlacement().inverse()
            if not inverse.isIdentity():
                tool = tool.copy()
                tool.transformShape(inverse.toMatrix(), True)
        if not has_base:
            result = tool
        elif operation == "Intersect":
            result = base.Shape.common(tool)
        elif operation == "Cut":
            result = base.Shape.cut(tool)
        else:
            result = base.Shape.fuse(tool)
        if obj.Refine:
            try:
                result = result.removeSplitter()
            except Exception:
                pass
        if result.isNull() or not result.Solids or result.Volume < TOL:
            if operation == "Cut":
                raise SweepError("This cut would remove the whole body.")
            raise SweepError(
                "The sweep does not overlap the body, so Intersect would leave nothing."
            )
        if operation == "Cut" and abs(result.Volume - base.Shape.Volume) < 1e-9:
            raise SweepError("The cut does not touch the body. Move the profile or the path.")
        obj.Shape = result.Solids[0] if len(result.Solids) == 1 else result

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _links(value):
    found = []
    for linked, subs in value or []:
        if linked is None:
            continue
        for sub in subs or [""]:
            found.append((linked, sub))
    return found


def fp_options(obj):
    return {
        "type": "single" if obj.SweepType == "Single Path" else "rail",
        "operation": obj.Operation.lower(),
        "distance": float(obj.Distance),
        "distance2": float(obj.Distance2),
        "taper": obj.TaperAngle.Value,
        "twist": obj.TwistAngle.Value,
        "orientation": obj.Orientation.lower(),
        "scaling": obj.ProfileScaling.lower(),
    }


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .sweep_ui import ViewProviderSweep

        ViewProviderSweep(obj.ViewObject)
    except Exception:
        pass


# -- which FreeCAD feature ----------------------------------------------------------------------
def _native_profile(profiles, body):
    """Profile value for FreeCAD's Pipe (a sketch, or (feature, [face])), or None when its
    Pipe cannot take these profiles as they are."""
    objs = {obj.Name for obj, _ in profiles}
    if len(objs) != 1:
        return None
    obj = profiles[0][0]
    if owner_body(obj) is not body or obj is body:
        return None
    if is_sketch(obj):
        try:
            whole = {k for k in (extrude.key(p) for p in extrude.expand_whole([(obj, "")]))}
            picked = {extrude.key(p) for p in extrude.expand_whole(profiles)}
        except Exception:
            return None
        return obj if whole == picked and whole else None
    if len(profiles) == 1 and profiles[0][1].startswith("Face"):
        return (obj, [profiles[0][1]])
    return None


def _native_curves(refs, body):
    refs = curves.normalize(refs)
    if not refs or len({obj.Name for obj, _ in refs}) != 1:
        return None
    obj = refs[0][0]
    if owner_body(obj) is not body or obj is body:
        return None
    return (obj, [sub for _, sub in refs])


def native_type(profiles, path_refs, options, body, two_sides):
    """FreeCAD's own Pipe type when it builds exactly this sweep, else None."""
    if body is None or not single(options):
        return None
    if options["operation"] not in ("join", "cut", "new_body"):
        return None
    if abs(options["taper"]) > 1e-9 or abs(options["twist"]) > 1e-9:
        return None
    if abs(options["distance"] - 1.0) > 1e-9:
        return None
    if two_sides and abs(options["distance2"] - 1.0) > 1e-9:
        return None
    if _native_profile(profiles, body) is None or _native_curves(path_refs, body) is None:
        return None
    return "PartDesign::SubtractivePipe" if options["operation"] == "cut" else NATIVE[0]


# -- building -----------------------------------------------------------------------------------
def _has_solid(body, before=None):
    tip = before.BaseFeature if before is not None else body.Tip
    return tip is not None and not tip.Shape.isNull() and bool(tip.Shape.Solids)


def _insert(body, type_id, name, before=None):
    if before is not None:
        obj = body.Document.addObject(type_id, name)
        body.insertObject(obj, before, False)
        return obj
    return body.newObject(type_id, name)


def _source_body(profiles):
    body = owner_body(profiles[0][0])
    if body is None:
        raise SweepError("The profile must belong to a body. Use Create Sketch first.")
    return body


def _target(feature, profiles, options):
    """(target body or None for 'make a new one', source body)."""
    src = _source_body(profiles)
    meta = load_meta(feature) if feature is not None else {}
    created = None
    if feature is not None and meta.get("created_body"):
        created = feature.Document.getObject(meta["created_body"])
    if options["operation"] == "new_body":
        if created is not None:
            return created, src
        if feature is not None and owner_body(feature) is src and not _has_solid(src, feature):
            return src, src
        if feature is None and not _has_solid(src):
            return src, src
        return None, src
    return src, src


def _new_body(src_body):
    doc = src_body.Document
    count = len([o for o in doc.Objects if o.TypeId == "PartDesign::Body"]) + 1
    body = doc.addObject("PartDesign::Body", "Body")
    container = src_body.getParentGeoFeatureGroup()
    if container is not None and hasattr(container, "addObject"):
        container.addObject(body)
    body.Label = "Body%d" % count
    return body


def _two_sides(profiles, path_refs, options):
    try:
        return plan(profiles, path_refs, options).two_sides
    except Exception:
        return False


def build(profiles, path_refs, rail_refs, options, name="Sweep", feature=None, hide=True):
    """Create the sweep, or rebuild `feature` with new picks/options. Returns the feature (a
    different object when its kind had to change). hide=False keeps the sketches visible
    (the dialog hides them on OK, like Fusion)."""
    profiles = check_profiles(profiles)
    options = options_with_defaults(options)
    check_options(options)
    path_refs = curves.normalize(path_refs)
    rail_refs = curves.normalize(rail_refs) if not single(options) else []
    # Fails early with the reason (no path, path in pieces, ...): nothing is built then.
    tool_shape(profiles, path_refs, rail_refs, options)
    target, src = _target(feature, profiles, options)
    two = _two_sides(profiles, path_refs, options)
    native = native_type(profiles, path_refs, options, target, two) if target else None
    type_id = native or FP_TYPE
    if feature is not None:
        same = feature.TypeId == type_id and (type_id != FP_TYPE or is_own(feature))
        if owner_body(feature) is target and same:
            _update(feature, profiles, path_refs, rail_refs, options, hide)
            return feature
        blocking = [o for o in extrude.dependents(feature)]
        if blocking:
            raise SweepError(
                "%s is used by %s, so it cannot change this way here. Make a new sweep instead."
                % (feature.Label, ", ".join(o.Label for o in blocking))
            )
    old_meta = load_meta(feature) if feature is not None else {}
    created = None
    if target is None:
        target = created = _new_body(src)
        type_id = FP_TYPE  # the profile and path stay in their own body
    elif old_meta.get("created_body") == target.Name:
        created = target
    before = feature if (feature is not None and owner_body(feature) is target) else None
    was_tip = before is not None and target.Tip is before
    new = _insert(target, type_id, name, before)
    if type_id == FP_TYPE:
        SweepFeature(new)
        _attach_view_provider(new)
    _save_meta(new, {"created_body": created.Name if created is not None else None})
    try:
        _update(new, profiles, path_refs, rail_refs, options, hide)
    except Exception:
        _remove(new, keep_body=created is None or before is not None)
        raise
    if feature is not None:
        label = feature.Label
        old_body = owner_body(feature)
        _remove(feature, keep_body=old_body is target)
        new.Label = label
        if old_body is not None and old_body is not target:
            extrude.show_tip(old_body)
    if before is None or was_tip:
        target.Tip = new
    return new


def _update(feature, profiles, path_refs, rail_refs, options, hide=True):
    body = owner_body(feature)
    if feature.TypeId in NATIVE:
        profile = _native_profile(profiles, body)
        spine = _native_curves(path_refs, body)
        if profile is None or spine is None:
            raise SweepError("internal: these picks need SciForge's own sweep")
        if feature.Profile != (profile if isinstance(profile, tuple) else (profile, [""])):
            feature.Profile = profile
        feature.Spine = spine
        feature.SpineTangent = False
        mode = "Fixed" if options["orientation"] == "parallel" else "Standard"
        if feature.Mode != mode:
            feature.Mode = mode
        if feature.Transition != "Right corner":
            feature.Transition = "Right corner"
        if feature.Transformation != "Constant":
            feature.Transformation = "Constant"
        feature.Refine = True
    else:
        feature.Profiles = [(obj, [sub]) for obj, sub in profiles]
        feature.Path = [(obj, [sub]) for obj, sub in path_refs]
        feature.GuideRail = [(obj, [sub]) for obj, sub in rail_refs]
        operation = {"cut": "Cut", "intersect": "Intersect"}.get(options["operation"], "Join")
        if feature.Operation != operation:
            feature.Operation = operation
        sweep_type = "Single Path" if single(options) else "Path + Guide Rail"
        if feature.SweepType != sweep_type:
            feature.SweepType = sweep_type
        feature.Distance = max(0.0, min(1.0, options["distance"]))
        feature.Distance2 = max(0.0, min(1.0, options["distance2"]))
        feature.TaperAngle = options["taper"]
        feature.TwistAngle = options["twist"]
        orientation = options["orientation"].capitalize()
        if feature.Orientation != orientation:
            feature.Orientation = orientation
        scaling = options["scaling"].capitalize()
        if feature.ProfileScaling != scaling:
            feature.ProfileScaling = scaling
        feature.Refine = True
    meta = load_meta(feature)
    meta.update(
        {
            "v": 1,
            "operation": options["operation"],
            "type": options["type"],
            "distance": options["distance"],
            "distance2": options["distance2"],
            "taper": options["taper"],
            "twist": options["twist"],
            "orientation": options["orientation"],
            "scaling": options["scaling"],
            "chain": options["chain"],
            "profiles": _refs_json(profiles),
            "path": _refs_json(path_refs),
            "rail": _refs_json(rail_refs),
        }
    )
    _save_meta(feature, meta)
    if hide:
        hide_sketches(profiles, path_refs, rail_refs)


def hide_sketches(profiles, path_refs=(), rail_refs=()):
    """Fusion hides the sketches a feature used."""
    if not App.GuiUp:
        return
    for obj, _ in list(profiles) + list(path_refs) + list(rail_refs):
        if is_sketch(obj):
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass


def _delete(obj):
    doc = obj.Document
    body = owner_body(obj)
    try:
        if body is not None and body is not obj:
            body.removeObject(obj)
    except Exception:
        pass
    try:
        doc.removeObject(obj.Name)
    except Exception:
        pass


def _remove(feature, keep_body=True):
    meta = load_meta(feature)
    doc = feature.Document
    body = owner_body(feature)
    was_tip = body is not None and body.Tip is feature
    _delete(feature)
    if not keep_body and body is not None and meta.get("created_body") == body.Name:
        rest = [o for o in body.Group if o.TypeId != "App::Origin"]
        if not rest:
            body.removeObjectsFromDocument()
            doc.removeObject(body.Name)
            return
    if was_tip:
        extrude.show_tip(body)


def remove(feature):
    _remove(feature, keep_body=False)


def make(profiles, path_refs, options, rail_refs=None, name="Sweep"):
    """New sweep with Fusion-style options."""
    return build(normalize(profiles), path_refs, rail_refs or [], options, name)


def update(feature, profiles=None, path_refs=None, rail_refs=None, options=None):
    """Rebuild an existing sweep; what is not given stays as it is."""
    old_profiles, old_path, old_rail, old_options = read(feature)
    merged = dict(old_options)
    merged.update(options or {})
    return build(
        normalize(profiles) if profiles is not None else old_profiles,
        path_refs if path_refs is not None else old_path,
        rail_refs if rail_refs is not None else old_rail,
        merged,
        feature=feature,
    )


# -- reading back --------------------------------------------------------------------------------
def read(feature):
    """(profiles, path refs, rail refs, options) of an existing sweep, as the dialog shows
    them (a FreeCAD-made Pipe is read from its own properties)."""
    meta = load_meta(feature)
    doc = feature.Document
    options = dict(DEFAULTS)
    for name in DEFAULTS:
        if name in meta:
            options[name] = meta[name]
    if is_own(feature):
        options.update(fp_options(feature))
        if meta.get("operation") == "new_body":
            options["operation"] = "new_body"
        profiles = _links(feature.Profiles)
        path_refs = _links(feature.Path)
        rail_refs = _links(feature.GuideRail)
        return profiles, path_refs, rail_refs, options_with_defaults(options)
    options["operation"] = (
        "cut"
        if feature.TypeId == "PartDesign::SubtractivePipe"
        else ("new_body" if meta.get("operation") == "new_body" else "join")
    )
    options["type"] = "single"
    options["orientation"] = "parallel" if feature.Mode == "Fixed" else "perpendicular"
    options["taper"] = 0.0
    options["twist"] = 0.0
    options["distance"] = 1.0
    options["distance2"] = 1.0
    profiles = _refs_load(doc, meta.get("profiles"))
    if not profiles:
        value = feature.Profile
        obj = value[0] if isinstance(value, tuple) else value
        subs = [s for s in (list(value[1]) if isinstance(value, tuple) else []) if s]
        if obj is not None:
            profiles = [(obj, s) for s in subs] if subs and not is_sketch(obj) else [(obj, "")]
    path_refs = _refs_load(doc, meta.get("path"))
    if not path_refs and feature.Spine:
        obj, subs = feature.Spine[0], list(feature.Spine[1] or [])
        if obj is not None:
            path_refs = curves.normalize([(obj, s) for s in subs] if subs else [(obj, "")])
    return profiles, path_refs, [], options_with_defaults(options)
