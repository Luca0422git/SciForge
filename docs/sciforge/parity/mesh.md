# Parity spec: the MESH tab (outline 7.12, mesh basics)

Repair (and Make Closed Mesh), Remesh, Reduce, Smooth, Shell, Plane Cut, Separate, Combine,
Reverse Normal, Erase and Fill, Delete Faces, Generate Face Groups, Tessellate, Create Mesh
Section Sketch; since wave 5 (branch `sf/mesh-inspect-2`) also Direct Edit, Create Face Group,
Combine Face Groups, Smooth on face groups and mesh steps that roll back with the history
marker. Insert Mesh and Convert Mesh are in `parity/insert-export.md`. Copied behaviour only,
never Fusion's assets, wording or code. Status: **built and tested with real clicks (8 + 4
scenarios, 510 + 310 checks), not yet signed off by Luca.**

Every row says where its behaviour comes from:

- **Autodesk**: Autodesk's own help page, blog or API reference (read through search summaries
  on 2026-10-13 and 2026-10-16; the help site itself is not reachable from the build sandbox).
- **Forum**: an Autodesk community forum answer (a user or an Autodesk employee).
- **Guess**: nothing found; SciForge's choice, to confirm in real Fusion.

## Wave 5: Direct Edit, face groups, the history marker (behaviour spec, 2026-10-16)

Sources read (search excerpts): help "Edit a mesh body directly" (MESH-DIRECT-EDIT.htm), "Mesh
Selection Palette reference" (MESH-SELECTION-PALETTE.htm), "Create a face group from faces on
a mesh body" (MESH-CREATE-FACE-GROUP.htm), "Combine face groups on a mesh body"
(MESH-COMBINE-FACE-GROUPS.htm), "Reverse normal direction of faces", "Smooth a mesh body",
the Fusion keyboard shortcut guide (Direct Mesh Editing table), the blog "Mastering Mesh
Conversion" (face groups), Autodesk Community threads "How do we edit individual face groups
on a mesh?" (2025) and "Can't select faces on mesh body", the Autodesk Learn lesson "Generate
and edit face groups on a mesh body".

