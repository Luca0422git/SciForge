# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Pipe (SOLID > CREATE > Pipe) on PartDesign's AdditivePipe. No GUI code: the
Pipe dialog (pipe_ui.py) and the golden-model builder both call this module.

The path: edges the user clicked, a list of (object, "EdgeN") of sketches (sketch lines,
arcs, splines) or of bodies (model edges). Chain Selection adds the edges joined to a
clicked one without a corner (tangent), like Fusion. The pipe starts at the end of the
path nearest the start of the first clicked edge.

Options (dict, see DEFAULTS):
  distance      how far along the path the pipe goes, 0..1 (1 = the whole path)
  chain         Chain Selection (only used while picking)
  section       circular | square | triangular
  section_size  the section's size: the diameter of the circle round it (Fusion's coil
                and pipe sections are measured that way)
  hollow        True: a tube with walls `thickness` thick
  thickness     the wall of a hollow pipe
  operation     join | cut | intersect | new_body

What is built: PartDesign::AdditivePipe (join, new body) or SubtractivePipe (cut), or
SciForge's PipeFeature (intersect), sweeping SciForge's own section along SciForge's own
path object (both hidden 2D objects in the body, computed from the dialog's values: the
pipe has no sketch of its own, like in Fusion). Options are kept as JSON in the hidden
property "SciForgePipe"; the step reports itself to the timeline as "Pipe".
"""
import math

import FreeCAD as App

from . import primitives
from . import primitives_core as core
from .primitives import PrimitiveError

SECTIONS = core.PIPE_SECTIONS
OPERATIONS = primitives.OPERATIONS
META = "SciForgePipe"
KIND = "Pipe"
PATH_ROLE = "PipePath"
SECTION_ROLE = "PipeSection"
FP_TYPE = "PartDesign::FeaturePython"
TANGENT_TOL = 1e-3  # radians: edges this close to tangent continue a chain
JOIN_TOL = 1e-6

DEFAULTS = {
    "distance": 1.0,
    "chain": True,
    "section": "circular",
    "section_size": 2.0,
    "hollow": False,
    "thickness": 0.5,
    "operation": "join",
}


def with_defaults(options):
    out = dict(DEFAULTS)
    out.update({k: v for k, v in (options or {}).items() if v is not None})
    return out


owner_body = primitives.owner_body


def _global_edge(obj, sub):
    edge = obj.Shape.getElement(sub).copy()
    place = primitives.body_placement(obj)
    if not place.isIdentity():
        edge.Placement = place.multiply(edge.Placement)
    return edge


def is_path_edge(obj, sub):
    """True if (obj, sub) is an edge a pipe can follow."""
    if obj is None or not (sub or "").startswith("Edge"):
        return False
    try:
        edge = obj.Shape.getElement(sub)
    except Exception:
        return False
    return edge.Length > 1e-7


# -- chains ----------------------------------------------------------------------------------------
def _ends(edge):
    a = edge.valueAt(edge.FirstParameter)
    b = edge.valueAt(edge.LastParameter)
    ta = edge.tangentAt(edge.FirstParameter)
    tb = edge.tangentAt(edge.LastParameter)
    return (a, ta), (b, tb)


def _tangent_joined(e1, e2):
    for p1, t1 in _ends(e1):
        for p2, t2 in _ends(e2):
            if (p1 - p2).Length < JOIN_TOL:
                cross = t1.cross(t2).Length
                if cross < math.sin(TANGENT_TOL):
                    return True
    return False


def chain(obj, sub):
    """The edges of `obj` joined to `sub` without a corner, `sub` first (Fusion's Chain
    Selection)."""
    shape = obj.Shape
    edges = list(shape.Edges)
    try:
        start = int(sub[4:]) - 1
    except ValueError:
        return [(obj, sub)]
    if start < 0 or start >= len(edges):
        return [(obj, sub)]
    found = [start]
    queue = [start]
    while queue:
        i = queue.pop()
        for j, other in enumerate(edges):
            if j in found or other.Length < 1e-9:
                continue
            if _tangent_joined(edges[i], other):
                found.append(j)
                queue.append(j)
    return [(obj, "Edge%d" % (i + 1)) for i in found]


def expand(picks, use_chain=True):
    """The path edges for what was clicked: each click with its chain (no duplicates)."""
    out, seen = [], set()
    for obj, sub in picks:
        group = chain(obj, sub) if use_chain else [(obj, sub)]
        for ref in group:
            key = (ref[0].Name, ref[1])
            if key not in seen:
                seen.add(key)
                out.append(ref)
    return out


# -- the path ------------------------------------------------------------------------------------------
def ordered_path(edges):
    """(wire, start point, start tangent) of edges (global or local, as given), ordered
    into one run starting at the end nearest the first edge's start. Raises
    PrimitiveError when the edges do not make one connected path."""
    import Part

    if not edges:
        raise PrimitiveError("Select a path: click sketch curves or edges of the model.")
    try:
        groups = Part.sortEdges(list(edges))
    except Exception:
        groups = [list(edges)]
    if len(groups) != 1:
        raise PrimitiveError(
            "The picked curves are not connected end to end, so they are no single path. "
            "Drop the ones that stand apart."
        )
    try:
        wire = Part.Wire(groups[0])
    except Exception:
        raise PrimitiveError("The picked curves do not make one path (they branch).")
    if len(wire.Edges) != len(edges):
        raise PrimitiveError("The picked curves do not make one path (they branch).")
    first = edges[0]
    anchor = first.valueAt(first.FirstParameter)
    ordered = wire.OrderedEdges
    head = ordered[0]
    tail = ordered[-1]
    if head.Orientation == "Reversed":
        p_head, t_head = head.valueAt(head.LastParameter), -head.tangentAt(head.LastParameter)
    else:
        p_head, t_head = head.valueAt(head.FirstParameter), head.tangentAt(head.FirstParameter)
    if tail.Orientation == "Reversed":
        p_tail, t_tail = tail.valueAt(tail.FirstParameter), tail.tangentAt(tail.FirstParameter)
    else:
        p_tail, t_tail = tail.valueAt(tail.LastParameter), -tail.tangentAt(tail.LastParameter)
    if wire.isClosed() or (p_head - anchor).Length <= (p_tail - anchor).Length + 1e-9:
        return wire, p_head, _unit(t_head), False
    return wire, p_tail, _unit(t_tail), True


def _unit(v):
    v = App.Vector(v)
    if v.Length < 1e-12:
        return App.Vector(0, 0, 1)
    v.normalize()
    return v


def trim(wire, start, reversed_run, fraction):
    """The first `fraction` (0..1] of the path run from `start` (an Edge list)."""
    import Part

    edges = list(wire.OrderedEdges)
    if reversed_run:
        edges = list(reversed(edges))
    total = sum(e.Length for e in edges)
    goal = total * min(1.0, fraction)
    out, run, point = [], 0.0, App.Vector(start)
    for e in edges:
        a = e.valueAt(e.FirstParameter)
        b = e.valueAt(e.LastParameter)
        forward = (a - point).Length <= (b - point).Length
        length = e.Length
        if run + length <= goal + 1e-9:
            piece = Part.Edge(e.Curve, e.FirstParameter, e.LastParameter)
            run += length
            point = b if forward else a
        else:
            rest = goal - run
            if rest <= 1e-7:
                break
            if forward:
                piece = Part.Edge(e.Curve, e.FirstParameter, e.getParameterByLength(rest))
            else:
                piece = Part.Edge(e.Curve, e.getParameterByLength(length - rest), e.LastParameter)
            run = goal
        # Every piece runs the way the pipe goes: the sweep starts where the section is.
        out.append(piece if forward else piece.reversed())
        if run >= goal - 1e-9:
            break
    if not out:
        raise PrimitiveError("The distance is too short to make a pipe.")
    return Part.Wire(out)


def sketch_normal(sources):
    """The global normal of the first sketch among `sources`, or None."""
    for obj in sources:
        if obj.isDerivedFrom("Sketcher::SketchObject"):
            return obj.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
    return None


def up_vector(tangent, normal, wire):
    """A direction across the path at its start for the section's 'up': the sketch's
    normal for a sketch path, the path's plane for a flat path, else Z (or X)."""
    candidates = [normal] if normal is not None else []
    try:
        plane = wire.findPlane()
        if plane is not None:
            candidates.append(App.Vector(plane.Axis))
    except Exception:
        pass
    candidates += [App.Vector(0, 0, 1), App.Vector(1, 0, 0), App.Vector(0, 1, 0)]
    for c in candidates:
        up = c - tangent * c.dot(tangent)
        if up.Length > 1e-6:
            up.normalize()
            return up
    return App.Vector(0, 0, 1)


