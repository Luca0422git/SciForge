# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI actions that read and edit an existing sketch: draw more in it, read it, add
constraints and dimensions (Fusion's forms of Collinear, Concentric and Midpoint, as
sketch_constrain_tools.py makes them), change and delete, and sketch Text (text.py). A
constraint or dimension that fights the sketch, or says what it says already, is taken out
again and the answer names the constraints it conflicts with or repeats, in the words the
sketch tools use (sketch_explain.py; idea 1 of docs/sciforge/dev/cadcraft-lessons.md)."""

import math

import FreeCAD as App

from ... import warn
from ..executor import UserError, json_result
from . import action

POS = {"whole": 0, "start": 1, "end": 2, "center": 3}
POS_NAMES = {0: "whole", 1: "start", 2: "end", 3: "center"}
DIMENSION_TYPES = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")


def _sketch(ctx, ident):
    obj = ctx.resolve(ident, "sketch")
    if obj.TypeId != "Sketcher::SketchObject":
        raise UserError("%r is not a sketch (it is a %s)." % (ident, obj.TypeId.split("::")[-1]))
    return obj


def _local(sketch, point):
    """A design point in the sketch's own x / y."""
    p = sketch.getGlobalPlacement().inverse().multVec(point)
    return [round(p.x, 6), round(p.y, 6)]


def _xy(v):
    return [round(v.x, 6), round(v.y, 6)]


def _geometry_row(sketch, index, geo):
    kind = geo.TypeId.replace("Part::Geom", "")
    row = {"index": index, "type": kind, "construction": bool(sketch.getConstruction(index))}
    try:
        if kind == "LineSegment":
            row.update(
                start=_xy(geo.StartPoint), end=_xy(geo.EndPoint), length=round(geo.length(), 6)
            )
        elif kind == "Circle":
            row.update(center=_xy(geo.Center), radius=round(geo.Radius, 6))
        elif kind == "ArcOfCircle":
            row.update(
                center=_xy(geo.Center),
                radius=round(geo.Radius, 6),
                start=_xy(geo.StartPoint),
                end=_xy(geo.EndPoint),
                start_angle=round(math.degrees(geo.FirstParameter), 6),
                end_angle=round(math.degrees(geo.LastParameter), 6),
            )
        elif kind == "Point":
            row.update(point=[round(geo.X, 6), round(geo.Y, 6)])
        elif kind in ("Ellipse", "ArcOfEllipse"):
            row.update(
                center=_xy(geo.Center),
                major=round(geo.MajorRadius, 6),
                minor=round(geo.MinorRadius, 6),
            )
        elif kind == "BSplineCurve":
            row.update(
                start=_xy(geo.StartPoint),
                end=_xy(geo.EndPoint),
                poles=geo.NbPoles,
                closed=bool(geo.isClosed()),
            )
    except Exception:
        pass
    return row


def _list(value):
    try:
        return list(value)
    except Exception:
        return []


