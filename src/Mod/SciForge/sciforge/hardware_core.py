# SPDX-License-Identifier: LGPL-2.1-or-later
"""The hardware library (INSERT > Hardware...): real-size screws, nuts, washers, heat-set
inserts and magnets, and the hole each one needs. Pure Python (no FreeCAD, unit tested);
hardware.py builds the solids from these numbers and hardware_ui.py is the dialog.

SciForge's own tables. The metric sizes are the dimensions the ISO standards give (the
usual largest value of each dimension, the size a part is drawn at); threads are not
modelled (plain cylinders at the nominal diameter, like a cosmetic thread):

  ISO 4762   socket head cap screw     head diameter dk, head height k, socket s, depth t
  ISO 7380-1 button head (hexagon socket)  dk, k, s, t (the standard starts at M3)
  ISO 10642  countersunk (hexagon socket, 90 degrees)  theoretical head diameter, k, s, t
             (the standard starts at M3)
  ISO 4032   hexagon nut               across flats s, height m
  ISO 7089   plain washer              inside d1, outside d2, thickness h
  heat-set threaded inserts for 3D prints: outside diameter, length and the hole they are
             melted into. No standard: one widely sold size set (Guess)
  round magnets: diameter x thickness, the common neodymium disc sizes (Guess)

The hole each one gets (hardware.py makes it a Hole step with SciForge's Hole feature):

  screws     a clearance hole (ISO 273, Fusion's Close / Normal / Loose fit, hole_tables);
             with "head sunk in": a counterbore for socket and button heads (socket heads:
             DIN 974-1 as the Hole dialog fills it in; button heads: dk + 1 mm, Guess), a
             90 degree countersink for countersunk heads (the head's theoretical diameter,
             so it sits flush)
  nuts, washers   a clearance hole for the screw that goes through them
  inserts    the insert's hole diameter, 1 mm deeper than the insert (Guess: room for the
             plastic it pushes down), flat bottom
  magnets    the magnet's diameter + a clearance (0.2 mm by default, Guess), as deep as
             the magnet is thick, flat bottom

Where a part sits (its own frame: z = 0 is the clicked face, +z points out of the part):
  screws     the head on the face (in the counterbore / countersink when sunk), the shank
             down into the part
  nuts, washers   on the face
  inserts, magnets   in the part, their top flush with the face
"""

import math

from . import hole_tables

SQRT3 = math.sqrt(3.0)


class HardwareError(ValueError):
    """The part cannot be made as asked; the message says why and what to do."""


KINDS = (
    ("screw", "Screw"),
    ("nut", "Nut"),
    ("washer", "Washer"),
    ("insert", "Heat-set insert"),
    ("magnet", "Magnet"),
)
FITS = (("close", "Close"), ("normal", "Normal"), ("loose", "Loose"))
HOLE_DEPTHS = (("all", "Through All"), ("length", "Screw length"))

# Standard series of screw lengths (ISO 4762 / ISO 888), mm.
LENGTH_SERIES = (
    2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100,
)  # fmt: skip

