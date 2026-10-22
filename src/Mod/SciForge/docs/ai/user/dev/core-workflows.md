<!-- A copy of docs/sciforge/dev/core-workflows.md for AI models, made by tools/sciforge/make_ai_docs.py: edit the original, then run the script. -->

# Everyday workflows: does each one work end to end?

**The depth check** next to the breadth check ([../parity-checklist.md](../parity-checklist.md),
which only says whether Fusion's menu entries exist). Like CADCraft's "alpha gate"
([cadcraft-lessons.md](cadcraft-lessons.md), idea 5): the six things Luca does in Fusion
every day, each marked **works end to end: yes / partly / no**, with the tests that prove it
and what is still missing. What is missing goes into the ranked work list
[remaining-gaps.md](remaining-gaps.md) (the G- numbers below).

Rules for this page:

- **yes**: Luca can do the whole workflow the Fusion way with no workaround; gaps left are
  options he rarely needs. **partly**: he gets to the end, but meets a missing piece or a
  workaround in normal use. **no**: he cannot finish it.
- Evidence is a test that drives SciForge with **real input** (GUI scenarios in
  `src/Mod/SciForge/SciForgeTests/gui/scenarios/`, the journey test) or checks the geometry
  against hand-worked numbers (golden models in `SciForgeTests/golden/models/`). Each was
  read for what it really does, not trusted by its name. "Run" says when it last passed here.
- Change a verdict only with a test that shows it, in the same commit.

Checked 2026-10-22 on `experimental` at 0b1da82 (`tools/sciforge/run_tests.sh` with the
real FreeCAD 1.1.4): unit tests, the 448 golden models (446 pass, 2 known xfail: OpenCASCADE
volume limits), smoke and journey test, and every scenario named below.

| # | Workflow | Works end to end |
|---|---|---|
| 1 | Sketch, constrain, extrude / revolve, fillet | **yes** |
| 2 | Go back and edit an early step of the timeline | **partly** |
| 3 | Components and joints (a mechanism) | **partly** |
| 4 | A drawing with dimensions, to PDF | **yes** |
| 5 | STEP round trip (Fusion's STEP in, edit, STEP out) | **yes** |
| 6 | Export for 3D printing | **yes** |

## 1. Sketch, constrain, extrude / revolve, fillet: yes

The bread and butter: Create Sketch on a plane or a face, rectangle / circle / lines with
typed sizes, constraints and dimensions, Extrude (Join / Cut chosen by itself), Revolve,
Fillet and Chamfer, Press Pull.

Evidence:
- `journey_gui.py` (part of every test run): Create Sketch on XY by a click, a 40 x 30
  rectangle, E and a dragged arrow, Q on the top face, a sketch on that face, a circle cut
  with -5 (Cut picked by itself), a face extruded; every pick a real click.
- `pi5_case.py` (124 checks): a whole Raspberry Pi 5 case the Fusion way: base block, R3
  corners, Shell 2 mm, posts with holes, openings in three walls, a lid as a New Body, a lip,
  a vent slot and a Rectangular Pattern, the outline rounded in one click; every volume by
  hand.
- `sketch_qa_part.py` (typed sizes, Press Pull, a sketch on the pulled face, the first sketch's
  dimension edited 40 -> 50 and everything following), `sketch_tools_constraints.py`
  (Collinear, Concentric, Midpoint, Curvature with Fusion's pick flow), `sketch_infer.py`
  (automatic constraints while drawing, Ctrl to switch them off), `sketch_tools_extrude.py`.
- `revolve_qa_part.py` (a groove revolved about an edge, Cut chosen by itself, edited after
  a Press Pull change, close and reopen), `fillet_qa_part.py` (fillets and chamfers on a
  multi-step part, Press Pull on a round, history edits round fillets).
- Golden models: `fillet_top_edges`, `fillet_all_edges`, `edit_fillet_radius`,
  `revolve_washer`, the 19 `sf_revolve_*`, `sketch_nut_trap_polygon`, `param_driven_box`.

Missing (none blocks the workflow): conflicting constraints are refused without naming the
culprits (G-03), no fully-constrained padlock (G-06), no Centerline line type (G-09),
projected curves cannot be dimensioned (G-02), Fillet G2 / setback / asymmetric need the
kernel (G-80), FreeCAD's solver has no curvature constraint between a spline and an arc
(G-83).

## 2. Go back and edit an early step: partly

Double-click an early step in the timeline (or edit its sketch), change a value, OK: every
later step follows. Roll the marker back, insert a step, roll forward; suppress, delete,
drag steps.

Evidence:
- `timeline_browser_qa.py`: an early edit that breaks a later fillet turns it red with the
  reason and nothing else (Fusion's way), and back; editing a rolled-back step; a new step
  inserted at the marker, the later fillet keeping its edge on the new base.
- `gaps_timeline_start.py` (marker before the first step, a post built there, the box
  rebuilt on it), `timeline_rolled_cut.py`, `fixsketch_join.py` and the other `fixsketch_*`
  (sketching on faces of edited extrudes), `fillet_qa_part.py` path 8 (the first Extrude
  made taller after a boss, a round, a pocket and a chamfer: all follow) and path 9,
  `revolve_qa_part.py` path 6, `patterns_qa_edit.py` path 6.
- Golden models: the 10 `tl_*` (roll back / forward, roll to the start, insert before a
  fillet, move a fillet earlier, suppress, delete), `edit_width_after_fillet_and_hole`,
  `edit_extrude_then_shell`, `pp_then_edit_extrude`, `hole_references_follow_edge`,
  `picks_fillet_chamfer_kept_after_reopen`, `extrude_start_object_follows`.
- Since 2026-10-21 an edit from the timeline rolls the design back to the step while its
  dialog is open, as Fusion does (`edit_rollback.py`; 19 scenarios updated then).

Why only partly:
- **No long-history test.** The outline's benchmark "a part edited at step 2 after 20 more
  steps" does not exist; the longest edit chain tested is about five steps (G-01).
- **Faces can be lost on big edits** (FreeCAD's topological naming): a later step can lose
  its face; SciForge names the step to re-pick (known-issues.md). Fusion keeps more (G-04).
- An older sketch edited shows only its own body rolled back (G-12); editing a pattern or an
  older revolve: check that they roll back like the rest (G-07, G-08); an edit opened by a
  double-click in the 3D view does not roll back (2026-10-21 notes).

## 3. Components and joints: partly

New Component, bodies into components, Joint (J) with snap points, the joint types, limits,
Drive Joints, Component Drag, Motion Link, contact sets, copies of components.

Evidence:
- `components_basic.py` (New Component, work into the active component, the root, nested
  components), `components2_move.py`, `components2_copy.py` (linked copies follow the
  original, Paste New is independent), `components2_pattern.py`, `components2_bodies.py`.
- `joints_basic.py` (J, snap points, the block lands on the plate, Revolute),
  `joints_types.py` (all seven types with limits, Animate checked), `joints_components.py`,
  `joints2_drag.py` (Component Drag along the joint, one undo step), `joints2_slider.py`
  (limits, contact sets stop a drag and a drive), `joints2_motion.py` (Motion Link pinion and
  rack, Motion Study), `joints2_nested.py`, `joints_asbuilt_group.py`.
- Golden models: the 6 `comp_*` (moves, pivot, paste instance / new, component patterns),
  `pattern_bodies_in_moved_component`.

Why only partly:
- **A drag moves one joint at a time**: no whole-mechanism solver, so a linkage of several
  joints does not move together when dragged (G-05); no contact during Animate (G-17).
- No Mirror of components (G-13); a copy's nested components are flattened (G-14);
  deleting the original freezes its copies (G-15); no paste between designs (G-16).
- The Components selection filter and Component priority are still greyed (G-11); the
  browser's component menu lacks Physical Material, Appearance, Properties, Opacity
  Control (G-23).

## 4. A drawing with dimensions, to PDF: yes

File > New Drawing > From Design, base and projected views, sections and details, the
Dimension command, tolerances, centre marks, text, the parts list and balloons, Export PDF;
the drawing follows changes to the design.

Evidence:
- `drawing_new.py` (Create Drawing dialog, its own tab, Base View, title block filled),
  `drawing_views.py`, `drawing2_views.py`, `drawing_section.py`, `drawing_detail.py`.
- `drawing_dimensions.py` (one Dimension command: length, diameter, radius, distance, angle
  by real clicks on the sheet), `drawing2_tolerance.py` (tolerances, ISO fits, basic and
  reference), `drawing2_ordinate.py`, `drawing2_symbols.py`, `drawing_annotations.py`.
- `drawing_update.py` and `drawing2_update.py` (the fillet radius changed in the design:
  the views and the dimensions follow), `drawing_assembly.py` (parts list and balloons),
  `drawing_export.py` (Export PDF and DXF, files read back), `drawing2_sheets.py`.

Missing: Arrange Dimensions (G-20), hole notes (G-21), Note and weld symbols (G-41),
exploded views (G-62), one sheet size per drawing (G-24), DWG (G-42), Move / Rotate of a
view are greyed (drag the view by its frame instead).

## 5. STEP round trip: yes

A STEP file (from Fusion, a supplier, a printer site) opened or inserted as components with
their colours, edited, exported again with its structure.

Evidence:
- `exchange2_step_open.py` (Ctrl+O of a STEP assembly: components, the linked copy, colours,
  volumes; a copy follows its original), `exchange2_step_insert.py` and `insert_step.py`
  (Insert STEP as one component, Fusion's Initial Position move, undo; the imported bodies
  take sketches and features like any body).
- `exchange2_export.py` P1 (UTILITIES > Export STEP of the whole design, opened again: the
  same components, the copy, the positions, the colours), `pi5_case.py` (STEP export of the
  case: two solids, the design's volume), `export_formats.py` (STEP of two bodies).

Missing: bodies inside a component come back named Body1, Body2 after the round trip
(G-10); an inserted design's own components come in flat (G-22). A STEP never carries a
timeline (Fusion's neither): imported shapes are edited with Press Pull, Move face, Offset
Face and new features. `.f3d` cannot be opened (closed format, MEMORY 2026-10-16).

## 6. Export for 3D printing: yes

UTILITIES > 3D Print: pick the bodies, format (3MF / STL), refinement, then save the file or
send it straight to the slicer; Export (STL, 3MF, OBJ, STEP) and Export Everything.

Evidence:
- `export_print.py` (the dialog, refinement Low / Medium / High / Custom with the triangle
  count, a watertight 3MF within 2 % of the body's volume, Send to a slicer),
  `send_to_slicer.py` (slicers found on the computer, Other..., Save file only, what the
  slicer gets), `export_formats.py` (STL / 3MF / OBJ, one file per body, volumes checked),
  `export_everything.py`, `mesh_print.py` (a mesh body printed as it is), the smoke test
  ("3D Print writes a 3MF", volume within 1 %), `pi5_case.py` (one STL per body).

Missing: nothing found for Luca's printing work.