@action("get_sketch")
def get_sketch(ctx, args):
    from ... import extrude

    sketch = _sketch(ctx, args["sketch"])
    doc = sketch.Document
    doc.recompute()
    place = sketch.getGlobalPlacement()
    info = {
        "id": sketch.Name,
        "label": sketch.Label,
        "placement": {
            "origin": [round(v, 6) for v in place.Base],
            "normal": [round(v, 6) for v in place.Rotation.multVec(App.Vector(0, 0, 1))],
            "x_axis": [round(v, 6) for v in place.Rotation.multVec(App.Vector(1, 0, 0))],
        },
        "geometry": [_geometry_row(sketch, i, g) for i, g in enumerate(sketch.Geometry)],
        "constraints": [],
    }
    support = sketch.AttachmentSupport
    if support:
        info["on"] = [
            "%s%s" % (obj.Label, ("." + subs[0]) if subs and subs[0] else "")
            for obj, subs in [
                (s[0], list(s[1]) if isinstance(s[1], (list, tuple)) else [s[1]]) for s in support
            ]
        ]
    for i, c in enumerate(sketch.Constraints):
        row = {"index": i, "type": c.Type}
        if c.Name:
            row["name"] = c.Name
        items = []
        for geo, pos in ((c.First, c.FirstPos), (c.Second, c.SecondPos), (c.Third, c.ThirdPos)):
            if geo is None or geo < -2000:
                continue
            items.append({"curve": geo, "point": POS_NAMES.get(pos, str(pos))})
        row["items"] = items
        if c.Type in DIMENSION_TYPES:
            try:
                q = sketch.getDatum(i)
                value = q.Value
                row["value"] = round(
                    math.degrees(value) if c.Type == "Angle" and "rad" in str(q.Unit) else value, 6
                )
                if c.Type == "Angle":
                    row["value"] = round(q.getValueAs("deg").Value, 6)
            except Exception:
                pass
            row["driving"] = bool(c.Driving)
            for path, expr in sketch.ExpressionEngine:
                if path in (".Constraints[%d]" % i, ".Constraints.%s" % c.Name):
                    from ... import parameters_core

                    row["expression"] = parameters_core.from_freecad(expr)
        info["constraints"].append(row)
    try:
        dof = sketch.solve()
        info["solver"] = {
            0: "solved",
            -1: "failed",
            -2: "redundant",
            -3: "conflicting",
            -4: "over-constrained",
        }.get(dof, str(dof))
    except Exception:
        pass
    try:
        info["degrees_of_freedom"] = int(
            sketch.getDoF() if hasattr(sketch, "getDoF") else sketch.DoF
        )
    except Exception:
        info["degrees_of_freedom"] = None
    try:  # Fusion's padlock, as the browser and timeline show it (sketch_explain)
        from ... import sketch_explain

        info["fully_constrained"] = bool(sketch_explain.fully_constrained(sketch))
    except Exception:
        pass
    for key, prop in (
        ("conflicting", "Conflicting"),
        ("redundant", "Redundant"),
        ("malformed", "Malformed"),
    ):
        found = _list(getattr(sketch, prop + "Constraints", []))
        if found:
            info[key + "_constraints"] = [n - 1 for n in found]  # (FreeCAD counts from 1)
    areas = []
    try:
        for sub, face in extrude.regions(sketch):
            areas.append({"area_mm2": round(face.Area, 6), "point_inside": _inside(sketch, face)})
    except Exception:
        pass
    info["closed_areas"] = areas
    return json_result(info)


def _inside(sketch, face):
    """A point inside a sketch area, in sketch coordinates (for regions)."""
    try:
        points, triangles = face.tessellate(0.5)
        best = None
        for a, b, c in triangles:
            pa, pb, pc = points[a], points[b], points[c]
            area = ((pb - pa).cross(pc - pa)).Length
            if best is None or area > best[0]:
                best = (area, (pa + pb + pc) * (1.0 / 3.0))
        if best is not None:
            return _local(sketch, best[1])
    except Exception:
        pass
    return _local(sketch, face.CenterOfMass)


# -- drawing ------------------------------------------------------------------------------------
@action("add_to_sketch")
def add_to_sketch(ctx, args):
    from ..ops import core
    from ..ops.sweep_loft_ops import draw_curves

    sketch = _sketch(ctx, args["sketch"])
    doc = sketch.Document
    construction = bool(args.get("construction"))

    def work():
        first = len(sketch.Geometry)
        if args.get("geometry"):
            core.draw(sketch, args["geometry"], first_index=len(sketch.Constraints))
        if args.get("curves"):
            draw_curves(sketch, args["curves"], "add_to_sketch")
        added = list(range(first, len(sketch.Geometry)))
        if construction:
            for index in added:
                sketch.setConstruction(index, True)
        doc.recompute()
        if "Invalid" in list(sketch.State):
            raise UserError("The sketch became invalid (conflicting constraints).")
        return added

    before = _broken(doc)
    added = ctx.change(work)
    return ctx.done(
        "Done: %s. New curves %s in %s." % (ctx.title, _span(added), sketch.Name), doc, before
    )


