# Session log: patterns and mirrors of bodies (branch `sf/fix-pattern-bodies`, 2026-10-16)

To be folded into MEMORY.md's Session log at the merge (this branch does not edit MEMORY.md).

## Luca's report (CI #117 quick update)

"using rectangular/circular pattern completely breaks all bodies. the original object in the
pattern can not be edited and if deleted, it breaks everything else. it cant even be moved
without breaking everything. any movements or edits to the original will also happen to the
other bodies." / "mirror has the same issues as rectangular/circular pattern".

## Root cause

A pattern of bodies (and a Mirror with Operation New Body) is one top-level step
(`pattern.BodyPatternFeature`) plus one copy feature per new body. The step linked the source
**body** (`Source`) and copied `source.Shape`, the body's *current* final shape (its Tip):

- every step of the original made after the pattern (a Move, a hole, a fillet) reached every
  copy: "any movements or edits to the original will also happen to the other bodies";
- the link to the body made the step depend on the whole body, so a step of the original that
  uses a copy (a Combine of a copy into it, Fusion's usual next step) closed a dependency
  cycle: FreeCAD printed "The graph must be a DAG", objects stayed "touched after recompute",
  and the copy took the combined shape ("breaks all bodies");
- deleting the original made the step fail (red, a Python error in the step) instead of
  leaving the copies alone;
- (found on the way) for a body in a moved, turned component the copy landed in the wrong
  place: `source.Shape` carries the body's placement but not the component's, while the
  movement was worked out with the body's global placement (golden
  `pattern_bodies_in_moved_component`: the old code put the copy at design x 0..40).

All three reproduced with real clicks on the old code (scenarios below: 161, 160, 159 checks,
failing exactly there) and headless (Combine cycle).

## The fix

Fusion copies the body **as it stands at the pattern's place in the timeline** (parity doc
B1-B10, with sources):

- `pattern.py`: the step links the source body's last solid step before it in the timeline
  (`Source`; `wanted_source` reads the timeline order across bodies, hidden follower / base
  steps sit where their lead or the step before them is) and keeps the body's name in
  `SourceBody` (a string, no dependency). The copies are that step's solid in design
  coordinates (`bodies.global_shape`: body and component placement), the references read in
  the body's coordinates. `resolve_source(s)` finds the step again; the copies read the
  step's compound instead of recomputing every copy N times.
- `timeline_ops.recompute` resolves before recomputing and `settle` after every recompute
  (a step added at the marker before the pattern, a step deleted, the pattern dragged);
  `step_order(doc)` is the timeline's merge without reading problems (cheap).
- The step rolls back with the history marker (`SciForgeRolls`, like a component pattern):
  while the marker stands before it its copies are hidden (`_follow_root_steps`), they do not
  take new work (`commands.not_made_yet`), and a body freed by a rolled-back Combine stays
  hidden while the marker hides it (`bodies.sync_consumed`).
- A step added to a body while the marker stands right before a step outside the bodies
  (the marker note names it) goes in before that step (`timeline_ops.
  rank_before_marker_step`, pure part `timeline_core.keys_to_go_before`, unit-tested): before,
  by creation order, it landed after the pattern (and after a component step), so a boss added
  "before the pattern" never reached the copies.
- `uses()` of a pattern of bodies is the body's first step (or the step that made a copy
  body), not the step it copies now: it can be dragged anywhere after the body exists.
- Deleting the original: the step keeps its copies and shows a warning (not red); Undo makes
  it compute again. Old files: `BodyPatternFeature.onDocumentRestored` links the step before
  it and marks it (`upgrade.mark(obj, "body_pattern")`); `upgrade.after_open` recomputes it
  once the file is open (GUI), with a log line.
- Dialog: editing a body pattern after the original got later steps, an edge those steps made
  or moved is refused with the reason ("That was made after this pattern..."); the drag
  arrows, dots and Pattern on Path's automatic start point are worked out from the step the
  pattern copies (`objects_center(options, base)`), not the body as it is now.
