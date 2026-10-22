# SPDX-License-Identifier: LGPL-2.1-or-later
"""What the documentation for AI models promises about a tool, checked in real FreeCAD by
SciForgeTests/headless/docs_runner.py (run_promises): the review of 2026-10-22 found calls
that did something else than their reference page said (docs/sciforge/sessions/
2026-10-22-fix-aidocs.md). Each promise is a session of calls in the format of the
documents' "sciforge-calls" blocks: {"tool", "args", "expect"} (expect: "contains",
"not_contains", "json" paths with tolerances, "error"). Plain Python data.
"""

PLATE = [
    {"tool": "new_design", "args": {"name": "Promise"}},
    {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]}},
    {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 20}},
    {
        "tool": "create_sketch",
        "args": {"plane": "XY", "offset": 20, "geometry": [{"circle": [15, 20, 1]}]},
    },
]
HOLE_9 = {"tool": "query_geometry", "args": {"select": {"type": "cylinder", "radius": 4.5}}}
UNDO = {"tool": "undo", "args": {}, "expect": {"contains": ["48000 mm3"]}}

PROMISES = {
    # hole.md: size "nominal size, e.g. 8 (M8...)": an M8 normal clearance hole is 9 mm (it
    # was the default M6's 6.6 mm whatever size said)
    "hole size picks its designation": PLATE
    + [
        {
            "tool": "hole",
            "args": {"sketch": "Sketch2", "tap_type": "clearance", "size": "8", "extent": "all"},
        },
        dict(HOLE_9, expect={"json": {"count": 1}}),
        UNDO,
        {
            "tool": "hole",
            "args": {"sketch": "Sketch2", "tap_type": "clearance", "size": "M8", "extent": "all"},
        },
        dict(HOLE_9, expect={"json": {"count": 1}}),
        UNDO,
        {
            "tool": "hole",
            "args": {"sketch": "Sketch2", "tap_type": "clearance", "size": "99", "extent": "all"},
            "expect": {"error": True, "contains": ["unknown size '99'"]},
        },
        {
            "tool": "hole",
            "args": {
                "sketch": "Sketch2",
                "tap_type": "clearance",
                "designation": "M8x1.25",
                "extent": "all",
            },
        },
        dict(HOLE_9, expect={"json": {"count": 1}}),
        UNDO,
    ],
    # hole.md: drill_point defaults to flat, also with the dialog's options; "Give depth or
    # through_all", also for a tapped hole
    "hole defaults": PLATE
    + [
        {
            "tool": "hole",
            "args": {
                "sketch": "Sketch2",
                "diameter": 6,
                "depth": 8,
                "hole_type": "counterbore",
                "cbore_diameter": 11,
                "cbore_depth": 3,
            },
        },
        {
            "tool": "query_geometry",
            "args": {"select": {"type": "cone"}},
            "expect": {"json": {"count": 0}},
        },
        UNDO,
        {
            "tool": "hole",
            "args": {"sketch": "Sketch2", "tap_type": "tapped", "designation": "M8x1.25"},
            "expect": {"error": True, "contains": ["give depth"]},
        },
    ],
    # circular_pattern.md: quantity 3 when left out (the dialog's, Fusion's);
    # rectangular_pattern.md: distance 20
    "pattern defaults": PLATE
    + [
        {
            "tool": "create_sketch",
            "args": {"plane": "XY", "offset": 20, "geometry": [{"circle": [45, 20, 3]}]},
        },
        {"tool": "extrude", "args": {"profile": "Sketch3", "distance": 5}},
        {"tool": "circular_pattern", "args": {"features": ["Extrude2"], "axis": "Z"}},
        {
            "tool": "get_step",
            "args": {"step": "Pattern1"},
            "expect": {"json": {"definition.options.quantity": 3}},
        },
        {"tool": "undo", "args": {}},
        {"tool": "rectangular_pattern", "args": {"features": ["Extrude2"], "direction": "Y"}},
        {
            "tool": "get_step",
            "args": {"step": "Pattern1"},
            "expect": {
                "json": {"definition.options.quantity": 2, "definition.options.distance": 20.0}
            },
        },
    ],
    # docs_search / docs_read: what the reference pages and README link to can be read
    "documentation links": [
        {
            "tool": "docs_read",
            "args": {"path": "sciforge://tools/query_geometry"},
            "expect": {"contains": ["reference/query_geometry.md"]},
        },
        {
            "tool": "docs_search",
            "args": {"query": "fillet", "scope": "nowhere"},
            "expect": {"error": True, "contains": ["is not a folder or document"]},
        },
    ],
}