def _span(indexes):
    if not indexes:
        return "(none)"
    if len(indexes) == 1:
        return str(indexes[0])
    return "%d to %d" % (indexes[0], indexes[-1])


def _broken(doc):
    from ..executor import _broken as broken

    return broken(doc)


# -- constraints --------------------------------------------------------------------------------
def _ref(item):
    return int(item["curve"]), POS[item.get("point", "whole")]


def _con(*args):
    import Sketcher

    return Sketcher.Constraint(*args)


def _constraint(sketch, kind, items):
    refs = [_ref(i) for i in items]
    g1, p1 = refs[0]
    g2, p2 = refs[1] if len(refs) > 1 else (None, 0)
    if kind == "coincident":
        if p1 and p2:
            return [_con("Coincident", g1, p1, g2, p2)]
        if p1 or p2:
            point, curve = ((g1, p1), g2) if p1 else ((g2, p2), g1)
            return [_con("PointOnObject", point[0], point[1], curve)]
        raise UserError("coincident needs at least one point (start, end or center).")
    if kind == "point_on":
        if not p1 or p2:
            raise UserError("point_on takes a point first, then a whole curve.")
        return [_con("PointOnObject", g1, p1, g2)]
    if kind in ("horizontal", "vertical"):
        word = kind.capitalize()
        if len(refs) == 1:
            return [_con(word, g1)]
        if not (p1 and p2):
            raise UserError("%s of two items needs two points." % kind)
        return [_con(word, g1, p1, g2, p2)]
    if kind in ("parallel", "perpendicular", "equal", "collinear"):
        word = {"collinear": "Tangent"}.get(kind, kind.capitalize())
        return [_con(word, g1, g2)]  # (FreeCAD's line-line tangency is collinearity)
    if kind in ("tangent", "smooth"):
        if p1 and p2:
            return [_con("Tangent", g1, p1, g2, p2)]
        return [_con("Tangent", g1, g2)]
    if kind == "concentric":
        return [_con("Coincident", g1, 3, g2, 3)]
    if kind == "midpoint":
        point, line = (refs[0], refs[1][0]) if refs[0][1] else (refs[1], refs[0][0])
        if not point[1]:
            raise UserError("midpoint takes a point (start, end or center) and a line.")
        geo = sketch.Geometry[line] if line >= 0 else None
        if geo is None or geo.TypeId != "Part::GeomLineSegment":
            raise UserError("midpoint here takes a line (for an arc use Fusion's dialog).")
        return [_con("Symmetric", line, 1, line, 2, point[0], point[1])]
    if kind == "symmetric":
        g3, p3 = refs[2]
        if not (p1 and p2):
            raise UserError(
                "symmetric takes two points (start, end or center), then a line "
                "or a point to mirror about."
            )
        if p3:
            return [_con("Symmetric", g1, p1, g2, p2, g3, p3)]
        return [_con("Symmetric", g1, p1, g2, p2, g3)]
    if kind == "fix":
        if not p1:
            return [_con("Block", g1)]
        point = sketch.getPoint(g1, p1)
        return [_con("DistanceX", g1, p1, point.x), _con("DistanceY", g1, p1, point.y)]
    raise UserError("Unknown constraint %r." % kind)


def _check_items(sketch, items):
    count = len(sketch.Geometry)
    for item in items:
        curve = int(item["curve"])
        if curve >= count or curve < -2:
            raise UserError(
                "The sketch has no curve %d (it has 0 to %d; -1 / -2 are its x / y "
                "axes)." % (curve, count - 1)
            )


# Fusion's names of the constraint tools (the titles sketch_explain's messages start with)
TITLES = {
    "coincident": "Coincident",
    "point_on": "Coincident",
    "symmetric": "Symmetry",
    "smooth": "Smooth",
    "fix": "Fix",
}


def _title(kind):
    return TITLES.get(kind, kind.replace("_", " ").capitalize())


