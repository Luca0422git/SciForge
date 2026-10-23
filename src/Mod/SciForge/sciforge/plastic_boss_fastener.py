# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Boss's fastener (Fusion's Boss > Fastener > Create Component): a simple screw at every
boss point, in a component of its own, made from the boss's settings (no Qt).

The screw's head sits on the head side's seat: the counterbore's floor, the countersink
(flush with the outside), or the outside face for a simple hole. Its shank (the thread
diameter) runs from there towards the thread side and stops 0.5 mm short of the pilot hole's
bottom (Length 0 = that, Auto), or is the Length typed. Head types: Pan (a round head 0.6 d
high), Flat (countersunk, its cone the countersink's angle), Hex (across flats = the
counterbore's diameter - 0.5). The thread is not modelled (Fusion's fastener carries it as a
cosmetic thread). The step (``SciForge::BossFastener``) lives in the fastener component's
body and follows the boss: edit the boss, the screws move with it.

Options (``options["fastener"]``): create (bool), head ("pan" | "flat" | "hex"), length (mm,
0 = auto).
"""

import math

import FreeCAD as App

from . import bodies, curves, warn

FP_TYPE = "PartDesign::FeaturePython"
TYPE = "BossFastener"
HEADS = ("pan", "flat", "hex")
DEFAULTS = {"create": False, "head": "pan", "length": 0.0}


class FastenerError(ValueError):
    """The fastener cannot be made as asked; the message says why."""


def options_of(options):
    out = dict(DEFAULTS)
    out.update(options.get("fastener") or {})
    if out["head"] not in HEADS:
        raise FastenerError("unknown head type %r" % out["head"])
    out["length"] = float(out["length"])
    if out["length"] < 0:
        raise FastenerError("The fastener length cannot be negative (0 = auto).")
    return out


def _side_info(pb, base, frame, settings, label):
    _adds, _cuts, info = pb.side_shapes(base, frame, settings, label)
    return info


def screw_shapes(pb, options, head_frames, head_base, thread_frames, thread_base):
    """One screw solid per point (global). head_* / thread_* are the two sides' frames and
    body shapes (thread_* may be None: the screw then ends at its Length or 2.5 d)."""
    import Part

    f = options_of(options)
    d = float(options["screw"])
    s1 = dict(options["side1"], side=1)
    s2 = dict(options["side2"], side=2)
    solids = []
    for i, frame in enumerate(head_frames):
        info1 = _side_info(pb, head_base, frame, s1, "Side 1")
        tip1, s_out1 = info1["tip"], info1["s_out"]
        hole = s1["hole"]
        if s1["shape"] == "blank":
            raise FastenerError("Side 1 is blank (no hole): there is no screw to place.")
        if hole == "counterbore":
            seat = tip1 + float(s1["major_depth"])
        else:
            seat = s_out1  # the countersink's mouth or the outside face
        # how far the shank reaches from the parting plane into the thread side
        reach = None
        if thread_frames is not None and i < len(thread_frames) and thread_base is not None:
            info2 = _side_info(pb, thread_base, thread_frames[i], s2, "Side 2")
            if s2["shape"] != "blank":
                if s2["extent"] == "through":
                    end = info2["s_out"]
                elif s2["extent"] == "from_top":
                    end = info2["tip"] + float(s2["hole_depth"])
                else:
                    end = info2["s_out"] - float(s2["hole_depth"])
                reach = end - 0.5
        length = f["length"] if f["length"] > 1e-9 else (seat + reach if reach else 2.5 * d)
        if length <= 1e-3:
            raise FastenerError("The fastener has no length: type a Length.")
        up = frame.d  # towards the head side's outside
        down = up * -1.0
        seat_point = frame.at(seat)
        shank = Part.makeCylinder(d / 2.0, length, seat_point, down)
        if f["head"] == "flat":
            angle = float(s1["countersink_angle"]) if hole == "countersink" else 90.0
            r_top = float(s1["major_diameter"]) / 2.0 - 0.1 if hole != "simple" else 1.0 * d
            h = max(0.05, (r_top - d / 2.0) / math.tan(math.radians(angle / 2.0)))
            if length <= h + 1e-3:
                raise FastenerError("The fastener is shorter than its head: make it longer.")
            head = Part.makeCone(d / 2.0, r_top, h, seat_point + down * h, up)
            # a countersunk screw's length is overall: its shank is the length less the head
            shank = Part.makeCylinder(d / 2.0, length - h, seat_point + down * h, down)
            # a flat head sits in the countersink: its top is the seat
            screw = head.fuse(shank)
        else:
            if hole == "counterbore":
                width = float(s1["major_diameter"]) - 0.5
            else:
                width = 2.0 * d
            height = 0.6 * d
            if f["head"] == "pan":
                head = Part.makeCylinder(width / 2.0, height, seat_point, up)
            else:
                head = _hex_prism(frame, seat_point, up, width, height)
            screw = head.fuse(shank)
        try:
            screw = screw.removeSplitter()
        except Exception:
            pass
        solids += list(screw.Solids)
    return solids


def _hex_prism(frame, base_point, up, across_flats, height):
    import Part

    r = across_flats / 2.0 / math.cos(math.radians(30.0))
    pts = []
    for k in range(6):
        a = math.radians(60.0 * k)
        pts.append(base_point + frame.x * (r * math.cos(a)) + frame.y * (r * math.sin(a)))
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    return face.extrude(up * height)


# -- the step ------------------------------------------------------------------------------------
def is_fastener(obj):
    return bodies.alive(obj) and getattr(obj, "SciForgeType", "") == TYPE


class FastenerFeature:
    """The screws of a boss. Saved files store "sciforge.plastic_boss_fastener.
    FastenerFeature": never rename."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        if "Bosses" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkListGlobal", "Bosses", "Fastener", "Boss steps")
        if "BossGroup" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "BossGroup", "Fastener", "The boss it holds")
        bodies.mark(obj, TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            compute(obj)
        except Exception:
            import Part

            obj.Shape = Part.Shape()
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def compute(obj):
    import Part

    from . import plastic_boss as pb

    steps = [s for s in obj.Bosses if pb.is_boss(s)]
    if not steps:
        raise FastenerError("The boss of this fastener is gone.")
    options = pb.check_options(pb.resolved_options(steps[0]))
    refs = pb._refs(steps[0])
    sketch = pb.check_refs(refs)
    points = pb.global_points(refs)
    offset = float(options.get("offset", 0.0))
    head = thread = None
    for step in steps:
        toward = 1 if step.Toward >= 0 else -1
        if pb.side_of(options, toward) == 1:
            head = (step, toward)
        else:
            thread = (step, toward)
    if head is None:
        raise FastenerError("A fastener needs the head side (Side 1) of the boss.")
    # each side's values as its own body's rule gives them
    head_options = pb.check_options(pb.resolved_options(head[0]))
    if thread is not None:
        thread_options = pb.check_options(pb.resolved_options(thread[0]))
        head_options["side2"] = thread_options["side2"]
    options = head_options

    def base_of(step):
        base = step.BaseFeature
        return curves.to_global(base.Shape, base)

    head_frames = pb.frames_for(sketch, points, head[1], offset)
    thread_frames = pb.frames_for(sketch, points, thread[1], offset) if thread else None
    solids = screw_shapes(
        pb,
        options,
        head_frames,
        base_of(head[0]),
        thread_frames,
        base_of(thread[0]) if thread else None,
    )
    body = curves.owner_body(obj)
    shape = Part.makeCompound(solids) if len(solids) > 1 else solids[0]
    if body is not None:
        shape = bodies.to_local(shape, body)
    obj.Shape = shape


def find(doc, group):
    for obj in doc.Objects:
        if is_fastener(obj) and obj.BossGroup == group:
            return obj
    return None


def sync(doc, steps, options):
    """Make, update or remove the fastener of the boss `steps` as options["fastener"] says.
    Returns the fastener step or None."""
    from . import components

    f = options_of(options)
    group = steps[0].BossGroup if steps else ""
    existing = find(doc, group) if group else None
    if not f["create"] or not steps:
        if existing is not None:
            body = bodies.body_of(existing)
            component = components.container_of(body) if body is not None else None
            bodies.remove_body(body) if body is not None else None
            if component is not None:
                try:
                    components.drop_if_empty(component)
                except Exception as exc:
                    warn("fastener component: %s" % exc)
        return None
    if existing is None:
        component = components.new_component(doc, "Fastener")
        body = components.new_body_in(doc, component, "Screw")
        existing = body.newObject(FP_TYPE, "Fastener")
        FastenerFeature(existing)
        body.Tip = existing
        existing.BossGroup = group
        if App.GuiUp:
            try:
                from .plastic_boss_ui import ViewProviderFastener

                ViewProviderFastener(existing.ViewObject)
            except Exception as exc:
                warn("fastener view provider: %s" % exc)
    existing.Bosses = list(steps)
    existing.touch()
    return existing
