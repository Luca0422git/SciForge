# SPDX-License-Identifier: LGPL-2.1-or-later
"""The complete example of every AI tool shown on its reference page (docs/ai/reference/<tool>.md,
written by sciforge/ai/tool_docs.py): the calls that make the design it starts from (a
setup), the call itself, and the real answer, recorded in real FreeCAD by
SciForgeTests/headless/docs_runner.py into tool_results.json.

    SCIFORGE_DOCS_RECORD=1 freecadcmd -c "from SciForgeTests.headless import docs_runner; docs_runner.main()"

records the answers again (then run tools/sciforge/make_ai_docs.py); without
SCIFORGE_DOCS_RECORD the runner checks that every answer is still what the page shows.
"{tmp}" in a path is a fresh temporary folder (shown as /home/me/sciforge on the pages).
An example with "gui": True needs the SciForge window and is recorded by the GUI scenario
ai_docs_gui. Plain Python data.
"""

TOP = {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}
TOP4 = {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}
VERTICAL4 = {"type": "line", "parallel": [0, 0, 1], "count": 4}
SIDES4 = {"along": [0, 0, 1], "type": "plane", "count": 4}


def call(tool, **args):
    return {"tool": tool, "args": args}


EMPTY = [call("new_design", name="Example")]
PLATE = EMPTY + [
    call("create_sketch", plane="XY", geometry=[{"rect": [0, 0, 60, 40], "name": "base"}]),
    call("extrude", profile="Sketch1", distance=10),
]
PLATE_HOLE = PLATE + [
    call("create_sketch", plane="XY", offset=10, geometry=[{"circle": [30, 20, 4]}]),
    call("hole", sketch="Sketch2", diameter=8, through_all=True),
]
PLATE_BOSS = PLATE + [
    call("create_sketch", plane="XY", offset=10, geometry=[{"circle": [10, 20, 5]}]),
    call("extrude", profile="Sketch2", distance=5),
]
TWO_BODIES = PLATE + [
    call(
        "primitive",
        kind="box",
        plane="XY",
        x=40,
        y=10,
        length=40,
        width=20,
        height=20,
        operation="new_body",
    ),
]
SHAFT = EMPTY + [
    call("primitive", kind="cylinder", plane="XY", diameter=10, height=30),
]
RING = EMPTY + [
    call("create_sketch", plane="XZ", geometry=[{"rect": [10, 0, 20, 10]}]),
]
COMPONENTS = EMPTY + [
    call("new_component", label="Base"),
    call("create_sketch", plane="XY", geometry=[{"rect": [-30, -30, 30, 30]}]),
    call("extrude", profile="Sketch1", distance=10),
    call("new_component", label="Wheel"),
    call("create_sketch", plane="XY", offset=20, geometry=[{"circle": [0, 0, 15]}]),
    call("extrude", profile="Sketch2", distance=5),
]
DRAWING = PLATE_HOLE + [call("create_drawing", base_view="Front", projected=["Top", "Right"])]
SAVED = PLATE + [call("save_as", path="{tmp}/plate.FCStd")]

