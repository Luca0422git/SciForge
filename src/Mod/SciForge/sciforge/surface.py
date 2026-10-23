# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's SURFACE tools: the document side, no Qt. The dialogs (surface_ui.py) and the
golden-model builder both call build().

How a surface body lives in a SciForge design (docs/sciforge/parity/surface.md explains
the choice): a surface body is a PartDesign Body like a solid body, whose result is a
surface (faces, no solid). Every surface step is a PartDesign::FeaturePython
(SurfaceFeature below, timeline type "SciForge::<SciForgeType>") in a body's history, so
the browser lists the body in Bodies (with the surface icon while it has no solid), the
timeline shows, rolls back, suppresses and edits the step, components, Move/Copy,
Appearance, Delete and save / reopen work as for every body, and the 3D view picks its
faces and edges like any body's.

  CREATE tools (Extrude, Revolve, Sweep, Loft, Patch, Ruled, Offset, Boundary Fill and
  Thicken as New Body / New Component) make the first step of a new body.
  MODIFY tools (Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal; Thicken and
  Boundary Fill with Join / Cut / Intersect) add a step at the history marker of the body
  they change, so a stitched closed surface becomes a solid body that solid features
  carry on from.

Picks are (object, sub-element) pairs: sketch curves (sketch, "EdgeN"), edges and faces
of a body (its feature, "EdgeN" / "FaceN"), a whole body (body, ""), a plane or axis
(object, ""). A whole body is linked through its last step at the time, like Combine.
Numbers live in real properties (Distance, Angle...) so parameters and formulas work;
choices and picked cells are JSON in the hidden "SciForgeSurface" property.
"""

import json

import FreeCAD as App

from . import bodies, curves, log, warn
from . import surface_core as core
from .surface_core import NeedsPick, SurfaceError

TYPE = "PartDesign::FeaturePython"
META = "SciForgeSurface"
LINKS = ("Refs", "Refs2", "Refs3")
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
LINE_TYPES = ("App::Line", "PartDesign::Line", "Part::DatumLine")
POINT_TYPES = ("App::Point", "PartDesign::Point", "Part::DatumPoint")
# Construction geometry: it lives in a body (its Origin) but picking it never means that body.
CONSTRUCTION_TYPES = PLANE_TYPES + LINE_TYPES + POINT_TYPES

# Dialog option -> the feature's number property (so a parameter or formula can drive it).
NUMBERS = {
    "extrude": {
        "distance": "Distance",
        "distance2": "Distance2",
        "start_offset": "Offset",
        "taper": "Taper",
        "taper2": "Taper2",
    },
    "revolve": {"angle": "Angle", "angle2": "Angle2"},
    "sweep": {
        "distance": "Ratio",
        "distance2": "Ratio2",
        "rail_distance": "Ratio3",
        "twist": "Angle",
        "taper": "Taper",
    },
    "loft": {
        "start_weight": "Weight",
        "end_weight": "Weight2",
        "start_angle": "Angle",
        "end_angle": "Angle2",
    },
    "patch": {"weight": "Weight"},
    "ruled": {"distance": "Distance", "angle": "Angle"},
    "offset": {"distance": "Distance"},
    "thicken": {"thickness": "Distance"},
    "extend": {"distance": "Distance"},
    "untrim": {"distance": "Distance"},
    "stitch": {"tolerance": "Tolerance"},
}
PROPERTY_TYPES = {
    "Distance": "App::PropertyDistance",
    "Distance2": "App::PropertyDistance",
    "Offset": "App::PropertyDistance",
    "Taper": "App::PropertyAngle",
    "Taper2": "App::PropertyAngle",
    "Angle": "App::PropertyAngle",
    "Angle2": "App::PropertyAngle",
    "Ratio": "App::PropertyFloat",
    "Ratio2": "App::PropertyFloat",
    "Ratio3": "App::PropertyFloat",
    "Weight": "App::PropertyFloat",
    "Weight2": "App::PropertyFloat",
    "Tolerance": "App::PropertyLength",
}
# What each kind keeps in its three link lists.
ROLES = {
    "extrude": ("profile", "to_object (All: the bodies it goes through)", "start_object"),
    "revolve": ("profile", "axis", "to_object"),
    "sweep": ("profile", "path", "rail (Guide Surface: its faces)"),
    "loft": ("sections", "rails", "centerline"),
    "patch": ("boundary", "interior", None),
    "ruled": ("edges", "direction", None),
    "offset": ("faces", None, None),
    "boundary_fill": ("tools", None, None),
    "thicken": ("faces", None, None),
    "trim": ("tool", "others", None),
    "untrim": ("faces (Manual: the loops' edges)", None, None),
    "extend": ("edges", None, None),
    "stitch": ("bodies (Join / Cut / Intersect: all of them)", None, None),
    "unstitch": ("faces", None, None),
    "reverse_normal": (None, None, None),
    "piece": (None, None, None),
}


# -- finding surface steps and bodies ---------------------------------------------------------
def kind_of(obj):
    """The surface kind of a step ("patch", "trim"...), or None."""
    return core.kind_of_type(bodies.kind(obj))


def is_surface_step(obj):
    return kind_of(obj) is not None


def is_surface_shape(shape):
    try:
        return shape is not None and not shape.isNull() and bool(shape.Faces) and not shape.Solids
    except Exception:
        return False


def is_surface_body(body):
    """True for a body whose result is a surface (faces and no solid): Fusion's surface
    body, shown with the surface icon. An empty body is not one."""
    if not bodies.is_body(body):
        return False
    tip = getattr(body, "Tip", None)
    return tip is not None and is_surface_shape(tip.Shape)


def surface_bodies(doc, visible_only=False):
    return [
        b
        for b in bodies.list_bodies(doc)
        if is_surface_body(b) and (not visible_only or bodies.is_shown(b))
    ]


def leader_of(step):
    """A follower step's leader (a Trim / Reverse Normal over several bodies), else the
    step itself."""
    leader = getattr(step, "Leader", None)
    return leader if leader is not None and bodies.alive(leader) else step


def followers_of(step):
    return [
        o
        for o in step.InList
        if is_surface_step(o) and getattr(o, "Leader", None) is step and bodies.alive(o)
    ]


def pieces_of(step):
    found = [o for o in step.InList if kind_of(o) == "piece" and getattr(o, "Source", None) is step]
    return sorted(found, key=lambda o: o.Index)


def created_body(step):
    meta = bodies.load_meta(step, META)
    name = meta.get("created_body")
    body = step.Document.getObject(name) if name else None
    return body if body is not None and step in getattr(body, "Group", []) else None


# -- the feature --------------------------------------------------------------------------------
class SurfaceFeature:
    """Every surface step. Saved in files as "sciforge.surface.SurfaceFeature": keep the name
    and the properties."""

    def __init__(self, obj, kind):
        obj.Proxy = self
        self.ensure_properties(obj, kind)

    @staticmethod
    def ensure_properties(obj, kind=None):
        def add(kind_, name, doc, group="Surface", mode=0):
            if name not in obj.PropertiesList:
                obj.addProperty(kind_, name, group, doc, mode)
                return True
            return False

        if kind is not None:
            bodies.mark(obj, core.sciforge_type(kind))
        kind = kind_of(obj)
        for prop in LINKS:
            add("App::PropertyLinkSubListGlobal", prop, "Picked curves, faces, bodies", mode=0)
        add("App::PropertyLinkGlobal", "Leader", "The step this one follows", mode=4)
        if kind == "piece":
            add("App::PropertyLinkGlobal", "Source", "The Unstitch it comes from")
            add("App::PropertyInteger", "Index", "Which face (1 = first)")
        if kind in ("unstitch", "untrim") and "Pieces" not in obj.PropertiesList:
            obj.addProperty("Part::PropertyPartShape", "Pieces", "Surface", "", 4 | 16)
        for option, prop in NUMBERS.get(kind, {}).items():
            if add(PROPERTY_TYPES[prop], prop, option.replace("_", " ").capitalize()):
                default = core.KINDS[kind]["defaults"].get(option, 0.0)
                setattr(obj, prop, float(default))

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)
        apply_number_modes(obj)

    def onChanged(self, obj, prop):
        if prop == META:  # its choices changed (a dialog, undo / redo, a Cancel)
            apply_number_modes(obj)
        elif prop == "Shape":
            self._keep_surface_when_suppressed(obj)

    def _keep_surface_when_suppressed(self, obj):
        """Suppressed in the timeline: FreeCAD's PartDesign gives a suppressed step the step
        before it only when that is a solid, so a surface step came out empty, its body went
        blank and the steps after it red. The step then shows the surface before it,
        unchanged (as SurfaceModifyFeature does); the first step of a body stays empty."""
        if getattr(self, "_passing", False):
            return
        try:
            if not getattr(obj, "Suppressed", False) or not obj.Shape.isNull():
                return
            doc = obj.Document
            if doc.Restoring or getattr(doc, "Transacting", False):
                return  # the file / the undo step brings its own shape
            base = getattr(obj, "BaseFeature", None)
            if base is not None and not base.Shape.isNull() and base.Shape.Faces:
                self._passing = True
                obj.Shape = base.Shape.copy()
        except Exception:
            pass
        finally:
            self._passing = False

    def execute(self, obj):
        if getattr(obj, "Suppressed", False):
            # Off in the timeline: FreeCAD throws the result away and shows the step before
            # it (onChanged above keeps a surface). Building it anyway fails when the step
            # before it went off too (the first step of the body), and FreeCAD then prints
            # that error at every recompute.
            return
        try:
            try:
                curves.refind(obj, LINKS)  # elements FreeCAD lost after a reopen
            except Exception:
                pass
            shape = compute(obj)
            body = bodies.body_of(obj)
            obj.Shape = bodies.to_local(shape, body) if body is not None else shape
            try:
                curves.remember(obj, LINKS)
            except Exception:
                pass
        except Exception:
            bodies.pass_through(obj)  # the body as it was before it; the step shows red
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def apply_number_modes(obj):
    """Change Parameters lists only the numbers a step's choices use, as Fusion lists a
    feature's values in use (a One Side extrude has no Distance Two there): the numbers whose
    rows the dialog hid (saved with the choices, "hidden_numbers") are hidden properties,
    which parameters.py passes over as it does for FreeCAD's own features. It follows the
    saved choices, so undo, redo and Cancel bring the right ones back. Never raises."""
    try:
        kind = kind_of(obj)
        numbers = NUMBERS.get(kind or "", {})
        if not numbers:
            return
        meta = bodies.load_meta(obj, META)
        hidden = set((meta.get("options") or {}).get("hidden_numbers") or [])
        props = obj.PropertiesList
        for option, prop in numbers.items():
            if prop not in props:
                continue
            want = option in hidden
            if bool(obj.getEditorMode(prop)) != want:
                obj.setEditorMode(prop, 2 if want else 0)
    except Exception as exc:
        warn("surface parameters of %s: %s" % (getattr(obj, "Label", "?"), exc))


# -- reading a step --------------------------------------------------------------------------------
def refs_of(obj, prop):
    """[(object, sub)] of a link list, in the order picked ("" = the whole object)."""
    out = []
    for linked, subs in curves._items(getattr(obj, prop, None)):
        if linked is None:
            continue
        for sub in subs or [""]:
            out.append((linked, sub or ""))
    return out


def options_of(obj):
    """The dialog options of a step (its leader's for a follower): choices from the JSON,
    numbers from the properties."""
    source = leader_of(obj)
    kind = kind_of(source)
    meta = bodies.load_meta(source, META)
    options = core.with_saved(kind, meta.get("options") or {})
    for option, prop in NUMBERS.get(kind, {}).items():
        try:
            value = getattr(source, prop)
            options[option] = float(getattr(value, "Value", value))
        except Exception:
            pass
    return options


def read(step):
    """(kind, {"refs": [...], "refs2": [...], "refs3": [...]}, options) of a step; for a
    follower, of its leader. Whole bodies are given back as the body."""
    leader = leader_of(step)
    kind = kind_of(leader)
    refs = {}
    for prop, key in zip(LINKS, ("refs", "refs2", "refs3")):
        found = []
        for obj, sub in refs_of(leader, prop):
            found.append(_as_body_pick(obj, sub, leader))
        refs[key] = found
    options = options_of(leader)
    meta = bodies.load_meta(leader, META)
    if kind == "loft":
        options["groups"] = list(meta.get("groups") or [])
    if kind == "trim":
        options["cells"] = [list(c) for c in meta.get("cells") or []]
        options["bodies"] = [
            b for b in (bodies.body_of(s) for s in [leader] + followers_of(leader)) if b
        ]
    if kind == "reverse_normal":
        options["bodies"] = [
            b for b in (bodies.body_of(s) for s in [leader] + followers_of(leader)) if b
        ]
    if kind in ("thicken", "boundary_fill") and core.is_solid_operation(options.get("operation")):
        options["target"] = bodies.body_of(leader)
    if kind == "stitch":
        if core.is_solid_operation(options.get("operation")):
            options["target"] = bodies.body_of(leader)
        else:
            refs["refs"] = [(bodies.body_of(leader), "")] + refs["refs"]
    return kind, refs, options


def _as_body_pick(obj, sub, step):
    """A link to a body's step with no sub-element means "that whole body"."""
    if sub:
        return (obj, sub)
    body = bodies.body_of(obj)
    if body is not None and body is not obj and obj.TypeId not in CONSTRUCTION_TYPES:
        if not getattr(obj, "TypeId", "").startswith("Sketcher"):
            return (body, "")
    return (obj, sub)


# -- resolving picks (design coordinates) ----------------------------------------------------------
def _global(obj, element):
    return curves.to_global(element, obj)


def element_of(obj, sub):
    """Edge / face / vertex `sub` of `obj` in design coordinates (a copy)."""
    try:
        element = obj.Shape.getElement(sub)
    except Exception:
        element = None
    if element is None or element.isNull():
        raise SurfaceError(
            "Something picked from %s is gone (an earlier step changed it). Edit this step "
            "and pick it again." % getattr(obj, "Label", "?")
        )
    return _global(obj, element)


def whole_shape(obj):
    """A body (its last step) or a step's shape in design coordinates."""
    if bodies.is_body(obj):
        obj = obj.Tip
    if obj is None:
        raise SurfaceError("A body picked has no shape (yet).")
    shape = bodies.global_shape(obj)
    if shape.isNull():
        raise SurfaceError("%s has no shape." % obj.Label)
    return shape


def edges_of(refs):
    """The curves of picks: sketch curves and body edges (a whole sketch: all its curves)."""
    found = []
    for obj, sub in refs:
        if obj is None:
            continue
        if sub.startswith("Edge"):
            found.append(element_of(obj, sub))
        elif sub.startswith("Face"):
            # a flat face as a profile (Extrude): the curves round it, holes too
            found.extend(element_of(obj, sub).Edges)
        elif not sub and curves.is_sketch(obj):
            found.extend(_global(obj, obj.Shape).Edges)
        elif not sub:
            found.extend(whole_shape(obj).Edges)
    return found


def faces_of(refs):
    found = []
    for obj, sub in refs:
        if obj is None:
            continue
        if sub.startswith("Face"):
            found.append(element_of(obj, sub))
        elif not sub and obj.TypeId not in PLANE_TYPES:
            found.extend(whole_shape(obj).Faces)
    return found


def plane_of_ref(obj, sub):
    """(point, normal) of a plane pick: an origin / construction plane or a flat face."""
    if obj.TypeId in PLANE_TYPES:
        place = obj.getGlobalPlacement()
        return App.Vector(place.Base), place.Rotation.multVec(App.Vector(0, 0, 1))
    if sub.startswith("Face"):
        face = element_of(obj, sub)
        if face.Surface.TypeId != "Part::GeomPlane":
            raise SurfaceError("Pick a flat face or a plane.")
        u0, u1, v0, v1 = face.ParameterRange
        return face.CenterOfMass, face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    raise SurfaceError("Pick a flat face or a plane.")


def axis_of_ref(ref):
    from . import revolve

    try:
        return revolve.axis_line(ref)
    except Exception as exc:
        raise SurfaceError(str(exc))


def sketch_normal(refs):
    """The normal of the sketch the curves come from (all from one plane), else the plane
    the curves lie in."""
    from . import surface_geom as g

    normals = []
    for obj, _sub in refs:
        if curves.is_sketch(obj):
            normals.append(obj.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1)))
    if normals and all(abs(abs(n.dot(normals[0])) - 1.0) < 1e-7 for n in normals):
        return normals[0]
    flat = g.plane_of(edges_of(refs))
    if flat is None:
        raise SurfaceError(
            "The curves do not lie in one plane, so there is no direction to extrude them in. "
            "Pick curves of one sketch."
        )
    return flat[1]


