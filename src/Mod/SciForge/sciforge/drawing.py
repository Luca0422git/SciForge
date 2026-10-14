# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drawings of a design, on FreeCAD's TechDraw (no Qt: the commands live in drawing_ui.py).

A drawing is a TechDraw page (``TechDraw::DrawPage``, SciForgeType "Drawing") inside the
design's own file, so it always updates with the design and is saved with it (Fusion keeps
drawings as separate files linked to the design; see docs/sciforge/parity/drawings.md).

    page                    DrawPage  + SciForge's settings (standard, units, sheet...)
      Sheet                 DrawSVGTemplate: SciForge's own title block (drawing_core)
      base view             DrawViewPart (SciForgeType BaseView)
      projected views       DrawViewPart made from a parent view (SciForgeParent, Kind);
                            kept lined up with the parent by keep_aligned()
      section / detail      DrawViewSection / DrawViewDetail with BaseView = their parent
      broken view           DrawBrokenView standing in for the view it breaks
      dimensions            DrawViewDimension (References2D = the picked view edges)
      centre marks          cosmetic lines of the view (dash-dot), remembered on the view
      centre lines          TechDraw centre lines between two edges
      text                  DrawViewAnnotation
      parts list            DrawViewSymbol drawing drawing_core's table
      balloons              DrawViewBalloon

Coordinates: page millimetres, origin bottom left, y up. A view's own coordinates are
unscaled millimetres from the view's centre ("local"), y up.
"""

import datetime
import getpass
import json
import math
import os

import FreeCAD as App

from . import drawing_core as core
from . import log, warn

V = App.Vector
TYPE = "Drawing"
PAGE = "TechDraw::DrawPage"
GROUP = "TechDraw::DrawProjGroup"
ITEM = "TechDraw::DrawProjGroupItem"
PART_VIEW = "TechDraw::DrawViewPart"
SECTION = "TechDraw::DrawViewSection"
DETAIL = "TechDraw::DrawViewDetail"
COMPLEX = "TechDraw::DrawComplexSection"
BROKEN = "TechDraw::DrawBrokenView"
DIMENSION = "TechDraw::DrawViewDimension"
BALLOON = "TechDraw::DrawViewBalloon"
ANNOTATION = "TechDraw::DrawViewAnnotation"
SYMBOL = "TechDraw::DrawViewSymbol"
VIEW_TYPES = (ITEM, PART_VIEW, SECTION, COMPLEX, DETAIL, BROKEN)
LINE_DASHDOT = 4  # TechDraw line styles: 1 continuous, 2 dash, 3 dot, 4 dash-dot
CENTER_EXTENSION = 3.0  # mm on the paper a centre mark reaches past its circle
HATCH_FILE = "FCPAT.pat"  # TechDraw's own patterns
HATCH_NAME = "Diagonal4"  # 45 degree lines, like ANSI31
HATCH_SPACING = 4.0  # mm on the paper between the hatch lines (Diagonal4's spacing)


class DrawingError(ValueError):
    """A drawing operation that cannot be done, with a sentence that says why."""


# ------------------------------------------------------------------ small helpers
def _add(obj, kind, name, value=None):
    if name not in obj.PropertiesList:
        obj.addProperty(kind, name, "SciForge", "", 0)
    if value is not None:
        setattr(obj, name, value)


def _mark(obj, sciforge_type):
    """SciForge's name for the object; drawing objects are never timeline steps."""
    _add(obj, "App::PropertyString", "SciForgeType", sciforge_type)
    _add(obj, "App::PropertyBool", "SciForgeTimeline", False)


def _add_to_page(page, view, x=None, y=None):
    """Put a view on the page at (x, y): TechDraw's addView moves a new view to the
    middle of the sheet, so the position is set after it."""
    if x is None:
        x, y = _value(view.X), _value(view.Y)
    page.addView(view)
    view.X = x
    view.Y = y


def _get(obj, name, default=""):
    try:
        return getattr(obj, name)
    except Exception:
        return default


def same(a, b):
    """The same document object (compared by name: FreeCAD may hand out new wrappers)."""
    try:
        return a is not None and b is not None and a.Name == b.Name and a.Document == b.Document
    except Exception:
        return False


def alive(obj):
    try:
        return obj is not None and bool(obj.isAttachedToDocument())
    except Exception:
        return False


def kind(obj):
    return _get(obj, "SciForgeType", "") or ""


def is_page(obj):
    try:
        return obj is not None and obj.TypeId == PAGE
    except Exception:
        return False


def is_section(obj):
    """A section view: a straight cut (DrawViewSection) or one with several segments
    (DrawComplexSection)."""
    try:
        return obj.TypeId in (SECTION, COMPLEX)
    except Exception:
        return False


def is_view(obj):
    try:
        return obj.TypeId in VIEW_TYPES
    except Exception:
        return False


def all_pages(doc):
    """Every TechDraw page of the design: each sheet of each drawing."""
    if doc is None:
        return []
    return sorted([o for o in doc.Objects if o.TypeId == PAGE], key=lambda o: o.ID)


def drawings(doc):
    """The design's drawings (their first sheets), in the order they were made; further
    sheets of a drawing (drawing_sheets.py) are not drawings of their own."""
    return [p for p in all_pages(doc) if kind(p) != "DrawingSheet"]


def page_of(obj):
    """The drawing an object of it belongs to."""
    if obj is None:
        return None
    if is_page(obj):
        return obj
    # (not TechDraw's findParentPage: it crashes FreeCAD for a view on no page yet)
    for parent in getattr(obj, "InList", []):
        if is_page(parent):
            return parent
        if parent.TypeId == GROUP:
            return page_of(parent)
    return None


def group_of(item):
    for parent in getattr(item, "InList", []):
        if parent.TypeId == GROUP:
            return parent
    return None


def standard_of(page):
    return _get(page, "SciForgeStandard", "") or (
        "ASME" if _get(page, "ProjectionType", "") == "Third angle" else "ISO"
    )


def units_of(page):
    return _get(page, "SciForgeUnits", "") or "mm"


def sheet_of(page):
    standard = standard_of(page)
    return _get(page, "SciForgeSheet", "") or core.DEFAULT_SHEET[standard]


def scale_of(view):
    try:
        return float(view.getScale())
    except Exception:
        try:
            return float(view.Scale)
        except Exception:
            return 1.0


def _value(q):
    return float(getattr(q, "Value", q))


def view_position(view):
    """Where a view's centre is on the page (mm, y up)."""
    x, y = _value(view.X), _value(view.Y)
    if view.TypeId == ITEM:
        group = group_of(view)
        if group is not None:
            x += _value(group.X)
            y += _value(group.Y)
    return x, y


def page_to_local(view, point):
    """A page point in a view's own coordinates (unscaled, from its centre, y up)."""
    x, y = view_position(view)
    s = scale_of(view) or 1.0
    angle = math.radians(_value(getattr(view, "Rotation", 0.0)))
    u, v = (point[0] - x) / s, (point[1] - y) / s
    if abs(angle) > 1e-12:
        c, sn = math.cos(-angle), math.sin(-angle)
        u, v = u * c - v * sn, u * sn + v * c
    return u, v


def local_to_page(view, point):
    x, y = view_position(view)
    s = scale_of(view)
    angle = math.radians(_value(getattr(view, "Rotation", 0.0)))
    u, v = point[0] * s, point[1] * s
    if abs(angle) > 1e-12:
        c, sn = math.cos(angle), math.sin(angle)
        u, v = u * c - v * sn, u * sn + v * c
    return x + u, y + v


def axes_of(view):
    d = view.Direction
    x = view.XDirection
    return core.view_axes((d.x, d.y, d.z), (x.x, x.y, x.z))


def centre_of(view):
    """The model point at the middle of a view (its own coordinates' origin).

    TechDraw centres a view on the exact bounding box of its parts seen along the view
    (a copy without the 3D view's mesh); its getGeometricCenter() measures the meshed
    parts instead, which is off by the mesh's sag on curved faces (0.02 mm on an R8
    fillet): marks and cuts made from it missed TechDraw's lines by that much. A
    straight section is centred on what lies behind its cut."""
    if getattr(view, "TypeId", "") == SECTION:
        try:
            from . import drawing_depth

            centre = drawing_depth.cut_centre(view)
            if centre is not None:
                return centre
        except Exception as exc:
            log("section centre of %s: %s" % (getattr(view, "Label", "?"), exc))
    try:
        import Part

        from . import bodies

        shapes = []
        for src in getattr(view, "Source", []):
            if not alive(src):
                continue
            try:
                shape = bodies.global_shape(src)
            except Exception:
                shape = src.Shape.copy()
            if not shape.isNull():
                shapes.append(shape)
        if shapes:
            x, y, d = axes_of(view)
            matrix = App.Matrix(
                x[0], x[1], x[2], 0, y[0], y[1], y[2], 0, d[0], d[1], d[2], 0, 0, 0, 0, 1
            )
            local = Part.makeCompound(shapes).transformed(matrix, True)
            box = local.optimalBoundingBox(False, False)
            c = box.Center
            return core.to_model((x, y, d), (d[0] * c.z, d[1] * c.z, d[2] * c.z), c.x, c.y)
    except Exception as exc:
        log("view centre of %s: %s" % (getattr(view, "Label", "?"), exc))
    try:
        c = view.getGeometricCenter()
        return (c.x, c.y, c.z)
    except Exception:
        return (0.0, 0.0, 0.0)


def view_extent(view):
    """(half width, half height) of a view on the page (mm), from its visible edges."""
    xs, ys = [], []
    try:
        for edge in view.getVisibleEdges(True):
            box = edge.BoundBox
            xs += [box.XMin, box.XMax]
            ys += [box.YMin, box.YMax]
    except Exception:
        pass
    if not xs:
        return 10.0, 10.0
    return max(abs(min(xs)), abs(max(xs))), max(abs(min(ys)), abs(max(ys)))


def has_geometry(view):
    try:
        return bool(view.getVisibleEdges())
    except Exception:
        return False


def all_views(page):
    """Every view on a drawing, in page order."""
    found = []
    for obj in getattr(page, "Views", []):
        if obj.TypeId == GROUP:
            found += [v for v in obj.Views if alive(v)]
        elif is_view(obj):
            found.append(obj)
    return found


def annotations(page):
    """Everything on a drawing that is not a view: dimensions, balloons, text, tables."""
    return [o for o in getattr(page, "Views", []) if not is_view(o) and o.TypeId != GROUP]


def base_views(page):
    """The drawing's base views (Fusion: the first view placed of the design)."""
    return [v for v in all_views(page) if kind(v) == "BaseView"]


def parent_of(view):
    """The view a projected, section or detail view was made from."""
    parent = _get(view, "SciForgeParent", None)
    if alive(parent):
        return parent
    parent = _get(view, "BaseView", None)
    return parent if alive(parent) else None


def children_of(view):
    """Projected views made from `view` (they follow its style, scale and moves)."""
    found = []
    for user in getattr(view, "InList", []):
        if is_view(user) and same(_get(user, "SciForgeParent", None), view):
            found.append(user)
    return sorted(found, key=lambda o: o.ID)


def base_view_of(obj):
    """The base view a view hangs off."""
    seen = set()
    while obj is not None and obj.Name not in seen:
        seen.add(obj.Name)
        if kind(obj) == "BaseView":
            return obj
        obj = parent_of(obj)
    return None


