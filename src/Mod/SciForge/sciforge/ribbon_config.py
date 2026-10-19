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


def item(label, command, icon=None, key="", note="", checked=None, toggle=None):
    """One menu entry. key = Fusion's shortcut, shown at the right of the menu.
    checked = "module:function" in the sciforge package that says whether the entry is the
    current choice (a tick in the menu, e.g. the orbit mode; the ticked entries of one menu
    are one exclusive choice). toggle = the same, for an entry that is on or off by itself
    (a selection filter): its tick does not untick the others."""
    entry = {"label": label, "command": command, "icon": icon, "key": key, "note": note}
    if checked:
        entry["checked"] = checked
    if toggle:
        entry["toggle"] = toggle
    return entry


def sub(label, items, icon=None, note=""):
    """A submenu (shown with a little arrow; in the navigation bar, a drop-down button)."""
    return {"label": label, "submenu": items, "icon": icon, "note": note}


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
        item(
            "Derive",
            "SciForge_Derive",
            "derive",
            note="Bodies, sketches, planes and parameters into another design, linked.",
        ),
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
        item("Rib", "SciForge_Rib", "rib"),
        item("Web", "SciForge_Web", "web"),
        item("Emboss", "SciForge_Emboss", "emboss"),
        item(
            "Text",
            "SciForge_FaceText",
            "sk_text",
            note="Click a face or plane and type; Finish Sketch, then Extrude or Emboss it.",
        ),
        SEP,
        item("Hole", ("SciForge_Hole", "PartDesign_Hole"), "hole", "H"),
        item("Thread", "SciForge_Thread", "thread"),
        SEP,
        item("Box", ("SciForge_Box", "PartDesign_CompPrimitiveAdditive#0"), "box"),
        item("Cylinder", ("SciForge_Cylinder", "PartDesign_CompPrimitiveAdditive#1"), "cylinder"),
        item("Sphere", ("SciForge_Sphere", "PartDesign_CompPrimitiveAdditive#2"), "sphere"),
        item("Torus", ("SciForge_Torus", "PartDesign_CompPrimitiveAdditive#5"), "torus"),
        item("Coil", ("SciForge_Coil", "PartDesign_AdditiveHelix"), "coil"),
        item("Gear", "SciForge_Gear", "gear"),
        item("Pipe", "SciForge_Pipe", "pipe"),
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
                item("Pattern on Path", "SciForge_PatternOnPath", "pattern_rect"),
            ],
        ),
        item("Mirror", ("SciForge_Mirror", "PartDesign_Mirrored"), "mirror"),
        SEP,
        item("Thicken", "SciForge_Thicken", "thicken"),
        item("Boundary Fill", "SciForge_BoundaryFill", "boundary_fill"),
        SEP,
        item(
            "Create Base Feature",
            "SciForge_CreateBaseFeature",
            "base_feature",
            note="Direct edits kept as one base feature per body, not as single steps.",
        ),
        item("Finish Base Feature", "SciForge_FinishBaseFeature", "finish_sketch"),
        item("Joint Origin", "SciForge_JointOrigin", "joint_origin"),
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
            note="Faces: push/pull. Edges: fillet. A fillet face: change its radius. "
            "Work in progress: complex shapes can be slow or give odd results.",
        ),
        item("Fillet", ("SciForge_Fillet", "PartDesign_Fillet"), "fillet", "F"),
        item("Chamfer", ("SciForge_Chamfer", "PartDesign_Chamfer"), "chamfer"),
        SEP,
        item("Shell", ("SciForge_Shell", "PartDesign_Thickness"), "shell"),
        item("Draft", ("SciForge_Draft", "PartDesign_Draft"), "draft"),
        item("Scale", "SciForge_Scale", "scale"),
        item("Combine", ("SciForge_Combine", "PartDesign_Boolean"), "combine"),
        item("Offset Face", "SciForge_OffsetFace", "offset_face"),
        item("Replace Face", "SciForge_ReplaceFace", "replace_face"),
        item("Split Face", "SciForge_SplitFace", "split_face"),
        item("Split Body", "SciForge_SplitBody", "split_body"),
        item("Silhouette Split", "SciForge_SilhouetteSplit", "silhouette_split"),
        SEP,
        item("Move/Copy", ("SciForge_Move", "Std_TransformManip"), "move", "M"),
        item("Align", "SciForge_Align", "align"),  # Fusion gives Align no key; A is Appearance
        item("Delete", ("SciForge_Delete", "Std_Delete"), "delete", "Del"),
        item("Remove", "SciForge_Remove", "remove"),
        SEP,
        item("Physical Material", ("SciForge_PhysicalMaterial", "Std_SetMaterial"), "material"),
        item("Appearance", ("SciForge_Appearance", "Std_SetAppearance"), "appearance", "A"),
        item(
            "Manage Materials",
            ("SciForge_ManageMaterials", "Material_Edit"),
            "material",
            note="The material libraries: Physical and Appearance, favourites, your own.",
        ),
        SEP,
        item("Change Parameters", "SciForge_ChangeParameters", "parameters"),
        item(
            "Compute All",
            ("SciForge_ComputeAll", "Std_Refresh"),
            "compute",
            "Ctrl+B",
            note="Every parameter and step computed again; the steps that fail are listed.",
        ),
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
        item("Plane Tangent to Face at Point", "SciForge_Construct_PlaneAtPoint", "tangent_plane"),
        item("Plane Through Two Edges", "SciForge_Construct_PlaneTwoEdges", "plane_two_edges"),
        item(
            "Plane Through Three Points",
            "SciForge_Construct_PlaneThreePoints",
            "plane_three_points",
        ),
        item("Plane Along Path", "SciForge_Construct_PlaneAlongPath", "plane_along_path"),
        SEP,
        item("Axis Through Cylinder/Cone/Torus", "SciForge_Construct_AxisCylinder", "axis"),
        item("Axis Perpendicular to Face at Point", "SciForge_Construct_AxisNormal", "axis"),
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
        item("Interference", "SciForge_Interference", "interference"),
        item("Curvature Comb Analysis", "SciForge_CurvatureCombAnalysis", "curvature"),
        item("Zebra Analysis", "SciForge_ZebraAnalysis", "zebra"),
        item("Draft Analysis", "SciForge_DraftAnalysis", "draft_analysis"),
        item("Curvature Map Analysis", "SciForge_CurvatureMapAnalysis", "curvature_map"),
        item("Isocurve Analysis", "SciForge_IsocurveAnalysis", "isocurve"),
        item("Accessibility Analysis", "SciForge_AccessibilityAnalysis", "accessibility"),
        item("Minimum Radius Analysis", "SciForge_MinimumRadiusAnalysis", "min_radius"),
        SEP,
        item(
            "Section Analysis",
            ("SciForge_SectionAnalysis", "Part_SectionCut", "Std_ToggleClipPlane"),
            "section",
        ),
        item("Center of Mass", "SciForge_CenterOfMass", "center_of_mass"),
        item(
            "Display Component Colors",
            "SciForge_ComponentColors",
            "component_colors",
            "Shift+N",
            toggle="component_colors_ui:is_on",
        ),
    ],
)

