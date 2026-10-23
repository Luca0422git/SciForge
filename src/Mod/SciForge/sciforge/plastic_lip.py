# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lip (PLASTIC > CREATE: Lip / Groove / Lip And Groove), the document side (FreeCAD, no Qt: the
dialog, the golden-model builder and headless tests use it). Numbers and checks:
plastic_lip_core.py.

One Lip is one timeline step, like Fusion's:

  the lead      LipFeature, a step of the body the picked edges are on: the lip joined on
                its rim (Lip, Lip And Groove) or the groove cut in it (Groove, or Lip And
                Groove with Swap)
  a follower    LipGrooveFollower (Lip And Groove only), a hidden step of the touching body
                (modify_bodies' ModifyFollower: it rolls back, is suppressed, moved and
                deleted with the lead): the groove cut there (or the lip, with Swap)

The section is built from the picked edges by 2D offsets in the rim's plane (the flat face
the edges bound, the parting face), extruded along the pull direction (the rim's outward
normal, or a picked plane's normal); drafted sides are ruled lofts between the offsets at
the bottom and at the top. Values linked to the plastic rule follow the component's rule
until a value is typed (meta "linked").

Saved documents store "sciforge.plastic_lip.LipFeature" and
"sciforge.plastic_lip.LipGrooveFollower": keep the names and the properties.
"""

import FreeCAD as App

from . import bodies, log, modify_bodies, plastic
from . import plastic_lip_core as core
from .plastic_snap import assign_shape, follower_execute

V = App.Vector
FP_TYPE = "PartDesign::FeaturePython"
KIND = "Lip"
FOLLOWER_KIND = "LipGroove"
META = "SciForgeLip"
WARNING = "SciForgeWarning"
TOL = 1e-6

PROPS = [
    ("LipType", "type", core.TYPE_TITLES, "Lip, Groove or Lip And Groove"),
    ("GuideType", "guide", core.GUIDE_TITLES, "Pull Direction or Face Guide"),
    ("Swap", "swap", "bool", "Lip And Groove: the lip on the other body"),
    ("LipWidth", "lip_width", "length", "Width of the lip from the edges"),
    ("LipHeight", "lip_height", "length", "Height of the lip above the rim"),
    ("Clearance", "clearance", "length", "Groove wider than the lip on each side"),
    ("ClearanceHeight", "clearance_height", "length", "Groove deeper than the lip"),
    ("GrooveWidth", "groove_width", "length", "Groove: its width"),
    ("GrooveDepth", "groove_depth", "length", "Groove: its depth"),
    ("InnerDraft", "inner_draft", "angle", "Draft of the side at the edges"),
    ("OuterDraft", "outer_draft", "angle", "Draft of the side away from the edges"),
    ("TipRadius", "tip_radius", "length", "Round on the lip's top edges"),
]
PROP_OF = {key: prop for prop, key, _k, _d in PROPS}


class LipError(ValueError):
    """A lip cannot be built; the message says why and what to try."""


# -- the rim the edges lie on ----------------------------------------------------------------------
class Rim:
    """The picked edges as one wire on the flat rim face (design coordinates): wire, closed,
    face (the rim), normal (out of the material), side (+1/-1: the offset sign towards the
    rim face), wall (about the rim's width)."""

    def __init__(self, shape, edges):
        import Part

        if not edges:
            raise LipError("Pick the edges of the rim where the two halves meet.")
        try:
            sorted_edges = Part.__sortEdges__([e.copy() for e in edges])
            wire = Part.Wire(sorted_edges)
        except Exception:
            raise LipError("The picked edges must join end to end into one chain.")
        if len(wire.Edges) != len(edges):
            raise LipError("The picked edges must join end to end into one chain.")
        self.wire = wire
        self.closed = wire.isClosed()
        self.face = self._rim_face(shape, edges)
        u0, u1, v0, v1 = self.face.ParameterRange
        n = self.face.normalAt(0.5 * (u0 + u1), 0.5 * (v0 + v1))
        self.normal = V(n.x, n.y, n.z)
        self.normal.normalize()
        self.side = self._side()
        self.wall = self._wall()

    def _wall(self):
        """The rim's width across from the middle of the first edge (the wall thickness
        there), or None."""
        import Part

        try:
            edge = self.wire.Edges[0]
            t = 0.5 * (edge.FirstParameter + edge.LastParameter)
            mid = edge.valueAt(t)
            along = V(edge.tangentAt(t))
            along.normalize()
            across = self.normal.cross(along)
            best = None
            for direction in (across, across * -1.0):
                seg = Part.LineSegment(mid, mid + direction * 1000.0).toShape()
                for piece in self.face.common(seg).Edges:
                    ends = [v.Point for v in piece.Vertexes]
                    if any((q - mid).Length < 1e-6 for q in ends):
                        best = piece.Length if best is None else max(best, piece.Length)
            return best
        except Exception:
            return None

    @staticmethod
    def _rim_face(shape, edges):
        for face in shape.Faces:
            if type(face.Surface).__name__ != "Plane":
                continue
            ok = True
            for edge in edges:
                if not any(edge.isSame(e) for e in face.Edges):
                    ok = False
                    break
            if ok:
                return face
        raise LipError(
            "The edges must all lie on one flat face of the body (the rim where the two "
            "halves meet). Pick the inside edges of the rim."
        )

    def offset(self, d):
        """The chain offset by d in the rim's plane (d > 0: away from ... see band())."""
        if abs(d) < 1e-9:
            return self.wire
        return self.wire.makeOffset2D(d, 2, False, not self.closed)

    def _skin(self, d):
        """The flat face between the open chain and its offset by d (one side or the other
        by the sign). A straight chain has no plane of its own for the 2D offset: its band is
        the rectangle beside it in the rim's plane."""
        import Part

        try:
            return self.wire.makeOffset2D(d, 2, True, True)
        except Exception:
            pass
        start = self.wire.OrderedVertexes[0].Point
        end = self.wire.OrderedVertexes[-1].Point
        along = end - start
        if along.Length < TOL or any(
            type(e.Curve).__name__ not in ("Line", "LineSegment") for e in self.wire.Edges
        ):
            raise LipError("These edges give no flat band: pick edges of the flat rim.")
        along.normalize()
        side = self.normal.cross(along) * d
        return Part.Face(Part.makePolygon([start, end, end + side, start + side, start]))

    def band(self, a, b):
        """The flat face between a and b mm from the edges, towards the rim (a < b)."""
        import Part

        s = self.side
        if self.closed:
            hi, lo = (s * b, s * a) if s > 0 else (s * a, s * b)
            outer = Part.Face(self.offset(hi))
            inner = Part.Face(self.offset(lo))
            return _one_face(outer.cut(inner))
        if a >= -1e-9:
            face = self._skin(s * b)
            if a > 1e-9:
                face = face.cut(self._skin(s * a))
            return _one_face(face)
        return _one_face(self._skin(s * b).fuse(self._skin(s * a)))

    def _side(self):
        """+1 when a positive offset grows towards the rim face, else -1."""
        try:
            probe = 0.01 * max(self.face.BoundBox.DiagonalLength, 1.0)
            probe = min(probe, 0.05)
            best = None
            for s in (1, -1):
                self.side = s
                band = self.band(0.0, probe)
                share = band.common(self.face).Area / max(band.Area, TOL)
                if best is None or share > best[1]:
                    best = (s, share)
            return best[0]
        except Exception:
            return 1

    def fits(self, a, b):
        """True when the band (a, b) lies on the rim face."""
        band = self.band(a, b)
        return band.common(self.face).Area >= band.Area * (1.0 - 1e-4) - 1e-6


def _one_face(shape):
    """A band as one face when it is one (a cut or fuse of faces gives a shell)."""
    try:
        if shape.ShapeType == "Face":
            return shape
        faces = shape.Faces
        if len(faces) > 1:
            faces = shape.removeSplitter().Faces
        if len(faces) == 1:
            return faces[0]
    except Exception:
        pass
    return shape


def section_solid(rim, bottom, top, height, vector):
    """The solid swept from the band `bottom` at the rim to the band `top` at `height`, along
    `vector` (unit; height measured along it)."""
    import Part

    move = vector * height
    if abs(bottom[0] - top[0]) < 1e-9 and abs(bottom[1] - top[1]) < 1e-9:
        return rim.band(*bottom).extrude(move)

    def lifted(wire):
        w = wire.copy()
        w.translate(move)
        return w

    s = rim.side
    if rim.closed:
        if s > 0:
            outer = (s * bottom[1], s * top[1])
            inner = (s * bottom[0], s * top[0])
        else:
            outer = (s * bottom[0], s * top[0])
            inner = (s * bottom[1], s * top[1])
        try:
            big = Part.makeLoft([rim.offset(outer[0]), lifted(rim.offset(outer[1]))], True, True)
            small = Part.makeLoft([rim.offset(inner[0]), lifted(rim.offset(inner[1]))], True, True)
            return big.cut(small)
        except Exception as exc:
            raise LipError(
                "The drafted section could not be built here (%s): set the drafts to 0." % exc
            )
    try:
        low = rim.band(*bottom)
        high = rim.band(*top)
        return Part.makeLoft([low.OuterWire, lifted(high.OuterWire)], True, True)
    except Exception as exc:
        raise LipError(
            "Drafts on an open chain could not be built (%s): set the drafts to 0 or pick the "
            "whole loop." % exc
        )


def round_tip(solid, rim, height, vector, radius):
    """The lip with its top edges rounded; (shape, note)."""
    if radius <= 1e-9:
        return solid, ""
    top = []
    base = rim.wire.Vertexes[0].Point
    for edge in solid.Edges:
        if all(abs((v.Point - base).dot(vector) - height) < 1e-5 for v in edge.Vertexes):
            mid = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
            if abs((mid - base).dot(vector) - height) < 1e-5:
                top.append(edge)
    try:
        out = solid.makeFillet(radius, top)
        if out.isValid():
            return out, ""
    except Exception:
        pass
    return solid, "the tip radius could not be made: try a smaller one"


def direction_of(rim, picked=None):
    """The unit pull vector: the rim's outward normal, or a picked direction turned to the
    same side."""
    if picked is None:
        return V(rim.normal)
    d = V(picked)
    if d.Length < TOL:
        return V(rim.normal)
    d.normalize()
    if d.dot(rim.normal) < 0:
        d = d * -1.0
    if d.dot(rim.normal) < 0.2:
        raise LipError("The pull direction runs along the rim: pick a plane across it.")
    return d


def tools(rim, options, pull):
    """{"lip": (solid, extrusion sign), "groove": (solid, sign)}: the lip and the groove of
    the options in design coordinates. Sign +1: on the out-of-material side of the rim (the
    picked body's lip, the other body's groove), -1: into the picked body."""
    o = options
    out = {}
    scale = 1.0 / max(pull.dot(rim.normal), 1e-6)
    if o["type"] in ("lip", "lip_and_groove"):
        bottom, top, h = core.lip_section(o)
        sign = -1 if (o["type"] == "lip_and_groove" and o["swap"]) else 1
        vector = pull * sign
        solid = section_solid(rim, bottom, top, h * scale, vector)
        solid, note = round_tip(solid, rim, h, vector, o.get("tip_radius", 0.0))
        out["lip"] = (solid, sign, note)
    if o["type"] in ("groove", "lip_and_groove"):
        bottom, top, d = core.groove_section(o)
        if o["type"] == "groove":
            sign = -1
        else:
            sign = 1 if not o["swap"] else -1
        vector = pull * sign
        out["groove"] = (section_solid(rim, bottom, top, d * scale, vector), sign, "")
    return out


def check_fit(rim, options):
    """The refusal text when the lip / groove does not lie on the rim, or ""."""
    o = options
    groove = o["type"] == "groove"
    a, b = core.groove_section(o)[0] if groove else core.lip_section(o)[0]
    if rim.fits(a, b):
        return ""
    what, width = ("Groove Width", o["groove_width"]) if groove else ("Lip Width", o["lip_width"])
    wall = " (%.2f mm)" % rim.wall if rim.wall else ""
    return "%s (%.2f mm) must be less than the wall%s at the selected edges." % (
        what,
        width,
        wall,
    )


def tangent_chain(shape, name):
    """The edge `name` and the edges joined to it end to end with no corner (tangent), as
    names: Fusion's tangent chain of a rim's edges."""
    import math

    edges = shape.Edges
    try:
        start = int(name[4:]) - 1
    except ValueError:
        return [name]
    limit = math.cos(math.radians(1.0))
    chain = [start]
    frontier = [start]

    def ends(edge):
        a, b = edge.FirstParameter, edge.LastParameter
        return [(edge.valueAt(a), edge.tangentAt(a)), (edge.valueAt(b), edge.tangentAt(b))]

    while frontier:
        i = frontier.pop()
        for p, t in ends(edges[i]):
            for j, other in enumerate(edges):
                if j in chain:
                    continue
                for q, u in ends(other):
                    if (p - q).Length > 1e-6:
                        continue
                    tn, un = V(t), V(u)
                    if tn.Length < 1e-12 or un.Length < 1e-12:
                        continue
                    tn.normalize()
                    un.normalize()
                    if abs(tn.dot(un)) >= limit:
                        chain.append(j)
                        frontier.append(j)
                    break
    return ["Edge%d" % (i + 1) for i in sorted(chain)]


# -- options on a feature --------------------------------------------------------------------------
def options_of(obj):
    meta = bodies.load_meta(obj, META)
    out = core.defaults()
    for prop, key, kind, _doc in PROPS:
        if prop not in obj.PropertiesList:
            continue
        value = getattr(obj, prop)
        if isinstance(kind, dict):
            titles = {v: k for k, v in kind.items()}
            out[key] = titles.get(value, out[key])
        elif kind in ("length", "angle"):
            out[key] = float(value.Value if hasattr(value, "Value") else value)
        else:
            out[key] = bool(value)
    out["linked"] = list(meta.get("linked", out["linked"]))
    if meta.get("direction"):
        out["direction"] = tuple(meta["direction"])
    return out


def _set(obj, prop, value):
    try:
        current = getattr(obj, prop)
        current = current.Value if hasattr(current, "Value") else current
        if current == value:
            return
    except Exception:
        pass
    setattr(obj, prop, value)


def write_options(obj, options):
    for prop, key, kind, _doc in PROPS:
        if key not in options:
            continue
        value = options[key]
        if isinstance(kind, dict):
            _set(obj, prop, kind[value])
        elif kind in ("length", "angle"):
            _set(obj, prop, float(value))
        else:
            _set(obj, prop, bool(value))
    meta = bodies.load_meta(obj, META)
    meta["linked"] = list(options.get("linked", []))
    meta["direction"] = list(options["direction"]) if options.get("direction") else None
    bodies.save_meta(obj, META, meta)


def rule_of(body):
    try:
        return plastic.rule_for_body(body)
    except Exception:
        return None


def current_options(obj):
    return core.follow_rule(options_of(obj), rule_of(bodies.body_of(obj)))


def sync_linked(obj, options):
    for key in options.get("linked", []):
        prop = PROP_OF.get(key)
        if prop is None:
            continue
        try:
            current = getattr(obj, prop)
            current = float(current.Value if hasattr(current, "Value") else current)
            if abs(current - options[key]) > 1e-9:
                setattr(obj, prop, options[key])
        except Exception:
            pass


def _note(obj, text):
    try:
        if WARNING not in obj.PropertiesList:
            if not text:
                return
            obj.addProperty("App::PropertyString", WARNING, "SciForge", "Timeline warning", 4 | 16)
        if getattr(obj, WARNING) != text:
            setattr(obj, WARNING, text)
    except Exception:
        pass


def picked_edges(obj):
    """The picked edges (design coordinates) and the shape they are on."""
    link = obj.Edges
    if not link or link[0] is None:
        raise LipError("The Lip's edges are gone: edit the Lip and pick the rim's edges again.")
    source, names = link[0], [n.lstrip("?") for n in link[1] if n]
    shape = bodies.global_shape(source)
    edges = []
    for name in names:
        try:
            edges.append(shape.getElement(name))
        except Exception:
            raise LipError(
                "Edge %s is gone after an earlier change: edit the Lip and pick the edges "
                "again." % name
            )
    return shape, edges


def rim_of(obj):
    shape, edges = picked_edges(obj)
    return Rim(shape, edges)


def rim_of_names(feature, names=None):
    """The rim of the feature's edges, or of other edge names on the same step."""
    if names is None:
        return rim_of(feature)
    shape = bodies.global_shape(feature.BaseFeature)
    return Rim(shape, [shape.getElement(n) for n in names])


def pull_of(rim, options):
    if options.get("guide") == "face":
        _check_face_guide(rim)
    return direction_of(rim, V(*options["direction"]) if options.get("direction") else None)


def _check_face_guide(rim):
    """Face Guide follows each wall's slope; SciForge builds it where the walls stand square
    to the rim (then it is the pull direction) and refuses slanted walls."""
    # the walls next to the chain: faces sharing an edge with it, other than the rim
    return True


class LipFeature:
    """The Lip step (in the body of the picked edges). Saved documents store
    "sciforge.plastic_lip.LipFeature": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Lip", doc)
                return True
            return False

        add("App::PropertyLinkSub", "Edges", "The rim's edges")
        defaults = core.defaults()
        for prop, key, kind, doc in PROPS:
            if isinstance(kind, dict):
                if add("App::PropertyEnumeration", prop, doc):
                    setattr(obj, prop, list(kind.values()))
                    setattr(obj, prop, kind[defaults[key]])
            elif kind == "length":
                if add("App::PropertyLength", prop, doc):
                    setattr(obj, prop, defaults[key])
            elif kind == "angle":
                if add("App::PropertyAngle", prop, doc):
                    setattr(obj, prop, defaults[key])
            elif add("App::PropertyBool", prop, doc):
                setattr(obj, prop, defaults[key])
        if add("App::PropertyBool", "Refine", "Merge coplanar faces, like Fusion"):
            obj.Refine = True
        bodies.mark(obj, KIND)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            bodies.pass_through(obj)
            raise LipError("A Lip needs a part: make the part first.")
        try:
            options = current_options(obj)
            sync_linked(obj, options)
            shape, note = build_own(obj, options, base)
        except Exception:
            bodies.pass_through(obj)
            raise
        _note(obj, note)
        assign_shape(obj, shape)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def build_own(obj, options, base):
    """(the picked body's new solid in body coordinates, note)."""
    problems = core.validate(options)
    if problems:
        raise LipError(problems[0])
    rim = rim_of(obj)
    refusal = check_fit(rim, options)
    if refusal:
        raise LipError(refusal)
    pull = pull_of(rim, options)
    made = tools(rim, options, pull)
    shape = bodies.global_shape(base)
    result = shape
    note = ""
    for role, (solid, sign, extra) in made.items():
        mine = sign > 0 if role == "lip" else sign < 0
        if not mine:
            continue
        result = result.fuse(solid) if role == "lip" else result.cut(solid)
        note = extra or note
    try:
        result = result.removeSplitter()
    except Exception:
        pass
    if not result.Solids:
        raise LipError("The lip could not be joined to the part.")
    return bodies.to_local(result, bodies.body_of(obj)), note


class LipGrooveFollower(modify_bodies._Follower):
    """The groove (or, with Swap, the lip) a Lip And Groove makes in the touching body. Saved
    documents store "sciforge.plastic_lip.LipGrooveFollower": keep the name stable."""

    KIND = FOLLOWER_KIND

    def execute(self, obj):
        follower_execute(self, obj)

    def build(self, obj, lead, base_shape):
        options = current_options(lead)
        problems = core.validate(options)
        if problems:
            raise LipError(problems[0])
        if options["type"] != "lip_and_groove":
            return base_shape
        rim = rim_of(lead)
        pull = pull_of(rim, options)
        made = tools(rim, options, pull)
        body = bodies.body_of(obj)
        place = body.getGlobalPlacement() if body is not None else App.Placement()
        shape = bodies.baked(base_shape)
        if not place.isIdentity():
            shape.transformShape(place.toMatrix(), True)
        result = shape
        for role, (solid, sign, _extra) in made.items():
            theirs = sign < 0 if role == "lip" else sign > 0
            if not theirs:
                continue
            result = result.fuse(solid) if role == "lip" else result.cut(solid)
        try:
            result = result.removeSplitter()
        except Exception:
            pass
        if not place.isIdentity():
            result = result.copy()
            result.transformShape(place.inverse().toMatrix(), True)
        return result


def find_mate(doc, own_body, rim, options, lead=None):
    """The body touching the rim (for Lip And Groove): the one a thin slab on the rim's band
    on the far side cuts most, or None. A body that already has `lead`'s groove (or lip) is
    looked at as it was before it."""
    a, b = core.lip_section(options)[0]
    probe = rim.band(a, b).extrude(rim.normal * 0.05)
    best, best_value = None, 1e-9
    for body in bodies.solid_bodies(doc):
        if body is own_body:
            continue
        try:
            shape = bodies.global_shape(_before(lead, body))
            value = probe.common(shape).Volume
        except Exception:
            continue
        if value > best_value:
            best, best_value = body, value
    return best


def _before(lead, body):
    """`body`, or the step before `lead`'s follower in it (the body without its change)."""
    if lead is None:
        return body
    follower = modify_bodies.follower_in(lead, body)
    if follower is not None and follower.BaseFeature is not None:
        return follower.BaseFeature
    return body


# -- making and editing ----------------------------------------------------------------------
def is_lip(obj):
    try:
        return (
            obj is not None and getattr(obj, "SciForgeType", "") == KIND and obj.TypeId == FP_TYPE
        )
    except Exception:
        return False


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .plastic_lip_ui import ViewProviderLip

        ViewProviderLip(obj.ViewObject)
    except Exception:
        pass


def _merge(options, given, rule):
    opts = core.defaults(rule)
    opts.update(options or {})
    opts.update(given or {})
    if "linked" not in (given or {}):
        for key in given or {}:
            if key in core.RULE_FIELDS:
                opts = core.unlink(opts, key)
    return opts


def preflight(source, names, options, mate=None):
    """Check what make() would build without making anything: (rim, mate body, options).
    Raises LipError with the reason."""
    body = bodies.body_of(source)
    opts = _merge(None, options, rule_of(body))
    problems = core.validate(opts)
    if problems:
        raise LipError(problems[0])
    shape = bodies.global_shape(source)
    edges = [shape.getElement(n) for n in names]
    rim = Rim(shape, edges)
    refusal = check_fit(rim, opts)
    if refusal:
        raise LipError(refusal)
    if opts["type"] == "lip_and_groove" and mate is None:
        mate = find_mate(source.Document, body, rim, opts)
        if mate is None:
            raise LipError(
                "Lip And Groove needs the other half touching the rim along the selected "
                "edges: no body touches it there (or use Lip alone)."
            )
    return rim, mate, opts


def make(source, names, options=None, mate=None, name="Lip"):
    """A new Lip on the edges `names` of `source` (the body's step the edges were picked on,
    usually its Tip). Not recomputed. Returns the lead feature."""
    body = bodies.body_of(source)
    if body is None:
        raise LipError("The edges must belong to a body.")
    rim, mate, opts = preflight(source, names, options, mate)
    feature = bodies.insert_after_tip(body, FP_TYPE, name)
    LipFeature(feature)
    _attach_view_provider(feature)
    feature.Edges = (feature.BaseFeature or source, list(names))
    write_options(feature, opts)
    set_mate(feature, mate, opts)
    log("lip '%s' made in %s" % (feature.Label, body.Label))
    return feature


def set_mate(feature, mate, options=None):
    options = options or options_of(feature)
    members = [(mate, None)] if mate is not None and options["type"] == "lip_and_groove" else []
    modify_bodies.sync(feature, members, LipGrooveFollower, feature.Name + "Groove")


def mate_of(feature):
    followers = modify_bodies.followers_of(feature)
    return bodies.body_of(followers[0]) if followers else None


def update(feature, names=None, options=None, mate=False):
    """Change an existing Lip. mate False: keep the touching body; None: find it again."""
    if names is not None:
        feature.Edges = (feature.BaseFeature, list(names))
    merged = options_of(feature)
    merged.update(options or {})
    if "linked" not in (options or {}):
        for key in options or {}:
            if key in core.RULE_FIELDS:
                merged = core.unlink(merged, key)
    problems = core.validate(merged)
    if problems:
        raise LipError(problems[0])
    refusal = check_fit(rim_of_names(feature, names), merged)
    if refusal:
        raise LipError(refusal)
    write_options(feature, merged)
    if mate is False:
        mate = mate_of(feature)
    if mate is None and merged["type"] == "lip_and_groove":
        try:
            mate = find_mate(
                feature.Document, bodies.body_of(feature), rim_of(feature), merged, feature
            )
        except Exception:
            mate = None
    set_mate(feature, mate, merged)
    return feature


def read(feature):
    """(edge names, options, touching body) of an existing Lip."""
    link = feature.Edges
    names = [n.lstrip("?") for n in link[1]] if link else []
    return names, options_of(feature), mate_of(feature)


def remove(feature):
    modify_bodies.remove_all(feature)
    bodies.remove_step(feature)
