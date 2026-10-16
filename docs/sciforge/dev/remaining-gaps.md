# Remaining gaps after the first plan (survey of 2026-10-14)

Every area of the first plan is merged (up to `sf/gaps`). This survey lists what the parity
docs (`docs/sciforge/parity/*.md`) still mark as missing or different from Fusion. Wave 4
(briefs in `docs/sciforge/dev/briefs/*-2.md`) takes the top of it.

## By area

- **sketch.md**: (Chamfer types with typed values and dimensions by sf/modeling-2; the typed
  line angle from the X axis matches Fusion's forum answers; a sketch on an edited face shows
  the part as it is now, and an older sketch edited from the timeline shows its own body
  rolled back, by sf/fix-sketch-face.) Editing an older sketch rolls back only its own body in
  the drawing (Fusion rolls back the other bodies too); suppressing a Move also suppresses a
  sketch on its face. No 3D Sketch. Project to Surface
  curves sit outside the sketch (not in the browser or timeline). Chamfer lines only.
- **extrude-presspull.md**: (To Object extend options, Offset and a following Start: Object by
  sf/modeling-2; a clicked face or corner sets the height, and a held arrow snaps to it, by
  sf/fix-extrude-to-face.) Move, Scale and Draft handles have no value box. Press Pull on a
  face (an offset) does not snap to a clicked face; no snapping to edges or sketch points
  while dragging.
- **fillet.md**: (sf/fillet-2 built radius sets, Chord Length, Variable, Tangent Chain off,
  Rule and Full Round fillets.) Left: G2, Setback, Asymmetric (kernel); Full Round only on a
  straight rib between parallel walls; radius points take plain numbers.
- **hole-thread.md**: (NPT / BSPT, fastener clearance, thread class, curved faces by
  sf/modeling-2.) Taper threads are cosmetic only; three screw types in the tables.
- **patterns.md**: (Components by sf/components-2; Compute Option Adjust and the Path start
  point by sf/modify-2; body patterns and mirrors copy the body as it is at the pattern, roll
  back with the marker and survive the original's deletion, by sf/fix-pattern-bodies.) Left:
  Mirror of components; Adjust only re-runs extrudes; Delete on one copy deletes only that
  copy (Fusion deletes the whole pattern); editing a pattern does not roll the design back to
  it; undo of a marker roll before a step outside the bodies leaves the marker after it.
- **joints.md**: (sf/joints-2 built Component Drag, position modes, Motion Link, Contact Sets,
  Motion Study, nested components, no auto-ground.) Left: a drag pulls one joint at a time (no
  whole-mechanism drag solver), no contact during Animate, no Motion Study graph, no Lock
  Motion or Animate Joint Relationships.
- **components.md**: (sf/components-2 built Move/Copy, Set Pivot, Copy/Paste instances, Paste
  New, component patterns, the marker hiding components, the see-through look.) Left: a copy's
  nested components are flattened; deleting the original freezes its copies; no paste between
  designs; no Mirror of components; no "position pending" question.
- **drawings.md**: (tolerances, fits, dimension text, ordinate / baseline / chain, Leader,
  GD&T, sheets, Full / Half / Offset / Aligned sections, depth, breakout and auto centre marks
  by sf/drawings-2.) Left: Exploded views, Note and Weld symbols, Arrange Dimensions, hole notes,
  per-sheet size, DWG, depth only on straight cut lines.
- **bodies.md**: (Combine New Component, multi-tool Split, Set Pivot, component moves by
  sf/components-2; Move Object Faces by sf/modify-2.) Left: faces of one body per Move.
- **direct-modify.md**: (Press Pull Offset Type and Replace Face onto any surface by
  sf/modify-2.) Features in a direct design cannot be edited.
- **revolve.md**: (Objects To Cut for Revolve, Sweep and Loft by sf/modeling-2.) Editing an
  older step does not roll the timeline back first.
- **primitives.md**: no snapping to edge midpoints or to points off the plane.
- **shell-draft-scale.md**: (Parting Line, Two Side, Symmetric, several bodies per step and
  Scale of sketches by sf/modify-2.) Left: Move Parting Line (kernel), components not scaled,
  non-uniform scale of a sketch.
- **sweep-loft-rib.md**: (Sweep formulas by sf/modeling-2.) No Loft Tangent Edges Merge. End
  conditions not with rails, a centerline or a closed loft.
- **surface.md**: surface Extrude has no From Object or All. Surface Revolve has no Type To.
  Surface Sweep has no rail or taper, surface Loft no rails or end conditions.
- **text-emboss.md**: the text frame cannot be resized by dragging its corner.
- **insert-export.md**: no IGES, DXF or DWG export. STEP comes in flattened to bodies. Insert
  SVG/DXF and Canvas have no manipulators.
- **mesh.md**: no Direct Edit environment. No Create or Combine Face Groups. Mesh steps do not
  roll back with the marker.
- **inspect.md**: Interference cannot create bodies. Measure's Component filter is greyed.
- **inspect-analysis.md**: meshes cannot be analysed. No Include Sharp Curves.
- **misc.md**: (Decals follow their face through moves, joints, face edits and component
  copies by sf/fix-decal.) Derive brings components in flat. The source version cannot be
  chosen. No adsk add-in API. A decal on a component's copy is listed only under the
  original; a face that changes shape and moves in one step may lose its decal (red, Select
  Face puts it back).
- **selection.md**: no double-click chain selection in sketches. No box selection of planes
  and axes.
- **timeline-browser.md**: an Extrude made while rolled back before a fillet cannot switch to
  Cut. Groups cannot be dragged as a whole. No New Body command.
- **versions.md**: no automatic version on close, Milestone, Data Panel Move/Copy or
  out-of-date icon.
- **ui-shell.md**: dialogs are docked, not floating. Document tabs are at the bottom. No
  COMMENTS panel. No lit environments.

## Needs FreeCAD C++ or the kernel

- Patch Curvature continuity: core patch #14, in full build #6 (63fe08ff6d) and later.
- A hole's seam line across bent section views: TechDraw's DrawViewSection (C++); straight
  sections hide it (sf/drawings-2).
- Fillet Tangent Chain off, G2 fillets, setback corners: OpenCASCADE limits (fillet.md).
- Sketch Curvature constraint: FreeCAD's solver has none (G2 only spline-line).
