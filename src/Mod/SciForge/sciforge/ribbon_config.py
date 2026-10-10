# SPDX-License-Identifier: LGPL-2.1-or-later
"""The ribbon (tabs, groups, menus) as plain data. Pure Python, unit tested.

Layout, order and keyboard shortcuts follow Fusion's stock Design workspace
(captured from the owner's screenshots, docs/sciforge/parity/ui-shell.md).
Labels are generic CAD terms; vendor-specific and out-of-scope entries
(cloud part catalogs, form/sculpt, PCB) are left out on purpose.

An item's command is:
  "Name"            a FreeCAD/SciForge command
  "Name#2"          entry 2 of a FreeCAD drop-down command (e.g. primitives)
  ("A", "B")        first one that exists in the running FreeCAD
  None              not available in SciForge yet: shown greyed out, like
                    Fusion greys out unavailable commands. The menus double as
                    a visible parity to-do list.
"""

SEP = None  # separator line inside a menu


def item(label, command, icon=None, key="", note=""):
    """One menu entry. key = Fusion's shortcut, shown at the right of the menu."""
    return {"label": label, "command": command, "icon": icon, "key": key, "note": note}


def sub(label, items, icon=None):
    """A submenu (shown with a little arrow)."""
    return {"label": label, "submenu": items, "icon": icon}


def group(gid, title, big, items):
    """big: labels of the items shown as large toolbar icons, in order."""
    return {"id": gid, "title": title, "big": big, "items": items}


INTERIM = "Interim: until SciForge has a unified Revolve dialog, cutting is a separate command."

# ---------------------------------------------------------------- SOLID tab
SOLID_CREATE = group(
    "create",
    "CREATE",
    ["Create Sketch", "Extrude", "Revolve", "Hole", "Rectangular Pattern", "Mirror"],
    [
        item("Create Sketch", "SciForge_NewSketch", "sketch_create"),
        item("Derive", None, "derive"),
        SEP,
        item(
            "Extrude",
            "SciForge_Extrude",
            "extrude",
            "E",
            note="Join, cut or new body in one dialog; drag into the part to cut.",
        ),
        item("Revolve", ("SciForge_Revolve", "PartDesign_Revolution"), "revolve"),
        item("Sweep", ("SciForge_Sweep", "PartDesign_AdditivePipe"), "sweep"),
        item("Loft", ("SciForge_Loft", "PartDesign_AdditiveLoft"), "loft"),
        item("Rib", None, "rib"),
        item("Web", None, "web"),
        item("Emboss", None, "emboss"),
        SEP,
        item("Hole", ("SciForge_Hole", "PartDesign_Hole"), "hole", "H"),
        item("Thread", None, "thread"),
        SEP,
        item("Box", ("SciForge_Box", "PartDesign_CompPrimitiveAdditive#0"), "box"),
        item("Cylinder", ("SciForge_Cylinder", "PartDesign_CompPrimitiveAdditive#1"), "cylinder"),
        item("Sphere", ("SciForge_Sphere", "PartDesign_CompPrimitiveAdditive#2"), "sphere"),
        item("Torus", ("SciForge_Torus", "PartDesign_CompPrimitiveAdditive#5"), "torus"),
        item("Coil", ("SciForge_Coil", "PartDesign_AdditiveHelix"), "coil"),
        item("Pipe", None, "pipe"),
        SEP,
        sub(
            "Pattern",
            [
                item(
                    "Rectangular Pattern",
                    ("SciForge_RectangularPattern", "PartDesign_LinearPattern"),
                    "pattern_rect",
                ),
                item(
                    "Circular Pattern",
                    ("SciForge_CircularPattern", "PartDesign_PolarPattern"),
                    "pattern_circ",
                ),
                item("Pattern on Path", None, "pattern_rect"),
            ],
        ),
        item("Mirror", ("SciForge_Mirror", "PartDesign_Mirrored"), "mirror"),
        SEP,
        item("Thicken", None, "thicken"),
        item("Boundary Fill", None, "boundary_fill"),
        SEP,
        item("Create Base Feature", None, "box"),
        item("Joint Origin", None, "joint"),
    ],
)

