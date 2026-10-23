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
  box (and, editing the flange that made a body, the swap of that body's rule), height arrow,
  distance arrow, angle handle on the bend, value boxes, formulas / user parameters in every
  field, Two Offsets between two picked faces / planes, a contour drawn from the end of a
  sheet edge joined along that edge), Sheet Metal Rules (`sheetmetal_rules_ui.py` + `sheetmetal_rules.py`: In This Design
  / Library, New / Edit / Copy / Delete / Set Active, editor page), New Component Type
  (`components_ui.py` + `sheetmetal_component.py`).
- **Integration**: ribbon (Flange, Sheet Metal Rules wired; the SHEET METAL skeleton matched the
  research, left as it was), browser (bent-sheet body icon with the rule in its tooltip,
  Sheet Metal component icon, "Sheet Metal Rule: <name>" row under Document Settings that
  opens the dialog), timeline name/icon (`timeline_core.KINDS["flange"]` registered from the
  `_ui.py`), Change Parameters fields (`parameters.SCIFORGE_PROPS["Flange"]`), icons
  (`tools/sciforge/icons_sheetmetal.py`: sm_flange, sm_rules, sheet_metal_body, sm_component).
- **Tests**: 19 golden models (volumes by hand, one FreeCAD baseline), unit tests
  (`test_sheetmetal_flange_core.py`), 6 scenarios (flange 79 checks, rules 60, contour 58,
  edge options 64, parameters 17, components 36), the SHEET METAL ribbon sweep (99).

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
- A mitre at an **inside** corner (L-shaped plate) must keep each flange on its own edge's side:
  the side is taken from the edge's midpoint, not from the outward normals' difference (the
  first version cut both flanges away there and still made a valid, wrong solid; a probe
  caught it, golden `sheetmetal_edge_flange_inner_corner` now holds it).
- The Flange preview changes the plate (the bend cuts it back), so a second edge clicked on
  the preview is shorter than the plate's: it is matched back to the plate's edge by line and
  midpoint (`_same_edge`), not by length.

## Gaps (also in the parity doc's Known gaps)

Corner relief shapes are not cut in the folded part (needs the unfolder); edge flange New
Body; a contour flange on an edge always runs the whole edge (no width types / bend
position); splines in contour flanges; Tear relief is a 0.05 mm slit; rule expressions take
Thickness only (the Flange's own fields take user parameters).

## Notes for the integrator

- Shared files touched: `browser_core.py` / `browser_ui.py` (icons, rule row; `build()` got a
  `settings_extra=()` keyword as the integration map planned, plastic-1 may add its row
  there), `components_ui.py` (Type row), `ribbon_config.py` (two own lines),
  `SciForgeTests/gui/scenarios/ribbon_sweep.py` (one INTENDED line for the rules window).
- sm-more: `sheetmetal_form.bend_wall(frame, t0, t1, thickness, radius, angle, length,
  position)` and `edge_frame(shape, "EdgeN", thickness, flip)`; `effective_rule(rule, opts)`.
- sm-flat: every flange solid is walls + cylinders; a radius 0 bend has no inner cylinder.
  `sheetmetal_flange.corner_reliefs(step)` (and `sheetmetal_form.mitred_corners`) give each
  mitred corner and the 2-bend relief to cut in the flat pattern (the folded part leaves the
  corner open).

## QA pass (2026-10-23, branch `sf/sm-forming-qa`)

Independent QA of `sf/sm-forming` (every sheet metal scenario, the shared-file scenarios
components_basic, timeline_browser_2, timeline_browser_qa3, ribbon_sweep with
SWEEP_TABS=sheet_metal, unit and golden runs, the whole diff read, headless probes of the
geometry against research 4.3 / 4.4 / 4.7).

Fixed (details in `docs/sciforge/parity/sheet-metal.md`, "QA pass"):

- A later Flange on the plate edge next to an earlier edge flange was refused ("not on the
  sheet's thickness"): the two side faces fuse into one coplanar face. `edge_frame` probes
  the solid's thickness when the face extents cannot tell.
- Mitred corners of flanges standing out past the plate (Outside / Adjacent, or leaning out
  below 90 degrees) were left open; the flanges now run on to the mitre (research 4.7).
- A Sheet Metal component's active rule could be deleted from the design.
- New Component + a Rule chosen after the pick left the component's active rule behind.
- A library rule tried in the Flange's Rule box and then left stayed In This Design.
- Inserting a design with its own rule into one that already had sheet metal silently
  rebuilt the inserted parts in the default rule (copied rule stores were never read).

FreeCAD facts found:

- `Document.copyObject(obj, True)` (Paste New, Insert) copies the objects a flange links
  through `App::PropertyLinkGlobal` too: the rule store comes along as `SheetMetalRules001`.
- After a fuse + `removeSplitter`, a plate's side face and a coplanar flange end face become
  one face: never measure the sheet's thickness from a face's extent alone.
- `harness.press` sends keys to the 3D view: a non-modal window (Sheet Metal Rules) gets Esc
  only when it is sent to its own focused widget.

New tests: scenario `sheetmetal_qa` (empty design, preselected edge, Cancel, save / reopen,
edit from the timeline, rule Undo / Redo, later flanges, component rule refusal, New
Component rule, Outside mitre), golden models `sheetmetal_edge_flange_adjacent_later` and
`sheetmetal_edge_flange_miter_outside`.
