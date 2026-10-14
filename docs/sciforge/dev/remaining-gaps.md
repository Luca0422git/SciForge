# Remaining gaps after the first plan (survey of 2026-10-14)

Every area of the first plan is merged (up to `sf/gaps`). This survey lists what the parity
docs (`docs/sciforge/parity/*.md`) still mark as missing or different from Fusion. Wave 4
(briefs in `docs/sciforge/dev/briefs/*-2.md`) takes the top of it.

## By area

- **sketch.md**: Chamfer has one distance set by the mouse (no types, no typed value, no
  dimension). A typed line angle is measured from the X axis. No 3D Sketch. Project to Surface
  curves sit outside the sketch (not in the browser or timeline).
- **extrude-presspull.md**: To Object has no To Adjacent Faces / Through Body / Offset. Start:
  Object does not follow later changes. Move, Scale and Draft handles have no value box.
- **fillet.md**: (sf/fillet-2 built radius sets, Chord Length, Variable, Tangent Chain off,
  Rule and Full Round fillets.) Left: G2, Setback, Asymmetric (kernel); Full Round only on a
  straight rib between parallel walls; radius points take plain numbers.
- **hole-thread.md**: no Taper Tapped (NPT). Clearance holes not chosen by fastener. The
  modeled thread ignores the class. A hole on a curved face does not follow the face.
- **patterns.md**: no Compute Option Adjust / Optimized. No Pattern Type Components. No start
  point for Pattern on Path.
- **joints.md**: (sf/joints-2 built Component Drag, position modes, Motion Link, Contact Sets,
  Motion Study, nested components, no auto-ground.) Left: a drag pulls one joint at a time (no
  whole-mechanism drag solver), no contact during Animate, no Motion Study graph, no Lock
  Motion or Animate Joint Relationships.
- **components.md**: a whole component cannot be moved. No copy/paste of components. Rolling the
  marker back does not hide a component. Inactive components are not ghosted.
- **drawings.md**: one sheet per drawing. No tolerances or dimension text editing, no
  ordinate / baseline / chain dimensions. No Leader, Note or GD&T. No section depth, offset,
  half or breakout sections. No automatic centre marks. No DWG.
- **bodies.md**: Combine has no New Component. Split Body takes one tool. Move has no Set Pivot
  and cannot move components or faces.
- **direct-modify.md**: no Press Pull Offset Type. Features in a direct design cannot be edited.
  Replace Face only takes flat, cylinder or sphere targets.
- **revolve.md**: no Objects To Cut (Revolve, Sweep and Loft act on the sketch's body only).
- **primitives.md**: no snapping to edge midpoints or to points off the plane.
- **shell-draft-scale.md**: Draft has no Parting Line or Two Sides. One body per step.
  Sketches and components cannot be scaled.
- **sweep-loft-rib.md**: no Loft Tangent Edges Merge. End conditions not with rails, a
  centerline or a closed loft. Sweep distances take plain numbers only.
- **surface.md**: surface Extrude has no From Object or All. Surface Revolve has no Type To.
  Surface Sweep has no rail or taper, surface Loft no rails or end conditions.
- **text-emboss.md**: the text frame cannot be resized by dragging its corner.
- **insert-export.md**: no IGES, DXF or DWG export. STEP comes in flattened to bodies. Insert
  SVG/DXF and Canvas have no manipulators.
- **mesh.md**: no Direct Edit environment. No Create or Combine Face Groups. Mesh steps do not
  roll back with the marker.
- **inspect.md**: Interference cannot create bodies. Measure's Component filter is greyed.
- **inspect-analysis.md**: meshes cannot be analysed. No Include Sharp Curves.
- **misc.md**: Derive brings components in flat. The source version cannot be chosen. No adsk
  add-in API.
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
- A hole's seam line across section views: TechDraw's DrawViewSection (C++).
- Fillet Tangent Chain off, G2 fillets, setback corners: OpenCASCADE limits (fillet.md).
- Sketch Curvature constraint: FreeCAD's solver has none (G2 only spline-line).