def profile_plane(refs):
    """(point, normal) of the sketch every profile curve comes from, or None (curves of
    several sketches or edges of bodies: the plane they lie in is used instead)."""
    sketches = {obj.Name: obj for obj, _sub in refs if curves.is_sketch(obj)}
    if len(sketches) != 1 or any(not curves.is_sketch(obj) for obj, _sub in refs):
        return None
    place = list(sketches.values())[0].getGlobalPlacement()
    return App.Vector(place.Base), place.Rotation.multVec(App.Vector(0, 0, 1))


def _edge_faces(obj, sub):
    """The faces of the body result an edge belongs to (design coordinates)."""
    shape = bodies.global_shape(obj)
    edge = shape.getElement(sub)
    return edge, list(shape.ancestorsOfType(edge, __import__("Part").Face)), shape


# -- computing a step ------------------------------------------------------------------------------
def compute(obj):
    """The shape of a surface step in design coordinates."""
    kind = kind_of(obj)
    if kind is None:
        raise SurfaceError("Not a surface step.")
    if kind == "piece":
        return _compute_piece(obj)
    leader = leader_of(obj)
    options = options_of(obj)
    refs = [refs_of(leader, p) for p in LINKS]
    fn = COMPUTE[kind]
    return fn(obj, leader, options, refs)


