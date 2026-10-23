# Session log: fixes to "sketch constraints that explain themselves" (branch `fix/sketch`, 2026-10-22)

An adversarial review of item 1 (`wf/sketch-explain`, notes in
`2026-10-21-sketch-explain.md`) found ten problems (SE-1 to SE-10). Each was reproduced first
on this branch (made from `integration`), then fixed at its root, with a regression test that
fails on the old code and passes now. No FreeCAD core file changed (nothing for
`docs/sciforge/core-patches.md`). MEMORY.md is not edited here (parallel branches).

## What Luca sees now (plain language)

- **Every way of adding a constraint is checked**, not only "tool first, then a line". Before,
  these turned the sketch red with no message: selecting a line first and then clicking
  Horizontal/Vertical; Horizontal/Vertical on two points; Tangent on a line and an arc whose
  ends already touch. Now they are refused and the message names what they fight, like the
  rest (SE-1).
- **A constraint that FreeCAD blames on older constraints is refused too.** FreeCAD sometimes
  flags old constraints as the redundant ones, or simply cannot solve the sketch and lists
  nothing. SciForge now checks the sketch without the new constraint: if it was fine before,
  the new one is refused ("Symmetry: not added, the Horizontal on Line 1 and the Vertical on
  Line 2 already make it so"; "Coincident: not added, it conflicts with the Symmetry about the
  origin") (SE-2).
- **The padlock and "Fully constrained" are only shown on a sketch that is really fine.** A
  sketch with a redundant constraint, or whose last recompute failed, gets no padlock; the
  Sketch Palette says "Redundant constraints" for one with a redundant constraint (SE-3).
- **The dimension box**: a formula with an unknown name (`=foo*2`) is always refused, also
  right after another refused value (before, the second one slipped through and broke the
  sketch). A value or a formula the sketch cannot take now says "That value does not fit the
  other dimensions and constraints of the sketch" instead of FreeCAD's "Invalid constraint
  index: 12" or "That formula cannot be computed" (SE-4, SE-8).
- **Big sketches stay responsive.** Explaining a redundant constraint on a sketch of 180 lines
  took 2.5 s and blamed an unrelated dimension; now it takes about 1 s, looks at the nearest
  constraints first, and when it had to stop early it says so ("it is so already (the
  Horizontal on Line 7, among others)") instead of guessing (SE-5). Drawing in a big sketch is
  as fast as before the explain feature (SE-6).
- **Change Parameters**: a negative sketch size is refused like 0 and the message shows the
  value typed ("would be -3 mm"); a value the sketch cannot take says so in words (and the
  design is recomputed); a parameter formula with a typo (`width2`) is refused ("the formula
  width2 of width cannot be computed") instead of silently freezing the parameter (SE-7,
  SE-8, SE-9).
- **A refused constraint leaves no Redo behind** (Ctrl+Y no longer re-adds it) (SE-10).

## What changed (for the next session)

- `sketch_explain_core.py`: `constraint_step_title(step, types)` also knows "Add
  horizontal/vertical constraint" (the title is the type added), the "... alignment" steps of
  two points, "Add tangent constraint point" and FreeCAD's two "Swap ..." tangency steps
  (`is_swap_step`). `is_fully_constrained(..., broken=)`: no padlock with redundant
  constraints or a failed recompute. `freedom_note(..., redundant)`. `keep_strongest` (the new
  inferred-constraint fallback). `refused_constraint(..., partial)` /
  `driven_dimension(..., partial)` for a cut-short culprit search.
- `sketch_explain.py`: `check_new` reads `solve()`'s code; when it is not 0 and the new
  constraints are not the ones flagged, `_solve_without` solves once with them switched off and
  they are refused when the sketch was fine (or less broken) without them; culprits = the
  newly redundant / conflicting ones, or the partially redundant ones for a solve that found
  no solution. `redundant_culprits`: candidates nearest first (`_nearness`: rings of curves,
  directions and relations before dimensions, joins last), one time budget for everything
  (`PROBE_SECONDS` = 1.0, the solves before and after included), no extra solve when
  `setActive` solves by itself (sketch open for editing, Sketcher "Auto-update" off:
  `_solves_itself`), returns `Culprits` with `partial`; the "constraints on the same curves"
  guess only when every candidate was tried. `fully_constrained` passes `broken` (State
  Invalid/Error, not asked of the sketch being edited). `add_checked`: fast path is one solve
  (as before the feature); otherwise the weakest guesses are taken out until the sketch is
  clean and the earlier ones tried again (`keep_strongest`), with `delConstraint(i, True)` (no
  FreeCAD solve) and the curves put back only after a collapse; the one-by-one fallback only
  when the sketch was not clean before. Dead code after its `return` removed.
- `sketch_mode.py`: `settled` schedules `_check_added` on every commit/redo (the swap does not
  grow the count); `_check_added` takes the swap's new constraint (the last one) and passes the
  added types for the title; after a refused commit `_drop_redo` empties Redo (an aborted
  throw-away step: FreeCAD clears Redo when a step starts recording; the sketch's Label2 is
  touched and put back by the abort). `DimensionEditor.apply`: a formula is checked with
  `evalExpression` (not the sketch's State, which can be stale); after a failed try whose
  recompute marked the sketch, it is recomputed; `PLAIN` maps "Invalid constraint index"
  (setDatum's words for a solve with no solution) to the "does not fit" text.
- `sketch_infer.py`: the extra `solve()` after `add_checked` is gone.
- `sketch_constrain_tools.py`: keeps culprits `check_new` already found; passes `partial`.
- `sketch_palette.py`: "Redundant constraints" note (red).
- `parameters.py`: the trial no longer skips the Parameters VarSet (a formula it cannot
  compute is a broken step); `signs_of` + `broken_steps(doc, signs, typed)`: a
  horizontal/vertical sketch dimension whose sign flipped is broken, a dimension's value is
  read from its formula (FreeCAD stores 0 for a negative length), and a number typed for a
  length parameter that FreeCAD held at 0 is used in the message (`_held_back`);
  `_solver_refusal`: a setDatum failure becomes a refusal in words, with culprits when FreeCAD
  lists them, and the design is recomputed.

## Findings

- In the Sketcher's edit mode FreeCAD solves the sketch inside `addConstraint`,
  `delConstraint` and `setActive` themselves (the sketch's `noRecomputes`, set from the
  Sketcher "Auto-update" setting, off by default; not readable from Python). `delConstraint`
  takes a second argument `noSolve`. Setting `sketch.Geometry` back costs about 3 solves on a
  big sketch (0.58 s for 181 lines), reading it is free.
- `setDatum` returns `solve()`'s code: -1 (no solution) reads "Invalid constraint index",
  -2 "Datum ... is invalid", -4 "Negative datum values are not valid".
- A failed solve (-1) updates neither the geometry nor `FullyConstrained`; a redundant one (-2)
  solves but does not update them either. Neither is readable afterwards without solving.
- App::PropertyLength (the "mm" user parameters) holds negatives at 0 without a word.
- With a stale constraint count (constraints added by script outside an undo step) the check
  sees the script's constraints as new too and names fewer culprits; real use always adds
  through undo steps.

## Decisions

- A cut-short culprit search names what it found and says "among others"; it does not fall back
  to guessing (the guess named an unrelated dimension).
- The check that a new constraint made the sketch worse costs two extra solves, but only when
  FreeCAD's verdict is not already about the new constraint (rare).
- The probe budget is 1.0 s in all (a sketch whose single solve takes 0.2 s: about 1.2 s with
  the check's own solve).

## Limitations

- The padlock rule cannot see a failed solve (-1) of the sketch being edited (FreeCAD does
  not expose it without a solve); every SciForge path that could cause one now refuses it.

## Tests

- Unit: `test_sketch_explain_core.py` (28 tests, 6 new: step titles, keep_strongest, padlock
  with redundancy / broken recompute, palette note, partial wording).
- New GUI scenarios: `sketch_explain_paths` (SE-1 preselect, point H/V, tangent swap; SE-2
  symmetry and no-solution coincident; SE-3 palette and padlock; SE-10 Redo; SE-5 big sketch:
  time, culprits, no dimension) and `sketch_explain_box` (SE-4 and SE-8 in the dimension box
  and Change Parameters' trial). `parameters_trial` gained B2 (typo formula, SE-9), B3 (width
  -5, SE-7) and C2 (height -3, SE-7).
- On the old code (integration 3e515b5) the new unit tests fail (7 errors, 1 failure) and the
  three scenarios fail at exactly these checks.
- Headless measurements (181-line strip, one solve 0.19 s): redundant check 2.25 s -> 0.97 s,
  inferred fast path 0.39 s -> 0.19 s (old code before the feature: 0.20 s), fallback 2.35 s
  -> 0.68 s (before the feature: 0.63 s).

## Test results

All with real FreeCAD 1.1.4 (`tools/sciforge/run_tests.sh`), on the final code:

- `--only base`: unit 2097 tests OK (9 skipped); golden 451 pass + the 2 known XFAIL; journey,
  smoke and restarts pass; documentation examples 137 items / 874 calls / 0 failed; agent end
  to end 70 / 70. The headless AI run had one failure on the first pass: a Concentric of two
  circles whose centres are both pinned to (30, 0) was expected to say "conflicts with"; it is
  a repeat (FreeCAD flags the old dimensions), and the answer now says "Concentric: not added,
  the 30 mm dimension 'g3.x' and the 0 mm dimension 'g3.y' already make it so". The
  expectation in `SciForgeTests/headless/runner.py` was changed to that; rerun: 202 calls /
  117 tools / 0 failed.
- The reviewer's own scenarios (rv_sketch_a, b, c2, d, e, run from the scratch folder, not
  committed): every check of the findings passes. (rv_sketch_a's "D: palette follows undo"
  check expects "not fully constrained" for a sketch whose 11 constraints leave 0 degrees of
  freedom: its expectation, not a fault.)
- 97 related GUI scenarios (every `sketch*`, `fixsketch_*`, `sketch2_*`, `parameters*`,
  timeline/browser and parameter scenarios, everything that uses `sketch_explain`, Change
  Parameters or `inspect_design`, and the three new/extended ones): 95 PASS.
  `modeling2_sketch` (a too-long sketch chamfer is expected to be refused, item 8 now limits
  it: "Chamfer: 30 mm does not fit: limited to 17.11 mm") and `revolve_qa` ("P4 400 is
  explained": item 8 limits the revolve angle) fail identically on `integration` 3e515b5
  without these changes: expectations left behind by `wf/limits`, not this work.