# ------------------------------------------------------------------ the design
def design_bodies(doc, visible_only=False):
    """Bodies of the design that hold a solid (what a drawing can show)."""
    from . import bodies

    return bodies.solid_bodies(doc, visible_only=visible_only)


def sources_for(doc, contents, chosen=None):
    """The bodies a new drawing shows: Fusion's Contents choice (Full Assembly, Visible
    Only, Select)."""
    if contents == "Select":
        found = [b for b in (chosen or []) if alive(b)]
    elif contents == "Visible Only":
        found = design_bodies(doc, visible_only=True)
    else:
        found = design_bodies(doc)
    if not found:
        if contents == "Select":
            raise DrawingError("Pick the bodies or components to draw (tick them in the list).")
        if contents == "Visible Only":
            raise DrawingError("Nothing is shown: show a body, or choose Full Assembly.")
        raise DrawingError(
            "There is nothing to draw yet: the design has no solid bodies. Make a body "
            "first, then make the drawing."
        )
    return found


def _author():
    try:
        name = App.ParamGet("User parameter:BaseApp/Preferences/Document").GetString(
            "prefAuthor", ""
        )
        if name:
            return name
    except Exception:
        pass
    try:
        return getpass.getuser()
    except Exception:
        return ""


def _material_text(sources):
    from . import material

    names = []
    for body in sources:
        try:
            label = material.effective(body)[0]
        except Exception:
            label = ""
        label = label.replace(" (default)", "")
        if label and label not in names:
            names.append(label)
    return names[0] if len(names) == 1 else ""


def components_of(sources):
    """[{"name", "material", "description", "key", "bodies"}] of the components shown:
    a body inside a component counts as that component; a body at the root as itself."""
    from . import components, material

    found = []
    index = {}
    for body in sources:
        comp = components.component_of(body)
        unit = comp if comp is not None else body
        if unit.Name in index:
            index[unit.Name]["bodies"].append(body)
            continue
        try:
            mat = material.effective(body)[0].replace(" (default)", "")
        except Exception:
            mat = ""
        entry = {
            "name": unit.Label,
            "description": _get(unit, "Label2", "") or "",
            "material": mat,
            "key": unit.Name,
            "bodies": [body],
        }
        index[unit.Name] = entry
        found.append(entry)
    return found


# ------------------------------------------------------------------ the sheet
def template_folder():
    path = os.path.join(App.getUserAppDataDir(), "SciForge", "drawing-templates")
    os.makedirs(path, exist_ok=True)
    return path


def template_file(standard, sheet, title_block=True):
    """The SVG of a SciForge sheet (written once per size; TechDraw keeps a copy inside
    the design file, so the drawing opens anywhere)."""
    name = "SciForge_%s_%s%s.svg" % (standard, sheet, "" if title_block else "_blank")
    path = os.path.join(template_folder(), name)
    text = core.template_svg(standard, sheet, {}, title_block)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            if handle.read() == text:
                return path
    except OSError:
        pass
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def next_drawing_label(doc):
    base = "%s Drawing" % doc.Label
    labels = {p.Label for p in drawings(doc)}
    if base not in labels:
        return base
    n = 2
    while "%s %d" % (base, n) in labels:
        n += 1
    return "%s %d" % (base, n)


def create_drawing(
    doc,
    sources,
    standard="ISO",
    units="mm",
    sheet=None,
    title_block=True,
    label=None,
    contents="",
):
    """A new drawing (Fusion: File > New Drawing > From Design) with an empty sheet.
    contents "Full Assembly": the drawing keeps showing every body of the design (one
    added later comes into its views and parts list); otherwise the given bodies."""
    if standard not in core.STANDARDS:
        raise DrawingError("Choose ASME or ISO.")
    if units not in core.UNITS:
        raise DrawingError("Choose mm or in.")
    sheet = sheet if sheet in core.sheet_names(standard) else core.DEFAULT_SHEET[standard]
    sources = [s for s in sources if alive(s)]
    if not sources:
        raise DrawingError("There is nothing to draw: pick at least one body.")
    import TechDraw  # noqa: F401  (registers the types)

    page = doc.addObject(PAGE, "Drawing")
    page.Label = label or next_drawing_label(doc)
    template = doc.addObject("TechDraw::DrawSVGTemplate", "Sheet")
    template.Template = template_file(standard, sheet, title_block)
    page.Template = template
    page.ProjectionType = core.projection_of(standard)
    page.KeepUpdated = True
    _mark(page, TYPE)
    _add(page, "App::PropertyString", "SciForgeStandard", standard)
    _add(page, "App::PropertyString", "SciForgeUnits", units)
    _add(page, "App::PropertyString", "SciForgeSheet", sheet)
    _add(page, "App::PropertyBool", "SciForgeTitleBlock", bool(title_block))
    # (Global: the bodies may be inside components; a plain link list warned that they
    # were out of its scope on every recompute)
    _add(page, "App::PropertyLinkListGlobal", "SciForgeSources", sources)
    _add(page, "App::PropertyStringList", "SciForgeTitleEdits", [])
    _add(page, "App::PropertyString", "SciForgeContents", contents or "")
    date = datetime.date.today().isoformat()
    values = core.title_values(
        design=doc.Label,
        author=_author(),
        date=date,
        scale="",
        standard=standard,
        sheet=sheet,
        units=units,
        material=_material_text(sources),
    )
    if title_block:
        set_title(page, values, by_hand=False)
    log("drawing %s: %s %s %s" % (page.Label, standard, sheet, units))
    return page


def title_template(page):
    template = _get(page, "Template", None)
    if template is None or "EditableTexts" not in template.PropertiesList:
        return None
    return template


def title(page):
    template = title_template(page)
    if template is None:
        return {}
    return dict(template.EditableTexts)


def set_title(page, values, by_hand=True):
    """Fill title block fields. Fields typed by a person stop following the design."""
    template = title_template(page)
    if template is None:
        return
    texts = dict(template.EditableTexts)
    changed = False
    edits = list(_get(page, "SciForgeTitleEdits", []) or [])
    for key, value in values.items():
        if key not in texts and key not in core.TITLE_KEYS:
            continue
        value = str(value if value is not None else "")
        if texts.get(key) != value:
            texts[key] = value
            changed = True
        if by_hand and key not in edits:
            edits.append(key)
    if changed:
        template.EditableTexts = texts
    if by_hand and "SciForgeTitleEdits" in page.PropertiesList:
        if list(page.SciForgeTitleEdits) != edits:
            page.SciForgeTitleEdits = edits


def auto_title_values(page):
    """The title block fields that follow the design (until typed over)."""
    doc = page.Document
    standard = standard_of(page)
    sources = [s for s in _get(page, "SciForgeSources", []) or [] if alive(s)]
    scale = ""
    bases = base_views(page)
    if bases:
        scale = core.format_scale(scale_of(bases[0]))
    return {
        "Title": doc.Label,
        "PartNumber": doc.Label,
        "Scale": scale,
        "Size": sheet_of(page),
        "Units": units_of(page),
        "Material": _material_text(sources),
        "Sheet": _sheet_text(page),
        "Standard": standard,
    }


def _sheet_text(page):
    """The title block's sheet number: "2 / 3" (follows added, deleted, moved sheets)."""
    try:
        from . import drawing_sheets

        return drawing_sheets.sheet_title_value(page)
    except Exception as exc:
        warn("sheet number of %s: %s" % (getattr(page, "Label", "?"), exc))
        return "1 / 1"


def refresh_title(page):
    """Keep the automatic fields (scale, name, material...) up to date."""
    if title_template(page) is None:
        return False
    edits = set(_get(page, "SciForgeTitleEdits", []) or [])
    current = title(page)
    wanted = {
        k: v
        for k, v in auto_title_values(page).items()
        if k in core.AUTO_KEYS and k not in edits and current.get(k) != v
    }
    if wanted:
        set_title(page, wanted, by_hand=False)
        return True
    return False


# ------------------------------------------------------------------ views
def _style(view, style, tangent="Full Length"):
    hidden = style in ("Visible and Hidden Edges", "Shaded with Hidden Edges")
    view.HardHidden = hidden
    view.SmoothHidden = hidden and tangent != "Off"
    view.SmoothVisible = tangent != "Off"
    view.SeamVisible = False
    view.SeamHidden = False
    _add(view, "App::PropertyString", "SciForgeStyle", style)
    _add(view, "App::PropertyString", "SciForgeTangent", tangent)


def style_of(view):
    return _get(view, "SciForgeStyle", "") or (
        "Visible and Hidden Edges" if _get(view, "HardHidden", False) else "Visible Edges"
    )


def tangent_of(view):
    return _get(view, "SciForgeTangent", "") or (
        "Full Length" if _get(view, "SmoothVisible", True) else "Off"
    )


def model_extent(sources, axes):
    """(width, height, depth) of the sources seen along a view's axes (mm at 1:1)."""
    lo = [float("inf")] * 3
    hi = [-float("inf")] * 3
    for src in sources:
        try:
            shape = src.Shape
            for vertex in shape.Vertexes:
                p = vertex.Point
                for i, axis in enumerate(axes):
                    d = p.x * axis[0] + p.y * axis[1] + p.z * axis[2]
                    lo[i] = min(lo[i], d)
                    hi[i] = max(hi[i], d)
        except Exception:
            continue
    if lo[0] == float("inf"):
        return 10.0, 10.0, 10.0
    return tuple(max(1e-3, hi[i] - lo[i]) for i in range(3))


def automatic_scale(page, sources, orientation="Front"):
    """Fusion's Automatic scale: the largest standard scale at which the base view and a
    projected view beside and above it fit the sheet."""
    direction, xdir = orientation_axes(orientation)
    axes = core.view_axes(direction, xdir)
    width, height, depth = model_extent(sources, axes)
    x0, y0, x1, y1 = core.drawing_area(standard_of(page), sheet_of(page))
    gap = 0.12
    return core.fit_scale(
        (width + depth) * (1 + gap), (height + depth) * (1 + gap), x1 - x0, y1 - y0
    )


def orientation_axes(name):
    for label, direction, xdir in core.ORIENTATIONS:
        if label == name:
            return direction, xdir
    return core.ORIENTATIONS[0][1], core.ORIENTATIONS[0][2]


def add_base_view(page, sources, x, y, orientation="Front", style=None, scale=None, tangent=None):
    """The first view of a drawing (Fusion's Base View)."""
    doc = page.Document
    style = style or "Visible and Hidden Edges"
    tangent = tangent or "Full Length"
    if scale is None:
        scale = automatic_scale(page, sources, orientation)
    direction, xdir = orientation_axes(orientation)
    view = doc.addObject(PART_VIEW, "BaseView")
    view.Source = list(sources)
    view.Direction = V(*direction)
    view.XDirection = V(*xdir)
    view.ScaleType = "Custom"
    view.Scale = scale
    view.X = x
    view.Y = y
    _style(view, style, tangent)
    _mark(view, "BaseView")
    _add(view, "App::PropertyString", "SciForgeOrientation", orientation)
    view.Label = "Base View"
    _add_to_page(page, view)
    return view