SOLID_MODIFY = group(
    "modify",
    "MODIFY",
    ["Press Pull", "Fillet", "Chamfer", "Shell", "Combine", "Split Body", "Scale", "Move/Copy"],
    [
        item(
            "Press Pull",
            "SciForge_PressPull",
            "press_pull",
            "Q",
            note="Faces: push/pull. Edges: fillet. A fillet face: change its radius.",
        ),
        item("Fillet", ("SciForge_Fillet", "PartDesign_Fillet"), "fillet", "F"),
        item("Chamfer", ("SciForge_Chamfer", "PartDesign_Chamfer"), "chamfer"),
        SEP,
        item("Shell", ("SciForge_Shell", "PartDesign_Thickness"), "shell"),
        item("Draft", ("SciForge_Draft", "PartDesign_Draft"), "draft"),
        item("Scale", None, "scale"),
        item("Combine", ("SciForge_Combine", "PartDesign_Boolean"), "combine"),
        item("Offset Face", "SciForge_PressPull", "offset_face"),
        item("Replace Face", None, "replace_face"),
        item("Split Face", None, "split_face"),
        item("Split Body", None, "split_body"),
        item("Silhouette Split", None, "silhouette_split"),
        SEP,
        item("Move/Copy", ("SciForge_Move", "Std_TransformManip"), "move", "M"),
        item("Align", None, "align", "A"),
        item("Delete", ("SciForge_Delete", "Std_Delete"), "delete", "Del"),
        item("Remove", None, "remove"),
        SEP,
        item("Physical Material", ("SciForge_PhysicalMaterial", "Std_SetMaterial"), "material"),
        item("Appearance", ("SciForge_Appearance", "Std_SetAppearance"), "appearance"),
        item("Manage Materials", "Material_Edit", "material"),
        SEP,
        item("Change Parameters", "SciForge_ChangeParameters", "parameters"),
        item("Compute All", "Std_Refresh", "compute", "Ctrl+B"),
    ],
)

CONSTRUCT = group(
    "construct",
    "CONSTRUCT",
    ["Offset Plane"],
    [
        item("User Coordinate System", "PartDesign_CoordinateSystem", "ucs"),
        SEP,
        item(
            "Offset Plane",
            "SciForge_Construct_OffsetPlane",
            "offset_plane",
        ),
        item("Plane at Angle", "SciForge_Construct_PlaneAtAngle", "plane_angle"),
        item("Tangent Plane", "SciForge_Construct_TangentPlane", "tangent_plane"),
        item("Midplane", "SciForge_Construct_Midplane", "midplane"),
        item("Perpendicular Plane", "SciForge_Construct_PerpendicularPlane", "plane_perp"),
        item("Plane Through Two Edges", "SciForge_Construct_PlaneTwoEdges", "plane_two_edges"),
        item(
            "Plane Through Three Points",
            "SciForge_Construct_PlaneThreePoints",
            "plane_three_points",
        ),
        item("Plane Along Path", "SciForge_Construct_PlaneAlongPath", "plane_along_path"),
        SEP,
        item("Axis Through Cylinder/Cone/Torus", "SciForge_Construct_AxisCylinder", "axis"),
        item("Axis Perpendicular to Face", "SciForge_Construct_AxisNormal", "axis"),
        item("Axis Through Two Planes", "SciForge_Construct_AxisTwoPlanes", "axis"),
        item("Axis Through Two Points", "SciForge_Construct_AxisTwoPoints", "axis_two_points"),
        item("Axis Through Edge", "SciForge_Construct_AxisEdge", "axis_edge"),
        SEP,
        item("Point at Vertex", "SciForge_Construct_PointVertex", "point"),
        item("Point Through Two Edges", "SciForge_Construct_PointTwoEdges", "point"),
        item("Point Through Three Planes", "SciForge_Construct_PointThreePlanes", "point"),
        item("Point at Center of Circle/Sphere/Torus", "SciForge_Construct_PointCenter", "point"),
        item("Point at Edge and Plane", "SciForge_Construct_PointEdgePlane", "point"),
        item("Point Along Path", "SciForge_Construct_PointAlongPath", "point"),
    ],
)

