### Session log: fixes to the export / import reports after review (branch `fix/export`, 2026-10-22)

Written instead of a MEMORY.md entry (parallel branches; merge it into MEMORY.md's session
log when the branch is merged). Base: `integration` (3e515b5). An adversarial review of item
2 (the export / import report card, `docs/sciforge/sessions/2026-10-21-export-report.md`)
found 11 problems. Each was reproduced on this branch before it was fixed. No FreeCAD core
change.

#### What changed for Luca (plain language)

- **The card shows every line.** Before, when the title and several lines wrapped (Export
  Everything always does), the card came out too short and the last lines were cut off or
  ran into each other. Its height now comes from the text at its real width.
- **The card no longer covers the navigation bar** in a small window: it moves up above
  the bar when they would overlap.
- **No stale card.** If you export (or import) again and this time nothing is lost, the
  card from the earlier export goes away instead of staying as if it described the new file.
- **Export Everything tells the truth about components.** Its STEP file is written body by
  body, so the components are not in it either; the card now says the components are lost
  in all four files (before it said only STL, 3MF and OBJ, as if the STEP had kept them).
  The same goes for Export > Selected bodies as STEP.
- **Save As DXF of a sketch on a face** no longer says "1 projected curve" was lost: curves
  that Project / Auto project bring in are real curves of the sketch and are in the DXF.
  Only reference curves (projected but not "defining") are listed, and they are counted
  as curves.
- **IGES** no longer says the file has no names: it has them (other programs read them).
  The card now says the names come back as Body1, Body2 ... when SciForge opens the file.
- **Opening or inserting a big STEP is fast again** (a file of 10 plates with 324 holes each:
  23.8 s before, 7.7 s now, the same as without any report). The check for "bodies with
  geometry errors" now only looks at the first 300 faces of a file.
- **Exporting a big design** spends much less time on the report (STL of the perf_big_model
  design: 0.80 s before, 0.25 s now).
- **Wording**: "1 parameter (its value is built in)", "1 component hidden, with its
  bodies", "1 loose face that is not part of a solid", "1 curved face becomes ...". In
  Export Everything a line that only some files lose starts with those files ("STL: 3
  bodies become one mesh ...") instead of ending in a second pair of brackets, and the mesh
  body line says "1 mesh body not in the STEP (exact solids only): it is in the STL, 3MF,
  OBJ" (no more advice to export it as STL right after SciForge did).
- **Parameters** are only listed for a partial export (some bodies, a component, Save As
  Mesh) when the exported steps use them (directly or through another parameter's formula).
- **A 3MF in micrometres** (it comes in 1000 times too big: FreeCAD ignores the unit) now
  gets a line on the card: "the file says its numbers are in micrometres; it came in as
  millimetres: scale it by 0.001 if the size is wrong (Unit Type has no micrometres)".

#### Findings and what was done

| Id | Finding | Result |
|---|---|---|
| F1 | card too short when lines wrap | fixed: `Notice.fit_height()` sets the height from `heightForWidth(380)` of the layout (`adjustSize()` guessed it from a wrong width) |
| F2 | STEP open / insert 3x slower (`isValid` on every part) | fixed: `piece_notes` checks at most `MAX_VALIDITY_FACES` = 300 faces per import (budget kept in the notes) |
| F3 | Export Everything / AI STEP (window open) / Selected bodies STEP are flat, card said components kept | fixed in the report: fact `flat` (body-by-body scope) makes STEP list the components. The files themselves are unchanged (see "For Luca to decide") |
| F4 | DXF: defining projected curves reported lost, references counted instead of curves | fixed: `_reference_curves` counts non-defining, non-point external curves |
| F5 | IGES "holds unnamed shapes" is false | fixed: reworded (the names are in the file; SciForge's reader brings them back as Body1 ...) |
| F6 | stale card after an export with nothing lost | fixed: `report_export` / `report_import` hide the card when their report is empty (`hide_current()`) |
| F7 | card covers the navigation bar in a small window | fixed: `place()` moves the card above the bar when they intersect, and places again after the bar has moved on a resize |
| F8 | confusing wording, broken singulars, double brackets | fixed (see above) |
| F9 | shape copies just to count curved faces | fixed: `_curved_faces` reads `body.Shape` (a face's kind does not depend on placement) |
| F10 | every parameter listed for partial exports | fixed: `_parameter_count(doc, steps)` counts the parameters the scope's steps use, transitively through parameter formulas |
| F11 | micron 3MF not reported; notes claimed 3D Print reports hidden bodies | fixed: micron mapped to "Micrometer" with a "scale it by" line; notes corrected (3D Print exports ticked bodies, so hidden bodies do not apply) |

#### For Luca to decide (not changed)

- Export Everything (and the AI's STEP export with the window open) writes a flat STEP
  (`export.export_step`: every body a part of its own, names kept, no components), while
  File > Export writes the structured one (`exchange.export_cad`: components kept, but
  bodies inside a component come back as Body1, Body2 ...). The card now says so honestly.
  Switching Export Everything to the structured STEP is possible but changes the file
  (names vs. structure): say if you want it.

#### Tests (real FreeCAD 1.1.4)

- Unit: `test_export_report_core.py` (47 tests, 6 new: flat STEP components, IGES wording,
  singular wording, combined mesh line, flat components in Export Everything, micron 3MF);
  new `test_export_report_counts.py` (validity budget, curved faces without copies). The
  new tests fail on the old code.
- Golden: `export_report_design` now has a parameter used by Body only (`thick = width /
  4` drives e1): the whole design reports 2, Body alone 2 (through the formula), Bracket 0.
  `export_report_sketch_dxf`: a sketch on a face with Auto project (no projected curve
  lost; the round trip counts the curves in the DXF) and then two reference curves
  (`sketch_extras` gained `references`): 2 projected curves. `export_report_imports`:
  `tetra_micron.3mf` reports the unit.
- New GUI scenario `export_report_card` (real Export Everything, Export dialog, a
  1100 x 700 window): the component line without formats, the mesh body line, every label
  fits in the card, no stale card, no overlap with the navigation bar.
- Changed: `import_report` ("1 hatch (FreeCAD cannot read it)"), the recorded AI example
  in `SciForgeTests/docs/tool_results.json` ("1 curved face becomes"), AI docs regenerated.
- Speed (reviewer's scripts): STEP open 23.8 s -> 7.7 s (7.3 s without any check); STL
  report on perf_big_model 0.80 s -> 0.25 s.
- `--only base`: unit 2101 OK (9 skipped), golden 451 pass + 2 known XFAIL (`plate_hole_grid`,
  `sf_loft_merge_slot_volume`), headless AI 202 calls 0 failed, docs 137 items 0 failed,
  agent 70 checks, smoke and journey: all passed.
- Related scenarios, all PASS: ai_tools_gui 22, direct_step_box 186, drawing_export 76,
  exchange2_export 89, exchange2_step_insert 75, exchange2_step_open 80, export_everything
  27, export_formats 54, export_print 44, export_report 61, export_report_card 43,
  home_screen 71, import_report 40, insert_dxf 36, insert_mesh 65, insert_step 30,
  mesh_print 34, navbar_display 73, navbar_grid 56 (failed once on a drag that landed on
  exactly 10.0 mm, passed when run again: nothing to do with the card), navbar_viewports
  59, send_to_slicer 106, sketch2_project 95.
