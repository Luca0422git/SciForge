# Parity spec: Insert, import, export, make (outline 7.12)

Insert Mesh, Convert Mesh, Insert STEP, Insert SVG, Insert DXF, Canvas (Insert / Edit /
Calibrate), Export, 3D Print, Export Everything. Copied behaviour only, never Fusion's assets,
wording or code. Status: **built and tested with real clicks (9 scenarios, 320 checks), not yet
signed off by Luca**. Every choice marked **(assumed)** is a guess to confirm in real Fusion.

Code (all in `src/Mod/SciForge/sciforge/`):

| File | What |
|---|---|
| `insert.py` | no Qt: mesh units / flip / centre / ground maths, mesh bodies (`Mesh::Feature`), `ConvertMeshFeature` (a `PartDesign::FeaturePython` step), STEP into bodies, SVG / DXF curves into sketch geometry (fixed), canvases (`Image::ImagePlane`), calibrate maths |
| `insert_ui.py` | the dialogs: Insert Mesh (with the move manipulator), Convert Mesh, Insert SVG / DXF, Canvas / Edit Canvas, Calibrate; the Insert STEP command; browser hooks |
| `export.py` | no Qt: refinement presets, mesh writing (STL binary / ASCII, 3MF with body names, OBJ with groups), STEP writing, Export Everything's file plan and README |
| `export_ui.py` | the Export dialog, the 3D Print dialog, the Export Everything command |
| `ribbon_config.py` | INSERT group, MESH tab (Insert Mesh, Convert Mesh), UTILITIES > MAKE (3D Print, Export, Export Everything), `FILE_MENU` (the quick-access Menu's File entries) |
| `browser_core.py` / `browser_ui.py` | mesh bodies in the Bodies folder, the Canvases folder, right-click entries (Convert Mesh, Edit Canvas, Calibrate) |
| `timeline_core.py` | the step kinds Insert Mesh, Convert Mesh, Insert STEP |

Tests: scenarios `insert_mesh.py` (Insert Mesh + Convert Mesh, 65 checks), `insert_step.py`
(22), `insert_svg.py` (38), `insert_dxf.py` (35), `insert_canvas.py` (48), `export_formats.py`
(53), `export_print.py` (41), `export_everything.py` (27), `insert_reopen.py` (save / reopen with
a mesh, a converted body and a canvas, 24); unit tests `test_insert_core.py`,
`test_export_core.py`; fixtures in `SciForgeTests/fixtures/` (made by `make_fixtures.py`).

## Sources

Autodesk's public help and support pages (read through search summaries on 2026-10-13; the
help site itself is not reachable from the build sandbox), community answers where the help
says nothing, and the Fusion API reference for defaults:

