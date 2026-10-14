# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole sizes that come from standards: clearance holes chosen by fastener, and taper pipe
threads (Fusion's Hole Tap Type "Taper Tapped"). Pure Python (unit tested); hole.py and the
Hole dialog read these tables.

Clearance holes (Fusion: Hole Tap Type Clearance, then Standard, Fastener Type, Size and
Fit). The hole's diameter follows the screw's size and the fit:

  metric  ISO 273: fine / medium / coarse series = Fusion's Close / Normal / Loose
  inch    ASME B18.2.8: close / normal / loose
  (the same rows FreeCAD's Hole uses, src/Mod/PartDesign/App/FeatureHole.cpp; sizes the
  standards leave out get FreeCAD's factors, so both always agree)

The fastener type gives the counterbore or countersink a counterbored or countersunk
clearance hole starts with (the dialog fills them in; they can still be typed over):

  socket head cap screws   ISO 4762 / ASME B18.3 heads, counterbores per DIN 974-1 (metric)
                           and the usual ASME B18.3 counterbore table (inch)
  hex head screws / bolts  ISO 4017 / ASME B18.2.1 heads, a counterbore wide enough for a
                           socket wrench (DIN 974-1's row for hexagon heads, metric)
  countersunk screws       ISO 10642 (90 degrees) / ASME B18.3 flat head (82 degrees): the
                           countersink is the head's theoretical diameter, so the head sits
                           flush

Taper pipe threads (Fusion: Hole Tap Type "Taper Tapped", a tapered hole tapped with a pipe
thread; the thread itself is cosmetic, as in Fusion):

  NPT   ASME B1.20.1, 60 degree thread, h = 0.8 P. At the opening of an internal thread
        (the hand-tight gauge plane) the pitch diameter is E1 = E0 + L1 / 16 with
        E0 = D - (0.05 D + 1.1) P; the hole starts at the minor diameter E1 - 0.8 P
  BSPT  ISO 7-1 (Rc internal), 55 degree Whitworth thread, h = 0.640327 P. At the gauge
        plane (the opening) the major diameter is the gauge diameter d; the hole starts at
        the minor diameter d - 2 h

Both taper 1 in 16 on the diameter: the hole's wall leans in by atan(1/32) = 1.7899 degrees.
"""

import math

INCH = 25.4

# -- clearance holes -----------------------------------------------------------------------------
FITS = ("close", "normal", "loose")

# ISO 273: screw diameter -> (fine, medium, coarse) = (close, normal, loose) hole diameters, mm.
ISO_273 = {
    "1": (1.1, 1.2, 1.3),
    "1.2": (1.3, 1.4, 1.5),
    "1.4": (1.5, 1.6, 1.8),
    "1.6": (1.7, 1.8, 2.0),
    "1.8": (2.0, 2.1, 2.2),
    "2": (2.2, 2.4, 2.6),
    "2.5": (2.7, 2.9, 3.1),
    "3": (3.2, 3.4, 3.6),
    "3.5": (3.7, 3.9, 4.2),
    "4": (4.3, 4.5, 4.8),
    "4.5": (4.8, 5.0, 5.3),
    "5": (5.3, 5.5, 5.8),
    "6": (6.4, 6.6, 7.0),
    "7": (7.4, 7.6, 8.0),
    "8": (8.4, 9.0, 10.0),
    "10": (10.5, 11.0, 12.0),
    "12": (13.0, 13.5, 14.5),
    "14": (15.0, 15.5, 16.5),
    "16": (17.0, 17.5, 18.5),
    "18": (19.0, 20.0, 21.0),
    "20": (21.0, 22.0, 24.0),
    "22": (23.0, 24.0, 26.0),
    "24": (25.0, 26.0, 28.0),
    "27": (28.0, 30.0, 32.0),
    "30": (31.0, 33.0, 35.0),
    "33": (34.0, 36.0, 38.0),
    "36": (37.0, 39.0, 42.0),
    "39": (40.0, 42.0, 45.0),
    "42": (43.0, 45.0, 48.0),
    "45": (46.0, 48.0, 52.0),
    "48": (50.0, 52.0, 56.0),
    "52": (54.0, 56.0, 62.0),
    "56": (58.0, 62.0, 66.0),
    "60": (62.0, 66.0, 70.0),
    "64": (66.0, 70.0, 74.0),
    "68": (70.0, 74.0, 78.0),
}
ISO_FACTORS = (1.06, 1.10, 1.16)  # FreeCAD's fallback for sizes ISO 273 leaves out

# ASME B18.2.8: screw size -> (close, normal, loose) hole diameters, mm (FreeCAD's rows: the
# drill size the standard names, in mm).
ASME_B18_2_8 = {
    "#0": (1.7, 1.9, 2.4),
    "#1": (2.1, 2.3, 2.6),
    "#2": (2.4, 2.6, 2.9),
    "#3": (2.7, 2.9, 3.3),
    "#4": (3.0, 3.3, 3.7),
    "#5": (3.6, 4.0, 4.4),
    "#6": (3.9, 4.3, 4.7),
    "#8": (4.6, 5.0, 5.4),
    "#10": (5.2, 5.6, 6.0),
    "1/4": (6.8, 7.1, 7.5),
    "5/16": (8.3, 8.7, 9.1),
    "3/8": (9.9, 10.3, 10.7),
    "7/16": (11.5, 11.9, 12.3),
    "1/2": (13.5, 14.3, 15.5),
    "5/8": (16.7, 17.5, 18.6),
    "3/4": (19.8, 20.6, 23.0),
    "7/8": (23.0, 23.8, 26.2),
    "1": (26.2, 27.8, 29.4),
    "1 1/8": (29.4, 31.0, 33.3),
    "1 3/16": (31.0, 32.5, 34.9),
    "1 1/4": (32.5, 34.1, 36.5),
    "1 3/8": (36.5, 38.1, 40.9),
    "1 1/2": (39.7, 41.3, 44.0),
}
ASME_FACTORS = (1.04, 1.08, 1.12)


def _fit_index(fit):
    if fit not in FITS:
        raise ValueError("unknown fit %r (close, normal or loose)" % (fit,))
    return FITS.index(fit)


def clearance_diameter(standard, size, diameter, fit="normal"):
    """The clearance hole's diameter (mm) for a screw of this standard ("iso" / "ansi"),
    size ("6", "1/4", "#10") and nominal diameter (mm), with Fusion's fit."""
    i = _fit_index(fit)
    table, factors = (ISO_273, ISO_FACTORS) if standard == "iso" else (ASME_B18_2_8, ASME_FACTORS)
    row = table.get(size)
    if row is not None:
        return row[i]
    return float(diameter) * factors[i]


# -- fasteners -----------------------------------------------------------------------------------
class Fastener:
    """A fastener type: the head it has (a counterbore or a countersink holds it) and the
    head sizes (mm) per screw size."""

    __slots__ = ("key", "label", "standard", "cut", "angle", "heads")

    def __init__(self, key, label, standard, cut, heads, angle=0.0):
        self.key = key
        self.label = label
        self.standard = standard
        self.cut = cut  # "counterbore" | "countersink"
        self.angle = angle  # countersink angle (degrees)
        self.heads = heads  # size -> (counterbore / countersink diameter, counterbore depth)

    def sizes(self):
        return list(self.heads)

    def __repr__(self):
        return "<Fastener %s>" % self.key


def _inch(values):
    return tuple(round(v * INCH, 4) for v in values)


def _cbore_depth(k, size_mm):
    """DIN 974-1's counterbore depth for a socket head cap screw: the head height k and a
    little more, so the head sits just below the face."""
    extra = 0.2 if size_mm <= 2.5 else 0.4 if size_mm <= 6 else 0.6 if size_mm <= 20 else 0.8
    return round(k + extra, 4)


# ISO 4762 socket head cap screws: size -> (head diameter dk, head height k, counterbore
# diameter (DIN 974-1)).
_ISO_4762 = (
    ("1.6", 3.0, 1.6, 3.5),
    ("2", 3.8, 2.0, 4.4),
    ("2.5", 4.5, 2.5, 5.4),
    ("3", 5.5, 3.0, 6.5),
    ("4", 7.0, 4.0, 8.0),
    ("5", 8.5, 5.0, 10.0),
    ("6", 10.0, 6.0, 11.0),
    ("8", 13.0, 8.0, 15.0),
    ("10", 16.0, 10.0, 18.0),
    ("12", 18.0, 12.0, 20.0),
    ("14", 21.0, 14.0, 24.0),
    ("16", 24.0, 16.0, 26.0),
    ("20", 30.0, 20.0, 33.0),
    ("24", 36.0, 24.0, 40.0),
    ("30", 45.0, 30.0, 48.0),
    ("36", 54.0, 36.0, 57.0),
)
# ISO 4017 hex head screws: size -> (across flats s, head height k, counterbore diameter for
# a socket wrench (DIN 974-1, hexagon heads)).
_ISO_4017 = (
    ("3", 5.5, 2.0, 11.0),
    ("4", 7.0, 2.8, 13.0),
    ("5", 8.0, 3.5, 15.0),
    ("6", 10.0, 4.0, 18.0),
    ("8", 13.0, 5.3, 24.0),
    ("10", 16.0, 6.4, 28.0),
    ("12", 18.0, 7.5, 33.0),
    ("14", 21.0, 8.8, 36.0),
    ("16", 24.0, 10.0, 40.0),
    ("20", 30.0, 12.5, 46.0),
    ("24", 36.0, 15.0, 58.0),
    ("30", 46.0, 18.7, 73.0),
    ("36", 55.0, 22.5, 82.0),
)
# ISO 10642 countersunk socket head: size -> theoretical head diameter (90 degrees).
_ISO_10642 = (
    ("3", 6.72),
    ("4", 8.96),
    ("5", 11.2),
    ("6", 13.44),
    ("8", 17.92),
    ("10", 22.4),
    ("12", 26.88),
    ("16", 33.6),
    ("20", 40.32),
)
# ASME B18.3 socket head cap screws: size -> (head diameter, head height, counterbore
# diameter), inches.
_ASME_SHCS = (
    ("#0", 0.096, 0.060, 0.125),
    ("#1", 0.118, 0.073, 0.15625),
    ("#2", 0.140, 0.086, 0.1875),
    ("#3", 0.161, 0.099, 0.21875),
    ("#4", 0.183, 0.112, 0.21875),
    ("#5", 0.205, 0.125, 0.25),
    ("#6", 0.226, 0.138, 0.28125),
    ("#8", 0.270, 0.164, 0.3125),
    ("#10", 0.312, 0.190, 0.375),
    ("1/4", 0.375, 0.250, 0.4375),
    ("5/16", 0.469, 0.3125, 0.53125),
    ("3/8", 0.5625, 0.375, 0.625),
    ("7/16", 0.656, 0.4375, 0.71875),
    ("1/2", 0.750, 0.500, 0.8125),
    ("5/8", 0.9375, 0.625, 1.0),
    ("3/4", 1.125, 0.750, 1.1875),
    ("1", 1.500, 1.000, 1.625),
)
# ASME B18.3 flat head socket cap screws: size -> theoretical head diameter (82 degrees), in.
_ASME_FHSCS = (
    ("#0", 0.138),
    ("#1", 0.168),
    ("#2", 0.197),
    ("#3", 0.226),
    ("#4", 0.255),
    ("#5", 0.281),
    ("#6", 0.307),
    ("#8", 0.359),
    ("#10", 0.411),
    ("1/4", 0.531),
    ("5/16", 0.656),
    ("3/8", 0.781),
    ("7/16", 0.844),
    ("1/2", 0.938),
    ("5/8", 1.188),
    ("3/4", 1.438),
    ("1", 1.938),
)
# ASME B18.2.1 hex bolts: size -> (across flats, head height), inches. The counterbore is
# 1.75 times the width across flats, rounded up to 1/16 in (SciForge's choice, the ratio of
# DIN 974-1's metric rows).
_ASME_HEX = (
    ("1/4", 0.4375, 0.171875),
    ("5/16", 0.5, 0.21875),
    ("3/8", 0.5625, 0.25),
    ("7/16", 0.625, 0.296875),
    ("1/2", 0.75, 0.34375),
    ("5/8", 0.9375, 0.421875),
    ("3/4", 1.125, 0.5),
    ("7/8", 1.3125, 0.578125),
    ("1", 1.5, 0.671875),
)


def _size_mm(size):
    try:
        return float(size)
    except ValueError:
        return 0.0


def _sixteenths_up(inches):
    return math.ceil(inches * 16.0 - 1e-9) / 16.0


FASTENERS = (
    Fastener(
        "socket_head",
        "Socket Head Cap Screw (ISO 4762)",
        "iso",
        "counterbore",
        {s: (cb, _cbore_depth(k, _size_mm(s))) for s, _dk, k, cb in _ISO_4762},
    ),
    Fastener(
        "hex_head",
        "Hex Head Screw (ISO 4017)",
        "iso",
        "counterbore",
        {s: (cb, _cbore_depth(k, _size_mm(s))) for s, _s, k, cb in _ISO_4017},
    ),
    Fastener(
        "countersunk",
        "Countersunk Socket Head Screw (ISO 10642)",
        "iso",
        "countersink",
        {s: (dk, 0.0) for s, dk in _ISO_10642},
        angle=90.0,
    ),
    Fastener(
        "socket_head",
        "Socket Head Cap Screw (ASME B18.3)",
        "ansi",
        "counterbore",
        {s: _inch((cb, h)) for s, _d, h, cb in _ASME_SHCS},
    ),
    Fastener(
        "hex_head",
        "Hex Bolt (ASME B18.2.1)",
        "ansi",
        "counterbore",
        {s: _inch((_sixteenths_up(1.75 * f), h)) for s, f, h in _ASME_HEX},
    ),
    Fastener(
        "countersunk",
        "Flat Head Socket Cap Screw (ASME B18.3)",
        "ansi",
        "countersink",
        {s: (round(d * INCH, 4), 0.0) for s, d in _ASME_FHSCS},
        angle=82.0,
    ),
)


def fasteners(standard, hole_type="simple"):
    """The fastener types Fusion's clearance hole offers for this standard and hole type: a
    counterbore holds socket and hex heads, a countersink the countersunk ones, a simple
    hole any of them (the shank only goes through)."""
    found = []
    for f in FASTENERS:
        if f.standard != standard:
            continue
        if hole_type == "counterbore" and f.cut != "counterbore":
            continue
        if hole_type == "countersink" and f.cut != "countersink":
            continue
        found.append(f)
    return found


def fastener(standard, key):
    for f in FASTENERS:
        if f.standard == standard and f.key == key:
            return f
    return None


def default_fastener(standard, hole_type="simple"):
    found = fasteners(standard, hole_type)
    return found[0] if found else None


def head_cut(standard, key, size):
    """What a counterbored or countersunk clearance hole for this fastener and size starts
    with: {"hole_type", "diameter", "depth" (counterbore) or "angle" (countersink)}, or None
    when the fastener has no such size."""
    f = fastener(standard, key)
    if f is None or size not in f.heads:
        return None
    diameter, depth = f.heads[size]
    if f.cut == "countersink":
        return {"hole_type": "countersink", "diameter": diameter, "angle": f.angle}
    return {"hole_type": "counterbore", "diameter": diameter, "depth": depth}


# -- taper pipe threads -------------------------------------------------------------------------
TAPER_HALF_ANGLE = math.degrees(math.atan(1.0 / 32.0))  # 1 in 16 on the diameter
TAPER_KINDS = (
    ("npt", "ANSI Taper Pipe Thread (NPT)"),
    ("bspt", "ISO Taper Pipe Thread (BSPT, Rc)"),
)

# ASME B1.20.1 NPT: size -> (threads per inch, outside diameter D, hand-tight engagement L1),
# inches.
_NPT = (
    ("1/16", 27.0, 0.3125, 0.160),
    ("1/8", 27.0, 0.405, 0.1615),
    ("1/4", 18.0, 0.540, 0.2278),
    ("3/8", 18.0, 0.675, 0.240),
    ("1/2", 14.0, 0.840, 0.320),
    ("3/4", 14.0, 1.050, 0.339),
    ("1", 11.5, 1.315, 0.400),
    ("1 1/4", 11.5, 1.660, 0.420),
    ("1 1/2", 11.5, 1.900, 0.420),
    ("2", 11.5, 2.375, 0.436),
    ("2 1/2", 8.0, 2.875, 0.682),
    ("3", 8.0, 3.500, 0.766),
)
# ISO 7-1 (BSPT, Rc internal): size -> (threads per inch, gauge diameter d, gauge length), mm.
_BSPT = (
    ("1/16", 28.0, 7.723, 4.0),
    ("1/8", 28.0, 9.728, 4.0),
    ("1/4", 19.0, 13.157, 6.0),
    ("3/8", 19.0, 16.662, 6.4),
    ("1/2", 14.0, 20.955, 8.2),
    ("3/4", 14.0, 26.441, 9.5),
    ("1", 11.0, 33.249, 10.4),
    ("1 1/4", 11.0, 41.910, 12.7),
    ("1 1/2", 11.0, 47.803, 12.7),
    ("2", 11.0, 59.614, 15.9),
    ("2 1/2", 11.0, 75.184, 17.5),
    ("3", 11.0, 87.884, 20.6),
)


class TaperThread:
    """One taper pipe thread size (mm): the thread at the hole's opening and how it tapers."""

    __slots__ = ("kind", "size", "tpi", "pitch", "major", "minor", "engagement", "label")

    def __init__(self, kind, size, tpi, major, minor, engagement):
        self.kind = kind
        self.size = size
        self.tpi = tpi
        self.pitch = INCH / tpi
        self.major = major  # major diameter at the opening (the gauge plane)
        self.minor = minor  # minor diameter at the opening: the hole's diameter there
        self.engagement = engagement  # hand-tight / gauge length
        self.label = "%s-%g NPT" % (size, tpi) if kind == "npt" else "Rc %s" % size

    def diameter_at(self, depth):
        """The hole's (minor) diameter `depth` mm below the opening (1 in 16 on the
        diameter)."""
        return self.minor - float(depth) / 16.0

    def __repr__(self):
        return "<TaperThread %s>" % self.label


def _npt(size, tpi, outside, l1):
    p = 1.0 / tpi
    e0 = outside - (0.05 * outside + 1.1) * p
    e1 = e0 + l1 / 16.0
    h = 0.8 * p
    return TaperThread("npt", size, tpi, (e1 + h) * INCH, (e1 - h) * INCH, l1 * INCH)


def _bspt(size, tpi, gauge, length):
    p = INCH / tpi
    h = 0.640327 * p
    return TaperThread("bspt", size, tpi, gauge, gauge - 2.0 * h, length)


_TAPER = None


def _taper_all():
    global _TAPER
    if _TAPER is None:
        _TAPER = [_npt(*row) for row in _NPT] + [_bspt(*row) for row in _BSPT]
    return _TAPER


def taper_sizes(kind):
    return [t.size for t in _taper_all() if t.kind == kind]


def taper_thread(kind, size):
    for t in _taper_all():
        if t.kind == kind and t.size == size:
            return t
    return None


def taper_kind_label(kind):
    return dict(TAPER_KINDS).get(kind, kind)