def set_base_orientation(view, orientation):
    """A base view's orientation; its projected views turn with it."""
    direction, xdir = orientation_axes(orientation)
    view.Direction = V(*direction)
    view.XDirection = V(*xdir)
    _add(view, "App::PropertyString", "SciForgeOrientation", orientation)
    _turn_children(view)


def _turn_children(view):
    for child in children_of(view):
        child_kind = _get(child, "SciForgeKind", "")
        if not child_kind:
            continue
        direction, xdir = core.projected_axes(axes_of(view), child_kind)
        child.Direction = V(*direction)
        child.XDirection = V(*xdir)
        _turn_children(child)


def orientation_of(view):
    return _get(view, "SciForgeOrientation", "") or "Front"


def is_isometric(view):
    """A view looking at the design from a slant (Home, or an isometric projected view):
    its lengths are foreshortened, so Fusion does not dimension it. A section is a true
    view of its cut whatever its direction; a detail is what its parent is."""
    if is_section(view):
        return False
    if view.TypeId == DETAIL:
        parent = view.BaseView
        return is_isometric(parent) if alive(parent) else False
    d = view.Direction
    big = [abs(c) for c in (d.x, d.y, d.z) if abs(c) > 1e-6]
    return len(big) > 1


def _family(view):
    """A view and the projected views made from it, at any depth."""
    found = [view]
    for child in children_of(view):
        found += _family(child)
    return found


def set_view_style(view, style, tangent=None):
    """Style of a view; its projected views follow (Fusion: projected views inherit their
    parent's properties)."""
    tangent = tangent or tangent_of(view)
    for target in _family(view):
        _style(target, style, tangent)


def set_scale(view, scale):
    """Scale of a view; its projected views follow."""
    for target in _family(view):
        target.ScaleType = "Custom"
        target.Scale = scale
        if target.TypeId == DETAIL:
            target.Label = detail_caption(target)
            apply_caption(target)


def add_projected(parent, kind_name, x, y):
    """A projected view of `parent` (Fusion's Projected View) at page point (x, y)."""
    page = page_of(parent)
    doc = parent.Document
    existing = [v for v in children_of(parent) if _get(v, "SciForgeKind", "") == kind_name]
    if existing:
        raise DrawingError("There is already a %s view of that view." % _kind_label(kind_name))
    direction, xdir = core.projected_axes(axes_of(parent), kind_name)
    view = doc.addObject(PART_VIEW, "ProjectedView")
    view.Source = _view_sources(parent)  # (not a breakout's trimmed copy)
    clip = _get(parent, "SciForgeDepthClip", None)
    if core.is_iso_kind(kind_name) and has_breakout(parent) and alive(clip):
        # Fusion: an isometric view made from a view with a breakout shows its cut
        _add(view, "App::PropertyLinkListGlobal", "SciForgeCutSources", _view_sources(parent))
        view.Source = [clip]
    view.Direction = V(*direction)
    view.XDirection = V(*xdir)
    view.ScaleType = "Custom"
    view.Scale = scale_of(parent)
    view.X = x
    view.Y = y
    _style(view, style_of(parent), tangent_of(parent))
    _mark(view, "ProjectedView")
    _add(view, "App::PropertyLink", "SciForgeParent", parent)
    _add(view, "App::PropertyString", "SciForgeKind", kind_name)
    px, py = view_position(parent)
    _add(view, "App::PropertyFloatList", "SciForgeOffset", [x - px, y - py])
    view.Label = "%s View" % _kind_label(kind_name)
    _add_to_page(page, view)
    return view


def _axis_of(view):
    """The page direction a view may slide along from its parent (None: free)."""
    child_kind = _get(view, "SciForgeKind", "")
    if child_kind in ("Right", "Left"):
        return (1.0, 0.0)
    if child_kind in ("Top", "Bottom"):
        return (0.0, 1.0)
    if is_section(view):
        line = section_line_of(view)
        parent = parent_of(view)
        if line is not None and parent is not None:
            info = core.section_line(line[0], line[1], line[2], "Third angle")
            if info is not None:
                return info["n"]
    return None


_LAST = {}  # (document, view) -> last page position seen by keep_aligned


def keep_aligned(page):
    """Projected and section views stay lined up with their parent (Fusion): the parent
    moved -> they move with it; one of them moved -> it slides along its axis only."""
    changed = False
    doc_name = page.Document.Name
    views = all_views(page)
    for view in views:
        parent = _get(view, "SciForgeParent", None) if view.TypeId != DETAIL else None
        if is_section(view):
            parent = _get(view, "BaseView", None)
        if not alive(parent):
            continue
        axis = _axis_of(view)
        if axis is None and is_section(view):
            continue
        px, py = view_position(parent)
        cx, cy = view_position(view)
        offset = list(_get(view, "SciForgeOffset", []) or [])
        if len(offset) != 2:
            offset = [cx - px, cy - py]
        last_p = _LAST.get((doc_name, parent.Name))
        last_c = _LAST.get((doc_name, view.Name))
        parent_moved = last_p is not None and (
            abs(last_p[0] - px) > 1e-7 or abs(last_p[1] - py) > 1e-7
        )
        child_moved = last_c is not None and (
            abs(last_c[0] - cx) > 1e-7 or abs(last_c[1] - cy) > 1e-7
        )
        if child_moved and not parent_moved:
            offset = [cx - px, cy - py]
        if axis is not None:
            along = offset[0] * axis[0] + offset[1] * axis[1]
            offset = [axis[0] * along, axis[1] * along]
        if list(_get(view, "SciForgeOffset", []) or []) != offset:
            _add(view, "App::PropertyFloatList", "SciForgeOffset", offset)
        tx, ty = px + offset[0], py + offset[1]
        if abs(tx - cx) > 1e-7 or abs(ty - cy) > 1e-7:
            view.X = tx
            view.Y = ty
            changed = True
    for view in all_views(page):
        _LAST[(doc_name, view.Name)] = view_position(view)
    return changed


def _kind_label(kind):
    names = {
        "FrontTopRight": "Isometric (top right)",
        "FrontTopLeft": "Isometric (top left)",
        "FrontBottomRight": "Isometric (bottom right)",
        "FrontBottomLeft": "Isometric (bottom left)",
    }
    return names.get(kind, kind)


def used_labels(page):
    labels = []
    for view in all_views(page):
        for prop in ("SectionSymbol", "Reference"):
            value = _get(view, prop, "")
            if value:
                labels.append(value)
    return labels


def add_section(parent, p1, p2, side, position, label=None, scale=None, points=None, depth=None):
    """Section View: cut along the line p1-p2 (parent view coordinates) and look from the
    side the view is placed on (third angle) or from the other side (first angle).

    points: the whole cut line when it has bends (Fusion's half, offset and aligned
    sections): TechDraw's complex section cuts along it (the first segment sets the
    viewing direction). depth: ("Full" | "Slice" | "Distance", mm) for a straight line."""
    page = page_of(parent)
    doc = parent.Document
    projection = page.ProjectionType
    pts = core.simplify_line([tuple(p) for p in (points or [p1, p2])])
    if len(pts) < 2:
        raise DrawingError("Click at least two points for the cut line.")
    p1, p2 = pts[0], pts[1]
    line = core.section_line(p1, p2, side, projection)
    if line is None:
        raise DrawingError("The section line has no length: click two different points.")
    section_kind = core.section_kind(pts)
    if section_kind is None:
        raise DrawingError("Two points of the cut line are the same: click different points.")
    axes = axes_of(parent)
    direction, xdir, normal = core.section_axes(axes, line)
    mid = line["mid"]
    origin = core.to_model(axes, centre_of(parent), mid[0], mid[1])
    label = label or core.next_label(used_labels(page))
    complex_cut = len(pts) > 2
    if depth is not None and depth[0] != "Full":
        # (refused before anything is made)
        if depth[0] not in DEPTH_MODES:
            raise DrawingError("Choose Full, Slice or Distance.")
        if depth[0] == "Distance" and (depth[1] if len(depth) > 1 else 0.0) <= 0:
            raise DrawingError("Type how far behind the cut the section shows (more than 0 mm).")
        if complex_cut:
            raise DrawingError(
                "Section depth works with a straight cut line: choose Full for a line "
                "with bends."
            )
    section = doc.addObject(COMPLEX if complex_cut else SECTION, "Section")
    section.Source = _view_sources(parent)
    section.Direction = V(*direction)
    section.XDirection = V(*xdir)
    section.SectionNormal = V(*normal)
    section.SectionOrigin = V(*origin)
    section.SectionDirection = "Aligned"
    section.SectionSymbol = label
    section.ScaleType = "Custom"
    section.Scale = scale if scale else scale_of(parent)
    section.X = position[0]
    section.Y = position[1]
    if complex_cut:
        profile = _plane_sketch(parent, "SectionLine", list(zip(pts, pts[1:])), "DrawingProfile")
        section.CuttingToolWireObject = profile
        section.ProjectionStrategy = "Aligned" if section_kind == "Aligned" else "Offset"
    _hatch(section)
    _add_to_page(page, section)
    section.BaseView = parent
    _mark(section, "CutView")  # (a "Section" type would be an analysis in the browser)
    _add(section, "App::PropertyStringList", "SciForgeLine", [json.dumps([p1, p2, side])])
    _add(section, "App::PropertyString", "SciForgePoints", json.dumps([list(p) for p in pts]))
    _add(section, "App::PropertyString", "SciForgeSectionKind", section_kind)
    px, py = view_position(parent)
    _add(section, "App::PropertyFloatList", "SciForgeOffset", [position[0] - px, position[1] - py])
    # Fusion's section views show no hidden edges by default
    style = {"Visible and Hidden Edges": "Visible Edges", "Shaded with Hidden Edges": "Shaded"}
    _style(section, style.get(style_of(parent), style_of(parent)), tangent_of(parent))
    section.Label = section_caption(label)
    apply_caption(section)  # written under the view, also in the PDF
    if depth is not None and depth[0] != "Full":
        set_section_depth(section, depth[0], depth[1] if len(depth) > 1 else 0.0)
    return section


def section_points(section):
    """The cut line's points (parent view coordinates)."""
    try:
        pts = json.loads(_get(section, "SciForgePoints", "") or "[]")
        if len(pts) >= 2:
            return [tuple(p) for p in pts]
    except ValueError:
        pass
    line = section_line_of(section)
    return [line[0], line[1]] if line else []


def section_kind_of(section):
    return _get(section, "SciForgeSectionKind", "") or core.section_kind(section_points(section))


def _plane_sketch(view, name, segments, sciforge_type):
    """A hidden sketch in a view's plane through its centre holding line segments given in
    the view's own coordinates (TechDraw's break lines and complex section profiles must
    be sketches lying square to the view)."""
    import Part
    import Sketcher  # noqa: F401

    doc = view.Document
    xa, ya, da = axes_of(view)
    centre = centre_of(view)
    matrix = App.Matrix(
        xa[0],
        ya[0],
        da[0],
        centre[0],
        xa[1],
        ya[1],
        da[1],
        centre[1],
        xa[2],
        ya[2],
        da[2],
        centre[2],
        0.0,
        0.0,
        0.0,
        1.0,
    )
    sketch = doc.addObject("Sketcher::SketchObject", name)
    sketch.Placement = App.Placement(matrix)
    for a, b in segments:
        sketch.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(b[0], b[1], 0)))
    _set_shown(sketch, False)
    _mark(sketch, sciforge_type)
    return sketch


