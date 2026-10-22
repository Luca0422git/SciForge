# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI actions that let an agent check its own work (catalog/verify_tools.py says what each
one answers): inspect_design, query_geometry, check_design, render and diff_design. They
read the design with SciForge's own code (bodies, timeline_ops, parameters, analysis,
material) and never change it; render draws with the 3D view of the window when there is
one (capture_ui) and with sciforge/ai/render_core.py otherwise.

Snapshots: inspect_design keeps a small record of the design (each body's volume, area,
size and counts, each step's state and values, the parameters) under an id ("S1"), and the
executor keeps one taken just before the latest change ("last_change"); diff_design compares
the design with either, or with the solid as it was after a step."""

import base64
import time

from .. import bridge_core
from ..executor import UserError, json_result
from . import action

MAX_SNAPSHOTS = 20  # per design, oldest dropped first
_SNAPSHOTS = {}  # document name -> {"S1": record, ...}
_LAST = {}  # document name -> the record taken before the latest change
_COUNTER = {"n": 0}


def _r(value, digits=6):
    try:
        out = round(float(value), digits)
        return 0.0 if out == 0 else out
    except Exception:
        return value


def _bbox(box):
    return {
        "min": [_r(box.XMin), _r(box.YMin), _r(box.ZMin)],
        "max": [_r(box.XMax), _r(box.YMax), _r(box.ZMax)],
        "size": [_r(box.XLength), _r(box.YLength), _r(box.ZLength)],
    }


def _shape_counts(shape):
    return {
        "solids": len(shape.Solids),
        "shells": len(shape.Shells),
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "vertices": len(shape.Vertexes),
    }


def _centre(shape):
    from ... import analysis

    try:
        centre, _volume = analysis.center_of_mass([shape])
        return [_r(v) for v in centre]
    except Exception:
        try:
            return [_r(v) for v in shape.CenterOfMass]
        except Exception:
            return None


def _chosen(ctx, args, doc):
    from ... import bodies

    if args.get("bodies"):
        return [ctx.body_of(ident) for ident in args["bodies"]]
    return bodies.list_bodies(doc)


def body_row(body, full=True):
    """What inspect_design tells about one body."""
    from ... import bodies

    row = {"id": body.Name, "label": body.Label}
    try:
        row["shown"] = bool(bodies.is_shown(body))
    except Exception:
        pass
    shape = None
    try:
        shape = bodies.global_shape(body) if not body.Shape.isNull() else None
    except Exception:
        shape = None
    if shape is None or shape.isNull():
        row.update(solid=False, empty=True)
        return row
    row.update(_shape_counts(shape))
    row["solid"] = bool(shape.Solids)
    row["volume_mm3"] = _r(shape.Volume)
    row["area_mm2"] = _r(shape.Area)
    row["bbox_mm"] = _bbox(shape.BoundBox)
    if not full:
        return row
    try:
        row["valid"] = bool(shape.isValid())
    except Exception:
        row["valid"] = False
    if shape.Solids:
        row["center_of_mass_mm"] = _centre(shape)
        try:
            row["closed"] = all(s.isClosed() for s in shape.Shells)
        except Exception:
            pass
    try:
        tip = getattr(body, "Tip", None)
        row["tip"] = tip.Name if tip is not None else None
    except Exception:
        pass
    try:
        from ... import material

        label, rho = material.effective(body)
        row["material"] = label
        if rho and shape.Solids:
            row["mass_g"] = _r(shape.Volume * rho * 1000.0)
    except Exception:
        pass
    try:
        from ... import components

        comp = components.component_of(body)
        if comp is not None:
            row["component"] = comp.Name
    except Exception:
        pass
    return row


def _steps(doc, detail="summary"):
    from ... import timeline_ops
    from .timeline_actions import _read, _values_of, step_kind

    try:
        tl = timeline_ops.timeline(doc)
    except Exception:
        return [], None
    values = _values_of(doc)
    rows = []
    for item in tl.items:
        obj = doc.getObject(item.name)
        row = {
            "index": item.index,
            "id": item.name,
            "name": item.display,
            "kind": item.kind,
            "type": obj.TypeId if obj is not None else item.type_id,
            "body": item.body,
            "state": item.state,
        }
        if item.suppressed:
            row["suppressed"] = True
        row["status"] = item.status
        if item.message:
            row["message"] = item.message
        if item.component:
            row["component"] = item.component_name or item.component
        if item.name in values:
            row["values"] = values[item.name]
        if detail == "full" and obj is not None:
            try:
                kind = step_kind(obj)
                read = _read(obj, kind) if kind and kind != "sketch" else None
                if read is not None:
                    row["definition"] = read
            except Exception as exc:
                row["definition_error"] = str(exc)
        rows.append(row)
    after = tl.items[tl.marker - 1].name if 0 < tl.marker <= len(tl.items) else None
    marker = {"after_step": after, "slot": tl.marker, "at_end": tl.at_end}
    return rows, marker


def _parameters(doc):
    from ... import parameters

    rows = []
    try:
        for row in parameters.user_parameters(doc):
            rows.append(
                {
                    "name": row["name"],
                    "value": _r(row["value"]),
                    "unit": row["unit"],
                    "expression": row["expression"],
                    "comment": row.get("comment") or "",
                }
            )
    except Exception:
        pass
    return rows


def _sketches(doc):
    from ... import extrude

    rows = []
    for obj in doc.Objects:
        if obj.TypeId != "Sketcher::SketchObject":
            continue
        row = {"id": obj.Name, "label": obj.Label, "curves": len(obj.Geometry)}
        try:
            row["closed_areas"] = len(extrude.regions(obj))
        except Exception:
            row["closed_areas"] = None
        try:
            row["fully_constrained"] = bool(obj.FullyConstrained)
        except Exception:
            pass
        for key in ("Conflicting", "Redundant", "Malformed"):
            found = list(getattr(obj, key + "Constraints", []) or [])
            if found:
                row[key.lower() + "_constraints"] = [n - 1 for n in found]
        rows.append(row)
    return rows


def _assembly(doc, info):
    from ..actions.inspect_actions import _round

    try:
        from ... import components

        comps = components.list_components(doc)
        if comps:
            info["components"] = [
                {
                    "id": c.Name,
                    "label": c.Label,
                    "bodies": [b.Name for b in components.bodies_in(doc, c)],
                }
                for c in comps
            ]
    except Exception:
        pass
    try:
        from ... import joints

        found = joints.joints(doc)
        if found:
            info["joints"] = [
                {
                    "id": j.Name,
                    "label": j.Label,
                    "type": joints.fusion_type(j),
                    "value": [_round(v) for v in joints.value(j)],
                }
                for j in found
            ]
    except Exception:
        pass
    datums = [
        o
        for o in doc.Objects
        if o.TypeId in ("PartDesign::Plane", "PartDesign::Line", "PartDesign::Point")
    ]
    if datums:
        info["construction"] = [
            {"id": o.Name, "label": o.Label, "type": o.TypeId.split("::")[1]} for o in datums
        ]
    pages = [o for o in doc.Objects if o.TypeId == "TechDraw::DrawPage"]
    if pages:
        info["drawings"] = [{"id": p.Name, "label": p.Label} for p in pages]


# -- snapshots --------------------------------------------------------------------------------
def record(doc):
    """A small record of the design for diff_design (cheap: no validity checks)."""
    from ... import bodies, timeline_ops
    from .timeline_actions import _values_of

    out = {"doc": doc.Name, "time": time.time(), "bodies": {}, "steps": {}, "order": []}
    for body in bodies.list_bodies(doc):
        out["bodies"][body.Name] = body_row(body, full=False)
    try:
        values = _values_of(doc)
        for item in timeline_ops.timeline(doc).items:
            out["order"].append(item.name)
            out["steps"][item.name] = {
                "index": item.index,
                "name": item.display,
                "kind": item.kind,
                "state": item.state,
                "status": item.status,
                "message": item.message,
                "suppressed": bool(item.suppressed),
                "values": values.get(item.name, {}),
            }
    except Exception:
        pass
    out["parameters"] = {p["name"]: p for p in _parameters(doc)}
    return out


def keep_snapshot(doc):
    _COUNTER["n"] += 1
    ident = "S%d" % _COUNTER["n"]
    store = _SNAPSHOTS.setdefault(doc.Name, {})
    store[ident] = record(doc)
    while len(store) > MAX_SNAPSHOTS:
        store.pop(next(iter(store)))
    return ident


def before_change(doc):
    """The executor calls this before a call that changes the design: a record, or None."""
    try:
        return record(doc) if doc is not None else None
    except Exception:
        return None


def after_change(doc_name, rec):
    """The change went through: rec becomes what last_change compares with."""
    if rec is not None and doc_name:
        _LAST[doc_name] = rec


def forget(doc_name):
    _SNAPSHOTS.pop(doc_name, None)
    _LAST.pop(doc_name, None)


# -- inspect_design ---------------------------------------------------------------------------
@action("inspect_design")
def inspect_design(ctx, args):
    doc = ctx.doc
    if doc is None:
        return json_result(
            {
                "design": None,
                "note": "No design is open: new_design, open_design or "
                "create_sketch starts one.",
            },
            "No design is open.",
            compact=True,
        )
    detail = args.get("detail", "summary")
    active = ctx.host.find_body(doc)
    info = {
        "design": doc.Label,
        "id": doc.Name,
        "file": doc.FileName or None,
        "units": "mm, mm2, mm3, g, degrees",
        "active_body": active.Name if active is not None else None,
    }
    rows = [body_row(b) for b in _chosen(ctx, args, doc)]
    info["bodies"] = rows
    steps, marker = _steps(doc, detail)
    info["timeline"] = steps
    if marker is not None:
        info["history_marker"] = marker
    info["parameters"] = _parameters(doc)
    info["sketches"] = _sketches(doc)
    _assembly(doc, info)
    try:
        info["selection"] = ctx.host.selection(doc)
    except Exception:
        info["selection"] = []
    failed = [s for s in steps if s.get("status") == "error"]
    invalid = [b for b in rows if b.get("solid") and not b.get("valid", True)]
    info["summary"] = {
        "bodies": len(rows),
        "solid_bodies": len([b for b in rows if b.get("solid")]),
        "steps": len(steps),
        "failed_steps": [s["id"] for s in failed],
        "invalid_bodies": [b["id"] for b in invalid],
        "total_volume_mm3": _r(sum(b.get("volume_mm3", 0.0) for b in rows if b.get("solid"))),
    }
    info["snapshot"] = keep_snapshot(doc)
    words = "%s: %d bod%s, %d step%s" % (
        doc.Label,
        len(rows),
        "y" if len(rows) == 1 else "ies",
        len(steps),
        "" if len(steps) == 1 else "s",
    )
    if failed:
        words += ", %d failed (%s)" % (len(failed), ", ".join(s["id"] for s in failed))
    if invalid:
        words += ", %d invalid bod%s" % (len(invalid), "y" if len(invalid) == 1 else "ies")
    return json_result(info, words + ". Snapshot %s." % info["snapshot"], compact=True)


# -- query_geometry ---------------------------------------------------------------------------
def target_shape(ctx, ident=None):
    """(object, shape, words) of what query_geometry / render's highlight look at: a body
    (its tip's solid, the shape the selectors of every tool look at) or a step (the solid
    as it was right after it)."""
    from ... import bodies

    doc = ctx.need_doc()
    if ident:
        obj = ctx.resolve(ident, "body or step")
    else:
        obj = ctx.host.find_body(doc)
        if obj is None:
            raise UserError("There is no body to look at: make one first.")
    if bodies.is_body(obj):
        tip = getattr(obj, "Tip", None)
        source = tip if tip is not None and not tip.Shape.isNull() else obj
        words = "body %s" % obj.Name
    else:
        source = obj
        words = "step %s" % obj.Name
    try:
        shape = source.Shape
    except Exception:
        shape = None
    if shape is None or shape.isNull():
        raise UserError("%s has no shape to look at." % obj.Name)
    return obj, source, shape, words


@action("query_geometry")
def query_geometry(ctx, args):
    from .. import geometry_facts as gf
    from ..ops import selectors

    obj, source, shape, words = target_shape(ctx, args.get("of"))
    element = args.get("element", "faces")
    spec = args.get("select") or {"all": True}
    try:
        if element == "vertices":
            names = gf.select_vertices(shape, spec)
        else:
            names = selectors.select(shape, spec, element)
    except (selectors.SelectionError, KeyError, ValueError) as exc:
        raise UserError("The selector does not fit %s: %s." % (words, exc))
    limit = int(args.get("limit", 60))
    shown = names[:limit]
    refs = {}
    if args.get("refs", True) and element != "vertices":
        refs = gf.stable_refs(shape, element, wanted=set(shown))
    rows = []
    for name in shown:
        sub = shape.getElement(name)
        row = {"name": name}
        row.update(gf.facts(sub, element))
        if element != "vertices":
            row["ref"] = refs.get(name) if args.get("refs", True) else None
        pick = gf.pick_of(name, element, row.get("ref"), sub)
        if pick is not None:
            row["pick"] = pick
        rows.append(row)
    out = {
        "of": obj.Name,
        "shape_of": source.Name,
        "element": element,
        "count": len(names),
        "shown": len(rows),
        "elements": rows,
        "note": "name (Face3...) is FreeCAD's number for the element now and changes when "
        "the model changes; ref is a selector that picks the same element by its geometry: "
        "use ref (or pick) in other tools. Coordinates are in mm, in %s's own coordinates."
        % obj.Name,
    }
    try:
        from ... import bodies

        body = obj if bodies.is_body(obj) else bodies.body_of(obj)
        place = body.getGlobalPlacement() if body is not None else None
        if place is not None and not place.isIdentity():
            out["body_placement"] = {
                "base_mm": [_r(v) for v in place.Base],
                "axis": [_r(v) for v in place.Rotation.Axis],
                "angle_deg": _r(place.Rotation.Angle * 57.29577951308232),
            }
            out["note"] += " The body is moved: add body_placement for design coordinates."
    except Exception:
        pass
    if len(names) > len(rows):
        out["more"] = "%d more not shown: narrow select or raise limit" % (len(names) - len(rows))
    text = "%d %s of %s%s." % (
        len(names),
        element if len(names) != 1 else element[:-1] if element != "vertices" else "vertex",
        words,
        (" (showing %d)" % len(rows)) if len(names) > len(rows) else "",
    )
    return json_result(out, text, compact=True)


# -- check_design -----------------------------------------------------------------------------
@action("check_design")
def check_design(ctx, args):
    from ... import analysis, bodies

    doc = ctx.need_doc()
    problems, warnings = [], []
    rows = []
    chosen = _chosen(ctx, args, doc)
    for body in chosen:
        row = body_row(body)
        rows.append(row)
        name = "%s (%s)" % (body.Label, body.Name)
        if row.get("empty"):
            warnings.append("%s is empty: it has no shape." % name)
            continue
        if not row.get("solid"):
            warnings.append(
                "%s has no solid, only %d face(s) (a surface body)." % (name, row["faces"])
            )
            continue
        if not row.get("valid", True):
            detail = ""
            try:
                bodies.global_shape(body).check(True)
            except Exception as exc:
                detail = ": " + (str(exc).strip().splitlines() or [""])[0][:200]
            problems.append("%s is not a valid solid%s." % (name, detail))
        if row.get("closed") is False:
            problems.append("%s is not closed (it has holes in its skin)." % name)
        if row.get("solids", 0) > 1:
            warnings.append(
                "%s is made of %d separate pieces (Fusion would make them separate bodies; a "
                "3D printer prints them apart)." % (name, row["solids"])
            )
        if row.get("volume_mm3", 0) <= 1e-9:
            problems.append("%s has no volume." % name)
    steps, marker = _steps(doc)
    failed = [s for s in steps if s.get("status") == "error"]
    for s in failed:
        problems.append(
            "Step %s (%s) failed: %s" % (s["name"], s["id"], s.get("message") or "no reason given")
        )
    for s in steps:
        if s.get("status") == "warning":
            warnings.append("Step %s (%s) warns: %s" % (s["name"], s["id"], s.get("message") or ""))
    suppressed = [s["id"] for s in steps if s.get("suppressed")]
    if suppressed:
        warnings.append("Suppressed steps (left out of the result): %s." % ", ".join(suppressed))
    if marker is not None and not marker["at_end"]:
        later = [s["id"] for s in steps if s.get("state") == "rolled_back"]
        warnings.append(
            "The history marker is rolled back: %d step(s) after it are not in the result (%s)."
            % (len(later), ", ".join(later))
        )
    sketches = _sketches(doc)
    for sk in sketches:
        for key in ("conflicting", "redundant", "malformed"):
            if sk.get(key + "_constraints"):
                problems.append(
                    "Sketch %s has %s constraints (numbers %s)."
                    % (sk["id"], key, ", ".join(str(n) for n in sk[key + "_constraints"]))
                )
    overlap = []
    if args.get("interference", True):
        solid = [b for b in chosen if bodies.has_solid(b)]
        if len(solid) >= 2:
            try:
                pairs = analysis.interference([(b.Label, bodies.global_shape(b)) for b in solid])
                overlap = [{"body1": a, "body2": b, "volume_mm3": _r(v)} for a, b, v, _s in pairs]
            except Exception as exc:
                warnings.append("Interference could not be checked: %s" % exc)
            for pair in overlap:
                problems.append(
                    "Bodies %s and %s overlap by %.6g mm3."
                    % (pair["body1"], pair["body2"], pair["volume_mm3"])
                )
    others = []
    for obj in doc.Objects:
        try:
            state = list(obj.State)
        except Exception:
            continue
        if "Invalid" in state and obj.Name not in {s["id"] for s in steps}:
            others.append(obj.Name)
    if others:
        problems.append("These objects are in error: %s." % ", ".join(others))
    out = {
        "ok": not problems,
        "problems": problems,
        "warnings": warnings,
        "bodies": rows,
        "failed_steps": [
            {"id": s["id"], "name": s["name"], "message": s.get("message", "")} for s in failed
        ],
        "interference": overlap if args.get("interference", True) else None,
        "sketches": [
            {k: v for k, v in s.items() if k in ("id", "fully_constrained", "closed_areas")}
            for s in sketches
        ],
    }
    text = "Design check: %s, %d problem%s, %d warning%s." % (
        "OK" if not problems else "NOT OK",
        len(problems),
        "" if len(problems) == 1 else "s",
        len(warnings),
        "" if len(warnings) == 1 else "s",
    )
    return json_result(out, text, compact=True)


# -- render -------------------------------------------------------------------------------------
def _tolerance(shape):
    try:
        return max(shape.BoundBox.DiagonalLength / 600.0, 0.005)
    except Exception:
        return 0.05


def _highlights(ctx, highlight):
    """{"faces": set of (shape source name, element name), "edges": ...} to mark."""
    from ..ops import selectors

    marked = {"faces": set(), "edges": set(), "words": []}
    if not highlight:
        return marked
    _obj, source, shape, words = target_shape(ctx, highlight.get("of"))
    for element in ("faces", "edges"):
        if element not in highlight:
            continue
        try:
            names = selectors.select(shape, highlight[element], element)
        except (selectors.SelectionError, KeyError, ValueError) as exc:
            raise UserError("The highlight selector does not fit %s: %s." % (words, exc))
        if not names:
            raise UserError("The highlight's %s selector picked nothing on %s." % (element, words))
        marked[element].update(names)
        marked["words"].append("%d %s of %s" % (len(names), element, words))
    marked["source"] = source
    marked["shape"] = shape
    return marked


def scene(ctx, doc, marked, edges=True):
    """(meshes, lines) of the design for render_core: every shown body with a solid or
    faces, the shown sketches as blue lines, and the marked faces / edges in orange."""
    from ... import bodies
    from .. import render_core

    meshes, lines = [], []
    shown = [b for b in bodies.list_bodies(doc) if bodies.is_shown(b)]
    source = marked.get("source")
    for n, body in enumerate(shown):
        try:
            if body.Shape.isNull() or not body.Shape.Faces:
                continue
            shape = bodies.global_shape(body)
        except Exception:
            continue
        color = render_core.BODY_COLORS[n % len(render_core.BODY_COLORS)]
        tol = _tolerance(shape)
        mark_here = source is not None and (source is body or getattr(body, "Tip", None) is source)
        for i, face in enumerate(shape.Faces, start=1):
            try:
                points, tris = face.tessellate(tol)
            except Exception:
                continue
            hot = mark_here and ("Face%d" % i) in marked["faces"]
            meshes.append(
                {
                    "points": [(p.x, p.y, p.z) for p in points],
                    "triangles": tris,
                    "color": render_core.HIGHLIGHT if hot else color,
                }
            )
        if edges or mark_here:
            for i, edge in enumerate(shape.Edges, start=1):
                hot = mark_here and ("Edge%d" % i) in marked["edges"]
                if not edges and not hot:
                    continue
                try:
                    points = edge.discretize(Deflection=tol)
                except Exception:
                    continue
                lines.append(
                    {
                        "points": [(p.x, p.y, p.z) for p in points],
                        "color": render_core.HIGHLIGHT if hot else render_core.EDGE,
                        "width": 3 if hot else 1,
                    }
                )
    if source is not None and not any(
        source is b or getattr(b, "Tip", None) is source for b in shown
    ):  # an earlier step (not what the body shows now): its marked faces / edges drawn alone
        shape = marked["shape"]
        tol = _tolerance(shape)
        for name in sorted(marked["faces"]):
            points, tris = shape.getElement(name).tessellate(tol)
            meshes.append(
                {
                    "points": [(p.x, p.y, p.z) for p in points],
                    "triangles": tris,
                    "color": render_core.HIGHLIGHT,
                }
            )
        for name in sorted(marked["edges"]):
            points = shape.getElement(name).discretize(Deflection=tol)
            lines.append(
                {
                    "points": [(p.x, p.y, p.z) for p in points],
                    "color": render_core.HIGHLIGHT,
                    "width": 3,
                    "on_top": True,
                }
            )
    for obj in doc.Objects:
        if obj.TypeId != "Sketcher::SketchObject" or not _sketch_shown(obj):
            continue
        try:
            wire_shape = bodies.global_shape(obj)
            tol = _tolerance(wire_shape)
            for edge in wire_shape.Edges:
                points = edge.discretize(Deflection=tol)
                lines.append(
                    {"points": [(p.x, p.y, p.z) for p in points], "color": render_core.SKETCH}
                )
        except Exception:
            continue
    return meshes, lines


def _sketch_shown(sketch):
    """Whether the window shows the sketch. Without the window nothing hides the sketches
    a feature used (the window's PartDesign does), so those count as hidden."""
    import FreeCAD as App

    from ... import bodies

    if App.GuiUp:
        return bodies.is_shown(sketch)
    if not getattr(sketch, "Visibility", True):
        return False
    return not any(o.TypeId not in ("PartDesign::Body", "App::Part") for o in sketch.InList)


def _software(ctx, doc, args, marked):
    from .. import render_core

    meshes, lines = scene(ctx, doc, marked, bool(args.get("edges", True)))
    if not meshes and not lines:
        raise UserError("There is nothing shown to draw: the design has no visible body or sketch.")
    try:
        png, info = render_core.render(
            meshes,
            lines,
            int(args.get("width", 800)),
            int(args.get("height", 600)),
            args.get("view", "iso"),
            args.get("direction"),
        )
    except render_core.RenderError as exc:
        raise UserError(str(exc))
    return base64.b64encode(png).decode("ascii"), info


def _window(ctx, doc, args, marked):
    """The picture from SciForge's own 3D view (the person's camera is put back after)."""
    from .view_actions import ORIENTATIONS

    view = ctx.host.view(doc)
    if view is None:
        raise UserError("There is no 3D view to take the picture from.")
    try:
        camera = view.getCamera()
    except Exception:
        camera = None
    selection = ctx.host.push_highlight(doc, marked)
    try:
        if args.get("direction"):
            d = args["direction"]
            view.setViewDirection((-d[0], -d[1], -d[2]))
        else:
            getattr(view, ORIENTATIONS[args.get("view", "iso")])()
        if args.get("fit", True):
            view.fitAll()
        width, height = int(args.get("width", 800)), int(args.get("height", 600))
        data = ctx.host.screenshot(doc, width, height)
    finally:
        ctx.host.pop_highlight(doc, selection)
        if camera is not None:
            try:
                view.setCamera(camera)
            except Exception:
                pass
    return data, {
        "width": width,
        "height": height,
        "view": args.get("direction") or args.get("view", "iso"),
    }


@action("render")
def render(ctx, args):
    doc = ctx.need_doc()
    marked = _highlights(ctx, args.get("highlight"))
    renderer = args.get("renderer", "auto")
    if renderer == "window" and not ctx.host.gui:
        raise UserError(
            "renderer window needs the SciForge window, and SciForge is running without one: "
            "use renderer software (or auto)."
        )
    use_window = renderer == "window" or (renderer == "auto" and ctx.host.view(doc) is not None)
    if use_window:
        data, info = _window(ctx, doc, args, marked)
        info["renderer"] = "window"
    else:
        data, info = _software(ctx, doc, args, marked)
        info["renderer"] = "software"
    what = info["view"] if isinstance(info["view"], str) else "direction %s" % info["view"]
    text = "A %d x %d picture of %s (%s view, %s renderer)" % (
        info["width"],
        info["height"],
        doc.Label,
        what,
        info["renderer"],
    )
    if marked["words"]:
        text += "; in orange: %s" % "; ".join(marked["words"])
    if info.get("mm_per_pixel"):
        text += "; 1 pixel = %.4g mm" % info["mm_per_pixel"]
    return bridge_core.result(text + ".", data)


# -- diff_design ------------------------------------------------------------------------------
_BODY_KEYS = ("volume_mm3", "area_mm2", "solids", "faces", "edges", "vertices")


def _num_change(before, after):
    out = {"before": before, "after": after}
    try:
        out["change"] = _r(after - before)
    except Exception:
        pass
    return out


def _body_changes(old, new):
    changes = {}
    for key in _BODY_KEYS:
        a, b = old.get(key), new.get(key)
        if a is None and b is None:
            continue
        if a is None or b is None or abs(float(a) - float(b)) > 1e-6 * max(1.0, abs(float(a))):
            changes[key] = _num_change(a, b)
    a, b = (old.get("bbox_mm") or {}).get("size"), (new.get("bbox_mm") or {}).get("size")
    if a != b:
        changes["size_mm"] = {"before": a, "after": b}
    if old.get("solid") != new.get("solid"):
        changes["solid"] = {"before": old.get("solid"), "after": new.get("solid")}
    return changes


def compare(old, new):
    """What differs between two records (record())."""
    out = {"bodies": {"added": [], "removed": [], "changed": []}}
    for name, row in new["bodies"].items():
        if name not in old["bodies"]:
            out["bodies"]["added"].append(row)
        else:
            changes = _body_changes(old["bodies"][name], row)
            if changes:
                out["bodies"]["changed"].append({"id": name, "label": row["label"], **changes})
    for name, row in old["bodies"].items():
        if name not in new["bodies"]:
            out["bodies"]["removed"].append({"id": name, "label": row.get("label")})
    steps = {"added": [], "removed": [], "changed": []}
    for name in new["order"]:
        row = new["steps"][name]
        if name not in old["steps"]:
            steps["added"].append({"id": name, "name": row["name"], "kind": row["kind"]})
            continue
        before = old["steps"][name]
        changes = {}
        for key in ("name", "state", "status", "message", "suppressed", "index"):
            if before.get(key) != row.get(key):
                changes[key] = {"before": before.get(key), "after": row.get(key)}
        values = {}
        for key in set(before.get("values", {})) | set(row.get("values", {})):
            a, b = before.get("values", {}).get(key), row.get("values", {}).get(key)
            if a != b:
                values[key] = {"before": a, "after": b}
        if values:
            changes["values"] = values
        if changes:
            steps["changed"].append({"id": name, "name": row["name"], **changes})
    for name in old["order"]:
        if name not in new["steps"]:
            row = old["steps"][name]
            steps["removed"].append({"id": name, "name": row["name"], "kind": row["kind"]})
    out["steps"] = steps
    params = {"added": [], "removed": [], "changed": []}
    for name, row in new["parameters"].items():
        if name not in old["parameters"]:
            params["added"].append(row)
        elif old["parameters"][name] != row:
            params["changed"].append(
                {
                    "name": name,
                    "before": {k: old["parameters"][name].get(k) for k in ("value", "expression")},
                    "after": {k: row.get(k) for k in ("value", "expression")},
                }
            )
    for name in old["parameters"]:
        if name not in new["parameters"]:
            params["removed"].append({"name": name})
    out["parameters"] = params
    return out


def _words(diff):
    parts = []
    b, s, p = diff["bodies"], diff["steps"], diff["parameters"]
    if s["added"]:
        parts.append(
            "steps added: %s" % ", ".join("%s (%s)" % (x["name"], x["id"]) for x in s["added"])
        )
    if s["removed"]:
        parts.append("steps removed: %s" % ", ".join(x["id"] for x in s["removed"]))
    if s["changed"]:
        parts.append("steps changed: %s" % ", ".join(x["id"] for x in s["changed"]))
    if b["added"]:
        parts.append("bodies added: %s" % ", ".join(x["id"] for x in b["added"]))
    if b["removed"]:
        parts.append("bodies removed: %s" % ", ".join(x["id"] for x in b["removed"]))
    for row in b["changed"]:
        if "volume_mm3" in row:
            v = row["volume_mm3"]
            parts.append(
                "%s volume %.6g -> %.6g mm3" % (row["label"], v["before"] or 0, v["after"] or 0)
            )
        else:
            parts.append(
                "%s changed (%s)"
                % (row["label"], ", ".join(k for k in row if k not in ("id", "label")))
            )
    if p["added"] or p["removed"] or p["changed"]:
        parts.append(
            "parameters: %d added, %d removed, %d changed"
            % (len(p["added"]), len(p["removed"]), len(p["changed"]))
        )
    return "; ".join(parts) if parts else "nothing changed"


def _since_step(ctx, doc, ident):
    from ... import bodies, timeline_ops

    try:
        obj = ctx.resolve(ident, "step")
    except UserError:
        raise UserError(
            "There is no step or snapshot called %r: give a snapshot id that inspect_design "
            'answered ("S1"), "last_change", or a step id from get_timeline.' % ident
        )
    body = obj if bodies.is_body(obj) else bodies.body_of(obj)
    if body is None:
        raise UserError("%s is not in a body: give a step of a body, or a snapshot id." % ident)
    try:
        old_shape = bodies.global_shape(obj)
    except Exception:
        old_shape = None
    if old_shape is None or old_shape.isNull() or not old_shape.Faces:
        raise UserError(
            "%s has no solid of its own (a sketch or a plane?): give a step that makes or "
            "changes a solid, or a snapshot id." % ident
        )
    before = body_row(body, full=False)
    before.update(_shape_counts(old_shape))
    before.update(
        solid=bool(old_shape.Solids),
        volume_mm3=_r(old_shape.Volume),
        area_mm2=_r(old_shape.Area),
        bbox_mm=_bbox(old_shape.BoundBox),
    )
    now = body_row(body, full=False)
    later = []
    try:
        tl = timeline_ops.timeline(doc)
        names = tl.names()
        if obj.Name in names:
            start = names.index(obj.Name)
            for item in tl.items[start + 1 :]:
                if item.body == body.Name:
                    later.append(
                        {
                            "id": item.name,
                            "name": item.display,
                            "kind": item.kind,
                            "state": item.state,
                            "status": item.status,
                        }
                    )
    except Exception:
        pass
    changes = _body_changes(before, now)
    out = {
        "since": obj.Name,
        "body": body.Name,
        "later_steps": later,
        "after_step": {k: before.get(k) for k in _BODY_KEYS + ("bbox_mm",)},
        "now": {k: now.get(k) for k in _BODY_KEYS + ("bbox_mm",)},
        "changes": changes,
    }
    text = "Since %s, %d later step(s) in %s" % (obj.Name, len(later), body.Label)
    if "volume_mm3" in changes:
        v = changes["volume_mm3"]
        text += "; volume %.6g -> %.6g mm3" % (v["before"], v["after"])
    elif not changes:
        text += "; the solid is the same"
    return json_result(out, text + ".", compact=True)


@action("diff_design")
def diff_design(ctx, args):
    doc = ctx.need_doc()
    since = args["since"]
    if since == "last_change":
        old = _LAST.get(doc.Name)
        if old is None:
            raise UserError(
                "No AI change was made to this design in this session yet, so there is no "
                "last_change: call inspect_design for a snapshot id and diff since it later."
            )
        label = "the last change"
    elif since in _SNAPSHOTS.get(doc.Name, {}):
        old = _SNAPSHOTS[doc.Name][since]
        label = since
    elif since[:1] == "S" and since[1:].isdigit():
        raise UserError(
            "There is no snapshot %s of this design (snapshots last for this session; the "
            "newest %d are kept): call inspect_design for a new one." % (since, MAX_SNAPSHOTS)
        )
    else:
        return _since_step(ctx, doc, since)
    diff = compare(old, record(doc))
    diff["since"] = since
    return json_result(diff, "Since %s: %s." % (label, _words(diff)), compact=True)
