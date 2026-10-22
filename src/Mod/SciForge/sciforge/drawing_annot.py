# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dimension text and the drawing's annotations, on TechDraw (no Qt: the commands are in
drawing_annot_ui.py, the shapes and texts in drawing_annot_core.py / drawing_dims_core.py).

Dimensions: Fusion's Dimension dialog settings (override, text before / after, precision,
tolerances, ISO fits, basic, reference) are kept as JSON on the TechDraw dimension
(SciForgeDimSettings) and written into TechDraw's own text properties: the main text,
the two small stacked tolerance texts and the frame of a basic dimension. A dimension
without settings keeps TechDraw's own formatting.

Annotations: leaders with text, feature control frames, datum identifiers, surface
texture symbols, ordinate dimensions and arc lengths. Each one is a TechDraw
DrawViewSymbol (SciForgeType "DrawingAnnotation") whose SVG is drawn from its settings
(SciForgeAnno, JSON). It is attached to a point of a view's edge (an "anchor": the
element's name, what kind of element it is and its shape, to find it again when the
design changes) and its text or frame sits at an offset from the view, so it moves with
the view and follows the edge after design changes.
"""

import json
import math

import FreeCAD as App

from . import drawing
from . import drawing_annot_core as ac
from . import drawing_dims_core as dc
from . import log, warn

V = App.Vector
ANNOT_TYPE = "DrawingAnnotation"
DIM_SETTINGS = "SciForgeDimSettings"
KIND_LABELS = {
    "leader": "Leader",
    "fcf": "Feature Control Frame",
    "datum": "Datum",
    "texture": "Surface Texture",
    "ordinate": "Ordinate Dimension",
    "arc": "Arc Length",
}
DXF_LAYERS = {
    "leader": "TEXT",
    "fcf": "SYMBOLS",
    "datum": "SYMBOLS",
    "texture": "SYMBOLS",
    "ordinate": "DIMENSIONS",
    "arc": "DIMENSIONS",
}


# ------------------------------------------------------------------ dimension text
def dimension_kind(dim):
    """Distance, Diameter, Radius or Angle (what drawing_dims_core formats)."""
    dim_type = drawing._get(dim, "Type", "Distance")
    if dim_type in ("Angle", "Angle3Pt"):
        return "Angle"
    if dim_type in ("Diameter", "Radius"):
        return dim_type
    return "Distance"


def dimension_settings(dim):
    return dc.settings(drawing._get(dim, DIM_SETTINGS, "") or "")


def dimension_texts(dim, data=None):
    """{"main", "over", "under", "framed", "lines"} the dimension shows (None when its
    value is not known yet)."""
    value = drawing.dimension_value(dim)
    if value is None:
        return None
    page = drawing.page_of(dim)
    units = drawing.units_of(page) if page is not None else "mm"
    return dc.texts(
        value, dimension_kind(dim), units, dimension_settings(dim) if data is None else data
    )


def set_dimension_settings(dim, data):
    """Store a dimension's Dimension dialog settings and show them."""
    drawing._add(dim, "App::PropertyString", DIM_SETTINGS, dc.to_json(data))
    apply_dimension_text(dim)


def _set(obj, prop, value):
    if prop not in obj.PropertiesList:
        return False
    current = getattr(obj, prop)
    if current == value:
        return False
    setattr(obj, prop, value)
    return True


def apply_dimension_text(dim):
    """TechDraw's text properties from the settings. A dimension without settings in the
    drawing's own units keeps TechDraw's formatting; any other one writes its text (it
    follows the value on every refresh of the drawing). True when something changed."""
    page = drawing.page_of(dim)
    if page is None:
        return False
    units = drawing.units_of(page)
    data = dimension_settings(dim)
    kind = dimension_kind(dim)
    native = kind == "Angle" or drawing.schema_length_unit() == units
    changed = False
    if dc.is_default(data) and native:
        if drawing._get(dim, "Arbitrary", False) and drawing._get(dim, "SciForgeOwnText", False):
            changed |= _set(dim, "Arbitrary", False)
            changed |= _set(
                dim,
                "FormatSpec",
                drawing.core.dimension_format(units, drawing.standard_of(page), dim.Type),
            )
        changed |= _set(dim, "ArbitraryTolerances", False)
        changed |= _set(dim, "TheoreticalExact", False)
        return changed
    texts = dimension_texts(dim, data)
    if texts is None:
        return changed
    changed |= _set(dim, "Arbitrary", True)
    changed |= _set(dim, "FormatSpec", texts["main"])
    tolerances = bool(texts["over"] or texts["under"])
    changed |= _set(dim, "EqualTolerance", False)
    changed |= _set(dim, "ArbitraryTolerances", tolerances)
    if tolerances:
        changed |= _set(dim, "FormatSpecOverTolerance", texts["over"] or "0")
        changed |= _set(dim, "FormatSpecUnderTolerance", texts["under"] or "0")
    changed |= _set(dim, "TheoreticalExact", bool(texts["framed"]))
    drawing._add(dim, "App::PropertyBool", "SciForgeOwnText", True)
    return changed


