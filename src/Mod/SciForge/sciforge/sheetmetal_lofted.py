# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's lofted flange (the Lofted type of Fusion's Flange dialog; in SciForge its own
command, SHEET METAL > CREATE > Lofted Flange, right under Flange): a sheet of the rule's
thickness lofted between two profiles on separate planes. FreeCAD side, no Qt: the dialog
(sheetmetal_lofted_ui.py) and the golden-model builder both call make().

* Profiles: two sketches (or chains of their edges), both open or both closed, made of lines
  and arcs only (Fusion: splines need Contour). Coplanar profiles are refused.
* Brake Form (a press-brake part): every arc is replaced by straight facets (Facet Control:
  Chord Tolerance, Facet Angle, Facet Distance or Face Number); the two profiles are matched
  point for point (each profile's corners kept) and joined by flat triangular facets. The
  facets meet in sharp folds (SciForge does not round them with the bend radius yet: Known
  gaps in docs/sciforge/parity/sheet-metal-more.md).
* Die Form (a stamped part): one smooth ruled surface between the two profiles. It is curved
  in two directions and cannot be laid flat exactly: the step says so (Developable = False)
  and the flat pattern refuses it with that reason.
* Orientation Side 1 / Side 2 / Center: which side of the profiles the thickness goes.
* Operation New Body (a new sheet metal body with the active rule) or Join (into the active
  sheet metal body).
Sources: docs/sciforge/dev/research/fusion-sheet-metal.md 2.2.4.
"""

import FreeCAD as App

from . import bodies, log, sheetmetal, sheetmetal_bend as sb, sheetmetal_bend_core as core

V = App.Vector
TYPE = "PartDesign::FeaturePython"
KIND = "SheetMetalLoftedFlange"
FORMING = [core.FORMING_LABELS[k] for k in core.FORMING_TYPES]
CONTROLS = [core.FACET_LABELS[k] for k in core.FACET_CONTROLS]
ORIENTATIONS = ["Side 1", "Side 2", "Center"]
DIE_TOLERANCE = 0.02  # chord tolerance (mm) of an open Die Form profile's fine facets


def default_options():
    return {
        "forming": "brake",
        "control": "chord_tolerance",
        "value": core.FACET_DEFAULTS["chord_tolerance"],
        "orientation": "side1",
        "operation": "new_body",
    }


def profile_wire(edges):
    """One wire from a profile's edges (lines and arcs only)."""
    import Part

    if not edges:
        raise sb.SheetMetalError("A profile is empty.")
    for edge in edges:
        if not isinstance(edge.Curve, (Part.Line, Part.LineSegment, Part.Circle, Part.ArcOfCircle)):
            raise sb.SheetMetalError(
                "Lofted flange profiles may hold only lines and arcs (use Contour for splines)."
            )
    groups = Part.sortEdges(list(edges))
    if len(groups) != 1:
        raise sb.SheetMetalError("A profile must be one connected chain of lines and arcs.")
    return Part.Wire(groups[0])


def _polyline(wire, control, value):
    """The wire as points (each arc replaced by facets), in order; closed wires repeat their
    first point at the end."""
    import Part

    pts = []
    for edge in wire.OrderedEdges:
        a = edge.Vertexes[0].Point
        if isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
            seg = [edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)]
        else:
            radius = edge.Curve.Radius
            sweep = abs(edge.LastParameter - edge.FirstParameter) * 180.0 / 3.141592653589793
            n = core.facets_for_arc(radius, sweep, control, value)
            seg = edge.discretize(n + 1)
        if edge.Orientation == "Reversed":
            seg = list(reversed(seg))
        if pts and (pts[-1] - seg[0]).Length > 1e-6 and (pts[-1] - seg[-1]).Length < 1e-6:
            seg = list(reversed(seg))
        if pts and (pts[-1] - seg[0]).Length < 1e-6:
            seg = seg[1:]
        del a
        pts += seg
    return pts


def _lengths(pts):
    out = [0.0]
    for a, b in zip(pts, pts[1:]):
        out.append(out[-1] + (b - a).Length)
    total = out[-1] or 1.0
    return [x / total for x in out]


