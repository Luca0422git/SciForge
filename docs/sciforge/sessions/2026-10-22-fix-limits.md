# 2026-10-22: fixes to "values stop at the limit" (branch `fix/limits`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md). Follows
the review of item 8 (`2026-10-21-limits.md`): seven findings, all reproduced, all fixed.

## What changed, in plain words

- **L1 Extrude: a taper you did not touch is never changed.** Rectangle, taper -50 (fits),
  then the distance made longer so -50 no longer fits: before, the dialog quietly rewrote
  the taper step by step (to -26.5) and OK made that. Now the taper stays -50, the dialog
  says why it does not fit and the steepest taper that would ("Furthest that fits here:
  -26.5°"), and OK waits until you change something. The limit search used to leave its
  last trial taper in the real extrude; now the dialog's own values are put back after
  every search. While the distance arrow is being dragged the limit is not searched on
  every step (that cost 14 searches in one drag); it is worked out once you let go.
- **L2 Busy parts: a rough limit is no longer a wall.** On a slow part the search may stop
  early (time budget) with a value that is only "safe", not the real limit. Before, every
  later value above it was refused without being tried ("2.5 mm does not fit" when it did).
  Now only values past the nearest value that was really built and refused are held without
  a build; values in between are tried (and, if refused, the gap is searched). The search
  also tries values near the last good one first (geometric middle when far apart, 10 then
  4.5 between 2 and 50, instead of 26), so its first builds are more useful: on the
  reviewer's 61-edge plate it now finds the exact 3.00 mm.
- **L3 Shell no longer crashes FreeCAD on a busy part.** Shell walls of 8 to 30 mm on a plate
  with holes and bosses crashed OpenCASCADE's validity check (segfault, document lost; the
  base commit too, but item 8 made the search try such walls). Those results have an open
  shell (a solid with one is never valid), so the shell check now refuses an open shell
  before asking OpenCASCADE, and checks the bounding box and volume first too. The fillet /
  chamfer trial got the same open-shell check. A scan of every wall from 2 to 50 mm in 0.5
  steps on that plate: no crash.
- **L4 Distance and Angle chamfer on edges with different corners.** The check used one
  bevel with the largest second distance on every edge, so a 90 and a 135 degree edge
  together were refused at sizes FreeCAD builds. Now the edges are checked in groups with
  the same corner angle, each with its own second distance (what FreeCAD's own builder does).
  Not checked any more: how two groups meet at a shared corner (FreeCAD's own builder then
  decides, as before item 8).
- **L5 The blue note goes when an option changes.** Draft held at 71.5 ("80° does not fit"),
  then Flip: the note stayed although 80 then fits. A note now belongs to the inputs it was
  made for (picks, options, the other values); when they change it goes. All dialogs that
  hold values get this (Shell, Draft, Press Pull, Thicken, Extrude, primitives, Gear, Coil,
  Pipe, Fillet / Chamfer).
- **L6 Words.** A count has no unit: "20 does not fit: limited to 9.99" for a coil's turns
  (it said "mm"). A lower limit on a positive value says "Smallest that fits here: ..."
  (a pipe's section size); "Furthest" stays for a push into the part or a negative angle.
- **L7 Nothing in the Report view.** The Fillet dialog printed "[SciForge] Fillet 50 does not
  fit here, held at 9.99" on every hold; gone, as the notes always said.

## Where

- `sciforge/value_limits.py`: `_middle()` (geometric middle), `search(seen=)` (the nearest
  refused value), `LimitCache` entries `(limit, bad, wall)`, `Limiter.find` keeps the wall
  of an inexact search, `Limiter.note` is a property tied to `note_key` / `key_now`,
  unit "" kept, `note_reached` "Smallest".
- `sciforge/extrude_ui.py`: `limit_search` puts the extrude back, `_arrow_held`, the OK
  refusal carries the limit.
- `sciforge/shelling.py`: `_closed()`, cheap checks before `isValid()` in `_check` / `_offset`.
- `sciforge/blend.py`: `check_build` per corner-angle group; open-shell check in `trial`.
- `sciforge/fillet_ui.py`: `_limit_key_now`, no log line on a hold.
- `sciforge/primitives_ui.py`: `limit_unit` keeps "".

## Tests

- Unit (`test_value_limits.py`, 34 tests): a search cut short is not a wall, the search stays
  near the good value, an exact limit is a wall, the note goes when the inputs change, the
  words. The new ones fail on the integration head and pass here.
- New GUI scenarios: `limits_extrude_other` (L1: drag and type the distance under a taper,
  one search, OK waits, then -30 made; fails on the integration head with the taper rewritten
  to -26.5), `limits_review` (L5 Draft Flip, L6 Coil turns, L3 Shell on the busy plate, L4
  chamfer check; crashes FreeCAD on the integration head). `limits_fillet` now also checks
  that nothing goes to the Report view (L7; fails on the integration head).
- `extrude_presspull_qa` (path 3) still expected the old behaviour for a taper typed too
  steep (error, OK refused); it failed on the integration head too. Updated to Luca's
  decision: -60 on the 10 x 10 x 5 column is held at the steepest taper that fits and said.

## Results (real FreeCAD 1.1.4 under xvfb, 2026-10-22)

- `run_tests.sh --only base`: unit (2095 tests), golden (451 pass, 2 known xfail), headless
  AI tools, docs examples, agent end to end, smoke, journey, restart: all passed.
- Scenarios, all PASS: `limits_extrude`, `limits_extrude_other`, `limits_fillet`,
  `limits_notes`, `limits_presspull`, `limits_primitives`, `limits_review`, `limits_revolve`,
  `limits_shell_draft`, `limits_thicken`, `fillet`, `fillet_qa`, `fillet_qa_chamfer`,
  `fillet_qa_more`, `fillet_qa_part`, `fillet2_chamfer`, `fillet2_chord`, `fillet2_sets`,
  `fillet2_variable`, `fillet2_chain`, `fillet_chain`, `fillet_chamfer`, `chamfer_arrow`,
  `draft_curved`, `gear_refuse`, `sketch2_fillet`, `surface_thicken`, `shell_draft`,
  `shell_draft_draft`, `shell_draft_hollow`, `shell_draft_qa`, `shell_draft_qa_draft`,
  `shell_draft_qa_mix`, `shell_draft_qa_shell`, `shell_draft_qa_scale`, `shell_draft_scale`,
  `modify2_draft`, `modify2_shell`, `modify2_presspull_type`, `primitives_qa_coil`,
  `primitives_qa_more`, `primitives_qa_part`, `primitives_qa_pipe`, `primitives_shapes`,
  `extrude_presspull_qa` (after the update), `extrude_presspull_qa2` to `qa7`,
  `extrude_options`, `gaps_extrude_taper_to`, `extrude_feel`, `extrude_review_fixes`,
  `sketch_tools_circles`, `sketch_qa`, `sketch_explain`, `undo_fast`, `mesh_edit_reopen`.