- Found by the new "a copy moved on its own" steps (also on the old code): after a design was
  opened again, every copy's hidden copy feature (`BodyCopy`, saved hidden) was shown by
  FreeCAD (C++ inside `openDocument`; a feature without a Python view provider), so a click on
  a copy picked that feature instead of the copy's body: Move/Copy got no body, and a copy
  moved later would have left its old shape drawn. The copy feature now has a view provider
  (`pattern_ui.ViewProviderBodyCopy`, kept hidden when opened, as Move/Copy's copy step with
  its `StepViewProvider`); for designs saved without it, `BodyCopyFeature.onDocumentRestored`
  marks the document (`upgrade.mark(obj, "copy_view")`) and `upgrade.after_open` runs
  `keep_copy_features_hidden` (hides them, attaches the view provider; the design does not
  count as changed for that) once the design is ready, and once more 0.5 s later.
- Pattern Type Components (components-2) is untouched (instances by design).

## FreeCAD facts and traps

- Properties set in a Python feature's `onDocumentRestored` do not leave it touched (FreeCAD
  purges after restore): a migration that needs a recompute must touch the object later
  (`upgrade.after_open`).
- A link from a feature outside a body to the *body* is a dependency on every step in it
  (Group, Tip): link the step you need.
- A `Part::FeaturePython` with no Python view provider, saved hidden, is shown again when the
  design is opened in the GUI (FreeCAD 1.1.4; headless it stays hidden). Give such helpers a
  view provider.
- `DocumentObject.isTouched()` does not exist in Python: read `"Touched" in obj.State`.
- An App document observer's `slotFinishRestoreDocument` is never called in FreeCAD 1.1.4
  (checked with a spy while opening a file); FreeCAD's own visibility changes happen
  synchronously inside `openDocument`. Use a feature's `onDocumentRestored` plus a deferred
  step (`upgrade.mark` / `after_open`). `thread_ui._AppWatch` also defines that slot (it has
  other triggers, so cosmetic threads still update).
- The "marker stands before a non-solid step" note lives in `doc.Meta`, which FreeCAD's undo
  does not restore: Undo of such a marker roll leaves the marker after that step (general;
  listed in the parity doc).
- A `PartDesign::Pad` made by a plain script (no SciForge metadata) opened from the timeline
  did not take a new distance on OK in the scenario (seen once with the first fixture; the
  fixture is now made with `extrude.make`, as SciForge's own Extrude is). Not investigated.

## Tests

- New scenarios (`gui/fixpattern_steps.py` has the shared steps), all PASS on the final code:
  `fixpattern_rect` 185 checks (161 before the copy steps were added: on the old code it
  failed 24 of them, exactly Luca's complaints), `fixpattern_circ` 160 and `fixpattern_mirror`
  159 (both failing the same way on the old code), `fixpattern_path` 162, `fixpattern_marker`
  54 (Combine of the copy into the original, marker before the pattern, a boss added there,
  rolled forward and back), `fixpattern_old_file` 110 (`fixtures/pattern_bodies_v1.FCStd`,
  made by `fixtures/make_old_pattern.py` with the code before the fix).
- Older scenarios run on this branch, all PASS: `patterns_*` (12), `bodies_*` (8),
  `modify_remove`, `components2_bodies`, `components2_marker`, `components2_move`,
  `components2_pattern`, `components_extrude`, `modify2_bodies`, `modify2_pattern_adjust`,
  `modify2_pattern_path`, `gaps_timeline_start`, `revolve_qa_more`, `timeline_browser*` (6;
  `timeline_browser_qa4` failed its known "marker is in view" check once under load and
  passed alone), `timeline_roll_view`, `timeline_rolled_cut`; `--only base` (1091 unit tests,
  golden 402 pass + 1 expected xfail, smoke, journey); `check_install.sh`.
- Golden models `pattern_bodies_move_original_after`, `mirror_body_new_body_move_after` (fail
  on the old code: bbox z 20..30), `pattern_bodies_in_moved_component` (fails on the old
  code); `measure_bodies` takes a pattern of bodies (its copies).
- Unit: `test_timeline_core.StepAtMarkerBeforeRootStepTests`.
- `patterns_qa_features` Path 17 now expects the warning (the copies stay) instead of red.

## Gaps (parity doc, Known gaps)

- Delete on one copy deletes only that copy (Fusion deletes the whole pattern; Remove takes
  one), and a later edit of the pattern does not make it again. Not changed here.
- Editing a body pattern does not roll the design back to it (Fusion does for every edit).
- Undo of a marker roll to "right before a step outside the bodies" (see above).