def section_frame(point, tangent, up):
    """Placement whose z is the path direction, y the section's up, at the start."""
    z = _unit(tangent)
    y = _unit(up - z * up.dot(z))
    x = y.cross(z)
    matrix = App.Matrix(x.x, y.x, z.x, point.x, x.y, y.y, z.y, point.y, x.z, y.z, z.z, point.z)
    return App.Placement(matrix)


def section_wires(options):
    """The section's outline(s) in its own plane (local xy): [outer] or [outer, inner]."""
    import Part

    size = float(options["section_size"])
    kind = options["section"]
    hollow = bool(options.get("hollow"))
    t = float(options.get("thickness", 0.0))

    def circle(r):
        return Part.Wire(Part.Circle(App.Vector(), App.Vector(0, 0, 1), r).toShape())

    def square(half):
        pts = [App.Vector(-half, -half), App.Vector(half, -half), App.Vector(half, half)]
        pts.append(App.Vector(-half, half))
        return Part.makePolygon(pts + [pts[0]])

    def triangle(r):  # circumradius r, a corner pointing up (+y)
        pts = [
            App.Vector(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
            for a in (90.0, 210.0, 330.0)
        ]
        return Part.makePolygon(pts + [pts[0]])

    if kind == "square":
        half = size / (2.0 * math.sqrt(2.0))
        wires = [square(half)] + ([square(half - t)] if hollow else [])
    elif kind == "triangular":
        r = size / 2.0
        wires = [triangle(r)] + ([triangle(r - 2.0 * t)] if hollow else [])
    else:
        wires = [circle(size / 2.0)] + ([circle(size / 2.0 - t)] if hollow else [])
    return wires


section_area = core.pipe_section_area
check = core.pipe_check


# -- the helper objects -------------------------------------------------------------------------------
class PipePath:
    """The pipe's path in its body: the picked edges (any body, any sketch) joined into one
    run, cut at Distance. Also records where the run starts and its direction there
    (Start, Tangent, Up) for the section. Saved documents store
    "sciforge.pipe.PipePath": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Pipe path", doc)
                return True
            return False

        add("App::PropertyLinkSubListGlobal", "Edges", "The edges the pipe follows")
        if add("App::PropertyFloat", "Distance", "How far along the path (0..1)"):
            obj.Distance = 1.0
        for name in ("Start", "Tangent", "Up"):
            if add("App::PropertyVector", name, "Where the pipe starts"):
                obj.setEditorMode(name, 1)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        refs = []
        for linked, subs in obj.Edges:
            for sub in subs:
                refs.append((linked, sub))
        if not refs:
            raise PrimitiveError("The pipe has no path. Edit it and select one.")
        inverse = primitives.body_placement(obj).inverse()
        edges = []
        for linked, sub in refs:
            try:
                edge = _global_edge(linked, sub)
            except Exception:
                raise PrimitiveError(
                    "An edge of the pipe's path is gone (%s of %s). Edit the pipe and pick "
                    "the path again." % (sub, linked.Label)
                )
            edge.Placement = inverse.multiply(edge.Placement)
            edges.append(edge)
        wire, start, tangent, reverse = ordered_path(edges)
        normal = sketch_normal([o for o, _ in refs])
        if normal is not None:
            normal = inverse.Rotation.multVec(normal)  # into this body's coordinates
        up = up_vector(tangent, normal, wire)
        path = trim(wire, start, reverse, float(obj.Distance))
        for prop, value in (("Start", start), ("Tangent", tangent), ("Up", up)):
            if (getattr(obj, prop) - value).Length > 1e-12:
                setattr(obj, prop, value)
        obj.Placement = App.Placement()
        obj.Shape = path

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class PipeSection:
    """The pipe's section at the start of its path, square to it (circle, square or
    triangle, hollow or not). Saved documents store "sciforge.pipe.PipeSection": keep the
    name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Pipe section", doc)
                return True
            return False

        add("App::PropertyLink", "Path", "The pipe's path object")
        if add("App::PropertyEnumeration", "Section", "Shape of the section"):
            obj.Section = list(SECTIONS)
        if add("App::PropertyLength", "SectionSize", "Diameter of the circle round it"):
            obj.SectionSize = 2.0
        add("App::PropertyBool", "Hollow", "A tube")
        if add("App::PropertyLength", "Thickness", "Wall of a hollow pipe"):
            obj.Thickness = 0.5

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        import Part

        path = obj.Path
        if path is None:
            raise PrimitiveError("The pipe's path is gone. Edit the pipe and pick it again.")
        place = section_frame(path.Start, path.Tangent, path.Up)
        options = {
            "section": obj.Section,
            "section_size": obj.SectionSize.Value,
            "hollow": obj.Hollow,
            "thickness": obj.Thickness.Value,
        }
        wires = section_wires(options)
        shape = Part.Compound(wires)
        obj.Placement = place
        shape.Placement = place
        obj.Shape = shape

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def sweep(path_wire, section_shape):
    """The pipe's solid: the section's outer wire swept along the path, minus the inner
    one (hollow). The same sweep PartDesign's pipe makes (corrected Frenet, transformed
    corners)."""
    wires = list(section_shape.Wires)
    if not wires:
        raise PrimitiveError("The pipe has no section.")

    def one(w):
        solid = path_wire.makePipeShell([w], True, False, 0)
        if solid.Volume < 0:
            solid.reverse()
        return solid

    tool = one(wires[0])
    for inner in wires[1:]:
        tool = tool.cut(one(inner))
    return tool


