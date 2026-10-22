# SPDX-License-Identifier: LGPL-2.1-or-later
"""The parts the Draft speed scenario (scenarios/perf_draft.py) drags the angle on, as golden
model steps (SciForgeTests/golden/builder.py builds them, headless or in the GUI):

  BOX      the simple box: 40 x 30 x 10 from the origin
  PART     a realistic part (Luca's kind): a 100 x 60 x 30 block with rounded vertical
           corners (r 6), 12 holes with chamfered rims, a 40 x 24 pocket 12 deep with
           rounded corners, 12 pins with rounded tops on the pocket floor, two round bosses
           on top, 16 small recesses in the top and 32 in the bottom: ~190 faces
"""

BOX = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10},
]

HOLES = [(x, y) for x in (10, 30, 70, 90) for y in (8, 52)] + [
    (10, 30),
    (90, 30),
    (50, 8),
    (50, 52),
]
PINS = [(x, y) for x in (36, 44, 56, 64) for y in (23, 30, 37)]
TOP_RECESSES = [(x, y) for x in range(15, 90, 10) for y in (15, 45)]
BOTTOM_RECESSES = [(x, y) for x in range(15, 90, 10) for y in (16, 24, 36, 44)]

PART = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 100, 60]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 30},
    {
        "op": "fillet",
        "id": "f1",
        "edges": {"type": "line", "parallel": [0, 0, 1], "count": 4},
        "radius": 6,
    },
    {
        "op": "sketch",
        "id": "s2",
        "plane": "XY",
        "offset": 30,
        "geometry": [{"circle": [x, y, 3]} for x, y in HOLES],
    },
    {
        "op": "extrude",
        "id": "e2",
        "profile": "s2",
        "distance": 30,
        "flip": True,
        "operation": "cut",
    },
    {
        "op": "chamfer",
        "id": "c1",
        "edges": {"type": "circle", "radius": 3, "at": {"axis": "z", "value": "max"}, "count": 12},
        "distance": 0.8,
    },
    {
        "op": "sketch",
        "id": "s3",
        "plane": "XY",
        "offset": 30,
        "geometry": [{"rect": [30, 18, 70, 42]}],
    },
    {
        "op": "extrude",
        "id": "e3",
        "profile": "s3",
        "distance": 12,
        "flip": True,
        "operation": "cut",
    },
    {
        "op": "fillet",
        "id": "f2",
        "edges": {
            "type": "line",
            "parallel": [0, 0, 1],
            "at": {"axis": "z", "value": 24},
            "count": 4,
        },
        "radius": 3,
    },
    {
        "op": "sketch",
        "id": "s4",
        "plane": "XY",
        "offset": 18,
        "geometry": [{"circle": [x, y, 1.5]} for x, y in PINS],
    },
    {"op": "extrude", "id": "e4", "profile": "s4", "distance": 6},
    {
        "op": "sketch",
        "id": "s5",
        "plane": "XY",
        "offset": 30,
        "geometry": [{"circle": [20, 30, 5]}, {"circle": [80, 30, 5]}],
    },
    {"op": "extrude", "id": "e5", "profile": "s5", "distance": 8},
    {
        "op": "fillet",
        "id": "f3",
        "edges": {"type": "circle", "radius": 1.5, "at": {"axis": "z", "value": 24}, "count": 12},
        "radius": 0.4,
    },
    {
        "op": "sketch",
        "id": "s6",
        "plane": "XY",
        "offset": 30,
        "geometry": [{"circle": [x, y, 1.2]} for x, y in TOP_RECESSES],
    },
    {"op": "extrude", "id": "e6", "profile": "s6", "distance": 3, "flip": True, "operation": "cut"},
    {
        "op": "sketch",
        "id": "s7",
        "plane": "XY",
        "geometry": [{"circle": [x, y, 1.5]} for x, y in BOTTOM_RECESSES],
    },
    {"op": "extrude", "id": "e7", "profile": "s7", "distance": 3, "operation": "cut"},
]


def build(doc, steps):
    """Build `steps` in `doc` (golden builder); returns the builder."""
    from SciForgeTests.golden.builder import Builder

    builder = Builder(doc)
    for step in steps:
        builder.run(step)
    doc.recompute()
    return builder


def outer_sides(shape):
    """Face names of the block's outer side walls (4 flat sides and the 4 rounded corners):
    the faces Luca drafts on such a part."""
    names = []
    box = shape.BoundBox
    for i, face in enumerate(shape.Faces, start=1):
        fb = face.BoundBox
        if fb.ZLength < 29.0:
            continue
        on_side = (
            abs(fb.XMin - box.XMin) < 1e-6
            or abs(fb.XMax - box.XMax) < 1e-6
            or abs(fb.YMin - box.YMin) < 1e-6
            or abs(fb.YMax - box.YMax) < 1e-6
        )
        if on_side:
            names.append("Face%d" % i)
    return names


def pocket_walls(shape):
    """Face names of the pocket's side walls (4 flat walls, 4 rounded corners)."""
    names = []
    for i, face in enumerate(shape.Faces, start=1):
        fb = face.BoundBox
        if (
            fb.XMin > 29.0
            and fb.XMax < 71.0
            and fb.YMin > 17.0
            and fb.YMax < 43.0
            and abs(fb.ZMax - 30.0) < 1e-6
            and abs(fb.ZMin - 18.0) < 1e-6
        ):
            names.append("Face%d" % i)
    return names
