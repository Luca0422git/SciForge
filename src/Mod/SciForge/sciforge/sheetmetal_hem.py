# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's SHEET METAL > CREATE > Hem: fold the edges of a sheet back on themselves. FreeCAD
side, no Qt: the dialog (sheetmetal_hem_ui.py) and the golden-model builder both call make().

For each picked edge (where a top or bottom face meets a side face as thick as the sheet), the
sheet is cut back by the Bend Position and the hem's strip is built in the edge's cross-section
(sheetmetal_bend_core.hem_profile: Flat / Open / Rolled / Teardrop / Rope / Double) and pulled
along the edge. Two picked edges that meet at a corner are mitred there (Miter Corners: each
hem stops half the rule's miter gap short of the corner's bisector) or left overlapping.

Everything is flat walls and cylindrical bends of the sheet's thickness, so the flat pattern
can unfold it. Sources: docs/sciforge/dev/research/fusion-sheet-metal.md 2.4, 4.4.
"""

import FreeCAD as App

from . import bodies, log, sheetmetal_bend as sb, sheetmetal_bend_core as core

V = App.Vector
TYPE = "PartDesign::FeaturePython"
KIND = "SheetMetalHem"
TYPES = [core.HEM_LABELS[k] for k in core.HEM_TYPES]
POSITIONS = [core.HEM_POSITION_LABELS[k] for k in core.HEM_POSITIONS]


def default_options(thickness=1.0):
    opts = core.hem_defaults(thickness)
    opts.update({"override": False, "radius_override": None})
    return opts


def _corner_cuts(frames, gap):
    """{index: [(point, normal)]} half-spaces each hem keeps at shared corners: the points X
    with (X - point) . normal >= 0 stay. Two picked edges meet when they share an end point."""
    cuts = {i: [] for i in range(len(frames))}
    for i, fa in enumerate(frames):
        for j in range(i + 1, len(frames)):
            fb = frames[j]
            for pa in (fa["start"], fa["end"]):
                for pb in (fb["start"], fb["end"]):
                    if (pa - pb).Length > 1e-5:
                        continue
                    ua = sb.unit((fa["end"] if pa is fa["start"] else fa["start"]) - pa)
                    ub = sb.unit((fb["end"] if pb is fb["start"] else fb["start"]) - pb)
                    m = ua - ub
                    if m.Length < 1e-9:
                        continue
                    m = sb.unit(m)
                    cuts[i].append((pa + m * (gap / 2.0), m))
                    cuts[j].append((pa - m * (gap / 2.0), m * -1.0))
    return cuts


def hem_shape(shape, edge_names, options, thickness, rule_radius, miter_gap):
    """The body's solid with hems on `edge_names`. Raises sb.SheetMetalError."""
    if not edge_names:
        raise sb.SheetMetalError("Pick one or more edges of the sheet to hem.")
    values = dict(options)
    try:
        segs, inner = core.hem_segments(values, thickness, rule_radius)
        x0 = core.hem_start(values.get("position", "inside"), inner, thickness)
    except ValueError as exc:
        raise sb.SheetMetalError(str(exc))
    return edge_strips(
        shape,
        edge_names,
        segs,
        x0,
        thickness,
        miter_gap if options.get("miter", True) else None,
        bool(options.get("flip", False)),
        "This hem",
    )


def edge_strips(shape, edge_names, segs, x0, thickness, miter_gap, flip, what):
    """The solid with a strip of sheet (core.walk segments, starting x0 from each edge) added
    along each picked edge, the sheet cut back to x0 first. miter_gap None: no mitres."""
    pieces, _end = core.walk(segs, (x0, -thickness / 2.0), 0.0, thickness)
    frames = [sb.edge_frame(shape, name, thickness) for name in edge_names]
    big = shape.BoundBox.DiagonalLength * 2.0 + 10.0
    cuts = _corner_cuts(frames, miter_gap) if miter_gap is not None else {}
    trims, strips = [], []
    for index, fr in enumerate(frames):
        up = fr["normal"] * (-1.0 if flip else 1.0)
        origin = fr["start"] - (fr["normal"] * thickness if flip else V(0, 0, 0))
        xdir = fr["out"]
        along = fr["dir"]
        if x0 < -1e-9:
            trims.append(
                sb.frame_box(
                    origin,
                    xdir,
                    along,
                    up,
                    x0,
                    big,
                    0.0,
                    fr["length"],
                    -thickness * 1.5,
                    thickness * 0.5,
                )
            )
        strip = sb.strip_solid(pieces, thickness, origin, xdir, up, along * fr["length"])
        for point, normal in cuts.get(index, []):
            # keep the side of the corner's bisector this edge lies on
            ydir = up.cross(normal)
            keep = sb.frame_box(point, normal, ydir, up, 0.0, big, -big, big, -big, big)
            strip = strip.common(keep)
        strips.append(strip)
    trimmed = shape.cut(trims) if trims else shape
    merged = sb.fuse_all(trimmed, strips)
    return sb.one_solid(merged, what)