# ------------------------------------------------------------------ section depth
DEPTH_MODES = ("Full", "Slice", "Distance")
SLICE_DEPTH = 0.01  # mm behind the cut a Slice keeps (only the cut faces show)


def section_depth(section):
    """(mode, distance) of a section view (Fusion's Section Depth)."""
    try:
        data = json.loads(_get(section, "SciForgeDepth", "") or "{}")
    except ValueError:
        data = {}
    mode = data.get("mode", "Full")
    return (mode if mode in DEPTH_MODES else "Full"), float(data.get("value", 0.0) or 0.0)


def set_section_depth(section, mode, value=0.0):
    """Fusion's Section Depth: Full shows everything behind the cut; Slice only what the
    cut line cuts through; Distance what lies up to `value` mm behind it. TechDraw draws
    everything behind its cut: the lines that lie deeper are switched off
    (drawing_depth.py)."""
    from . import drawing_depth

    if mode not in DEPTH_MODES:
        raise DrawingError("Choose Full, Slice or Distance.")
    if mode == "Distance" and value <= 0:
        raise DrawingError("Type how far behind the cut the section shows (more than 0 mm).")
    if section.TypeId == COMPLEX and mode != "Full":
        raise DrawingError(
            "Section depth works with a straight cut line: this section's line has bends."
        )
    _add(
        section, "App::PropertyString", "SciForgeDepth", json.dumps({"mode": mode, "value": value})
    )
    drawing_depth.refresh(section, force=True)
    return section


def refresh_depth(view):
    """A Slice / Distance section follows the design: the lines beyond its depth are
    worked out again when its lines or the parts changed. True when it changed."""
    if not is_section(view):
        return False
    from . import drawing_depth

    return drawing_depth.refresh(view)


def _hatch(section):
    """Fusion hatches cut faces with 45 degree lines (ANSI31)."""
    try:
        path = os.path.join(App.getResourceDir(), "Mod", "TechDraw", "PAT", HATCH_FILE)
        if os.path.isfile(path):
            section.CutSurfaceDisplay = "PatHatch"
            section.FileGeomPattern = path
            section.NameGeomPattern = HATCH_NAME
            section.HatchScale = 1.0
    except Exception as exc:
        warn("section hatch: %s" % exc)


def section_caption(label):
    """What the drawing writes under a section view (Fusion: SECTION A-A)."""
    return "SECTION %s-%s" % (label, label)


def detail_caption(detail):
    """What the drawing writes under a detail view: its letter and its scale."""
    return "DETAIL %s (%s)" % (detail.Reference, core.format_scale(scale_of(detail)))


def default_caption(view):
    """What a view's label says unless a person typed another text: SECTION A-A, DETAIL
    B (2:1), or the view's name."""
    if is_section(view):
        return section_caption(view.SectionSymbol)
    if view.TypeId == DETAIL:
        return detail_caption(view)
    return view.Label


def view_label(view):
    return _get(view, "SciForgeViewLabel", "") or default_caption(view)


def label_shown(view):
    """Fusion shows the labels of section and detail views, not of the others, until a
    person changes that."""
    if "SciForgeLabelShown" in view.PropertiesList:
        return bool(view.SciForgeLabelShown)
    return is_section(view) or view.TypeId == DETAIL


def set_view_label(view, text=None, shown=None):
    """Edit a view's label (Fusion's View Label): its text and whether it shows."""
    if text is not None:
        text = text.strip()
        _add(
            view,
            "App::PropertyString",
            "SciForgeViewLabel",
            "" if text == default_caption(view) else text,
        )
    if shown is not None:
        _add(view, "App::PropertyBool", "SciForgeLabelShown", bool(shown))
    apply_caption(view)


def apply_caption(view):
    want = view_label(view) if label_shown(view) else ""
    if _get(view, "Caption", None) != want:
        view.Caption = want


def section_line_of(section):
    try:
        p1, p2, side = json.loads(section.SciForgeLine[0])
        return tuple(p1), tuple(p2), tuple(side)
    except Exception:
        return None


def add_detail(parent, centre, radius, position, label=None, scale=None):
    """Detail View: the part of the parent inside a circle (parent coordinates), larger."""
    page = page_of(parent)
    doc = parent.Document
    if radius <= 1e-6:
        raise DrawingError("Make the circle bigger: drag away from its centre.")
    label = label or core.next_label(used_labels(page))
    detail = doc.addObject(DETAIL, "Detail")
    detail.Source = _view_sources(parent)
    detail.Direction = parent.Direction
    detail.XDirection = parent.XDirection
    detail.AnchorPoint = V(centre[0], centre[1], 0)
    detail.Radius = radius
    detail.Reference = label
    detail.ScaleType = "Custom"
    detail.Scale = scale if scale else scale_of(parent) * core.DEFAULT_DETAIL_FACTOR
    detail.X = position[0]
    detail.Y = position[1]
    _add_to_page(page, detail)
    detail.BaseView = parent
    _mark(detail, "DetailView")
    _style(detail, style_of(parent), tangent_of(parent))
    detail.Label = detail_caption(detail)
    apply_caption(detail)
    return detail


def add_break(view, a, b, gap=None):
    """Break View: the part of a view between a and b (view coordinates) is taken out and
    the two ends move together. TechDraw does this with a broken view that stands in for
    the original one (kept hidden, so removing the break brings it back)."""
    page = page_of(view)
    doc = view.Document
    if view.TypeId == BROKEN:
        raise DrawingError("This view is already broken: remove its break first (Delete).")
    if view.TypeId in (DETAIL,):
        raise DrawingError("A detail view cannot be broken: break its parent instead.")
    du, dv = b[0] - a[0], b[1] - a[1]
    horizontal = abs(du) >= abs(dv)
    if (abs(du) if horizontal else abs(dv)) < 1e-3:
        raise DrawingError("Click two different points along the view to break it.")
    # TechDraw's break object: a sketch with two lines across the view at the break's
    # ends, in the view's own plane (an edge object failed in the GUI: "TopoDS::Edge")
    half_w, half_h = view_extent(view)
    s = scale_of(view) or 1.0
    reach = (max(half_w, half_h) / s) + 5.0
    segments = []
    for end in (a, b):
        if horizontal:
            segments.append(((end[0], -reach), (end[0], reach)))
        else:
            segments.append(((-reach, end[1]), (reach, end[1])))
    marker = _plane_sketch(view, "DrawingBreak", segments, "DrawingBreak")
    broken = doc.addObject(BROKEN, "BrokenView")
    broken.Source = _view_sources(view)
    broken.Breaks = [marker]
    broken.Direction = view.Direction
    broken.XDirection = view.XDirection
    broken.ScaleType = "Custom"
    broken.Scale = scale_of(view)
    if gap is not None:
        broken.Gap = gap
    x, y = view_position(view)
    broken.X = x
    broken.Y = y
    # (its name and SciForge's settings before it goes on the page: TechDraw's page view
    # refused a new name for a broken view it was still computing)
    broken.Label = "%s (broken)" % view.Label
    _style(broken, style_of(view), tangent_of(view))
    _mark(broken, "BreakView")
    _add(broken, "App::PropertyLink", "SciForgeBrokenOf", view)
    _add(
        broken,
        "App::PropertyString",
        "SciForgeBreakAxis",
        "horizontal" if horizontal else "vertical",
    )
    _add_to_page(page, broken)
    _set_shown(view, False)
    return broken


def _set_shown(view, shown):
    try:
        view.Visibility = bool(shown)
    except Exception:
        pass
    try:
        if App.GuiUp and view.ViewObject is not None:
            view.ViewObject.Visibility = bool(shown)
    except Exception:
        pass


# ------------------------------------------------------------------ geometry of picks
def edge_info(view, name):
    """What a picked view element is, in view coordinates (unscaled, y up), for
    drawing_core.infer_dimension: a line, circle, arc, vertex or other curve."""
    import Part

    try:
        if name.startswith("Vertex"):
            vertex = view.getVertexBySelection(name)
            p = vertex.Point
            return {"kind": "vertex", "point": (p.x, p.y), "name": name}
        if not name.startswith("Edge"):
            return None
        edge = view.getEdgeBySelection(name)
    except Exception:
        return None
    curve = edge.Curve
    if isinstance(curve, (Part.Line, Part.LineSegment)) or curve.__class__.__name__ == "Line":
        a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        return {"kind": "line", "p1": (a.x, a.y), "p2": (b.x, b.y), "name": name}
    if isinstance(curve, Part.Circle):
        c = curve.Center
        full = edge.isClosed() or abs(edge.Length - 2 * math.pi * curve.Radius) < 1e-6
        return {
            "kind": "circle" if full else "arc",
            "center": (c.x, c.y),
            "radius": curve.Radius,
            "name": name,
        }
    return {"kind": "curve", "name": name}


def center_vertex(view, center, tol=1e-4):
    """The name of the view vertex at a circle's centre (TechDraw adds one per circle)."""
    best, best_d = None, None
    for i, p in enumerate(_all_vertexes(view)):
        d = math.hypot(p[0] - center[0], p[1] - center[1])
        if best_d is None or d < best_d:
            best, best_d = i, d
    if best is not None and best_d <= max(tol, 1e-3):
        return "Vertex%d" % best
    return None


def _all_vertexes(view):
    """Every vertex of a view by index (unscaled, y up), as selection names count them."""
    found = []
    i = 0
    while True:
        try:
            vertex = view.getVertexBySelection("Vertex%d" % i)
        except Exception:
            break
        if vertex is None:
            break
        p = vertex.Point
        found.append((p.x, p.y))
        i += 1
        if i > 5000:
            break
    return found


# ------------------------------------------------------------------ dimensions
def add_dimension(view, refs, dim_type, position):
    """A dimension of the picked elements of one view, its text at a page position."""
    page = page_of(view)
    doc = view.Document
    dim = doc.addObject(DIMENSION, "Dimension")
    dim.Type = dim_type
    dim.References2D = [(view, r) for r in refs]
    dim.MeasureType = "Projected"
    dim.FormatSpec = core.dimension_format(units_of(page), standard_of(page), dim_type)
    dim.ShowUnits = False
    page.addView(dim)
    place_dimension(dim, position)
    _mark(dim, "Dimension")
    return dim


def place_dimension(dim, position):
    view = dim.References2D[0][0] if dim.References2D else None
    if view is None:
        return
    x, y = view_position(view)
    dim.X = position[0] - x
    dim.Y = position[1] - y


def dimension_value(dim):
    try:
        return float(dim.getRawValue())
    except Exception:
        return None


def dimension_text(dim):
    if _get(dim, "SciForgeDimSettings", ""):
        from . import drawing_annot

        text = drawing_annot.dimension_one_line(dim)
        if text:
            return text
    value = dimension_value(dim)
    if value is None:
        return ""
    page = page_of(dim)
    if dim.Type in ("Angle", "Angle3Pt"):
        return "%s°" % core._short(round(value, 2))
    text = core.format_value(value, units_of(page) if page is not None else "mm")
    if dim.Type == "Diameter":
        return core.DIAMETER_SIGN + text
    if dim.Type == "Radius":
        return "R" + text
    return text


