# 2026-10-23: PLASTIC part 2: Snap Fit, Lip, Design Advice (branch `sf/plastic-2`, wave 6)

Luca asked for Fusion's SHEET METAL and PLASTIC tabs, all of it, in one go (plan
`docs/sciforge/plan-sheet-metal-plastic-surface.md`). This builder did PLASTIC > CREATE > Snap
Fit and Lip and PLASTIC > INSPECT > Design Advice. Spec with sources, what is built, tests and
gaps: `docs/sciforge/parity/plastic-2.md`. No core patch (no full build needed). MEMORY.md not
edited (this file is the session log entry).

## What was built

- `sciforge/plastic_snap_core.py`, `plastic_lip_core.py`, `plastic_advice_core.py`: the pure
  parts (no FreeCAD, no Qt): options and their defaults from the plastic rule, which fields
  follow the rule ("linked" until typed), every refusal with its text, the hook's sections
  and catch profile, the groove / slot / loop boxes, the strain check (tapered factor
  1 / 1.09 per the research's critic pass C5), the lip and groove sections as offsets from
  the picked edges, the Design Advice checks, colours, list rows, a smooth thickness blend
  and a numpy ray caster.
- `sciforge/plastic_snap.py`, `plastic_lip.py`: the steps. A lead step in one body
  (`SnapFitFeature`, `LipFeature`) and a hidden follower in the other body
  (`SnapGrooveFollower`, `LipGrooveFollower`, subclasses of `modify_bodies._Follower`, role
  ModifyFollower, so the timeline rolls back / suppresses / moves / deletes them with the
  lead without any change to the timeline code; golden models prove suppress and the
  marker). `make / update / read / remove`, used by the dialogs, the golden ops and tests.
  Snap Fit: three types, Automatic / Manual points, Uniform / Independent / Aligned (to the
  points' middle, a point, a line or a face), To Next / Distance, beam taper and draft, catch
  angles, base fillet, Hook / Groove switches, picked or found bodies, Flip. Lip: Lip /
  Groove / Lip And Groove, Swap, tangent chains (closed or open, straight or round), Pull
  Direction (rim normal or picked) and Face Guide (leans with a drafted wall), drafts, tip
  and root radius (the groove's mouth rounded to keep the clearance).
- `sciforge/plastic_advice.py`: the analysis object (`DesignAdvice`, SciForgeType
  "DesignAdviceAnalysis", so the browser's Analysis folder shows it), measuring in its
  `execute` (results as JSON in `Results`), never failing (a `Problem` text instead), waiting
  while hidden (`Stale`) and checking again when shown.
- `sciforge/plastic_snap_ui.py`, `plastic_lip_ui.py`, `plastic_advice_ui.py`: the dialogs
  (`taskui.Panel`), arrows and rotation handles with value boxes, view providers,
  `COMMANDS` / `EDITORS`, and the timeline kinds (`timeline_core.KINDS["snap_fit"]`,
  `["lip"]`), Change Parameters entries and the browser's Analysis icon registered at import
  (no edit of those shared files).
- Golden ops `sf_snap_fit`, `sf_snap_fit_edit`, `sf_lip`, `sf_lip_edit`
  (`ai/ops/plastic2_ops.py`, schema `golden/plastic2_schema.py`), 18 golden models with
  hand-worked volumes (they give every size, so they do not depend on the default rule).
- Icons `pl_snap_fit`, `pl_lip`, `pl_design_advice`, `pl_snap_groove`
  (`tools/sciforge/icons_plastic2.py`); the three ribbon entries wired.
- Scenarios `plastic2_snap` (63 checks), `plastic2_snap_options` (78), `plastic2_lip` (85),
  `plastic2_advice` (70); helpers `SciForgeTests/gui/plastic2_steps.py`; unit tests
  `test_plastic2_core.py` (34).

## FreeCAD facts and traps found

- **A step's Placement lands on the shape it is given.** During a recompute FreeCAD puts a
  feature's own `Placement` on the shape assigned to it (`Part::Feature::onChanged`). A
  `PartDesign::FeaturePython` added after a PartDesign primitive inherits the primitive's
  Placement (a cavity box at (2, 2, 2)), so a body-coordinate result assigned as it is was
  drawn (and picked) 2 mm off, with the right volume. `plastic_snap.assign_shape` puts the
  geometry in moved back by the step's Placement. Other SciForge FeaturePython steps
  (`rib.py`, `shelling.py`, `presspull.py`, `modify_bodies._Follower`) assign shapes as they
  are and would show the same shift after a primitive (not seen with sketch + extrude, whose
  steps have no Placement): worth a check by their owners.
- `Mesh.nearestFacetOnRay` ignores the ray's direction (it returned a facet behind the
  origin): Design Advice casts its own rays (numpy Moller-Trumbore).
- `Wire.makeOffset2D` refuses a single straight edge (no plane of its own): the band beside
  a straight chain is made as a rectangle in the rim's plane.
- Which side a `makeOffset2D` with a positive distance grows to depends on the wire's
  direction: a rectangle picked from a cavity grew, a circle picked from a cone's top face
  shrank. The band takes the bigger of the two offset loops as its outside.
- A cut or fuse of two faces gives a Shell, not a Face (`OuterWire` missing): `_one_face`.
- A ray along a face's inward normal runs along inside the wall at a rim's top or a hole's
  side (20 mm instead of 2): the wall is then measured across, from the nearest face
  straight through.
- Searching for "the other body" must look at it as it was before this step's own groove
  (`_before(lead, body)`), or an edit finds no body any more. Searching for the hook body
  must start on the parting plane itself: a start a hair to the other side began inside a
  panel under the lid and took it for the hook's body.
- In the GUI a click on an edge of the preview can name an edge the base does not have (the
  lip lengthens a rim edge): the edge is found again by the clicked point.
- In xvfb, clicks meant for a face land on a drag arrow drawn on top when they are close on
  the screen: scenarios click away from the dialog's handles.

## Gaps (details in the parity doc)

Fusion's exact Snap Fit / Lip dialogs (no page access, no API objects: labels, defaults and
the Parallel / Perpendicular geometry are SciForge's reading); Face Guide on a chain whose
walls have different drafts (refused); lip edges not in one plane (refused); Snap Fit
visibility controls (read as Hide Other Body); Aligned to a face uses its centre; Root
Radius defaults to 0; Design Advice is sampled (8 points a face), no browser alert badge;
injection-moulding simulation out of scope.

## Notes for the integrator

- Shared file touched: `ribbon_config.py`, the three `# owner: plastic-2` lines only. A trial
  merge with `sf/plastic-1` conflicts on the adjacent CREATE lines: keep plastic-1's Boss and
  Rest lines and this branch's Snap Fit and Lip lines (both as committed).
- `plastic_lip.py` imports `assign_shape` / `follower_execute` from `plastic_snap.py`.
- Scenario setups clear the plastic library preferences plastic-1 adds
  (`Mod/SciForge/Plastic`: Library, Default), so a user default left by another scenario
  cannot change the checked sizes.
