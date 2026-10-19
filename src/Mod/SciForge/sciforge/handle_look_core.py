# SPDX-License-Identifier: LGPL-2.1-or-later
"""How SciForge's drag handles look and how big they are (plain data and maths, no FreeCAD).

Luca: "SciForge has some janky looking arrows and sometimes they are oversized and sometimes
they are tiny. It should be a consistent size. same thing for the angle dragger". Fusion's
handles keep one size on the screen whatever the part is and however far you zoom:

  - the distance arrow: a small solid blue arrow, a short shaft and a wide head, a thin
    light outline, about 32 px from its foot to its tip;
  - the angle handle: a small white disc (about 19 px) with a dark dot in the middle, on a
    thin light arc;
  - both turn a lighter colour under the mouse and while dragged.

So every handle is drawn in pixels: its shapes are built here in pixel units and FreeCAD's
SoShapeScale scales them every frame so one unit is one pixel on the screen (handle_look.py
builds the Coin nodes). The handle's own maths (where it can be grabbed, where its value box
goes, where the tests aim) uses the same pixel sizes times the millimetres one pixel covers
at the handle (mm_per_px), so what is drawn and what is grabbed always agree.

Sizes are Guesses from Luca's picture of Fusion's Extrude (the arrow ~30-35 px tall, the
disc ~18-20 px); the unit tests (test_handle_look_core) keep the proportions.
"""

import math

# -- the distance arrow (pixels) ------------------------------------------------------------
ARROW_PX = 32.0  # foot to tip
HEAD_PX = 13.0  # the head (a cone) at the tip end
HEAD_RADIUS_PX = 7.5  # the head is 15 px wide
SHAFT_RADIUS_PX = 2.25  # the shaft is 4.5 px wide
OUTLINE_PX = 1.5  # the light outline round the arrow and the disc
GRAB_SLACK_PX = 4.0  # a press this far off the drawn handle still takes it
# Where a person aims at an arrow (a share of its length from the foot): on the head.
HEAD_AIM = 0.75

# -- the angle handle (pixels) --------------------------------------------------------------
DISC_RADIUS_PX = 9.5  # a 19 px disc
DOT_RADIUS_PX = 3.0  # the dark dot in its middle
ARC_REACH_PX = 30.0  # the thin arc a disc rides on runs this far on each side of it
ARC_WIDTH_PX = 1.5

# -- a ball handle (a point slid along a path) ----------------------------------------------
BALL_RADIUS_PX = 7.0

# -- Move's manipulator (pixels from its centre) --------------------------------------------
TRIAD_PX = 96.0  # centre to an arrow's tip
TRIAD_GAP = 0.15  # the arrows start this share of TRIAD_PX out (the middle stays clear)
TRIAD_RING = 0.6  # the turn handles' arcs run at this share of TRIAD_PX
TRIAD_RING_WIDTH_PX = 3.0

# -- colours (RGB 0..1) ---------------------------------------------------------------------
BLUE = (0.16, 0.50, 0.93)  # the arrow (Fusion's manipulator blue)
BLUE_HOT = (0.48, 0.76, 1.0)  # under the mouse / dragged
OUTLINE = (0.93, 0.96, 1.0)  # the thin light outline
DISC = (0.97, 0.97, 0.97)  # the angle disc
DISC_HOT = (0.74, 0.87, 1.0)
DOT = (0.16, 0.18, 0.22)
DISC_OUTLINE = (0.36, 0.40, 0.46)  # a disc's rim (white on a light part needs an edge)
ARC = (0.82, 0.86, 0.92)  # the thin light arc / line
AXIS_COLOURS = ((0.90, 0.28, 0.28), (0.35, 0.78, 0.35), (0.30, 0.52, 0.98))  # Move: X Y Z
AXIS_HOT = (1.0, 0.85, 0.35)


def length_mm(mm_per_px, pixels=ARROW_PX):
    """`pixels` on the screen in millimetres at a point where one pixel is `mm_per_px` mm."""
    return max(float(mm_per_px), 1e-9) * float(pixels)


def hot_colour(colour, hot, hot_colour=None):
    """The colour to paint a handle: lighter under the mouse or while dragged."""
    if not hot:
        return tuple(colour)
    if hot_colour is not None:
        return tuple(hot_colour)
    return tuple(min(1.0, c + (1.0 - c) * 0.55) for c in colour)


def shaded(colour):
    """(diffuse, emissive) of a lit handle: a little 3D shading, never dark."""
    diffuse = tuple(c * 0.75 for c in colour)
    emissive = tuple(c * 0.40 for c in colour)
    return diffuse, emissive