INSPECT = group(
    "inspect",
    "INSPECT",
    ["Measure", "Section Analysis"],
    [
        item("Measure", ("SciForge_Measure", "Std_Measure"), "measure", "I"),
        item("Interference", None, "interference"),
        item("Curvature Comb Analysis", None, "curvature"),
        item("Zebra Analysis", None, "zebra"),
        item("Draft Analysis", None, "draft"),
        SEP,
        item(
            "Section Analysis",
            ("SciForge_SectionAnalysis", "Part_SectionCut", "Std_ToggleClipPlane"),
            "section",
        ),
        item("Center of Mass", None, "center_of_mass"),
    ],
)

INSERT = group(
    "insert",
    "INSERT",
    ["Insert Component", "Canvas", "Insert Mesh"],
    [
        item("Decal", None, "decal"),
        item("Canvas", None, "canvas"),
        item("Insert SVG", "Std_Import", "insert_svg"),
        item("Insert DXF", "Std_Import", "insert_dxf"),
        item("Insert Mesh", "Mesh_Import", "insert_mesh"),
        SEP,
        item("Insert Component", None, "insert_component"),
        item("Insert Derive", None, "derive"),
    ],
)

ASSEMBLE = group(
    "assemble",
    "ASSEMBLE",
    ["New Component"],
    [
        item("New Component", ("SciForge_NewComponent", "Std_Part"), "new_component"),
        item("Joint", None, "joint", "J"),
        item("As-built Joint", None, "joint"),
        item("Joint Origin", None, "joint"),
        item("Rigid Group", None, "new_component"),
        SEP,
        item("Drive Joints", None, "joint"),
        item("Motion Link", None, "joint"),
    ],
)

SELECT = group(
    "select",
    "SELECT",
    ["Window Selection"],
    [
        item("Window Selection", "Std_BoxSelection", "select"),
        item("Freeform Selection", None, "select"),
        item("Paint Selection", None, "select"),
        SEP,
        item("Select All", "Std_SelectAll", "select"),
    ],
)

# ---------------------------------------------------------------- SURFACE tab
SURFACE_CREATE = group(
    "s_create",
    "CREATE",
    ["Extrude", "Loft", "Patch", "Ruled"],
    [
        item("Create Sketch", "SciForge_NewSketch", "sketch_create"),
        SEP,
        item("Extrude", "Part_Extrude", "extrude"),
        item("Revolve", "Part_Revolve", "revolve"),
        item("Sweep", "Part_Sweep", "sweep"),
        item("Loft", ("Surface_Sections", "Part_Loft"), "loft"),
        item("Patch", "Surface_Filling", "boundary_fill"),
        item("Ruled", "Part_RuledSurface", "thicken"),
        item("Offset", "Part_Offset", "offset_face"),
        item("Fill", "Surface_GeomFillSurface", "boundary_fill"),
        item("Blend Curve", "Surface_BlendCurve", "sk_spline"),
    ],
)
SURFACE_MODIFY = group(
    "s_modify",
    "MODIFY",
    ["Trim", "Extend", "Thicken"],
    [
        item("Trim", None, "sk_trim"),
        item("Untrim", None, "sk_extend"),
        item("Extend", "Surface_ExtendFace", "sk_extend"),
        item("Stitch", None, "combine"),
        item("Unstitch", None, "split_body"),
        item("Thicken", "Part_Thickness", "thicken"),
        SEP,
        item("Delete", ("SciForge_Delete", "Std_Delete"), "delete", "Del"),
    ],
)

# ---------------------------------------------------------------- MESH tab
MESH_CREATE = group(
    "m_create",
    "CREATE",
    ["Insert Mesh"],
    [
        item("Insert Mesh", "Mesh_Import", "insert_mesh"),
        item("Tessellate", "Mesh_FromPartShape", "insert_mesh"),
    ],
)
MESH_PREPARE = group(
    "m_prepare",
    "PREPARE",
    ["Repair", "Remesh"],
    [
        item("Repair", "Mesh_Evaluation", "compute"),
        item("Remesh", "Mesh_RemeshGmsh", "insert_mesh"),
        item("Reduce", "Mesh_Decimating", "insert_mesh"),
        item("Smooth", "Mesh_Smoothing", "insert_mesh"),
    ],
)
MESH_MODIFY = group(
    "m_modify",
    "MODIFY",
    ["Plane Cut"],
    [
        item("Plane Cut", "Mesh_TrimByPlane", "split_body"),
        item("Separate", "Mesh_SplitComponents", "split_body"),
        item("Combine", "Mesh_Union", "combine"),
        item("Reverse Normal", "Mesh_FlipNormals", "compute"),
    ],
)
MESH_CONVERT = group(
    "m_convert",
    "CONVERT",
    ["Convert Mesh"],
    [
        item("Convert Mesh", "Part_ShapeFromMesh", "insert_mesh"),
    ],
)