def refresh_dimension_texts(page):
    changed = False
    for dim in drawing.annotations(page):
        if dim.TypeId != drawing.DIMENSION:
            continue
        try:
            changed |= apply_dimension_text(dim)
        except Exception as exc:
            warn("dimension %s: %s" % (dim.Label, exc))
    return changed


def dimension_one_line(dim):
    texts = dimension_texts(dim)
    return dc.one_line(texts) if texts is not None else ""


# ------------------------------------------------------------------ elements of a view
def _line_sig(info):
    return [info["p1"][0], info["p1"][1], info["p2"][0], info["p2"][1]]


def elements(view):
    """[(name, info)] of every edge and vertex of a view (drawing.edge_info), unscaled
    view coordinates."""
    found = []
    i = 0
    while i < 5000:
        try:
            edge = view.getEdgeBySelection("Edge%d" % i)
        except Exception:
            break
        if edge is None:
            break
        info = drawing.edge_info(view, "Edge%d" % i)
        if info is not None:
            if info["kind"] == "arc":
                a = edge.valueAt(edge.FirstParameter)
                b = edge.valueAt(edge.LastParameter)
                c = info["center"]
                info["a0"] = math.degrees(math.atan2(a.y - c[1], a.x - c[0]))
                info["a1"] = math.degrees(math.atan2(b.y - c[1], b.x - c[0]))
                m = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
                info["am"] = math.degrees(math.atan2(m.y - c[1], m.x - c[0]))
            found.append(("Edge%d" % i, info))
        i += 1
    i = 0
    while i < 5000:
        try:
            vertex = view.getVertexBySelection("Vertex%d" % i)
        except Exception:
            break
        if vertex is None:
            break
        p = vertex.Point
        found.append(("Vertex%d" % i, {"kind": "vertex", "point": (p.x, p.y)}))
        i += 1
    return found


def _sig(info):
    kind = info["kind"]
    if kind == "line":
        return _line_sig(info)
    if kind in ("circle", "arc"):
        sig = [info["center"][0], info["center"][1], info["radius"]]
        if kind == "arc":
            sig += [info.get("a0", 0.0), info.get("a1", 0.0), info.get("am", 0.0)]
        return sig
    if kind == "vertex":
        return [info["point"][0], info["point"][1]]
    return []


def make_anchor(view, name, local):
    """An anchor on the element `name` of a view, at the point of it nearest to `local`
    (or a free point of the view when name is None)."""
    if not name:
        return {"ref": None, "kind": "point", "local": [local[0], local[1]]}
    info = drawing.edge_info(view, name)
    if info is None:
        return {"ref": None, "kind": "point", "local": [local[0], local[1]]}
    if info["kind"] in ("arc",):
        for elem_name, elem in elements(view):
            if elem_name == name:
                info = elem
                break
    anchor = {"ref": name, "kind": info["kind"], "sig": _sig(info)}
    if info["kind"] == "line":
        (x1, y1), (x2, y2) = info["p1"], info["p2"]
        dx, dy = x2 - x1, y2 - y1
        length2 = dx * dx + dy * dy
        t = 0.5 if length2 < 1e-12 else ((local[0] - x1) * dx + (local[1] - y1) * dy) / length2
        anchor["t"] = max(0.0, min(1.0, t))
    elif info["kind"] in ("circle", "arc"):
        c = info["center"]
        anchor["angle"] = math.degrees(math.atan2(local[1] - c[1], local[0] - c[0]))
    anchor["local"] = list(anchor_point(anchor) or local)
    return anchor


