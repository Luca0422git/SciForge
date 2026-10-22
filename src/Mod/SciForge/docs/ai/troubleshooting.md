# Troubleshooting: failures and how to recover

What goes wrong most often when an AI builds in SciForge, what SciForge answers, and what to
do. A call that fails changes nothing (there is nothing to undo); a call that worked but did
the wrong thing is taken back with `undo`. Every block below is run by SciForge's tests, so
the messages are the real ones.

The part most blocks start from: a 60 x 40 x 10 plate.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Troubles"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10},
   "expect": {"contains": ["24000 mm3"]}}
]
```

## The selector picked the wrong number of elements

`count` protects the design: when the selector picks another number of elements, the tool
fails and lists what it picked. Fix the selector (add `type`, `at`, `radius`), or call
`query_geometry` with it to see what it picks and use the `ref` of the one you want.

```json sciforge-calls
[
  {"tool": "fillet", "args": {"edges": {"type": "line", "at": {"axis": "z", "value": "max"},
    "count": 3}, "radius": 2},
   "expect": {"error": true, "contains": ["picked 4 edges, expected 3"]}},
  {"tool": "fillet", "args": {"edges": {"type": "circle", "count": 1}, "radius": 2},
   "expect": {"error": true, "contains": ["picked 0 edges, expected 1: nothing"]}}
]
```

## A size that does not fit

A fillet or chamfer bigger than the faces next to it, a shell wall thicker than the part, a
draft angle steeper than the face takes, a press pull deeper than the part: the call fails
and changes nothing. SciForge never builds a smaller value in place of yours (you asked for
an exact value); instead the answer ends with the largest value that does fit, found by
trying smaller values (the same search SciForge's dialogs use when a person drags a value
past what fits): `Largest radius that fits here: 19.99 mm`. Every try rebuilds the design, so
the search has a time limit of a few seconds, every try counted: when it runs out the answer
says `Largest radius found that fits here` (a little more may fit), and on a design so big
that a single try takes longer than that, SciForge does not search at all and says so
(`SciForge did not search for the largest radius that fits`): try a smaller value yourself.
For a value that goes the other way (a press pull into the part, a negative angle) it says
`Furthest ... that fits here`. Use that value or less, or rethink the size. Changing a step
later with `edit_step` answers the same way. A size given as a formula (`expressions`) is
not searched.

```json sciforge-calls
[
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4},
    "radius": 30},
   "expect": {"error": true, "contains": ["Radius 30 mm is too big here",
     "Largest radius that fits here: 19.99 mm", "give radius 19.99 or less"]}},
  {"tool": "shell", "args": {"faces": {"normal": [0, 0, 1], "count": 1}, "thickness": 25},
   "expect": {"error": true, "contains": ["the value does not fit here",
     "Largest thickness that fits here: 9.99 mm"]}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4},
    "radius": 5}, "expect": {"contains": ["Its id is 'Fillet1'"]}},
  {"tool": "edit_step", "args": {"step": "Fillet1", "set": {"radius": 30}},
   "expect": {"error": true, "contains": ["Largest radius that fits here: 19.99 mm",
     "give set.radius 19.99 or less"]}},
  {"tool": "undo", "args": {}, "expect": {"contains": ["Undo: AI: Fillet 5 mm."]}}
]
```

Note the shell: OpenCASCADE quietly gives the plate back unchanged for a wall thicker than
the part; SciForge sees that the volume did not change and refuses it like any other size
that does not fit.

## It points the wrong way (nothing changed)

An extrude goes along its sketch's normal; a cut from a sketch on the top face (XY with
offset 10) goes up into empty space unless `flip` is true. A hole drills against its
sketch's normal: from a sketch on the bottom plane (XY, z = 0) it drills downward, away from
the part. In both cases the answer ends with `Warning: no solid changed`.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10,
    "geometry": [{"circle": [30, 20, 5]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 4, "operation": "cut"},
   "expect": {"contains": ["24000 mm3", "Warning: no solid changed"]}},
  {"tool": "undo", "args": {}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 4, "operation": "cut",
    "flip": true}, "expect": {"contains": ["23685.8 mm3"], "not_contains": ["Warning"]}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"circle": [10, 10, 2]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch3", "diameter": 4, "depth": 5},
   "expect": {"contains": ["Warning: no solid changed"]}},
  {"tool": "undo", "args": {}}
]
```

## Unknown ids

Ids come from the answers and from `get_timeline`; a typo or an id from another design fails
before anything changes.

```json sciforge-calls
[
  {"tool": "extrude", "args": {"profile": "Sketch9", "distance": 3},
   "expect": {"error": true, "contains": ["there is no step, sketch or body called 'Sketch9'"]}},
  {"tool": "edit_step", "args": {"step": "Fillet7", "set": {"radius": 1}},
   "expect": {"error": true}}
]
```

## No sketch area there

`regions` points must lie inside an area of the sketch (sketch coordinates); `get_sketch`
lists the areas with a point inside each.

```json sciforge-calls
[
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 5, "regions": [[70, 70]],
    "operation": "new_body"},
   "expect": {"error": true, "contains": ["no sketch area contains [70, 70]"]}}
]
```

## A later step broke

Changing an early step (or inserting one with the history marker rolled back) can take away
the faces or edges a later step was built on. The answer names the steps that now fail and
why; `check_design` lists them too. Fix them by editing them (`edit_step`: a fillet takes
`add_edges` to pick edges again), by undoing the change, or by suppressing or deleting the
broken step if it is no longer wanted.