INSERT = group(
    "insert",
    "INSERT",
    ["Insert Component", "Canvas", "Insert Mesh"],
    [
        item("Decal", "SciForge_Decal", "decal", note="A picture on a face, flat or curved."),
        item("Canvas", "SciForge_InsertCanvas", "canvas", note="A reference image on a plane."),
        item("Insert SVG", "SciForge_InsertSVG", "insert_svg", note="SVG curves into a sketch."),
        item("Insert DXF", "SciForge_InsertDXF", "insert_dxf", note="DXF curves into a sketch."),
        item(
            "Insert Mesh",
            "SciForge_InsertMesh",
            "insert_mesh",
            note="An STL, OBJ or 3MF file as a mesh body.",
        ),
        SEP,
        item(
            "Insert Component",
            "SciForge_InsertDesign",
            "insert_component",
            note="Another design as a component linked to its file (Break Link: a copy)",
        ),
        item(
            "Insert Derive",
            "SciForge_InsertDerive",
            "derive",
            note="Bodies, sketches, planes and parameters of a saved design, linked.",
        ),
        # Fusion brings STEP files in through its Data Panel (upload, then Insert into the
        # design); SciForge has no cloud panel, so the file is picked straight away.
        item(
            "Insert STEP",
            "SciForge_InsertSTEP",
            "insert_step",
            note="A STEP or IGES file as a component: its parts, copies, names, colours.",
        ),
        SEP,
        item(
            "Hardware...",
            "SciForge_Hardware",
            "hardware",
            note="A real-size screw, nut, washer, heat-set insert or magnet, and its hole.",
        ),
    ],
)

ASSEMBLE = group(
    "assemble",
    "ASSEMBLE",
    ["New Component"],
    [
        item("New Component", ("SciForge_NewComponent", "Std_Part"), "new_component"),
        item(
            "Joint",
            "SciForge_Joint",
            "joint",
            "J",
            note="Click a snap point on each component; component 1 moves onto component 2.",
        ),
        item("As-built Joint", "SciForge_AsBuiltJoint", "joint_asbuilt"),
        item("Joint Origin", "SciForge_JointOrigin", "joint_origin"),
        item("Rigid Group", "SciForge_RigidGroup", "rigid_group"),
        SEP,
        item("Drive Joints", "SciForge_DriveJoints", "drive_joints"),
        item(
            "Motion Link",
            "SciForge_MotionLink",
            "motion_link",
            note="Tie two joints: when one moves, the other follows by a ratio (gear and rack).",
        ),
        SEP,
        # Fusion's contact choices: one of the three is on (joints_motion_ui.py)
        item(
            "Enable Contact Sets",
            "SciForge_EnableContactSets",
            "contact_set",
            checked="joints_motion_ui:contact_sets_on",
        ),
        item(
            "Enable All Contact",
            "SciForge_EnableAllContact",
            "contact_set",
            checked="joints_motion_ui:contact_all_on",
        ),
        item(
            "Disable Contact",
            "SciForge_DisableContact",
            "contact_set",
            checked="joints_motion_ui:contact_off",
        ),
        item("New Contact Set", "SciForge_NewContactSet", "contact_set"),
        SEP,
        item(
            "Motion Study",
            "SciForge_MotionStudy",
            "motion_study",
            note="Joint values at steps 0 to 100, played back.",
        ),
        SEP,
        # Fusion shows these in a POSITION panel that appears once a component was moved;
        # here they stay in the menu and are greyed while nothing moved (parity/joints.md).
        item("Capture Position", "SciForge_CapturePosition", "position"),
        item("Revert Position", "SciForge_RevertPosition", "position"),
    ],
)

