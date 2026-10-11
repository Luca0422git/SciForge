# SPDX-License-Identifier: LGPL-2.1-or-later
"""The number logic of Box, Cylinder, Sphere, Torus, Coil and Pipe: no FreeCAD, no Qt, so
it is unit tested (SciForgeTests/unit/test_primitives_core.py). primitives.py, coil.py and
pipe.py build the geometry from it; the dialogs use its rounding.

Fusion's sizes and the checks that keep a value the dialog cannot build from reaching
FreeCAD (where it would fail with a message about OpenCASCADE instead of what to change).
"""
import math

OPERATIONS = ("join", "cut", "intersect", "new_body")
POSITIONS = ("inside", "center", "outside")
KINDS = ("box", "cylinder", "sphere", "torus")
COIL_TYPES = ("rev_height", "rev_pitch", "height_pitch", "spiral")
COIL_SECTIONS = ("circular", "square", "tri_ext", "tri_int")
PIPE_SECTIONS = ("circular", "square", "triangular")
# Which values each coil type takes from the dialog (the others are worked out).
COIL_USES = {
    "rev_height": ("revolutions", "height", "angle"),
    "rev_pitch": ("revolutions", "pitch", "angle"),
    "height_pitch": ("height", "pitch", "angle"),
    "spiral": ("revolutions", "pitch"),
}


class PrimitiveError(ValueError):
    """It cannot be built as asked; the message says why and what to do."""


# -- round numbers ------------------------------------------------------------------------------
def nice(value):
    """A round number at or just above `value` (1, 2, 2.5, 5 x 10^n): Fusion's first values
    look like that."""
    value = abs(float(value))
    if value < 1e-9:
        return 1.0
    power = 10.0 ** math.floor(math.log10(value))
    for step in (1.0, 2.0, 2.5, 5.0, 10.0):
        if value <= step * power * 1.0001:
            return step * power
    return 10.0 * power


def nice_floor(value):
    """The largest round step (1, 2.5, 5 x 10^n) not above `value`: clicks land on values a
    person would type (every multiple of 5 mm is reachable at any normal zoom), and the
    step is never finer than the few pixels a hand misses by."""
    value = abs(float(value))
    if value < 1e-9:
        return 0.0
    power = 10.0 ** math.floor(math.log10(value))
    best = power
    for step in (1.0, 2.5, 5.0):
        if step * power <= value * 1.0001:
            best = step * power
    return best


def nearest_snap(x, y, snaps, reach):
    """The snap point (x, y) nearest to the mouse at (x, y) within `reach` (plane units),
    or None when none is that close."""
    best = None
    for sx, sy in snaps:
        gap = math.hypot(x - sx, y - sy)
        if gap <= reach and (best is None or gap < best[0]):
            best = (gap, (sx, sy))
    return None if best is None else best[1]


def round_to(value, step):
    """`value` to the nearest multiple of `step` (halves go up, never to -0.0)."""
    if step <= 0:
        return value
    out = math.floor(value / step + 0.5) * step
    return round(out, 9) + 0.0


# -- the operation Fusion picks ----------------------------------------------------------------------
def operation_for(has_solid, inside, outside, gap):
    """Fusion's choice when the user did not pick one, from how the new solid sits against
    the part: mostly inside -> cut, touching or overlapping -> join, away from every solid
    (or the first solid) -> new body. inside/outside: volumes, gap: the distance between."""
    if not has_solid:
        return "new_body"
    total = inside + outside
    if inside > outside + 1e-6 * max(1.0, total):
        return "cut"
    if inside > 1e-9:
        return "join"
    return "join" if gap < 1e-6 else "new_body"


# -- Box, Cylinder, Sphere, Torus ------------------------------------------------------------------------
def torus_radii(options):
    """(ring radius, section radius) of a torus from Fusion's fields: the section sits
    inside, on or outside the inner circle."""
    inner = float(options["inner_diameter"]) / 2.0
    minor = float(options["torus_diameter"]) / 2.0
    position = options.get("position", "center")
    if position == "inside":
        return inner - minor, minor
    if position == "outside":
        return inner + minor, minor
    return inner, minor


def thickest_torus(options):
    """The largest torus diameter that still leaves a hole in the middle."""
    inner = float(options["inner_diameter"])
    position = options.get("position", "center")
    if position == "inside":
        return inner / 2.0  # R = D/2 - r > r  ->  2r < D/2
    if position == "outside":
        return float("inf")
    return inner  # R = D/2 > r  ->  2r < D


