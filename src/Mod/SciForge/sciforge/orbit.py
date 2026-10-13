# SPDX-License-Identifier: LGPL-2.1-or-later
"""The orbit's two modes and the camera maths for orbiting about a chosen point, without
Qt or FreeCAD (unit tested). orbit_ui.py puts it to work.

Fusion has two orbit modes:

* **Constrained** (the default): the model turns about its up axis (Z) for sideways mouse
  moves and tilts toward or away from you for up/down moves; it never rolls, so vertical
  edges stay vertical. FreeCAD calls this "Free Turntable" (OrbitStyle 2).
* **Free**: the model tumbles in any direction, rolling included. FreeCAD's "Rounded
  Arcball" (OrbitStyle 4) is the nearest: an arcball inside, a pure roll towards the
  edges of the view, like the ring of Fusion's and Inventor's free orbit. (FreeCAD's plain
  "Trackball", 1, never gives a clean roll; "Trackball Classic", 3, only turns about the
  screen's axes.) Which one Fusion really feels like is unconfirmed.

The orbit centre (pivot): FreeCAD's own orbit turns about the point the camera looks at
(the middle of the window), and FreeCAD gives Python no way to move that centre. So when
a person sets an orbit centre (Shift + a middle click on the model, or Set Orbit Center),
SciForge turns the camera itself with `orbit_camera`: the orientation changes exactly as
in the constrained (or free) orbit, and the camera's position swings round the pivot so
the pivot stays on the same pixel of the screen.

Rotations are quaternions (x, y, z, w) like FreeCAD's ``Rotation.Q``; see viewcube.py.
"""
import math

from . import viewcube

CONSTRAINED = "constrained"
FREE = "free"
MODES = (CONSTRAINED, FREE)
DEFAULT_MODE = CONSTRAINED
LABELS = {CONSTRAINED: "Constrained Orbit", FREE: "Free Orbit"}
# FreeCAD's OrbitStyle for each mode (View preference group).
FREECAD_STYLE = {CONSTRAINED: 2, FREE: 4}

# FreeCAD's own orbit maps the mouse onto a sphere of this radius drawn in a square
# -1..1 over the view (NavigationStyle.cpp, FCSphereSheetProjector): a move of one pixel
# near the middle of the view turns the camera by about 2 / (size * radius) radians, times
# FreeCAD's "Sensitivity" (2), with size the view's width for sideways moves and its height
# for up/down moves. The pivot orbit uses the same figures, so it feels like the orbit
# without a pivot (checked in the orbit_feel scenario: the same drag turns within a few
# percent of FreeCAD's own).
FREECAD_SPHERE_RADIUS = 0.8

# The dot that marks the orbit centre (orbit_ui draws it as a Coin node of this name).
MARKER_NAME = "SciForgeOrbitCenter"
MARKER_COLOUR = (0.24, 0.80, 0.36)  # a clear green (SciForge's own shade)


def normalise_mode(text):
    """The orbit mode named by a preference string (anything unknown: the default)."""
    text = str(text or "").strip().lower()
    return text if text in MODES else DEFAULT_MODE


def freecad_style(mode):
    return FREECAD_STYLE[normalise_mode(mode)]


def mode_of_style(style):
    """The mode whose FreeCAD OrbitStyle this is (None for a style SciForge does not use)."""
    for mode, value in FREECAD_STYLE.items():
        if value == style:
            return mode
    return None


def degrees_per_pixel(width, height, sensitivity=2.0):
    """(sideways, up/down) degrees one pixel of mouse movement turns the camera in FreeCAD's
    own orbit, for a view of this size in pixels (near the middle of the view). FreeCAD
    multiplies the turn by its "Sensitivity" preference (2 by default) when that is above 1."""
    width = max(1.0, float(width))
    height = max(1.0, float(height))
    factor = sensitivity if sensitivity > 1.0 else 1.0
    return (
        math.degrees(2.0 * factor / (width * FREECAD_SPHERE_RADIUS)),
        math.degrees(2.0 * factor / (height * FREECAD_SPHERE_RADIUS)),
    )