def _base(obj, what="surface"):
    base = getattr(obj, "BaseFeature", None)
    if base is None or base.Shape.isNull():
        raise SurfaceError("There is no %s before this step in its body." % what)
    return bodies.global_shape(base)


def target_of_ref(obj, sub, chain=False):
    """What a picked object is for Extrude's To Object / From Object: ("plane", point,
    normal) for a plane or a flat face, ("point", point) for a point, ("shape", shape) for a
    curved face or a whole body (design coordinates). chain: a face and the faces joined
    smoothly to it (Fusion's Chain Faces)."""
    import Part

    if chain and sub.startswith("Face") and obj.TypeId not in PLANE_TYPES:
        from . import shelling

        try:
            names = shelling.tangent_faces(obj.Shape, [sub])
        except Exception:
            names = [sub]
        if len(names) > 1:
            return ("shape", Part.makeCompound([element_of(obj, n) for n in names]))
    if obj.TypeId in PLANE_TYPES:
        return ("plane",) + tuple(plane_of_ref(obj, sub))
    if obj.TypeId in POINT_TYPES:
        return ("point", App.Vector(obj.getGlobalPlacement().Base))
    if sub.startswith("Vertex"):
        return ("point", element_of(obj, sub).Point)
    if sub.startswith("Face"):
        face = element_of(obj, sub)
        if face.Surface.TypeId == "Part::GeomPlane":
            return ("plane",) + tuple(plane_of_ref(obj, sub))
        return ("shape", face)
    if sub.startswith("Edge") or curves.is_sketch(obj):
        raise SurfaceError("Pick a plane, a face, a body or a point (not a curve).")
    shape = whole_shape(obj)
    if not shape.Faces:
        raise SurfaceError("%s has no faces to extrude to." % obj.Label)
    return ("shape", shape if shape.Solids else Part.makeCompound(shape.Faces))


