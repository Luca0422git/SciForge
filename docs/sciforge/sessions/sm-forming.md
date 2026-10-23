# Session log: SHEET METAL, forming (branch `sf/sm-forming`, wave 6, 2026-10-23)

Builder: sm-forming (rules, sheet metal bodies, Flange). Brief:
`docs/sciforge/dev/briefs/sm-forming.md`; spec `docs/sciforge/parity/sheet-metal.md`.

## What was built

- **Geometry, Qt-free** (`sheetmetal_form.py`, committed in the first hour for sm-more):
  `base_flange`, `contour_flange` (open chain of lines / tangent arcs, sharp corners bent so
  the inside radius is the rule's), `edge_frame` (finds the sheet's top/bottom face, side
  face and thickness at a picked edge, with the reasons a pick is refused), `bend_wall` (one
  bend + wall on a sheet edge: the public piece Hem reuses), `edge_flange` (several edges,
  Height Datum, Bend Position, Angle, Flip, width types, bend reliefs with remnant, mitred
  corners with the rule's gap, To Object, rule overrides, refusals). Every solid is planar
  walls + cylindrical bends; the cross-section is built as one closed face (offsets of a
  tangent chain) and extruded, so faces are exact (no booleans for the bend itself).
- **Contract additions** (`sheetmetal_core.py`, nothing renamed): `thickness_offsets`,
  `bend_start_x`, `wall_length`, `width_range`, `path_radius`, `relief_ends`, `TEAR_SLIT`,
  `unique_name`, `check_name`, `display_value`, `parse_length`; library thicknesses per the
  research. `sheetmetal.py`: `make_sheet_metal_body` now always makes the design's rule store
  (the design keeps its own copy of its rules), `find_sheet_body(doc, active, component)`.
- **The Flange step** (`sheetmetal_flange.py`): `FlangeFeature` (`SciForge::Flange`), options
  as Fusion names them in real properties (Height, Angle, Distance... so parameters and
  Change Parameters work; unused ones hidden per kind), make / update / discard, Join checks.
- **Dialogs**: Flange (`sheetmetal_flange_ui.py`: picks decide the mode, every option, Rule
  box, height arrow, distance arrow, angle handle, value boxes, formulas / parameters in every
  field), Sheet Metal Rules (`sheetmetal_rules_ui.py` + `sheetmetal_rules.py`: In This Design
  / Library, New / Edit / Copy / Delete / Set Active, editor page), New Component Type
  (`components_ui.py` + `sheetmetal_component.py`).
- **Integration**: ribbon (Flange, Sheet Metal Rules wired; the SHEET METAL skeleton matched the
  research, left as it was), browser (bent-sheet body icon with the rule in its tooltip,
  Sheet Metal component icon, "Sheet Metal Rule: <name>" row under Document Settings that
  opens the dialog), timeline name/icon (`timeline_core.KINDS["flange"]` registered from the
  `_ui.py`), Change Parameters fields (`parameters.SCIFORGE_PROPS["Flange"]`), icons
  (`tools/sciforge/icons_sheetmetal.py`: sm_flange, sm_rules, sheet_metal_body, sm_component).
- **Tests**: 16 golden models (hand-derived volumes), unit tests
  (`test_sheetmetal_flange_core.py`), 5 scenarios (see the report), SHEET METAL ribbon sweep.

## FreeCAD facts and traps found

- **A transaction opened in a ribbon command's `Activated` is closed (empty) by FreeCAD when
  the command returns.** A non-modal dialog that changes the document later must open its
  undo step at the first change (`RulesDialog._begin`, `App.getActiveTransaction()`), or the
  changes are never recorded and Undo takes back the step before.
- **A step that must follow data outside its body** (the rule store) can link it with
  `App::PropertyLinkGlobal` (no scope check): a change of the store (and its undo) then
  recomputes the step by itself.
- `bend_start_x` for Inside / Outside at 180 degrees is infinite (tan 90): refused with the
  reason instead of a 1e16 mm cut.
- `Part.Plane(point, normal).toShape(u0, u1, v0, v1)` gives a bounded face; extruded it is a
  cheap half-space for mitres.
- "h" cannot be a user parameter name (FreeCAD reads it as hours): scenarios use "lip".
- The Flange preview changes the plate (the bend cuts it back), so a second edge clicked on
  the preview is shorter than the plate's: it is matched back to the plate's edge by line and
  midpoint (`_same_edge`), not by length.

## Gaps (also in the parity doc's Known gaps)

Corner relief shapes are not cut in the folded part (needs the unfolder); edge flange New
Body; contour flange attached to an edge with width types; Two Offsets from picked faces;
splines in contour flanges; Tear relief is a 0.05 mm slit; rule expressions take Thickness
only.

## Notes for the integrator

- Shared files touched: `browser_core.py` / `browser_ui.py` (icons, rule row; `build()` got a
  `settings_extra=()` keyword as the integration map planned, plastic-1 may add its row
  there), `components_ui.py` (Type row), `ribbon_config.py` (two own lines),
  `SciForgeTests/gui/scenarios/ribbon_sweep.py` (one INTENDED line for the rules window).
- sm-more: `sheetmetal_form.bend_wall(frame, t0, t1, thickness, radius, angle, length,
  position)` and `edge_frame(shape, "EdgeN", thickness, flip)`; `effective_rule(rule, opts)`.
- sm-flat: every flange solid is walls + cylinders; a radius 0 bend has no inner cylinder.