def arrow_parts(length=ARROW_PX, head=HEAD_PX, head_radius=HEAD_RADIUS_PX,
                shaft_radius=SHAFT_RADIUS_PX, start=0.0):
    """The arrow along +Y in pixels, as Coin's cylinder and cone want them (centred on
    their axis): {"shaft": (centre_y, height, radius), "head": (centre_y, height, radius)}.
    `start` moves the foot out (Move's arrows start off the centre)."""
    shaft_height = max(float(length) - float(start) - float(head), 0.5)
    return {
        "shaft": (start + shaft_height / 2.0, shaft_height, shaft_radius),
        "head": (length - head / 2.0, float(head), head_radius),
    }


def outline_parts(parts, outline=OUTLINE_PX):
    """The same parts grown by `outline` all round (drawn behind the arrow: its rim)."""
    grown = {}
    for name, (centre, height, radius) in parts.items():
        grown[name] = (centre, height + 2.0 * outline, radius + outline)
    return grown


def half_width_px(kind="arrow"):
    """Half the drawn width of a handle (pixels): where it can be grabbed sideways."""
    return {"arrow": HEAD_RADIUS_PX, "disc": DISC_RADIUS_PX, "ball": BALL_RADIUS_PX}.get(
        kind, HEAD_RADIUS_PX
    ) + OUTLINE_PX


def grab_px(kind="arrow", at_least=0.0):
    """How far from a handle's line (or a disc's / ball's centre) a press still takes it:
    the drawn half width plus a few pixels of slack, never less than `at_least`."""
    return max(half_width_px(kind) + GRAB_SLACK_PX, float(at_least))


def segment_distance(p, a, b):
    """Distance (pixels) from the point p to the segment a-b (all (x, y))."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def grab_parts(length=ARROW_PX, head=HEAD_PX, start=0.0, slack=GRAB_SLACK_PX):
    """Where an arrow along +Y (pixels, as arrow_parts) can be grabbed, as Coin cylinders
    {"shaft": (centre_y, height, radius), "head": ...}: the drawn shapes with their outline
    and `slack` pixels round them, the head's zone running `slack` past the tip. Nothing
    behind the foot and only a slim zone round the shaft: the foot stands on what the
    value is measured from (a profile's middle, a pattern's copy, a face), and a press
    there must still reach that (a click on a profile, on a copy's dot), not the arrow."""
    shaft_top = max(float(length) - float(head), float(start))
    shaft_height = max(shaft_top - float(start), 0.5)
    head_height = float(length) - shaft_top + float(slack)
    return {
        "shaft": (start + shaft_height / 2.0, shaft_height, SHAFT_RADIUS_PX + OUTLINE_PX + slack),
        "head": (shaft_top + head_height / 2.0, head_height, HEAD_RADIUS_PX + OUTLINE_PX + slack),
    }


def on_arrow(p, foot, tip, slack=GRAB_SLACK_PX):
    """True when the screen point p is on the arrow drawn from `foot` to `tip` (pixels),
    with `slack` pixels to spare: the zones of grab_parts (slim round the shaft, wide round
    the head, nothing behind the foot)."""
    fx, fy = foot
    dx, dy = tip[0] - fx, tip[1] - fy
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return math.hypot(p[0] - fx, p[1] - fy) <= HEAD_RADIUS_PX + OUTLINE_PX + slack
    ux, uy = dx / length, dy / length
    along = (p[0] - fx) * ux + (p[1] - fy) * uy  # pixels from the foot towards the tip
    across = abs((p[0] - fx) * uy - (p[1] - fy) * ux)
    if along < 0.0 or along > length + slack:
        return False
    if along >= length * (1.0 - HEAD_PX / ARROW_PX):  # on the head
        return across <= HEAD_RADIUS_PX + OUTLINE_PX + slack
    return across <= SHAFT_RADIUS_PX + OUTLINE_PX + slack


def arc_span(radius_mm, mm_per_px, reach_px=ARC_REACH_PX):
    """Half the angle (degrees) of the thin arc a disc rides on: `reach_px` pixels of arc
    on each side of it at `radius_mm` from its centre, at most a half turn."""
    radius = max(float(radius_mm), 1e-9)
    return min(180.0, math.degrees(length_mm(mm_per_px, reach_px) / radius))


def sign(value):
    """+1 or -1: the way an arrow at `value` points (along its line, or back for a minus)."""
    return -1.0 if float(value) < 0 else 1.0