SETUPS = {
    "none": [],
    "empty": EMPTY,
    "plate": PLATE,
    "plate_hole": PLATE_HOLE,
    "plate_boss": PLATE_BOSS,
    "two_bodies": TWO_BODIES,
    "shaft": SHAFT,
    "ring_sketch": RING,
    "components": COMPONENTS,
    "drawing": DRAWING,
    "saved": SAVED,
    "sketch": EMPTY
    + [call("create_sketch", plane="XY", geometry=[{"rect": [0, 0, 60, 40], "name": "base"}])],
    "sketch_lines": EMPTY
    + [
        call(
            "create_curve_sketch",
            plane="XY",
            curves=[{"line": [0, 0, 40, 2]}, {"line": [40, 2, 40, 30]}],
        )
    ],
    "sweep": EMPTY
    + [
        call("create_sketch", plane="XY", geometry=[{"circle": [0, 0, 3]}]),
        call(
            "create_curve_sketch",
            plane="XZ",
            curves=[{"line": [0, 0, 0, 40]}, {"arc": [20, 40, 20, 90, 180]}],
        ),
    ],
    "loft": EMPTY
    + [
        call("create_sketch", plane="XY", geometry=[{"center_rect": [0, 0, 30, 30]}]),
        call("create_sketch", plane="XY", offset=25, geometry=[{"circle": [0, 0, 10]}]),
    ],
    "tray": EMPTY
    + [
        call("create_sketch", plane="XY", geometry=[{"rect": [0, 0, 60, 40]}]),
        call("extrude", profile="Sketch1", distance=20),
        call("shell", faces=TOP, thickness=2),
        call(
            "create_curve_sketch",
            plane="XY",
            offset=20,
            curves=[{"line": [2, 20, 58, 20]}],
        ),
    ],
    "gusset": EMPTY
    + [
        call(
            "create_sketch",
            plane="XZ",
            geometry=[{"polyline": [[0, 0], [40, 0], [40, 5], [5, 5], [5, 40], [0, 40]]}],
        ),
        call("extrude", profile="Sketch1", distance=20),
        call("create_curve_sketch", plane="XZ", offset=10, curves=[{"line": [5, 25, 25, 5]}]),
    ],
    "label": SHAFT
    + [
        call("create_sketch", plane="XZ", offset=-5, geometry=[{"center_rect": [0, 15, 6, 4]}]),
    ],
    "pipe_path": EMPTY
    + [call("create_curve_sketch", plane="XY", curves=[{"line": [0, 0, 0, 40]}])],
    "path_pattern": PLATE_BOSS
    + [call("create_curve_sketch", plane="XY", offset=10, curves=[{"line": [10, 20, 50, 20]}])],
    "revolved": EMPTY
    + [
        call("create_sketch", plane="XZ", geometry=[{"rect": [0, 0, 10, 20]}]),
        call("revolve", profile="Sketch1", axis="Z"),
    ],
    "two_heights": EMPTY
    + [
        call("primitive", kind="box", plane="XY", length=20, width=20, height=10),
        call(
            "primitive",
            kind="box",
            plane="XY",
            x=30,
            length=20,
            width=20,
            height=15,
            operation="new_body",
        ),
    ],
    "filleted": PLATE + [call("fillet", edges=VERTICAL4, radius=5)],
    "parameter": PLATE + [call("set_parameter", name="gap", value=2, unit="mm")],
    "surface_line": EMPTY
    + [call("create_curve_sketch", plane="XY", curves=[{"line": [0, 0, 30, 0]}])],
    "drawing_saved": PLATE_HOLE
    + [
        call("create_drawing", base_view="Front", projected=["Top", "Right"]),
    ],
    "sphere": EMPTY + [call("primitive", kind="sphere", plane="XY", diameter=20)],
    "two_designs": PLATE + [call("new_design", name="Second")],
    "grouped": PLATE_HOLE + [call("fillet", edges=TOP4, radius=2)],
}