# ------------------------------------------------------------------ centre marks and lines
def add_center_mark(view, edge_name):
    """Fusion's Center Mark on a circle or arc: two dash-dot lines crossing at its
    centre, a little past the circle."""
    info = edge_info(view, edge_name)
    if info is None or info["kind"] not in ("circle", "arc"):
        raise DrawingError("Click a circle or an arc for a centre mark.")
    return _make_mark(view, info["center"], info["radius"])


def _make_mark(view, center, radius):
    s = scale_of(view) or 1.0
    reach = radius + CENTER_EXTENSION / s
    cx, cy = center
    tags = [
        view.makeCosmeticLine(V(cx - reach, cy, 0), V(cx + reach, cy, 0), LINE_DASHDOT, 0.18),
        view.makeCosmeticLine(V(cx, cy - reach, 0), V(cx, cy + reach, 0), LINE_DASHDOT, 0.18),
    ]
    marks = center_marks(view)
    marks.append({"tags": tags, "c": [cx, cy], "r": radius})
    _save_marks(view, marks)
    return tags


def center_marks(view):
    try:
        return [json.loads(t) for t in _get(view, "SciForgeCenterMarks", []) or []]
    except Exception:
        return []


def _save_marks(view, marks):
    _add(view, "App::PropertyStringList", "SciForgeCenterMarks", [json.dumps(m) for m in marks])


def remove_center_mark(view, index):
    marks = center_marks(view)
    if not 0 <= index < len(marks):
        return
    for tag in marks[index]["tags"]:
        try:
            view.removeCosmeticEdge(tag)
        except Exception:
            pass
    del marks[index]
    _save_marks(view, marks)


def circles_of(view):
    """[(centre, radius)] of the full circles a view shows (unscaled, y up)."""
    import Part

    found = []
    s = scale_of(view) or 1.0
    try:
        edges = view.getVisibleEdges(True)
    except Exception:
        return found
    for edge in edges:
        curve = edge.Curve
        if isinstance(curve, Part.Circle) and edge.isClosed():
            c = curve.Center
            found.append(((c.x / s, c.y / s), curve.Radius / s))
    return found


def follow_center_marks(view):
    """After the design changed: a centre mark whose circle moved goes with it (to the
    nearest circle of the same size); one whose circle is gone is removed."""
    marks = center_marks(view)
    if not marks:
        return False
    circles = circles_of(view)
    if not circles and not has_geometry(view):
        return False
    changed = False
    keep = []
    for mark in marks:
        cx, cy = mark["c"]
        r = mark["r"]
        same = [c for c in circles if abs(c[1] - r) < 1e-4]
        if any(math.hypot(c[0][0] - cx, c[0][1] - cy) < 1e-4 for c in same):
            keep.append(mark)
            continue
        candidates = same or [c for c in circles if abs(c[1] - r) < max(1.0, 0.5 * r)]
        for tag in mark["tags"]:
            try:
                view.removeCosmeticEdge(tag)
            except Exception:
                pass
        changed = True
        if not candidates:
            continue
        best = min(candidates, key=lambda c: math.hypot(c[0][0] - cx, c[0][1] - cy))
        s = scale_of(view) or 1.0
        reach = best[1] + CENTER_EXTENSION / s
        bx, by = best[0]
        tags = [
            view.makeCosmeticLine(V(bx - reach, by, 0), V(bx + reach, by, 0), LINE_DASHDOT, 0.18),
            view.makeCosmeticLine(V(bx, by - reach, 0), V(bx, by + reach, 0), LINE_DASHDOT, 0.18),
        ]
        keep.append({"tags": tags, "c": [bx, by], "r": best[1]})
    if changed:
        _save_marks(view, keep)
        try:
            # TechDraw draws a view's cosmetic lines from its last recompute: without one
            # the sheet kept showing the mark where the hole was
            view.recompute()
        except Exception as exc:
            warn("centre marks of %s: %s" % (view.Label, exc))
    return changed


def add_centerline(view, first, second):
    """Fusion's Centerline: the line midway between two parallel edges."""
    a, b = edge_info(view, first), edge_info(view, second)
    if not a or not b or a["kind"] != "line" or b["kind"] != "line":
        raise DrawingError("Click two straight edges that run side by side.")
    da = (a["p2"][0] - a["p1"][0], a["p2"][1] - a["p1"][1])
    db = (b["p2"][0] - b["p1"][0], b["p2"][1] - b["p1"][1])
    cross = da[0] * db[1] - da[1] * db[0]
    norm = math.hypot(*da) * math.hypot(*db)
    if norm < 1e-12 or abs(cross / norm) > math.sin(math.radians(1.0)):
        raise DrawingError(
            "These edges are not parallel: a centreline goes between two edges that run "
            "side by side."
        )
    if abs(da[0]) < 1e-9:
        mode = 0  # vertical
    elif abs(da[1]) < 1e-9:
        mode = 1  # horizontal
    else:
        mode = 2
    tag = view.makeCenterLine([first, second], mode)
    return tag


# ------------------------------------------------------------------ automatic centre marks
AUTO_KINDS = ("holes", "extrudes", "cuts")


def auto_mark_settings(view):
    """Fusion's Automated Center Marks and Center Lines of a view: which round features
    get them (Holes, Round Extrudes, Round Cuts)."""
    try:
        data = json.loads(_get(view, "SciForgeAutoMarks", "") or "{}")
    except ValueError:
        data = {}
    return {k: bool(data.get(k)) for k in AUTO_KINDS}


def set_auto_marks(view, settings):
    data = {k: bool(settings.get(k)) for k in AUTO_KINDS}
    _add(view, "App::PropertyString", "SciForgeAutoMarks", json.dumps(data, sort_keys=True))
    return refresh_auto_marks(view, force=True)


def has_breakout(view):
    """True when a view has a Breakout Section View (drawing_breakout.py)."""
    return bool(_get(view, "SciForgeBreakout", ""))


def _view_sources(view):
    """The parts a view shows (a breakout's trimmed copy stands for its parts)."""
    cut = [s for s in (_get(view, "SciForgeCutSources", []) or []) if alive(s)]
    if cut:
        return cut
    return [s for s in getattr(view, "Source", []) if alive(s) and kind(s) != "DrawingDepth"]


def round_features(view):
    """[(kind, axis point, axis direction, radius, (t0, t1))] of the full round faces of
    the parts a view shows: holes and round cuts are inner cylinders, round extrudes
    outer ones (a fillet is only part of a round and is left out)."""
    import Part

    from . import bodies

    groups = {}
    for src in _view_sources(view):
        try:
            shape = bodies.global_shape(src)
        except Exception:
            continue
        for face in shape.Faces:
            surface = face.Surface
            if not isinstance(surface, Part.Cylinder):
                continue
            axis = V(surface.Axis)
            axis.normalize()
            centre = V(surface.Center)
            radius = surface.Radius
            u0, u1, v0, v1 = face.ParameterRange
            span = abs(u1 - u0)
            # convex or concave: the face's outward normal points away from the axis on a
            # boss, towards it in a hole (normalAt already points out of the solid)
            u, v = (u0 + u1) / 2.0, (v0 + v1) / 2.0
            point = face.valueAt(u, v)
            normal = face.normalAt(u, v)
            radial = point - centre
            radial = radial - axis * radial.dot(axis)
            inner = normal.dot(radial) < 0
            # one round, possibly in several faces: the same axis line and radius
            base = centre - axis * centre.dot(axis)
            key = (
                round(abs(axis.x), 4),
                round(abs(axis.y), 4),
                round(abs(axis.z), 4),
                round(base.x, 3),
                round(base.y, 3),
                round(base.z, 3),
                round(radius, 4),
                inner,
            )
            ts = [(vx.Point - centre).dot(axis) for vx in face.Vertexes]
            entry = groups.setdefault(key, [0.0, centre, axis, radius, [], inner])
            entry[0] += span
            entry[4] += ts
    found = []
    for total, centre, axis, radius, ts, inner in groups.values():
        if total < math.radians(300.0) or not ts:
            continue
        found.append(("hole" if inner else "extrude", centre, axis, radius, (min(ts), max(ts))))
    return found


def auto_mark_geometry(view, settings=None):
    """{"marks": [[cx, cy, r]], "lines": [[x1, y1, x2, y2]]} (view coordinates) of the
    automatic centre marks (rounds seen end on) and centre lines (rounds seen from the
    side) of a view."""
    settings = settings or auto_mark_settings(view)
    want_inner = settings.get("holes") or settings.get("cuts")
    want_outer = settings.get("extrudes")
    marks, lines = [], []
    if not (want_inner or want_outer):
        return {"marks": marks, "lines": lines}
    axes = axes_of(view)
    d = axes[2]
    centre = centre_of(view)
    s = scale_of(view) or 1.0
    for feature, point, axis, radius, (t0, t1) in round_features(view):
        if feature == "hole" and not want_inner:
            continue
        if feature == "extrude" and not want_outer:
            continue
        along = abs(axis.x * d[0] + axis.y * d[1] + axis.z * d[2])
        if along > 0.9999:
            u, v = core.to_view(axes, centre, (point.x, point.y, point.z))
            mark = [round(u, 6), round(v, 6), round(radius, 6)]
            if mark not in marks:
                marks.append(mark)
        elif along < 1e-4:
            reach = CENTER_EXTENSION / s
            a = point + axis * (t0 - reach)
            b = point + axis * (t1 + reach)
            ua = core.to_view(axes, centre, (a.x, a.y, a.z))
            ub = core.to_view(axes, centre, (b.x, b.y, b.z))
            line = [round(ua[0], 6), round(ua[1], 6), round(ub[0], 6), round(ub[1], 6)]
            if line not in lines and [line[2], line[3], line[0], line[1]] not in lines:
                lines.append(line)
    return {"marks": marks, "lines": lines}


def auto_marks_of(view):
    try:
        return json.loads(_get(view, "SciForgeAutoGeometry", "") or "{}")
    except ValueError:
        return {}


def refresh_auto_marks(view, force=False):
    """Make the automatic centre marks and lines again when the design changed them."""
    if "SciForgeAutoMarks" not in view.PropertiesList and not force:
        return False
    if not has_geometry(view):
        return False
    geometry = auto_mark_geometry(view)
    old = auto_marks_of(view)
    if (
        not force
        and old.get("marks", []) == geometry["marks"]
        and old.get("lines", []) == geometry["lines"]
    ):
        return False
    for tag in list(_get(view, "SciForgeAutoTags", []) or []):
        try:
            view.removeCosmeticEdge(tag)
        except Exception:
            pass
    tags = []
    s = scale_of(view) or 1.0
    for cx, cy, r in geometry["marks"]:
        reach = r + CENTER_EXTENSION / s
        tags.append(
            view.makeCosmeticLine(V(cx - reach, cy, 0), V(cx + reach, cy, 0), LINE_DASHDOT, 0.18)
        )
        tags.append(
            view.makeCosmeticLine(V(cx, cy - reach, 0), V(cx, cy + reach, 0), LINE_DASHDOT, 0.18)
        )
    for x1, y1, x2, y2 in geometry["lines"]:
        tags.append(view.makeCosmeticLine(V(x1, y1, 0), V(x2, y2, 0), LINE_DASHDOT, 0.18))
    _add(view, "App::PropertyStringList", "SciForgeAutoTags", tags)
    _add(view, "App::PropertyString", "SciForgeAutoGeometry", json.dumps(geometry, sort_keys=True))
    try:
        view.recompute()
    except Exception as exc:
        warn("centre marks of %s: %s" % (view.Label, exc))
    return True