```json sciforge-calls
[
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 0, 1],
    "not_on_faces": {"type": "cylinder"}, "count": 4}, "radius": 3},
   "expect": {"contains": ["Its id is 'Fillet1'"]}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}},
  {"tool": "edit_step", "args": {"step": "Fillet1", "set": {"radius": 25}},
   "expect": {"error": true}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}}
]
```

An edit that would break its own step is refused and the step stays as it was. Deleting a
step that a later one is built on breaks the later one (the hole's radius differs from the
fillets' 3 mm on purpose: the fillets' top arcs are circles of radius 3 too):

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10,
    "geometry": [{"circle": [45, 20, 2.5]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch4", "diameter": 5, "through_all": true},
   "expect": {"contains": ["Its id is 'Hole1'"]}},
  {"tool": "chamfer", "args": {"edges": {"type": "circle", "radius": 2.5,
    "at": {"axis": "z", "value": "max"}, "count": 1}, "distance": 0.5},
   "expect": {"contains": ["Its id is 'Chamfer1'"]}},
  {"tool": "delete_step", "args": {"steps": ["Hole1"]}, "expect": {"contains": ["Chamfer1"]}},
  {"tool": "check_design", "args": {},
   "expect": {"json": {"ok": false, "failed_steps.0.id": "Chamfer1"}}},
  {"tool": "undo", "args": {}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}}
]
```

## Rounding edges that are already smooth

The edge between a fillet and the face next to it is smooth (tangent): there is nothing to
round there, and SciForge says so instead of asking you to pick edges.

```json sciforge-calls
[
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "parallel": [0, 0, 1], "at": {"axis": "x", "value": "max"}}},
   "expect": {"json": {"count": 2}}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 0, 1],
    "at": {"axis": "x", "value": "max"}, "count": 2}, "radius": 1},
   "expect": {"error": true, "contains": ["smooth"]}}
]
```

## The tool needs something that is not there

```json sciforge-calls
[
  {"tool": "close_design", "args": {"discard_changes": true}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "count": 4}, "radius": 1},
   "expect": {"error": true, "contains": ["No design is open"]}},
  {"tool": "new_design", "args": {"name": "Empty"}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "count": 4}, "radius": 1},
   "expect": {"error": true, "contains": ["no solid body yet"]}},
  {"tool": "add_drawing_view", "args": {"kind": "projected", "parent": "BaseView",
    "direction": "Top"}, "expect": {"error": true, "contains": ["no drawing yet"]}}
]
```

Without the SciForge window (the command line, the MCP server's `--headless` mode) the tools
that need it answer: "This needs the SciForge window, and SciForge is running without one".
`render` works without the window.

## Files

Headless SciForge never replaces a file unless it was started with `--allow-overwrite`
(the window asks the person instead); paths must end in the format's extension; `save` on a
design that was never saved needs `path` (or use `save_as`).

An export answers what the file does not keep of this design, after the file written: `Not
kept in this file:` and one line each (the timeline steps, sketches, hidden bodies,
colours, names, bodies merged into one mesh...), the same list the person sees after File >
Export; nothing is listed when nothing is lost. Inserting or opening a file answers what did
not come in or came in changed (`Not brought in, or changed:`: an open mesh, a 3MF's unit,
DXF texts and hatches, loose faces of a STEP...). These are facts about the file formats, not
errors: decide whether they matter (a STEP for another CAD program never has the timeline).

```json sciforge-calls
[
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "length": 10, "width": 10,
    "height": 10}},
  {"tool": "export", "args": {"format": "step", "path": "{tmp}/box.step"},
   "expect": {"contains": ["box.step", "Not kept in this file:",
     "- the timeline (1 step): the file holds the finished shapes only"]}},
  {"tool": "export", "args": {"format": "step", "path": "{tmp}/box.step"},
   "expect": {"error": true, "contains": ["already exists"]}},
  {"tool": "export", "args": {"format": "stl", "path": "{tmp}/box.step"},
   "expect": {"error": true, "contains": ["path must end in .stl for format stl"]}},
  {"tool": "save", "args": {}, "expect": {"error": true}}
]
```

## Parameters and sketches

```json sciforge-calls
[
  {"tool": "set_parameter", "args": {"name": "w", "value": 10}},
  {"tool": "set_parameter", "args": {"name": "half", "value": "w / 2"}},
  {"tool": "delete_parameter", "args": {"name": "w"},
   "expect": {"error": true, "contains": ["is used by: the parameter half"]}},
  {"tool": "set_parameter", "args": {"name": "2nd", "value": 1},
   "expect": {"error": true, "contains": ["name must start with a letter"]}}
]
```

A parameter that a formula uses (another parameter's, a sketch dimension's or a step's)
cannot be deleted: change those first. A sketch constraint or dimension that conflicts with
the sketch, or that the sketch already says, is refused with the constraints it fights or
repeats, named in words and by index ([sketches.md](sciforge://docs/sketches.md)).

## Over MCP: SciForge busy, closed, or the answer lost

- "SciForge is busy: ..." : a dialog, a sketch or a question is open in SciForge; the person
  has to finish or cancel it.
- "SciForge is not running, or 'Allow AI apps to control SciForge' is off": the documentation
  tools still work (the MCP server answers them itself); the design tools need SciForge.
- "The answer from SciForge was lost ... may or may not have been applied": look at the
  design (`inspect_design`, or `diff_design` since a snapshot) before calling again.

## When the picture and the numbers disagree

Trust the numbers. `render` and `screenshot` are pictures at one size and angle; volumes,
bounding boxes and `query_geometry` facts are exact. A body that looks right can be several
pieces (`check_design` says so) or have a sliver; a body that looks wrong can be a camera
angle. [checking.md](sciforge://docs/checking.md) has the routine.