def anchor_point(anchor):
    """The anchor's point (unscaled view coordinates) from its element's shape."""
    kind = anchor.get("kind")
    sig = anchor.get("sig") or []
    if kind == "line" and len(sig) == 4:
        t = anchor.get("t", 0.5)
        return (sig[0] + (sig[2] - sig[0]) * t, sig[1] + (sig[3] - sig[1]) * t)
    if kind in ("circle", "arc") and len(sig) >= 3:
        a = math.radians(anchor.get("angle", 0.0))
        return (sig[0] + sig[2] * math.cos(a), sig[1] + sig[2] * math.sin(a))
    if kind == "vertex" and len(sig) == 2:
        return (sig[0], sig[1])
    local = anchor.get("local")
    return tuple(local) if local else None


def centre_point(anchor):
    """The point an ordinate takes from an anchor: a circle's centre, a vertex, a line's
    nearer end."""
    kind = anchor.get("kind")
    sig = anchor.get("sig") or []
    if kind in ("circle", "arc") and len(sig) >= 3:
        return (sig[0], sig[1])
    if kind == "line" and len(sig) == 4:
        return (sig[0], sig[1]) if anchor.get("t", 0.5) <= 0.5 else (sig[2], sig[3])
    return anchor_point(anchor)


def _score(kind, old, new):
    """How unlike two elements of one kind are (None: too unlike to be the same)."""
    if kind == "vertex":
        return math.hypot(new[0] - old[0], new[1] - old[1])
    if kind in ("circle", "arc"):
        dr = abs(new[2] - old[2])
        if dr > max(1e-3, 0.5 * old[2]):
            return None
        return math.hypot(new[0] - old[0], new[1] - old[1]) + 10.0 * dr
    if kind == "line":
        da = math.atan2(old[3] - old[1], old[2] - old[0])
        db = math.atan2(new[3] - new[1], new[2] - new[0])
        diff = abs((da - db + math.pi / 2.0) % math.pi - math.pi / 2.0)
        if diff > math.radians(2.0):
            return None
        la = math.hypot(old[2] - old[0], old[3] - old[1])
        lb = math.hypot(new[2] - new[0], new[3] - new[1])
        if la > 1e-9 and not (0.5 <= lb / la <= 2.0):
            return None
        mid_a = ((old[0] + old[2]) / 2.0, (old[1] + old[3]) / 2.0)
        mid_b = ((new[0] + new[2]) / 2.0, (new[1] + new[3]) / 2.0)
        return math.hypot(mid_b[0] - mid_a[0], mid_b[1] - mid_a[1]) + abs(lb - la)
    return None


def _same_sig(a, b, tol=1e-4):
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def resolve_anchor(anchor, elems):
    """The anchor on the view's elements as they are now (`elems`: elements(view)): the
    same element if its name still shows it, else the most alike element of that kind.
    Returns (anchor, moved)."""
    kind = anchor.get("kind")
    if kind == "point" or not anchor.get("ref"):
        return anchor, False
    old = anchor.get("sig") or []
    by_name = dict(elems)
    current = by_name.get(anchor["ref"])
    if current is not None and current["kind"] == kind and _same_sig(_sig(current), old):
        return anchor, False
    best = None
    for name, info in elems:
        if info["kind"] != kind:
            continue
        score = _score(kind, old, _sig(info))
        if score is None:
            continue
        if best is None or score < best[0]:
            best = (score, name, info)
    if best is None:
        return anchor, False
    new = dict(anchor)
    new["ref"] = best[1]
    new["sig"] = _sig(best[2])
    point = anchor_point(new)
    if point is not None:
        new["local"] = [point[0], point[1]]
    return new, not _same_sig(new["sig"], old)


# ------------------------------------------------------------------ annotation objects
def is_annotation(obj):
    return drawing.kind(obj) == ANNOT_TYPE


def annotation_data(obj):
    try:
        return json.loads(drawing._get(obj, "SciForgeAnno", "") or "{}")
    except ValueError:
        return {}


def annotation_kind(obj):
    return annotation_data(obj).get("kind", "")


def annotation_view(obj, data=None):
    data = data if data is not None else annotation_data(obj)
    name = data.get("view")
    view = obj.Document.getObject(name) if name else None
    return view if drawing.alive(view) else None


def annotations_of(page):
    return [o for o in drawing.annotations(page) if is_annotation(o)]