def _at(pts, params, t):
    for i in range(len(params) - 1):
        if params[i] - 1e-12 <= t <= params[i + 1] + 1e-12:
            span = params[i + 1] - params[i]
            f = 0.0 if span < 1e-15 else (t - params[i]) / span
            return pts[i] + (pts[i + 1] - pts[i]) * f
    return pts[-1]


def matched(p1, p2):
    """Both polylines sampled at the union of their (normalised arc-length) vertex
    parameters: the same number of points, every original corner kept."""
    t1, t2 = _lengths(p1), _lengths(p2)
    ts = sorted(set([round(t, 9) for t in t1 + t2]))
    return [_at(p1, t1, t) for t in ts], [_at(p2, t2, t) for t in ts]


def _align_closed(p1, p2):
    """Start the second closed polyline at its point nearest the first's start, going the
    same way round."""
    ring = p2[:-1]
    start = min(range(len(ring)), key=lambda i: (ring[i] - p1[0]).Length)
    ring = ring[start:] + ring[:start]
    c1 = sum(p1[:-1], V()) * (1.0 / (len(p1) - 1))
    c2 = sum(ring, V()) * (1.0 / len(ring))

    def turn(points, centre):
        total = V()
        for a, b in zip(points, points[1:] + points[:1]):
            total += (a - centre).cross(b - centre)
        return total

    if turn(p1[:-1], c1).dot(turn(ring, c2)) < 0:
        ring = [ring[0]] + list(reversed(ring[1:]))
    return ring + [ring[0]]


def _solve3(rows, rhs):
    """Least-squares x for rows . x = rhs (3 unknowns), by the normal equations."""
    a = [[sum(r[i] * r[j] for r in rows) for j in range(3)] for i in range(3)]
    b = [sum(r[i] * v for r, v in zip(rows, rhs)) for i in range(3)]

    def det(m):
        return (
            m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
        )

    d = det(a)
    if abs(d) < 1e-14:
        return None
    out = []
    for k in range(3):
        m = [row[:] for row in a]
        for i in range(3):
            m[i][k] = b[i]
        out.append(det(m) / d)
    return V(*out)


def _strip(w1, w2, control, value):
    """(a, b, closed): the two profiles as matched point lists (Brake Form facets)."""
    p1 = _polyline(w1, control, value)
    p2 = _polyline(w2, control, value)
    closed = w1.isClosed()
    if closed:
        p2 = _align_closed(p1, p2)
    elif (p1[0] - p2[0]).Length + (p1[-1] - p2[-1]).Length > (p1[0] - p2[-1]).Length + (
        p1[-1] - p2[0]
    ).Length:
        p2 = list(reversed(p2))
    a, b = matched(p1, p2)
    return a, b, closed