# Fusion's SELECT menu (parity/selection.md): the select tool, the three box modes with
# their 1 / 2 / 3 keys, the filters (each on or off), the priorities (one at a time; the
# active one clicked again clears it), Select Other (also a long press on the model).
SELECT = group(
    "select",
    "SELECT",
    ["Select"],
    [
        item(
            "Select",
            "SciForge_Select",
            "select",
            note="Click to select; drag a box (left to right: fully inside, right to left: "
            "touched); hold the button on the model for Select Other",
        ),
        SEP,
        item(
            "Window Selection",
            "SciForge_SelectWindow",
            "select_window",
            "1",
            note="A box: left to right takes what is fully inside, right to left what it touches",
            checked="selection_ui:is_window",
        ),
        item(
            "Freeform Selection",
            "SciForge_SelectFreeform",
            "select_freeform",
            "2",
            note="A free shape drawn around things; the direction works like the box",
            checked="selection_ui:is_freeform",
        ),
        item(
            "Paint Selection",
            "SciForge_SelectPaint",
            "select_paint",
            "3",
            note="Drag over things: everything the pointer passes is selected",
            checked="selection_ui:is_paint",
        ),
        SEP,
        sub(
            "Selection Filters",
            [
                item(
                    "Select Through",
                    "SciForge_SelectThrough",
                    "select_through",
                    note="A box also takes what is hidden behind other faces",
                    toggle="selection_ui:is_select_through",
                ),
                SEP,
                item(
                    "Bodies",
                    "SciForge_SelectFilterBodies",
                    "select_body",
                    toggle="selection_ui:bodies_on",
                ),
                item(
                    "Body Faces",
                    "SciForge_SelectFilterFaces",
                    "select_face",
                    toggle="selection_ui:faces_on",
                ),
                item(
                    "Body Edges",
                    "SciForge_SelectFilterEdges",
                    "select_edge",
                    toggle="selection_ui:edges_on",
                ),
                item(
                    "Body Vertices",
                    "SciForge_SelectFilterVertices",
                    "select_vertex",
                    toggle="selection_ui:vertices_on",
                ),
                item(
                    "Sketch Curves",
                    "SciForge_SelectFilterSketchCurves",
                    "select_sketch",
                    toggle="selection_ui:sketch_curves_on",
                ),
                item(
                    "Sketch Points",
                    "SciForge_SelectFilterSketchPoints",
                    "select_sketch",
                    toggle="selection_ui:sketch_points_on",
                ),
                item(
                    "Work Geometry",
                    "SciForge_SelectFilterWorkGeometry",
                    "select_work",
                    toggle="selection_ui:work_geometry_on",
                ),
                item(
                    "Components", None, "new_component", note="Components are not in SciForge yet"
                ),
            ],
            "select_filter",
        ),
        sub(
            "Selection Priority",
            [
                item(
                    "Select Body Priority",
                    "SciForge_SelectPriorityBody",
                    "select_body",
                    note="Only whole bodies; the active priority clicked again clears the filter",
                    toggle="selection_ui:is_body_priority",
                ),
                item(
                    "Select Face Priority",
                    "SciForge_SelectPriorityFace",
                    "select_face",
                    note="Only faces of bodies",
                    toggle="selection_ui:is_face_priority",
                ),
                item(
                    "Select Edge Priority",
                    "SciForge_SelectPriorityEdge",
                    "select_edge",
                    note="Only edges of bodies",
                    toggle="selection_ui:is_edge_priority",
                ),
                item(
                    "Select Component Priority",
                    None,
                    "new_component",
                    note="Components are not in SciForge yet",
                ),
            ],
            "select_priority",
        ),
        SEP,
        item(
            "Select Other",
            "SciForge_SelectOther",
            "select_other",
            note="Everything under the pointer, front to back (or hold the left button there)",
        ),
        item("Select All", "Std_SelectAll", "select"),
        SEP,
        item(
            "Component Drag",
            "SciForge_ComponentDrag",
            "component_drag",
            note="Dragging a component moves it along its joints (untick: a drag draws a box)",
            toggle="joints_drag:enabled",
        ),
    ],
)

# ---------------------------------------------------------------- SURFACE tab
SURFACE_CREATE = group(
    "s_create",
    "CREATE",
    ["Extrude", "Loft", "Patch", "Thicken"],
    [
        # Fusion's SURFACE > CREATE (parity/surface.md): the surface versions of Extrude,
        # Revolve, Sweep, Loft; Patch, Ruled, Offset; Thicken and Boundary Fill at the end.
        item("Create Sketch", "SciForge_NewSketch", "sketch_create"),
        SEP,
        item("Extrude", "SciForge_SurfaceExtrude", "surface_extrude"),
        item("Revolve", "SciForge_SurfaceRevolve", "surface_revolve"),
        item("Sweep", "SciForge_SurfaceSweep", "surface_sweep"),
        item("Loft", "SciForge_SurfaceLoft", "surface_loft"),
        item("Patch", "SciForge_Patch", "patch"),
        item("Ruled", "SciForge_Ruled", "ruled"),
        item("Offset", "SciForge_SurfaceOffset", "surface_offset"),
        SEP,
        item("Thicken", "SciForge_Thicken", "thicken"),
        item("Boundary Fill", "SciForge_BoundaryFill", "boundary_fill"),
    ],
)
SURFACE_MODIFY = group(
    "s_modify",
    "MODIFY",
    ["Trim", "Extend", "Stitch"],
    [
        item("Trim", "SciForge_Trim", "trim"),
        item("Untrim", "SciForge_Untrim", "untrim"),
        item("Extend", "SciForge_SurfaceExtend", "surface_extend"),
        item("Stitch", "SciForge_Stitch", "stitch"),
        item("Unstitch", "SciForge_Unstitch", "unstitch"),
        item("Reverse Normal", "SciForge_ReverseNormal", "reverse_normal"),
        SEP,
        item("Replace Face", "SciForge_ReplaceFace", "replace_face"),
        item("Split Face", "SciForge_SplitFace", "split_face"),
        SEP,
        item("Delete", ("SciForge_Delete", "Std_Delete"), "delete", "Del"),
    ],
)