# ------------------------------------------------------------------ edge extensions
def _intersection(a, b):
    """Where two lines (each ((x1, y1), (x2, y2))) meet, or None when parallel."""
    (x1, y1), (x2, y2) = a
    (x3, y3), (x4, y4) = b
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return x1 + t * (x2 - x1), y1 + t * (y2 - y1)


def extensions_of(view):
    try:
        return [json.loads(t) for t in _get(view, "SciForgeExtensions", []) or []]
    except ValueError:
        return []


def _save_extensions(view, items):
    _add(
        view,
        "App::PropertyStringList",
        "SciForgeExtensions",
        [json.dumps(i, sort_keys=True) for i in items],
    )


def _extension_cosmetics(view, item):
    """Draw an edge extension: thin lines from both edges' nearer ends to where they
    meet and a point there (to dimension to)."""
    a, b = item["a"], item["b"]
    la = ((a[0], a[1]), (a[2], a[3]))
    lb = ((b[0], b[1]), (b[2], b[3]))
    point = _intersection(la, lb)
    if point is None:
        return None
    tags = []
    for line in (la, lb):
        near = min(line, key=lambda p: math.hypot(p[0] - point[0], p[1] - point[1]))
        if math.hypot(near[0] - point[0], near[1] - point[1]) > 1e-6:
            tags.append(
                view.makeCosmeticLine(V(near[0], near[1], 0), V(point[0], point[1], 0), 1, 0.13)
            )
    vertex = view.makeCosmeticVertex(V(point[0], point[1], 0))
    return {
        "a": a,
        "b": b,
        "edges": item.get("edges", []),
        "tags": tags,
        "vertex": vertex,
        "point": [point[0], point[1]],
    }


def _remove_extension(view, item):
    for tag in item.get("tags", []):
        try:
            view.removeCosmeticEdge(tag)
        except Exception:
            pass
    if item.get("vertex"):
        try:
            view.removeCosmeticVertex(item["vertex"])
        except Exception:
            pass


def add_edge_extension(view, first, second):
    """Fusion's Edge Extension: two straight edges extended to where they would meet
    (a filleted or chamfered corner's sharp corner), with a point there."""
    a, b = edge_info(view, first), edge_info(view, second)
    if not a or not b or a["kind"] != "line" or b["kind"] != "line":
        raise DrawingError("Click two straight edges.")
    sig_a = [a["p1"][0], a["p1"][1], a["p2"][0], a["p2"][1]]
    sig_b = [b["p1"][0], b["p1"][1], b["p2"][0], b["p2"][1]]
    if _intersection((a["p1"], a["p2"]), (b["p1"], b["p2"])) is None:
        raise DrawingError(
            "These edges are parallel: they never meet. Click two edges at an angle."
        )
    if not has_geometry(view):
        raise DrawingError("The view is still being drawn: try again in a moment.")
    item = _extension_cosmetics(view, {"a": sig_a, "b": sig_b, "edges": [first, second]})
    items = extensions_of(view)
    items.append(item)
    _save_extensions(view, items)
    return item


def refresh_extensions(view):
    """Edge extensions follow their edges after the design changed."""
    items = extensions_of(view)
    if not items or not has_geometry(view):
        return False
    from . import drawing_annot

    elems = None
    changed = False
    keep = []
    for item in items:
        if elems is None:
            elems = drawing_annot.elements(view)
        moved = False
        sigs = []
        for key in ("a", "b"):
            anchor = {"ref": "?", "kind": "line", "sig": item[key], "t": 0.5}
            new, did = drawing_annot.resolve_anchor(anchor, elems)
            moved |= did
            sigs.append(new["sig"])
        if not moved:
            keep.append(item)
            continue
        _remove_extension(view, item)
        made = _extension_cosmetics(
            view, {"a": sigs[0], "b": sigs[1], "edges": item.get("edges", [])}
        )
        if made is not None:
            keep.append(made)
        changed = True
    if changed:
        _save_extensions(view, keep)
        try:
            view.recompute()
        except Exception as exc:
            warn("edge extensions of %s: %s" % (view.Label, exc))
    return changed


# ------------------------------------------------------------------ text, balloons, tables
def add_text(page, lines, position, size=3.5, width=None):
    doc = page.Document
    note = doc.addObject(ANNOTATION, "Text")
    note.Text = [str(line) for line in lines] or [""]
    note.TextSize = size
    if width:
        try:
            note.MaxWidth = width
        except Exception:
            pass
    note.X = position[0]
    note.Y = position[1]
    _add_to_page(page, note)
    _mark(note, "DrawingText")
    note.Label = "Text"
    return note


def add_balloon(view, origin, position, text):
    """A balloon pointing at `origin` (page) with its circle at `position` (page)."""
    page = page_of(view)
    doc = view.Document
    balloon = doc.addObject(BALLOON, "Balloon")
    balloon.SourceView = view
    x, y = view_position(view)
    balloon.OriginX = origin[0] - x
    balloon.OriginY = origin[1] - y
    balloon.X = position[0] - x
    balloon.Y = position[1] - y
    balloon.Text = str(text)
    balloon.BubbleShape = "Circular"
    balloon.EndType = "Filled arrow"
    page.addView(balloon)
    _mark(balloon, "Balloon")
    return balloon


def balloon_page_points(balloon):
    view = balloon.SourceView
    x, y = view_position(view) if view is not None else (0.0, 0.0)
    return (
        (x + _value(balloon.OriginX), y + _value(balloon.OriginY)),
        (x + _value(balloon.X), y + _value(balloon.Y)),
    )


def parts_list_of(page):
    for obj in annotations(page):
        if kind(obj) == "PartsList":
            return obj
    return None


def parts_rows_for(view):
    sources = _view_sources(view)
    comps = components_of(sources)
    rows = core.parts_rows(comps)
    by_key = {}
    for comp in comps:
        by_key[comp["key"]] = comp
    for row in rows:
        row["bodies"] = [b.Name for key in row["members"] for b in by_key[key]["bodies"]]
    return rows


def add_parts_list(page, view, top_left, balloons=True):
    """Fusion's Table (parts list) for the components a view shows, its top left corner
    at `top_left`; balloons on the view for every row (Fusion adds them too)."""
    if parts_list_of(page) is not None:
        raise DrawingError("This drawing already has a parts list.")
    doc = page.Document
    rows = parts_rows_for(view)
    if not rows:
        raise DrawingError("The view shows no components.")
    table = doc.addObject(SYMBOL, "PartsList")
    _mark(table, "PartsList")
    _add(table, "App::PropertyLink", "SciForgeView", view)
    _add(table, "App::PropertyFloatList", "SciForgeCorner", [top_left[0], top_left[1]])
    table.Label = "Parts List"
    _add_to_page(page, table)
    _draw_table(table, rows, top_left)
    made = []
    if balloons:
        made = add_row_balloons(view, rows)
    return table, made


def _header_at_bottom(page, top_left):
    try:
        height = _value(page.Template.Height)
    except Exception:
        height = core.sheet_size(standard_of(page), sheet_of(page))[1]
    return top_left[1] < height / 2.0


def _draw_table(table, rows, top_left):
    page = page_of(table)
    layout = core.table_layout(rows, header_at_bottom=_header_at_bottom(page, top_left))
    table.Symbol = core.table_svg(layout)
    table.X = top_left[0] + layout["width"] / 2.0
    table.Y = top_left[1] - layout["height"] / 2.0
    _add(table, "App::PropertyString", "SciForgeRows", json.dumps(_plain_rows(rows)))
    return layout


def _plain_rows(rows):
    return [{k: v for k, v in row.items() if k != "members"} for row in rows]


def table_rows(table):
    try:
        return json.loads(table.SciForgeRows)
    except Exception:
        return []


def table_layout_of(table):
    corner = list(_get(table, "SciForgeCorner", []) or [0.0, 0.0])
    page = page_of(table)
    return (
        core.table_layout(table_rows(table), header_at_bottom=_header_at_bottom(page, corner)),
        corner,
    )


def refresh_parts_list(table):
    """The rows follow the components the view shows (a renamed or added component)."""
    view = _get(table, "SciForgeView", None)
    if not alive(view):
        return False
    rows = _plain_rows(parts_rows_for(view))
    if rows == table_rows(table):
        return False
    corner = list(table.SciForgeCorner)
    _draw_table(table, parts_rows_for(view), corner)
    return True


def add_row_balloons(view, rows):
    made = []
    half_w, half_h = view_extent(view)
    centre = view_position(view)
    for i, row in enumerate(rows):
        anchor = component_anchor(view, row.get("bodies", []))
        if anchor is None:
            continue
        spot = core.balloon_spot(centre, anchor, half_w, half_h, i)
        made.append(add_balloon(view, anchor, spot, row["Item"]))
    return made


def component_anchor(view, body_names):
    """A page point on the outline of the given bodies as the view shows them (the middle
    of the longest visible edge that is theirs: an edge where two components touch is the
    nearer one's), for a balloon's arrow."""
    doc = view.Document
    wanted = [doc.getObject(name) for name in body_names]
    wanted = [b for b in wanted if alive(b)]
    if not wanted:
        return None
    names = {b.Name for b in wanted}
    s = scale_of(view) or 1.0
    candidates = []
    for edge in _visible_edges_local(view):
        mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        candidates.append((edge.Length, (mid.x, mid.y)))
    candidates.sort(key=lambda c: -c[0])
    fallback = None
    for _length, (mx, my) in candidates:
        local = (mx / s, my / s)
        if _sight_hit(view, wanted, local) is None:
            continue  # not on these bodies at all
        if fallback is None:
            fallback = (mx, my)
        owner = component_at(view, local)
        if owner is not None and owner.Name in names:
            x, y = view_position(view)
            return x + mx, y + my
    if fallback is None:
        return None
    x, y = view_position(view)
    return x + fallback[0], y + fallback[1]


def _visible_edges_local(view):
    try:
        return list(view.getVisibleEdges(True))
    except Exception:
        return []


def _sight_line(view, local_point):
    """The line through a point of a view along the view's direction, and that direction
    (towards the viewer)."""
    import Part

    axes = axes_of(view)
    p = core.to_model(axes, centre_of(view), local_point[0], local_point[1])
    d = axes[2]
    far = 1e4
    line = Part.makeLine(
        V(*core.v_add(p, core.v_mul(d, far))), V(*core.v_sub(p, core.v_mul(d, far)))
    )
    return line, d


def _sight_hit(view, bodies, local_point, tolerance=0.05):
    """(body, depth) of the body nearest to the viewer that the sight line through a view
    point touches (depth: how far towards the viewer), or None."""
    line, d = _sight_line(view, local_point)
    best = None
    for body in bodies:
        try:
            dist, pairs, _info = body.Shape.distToShape(line)
        except Exception:
            continue
        if dist > tolerance or not pairs:
            continue
        points = [p for p, _q in pairs]
        try:
            # (where the line runs along a face, distToShape gives any one point of it)
            points += [v.Point for v in body.Shape.section(line).Vertexes]
        except Exception:
            pass
        depth = max(core.v_dot((p.x, p.y, p.z), d) for p in points)
        if best is None or depth > best[1] + 1e-6:
            best = (body, depth)
    return best


