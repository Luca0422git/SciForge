# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's surface analyses (INSPECT menu), the document side (no Qt, no Coin).

Each analysis is an App::FeaturePython with SciForgeType "...Analysis" (KINDS below), so the
browser lists it in its Analysis folder (eye to show / hide, Edit, Delete) and the timeline
leaves it out, as Fusion does. It keeps what its dialog set (the bodies, faces or edges it
looks at, the pull direction, the numbers) and is saved with the design. The analysis never
changes the model: surface_analysis_ui.py draws its colours, stripes or combs over the model
from the data worked out here (mesh(), comb_lines(), iso_lines()), again after every change.

Saved documents store "sciforge.surface_analysis.SurfaceAnalysis": keep the name stable.
"""

try:
    import FreeCAD as App

    V = App.Vector
except ImportError:
    App = V = None

import math  # noqa: E402

from . import analysis_core as core  # noqa: E402
from . import labels  # noqa: E402

ZEBRA = "ZebraAnalysis"
DRAFT = "DraftAnalysis"
COMB = "CurvatureCombAnalysis"
CURVATURE_MAP = "CurvatureMapAnalysis"
ISOCURVE = "IsocurveAnalysis"
ACCESSIBILITY = "AccessibilityAnalysis"
MIN_RADIUS = "MinimumRadiusAnalysis"
ENVIRONMENT = "EnvironmentMapAnalysis"  # Fusion's Environmental Map Analysis (Sept 2026)

# kind -> title (command and dialog), label base (browser: Zebra1 ...), icon, what is picked
# ("bodies", "faces" or "edges"), whether a pull / access direction is picked too.
KINDS = {
    ZEBRA: ("Zebra Analysis", "Zebra", "zebra", "bodies", False),
    DRAFT: ("Draft Analysis", "Draft", "draft_analysis", "bodies", True),
    COMB: ("Curvature Comb Analysis", "Curvature Comb", "curvature", "edges", False),
    CURVATURE_MAP: ("Curvature Map Analysis", "Curvature Map", "curvature_map", "bodies", False),
    ISOCURVE: ("Isocurve Analysis", "Isocurve", "isocurve", "faces", False),
    ACCESSIBILITY: ("Accessibility Analysis", "Accessibility", "accessibility", "bodies", True),
    MIN_RADIUS: ("Minimum Radius Analysis", "Minimum Radius", "min_radius", "bodies", False),
    ENVIRONMENT: (
        "Environmental Map Analysis",
        "Environmental Map",
        "environment_map",
        "bodies",
        False,
    ),
}
ZEBRA_DIRECTIONS = ("Vertical", "Horizontal")
MAP_DISPLAYS = ("Smooth", "Bands")
ISO_TYPES = ("U and V", "U", "V")
# The studio the Environmental Map reflects: soft light strips over a dark floor (Studio),
# or a bright sky over a dark ground (Horizon).
ENVIRONMENTS = ("Studio", "Horizon")

# (type, name, tooltip, default) per kind, after the common ones
COMMON = [
    ("App::PropertyLinkSubListGlobal", "Targets", "Bodies, faces or edges analysed", None),
    ("App::PropertyString", "Problem", "Why the analysis shows nothing", ""),
]
SHADED = [
    ("App::PropertyInteger", "Opacity", "0 .. 100 %: how strongly the analysis covers", 100),
    ("App::PropertyBool", "HighQuality", "A finer display (slower)", False),
]
DIRECTION = [
    ("App::PropertyLinkSubGlobal", "PullDirection", "Plane, flat face, edge or axis", None),
    ("App::PropertyBool", "Flip", "Reverse the direction", False),
    ("App::PropertyVector", "PullVector", "The direction (worked out)", None),
]
PROPS = {
    ZEBRA: SHADED
    + [
        ("App::PropertyEnumeration", "Direction", "Stripes vertical or horizontal", None),
        ("App::PropertyInteger", "Repeats", "Number of stripe pairs (1 .. 100)", 20),
        ("App::PropertyBool", "LockStripes", "Stripes stay on the model when it turns", False),
        ("App::PropertyPlacement", "LockedView", "The camera the stripes were locked in", None),
        ("App::PropertyFloat", "LockedHeight", "The view's size when locked", 0.0),
    ],
    DRAFT: SHADED
    + DIRECTION
    + [
        ("App::PropertyAngle", "DraftStart", "Below this draft: red", 1.0),
        ("App::PropertyAngle", "DraftStop", "From this draft on: green / blue", 3.0),
        ("App::PropertyBool", "ToleranceZone", "Yellow between start and stop", False),
    ],
    COMB: [
        ("App::PropertyInteger", "Density", "Teeth per edge (2 .. 100)", 30),
        ("App::PropertyFloat", "CombScale", "Length of the teeth", 1.0),
    ],
    CURVATURE_MAP: SHADED
    + [
        ("App::PropertyEnumeration", "MapType", "What is shown", None),
        ("App::PropertyEnumeration", "MapDisplay", "Smooth or in bands (Gaussian)", None),
        ("App::PropertyFloat", "MapScale", "Strength of the colours (Gaussian)", 1.0),
        ("App::PropertyLength", "LimitRadius", "Radius at which it turns red (Principal)", 10.0),
    ],
    ISOCURVE: [
        ("App::PropertyEnumeration", "IsoType", "U, V or both", None),
        ("App::PropertyInteger", "IsoCount", "Isocurves per direction (1 .. 50)", 5),
        ("App::PropertyBool", "ShowCombs", "A curvature comb on each isocurve", False),
        ("App::PropertyInteger", "Density", "Teeth per comb (2 .. 100)", 30),
        ("App::PropertyFloat", "CombScale", "Length of the teeth", 1.0),
    ],
    ACCESSIBILITY: SHADED
    + DIRECTION
    + [("App::PropertyEnumeration", "AccessMode", "Which way the tool comes from", None)],
    ENVIRONMENT: SHADED
    + [
        ("App::PropertyEnumeration", "Environment", "The surroundings reflected", None),
        ("App::PropertyInteger", "ReflectionStrength", "0 .. 100 %: how strong the reflection", 70),
    ],
    MIN_RADIUS: SHADED
    + [
        ("App::PropertyLength", "MinimumRadius", "Tighter concave rounds: red", 1.0),
        ("App::PropertyLength", "ToolRadius", "Concave rounds this tool fits: green", 5.0),
        (
            "App::PropertyBool",
            "IncludeSharpCurves",
            "Sharp inner edges count as radius 0 (red)",
            False,
        ),
    ],
}
ENUMS = {
    "Direction": ZEBRA_DIRECTIONS,
    "MapType": core.MAP_TYPES,
    "MapDisplay": MAP_DISPLAYS,
    "IsoType": ISO_TYPES,
    "AccessMode": core.ACCESS_MODES,
    "Environment": ENVIRONMENTS,
}


_IMAGES = {}


def environment_image(name, size=128):
    """The picture for `name` (made once, then kept)."""
    key = (name, int(size))
    if key not in _IMAGES:
        _IMAGES[key] = _environment_image(name, int(size))
    return _IMAGES[key]


def _environment_image(name, size):
    """The reflected surroundings as a sphere map (size x size grey levels, bytes, rows from
    the bottom): what a mirror ball standing in them shows. Studio: three soft horizontal
    light strips above, a dark floor below; Horizon: a sky brightening to the horizon over a
    dark ground. Coin maps it by the reflection direction (SoTextureCoordinateEnvironment),
    so the bands slide over a surface as the view turns, and a kink or a curvature jump in
    the surface shows as a kink or a jump in them (the point of the analysis)."""
    data = bytearray()
    strips = ((0.62, 0.07), (0.28, 0.05), (-0.05, 0.035))  # (height, half width) on the ball
    for row in range(size):
        y = (row + 0.5) / size * 2.0 - 1.0
        for col in range(size):
            x = (col + 0.5) / size * 2.0 - 1.0
            r2 = x * x + y * y
            if r2 > 1.0:
                data.append(0)
                continue
            if name == "Horizon":
                level = 0.15 + 0.85 * (y + 1.0) / 2.0 if y > -0.05 else 0.08
            else:
                level = 0.10 if y < -0.25 else 0.22
                for height, half in strips:
                    d = abs(y - height)
                    if d < half * 2.0:
                        level = max(level, 1.0 - (d / (half * 2.0)) ** 2)
            data.append(int(round(255 * max(0.0, min(1.0, level)))))
    return bytes(data)


class AnalysisError(ValueError):
    pass


def title(kind):
    return KINDS[kind][0]


def icon(kind):
    return KINDS.get(kind, ("", "", "zebra"))[2]


def picks(kind):
    return KINDS[kind][3]


def has_direction(kind):
    return KINDS[kind][4]


def kind_of(obj):
    try:
        kind = getattr(obj, "SciForgeType", "")
        return kind if kind in KINDS else ""
    except Exception:
        return ""


def is_analysis(obj, kind=None):
    try:
        found = kind_of(obj)
        if not found or (kind and found != kind):
            return False
        return obj.isAttachedToDocument()
    except Exception:
        return False


def analyses(doc, kind=None):
    return [o for o in doc.Objects if is_analysis(o, kind)]


def alive(obj):
    try:
        return obj is not None and obj.isAttachedToDocument()
    except Exception:
        return False


# -- the analysis object --------------------------------------------------------------------
class SurfaceAnalysis:
    """Proxy of every surface analysis (the kind is SciForgeType; see the module text)."""

    def __init__(self, obj, kind):
        obj.Proxy = self
        self.ensure_properties(obj, kind)

    @staticmethod
    def ensure_properties(obj, kind=None):
        props = obj.PropertiesList
        if "SciForgeType" not in props:
            obj.addProperty("App::PropertyString", "SciForgeType", "SciForge", "Kind")
        if kind:
            obj.SciForgeType = kind
        kind = obj.SciForgeType
        for type_name, name, tip, default in COMMON + PROPS.get(kind, []):
            if name in props:
                continue
            obj.addProperty(type_name, name, "Analysis", tip)
            if name in ENUMS:
                setattr(obj, name, list(ENUMS[name]))
            elif default is not None:
                setattr(obj, name, default)
        try:
            obj.setEditorMode("SciForgeType", 2)
            obj.setPropertyStatus("Problem", ["Output", "Hidden"])
            for name in ("PullVector", "LockedView", "LockedHeight"):
                if name in obj.PropertiesList:
                    obj.setEditorMode(name, 2)
        except Exception:
            pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        """Check the picks and work the direction out again (it follows the face or edge it
        was picked on). Never fails: what is wrong goes to Problem and the dialog says it."""
        problem = ""
        try:
            if not targets(obj):
                problem = GONE[picks(obj.SciForgeType)]
                if any(is_mesh_owner(o) and _mesh_end(o) is None for o, _s in obj.Targets or []):
                    problem = (
                        "Its mesh body does not exist at the history marker (the marker stands "
                        "before it): roll the marker forward to see the analysis."
                    )
            elif has_direction(obj.SciForgeType):
                vector = pull_vector(obj)
                if (obj.PullVector - vector).Length > 1e-12:
                    obj.PullVector = vector
        except AnalysisError as exc:
            problem = str(exc)
        except Exception as exc:
            problem = str(exc) or "This analysis could not be worked out."
        if obj.Problem != problem:
            obj.Problem = problem

    def allowDuplicateLabel(self, obj):
        return labels.allow_duplicate()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


GONE = {
    "bodies": "The bodies of this analysis are gone. Edit it and pick a body.",
    "faces": "The faces of this analysis are gone. Edit it and pick a face.",
    "edges": "The edges of this analysis are gone. Edit it and pick an edge.",
}


def next_label(doc, base):
    import re

    used = 0
    for obj in doc.Objects:
        match = re.match(r"^%s(\d+)$" % re.escape(base), obj.Label or "")
        if match:
            used = max(used, int(match.group(1)))
    return "%s%d" % (base, used + 1)


def make(doc, kind):
    obj = doc.addObject("App::FeaturePython", kind.replace("Analysis", ""))
    SurfaceAnalysis(obj, kind)
    labels.set_exact(obj, next_label(doc, KINDS[kind][1]))
    return obj


# -- mesh bodies -------------------------------------------------------------------------------
# Fusion analyses mesh bodies with Zebra (its API lists mesh bodies among a zebra analysis'
# input entities); the other analyses need an exact surface (normals and curvatures of a
# B-rep face), which a mesh has not.
MESH_KINDS = {ZEBRA}
MESH_TYPES = ("Mesh::Feature", "Mesh::FeaturePython")


def is_mesh_owner(obj):
    try:
        return obj is not None and obj.TypeId in MESH_TYPES
    except Exception:
        return False


def takes_meshes(kind):
    return kind in MESH_KINDS


def mesh_refusal(kind):
    """Why a mesh body cannot take this analysis (said when one is clicked)."""
    return (
        "%s needs a solid or surface body: a mesh body has no exact surface. Mesh bodies "
        "take Zebra Analysis (or MESH > Convert Mesh first)." % title(kind)
    )


def _mesh_end(obj):
    """The mesh body `obj` belongs to as the design is now: the newest step of its history
    (a later mesh step uses the older one up), or None when it does not exist at the
    history marker."""
    try:
        from . import bodies, mesh
    except Exception:
        return obj
    seen = set()
    current = obj
    while current is not None and current.Name not in seen:
        seen.add(current.Name)
        if mesh.rolled_back(current):
            return None
        users = bodies.consumers(current.Document)
        user = users.get(current.Name)
        if user is None:
            return current
        if not mesh.is_mesh(user) or mesh.is_piece(user):
            return current if not mesh.is_piece(user) else user
        current = user
    return current


def mesh_of(owner):
    """The triangles of a mesh body where it shows (its placement built in), with one normal
    per point (the mean of its faces': Coin shades smoothly across them, as the body is)."""
    result = Mesh()
    try:
        points, facets = owner.Mesh.Topology
    except Exception:
        return result
    points = [(p.x, p.y, p.z) for p in points]
    triangles = [tuple(f) for f in facets]
    result.add(points, triangles, _triangle_normals(points, triangles), [])
    result.on_mesh = True
    return result


def bound_box(owner):
    """The bounds of a body or mesh body in its parent's coordinates."""
    if is_mesh_owner(owner):
        return owner.Mesh.BoundBox
    return owner.Shape.BoundBox


def global_box(owner, frame):
    """Bounds of `owner` moved by `frame` (its component's placement)."""
    if frame.isIdentity():
        return bound_box(owner)
    if is_mesh_owner(owner):
        copy = owner.Mesh.copy()
        copy.transform(frame.toMatrix())
        return copy.BoundBox
    return owner.Shape.transformed(frame.toMatrix()).BoundBox


def stamp(owner):
    """Changes whenever what an analysis of `owner` draws on changes."""
    if is_mesh_owner(owner):
        m = owner.Mesh
        return (m.CountFacets, m.CountPoints, round(m.Area, 9), str(owner.Placement))
    return (owner.Shape.hashCode(), display_tolerance(owner))


# -- what is analysed --------------------------------------------------------------------------
def owner_of(obj):
    """The body (or loose solid, or mesh body) a picked object belongs to, or None."""
    if obj is None:
        return None
    if is_mesh_owner(obj):
        return _mesh_end(obj)
    if obj.TypeId == "PartDesign::Body":
        return obj
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        parent = None
    if parent is not None and parent.TypeId == "PartDesign::Body":
        return parent
    if parent is None or parent.TypeId == "App::Part":
        try:
            if obj.isDerivedFrom("Part::Feature") and not getattr(obj, "SciForgeType", ""):
                shape = obj.Shape
                if not shape.isNull() and (shape.Solids or shape.Faces):
                    return obj
        except Exception:
            return None
    return None


def set_targets(obj, entries):
    """entries: [(owner, [element names])] ([] = the whole body)."""
    value = [(owner, list(names) if names else []) for owner, names in entries if alive(owner)]
    current = [(o, list(s) if s and s != ("",) else []) for o, s in (obj.Targets or [])]
    current = [(o, [n for n in s if n]) for o, s in current]
    if [(o.Name, s) for o, s in current] != [(o.Name, s) for o, s in value]:
        obj.Targets = [(o, s if s else "") for o, s in value]


def targets(obj):
    """[(owner, [element names])] still there ([] = the whole body)."""
    found = []
    for entry in obj.Targets or []:
        owner, subs = entry
        if not alive(owner):
            continue
        if is_mesh_owner(owner):
            # a mesh body: the whole body, as its history stands now (a later mesh step is
            # the body then); none when it does not exist at the history marker
            end = _mesh_end(owner)
            if end is not None and alive(end) and takes_meshes(getattr(obj, "SciForgeType", "")):
                found.append((end, []))
            continue
        if isinstance(subs, str):
            subs = [subs]
        names = [s for s in (subs or []) if s]
        try:
            shape = owner.Shape
            if shape.isNull():
                continue
            names = [n for n in names if _has_element(shape, n)]
        except Exception:
            continue
        if subs and any(subs) and not names:
            continue  # its faces / edges are all gone
        found.append((owner, names))
    return found


def _has_element(shape, name):
    try:
        return shape.getElement(name) is not None
    except Exception:
        return False


def parent_placement(owner):
    """Global placement of what holds `owner` (a component), identity at the root. A body's
    Shape already has the body's own placement."""
    try:
        parent = owner.getParentGeoFeatureGroup()
        if parent is not None:
            return parent.getGlobalPlacement()
    except Exception:
        pass
    return App.Placement()


# -- the pull direction ----------------------------------------------------------------------
def pull_vector(obj):
    """Unit pull (or access) direction, global: the picked plane's or flat face's normal, the
    picked edge's or axis' direction, a round face's axis; +Z when nothing is picked."""
    from . import construct

    link = getattr(obj, "PullDirection", None)
    if not link:
        direction = V(0, 0, 1)
    else:
        target, subs = link if isinstance(link, tuple) else (link, [""])
        if not alive(target):
            raise AnalysisError(
                "The direction of this analysis is gone. Edit it and pick a plane, a flat "
                "face, a straight edge or an axis."
            )
        sub = (subs[0] if isinstance(subs, (list, tuple)) and subs else subs) or ""
        direction = direction_of(construct.normalize_pick(target, sub))
    if getattr(obj, "Flip", False):
        direction = direction * -1.0
    return direction


def direction_of(ref):
    from . import construct

    kinds = construct.kinds_of(*ref)
    try:
        if "plane" in kinds:
            return V(construct.plane_of(ref)[1])
        if "line" in kinds:
            return V(construct.line_of(ref)[1])
        if "round" in kinds or "curved" in kinds:
            return V(construct.revolution_of(ref)[1])
    except construct.ConstructError as exc:
        raise AnalysisError(str(exc))
    raise AnalysisError(
        "%s gives no direction: pick a plane, a flat face, a straight edge or an axis."
        % (construct.describe(*ref) or "That")
    )


def fits_direction(obj, sub):
    from . import construct

    kinds = construct.kinds_of(obj, sub)
    return bool(kinds & {"plane", "line", "round"})


# -- meshes ------------------------------------------------------------------------------------
def display_tolerance(owner):
    """The deflection FreeCAD's display meshes `owner` with (a hair more): the faces are
    meshed the same way, so the analysis lies exactly on the model's own triangles."""
    shown = owner.Tip if owner.TypeId == "PartDesign::Body" and owner.Tip else owner
    deviation = 0.2
    try:
        deviation = float(shown.ViewObject.Deviation)
    except Exception:
        pass
    best = 0.0
    for shape in (owner.Shape, shown.Shape):
        try:
            box = shape.BoundBox
            best = max(best, (box.XLength + box.YLength + box.ZLength) / 300.0 * deviation)
        except Exception:
            continue
    return max(best * 1.05, 1e-4)


class Mesh:
    """Points (owner coordinates), triangles, unit outward normals and principal curvatures
    (signed against the outward normal: + concave) of the analysed faces of one body."""

    def __init__(self):
        self.points = []
        self.triangles = []
        self.normals = []
        self.curvatures = []  # (k1, k2) per point, when asked for
        self.on_mesh = False  # drawn over a mesh body's own faces (they are not switched off)

    def add(self, points, triangles, normals, curvatures):
        base = len(self.points)
        self.points += points
        self.normals += normals
        self.curvatures += curvatures
        self.triangles += [(a + base, b + base, c + base) for a, b, c in triangles]


def _triangle_normals(points, triangles):
    """Per point: the average normal of its triangles (where the surface cannot say)."""
    acc = [(0.0, 0.0, 0.0)] * len(points)
    for a, b, c in triangles:
        n = core.cross(core.sub(points[b], points[a]), core.sub(points[c], points[a]))
        for i in (a, b, c):
            acc[i] = core.add(acc[i], n)
    out = []
    for n in acc:
        try:
            out.append(core.unit(n))
        except ValueError:
            out.append((0.0, 0.0, 1.0))
    return out


def face_mesh(face, tolerance, max_edge, curvature=False):
    """(points, triangles, normals, curvatures) of one face on the model's own triangles,
    split finer where they are longer than `max_edge`."""
    pts, tris = face.tessellate(tolerance)
    points = [(p.x, p.y, p.z) for p in pts]
    tris = [tuple(t) for t in tris]
    points, tris = core.subdivide(points, tris, max_edge)
    fallback = _triangle_normals(points, tris)
    reversed_face = face.Orientation == "Reversed"
    surface = face.Surface
    planar = type(surface).__name__ == "Plane"
    normals = []
    curvatures = []
    if planar:
        try:
            u0, u1, v0, v1 = face.ParameterRange
            n = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            normal = core.unit((n.x, n.y, n.z))
        except Exception:
            normal = None
        for i in range(len(points)):
            normals.append(normal or fallback[i])
            if curvature:
                curvatures.append((0.0, 0.0))
        return points, tris, normals, curvatures
    for i, p in enumerate(points):
        try:
            u, v = surface.parameter(V(*p))
            n = face.normalAt(u, v)
            normals.append(core.unit((n.x, n.y, n.z)))
        except Exception:
            normals.append(fallback[i])
            u = v = None
        if curvature:
            k = (0.0, 0.0)
            if u is not None:
                try:
                    k1, k2 = face.curvatureAt(u, v)
                    sign = -1.0 if reversed_face else 1.0
                    k = (sign * k1, sign * k2)
                except Exception:
                    k = (0.0, 0.0)
            curvatures.append(k)
    return points, tris, normals, curvatures


def owner_faces(owner, names):
    """The faces of `owner` to analyse: the named ones, else all."""
    shape = owner.Shape
    if not names:
        return list(shape.Faces)
    out = []
    for name in names:
        try:
            item = shape.getElement(name)
            if item is not None and item.ShapeType == "Face":
                out.append(item)
        except Exception:
            continue
    return out


def mesh(owner, names=(), quality=False, curvature=False, coarse=False):
    """The Mesh of the analysed faces of `owner` (owner coordinates: put them in the
    component with parent_placement). coarse: the model's own triangles, not split."""
    if is_mesh_owner(owner):
        return mesh_of(owner)
    result = Mesh()
    shape = owner.Shape
    if shape.isNull():
        return result
    size = max(1e-6, shape.BoundBox.DiagonalLength)
    max_edge = 0.0 if coarse else size / (110.0 if quality else 40.0)
    tolerance = display_tolerance(owner)
    for face in owner_faces(owner, names):
        try:
            result.add(*face_mesh(face, tolerance, max_edge, curvature))
        except Exception:
            continue
    return result


def obstacle_triangles(owner):
    """[(a, b, c)] of the whole body at the display's tolerance (what can block a tool)."""
    found = []
    tolerance = display_tolerance(owner)
    for face in owner.Shape.Faces:
        try:
            pts, tris = face.tessellate(tolerance)
        except Exception:
            continue
        p = [(q.x, q.y, q.z) for q in pts]
        found += [(p[a], p[b], p[c]) for a, b, c in tris]
    return found


# -- colours per point -------------------------------------------------------------------------
def draft_colors(obj, normals, pull):
    start = float(obj.DraftStart.Value)
    stop = float(obj.DraftStop.Value)
    zone = bool(obj.ToleranceZone)
    return [core.draft_color(core.draft_angle(n, pull), start, stop, zone) for n in normals]


def map_colors(obj, m, size):
    kind = obj.MapType
    if kind == "Gaussian":
        bands = obj.MapDisplay == "Bands"
        scale = float(obj.MapScale)
        return [
            core.gaussian_color(core.gaussian_level(k1, k2, size, scale), bands)
            for k1, k2 in m.curvatures
        ]
    limit = float(obj.LimitRadius.Value)
    return [core.limit_color(core.principal_value(k1, k2, kind), limit) for k1, k2 in m.curvatures]


def radius_colors(obj, m):
    lo = float(obj.MinimumRadius.Value)
    hi = float(obj.ToolRadius.Value)
    return [core.min_radius_color(core.concave_radius(k1, k2), lo, hi) for k1, k2 in m.curvatures]


def _face_normal_at(face, point):
    try:
        u, v = face.Surface.parameter(point)
        n = face.normalAt(u, v)
        return V(n.x, n.y, n.z)
    except Exception:
        return None


def sharp_concave_edges(owner, crease_degrees=1.0):
    """Minimum Radius' Include Sharp Curves: the edges where two faces meet in a sharp inner
    corner (radius 0: no round cutter reaches into it), as polylines in the owner's
    coordinates. An edge is concave when the second face's outward normal points into the
    first face's side of the edge; faces meeting smoothly (tangent) do not count."""
    import Part

    shape = owner.Shape
    if shape.isNull():
        return []
    faces = list(shape.Faces)
    size = max(shape.BoundBox.DiagonalLength, 1e-6)
    eps = size * 1e-4
    limit = math.cos(math.radians(crease_degrees))
    found = []
    for edge in shape.Edges:
        try:
            if edge.Length < eps:
                continue
            owners = [f for f in faces if any(e.isSame(edge) for e in f.Edges)]
            if len(owners) != 2:
                continue
            t = 0.5 * (edge.FirstParameter + edge.LastParameter)
            point = edge.valueAt(t)
            n1 = _face_normal_at(owners[0], point)
            n2 = _face_normal_at(owners[1], point)
            if n1 is None or n2 is None or n1.dot(n2) >= limit:
                continue  # smooth or tangent there: not a sharp corner
            tangent = edge.tangentAt(t)
            into = n1.cross(tangent)
            if into.Length < 1e-12:
                continue
            into.normalize()
            probe = Part.Vertex(point + into * (eps * 10.0))
            if owners[0].distToShape(probe)[0] > eps * 5.0:
                into = into * -1.0  # the other way runs off the first face
            if n2.dot(into) > 1e-6:
                found.append(polyline(edge, size))
        except Exception:
            continue
    return found


def access_colors(obj, m, owner, pull):
    """Green where a tool along the access direction(s) reaches the surface, red where the
    part is in the way or the surface faces away."""
    directions = core.access_directions(pull, obj.AccessMode)
    triangles = obstacle_triangles(owner)
    reach = core.reachable_points(m.points, m.normals, directions, triangles)
    return [core.ACCESSIBLE if ok else core.BLOCKED for ok in reach]


# -- curves: combs and isocurves -----------------------------------------------------------------
def owner_edges(owner, names):
    out = []
    shape = owner.Shape
    for name in names:
        try:
            item = shape.getElement(name)
            if item is not None and item.ShapeType == "Edge":
                out.append(item)
        except Exception:
            continue
    return out


def edge_samples(edge, density):
    """[(point, to_centre, curvature)] along an edge (owner coordinates)."""
    out = []
    for t in core.comb_params(edge.FirstParameter, edge.LastParameter, density):
        p = edge.valueAt(t)
        point = (p.x, p.y, p.z)
        k = 0.0
        to_centre = (0.0, 0.0, 0.0)
        try:
            k = abs(float(edge.curvatureAt(t)))
            if k > 1e-9:
                c = edge.centerOfCurvatureAt(t)
                to_centre = core.unit(core.sub((c.x, c.y, c.z), point))
            else:
                k = 0.0
        except Exception:
            k = 0.0
        out.append((point, to_centre, k))
    return out


def combs(curves, density, scale_factor):
    """Combs of curves: [{"base": [points], "teeth": [(point, tip, colour)], "tips": [...]}]
    with one gain for all (so teeth compare across the picked edges)."""
    sampled = [edge_samples(e, density) for e in curves]
    every = [k for s in sampled for _p, _c, k in s]
    box = None
    for e in curves:
        box = e.BoundBox if box is None else box.united(e.BoundBox)
    reference = box.DiagonalLength if box is not None else 1.0
    gain = core.comb_gain(every, reference, scale_factor)
    peak = max(every or [0.0])
    out = []
    for edge, samples in zip(curves, sampled):
        teeth = []
        tips = []
        for point, to_centre, k in samples:
            tip = core.comb_tooth(point, to_centre, k, gain)
            teeth.append((point, tip, core.comb_color(k, peak)))
            tips.append(tip)
        out.append({"base": polyline(edge, reference), "teeth": teeth, "tips": tips})
    return out


def polyline(edge, size):
    try:
        pts = edge.discretize(Deflection=max(1e-4, size / 2000.0))
    except Exception:
        pts = [edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)]
    return [(p.x, p.y, p.z) for p in pts]


