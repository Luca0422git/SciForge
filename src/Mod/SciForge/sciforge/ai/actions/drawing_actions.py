# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI actions for drawings, with SciForge's drawing code (drawing.py on FreeCAD's TechDraw,
the code behind DRAWING > CREATE / DIMENSIONS / TEXT / EXPORT): make a drawing with its base
and projected views, add section and detail views, dimensions (found from the view's
elements the way the Dimension command infers them from clicks), text, parts lists and
centre marks, read drawings, export PDF / DXF."""

import math
import os

from .. import bridge_core
from ..executor import UserError, json_result
from . import action

KIND_NAMES = {"projected": "ProjectedView", "base": "BaseView"}


def _pages(doc):
    return [o for o in doc.Objects if o.TypeId == "TechDraw::DrawPage"]


def _page(ctx, ident=None):
    from ... import drawing

    doc = ctx.need_doc()
    if ident:
        obj = ctx.resolve(ident, "drawing")
        page = obj if drawing.is_page(obj) else drawing.page_of(obj)
        if page is None:
            raise UserError("%r is not a drawing or a view of one." % ident)
        return page
    pages = _pages(doc)
    if not pages:
        raise UserError("The design has no drawing yet: call create_drawing first.")
    return pages[-1]


def _view(ctx, ident):
    from ... import drawing

    obj = ctx.resolve(ident, "drawing view")
    if not drawing.is_view(obj):
        raise UserError("%r is not a drawing view." % ident)
    return obj


def _sheet(page):
    from ... import drawing, drawing_core

    try:
        return drawing_core.sheet_size(drawing.standard_of(page), drawing.sheet_of(page))
    except Exception:
        return (420.0, 297.0)


def _offset(page, kind):
    """Where a projected view goes, from its parent (a fraction of the sheet)."""
    w, h = _sheet(page)
    dx = {"Right": 0.32, "Left": -0.28, "Top": 0.0, "Bottom": 0.0}.get(kind)
    dy = {"Top": 0.32, "Bottom": -0.32, "Right": 0.0, "Left": 0.0}.get(kind)
    if dx is None:  # an isometric corner view
        dx = 0.32 if "Right" in kind else -0.28
        dy = 0.3 if "Top" in kind else -0.3
    if page.ProjectionType == "First angle":  # ISO: the top view goes below the front
        dx, dy = -dx, -dy
    return dx * w, dy * h


def _recompute(page):
    try:
        page.Document.recompute()
    except Exception:
        pass


@action("create_drawing")
def create_drawing(ctx, args):
    from ... import drawing

    doc = ctx.need_doc()
    if args.get("bodies"):
        sources = [ctx.body_of(i) for i in args["bodies"]]
    else:
        sources = drawing.design_bodies(doc, visible_only=True) or drawing.design_bodies(doc)

    def work():
        try:
            page = drawing.create_drawing(
                doc,
                sources,
                standard=args.get("standard", "ISO"),
                units=args.get("units", "mm"),
                sheet=args.get("sheet"),
                title_block=args.get("title_block", True),
                label=args.get("label"),
            )
            w, h = _sheet(page)
            x, y = args.get("at", (0.32 * w, 0.58 * h))
            base = drawing.add_base_view(
                page,
                sources,
                x,
                y,
                args.get("base_view", "Front"),
                args.get("style"),
                args.get("scale"),
            )
            doc.recompute()
            views = [base]
            for kind in args.get("projected") or []:
                dx, dy = _offset(page, kind)
                views.append(drawing.add_projected(base, kind, x + dx, y + dy))
            doc.recompute()
            drawing.keep_aligned(page)
        except drawing.DrawingError as exc:
            raise UserError(str(exc))
        return page, views

    page, views = ctx.change(work)
    _recompute(page)
    return bridge_core.result(
        "Done: drawing %r (id %r) on a %s %s sheet, scale %s; views %s."
        % (
            page.Label,
            page.Name,
            drawing.standard_of(page),
            drawing.sheet_of(page),
            _scale_text(drawing.scale_of(views[0])),
            ", ".join("%s (%s)" % (v.Name, v.Label) for v in views),
        )
    )


def _scale_text(scale):
    try:
        if scale >= 1:
            return "%g:1" % scale
        return "1:%g" % round(1.0 / scale, 6)
    except Exception:
        return str(scale)


@action("add_drawing_view")
def add_drawing_view(ctx, args):
    from ... import drawing

    page = _page(ctx, args.get("drawing") or args.get("parent"))
    kind = args["kind"]
    w, h = _sheet(page)

    def work():
        try:
            if kind == "base":
                sources = drawing.design_bodies(page.Document, visible_only=True)
                x, y = args.get("at", (0.7 * w, 0.3 * h))
                view = drawing.add_base_view(
                    page, sources, x, y, args["orientation"], args.get("style"), args.get("scale")
                )
            else:
                parent = _view(ctx, args["parent"])
                px, py = drawing.view_position(parent)
                if kind == "projected":
                    dx, dy = _offset(page, args["direction"])
                    x, y = args.get("at", (px + dx, py + dy))
                    view = drawing.add_projected(parent, args["direction"], x, y)
                elif kind == "section":
                    (x1, y1), (x2, y2) = args["line"]
                    pos = args.get("at", (px + 0.3 * w, py))
                    side = drawing.page_to_local(parent, pos)
                    if "side" in args:  # 1: left of the line's direction, -1: right
                        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                        length = math.hypot(x2 - x1, y2 - y1) or 1.0
                        nx, ny = -(y2 - y1) / length, (x2 - x1) / length
                        s = 1.0 if int(args["side"]) >= 0 else -1.0
                        side = (mx + s * nx * 10.0, my + s * ny * 10.0)
                    view = drawing.add_section(
                        parent, (x1, y1), (x2, y2), side, pos, args.get("label"), args.get("scale")
                    )
                else:
                    pos = args.get("at", (px + 0.3 * w, py - 0.3 * h))
                    view = drawing.add_detail(
                        parent,
                        tuple(args["center"]),
                        args["radius"],
                        pos,
                        args.get("label"),
                        args.get("scale"),
                    )
            if args.get("style") and kind != "base":
                drawing.set_view_style(view, args["style"])
            page.Document.recompute()
            drawing.keep_aligned(page)
        except drawing.DrawingError as exc:
            raise UserError(str(exc))
        return view

    view = ctx.change(work)
    return bridge_core.result(
        "Done: %s view %r (id %r) on %s." % (kind, view.Label, view.Name, page.Label)
    )


# -- dimensions ---------------------------------------------------------------------------------
def view_elements(view, limit=3000):
    """[info] of every element of a view (drawing.edge_info: lines, circles, arcs)."""
    from ... import drawing

    found = []
    misses = 0
    for i in range(limit):
        info = drawing.edge_info(view, "Edge%d" % i)
        if info is None:
            misses += 1
            if misses > 3:
                break
            continue
        misses = 0
        found.append(info)
    return found


def _distance(info, point):
    px, py = point
    if info["kind"] == "line":
        (x1, y1), (x2, y2) = info["p1"], info["p2"]
        dx, dy = x2 - x1, y2 - y1
        length = dx * dx + dy * dy
        t = (
            0.0
            if length < 1e-12
            else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length))
        )
        return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
    if info["kind"] in ("circle", "arc"):
        cx, cy = info["center"]
        return abs(math.hypot(px - cx, py - cy) - info["radius"])
    if info["kind"] == "vertex":
        return math.hypot(px - info["point"][0], py - info["point"][1])
    return float("inf")


def _find(view, elements, pick, index):
    from ... import drawing

    kind = pick.get("kind")
    candidates = []
    if kind == "vertex":
        for i in range(3000):
            name = "Vertex%d" % i
            info = drawing.edge_info(view, name)
            if info is None:
                break
            candidates.append(info)
    else:
        candidates = [e for e in elements if kind in (None, e["kind"])]
    if "radius" in pick:
        candidates = [
            e
            for e in candidates
            if e["kind"] in ("circle", "arc") and abs(e["radius"] - pick["radius"]) < 1e-3
        ]
    if not candidates:
        raise UserError(
            "picks[%d]: the view has no such element (get_drawing with edges true "
            "lists them)." % index
        )
    if "near" in pick:
        return min(candidates, key=lambda e: _distance(e, pick["near"]))
    if len(candidates) > 1:
        raise UserError(
            "picks[%d]: %d elements match: give near [x, y] (get_drawing with "
            "edges true lists them)." % (index, len(candidates))
        )
    return candidates[0]


FORCED = {
    "linear": ("DistanceX", "DistanceY"),
    "aligned": ("Distance",),
    "radius": ("Radius",),
    "diameter": ("Diameter",),
    "angular": ("Angle", "Angle3Pt"),
}


@action("add_drawing_dimension")
def add_drawing_dimension(ctx, args):
    from ... import drawing, drawing_core

    view = _view(ctx, args["view"])
    page = drawing.page_of(view)
    elements = view_elements(view)
    infos = [_find(view, elements, pick, i) for i, pick in enumerate(args["picks"])]
    place = drawing.page_to_local(view, args["at"]) if "at" in args else None
    result = drawing_core.infer_dimension(infos, place)
    if "error" in result:
        raise UserError(result["error"])
    if "need" in result:
        raise UserError("One more element is needed for that dimension.")
    forced = args.get("type")
    if forced:
        allowed = FORCED[forced]
        if result["type"] not in allowed:
            swap = {
                ("linear", "Distance"): "DistanceX",
                ("aligned", "DistanceX"): "Distance",
                ("aligned", "DistanceY"): "Distance",
                ("radius", "Diameter"): "Radius",
                ("diameter", "Radius"): "Diameter",
            }.get((forced, result["type"]))
            if swap is None:
                raise UserError("That is not something a %s dimension measures." % forced)
            result["type"] = swap
    refs = []
    for i, info in enumerate(infos):
        if i in result.get("use_centers", []):
            centre = drawing.center_vertex(view, info["center"])
            if centre is None:
                raise UserError("The centre of that circle is not a point of the view.")
            refs.append(centre)
        else:
            refs.append(info["name"])
    if "at" in args:
        position = tuple(args["at"])
    else:
        x, y = drawing.view_position(view)
        hw, hh = drawing.view_extent(view)
        position = (x + hw + 8.0, y + hh + 8.0)

    def work():
        dim = drawing.add_dimension(view, refs, result["type"], position)
        page.Document.recompute()
        return dim

    dim = ctx.change(work)
    value = drawing.dimension_value(dim)
    return bridge_core.result(
        "Done: %s dimension %r on %s: %s."
        % (result["type"], dim.Name, view.Label, ("%.6g" % value) if value is not None else "?")
    )


@action("add_drawing_annotation")
def add_drawing_annotation(ctx, args):
    from ... import drawing

    page = _page(ctx, args.get("drawing") or args.get("view"))
    kind = args["kind"]
    w, h = _sheet(page)

    def work():
        try:
            if kind == "text":
                at = args.get("at", (0.1 * w, 0.12 * h))
                return drawing.add_text(
                    page, str(args["text"]).split("\n"), at, args.get("size", 3.5)
                )
            view = _view(ctx, args["view"])
            if kind == "parts_list":
                at = args.get("at", (0.62 * w, 0.95 * h))
                return drawing.add_parts_list(page, view, at, args.get("balloons", True))
            made = []
            for info in view_elements(view):
                if info["kind"] == "circle":
                    made.append(drawing.add_center_mark(view, info["name"]))
            if not made:
                raise UserError("%s shows no circle." % view.Label)
            return made[0]
        except drawing.DrawingError as exc:
            raise UserError(str(exc))

    made = ctx.change(work)
    _recompute(page)
    name = getattr(made, "Name", "")
    return bridge_core.result(
        "Done: %s on %s%s."
        % (kind.replace("_", " "), page.Label, (" (id %r)" % name) if name else "")
    )


@action("get_drawing")
def get_drawing(ctx, args):
    from ... import drawing

    doc = ctx.need_doc()
    pages = [_page(ctx, args["drawing"])] if args.get("drawing") else _pages(doc)
    out = []
    for page in pages:
        row = {
            "id": page.Name,
            "label": page.Label,
            "standard": drawing.standard_of(page),
            "sheet": drawing.sheet_of(page),
            "units": drawing.units_of(page),
            "sheet_size_mm": list(_sheet(page)),
            "title_block": drawing.title(page),
            "views": [],
            "annotations": [],
        }
        for view in drawing.all_views(page):
            x, y = drawing.view_position(view)
            hw, hh = drawing.view_extent(view)
            item = {
                "id": view.Name,
                "label": view.Label,
                "kind": drawing.kind(view) or view.TypeId.split("::")[-1],
                "orientation": drawing.orientation_of(view),
                "scale": drawing.scale_of(view),
                "at": [round(x, 3), round(y, 3)],
                "half_size_mm": [round(hw, 3), round(hh, 3)],
            }
            parent = drawing.parent_of(view)
            if parent is not None:
                item["parent"] = parent.Name
            if args.get("edges"):
                elements = []
                for info in view_elements(view):
                    info = dict(info)
                    for key in ("p1", "p2", "center", "point"):
                        if key in info:
                            info[key] = [round(v, 4) for v in info[key]]
                    if "radius" in info:
                        info["radius"] = round(info["radius"], 4)
                    elements.append(info)
                item["elements"] = elements
            row["views"].append(item)
        for obj in drawing.annotations(page):
            entry = {"id": obj.Name, "label": obj.Label, "type": obj.TypeId.split("::")[-1]}
            if obj.TypeId == drawing.DIMENSION:
                value = drawing.dimension_value(obj)
                entry["value"] = round(value, 6) if value is not None else None
                entry["dimension_type"] = obj.Type
            row["annotations"].append(entry)
        out.append(row)
    return json_result({"drawings": out})


@action("export_drawing")
def export_drawing(ctx, args):
    from ... import drawing, drawing_sheets

    page = _page(ctx, args.get("drawing"))
    path = ctx.full_path(args["path"])
    if os.path.exists(path) and not ctx.host.confirm_overwrite(path):
        raise UserError(ctx.host.refuse_overwrite_text(path))
    _recompute(page)
    try:
        if args["format"] == "pdf":
            if not ctx.host.gui:
                raise UserError(
                    "PDF export needs the SciForge window (TechDraw prints the "
                    "sheet itself); export DXF instead, or run SciForge."
                )
            written = drawing_sheets.export_pdf(page, path)
            which = "all"  # every sheet in one PDF
        else:
            written = drawing.export_dxf(page, path)
            which = "current"  # a DXF holds one sheet
    except drawing.DrawingError as exc:
        raise UserError(str(exc))
    from .document_actions import export_losses

    lost = export_losses(
        page.Document,
        page,
        "drawing_" + args["format"],
        os.path.basename(str(written or path)),
        which=which,
    )
    return bridge_core.result("Exported %s to %s.%s" % (page.Label, written or path, lost))