def component_at(view, local_point, sources=None):
    """The component (or root body) a picked point of a view belongs to: the body nearest
    to the viewer along the sight line through it (where two touch, the one in front)."""
    hit = _sight_hit(view, sources or _view_sources(view), local_point)
    return hit[0] if hit is not None else None


def item_for_body(page, body):
    """The parts-list item number of the component a body is in."""
    table = parts_list_of(page)
    if table is None:
        return None
    for row in table_rows(table):
        if body.Name in row.get("bodies", []):
            return row["Item"]
    return None


# ------------------------------------------------------------------ keeping up with the design
def schema_length_unit():
    """The length unit FreeCAD writes values in now ("mm", "in", ...)."""
    try:
        unit = App.Units.Quantity(1.0, App.Units.Length).getUserPreferred()[2]
        return "in" if unit in ("in", '"') else unit
    except Exception:
        return "mm"


def refresh_dimensions(page):
    """Every dimension's text from its settings (drawing_annot.apply_dimension_text): a
    drawing in other units than FreeCAD's current ones, or a dimension with a tolerance
    or other text, writes its text itself and follows each value."""
    from . import drawing_annot

    return drawing_annot.refresh_dimension_texts(page)


def follow_assembly(page):
    """A Full Assembly drawing shows the design's bodies as they are now: a body or
    component added later comes into the views that show the whole design (and so into
    the parts list). True when the views changed."""
    if _get(page, "SciForgeContents", "") != "Full Assembly":
        return False
    wanted = design_bodies(page.Document)
    if not wanted:
        return False
    old = [s for s in (_get(page, "SciForgeSources", []) or []) if alive(s)]
    names = sorted(b.Name for b in wanted)
    if sorted(b.Name for b in old) == names:
        return False
    old_names = sorted(b.Name for b in old)
    page.SciForgeSources = wanted
    changed = []
    for view in all_views(page):
        current = sorted(s.Name for s in _view_sources(view))
        if current == old_names or not current:
            if has_breakout(view):
                from . import drawing_breakout

                drawing_breakout.set_sources(view, wanted)  # its trimmed copy follows
            elif any(kind(s) == "DrawingDepth" for s in view.Source):
                # (an isometric view showing its parent's breakout)
                _add(view, "App::PropertyLinkListGlobal", "SciForgeCutSources", list(wanted))
            else:
                view.Source = list(wanted)
            changed.append(view)
    for view in sorted(changed, key=lambda v: v.ID):
        try:
            view.recompute()
        except Exception as exc:
            warn("view %s: %s" % (view.Label, exc))
    log("drawing %s shows %d bodies now" % (page.Label, len(wanted)))
    return True


def refresh(page):
    """After the design changed: the bodies a Full Assembly drawing shows, title block,
    parts list, centre marks. True when anything changed."""
    changed = False
    try:
        changed |= follow_assembly(page)
    except Exception as exc:
        warn("drawing contents: %s" % exc)
    try:
        changed |= refresh_title(page)
    except Exception as exc:
        warn("drawing title block: %s" % exc)
    try:
        changed |= refresh_dimensions(page)
    except Exception as exc:
        warn("dimensions: %s" % exc)
    for view in all_views(page):
        try:
            if has_breakout(view):
                from . import drawing_breakout

                changed |= drawing_breakout.refresh(view)
            else:
                changed |= refresh_depth(view)
        except Exception as exc:
            warn("section depth / breakout of %s: %s" % (view.Label, exc))
    table = parts_list_of(page)
    if table is not None:
        try:
            changed |= refresh_parts_list(table)
        except Exception as exc:
            warn("parts list: %s" % exc)
    for view in all_views(page):
        try:
            changed |= follow_center_marks(view)
        except Exception as exc:
            warn("centre marks of %s: %s" % (view.Label, exc))
        try:
            changed |= refresh_auto_marks(view)
        except Exception as exc:
            warn("automatic centre marks of %s: %s" % (view.Label, exc))
        try:
            changed |= refresh_extensions(view)
        except Exception as exc:
            warn("edge extensions of %s: %s" % (view.Label, exc))
    try:
        from . import drawing_annot

        changed |= drawing_annot.follow(page, geometry=True)
    except Exception as exc:
        warn("annotations: %s" % exc)
    return changed


# ------------------------------------------------------------------ deleting
def dependents(obj):
    """What goes with a drawing object when it is deleted (Fusion: a view takes its
    dimensions, balloons, and the views made from it)."""
    found = []
    todo = [obj]
    seen = set()
    while todo:
        current = todo.pop()
        if current.Name in seen:
            continue
        seen.add(current.Name)
        found.append(current)
        for user in getattr(current, "InList", []):
            if user.TypeId in (DIMENSION, BALLOON, SECTION, DETAIL, BROKEN, COMPLEX):
                todo.append(user)
            elif user.TypeId == SYMBOL and kind(user) in ("PartsList", "DrawingAnnotation"):
                todo.append(user)
            elif is_view(user) and same(_get(user, "SciForgeParent", None), current):
                todo.append(user)
        if current.TypeId == GROUP:
            todo += list(current.Views)
    return found


def delete_objects(doc, objects):
    """Delete drawing objects and what depends on them (Fusion: a view takes its
    dimensions, balloons and the views made from it along). Returns the deleted names."""
    names = []
    for obj in objects:
        if not alive(obj):
            continue
        for target in dependents(obj):
            if target.Name not in names:
                names.append(target.Name)
    # a broken view's original comes back; its break line goes
    for name in list(names):
        obj = doc.getObject(name)
        if obj is not None and obj.TypeId == BROKEN:
            original = _get(obj, "SciForgeBrokenOf", None)
            if alive(original) and original.Name not in names:
                _set_shown(original, True)
            for marker in obj.Breaks:
                if marker.Name not in names:
                    names.append(marker.Name)
        # a section's cut line (several segments) and a breakout's trimmed copy go with it
        if obj is not None and is_view(obj):
            for helper in (
                _get(obj, "CuttingToolWireObject", None),
                _get(obj, "SciForgeDepthClip", None),
            ):
                if alive(helper) and helper.Name not in names:
                    names.append(helper.Name)
    rank = {DIMENSION: 0, BALLOON: 0, SYMBOL: 0, ANNOTATION: 0}
    order = [doc.getObject(n) for n in names if doc.getObject(n) is not None]
    order.sort(key=lambda o: (rank.get(o.TypeId, 1), -o.ID))
    removed = []
    for obj in order:
        if not alive(obj):
            continue
        try:
            page = page_of(obj)
            name = obj.Name
            if page is not None and obj in list(page.Views):
                try:
                    page.removeView(obj)
                except Exception:
                    pass
            doc.removeObject(name)
            removed.append(name)
        except Exception as exc:
            warn("could not delete %s: %s" % (getattr(obj, "Label", "?"), exc))
    return removed


def delete_drawing(page):
    """A whole drawing: its views, annotations and its sheet."""
    doc = page.Document
    objects = list(page.Views)
    removed = delete_objects(doc, objects)
    template = _get(page, "Template", None)
    name = page.Name
    doc.removeObject(name)
    if alive(template):
        doc.removeObject(template.Name)
    return removed + [name]


# ------------------------------------------------------------------ export
def export_pdf(page, path):
    """The sheet as a PDF (needs FreeCAD's GUI: TechDraw prints its own page view)."""
    import TechDrawGui

    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    TechDrawGui.exportPageAsPdf(page, path)
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise DrawingError("The PDF could not be written to %s." % path)
    return path


def export_dxf(page, path):
    """The sheet as a DXF (R12): frame and title block, every view (visible, hidden,
    centre lines on their own layers), dimensions, text, balloons and the parts list."""
    dxf = core.DxfWriter()
    dxf.layer("SHEET", 7)
    dxf.layer("VISIBLE", 7)
    dxf.layer("HIDDEN", 8, "HIDDEN")
    dxf.layer("CENTER", 1, "CENTER")
    dxf.layer("HATCH", 8)
    dxf.layer("DIMENSIONS", 3)
    dxf.layer("TEXT", 7)
    dxf.layer("TABLE", 7)
    standard, sheet = standard_of(page), sheet_of(page)
    values = title(page)
    for prim in core.template_primitives(
        standard, sheet, values, bool(_get(page, "SciForgeTitleBlock", True))
    ):
        if prim[0] == "line":
            dxf.line(prim[1], prim[2], prim[3], prim[4], "SHEET")
        elif prim[0] == "circle":
            dxf.circle(prim[1], prim[2], prim[3], "SHEET")
        elif prim[4]:
            align = {"middle": "center", "end": "right"}.get(prim[6], "left")
            dxf.text(prim[1], prim[2], prim[3], prim[4], "SHEET", align)
    for view in all_views(page):
        if not _get(view, "Visibility", True):
            continue
        _dxf_view(dxf, view)
    for obj in annotations(page):
        try:
            if obj.TypeId == DIMENSION:
                _dxf_dimension(dxf, obj)
            elif obj.TypeId == ANNOTATION:
                lines = list(obj.Text)
                size = _value(obj.TextSize)
                x, y = _value(obj.X), _value(obj.Y)
                top = y + (len(lines) - 1) * size * 0.75
                for i, line in enumerate(lines):
                    dxf.text(x, top - i * size * 1.5, size, line, "TEXT", "center")
            elif obj.TypeId == BALLOON:
                _dxf_balloon(dxf, obj)
            elif kind(obj) == "DrawingAnnotation":
                from . import drawing_annot

                drawing_annot.to_dxf(dxf, obj)
            elif kind(obj) == "PartsList":
                layout, corner = table_layout_of(obj)
                for x1, y1, x2, y2, _w in layout["lines"]:
                    dxf.line(
                        corner[0] + x1, corner[1] + y1, corner[0] + x2, corner[1] + y2, "TABLE"
                    )
                for x, y, size, text, anchor in layout["texts"]:
                    dxf.text(
                        corner[0] + x,
                        corner[1] + y,
                        size,
                        text,
                        "TABLE",
                        "center" if anchor == "middle" else "left",
                    )
        except Exception as exc:
            warn("DXF: %s: %s" % (getattr(obj, "Label", "?"), exc))
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(dxf.to_text())
    return path


def _dxf_edge(dxf, edge, ox, oy, layer):
    import Part

    curve = edge.Curve
    if isinstance(curve, Part.Circle):
        c = curve.Center
        r = curve.Radius
        if edge.isClosed():
            dxf.circle(ox + c.x, oy + c.y, r, layer)
            return
        a = edge.valueAt(edge.FirstParameter)
        b = edge.valueAt(edge.LastParameter)
        m = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        start = math.degrees(math.atan2(a.y - c.y, a.x - c.x))
        end = math.degrees(math.atan2(b.y - c.y, b.x - c.x))
        mid = math.degrees(math.atan2(m.y - c.y, m.x - c.x))
        # counter-clockwise from start must pass through mid; else swap
        if (mid - start) % 360.0 > (end - start) % 360.0:
            start, end = end, start
        dxf.arc(ox + c.x, oy + c.y, r, start, end, layer)
        return
    if curve.__class__.__name__ in ("Line", "LineSegment"):
        a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        dxf.line(ox + a.x, oy + a.y, ox + b.x, oy + b.y, layer)
        return
    try:
        points = edge.discretize(Deflection=0.02)
    except Exception:
        points = [edge.Vertexes[0].Point, edge.Vertexes[-1].Point]
    dxf.polyline([(ox + p.x, oy + p.y) for p in points], layer)