def _c_extrude(obj, leader, o, refs):
    from . import surface_geom as g

    profile = refs[0]
    if not profile:
        raise NeedsPick("Select the profile: sketch curves or edges of a body.")
    normal = sketch_normal(profile)
    target = None
    through = None
    if o["extent"] == "to_object":
        if not refs[1]:
            raise NeedsPick("Select the object to extrude to: a plane, a face, a body or a point.")
        target = target_of_ref(*refs[1][0], chain=bool(o.get("chain_faces", True)))
    elif o["extent"] == "all":
        through = [whole_shape(b) for b, _s in refs[1]]
    start = None
    if o["start"] == "object":
        if not refs[2]:
            raise NeedsPick("Select where the extrusion starts: a plane, a face or a point.")
        start = target_of_ref(*refs[2][0])
    return g.extrude_curves(edges_of(profile), normal, o, target, start, through)


def _c_revolve(obj, leader, o, refs):
    from . import revolve
    from . import surface_geom as g

    if not refs[0]:
        raise NeedsPick("Select the profile: sketch curves or edges of a body.")
    if not refs[1]:
        raise NeedsPick("Select the axis: a sketch line, a straight edge or an axis.")
    point, direction = axis_of_ref(refs[1][0])
    edges = edges_of(refs[0])
    if o.get("project_axis"):
        point, direction = g.project_axis(edges, point, direction, profile_plane(refs[0]))
    directions = None
    second = None
    if o["type"] == "to":
        if not refs[2]:
            raise NeedsPick(
                "Select the object to revolve to: a plane or flat face through the axis, an "
                "edge or a point."
            )
        two = o.get("direction") == "two_sides"
        if two and len(refs[2]) < 2:
            raise NeedsPick("Select the object the second side revolves to.")
        try:
            directions = revolve.target_directions(refs[2][0], point, direction)
            if two:
                second = revolve.target_directions(refs[2][1], point, direction)
        except Exception as exc:
            raise SurfaceError(problem_text(exc))
    return g.revolve_curves(edges, point, direction, o, directions, second)


def _c_sweep(obj, leader, o, refs):
    from . import surface_geom as g

    if not refs[0]:
        raise NeedsPick("Select the profile: sketch curves or edges of a body.")
    if not refs[1]:
        raise NeedsPick("Select the path: sketch curves or edges of a body.")
    try:
        path = curves.Path(edges_of(refs[1]))
    except curves.CurveError as exc:
        raise SurfaceError(str(exc))
    rail = None
    guide = None
    if o.get("type") == "rail":
        if not refs[2]:
            raise NeedsPick("Select the guide rail: sketch curves or edges of a body.")
        try:
            rail = curves.Path(edges_of(refs[2]), start_near=path.start)
        except curves.CurveError as exc:
            raise SurfaceError("Guide rail: %s" % exc)
    elif o.get("type") == "surface":
        guide = faces_of([r for r in refs[2] if r[1].startswith("Face")])
        if not guide:
            raise NeedsPick("Select the guide surface: faces the path runs along.")
    return g.sweep_curves(edges_of(refs[0]), path, o, rail, guide)


def _c_loft(obj, leader, o, refs):
    from . import loft_ends
    from . import surface_geom as g

    meta = bodies.load_meta(leader, META)
    sections = loft_groups(refs[0], meta.get("groups"))
    shapes = [section_shape(group) for group in sections]
    profiles = None
    if loft_ends.active(o):
        profiles = [curve_section(group, shape) for group, shape in zip(sections, shapes)]
    rails = None
    centerline = None
    near = shapes[0].BoundBox.Center if shapes else None
    if o.get("guide", "rails") == "rails" and refs[1]:
        rails = rail_paths(edges_of(refs[1]), near)
    if o.get("guide") == "centerline" and refs[2]:
        try:
            centerline = curves.Path(edges_of(refs[2]), start_near=near)
            centerline = loft_ends.between_profiles(centerline, near, shapes[-1].BoundBox.Center)
        except curves.CurveError as exc:
            raise SurfaceError("Centerline: %s" % exc)
    return g.loft_surface(shapes, o, rails, centerline, profiles)


def rail_paths(edges, near=None):
    """Each connected run of rail curves is one rail (a curves.Path)."""
    import Part

    try:
        groups = Part.sortEdges(edges, 1e-5)
    except Exception:
        groups = [edges]
    paths = []
    for group in groups:
        try:
            paths.append(curves.Path(group, start_near=near))
        except curves.CurveError as exc:
            raise SurfaceError("Rail: %s" % exc)
    return paths


def curve_section(group, shape):
    """What a surface loft profile is, for its end conditions (loft_ends.CurveSection)."""
    from . import loft_ends
    from . import surface_geom as g

    if shape.ShapeType == "Vertex":
        return loft_ends.CurveSection(shape, "point", profile=group[0])
    if all(curves.is_sketch(obj) for obj, _sub in group):
        normal = group[0][0].getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
        return loft_ends.CurveSection(shape, "sketch", normal=normal, profile=group[0])
    pairs = []
    for obj, sub in group:
        if not sub.startswith("Edge") or curves.is_sketch(obj):
            continue
        edge, faces, _shape = _edge_faces(obj, sub)
        if faces:
            pairs.append((edge, faces[0]))
    flat = g.plane_of([shape])
    return loft_ends.CurveSection(
        shape, "edge", normal=flat[1] if flat else None, guide_pairs=pairs, profile=group[0]
    )


def loft_groups(flat, sizes):
    """The flat pick list split into profiles (each a list of picks)."""
    if not sizes or sum(sizes) != len(flat):
        return [[p] for p in flat]
    out, i = [], 0
    for n in sizes:
        out.append(flat[i : i + n])
        i += n
    return out


def section_shape(group):
    """One loft profile: a wire of curves, or a point."""
    import Part

    from . import surface_geom as g

    if len(group) == 1 and group[0][1].startswith("Vertex"):
        return element_of(*group[0])
    if len(group) == 1 and group[0][0].TypeId in POINT_TYPES:
        return Part.Vertex(group[0][0].getGlobalPlacement().Base)
    wires = g.wires_of(edges_of(group))
    if len(wires) != 1:
        raise SurfaceError(
            "A loft profile must be one connected curve (it has %d pieces). Pick connected "
            "curves for each profile." % len(wires)
        )
    return wires[0]


def _c_patch(obj, leader, o, refs):
    from . import surface_geom as g

    if not refs[0]:
        raise NeedsPick("Select the boundary: edges of a body or sketch curves.")
    boundary = []
    per_edge = list(o.get("edge_continuity") or [])
    for index, ref in enumerate(refs[0]):
        target, sub = ref
        order = None  # Group Edges: the one Continuity for all
        if not o.get("group_edges", True) and index < len(per_edge):
            order = core.CONTINUITY.get(per_edge[index], 0)
        if sub.startswith("Edge") and not curves.is_sketch(target):
            edge, faces, _shape = _edge_faces(target, sub)
            boundary.append((edge, faces[0] if faces else None, order))
        else:
            for edge in edges_of([ref]):
                boundary.append((edge, None, order))
    interior, points = [], []
    for ref in refs[1]:
        if ref[1].startswith("Vertex"):
            points.append(element_of(*ref))
        else:
            interior.extend(edges_of([ref]))
    return g.patch(boundary, o["continuity"], interior, points, bool(o.get("reverse")))


