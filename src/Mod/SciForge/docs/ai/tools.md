# SciForge AI tools

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

SciForge offers 117 tools to AI apps (through MCP, the built-in chat panel and the command line), listed here in the order tools/list gives them. All lengths are in millimetres (mm) and all angles in degrees. Every tool that changes the design is one undo step named "AI: ..."; errors come back as plain sentences. Each tool has a reference page (reference/<tool>.md: every argument, the answer, the errors and a complete example with its real answer); the resource sciforge://tools has every schema as JSON.

## All tools

| Tool | Title | Category | Fusion command | Kind | Needs |
|---|---|---|---|---|---|
| [`get_design`](sciforge://docs/reference/get_design.md) | Get design | Inspect and measure | BROWSER (the design's bodies, sketches, parameters) and TIMELINE | read-only | nothing |
| [`screenshot`](sciforge://docs/reference/screenshot.md) | Screenshot | View | File > Capture Image | read-only | an open design, the SciForge window |
| [`measure`](sciforge://docs/reference/measure.md) | Measure | Inspect and measure | INSPECT > Measure | read-only | an open design |
| [`create_sketch`](sciforge://docs/reference/create_sketch.md) | Create sketch | Sketch | SOLID > CREATE > Create Sketch | changes the design (one undo step) | nothing |
| [`extrude`](sciforge://docs/reference/extrude.md) | Extrude | Create (SOLID) | SOLID > CREATE > Extrude | changes the design (one undo step) | an open design |
| [`revolve`](sciforge://docs/reference/revolve.md) | Revolve | Create (SOLID) | SOLID > CREATE > Revolve | changes the design (one undo step) | an open design |
| [`fillet`](sciforge://docs/reference/fillet.md) | Fillet | Modify | SOLID > MODIFY > Fillet | changes the design (one undo step) | a solid body |
| [`chamfer`](sciforge://docs/reference/chamfer.md) | Chamfer | Modify | SOLID > MODIFY > Chamfer | changes the design (one undo step) | a solid body |
| [`hole`](sciforge://docs/reference/hole.md) | Hole | Create (SOLID) | SOLID > CREATE > Hole | changes the design (one undo step) | a solid body |
| [`pattern`](sciforge://docs/reference/pattern.md) | Pattern | Create (SOLID) | SOLID > CREATE > Pattern > Rectangular / Circular Pattern (features) | changes the design (one undo step) | a solid body |
| [`shell`](sciforge://docs/reference/shell.md) | Shell | Modify | SOLID > MODIFY > Shell | changes the design (one undo step) | a solid body |
| [`set_parameter`](sciforge://docs/reference/set_parameter.md) | Set parameter | Parameters | MODIFY > Change Parameters (User Parameters, +) | changes the design (one undo step) | nothing |
| [`undo`](sciforge://docs/reference/undo.md) | Undo | Designs and files | Quick Access Toolbar > Undo (Ctrl+Z) | takes back the last undo step | an open design |
| [`redo`](sciforge://docs/reference/redo.md) | Redo | Designs and files | Quick Access Toolbar > Redo (Ctrl+Y) | brings back the last undone step | an open design |
| [`save`](sciforge://docs/reference/save.md) | Save | Designs and files | Quick Access Toolbar > Save | writes files | an open design |
| [`export`](sciforge://docs/reference/export.md) | Export | Import and export | File > Export | writes files | an open design |
| [`create_curve_sketch`](sciforge://docs/reference/create_curve_sketch.md) | Create sketch of curves | Sketch | SOLID > CREATE > Create Sketch (lines, arcs, points) | changes the design (one undo step) | nothing |
| [`add_to_sketch`](sciforge://docs/reference/add_to_sketch.md) | Add to sketch | Sketch | SKETCH > CREATE (Line, Rectangle, Circle, Arc, Polygon, Slot, Spline, Point) | changes the design (one undo step) | an open design |
| [`get_sketch`](sciforge://docs/reference/get_sketch.md) | Get sketch | Sketch | BROWSER > Sketches (and the Sketch Palette) | read-only | an open design |
| [`sketch_constraint`](sciforge://docs/reference/sketch_constraint.md) | Sketch constraint | Sketch | SKETCH > CONSTRAINTS | changes the design (one undo step) | an open design |
| [`sketch_dimension`](sciforge://docs/reference/sketch_dimension.md) | Sketch dimension | Sketch | SKETCH > CREATE > Sketch Dimension (D) | changes the design (one undo step) | an open design |
| [`set_sketch_dimension`](sciforge://docs/reference/set_sketch_dimension.md) | Set sketch dimension | Sketch | SKETCH > double-click a dimension (or MODIFY > Change Parameters, Model Parameters) | changes the design (one undo step) | an open design |
| [`sketch_delete`](sciforge://docs/reference/sketch_delete.md) | Delete in sketch | Sketch | SKETCH > select > Delete | changes the design (one undo step), destructive | an open design |
| [`sketch_polygon`](sciforge://docs/reference/sketch_polygon.md) | Polygon | Sketch | SKETCH > CREATE > Polygon > Circumscribed / Inscribed Polygon | changes the design (one undo step) | an open design |
| [`sketch_trim`](sciforge://docs/reference/sketch_trim.md) | Trim | Sketch | SKETCH > MODIFY > Trim (T) | changes the design (one undo step) | an open design |
| [`sketch_text`](sciforge://docs/reference/sketch_text.md) | Text | Sketch | SKETCH > CREATE > Text | changes the design (one undo step) | an open design |
| [`sweep`](sciforge://docs/reference/sweep.md) | Sweep | Create (SOLID) | SOLID > CREATE > Sweep | changes the design (one undo step) | an open design |
| [`loft`](sciforge://docs/reference/loft.md) | Loft | Create (SOLID) | SOLID > CREATE > Loft | changes the design (one undo step) | an open design |
| [`rib`](sciforge://docs/reference/rib.md) | Rib | Create (SOLID) | SOLID > CREATE > Rib | changes the design (one undo step) | a solid body |
| [`web`](sciforge://docs/reference/web.md) | Web | Create (SOLID) | SOLID > CREATE > Web | changes the design (one undo step) | a solid body |
| [`emboss`](sciforge://docs/reference/emboss.md) | Emboss | Create (SOLID) | SOLID > CREATE > Emboss | changes the design (one undo step) | a solid body |
| [`thread`](sciforge://docs/reference/thread.md) | Thread | Create (SOLID) | SOLID > CREATE > Thread | changes the design (one undo step) | a solid body |
| [`primitive`](sciforge://docs/reference/primitive.md) | Box / Cylinder / Sphere / Torus | Create (SOLID) | SOLID > CREATE > Box, Cylinder, Sphere, Torus | changes the design (one undo step) | nothing |
| [`coil`](sciforge://docs/reference/coil.md) | Coil | Create (SOLID) | SOLID > CREATE > Coil | changes the design (one undo step) | nothing |
| [`pipe`](sciforge://docs/reference/pipe.md) | Pipe | Create (SOLID) | SOLID > CREATE > Pipe | changes the design (one undo step) | an open design |
| [`gear`](sciforge://docs/reference/gear.md) | Gear | Create (SOLID) | SOLID > CREATE > Gear | changes the design (one undo step) | nothing |
| [`rectangular_pattern`](sciforge://docs/reference/rectangular_pattern.md) | Rectangular pattern | Create (SOLID) | SOLID > CREATE > Pattern > Rectangular Pattern | changes the design (one undo step) | a solid body |
| [`circular_pattern`](sciforge://docs/reference/circular_pattern.md) | Circular pattern | Create (SOLID) | SOLID > CREATE > Pattern > Circular Pattern | changes the design (one undo step) | a solid body |
| [`pattern_on_path`](sciforge://docs/reference/pattern_on_path.md) | Pattern on path | Create (SOLID) | SOLID > CREATE > Pattern > Pattern on Path | changes the design (one undo step) | a solid body |
| [`mirror`](sciforge://docs/reference/mirror.md) | Mirror | Create (SOLID) | SOLID > CREATE > Mirror | changes the design (one undo step) | a solid body |
| [`pattern_components`](sciforge://docs/reference/pattern_components.md) | Pattern components | Assemble | SOLID > CREATE > Pattern (Pattern Type: Components) | changes the design (one undo step) | an open design |
| [`insert_hardware`](sciforge://docs/reference/insert_hardware.md) | Insert hardware | Assemble | INSERT > Hardware (McMaster-Carr / fasteners in Fusion) | changes the design (one undo step) | a solid body |
| [`press_pull`](sciforge://docs/reference/press_pull.md) | Press pull | Modify | SOLID > MODIFY > Press Pull (Q) | changes the design (one undo step) | a solid body |
| [`fillet_sets`](sciforge://docs/reference/fillet_sets.md) | Fillet / chamfer with sets | Modify | SOLID > MODIFY > Fillet / Chamfer (several selection sets, Chord Length, Variable) | changes the design (one undo step) | a solid body |
| [`rule_fillet`](sciforge://docs/reference/rule_fillet.md) | Rule fillet | Modify | SOLID > MODIFY > Fillet (Type: Rule Fillet) | changes the design (one undo step) | a solid body |
| [`full_round_fillet`](sciforge://docs/reference/full_round_fillet.md) | Full round fillet | Modify | SOLID > MODIFY > Fillet (Type: Full Round Fillet) | changes the design (one undo step) | a solid body |
| [`draft`](sciforge://docs/reference/draft.md) | Draft | Modify | SOLID > MODIFY > Draft | changes the design (one undo step) | a solid body |
| [`scale`](sciforge://docs/reference/scale.md) | Scale | Modify | SOLID > MODIFY > Scale | changes the design (one undo step) | a solid body |
| [`combine`](sciforge://docs/reference/combine.md) | Combine | Modify | SOLID > MODIFY > Combine | changes the design (one undo step) | an open design |
| [`split_body`](sciforge://docs/reference/split_body.md) | Split body | Modify | SOLID > MODIFY > Split Body | changes the design (one undo step) | a solid body |
| [`split_face`](sciforge://docs/reference/split_face.md) | Split face | Modify | SOLID > MODIFY > Split Face | changes the design (one undo step) | a solid body |
| [`silhouette_split`](sciforge://docs/reference/silhouette_split.md) | Silhouette split | Modify | SOLID > MODIFY > Silhouette Split | changes the design (one undo step) | a solid body |
| [`replace_face`](sciforge://docs/reference/replace_face.md) | Replace face | Modify | SOLID > MODIFY > Replace Face | changes the design (one undo step) | a solid body |
| [`delete_face`](sciforge://docs/reference/delete_face.md) | Delete face | Modify | SOLID > MODIFY > Delete (faces) | changes the design (one undo step), destructive | a solid body |
| [`remove_bodies`](sciforge://docs/reference/remove_bodies.md) | Remove | Modify | SOLID > MODIFY > Remove | changes the design (one undo step), destructive | an open design |
| [`delete_bodies`](sciforge://docs/reference/delete_bodies.md) | Delete bodies | Modify | BROWSER > a body > Delete | changes the design (one undo step), destructive | an open design |
| [`move_copy`](sciforge://docs/reference/move_copy.md) | Move / copy | Modify | SOLID > MODIFY > Move/Copy (M) | changes the design (one undo step) | an open design |
| [`align`](sciforge://docs/reference/align.md) | Align | Modify | SOLID > MODIFY > Align | changes the design (one undo step) | a solid body |
| [`physical_material`](sciforge://docs/reference/physical_material.md) | Physical material | Modify | SOLID > MODIFY > Physical Material | changes the design (one undo step) | an open design |
| [`list_materials`](sciforge://docs/reference/list_materials.md) | List materials | Modify | SOLID > MODIFY > Physical Material / Appearance (libraries) | read-only | nothing |
| [`appearance`](sciforge://docs/reference/appearance.md) | Appearance | Modify | SOLID > MODIFY > Appearance (A) | changes the design (one undo step) | an open design |
| [`capture_design_history`](sciforge://docs/reference/capture_design_history.md) | Capture design history | Timeline (history) | the design's menu: Capture Design History / Do Not Capture Design History | changes the design (one undo step), destructive | an open design |
| [`surface`](sciforge://docs/reference/surface.md) | Surface | Surface | SURFACE > CREATE / MODIFY (Extrude, Revolve, Sweep, Loft, Patch, Ruled, Offset, Boundary Fill, Thicken, Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal) | changes the design (one undo step) | nothing |
| [`construct_plane`](sciforge://docs/reference/construct_plane.md) | Construction plane | Construct | SOLID > CONSTRUCT > (planes) | changes the design (one undo step) | an open design |
| [`construct_axis`](sciforge://docs/reference/construct_axis.md) | Construction axis | Construct | SOLID > CONSTRUCT > (axes) | changes the design (one undo step) | an open design |
| [`construct_point`](sciforge://docs/reference/construct_point.md) | Construction point | Construct | SOLID > CONSTRUCT > (points) | changes the design (one undo step) | an open design |
| [`new_component`](sciforge://docs/reference/new_component.md) | New component | Assemble | ASSEMBLE > New Component | changes the design (one undo step) | nothing |
| [`components_from_bodies`](sciforge://docs/reference/components_from_bodies.md) | Components from bodies | Assemble | BROWSER > a body > Create Components from Bodies | changes the design (one undo step) | an open design |
| [`copy_component`](sciforge://docs/reference/copy_component.md) | Copy / paste component | Assemble | Copy (Ctrl+C) a component, then Paste / Paste New | changes the design (one undo step) | an open design |
| [`activate`](sciforge://docs/reference/activate.md) | Activate body / component | Assemble | BROWSER > a body or component > Activate | changes the design (one undo step) | an open design |
| [`new_body`](sciforge://docs/reference/new_body.md) | New body | Assemble | BROWSER > Bodies > New Body | changes the design (one undo step) | nothing |
| [`joint`](sciforge://docs/reference/joint.md) | Joint | Assemble | ASSEMBLE > Joint (J) | changes the design (one undo step) | an open design |
| [`drive_joint`](sciforge://docs/reference/drive_joint.md) | Drive joint | Assemble | ASSEMBLE > Drive Joints | changes the design (one undo step) | an open design |
| [`ground`](sciforge://docs/reference/ground.md) | Ground / unground | Assemble | BROWSER > a component > Ground | changes the design (one undo step) | an open design |
| [`physical_properties`](sciforge://docs/reference/physical_properties.md) | Physical properties | Inspect and measure | BROWSER > a body > Properties (INSPECT) | read-only | an open design |
| [`center_of_mass`](sciforge://docs/reference/center_of_mass.md) | Center of mass | Inspect and measure | INSPECT > Center of Mass | read-only | a solid body |
| [`interference`](sciforge://docs/reference/interference.md) | Interference | Inspect and measure | INSPECT > Interference | read-only | a solid body |
| [`section_analysis`](sciforge://docs/reference/section_analysis.md) | Section analysis | Inspect and measure | INSPECT > Section Analysis | read-only | a solid body |
| [`get_timeline`](sciforge://docs/reference/get_timeline.md) | Get timeline | Timeline (history) | TIMELINE (the bar at the bottom) | read-only | an open design |
| [`get_step`](sciforge://docs/reference/get_step.md) | Get step | Timeline (history) | TIMELINE > double-click a step (the dialog's fields) | read-only | an open design |
| [`edit_step`](sciforge://docs/reference/edit_step.md) | Edit step | Timeline (history) | TIMELINE > double-click a step > change its fields > OK | changes the design (one undo step) | an open design |
| [`roll_timeline`](sciforge://docs/reference/roll_timeline.md) | Move history marker | Timeline (history) | TIMELINE > drag the history marker (and the playback buttons) | changes the design (one undo step) | an open design |
| [`suppress_step`](sciforge://docs/reference/suppress_step.md) | Suppress / unsuppress | Timeline (history) | TIMELINE > right-click a step > Suppress Features | changes the design (one undo step) | an open design |
| [`delete_step`](sciforge://docs/reference/delete_step.md) | Delete step | Timeline (history) | TIMELINE > right-click a step > Delete | changes the design (one undo step), destructive | an open design |
| [`move_step`](sciforge://docs/reference/move_step.md) | Reorder step | Timeline (history) | TIMELINE > drag a step | changes the design (one undo step) | an open design |
| [`rename`](sciforge://docs/reference/rename.md) | Rename | Timeline (history) | TIMELINE / BROWSER > right-click > Rename | changes the design (one undo step) | an open design |
| [`group_steps`](sciforge://docs/reference/group_steps.md) | Group steps | Timeline (history) | TIMELINE > select steps > right-click > Group | changes the design (one undo step) | an open design |
| [`list_parameters`](sciforge://docs/reference/list_parameters.md) | List parameters | Parameters | MODIFY > Change Parameters | read-only | an open design |
| [`delete_parameter`](sciforge://docs/reference/delete_parameter.md) | Delete parameter | Parameters | MODIFY > Change Parameters > a user parameter > Delete | changes the design (one undo step), destructive | an open design |
| [`set_model_parameter`](sciforge://docs/reference/set_model_parameter.md) | Set model parameter | Parameters | MODIFY > Change Parameters > Model Parameters | changes the design (one undo step) | an open design |
| [`new_design`](sciforge://docs/reference/new_design.md) | New design | Designs and files | File > New Design | changes the open designs (not an undo step) | nothing |
| [`open_design`](sciforge://docs/reference/open_design.md) | Open design | Designs and files | File > Open | changes which design is open or active, changes no design | nothing |
| [`save_as`](sciforge://docs/reference/save_as.md) | Save as | Designs and files | File > Save As | writes files | an open design |
| [`close_design`](sciforge://docs/reference/close_design.md) | Close design | Designs and files | File > Close | changes the open designs (not an undo step), destructive | nothing |
| [`list_designs`](sciforge://docs/reference/list_designs.md) | List designs | Designs and files | the design tabs | read-only | nothing |
| [`switch_design`](sciforge://docs/reference/switch_design.md) | Switch design | Designs and files | click a design tab | changes which design is open or active, changes no design | nothing |
| [`import_file`](sciforge://docs/reference/import_file.md) | Insert file | Import and export | INSERT > Insert Mesh / Insert DXF / Insert STEP, and Insert into Current Design | changes the design (one undo step) | nothing |
| [`create_drawing`](sciforge://docs/reference/create_drawing.md) | Create drawing | Drawings | File > New Drawing > From Design | changes the design (one undo step) | a solid body |
| [`add_drawing_view`](sciforge://docs/reference/add_drawing_view.md) | Add drawing view | Drawings | DRAWING > CREATE > Base View / Projected View / Section View / Detail View | changes the design (one undo step) | a drawing |
| [`add_drawing_dimension`](sciforge://docs/reference/add_drawing_dimension.md) | Add drawing dimension | Drawings | DRAWING > DIMENSIONS > Dimension | changes the design (one undo step) | a drawing |
| [`add_drawing_annotation`](sciforge://docs/reference/add_drawing_annotation.md) | Add drawing annotation | Drawings | DRAWING > TEXT / TABLES / SYMBOLS (Text, Table (parts list), Center Mark) | changes the design (one undo step) | a drawing |
| [`get_drawing`](sciforge://docs/reference/get_drawing.md) | Get drawing | Drawings | BROWSER > Drawings | read-only | a drawing |
| [`export_drawing`](sciforge://docs/reference/export_drawing.md) | Export drawing | Drawings | DRAWING > EXPORT > Output PDF / Output DXF | writes files | a drawing |
| [`set_view`](sciforge://docs/reference/set_view.md) | Set view | View | NAVIGATION BAR and VIEWCUBE (Home, Fit, Orbit, Look At) | read-only | an open design, the SciForge window |
| [`get_view`](sciforge://docs/reference/get_view.md) | Get view | View | (the 3D view's camera) | read-only | an open design, the SciForge window |
| [`named_view`](sciforge://docs/reference/named_view.md) | Named view | View | BROWSER > Named Views (New Named View, go to, delete) | changes the design (one undo step) | an open design |
| [`show_hide`](sciforge://docs/reference/show_hide.md) | Show / hide | View | BROWSER > the eye icon (Show / Hide) | changes the design (one undo step) | an open design |
| [`get_help`](sciforge://docs/reference/get_help.md) | Get help | Help | (SciForge's documentation for AI models) | read-only | nothing |
| [`list_tools`](sciforge://docs/reference/list_tools.md) | List tools | Help | (SciForge's command list) | read-only | nothing |
| [`inspect_design`](sciforge://docs/reference/inspect_design.md) | Inspect design | Inspect and measure | BROWSER + TIMELINE + Properties (everything at once) | read-only | nothing |
| [`query_geometry`](sciforge://docs/reference/query_geometry.md) | Query geometry | Inspect and measure | Selection filters + INSPECT > Measure (on what a selector picks) | read-only | an open design |
| [`check_design`](sciforge://docs/reference/check_design.md) | Check design | Inspect and measure | INSPECT > Interference + the timeline's warnings | read-only | an open design |
| [`render`](sciforge://docs/reference/render.md) | Render | View | File > Capture Image (returned to the AI as a picture) | read-only | an open design |
| [`diff_design`](sciforge://docs/reference/diff_design.md) | Diff design | Inspect and measure | TIMELINE (compare before and after) | read-only | an open design |
| [`docs_search`](sciforge://docs/reference/docs_search.md) | Search the documentation | Help | (Fusion's help search, for SciForge) | read-only | nothing |
| [`docs_read`](sciforge://docs/reference/docs_read.md) | Read documentation | Help | (Fusion's help page, for SciForge) | read-only | nothing |
| [`examples_search`](sciforge://docs/reference/examples_search.md) | Search examples | Help | (Fusion's sample designs, for SciForge) | read-only | nothing |

## Help

- [`get_help`](sciforge://docs/reference/get_help.md): Read SciForge's rules for AI tools: overview, selectors (how to pick faces and edges), picks (planes, axes, faces, edges, corners), body_picks, sketches (planes and coordinates), geometry (sketch shapes), curves (paths and rails), steps (ids), expressions (parameters in fields), workflow (how to build and check a part), checking (the tools that check your work with numbers and pictures), docs (where the documentation is and how to search it), tools (every tool by category with its Fusion command).
- [`list_tools`](sciforge://docs/reference/list_tools.md): List every tool by category with its Fusion command, whether it changes the design, and whether it can run right now (and why not: no design open, no solid yet, needs the SciForge window...).
- [`docs_search`](sciforge://docs/reference/docs_search.md): Search SciForge's documentation for AI models: the handbook (how SciForge works, Fusion's ideas mapped to SciForge, coordinates, the timeline, undo, checking your work, failures and how to recover), the selector cookbook, tested recipes for common parts, one reference page per tool (every argument, errors, a real example) and SciForge's own user documentation (cheat sheet, known issues, one Fusion parity spec per feature).
- [`docs_read`](sciforge://docs/reference/docs_read.md): Read one document of SciForge's documentation for AI models, or one section of it: path is what docs_search answers (handbook.md, recipes/bracket.md, reference/extrude.md, user/known-issues.md), optionally with #anchor for one section (or give section).
- [`examples_search`](sciforge://docs/reference/examples_search.md): Find worked examples: recipes (tested sequences of tool calls that build a common part: bracket, enclosure with lid, shaft with keyway, gear pair, flange with bolt pattern, threaded fastener, snap-fit, sheet-like part, revolved knob, lofted handle, surface patch...) and golden models (about 450 small designs in SciForge's design-step language, each with its measured volume and size: proof of what a feature does).

## Designs and files

- [`undo`](sciforge://docs/reference/undo.md): Undo the last change in SciForge (each AI change is one undo step).
- [`redo`](sciforge://docs/reference/redo.md): Redo the change undo took back (one AI call or one SciForge command at a time; a new change after an undo clears what could be redone).
- [`save`](sciforge://docs/reference/save.md): Save the design.
- [`new_design`](sciforge://docs/reference/new_design.md): Start a new, empty design (with one body) and make it the active one.
- [`open_design`](sciforge://docs/reference/open_design.md): Open a design (.FCStd) or a STEP / IGES file as a new design (its components and bodies kept).
- [`save_as`](sciforge://docs/reference/save_as.md): Save the design under a new name (a full path ending in .FCStd); the design then lives there.
- [`close_design`](sciforge://docs/reference/close_design.md): Close a design (default: the active one).
- [`list_designs`](sciforge://docs/reference/list_designs.md): List the open designs: name, label, file, whether it has unsaved changes and which one is active.
- [`switch_design`](sciforge://docs/reference/switch_design.md): Make another open design the active one (the tools then work on it).

## Inspect and measure

- [`get_design`](sciforge://docs/reference/get_design.md): Describe the open SciForge design: its bodies (volume in mm3, bounding box in mm), the timeline steps with their ids (use these ids in profile, sketch and features arguments), the user parameters and the sketches with their areas.
- [`measure`](sciforge://docs/reference/measure.md): Measure between two picks a and b of the current body or the origin: the minimum distance (mm) and, where it makes sense, the angle (degrees), like SciForge's Measure tool; also the X / Y / Z distances, the two nearest points and what each pick is (length, area, radius...).
- [`physical_properties`](sciforge://docs/reference/physical_properties.md): Physical properties of bodies, as Fusion's Properties: volume (mm3), area (mm2), material and density, mass (g), centre of mass and bounding box (mm), number of faces, edges and solids, and whether the solid is valid.
- [`center_of_mass`](sciforge://docs/reference/center_of_mass.md): The centre of mass of bodies together (Fusion's Center of Mass), weighted by their materials.
- [`interference`](sciforge://docs/reference/interference.md): Find where bodies overlap (Fusion's Interference): every pair that overlaps with the overlapping volume (mm3).
- [`section_analysis`](sciforge://docs/reference/section_analysis.md): Cut the design with a plane to look inside (Fusion's Section Analysis): plane (a pick: an origin plane or a flat face), distance (offset, mm), x_angle / y_angle (tilt, degrees), flip.
- [`inspect_design`](sciforge://docs/reference/inspect_design.md): Read the whole design as numbers, to check work before trusting a picture: every body (valid solid or not, volume mm3, area mm2, bounding box and size mm, centre of mass, number of solids, faces, edges and corners, material and mass, shown or hidden); every timeline step in order (id, name, kind, body, done or rolled back, suppressed, status and the error message when it failed, its main values; detail full adds every option as get_step shows them); user parameters; components and joints; construction geometry; sketches (closed areas, fully constrained); drawings; and what is selected in SciForge (window only).
- [`query_geometry`](sciforge://docs/reference/query_geometry.md): List the faces, edges or corners (vertices) of a body or step that a selector picks, with facts about each: type (plane, cylinder.
- [`check_design`](sciforge://docs/reference/check_design.md): Check that the design is sound, before saving or exporting it: every body is one valid, closed solid (invalid or open shapes, bodies made of several pieces, empty bodies), timeline steps that failed or warn (with the reason), steps left after the history marker, suppressed steps, sketches with conflicting constraints, and bodies that overlap (Fusion's Interference; interference: false skips it, it takes longest).
- [`diff_design`](sciforge://docs/reference/diff_design.md): What changed in the design since: a snapshot id that inspect_design answered ("S3"), "last_change" (just before the latest change an AI made: what that change did), or a step id (the solid as it was right after that step, compared with now: what the later steps did).

## Sketch

- [`create_sketch`](sciforge://docs/reference/create_sketch.md): Create a sketch with closed shapes (and lines) in it, ready for extrude, revolve or hole.
- [`create_curve_sketch`](sciforge://docs/reference/create_curve_sketch.md): Create a sketch of open curves and points: the paths, rails, guide curves and rib / web curves that sweep, loft, pipe, rib, web, pattern_on_path and split_body use, and points for holes and lofts.
- [`add_to_sketch`](sciforge://docs/reference/add_to_sketch.md): Draw more in an existing sketch (Fusion: edit the sketch and draw): closed shapes (geometry, the same items as create_sketch, with their named dimensions) and open curves or points (curves, the same items as create_curve_sketch).
- [`get_sketch`](sciforge://docs/reference/get_sketch.md): Read a sketch: its plane and placement, every curve by index (type, points, radius, construction or not), every constraint by index (type, name, the curves it ties, its value for dimensions, driving or not), how many degrees of freedom are left (0: fully constrained, Fusion's padlock), the constraints that conflict or are redundant, and its closed areas (with a point inside each, for regions).
- [`sketch_constraint`](sciforge://docs/reference/sketch_constraint.md): Add a geometric constraint to a sketch, as Fusion's Constraints panel: coincident (two points, or a point on a curve), horizontal / vertical (a line, or two points), parallel, perpendicular, tangent, equal, collinear (two lines), concentric (two circles or arcs), midpoint (a point and a line or arc), symmetric (two points or curves and the line they mirror about, third), fix (lock a curve or point), point_on (a point on a curve), smooth (G2 where a spline meets a curve; tangent only when the solver cannot keep curvature).
- [`sketch_dimension`](sciforge://docs/reference/sketch_dimension.md): Add a driving dimension to a sketch, like Fusion's Sketch Dimension: distance (between two points, a point and a line, or one line's length), distance_x / distance_y (horizontal / vertical), radius, diameter, angle (between two lines, or of one line to the x axis).
- [`set_sketch_dimension`](sciforge://docs/reference/set_sketch_dimension.md): Change a sketch dimension: by its name (rectangles made by create_sketch with a name have <name>.width, <name>.height, <name>.x, <name>.y; circles <name>.diameter, <name>.x, <name>.y) or by its index (get_sketch).
- [`sketch_delete`](sciforge://docs/reference/sketch_delete.md): Delete curves and / or constraints of a sketch by their indexes (get_sketch).
- [`sketch_polygon`](sciforge://docs/reference/sketch_polygon.md): Add a regular polygon to a sketch, Fusion's way: center and point, where point is the middle of an edge (circumscribed, default) or a corner (inscribed).
- [`sketch_trim`](sciforge://docs/reference/sketch_trim.md): Trim sketch curves, as clicking Trim at each point in turn: the curve nearest the point loses the piece between its neighbouring intersections.
- [`sketch_text`](sciforge://docs/reference/sketch_text.md): Write text in a sketch (Fusion's sketch Text): its letters become areas you can extrude (profile: the text's id) or emboss.

## Create (SOLID)

- [`extrude`](sciforge://docs/reference/extrude.md): Extrude a sketch's areas into a solid (SciForge's Extrude).
- [`revolve`](sciforge://docs/reference/revolve.md): Revolve a sketch's areas around an axis (SciForge's Revolve).
- [`hole`](sciforge://docs/reference/hole.md): Drill holes into the part (SciForge's Hole).
- [`pattern`](sciforge://docs/reference/pattern.md): Repeat earlier steps (features: their ids, e.g.
- [`sweep`](sciforge://docs/reference/sweep.md): Sweep a profile along a path (Fusion's Sweep).
- [`loft`](sciforge://docs/reference/loft.md): Loft through profiles in order (Fusion's Loft).
- [`rib`](sciforge://docs/reference/rib.md): Fusion's Rib: a thin wall from one open sketch curve; the rib grows in the sketch plane to the part, always joined to the part.
- [`web`](sciforge://docs/reference/web.md): Fusion's Web: a thin wall from open sketch curves; the web grows out of the sketch plane, always joined to the part.
- [`emboss`](sciforge://docs/reference/emboss.md): Emboss (raise) or deboss (sink) a sketch's areas onto faces of the part, wrapping them onto curved faces (Fusion's Emboss).
- [`thread`](sciforge://docs/reference/thread.md): Put a thread on round faces (Fusion's Thread).
- [`primitive`](sciforge://docs/reference/primitive.md): Make a box, cylinder, sphere or torus (Fusion's primitives) on an origin plane or a flat face, in that plane's own x / y frame.
- [`coil`](sciforge://docs/reference/coil.md): Make a coil (spring, helix) or a flat spiral (Fusion's Coil): plane and x / y of its centre, diameter, type rev_height (revolutions + height), rev_pitch, height_pitch or spiral; revolutions, height, pitch (mm per turn), angle (taper, degrees), clockwise; section circular | square | tri_ext | tri_int, section_position inside | center | outside, section_size (mm).
- [`pipe`](sciforge://docs/reference/pipe.md): Make a pipe along a path (Fusion's Pipe): path {"sketch": id, "edge": n} (the sketch's n-th curve, 1 = first, with the curves chained to it when chain is true) or {"edges": edge selector} (edges of the part).
- [`gear`](sciforge://docs/reference/gear.md): Make an involute gear (SciForge's Gear tool): type spur | internal (a ring with teeth inside: rim) | rack (rack_size teeth or length with rack_length, rack_height); standard metric (module, mm) | english (diametral_pitch, teeth per inch); teeth, pressure_angle (14.5, 20 or 25 degrees), backlash, fillet (root fillet, mm), thickness, symmetric (both sides of the plane), hole (bore diameter, 0 none), plane, x / y.
- [`rectangular_pattern`](sciforge://docs/reference/rectangular_pattern.md): Fusion's Rectangular Pattern dialog: repeat features (step ids), faces or the whole body in rows.
- [`circular_pattern`](sciforge://docs/reference/circular_pattern.md): Fusion's Circular Pattern dialog: repeat features, faces or the whole body around an axis: X | Y | Z, {"edge": selector} (a straight edge) or {"face": selector} (a round face's axis).
- [`pattern_on_path`](sciforge://docs/reference/pattern_on_path.md): Fusion's Pattern on Path: repeat features, faces or the body along a sketch curve.
- [`mirror`](sciforge://docs/reference/mirror.md): Fusion's Mirror: mirror features, faces or the whole body about a plane: XY | XZ | YZ or {"face": selector} (a flat face of the part).

## Modify

- [`fillet`](sciforge://docs/reference/fillet.md): Round edges of the current body with a radius (SciForge's Fillet).
- [`chamfer`](sciforge://docs/reference/chamfer.md): Bevel edges of the current body (SciForge's Chamfer).
- [`shell`](sciforge://docs/reference/shell.md): Hollow the current body out with a wall thickness (SciForge's Shell).
- [`press_pull`](sciforge://docs/reference/press_pull.md): Fusion's Press Pull: push or pull faces by a distance (mm, negative pushes in), or give edges (they get a fillet of that radius), or fillet_face (a face a fillet made: that fillet's radius becomes distance).
- [`fillet_sets`](sciforge://docs/reference/fillet_sets.md): Fusion's Fillet or Chamfer dialog with several selection sets in one step (the "+" rows): each set picks edges / faces / features and has its own size.
- [`rule_fillet`](sciforge://docs/reference/rule_fillet.md): Fusion's Rule Fillet: round every edge a rule finds, found again whenever the part changes.
- [`full_round_fillet`](sciforge://docs/reference/full_round_fillet.md): Fusion's Full Round Fillet: each selector picks one centre face (a rib's top, say); it is replaced by a round that touches both side faces.
- [`draft`](sciforge://docs/reference/draft.md): Fusion's Draft: tilt faces by an angle for a mould.
- [`scale`](sciforge://docs/reference/scale.md): Fusion's Scale: make the current body (or bodies: several step ids, one step; or a sketch: its curves and dimensions) bigger or smaller.
- [`combine`](sciforge://docs/reference/combine.md): Fusion's Combine: join, cut or intersect bodies.
- [`split_body`](sciforge://docs/reference/split_body.md): Fusion's Split Body: cut a body into pieces (new bodies).
- [`split_face`](sciforge://docs/reference/split_face.md): Fusion's Split Face: split faces of a body with a tool, so they can be drafted or coloured on their own.
- [`silhouette_split`](sciforge://docs/reference/silhouette_split.md): Fusion's Silhouette Split: split a body along its outline seen from a direction.
- [`replace_face`](sciforge://docs/reference/replace_face.md): Fusion's Replace Face: move faces of a body onto a target (a plane or a face): faces (selector, of: the body's step), tangent_chain, target (a body pick: XY / XZ / YZ or {"face": selector, "of": id}).
- [`delete_face`](sciforge://docs/reference/delete_face.md): Delete faces of the current body (Fusion: select faces, Delete): the gap heals, as when a fillet or a hole is removed.
- [`remove_bodies`](sciforge://docs/reference/remove_bodies.md): Fusion's Remove: take bodies out of the design from this point of the timeline on (a timeline step: rolling back before it brings them back).
- [`delete_bodies`](sciforge://docs/reference/delete_bodies.md): Delete bodies (picked in the browser, then Delete): they are gone from the whole history; what used them keeps working where it can.
- [`move_copy`](sciforge://docs/reference/move_copy.md): Fusion's Move/Copy.
- [`align`](sciforge://docs/reference/align.md): Fusion's Align (Objects: Bodies): move a body so that from (a face, edge or corner of it) lands on to (another face, edge, corner, plane or axis).
- [`physical_material`](sciforge://docs/reference/physical_material.md): Give a body its physical material (Fusion's Physical Material): density for mass and the material's look.
- [`list_materials`](sciforge://docs/reference/list_materials.md): List SciForge's physical materials (key, name, density kg/m3, group) and appearances (key, name, colour), for physical_material and appearance.
- [`appearance`](sciforge://docs/reference/appearance.md): Fusion's Appearance: colour a body, or some faces of it, without changing its material.

## Surface

- [`surface`](sciforge://docs/reference/surface.md): One of the SURFACE tab's tools (thin surface bodies with no volume; Thicken, Boundary Fill and Stitch make solids).

## Construct

- [`construct_plane`](sciforge://docs/reference/construct_plane.md): Make a construction plane (Fusion's CONSTRUCT menu) the way its dialog does; it follows what it is built on when the part changes and other tools can use it (sketch on a plane with create_sketch on, pick it with {"construct": id}).
- [`construct_axis`](sciforge://docs/reference/construct_axis.md): Make a construction axis (Fusion's CONSTRUCT menu) the way its dialog does; it follows what it is built on when the part changes and other tools can use it (sketch on a plane with create_sketch on, pick it with {"construct": id}).
- [`construct_point`](sciforge://docs/reference/construct_point.md): Make a construction point (Fusion's CONSTRUCT menu) the way its dialog does; it follows what it is built on when the part changes and other tools can use it (sketch on a plane with create_sketch on, pick it with {"construct": id}).

## Assemble

- [`pattern_components`](sciforge://docs/reference/pattern_components.md): Pattern a whole component (its copies are linked instances, as Fusion's): kind rectangular (direction, direction2: origin axes X / Y / Z; quantity, quantity2, distance, distance2, distribution extent | spacing) or circular (axis, quantity, angle, circular_type full | angle | symmetric).
- [`insert_hardware`](sciforge://docs/reference/insert_hardware.md): Insert a fastener with the hole it needs: click a flat face of the current body at at ([x, y, z], design coordinates) or a round edge (a hole's rim).
- [`new_component`](sciforge://docs/reference/new_component.md): Make a new, empty component (Fusion's New Component) with its own body, inside parent (a component id) or at the top of the design; it becomes the active component, so the next sketches and features go into it.
- [`components_from_bodies`](sciforge://docs/reference/components_from_bodies.md): Put bodies into components of their own (one component per body), so joints can move them.
- [`copy_component`](sciforge://docs/reference/copy_component.md): Copy a component and paste it: new false (default) makes a linked instance (it changes with the original, Fusion's Paste), new true an independent copy (Paste New); moved by dx / dy / dz (mm).
- [`activate`](sciforge://docs/reference/activate.md): Make a body (by any step in it) or a component the one you work in: the next sketches and features go into it (Fusion's Activate Component).
- [`new_body`](sciforge://docs/reference/new_body.md): Make a new, empty body in the active component and make it the active body: the next sketch and extrude go into it.
- [`joint`](sciforge://docs/reference/joint.md): Fusion's Joint: the first component moves so that its snap point meets the second's.
- [`drive_joint`](sciforge://docs/reference/drive_joint.md): Put a joint at an angle (degrees) and / or slide distance (mm), within its limits; what hangs on it follows.
- [`ground`](sciforge://docs/reference/ground.md): Ground a component (it never moves when joints solve) or unground it (ground: false).

## Timeline (history)

- [`capture_design_history`](sciforge://docs/reference/capture_design_history.md): Turn the timeline on or off for the design (Fusion's Capture Design History).
- [`get_timeline`](sciforge://docs/reference/get_timeline.md): List the timeline in order: every step with its id, its name as the timeline shows it ("Extrude 2"), its kind, the body / component it belongs to, whether it is before the history marker (done) or after it (rolled_back), suppressed, its status (ok, warning, error, with the reason in plain words) and its main values (distance, radius, quantity...); plus where the history marker stands.
- [`get_step`](sciforge://docs/reference/get_step.md): Read one step's definition, the way its dialog shows it when you double-click it: its kind and every option (distances, angles, operation, what it is built on), the formulas that drive values, its status and what it uses.
- [`edit_step`](sciforge://docs/reference/edit_step.md): Change an existing step's options, as double-clicking it in the timeline: set {option: value} with the names get_step shows (extrude: distance, distance2, taper, direction, operation, through_all...; revolve: angle, type, direction, operation; fillet / chamfer: radius, distance...; hole: diameter, depth, extent, hole_type...; patterns: quantity, distance, angle...; shell, draft, scale, sweep, loft, rib, primitives, coil, pipe, gear, hardware, emboss, thread, surface, combine, split, move, align, construction planes...).
- [`roll_timeline`](sciforge://docs/reference/roll_timeline.md): Move the timeline's history marker: to start (an empty design), end, previous / next (one step), or after / before a step.
- [`suppress_step`](sciforge://docs/reference/suppress_step.md): Suppress steps (they stay in the timeline but are skipped, as if they were not there) or bring them back (suppress: false).
- [`delete_step`](sciforge://docs/reference/delete_step.md): Delete steps from the timeline (Fusion asks the same: steps that depend on them may break and are named in the answer).
- [`move_step`](sciforge://docs/reference/move_step.md): Move a step before or after another one in the timeline.
- [`rename`](sciforge://docs/reference/rename.md): Rename a timeline step, a body, a component, a sketch or a drawing (what the timeline and browser show).
- [`group_steps`](sciforge://docs/reference/group_steps.md): Group neighbouring timeline steps under one name (Fusion's timeline groups), or ungroup (ungroup: true with the group's id).

## Parameters

- [`set_parameter`](sciforge://docs/reference/set_parameter.md): Create or change a user parameter (SciForge's Change Parameters).
- [`list_parameters`](sciforge://docs/reference/list_parameters.md): List the design's parameters, as Change Parameters shows them: user parameters (name, unit, formula, value, comment), parameters brought in by a Derive (read-only), and model parameters: every dimension in the design (each step's values and each sketch dimension: the step id, its label, value, unit and formula).
- [`delete_parameter`](sciforge://docs/reference/delete_parameter.md): Delete a user parameter.
- [`set_model_parameter`](sciforge://docs/reference/set_model_parameter.md): Change a model parameter: one value of a step (label as list_parameters shows it: "Distance", "Radius", "Set 1 Size", "Quantity"...) or a sketch dimension (its name or label).

## Import and export

- [`export`](sciforge://docs/reference/export.md): Export the design's bodies to a file: format step (.step / .stp), stl or 3mf (for 3D printing).
- [`import_file`](sciforge://docs/reference/import_file.md): Bring a file into the active design: STEP / IGES (one component with the file's structure, its bodies and colours), STL / OBJ / 3MF (a mesh body; unit: the file's unit), DXF (its curves into a new sketch on sketch_plane XY | XZ | YZ, ready to extrude), FCStd (another design's bodies as a component).

## Drawings

- [`create_drawing`](sciforge://docs/reference/create_drawing.md): Make a 2D drawing of the design (Fusion's New Drawing From Design), kept in the design and updated with it: bodies (step ids, default every visible body), standard ISO | ASME, sheet (A4..A0 for ISO, A..E for ASME), units mm | in, title_block; a base view (base_view orientation Front, Back, Top, Bottom, Left, Right or Home (isometric), at [x, y] on the sheet in mm from the bottom left, scale, style) and projected views (projected: Top, Right, FrontTopRight.
- [`add_drawing_view`](sciforge://docs/reference/add_drawing_view.md): Add a view to a drawing: kind base (orientation, at, scale, style), projected (parent view id, direction Top / Right /.
- [`add_drawing_dimension`](sciforge://docs/reference/add_drawing_dimension.md): Dimension a drawing view, as Fusion's Dimension command does from what is clicked: one line (its length, horizontal / vertical / aligned), one circle (diameter) or arc (radius), two points / lines (the distance or angle between them).
- [`add_drawing_annotation`](sciforge://docs/reference/add_drawing_annotation.md): Add to a drawing: kind text (text lines at [x, y], size mm), parts_list (a table of the view's components with balloons, at = its top-left corner) or center_marks (a centre mark on every circle of a view).
- [`get_drawing`](sciforge://docs/reference/get_drawing.md): Describe drawings: each drawing's id, sheet, standard, units, title block values and views (id, kind, orientation, scale, position on the sheet, size) with their dimensions (value) and, with edges true, each view's elements (lines with ends, circles with centre and radius, in the view's own mm from its centre) for add_drawing_dimension.
- [`export_drawing`](sciforge://docs/reference/export_drawing.md): Export a drawing: format pdf (every sheet in one PDF; needs the SciForge window) or dxf (the sheet: frame, views on their own layers, dimensions, text).

## View

- [`screenshot`](sciforge://docs/reference/screenshot.md): Take a picture (PNG) of the design as SciForge shows it, to see what you built.
- [`set_view`](sciforge://docs/reference/set_view.md): Turn the 3D view: orientation iso | home | front | back | top | bottom | left | right, fit (zoom so everything shows, default true), projection perspective | orthographic, or camera (a camera string get_view returned), or look_at: a face selector (the view looks straight at that face, Fusion's Look At).
- [`get_view`](sciforge://docs/reference/get_view.md): The 3D view's camera now (a string set_view takes back), its projection, and the saved named views of the design.
- [`named_view`](sciforge://docs/reference/named_view.md): Named views kept in the design (Fusion's Named Views): action save (the current camera under name), go (turn the view to it), delete, list.
- [`show_hide`](sciforge://docs/reference/show_hide.md): Show or hide bodies, components, sketches, construction geometry or drawings in the 3D view (they stay in the design).
- [`render`](sciforge://docs/reference/render.md): Take a picture of the design and get the image itself (PNG), to look at what was built.

## Shared rules

<a id="help-overview"></a>

### overview

SciForge is a parametric CAD program (built on FreeCAD) that works like Autodesk Fusion. These tools build and change the design open in SciForge step by step in its timeline, with the same code as SciForge's own dialogs; every change is one undo step. All lengths are in millimetres (mm) and all angles in degrees. Faces and edges are picked with selectors that describe their geometry (get_help topic selectors), never by internal names. Steps, sketches, bodies and components are named by the ids the tools report and get_design / get_timeline list (for example 'Sketch1', 'Extrude2'). A body is named by any step in it (the step that made it, usually). Errors come back as plain sentences: read them, fix the arguments and try again; a size that does not fit (a fillet radius, a shell thickness, a draft angle...) is refused with the largest value that does, never built smaller in its place. Read-only tools (inspect_design, query_geometry, check_design, render, diff_design, get_design, get_timeline, get_step, measure, physical_properties...) never change anything.

<a id="help-selectors"></a>

### selectors

A selector picks edges or faces by their geometry, the way a person would click them (never by names like "Edge7"). It is an object; every filter is optional, they combine with AND and apply in this order:

  type: for edges line, circle, ellipse or bspline; for faces plane, cylinder, cone, sphere, torus, bspline or extrusion (the side of an extruded spline or ellipse).

  normal: [x, y, z] (faces only) flat faces whose outward normal points this way.

  parallel: [x, y, z] straight edges parallel to this direction (either sense).

  along: [x, y, z] (faces only) faces running along this direction: the side walls of a part extruded that way (flat, round or free-form).

  radius: a number (mm): circles, cylinders and spheres with this radius.

  on_faces: a face selector (edges only): the edges that bound the faces it picks.

  not_on_faces: a face selector (edges only): the edges that do NOT bound those faces.

  at: {"axis": "x" | "y" | "z", "value": "max" | "min" | a number in mm}, or a list of them: keeps the elements whose centre lies at the extreme (or at that coordinate) along the axis, among those the filters above kept; a list applies each condition in turn.

  all: true: every edge or face (combine with nothing else except count).

  count: a whole number: the pick must contain exactly this many, or the tool fails instead of changing the wrong geometry. Always give it.

  any_of: [selector, ...]: the union of several selectors (each may have its own count).

Examples: the 4 top edges of a box {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}; the top face {"normal": [0, 0, 1], "count": 1}; one specific edge {"type": "line", "parallel": [0, 1, 0], "at": [{"axis": "x", "value": 5}, {"axis": "z", "value": 5}], "count": 1}.

Selectors look at the current body as it is now; call get_design first to see its size.

<a id="help-picks"></a>

### picks

A pick is one of {"plane": "XY"|"XZ"|"YZ"}, {"axis": "X"|"Y"|"Z"}, {"origin": true}, {"face": face selector}, {"edge": edge selector}, {"vertex": [x, y, z]} (a corner of the part) or {"construct": id} (a construction plane, axis or point made earlier). Face and edge selectors must pick exactly one element of the current body.

<a id="help-body_picks"></a>

### body_picks

A body pick is "XY" | "XZ" | "YZ" (an origin plane), "X" | "Y" | "Z" (an origin axis), {"face": selector, "of": step id}, {"edge": selector, "of": step id}, {"vertex": {"at": ...}, "of": step id} (a corner: the vertex selector takes only "at" conditions) or {"body": step id} (a whole body). "of" names a step whose body the selector looks at; left out, the body you are working on.

<a id="help-sketches"></a>

### sketches

Sketch planes are the origin planes: XY (normal +Z, sketch x/y are X/Y), XZ (normal -Y, sketch x/y are X/Z) and YZ (normal +X, sketch x/y are Y/Z). offset moves the sketch along that normal. Instead of a plane you can give face, a selector that picks exactly one flat face of the part; the sketch's x/y axes are then the ones SciForge gives that face, so prefer an origin plane with an offset when you can.

<a id="help-geometry"></a>

### geometry

Each geometry item is an object with exactly one of: rect [x0, y0, x1, y1] (two opposite corners), center_rect [cx, cy, width, height], circle [cx, cy, radius], polyline [[x, y], ...] (at least 3 corners, always closed), polygon {center: [x, y], radius, sides, rotation} (a regular polygon with its corners on that radius; rotation in degrees), slot [x1, y1, x2, y2, width] (a straight slot between two centre points), line [x0, y0, x1, y1] (one open line: it makes no area). Optional name: dimensions <name>.width, <name>.height, <name>.x, <name>.y (rectangles) or <name>.diameter, <name>.x, <name>.y (circles). Shapes inside each other make separate areas (a circle inside a rectangle makes a ring area and a disc area); extrude and revolve without regions use the outer areas with the shapes inside them as holes (that rectangle with its circle extrudes as a plate with a hole). Also: ellipse [cx, cy, major, minor] (major radius along x, the larger), spline_loop [[x, y], ...] (a closed smooth curve through at least 3 points), segments [{line: [x0, y0, x1, y1]} | {arc: [cx, cy, r, a0, a1]} | {spline: [[x, y], ...], tangents: [[tx, ty], [tx, ty]]}, ...] (a closed chain of lines, arcs counter-clockwise from a0 to a1 degrees, and open splines; each piece starts where the one before ends).

<a id="help-curves"></a>

### curves

Curves (paths, rails, rib curves) are given as "<sketch id>" (every curve of that sketch), {"sketch": id, "at": [x, y]} (the curve through that sketch point and the curves joined smoothly to it, like Fusion's chain selection; "chain": false for that curve alone; "at" may also be a list of points) or {"edge": edge selector} (edges of the part as it is now).

<a id="help-steps"></a>

### steps

Steps, sketches, bodies and components are named by the ids the tools report and get_design / get_timeline list (for example 'Sketch1', 'Extrude2'). A body is named by any step in it (the step that made it, usually).

<a id="help-expressions"></a>

### expressions

Value fields can follow a parameter: expressions {field: formula} (for example {"distance": "width / 2"}) keeps the field driven by that formula. User parameters are made with set_parameter; formulas use their names with + - * / ( ) and mm / deg units.

<a id="help-workflow"></a>

### workflow

1. inspect_design (or get_design, list_designs / new_design / open_design) to see what is there. 2. Build: create_sketch on a plane, then extrude / revolve / sweep / loft; primitive, coil, pipe, gear make solids directly; hole, thread, fillet, chamfer, shell, draft change the solid. 3. After every change check the numbers it answers (volumes, bounding boxes); diff_design since last_change says exactly what it did; query_geometry lists the faces / edges a selector picks (with a stable ref for each) before you fillet or chamfer them; check_design says whether the design is sound; render returns a picture (highlight shows what a selector picks). Trust the numbers first, the picture second. 4. Name things with set_parameter and expressions so the design stays easy to change; edit_step and set_model_parameter change what exists; get_timeline shows the history and roll_timeline / suppress_step / move_step / delete_step change it. 5. undo takes back the last change. 6. save / save_as / export / export_drawing write files.

<a id="help-checking"></a>

### checking

Check your work with numbers before trusting a picture. inspect_design: every body (valid?, volume, area, bounding box, centre of mass, faces / edges / corners), every step (state, error message, values), parameters, components, joints, the selection; it answers a snapshot id. diff_design since that id, since last_change or since a step id: what changed (bodies, steps, parameters). query_geometry: the faces / edges / corners a selector picks with their facts (type, area / length, normal, axis, radius, centre) and a ref, a selector that picks exactly that element: give it to fillet / chamfer / shell / draft, or pick ({"face": ref}) to measure / create_sketch. check_design: invalid or open solids, bodies in several pieces, failed steps, overlapping bodies. measure: the distance / angle between two picks, or the size of one. render: a PNG picture (iso, front, top... or a direction), highlight marks faces / edges in orange; it works without the window too (renderer software).

<a id="help-docs"></a>

### docs

SciForge's documentation for AI models is searchable: docs_search finds the sections that match a few words (with a snippet and a path#anchor), docs_read reads a document or one section, examples_search finds tested recipes and golden models by words, tool, op or tag. Start with handbook.md (how SciForge works, Fusion's ideas mapped to it, coordinates, undo, checking, recovering from failures), selectors.md (the selector cookbook) and recipes/index.md (step-by-step parts); reference/<tool>.md has every argument of a tool with a real example; user/ has SciForge's documentation for people. Over MCP the same documents are resources sciforge://docs/<path>, and sciforge://handbook is all of them in one file.