def _view_origin(view):
    return drawing.view_position(view) if view is not None else (0.0, 0.0)


def page_point(view, anchor):
    """The page point of an anchor of a view."""
    if view is None or not anchor:
        return None
    local = anchor.get("local") or anchor_point(anchor)
    if local is None:
        return None
    return drawing.local_to_page(view, local)


def _tangent_on_page(view, anchor):
    if anchor.get("kind") != "line" or view is None:
        return None
    sig = anchor.get("sig") or []
    if len(sig) != 4:
        return None
    a = drawing.local_to_page(view, (sig[0], sig[1]))
    b = drawing.local_to_page(view, (sig[2], sig[3]))
    return (b[0] - a[0], b[1] - a[1])


def value_text(page, value_mm):
    units = drawing.units_of(page) if page is not None else "mm"
    return dc.number(value_mm, None, units)


def prims_of(obj, data=None, page=None, spoken=False):
    """The annotation's shapes on the page (drawing_annot_core primitives); spoken=True
    adds the text a drawn symbol stands for (a PDF's searchable text)."""
    data = data if data is not None else annotation_data(obj)
    page = page if page is not None else drawing.page_of(obj)
    standard = drawing.standard_of(page) if page is not None else "ISO"
    view = annotation_view(obj, data)
    base = _view_origin(view)
    off = data.get("off") or [0.0, 0.0]
    place = (base[0] + off[0], base[1] + off[1])
    anchor = data.get("anchor")
    anchor_pt = page_point(view, anchor) if anchor else None
    kind = data.get("kind")
    if kind == "leader":
        if anchor_pt is None:
            return ac.text_lines(data.get("lines") or [""], place[0], place[1])
        return ac.leader(anchor_pt, place, data.get("lines") or [""])
    if kind == "fcf":
        prims, _box = ac.feature_control(anchor_pt, place, data.get("fcf") or {}, spoken=spoken)
        return prims
    if kind == "datum":
        return ac.datum_identifier(
            anchor_pt or (place[0], place[1] - 10.0),
            place,
            data.get("letter", "A"),
            tangent=_tangent_on_page(view, anchor) if anchor else None,
        )
    if kind == "texture":
        return ac.surface_texture(anchor_pt, place, data.get("texture") or {}, standard)
    if kind == "ordinate":
        origin = data.get("origin")
        if view is None or not origin or not anchor:
            return []
        s = drawing.scale_of(view) or 1.0
        o = drawing.local_to_page(view, centre_point(origin))
        f = drawing.local_to_page(view, centre_point(anchor))
        axis = data.get("axis", "x")
        value = ac.ordinate_value(o, f, axis, s)
        return ac.ordinate(f, place, axis, value_text(page, value), standard)
    if kind == "arc":
        if view is None or not anchor:
            return []
        sig = anchor.get("sig") or []
        if len(sig) < 6:
            return []
        s = drawing.scale_of(view) or 1.0
        centre = drawing.local_to_page(view, (sig[0], sig[1]))
        a0, a1, am = sig[3], sig[4], sig[5]
        # counter-clockwise from a0 must pass through the middle
        if (am - a0) % 360.0 > (a1 - a0) % 360.0:
            a0, a1 = a1, a0
        rotation = drawing._value(getattr(view, "Rotation", 0.0))
        sweep = math.radians((a1 - a0) % 360.0)
        length = sig[2] * sweep
        return ac.arc_length(
            centre, sig[2] * s, a0 + rotation, a1 + rotation, place, value_text(page, length)
        )
    return []


def render(obj, data=None):
    """Draw the annotation: its SVG and its place on the sheet. True when it changed."""
    data = data if data is not None else annotation_data(obj)
    prims = prims_of(obj, data)
    if not prims:
        return False
    svg, centre = ac.svg(prims)
    changed = False
    if obj.Symbol != svg:
        obj.Symbol = svg
        changed = True
    if (
        abs(drawing._value(obj.X) - centre[0]) > 1e-6
        or abs(drawing._value(obj.Y) - centre[1]) > 1e-6
    ):
        obj.X = centre[0]
        obj.Y = centre[1]
        changed = True
    rendered = list(drawing._get(obj, "SciForgeRendered", []) or [])
    if rendered != [centre[0], centre[1]]:
        drawing._add(obj, "App::PropertyFloatList", "SciForgeRendered", [centre[0], centre[1]])
    return changed