def _thick_strip(a, b, closed, thickness, side, plane1, plane2):
    """A solid of flat facets between the matched point lists a and b, side * T thick: every
    facet moved T along its normal, each corner put where its facets' moved planes meet (and
    kept in its profile's plane), so each facet is T thick."""
    import Part

    if closed:
        a, b = a[:-1], b[:-1]
    n = len(a)
    pts = list(a) + list(b)
    tris = []  # index triples: 0..n-1 on profile 1, n..2n-1 on profile 2
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        for tri in ((i, j, n + j), (i, n + j, n + i)):
            p0, p1, p2 = pts[tri[0]], pts[tri[1]], pts[tri[2]]
            if (p1 - p0).cross(p2 - p0).Length > 1e-9:
                tris.append(tri)
    if not tris:
        raise sb.SheetMetalError("The profiles give no facets.")
    normals = []
    for tri in tris:
        p0, p1, p2 = pts[tri[0]], pts[tri[1]], pts[tri[2]]
        normals.append(sb.unit((p1 - p0).cross(p2 - p0)) * side)
    moved = []
    for k, p in enumerate(pts):
        rows, rhs, near = [], [], []
        for tri, nrm in zip(tris, normals):
            if k in tri:
                rows.append((nrm.x, nrm.y, nrm.z))
                rhs.append(nrm.dot(p) + thickness)
                near.append(nrm)
        plane = plane1 if k < n else plane2
        if plane is not None:
            pn, pp = plane
            rows.append((pn.x * 1000.0, pn.y * 1000.0, pn.z * 1000.0))
            rhs.append(pn.dot(pp) * 1000.0)
        x = _solve3(rows, rhs) if len(rows) >= 3 else None
        if x is None or (x - p).Length > 4.0 * thickness:
            x = p + sb.unit(sum(near, V())) * thickness
        moved.append(x)
    faces = []

    def tri_face(p0, p1, p2):
        if (p1 - p0).cross(p2 - p0).Length > 1e-10:
            faces.append(Part.Face(Part.makePolygon([p0, p1, p2, p0])))

    def quad_faces(p0, p1, p2, p3):
        try:
            face = Part.Face(Part.makePolygon([p0, p1, p2, p3, p0]))
            if face.Surface.TypeId == "Part::GeomPlane" and face.Area > 1e-10:
                faces.append(face)
                return
        except Exception:
            pass
        tri_face(p0, p1, p2)
        tri_face(p0, p2, p3)

    for tri in tris:
        tri_face(pts[tri[0]], pts[tri[1]], pts[tri[2]])
        tri_face(moved[tri[0]], moved[tri[2]], moved[tri[1]])
    if closed:
        loops = [list(range(n)) + [0], list(range(n, 2 * n)) + [n]]
    else:
        loops = [list(range(n)), list(range(n, 2 * n))]
        for i, j in ((0, n), (n - 1, 2 * n - 1)):
            quad_faces(pts[i], pts[j], moved[j], moved[i])
    for loop in loops:
        for i, j in zip(loop, loop[1:]):
            if (pts[j] - pts[i]).Length > 1e-9:
                quad_faces(pts[i], pts[j], moved[j], moved[i])
    shell = Part.Shell(faces)
    shell.sewShape()
    try:
        if shell.ShapeType != "Shell":
            shell = shell.Shells[0]
        solid = Part.Solid(shell)
    except Exception:
        raise sb.SheetMetalError("The facets could not be closed into a sheet.")
    if solid.Volume < 0:
        solid.reverse()
    return solid


def _profile_plane(wire):
    try:
        plane = wire.findPlane()
    except Exception:
        plane = None
    if plane is None:
        return None
    return (sb.unit(plane.Axis), wire.Vertexes[0].Point)


def _section(wire, thickness, side):
    """The profile thickened in its own plane (Die Form): (outer, inner) wires of a closed
    profile, or (a closed wire round an open profile, None)."""
    import Part

    if wire.isClosed():
        grown = Part.Face(wire).makeOffset2D(thickness * side, join=0)
        if side > 0:
            return grown.OuterWire, wire
        return wire, grown.OuterWire
    off = wire.makeOffset2D(thickness * side, join=0, openResult=True)
    return off.Wires[0], None


def _brake(w1, w2, options, thickness, orientation):
    control = options.get("control", "chord_tolerance")
    value = float(options.get("value", core.FACET_DEFAULTS.get(control, 1.0)))
    try:
        a, b, closed = _strip(w1, w2, control, value)
    except ValueError as exc:
        raise sb.SheetMetalError(str(exc))
    plane1, plane2 = _profile_plane(w1), _profile_plane(w2)
    if orientation == "center":
        one = _thick_strip(a, b, closed, thickness / 2.0, 1.0, plane1, plane2)
        two = _thick_strip(a, b, closed, thickness / 2.0, -1.0, plane1, plane2)
        return one.fuse(two).removeSplitter()
    side = 1.0 if orientation == "side1" else -1.0
    return _thick_strip(a, b, closed, thickness, side, plane1, plane2)


def _die(w1, w2, thickness, orientation):
    import Part

    if w1.isClosed():
        ring = _align_closed(_polyline(w1, "facet_number", 1), _polyline(w2, "facet_number", 1))
        w2 = _rewire_from(w2, ring[0])
    sides = (
        [(thickness / 2.0, 1.0), (thickness / 2.0, -1.0)]
        if orientation == "center"
        else [(thickness, 1.0 if orientation == "side1" else -1.0)]
    )
    if not w1.isClosed():
        # an open profile (a straight line has no plane of its own to thicken in): very
        # fine facets, which look smooth
        fine = {"control": "chord_tolerance", "value": DIE_TOLERANCE}
        return _brake(w1, w2, fine, thickness, orientation)
    try:
        outer1, outer2, inner1, inner2 = w1, w2, w1, w2
        for t, sign in sides:
            s1 = _section(w1, t, sign)
            s2 = _section(w2, t, sign)
            if sign > 0:
                outer1, outer2 = s1[0], s2[0]
            else:
                inner1, inner2 = s1[1], s2[1]
        outer = Part.makeLoft([outer1, outer2], True, True)
        inner = Part.makeLoft([inner1, inner2], True, True)
        return outer.cut(inner)
    except sb.SheetMetalError:
        raise
    except Exception as exc:
        raise sb.SheetMetalError("The die-formed flange could not be made here (%s)." % exc)