| Fusion | SciForge | Source |
|---|---|---|
| MODIFY > Direct Edit on a mesh body opens the Direct Mesh Editing environment (its own toolbar tab) | MESH > MODIFY > Direct Edit opens one dialog: the palette and the tools (no contextual tab: see gaps) | Autodesk |
| Direct Edit adds a mesh base feature to the timeline; the changes inside it are not separate features | one timeline step "Mesh Base Feature 1"; its edits are listed in the dialog, the timeline shows the one step | Autodesk |
| A copy of the mesh is the body after the base feature | the step is the body (same name), the step before it is used up, as every MESH step | Autodesk |
| The base feature keeps the mesh as edited | the step keeps its edits (one per line, the picked faces by their centres) and plays them again on the body as the step before leaves it, so an earlier change still reaches it (a picked face that is gone is reported: "N picked faces are gone") | deliberate difference (never loses a later edit of an earlier step); Guess |
| Edit Feature on the base feature (timeline or browser) re-enters Direct Edit | double-click the step in the timeline (or the body in the browser): the dialog opens with its edits listed | Autodesk |
| Finish Direct Editing (toolbar or palette) leaves the environment | Finish Direct Edit button (or OK, Enter); Cancel / Esc leave the body as it was; one undo step | Autodesk; Guess (Esc) |
| Finish with no edit | refused: "No edit yet: pick faces and Delete, Move, Smooth... them (or Cancel)" | Guess |
| The Mesh Selection Palette opens set to Paint | Selection: Paint (default), Window, Free Form | Autodesk |
| Paint: a brush whose size scales with the body | Brush Size (mm), 5 % of the body's size at first; a click or a drag paints the faces joined to the face under the pointer within the brush | Autodesk (brush); Guess (5 %, mm field instead of a slider) |
| Window and Free Form selection | Window: a box (left to right: faces wholly inside; right to left: faces it touches, as SciForge's box selection); Free Form: draw round the faces | Autodesk (types); Guess (crossing rule) |
| Filter Faces or Face Groups | Select: Faces / Face Groups (a pick takes whole face groups) | Autodesk |
| Select Back Faces (off: a face is taken only from its front) | same, off at first; off, a box or lasso takes only faces turned towards you and not hidden by the body | Autodesk; Guess (hidden faces left out) |
| Grow (Shift+Up), Shrink (Shift+Down), Invert (Alt+N), Expand To Face Group (Alt+G), Expand To Connected (Alt+C) | same buttons and keys (Grow / Shrink by one ring of faces sharing a corner) | Autodesk |
| Clicking empty canvas clears the selection | same (Clear button too); Ctrl takes faces off | Autodesk (clear); Guess (Ctrl) |
| Delete removes the picked faces | Delete (Del) | Autodesk |
| Erase and Fill (Direct Edit only) | Erase and Fill with Type Uniform / Minimal and Density, on the picked faces | Autodesk |
| Create Face Group: faces picked (joined or not) become one face group | Create Face Group: the picked faces become one new face group, shown in its colour | Autodesk |
| Reverse Normal of single faces in Direct Edit | Reverse Normal of the picked faces | Autodesk |
| Faces moved in Direct Edit (Move/Copy on the selected faces) | Move: an arrow on the picked faces, Direction Normal (their mean normal) / X / Y / Z and a Distance (typed or dragged, value box beside the arrow); the faces around stretch; Apply Move makes it an edit | Forum / tutorial (moving selected faces); Guess (arrow instead of Fusion's triad) |
| Smooth (selected faces or face groups) | Smooth of the picked faces with Smoothness (0..1, 0.02): their rim stays where it is | Autodesk (Smooth takes face groups); Guess (Laplace with a fixed rim for a region) |
| Undo inside the environment | Remove Last Edit takes the last edit back (Ctrl+Z cancels the whole dialog, as every SciForge dialog) | Guess |
| In parametric mode face groups are the smallest pick; single faces need Direct Edit | same: MODIFY tools pick whole bodies or face groups | Forum |
| PREPARE > Create Face Group (with the palette) | PREPARE > Create Face Group: also a timeline step of its own with the brush (as SciForge's Erase and Fill), besides the edit inside Direct Edit | Autodesk (in Direct Edit); deliberate (a step of its own) |
| PREPARE > Combine Face Groups: two or more face groups that share an edge become one; a timeline feature | same: click the groups (a click on a picked one drops it); groups that do not touch are refused: "These face groups do not touch: Combine Face Groups joins face groups that share an edge"; "Combine Face Groups 1" | Autodesk |
| Smooth of a mesh body or of face groups (MODIFY > Smooth) | Smooth has a Face Groups box (when the body has face groups): only those groups are smoothed, their rim stays | Autodesk |
| Features after the timeline marker are rolled back; a new feature goes in at the marker | every mesh step (Insert Mesh, Tessellate, Repair ... Direct Edit) rolls back: hidden, not in the browser, using nothing up, so the body shows as the step before it left it; a mesh step made there goes in at the marker and the body's later steps build on it; a design of mesh bodies only can have its marker anywhere | Autodesk (timeline) |

## Sources

## Sources

| Page | What it gave |
|---|---|
| help "Mesh creation" (Fusion-Mesh/files/MESH-CREATE-TOOLS.htm) | the CREATE tools: Insert Mesh (all faces in one face group), Tessellate (face groups made automatically), Create Face Group, Create Mesh Section Sketch (a sketch holding the line where a plane cuts the mesh; refined later with Fit Curves to Mesh Section) |
| help "Mesh preparation" (MESH-PREPARE-TOOLS.htm) | the PREPARE tools: Create Face Group, Generate Face Groups, Combine Face Groups, Repair |
| help "Mesh modification" (MESH-MODIFY-TOOLS.htm) | the MODIFY tools: Remesh, Reduce, Plane Cut, Shell, Combine (join / intersect / cut / merge, overlapping boundary edges stitched), Separate, Reverse Normal, Smooth, Direct Edit |
| help "MESH REPAIR" (MESH-REPAIR.htm) | Repair Type Close Holes (flipped triangles and holes, fastest), Stitch and Remove (+ stitch, double triangles, degenerate faces, tiny shells), Wrap (+ wraps the surface, inner structures destroyed), Rebuild (4 rebuild types, slowest); opened from PREPARE > Repair or the warning icon beside the body in the browser; the detailed analysis lists issues before and after |
| blog "Introducing the Mesh Repair Detailed Analysis Tool" (Jan 2022) | a bad mesh has a yellow warning icon in the browser, hovering it lists the problems; small-shell threshold slider |
| API `MeshRepairFeatureInput`, `MeshRepairTypes`, `MeshRepairRebuildTypes` | meshRepairType default **Stitch and Remove**; rebuild types Fast (default), Preserve Sharp Edges, Accurate, Blocky (newer: Adaptive, Adaptive Preserve Sharp Edges); density 8..256, default 128; offset (Accurate only), default 0; OneTouchFix type |
| blog (2016) on the mesh environment; forum "Make Closed Mesh" threads | "Rebuild as Solid" renamed "Make Closed Mesh"; it closes the holes of scans, with accuracy and offset settings; users report it loses detail |
| help "Remesh faces on a mesh body" (MESH-REMESH.htm), API `MeshRemeshFeatureInput` | Remesh Type Adaptive (small faces where the detail is) / Uniform (faces of a similar size); Density 0..1 (0.25); Shape Preservation 0..1 (0.5, Adaptive only); Preserve Sharp Edges, Preserve Boundaries (both off); Preview |
| help "Reduce faces on a mesh body" (MESH-REDUCE.htm), API `MeshReduceFeatureInput` | Reduce Target Tolerance (default; a maximum deviation in design units) / Proportion (percent of the faces kept) / Face Count; Reduce Type Adaptive (default) / Uniform, ignored for Tolerance; a mesh body or face groups; Preview |
| help "Smooth a mesh body" (MESH-SMOOTH.htm), API `MeshSmoothFeatureInput` | Smoothness 0 (least) .. 1 (most), API default 0.02; whole body or face groups; Preview |
| help "Shell a mesh body" (MESH-SHELL.htm) | the body, Thickness, Preview; hollows the inside (3D printing: less material and time); no Direction option on the mesh page |
| help "Trim or split a mesh body with a plane" (MESH-PLANE-CUT.htm); forum "Mesh body plane cut problem" | a body and a plane or planar face; distance / plane / rotation manipulators and Distance / angle fields; Type Trim / Split Body / Split Faces; Flip changes the side removed; Fill Type No Fill / Uniform / Minimal for Trim and Split Body; no Preview box (an Autodesk community manager agreed it should have one) |
| help "Separate a mesh body" (MESH-SEPARATE.htm), API `MeshSeparateFeatureInput` | Separate Type Mesh Shells / All Face Groups / Select Face Groups; Keep Body (default off); a Separate feature in the timeline |
| help "Combine mesh bodies" (MESH-COMBINE.htm), API `MeshCombineFeatureInput` | Target Body, Tool Bodies, Operation Join (default; inner structures removed) / Cut / Intersect / Merge (inner structures kept), Keep Tools (default off), New Component |
| help "Reverse normal direction of faces" (MESH-REVERSE-NORMAL.htm), API `MeshReverseNormalFeatureInput` | the faces of a whole body or of face groups (MODIFY), single faces in Direct Edit; a timeline feature |
| help "Erase and fill regions on a mesh body" (MESH-ERASE-FILL.htm); forum on its removed Weight option | Direct Edit only; Type Uniform (even faces, Density) / Minimal (fewest faces, long thin ones); double-click a face on a hole's rim takes the whole rim |
| help "Edit a mesh body directly" (MESH-DIRECT-EDIT.htm), "Mesh Selection Palette" | Direct Edit makes a mesh base feature; faces picked with a paint brush; Delete removes faces |
| help "MESH GENERATE FACE GROUPS", API `MeshGenerateFaceGroupsFeatureInput`, blog "Mastering Mesh Conversion" | Method Fast (Angle Threshold, API 0.436 rad = 25 deg; Minimum Face Group Size, 0.02 of the area) / Accurate (Boundary Tolerance, 0.001 of the largest size); a Generate Face Groups feature in the timeline |
| help "MESH TESSELLATE", API `TessellateFeatureInput`, blog "Convert solid body to mesh body" | Refinement High / Medium (default) / Low / Custom (Surface Deviation, Normal Deviation, Maximum Edge Length, Aspect Ratio; changing one turns it Custom); triangle count; Create Quads; the solid is converted to a mesh body on OK |
| help "Create a mesh section sketch" / "Fit curves to mesh sections" (Fusion-Sketch) | pick a mesh body and a plane, move the section; a sketch with the section line; Fit Curves to Mesh Section draws lines, arcs, splines over it; one sketch per section (forum) |

## How it is built

| File | What |
|---|---|
| `mesh_core.py` | no FreeCAD, no Qt (unit tested, 50 tests): Fusion's choices and defaults, the value mappings, open edges / holes / shells, the plane cut's 2D regions, face groups by angle, splitting long edges without cracks, welding open edges, hole filling, the voxel rebuild (Rebuild, Uniform remesh, Make Closed Mesh), the plane section, the brush |
| `mesh.py` | the document side: every MESH step is a `Mesh::FeaturePython` (proxy `MeshStep`, view `MeshStepView`) reading the body as the step before left it (`Source`); the newest step *is* the body (same name), the earlier ones are used up (hidden, not listed); pieces (`MeshPiece`) for Separate and Split Body; a step that cannot be done shows the body as it was and says why (timeline warning, dialog message); history, delete and rename of a whole mesh body |
| `mesh_ui.py` | Repair / Make Closed Mesh, Remesh, Reduce, Smooth, Shell, Reverse Normal, Separate, Combine, Generate Face Groups, Tessellate dialogs and commands |
| `mesh_cut_ui.py` | Plane Cut and Create Mesh Section Sketch (origin squares, the plane's arrow and turn handles, Distance / X Angle / Y Angle) |
| `mesh_pick_ui.py` | Erase and Fill and Delete Faces (the Faces box, Brush Size, marks on the picked faces) |
| `mesh_edit_core.py` (wave 5) | no FreeCAD, no Qt (unit tested, `test_mesh_edit_core.py`): Direct Edit's edits as text and how they are played again (delete, erase and fill, create face group, reverse, move, smooth a region with its rim fixed), the palette's Grow / Shrink / Invert / Expand To Face Group / Connected, faces facing the eye, faces inside a box or lasso, Combine Face Groups' "do they touch" rule, rims of gaps whose faces disagree on their winding |
| `mesh_direct_ui.py` (wave 5) | MODIFY > Direct Edit: the palette and the tools in one dialog; SciForge's own mouse handling on the 3D view while it picks faces (paint strokes, window box, free form lasso: rays through the body, FreeCAD's selection is not used), the environment's keys, the Move arrow with its value box, the list of edits |
| `mesh_groups_ui.py` (wave 5) | PREPARE > Create Face Group (brush) and Combine Face Groups (click the groups) |
| shared files | `timeline_core.py` (step kinds and icons), `timeline_ops.py` (step names, rename, pieces go with their step), `browser_core.py` / `browser_ui.py` (mesh steps in Bodies, the warning, right-click Repair, rename and delete of a mesh body's history), `insert.py` (a mesh step is a mesh body), `export.py` / `export_ui.py` (3D Print, Export, Export Everything take mesh bodies), `bodies.py` / `commands.py` (a body used up by a mesh step, a Tessellated solid, is no longer the active body nor picked for new work), `ribbon_config.py`, `tools/sciforge/make_icons.py` (14 icons; wave 5: 3 more) |
| shared files, wave 5 | `timeline_ops.py` (`is_mesh_step`, mesh steps roll back: `follow_mesh_steps` from `show_marker_state` and `settle`, flag `SciForgeRolledBack`), `timeline_core.py` (the marker without solid steps, the new kinds), `bodies.py` (`is_active_step`: a rolled-back step outside the bodies uses nothing up), `browser_ui.py` (rolled-back mesh steps are not listed), `insert.py` (Insert Mesh at a rolled-back marker goes in there), `mesh_ui.py` (`body_end`, a new step at the marker becomes what the later steps read, Smooth's Face Groups box) |

The ribbon: CREATE Insert Mesh, Tessellate, Create Mesh Section Sketch; PREPARE Create Face
Group, Generate Face Groups, Combine Face Groups, Repair; MODIFY Remesh, Reduce, Plane Cut,
Shell, Smooth, Combine, Separate, Reverse Normal, Direct Edit, Erase and Fill, Delete Faces,
Make Closed Mesh; CONVERT Convert Mesh.

## What the user does (and what SciForge does)

Common to every dialog (Fusion's pattern): the body box waits blue for a click on a mesh body
(one picked before the command is taken); OK adds one step to the timeline, one undo step;
Cancel or Esc leaves the body as it was; timeline double-click opens the step again with its
values; a step that cannot be done says why in the dialog and OK waits.

| Fusion | SciForge | Source |
|---|---|---|
| A mesh body that is not closed has a warning icon in the browser; hovering lists the problems | the browser row shows the warning; its tip lists holes, flipped faces, edges with more than two faces and says "right-click > Repair, or MESH > Repair" | Autodesk (blog) |
| Clicking the warning icon opens Repair | right-click the body > Repair (the icon is not a button yet) | Autodesk / gap |
| An inside-out body (every face pointing in) | flagged in the browser the same way ("Inside out: Reverse Normal or Repair") | Guess (useful for printing; FreeCAD's `Mesh.Volume` is never negative, so SciForge works out the signed volume itself) |
| Steps named after the tool in the timeline ("Repair 1"); the body keeps its name | same: the body keeps the file's name through every step; the timeline shows Repair 1, Remesh 1...; rename the body from the browser | Autodesk |
| A feature that fails stays in the timeline with a warning, the later ones go on | same: a step that cannot be done passes the body through and the timeline step shows the reason; deleting a step from the middle makes the next one read the step before (it may then fail and say why) | Autodesk (general timeline behaviour) |

### Repair (PREPARE > Repair)

| Fusion | SciForge | Source |
|---|---|---|
| Repair Type Close Holes / Stitch and Remove / Wrap / Rebuild, least to most invasive | same four; Close Holes: flipped faces turned and holes filled; Stitch and Remove: + doubled points and faces removed, cracks welded (within 1e-4 of the size), faces of no area and edges with more than two faces removed, tiny shells removed; Wrap: + inner shells and inside faces removed, self-crossings fixed; Rebuild: a new closed surface from a voxel model | Autodesk |
| Default Stitch and Remove | same | Autodesk (API) |
| Rebuild Type Fast / Preserve Sharp Edges / Accurate / Blocky, Density 8..256 (128), Offset (Accurate only) | same rows and defaults; Density = cells along the body's longest side; Fast is smoothed, Preserve Sharp Edges puts each corner on the crease, Accurate puts the corners on the original surface (and moves it out by Offset), Blocky leaves the cubes | Autodesk (API); the methods are SciForge's |
| The analysis before and after | "Before:" with the faces, size and problems; "After:" with the result and one plain sentence: closed (watertight), or "Not closed yet: try Wrap or Rebuild", or "This mesh cannot be repaired into a closed body (it may be a surface with no inside): try a higher Density, or Plane Cut away the broken part" | Autodesk (what); wording SciForge's |
| Preview | a Preview box, off at first (the body shows as it is until ticked) | Guess (Fusion's other slow mesh tools have one; forum) |
| Make Closed Mesh | MODIFY > Make Closed Mesh opens Repair with Rebuild / Accurate chosen | Forum (older name of the same job); Guess (which rebuild) |
| OneTouchFix (API), the detailed analysis's small-shell and degenerate thresholds | not built | gap |

### Remesh, Reduce, Smooth, Shell (MODIFY)

| Fusion | SciForge | Source |
|---|---|---|
| Remesh: Type Adaptive / Uniform, Density 0..1 (0.25), Shape Preservation (0.5, Adaptive), Preserve Sharp Edges, Preserve Boundaries, Preview | same rows and defaults. Density sets the edge length (a tenth of the diagonal at 0, a thousandth at 1: 0.25 is about 3 %); Adaptive splits long edges then decimates, smoothing by (1 - Shape Preservation); Uniform rebuilds a closed body from a voxel model (even triangles), an open one by splitting edges | Autodesk (rows); Guess (the mapping) |
| Reduce: Target Tolerance (default) / Proportion / Face Count; Reduce Type Adaptive / Uniform (not for Tolerance); Preview | same rows; Tolerance starts at 0.05 mm (Fusion's API starts at 0, which reduces nothing), Proportion at 50 %, Face Count at half the body's faces; Face Count gives exactly that many faces | Autodesk (rows); Guess (the starting values) |
| Reduce asks for more faces than the body has | refused: "ask for fewer"; OK waits | Guess |
| Smooth: Smoothness 0..1 (0.02), Preview | same; rounds of Taubin smoothing (keeps the volume, unlike plain averaging): 0.02 = 2 rounds, 1 = 60 | Autodesk (rows); Guess (the mapping) |
| Smooth / Remesh / Reduce on face groups only | Smooth: a Face Groups box (wave 5); Remesh and Reduce: the whole body only | Autodesk; gap (Remesh, Reduce) |
| Shell: Thickness, Preview | same; Thickness starts at 2 mm; the inside wall is the surface moved in by exactly the thickness (corners too), facing in; a wall that does not fit is refused with the most that fits ("under 2.50 mm"), one whose inside would cross itself too | Autodesk (rows); Guess (2 mm) |

### Plane Cut (MODIFY)

| Fusion | SciForge | Source |
|---|---|---|
| Pick the body, then a plane or planar face | same: the three origin squares show while the Plane box waits; a construction plane or a flat face can be clicked | Autodesk |
| Distance, angle fields and manipulators | Distance (an arrow to drag), X Angle and Y Angle (turn handles), like Section Analysis | Autodesk |
| Type Trim / Split Body / Split Faces; Flip | same; Trim keeps the side behind the plane's arrow, Flip keeps the other; Split Body makes two bodies "name" and "name (2)"; Split Faces cuts the faces along the plane and keeps one body | Autodesk |
| Fill Type No Fill / Uniform / Minimal | same: Minimal closes the cut with the fewest triangles, Uniform with even ones; holes and islands in the cut are kept (a ring cut gives a ring) | Autodesk; Guess (Uniform first) |
| A plane that misses the body | "The plane does not cut the body: it lies wholly on one side. Move the plane onto the body (drag the arrow or type a Distance)"; OK waits | Guess |
| No Preview box, the cut follows at once | same | Autodesk / Forum |

### Separate, Combine (MODIFY)

| Fusion | SciForge | Source |
|---|---|---|
| Separate Type Mesh Shells / All Face Groups / Select Face Groups; Keep Body (off) | same; the pieces appear at once ("name", "name (2)" ...), biggest first; Select Face Groups waits for clicks on the groups (picked groups first, the rest last); Keep Body leaves the body as well | Autodesk; Guess (names, order) |
| A body that is one shell | "The body is one shell: there is nothing to separate" (try face groups or Plane Cut > Split Body) | Guess |
| Combine: Target Body, Tool Bodies, Operation Join / Cut / Intersect / Merge, Keep Tools (off) | same; Join / Cut / Intersect with FreeCAD's mesh booleans, Merge puts the bodies together as they are; the tools are used up unless Keep Tools | Autodesk |
| Join needs closed bodies | refused for open bodies: "Join needs closed bodies: Repair them first (or use Merge, which keeps them as they are)"; Intersect of bodies that do not overlap and a Cut that leaves nothing are refused too | Guess (wording) |
| New Component | not offered (no components in this flow yet) | gap |

### Reverse Normal, Generate Face Groups (MODIFY / PREPARE)

| Fusion | SciForge | Source |
|---|---|---|
| Reverse Normal of the whole body or of face groups | same: without face groups every face turns at once; with face groups the Face Groups box waits for clicks ("All faces" when none picked) | Autodesk |
| Single faces (Direct Edit) | Direct Edit > Reverse Normal of the picked faces (wave 5) | Autodesk |
| Generate Face Groups: Fast (Angle Threshold 25 deg, Minimum Face Group Size 0.02) / Accurate (Boundary Tolerance 0.001), Preview | same rows and defaults; Fast grows groups across edges that bend less than the angle and folds groups smaller than the minimum into a neighbour; Accurate takes FreeCAD's plane / cylinder / sphere fitting first; each group drawn in its own colour; the dialog counts them | Autodesk |
| Create Face Group, Combine Face Groups | built (wave 5, see the spec at the top) | Autodesk |

### Erase and Fill, Delete Faces (Fusion: Direct Edit)

| Fusion | SciForge | Source |
|---|---|---|
| Inside Direct Edit (a mesh base feature, not in the parametric history) | in Direct Edit (wave 5), and also MODIFY > Erase and Fill and Delete Faces as ordinary timeline steps of their own (editable, one undo step), as before | Autodesk; deliberate (the steps of their own stay) |
| Faces picked with a paint brush (Mesh Selection Palette) | a click takes the faces within Brush Size around the clicked one (joined to it); Ctrl+click takes them off; Clear Faces; the picked faces are marked; picks are kept by their centres, so an edit earlier in the history keeps them where they still exist | Autodesk (brush); Guess (keys) |
| Erase and Fill Type Uniform (Density) / Minimal | same; only the holes the erase made are filled (holes the body had stay) | Autodesk |
| Delete: the faces removed, the hole stays | same (the browser then flags the hole; Repair or Erase and Fill close it) | Autodesk |
| Double-click a hole's rim to take the whole rim | not built | gap |

### Tessellate, Create Mesh Section Sketch (CREATE)

| Fusion | SciForge | Source |
|---|---|---|
| Tessellate a solid: Refinement Low / Medium / High / Custom, a changed value turns it Custom, the triangle count | same (the presets of SciForge's 3D Print); Custom with Surface Deviation, Normal Deviation, Maximum Edge Length; the count shown; one face group per face of the solid | Autodesk |
| The solid is converted on OK | the solid is used up (hidden, not listed, no longer the active body: a new sketch goes into a body that is shown, made if needed); the mesh body takes its name; Ctrl+Z brings the solid back | Autodesk (blog) |
| Aspect Ratio, Create Quads | not built (FreeCAD's mesher has no aspect setting; FreeCAD meshes are triangles) | gap |
| Create Mesh Section Sketch: the body, a plane, the section moved | same: the origin squares, Distance arrow; the section drawn over the part as you move it and counted; OK makes a sketch "Mesh Section name" on that plane with the section's lines, fixed (green) | Autodesk |
| Fusion's section is a special curve; Fit Curves to Mesh Section draws over it | SciForge's sketch holds plain fixed line segments (simplified within 0.02 % of the size), which a closed section can be extruded from straight away; no Fit Curves | gap |
| A plane that misses the body | the dialog says so; OK waits | Guess |
| The sketch needs no body | SciForge puts every sketch in a body: a design of mesh bodies only gets an empty "Body" for it | deliberate (SciForge's sketches live in bodies) |

### 3D Print, Export, Export Everything of mesh bodies

| Fusion | SciForge | Source |
|---|---|---|
| A mesh body can be 3D printed and saved as STL / 3MF / OBJ | same: the dialogs list mesh bodies beside solids; a mesh body is written with its own triangles (the refinement does not change it); 1000 mm3 in, 1000 mm3 out | Autodesk |
| STEP of a mesh body | refused: "STEP holds solid bodies only: convert the mesh bodies first (MESH > Convert Mesh), or export them as STL, 3MF or OBJ"; Export Everything of a design of mesh bodies only writes no STEP and its README names none | Guess (Fusion has no STEP of a mesh either) |

## Known gaps (never faked: listed here)

| Fusion behaviour | Why not (yet) |
|---|---|
| Direct Edit's own toolbar tab (the Direct Mesh Editing contextual tab) | the palette and the tools are one dialog; the ribbon keeps its tabs |
| Fusion's frozen mesh base feature | SciForge plays the edits again on the body as the step before leaves it (an earlier change reaches the Direct Edit; picks that are gone are reported) |
| Move with Fusion's Move/Copy triad (rotate, free move) | an arrow along the faces' normal or an axis, a Distance; no rotation |
| Undo of single edits inside Direct Edit with Ctrl+Z | Remove Last Edit; Ctrl+Z cancels the dialog as in every SciForge dialog |
| A hole's rim double-clicked to take the whole rim | not built (Expand To Connected / Grow help) |
| Remesh / Reduce / Separate on picked face groups (Separate's Select Face Groups, Reverse Normal and Smooth have them) | FreeCAD's remesh and decimation work on whole meshes |
| Display Mesh Face Groups (Shift+F) on / off | face groups are always drawn in their colours |
| Playback buttons over mesh steps (Previous / Next) | they step over the solid steps only; dragging the marker and Roll History Marker Here reach every mesh step |
| Repair's OneTouchFix and the detailed analysis (thresholds, before / after table) | the dialog lists the problems before and after in one line each |
| The warning icon as a button that opens Repair | right-click > Repair instead |
| Rebuild types Adaptive and Adaptive Preserve Sharp Edges (newer Fusion API) | the four of the help page only |
| Tessellate's Aspect Ratio and Create Quads; Combine's New Component | FreeCAD's mesher has no aspect setting and no quads; no components here |
| Fusion's mesh-section curve and Fit Curves to Mesh Section | plain fixed lines instead |
| Remesh / Reduce / Smooth results equal to Fusion's | different algorithms (FreeCAD's decimation and Taubin smoothing, SciForge's voxel rebuild); the rows, ranges and defaults are Fusion's, the faces they make are not |
| Big meshes | the voxel rebuild and the section are pure Python: a 500 000-face body takes seconds to minutes; the dialogs' Preview stays off until ticked (Fusion's way too) |