EXAMPLES = [
    # -- inspect --------------------------------------------------------------------------------
    {"tool": "get_design", "setup": "plate", "args": {}, "note": "the plate as JSON"},
    {
        "tool": "screenshot",
        "setup": "plate",
        "args": {"view": "top", "width": 800, "height": 600},
        "note": "a top view, 800 x 600 (needs the SciForge window)",
        "gui": True,
    },
    {
        "tool": "measure",
        "setup": "plate_hole",
        "args": {"a": {"face": TOP}, "b": {"plane": "XY"}},
        "note": "the height of the top face above the XY plane",
    },
    {
        "tool": "measure",
        "setup": "plate_hole",
        "args": {"a": {"face": {"type": "cylinder", "count": 1}}},
        "note": "the size of one pick: the hole's round face",
    },
    {"tool": "physical_properties", "setup": "plate", "args": {}, "note": "volume, area, mass"},
    {"tool": "center_of_mass", "setup": "plate_hole", "args": {}, "note": "the centre of mass"},
    {"tool": "interference", "setup": "two_bodies", "args": {}, "note": "two bodies that overlap"},
    {
        "tool": "section_analysis",
        "setup": "plate_hole",
        "args": {"plane": {"plane": "XZ"}, "distance": 20},
        "note": "a cut through the hole, 20 mm from XZ",
    },
    {"tool": "inspect_design", "setup": "plate_hole", "args": {}, "note": "everything at once"},
    {
        "tool": "query_geometry",
        "setup": "plate_hole",
        "args": {"select": {"type": "cylinder"}},
        "note": "the round faces, with a ref for each",
    },
    {
        "tool": "query_geometry",
        "setup": "plate",
        "args": {"element": "edges", "select": TOP4},
        "note": "the four top edges, each with a ref that picks only it",
    },
    {"tool": "check_design", "setup": "plate_hole", "args": {}, "note": "is the design sound"},
    {
        "tool": "render",
        "setup": "plate_hole",
        "args": {"width": 400, "height": 300, "highlight": {"faces": {"type": "cylinder"}}},
        "note": "an iso picture with the hole marked in orange",
    },
    {
        "tool": "diff_design",
        "setup": "plate_hole",
        "args": {"since": "last_change"},
        "note": "what the hole did",
    },
    # -- sketch ---------------------------------------------------------------------------------
    {
        "tool": "create_sketch",
        "setup": "empty",
        "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]},
        "note": "a 60 x 40 rectangle on XY whose dimensions are named base.width / base.height",
    },
    {
        "tool": "create_sketch",
        "setup": "plate",
        "args": {"face": TOP, "geometry": [{"circle": [30, 20, 5]}]},
        "note": "a circle on the plate's top face",
    },
    {
        "tool": "create_curve_sketch",
        "setup": "empty",
        "args": {
            "plane": "XZ",
            "curves": [{"line": [0, 0, 0, 40]}, {"arc": [20, 40, 20, 90, 180]}],
        },
        "note": "an open path: a line up and a quarter arc (a sweep path)",
    },
    {
        "tool": "add_to_sketch",
        "setup": "sketch",
        "args": {"sketch": "Sketch1", "geometry": [{"circle": [30, 20, 6], "name": "bore"}]},
        "note": "a named circle inside the rectangle",
    },
    {"tool": "get_sketch", "setup": "sketch", "args": {"sketch": "Sketch1"}, "note": "its curves"},
    {
        "tool": "sketch_constraint",
        "setup": "sketch_lines",
        "args": {"sketch": "Sketch1", "kind": "horizontal", "items": [{"curve": 0}]},
        "note": "make the first line horizontal",
    },
    {
        "tool": "sketch_dimension",
        "setup": "sketch_lines",
        "args": {
            "sketch": "Sketch1",
            "kind": "distance",
            "items": [{"curve": 0}],
            "value": 50,
            "name": "len",
        },
        "note": "a 50 mm dimension on the first line, named len",
    },
    {
        "tool": "set_sketch_dimension",
        "setup": "plate",
        "args": {"sketch": "Sketch1", "constraint": "base.width", "value": 80},
        "note": "make the plate 80 mm wide (the extrude follows)",
    },
    {
        "tool": "sketch_delete",
        "setup": "sketch_lines",
        "args": {"sketch": "Sketch1", "curves": [1]},
        "note": "delete the second line",
    },
    {
        "tool": "sketch_polygon",
        "setup": "sketch",
        "args": {
            "sketch": "Sketch1",
            "center": [30, 20],
            "point": [35, 20],
            "sides": 6,
            "diameter": 10,
            "name": "nut",
        },
        "note": "a hexagon 10 mm across the corners",
    },
    {
        "tool": "sketch_trim",
        "setup": "sketch",
        "args": {"sketch": "Sketch1", "points": [[30, 0]]},
        "note": "trim the bottom line of the rectangle",
    },
    {
        "tool": "sketch_text",
        "setup": "sketch",
        "args": {"sketch": "Sketch1", "text": "SF", "height": 8, "corner": [5, 5]},
        "note": "the letters SF, 8 mm high",
    },
    # -- create ---------------------------------------------------------------------------------
    {
        "tool": "extrude",
        "setup": "sketch",
        "args": {"profile": "Sketch1", "distance": 10},
        "note": "a 10 mm plate",
    },
    {
        "tool": "extrude",
        "setup": "plate",
        "args": {"face": TOP, "distance": 5, "taper": 10},
        "note": "pull the top face up 5 mm with a 10 degree taper",
    },
    {
        "tool": "revolve",
        "setup": "ring_sketch",
        "args": {"profile": "Sketch1", "axis": "Z"},
        "note": "a full turn about Z: a ring",
    },
    {
        "tool": "hole",
        "setup": "plate",
        "args": {"face": TOP, "at": [30, 20, 10], "diameter": 6, "depth": 8},
        "note": "a single 6 mm hole, 8 mm deep, on the top face",
    },
    {
        "tool": "hole",
        "setup": "plate",
        "args": {
            "face": TOP,
            "at": [15, 20, 10],
            "diameter": 5.5,
            "through_all": True,
            "counterbore": {"diameter": 10, "depth": 5.5},
        },
        "note": "a counterbored hole for an M5 socket head screw",
    },
    {
        "tool": "pattern",
        "setup": "plate_boss",
        "args": {
            "kind": "rectangular",
            "features": ["Extrude2"],
            "direction": "X",
            "count": 3,
            "spacing": 20,
        },
        "note": "three bosses 20 mm apart",
    },
    {
        "tool": "rectangular_pattern",
        "setup": "plate_boss",
        "args": {
            "features": ["Extrude2"],
            "direction": "X",
            "quantity": 3,
            "distance": 40,
            "distribution": "extent",
        },
        "note": "three bosses spread over 40 mm",
    },
    {
        "tool": "circular_pattern",
        "setup": "plate_boss",
        "args": {"features": ["Extrude2"], "axis": "Z", "quantity": 4},
        "note": "four bosses around the Z axis",
    },
    {
        "tool": "pattern_on_path",
        "setup": "path_pattern",
        "args": {
            "features": ["Extrude2"],
            "path": {"sketch": "Sketch3"},
            "quantity": 3,
            "distance": 20,
            "distribution": "spacing",
        },
        "note": "three bosses along a line, 20 mm apart",
    },
    {
        "tool": "mirror",
        "setup": "plate_boss",
        "args": {"features": ["Extrude2"], "plane": "XZ"},
        "note": "mirror the boss about the XZ plane (y = 0: the copy lands outside the plate)",
    },
    {
        "tool": "sweep",
        "setup": "sweep",
        "args": {"profile": "Sketch1", "path": "Sketch2"},
        "note": "a circle swept along a line and an arc",
    },
    {
        "tool": "loft",
        "setup": "loft",
        "args": {"profiles": [{"profile": "Sketch1"}, {"profile": "Sketch2"}]},
        "note": "from a square to a circle 25 mm higher",
    },
    {
        "tool": "rib",
        "setup": "gusset",
        "args": {"curves": "Sketch2", "thickness": 2},
        "note": "a 2 mm rib in the corner of an L profile",
    },
    {
        "tool": "web",
        "setup": "tray",
        "args": {"curves": "Sketch2", "thickness": 2},
        "note": "a 2 mm wall across the tray",
    },
    {
        "tool": "emboss",
        "setup": "label",
        "args": {"sketch": "Sketch1", "faces": {"type": "cylinder", "count": 1}, "depth": 0.5},
        "note": "raise a small rectangle 0.5 mm on the round face",
    },
    {
        "tool": "thread",
        "setup": "shaft",
        "args": {
            "faces": {"type": "cylinder", "radius": 5, "count": 1},
            "modeled": True,
            "full_length": False,
            "length": 12,
        },
        "note": "a 12 mm modeled M10 thread on the 10 mm shaft",
    },
    {
        "tool": "primitive",
        "setup": "empty",
        "args": {"kind": "box", "plane": "XY", "length": 40, "width": 20, "height": 10},
        "note": "a 40 x 20 x 10 box",
    },
    {
        "tool": "coil",
        "setup": "empty",
        "args": {
            "plane": "XY",
            "diameter": 20,
            "revolutions": 4,
            "height": 20,
            "section_size": 2,
        },
        "note": "a 4-turn spring, 20 mm tall",
    },
    {
        "tool": "pipe",
        "setup": "pipe_path",
        "args": {"path": {"sketch": "Sketch1", "edge": 1}, "section_size": 4},
        "note": "a 4 mm pipe along a line",
    },
    {
        "tool": "gear",
        "setup": "empty",
        "args": {"module": 1.5, "teeth": 20, "thickness": 8, "hole": 8},
        "note": "a 20-tooth spur gear, module 1.5",
    },
    {
        "tool": "insert_hardware",
        "setup": "plate",
        "args": {
            "face": TOP,
            "at": [10, 10, 10],
            "standard": "iso4762",
            "size": "3",
            "length": 10,
        },
        "note": "an M3 x 10 socket head screw with its hole",
    },
    # -- modify ---------------------------------------------------------------------------------
    {
        "tool": "fillet",
        "setup": "plate",
        "args": {"edges": VERTICAL4, "radius": 5},
        "note": "round the four vertical corners",
    },
    {
        "tool": "chamfer",
        "setup": "plate",
        "args": {"edges": TOP4, "distance": 1},
        "note": "a 1 mm chamfer on the four top edges",
    },
    {
        "tool": "shell",
        "setup": "plate",
        "args": {"faces": TOP, "thickness": 2},
        "note": "hollow the plate, open at the top, 2 mm walls",
    },
    {
        "tool": "press_pull",
        "setup": "plate",
        "args": {"faces": TOP, "distance": 5},
        "note": "pull the top face up 5 mm",
    },
    {
        "tool": "fillet_sets",
        "setup": "plate",
        "args": {
            "sets": [
                {"edges": VERTICAL4, "radius": 5},
                {"edges": TOP4, "radius": 1},
            ]
        },
        "note": "two radii in one step",
    },
    {
        "tool": "rule_fillet",
        "setup": "plate_boss",
        "args": {"radius": 1, "rule": "all", "features": ["Extrude2"]},
        "note": "round every edge of the boss",
    },
    {
        "tool": "full_round_fillet",
        "setup": "empty",
        "args": {"faces": [{"normal": [0, 0, 1], "count": 1}]},
        "note": "round the top of a wall completely (the wall is made first)",
        "setup_extra": [
            call("primitive", kind="box", plane="XY", length=40, width=4, height=20),
        ],
    },
    {
        "tool": "draft",
        "setup": "plate",
        "args": {"plane": "XY", "faces": SIDES4, "angle": 3},
        "note": "3 degrees of draft on the four side walls",
    },
    {"tool": "scale", "setup": "plate", "args": {"factor": 0.5}, "note": "half as big"},
    {
        "tool": "combine",
        "setup": "two_bodies",
        "args": {"target": "Extrude1", "tools": ["Primitive1"], "operation": "cut"},
        "note": "cut the box out of the plate",
    },
    {
        "tool": "split_body",
        "setup": "revolved",
        "args": {"body": "Revolve1", "tool": "YZ"},
        "note": "split a cylinder in two halves at the YZ plane",
    },
    {
        "tool": "split_face",
        "setup": "revolved",
        "args": {"faces": {"type": "cylinder", "count": 1}, "tool": "XZ"},
        "note": "split the cylinder's round face in two at the XZ plane",
    },
    {
        "tool": "silhouette_split",
        "setup": "sphere",
        "args": {"body": "Primitive1", "direction": "Z", "operation": "body"},
        "note": "split a ball into its top and bottom halves (its outline seen from Z)",
    },
    {
        "tool": "replace_face",
        "setup": "two_heights",
        "args": {
            "faces": TOP,
            "of": "Primitive1",
            "target": {"face": TOP, "of": "Primitive2"},
        },
        "note": "raise the low box's top to the high box's top",
    },
    {
        "tool": "delete_face",
        "setup": "plate_hole",
        "args": {"faces": {"type": "cylinder", "count": 1}},
        "note": "delete the hole (the solid heals)",
    },
    {
        "tool": "remove_bodies",
        "setup": "two_bodies",
        "args": {"bodies": ["Primitive1"]},
        "note": "remove the box (a timeline step)",
    },
    {
        "tool": "delete_bodies",
        "setup": "two_bodies",
        "args": {"bodies": ["Primitive1"]},
        "note": "delete the box's body and its steps",
    },
    {
        "tool": "move_copy",
        "setup": "two_bodies",
        "args": {"bodies": ["Primitive1"], "move_type": "translate", "dx": 30},
        "note": "move the box 30 mm along X",
    },
    {
        "tool": "align",
        "setup": "two_heights",
        "args": {
            "from": {"face": {"normal": [0, 0, -1], "count": 1}, "of": "Primitive2"},
            "to": {"face": TOP, "of": "Primitive1"},
        },
        "note": "put the high box on top of the low one",
    },
    {
        "tool": "physical_material",
        "setup": "plate",
        "args": {"body": "Extrude1", "material": "aluminium"},
        "note": "make the plate aluminium",
    },
    {"tool": "list_materials", "setup": "none", "args": {}, "note": "materials and appearances"},
    {
        "tool": "appearance",
        "setup": "plate",
        "args": {"body": "Extrude1", "look": "plastic_red"},
        "note": "red plastic",
    },
    # -- surface, construct ---------------------------------------------------------------------
    {
        "tool": "surface",
        "setup": "surface_line",
        "args": {
            "kind": "extrude",
            "refs": [{"sketch": "Sketch1", "at": [15, 0]}],
            "options": {"distance": 20},
        },
        "note": "a 20 mm surface from a sketch line",
    },
    {
        "tool": "construct_plane",
        "setup": "plate",
        "args": {"preset": "OffsetPlane", "refs": [{"plane": "XY"}], "distance": 25},
        "note": "a plane 25 mm above XY",
    },
    {
        "tool": "construct_axis",
        "setup": "plate_hole",
        "args": {"preset": "AxisCylinder", "refs": [{"face": {"type": "cylinder", "count": 1}}]},
        "note": "an axis through the hole",
    },
    {
        "tool": "construct_point",
        "setup": "plate_hole",
        "args": {
            "preset": "PointCenter",
            "refs": [{"edge": {"type": "circle", "at": {"axis": "z", "value": "max"}, "count": 1}}],
        },
        "note": "a point at the centre of the hole's top edge",
    },
    # -- assemble -------------------------------------------------------------------------------
    {"tool": "new_component", "setup": "empty", "args": {"label": "Lid"}, "note": "a component"},
    {
        "tool": "components_from_bodies",
        "setup": "two_bodies",
        "args": {"bodies": ["Primitive1"], "label": "Block"},
        "note": "the box's body becomes the component Block",
    },
    {
        "tool": "copy_component",
        "setup": "components",
        "args": {"component": "Wheel", "dx": 40},
        "note": "a linked copy of the wheel 40 mm along X",
    },
    {
        "tool": "activate",
        "setup": "two_bodies",
        "args": {"target": "Extrude1"},
        "note": "work in the plate's body again",
    },
    {"tool": "new_body", "setup": "plate", "args": {"label": "Insert"}, "note": "a new body"},
    {
        "tool": "joint",
        "setup": "components",
        "args": {
            "type": "revolute",
            "first": {
                "component": "Wheel",
                "face": {"normal": [0, 0, -1], "count": 1},
                "snap": "centre",
            },
            "second": {"component": "Base", "face": TOP, "snap": "centre"},
        },
        "note": "the wheel sits on the base and turns about the joint's axis",
    },
    {
        "tool": "drive_joint",
        "setup": "components",
        "args": {"joint": "Joint", "angle": 45},
        "note": "turn the joint 45 degrees (the joint is made first)",
        "setup_extra": [
            call(
                "joint",
                type="revolute",
                first={
                    "component": "Wheel",
                    "face": {"normal": [0, 0, -1], "count": 1},
                    "snap": "centre",
                },
                second={"component": "Base", "face": TOP, "snap": "centre"},
            )
        ],
    },
    {"tool": "ground", "setup": "components", "args": {"component": "Base"}, "note": "fix Base"},
    {
        "tool": "pattern_components",
        "setup": "components",
        "args": {"component": "Wheel", "kind": "circular", "axis": "Z", "quantity": 3},
        "note": "three wheels around Z",
    },
    # -- timeline, parameters -------------------------------------------------------------------
    {"tool": "get_timeline", "setup": "plate_hole", "args": {}, "note": "the steps in order"},
    {
        "tool": "get_step",
        "setup": "plate_hole",
        "args": {"step": "Extrude1"},
        "note": "every option of the extrude",
    },
    {
        "tool": "edit_step",
        "setup": "plate_hole",
        "args": {"step": "Extrude1", "set": {"distance": 15}},
        "note": "make the plate 15 mm thick (the hole follows)",
    },
    {
        "tool": "roll_timeline",
        "setup": "plate_hole",
        "args": {"after": "Extrude1"},
        "note": "roll the history marker back to just after the extrude",
    },
    {
        "tool": "suppress_step",
        "setup": "plate_hole",
        "args": {"steps": ["Hole1"]},
        "note": "switch the hole off without deleting it",
    },
    {
        "tool": "delete_step",
        "setup": "plate_hole",
        "args": {"steps": ["Hole1"]},
        "note": "delete the hole step",
    },
    {
        "tool": "move_step",
        "setup": "grouped",
        "args": {"step": "Fillet1", "after": "Extrude1"},
        "note": "move the fillet before the hole",
    },
    {
        "tool": "rename",
        "setup": "plate",
        "args": {"target": "Extrude1", "name": "Base plate"},
        "note": "a clearer name in the timeline",
    },
    {
        "tool": "group_steps",
        "setup": "plate_hole",
        "args": {"steps": ["Sketch2", "Hole1"], "name": "Mounting hole"},
        "note": "group the hole and its sketch",
    },
    {
        "tool": "capture_design_history",
        "setup": "plate",
        "args": {"on": False},
        "note": "stop recording steps (direct modelling)",
    },
    {
        "tool": "set_parameter",
        "setup": "plate",
        "args": {"name": "thickness", "value": 12, "unit": "mm"},
        "note": "a user parameter",
    },
    {"tool": "list_parameters", "setup": "parameter", "args": {}, "note": "every parameter"},
    {
        "tool": "delete_parameter",
        "setup": "parameter",
        "args": {"name": "gap"},
        "note": "delete an unused parameter",
    },
    {
        "tool": "set_model_parameter",
        "setup": "parameter",
        "args": {"step": "Extrude1", "label": "Distance", "expression": "gap * 6"},
        "note": "drive the plate's thickness from the parameter gap",
    },
    {
        "tool": "undo",
        "setup": "filleted",
        "args": {},
        "note": "take back the fillet",
    },
    {
        "tool": "redo",
        "setup": "filleted",
        "args": {},
        "note": "redo the fillet after an undo",
        "setup_extra": [call("undo")],
    },
    # -- designs and files ----------------------------------------------------------------------
    {"tool": "new_design", "setup": "none", "args": {"name": "Bracket"}, "note": "a new design"},
    {
        "tool": "open_design",
        "setup": "saved",
        "args": {"path": "{tmp}/plate.FCStd"},
        "note": "open a saved design (already open here: it is switched to)",
    },
    {
        "tool": "save",
        "setup": "saved",
        "args": {},
        "note": "save again where it was saved",
    },
    {
        "tool": "save_as",
        "setup": "plate",
        "args": {"path": "{tmp}/bracket.FCStd"},
        "note": "save under a new name",
    },
    {
        "tool": "close_design",
        "setup": "two_designs",
        "args": {"design": "Second", "discard_changes": True},
        "note": "close a design that was never saved (a new design counts as changed)",
    },
    {"tool": "list_designs", "setup": "two_designs", "args": {}, "note": "the open designs"},
    {
        "tool": "switch_design",
        "setup": "two_designs",
        "args": {"design": "Example"},
        "note": "make another open design the active one",
    },
    {
        "tool": "export",
        "setup": "plate_hole",
        "args": {"format": "stl", "path": "{tmp}/plate.stl"},
        "note": "an STL for 3D printing",
    },
    {
        "tool": "export",
        "setup": "plate_hole",
        "args": {"format": "step", "path": "{tmp}/plate.step"},
        "note": "a STEP file for other CAD programs",
    },
    {
        "tool": "import_file",
        "setup": "empty",
        "args": {"path": "{tmp}/part.step"},
        "note": "insert a STEP file (written first by the setup)",
        "setup_extra": [
            call("primitive", kind="box", plane="XY", length=10, width=10, height=10),
            call("export", format="step", path="{tmp}/part.step"),
            call("new_design", name="Assembly"),
        ],
    },
    # -- drawings -------------------------------------------------------------------------------
    {
        "tool": "create_drawing",
        "setup": "plate_hole",
        "args": {"base_view": "Front", "projected": ["Top", "Right", "FrontTopRight"]},
        "note": "three views and an isometric",
    },
    {
        "tool": "add_drawing_view",
        "setup": "drawing",
        "args": {"kind": "projected", "parent": "BaseView", "direction": "FrontTopRight"},
        "note": "an isometric view projected from the base view",
    },
    {
        "tool": "add_drawing_dimension",
        "setup": "drawing",
        "args": {"view": "BaseView", "picks": [{"kind": "line", "near": [0, 5]}]},
        "note": "the length of the line nearest to (0, 5) in the base view",
    },
    {
        "tool": "add_drawing_annotation",
        "setup": "drawing",
        "args": {"kind": "text", "text": "Break all sharp edges", "at": [20, 40]},
        "note": "a note on the sheet",
    },
    {"tool": "get_drawing", "setup": "drawing", "args": {}, "note": "the sheet and its views"},
    {
        "tool": "export_drawing",
        "setup": "drawing",
        "args": {"format": "dxf", "path": "{tmp}/plate.dxf"},
        "note": "the drawing as DXF (PDF needs the window)",
    },
    # -- view -----------------------------------------------------------------------------------
    {
        "tool": "set_view",
        "setup": "plate",
        "args": {"orientation": "top"},
        "note": "look from the top (needs the SciForge window)",
        "gui": True,
    },
    {
        "tool": "get_view",
        "setup": "plate",
        "args": {},
        "note": "the camera (needs the SciForge window)",
        "gui": True,
    },
    {
        "tool": "named_view",
        "setup": "plate",
        "args": {"action": "list"},
        "note": "the design's named views",
    },
    {
        "tool": "show_hide",
        "setup": "plate",
        "args": {"targets": ["Sketch1"], "visible": True},
        "note": "show the plate's sketch",
    },
    # -- help and documentation -----------------------------------------------------------------
    {"tool": "get_help", "setup": "none", "args": {"topic": "picks"}, "note": "the pick rules"},
    {"tool": "list_tools", "setup": "none", "args": {"category": "inspect"}, "note": "by category"},
    {
        "tool": "docs_search",
        "setup": "none",
        "args": {"query": "shell open top wall thickness", "limit": 3},
        "note": "find how to hollow a part",
    },
    {
        "tool": "docs_read",
        "setup": "none",
        "args": {"path": "handbook.md", "section": "units-and-coordinates"},
        "note": "one section of the handbook",
    },
    {
        "tool": "examples_search",
        "setup": "none",
        "args": {"query": "bolt circle flange", "limit": 3},
        "note": "examples of a flange with holes around a circle",
    },
]
