# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI actions that read the design (never change it): get_design, measure, physical
properties, centre of mass, interference, section analysis, the material libraries, help
and the tool list. Built on SciForge's own INSPECT code (measure.py, analysis.py,
section.py, material.py)."""

from .. import bridge_core, catalog
from ..executor import UserError, json_result, state
from . import action


def _round(value, digits=6):
    try:
        return round(float(value), digits)
    except Exception:
        return value


def _bbox(box):
    return [_round(v) for v in (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax)]


@action("get_design")
def get_design(ctx, args):
    from ... import bodies, extrude, parameters

    doc = ctx.doc
    if doc is None:
        return bridge_core.result("No design is open. create_sketch starts a new one.")
    active = ctx.host.find_body(doc)
    info = {
        "design": doc.Label,
        "id": doc.Name,
        "file": doc.FileName or None,
        "units": "mm",
        "active_body": active.Name if active is not None else None,
        "bodies": [],
    }
    for body in bodies.solid_bodies(doc):
        shape = body.Shape
        row = {
            "id": body.Name,
            "label": body.Label,
            "volume_mm3": round(shape.Volume, 6),
            "area_mm2": round(shape.Area, 6),
            "bbox_mm": _bbox(shape.BoundBox),
            "solids": len(shape.Solids),
            "faces": len(shape.Faces),
            "tip": body.Tip.Name if body.Tip is not None else None,
        }
        try:
            from ... import material

            label, rho = material.effective(body)
            row["material"] = label
            if rho:
                row["mass_g"] = round(shape.Volume * rho * 1000.0, 6)
        except Exception:
            pass
        info["bodies"].append(row)
    others = [b for b in bodies.list_bodies(doc) if b not in bodies.solid_bodies(doc)]
    if others:
        info["empty_or_surface_bodies"] = [{"id": b.Name, "label": b.Label} for b in others]
    try:
        from ... import timeline_ops

        tl = timeline_ops.timeline(doc)
        items = tl.items
        info["history_marker"] = tl.marker
    except Exception:
        items = None
    info["timeline"] = []
    if items is not None:
        for item in items:
            obj = doc.getObject(item.name)
            row = {
                "id": item.name,
                "label": obj.Label if obj is not None else item.label,
                "type": obj.TypeId if obj is not None else item.type_id,
                "name": item.display,
                "state": item.state,
            }
            if item.suppressed:
                row["suppressed"] = True
            if item.status != "ok":
                row["status"] = item.status
                row["message"] = item.message
            info["timeline"].append(row)
    else:
        for obj in doc.Objects:
            info["timeline"].append({"id": obj.Name, "label": obj.Label, "type": obj.TypeId})
    info["parameters"] = []
    try:
        for row in parameters.user_parameters(doc):
            info["parameters"].append(
                {
                    "name": row["name"],
                    "value": _round(row["value"]),
                    "unit": row["unit"],
                    "expression": row["expression"],
                }
            )
    except Exception:
        pass
    info["sketches"] = []
    for obj in doc.Objects:
        if obj.TypeId == "Sketcher::SketchObject":
            try:
                areas = len(extrude.regions(obj))
            except Exception:
                areas = None
            info["sketches"].append({"id": obj.Name, "label": obj.Label, "closed_areas": areas})
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
    return json_result(info)


@action("measure")
def measure(ctx, args):
    from ... import measure as measuring
    from ..ops import inspect_ops

    builder = ctx.builder()
    a = inspect_ops._ref(builder, args["a"], "measure a")
    first = measuring.entity(*a)
    details = {"a": _entity_info(measuring, first)}
    if "b" not in args:
        rows = details["a"]["properties"]
        words = ", ".join(
            "%s %.6g %s" % (k.rsplit("_", 1)[0].replace("_", " "), v, k.rsplit("_", 1)[-1])
            for k, v in rows.items()
        )
        return json_result(
            details, "Measured a (%s): %s." % (details["a"]["kind"], words), compact=True
        )
    b = inspect_ops._ref(builder, args["b"], "measure b")
    second = measuring.entity(*b)
    found = measuring.relation(first, second)
    words = ["distance %.6g mm" % found["distance"]]
    if found.get("angle") is not None:
        words.append("angle %.6g degrees" % found["angle"])
    details["b"] = _entity_info(measuring, second)
    details.update(
        distance_mm=_round(found["distance"]),
        angle_deg=_round(found["angle"]) if found.get("angle") is not None else None,
        delta_mm=[_round(found["dx"]), _round(found["dy"]), _round(found["dz"])],
        nearest_points_mm=[[_round(c) for c in p] for p in found["points"]],
    )
    return json_result(details, "Measured: " + ", ".join(words) + ".", compact=True)


_UNITS = {"length": "mm", "area": "mm2", "volume": "mm3", "angle": "deg", "coordinate": "mm"}


def _entity_info(measuring, entity):
    """What one pick is, as Fusion's Measure shows it: {kind, properties {name_unit: value}}."""
    rows = {}
    for name, value, quantity in measuring.properties(entity):
        rows["%s_%s" % (name.lower().replace(" ", "_"), _UNITS.get(quantity, ""))] = _round(value)
    return {"kind": entity.kind, "properties": rows}


def _chosen_bodies(ctx, args):
    from ... import bodies

    doc = ctx.need_doc()
    if args.get("bodies"):
        return [ctx.body_of(ident) for ident in args["bodies"]]
    return bodies.solid_bodies(doc)