class PipeFeature:
    """Pipe with operation Intersect: the body keeps what lies inside the pipe. Saved
    documents store "sciforge.pipe.PipeFeature": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        if "Spine" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Spine", "Pipe", "The path object")
        if "Profile" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Profile", "Pipe", "The section object")
        if "Refine" not in obj.PropertiesList:
            obj.addProperty("App::PropertyBool", "Refine", "Pipe", "Merge coplanar faces")
            obj.Refine = True
        primitives.mark_type(obj, KIND)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise PrimitiveError("Intersect needs a solid before it in the timeline.")
        if obj.Spine is None or obj.Profile is None:
            raise PrimitiveError("The pipe has no path or section.")
        tool = sweep(obj.Spine.Shape.Wires[0], obj.Profile.Shape)
        result = base.Shape.common(tool)
        if obj.Refine:
            result = result.removeSplitter()
        if result.isNull() or not result.Solids or result.Volume < 1e-7:
            raise PrimitiveError("The pipe does not overlap the body, so Intersect leaves nothing.")
        obj.Shape = result.Solids[0] if len(result.Solids) == 1 else result

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .pipe_ui import ViewProviderPipe

        ViewProviderPipe(obj.ViewObject)
    except Exception:
        pass


# -- building -------------------------------------------------------------------------------------------
def type_id(operation):
    if operation == "cut":
        return "PartDesign::SubtractivePipe"
    if operation == "intersect":
        return FP_TYPE
    return "PartDesign::AdditivePipe"


def is_pipe(obj):
    return obj is not None and getattr(obj, "SciForgeType", "") == KIND


def source_body(path):
    """The body the pipe goes into: the first model edge's body, else the sketch's."""
    for obj, _ in path:
        if not obj.isDerivedFrom("Sketcher::SketchObject"):
            body = owner_body(obj)
            if body is not None:
                return body
    for obj, _ in path:
        body = owner_body(obj)
        if body is not None:
            return body
    return None


def check_path(path):
    if not path:
        raise PrimitiveError("Select a path: click sketch curves or edges of the model.")
    for obj, sub in path:
        if not is_path_edge(obj, sub):
            raise PrimitiveError("%s of %s is no curve to follow." % (sub, obj.Label))
    edges = [_global_edge(obj, sub) for obj, sub in path]
    ordered_path(edges)
    return list(path)


def build(path, options, feature=None, name="Pipe", body=None):
    """Create the pipe, or rebuild `feature`. `body`: where it goes when the path has no
    body of its own. Returns the step."""
    options = with_defaults(options)
    check(options)
    path = check_path(path)
    src = source_body(path) or body
    if src is None:
        raise PrimitiveError("The path must belong to a body. Use Create Sketch first.")
    if feature is not None and any(obj is feature for obj, _ in path):
        raise PrimitiveError("The pipe cannot follow its own edges. Pick other edges.")
    operation = options["operation"]
    tid = type_id(operation)

    def setup(new):
        if tid == FP_TYPE:
            PipeFeature(new)
            _attach_view_provider(new)
        primitives.mark_type(new, KIND)

    def update(step, target):
        _update(step, target, path, options)

    return primitives.build_step(feature, src, operation, tid, name, update, setup, prop=META)


def _helper(body, feature, old, cls, type_name, role):
    for helper in list(old):
        if isinstance(getattr(helper, "Proxy", None), cls):
            old.remove(helper)
            return helper
    obj = primitives.insert_helper(body, feature, "Part::Part2DObjectPython", type_name, role)
    cls(obj)
    return obj


def _update(feature, body, path, options):
    meta = primitives.load_meta(feature, META)
    doc = feature.Document
    old_names = list(meta.get("helpers", []))
    old = [doc.getObject(n) for n in old_names]
    old = [h for h in old if h is not None]
    spine = _helper(body, feature, old, PipePath, "PipePath", PATH_ROLE)
    section = _helper(body, feature, old, PipeSection, "PipeSection", SECTION_ROLE)
    helpers = [spine, section]
    primitives.drop_helpers(doc, old_names, {h.Name for h in helpers})
    spine.Label = "%s path" % feature.Label
    section.Label = "%s section" % feature.Label
    grouped, order = {}, []
    for obj, sub in path:
        if obj.Name not in grouped:
            grouped[obj.Name] = (obj, [])
            order.append(obj.Name)
        grouped[obj.Name][1].append(sub)
    links = [(grouped[n][0], tuple(grouped[n][1])) for n in order]
    if [(o.Name, tuple(s)) for o, s in spine.Edges] != [(o.Name, s) for o, s in links]:
        spine.Edges = links
    if abs(spine.Distance - float(options["distance"])) > 1e-12:
        spine.Distance = float(options["distance"])
    if section.Path is not spine:
        section.Path = spine
    if section.Section != options["section"]:
        section.Section = options["section"]
    for prop, value in (
        ("SectionSize", float(options["section_size"])),
        ("Thickness", float(options["thickness"])),
    ):
        if abs(getattr(section, prop).Value - value) > 1e-12:
            setattr(section, prop, value)
    if section.Hollow != bool(options["hollow"]):
        section.Hollow = bool(options["hollow"])
    for helper in helpers:
        primitives.hide(helper)
    spine.recompute()
    section.recompute()
    if "Invalid" in list(spine.State) or spine.Shape.isNull():
        raise PrimitiveError(spine.getStatusString() or "The path cannot be followed.")
    if feature.TypeId == FP_TYPE:
        if feature.Spine is not spine:
            feature.Spine = spine
        if feature.Profile is not section:
            feature.Profile = section
    else:
        if feature.Spine is None or feature.Spine[0] is not spine:
            feature.Spine = (spine, [])
        if feature.Profile is None or feature.Profile[0] is not section:
            feature.Profile = (section, [""])
        if feature.Mode != "Standard":
            feature.Mode = "Standard"
        if feature.Transition != "Transformed":
            feature.Transition = "Transformed"
        if not feature.Refine:
            feature.Refine = True
    meta.update(
        {
            "v": 1,
            "kind": "pipe",
            "path": [[obj.Name, sub] for obj, sub in path],
            "options": {k: v for k, v in options.items() if k != "expressions"},
            "formulas": {k: v for k, v in (options.get("expressions") or {}).items() if v},
            "helpers": [h.Name for h in helpers],
        }
    )
    primitives.save_meta(feature, meta, META)
    formulas = options.get("expressions") or {}
    primitives.set_formulas(
        [
            (section, "SectionSize", formulas.get("section_size", "")),
            (section, "Thickness", formulas.get("thickness", "") if options["hollow"] else ""),
        ]
    )


def hide_sketches(path):
    """Fusion hides a sketch once a feature uses it."""
    if not App.GuiUp:
        return
    for obj, _ in path:
        if obj.isDerivedFrom("Sketcher::SketchObject"):
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass


# -- reading back ----------------------------------------------------------------------------------------
def read(feature):
    """(path, options) of an existing pipe, as the dialog shows them."""
    meta = primitives.load_meta(feature, META)
    options = with_defaults(meta.get("options", {}))
    path = []
    for name, sub in meta.get("path", []):
        obj = feature.Document.getObject(name)
        if obj is not None:
            path.append((obj, sub))
    if feature.TypeId == FP_TYPE:
        options["operation"] = "intersect"
    elif feature.TypeId == "PartDesign::SubtractivePipe":
        options["operation"] = "cut"
    else:
        saved = meta.get("options", {}).get("operation")
        options["operation"] = "new_body" if saved == "new_body" else "join"
    # The values as they are now (a parameter may drive them), not as last typed.
    section = None
    for name in meta.get("helpers", []):
        helper = feature.Document.getObject(name)
        if helper is not None and isinstance(getattr(helper, "Proxy", None), PipeSection):
            section = helper
        elif helper is not None and isinstance(getattr(helper, "Proxy", None), PipePath):
            options["distance"] = float(helper.Distance)
    options["expressions"] = {}
    if section is not None:
        options["section_size"] = section.SectionSize.Value
        options["thickness"] = section.Thickness.Value
        options["expressions"] = primitives.kept_formulas(
            meta,
            {"section_size": [(section, "SectionSize")], "thickness": [(section, "Thickness")]},
        )
    return path, options


def is_ours(feature):
    return is_pipe(feature) and bool(primitives.load_meta(feature, META).get("path"))


def make(path, options, name="Pipe"):
    return build(path, options, name=name)


def update(feature, path=None, options=None):
    old_path, old_options = read(feature)
    merged = dict(old_options)
    merged.update(options or {})
    return build(path if path is not None else old_path, merged, feature=feature)


def remove(feature):
    body = owner_body(feature)
    primitives.remove_step(feature, keep_body=False, prop=META)
    primitives.show_tip(body)


def tool_shape(path, options):
    """The pipe's solid in global coordinates (for picking the operation)."""
    options = with_defaults(options)
    check(options)
    edges = [_global_edge(obj, sub) for obj, sub in check_path(path)]
    wire, start, tangent, reverse = ordered_path(edges)
    up = up_vector(tangent, sketch_normal([o for o, _ in path]), wire)
    run = trim(wire, start, reverse, float(options["distance"]))
    import Part

    section = Part.Compound(section_wires(options))
    section.Placement = section_frame(start, tangent, up)
    return sweep(run, section)


def path_length(path):
    edges = [_global_edge(obj, sub) for obj, sub in path]
    return sum(e.Length for e in edges)


def path_points(path, options=None, count=64):
    """(points along the whole path from its start, the point where the pipe ends), global."""
    edges = [_global_edge(obj, sub) for obj, sub in path]
    wire, start, tangent, reverse = ordered_path(edges)
    full = trim(wire, start, reverse, 1.0)
    points = _points_from(full, start, count)
    end = None
    if options is not None:
        run = trim(wire, start, reverse, float(with_defaults(options)["distance"]))
        end = _points_from(run, start, 2)[-1]
    return points, end, start, tangent


def _points_from(wire, start, count):
    """Points along a wire from the end at `start`."""
    pts = wire.discretize(max(2, count))
    if (pts[0] - start).Length > (pts[-1] - start).Length:
        pts = list(reversed(pts))
    return pts