def lofted_shape(edges1, edges2, options, thickness):
    """The lofted flange as a solid (design coordinates). Raises sb.SheetMetalError."""
    import Part

    w1 = profile_wire(edges1)
    w2 = profile_wire(edges2)
    if w1.isClosed() != w2.isClosed():
        raise sb.SheetMetalError("Both profiles must be open, or both closed.")
    common = w1.common(w2)
    if common.Edges:
        raise sb.SheetMetalError("The two profiles touch; they must be on separate planes.")
    try:
        both = Part.Compound([w1, w2])
        flat = both.findPlane()
    except Exception:
        flat = None
    if flat is not None:
        raise sb.SheetMetalError("The two profiles lie in one plane; put them on separate planes.")
    orientation = options.get("orientation", "side1")
    if options.get("forming", "brake") == "brake":
        solid = _brake(w1, w2, options, thickness, orientation)
    else:
        solid = _die(w1, w2, thickness, orientation)
    solids = list(solid.Solids) if not solid.isNull() else []
    if not solids:
        raise sb.SheetMetalError("The flange could not be made this thick here.")
    out = solids[0] if len(solids) == 1 else solids[0].fuse(solids[1:])
    if out.Volume < 0:
        out.reverse()
    return sb.one_solid(out, "This lofted flange")


def _rewire_from(wire, point):
    """A closed wire starting at its vertex nearest `point` (for the ruled surface)."""
    import Part

    edges = list(wire.OrderedEdges)
    best = min(range(len(edges)), key=lambda i: (edges[i].Vertexes[0].Point - point).Length)
    return Part.Wire(edges[best:] + edges[:best])