def _c_ruled(obj, leader, o, refs):
    from . import surface_geom as g

    if not refs[0]:
        raise NeedsPick("Select edges of a body or sketch curves.")
    items = []
    for ref in refs[0]:
        target, sub = ref
        if curves.is_sketch(target):
            normal = target.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
            for edge in edges_of([ref]):
                items.append((edge, None, normal, False))
            continue
        edge, faces, _shape = _edge_faces(target, sub)
        face = None
        if faces:
            face = faces[1] if o.get("alternate") and len(faces) > 1 else faces[0]
        items.append((edge, face, None, bool(o.get("alternate"))))
    direction = None
    if o["ruled_type"] == "direction":
        if not refs[1]:
            raise NeedsPick("Select the direction: a straight edge, an axis or a plane.")
        direction = direction_of_ref(refs[1][0])
    return g.ruled(items, o["ruled_type"], o["distance"], o["angle"], direction, o["mitered"])


def direction_of_ref(ref):
    obj, sub = ref
    if obj.TypeId in PLANE_TYPES or sub.startswith("Face"):
        return plane_of_ref(obj, sub)[1]
    return axis_of_ref(ref)[1]


def _c_offset(obj, leader, o, refs):
    from . import surface_geom as g

    faces = faces_of(refs[0])
    if not faces:
        raise NeedsPick("Select the faces to offset.")
    return g.offset_faces(faces, o["distance"], o.get("offset_type", "sharp"))


def _c_thicken(obj, leader, o, refs):
    from . import surface_geom as g

    faces = faces_of(refs[0])
    if not faces:
        raise NeedsPick("Select the faces (or a surface body) to thicken.")
    solid = g.thicken(faces, o["thickness"], o["direction"], o["thicken_type"])
    if core.is_solid_operation(o["operation"]):
        return g.thicken_cut(_base(obj, "solid"), solid, o["operation"])
    return solid


def tool_shapes(refs):
    """Boundary Fill tools: bodies and faces as they are, planes as big squares around the
    other tools."""
    from . import surface_geom as g

    shapes, planes = [], []
    for obj, sub in refs:
        if obj.TypeId in PLANE_TYPES:
            planes.append(plane_of_ref(obj, sub))
        elif sub.startswith("Face"):
            shapes.append(element_of(obj, sub))
        else:
            shapes.append(whole_shape(obj))
    far = max([p.Length for p, _n in planes] or [0.0])
    size = (g.reach(shapes, 50.0) if shapes else 200.0) + 2.0 * far
    for point, normal in planes:
        shapes.append(g.plane_face(point, normal, size))
    return shapes


def _c_boundary_fill(obj, leader, o, refs):
    from . import surface_geom as g

    if not refs[0]:
        raise NeedsPick("Select the tools: bodies, surfaces and planes that close a space.")
    meta = bodies.load_meta(leader, META)
    points = meta.get("cells") or []
    solid = g.fill_cells(tool_shapes(refs[0]), points)
    if core.is_solid_operation(o["operation"]):
        return g.thicken_cut(_base(obj, "solid"), solid, o["operation"])
    return solid


def trim_cutter(step, leader, refs, around):
    """What cuts this step's body: the trim tool; for the tool's own body, the other
    surfaces it was trimmed against."""
    from . import surface_geom as g

    tool = refs[0][0] if refs[0] else None
    if tool is None:
        raise NeedsPick("Select the trim tool: a surface, a plane, a sketch curve or a body.")
    obj, sub = tool
    body = bodies.body_of(step)
    own = bodies.body_of(obj) is body and obj.TypeId not in CONSTRUCTION_TYPES
    if body is not None and own and not sub.startswith("Edge"):  # an origin plane is no body
        others = [whole_shape(o) for o, _s in refs[1]]
        if not others:
            raise SurfaceError("Nothing to trim the trim tool itself against.")
        return g.compound(others)
    return tool_cutter(tool, around)


def tool_cutter(tool, around):
    """The trim tool as a shape: a plane as a big square, a sketch curve carried straight
    through along the sketch's normal, a face, a body."""
    import Part

    from . import surface_geom as g

    obj, sub = tool
    size = g.reach([around])
    if obj.TypeId in PLANE_TYPES:
        point, normal = plane_of_ref(obj, sub)
        return g.plane_face(point, normal, size)
    if curves.is_sketch(obj):
        normal = obj.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
        bands = []
        for edge in edges_of([tool]):
            moved = edge.copy()
            moved.translate(normal * -size)
            bands.extend(moved.extrude(normal * (2 * size)).Faces)
        return Part.makeCompound(bands)
    if sub.startswith("Face"):
        return element_of(obj, sub)
    return whole_shape(obj)


def _c_trim(obj, leader, o, refs):
    from . import surface_geom as g

    base = _base(obj)
    cutter = trim_cutter(obj, leader, refs, base)
    meta = bodies.load_meta(leader, META)
    body = bodies.body_of(obj)
    points = [p for name, p in meta.get("cells") or [] if body is not None and name == body.Name]
    if not points:
        raise NeedsPick("Click the pieces to remove.")
    return g.trim(base, cutter, points)


def _c_untrim(obj, leader, o, refs):
    from . import surface_geom as g

    import Part

    base = _base(obj)
    faces, loops = [], []
    for ref in refs[0]:
        if ref[1].startswith("Edge"):
            loops.append(_matching(base, element_of(*ref), "Edge"))
        else:
            faces.append(_matching(base, element_of(*ref), "Face"))
    if o["loop_type"] == "manual":
        if not loops:
            raise NeedsPick("Select the loops to remove: click an edge of each.")
        result = g.untrim_loops(base, loops, o["distance"] if o.get("extend") else 0.0)
    else:
        if not faces:
            raise NeedsPick("Select the faces to untrim.")
        result = g.untrim(base, faces, o["loop_type"], o["distance"] if o.get("extend") else 0.0)
    # Keep Copy: the surface as it was goes on in a body of its own (the step's piece)
    obj.Pieces = Part.makeCompound([base.copy()]) if o.get("keep_copy") else Part.Shape()
    return result


