# 2026-10-22: the nine parallel branches made to work together (branch `integration`)

To be copied into MEMORY.md by whoever merges `integration` (this branch does not edit
MEMORY.md). `integration` = `experimental` (0b1da82) + the nine branches of 2026-10-21/22
(wf/limits, wf/sketch-explain, wf/export-report, wf/ai-tools, wf/ai-verify, wf/ai-docs,
wf/view-speed, wf/parity-script, wf/pdf), merged without textual conflicts, then this
session's work. No FreeCAD core file changed (nothing for `core-patches.md`, no full build).

## In plain words (for Luca)

The branches were built side by side, so some of them could not use each other yet. Now:

1. **An AI that exports or imports gets the same "what is lost" list you get.** After an AI
   (the chat panel, Claude over MCP, or `sciforge-cli convert`) exports a STEP / STL / 3MF /
   OBJ / IGES / BREP / DXF file or a drawing, its answer ends with "Not kept in this file:"
   and the same lines as the card you see after File > Export (the timeline, sketches,
   hidden bodies, colours...). In the window the card also appears. After an AI inserts or
   opens a file it is told what did not come in ("Not brought in, or changed: the mesh is not
   closed: 3 open edges..."), like the card after INSERT. BREP files (only the AI writes
   them) got their own rule: exact shapes, but no names, colours or structure.
2. **An AI that asks for a size that does not fit is told the largest one that does.** Your
   dialogs stop a dragged or typed value at the limit (your decision of 2026-10-21). An AI
   asked for an exact number, so SciForge does *not* quietly build a smaller one: the call
   fails as before, and the message now ends with, for example, "Largest radius that fits
   here: 19.99 mm (30 mm does not; ... give radius 19.99 or less)". It is found with the same
   search your dialogs use, by trying values (a few seconds at most) in steps that are taken
   back, so the design and the undo list are untouched. It works for fillet, chamfer, fillet
   sets, shell, draft, press pull, extrude taper / thin wall, surface thicken, torus, coil,
   pipe and gear sizes, and for changing those sizes later (edit_step). A shell thicker than
   the part, which OpenCASCADE used to hand back unchanged with only a warning, is now refused
   the same way.
3. **An AI's sketch constraints explain themselves like yours do.** A constraint or
   dimension an AI adds that fights the sketch (or that the sketch already says) is refused
   with the same words you see: "Vertical: not added, it conflicts with the 50 mm dimension
   'len'", plus the constraint numbers so the AI can delete or change them. In the window the
   culprits get the red rings. A new dimension value that does not fit says what it fights
   ("That value does not fit: it conflicts with ..."). The AI's design summary
   (inspect_design / check_design) now says for every sketch whether it is fully constrained
   (your padlock) and how many ways it can still move.
4. **Checked together:** an AI's Undo / Redo now skips the slow rebuild exactly when your
   Ctrl+Z does (the "undo without rebuild" of the speed work), the padlock is redrawn in the
   timeline when only the lock changes, and the test of fast Undo got two new paths: a
   fillet value held at its limit, then Ctrl+Z / Ctrl+Y; and the AI's own undo / redo, and a
   refused AI value followed by Ctrl+Z. The work list (`remaining-gaps.md`) no longer lists
   the two sketch gaps the sketch-explain branch closed (G-03, G-06).

## What was built (for the next session)

- `sciforge/ai/actions/document_actions.py`: `export_losses()` (export_report.safe_losses +
  export_report_ui.report_export: the log line, the card in the window, and the lines for the
  answer), `import_notes()`, `report_lines()`; `export` (every format: whole design as File >
  Export writes it, chosen bodies, `whole=True` for exportable_bodies, the mesh options),
  `open_design` (STEP / IGES notes), `import_file` (STEP / IGES, mesh, DXF notes with the
  curves a sketch could not take). `drawing_actions.export_drawing`: PDF all sheets, DXF the
  current one. `headless.convert` also carries the source's import notes.
- `export_report_core` / `export_report`: format `brep` (EXACT_FORMATS step / iges / brep: no
  mesh bodies; names lost = every solid, BREP is one unnamed compound). Unit test `test_brep`.
- `sciforge/ai/value_fit.py` (new, pure, unit tested in `test_ai_value_fit.py`): which values
  of which tools are searched (`LIMITED`, paths into the arguments, `sets[*]` for fillet
  sets; formulas in `expressions` are never searched), `largest(tool, args, trial)` with
  `value_limits.search` (budget 3 s), the sentence. `is_limit()` = value_limits' words or
  "failed to compute".
