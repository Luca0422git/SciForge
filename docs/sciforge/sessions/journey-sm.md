### Session log: SHEET METAL journey (branch `sf/journey-sm`, wave 6, 2026-10-23)

An end-to-end test of the SHEET METAL tab as a Fusion user uses it, across the tools of
sm-forming (Sheet Metal Rules, Flange), sm-more (Hem, Corner Closure) and sm-flat (Create
Flat Pattern, Export DXF, Convert to Sheet Metal, Rip), only real clicks and keys.

**Scenarios**

- `journey_sheetmetal`: a new design; SHEET METAL tab; Sheet Metal Rules: Aluminum (mm)
  copied from the library and made active (the Document Settings row follows); Create Sketch
  on XY, a 60 x 40 rectangle; Flange, a click inside it: a 1.5 mm plate following Aluminum
  (mm); Flange on the right and front edges together, Height 15: mitred corner (volume by
  hand, golden `sheetmetal_edge_flange_miter`'s sum); Hem (Open) on the back edge (volume
  from the hem's cross-section, 57 mm of edge); Corner Closure on the mitred corner (the
  front wall's end edge, the right wall's), gap 0.2; Create Sketch on the right wall, a
  circle, E, -10: a hole through the wall; Create Flat Pattern from the plate's top: 73.89 x
  59.39 = (60 - (R + T)) + BA + (H - R) by (H - R) + BA + 37 + the hem's flat length; Export
  DXF read back (outline, the hole on INTERIOR_PROFILES, three bend centre lines, six extent
  lines); Finish Flat Pattern; the rule's Thickness edited to 2: the folded part (top at 17)
  and the flat (73.52 x 58.72) follow; Ctrl+Z / Ctrl+Y; saved (Ctrl+S, version), closed,
  reopened: the part, the timeline and the flat pattern intact, the flat opens with a
  double-click; Flange 2 edited from the timeline to Height 20: the hem, the closure, the
  hole and the flat follow; Ctrl+Z.
- `journey_sheetmetal_convert`: a 40 x 30 x 20 block (Create Sketch, E), its vertical edges
  rounded 2 (F, three edges, the view turned, the fourth), Shell with the top and (view
  turned over) the bottom taken away, 1 mm: a tube; Convert to Sheet Metal from the front
  wall (1.000 mm, 4 bends, Template Rule); Rip (Face) on the back-right corner; Create Flat
  Pattern from the front wall: 36 + 26 + 36 + 26 + 3 BA = 130.79 x 20, 3 bends; Finish;
  Ctrl+Z / Ctrl+Y.
- `journey_sheetmetal_tray`: Steel (mm); an 80 x 50 plate; Flange on all four top edges
  (four clicks), Height 20: four mitred corners; Corner Closure on the front-right corner
  with a Round relief (cut through the bends, less material); Create Flat Pattern from the
  floor: 118.52 x 88.52, 4 bends, a cross-shaped blank with the corners open; Export DXF:
  the reliefs are arcs of the outline, 4 up centre lines, 8 extent lines; Finish; Ctrl+Z /
  Ctrl+Y.

**Results (FreeCAD 1.1.4, xvfb)**: `journey_sheetmetal` PASS (151 checks),
`journey_sheetmetal_convert` PASS (44), `journey_sheetmetal_tray` PASS (46); the eleven
`flatpattern_*` scenarios PASS after the fix; golden `sm_flat*` 19 pass; unit OK. Checked
headless as well: the flat pattern follows the rule's K factor and Bend Radius, and an edit
of Flange 2's height rebuilds the hem and the Corner Closure exactly as a fresh build.

**Fixed**

- `flatpattern.refind`: the flat pattern's stationary face was only looked for in its old
  plane, so changing the rule's Thickness made the Flat Pattern red ("the stationary face
  is gone after an edit"). It now follows a face that moved along its normal. Golden model
  `sm_flat_thickness_follow` (1 mm then 2 mm L bracket, analytic sizes).

**Not bugs (documented gaps, worked around in the journey)**

- A shelled box with sharp corners cannot be converted (sheet-metal-flat.md, Convert row;
  Fusion's forum answer says the same): the convert journey rounds the vertical edges and
  takes the top and bottom away (a tube), then Rips it.
- Corner reliefs are cut on the flat only and a corner closed by Corner Closure gets none
  (sheet-metal-flat.md Known gaps): the DXF check counts the outline, not relief circles.

**Seen, not fixed**

- When the flat pattern is created, FreeCAD logs "CornerClosure.DominantEdge missing element
  reference ... Hem ... Edge45": the Corner Closure keeps its edges as plain names on the
  step before it (a Python feature's shape, whose element map FreeCAD rebuilds with other
  hashed names). The closure still rebuilds right (the edge keeps its number while the
  topology stays the same, as in every edit of the journey); an edit that renumbers the
  hem's edges could make it pick another edge (sm-more's area).
- The journey's first hem check used the smmore_hem scenario's volume formula
  (FLAT + x0 L + strip L), which holds only for a 1 mm sheet: the sheet cut back is x0 T.
