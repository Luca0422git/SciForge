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
BROKEN = "TechDraw::DrawBrokenView"
DIMENSION = "TechDraw::DrawViewDimension"
BALLOON = "TechDraw::DrawViewBalloon"
ANNOTATION = "TechDraw::DrawViewAnnotation"
SYMBOL = "TechDraw::DrawViewSymbol"
VIEW_TYPES = (ITEM, PART_VIEW, SECTION, DETAIL, BROKEN)
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


def is_view(obj):
    try:
        return obj.TypeId in VIEW_TYPES
    except Exception:
        return False


def drawings(doc):
    """The design's drawings (its TechDraw pages), in the order they were made."""
    if doc is None:
        return []
    return sorted([o for o in doc.Objects if o.TypeId == PAGE], key=lambda o: o.ID)


def page_of(obj):
    """The drawing an object of it belongs to."""
    if obj is None:
        return None
    if is_page(obj):
        return obj
    try:
        page = obj.findParentPage()
        if page is not None:
            return page
    except Exception:
        pass
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
    doc, sources, standard="ISO", units="mm", sheet=None, title_block=True, label=None
):
    """A new drawing (Fusion: File > New Drawing > From Design) with an empty sheet."""
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
    _add(page, "App::PropertyLinkList", "SciForgeSources", sources)
    _add(page, "App::PropertyStringList", "SciForgeTitleEdits", [])
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
        "Sheet": "1 / 1",
        "Standard": standard,
    }


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
            target.Caption = target.Label


def add_projected(parent, kind_name, x, y):
    """A projected view of `parent` (Fusion's Projected View) at page point (x, y)."""
    page = page_of(parent)
    doc = parent.Document
    existing = [v for v in children_of(parent) if _get(v, "SciForgeKind", "") == kind_name]
    if existing:
        raise DrawingError("There is already a %s view of that view." % _kind_label(kind_name))
    direction, xdir = core.projected_axes(axes_of(parent), kind_name)
    view = doc.addObject(PART_VIEW, "ProjectedView")
    view.Source = list(parent.Source)
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
    if view.TypeId == SECTION:
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
        if view.TypeId == SECTION:
            parent = _get(view, "BaseView", None)
        if not alive(parent):
            continue
        axis = _axis_of(view)
        if axis is None and view.TypeId == SECTION:
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


def add_section(parent, p1, p2, side, position, label=None, scale=None):
    """Section View: cut along the line p1-p2 (parent view coordinates) and look from the
    side the view is placed on (third angle) or from the other side (first angle)."""
    page = page_of(parent)
    doc = parent.Document
    projection = page.ProjectionType
    line = core.section_line(p1, p2, side, projection)
    if line is None:
        raise DrawingError("The section line has no length: click two different points.")
    axes = axes_of(parent)
    direction, xdir, normal = core.section_axes(axes, line)
    mid = line["mid"]
    origin = core.to_model(axes, centre_of(parent), mid[0], mid[1])
    label = label or core.next_label(used_labels(page))
    section = doc.addObject(SECTION, "Section")
    section.Source = list(parent.Source)
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
    _hatch(section)
    _add_to_page(page, section)
    section.BaseView = parent
    _mark(section, "CutView")  # (a "Section" type would be an analysis in the browser)
    _add(section, "App::PropertyStringList", "SciForgeLine", [json.dumps([p1, p2, side])])
    px, py = view_position(parent)
    _add(section, "App::PropertyFloatList", "SciForgeOffset", [position[0] - px, position[1] - py])
    _style(section, style_of(parent), tangent_of(parent))
    section.HardHidden = False  # Fusion's section views show no hidden edges by default
    section.SmoothHidden = False
    section.Label = section_caption(label)
    section.Caption = section.Label  # written under the view, also in the PDF
    return section


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
    detail.Source = list(parent.Source)
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
    detail.Caption = detail.Label
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
    import Sketcher  # noqa: F401
    import Part

    axes = axes_of(view)
    centre = centre_of(view)
    half_w, half_h = view_extent(view)
    s = scale_of(view) or 1.0
    reach = (max(half_w, half_h) / s) + 5.0
    xa, ya, da = axes
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
    marker = doc.addObject("Sketcher::SketchObject", "DrawingBreak")
    marker.Placement = App.Placement(matrix)
    for end in (a, b):
        if horizontal:
            p, q = V(end[0], -reach, 0), V(end[0], reach, 0)
        else:
            p, q = V(-reach, end[1], 0), V(reach, end[1], 0)
        marker.addGeometry(Part.LineSegment(p, q))
    marker.Visibility = False
    try:
        if marker.ViewObject is not None:
            marker.ViewObject.Visibility = False
    except Exception:
        pass
    _mark(marker, "DrawingBreak")
    broken = doc.addObject(BROKEN, "BrokenView")
    broken.Source = list(view.Source)
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
    sources = [s for s in getattr(view, "Source", []) if alive(s)]
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
    """A page point on the outline of the given bodies as the view shows them (a visible
    edge's middle), for a balloon's arrow."""
    doc = view.Document
    shapes = []
    for name in body_names:
        body = doc.getObject(name)
        if alive(body):
            shapes.append(body.Shape)
    if not shapes:
        return None
    axes = axes_of(view)
    centre = centre_of(view)
    s = scale_of(view)
    best = None
    for edge in _visible_edges_local(view):
        mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        u, v = mid.x / s, mid.y / s
        hit = _depth_hit(shapes, axes, centre, u, v)
        if hit is None:
            continue
        if best is None or hit < best[0]:
            best = (hit, (mid.x, mid.y))
    if best is None:
        return None
    x, y = view_position(view)
    return x + best[1][0], y + best[1][1]


