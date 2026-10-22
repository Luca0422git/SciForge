# Session log: sketch curves keep their construction flags and ids (branch `wf/sketch-geometry`, 2026-10-22)

Luca: "fix the sketch tools bug. the loose end you left open". The loose end (MEMORY.md, full
suite session; `2026-10-22-integration.md`): `sketch_explain.py`, `scale.py` and `text.py`
reset a sketch's curves with `sketch.Geometry = [...]`, which in FreeCAD 1.1.4 turns
construction points into normal points with new geometry ids. Only the sketch fillet/chamfer
had been fixed (`sketch_fillet_tool.set_geometry`). Branch made from `experimental` c59634a.
No FreeCAD core file changed (nothing for `docs/sciforge/core-patches.md`). MEMORY.md is not
edited here (parallel branches): the summary below is for it.

## What Luca sees now (plain language)

- **Construction points stay construction points.** After a sketch fillet the old corner is
  kept as a dashed construction point. Scaling that sketch (MODIFY > Scale), dragging the
  frame of a text in it, or SciForge putting curves back after it tried a constraint that did
  not fit used to turn that point (and an ellipse's two focus points) into real points: the
  sketch got stray points, they lost their "name" (the geometry id FreeCAD and SciForge use to
  find a curve again), and an ellipse's foci lost their role. Now every curve keeps its
  construction look, its id and its role, whatever SciForge does to the sketch.
- **A refused Change Parameters really changes nothing.** Typing a value that breaks the
  design (say a sketch width of -60) is refused, but in a sketch that is not fully
  constrained the curves did not come back where they were: a 40 x 20 rectangle with only its
  width set came back shifted and twice as tall, and the extrusion doubled in volume. Now
  every sketch's curves are put back exactly.
- **Derived sketches keep their curve ids when they update.** A sketch derived from another
  design (Derive) was rebuilt with new ids on every update; now each curve keeps the id of the
  curve it copies, so whatever refers to it keeps finding it.

## The root cause (FreeCAD 1.1.4, read in the source and checked in real FreeCAD)

Every sketch curve carries "extensions" besides its shape: the SketchGeometryExtension (the
geometry id, the construction flag, the blocked state, the internal-alignment role of an
ellipse's or B-spline's helper curves, the geometry layer) and, in the window, the
ViewProviderSketchGeometryExtension (visual layer, B-spline representation factor).

- `sketch.Geometry` hands every curve to Python with its extensions *except points*:
  `Part::GeomPoint::getPyObject()` builds a new point from the coordinates
  (`src/Mod/Part/App/Geometry.cpp`), the other types clone themselves. Assigning the list back
  (`sketch.Geometry = geos`) gives FreeCAD points without extensions: it makes them normal
  points with new ids (an ellipse's foci: normal points with no role).
- A curve made afresh (`Part.LineSegment(...)`) has no extension either: new id, normal.
- Setting a GeometryFacade's `.Geometry` replaces the curve with one without extension too.
- `sketch.GeometryFacadeList` (read and write) hands every curve with all its extensions:
  `SketchObjectPy::get/setGeometryFacadeList` clone the whole geometry. Reading it costs the
  same as `sketch.Geometry` (0.53 against 0.45 ms for 600 curves), writing it a bit less
  (4.6 against 5.4 ms).
- Saving keeps a construction point (MEMORY.md said "a sketch point's construction flag is
  not kept in the file": that was this bug, not the file; checked: saved and reopened, a
  construction point stays construction with its id).

## The fix

- **`sciforge/sketch_geometry.py`** (new, shared): `set_geometry(sketch, {index: curve})`
  replaces some curves through `GeometryFacadeList`, and a replaced curve takes every
  extension of the curve it replaces (id, construction, blocked, internal role, layers);
  `snapshot(sketch)` / `restore(sketch, snap)` / `curves(snap)` keep and put back a sketch's
  curves; `state(sketch)` for tests. A fallback for a FreeCAD without `GeometryFacadeList`
  (the old flags + `setGeometryIds` way). They do not solve or recompute (callers do what
  they did before).
- `sketch_fillet_tool` / `sketch_chamfer_tool` use it (their own `set_geometry` is gone).
- `sketch_explain`: `redundant_culprits` and `_solve_without` (curves put back when the
  solver moved them while constraints were switched off), `add_checked` (curves put back
  after a squeezed solve) snapshot and restore with it.
- `scale.scale_sketch` (Modify > Scale of sketches: make, edit, undo by deleting the step,
  the AI `scale` tool) sets the scaled curves with `set_geometry`.
- `text.set_frame` (frame corner drags, the Text dialog's frame changes) changes only the
  four frame lines with `set_geometry`; the sketch's other curves are not touched.
- `derive._fill_sketch` gives each derived curve the geometry id of its source curve
  (`setGeometryIds`; they were renumbered on every update: the update deletes and adds all).
- `parameters.change_checked` (Change Parameters' trial) snapshots every sketch before the
  change and, when the change is refused (half-way or after the recompute), puts back every
  sketch whose curves moved, before the single recompute that follows.

## The audit (every way SciForge sets or rebuilds a sketch's curves)

Searched the whole `sciforge` package (with `ai/ops`, `ai/actions`): assignments to
`.Geometry`, `GeometryFacadeList`, Geometry slices, `delGeometry`/`deleteAllGeometry` +
`addGeometry` rebuilds, sketch copies kept for undo or trials, and every place that puts a
sketch back.

| Place | What it does | Verdict |
|---|---|---|
| `sketch_explain.py` `redundant_culprits`, `_solve_without`, `add_checked` | put curves back | fixed |
| `scale.py` `scale_sketch` | sets every curve scaled | fixed |
| `text.py` `set_frame` | sets the frame lines | fixed |
| `sketch_fillet_tool.give_back`, `sketch_chamfer_tool._build_arc` | sets cut curves | already safe, now the shared helper |
| `derive.py` `_fill_sketch` | deletes all, adds all on update | ids now kept (construction was) |
| `parameters.py` `change_checked` | puts a refused change back | curves now put back too |
| `hole.py` `_rebuild_sketch` | deletes all, adds one point (the Single Hole's own hidden helper sketch) | left: nothing refers to its point's id, it is no user geometry |
| `delete.py`, `insert.py`, `ai/actions/sketch_actions.py` `delGeometries` | delete curves | safe: FreeCAD's delete keeps the others' extensions |
| `text.py` `remove_frame`, glyph curves (`explode`) | delete / add curves | safe (adds new curves, deletes its own) |
| `direct.py` `sketch.Constraints = moved` | constraints only | safe |
| `ai/ops`, `ai/actions` | only `addGeometry` / `delGeometries` | safe |
| `edit_rollback`, `undo_fast`, `timeline_ops.snapshot` | hide/restore features, not curves | not affected |

## Tests (real FreeCAD 1.1.4)

Each regression check fails on the old code (c59634a's `sciforge` package with the new tests)
and passes now.

- **New GUI scenario `sketch_geometry_keep`** (162 checks, real input where the user path goes
  through a tool or dialog): a fully constrained rectangle plus an ellipse with its four
  helper curves; the rectangle's corner filleted with SciForge's Fillet (MODIFY > Fillet, the
  corner, 3, Enter: the old corner a construction point), then
  - E1 `add_checked` with guesses that squeeze a line, E2 `check_new` -> `redundant_culprits`
    on curves the solver moves, E3 `_solve_without` (each on a copy of the filleted sketch
    made with `GeometryFacadeList`): every curve keeps its flag and id, the rectangle's
    constraints and profiles unchanged;
  - S Finish Sketch, browser row, MODIFY > Scale, factor 2, OK: same flags, ids and internal
    roles, same constraints with the dimensions doubled, still fully constrained, profiles 4x
    the area, no stray vertex in the sketch's shape (old: 9 vertices for 6: the corner and the
    two foci); Ctrl+Z as before;
  - T the sketch opened from the timeline, SKETCH > CREATE > Text, its frame corner dragged:
    the rectangle's curves keep flags and ids, constraints and profiles unchanged;
  - R Finish Sketch, save, close, reopen: as saved, the old corner construction;
  - P MODIFY > Change Parameters, the width of an under-constrained sketch typed -60:
    refused, every curve where it was, the part unchanged (old: 16359 mm3 for 7986);
  - D a sketch derived from a saved design keeps its source's ids, and over an update.
  Old code: 18 checks fail (E1-E3, S, T, R, P, D).
- **Headless** (`SciForgeTests/headless/runner.py`): a sketch with a centre rectangle (its
  centre is a construction point) scaled by the AI `scale` tool keeps every curve's flag and
  id (old: the centre became a normal point with a new id).

## Results (final code, commit after e3c4666)

- `--only unit`: 2166 tests OK (9 skipped).
- `--only base`: all passed (golden 451 pass + 2 known xfail; headless 284 calls, 0 failed,
  with the new scale check; docs 141 items, 0 failed; agent end to end 81 checks; smoke,
  journey, restart).
- 46 related scenarios, all PASS on the final code: sketch_geometry_keep (162),
  sketch_explain (159), sketch_explain_box, sketch_explain_paths, sketch2_fillet (165),
  sketch2_text_frame, the eight sketch_tools_*, the six fixsketch_*, sketch_qa (460),
  sketch_qa_keys, sketch_qa_part, modeling2_sketch (142), modify2_scale, shell_draft_scale,
  shell_draft_qa_scale (368), sketch_text_basic/cut/edit/more/path, text_on_face,
  emboss_flat, emboss_cylinder, parameters_trial, limits_fillet, limits_notes, limits_review,
  misc_derive, polish2_derive, sketch_infer, sketch_infer_tools, sketch_infer_undo,
  sketch_modify, sketch_polygon. (No limits_* scenario has "sketch" in its name; the three
  that touch sketch limits were run.)

## For MEMORY.md (to merge)

- Status: the loose end "sketch_explain.py, scale.py, text.py reset sketch geometry in the
  unsafe way" is done (`sciforge/sketch_geometry.py`; also derive ids and the refused
  Change Parameters putting curves back).
- Known issue to drop: "A sketch point's construction flag is not kept in the file" (wrong:
  it was this bug).

## Findings

- FreeCAD 1.1.4: `sketch.Geometry` gives points without their sketch data (construction flag,
  id, internal role); assigning it back makes them normal points with new ids. Use
  `GeometryFacadeList` (sciforge/sketch_geometry.py) to set or put back curves.
- A construction point's flag IS kept in the file (the old MEMORY note was this bug).
- A refused parameter change put the value back, but the solver started from where the
  change had moved an under-constrained sketch: its curves (and the extrusion) stayed changed.
- `Sketcher.Constraint` has no `InternalAlignmentType` attribute in Python; a curve's role is
  the facade's `InternalType` ("EllipseMajorDiameter", "EllipseFocus1", ...).
- `sketch.addConstraint` from Python solves a sketch that is not open (a test that wants the
  curves off their constraints must add a constraint that makes the solve fail).

## Review follow-up (same branch): three more ways a sketch did not stay what it was

Adversarial reviewers found three problems (SKETCH-1-F1..F3). Each was reproduced in real
FreeCAD 1.1.4 first (all three were already in c59634a, so not regressions of this branch).

### What Luca sees now (plain language)

- **Purple (projected) edges keep following the part.** When a step is deleted (say a
  fillet) or replaced by SciForge (a pattern edited into SciForge's own pattern, a shell that
  becomes a draft, a revolve switched from Join to Cut, a sweep or loft rebuilt), a sketch
  built on it used to move to the step before, but its projected edges stayed glued to the
  deleted step: FreeCAD kept them as frozen copies ("missing reference" in the log). Lines
  drawn against them held on to that dead copy, so making the box wider no longer moved
  them. Now the projected edges are projected again from the step that remains, and every
  constraint on them moves along: widen the box and the purple edge and the line attached to
  it follow, also after saving and reopening.
- **Deleting a sketch Scale puts the sketch back exactly.** A sketch whose width follows a
  parameter keeps that width when scaled, so the solver moves the rest of the sketch. Taking
  the Scale away (or changing its factor) used to shift the whole sketch (and the extrusion)
  by several millimetres. The Scale step now remembers the curves from before it and puts
  them back.
- **Derived ellipses and splines keep their helper curves tied to them.** In a sketch
  derived from another design, an ellipse's focus points and a spline's knot points became
  loose construction points, and the helper lines were not tied to their curve. They now
  keep their role and are tied exactly as in the source.

### F1: projected edges of a replaced or deleted step (sciforge/sketch_external.py, new)

Root cause: FreeCAD 1.1.4 makes `ExternalGeometry` read-only, and the five helpers that move
later steps to a new step (delete._relink_to_base, pattern.relink_dependents,
shelling._repoint (also used by drafting), revolve._relink_users, curves.relink_users (used
by sweep and loft)) set every link property with `setattr`, swallowing the error. Only
direct._relink_external (Delete Face / Move Face) re-projected.

Fix: direct's re-projection moved to the shared `sketch_external.relink(sketch, old, new,
rename, drop_lost=False)`; all six places use it for a sketch's ExternalGeometry, each with
its own way of finding the element again on the new step (the one it already used for the
attachment, but returning None when nothing is found). Each link of the old step is
projected again from the new one (addExternal, same Defining / intersection), the
constraints on the old curves move to the new ones, the old curves are deleted, Auto
project's record of its curve ids follows. An element not found on the new step: left as it
was (FreeCAD's frozen copy, as before) except in direct (taken out with its constraints, as
before).

Two more FreeCAD facts found on the way (both handled in sketch_external):

- A projected curve that is a **point** (a projected vertex, or an edge seen end-on) has no
  readable reference from Python: `sketch.ExternalGeo` hands points without their
  extensions (the same GeomPoint::getPyObject root cause as the rest of this branch), so
  `ExternalGeometryFacade(geo).Ref` is ''. Such a link is matched to its point by where the
  element projects onto the sketch plane.
- `ExternalTypes` has one entry per ExternalGeometry link (0 projection, 1 intersection, 2
  both), not one per curve: direct indexed it per curve (so it always read "projection").
  Now read per link. A link of type 2 (both) is re-made as a projection only (rare; not
  reproduced).

### F2: deleting or editing a sketch Scale (sciforge/scale.py)

The Scale step keeps each sketch's curves before and after the scale (hidden properties
`Before`, `After` (Part::PropertyGeometryList, saved with the file) and `Counts`). Delete
(the watcher) and an edit (factor change, point change) first scale the dimensions back as
before, then, when the sketch's curves are still exactly those the scale made (nothing
changed the sketch since), put the kept curves back (sketch_geometry.set_geometry: flags and
ids kept) and solve. When the sketch was changed after the scale, or the step comes from an
older SciForge (no kept curves), it is scaled back as before (and a log line says so).

### F3: Derive and internal-alignment helpers (sciforge/derive.py)

read_doc also keeps each source sketch's `GeometryFacadeList` (every curve with its id,
construction flag and internal role) and its InternalAlignment constraints. _fill_sketch
sets the facades into the empty derived sketch in one go (the blocked flag cleared: the
Block constraints added after give it), adds Block to every normal curve (as before) and
the source's InternalAlignment constraints. Old way kept as a fallback.

### Tests

- New GUI scenario **sketch_geometry_follow** (53 checks): A the Fillet clicked in the
  timeline, MODIFY > Delete (real input), the box widened to 60, saved and reopened; B a
  FreeCAD LinearPattern edited into SciForge's pattern with Auto project on a copy's face,
  the boss widened; C shelling._repoint, curves.relink_users, revolve._relink_users with a
  projected edge and a projected point; S sketch Scale with a parameter-bound width: x2,
  edit to x3, delete; again, save, reopen, delete; D derive of an ellipse and a B-spline with
  their helpers, and an update. On the code before this follow-up (87370a0) 17 checks fail
  (A, B, C, S and D each); all 53 pass now.

### Results (final code)

(filled in below when the runs finish)

### Not done / for later

- follow.repair and timeline_ops also set link properties of later steps generically; they
  were not part of the review and were not checked for ExternalGeometry (FreeCAD's own
  topological naming usually keeps those references).
