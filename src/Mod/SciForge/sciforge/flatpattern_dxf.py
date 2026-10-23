# SPDX-License-Identifier: LGPL-2.1-or-later
"""The flat pattern as DXF (pure Python, no FreeCAD, no Qt; unit tested).

Fusion's FLAT PATTERN > Export DXF writes the part's outline for a laser or water-jet cutter,
every kind of line on its own layer so the shop can switch the bend lines off:

    OUTER_PROFILES          the outline of the part
    INTERIOR_PROFILES       holes and cut-outs
    BEND_CENTER_LINES_UP    centre line of each bend that folds toward the stationary face's side
    BEND_CENTER_LINES_DOWN  ... that folds away from it
    BEND_EXTENT_LINES       the two lines where each bend starts and ends
    TEXT                    a note on each bend: direction, angle, inner radius

The entities come in as plain tuples (flatpattern.dxf_entities builds them from the shape):
("line", x1, y1, x2, y2), ("circle", cx, cy, r), ("arc", cx, cy, r, start_deg, end_deg)
(counter-clockwise), ("polyline", [(x, y), ...], closed), ("spline", degree, knots,
[(x, y), ...] poles), ("text", x, y, height, value, rotation_deg).
The file is AutoCAD R12 (read by every CAM program) in millimetres; a spline is written as
a SPLINE entity, or as a polyline when "Convert Splines to Polylines" is on (the caller then
sends polylines instead).
"""

from .drawing_core import DxfWriter, read_dxf_entities

OUTER = "OUTER_PROFILES"
INTERIOR = "INTERIOR_PROFILES"
BEND_UP = "BEND_CENTER_LINES_UP"
BEND_DOWN = "BEND_CENTER_LINES_DOWN"
EXTENT = "BEND_EXTENT_LINES"
TEXT = "TEXT"
LAYERS = (
    (OUTER, 7, "CONTINUOUS"),
    (INTERIOR, 7, "CONTINUOUS"),
    (BEND_UP, 1, "CENTER"),
    (BEND_DOWN, 5, "CENTER"),
    (EXTENT, 8, "HIDDEN"),
    (TEXT, 3, "CONTINUOUS"),
)
DEFAULT_OPTIONS = {
    "center_lines": True,
    "extent_lines": True,
    "splines_to_polylines": False,
    "tolerance": 0.1,  # mm (Fusion: 0.01 cm)
    "notes": True,
}


class FlatDxfWriter(DxfWriter):
    """DxfWriter with polylines (one POLYLINE entity) and splines."""

    def polyline2(self, points, layer="0", closed=False):
        self.layer(layer)
        self.entities.append(("POLYLINE", [(8, layer), (66, 1), (70, 1 if closed else 0)]))
        for x, y in points:
            self.entities.append(
                ("VERTEX", [(8, layer), (10, float(x)), (20, float(y)), (30, 0.0)])
            )
        self.entities.append(("SEQEND", [(8, layer)]))

    def spline(self, degree, knots, poles, layer="0"):
        self.layer(layer)
        codes = [
            (8, layer),
            (100, "AcDbSpline"),
            (70, 8),
            (71, int(degree)),
            (72, len(knots)),
            (73, len(poles)),
            (74, 0),
        ]
        codes += [(40, float(k)) for k in knots]
        for x, y in poles:
            codes += [(10, float(x)), (20, float(y)), (30, 0.0)]
        self.entities.append(("SPLINE", codes))


def write(outer, interior, bends, options=None):
    """The DXF text. outer / interior: lists of entity tuples. bends: dicts with "up",
    "centre" [(x, y), (x, y)], "start" and "end" lines, "angle", "radius"."""
    opts = dict(DEFAULT_OPTIONS, **(options or {}))
    dxf = FlatDxfWriter()
    for name, color, linetype in LAYERS:
        dxf.layer(name, color, linetype)
    for layer, items in ((OUTER, outer), (INTERIOR, interior)):
        for item in items:
            _put(dxf, item, layer)
    for bend in bends:
        if opts["center_lines"]:
            (x1, y1), (x2, y2) = bend["centre"]
            dxf.line(x1, y1, x2, y2, BEND_UP if bend["up"] else BEND_DOWN)
        if opts["extent_lines"]:
            for key in ("start", "end"):
                (x1, y1), (x2, y2) = bend[key]
                dxf.line(x1, y1, x2, y2, EXTENT)
        if opts["notes"]:
            (x1, y1), (x2, y2) = bend["centre"]
            dxf.text(
                (x1 + x2) / 2.0,
                (y1 + y2) / 2.0,
                2.5,
                note(bend),
                TEXT,
                align="center",
            )
    return dxf.to_text()


def note(bend):
    """'UP 90.0%%d R1' style bend note (direction, angle, inner radius); %%d is DXF's own
    code for the degree sign (an R12 file is plain ASCII)."""
    radius = ("%.3f" % bend["radius"]).rstrip("0").rstrip(".")
    return "%s %.1f%s R%s" % ("UP" if bend["up"] else "DOWN", bend["angle"], "%%d", radius)


def _put(dxf, item, layer):
    kind = item[0]
    if kind == "line":
        dxf.line(item[1], item[2], item[3], item[4], layer)
    elif kind == "circle":
        dxf.circle(item[1], item[2], item[3], layer)
    elif kind == "arc":
        dxf.arc(item[1], item[2], item[3], item[4], item[5], layer)
    elif kind == "polyline":
        dxf.polyline2(item[1], layer, item[2])
    elif kind == "spline":
        dxf.spline(item[1], item[2], item[3], layer)
    else:
        raise ValueError("unknown DXF entity %r" % (kind,))


def count_by_layer(text):
    """{layer: {kind: count}} of a DXF's entities (VERTEX / SEQEND left out): the read-back
    check of tests and scenarios."""
    out = {}
    for kind, codes in read_dxf_entities(text):
        if kind in ("VERTEX", "SEQEND"):
            continue
        layer = (codes.get(8) or ["0"])[0]
        out.setdefault(layer, {})
        out[layer][kind] = out[layer].get(kind, 0) + 1
    return out