def _visible_edges_local(view):
    try:
        return list(view.getVisibleEdges(True))
    except Exception:
        return []


def _depth_hit(shapes, axes, centre, u, v):
    """Distance from a view point's sight line to the nearest of `shapes` (0 = on it)."""
    import Part

    x, y, d = axes
    p = core.to_model(axes, centre, u, v)
    far = 1e4
    a = V(*core.v_add(p, core.v_mul(d, far)))
    b = V(*core.v_sub(p, core.v_mul(d, far)))
    line = Part.makeLine(a, b)
    best = None
    for shape in shapes:
        try:
            dist = shape.distToShape(line)[0]
        except Exception:
            continue
        if best is None or dist < best:
            best = dist
    if best is None or best > 1e-3:
        return None
    return best


def component_at(view, local_point, sources=None):
    """The component (or root body) a picked point of a view belongs to: the nearest
    body along the sight line through it."""
    import Part

    doc = view.Document
    axes = axes_of(view)
    centre = centre_of(view)
    p = core.to_model(axes, centre, local_point[0], local_point[1])
    far = 1e4
    d = axes[2]
    line = Part.makeLine(
        V(*core.v_add(p, core.v_mul(d, far))), V(*core.v_sub(p, core.v_mul(d, far)))
    )
    best = None
    for body in sources or [s for s in view.Source if alive(s)]:
        try:
            dist = body.Shape.distToShape(line)[0]
        except Exception:
            continue
        if best is None or dist < best[0]:
            best = (dist, body)
    if best is None or best[0] > 0.05:
        return None
    del doc
    return best[1]


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
    """A drawing in other units than FreeCAD's current ones writes its dimensions itself
    (TechDraw formats in the current units only): the text follows each value."""
    units = units_of(page)
    native = schema_length_unit() == units
    changed = False
    for dim in annotations(page):
        if dim.TypeId != DIMENSION:
            continue
        angular = dim.Type in ("Angle", "Angle3Pt")
        if native or angular:
            if dim.Arbitrary and _get(dim, "SciForgeOwnText", False):
                dim.Arbitrary = False
                dim.FormatSpec = core.dimension_format(units, standard_of(page), dim.Type)
                changed = True
            continue
        text = dimension_text(dim)
        if not text:
            continue
        if not dim.Arbitrary or dim.FormatSpec != text:
            dim.Arbitrary = True
            dim.FormatSpec = text
            _add(dim, "App::PropertyBool", "SciForgeOwnText", True)
            changed = True
    return changed


def refresh(page):
    """After the design changed: title block, parts list, centre marks. True when
    anything changed."""
    changed = False
    try:
        changed |= refresh_title(page)
    except Exception as exc:
        warn("drawing title block: %s" % exc)
    try:
        changed |= refresh_dimensions(page)
    except Exception as exc:
        warn("dimensions: %s" % exc)
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
            if user.TypeId in (DIMENSION, BALLOON, SECTION, DETAIL, BROKEN):
                todo.append(user)
            elif user.TypeId == SYMBOL and kind(user) == "PartsList":
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
    for p, q in marks:
        dxf.line(ox + p[0], oy + p[1], ox + q[0], oy + q[1], "CENTER")
    try:
        visible = view.getVisibleEdges(True)
    except Exception:
        visible = []
    for edge in visible:
        if _same_segment(edge, marks):
            continue
        _dxf_edge(dxf, edge, ox, oy, "VISIBLE")
    if _get(view, "HardHidden", False):
        try:
            for edge in view.getHiddenEdges(True):
                _dxf_edge(dxf, edge, ox, oy, "HIDDEN")
        except Exception:
            pass
    label = ""
    if view.TypeId == SECTION:
        label = "SECTION %s-%s" % (view.SectionSymbol, view.SectionSymbol)
    elif view.TypeId == DETAIL:
        label = "DETAIL %s (%s)" % (view.Reference, core.format_scale(s))
    if label:
        half_w, half_h = view_extent(view)
        dxf.text(ox, oy - half_h - 7.0, 3.5, label, "TEXT", "center")
    if view.TypeId == SECTION:
        _dxf_section_line(dxf, view)
        if _get(view, "CutSurfaceDisplay", "") != "Hide":
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

    shapes = [s.Shape for s in section.Source if alive(s) and not s.Shape.isNull()]
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
    a = local_to_page(parent, p1)
    b = local_to_page(parent, p2)
    dxf.line(a[0], a[1], b[0], b[1], "CENTER")
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
        p, q = dim.getLinearPoints()
        a = (ox + p.x, oy + p.y)
        b = (ox + q.x, oy + q.y)
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