# ---------------------------------------------------------------- MESH tab
MESH_CREATE = group(
    "m_create",
    "CREATE",
    ["Insert Mesh", "Tessellate"],
    [
        item("Insert Mesh", "SciForge_InsertMesh", "insert_mesh"),
        item(
            "Tessellate",
            ("SciForge_MeshTessellate", "Mesh_FromPartShape"),
            "mesh_tessellate",
            note="A solid body into a mesh body, at a refinement; its faces become face groups.",
        ),
        item(
            "Create Mesh Section Sketch",
            "SciForge_MeshSectionSketch",
            "mesh_section",
            note="A sketch of where a plane cuts a mesh body.",
        ),
    ],
)
MESH_PREPARE = group(
    "m_prepare",
    "PREPARE",
    ["Generate Face Groups", "Repair"],
    [
        item(
            "Create Face Group",
            "SciForge_MeshCreateFaceGroup",
            "mesh_create_group",
            note="Faces you paint over become one face group.",
        ),
        item("Generate Face Groups", "SciForge_MeshFaceGroups", "mesh_face_groups"),
        item(
            "Combine Face Groups",
            "SciForge_MeshCombineFaceGroups",
            "mesh_combine_groups",
            note="Face groups that touch become one.",
        ),
        item(
            "Repair",
            ("SciForge_MeshRepair", "Mesh_Evaluation"),
            "mesh_repair",
            note="Close holes, turn flipped faces round, stitch cracks, or rebuild it closed.",
        ),
    ],
)
MESH_MODIFY = group(
    "m_modify",
    "MODIFY",
    ["Remesh", "Reduce", "Plane Cut"],
    [
        item("Remesh", ("SciForge_MeshRemesh", "Mesh_RemeshGmsh"), "mesh_remesh"),
        item("Reduce", ("SciForge_MeshReduce", "Mesh_Decimating"), "mesh_reduce"),
        item(
            "Plane Cut",
            ("SciForge_MeshPlaneCut", "Mesh_TrimByPlane"),
            "mesh_plane_cut",
            note="Trim or split a mesh body with a plane, the cut closed.",
        ),
        item("Shell", "SciForge_MeshShell", "mesh_shell"),
        item("Smooth", ("SciForge_MeshSmooth", "Mesh_Smoothing"), "mesh_smooth"),
        SEP,
        item("Combine", ("SciForge_MeshCombine", "Mesh_Union"), "mesh_combine"),
        item("Separate", ("SciForge_MeshSeparate", "Mesh_SplitComponents"), "mesh_separate"),
        item(
            "Reverse Normal",
            ("SciForge_MeshReverseNormal", "Mesh_FlipNormals"),
            "mesh_reverse_normal",
        ),
        item(
            "Direct Edit",
            "SciForge_MeshDirectEdit",
            "mesh_direct_edit",
            note="Pick single faces of a mesh body: delete, fill, group, turn, move, smooth.",
        ),
        SEP,
        item("Erase and Fill", "SciForge_MeshEraseFill", "mesh_erase_fill"),
        item("Delete Faces", "SciForge_MeshDeleteFaces", "mesh_delete_faces"),
        item(
            "Make Closed Mesh",
            "SciForge_MeshMakeClosed",
            "mesh_repair",
            note="Rebuild a closed (watertight) body from a broken mesh (Repair > Rebuild).",
        ),
    ],
)
MESH_CONVERT = group(
    "m_convert",
    "CONVERT",
    ["Convert Mesh"],
    [
        item(
            "Convert Mesh",
            ("SciForge_ConvertMesh", "Part_ShapeFromMesh"),
            "convert_mesh",
            note="A mesh body into a solid body: faceted, or prismatic (flat faces merged).",
        ),
    ],
)

