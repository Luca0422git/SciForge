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
SAMPLES = 8  # at most this many points per face


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
        try:
            obj.setEditorMode("SciForgeType", 2)
            for name in ("Problem", "Results", "Summary"):
                obj.setPropertyStatus(name, ["Output", "Hidden"])
            obj.setEditorMode("PullVector", 2)
        except Exception:
            pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        """Check the bodies again. Never fails: what is wrong goes to Problem."""
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


def checks_of(obj):
    return [c for c, prop in CHECK_PROPS.items() if bool(getattr(obj, prop, True))]


def measure(obj):
    owners = targets(obj)
    if not owners:
        raise AdviceError("Pick the bodies to check (bodies of components with a plastic rule).")
    pull = pull_of(obj)
    checks = checks_of(obj)
    out = {"bodies": []}
    for body in owners:
        rule = plastic.rule_for_body(body)
        data = measure_shape(bodies.global_shape(body), rule, pull, checks)
        data.update({"name": body.Name, "label": body.Label, "rule": rule["name"]})
        out["bodies"].append(data)
    return out


# -- measuring one body ---------------------------------------------------------------------------
def _normal(face, point):
    try:
        u, v = face.Surface.parameter(point)
        n = face.normalAt(u, v)
        return V(n.x, n.y, n.z), face.Surface.value(u, v)
    except Exception:
        return None, point


def face_samples(face, tolerance, count=SAMPLES):
    """[(point, outward normal)] spread over the face: centroids of its display triangles."""
    try:
        pts, tris = face.tessellate(tolerance)
    except Exception:
        return []
    if not tris:
        return []
    step = max(1, int(math.ceil(len(tris) / float(count))))
    found = []
    for k in range(0, len(tris), step):
        a, b, c = (pts[i] for i in tris[k])
        centre = (a + b + c) * (1.0 / 3.0)
        n, on = _normal(face, centre)
        if n is None or n.Length < 1e-12:
            continue
        n.normalize()
        found.append((on, n))
    return found


def _triangles(shape, tolerance):
    found = []
    for face in shape.Faces:
        try:
            pts, tris = face.tessellate(tolerance)
        except Exception:
            continue
        p = [(q.x, q.y, q.z) for q in pts]
        found += [(p[a], p[b], p[c]) for a, b, c in tris]
    return found


def measure_shape(shape, rule, pull, checks):
    """{"faces": {...}, "edges": {...}, "pull": [...]} of one solid (design coordinates)."""
    size = max(shape.BoundBox.DiagonalLength, 1e-6)
    tolerance = max(0.005, size / 400.0)
    eps = max(1e-4, size * 1e-6)
    triangles = _triangles(shape, tolerance)
    p = (pull.x, pull.y, pull.z)
    samples = []  # (face index, point, normal)
    for i, face in enumerate(shape.Faces):
        for point, normal in face_samples(face, tolerance):
            samples.append((i, point, normal))
    need_t = any(c in checks for c in ("thickness", "variation"))
    thick = [None] * len(samples)
    if need_t and samples:
        origins = [tuple(pt - n * eps) for _i, pt, n in samples]
        dirs = [tuple(n * -1.0) for _i, _pt, n in samples]
        thick = core.first_hits(origins, dirs, triangles, near=eps * 0.5)
        thick = [None if t is None else t + eps for t in thick]
        thick = confirmed(shape, samples, thick, rule, eps)
        thick = inscribed(shape, samples, thick)
    along = against = [False] * len(samples)
    if "undercut" in checks and samples:
        origins = [tuple(pt + n * eps) for _i, pt, n in samples]
        up = core.first_hits(origins, [p] * len(samples), triangles, near=eps * 0.5)
        down = core.first_hits(origins, [(-p[0], -p[1], -p[2])] * len(samples), triangles, near=eps * 0.5)
        along = [t is not None for t in up]
        against = [t is not None for t in down]
    faces = {}
    for k, (i, _pt, n) in enumerate(samples):
        name = "Face%d" % (i + 1)
        entry = faces.setdefault(name, {"issues": {}, "t_min": None, "t_max": None})
        issues = entry["issues"]
        t = thick[k]
        nt = (n.x, n.y, n.z)
        if t is not None:
            entry["t_min"] = t if entry["t_min"] is None else min(entry["t_min"], t)
            entry["t_max"] = t if entry["t_max"] is None else max(entry["t_max"], t)
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
    faces = {name: data for name, data in faces.items() if data["issues"] or data["t_min"] is not None}
    return {"faces": faces, "edges": edges, "pull": list(p)}


def confirmed(shape, samples, thick, rule, eps):
    """The display triangles cut corners off round faces, so a ray next to a hole can stop
    short: a thickness that breaks the rule is measured again on the exact shape."""
    import Part

    out = list(thick)
    for k, ((_i, point, normal), t) in enumerate(zip(samples, thick)):
        if t is None:
            continue
        if not (core.thickness_issue(t, rule) or core.variation_issue(t, rule)):
            continue
        start = point - normal * eps
        seg = Part.LineSegment(start, start - normal * (max(t, 1.0) * 4.0 + 1.0)).toShape()
        try:
            inside = shape.common(seg)
        except Exception:
            continue
        best = None
        for edge in inside.Edges:
            ends = [v.Point for v in edge.Vertexes]
            if not ends:
                continue
            near = min((q - start).Length for q in ends)
            if near < 10 * eps:
                best = edge.Length + eps if best is None else min(best, edge.Length + eps)
        if best is not None:
            out[k] = best
    return out


def inscribed(shape, samples, thick):
    """The wall thickness at each sample: the ray's length along the inward normal, unless
    the ray ran along inside a wall (a rim's top, a hole through a wall: halfway along it
    the nearest face is much closer than half the ray); then the wall across there: from the
    nearest face straight through to the face opposite."""
    import Part

    boundary = Part.makeCompound(list(shape.Faces))
    out = []
    for (_i, point, normal), t in zip(samples, thick):
        if t is None:
            out.append(None)
            continue
        middle = point - normal * (0.5 * t)
        try:
            d, pairs, _info = boundary.distToShape(Part.Vertex(middle))
            if not (1e-9 < 2.0 * d < 0.5 * t):
                out.append(t)
                continue
            near = pairs[0][0]
            away = middle - near
            away.normalize()
            seg = Part.LineSegment(middle, middle + away * (t + 1.0)).toShape()
            inside = shape.common(seg)
            across = None
            for edge in inside.Edges:
                ends = [v.Point for v in edge.Vertexes]
                if any((q - middle).Length < 1e-6 for q in ends):
                    across = edge.Length
                    break
            out.append(d + across if across is not None else 2.0 * d)
        except Exception:
            out.append(t)
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
            into = (n1 + n2) * -1.0
            if into.Length < 1e-9:
                continue
            into.normalize()
            probe = mid + into * (eps * 20)
            if not shape.isInside(probe, eps, False):
                continue  # concave: no knife edge
            angle = 180.0 - between
            if core.knife_issue(angle):
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
