"""All of Forge's layout lives here as plain data, so tweaking the interface
never means touching GUI code.

A command "slot" is either a command name or a tuple of alternatives; the
first one that exists in the running FreeCAD wins, and slots that resolve to
nothing are skipped and listed in Forge > Diagnostics.
"""

# If drop-down group buttons misbehave on your FreeCAD build, set this to
# False and every group becomes a flat run of buttons instead.
USE_DROPDOWNS = True

# Drop-down groups. Keys are Forge command ids.
GROUPS = {
    "Forge_GroupCreate": {
        "title": "Create",
        "tip": "Add material: extrude, revolve, loft, sweep",
        "commands": [
            "PartDesign_Pad",
            "PartDesign_Revolution",
            "PartDesign_AdditiveLoft",
            "PartDesign_AdditivePipe",
            "PartDesign_AdditiveHelix",
        ],
    },
    "Forge_GroupCut": {
        "title": "Cut",
        "tip": "Remove material: cut, groove, holes",
        "commands": [
            "PartDesign_Pocket",
            "PartDesign_Hole",
            "PartDesign_Groove",
            "PartDesign_SubtractiveLoft",
            "PartDesign_SubtractivePipe",
        ],
    },
    "Forge_GroupModify": {
        "title": "Modify",
        "tip": "Fillet, chamfer, draft, shell and patterns",
        "commands": [
            "PartDesign_Fillet",
            "PartDesign_Chamfer",
            "PartDesign_Draft",
            "PartDesign_Thickness",
            "PartDesign_Mirrored",
            "PartDesign_LinearPattern",
            "PartDesign_PolarPattern",
            "PartDesign_MultiTransform",
        ],
    },
    "Forge_GroupConstruct": {
        "title": "Construct",
        "tip": "Reference planes, axes, points and coordinate systems",
        "commands": [
            "PartDesign_Plane",
            "PartDesign_Line",
            "PartDesign_Point",
            "PartDesign_CoordinateSystem",
            "PartDesign_ShapeBinder",
        ],
    },
    "Forge_GroupSketchDraw": {
        "title": "Sketch Draw",
        "tip": "Sketch geometry",
        "commands": [
            "Sketcher_CreateLine",
            "Sketcher_CreatePolyline",
            "Sketcher_CreateRectangle",
            "Sketcher_CreateCircle",
            "Sketcher_CreateArc",
            "Sketcher_CreateSlot",
            "Sketcher_CreatePoint",
        ],
    },
    "Forge_GroupSketchModify": {
        "title": "Sketch Modify",
        "tip": "Trim, extend, fillet and offset sketch geometry",
        "commands": [
            "Sketcher_Trimming",
            "Sketcher_Extend",
            "Sketcher_CreateFillet",
            "Sketcher_Offset",
            "Sketcher_External",
        ],
    },
}

# Toolbars, in order. Items are group ids, Forge command ids, or command slots.
TOOLBARS = [
    (
        "Forge Design",
        [
            "Forge_NewDesign",
            "Forge_NewSketch",
            "Forge_GroupCreate",
            "Forge_GroupCut",
            "Forge_GroupModify",
            "Forge_GroupConstruct",
            "Forge_CommandSearch",
        ],
    ),
    (
        "Forge Sketch",
        [
            "Forge_GroupSketchDraw",
            "Forge_GroupSketchModify",
            ("Sketcher_Dimension", "Sketcher_ConstrainDistance"),
            "Sketcher_ToggleConstruction",
            "Sketcher_LeaveSketch",
        ],
    ),
    (
        "Forge View",
        [
            "Std_ViewFitAll",
            "Std_ViewIsometric",
            "Std_ViewFront",
            "Std_ViewTop",
            "Std_ViewRight",
        ],
    ),
]

# Commands shown in the top-level Forge menu (besides the group submenus).
FORGE_MENU = [
    "Forge_NewDesign",
    "Forge_NewSketch",
    "Forge_CommandSearch",
    "Forge_ToggleTimeline",
    "Forge_ResetShortcuts",
    "Forge_Diagnostics",
]

# Fusion-style shortcut map. Applied while the Forge workbench is active and
# restored when you leave it. Edit freely, or override per machine with
# <FreeCAD user data dir>/Forge/shortcuts.json ({"Command_Name": "Key"}).
# These follow Fusion's defaults as best I know them; verify against your
# own muscle memory and adjust.
SHORTCUTS = {
    "Forge_CommandSearch": "S",
    "PartDesign_Pad": "E",
    "PartDesign_Fillet": "F",
    "PartDesign_Hole": "H",
    "Sketcher_Dimension": "D",
    "Sketcher_CreateLine": "L",
    "Sketcher_CreateCircle": "C",
    "Sketcher_CreateRectangle": "R",
    "Sketcher_Trimming": "T",
    "Sketcher_ToggleConstruction": "X",
    "Std_ViewFitAll": "F6",
}