# -- the tables ---------------------------------------------------------------------------------
# ISO 4762: size -> (d, dk, k, s, t, (shortest, longest length))
ISO_4762 = {
    "2": (2.0, 3.8, 2.0, 1.5, 1.0, (3, 20)),
    "2.5": (2.5, 4.5, 2.5, 2.0, 1.1, (4, 25)),
    "3": (3.0, 5.5, 3.0, 2.5, 1.3, (5, 30)),
    "4": (4.0, 7.0, 4.0, 3.0, 2.0, (6, 40)),
    "5": (5.0, 8.5, 5.0, 4.0, 2.5, (8, 50)),
    "6": (6.0, 10.0, 6.0, 5.0, 3.0, (10, 60)),
    "8": (8.0, 13.0, 8.0, 6.0, 4.0, (12, 80)),
}
# ISO 7380-1: size -> (d, dk, k, s, t, lengths). The length ranges are the ones commonly
# sold (Guess: the standard's own table is shorter for M3 and M4).
ISO_7380 = {
    "3": (3.0, 5.7, 1.65, 2.0, 1.04, (5, 30)),
    "4": (4.0, 7.6, 2.2, 2.5, 1.3, (6, 40)),
    "5": (5.0, 9.5, 2.75, 3.0, 1.56, (8, 40)),
    "6": (6.0, 10.5, 3.3, 4.0, 2.08, (10, 40)),
    "8": (8.0, 14.0, 4.4, 5.0, 2.6, (12, 50)),
}
# ISO 10642: size -> (d, theoretical dk, k, s, t, lengths). k = (dk - d) / 2: a 90 degree
# cone from dk down to the shank. The length counts the head (it sits in the part).
ISO_10642 = {
    "3": (3.0, 6.72, 1.86, 2.0, 1.1, (8, 30)),
    "4": (4.0, 8.96, 2.48, 2.5, 1.5, (8, 40)),
    "5": (5.0, 11.2, 3.1, 3.0, 1.9, (8, 50)),
    "6": (6.0, 13.44, 3.72, 4.0, 2.2, (8, 60)),
    "8": (8.0, 17.92, 4.96, 5.0, 3.0, (10, 80)),
}
# ISO 4032: size -> (d, s, m)
ISO_4032 = {
    "2": (2.0, 4.0, 1.6),
    "2.5": (2.5, 5.0, 2.0),
    "3": (3.0, 5.5, 2.4),
    "4": (4.0, 7.0, 3.2),
    "5": (5.0, 8.0, 4.7),
    "6": (6.0, 10.0, 5.2),
    "8": (8.0, 13.0, 6.8),
}
# ISO 7089: size -> (d1, d2, h)
ISO_7089 = {
    "2": (2.2, 5.0, 0.3),
    "2.5": (2.7, 6.0, 0.5),
    "3": (3.2, 7.0, 0.5),
    "4": (4.3, 9.0, 0.8),
    "5": (5.3, 10.0, 1.0),
    "6": (6.4, 12.0, 1.6),
    "8": (8.4, 16.0, 1.6),
}
# Heat-set inserts (Guess: the "standard length" size set most 3D-printing sellers list):
# size -> (thread d, outside diameter, length, hole diameter)
INSERTS = {
    "2": (2.0, 3.6, 3.0, 3.2),
    "2.5": (2.5, 4.6, 4.0, 4.0),
    "3": (3.0, 4.6, 5.7, 4.0),
    "4": (4.0, 6.3, 8.1, 5.6),
    "5": (5.0, 7.1, 9.5, 6.4),
}
INSERT_EXTRA_DEPTH = 1.0  # the hole is this much deeper than the insert (Guess)
# Round magnets: "DxT" -> (diameter, thickness)
MAGNETS = {
    "3x2": (3.0, 2.0),
    "4x2": (4.0, 2.0),
    "5x2": (5.0, 2.0),
    "5x3": (5.0, 3.0),
    "6x2": (6.0, 2.0),
    "6x3": (6.0, 3.0),
    "8x2": (8.0, 2.0),
    "8x3": (8.0, 3.0),
    "10x2": (10.0, 2.0),
    "10x3": (10.0, 3.0),
    "10x5": (10.0, 5.0),
    "12x3": (12.0, 3.0),
    "15x3": (15.0, 3.0),
    "20x3": (20.0, 3.0),
}
MAGNET_CLEARANCE = 0.2  # mm on the diameter (Guess: printed holes come out small)
BUTTON_CBORE_EXTRA = 1.0  # a button head's counterbore is dk + this (Guess)

# Standards: key -> (kind, label, the name's ending, table)
STANDARDS = {
    "iso4762": ("screw", "Socket head cap screw (ISO 4762)", "ISO 4762", ISO_4762),
    "iso7380": ("screw", "Button head screw (ISO 7380)", "ISO 7380", ISO_7380),
    "iso10642": ("screw", "Countersunk screw (ISO 10642)", "ISO 10642", ISO_10642),
    "iso4032": ("nut", "Hex nut (ISO 4032)", "ISO 4032", ISO_4032),
    "iso7089": ("washer", "Plain washer (ISO 7089)", "ISO 7089", ISO_7089),
    "insert": ("insert", "Heat-set insert (3D printing)", "heat-set insert", INSERTS),
    "magnet": ("magnet", "Round magnet", "", MAGNETS),
}
STANDARD_ORDER = ("iso4762", "iso7380", "iso10642", "iso4032", "iso7089", "insert", "magnet")