# ---------------------------------------------------------------- UTILITIES tab
UTIL_MAKE = group(
    "u_make",
    "MAKE",
    ["3D Print"],
    [
        item("3D Print", "SciForge_3DPrint", "insert_mesh", note="Save a body as 3MF or STL."),
        item("Export", "Std_Export", "qa_save"),
    ],
)
UTIL_ADDINS = group(
    "u_addins",
    "ADD-INS",
    ["Scripts and Add-Ins"],
    [
        item("Scripts and Add-Ins", "Std_DlgMacroExecute", "parameters"),
        item("Add-on Manager", "Std_AddonMgr", "new_component"),
    ],
)
UTIL_UTILITY = group(
    "u_utility",
    "UTILITY",
    ["Preferences"],
    [
        item("Preferences", "Std_DlgPreferences", "tl_settings"),
        item("SciForge Diagnostics", "SciForge_Diagnostics", "compute"),
        item("Command Search", "SciForge_CommandSearch", "nav_zoom", "S"),
    ],
)

# ---------------------------------------------------------------- SKETCH tab (contextual)
SKETCH_CREATE = group(
    "k_create",
    "CREATE",
    ["Circle", "Line", "Spline", "2-Point Rectangle", "Mirror", "Sketch Dimension"],
    [
        item("Line", "SciForge_SketchLine", "sk_line", "L"),
        item("Midpoint Line", None, "sk_line"),
        sub(
            "Rectangle",
            [
                item("2-Point Rectangle", "Sketcher_CreateRectangle", "sk_rectangle", "R"),
                item("3-Point Rectangle", None, "sk_rectangle"),
                item("Center Rectangle", "Sketcher_CreateRectangle_Center", "sk_rectangle"),
            ],
            "sk_rectangle",
        ),
        sub(
            "Circle",
            [
                item("Center Diameter Circle", "Sketcher_CreateCircle", "sk_circle", "C"),
                item("2-Point Circle", None, "sk_circle"),
                item("3-Point Circle", "Sketcher_Create3PointCircle", "sk_circle"),
                item("2-Tangent Circle", None, "sk_circle"),
                item("3-Tangent Circle", None, "sk_circle"),
            ],
            "sk_circle",
        ),
        sub(
            "Arc",
            [
                item("3-Point Arc", "Sketcher_Create3PointArc", "sk_arc"),
                item("Center Point Arc", "Sketcher_CreateArc", "sk_arc"),
                item("Tangent Arc", None, "sk_arc"),
            ],
            "sk_arc",
        ),
        sub(
            "Polygon",
            [
                item("Circumscribed Polygon", "SciForge_PolygonCircumscribed", "sk_polygon"),
                item("Inscribed Polygon", "SciForge_PolygonInscribed", "sk_polygon"),
                item("Edge Polygon", None, "sk_polygon"),
            ],
            "sk_polygon",
        ),
        item("Ellipse", "Sketcher_CreateEllipseByCenter", "sk_ellipse"),
        sub(
            "Slot",
            [
                item("Center to Center Slot", "Sketcher_CreateSlot", "sk_slot"),
                item("Overall Slot", None, "sk_slot"),
                item("Center Point Slot", None, "sk_slot"),
                item("Three Point Arc Slot", "Sketcher_CreateArcSlot", "sk_slot"),
                item("Center Point Arc Slot", "Sketcher_CreateArcSlot", "sk_slot"),
            ],
            "sk_slot",
        ),
        sub(
            "Spline",
            [
                item("Fit Point Spline", "Sketcher_CreateBSplineByInterpolation", "sk_spline"),
                item("Control Point Spline", "Sketcher_CreateBSpline", "sk_spline"),
            ],
            "sk_spline",
        ),
        item("Conic Curve", None, "sk_conic"),
        item("Point", "Sketcher_CreatePoint", "sk_point"),
        item("Text", None, "sk_text"),
        SEP,
        item("Mirror", "SciForge_SketchMirror", "sk_mirror"),
        item("Circular Pattern", "SciForge_SketchCircularPattern", "sk_pattern_circ"),
        item("Rectangular Pattern", "SciForge_SketchRectangularPattern", "sk_pattern_rect"),
        SEP,
        sub(
            "Project / Include",
            [
                item("Project", "SciForge_SketchProject", "sk_project", "P"),
                item("Intersect", "Sketcher_Intersection", "sk_intersect"),
                item("Include 3D Geometry", "SciForge_SketchInclude3D", "sk_project"),
                item("Project to Surface", None, "sk_project"),
            ],
        ),
        item("Sketch Dimension", "Sketcher_Dimension", "sk_dimension", "D"),
    ],
)
SKETCH_MODIFY = group(
    "k_modify",
    "MODIFY",
    ["Fillet", "Trim", "Offset", "Extend"],
    [
        item("Fillet", "Sketcher_CreateFillet", "sk_fillet"),
        item("Chamfer", "Sketcher_CreateChamfer", "sk_chamfer"),
        item("Offset", "SciForge_SketchOffset", "sk_offset", "O"),
        item("Trim", "Sketcher_Trimming", "sk_trim", "T"),
        item("Extend", "Sketcher_Extend", "sk_extend"),
        item("Break", "Sketcher_Split", "sk_break"),
        item("Sketch Scale", "SciForge_SketchScale", "sk_scale"),
        item("Move/Copy", "SciForge_SketchMove", "sk_move", "M"),
    ],
)
SKETCH_CONSTRAINTS = group(
    "k_constraints",
    "CONSTRAINTS",
    ["Fix/Unfix", "Coincident", "Tangent", "Equal", "Parallel", "Perpendicular"],
    [
        item("Coincident", "Sketcher_ConstrainCoincidentUnified", "c_coincident"),
        item("Collinear", None, "c_collinear"),
        item("Concentric", None, "c_concentric"),
        item("Midpoint", None, "c_midpoint"),
        item("Fix/Unfix", "Sketcher_ConstrainLock", "c_fix"),
        item("Parallel", "Sketcher_ConstrainParallel", "c_parallel"),
        item("Perpendicular", "Sketcher_ConstrainPerpendicular", "c_perpendicular"),
        item("Horizontal/Vertical", "Sketcher_ConstrainHorVer", "c_horizontal"),
        item("Tangent", "Sketcher_ConstrainTangent", "c_tangent"),
        item("Curvature", None, "c_smooth"),
        item("Equal", "Sketcher_ConstrainEqual", "c_equal"),
        item("Symmetry", "Sketcher_ConstrainSymmetric", "c_symmetric"),
    ],
)
FINISH_SKETCH = group(
    "k_finish",
    "FINISH SKETCH",
    ["Finish Sketch"],
    [
        item("Finish Sketch", "SciForge_FinishSketch", "finish_sketch"),
        item("Toggle Construction", "Sketcher_ToggleConstruction", "sk_line", "X"),
    ],
)

