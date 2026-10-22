# SciForge AI tools

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

SciForge offers 114 tools to AI apps (through MCP, the built-in chat panel and the command line), listed here in the order tools/list gives them. All lengths are in millimetres (mm) and all angles in degrees. Every tool that changes the design is one Undo step named "AI: ..."; errors come back as plain sentences. The same text is in each tool's description; the resource sciforge://tools has every schema as JSON.

## All tools

| Tool | Title | Category | Fusion command | Kind | Needs |
|---|---|---|---|---|---|
| [`get_design`](#get_design) | Get design | Inspect and measure | BROWSER (the design's bodies, sketches, parameters) and TIMELINE | read-only | nothing |
| [`screenshot`](#screenshot) | Screenshot | View | File > Capture Image | read-only | an open design, the SciForge window |
| [`measure`](#measure) | Measure | Inspect and measure | INSPECT > Measure | read-only | an open design |
| [`create_sketch`](#create_sketch) | Create sketch | Sketch | SOLID > CREATE > Create Sketch | changes the design (one Undo step) | nothing |
| [`extrude`](#extrude) | Extrude | Create (SOLID) | SOLID > CREATE > Extrude | changes the design (one Undo step) | an open design |
| [`revolve`](#revolve) | Revolve | Create (SOLID) | SOLID > CREATE > Revolve | changes the design (one Undo step) | an open design |
| [`fillet`](#fillet) | Fillet | Modify | SOLID > MODIFY > Fillet | changes the design (one Undo step) | a solid body |
| [`chamfer`](#chamfer) | Chamfer | Modify | SOLID > MODIFY > Chamfer | changes the design (one Undo step) | a solid body |
| [`hole`](#hole) | Hole | Create (SOLID) | SOLID > CREATE > Hole | changes the design (one Undo step) | a solid body |
| [`pattern`](#pattern) | Pattern | Create (SOLID) | SOLID > CREATE > Pattern > Rectangular / Circular Pattern (features) | changes the design (one Undo step) | a solid body |
| [`shell`](#shell) | Shell | Modify | SOLID > MODIFY > Shell | changes the design (one Undo step) | a solid body |
| [`set_parameter`](#set_parameter) | Set parameter | Parameters | MODIFY > Change Parameters (User Parameters, +) | changes the design (one Undo step) | nothing |
| [`undo`](#undo) | Undo | Designs and files | Quick Access Toolbar > Undo (Ctrl+Z) | changes the design (one Undo step) | an open design |
| [`redo`](#redo) | Redo | Designs and files | Quick Access Toolbar > Redo (Ctrl+Y) | changes the design (one Undo step) | an open design |
| [`save`](#save) | Save | Designs and files | Quick Access Toolbar > Save | writes files | an open design |
| [`export`](#export) | Export | Import and export | File > Export | writes files | an open design |
| [`create_curve_sketch`](#create_curve_sketch) | Create sketch of curves | Sketch | SOLID > CREATE > Create Sketch (lines, arcs, points) | changes the design (one Undo step) | nothing |
| [`add_to_sketch`](#add_to_sketch) | Add to sketch | Sketch | SKETCH > CREATE (Line, Rectangle, Circle, Arc, Polygon, Slot, Spline, Point) | changes the design (one Undo step) | an open design |
| [`get_sketch`](#get_sketch) | Get sketch | Sketch | BROWSER > Sketches (and the Sketch Palette) | read-only | an open design |
| [`sketch_constraint`](#sketch_constraint) | Sketch constraint | Sketch | SKETCH > CONSTRAINTS | changes the design (one Undo step) | an open design |
| [`sketch_dimension`](#sketch_dimension) | Sketch dimension | Sketch | SKETCH > CREATE > Sketch Dimension (D) | changes the design (one Undo step) | an open design |
| [`set_sketch_dimension`](#set_sketch_dimension) | Set sketch dimension | Sketch | SKETCH > double-click a dimension (or MODIFY > Change Parameters, Model Parameters) | changes the design (one Undo step) | an open design |
| [`sketch_delete`](#sketch_delete) | Delete in sketch | Sketch | SKETCH > select > Delete | changes the design (one Undo step), destructive | an open design |
| [`sketch_polygon`](#sketch_polygon) | Polygon | Sketch | SKETCH > CREATE > Polygon > Circumscribed / Inscribed Polygon | changes the design (one Undo step) | an open design |
| [`sketch_trim`](#sketch_trim) | Trim | Sketch | SKETCH > MODIFY > Trim (T) | changes the design (one Undo step) | an open design |
| [`sketch_text`](#sketch_text) | Text | Sketch | SKETCH > CREATE > Text | changes the design (one Undo step) | an open design |
| [`sweep`](#sweep) | Sweep | Create (SOLID) | SOLID > CREATE > Sweep | changes the design (one Undo step) | an open design |
| [`loft`](#loft) | Loft | Create (SOLID) | SOLID > CREATE > Loft | changes the design (one Undo step) | an open design |
| [`rib`](#rib) | Rib | Create (SOLID) | SOLID > CREATE > Rib | changes the design (one Undo step) | a solid body |
| [`web`](#web) | Web | Create (SOLID) | SOLID > CREATE > Web | changes the design (one Undo step) | a solid body |
| [`emboss`](#emboss) | Emboss | Create (SOLID) | SOLID > CREATE > Emboss | changes the design (one Undo step) | a solid body |
| [`thread`](#thread) | Thread | Create (SOLID) | SOLID > CREATE > Thread | changes the design (one Undo step) | a solid body |
| [`primitive`](#primitive) | Box / Cylinder / Sphere / Torus | Create (SOLID) | SOLID > CREATE > Box, Cylinder, Sphere, Torus | changes the design (one Undo step) | nothing |
| [`coil`](#coil) | Coil | Create (SOLID) | SOLID > CREATE > Coil | changes the design (one Undo step) | nothing |
| [`pipe`](#pipe) | Pipe | Create (SOLID) | SOLID > CREATE > Pipe | changes the design (one Undo step) | an open design |
| [`gear`](#gear) | Gear | Create (SOLID) | SOLID > CREATE > Gear | changes the design (one Undo step) | nothing |
| [`rectangular_pattern`](#rectangular_pattern) | Rectangular pattern | Create (SOLID) | SOLID > CREATE > Pattern > Rectangular Pattern | changes the design (one Undo step) | a solid body |
| [`circular_pattern`](#circular_pattern) | Circular pattern | Create (SOLID) | SOLID > CREATE > Pattern > Circular Pattern | changes the design (one Undo step) | a solid body |
| [`pattern_on_path`](#pattern_on_path) | Pattern on path | Create (SOLID) | SOLID > CREATE > Pattern > Pattern on Path | changes the design (one Undo step) | a solid body |
| [`mirror`](#mirror) | Mirror | Create (SOLID) | SOLID > CREATE > Mirror | changes the design (one Undo step) | a solid body |
| [`pattern_components`](#pattern_components) | Pattern components | Assemble | SOLID > CREATE > Pattern (Pattern Type: Components) | changes the design (one Undo step) | an open design |
| [`insert_hardware`](#insert_hardware) | Insert hardware | Assemble | INSERT > Hardware (McMaster-Carr / fasteners in Fusion) | changes the design (one Undo step) | a solid body |
| [`press_pull`](#press_pull) | Press pull | Modify | SOLID > MODIFY > Press Pull (Q) | changes the design (one Undo step) | a solid body |
| [`fillet_sets`](#fillet_sets) | Fillet / chamfer with sets | Modify | SOLID > MODIFY > Fillet / Chamfer (several selection sets, Chord Length, Variable) | changes the design (one Undo step) | a solid body |
| [`rule_fillet`](#rule_fillet) | Rule fillet | Modify | SOLID > MODIFY > Fillet (Type: Rule Fillet) | changes the design (one Undo step) | a solid body |
| [`full_round_fillet`](#full_round_fillet) | Full round fillet | Modify | SOLID > MODIFY > Fillet (Type: Full Round Fillet) | changes the design (one Undo step) | a solid body |
| [`draft`](#draft) | Draft | Modify | SOLID > MODIFY > Draft | changes the design (one Undo step) | a solid body |
| [`scale`](#scale) | Scale | Modify | SOLID > MODIFY > Scale | changes the design (one Undo step) | a solid body |
| [`combine`](#combine) | Combine | Modify | SOLID > MODIFY > Combine | changes the design (one Undo step) | an open design |
| [`split_body`](#split_body) | Split body | Modify | SOLID > MODIFY > Split Body | changes the design (one Undo step) | a solid body |
| [`split_face`](#split_face) | Split face | Modify | SOLID > MODIFY > Split Face | changes the design (one Undo step) | a solid body |
| [`silhouette_split`](#silhouette_split) | Silhouette split | Modify | SOLID > MODIFY > Silhouette Split | changes the design (one Undo step) | a solid body |
| [`replace_face`](#replace_face) | Replace face | Modify | SOLID > MODIFY > Replace Face | changes the design (one Undo step) | a solid body |
| [`delete_face`](#delete_face) | Delete face | Modify | SOLID > MODIFY > Delete (faces) | changes the design (one Undo step), destructive | a solid body |
| [`remove_bodies`](#remove_bodies) | Remove | Modify | SOLID > MODIFY > Remove | changes the design (one Undo step), destructive | an open design |
| [`delete_bodies`](#delete_bodies) | Delete bodies | Modify | BROWSER > a body > Delete | changes the design (one Undo step), destructive | an open design |
| [`move_copy`](#move_copy) | Move / copy | Modify | SOLID > MODIFY > Move/Copy (M) | changes the design (one Undo step) | an open design |
| [`align`](#align) | Align | Modify | SOLID > MODIFY > Align | changes the design (one Undo step) | a solid body |
| [`physical_material`](#physical_material) | Physical material | Modify | SOLID > MODIFY > Physical Material | changes the design (one Undo step) | an open design |
| [`list_materials`](#list_materials) | List materials | Modify | SOLID > MODIFY > Physical Material / Appearance (libraries) | read-only | nothing |
| [`appearance`](#appearance) | Appearance | Modify | SOLID > MODIFY > Appearance (A) | changes the design (one Undo step) | an open design |
| [`capture_design_history`](#capture_design_history) | Capture design history | Timeline (history) | the design's menu: Capture Design History / Do Not Capture Design History | changes the design (one Undo step), destructive | an open design |
| [`surface`](#surface) | Surface | Surface | SURFACE > CREATE / MODIFY (Extrude, Revolve, Sweep, Loft, Patch, Ruled, Offset, Boundary Fill, Thicken, Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal) | changes the design (one Undo step) | nothing |
| [`construct_plane`](#construct_plane) | Construction plane | Construct | SOLID > CONSTRUCT > (planes) | changes the design (one Undo step) | an open design |
| [`construct_axis`](#construct_axis) | Construction axis | Construct | SOLID > CONSTRUCT > (axes) | changes the design (one Undo step) | an open design |
| [`construct_point`](#construct_point) | Construction point | Construct | SOLID > CONSTRUCT > (points) | changes the design (one Undo step) | an open design |
| [`new_component`](#new_component) | New component | Assemble | ASSEMBLE > New Component | changes the design (one Undo step) | nothing |
| [`components_from_bodies`](#components_from_bodies) | Components from bodies | Assemble | BROWSER > a body > Create Components from Bodies | changes the design (one Undo step) | an open design |
| [`copy_component`](#copy_component) | Copy / paste component | Assemble | Copy (Ctrl+C) a component, then Paste / Paste New | changes the design (one Undo step) | an open design |
| [`activate`](#activate) | Activate body / component | Assemble | BROWSER > a body or component > Activate | changes the design (one Undo step) | an open design |
| [`new_body`](#new_body) | New body | Assemble | BROWSER > Bodies > New Body | changes the design (one Undo step) | nothing |
| [`joint`](#joint) | Joint | Assemble | ASSEMBLE > Joint (J) | changes the design (one Undo step) | an open design |
| [`drive_joint`](#drive_joint) | Drive joint | Assemble | ASSEMBLE > Drive Joints | changes the design (one Undo step) | an open design |
| [`ground`](#ground) | Ground / unground | Assemble | BROWSER > a component > Ground | changes the design (one Undo step) | an open design |
| [`physical_properties`](#physical_properties) | Physical properties | Inspect and measure | BROWSER > a body > Properties (INSPECT) | read-only | an open design |
| [`center_of_mass`](#center_of_mass) | Center of mass | Inspect and measure | INSPECT > Center of Mass | read-only | a solid body |
| [`interference`](#interference) | Interference | Inspect and measure | INSPECT > Interference | read-only | a solid body |
| [`section_analysis`](#section_analysis) | Section analysis | Inspect and measure | INSPECT > Section Analysis | read-only | a solid body |
| [`get_timeline`](#get_timeline) | Get timeline | Timeline (history) | TIMELINE (the bar at the bottom) | read-only | an open design |
| [`get_step`](#get_step) | Get step | Timeline (history) | TIMELINE > double-click a step (the dialog's fields) | read-only | an open design |
| [`edit_step`](#edit_step) | Edit step | Timeline (history) | TIMELINE > double-click a step > change its fields > OK | changes the design (one Undo step) | an open design |
| [`roll_timeline`](#roll_timeline) | Move history marker | Timeline (history) | TIMELINE > drag the history marker (and the playback buttons) | changes the design (one Undo step) | an open design |
| [`suppress_step`](#suppress_step) | Suppress / unsuppress | Timeline (history) | TIMELINE > right-click a step > Suppress Features | changes the design (one Undo step) | an open design |
| [`delete_step`](#delete_step) | Delete step | Timeline (history) | TIMELINE > right-click a step > Delete | changes the design (one Undo step), destructive | an open design |
| [`move_step`](#move_step) | Reorder step | Timeline (history) | TIMELINE > drag a step | changes the design (one Undo step) | an open design |
| [`rename`](#rename) | Rename | Timeline (history) | TIMELINE / BROWSER > right-click > Rename | changes the design (one Undo step) | an open design |
| [`group_steps`](#group_steps) | Group steps | Timeline (history) | TIMELINE > select steps > right-click > Group | changes the design (one Undo step) | an open design |
| [`list_parameters`](#list_parameters) | List parameters | Parameters | MODIFY > Change Parameters | read-only | an open design |
| [`delete_parameter`](#delete_parameter) | Delete parameter | Parameters | MODIFY > Change Parameters > a user parameter > Delete | changes the design (one Undo step), destructive | an open design |
| [`set_model_parameter`](#set_model_parameter) | Set model parameter | Parameters | MODIFY > Change Parameters > Model Parameters | changes the design (one Undo step) | an open design |
| [`new_design`](#new_design) | New design | Designs and files | File > New Design | changes the design (one Undo step) | nothing |
| [`open_design`](#open_design) | Open design | Designs and files | File > Open | read-only | nothing |
| [`save_as`](#save_as) | Save as | Designs and files | File > Save As | writes files | an open design |
| [`close_design`](#close_design) | Close design | Designs and files | File > Close | changes the design (one Undo step), destructive | an open design |
| [`list_designs`](#list_designs) | List designs | Designs and files | the design tabs | read-only | nothing |
| [`switch_design`](#switch_design) | Switch design | Designs and files | click a design tab | read-only | nothing |
| [`import_file`](#import_file) | Insert file | Import and export | INSERT > Insert Mesh / Insert DXF / Insert STEP, and Insert into Current Design | changes the design (one Undo step) | nothing |
| [`create_drawing`](#create_drawing) | Create drawing | Drawings | File > New Drawing > From Design | changes the design (one Undo step) | a solid body |
| [`add_drawing_view`](#add_drawing_view) | Add drawing view | Drawings | DRAWING > CREATE > Base View / Projected View / Section View / Detail View | changes the design (one Undo step) | a drawing |
| [`add_drawing_dimension`](#add_drawing_dimension) | Add drawing dimension | Drawings | DRAWING > DIMENSIONS > Dimension | changes the design (one Undo step) | a drawing |
| [`add_drawing_annotation`](#add_drawing_annotation) | Add drawing annotation | Drawings | DRAWING > TEXT / TABLES / SYMBOLS (Text, Table (parts list), Center Mark) | changes the design (one Undo step) | a drawing |
| [`get_drawing`](#get_drawing) | Get drawing | Drawings | BROWSER > Drawings | read-only | a drawing |
| [`export_drawing`](#export_drawing) | Export drawing | Drawings | DRAWING > EXPORT > Output PDF / Output DXF | writes files | a drawing |
| [`set_view`](#set_view) | Set view | View | NAVIGATION BAR and VIEWCUBE (Home, Fit, Orbit, Look At) | read-only | an open design, the SciForge window |
| [`get_view`](#get_view) | Get view | View | (the 3D view's camera) | read-only | an open design, the SciForge window |
| [`named_view`](#named_view) | Named view | View | BROWSER > Named Views (New Named View, go to, delete) | changes the design (one Undo step) | an open design |
| [`show_hide`](#show_hide) | Show / hide | View | BROWSER > the eye icon (Show / Hide) | changes the design (one Undo step) | an open design |
| [`get_help`](#get_help) | Get help | Help | (SciForge's documentation for AI models) | read-only | nothing |
| [`list_tools`](#list_tools) | List tools | Help | (SciForge's command list) | read-only | nothing |
| [`inspect_design`](#inspect_design) | Inspect design | Inspect and measure | BROWSER + TIMELINE + Properties (everything at once) | read-only | nothing |
| [`query_geometry`](#query_geometry) | Query geometry | Inspect and measure | Selection filters + INSPECT > Measure (on what a selector picks) | read-only | an open design |
| [`check_design`](#check_design) | Check design | Inspect and measure | INSPECT > Interference + the timeline's warnings | read-only | an open design |
| [`render`](#render) | Render | View | File > Capture Image (returned to the AI as a picture) | read-only | an open design |
| [`diff_design`](#diff_design) | Diff design | Inspect and measure | TIMELINE (compare before and after) | read-only | an open design |

## Help

<a id="get_help"></a>

### `get_help`: Get help

Fusion: (SciForge's documentation for AI models). Read-only. Needs nothing.

Read SciForge's rules for AI tools: overview, selectors (how to pick faces and edges), picks (planes, axes, faces, edges, corners), body_picks, sketches (planes and coordinates), geometry (sketch shapes), curves (paths and rails), steps (ids), expressions (parameters in fields), workflow (how to build and check a part), checking (the tools that check your work with numbers and pictures), tools (every tool by category with its Fusion command). Without topic: overview.

| Argument | Type | Default | Description |
|---|---|---|---|
| `topic` | `overview` \| `selectors` \| `picks` \| `body_picks` \| `sketches` \| `geometry` \| `curves` \| `steps` \| `expressions` \| `workflow` \| `checking` \| `tools` | `"overview"` |  |

Examples:

- how selectors pick faces and edges:
  `{"topic": "selectors"}`

<a id="list_tools"></a>

### `list_tools`: List tools

Fusion: (SciForge's command list). Read-only. Needs nothing.

List every tool by category with its Fusion command, whether it changes the design, and whether it can run right now (and why not: no design open, no solid yet, needs the SciForge window...). category: only that category.

| Argument | Type | Default | Description |
|---|---|---|---|
| `category` | `help` \| `document` \| `inspect` \| `sketch` \| `create` \| `modify` \| `surface` \| `construct` \| `assemble` \| `timeline` \| `parameters` \| `import_export` \| `drawing` \| `view` |  |  |

Examples:

- the Modify tools and which can run now:
  `{"category": "modify"}`

## Designs and files

<a id="undo"></a>

### `undo`: Undo

Fusion: Quick Access Toolbar > Undo (Ctrl+Z). Changes the design (one Undo step). Needs an open design.

Undo the last change in SciForge (each AI change is one undo step).

No arguments.

Examples:

- take back the last change:
  `{}`

<a id="redo"></a>

### `redo`: Redo

Fusion: Quick Access Toolbar > Redo (Ctrl+Y). Changes the design (one Undo step). Needs an open design.

Redo the change undo took back (one AI call or one SciForge command at a time; a new change after an undo clears what could be redone).

No arguments.

Examples:

- do again what undo took back:
  `{}`

<a id="save"></a>

### `save`: Save

Fusion: Quick Access Toolbar > Save. Writes files. Needs an open design.

Save the design. Without path it is saved where it is (a new design asks for a place in SciForge). With path (a full path ending in .FCStd) it is saved there; saving over another existing file must be confirmed by the person in SciForge.

| Argument | Type | Default | Description |
|---|---|---|---|
| `path` | string |  |  |

Examples:

- save under that name:
  `{"path": "/home/me/designs/bracket.FCStd"}`

<a id="new_design"></a>

### `new_design`: New design

Fusion: File > New Design. Changes the design (one Undo step). Needs nothing.

Start a new, empty design (with one body) and make it the active one. name: its name.

| Argument | Type | Default | Description |
|---|---|---|---|
| `name` | string | `"Untitled"` | the design's name |

Examples:

- a new design called Bracket:
  `{"name": "Bracket"}`

<a id="open_design"></a>

### `open_design`: Open design

Fusion: File > Open. Read-only. Needs nothing.

Open a design (.FCStd) or a STEP / IGES file as a new design (its components and bodies kept). A design that is already open comes to the front. It becomes the active design.

| Argument | Type | Default | Description |
|---|---|---|---|
| `path` (required) | string |  | full path of the file |

Examples:

- open a saved design:
  `{"path": "/home/me/designs/bracket.FCStd"}`

<a id="save_as"></a>

### `save_as`: Save as

Fusion: File > Save As. Writes files. Needs an open design.

Save the design under a new name (a full path ending in .FCStd); the design then lives there. Replacing another existing file must be confirmed by the person in SciForge.

| Argument | Type | Default | Description |
|---|---|---|---|
| `path` (required) | string |  | full path ending in .FCStd |

Examples:

- a copy under a new name:
  `{"path": "/home/me/designs/bracket-v2.FCStd"}`

<a id="close_design"></a>

### `close_design`: Close design

Fusion: File > Close. Changes the design (one Undo step), destructive. Needs an open design.

Close a design (default: the active one). Unsaved changes are refused unless discard_changes is true (the person in SciForge is asked first).

| Argument | Type | Default | Description |
|---|---|---|---|
| `design` | string |  | the design's name (list_designs) |
| `discard_changes` | boolean | `false` | close even with unsaved changes |

Examples:

- close the active design (it must be saved):
  `{}`

<a id="list_designs"></a>

### `list_designs`: List designs

Fusion: the design tabs. Read-only. Needs nothing.

List the open designs: name, label, file, whether it has unsaved changes and which one is active.

No arguments.

Examples:

- which designs are open:
  `{}`

<a id="switch_design"></a>

### `switch_design`: Switch design

Fusion: click a design tab. Read-only. Needs nothing.

Make another open design the active one (the tools then work on it).

| Argument | Type | Default | Description |
|---|---|---|---|
| `design` (required) | string |  | its name or label (list_designs) |

Examples:

- work on Bracket:
  `{"design": "Bracket"}`

## Inspect and measure

<a id="get_design"></a>

### `get_design`: Get design

Fusion: BROWSER (the design's bodies, sketches, parameters) and TIMELINE. Read-only. Needs nothing.

Describe the open SciForge design: its bodies (volume in mm3, bounding box in mm), the timeline steps with their ids (use these ids in profile, sketch and features arguments), the user parameters and the sketches with their areas. Call it before changing a design and after each change to check the result. All lengths are in millimetres (mm) and all angles in degrees.

No arguments.

Examples:

- everything about the open design, as JSON:
  `{}`

<a id="measure"></a>

### `measure`: Measure

Fusion: INSPECT > Measure. Read-only. Needs an open design.

Measure between two picks a and b of the current body or the origin: the minimum distance (mm) and, where it makes sense, the angle (degrees), like SciForge's Measure tool; also the X / Y / Z distances, the two nearest points and what each pick is (length, area, radius...). Only a: the size of that one pick (an edge's length and radius, a face's area and perimeter). (rules: [picks](#help-picks)) (rules: [selectors](#help-selectors))

| Argument | Type | Default | Description |
|---|---|---|---|
| `a` (required) | object |  | the first pick. (rules: [picks](#help-picks)) |
| `b` | object |  | the second pick (optional). (rules: [picks](#help-picks)) |

Examples:

- the height of the top face above the XY plane:
  `{"a": {"face": {"normal": [0, 0, 1], "count": 1}}, "b": {"plane": "XY"}}`

<a id="physical_properties"></a>

### `physical_properties`: Physical properties

Fusion: BROWSER > a body > Properties (INSPECT). Read-only. Needs an open design.

Physical properties of bodies, as Fusion's Properties: volume (mm3), area (mm2), material and density, mass (g), centre of mass and bounding box (mm), number of faces, edges and solids, and whether the solid is valid. bodies: step ids (default every body).

| Argument | Type | Default | Description |
|---|---|---|---|
| `bodies` | array of strings |  | the bodies (default: all) |

Examples:

- every body's mass, volume and centre of mass:
  `{}`

<a id="center_of_mass"></a>

### `center_of_mass`: Center of mass

Fusion: INSPECT > Center of Mass. Read-only. Needs a solid body.

The centre of mass of bodies together (Fusion's Center of Mass), weighted by their materials. bodies: step ids (default every body).

| Argument | Type | Default | Description |
|---|---|---|---|
| `bodies` | array of strings |  | the bodies (default: all) |

Examples:

- where the whole design balances:
  `{}`

<a id="interference"></a>

### `interference`: Interference

Fusion: INSPECT > Interference. Read-only. Needs a solid body.

Find where bodies overlap (Fusion's Interference): every pair that overlaps with the overlapping volume (mm3). bodies: step ids (default every body); include_coincident: count bodies that only touch.

| Argument | Type | Default | Description |
|---|---|---|---|
| `bodies` | array of strings |  | the bodies (default: all) |
| `include_coincident` | boolean | `false` |  |

Examples:

- do any parts collide?:
  `{}`

<a id="section_analysis"></a>

### `section_analysis`: Section analysis

Fusion: INSPECT > Section Analysis. Read-only. Needs a solid body.

Cut the design with a plane to look inside (Fusion's Section Analysis): plane (a pick: an origin plane or a flat face), distance (offset, mm), x_angle / y_angle (tilt, degrees), flip. Answers the volume kept (on the side the plane's normal points away from) and the area of the cut faces; nothing is left in the design.

| Argument | Type | Default | Description |
|---|---|---|---|
| `plane` (required) | object |  | the section plane. (rules: [picks](#help-picks)) |
| `distance` | number | `0` | (mm) |
| `x_angle` | number | `0` | (degrees) |
| `y_angle` | number | `0` | (degrees) |
| `flip` | boolean | `false` |  |

Examples:

- a cut 5 mm from XZ:
  `{"plane": {"plane": "XZ"}, "distance": 5}`

<a id="inspect_design"></a>

### `inspect_design`: Inspect design

Fusion: BROWSER + TIMELINE + Properties (everything at once). Read-only. Needs nothing.

Read the whole design as numbers, to check work before trusting a picture: every body (valid solid or not, volume mm3, area mm2, bounding box and size mm, centre of mass, number of solids, faces, edges and corners, material and mass, shown or hidden); every timeline step in order (id, name, kind, body, done or rolled back, suppressed, status and the error message when it failed, its main values; detail full adds every option as get_step shows them); user parameters; components and joints; construction geometry; sketches (closed areas, fully constrained); drawings; and what is selected in SciForge (window only). The answer has a snapshot id: diff_design since it shows what changed later. bodies: only these (step ids).

| Argument | Type | Default | Description |
|---|---|---|---|
| `detail` | `summary` \| `full` | `"summary"` | full adds every step's definition |
| `bodies` | array of strings |  | only these bodies (default: all) |

Examples:

- everything about the open design, with a snapshot id:
  `{}`
- also every step's options:
  `{"detail": "full"}`

<a id="query_geometry"></a>

### `query_geometry`: Query geometry

Fusion: Selection filters + INSPECT > Measure (on what a selector picks). Read-only. Needs an open design.

List the faces, edges or corners (vertices) of a body or step that a selector picks, with facts about each: type (plane, cylinder... / line, circle...), area mm2 or length mm, centre, normal of flat faces, axis and radius of round ones, start / end and direction of edges, bounding box. Each comes with ref: a selector that picks exactly that one element by its geometry (stable when FreeCAD renumbers faces), and pick: the same ready for measure, create_sketch face, construct_plane... Pass ref straight to fillet, chamfer, shell, draft (edges / faces) to change exactly that element. of: a body or step id (default the body being worked on; a step: the solid as it was after that step). element: faces (default), edges or vertices. select: a selector (default all; for vertices only at / all / count). limit: at most this many (default 60).

| Argument | Type | Default | Description |
|---|---|---|---|
| `of` | string |  | the body or step (default: the body being worked on) |
| `element` | `faces` \| `edges` \| `vertices` | `"faces"` |  |
| `select` | object |  | a selector (see get_help topic selectors); vertices take only at / all / count. Default: all |
| `limit` | integer | `60` | at most this many elements (>= 1, <= 500) |
| `refs` | boolean | `true` | give each element its stable reference |

Examples:

- every round face: the holes and bosses:
  `{"select": {"type": "cylinder"}}`
- the edges at the top, each with a selector fillet can take:
  `{"element": "edges", "select": {"at": {"axis": "z", "value": "max"}}}`
- the corners after Extrude1:
  `{"of": "Extrude1", "element": "vertices"}`

<a id="check_design"></a>

### `check_design`: Check design

Fusion: INSPECT > Interference + the timeline's warnings. Read-only. Needs an open design.

Check that the design is sound, before saving or exporting it: every body is one valid, closed solid (invalid or open shapes, bodies made of several pieces, empty bodies), timeline steps that failed or warn (with the reason), steps left after the history marker, suppressed steps, sketches with conflicting constraints, and bodies that overlap (Fusion's Interference; interference: false skips it, it takes longest). Answers ok (true when there are no problems), the problems and warnings in plain sentences, and the facts behind them. bodies: only these (step ids).

| Argument | Type | Default | Description |
|---|---|---|---|
| `interference` | boolean | `true` | look for bodies that overlap |
| `bodies` | array of strings |  | only these bodies (default: all) |

Examples:

- is everything valid and nothing broken or overlapping?:
  `{}`

<a id="diff_design"></a>

### `diff_design`: Diff design

Fusion: TIMELINE (compare before and after). Read-only. Needs an open design.

What changed in the design since: a snapshot id that inspect_design answered ("S3"), "last_change" (just before the latest change an AI made: what that change did), or a step id (the solid as it was right after that step, compared with now: what the later steps did). Answers the bodies added, removed and changed (volume, area, size, faces, edges before and after), the timeline steps added, removed or changed (values, state, status) and the parameters changed.

| Argument | Type | Default | Description |
|---|---|---|---|
| `since` (required) | string |  | a snapshot id ("S1"), "last_change" or a step id |

Examples:

- what the last change did:
  `{"since": "last_change"}`
- everything that changed since inspect_design gave S1:
  `{"since": "S1"}`
- what the steps after Extrude1 did to the solid:
  `{"since": "Extrude1"}`

## Sketch

<a id="create_sketch"></a>

### `create_sketch`: Create sketch

Fusion: SOLID > CREATE > Create Sketch. Changes the design (one Undo step). Needs nothing.

Create a sketch with closed shapes (and lines) in it, ready for extrude, revolve or hole. It becomes one timeline step; its id is the profile for the next tools. (rules: [sketches](#help-sketches)) (rules: [geometry](#help-geometry)) on: the id of a construction plane (construct_plane) to sketch on instead. auto_project (with face): the face's edges are projected into the sketch, as Fusion does. All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `plane` | `XY` \| `XZ` \| `YZ` |  |  |
| `offset` | number | `0` | mm along the plane's normal |
| `face` | object |  | Instead of plane: the flat face to sketch on (one face). (rules: [selectors](#help-selectors)) |
| `on` | string |  | Instead of plane: the id of a construction plane to sketch on |
| `auto_project` | boolean |  | with face: project the face's edges into the sketch |
| `geometry` (required) | array of objects |  | (rules: [geometry](#help-geometry)) |

Examples:

- a 40 x 20 mm rectangle on the XY plane, its sizes named base.width / base.height:
  `{"plane": "XY", "geometry": [{"rect": [0, 0, 40, 20], "name": "base"}]}`
- a 6 mm circle 10 mm above XY (on top of a 10 mm thick part):
  `{"plane": "XY", "offset": 10, "geometry": [{"circle": [20, 10, 3]}]}`

<a id="create_curve_sketch"></a>

### `create_curve_sketch`: Create sketch of curves

Fusion: SOLID > CREATE > Create Sketch (lines, arcs, points). Changes the design (one Undo step). Needs nothing.

Create a sketch of open curves and points: the paths, rails, guide curves and rib / web curves that sweep, loft, pipe, rib, web, pattern_on_path and split_body use, and points for holes and lofts. Arcs run counter-clockwise from a0 to a1 (degrees); a polyline stays open. Closed shapes (areas) are made with create_sketch. (rules: [sketches](#help-sketches)) All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `plane` (required) | `XY` \| `XZ` \| `YZ` |  |  |
| `offset` | number | `0` | mm along the plane's normal |
| `curves` (required) | array of objects |  | the curves and points |

Examples:

- a sweep path: a straight line up, then a quarter arc:
  `{"plane": "XZ", "curves": [{"line": [0, 0, 0, 40]}, {"arc": [20, 40, 20, 90, 180]}]}`
- two sketch points (hole centres):
  `{"plane": "XY", "curves": [{"point": [10, 10]}, {"point": [30, 10]}]}`

<a id="add_to_sketch"></a>

### `add_to_sketch`: Add to sketch

Fusion: SKETCH > CREATE (Line, Rectangle, Circle, Arc, Polygon, Slot, Spline, Point). Changes the design (one Undo step). Needs an open design.

Draw more in an existing sketch (Fusion: edit the sketch and draw): closed shapes (geometry, the same items as create_sketch, with their named dimensions) and open curves or points (curves, the same items as create_curve_sketch). construction: true draws construction geometry (dashed, it makes no area: guides for constraints and axes). Coordinates are the sketch's own x / y (see get_sketch). Everything built from the sketch updates. (rules: [geometry](#help-geometry)) All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` (required) | string |  | the sketch to draw in |
| `geometry` | array of objects |  | closed shapes |
| `curves` | array of objects |  | open curves and points |
| `construction` | boolean | `false` | construction geometry |

Examples:

- a circle (bore.diameter) added to Sketch1:
  `{"sketch": "Sketch1", "geometry": [{"circle": [20, 10, 4], "name": "bore"}]}`
- a construction line (for example a revolve axis):
  `{"sketch": "Sketch1", "curves": [{"line": [0, -5, 0, 25]}], "construction": true}`

<a id="get_sketch"></a>

### `get_sketch`: Get sketch

Fusion: BROWSER > Sketches (and the Sketch Palette). Read-only. Needs an open design.

Read a sketch: its plane and placement, every curve by index (type, points, radius, construction or not), every constraint by index (type, name, the curves it ties, its value for dimensions, driving or not), how many degrees of freedom are left (0: fully constrained, Fusion's padlock), the constraints that conflict or are redundant, and its closed areas (with a point inside each, for regions). Use the indexes in sketch_constraint, sketch_dimension, set_sketch_dimension and sketch_delete.

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` (required) | string |  | the sketch to read |

Examples:

- curves, constraints and areas of Sketch1:
  `{"sketch": "Sketch1"}`

<a id="sketch_constraint"></a>

### `sketch_constraint`: Sketch constraint

Fusion: SKETCH > CONSTRAINTS. Changes the design (one Undo step). Needs an open design.

Add a geometric constraint to a sketch, as Fusion's Constraints panel: coincident (two points, or a point on a curve), horizontal / vertical (a line, or two points), parallel, perpendicular, tangent, equal, collinear (two lines), concentric (two circles or arcs), midpoint (a point and a line or arc), symmetric (two points or curves and the line they mirror about, third), fix (lock a curve or point), point_on (a point on a curve), smooth (G2 where a spline meets a curve; tangent only when the solver cannot keep curvature). items are curves by index (get_sketch) with the point that matters. A constraint that conflicts with the sketch is not added: the answer names the constraints it fights with.

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` (required) | string |  | the sketch |
| `kind` (required) | `coincident` \| `horizontal` \| `vertical` \| `parallel` \| `perpendicular` \| `tangent` \| `equal` \| `symmetric` \| `concentric` \| `collinear` \| `midpoint` \| `fix` \| `point_on` \| `smooth` |  |  |
| `items` (required) | array of objects |  | the curves / points it ties, in order |

Examples:

- make line 0 horizontal:
  `{"sketch": "Sketch1", "kind": "horizontal", "items": [{"curve": 0}]}`
- put circle 4's centre on the sketch origin:
  `{"sketch": "Sketch1", "kind": "coincident", "items": [{"curve": 4, "point": "center"}, {"curve": -1, "point": "start"}]}`

<a id="sketch_dimension"></a>

### `sketch_dimension`: Sketch dimension

Fusion: SKETCH > CREATE > Sketch Dimension (D). Changes the design (one Undo step). Needs an open design.

Add a driving dimension to a sketch, like Fusion's Sketch Dimension: distance (between two points, a point and a line, or one line's length), distance_x / distance_y (horizontal / vertical), radius, diameter, angle (between two lines, or of one line to the x axis). value in mm or degrees, or expression: a formula with parameters ("width / 2"). name names it for set_sketch_dimension and expressions. A dimension that over-constrains the sketch is refused with the constraints it conflicts with.

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` (required) | string |  | the sketch |
| `kind` (required) | `distance` \| `distance_x` \| `distance_y` \| `radius` \| `diameter` \| `angle` |  |  |
| `items` (required) | array of objects |  | the curves / points measured |
| `value` | number |  | mm (lengths) or degrees (angles) |
| `expression` | string |  | a formula instead of value, e.g. width / 2 |
| `name` | string |  | a name, e.g. slot.width |

Examples:

- circle 4 is 8 mm across:
  `{"sketch": "Sketch1", "kind": "diameter", "items": [{"curve": 4}], "value": 8, "name": "bore.diameter"}`
- the circle's centre at half the width:
  `{"sketch": "Sketch1", "kind": "distance_x", "items": [{"curve": -1, "point": "start"}, {"curve": 4, "point": "center"}], "expression": "width / 2"}`

<a id="set_sketch_dimension"></a>

### `set_sketch_dimension`: Set sketch dimension

Fusion: SKETCH > double-click a dimension (or MODIFY > Change Parameters, Model Parameters). Changes the design (one Undo step). Needs an open design.

Change a sketch dimension: by its name (rectangles made by create_sketch with a name have <name>.width, <name>.height, <name>.x, <name>.y; circles <name>.diameter, <name>.x, <name>.y) or by its index (get_sketch). value in mm / degrees, or expression (a formula with parameters; an empty expression removes the formula). Everything built from the sketch updates; steps that break are named in the answer.

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` (required) | string |  | the sketch |
| `constraint` | string |  | the dimension's name, e.g. base.width |
| `index` | integer |  | the constraint's index (get_sketch) (>= 0) |
| `value` | number |  | mm or degrees |
| `expression` | string |  | a formula, e.g. width * 2 |

Examples:

- make the rectangle 60 mm wide:
  `{"sketch": "Sketch1", "constraint": "base.width", "value": 60}`

<a id="sketch_delete"></a>

### `sketch_delete`: Delete in sketch

Fusion: SKETCH > select > Delete. Changes the design (one Undo step), destructive. Needs an open design.

Delete curves and / or constraints of a sketch by their indexes (get_sketch). Deleting a curve deletes the constraints on it too. Indexes after the deleted ones move down: call get_sketch again before the next edit.

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` (required) | string |  | the sketch |
| `curves` | array of integers |  | curve indexes |
| `constraints` | array of integers |  | constraint indexes |

Examples:

- delete curve 3:
  `{"sketch": "Sketch1", "curves": [3]}`

<a id="sketch_polygon"></a>

### `sketch_polygon`: Polygon

Fusion: SKETCH > CREATE > Polygon > Circumscribed / Inscribed Polygon. Changes the design (one Undo step). Needs an open design.

Add a regular polygon to a sketch, Fusion's way: center and point, where point is the middle of an edge (circumscribed, default) or a corner (inscribed). diameter dimensions it (across flats when circumscribed, across corners when inscribed), named <name>.diameter. All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` (required) | string |  | the sketch |
| `center` (required) | array of 2 numbers |  | [x, y] in sketch coordinates (mm) |
| `point` (required) | array of 2 numbers |  | the middle of an edge (circumscribed) or a corner (inscribed) |
| `sides` (required) | integer |  | number of sides (>= 3) |
| `circumscribed` | boolean | `true` | point is the middle of an edge |
| `diameter` | number |  | across flats / corners, mm (> 0) |
| `name` | string |  | names its dimension <name>.diameter |

Examples:

- a hexagon 10 mm across flats:
  `{"sketch": "Sketch1", "center": [0, 0], "point": [5, 0], "sides": 6, "diameter": 10, "name": "nut"}`

<a id="sketch_trim"></a>

### `sketch_trim`: Trim

Fusion: SKETCH > MODIFY > Trim (T). Changes the design (one Undo step). Needs an open design.

Trim sketch curves, as clicking Trim at each point in turn: the curve nearest the point loses the piece between its neighbouring intersections. Points are [x, y] in the sketch's coordinates, on the piece to remove.

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` (required) | string |  | the sketch |
| `points` (required) | array of arrays |  | one Trim click each |

Examples:

- remove the piece of curve through (20, 0):
  `{"sketch": "Sketch1", "points": [[20, 0]]}`

<a id="sketch_text"></a>

### `sketch_text`: Text

Fusion: SKETCH > CREATE > Text. Changes the design (one Undo step). Needs an open design.

Write text in a sketch (Fusion's sketch Text): its letters become areas you can extrude (profile: the text's id) or emboss. corner is the frame's top-left corner in sketch coordinates, height the letter height (mm); font a font family installed on the computer (default: SciForge's), bold, italic, angle (degrees), h_align left | center | right, v_align top | middle | bottom, width / frame_height: the text frame (0: fits the text), spacing (extra letter spacing).

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` (required) | string |  | the sketch to write in |
| `text` (required) | string |  | the text |
| `height` | number | `5` | letter height (mm) (> 0) |
| `corner` | array of 2 numbers |  | the frame's top-left corner [x, y] |
| `font` | string |  | a font family |
| `bold` | boolean | `false` |  |
| `italic` | boolean | `false` |  |
| `angle` | number | `0` | degrees |
| `h_align` | `left` \| `center` \| `right` | `"left"` |  |
| `v_align` | `top` \| `middle` \| `bottom` | `"top"` |  |
| `width` | number |  | frame width (mm, 0: fits the text) (>= 0) |
| `frame_height` | number |  | frame height (mm, 0: fits the text) (>= 0) |
| `spacing` | number |  | extra letter spacing |

Examples:

- a 6 mm high text; extrude it with profile = the text's id:
  `{"sketch": "Sketch2", "text": "SciForge", "height": 6, "corner": [2, 18]}`

## Create (SOLID)

<a id="extrude"></a>

### `extrude`: Extrude

Fusion: SOLID > CREATE > Extrude. Changes the design (one Undo step). Needs an open design.

Extrude a sketch's areas into a solid (SciForge's Extrude). distance goes along the sketch normal; flip: true goes the other way, for cuts too: a cut from a sketch lying on top of the part needs flip: true. regions picks some areas by a point inside each ([x, y] in sketch coordinates); without it every area is used. direction one_side (default), symmetric (distance is the whole length, half on each side) or two_sides (distance one way, distance2 the other). through_all goes through the whole part instead of a distance. taper in degrees. More of Fusion's dialog: face (a flat face of the part as the profile, instead of a sketch), more_profiles (more sketches extruded together), to (Extent To Object: a plane, a face or a body to stop at), extent2 / to2 / taper2 (side two), measurement (symmetric: whole or half length), start (profile, offset with start_offset, or object with start_from), thin {location side1|center|side2, thickness, location2, thickness2} (a Thin Extrude: a wall along the profile; with curves it extrudes open sketch curves), bodies (Bodies to Cut / Join: auto or step ids), extend / object_offset (To Object). All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `profile` | string |  | id of a create_sketch step |
| `regions` | array of arrays |  |  |
| `distance` | number |  | (> 0) |
| `operation` | `join` \| `cut` \| `intersect` \| `new_body` | `"join"` | join adds to the current body, cut removes from it, intersect keeps only the overlap, new_body makes a separate body |
| `direction` | `one_side` \| `symmetric` \| `two_sides` | `"one_side"` |  |
| `distance2` | number |  | (> 0) |
| `through_all` | boolean | `false` |  |
| `taper` | number | `0` | (>= -89, <= 89) |
| `flip` | boolean | `false` |  |
| `face` | object |  | instead of profile: a flat face of the part as the profile (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `more_profiles` | array of strings |  | more sketch steps extruded with profile |
| `curves` | string or object |  | open sketch curves for a thin extrude. (rules: [curves](#help-curves)) |
| `to` | object |  | what an extent goes to or a start is measured from: {"plane": "XY"\|"XZ"\|"YZ"}, {"face": face selector} (a face of the current body; add "of": step id for a face of another body) or {"step": id} (the solid of that step's body) |
| `extent2` | `distance` \| `through_all` \| `to_object` |  | side two's extent |
| `to2` | object |  | what an extent goes to or a start is measured from: {"plane": "XY"\|"XZ"\|"YZ"}, {"face": face selector} (a face of the current body; add "of": step id for a face of another body) or {"step": id} (the solid of that step's body) |
| `taper2` | number |  | side two's taper (degrees) (>= -89, <= 89) |
| `measurement` | `whole` \| `half` | `"whole"` | symmetric: distance is the whole length or each half |
| `start` | `profile` \| `offset` \| `object` | `"profile"` | where the extrude starts |
| `start_offset` | number |  | start offset along the normal (mm) |
| `start_from` | object |  | what an extent goes to or a start is measured from: {"plane": "XY"\|"XZ"\|"YZ"}, {"face": face selector} (a face of the current body; add "of": step id for a face of another body) or {"step": id} (the solid of that step's body) |
| `thin` | object |  | Thin Extrude: a wall along the profile instead of a solid |
| `bodies` | string or array |  | "auto": every body the feature passes through is cut / joined (what the dialog lists by itself); or a list of step ids: exactly those bodies (the dialog's "Bodies to Cut" row) |
| `extend` | `face` \| `adjacent` \| `body` \| `through` |  | To Object: how the target face is extended |
| `extend2` | `face` \| `adjacent` \| `body` \| `through` |  | side two's extend |
| `object_offset` | number |  | To Object: stop this far from the object (mm) |
| `object_offset2` | number |  | side two's object offset (mm) |

Examples:

- a 10 mm solid from Sketch1's areas:
  `{"profile": "Sketch1", "distance": 10}`
- cut a sketch lying on the top face down through the whole part:
  `{"profile": "Sketch2", "through_all": true, "operation": "cut", "flip": true}`
- extrude up to the top face (Extent To Object):
  `{"profile": "Sketch3", "to": {"face": {"normal": [0, 0, 1], "count": 1}}, "operation": "join"}`

<a id="revolve"></a>

### `revolve`: Revolve

Fusion: SOLID > CREATE > Revolve. Changes the design (one Undo step). Needs an open design.

Revolve a sketch's areas around an axis (SciForge's Revolve). axis: X, Y or Z (origin axes) or sketch_h / sketch_v (the sketch's own horizontal or vertical axis). angle in degrees, 360 (default) for a full turn. regions picks areas by a point inside each, as for extrude. operation auto (default) lets SciForge choose like its Revolve dialog does. More of the dialog: face (a flat face as the profile), axis {"sketch": id, "at": [x, y]} (the sketch line through that point), {"sketch": id, "construction": [[x1, y1], [x2, y2]]} (a construction line drawn for it), {"edge": selector} (a straight edge of the part); type angle | to | full, to (a pick it revolves up to), direction one_side | two_sides | symmetric, angle2 (side two), bodies.

| Argument | Type | Default | Description |
|---|---|---|---|
| `profile` | string |  | id of a create_sketch step |
| `regions` | array of arrays |  |  |
| `axis` (required) | string or object |  | X, Y, Z, sketch_h, sketch_v or an axis object (see above) |
| `angle` | number | `360` | (> 0, <= 360) |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` | `"auto"` |  |
| `face` | object |  | instead of profile: a flat face of the part as the profile (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `type` | `angle` \| `to` \| `full` |  | angle (default with an angle), full or to |
| `to` | object |  | type to: what the revolve goes up to. (rules: [picks](#help-picks)) |
| `direction` | `one_side` \| `two_sides` \| `symmetric` | `"one_side"` |  |
| `angle2` | number |  | side two's angle (degrees) (> 0, <= 360) |
| `bodies` | string or array |  | "auto": every body the feature passes through is cut / joined (what the dialog lists by itself); or a list of step ids: exactly those bodies (the dialog's "Bodies to Cut" row) |

Examples:

- a full turn about the Z axis:
  `{"profile": "Sketch1", "axis": "Z"}`
- a quarter turn about a straight edge of the part:
  `{"profile": "Sketch1", "axis": {"edge": {"type": "line", "parallel": [0, 0, 1], "at": {"axis": "x", "value": "min"}, "count": 1}}, "angle": 90}`

<a id="hole"></a>

### `hole`: Hole

Fusion: SOLID > CREATE > Hole. Changes the design (one Undo step). Needs a solid body.

Drill holes into the part (SciForge's Hole). First create_sketch on the face where the holes start (for example plane XY with offset = the top's height) with a small circle at each hole centre; the holes go at the circles' centres, whatever their size. Give depth or through_all. Optional counterbore {diameter, depth} or countersink {diameter, angle} (angle in degrees, default 90). Single Hole instead of a sketch: face (the flat face clicked) and at ([x, y, z] on it), with up to two references [{edge: edge selector, distance}] that place the centre from straight edges. All of Fusion's Hole dialog: hole_type simple | counterbore | countersink (cbore_diameter, cbore_depth, csink_diameter, csink_angle), extent distance | all | to (to: a plane or face), drill_point flat | angle (drill_angle), tap_type simple | clearance | tapped | taper, standard iso | ansi, size / designation (e.g. M6x1, 1/4-20 UNC), fit close | normal | loose, fastener socket_head | hex_head | countersunk, fastener_head (head pocket sized for it), taper_kind npt | bspt with taper_size, thread_class, thread_direction right | left, modeled (real thread), full_tap, tap_depth, flip. All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` | string |  | id of the sketch with the centres |
| `diameter` | number |  | (> 0) |
| `depth` | number |  | (> 0) |
| `through_all` | boolean | `false` |  |
| `counterbore` | object |  |  |
| `countersink` | object |  |  |
| `face` | object |  | Single Hole: the flat face the hole starts on (one face) (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `at` | array of 3 numbers |  | Single Hole: the clicked point on that face |
| `references` | array of objects |  | Single Hole: up to two edges that place the centre |
| `hole_type` | `simple` \| `counterbore` \| `countersink` | `"simple"` |  |
| `cbore_diameter` | number |  | counterbore diameter (mm) (> 0) |
| `cbore_depth` | number |  | counterbore depth (mm) (> 0) |
| `csink_diameter` | number |  | countersink diameter (mm) (> 0) |
| `csink_angle` | number |  | countersink angle (degrees) (> 0, <= 179) |
| `extent` | `distance` \| `all` \| `to` | `"distance"` |  |
| `to` | object |  | extent to: {"plane": "XY"\|"XZ"\|"YZ"} or {"face": selector} |
| `drill_point` | `flat` \| `angle` | `"flat"` |  |
| `drill_angle` | number |  | drill point angle (degrees) (> 0, <= 180) |
| `tap_type` | `simple` \| `clearance` \| `tapped` \| `taper` | `"simple"` |  |
| `standard` | `iso` \| `ansi` | `"iso"` |  |
| `size` | string |  | nominal size, e.g. 6 (M6) or 1/4 |
| `designation` | string |  | thread designation, e.g. M6x1 or 1/4-20 UNC |
| `fit` | `close` \| `normal` \| `loose` | `"normal"` | clearance hole fit |
| `fastener` | `socket_head` \| `hex_head` \| `countersunk` |  | clearance: the fastener the hole is for |
| `fastener_head` | boolean |  | size the counterbore / countersink for that fastener |
| `taper_kind` | `npt` \| `bspt` |  |  |
| `taper_size` | string |  | taper thread size, e.g. 1/8 |
| `thread_class` | string |  | e.g. 6H or 2B |
| `thread_direction` | `right` \| `left` | `"right"` |  |
| `modeled` | boolean |  | cut the real thread (default: cosmetic) |
| `full_tap` | boolean |  | thread the whole depth |
| `tap_depth` | number |  | thread depth (mm) (> 0) |
| `flip` | boolean |  | drill the other way |

Examples:

- 6 mm holes through the part at Sketch2's circle centres:
  `{"sketch": "Sketch2", "diameter": 6, "through_all": true}`
- one tapped M6 hole 12 mm deep, clicked on the top face:
  `{"face": {"normal": [0, 0, 1], "count": 1}, "at": [20, 10, 10], "tap_type": "tapped", "designation": "M6x1", "depth": 12}`

<a id="pattern"></a>

### `pattern`: Pattern

Fusion: SOLID > CREATE > Pattern > Rectangular / Circular Pattern (features). Changes the design (one Undo step). Needs a solid body.

Repeat earlier steps (features: their ids, e.g. a cut or a hole). kind rectangular: count copies spaced by spacing (mm) along direction X, Y or Z, optionally a second row with direction2, count2, spacing2. kind circular: count copies around axis X, Y or Z over angle degrees (default 360). Counts include the original. rectangular_pattern, circular_pattern, pattern_on_path and mirror offer the whole Fusion dialogs (faces, bodies, edges as directions, symmetric, suppression).

| Argument | Type | Default | Description |
|---|---|---|---|
| `kind` (required) | `rectangular` \| `circular` |  |  |
| `features` (required) | array of strings |  | ids of earlier steps (from get_design's timeline) |
| `direction` | `X` \| `Y` \| `Z` |  |  |
| `count` (required) | integer |  | (>= 2) |
| `spacing` | number |  |  |
| `direction2` | `X` \| `Y` \| `Z` |  |  |
| `count2` | integer |  | (>= 2) |
| `spacing2` | number |  |  |
| `axis` | `X` \| `Y` \| `Z` |  |  |
| `angle` | number | `360` | (> 0, <= 360) |

Examples:

- three copies of a cut, 20 mm apart along X:
  `{"kind": "rectangular", "features": ["Extrude2"], "direction": "X", "count": 3, "spacing": 20}`
- six holes around the Z axis:
  `{"kind": "circular", "features": ["Hole1"], "axis": "Z", "count": 6}`

<a id="sweep"></a>

### `sweep`: Sweep

Fusion: SOLID > CREATE > Sweep. Changes the design (one Undo step). Needs an open design.

Sweep a profile along a path (Fusion's Sweep). profile: a sketch id (its one area; a sketch with several areas is taken whole), with regions [[x, y], ...] to click some areas, or face: a flat face of the part. path (and rail): curves. (rules: [curves](#help-curves)) type single (path only), rail (path + guide rail: the profile follows the rail, scaling scale | stretch | none) or surface (path + guide surface faces). distance / distance2: how far along the path, 0..1 (1 = all the way); taper and twist (degrees, single path); orientation perpendicular | parallel; operation; bodies (Objects To Cut). (rules: [expressions](#help-expressions)) All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `profile` | string |  | the profile sketch |
| `regions` | array of arrays |  | areas of the profile sketch, a point inside each |
| `face` | object |  | instead of profile: a flat face as the profile (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `path` (required) | string or object |  | the path |
| `rail` | string or object |  | type rail: the guide rail |
| `surface` | object |  | type surface: the guide surface faces (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `type` | `single` \| `rail` \| `surface` | `"single"` |  |
| `distance` | number | `1` | how far along the path, 0..1 (>= 0, <= 1) |
| `distance2` | number |  | side two, 0..1 (>= 0, <= 1) |
| `taper` | number | `0` | taper angle (degrees) |
| `twist` | number | `0` | twist angle (degrees) |
| `orientation` | `perpendicular` \| `parallel` | `"perpendicular"` |  |
| `scaling` | `scale` \| `stretch` \| `none` | `"scale"` | type rail |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` | `"auto"` | auto (default: what the dialog picks by itself), join, cut, intersect or new_body |
| `bodies` | string or array |  | Objects To Cut: "auto" (every body in the way) or a list of step ids |
| `expressions` | object |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |

Examples:

- sweep Sketch1's circle along every curve of Sketch2:
  `{"profile": "Sketch1", "path": "Sketch2"}`
- along the chain through (0, 20), a quarter turn of twist:
  `{"profile": "Sketch1", "path": {"sketch": "Sketch2", "at": [0, 20]}, "twist": 90}`

<a id="loft"></a>

### `loft`: Loft

Fusion: SOLID > CREATE > Loft. Changes the design (one Undo step). Needs an open design.

Loft through profiles in order (Fusion's Loft). Each profile is {"profile": sketch id} (its one area, else the whole sketch), {"profile": id, "region": [x, y]} (one area), {"face": selector} or {"point": {"sketch": id, "at": [x, y]}} (a sketch point, first or last only). rails: guide rails (each a curves spec), or centerline: one centre line. closed: the loft comes back to the first profile. start_* / end_*: Fusion's end conditions of the first / last profile (free, direction, tangent, curvature, point_tangent) with weight 0.1..2 and angle. merge: merge tangent edges. operation, bodies. (rules: [curves](#help-curves))

| Argument | Type | Default | Description |
|---|---|---|---|
| `profiles` (required) | array of objects |  | in loft order |
| `rails` | array of string or objects |  | guide rails |
| `centerline` | string or object |  | a centre line (curves) |
| `guide` | `rails` \| `centerline` | `"rails"` |  |
| `closed` | boolean | `false` |  |
| `merge` | boolean | `false` | merge tangent edges |
| `start_condition` | `free` \| `direction` \| `tangent` \| `curvature` \| `point_tangent` | `"free"` |  |
| `start_weight` | number | `1` | how strongly the start condition pulls (0.1..2) (>= 0.1, <= 2) |
| `start_angle` | number | `0` | (degrees) |
| `end_condition` | `free` \| `direction` \| `tangent` \| `curvature` \| `point_tangent` | `"free"` |  |
| `end_weight` | number | `1` | how strongly the end condition pulls (0.1..2) (>= 0.1, <= 2) |
| `end_angle` | number | `0` | (degrees) |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` | `"auto"` | auto (default: what the dialog picks by itself), join, cut, intersect or new_body |
| `bodies` | string or array |  | Objects To Cut: "auto" (every body in the way) or a list of step ids |

Examples:

- a loft from a square to a circle on an offset plane:
  `{"profiles": [{"profile": "Sketch1"}, {"profile": "Sketch2"}]}`

<a id="rib"></a>

### `rib`: Rib

Fusion: SOLID > CREATE > Rib. Changes the design (one Undo step). Needs a solid body.

Fusion's Rib: a thin wall from one open sketch curve; the rib grows in the sketch plane to the part, always joined to the part. curves: (rules: [curves](#help-curves)) thickness (mm), thickness_side symmetric | one_side (flip_side: the other side), depth_type to_next (up to the part) | depth (with depth), flip (the other direction), extend (the ends reach the part). All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `curves` (required) | string or object |  | the curves |
| `thickness` | number | `2` | wall thickness (mm) (> 0) |
| `thickness_side` | `symmetric` \| `one_side` | `"symmetric"` |  |
| `flip_side` | boolean | `false` |  |
| `depth_type` | `to_next` \| `depth` | `"to_next"` |  |
| `depth` | number |  | depth (mm), depth_type depth (> 0) |
| `flip` | boolean | `false` |  |
| `extend` | boolean | `true` |  |

Examples:

- a 2 mm rib from Sketch3's curve:
  `{"curves": "Sketch3", "thickness": 2}`

<a id="web"></a>

### `web`: Web

Fusion: SOLID > CREATE > Web. Changes the design (one Undo step). Needs a solid body.

Fusion's Web: a thin wall from open sketch curves; the web grows out of the sketch plane, always joined to the part. curves: (rules: [curves](#help-curves)) thickness (mm), thickness_side symmetric | one_side (flip_side: the other side), depth_type to_next (up to the part) | depth (with depth), flip (the other direction), extend (the ends reach the part). All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `curves` (required) | string or object |  | the curves |
| `thickness` | number | `2` | wall thickness (mm) (> 0) |
| `thickness_side` | `symmetric` \| `one_side` | `"symmetric"` |  |
| `flip_side` | boolean | `false` |  |
| `depth_type` | `to_next` \| `depth` | `"to_next"` |  |
| `depth` | number |  | depth (mm), depth_type depth (> 0) |
| `flip` | boolean | `false` |  |
| `extend` | boolean | `true` |  |

Examples:

- a 2 mm web from Sketch3's curve:
  `{"curves": "Sketch3", "thickness": 2}`

<a id="emboss"></a>

### `emboss`: Emboss

Fusion: SOLID > CREATE > Emboss. Changes the design (one Undo step). Needs a solid body.

Emboss (raise) or deboss (sink) a sketch's areas onto faces of the part, wrapping them onto curved faces (Fusion's Emboss). Every closed area of the sketch is a profile (a sketch_text works too). faces: the faces to wrap onto; depth (mm; negative swaps the effect); effect emboss | deboss; h / v (mm): horizontal / vertical offset along the face; angle (degrees): rotation; tangent_chain (default true).

| Argument | Type | Default | Description |
|---|---|---|---|
| `sketch` (required) | string |  | the sketch (or text) with the areas |
| `faces` (required) | object |  | the faces to wrap onto (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `depth` | number | `1` | mm |
| `effect` | `emboss` \| `deboss` | `"emboss"` |  |
| `h` | number | `0` | horizontal offset (mm) |
| `v` | number | `0` | vertical offset (mm) |
| `angle` | number | `0` | rotation (degrees) |
| `tangent_chain` | boolean | `true` |  |

Examples:

- raise Sketch3's text 0.5 mm on a round face:
  `{"sketch": "Sketch3", "faces": {"type": "cylinder", "count": 1}, "depth": 0.5}`

<a id="thread"></a>

### `thread`: Thread

Fusion: SOLID > CREATE > Thread. Changes the design (one Undo step). Needs a solid body.

Put a thread on round faces (Fusion's Thread). faces: cylinder faces (a shaft or a hole). The size comes from the face unless designation (e.g. M6x1, 1/4-20 UNC) or size is given; standard iso | ansi; thread_class; direction right | left. modeled: true cuts the real ISO 68-1 groove (false: cosmetic, nothing changes in the solid). full_length, or length (mm) with offset (mm from the start) and from_end.

| Argument | Type | Default | Description |
|---|---|---|---|
| `faces` (required) | object |  | the cylinder faces (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `standard` | `iso` \| `ansi` | `"iso"` |  |
| `size` | string |  | nominal size |
| `designation` | string |  | e.g. M6x1 |
| `thread_class` | string |  | e.g. 6g |
| `direction` | `right` \| `left` | `"right"` |  |
| `modeled` | boolean | `false` | cut the real thread |
| `full_length` | boolean | `true` |  |
| `length` | number |  | mm (full_length false) (> 0) |
| `offset` | number |  | mm from the start (>= 0) |
| `from_end` | boolean | `false` | measure from the other end |

Examples:

- an 8 mm modeled thread on the 6 mm shaft:
  `{"faces": {"type": "cylinder", "radius": 3, "count": 1}, "modeled": true, "full_length": false, "length": 8}`

<a id="primitive"></a>

### `primitive`: Box / Cylinder / Sphere / Torus

Fusion: SOLID > CREATE > Box, Cylinder, Sphere, Torus. Changes the design (one Undo step). Needs nothing.

Make a box, cylinder, sphere or torus (Fusion's primitives) on an origin plane or a flat face, in that plane's own x / y frame. box: x, y (first corner), length, width, height (signed: a negative height goes below the plane), sx / sy (+1 / -1: the side the box goes to); cylinder: x, y (centre), diameter, height; sphere: x, y, diameter; torus: x, y, inner_diameter, torus_diameter, position inside | center | outside. operation auto (what the dialog picks: join when it touches the part, else new_body), join, cut, intersect, new_body or new_component. (rules: [expressions](#help-expressions)) All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `kind` (required) | `box` \| `cylinder` \| `sphere` \| `torus` |  |  |
| `plane` | string or object |  | "XY" \| "XZ" \| "YZ" (an origin plane of the current body) or {"face": selector} (a flat face of the part, as clicked) |
| `x` | number | `0` | x in the plane (mm) |
| `y` | number | `0` | y in the plane (mm) |
| `sx` | integer | `1` | +1 / -1 |
| `sy` | integer | `1` | +1 / -1 |
| `length` | number |  | box length (x) (mm) |
| `width` | number |  | box width (y) (mm) |
| `height` | number |  | height along the plane's normal (mm) |
| `diameter` | number |  | mm (> 0) |
| `inner_diameter` | number |  | torus: inner diameter (mm) (> 0) |
| `torus_diameter` | number |  | torus: the tube's diameter (mm) (> 0) |
| `position` | `inside` \| `center` \| `outside` | `"inside"` | torus |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` \| `new_component` | `"auto"` |  |
| `expressions` | object |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |

Examples:

- a 40 x 20 x 10 box at the origin:
  `{"kind": "box", "plane": "XY", "length": 40, "width": 20, "height": 10}`
- a boss on the top face:
  `{"kind": "cylinder", "plane": {"face": {"normal": [0, 0, 1], "count": 1}}, "x": 20, "y": 10, "diameter": 8, "height": 5}`

<a id="coil"></a>

### `coil`: Coil

Fusion: SOLID > CREATE > Coil. Changes the design (one Undo step). Needs nothing.

Make a coil (spring, helix) or a flat spiral (Fusion's Coil): plane and x / y of its centre, diameter, type rev_height (revolutions + height), rev_pitch, height_pitch or spiral; revolutions, height, pitch (mm per turn), angle (taper, degrees), clockwise; section circular | square | tri_ext | tri_int, section_position inside | center | outside, section_size (mm). operation auto, join, cut, intersect, new_body. All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `plane` | string or object |  | "XY" \| "XZ" \| "YZ" (an origin plane of the current body) or {"face": selector} (a flat face of the part, as clicked) |
| `x` | number | `0` | (mm) |
| `y` | number | `0` | (mm) |
| `diameter` | number | `20` | mm (> 0) |
| `type` | `rev_height` \| `rev_pitch` \| `height_pitch` \| `spiral` | `"rev_height"` |  |
| `revolutions` | number | `5` | (> 0) |
| `height` | number | `20` | (mm) |
| `pitch` | number | `4` | mm per turn (> 0) |
| `angle` | number | `0` | taper (degrees) |
| `clockwise` | boolean | `true` |  |
| `section` | `circular` \| `square` \| `tri_ext` \| `tri_int` | `"circular"` |  |
| `section_position` | `inside` \| `center` \| `outside` | `"inside"` |  |
| `section_size` | number | `2` | mm (> 0) |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` | `"auto"` | auto (default: what the dialog picks by itself), join, cut, intersect or new_body |
| `expressions` | object |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |

Examples:

- a 6-turn spring, 30 mm tall:
  `{"plane": "XY", "diameter": 20, "revolutions": 6, "height": 30, "section_size": 2}`

<a id="pipe"></a>

### `pipe`: Pipe

Fusion: SOLID > CREATE > Pipe. Changes the design (one Undo step). Needs an open design.

Make a pipe along a path (Fusion's Pipe): path {"sketch": id, "edge": n} (the sketch's n-th curve, 1 = first, with the curves chained to it when chain is true) or {"edges": edge selector} (edges of the part). section circular | square | triangular, section_size (mm), hollow with thickness (mm), distance 0..1 (how far along the path). operation auto, join, cut, intersect, new_body. All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `path` (required) | object |  | {"sketch": id, "edge": n} or {"edges": selector} |
| `chain` | boolean | `true` | follow the curves joined to it |
| `section` | `circular` \| `square` \| `triangular` | `"circular"` |  |
| `section_size` | number | `2` | mm (> 0) |
| `hollow` | boolean | `false` |  |
| `thickness` | number | `0.5` | wall (mm), hollow (> 0) |
| `distance` | number | `1` | 0..1 of the path (>= 0, <= 1) |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` | `"auto"` | auto (default: what the dialog picks by itself), join, cut, intersect or new_body |
| `expressions` | object |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |

Examples:

- a 4 mm pipe along Sketch2's path:
  `{"path": {"sketch": "Sketch2", "edge": 1}, "section_size": 4}`

<a id="gear"></a>

### `gear`: Gear

Fusion: SOLID > CREATE > Gear. Changes the design (one Undo step). Needs nothing.

Make an involute gear (SciForge's Gear tool): type spur | internal (a ring with teeth inside: rim) | rack (rack_size teeth or length with rack_length, rack_height); standard metric (module, mm) | english (diametral_pitch, teeth per inch); teeth, pressure_angle (14.5, 20 or 25 degrees), backlash, fillet (root fillet, mm), thickness, symmetric (both sides of the plane), hole (bore diameter, 0 none), plane, x / y. operation join | cut | new_body (default) | new_component. (rules: [expressions](#help-expressions)) All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `plane` | string or object |  | "XY" \| "XZ" \| "YZ" (an origin plane of the current body) or {"face": selector} (a flat face of the part, as clicked) |
| `x` | number | `0` | (mm) |
| `y` | number | `0` | (mm) |
| `type` | `spur` \| `internal` \| `rack` | `"spur"` |  |
| `standard` | `metric` \| `english` | `"metric"` |  |
| `module` | number | `2` | mm (> 0) |
| `diametral_pitch` | number | `12` | teeth per inch (> 0) |
| `teeth` | integer | `24` | (>= 1, <= 400) |
| `pressure_angle` | number | `20` | degrees: 14.5, 20 or 25 |
| `backlash` | number | `0` | mm (>= 0) |
| `fillet` | number | `0.5` | root fillet (mm) (>= 0) |
| `thickness` | number | `10` | mm (> 0) |
| `symmetric` | boolean | `false` |  |
| `hole` | number | `10` | bore diameter (mm, 0: none) (>= 0) |
| `rim` | number | `5` | internal gear: rim (mm) (> 0) |
| `rack_size` | `teeth` \| `length` | `"teeth"` |  |
| `rack_length` | number | `100` | mm (> 0) |
| `rack_height` | number | `5` | mm (> 0) |
| `operation` | `join` \| `cut` \| `new_body` \| `new_component` | `"new_body"` |  |
| `expressions` | object |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |

Examples:

- a 30-tooth spur gear, module 1.5:
  `{"module": 1.5, "teeth": 30, "thickness": 8, "hole": 8}`

<a id="rectangular_pattern"></a>

### `rectangular_pattern`: Rectangular pattern

Fusion: SOLID > CREATE > Pattern > Rectangular Pattern. Changes the design (one Undo step). Needs a solid body.

Fusion's Rectangular Pattern dialog: repeat features (step ids), faces or the whole body in rows. direction X | Y | Z, or {"edge": selector} / {"face": selector} (along a straight edge, or a flat face's normal); quantity (copies, the original counted); distance with distribution extent (the whole span) or spacing (between copies); direction_type one | symmetric; a second direction with direction2, quantity2, distance2, direction_type2; suppressed: copies left out. (rules: [expressions](#help-expressions)) All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `features` | array of strings |  | Pattern Type Features: the steps to repeat |
| `faces` | object |  | Pattern Type Faces: faces of the part to repeat (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `body` | boolean |  | Pattern Type Bodies: the whole current body (the copies are new bodies) |
| `expressions` | object |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |
| `suppressed` | array of integers |  | copies left out, by their number among the copies (Suppression) |
| `compute` | `optimized` \| `identical` \| `adjust` |  | Compute Option |
| `direction` (required) | string or object |  | X, Y, Z or a pick |
| `quantity` | integer | `2` | (>= 1) |
| `distance` | number |  | span or spacing (mm) |
| `distribution` | `extent` \| `spacing` | `"extent"` |  |
| `direction_type` | `one` \| `symmetric` | `"one"` |  |
| `direction2` | string or object |  | X, Y, Z or a pick |
| `quantity2` | integer |  | (>= 1) |
| `distance2` | number |  | (mm) |
| `direction_type2` | `one` \| `symmetric` |  |  |

Examples:

- four copies spread over 60 mm along X:
  `{"features": ["Extrude2"], "direction": "X", "quantity": 4, "distance": 60, "distribution": "extent"}`

<a id="circular_pattern"></a>

### `circular_pattern`: Circular pattern

Fusion: SOLID > CREATE > Pattern > Circular Pattern. Changes the design (one Undo step). Needs a solid body.

Fusion's Circular Pattern dialog: repeat features, faces or the whole body around an axis: X | Y | Z, {"edge": selector} (a straight edge) or {"face": selector} (a round face's axis). quantity; type full (360 degrees) | angle (the total angle) | symmetric. (rules: [expressions](#help-expressions))

| Argument | Type | Default | Description |
|---|---|---|---|
| `features` | array of strings |  | Pattern Type Features: the steps to repeat |
| `faces` | object |  | Pattern Type Faces: faces of the part to repeat (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `body` | boolean |  | Pattern Type Bodies: the whole current body (the copies are new bodies) |
| `expressions` | object |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |
| `suppressed` | array of integers |  | copies left out, by their number among the copies (Suppression) |
| `compute` | `optimized` \| `identical` \| `adjust` |  | Compute Option |
| `axis` (required) | string or object |  | X, Y, Z or a pick |
| `quantity` | integer | `3` | (>= 1) |
| `type` | `full` \| `angle` \| `symmetric` | `"full"` |  |
| `angle` | number |  | total angle (degrees) |

Examples:

- eight holes around a round face's axis:
  `{"features": ["Hole1"], "axis": {"face": {"type": "cylinder", "radius": 20, "count": 1}}, "quantity": 8}`

<a id="pattern_on_path"></a>

### `pattern_on_path`: Pattern on path

Fusion: SOLID > CREATE > Pattern > Pattern on Path. Changes the design (one Undo step). Needs a solid body.

Fusion's Pattern on Path: repeat features, faces or the body along a sketch curve. path {"sketch": id} or {"sketch": id, "edge": n} (n-th curve, 1 = first); quantity; distance with distribution extent | spacing; direction_type one | symmetric; orientation identical (copies keep their direction) | path (they turn with the path); start_point 0..1 (where on the path it starts). All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `features` | array of strings |  | Pattern Type Features: the steps to repeat |
| `faces` | object |  | Pattern Type Faces: faces of the part to repeat (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `body` | boolean |  | Pattern Type Bodies: the whole current body (the copies are new bodies) |
| `expressions` | object |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |
| `suppressed` | array of integers |  | copies left out, by their number among the copies (Suppression) |
| `compute` | `optimized` \| `identical` \| `adjust` |  | Compute Option |
| `path` (required) | object |  | {"sketch": id} or {"sketch": id, "edge": n} |
| `quantity` | integer | `3` | (>= 1) |
| `distance` | number |  | (mm) |
| `distribution` | `extent` \| `spacing` | `"extent"` |  |
| `direction_type` | `one` \| `symmetric` | `"one"` |  |
| `orientation` | `identical` \| `path` | `"identical"` |  |
| `start_point` | number |  | 0 (start) .. 1 (end) (>= 0, <= 1) |

Examples:

- five copies along Sketch3's curve:
  `{"features": ["Extrude2"], "path": {"sketch": "Sketch3"}, "quantity": 5, "distance": 80}`

<a id="mirror"></a>

### `mirror`: Mirror

Fusion: SOLID > CREATE > Mirror. Changes the design (one Undo step). Needs a solid body.

Fusion's Mirror: mirror features, faces or the whole body about a plane: XY | XZ | YZ or {"face": selector} (a flat face of the part). A body mirror takes operation join (one body with the original) or new_body.

| Argument | Type | Default | Description |
|---|---|---|---|
| `features` | array of strings |  | Pattern Type Features: the steps to repeat |
| `faces` | object |  | Pattern Type Faces: faces of the part to repeat (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `body` | boolean |  | Pattern Type Bodies: the whole current body (the copies are new bodies) |
| `expressions` | object |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |
| `suppressed` | array of integers |  | copies left out, by their number among the copies (Suppression) |
| `compute` | `optimized` \| `identical` \| `adjust` |  | Compute Option |
| `plane` (required) | string or object |  | XY, XZ, YZ or {"face": selector} |
| `operation` | `join` \| `new_body` | `"new_body"` | body mirror only |

Examples:

- mirror the whole body about YZ into one body:
  `{"body": true, "plane": "YZ", "operation": "join"}`

## Modify

<a id="fillet"></a>

### `fillet`: Fillet

Fusion: SOLID > MODIFY > Fillet. Changes the design (one Undo step). Needs a solid body.

Round edges of the current body with a radius (SciForge's Fillet). Pick them with edges (an edge selector), faces (every sharp edge around the faces a face selector picks) and/or features (the edges earlier steps made, by step id). Errors such as 'the radius is too big for this edge' come back as sentences. For several radii, chord length, variable radius or tangent chain off use fillet_sets; Rule Fillet and Full Round Fillet are their own tools. With the timeline marker rolled back the fillet goes in at the marker and later fillets keep their edges. All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `edges` | object |  | The edges to round. (rules: [selectors](#help-selectors)) |
| `faces` | object |  | Round every sharp edge around these faces. (rules: [selectors](#help-selectors)) |
| `features` | array of strings |  | ids of earlier steps (from get_design's timeline) |
| `radius` (required) | number |  | (> 0) |

Examples:

- round the 4 top edges of a box, 3 mm:
  `{"edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}, "radius": 3}`

<a id="chamfer"></a>

### `chamfer`: Chamfer

Fusion: SOLID > MODIFY > Chamfer. Changes the design (one Undo step). Needs a solid body.

Bevel edges of the current body (SciForge's Chamfer). distance alone: equal distances; distance and distance2: two distances (flip swaps the sides); distance and angle: a distance and an angle in degrees. Pick edges as for fillet. All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `edges` | object |  | The edges to bevel. (rules: [selectors](#help-selectors)) |
| `faces` | object |  | Bevel every sharp edge around these faces. (rules: [selectors](#help-selectors)) |
| `features` | array of strings |  | ids of earlier steps (from get_design's timeline) |
| `distance` (required) | number |  | (> 0) |
| `distance2` | number |  | (> 0) |
| `angle` | number |  | (> 0, <= 89) |
| `flip` | boolean | `false` |  |

Examples:

- 1 mm at 30 degrees:
  `{"edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}, "distance": 1, "angle": 30}`

<a id="shell"></a>

### `shell`: Shell

Fusion: SOLID > MODIFY > Shell. Changes the design (one Undo step). Needs a solid body.

Hollow the current body out with a wall thickness (SciForge's Shell). faces: the faces to remove (open), a face selector, e.g. the top face {"normal": [0, 0, 1], "count": 1}. direction inside (default: the outside stays where it is) or outside. More of Fusion's dialog: body: true (hollow and closed, no face removed), direction both with inside / outside thicknesses, shell_type sharp | rounded (rounded outer corners), bodies [{"body": step id, "faces": selector}] (one Shell over several bodies). All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `faces` | object |  | The faces to remove. (rules: [selectors](#help-selectors)) |
| `thickness` | number |  | (> 0) |
| `direction` | `inside` \| `outside` \| `both` | `"inside"` |  |
| `body` | boolean |  | hollow the whole body, closed (no face removed) |
| `inside` | number |  | inside thickness (mm) (> 0) |
| `outside` | number |  | outside thickness (mm) (> 0) |
| `shell_type` | `sharp` \| `rounded` | `"sharp"` |  |
| `bodies` | array of objects |  | several bodies in one Shell |

Examples:

- an open box with 2 mm walls:
  `{"faces": {"normal": [0, 0, 1], "count": 1}, "thickness": 2}`

<a id="press_pull"></a>

### `press_pull`: Press pull

Fusion: SOLID > MODIFY > Press Pull (Q). Changes the design (one Undo step). Needs a solid body.

Fusion's Press Pull: push or pull faces by a distance (mm, negative pushes in), or give edges (they get a fillet of that radius), or fillet_face (a face a fillet made: that fillet's radius becomes distance). offset_type (faces): automatic (default), new (a new Press Pull step), modify (change the extrude that made the faces, no new step).

| Argument | Type | Default | Description |
|---|---|---|---|
| `faces` | object |  | the faces to move (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `edges` | object |  | edges to round (an edge selector: filters type, parallel, radius, on_faces, not_on_faces, at, all, count, any_of; see get_help topic selectors). Give count. |
| `fillet_face` | object |  | a face of a fillet (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `distance` (required) | number |  | mm (a radius for edges / fillet faces) |
| `offset_type` | `automatic` \| `new` \| `modify` | `"automatic"` |  |

Examples:

- pull the top face up 5 mm:
  `{"faces": {"normal": [0, 0, 1], "count": 1}, "distance": 5}`

<a id="fillet_sets"></a>

### `fillet_sets`: Fillet / chamfer with sets

Fusion: SOLID > MODIFY > Fillet / Chamfer (several selection sets, Chord Length, Variable). Changes the design (one Undo step). Needs a solid body.

Fusion's Fillet or Chamfer dialog with several selection sets in one step (the "+" rows): each set picks edges / faces / features and has its own size. Fillet rows: radius, radius_type constant | chord (chord) | variable (start, end, points [[position 0..1, radius]]), tangent_chain. Chamfer rows (kind chamfer): chamfer_type equal | two | angle, distance, distance2, angle, flip. tangent_chain (the step's, default true). All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `kind` | `fillet` \| `chamfer` | `"fillet"` |  |
| `sets` (required) | array of objects |  | the selection sets |
| `tangent_chain` | boolean | `true` |  |

Examples:

- 3 mm on the top edges and 1 mm on the vertical edges, one step:
  `{"sets": [{"edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}, "radius": 3}, {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4}, "radius": 1}]}`

<a id="rule_fillet"></a>

### `rule_fillet`: Rule fillet

Fusion: SOLID > MODIFY > Fillet (Type: Rule Fillet). Changes the design (one Undo step). Needs a solid body.

Fusion's Rule Fillet: round every edge a rule finds, found again whenever the part changes. rule all (every edge of faces / features) or between (the edges between the first group and faces2 / features2); rounds (concave edges) and fillets (convex) on or off; radius (mm).

| Argument | Type | Default | Description |
|---|---|---|---|
| `radius` (required) | number |  | mm (> 0) |
| `rule` | `all` \| `between` | `"all"` |  |
| `faces` | object |  | the faces (first group) (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `features` | array of strings |  | steps whose faces form the first group |
| `faces2` | object |  | the second group, rule between (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `features2` | array of strings |  | steps for the second group |
| `rounds` | boolean | `true` |  |
| `fillets` | boolean | `true` |  |

Examples:

- round every edge the boss Extrude2 made:
  `{"radius": 1, "rule": "all", "features": ["Extrude2"]}`

<a id="full_round_fillet"></a>

### `full_round_fillet`: Full round fillet

Fusion: SOLID > MODIFY > Fillet (Type: Full Round Fillet). Changes the design (one Undo step). Needs a solid body.

Fusion's Full Round Fillet: each selector picks one centre face (a rib's top, say); it is replaced by a round that touches both side faces.

| Argument | Type | Default | Description |
|---|---|---|---|
| `faces` (required) | array of objects |  | one selector per round |

Examples:

- round off the top of a thin wall:
  `{"faces": [{"normal": [0, 0, 1], "count": 1}]}`

<a id="draft"></a>

### `draft`: Draft

Fusion: SOLID > MODIFY > Draft. Changes the design (one Undo step). Needs a solid body.

Fusion's Draft: tilt faces by an angle for a mould. plane: the fixed plane (XY | XZ | YZ or {"face": selector}: a flat face, its outward side the pull direction); faces: the faces to tilt (or [{body, faces}, ...] for several bodies in one step); angle (degrees, positive narrows the part toward the pull direction); flip. draft_type fixed (default) | parting (with parting: XY / {"face": sel} / {"edges": sel} / {"sketch": id}, the parting line); sides one | two (with angle2) | symmetric.

| Argument | Type | Default | Description |
|---|---|---|---|
| `plane` (required) | string or object |  | XY, XZ, YZ or {"face": selector} |
| `faces` (required) | object or array |  | a face selector, or [{body, faces}] for several bodies |
| `angle` | number | `1` | (degrees) |
| `flip` | boolean | `false` |  |
| `draft_type` | `fixed` \| `parting` | `"fixed"` |  |
| `parting` | string or object |  | parting line: a plane name, face, edges or sketch |
| `sides` | `one` \| `two` \| `symmetric` | `"one"` |  |
| `angle2` | number |  | side two (degrees) |

Examples:

- 3 degrees on the four side walls, pulled up from XY:
  `{"plane": "XY", "faces": {"along": [0, 0, 1], "count": 4}, "angle": 3}`

<a id="scale"></a>

### `scale`: Scale

Fusion: SOLID > MODIFY > Scale. Changes the design (one Undo step). Needs a solid body.

Fusion's Scale: make the current body (or bodies: several step ids, one step; or a sketch: its curves and dimensions) bigger or smaller. factor (uniform) or factors [x, y, z] (non-uniform, bodies only); point: "origin" (default) or [x, y, z], a corner of the part to scale about.

| Argument | Type | Default | Description |
|---|---|---|---|
| `factor` | number |  | uniform scale factor (> 0) |
| `factors` | array of 3 numbers |  | [x, y, z] factors |
| `point` | string or array |  | "origin" or [x, y, z] (a corner of the part) |
| `bodies` | array of strings |  | several bodies, by a step of each |
| `sketch` | string |  | scale this sketch instead |

Examples:

- twice as big about the origin:
  `{"factor": 2}`
- half as tall:
  `{"factors": [1, 1, 0.5]}`

<a id="combine"></a>

### `combine`: Combine

Fusion: SOLID > MODIFY > Combine. Changes the design (one Undo step). Needs an open design.

Fusion's Combine: join, cut or intersect bodies. target: the body kept (a step id of it); tools: the bodies used (step ids). keep_tools keeps them; new_body / new_component puts the result in a new body / component.

| Argument | Type | Default | Description |
|---|---|---|---|
| `target` (required) | string |  | the target body (a step in it) |
| `tools` (required) | array of strings |  | the tool bodies |
| `operation` | `join` \| `cut` \| `intersect` | `"join"` |  |
| `new_body` | boolean | `false` |  |
| `new_component` | boolean | `false` |  |
| `keep_tools` | boolean | `false` |  |

Examples:

- cut Extrude2's body out of Extrude1's:
  `{"target": "Extrude1", "tools": ["Extrude2"], "operation": "cut"}`

<a id="split_body"></a>

### `split_body`: Split body

Fusion: SOLID > MODIFY > Split Body. Changes the design (one Undo step). Needs a solid body.

Fusion's Split Body: cut a body into pieces (new bodies). body: the body (a step id); tool: XY | XZ | YZ, {"face": selector, "of": step id} (a face, of another body with of), {"body": step id} or {"sketch": id, "edge": n} (a sketch curve, cut straight through); tools: several at once. extend (default true): the splitting face is extended.

| Argument | Type | Default | Description |
|---|---|---|---|
| `body` (required) | string |  | the body to split |
| `tool` | string or object |  | the splitting tool |
| `tools` | array of string or objects |  | several splitting tools |
| `extend` | boolean | `true` |  |

Examples:

- split the body in two at YZ:
  `{"body": "Extrude1", "tool": "YZ"}`

<a id="split_face"></a>

### `split_face`: Split face

Fusion: SOLID > MODIFY > Split Face. Changes the design (one Undo step). Needs a solid body.

Fusion's Split Face: split faces of a body with a tool, so they can be drafted or coloured on their own. faces (selector, of: the body's step), tool: a body pick, extend, split_type surface | vector (along direction) | closest. (rules: [body_picks](#help-body_picks))

| Argument | Type | Default | Description |
|---|---|---|---|
| `faces` (required) | object |  | the faces to split (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `of` | string |  | the body the faces are on (default: the current one) |
| `tool` (required) | string or object |  | the splitting tool (a body pick) |
| `extend` | boolean | `false` |  |
| `split_type` | `surface` \| `vector` \| `closest` | `"surface"` |  |
| `direction` | string or object |  | split_type vector: the direction (a body pick) |

Examples:

- split the side walls at the XY plane:
  `{"faces": {"along": [0, 0, 1], "count": 4}, "tool": "XY"}`

<a id="silhouette_split"></a>

### `silhouette_split`: Silhouette split

Fusion: SOLID > MODIFY > Silhouette Split. Changes the design (one Undo step). Needs a solid body.

Fusion's Silhouette Split: split a body along its outline seen from a direction. body (step id), direction (a body pick: a plane, face, edge or axis), operation faces (split the faces) | body (two bodies) | shelled (for a shelled part).

| Argument | Type | Default | Description |
|---|---|---|---|
| `body` (required) | string |  | the body |
| `direction` (required) | string or object |  | the view direction (a body pick) |
| `operation` | `faces` \| `body` \| `shelled` | `"faces"` |  |

Examples:

- split a round part into two halves seen from Z:
  `{"body": "Revolve1", "direction": "Z", "operation": "body"}`

<a id="replace_face"></a>

### `replace_face`: Replace face

Fusion: SOLID > MODIFY > Replace Face. Changes the design (one Undo step). Needs a solid body.

Fusion's Replace Face: move faces of a body onto a target (a plane or a face): faces (selector, of: the body's step), tangent_chain, target (a body pick: XY / XZ / YZ or {"face": selector, "of": id}).

| Argument | Type | Default | Description |
|---|---|---|---|
| `faces` (required) | object |  | the faces to replace (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `of` | string |  | the body they are on |
| `tangent_chain` | boolean | `true` |  |
| `target` (required) | string or object |  | the new face (a body pick) |

Examples:

- move the top face up to another body's top:
  `{"faces": {"normal": [0, 0, 1], "count": 1}, "target": {"face": {"normal": [0, 0, 1], "count": 1}, "of": "Extrude2"}}`

<a id="delete_face"></a>

### `delete_face`: Delete face

Fusion: SOLID > MODIFY > Delete (faces). Changes the design (one Undo step), destructive. Needs a solid body.

Delete faces of the current body (Fusion: select faces, Delete): the gap heals, as when a fillet or a hole is removed.

| Argument | Type | Default | Description |
|---|---|---|---|
| `faces` (required) | object |  | the faces to delete (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |

Examples:

- remove a 6 mm hole's wall: the hole is gone:
  `{"faces": {"type": "cylinder", "radius": 3, "count": 1}}`

<a id="remove_bodies"></a>

### `remove_bodies`: Remove

Fusion: SOLID > MODIFY > Remove. Changes the design (one Undo step), destructive. Needs an open design.

Fusion's Remove: take bodies out of the design from this point of the timeline on (a timeline step: rolling back before it brings them back). bodies: step ids.

| Argument | Type | Default | Description |
|---|---|---|---|
| `bodies` (required) | array of strings |  | the bodies to remove |

Examples:

- remove the tool body after a combine:
  `{"bodies": ["Extrude3"]}`

<a id="delete_bodies"></a>

### `delete_bodies`: Delete bodies

Fusion: BROWSER > a body > Delete. Changes the design (one Undo step), destructive. Needs an open design.

Delete bodies (picked in the browser, then Delete): they are gone from the whole history; what used them keeps working where it can. bodies: step ids.

| Argument | Type | Default | Description |
|---|---|---|---|
| `bodies` (required) | array of strings |  | the bodies to delete |

Examples:

- delete Extrude3's body:
  `{"bodies": ["Extrude3"]}`

<a id="move_copy"></a>

### `move_copy`: Move / copy

Fusion: SOLID > MODIFY > Move/Copy (M). Changes the design (one Undo step). Needs an open design.

Fusion's Move/Copy. What moves: bodies (step ids), faces (a selector: the faces move, the body follows) or components (component ids). move_type free (dx dy dz and rotations rx ry rz about pivot), translate (dx, dy, dz), rotate (angle about axis X / Y / Z through pivot), point_to_point (from_point to to_point), point_to_position (from_point goes to px, py, pz). copy: move a copy (bodies). capture (components): record the move as a timeline step (Capture Position). All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `bodies` | array of strings |  | the bodies |
| `faces` | object |  | the faces (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `components` | array of strings |  | the components |
| `move_type` | `free` \| `translate` \| `rotate` \| `point_to_point` \| `point_to_position` |  |  |
| `dx` | number | `0` | (mm) |
| `dy` | number | `0` | (mm) |
| `dz` | number | `0` | (mm) |
| `rx` | number | `0` | (degrees) |
| `ry` | number | `0` | (degrees) |
| `rz` | number | `0` | (degrees) |
| `angle` | number |  | rotate (degrees) |
| `axis` | `X` \| `Y` \| `Z` |  | rotate: an origin axis |
| `pivot` | array of 3 numbers |  | the point rotations turn about |
| `from_point` | array of 3 numbers |  | [x, y, z] in design coordinates (mm) |
| `to_point` | array of 3 numbers |  | [x, y, z] in design coordinates (mm) |
| `px` | number |  | (mm) |
| `py` | number |  | (mm) |
| `pz` | number |  | (mm) |
| `copy` | boolean | `false` |  |
| `capture` | boolean | `false` | components: a Move step in the timeline |

Examples:

- move a body 30 mm along X:
  `{"bodies": ["Extrude2"], "move_type": "translate", "dx": 30}`
- push the +X face out 5 mm:
  `{"faces": {"normal": [1, 0, 0], "count": 1}, "dx": 5}`

<a id="align"></a>

### `align`: Align

Fusion: SOLID > MODIFY > Align. Changes the design (one Undo step). Needs a solid body.

Fusion's Align (Objects: Bodies): move a body so that from (a face, edge or corner of it) lands on to (another face, edge, corner, plane or axis). flip turns it over; turns (0..3) quarter-turns about the aligned axis. (rules: [body_picks](#help-body_picks))

| Argument | Type | Default | Description |
|---|---|---|---|
| `from` (required) | string or object |  | on the body that moves (a body pick) |
| `to` (required) | string or object |  | where it goes (a body pick) |
| `flip` | boolean | `false` |  |
| `turns` | integer | `0` | (>= 0, <= 3) |

Examples:

- stand one body on the other's top face:
  `{"from": {"face": {"normal": [0, 0, -1], "count": 1}, "of": "Extrude2"}, "to": {"face": {"normal": [0, 0, 1], "count": 1}, "of": "Extrude1"}}`

<a id="physical_material"></a>

### `physical_material`: Physical material

Fusion: SOLID > MODIFY > Physical Material. Changes the design (one Undo step). Needs an open design.

Give a body its physical material (Fusion's Physical Material): density for mass and the material's look. body: a step of it (default: the current body). material: one of SciForge's library (list_materials lists them with densities), or a user material (user:<name>).

| Argument | Type | Default | Description |
|---|---|---|---|
| `body` | string |  | a step of the body |
| `material` (required) | string |  | library key, e.g. aluminium, abs, steel |

Examples:

- make the part aluminium 6061:
  `{"body": "Extrude1", "material": "aluminium_6061"}`

<a id="list_materials"></a>

### `list_materials`: List materials

Fusion: SOLID > MODIFY > Physical Material / Appearance (libraries). Read-only. Needs nothing.

List SciForge's physical materials (key, name, density kg/m3, group) and appearances (key, name, colour), for physical_material and appearance.

No arguments.

Examples:

- the material and appearance libraries:
  `{}`

<a id="appearance"></a>

### `appearance`: Appearance

Fusion: SOLID > MODIFY > Appearance (A). Changes the design (one Undo step). Needs an open design.

Fusion's Appearance: colour a body, or some faces of it, without changing its material. body: a step of it (default: the current body); faces: a selector (only these faces); look: a library key (list_materials) or color [r, g, b] (0..1) with shininess (0..1) and transparency (0..1). clear: true removes the body's own appearance.

| Argument | Type | Default | Description |
|---|---|---|---|
| `body` | string |  | a step of the body |
| `faces` | object |  | only these faces (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `look` | string |  | an appearance key, e.g. plastic_red |
| `color` | array of 3 numbers |  | [r, g, b] 0..1 |
| `shininess` | number | `0.5` | (>= 0, <= 1) |
| `transparency` | number | `0` | (>= 0, <= 1) |

Examples:

- the current body in glossy red:
  `{"look": "plastic_red"}`
- just the top face blue:
  `{"faces": {"normal": [0, 0, 1], "count": 1}, "color": [0.1, 0.3, 0.8]}`

## Surface

<a id="surface"></a>

### `surface`: Surface

Fusion: SURFACE > CREATE / MODIFY (Extrude, Revolve, Sweep, Loft, Patch, Ruled, Offset, Boundary Fill, Thicken, Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal). Changes the design (one Undo step). Needs nothing.

One of the SURFACE tab's tools (thin surface bodies with no volume; Thicken, Boundary Fill and Stitch make solids). kind picks the tool; refs / refs2 / refs3 are the dialog's selection boxes in order (profile, then path / axis / rails / tools...). options: the dialog's fields: extrude: start, start_offset, direction one_side|two_sides|symmetric, measurement, extent distance|to_object|all, distance, distance2, taper, taper2, flip, operation new_body|new_component; revolve: type angle|to|full, direction, angle, angle2; sweep: type single|rail, distance, distance2, orientation, twist, taper, scaling; loft: guide, closed, merge, start_/end_condition, _weight, _angle; patch: continuity connected|tangent|curvature, weight, group_edges; ruled: ruled_type tangent|normal|direction, distance, angle, alternate, mitered; offset: distance; boundary_fill: remove_tools, operation join|cut|intersect|new_body; thicken: thickness, direction, thicken_type sharp|rounded, operation; untrim: loop_type all|internal|external, extend, distance; extend: distance, extend_type natural|perpendicular|tangent, alignment free|align; stitch: tolerance (mm), operation; every kind: chain (chain selection). remove (trim): [{step, at: [x, y, z]}] a point on each piece to take away; cells (boundary_fill): [[x, y, z], ...] a point in each cell kept; bodies (reverse_normal): step ids; target: the solid body a thicken / boundary fill joins or cuts. All lengths are in millimetres (mm) and all angles in degrees.

| Argument | Type | Default | Description |
|---|---|---|---|
| `kind` (required) | `extrude` \| `revolve` \| `sweep` \| `loft` \| `patch` \| `ruled` \| `offset` \| `boundary_fill` \| `thicken` \| `trim` \| `untrim` \| `extend` \| `stitch` \| `unstitch` \| `reverse_normal` |  |  |
| `refs` | array of objects |  | the first selection box |
| `refs2` | array of objects |  | the second selection box |
| `refs3` | array of objects |  | the third selection box |
| `options` | object |  | the dialog's fields (see above) |
| `remove` | array of objects |  | trim: the pieces to take away |
| `cells` | array of arrays |  | boundary_fill: a point inside each cell |
| `bodies` | array of strings |  | reverse_normal: the bodies |
| `target` | string |  | thicken / boundary_fill: the solid body it joins or cuts |

Examples:

- a 20 mm surface from a sketch curve:
  `{"kind": "extrude", "refs": [{"sketch": "Sketch1", "at": [10, 0]}], "options": {"distance": 20}}`
- turn the surface into a 2 mm solid:
  `{"kind": "thicken", "refs": [{"step": "Surface1"}], "options": {"thickness": 2}}`

## Construct

<a id="construct_plane"></a>

### `construct_plane`: Construction plane

Fusion: SOLID > CONSTRUCT > (planes). Changes the design (one Undo step). Needs an open design.

Make a construction plane (Fusion's CONSTRUCT menu) the way its dialog does; it follows what it is built on when the part changes and other tools can use it (sketch on a plane with create_sketch on, pick it with {"construct": id}). preset and its refs: OffsetPlane: a plane or flat face (and, extent To Object, a point); PlaneAtAngle: a line (edge, sketch line or axis); TangentPlane: a round face; Midplane: two planes / flat faces; PlaneTwoEdges: two lines in one plane; PlaneThreePoints: three points; PlaneAtPoint: a face and a point; PlaneAlongPath: an edge or sketch curve. distance (mm, OffsetPlane), angle (degrees, PlaneAtAngle / TangentPlane), fraction (0..1 along the path), distance_type physical | proportional (along a path); points: where each face was clicked ([x, y, z] or null, per ref). (rules: [picks](#help-picks))

| Argument | Type | Default | Description |
|---|---|---|---|
| `preset` (required) | `OffsetPlane` \| `PlaneAtAngle` \| `TangentPlane` \| `Midplane` \| `PlaneTwoEdges` \| `PlaneThreePoints` \| `PlaneAtPoint` \| `PlaneAlongPath` |  |  |
| `refs` (required) | array of objects |  | what it is built on, in order |
| `distance` | number |  | OffsetPlane distance (mm) |
| `angle` | number |  | PlaneAtAngle / TangentPlane (degrees) |
| `fraction` | number |  | 0..1 along a path (>= 0, <= 1) |
| `distance_type` | `physical` \| `proportional` |  |  |
| `points` | array of array or nulls |  | per ref: the point clicked on a face, or null |

Examples:

- a plane 25 mm above XY:
  `{"preset": "OffsetPlane", "refs": [{"plane": "XY"}], "distance": 25}`

<a id="construct_axis"></a>

### `construct_axis`: Construction axis

Fusion: SOLID > CONSTRUCT > (axes). Changes the design (one Undo step). Needs an open design.

Make a construction axis (Fusion's CONSTRUCT menu) the way its dialog does; it follows what it is built on when the part changes and other tools can use it (sketch on a plane with create_sketch on, pick it with {"construct": id}). preset and its refs: AxisCylinder: a round face or circular edge; AxisNormal: a face (and optionally a point); AxisTwoPlanes: two planes / flat faces; AxisTwoPoints: two points; AxisEdge: a straight edge or sketch line. distance (mm, OffsetPlane), angle (degrees, PlaneAtAngle / TangentPlane), fraction (0..1 along the path), distance_type physical | proportional (along a path); points: where each face was clicked ([x, y, z] or null, per ref). (rules: [picks](#help-picks))

| Argument | Type | Default | Description |
|---|---|---|---|
| `preset` (required) | `AxisCylinder` \| `AxisNormal` \| `AxisTwoPlanes` \| `AxisTwoPoints` \| `AxisEdge` |  |  |
| `refs` (required) | array of objects |  | what it is built on, in order |
| `distance` | number |  | OffsetPlane distance (mm) |
| `angle` | number |  | PlaneAtAngle / TangentPlane (degrees) |
| `fraction` | number |  | 0..1 along a path (>= 0, <= 1) |
| `distance_type` | `physical` \| `proportional` |  |  |
| `points` | array of array or nulls |  | per ref: the point clicked on a face, or null |

Examples:

- the axis of a round face:
  `{"preset": "AxisCylinder", "refs": [{"face": {"type": "cylinder", "count": 1}}]}`

<a id="construct_point"></a>

### `construct_point`: Construction point

Fusion: SOLID > CONSTRUCT > (points). Changes the design (one Undo step). Needs an open design.

Make a construction point (Fusion's CONSTRUCT menu) the way its dialog does; it follows what it is built on when the part changes and other tools can use it (sketch on a plane with create_sketch on, pick it with {"construct": id}). preset and its refs: PointVertex: a corner or sketch point; PointTwoEdges: two edges that cross; PointThreePlanes: three planes / flat faces; PointCenter: a circular edge or a ball; PointEdgePlane: an edge and a plane it crosses; PointAlongPath: an edge or sketch curve. distance (mm, OffsetPlane), angle (degrees, PlaneAtAngle / TangentPlane), fraction (0..1 along the path), distance_type physical | proportional (along a path); points: where each face was clicked ([x, y, z] or null, per ref). (rules: [picks](#help-picks))

| Argument | Type | Default | Description |
|---|---|---|---|
| `preset` (required) | `PointVertex` \| `PointTwoEdges` \| `PointThreePlanes` \| `PointCenter` \| `PointEdgePlane` \| `PointAlongPath` |  |  |
| `refs` (required) | array of objects |  | what it is built on, in order |
| `distance` | number |  | OffsetPlane distance (mm) |
| `angle` | number |  | PlaneAtAngle / TangentPlane (degrees) |
| `fraction` | number |  | 0..1 along a path (>= 0, <= 1) |
| `distance_type` | `physical` \| `proportional` |  |  |
| `points` | array of array or nulls |  | per ref: the point clicked on a face, or null |

Examples:

- the centre of a circular edge:
  `{"preset": "PointCenter", "refs": [{"edge": {"type": "circle", "count": 1}}]}`

## Assemble

<a id="pattern_components"></a>

### `pattern_components`: Pattern components

Fusion: SOLID > CREATE > Pattern (Pattern Type: Components). Changes the design (one Undo step). Needs an open design.

Pattern a whole component (its copies are linked instances, as Fusion's): kind rectangular (direction, direction2: origin axes X / Y / Z; quantity, quantity2, distance, distance2, distribution extent | spacing) or circular (axis, quantity, angle, circular_type full | angle | symmetric). component: the component's id.

| Argument | Type | Default | Description |
|---|---|---|---|
| `component` (required) | string |  | the component |
| `kind` (required) | `rectangular` \| `circular` |  |  |
| `axis` | `X` \| `Y` \| `Z` |  |  |
| `direction` | `X` \| `Y` \| `Z` |  |  |
| `direction2` | `X` \| `Y` \| `Z` |  |  |
| `quantity` | integer | `2` | (>= 1) |
| `quantity2` | integer |  | (>= 1) |
| `distance` | number |  | (mm) |
| `distance2` | number |  | (mm) |
| `angle` | number | `360` | (degrees) |
| `circular_type` | `full` \| `angle` \| `symmetric` | `"full"` |  |
| `distribution` | `extent` \| `spacing` | `"extent"` |  |
| `direction_type` | `one` \| `symmetric` |  |  |
| `direction_type2` | `one` \| `symmetric` |  |  |

Examples:

- six copies of a component around Z:
  `{"component": "Part", "kind": "circular", "axis": "Z", "quantity": 6}`

<a id="insert_hardware"></a>

### `insert_hardware`: Insert hardware

Fusion: INSERT > Hardware (McMaster-Carr / fasteners in Fusion). Changes the design (one Undo step). Needs a solid body.

Insert a fastener with the hole it needs: click a flat face of the current body at at ([x, y, z], design coordinates) or a round edge (a hole's rim). standard iso4762 (socket head cap screw), iso7380 (button head), iso10642 (countersunk), iso4032 (hex nut), iso7089 (washer), insert (heat-set insert), magnet; size ("3" for M3, "6x3" for a magnet), length (mm), flip, make_hole (default true), fit close | normal | loose, sink_head (counterbore / countersink for the head), hole_depth all | length, clearance (a magnet's pocket, mm). The part becomes its own component.

| Argument | Type | Default | Description |
|---|---|---|---|
| `face` | object |  | the flat face clicked (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `at` | array of 3 numbers |  | where on it |
| `edge` | object |  | instead: a round edge (a hole's rim) (an edge selector: filters type, parallel, radius, on_faces, not_on_faces, at, all, count, any_of; see get_help topic selectors). Give count. |
| `standard` | `iso4762` \| `iso7380` \| `iso10642` \| `iso4032` \| `iso7089` \| `insert` \| `magnet` | `"iso4762"` |  |
| `size` | string |  | e.g. 3 (M3) or 6x3 |
| `length` | number |  | mm (> 0) |
| `flip` | boolean | `false` |  |
| `make_hole` | boolean | `true` |  |
| `fit` | `close` \| `normal` \| `loose` | `"normal"` |  |
| `sink_head` | boolean | `false` |  |
| `hole_depth` | `all` \| `length` | `"all"` |  |
| `clearance` | number |  | mm (>= 0) |

Examples:

- an M3 x 10 socket head screw with its hole:
  `{"face": {"normal": [0, 0, 1], "count": 1}, "at": [10, 10, 10], "standard": "iso4762", "size": "3", "length": 10}`

<a id="new_component"></a>

### `new_component`: New component

Fusion: ASSEMBLE > New Component. Changes the design (one Undo step). Needs nothing.

Make a new, empty component (Fusion's New Component) with its own body, inside parent (a component id) or at the top of the design; it becomes the active component, so the next sketches and features go into it. label names it.

| Argument | Type | Default | Description |
|---|---|---|---|
| `label` | string |  | its name |
| `parent` | string |  | the component it goes into |

Examples:

- a component called Lid, active:
  `{"label": "Lid"}`

<a id="components_from_bodies"></a>

### `components_from_bodies`: Components from bodies

Fusion: BROWSER > a body > Create Components from Bodies. Changes the design (one Undo step). Needs an open design.

Put bodies into components of their own (one component per body), so joints can move them. bodies: step ids; label names the component (one body).

| Argument | Type | Default | Description |
|---|---|---|---|
| `bodies` (required) | array of strings |  | the bodies |
| `label` | string |  | the new component's name |

Examples:

- Extrude1's body as Base:
  `{"bodies": ["Extrude1"], "label": "Base"}`

<a id="copy_component"></a>

### `copy_component`: Copy / paste component

Fusion: Copy (Ctrl+C) a component, then Paste / Paste New. Changes the design (one Undo step). Needs an open design.

Copy a component and paste it: new false (default) makes a linked instance (it changes with the original, Fusion's Paste), new true an independent copy (Paste New); moved by dx / dy / dz (mm).

| Argument | Type | Default | Description |
|---|---|---|---|
| `component` (required) | string |  | the component |
| `new` | boolean | `false` | Paste New: an independent copy |
| `dx` | number | `0` | (mm) |
| `dy` | number | `0` | (mm) |
| `dz` | number | `0` | (mm) |

Examples:

- a linked copy of Bolt 30 mm along X:
  `{"component": "Bolt", "dx": 30}`

<a id="activate"></a>

### `activate`: Activate body / component

Fusion: BROWSER > a body or component > Activate. Changes the design (one Undo step). Needs an open design.

Make a body (by any step in it) or a component the one you work in: the next sketches and features go into it (Fusion's Activate Component).

| Argument | Type | Default | Description |
|---|---|---|---|
| `target` (required) | string |  | a body, a step in it, or a component |

Examples:

- work in Extrude2's body:
  `{"target": "Extrude2"}`

<a id="new_body"></a>

### `new_body`: New body

Fusion: BROWSER > Bodies > New Body. Changes the design (one Undo step). Needs nothing.

Make a new, empty body in the active component and make it the active body: the next sketch and extrude go into it. label names it.

| Argument | Type | Default | Description |
|---|---|---|---|
| `label` | string |  | its name |

Examples:

- a new body called Insert:
  `{"label": "Insert"}`

<a id="joint"></a>

### `joint`: Joint

Fusion: ASSEMBLE > Joint (J). Changes the design (one Undo step). Needs an open design.

Fusion's Joint: the first component moves so that its snap point meets the second's. type rigid | revolute | slider | cylindrical | pinslot | planar | ball; first / second: {component, face | edge | vertex, snap, point}: the element is found on that component with a selector, snap picks which of its snap points (centre of a circle or face, vertex, midpoint...). offset x / y / z (mm), angle (degrees), flip; rotate / slide: the motion axis x | y | z. Answers where the component went and whether the joint holds.

| Argument | Type | Default | Description |
|---|---|---|---|
| `type` | `rigid` \| `revolute` \| `slider` \| `cylindrical` \| `pinslot` \| `planar` \| `ball` | `"rigid"` |  |
| `first` (required) | object |  | one side of a joint: a component and an element of it with a snap point |
| `second` (required) | object |  | one side of a joint: a component and an element of it with a snap point |
| `offset` | array of 3 numbers |  | [x, y, z] offset of the joint origin (mm) |
| `angle` | number | `0` | (degrees) |
| `flip` | boolean | `false` |  |
| `rotate` | `x` \| `y` \| `z` |  | the rotation axis |
| `slide` | `x` \| `y` \| `z` |  | the slide axis |

Examples:

- the wheel turns on the axle:
  `{"type": "revolute", "first": {"component": "Wheel", "face": {"type": "cylinder", "count": 1}, "snap": "circle"}, "second": {"component": "Axle", "face": {"type": "cylinder", "count": 1}, "snap": "circle"}}`

<a id="drive_joint"></a>

### `drive_joint`: Drive joint

Fusion: ASSEMBLE > Drive Joints. Changes the design (one Undo step). Needs an open design.

Put a joint at an angle (degrees) and / or slide distance (mm), within its limits; what hangs on it follows. joint: its id.

| Argument | Type | Default | Description |
|---|---|---|---|
| `joint` (required) | string |  | the joint |
| `angle` | number |  | (degrees) |
| `slide` | number |  | (mm) |

Examples:

- turn the revolute joint to 45 degrees:
  `{"joint": "Joint1", "angle": 45}`

<a id="ground"></a>

### `ground`: Ground / unground

Fusion: BROWSER > a component > Ground. Changes the design (one Undo step). Needs an open design.

Ground a component (it never moves when joints solve) or unground it (ground: false).

| Argument | Type | Default | Description |
|---|---|---|---|
| `component` (required) | string |  | the component or body |
| `ground` | boolean | `true` |  |

Examples:

- the base stays put:
  `{"component": "Base"}`

## Timeline (history)

<a id="capture_design_history"></a>

### `capture_design_history`: Capture design history

Fusion: the design's menu: Capture Design History / Do Not Capture Design History. Changes the design (one Undo step), destructive. Needs an open design.

Turn the timeline on or off for the design (Fusion's Capture Design History). on: false freezes every body into one step (direct modelling: press_pull, move_copy... still work); on: true starts a timeline again from there.

| Argument | Type | Default | Description |
|---|---|---|---|
| `on` (required) | boolean |  | capture the history |

Examples:

- switch to direct modelling (no timeline):
  `{"on": false}`

<a id="get_timeline"></a>

### `get_timeline`: Get timeline

Fusion: TIMELINE (the bar at the bottom). Read-only. Needs an open design.

List the timeline in order: every step with its id, its name as the timeline shows it ("Extrude 2"), its kind, the body / component it belongs to, whether it is before the history marker (done) or after it (rolled_back), suppressed, its status (ok, warning, error, with the reason in plain words) and its main values (distance, radius, quantity...); plus where the history marker stands.

No arguments.

Examples:

- the steps, their state and the marker:
  `{}`

<a id="get_step"></a>

### `get_step`: Get step

Fusion: TIMELINE > double-click a step (the dialog's fields). Read-only. Needs an open design.

Read one step's definition, the way its dialog shows it when you double-click it: its kind and every option (distances, angles, operation, what it is built on), the formulas that drive values, its status and what it uses. The names of the options are the ones edit_step takes.

| Argument | Type | Default | Description |
|---|---|---|---|
| `step` (required) | string |  | the step |

Examples:

- Extrude1's options:
  `{"step": "Extrude1"}`

<a id="edit_step"></a>

### `edit_step`: Edit step

Fusion: TIMELINE > double-click a step > change its fields > OK. Changes the design (one Undo step). Needs an open design.

Change an existing step's options, as double-clicking it in the timeline: set {option: value} with the names get_step shows (extrude: distance, distance2, taper, direction, operation, through_all...; revolve: angle, type, direction, operation; fillet / chamfer: radius, distance...; hole: diameter, depth, extent, hole_type...; patterns: quantity, distance, angle...; shell, draft, scale, sweep, loft, rib, primitives, coil, pipe, gear, hardware, emboss, thread, surface, combine, split, move, align, construction planes...). A fillet or chamfer also takes add_edges / add_faces (more edges). The steps after it update and keep their faces and edges; steps that break are named in the answer.

| Argument | Type | Default | Description |
|---|---|---|---|
| `step` (required) | string |  | the step to change |
| `set` | object |  | {option: value} |
| `add_edges` | object |  | fillet / chamfer: more edges (an edge selector: filters type, parallel, radius, on_faces, not_on_faces, at, all, count, any_of; see get_help topic selectors). Give count. |
| `add_faces` | object |  | fillet / chamfer: every edge around more faces (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |

Examples:

- make the extrude 15 mm:
  `{"step": "Extrude1", "set": {"distance": 15}}`
- change the fillet to 2 mm:
  `{"step": "Fillet1", "set": {"radius": 2}}`

<a id="roll_timeline"></a>

### `roll_timeline`: Move history marker

Fusion: TIMELINE > drag the history marker (and the playback buttons). Changes the design (one Undo step). Needs an open design.

Move the timeline's history marker: to start (an empty design), end, previous / next (one step), or after / before a step. Steps after the marker are rolled back (not computed); a new feature goes in at the marker, as in Fusion. Move it back to the end when you are done.

| Argument | Type | Default | Description |
|---|---|---|---|
| `to` | `start` \| `end` \| `previous` \| `next` |  |  |
| `after` | string |  | put the marker right after this step |
| `before` | string |  | put the marker right before this step |

Examples:

- roll back to just after Extrude1:
  `{"after": "Extrude1"}`
- roll forward to the end:
  `{"to": "end"}`

<a id="suppress_step"></a>

### `suppress_step`: Suppress / unsuppress

Fusion: TIMELINE > right-click a step > Suppress Features. Changes the design (one Undo step). Needs an open design.

Suppress steps (they stay in the timeline but are skipped, as if they were not there) or bring them back (suppress: false). Steps that depend on them are suppressed with them; the answer names them.

| Argument | Type | Default | Description |
|---|---|---|---|
| `steps` (required) | array of strings |  | the steps |
| `suppress` | boolean | `true` |  |

Examples:

- try the part without the fillet:
  `{"steps": ["Fillet1"]}`

<a id="delete_step"></a>

### `delete_step`: Delete step

Fusion: TIMELINE > right-click a step > Delete. Changes the design (one Undo step), destructive. Needs an open design.

Delete steps from the timeline (Fusion asks the same: steps that depend on them may break and are named in the answer). Undo brings them back.

| Argument | Type | Default | Description |
|---|---|---|---|
| `steps` (required) | array of strings |  | the steps |

Examples:

- delete the chamfer:
  `{"steps": ["Chamfer1"]}`

<a id="move_step"></a>

### `move_step`: Reorder step

Fusion: TIMELINE > drag a step. Changes the design (one Undo step). Needs an open design.

Move a step before or after another one in the timeline. A step can never move before what it is built on: the refusal says why.

| Argument | Type | Default | Description |
|---|---|---|---|
| `step` (required) | string |  | the step |
| `before` | string |  | id of an earlier step |
| `after` | string |  | id of an earlier step |

Examples:

- fillet after the boss:
  `{"step": "Fillet1", "after": "Extrude2"}`

<a id="rename"></a>

### `rename`: Rename

Fusion: TIMELINE / BROWSER > right-click > Rename. Changes the design (one Undo step). Needs an open design.

Rename a timeline step, a body, a component, a sketch or a drawing (what the timeline and browser show). The id stays the same.

| Argument | Type | Default | Description |
|---|---|---|---|
| `target` (required) | string |  | the thing to rename |
| `name` (required) | string |  | the new name |

Examples:

- name the first extrude:
  `{"target": "Extrude1", "name": "Base plate"}`

<a id="group_steps"></a>

### `group_steps`: Group steps

Fusion: TIMELINE > select steps > right-click > Group. Changes the design (one Undo step). Needs an open design.

Group neighbouring timeline steps under one name (Fusion's timeline groups), or ungroup (ungroup: true with the group's id).

| Argument | Type | Default | Description |
|---|---|---|---|
| `steps` | array of strings |  | the steps (next to each other) |
| `name` | string |  | the group's name |
| `ungroup` | boolean | `false` |  |
| `group` | string |  | ungroup: the group's id (get_timeline) |

Examples:

- group the boss:
  `{"steps": ["Sketch2", "Extrude2"], "name": "Boss"}`

## Parameters

<a id="set_parameter"></a>

### `set_parameter`: Set parameter

Fusion: MODIFY > Change Parameters (User Parameters, +). Changes the design (one Undo step). Needs nothing.

Create or change a user parameter (SciForge's Change Parameters). value is a number or an expression using other parameters, e.g. "width / 4". unit: mm (default), deg or empty for a plain number. Everything that uses the parameter updates.

| Argument | Type | Default | Description |
|---|---|---|---|
| `name` (required) | string |  | letters, digits and _ |
| `value` (required) | number or string |  |  |
| `unit` | string | `"mm"` |  |
| `comment` | string |  | a note shown in Change Parameters |

Examples:

- width follows depth:
  `{"name": "width", "value": "depth * 2", "unit": "mm"}`

<a id="list_parameters"></a>

### `list_parameters`: List parameters

Fusion: MODIFY > Change Parameters. Read-only. Needs an open design.

List the design's parameters, as Change Parameters shows them: user parameters (name, unit, formula, value, comment), parameters brought in by a Derive (read-only), and model parameters: every dimension in the design (each step's values and each sketch dimension: the step id, its label, value, unit and formula).

| Argument | Type | Default | Description |
|---|---|---|---|
| `model` | boolean | `true` | include the model parameters |

Examples:

- every parameter and dimension:
  `{}`

<a id="delete_parameter"></a>

### `delete_parameter`: Delete parameter

Fusion: MODIFY > Change Parameters > a user parameter > Delete. Changes the design (one Undo step), destructive. Needs an open design.

Delete a user parameter. Refused, with the names, while formulas still use it.

| Argument | Type | Default | Description |
|---|---|---|---|
| `name` (required) | string |  | the parameter |

Examples:

- delete the unused parameter gap:
  `{"name": "gap"}`

<a id="set_model_parameter"></a>

### `set_model_parameter`: Set model parameter

Fusion: MODIFY > Change Parameters > Model Parameters. Changes the design (one Undo step). Needs an open design.

Change a model parameter: one value of a step (label as list_parameters shows it: "Distance", "Radius", "Set 1 Size", "Quantity"...) or a sketch dimension (its name or label). value (mm / degrees / a count) or expression (a formula with user parameters, kept as a link). Everything after it updates.

| Argument | Type | Default | Description |
|---|---|---|---|
| `step` (required) | string |  | the step or sketch |
| `label` (required) | string |  | which of its values (from list_parameters) |
| `value` | number |  |  |
| `expression` | string |  | a formula |

Examples:

- Extrude1's distance follows the parameter height:
  `{"step": "Extrude1", "label": "Distance", "expression": "height"}`

## Import and export

<a id="export"></a>

### `export`: Export

Fusion: File > Export. Writes files. Needs an open design.

Export the design's bodies to a file: format step (.step / .stp), stl or 3mf (for 3D printing). path is a full path; replacing an existing file must be confirmed by the person in SciForge. Also: iges (.igs), stl_ascii, obj, brep, and dxf (one sketch, or one flat face, as 2D curves: give sketch or face). bodies: step ids of the bodies to write (default every visible body); mesh formats take refinement Low | Medium | High (Fusion's presets), unit (Millimeter, Centimeter, Meter, Inch, Foot) and one_file_per_body. STEP keeps the components and colours; mesh files keep only the triangles (no sketches, timeline or parameters).

| Argument | Type | Default | Description |
|---|---|---|---|
| `format` (required) | `step` \| `stl` \| `3mf` \| `iges` \| `stl_ascii` \| `obj` \| `brep` \| `dxf` |  |  |
| `path` (required) | string |  |  |
| `bodies` | array of strings |  | the bodies to write (default: every visible body) |
| `sketch` | string |  | format dxf: the sketch to write |
| `face` | object |  | format dxf: the flat face to write (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `refinement` | `Low` \| `Medium` \| `High` | `"Medium"` |  |
| `unit` | `Millimeter` \| `Centimeter` \| `Meter` \| `Inch` \| `Foot` | `"Millimeter"` |  |
| `one_file_per_body` | boolean | `false` | mesh formats: one file per body |

Examples:

- an STL for 3D printing:
  `{"format": "stl", "path": "/home/me/part.stl"}`
- Sketch1 as a DXF for a laser cutter:
  `{"format": "dxf", "path": "/home/me/outline.dxf", "sketch": "Sketch1"}`

<a id="import_file"></a>

### `import_file`: Insert file

Fusion: INSERT > Insert Mesh / Insert DXF / Insert STEP, and Insert into Current Design. Changes the design (one Undo step). Needs nothing.

Bring a file into the active design: STEP / IGES (one component with the file's structure, its bodies and colours), STL / OBJ / 3MF (a mesh body; unit: the file's unit), DXF (its curves into a new sketch on sketch_plane XY | XZ | YZ, ready to extrude), FCStd (another design's bodies as a component). label names what is made.

| Argument | Type | Default | Description |
|---|---|---|---|
| `path` (required) | string |  | full path of the file |
| `unit` | `mm` \| `cm` \| `m` \| `in` \| `ft` | `"mm"` | mesh / DXF files: the file's unit |
| `sketch_plane` | `XY` \| `XZ` \| `YZ` | `"XY"` | DXF: the plane |
| `label` | string |  | the name of what is made |

Examples:

- a motor model as a component:
  `{"path": "/home/me/parts/motor.step"}`
- a DXF outline as a sketch:
  `{"path": "/home/me/logo.dxf", "sketch_plane": "XY"}`

## Drawings

<a id="create_drawing"></a>

### `create_drawing`: Create drawing

Fusion: File > New Drawing > From Design. Changes the design (one Undo step). Needs a solid body.

Make a 2D drawing of the design (Fusion's New Drawing From Design), kept in the design and updated with it: bodies (step ids, default every visible body), standard ISO | ASME, sheet (A4..A0 for ISO, A..E for ASME), units mm | in, title_block; a base view (base_view orientation Front, Back, Top, Bottom, Left, Right or Home (isometric), at [x, y] on the sheet in mm from the bottom left, scale, style) and projected views (projected: Top, Right, FrontTopRight... placed next to it). Answers the drawing's and views' ids.

| Argument | Type | Default | Description |
|---|---|---|---|
| `bodies` | array of strings |  | the bodies to draw (default: every visible body) |
| `standard` | `ISO` \| `ASME` | `"ISO"` |  |
| `sheet` | string |  | A4, A3, A2, A1, A0 (ISO) or A, B, C, D, E (ASME) |
| `units` | `mm` \| `in` | `"mm"` |  |
| `title_block` | boolean | `true` |  |
| `label` | string |  | the drawing's name |
| `base_view` | `Front` \| `Back` \| `Top` \| `Bottom` \| `Left` \| `Right` \| `Home` | `"Front"` | the base view's orientation |
| `at` | array of 2 numbers |  | [x, y] of the base view on the sheet (mm) |
| `scale` | number |  | view scale (default: fits the sheet) (> 0) |
| `style` | `Visible Edges` \| `Visible and Hidden Edges` \| `Shaded` \| `Shaded with Hidden Edges` | `"Visible and Hidden Edges"` |  |
| `projected` | array of strings |  | projected views to add |

Examples:

- the classic three views plus an isometric:
  `{"base_view": "Front", "projected": ["Top", "Right", "FrontTopRight"]}`

<a id="add_drawing_view"></a>

### `add_drawing_view`: Add drawing view

Fusion: DRAWING > CREATE > Base View / Projected View / Section View / Detail View. Changes the design (one Undo step). Needs a drawing.

Add a view to a drawing: kind base (orientation, at, scale, style), projected (parent view id, direction Top / Right / ... / FrontTopRight), section (parent, line [[x1, y1], [x2, y2]] in the parent view's own mm from its centre, side 1 | -1) or detail (parent, center [x, y] in the parent's mm, radius, scale). at: where on the sheet [x, y] mm.

| Argument | Type | Default | Description |
|---|---|---|---|
| `drawing` | string |  | the drawing (default: the newest) |
| `kind` (required) | `base` \| `projected` \| `section` \| `detail` |  |  |
| `parent` | string |  | the view it is made from |
| `orientation` | `Front` \| `Back` \| `Top` \| `Bottom` \| `Left` \| `Right` \| `Home` |  |  |
| `direction` | `Top` \| `Bottom` \| `Left` \| `Right` \| `FrontTopRight` \| `FrontTopLeft` \| `FrontBottomRight` \| `FrontBottomLeft` |  |  |
| `line` | array of 2 arrays |  | section line [[x1, y1], [x2, y2]] |
| `side` | integer |  | section: 1 looks from the left of the line's direction, -1 from the right (default: from where the view is placed) |
| `center` | array of 2 numbers |  | detail centre [x, y] |
| `radius` | number |  | detail circle radius (mm) (> 0) |
| `at` | array of 2 numbers |  | [x, y] on the sheet (mm) |
| `scale` | number |  | (> 0) |
| `style` | `Visible Edges` \| `Visible and Hidden Edges` \| `Shaded` \| `Shaded with Hidden Edges` |  |  |
| `label` | string |  | section / detail letter |

Examples:

- a section through the middle of the base view:
  `{"kind": "section", "parent": "BaseView", "line": [[-50, 0], [50, 0]]}`

<a id="add_drawing_dimension"></a>

### `add_drawing_dimension`: Add drawing dimension

Fusion: DRAWING > DIMENSIONS > Dimension. Changes the design (one Undo step). Needs a drawing.

Dimension a drawing view, as Fusion's Dimension command does from what is clicked: one line (its length, horizontal / vertical / aligned), one circle (diameter) or arc (radius), two points / lines (the distance or angle between them). picks: the view's elements, each {kind: line | circle | arc | vertex, near: [x, y] in the view's own mm from its centre (get_drawing lists the elements), radius}; type forces a kind of dimension (linear, aligned, radius, diameter, angular); at: where the text goes on the sheet [x, y] mm. Answers the measured value.

| Argument | Type | Default | Description |
|---|---|---|---|
| `view` (required) | string |  | the view |
| `picks` (required) | array of objects |  | one or two elements |
| `type` | `linear` \| `aligned` \| `radius` \| `diameter` \| `angular` |  |  |
| `at` | array of 2 numbers |  | text position on the sheet (mm) |

Examples:

- the diameter of the 6 mm hole:
  `{"view": "BaseView", "picks": [{"kind": "circle", "radius": 3}]}`

<a id="add_drawing_annotation"></a>

### `add_drawing_annotation`: Add drawing annotation

Fusion: DRAWING > TEXT / TABLES / SYMBOLS (Text, Table (parts list), Center Mark). Changes the design (one Undo step). Needs a drawing.

Add to a drawing: kind text (text lines at [x, y], size mm), parts_list (a table of the view's components with balloons, at = its top-left corner) or center_marks (a centre mark on every circle of a view).

| Argument | Type | Default | Description |
|---|---|---|---|
| `drawing` | string |  | the drawing (default: the newest) |
| `kind` (required) | `text` \| `parts_list` \| `center_marks` |  |  |
| `text` | string |  | text (new lines split it) |
| `size` | number | `3.5` | text height (mm) (> 0) |
| `view` | string |  | parts list / centre marks: the view |
| `at` | array of 2 numbers |  | [x, y] on the sheet (mm) |
| `balloons` | boolean | `true` | parts list: balloons on the view |

Examples:

- a note on the sheet:
  `{"kind": "text", "text": "Break all sharp edges", "at": [20, 40]}`

<a id="get_drawing"></a>

### `get_drawing`: Get drawing

Fusion: BROWSER > Drawings. Read-only. Needs a drawing.

Describe drawings: each drawing's id, sheet, standard, units, title block values and views (id, kind, orientation, scale, position on the sheet, size) with their dimensions (value) and, with edges true, each view's elements (lines with ends, circles with centre and radius, in the view's own mm from its centre) for add_drawing_dimension.

| Argument | Type | Default | Description |
|---|---|---|---|
| `drawing` | string |  | one drawing (default: all) |
| `edges` | boolean | `false` | list each view's lines and circles |

Examples:

- views and their lines and circles:
  `{"edges": true}`

<a id="export_drawing"></a>

### `export_drawing`: Export drawing

Fusion: DRAWING > EXPORT > Output PDF / Output DXF. Writes files. Needs a drawing.

Export a drawing: format pdf (every sheet in one PDF; needs the SciForge window) or dxf (the sheet: frame, views on their own layers, dimensions, text). Replacing an existing file must be confirmed by the person in SciForge.

| Argument | Type | Default | Description |
|---|---|---|---|
| `drawing` | string |  | the drawing (default: the newest) |
| `format` (required) | `pdf` \| `dxf` |  |  |
| `path` (required) | string |  | full path |

Examples:

- a PDF of the drawing:
  `{"format": "pdf", "path": "/home/me/bracket.pdf"}`

## View

<a id="screenshot"></a>

### `screenshot`: Screenshot

Fusion: File > Capture Image. Read-only. Needs an open design, the SciForge window.

Take a picture (PNG) of the design as SciForge shows it, to see what you built. view picks the camera: iso (default), front, back, top, bottom, left or right.

| Argument | Type | Default | Description |
|---|---|---|---|
| `view` | `iso` \| `front` \| `back` \| `top` \| `bottom` \| `left` \| `right` | `"iso"` |  |
| `width` | integer | `1024` | picture width in pixels (>= 64, <= 4096) |
| `height` | integer | `768` | picture height in pixels (>= 64, <= 4096) |

Examples:

- a top view, 800 x 600:
  `{"view": "top", "width": 800, "height": 600}`

<a id="set_view"></a>

### `set_view`: Set view

Fusion: NAVIGATION BAR and VIEWCUBE (Home, Fit, Orbit, Look At). Read-only. Needs an open design, the SciForge window.

Turn the 3D view: orientation iso | home | front | back | top | bottom | left | right, fit (zoom so everything shows, default true), projection perspective | orthographic, or camera (a camera string get_view returned), or look_at: a face selector (the view looks straight at that face, Fusion's Look At).

| Argument | Type | Default | Description |
|---|---|---|---|
| `orientation` | `iso` \| `home` \| `front` \| `back` \| `top` \| `bottom` \| `left` \| `right` |  |  |
| `fit` | boolean | `true` |  |
| `projection` | `perspective` \| `orthographic` |  |  |
| `camera` | string |  | a camera description from get_view |
| `look_at` | object |  | look straight at this face (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |

Examples:

- look from the top, fitted:
  `{"orientation": "top"}`

<a id="get_view"></a>

### `get_view`: Get view

Fusion: (the 3D view's camera). Read-only. Needs an open design, the SciForge window.

The 3D view's camera now (a string set_view takes back), its projection, and the saved named views of the design.

No arguments.

Examples:

- the camera and the named views:
  `{}`

<a id="named_view"></a>

### `named_view`: Named view

Fusion: BROWSER > Named Views (New Named View, go to, delete). Changes the design (one Undo step). Needs an open design.

Named views kept in the design (Fusion's Named Views): action save (the current camera under name), go (turn the view to it), delete, list.

| Argument | Type | Default | Description |
|---|---|---|---|
| `action` (required) | `save` \| `go` \| `delete` \| `list` |  |  |
| `name` | string |  | the view's name |

Examples:

- remember this camera:
  `{"action": "save", "name": "Assembly view"}`

<a id="show_hide"></a>

### `show_hide`: Show / hide

Fusion: BROWSER > the eye icon (Show / Hide). Changes the design (one Undo step). Needs an open design.

Show or hide bodies, components, sketches, construction geometry or drawings in the 3D view (they stay in the design). targets: ids; visible: true shows, false hides.

| Argument | Type | Default | Description |
|---|---|---|---|
| `targets` (required) | array of strings |  | what to show or hide |
| `visible` (required) | boolean |  |  |

Examples:

- hide Sketch1:
  `{"targets": ["Sketch1"], "visible": false}`

<a id="render"></a>

### `render`: Render

Fusion: File > Capture Image (returned to the AI as a picture). Read-only. Needs an open design.

Take a picture of the design and get the image itself (PNG), to look at what was built. view: iso (default: from front, right and top, as Fusion's Home view), front, back, top, bottom, left or right; or direction [x, y, z]: where the camera looks from. fit (default true) frames the whole design. highlight: {faces: selector, edges: selector, of: step id} marks those faces / edges in orange (check what a selector picks before using it). renderer: window (SciForge's own 3D view, as the person sees it), software (a simple picture of the solids drawn by SciForge itself: works without the window), auto (default: the window when there is one). Numbers from inspect_design / query_geometry are more exact than a picture: use both.

| Argument | Type | Default | Description |
|---|---|---|---|
| `view` | `iso` \| `front` \| `back` \| `top` \| `bottom` \| `left` \| `right` | `"iso"` |  |
| `direction` | array of 3 numbers |  | where the camera looks from |
| `width` | integer | `800` | picture width in pixels (>= 64, <= 2048) |
| `height` | integer | `600` | picture height in pixels (>= 64, <= 2048) |
| `fit` | boolean | `true` | frame the whole design |
| `highlight` | object |  | faces / edges to mark in orange |
| `edges` | boolean | `true` | draw the edges (software renderer) |
| `renderer` | `auto` \| `window` \| `software` | `"auto"` |  |

Examples:

- an iso picture of the whole design, 800 x 600:
  `{}`
- from the top, the round faces (holes) in orange:
  `{"view": "top", "highlight": {"faces": {"type": "cylinder"}}}`
- a quick small picture:
  `{"renderer": "software", "width": 400, "height": 300}`

## Shared rules

<a id="help-overview"></a>

### overview

SciForge is a parametric CAD program (built on FreeCAD) that works like Autodesk Fusion. These tools build and change the design open in SciForge step by step in its timeline, with the same code as SciForge's own dialogs; every change is one undo step. All lengths are in millimetres (mm) and all angles in degrees. Faces and edges are picked with selectors that describe their geometry (get_help topic selectors), never by internal names. Steps, sketches, bodies and components are named by the ids the tools report and get_design / get_timeline list (for example 'Sketch1', 'Extrude2'). A body is named by any step in it (the step that made it, usually). Errors come back as plain sentences: read them, fix the arguments and try again. Read-only tools (inspect_design, query_geometry, check_design, render, diff_design, get_design, get_timeline, get_step, measure, physical_properties...) never change anything.

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

Each geometry item is an object with exactly one of: rect [x0, y0, x1, y1] (two opposite corners), center_rect [cx, cy, width, height], circle [cx, cy, radius], polyline [[x, y], ...] (at least 3 corners, always closed), polygon {center: [x, y], radius, sides, rotation} (a regular polygon with its corners on that radius; rotation in degrees), slot [x1, y1, x2, y2, width] (a straight slot between two centre points), line [x0, y0, x1, y1] (one open line: it makes no area). Optional name: dimensions <name>.width, <name>.height, <name>.x, <name>.y (rectangles) or <name>.diameter, <name>.x, <name>.y (circles). Shapes inside each other make separate areas (a circle inside a rectangle makes a ring area and a disc area). Also: ellipse [cx, cy, major, minor] (major radius along x, the larger), spline_loop [[x, y], ...] (a closed smooth curve through at least 3 points), segments [{line: [x0, y0, x1, y1]} | {arc: [cx, cy, r, a0, a1]} | {spline: [[x, y], ...], tangents: [[tx, ty], [tx, ty]]}, ...] (a closed chain of lines, arcs counter-clockwise from a0 to a1 degrees, and open splines; each piece starts where the one before ends).

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