DEFAULTS = {
    "kind": "screw",
    "standard": "iso4762",
    "size": "3",
    "length": 10.0,
    "flip": False,
    "make_hole": True,
    "fit": "normal",
    "sink_head": True,
    "hole_depth": "all",
    "clearance": MAGNET_CLEARANCE,
}
DEFAULT_SIZE = {"magnet": "6x3"}


# -- reading the tables -------------------------------------------------------------------------
def standards(kind):
    """[(key, label)] of the standards of a kind, in the dialog's order."""
    return [(k, STANDARDS[k][1]) for k in STANDARD_ORDER if STANDARDS[k][0] == kind]


def kind_of(standard):
    if standard not in STANDARDS:
        raise HardwareError("Unknown hardware standard %r." % (standard,))
    return STANDARDS[standard][0]


def _size_number(size):
    try:
        return float(size)
    except (TypeError, ValueError):
        a, _, b = str(size).partition("x")
        try:
            return float(a) * 1000.0 + float(b)
        except ValueError:
            return 1e9


def sizes(standard):
    """The sizes of a standard, smallest first ("2", "2.5", ... or "6x3" for magnets)."""
    kind_of(standard)
    return sorted(STANDARDS[standard][3], key=_size_number)


def size_label(standard, size):
    """What the Size box shows: "M3", or "6 x 3 mm" for a magnet."""
    if kind_of(standard) == "magnet":
        d, t = MAGNETS[size]
        return "%g x %g mm" % (d, t)
    return "M%s" % size


def default_size(standard):
    found = sizes(standard)
    wanted = DEFAULT_SIZE.get(kind_of(standard), "3")
    return wanted if wanted in found else found[0]


def row(standard, size):
    table = STANDARDS[standard][3] if standard in STANDARDS else {}
    if size not in table:
        raise HardwareError(
            "%s has no size %s. Pick one of: %s."
            % (
                STANDARDS.get(standard, ("", standard))[1],
                size,
                ", ".join(size_label(standard, s) for s in sizes(standard)),
            )
        )
    return table[size]


def has_length(standard):
    return kind_of(standard) == "screw"


def lengths(standard, size):
    """The standard lengths a screw comes in (ISO 4762's length series within its range)."""
    if not has_length(standard):
        return []
    lo, hi = row(standard, size)[5]
    return [float(v) for v in LENGTH_SERIES if lo - 1e-9 <= v <= hi + 1e-9]


def default_length(standard, size):
    """About 3.3 times the diameter (M3 -> 10), the nearest standard length."""
    found = lengths(standard, size)
    if not found:
        return 0.0
    d = row(standard, size)[0]
    return min(found, key=lambda v: (abs(v - 3.3 * d), v))


def dims(standard, size):
    """The part's sizes (mm) by name."""
    kind = kind_of(standard)
    r = row(standard, size)
    if kind == "screw":
        d, dk, k, s, t, _range = r
        return {"d": d, "dk": dk, "k": k, "s": s, "t": t}
    if kind == "nut":
        d, s, m = r
        return {"d": d, "s": s, "m": m, "e": 2.0 * s / SQRT3}
    if kind == "washer":
        d1, d2, h = r
        return {"d1": d1, "d2": d2, "h": h}
    if kind == "insert":
        d, outside, length, hole = r
        return {"d": d, "outside": outside, "length": length, "hole": hole}
    diameter, thickness = r
    return {"diameter": diameter, "thickness": thickness}


def nominal(standard, size):
    """The screw diameter a part goes with (a magnet: its own diameter)."""
    kind = kind_of(standard)
    if kind == "magnet":
        return MAGNETS[size][0]
    if kind == "washer":
        return _size_number(size)
    return row(standard, size)[0]


# -- options -------------------------------------------------------------------------------------
def with_defaults(options=None):
    o = dict(DEFAULTS)
    o.update({k: v for k, v in (options or {}).items() if v is not None})
    if o["standard"] not in STANDARDS:
        o["standard"] = standards(o["kind"])[0][0] if o["kind"] in dict(KINDS) else "iso4762"
    o["kind"] = kind_of(o["standard"])
    if o["size"] not in STANDARDS[o["standard"]][3]:
        o["size"] = default_size(o["standard"])
    if has_length(o["standard"]):
        try:
            o["length"] = float(o["length"])
        except (TypeError, ValueError):
            o["length"] = default_length(o["standard"], o["size"])
    if (options or {}).get("sink_head") is None:
        o["sink_head"] = default_sink(o["standard"])
    o["flip"] = bool(o["flip"])
    o["make_hole"] = bool(o["make_hole"])
    o["sink_head"] = bool(o["sink_head"])
    o["clearance"] = float(o["clearance"])
    return o


