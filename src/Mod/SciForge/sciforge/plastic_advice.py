# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design Advice (PLASTIC > INSPECT), the document side (FreeCAD, no Qt: the dialog, headless
tests and the golden checks use it). The checks themselves: plastic_advice_core.py.

A Design Advice is an analysis like SciForge's others: an App::FeaturePython with
SciForgeType "DesignAdviceAnalysis", so the browser keeps it in its Analysis folder (eye,
Edit, Delete) and the timeline leaves it out. It keeps the bodies it checks, the pull
direction and which checks run, and works its results out again whenever one of its bodies
changes (Fusion re-checks the design as it changes). The model never changes:
plastic_advice_ui.py colours the faces from the results kept in "Results" (JSON):

  {"bodies": [{"name", "label", "rule", "pull": [x, y, z],
               "faces": {"Face3": {"issues": {"thin": 0.8, ...}, "t_min", "t_max"}},
               "edges": {"Edge7": 30.0}}]}      (a knife edge's angle in the material)

Saved documents store "sciforge.plastic_advice.DesignAdvice": keep the name stable.
"""

import json
import math
import time

import FreeCAD as App

from . import bodies, labels, log, plastic
from . import plastic_advice_core as core

V = App.Vector
KIND = "DesignAdviceAnalysis"
LABEL = "Design Advice"
DISPLAYS = ("Issues", "Thickness")
CHECK_PROPS = {
    "thickness": "CheckThickness",
    "variation": "CheckVariation",
    "draft": "CheckDraft",
    "knife": "CheckKnifeEdges",
    "undercut": "CheckUndercuts",
}
SAMPLES = 8  # points on a small face
MAX_SAMPLES = 32  # points on a big face (one every SPACING wall thicknesses or so)
BUDGET = 4000  # points in all: a body of many faces gets fewer a face (the check stays short)
SPACING = 3.0


class AdviceError(ValueError):
    pass


def is_advice(obj):
    try:
        return getattr(obj, "SciForgeType", "") == KIND and obj.isAttachedToDocument()
    except Exception:
        return False


def advices(doc):
    return [o for o in doc.Objects if is_advice(o)]


class DesignAdvice:
    """Proxy of a Design Advice analysis. Saved documents store
    "sciforge.plastic_advice.DesignAdvice": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, default=None):
            if name in obj.PropertiesList:
                return False
            obj.addProperty(kind, name, "Design Advice", doc)
            if default is not None:
                setattr(obj, name, default)
            return True

        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "SciForge", "Kind")
            obj.SciForgeType = KIND
        add("App::PropertyLinkSubListGlobal", "Targets", "The bodies checked")
        add("App::PropertyLinkSubGlobal", "PullDirection", "Plane, flat face, edge or axis")
        add("App::PropertyBool", "Flip", "Reverse the pull direction", False)
        add("App::PropertyVector", "PullVector", "The pull direction (worked out)")
        for check, prop in CHECK_PROPS.items():
            add("App::PropertyBool", prop, "Check %s" % core.CHECK_TITLES[check], True)
        if add("App::PropertyEnumeration", "Display", "Issue colours or thickness map"):
            obj.Display = list(DISPLAYS)
        add("App::PropertyString", "Problem", "Why the analysis shows nothing", "")
        add("App::PropertyString", "Results", "What was found (JSON)", "")
        add("App::PropertyString", "Summary", "What was found", "")
        add("App::PropertyBool", "Stale", "Not checked again while hidden", False)
        add("App::PropertyString", "CheckedShapes", "The bodies as last checked", "")
        try:
            obj.setEditorMode("SciForgeType", 2)
            for name in ("Problem", "Results", "Summary", "Stale", "CheckedShapes"):
                obj.setPropertyStatus(name, ["Output", "Hidden"])
            obj.setEditorMode("PullVector", 2)
            # the display only changes the colours drawn from the results kept: no new
            # check (seconds on a big part). "Output": a change does not touch the analysis
            # (NoRecompute does not stop a FeaturePython from running again)
            obj.setPropertyStatus("Display", "Output")
        except Exception:
            pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        """Check the bodies again. Never fails: what is wrong goes to Problem. A hidden
        analysis waits (Stale) until it is shown again: editing a big design does not pay for
        checks nobody sees."""
        if hidden(obj):
            if not obj.Stale:
                obj.Stale = True
            return
        if obj.Stale:
            obj.Stale = False
        problem = ""
        results = {"bodies": []}
        try:
            results = measure(obj)
        except AdviceError as exc:
            problem = str(exc)
        except Exception as exc:
            problem = str(exc) or "Design Advice could not check this design."
        text = json.dumps(results, sort_keys=True)
        if obj.Results != text:
            obj.Results = text
        checked = signature(obj)
        if not _same_shapes(obj.CheckedShapes, checked):
            obj.CheckedShapes = checked
        summary = core.summary_text(results) if not problem else ""
        if obj.Summary != summary:
            obj.Summary = summary
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