@action("physical_properties")
def physical_properties(ctx, args):
    from ... import bodies, material

    rows = []
    for body in _chosen_bodies(ctx, args):
        row = {"id": body.Name, "label": body.Label}
        if not bodies.has_solid(body):
            row["solid"] = False
            rows.append(row)
            continue
        shape = bodies.global_shape(body)
        label, rho = material.effective(body)
        row.update(
            volume_mm3=_round(shape.Volume),
            area_mm2=_round(shape.Area),
            material=label,
            density_kg_m3=_round(rho * 1e9, 3) if rho else None,
            mass_g=_round(shape.Volume * rho * 1000.0) if rho else None,
            center_of_mass_mm=_centre(shape),
            bbox_mm=_bbox(shape.BoundBox),
            faces=len(shape.Faces),
            edges=len(shape.Edges),
            solids=len(shape.Solids),
            valid=bool(shape.isValid()),
        )
        rows.append(row)
    if not rows:
        raise UserError("The design has no body.")
    return json_result({"bodies": rows})


def _centre(shape):
    from ... import analysis

    try:
        centre, _volume = analysis.center_of_mass([shape])
        return [_round(v) for v in centre]
    except Exception:
        return None


@action("center_of_mass")
def center_of_mass(ctx, args):
    from ... import analysis, bodies

    found = [b for b in _chosen_bodies(ctx, args) if bodies.has_solid(b)]
    if not found:
        raise UserError("There is no solid body to find the centre of mass of.")
    shapes = [bodies.global_shape(b) for b in found]
    densities = [analysis.density_of(b) for b in found]
    try:
        centre, volume = analysis.center_of_mass(shapes, densities)
    except analysis.AnalysisError as exc:
        raise UserError(str(exc))
    return json_result(
        {
            "center_of_mass_mm": [_round(v) for v in centre],
            "volume_mm3": _round(volume),
            "bodies": [b.Name for b in found],
            "weighted_by_material": None not in densities,
        },
        "Centre of mass at (%.6g, %.6g, %.6g) mm." % (centre.x, centre.y, centre.z),
    )


@action("interference")
def interference(ctx, args):
    from ... import analysis, bodies

    found = [b for b in _chosen_bodies(ctx, args) if bodies.has_solid(b)]
    if len(found) < 2:
        raise UserError(analysis.TOO_FEW)
    named = [(b.Label, bodies.global_shape(b)) for b in found]
    try:
        pairs = analysis.interference(named, bool(args.get("include_coincident")))
    except analysis.AnalysisError as exc:
        raise UserError(str(exc))
    rows = [{"body1": a, "body2": b, "volume_mm3": _round(v)} for a, b, v, _s in pairs]
    text = (
        "No bodies overlap."
        if not rows
        else "%d pair(s) overlap, %.6g mm3 in all."
        % (len(rows), sum(r["volume_mm3"] for r in rows))
    )
    return json_result({"pairs": rows}, text)


@action("section_analysis")
def section_analysis(ctx, args):
    from ... import bodies, section
    from ..ops import inspect_ops

    builder = ctx.builder()
    ref = inspect_ops._ref(builder, args["plane"], "section_analysis plane")
    try:
        place = section.cut_frame(
            ref,
            args.get("distance", 0.0),
            args.get("x_angle", 0.0),
            args.get("y_angle", 0.0),
            bool(args.get("flip", False)),
        )
    except section.SectionError as exc:
        raise UserError(str(exc))
    rows = []
    total_kept = total_cap = 0.0
    for body in bodies.solid_bodies(ctx.doc):
        shape = bodies.global_shape(body)
        kept = section.kept_volume(shape, place)
        cap = sum(f.Area for f in section.cap_faces(shape, place))
        total_kept += kept
        total_cap += cap
        rows.append(
            {"body": body.Name, "kept_volume_mm3": _round(kept), "cut_area_mm2": _round(cap)}
        )
    normal = section.normal_of(place)
    return json_result(
        {
            "plane_point_mm": [_round(v) for v in place.Base],
            "plane_normal": [_round(v) for v in normal],
            "bodies": rows,
        },
        "Section: %.6g mm3 kept, %.6g mm2 of cut faces." % (total_kept, total_cap),
    )


@action("list_materials")
def list_materials(ctx, args):
    from ... import appearance, material

    mats = []
    for row in material.entries():
        rho = None
        try:
            rho = material.density_of(row["key"])
        except Exception:
            pass
        mats.append(
            {
                "key": row["key"],
                "name": row["label"],
                "group": row["group"],
                "density_kg_m3": _round(rho * 1e9, 3) if rho else None,
            }
        )
    try:
        for row in material.user_entries():
            mats.append({"key": row["key"], "name": row.get("label", row["key"]), "group": "User"})
    except Exception:
        pass
    looks = [
        {"key": look["key"], "name": look["label"], "group": look["group"], "color": look["color"]}
        for look in appearance.library()
    ]
    return json_result({"materials": mats, "appearances": looks})


@action("get_help")
def get_help(ctx, args):
    return bridge_core.result(catalog.help_text(args.get("topic", "overview")))


@action("list_tools")
def list_tools(ctx, args):
    rows = catalog.tool_list(state(ctx.host), args.get("category"))
    return json_result({"tools": rows, "count": len(rows)})