class HemFeature:
    """Saved in files as "sciforge.sheetmetal_hem.HemFeature": keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Hem", doc)
                return True
            return False

        add("App::PropertyLinkSub", "Edges", "The edges hemmed")
        if add("App::PropertyEnumeration", "HemType", "Flat, Open, Rolled, Teardrop, Rope, Double"):
            obj.HemType = TYPES
            obj.HemType = "Open"
        if add("App::PropertyLength", "Length", "Length of the hem from its outside"):
            obj.Length = 4.0
        if add("App::PropertyLength", "Gap", "Space between the layers"):
            obj.Gap = 0.5
        if add("App::PropertyLength", "Radius", "Inner radius of the roll"):
            obj.Radius = 2.0
        if add("App::PropertyAngle", "RollAngle", "How far a Rolled hem rolls"):
            obj.RollAngle = 270.0
        add("App::PropertyLength", "Setback", "Double: how far the second run stops short")
        if add("App::PropertyEnumeration", "BendPosition", "Where the fold sits on the edge"):
            obj.BendPosition = POSITIONS
            obj.BendPosition = "Inside"
        add("App::PropertyBool", "Flip", "Hem to the other side")
        if add("App::PropertyBool", "MiterCorners", "Mitre where two hems meet"):
            obj.MiterCorners = True
        add("App::PropertyBool", "OverrideRadius", "Use Bend Radius instead of the rule's")
        if add("App::PropertyLength", "BendRadius", "Rule bend radius override (Rope)"):
            obj.BendRadius = 1.0
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane"):
            obj.Refine = True
        bodies.mark(obj, KIND)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)
        show_used(obj)

    def onChanged(self, obj, prop):
        if prop in ("HemType", "OverrideRadius"):
            show_used(obj)

    def execute(self, obj):
        try:
            obj.Shape = build(obj)
        except Exception:
            bodies.pass_through(obj)
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


HEM_PROPS = {
    "length": "Length",
    "gap": "Gap",
    "radius": "Radius",
    "angle": "RollAngle",
    "setback": "Setback",
}


def show_used(obj):
    """Only the values the hem's type uses are shown (property editor, the timeline's Change
    Parameters), like the dialog's rows: a Gap typed there for a Rolled hem changed nothing."""
    try:
        used = core.HEM_VALUES.get(_key(str(obj.HemType), core.HEM_LABELS), ())
        for key, prop in HEM_PROPS.items():
            obj.setEditorMode(prop, 0 if key in used else 2)
        obj.setEditorMode("BendRadius", 0 if obj.OverrideRadius else 2)
    except Exception:
        pass


def _key(label, table):
    for key, text in table.items():
        if text == label:
            return key
    return label.lower()


def options_of(obj):
    return {
        "type": _key(str(obj.HemType), core.HEM_LABELS),
        "length": float(obj.Length),
        "gap": float(obj.Gap),
        "radius": float(obj.Radius),
        "angle": float(obj.RollAngle),
        "setback": float(obj.Setback),
        "position": _key(str(obj.BendPosition), core.HEM_POSITION_LABELS),
        "flip": bool(obj.Flip),
        "miter": bool(obj.MiterCorners),
        "override": bool(obj.OverrideRadius),
        "radius_override": float(obj.BendRadius),
    }


def build(obj):
    base = obj.BaseFeature
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise sb.SheetMetalError("There is no sheet to hem before this step.")
    body = bodies.body_of(obj)
    opts = options_of(obj)
    thickness, radius, _k, rule = sb.rule_values(
        body, opts["radius_override"] if opts["override"] else None
    )
    link = obj.Edges
    names = list(link[1]) if link else []
    shape = base.Shape.copy()
    shape.Placement = App.Placement()
    result = hem_shape(shape, names, opts, thickness, radius, float(rule["miter_gap"]))
    if obj.Refine:
        try:
            result = result.removeSplitter()
        except Exception:
            pass
    return result


def apply(obj, base, edge_names, options):
    obj.Edges = (base, list(edge_names))
    obj.HemType = core.HEM_LABELS[options.get("type", "open")]
    obj.Length = float(options.get("length", 4.0))
    obj.Gap = float(options.get("gap", 0.5))
    obj.Radius = float(options.get("radius", 2.0))
    obj.RollAngle = float(options.get("angle", 270.0))
    obj.Setback = float(options.get("setback", 0.0))
    obj.BendPosition = core.HEM_POSITION_LABELS[options.get("position", "inside")]
    obj.Flip = bool(options.get("flip", False))
    obj.MiterCorners = bool(options.get("miter", True))
    obj.OverrideRadius = bool(options.get("override", False))
    if options.get("radius_override") is not None:
        obj.BendRadius = float(options["radius_override"])


def make(body, base, edge_names, options=None, name="Hem"):
    """A Hem step at the history marker of `body`, built on `base`."""
    thickness = 1.0
    try:
        thickness = sb.rule_values(body)[0]
    except Exception:
        pass
    opts = default_options(thickness)
    opts.update(options or {})
    obj = bodies.insert_after_tip(body, TYPE, name)
    HemFeature(obj)
    obj.BaseFeature = base
    apply(obj, base, edge_names, opts)
    _view(obj)
    log("hem %s made" % obj.Name)
    return obj


def read(obj):
    link = obj.Edges
    return obj.BaseFeature, list(link[1]) if link else [], options_of(obj)


def _view(obj):
    if not App.GuiUp:
        return
    try:
        from . import sheetmetal_hem_ui

        sheetmetal_hem_ui.ViewProviderHem(obj.ViewObject)
    except Exception:
        pass
