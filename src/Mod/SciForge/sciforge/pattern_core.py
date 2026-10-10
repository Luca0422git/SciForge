# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the copies of Fusion's Rectangular and Circular Pattern go: pure Python (no
FreeCAD), unit tested (SciForgeTests/unit/test_pattern_core.py).

Fusion's fields, per direction of a rectangular pattern:
  Quantity        how many instances, the original included (1 = only the original)
  Distance        Extent: from the original to the last instance;
                  Spacing: from one instance to the next.
                  A negative distance goes the other way.
  Direction Type  One Direction: the instances go one way from the original;
                  Symmetric: the same instances on the other side of it too (the original
                  is shared, so a quantity of 3 gives 5 instances in a row).
Circular pattern:
  Full       Quantity instances evenly around the whole circle
  Angle      Quantity instances from the original to Total Angle (360 = Full)
  Symmetric  the Angle pattern on both sides of the original
"""

SENTINEL = -1.0  # FreeCAD's pattern features read a spacing of exactly -1 as "use Offset"
NUDGE = 1e-9  # mm or degrees: far below the kernel's tolerance (1e-7 mm)


class PatternError(ValueError):
    """A value Fusion's dialog would refuse; the text says what to change."""


def step_of(quantity, distance, distribution):
    """Distance between neighbouring instances along one direction (signed)."""
    quantity = int(quantity)
    if quantity <= 1:
        return 0.0
    if distribution == "spacing":
        return float(distance)
    return float(distance) / (quantity - 1)


def linear_offsets(quantity, distance, distribution="extent", direction_type="one"):
    """Signed offsets of the instances from the original, the original (0) first."""
    quantity = int(quantity)
    if quantity < 1:
        raise PatternError("The quantity must be at least 1.")
    step = step_of(quantity, distance, distribution)
    offsets = [step * k for k in range(quantity)]
    if direction_type == "symmetric":
        offsets += [-step * k for k in range(quantity - 1, 0, -1)]
    return offsets


def circular_angles(quantity, angle=360.0, kind="full"):
    """Angles (degrees) of the instances, the original (0) first."""
    quantity = int(quantity)
    if quantity < 1:
        raise PatternError("The quantity must be at least 1.")
    if quantity == 1:
        return [0.0]
    if kind == "full" or (kind == "angle" and abs(abs(float(angle)) - 360.0) < 1e-9):
        step = 360.0 / quantity
        if kind == "angle" and float(angle) < 0:
            step = -step
    else:
        if abs(float(angle)) < 1e-9:
            raise PatternError("The total angle must not be 0.")
        step = float(angle) / (quantity - 1)
    angles = [step * k for k in range(quantity)]
    if kind == "symmetric":
        angles += [-step * k for k in range(quantity - 1, 0, -1)]
    return angles


def walk(offsets):
    """The gaps FreeCAD's pattern features take ("Spacings": each instance is that far from
    the one before) to put instances at `offsets` (which start with the original, 0)."""
    return [b - a for a, b in zip(offsets, offsets[1:])]


def safe_walk(gaps):
    """`gaps` with any gap of exactly -1 moved by a nanometre: FreeCAD reads -1 as "use the
    Offset value"."""
    return [g - NUDGE if g == SENTINEL else g for g in gaps]


def symmetric_walk_terms(quantity):
    """Multipliers of the step for the symmetric walk 0, s, 2s, .. (n-1)s, -(n-1)s, .. -s."""
    quantity = int(quantity)
    if quantity <= 1:
        return []
    return [1] * (quantity - 1) + [-(2 * quantity - 2)] + [1] * (quantity - 2)


def instance_count(quantity, direction_type="one"):
    quantity = max(1, int(quantity))
    return 2 * quantity - 1 if direction_type == "symmetric" else quantity


def grid(offsets1, offsets2):
    """Every combination of the two directions' offsets, the original (0, 0) first."""
    return [(a, b) for a in offsets1 for b in offsets2]


def default_distance(size, quantity=2):
    """Fusion starts a pattern with copies that do not overlap the original: a little more
    than the object's size per instance (rounded to a whole millimetre)."""
    size = max(float(size), 1.0)
    per = float(int(size * 1.5 + 0.999))
    return per * max(1, int(quantity) - 1)