def check_sizes(kind, options):
    """Raise PrimitiveError when the values cannot make the solid (said in the dialog)."""
    if kind not in KINDS:
        raise PrimitiveError("Unknown primitive %r." % kind)
    if options.get("operation") not in OPERATIONS:
        raise PrimitiveError("Unknown operation %r." % options.get("operation"))

    def size(key, what):
        try:
            value = float(options[key])
        except Exception:
            raise PrimitiveError("%s must be a number." % what)
        if abs(value) < 1e-6:
            raise PrimitiveError("%s cannot be 0. Type a size or drag the arrow." % what)
        return value

    if kind == "box":
        if size("length", "Length") < 0 or size("width", "Width") < 0:
            raise PrimitiveError("Length and Width are sizes: type positive values.")
        size("height", "Height")
    elif kind == "cylinder":
        if size("diameter", "Diameter") < 0:
            raise PrimitiveError("The diameter must be positive.")
        size("height", "Height")
    elif kind == "sphere":
        if size("diameter", "Diameter") < 0:
            raise PrimitiveError("The diameter must be positive.")
    elif kind == "torus":
        if size("inner_diameter", "Inner Diameter") < 0:
            raise PrimitiveError("The inner diameter must be positive.")
        if size("torus_diameter", "Torus Diameter") < 0:
            raise PrimitiveError("The torus diameter must be positive.")
        if options.get("position") not in POSITIONS:
            raise PrimitiveError("Position must be Inside, On Center or Outside.")
        major, minor = torus_radii(options)
        if major <= minor + 1e-6:
            raise PrimitiveError(
                "The ring is too thick for its diameter: it would close up in the middle. "
                "Make the torus diameter smaller (under %.4g mm here) or the inner diameter "
                "larger." % thickest_torus(options)
            )
    return options


def box_corner(options):
    """(x, y, z) of the box's lowest corner in the plane's frame."""
    length, width = abs(float(options["length"])), abs(float(options["width"]))
    x, y = float(options["x"]), float(options["y"])
    x0 = x if float(options.get("sx", 1.0)) >= 0 else x - length
    y0 = y if float(options.get("sy", 1.0)) >= 0 else y - width
    return x0, y0, min(float(options["height"]), 0.0)


def volume(kind, options):
    """The primitive's own volume (before it is joined or cut)."""
    if kind == "box":
        return abs(float(options["length"]) * float(options["width"]) * float(options["height"]))
    if kind == "cylinder":
        r = float(options["diameter"]) / 2.0
        return math.pi * r * r * abs(float(options["height"]))
    if kind == "sphere":
        r = float(options["diameter"]) / 2.0
        return 4.0 / 3.0 * math.pi * r**3
    major, minor = torus_radii(options)
    return 2.0 * math.pi * math.pi * major * minor * minor


# -- Coil --------------------------------------------------------------------------------------------------
def coil_section_extent(options):
    """(how far the coil's section reaches outward, inward, along the axis) from its
    centre. Section Size is the diameter of the circle round the section (Fusion)."""
    size = float(options["section_size"])
    kind = options["section"]
    if kind == "square":
        half = size / (2.0 * math.sqrt(2.0))
        return half, half, 2.0 * half
    if kind in ("tri_ext", "tri_int"):
        r = size / 2.0
        side = r * math.sqrt(3.0)
        return (r, r / 2.0, side) if kind == "tri_ext" else (r / 2.0, r, side)
    return size / 2.0, size / 2.0, size


def coil_section_radius(options):
    """Distance of the section's centre from the axis (at the start)."""
    out, inward, _ = coil_section_extent(options)
    half = float(options["diameter"]) / 2.0
    position = options["section_position"]
    if position == "inside":
        return half - out
    if position == "outside":
        return half + inward
    return half


def coil_section_points(options):
    """Outline of the coil's section in its upright plane: x away from the axis, y along
    it (None for the circle)."""
    rc = coil_section_radius(options)
    size = float(options["section_size"])
    kind = options["section"]
    if kind == "square":
        h = size / (2.0 * math.sqrt(2.0))
        return [(rc - h, -h), (rc + h, -h), (rc + h, h), (rc - h, h)]
    if kind in ("tri_ext", "tri_int"):
        r = size / 2.0
        sign = 1.0 if kind == "tri_ext" else -1.0
        return [
            (rc + sign * r, 0.0),
            (rc - sign * r / 2.0, r * math.sqrt(3.0) / 2.0),
            (rc - sign * r / 2.0, -r * math.sqrt(3.0) / 2.0),
        ]
    return None


def coil_resolved(options):
    """(revolutions, height, pitch) as the coil will have them, whatever the type."""
    kind = options["type"]
    turns = float(options["revolutions"])
    height = float(options["height"])
    pitch = float(options["pitch"])
    if kind == "rev_height":
        pitch = abs(height) / turns if turns > 0 else 0.0
    elif kind == "rev_pitch":
        height = turns * pitch * (-1.0 if height < 0 else 1.0)
    elif kind == "height_pitch":
        turns = abs(height) / pitch if pitch > 0 else 0.0
    else:
        height = 0.0
    return turns, height, pitch