def save(obj, data):
    text = json.dumps(data, sort_keys=True)
    if drawing._get(obj, "SciForgeAnno", "") != text:
        drawing._add(obj, "App::PropertyString", "SciForgeAnno", text)
    if drawing._get(obj, "SciForgeAnnoKind", "") != data.get("kind", ""):
        drawing._add(obj, "App::PropertyString", "SciForgeAnnoKind", data.get("kind", ""))


def add_annotation(page, data, view=None):
    """A new annotation on a drawing's sheet (one TechDraw symbol)."""
    doc = page.Document
    data = dict(data)
    data["view"] = view.Name if view is not None else ""
    obj = doc.addObject(drawing.SYMBOL, "Annotation")
    drawing._mark(obj, ANNOT_TYPE)
    if view is not None:
        drawing._add(obj, "App::PropertyLink", "SciForgeView", view)
    save(obj, data)
    try:
        obj.ScaleType = "Custom"
        obj.Scale = 1.0
    except Exception:
        pass
    obj.Label = label_for(data)
    prims = prims_of(obj, data, page)
    svg, centre = ac.svg(prims) if prims else ("", (0.0, 0.0))
    obj.Symbol = svg
    drawing._add_to_page(page, obj, centre[0], centre[1])
    drawing._add(obj, "App::PropertyFloatList", "SciForgeRendered", [centre[0], centre[1]])
    log("%s on %s" % (obj.Label, page.Label))
    return obj


def label_for(data):
    kind = data.get("kind", "")
    if kind == "datum":
        return "Datum %s" % (data.get("letter") or "A")
    if kind == "leader":
        first = (data.get("lines") or [""])[0]
        return ("Leader: %s" % first) if first else "Leader"
    return KIND_LABELS.get(kind, "Annotation")


def update_annotation(obj, data):
    """New settings for an annotation (its dialog)."""
    save(obj, data)
    label = label_for(data)
    if obj.Label != label:
        obj.Label = label
    render(obj, data)


def follow(page, geometry=False):
    """Keep every annotation of a drawing where it belongs: with its view (always), on
    its edge after the design changed (geometry=True), and its text where a person
    dragged it. True when something changed."""
    changed = False
    cache = {}
    for obj in annotations_of(page):
        try:
            data = annotation_data(obj)
            view = annotation_view(obj, data)
            dirty = False
            # dragged on the sheet by a person: the text / frame moves, the arrow stays
            rendered = list(drawing._get(obj, "SciForgeRendered", []) or [])
            if len(rendered) == 2:
                dx = drawing._value(obj.X) - rendered[0]
                dy = drawing._value(obj.Y) - rendered[1]
                if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                    off = data.get("off") or [0.0, 0.0]
                    data["off"] = [off[0] + dx, off[1] + dy]
                    dirty = True
            if geometry and view is not None and drawing.has_geometry(view):
                elems = cache.get(view.Name)
                if elems is None:
                    elems = cache[view.Name] = elements(view)
                for key in ("anchor", "origin"):
                    if data.get(key):
                        new, _moved = resolve_anchor(data[key], elems)
                        if new != data[key]:
                            data[key] = new
                            dirty = True
            if dirty:
                save(obj, data)
            changed |= render(obj, data) or dirty
        except Exception as exc:
            warn("annotation %s: %s" % (getattr(obj, "Label", "?"), exc))
    return changed


def to_dxf(dxf, obj, spoken=False):
    data = annotation_data(obj)
    layer = DXF_LAYERS.get(data.get("kind"), "TEXT")
    dxf.layer("SYMBOLS", 5)
    ac.to_dxf(dxf, prims_of(obj, data, spoken=spoken), layer)


def describe(obj):
    """One line of what an annotation says (tests, logs)."""
    data = annotation_data(obj)
    kind = data.get("kind")
    if kind == "fcf":
        return ac.fcf_text(data.get("fcf") or {})
    if kind == "texture":
        return ac.surface_text(data.get("texture") or {})
    if kind == "datum":
        return data.get("letter", "")
    if kind == "leader":
        return "\n".join(data.get("lines") or [])
    return " ".join(ac.texts_of(prims_of(obj, data)))


def used_datum_letters(page):
    letters = []
    for sheet in _sheets_of(page):
        for obj in annotations_of(sheet):
            data = annotation_data(obj)
            if data.get("kind") == "datum" and data.get("letter"):
                letters.append(str(data["letter"]).upper())
    return letters


