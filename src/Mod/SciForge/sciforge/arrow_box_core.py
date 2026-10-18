# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the value box next to a drag arrow goes on the screen (pure geometry, no Qt).

Fusion shows a distance box beside the arrow you drag. The box must never cover the
arrow's heads: they are what you grab. An arrow can point any way on the screen (in the
Front view the arrow of a side face points sideways), so the box goes, in this order:

  1. beside the arrow's middle, on its right (above it when the arrow lies level),
     clear of the heads;
  2. beside it on the other side (when the edge of the view is in the way);
  3. past the arrow's tip, then past its tail;

and it always stays inside the view. Pixels: x to the right, y down (as in Qt).
taskui.ArrowValueBox uses spot(); the unit tests check it without FreeCAD.
"""

import math

# Coin's own SoTranslate1Dragger arrow (a head at both ends), measured in "arrow sizes"
# (the size is a length in mm) from its middle: a thin bar to 1.0 on both sides, then a
# cone head from 1.0 to 1.5, 0.25 wide (radius). SciForge's own arrows no longer look like
# this (they are drawn in pixels, handle_look_core); these two numbers stay for
# ArrowValueBox.place() and handle_size(), which still work in such sizes.
REACH = 1.5  # middle to either tip: the whole arrow is 2 * REACH sizes long
HEAD = 0.25  # half the width of a head (its cone's radius), in sizes
GAP = 6.0  # pixels between the arrow (its heads included) and the box
EDGE = 2.0  # pixels kept free at the view's border
# A drag arrow's size on the screen: Fusion's arrows look the same size whatever the part
# is, about this many pixels for one arrow size (the whole arrow is 2 * REACH sizes long:
# about 75 px). Extrude's arrows come out near this after Fit.
ARROW_PIXELS = 25.0
MIN_SIZE = 0.35  # mm: the whole arrow is at least about 1 mm long


def handle_size(mm_per_pixel, pixels=ARROW_PIXELS, lo=MIN_SIZE, hi=None):
    """The size (mm) of a drag arrow that shows `pixels` pixels per size on a screen where
    one pixel is `mm_per_pixel` mm, kept between `lo` and `hi` (mm). `hi` stops the arrow
    from dwarfing a short picked edge (about half its length for the whole arrow: pass its
    length / (4 * REACH)); `lo` keeps it visible on a tiny part."""
    size = max(float(mm_per_pixel), 0.0) * float(pixels)
    if hi is not None:
        size = min(size, max(float(hi), 1e-6))
    return max(size, float(lo))


def _segment_point(a, b, p):
    """Distance from point p to the segment a-b."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _rect_point(rect, p):
    """Distance from point p to the rectangle (left, top, width, height); 0 inside."""
    left, top, width, height = rect
    dx = max(left - p[0], 0.0, p[0] - (left + width))
    dy = max(top - p[1], 0.0, p[1] - (top + height))
    return math.hypot(dx, dy)


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_cross(p1, p2, q1, q2):
    d1, d2 = _cross(q1, q2, p1), _cross(q1, q2, p2)
    d3, d4 = _cross(p1, p2, q1), _cross(p1, p2, q2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def rect_gap(a, b):
    """Distance between two rectangles (left, top, width, height): 0 when they touch, less
    than 0 (minus how deep) when they overlap."""
    dx = max(a[0] - (b[0] + b[2]), b[0] - (a[0] + a[2]))
    dy = max(a[1] - (b[1] + b[3]), b[1] - (a[1] + a[3]))
    if dx < 0 and dy < 0:
        return max(dx, dy)  # overlapping: the smaller overlap, as a negative number
    return math.hypot(max(dx, 0.0), max(dy, 0.0))


def clearance(tail, tip, rect):
    """Distance between the segment tail-tip and the rectangle (left, top, width, height):
    0 when they touch or overlap."""
    if _rect_point(rect, tail) == 0.0 or _rect_point(rect, tip) == 0.0:
        return 0.0
    left, top, width, height = rect
    corners = [(left, top), (left + width, top), (left + width, top + height), (left, top + height)]
    for i in range(4):
        if _segments_cross(tail, tip, corners[i], corners[(i + 1) % 4]):
            return 0.0
    return min(
        [_rect_point(rect, tail), _rect_point(rect, tip)]
        + [_segment_point(tail, tip, c) for c in corners]
    )


def spot(
    anchor,
    tail,
    tip,
    radius,
    box,
    view,
    gap=GAP,
    other_side=False,
    past_tip=False,
    avoid=(),
    avoid_rects=(),
):
    """Top-left corner (x, y) of a box of size `box` (w, h) beside an arrow on the screen.

    anchor     the arrow's middle (where the extrusion ends), in view pixels
    tail, tip  the arrow's two ends (the tips of its heads)
    radius     how far the heads reach sideways from the arrow's line, in pixels
    view       the size (w, h) of the 3D view the box sits in
    other_side the box starts on the arrow's other side (left, or below a level arrow):
               for a second arrow that can sit on the first one (both at 0), so the two
               boxes do not cover each other
    past_tip   the box starts past the arrow's tip (a third arrow on the same spot)
    avoid      the dialog's other handles, [(tail, tip, radius)] in pixels: the box covers
               none of them either (a pattern's two arrows meet at a corner)
    avoid_rects the dialog's other boxes, [(left, top, width, height)]: never covered
    The box keeps `gap` pixels plus `radius` away from the arrow's line, never covers a
    head (its own or another handle's) or another box, and stays inside the view. When
    every spot beside the arrow is taken (two arrows on one spot with a third handle next
    to them), the same directions are tried further out; only when nothing fits at all
    does it go where it covers the least."""
    ax, ay = float(anchor[0]), float(anchor[1])
    tail = (float(tail[0]), float(tail[1]))
    tip = (float(tip[0]), float(tip[1]))
    width, height = float(box[0]), float(box[1])
    view_w, view_h = float(view[0]), float(view[1])
    dx, dy = tip[0] - tail[0], tip[1] - tail[1]
    length = math.hypot(dx, dy)
    if length < 1.0:
        dx, dy = 0.0, -1.0  # the arrow points at you (or away): as if it stood upright
    else:
        dx, dy = dx / length, dy / length
    # The two sides of the arrow: its right first, or above it when it lies level.
    sides = sorted([(-dy, dx), (dy, -dx)], key=lambda n: -(n[0] - 0.5 * n[1]))
    if other_side:
        sides.reverse()
    # (direction, where it starts, how far the box's centre goes along it)
    ways = []
    for nx, ny in sides:
        reach = radius + gap + (abs(nx) * width + abs(ny) * height) / 2.0
        ways.append(((nx, ny), (ax, ay), reach))
    along = radius + gap + (abs(dx) * width + abs(dy) * height) / 2.0
    ways.append(((dx, dy), tip, along))
    ways.append(((-dx, -dy), tail, along))
    if past_tip:
        ways = ways[2:] + ways[:2]
    step = 0.6 * max(width, height)  # further out when the spots beside the arrow are taken
    spots = []
    for k in range(4):
        for (nx, ny), (ox, oy), reach in ways:
            cx, cy = ox + nx * (reach + k * step), oy + ny * (reach + k * step)
            left = max(EDGE, min(cx - width / 2.0, view_w - width - EDGE))
            top = max(EDGE, min(cy - height / 2.0, view_h - height - EDGE))
            rect = (left, top, width, height)
            handles = clearance(tail, tip, rect) - radius
            for other_tail, other_tip, other_radius in avoid:
                handles = min(handles, clearance(other_tail, other_tip, rect) - float(other_radius))
            boxes = min((rect_gap(rect, other) for other in avoid_rects), default=1e9)
            if min(handles, boxes) >= 1.0:
                return int(round(left)), int(round(top))
            spots.append((handles, boxes, k, left, top))
    # Nothing fits at all: a box over another box costs less than a box over a handle (the
    # handle can no longer be grabbed there: CI #145-#149, Insert Canvas's crowded handles
    # with wider fonts). The nearest spot clear of every handle, else the least covering.
    free = [s for s in spots if s[0] >= 1.0]
    if free:
        best = max(free, key=lambda s: (s[1], -s[2]))
    else:
        best = max(spots, key=lambda s: (s[0], -s[2]))
    return int(round(best[3])), int(round(best[4]))
