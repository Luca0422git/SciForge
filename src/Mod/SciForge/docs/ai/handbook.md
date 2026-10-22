# SciForge handbook for AI models

How SciForge works and how to build in it well with its tools. Read this first; the other
documents go deeper: [sketches.md](sciforge://docs/sketches.md) (sketches and profiles),
[selectors.md](sciforge://docs/selectors.md) (picking faces and edges, with a cookbook),
[checking.md](sciforge://docs/checking.md) (verifying your work),
[troubleshooting.md](sciforge://docs/troubleshooting.md) (failures and how to recover),
[recipes](sciforge://docs/recipes/index.md) (whole parts step by step) and
`reference/<tool>.md` (every argument of every tool, with a real example).

The blocks marked `sciforge-calls` in these documents are tool calls that SciForge's tests
run in real FreeCAD, in order, for every document: each is `{"tool", "args"}` plus
`expect`, what the answer must contain (texts, JSON values with a tolerance, a picture's
size). `expect` is not a tool argument: send only `args`.

## What SciForge is

SciForge is a parametric CAD program built on FreeCAD 1.1 that works like Autodesk Fusion:
the same workspaces, ribbon, timeline, browser and dialogs, the same keyboard shortcuts, and
the same way of building a part from sketches and features that stay editable. Under it,
FreeCAD's PartDesign and OpenCASCADE do the geometry. The AI tools are the same code as
SciForge's own dialogs: an `extrude` call builds exactly what the Extrude dialog builds, and
the result is a step in the timeline that the person can double-click and edit.

What SciForge does not have (yet): sheet metal, T-spline sculpting, simulation, rendering,
CAM, electronics, `.f3d` files (Fusion's format is closed: STEP comes in fine). The person's
own documentation lists what is built and what is not: [known issues](sciforge://docs/user/known-issues.md),
[feature outline](sciforge://docs/user/feature-outline.md) and one Fusion parity spec per
feature (`user/parity/<feature>.md`).

## How you work with SciForge

You call tools; each answers in plain sentences, often followed by JSON:

- A tool that changes the design answers `Done: <what>. Its id is '<id>'. Bodies now: ...`
  with every solid body's volume and size, so you can check the change at once. When the
  change broke later steps it says `These steps now fail: ...`; when it changed no solid at
  all it ends with `Warning: no solid changed ...` (a cut that pointed away from the part, a
  wall thicker than the part).
- A tool that fails changes nothing and says why in one sentence: `Not done (AI: Fillet
  30 mm): Radius 30 mm is too big here: ...`. Read it, fix the arguments, call again.
- Arguments that break a tool's rules are refused before anything runs: `Not done: give
  profile (a sketch id) or face (a flat face selector), one of them.`
- Read-only tools (`get_design`, `inspect_design`, `query_geometry`, `check_design`, `measure`,
  `render`, `diff_design`, `get_timeline`, `get_step`, `get_sketch`, `list_parameters`,
  `physical_properties`, the documentation tools...) never change anything; call them as often
  as you like.
- In the SciForge window, the person is asked once per session whether an AI app may control
  SciForge, and every time a file would be overwritten. While a dialog, a sketch or a
  question is open in SciForge, changing calls answer that SciForge is busy.
- Without the window (`sciforge-cli`, the MCP server's `--headless` mode) the same tools run
  on designs opened there; the few that need the window (`screenshot`, `set_view`, `get_view`,
  PDF drawing export) say so, and `render` draws its pictures with SciForge's own software
  renderer.

```json sciforge-calls
[
  {"tool": "get_design", "args": {}, "expect": {"contains": ["No design is open"]}},
  {"tool": "new_design", "args": {"name": "Handbook"},
   "expect": {"contains": ["New design 'Handbook'", "the active design"]}},
  {"tool": "extrude", "args": {"profile": "Sketch9"}, "expect": {"error": true,
   "contains": ["distance is missing"]}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]},
   "expect": {"contains": ["Done: AI: Sketch on XY. Its id is 'Sketch1'."]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10},
   "expect": {"contains": ["Its id is 'Extrude1'", "Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm."]}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4},
    "radius": 30},
   "expect": {"error": true, "contains": ["Radius 30 mm is too big here"]}}
]
```

<a id="units-and-coordinates"></a>

## Units and coordinates

All lengths are millimetres and all angles degrees, in every argument and every answer
(areas mm2, volumes mm3, masses grams). The design's axes are Fusion's with Z up: X to the
right, Y away from you, Z up; the Home (iso) view looks from the front-right-top.

The three origin planes and their sketch coordinates:

| Plane | Normal (extrude direction) | Sketch x is | Sketch y is | `offset` d puts the plane at |
|---|---|---|---|---|
| XY | +Z | X | Y | z = d |
| XZ | -Y | X | Z | y = -d |
| YZ | +X | Y | Z | x = d |

So an extrude from an XZ sketch goes toward -Y, and on XZ a positive offset moves the sketch
to negative Y. A sketch on a flat face of the part (`create_sketch` with `face`) has its own
x / y axes; on a face that faces +Z (a top face) they are the design's X and Y, and
`get_sketch` always tells (its `placement`: origin, normal, x axis).

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Planes"}},
  {"tool": "create_sketch", "args": {"plane": "XZ", "geometry": [{"rect": [0, 0, 20, 10]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 5}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"bodies.0.bbox_mm.min": [0.0, -5.0, 0.0],
     "bodies.0.bbox_mm.max": [20.0, 0.0, 10.0]}}},
  {"tool": "create_curve_sketch", "args": {"plane": "XZ", "offset": 10,
    "curves": [{"point": [0, 0]}]}},
  {"tool": "get_sketch", "args": {"sketch": "Sketch2"},
   "expect": {"json": {"placement.origin": [0.0, -10.0, 0.0],
     "placement.normal": [0.0, -1.0, 0.0]}}},
  {"tool": "create_sketch", "args": {"plane": "YZ", "geometry": [{"rect": [0, 0, 20, 10]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch3", "distance": 5, "operation": "new_body"}},
  {"tool": "inspect_design", "args": {"bodies": ["Extrude2"]},
   "expect": {"json": {"bodies.0.bbox_mm.min": [0.0, 0.0, 0.0],
     "bodies.0.bbox_mm.max": [5.0, 20.0, 10.0]}}}
]
```

## Fusion's ideas in SciForge

| Fusion | SciForge (and the tools) |
|---|---|
| Timeline | The same: every feature is a step, in order. `get_timeline` lists them, `get_step` reads one, `edit_step` changes one, `suppress_step`, `delete_step`, `move_step`, `rename`, `group_steps` |
| History marker | The same: `roll_timeline` moves it; steps after it are rolled back; new features go in at the marker |
| Capture Design History off (direct modelling) | `capture_design_history` with `on: false` |
| Bodies | Bodies (FreeCAD's PartDesign bodies). `new_body`, `activate`, `combine`, `split_body`, `move_copy`, `delete_bodies` |
| Components | Components: a part with its own bodies that joints can move. `new_component`, `components_from_bodies`, `copy_component`, `ground`, `pattern_components` |
| Joints | `joint` (rigid, revolute, slider, cylindrical, pin-slot, planar, ball), `drive_joint` |
| Sketch, profiles | `create_sketch` (closed shapes = profiles), `create_curve_sketch` (open curves), `add_to_sketch`; the closed areas are the profiles; `regions` picks some |
| Sketch constraints and dimensions | `sketch_constraint`, `sketch_dimension`, `set_sketch_dimension`, `get_sketch` (degrees of freedom, conflicts) |
| Change Parameters | `set_parameter` (user parameters), `set_model_parameter` (a step's value or a sketch dimension, with a formula), `list_parameters` |
| Construction planes, axes, points | `construct_plane`, `construct_axis`, `construct_point`; sketch on a construction plane with `create_sketch` `on` |
| Selection (clicking faces / edges) | selectors: objects that describe the geometry ([selectors.md](sciforge://docs/selectors.md)) |
| INSPECT (Measure, Interference, Section Analysis, Center of Mass) | `measure`, `interference`, `section_analysis`, `center_of_mass`, `physical_properties`; plus `inspect_design`, `query_geometry`, `check_design`, `diff_design` for an AI |
| Physical Material, Appearance | `physical_material` (density, mass), `appearance` (colour), `list_materials` |
| Drawings | `create_drawing`, `add_drawing_view`, `add_drawing_dimension`, `add_drawing_annotation`, `get_drawing`, `export_drawing` |
| File > Export / Insert | `export` (STEP, IGES, STL, 3MF, OBJ, BREP, DXF), `import_file`, `save`, `save_as`, `open_design` |

<a id="timeline-and-history-marker"></a>

## The timeline and the history marker

Every feature is a step in the timeline, computed in order; a step uses what the steps
before it made. `get_timeline` lists the steps (index, id, name, kind, body, state `done` or
`rolled_back`, status, the error message of a failed step, the main values) and where the
history marker is.

`roll_timeline` moves the marker (`after` / `before` a step, `start`, `end`, `previous`,
`next`). Steps after it are rolled back: not computed, as if they were not there yet. A new
feature made while the marker is rolled back goes in at the marker, before the rolled-back
steps (a fillet or chamfer goes in there and keeps the later blends' edges). Move the marker
back to the end when you are done (`{"to": "end"}`), and check: inserting a feature can make
a later step lose its faces. While rolled back, the bodies in the answers are the bodies at
the marker (a feature inserted there may only show once the marker is at the end again),
and steps after the marker may show `status: error` because their faces are not there; they
normally recover at the end.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Marker"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4},
    "radius": 5}, "expect": {"contains": ["Its id is 'Fillet1'", "23785.4 mm3"]}},
  {"tool": "roll_timeline", "args": {"after": "Extrude1"},
   "expect": {"contains": ["1 step(s) rolled back", "24000 mm3"]}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10,
    "geometry": [{"circle": [30, 20, 5]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5},
   "expect": {"contains": ["Its id is 'Extrude2'"], "not_contains": ["Warning"]}},
  {"tool": "get_timeline", "args": {},
   "expect": {"json": {"steps.3.id": "Extrude2", "steps.4.id": "Fillet1",
     "steps.4.state": "rolled_back", "history_marker.at_end": false}}},
  {"tool": "roll_timeline", "args": {"to": "end"},
   "expect": {"contains": ["at the end", "24178.1 mm3", "60 x 40 x 15 mm"]}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}}
]
```

Other timeline tools: `suppress_step` (skip a step without deleting it; the steps that need
it are suppressed with it), `delete_step` (undo brings it back), `move_step` (never before
what it is built on), `edit_step` (change a step's options with the names `get_step` shows;
the later steps update), `rename`, `group_steps`.

<a id="bodies-and-components"></a>

## Bodies

A body is one solid (or a surface, or empty). Features go into the active body: the one the
last feature went into, or the one `new_body` / `activate` made active. `extrude`, `revolve`
and the other features take `operation`: `join` (default for extrude: add to the body),
`cut`, `intersect`, or `new_body`. A cut or join with `bodies` works on other bodies too.

A body is named by any of its steps (the step that made it, usually), or by its own id or
label: `get_design` lists `id` (FreeCAD's internal name, "Body001") and `label` (the name
shown, "Body2"). The body summary in every answer uses labels.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Bodies"}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "length": 20, "width": 20,
    "height": 10}, "expect": {"contains": ["Its id is 'Primitive1'", "Body1: 4000 mm3"]}},
  {"tool": "new_body", "args": {"label": "Second"},
   "expect": {"contains": ["new body 'Second' (id 'Body001')"]}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [30, 0, 40, 10]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 5},
   "expect": {"contains": ["Body1: 4000 mm3", "Second: 500 mm3"]}},
  {"tool": "activate", "args": {"target": "Primitive1"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10,
    "geometry": [{"circle": [10, 10, 3]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 2},
   "expect": {"contains": ["Body1: 4056.55 mm3", "Second: 500 mm3"]}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"bodies.1.id": "Body001", "bodies.1.label": "Second"}}}
]
```

<a id="components-and-joints"></a>

## Components and joints

A component is a part of an assembly with its own bodies (and its own origin): Fusion's
components. `new_component` makes one (and activates it: the next sketches and features go
into it); `components_from_bodies` puts existing bodies into components of their own;
`copy_component` pastes a linked instance (or an independent copy with `new: true`).

A joint moves the first component so that a snap point on it meets a snap point on the
second (Fusion's Joint): `first` / `second` are `{component, face | edge | vertex, snap}`
where the face / edge is found with a selector on that component, and `snap` picks which
point of it (`centre` of a circle or a flat face, a vertex, a midpoint...). `type` is rigid,
revolute, slider, cylindrical, pinslot, planar or ball. `ground` fixes a component; the joint
answers where the component went. `drive_joint` turns or slides a joint.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Assembly"}},
  {"tool": "new_component", "args": {"label": "Base"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [-30, -30, 30, 30]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "new_component", "args": {"label": "Wheel"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 20,
    "geometry": [{"circle": [0, 0, 15]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5}},
  {"tool": "ground", "args": {"component": "Base"}, "expect": {"contains": ["grounded"]}},
  {"tool": "joint", "args": {"type": "revolute",
    "first": {"component": "Wheel", "face": {"normal": [0, 0, -1], "count": 1}, "snap": "centre"},
    "second": {"component": "Base", "face": {"normal": [0, 0, 1], "at": {"axis": "z",
      "value": "max"}, "count": 1}, "snap": "centre"}},
   "expect": {"contains": ["revolute joint between Wheel and Base", "Its id is 'Joint'"]}},
  {"tool": "drive_joint", "args": {"joint": "Joint", "angle": 30}}
]
```

The wheel's underside (z = 20) was moved onto the base's top (z = 10): the joint answer
says "now at [0, 0, -10]", the component's move.

## Sketches and profiles

A sketch is drawn on a plane (an origin plane with an `offset`, a flat face of the part, or a
construction plane). `create_sketch` draws closed shapes (rectangles, circles, polygons,
slots, polylines, ellipses, closed chains of lines and arcs); its closed areas are the
profiles that `extrude`, `revolve`, `sweep` and `loft` use, and `hole` uses its circles'
centres. `create_curve_sketch` draws open curves and points (paths, rails, rib and web
curves, hole points). Shapes inside other shapes are holes in them unless `regions` picks
areas. Named shapes get named dimensions (`plate.width`) that `set_sketch_dimension`
changes, also with a formula. [sketches.md](sciforge://docs/sketches.md) has all of it.

Two rules that trip models up:
- A sketch on an origin plane with an `offset` stays where it is when the part changes; a
  sketch on a face (`face`) moves with that face. Sketch on the face when the sketch belongs
  to it (holes in a top face that must follow the thickness).
- Directions: an extrude goes along its sketch's normal (`flip: true` the other way), so a
  cut from a sketch lying on the top face needs `flip: true`; a hole drills against its
  sketch's normal, into the face the sketch lies on.

<a id="ids-and-names"></a>

## Ids and names

Every step, sketch, body and component has an id: the answers report it (`Its id is
'Extrude2'`), `get_design` and `get_timeline` list them. Use the id the answer gives: most
are a name and a number (Sketch1, Extrude1, Fillet1, Hole1, Pattern1, Primitive1, Gear1), but
not all (a joint can be `Joint`, a move `Move`, a component `Component001`). A rename
changes what is shown (the label); the id stays, and both work as a name.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Names"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 20, 20]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 5}},
  {"tool": "rename", "args": {"target": "Extrude1", "name": "Base plate"}},
  {"tool": "get_step", "args": {"step": "Base plate"}, "expect": {"contains": ["Extrude1"]}},
  {"tool": "edit_step", "args": {"step": "Extrude1", "set": {"distance": 8}},
   "expect": {"contains": ["3200 mm3"]}}
]
```

## Undo: how tool calls become undo steps

Every call that changes the design is exactly one undo step, named after the call ("AI:
Extrude 10 mm", "AI: Fillet 5 mm", "AI: Edit Extrude1"), the same as a step made by hand: the
person sees it in Edit > Undo and can undo it with Ctrl+Z, and the AI panel's **Undo last AI
step** button undoes the newest step when an AI made it. `undo` and `redo` do the same for
you, one call per step. A call that fails changes nothing, so there is nothing to undo. Files
written (`save`, `export`) are not undone. Opening, creating, switching and closing designs
are not undo steps either.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Undo"}},
  {"tool": "undo", "args": {}, "expect": {"error": true, "contains": ["nothing to undo"]}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "edit_step", "args": {"step": "Extrude1", "set": {"distance": 20}},
   "expect": {"contains": ["Done: AI: Edit Extrude1.", "48000 mm3"]}},
  {"tool": "undo", "args": {}, "expect": {"contains": ["Undo: AI: Edit Extrude1.", "24000 mm3"]}},
  {"tool": "undo", "args": {}, "expect": {"contains": ["Undo: AI: Extrude 10 mm.", "No solid body yet."]}},
  {"tool": "redo", "args": {}, "expect": {"contains": ["Redo: AI: Extrude 10 mm.", "24000 mm3"]}}
]
```

Over MCP, when SciForge's answer to a changing call is lost (the connection broke), the call
is not repeated by itself: the answer says it may or may not have been applied, so look
(`inspect_design`, or `diff_design` since a snapshot) before calling again.

## Parameters and design intent

Name the sizes that matter with `set_parameter` and drive the steps with formulas, so the
design stays easy to change: sketch dimensions with `set_sketch_dimension` (`expression`),
steps' values with `set_model_parameter` (its labels: `list_parameters`), and fields of
patterns, primitives, gears and other tools with `expressions` (`{"distance": "width - 2 *
margin"}`). A formula uses parameter names, + - * / ( ) and units (mm, deg). See
[the parametric plate](sciforge://docs/recipes/parametric-plate.md).

## A good way to work

1. Look first: `inspect_design` (or `list_designs`, `new_design`, `open_design`). It answers
   a snapshot id for `diff_design` later.
2. Plan in millimetres: base sketch and feature, then holes, patterns, fillets and chamfers
   last (rounds on edges that later features would cut are fragile, as in Fusion).
3. One step at a time. After each, read the numbers in the answer; when in doubt,
   `diff_design` since `last_change`. Before a fillet, chamfer, shell or draft, call
   `query_geometry` with the selector: it shows what it picks, with a `ref` for each element.
4. When a step fails, read the sentence; [troubleshooting.md](sciforge://docs/troubleshooting.md)
   lists the usual causes. `undo` takes back a step that came out wrong.
5. At the end: `check_design` (valid solids, no failed step, no overlapping bodies), the
   volume and bounding box against what was asked, a `render` from two views, then
   `physical_material`, `save_as` or `export` as the person wants.

When something is unclear (a size, which face, whether to replace a file), ask the person;
search this documentation (`docs_search`) before guessing how a tool behaves; look for a
tested example (`examples_search`) before inventing a sequence of calls.