def _matching(shape, element, kind):
    """`shape`'s own sub-shape (isSame works) where `element` (a copy) is."""
    from . import surface_geom as g

    pool = shape.Faces if kind == "Face" else shape.Edges
    for item in pool:
        if item.isSame(element):
            return item
    if kind == "Face":
        point = g.face_point(element)
    else:
        point = element.valueAt((element.FirstParameter + element.LastParameter) / 2.0)
    best = min(pool, key=lambda x: g.distance(x, point)) if pool else None
    if best is None or g.distance(best, point) > 1e-4:
        raise SurfaceError("A %s picked is not on this body any more." % kind.lower())
    return best


def _c_extend(obj, leader, o, refs):
    from . import surface_geom as g

    base = _base(obj)
    edges = [_matching(base, element_of(*ref), "Edge") for ref in refs[0]]
    if not edges:
        raise NeedsPick("Select edges on the outside of a surface body.")
    return g.extend(base, edges, o["distance"], o["extend_type"], o["alignment"])


def _c_stitch(obj, leader, o, refs):
    from . import surface_geom as g

    others = [whole_shape(b) for b, _s in refs[0]]
    if core.is_solid_operation(o.get("operation")):
        # Join / Cut / Intersect: the step is in the solid body it acts on; every surface
        # picked is stitched, and the closed result combined with that solid
        if not others:
            raise NeedsPick("Select the surface bodies to stitch.")
        shape, _open = g.stitch(others, o["tolerance"])
        return g.stitched_operation(_base(obj, "solid"), shape, o["operation"])
    base = _base(obj)
    if not others:
        raise NeedsPick("Select the other surface bodies to stitch to this one.")
    shape, _open = g.stitch([base] + others, o["tolerance"])
    return shape


def _c_unstitch(obj, leader, o, refs):
    import Part

    from . import surface_geom as g

    base = _base(obj, "body")
    faces = [_matching(base, element_of(*ref), "Face") for ref in refs[0]]
    stay, taken = g.unstitch(base, faces)
    if stay is None:  # every face was picked: the first one stays in this body
        stay, taken = taken[0], taken[1:]
    obj.Pieces = Part.makeCompound(taken) if taken else Part.Shape()
    return stay


def _compute_piece(obj):
    source = getattr(obj, "Source", None)
    if source is None or not bodies.alive(source):
        if obj.Shape.isNull():
            raise SurfaceError("The Unstitch this face came from is gone.")
        return bodies.global_shape(obj)  # keeps its last shape
    if kind_of(source) == "untrim":  # Untrim's Keep Copy: the surface before the untrim
        if source.Pieces.isNull() or not source.Pieces.Faces:
            raise SurfaceError("The Untrim this copy came from no longer keeps a copy.")
        kept = source.Pieces.copy()
        shapes = kept.childShapes() if kept.ShapeType == "Compound" else [kept]
        return shapes[0] if len(shapes) == 1 else kept
    faces = source.Pieces.Faces if not source.Pieces.isNull() else []
    if obj.Index - 1 >= len(faces) or obj.Index < 1:
        raise SurfaceError("The Unstitch it came from no longer makes this face.")
    return faces[obj.Index - 1].copy()  # stored in design coordinates


def _c_reverse(obj, leader, o, refs):
    from . import surface_geom as g

    return g.reverse(_base(obj))


COMPUTE = {
    "extrude": _c_extrude,
    "revolve": _c_revolve,
    "sweep": _c_sweep,
    "loft": _c_loft,
    "patch": _c_patch,
    "ruled": _c_ruled,
    "offset": _c_offset,
    "boundary_fill": _c_boundary_fill,
    "thicken": _c_thicken,
    "trim": _c_trim,
    "untrim": _c_untrim,
    "extend": _c_extend,
    "stitch": _c_stitch,
    "unstitch": _c_unstitch,
    "reverse_normal": _c_reverse,
}


# -- building --------------------------------------------------------------------------------------
def _flat(refs):
    out = []
    for obj, sub in refs or []:
        if obj is None:
            continue
        out.append((obj, sub or ""))
    return out


def _set_links(step, prop, refs, keep_steps=None):
    """Write the picks into a link list. A body already linked keeps the step it had (a
    later step added to that body does not change this one, like Fusion's timeline)."""
    value = []
    had = {}
    for obj, sub in refs_of(step, prop):
        if sub or obj.TypeId in CONSTRUCTION_TYPES or curves.is_sketch(obj):
            continue  # an origin plane or a whole sketch is not its body
        body = bodies.body_of(obj)
        if body is not None:
            had[body.Name] = obj
    for obj, sub in _flat(refs):
        if bodies.is_body(obj):
            step_obj = had.get(obj.Name) or obj.Tip
            if keep_steps is not None and obj.Name in keep_steps:
                step_obj = keep_steps[obj.Name]
            if step_obj is step or (step_obj is not None and _after(step_obj, step)):
                step_obj = step.BaseFeature  # this step's own body: as it was before it
            if step_obj is None:
                raise SurfaceError("%s has nothing in it yet." % obj.Label)
            value.append((step_obj, ""))
        else:
            value.append((obj, sub))
    current = refs_of(step, prop)
    if [(o.Name, s) for o, s in current] != [(o.Name, s) for o, s in value]:
        setattr(step, prop, value)


def _after(a, b):
    """True when step `a` comes after step `b` in the same body."""
    body = bodies.body_of(b)
    if body is None or bodies.body_of(a) is not body:
        return False
    group = list(body.Group)
    try:
        return group.index(a) > group.index(b)
    except ValueError:
        return False


def _set_numbers(step, kind, options):
    for option, prop in NUMBERS.get(kind, {}).items():
        if option not in options or prop not in step.PropertiesList:
            continue
        try:
            if any(path == prop for path, _expr in step.ExpressionEngine):
                continue  # a formula drives it
        except Exception:
            pass
        value = float(options[option])
        current = getattr(step, prop)
        current = float(getattr(current, "Value", current))
        if abs(current - value) > 1e-12:
            setattr(step, prop, value)


def _choices(kind, options):
    keep = {}
    for key, value in core.with_defaults(kind, options).items():
        if key in NUMBERS.get(kind, {}) or key in ("target", "bodies", "groups"):
            continue
        if isinstance(value, (str, bool, int, float, list)) or value is None:
            keep[key] = value
    return keep


def _save(step, kind, options, extra=None):
    meta = bodies.load_meta(step, META)
    meta["options"] = _choices(kind, options)
    meta.update(extra or {})
    bodies.save_meta(step, META, meta)


def source_body(refs, doc):
    """The body a new surface body goes beside (its component): the first pick's."""
    for obj, _sub in _flat(refs):
        body = bodies.body_of(obj)
        if body is not None:
            return body
    found = bodies.find_body(doc)
    return found


def _new_host(doc, refs, options):
    from . import components

    src = source_body(refs, doc)
    if src is None:
        return components.new_body_in(doc, components.active_component(doc))
    return components.body_for_new(src, options.get("operation") == "new_component")


