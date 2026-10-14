# Parity spec: the MESH tab (outline 7.12, mesh basics)

Repair (and Make Closed Mesh), Remesh, Reduce, Smooth, Shell, Plane Cut, Separate, Combine,
Reverse Normal, Erase and Fill, Delete Faces, Generate Face Groups, Tessellate, Create Mesh
Section Sketch. Insert Mesh and Convert Mesh are in `parity/insert-export.md`. Copied behaviour
only, never Fusion's assets, wording or code. Status: **built and tested with real clicks (9
scenarios, 513 checks), not yet signed off by Luca.**

Every row says where its behaviour comes from:

- **Autodesk**: Autodesk's own help page, blog or API reference (read through search summaries
  on 2026-10-13; the help site itself is not reachable from the build sandbox).
- **Forum**: an Autodesk community forum answer (a user or an Autodesk employee).
- **Guess**: nothing found; SciForge's choice, to confirm in real Fusion.

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
| shared files | `timeline_core.py` (step kinds and icons), `timeline_ops.py` (step names, rename, pieces go with their step), `browser_core.py` / `browser_ui.py` (mesh steps in Bodies, the warning, right-click Repair, rename and delete of a mesh body's history), `insert.py` (a mesh step is a mesh body), `export.py` / `export_ui.py` (3D Print, Export, Export Everything take mesh bodies), `ribbon_config.py`, `tools/sciforge/make_icons.py` (14 icons) |

The ribbon: CREATE Insert Mesh, Tessellate, Create Mesh Section Sketch; PREPARE Generate Face
Groups, Repair; MODIFY Remesh, Reduce, Plane Cut, Shell, Smooth, Combine, Separate, Reverse
Normal, Erase and Fill, Delete Faces, Make Closed Mesh; CONVERT Convert Mesh.

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
| Smooth / Remesh / Reduce on face groups only | the whole body only | gap |
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
| Single faces (Direct Edit) | not built (see Direct Edit) | gap |
| Generate Face Groups: Fast (Angle Threshold 25 deg, Minimum Face Group Size 0.02) / Accurate (Boundary Tolerance 0.001), Preview | same rows and defaults; Fast grows groups across edges that bend less than the angle and folds groups smaller than the minimum into a neighbour; Accurate takes FreeCAD's plane / cylinder / sphere fitting first; each group drawn in its own colour; the dialog counts them | Autodesk |
| Create Face Group, Combine Face Groups | not built | gap |

### Erase and Fill, Delete Faces (Fusion: Direct Edit)

| Fusion | SciForge | Source |
|---|---|---|
| Inside Direct Edit (a mesh base feature, not in the parametric history) | MODIFY > Erase and Fill and Delete Faces are ordinary timeline steps (editable, one undo step) | Autodesk; deliberate difference (SciForge has no Direct Edit environment) |
| Faces picked with a paint brush (Mesh Selection Palette) | a click takes the faces within Brush Size around the clicked one (joined to it); Ctrl+click takes them off; Clear Faces; the picked faces are marked; picks are kept by their centres, so an edit earlier in the history keeps them where they still exist | Autodesk (brush); Guess (keys) |
| Erase and Fill Type Uniform (Density) / Minimal | same; only the holes the erase made are filled (holes the body had stay) | Autodesk |
| Delete: the faces removed, the hole stays | same (the browser then flags the hole; Repair or Erase and Fill close it) | Autodesk |
| Double-click a hole's rim to take the whole rim | not built | gap |

### Tessellate, Create Mesh Section Sketch (CREATE)

| Fusion | SciForge | Source |
|---|---|---|
| Tessellate a solid: Refinement Low / Medium / High / Custom, a changed value turns it Custom, the triangle count | same (the presets of SciForge's 3D Print); Custom with Surface Deviation, Normal Deviation, Maximum Edge Length; the count shown; one face group per face of the solid | Autodesk |
| The solid is converted on OK | the solid is used up (hidden, not listed); the mesh body takes its name; Ctrl+Z brings the solid back | Autodesk (blog) |
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
| Direct Edit environment (mesh base feature, Mesh Selection Palette, single-face Reverse Normal, rim double-click) | a whole environment; Erase and Fill and Delete Faces are timeline steps instead |
| Create Face Group, Combine Face Groups; Remesh / Reduce / Smooth / Separate on picked face groups only (except Separate's Select Face Groups and Reverse Normal) | face group picking exists only where listed above |
| Repair's OneTouchFix and the detailed analysis (thresholds, before / after table) | the dialog lists the problems before and after in one line each |
| The warning icon as a button that opens Repair | right-click > Repair instead |
| Rebuild types Adaptive and Adaptive Preserve Sharp Edges (newer Fusion API) | the four of the help page only |
| Tessellate's Aspect Ratio and Create Quads; Combine's New Component | FreeCAD's mesher has no aspect setting and no quads; no components here |
| Fusion's mesh-section curve and Fit Curves to Mesh Section | plain fixed lines instead |
| Mesh steps rolling back with the timeline marker | mesh bodies sit outside PartDesign bodies (as Insert Mesh already did) |
| Remesh / Reduce / Smooth results equal to Fusion's | different algorithms (FreeCAD's decimation and Taubin smoothing, SciForge's voxel rebuild); the rows, ranges and defaults are Fusion's, the faces they make are not |
| Big meshes | the voxel rebuild and the section are pure Python: a 500 000-face body takes seconds to minutes; the dialogs' Preview stays off until ticked (Fusion's way too) |
