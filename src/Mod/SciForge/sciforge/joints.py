# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's joints on FreeCAD 1.1.4's Assembly solver: the document side (no Qt; the dialogs
are in joints_ui.py, the maths in joints_core.py). Spec: docs/sciforge/parity/joints.md.

How it fits FreeCAD (the component contract of the spec):

- The parts a joint moves are the topmost objects of the design: a PartDesign::Body at the
  document root, an App::Part component at the root (its bodies move with it), or a
  Part::Feature solid at the root. Motion is a change of that object's Placement.
- One hidden Assembly::AssemblyObject ("SciForgeAssembly") holds the joints in its Joints
  group; it owns no body or component (the solver reads each part's Placement through the
  joint's references). It is made on the first joint, ground or rigid group.
- A joint is an App::FeaturePython with the proxy JointProxy below, a subclass of FreeCAD's
  own JointObject.Joint, so the C++ solver treats it as one of its own; SciForge keeps its
  Fusion-side data (type, the two snaps, offsets, axes, limits' rest) in extra properties and
  computes the two joint coordinate systems (Placement1/2) itself, Fusion's way.
- Planar rides on FreeCAD's Distance joint between two flat faces (distance 0); Pin-Slot adds
  a hidden helper joint (Distance 0 between a point and a plane) that keeps the pin on the
  slot's line. Rigid groups are hidden Fixed helper joints between the members.
"""

import json
import math

import FreeCAD as App

from . import bodies, joints_core as core, log, warn

ASSEMBLY_NAME = "SciForgeAssembly"
ASSEMBLY_LABEL = "Assembly"
TYPE_PROP = "SciForgeType"
JOINT_TYPES = ("Joint", "AsBuiltJoint")  # SciForgeType of the joints a person made
HELPER_ROLE = "JointHelper"
MEMBER_ROLE = "RigidGroupMember"
PROPS = {
    "fusion": "SciForgeJointType",  # rigid / revolute / ...
    "snap1": "SciForgeSnap1",  # JSON: where joint origin 1 is on component 1
    "snap2": "SciForgeSnap2",
    "offset": "SciForgeOffset",  # JSON: {"x", "y", "z", "angle", "flip"}
    "axes": "SciForgeAxes",  # JSON: {"rotate": "z", "slide": "x"}
    "rest": "SciForgeRest",  # JSON: {"angle": v or None, "slide": v or None}
    "parent": "SciForgeParent",  # helper joints: the joint / rigid group they serve
    "role": "SciForgeRole",  # helpers: JointHelper / RigidGroupMember
    "baseline": "SciForgeBaseline",  # on the assembly: the placements after the last joint
    "placements": "SciForgePlacements",  # on a Position step
}
_ASSEMBLY_TYPE = "Assembly::AssemblyObject"

# FreeCAD's own joint classes (Mod/Assembly, in every FreeCAD 1.1). The proxy below must be a
# subclass of FreeCAD's Joint at import time: a reopened file makes the proxy without
# calling __init__.
try:
    import JointObject as _JointObject
    import UtilsAssembly as _UtilsAssembly

    _JointBase = _JointObject.Joint
except Exception as _exc:  # pragma: no cover - only outside FreeCAD
    _JointObject = _UtilsAssembly = None
    _JointBase = object
    warn("FreeCAD's Assembly joints are not available: %s" % _exc)


JointError = core.JointError  # one error type for the maths and the document side


def _utils():
    if _UtilsAssembly is None:
        raise JointError("FreeCAD's Assembly workbench is missing: joints cannot be made.")
    return _UtilsAssembly


def _joint_module():
    if _JointObject is None:
        raise JointError("FreeCAD's Assembly workbench is missing: joints cannot be made.")
    return _JointObject


# -- placements <-> frames -------------------------------------------------------------------------
def to_frame(plc):
    m = plc.toMatrix()
    return (
        (m.A14, m.A24, m.A34),
        ((m.A11, m.A12, m.A13), (m.A21, m.A22, m.A23), (m.A31, m.A32, m.A33)),
    )


def from_frame(f):
    o, r = f
    return App.Placement(
        App.Matrix(
            r[0][0],
            r[0][1],
            r[0][2],
            o[0],
            r[1][0],
            r[1][1],
            r[1][2],
            o[1],
            r[2][0],
            r[2][1],
            r[2][2],
            o[2],
            0.0,
            0.0,
            0.0,
            1.0,
        )
    )


def _plc_list(plc):
    q = plc.Rotation.Q
    return [plc.Base.x, plc.Base.y, plc.Base.z, q[0], q[1], q[2], q[3]]


def _plc_from_list(values):
    x, y, z, q0, q1, q2, q3 = values
    return App.Placement(App.Vector(x, y, z), App.Rotation(q0, q1, q2, q3))


def _tuple(v):
    return (float(v.x), float(v.y), float(v.z))


# -- the hidden assembly ---------------------------------------------------------------------------
def assembly(doc, create=False):
    """The design's hidden assembly root (made when `create`), or None."""
    if doc is None:
        return None
    for obj in doc.Objects:
        if obj.TypeId == _ASSEMBLY_TYPE and obj.Name == ASSEMBLY_NAME:
            return obj
    for obj in doc.Objects:  # a file whose assembly got another name
        if obj.TypeId == _ASSEMBLY_TYPE and getattr(obj, TYPE_PROP, "") == "Assembly":
            return obj
    if not create:
        return None
    asm = doc.addObject(_ASSEMBLY_TYPE, ASSEMBLY_NAME)
    asm.Label = ASSEMBLY_LABEL
    asm.Type = "Assembly"
    bodies.mark(asm, "Assembly")
    bodies.hide_from_timeline(asm)
    group = asm.newObject("Assembly::JointGroup", "Joints")
    bodies.hide_from_timeline(group)
    bodies.add_prop(asm, "App::PropertyString", PROPS["baseline"], "SciForge")
    if asm.ViewObject is not None:
        try:
            asm.ViewObject.Visibility = True  # the joints draw through it
        except Exception:
            pass
    log("hidden assembly root made for the joints")
    return asm


def joint_group(doc, create=False):
    asm = assembly(doc, create)
    if asm is None:
        return None
    for obj in asm.OutList:
        if obj.TypeId == "Assembly::JointGroup":
            return obj
    group = asm.newObject("Assembly::JointGroup", "Joints")
    bodies.hide_from_timeline(group)
    return group


def is_assembly_piece(obj):
    """The hidden assembly, its groups and its joints: never shown as bodies or steps."""
    try:
        if obj.TypeId in (_ASSEMBLY_TYPE, "Assembly::JointGroup"):
            return True
        return obj.TypeId == "App::FeaturePython" and hasattr(obj, "JointType")
    except Exception:
        return False


# -- parts (what a joint moves) --------------------------------------------------------------------
def is_part(obj):
    """A top-level thing a joint can move: a root body, a root component, a root solid."""
    try:
        if obj is None or is_assembly_piece(obj):
            return False
        if obj.getParentGeoFeatureGroup() is not None:
            return False
        if obj.TypeId == "PartDesign::Body":
            return True
        if obj.TypeId == "App::Part":
            return True
        if getattr(obj, TYPE_PROP, "") or getattr(obj, "SciForgeRole", ""):
            return False  # a SciForge step outside the bodies (a copy's Move...), not a part
        if obj.isDerivedFrom("Part::Feature") and not obj.isDerivedFrom("Part::Datum"):
            return not obj.TypeId.startswith("Sketcher") and bool(obj.Shape.Solids)
    except Exception:
        return False
    return False


def parts(doc):
    return [o for o in doc.Objects if is_part(o)]


def part_of(obj):
    """The part (see is_part) that `obj` belongs to: itself, its body, its component, the
    top-level component of a nested one; None for things outside any part."""
    seen = 0
    current = obj
    while current is not None and seen < 20:
        seen += 1
        if is_part(current):
            return current
        try:
            parent = current.getParentGeoFeatureGroup()
        except Exception:
            parent = None
        if parent is None:
            # a feature at the root of a body is found through InList (sketches, datums)
            try:
                owners = [o for o in current.InList if o.TypeId == "PartDesign::Body"]
            except Exception:
                owners = []
            parent = owners[0] if owners else None
        current = parent
    return None


def _path(part, obj):
    """Object names from `part` down to `obj` (not including the part), dotted + "."."""
    names = []
    current = obj
    guard = 0
    while current is not None and current is not part and guard < 20:
        guard += 1
        names.append(current.Name)
        try:
            current = current.getParentGeoFeatureGroup()
        except Exception:
            current = None
    names.reverse()
    return "".join(n + "." for n in names)


def reference(part, obj, element):
    """FreeCAD's joint reference for an element of `obj` inside `part`: [part, [sub, sub]]."""
    sub = _path(part, obj) + (element or "")
    return [part, [sub, sub]]


def shape_owner(ref):
    """The object whose Shape holds the referenced element (a body, a solid, a datum)."""
    try:
        return _utils().getObject(ref)
    except Exception:
        return None


def element_name(sub):
    return (sub or "").split(".")[-1]


def global_of(ref):
    """Global placement of the referenced object (FreeCAD's convention: the JCS placements
    are relative to it)."""
    try:
        return _utils().getGlobalPlacement(ref)
    except Exception:
        return App.Placement()


def geometry(obj):
    """(shape, to_local): the object's geometry and the placement that takes a point of that
    shape into the object's own coordinates (FreeCAD's Placement1/2 are relative to the
    object). A body's Tip shape is already in body coordinates and never depends on where
    the body stands: a body's placed Shape can lag behind its Placement for a moment after a
    move, and a joint origin computed from that lag landed in the wrong place."""
    if obj.TypeId == "PartDesign::Body":
        tip = obj.Tip
        try:
            if tip is not None and not tip.Shape.isNull():
                return tip.Shape, App.Placement()
        except Exception:
            pass
    shape = obj.Shape
    return shape, shape.Placement.inverse()


# -- picks (what a click means) --------------------------------------------------------------------
class Pick:
    """A click on a component: the part it moves, the object whose shape was hit, the
    element ("Face6", "Edge2", "Vertex3", "" for a whole object or a datum), the FreeCAD
    reference, and the global point clicked (or None)."""

    def __init__(self, part, obj, element, point=None):
        self.part = part
        self.obj = obj
        self.element = element or ""
        self.point = point
        self.ref = reference(part, obj, self.element)

    def __repr__(self):
        return "Pick(%s, %s, %r)" % (self.part.Label, self.obj.Label, self.element)

    def is_datum(self):
        return _is_datum(self.obj)


def _is_datum(obj):
    try:
        return obj.isDerivedFrom("App::LocalCoordinateSystem") or obj.isDerivedFrom("Part::Datum")
    except Exception:
        return False


def _resolve_sub(root, sub):
    """(object, element) of a selection path: "Pad.Face6" on a body is the body's Face6,
    "Body001.Box001.Face5" on a component is Body001's Face5, "Box.JointOrigin." (or a
    datum's axis) is the joint-origin datum itself."""
    doc = root.Document
    names = sub.split(".") if sub else [""]
    element = names[-1]
    obj = root
    for name in names[:-1]:
        child = doc.getObject(name)
        if child is None:
            break
        if child.isDerivedFrom("PartDesign::Feature"):
            continue  # a body's step (its Tip): the element belongs to the body
        obj = child
    try:
        if obj.isDerivedFrom("App::DatumElement"):
            parent = obj.getParent()
            if parent is not None:
                obj = parent
    except Exception:
        pass
    if _is_datum(obj) or not element.startswith(("Face", "Edge", "Vertex")):
        element = ""
    return obj, element


def resolve_selection(root, sub, point=None):
    """A FreeCAD selection entry (root object, sub-element path, picked point) as a Pick, or
    None when it is not on a part (the hidden assembly, a joint's own marker, a sketch)."""
    if root is None or is_assembly_piece(root):
        return None
    obj, element = _resolve_sub(root, sub or "")
    part = part_of(obj) or part_of(root)
    if part is None:
        return None
    if obj is part and obj.TypeId == "App::Part":
        return None  # a component clicked without a body under the mouse
    pnt = App.Vector(point) if point is not None else None
    return Pick(part, obj, element, pnt)


def any_element_ref(part):
    """A reference to some element of a part, for joints whose placement SciForge stores
    itself (as-built, rigid groups): FreeCAD wants an element name in every reference."""
    candidates = [part]
    try:
        if part.TypeId == "App::Part":
            candidates = [o for o in part.OutListRecursive if o.TypeId == "PartDesign::Body"] + [
                o for o in part.OutListRecursive if o.isDerivedFrom("Part::Feature")
            ]
    except Exception:
        pass
    for obj in candidates:
        try:
            if obj.Shape.Vertexes:
                return reference(part, obj, "Vertex1")
        except Exception:
            continue
    raise JointError("%s has no geometry to joint." % part.Label)


def planar_face_ref(pick):
    """A reference to a flat face of the picked object (the picked face when it is flat): the
    solver's planar constraint (Planar, Pin-Slot) needs one on each side."""
    shape = pick.obj.Shape
    if pick.element.startswith("Face"):
        face = shape.getElement(pick.element)
        if face is not None and face.Surface.TypeId == "Part::GeomPlane":
            return pick.ref
    for i, face in enumerate(shape.Faces):
        if face.Surface.TypeId == "Part::GeomPlane":
            return reference(pick.part, pick.obj, "Face%d" % (i + 1))
    raise JointError(
        "%s has no flat face: a Planar or Pin-Slot joint needs one on each component."
        % pick.part.Label
    )


# -- snap points -----------------------------------------------------------------------------------
def _vertex_name(shape, point, tol=1e-7):
    for i, v in enumerate(shape.Vertexes):
        if (v.Point - point).Length <= tol:
            return "Vertex%d" % (i + 1)
    return ""


def _edge_name(shape, edge):
    for i, e in enumerate(shape.Edges):
        try:
            if e.isSame(edge):
                return "Edge%d" % (i + 1)
        except Exception:
            continue
    return ""


def _face_frame(face):
    """(point, Z, X hint) of a face's centre snap in shape coordinates."""
    surface = face.Surface
    kind = surface.TypeId
    if kind == "Part::GeomPlane":
        centre = face.CenterOfMass
        u, v = face.Surface.parameter(centre)
        normal = face.normalAt(u, v)
        hint = _longest_edge_direction(face) or App.Vector(
            surface.Rotation.multVec(App.Vector(1, 0, 0))
        )
        return centre, normal, hint
    if kind in ("Part::GeomCylinder", "Part::GeomCone"):
        axis = App.Vector(surface.Axis)
        rel = face.CenterOfGravity - surface.Center
        centre = surface.Center + axis * rel.dot(axis) / max(axis.Length**2, 1e-12)
        return centre, axis, None
    if kind == "Part::GeomTorus":
        return App.Vector(surface.Center), App.Vector(surface.Axis), None
    if kind == "Part::GeomSphere":
        return App.Vector(surface.Center), App.Vector(0, 0, 1), None
    centre = face.CenterOfMass
    try:
        u, v = face.Surface.parameter(centre)
        normal = face.normalAt(u, v)
    except Exception:
        normal = App.Vector(0, 0, 1)
    return centre, normal, None


def _longest_edge_direction(face):
    best = None
    for edge in face.Edges:
        if edge.Curve.TypeId == "Part::GeomLine" and (best is None or edge.Length > best.Length):
            best = edge
    if best is None:
        return None
    return best.valueAt(best.LastParameter) - best.valueAt(best.FirstParameter)


def _is_circle(edge):
    return edge.Curve.TypeId in ("Part::GeomCircle",)


def _circle_axis(edge):
    return App.Vector(edge.Curve.Axis)


def _edge_frame(edge):
    """(Z, X hint) of an edge's snaps in shape coordinates."""
    if _is_circle(edge):
        return _circle_axis(edge), None
    direction = edge.valueAt(edge.LastParameter) - edge.valueAt(edge.FirstParameter)
    if direction.Length < 1e-9:
        direction = App.Vector(0, 0, 1)
    return direction, None


def _snap(kind, at, point, z, hint):
    return {"kind": kind, "at": at, "point": point, "z": z, "hint": hint}


def _shape_snaps(shape, element):
    """Snap points of an element in the shape's coordinates: dicts with kind, at (the shape
    element the snap sits on), point, z (the joint origin's Z), hint (its X)."""
    out = []
    if element.startswith("Face"):
        face = shape.getElement(element)
        if face is None:
            return out
        centre, z, hint = _face_frame(face)
        out.append(_snap("centre", element, centre, z, hint))
        for v in face.Vertexes:
            out.append(_snap("vertex", _vertex_name(shape, v.Point), v.Point, z, hint))
        for edge in face.Edges:
            name = _edge_name(shape, edge)
            if _is_circle(edge):
                axis = _circle_axis(edge)
                if axis.dot(z) < 0:
                    axis = axis * -1  # a face's round edge turns with the face's normal
                out.append(_snap("circle", name, App.Vector(edge.Curve.Center), axis, hint))
            elif edge.Curve.TypeId == "Part::GeomLine":
                mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
                out.append(_snap("midpoint", name, mid, z, hint))
    elif element.startswith("Edge"):
        edge = shape.getElement(element)
        if edge is None:
            return out
        z, hint = _edge_frame(edge)
        if _is_circle(edge):
            out.append(_snap("circle", element, App.Vector(edge.Curve.Center), z, hint))
        mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        out.append(_snap("midpoint", element, mid, z, hint))
        for v in edge.Vertexes:
            out.append(_snap("vertex", _vertex_name(shape, v.Point), v.Point, z, hint))
    elif element.startswith("Vertex"):
        vertex = shape.getElement(element)
        if vertex is not None:
            out.append(_snap("vertex", element, vertex.Point, None, None))
    return [s for s in out if s["at"] or s["kind"] in ("centre", "midpoint", "circle")]


def _frame_from(point, z, hint):
    """A core frame from a point, a Z direction (None: like the component's axes) and an X
    hint, all in one coordinate system."""
    if z is None:
        return core.frame(_tuple(point))
    try:
        rot = core.rot_from_z(_tuple(z), None if hint is None else _tuple(hint))
    except core.JointError:
        rot = core.IDENTITY
    return (_tuple(point), rot)


def snap_candidates(pick):
    """Fusion's snap points for the element under the mouse, in global coordinates:
    [{"kind", "at", "point" (App.Vector), "frame" (App.Placement)}], the first the one a
    joint origin takes when the mouse is on none in particular (the centre)."""
    if pick.is_datum():
        plc = global_of(pick.ref)
        return [{"kind": "origin", "at": "", "point": App.Vector(plc.Base), "frame": plc}]
    if not pick.element:
        return []
    try:
        shape, to_local = geometry(pick.obj)
    except Exception:
        return []
    G = global_of(pick.ref)
    found = []
    for snap in _shape_snaps(shape, pick.element):
        local = to_local * from_frame(_frame_from(snap["point"], snap["z"], snap["hint"]))
        plc = G * local
        found.append(
            {
                "kind": snap["kind"],
                "at": snap["at"],
                "point": App.Vector(plc.Base),
                "frame": plc,
                "oriented": snap["z"] is not None,  # a bare corner has no direction
            }
        )
    unique = []
    for s in found:
        if all((s["point"] - u["point"]).Length > 1e-7 for u in unique):
            unique.append(s)
    return unique


def nearest_snap(candidates, point):
    if not candidates:
        return None
    if point is None:
        return candidates[0]
    index = core.nearest([_tuple(c["point"]) for c in candidates], _tuple(point))
    return candidates[index]


def snap_record(pick, snap):
    """What a joint stores about one side: enough to find the place again on new geometry
    (the element, the snap kind, the shape element the snap sits on)."""
    return {"kind": snap["kind"], "element": pick.element, "at": snap.get("at", "")}


def as_built_record(plc):
    """A side whose place is stored once, where it was (as-built joints, rigid groups)."""
    return {"kind": "asbuilt", "element": "", "at": "", "frame": _plc_list(plc)}


def local_placement(ref, record):
    """Placement1/2 (relative to the referenced object, FreeCAD's convention) for a stored
    snap on the current geometry. An as-built record gives its stored global place."""
    if not record:
        return App.Placement()
    kind = record.get("kind")
    if kind == "asbuilt":
        return global_of(ref).inverse() * _plc_from_list(record["frame"])
    if kind == "origin":
        return App.Placement()  # the datum itself is the joint origin
    obj = shape_owner(ref)
    if obj is None:
        return App.Placement()
    try:
        shape, to_local = geometry(obj)
    except Exception:
        return App.Placement()
    element = record.get("element") or element_name(ref[1][0])
    snaps = _shape_snaps(shape, element)
    chosen = None
    for s in snaps:
        if s["kind"] == kind and s["at"] == record.get("at", ""):
            chosen = s
            break
    if chosen is None:  # the element changed: fall back to its centre
        chosen = snaps[0] if snaps else None
    if chosen is None:
        return App.Placement()
    hint = chosen["hint"]
    if record.get("x") and chosen["z"] is not None:
        # the X the joint was made with (keeps the component's heading): stored relative to
        # the object, the snap maths work in the shape's coordinates
        hint = to_local.inverse().Rotation.multVec(App.Vector(*record["x"]))
    local = _frame_from(chosen["point"], chosen["z"], hint)
    return to_local * from_frame(local)


def set_heading(joint, index, x_global):
    """Store, for one side, the X axis (global direction) its joint origin must have, so
    the component keeps the heading it was mated with."""
    ref = joint.Reference1 if index == 0 else joint.Reference2
    key = PROPS["snap1" if index == 0 else "snap2"]
    record = _json(joint, key)
    if record.get("kind") in ("asbuilt", "origin") or not ref:
        return
    local = global_of(ref).Rotation.inverted().multVec(App.Vector(x_global))
    record["x"] = [local.x, local.y, local.z]
    _set_json(joint, key, record)


# -- the joint object ------------------------------------------------------------------------------
def _json(obj, prop, default=None):
    try:
        text = getattr(obj, prop, "") or ""
        return json.loads(text) if text else (default if default is not None else {})
    except Exception:
        return default if default is not None else {}


def _set_json(obj, prop, value):
    text = json.dumps(value, sort_keys=True)
    if getattr(obj, prop, None) != text:
        setattr(obj, prop, text)


def _add_props(joint):
    bodies.add_prop(joint, "App::PropertyString", TYPE_PROP, "Base")
    for key in ("fusion", "snap1", "snap2", "offset", "axes", "rest", "role"):
        bodies.add_prop(joint, "App::PropertyString", PROPS[key], "SciForge")
    # global scope: a rigid group's helpers (in the assembly) link the group at the root
    bodies.add_prop(joint, "App::PropertyLinkGlobal", PROPS["parent"], "SciForge")


class JointProxy(_JointBase):
    """SciForge's joint: FreeCAD's JointObject.Joint with Fusion's joint-origin rules.
    Saved in files as "sciforge.joints.JointProxy": keep the name."""

    def __init__(self, joint, fusion_type, sciforge_type="Joint", role=""):
        _add_props(joint)
        setattr(joint, TYPE_PROP, sciforge_type)
        setattr(joint, PROPS["fusion"], fusion_type)
        setattr(joint, PROPS["role"], role)
        if not getattr(joint, PROPS["offset"]):
            _set_json(joint, PROPS["offset"], default_offset())
        if not getattr(joint, PROPS["axes"]):
            _set_json(joint, PROPS["axes"], default_axes(fusion_type))
        if not getattr(joint, PROPS["rest"]):
            _set_json(joint, PROPS["rest"], {"angle": None, "slide": None})
        index = _joint_module().JointTypes.index(core.FREECAD_TYPE[fusion_type])
        _JointBase.__init__(self, joint, index)

    def onDocumentRestored(self, joint):
        _add_props(joint)
        _JointBase.onDocumentRestored(self, joint)

    def onChanged(self, joint, prop):
        if App.isRestoring():
            return
        if prop in ("Reference1", "Reference2"):
            try:
                joint.recompute()
            except Exception:
                pass
        elif prop == "Suppressed" and getattr(joint, PROPS["role"], "") == "":
            # a Pin-Slot's hidden slot joint is off whenever the joint is (the timeline's
            # Suppress sets only the joint)
            for helper in helpers_of(joint):
                try:
                    if bool(helper.Suppressed) != bool(joint.Suppressed):
                        helper.Suppressed = bool(joint.Suppressed)
                except Exception:
                    pass

    def findPlacement(self, joint, ref, index=0):
        try:
            if ref is None or not _utils().isRefValid(ref, 1):
                return App.Placement()
            role = getattr(joint, PROPS["role"], "")
            if role == HELPER_ROLE:
                return helper_placement(joint, index)
            record = _json(joint, PROPS["snap1" if index == 0 else "snap2"])
            plc = local_placement(ref, record)
            f = to_frame(plc)
            if index == 0:
                # the solver makes the two stored joint origins coincide: joint origin 1 is
                # stored with Fusion's offsets, Angle and mating (faces against each other)
                # taken out, so that the component itself ends up where Fusion puts it
                f = core.compose(f, stored_offset(joint))
            axis = motion_axis(joint)
            if axis != "z":
                f = core.to_motion_axis(f, axis)
            return from_frame(f)
        except Exception as exc:
            warn("joint %s: could not place its joint origin: %s" % (joint.Label, exc))
            return App.Placement()

    def execute(self, joint):
        _JointBase.execute(self, joint)

    def dumps(self):
        return None

    def loads(self, state):
        return None


def default_offset():
    return {"x": 0.0, "y": 0.0, "z": 0.0, "angle": 0.0, "flip": False, "mate": True}


def default_axes(fusion_type):
    axes = {"rotate": "z", "slide": "z"}
    if fusion_type == "pinslot":
        axes["slide"] = "x"
    return axes


def fusion_type(joint):
    return getattr(joint, PROPS["fusion"], "") or "rigid"


def motion_axis(joint):
    """The joint origin axis FreeCAD moves about (Z after this turn): the Rotate axis of a
    Revolute / Cylindrical, the Normal of a Planar, the Slide axis of a Slider."""
    axes = _json(joint, PROPS["axes"], default_axes(fusion_type(joint)))
    kind = fusion_type(joint)
    if kind in ("revolute", "cylindrical", "planar"):
        return axes.get("rotate", "z")
    if kind == "slider":
        return axes.get("slide", "z")
    return "z"


def offsets(joint):
    data = default_offset()
    data.update(_json(joint, PROPS["offset"]))
    return data


def is_joint(obj):
    try:
        return obj.TypeId == "App::FeaturePython" and getattr(obj, TYPE_PROP, "") in JOINT_TYPES
    except Exception:
        return False


def is_helper(obj):
    try:
        return obj.TypeId == "App::FeaturePython" and getattr(obj, PROPS["role"], "") in (
            HELPER_ROLE,
            MEMBER_ROLE,
        )
    except Exception:
        return False


def joints(doc):
    """The joints a person made, oldest first."""
    return sorted((o for o in doc.Objects if is_joint(o)), key=lambda o: o.ID)


def helpers_of(parent):
    try:
        return [
            o
            for o in parent.Document.Objects
            if is_helper(o) and getattr(o, PROPS["parent"], None) is parent
        ]
    except Exception:
        return []


def part1(joint):
    return joint.Reference1[0] if joint.Reference1 else None


def part2(joint):
    return joint.Reference2[0] if joint.Reference2 else None


def jcs_global(joint, index):
    """Joint origin 1 or 2 as a global placement."""
    ref = joint.Reference1 if index == 0 else joint.Reference2
    plc = joint.Placement1 if index == 0 else joint.Placement2
    if not ref:
        return App.Placement()
    return _utils().getJcsGlobalPlc(plc, ref)


def label_for(doc, fusion_type):
    return "%s %d" % (
        core.TITLES[fusion_type],
        core.label_number([j.Label for j in joints(doc)], core.TITLES[fusion_type]),
    )


# -- making joints ---------------------------------------------------------------------------------
def _new_joint_object(doc, fusion_type, sciforge_type="Joint", role="", label=None):
    group = joint_group(doc, create=True)
    joint = group.newObject("App::FeaturePython", "Joint")
    joint.Label = label or label_for(doc, fusion_type)
    JointProxy(joint, fusion_type, sciforge_type, role)
    if role:
        bodies.hide_from_timeline(joint)
    return joint


def _check_two_parts(pick1, pick2):
    if pick1 is None or pick2 is None:
        raise JointError("Pick a point on each of two components.")
    if pick1.part is pick2.part:
        raise JointError(
            "Both picks are on %s. Pick a point on another component." % pick1.part.Label
        )


def create_joint(doc, fusion_type, pick1, snap1, pick2, snap2, offset=None, axes=None):
    """A Fusion Joint: component 1 (pick1 / snap1) moves onto component 2 (pick2 / snap2).
    Returns the joint. The caller holds the undo step."""
    _check_two_parts(pick1, pick2)
    if fusion_type not in core.JOINT_TYPES:
        raise JointError("Unknown joint type %r." % (fusion_type,))
    joint = _new_joint_object(doc, fusion_type)
    _set_json(joint, PROPS["snap1"], snap_record(pick1, snap1))
    _set_json(joint, PROPS["snap2"], snap_record(pick2, snap2))
    data = dict(default_offset(), **(offset or {}))
    # faces mate (Z against each other); a bare corner has no face: the axes start the same
    # way (a corner picked on a face takes the face's direction and mates)
    data["mate"] = bool(snap1.get("oriented", True) and snap2.get("oriented", True))
    _set_json(joint, PROPS["offset"], data)
    if axes:
        _set_json(joint, PROPS["axes"], dict(default_axes(fusion_type), **axes))
    set_references(joint, pick1, pick2)
    return joint


def set_references(joint, pick1, pick2):
    """Point the joint at its two components (Planar / Pin-Slot need flat faces for the
    solver; the snaps keep the joint origins where they were picked) and make the helper."""
    kind = fusion_type(joint)
    if kind in ("planar", "pinslot"):
        ref1, ref2 = planar_face_ref(pick1), planar_face_ref(pick2)
    else:
        ref1, ref2 = pick1.ref, pick2.ref
    joint.Reference1 = ref1
    joint.Reference2 = ref2
    joint.Placement1 = joint.Proxy.findPlacement(joint, ref1, 0)
    joint.Placement2 = joint.Proxy.findPlacement(joint, ref2, 1)
    sync_helper(joint)


def set_type(joint, fusion_type, pick1=None, pick2=None):
    """Change the type of an existing joint (the Motion tab's Type)."""
    if fusion_type not in core.JOINT_TYPES:
        raise JointError("Unknown joint type %r." % (fusion_type,))
    old = getattr(joint, PROPS["fusion"], "")
    if fusion_type == old:
        return
    setattr(joint, PROPS["fusion"], fusion_type)
    joint.JointType = core.FREECAD_TYPE[fusion_type]
    if joint.Label.startswith(core.TITLES.get(old, "") + " "):
        joint.Label = label_for(joint.Document, fusion_type)  # "Rigid 1" -> "Revolute 1"
    axes = _json(joint, PROPS["axes"], {})
    merged = default_axes(fusion_type)
    merged.update({k: v for k, v in axes.items() if v in ("x", "y", "z")})
    if fusion_type == "pinslot" and merged.get("slide") == "z":
        merged["slide"] = "x"
    _set_json(joint, PROPS["axes"], merged)
    if fusion_type in ("planar", "pinslot"):
        if pick1 is not None and pick2 is not None:
            joint.Reference1 = planar_face_ref(pick1)
            joint.Reference2 = planar_face_ref(pick2)
        joint.Distance = 0.0
    elif pick1 is not None and pick2 is not None:
        joint.Reference1, joint.Reference2 = pick1.ref, pick2.ref
    refresh_placements(joint)
    sync_helper(joint)


def refresh_placements(joint):
    joint.Placement1 = joint.Proxy.findPlacement(joint, joint.Reference1, 0)
    joint.Placement2 = joint.Proxy.findPlacement(joint, joint.Reference2, 1)


def set_offset(joint, **values):
    data = offsets(joint)
    for key, value in values.items():
        if key not in data:
            raise JointError("Unknown offset %r." % (key,))
        data[key] = bool(value) if key in ("flip", "mate") else float(value)
    _set_json(joint, PROPS["offset"], data)


def set_axes(joint, **values):
    data = _json(joint, PROPS["axes"], default_axes(fusion_type(joint)))
    for key, value in values.items():
        if value not in ("x", "y", "z"):
            raise JointError("Unknown axis %r." % (value,))
        data[key] = value
    _set_json(joint, PROPS["axes"], data)
    refresh_placements(joint)
    sync_helper(joint)


# -- the Pin-Slot helper ---------------------------------------------------------------------------
def helper_placement(helper, index):
    """The hidden point-in-plane joint of a Pin-Slot: the pin's point on side 1, on side 2
    the plane through the joint origin whose normal is the in-plane axis the slot does not
    slide along."""
    parent = getattr(helper, PROPS["parent"], None)
    if parent is None or not _utils().isRefValid(parent.Reference1, 1):
        return App.Placement()
    # FreeCAD's solver puts the face first in a point-to-plane Distance joint and swaps the
    # references of a joint that has them the other way round: go by the element, not the
    # side
    ref = helper.Reference1 if index == 0 else helper.Reference2
    element = element_name(ref[1][0]) if _utils().isRefValid(ref, 1) else ""
    if element.startswith("Vertex"):
        return App.Placement(parent.Placement1)  # the pin's point, on component 1
    axes = _json(parent, PROPS["axes"], default_axes("pinslot"))
    slide = axes.get("slide", "x")
    normal = "y" if slide == "x" else "x"
    return from_frame(core.to_motion_axis(to_frame(parent.Placement2), normal))


def sync_helper(joint):
    """Make, update or remove the Pin-Slot helper of a joint."""
    doc = joint.Document
    existing = [h for h in helpers_of(joint) if getattr(h, PROPS["role"], "") == HELPER_ROLE]
    if fusion_type(joint) != "pinslot":
        for h in existing:
            doc.removeObject(h.Name)
        return None
    helper = existing[0] if existing else None
    if helper is None:
        helper = _new_joint_object(
            doc, "planar", "Helper", HELPER_ROLE, label=joint.Label + " slot"
        )
        setattr(helper, PROPS["parent"], joint)
        helper.Visibility = False
    helper.JointType = "Distance"
    helper.Distance = 0.0
    p1, p2 = part1(joint), part2(joint)
    if p1 is None or p2 is None:
        return helper
    # the flat face of component 2 first, then a point of the pin's object (any vertex): that
    # is what tells FreeCAD's solver "point in plane", in the order it keeps
    obj1 = shape_owner(joint.Reference1)
    helper.Reference1 = joint.Reference2
    helper.Reference2 = reference(p1, obj1, "Vertex1") if obj1 is not None else joint.Reference1
    helper.Placement1 = helper_placement(helper, 0)
    helper.Placement2 = helper_placement(helper, 1)
    helper.Suppressed = bool(getattr(joint, "Suppressed", False))
    return helper


# -- grounding -------------------------------------------------------------------------------------
def grounds(doc):
    return [
        o
        for o in doc.Objects
        if o.TypeId == "App::FeaturePython" and "ObjectToGround" in o.PropertiesList
    ]


def ground_of(part):
    for g in grounds(part.Document):
        if g.ObjectToGround is part:
            return g
    return None


def is_grounded(part):
    return part is not None and ground_of(part) is not None


def ground(part):
    """Ground a part: it never moves. Returns the ground object (existing or new)."""
    if not is_part(part):
        raise JointError("%s is not a component or body that joints can move." % part.Label)
    found = ground_of(part)
    if found is not None:
        return found
    doc = part.Document
    group = joint_group(doc, create=True)
    obj = group.newObject("App::FeaturePython", "Ground")
    obj.Label = "Ground %s" % part.Label
    _joint_module().GroundedJoint(obj, part)
    bodies.mark(obj, "Ground")
    bodies.hide_from_timeline(obj)
    log("%s grounded" % part.Label)
    return obj


def unground(part):
    found = ground_of(part)
    if found is None:
        return False
    found.Document.removeObject(found.Name)
    log("%s ungrounded" % part.Label)
    return True


def _with_helpers(joint):
    return [] if joint is None else [joint] + helpers_of(joint)


def connected(part, excluding=None):
    """True when joints chain the part to a grounded part (excluding one joint and its
    helpers, if given)."""
    asm = assembly(part.Document)
    if asm is None:
        return False
    skipped = _with_helpers(excluding)
    was = [bool(getattr(j, "Suppressed", False)) for j in skipped]
    for j in skipped:
        j.Suppressed = True
    try:
        return bool(asm.isPartConnected(part))
    finally:
        for j, state in zip(skipped, was):
            j.Suppressed = state


def _joints_between(doc, excluding=None):
    """[(part a, part b)] for every active joint (helpers included), except `excluding`
    and its helpers."""
    pairs = []
    skipped = _with_helpers(excluding)
    for obj in doc.Objects:
        if any(obj is s for s in skipped) or not (is_joint(obj) or is_helper(obj)):
            continue
        if getattr(obj, "Suppressed", False):
            continue
        a, b = part1(obj), part2(obj)
        if a is not None and b is not None and a is not b:
            pairs.append((a, b))
    return pairs


def _reachable(start, pairs):
    seen = {start.Name: start}
    queue = [start]
    while queue:
        current = queue.pop()
        for a, b in pairs:
            for x, y in ((a, b), (b, a)):
                if x is current and y.Name not in seen:
                    seen[y.Name] = y
                    queue.append(y)
    return seen


def downstream(part, joint):
    """The parts that hang on `part` through other joints and are not held by the ground
    themselves: they move with it (FreeCAD's getDownstreamParts, in Python)."""
    doc = part.Document
    pairs = _joints_between(doc, excluding=joint)
    held = {}
    for g in grounds(doc):
        if g.ObjectToGround is not None:
            held.update(_reachable(g.ObjectToGround, pairs))
    hanging = _reachable(part, pairs)
    return [p for name, p in hanging.items() if name not in held and p is not part]


def moving_side(joint):
    """Which component a new / edited joint moves: component 1 unless something holds it
    and component 2 is free; None when both are held (the solver decides)."""
    p1, p2 = part1(joint), part2(joint)
    if p1 is None or p2 is None:
        return None
    if not connected(p1, excluding=joint):
        return 0
    if not connected(p2, excluding=joint):
        return 1
    return None


def ensure_ground(joint):
    """FreeCAD's solver drops joints not chained to a grounded part: when neither component
    is, component 2 is grounded (Fusion needs no ground: spec, Known gaps). Returns the
    grounded part or None."""
    p1, p2 = part1(joint), part2(joint)
    if p1 is None or p2 is None:
        return None
    if connected(p1, excluding=joint) or connected(p2, excluding=joint):
        return None
    ground(p2)
    return p2


def move_part(part, transform, joint=None):
    """Apply a global transform (App.Placement) to a part and whatever hangs on it."""
    targets = [part] + (downstream(part, joint) if joint is not None else [])
    for target in targets:
        target.Placement = transform * target.Placement


def mates(joint):
    """Whether the two joint origins' Z axes end up against each other: Fusion mates faces
    and Flip turns that over; a bare corner has no face to mate, so there the axes start the
    same way (the offset record's "mate" says which rule applies)."""
    data = offsets(joint)
    return bool(data.get("mate", True)) != bool(data["flip"])


def stored_offset(joint):
    """See joints_core.stored_offset: offsets, Angle and mating folded into joint origin 1."""
    data = offsets(joint)
    return core.stored_offset((data["x"], data["y"], data["z"]), data["angle"], mates(joint))


def _plain(frame, joint):
    """A stored joint origin without the Motion-tab axis turn (both sides share it)."""
    axis = motion_axis(joint)
    if axis == "z":
        return frame
    return (frame[0], core.rot_mul(frame[1], core.rot_transpose(core.AXIS_TO_Z[axis])))


def align(joint, first=False):
    """Place the moving component so the two stored joint origins coincide (that is where
    Fusion's offsets, Angle and Flip put component 1), then solve. `first`: the joint is
    new, so the component keeps its heading (no spin about the joint axis) and that heading
    becomes the joint's X. Returns the solver's result code (0 = fine)."""
    refresh_placements(joint)
    side = moving_side(joint)
    if side is not None:
        jcs1 = to_frame(jcs_global(joint, 0))
        jcs2 = to_frame(jcs_global(joint, 1))
        if side == 0:
            T = core.mate_transform(jcs1, jcs2)
            if first:
                T = core.keep_heading(T, jcs2[0], core.axis_of(jcs2[1], 2))
            move_part(part1(joint), from_frame(T), joint)
            if first:
                # joint origin 1's own X: the one that makes the stored frames coincide
                own = core.own_frame(_plain(jcs2, joint), *_offset_args(joint))
                set_heading(joint, 0, core.axis_of(own[1], 0))
                refresh_placements(joint)
        else:
            # component 2 is the free one: it comes to joint origin 1 instead
            T = core.mate_transform(jcs2, jcs1)
            if first:
                T = core.keep_heading(T, jcs1[0], core.axis_of(jcs1[1], 2))
            move_part(part2(joint), from_frame(T), joint)
            if first:
                set_heading(joint, 1, core.axis_of(_plain(jcs1, joint)[1], 0))
                refresh_placements(joint)
    sync_helper(joint)
    return solve(joint.Document)


def _offset_args(joint):
    data = offsets(joint)
    return (data["x"], data["y"], data["z"]), data["angle"], mates(joint)


def own_jcs1(joint):
    """Component 1's own joint origin (where Fusion draws its triad), global."""
    return from_frame(
        core.own_frame(_plain(to_frame(jcs_global(joint, 0)), joint), *_offset_args(joint))
    )


_LAST_BROKEN = []  # labels of the joints the last solve could not satisfy


def satisfied(joint, tol=1e-4):
    """True when the joint's two (stored) joint origins sit as its type demands. FreeCAD's
    solver reports success on a flipped or torn arrangement when joints fight each other
    (its equations accept a half turn), so every solve is checked against this."""
    try:
        j1, j2 = jcs_global(joint, 0), jcs_global(joint, 1)
    except Exception:
        return True
    zv = App.Vector(0, 0, 1)
    xv = App.Vector(1, 0, 0)
    d = j1.Base - j2.Base
    z1, z2 = j1.Rotation.multVec(zv), j2.Rotation.multVec(zv)
    x1, x2 = j1.Rotation.multVec(xv), j2.Rotation.multVec(xv)

    def same(a, b):
        return a.dot(b) > 1.0 - 1e-6

    def on_axis():
        return (d - z2 * d.dot(z2)).Length < tol

    kind = getattr(joint, "JointType", "")
    if kind == "Fixed":
        return d.Length < tol and same(z1, z2) and same(x1, x2)
    if kind == "Revolute":
        return d.Length < tol and same(z1, z2)
    if kind == "Cylindrical":
        return same(z1, z2) and on_axis()
    if kind == "Slider":
        return same(z1, z2) and same(x1, x2) and on_axis()
    if kind == "Ball":
        return d.Length < tol
    if kind == "Distance":
        if getattr(joint, PROPS["role"], "") == HELPER_ROLE:
            # a point (on a vertex) in a plane (on a face), whichever side each is on
            first = element_name(joint.Reference1[1][0]) if joint.Reference1 else ""
            plane, point = (j2, j1) if first.startswith("Vertex") else (j1, j2)
            return abs((point.Base - plane.Base).dot(plane.Rotation.multVec(zv))) < tol
        return same(z1, z2) and abs(d.dot(z2)) < tol
    return True


def broken_joints(doc):
    """The active joints (and helpers) the current placements do not satisfy, among those
    the solver works on (chained to a grounded part)."""
    asm = assembly(doc)
    if asm is None:
        return []
    found = []
    for obj in doc.Objects:
        if not (is_joint(obj) or is_helper(obj)) or getattr(obj, "Suppressed", False):
            continue
        p1, p2 = part1(obj), part2(obj)
        if p1 is None or p2 is None:
            continue
        try:
            if not (asm.isPartConnected(p1) or asm.isPartConnected(p2)):
                continue
        except Exception:
            pass
        if not satisfied(obj):
            parent = getattr(obj, PROPS["parent"], None) if is_helper(obj) else None
            found.append(parent if parent is not None else obj)
    return found


def solve(doc):
    """Run FreeCAD's solver; 0 when it worked (see solve_message): -2 when it said it did
    but the joints are not all satisfied."""
    asm = assembly(doc)
    if asm is None:
        return 0
    try:
        code = int(asm.solve())
    except Exception as exc:
        warn("joints: solve failed: %s" % exc)
        return -1
    if code == 0:
        broken = broken_joints(doc)
        _LAST_BROKEN[:] = sorted({b.Label for b in broken})
        if broken:
            log("joints the solver could not satisfy: %s" % ", ".join(_LAST_BROKEN))
            return -2
    return code


SOLVE_MESSAGES = {
    0: "",
    -6: "No component is grounded, so nothing holds the assembly: ground one (right-click a "
    "body in the browser).",
    -1: "The joints cannot all be satisfied together (one of them fights another). Undo the "
    "last change or suppress a joint.",
    -2: "The joints cannot all be satisfied together: %s fights the others. Change it, "
    "suppress a joint, or Cancel.",
}


def solve_message(code):
    if code == 0:
        return ""
    if code == -2:
        return SOLVE_MESSAGES[-2] % (", ".join(_LAST_BROKEN) or "a joint")
    return SOLVE_MESSAGES.get(code, "The solver could not place the components (code %s)." % code)


# -- values, limits, driving -----------------------------------------------------------------------
def slide_axis(joint):
    """The joint origin 2 axis a slide is measured along: a Pin-Slot's slot, else Z."""
    if fusion_type(joint) == "pinslot":
        return _json(joint, PROPS["axes"], default_axes("pinslot")).get("slide", "x")
    return "z"


def value(joint):
    """(angle in degrees, slide in mm) of the joint now."""
    return core.joint_value(
        to_frame(jcs_global(joint, 0)), to_frame(jcs_global(joint, 1)), slide_axis(joint)
    )


def limits(joint):
    """{"angle": {"min", "max", "rest"}, "slide": {...}} with None for an unset value."""
    rest = _json(joint, PROPS["rest"], {"angle": None, "slide": None})
    return {
        "angle": {
            "min": joint.AngleMin.Value if joint.EnableAngleMin else None,
            "max": joint.AngleMax.Value if joint.EnableAngleMax else None,
            "rest": rest.get("angle"),
        },
        "slide": {
            "min": joint.LengthMin.Value if joint.EnableLengthMin else None,
            "max": joint.LengthMax.Value if joint.EnableLengthMax else None,
            "rest": rest.get("slide"),
        },
    }


def set_limits(joint, angle=None, slide=None):
    """Set the limits (each a dict with min / max / rest, None = off); the rest must lie
    inside the range."""
    rest = _json(joint, PROPS["rest"], {"angle": None, "slide": None})
    if angle is not None:
        a = core.normalize_limits(angle)
        joint.EnableAngleMin = a["min"] is not None
        joint.EnableAngleMax = a["max"] is not None
        if a["min"] is not None:
            joint.AngleMin = a["min"]
        if a["max"] is not None:
            joint.AngleMax = a["max"]
        rest["angle"] = a["rest"]
    if slide is not None:
        s = core.normalize_limits(slide)
        joint.EnableLengthMin = s["min"] is not None
        joint.EnableLengthMax = s["max"] is not None
        if s["min"] is not None:
            joint.LengthMin = s["min"]
        if s["max"] is not None:
            joint.LengthMax = s["max"]
        rest["slide"] = s["rest"]
    _set_json(joint, PROPS["rest"], rest)


def has_angle(joint):
    return fusion_type(joint) in core.HAS_ANGLE


def has_slide(joint):
    return fusion_type(joint) in core.HAS_DISTANCE


def driven_part(joint):
    """The side a drive moves (the free one), with the index of its joint origin. When both
    sides are held by other joints (a closed loop) the side that is not grounded moves and
    the solver carries the rest of the loop."""
    side = moving_side(joint)
    if side is None:
        p1, p2 = part1(joint), part2(joint)
        if is_grounded(p1) and is_grounded(p2):
            raise JointError(
                "%s and %s are both grounded: unground one to drive %s."
                % (p1.Label, p2.Label, joint.Label)
            )
        side = 1 if is_grounded(p1) else 0
    return (part1(joint) if side == 0 else part2(joint)), side


def drive(joint, angle=None, slide=None, do_solve=True):
    """Put the joint at an angle and / or slide (clamped to its limits) by moving the free
    component and whatever hangs on it, then solve so the rest of the chain follows.
    Returns (angle, slide) actually set."""
    lim = limits(joint)
    if angle is not None:
        angle = core.clamp(angle, lim["angle"]["min"], lim["angle"]["max"])
        if not has_angle(joint):
            angle = None
    if slide is not None:
        slide = core.clamp(slide, lim["slide"]["min"], lim["slide"]["max"])
        if not has_slide(joint):
            slide = None
    part, side = driven_part(joint)
    jcs1 = to_frame(jcs_global(joint, 0))
    jcs2 = to_frame(jcs_global(joint, 1))
    T = core.drive_transform(jcs1, jcs2, angle, slide, slide_axis(joint))
    if side == 1:
        # component 2 moves instead: the same relative motion, the other way round
        T = core.inverse(T)
    move_part(part, from_frame(T), joint)
    if do_solve:
        solve(joint.Document)
    return value(joint)


def keep_in_limits(joint):
    """A joint standing outside its limits (they were just set) goes to the nearest one.
    Returns True when it moved."""
    lim = limits(joint)
    angle, slide = value(joint)
    a = core.clamp(angle, lim["angle"]["min"], lim["angle"]["max"]) if has_angle(joint) else None
    s = core.clamp(slide, lim["slide"]["min"], lim["slide"]["max"]) if has_slide(joint) else None
    if (a is None or abs(a - angle) < 1e-9) and (s is None or abs(s - slide) < 1e-9):
        return False
    drive(joint, angle=a, slide=s)
    return True


def go_to_rest(joint):
    """Put the joint at its Rest value(s), when set (Fusion: where the motion settles).
    Returns True when it moved."""
    lim = limits(joint)
    angle = lim["angle"]["rest"] if has_angle(joint) else None
    slide = lim["slide"]["rest"] if has_slide(joint) else None
    if angle is None and slide is None:
        return False
    drive(joint, angle=angle, slide=slide)
    return True


def wobble(joint, phase, span):
    """Move a Ball (pitch / yaw) or Planar (slide in its plane) joint for the preview."""
    kind = fusion_type(joint)
    part, side = driven_part(joint)
    jcs1 = to_frame(jcs_global(joint, 0))
    jcs2 = to_frame(jcs_global(joint, 1))
    t = 2.0 * math.pi * phase
    if kind == "ball":
        T = core.wobble_frame(jcs1, jcs2, pitch=20.0 * math.sin(t), yaw=20.0 * math.sin(2 * t))
    elif kind == "planar":
        T = core.slide_frame(jcs1, jcs2, dx=span * math.sin(t), dy=0.5 * span * math.sin(2 * t))
    else:
        return
    if side == 1:
        T = core.inverse(T)  # component 2 moves instead
    move_part(part, from_frame(T), joint)


def part_size(part):
    try:
        box = part.Shape.BoundBox
        return float(box.DiagonalLength) if box.isValid() else 10.0
    except Exception:
        return 10.0


# -- placements of every part (capture / revert) ---------------------------------------------------
def placements(doc):
    return {p.Name: _plc_list(p.Placement) for p in parts(doc)}


def apply_placements(doc, stored):
    for name, values in (stored or {}).items():
        obj = doc.getObject(name)
        if obj is not None and is_part(obj):
            plc = _plc_from_list(values)
            if not obj.Placement.isSame(plc, 1e-7):
                obj.Placement = plc


def save_baseline(doc):
    """Remember where the joints put everything (Revert without a captured position)."""
    asm = assembly(doc)
    if asm is None:
        return
    bodies.add_prop(asm, "App::PropertyString", PROPS["baseline"], "SciForge")
    _set_json(asm, PROPS["baseline"], placements(doc))


def baseline(doc):
    asm = assembly(doc)
    return _json(asm, PROPS["baseline"]) if asm is not None else {}


def positions(doc):
    """Captured Position steps, oldest first."""
    return sorted(
        (o for o in doc.Objects if getattr(o, TYPE_PROP, "") == "Position"), key=lambda o: o.ID
    )


def last_positions(doc):
    """The newest captured position's placements, else the baseline."""
    found = positions(doc)
    if found:
        return _json(found[-1], PROPS["placements"])
    return baseline(doc)


def positions_dirty(doc, tol=1e-6):
    """True when a part stands elsewhere than the last capture / the joints put it."""
    stored = last_positions(doc)
    if not stored:
        return False
    for name, values in stored.items():
        obj = doc.getObject(name)
        if obj is None or not is_part(obj):
            continue
        if not obj.Placement.isSame(_plc_from_list(values), tol):
            return True
    return False


class PositionProxy:
    """A captured position (Fusion's Capture Position step). Saved as
    "sciforge.joints.PositionProxy": keep the name."""

    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        pass

    def onChanged(self, obj, prop):
        pass

    def dumps(self):
        return None

    def loads(self, state):
        return None


def capture_position(doc):
    """Record where every part stands as a Position step; returns it."""
    if assembly(doc) is None:
        raise JointError("Nothing to capture: there are no joints yet.")
    obj = doc.addObject("App::FeaturePython", "Position")
    obj.Label = "Position %d" % core.label_number([p.Label for p in positions(doc)], "Position")
    PositionProxy(obj)
    bodies.mark(obj, "Position")
    bodies.add_prop(obj, "App::PropertyString", PROPS["placements"], "SciForge")
    _set_json(obj, PROPS["placements"], placements(doc))
    save_baseline(doc)
    return obj


def revert_position(doc):
    """Put every part back where the last capture (or the joints) left it."""
    stored = last_positions(doc)
    if not stored:
        raise JointError("Nothing to revert to: no position was captured.")
    apply_placements(doc, stored)
    return solve(doc)


# -- rigid groups ----------------------------------------------------------------------------------
class RigidGroupProxy:
    """Fusion's Rigid Group: members locked together where they stand; the hidden Fixed
    helper joints do the holding. Saved as "sciforge.joints.RigidGroupProxy": keep the
    name."""

    def __init__(self, obj):
        obj.Proxy = self
        bodies.add_prop(obj, "App::PropertyLinkList", "Members", "Rigid Group", hidden=False)
        bodies.add_prop(obj, "App::PropertyBool", "IncludeChildren", "Rigid Group", hidden=False)
        if not obj.hasExtension("App::SuppressibleExtensionPython"):
            obj.addExtension("App::SuppressibleExtensionPython")

    def onDocumentRestored(self, obj):
        self.__init__(obj)

    def execute(self, obj):
        pass

    def onChanged(self, obj, prop):
        if App.isRestoring():
            return
        if prop == "Suppressed":
            for helper in helpers_of(obj):
                try:
                    helper.Suppressed = bool(obj.Suppressed)
                except Exception:
                    pass

    def dumps(self):
        return None

    def loads(self, state):
        return None


def is_rigid_group(obj):
    try:
        return getattr(obj, TYPE_PROP, "") == "RigidGroup"
    except Exception:
        return False


def rigid_groups(doc):
    return sorted((o for o in doc.Objects if is_rigid_group(o)), key=lambda o: o.ID)


def create_rigid_group(doc, members, include_children=True):
    members = [m for m in members if is_part(m)]
    if len(members) < 2:
        raise JointError("Pick two or more components for a rigid group.")
    joint_group(doc, create=True)
    obj = doc.addObject("App::FeaturePython", "RigidGroup")
    obj.Label = "Rigid Group %d" % core.label_number(
        [g.Label for g in rigid_groups(doc)], "Rigid Group"
    )
    RigidGroupProxy(obj)
    bodies.mark(obj, "RigidGroup")
    obj.Members = members
    obj.IncludeChildren = bool(include_children)
    rebuild_rigid_group(obj)
    return obj


def rebuild_rigid_group(group):
    """Make the hidden Fixed joints between the first member and every other member."""
    doc = group.Document
    for helper in helpers_of(group):
        doc.removeObject(helper.Name)
    members = [m for m in group.Members if m is not None and is_part(m)]
    if len(members) < 2:
        return
    anchor = members[0]
    frame = App.Placement(anchor.Placement)
    for member in members[1:]:
        helper = _new_joint_object(doc, "rigid", "Helper", MEMBER_ROLE, label=group.Label + " link")
        _set_json(helper, PROPS["offset"], dict(default_offset(), mate=False))  # as they stand
        setattr(helper, PROPS["parent"], group)
        helper.Visibility = False
        _set_json(helper, PROPS["snap1"], as_built_record(frame))
        _set_json(helper, PROPS["snap2"], as_built_record(frame))
        helper.Reference1 = any_element_ref(member)
        helper.Reference2 = any_element_ref(anchor)
        refresh_placements(helper)
        helper.Suppressed = bool(getattr(group, "Suppressed", False))
    if not any(connected(m) for m in members):
        ground(anchor)
    solve(doc)


# -- as-built joints -------------------------------------------------------------------------------
def create_as_built_joint(doc, fusion_type, part_a, part_b, origin_pick=None, origin_snap=None):
    """A joint between two components where they stand. `origin_pick` / `origin_snap` give
    the joint origin (the axis of the motion) for every type but Rigid; the side it was
    picked on follows that geometry, the other side keeps the place as built."""
    _check_as_built(fusion_type, part_a, part_b, origin_pick, origin_snap)
    joint = _new_joint_object(doc, fusion_type, "AsBuiltJoint")
    set_as_built(joint, fusion_type, part_a, part_b, origin_pick, origin_snap)
    ensure_ground(joint)
    return joint


def _check_as_built(fusion_type, part_a, part_b, origin_pick, origin_snap):
    if part_a is None or part_b is None:
        raise JointError("Pick two components.")
    if part_a is part_b:
        raise JointError("Both picks are on %s. Pick two different components." % part_a.Label)
    if fusion_type not in core.JOINT_TYPES:
        raise JointError("Unknown joint type %r." % (fusion_type,))
    if fusion_type != "rigid" and (origin_pick is None or origin_snap is None):
        raise JointError("Pick the joint's position (a snap point) on one of the components.")


def _snap_frame(pick, snap):
    """The global frame of a stored snap (kind + the element it sits on) on today's geometry."""
    if snap.get("frame") is not None:
        return App.Placement(snap["frame"])
    candidates = snap_candidates(pick)
    for c in candidates:
        if c["kind"] == snap.get("kind") and c.get("at", "") == snap.get("at", ""):
            return App.Placement(c["frame"])
    if candidates:
        return App.Placement(candidates[0]["frame"])
    raise JointError("The joint's position is gone from %s. Pick it again." % pick.part.Label)


def set_as_built(joint, fusion_type, part_a, part_b, origin_pick=None, origin_snap=None):
    """(Re)define an as-built joint in place (Edit keeps the same joint, its place in the
    timeline and its limits): the type, the two components where they stand now and the
    position of its axis."""
    _check_as_built(fusion_type, part_a, part_b, origin_pick, origin_snap)
    old = getattr(joint, PROPS["fusion"], "")
    setattr(joint, PROPS["fusion"], fusion_type)
    joint.JointType = core.FREECAD_TYPE[fusion_type]
    if old and old != fusion_type and joint.Label.startswith(core.TITLES.get(old, "?") + " "):
        joint.Label = label_for(joint.Document, fusion_type)
    # where they stand: the two joint origins are the same frame, nothing mates or flips
    _set_json(joint, PROPS["offset"], dict(default_offset(), mate=False))
    _set_json(joint, PROPS["axes"], default_axes(fusion_type))
    # the joint origin: the picked snap (global), else component 2's own origin
    if origin_pick is not None and origin_snap is not None:
        frame = _snap_frame(origin_pick, origin_snap)
    else:
        frame = App.Placement(part_b.Placement)
    refs = []
    for index, part in ((0, part_a), (1, part_b)):
        key = PROPS["snap1" if index == 0 else "snap2"]
        if origin_pick is not None and origin_pick.part is part:
            _set_json(joint, key, snap_record(origin_pick, origin_snap))  # follows geometry
            ref = origin_pick.ref
        else:
            _set_json(joint, key, as_built_record(frame))  # stays where it is now
            ref = any_element_ref(part)
        if fusion_type in ("planar", "pinslot"):
            ref = _planar_face_of(part, ref)
        refs.append(ref)
    if fusion_type in ("planar", "pinslot"):
        joint.Distance = 0.0
    joint.Reference1, joint.Reference2 = refs
    refresh_placements(joint)
    sync_helper(joint)
    return joint


def _planar_face_of(part, ref):
    obj = shape_owner(ref)
    if obj is None:
        return ref
    pick = Pick(part, obj, element_name(ref[1][0]))
    try:
        return planar_face_ref(pick)
    except JointError:
        return ref


# -- joint origins ---------------------------------------------------------------------------------
def is_joint_origin(obj):
    try:
        return getattr(obj, TYPE_PROP, "") == "JointOrigin"
    except Exception:
        return False


def joint_origins(doc):
    return sorted((o for o in doc.Objects if is_joint_origin(o)), key=lambda o: o.ID)


def create_joint_origin(doc, pick, snap, offset=None):
    """A joint origin on a component at a snap point (plus offsets / angle / flip): a
    coordinate-system datum in the body (or component) that joints can snap to."""
    if pick is None or snap is None:
        raise JointError("Pick a snap point on a component.")
    owner = pick.obj if pick.obj.TypeId == "PartDesign::Body" else pick.part
    if owner.TypeId == "PartDesign::Body":
        obj = owner.newObject("PartDesign::CoordinateSystem", "JointOrigin")
    else:
        obj = owner.newObject("App::LocalCoordinateSystem", "JointOrigin")
    obj.Label = "Joint Origin %d" % core.label_number(
        [o.Label for o in joint_origins(doc)], "Joint Origin"
    )
    bodies.mark(obj, "JointOrigin")
    bodies.add_prop(obj, "App::PropertyString", PROPS["snap1"], "SciForge")
    bodies.add_prop(obj, "App::PropertyString", PROPS["offset"], "SciForge")
    # the object it sits on, by name: a link from inside the body to the body is a cycle
    bodies.add_prop(obj, "App::PropertyString", "SciForgeOn", "SciForge")
    bodies.add_prop(obj, "App::PropertyString", "SciForgeElement", "SciForge")
    if "MapMode" in obj.PropertiesList:
        obj.MapMode = "Deactivated"
    obj.SciForgeOn = pick.obj.Name
    obj.SciForgeElement = pick.element
    _set_json(obj, PROPS["snap1"], snap_record(pick, snap))
    _set_json(obj, PROPS["offset"], dict(default_offset(), **(offset or {})))
    place_joint_origin(obj)
    return obj


def joint_origin_owner(obj):
    name = getattr(obj, "SciForgeOn", "") or ""
    return obj.Document.getObject(name) if name else None


def place_joint_origin(obj):
    """Put a joint origin at its snap (on the current geometry) with its offsets."""
    on = joint_origin_owner(obj)
    if on is None:
        return
    part = part_of(on) or on
    ref = reference(part, on, getattr(obj, "SciForgeElement", ""))
    local = local_placement(ref, _json(obj, PROPS["snap1"]))  # relative to `on`
    data = dict(default_offset(), **_json(obj, PROPS["offset"]))
    f = to_frame(local)
    f = core.compose(
        f, core.frame((data["x"], data["y"], data["z"]), core.rot_axis_angle(core.Z, data["angle"]))
    )
    if data["flip"]:
        f = (f[0], core.rot_mul(f[1], core.FLIP))
    local = from_frame(f)
    # the datum's Placement is relative to its container: the body itself when it sits in
    # one (`on`), else `on`'s own container, where `on` stands at on.Placement
    parent = obj.getParentGeoFeatureGroup()
    if parent is not on:
        local = on.Placement * local
    if not obj.Placement.isSame(local, 1e-9):
        obj.Placement = local


# -- tidying up ------------------------------------------------------------------------------------
def _dead_ref(ref):
    """True when a joint reference lost its part, or the object inside the part whose
    element it names (a body deleted from a component)."""
    try:
        if ref is None or ref[0] is None or ref[0].Document is None:
            return True
        doc = ref[0].Document
        subs = list(ref[1]) if len(ref) > 1 else []
        for name in (subs[0].split(".")[:-1] if subs else []):
            if name and doc.getObject(name) is None:
                return True
        return False
    except Exception:
        return True


def _references(joint, target):
    """True when one of the joint's references is on `target`: the part itself, or a body
    (a nested component) inside the part on the way to the element."""
    for ref in (joint.Reference1, joint.Reference2):
        try:
            if not ref:
                continue
            if ref[0] is target:
                return True
            subs = list(ref[1]) if len(ref) > 1 else []
            if subs and target.Name in subs[0].split(".")[:-1]:
                return True
        except Exception:
            continue
    return False


def remove_joints_of(part):
    """Fusion deletes a component's joints with it: the joints, Pin-Slot helpers and
    rigid-group links on `part` (a part, or a body or component inside one), and its
    ground, go now (called while it is being deleted, so it is the same undo step). A rigid
    group left with one member goes too. Returns the names removed."""
    doc = part.Document
    doomed = []
    for obj in doc.Objects:
        if obj is part:
            continue
        if (is_joint(obj) or is_helper(obj)) and _references(obj, part):
            doomed.append(obj)
            doomed.extend(h for h in helpers_of(obj) if h not in doomed)
        elif "ObjectToGround" in obj.PropertiesList and obj.ObjectToGround is part:
            doomed.append(obj)
    for group in rigid_groups(doc):
        left = [m for m in group.Members if m is not None and m is not part]
        if len(left) < 2 and any(m is part for m in group.Members):
            doomed.append(group)
            doomed.extend(h for h in helpers_of(group) if h not in doomed)
    names = []
    for obj in doomed:
        try:
            name = obj.Name
            if doc.getObject(name) is not None:
                doc.removeObject(name)
                names.append(name)
        except Exception as exc:
            warn("joints: could not remove %s: %s" % (getattr(obj, "Label", "?"), exc))
    if names:
        log("joints removed with %s: %s" % (part.Label, ", ".join(names)))
    return names


def _rerooted(ref):
    """`ref` pointed at the part that now holds its body (the body went into or out of a
    component), or None when it is still right (or broken: tidy's business)."""
    try:
        part, subs = ref[0], list(ref[1])
        if part is None or not subs:
            return None
        doc = part.Document
        owner = part
        for name in subs[0].split(".")[:-1]:
            obj = doc.getObject(name)
            if obj is None:
                return None
            if obj.isDerivedFrom("PartDesign::Feature"):
                continue
            owner = obj
        new_part = part_of(owner)
        if new_part is None:
            return None
        prefix = _path(new_part, owner) if owner is not new_part else ""
        new_subs = [prefix + s.split(".")[-1] for s in subs]
        if new_part is part and new_subs == subs:
            return None
        return [new_part, new_subs]
    except Exception:
        return None


def reroot(doc):
    """After bodies moved into or out of components (Create Components from Bodies, a drag
    in the browser): the joints, grounds and rigid groups follow them to the part that now
    moves them. A joint whose two sides end up in one component is switched off (Fusion
    joints components, not bodies of one component). Returns the joints changed."""
    changed = []
    for obj in doc.Objects:
        if not (is_joint(obj) or is_helper(obj)):
            continue
        for prop in ("Reference1", "Reference2"):
            ref = getattr(obj, prop, None)
            new = _rerooted(ref) if ref else None
            if new is not None:
                setattr(obj, prop, new)
                if obj not in changed:
                    changed.append(obj)
        p1, p2 = part1(obj), part2(obj)
        if obj in changed and p1 is not None and p1 is p2 and not obj.Suppressed:
            obj.Suppressed = True
            warn("%s joins two bodies of %s now: it is switched off" % (obj.Label, p1.Label))
    for g in grounds(doc):
        target = g.ObjectToGround
        if target is not None and not is_part(target):
            new = part_of(target)
            if new is not None and new is not target:
                g.ObjectToGround = new
    for group in rigid_groups(doc):
        members, seen = [], set()
        for m in group.Members:
            m = (part_of(m) or m) if m is not None else None
            if m is not None and m.Name not in seen:
                seen.add(m.Name)
                members.append(m)
        if [m.Name for m in members] != [m.Name for m in group.Members if m is not None]:
            group.Members = members
    if changed:
        log("joints follow their bodies: %s" % ", ".join(j.Label for j in changed))
    return changed


class _DeleteWatch:
    """Removes a part's joints while the part itself is being deleted (same undo step as
    the delete, whoever deletes it: the browser, the timeline, a component's Delete, a
    script), and points joints at the component a jointed body was moved into. Not while
    FreeCAD undoes or redoes: the joints come and go with the step."""

    def __init__(self):
        self.closing = set()  # documents being closed: their objects are torn down

    def slotCreatedDocument(self, doc):
        self.closing.discard(doc.Name)

    def slotDeletedDocument(self, doc):
        self.closing.add(doc.Name)

    def slotChangedObject(self, obj, prop):
        try:
            if prop != "Group" or obj.TypeId != "App::Part":
                return
            doc = obj.Document
            if doc is None or App.isRestoring() or getattr(doc, "Transacting", False):
                return
            if doc.Name in self.closing:
                return
            if assembly(doc) is not None:
                reroot(doc)
        except Exception as exc:
            warn("joints: %s" % exc)

    def slotDeletedObject(self, obj):
        try:
            doc = obj.Document
            if doc is None or App.isRestoring() or getattr(doc, "Transacting", False):
                return
            if doc.Name in self.closing or assembly(doc) is None:
                return
            if is_part(obj) or obj.TypeId in ("PartDesign::Body", "App::Part"):
                remove_joints_of(obj)
            elif is_joint(obj) or is_rigid_group(obj):
                # a Pin-Slot's slot joint and a rigid group's links go with it (the timeline
                # and the browser delete only the step itself)
                for helper in helpers_of(obj):
                    if doc.getObject(helper.Name) is not None:
                        doc.removeObject(helper.Name)
        except Exception as exc:
            warn("joints: %s" % exc)


_DELETE_WATCH = {"observer": None}


def install_delete_watch():
    if _DELETE_WATCH["observer"] is None:
        _DELETE_WATCH["observer"] = _DeleteWatch()
        App.addDocumentObserver(_DELETE_WATCH["observer"])


def tidy(doc):
    """Remove what lost its purpose: joints whose component is gone (Fusion deletes a
    component's joints with it), helpers whose joint or rigid group is gone, grounds of a
    gone part, rigid groups down to one member. Returns the names removed."""
    removed = []
    for obj in list(doc.Objects):
        try:
            if obj.Document is None:
                continue
            if is_helper(obj) and getattr(obj, PROPS["parent"], None) is None:
                removed.append(obj.Name)
            elif is_joint(obj) or is_helper(obj):
                if _dead_ref(obj.Reference1) or _dead_ref(obj.Reference2):
                    removed.append(obj.Name)
            elif "ObjectToGround" in obj.PropertiesList and obj.ObjectToGround is None:
                removed.append(obj.Name)
            elif is_rigid_group(obj):
                members = [m for m in obj.Members if m is not None]
                if len(members) < 2:
                    removed.append(obj.Name)
                elif len(members) != len(obj.Members):
                    obj.Members = members
                    rebuild_rigid_group(obj)
        except Exception as exc:
            warn("joints tidy: %s" % exc)
    for name in removed:
        if doc.getObject(name) is not None:
            doc.removeObject(name)
    if removed:
        log("joints removed with their components: %s" % ", ".join(removed))
    return removed


def delete_joint(joint):
    """Delete a joint with its helpers; the components stay where they are."""
    doc = joint.Document
    for helper in helpers_of(joint):
        doc.removeObject(helper.Name)
    doc.removeObject(joint.Name)


def describe(joint):
    """One line for the browser's tooltip."""
    p1, p2 = part1(joint), part2(joint)
    kind = core.TITLES.get(fusion_type(joint), "Joint")
    names = " - ".join(p.Label for p in (p1, p2) if p is not None)
    return "%s joint: %s" % (kind, names) if names else kind


try:
    install_delete_watch()
except Exception as _exc:  # never let an import fail the commands
    warn("joints delete watch unavailable: %s" % _exc)
