# SPDX-License-Identifier: LGPL-2.1-or-later
"""What an export leaves out and what an import skipped, the rules without FreeCAD or Qt
(unit tested: SciForgeTests/unit/test_export_report_core.py). export_report.py counts what
the design has (the "facts"); this module turns the counts into short sentences, only for
what this design really had, so a part with nothing to lose gives no message at all.

Never drop data silently (docs/sciforge/dev/cadcraft-lessons.md, idea 2). Every rule below
was checked against what FreeCAD 1.1.4 really writes and reads back (round trips in
SciForgeTests/golden/export_checks.py and the scenario export_report; findings in
docs/sciforge/sessions/2026-10-21-export-report.md):

  every 3D file  holds finished shapes: no timeline, sketches, construction geometry,
                 parameters, joints, physical materials, cosmetic threads, decals or canvases;
  STEP           keeps components, copies and colours (colours only with the window open:
                 FreeCAD's headless writer has no colours); see-through looks come out
                 opaque; bodies come back named Body1, Body2 ... inside a component (a single
                 body at the design's root keeps its name);
  IGES           solids only: no components, no colours, no names;
  STL            one mesh: no names, no colours, no unit (the numbers are in the unit chosen
                 but the file cannot say which); curved faces become flat triangles;
  3MF            one object per body with its name and the unit; no colours, no components;
  OBJ            named groups; no colours (no material file), no unit, no components;
  DXF of a sketch  curves only (lines, arcs, circles, ellipses, splines): no dimensions or
                 constraints, no construction geometry, no points, no projected curves, and
                 flat in the sketch's own X and Y;
  drawing DXF    SciForge's own writer: dimensions and symbols as plain lines and text,
                 curves that are not circles or arcs as short straight lines, hatching as
                 separate lines, text without a named font;
  drawing PDF    what the sheet shows (hidden views are not on it).

An item is {"key", "count", "text"}; `formats` is added when reports of several files are
combined (Export Everything).
"""

import re
import xml.etree.ElementTree as ElementTree

# -- formats ---------------------------------------------------------------------------------
FORMAT_NAMES = {
    "step": "STEP",
    "iges": "IGES",
    "stl": "STL",
    "stl_ascii": "STL",
    "3mf": "3MF",
    "obj": "OBJ",
    "brep": "BREP",
    "dxf": "DXF",
    "dwg": "DWG",
    "drawing_pdf": "PDF",
    "drawing_dxf": "DXF",
}
SOLID_FORMATS = ("step", "iges", "stl", "stl_ascii", "3mf", "obj", "brep")
EXACT_FORMATS = ("step", "iges", "brep")  # exact solids only (no mesh bodies)
MESH_FORMATS = ("stl", "stl_ascii", "3mf", "obj")
FLAT_FORMATS = ("dxf", "dwg")
DRAWING_FORMATS = ("drawing_pdf", "drawing_dxf")
_ALIASES = {
    "stp": "step",
    "igs": "iges",
    "brp": "brep",
    "stl (binary)": "stl",
    "stl (ascii)": "stl_ascii",
    "pdf": "drawing_pdf",
}

# 3D Print only says what matters for the print (the file goes to a slicer, not to another
# CAD program): what is left out of the print, colours, bodies merged into one, the unit.
PRINT_KEYS = (
    "hidden",
    "hidden_components",
    "surfaces",
    "open_meshes",
    "looks",
    "merged",
    "unit",
    "threads",
)

# items in the order they are listed
ORDER = (
    "hidden",
    "hidden_components",
    "surfaces",
    "meshes",
    "open_meshes",
    "timeline",
    "sketches",
    "construction",
    "parameters",
    "joints",
    "components",
    "merged",
    "names",
    "looks",
    "see_through",
    "materials",
    "threads",
    "pictures",
    "curved",
    "unit",
    # DXF of a sketch
    "dimensions",
    "constraints",
    "construction_curves",
    "points",
    "projected",
    "off_plane",
    # drawings
    "sheets_left",
    "hidden_views",
    "drawing_dimensions",
    "symbols",
    "tables",
    "curves",
    "hatching",
    "fonts",
)


class ReportError(ValueError):
    """A format this module does not know."""