TABS = [
    {
        "id": "solid",
        "title": "SOLID",
        "groups": [SOLID_CREATE, SOLID_MODIFY, CONSTRUCT, INSPECT, INSERT, ASSEMBLE, SELECT],
    },
    {
        "id": "surface",
        "title": "SURFACE",
        "groups": [SURFACE_CREATE, SURFACE_MODIFY, CONSTRUCT, INSPECT, INSERT, SELECT],
    },
    {
        "id": "mesh",
        "title": "MESH",
        "groups": [
            MESH_CREATE,
            MESH_PREPARE,
            MESH_MODIFY,
            MESH_CONVERT,
            CONSTRUCT,
            INSPECT,
            SELECT,
        ],
    },
    {"id": "utilities", "title": "UTILITIES", "groups": [UTIL_MAKE, UTIL_ADDINS, UTIL_UTILITY]},
    {
        "id": "sketch",
        "title": "SKETCH",
        "contextual": True,
        "groups": [
            SKETCH_CREATE,
            SKETCH_MODIFY,
            SKETCH_CONSTRAINTS,
            INSPECT,
            INSERT,
            SELECT,
            FINISH_SKETCH,
        ],
    },
]

# Quick-access buttons at the top left, like Fusion's application bar.
QUICK_ACCESS = [
    item("Menu", "__menu__", "qa_menu", note="All FreeCAD menus"),
    item("New", "Std_New", "qa_new", "Ctrl+N"),
    item("Open", "Std_Open", "qa_open", "Ctrl+O"),
    item("Save", "Std_Save", "qa_save", "Ctrl+S"),
    item("Undo", "Std_Undo", "qa_undo", "Ctrl+Z"),
    item("Redo", "Std_Redo", "qa_redo", "Ctrl+Y"),
]