def _make_step(body, kind, name):
    step = bodies.insert_after_tip(body, TYPE, name or core.sciforge_type(kind))
    SurfaceFeature(step, kind)
    _attach_view_provider(step)
    return step


def _attach_view_provider(step):
    if not App.GuiUp:
        return
    try:
        from .surface_ui import SurfaceViewProvider

        SurfaceViewProvider(step.ViewObject)
    except Exception:
        try:
            from .bodies_gui import StepViewProvider

            StepViewProvider(step.ViewObject)
        except Exception:
            pass


def _host_for(kind, refs, options, doc):
    """(body the step goes into, True when that body is new)."""
    solid_op = core.is_solid_operation(options.get("operation"))
    if kind in ("thicken", "boundary_fill", "stitch") and solid_op:
        target = options.get("target")
        if target is None or not bodies.has_solid(target):
            raise SurfaceError(
                "Join, Cut and Intersect need a solid body to act on. Pick New Body, or make "
                "a solid first."
            )
        return target, False
    if core.makes_body(kind):
        return None, True
    if kind == "stitch":
        first = refs.get("refs")[0][0] if refs.get("refs") else None
        body = bodies.body_of(first) if first is not None else None
        if body is None:
            raise NeedsPick("Select the surface bodies to stitch.")
        return body, False
    picks = _flat(refs.get("refs"))
    if not picks:
        raise NeedsPick(_hint(kind))
    body = bodies.body_of(picks[0][0])
    if body is None:
        raise SurfaceError("Pick something on a surface body.")
    for obj, _sub in picks[1:]:
        if bodies.body_of(obj) is not body:
            raise SurfaceError(
                "%s works on one body at a time: everything picked must be on %s."
                % (core.title(kind), body.Label)
            )
    return body, False


def _hint(kind):
    return {
        "untrim": "Select the faces to untrim.",
        "extend": "Select edges on the outside of a surface body.",
        "unstitch": "Select the faces (or bodies) to unstitch.",
    }.get(kind, "Select what to work on.")


def build(kind, refs, options, feature=None, name=None):
    """Create a surface step, or update `feature` (a different object when the change
    needs another body: an operation switched between New Body and Join, other picks).
    `refs`: {"refs": [(obj, sub)], "refs2": [...], "refs3": [...]}. Returns the step (the
    leader for Trim / Reverse Normal over several bodies)."""
    options = core.with_defaults(kind, options)
    core.check_values(kind, options)
    first = feature if feature is not None and bodies.alive(feature) else _first_obj(refs)
    doc = first.Document if first is not None else App.ActiveDocument
    if kind == "trim":
        return _build_trim(refs, options, feature, name)
    if kind == "reverse_normal":
        return _build_reverse(options, feature, name)
    body, new = _host_for(kind, refs, options, doc)
    if feature is not None and bodies.alive(feature):
        if not _same_host(feature, body, new, options):
            label = feature.Label
            remove(feature)
            feature = None
            name = name or label
    if feature is None or not bodies.alive(feature):
        if new:
            body = _new_host(doc, _host_refs(kind, refs), options)
            feature = _make_step(body, kind, name)
            component = options.get("operation") == "new_component"
            bodies.save_meta(feature, META, {"created_body": body.Name, "component": component})
            _copy_look_from(refs, body)
        else:
            feature = _make_step(body, kind, name)
    stitch_refs = None
    if kind == "stitch":
        own = bodies.body_of(feature)
        stitch_refs = [(o, s) for o, s in _flat(refs.get("refs")) if bodies.body_of(o) is not own]
    for prop, key in zip(LINKS, ("refs", "refs2", "refs3")):
        value = stitch_refs if (kind == "stitch" and key == "refs") else refs.get(key)
        if kind in ("untrim", "extend", "unstitch") and key == "refs":
            value = _on_base(feature, value)
        _set_links(feature, prop, value or [])
    _set_numbers(feature, kind, options)
    extra = {}
    if kind == "loft":
        extra["groups"] = list(options.get("groups") or [])
    if kind == "boundary_fill":
        extra["cells"] = [list(map(float, p)) for p in options.get("cells") or []]
    _save(feature, kind, options, extra)
    if kind == "unstitch":
        _sync_pieces(feature, len(_flat(refs.get("refs"))))
    if kind == "untrim":
        _sync_pieces(feature, 1 if options.get("keep_copy") else 0, copy=True)
    return feature


def _first_obj(refs):
    for key in ("refs", "refs2", "refs3"):
        for obj, _sub in _flat((refs or {}).get(key)):
            return obj
    return None


def _host_refs(kind, refs):
    return _flat(refs.get("refs")) + _flat(refs.get("refs2"))


def _same_host(feature, body, new, options):
    current = bodies.body_of(feature)
    if new:
        made = created_body(feature)
        component = bool(bodies.load_meta(feature, META).get("component"))
        return made is not None and component == (options.get("operation") == "new_component")
    return current is body and created_body(feature) is None


def _on_base(feature, refs):
    """Picks made on a body's result (its Tip when the dialog opened) are linked to this
    step's base, which is that same result; a whole body stands for all its faces."""
    base = getattr(feature, "BaseFeature", None)
    out = []
    for obj, sub in _flat(refs):
        if base is not None and obj is not base and bodies.body_of(obj) is bodies.body_of(base):
            obj = base
        if not sub and obj is base and base is not None:
            out.extend((base, "Face%d" % (i + 1)) for i in range(len(base.Shape.Faces)))
            continue
        out.append((obj, sub))
    return out


def _copy_look_from(refs, body):
    """A body made from another body's faces (Offset, Thicken...) looks like it."""
    for obj, _sub in _flat(refs.get("refs")):
        src = bodies.body_of(obj)
        if src is not None and src is not body and not curves.is_sketch(obj):
            try:
                body.ShapeMaterial = src.ShapeMaterial
            except Exception:
                pass
            return


# -- Trim and Reverse Normal over several bodies ---------------------------------------------------
def _group(leader):
    if leader is None or not bodies.alive(leader):
        return []
    return [leader] + followers_of(leader)