- `executor.Context.build`: `_run_steps` (one transaction; for a limited call also refuses a
  result whose volumes and boxes did not change: `_NoChange`), `_trial` (the same call with
  another value in a transaction that is aborted; a trial is stricter: valid solids and a
  volume change), `_largest`. When nothing changed and no smaller value helps, the call is
  built as asked with the old "Warning: no solid changed" (cuts that miss are unchanged).
- `timeline_actions.edit_step`: the same for an edit (`edit_candidates`, `_largest_edit`).
- `sketch_actions`: `_add_checked(ctx, sketch, constraints, title)` uses
  `sketch_explain.check_new` / `refusal` (Fusion titles: Coincident, Symmetry, Fix...);
  when the solver fails without listing the new constraint, the ones it lists are named;
  `_explained` adds the indices and highlights in the window (the "(highlighted in the
  sketch)" words only there); `set_sketch_dimension` refuses a size of 0 and names a value
  conflict (`value_conflict`); `get_sketch` reads the padlock with sketch_explain and the
  degrees of freedom from `DoF`.
- `verify_actions._freedom`: `fully_constrained` and `degrees_of_freedom` per sketch in
  inspect_design and check_design (no solve, except a sketch not solved since its file was
  opened, whose DoF FreeCAD leaves at 0).
- `document_actions._settle_after_undo`: the AI's undo / redo do what
  `timeline_ui.after_undo` does (undo_fast.settle_without_rebuild, else
  timeline_ops.recompute).
- `timeline_ui._look` includes `locked`.
- Docs: troubleshooting "A size that does not fit" and "Files", handbook, sketches, every
  tool reference page's Errors (generated: `tool_docs._errors`), the overview / MCP
  instructions; catalogue descriptions of export, open_design, import_file, export_drawing;
  reference examples recorded again (export STL / STEP, export_drawing DXF, inspect_design,
  check_design, get_sketch, and the two documentation-search examples whose counts moved);
  every changed answer read and checked against the design it comes from.

## Findings

- Re-applying the same value with edit_step makes no undo step (FreeCAD drops an empty
  transaction): a test that assumed one undid the step before it.
- After an AI call refused with the largest value, the next Ctrl+Z rebuilds instead of
  skipping (the trial transactions are taken back and the design recomputed outside a
  transaction, so undo_fast cannot vouch for the shapes): the safe side, the part is right.
- A shell as thick as the part (10 mm on a 10 mm plate, top face open) comes back with the
  same volume and other faces: not a shell. Limited calls now compare volumes, not faces.
- `parity.py --check` was up to date after the merge (457 / 631 Fusion commands); the merge
  changed no menu. `check_install.sh`: all files installed.

## Tests

- Unit: `test_ai_value_fit.py` (11, new), `test_export_report_core.test_brep`; whole suite
  2091 OK (9 skipped).
- Headless: runner checks the export reports (STEP, STL, BREP, drawing DXF) and the
  sketch refusal words; docs runner (every documentation block, the examples recorded
  again): 137 items, 874 calls, 0 failed; agent end to end 70 / 70.
