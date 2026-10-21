# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks of a shape that several parts of a dialog ask for, done once per shape.

A preview asked `shape.isValid()` up to three times for the same result (is the step sound,
the status line, OK): 12-15 ms each on a filleted part. The answer is kept for the last few
shapes, keyed by the shape's identity (its hashCode and type); the shape itself is kept
with it so the key cannot be reused by another shape meanwhile.
"""

_VALID = []  # [(key, shape, valid)], newest last
_KEEP = 8


def _key(shape):
    return (shape.hashCode(), shape.ShapeType)


def is_valid(shape):
    """shape.isValid(), remembered for the last few shapes."""
    try:
        key = _key(shape)
    except Exception:
        return shape.isValid()
    for k, kept, valid in _VALID:
        if k == key and kept.isSame(shape):
            return valid
    valid = shape.isValid()
    _VALID.append((key, shape, valid))
    del _VALID[:-_KEEP]
    return valid