def hidden(obj):
    """True when the analysis' eye is off in the GUI (headless: never)."""
    if not App.GuiUp:
        return False
    try:
        return obj.ViewObject is not None and not obj.ViewObject.Visibility
    except Exception:
        return False


def signature(obj):
    """The checked bodies as they are now, in short (volume, area, faces): tells whether the
    results kept still describe them (JSON)."""
    out = []
    for body in targets(obj):
        try:
            shape = body.Shape
            out.append([body.Name, shape.Volume, shape.Area, len(shape.Faces)])
        except Exception:
            out.append([body.Name, 0.0, 0.0, 0])
    return json.dumps(out)


def _same_shapes(a, b, tol=1e-6):
    try:
        a, b = json.loads(a), json.loads(b)
        if len(a) != len(b):
            return False
        for x, y in zip(a, b):
            if x[0] != y[0] or x[3] != y[3]:
                return False
            for u, v in ((x[1], y[1]), (x[2], y[2])):
                if abs(u - v) > tol * max(1.0, abs(u), abs(v)):
                    return False
        return True
    except Exception:
        return False


def out_of_date(obj):
    """True when a shown analysis keeps results of bodies that changed since (an Undo / Redo
    of a change made while it was hidden brings the bodies back, not its results). Never
    for one that has not checked anything yet."""
    try:
        if hidden(obj) or not obj.Results or obj.Problem or not obj.CheckedShapes:
            return False
        return not _same_shapes(obj.CheckedShapes, signature(obj))
    except Exception:
        return False


# -- which bodies -------------------------------------------------------------------------------
def ruled_bodies(doc):
    """Visible solid bodies of components with a plastic rule (Fusion checks those); when no
    component has one, every visible solid body (checked with the default rule)."""
    from . import components

    found, every = [], []
    for body in bodies.solid_bodies(doc, visible_only=True):
        every.append(body)
        try:
            if plastic.assigned_rule_name(doc, components.container_of(body)):
                found.append(body)
        except Exception:
            continue
    return found or every


def targets(obj):
    out = []
    for entry in obj.Targets or []:
        owner = entry[0]
        if bodies.alive(owner) and bodies.has_solid(owner):
            out.append(owner)
    return out


def body_title(owner):
    """How the advice names a body: "Component/Body1" for a body in a component (two
    components can each hold a "Body1"), its label alone at the design's root."""
    try:
        from . import components

        component = components.container_of(owner)
    except Exception:
        component = None
    if component is None:
        return owner.Label
    return "%s/%s" % (component.Label, owner.Label)


def set_targets(obj, owners):
    owners = [o for o in owners if bodies.alive(o)]
    current = [o for o, _s in (obj.Targets or [])]
    if [o.Name for o in current] != [o.Name for o in owners]:
        obj.Targets = [(o, "") for o in owners]


def pull_of(obj):
    from . import surface_analysis

    try:
        vector = surface_analysis.pull_vector(obj)
    except surface_analysis.AnalysisError as exc:
        raise AdviceError(str(exc))
    if (obj.PullVector - vector).Length > 1e-12:
        obj.PullVector = vector
    return vector