def orbit_free(q, dx, dy, deg_x, deg_y):
    """A free orbit for a mouse move of (dx, dy) pixels (y grows downwards): the camera turns
    about its own up axis for sideways moves and about its sideways axis for up/down moves
    (a classic trackball). Straight moves never roll; a loop of moves does, like any
    trackball. Used by the ViewCube's drag in Free mode."""
    right, up, _ = viewcube.camera_axes(q)
    yaw = viewcube.q_axis_angle(up, math.radians(-dx * deg_x))
    pitch = viewcube.q_axis_angle(right, math.radians(-dy * deg_y))
    return viewcube.q_unit(viewcube.q_mul(yaw, viewcube.q_mul(pitch, q)))


def orbit_constrained(q, dx, dy, deg_x, deg_y):
    """Fusion's constrained orbit (a turntable): sideways moves turn about the world's Z,
    up/down moves tilt about the camera's sideways axis; the camera can never roll. The same
    turn as viewcube.orbit, with separate scales for the two directions."""
    right, up, _ = viewcube.camera_axes(q)
    side = 1.0 if up[2] >= 0 else -1.0  # upside down, sideways moves turn the other way
    spin = viewcube.q_axis_angle((0.0, 0.0, 1.0), math.radians(-dx * deg_x * side))
    tilt = viewcube.q_axis_angle(right, math.radians(-dy * deg_y))
    return viewcube.q_unit(viewcube.q_mul(spin, viewcube.q_mul(tilt, q)))


def turn(q, dx, dy, mode=CONSTRAINED, deg_x=viewcube.ORBIT_DEG_PER_PIXEL, deg_y=None):
    """The camera orientation after a mouse move of (dx, dy) pixels in this orbit mode."""
    deg_y = deg_x if deg_y is None else deg_y
    if normalise_mode(mode) == FREE:
        return orbit_free(q, dx, dy, deg_x, deg_y)
    return orbit_constrained(q, dx, dy, deg_x, deg_y)


def orbit_camera(position, q, pivot, dx, dy, mode=CONSTRAINED, deg_x=None, deg_y=None):
    """Orbit the camera about `pivot` for a mouse move of (dx, dy) pixels.

    `position` and `pivot` are world points, `q` the camera's orientation. Returns the new
    (position, orientation). The orientation turns as in `turn`; the position swings round
    the pivot by the same rotation, so the pivot keeps its place in the camera's eyes (the
    same pixel on screen, the same depth). With the pivot at the point the camera looks at,
    this is exactly FreeCAD's own orbit."""
    deg_x = viewcube.ORBIT_DEG_PER_PIXEL if deg_x is None else deg_x
    deg_y = deg_x if deg_y is None else deg_y
    q = viewcube.q_unit(q)
    new_q = turn(q, dx, dy, mode, deg_x, deg_y)
    # The rotation that was applied: new_q = R * q.
    applied = viewcube.q_mul(new_q, viewcube.q_conj(q))
    arm = viewcube.add(position, viewcube.scale(pivot, -1.0))
    new_position = viewcube.add(pivot, viewcube.rotate(applied, arm))
    return new_position, new_q


def in_camera(position, q, point):
    """A world point as the camera sees it (x right, y up, z towards the viewer): what
    `orbit_camera` keeps unchanged for the pivot."""
    offset = viewcube.add(point, viewcube.scale(position, -1.0))
    return viewcube.rotate(viewcube.q_conj(viewcube.q_unit(q)), offset)


def focal_point(position, q, focal_distance):
    """The point the camera looks at: FreeCAD's orbit centre when no pivot is set."""
    _, _, view = viewcube.camera_axes(q)
    return viewcube.add(position, viewcube.scale(view, focal_distance))