# ---------------------------------------------------------------- UTILITIES tab
UTIL_MAKE = group(
    "u_make",
    "MAKE",
    ["3D Print", "Export"],
    [
        item(
            "3D Print",
            "SciForge_3DPrint",
            "print_3d",
            note="Send the bodies straight to your slicer (or save a 3MF / STL file).",
        ),
        item(
            "Export",
            ("SciForge_Export", "Std_Export"),
            "export",
            note="STEP with components, IGES, STL, 3MF, OBJ; a sketch as DXF.",
        ),
        item(
            "Export Everything",
            "SciForge_ExportEverything",
            "export_all",
            note="The whole design as STEP + STL + 3MF + a picture, in a folder beside it.",
        ),
    ],
)
UTIL_ADDINS = group(
    "u_addins",
    "ADD-INS",
    ["Scripts and Add-Ins"],
    [
        item(
            "Scripts and Add-Ins",
            ("SciForge_ScriptsAddIns", "Std_DlgMacroExecute"),
            "parameters",
            "Shift+S",
            note="Run, create and edit scripts and add-ins; Run on Startup.",
        ),
        item("Add-on Manager", "Std_AddonMgr", "new_component"),
    ],
)
UTIL_UTILITY = group(
    "u_utility",
    "UTILITY",
    ["Preferences"],
    [
        item(
            "Preferences",
            ("SciForge_Preferences", "Std_DlgPreferences"),
            "tl_settings",
            note="Navigation, units of new designs, design history, materials, graphics.",
        ),
        item(
            "Project and Recovery Settings",
            "SciForge_FilesSettings",
            "folder",
            note="Project folder, recovery copies, version descriptions, git",
        ),
        SEP,
        item("Version History", "SciForge_VersionHistory", "document"),
        item("Recover Documents", "SciForge_RecoverDocuments", "document"),
        item("Save As", "SciForge_SaveAs", "qa_save"),
        SEP,
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
        item("Midpoint Line", "SciForge_SketchMidpointLine", "sk_line"),
        sub(
            "Rectangle",
            [
                item("2-Point Rectangle", "Sketcher_CreateRectangle", "sk_rectangle", "R"),
                item("3-Point Rectangle", "SciForge_SketchRectangle3Point", "sk_rectangle"),
                item("Center Rectangle", "Sketcher_CreateRectangle_Center", "sk_rectangle"),
            ],
            "sk_rectangle",
        ),
        sub(
            "Circle",
            [
                item("Center Diameter Circle", "Sketcher_CreateCircle", "sk_circle", "C"),
                item("2-Point Circle", "SciForge_SketchCircle2Point", "sk_circle"),
                item("3-Point Circle", "Sketcher_Create3PointCircle", "sk_circle"),
                item("2-Tangent Circle", "SciForge_SketchCircle2Tangent", "sk_circle"),
                item("3-Tangent Circle", "SciForge_SketchCircle3Tangent", "sk_circle"),
            ],
            "sk_circle",
        ),
        sub(
            "Arc",
            [
                item("3-Point Arc", "Sketcher_Create3PointArc", "sk_arc"),
                item("Center Point Arc", "Sketcher_CreateArc", "sk_arc"),
                item("Tangent Arc", "SciForge_SketchTangentArc", "sk_arc"),
            ],
            "sk_arc",
        ),
        sub(
            "Polygon",
            [
                item("Circumscribed Polygon", "SciForge_PolygonCircumscribed", "sk_polygon"),
                item("Inscribed Polygon", "SciForge_PolygonInscribed", "sk_polygon"),
                item("Edge Polygon", "SciForge_SketchPolygonEdge", "sk_polygon"),
            ],
            "sk_polygon",
        ),
        item("Ellipse", "Sketcher_CreateEllipseByCenter", "sk_ellipse"),
        sub(
            "Slot",
            [
                item(
                    "Center to Center Slot",
                    ("SciForge_SketchSlotCenter", "Sketcher_CreateSlot"),
                    "sk_slot",
                ),
                item("Overall Slot", "SciForge_SketchSlotOverall", "sk_slot"),
                item("Center Point Slot", "SciForge_SketchSlotCenterPoint", "sk_slot"),
                item("Three Point Arc Slot", "SciForge_SketchSlotArc3Point", "sk_slot"),
                item("Center Point Arc Slot", "Sketcher_CreateArcSlot", "sk_slot"),
            ],
            "sk_slot",
        ),
        sub(
            "Spline",
            [
                item(
                    "Fit Point Spline",
                    ("SciForge_SketchFitSpline", "Sketcher_CreateBSplineByInterpolation"),
                    "sk_spline",
                ),
                item("Control Point Spline", "Sketcher_CreateBSpline", "sk_spline"),
            ],
            "sk_spline",
        ),
        item("Conic Curve", "SciForge_SketchConic", "sk_conic"),
        item("Point", "Sketcher_CreatePoint", "sk_point"),
        item("Text", "SciForge_SketchText", "sk_text"),
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
                item("Project to Surface", "SciForge_SketchProjectToSurface", "sk_project"),
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
        item("Fillet", ("SciForge_SketchFillet", "Sketcher_CreateFillet"), "sk_fillet"),
        item("Chamfer", ("SciForge_SketchChamfer", "Sketcher_CreateChamfer"), "sk_chamfer"),
        item("Offset", "SciForge_SketchOffset", "sk_offset", "O"),
        item("Trim", ("SciForge_SketchTrim", "Sketcher_Trimming"), "sk_trim", "T"),
        item("Extend", ("SciForge_SketchExtend", "Sketcher_Extend"), "sk_extend"),
        item("Break", ("SciForge_SketchBreak", "Sketcher_Split"), "sk_break"),
        item("Sketch Scale", "SciForge_SketchScale", "sk_scale"),
        item("Move/Copy", "SciForge_SketchMove", "sk_move", "M"),
    ],
)
SKETCH_CONSTRAINTS = group(
    "k_constraints",
    "CONSTRAINTS",
    ["Fix/Unfix", "Coincident", "Tangent", "Equal", "Parallel", "Perpendicular"],
    [
        item("Coincident", "SciForge_SketchCoincident", "c_coincident"),
        item("Collinear", "SciForge_SketchCollinear", "c_collinear"),
        item("Concentric", "SciForge_SketchConcentric", "c_concentric"),
        item("Midpoint", "SciForge_SketchMidpoint", "c_midpoint"),
        item("Fix/Unfix", "SciForge_SketchFix", "c_fix"),
        item("Parallel", "SciForge_SketchParallel", "c_parallel"),
        item("Perpendicular", "SciForge_SketchPerpendicular", "c_perpendicular"),
        item("Horizontal/Vertical", "SciForge_SketchHorizontalVertical", "c_horizontal"),
        item("Tangent", "SciForge_SketchTangent", "c_tangent"),
        item("Curvature", "SciForge_SketchCurvature", "c_smooth"),
        item("Equal", "SciForge_SketchEqual", "c_equal"),
        item("Symmetry", "SciForge_SketchSymmetry", "c_symmetric"),
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

# ---------------------------------------------------------------- DRAWING tab (contextual)
# Fusion's DRAWING workspace toolbar (Autodesk "Drawing workspace reference"); it shows
# while a drawing's tab is the active one (drawing_ui.py), like the SKETCH tab.
DRAWING_CREATE = group(
    "d_create",
    "CREATE",
    ["Base View", "Projected View", "Section View", "Detail View"],
    [
        item(
            "Base View",
            "SciForge_DrawingBaseView",
            "dw_base_view",
            note="The first view of the design: orientation, style and scale; click to place it.",
        ),
        item(
            "Projected View",
            "SciForge_DrawingProjectedView",
            "dw_projected_view",
            note="Move round the base view and click: top, side and isometric views.",
        ),
        item(
            "Section View",
            "SciForge_DrawingSectionView",
            "dw_section_view",
            note="Click a view, draw the cut line with two clicks, then place the section.",
        ),
        item(
            "Detail View",
            "SciForge_DrawingDetailView",
            "dw_detail_view",
            note="Click the centre and the size of a circle on a view, then place it larger.",
        ),
        item(
            "Break View",
            "SciForge_DrawingBreakView",
            "dw_break_view",
            note="Click a long view, then the two ends of the part to leave out.",
        ),
        SEP,
        item(
            "Breakout Section View",
            "SciForge_DrawingBreakoutView",
            "dw_section_view",
            note="Click a view, then a closed boundary around what should show inside.",
        ),
        item("Exploded View", None, "dw_base_view"),
    ],
)
DRAWING_MODIFY = group(
    "d_modify",
    "MODIFY",
    ["Delete"],
    [
        item(
            "Edit View", "SciForge_DrawingEditView", "dw_base_view", note="Or double-click a view"
        ),
        item(
            "Title Block",
            "SciForge_DrawingTitleBlock",
            "dw_title_block",
            note="Or double-click the title block",
        ),
        SEP,
        item("Move", None, "move", note="Drag a view by its frame on the sheet"),
        item("Rotate", None, "move"),
        item("Delete", "SciForge_DrawingDelete", "delete", "Del"),
    ],
)
DRAWING_GEOMETRY = group(
    "d_geometry",
    "GEOMETRY",
    ["Center Mark", "Centerline"],
    [
        item("Centerline", "SciForge_DrawingCenterline", "dw_centerline"),
        item("Center Mark", "SciForge_DrawingCenterMark", "dw_center_mark"),
        item("Center Mark Pattern", None, "dw_center_mark"),
        item(
            "Edge Extension",
            "SciForge_DrawingEdgeExtension",
            "dw_centerline",
            note="Click two edges: they reach to where they would meet (a rounded corner).",
        ),
    ],
)
DRAWING_DIMENSIONS = group(
    "d_dimensions",
    "DIMENSIONS",
    ["Dimension"],
    [
        item(
            "Dimension",
            "SciForge_DrawingDimension",
            "dw_dimension",
            "D",
            note="Pick an edge, a circle or two things; the right kind of dimension follows.",
        ),
        SEP,
        item("Linear Dimension", "SciForge_DrawingLinearDimension", "dw_dimension"),
        item("Aligned Dimension", "SciForge_DrawingAlignedDimension", "dw_dimension"),
        item("Angular Dimension", "SciForge_DrawingAngularDimension", "dw_dimension"),
        item("Radius Dimension", "SciForge_DrawingRadiusDimension", "dw_dimension"),
        item("Diameter Dimension", "SciForge_DrawingDiameterDimension", "dw_dimension"),
        item("Arc Length Dimension", "SciForge_DrawingArcLengthDimension", "dw_dimension"),
        SEP,
        item(
            "Ordinate Dimension",
            "SciForge_DrawingOrdinateDimension",
            "dw_dimension",
            note="Click the origin, then each point and where its value goes.",
        ),
        item(
            "Baseline Dimension",
            "SciForge_DrawingBaselineDimension",
            "dw_dimension",
            note="Click a dimension, then more points: each one from the same start.",
        ),
        item(
            "Chain Dimension",
            "SciForge_DrawingChainDimension",
            "dw_dimension",
            note="Click a dimension, then more points: each one from the point before.",
        ),
        SEP,
        item(
            "Edit Dimension",
            "SciForge_DrawingEditDimension",
            "dw_dimension",
            note="Or double-click a dimension: text, tolerance, fits, basic, reference.",
        ),
    ],
)
DRAWING_TEXT = group(
    "d_text",
    "TEXT",
    ["Text"],
    [
        item("Text", "SciForge_DrawingText", "dw_text", note="Click two corners, then type."),
        item(
            "Leader",
            "SciForge_DrawingLeader",
            "dw_text",
            note="Click an edge, then where the text goes; type the text.",
        ),
        item("Note", None, "dw_text"),
    ],
)
DRAWING_SYMBOLS = group(
    "d_symbols",
    "SYMBOLS",
    ["Surface Texture"],
    [
        item("Surface Texture", "SciForge_DrawingSurfaceTexture", "dw_symbol"),
        item(
            "Feature Control Frame",
            "SciForge_DrawingFeatureControlFrame",
            "dw_symbol",
            note="GD&T: characteristic, tolerance and datums; click an edge, then the place.",
        ),
        item("Datum Identifier", "SciForge_DrawingDatumIdentifier", "dw_symbol"),
    ],
)
DRAWING_TABLES = group(
    "d_tables",
    "TABLES",
    ["Table", "Balloon"],
    [
        item(
            "Table",
            "SciForge_DrawingTable",
            "dw_table",
            note="A parts list of the components a view shows, with balloons.",
        ),
        item(
            "Balloon",
            "SciForge_DrawingBalloon",
            "dw_balloon",
            note="Click a component on a view, then where the balloon goes.",
        ),
        item("Renumber", None, "dw_balloon"),
        item("Align Balloons", None, "dw_balloon"),
    ],
)
DRAWING_EXPORT = group(
    "d_export",
    "EXPORT",
    ["Export PDF", "Export DXF"],
    [
        item("Export PDF", "SciForge_DrawingExportPDF", "dw_export_pdf"),
        item("Export DXF", "SciForge_DrawingExportDXF", "dw_export_dxf"),
        item("Export DWG", None, "export"),
        item("Export CSV", None, "export"),
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
    {
        "id": "drawing",
        "title": "DRAWING",
        "contextual": True,
        "groups": [
            DRAWING_CREATE,
            DRAWING_MODIFY,
            DRAWING_GEOMETRY,
            DRAWING_DIMENSIONS,
            DRAWING_TEXT,
            DRAWING_SYMBOLS,
            DRAWING_TABLES,
            DRAWING_EXPORT,
        ],
    },
]

# Fusion's File menu (the application menu), in its order; cloud-only entries (upload,
# share, recover documents) are left out. Shown first by the quick-access Menu button,
# above FreeCAD's own menus (ribbon_ui).
# Fusion's File menu (the app bar's Menu button opens it, FreeCAD's own menus below).
FILE_MENU = [
    item("New Design", "SciForge_NewDesign", "qa_new", "Ctrl+N"),
    item(
        "New Drawing",
        "SciForge_NewDrawing",
        "dw_new",
        note="From Design: views of this design on a sheet",
    ),
    item("Open", ("SciForge_Open", "Std_Open"), "qa_open", "Ctrl+O"),
    item("Recover Documents", "SciForge_RecoverDocuments", "document"),
    SEP,
    item("Save", ("SciForge_Save", "Std_Save"), "qa_save", "Ctrl+S"),
    item("Save As", ("SciForge_SaveAs", "Std_SaveAs"), "qa_save"),
    item("Version History", "SciForge_VersionHistory", "document"),
    SEP,
    item("Export", ("SciForge_Export", "Std_Export"), "export"),
    item("3D Print", "SciForge_3DPrint", "print_3d"),
    item("Export Everything", "SciForge_ExportEverything", "export_all"),
    item("Capture Image", ("SciForge_CaptureImage", "Std_ViewScreenShot"), "canvas"),
    SEP,
    item("Insert Mesh", "SciForge_InsertMesh", "insert_mesh"),
    item("Insert STEP", "SciForge_InsertSTEP", "insert_step"),
    item("Insert SVG", "SciForge_InsertSVG", "insert_svg"),
    item("Insert DXF", "SciForge_InsertDXF", "insert_dxf"),
    item("Canvas", "SciForge_InsertCanvas", "canvas"),
    item("Insert Design", "SciForge_InsertDesign", "insert_component"),
    SEP,
    item("Project and Recovery Settings", "SciForge_FilesSettings", "folder"),
]

# Quick-access buttons at the top left, like Fusion's application bar.
QUICK_ACCESS = [
    item(
        "Data Panel",
        "SciForge_DataPanel",
        "folder",
        "Ctrl+Alt+P",
        note="The project folder's designs with thumbnails (Fusion's Data Panel)",
    ),
    item("Menu", "__menu__", "qa_menu", note="All FreeCAD menus"),
    item("New", "Std_New", "qa_new", "Ctrl+N"),
    item("Open", ("SciForge_Open", "Std_Open"), "qa_open", "Ctrl+O"),
    item(
        "Save",
        ("SciForge_Save", "Std_Save"),
        "qa_save",
        "Ctrl+S",
        note="Every save is a version: v1, v2, ... with a description",
    ),
    item("Undo", "Std_Undo", "qa_undo", "Ctrl+Z"),
    item("Redo", "Std_Redo", "qa_redo", "Ctrl+Y"),
]

# Navigation bar floating at the bottom centre of the 3D view. Orbit is a drop-down with
# Fusion's two orbit modes (the tick shows the current one; orbit_ui.py).
NAV_BAR = [
    sub(
        "Orbit",
        [
            item(
                "Constrained Orbit",
                "SciForge_OrbitConstrained",
                "nav_orbit",
                note="Turns about the up axis and tilts; never rolls",
                checked="orbit_ui:is_constrained",
            ),
            item(
                "Free Orbit",
                "SciForge_OrbitFree",
                "nav_orbit",
                note="Tumbles in any direction, rolling included",
                checked="orbit_ui:is_free",
            ),
        ],
        "nav_orbit",
        note="Shift + middle mouse button",
    ),
    item("Look At", "Std_AlignToSelection", "nav_lookat"),
    item("Pan", "SciForge_Pan", "nav_pan", note="Drag to move the view (or the middle button)"),
    sub(
        "Zoom",
        [
            item("Zoom", "SciForge_Zoom", "nav_zoom", note="Drag up or down (or the wheel)"),
            item("Zoom Window", "SciForge_ZoomWindow", "nav_zoom_window"),
        ],
        "nav_zoom",
    ),
    item("Fit", "Std_ViewFitAll", "nav_fit", "F6"),
    sub(
        "Display Settings",
        [
            sub(
                "Visual Style",
                [
                    item(
                        "Shaded",
                        "SciForge_StyleShaded",
                        "nav_display",
                        checked="display_ui:is_shaded",
                    ),
                    item(
                        "Shaded with Hidden Edges",
                        "SciForge_StyleShadedHidden",
                        "nav_display",
                        checked="display_ui:is_shaded_hidden",
                    ),
                    item(
                        "Shaded with Visible Edges Only",
                        "SciForge_StyleShadedVisible",
                        "nav_display",
                        checked="display_ui:is_shaded_visible",
                    ),
                    item(
                        "Wireframe",
                        "SciForge_StyleWireframe",
                        "nav_display",
                        checked="display_ui:is_wireframe",
                    ),
                    item(
                        "Wireframe with Hidden Edges",
                        "SciForge_StyleWireframeHidden",
                        "nav_display",
                        checked="display_ui:is_wireframe_hidden",
                    ),
                    item(
                        "Wireframe with Visible Edges Only",
                        "SciForge_StyleWireframeVisible",
                        "nav_display",
                        checked="display_ui:is_wireframe_visible",
                    ),
                ],
                "nav_display",
            ),
            sub(
                "Environment",
                [
                    item("Theme", "SciForge_EnvTheme", None, checked="display_ui:is_env_theme"),
                    item(
                        "Photo Booth",
                        "SciForge_EnvPhotoBooth",
                        None,
                        checked="display_ui:is_env_photo_booth",
                    ),
                    item(
                        "Grey Room",
                        "SciForge_EnvGreyRoom",
                        None,
                        checked="display_ui:is_env_grey_room",
                    ),
                    item(
                        "Dark Sky",
                        "SciForge_EnvDarkSky",
                        None,
                        checked="display_ui:is_env_dark_sky",
                    ),
                    item(
                        "Infinity Pool",
                        "SciForge_EnvInfinityPool",
                        None,
                        checked="display_ui:is_env_infinity_pool",
                    ),
                    item(
                        "Tranquility Blue",
                        "SciForge_EnvTranquilityBlue",
                        None,
                        checked="display_ui:is_env_tranquility_blue",
                    ),
                    item(
                        "Warm Light",
                        "SciForge_EnvWarmLight",
                        None,
                        checked="display_ui:is_env_warm_light",
                    ),
                ],
                "nav_display",
            ),
            sub(
                "Effects",
                [
                    item(
                        "Ground Shadow",
                        "SciForge_GroundShadow",
                        None,
                        toggle="display_ui:ground_shadow_on",
                    ),
                    item(
                        "Ground Plane",
                        "SciForge_GroundPlane",
                        None,
                        toggle="display_ui:ground_plane_on",
                    ),
                    item(
                        "Ambient Occlusion",
                        None,
                        None,
                        note="Not available: FreeCAD's 3D view has no ambient occlusion",
                    ),
                    item(
                        "Reflections",
                        None,
                        None,
                        note="Not available: FreeCAD's 3D view draws no reflections",
                    ),
                ],
                "nav_display",
            ),
            sub(
                "Object Visibility",
                [
                    item(
                        "Show All", "SciForge_ShowAllObjects", None, toggle="display_ui:all_shown"
                    ),
                    SEP,
                    item(
                        "Origins", "SciForge_ShowOrigins", None, toggle="display_ui:shows_origins"
                    ),
                    item(
                        "Analysis",
                        "SciForge_ShowAnalysis",
                        None,
                        toggle="display_ui:shows_analysis",
                    ),
                    item("Joints", "SciForge_ShowJoints", None, toggle="display_ui:shows_joints"),
                    item(
                        "Joint Origins",
                        "SciForge_ShowJointOrigins",
                        None,
                        toggle="display_ui:shows_joint_origins",
                    ),
                    item(
                        "Sketches",
                        "SciForge_ShowSketches",
                        None,
                        toggle="display_ui:shows_sketches",
                    ),
                    item(
                        "Construction Planes",
                        "SciForge_ShowConstructionPlanes",
                        None,
                        toggle="display_ui:shows_planes",
                    ),
                    item(
                        "Construction Axes",
                        "SciForge_ShowConstructionAxes",
                        None,
                        toggle="display_ui:shows_axes",
                    ),
                    item(
                        "Construction Points",
                        "SciForge_ShowConstructionPoints",
                        None,
                        toggle="display_ui:shows_points",
                    ),
                    item(
                        "Canvases",
                        "SciForge_ShowCanvases",
                        None,
                        toggle="display_ui:shows_canvases",
                    ),
                    item(
                        "Mesh Bodies",
                        "SciForge_ShowMeshBodies",
                        None,
                        toggle="display_ui:shows_meshes",
                    ),
                ],
                "nav_display",
            ),
            sub(
                "Camera",
                [
                    item(
                        "Orthographic",
                        "SciForge_CameraOrthographic",
                        None,
                        checked="display_ui:is_orthographic",
                    ),
                    item(
                        "Perspective",
                        "SciForge_CameraPerspective",
                        None,
                        checked="display_ui:is_perspective",
                    ),
                    item(
                        "Perspective with Ortho Faces",
                        "SciForge_CameraOrthoFaces",
                        None,
                        checked="display_ui:is_ortho_faces",
                    ),
                ],
                "nav_display",
            ),
            item("Ground Plane Offset", "SciForge_GroundPlaneOffset", "nav_display"),
        ],
        "nav_display",
    ),
    sub(
        "Grid and Snaps",
        [
            item("Layout Grid", "SciForge_LayoutGrid", "nav_grid", toggle="grid_ui:layout_grid_on"),
            item(
                "Layout Grid Lock",
                "SciForge_LayoutGridLock",
                "nav_grid",
                toggle="grid_ui:grid_locked",
            ),
            item("Snap to Grid", "SciForge_SnapToGrid", "grid_snap", toggle="grid_ui:snap_on"),
            item("Grid Settings", "SciForge_GridSettings", "nav_grid"),
            SEP,
            item(
                "Incremental Move",
                "SciForge_IncrementalMove",
                "increment",
                toggle="grid_ui:incremental_on",
            ),
            item("Set Increments", "SciForge_SetIncrements", "increment"),
        ],
        "nav_grid",
    ),
    sub(
        "Viewports",
        [
            item(
                "Single View",
                "SciForge_ViewportSingle",
                "view_single",
                checked="viewports_ui:is_single",
            ),
            item(
                "Two Views Horizontal",
                "SciForge_ViewportTwoHorizontal",
                "view_two_h",
                checked="viewports_ui:is_two_h",
            ),
            item(
                "Two Views Vertical",
                "SciForge_ViewportTwoVertical",
                "view_two_v",
                checked="viewports_ui:is_two_v",
            ),
            item(
                "Multiple Views",
                "SciForge_ViewportMultiple",
                "nav_viewports",
                "Shift+1",
                checked="viewports_ui:is_multiple",
            ),
        ],
        "nav_viewports",
    ),
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
    SEP,
    item("Set Orbit Center", "SciForge_SetOrbitCenter", "orbit_center"),
    item("Reset Orbit Center", "SciForge_ResetOrbitCenter", "orbit_center"),
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
