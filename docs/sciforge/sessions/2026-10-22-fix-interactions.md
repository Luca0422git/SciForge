# 2026-10-22: fixes for how the nine merged branches work together (branch `fix/interactions`)

To be copied into MEMORY.md by whoever merges this branch (it does not edit MEMORY.md).
Based on `integration` (3e515b5). It fixes what a reviewer found when it looked at how the
merged branches work together (findings X1-X6). No FreeCAD core file changed (nothing for
`core-patches.md`).

## In plain words (for Luca)

1. **Fast Undo now keeps working after you undo a new step (X1).** When you added a step
   (a fillet, say) and pressed Ctrl+Z, FreeCAD left the Body marked "needs a rebuild".
   SciForge's fast-undo bookkeeping saw that mark, so the *next* change you made and undid
   was rebuilt the slow way (15-23 s on your big designs). Two causes, both fixed: after
   Ctrl+Z the timeline now looks at every object, the Body included, and clears the mark
   when FreeCAD already put the right shape back. And a new step that FreeCAD shows as
   "needs a rebuild" at the very moment the change starts no longer counts against it (the
   undo deletes that step anyway). The AI's Undo and your Ctrl+Z now decide the same way.
2. **Sketches drawn by the AI at the origin no longer switch off Change Parameters' check
   (X2).** The AI places a circle at the origin with "0 mm from the origin" dimensions.
   SciForge counted those as broken, so the sketch looked broken from the start and every
   new breakage got through (a diameter driven to 0 wrecked the sketch). Now a horizontal or
   vertical distance *between two points* may be 0 (it only says they line up); a line's
   own width of 0 is still refused. And Change Parameters now compares problem by problem,
   so one old problem in a sketch no longer hides a new one. The AI can also set such a
   distance back to 0.
3. **The AI's "largest value that fits" search no longer freezes SciForge (X3).** Each try
   rebuilds the design. The search now has one time limit (3 s) for everything it builds;
   if one try takes longer than half of that, it does not search and says so ("SciForge did
   not search for the largest radius that fits: every try rebuilds this design (about 4 s)
   ... Try a smaller radius"). On the reviewer's 40-hole plate: 23 s became 9 s (the refused
   change itself plus one try) and 12.7 s became 4 s. The AI docs no longer promise "a few
   seconds at most".
4. **An AI's STEP export in the window keeps the components (X4)**, like File > Export and
   `sciforge-cli` (it used to write a flat list of bodies there). A STEP written as a list
   of bodies (bodies picked, Export Everything) now says in its "Not kept in this file" list
   that the components are lost.
5. **An AI call that is refused tells you when it emptied your Redo list (X5).** FreeCAD
   empties the Redo list whenever a change is *tried*, even one that is taken back; this
   cannot be avoided without changing FreeCAD itself. The answer now adds "(The design is
   as it was, but trying this emptied the Redo list: 'AI: Fillet 2 mm' can no longer be
   redone.)".
6. **AI sketch refusals no longer say "highlighted in the sketch" when you cannot see the
   sketch (X6)** (hidden after an extrude, or in a hidden body): nothing is selected or
   ringed then. On a sketch you can see, the red rings still show.

## Details

- X1: `undo_fast.Ledger.created()` drops an object created inside the transaction being
  recorded from the "not up to date at the start" list (`slotOpenTransaction` now passes the
  names; FreeCAD 1.1 opens the transaction when the new object is already in the document,
  touched). `timeline_ui.after_undo` and the AI's `_settle_after_undo` both use
  `undo_fast.touched(doc)` (every object). Tests: `test_undo_fast.py` (3 new), scenario
  `undo_fast` paths G (dialog-style new step, Ctrl+Z, edit, Ctrl+Z) and H (AI fillet,
  Ctrl+Z; AI fillet, AI undo): nothing rebuilt, nothing left touched.
- X2: `sketch_explain_core.is_offset()` / `bad_size(..., offset)`; `parameters.broken_problems`
  and `change_checked` compare (step, problem) keys; `set_sketch_dimension` accepts 0 for an
  offset. The dimension box in the sketch (sketch_mode) still refuses 0 for any dimension,
  as Fusion does. Tests: `test_sketch_explain_core.py`, headless session (circle at the
  origin: Change Parameters refuses d = -4; an old line-width-0 problem does not hide it;
  g0.x 5 then 0).
- X3: `value_limits.search(strict=True, per_try=...)`: every build counted against the
  budget, none started that the time left cannot hold (judged by the slowest try so far);
  `value_fit.search_sentence` gives all values of a call one budget, starts from the refused
  call's own time, and answers `too_slow` when it cannot try twice. The dialogs' search is
  unchanged. Tests: `test_ai_value_fit.py` (fake clock: whole search <= 3 s, too slow, a slow
  first try).
- X4: `document_actions.export_file` writes the whole design with `exchange.export_cad(scope
  "design")` with or without the window; `export_report.design_facts` sets `flat` for a list
  of bodies and `export_report_core.items` then lists the components for STEP. Tests:
  `test_export_report_core.py`, scenario `ai_tools_gui` path 8.
- X5: `executor.run` compares the Redo list before and after a refused call. Test: headless
  session (fillet R1, undo, fillet R50 refused: the answer names the emptied redo).
- X6: `sketch_actions._shown()` (open in edit, or shown with every container above it).
  Test: scenario `ai_tools_gui` path 9.

## Not changed

- The reviewer's own repro scenarios `xreview_a` (path A deletes Sketch1 with two undos,
  then reads it) and `xreview_c` (its ledger wrapper takes the old one-argument `opened`)
  fail for reasons of their own; the behaviour they probe is covered by the tests above.
