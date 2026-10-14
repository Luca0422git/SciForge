# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of Fusion's Emboss, without FreeCAD: depth and effect, the alignment of the
profile on the face, and how a flat profile is wrapped onto a cylinder or a cone without
stretching (both can be unrolled flat, so a letter keeps its size and shape on them).

Fusion's Emboss dialog (Autodesk help "Emboss a solid body", "Reference: Emboss"):
  Sketch Profiles   closed sketch areas or text (any font but single-line ones)
  Faces             the faces of a body to emboss on; Tangent Chain picks the faces
                    joined smoothly to a picked one too
  Effect            Emboss adds material, Deboss removes it
  Depth             a negative depth swaps Emboss and Deboss
  Alignment         Horizontal Distance, Vertical Distance, Rotation Angle (each also a
                    handle on the face)
Fusion wraps onto flat, cylindrical and conical faces and refuses faces curved in two
directions (an Autodesk answer on its forum); SciForge projects onto those along the
sketch's direction instead and says so.

Coordinates here: the profile's own 2D (x, y) (sketch axes, relative to the anchor, the
middle of the profiles), and the face's tangent plane at the anchor (a, b) along the
face's parameter directions (around / along for a cylinder or cone).
"""

import math

EFFECTS = ("emboss", "deboss")
KINDS = ("plane", "cylinder", "cone", "other")
MIN_DEPTH = 0.001  # mm
MAX_DEPTH = 10000.0
DEFAULT_DEPTH = 1.0
EPS = 0.005  # mm: the raised letters start this far inside the part (a clean join)


class EmbossError(ValueError):
    """The emboss cannot be made; the message says why and what to try."""


def default_options():
    return {
        "effect": "emboss",
        "depth": DEFAULT_DEPTH,
        "h": 0.0,
        "v": 0.0,
        "angle": 0.0,
        "tangent_chain": True,
    }


def effect_of(depth, effect):
    """Fusion: a negative depth swaps Emboss and Deboss. Returns (depth > 0, effect)."""
    depth = float(depth)
    if effect not in EFFECTS:
        raise EmbossError("Unknown effect %r." % effect)
    if depth < 0:
        return -depth, ("deboss" if effect == "emboss" else "emboss")
    return depth, effect


def check_depth(depth):
    if not (MIN_DEPTH <= float(depth) <= MAX_DEPTH):
        raise EmbossError(
            "The depth must be between %g and %g mm (and not 0)." % (MIN_DEPTH, MAX_DEPTH)
        )


def signed(depth, effect):
    """The depth along the face's outward normal: + for Emboss, - for Deboss."""
    return depth if effect == "emboss" else -depth


def kind_of(type_id):
    """The surface kind Emboss knows from a FreeCAD surface type."""
    return {
        "Part::GeomPlane": "plane",
        "Part::GeomCylinder": "cylinder",
        "Part::GeomCone": "cone",
    }.get(type_id, "other")


def align(x, y, h=0.0, v=0.0, angle_deg=0.0):
    """The profile point (x, y) after the Alignment: turned by Rotation Angle about the
    anchor, then moved by Horizontal / Vertical Distance (the profile's own axes)."""
    a = math.radians(angle_deg)
    co, si = math.cos(a), math.sin(a)
    return (co * x - si * y + h, si * x + co * y + v)


def to_tangent(x, y, xa, xb, ya, yb):
    """(a, b) of profile point (x, y), the profile's axes landing on the tangent plane as
    the unit vectors (xa, xb) and (ya, yb) in the face's (a, b) directions."""
    return (x * xa + y * ya, x * xb + y * yb)


# -- unrolling -----------------------------------------------------------------------------------
def cylinder_uv(a, b, radius, u0, v0):
    """Cylinder parameters of tangent-plane point (a, b) (a around, b along the axis)
    when the cylinder is rolled over that plane from the anchor (u0, v0): an arc of
    length a is a turn of a / radius."""
    if radius <= 0:
        raise EmbossError("The cylinder has no radius.")
    return (u0 + a / radius, v0 + b)


def cone_uv(a, b, radius, semi_angle, u0, v0):
    """Cone parameters (OpenCASCADE's: u the turn, v along the side from the reference
    circle of `radius`) of tangent-plane point (a, b) at the anchor (u0, v0) (a around,
    b along the side toward +v). The cone is unrolled about its apex: a circle sector
    where the distance from the apex stays and the turn shrinks by sin(semi angle)."""
    s = math.sin(semi_angle)
    if abs(s) < 1e-12:
        return cylinder_uv(a, b, radius, u0, v0)
    k = abs(s)
    sign = 1.0 if s > 0 else -1.0
    rho0 = (radius + v0 * s) / k  # the anchor's distance from the apex
    if rho0 <= 1e-9:
        raise EmbossError("The profile sits on the cone's tip: move it along the cone.")
    x = rho0 + sign * b
    rho = math.hypot(x, a)
    if rho < 1e-9:
        raise EmbossError("The profile reaches the cone's tip: move it or make it smaller.")
    turn = math.atan2(a, x)
    return (u0 + turn / k, v0 + sign * (rho - rho0))


def fits_around(width, radius):
    """True if a profile `width` mm long around a cylinder of `radius` does not reach
    round onto itself."""
    return width < 2.0 * math.pi * radius - 1e-9


def check_deboss_depth(depth, kind, radius=None):
    """A deboss into a round part must stop before its axis."""
    if kind in ("cylinder", "cone") and radius is not None and depth >= radius:
        raise EmbossError(
            "A deboss %g mm deep goes past the middle of this round face (radius %g mm). "
            "Make it shallower." % (depth, radius)
        )


def samples(length, step=0.5, low=8, high=64):
    """How many points to follow a curve of `length` mm by (cones and other faces)."""
    return max(low, min(high, int(math.ceil(length / step)) + 1))