def _same_segment(edge, segments):
    try:
        a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    except Exception:
        return False
    for p, q in segments:
        if (
            math.hypot(a.x - p[0], a.y - p[1]) < 1e-4 and math.hypot(b.x - q[0], b.y - q[1]) < 1e-4
        ) or (
            math.hypot(a.x - q[0], a.y - q[1]) < 1e-4 and math.hypot(b.x - p[0], b.y - p[1]) < 1e-4
        ):
            return True
    return False


def _dxf_view(dxf, view):
    ox, oy = view_position(view)
    s = scale_of(view)
    marks = []
    for mark in center_marks(view):
        cx, cy = mark["c"]
        reach = mark["r"] + CENTER_EXTENSION / (s or 1.0)
        marks.append(((s * (cx - reach), s * cy), (s * (cx + reach), s * cy)))
        marks.append(((s * cx, s * (cy - reach)), (s * cx, s * (cy + reach))))
    auto = auto_marks_of(view)
    for cx, cy, r in auto.get("marks", []):
        reach = r + CENTER_EXTENSION / (s or 1.0)
        marks.append(((s * (cx - reach), s * cy), (s * (cx + reach), s * cy)))
        marks.append(((s * cx, s * (cy - reach)), (s * cx, s * (cy + reach))))
    for x1, y1, x2, y2 in auto.get("lines", []):
        marks.append(((s * x1, s * y1), (s * x2, s * y2)))
    for p, q in marks:
        dxf.line(ox + p[0], oy + p[1], ox + q[0], oy + q[1], "CENTER")
    for item in extensions_of(view):
        point = item.get("point")
        for key in ("a", "b"):
            sig = item.get(key) or []
            if point and len(sig) == 4:
                ends = ((sig[0], sig[1]), (sig[2], sig[3]))
                near = min(ends, key=lambda e: math.hypot(e[0] - point[0], e[1] - point[1]))
                a = local_to_page(view, near)
                b = local_to_page(view, point)
                dxf.line(a[0], a[1], b[0], b[1], "VISIBLE")
    hatch = []
    if has_breakout(view):
        from . import drawing_breakout

        for x1, y1, x2, y2 in drawing_breakout.hatch_of(view):
            hatch.append(((s * x1, s * y1), (s * x2, s * y2)))
    from . import drawing_depth

    def deeper(edge):
        return is_section(view) and drawing_depth.is_hidden(view, edge, s)

    try:
        visible = view.getVisibleEdges(True)
    except Exception:
        visible = []
    for edge in visible:
        if _same_segment(edge, marks) or _same_segment(edge, hatch) or deeper(edge):
            continue
        _dxf_edge(dxf, edge, ox, oy, "VISIBLE")
    for p, q in hatch:
        dxf.line(ox + p[0], oy + p[1], ox + q[0], oy + q[1], "HATCH")
    if _get(view, "HardHidden", False):
        try:
            for edge in view.getHiddenEdges(True):
                if not deeper(edge):
                    _dxf_edge(dxf, edge, ox, oy, "HIDDEN")
        except Exception:
            pass
    label = _get(view, "Caption", "") or ""
    if label:
        half_w, half_h = view_extent(view)
        dxf.text(ox, oy - half_h - 7.0, 3.5, label, "TEXT", "center")
    if is_section(view):
        _dxf_section_line(dxf, view)
        if _get(view, "CutSurfaceDisplay", "") != "Hide" and view.TypeId == SECTION:
            try:
                for a, b in section_hatch(view):
                    dxf.line(ox + a[0], oy + a[1], ox + b[0], oy + b[1], "HATCH")
            except Exception as exc:
                warn("DXF: hatching of %s: %s" % (view.Label, exc))
    if view.TypeId == DETAIL:
        parent = view.BaseView
        if alive(parent):
            px, py = local_to_page(parent, (view.AnchorPoint.x, view.AnchorPoint.y))
            r = _value(view.Radius) * scale_of(parent)
            dxf.circle(px, py, r, "CENTER")
            dxf.text(px + r * 0.75, py + r * 0.75, 3.5, view.Reference, "TEXT", "left")


def section_faces(section):
    """The faces a section cuts, in the section view's own coordinates (unscaled, from
    its centre; the faces lie in a plane square to the view's direction)."""
    import Part

    # (TechDraw cuts what the parent view shows)
    parent = _get(section, "BaseView", None)
    sources = [s for s in getattr(parent, "Source", []) if alive(s)] if alive(parent) else []
    sources = sources or [s for s in section.Source if alive(s)]
    shapes = [s.Shape for s in sources if not s.Shape.isNull()]
    if not shapes:
        return []
    normal = section.SectionNormal
    origin = section.SectionOrigin
    wires = Part.makeCompound(shapes).slice(normal, normal.dot(origin))
    if not wires:
        return []
    face = Part.makeFace(wires, "Part::FaceMakerBullseye")
    x, y, d = axes_of(section)
    c = centre_of(section)
    matrix = App.Matrix(x[0], x[1], x[2], 0, y[0], y[1], y[2], 0, d[0], d[1], d[2], 0)
    matrix.move(matrix.multVec(V(-c[0], -c[1], -c[2])))
    return face.transformed(matrix).Faces


def section_hatch(section, spacing=HATCH_SPACING):
    """The hatch lines of a section's cut faces on the paper, relative to the view's
    position: [((x1, y1), (x2, y2))]. For the DXF (the sheet shows TechDraw's own)."""
    import Part

    s = scale_of(section) or 1.0
    found = []
    for face in section_faces(section):
        box = face.BoundBox
        z = (box.ZMin + box.ZMax) / 2.0
        for a, b in core.hatch_lines((box.XMin, box.YMin, box.XMax, box.YMax), spacing / s, 45.0):
            line = Part.LineSegment(V(a[0], a[1], z), V(b[0], b[1], z)).toShape()
            for edge in face.common(line).Edges:
                p, q = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
                if (q - p).Length > 1e-6:
                    found.append(((s * p.x, s * p.y), (s * q.x, s * q.y)))
    return found


def _dxf_section_line(dxf, section):
    parent = section.BaseView
    line = section_line_of(section)
    if not alive(parent) or line is None:
        return
    p1, p2, _side = line
    pts = section_points(section) or [p1, p2]
    for q1, q2 in zip(pts, pts[1:]):
        qa = local_to_page(parent, q1)
        qb = local_to_page(parent, q2)
        dxf.line(qa[0], qa[1], qb[0], qb[1], "CENTER")
    a = local_to_page(parent, pts[0])
    b = local_to_page(parent, pts[-1])
    info = core.section_line(p1, p2, _side, page_of(section).ProjectionType)
    if info is None:
        return
    # arrows at both ends point the way the section is seen (against `look`)
    lx, ly = -info["look"][0], -info["look"][1]
    for end in (a, b):
        tail = (end[0] - lx * 8.0, end[1] - ly * 8.0)
        dxf.line(tail[0], tail[1], end[0], end[1], "DIMENSIONS")
        _arrow(dxf, end, (lx, ly), "DIMENSIONS")
        dxf.text(
            tail[0] - lx * 4.0, tail[1] - ly * 4.0, 5.0, section.SectionSymbol, "TEXT", "center"
        )


def _arrow(dxf, tip, direction, layer, length=3.0, width=1.0):
    dx, dy = direction
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    bx, by = tip[0] - dx * length, tip[1] - dy * length
    dxf.solid(
        [(tip[0], tip[1]), (bx - dy * width, by + dx * width), (bx + dy * width, by - dx * width)],
        layer,
    )


def _dxf_dimension(dxf, dim):
    if not dim.References2D:
        return
    view = dim.References2D[0][0]
    ox, oy = view_position(view)
    text = dimension_text(dim)
    lx, ly = ox + _value(dim.X), oy + _value(dim.Y)
    layer = "DIMENSIONS"
    if dim.Type in core.LINEAR_TYPES:
        p, q = dim.getLinearPoints()  # (y down, from the view's centre)
        a = (ox + p.x, oy - p.y)
        b = (ox + q.x, oy - q.y)
        if dim.Type == "DistanceX":
            a2, b2 = (a[0], ly), (b[0], ly)
        elif dim.Type == "DistanceY":
            a2, b2 = (lx, a[1]), (lx, b[1])
        else:
            ux, uy = b[0] - a[0], b[1] - a[1]
            n = math.hypot(ux, uy) or 1.0
            nx, ny = -uy / n, ux / n
            off = (lx - a[0]) * nx + (ly - a[1]) * ny
            a2 = (a[0] + nx * off, a[1] + ny * off)
            b2 = (b[0] + nx * off, b[1] + ny * off)
        dxf.line(a[0], a[1], a2[0], a2[1], layer)
        dxf.line(b[0], b[1], b2[0], b2[1], layer)
        dxf.line(a2[0], a2[1], b2[0], b2[1], layer)
        _arrow(dxf, a2, (a2[0] - b2[0], a2[1] - b2[1]), layer)
        _arrow(dxf, b2, (b2[0] - a2[0], b2[1] - a2[1]), layer)
        dxf.text(lx, ly + 1.0, 3.5, text, layer, "center")
    elif dim.Type in ("Radius", "Diameter"):
        name = dim.References2D[0][1]
        info = edge_info(view, name if isinstance(name, str) else name[0])
        if info and "center" in info:
            s = scale_of(view)
            cx, cy = ox + info["center"][0] * s, oy + info["center"][1] * s
            r = info["radius"] * s
            ux, uy = lx - cx, ly - cy
            n = math.hypot(ux, uy) or 1.0
            ux, uy = ux / n, uy / n
            tip = (cx + ux * r, cy + uy * r)
            start = (cx - ux * r, cy - uy * r) if dim.Type == "Diameter" else (cx, cy)
            dxf.line(start[0], start[1], lx, ly, layer)
            _arrow(dxf, tip, (ux, uy), layer)
            if dim.Type == "Diameter":
                _arrow(dxf, start, (-ux, -uy), layer)
        dxf.text(lx, ly + 1.0, 3.5, text, layer, "center")
    else:
        dxf.text(lx, ly, 3.5, text, layer, "center")


def _dxf_balloon(dxf, balloon):
    origin, spot = balloon_page_points(balloon)
    r = 4.0
    dx, dy = origin[0] - spot[0], origin[1] - spot[1]
    n = math.hypot(dx, dy) or 1.0
    start = (spot[0] + dx / n * r, spot[1] + dy / n * r)
    dxf.circle(spot[0], spot[1], r, "DIMENSIONS")
    dxf.line(start[0], start[1], origin[0], origin[1], "DIMENSIONS")
    _arrow(dxf, origin, (dx, dy), "DIMENSIONS")
    dxf.text(spot[0], spot[1] - 1.75, 3.5, balloon.Text, "DIMENSIONS", "center")