def pull_for(obj, body, pull):
    """The pull direction for one body: the picked one, else the Z of the body's component
    (research 2.11: "Z of the component"; a turned component's part is moulded along its
    own Z), turned round with Flip."""
    if obj.PullDirection:
        return pull
    from . import surface_analysis

    z = surface_analysis.parent_placement(body).Rotation.multVec(V(0, 0, 1))
    return z * -1.0 if obj.Flip else z


def checks_of(obj):
    return [c for c, prop in CHECK_PROPS.items() if bool(getattr(obj, prop, True))]


def measure(obj):
    owners = targets(obj)
    if not owners:
        raise AdviceError("Pick the bodies to check (bodies of components with a plastic rule).")
    pull = pull_of(obj)
    checks = checks_of(obj)
    out = {"bodies": []}
    start = time.time()
    for body in owners:
        rule = plastic.rule_for_body(body)
        data = measure_shape(bodies.global_shape(body), rule, pull_for(obj, body, pull), checks)
        data.update({"name": body.Name, "label": body_title(body), "rule": rule["name"]})
        out["bodies"].append(data)
    log(
        "design advice '%s': %d bod%s checked in %.1f s"
        % (obj.Label, len(owners), "y" if len(owners) == 1 else "ies", time.time() - start)
    )
    return out


# -- measuring one body ---------------------------------------------------------------------------
def _normal(face, point, surface=None):
    """(outward normal, the point moved onto the face's surface) at a point near the face;
    surface: face.Surface when the caller has it (it is made anew at each call)."""
    try:
        surface = surface if surface is not None else face.Surface
        u, v = surface.parameter(point)
        n = face.normalAt(u, v)
        return V(n.x, n.y, n.z), surface.value(u, v)
    except Exception:
        return None, point