def _explained(ctx, sketch, text, culprits):
    """sketch_explain's message for an AI answer: the culprits by index too (the AI deletes
    or changes them by index); highlighted in the window, as the dialogs do."""
    from ... import sketch_explain, sketch_explain_core

    if ctx.host.gui and culprits:
        try:
            sketch_explain.highlight(sketch, culprits)
        except Exception as exc:
            warn("AI sketch: the culprits were not highlighted (%s)" % exc)
    else:
        text = text.replace(sketch_explain_core.SHOWN, "")
    if culprits:
        text = text.rstrip().rstrip(".") + (
            " (constraint%s %s of %s: get_sketch lists them, sketch_delete removes one)."
            % ("s" if len(culprits) > 1 else "", ", ".join(str(i) for i in culprits), sketch.Name)
        )
    return text


def _listed(sketch, new):
    """The constraints the last solve called redundant, apart from `new`, on the curves
    connected to them (sketch_explain.component)."""
    from ... import sketch_explain

    _conflicting, redundant = sketch_explain.bad_sets(sketch)
    near = sketch_explain.component(sketch, new)
    return sorted(i for i in redundant if i not in new and i in near)


def _add_checked(ctx, sketch, constraints, title):
    """Add constraints; if one conflicts with the sketch or says what it says already, take
    them out again and say which constraints it fights or repeats, in the words the
    sketch's own tools use (sketch_explain)."""
    from ... import sketch_explain

    first = len(sketch.Constraints)
    before = sketch.solve()
    sketch.addConstraint(constraints)
    added = list(range(first, len(sketch.Constraints)))
    finding = sketch_explain.check_new(sketch, added, probe=True)
    code = sketch.solve() if not finding else -1
    if not finding and code != 0 and before == 0:
        # the solver failed without listing the new ones (two fixed circles made
        # concentric: it lists the Blocks): the others it lists are what they fight
        culprits = sketch_explain.conflict_culprits(sketch, added) or _listed(sketch, added)
        if culprits:
            finding = sketch_explain.Finding("conflict", added, culprits)
    if finding or (code != 0 and before == 0):
        text = ""
        if finding:
            sketch_explain.log_finding("AI " + title, sketch, finding)
            text = sketch_explain.refusal(sketch, title, finding)
            text = _explained(ctx, sketch, text, finding.culprits)
        for index in sorted(added, reverse=True):
            sketch.delConstraint(index)
        sketch.solve()
        if text:
            raise UserError(text)
        raise UserError(
            "%s: not added, it does not fit the sketch's other constraints "
            "(over-constrained)." % title
        )
    return added


@action("sketch_constraint")
def sketch_constraint(ctx, args):
    sketch = _sketch(ctx, args["sketch"])
    _check_items(sketch, args["items"])
    doc = sketch.Document

    def work():
        added = _add_checked(
            ctx, sketch, _constraint(sketch, args["kind"], args["items"]), _title(args["kind"])
        )
        doc.recompute()
        return added

    before = _broken(doc)
    added = ctx.change(work)
    note = " (tangent: the solver keeps G1 here)" if args["kind"] == "smooth" else ""
    return ctx.done(
        "Done: %s%s, constraint %s of %s." % (ctx.title, note, _span(added), sketch.Name),
        doc,
        before,
    )


def _point(sketch, ref):
    g, p = ref
    if g == -1 and p in (0, 1):
        return App.Vector(0, 0, 0)
    return sketch.getPoint(g, p if p else 1)


def _measured(sketch, kind, refs):
    """What a new dimension measures now (its starting value when a formula drives it)."""
    if kind in ("radius", "diameter"):
        geo = sketch.Geometry[refs[0][0]]
        return geo.Radius * (2.0 if kind == "diameter" else 1.0)
    if kind == "angle":

        def direction(g):
            if g == -1:
                return App.Vector(1, 0, 0)
            if g == -2:
                return App.Vector(0, 1, 0)
            geo = sketch.Geometry[g]
            return geo.EndPoint - geo.StartPoint

        a = direction(refs[0][0])
        b = direction(refs[1][0]) if len(refs) > 1 else App.Vector(1, 0, 0)
        return math.degrees(a.getAngle(b))
    if len(refs) == 1:
        geo = sketch.Geometry[refs[0][0]]
        delta = geo.EndPoint - geo.StartPoint
    elif refs[1][1] == 0:  # a point and a line
        geo = sketch.Geometry[refs[1][0]]
        point = _point(sketch, refs[0])
        line = geo.EndPoint - geo.StartPoint
        foot = geo.StartPoint + line * ((point - geo.StartPoint).dot(line) / line.dot(line))
        delta = point - foot
        return delta.Length
    else:
        delta = _point(sketch, refs[1]) - _point(sketch, refs[0])
    if kind == "distance_x":
        return delta.x
    if kind == "distance_y":
        return delta.y
    return delta.Length


