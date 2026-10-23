# Session log: sketch constraints that explain themselves (branch `wf/sketch-explain`, 2026-10-21)

Idea 1 of `docs/sciforge/dev/cadcraft-lessons.md`, approved by Luca. Started from
`experimental` 0b1da82. No FreeCAD core file changed (no full build needed, nothing for
`docs/sciforge/core-patches.md`). MEMORY.md is not edited here (parallel branches): this file
is the session's log.

## What Luca sees (plain language)

- **When a constraint does not fit, SciForge says which ones it fights.** Before, a
  constraint that fought the sketch either turned the sketch red (FreeCAD's own tools:
  Horizontal/Vertical, Parallel, Perpendicular, Tangent, Equal, Coincident, Symmetry, Fix) or
  said "it does not fit the sketch's other constraints". Now it is not added, like in Fusion,
  and the message names the culprits in Fusion's words, for example *"Equal: not added, it
  conflicts with the 40 mm dimension and the 20 mm dimension (highlighted in the sketch)"*.
  The culprits get a red ring in the sketch (and are selected when FreeCAD allows it) for
  2.5 seconds or until the next click or key.
- **A constraint that is already true** (Parallel on two lines that are both Horizontal) is
  not added either: *"Parallel: not added, the Horizontal on Line 1 and the Horizontal on
  Line 3 already make it so"*.
- **A dimension on a size already set** still becomes a driven dimension (as before), and
  the message now says what sets it.
- **A typed dimension value that does not fit** (the box stays open) says what it conflicts
  with. A formula typed in the box (`=width - 50 mm`) can use parameter names like the rest
  of SciForge, a formula FreeCAD cannot compute is refused instead of being kept broken, and
  a formula that gives 0 or less is refused like a typed 0.
- **Padlock.** A fully constrained sketch (nothing in it can move) has a small padlock on its
  icon in the browser and in the timeline, updated live. The Sketch Palette shows "2 left to
  define" (how many ways the curves can still move) or "Fully constrained".
- **Change Parameters checks first.** A parameter value that would break the design (a
  sketch dimension of 0, a sketch whose constraints would conflict, an extrude that would
  fail or come out empty) is refused and nothing changes; the dialog says what would break:
  *"Not changed: with width = 0, Sketch 1 would break: its dimension d10 of Line 1 would be
  0 mm, and a size must be more than 0. Extrude 1 would break too."*
- **Guessed constraints in a better order.** When the constraints SciForge guesses while you
  draw (snaps, level/upright, parallel...) do not all fit, the strong ones are kept and only
  the weak ones dropped (before, all the ones involved were dropped together).

## What was built (for the next session)

- `sciforge/sketch_explain_core.py` (pure, unit tested): curve names per kind ("Line 2",
  axes, projected curves), one constraint in words (`describe`: Fusion names: Concentric,
  Collinear, Midpoint, Symmetry, Fix; dimensions by value), culprit ordering
  (`meaning_rank`: dimensions/Fix, then Horizontal/Vertical, relations, Coincident last; left
  over Coincidents counted: "and 4 Coincidents"), the messages, FreeCAD's undo-step names ->
  tool titles (`constraint_step_title`), inference priority (`inference_rank`,
  `add_in_order`), the padlock rule (`is_fully_constrained`), the palette note, the
  parameter-refusal message and `bad_size`.
- `sciforge/sketch_explain.py` (FreeCAD): `check_new` (solve, then conflict: FreeCAD's
  `ConflictingConstraints` group minus the new ones, limited to the constraints connected
  through the sketch's own curves; redundant: `redundant_culprits` switches each connected
  constraint off in turn with `setActive` and keeps the ones whose absence ends the
  redundancy, geometry checked and put back), `highlight` (selection + a see-through ring
  layer on the 3D view, `SciForgeConstraintRings`; an app event filter installed one event
  later clears it on the next press/wheel/key), `fully_constrained` / `freedom` (no solve),
  `paint_padlock`, `add_checked` (inference priority).
- Wired into: `sketch_constrain_tools.PickConstraint._apply` (Collinear, Concentric, Midpoint,
  Curvature), `sketch_mode.SketchSession._check_added` (FreeCAD's constraint tools: after a
  commit or redo whose undo step is "Add ... constraint", a bad constraint is undone and
  explained), `_make_driven_if_redundant`, `DimensionEditor.apply`, `timeline_ops.problem`
  (sketch warnings/errors name the constraints), `browser_core/_ui` and `timeline_core/_ops/_ui`
  (padlock; `locked` in the signatures so they redraw), `sketch_palette` (note),
  `sketch_infer` and `sketch_draw._add_checked` (priority), `parameters.change_checked` +
  `parameters_ui` (trial).

## Findings

- FreeCAD 1.1.4's `setDatum` says *"Negative datum values are not valid"* for **any**
  over-constrained result (its code -4), also for a positive value. SciForge showed that as
  "The value must be more than 0." for a conflicting value: now it says what conflicts.
- After a failed `setDatum` FreeCAD puts the old value back but **keeps the diagnosis** of the
  failed solve (`ConflictingConstraints`): the culprits of a value conflict are read there.