def comb_data(obj):
    """[(owner, combs)] of a Curvature Comb analysis."""
    out = []
    for owner, names in targets(obj):
        curves = owner_edges(owner, names)
        if curves:
            out.append((owner, combs(curves, obj.Density, obj.CombScale)))
    return out


def iso_edges(face, kind, count):
    """The isocurves of a face (owner coordinates), kept to the face's own outline."""
    import Part

    u0, u1, v0, v1 = face.ParameterRange
    surface = face.Surface
    found = []
    wanted = []
    if kind in ("U and V", "U"):
        wanted += [("u", u) for u in core.iso_values(u0, u1, count)]
    if kind in ("U and V", "V"):
        wanted += [("v", v) for v in core.iso_values(v0, v1, count)]
    for which, value in wanted:
        try:
            if which == "u":
                curve = surface.uIso(value)
                edge = Part.Edge(curve, v0, v1)
            else:
                curve = surface.vIso(value)
                edge = Part.Edge(curve, u0, u1)
        except Exception:
            continue
        try:
            inside = face.common(edge).Edges
        except Exception:
            inside = []
        found += [e for e in inside if e.Length > 1e-7] if inside else []
    return found


def iso_data(obj):
    """[(owner, [{"base": points, "teeth": [...], "tips": [...]}])] of an Isocurve analysis."""
    out = []
    count = int(core.clamp(int(obj.IsoCount), 1, 50))
    for owner, names in targets(obj):
        curves = []
        for face in owner_faces(owner, names):
            curves += iso_edges(face, obj.IsoType, count)
        if not curves:
            continue
        if obj.ShowCombs:
            out.append((owner, combs(curves, obj.Density, obj.CombScale)))
        else:
            size = owner.Shape.BoundBox.DiagonalLength
            plain = [{"base": polyline(e, size), "teeth": [], "tips": []} for e in curves]
            out.append((owner, plain))
    return out


def read(obj):
    """{property: value} of an analysis, for its dialog."""
    values = {}
    for _t, name, _tip, _d in PROPS.get(obj.SciForgeType, []):
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        values[name] = getattr(value, "Value", value)
    return values