- GUI: `undo_fast` paths E and F (71 checks), `ai_tools_gui` path 7 (the AI export's report
  and the window's card).
- `run_tests.sh --only base` on the final code: all passed (unit 2091 OK, 9 skipped; golden
  451 pass + the 2 known XFAIL plate_hole_grid and sf_loft_merge_slot_volume; headless 202
  calls / 117 tools / 0 failed; documentation examples 137 items / 874 calls / 0 failed;
  agent end to end 70 / 70; smoke, journey, restart).
- Scenarios, all PASS: ai_agent_e2e (78 checks), ai_bridge (44), ai_chat (20), ai_docs_gui
  (16), ai_panel (27), ai_tools_gui (22), drawing_pdf_layers (55), export_report (61),
  fillet_qa (114), import_report (39), limits_fillet (51), limits_presspull (35),
  limits_shell_draft (48), parameters_trial (36), perf_benchmark (21), sketch_explain (159),
  timeline_browser (92), undo_fast (71). The full suite (about 400) was not run here.
- `make_ai_docs.py --check`, `parity.py --check`, `check_install.sh`: pass.

## Limitations

- The AI's search tries values by building the step (each trial is a real build): on a very
  big design it can take longer than the 3 s budget (at least 3 builds are made).
- Values that must not get *smaller* (a coil's pitch, a torus' inner diameter, a gear's
  rim) are not searched: only values whose safe side is toward 0.
- set_model_parameter (fillet sets' sizes) is not searched.

## Later the same day: the four scenarios that failed in the full GUI run

The full GUI suite (427 scenarios) passed except four, which failed every time, also alone.
Each is now fixed (code bug, or an expectation still written for the old refusal).

- **`patterns_qa_more`, Circular Pattern Total Angle 270 typed (code bug).** The curved
  handle said -90 instead of 270 and a drag from there gave -70.9. Cause: the limits branch
  made `extrude_ui.AngleDragger.set_angle` remember the angle as the disc reads it back (80
  came back as 80.0000026), but the disc itself only knows -180..180: 270 reads back as -90,
  and the pattern's handle (`pattern_ui._TurnDragger`, which counts past half a turn from
  its last reading) then started from -90. Now the read-back is unwrapped next to the angle
  asked for (270 stays 270, 80 still keeps its read-back rounding). It passed on 0b1da82,
  before the merge of wf/limits.
- **`revolve_qa` P4 (expectation).** 400 typed is set to 360 and said ("400° does not fit:
  limited to 360.0°"), the preview is a full turn: Luca's approved behaviour. The scenario
  checked the old error; updated.
- **`revolve_axes` 3 (expectation, plus a clearer note).** Two Sides 270 + 120: side two is
  set to 90 (the two sides together one full turn, the whole ring) and OK works, so the
  scenario's "OK refused" and everything after it (the dialog had closed) failed. Updated:
  it checks the held angle, the note, no error and the full ring in the preview, then goes
  on with One Side 360, New Body, OK as before. The note now says why the limit is less
  than 360: "120° does not fit: limited to 90.0° (both sides together make one full turn)"
  (Symmetric: "(180° each way make one full turn)"), also for the arrow's "Largest that
  fits here"; `limits_revolve` updated to those words.
- **`modeling2_sketch` 2 (expectation, and a real bug).** The equal chamfer typed 30 on a
  side with 17.1132 mm left is now held at the largest that fits (Luca's decision), so the
  old "refused" check and the steps after it failed. The real bug: the largest value was
  rounded down to the box's precision (17.11), which left a line of 0.0032 mm in the sketch
  (and a sliver face once extruded). The sketch Fillet had the same problem (`sketch2_fillet`
  B: radius 29.99 left 0.01 mm of the 30 mm line). Decision: **the largest sketch fillet or
  chamfer takes the curve whole.** Its limit is worked out exactly (chamfer between two
  lines: `sketch_chamfer_core.largest`, from the lines' lengths; fillet:
  `sketch_fillet_core.largest_radius`, a bisection to 1e-12 with no rounding), reaching
  the far end of a curve now fits (`check_fits`, `fits`), and a value within the box's
  precision (0.01 mm) of the limit counts as the limit, so no sliver can be left by a drag
  or a typed 17.11 either. The used-up curve is not cut to nothing (a zero-length line
  breaks FreeCAD's corner constraints): FreeCAD's fillet first cuts half as far, then
  `sketch_fillet_tool.give_back` gives the curve back whole as construction geometry (every
  constraint and dimension it had stays), puts the chamfer line / fillet arc exactly where
  it ends up (so the solver moves nothing, also in a sketch with free curves, where it
  otherwise dragged a line 3.6 mm away) and joins it to the curve's far end (the fillet
  tangent there). A fully constrained sketch stays so; the chamfer's dimension on the
  used-up side becomes a reference. Works for lines and arcs (checked headless: line + arc
  with the line used up, a short arc used up). Scenario updated: 30 Enter makes the largest
  chamfer (from the first chamfer's end to (32.89, 30), no line under 0.01 mm, the right
  side kept whole as construction, the sketch still fully constrained), Ctrl+Z, then 4 as
  before. `sketch2_fillet` B now also checks that the 30 mm line is kept whole and the arc
  ends at (0, 30).
- Found on the way: the line + arc chamfer (`_build_arc`) set `sketch.Geometry`, which in
  FreeCAD 1.1.4 turns construction *points* into normal points and gives them new geometry
  ids: an earlier fillet's old corner point lost its construction look. Now
  `sketch_fillet_tool.set_geometry` keeps every curve's construction flag and id
  (`sketch2_fillet` C checks B's old corner). `sketch_explain.py` (restoring curves after a
  squeezed solve), `scale.py` and `text.py` assign `sketch.Geometry` the same way (not
  changed here).

Tests (real FreeCAD 1.1.4 under xvfb): unit `test_sketch_chamfer_core.py`,
`test_sketch_fillet_core.py` (exact limits, reaching the end fits, line + arc, short arc);
`run_tests.sh --only unit` passes. The four scenarios pass (modeling2_sketch 142 checks,
patterns_qa_more 52, revolve_axes 80, revolve_qa 347), and so do the related ones:
fixsketch_fillet, sketch2_fillet, sketch2_palette, sketch_qa, sketch_pattern, the eight
sketch_tools_*, the eight revolve*, the twelve patterns*, components2_pattern,
fixpattern_circ and the ten limits_* (45 scenarios on the final code, sketch_qa just
before the last small change to `give_back`).