- `FullyConstrained` is saved with the file but **not updated** by a solve that only finds
  redundancy, and it **stays True** when the sketch goes into conflict; `DoF` is 0 after
  opening a file until the first solve. The padlock rule combines them (unit tested).
- FreeCAD names a redundant group only by the constraint it would drop; a conflict by its whole
  group (often with corner Coincidents). A redundant dimension's culprits found by switching
  constraints off include the corners too: they are counted, not listed.
- While one of FreeCAD's own constraint tools runs, its selection gate refuses constraints:
  that is why the culprits also get rings (selection alone showed nothing there).
- Inferred guesses that only fit by **collapsing a line** (upright and parallel to a level
  line) are no conflict to FreeCAD: its solver squeezes the line to a point (solve() 0, then
  -1). `add_checked` treats a curve that collapsed as "does not fit" and puts the curves back.
- The dimension box passed `=width*2` to FreeCAD unchanged (FreeCAD does not know `width`,
  only `Parameters.width`) and a formula that failed was committed silently: fixed.
- **Least movement (item 5), no fix needed:** FreeCAD's solver splits a sketch into groups that
  share no curve and only solves the group of the changed dimension, then moves as little as
  it can. Checked (scenario `sketch_explain` step H): curves not touching the dimensioned line
  do not move at all, and the far end of a free line hanging on it stays. The one thing that
  differs from CADCraft's rule is a dimensioned line that is free at both ends: it grows from
  both ends (FreeCAD's least total movement); Fusion's choice there is unconfirmed, so it is
  left as it is.

## Decisions

- Refused constraints from FreeCAD's own tools are taken back with Undo (no API to drop them
  before FreeCAD commits). A Redo of that step is refused again.
- Typed lengths among the inferred constraints rank above every guess (the user typed them);
  an inferred 45 degree Angle ranks with Horizontal/Vertical.
- A horizontal/vertical distance of exactly 0 counts as "no size" (as the dimension box already
  refused 0 for every dimension).
- Change Parameters keeps its one transaction (Cancel undoes everything): a refused change is
  put back by hand (expressions and value) and the design recomputed. The trial recompute's
  own FreeCAD messages ("Invalid solution from DogLeg solver"...) still reach the Report view.
- The typed-dimension check covers the sketch only (0 or less, conflicts, formulas): the steps
  after the sketch are recomputed when the sketch is finished, as before.

## Limitations

- FreeCAD's own refusals before adding ("Impossible constraint", "Wrong selection") still go
  only to FreeCAD's notification list (SciForge keeps balloons off): not changed here.
- The rings are placed at a dimension's value or by the middle of the constrained curves, not
  exactly on FreeCAD's glyphs; they do not follow a zoom/pan (the next wheel turn or click
  ends the highlight anyway).
- Finding a redundancy's culprits switches up to 150 connected constraints off one at a time.
  (Corrected on 2026-10-22, docs/sciforge/sessions/2026-10-22-fix-sketch.md: the "at most
  1.5 s" written here was not true, the solves before and after were not counted and the
  candidates were tried in index order. Now the nearest are tried first, the whole search
  including its solves stops after 1 s, and a cut-short list is said to be only part of the
  reason, without guessing.)
- Messages are English only, like the rest of SciForge.

## Tests

- Unit: `SciForgeTests/unit/test_sketch_explain_core.py` (22 tests).
- GUI scenarios (real input): `sketch_explain` (A padlock in browser, timeline and palette
  after drawing and dimensioning a rectangle; B Equal conflict from FreeCAD's tool: refused,
  named, rings; C Parallel repeat; D Collinear conflict in SciForge's pick tool, rings and
  selection; E driven dimension named; F value conflict in the dimension box; G padlock after
  Finish Sketch; H least movement; I inference priority, also the collapsing case) and
  `parameters_trial` (user and model parameters refused and accepted in the dialog, formula
  in the dimension box).
- Results: see "Test results" below.

## Test results

All with real FreeCAD 1.1.4 (`tools/sciforge/run_tests.sh`), on the final code:

- `--only base` (1821 unit tests, 448 golden models, smoke, journey): all passed.
- New scenarios: `sketch_explain` PASS (159 checks), `parameters_trial` PASS (36 checks).
- Existing related scenarios, 75 in all: every `fixsketch_*`, `sketch2_*` and `sketch_*`
  scenario (there are no `sketch3_*` files), the timeline/browser ones (`timeline_browser*`,
  `timeline_roll_view`, `timeline_rolled_cut`, `polish2_timeline_groups`, `bodies_timeline`,
  `gaps_timeline_start`), the parameter ones (`misc_derive`, `shell_draft_qa_scale`,
  `patterns_params`, `gaps_formula_units`) and `modeling2_sketch`, `polish2_sketch_check`,
  `selection_sketch`, `hole_sketch`, `extrude_edit_sketch_shown`, `extrude_from_edited_sketch`:
  all PASS. `sketch_draw` failed once ("sketch palette shown" right after Create Sketch) while
  three test runs shared the 4 CPUs; run again alone it passed (134 checks): a timing check
  under load, not this change. No existing test expectation was changed.
