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
  sketch on its face. (3D Sketch on SciForge's own handler, Projected Curves belonging to the
  sketch, SciForge's own Fillet, line-arc Chamfer, by sf/sketch-2.) Left: no Centerline line
  type; 3D curves have no constraints, dimensions, arcs or typed length / angle; projected
  curves cannot be dimensioned and have no Break Link; FreeCAD loses some projections when the
  source edge moves (re-project by hand).
- **extrude-presspull.md**: (To Object extend options, Offset and a following Start: Object by
  sf/modeling-2; a clicked face or corner sets the height, and a held arrow snaps to it, by
  sf/fix-extrude-to-face; value boxes on Move's triad, Scale, Draft and the other handles by
  sf/polish-2.) Press Pull on a face (an offset) does not snap to a clicked face; no snapping to edges or sketch points
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
- **sweep-loft-rib.md**: (Sweep formulas by sf/modeling-2; solid Loft Tangent Edges Merge, end
  conditions with rails / a centerline, rails on other bodies' edges, parameters for the end
  values, by sf/surface-2.) Left: Tangent Edges Merge is off by default (OpenCASCADE's volume
  of a merged side is 5.6 % off); three or more rails are refused; a closed loft with rails or
  a centerline is refused; no start-point matching for closed lofts; turning rail lofts are
  about 1 % off.
- **surface.md**: (Surface Extrude From Object / All / To Object with Chain Faces, Revolve
  To, Sweep with a guide rail, profile scaling, taper and twist, Loft rails / centerline / end
  conditions / Merge, Stitch's green edges, by sf/surface-2.) Left: Sweep Path + Guide Rail
  extents; Extrude All counts the bodies visible when the step was made; no taper from a
  slanted or curved start; Patch per-edge continuity and Tangency Weight; Extend Align Edges.
- **text-emboss.md**: (a text frame resized by dragging its corner by sf/sketch-2.)
- **insert-export.md**: (STEP / IGES open and insert as components, STEP export with
  structure, IGES / DXF / mesh export, SVG / DXF / Canvas manipulators, Insert Design as a
  linked component with Break Link, Data Panel Upload, by sf/exchange-2.) Left: bodies inside
  a component come back as Body1, Body2 after a STEP round trip; an inserted design's own
  components come in flat; a linked copy can be edited in place; DWG needs a free converter
  (none bundled); no SAT / SMT / F3D / FBX / USD; no McMaster-Carr; the decal's scale arrow has
  no value box.
- **mesh.md**: (Direct Edit with brush / window / free-form selection, delete, move, smooth,
  Erase and Fill, Reverse Normal; Create / Combine Face Groups; mesh steps roll back with the
  marker, by sf/mesh-inspect-2.) Left: no contextual ribbon tab (one dialog); Move is an arrow,
  not Fusion's triad; no Remesh / Reduce on picked face groups; no Shift+F face-group colours.
- **inspect.md**: (Interference Create Bodies and Measure's Component filter by
  sf/mesh-inspect-2.) Left: no Cycle Component Color.
- **inspect-analysis.md**: (Zebra on mesh bodies and Include Sharp Curves in Minimum Radius by
  sf/mesh-inspect-2.) The other analyses refuse mesh bodies (only Zebra is documented for
  meshes).
- **misc.md**: (Decals follow their face through moves, joints, face edits and component
  copies by sf/fix-decal; Derive keeps the component structure and takes a chosen version, by
  sf/polish-2.) No adsk add-in API. A decal on a component's copy is listed only under the
  original; a face that changes shape and moves in one step may lose its decal (red, Select
  Face puts it back).
- **selection.md**: (double-click chain selection in sketches, Fusion's box modifiers, box
  selection of planes, axes and points, by sf/sketch-2.)
- **timeline-browser.md**: (Groups dragged as a whole, Roll History Marker Here on a group, by
  sf/polish-2; the rolled-back Extrude switching to Cut was already fixed in 27d4492778.)
  Groups cannot nest. No New Body command.
- **versions.md**: (Milestones, automatic version on close, Data Panel Move / Copy of designs,
  the out-of-date button, by sf/polish-2.) No Move / Copy of whole folders; Get Latest updates
  every out-of-date reference at once; FreeCAD's Close All Documents still asks FreeCAD's
  question.
- **ui-shell.md**: dialogs are docked, not floating. Document tabs are at the bottom. No
  COMMENTS panel. No lit environments.

## Needs FreeCAD C++ or the kernel

- Patch Curvature continuity: core patch #14, in full build #6 (63fe08ff6d) and later.
- A hole's seam line across bent section views: TechDraw's DrawViewSection (C++); straight
  sections hide it (sf/drawings-2).
- Fillet Tangent Chain off, G2 fillets, setback corners: OpenCASCADE limits (fillet.md).
- Sketch Curvature constraint: FreeCAD's solver has none (G2 only spline-line).