def _build_trim(refs, options, feature, name):
    """A Trim step in every body that loses a piece; the first is the leader (the timeline
    step), the others follow it."""
    tool = _flat(refs.get("refs"))
    if not tool:
        raise NeedsPick("Select the trim tool: a surface, a plane, a sketch curve or a body.")
    cells = [(n, list(map(float, p))) for n, p in options.get("cells") or []]
    names = []
    for body_name, _p in cells:
        if body_name not in names:
            names.append(body_name)
    if not names:
        raise NeedsPick("Click the pieces to remove.")
    doc = tool[0][0].Document
    wanted = [doc.getObject(n) for n in names if doc.getObject(n) is not None]
    existing = {bodies.body_of(s).Name: s for s in _group(feature) if bodies.body_of(s)}
    steps = []
    for body in wanted:
        step = existing.pop(body.Name, None)
        if step is None:
            step = _make_step(body, "trim", name if not steps else None)
        steps.append(step)
    for step in existing.values():
        _remove_step(step)
    leader = steps[0]
    if leader.Leader is not None:
        leader.Leader = None
    for step in steps[1:]:
        if step.Leader is not leader:
            step.Leader = leader
        bodies.hide_from_timeline(step)
    _show_in_timeline(leader)
    # A body picked as the tool (or cut by it) is linked as it was before this Trim: one of
    # the Trim's own steps may be in it.
    before = {bodies.body_of(s).Name: s.BaseFeature for s in steps if bodies.body_of(s)}
    _set_links(leader, "Refs", tool, keep_steps=before)
    _set_links(leader, "Refs2", _flat(refs.get("refs2")), keep_steps=before)
    _save(leader, "trim", options, {"cells": [[n, p] for n, p in cells]})
    for step in steps[1:]:
        for prop in LINKS:
            if refs_of(step, prop):
                setattr(step, prop, [])
    return leader


def _show_in_timeline(step):
    if "SciForgeTimeline" in step.PropertiesList and not step.SciForgeTimeline:
        step.SciForgeTimeline = True


def _build_reverse(options, feature, name):
    wanted = [b for b in options.get("bodies") or [] if bodies.alive(b)]
    if not wanted:
        raise NeedsPick("Select the surface bodies (or their faces) to reverse.")
    for body in wanted:
        if not is_surface_body(body) and not _reverse_member(feature, body):
            raise SurfaceError(
                "%s is a solid: Reverse Normal works on surface bodies." % body.Label
            )
    existing = {bodies.body_of(s).Name: s for s in _group(feature) if bodies.body_of(s)}
    steps = []
    for body in wanted:
        step = existing.pop(body.Name, None)
        if step is None:
            step = _make_step(body, "reverse_normal", name if not steps else None)
        steps.append(step)
    for step in existing.values():
        _remove_step(step)
    leader = steps[0]
    if leader.Leader is not None:
        leader.Leader = None
    _show_in_timeline(leader)
    for step in steps[1:]:
        if step.Leader is not leader:
            step.Leader = leader
        bodies.hide_from_timeline(step)
    _save(leader, "reverse_normal", options)
    return leader


def _reverse_member(feature, body):
    return any(bodies.body_of(s) is body for s in _group(feature))


# -- Unstitch pieces -------------------------------------------------------------------------------
def _sync_pieces(step, picked, copy=False):
    """One new surface body per face that leaves the body (all but one when every face was
    picked), each starting with a hidden step that takes its face from the Unstitch. With
    copy (Untrim's Keep Copy): `picked` is 0 or 1, one body holding the surface as it was."""
    doc = step.Document
    pieces = pieces_of(step)
    source = bodies.body_of(step)
    try:
        base = step.BaseFeature.Shape if step.BaseFeature is not None else None
        total = len(base.Faces) if base is not None else picked
    except Exception:
        total = picked
    count = picked - 1 if (picked >= total and not copy) else picked
    for piece in pieces[count:]:
        _remove_piece(piece)
    for index in range(len(pieces) + 1, count + 1):
        body = bodies.new_body(doc, like=source)
        piece = _make_step(body, "piece", "SurfacePiece")
        piece.Source = step
        piece.Index = index
        bodies.hide_from_timeline(piece)
        bodies.save_meta(piece, META, {"source": source.Name if source else ""})
        try:
            body.ShapeMaterial = source.ShapeMaterial
        except Exception:
            pass


def piece_body(piece):
    return bodies.body_of(piece)


def _remove_piece(piece):
    body = bodies.body_of(piece)
    if body is not None and list(body.Group) and body.Group[0] is piece:
        bodies.remove_body(body)
        return
    _remove_step(piece)


# -- removing --------------------------------------------------------------------------------------
def _remove_step(step):
    if not bodies.alive(step):
        return
    made = created_body(step)
    if made is not None:
        from . import components

        container = components.container_of(made)
        bodies.remove_body(made)
        if container is not None:
            components.drop_if_empty(container)
        return
    bodies.remove_step(step)


def remove(feature):
    """Take a surface step out again (a cancelled preview, a rebuild with another host)
    with what it made: its new body, its followers, its unstitched pieces."""
    if feature is None or not bodies.alive(feature):
        return
    for follower in followers_of(feature):
        _remove_step(follower)
    for piece in pieces_of(feature):
        _remove_piece(piece)
    _remove_step(feature)


# -- bodies used up (hidden while the step is part of the design) ----------------------------------
def _stitched_bodies(step):
    found = []
    own = bodies.body_of(step)
    for obj, _sub in refs_of(step, "Refs"):
        body = bodies.body_of(obj)
        if body is not None and body is not own and body not in found:
            found.append(body)
    return found


def _fill_tools(step):
    options = options_of(step)
    if not options.get("remove_tools"):
        return []
    found = []
    own = bodies.body_of(step)
    for obj, sub in refs_of(step, "Refs"):
        if obj.TypeId in CONSTRUCTION_TYPES:
            continue  # an origin plane is not its body
        body = bodies.body_of(obj)
        if not sub and body is not None and body is not own and body not in found:
            found.append(body)
    return found


bodies.CONSUMERS["Stitch"] = _stitched_bodies
bodies.CONSUMERS["BoundaryFill"] = _fill_tools


# -- helpers for the dialogs and the browser -------------------------------------------------------
def hide_sketches(step):
    """The sketches a CREATE step was made from are hidden on OK (Fusion hides a sketch
    its feature used); Undo shows them again."""
    for prop in LINKS:
        for obj, _sub in refs_of(step, prop):
            if curves.is_sketch(obj):
                bodies.set_shown(obj, False)


def two_sided(body):
    """Surfaces are seen from both sides: their back is lit like their front."""
    if not App.GuiUp or body is None:
        return
    try:
        vobj = body.ViewObject
        if vobj is not None and "Lighting" in vobj.PropertiesList and vobj.Lighting != "Two side":
            vobj.Lighting = "Two side"
    except Exception:
        pass


def describe(step):
    """A short line for the timeline's hover text and the log."""
    kind = kind_of(step)
    if kind is None:
        return ""
    return "%s (%s)" % (core.title(kind), step.Label)


def problem_text(exc):
    """FreeCAD's exception text without its prefixes."""
    text = str(exc or "").strip()
    for prefix in ("Exception: ", "<Exception> ", "SurfaceError: "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text


def log_built(step):
    try:
        log("%s built in %s" % (describe(step), bodies.body_of(step).Label))
    except Exception as exc:
        warn("surface: %s" % exc)


def dumps_options(options):
    return json.dumps(options, sort_keys=True, default=str)