def format_key(fmt):
    """The rule key of an export type: "STEP", "STL (Binary)", "3MF", ".stp", "step" ...
    (a drawing's PDF / DXF: "drawing_pdf" / "drawing_dxf")."""
    text = (fmt or "").strip().lower().lstrip(".")
    text = _ALIASES.get(text, text)
    if text in FORMAT_NAMES:
        return text
    raise ReportError("Unknown export type: %s" % fmt)


def format_name(fmt):
    return FORMAT_NAMES[format_key(fmt)]


# -- words -----------------------------------------------------------------------------------
def plural(count, one, many=None):
    """'1 sketch', '3 sketches' (many: the plural when it is not one + 's')."""
    if count == 1:
        return "1 %s" % one
    return "%d %s" % (count, many or one + "s")


def _bodies(count):
    return plural(count, "body", "bodies")


def _item(key, count, text):
    return {"key": key, "count": int(count), "text": text}


def _mm(value):
    text = ("%.4f" % float(value)).rstrip("0").rstrip(".")
    return text or "0"


UNIT_WORDS = {
    "Millimeter": "millimetres",
    "Centimeter": "centimetres",
    "Meter": "metres",
    "Inch": "inches",
    "Foot": "feet",
}


# -- export ----------------------------------------------------------------------------------
def _n(facts, key):
    try:
        return int(facts.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _left_out(facts, fmt, out):
    """What the export leaves out of the file whatever the format (it was not chosen or the
    format cannot hold that kind of body)."""
    if _n(facts, "hidden"):
        n = _n(facts, "hidden")
        out.append(_item("hidden", n, "%s hidden (only shown bodies are exported)" % _bodies(n)))
    if _n(facts, "hidden_components"):
        n = _n(facts, "hidden_components")
        out.append(
            _item(
                "hidden_components",
                n,
                "%s hidden, with their bodies" % plural(n, "component"),
            )
        )
    if _n(facts, "surfaces"):
        n = _n(facts, "surfaces")
        out.append(
            _item(
                "surfaces",
                n,
                "%s (only solid bodies are exported)" % plural(n, "surface body", "surface bodies"),
            )
        )
    if fmt in EXACT_FORMATS and _n(facts, "meshes"):
        n = _n(facts, "meshes")
        out.append(
            _item(
                "meshes",
                n,
                "%s (%s holds exact solids only: export them as STL, 3MF or OBJ)"
                % (plural(n, "mesh body", "mesh bodies"), FORMAT_NAMES[fmt]),
            )
        )


def _history(facts, out, design_wide=True):
    """What no 3D exchange file holds: how the design was made."""
    n = _n(facts, "timeline")
    if n:
        out.append(
            _item(
                "timeline",
                n,
                "the timeline (%s): the file holds the finished shapes only" % plural(n, "step"),
            )
        )
    n = _n(facts, "sketches")
    if n:
        out.append(_item("sketches", n, plural(n, "sketch", "sketches")))
    n = _n(facts, "construction")
    if n:
        out.append(
            _item(
                "construction",
                n,
                "%s (planes, axes, points)" % plural(n, "construction feature"),
            )
        )
    n = _n(facts, "parameters")
    if n:
        out.append(
            _item("parameters", n, "%s (their values are built in)" % plural(n, "parameter"))
        )
    n = _n(facts, "joints")
    if n and design_wide:
        out.append(
            _item("joints", n, "%s (the parts stay where they are now)" % plural(n, "joint"))
        )


def _material_lines(facts, out):
    n = _n(facts, "materials")
    if n:
        out.append(
            _item(
                "materials",
                n,
                "the physical material of %s (mass and density)" % _bodies(n),
            )
        )
    n = _n(facts, "threads")
    if n:
        out.append(
            _item(
                "threads",
                n,
                "%s (only Modeled threads are real shape)" % plural(n, "cosmetic thread"),
            )
        )
    n = _n(facts, "pictures")
    if n:
        out.append(_item("pictures", n, plural(n, "decal or canvas", "decals and canvases")))


def items(fmt, facts, purpose="file"):
    """The list of what a file of type `fmt` will not keep of the design described by
    `facts` (counts, see export_report.facts). purpose "print": 3D Print, only what matters
    to the print. Empty when nothing is lost."""
    fmt = format_key(fmt)
    facts = facts or {}
    out = []
    if fmt in SOLID_FORMATS:
        _left_out(facts, fmt, out)
        _history(facts, out, design_wide=facts.get("scope", "design") != "bodies")
        comps = _n(facts, "components")
        if comps and fmt != "step":
            out.append(
                _item(
                    "components",
                    comps,
                    "the components (%d): every body is written on its own, flat" % comps,
                )
            )
        solids = _n(facts, "solids")
        meshes = _n(facts, "mesh_bodies")
        together = solids + meshes
        if fmt in ("stl", "stl_ascii") and together > 1 and not facts.get("per_body"):
            out.append(
                _item(
                    "merged",
                    together,
                    "%d bodies become one mesh: no names, no separate parts" % together,
                )
            )
        if fmt == "step":
            n = _n(facts, "names_lost")
            if n:
                out.append(
                    _item(
                        "names",
                        n,
                        "the names of %s (they come back as Body1, Body2 ...)" % _bodies(n),
                    )
                )
        elif fmt in ("iges", "brep") and _n(facts, "names_lost"):
            n = _n(facts, "names_lost")
            out.append(
                _item(
                    "names",
                    n,
                    "the names of %s (%s holds unnamed shapes)" % (_bodies(n), FORMAT_NAMES[fmt]),
                )
            )
        looks = _n(facts, "looks")
        colours_kept = fmt == "step" and bool(facts.get("colours_written"))
        if looks and not colours_kept:
            reason = (
                "FreeCAD writes STEP colours only with the window open"
                if fmt == "step"
                else "the file is written without colours"
            )
            out.append(_item("looks", looks, "the colours of %s (%s)" % (_bodies(looks), reason)))
        n = _n(facts, "see_through")
        if n and colours_kept:
            out.append(
                _item(
                    "see_through",
                    n,
                    "see-through looks on %s (written as solid colours)" % _bodies(n),
                )
            )
        _material_lines(facts, out)
        if fmt in MESH_FORMATS:
            n = _n(facts, "open_meshes")
            if n:
                out.append(
                    _item(
                        "open_meshes",
                        n,
                        "%s not closed (holes): a slicer may complain"
                        % plural(n, "mesh body", "mesh bodies"),
                    )
                )
            n = _n(facts, "curved")
            if n:
                dev = facts.get("deviation")
                within = (" (within %s mm)" % _mm(dev)) if dev else ""
                out.append(
                    _item(
                        "curved",
                        n,
                        "exact curves: %s become small flat triangles%s"
                        % (plural(n, "curved face"), within),
                    )
                )
            unit = facts.get("unit") or "Millimeter"
            if fmt != "3mf" and unit != "Millimeter":
                out.append(
                    _item(
                        "unit",
                        1,
                        "the unit: the numbers are in %s, but the file cannot say so (most "
                        "programs read millimetres)" % UNIT_WORDS.get(unit, unit.lower()),
                    )
                )
    elif fmt in FLAT_FORMATS:
        n = _n(facts, "dimensions")
        if n:
            out.append(_item("dimensions", n, plural(n, "dimension")))
        n = _n(facts, "constraints")
        if n:
            out.append(_item("constraints", n, plural(n, "constraint")))
        n = _n(facts, "construction_curves")
        if n:
            out.append(
                _item(
                    "construction_curves",
                    n,
                    "%s (construction)" % plural(n, "construction curve"),
                )
            )
        n = _n(facts, "points")
        if n:
            out.append(_item("points", n, plural(n, "sketch point")))
        n = _n(facts, "projected")
        if n:
            out.append(_item("projected", n, plural(n, "projected curve")))
        if facts.get("off_plane"):
            out.append(
                _item(
                    "off_plane",
                    1,
                    "where the sketch sits in 3D (the file is flat, in the sketch's own X and Y)",
                )
            )
    else:  # drawings
        n = _n(facts, "sheets_left")
        if n:
            out.append(
                _item(
                    "sheets_left",
                    n,
                    "%s (only the current sheet was exported)" % plural(n, "other sheet"),
                )
            )
        n = _n(facts, "hidden_views")
        if n:
            out.append(_item("hidden_views", n, plural(n, "hidden view")))
        if fmt == "drawing_dxf":
            n = _n(facts, "drawing_dimensions")
            if n:
                out.append(
                    _item(
                        "drawing_dimensions",
                        n,
                        "%s as plain lines and text: they no longer measure the views"
                        % plural(n, "dimension"),
                    )
                )
            n = _n(facts, "symbols")
            if n:
                out.append(
                    _item(
                        "symbols",
                        n,
                        "%s (GD&T, datums, surface finish, notes) as plain lines and text"
                        % plural(n, "symbol"),
                    )
                )
            n = _n(facts, "tables")
            if n:
                out.append(
                    _item("tables", n, "%s as plain lines and text" % plural(n, "parts list"))
                )
            n = _n(facts, "curves")
            if n:
                out.append(
                    _item(
                        "curves",
                        n,
                        "%s that are not circles or arcs, as short straight lines"
                        % plural(n, "curved edge"),
                    )
                )
            n = _n(facts, "hatching")
            if n:
                out.append(
                    _item(
                        "hatching",
                        n,
                        "the hatching of %s as separate lines (no hatch area)"
                        % plural(n, "section view"),
                    )
                )
            if _n(facts, "texts"):
                out.append(
                    _item(
                        "fonts",
                        _n(facts, "texts"),
                        "the font of the text (the DXF names none: other programs use their own)",
                    )
                )
    if purpose == "print":
        out = [i for i in out if i["key"] in PRINT_KEYS]
    rank = {key: n for n, key in enumerate(ORDER)}
    out.sort(key=lambda i: rank.get(i["key"], len(ORDER)))
    return out


def combine(reports):
    """One list for several files written at once (Export Everything): `reports` is
    [(format name, items)]. An item every file loses is listed once; one only some lose
    says which ("the colours of 2 bodies (STL, OBJ)")."""
    names = [name for name, _ in reports]
    found = {}
    order = []
    for name, entries in reports:
        for entry in entries:
            key = (entry["key"], entry["text"])
            if key not in found:
                found[key] = dict(entry, formats=[])
                order.append(key)
            if name not in found[key]["formats"]:
                found[key]["formats"].append(name)
    out = []
    for key in order:
        entry = found[key]
        if len(entry["formats"]) < len(set(names)):
            entry["text"] = "%s (%s)" % (entry["text"], ", ".join(entry["formats"]))
        out.append(entry)
    rank = {key: n for n, key in enumerate(ORDER)}
    out.sort(key=lambda i: rank.get(i["key"], len(ORDER)))
    return out


def summary(file_name, entries, verb="Not in"):
    """One line for the log and the AI: "Not in two.stl: the timeline (6 steps); 2
    sketches." Empty when nothing is lost."""
    if not entries:
        return ""
    return "%s %s: %s." % (verb, file_name, "; ".join(e["text"] for e in entries))


# -- import ----------------------------------------------------------------------------------
def mesh_items(facts):
    """What an inserted mesh file (STL, OBJ, 3MF) has that SciForge does not take, or what
    is wrong with it. facts: open_edges, non_manifold, flipped, pieces, objects (a 3MF's
    objects, which come in as one mesh body), colours (bool), file_unit and unit (a 3MF's
    own unit and the Unit Type it came in with)."""
    facts = facts or {}
    out = []
    n = _n(facts, "open_edges")
    if n:
        out.append(
            _item(
                "open_edges",
                n,
                "the mesh is not closed: %s (holes); it is not a watertight solid"
                % plural(n, "open edge"),
            )
        )
    n = _n(facts, "non_manifold")
    if n:
        out.append(
            _item(
                "non_manifold",
                n,
                "%s shared by more than two triangles" % plural(n, "edge"),
            )
        )
    n = _n(facts, "flipped")
    if n:
        out.append(_item("flipped", n, "%s facing the wrong way" % plural(n, "triangle")))
    n = _n(facts, "objects")
    if n > 1:
        out.append(
            _item(
                "objects",
                n,
                "the file's %d objects came in as one mesh body (their names are not kept)" % n,
            )
        )
    elif _n(facts, "pieces") > 1:
        n = _n(facts, "pieces")
        out.append(_item("pieces", n, "the mesh is %d separate pieces in one body" % n))
    if facts.get("colours"):
        out.append(_item("colours", 1, "the file's colours (Insert Mesh takes the shape only)"))
    file_unit, unit = facts.get("file_unit"), facts.get("unit")
    if file_unit and unit and file_unit != unit:
        out.append(
            _item(
                "unit",
                1,
                "the file says its numbers are in %s; it came in as %s: change Unit Type "
                "if the size is wrong"
                % (UNIT_WORDS.get(file_unit, file_unit), UNIT_WORDS.get(unit, unit)),
            )
        )
    return out


def cad_items(facts):
    """What a STEP / IGES file held that did not come in, or came in changed. facts:
    loose_faces (faces of a part that also has solids: only the solids are taken),
    loose_curves (curves and points: only solids and surfaces are taken), sewn (open
    shells that came in as surface bodies), invalid (bodies whose shape has errors)."""
    facts = facts or {}
    out = []
    n = _n(facts, "loose_faces")
    if n:
        out.append(
            _item(
                "loose_faces",
                n,
                "%s that are not part of a solid (only the solids of those parts came in)"
                % plural(n, "loose face"),
            )
        )
    n = _n(facts, "loose_curves")
    if n:
        out.append(
            _item(
                "loose_curves",
                n,
                "%s (only solids and surfaces are brought in)"
                % plural(n, "curve or point", "curves and points"),
            )
        )
    n = _n(facts, "sewn")
    if n:
        out.append(
            _item(
                "sewn",
                n,
                "%s of loose faces became surface bodies (they do not close into a solid)"
                % plural(n, "set"),
            )
        )
    n = _n(facts, "invalid")
    if n:
        out.append(
            _item(
                "invalid",
                n,
                "%s with geometry errors from the file: later steps on them may fail" % _bodies(n),
            )
        )
    return out


# DXF entities that Insert DXF does not take on purpose (curves go into sketches; FreeCAD's
# importer is told not to bring texts and dimensions, and points are not curves)
DXF_TEXTS = ("TEXT", "MTEXT", "ATTRIB", "ATTDEF", "DIMENSION", "LEADER", "MLEADER", "TOLERANCE")
DXF_POINTS = ("POINT",)


def dxf_facts(stats):
    """facts for curve_items from the statistics FreeCAD's DXF importer returns
    (Import.readDXF: entityCounts, unsupportedFeatures {"Entity type 'HATCH'": [(line,
    handle), ...]})."""
    stats = stats or {}
    counts = dict(stats.get("entityCounts") or {})
    unsupported = {}
    for key, places in (stats.get("unsupportedFeatures") or {}).items():
        match = re.search(r"'([^']+)'", str(key))
        name = match.group(1) if match else str(key)
        try:
            n = len(places)
        except TypeError:
            n = int(places or 0)
        unsupported[name] = unsupported.get(name, 0) + n
    texts = sum(int(counts.get(k, 0)) for k in DXF_TEXTS if k not in unsupported)
    points = sum(int(counts.get(k, 0)) for k in DXF_POINTS if k not in unsupported)
    return {"unsupported": unsupported, "texts": texts, "points": points}


def svg_facts(text):
    """facts for curve_items from an SVG's text: the texts and pictures in it (FreeCAD's
    SVG reader takes paths and shapes only)."""
    texts = images = 0
    try:
        root = ElementTree.fromstring(text)
        for element in root.iter():
            tag = element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""
            if tag == "text":
                texts += 1
            elif tag == "image":
                images += 1
    except Exception:
        texts = len(re.findall(r"<(?:\w+:)?text[\s>]", text or ""))
        images = len(re.findall(r"<(?:\w+:)?image[\s>/]", text or ""))
    return {"texts": texts, "images": images}


DXF_NAMES = {
    "HATCH": ("hatch", "hatches"),
    "SOLID": ("filled area", "filled areas"),
    "3DFACE": ("3D face", "3D faces"),
    "IMAGE": ("picture", "pictures"),
    "WIPEOUT": ("wipeout", "wipeouts"),
    "MESH": ("mesh", "meshes"),
    "3DSOLID": ("3D solid", "3D solids"),
    "REGION": ("region", "regions"),
    "BODY": ("3D body", "3D bodies"),
}


def curve_items(facts, kind="dxf"):
    """What an SVG / DXF held that is not in the sketch. facts: unsupported {entity: n}
    (FreeCAD cannot read them), texts (texts and dimensions), points, images (SVG
    pictures), skipped (curves a sketch could not take), flattened (curves that were not
    flat, laid onto the sketch plane)."""
    facts = facts or {}
    out = []
    for name, n in sorted((facts.get("unsupported") or {}).items()):
        if not n:
            continue
        one, many = DXF_NAMES.get(name, ("%s entity" % name, "%s entities" % name))
        out.append(_item("unsupported", n, "%s (FreeCAD cannot read them)" % plural(n, one, many)))
    n = _n(facts, "texts")
    if n:
        what = "text or dimension" if kind == "dxf" else "text"
        whats = "texts and dimensions" if kind == "dxf" else "texts"
        out.append(
            _item("texts", n, "%s (only curves go into the sketch)" % plural(n, what, whats))
        )
    n = _n(facts, "points")
    if n:
        out.append(_item("points", n, "%s (only curves go into the sketch)" % plural(n, "point")))
    n = _n(facts, "images")
    if n:
        out.append(_item("images", n, plural(n, "picture")))
    n = _n(facts, "skipped")
    if n:
        out.append(_item("skipped", n, "%s a sketch cannot hold" % plural(n, "curve")))
    n = _n(facts, "flattened")
    if n:
        out.append(
            _item(
                "flattened",
                n,
                "%s not flat in the file, laid flat on the sketch" % plural(n, "curve"),
            )
        )
    return out


def open_edges(facets):
    """(open edges, edges shared by more than two triangles) of a mesh given as its
    triangles' point indices [(a, b, c), ...]."""
    count = {}
    for facet in facets:
        a, b, c = facet[0], facet[1], facet[2]
        for p, q in ((a, b), (b, c), (c, a)):
            key = (p, q) if p < q else (q, p)
            count[key] = count.get(key, 0) + 1
    single = sum(1 for v in count.values() if v == 1)
    many = sum(1 for v in count.values() if v > 2)
    return single, many


_UNIT_3MF = {
    "micron": None,
    "millimeter": "Millimeter",
    "centimeter": "Centimeter",
    "meter": "Meter",
    "inch": "Inch",
    "foot": "Foot",
}


def three_mf_facts(model_xml):
    """{objects, colours, file_unit} of a 3MF's 3D/3dmodel.model text: how many mesh
    objects, whether it has colours or materials, the unit it says (default millimetre)."""
    objects = 0
    colours = False
    unit = "millimeter"
    try:
        root = ElementTree.fromstring(model_xml)
        unit = root.attrib.get("unit", "millimeter")
        for element in root.iter():
            tag = element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""
            if tag == "object" and any(
                (c.tag.rsplit("}", 1)[-1] if isinstance(c.tag, str) else "") == "mesh"
                for c in element
            ):
                objects += 1
            elif tag in ("basematerials", "colorgroup", "texture2dgroup", "color"):
                colours = True
    except Exception:
        objects = len(re.findall(r"<(?:\w+:)?mesh[\s>]", model_xml or ""))
        colours = bool(re.search(r"basematerials|colorgroup|displaycolor", model_xml or ""))
        match = re.search(r'<model[^>]*unit="([a-z]+)"', model_xml or "")
        unit = match.group(1) if match else "millimeter"
    return {"objects": objects, "colours": colours, "file_unit": _UNIT_3MF.get(unit)}


def obj_has_colours(text):
    """True when an OBJ names a material file or materials (its colours)."""
    return bool(re.search(r"^\s*(mtllib|usemtl)\s", text or "", re.MULTILINE))


def notice_lines(entries, limit=8):
    """The lines a notice shows: the first `limit` items, then "... and N more"."""
    lines = [e["text"] for e in entries[:limit]]
    if len(entries) > limit:
        lines.append("... and %d more (see the Report view)" % (len(entries) - limit))
    return lines