def _dimension(kind, refs, value):
    word = {
        "distance": "Distance",
        "distance_x": "DistanceX",
        "distance_y": "DistanceY",
        "radius": "Radius",
        "diameter": "Diameter",
        "angle": "Angle",
    }[kind]
    if kind == "angle":
        value = math.radians(value)
        if len(refs) == 1:
            return _con("Angle", refs[0][0], value)
        return _con("Angle", refs[0][0], refs[1][0], value)
    if kind in ("radius", "diameter"):
        return _con(word, refs[0][0], value)
    if len(refs) == 1:
        if refs[0][1]:
            raise UserError("a %s of one item takes a whole line" % kind)
        return _con(word, refs[0][0], value)
    (g1, p1), (g2, p2) = refs
    if not p1:
        raise UserError("the first item of a distance is a point (start, end or center)")
    if not p2:
        if kind != "distance":
            raise UserError("%s between a point and a line: give two points" % kind)
        return _con("Distance", g1, p1, g2, value)
    if g1 == -1 and p1 == 0:
        p1 = 1
    return _con(word, g1, p1, g2, p2, value)


@action("sketch_dimension")
def sketch_dimension(ctx, args):
    from ... import parameters

    sketch = _sketch(ctx, args["sketch"])
    _check_items(sketch, args["items"])
    refs = [_ref(i) for i in args["items"]]
    kind = args["kind"]
    doc = sketch.Document
    if "value" in args:
        value = float(args["value"])
    else:
        value = _measured(sketch, kind, refs)
    if kind in ("radius", "diameter", "distance") and value <= 0:
        raise UserError("A %s must be more than 0." % kind)

    def work():
        added = _add_checked(ctx, sketch, [_dimension(kind, refs, value)], "Dimension")
        index = added[0]
        if args.get("name"):
            sketch.renameConstraint(index, args["name"])
        if args.get("expression"):
            parameters._set(
                sketch, ".Constraints[%d]" % index, args["expression"], parameters.user_names(doc)
            )
        doc.recompute()
        if "Invalid" in list(sketch.State):
            raise UserError("The sketch could not take that dimension.")
        return index

    before = _broken(doc)
    index = ctx.change(work)
    shown = sketch.getDatum(index)
    return ctx.done(
        "Done: %s, constraint %d of %s = %s." % (ctx.title, index, sketch.Name, shown.UserString),
        doc,
        before,
    )


