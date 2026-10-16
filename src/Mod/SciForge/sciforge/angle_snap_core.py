# SPDX-License-Identifier: LGPL-2.1-or-later
"""Angle snapping for the turn handles (no FreeCAD, no Qt: unit-tested).

Luca chose: while an angle handle is dragged, the angle snaps to 0, 45, 90, 135, 180...
(always on), holding Ctrl moves it freely, and a protractor wheel shows where it snaps and
the angle it is at (protractor.ProtractorRing). Fusion has neither a fixed 45/90 snap nor a
wheel (its rotation increments depend on the zoom): this goes beyond Fusion.

- The snap pulls the angle onto the nearest multiple of 45 degrees when the hand is within
  a few pixels of it along the ring on the screen, so the pull feels the same however big
  the ring is drawn: `tolerance_degrees(ring_pixels)`.
- Ctrl held: the raw angle (no snap, no steps).
- Incremental Move on (navigation bar): the angle goes in steps of the increment, as
  before; a step that lands on a multiple of 45 lights its tick too.
"""

import math

SNAP_EVERY = 45.0  # degrees between snap angles
TICK_EVERY = 15.0  # degrees between the wheel's ticks
SNAP_PIXELS = 6.0  # the pull reaches this far along the ring on the screen
MIN_TOLERANCE = 1.0  # degrees, a ring drawn very big
MAX_TOLERANCE = 4.0  # degrees, a ring drawn very small


def tolerance_degrees(ring_pixels):
    """How many degrees from a snap angle the pull reaches, for a ring `ring_pixels` in
    radius on the screen (SNAP_PIXELS of arc, between MIN and MAX_TOLERANCE)."""
    try:
        ring = float(ring_pixels)
    except (TypeError, ValueError):
        return MAX_TOLERANCE
    if not ring > 0.0:
        return MAX_TOLERANCE
    reach = math.degrees(SNAP_PIXELS / ring)
    return max(MIN_TOLERANCE, min(MAX_TOLERANCE, reach))


def on_snap(angle, every=SNAP_EVERY, slack=1e-6):
    """The snap angle `angle` lies on (a multiple of `every`), or None."""
    nearest = round(float(angle) / every) * every
    return nearest if abs(float(angle) - nearest) <= slack else None


def snap(angle, tolerance=MAX_TOLERANCE, free=False, step=None, every=SNAP_EVERY):
    """(angle to use, snap angle it sits on or None).

    free: Ctrl is held, the raw angle. step: Incremental Move's increment (degrees) when
    that mode is on: the angle in those steps. Else the nearest multiple of `every` when
    it is within `tolerance` degrees."""
    value = float(angle)
    if free:
        return value, on_snap(value, every)
    if step is not None and step > 0.0:
        value = round(value / step) * step
        return value, on_snap(value, every)
    nearest = round(value / every) * every
    if abs(value - nearest) <= tolerance:
        return nearest, nearest
    return value, None


def ticks(every=TICK_EVERY, long_every=SNAP_EVERY):
    """[(degrees, long)] round the wheel: a tick every 15 degrees, the 45 / 90 ones long."""
    count = int(round(360.0 / every))
    found = []
    for i in range(count):
        degrees = i * every
        found.append((degrees, on_snap(degrees, long_every) is not None))
    return found


def text(angle):
    """The angle as the wheel shows it: one decimal, "deg"."""
    value = float(angle)
    if abs(value) < 0.05:
        value = 0.0
    return "%.1f deg" % value