def next_datum_letter(page):
    used = set(used_datum_letters(page))
    for letter in drawing.core.LABEL_LETTERS:
        if letter not in used:
            return letter
    return "A"


def _sheets_of(page):
    try:
        from . import drawing_sheets

        return drawing_sheets.sheets(page)
    except Exception:
        return [page]


# ------------------------------------------------------------------ ordinate, baseline, chain
def add_ordinate(view, origin, anchor, axis, place):
    """An ordinate dimension of a view: the distance along `axis` ("x" or "y") from the
    origin anchor to the feature anchor, its text line through the page point `place`."""
    page = drawing.page_of(view)
    base = drawing.view_position(view)
    data = {
        "kind": "ordinate",
        "origin": origin,
        "anchor": anchor,
        "axis": axis,
        "off": [place[0] - base[0], place[1] - base[1]],
    }
    return add_annotation(page, data, view)


def ordinate_value(obj):
    """The distance an ordinate dimension shows, model mm."""
    data = annotation_data(obj)
    view = annotation_view(obj, data)
    if view is None:
        return None
    o = drawing.local_to_page(view, centre_point(data["origin"]))
    f = drawing.local_to_page(view, centre_point(data["anchor"]))
    return ac.ordinate_value(o, f, data.get("axis", "x"), drawing.scale_of(view))


def has_zero(page, view, origin, axis):
    """An ordinate set's origin already shows its 0 on this axis."""
    for obj in annotations_of(page):
        data = annotation_data(obj)
        if (
            data.get("kind") == "ordinate"
            and data.get("view") == view.Name
            and data.get("axis") == axis
            and data.get("origin")
            and data.get("anchor")
            and _same_point(centre_point(data["origin"]), centre_point(origin))
            and _same_point(centre_point(data["anchor"]), centre_point(origin))
        ):
            return True
    return False


def _same_point(a, b, tol=1e-4):
    return a is not None and b is not None and math.hypot(a[0] - b[0], a[1] - b[1]) <= tol


def vertex_at(view, point, tol=1e-3):
    """The name of the view vertex at a point (unscaled view coordinates)."""
    best = None
    for name, info in elements(view):
        if info["kind"] != "vertex":
            continue
        d = math.hypot(info["point"][0] - point[0], info["point"][1] - point[1])
        if d <= tol and (best is None or d < best[0]):
            best = (d, name)
    return best[1] if best else None


def dimension_points(dim):
    """(first, second) page points a linear dimension measures between."""
    view = dim.References2D[0][0] if dim.References2D else None
    if view is None:
        return None
    try:
        p, q = dim.getLinearPoints()
    except Exception:
        return None
    # (TechDraw gives them with y down, scaled, from the view's centre)
    x, y = drawing.view_position(view)
    return (x + p.x, y - p.y), (x + q.x, y - q.y)


def dimension_line_offset(dim):
    """Where the dimension line of a linear dimension is: its text's page point."""
    view = dim.References2D[0][0]
    x, y = drawing.view_position(view)
    return x + drawing._value(dim.X), y + drawing._value(dim.Y)


def base_reference(dim, near_page):
    """The vertex name (and its page point) of a linear dimension's end nearest to a page
    point: Fusion's Baseline and Chain start from the extension line clicked."""
    view = dim.References2D[0][0]
    points = dimension_points(dim)
    if points is None:
        return None, None
    end = min(points, key=lambda p: math.hypot(p[0] - near_page[0], p[1] - near_page[1]))
    local = drawing.page_to_local(view, end)
    name = vertex_at(view, local)
    return name, end


def stacked_position(dim_type, base_text_at, first, second, spacing, count):
    """Where the n-th stacked dimension's text goes (baseline: each next one `spacing`
    further out than the one before)."""
    mid_x = (first[0] + second[0]) / 2.0
    mid_y = (first[1] + second[1]) / 2.0
    if dim_type == "DistanceX":
        direction = 1.0 if base_text_at[1] >= min(first[1], second[1]) else -1.0
        return mid_x, base_text_at[1] + direction * spacing * count
    direction = 1.0 if base_text_at[0] >= min(first[0], second[0]) else -1.0
    return base_text_at[0] + direction * spacing * count, mid_y