def coil_check(options):
    """Raise PrimitiveError with what to change when the values cannot make a coil."""
    for key, values in (
        ("type", COIL_TYPES),
        ("section", COIL_SECTIONS),
        ("section_position", POSITIONS),
        ("operation", OPERATIONS),
    ):
        if options.get(key) not in values:
            raise PrimitiveError("Unknown %s %r." % (key.replace("_", " "), options.get(key)))
    kind = options["type"]
    if float(options["diameter"]) <= 1e-6:
        raise PrimitiveError("The diameter must be larger than 0.")
    if float(options["section_size"]) <= 1e-6:
        raise PrimitiveError("The section size must be larger than 0.")
    uses = COIL_USES[kind]
    if "revolutions" in uses and float(options["revolutions"]) <= 1e-6:
        raise PrimitiveError("Revolutions must be more than 0.")
    if "height" in uses and abs(float(options["height"])) <= 1e-6:
        raise PrimitiveError("The height cannot be 0.")
    if "pitch" in uses and float(options["pitch"]) <= 1e-6:
        raise PrimitiveError("The pitch must be more than 0.")
    angle = float(options.get("angle", 0.0)) if "angle" in uses else 0.0
    if abs(angle) >= 89.0:
        raise PrimitiveError("The angle must stay between -89 and 89 degrees.")
    out, inward, along = coil_section_extent(options)
    rc = coil_section_radius(options)
    if rc - inward <= 1e-6:
        raise PrimitiveError(
            "The section reaches the coil's axis: make the section smaller than the coil "
            "or place it outside the diameter."
        )
    turns, height, pitch = coil_resolved(options)
    if kind == "spiral":
        if pitch <= out + inward + 1e-6:
            raise PrimitiveError(
                "The turns of the spiral touch each other: the pitch must be larger than the "
                "section (%.4g mm)." % (out + inward)
            )
    else:
        # Turns closer than the section would cut into each other (OpenCASCADE then fails).
        axial = pitch * math.cos(math.radians(angle))
        if turns > 1.0 + 1e-9 and axial <= along + 1e-6:
            raise PrimitiveError(
                "The turns touch each other: the pitch (%.4g mm) must be larger than the "
                "section (%.4g mm). Make the coil taller, use fewer revolutions or a smaller "
                "section." % (pitch, along)
            )
        top = rc + abs(height) * math.tan(math.radians(angle))
        if top - inward <= 1e-6:
            raise PrimitiveError(
                "With this angle the coil narrows to its axis before the end. Make the "
                "angle smaller or the coil shorter."
            )
    return options


def coil_volume(options):
    """The coil's volume by Pappus: section area x the path its centre of area travels
    round the axis (FreeCAD's helix sweeps the upright section, so rising adds nothing)."""
    size = float(options["section_size"])
    kind = options["section"]
    rc = coil_section_radius(options)
    if kind == "circular":
        area = math.pi * size * size / 4.0
    elif kind == "square":
        area = size * size / 2.0
    else:
        r = size / 2.0
        area = 3.0 * math.sqrt(3.0) / 4.0 * r * r  # the circle's centre is the centroid
    turns, height, pitch = coil_resolved(options)
    if options["type"] == "spiral":
        mean = rc + pitch * turns / 2.0
    else:
        mean = rc + abs(height) / 2.0 * math.tan(math.radians(float(options.get("angle", 0.0))))
    return area * 2.0 * math.pi * mean * turns


# -- Pipe --------------------------------------------------------------------------------------------------
def pipe_wall_limit(options):
    """The thickest wall a hollow section can have (half its inner span)."""
    size = float(options["section_size"])
    return {
        "circular": size / 2.0,  # radius
        "square": size / (2.0 * math.sqrt(2.0)),  # half side
        "triangular": size / 4.0,  # inradius
    }[options["section"]]


def pipe_check(options):
    for key, values in (("section", PIPE_SECTIONS), ("operation", OPERATIONS)):
        if options.get(key) not in values:
            raise PrimitiveError("Unknown %s %r." % (key, options.get(key)))
    distance = float(options["distance"])
    if distance <= 1e-6 or distance > 1.0 + 1e-9:
        raise PrimitiveError("The distance goes from 0 (start) to 1 (the whole path).")
    if float(options["section_size"]) <= 1e-6:
        raise PrimitiveError("The section size must be larger than 0.")
    if options.get("hollow"):
        t = float(options.get("thickness", 0.0))
        if t <= 1e-6:
            raise PrimitiveError("The section thickness must be larger than 0.")
        limit = pipe_wall_limit(options)
        if t >= limit - 1e-6:
            raise PrimitiveError(
                "The wall is as thick as the section, so nothing would be hollow. Make the "
                "thickness smaller than %.4g mm." % limit
            )
    return options


def pipe_section_area(options):
    size = float(options["section_size"])
    kind = options["section"]
    t = float(options.get("thickness", 0.0)) if options.get("hollow") else 0.0

    def area(s):
        if kind == "square":
            return s * s / 2.0
        if kind == "triangular":
            return 3.0 * math.sqrt(3.0) / 16.0 * s * s
        return math.pi * s * s / 4.0

    if not t:
        return area(size)
    inner = {"square": size - 2.0 * math.sqrt(2.0) * t, "triangular": size - 4.0 * t}.get(
        kind, size - 2.0 * t
    )
    return area(size) - area(inner)