def default_sink(standard):
    """Socket and countersunk heads go into the part by default; a button head is made to sit
    on the face (Guess)."""
    return standard != "iso7380"


def change_standard(options, standard):
    """The options for another standard: its default size (the same size when it has it),
    length and head setting."""
    o = with_defaults(options)
    size = o["size"] if o["size"] in STANDARDS[standard][3] else default_size(standard)
    o.update(standard=standard, kind=kind_of(standard), size=size, sink_head=default_sink(standard))
    if has_length(standard):
        o["length"] = fit_length(standard, size, o.get("length"))
    return o


def fit_length(standard, size, length):
    """The length kept when the size changes: the same one when the new size has it, else
    the new size's default."""
    found = lengths(standard, size)
    try:
        length = float(length)
    except (TypeError, ValueError):
        length = None
    if length is not None and any(abs(v - length) < 1e-9 for v in found):
        return length
    return default_length(standard, size)


def check(options):
    """Raise HardwareError when the options cannot make a part; returns the options."""
    o = with_defaults(options)
    row(o["standard"], o["size"])
    if has_length(o["standard"]):
        if o["length"] <= 0:
            raise HardwareError("The screw length must be more than 0.")
        if o["standard"] == "iso10642" and o["length"] <= dims(o["standard"], o["size"])["k"]:
            raise HardwareError("A countersunk screw's length counts its head: make it longer.")
    if o["fit"] not in dict(FITS):
        raise HardwareError("The fit must be Close, Normal or Loose.")
    if o["hole_depth"] not in dict(HOLE_DEPTHS):
        raise HardwareError("The hole depth must be Through All or Screw length.")
    if o["kind"] == "magnet" and not 0.0 <= o["clearance"] < 5.0:
        raise HardwareError("The magnet's clearance must be between 0 and 5 mm.")
    return o


def name(options):
    """The part's name, size first: "M3x10 ISO 4762", "M3 ISO 4032", "Magnet 6x3"."""
    o = with_defaults(options)
    kind, _label, ending, _table = STANDARDS[o["standard"]]
    if kind == "magnet":
        d, t = MAGNETS[o["size"]]
        return "Magnet %gx%g" % (d, t)
    if kind == "screw":
        return "M%sx%g %s" % (o["size"], o["length"], ending)
    if kind == "insert":
        return "M%s Heat-set insert" % o["size"]
    return "M%s %s" % (o["size"], ending)


# -- the hole ------------------------------------------------------------------------------------
def head_cut(options):
    """The counterbore or countersink a sunk screw head sits in: {"hole_type", "diameter",
    "depth" | "angle"}, or None (not a screw, or the head sits on the face)."""
    o = with_defaults(options)
    if o["kind"] != "screw" or not o["sink_head"]:
        return None
    size = o["size"]
    if o["standard"] == "iso4762":
        return hole_tables.head_cut("iso", "socket_head", size)
    if o["standard"] == "iso10642":
        return hole_tables.head_cut("iso", "countersunk", size)
    dm = dims(o["standard"], size)  # a button head: dk + 1, as deep as DIN 974-1's rule
    return {
        "hole_type": "counterbore",
        "diameter": round(dm["dk"] + BUTTON_CBORE_EXTRA, 4),
        "depth": hole_tables._cbore_depth(dm["k"], dm["d"]),
    }


def clearance(options):
    """The clearance hole's diameter for the screw that goes through (ISO 273)."""
    o = with_defaults(options)
    d = nominal(o["standard"], o["size"])
    return hole_tables.clearance_diameter("iso", o["size"], d, o["fit"])


