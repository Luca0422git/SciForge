# Parity spec: Insert, import, export, make (outline 7.12)

Insert Mesh, Convert Mesh, Insert STEP, Insert SVG, Insert DXF, Canvas (Insert / Edit /
Calibrate), Export, 3D Print, Export Everything. The rest of the MESH tab (Repair, Remesh,
Reduce, Plane Cut...) is in `parity/mesh.md`. Copied behaviour only, never Fusion's assets,
wording or code. Status: **built and tested with real clicks (9 scenarios, 320 checks; Part 2 below: 5
more, 329 checks), not yet signed off by Luca**. Every choice marked **(assumed)** is a guess to confirm in real Fusion.

Code (all in `src/Mod/SciForge/sciforge/`):

| File | What |
|---|---|
| `insert.py` | no Qt: mesh units / flip / centre / ground maths, mesh bodies (`Mesh::Feature`), `ConvertMeshFeature` (a `PartDesign::FeaturePython` step), STEP into bodies, SVG / DXF curves into sketch geometry (fixed), canvases (`Image::ImagePlane`), calibrate maths |
| `insert_ui.py` | the dialogs: Insert Mesh (with the move manipulator), Convert Mesh, Insert SVG / DXF, Canvas / Edit Canvas, Calibrate; the Insert STEP command; browser hooks |
| `export.py` | no Qt: refinement presets, mesh writing (STL binary / ASCII, 3MF with body names, OBJ with groups), STEP writing, Export Everything's file plan and README |
| `export_ui.py` | the Export dialog, the 3D Print dialog (Send to Slicer), the Export Everything command |
| `slicer_core.py` | no Qt / FreeCAD: finding the slicers (Windows, Linux, macOS rules), the Send to list, the command line, units and file names (unit tests `test_slicer_core.py`) |
| `ribbon_config.py` | INSERT group, MESH tab (Insert Mesh, Convert Mesh), UTILITIES > MAKE (3D Print, Export, Export Everything), `FILE_MENU` (the quick-access Menu's File entries) |
| `browser_core.py` / `browser_ui.py` | mesh bodies in the Bodies folder, the Canvases folder, right-click entries (Convert Mesh, Edit Canvas, Calibrate) |
| `timeline_core.py` | the step kinds Insert Mesh, Convert Mesh, Insert STEP |

Tests: scenarios `insert_mesh.py` (Insert Mesh + Convert Mesh, 65 checks), `insert_step.py`
(22), `insert_svg.py` (38), `insert_dxf.py` (35), `insert_canvas.py` (48), `export_formats.py`
(53), `export_print.py` (41), `send_to_slicer.py` (106: fake slicers, no slicer found, Other..., Save a copy, Cancel, Preferences > 3D Print), `export_everything.py` (27), `insert_reopen.py` (save / reopen with
a mesh, a converted body and a canvas, 24); unit tests `test_insert_core.py`,
`test_export_core.py`; fixtures in `SciForgeTests/fixtures/` (made by `make_fixtures.py`).

## Part 2 (exchange-2, 2026-10-16): structure in and out, manipulators, linked designs

Built in `src/Mod/SciForge/sciforge/`: `exchange_core.py` (no FreeCAD: file kinds, how a
file's tree becomes components and bodies, how a design is written so it reads back the
same; unit tested in `test_exchange_core.py`), `step_import.py` (STEP / IGES with their
structure), `exchange.py` (STEP with components, IGES, DXF of a sketch or flat face, DWG
through a converter, meshes in a component's frame), `design_insert.py` (Insert into
Current Design as a linked component, Break Link), `exchange_ui.py` (File > Open, Insert
STEP's flow, Save As DXF, Save As Mesh, Break Link), the manipulator (`_PlaneHandles`) in
`insert_ui.py`, the Export dialog in `export_ui.py`, the Data Panel's Upload in
`versions_ui.py`. Scenarios `exchange2_step_open` (80 checks), `exchange2_step_insert`
(75), `exchange2_export` (89), `exchange2_manip` (43), `exchange2_link` (42); the earlier
`insert_step`, `insert_svg` and `versions_link` follow the new behaviour.

### Behaviour spec (sources: Autodesk = Autodesk help / support / blog; Forum = Autodesk
Community answer; Guess = no source found, to check in real Fusion)

| Fusion | Source | SciForge |
|---|---|---|
| A STEP file keeps its component structure and names ("STEP (.stp) files retain component structure and names") | Autodesk (handout "Fusion 360 Large Model Management"); Forum ("STEP files imported into Fusion create components"; a round trip Fusion > STEP > Fusion keeps the structure) | Same: every product of the file is a component named after it, nested as in the file |
| SAT files "will place all components into a flattened structure" | Autodesk (same handout) | SAT is refused: FreeCAD cannot read ACIS (the message says to save STEP in the other program) |
| IGES comes in as bodies (no assemblies in IGES) | Guess (IGES has no product structure) | The solids as bodies; a file of loose faces is sewn: closed shells become solids, open ones surface bodies |
| A part used several times comes in once, the others as copies ("Wheel:1", "Wheel:2") | Guess (Fusion's occurrence naming from Copy / Paste, parity/components.md) | Same: the second occurrence is a linked copy (instances.py), "Wheel:2"; the browser shows "Wheel:1" for the original |
| A part's solids are the component's bodies, numbered Body1, Body2 ... | Guess (Fusion numbers bodies per component) | Same; a single part opened on its own is a body of the design named after the part |
| File > Open of a STEP file (Fusion: Upload, then the translated design opens) | Autodesk (support "How to insert / open DXF files"; Data Panel Upload) | File > Open (Ctrl+O; the application menu) takes designs, STEP and IGES; a STEP / IGES file becomes a new, unsaved design named after the file (Ctrl+S then asks where to keep it) |
| Upload in the Data Panel | Autodesk (Data Panel pages) | The Data Panel's **Upload** copies a STEP / IGES file into the folder shown; double-click opens it as a design; right-click > Insert into Current Design |
| Insert into Current Design: "inserted as an external component and the Initial Position dialog displays"; "position the component by dragging manipulators in the canvas or by entering Distance and Angle values"; "An Insert feature displays in the Timeline" | Autodesk (help "Insert designs", ASM-INSERT-FUSION-DESIGN) | Insert STEP: the whole file is one component named after the file, in the active component, one undo step; then the Move dialog opens on it (arrows and Distance / Angle fields); Esc leaves it where it came in (**Guess**: Esc in Fusion's Initial Position) |
| The inserted design is "associatively linked to the source design"; when the source changes, it is out of date and can be brought up to date | Autodesk (help "Insert designs created in other CAD applications": Out-Of-Date icon) | Insert Component (Insert Design, the Data Panel's Insert into Current Design) of a SciForge design: one component named after it, linked to its file by a relative path; its bodies are copies of the other design's bodies; when the other design was saved again, the copies are brought up to date as the design opens (no out-of-date icon: they follow at once) |
| Right-click > Break Link: "Your component now becomes a stand-alone part, and you're free to edit its features within your current file" | Autodesk (blog "Insert Into Current Design ... Break Link") | Same: the other design's bodies are copied in with every feature (their steps join the timeline), one undo step; refused with the reason when the other design is not found |
| File > Export types: Fusion archive, Inventor, DWG, DXF, FBX, IGES, OBJ, SAT, SketchUp, SMT, STEP, STL (newer help: 3MF, USDZ) | Autodesk (support "How to export a CAD design from Fusion"; help "Export designs") | Type: STEP, IGES, STL (Binary), STL (ASCII), 3MF, OBJ, DXF, DWG; Export: Whole design, Selected bodies or **A component** (a list of the components) |
| STEP export keeps the structure (round trip) | Forum (the round-trip test above) | Each component is a product (a component with bodies only is a part named after it; with components in it, an assembly holding them and a part of its name for its bodies); a copy of a component is a second occurrence of the same product; colours kept. Opened again: the same components, copies, bodies, places and colours (`exchange2_export` P1) |
| Save As Mesh of a component: "the selected component defines the coordinate system"; "only visible bodies are exported"; Structure One File / One Body Per File | Forum (Autodesk employee); Autodesk (help "Save bodies in a component as 3MF, OBJ, or STL files") | Export > A component (or right-click a component or body > **Save As Mesh**, which opens the Export dialog on it with 3MF): the shown bodies of the component and its components, in the component's own coordinates; One File / One File Per Body as before |
| Right-click a sketch > Save As DXF: "this method will include only the geometry in that individual sketch"; "If your design doesn't include a sketch, the Save As DXF option is disabled" | Autodesk (support "How to export a Fusion design to a DWG or DXF file"); SendCutSend guide | Same entry in the browser's sketch menu: the sketch's curves in the sketch's own X / Y (whatever plane it is on), mm ($INSUNITS 4); construction lines are left out (**Guess**) |
| DXF of a flat face | Guess (Fusion: project the face into a sketch, then Save As DXF) | Export, Type DXF, with a flat face picked (or Use Selection): its edges in the face's own frame, the origin at its middle |
| DWG of a design ("DWG and DXF export a wireframe") | Autodesk (export list); the content is not documented | DWG is written only through a free converter (LibreDWG's dxf2dwg, the ODA File Converter or QCAD, found the way FreeCAD finds them); without one, Export refuses and names them. This machine has none, so the DWG path is untested |
| Insert SVG: "the manipulator handles allow you to move, rotate, and scale the SVG image on the active sketch plane"; "the image geometry is centered on the sketch origin"; "Z Angle: Rotates the image geometry around the origin point. Positive values are clockwise" | Autodesk (support "How to insert and engrave an SVG file"; help "Add an SVG image", SLD-INS-SVG, read through search excerpts) | Same: the SVG is centred on the sketch origin; positive Z Angle turns it clockwise; the manipulator sits at its middle: two arrows (X / Y Distance), a curved handle (Z Angle), an arrow beyond its right edge (Scale), each with a value box; Enter in a value box takes the value and finishes (OK), as Enter does everywhere in Fusion |
| The SVG manipulator follows the sketch plane (a bug made it follow the world axes in a child component) | Forum (FUS-97316, Autodesk QA) | The arrows follow the plane's X and Y |
| Insert DXF: "the DXF origin is placed at the sketch origin" | Autodesk (help "Insert a DXF file") | Same; its manipulator sits at the DXF's origin (where it turns and scales about); its Z Angle turns counter-clockwise (**Guess**: no source for DXF) |
| Canvas: the manipulator "stays anchored to the image's center"; no way to move the pivot | Forum (Autodesk support answer, "Dynamic Manipulator") | Same handles at the picture's middle (Z Angle counter-clockwise, **Guess**); Edit Canvas has them too; the scale handle scales X and Y together; Calibrate's scale is kept (the handles start from it) |
| The manipulator keeps its size on the screen when zooming | Guess (every Fusion manipulator does) | The handles are made again when the view is zoomed, panned or turned |
| McMaster-Carr insert | Autodesk (Insert > Insert McMaster-Carr Component) | Not built: it needs McMaster's online catalogue inside the program; a STEP downloaded from mcmaster.com goes in with Insert STEP. Standard screws, nuts, washers, heat-set inserts and magnets come from SciForge's own offline library: INSERT > Hardware... (parity/hardware.md) |

### Known gaps of Part 2 (also listed in Known gaps below)

- Body names inside components do not survive a STEP round trip (FreeCAD's STEP writer has
  no names for the solids of a product): they come back as Body1, Body2 (Fusion keeps them).
  A component named like its only sub-component folds into one level when read back.
- An inserted design's own components come in flat (its bodies in one component), like a
  copy of a component (parity/components.md); a linked copy can be changed in this design
  (Fusion locks it until Break Link).
- No out-of-date icon and no Get Latest: the copies follow the other design's saved file
  when this design opens.
- Insert STEP is a one-off import (not linked to the STEP file).
- DWG untested (no converter in the sandbox); the DWG path converts the DXF SciForge writes.
- SAT / SMT / F3D / FBX / USD / SketchUp / Inventor: not read or written (FreeCAD has no
  readers or writers for them; ACIS needs a commercial kernel).
- A decal keeps its own manipulator (decal_ui.py: arrows, turn and scale, value boxes on the
  arrows and the turn); its scale arrow has no value box.

## Part 3 (export-report, 2026-10-21): what an export leaves out, what an import skipped

Idea 2 of `docs/sciforge/dev/cadcraft-lessons.md`, approved by Luca: never drop data
silently. After every export (File > Export, Save As DXF, 3D Print, Export Everything, a
drawing's Export PDF / DXF) a short card in the bottom right corner of the 3D view says what
the file does not keep, counted from this design ("Not kept in this file: the timeline (4
steps); 2 sketches; the colours of 1 body ..."); after Insert Mesh, Insert SVG / DXF and
Open / Insert STEP it says what did not come in. No card when nothing is lost; no pop-up;
the same line goes to the Report view. Fusion has no such message (this goes beyond it, as
CADCraft does); the wording is SciForge's own.

Built in `src/Mod/SciForge/sciforge/`: `export_report_core.py` (no FreeCAD: the rules per
format and the sentences, unit tested in `test_export_report_core.py`), `export_report.py`
(the counts from the real design, following each export path exactly; `losses(doc, objects,
fmt)` is the function the AI tools can call), `export_report_ui.py` (the card). Golden
models `export_report_design`, `export_report_sketch_dxf`, `export_report_imports` (each
claim proven by writing the file and reading it back, `golden/export_checks.py`); scenarios
`export_report`, `import_report`, and `drawing_export` checks the drawing DXF's message.

| File | What it does not keep (checked in FreeCAD 1.1.4) |
|---|---|
| Every 3D file | the timeline, sketches, construction planes / axes / points, parameters (values built in), joints, physical materials, cosmetic threads, decals and canvases; hidden bodies and surface bodies are not exported |
| STEP | keeps components, copies and colours (with the window open; FreeCAD's headless writer has none); see-through looks come out opaque; bodies in a component come back Body1, Body2 ... (a single body at the design's root keeps its name); mesh bodies cannot go in |
| IGES | no components, no colours, no names (one unnamed product); mesh bodies cannot go in |
| STL | one mesh (several bodies merged: no names, no parts), no colours, no unit; curved faces become triangles |
| 3MF | names and unit kept; no colours, no components; curved faces become triangles |
| OBJ | names kept (groups); no colours (no material file), no unit, no components |
| DXF / DWG of a sketch | dimensions, constraints, construction curves, points, projected curves; flat in the sketch's own X and Y |
| Drawing DXF | dimensions and symbols as plain lines and text, curves that are not circles / arcs as short lines, hatching as separate lines, no named font; hidden views; the other sheets with Current Sheet |
| Drawing PDF | hidden views; the other sheets with Current Sheet |

Imports: Insert Mesh (open edges, edges shared by more than two triangles, flipped
triangles, a 3MF's several objects in one body, its colours, its own unit when it differs
from Unit Type), Insert DXF (entities FreeCAD's importer cannot read, from its own
statistics; texts / dimensions and points, which are not curves), Insert SVG (texts,
pictures), Open / Insert STEP and IGES (loose faces of a part that also has solids, loose
curves and points, loose faces sewn into surface bodies, shapes with errors).

## Sources (Part 1)

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
- 3D Print to a slicer (Send to Slicer, 2026-10-18; help pages unreachable from the sandbox,
  read through search excerpts): help "3D print a design" (SLD-3D-PRINT.htm, and its French
  copy): Preparation Type Manufacturing / Export / Print Utility; Print Utility: "select the
  Application ... from the dropdown list of 3D print utilities that Fusion has found", else
  "select Custom" and specify the program's location. Support article "How to export an
  STL/3MF file from Fusion": untick Send to 3D Print Utility to save a file. Forums: Autodesk
  Community "Send 3d print to cura" (Cura is picked up when installed), "Recent update broke
  send to 3D Printer" and "Version Fusion 2.0.20256 print utility fails if target slicer is
  open" (FUS-171507: Bambu Studio, OrcaSlicer, PrusaSlicer got nothing while already open;
  Custom pointed at the .exe or a Windows shortcut works), "Send to 3D print utility always
  reverts to checked", "Save As Mesh - behaviour changed"; Bambu Lab forum "Can't send files
  from Fusion 360 anymore" (Custom = bambu-studio.exe). Install folders of the four slicers:
  their Windows installers' defaults (**from memory; Guess** where a version changes them).
- Fusion inserts STEP files through its Data Panel (upload, then Insert into Current Design,
  which opens a Move dialog) or opens them as a design: SciForge has no cloud panel, so
  **Insert STEP** picks the file at once (support article "How to insert a mesh body" for the
  Insert menu's shape; the components doc for where the bodies go, once components exist).

## What gets built

| Tool | Built as |
|---|---|
| Insert Mesh | a `Mesh::Feature` at document level (SciForgeType `InsertMesh`), its triangles in design units, Z up; Placement = the dialog's position and angles; `SourceFile`, `UnitType`, `FlipUp`, `UnitScale` remembered so the step can be edited without the file |
| Convert Mesh | a new body whose first step is SciForge's `ConvertMesh` feature (`Source` = the mesh body, `Method`, `Parametric`, `Tolerance`); Parametric rebuilds from the mesh when it moves or changes, Base Feature keeps the solid it made |
| Insert STEP | the file as one component (`App::Part`) named after it, its products as nested components, each solid a `PartDesign::Body` (FreeCAD's `BaseFeature` step, marked `InsertSTEP`, its base `Part::Feature` inside the component), a repeated part as an instance (`instances.py`), its colours as a SciForge Appearance (per face when the part has several); read with FreeCAD's STEP reader in a hidden throw-away document (Part 2) |
| Insert SVG / DXF | sketch geometry (lines, circles, arcs, ellipses, splines) added to a sketch with a `Block` constraint each (fixed, green), made from FreeCAD's `importSVG` / `importDXF` run in a throw-away hidden document; the dialog's X / Y / angle / scale / flips are applied to the geometry itself (never OpenCASCADE's shape transform, which turns everything into B-splines) |
| Canvas | an `Image::ImagePlane` (SciForgeType `Canvas`, kept out of the timeline) with the picture inside the design file (FreeCAD's `ImageFile` keeps a copy), `PlaneFrame` = the plane it sits on, `BaseWidth` / `BaseHeight`, `ScaleX` / `ScaleY`, `XDistance`, `YDistance`, `ZAngle`, `FlipHorizontal`, `FlipVertical`, `CanvasOpacity`, `DisplayThrough`; opacity = the view's Transparency, Display Through = the image drawn as a Coin annotation (after everything else, no depth test), Selectable = the view's Selectable |
| Export (meshes) | FreeCAD's mesher with Surface Deviation (linear deflection, mm) and Normal Deviation (angular deflection); STL = one mesh (the union), 3MF and OBJ = one object per body with its name (the 3MF object names and unit are written by SciForge, FreeCAD leaves them out) |
| Export (STEP / IGES) | a hidden throw-away document mirroring the components (Part 2), written by FreeCAD's `ImportGui.export` (names and colours); IGES with solids (OpenCASCADE's brep mode 1) |
| Export (DXF / DWG) | the sketch's or face's edges in its own 2D frame, written by FreeCAD's `importDXF`; DWG converted by FreeCAD's `importDWG.convertToDwg` when a converter is installed |
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

### Insert STEP (INSERT > Insert STEP; File menu; Data Panel > Insert into Current Design)

| Fusion | SciForge |
|---|---|
| Upload the STEP to the Data Panel, then Insert into Current Design (the Initial Position dialog opens) | pick the file (STEP or IGES; or the Data Panel's uploaded file); the file comes in as one component named after it, in the active component; the Move dialog opens on it (Part 2) |
| The STEP's component structure, the parts' names, colours | same: nested components named after the products, Body1 ... in each, per-face colours kept; a part used twice comes in once plus a linked copy ("Wheel:2"); the timeline shows the components and "Insert STEP N" per body |
| A second insert of the same file | "two_parts (2)" with its own components |
| Ctrl+Z | the Move first, then the whole insert; Ctrl+Y brings them back with their colours |
| File > Open of a STEP / IGES file | a new design of the file (Part 2) |

### Insert SVG / Insert DXF (INSERT menu; File menu)

| Fusion | SciForge |
|---|---|
| Pick the file, then a planar face or plane (an active sketch is used) | same: the origin squares light up like Create Sketch, flat faces can be clicked; a sketch that is open gets the curves (the sketch is closed while the dialog runs and opened again on OK or Cancel) |
| The curves appear in a sketch; an SVG "centered on the sketch origin", a DXF's origin at the sketch origin | same (Part 2); Y of an SVG pointing down (as FreeCAD reads SVG and as Fusion's Y Distance says) |
| X Distance, Y Distance, Z Angle (SVG: positive clockwise), Scale Plane XY, Horizontal Flip, Vertical Flip, manipulators | the fields (live) and the manipulator on the plane: two arrows, a curved handle, a scale arrow, value boxes (Part 2) |
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
| The manipulator at the picture's middle (move, turn, scale) | same in Canvas and Edit Canvas, with value boxes (Part 2) |
| Right-click > Calibrate: two points, the distance, Enter | same: the dialog says which point to click, draws the two points and the line, shows the picked distance in the field; type the real distance, Enter (or OK): the canvas scales about its centre **(about which point Fusion scales: assumed)**; the clicks land on screen pixels, so the result is within about 0.1 mm |
| Save, reopen: the canvas is there | same, the picture is inside the design file (FreeCAD keeps a copy); Display Through and opacity are put back when a design opens |

### Export (UTILITIES > MAKE > Export; File menu > Export)

| Fusion | SciForge |
|---|---|
| File > Export: Name, Type, Location, Export | the Export dialog: Export (Whole design / Selected bodies with a ticked list / A component), Type (STEP, IGES, STL Binary, STL ASCII, 3MF, OBJ, DXF, DWG), Sketch or face (DXF / DWG, with Use Selection), Name, Location (…), "Open the folder afterwards", Export (Part 2) |
| Mesh types from Save As Mesh: Unit Type, Structure One File / One File Per Body, Refinement Low / Medium / High / Custom, Surface Deviation, Normal Deviation, Number of Triangles | same rows (shown for mesh types; greyed for STEP); the count follows the refinement |
| Formats SciForge does not write | SAT, SMT, F3D, FBX, USD, SketchUp, Inventor (FreeCAD has no writers for them); DWG only through a free converter (Part 2) |
| A body with no solid | left out of the list; "Whole design" exports the shown bodies **(hidden bodies left out: assumed)**; mesh bodies are listed and written with their own triangles (STEP refuses them: `parity/mesh.md`) |

### 3D Print (UTILITIES > MAKE > 3D Print; File menu)

| Fusion | SciForge |
|---|---|
| Selection: bodies | the bodies list, ticked from the selection (else all shown bodies) |
| Preparation Type Export; Format 3MF / STL (Binary) / STL (ASCII) / OBJ | the formats (Manufacturing left out: no CAM) |
| Refinement Low / Medium / High / Custom with Surface Deviation, Normal Deviation (Maximum Edge Length, Aspect Ratio), Preview Mesh, Number of Triangles | Low = 0.127 mm / 30 deg, Medium = 0.0508 mm / 15 deg, High = 0.0254 mm / 10 deg **(the numbers Fusion shows for a mm design, from memory: thousandths of an inch; unconfirmed)**, Custom takes the two fields; Number of Triangles; no Maximum Edge Length / Aspect Ratio (FreeCAD's mesher has no such settings) and no Preview Mesh overlay (gaps) |
| Preparation Type Print Utility: Application = a drop-down of the 3D print utilities Fusion found on the computer, or Custom (then point it at the program); older versions: a "Send to 3D Print Utility" check box with the same list (sources below) | **Send to** drop-down (Send to Slicer, 2026-10-18): the slicers SciForge finds (PrusaSlicer, Bambu Studio, OrcaSlicer, UltiMaker Cura), then "Other... (pick the program)" (Fusion's Custom: choosing it opens the program picker; Program row with "…") and "Save file only" (Fusion's Export). One drop-down instead of Preparation Type + Application: same choices, parity level B |
| How Fusion finds the utilities (not documented) | **(SciForge's own rules)** Windows: Program Files, Program Files (x86), `%LOCALAPPDATA%\Programs` (`Prusa3D\PrusaSlicer\prusa-slicer.exe`, `Bambu Studio\bambu-studio.exe`, `OrcaSlicer\orca-slicer.exe`, the newest `UltiMaker Cura <version>\UltiMaker-Cura.exe`); Linux: the PATH, Flatpak (`/var/lib/flatpak/exports/bin`, `~/.local/share/flatpak/exports/bin`), AppImages in `~/Applications`, `~/Downloads`, `~/bin`; macOS: `/Applications/*.app`. No registry, nothing started. `slicer_core.py` |
| Nothing found | **(SciForge's own)** the dialog says plainly that no slicer was found and offers Other... and Save file only (it starts at Save file only); OK on Other... without a program says so and writes nothing |
| OK with a utility: the file goes to the slicer (forum users: Fusion hands it an STL / 3MF; a slicer already running sometimes got an empty plate, Autodesk ticket FUS-171507) | OK writes the file to SciForge's temporary print folder (files older than 7 days cleaned up) and starts the slicer with the file's path as its argument (detached: SciForge carries on). A Windows shortcut (.lnk) or batch file is started the way a double click does (`cmd /c start`), a macOS .app with `open -a` |
| The file the slicer gets | one object per body named after the body, placed as in the design; **always millimetres when sending** (Unit Type greyed at Millimeter: slicers work in mm and an STL has no unit; 3MF says `unit="millimeter"`). Named after the body for one body, after the design for several |
| (Fusion has no such option: Guess) | **Also save a copy next to the design** (SciForge's own, Luca's request): the same file beside the design file (or the last export folder for an unsaved design); never overwrites (`name-2.3mf`...), since slicers save their projects as .3mf too |
| Fusion remembers the utility (forum: "Send to 3D Print Utility always reverts to checked"; after 2.0.20256 the Preparation Type was not remembered for some users) | Send to, the Other program, Format and Save a copy are remembered on OK (Cancel keeps the old ones) and shown on **Preferences > 3D Print** (SciForge's own page: Send to, Program (Other), Format, Also save a copy; it also lists the slicers found) |
| Save file only (Export) | OK asks where to save (the Unit Type chosen is used) and opens the folder |

### Export Everything (UTILITIES > MAKE; File menu)

Luca's ownership guarantee (outline 5.6): one command writes the whole design to open formats.
Beside a saved design `Bracket.FCStd` it makes `Bracket-export/` with `Bracket.step`,
`Bracket.stl`, `Bracket.3mf`, `Bracket.obj`, `Bracket.png` and `README.txt`, then opens the
folder. A design never saved asks for a folder first. An empty design says there is nothing to
export. Fusion has no such command (its nearest is File > Export, one format at a time).

## Known gaps (never faked: listed here)

| Fusion behaviour | Why not (yet) |
|---|---|
| Insert McMaster-Carr | needs McMaster's online catalogue in the program (SciForge is offline): a downloaded STEP goes in with Insert STEP; standard hardware: INSERT > Hardware... (parity/hardware.md). Derive, Decal, Insert Component: their own docs (parity/misc.md, Part 2) |
| STEP body names inside components after a round trip; an inserted design's own components; a linked copy locked against edits; the out-of-date icon | Part 2, Known gaps |
| Convert Mesh "Organic", surface fitting of round faces (Prismatic keeps them faceted) | FreeCAD has no mesh-to-surface fitting |
| Export: SAT, SMT, F3D, FBX, USD; DWG without a converter | no FreeCAD writers; DWG needs LibreDWG / ODA / QCAD installed (untested here) |
| 3D Print: Maximum Edge Length, Aspect Ratio, Preview Mesh overlay, Manufacturing preparation | FreeCAD's mesher has no edge length / aspect settings; no CAM |
| 3D Print: utilities Fusion lists that SciForge does not look for (PreForm, Meshmixer, Print Studio...) and slicers beyond the four (Creality Print, Elegoo, SuperSlicer...) | pick them with Other...; more can be added to `slicer_core.SLICERS` (one entry each) |
| A slicer that is already open getting the file | up to the slicer (PrusaSlicer / OrcaSlicer / Bambu Studio open a second window or hand the file to the open one, depending on their own "single instance" setting); untested with the real programs, only with stand-ins |
| The exact refinement numbers of Low / Medium / High | from memory of Fusion's dialog, to confirm |
| An inserted mesh in the timeline rolls back with the marker | mesh bodies sit outside the PartDesign bodies, so the history marker never hides them |
| Canvas: "Render as" options | not built (rendering is out of scope) |
| FreeCAD's SVG importer skips text and gradients; a `<circle>` with stroke attributes came in at twice its position in one FreeCAD build | FreeCAD's importer; the fixture avoids stroke attributes, real files may need a path-based circle |
