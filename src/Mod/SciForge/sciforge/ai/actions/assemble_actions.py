# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI actions for bodies and components (new, activate), joints (joints.py: the same code
as the Joint dialog: a pick on each component, a snap point on it, align, solve), Ground,
Physical Material (material.py) and Appearance (appearance.py)."""

import FreeCAD as App

from .. import bridge_core
from ..executor import UserError
from . import action


@action("new_component")
def new_component(ctx, args):
    from ... import components

    doc = ctx.need_doc(create=True)
    parent = None
    if args.get("parent"):
        parent = ctx.resolve(args["parent"], "component")
        if not components.is_component(parent):
            raise UserError("%r is not a component." % args["parent"])

    def work():
        part = components.new_component(doc, args.get("label"), parent)
        body = components.new_body_in(doc, part)
        return part, body

    part, body = ctx.change(work)
    components.activate_body(body)
    ctx.host.set_active_body(body)
    return bridge_core.result(
        "Done: new component %r (id %r) with the body %r; it is the active component: the "
        "next sketches go into it." % (part.Label, part.Name, body.Name)
    )


@action("new_body")
def new_body(ctx, args):
    from ... import bodies, components

    doc = ctx.need_doc(create=True)
    current = ctx.host.find_body(doc)

    def work():
        if current is not None:
            container = components.container_of(current)
            if container is not None:
                return components.new_body_in(doc, container, label=args.get("label"))
        return bodies.new_body(doc, args.get("label"), like=current)

    body = ctx.change(work)
    ctx.host.set_active_body(body)
    return bridge_core.result(
        "Done: new body %r (id %r), the active body now." % (body.Label, body.Name)
    )


@action("activate")
def activate(ctx, args):
    from ... import bodies, components

    obj = ctx.resolve(args["target"])
    if components.is_component(obj):
        components.set_active(obj)
        body = components.preferred_body(obj.Document, obj)
        if body is None:
            body = components.new_body_in(obj.Document, obj)
        ctx.host.set_active_body(body)
        return bridge_core.result(
            "The active component is now %s (body %s)." % (obj.Label, body.Name)
        )
    body = obj if bodies.is_body(obj) else bodies.body_of(obj)
    if body is None:
        raise UserError("%r is not a body, a step in one, or a component." % args["target"])
    components.activate_body(body)
    ctx.host.set_active_body(body)
    return bridge_core.result("The active body is now %s (id %r)." % (body.Label, body.Name))


# -- joints -------------------------------------------------------------------------------------
def _part_and_pick(ctx, side, what):
    from ... import bodies, components, joints
    from ..ops import selectors

    obj = ctx.resolve(side["component"], "component or body")
    part = joints.part_of(obj)
    if part is None:
        raise UserError(
            "%s: %r is not a component or body joints can move." % (what, side["component"])
        )
    if components.is_component(part):
        body = obj if bodies.is_body(obj) else None
        if body is None:
            found = [
                b
                for b in components.bodies_in(obj.Document, part, recursive=True)
                if bodies.has_solid(b)
            ]
            if not found:
                raise UserError("%s: %s has no solid body." % (what, part.Label))
            body = found[0]
    else:
        body = obj if bodies.is_body(obj) else bodies.body_of(obj) or part
    shape, _local = joints.geometry(body)
    element = ""
    if "face" in side or "edge" in side:
        kind = "faces" if "face" in side else "edges"
        names = selectors.select(shape, side["face" if "face" in side else "edge"], kind)
        if len(names) != 1:
            raise UserError(
                "%s: the selector must pick one element of %s (it picked %d)."
                % (what, body.Label, len(names))
            )
        element = names[0]
    elif "vertex" in side:
        probe = App.Vector(*side["vertex"])
        place = body.getGlobalPlacement()
        for i, vertex in enumerate(shape.Vertexes, start=1):
            if (place.multVec(vertex.Point) - probe).Length < 1e-6:
                element = "Vertex%d" % i
        if not element:
            raise UserError("%s: %s has no corner at %s." % (what, body.Label, side["vertex"]))
    else:
        raise UserError(
            "%s: give face, edge or vertex (where on %s the joint sits)." % (what, body.Label)
        )
    point = App.Vector(*side["point"]) if "point" in side else None
    pick = joints.Pick(part, body, element, point)
    snaps = joints.snap_candidates(pick)
    if not snaps:
        raise UserError("%s: no snap point on that element." % what)
    if "snap" in side:
        wanted = [s for s in snaps if s["kind"] == side["snap"]]
        if not wanted:
            raise UserError(
                "%s: that element has no %s snap (it has %s)."
                % (what, side["snap"], ", ".join(sorted({s["kind"] for s in snaps})))
            )
        snap = joints.nearest_snap(wanted, point)
    else:
        snap = joints.nearest_snap(snaps, point)
    return pick, snap


@action("joint")
def joint(ctx, args):
    from ... import joints

    doc = ctx.need_doc()
    pick1, snap1 = _part_and_pick(ctx, args["first"], "first")
    pick2, snap2 = _part_and_pick(ctx, args["second"], "second")
    kind = args.get("type", "rigid")
    offset = {}
    if "offset" in args:
        offset.update(x=args["offset"][0], y=args["offset"][1], z=args["offset"][2])
    if "angle" in args:
        offset["angle"] = args["angle"]
    if "flip" in args:
        offset["flip"] = bool(args["flip"])
    axes = {k: args[k] for k in ("rotate", "slide") if k in args}
    before = {p.Name: App.Placement(p.Placement) for p in (pick1.part, pick2.part)}

    def work():
        try:
            made = joints.create_joint(
                doc, kind, pick1, snap1, pick2, snap2, offset or None, axes or None
            )
            code = joints.align(made, first=True)
        except joints.JointError as exc:
            raise UserError(str(exc))
        if code == 0:
            joints.keep_in_limits(made)
        return made, code

    made, code = ctx.change(work)
    moved = [p for p in (pick1.part, pick2.part) if not p.Placement.isSame(before[p.Name], 1e-9)]
    text = "Done: %s joint between %s and %s. Its id is %r." % (
        kind,
        pick1.part.Label,
        pick2.part.Label,
        made.Name,
    )
    if moved:
        text += " Moved: %s (now at %s)." % (
            ", ".join(p.Label for p in moved),
            ", ".join("[%.6g, %.6g, %.6g]" % tuple(p.Placement.Base) for p in moved),
        )
    problem = joints.solve_message(code)
    if problem:
        text += " " + problem
    return ctx.done(text, doc)


@action("drive_joint")
def drive_joint(ctx, args):
    from ... import joints

    doc = ctx.need_doc()
    obj = ctx.resolve(args["joint"], "joint")
    if not joints.is_joint(obj):
        raise UserError("%r is not a joint." % args["joint"])

    def work():
        try:
            return joints.drive(obj, args.get("angle"), args.get("slide"))
        except joints.JointError as exc:
            raise UserError(str(exc))

    angle, slide = ctx.change(work)
    return ctx.done(
        "Done: %s at angle %.6g degrees, slide %.6g mm." % (obj.Label, angle or 0.0, slide or 0.0),
        doc,
    )


@action("ground")
def ground(ctx, args):
    from ... import joints

    ctx.need_doc()
    obj = ctx.resolve(args["component"], "component or body")
    part = joints.part_of(obj)
    if part is None:
        raise UserError("%r is not a component or body." % args["component"])
    on = args.get("ground", True)

    def work():
        try:
            return joints.ground(part) if on else joints.unground(part)
        except joints.JointError as exc:
            raise UserError(str(exc))

    ctx.change(work)
    return bridge_core.result("%s is %s." % (part.Label, "grounded" if on else "not grounded"))


# -- material and looks ---------------------------------------------------------------------------
def _body(ctx, args):
    if args.get("body"):
        return ctx.body_of(args["body"])
    body = ctx.host.find_body(ctx.need_doc())
    if body is None:
        raise UserError("There is no body.")
    return body


@action("physical_material")
def physical_material(ctx, args):
    from ... import material

    body = _body(ctx, args)
    key = args["material"]
    if material.entry(key) is None:
        keys = [row[0] for row in material.LIBRARY]
        raise UserError(
            "There is no material %r (list_materials lists them: %s)." % (key, ", ".join(keys))
        )

    def work():
        try:
            material.assign(body, key)
        except material.MaterialError as exc:
            raise UserError(str(exc))

    ctx.change(work)
    label, rho = material.effective(body)
    mass = material.mass(body)
    return bridge_core.result(
        "Done: %s is %s%s."
        % (body.Label, label, (", %.6g g" % (mass * 1000.0)) if mass is not None else "")
    )


@action("appearance")
def appearance(ctx, args):
    from ... import appearance as looks
    from ..ops import selectors

    body = _body(ctx, args)
    if "look" in args:
        look = looks.find(args["look"])
        if look is None:
            raise UserError("There is no appearance %r (list_materials lists them)." % args["look"])
    else:
        look = looks.custom(
            args["color"], args.get("shininess", 0.5), args.get("transparency", 0.0)
        )

    def work():
        if "faces" in args:
            tip = body.Tip
            names = selectors.select(tip.Shape, args["faces"], "faces")
            if not names:
                raise UserError("The face selector picked nothing.")
            looks.set_faces(body, tip, names, look)
        else:
            looks.set_body(body, look)
        looks.apply(body)

    ctx.change(work)
    return bridge_core.result(
        "Done: %s%s in %s."
        % (body.Label, " (some faces)" if "faces" in args else "", look["label"])
    )