def seat(options):
    """Height of the part's seat above the clicked face (its frame's z). A sunk socket or
    button head sits at the bottom of its counterbore (made with the hole, or already there:
    the top rim of a counterbore was clicked), a sunk countersunk head flush with the face;
    a countersunk head not sunk sits with its cone on the face. Everything else sits at 0."""
    o = with_defaults(options)
    if o["kind"] != "screw":
        return 0.0
    if o["standard"] == "iso10642":
        return 0.0 if o["sink_head"] else dims(o["standard"], o["size"])["k"]
    cut = head_cut(o)
    if cut is not None and cut["hole_type"] == "counterbore":
        return -float(cut["depth"])
    return 0.0


def hole_options(options):
    """The Hole step the part needs (hole.py options), or None when "make the hole" is off."""
    o = check(options)
    if not o["make_hole"]:
        return None
    kind = o["kind"]
    base = {"drill_point": "flat", "flip": False}
    if kind == "insert":
        dm = dims(o["standard"], o["size"])
        return dict(
            base,
            tap_type="simple",
            hole_type="simple",
            diameter=dm["hole"],
            extent="distance",
            depth=round(dm["length"] + INSERT_EXTRA_DEPTH, 4),
        )
    if kind == "magnet":
        dm = dims(o["standard"], o["size"])
        return dict(
            base,
            tap_type="simple",
            hole_type="simple",
            diameter=round(dm["diameter"] + o["clearance"], 4),
            extent="distance",
            depth=dm["thickness"],
        )
    out = dict(
        base,
        tap_type="clearance",
        standard="iso",
        size=o["size"],
        designation="",  # hole.py takes the size's coarse thread (M3x0.5)
        fit=o["fit"],
        hole_type="simple",
        extent="all",
        depth=10.0,
        fastener="",
    )
    cut = head_cut(o) if kind == "screw" else None
    if cut is not None:
        out["hole_type"] = cut["hole_type"]
        if cut["hole_type"] == "counterbore":
            out.update(fastener="socket_head", cbore_diameter=cut["diameter"])
            out["cbore_depth"] = cut["depth"]
        else:
            out.update(fastener="countersunk", csink_diameter=cut["diameter"])
            out["csink_angle"] = cut["angle"]
    if kind == "screw" and o["hole_depth"] == "length":
        out["extent"] = "distance"
        depth = o["length"]  # a countersunk screw's length counts its head
        if o["standard"] != "iso10642":
            depth -= seat(o)  # the shank starts at the bottom of the counterbore
        out["depth"] = round(depth, 4)
    return out


# -- automatic size (Fusion's Size: Automatic, from the hole clicked) ---------------------------
def head_fits_rim(standard, size, diameter):
    """True when a round edge this wide is the top of the counterbore or countersink this
    screw's head sinks into (wider than any clearance hole for it): the head goes in."""
    if kind_of(standard) != "screw":
        return False
    loose = hole_tables.clearance_diameter("iso", size, nominal(standard, size), "loose")
    return float(diameter) > loose + 0.1


def size_for_hole(standard, diameter, current=None):
    """The size of `standard` that goes into a round hole of this diameter, or None: a
    clearance hole (between the screw's diameter and its loose fit), a tapped hole for it (a
    little under the screw's diameter), the counterbore or countersink of its head, an
    insert's hole, a magnet's pocket. When several fit equally well (6 x 2 and 6 x 3 magnets,
    M2.5 and M3 inserts share a hole), `current` wins."""
    kind = kind_of(standard)
    diameter = float(diameter)
    best = None
    for size in sizes(standard):
        if kind == "magnet":
            d = MAGNETS[size][0]
            lo, hi, target = d - 0.05, d + 0.6, d + MAGNET_CLEARANCE
        elif kind == "insert":
            hole = INSERTS[size][3]
            lo, hi, target = hole - 0.3, hole + 0.3, hole
        else:
            d = nominal(standard, size)
            lo = 0.75 * d
            hi = hole_tables.clearance_diameter("iso", size, d, "loose") + 0.1
            # a clearance hole of any fit, or the tap drill (about d - pitch, 0.84 d)
            target = tuple(
                hole_tables.clearance_diameter("iso", size, d, fit) for fit, _ in FITS
            ) + (0.84 * d,)
            cut = head_cut({"standard": standard, "size": size, "sink_head": True})
            if cut is not None and abs(diameter - cut["diameter"]) <= 0.3:
                lo, hi, target = cut["diameter"] - 0.3, cut["diameter"] + 0.3, cut["diameter"]
        if lo - 1e-9 <= diameter <= hi + 1e-9:
            targets = target if isinstance(target, tuple) else (target,)
            score = min(abs(diameter - t) for t in targets)
            score -= 1e-6 if size == current else 0.0
            if best is None or score < best[0]:
                best = (score, size)
    return best[1] if best else None