# Navigation bar floating at the bottom centre of the 3D view.
NAV_BAR = [
    item("Orbit", None, "nav_orbit", note="Shift + middle mouse button"),
    item("Look At", "Std_AlignToSelection", "nav_lookat"),
    item("Pan", None, "nav_pan", note="Middle mouse button"),
    item("Zoom Window", "Std_ViewBoxZoom", "nav_zoom"),
    item("Fit", "Std_ViewFitAll", "nav_fit", "F6"),
    sub(
        "Display Settings",
        [
            item("Visual Style", "Std_DrawStyle", "nav_display"),
            item("Orthographic", "Std_OrthographicCamera", "nav_display"),
            item("Perspective", "Std_PerspectiveCamera", "nav_display"),
        ],
        "nav_display",
    ),
    item("Grid and Snaps", None, "nav_grid"),
    item("Viewports", None, "nav_viewports"),
]


# Right-click marking menu: 8 slots around the cursor, clockwise from the top
# (N, NE, E, SE, S, SW, W, NW), then a list underneath. "__repeat__" repeats the
# last command. NOTE: positions are a first guess; confirm against Fusion
# (docs/sciforge/parity/ui-shell.md).
MARKING_MENU = [
    item("Repeat", "__repeat__", "compute"),
    item("Delete", ("SciForge_Delete", "Std_Delete"), "delete", "Del"),
    item("Press Pull", "SciForge_PressPull", "press_pull", "Q"),
    item("Undo", "Std_Undo", "qa_undo", "Ctrl+Z"),
    item("Move/Copy", ("SciForge_Move", "Std_TransformManip"), "move", "M"),
    item("Hole", ("SciForge_Hole", "PartDesign_Hole"), "hole", "H"),
    item("Create Sketch", "SciForge_NewSketch", "sketch_create"),
    item("Extrude", "SciForge_Extrude", "extrude", "E"),
]

MARKING_LIST = [
    item("Redo", "Std_Redo", "qa_redo", "Ctrl+Y"),
    item("Fillet", ("SciForge_Fillet", "PartDesign_Fillet"), "fillet", "F"),
    item("Measure", ("SciForge_Measure", "Std_Measure"), "measure", "I"),
    SEP,
    item("Hide", "Std_HideSelection", "nav_display"),
    item("Show All", "Std_ShowObjects", "nav_display"),
    item("Fit", "Std_ViewFitAll", "nav_fit", "F6"),
    item("Look At", "Std_AlignToSelection", "nav_lookat"),
]


def iter_items(entries):
    """Every item (not separators or submenus) in a list, depth first."""
    for entry in entries:
        if entry is SEP:
            continue
        if "submenu" in entry:
            yield from iter_items(entry["submenu"])
        else:
            yield entry


def all_items():
    seen = set()
    for tab in TABS:
        for grp in tab["groups"]:
            if id(grp) in seen:
                continue
            seen.add(id(grp))
            yield from iter_items(grp["items"])
    yield from iter_items(QUICK_ACCESS)
    yield from iter_items(NAV_BAR)
    yield from iter_items([e for e in MARKING_MENU if e["command"] != "__repeat__"])
    yield from iter_items(MARKING_LIST)


def find(grp, label):
    """The item (or submenu) with this label in a group, searching submenus too."""
    for entry in grp["items"]:
        if entry is SEP:
            continue
        if entry["label"] == label:
            return entry
        if "submenu" in entry:
            for inner in iter_items(entry["submenu"]):
                if inner["label"] == label:
                    return inner
    return None


def command_names(command):
    """All command names a slot may resolve to (without the #index suffix)."""
    if command is None:
        return ()
    names = (command,) if isinstance(command, str) else tuple(command)
    return tuple(n.split("#")[0] for n in names)
