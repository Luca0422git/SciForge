"""All of SciForge's layout lives here as plain data, so tweaking the interface
never means touching GUI code.

A command "slot" is either a command name or a tuple of alternatives; the
first one that exists in the running FreeCAD wins, and slots that resolve to
nothing are skipped and listed in SciForge > Diagnostics.
"""

# If drop-down group buttons misbehave on your FreeCAD build, set this to
# False and every group becomes a flat run of buttons instead.
USE_DROPDOWNS = True

# The Fusion-style ribbon (ribbon_config.py) replaces the plain toolbars below.
# Set to False to get the old toolbars back (e.g. if the ribbon misbehaves).
USE_RIBBON = True

# Drop-down groups. Keys are SciForge command ids.
GROUPS = {
    "SciForge_GroupCreate": {
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
    "SciForge_GroupCut": {
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
    "SciForge_GroupModify": {
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
    "SciForge_GroupConstruct": {
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
    "SciForge_GroupSketchDraw": {
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
    "SciForge_GroupSketchModify": {
        "title": "Sketch Modify",
        "tip": "Trim, extend, fillet and offset sketch geometry",
        "commands": [
            "Sketcher_Trimming",
            "Sketcher_Extend",
            "Sketcher_CreateFillet",
            "Sketcher_Offset",
            # FreeCAD 1.1 split the old Sketcher_External into Projection and
            # Intersection, which matches Fusion's separate Project / Intersect.
            ("Sketcher_Projection", "Sketcher_External"),
            "Sketcher_Intersection",
        ],
    },
}

# Toolbars, in order. Items are group ids, SciForge command ids, or command slots.
TOOLBARS = [
    (
        "SciForge Design",
        [
            "SciForge_NewDesign",
            "SciForge_NewSketch",
            "SciForge_GroupCreate",
            "SciForge_GroupCut",
            "SciForge_GroupModify",
            "SciForge_GroupConstruct",
            "SciForge_CommandSearch",
        ],
    ),
    (
        "SciForge Sketch",
        [
            "SciForge_GroupSketchDraw",
            "SciForge_GroupSketchModify",
            ("Sketcher_Dimension", "Sketcher_ConstrainDistance"),
            "Sketcher_ToggleConstruction",
            "Sketcher_LeaveSketch",
        ],
    ),
    (
        "SciForge View",
        [
            "Std_ViewFitAll",
            "Std_ViewIsometric",
            "Std_ViewFront",
            "Std_ViewTop",
            "Std_ViewRight",
        ],
    ),
]

# Commands shown in the top-level SciForge menu (besides the group submenus).
FORGE_MENU = [
    "SciForge_NewDesign",
    "SciForge_NewSketch",
    "SciForge_CommandSearch",
    "SciForge_ToggleTimeline",
    "SciForge_ResetShortcuts",
    "SciForge_Diagnostics",
]

# Fusion-style shortcut map. Applied while the SciForge workbench is active and
# restored when you leave it. Edit freely, or override per machine with
# <FreeCAD user data dir>/SciForge/shortcuts.json ({"Command_Name": "Key"}).
# These follow Fusion's defaults as best I know them; verify against your
# own muscle memory and adjust.
SHORTCUTS = {
    "SciForge_CommandSearch": "S",
    "SciForge_PressPull": "Q",
    "SciForge_Extrude": "E",
    "PartDesign_Fillet": "F",
    "PartDesign_Hole": "H",
    "Sketcher_Dimension": "D",
    "Sketcher_CreateLine": "L",
    "Sketcher_CreateCircle": "C",
    "Sketcher_CreateRectangle": "R",
    "Sketcher_Trimming": "T",
    "Sketcher_ToggleConstruction": "X",
    "Sketcher_Offset": "O",
    "Sketcher_Projection": "P",
    "Std_TransformManip": "M",
    "Std_Measure": "I",
    "Std_ViewFitAll": "F6",
}

# When SciForge has its own Fusion-style version of a command, the key runs that
# one instead (the ribbon does the same: see the ("SciForge_X", "FreeCAD_X") pairs
# in ribbon_config.py).
PREFERRED = {
    "PartDesign_Fillet": "SciForge_Fillet",
    "PartDesign_Hole": "SciForge_Hole",
    "Std_TransformManip": "SciForge_Move",
    "Std_Measure": "SciForge_Measure",
    "Sketcher_CreateLine": "SciForge_SketchLine",
    "Sketcher_Offset": "SciForge_SketchOffset",
}