@action("set_sketch_dimension")
def set_sketch_dimension(ctx, args):
    from ... import parameters

    sketch = _sketch(ctx, args["sketch"])
    doc = sketch.Document
    if "constraint" in args:
        found = [i for i, c in enumerate(sketch.Constraints) if c.Name == args["constraint"]]
        if not found:
            names = [c.Name for c in sketch.Constraints if c.Name]
            raise UserError(
                "%s has no dimension called %r (named ones: %s)."
                % (sketch.Name, args["constraint"], ", ".join(names) or "none")
            )
        index = found[0]
    else:
        index = int(args["index"])
        if index >= len(sketch.Constraints):
            raise UserError("%s has no constraint %d." % (sketch.Name, index))
    c = sketch.Constraints[index]
    if c.Type not in DIMENSION_TYPES:
        raise UserError("Constraint %d is a %s, not a dimension." % (index, c.Type))
    path = ".Constraints[%d]" % index

    from ... import sketch_explain_core

    offset = sketch_explain_core.is_offset(c.Type, c.First, c.Second)
    if "value" in args and sketch_explain_core.bad_size(c.Type, float(args["value"]), offset):
        raise UserError("The value must be more than 0.")

    def conflict():
        """The value does not fit: name what it fights (FreeCAD's failed solve still knows),
        in the words of the dimension box (sketch_explain)."""
        from ... import sketch_explain

        try:
            culprits = sketch_explain.conflict_culprits(sketch, [index])
        except Exception:
            culprits = []
        if not culprits:
            return UserError(
                "The sketch cannot take that value (it would break its other constraints)."
            )
        words, _count = sketch_explain.words(sketch, culprits)
        text = sketch_explain_core.value_conflict(words)
        return UserError(_explained(ctx, sketch, text, culprits))

    def work():
        solved_before = sketch.solve() == 0
        if "value" in args:
            sketch.setExpression(path, None)
            unit = "deg" if c.Type == "Angle" else "mm"
            try:
                sketch.setDatum(index, App.Units.Quantity("%r %s" % (float(args["value"]), unit)))
            except Exception:
                raise conflict()  # (FreeCAD: "Negative datum values are not valid")
        elif args["expression"].strip():
            parameters._set(sketch, path, args["expression"], parameters.user_names(doc))
        else:
            sketch.setExpression(path, None)
        doc.recompute()
        if "Invalid" in list(sketch.State) or (solved_before and sketch.solve() != 0):
            raise conflict()

    before = _broken(doc)
    ctx.change(work)
    return ctx.done(
        "Done: %s = %s." % (c.Name or "dimension %d" % index, sketch.getDatum(index).UserString),
        doc,
        before,
    )


@action("sketch_delete")
def sketch_delete(ctx, args):
    sketch = _sketch(ctx, args["sketch"])
    doc = sketch.Document
    curves = sorted(set(args.get("curves") or []))
    constraints = sorted(set(args.get("constraints") or []), reverse=True)
    for index in curves:
        if index >= len(sketch.Geometry):
            raise UserError("%s has no curve %d." % (sketch.Name, index))
    for index in constraints:
        if index >= len(sketch.Constraints):
            raise UserError("%s has no constraint %d." % (sketch.Name, index))

    def work():
        for index in constraints:
            sketch.delConstraint(index)
        if curves:
            sketch.delGeometries(curves)
        doc.recompute()

    before = _broken(doc)
    ctx.change(work)
    return ctx.done(
        "Done: deleted %d curve(s) and %d constraint(s) of %s. Indexes have moved: "
        "call get_sketch again." % (len(curves), len(constraints), sketch.Name),
        doc,
        before,
    )


@action("sketch_text")
def sketch_text(ctx, args):
    from ... import text, text_core

    sketch = _sketch(ctx, args["sketch"])
    doc = sketch.Document
    spec = text.default_spec()
    for key in (
        "text",
        "height",
        "font",
        "bold",
        "italic",
        "angle",
        "h_align",
        "v_align",
        "spacing",
        "width",
        "frame_height",
    ):
        if key in args:
            spec[key] = args[key]
    spec["corner"] = tuple(args.get("corner", (0.0, 0.0)))
    if not spec.get("width") or not spec.get("frame_height"):
        try:
            info = text.resolve_font(spec["font"], spec["bold"], spec["italic"])[0]
            width, height = text_core.text_extent(
                spec["text"], info, spec["height"], spec["spacing"]
            )
        except Exception:
            width, height = 10.0 * spec["height"], 1.5 * spec["height"]
        spec["width"] = spec.get("width") or width
        spec["frame_height"] = spec.get("frame_height") or height

    def work():
        try:
            obj = text.make(sketch, spec, ctx.new_id("Text"))
        except text.TextError as exc:
            raise UserError(str(exc))
        doc.recompute()
        if "Invalid" in list(obj.State):
            raise UserError("The text could not be made: %s" % obj.getStatusString())
        return obj

    before = _broken(doc)
    obj = ctx.change(work)
    return ctx.done(
        "Done: %s. Its id is %r: extrude it with profile %r." % (ctx.title, obj.Name, obj.Name),
        doc,
        before,
    )