# -- sizes and volumes of the solids (hardware.py builds exactly these) -------------------------
def hex_area(s):
    """Area of a regular hexagon s across the flats."""
    return SQRT3 / 2.0 * s * s


def cap_radius(base_radius, height):
    """Radius of the sphere a cap of this base radius and height is cut from."""
    return (base_radius * base_radius + height * height) / (2.0 * height)


def dome_socket(dk, k, s, t, steps=2000):
    """What a hexagon socket s across the flats, t deep from the top, takes out of a button
    head (a spherical cap dk wide and k high): the socket's walls end where the dome falls
    away, so it is less than hex_area(s) * t. Over each twelfth of the hexagon (polar angle
    phi from a flat's middle, out to (s / 2) / cos(phi)) the depth below the dome is
    integrated in closed form; Simpson's rule takes it round the angle."""
    big = cap_radius(dk / 2.0, k)
    a = big - t  # the socket's floor, measured up from the sphere's centre
    if a >= big:
        return 0.0
    edge = math.sqrt(max(0.0, big * big - a * a))  # where the floor meets the dome

    def radial(rho):
        # integral of (sqrt(R^2 - r^2) - a) r dr from 0 to rho, written without the
        # difference of two cubes of R (a wide, flat dome lost every digit that way)
        rho = min(rho, edge)
        b = math.sqrt(max(0.0, big * big - rho * rho))
        cubes = rho * rho / (big + b) * (big * big + big * b + b * b) / 3.0  # (R^3 - b^3) / 3
        return cubes - a * rho * rho / 2.0

    n = steps if steps % 2 == 0 else steps + 1
    hi = math.pi / 6.0
    h = hi / n
    total = 0.0
    for i in range(n + 1):
        phi = i * h
        w = 1 if i in (0, n) else (4 if i % 2 else 2)
        total += w * radial((s / 2.0) / math.cos(phi))
    return 12.0 * total * h / 3.0


def volume(options):
    """The solid's volume (mm3), worked out by hand from the shapes hardware.py builds."""
    o = with_defaults(options)
    dm = dims(o["standard"], o["size"])
    kind = o["kind"]
    pi = math.pi
    if kind == "nut":
        return (hex_area(dm["s"]) - pi * dm["d"] ** 2 / 4.0) * dm["m"]
    if kind == "washer":
        return pi / 4.0 * (dm["d2"] ** 2 - dm["d1"] ** 2) * dm["h"]
    if kind == "insert":
        return pi / 4.0 * (dm["outside"] ** 2 - dm["d"] ** 2) * dm["length"]
    if kind == "magnet":
        return pi / 4.0 * dm["diameter"] ** 2 * dm["thickness"]
    d, dk, k, s, t = dm["d"], dm["dk"], dm["k"], dm["s"], dm["t"]
    socket = hex_area(s) * t
    length = o["length"]
    if o["standard"] == "iso4762":
        return pi * dk * dk / 4.0 * k - socket + pi * d * d / 4.0 * length
    if o["standard"] == "iso7380":
        big = cap_radius(dk / 2.0, k)
        dome = pi * k * k * (3.0 * big - k) / 3.0
        return dome - dome_socket(dk, k, s, t) + pi * d * d / 4.0 * length
    big, small = dk / 2.0, d / 2.0
    cone = pi * k / 3.0 * (big * big + big * small + small * small)
    return cone - socket + pi * small * small * (length - k)


def extent(options):
    """(bottom, top) of the solid along its own z before the seat and flip are applied."""
    o = with_defaults(options)
    dm = dims(o["standard"], o["size"])
    kind = o["kind"]
    if kind == "nut":
        return 0.0, dm["m"]
    if kind == "washer":
        return 0.0, dm["h"]
    if kind == "insert":
        return -dm["length"], 0.0
    if kind == "magnet":
        return -dm["thickness"], 0.0
    if o["standard"] == "iso10642":
        return -o["length"], 0.0
    return -o["length"], dm["k"]