def face_samples(face, tolerance, count=SAMPLES, spacing=0.0, most=MAX_SAMPLES):
    """[(point, outward normal)] spread over the face: centroids of its display triangles,
    split finer on a big face so it gets about one point every `spacing` (at least `count`,
    at most `most` points)."""
    try:
        pts, tris = face.tessellate(tolerance)
    except Exception:
        return []
    if not tris:
        return []
    points = [(q.x, q.y, q.z) for q in pts]
    tris = [tuple(t) for t in tris]
    want = count
    if spacing > 0:
        try:
            want = int(min(most, max(count, math.ceil(face.Area / (spacing * spacing)))))
        except Exception:
            want = count
        if len(tris) < want:
            from . import analysis_core

            points, tris = analysis_core.subdivide(points, tris, spacing)
    step = max(1, int(math.ceil(len(tris) / float(want))))
    try:
        surface = face.Surface
    except Exception:
        return []
    found = []
    for k in range(0, len(tris), step):
        a, b, c = (points[i] for i in tris[k])
        centre = V(
            (a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0, (a[2] + b[2] + c[2]) / 3.0
        )
        n, on = _normal(face, centre, surface)
        if n is None or n.Length < 1e-12:
            continue
        n.normalize()
        found.append((on, n))
    return found


def premeshed(shape, tolerance):
    """A copy of the shape with its display triangles made once, at `tolerance` and a 0.5 rad
    angular deflection: the faces' tessellate() then takes these. FreeCAD's own tessellate
    splits small circles far finer: a plate with 400 small holes took 46 s to mesh, 5 s
    this way. (A copy: the model's own triangles, which the 3D view draws, stay as they
    are; its faces and edges keep their numbers.)"""
    try:
        import MeshPart

        copy = shape.copy()
        MeshPart.meshFromShape(
            Shape=copy, LinearDeflection=tolerance, AngularDeflection=0.5, Relative=False
        )
        return copy
    except Exception:
        return shape


def sample_counts(faces):
    """(points on a small face, at most on a big one) for a body of `faces` faces: SAMPLES
    and MAX_SAMPLES, fewer when that would pass BUDGET points in all (at least 2 a face)."""
    if faces * SAMPLES <= BUDGET:
        return SAMPLES, MAX_SAMPLES
    count = max(2, int(BUDGET // max(1, faces)))
    return count, max(count, min(MAX_SAMPLES, 2 * count))


def _triangles(shape, tolerance):
    """The display triangles of the shape and, for each, the index of its face."""
    found, owners = [], []
    for i, face in enumerate(shape.Faces):
        try:
            pts, tris = face.tessellate(tolerance)
        except Exception:
            continue
        p = [(q.x, q.y, q.z) for q in pts]
        found += [(p[a], p[b], p[c]) for a, b, c in tris]
        owners += [i] * len(tris)
    return found, owners


class Rays:
    """Rays against one shape: cast on its display triangles (a grid of them, see
    core.RayGrid), the hit then moved onto the exact face it lies on."""

    def __init__(self, shape, tolerance):
        self.faces = shape.Faces
        self.surfaces = {}
        self.tolerance = tolerance
        triangles, self.owners = _triangles(shape, tolerance)
        self.grid = core.RayGrid.of(triangles)
        self.triangles = triangles if self.grid is None else None

    def cast(self, origins, directions, near):
        if not origins:
            return []
        if self.grid is not None:
            return self.grid.cast(origins, directions, near, True)
        nears = near if isinstance(near, (list, tuple)) else [near] * len(origins)
        return [
            core._first_hit_py(o, d, self.triangles, n, True)
            for o, d, n in zip(origins, directions, nears)
        ]

    def distances(self, origins, directions, near, own=None):
        """The exact distance to the first face along each unit ray, or None. own: the index
        of the face each ray starts on. A ray starting on a convex face starts outside the
        triangles that cut its corner; it meets them at once and that hit lands back on its
        own face: such a hit is passed."""
        count = len(origins)
        nears = [near] * count
        out = [None] * count
        todo = list(range(count))
        for _round in range(4):
            found = self.cast(
                [origins[k] for k in todo], [directions[k] for k in todo], [nears[k] for k in todo]
            )
            again = []
            for k, hit in zip(todo, found):
                t = self.exact(origins[k], directions[k], hit)
                if (
                    t is not None
                    and own is not None
                    and self.owners[hit[1]] == own[k]
                    and t < 2.0 * self.tolerance
                ):
                    nears[k] = hit[0] + 1e-9 + 1e-6 * self.tolerance
                    again.append(k)
                else:
                    out[k] = t
            todo = again
            if not todo:
                break
        return out

    def nearest(self, point, radius):
        """(distance, triangle index) of the nearest display triangle within radius, or None."""
        if self.grid is not None:
            return self.grid.nearest(tuple(point), radius)
        best = None
        for k, tri in enumerate(self.triangles):
            d = core.point_triangle_distance(tuple(point), tri)
            if d <= radius and (best is None or d < best[0]):
                best = (d, k)
        return best

    def blocked(self, origins, direction, near):
        found = self.cast(origins, [direction] * len(origins), near)
        return [hit[0] is not None for hit in found]

    def exact(self, origin, direction, hit):
        """The display triangles cut corners off round faces (a ray stops a little short of a
        boss's side, or runs a little past a hole's): Newton steps along the ray onto the
        face of the triangle it met."""
        t0, tri = hit
        if t0 is None:
            return None
        try:
            i = self.owners[tri]
            if i not in self.surfaces:
                self.surfaces[i] = self.faces[i].Surface
            surface = self.surfaces[i]
            o, d = V(*origin), V(*direction)
            t = t0
            for _k in range(4):
                x = o + d * t
                u, v = surface.parameter(x)
                q = surface.value(u, v)
                n = surface.normal(u, v)
                along = d.dot(n)
                if abs(along) < 0.2:
                    return t0
                step = (q - x).dot(n) / along
                t += step
                if abs(step) < 1e-7:
                    break
            return t if abs(t - t0) < 3.0 * self.tolerance + 1e-6 else t0
        except Exception:
            return t0


def measure_shape(shape, rule, pull, checks):
    """{"faces": {...}, "edges": {...}, "pull": [...]} of one solid (design coordinates)."""
    size = max(shape.BoundBox.DiagonalLength, 1e-6)
    tolerance = max(0.005, size / 400.0)
    eps = max(1e-4, size * 1e-6)
    shape = premeshed(shape, tolerance)
    p = (pull.x, pull.y, pull.z)
    samples = []  # (face index, point, normal)
    spacing = max(SPACING * rule.get("thickness", 0.0), size / 30.0)
    count, most = sample_counts(len(shape.Faces))
    for i, face in enumerate(shape.Faces):
        for point, normal in face_samples(face, tolerance, count, spacing, most):
            samples.append((i, point, normal))
    need_t = any(c in checks for c in ("thickness", "variation"))
    rays = Rays(shape, tolerance) if samples and (need_t or "undercut" in checks) else None
    thick = [None] * len(samples)
    if need_t and samples:
        origins = [tuple(pt - n * eps) for _i, pt, n in samples]
        dirs = [tuple(n * -1.0) for _i, _pt, n in samples]
        thick = rays.distances(origins, dirs, eps * 0.5, [i for i, _pt, _n in samples])
        thick = [None if t is None else t + eps for t in thick]
        thick = inscribed(shape, rays, samples, thick, rule)
    along = against = [False] * len(samples)
    if "undercut" in checks and samples:
        # from outside the triangles that cut the corners off a hole's side (inside them a
        # ray up the hole would meet the top face's triangles)
        out = eps + 1.5 * tolerance
        origins = [tuple(pt + n * out) for _i, pt, n in samples]
        along = rays.blocked(origins, p, eps * 0.5)
        against = rays.blocked(origins, (-p[0], -p[1], -p[2]), eps * 0.5)
    faces = {}
    for k, (i, _pt, n) in enumerate(samples):
        name = "Face%d" % (i + 1)
        entry = faces.setdefault(name, {"issues": {}, "t_min": None, "t_max": None, "samples": []})
        issues = entry["issues"]
        t = thick[k]
        nt = (n.x, n.y, n.z)
        if t is not None:
            entry["t_min"] = t if entry["t_min"] is None else min(entry["t_min"], t)
            entry["t_max"] = t if entry["t_max"] is None else max(entry["t_max"], t)
            pt = samples[k][1]
            entry["samples"].append([round(pt.x, 4), round(pt.y, 4), round(pt.z, 4), round(t, 4)])
        if "thickness" in checks:
            kind = core.thickness_issue(t, rule)
            if kind == "thin":
                issues["thin"] = min(issues.get("thin", t), t)
            elif kind == "thick":
                issues["thick"] = max(issues.get("thick", t), t)
        if "variation" in checks and core.variation_issue(t, rule):
            worst = issues.get("variation")
            if worst is None or abs(t - rule["thickness"]) > abs(worst - rule["thickness"]):
                issues["variation"] = t
        if "draft" in checks and core.draft_issue(nt, p, rule["minimum_draft_angle"]):
            angle = core.draft_of(nt, p)
            issues["draft"] = min(issues.get("draft", angle), angle)
        if "undercut" in checks and core.undercut_issue(nt, p, along[k], against[k]):
            issues["undercut"] = None
    edges = {}
    if "knife" in checks:
        edges = knife_edges(shape, eps)
    faces = {
        name: data for name, data in faces.items() if data["issues"] or data["t_min"] is not None
    }
    return {"faces": faces, "edges": edges, "pull": list(p)}


def _long(t, rule):
    """True when a reading is longer than the rule allows (only such a reading can be a ray
    that ran along inside a wall; a shorter one is right, or the wall's sides show it)."""
    if t is None:
        return False
    if core.thickness_issue(t, rule) == "thick":
        return True
    return t > rule["thickness"] and core.variation_issue(t, rule)


def inscribed(shape, rays, samples, thick, rule):
    """The wall thickness at each sample: the ray's length along the inward normal, unless
    the ray ran along inside a wall (a rim's top, a hole through a wall: halfway along it
    the nearest face is much closer than half the ray); then the wall across there: from the
    nearest face straight through to the face opposite. Where that way across runs along
    inside a wall again (a point beside the edge where two walls meet), no reading."""
    out = list(thick)
    across = []  # (sample, distance to the nearest face, middle, away)
    for k, ((_i, point, normal), t) in enumerate(zip(samples, thick)):
        if not _long(t, rule):
            continue
        middle = point - normal * (0.5 * t)
        try:
            found = rays.nearest(middle, 0.25 * t)
            if found is None:
                continue
            face = rays.faces[rays.owners[found[1]]]
            _n, foot = _normal(face, middle)
            away = middle - foot
            d = away.Length
            if not (1e-9 < 2.0 * d < 0.5 * t):
                continue
            away.normalize()
            across.append((k, d, middle, away))
        except Exception:
            continue
    if across:
        found = rays.distances(
            [tuple(m) for _k, _d, m, _a in across], [tuple(a) for _k, _d, _m, a in across], 1e-9
        )
        for (k, d, _m, _a), t in zip(across, found):
            total = d + t if t is not None else 2.0 * d
            if t is not None and t > 4.0 * d and _long(total, rule):
                # where walls meet (a box's corner): the way across runs along inside the
                # other wall too; no reading here (the walls' other points show them)
                out[k] = None
            else:
                out[k] = total
    return out


def knife_edges(shape, eps):
    """{"EdgeN": angle in the material (degrees)} of the convex edges sharper than
    core.KNIFE_ANGLE."""
    import Part

    found = {}
    for i, edge in enumerate(shape.Edges):
        try:
            if edge.Length < eps * 10:
                continue
            owners = shape.ancestorsOfType(edge, Part.Face)
            if len(owners) != 2 or owners[0].isSame(owners[1]):
                continue
            t = 0.5 * (edge.FirstParameter + edge.LastParameter)
            mid = edge.valueAt(t)
            n1, _ = _normal(owners[0], mid)
            n2, _ = _normal(owners[1], mid)
            if n1 is None or n2 is None:
                continue
            n1.normalize()
            n2.normalize()
            between = math.degrees(math.acos(max(-1.0, min(1.0, n1.dot(n2)))))
            if between < 1.0:
                continue  # tangent faces
            angle = 180.0 - between
            if not core.knife_issue(angle):
                continue
            into = (n1 + n2) * -1.0
            if into.Length < 1e-9:
                continue
            into.normalize()
            probe = mid + into * (eps * 20)
            if not shape.isInside(probe, eps, False):
                continue  # concave (a deep notch): no knife edge
            found["Edge%d" % (i + 1)] = angle
        except Exception:
            continue
    return found


# -- making ---------------------------------------------------------------------------------------
def next_label(doc):
    import re

    used = 0
    for obj in doc.Objects:
        match = re.match(r"^%s(\d+)$" % re.escape(LABEL), obj.Label or "")
        if match:
            used = max(used, int(match.group(1)))
    return "%s%d" % (LABEL, used + 1)


def make(doc, owners=None, options=None):
    """A new Design Advice over `owners` (default: ruled_bodies). Not recomputed."""
    obj = doc.addObject("App::FeaturePython", "DesignAdvice")
    DesignAdvice(obj)
    labels.set_exact(obj, next_label(doc))
    set_targets(obj, owners if owners is not None else ruled_bodies(doc))
    apply(obj, options or {})
    if App.GuiUp:
        try:
            from .plastic_advice_ui import ViewProviderDesignAdvice

            ViewProviderDesignAdvice(obj.ViewObject)
        except Exception:
            pass
    log("design advice '%s' made" % obj.Label)
    return obj


def apply(obj, options):
    """options: {"thickness": bool, ..., "flip": bool, "display": "Issues" | "Thickness"}."""
    for check, prop in CHECK_PROPS.items():
        if check in options and bool(getattr(obj, prop)) != bool(options[check]):
            setattr(obj, prop, bool(options[check]))
    if "flip" in options and bool(obj.Flip) != bool(options["flip"]):
        obj.Flip = bool(options["flip"])
    if options.get("display") in DISPLAYS and obj.Display != options["display"]:
        obj.Display = options["display"]


def results(obj):
    try:
        return json.loads(obj.Results or "{}") or {"bodies": []}
    except Exception:
        return {"bodies": []}
