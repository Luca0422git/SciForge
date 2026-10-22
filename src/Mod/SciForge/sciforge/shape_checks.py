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


_FACE_BOXES = []  # [(key, shape, [(face, its bounding box)])], newest last
_KEEP_FACES = 4


def face_boxes(shape):
    """[(face, face.BoundBox)] of every face of `shape`, remembered for the last few shapes
    (the extrude dialog asks on every preview whether the extrusion lies on a face of each
    body: listing a plate of 1700 faces with their boxes took 0.12 s each time). The list
    and its boxes are shared: callers only read them."""
    try:
        key = _key(shape)
    except Exception:
        return [(f, f.BoundBox) for f in shape.Faces]
    for k, kept, boxes in _FACE_BOXES:
        if k == key and kept.isSame(shape):
            return boxes
    boxes = [(f, f.BoundBox) for f in shape.Faces]
    _FACE_BOXES.append((key, shape, boxes))
    del _FACE_BOXES[:-_KEEP_FACES]
    return boxes