- Insert Mesh: help "MESH INSERT MESH" (Fusion-Mesh/files/MESH-INSERT-MESH.htm): Unit Type
  (centimeter, millimeter, meter, inch, foot), Flip Up Direction ("flips the direction of the Y
  and Z axes"), Center, Move to Ground, X / Y / Z and angle values, manipulators, "the contents
  of the file displays as a mesh body in the canvas and the Browser, in the Bodies folder of
  the active component", "A Mesh Base Feature displays in the Timeline"; support article "How
  to insert a mesh body into Fusion" (STL and OBJ are unitless); API `MeshUnits` enumeration
  (the unit order).
- Convert Mesh: help "MESH CONVERT TO SOLID": Operation Parametric ("a Convert Mesh feature
  displays in the Timeline") / Base Feature; Method Faceted ("individual faces on the mesh body
  to individual faces on the new solid"), Prismatic ("merges groups of faces in prismatic
  features into singular faces"), Organic (extension only); Autodesk blog "Converting a Mesh
  into a Solid Body in Autodesk Fusion".
- Insert canvas: help "Insert canvas (image)" (SLD-INSERT-CANVAS.htm) and "Canvas reference":
  Insert > Canvas, choose the image, select a face or plane; Canvas Opacity, Display Through
  ("lets the image show through objects that are in front of it"), Selectable, X Distance,
  Y Distance, Z Angle, Scale X, Scale Y, Scale Plane XY, Horizontal Flip, Vertical Flip;
  "Calibrate canvas (image)" (SLD-SCALE-CANVAS.htm): browser > Canvases > right-click the image
  > Calibrate, select two points, type the distance, Enter; Autodesk forum reply (QA engineer):
  the defaults became 50 % opacity and Display Through on; Autodesk engineer on the default
  size: the image is scaled "to the size of its target plane", approximate by design.
- Insert SVG: help "Add an SVG image" (SLD-INS-SVG.htm) and the Insert SVG reference: a planar
  face (or the active sketch), X / Y Distance ("positive Y moves geometry below the origin"),
  Z Angle, Scale, Horizontal / Vertical Flip; the geometry is fixed after OK (Product Design
  Online); forum threads on pixel units (96 px per inch).
- Insert DXF: help "Insert a DXF file" (SLD-INS-DXF.htm) and its reference: a planar face,
  Units ("if the DXF has no units information, the design's units are used"), Insert Mode
  Single Sketch / One Sketch per Layer, X / Y Distance, DXF Layers (all ticked), "the DXF
  origin is placed at the sketch origin", an active sketch is used in Single Sketch mode.
- Export: support article "How to export a CAD design from Fusion" (File > Export, Type,
  Location, Export) and "Supported file formats" (STEP, STL, 3MF, OBJ, IGES, SAT, SMT, F3D,
  DWG, DXF, FBX, USD); help "Save bodies in a component as 3MF, OBJ, or STL files" (Save As
  Mesh: Format 3MF / STL Binary / STL ASCII / OBJ, Unit Type, Structure One File / One File Per
  Body, Refinement Low / Medium / High / Custom, Surface Deviation, Normal Deviation, Maximum
  Edge Length, Aspect Ratio, Preview Mesh, Number of Triangles).
- 3D Print: help "3D print a design" (SLD-3D-PRINT.htm): Utilities > Make > 3D Print,
  Selection, Preparation Type Export (Manufacturing goes to the Manufacture workspace), Format,
  Refinement Settings, Send to 3D Print Utility; API `STLExportOptions` (the default
  refinement is Medium; Surface Deviation = the greatest distance between the true surface and
  the triangles, Normal Deviation = the greatest angle between neighbouring triangle normals).
- Fusion inserts STEP files through its Data Panel (upload, then Insert into Current Design,
  which opens a Move dialog) or opens them as a design: SciForge has no cloud panel, so
  **Insert STEP** picks the file at once (support article "How to insert a mesh body" for the
  Insert menu's shape; the components doc for where the bodies go, once components exist).

## What gets built

| Tool | Built as |
|---|---|
| Insert Mesh | a `Mesh::Feature` at document level (SciForgeType `InsertMesh`), its triangles in design units, Z up; Placement = the dialog's position and angles; `SourceFile`, `UnitType`, `FlipUp`, `UnitScale` remembered so the step can be edited without the file |
| Convert Mesh | a new body whose first step is SciForge's `ConvertMesh` feature (`Source` = the mesh body, `Method`, `Parametric`, `Tolerance`); Parametric rebuilds from the mesh when it moves or changes, Base Feature keeps the solid it made |
| Insert STEP | one `PartDesign::Body` per solid of the file (FreeCAD's `BaseFeature` step, marked `InsertSTEP`), named after the file's parts, its colours as a SciForge Appearance (per face when the part has several); the file's containers, origins and links are removed again |
| Insert SVG / DXF | sketch geometry (lines, circles, arcs, ellipses, splines) added to a sketch with a `Block` constraint each (fixed, green), made from FreeCAD's `importSVG` / `importDXF` run in a throw-away hidden document; the dialog's X / Y / angle / scale / flips are applied to the geometry itself (never OpenCASCADE's shape transform, which turns everything into B-splines) |
| Canvas | an `Image::ImagePlane` (SciForgeType `Canvas`, kept out of the timeline) with the picture inside the design file (FreeCAD's `ImageFile` keeps a copy), `PlaneFrame` = the plane it sits on, `BaseWidth` / `BaseHeight`, `ScaleX` / `ScaleY`, `XDistance`, `YDistance`, `ZAngle`, `FlipHorizontal`, `FlipVertical`, `CanvasOpacity`, `DisplayThrough`; opacity = the view's Transparency, Display Through = the image drawn as a Coin annotation (after everything else, no depth test), Selectable = the view's Selectable |
| Export (meshes) | FreeCAD's mesher with Surface Deviation (linear deflection, mm) and Normal Deviation (angular deflection); STL = one mesh (the union), 3MF and OBJ = one object per body with its name (the 3MF object names and unit are written by SciForge, FreeCAD leaves them out) |
| Export (STEP) | FreeCAD's `ImportGui.export` (names and colours) |
| Export Everything | `<design folder>/<name>-export/` with `<name>.step`, `.stl`, `.3mf`, `.obj` (Medium refinement), `.png` (the 3D view, 1600 x 1200) and `README.txt` saying what each file is |

## What the user does (and what SciForge does)

### Insert Mesh (INSERT > Insert Mesh; MESH tab > Insert Mesh)

| Fusion | SciForge |
|---|---|
| Pick an STL / OBJ / 3MF file | same (the system file dialog; the folder is remembered) |
| The mesh body appears at once in the Bodies folder, "Insert Mesh" in the timeline | same: the Bodies folder lists it with a mesh icon, named after the file; the timeline step is "Insert Mesh N" (its tooltip) shown with the file's name |
| Unit Type: Centimeter, Millimeter, Meter, Inch, Foot; Fusion starts at Centimeter (forum: STLs came in ten times too big until Millimeter was chosen) | same choices, same order; **SciForge starts at the design's unit** (Millimeter for a mm design), a deliberate difference: slicer STLs are in mm, and the ten-times-too-big insert is a known Fusion annoyance (Luca to confirm he wants it this way); a change re-scales the triangles |
| Flip Up Direction: Y and Z swapped (a Y-up file turned Z-up) | same: 90 degrees about X, as a check box **(assumed: Fusion's is a button)** |
| Center: the box's middle to the origin; Move to Ground: the lowest point on Z = 0 | same |
| X / Y / Z Distance and Angle fields, manipulator arrows and turn handles, Reset | same: the Move manipulator (three arrows, three turn handles, drawn on top), the fields follow a drag and a drag follows the fields; turns are about the mesh's middle **(assumed)** |
| OK keeps the mesh body; Cancel removes it; Ctrl+Z / Ctrl+Y | same, one undo step |
| Edit Feature on the timeline step | timeline double-click opens the dialog again (unit, flip, position); Cancel puts everything back |
| the number of triangles | shown in the dialog with the size in mm and a note when the mesh is not watertight |

### Convert Mesh (MESH tab > Convert Mesh; right-click a mesh body in the browser)

| Fusion | SciForge |
|---|---|
| Body: a mesh body (click it) | same; the dialog waits with its box blue; a mesh body picked before the command, or the browser's right-click entry, fills it |
| Operation: Parametric / Base Feature | same (Parametric follows the mesh body: move the mesh, the solid follows, also after save and reopen) |
| Method: Faceted / Prismatic / Organic | Faceted (one flat face per triangle) and Prismatic (flat faces merged: a box becomes 6 faces, a cylinder's sides stay faceted: FreeCAD fits no curved surfaces); Organic not offered (Fusion: extension only) |
| Live preview; the converted body in the Bodies folder, "Convert Mesh" in the timeline | same; the new body is named "<mesh> (solid)" and becomes the active body |
| A warning for big meshes | above 10 000 triangles the dialog says the conversion can take a while **(the limit is Fusion's; what it says is SciForge's)** |
| Not watertight: cannot convert | the dialog says so and points at MESH > Repair; OK waits |
| The mesh body afterwards | hidden (its eye off) **(assumed)**; Ctrl+Z shows it again |

### Insert STEP (INSERT > Insert STEP; File menu)

| Fusion | SciForge |
|---|---|
| Upload the STEP to the Data Panel, then Insert into Current Design (a Move dialog opens) | pick the file; the bodies appear at once, selected (press M to move them) **(SciForge's own: no cloud panel)** |
| One body per STEP solid, the parts' names, colours | same (per-face colours kept when a part has several); the browser lists the bodies; the timeline shows "Insert STEP N" per body |
| The STEP's component structure | flattened to bodies (no components yet: `parity/components.md` once it exists) |
| A second insert of the same file | the new bodies are "Plate (2)", "Peg (2)" |
| Ctrl+Z | removes the bodies; Ctrl+Y brings them back with their colours |

### Insert SVG / Insert DXF (INSERT menu; File menu)

| Fusion | SciForge |
|---|---|
| Pick the file, then a planar face or plane (an active sketch is used) | same: the origin squares light up like Create Sketch, flat faces can be clicked; a sketch that is open gets the curves (the sketch is closed while the dialog runs and opened again on OK or Cancel) |
| The curves appear in a sketch at the sketch origin | same; the SVG's origin at the sketch origin, Y of the file pointing down (as FreeCAD reads SVG and as Fusion's Y Distance says) |
| X Distance, Y Distance, Z Angle, Scale Plane XY, Horizontal Flip, Vertical Flip, manipulators | the fields (live); no manipulator yet (gap) |
| DXF: Units (the file's, or a unit the file's numbers count in), Insert Mode Single Sketch / One Sketch per Layer, DXF Layers ticked | same; "As in the file" takes FreeCAD's reading of $INSUNITS; per-layer sketches are named "<file> <layer>" |
| The geometry is fixed after OK | same: a Block constraint on every curve (green = fixed in SciForge's sketches) |
| OK: the sketch is the active sketch | the sketch opens for editing (Finish Sketch, or E to extrude it) |
| Pixel SVGs come in small (96 px per inch) | same as FreeCAD reads them; Scale fixes it (Fusion users type 0.3528 or 96 in the same case) |
| FreeCAD's own DXF import dialog | kept off during the import (SciForge's dialog holds the choices); the user's setting is put back |

### Canvas (INSERT > Canvas; browser > Canvases)

| Fusion | SciForge |
|---|---|
| Pick the image (PNG, JPEG, BMP, GIF, TIFF), then a face or plane | same |
| The image is sized "to the target plane" (approximate), centred on the face / plane origin | the longer side 1.3 x the design's longest dimension (the origin squares' size), 100 mm in an empty design, centred on the face's centre (a plane: its origin); the picture keeps its proportions |
| Canvas Opacity (50 %), Display Through (on), Selectable, Horizontal / Vertical Flip, X / Y Distance, Z Angle, Scale X / Y / Plane XY | same fields, same defaults; Display Through draws the image over everything in front of it; a flip turns the picture over (the image plane shows both sides) |
| Canvases folder in the browser, eye, rename, delete; not in the timeline | same **(not in the timeline: assumed)** |
| Right-click > Edit Canvas | same (also a double-click on the row); Cancel puts the values back |
| Right-click > Calibrate: two points, the distance, Enter | same: the dialog says which point to click, draws the two points and the line, shows the picked distance in the field; type the real distance, Enter (or OK): the canvas scales about its centre **(about which point Fusion scales: assumed)**; the clicks land on screen pixels, so the result is within about 0.1 mm |
| Save, reopen: the canvas is there | same, the picture is inside the design file (FreeCAD keeps a copy); Display Through and opacity are put back when a design opens |

### Export (UTILITIES > MAKE > Export; File menu > Export)

| Fusion | SciForge |
|---|---|
| File > Export: Name, Type, Location, Export | the Export dialog: Export (Whole design / Selected bodies with a ticked list), Type (STEP, STL Binary, STL ASCII, 3MF, OBJ), Name, Location (…), "Open the folder afterwards", Export |
| Mesh types from Save As Mesh: Unit Type, Structure One File / One File Per Body, Refinement Low / Medium / High / Custom, Surface Deviation, Normal Deviation, Number of Triangles | same rows (shown for mesh types; greyed for STEP); the count follows the refinement |
| Formats SciForge does not write | IGES, SAT, SMT, F3D, DWG, DXF, FBX, USD (FreeCAD could do IGES and DXF; not offered yet) |
| A body with no solid | left out of the list; "Whole design" exports the shown bodies **(hidden bodies left out: assumed)** |

### 3D Print (UTILITIES > MAKE > 3D Print; File menu)

| Fusion | SciForge |
|---|---|
| Selection: bodies | the bodies list, ticked from the selection (else all shown bodies) |
| Preparation Type Export; Format 3MF / STL (Binary) / STL (ASCII) / OBJ | the formats (Manufacturing left out: no CAM) |
| Refinement Low / Medium / High / Custom with Surface Deviation, Normal Deviation (Maximum Edge Length, Aspect Ratio), Preview Mesh, Number of Triangles | Low = 0.127 mm / 30 deg, Medium = 0.0508 mm / 15 deg, High = 0.0254 mm / 10 deg **(the numbers Fusion shows for a mm design, from memory: thousandths of an inch; unconfirmed)**, Custom takes the two fields; Number of Triangles; no Maximum Edge Length / Aspect Ratio (FreeCAD's mesher has no such settings) and no Preview Mesh overlay (gaps) |
| Send to 3D Print Utility (the slicer), or a file | same: tick it and name the slicer program once (remembered), OK writes a temporary 3MF / STL and starts the slicer with it; unticked, OK asks where to save and opens the folder |

### Export Everything (UTILITIES > MAKE; File menu)

Luca's ownership guarantee (outline 5.6): one command writes the whole design to open formats.
Beside a saved design `Bracket.FCStd` it makes `Bracket-export/` with `Bracket.step`,
`Bracket.stl`, `Bracket.3mf`, `Bracket.obj`, `Bracket.png` and `README.txt`, then opens the
folder. A design never saved asks for a folder first. An empty design says there is nothing to
export. Fusion has no such command (its nearest is File > Export, one format at a time).

## Known gaps (never faked: listed here)

| Fusion behaviour | Why not (yet) |
|---|---|
| Insert Derive, Insert McMaster-Carr, Decal, Insert Component | out of scope / components first |
| STEP into a component, Fusion's Move dialog after an insert | no components yet; the bodies are selected so M moves them |
| Insert SVG / DXF manipulators (move, turn, scale on the plane) | fields only |
| Convert Mesh "Organic", surface fitting of round faces (Prismatic keeps them faceted) | FreeCAD has no mesh-to-surface fitting |
| Mesh repair, remesh, reduce (MESH tab PREPARE) | FreeCAD's own Mesh commands are wired in the MESH tab, not Fusion-styled yet |
| Export: IGES, SAT, SMT, F3D, DWG, DXF, FBX, USD | not offered; FreeCAD could write IGES / DXF |
| 3D Print: Maximum Edge Length, Aspect Ratio, Preview Mesh overlay, Manufacturing preparation | FreeCAD's mesher has no edge length / aspect settings; no CAM |
| The exact refinement numbers of Low / Medium / High | from memory of Fusion's dialog, to confirm |
| An inserted mesh in the timeline rolls back with the marker | mesh bodies sit outside the PartDesign bodies, so the history marker never hides them |
| Canvas: Fusion's manipulators on the image, "Render as" options | the fields only |
| FreeCAD's SVG importer skips text and gradients; a `<circle>` with stroke attributes came in at twice its position in one FreeCAD build | FreeCAD's importer; the fixture avoids stroke attributes, real files may need a path-based circle |