class LoftedFlangeFeature:
    """Saved in files as "sciforge.sheetmetal_lofted.LoftedFlangeFeature": keep the name."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Lofted Flange", doc)
                return True
            return False

        # Global links: the profiles' sketches may sit in another body
        add("App::PropertyLinkSubListGlobal", "Profile1", "First profile")
        add("App::PropertyLinkSubListGlobal", "Profile2", "Second profile")
        if add("App::PropertyEnumeration", "FormingType", "Brake Form or Die Form"):
            obj.FormingType = FORMING
            obj.FormingType = FORMING[0]
        if add("App::PropertyEnumeration", "FacetControl", "How Brake Form facets are sized"):
            obj.FacetControl = CONTROLS
            obj.FacetControl = CONTROLS[0]
        if add("App::PropertyFloat", "FacetValue", "Tolerance (mm), angle (°), width or count"):
            obj.FacetValue = core.FACET_DEFAULTS["chord_tolerance"]
        if add("App::PropertyEnumeration", "Orientation", "Side of the profiles"):
            obj.Orientation = ORIENTATIONS
            obj.Orientation = "Side 1"
        add("App::PropertyBool", "Join", "Join to the body before (else a new body)")
        if add("App::PropertyBool", "Developable", "Can be laid flat (Brake Form)"):
            obj.Developable = True
        try:
            obj.setEditorMode("Developable", 1)
        except Exception:
            pass
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
        "forming": _key(str(obj.FormingType), core.FORMING_LABELS),
        "control": _key(str(obj.FacetControl), core.FACET_LABELS),
        "value": float(obj.FacetValue),
        "orientation": {"Side 1": "side1", "Side 2": "side2", "Center": "center"}[
            str(obj.Orientation)
        ],
        "operation": "join" if obj.Join else "new_body",
    }


def profile_edges(links):
    """Edges (design coordinates) of a profile link: named edges, or a whole sketch."""
    out = []
    for owner, subs in links or []:
        shape = bodies.global_shape(owner)
        names = [s for s in subs if s.startswith("Edge")]
        if names:
            for name in names:
                try:
                    out.append(shape.getElement(name))
                except Exception:
                    raise sb.SheetMetalError("A profile edge is gone; pick the profile again.")
        else:
            out += list(shape.Edges)
    return out


def build(obj):
    body = bodies.body_of(obj)
    thickness = sb.rule_values(body)[0]
    opts = options_of(obj)
    obj.Developable = opts["forming"] == "brake"
    solid = lofted_shape(profile_edges(obj.Profile1), profile_edges(obj.Profile2), opts, thickness)
    local = bodies.to_local(solid, body)
    base = obj.BaseFeature
    if obj.Join and base is not None and not base.Shape.isNull() and base.Shape.Solids:
        shape = base.Shape.copy()
        shape.Placement = App.Placement()
        local = sb.one_solid(sb.fuse_all(shape, [local], refine=bool(obj.Refine)), "Join")
    elif obj.Refine:
        try:
            local = local.removeSplitter()
        except Exception:
            pass
    return local


def _whole(links):
    """[(owner, [edge names])]: an owner given with no names stands for all its edges (a
    link with no sub-elements would be dropped by FreeCAD)."""
    out = []
    for owner, subs in links:
        subs = [s for s in subs if s]
        if not subs:
            try:
                if owner.Shape.isNull():
                    owner.recompute()
            except Exception:
                pass
            subs = ["Edge%d" % i for i in range(1, len(owner.Shape.Edges) + 1)]
        out.append((owner, subs))
    return out


def apply(obj, profile1, profile2, options):
    obj.Profile1 = _whole(profile1)
    obj.Profile2 = _whole(profile2)
    obj.FormingType = core.FORMING_LABELS[options.get("forming", "brake")]
    obj.FacetControl = core.FACET_LABELS[options.get("control", "chord_tolerance")]
    obj.FacetValue = float(options.get("value", core.FACET_DEFAULTS["chord_tolerance"]))
    obj.Orientation = {"side1": "Side 1", "side2": "Side 2", "center": "Center"}[
        options.get("orientation", "side1")
    ]
    obj.Join = options.get("operation") == "join"


def target_body(doc, operation, active=None, rule_name=None):
    """The body the flange goes into: the active sheet metal body (Join), else a new sheet
    metal body in the active component with its active rule."""
    from . import components

    if operation == "join" and active is not None and sheetmetal.is_sheet_metal_body(active):
        return active
    component = components.active_component(doc) if App.GuiUp else None
    body = components.new_body_in(doc, component)
    sheetmetal.make_sheet_metal_body(body, rule_name or sheetmetal.active_rule_name(doc, component))
    return body


def make(body, profile1, profile2, options=None, name="LoftedFlange", hide=True):
    """A Lofted Flange step at the history marker of `body` (a sheet metal body).
    profile1 / profile2: [(sketch, ["Edge1", ...] or [])]."""
    opts = default_options()
    opts.update(options or {})
    base = body.Tip
    obj = bodies.insert_after_tip(body, TYPE, name)
    LoftedFlangeFeature(obj)
    if base is not None and opts.get("operation") == "join":
        obj.BaseFeature = base
    apply(obj, profile1, profile2, opts)
    _view(obj)
    if hide:
        hide_sketches(obj)
    log("lofted flange %s made" % obj.Name)
    return obj


def hide_sketches(obj):
    """Hide the profiles' sketches (Fusion consumes them)."""
    for owner, _subs in list(obj.Profile1 or []) + list(obj.Profile2 or []):
        try:
            if owner.ViewObject is not None:
                owner.ViewObject.Visibility = False
        except Exception:
            pass


def read(obj):
    return (
        [(o, list(s)) for o, s in obj.Profile1],
        [(o, list(s)) for o, s in obj.Profile2],
        options_of(obj),
    )


def _view(obj):
    if not App.GuiUp:
        return
    try:
        from . import sheetmetal_lofted_ui

        sheetmetal_lofted_ui.ViewProviderLofted(obj.ViewObject)
    except Exception:
        pass
